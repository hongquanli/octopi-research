import os

# qt libraries
from qtpy.QtCore import QObject

from control._def import *

from lxml import etree as ET
from pathlib import Path
import control.utils_config as utils_config

from typing import Optional, List, Union, Tuple

class Configuration:
    """
        self.name is channel name

        self.exposure_time is exposure_time in ms

        self.analog_gain is % additional light source power (?)
    """
    def __init__(self,
        mode_id:str,
        name:str,
        camera_sn,
        exposure_time:float,
        analog_gain:float,
        illumination_source:int,
        illumination_intensity:float
    ):
        self.id = mode_id
        """ channel name """
        self.name = name
        """ exposure time in ms """
        self.exposure_time = exposure_time
        """ analog gain in % additional light source power (?) """
        self.analog_gain = analog_gain
        self.illumination_source = illumination_source
        self.illumination_intensity = illumination_intensity
        self.camera_sn = camera_sn

class ConfigurationManager(QObject):
    def __init__(self,filename=str(Path.home() / "configurations_default.xml")):
        QObject.__init__(self)
        self.config_filename:str = filename
        self.configurations:List[Configuration] = []
        self.read_configurations()
        
    def save_configurations(self):
        self.write_configuration(self.config_filename)

    def write_configuration(self,filename):
        self.config_xml_tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)

    def read_configurations(self):
        if(os.path.isfile(self.config_filename)==False):
            utils_config.generate_default_configuration(self.config_filename)
        self.config_xml_tree = ET.parse(self.config_filename) # type: ignore
        self.config_xml_tree_root = self.config_xml_tree.getroot()
        self.num_configurations = 0
        for mode in self.config_xml_tree_root.iter('mode'):
            self.num_configurations = self.num_configurations + 1
            self.configurations.append(
                Configuration(
                    mode_id = mode.get('ID'),
                    name = mode.get('Name'),
                    exposure_time = float(mode.get('ExposureTime')),
                    analog_gain = float(mode.get('AnalogGain')),
                    illumination_source = int(mode.get('IlluminationSource')),
                    illumination_intensity = float(mode.get('IlluminationIntensity')),
                    camera_sn = mode.get('CameraSN'))
            )

    def update_configuration(self,configuration_id,attribute_name,new_value):
        list = self.config_xml_tree_root.xpath("//mode[contains(@ID," + "'" + str(configuration_id) + "')]")
        mode_to_update = list[0]
        mode_to_update.set(attribute_name,str(new_value))
        self.save_configurations()
