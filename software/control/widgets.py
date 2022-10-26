# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import pyqtgraph as pg

from datetime import datetime

from control._def import *

class CameraSettingsWidget(QFrame):

    signal_camera_set_temperature = Signal(float)

    def __init__(self, camera, include_gain_exposure_time = True, include_camera_temperature_setting = False, main=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.camera = camera
        self.add_components(include_gain_exposure_time,include_camera_temperature_setting)        
        # set frame style
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self,include_gain_exposure_time,include_camera_temperature_setting):

        # add buttons and input fields
        self.entry_exposureTime = QDoubleSpinBox()
        self.entry_exposureTime.setMinimum(self.camera.EXPOSURE_TIME_MS_MIN) 
        self.entry_exposureTime.setMaximum(self.camera.EXPOSURE_TIME_MS_MAX) 
        self.entry_exposureTime.setSingleStep(1)
        self.entry_exposureTime.setValue(20)
        self.camera.set_exposure_time(20)

        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain.setMinimum(self.camera.GAIN_MIN) 
        self.entry_analogGain.setMaximum(self.camera.GAIN_MAX) 
        self.entry_analogGain.setSingleStep(self.camera.GAIN_STEP)
        self.entry_analogGain.setValue(0)
        self.camera.set_analog_gain(0)

        self.dropdown_pixelFormat = QComboBox()
        self.dropdown_pixelFormat.addItems(['MONO8','MONO12','MONO14','MONO16','BAYER_RG8','BAYER_RG12'])
        if self.camera.pixel_format is not None:
            self.dropdown_pixelFormat.setCurrentText(self.camera.pixel_format)
        # to do: load and save pixel format in configurations

        self.entry_ROI_offset_x = QSpinBox()
        self.entry_ROI_offset_x.setValue(CAMERA.ROI_OFFSET_X_DEFAULT)
        self.entry_ROI_offset_x.setFixedWidth(40)
        self.entry_ROI_offset_x.setMinimum(-1500)
        self.entry_ROI_offset_x.setMaximum(1500)
        self.entry_ROI_offset_x.setKeyboardTracking(False)
        self.entry_ROI_offset_y = QSpinBox()
        self.entry_ROI_offset_y.setValue(CAMERA.ROI_OFFSET_Y_DEFAULT)
        self.entry_ROI_offset_y.setFixedWidth(40)
        self.entry_ROI_offset_y.setMinimum(-1500)
        self.entry_ROI_offset_y.setMaximum(1500)
        self.entry_ROI_offset_y.setKeyboardTracking(False)
        self.entry_ROI_width = QSpinBox()
        self.entry_ROI_width.setMaximum(4000)
        self.entry_ROI_width.setValue(CAMERA.ROI_WIDTH_DEFAULT)
        self.entry_ROI_width.setFixedWidth(60)
        self.entry_ROI_width.setKeyboardTracking(False)
        self.entry_ROI_height = QSpinBox()
        self.entry_ROI_height.setMaximum(3000)
        self.entry_ROI_height.setValue(CAMERA.ROI_HEIGHT_DEFAULT)
        self.entry_ROI_height.setFixedWidth(60)
        self.entry_ROI_height.setKeyboardTracking(False)
        self.entry_temperature = QDoubleSpinBox()
        self.entry_temperature.setMaximum(25)
        self.entry_temperature.setMinimum(-50)
        self.entry_temperature.setDecimals(1)
        self.label_temperature_measured = QLabel()
        # self.label_temperature_measured.setNum(0)
        self.label_temperature_measured.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        # connection
        self.entry_exposureTime.valueChanged.connect(self.camera.set_exposure_time)
        self.entry_analogGain.valueChanged.connect(self.camera.set_analog_gain)
        self.dropdown_pixelFormat.currentTextChanged.connect(self.camera.set_pixel_format)
        self.entry_ROI_offset_x.valueChanged.connect(self.set_ROI)
        self.entry_ROI_offset_y.valueChanged.connect(self.set_ROI)
        self.entry_ROI_height.valueChanged.connect(self.set_ROI)
        self.entry_ROI_width.valueChanged.connect(self.set_ROI)
        self.entry_temperature.valueChanged.connect(self.signal_camera_set_temperature.emit)

        # layout
        grid_ctrl = QGridLayout()
        if include_gain_exposure_time:
            grid_ctrl.addWidget(QLabel('Exposure Time (ms)'), 0,0)
            grid_ctrl.addWidget(self.entry_exposureTime, 0,1)
            grid_ctrl.addWidget(QLabel('Analog Gain'), 1,0)
            grid_ctrl.addWidget(self.entry_analogGain, 1,1)
        grid_ctrl.addWidget(QLabel('Pixel Format'), 2,0)
        grid_ctrl.addWidget(self.dropdown_pixelFormat, 2,1)
        if include_camera_temperature_setting:
            grid_ctrl.addWidget(QLabel('Set Temperature (C)'),3,0)
            grid_ctrl.addWidget(self.entry_temperature,3,1)
            grid_ctrl.addWidget(QLabel('Actual Temperature (C)'),3,2)
            grid_ctrl.addWidget(self.label_temperature_measured,3,3)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(QLabel('ROI'))
        hbox1.addStretch()
        hbox1.addWidget(QLabel('height'))
        hbox1.addWidget(self.entry_ROI_height)
        hbox1.addWidget(QLabel('width'))
        hbox1.addWidget(self.entry_ROI_width)
        
        hbox1.addWidget(QLabel('offset y'))
        hbox1.addWidget(self.entry_ROI_offset_y)
        hbox1.addWidget(QLabel('offset x'))
        hbox1.addWidget(self.entry_ROI_offset_x)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_ctrl,0,0)
        self.grid.addLayout(hbox1,1,0)
        self.setLayout(self.grid)

    def set_exposure_time(self,exposure_time):
        self.entry_exposureTime.setValue(exposure_time)

    def set_analog_gain(self,analog_gain):
        self.entry_analogGain.setValue(analog_gain)

    def set_ROI(self):
    	self.camera.set_ROI(self.entry_ROI_offset_x.value(),self.entry_ROI_offset_y.value(),self.entry_ROI_width.value(),self.entry_ROI_height.value())

    def update_measured_temperature(self,temperature):
        self.label_temperature_measured.setNum(temperature)

