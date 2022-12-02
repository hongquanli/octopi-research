# qt libraries
from qtpy.QtCore import Signal, Qt # type: ignore
from qtpy.QtWidgets import QFrame, QComboBox, QDoubleSpinBox, QPushButton, QSlider, QGridLayout, QLabel, QVBoxLayout, QFileDialog

import time

from control._def import *
from control.core import Configuration, LiveController, ConfigurationManager, StreamHandler
from control.typechecker import TypecheckFunction
from control.gui import *

from typing import Optional, Union, List, Tuple

# 'Live' button text
LIVE_BUTTON_IDLE_TEXT="Start Live"
LIVE_BUTTON_RUNNING_TEXT="Stop Live"

LIVE_BUTTON_TOOLTIP="""start/stop live image view

displays each image that is recorded by the camera

useful for manual investigation of a plate and/or imaging settings. Note that this can lead to strong photobleaching. Consider using the snapshot button instead (labelled 'snap')"""
BTN_SNAP_TOOLTIP="take single image (minimizes bleaching for manual testing)"

exposure_time_tooltip="exposure time is the time the camera sensor records an image. Higher exposure time means more time to record light emitted from a sample, which also increases bleaching (the light source is activate as long as the camera sensor records the light)"
analog_gain_tooltip="analog gain increases the camera sensor sensitiviy. Higher gain will make the image look brighter so that a lower exposure time can be used, but also introduces more noise."
channel_offset_tooltip="channel specific z offset used in multipoint acquisition to focus properly in channels that are not in focus at the same time the nucleus is (given the nucleus is the channel that is used for focusing)"

CAMERA_PIXEL_FORMAT_TOOLTIP="camera pixel format\n\nMONO8 means monochrome (grey-scale) 8bit\nMONO12 means monochrome 12bit\n\nmore bits can capture more detail (8bit can capture 2^8 intensity values, 12bit can capture 2^12), but also increase file size"

