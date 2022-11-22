# qt libraries
from qtpy.QtCore import Signal, Qt # type: ignore
from qtpy.QtWidgets import QFrame, QComboBox, QDoubleSpinBox, QPushButton, QSlider, QGridLayout, QLabel, QVBoxLayout

import time

from control._def import *
from control.core import Configuration, LiveController, ConfigurationManager, StreamHandler
from control.typechecker import TypecheckFunction

from typing import Optional, Union, List, Tuple

# 'Live' button text
LIVE_BUTTON_IDLE_TEXT="Start Live"
LIVE_BUTTON_RUNNING_TEXT="Stop Live"

class LiveControlWidget(QFrame):
    signal_newExposureTime = Signal(float)
    signal_newAnalogGain = Signal(float)

    @property
    def fps_trigger(self)->float:
        return self.liveController.fps_trigger

    def __init__(self, 
        streamHandler:StreamHandler, 
        liveController:LiveController,
        configurationManager:ConfigurationManager, 
        show_trigger_options:bool=True
    ):
        super().__init__()
        self.liveController = liveController
        self.streamHandler = streamHandler
        self.configurationManager = configurationManager
        
        self.triggerMode = TriggerMode.SOFTWARE
        # note that this references the object in self.configurationManager.configurations
        self.currentConfiguration:Configuration = self.configurationManager.configurations[0]

        self.add_components(show_trigger_options)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.update_microscope_mode_by_name(self.currentConfiguration.name)

        self.is_switching_mode = False # flag used to prevent from settings being set by twice - from both mode change slot and value change slot; another way is to use blockSignals(True)

    @TypecheckFunction
    def add_components(self,
        show_trigger_options:bool
    ):
        # line 0: trigger mode
        self.triggerMode = None
        self.dropdown_triggerManu = QComboBox()
        self.dropdown_triggerManu.addItems([mode.value for mode in TriggerMode])

        # line 1: fps
        self.entry_triggerFPS = QDoubleSpinBox()
        self.entry_triggerFPS.setMinimum(0.02)
        self.entry_triggerFPS.setMaximum(1000)
        self.entry_triggerFPS.setSingleStep(1)
        self.entry_triggerFPS.setValue(self.fps_trigger)

        # line 2: choose microscope mode / toggle live mode 
        self.dropdown_modeSelection = QComboBox()
        for microscope_configuration in self.configurationManager.configurations:
            self.dropdown_modeSelection.addItems([microscope_configuration.name])
        self.dropdown_modeSelection.setCurrentText(self.currentConfiguration.name)

        self.btn_live = QPushButton(LIVE_BUTTON_IDLE_TEXT)
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(False)
        self.btn_live.setDefault(False)
        self.btn_live.setToolTip("""
            start/stop live image view

            displays each image that is recorded by the camera

            useful for manual investigation of a plate and/or imaging settings. Note that this can lead to strong photobleaching. Consider using the snapshot button instead (labelled 'snap')
        """)

        self.btn_snap=QPushButton("snap")
        self.btn_snap.setToolTip("take single image (minimizes bleaching for manual testing)")

        # line 3: exposure time and analog gain associated with the current mode
        self.entry_exposureTime = QDoubleSpinBox()
        self.entry_exposureTime.setMinimum(self.liveController.camera.EXPOSURE_TIME_MS_MIN) 
        self.entry_exposureTime.setMaximum(self.liveController.camera.EXPOSURE_TIME_MS_MAX) 
        self.entry_exposureTime.setSingleStep(1)
        self.entry_exposureTime.setValue(0)

        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain.setMinimum(0) 
        self.entry_analogGain.setMaximum(24) 
        self.entry_analogGain.setSingleStep(0.1)
        self.entry_analogGain.setValue(0)

        self.slider_illuminationIntensity = QSlider(Qt.Horizontal)
        self.slider_illuminationIntensity.setTickPosition(QSlider.TicksBelow)
        self.slider_illuminationIntensity.setMinimum(0)
        self.slider_illuminationIntensity.setMaximum(100)
        self.slider_illuminationIntensity.setValue(100)
        self.slider_illuminationIntensity.setSingleStep(1)
        self.slider_illuminationIntensity.setTickInterval(5)

        self.entry_illuminationIntensity = QDoubleSpinBox()
        self.entry_illuminationIntensity.setMinimum(0.1)
        self.entry_illuminationIntensity.setMaximum(100)
        self.entry_illuminationIntensity.setSingleStep(0.1)
        self.entry_illuminationIntensity.setValue(100)
        
        # connections
        self.entry_triggerFPS.valueChanged.connect(self.liveController.set_trigger_fps)
        self.dropdown_modeSelection.currentTextChanged.connect(self.update_microscope_mode_by_name)
        self.dropdown_triggerManu.currentIndexChanged.connect(self.update_trigger_mode)
        self.btn_live.clicked.connect(self.toggle_live)
        self.btn_snap.clicked.connect(self.take_snapshot)
        self.entry_exposureTime.valueChanged.connect(self.update_config_exposure_time)
        self.entry_analogGain.valueChanged.connect(self.update_config_analog_gain)
        self.entry_illuminationIntensity.valueChanged.connect(self.update_config_illumination_intensity)
        self.entry_illuminationIntensity.valueChanged.connect(lambda v:self.slider_illuminationIntensity.setValue(int(v))) # slider does not take float values
        self.slider_illuminationIntensity.valueChanged.connect(lambda v:self.entry_illuminationIntensity.setValue(float(v))) # doublespinbox does not take ints

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('Trigger Mode'), 0,0)
        grid_line0.addWidget(self.dropdown_triggerManu, 0,1)
        grid_line0.addWidget(QLabel('Trigger FPS'), 0,2)
        grid_line0.addWidget(self.entry_triggerFPS, 0,3)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Imaging Mode'), 0,0)
        grid_line1.addWidget(self.dropdown_modeSelection, 0,1)
        grid_line1.addWidget(self.btn_live, 0,2)
        grid_line1.addWidget(self.btn_snap, 0,3)

        grid_line2 = QGridLayout()

        exposure_time_label=QLabel('Exposure Time (ms)')
        exposure_time_tooltip="exposure time is the time the camera sensor records an image. Higher exposure time means more time to record light emitted from a sample, which also increases bleaching (the light source is activate as long as the camera sensor records the light)"
        exposure_time_label.setToolTip(exposure_time_tooltip)
        self.entry_exposureTime.setToolTip(exposure_time_tooltip)
        grid_line2.addWidget(exposure_time_label, 0,0)
        grid_line2.addWidget(self.entry_exposureTime, 0,1)
        analog_gain_label=QLabel('Analog Gain')
        analog_gain_tooltip="analog gain increases the camera sensor sensitiviy. Higher gain will make the image look brighter so that a lower exposure time can be used, but also introduces more noise."
        analog_gain_label.setToolTip(analog_gain_tooltip)
        self.entry_analogGain.setToolTip(analog_gain_tooltip)
        grid_line2.addWidget(analog_gain_label, 0,2)
        grid_line2.addWidget(self.entry_analogGain, 0,3)

        grid_line4 = QGridLayout()
        grid_line4.addWidget(QLabel('Illumination'), 0,0)
        grid_line4.addWidget(self.slider_illuminationIntensity, 0,1)
        grid_line4.addWidget(self.entry_illuminationIntensity, 0,2)

        self.grid = QVBoxLayout()
        if show_trigger_options:
            self.grid.addLayout(grid_line0)
        self.grid.addLayout(grid_line1)
        self.grid.addLayout(grid_line2)
        self.grid.addLayout(grid_line4)
        self.grid.addStretch()
        self.setLayout(self.grid)

    @TypecheckFunction
    def take_snapshot(self,_pressed:Any=None):
        """ take a snapshot (more precisely, request a snapshot) """
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
        self.is_switching_mode = False

    @TypecheckFunction
    def update_trigger_mode(self):
        self.liveController.set_trigger_mode(self.dropdown_triggerManu.currentText())

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
    def set_microscope_mode(self,config:Configuration):
        # self.liveController.set_microscope_mode(config)
        self.dropdown_modeSelection.setCurrentText(config.name)

    @TypecheckFunction
    def set_trigger_mode(self,trigger_mode:str):
        self.dropdown_triggerManu.setCurrentText(trigger_mode)
        self.liveController.set_trigger_mode(self.dropdown_triggerManu.currentText())
