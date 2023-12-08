from lxml import etree as ET
import json
import sys
import os
import re

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

def get_dimensions_for_dataset(dataset_folder_path, sensor_pixel_size_um_default = 1.0, objective_magnification_default=1.0, Nz_override = None, Nt_override = None):
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
    if Nt_override is not None:
        if Nt_override < Nt:
            Nt = Nt_override
    Nz = int(acq_params.get('Nz'))
    if Nz_override is not None:
        if Nz_override < Nz:
            Nz = Nz_override
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


def create_dask_array_for_single_fov(dataset_folder_path, x=0,y=0, sensor_pixel_size_um_default = 1.0, objective_magnification_default=1.0, z_to_use=None, t_to_use=None, well=0):
    Nt_override = None
    if t_to_use is not None:
        Nt_override = len(t_to_use)
    Nz_override = None
    if z_to_use is not None:
        Nz_override = len(z_to_use)
    dimension_data = get_dimensions_for_dataset(dataset_folder_path, sensor_pixel_size_um_default, objective_magnification_default, Nz_override, Nt_override)
    if t_to_use is not None:
        if max(t_to_use) >= dimension_data['Nt'] or min(t_to_use) < 0:
            raise IndexError("t index given in list out of bounds")
    if z_to_use is not None:
        if max(z_to_use) >= dimension_data['Nz'] or min(z_to_use) < 0:
            raise IndexError("z index given in list out of bounds")
    if t_to_use is None:
        t_to_use = list(range(dimension_data['Nt']))
    if z_to_use is None:
        z_to_use = list(range(dimension_data['Nz']))
    if x >= dimension_data['Nx'] or x<0 or y>= dimension_data['Ny'] or y < 0:
        raise IndexError("FOV indices out of range.")
    dask_arrays_time = []
    for t in t_to_use:
        dask_arrays_channel = []
        for channel in dimension_data['channels']:
            filenames = []
            for z in z_to_use:
                image_path = str(t)+"/"+str(y)+"_"+str(x)+"_"+str(z)+"_"+channel.strip().replace(" ","_")+".*"
                image_path = os.path.join(dataset_folder_path, image_path)
                file_matches = glob(image_path)
                if len(file_matches) > 0:
                    filenames.append(file_matches[0])
                else:
                    image_path = str(t)+"/"+str(well)+"_"+str(y)+"_"+str(x)+"_"+str(z)+"_"+channel.strip().replace(" ","_")+".*"
                    image_path = os.path.join(dataset_folder_path, image_path)
                    file_matches = glob(image_path)
                    if len(file_matches) > 0:
                        filenames.append(file_matches[0])
            filenames = sorted(filenames,key=alphanumeric_key)
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

def create_zarr_for_single_fov(dataset_folder_path, saving_path, x=0,y=0,sensor_pixel_size_um=1.0, objective_magnification=1.0, z_to_use=None, t_to_use = None, well=0):
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

    fov_dask_array = create_dask_array_for_single_fov(dataset_folder_path, x,y, sensor_pixel_size_um, objective_magnification, z_to_use, t_to_use, well)
    xy_only_dims = fov_dask_array.shape[3:]
    store = parse_url(saving_path, mode="w").store
    root = zarr.group(store=store)
    write_image(image=fov_dask_array, group=root,
            scaler = None, axes=["t","c","z","y","x"],
            coordinate_transformations=[coord_transform],
            storage_options=dict(chunks=(1,1,1,*xy_only_dims)))

if __name__ == "__main__":
    if len(sys.argv) != 5 and len(sys.argv) != 3 and len(sys.argv) != 7 and len(sys.argv) != 8 and len(sys.argv) != 9:
        raise RuntimeError("2 positional arguments required: path to slide data folder, and path to zarr to write. The following 2 positional arguments, if they exist, must be the x-index and the y-index of the FOV to convert (default 0). The last two positional arguments should be the pixel_size_um parameter of the sensor, and the magnification of the objective used. The last two positional arguments are an override on the number of z steps to use and an override on the number of t steps to use.")
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

    try:
        Nz_override = int(sys.argv[7])
        z_to_use = list(range(Nz_override))
    except IndexError:
        z_to_use = None

    try:
        Nt_override = int(sys.argv[8])
        t_to_use = list(range(Nt_overide))
    except IndexError:
        t_to_use = None

    create_zarr_for_single_fov(folderpath, saving_path,x,y, sensor_pixel_size, objective_magnification, z_to_use, t_to_use)
    print("OME-Zarr written to "+saving_path)
    print("Use the command\n    $> napari --plugin napari-ome-zarr "+saving_path+"\nto view.")