class LiveControlWidget(QFrame):
    signal_newExposureTime = Signal(float)
    signal_newAnalogGain = Signal(float)
    signal_autoLevelSetting = Signal(bool)
    def __init__(self, streamHandler, liveController, configurationManager=None, show_trigger_options=True, show_display_options=True, show_autolevel = False, autolevel=False, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.liveController = liveController
        self.streamHandler = streamHandler
        self.configurationManager = configurationManager
        self.fps_trigger = 10
        self.fps_display = 10
        self.liveController.set_trigger_fps(self.fps_trigger)
        self.streamHandler.set_display_fps(self.fps_display)
        
        self.triggerMode = TriggerMode.SOFTWARE
        # note that this references the object in self.configurationManager.configurations
        self.currentConfiguration = self.configurationManager.configurations[0]

        self.add_components(show_trigger_options,show_display_options,show_autolevel,autolevel)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.update_microscope_mode_by_name(self.currentConfiguration.name)

        self.is_switching_mode = False # flag used to prevent from settings being set by twice - from both mode change slot and value change slot; another way is to use blockSignals(True)

    def add_components(self,show_trigger_options,show_display_options,show_autolevel,autolevel):
        # line 0: trigger mode
        self.triggerMode = None
        self.dropdown_triggerManu = QComboBox()
        self.dropdown_triggerManu.addItems([TriggerMode.SOFTWARE,TriggerMode.HARDWARE,TriggerMode.CONTINUOUS])

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

        self.btn_live = QPushButton("Live")
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(False)
        self.btn_live.setDefault(False)

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
        self.slider_illuminationIntensity.setSingleStep(0.1)

        self.entry_illuminationIntensity = QDoubleSpinBox()
        self.entry_illuminationIntensity.setMinimum(0.1) 
        self.entry_illuminationIntensity.setMaximum(100) 
        self.entry_illuminationIntensity.setSingleStep(0.1)
        self.entry_illuminationIntensity.setValue(100)

        # line 4: display fps and resolution scaling
        self.entry_displayFPS = QDoubleSpinBox()
        self.entry_displayFPS.setMinimum(1) 
        self.entry_displayFPS.setMaximum(240) 
        self.entry_displayFPS.setSingleStep(1)
        self.entry_displayFPS.setValue(self.fps_display)

        self.slider_resolutionScaling = QSlider(Qt.Horizontal)
        self.slider_resolutionScaling.setTickPosition(QSlider.TicksBelow)
        self.slider_resolutionScaling.setMinimum(10)
        self.slider_resolutionScaling.setMaximum(100)
        self.slider_resolutionScaling.setValue(DEFAULT_DISPLAY_CROP)
        self.slider_resolutionScaling.setSingleStep(10)

        # autolevel
        self.btn_autolevel = QPushButton('Autolevel')
        self.btn_autolevel.setCheckable(True)
        self.btn_autolevel.setChecked(autolevel)
        
        # connections
        self.entry_triggerFPS.valueChanged.connect(self.liveController.set_trigger_fps)
        self.entry_displayFPS.valueChanged.connect(self.streamHandler.set_display_fps)
        self.slider_resolutionScaling.valueChanged.connect(self.streamHandler.set_display_resolution_scaling)
        self.slider_resolutionScaling.valueChanged.connect(self.liveController.set_display_resolution_scaling)
        self.dropdown_modeSelection.currentTextChanged.connect(self.update_microscope_mode_by_name)
        self.dropdown_triggerManu.currentIndexChanged.connect(self.update_trigger_mode)
        self.btn_live.clicked.connect(self.toggle_live)
        self.entry_exposureTime.valueChanged.connect(self.update_config_exposure_time)
        self.entry_analogGain.valueChanged.connect(self.update_config_analog_gain)
        self.entry_illuminationIntensity.valueChanged.connect(self.update_config_illumination_intensity)
        self.entry_illuminationIntensity.valueChanged.connect(self.slider_illuminationIntensity.setValue)
        self.slider_illuminationIntensity.valueChanged.connect(self.entry_illuminationIntensity.setValue)
        self.btn_autolevel.clicked.connect(self.signal_autoLevelSetting.emit)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('Trigger Mode'), 0,0)
        grid_line0.addWidget(self.dropdown_triggerManu, 0,1)
        grid_line0.addWidget(QLabel('Trigger FPS'), 0,2)
        grid_line0.addWidget(self.entry_triggerFPS, 0,3)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Microscope Configuration'), 0,0)
        grid_line1.addWidget(self.dropdown_modeSelection, 0,1)
        grid_line1.addWidget(self.btn_live, 0,2)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Exposure Time (ms)'), 0,0)
        grid_line2.addWidget(self.entry_exposureTime, 0,1)
        grid_line2.addWidget(QLabel('Analog Gain'), 0,2)
        grid_line2.addWidget(self.entry_analogGain, 0,3)

        grid_line4 = QGridLayout()
        grid_line4.addWidget(QLabel('Illumination'), 0,0)
        grid_line4.addWidget(self.slider_illuminationIntensity, 0,1)
        grid_line4.addWidget(self.entry_illuminationIntensity, 0,2)

        grid_line3 = QGridLayout()
        grid_line3.addWidget(QLabel('Display FPS'), 0,0)
        grid_line3.addWidget(self.entry_displayFPS, 0,1)
        grid_line3.addWidget(QLabel('Display Resolution'), 0,2)
        grid_line3.addWidget(self.slider_resolutionScaling,0,3)
        if show_autolevel:
            grid_line3.addWidget(self.btn_autolevel,0,4)

        self.grid = QVBoxLayout()
        if show_trigger_options:
            self.grid.addLayout(grid_line0)
        self.grid.addLayout(grid_line1)
        self.grid.addLayout(grid_line2)
        self.grid.addLayout(grid_line4)
        if show_display_options:
            self.grid.addLayout(grid_line3)
        self.grid.addStretch()
        self.setLayout(self.grid)

    def toggle_live(self,pressed):
        if pressed:
            self.liveController.start_live()
        else:
            self.liveController.stop_live()

    def update_camera_settings(self):
        self.signal_newAnalogGain.emit(self.entry_analogGain.value())
        self.signal_newExposureTime.emit(self.entry_exposureTime.value())

    def update_microscope_mode_by_name(self,current_microscope_mode_name):
        self.is_switching_mode = True
        # identify the mode selected (note that this references the object in self.configurationManager.configurations)
        self.currentConfiguration = next((config for config in self.configurationManager.configurations if config.name == current_microscope_mode_name), None)
        # update the microscope to the current configuration
        self.liveController.set_microscope_mode(self.currentConfiguration)
        # update the exposure time and analog gain settings according to the selected configuration
        self.entry_exposureTime.setValue(self.currentConfiguration.exposure_time)
        self.entry_analogGain.setValue(self.currentConfiguration.analog_gain)
        self.entry_illuminationIntensity.setValue(self.currentConfiguration.illumination_intensity)
        self.is_switching_mode = False

    def update_trigger_mode(self):
        self.liveController.set_trigger_mode(self.dropdown_triggerManu.currentText())

    def update_config_exposure_time(self,new_value):
        if self.is_switching_mode == False:
            self.currentConfiguration.exposure_time = new_value
            self.configurationManager.update_configuration(self.currentConfiguration.id,'ExposureTime',new_value)
            self.signal_newExposureTime.emit(new_value)

    def update_config_analog_gain(self,new_value):
        if self.is_switching_mode == False:
            self.currentConfiguration.analog_gain = new_value
            self.configurationManager.update_configuration(self.currentConfiguration.id,'AnalogGain',new_value)
            self.signal_newAnalogGain.emit(new_value)

    def update_config_illumination_intensity(self,new_value):
        if self.is_switching_mode == False:
            self.currentConfiguration.illumination_intensity = new_value
            self.configurationManager.update_configuration(self.currentConfiguration.id,'IlluminationIntensity',new_value)
            self.liveController.set_illumination(self.currentConfiguration.illumination_source, self.currentConfiguration.illumination_intensity)

    def set_microscope_mode(self,config):
        # self.liveController.set_microscope_mode(config)
        self.dropdown_modeSelection.setCurrentText(config.name)

    def set_trigger_mode(self,trigger_mode):
        self.dropdown_triggerManu.setCurrentText(trigger_mode)
        self.liveController.set_trigger_mode(self.dropdown_triggerManu.currentText())

class RecordingWidget(QFrame):
    def __init__(self, streamHandler, imageSaver, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imageSaver = imageSaver # for saving path control
        self.streamHandler = streamHandler
        self.base_path_is_set = False
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')

        self.lineEdit_savingDir.setText(DEFAULT_SAVING_PATH)
        self.imageSaver.set_base_path(DEFAULT_SAVING_PATH)

        self.lineEdit_experimentID = QLineEdit()

        self.entry_saveFPS = QDoubleSpinBox()
        self.entry_saveFPS.setMinimum(0.02) 
        self.entry_saveFPS.setMaximum(1000) 
        self.entry_saveFPS.setSingleStep(1)
        self.entry_saveFPS.setValue(1)
        self.streamHandler.set_save_fps(1)

        self.entry_timeLimit = QSpinBox()
        self.entry_timeLimit.setMinimum(-1) 
        self.entry_timeLimit.setMaximum(60*60*24*30) 
        self.entry_timeLimit.setSingleStep(1)
        self.entry_timeLimit.setValue(-1)

        self.btn_record = QPushButton("Record")
        self.btn_record.setCheckable(True)
        self.btn_record.setChecked(False)
        self.btn_record.setDefault(False)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Saving Path'))
        grid_line1.addWidget(self.lineEdit_savingDir, 0,1)
        grid_line1.addWidget(self.btn_setSavingDir, 0,2)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Experiment ID'), 0,0)
        grid_line2.addWidget(self.lineEdit_experimentID,0,1)

        grid_line3 = QGridLayout()
        grid_line3.addWidget(QLabel('Saving FPS'), 0,0)
        grid_line3.addWidget(self.entry_saveFPS, 0,1)
        grid_line3.addWidget(QLabel('Time Limit (s)'), 0,2)
        grid_line3.addWidget(self.entry_timeLimit, 0,3)
        grid_line3.addWidget(self.btn_record, 0,4)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line1,0,0)
        self.grid.addLayout(grid_line2,1,0)
        self.grid.addLayout(grid_line3,2,0)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_record.clicked.connect(self.toggle_recording)
        self.entry_saveFPS.valueChanged.connect(self.streamHandler.set_save_fps)
        self.entry_timeLimit.valueChanged.connect(self.imageSaver.set_recording_time_limit)
        self.imageSaver.stop_recording.connect(self.stop_recording)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.imageSaver.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True

    def toggle_recording(self,pressed):
        if self.base_path_is_set == False:
            self.btn_record.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if pressed:
            self.lineEdit_experimentID.setEnabled(False)
            self.btn_setSavingDir.setEnabled(False)
            self.imageSaver.start_new_experiment(self.lineEdit_experimentID.text())
            self.streamHandler.start_recording()
        else:
            self.streamHandler.stop_recording()
            self.lineEdit_experimentID.setEnabled(True)
            self.btn_setSavingDir.setEnabled(True)

    # stop_recording can be called by imageSaver
    def stop_recording(self):
        self.lineEdit_experimentID.setEnabled(True)
        self.btn_record.setChecked(False)
        self.streamHandler.stop_recording()
        self.btn_setSavingDir.setEnabled(True)

