import cv2
import imagej, scyjava
import os
import shutil
import tifffile
from glob import glob
import numpy as np
import multiprocessing as mp

JVM_MAX_MEMORY_GB = 4.0

def compute_overlap_percent(deltaX, deltaY, image_width, image_height, pixel_size_xy, min_overlap=0):
    """Helper function to calculate percent overlap between images in
    a grid"""
    shift_x = deltaX/pixel_size_xy
    shift_y = deltaY/pixel_size_xy
    overlap_x = max(0,image_width-shift_x)
    overlap_y = max(0,image_height-shift_y)
    overlap_x = overlap_x*100.0/image_width
    overlap_y = overlap_y*100.0/image_height
    overlap = max(min_overlap, overlap_x, overlap_y)
    return overlap

def stitch_slide_mp(*args, **kwargs):
    ctx = mp.get_context('spawn')
    stitch_process = ctx.Process(target=stitch_slide, args=args, kwargs=kwargs)
    stitch_process.start()
    return stitch_process
    
def migrate_tile_config(fovs_path, coord_name, channel_name_source, z_index_source, channel_name_target, z_index_target):
    channel_name_source = channel_name_source.replace(" ", "_")
    channel_name_target = channel_name_target.replace(" ","_")
    
    if z_index_source == z_index_target and channel_name_source == channel_name_target:
        raise RuntimeError("Source and target for channel/z-index migration are the same!")

    tile_conf_name_source = "TileConfiguration_COORD_"+coord_name+"_Z_"+str(z_index_source)+"_"+channel_name_source+".registered.txt"
    tile_conf_name_target = "TileConfiguration_COORD_"+coord_name+"_Z_"+str(z_index_target)+"_"+channel_name_target+".registered.txt"
    tile_config_source_path = os.path.join(fovs_path, tile_conf_name_source)
        
    if not os.path.isfile(tile_config_source_path):
        tile_config_source_path = tile_config_source_path.replace(".registered.txt", ".txt")

    assert os.path.isfile(tile_config_source_path)

    tile_config_target_path = os.path.join(fovs_path, tile_conf_name_target)

    tile_conf_target = open(tile_config_target_path, 'w')

    with open(tile_config_source_path, 'r') as tile_conf_source:
        for line in tile_conf_source:
            if line.startswith("#") or line.startswith("dim") or len(line) <= 1:
                tile_conf_target.write(line)
                continue
            line_to_write = line.replace("_"+str(z_index_source)+"_"+channel_name_source, "_"+str(z_index_target)+"_"+channel_name_target)
            tile_conf_target.write(line_to_write)

    tile_conf_target.close()

    return tile_conf_name_target

def stitch_slide(slide_path, time_indices, channels, z_indices, coord_names=[''], overlap_percent=10, reg_threshold=0.30, avg_displacement_threshold=2.50, abs_displacement_threshold=3.50, tile_downsampling=0.5, recompute_overlap=False, **kwargs):
    st = Stitcher()
    st.stitch_slide(slide_path, time_indices, channels, z_indices, coord_names, overlap_percent, reg_threshold, avg_displacement_threshold, abs_displacement_threshold, tile_downsampling, recompute_overlap, **kwargs)

class Stitcher:
    def __init__(self):
        scyjava.config.add_option('-Xmx'+str(int(JVM_MAX_MEMORY_GB))+'g')
        self.ij = imagej.init('sc.fiji:fiji', mode='headless')

    def stitch_slide(self, slide_path, time_indices, channels, z_indices, coord_names=[''], overlap_percent = 10, reg_threshold=0.30, avg_displacement_threshold=2.50, abs_displacement_threshold=3.50, tile_downsampling=0.5, recompute_overlap=False, **kwargs):
        for time_index in time_indices:
            self.stitch_single_time_point(slide_path, time_index, channels, z_indices, coord_names, overlap_percent, reg_threshold, avg_displacement_threshold, abs_displacement_threshold, tile_downsampling, recompute_overlap, **kwargs)

    def stitch_single_time_point(self, slide_path, time_index, channels, z_indices, coord_names = [''], overlap_percent=10, reg_threshold=0.30, avg_displacement_threshold=2.50, abs_displacement_threshold=3.50, tile_downsampling=0.5, recompute_overlap=False, **kwargs):
        fovs_path = os.path.join(slide_path, str(time_index))
        for coord_name in coord_names:
            already_registered = False
            registered_z_index = None
            registered_channel_name = None
            for channel_name in channels:
                for z_index in z_indices:
                    if already_registered:
                        migrate_tile_config(fovs_path, coord_name, registered_channel_name, registered_z_index, channel_name.replace(" ", "_"), z_index)
                        output_dir = self.stitch_single_channel_from_tile_config(fovs_path, channel_name, z_index, coord_name)
                        combine_stitched_channels(output_dir, **kwargs)
                    else:
                        output_dir = self.stitch_single_channel(fovs_path, channel_name, z_index, coord_name, overlap_percent, reg_threshold, avg_displacement_threshold, abs_displacement_threshold, tile_downsampling, recompute_overlap)
                        combine_stitched_channels(output_dir, **kwargs)
                    if not already_registered:
                        already_registered = True
                        registered_z_index = z_index
                        registered_channel_name = channel_name.replace(" ", "_")


    def stitch_single_channel_from_tile_config(self, fovs_path, channel_name, z_index, coord_name):
        """
        Stitches images using grid/collection stitching, reading registered
        positions from a tile configuration path that has been migrated from an
        already-registered channel/z-level at the same coordinate name
        """
        channel_name = channel_name.replace(" ", "_")
        tile_conf_name = "TileConfiguration_COORD_"+coord_name+"_Z_"+str(z_index)+"_"+channel_name+".registered.txt"
        assert os.path.isfile(os.path.join(fovs_path, tile_conf_name))

        stitching_output_dir = 'COORD_'+coord_name+"_Z_"+str(z_index)+"_"+channel_name+"_stitched/"

        stitching_output_dir = os.path.join(fovs_path,stitching_output_dir)

        os.makedirs(stitching_output_dir, exist_ok=True)

        stitching_params = {'type':'Positions from file',
                'order':'Defined by TileConfiguration',
                'fusion_mode':'Linear Blending',
                'ignore_z_stage':True,
                'downsample_tiles':False,
                'directory':fovs_path,
                'layout_file':tile_conf_name,
                'fusion_method':'Linear Blending',
                'regression_threshold':"0.30",
                'max/avg_displacement_threshold':"2.50",
                'absolute_displacement_threshold':"3.50",
                'compute_overlap':False,
                'computation_parameters':'Save computation time (but use more RAM)',
                'image_output':'Write to disk',
                'output_directory':stitching_output_dir 
                }

        plugin = "Grid/Collection stitching"

        self.ij.py.run_plugin(plugin, stitching_params)

        return stitching_output_dir


    def stitch_single_channel(self, fovs_path, channel_name, z_index, coord_name='', overlap_percent=10, reg_threshold = 0.30, avg_displacement_threshold=2.50, abs_displacement_threshold=3.50, tile_downsampling=0.5, recompute_overlap=False):
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
                'grid_size_x':grid_size_x,
                'grid_size_y':grid_size_y,
                'first_file_index_x':str(0),
                'first_file_index_y':str(0),
                'ignore_z_stage':True,
                'downsample_tiles':False,
                'tile_overlap':overlap_percent,
                'directory':fovs_path,
                'file_names':stitching_filename_pattern,
                'output_textfile_name':tile_conf_name,
                'fusion_method':'Linear Blending',
                'regression_threshold':str(reg_threshold),
                'max/avg_displacement_threshold':str(avg_displacement_threshold),
                'absolute_displacement_threshold':str(abs_displacement_threshold),
                'compute_overlap':recompute_overlap,
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

        return stitching_output_dir

