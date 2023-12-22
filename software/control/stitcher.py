import cv2
import imagej, scyjava
from control._def import JVM_MAX_MEMORY_GB
import os
import shutil
from glob import glob

def compute_overlap_percent(deltaX, deltaY, image_width, image_height, pixel_size_xy, min_overlap=0):
    """Helper function to calculate percent overlap between images in
    a grid"""
    shift_x = deltaX/pixel_size_xy
    shift_y = deltaY/pixel_size_xy
    overlap_x = max(0,int(image_width-shift_x))
    overlap_y = max(0,int(image_height-shift_y))
    overlap_x = overlap_x/image_width
    overlap_y = overlap_y/image_height
    overlap = max(int(min_overlap), int(overlap_x), int(overlap_y))
    return overlap


class Stitcher:
    def __init__(self):
        scyjava.config.add_option('-Xmx'+str(int(JVM_MAX_MEMORY_GB))+'g')
        self.ij = imagej.init('sc.fiji:fiji', mode='headless')

    def stitch_single_channel(self, fovs_path, channel_name, z_index, coord_name='', overlap_percent=10, reg_threshold = 0.30, avg_displacement_threshold=2.50, abs_displacement_threshold=3.50, tile_downsampling=0.5):
        """
        Stitches images using grid/collection stitching with filename-defined
        positions following the format that squid saves multipoint acquisitions
        in. Requires that the filename-indicated grid positions go top-to-bottom
        on the y axis and left-to-right on the x axis (this is handled by
        the MultiPointController code in control/core.py). Must be passed
        the folder containing the image files.
        """
        channel_name = channel_name.replace(" ", "_")

        file_search_name = coord_name+"0_0_"+str(z_index)+"_"+channel_name+".*"

        ext_glob = list(glob(os.path.join(fovs_path,file_search_name)))

        file_ext = ext_glob[0].split(".")[-1]

        y_length_pattern = coord_name+"*_0_"+str(z_index)+"_"+channel_name+"."+file_ext

        x_length_pattern = coord_name+"0_*_"+str(z_index)+"_"+channel_name+"."+file_ext

        grid_size_y = len(list(glob(os.path.join(fovs_path,y_length_pattern))))

        grid_size_x = len(list(glob(os.path.join(fovs_path,x_length_pattern))))

        stitching_filename_pattern = coord_name+"{y}_{x}_"+str(z_index)+"_"+channel_name+"."+file_ext

        stitching_output_dir = 'COORD_'+coord_name+"_Z_"+str(z_index)+"_"+channel_name+"_stitched/"

        tile_conf_name = "TileConfiguration_COORD_"+coord_name+"_Z_"+str(z_index)+"_"+channel_name+".txt"

        stitching_output_dir = os.path.join(fovs_path,stitching_output_dir)

        os.makedirs(stitching_output_dir, exist_ok=True)


        sample_tile_name = coord_name+"0_0_"+str(z_index)+"_"+channel_name+"."+file_ext
        sample_tile_shape = cv2.imread(os.path.join(fovs_path, sample_tile_name)).shape

        tile_downsampled_width=int(sample_tile_shape[1]*tile_downsampling)
        tile_downsampled_height=int(sample_tile_shape[0]*tile_downsampling)
        stitching_params = {'type':'Filename defined position',
                'order':'Defined by filename',
                'fusion_mode':'Linear Blending',
                'grid_size_x':str(grid_size_x),
                'grid_size_y':str(grid_size_y),
                'first_file_index_x':str(0),
                'first_file_index_y':str(0),
                'ignore_z_stage':True,
                'downsample_tiles':False,
                'tile_overlap':str(overlap_percent),
                'directory':fovs_path,
                'file_names':stitching_filename_pattern,
                'output_textfile_name':tile_conf_name,
                'fusion_method':'Linear Blending',
                'regression_threshold':str(reg_threshold),
                'max/avg_displacement_threshold':str(avg_displacement_threshold),
                'absolute_displacement_threshold':str(abs_displacement_threshold),
                'compute_overlap':False,
                'computation_parameters':'Save computation time (but use more RAM)',
                'image_output':'Write to disk',
                'output_directory':stitching_output_dir #,
                #'x':str(tile_downsampling),
                #'y':str(tile_downsampling),
                #'width':str(tile_downsampled_width),
                #'height':str(tile_downsampled_height),
                #'interpolation':'Bicubic average'
                }

        plugin = "Grid/Collection stitching"

        self.ij.py.run_plugin(plugin, stitching_params)