class NavigationWidget(QFrame):
    def __init__(self, navigationController, slidePositionController=None, main=None, widget_configuration = 'full', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigationController = navigationController
        self.slidePositionController = slidePositionController
        self.widget_configuration = widget_configuration
        self.slide_position = None
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.label_Xpos = QLabel()
        self.label_Xpos.setNum(0)
        self.label_Xpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dX = QDoubleSpinBox()
        self.entry_dX.setMinimum(0) 
        self.entry_dX.setMaximum(25) 
        self.entry_dX.setSingleStep(0.2)
        self.entry_dX.setValue(0)
        self.entry_dX.setDecimals(3)
        self.entry_dX.setKeyboardTracking(False)
        self.btn_moveX_forward = QPushButton('Forward')
        self.btn_moveX_forward.setDefault(False)
        self.btn_moveX_backward = QPushButton('Backward')
        self.btn_moveX_backward.setDefault(False)

        self.btn_home_X = QPushButton('Home X')
        self.btn_home_X.setDefault(False)
        self.btn_home_X.setEnabled(HOMING_ENABLED_X)
        self.btn_zero_X = QPushButton('Zero X')
        self.btn_zero_X.setDefault(False)
        
        self.label_Ypos = QLabel()
        self.label_Ypos.setNum(0)
        self.label_Ypos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dY = QDoubleSpinBox()
        self.entry_dY.setMinimum(0)
        self.entry_dY.setMaximum(25)
        self.entry_dY.setSingleStep(0.2)
        self.entry_dY.setValue(0)
        self.entry_dY.setDecimals(3)
        self.entry_dY.setKeyboardTracking(False)
        self.btn_moveY_forward = QPushButton('Forward')
        self.btn_moveY_forward.setDefault(False)
        self.btn_moveY_backward = QPushButton('Backward')
        self.btn_moveY_backward.setDefault(False)

        self.btn_home_Y = QPushButton('Home Y')
        self.btn_home_Y.setDefault(False)
        self.btn_home_Y.setEnabled(HOMING_ENABLED_Y)
        self.btn_zero_Y = QPushButton('Zero Y')
        self.btn_zero_Y.setDefault(False)

        self.label_Zpos = QLabel()
        self.label_Zpos.setNum(0)
        self.label_Zpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dZ = QDoubleSpinBox()
        self.entry_dZ.setMinimum(0) 
        self.entry_dZ.setMaximum(1000) 
        self.entry_dZ.setSingleStep(0.2)
        self.entry_dZ.setValue(0)
        self.entry_dZ.setDecimals(3)
        self.entry_dZ.setKeyboardTracking(False)
        self.btn_moveZ_forward = QPushButton('Forward')
        self.btn_moveZ_forward.setDefault(False)
        self.btn_moveZ_backward = QPushButton('Backward')
        self.btn_moveZ_backward.setDefault(False)

        self.btn_home_Z = QPushButton('Home Z')
        self.btn_home_Z.setDefault(False)
        self.btn_home_Z.setEnabled(HOMING_ENABLED_Z)
        self.btn_zero_Z = QPushButton('Zero Z')
        self.btn_zero_Z.setDefault(False)

        self.btn_load_slide = QPushButton('To Slide Loading Position')
        
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('X (mm)'), 0,0)
        grid_line0.addWidget(self.label_Xpos, 0,1)
        grid_line0.addWidget(self.entry_dX, 0,2)
        grid_line0.addWidget(self.btn_moveX_forward, 0,3)
        grid_line0.addWidget(self.btn_moveX_backward, 0,4)
        
        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Y (mm)'), 0,0)
        grid_line1.addWidget(self.label_Ypos, 0,1)
        grid_line1.addWidget(self.entry_dY, 0,2)
        grid_line1.addWidget(self.btn_moveY_forward, 0,3)
        grid_line1.addWidget(self.btn_moveY_backward, 0,4)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Z (um)'), 0,0)
        grid_line2.addWidget(self.label_Zpos, 0,1)
        grid_line2.addWidget(self.entry_dZ, 0,2)
        grid_line2.addWidget(self.btn_moveZ_forward, 0,3)
        grid_line2.addWidget(self.btn_moveZ_backward, 0,4)
        
        grid_line3 = QGridLayout()
        if self.widget_configuration == 'full':
            grid_line3.addWidget(self.btn_zero_X, 0,3)
            grid_line3.addWidget(self.btn_zero_Y, 0,4)
            grid_line3.addWidget(self.btn_zero_Z, 0,5)
            grid_line3.addWidget(self.btn_home_X, 0,0)
            grid_line3.addWidget(self.btn_home_Y, 0,1)
            grid_line3.addWidget(self.btn_home_Z, 0,2)
        elif self.widget_configuration == 'malaria':
            grid_line3.addWidget(self.btn_load_slide, 0,0,1,2)
            grid_line3.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3.addWidget(self.btn_zero_Z, 0,3,1,1)
        elif self.widget_configuration == '384 well plate':
            grid_line3.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3.addWidget(self.btn_zero_Z, 0,3,1,1)
        elif self.widget_configuration == '96 well plate':
            grid_line3.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3.addWidget(self.btn_zero_Z, 0,3,1,1)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        self.grid.addLayout(grid_line3,3,0)
        self.setLayout(self.grid)

        self.entry_dX.valueChanged.connect(self.set_deltaX)
        self.entry_dY.valueChanged.connect(self.set_deltaY)
        self.entry_dZ.valueChanged.connect(self.set_deltaZ)

        self.btn_moveX_forward.clicked.connect(self.move_x_forward)
        self.btn_moveX_backward.clicked.connect(self.move_x_backward)
        self.btn_moveY_forward.clicked.connect(self.move_y_forward)
        self.btn_moveY_backward.clicked.connect(self.move_y_backward)
        self.btn_moveZ_forward.clicked.connect(self.move_z_forward)
        self.btn_moveZ_backward.clicked.connect(self.move_z_backward)

        self.btn_home_X.clicked.connect(self.home_x)
        self.btn_home_Y.clicked.connect(self.home_y)
        self.btn_home_Z.clicked.connect(self.home_z)
        self.btn_zero_X.clicked.connect(self.zero_x)
        self.btn_zero_Y.clicked.connect(self.zero_y)
        self.btn_zero_Z.clicked.connect(self.zero_z)

        self.btn_load_slide.clicked.connect(self.switch_position)
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF");
        
    def move_x_forward(self):
        self.navigationController.move_x(self.entry_dX.value())
    def move_x_backward(self):
        self.navigationController.move_x(-self.entry_dX.value())
    def move_y_forward(self):
        self.navigationController.move_y(self.entry_dY.value())
    def move_y_backward(self):
        self.navigationController.move_y(-self.entry_dY.value())
    def move_z_forward(self):
        self.navigationController.move_z(self.entry_dZ.value()/1000)
    def move_z_backward(self):
        self.navigationController.move_z(-self.entry_dZ.value()/1000) 

    def set_deltaX(self,value):
        mm_per_ustep = SCREW_PITCH_X_MM/(self.navigationController.x_microstepping*FULLSTEPS_PER_REV_X) # to implement a get_x_microstepping() in multipointController
        deltaX = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_dX.setValue(deltaX)
    def set_deltaY(self,value):
        mm_per_ustep = SCREW_PITCH_Y_MM/(self.navigationController.y_microstepping*FULLSTEPS_PER_REV_Y)
        deltaY = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_dY.setValue(deltaY)
    def set_deltaZ(self,value):
        mm_per_ustep = SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_dZ.setValue(deltaZ)

    def home_x(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.home_x()

    def home_y(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.home_y()

    def home_z(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.home_z()

    def zero_x(self):
        self.navigationController.zero_x()

    def zero_y(self):
        self.navigationController.zero_y()

    def zero_z(self):
        self.navigationController.zero_z()

    def slot_slide_loading_position_reached(self):
        self.slide_position = 'loading'
        self.btn_load_slide.setStyleSheet("background-color: #C2FFC2");
        self.btn_load_slide.setText('To Slide Scanning Position')
        self.btn_moveX_forward.setEnabled(False)
        self.btn_moveX_backward.setEnabled(False)
        self.btn_moveY_forward.setEnabled(False)
        self.btn_moveY_backward.setEnabled(False)
        self.btn_moveZ_forward.setEnabled(False)
        self.btn_moveZ_backward.setEnabled(False)

    def slot_slide_scanning_position_reached(self):
        self.slide_position = 'scanning'
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF");
        self.btn_load_slide.setText('To Slide Loading Position')
        self.btn_moveX_forward.setEnabled(True)
        self.btn_moveX_backward.setEnabled(True)
        self.btn_moveY_forward.setEnabled(True)
        self.btn_moveY_backward.setEnabled(True)
        self.btn_moveZ_forward.setEnabled(True)
        self.btn_moveZ_backward.setEnabled(True)

    def switch_position(self):
        if self.slide_position != 'loading':
            self.slidePositionController.move_to_slide_loading_position()
        else:
            self.slidePositionController.move_to_slide_scanning_position()

class DACControWidget(QFrame):
    def __init__(self, microcontroller ,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.microcontroller = microcontroller
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.slider_DAC0 = QSlider(Qt.Horizontal)
        self.slider_DAC0.setTickPosition(QSlider.TicksBelow)
        self.slider_DAC0.setMinimum(0)
        self.slider_DAC0.setMaximum(100)
        self.slider_DAC0.setSingleStep(0.1)
        self.slider_DAC0.setValue(0)

        self.entry_DAC0 = QDoubleSpinBox()
        self.entry_DAC0.setMinimum(0) 
        self.entry_DAC0.setMaximum(100) 
        self.entry_DAC0.setSingleStep(0.1)
        self.entry_DAC0.setValue(0)
        self.entry_DAC0.setKeyboardTracking(False)

        self.slider_DAC1 = QSlider(Qt.Horizontal)
        self.slider_DAC1.setTickPosition(QSlider.TicksBelow)
        self.slider_DAC1.setMinimum(0)
        self.slider_DAC1.setMaximum(100)
        self.slider_DAC1.setValue(0)
        self.slider_DAC1.setSingleStep(0.1)

        self.entry_DAC1 = QDoubleSpinBox()
        self.entry_DAC1.setMinimum(0) 
        self.entry_DAC1.setMaximum(100) 
        self.entry_DAC1.setSingleStep(0.1)
        self.entry_DAC1.setValue(0)
        self.entry_DAC1.setKeyboardTracking(False)

        # connections
        self.entry_DAC0.valueChanged.connect(self.set_DAC0)
        self.entry_DAC0.valueChanged.connect(self.slider_DAC0.setValue)
        self.slider_DAC0.valueChanged.connect(self.entry_DAC0.setValue)
        self.entry_DAC1.valueChanged.connect(self.set_DAC1)
        self.entry_DAC1.valueChanged.connect(self.slider_DAC1.setValue)
        self.slider_DAC1.valueChanged.connect(self.entry_DAC1.setValue)

        # layout
        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('DAC0'), 0,0)
        grid_line1.addWidget(self.slider_DAC0, 0,1)
        grid_line1.addWidget(self.entry_DAC0, 0,2)
        grid_line1.addWidget(QLabel('DAC1'), 1,0)
        grid_line1.addWidget(self.slider_DAC1, 1,1)
        grid_line1.addWidget(self.entry_DAC1, 1,2)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line1,1,0)
        self.setLayout(self.grid)

    def set_DAC0(self,value):
        self.microcontroller.analog_write_onboard_DAC(0,int(value*65535/100))

    def set_DAC1(self,value):
        self.microcontroller.analog_write_onboard_DAC(1,int(value*65535/100))

class AutoFocusWidget(QFrame):
    def __init__(self, autofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autofocusController = autofocusController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.entry_delta = QDoubleSpinBox()
        self.entry_delta.setMinimum(0) 
        self.entry_delta.setMaximum(20) 
        self.entry_delta.setSingleStep(0.2)
        self.entry_delta.setDecimals(3)
        self.entry_delta.setValue(1.524)
        self.entry_delta.setKeyboardTracking(False)
        self.autofocusController.set_deltaZ(1.524)

        self.entry_N = QSpinBox()
        self.entry_N.setMinimum(3) 
        self.entry_N.setMaximum(20) 
        self.entry_N.setSingleStep(1)
        self.entry_N.setValue(10)
        self.entry_N.setKeyboardTracking(False)
        self.autofocusController.set_N(10)

        self.btn_autofocus = QPushButton('Autofocus')
        self.btn_autofocus.setDefault(False)
        self.btn_autofocus.setCheckable(True)
        self.btn_autofocus.setChecked(False)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('delta Z (um)'), 0,0)
        grid_line0.addWidget(self.entry_delta, 0,1)
        grid_line0.addWidget(QLabel('N Z planes'), 0,2)
        grid_line0.addWidget(self.entry_N, 0,3)
        grid_line0.addWidget(self.btn_autofocus, 0,4)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.setLayout(self.grid)
        
        # connections
        self.btn_autofocus.clicked.connect(self.autofocusController.autofocus)
        self.entry_delta.valueChanged.connect(self.set_deltaZ)
        self.entry_N.valueChanged.connect(self.autofocusController.set_N)
        self.autofocusController.autofocusFinished.connect(self.autofocus_is_finished)

    def set_deltaZ(self,value):
        mm_per_ustep = SCREW_PITCH_Z_MM/(self.autofocusController.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_delta.setValue(deltaZ)
        self.autofocusController.set_deltaZ(deltaZ)

    def autofocus_is_finished(self):
        self.btn_autofocus.setChecked(False)

class MultiPointWidget(QFrame):
    def __init__(self, multipointController, configurationManager = None, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multipointController = multipointController
        self.configurationManager = configurationManager
        self.base_path_is_set = False
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):

        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')

        self.lineEdit_savingDir.setText(DEFAULT_SAVING_PATH)
        self.multipointController.set_base_path(DEFAULT_SAVING_PATH)
        self.base_path_is_set = True

        self.lineEdit_experimentID = QLineEdit()

        self.entry_deltaX = QDoubleSpinBox()
        self.entry_deltaX.setMinimum(0) 
        self.entry_deltaX.setMaximum(5) 
        self.entry_deltaX.setSingleStep(0.1)
        self.entry_deltaX.setValue(Acquisition.DX)
        self.entry_deltaX.setDecimals(3)
        self.entry_deltaX.setKeyboardTracking(False)

        self.entry_NX = QSpinBox()
        self.entry_NX.setMinimum(1) 
        self.entry_NX.setMaximum(50) 
        self.entry_NX.setSingleStep(1)
        self.entry_NX.setValue(1)
        self.entry_NX.setKeyboardTracking(False)

        self.entry_deltaY = QDoubleSpinBox()
        self.entry_deltaY.setMinimum(0) 
        self.entry_deltaY.setMaximum(5) 
        self.entry_deltaY.setSingleStep(0.1)
        self.entry_deltaY.setValue(Acquisition.DX)
        self.entry_deltaY.setDecimals(3)
        self.entry_deltaY.setKeyboardTracking(False)
        
        self.entry_NY = QSpinBox()
        self.entry_NY.setMinimum(1) 
        self.entry_NY.setMaximum(50) 
        self.entry_NY.setSingleStep(1)
        self.entry_NY.setValue(1)
        self.entry_NY.setKeyboardTracking(False)

        self.entry_deltaZ = QDoubleSpinBox()
        self.entry_deltaZ.setMinimum(0) 
        self.entry_deltaZ.setMaximum(1000) 
        self.entry_deltaZ.setSingleStep(0.2)
        self.entry_deltaZ.setValue(Acquisition.DZ)
        self.entry_deltaZ.setDecimals(3)
        self.entry_deltaZ.setKeyboardTracking(False)
        
        self.entry_NZ = QSpinBox()
        self.entry_NZ.setMinimum(1) 
        self.entry_NZ.setMaximum(100) 
        self.entry_NZ.setSingleStep(1)
        self.entry_NZ.setValue(1)
        self.entry_NZ.setKeyboardTracking(False)
        
        self.entry_dt = QDoubleSpinBox()
        self.entry_dt.setMinimum(0) 
        self.entry_dt.setMaximum(12*3600) 
        self.entry_dt.setSingleStep(1)
        self.entry_dt.setValue(0)
        self.entry_dt.setKeyboardTracking(False)

        self.entry_Nt = QSpinBox()
        self.entry_Nt.setMinimum(1) 
        self.entry_Nt.setMaximum(50000)   # @@@ to be changed
        self.entry_Nt.setSingleStep(1)
        self.entry_Nt.setValue(1)
        self.entry_Nt.setKeyboardTracking(False)

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection) # ref: https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum

        self.checkbox_withAutofocus = QCheckBox('With AF')
        self.checkbox_withAutofocus.setChecked(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.btn_startAcquisition = QPushButton('Start Acquisition')
        self.btn_startAcquisition.setCheckable(True)
        self.btn_startAcquisition.setChecked(False)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('Saving Path'))
        grid_line0.addWidget(self.lineEdit_savingDir, 0,1)
        grid_line0.addWidget(self.btn_setSavingDir, 0,2)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Experiment ID'), 0,0)
        grid_line1.addWidget(self.lineEdit_experimentID,0,1)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('dx (mm)'), 0,0)
        grid_line2.addWidget(self.entry_deltaX, 0,1)
        grid_line2.addWidget(QLabel('Nx'), 0,2)
        grid_line2.addWidget(self.entry_NX, 0,3)
        grid_line2.addWidget(QLabel('dy (mm)'), 0,4)
        grid_line2.addWidget(self.entry_deltaY, 0,5)
        grid_line2.addWidget(QLabel('Ny'), 0,6)
        grid_line2.addWidget(self.entry_NY, 0,7)

        grid_line2.addWidget(QLabel('dz (um)'), 1,0)
        grid_line2.addWidget(self.entry_deltaZ, 1,1)
        grid_line2.addWidget(QLabel('Nz'), 1,2)
        grid_line2.addWidget(self.entry_NZ, 1,3)
        grid_line2.addWidget(QLabel('dt (s)'), 1,4)
        grid_line2.addWidget(self.entry_dt, 1,5)
        grid_line2.addWidget(QLabel('Nt'), 1,6)
        grid_line2.addWidget(self.entry_Nt, 1,7)

        grid_line3 = QHBoxLayout()
        grid_line3.addWidget(self.list_configurations)
        grid_line3.addWidget(self.checkbox_withAutofocus)
        grid_line3.addWidget(self.btn_startAcquisition)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        self.grid.addLayout(grid_line3,3,0)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        self.entry_deltaX.valueChanged.connect(self.set_deltaX)
        self.entry_deltaY.valueChanged.connect(self.set_deltaY)
        self.entry_deltaZ.valueChanged.connect(self.set_deltaZ)
        self.entry_dt.valueChanged.connect(self.multipointController.set_deltat)
        self.entry_NX.valueChanged.connect(self.multipointController.set_NX)
        self.entry_NY.valueChanged.connect(self.multipointController.set_NY)
        self.entry_NZ.valueChanged.connect(self.multipointController.set_NZ)
        self.entry_Nt.valueChanged.connect(self.multipointController.set_Nt)
        self.checkbox_withAutofocus.stateChanged.connect(self.multipointController.set_af_flag)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)

    def set_deltaX(self,value):
        mm_per_ustep = SCREW_PITCH_X_MM/(self.multipointController.navigationController.x_microstepping*FULLSTEPS_PER_REV_X) # to implement a get_x_microstepping() in multipointController
        deltaX = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_deltaX.setValue(deltaX)
        self.multipointController.set_deltaX(deltaX)

    def set_deltaY(self,value):
        mm_per_ustep = SCREW_PITCH_Y_MM/(self.multipointController.navigationController.y_microstepping*FULLSTEPS_PER_REV_Y)
        deltaY = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_deltaY.setValue(deltaY)
        self.multipointController.set_deltaY(deltaY)

    def set_deltaZ(self,value):
        mm_per_ustep = SCREW_PITCH_Z_MM/(self.multipointController.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_deltaZ.setValue(deltaZ)
        self.multipointController.set_deltaZ(deltaZ)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.multipointController.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True

    def toggle_acquisition(self,pressed):
        if self.base_path_is_set == False:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if pressed:
            # @@@ to do: add a widgetManger to enable and disable widget 
            # @@@ to do: emit signal to widgetManager to disable other widgets
            self.setEnabled_all(False)
            self.multipointController.start_new_experiment(self.lineEdit_experimentID.text())
            self.multipointController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.multipointController.run_acquisition()
        else:
            self.multipointController.request_abort_aquisition()
            self.setEnabled_all(True)

    def acquisition_is_finished(self):
        self.btn_startAcquisition.setChecked(False)
        self.setEnabled_all(True)

    def setEnabled_all(self,enabled,exclude_btn_startAcquisition=True):
        self.btn_setSavingDir.setEnabled(enabled)
        self.lineEdit_savingDir.setEnabled(enabled)
        self.lineEdit_experimentID.setEnabled(enabled)
        self.entry_deltaX.setEnabled(enabled)
        self.entry_NX.setEnabled(enabled)
        self.entry_deltaY.setEnabled(enabled)
        self.entry_NY.setEnabled(enabled)
        self.entry_deltaZ.setEnabled(enabled)
        self.entry_NZ.setEnabled(enabled)
        self.entry_dt.setEnabled(enabled)
        self.entry_Nt.setEnabled(enabled)
        self.list_configurations.setEnabled(enabled)
        self.checkbox_withAutofocus.setEnabled(enabled)
        if exclude_btn_startAcquisition is not True:
            self.btn_startAcquisition.setEnabled(enabled)

    def disable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(False)

    def enable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(True)

class TrackingControllerWidget(QFrame):
    def __init__(self, trackingController, configurationManager, show_configurations = True, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trackingController = trackingController
        self.configurationManager = configurationManager
        self.base_path_is_set = False
        self.add_components(show_configurations)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self,show_configurations):
        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')
        self.lineEdit_savingDir.setText(DEFAULT_SAVING_PATH)
        self.trackingController.set_base_path(DEFAULT_SAVING_PATH)
        self.base_path_is_set = True

        self.lineEdit_experimentID = QLineEdit()

        self.dropdown_objective = QComboBox()
        self.dropdown_objective.addItems(list(OBJECTIVES.keys()))
        self.dropdown_objective.setCurrentText(DEFAULT_OBJECTIVE)

        self.dropdown_tracker = QComboBox()
        self.dropdown_tracker.addItems(TRACKERS)
        self.dropdown_tracker.setCurrentText(DEFAULT_TRACKER)

        self.entry_tracking_interval = QDoubleSpinBox()
        self.entry_tracking_interval.setMinimum(0) 
        self.entry_tracking_interval.setMaximum(30) 
        self.entry_tracking_interval.setSingleStep(0.5)
        self.entry_tracking_interval.setValue(0)

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection) # ref: https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum

        self.checkbox_withAutofocus = QCheckBox('With AF')
        self.checkbox_saveImages = QCheckBox('Save Images')
        self.btn_track = QPushButton('Start Tracking')
        self.btn_track.setCheckable(True)
        self.btn_track.setChecked(False)

        self.checkbox_enable_stage_tracking = QCheckBox(' Enable Stage Tracking')
        self.checkbox_enable_stage_tracking.setChecked(True)

        # layout
        grid_line0 = QGridLayout()
        tmp = QLabel('Saving Path')
        tmp.setFixedWidth(90)
        grid_line0.addWidget(tmp, 0,0)
        grid_line0.addWidget(self.lineEdit_savingDir, 0,1, 1,2)
        grid_line0.addWidget(self.btn_setSavingDir, 0,3)
        tmp = QLabel('Experiment ID')
        tmp.setFixedWidth(90)
        grid_line0.addWidget(tmp, 1,0)
        grid_line0.addWidget(self.lineEdit_experimentID, 1,1, 1,1)
        tmp = QLabel('Objective')
        tmp.setFixedWidth(90)
        grid_line0.addWidget(tmp,1,2)
        grid_line0.addWidget(self.dropdown_objective, 1,3)

        grid_line3 = QHBoxLayout()
        tmp = QLabel('Configurations')
        tmp.setFixedWidth(90)
        grid_line3.addWidget(tmp)
        grid_line3.addWidget(self.list_configurations)
        
        grid_line1 = QHBoxLayout()
        tmp = QLabel('Tracker')
        grid_line1.addWidget(tmp)
        grid_line1.addWidget(self.dropdown_tracker)
        tmp = QLabel('Tracking Interval (s)')
        grid_line1.addWidget(tmp)
        grid_line1.addWidget(self.entry_tracking_interval)
        grid_line1.addWidget(self.checkbox_withAutofocus)
        grid_line1.addWidget(self.checkbox_saveImages)

        grid_line4 = QGridLayout()
        grid_line4.addWidget(self.btn_track,0,0,1,3)
        grid_line4.addWidget(self.checkbox_enable_stage_tracking,0,4)

        self.grid = QVBoxLayout()
        self.grid.addLayout(grid_line0)
        if show_configurations:
            self.grid.addLayout(grid_line3)
        else:
            self.list_configurations.setCurrentRow(0) # select the first configuration
        self.grid.addLayout(grid_line1)        
        self.grid.addLayout(grid_line4)
        self.grid.addStretch()
        self.setLayout(self.grid)

        # connections - buttons, checkboxes, entries
        self.checkbox_enable_stage_tracking.stateChanged.connect(self.trackingController.toggle_stage_tracking)
        self.checkbox_withAutofocus.stateChanged.connect(self.trackingController.toggel_enable_af)
        self.checkbox_saveImages.stateChanged.connect(self.trackingController.toggel_save_images)
        self.entry_tracking_interval.valueChanged.connect(self.trackingController.set_tracking_time_interval)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_track.clicked.connect(self.toggle_acquisition)
        # connections - selections and entries
        self.dropdown_tracker.currentIndexChanged.connect(self.update_tracker)
        self.dropdown_objective.currentIndexChanged.connect(self.update_pixel_size)
        # controller to widget
        self.trackingController.signal_tracking_stopped.connect(self.slot_tracking_stopped)

        # run initialization functions
        self.update_pixel_size()
        self.trackingController.update_image_resizing_factor(1) # to add: image resizing slider

    def slot_joystick_button_pressed(self):
        self.btn_track.toggle()
        if self.btn_track.isChecked():
            if self.base_path_is_set == False:
                self.btn_track.setChecked(False)
                msg = QMessageBox()
                msg.setText("Please choose base saving directory first")
                msg.exec_()
                return
            self.setEnabled_all(False)
            self.trackingController.start_new_experiment(self.lineEdit_experimentID.text())
            self.trackingController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.trackingController.start_tracking()
        else:
            self.trackingController.stop_tracking()

    def slot_tracking_stopped(self):
        self.btn_track.setChecked(False)
        self.setEnabled_all(True)
        print('tracking stopped')

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.trackingController.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True 

    def toggle_acquisition(self,pressed):
        if pressed:
            if self.base_path_is_set == False:
                self.btn_track.setChecked(False)
                msg = QMessageBox()
                msg.setText("Please choose base saving directory first")
                msg.exec_()
                return
            # @@@ to do: add a widgetManger to enable and disable widget 
            # @@@ to do: emit signal to widgetManager to disable other widgets
            self.setEnabled_all(False)
            self.trackingController.start_new_experiment(self.lineEdit_experimentID.text())
            self.trackingController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.trackingController.start_tracking()
        else:
            self.trackingController.stop_tracking()

    def setEnabled_all(self,enabled):
        self.btn_setSavingDir.setEnabled(enabled)
        self.lineEdit_savingDir.setEnabled(enabled)
        self.lineEdit_experimentID.setEnabled(enabled)
        self.dropdown_tracker
        self.dropdown_objective
        self.list_configurations.setEnabled(enabled)

    def update_tracker(self, index):
        self.trackingController.update_tracker_selection(self.dropdown_tracker.currentText())

    def update_pixel_size(self): 
        objective = self.dropdown_objective.currentText()
        self.trackingController.objective = objective
        # self.internal_state.data['Objective'] = self.objective
        pixel_size_um = CAMERA_PIXEL_SIZE_UM[CAMERA_SENSOR] / ( TUBE_LENS_MM/ (OBJECTIVES[objective]['tube_lens_f_mm']/OBJECTIVES[objective]['magnification']) )
        self.trackingController.update_pixel_size(pixel_size_um)
        print('pixel size is ' + str(pixel_size_um) + ' um')


    '''
        # connections
        self.checkbox_withAutofocus.stateChanged.connect(self.trackingController.set_af_flag)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.trackingController.trackingStopped.connect(self.acquisition_is_finished)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.plateReadingController.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True

    def toggle_acquisition(self,pressed):
        if self.base_path_is_set == False:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if pressed:
            # @@@ to do: add a widgetManger to enable and disable widget 
            # @@@ to do: emit signal to widgetManager to disable other widgets
            self.setEnabled_all(False)
            self.trackingController.start_new_experiment(self.lineEdit_experimentID.text())
            self.trackingController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.trackingController.set_selected_columns(list(map(int,[item.text() for item in self.list_columns.selectedItems()])))
            self.trackingController.run_acquisition()
        else:
            self.trackingController.stop_acquisition() # to implement
            pass

    def acquisition_is_finished(self):
        self.btn_startAcquisition.setChecked(False)
        self.setEnabled_all(True)

    def setEnabled_all(self,enabled,exclude_btn_startAcquisition=False):
        self.btn_setSavingDir.setEnabled(enabled)
        self.lineEdit_savingDir.setEnabled(enabled)
        self.lineEdit_experimentID.setEnabled(enabled)
        self.list_columns.setEnabled(enabled)
        self.list_configurations.setEnabled(enabled)
        self.checkbox_withAutofocus.setEnabled(enabled)
        if exclude_btn_startAcquisition is not True:
            self.btn_startAcquisition.setEnabled(enabled)
    '''

