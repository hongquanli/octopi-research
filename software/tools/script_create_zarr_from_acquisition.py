from lxml import etree as ET
import json
import sys
import os

import zarr
from skimage.io import imread
from skimage.io.collection import alphanumeric_key
from dask import delayed
import dask.array as da
from glob import glob

from ome_zarr.writer import write_image
from ome_zarr.io import parse_url

lazy_imread = delayed(imread)

def read_configurations_used(filepath):
    xml_tree = ET.parse(filepath)
    xml_tree_root = xml_tree.getroot()
    conf_list = []
    for mode in xml_tree_root.iter('mode'):
        selected = int(mode.get("Selected"))
        if selected != 0:
            mode_id = int(mode.get("ID"))
            mode_name = mode.get('Name')
            conf_list.append((mode_id,mode_name))
    conf_list = sorted(conf_list,key= lambda tup: tup[0])
    conf_list = [tup[1] for tup in conf_list]
    return conf_list

def get_dimensions_for_dataset(dataset_folder_path, sensor_pixel_size_um_default = 1.0, objective_magnification_default=1.0):
    """Returns dict of dimensions and then step sizes in
    mm for dx/dy, um for dz, and s in dt.

    :return: dict in format {
        'Nx':Nx,
        'Ny':Ny,
        'Nz':Nz,
        'Nt':Nt,
        'dt':dt,
        'dx': dx (in mm),
        'dy': dy (in mm),
        'dz': dz (in um),
        'Nc': number of channels,
        'channels': list of channel names,
        'pixel_size_um': pixel side length (in um),
        'FOV_shape': int 2-tuple that is the shape of a single channel's FOV,
        'FOV_dtype': numpy dtype representing a single FOV image's dtype
    }"""
    acq_param_path = os.path.join(dataset_folder_path,"acquisition parameters.json")
    config_xml_path = os.path.join(dataset_folder_path,"configurations.xml")
    acq_params = None
    with open(acq_param_path,'r') as file:
        acq_params = json.load(file)
    Nt = int(acq_params.get('Nt'))
    Nz = int(acq_params.get('Nz'))
    dt = float(acq_params.get('dt(s)'))
    dz = float(acq_params.get('dz(um)'))
    
    Nx = int(acq_params.get('Nx'))
    Ny = int(acq_params.get('Ny'))
    dx = float(acq_params.get('dx(mm)'))
    dy = float(acq_params.get('dy(mm)'))

    try:
        objective = acq_params.get('objective')
        objective_magnification = float(objective['magnification'])
    except (KeyError, ValueError, AttributeError, TypeError):
        objective_magnification = objective_magnification_default

    try:
        sensor = acq_params.get('sensor')
        sensor_pixel_size = float(sensor['pixel_size_um'])
    except (KeyError, ValueError, AttributeError, TypeError):
        sensor_pixel_size = sensor_pixel_size_um_default

    pixel_size_um = sensor_pixel_size/objective_magnification

    imagespath = os.path.join(dataset_folder_path, '0/0_*.*')
    first_file  = sorted(glob(imagespath), key=alphanumeric_key)[0]
    sample = imread(first_file)
    
    FOV_shape = sample.shape
    FOV_dtype = sample.dtype

    channels = read_configurations_used(config_xml_path)
    Nc = len(channels)

    return {'Nx':Nx,
            'Ny':Ny,
            'Nz':Nz,
            'dx':dx,
            'dy':dy,
            'dz':dz,
            'Nt':Nt,
            'dt':dt,
            'Nc':Nc,
            'channels':channels,
            'pixel_size_um':pixel_size_um,
            'FOV_shape':FOV_shape,
            'FOV_dtype':FOV_dtype
            }


def create_dask_array_for_single_fov(dataset_folder_path, x=0,y=0, sensor_pixel_size_um_default = 1.0, objective_magnification_default=1.0):
    dimension_data = get_dimensions_for_dataset(dataset_folder_path, sensor_pixel_size_um_default, objective_magnification_default)
    if x >= dimension_data['Nx'] or x<0 or y>= dimension_data['Ny'] or y < 0:
        raise IndexError("FOV indices out of range.")
    dask_arrays_time = []
    for t in range(dimension_data['Nt']):
        dask_arrays_channel = []
        for channel in dimension_data['channels']:
            images_path = str(t)+"/"+str(y)+"_"+str(x)+"_*_"+channel.strip().replace(" ","_")+".*"
            images_path = os.path.join(dataset_folder_path, images_path)
            filenames = sorted(glob(images_path),key=alphanumeric_key)
            lazy_arrays = [lazy_imread(fn) for fn in filenames]
            dask_arrays = [
                    da.from_delayed(delayed_reader, shape = dimension_data['FOV_shape'], dtype=dimension_data['FOV_dtype'])
                    for delayed_reader in lazy_arrays
                    ]
            stack = da.stack(dask_arrays, axis=0)
            dask_arrays_channel.append(stack)
        channel_stack = da.stack(dask_arrays_channel, axis=0)
        dask_arrays_time.append(channel_stack)
    time_stack = da.stack(dask_arrays_time,axis=0)
    return time_stack

def create_zarr_for_single_fov(dataset_folder_path, saving_path, x=0,y=0,sensor_pixel_size_um=1.0, objective_magnification=1.0):
    try:
        os.mkdir(saving_path)
    except FileExistsError:
        pass
    dimension_data = get_dimensions_for_dataset(dataset_folder_path, sensor_pixel_size_um, objective_magnification)
    scale_xy = dimension_data["pixel_size_um"]
    scale_z = dimension_data["dz"]
    if scale_z == 0.0:
        scale_z = 1.0
    scale_t = dimension_data["dt"]
    if scale_t == 0.0:
        scale_t = 1.0
    coord_transform=[{"type":"scale","scale":[scale_t,1.0,scale_z,scale_xy,scale_xy]}]

    fov_dask_array = create_dask_array_for_single_fov(dataset_folder_path, x,y, sensor_pixel_size_um, objective_magnification)
    xy_only_dims = fov_dask_array.shape[3:]
    store = parse_url(saving_path, mode="w").store
    root = zarr.group(store=store)
    write_image(image=fov_dask_array, group=root,
            scaler = None, axes=["t","c","z","y","x"],
            coordinate_transformations=[coord_transform],
            storage_options=dict(chunks=(1,1,1,*xy_only_dims)))

if __name__ == "__main__":
    if len(sys.argv) != 5 and len(sys.argv) != 3 and len(sys.argv) != 7:
        raise RuntimeError("2 positional arguments required: path to slide data folder, and path to zarr to write. The following 2 positional arguments, if they exist, must be the x-index and the y-index of the FOV to convert (default 0). The last two positional arguments should be the pixel_size_um parameter of the sensor, and the magnification of the objective used.")
    folderpath = sys.argv[1]
    saving_path = sys.argv[2]
    try:
        x = int(sys.argv[3])
        y = int(sys.argv[4])
    except IndexError:
        x = 0
        y = 0

    try:
        sensor_pixel_size = float(sys.argv[5])
        objective_magnification = float(sys.argv[6])
    except IndexError:
        sensor_pixel_size=1.85
        objective_magnification=20.0

    create_zarr_for_single_fov(folderpath, saving_path,x,y, sensor_pixel_size, objective_magnification)
    print("OME-Zarr written to "+saving_path)
    print("Use the command\n    $> napari --plugin napari-ome-zarr "+saving_path+"\nto view.")