class LiveControlWidget(QFrame):
    signal_newExposureTime = Signal(float)
    signal_newAnalogGain = Signal(float)

    @property
    def fps_trigger(self)->float:
        return self.liveController.fps_trigger

    def __init__(self, 
        streamHandler:StreamHandler, 
        liveController:LiveController,
        configurationManager:ConfigurationManager
    ):
        super().__init__()
        self.liveController = liveController
        self.streamHandler = streamHandler
        self.configurationManager = configurationManager
        
        self.triggerMode = TriggerMode.SOFTWARE
        # note that this references the object in self.configurationManager.configurations
        self.currentConfiguration:Configuration = self.configurationManager.configurations[0]

        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.update_microscope_mode_by_name(self.currentConfiguration.name)

        self.is_switching_mode = False # flag used to prevent from settings being set by twice - from both mode change slot and value change slot; another way is to use blockSignals(True)

    def add_components(self):
        # line 0: trigger mode
        trigger_mode_name_list=[mode.value for mode in TriggerMode]
        self.dropdown_triggerMenu = Dropdown(trigger_mode_name_list,
            current_index=trigger_mode_name_list.index(self.triggerMode.value),
            on_currentIndexChanged=self.update_trigger_mode
        ).widget

        # line 1: fps
        self.entry_triggerFPS = SpinBoxDouble(minimum=0.02,maximum=100.0,step=1.0,default=self.fps_trigger,
            on_valueChanged=self.liveController.set_trigger_fps
        ).widget

        # line 2: choose microscope mode / toggle live mode
        configuration_name_list=[microscope_configuration.name for microscope_configuration in self.configurationManager.configurations]
        self.dropdown_modeSelection = Dropdown(
            configuration_name_list,
            current_index=configuration_name_list.index(self.currentConfiguration.name),
            on_currentTextChanged=self.update_microscope_mode_by_name
        ).widget

        self.btn_live=Button(LIVE_BUTTON_IDLE_TEXT,checkable=True,checked=False,default=False,tooltip=LIVE_BUTTON_TOOLTIP,on_clicked=self.toggle_live).widget

        self.btn_snap=Button("Snap",tooltip=BTN_SNAP_TOOLTIP,on_clicked=self.take_snapshot).widget

        # line 3: exposure time and analog gain associated with the current mode
        self.entry_exposureTime = SpinBoxDouble(
            minimum=self.liveController.camera.EXPOSURE_TIME_MS_MIN,
            maximum=self.liveController.camera.EXPOSURE_TIME_MS_MAX,step=1.0,default=0.0,
            tooltip=exposure_time_tooltip,
            on_valueChanged=self.update_config_exposure_time
        ).widget

        self.entry_analogGain = SpinBoxDouble(
            minimum=0.0,maximum=24.0,step=0.1,default=0.0,tooltip=analog_gain_tooltip,
            on_valueChanged=self.update_config_analog_gain
        ).widget

        self.entry_channelOffset=SpinBoxDouble(
            minimum=-30.0,maximum=30.0,step=0.1,default=0.0,tooltip=channel_offset_tooltip,
            on_valueChanged=self.update_config_channel_offset
        ).widget

        self.entry_illuminationIntensity = SpinBoxDouble(
            minimum=0.1,maximum=100.0,step=0.1,default=100.0,
            on_valueChanged=self.update_config_illumination_intensity
        ).widget

        self.save_illuminationConfig=Button("save config",on_clicked=self.save_illumination_config).widget
        self.load_illuminationConfig=Button("load config",on_clicked=self.load_illumination_config).widget

        exposure_time_label=Label('Exposure Time (ms)',tooltip=exposure_time_tooltip).widget

        analog_gain_label=Label('Analog Gain',tooltip=analog_gain_tooltip).widget

        channel_offset_label=Label("Offset (µm)",tooltip=channel_offset_tooltip).widget

        image_formats=['MONO8','MONO12']
        self.camera_pixel_format_widget=Dropdown(image_formats,
            current_index=0, # default pixel format is 8 bits
            tooltip=CAMERA_PIXEL_FORMAT_TOOLTIP,
            on_currentIndexChanged=lambda index:self.liveController.camera.set_pixel_format(image_formats[index])
        ).widget

        self.grid = VBox(
            Grid([ # general camera settings
                Label('pixel format',tooltip=CAMERA_PIXEL_FORMAT_TOOLTIP).widget, 
                self.camera_pixel_format_widget,
                QLabel('Trigger Mode'), 
                self.dropdown_triggerMenu, 
            ]).layout,
            Grid([ # start live imaging
                self.btn_live,
                self.btn_snap,
                Label('FPS',tooltip="take this many images per second.\n\nNote that the FPS is practially capped by the exposure time. A warning message will be printed in the terminal if the actual number of images per second does not match the requested number.").widget,
                self.entry_triggerFPS,
            ]).layout,
            Grid([ # change imaging channel, to view settings and at the same time take an image of that channel
                QLabel('Imaging Mode'),
                self.dropdown_modeSelection,
            ]).layout,
            Grid([ # channel settings 1/2
                exposure_time_label,
                self.entry_exposureTime,
                analog_gain_label,
                self.entry_analogGain,
                channel_offset_label,
                self.entry_channelOffset,
            ]).layout,
            Grid([ # channel settings 2/2, plus buttons to save/load configuration for all channels
                QLabel('Illumination'),
                self.entry_illuminationIntensity,
                self.save_illuminationConfig,
                self.load_illuminationConfig,
            ]).layout,
        ).layout
        self.grid.addStretch()
        self.setLayout(self.grid)

    def save_illumination_config(self,_button_state:bool):
        """ save illumination configuration to a file (GUI callback) """

        dialog=QFileDialog(options=QFileDialog.DontUseNativeDialog)
        dialog.setWindowModality(Qt.ApplicationModal)
        save_path=dialog.getSaveFileName(caption="Save current illumination config where?")[0]

        if save_path!="":
            if not save_path.endswith(".json"):
                save_path=save_path+".json"
            print(f"saving config to {save_path}")
            self.configurationManager.write_configuration(save_path)

    def load_illumination_config(self,_button_state:bool):
        """ load illumination configuration from a file (GUI callback) """

        if self.liveController.camera.is_live:
            print("! warning: cannot load illumination settings while live !")
            return
        
        dialog=QFileDialog(options=QFileDialog.DontUseNativeDialog)
        dialog.setWindowModality(Qt.ApplicationModal)
        load_path=dialog.getOpenFileName(caption="Load which illumination config?",filter="JSON (*.json)")[0]

        if load_path!="":
            print(f"loading config from {load_path}")
            self.configurationManager.read_configurations(load_path)
            self.update_microscope_mode_by_name(self.liveController.currentConfiguration.name)

    @TypecheckFunction
    def take_snapshot(self,_pressed:Any=None):
        """ take a snapshot (more precisely, request a snapshot) """
        self.liveController.set_microscope_mode(self.currentConfiguration)
        self.liveController.camera.is_live=True
        self.liveController.stream_handler.signal_new_frame_received.connect(self.snap_end)
        self.liveController.camera.start_streaming()
        if self.liveController.for_displacement_measurement:
            self.liveController.microcontroller.turn_on_AF_laser()
        self.liveController.trigger_acquisition()

    @TypecheckFunction
    def snap_end(self,_discard:Any=None):
        """ clean up after snapshot was recorded """
        self.liveController.stream_handler.signal_new_frame_received.disconnect(self.snap_end)
        if self.liveController.for_displacement_measurement:
            self.liveController.microcontroller.turn_off_AF_laser()
        self.liveController.camera.is_live=False

    @TypecheckFunction
    def toggle_live(self,pressed:bool):
        if pressed:
            self.liveController.set_microscope_mode(self.currentConfiguration)
            self.btn_live.setText(LIVE_BUTTON_RUNNING_TEXT)
            self.liveController.start_live()
            self.btn_snap.setDisabled(True)
        else:
            self.btn_live.setText(LIVE_BUTTON_IDLE_TEXT)
            self.liveController.stop_live()
            self.btn_snap.setDisabled(False)

    @TypecheckFunction
    def update_camera_settings(self):
        self.signal_newAnalogGain.emit(self.entry_analogGain.value())
        self.signal_newExposureTime.emit(self.entry_exposureTime.value())

    @TypecheckFunction
    def update_microscope_mode_by_name(self,current_microscope_mode_name:str):
        self.is_switching_mode = True
        # identify the mode selected (note that this references the object in self.configurationManager.configurations)
        self.currentConfiguration = [config for config in self.configurationManager.configurations if config.name == current_microscope_mode_name][0]
        # update the microscope to the current configuration
        self.liveController.set_microscope_mode(self.currentConfiguration)
        # update the exposure time and analog gain settings according to the selected configuration
        self.entry_exposureTime.setValue(self.currentConfiguration.exposure_time)
        self.entry_analogGain.setValue(self.currentConfiguration.analog_gain)
        self.entry_illuminationIntensity.setValue(self.currentConfiguration.illumination_intensity)
        self.entry_channelOffset.setValue(self.currentConfiguration.channel_z_offset)
        self.is_switching_mode = False

    @TypecheckFunction
    def update_trigger_mode(self):
        self.liveController.set_trigger_mode(self.dropdown_triggerMenu.currentText())

    @TypecheckFunction
    def update_config_exposure_time(self,new_value:float):
        if self.is_switching_mode == False:
            self.currentConfiguration.exposure_time = new_value
            self.configurationManager.update_configuration(self.currentConfiguration.id,'ExposureTime',new_value)
            self.signal_newExposureTime.emit(new_value)

    @TypecheckFunction
    def update_config_analog_gain(self,new_value:float):
        if self.is_switching_mode == False:
            self.currentConfiguration.analog_gain = new_value
            self.configurationManager.update_configuration(self.currentConfiguration.id,'AnalogGain',new_value)
            self.signal_newAnalogGain.emit(new_value)

    @TypecheckFunction
    def update_config_illumination_intensity(self,new_value:float):
        if self.is_switching_mode == False:
            self.currentConfiguration.illumination_intensity = new_value
            self.configurationManager.update_configuration(self.currentConfiguration.id,'IlluminationIntensity',new_value)
            self.liveController.set_illumination(self.currentConfiguration.illumination_source, self.currentConfiguration.illumination_intensity)

    @TypecheckFunction
    def update_config_channel_offset(self,new_value:float):
        if self.is_switching_mode == False:
            self.currentConfiguration.channel_z_offset = new_value
            self.configurationManager.update_configuration(self.currentConfiguration.id,'RelativeZOffsetUM',new_value)

    @TypecheckFunction
    def set_microscope_mode(self,config:Configuration):
        self.dropdown_modeSelection.setCurrentText(config.name)

    @TypecheckFunction
    def set_trigger_mode(self,trigger_mode:str):
        self.dropdown_triggerMenu.setCurrentText(trigger_mode)
        self.liveController.set_trigger_mode(self.dropdown_triggerMenu.currentText())
