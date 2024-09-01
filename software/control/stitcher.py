# napari + stitching libs
import os
import sys
from control._def import *
from qtpy.QtCore import *

import psutil
import shutil
import random
import json
import time
import math
from datetime import datetime
from lxml import etree
import numpy as np
import pandas as pd
import cv2
import dask.array as da
from dask.array import from_zarr
from dask_image.imread import imread as dask_imread
from skimage.registration import phase_cross_correlation
import ome_zarr
import zarr
from tifffile import TiffWriter
from aicsimageio.writers import OmeTiffWriter
from aicsimageio.writers import OmeZarrWriter
from aicsimageio import types
from basicpy import BaSiC

class Stitcher(QThread, QObject):

    update_progress = Signal(int, int)
    getting_flatfields = Signal()
    starting_stitching = Signal()
    starting_saving = Signal(bool)
    finished_saving = Signal(str, object)

    def __init__(self, input_folder, output_name='', output_format=".ome.zarr", apply_flatfield=0, use_registration=0, registration_channel='', registration_z_level=0, flexible=True):
        QThread.__init__(self)
        QObject.__init__(self)
        self.input_folder = input_folder
        self.image_folder = None
        self.output_name = output_name + output_format
        self.apply_flatfield = apply_flatfield
        self.use_registration = use_registration
        if use_registration:
            self.registration_channel = registration_channel
            self.registration_z_level = registration_z_level

        self.selected_modes = self.extract_selected_modes(self.input_folder)
        self.acquisition_params = self.extract_acquisition_parameters(self.input_folder)
        self.time_points = self.get_time_points(self.input_folder)
        print("timepoints:", self.time_points)
        self.is_reversed = self.determine_directions(self.input_folder) # init: top to bottom, left to right
        print(self.is_reversed)
        self.is_wellplate = IS_HCS
        self.flexible = flexible
        self.pixel_size_um = 1.0
        self.init_stitching_parameters()
        # self.overlap_percent = Acquisition.OVERLAP_PERCENT

    def init_stitching_parameters(self):
        self.is_rgb = {}
        self.regions = []
        self.channel_names = []
        self.mono_channel_names = []
        self.channel_colors = []
        self.num_z = self.num_c = 1
        self.num_cols = self.num_rows = 1
        self.input_height = self.input_width = 0
        self.num_pyramid_levels = 5
        self.v_shift = self.h_shift = (0,0)
        self.max_x_overlap = self.max_y_overlap = 0
        self.flatfields = {}
        self.stitching_data = {}
        self.tczyx_shape = (len(self.time_points),self.num_c,self.num_z,self.num_rows*self.input_height,self.num_cols*self.input_width)
        self.stitched_images = None
        self.chunks = None
        self.dtype = np.uint16

    def get_time_points(self, input_folder):
        try: # detects directories named as integers, representing time points.
            time_points = [d for d in os.listdir(input_folder) if os.path.isdir(os.path.join(input_folder, d)) and d.isdigit()]
            time_points.sort(key=int)
            return time_points
        except Exception as e:
            print(f"Error detecting time points: {e}")
            return ['0']

    def extract_selected_modes(self, input_folder):
        try:
            configs_path = os.path.join(input_folder, 'configurations.xml')
            tree = etree.parse(configs_path)
            root = tree.getroot()
            selected_modes = {}
            for mode in root.findall('.//mode'):
                if mode.get('Selected') == '1':
                    mode_id = mode.get('ID')
                    selected_modes[mode_id] = {
                        'Name': mode.get('Name'),
                        'ExposureTime': mode.get('ExposureTime'),
                        'AnalogGain': mode.get('AnalogGain'),
                        'IlluminationSource': mode.get('IlluminationSource'),
                        'IlluminationIntensity': mode.get('IlluminationIntensity')
                    }
            return selected_modes
        except Exception as e:
            print(f"Error reading selected modes: {e}")

    def extract_acquisition_parameters(self, input_folder):
        acquistion_params_path = os.path.join(input_folder, 'acquisition parameters.json')
        with open(acquistion_params_path, 'r') as file:
            acquisition_params = json.load(file)
        return acquisition_params

    def extract_wavelength(self, name):
        # Split the string and find the wavelength number immediately after "Fluorescence"
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]  # Assuming '488 nm Ex' and taking '488'
        for color in ['R', 'G', 'B']:
            if color in parts:
                return color
        return None

    def determine_directions(self, input_folder):
        # return {'rows': self.acquisition_params.get("row direction", False),
        #         'cols': self.acquisition_params.get("col direction", False),
        #         'z-planes': False}
        coordinates = pd.read_csv(os.path.join(input_folder, self.time_points[0], 'coordinates.csv'))
        try:
            first_region = coordinates['region'].unique()[0]
            coordinates = coordinates[coordinates['region'] == first_region]
            self.is_wellplate = True
        except Exception as e:
            print("no coordinates.csv well data:", e)
            self.is_wellplate = False
        i_rev = not coordinates.sort_values(by='i')['y (mm)'].is_monotonic_increasing
        j_rev = not coordinates.sort_values(by='j')['x (mm)'].is_monotonic_increasing
        k_rev = not coordinates.sort_values(by='z_level')['z (um)'].is_monotonic_increasing
        return {'rows': i_rev, 'cols': j_rev, 'z-planes': k_rev}

    def parse_filenames(self, time_point):
        # Initialize directories and read files
        self.image_folder = os.path.join(self.input_folder, str(time_point))
        print("stitching image folder:", self.image_folder)
        self.init_stitching_parameters()

        all_files = os.listdir(self.image_folder)
        sorted_input_files = sorted(
            [filename for filename in all_files if filename.endswith((".bmp", ".tiff")) and 'focus_camera' not in filename]
        )
        if not sorted_input_files:
            raise Exception("No valid files found in directory.")

        first_filename = sorted_input_files[0]
        try:
            first_region, first_i, first_j, first_k, channel_name = os.path.splitext(first_filename)[0].split('_', 4)
            first_k = int(first_k)
            print("region_i_j_k_channel_name: ", os.path.splitext(first_filename)[0])
            self.is_wellplate = True
        except ValueError as ve:
            first_i, first_j, first_k, channel_name = os.path.splitext(first_filename)[0].split('_', 3)
            print("i_j_k_channel_name: ", os.path.splitext(first_filename)[0])
            self.is_wellplate = False

        input_extension = os.path.splitext(sorted_input_files[0])[1]
        max_i, max_j, max_k = 0, 0, 0
        regions, channel_names = set(), set()

        for filename in sorted_input_files:
            if self.is_wellplate:
                region, i, j, k, channel_name = os.path.splitext(filename)[0].split('_', 4)
            else:
                region = '0'
                i, j, k, channel_name = os.path.splitext(filename)[0].split('_', 3)

            channel_name = channel_name.replace("_", " ").replace("full ", "full_")
            i, j, k = int(i), int(j), int(k)

            regions.add(region)
            channel_names.add(channel_name)
            max_i, max_j, max_k = max(max_i, i), max(max_j, j), max(max_k, k)

            tile_info = {
                'filepath': os.path.join(self.image_folder, filename),
                'region': region,
                'channel': channel_name,
                'z_level': k,
                'row': i,
                'col': j
            }
            self.stitching_data.setdefault(region, {}).setdefault(channel_name, {}).setdefault(k, {}).setdefault((i, j), tile_info)

        self.regions = sorted(regions)
        self.channel_names = sorted(channel_names)
        self.num_z, self.num_cols, self.num_rows = max_k + 1, max_j + 1, max_i + 1

        first_coord = f"{self.regions[0]}_{first_i}_{first_j}_{first_k}_" if self.is_wellplate else f"{first_i}_{first_j}_{first_k}_"
        found_dims = False
        mono_channel_names = []

        for channel in self.channel_names:
            filename = first_coord + channel.replace(" ", "_") + input_extension
            image = dask_imread(os.path.join(self.image_folder, filename))[0]

            if not found_dims:
                self.dtype = np.dtype(image.dtype)
                self.input_height, self.input_width = image.shape[:2]
                self.chunks = (1, 1, 1, self.input_height//2, self.input_width//2)
                found_dims = True
                print("chunks", self.chunks)

            if len(image.shape) == 3:
                self.is_rgb[channel] = True
                channel = channel.split('_')[0]
                mono_channel_names.extend([f"{channel}_R", f"{channel}_G", f"{channel}_B"])
            else:
                self.is_rgb[channel] = False
                mono_channel_names.append(channel)

        self.mono_channel_names = mono_channel_names
        self.num_c = len(mono_channel_names)
        self.channel_colors = [CHANNEL_COLORS_MAP.get(self.extract_wavelength(name), {'hex': 0xFFFFFF})['hex'] for name in self.mono_channel_names]
        print(self.mono_channel_names)
        print(self.regions)

    def get_flatfields(self, progress_callback=None):
        def process_images(images, channel_name):
            images = np.array(images)
            basic = BaSiC(get_darkfield=False, smoothness_flatfield=1)
            basic.fit(images)
            channel_index = self.mono_channel_names.index(channel_name)
            self.flatfields[channel_index] = basic.flatfield
            if progress_callback:
                progress_callback(channel_index + 1, self.num_c)

        # Iterate only over the channels you need to process
        for channel in self.channel_names:
            all_tiles = []
            # Collect tiles from all roi and z-levels for the current channel
            for roi in self.regions:
                for z_level in self.stitching_data[roi][channel]:
                    for row_col, tile_info in self.stitching_data[roi][channel][z_level].items():
                        all_tiles.append(tile_info)

            # Shuffle and select a subset of tiles for flatfield calculation
            random.shuffle(all_tiles)
            selected_tiles = all_tiles[:min(32, len(all_tiles))]

            if self.is_rgb[channel]:
                # Process each color channel if the channel is RGB
                images_r = [dask_imread(tile['filepath'])[0][:, :, 0] for tile in selected_tiles]
                images_g = [dask_imread(tile['filepath'])[0][:, :, 1] for tile in selected_tiles]
                images_b = [dask_imread(tile['filepath'])[0][:, :, 2] for tile in selected_tiles]
                channel = channel.split('_')[0]
                process_images(images_r, channel + '_R')
                process_images(images_g, channel + '_G')
                process_images(images_b, channel + '_B')
            else:
                # Process monochrome images
                images = [dask_imread(tile['filepath'])[0] for tile in selected_tiles]
                process_images(images, channel)

    def normalize_image(self, img):
        img_min, img_max = img.min(), img.max()
        img_normalized = (img - img_min) / (img_max - img_min)
        scale_factor = np.iinfo(self.dtype).max if np.issubdtype(self.dtype, np.integer) else 1
        return (img_normalized * scale_factor).astype(self.dtype)

    def visualize_image(self, img1, img2, title):
        if title == 'horizontal':
            combined_image = np.hstack((img1, img2))
        else:
            combined_image = np.vstack((img1, img2))
        cv2.imwrite(f"{self.input_folder}/{title}.png", combined_image)

    def calculate_horizontal_shift(self, img1_path, img2_path, max_overlap, margin_ratio=0.2):
        try:
            img1 = dask_imread(img1_path)[0].compute()
            img2 = dask_imread(img2_path)[0].compute()
            img1 = self.normalize_image(img1)
            img2 = self.normalize_image(img2)

            margin = int(self.input_height * margin_ratio)
            img1_overlap = (img1[margin:-margin, -max_overlap:]).astype(self.dtype)
            img2_overlap = (img2[margin:-margin, :max_overlap]).astype(self.dtype)

            self.visualize_image(img1_overlap, img2_overlap, "horizontal")
            shift, error, diffphase = phase_cross_correlation(img1_overlap, img2_overlap, upsample_factor=10)
            return round(shift[0]), round(shift[1] - img1_overlap.shape[1])
        except Exception as e:
            print(f"Error calculating horizontal shift: {e}")
            return (0, 0)

    def calculate_vertical_shift(self, img1_path, img2_path, max_overlap, margin_ratio=0.2):
        try:
            img1 = dask_imread(img1_path)[0].compute()
            img2 = dask_imread(img2_path)[0].compute()
            img1 = self.normalize_image(img1)
            img2 = self.normalize_image(img2)

            margin = int(self.input_width * margin_ratio)
            img1_overlap = (img1[-max_overlap:, margin:-margin]).astype(self.dtype)
            img2_overlap = (img2[:max_overlap, margin:-margin]).astype(self.dtype)

            self.visualize_image(img1_overlap, img2_overlap, "vertical")
            shift, error, diffphase = phase_cross_correlation(img1_overlap, img2_overlap, upsample_factor=10)
            return round(shift[0] - img1_overlap.shape[0]), round(shift[1])
        except Exception as e:
            print(f"Error calculating vertical shift: {e}")
            return (0, 0)

    def calculate_shifts(self, roi=""):
        roi = self.regions[0] if roi not in self.regions else roi
        self.registration_channel = self.registration_channel if self.registration_channel in self.channel_names else self.channel_names[0]

        # Calculate estimated overlap from acquisition parameters
        dx_mm = self.acquisition_params['dx(mm)']
        dy_mm = self.acquisition_params['dy(mm)']
        obj_mag = self.acquisition_params['objective']['magnification']
        obj_tube_lens_mm = self.acquisition_params['objective']['tube_lens_f_mm']
        sensor_pixel_size_um = self.acquisition_params['sensor_pixel_size_um']
        tube_lens_mm = self.acquisition_params['tube_lens_mm']

        obj_focal_length_mm = obj_tube_lens_mm / obj_mag
        actual_mag = tube_lens_mm / obj_focal_length_mm
        self.pixel_size_um = sensor_pixel_size_um / actual_mag
        print("pixel_size_um:", self.pixel_size_um)

        dx_pixels = dx_mm * 1000 / self.pixel_size_um
        dy_pixels = dy_mm * 1000 / self.pixel_size_um
        print("dy_pixels", dy_pixels, ", dx_pixels:", dx_pixels)

        self.max_x_overlap = round(abs(self.input_width - dx_pixels) / 2)
        self.max_y_overlap = round(abs(self.input_height - dy_pixels) / 2)
        print("objective calculated - vertical overlap:", self.max_y_overlap, ", horizontal overlap:", self.max_x_overlap)

        col_left, col_right = (self.num_cols - 1) // 2, (self.num_cols - 1) // 2 + 1
        if self.is_reversed['cols']:
            col_left, col_right = col_right, col_left

        row_top, row_bottom = (self.num_rows - 1) // 2, (self.num_rows - 1) // 2 + 1
        if self.is_reversed['rows']:
            row_top, row_bottom = row_bottom, row_top

        img1_path = img2_path_vertical = img2_path_horizontal = None
        for (row, col), tile_info in self.stitching_data[roi][self.registration_channel][self.registration_z_level].items():
            if col == col_left and row == row_top:
                img1_path = tile_info['filepath']
            elif col == col_left and row == row_bottom:
                img2_path_vertical = tile_info['filepath']
            elif col == col_right and row == row_top:
                img2_path_horizontal = tile_info['filepath']

        if img1_path is None:
            raise Exception(
                f"No input file found for c:{self.registration_channel} k:{self.registration_z_level} "
                f"j:{col_left} i:{row_top}"
            )

        self.v_shift = (
            self.calculate_vertical_shift(img1_path, img2_path_vertical, self.max_y_overlap)
            if self.max_y_overlap > 0 and img2_path_vertical and img1_path != img2_path_vertical else (0, 0)
        )
        self.h_shift = (
            self.calculate_horizontal_shift(img1_path, img2_path_horizontal, self.max_x_overlap)
            if self.max_x_overlap > 0 and img2_path_horizontal and img1_path != img2_path_horizontal else (0, 0)
        )
        print("vertical shift:", self.v_shift, ", horizontal shift:", self.h_shift)

    def calculate_dynamic_shifts(self, roi, channel, z_level, row, col):
        h_shift, v_shift = self.h_shift, self.v_shift

        # Check for left neighbor
        if (row, col - 1) in self.stitching_data[roi][channel][z_level]:
            left_tile_path = self.stitching_data[roi][channel][z_level][row, col - 1]['filepath']
            current_tile_path = self.stitching_data[roi][channel][z_level][row, col]['filepath']
            # Calculate horizontal shift
            new_h_shift = self.calculate_horizontal_shift(left_tile_path, current_tile_path, abs(self.h_shift[1]))

            # Check if the new horizontal shift is within 10% of the precomputed shift
            if self.h_shift == (0,0) or (0.95 * abs(self.h_shift[1]) <= abs(new_h_shift[1]) <= 1.05 * abs(self.h_shift[1]) and
                0.95 * abs(self.h_shift[0]) <= abs(new_h_shift[0]) <= 1.05 * abs(self.h_shift[0])):
                print("new h shift", new_h_shift, h_shift)
                h_shift = new_h_shift

        # Check for top neighbor
        if (row - 1, col) in self.stitching_data[roi][channel][z_level]:
            top_tile_path = self.stitching_data[roi][channel][z_level][row - 1, col]['filepath']
            current_tile_path = self.stitching_data[roi][channel][z_level][row, col]['filepath']
            # Calculate vertical shift
            new_v_shift = self.calculate_vertical_shift(top_tile_path, current_tile_path, abs(self.v_shift[0]))

            # Check if the new vertical shift is within 10% of the precomputed shift
            if self.v_shift == (0,0) or (0.95 * abs(self.v_shift[0]) <= abs(new_v_shift[0]) <= 1.05 * abs(self.v_shift[0]) and
                0.95 * abs(self.v_shift[1]) <= abs(new_v_shift[1]) <= 1.05 * abs(self.v_shift[1])):
                print("new v shift", new_v_shift, v_shift)
                v_shift = new_v_shift

        return h_shift, v_shift

    def init_output(self, time_point, region_id):
        output_folder = os.path.join(self.input_folder, f"{time_point}_stitched")
        os.makedirs(output_folder, exist_ok=True)
        self.output_path = os.path.join(output_folder, f"{region_id}_{self.output_name}" if self.is_wellplate else self.output_name)

        x_max = (self.input_width + ((self.num_cols - 1) * (self.input_width + self.h_shift[1])) + # horizontal width with overlap
                abs((self.num_rows - 1) * self.v_shift[1])) # horizontal shift from vertical registration
        y_max = (self.input_height + ((self.num_rows - 1) * (self.input_height + self.v_shift[0])) + # vertical height with overlap
                abs((self.num_cols - 1) * self.h_shift[0])) # vertical shift from horizontal registration
        if self.use_registration and DYNAMIC_REGISTRATION:
            y_max *= 1.05
            x_max *= 1.05
        size = max(y_max, x_max)
        num_levels = 1
        
        # Get the number of rows and columns
        if self.is_wellplate and STITCH_COMPLETE_ACQUISITION:
            rows, columns = self.get_rows_and_columns() 
            self.num_pyramid_levels = math.ceil(np.log2(max(x_max, y_max) / 1024 * max(len(rows), len(columns))))
        else:
            self.num_pyramid_levels = math.ceil(np.log2(max(x_max, y_max) / 1024))
        print("num_pyramid_levels", self.num_pyramid_levels)

        tczyx_shape = (1, self.num_c, self.num_z, y_max, x_max)
        self.tczyx_shape = tczyx_shape
        print(f"(t:{time_point}, roi:{region_id}) output shape: {tczyx_shape}")
        return da.zeros(tczyx_shape, dtype=self.dtype, chunks=self.chunks)

    def stitch_images(self, time_point, roi, progress_callback=None):
        self.stitched_images = self.init_output(time_point, roi)
        total_tiles = sum(len(z_data) for channel_data in self.stitching_data[roi].values() for z_data in channel_data.values())
        processed_tiles = 0

        for z_level in range(self.num_z):

            for row in range(self.num_rows):
                row = self.num_rows - 1 - row if self.is_reversed['rows'] else row

                for col in range(self.num_cols):
                    col = self.num_cols - 1 - col if self.is_reversed['cols'] else col

                    if self.use_registration and DYNAMIC_REGISTRATION and z_level == self.registration_z_level:
                        if (row, col) in self.stitching_data[roi][self.registration_channel][z_level]:
                            tile_info = self.stitching_data[roi][self.registration_channel][z_level][(row, col)]
                            self.h_shift, self.v_shift = self.calculate_dynamic_shifts(roi, self.registration_channel, z_level, row, col)

                    # Now apply the same shifts to all channels
                    for channel in self.channel_names:
                        if (row, col) in self.stitching_data[roi][channel][z_level]:
                            tile_info = self.stitching_data[roi][channel][z_level][(row, col)]
                            tile = dask_imread(tile_info['filepath'])[0]
                            #tile = tile[:, ::-1]
                            if self.is_rgb[channel]:
                                for color_idx, color in enumerate(['R', 'G', 'B']):
                                    tile_color = tile[:, :, color_idx]
                                    color_channel = f"{channel}_{color}"
                                    self.stitch_single_image(tile_color, z_level, self.mono_channel_names.index(color_channel), row, col)
                                    processed_tiles += 1
                            else:
                                self.stitch_single_image(tile, z_level, self.mono_channel_names.index(channel), row, col)
                                processed_tiles += 1
                        if progress_callback is not None:
                            progress_callback(processed_tiles, total_tiles)

    def stitch_single_image(self, tile, z_level, channel_idx, row, col):
        #print(tile.shape)
        if self.apply_flatfield:
            tile = (tile / self.flatfields[channel_idx]).clip(min=np.iinfo(self.dtype).min,
                                                              max=np.iinfo(self.dtype).max).astype(self.dtype)
        # Determine crop for tile edges
        top_crop = max(0, (-self.v_shift[0] // 2) - abs(self.h_shift[0]) // 2) if row > 0 else 0
        bottom_crop = max(0, (-self.v_shift[0] // 2) - abs(self.h_shift[0]) // 2) if row < self.num_rows - 1 else 0
        left_crop = max(0, (-self.h_shift[1] // 2) - abs(self.v_shift[1]) // 2) if col > 0 else 0
        right_crop = max(0, (-self.h_shift[1] // 2) - abs(self.v_shift[1]) // 2) if col < self.num_cols - 1 else 0

        tile = tile[top_crop:tile.shape[0]-bottom_crop, left_crop:tile.shape[1]-right_crop]

        # Initialize starting coordinates based on tile position and shift
        y = row * (self.input_height + self.v_shift[0]) + top_crop
        if self.h_shift[0] < 0:
            y -= (self.num_cols - 1 - col) * self.h_shift[0]  # Moves up if negative
        else:
            y += col * self.h_shift[0]  # Moves down if positive

        x = col * (self.input_width + self.h_shift[1]) + left_crop
        if self.v_shift[1] < 0:
            x -= (self.num_rows - 1 - row) * self.v_shift[1]  # Moves left if negative
        else:
            x += row * self.v_shift[1]  # Moves right if positive

        # Place cropped tile on the stitched image canvas
        self.stitched_images[0, channel_idx, z_level, y:y+tile.shape[0], x:x+tile.shape[1]] = tile
        # print(f" col:{col}, \trow:{row},\ty:{y}-{y+tile.shape[0]}, \tx:{x}-{x+tile.shape[-1]}")

    def save_as_ome_tiff(self):
        dz_um = self.acquisition_params.get("dz(um)", None)
        sensor_pixel_size_um = self.acquisition_params.get("sensor_pixel_size_um", None)
        dims = "TCZYX"
        # if self.is_rgb:
        #     dims += "S"

        ome_metadata = OmeTiffWriter.build_ome(
            image_name=[os.path.basename(self.output_path)],
            data_shapes=[self.stitched_images.shape],
            data_types=[self.stitched_images.dtype],
            dimension_order=[dims],
            channel_names=[self.mono_channel_names],
            physical_pixel_sizes=[types.PhysicalPixelSizes(dz_um, self.pixel_size_um, self.pixel_size_um)],
            #is_rgb=self.is_rgb
            #channel colors
        )
        OmeTiffWriter.save(
            data=self.stitched_images,
            uri=self.output_path,
            ome_xml=ome_metadata,
            dimension_order=[dims]
            #channel colors / names
        )
        self.stitched_images = None

    def save_as_ome_zarr(self):
        dz_um = self.acquisition_params.get("dz(um)", None)
        sensor_pixel_size_um = self.acquisition_params.get("sensor_pixel_size_um", None)
        dims = "TCZYX"
        intensity_min = np.iinfo(self.dtype).min
        intensity_max = np.iinfo(self.dtype).max
        channel_minmax = [(intensity_min, intensity_max)] * self.num_c
        for i in range(self.num_c):
            print(f"Channel {i}:", self.mono_channel_names[i], " \tColor:", self.channel_colors[i], " \tPixel Range:", channel_minmax[i])

        zarr_writer = OmeZarrWriter(self.output_path)
        zarr_writer.build_ome(
            size_z=self.num_z,
            image_name=os.path.basename(self.output_path),
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            channel_minmax=channel_minmax
        )
        zarr_writer.write_image(
            image_data=self.stitched_images,
            image_name=os.path.basename(self.output_path),
            physical_pixel_sizes=types.PhysicalPixelSizes(dz_um, self.pixel_size_um, self.pixel_size_um),
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            dimension_order=dims,
            scale_num_levels=self.num_pyramid_levels,
            chunk_dims=self.chunks
        )
        self.stitched_images = None

    def create_complete_ome_zarr(self):
        """ Creates a complete OME-ZARR with proper channel metadata. """
        final_path = os.path.join(self.input_folder, self.output_name.replace(".ome.zarr","") + "_complete_acquisition.ome.zarr")
        if len(self.time_points) == 1:
            zarr_path = os.path.join(self.input_folder, f"0_stitched", self.output_name)
            #final_path = zarr_path
            shutil.copytree(zarr_path, final_path)
        else:
            store = ome_zarr.io.parse_url(final_path, mode="w").store
            root_group = zarr.group(store=store)
            intensity_min = np.iinfo(self.dtype).min
            intensity_max = np.iinfo(self.dtype).max

            data = self.load_and_merge_timepoints()
            ome_zarr.writer.write_image(
                image=data,
                group=root_group,
                axes="tczyx",
                channel_names=self.mono_channel_names,
                storage_options=dict(chunks=self.chunks)
            )

            channel_info = [{
                "label": self.mono_channel_names[i],
                "color": f"{self.channel_colors[i]:06X}",
                "window": {"start": intensity_min, "end": intensity_max},
                "active": True
            } for i in range(self.num_c)]

            # Assign the channel metadata to the image group
            root_group.attrs["omero"] = {"channels": channel_info}

            print(f"Data saved in OME-ZARR format at: {final_path}")
            root = zarr.open(final_path, mode='r')
            print(root.tree())
            print(dict(root.attrs))
        self.finished_saving.emit(final_path, self.dtype)

    def create_hcs_ome_zarr(self):
        """Creates a hierarchical Zarr file in the HCS OME-ZARR format for visualization in napari."""
        hcs_path = os.path.join(self.input_folder, self.output_name.replace(".ome.zarr","") + "_complete_acquisition.ome.zarr")
        if len(self.time_points) == 1 and len(self.regions) == 1:
            stitched_zarr_path = os.path.join(self.input_folder, f"0_stitched", f"{self.regions[0]}_{self.output_name}")
            #hcs_path = stitched_zarr_path # replace next line with this if no copy wanted
            shutil.copytree(stitched_zarr_path, hcs_path)
        else:
            store = ome_zarr.io.parse_url(hcs_path, mode="w").store
            root_group = zarr.group(store=store)

            # Retrieve row and column information for plate metadata
            rows, columns = self.get_rows_and_columns()
            well_paths = [f"{well_id[0]}/{well_id[1:]}" for well_id in sorted(self.regions)]
            print(well_paths)
            ome_zarr.writer.write_plate_metadata(root_group, rows, [str(col) for col in columns], well_paths)

            # Loop over each well and save its data
            for well_id in self.regions:
                row, col = well_id[0], well_id[1:]
                row_group = root_group.require_group(row)
                well_group = row_group.require_group(col)
                self.write_well_and_metadata(well_id, well_group)

            print(f"Data saved in HCS OME-ZARR format at: {hcs_path}")

            print("HCS root attributes:")
            root = zarr.open(hcs_path, mode='r')
            print(root.tree())
            print(dict(root.attrs))

        self.finished_saving.emit(hcs_path, self.dtype)

    def write_well_and_metadata(self, well_id, well_group):
        """Process and save data for a single well across all timepoints."""
        # Load data from precomputed Zarrs for each timepoint
        data = self.load_and_merge_timepoints(well_id)
        intensity_min = np.iinfo(self.dtype).min
        intensity_max = np.iinfo(self.dtype).max
        #dataset = well_group.create_dataset("data", data=data, chunks=(1, 1, 1, self.input_height, self.input_width), dtype=data.dtype)
        field_paths = ["0"]  # Assuming single field of view
        ome_zarr.writer.write_well_metadata(well_group, field_paths)
        for fi, field in enumerate(field_paths):
            image_group = well_group.require_group(str(field))
            ome_zarr.writer.write_image(image=data,
                                        group=image_group,
                                        axes="tczyx",
                                        channel_names=self.mono_channel_names,
                                        storage_options=dict(chunks=self.chunks)
                                        )
            channel_info = [{
                "label": self.mono_channel_names[c],
                "color": f"{self.channel_colors[c]:06X}",
                "window": {"start": intensity_min, "end": intensity_max},
                "active": True
            } for c in range(self.num_c)]

            image_group.attrs["omero"] = {"channels": channel_info}

    def pad_to_largest(self, array, target_shape):
        if array.shape == target_shape:
            return array
        pad_widths = [(0, max(0, ts - s)) for s, ts in zip(array.shape, target_shape)]
        return da.pad(array, pad_widths, mode='constant', constant_values=0)

    def load_and_merge_timepoints(self, well_id=''):
        """Load and merge data for a well from Zarr files for each timepoint."""
        t_data = []
        t_shapes = []
        for t in self.time_points:
            if self.is_wellplate:
                filepath = f"{well_id}_{self.output_name}"
            else:
                filepath = f"{self.output_name}"
            zarr_path = os.path.join(self.input_folder, f"{t}_stitched", filepath)
            print(f"t:{t} well:{well_id}, \t{zarr_path}")
            z = zarr.open(zarr_path, mode='r')
            # Ensure that '0' contains the data and it matches expected dimensions
            x_max = self.input_width + ((self.num_cols - 1) * (self.input_width + self.h_shift[1])) + abs((self.num_rows - 1) * self.v_shift[1])
            y_max = self.input_height + ((self.num_rows - 1) * (self.input_height + self.v_shift[0])) + abs((self.num_cols - 1) * self.h_shift[0])
            t_array = da.from_zarr(z['0'], chunks=self.chunks)
            t_data.append(t_array)
            t_shapes.append(t_array.shape)

        # Concatenate arrays along the existing time axis if multiple timepoints are present
        if len(t_data) > 1:
            max_shape = tuple(max(s) for s in zip(*t_shapes))
            padded_data = [self.pad_to_largest(t, max_shape) for t in t_data]
            data = da.concatenate(padded_data, axis=0)
            print(f"(merged timepoints, well:{well_id}) output shape: {data.shape}")
            return data
        elif len(t_data) == 1:
            data = t_data[0]
            return data
        else:
            raise ValueError("no data loaded from timepoints.")

    def get_rows_and_columns(self):
        """Utility to extract rows and columns from well identifiers."""
        rows = set()
        columns = set()
        for well_id in self.regions:
            rows.add(well_id[0])  # Assuming well_id like 'A1'
            columns.add(int(well_id[1:]))
        return sorted(rows), sorted(columns)

    def run(self):
        # Main stitching logic
        stime = time.time()
        try:
            for time_point in self.time_points:
                ttime = time.time()
                print(f"starting t:{time_point}...")
                self.parse_filenames(time_point)

                if self.apply_flatfield:
                    print(f"getting flatfields...")
                    self.getting_flatfields.emit()
                    self.get_flatfields(progress_callback=self.update_progress.emit)
                    print("time to apply flatfields", time.time() - ttime)


                if self.use_registration:
                    shtime = time.time()
                    print(f"calculating shifts...")
                    self.calculate_shifts()
                    print("time to calculate shifts", time.time() - shtime)

                for well in self.regions:
                    wtime = time.time()
                    self.starting_stitching.emit()
                    print(f"\nstarting stitching...")
                    self.stitch_images(time_point, well, progress_callback=self.update_progress.emit)

                    sttime = time.time()
                    print("time to stitch well", sttime - wtime)

                    self.starting_saving.emit(not STITCH_COMPLETE_ACQUISITION)
                    print(f"saving...")
                    if ".ome.tiff" in self.output_path:
                        self.save_as_ome_tiff()
                    else:
                        self.save_as_ome_zarr()

                    print("time to save stitched well", time.time() - sttime)
                    print("time per well", time.time() - wtime)
                    if well != '0':
                        print(f"...done saving well:{well}")
                print(f"...finished t:{time_point}")
                print("time per timepoint", time.time() - ttime)

            if STITCH_COMPLETE_ACQUISITION and not self.flexible and ".ome.zarr" in self.output_name:
                self.starting_saving.emit(True)
                scatime = time.time()
                if self.is_wellplate:
                    self.create_hcs_ome_zarr()
                    print(f"...done saving complete hcs successfully")
                else:
                    self.create_complete_ome_zarr()
                    print(f"...done saving complete successfully")
                print("time to save merged wells and timepoints", time.time() - scatime)
            else:
                self.finished_saving.emit(self.output_path, self.dtype)
            print("total time to stitch + save:", time.time() - stime)

        except Exception as e:
            print("time before error", time.time() - stime)
            print(f"error While Stitching: {e}")



class CoordinateStitcher(QThread, QObject):
    update_progress = Signal(int, int)
    getting_flatfields = Signal()
    starting_stitching = Signal()
    starting_saving = Signal(bool)
    finished_saving = Signal(str, object)

    def __init__(self, input_folder, output_name='', output_format=".ome.zarr", apply_flatfield=0, use_registration=0, registration_channel='', registration_z_level=0, overlap_percent=0):
        super().__init__()
        self.input_folder = input_folder
        self.output_name = output_name + output_format
        self.output_format = output_format
        self.apply_flatfield = apply_flatfield
        self.use_registration = use_registration
        if use_registration:
            self.registration_channel = registration_channel
            self.registration_z_level = registration_z_level
        self.coordinates_df = None
        self.pixel_size_um = None
        self.acquisition_params = None
        self.time_points = []
        self.regions = []
        self.overlap_percent = overlap_percent
        self.scan_pattern = FOV_PATTERN
        self.init_stitching_parameters()


    def init_stitching_parameters(self):
        self.is_rgb = {}
        self.channel_names = []
        self.mono_channel_names = []
        self.channel_colors = []
        self.num_z = self.num_c = self.num_t = 1
        self.input_height = self.input_width = 0
        self.num_pyramid_levels = 5
        self.flatfields = {}
        self.stitching_data = {}
        self.dtype = np.uint16
        self.chunks = None
        self.h_shift = (0, 0)
        if self.scan_pattern == 'S-Pattern':
            self.h_shift_rev = (0, 0)
            self.h_shift_rev_odd = 0 # 0 reverse even rows, 1 reverse odd rows
        self.v_shift = (0, 0)
        self.x_positions = set()
        self.y_positions = set()

    def get_time_points(self):
        self.time_points = [d for d in os.listdir(self.input_folder) if os.path.isdir(os.path.join(self.input_folder, d)) and d.isdigit()]
        self.time_points.sort(key=int)
        return self.time_points

    def extract_acquisition_parameters(self):
        acquistion_params_path = os.path.join(self.input_folder, 'acquisition parameters.json')
        with open(acquistion_params_path, 'r') as file:
            self.acquisition_params = json.load(file)

    def get_pixel_size_from_params(self):
        obj_mag = self.acquisition_params['objective']['magnification']
        obj_tube_lens_mm = self.acquisition_params['objective']['tube_lens_f_mm']
        sensor_pixel_size_um = self.acquisition_params['sensor_pixel_size_um']
        tube_lens_mm = self.acquisition_params['tube_lens_mm']

        obj_focal_length_mm = obj_tube_lens_mm / obj_mag
        actual_mag = tube_lens_mm / obj_focal_length_mm
        self.pixel_size_um = sensor_pixel_size_um / actual_mag
        print("pixel_size_um:", self.pixel_size_um)

    def parse_filenames(self):
        self.extract_acquisition_parameters()
        self.get_pixel_size_from_params()

        self.stitching_data = {}
        self.regions = set()
        self.channel_names = set()
        max_z = 0
        max_fov = 0

        for t, time_point in enumerate(self.time_points):
            image_folder = os.path.join(self.input_folder, str(time_point))
            coordinates_path = os.path.join(self.input_folder, time_point, 'coordinates.csv')
            coordinates_df = pd.read_csv(coordinates_path)

            print(f"Processing timepoint {time_point}, image folder: {image_folder}")

            image_files = sorted([f for f in os.listdir(image_folder) if f.endswith(('.bmp', '.tiff')) and 'focus_camera' not in f])
            
            if not image_files:
                raise Exception(f"No valid files found in directory for timepoint {time_point}.")

            for file in image_files:
                parts = file.split('_', 3)
                region, fov, z_level, channel = parts[0], int(parts[1]), int(parts[2]), os.path.splitext(parts[3])[0]
                channel = channel.replace("_", " ").replace("full ", "full_")

                coord_row = coordinates_df[(coordinates_df['region'] == region) & 
                                           (coordinates_df['fov'] == fov) & 
                                           (coordinates_df['z_level'] == z_level)]

                if coord_row.empty:
                    print(f"Warning: No matching coordinates found for file {file}")
                    continue

                coord_row = coord_row.iloc[0]

                key = (t, region, fov, z_level, channel)
                self.stitching_data[key] = {
                    'filepath': os.path.join(image_folder, file),
                    'x': coord_row['x (mm)'],
                    'y': coord_row['y (mm)'],
                    'z': coord_row['z (um)'],
                    'channel': channel,
                    'z_level': z_level,
                    'region': region,
                    'fov_idx': fov,
                    't': t
                }

                self.regions.add(region)
                self.channel_names.add(channel)
                max_z = max(max_z, z_level)
                max_fov = max(max_fov, fov)

        self.regions = sorted(self.regions)
        self.channel_names = sorted(self.channel_names)
        self.num_t = len(self.time_points)
        self.num_z = max_z + 1
        self.num_fovs_per_region = max_fov + 1
        
        # Set up image parameters based on the first image
        first_key = list(self.stitching_data.keys())[0]
        first_region = self.stitching_data[first_key]['region']
        first_fov = self.stitching_data[first_key]['fov_idx']
        first_z_level = self.stitching_data[first_key]['z_level']
        first_image = dask_imread(self.stitching_data[first_key]['filepath'])[0]

        self.dtype = first_image.dtype
        if len(first_image.shape) == 2:
            self.input_height, self.input_width = first_image.shape
        elif len(first_image.shape) == 3:
            self.input_height, self.input_width = first_image.shape[:2]
        else:
            raise ValueError(f"Unexpected image shape: {first_image.shape}")
        self.chunks = (1, 1, 1, 512, 512)
        
        # Set up final monochrome channels
        self.mono_channel_names = []
        for channel in self.channel_names:
            channel_key = (t, first_region, first_fov, first_z_level, channel)
            channel_image = dask_imread(self.stitching_data[channel_key]['filepath'])[0]
            if len(channel_image.shape) == 3 and channel_image.shape[2] == 3:
                self.is_rgb[channel] = True
                channel = channel.split('_')[0]
                self.mono_channel_names.extend([f"{channel}_R", f"{channel}_G", f"{channel}_B"])
            else:
                self.is_rgb[channel] = False
                self.mono_channel_names.append(channel)
        self.num_c = len(self.mono_channel_names)
        self.channel_colors = [self.get_channel_color(name) for name in self.mono_channel_names]

        print(f"FOV dimensions: {self.input_height}x{self.input_width}")
        print(f"{self.num_z} Z levels, {self.num_t} Time points")
        print(f"{self.num_c} Channels: {self.mono_channel_names}")
        print(f"{len(self.regions)} Regions: {self.regions}")

    def get_channel_color(self, channel_name):
        color_map = {
            '405': 0x0000FF,  # Blue
            '488': 0x00FF00,  # Green
            '561': 0xFFCF00,  # Yellow
            '638': 0xFF0000,  # Red
            '730': 0x770000,  # Dark Red"
            '_B': 0x0000FF,  # Blue
            '_G': 0x00FF00,  # Green
            '_R': 0xFF0000  # Red
        }
        for key in color_map:
            if key in channel_name:
                return color_map[key]
        return 0xFFFFFF  # Default to white if no match found

    def calculate_output_dimensions(self, region):
        region_data = [tile_info for key, tile_info in self.stitching_data.items() if key[1] == region]
        
        if not region_data:
            raise ValueError(f"No data found for region {region}")

        self.x_positions = sorted(set(tile_info['x'] for tile_info in region_data))
        self.y_positions = sorted(set(tile_info['y'] for tile_info in region_data))

        if self.use_registration: # Add extra space for shifts 
            num_cols = len(self.x_positions)
            num_rows = len(self.y_positions)

            if self.scan_pattern == 'S-Pattern':
                max_h_shift = (max(self.h_shift[0], self.h_shift_rev[0]), max(self.h_shift[1], self.h_shift_rev[1]))
            else:
                max_h_shift = self.h_shift

            width_pixels = int(self.input_width + ((num_cols - 1) * (self.input_width + max_h_shift[1]))) # horizontal width with overlap
            width_pixels += abs((num_rows - 1) * self.v_shift[1]) # horizontal shift from vertical registration
            height_pixels = int(self.input_height + ((num_rows - 1) * (self.input_height + self.v_shift[0]))) # vertical height with overlap
            height_pixels += abs((num_cols - 1) * max_h_shift[0]) # vertical shift from horizontal registration
 
        else: # Use coordinates shifts 
            width_mm = max(self.x_positions) - min(self.x_positions) + (self.input_width * self.pixel_size_um / 1000)
            height_mm = max(self.y_positions) - min(self.y_positions) + (self.input_height * self.pixel_size_um / 1000)

            width_pixels = int(np.ceil(width_mm * 1000 / self.pixel_size_um))
            height_pixels = int(np.ceil(height_mm * 1000 / self.pixel_size_um))

        # Round up to the next multiple of 4
        width_pixels = ((width_pixels + 3) & ~3) + 4
        height_pixels = ((height_pixels + 3) & ~3) + 4

        # Get the number of rows and columns
        if len(self.regions) > 1:
            rows, columns = self.get_rows_and_columns()
            max_dimension = max(len(rows), len(columns))
        else:
            max_dimension = 1

        # Calculate the number of pyramid levels
        self.num_pyramid_levels = math.ceil(np.log2(max(width_pixels, height_pixels) / 1024 * max_dimension))
        print("# Pyramid levels:", self.num_pyramid_levels)
        return width_pixels, height_pixels

    def init_output(self, region):
        width, height = self.calculate_output_dimensions(region)
        self.output_shape = (self.num_t, self.num_c, self.num_z, height, width)
        print(f"Output shape for region {region}: {self.output_shape}")
        return da.zeros(self.output_shape, dtype=self.dtype, chunks=self.chunks)

    def get_flatfields(self, progress_callback=None):
        def process_images(images, channel_name):
            if images.size == 0:
                print(f"WARNING: No images found for channel {channel_name}")
                return

            if images.ndim != 3 and images.ndim != 4:
                raise ValueError(f"Images must be 3 or 4-dimensional array, with dimension of (T, Y, X) or (T, Z, Y, X). Got shape {images.shape}")

            basic = BaSiC(get_darkfield=False, smoothness_flatfield=1)
            basic.fit(images)
            channel_index = self.mono_channel_names.index(channel_name)
            self.flatfields[channel_index] = basic.flatfield
            if progress_callback:
                progress_callback(channel_index + 1, self.num_c)

        for channel in self.channel_names:
            print(f"Calculating {channel} flatfield...")
            images = []
            for t in self.time_points:
                time_images = [dask_imread(tile['filepath'])[0] for key, tile in self.stitching_data.items() if tile['channel'] == channel and key[0] == int(t)]
                if not time_images:
                    print(f"WARNING: No images found for channel {channel} at timepoint {t}")
                    continue
                random.shuffle(time_images)
                selected_tiles = time_images[:min(32, len(time_images))]
                images.extend(selected_tiles)

            if not images:
                print(f"WARNING: No images found for channel {channel} across all timepoints")
                continue

            images = np.array(images)

            if images.ndim == 3:
                # Images are in the shape (N, Y, X)
                process_images(images, channel)
            elif images.ndim == 4:
                if images.shape[-1] == 3:
                    # Images are in the shape (N, Y, X, 3) for RGB images
                    images_r = images[..., 0]
                    images_g = images[..., 1]
                    images_b = images[..., 2]
                    channel = channel.split('_')[0]
                    process_images(images_r, channel + '_R')
                    process_images(images_g, channel + '_G')
                    process_images(images_b, channel + '_B')
                else:
                    # Images are in the shape (N, Z, Y, X)
                    process_images(images, channel)
            else:
                raise ValueError(f"Unexpected number of dimensions in images array: {images.ndim}")

    def calculate_shifts(self, region):
        region_data = [v for k, v in self.stitching_data.items() if k[1] == region]
        
        # Get unique x and y positions
        x_positions = sorted(set(tile['x'] for tile in region_data))
        y_positions = sorted(set(tile['y'] for tile in region_data))
        
        # Initialize shifts
        self.h_shift = (0, 0)
        self.v_shift = (0, 0)

        # Set registration channel if not already set
        if not self.registration_channel:
            self.registration_channel = self.channel_names[0]
        elif self.registration_channel not in self.channel_names:
            print(f"Warning: Specified registration channel '{self.registration_channel}' not found. Using {self.channel_names[0]}.")
            self.registration_channel = self.channel_names[0]


        max_x_overlap = round(self.input_width * self.overlap_percent / 2 / 100)
        max_y_overlap = round(self.input_height * self.overlap_percent / 2 / 100)
        print(f"Expected shifts - Horizontal: {(0, -max_x_overlap)}, Vertical: {(-max_y_overlap , 0)}")

        # Find center positions
        center_x_index = (len(x_positions) - 1) // 2
        center_y_index = (len(y_positions) - 1) // 2
        
        center_x = x_positions[center_x_index]
        center_y = y_positions[center_y_index]

        right_x = None
        bottom_y = None

        # Calculate horizontal shift
        if center_x_index + 1 < len(x_positions):
            right_x = x_positions[center_x_index + 1]
            center_tile = self.get_tile(region, center_x, center_y, self.registration_channel, self.registration_z_level)
            right_tile = self.get_tile(region, right_x, center_y, self.registration_channel, self.registration_z_level)
            
            if center_tile is not None and right_tile is not None:
                self.h_shift = self.calculate_horizontal_shift(center_tile, right_tile, max_x_overlap)
            else:
                print(f"Warning: Missing tiles for horizontal shift calculation in region {region}.")
        
        # Calculate vertical shift
        if center_y_index + 1 < len(y_positions):
            bottom_y = y_positions[center_y_index + 1]
            center_tile = self.get_tile(region, center_x, center_y, self.registration_channel, self.registration_z_level)
            bottom_tile = self.get_tile(region, center_x, bottom_y, self.registration_channel, self.registration_z_level)
            
            if center_tile is not None and bottom_tile is not None:
                self.v_shift = self.calculate_vertical_shift(center_tile, bottom_tile, max_y_overlap)
            else:
                print(f"Warning: Missing tiles for vertical shift calculation in region {region}.")

        if self.scan_pattern == 'S-Pattern' and right_x and bottom_y:
            center_tile = self.get_tile(region, center_x, bottom_y, self.registration_channel, self.registration_z_level)
            right_tile = self.get_tile(region, right_x, bottom_y, self.registration_channel, self.registration_z_level)

            if center_tile is not None and right_tile is not None:
                self.h_shift_rev = self.calculate_horizontal_shift(center_tile, right_tile, max_x_overlap)
                self.h_shift_rev_odd = center_y_index % 2 == 0
                print(f"Bi-Directional Horizontal Shift - Reverse Horizontal: {self.h_shift_rev}")
            else:
                print(f"Warning: Missing tiles for reverse horizontal shift calculation in region {region}.")

        print(f"Calculated Uni-Directional Shifts - Horizontal: {self.h_shift}, Vertical: {self.v_shift}")


    def calculate_horizontal_shift(self, img1, img2, max_overlap):
        img1 = self.normalize_image(img1)
        img2 = self.normalize_image(img2)

        margin = int(img1.shape[0] * 0.2)  # 20% margin
        img1_overlap = img1[margin:-margin, -max_overlap:]
        img2_overlap = img2[margin:-margin, :max_overlap]

        self.visualize_image(img1_overlap, img2_overlap, 'horizontal')

        shift, error, diffphase = phase_cross_correlation(img1_overlap, img2_overlap, upsample_factor=10)
        return round(shift[0]), round(shift[1] - img1_overlap.shape[1])

    def calculate_vertical_shift(self, img1, img2, max_overlap):
        img1 = self.normalize_image(img1)
        img2 = self.normalize_image(img2)

        margin = int(img1.shape[1] * 0.2)  # 20% margin
        img1_overlap = img1[-max_overlap:, margin:-margin]
        img2_overlap = img2[:max_overlap, margin:-margin]

        self.visualize_image(img1_overlap, img2_overlap, 'vertical')

        shift, error, diffphase = phase_cross_correlation(img1_overlap, img2_overlap, upsample_factor=10)
        return round(shift[0] - img1_overlap.shape[0]), round(shift[1])

    def get_tile(self, region, x, y, channel, z_level):
        for key, value in self.stitching_data.items():
            if (key[1] == region and 
                value['x'] == x and 
                value['y'] == y and 
                value['channel'] == channel and 
                value['z_level'] == z_level):
                try:
                    return dask_imread(value['filepath'])[0]
                except FileNotFoundError:
                    print(f"Warning: Tile file not found: {value['filepath']}")
                    return None
        print(f"Warning: No matching tile found for region {region}, x={x}, y={y}, channel={channel}, z={z_level}")
        return None

    def normalize_image(self, img):
        img_min, img_max = img.min(), img.max()
        img_normalized = (img - img_min) / (img_max - img_min)
        scale_factor = np.iinfo(self.dtype).max if np.issubdtype(self.dtype, np.integer) else 1
        return (img_normalized * scale_factor).astype(self.dtype)

    def visualize_image(self, img1, img2, title):
        try:
            # Ensure images are numpy arrays
            img1 = np.asarray(img1)
            img2 = np.asarray(img2)

            if title == 'horizontal':
                combined_image = np.hstack((img1, img2))
            else:
                combined_image = np.vstack((img1, img2))
            
            # Convert to uint8 for saving as PNG
            combined_image_uint8 = (combined_image / np.iinfo(self.dtype).max * 255).astype(np.uint8)
            
            cv2.imwrite(f"{self.input_folder}/{title}.png", combined_image_uint8)
            
            print(f"Saved {title}.png successfully")
        except Exception as e:
            print(f"Error in visualize_image: {e}")

    def stitch_and_save_region(self, region, progress_callback=None):
        stitched_images = self.init_output(region)  # sets self.x_positions, self.y_positions
        region_data = {k: v for k, v in self.stitching_data.items() if k[1] == region}
        total_tiles = len(region_data)
        processed_tiles = 0

        x_min = min(self.x_positions)
        y_min = min(self.y_positions)

        for key, tile_info in region_data.items():
            t, _, fov, z_level, channel = key
            tile = dask_imread(tile_info['filepath'])[0]
            if self.use_registration:
                self.col_index = self.x_positions.index(tile_info['x'])
                self.row_index = self.y_positions.index(tile_info['y'])

                if self.scan_pattern == 'S-Pattern' and self.row_index % 2 == self.h_shift_rev_odd:
                    h_shift = self.h_shift_rev
                else:
                    h_shift = self.h_shift

                # Initialize starting coordinates based on tile position and shift
                x_pixel = int(self.col_index * (self.input_width + h_shift[1]))
                y_pixel = int(self.row_index * (self.input_height + self.v_shift[0]))

                # Apply horizontal shift effect on y-coordinate
                if h_shift[0] < 0:
                    y_pixel += int((len(self.x_positions) - 1 - self.col_index) * abs(h_shift[0]))  # Fov moves up as cols go right
                else:
                    y_pixel += int(self.col_index * h_shift[0])  # Fov moves down as cols go right

                # Apply vertical shift effect on x-coordinate
                if self.v_shift[1] < 0:
                    x_pixel += int((len(self.y_positions) - 1 - self.row_index) * abs(self.v_shift[1]))  # Fov moves left as rows go down
                else:
                    x_pixel += int(self.row_index * self.v_shift[1])   # Fov moves right as rows go down

            else:
                # Calculate base position
                x_pixel = int((tile_info['x'] - x_min) * 1000 / self.pixel_size_um)
                y_pixel = int((tile_info['y'] - y_min) * 1000 / self.pixel_size_um)

            self.place_tile(stitched_images, tile, x_pixel, y_pixel, z_level, channel, t)

            processed_tiles += 1
            if progress_callback:
                progress_callback(processed_tiles, total_tiles)

        self.starting_saving.emit(False)
        if len(self.regions) > 1:
            self.save_region_to_hcs_ome_zarr(region, stitched_images)
        else:
            # self.save_as_ome_zarr(region, stitched_images)
            self.save_region_to_ome_zarr(region, stitched_images) # bugs: when starting to save, main gui lags and disconnects

    def place_tile(self, stitched_images, tile, x_pixel, y_pixel, z_level, channel, t):
        if len(tile.shape) == 2:
            # Handle 2D grayscale image
            channel_idx = self.mono_channel_names.index(channel)
            self.place_single_channel_tile(stitched_images, tile, x_pixel, y_pixel, z_level, channel_idx, t)

        elif len(tile.shape) == 3:
            if tile.shape[2] == 3:
                # Handle RGB image
                channel = channel.split('_')[0]
                for i, color in enumerate(['R', 'G', 'B']):
                    channel_idx = self.mono_channel_names.index(f"{channel}_{color}")
                    self.place_single_channel_tile(stitched_images, tile[:,:,i], x_pixel, y_pixel, z_level, channel_idx, t)
            elif tile.shape[0] == 1:
                channel_idx = self.mono_channel_names.index(channel)
                self.place_single_channel_tile(stitched_images, tile[0], x_pixel, y_pixel, z_level, channel_idx, t)
        else:
            raise ValueError(f"Unexpected tile shape: {tile.shape}")

    def place_single_channel_tile(self, stitched_images, tile, x_pixel, y_pixel, z_level, channel_idx, t):
        if len(stitched_images.shape) != 5:
            raise ValueError(f"Unexpected stitched_images shape: {stitched_images.shape}. Expected 5D array (t, c, z, y, x).")

        if self.apply_flatfield:
            tile = self.apply_flatfield_correction(tile, channel_idx)

        if self.use_registration:
            if self.scan_pattern == 'S-Pattern' and self.row_index % 2 == self.h_shift_rev_odd:
                h_shift = self.h_shift_rev
            else:
                h_shift = self.h_shift

            # Determine crop for tile edges
            top_crop = max(0, (-self.v_shift[0] // 2) - abs(h_shift[0]) // 2) if self.row_index > 0 else 0 # if y
            bottom_crop = max(0, (-self.v_shift[0] // 2) - abs(h_shift[0]) // 2) if self.row_index < len(self.y_positions) - 1 else 0
            left_crop = max(0, (-h_shift[1] // 2) - abs(self.v_shift[1]) // 2) if self.col_index > 0 else 0
            right_crop = max(0, (-h_shift[1] // 2) - abs(self.v_shift[1]) // 2) if self.col_index < len(self.x_positions) - 1 else 0

            # Apply cropping to the tile
            tile = tile[top_crop:tile.shape[0]-bottom_crop, left_crop:tile.shape[1]-right_crop]

            # Adjust x_pixel and y_pixel based on cropping
            x_pixel += left_crop
            y_pixel += top_crop
        
        y_end = min(y_pixel + tile.shape[0], stitched_images.shape[3])
        x_end = min(x_pixel + tile.shape[1], stitched_images.shape[4])
        
        try:
            stitched_images[t, channel_idx, z_level, y_pixel:y_end, x_pixel:x_end] = tile[:y_end-y_pixel, :x_end-x_pixel]
        except Exception as e:
            print(f"ERROR: Failed to place tile. Details: {str(e)}")
            print(f"DEBUG: t:{t}, channel_idx:{channel_idx}, z_level:{z_level}, y:{y_pixel}-{y_end}, x:{x_pixel}-{x_end}")
            print(f"DEBUG: tile slice shape: {tile[:y_end-y_pixel, :x_end-x_pixel].shape}")
            raise

    def apply_flatfield_correction(self, tile, channel_idx):
        if channel_idx in self.flatfields:
            return (tile / self.flatfields[channel_idx]).clip(min=np.iinfo(self.dtype).min,
                                                              max=np.iinfo(self.dtype).max).astype(self.dtype)
        return tile

    def generate_pyramid(self, image, num_levels):
        pyramid = [image]
        for level in range(1, num_levels):
            scale_factor = 2 ** level
            factors = {0: 1, 1: 1, 2: 1, 3: scale_factor, 4: scale_factor}
            if isinstance(image, da.Array):
                downsampled = da.coarsen(np.mean, image, factors, trim_excess=True)
            else:
                block_size = (1, 1, 1, scale_factor, scale_factor)
                downsampled = downscale_local_mean(image, block_size)
            pyramid.append(downsampled)
        return pyramid

    def save_region_to_hcs_ome_zarr(self, region, stitched_images):
        output_path = os.path.join(self.input_folder, self.output_name)
        store = ome_zarr.io.parse_url(output_path, mode="a").store
        root = zarr.group(store=store)

        row, col = region[0], region[1:]
        row_group = root.require_group(row)
        well_group = row_group.require_group(col)

        if 'well' not in well_group.attrs:
            well_metadata = {
                "images": [{"path": "0", "acquisition": 0}],
            }
            ome_zarr.writer.write_well_metadata(well_group, well_metadata["images"])

        image_group = well_group.require_group("0")
        
        pyramid = self.generate_pyramid(stitched_images, self.num_pyramid_levels)
        coordinate_transformations = [
            [{
                "type": "scale",
                "scale": [1, 1, self.acquisition_params.get("dz(um)", 1), self.pixel_size_um * (2 ** i), self.pixel_size_um * (2 ** i)]
            }] for i in range(self.num_pyramid_levels)
        ]

        axes = [
            {"name": "t", "type": "time", "unit": "second"},
            {"name": "c", "type": "channel"},
            {"name": "z", "type": "space", "unit": "micrometer"},
            {"name": "y", "type": "space", "unit": "micrometer"},
            {"name": "x", "type": "space", "unit": "micrometer"}
        ]

        # Prepare channels metadata
        omero_channels = [{
            "label": name,
            "color": f"{color:06X}",
            "window": {"start": 0, "end": np.iinfo(self.dtype).max, "min": 0, "max": np.iinfo(self.dtype).max}
        } for name, color in zip(self.mono_channel_names, self.channel_colors)]

        omero = {
            "name": f"{region}",
            "version": "0.4",
            "channels": omero_channels
        }

        image_group.attrs["omero"] = omero

        # Write the multiscale image data and metadata
        ome_zarr.writer.write_multiscale(
            pyramid=pyramid,
            group=image_group,
            chunks=self.chunks,
            axes=axes,
            coordinate_transformations=coordinate_transformations,
            storage_options=dict(chunks=self.chunks),
            name=f"{region}"
        )

    def save_as_ome_zarr(self, region, stitched_images):
        output_path = os.path.join(self.input_folder, self.output_name)
        dz_um = self.acquisition_params.get("dz(um)", None)
        sensor_pixel_size_um = self.acquisition_params.get("sensor_pixel_size_um", None)
        channel_minmax = [(np.iinfo(self.dtype).min, np.iinfo(self.dtype).max)] * self.num_c
        for i in range(self.num_c):
            print(f"Channel {i}:", self.mono_channel_names[i], " \tColor:", self.channel_colors[i], " \tPixel Range:", channel_minmax[i])

        zarr_writer = OmeZarrWriter(output_path)
        zarr_writer.build_ome(
            size_z=self.num_z,
            image_name=region,
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            channel_minmax=channel_minmax
        )
        zarr_writer.write_image(
            image_data=stitched_images,
            image_name=region,
            physical_pixel_sizes=types.PhysicalPixelSizes(dz_um, self.pixel_size_um, self.pixel_size_um),
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            dimension_order="TCZYX",
            scale_num_levels=self.num_pyramid_levels,
            chunk_dims=self.chunks
        )

    def save_region_to_ome_zarr(self, region, stitched_images):
        output_path = os.path.join(self.input_folder, self.output_name)
        store = ome_zarr.io.parse_url(output_path, mode="a").store
        root = zarr.group(store=store)

        # Generate the pyramid
        pyramid = self.generate_pyramid(stitched_images, self.num_pyramid_levels)

        datasets = []
        for i in range(self.num_pyramid_levels):
            scale = 2**i
            datasets.append({
                "path": str(i),
                "coordinateTransformations": [{
                    "type": "scale",
                    "scale": [1, 1, self.acquisition_params.get("dz(um)", 1), self.pixel_size_um * scale, self.pixel_size_um * scale]
                }]
            })

        axes = [
            {"name": "t", "type": "time", "unit": "second"},
            {"name": "c", "type": "channel"},
            {"name": "z", "type": "space", "unit": "micrometer"},
            {"name": "y", "type": "space", "unit": "micrometer"},
            {"name": "x", "type": "space", "unit": "micrometer"}
        ]

        ome_zarr.writer.write_multiscales_metadata(root, datasets, axes=axes, name="stitched_image")

        omero = {
            "name": "stitched_image",
            "version": "0.4",
            "channels": [{
                "label": name,
                "color": f"{color:06X}",
                "window": {"start": 0, "end": np.iinfo(self.dtype).max, "min": 0, "max": np.iinfo(self.dtype).max}
            } for name, color in zip(self.mono_channel_names, self.channel_colors)]
        }
        root.attrs["omero"] = omero

        coordinate_transformations = [
            dataset["coordinateTransformations"] for dataset in datasets
        ]

        ome_zarr.writer.write_multiscale(
            pyramid=pyramid,
            group=root,
            axes="tczyx",
            coordinate_transformations=coordinate_transformations,
            storage_options=dict(chunks=self.chunks)
        )

    def write_stitched_plate_metadata(self):
        output_path = os.path.join(self.input_folder, self.output_name)
        store = ome_zarr.io.parse_url(output_path, mode="a").store
        root = zarr.group(store=store)

        rows, columns = self.get_rows_and_columns()
        well_paths = [f"{well_id[0]}/{well_id[1:]}" for well_id in sorted(self.regions)]
        
        plate_metadata = {
            "name": "Stitched Plate",
            "rows": [{"name": row} for row in rows],
            "columns": [{"name": col} for col in columns],
            "wells": [{"path": path, "rowIndex": rows.index(path[0]), "columnIndex": columns.index(path[2:])} 
                      for path in well_paths],
            "field_count": 1,
            "acquisitions": [{
                "id": 0,
                "maximumfieldcount": 1,
                "name": "Stitched Acquisition"
            }]
        }
        
        ome_zarr.writer.write_plate_metadata(
            root,
            rows=[row["name"] for row in plate_metadata["rows"]],
            columns=[col["name"] for col in plate_metadata["columns"]],
            wells=plate_metadata["wells"],
            acquisitions=plate_metadata["acquisitions"],
            name=plate_metadata["name"],
            field_count=plate_metadata["field_count"]
        )

    def get_rows_and_columns(self):
        rows = sorted(set(region[0] for region in self.regions))
        columns = sorted(set(region[1:] for region in self.regions))
        return rows, columns

    def create_ome_tiff(self, stitched_images):
        output_path = os.path.join(self.input_folder, self.output_name)
        
        with TiffWriter(output_path, bigtiff=True, ome=True) as tif:
            tif.write(
                data=stitched_images,
                shape=stitched_images.shape,
                dtype=self.dtype,
                photometric='minisblack',
                planarconfig='separate',
                metadata={
                    'axes': 'TCZYX',
                    'Channel': {'Name': self.mono_channel_names},
                    'SignificantBits': stitched_images.dtype.itemsize * 8,
                    'Pixels': {
                        'PhysicalSizeX': self.pixel_size_um,
                        'PhysicalSizeXUnit': 'µm',
                        'PhysicalSizeY': self.pixel_size_um,
                        'PhysicalSizeYUnit': 'µm',
                        'PhysicalSizeZ': self.acquisition_params.get("dz(um)", 1.0),
                        'PhysicalSizeZUnit': 'µm',
                    },
                }
            )
        
        print(f"Data saved in OME-TIFF format at: {output_path}")
        self.finished_saving.emit(output_path, self.dtype)


    def run(self):
        stime = time.time()
        # try:
        self.get_time_points()
        self.parse_filenames()

        if self.apply_flatfield:
            print("Calculating flatfields...")
            self.getting_flatfields.emit()
            self.get_flatfields(progress_callback=self.update_progress.emit)
            print("time to apply flatfields", time.time() - stime)

        if self.num_fovs_per_region > 1:
            self.run_regions()
        else:
            self.run_fovs() # only displays one fov per region even though all fovs are saved in zarr with metadata

        # except Exception as e:
        #     print("time before error", time.time() - stime)
        #     print(f"Error while stitching: {e}")
        #     raise


    def run_regions(self):
        stime = time.time()
        if len(self.regions) > 1:
            self.write_stitched_plate_metadata()

        if self.use_registration:
            print(f"\nCalculating shifts for region {self.regions[0]}...")
            self.calculate_shifts(self.regions[0])

        for region in self.regions:
            wtime = time.time()

            # if self.use_registration:
            #     print(f"\nCalculating shifts for region {region}...")
            #     self.calculate_shifts(region)

            self.starting_stitching.emit()
            print(f"\nstarting stitching for region {region}...")
            self.stitch_and_save_region(region, progress_callback=self.update_progress.emit)

            sttime = time.time()
            print(f"time to stitch and save region {region}", time.time() - wtime)
            print(f"...done with region:{region}")

        if self.output_format.endswith('.ome.tiff'):
            self.create_ome_tiff(self.stitched_images)
        else:
            output_path = os.path.join(self.input_folder, self.output_name)
            print(f"Data saved in OME-ZARR format at: {output_path}")
            self.print_zarr_structure(output_path)

        self.finished_saving.emit(os.path.join(self.input_folder, self.output_name), self.dtype)
        print("total time to stitch + save:", time.time() - stime)


#________________________________________________________________________________________________________________________________
# run_fovs: directly save fovs to final hcs ome zarr 
# 
# issue:
# only shows one fov per region when there are multiple fovs 
#   - (fix metadata? translation, scale, path, multiscale?)
# correct channels in napari, well + plate metadata, z-stack shape, time-point shape

    def run_fovs(self):
        stime = time.time()
        self.starting_stitching.emit()

        output_path = os.path.join(self.input_folder, self.output_name)
        store = ome_zarr.io.parse_url(output_path, mode="a").store
        root = zarr.group(store=store)

        self.write_fov_plate_metadata(root)

        total_fovs = sum(len(set([k[2] for k in self.stitching_data.keys() if k[1] == region])) for region in self.regions)
        processed_fovs = 0

        for region in self.regions:
            region_data = {k: v for k, v in self.stitching_data.items() if k[1] == region}
            well_group = self.write_fov_well_metadata(root, region)

            for fov_idx in range(self.num_fovs_per_region):
                fov_data = {k: v for k, v in region_data.items() if k[2] == fov_idx}
                
                if not fov_data:
                    continue  # Skip if no data for this FOV index

                tcz_fov = self.compile_single_fov_data(fov_data)
                self.write_fov_to_zarr(well_group, tcz_fov, fov_idx, fov_data)
                processed_fovs += 1
                self.update_progress.emit(processed_fovs, total_fovs)

        omero_channels = [{
            "label": name,
            "color": f"{color:06X}",
            "window": {"start": 0, "end": np.iinfo(self.dtype).max, "min": 0, "max": np.iinfo(self.dtype).max}
        } for name, color in zip(self.mono_channel_names, self.channel_colors)]

        omero = {
            "name": "hcs-acquisition",
            "version": "0.4",
            "channels": omero_channels
        }

        root.attrs["omero"] = omero

        print(f"Data saved in OME-ZARR format at: {output_path}")
        self.print_zarr_structure(output_path)
        self.finished_saving.emit(output_path, self.dtype)

        print("total time to save FOVs:", time.time() - stime)

    def compile_single_fov_data(self, fov_data):
        # Initialize a 5D array to hold all the data for this FOV
        tcz_fov = np.zeros((self.num_t, self.num_c, self.num_z, self.input_height, self.input_width), dtype=self.dtype)

        for key, scan_info in fov_data.items():
            t, _, _, z_level, channel = key
            image = dask_imread(scan_info['filepath'])[0]
            
            if self.apply_flatfield:
                channel_idx = self.mono_channel_names.index(channel)
                image = self.apply_flatfield_correction(image, channel_idx)

            if len(image.shape) == 3 and image.shape[2] == 3:  # RGB image
                channel = channel.split('_')[0]
                for i, color in enumerate(['R', 'G', 'B']):
                    c_idx = self.mono_channel_names.index(f"{channel}_{color}")
                    tcz_fov[t, c_idx, z_level] = image[:, :, i]
            else:  # Grayscale image
                c_idx = self.mono_channel_names.index(channel)
                tcz_fov[t, c_idx, z_level] = image

        return da.from_array(tcz_fov, chunks=self.chunks)

    def write_fov_plate_metadata(self, root):
        rows, columns = self.get_rows_and_columns()
        well_paths = [f"{well_id[0]}/{well_id[1:]}" for well_id in sorted(self.regions)]
        
        plate_metadata = {
            "name": "Sample",
            "rows": [{"name": row} for row in rows],
            "columns": [{"name": col} for col in columns],
            "wells": [{"path": path, "rowIndex": rows.index(path[0]), "columnIndex": columns.index(path[2:])} 
                      for path in well_paths],
            "field_count": self.num_fovs_per_region * len(self.regions),
            "acquisitions": [{
                "id": 0,
                "maximumfieldcount": self.num_fovs_per_region,
                "name": "Multipoint Acquisition"
            }]
        }
        
        ome_zarr.writer.write_plate_metadata(
            root,
            rows=[row["name"] for row in plate_metadata["rows"]],
            columns=[col["name"] for col in plate_metadata["columns"]],
            wells=plate_metadata["wells"],
            acquisitions=plate_metadata["acquisitions"],
            name=plate_metadata["name"],
            field_count=plate_metadata["field_count"]
        )

    def write_fov_well_metadata(self, root, region):
        row, col = region[0], region[1:]
        row_group = root.require_group(row)
        well_group = row_group.require_group(col)

        if 'well' not in well_group.attrs:
            well_metadata = {
                "images": [{"path": str(fov_idx), "acquisition": 0} for fov_idx in range(self.num_fovs_per_region)]
            }
            ome_zarr.writer.write_well_metadata(well_group, well_metadata["images"])
        return well_group

    def write_fov_to_zarr(self, well_group, tcz_fov, fov_idx, fov_data):
        axes = [
            {"name": "t", "type": "time", "unit": "second"},
            {"name": "c", "type": "channel"},
            {"name": "z", "type": "space", "unit": "micrometer"},
            {"name": "y", "type": "space", "unit": "micrometer"},
            {"name": "x", "type": "space", "unit": "micrometer"}
        ]

        # Generate pyramid levels
        pyramid = self.generate_pyramid(tcz_fov, self.num_pyramid_levels)

        # Get the position of the FOV (use the first scan in fov_data)
        first_scan = next(iter(fov_data.values()))
        x_mm, y_mm = first_scan['x'], first_scan['y']
        
        # Get the z positions
        z_positions = sorted(set(scan_info['z'] for scan_info in fov_data.values()))
        z_min = min(z_positions)
        dz = self.acquisition_params.get("dz(um)", 1.0)
        
        # Create coordinate transformations for each pyramid level
        coordinate_transformations = []
        for level in range(len(pyramid)):
            scale_factor = 2 ** level
            coordinate_transformations.append([
                {
                    "type": "scale",
                    "scale": [1, 1, dz, self.pixel_size_um * scale_factor, self.pixel_size_um * scale_factor]
                },
                {
                    "type": "translation",
                    "translation": [0, 0, z_min, y_mm*1000, x_mm*1000]
                }
            ])

        image_group = well_group.require_group(str(fov_idx))

        # Prepare datasets for multiscales metadata
        datasets = [
            {
                "path": str(i),
                "coordinateTransformations": coord_trans
            } for i, coord_trans in enumerate(coordinate_transformations)
        ]

        # Write multiscales metadata
        ome_zarr.writer.write_multiscales_metadata(
            group=image_group,
            datasets=datasets,
            axes=axes,
            name=f"FOV_{fov_idx}"  # This will be passed as part of **metadata
        )

        # Write the actual data
        ome_zarr.writer.write_multiscale(
            pyramid=pyramid,
            group=image_group,
            axes=axes,
            coordinate_transformations=coordinate_transformations,
            storage_options=dict(chunks=self.chunks),
        )

        # Add OMERO metadata
        omero_channels = [{
            "label": name,
            "color": f"{color:06X}",
            "window": {"start": 0, "end": np.iinfo(self.dtype).max, "min": 0, "max": np.iinfo(self.dtype).max}
        } for name, color in zip(self.mono_channel_names, self.channel_colors)]

        omero = {
            "name": f"FOV_{fov_idx}",
            "version": "0.4",
            "channels": omero_channels
        }

        image_group.attrs["omero"] = omero

    def print_zarr_structure(self, path, indent=""):
        root = zarr.open(path, mode='r')
        print(f"Zarr Tree and Metadata for: {path}")
        print(root.tree())
        print(dict(root.attrs))