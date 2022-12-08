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
        self.liveController.set_microscope_mode(self.currentConfiguration)

        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.is_switching_mode = False # flag used to prevent from settings being set by twice - from both mode change slot and value change slot; another way is to use blockSignals(True)

    def add_components(self):
        # line 0: trigger mode
        trigger_mode_name_list=[mode.value for mode in TriggerMode]
        self.dropdown_triggerMenu = Dropdown(trigger_mode_name_list,
            current_index=trigger_mode_name_list.index(self.triggerMode.value),
            on_currentIndexChanged=self.update_trigger_mode
        ).widget

        self.entry_triggerFPS = SpinBoxDouble(minimum=0.02,maximum=100.0,step=1.0,default=self.fps_trigger,
            on_valueChanged=self.liveController.set_trigger_fps
        ).widget

        self.btn_live=Button(LIVE_BUTTON_IDLE_TEXT,checkable=True,checked=False,default=False,tooltip=LIVE_BUTTON_TOOLTIP,on_clicked=self.toggle_live).widget

        image_formats=list(self.liveController.camera.camera.PixelFormat.get_range().keys())
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
                Label('FPS',tooltip="take this many images per second.\n\nNote that the FPS is practially capped by the exposure time. A warning message will be printed in the terminal if the actual number of images per second does not match the requested number.").widget,
                self.entry_triggerFPS,
            ]).layout,
        ).layout
        self.grid.addStretch()
        self.setLayout(self.grid)

    @TypecheckFunction
    def toggle_live(self,pressed:bool):
        if pressed:
            self.liveController.set_microscope_mode(self.currentConfiguration)
            self.btn_live.setText(LIVE_BUTTON_RUNNING_TEXT)
            self.liveController.start_live()
        else:
            self.btn_live.setText(LIVE_BUTTON_IDLE_TEXT)
            self.liveController.stop_live()

    @TypecheckFunction
    def update_camera_settings(self):
        self.signal_newAnalogGain.emit(self.configurationManager.configurations[0].analog_gain)
        self.signal_newExposureTime.emit(self.configurationManager.configurations[0].exposure_time)

    @TypecheckFunction
    def update_trigger_mode(self):
        self.liveController.set_trigger_mode(self.dropdown_triggerMenu.currentText())

    @TypecheckFunction
    def set_trigger_mode(self,trigger_mode:str):
        self.dropdown_triggerMenu.setCurrentText(trigger_mode)
        self.update_trigger_mode()

    @TypecheckFunction
    def set_microscope_mode(self,config:Configuration):
        self.dropdown_modeSelection.setCurrentText(config.name)