class PlateReaderAcquisitionWidget(QFrame):
    def __init__(self, plateReadingController, configurationManager = None, show_configurations = True, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plateReadingController = plateReadingController
        self.configurationManager = configurationManager
        self.base_path_is_set = False
        self.add_components(show_configurations)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self,show_configurations):
        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')
        self.lineEdit_savingDir.setText(DEFAULT_SAVING_PATH)
        self.plateReadingController.set_base_path(DEFAULT_SAVING_PATH)
        self.base_path_is_set = True

        self.lineEdit_experimentID = QLineEdit()

        self.list_columns = QListWidget()
        for i in range(PLATE_READER.NUMBER_OF_COLUMNS):
            self.list_columns.addItems([str(i+1)])
        self.list_columns.setSelectionMode(QAbstractItemView.MultiSelection) # ref: https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection) # ref: https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum

        self.checkbox_withAutofocus = QCheckBox('With AF')
        self.btn_startAcquisition = QPushButton('Start Acquisition')
        self.btn_startAcquisition.setCheckable(True)
        self.btn_startAcquisition.setChecked(False)

        self.btn_startAcquisition.setEnabled(False)

        # layout
        grid_line0 = QGridLayout()
        tmp = QLabel('Saving Path')
        tmp.setFixedWidth(90)
        grid_line0.addWidget(tmp)
        grid_line0.addWidget(self.lineEdit_savingDir, 0,1)
        grid_line0.addWidget(self.btn_setSavingDir, 0,2)

        grid_line1 = QGridLayout()
        tmp = QLabel('Sample ID')
        tmp.setFixedWidth(90)
        grid_line1.addWidget(tmp)
        grid_line1.addWidget(self.lineEdit_experimentID,0,1)

        grid_line2 = QGridLayout()
        tmp = QLabel('Columns')
        tmp.setFixedWidth(90)
        grid_line2.addWidget(tmp)
        grid_line2.addWidget(self.list_columns, 0,1)

        grid_line3 = QHBoxLayout()
        tmp = QLabel('Configurations')
        tmp.setFixedWidth(90)
        grid_line3.addWidget(tmp)
        grid_line3.addWidget(self.list_configurations)
        # grid_line3.addWidget(self.checkbox_withAutofocus)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        if show_configurations:
            self.grid.addLayout(grid_line3,3,0)
        else:
            self.list_configurations.setCurrentRow(0) # select the first configuration
        self.grid.addWidget(self.btn_startAcquisition,4,0)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        self.checkbox_withAutofocus.stateChanged.connect(self.plateReadingController.set_af_flag)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.plateReadingController.acquisitionFinished.connect(self.acquisition_is_finished)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.plateReadingController.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True

    def toggle_acquisition(self,pressed):
        if self.base_path_is_set == False:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if pressed:
            # @@@ to do: add a widgetManger to enable and disable widget 
            # @@@ to do: emit signal to widgetManager to disable other widgets
            self.setEnabled_all(False)
            self.plateReadingController.start_new_experiment(self.lineEdit_experimentID.text())
            self.plateReadingController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.plateReadingController.set_selected_columns(list(map(int,[item.text() for item in self.list_columns.selectedItems()])))
            self.plateReadingController.run_acquisition()
        else:
            self.plateReadingController.stop_acquisition() # to implement
            pass

    def acquisition_is_finished(self):
        self.btn_startAcquisition.setChecked(False)
        self.setEnabled_all(True)

    def setEnabled_all(self,enabled,exclude_btn_startAcquisition=False):
        self.btn_setSavingDir.setEnabled(enabled)
        self.lineEdit_savingDir.setEnabled(enabled)
        self.lineEdit_experimentID.setEnabled(enabled)
        self.list_columns.setEnabled(enabled)
        self.list_configurations.setEnabled(enabled)
        self.checkbox_withAutofocus.setEnabled(enabled)
        if exclude_btn_startAcquisition is not True:
            self.btn_startAcquisition.setEnabled(enabled)

    def slot_homing_complete(self):
        self.btn_startAcquisition.setEnabled(True)
    
