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
from lxml import etree
import numpy as np
import pandas as pd
import cv2
import dask.array as da
from dask_image.imread import imread as dask_imread
from skimage.registration import phase_cross_correlation
import ome_zarr
import zarr
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

    def __init__(self, input_folder, output_name='', output_format=".ome.zarr", apply_flatfield=0, use_registration=0, registration_channel='', registration_z_level=0):
        QThread.__init__(self)
        QObject.__init__(self)
        self.input_folder = input_folder
        self.image_folder = None
        self.output_name = output_name + output_format
        self.apply_flatfield = apply_flatfield
        self.use_registration = use_registration
        if use_registration:
            self.registration_channel = registration_channel

        self.selected_modes = self.extract_selected_modes(self.input_folder)
        self.acquisition_params = self.extract_acquisition_parameters(self.input_folder)
        self.time_points = self.get_time_points(self.input_folder)
        print("timepoints:", self.time_points)
        self.is_reversed = self.determine_directions(self.input_folder) # init: top to bottom, left to right
        print(self.is_reversed)
        self.is_wellplate = IS_HCS
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
        self.num_pyramid_levels = 1
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
                self.chunks = (1, 1, 1, self.input_height, self.input_width)
                found_dims = True
                print("chunks", self.chunks)

            if len(image.shape) == 3:
                self.is_rgb[channel] = True
                mono_channel_names.extend([f"{channel} R", f"{channel} G", f"{channel} B"])
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
                process_images(images_r, channel + ' R')
                process_images(images_g, channel + ' G')
                process_images(images_b, channel + ' B')
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

    def calculate_shifts(self, roi="", z_level=0):
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
        pixel_size_um = sensor_pixel_size_um / actual_mag
        print("pixel_size_um:", pixel_size_um)

        dx_pixels = dx_mm * 1000 / pixel_size_um
        dy_pixels = dy_mm * 1000 / pixel_size_um
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
        for (row, col), tile_info in self.stitching_data[roi][self.registration_channel][z_level].items():
            if col == col_left and row == row_top:
                img1_path = tile_info['filepath']
            elif col == col_left and row == row_bottom:
                img2_path_vertical = tile_info['filepath']
            elif col == col_right and row == row_top:
                img2_path_horizontal = tile_info['filepath']

        if img1_path is None:
            raise Exception(
                f"No input file found for c:{self.registration_channel} k:{z_level} "
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
        while size > 2000:
            size //= 2
            num_levels += 1
        self.num_pyramid_levels = num_levels
        print("num_pyramid_levels:", self.num_pyramid_levels)
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

                    if self.use_registration and DYNAMIC_REGISTRATION and z_level == 0:
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
                                    color_channel = f"{channel} {color}"
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
            physical_pixel_sizes=[types.PhysicalPixelSizes(dz_um, sensor_pixel_size_um, sensor_pixel_size_um)],
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
            physical_pixel_sizes=types.PhysicalPixelSizes(dz_um, sensor_pixel_size_um, sensor_pixel_size_um),
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            dimension_order=dims,
            scale_num_levels=self.num_pyramid_levels,
            chunk_dims=self.chunks
        )
        # # Print metadata after writing
        # print("ome-zarr metadata...")
        # zarr_root = zarr.open(self.output_path, mode='r')

        # print("root attributes:")
        # print(dict(zarr_root.attrs))
        # print("zarr structure:")
        # print(zarr_root.tree())
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

            if STITCH_COMPLETE_ACQUISITION and ".ome.zarr" in self.output_name:
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

    def __init__(self, input_folder, output_name='', output_format=".ome.zarr", apply_flatfield=0, use_registration=0):
        super().__init__()
        self.input_folder = input_folder
        self.output_name = output_name + output_format
        self.apply_flatfield = apply_flatfield
        self.use_registration = use_registration

        self.coordinates_df = None
        self.pixel_size_um = None
        self.acquisition_params = None
        self.time_points = []
        self.regions = []
        self.init_stitching_parameters()

    def init_stitching_parameters(self):
        self.is_rgb = {}
        self.channel_names = []
        self.mono_channel_names = []
        self.channel_colors = []
        self.num_z = self.num_c = 1
        self.input_height = self.input_width = 0
        self.num_pyramid_levels = 1
        self.flatfields = {}
        self.stitching_data = {}
        self.dtype = np.uint16
        self.chunks = None

    def get_time_points(self):
        try:
            time_points = [d for d in os.listdir(self.input_folder) if os.path.isdir(os.path.join(self.input_folder, d)) and d.isdigit()]
            time_points.sort(key=int)
            return time_points
        except Exception as e:
            print(f"Error detecting time points: {e}")
            return ['0']

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

    def parse_filenames(self, time_point):
        self.extract_acquisition_parameters()
        self.get_pixel_size_from_params()

        coordinates_path = os.path.join(self.input_folder, time_point, 'coordinates.csv')
        self.coordinates_df = pd.read_csv(coordinates_path)

        self.regions = sorted(self.coordinates_df['region'].unique())

        image_folder = os.path.join(self.input_folder, time_point)
        image_files = [f for f in os.listdir(image_folder) if f.endswith(('.bmp', '.tiff')) and 'focus_camera' not in f]

        for file in image_files:
            parts = file.split('_', 3)

            region, i, z_level, channel = parts[0], int(parts[1]), int(parts[2]), os.path.splitext(parts[3])[0]

            # Look up the corresponding row in the coordinates DataFrame
            coord_row = self.coordinates_df[(self.coordinates_df['region'] == region) & (self.coordinates_df['i'] == i) & (self.coordinates_df['z_level'] == z_level)]

            if coord_row.empty:
                print(f"Warning: No matching coordinates found for file {file}")
                continue

            coord_row = coord_row.iloc[0]  # Get the first (and should be only) matching row

            self.stitching_data[len(self.stitching_data)] = {
                'filepath': os.path.join(image_folder, file),
                'x': coord_row['x (mm)'],
                'y': coord_row['y (mm)'],
                'z': coord_row['z (um)'],
                'channel': channel,
                'z_level': z_level,
                'region': region,
                'fov_index': i
            }

            if channel not in self.channel_names:
                self.channel_names.append(channel)

        self.setup_image_parameters()

    def setup_image_parameters(self):
        first_image = list(self.stitching_data.values())[0]
        image = dask_imread(first_image['filepath'])[0]

        self.dtype = image.dtype
        self.input_height, self.input_width = image.shape[:2]
        self.chunks = (1, 1, 1, self.input_height, self.input_width)

        self.num_z = self.coordinates_df['z_level'].max() + 1

        for channel in self.channel_names:
            if len(image.shape) == 3:
                self.is_rgb[channel] = True
                self.mono_channel_names.extend([f"{channel} R", f"{channel} G", f"{channel} B"])
            else:
                self.is_rgb[channel] = False
                self.mono_channel_names.append(channel)

        self.num_c = len(self.mono_channel_names)
        self.channel_colors = [self.get_channel_color(name) for name in self.mono_channel_names]

    def get_channel_color(self, channel_name):
        color_map = {
            'BF': 0xFFFFFF,  # White
            'Fluorescence_405': 0x0000FF,  # Blue
            'Fluorescence_488': 0x00FF00,  # Green
            'Fluorescence_561': 0xFF0000,  # Red
            'Fluorescence_638': 0xFF00FF,  # Magenta
        }

        for key in color_map:
            if key in channel_name:
                return color_map[key]

        return 0xFFFFFF  # Default to white if no match found

    def calculate_output_dimensions(self, region):
        region_df = self.coordinates_df[self.coordinates_df['region'] == region]
        x_min = region_df['x (mm)'].min()
        x_max = region_df['x (mm)'].max()
        y_min = region_df['y (mm)'].min()
        y_max = region_df['y (mm)'].max()

        width_mm = x_max - x_min + (self.input_width * self.pixel_size_um / 1000)
        height_mm = y_max - y_min + (self.input_height * self.pixel_size_um / 1000)

        width_pixels = int(np.ceil(width_mm * 1000 / self.pixel_size_um))
        height_pixels = int(np.ceil(height_mm * 1000 / self.pixel_size_um))

        return width_pixels, height_pixels

    def init_output(self, region):
        width, height = self.calculate_output_dimensions(region)
        self.output_shape = (1, self.num_c, self.num_z, height, width)
        return da.zeros(self.output_shape, dtype=self.dtype, chunks=self.chunks)

    def get_flatfields(self, progress_callback=None):
        def process_images(images, channel_name):
            images = np.array(images)
            basic = BaSiC(get_darkfield=False, smoothness_flatfield=1)
            basic.fit(images)
            channel_index = self.mono_channel_names.index(channel_name)
            self.flatfields[channel_index] = basic.flatfield
            if progress_callback:
                progress_callback(channel_index + 1, self.num_c)

        for channel in self.channel_names:
            all_tiles = [tile_info for tile_info in self.stitching_data.values() if tile_info['channel'] == channel]
            random.shuffle(all_tiles)
            selected_tiles = all_tiles[:min(32, len(all_tiles))]

            if self.is_rgb[channel]:
                images_r = [dask_imread(tile['filepath'])[0][:, :, 0] for tile in selected_tiles]
                images_g = [dask_imread(tile['filepath'])[0][:, :, 1] for tile in selected_tiles]
                images_b = [dask_imread(tile['filepath'])[0][:, :, 2] for tile in selected_tiles]
                process_images(images_r, channel + ' R')
                process_images(images_g, channel + ' G')
                process_images(images_b, channel + ' B')
            else:
                images = [dask_imread(tile['filepath'])[0] for tile in selected_tiles]
                process_images(images, channel)

    def stitch_images(self, time_point, region, progress_callback=None):
        self.stitched_images = self.init_output(region)
        region_data = {k: v for k, v in self.stitching_data.items() if v['region'] == region}
        total_tiles = len(region_data)
        processed_tiles = 0

        region_df = self.coordinates_df[self.coordinates_df['region'] == region]
        x_min = region_df['x (mm)'].min()
        y_min = region_df['y (mm)'].min()

        for idx, tile_info in region_data.items():
            tile = dask_imread(tile_info['filepath'])[0]

            x_pixel = int((tile_info['x'] - x_min) * 1000 / self.pixel_size_um)
            y_pixel = int((tile_info['y'] - y_min) * 1000 / self.pixel_size_um)

            self.place_tile(tile, x_pixel, y_pixel, int(tile_info['z_level']), tile_info['channel'])

            processed_tiles += 1
            if progress_callback:
                progress_callback(processed_tiles, total_tiles)

    def place_tile(self, tile, x, y, z_level, channel):
        if self.is_rgb[channel]:
            for i, color in enumerate(['R', 'G', 'B']):
                channel_idx = self.mono_channel_names.index(f"{channel} {color}")
                self.place_single_channel_tile(tile[:,:,i], x, y, z_level, channel_idx)
        else:
            channel_idx = self.mono_channel_names.index(channel)
            self.place_single_channel_tile(tile, x, y, z_level, channel_idx)

    def place_single_channel_tile(self, tile, x, y, z_level, channel_idx):
        y_end = min(y + tile.shape[0], self.output_shape[3])
        x_end = min(x + tile.shape[1], self.output_shape[4])

        if self.apply_flatfield:
            tile = self.apply_flatfield_correction(tile, channel_idx)

        self.stitched_images[0, channel_idx, z_level, y:y_end, x:x_end] = tile[:y_end-y, :x_end-x]

    def apply_flatfield_correction(self, tile, channel_idx):
        if channel_idx in self.flatfields:
            return (tile / self.flatfields[channel_idx]).clip(min=np.iinfo(self.dtype).min,
                                                              max=np.iinfo(self.dtype).max).astype(self.dtype)
        return tile

    def save_as_ome_zarr(self, time_point, region):
        output_folder = os.path.join(self.input_folder, f"{time_point}_stitched")
        os.makedirs(output_folder, exist_ok=True)
        output_path = os.path.join(output_folder, f"{region}_{self.output_name}")
        image_name = f"{region}_t{time_point}"

        zarr_writer = OmeZarrWriter(output_path)
        zarr_writer.write_image(
            image_name=image_name,
            image_data=self.stitched_images,
            dimension_order="TCZYX",
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            physical_pixel_sizes=types.PhysicalPixelSizes(self.acquisition_params.get("dz(um)", 1.0), self.pixel_size_um, self.pixel_size_um),
            scale_num_levels=self.num_pyramid_levels,
            chunk_dims=self.chunks
        )

    def create_complete_ome_zarr(self):
        """ Creates a complete OME-ZARR with proper channel metadata. """
        final_path = os.path.join(self.input_folder, self.output_name.replace(".ome.zarr","") + "_complete_acquisition.ome.zarr")
        if len(self.time_points) == 1:
            zarr_path = os.path.join(self.input_folder, f"0_stitched", self.output_name)
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
        self.finished_saving.emit(final_path, self.dtype)

    def create_hcs_ome_zarr(self):
        """Creates a hierarchical Zarr file in the HCS OME-ZARR format for visualization in napari."""
        hcs_path = os.path.join(self.input_folder, self.output_name.replace(".ome.zarr","") + "_complete_acquisition.ome.zarr")
        if len(self.time_points) == 1 and len(self.regions) == 1:
            stitched_zarr_path = os.path.join(self.input_folder, f"0_stitched", f"{self.regions[0]}_{self.output_name}")
            shutil.copytree(stitched_zarr_path, hcs_path)
        else:
            store = ome_zarr.io.parse_url(hcs_path, mode="w").store
            root_group = zarr.group(store=store)

            rows, columns = self.get_rows_and_columns()
            well_paths = [f"{well_id[0]}/{well_id[1:]}" for well_id in sorted(self.regions)]
            ome_zarr.writer.write_plate_metadata(root_group, rows, [str(col) for col in columns], well_paths)

            for well_id in self.regions:
                row, col = well_id[0], well_id[1:]
                row_group = root_group.require_group(row)
                well_group = row_group.require_group(col)
                self.write_well_and_metadata(well_id, well_group)

        print(f"Data saved in HCS OME-ZARR format at: {hcs_path}")
        self.finished_saving.emit(hcs_path, self.dtype)

    def write_well_and_metadata(self, well_id, well_group):
        """Process and save data for a single well across all timepoints."""
        data = self.load_and_merge_timepoints(well_id)
        intensity_min = np.iinfo(self.dtype).min
        intensity_max = np.iinfo(self.dtype).max
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

    def load_and_merge_timepoints(self, well_id=''):
        """Load and merge data for a well from Zarr files for each timepoint."""
        t_data = []
        t_shapes = []
        for t in self.time_points:
            if well_id:
                filepath = f"{well_id}_{self.output_name}"
            else:
                filepath = f"{self.output_name}"
            zarr_path = os.path.join(self.input_folder, f"{t}_stitched", filepath)
            print(f"t:{t} well:{well_id}, \t{zarr_path}")
            z = zarr.open(zarr_path, mode='r')
            t_array = da.from_zarr(z['0'], chunks=self.chunks)
            t_data.append(t_array)
            t_shapes.append(t_array.shape)

        if len(t_data) > 1:
            max_shape = tuple(max(s) for s in zip(*t_shapes))
            padded_data = [self.pad_to_largest(t, max_shape) for t in t_data]
            data = da.concatenate(padded_data, axis=0)
        elif len(t_data) == 1:
            data = t_data[0]
        else:
            raise ValueError("no data loaded from timepoints.")

        return data

    def pad_to_largest(self, array, target_shape):
        if array.shape == target_shape:
            return array
        pad_widths = [(0, max(0, ts - s)) for s, ts in zip(array.shape, target_shape)]
        return da.pad(array, pad_widths, mode='constant', constant_values=0)

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
            self.time_points = self.get_time_points()
            for time_point in self.time_points:
                ttime = time.time()
                print(f"starting t:{time_point}...")
                self.parse_filenames(time_point)

                if self.apply_flatfield:
                    print("Calculating flatfields...")
                    self.getting_flatfields.emit()
                    self.get_flatfields(progress_callback=self.update_progress.emit)
                    print("time to apply flatfields", time.time() - ttime)

                for region in self.regions:
                    wtime = time.time()
                    self.starting_stitching.emit()
                    print(f"\nstarting stitching...")
                    self.stitch_images(time_point, region, progress_callback=self.update_progress.emit)

                    sttime = time.time()
                    print("time to stitch region", sttime - wtime)

                    self.starting_saving.emit(not STITCH_COMPLETE_ACQUISITION)
                    print(f"saving...")
                    self.save_as_ome_zarr(time_point, region)

                    print("time to save stitched region", time.time() - sttime)
                    print("time per region", time.time() - wtime)
                    print(f"...done saving region:{region}")
                print(f"...finished t:{time_point}")
                print("time per timepoint", time.time() - ttime)

            if STITCH_COMPLETE_ACQUISITION and ".ome.zarr" in self.output_name:
                self.starting_saving.emit(True)
                scatime = time.time()
                if len(self.regions) > 1:
                    self.create_hcs_ome_zarr()
                    print("...done saving complete hcs successfully")
                else:
                    self.create_complete_ome_zarr()
                    print("...done saving complete successfully")
                print("time to save merged regions and timepoints", time.time() - scatime)
            else:
                self.finished_saving.emit(self.output_path, self.dtype)
            print("total time to stitch + save:", time.time() - stime)

        except Exception as e:
            print("time before error", time.time() - stime)
            print(f"Error while stitching: {e}")
            raise