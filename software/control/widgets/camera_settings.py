# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import pyqtgraph as pg

from datetime import datetime

from control._def import *
import control.core as core

from typing import Optional, Union, List, Tuple

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