class PlateReaderNavigationWidget(QFrame):
    def __init__(self, plateReaderNavigationController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.plateReaderNavigationController = plateReaderNavigationController

    def add_components(self):
        self.dropdown_column = QComboBox()
        self.dropdown_column.addItems([''])
        self.dropdown_column.addItems([str(i+1) for i in range(PLATE_READER.NUMBER_OF_COLUMNS)])
        self.dropdown_row = QComboBox()
        self.dropdown_row.addItems([''])
        self.dropdown_row.addItems([chr(i) for i in range(ord('A'),ord('A')+PLATE_READER.NUMBER_OF_ROWS)])
        self.btn_moveto = QPushButton("Move To")
        self.btn_home = QPushButton('Home')
        self.label_current_location = QLabel()
        self.label_current_location.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.label_current_location.setFixedWidth(50)

        self.dropdown_column.setEnabled(False)
        self.dropdown_row.setEnabled(False)
        self.btn_moveto.setEnabled(False)
        
        # layout
        grid_line0 = QHBoxLayout()
        # tmp = QLabel('Saving Path')
        # tmp.setFixedWidth(90)
        grid_line0.addWidget(self.btn_home)
        grid_line0.addWidget(QLabel('Column'))
        grid_line0.addWidget(self.dropdown_column)
        grid_line0.addWidget(QLabel('Row'))
        grid_line0.addWidget(self.dropdown_row)
        grid_line0.addWidget(self.btn_moveto)
        grid_line0.addStretch()
        grid_line0.addWidget(self.label_current_location)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.setLayout(self.grid)

        self.btn_home.clicked.connect(self.home)
        self.btn_moveto.clicked.connect(self.move)

    def home(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.plateReaderNavigationController.home()

    def move(self):
        self.plateReaderNavigationController.moveto(self.dropdown_column.currentText(),self.dropdown_row.currentText())

    def slot_homing_complete(self):
        self.dropdown_column.setEnabled(True)
        self.dropdown_row.setEnabled(True)
        self.btn_moveto.setEnabled(True)

    def update_current_location(self,location_str):
        self.label_current_location.setText(location_str)
        row = location_str[0]
        column = location_str[1:]
        self.dropdown_row.setCurrentText(row)
        self.dropdown_column.setCurrentText(column)


class TriggerControlWidget(QFrame):
    # for synchronized trigger 
    signal_toggle_live = Signal(bool)
    signal_trigger_mode = Signal(str)
    signal_trigger_fps = Signal(float)

    def __init__(self, microcontroller2):
        super().__init__()
        self.fps_trigger = 10
        self.fps_display = 10
        self.microcontroller2 = microcontroller2
        self.triggerMode = TriggerMode.SOFTWARE
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        # line 0: trigger mode
        self.triggerMode = None
        self.dropdown_triggerManu = QComboBox()
        self.dropdown_triggerManu.addItems([TriggerMode.SOFTWARE,TriggerMode.HARDWARE])

        # line 1: fps
        self.entry_triggerFPS = QDoubleSpinBox()
        self.entry_triggerFPS.setMinimum(0.02) 
        self.entry_triggerFPS.setMaximum(1000) 
        self.entry_triggerFPS.setSingleStep(1)
        self.entry_triggerFPS.setValue(self.fps_trigger)

        self.btn_live = QPushButton("Live")
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(False)
        self.btn_live.setDefault(False)

        # connections
        self.dropdown_triggerManu.currentIndexChanged.connect(self.update_trigger_mode)
        self.btn_live.clicked.connect(self.toggle_live)
        self.entry_triggerFPS.valueChanged.connect(self.update_trigger_fps)

        # inititialization
        self.microcontroller2.set_camera_trigger_frequency(self.fps_trigger)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('Trigger Mode'), 0,0)
        grid_line0.addWidget(self.dropdown_triggerManu, 0,1)
        grid_line0.addWidget(QLabel('Trigger FPS'), 0,2)
        grid_line0.addWidget(self.entry_triggerFPS, 0,3)
        grid_line0.addWidget(self.btn_live, 1,0,1,4)
        self.setLayout(grid_line0)

    def toggle_live(self,pressed):
        self.signal_toggle_live.emit(pressed)
        if pressed:
            self.microcontroller2.start_camera_trigger()
        else:
            self.microcontroller2.stop_camera_trigger()

    def update_trigger_mode(self):
        self.signal_trigger_mode.emit(self.dropdown_triggerManu.currentText())

    def update_trigger_fps(self,fps):
        self.fps_trigger = fps
        self.signal_trigger_fps.emit(fps)
        self.microcontroller2.set_camera_trigger_frequency(self.fps_trigger)

class MultiCameraRecordingWidget(QFrame):
    def __init__(self, streamHandler, imageSaver, channels, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imageSaver = imageSaver # for saving path control
        self.streamHandler = streamHandler
        self.channels = channels
        self.base_path_is_set = False
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')

        self.lineEdit_experimentID = QLineEdit()

        self.entry_saveFPS = QDoubleSpinBox()
        self.entry_saveFPS.setMinimum(0.02) 
        self.entry_saveFPS.setMaximum(1000) 
        self.entry_saveFPS.setSingleStep(1)
        self.entry_saveFPS.setValue(1)
        for channel in self.channels:
            self.streamHandler[channel].set_save_fps(1)

        self.entry_timeLimit = QSpinBox()
        self.entry_timeLimit.setMinimum(-1) 
        self.entry_timeLimit.setMaximum(60*60*24*30) 
        self.entry_timeLimit.setSingleStep(1)
        self.entry_timeLimit.setValue(-1)

        self.btn_record = QPushButton("Record")
        self.btn_record.setCheckable(True)
        self.btn_record.setChecked(False)
        self.btn_record.setDefault(False)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Saving Path'))
        grid_line1.addWidget(self.lineEdit_savingDir, 0,1)
        grid_line1.addWidget(self.btn_setSavingDir, 0,2)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Experiment ID'), 0,0)
        grid_line2.addWidget(self.lineEdit_experimentID,0,1)

        grid_line3 = QGridLayout()
        grid_line3.addWidget(QLabel('Saving FPS'), 0,0)
        grid_line3.addWidget(self.entry_saveFPS, 0,1)
        grid_line3.addWidget(QLabel('Time Limit (s)'), 0,2)
        grid_line3.addWidget(self.entry_timeLimit, 0,3)
        grid_line3.addWidget(self.btn_record, 0,4)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line1,0,0)
        self.grid.addLayout(grid_line2,1,0)
        self.grid.addLayout(grid_line3,2,0)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_record.clicked.connect(self.toggle_recording)
        for channel in self.channels:
            self.entry_saveFPS.valueChanged.connect(self.streamHandler[channel].set_save_fps)
            self.entry_timeLimit.valueChanged.connect(self.imageSaver[channel].set_recording_time_limit)
            self.imageSaver[channel].stop_recording.connect(self.stop_recording)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        for channel in self.channels:
            self.imageSaver[channel].set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.save_dir_base = save_dir_base
        self.base_path_is_set = True

    def toggle_recording(self,pressed):
        if self.base_path_is_set == False:
            self.btn_record.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if pressed:
            self.lineEdit_experimentID.setEnabled(False)
            self.btn_setSavingDir.setEnabled(False)
            experiment_ID = self.lineEdit_experimentID.text()
            experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f')
            os.mkdir(os.path.join(self.save_dir_base,experiment_ID))
            for channel in self.channels:
                self.imageSaver[channel].start_new_experiment(os.path.join(experiment_ID,channel),add_timestamp=False)
                self.streamHandler[channel].start_recording()
        else:
            for channel in self.channels:
                self.streamHandler[channel].stop_recording()
            self.lineEdit_experimentID.setEnabled(True)
            self.btn_setSavingDir.setEnabled(True)

    # stop_recording can be called by imageSaver
    def stop_recording(self):
        self.lineEdit_experimentID.setEnabled(True)
        self.btn_record.setChecked(False)
        for channel in self.channels:
            self.streamHandler[channel].stop_recording()
        self.btn_setSavingDir.setEnabled(True)

class WaveformDisplay(QFrame):

    def __init__(self, N=1000, include_x=True, include_y=True, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.N = N
        self.include_x = include_x
        self.include_y = include_y
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.plotWidget = {}
        self.plotWidget['X'] = PlotWidget('X', N=self.N, add_legend=True)
        self.plotWidget['Y'] = PlotWidget('X', N=self.N, add_legend=True)

        layout = QGridLayout() #layout = QStackedLayout()
        if self.include_x:
            layout.addWidget(self.plotWidget['X'],0,0)
        if self.include_y:
            layout.addWidget(self.plotWidget['Y'],1,0)
        self.setLayout(layout)

    def plot(self,time,data):
        if self.include_x:
            self.plotWidget['X'].plot(time,data[0,:],'X',color=(255,255,255),clear=True)
        if self.include_y:
            self.plotWidget['Y'].plot(time,data[1,:],'Y',color=(255,255,255),clear=True)

    def update_N(self,N):
        self.N = N
        self.plotWidget['X'].update_N(N)
        self.plotWidget['Y'].update_N(N)

class PlotWidget(pg.GraphicsLayoutWidget):
    
    def __init__(self, title='', N = 1000, parent=None,add_legend=False):
        super().__init__(parent)
        self.plotWidget = self.addPlot(title = '', axisItems = {'bottom': pg.DateAxisItem()})
        if add_legend:
            self.plotWidget.addLegend()
        self.N = N
    
    def plot(self,x,y,label,color,clear=False):
        self.plotWidget.plot(x[-self.N:],y[-self.N:],pen=pg.mkPen(color=color,width=2),name=label,clear=clear)

    def update_N(self,N):
        self.N = N

class DisplacementMeasurementWidget(QFrame):
    def __init__(self, displacementMeasurementController, waveformDisplay, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.displacementMeasurementController = displacementMeasurementController
        self.waveformDisplay = waveformDisplay
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.entry_x_offset = QDoubleSpinBox()
        self.entry_x_offset.setMinimum(0) 
        self.entry_x_offset.setMaximum(3000) 
        self.entry_x_offset.setSingleStep(0.2)
        self.entry_x_offset.setDecimals(3)
        self.entry_x_offset.setValue(0)
        self.entry_x_offset.setKeyboardTracking(False)

        self.entry_y_offset = QDoubleSpinBox()
        self.entry_y_offset.setMinimum(0) 
        self.entry_y_offset.setMaximum(3000) 
        self.entry_y_offset.setSingleStep(0.2)
        self.entry_y_offset.setDecimals(3)
        self.entry_y_offset.setValue(0)
        self.entry_y_offset.setKeyboardTracking(False)

        self.entry_x_scaling = QDoubleSpinBox()
        self.entry_x_scaling.setMinimum(-100) 
        self.entry_x_scaling.setMaximum(100) 
        self.entry_x_scaling.setSingleStep(0.1)
        self.entry_x_scaling.setDecimals(3)
        self.entry_x_scaling.setValue(1)
        self.entry_x_scaling.setKeyboardTracking(False)

        self.entry_y_scaling = QDoubleSpinBox()
        self.entry_y_scaling.setMinimum(-100) 
        self.entry_y_scaling.setMaximum(100) 
        self.entry_y_scaling.setSingleStep(0.1)
        self.entry_y_scaling.setDecimals(3)
        self.entry_y_scaling.setValue(1)
        self.entry_y_scaling.setKeyboardTracking(False)

        self.entry_N_average = QSpinBox()
        self.entry_N_average.setMinimum(1) 
        self.entry_N_average.setMaximum(25) 
        self.entry_N_average.setSingleStep(1)
        self.entry_N_average.setValue(1)
        self.entry_N_average.setKeyboardTracking(False)

        self.entry_N = QSpinBox()
        self.entry_N.setMinimum(1) 
        self.entry_N.setMaximum(5000) 
        self.entry_N.setSingleStep(1)
        self.entry_N.setValue(1000)
        self.entry_N.setKeyboardTracking(False)

        self.reading_x = QLabel()
        self.reading_x.setNum(0)
        self.reading_x.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        self.reading_y = QLabel()
        self.reading_y.setNum(0)
        self.reading_y.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('x offset'), 0,0)
        grid_line0.addWidget(self.entry_x_offset, 0,1)
        grid_line0.addWidget(QLabel('x scaling'), 0,2)
        grid_line0.addWidget(self.entry_x_scaling, 0,3)
        grid_line0.addWidget(QLabel('y offset'), 0,4)
        grid_line0.addWidget(self.entry_y_offset, 0,5)
        grid_line0.addWidget(QLabel('y scaling'), 0,6)
        grid_line0.addWidget(self.entry_y_scaling, 0,7)
        
        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('d from x'), 0,0)
        grid_line1.addWidget(self.reading_x, 0,1)
        grid_line1.addWidget(QLabel('d from y'), 0,2)
        grid_line1.addWidget(self.reading_y, 0,3)
        grid_line1.addWidget(QLabel('N average'), 0,4)
        grid_line1.addWidget(self.entry_N_average, 0,5)
        grid_line1.addWidget(QLabel('N'), 0,6)
        grid_line1.addWidget(self.entry_N, 0,7)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.setLayout(self.grid)
        
        # connections
        self.entry_x_offset.valueChanged.connect(self.update_settings)
        self.entry_y_offset.valueChanged.connect(self.update_settings)
        self.entry_x_scaling.valueChanged.connect(self.update_settings)
        self.entry_y_scaling.valueChanged.connect(self.update_settings)
        self.entry_N_average.valueChanged.connect(self.update_settings)
        self.entry_N.valueChanged.connect(self.update_settings)
        self.entry_N.valueChanged.connect(self.update_waveformDisplay_N)

    def update_settings(self,new_value):
        print('update settings')
        self.displacementMeasurementController.update_settings(self.entry_x_offset.value(),self.entry_y_offset.value(),self.entry_x_scaling.value(),self.entry_y_scaling.value(),self.entry_N_average.value(),self.entry_N.value())
    
    def update_waveformDisplay_N(self,N):    
        self.waveformDisplay.update_N(N)

    def display_readings(self,readings):
        self.reading_x.setText("{:.2f}".format(readings[0]))
        self.reading_y.setText("{:.2f}".format(readings[1]))

class LaserAutofocusControlWidget(QFrame):
    def __init__(self, laserAutofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.laserAutofocusController = laserAutofocusController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.btn_initialize = QPushButton("Initialize")
        self.btn_initialize.setCheckable(False)
        self.btn_initialize.setChecked(False)
        self.btn_initialize.setDefault(False)

        self.btn_set_reference = QPushButton("Set as reference plane")
        self.btn_set_reference.setCheckable(False)
        self.btn_set_reference.setChecked(False)
        self.btn_set_reference.setDefault(False)

        self.label_displacement = QLabel()
        self.label_displacement.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        self.btn_measure_displacement = QPushButton("Measure displacement")
        self.btn_measure_displacement.setCheckable(False)
        self.btn_measure_displacement.setChecked(False)
        self.btn_measure_displacement.setDefault(False)

        self.entry_target = QDoubleSpinBox()
        self.entry_target.setMinimum(-100)
        self.entry_target.setMaximum(100)
        self.entry_target.setSingleStep(0.01)
        self.entry_target.setDecimals(2)
        self.entry_target.setValue(0)
        self.entry_target.setKeyboardTracking(False)

        self.btn_move_to_target = QPushButton("Move to target")
        self.btn_move_to_target.setCheckable(False)
        self.btn_move_to_target.setChecked(False)
        self.btn_move_to_target.setDefault(False)

        self.grid = QGridLayout()
        self.grid.addWidget(self.btn_initialize,0,0,1,3)
        self.grid.addWidget(self.btn_set_reference,1,0,1,3)
        self.grid.addWidget(QLabel('Displacement (um)'),2,0)
        self.grid.addWidget(self.label_displacement,2,1)
        self.grid.addWidget(self.btn_measure_displacement,2,2)
        self.grid.addWidget(QLabel('Target (um)'),3,0)
        self.grid.addWidget(self.entry_target,3,1)
        self.grid.addWidget(self.btn_move_to_target,3,2)
        self.grid.setRowStretch(self.grid.rowCount(), 1)

        self.setLayout(self.grid)

        # make connections
        self.btn_initialize.clicked.connect(self.laserAutofocusController.initialize_auto)
        self.btn_set_reference.clicked.connect(self.laserAutofocusController.set_reference)
        self.btn_measure_displacement.clicked.connect(self.laserAutofocusController.measure_displacement)
        self.btn_move_to_target.clicked.connect(self.move_to_target)
        self.laserAutofocusController.signal_displacement_um.connect(self.label_displacement.setNum)

    def move_to_target(self,target_um):
        self.laserAutofocusController.move_to_target(self.entry_target.value())


class WellSelectionWidget(QTableWidget):

    signal_wellSelected = Signal(int,int,float)
    signal_wellSelectedPos = Signal(float,float)

    def __init__(self, format_, *args):

        if format_ == 6:
            self.rows = 2
            self.columns = 3
            self.spacing_mm = 39.2
        elif format_ == 12:
            self.rows = 3
            self.columns = 4
            self.spacing_mm = 26
        elif format_ == 24:
            self.rows = 4
            self.columns = 6
            self.spacing_mm = 18
        elif format_ == 96:
            self.rows = 8
            self.columns = 12
            self.spacing_mm = 9
        elif format_ == 384:
            self.rows = 16
            self.columns = 24
            self.spacing_mm = 4.5
        elif format_ == 1536:
            self.rows = 32
            self.columns = 48
            self.spacing_mm = 2.25

        self.format = format_

        QTableWidget.__init__(self, self.rows, self.columns, *args)
        self.setData()
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cellDoubleClicked.connect(self.onDoubleClick)
        self.cellClicked.connect(self.onSingleClick)

        # size
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(5*self.spacing_mm)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setMinimumSectionSize(5*self.spacing_mm)

        self.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Minimum)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.resizeColumnsToContents()
        self.setFixedSize(self.horizontalHeader().length() + 
                   self.verticalHeader().width(),
                   self.verticalHeader().length() + 
                   self.horizontalHeader().height())

    def setData(self): 
        '''
        # cells
        for i in range(16):
            for j in range(24):
                newitem = QTableWidgetItem( chr(ord('A')+i) + str(j) )
                self.setItem(i, j, newitem)
        '''
        # row header
        row_headers = []
        for i in range(16):
            row_headers.append(chr(ord('A')+i))
        self.setVerticalHeaderLabels(row_headers)

        # make the outer cells not selectable if using 96 and 384 well plates
        if self.format == 384:
            for i in range(self.rows):
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.setItem(i,0,item)
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.setItem(i,self.columns-1,item)
            for j in range(self.columns):
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.setItem(0,j,item)
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.setItem(self.rows-1,j,item)
        elif self.format == 96:
            if NUMBER_OF_SKIP == 1:
                for i in range(self.rows):
                    item = QTableWidgetItem()
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    self.setItem(i,0,item)
                    item = QTableWidgetItem()
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    self.setItem(i,self.columns-1,item)
                for j in range(self.columns):
                    item = QTableWidgetItem()
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    self.setItem(0,j,item)
                    item = QTableWidgetItem()
                    item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                    self.setItem(self.rows-1,j,item)

    def onDoubleClick(self,row,col):
        if (row >= 0 + NUMBER_OF_SKIP and row <= self.rows-1-NUMBER_OF_SKIP ) and ( col >= 0 + NUMBER_OF_SKIP and col <= self.columns-1-NUMBER_OF_SKIP ):
            x_mm = X_MM_384_WELLPLATE_UPPERLEFT + WELL_SIZE_MM_384_WELLPLATE/2 - (A1_X_MM_384_WELLPLATE+WELL_SPACING_MM_384_WELLPLATE*NUMBER_OF_SKIP_384) + col*WELL_SPACING_MM + A1_X_MM + WELLPLATE_OFFSET_X_mm
            y_mm = Y_MM_384_WELLPLATE_UPPERLEFT + WELL_SIZE_MM_384_WELLPLATE/2 - (A1_Y_MM_384_WELLPLATE+WELL_SPACING_MM_384_WELLPLATE*NUMBER_OF_SKIP_384) + row*WELL_SPACING_MM + A1_Y_MM + WELLPLATE_OFFSET_Y_mm
            self.signal_wellSelectedPos.emit(x_mm,y_mm)
        # print('(' + str(row) + ',' + str(col) + ') doubleclicked')

    def onSingleClick(self,row,col):
        # self.get_selected_cells()
        pass

    def get_selected_cells(self):
        list_of_selected_cells = []
        for index in self.selectedIndexes():
             list_of_selected_cells.append((index.row(),index.column()))
        return(list_of_selected_cells)