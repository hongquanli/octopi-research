import os
from glob import glob
from script_stitch_slide import get_channels, get_time_indices
import json
import sys
import pandas as pd

def get_ny(slide_path):
    parameter_path = os.path.join(slide_path, "acquisition parameters.json")
    parameters = {}
    with open(parameter_path, "r") as f:
        parameters = json.load(f)

    Ny = int(parameters['Ny'])
    return Ny

def get_inverted_y_filepath(filepath, channel_name, Ny):
    """Given a channel name to strip and a number of y indices, returns
    a version of the slide name with its y-index inverted."""
    channel_name = channel_name.replace(" ", "_")
    filename = filepath.split("/")[-1]
    extension = filename.split(".")[-1]
    coord_list = filename.replace(channel_name, "").replace("."+extension,"").strip("_").split("_")
    if len(coord_list) > 3:
        coord_list[1] = str(Ny-1-int(coord_list[1]))
    else:
        coord_list[0] = str(Ny-1-int(coord_list[0]))

    inverted_y_filename = "_".join([*coord_list, channel_name])+"."+extension
    inverted_y_filepath = filepath.replace(filename, inverted_y_filename)
    return inverted_y_filepath


def invert_y_in_folder(fovs_path, channel_names, Ny):
    """Given a folder with FOVs, channel names, and Ny, inverts the y-indices of all of them"""
    
    for channel in channel_names:
        channel = channel.replace(" ", "_")
        filepaths = list(glob(os.path.join(fovs_path, "*_*_*_"+channel+".*")))
        for path in filepaths:
            inv_y_filepath = get_inverted_y_filepath(path, channel, Ny)
            os.rename(path, inv_y_filepath+"._inverted")
        for path in filepaths:
            os.rename(path+"._inverted", path)

def invert_y_in_slide(slide_path):
    Ny = get_ny(slide_path)
    time_indices = get_time_indices(slide_path)
    channels = get_channels(slide_path)
    for t in time_indices:
        fovs_path = os.path.join(slide_path, str(t))
        invert_y_in_folder(fovs_path, channels, Ny)

        # invert the y-index in the CSV too
        coord_csv_path = os.path.join(fovs_path, "coordinates.csv")
        coord_df = pd.read_csv(coord_csv_path)
        coord_df["i"] = (Ny-1)-coord_df["i"]
        coord_df.to_csv(coord_csv_path, index=False)

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("Must provide a path to a slide folder.")
        exit()
    invert_y_in_slide(sys.argv[1])
    print("Inverted all i/y-indices in "+sys.argv[1])