def images_identical(im_1, im_2):
    """Return True if two opencv arrays are exactly the same"""
    return im_1.shape == im_2.shape and not (np.bitwise_xor(im_1,im_2).any())

def combine_stitched_channels(stitched_image_folder_path, write_multiscale_tiff = False, pixel_size_um=1.0, tile_side_length=1024, subresolutions=3):
    """Combines the three channel images created into one TIFF. Currently
    not recommended to run this with multiscale TIFF enabled, combining
    all channels/z-levels in one region of the acquisition into one OME-TIFF
    to be done later."""

    c1 = cv2.imread(os.path.join(stitched_image_folder_path, "img_t1_z1_c1"))

    c2 = cv2.imread(os.path.join(stitched_image_folder_path, "img_t1_z1_c2"))

    c3 = cv2.imread(os.path.join(stitched_image_folder_path, "img_t1_z1_c3"))

    combine_to_mono = False

    if c2 is None or c3 is None:
        combine_to_mono = True

    if write_multiscale_tiff:
        output_path = os.path.join(stitched_image_folder_path,"stitched_img.ome.tif")
    else:
        output_path = os.path.join(stitched_image_folder_path,"stitched_img.tif")

    if not combine_to_mono:
        if images_identical(c1,c2) and images_identical(c2,c3):
            combine_to_mono = True

    if not combine_to_mono:
        c1 = c1[:,:,0]
        c2 = c2[:,:,1]
        c3 = c3[:,:,2]
        if write_multiscale_tiff:
            data = np.stack((c1,c2,c3), axis=0)
        else:
            data = np.stack((c1,c2,c3),axis=-1)
        axes = 'CYX'
        channels = {'Name':['Channel 1', 'Channel 2', 'Channel 3']}
    else:
        data = c1[:,:,0]
        axes = 'YX'
        channels = None

    metadata = {
            'axes':axes,
            'SignificantBits':16 if data.dtype==np.uint8 else 8,
            'PhysicalSizeX':pixel_size_um,
            'PhysicalSizeY':pixel_size_um,
            'PhysicalSizeXUnit':'um',
            'PhysicalSizeYUnit':'um',
            }
    if channels is not None:
        metadata['Channel'] = channels

    options = dict(
            photometric = 'rgb' if not combine_to_mono else 'minisblack',
            tile = (tile_side_length, tile_side_length),
            compression = 'jpeg',
            resolutionunit='CENTIMETER',
            maxworkers = 2
            )

    if write_multiscale_tiff:
        with tifffile.TiffWriter(output_path, bigtiff=True) as tif:
                tif.write(data, subifds=subresolutions,
                    resolution=(1e4/pixel_size_um, 1e4/pixel_size_um),
                    metadata = metadata,
                    **options)
                for level in range(subresolutions):
                    mag = 2**(level+1)
                    if combine_to_mono:
                        subdata = data[::mag,::mag]
                    else:
                        subdata = data[:,::mag,::mag]
                    tif.write(
                        subdata,
                        subfiletype=1,
                        resolution=(1e4/mag/pixel_size_um, 1e3/mag/pixel_size_um),
                        **options
                        )

                if combine_to_mono:
                    thumbnail = (data[::8,::8] >> 2).astype('uint8')
                else:
                    thumbnail = (data[0,::8,::8] >> 2).astype('uint8')
                tif.write(thumbnail,metadata={'Name':'thumbnail'})
    else:
        cv2.imwrite(output_path, data)

    channel_files = [os.path.join(stitched_image_folder_path,'img_t1_z1_c')+str(i+1) for i in range(3)]

    for filename in channel_files:
        try:
            os.remove(filename)
        except FileNotFoundError:
            pass
