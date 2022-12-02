import os

# qt libraries
from qtpy.QtCore import QObject

from control._def import *

import json
from pathlib import Path
import control.utils_config as utils_config

from typing import Optional, List, Union, Tuple, Any

class Configuration:
    """ illumination channel configuration """

    def __init__(self,
        mode_id:str, # id is a builtin function
        name:str,
        camera_sn,
        exposure_time:float,
        analog_gain:float,
        illumination_source:int,
        illumination_intensity:float,
        channel_z_offset:Optional[float]=None
    ):
        self.id = mode_id
        
        self.name = name
        """ channel name """

        self.exposure_time = exposure_time
        """ exposure time in ms """

        self.analog_gain = analog_gain
        """ analog gain increases camera sensor sensitivity """

        self.illumination_source = illumination_source
        """ illumination source id used by microcontroller """
        self.illumination_intensity = illumination_intensity
        """ percent light source power/intensity """

        self.camera_sn = camera_sn

        self.channel_z_offset=channel_z_offset
        """ relative z offset of the average object in this channel (e.g. used in multichannel acquisition) """

    def set_exposure_time(self,new_value):
        self.exposure_time=new_value
    def set_analog_gain(self,new_value):
        self.analog_gain=new_value
    def set_offset(self,new_value):
        self.channel_z_offset=new_value
    def set_illumination_intensity(self,new_value):
        self.illumination_intensity=new_value

    def as_dict(self):
        return {
            "ID":self.id,
            "Name":self.name,
            "IlluminationSource":self.illumination_source,
            "ExposureTime":self.exposure_time,
            "AnalogGain":self.analog_gain,
            "IlluminationIntensity":self.illumination_intensity,
            "CameraSN":self.camera_sn,
            "RelativeZOffsetUM":self.channel_z_offset,
        }

class ConfigurationManager(QObject):
    @property
    def num_configurations(self)->int:
        return len(self.configurations)

    def __init__(self,filename):
        QObject.__init__(self)
        self.config_filename:str = filename
        self.configurations:List[Configuration] = []
        self.read_configurations(self.config_filename)
        
    def save_configurations(self):
        self.write_configuration(self.config_filename)

    def write_configuration(self,filename:str):
        json_tree_string=json.encoder.JSONEncoder(indent=2).encode({
            'configurations':[
                config.as_dict() 
                for config 
                in self.configurations
            ]
        })
        with open(filename, mode="w", encoding="utf-8") as json_file:
            json_file.write(json_tree_string)

    def read_configurations(self,filename:str):
        with open(filename,mode="r",encoding="utf-8") as json_file:
            json_tree=json.decoder.JSONDecoder().decode(json_file.read())

        self.configurations=[]

        for mode in json_tree['configurations']:
            self.configurations.append(
                Configuration(
                    mode_id =                       mode['ID'],
                    name =                          mode['Name'],
                    illumination_source =    int(   mode['IlluminationSource']),
                    exposure_time =          float( mode['ExposureTime']),
                    analog_gain =            float( mode['AnalogGain']),
                    illumination_intensity = float( mode['IlluminationIntensity']),
                    camera_sn =                     mode['CameraSN'],
                    channel_z_offset =       float( mode['RelativeZOffsetUM']),
                )
            )

    def update_configuration(self,configuration_id:str,attribute_name:str,new_value:Any):
        mode_to_update = [config for config in self.configurations if config.id==configuration_id][0]
        
        if attribute_name=="ID":
            mode_to_update.id=new_value
        elif attribute_name=="Name":
            mode_to_update.name=new_value
        elif attribute_name=="IlluminationSource":
            mode_to_update.illumination_source=new_value
        elif attribute_name=="ExposureTime":
            mode_to_update.exposure_time=new_value
        elif attribute_name=="AnalogGain":
            mode_to_update.analog_gain=new_value
        elif attribute_name=="IlluminationIntensity":
            mode_to_update.illumination_intensity=new_value
        elif attribute_name=="CameraSN":
            mode_to_update.camera_sn=new_value
        elif attribute_name=="RelativeZOffsetUM":
            mode_to_update.channel_z_offset=new_value
        else:
            raise Exception(f"{attribute_name}")

        self.save_configurations()
