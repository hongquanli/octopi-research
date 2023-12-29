import json
import os
from glob import glob
from lxml import etree as ET
import cv2
from stitcher import stitch_slide, compute_overlap_percent
import sys

def get_pixel_size(slide_path, default_pixel_size=1.85, default_tube_lens_mm=50.0, default_objective_tube_lens_mm=180.0, default_magnification=20.0):
    parameter_path = os.path.join(slide_path, "acquisition parameters.json")
    parameters = {}
    with open(parameter_path, "r") as f:
        parameters = json.load(f)
    try:
        tube_lens_mm = float(parameters['tube_lens_mm'])
    except KeyError:
        tube_lens_mm = default_tube_lens_mm
    try:
        pixel_size_um = float(parameters['sensor_pixel_size_um'])
    except KeyError:
        pixel_size_um = default_pixel_size
    try:
        objective_tube_lens_mm = float(parameters['objective']['tube_lens_f_mm'])
    except KeyError:
        objective_tube_lens_mm = default_objective_tube_lens_mm
    try:
        magnification = float(parameters['objective']['magnification'])
    except KeyError:
        magnification = default_magnification

    pixel_size_xy = pixel_size_um/(magnification/(objective_tube_lens_mm/tube_lens_mm))

    return pixel_size_xy

def get_overlap(slide_path, **kwargs):
    sample_fov_path = os.path.join(slide_path, "0/*0_0_0_*.*")
    sample_fov_path = glob(sample_fov_path)[0]
    sample_fov_shape = cv2.imread(sample_fov_path).shape
    fov_width = sample_fov_shape[1]
    fov_height = sample_fov_shape[0]

    pixel_size_xy = get_pixel_size(slide_path, **kwargs)
    
    parameter_path = os.path.join(slide_path, "acquisition parameters.json")
    parameters = {}
    with open(parameter_path, "r") as f:
        parameters = json.load(f)

    dx = float(parameters['dx(mm)'])*1000.0
    dy = float(parameters['dy(mm)'])*1000.0

    overlap_percent = compute_overlap_percent(dx, dy, fov_width, fov_height, pixel_size_xy)

    return overlap_percent

def get_time_indices(slide_path):
    
    parameter_path = os.path.join(slide_path, "acquisition parameters.json")
    parameters = {}
    with open(parameter_path, "r") as f:
        parameters = json.load(f)

    time_indices = list(range(int(parameters['Nt'])))
    return time_indices

def get_channels(slide_path):
    config_xml_tree_root = ET.parse(os.path.join(slide_path, "configurations.xml")).getroot()
    channel_names = []
    for mode in config_xml_tree_root.iter('mode'):
        if mode.get("Selected") == "1":
            channel_names.append(mode.get('Name').replace(" ","_"))
    return channel_names

def get_z_indices(slide_path):
    parameter_path = os.path.join(slide_path, "acquisition parameters.json")
    parameters = {}
    with open(parameter_path, "r") as f:
        parameters = json.load(f)

    z_indices = list(range(int(parameters['Nz'])))
    return z_indices


def get_coord_names(slide_path):
    sample_fovs_path=os.path.join(slide_path, "0/*_0_0_0_*.*")
    sample_fovs = glob(sample_fovs_path)
    coord_names = []
    for fov in sample_fovs:
        filename = fov.split("/")[-1]
        coord_name = filename.split("_0_")[0]
        coord_names.append(coord_name+"_")
    coord_names = list(set(coord_names))
    if len(coord_names) == 0:
        coord_names = ['']
    return coord_names

def stitch_slide_from_path(slide_path, **kwargs):
    time_indices = get_time_indices(slide_path)
    z_indices = get_z_indices(slide_path)
    channels = get_channels(slide_path)
    coord_names = get_coord_names(slide_path)
    overlap_percent = get_overlap(slide_path, **kwargs)

    recompute_overlap = (overlap_percent > 10)

    stitch_slide(slide_path, time_indices, channels, z_indices, coord_names, overlap_percent = overlap_percent, reg_threshold=0.30, avg_displacement_threshold=2.50, abs_displacement_threshold=3.50, tile_downsampling=1.0, recompute_overlap=recompute_overlap)

def print_usage():
    usage_str = """
    Stitches images using Fiji. NOTE: the y-indexing of images must go from bottom to top, which is only the case for the most recent patch of Squid.

    Usage (to be run from software directory in your Squid install):

    python tools/script_stitch_slide.py PATH_TO_SLIDE_FOLDER [--sensor-size SENSOR_PIXEL_SIZE_UM] [--tube-lens TUBE_LENS_MM] [--objective-tube-lens OBJECTIVE_TUBE_LENS_MM] [--magnification MAGNIFICATION] [--help]

    OPTIONAL PARAMETERS:
    --help/-h : Prints this and exits.

    --sensor-size : Sensor pixel size in um
    --tube-lens : Your tube lens's length in mm (separate from the objective's
        tube lens focal length)
    --objective-tube-lens : Your objective's tube lens focal length in mm
    --magnification : Your objective's listed magnification

    The script will first try to read this parameters from acquisition parameters.json, but will default to your provided values if it can't.
    """

    print(usage_str)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No slide path name provided!")
        print_usage()
        exit()
        
    parameter_names = {
            "--sensor-size":"default_pixel_size",
            "--tube-lens":"default_tube_lens_mm",
            "--objective-tube-lens":"default_objective_tube_lens_mm",
            "--magnification":"default_magnification"
            }

    param_list = list(parameter_names.keys())

    user_kwargs = {}

    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        exit()

    for i in range(len(sys.argv)):
        if sys.argv[i] in param_list:
            try:
                arg_value = float(sys.argv[i+1])
                user_kwargs[parameter_names[sys.argv[i]]] = arg_value
            except (IndexError, ValueError):
                print("Malformed argument, exiting.")
                exit()

    

    stitch_slide_from_path(sys.argv[1], **user_kwargs)
