import os
import sys

# set QT_API environment variable
os.environ["QT_API"] = "pyqt5"

# qt libraries
import qtpy
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import pyqtgraph as pg
import pandas as pd
import napari
from napari.utils.colormaps import Colormap, AVAILABLE_COLORMAPS
import re
import cv2
import math
import locale
import time
from datetime import datetime

from control._def import *


class WrapperWindow(QMainWindow):
    def __init__(self, content_widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCentralWidget(content_widget)
        self.hide()

    def closeEvent(self, event):
        self.hide()
        event.ignore()

    def closeForReal(self, event):
        super().closeEvent(event)


class CollapsibleGroupBox(QGroupBox):
    def __init__(self, title):
        super(CollapsibleGroupBox,self).__init__(title)
        self.setCheckable(True)
        self.setChecked(True)
        self.higher_layout = QVBoxLayout()
        self.content = QVBoxLayout()
        #self.content.setAlignment(Qt.AlignTop)
        self.content_widget = QWidget()
        self.content_widget.setLayout(self.content)
        self.higher_layout.addWidget(self.content_widget)
        self.setLayout(self.higher_layout)
        self.toggled.connect(self.toggle_content)

    def toggle_content(self,state):
        self.content_widget.setVisible(state)


class ConfigEditorForAcquisitions(QDialog):
    def __init__(self, configManager, only_z_offset=True):
        super().__init__()

        self.config = configManager
        
        self.only_z_offset=only_z_offset

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QVBoxLayout()
        self.scroll_area_widget.setLayout(self.scroll_area_layout)
        self.scroll_area.setWidget(self.scroll_area_widget)

        self.save_config_button = QPushButton("Save Config")
        self.save_config_button.clicked.connect(self.save_config)
        self.save_to_file_button = QPushButton("Save to File")
        self.save_to_file_button.clicked.connect(self.save_to_file)
        self.load_config_button = QPushButton("Load Config from File")
        self.load_config_button.clicked.connect(lambda: self.load_config_from_file(None))

        layout = QVBoxLayout()
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.save_config_button)
        layout.addWidget(self.save_to_file_button)
        layout.addWidget(self.load_config_button)

        self.config_value_widgets = {}

        self.setLayout(layout)
        self.setWindowTitle("Configuration Editor")
        self.init_ui(only_z_offset)

    def init_ui(self, only_z_offset=None):
        if only_z_offset is None:
            only_z_offset = self.only_z_offset
        self.groups = {}
        for section in self.config.configurations:
            if not only_z_offset:
                group_box = CollapsibleGroupBox(section.name)
            else:
                group_box = QGroupBox(section.name)

            group_layout = QVBoxLayout()

            section_value_widgets = {}

            self.groups[str(section.id)] = group_box

            for option in section.__dict__.keys():
                if option.startswith('_') and option.endswith('_options'):
                    continue
                if option == 'id':
                    continue
                if only_z_offset and option != 'z_offset':
                    continue
                option_value = str(getattr(section, option))
                option_name = QLabel(option)
                option_layout = QHBoxLayout()
                option_layout.addWidget(option_name)
                if f'_{option}_options' in list(section.__dict__.keys()):
                    option_value_list = getattr(section,f'_{option}_options')
                    values = option_value_list.strip('[]').split(',')
                    for i in range(len(values)):
                        values[i] = values[i].strip()
                    if option_value not in values:
                        values.append(option_value)
                    combo_box = QComboBox()
                    combo_box.addItems(values)
                    combo_box.setCurrentText(option_value)
                    option_layout.addWidget(combo_box)
                    section_value_widgets[option] = combo_box
                else:
                    option_input = QLineEdit(option_value)
                    option_layout.addWidget(option_input)
                    section_value_widgets[option] = option_input
                group_layout.addLayout(option_layout)

            self.config_value_widgets[str(section.id)] = section_value_widgets
            if not only_z_offset:
                group_box.content.addLayout(group_layout)
            else:
                group_box.setLayout(group_layout)

            self.scroll_area_layout.addWidget(group_box)

    def save_config(self):
        for section in self.config.configurations:
            for option in section.__dict__.keys():
                if option.startswith("_") and option.endswith("_options"):
                    continue
                old_val = getattr(section,option)
                if option == 'id':
                    continue
                elif option == 'camera_sn':
                    option_name_in_xml = 'CameraSN'
                else:
                    option_name_in_xml = option.replace("_"," ").title().replace(" ","")
                try:
                    widget = self.config_value_widgets[str(section.id)][option]
                except KeyError:
                    continue
                if type(widget) is QLineEdit:
                    self.config.update_configuration(section.id, option_name_in_xml, widget.text())
                else:
                    self.config.update_configuration(section.id, option_name_in_xml, widget.currentText())
        self.config.configurations = []
        self.config.read_configurations()

    def save_to_file(self):
        self.save_config()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Acquisition Config File", '', "XML Files (*.xml);;All Files (*)")
        if file_path:
            self.config.write_configuration(file_path)

    def load_config_from_file(self,only_z_offset=None):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Acquisition Config File", '', "XML Files (*.xml);;All Files (*)")
        if file_path:
            self.config.config_filename = file_path
            self.config.configurations = []
            self.config.read_configurations()
            # Clear and re-initialize the UI
            self.scroll_area_widget.deleteLater()
            self.scroll_area_widget = QWidget()
            self.scroll_area_layout = QVBoxLayout()
            self.scroll_area_widget.setLayout(self.scroll_area_layout)
            self.scroll_area.setWidget(self.scroll_area_widget)
            self.init_ui(only_z_offset)


class ConfigEditor(QDialog):
    def __init__(self, config):
        super().__init__()

        self.config = config

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area_widget = QWidget()
        self.scroll_area_layout = QVBoxLayout()
        self.scroll_area_widget.setLayout(self.scroll_area_layout)
        self.scroll_area.setWidget(self.scroll_area_widget)

        self.save_config_button = QPushButton("Save Config")
        self.save_config_button.clicked.connect(self.save_config)
        self.save_to_file_button = QPushButton("Save to File")
        self.save_to_file_button.clicked.connect(self.save_to_file)
        self.load_config_button = QPushButton("Load Config from File")
        self.load_config_button.clicked.connect(self.load_config_from_file)

        layout = QVBoxLayout()
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.save_config_button)
        layout.addWidget(self.save_to_file_button)
        layout.addWidget(self.load_config_button)

        self.config_value_widgets = {}

        self.setLayout(layout)
        self.setWindowTitle("Configuration Editor")
        self.init_ui()

    def init_ui(self):
        self.groups = {}
        for section in self.config.sections():
            group_box = CollapsibleGroupBox(section)
            group_layout = QVBoxLayout()

            section_value_widgets = {}

            self.groups[section] = group_box

            for option in self.config.options(section):
                if option.startswith('_') and option.endswith('_options'):
                    continue 
                option_value = self.config.get(section, option)
                option_name = QLabel(option)
                option_layout = QHBoxLayout()
                option_layout.addWidget(option_name)
                if f'_{option}_options' in self.config.options(section):
                    option_value_list = self.config.get(section,f'_{option}_options')
                    values = option_value_list.strip('[]').split(',')
                    for i in range(len(values)):
                        values[i] = values[i].strip()
                    if option_value not in values:
                        values.append(option_value)
                    combo_box = QComboBox()
                    combo_box.addItems(values)
                    combo_box.setCurrentText(option_value)
                    option_layout.addWidget(combo_box)
                    section_value_widgets[option] = combo_box
                else:
                    option_input = QLineEdit(option_value)
                    option_layout.addWidget(option_input)
                    section_value_widgets[option] = option_input
                group_layout.addLayout(option_layout)

            self.config_value_widgets[section] = section_value_widgets
            group_box.content.addLayout(group_layout)
            self.scroll_area_layout.addWidget(group_box)

    def save_config(self):
        for section in self.config.sections():
            for option in self.config.options(section):
                if option.startswith("_") and option.endswith("_options"):
                    continue
                old_val = self.config.get(section, option)
                widget = self.config_value_widgets[section][option]
                if type(widget) is QLineEdit:
                    self.config.set(section, option, widget.text())
                else:
                    self.config.set(section, option, widget.currentText())
                if old_val != self.config.get(section,option):
                    print(self.config.get(section,option))

    def save_to_file(self):
        self.save_config()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Config File", '', "INI Files (*.ini);;All Files (*)")
        if file_path:
            with open(file_path, 'w') as configfile:
                self.config.write(configfile)

    def load_config_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Config File", '', "INI Files (*.ini);;All Files (*)")
        if file_path:
            self.config.read(file_path)
            # Clear and re-initialize the UI
            self.scroll_area_widget.deleteLater()
            self.scroll_area_widget = QWidget()
            self.scroll_area_layout = QVBoxLayout()
            self.scroll_area_widget.setLayout(self.scroll_area_layout)
            self.scroll_area.setWidget(self.scroll_area_widget)
            self.init_ui()


class ConfigEditorBackwardsCompatible(ConfigEditor):
    def __init__(self, config, original_filepath, main_window):
        super().__init__(config)
        self.original_filepath = original_filepath
        self.main_window = main_window
        
        self.apply_exit_button = QPushButton("Apply and Exit")
        self.apply_exit_button.clicked.connect(self.apply_and_exit)

        self.layout().addWidget(self.apply_exit_button)

    def apply_and_exit(self):
        self.save_config()
        with open(self.original_filepath, 'w') as configfile:
            self.config.write(configfile)
        try:
            self.main_window.close()
        except:
            pass
        self.close()


class SpinningDiskConfocalWidget(QWidget):
    def __init__(self, xlight, config_manager=None):
        super(SpinningDiskConfocalWidget,self).__init__()
        
        self.config_manager = config_manager

        self.xlight = xlight

        self.init_ui()
        
        self.dropdown_emission_filter.setCurrentText(str(self.xlight.get_emission_filter()))
        self.dropdown_dichroic.setCurrentText(str(self.xlight.get_dichroic()))

        self.dropdown_emission_filter.currentIndexChanged.connect(self.set_emission_filter)
        self.dropdown_dichroic.currentIndexChanged.connect(self.set_dichroic)
        
        self.disk_position_state = self.xlight.get_disk_position()        

        if self.disk_position_state == 1:
            self.btn_toggle_widefield.setText("Switch to Widefield")

        if self.config_manager is not None:
            if self.disk_position_state ==1:
                self.config_manager.config_filename = "confocal_configurations.xml"
            else:
                self.config_manager.config_filename = "widefield_configurations.xml"
            self.config_manager.configurations = []    
            self.config_manager.read_configurations()
        
        self.btn_toggle_widefield.clicked.connect(self.toggle_disk_position)

        self.btn_toggle_motor.clicked.connect(self.toggle_motor)

    def init_ui(self):
        
        emissionFilterLayout = QHBoxLayout()
        emissionFilterLayout.addWidget(QLabel("Emission Filter Position"))

        self.dropdown_emission_filter = QComboBox(self)
        self.dropdown_emission_filter.addItems([str(i+1) for i in range(8)])

        emissionFilterLayout.addWidget(self.dropdown_emission_filter)
        

        dichroicLayout = QHBoxLayout()
        dichroicLayout.addWidget(QLabel("Dichroic Position"))

        self.dropdown_dichroic = QComboBox(self)
        self.dropdown_dichroic.addItems([str(i+1) for i in range(5)])

        dichroicLayout.addWidget(self.dropdown_dichroic)

        dropdownLayout = QVBoxLayout()

        dropdownLayout.addLayout(dichroicLayout)
        dropdownLayout.addLayout(emissionFilterLayout)
        dropdownLayout.addStretch()
        

        self.btn_toggle_widefield = QPushButton("Switch to Confocal")

        self.btn_toggle_motor = QPushButton("Disk Motor On")
        self.btn_toggle_motor.setCheckable(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.btn_toggle_motor)

        layout.addWidget(self.btn_toggle_widefield)
        layout.addLayout(dropdownLayout)
        self.setLayout(layout)

    def disable_all_buttons(self):
        self.dropdown_emission_filter.setEnabled(False)
        self.dropdown_dichroic.setEnabled(False)
        self.btn_toggle_widefield.setEnabled(False)
        self.btn_toggle_motor.setEnabled(False)

    def enable_all_buttons(self):
        self.dropdown_emission_filter.setEnabled(True)
        self.dropdown_dichroic.setEnabled(True)
        self.btn_toggle_widefield.setEnabled(True)
        self.btn_toggle_motor.setEnabled(True)

    def toggle_disk_position(self):
        self.disable_all_buttons()
        if self.disk_position_state==1:
            self.disk_position_state = self.xlight.set_disk_position(0)
            self.btn_toggle_widefield.setText("Switch to Confocal")
        else:
            self.disk_position_state = self.xlight.set_disk_position(1)
            self.btn_toggle_widefield.setText("Switch to Widefield")
        if self.config_manager is not None:
            if self.disk_position_state ==1:
                self.config_manager.config_filename = "confocal_configurations.xml"
            else:
                self.config_manager.config_filename = "widefield_configurations.xml"
            self.config_manager.configurations = []    
            self.config_manager.read_configurations()
        self.enable_all_buttons()

    def toggle_motor(self):
        self.disable_all_buttons()
        if self.btn_toggle_motor.isChecked():
            self.xlight.set_disk_motor_state(True)
        else:
            self.xlight.set_disk_motor_state(False)
        self.enable_all_buttons()

    def set_emission_filter(self, index):
        self.disable_all_buttons()
        selected_pos = self.dropdown_emission_filter.currentText()
        self.xlight.set_emission_filter(selected_pos)
        self.enable_all_buttons()
    
    def set_dichroic(self, index):
        self.disable_all_buttons()
        selected_pos = self.dropdown_dichroic.currentText()
        self.xlight.set_dichroic(selected_pos)
        self.enable_all_buttons()


class ObjectivesWidget(QWidget):
    signal_objective_changed = Signal()

    def __init__(self, objective_store):
        super(ObjectivesWidget, self).__init__()
        self.objectiveStore = objective_store
        self.init_ui()
        self.dropdown.setCurrentText(self.objectiveStore.current_objective)

    def init_ui(self):
        self.dropdown = QComboBox(self)
        self.dropdown.addItems(self.objectiveStore.objectives_dict.keys())
        self.dropdown.currentTextChanged.connect(self.on_objective_changed)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("Objective"))
        layout.addWidget(self.dropdown)
        self.setLayout(layout)

    def on_objective_changed(self, objective_name):
        self.objectiveStore.set_current_objective(objective_name)
        self.signal_objective_changed.emit()


class FocusMapWidget(QWidget):

    def __init__(self, autofocusController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autofocusController = autofocusController
        self.init_ui()

    def init_ui(self):
        self.btn_add_to_focusmap = QPushButton("Add to focus map")
        self.btn_enable_focusmap = QPushButton("Enable focus map")
        self.btn_clear_focusmap = QPushButton("Clear focus map")
        self.fmap_coord_1 = QLabel("Focus Map Point 1: (xxx,yyy,zzz)")
        self.fmap_coord_2 = QLabel("Focus Map Point 2: (xxx,yyy,zzz)")
        self.fmap_coord_3 = QLabel("Focus Map Point 3: (xxx,yyy,zzz)")
        layout = QVBoxLayout()
        layout.addWidget(self.fmap_coord_1)
        layout.addWidget(self.fmap_coord_2)
        layout.addWidget(self.fmap_coord_3)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_add_to_focusmap)
        button_layout.addWidget(self.btn_clear_focusmap)

        layout.addLayout(button_layout)
        
        layout.addWidget(self.btn_enable_focusmap)

        self.setLayout(layout)

        self.btn_add_to_focusmap.clicked.connect(self.add_to_focusmap)
        self.btn_enable_focusmap.clicked.connect(self.enable_focusmap)
        self.btn_clear_focusmap.clicked.connect(self.clear_focusmap)

    def disable_all_buttons(self):
        self.btn_add_to_focusmap.setEnabled(False)
        self.btn_enable_focusmap.setEnabled(False)
        self.btn_clear_focusmap.setEnabled(False)

    def enable_all_buttons(self):
        self.btn_add_to_focusmap.setEnabled(True)
        self.btn_enable_focusmap.setEnabled(True)
        self.btn_clear_focusmap.setEnabled(True)

    def clear_focusmap(self):
        self.disable_all_buttons()
        self.autofocusController.clear_focus_map()
        self.update_focusmap_display()
        self.btn_enable_focusmap.setText("Enable focus map")
        self.enable_all_buttons()

    def update_focusmap_display(self):
        self.fmap_coord_1.setText("Focus Map Point 1: (xxx,yyy,zzz)")
        self.fmap_coord_2.setText("Focus Map Point 2: (xxx,yyy,zzz)")
        self.fmap_coord_3.setText("Focus Map Point 3: (xxx,yyy,zzz)")
        try:
            x,y,z = self.autofocusController.focus_map_coords[0]
            self.fmap_coord_1.setText(f"Focus Map Point 1: ({x:.3f},{y:.3f},{z:.3f})")
        except IndexError:
            pass
        try:
            x,y,z = self.autofocusController.focus_map_coords[1]
            self.fmap_coord_2.setText(f"Focus Map Point 2: ({x:.3f},{y:.3f},{z:.3f})")
        except IndexError:
            pass
        try:
            x,y,z = self.autofocusController.focus_map_coords[2]
            self.fmap_coord_3.setText(f"Focus Map Point 3: ({x:.3f},{y:.3f},{z:.3f})")
        except IndexError:
            pass



    def enable_focusmap(self):
        self.disable_all_buttons()
        if self.autofocusController.use_focus_map == False:
            self.autofocusController.set_focus_map_use(True)
        else:
            self.autofocusController.set_focus_map_use(False)
        if self.autofocusController.use_focus_map:
            self.btn_enable_focusmap.setText("Disable focus map")
        else:
            self.btn_enable_focusmap.setText("Enable focus map")
        self.enable_all_buttons()

    def add_to_focusmap(self):
        self.disable_all_buttons()
        try:
            self.autofocusController.add_current_coords_to_focus_map()
        except ValueError:
            pass
        self.update_focusmap_display()
        self.enable_all_buttons()


class CameraSettingsWidget(QFrame):

    def __init__(self, camera, include_gain_exposure_time = False, include_camera_temperature_setting = False, include_camera_auto_wb_setting = False, main=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.camera = camera
        self.add_components(include_gain_exposure_time,include_camera_temperature_setting,include_camera_auto_wb_setting)        
        # set frame style
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self,include_gain_exposure_time,include_camera_temperature_setting,include_camera_auto_wb_setting):

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
        else:
            print("setting camera's default pixel format")
            self.camera.set_pixel_format(DEFAULT_PIXEL_FORMAT)
            self.dropdown_pixelFormat.setCurrentText(DEFAULT_PIXEL_FORMAT)
        # to do: load and save pixel format in configurations

        self.entry_ROI_offset_x = QSpinBox()
        self.entry_ROI_offset_x.setValue(self.camera.OffsetX)
        self.entry_ROI_offset_x.setSingleStep(8)
        self.entry_ROI_offset_x.setFixedWidth(60)
        self.entry_ROI_offset_x.setMinimum(0)
        self.entry_ROI_offset_x.setMaximum(self.camera.WidthMax)
        self.entry_ROI_offset_x.setKeyboardTracking(False)
        self.entry_ROI_offset_y = QSpinBox()
        self.entry_ROI_offset_y.setValue(self.camera.OffsetY)
        self.entry_ROI_offset_y.setSingleStep(8)
        self.entry_ROI_offset_y.setFixedWidth(60)
        self.entry_ROI_offset_y.setMinimum(0)
        self.entry_ROI_offset_y.setMaximum(self.camera.HeightMax)
        self.entry_ROI_offset_y.setKeyboardTracking(False)
        self.entry_ROI_width = QSpinBox()
        self.entry_ROI_width.setMinimum(16)
        self.entry_ROI_width.setMaximum(self.camera.WidthMax)
        self.entry_ROI_width.setValue(self.camera.Width)
        self.entry_ROI_width.setSingleStep(8)
        self.entry_ROI_width.setFixedWidth(60)
        self.entry_ROI_width.setKeyboardTracking(False)
        self.entry_ROI_height = QSpinBox()
        self.entry_ROI_height.setSingleStep(8)
        self.entry_ROI_height.setMinimum(16)
        self.entry_ROI_height.setMaximum(self.camera.HeightMax)
        self.entry_ROI_height.setValue(self.camera.Height)
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
        self.entry_ROI_offset_x.valueChanged.connect(self.set_ROI_offset)
        self.entry_ROI_offset_y.valueChanged.connect(self.set_ROI_offset)
        self.entry_ROI_height.valueChanged.connect(self.set_Height)
        self.entry_ROI_width.valueChanged.connect(self.set_Width)

        # layout
        self.camera_layout = QVBoxLayout()
        if include_gain_exposure_time:
            exposure_line = QHBoxLayout()
            exposure_line.addWidget(QLabel('Exposure Time (ms)'))
            exposure_line.addWidget(self.entry_exposureTime)
            self.camera_layout.addLayout(exposure_line)
            gain_line = QHBoxLayout()
            gain_line.addWidget(QLabel('Analog Gain'))
            gain_line.addWidget(self.entry_analogGain)
            self.camera_layout.addLayout(gain_line)

        format_line = QHBoxLayout()
        format_line.addWidget(QLabel('Pixel Format'))
        format_line.addWidget(self.dropdown_pixelFormat)
        try:
            current_res = self.camera.resolution
            current_res_string = "x".join([str(current_res[0]),str(current_res[1])])
            res_options = [f"{res[0]}x{res[1]}" for res in self.camera.res_list]
            self.dropdown_res = QComboBox()
            self.dropdown_res.addItems(res_options)
            self.dropdown_res.setCurrentText(current_res_string)

            self.dropdown_res.currentTextChanged.connect(self.change_full_res)
            format_line.addWidget(QLabel("Full Resolution"))
            format_line.addWidget(self.dropdown_res)
        except AttributeError:
            pass
        self.camera_layout.addLayout(format_line)


        if include_camera_temperature_setting:
            temp_line = QHBoxLayout()
            temp_line.addWidget(QLabel('Set Temperature (C)'))
            temp_line.addWidget(self.entry_temperature)
            temp_line.addWidget(QLabel('Actual Temperature (C)'))
            temp_line.addWidget(self.label_temperature_measured)
            try:
                self.entry_temperature.valueChanged.connect(self.set_temperature)
                self.camera.set_temperature_reading_callback(self.update_measured_temperature)
            except AttributeError:
                pass
            self.camera_layout.addLayout(temp_line)

        roi_line = QHBoxLayout()
        roi_line.addWidget(QLabel('height'))
        roi_line.addWidget(self.entry_ROI_height)
        roi_line.addWidget(QLabel('width'))
        roi_line.addWidget(self.entry_ROI_width)
        roi_line.addWidget(QLabel('offset y'))
        roi_line.addWidget(self.entry_ROI_offset_y)
        roi_line.addWidget(QLabel('offset x'))
        roi_line.addWidget(self.entry_ROI_offset_x)
        self.camera_layout.addLayout(roi_line)

        if include_camera_auto_wb_setting:
            is_color = False
            try:
                is_color = self.camera.get_is_color()
            except AttributeError:
                pass

            if is_color is True:
                # auto white balance 
                self.btn_auto_wb = QPushButton('Auto White Balance')
                self.btn_auto_wb.setCheckable(True)
                self.btn_auto_wb.setChecked(False)
                self.btn_auto_wb.clicked.connect(self.toggle_auto_wb)
                print(self.camera.get_balance_white_auto())

                self.camera_layout.addLayout(grid_camera_setting_wb)

        self.setLayout(self.camera_layout)

    def toggle_auto_wb(self,pressed):
        # 0: OFF  1:CONTINUOUS  2:ONCE
        if pressed:
            self.camera.set_balance_white_auto(1)
        else:
            self.camera.set_balance_white_auto(0)

    def set_exposure_time(self,exposure_time):
        self.entry_exposureTime.setValue(exposure_time)

    def set_analog_gain(self,analog_gain):
        self.entry_analogGain.setValue(analog_gain)

    def set_Width(self):
        width = int(self.entry_ROI_width.value()//8)*8
        self.entry_ROI_width.blockSignals(True)
        self.entry_ROI_width.setValue(width)
        self.entry_ROI_width.blockSignals(False)
        offset_x = (self.camera.WidthMax - self.entry_ROI_width.value())/2
        offset_x = int(offset_x//8)*8
        self.entry_ROI_offset_x.blockSignals(True)
        self.entry_ROI_offset_x.setValue(offset_x)
        self.entry_ROI_offset_x.blockSignals(False)
        self.camera.set_ROI(self.entry_ROI_offset_x.value(),self.entry_ROI_offset_y.value(),self.entry_ROI_width.value(),self.entry_ROI_height.value())

    def set_Height(self):
        height = int(self.entry_ROI_height.value()//8)*8
        self.entry_ROI_height.blockSignals(True)
        self.entry_ROI_height.setValue(height)
        self.entry_ROI_height.blockSignals(False)
        offset_y = (self.camera.HeightMax - self.entry_ROI_height.value())/2
        offset_y = int(offset_y//8)*8
        self.entry_ROI_offset_y.blockSignals(True)
        self.entry_ROI_offset_y.setValue(offset_y)
        self.entry_ROI_offset_y.blockSignals(False)
        self.camera.set_ROI(self.entry_ROI_offset_x.value(),self.entry_ROI_offset_y.value(),self.entry_ROI_width.value(),self.entry_ROI_height.value())

    def set_ROI_offset(self):
    	self.camera.set_ROI(self.entry_ROI_offset_x.value(),self.entry_ROI_offset_y.value(),self.entry_ROI_width.value(),self.entry_ROI_height.value())

    def set_temperature(self):
        try:
            self.camera.set_temperature(float(self.entry_temperature.value()))
        except AttributeError:
            pass

    def update_measured_temperature(self,temperature):
        self.label_temperature_measured.setNum(temperature)

    def change_full_res(self, index):
        res_strings = self.dropdown_res.currentText().split("x")
        res_x = int(res_strings[0])
        res_y = int(res_strings[1])
        self.camera.set_resolution(res_x,res_y)
        self.entry_ROI_offset_x.blockSignals(True)
        self.entry_ROI_offset_y.blockSignals(True)
        self.entry_ROI_height.blockSignals(True)
        self.entry_ROI_width.blockSignals(True)

        self.entry_ROI_height.setMaximum(self.camera.HeightMax)
        self.entry_ROI_width.setMaximum(self.camera.WidthMax)

        self.entry_ROI_offset_x.setMaximum(self.camera.WidthMax)
        self.entry_ROI_offset_y.setMaximum(self.camera.HeightMax)
        
        self.entry_ROI_offset_x.setValue(int(8*self.camera.OffsetX//8))
        self.entry_ROI_offset_y.setValue(int(8*self.camera.OffsetY//8))
        self.entry_ROI_height.setValue(int(8*self.camera.Height//8))
        self.entry_ROI_width.setValue(int(8*self.camera.Width//8))

        self.entry_ROI_offset_x.blockSignals(False)
        self.entry_ROI_offset_y.blockSignals(False)
        self.entry_ROI_height.blockSignals(False)
        self.entry_ROI_width.blockSignals(False)


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
        self.slider_illuminationIntensity.setSingleStep(1)

        self.entry_illuminationIntensity = QDoubleSpinBox()
        self.entry_illuminationIntensity.setMinimum(0) 
        self.entry_illuminationIntensity.setMaximum(100) 
        self.entry_illuminationIntensity.setSingleStep(1)
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
        self.entry_illuminationIntensity.valueChanged.connect(lambda x: self.slider_illuminationIntensity.setValue(int(x)))
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


class PiezoWidget(QFrame):
    def __init__(self, navigationController, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_components()
        self.navigationController = navigationController

    def add_components(self):
        # Row 1: Slider and Double Spin Box for direct control
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setMinimum(0)
        self.slider.setMaximum(OBJECTIVE_PIEZO_RANGE_UM)  # Assuming maximum position is 300 um
        self.spinBox = QDoubleSpinBox(self)

        self.spinBox.setRange(0.0, OBJECTIVE_PIEZO_RANGE_UM)  # Range set from 0 to 300 um
        self.spinBox.setDecimals(0)
        self.spinBox.setSingleStep(1)  # Small step for fine control

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.slider)
        hbox1.addWidget(self.spinBox)

        # Row 2: Increment Double Spin Box, Move Up and Move Down Buttons
        self.increment_spinBox = QDoubleSpinBox(self)
        self.increment_spinBox.setRange(0.0, 100.0)  # Range for increment, adjust as needed
        self.increment_spinBox.setDecimals(0)
        self.increment_spinBox.setSingleStep(1)
        self.increment_spinBox.setValue(1.0)  # Set default increment to 1 um
        self.move_up_btn = QPushButton("Move Up", self)
        self.move_down_btn = QPushButton("Move Down", self)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.increment_spinBox)
        hbox2.addWidget(self.move_up_btn)
        hbox2.addWidget(self.move_down_btn)

        # Row 3: Home Button
        self.home_btn = QPushButton("Home to " + str(OBJECTIVE_PIEZO_HOME_UM) + " um", self)

        hbox3 = QHBoxLayout()
        hbox3.addWidget(self.home_btn)

        # Vertical Layout to include all HBoxes
        vbox = QVBoxLayout()
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox3)

        self.setLayout(vbox)

        # Connect signals and slots
        self.slider.valueChanged.connect(self.update_spinBox_from_slider)
        self.spinBox.valueChanged.connect(self.update_slider_from_spinBox)
        self.move_up_btn.clicked.connect(lambda: self.adjust_position(True))
        self.move_down_btn.clicked.connect(lambda: self.adjust_position(False))
        self.home_btn.clicked.connect(self.home)

    def update_spinBox_from_slider(self, value):
        self.spinBox.setValue(float(value))
        displacement_um = float(self.spinBox.value())
        dac = int(65535 * (displacement_um / OBJECTIVE_PIEZO_RANGE_UM))
        self.navigationController.microcontroller.analog_write_onboard_DAC(7, dac)

    def update_slider_from_spinBox(self, value):
        self.slider.setValue(int(value))

    def adjust_position(self, up):
        increment = self.increment_spinBox.value()
        current_position = self.spinBox.value()
        if up:
            new_position = current_position + increment
        else:
            new_position = current_position - increment
        self.spinBox.setValue(new_position)

    def home(self):
        self.spinBox.setValue(OBJECTIVE_PIEZO_HOME_UM)

    def update_displacement_um_display(self, displacement):
        self.spinBox.blockSignals(True)
        self.slider.blockSignals(True)
        self.spinBox.setValue(displacement)
        self.slider.setValue(int(displacement))
        self.spinBox.blockSignals(False)
        self.slider.blockSignals(False)


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
        self.flag_click_to_move = False
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
     
        self.checkbox_clickToMove = QCheckBox('Click to move')
        self.checkbox_clickToMove.setChecked(False)

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
        
        grid_line3 = QHBoxLayout()

        grid_line3_buttons = QGridLayout()
        if self.widget_configuration == 'full':
            grid_line3_buttons.addWidget(self.btn_zero_X, 0,3)
            grid_line3_buttons.addWidget(self.btn_zero_Y, 0,4)
            grid_line3_buttons.addWidget(self.btn_zero_Z, 0,5)
            grid_line3_buttons.addWidget(self.btn_home_X, 0,0)
            grid_line3_buttons.addWidget(self.btn_home_Y, 0,1)
            grid_line3_buttons.addWidget(self.btn_home_Z, 0,2)
        elif self.widget_configuration == 'malaria':
            grid_line3_buttons.addWidget(self.btn_load_slide, 0,0,1,2)
            grid_line3_buttons.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3_buttons.addWidget(self.btn_zero_Z, 0,3,1,1)
        elif self.widget_configuration == '384 well plate':
            grid_line3_buttons.addWidget(self.btn_load_slide, 0,0,1,2)
            grid_line3_buttons.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3_buttons.addWidget(self.btn_zero_Z, 0,3,1,1)
        elif self.widget_configuration == '96 well plate':
            grid_line3_buttons.addWidget(self.btn_load_slide, 0,0,1,2)
            grid_line3_buttons.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3_buttons.addWidget(self.btn_zero_Z, 0,3,1,1)
        else:
            grid_line3_buttons.addWidget(self.btn_load_slide, 0,0,1,2)
            grid_line3_buttons.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3_buttons.addWidget(self.btn_zero_Z, 0,3,1,1)

        grid_line3.addLayout(grid_line3_buttons)

        grid_line3.addWidget(self.checkbox_clickToMove)
        

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

        self.checkbox_clickToMove.stateChanged.connect(self.navigationController.set_flag_click_to_move)

        self.btn_load_slide.clicked.connect(self.switch_position)
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF")

    def toggle_navigation_controls(self, started):
        if started:
            self.flag_click_to_move = self.navigationController.get_flag_click_to_move()
            self.setEnabled_all(False)
            self.checkbox_clickToMove.setChecked(False)
        else:
            self.setEnabled_all(True)
            self.checkbox_clickToMove.setChecked(self.flag_click_to_move)

    def setEnabled_all(self, enabled):
        self.checkbox_clickToMove.setEnabled(enabled)
        self.btn_home_X.setEnabled(enabled)
        self.btn_zero_X.setEnabled(enabled)
        self.btn_moveX_forward.setEnabled(enabled)
        self.btn_moveX_backward.setEnabled(enabled)
        self.btn_home_Y.setEnabled(enabled)
        self.btn_zero_Y.setEnabled(enabled)
        self.btn_moveY_forward.setEnabled(enabled)
        self.btn_moveY_backward.setEnabled(enabled)
        self.btn_home_Z.setEnabled(enabled)
        self.btn_zero_Z.setEnabled(enabled)
        self.btn_moveZ_forward.setEnabled(enabled)
        self.btn_moveZ_backward.setEnabled(enabled)
        self.btn_load_slide.setEnabled(enabled)

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
        self.btn_load_slide.setStyleSheet("background-color: #C2FFC2")
        self.btn_load_slide.setText('To Scanning Position')
        self.btn_moveX_forward.setEnabled(False)
        self.btn_moveX_backward.setEnabled(False)
        self.btn_moveY_forward.setEnabled(False)
        self.btn_moveY_backward.setEnabled(False)
        self.btn_moveZ_forward.setEnabled(False)
        self.btn_moveZ_backward.setEnabled(False)
        self.btn_load_slide.setEnabled(True)

    def slot_slide_scanning_position_reached(self):
        self.slide_position = 'scanning'
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF")
        self.btn_load_slide.setText('To Loading Position')
        self.btn_moveX_forward.setEnabled(True)
        self.btn_moveX_backward.setEnabled(True)
        self.btn_moveY_forward.setEnabled(True)
        self.btn_moveY_backward.setEnabled(True)
        self.btn_moveZ_forward.setEnabled(True)
        self.btn_moveZ_backward.setEnabled(True)
        self.btn_load_slide.setEnabled(True)

    def switch_position(self):
        if self.slide_position != 'loading':
            self.slidePositionController.move_to_slide_loading_position()
        else:
            self.slidePositionController.move_to_slide_scanning_position()
        self.btn_load_slide.setEnabled(False)


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
        self.slider_DAC0.setSingleStep(1)
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
        self.slider_DAC1.setSingleStep(1)

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
        grid_line0.addWidget(QLabel('N Z planes'), 1,0)
        grid_line0.addWidget(self.entry_N, 1,1)
        grid_line0.addWidget(self.btn_autofocus, 2,0,1,2)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.setRowStretch(self.grid.rowCount(), 1)
        self.setLayout(self.grid)
        
        # connections
        self.btn_autofocus.clicked.connect(lambda : self.autofocusController.autofocus(False))
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


class FilterControllerWidget(QFrame):
    def __init__(self, filterController, liveController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filterController = filterController
        self.liveController = liveController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.comboBox = QComboBox()
        for i in range(1, 8):  # Assuming 7 filter positions
            self.comboBox.addItem(f"Position {i}")
        self.checkBox = QCheckBox("Disable filter wheel movement on changing Microscope Configuration", self)
            
        layout = QGridLayout()
        layout.addWidget(QLabel('Filter wheel position:'), 0,0)
        layout.addWidget(self.comboBox, 0,1)
        layout.addWidget(self.checkBox, 2,0)

        self.setLayout(layout)
        
        self.comboBox.currentIndexChanged.connect(self.on_selection_change)  # Connecting to selection change
        self.checkBox.stateChanged.connect(self.disable_movement_by_switching_channels)

    def on_selection_change(self, index):
        # The 'index' parameter is the new index of the combo box
        if index >= 0 and index <= 7:  # Making sure the index is valid
            self.filterController.set_emission_filter(index+1)

    def disable_movement_by_switching_channels(self, state):
        if state:
            self.liveController.enable_channel_auto_filter_switching = False
        else:
            self.liveController.enable_channel_auto_filter_switching = True


class StatsDisplayWidget(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initUI()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def initUI(self):
        self.layout = QVBoxLayout()
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.verticalHeader().hide()
        self.table_widget.horizontalHeader().hide()
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.layout.addWidget(self.table_widget)
        self.setLayout(self.layout)

    def display_stats(self, stats):
        print("displaying parasite stats")
        locale.setlocale(locale.LC_ALL, '')
        self.table_widget.setRowCount(len(stats))
        row = 0
        for key, value in stats.items():
            key_item = QTableWidgetItem(str(key))
            value_item = None
            try:
                value_item = QTableWidgetItem(f'{value:n}')
            except:
                value_item = QTableWidgetItem(str(value))
            self.table_widget.setItem(row,0,key_item)
            self.table_widget.setItem(row,1,value_item)
            row+=1


class MultiPointWidget(QFrame):

    signal_acquisition_started = Signal(bool)
    signal_acquisition_channels = Signal(list)
    signal_acquisition_shape = Signal(int, int, int, float, float, float)
    signal_stitcher_widget = Signal(bool)

    def __init__(self, multipointController, configurationManager = None, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multipointController = multipointController
        self.configurationManager = configurationManager
        self.well_selected = False
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
        self.entry_deltaX.setSuffix(' mm')
        self.entry_deltaX.setKeyboardTracking(False)

        self.entry_NX = QSpinBox()
        self.entry_NX.setMinimum(1) 
        self.entry_NX.setMaximum(50) 
        self.entry_NX.setSingleStep(1)
        self.entry_NX.setValue(Acquisition.NX)
        self.entry_NX.setKeyboardTracking(False)

        self.entry_deltaY = QDoubleSpinBox()
        self.entry_deltaY.setMinimum(0) 
        self.entry_deltaY.setMaximum(5) 
        self.entry_deltaY.setSingleStep(0.1)
        self.entry_deltaY.setValue(Acquisition.DX)
        self.entry_deltaY.setDecimals(3)
        self.entry_deltaY.setSuffix(' mm')
        self.entry_deltaY.setKeyboardTracking(False)
        
        self.entry_NY = QSpinBox()
        self.entry_NY.setMinimum(1) 
        self.entry_NY.setMaximum(50) 
        self.entry_NY.setSingleStep(1)
        self.entry_NY.setValue(Acquisition.NY)
        self.entry_NY.setKeyboardTracking(False)

        self.entry_deltaZ = QDoubleSpinBox()
        self.entry_deltaZ.setMinimum(0) 
        self.entry_deltaZ.setMaximum(1000) 
        self.entry_deltaZ.setSingleStep(0.2)
        self.entry_deltaZ.setValue(Acquisition.DZ)
        self.entry_deltaZ.setDecimals(3)
        self.entry_deltaZ.setSuffix(' μm')
        self.entry_deltaZ.setKeyboardTracking(False)
        
        self.entry_NZ = QSpinBox()
        self.entry_NZ.setMinimum(1)
        self.entry_NZ.setMaximum(2000)
        self.entry_NZ.setSingleStep(1)
        self.entry_NZ.setValue(1)
        self.entry_NZ.setKeyboardTracking(False)
        
        self.entry_dt = QDoubleSpinBox()
        self.entry_dt.setMinimum(0) 
        self.entry_dt.setMaximum(12*3600) 
        self.entry_dt.setSingleStep(1)
        self.entry_dt.setValue(0)
        self.entry_deltaZ.setSuffix(' s')
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

        self.checkbox_withAutofocus = QCheckBox('Contrast AF')
        self.checkbox_withAutofocus.setChecked(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_genFocusMap = QCheckBox('Generate Focus Map')
        self.checkbox_genFocusMap.setChecked(False)

        self.checkbox_withReflectionAutofocus = QCheckBox('Reflection AF')
        self.checkbox_withReflectionAutofocus.setChecked(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_stitchOutput = QCheckBox('Stitch Output')
        self.checkbox_stitchOutput.setChecked(False)

        self.multipointController.set_reflection_af_flag(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.btn_startAcquisition = QPushButton('Start\n Acquisition ')
        self.btn_startAcquisition.setStyleSheet("background-color: #C2C2FF")
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
        grid_line2.addWidget(QLabel('dx'), 0,0)
        grid_line2.addWidget(self.entry_deltaX, 0,1)
        grid_line2.addWidget(QLabel('Nx'), 0,3)
        grid_line2.addWidget(self.entry_NX, 0,4)
        grid_line2.addWidget(QLabel('dy'), 0,6)
        grid_line2.addWidget(self.entry_deltaY, 0,7)
        grid_line2.addWidget(QLabel('Ny'), 0,9)
        grid_line2.addWidget(self.entry_NY, 0,10)

        grid_line2.addWidget(QLabel('dz'), 1,0)
        grid_line2.addWidget(self.entry_deltaZ, 1,1)
        grid_line2.addWidget(QLabel('Nz'), 1,3)
        grid_line2.addWidget(self.entry_NZ, 1,4)
        grid_line2.addWidget(QLabel('dt'), 1,6)
        grid_line2.addWidget(self.entry_dt, 1,7)
        grid_line2.addWidget(QLabel('Nt'), 1,9)
        grid_line2.addWidget(self.entry_Nt, 1,10)

        grid_line2.setColumnStretch(2, 1)
        grid_line2.setColumnStretch(5, 1)
        grid_line2.setColumnStretch(8, 1)

        grid_af = QVBoxLayout()
        grid_af.addWidget(self.checkbox_withAutofocus)
        grid_af.addWidget(self.checkbox_genFocusMap)
        if SUPPORT_LASER_AUTOFOCUS:
            grid_af.addWidget(self.checkbox_withReflectionAutofocus)
        if ENABLE_STITCHER:
            grid_af.addWidget(self.checkbox_stitchOutput)

        grid_line3 = QHBoxLayout()
        grid_line3.addWidget(self.list_configurations)
        # grid_line3.addWidget(self.checkbox_withAutofocus)
        grid_line3.addLayout(grid_af)
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
        self.checkbox_withReflectionAutofocus.stateChanged.connect(self.multipointController.set_reflection_af_flag)
        self.checkbox_genFocusMap.stateChanged.connect(self.multipointController.set_gen_focus_map_flag)
        self.checkbox_stitchOutput.toggled.connect(self.display_stitcher_widget)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)
        self.list_configurations.itemSelectionChanged.connect(self.emit_selected_channels)

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

    def set_well_selected(self, selected):
        self.well_selected = selected

    def emit_selected_channels(self):
        selected_channels = [item.text() for item in self.list_configurations.selectedItems()]
        print(selected_channels)
        self.signal_acquisition_channels.emit(selected_channels)

    def toggle_acquisition(self,pressed):
        if self.base_path_is_set == False:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if self.well_selected == False and self.multipointController.scanCoordinates.format != 0:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please select a well to scan first")
            msg.exec_()
            return
        if not self.list_configurations.selectedItems(): # no channel selected
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please select at least one imaging channel first")
            msg.exec_()
            return
        if pressed:
            # @@@ to do: add a widgetManger to enable and disable widget 
            # @@@ to do: emit signal to widgetManager to disable other widgets
            self.setEnabled_all(False)

            # set parameters
            if self.multipointController.scanCoordinates is not None:
                self.multipointController.scanCoordinates.grid_skip_positions = []
            self.multipointController.set_deltaX(self.entry_deltaX.value())
            self.multipointController.set_deltaY(self.entry_deltaY.value())
            self.multipointController.set_deltaZ(self.entry_deltaZ.value())
            self.multipointController.set_deltat(self.entry_dt.value())
            self.multipointController.set_NX(self.entry_NX.value())
            self.multipointController.set_NY(self.entry_NY.value())
            self.multipointController.set_NZ(self.entry_NZ.value())
            self.multipointController.set_Nt(self.entry_Nt.value())
            self.multipointController.set_af_flag(self.checkbox_withAutofocus.isChecked())
            self.multipointController.set_reflection_af_flag(self.checkbox_withReflectionAutofocus.isChecked())
            self.multipointController.set_base_path(self.lineEdit_savingDir.text())
            self.multipointController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.multipointController.start_new_experiment(self.lineEdit_experimentID.text())

            # emit acquisition data
            self.signal_acquisition_started.emit(True)
            self.signal_acquisition_shape.emit(self.entry_NX.value(),
                                               self.entry_NY.value(),
                                               self.entry_NZ.value(),
                                               self.entry_deltaX.value(),
                                               self.entry_deltaY.value(),
                                               self.entry_deltaZ.value())

            self.multipointController.run_acquisition()
        else:
            self.multipointController.request_abort_aquisition()
            self.setEnabled_all(True)

    def acquisition_is_finished(self):
        self.signal_acquisition_started.emit(False)
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
        self.checkbox_withReflectionAutofocus.setEnabled(enabled)
        self.checkbox_genFocusMap.setEnabled(enabled)
        self.checkbox_stitchOutput.setEnabled(enabled)
        if exclude_btn_startAcquisition is not True:
            self.btn_startAcquisition.setEnabled(enabled)

    def display_stitcher_widget(self, checked):
        self.signal_stitcher_widget.emit(checked)

    def disable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(False)

    def enable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(True)


class MultiPointWidget2(QFrame):

    signal_acquisition_started = Signal(bool)
    signal_acquisition_channels = Signal(list)
    signal_acquisition_shape = Signal(int, int, int, float, float, float)
    signal_stitcher_widget = Signal(bool)

    def __init__(self, navigationController, navigationViewer, multipointController, configurationManager = None, main=None, scanCoordinates=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_used_locations = None
        self.last_used_location_ids = None
        self.multipointController = multipointController
        self.configurationManager = configurationManager
        self.navigationController = navigationController
        self.navigationViewer = navigationViewer
        self.scanCoordinates = scanCoordinates
        self.base_path_is_set = False
        self.location_list = np.empty((0, 3), dtype=float)
        self.location_ids = np.empty((0,), dtype='<U20')
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.acquisition_in_place=False

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

        self.dropdown_location_list = QComboBox()
        self.btn_add = QPushButton('Add')
        self.btn_remove = QPushButton('Remove')
        self.btn_previous = QPushButton('Previous')
        self.btn_next = QPushButton('Next')
        self.btn_clear = QPushButton('Clear')

        self.btn_load_last_executed = QPushButton('Prev Used Locations')

        self.btn_export_locations = QPushButton('Export Location List')
        self.btn_import_locations = QPushButton('Import Location List')

        # editable points table
        self.table_location_list = QTableWidget()
        self.table_location_list.setColumnCount(4)
        header_labels = ['x', 'y', 'z', 'ID']
        self.table_location_list.setHorizontalHeaderLabels(header_labels)
        self.btn_show_table_location_list = QPushButton('Open/Edit')

        self.entry_deltaX = QDoubleSpinBox()
        self.entry_deltaX.setMinimum(0) 
        self.entry_deltaX.setMaximum(5) 
        self.entry_deltaX.setSingleStep(0.1)
        self.entry_deltaX.setValue(Acquisition.DX)
        self.entry_deltaX.setDecimals(3)
        self.entry_deltaX.setSuffix(' mm')
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
        self.entry_deltaY.setSuffix(' mm')
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
        self.entry_deltaZ.setSuffix(' μm')
        self.entry_deltaZ.setKeyboardTracking(False)
        
        self.entry_NZ = QSpinBox()
        self.entry_NZ.setMinimum(1)
        self.entry_NZ.setMaximum(2000)
        self.entry_NZ.setSingleStep(1)
        self.entry_NZ.setValue(1)
        self.entry_NZ.setKeyboardTracking(False)
        
        self.entry_dt = QDoubleSpinBox()
        self.entry_dt.setMinimum(0)
        self.entry_dt.setMaximum(12*3600)
        self.entry_dt.setSingleStep(1)
        self.entry_dt.setValue(0)
        self.entry_dt.setSuffix(' s')
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

        self.checkbox_withAutofocus = QCheckBox('Contrast AF')
        self.checkbox_withAutofocus.setChecked(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_withReflectionAutofocus = QCheckBox('Reflection AF')
        self.checkbox_withReflectionAutofocus.setChecked(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_reflection_af_flag(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_stitchOutput = QCheckBox('Stitch Output')
        self.checkbox_stitchOutput.setChecked(False)

        self.btn_startAcquisition = QPushButton('Start\n Acquisition ')
        self.btn_startAcquisition.setStyleSheet("background-color: #C2C2FF")
        self.btn_startAcquisition.setCheckable(True)
        self.btn_startAcquisition.setChecked(False)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('Saving Path'))
        grid_line0.addWidget(self.lineEdit_savingDir, 0,1)
        grid_line0.addWidget(self.btn_setSavingDir, 0,2)
        grid_line0.addWidget(QLabel('ID'), 0,3)
        grid_line0.addWidget(self.lineEdit_experimentID,0,4)

        grid_line4 = QGridLayout()
        grid_line4.addWidget(QLabel('Location List'),0,0)
        grid_line4.addWidget(self.dropdown_location_list,0,1,1,2)
        grid_line4.addWidget(self.btn_clear,0,3)
        grid_line4.addWidget(self.btn_show_table_location_list,0,4)

        grid_line3point5 = QGridLayout()
        grid_line3point5.addWidget(self.btn_add,0,0)
        grid_line3point5.addWidget(self.btn_remove,0,1)
        grid_line3point5.addWidget(self.btn_next,0,2)
        grid_line3point5.addWidget(self.btn_previous,0,3)
        #grid_line3point5.addWidget(self.btn_load_last_executed,0,4)

        grid_line3point75 = QGridLayout()
        grid_line3point75.addWidget(self.btn_import_locations,0,0)
        grid_line3point75.addWidget(self.btn_export_locations,0,1)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('dx'), 0,0)
        grid_line2.addWidget(self.entry_deltaX, 0,1)
        grid_line2.addWidget(QLabel('Nx'), 0,3)
        grid_line2.addWidget(self.entry_NX, 0,4)
        grid_line2.addWidget(QLabel('dy'), 0,6)
        grid_line2.addWidget(self.entry_deltaY, 0,7)
        grid_line2.addWidget(QLabel('Ny'), 0,9)
        grid_line2.addWidget(self.entry_NY, 0,10)

        grid_line2.addWidget(QLabel('dz'), 1,0)
        grid_line2.addWidget(self.entry_deltaZ, 1,1)
        grid_line2.addWidget(QLabel('Nz'), 1,3)
        grid_line2.addWidget(self.entry_NZ, 1,4)
        grid_line2.addWidget(QLabel('dt'), 1,6)
        grid_line2.addWidget(self.entry_dt, 1,7)
        grid_line2.addWidget(QLabel('Nt'), 1,9)
        grid_line2.addWidget(self.entry_Nt, 1,10)

        grid_line2.setColumnStretch(2, 1)
        grid_line2.setColumnStretch(5, 1)
        grid_line2.setColumnStretch(8, 1)

        grid_af = QVBoxLayout()
        grid_af.addWidget(self.checkbox_withAutofocus)
        if SUPPORT_LASER_AUTOFOCUS:
            grid_af.addWidget(self.checkbox_withReflectionAutofocus)
        if ENABLE_STITCHER:
            grid_af.addWidget(self.checkbox_stitchOutput)

        grid_line3 = QHBoxLayout()
        grid_line3.addWidget(self.list_configurations)
        # grid_line3.addWidget(self.checkbox_withAutofocus)
        grid_line3.addLayout(grid_af)
        grid_line3.addWidget(self.btn_startAcquisition)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        # self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line4,1,0)
        self.grid.addLayout(grid_line3point5,2,0)
        self.grid.addLayout(grid_line3point75,3,0)
        # self.grid.addLayout(grid_line5,2,0)
        self.grid.addLayout(grid_line2,4,0)
        self.grid.addLayout(grid_line3,5,0)
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
        self.checkbox_withReflectionAutofocus.stateChanged.connect(self.multipointController.set_reflection_af_flag)
        self.checkbox_stitchOutput.toggled.connect(self.display_stitcher_widget)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)
        self.list_configurations.itemSelectionChanged.connect(self.emit_selected_channels)

        self.btn_add.clicked.connect(self.add_location)
        self.btn_remove.clicked.connect(self.remove_location)
        self.btn_previous.clicked.connect(self.previous)
        self.btn_next.clicked.connect(self.next)
        self.btn_clear.clicked.connect(self.clear)
        self.btn_load_last_executed.clicked.connect(self.load_last_used_locations)
        self.btn_export_locations.clicked.connect(self.export_location_list)
        self.btn_import_locations.clicked.connect(self.import_location_list)

        self.table_location_list.cellClicked.connect(self.cell_was_clicked)
        self.table_location_list.cellChanged.connect(self.cell_was_changed)
        self.btn_show_table_location_list.clicked.connect(self.table_location_list.show)

        self.dropdown_location_list.currentIndexChanged.connect(self.go_to)

        self.shortcut = QShortcut(QKeySequence(";"), self)
        self.shortcut.activated.connect(self.btn_add.click)

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

    def emit_selected_channels(self):
        selected_channels = [item.text() for item in self.list_configurations.selectedItems()]
        self.signal_acquisition_channels.emit(selected_channels)

    def display_stitcher_widget(self, checked):
        self.signal_stitcher_widget.emit(checked)

    def toggle_acquisition(self,pressed):
        if self.base_path_is_set == False:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if not self.list_configurations.selectedItems(): # no channel selected
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please select at least one imaging channel first")
            msg.exec_()
            return
        if pressed:
            # @@@ to do: add a widgetManger to enable and disable widget 
            # @@@ to do: emit signal to widgetManager to disable other widgets
            # clear skip positions
            if hasattr(self.multipointController, 'scanCoordinates') and self.multipointController.scanCoordinates:
                self.multipointController.scanCoordinates.grid_skip_positions = []

            # add the current location to the location list if the list is empty
            if len(self.location_list) == 0:
                self.add_location()
                self.acquisition_in_place = True
                self.multipointController.location_list = self.location_list

            self.setEnabled_all(False)
            # set parameters
            self.multipointController.set_deltaX(self.entry_deltaX.value())
            self.multipointController.set_deltaY(self.entry_deltaY.value())
            self.multipointController.set_deltaZ(self.entry_deltaZ.value())
            self.multipointController.set_deltat(self.entry_dt.value())
            self.multipointController.set_NX(self.entry_NX.value())
            self.multipointController.set_NY(self.entry_NY.value())
            self.multipointController.set_NZ(self.entry_NZ.value())
            self.multipointController.set_Nt(self.entry_Nt.value())
            self.multipointController.set_af_flag(self.checkbox_withAutofocus.isChecked())
            self.multipointController.set_reflection_af_flag(self.checkbox_withReflectionAutofocus.isChecked())
            self.multipointController.set_base_path(self.lineEdit_savingDir.text())
            self.multipointController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.multipointController.start_new_experiment(self.lineEdit_experimentID.text())

            # emit signals
            self.signal_acquisition_started.emit(True)
            self.signal_acquisition_shape.emit(self.entry_NX.value(),
                                               self.entry_NY.value(),
                                               self.entry_NZ.value(),
                                               self.entry_deltaX.value(),
                                               self.entry_deltaY.value(),
                                               self.entry_deltaZ.value())

            self.multipointController.run_acquisition(location_list=self.location_list)
        else:
            self.multipointController.request_abort_aquisition()
            self.setEnabled_all(True)

    def load_last_used_locations(self):
        if self.last_used_locations is None or len(self.last_used_locations) == 0:
            return
        self.clear_only_location_list()

        for row, row_ind in zip(self.last_used_locations, self.last_used_location_ids):
            x = row[0]
            y = row[1]
            z = row[2]
            name = row_ind[0]
            if not np.any(np.all(self.location_list[:, :2] == [x, y], axis=1)):
                location_str = 'x: ' + str(round(x,3)) + ' mm, y: ' + str(round(y,3)) + ' mm, z: ' + str(round(1000*z,1)) + ' um'
                self.dropdown_location_list.addItem(location_str)
                self.location_list = np.vstack((self.location_list, [[x,y,z]]))
                self.location_ids = np.append(self.location_ids, name)
                self.table_location_list.insertRow(self.table_location_list.rowCount())
                self.table_location_list.setItem(self.table_location_list.rowCount()-1,0, QTableWidgetItem(str(round(x,3))))
                self.table_location_list.setItem(self.table_location_list.rowCount()-1,1, QTableWidgetItem(str(round(y,3))))
                self.table_location_list.setItem(self.table_location_list.rowCount()-1,2, QTableWidgetItem(str(round(z*1000,1))))
                self.table_location_list.setItem(self.table_location_list.rowCount()-1,3, QTableWidgetItem(name))
                index = self.dropdown_location_list.count() - 1
                self.dropdown_location_list.setCurrentIndex(index)
                print(self.location_list)
                self.navigationViewer.register_fov_to_image(x,y)
            else:
                print("Duplicate values not added based on x and y.")
                #to-do: update z coordinate

    def acquisition_is_finished(self):
        if not self.acquisition_in_place:
            self.last_used_locations = self.location_list.copy()
            self.last_used_location_ids = self.location_ids.copy()
        else:
            self.clear_only_location_list()
            self.acquisition_in_place = False
        self.signal_acquisition_started.emit(False)
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
        self.checkbox_withReflectionAutofocus.setEnabled(enabled)
        self.checkbox_stitchOutput.setEnabled(enabled)
        if exclude_btn_startAcquisition is not True:
            self.btn_startAcquisition.setEnabled(enabled)

    def disable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(False)

    def enable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(True)

    def add_location(self):
        x = self.navigationController.x_pos_mm
        y = self.navigationController.y_pos_mm
        z = self.navigationController.z_pos_mm
        name = ''
        if self.scanCoordinates is not None:
            name = self.create_point_id()
        
        if not np.any(np.all(self.location_list[:, :2] == [x, y], axis=1)):
            location_str = 'x: ' + str(round(x,3)) + ' mm, y: ' + str(round(y,3)) + ' mm, z: ' + str(round(1000*z,1)) + ' um'
            self.dropdown_location_list.addItem(location_str)
            index = self.dropdown_location_list.count() - 1
            self.dropdown_location_list.setCurrentIndex(index)
            self.location_list = np.vstack((self.location_list, [[self.navigationController.x_pos_mm,self.navigationController.y_pos_mm,self.navigationController.z_pos_mm]]))
            print(self.location_list)
            self.location_ids = np.append(self.location_ids, name)
            self.table_location_list.insertRow(self.table_location_list.rowCount())
            self.table_location_list.setItem(self.table_location_list.rowCount()-1,0, QTableWidgetItem(str(round(x,3))))
            self.table_location_list.setItem(self.table_location_list.rowCount()-1,1, QTableWidgetItem(str(round(y,3))))
            self.table_location_list.setItem(self.table_location_list.rowCount()-1,2, QTableWidgetItem(str(round(1000*z,1))))
            self.table_location_list.setItem(self.table_location_list.rowCount()-1,3, QTableWidgetItem(name))
            self.navigationViewer.register_fov_to_image(x,y)
        else:
            print("Duplicate values not added based on x and y.")
            #to-do: update z coordinate

    def create_point_id(self):
        self.scanCoordinates.get_selected_wells()
        if len(self.scanCoordinates.name) == 0:
            print('Select a well first.')
            return None
        
        name = self.scanCoordinates.name[0]
        location_split_names = [int(x.split('-')[1]) for x in self.location_ids if x.split('-')[0] == name]
        if len(location_split_names) > 0:
            new_id = f'{name}-{np.max(location_split_names)+1}'
        else:
            new_id = f'{name}-0'
        return new_id

    def remove_location(self):
        index = self.dropdown_location_list.currentIndex()
        if index >=0:
            self.dropdown_location_list.removeItem(index)
            self.table_location_list.removeRow(index)
            x = self.location_list[index,0]
            y = self.location_list[index,1]
            z = self.location_list[index,2]
            self.navigationViewer.deregister_fov_to_image(x,y)
            self.location_list = np.delete(self.location_list, index, axis=0)
            self.location_ids = np.delete(self.location_ids, index, axis=0)
            if len(self.location_list) == 0:
                self.navigationViewer.clear_slide()
            print(self.location_list)

    def next(self):
        index = self.dropdown_location_list.currentIndex()
        max_index = self.dropdown_location_list.count() - 1
        index = min(index + 1, max_index)
        self.dropdown_location_list.setCurrentIndex(index)
        x = self.location_list[index,0]
        y = self.location_list[index,1]
        z = self.location_list[index,2]
        self.navigationController.move_x_to(x)
        self.navigationController.move_y_to(y)
        self.navigationController.move_z_to(z)

    def previous(self):
        index = self.dropdown_location_list.currentIndex()
        index = max(index - 1, 0)
        self.dropdown_location_list.setCurrentIndex(index)
        x = self.location_list[index,0]
        y = self.location_list[index,1]
        z = self.location_list[index,2]
        self.navigationController.move_x_to(x)
        self.navigationController.move_y_to(y)
        self.navigationController.move_z_to(z)

    def clear(self):
        self.location_list = np.empty((0, 3), dtype=float)
        self.location_ids = np.empty((0,), dtype=str)
        self.dropdown_location_list.clear()
        self.navigationViewer.clear_slide()
        self.table_location_list.setRowCount(0)

    def clear_only_location_list(self):
        self.location_list = np.empty((0,3),dtype=float)
        self.location_ids = np.empty((0,),dtype=str)
        self.dropdown_location_list.clear()
        self.table_location_list.setRowCount(0)

    def go_to(self,index):
        if index != -1:
            if index < len(self.location_list): # to avoid giving errors when adding new points
                x = self.location_list[index,0]
                y = self.location_list[index,1]
                z = self.location_list[index,2]
                self.navigationController.move_x_to(x)
                self.navigationController.move_y_to(y)
                self.navigationController.move_z_to(z)
                self.table_location_list.selectRow(index)

    def cell_was_clicked(self,row,column):

        self.dropdown_location_list.setCurrentIndex(row)

    def cell_was_changed(self,row,column):
        x= self.location_list[row,0]
        y= self.location_list[row,1]
        self.navigationViewer.deregister_fov_to_image(x,y)
    
        val_edit = self.table_location_list.item(row,column).text()
        if column < 2:
            val_edit = float(val_edit)
            self.location_list[row,column] = val_edit
        elif column == 2:
            z = float(val_edit)/1000
            self.location_list[row,column] = z
        else:
            self.location_ids[row] = val_edit
        
        self.navigationViewer.register_fov_to_image(self.location_list[row,0], self.location_list[row,1])
        location_str = 'x: ' + str(round(self.location_list[row,0],3)) + ' mm, y: ' + str(round(self.location_list[row,1],3)) + ' mm, z: ' + str(1000*round(self.location_list[row,2],3)) + ' um'
        self.dropdown_location_list.setItemText(row, location_str)
        self.go_to(row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.add_location()
        else:
            super().keyPressEvent(event)

    def _update_z(self,index,z_mm):
        self.location_list[index,2] = z_mm
        location_str = 'x: ' + str(round(self.location_list[index,0],3)) + ' mm, y: ' + str(round(self.location_list[index,1],3)) + ' mm, z: ' + str(round(1000*z_mm,1)) + ' um'
        self.dropdown_location_list.setItemText(index, location_str)

    def export_location_list(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Location List", '', "CSV Files (*.csv);;All Files (*)")
        if file_path:
            location_list_df = pd.DataFrame(self.location_list,columns=['x (mm)','y (mm)', 'z (um)'])
            location_list_df['ID'] = self.location_ids
            location_list_df['i'] = 0
            location_list_df['j'] = 0
            location_list_df['k'] = 0
            location_list_df.to_csv(file_path,index=False,header=True)

    def import_location_list(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Location List", '', "CSV Files (*.csv);;All Files (*)")
        if file_path:
            location_list_df = pd.read_csv(file_path)
            location_list_df_relevant = None
            try:
                location_list_df_relevant = location_list_df[['x (mm)', 'y (mm)', 'z (um)']]
            except KeyError:
                print("Improperly formatted location list being imported")
                return
            if 'ID' in location_list_df.columns:
                location_list_df_relevant['ID'] = location_list_df['ID'].astype(str)
            else:
                location_list_df_relevant['ID'] = 'None'
            self.clear_only_location_list()
            for index, row in location_list_df_relevant.iterrows():
                x = row['x (mm)']
                y = row['y (mm)']
                z = row['z (um)']
                name = row['ID']
                if not np.any(np.all(self.location_list[:, :2] == [x, y], axis=1)):
                    location_str = 'x: ' + str(round(x,3)) + ' mm, y: ' + str(round(y,3)) + ' mm, z: ' + str(round(1000*z,1)) + ' um'
                    self.dropdown_location_list.addItem(location_str)
                    index = self.dropdown_location_list.count() - 1
                    self.dropdown_location_list.setCurrentIndex(index)
                    self.location_list = np.vstack((self.location_list, [[x,y,z]]))
                    self.location_ids = np.append(self.location_ids, name)
                    self.table_location_list.insertRow(self.table_location_list.rowCount())
                    self.table_location_list.setItem(self.table_location_list.rowCount()-1,0, QTableWidgetItem(str(round(x,3))))
                    self.table_location_list.setItem(self.table_location_list.rowCount()-1,1, QTableWidgetItem(str(round(y,3))))
                    self.table_location_list.setItem(self.table_location_list.rowCount()-1,2, QTableWidgetItem(str(round(1000*z,1))))
                    self.table_location_list.setItem(self.table_location_list.rowCount()-1,3, QTableWidgetItem(name))
                    self.navigationViewer.register_fov_to_image(x,y)
                else:
                    print("Duplicate values not added based on x and y.")
            print(self.location_list)


class MultiPointWidgetGrid(QFrame):

    signal_acquisition_started = Signal(bool)
    signal_acquisition_channels = Signal(list)
    signal_acquisition_shape = Signal(int, int, int, float, float, float)
    signal_update_navigation_viewer = Signal()
    signal_stitcher_widget = Signal(bool)

    def __init__(self, navigationController, navigationViewer, multipointController, objectiveStore, configurationManager, scanCoordinates, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objectiveStore = objectiveStore
        self.multipointController = multipointController
        self.navigationController = navigationController
        self.navigationViewer = navigationViewer
        self.scanCoordinates = scanCoordinates
        self.configurationManager = configurationManager
        self.base_path_is_set = False
        self.well_selected = False
        self.use_coordinate_acquisition = True
        self.num_regions = 0
        self.region_coordinates = {}
        self.region_coordinates_map = {}
        self.acquisition_start_time = None
        self.eta_seconds = 0
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.set_default_scan_size()

    def add_components(self):
        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))

        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setText(DEFAULT_SAVING_PATH)
        self.multipointController.set_base_path(DEFAULT_SAVING_PATH)
        self.base_path_is_set = True

        self.lineEdit_experimentID = QLineEdit()

        # Update scan size entry
        self.entry_scan_size = QDoubleSpinBox()
        self.entry_scan_size.setRange(0.1, 100)
        self.entry_scan_size.setValue(1)
        self.entry_scan_size.setSuffix(" mm")

        self.entry_well_coverage = QDoubleSpinBox()
        self.entry_well_coverage.setRange(1, 1000)
        self.entry_well_coverage.setValue(100)
        self.entry_well_coverage.setSuffix(" %")

        self.entry_overlap = QDoubleSpinBox()
        self.entry_overlap.setRange(0, 99)
        self.entry_overlap.setValue(10)
        self.entry_overlap.setSuffix(" %")

        self.combobox_z_stack = QComboBox()
        self.combobox_z_stack.addItems(['Above', 'Center', 'Below'])
        
        # Add z-min and z-max entries
        self.entry_minZ = QDoubleSpinBox()
        self.entry_minZ.setMinimum(SOFTWARE_POS_LIMIT.Z_NEGATIVE * 1000)  # Convert to μm
        self.entry_minZ.setMaximum(SOFTWARE_POS_LIMIT.Z_POSITIVE * 1000)  # Convert to μm
        self.entry_minZ.setSingleStep(1)  # Step by 1 μm
        self.entry_minZ.setValue(self.navigationController.z_pos_mm * 1000)  # Set to minimum
        self.entry_minZ.setSuffix(" μm")

        self.set_minZ_button = QPushButton('Set')
        self.set_minZ_button.clicked.connect(self.set_z_min)

        self.entry_maxZ = QDoubleSpinBox()
        self.entry_maxZ.setMinimum(SOFTWARE_POS_LIMIT.Z_NEGATIVE * 1000)  # Convert to μm
        self.entry_maxZ.setMaximum(SOFTWARE_POS_LIMIT.Z_POSITIVE * 1000)  # Convert to μm
        self.entry_maxZ.setSingleStep(1)  # Step by 1 μm
        self.entry_maxZ.setValue(self.navigationController.z_pos_mm * 1000)  # Set to maximum
        self.entry_maxZ.setSuffix(" μm")

        self.set_maxZ_button = QPushButton('Set')
        self.set_maxZ_button.clicked.connect(self.set_z_max)

        self.entry_deltaZ = QDoubleSpinBox()
        self.entry_deltaZ.setMinimum(0)
        self.entry_deltaZ.setMaximum(1000)
        self.entry_deltaZ.setSingleStep(0.2)
        self.entry_deltaZ.setValue(Acquisition.DZ)
        self.entry_deltaZ.setDecimals(3)
        self.entry_deltaZ.setEnabled(False)
        self.entry_deltaZ.setSuffix(" μm")

        self.entry_NZ = QSpinBox()
        self.entry_NZ.setMinimum(1) 
        self.entry_NZ.setMaximum(2000) 
        self.entry_NZ.setSingleStep(1)
        self.entry_NZ.setValue(1)

        self.entry_dt = QDoubleSpinBox()
        self.entry_dt.setMinimum(0)
        self.entry_dt.setMaximum(12*3600)
        self.entry_dt.setSingleStep(1)
        self.entry_dt.setValue(0)
        self.entry_dt.setSuffix(" s")

        self.entry_Nt = QSpinBox()
        self.entry_Nt.setMinimum(1)
        self.entry_Nt.setMaximum(50000)
        self.entry_Nt.setSingleStep(1)
        self.entry_Nt.setValue(1)

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection)

        # Add a combo box for shape selection
        self.combobox_shape = QComboBox()
        self.combobox_shape.addItems(['Square', 'Circle'])

        self.checkbox_withAutofocus = QCheckBox('Contrast AF')
        self.checkbox_withAutofocus.setChecked(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_withReflectionAutofocus = QCheckBox('Reflection AF')
        self.checkbox_withReflectionAutofocus.setChecked(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_reflection_af_flag(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_genFocusMap = QCheckBox('Generate Focus Map')
        self.checkbox_genFocusMap.setChecked(False)

        # Add a checkbox for coordinate-based acquisition
        self.checkbox_useCoordinateAcquisition = QCheckBox('Use Coordinates')
        self.checkbox_useCoordinateAcquisition.setChecked(self.use_coordinate_acquisition)
        self.checkbox_useCoordinateAcquisition.stateChanged.connect(lambda state: setattr(self, 'use_coordinate_acquisition', bool(state)))

        self.checkbox_stitchOutput = QCheckBox('Stitch Output')
        self.checkbox_stitchOutput.setChecked(False)

        self.btn_startAcquisition = QPushButton('Start\n Acquisition ')
        self.btn_startAcquisition.setStyleSheet("background-color: #C2C2FF")
        self.btn_startAcquisition.setCheckable(True)
        self.btn_startAcquisition.setChecked(False)

        self.progress_label = QLabel('Region -/-')
        self.progress_bar = QProgressBar()
        self.eta_label = QLabel('--:--:--')
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.eta_label.setVisible(False)
        self.eta_timer = QTimer()

        # Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        #  Saving Path
        saving_path_layout = QHBoxLayout()
        saving_path_layout.addWidget(QLabel('Saving Path'))
        saving_path_layout.addWidget(self.lineEdit_savingDir)
        saving_path_layout.addWidget(self.btn_setSavingDir)
        main_layout.addLayout(saving_path_layout)

        # Experiment ID and Scan Shape
        
        row_1_layout = QHBoxLayout() 
        row_1_layout.addWidget(QLabel('Experiment ID'))
        row_1_layout.addWidget(self.lineEdit_experimentID)
        row_1_layout.addWidget(QLabel('Shape'))
        row_1_layout.addWidget(self.combobox_shape)
        # row_1_layout.addWidget(QLabel('Z-Stack'))
        # row_1_layout.addWidget(self.combobox_z_stack)
        main_layout.addLayout(row_1_layout)

        # Well Coverage, Scan Size, and Overlap
        row_4_layout = QHBoxLayout()
        row_4_layout.addWidget(QLabel('Size'))
        row_4_layout.addWidget(self.entry_scan_size)
        row_4_layout.addStretch(1)
        row_4_layout.addWidget(QLabel('Well Coverage'))
        row_4_layout.addWidget(self.entry_well_coverage)
        row_4_layout.addStretch(1)
        row_4_layout.addWidget(QLabel('FOV Overlap'))
        row_4_layout.addWidget(self.entry_overlap)
        main_layout.addLayout(row_4_layout)

        # Z and T
        row_2_3_layout = QGridLayout()
        row_2_3_layout.addWidget(self.set_minZ_button, 0, 0)
        row_2_3_layout.addWidget(QLabel('Z-min'), 0, 1)
        row_2_3_layout.addWidget(self.entry_minZ, 0, 2)
        row_2_3_layout.addWidget(QLabel('dz'), 0, 4)
        row_2_3_layout.addWidget(self.entry_deltaZ, 0, 5)
        row_2_3_layout.addWidget(QLabel('Nz'), 0, 7)
        row_2_3_layout.addWidget(self.entry_NZ, 0, 8)
        
        row_2_3_layout.addWidget(self.set_maxZ_button, 1, 0)
        row_2_3_layout.addWidget(QLabel('Z-max'), 1, 1)
        row_2_3_layout.addWidget(self.entry_maxZ, 1, 2)
        row_2_3_layout.addWidget(QLabel('dt'), 1, 4)
        row_2_3_layout.addWidget(self.entry_dt, 1, 5)
        row_2_3_layout.addWidget(QLabel('Nt'), 1, 7)
        row_2_3_layout.addWidget(self.entry_Nt, 1, 8)
        row_2_3_layout.setColumnStretch(3, 1)
        row_2_3_layout.setColumnStretch(6, 1)


        main_layout.addLayout(row_2_3_layout)

        # Configurations list, AF options, Start Acquisition button
        row_bottom_layout = QHBoxLayout()
        row_bottom_layout.addWidget(self.list_configurations)

        options_layout = QVBoxLayout()
        options_layout.addWidget(self.checkbox_genFocusMap)
        options_layout.addWidget(self.checkbox_withAutofocus)
        if SUPPORT_LASER_AUTOFOCUS:
            options_layout.addWidget(self.checkbox_withReflectionAutofocus)
        options_layout.addWidget(self.checkbox_useCoordinateAcquisition)
        if ENABLE_STITCHER:
            options_layout.addWidget(self.checkbox_stitchOutput)

        row_bottom_layout.addLayout(options_layout)

        row_bottom_layout.addWidget(self.btn_startAcquisition)
        main_layout.addLayout(row_bottom_layout)

        # Row 5: Progress Bar
        row_progress_layout = QHBoxLayout()
        row_progress_layout.addWidget(self.progress_label)
        row_progress_layout.addWidget(self.progress_bar)
        row_progress_layout.addWidget(self.eta_label)
        main_layout.addLayout(row_progress_layout)

        # Connections
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.entry_deltaZ.valueChanged.connect(self.set_deltaZ)
        self.entry_NZ.valueChanged.connect(self.multipointController.set_NZ)
        self.entry_dt.valueChanged.connect(self.multipointController.set_deltat)
        self.entry_Nt.valueChanged.connect(self.multipointController.set_Nt)
        self.entry_scan_size.valueChanged.connect(self.update_coverage_from_scan_size)
        self.entry_well_coverage.valueChanged.connect(self.update_scan_size_from_coverage)
        self.checkbox_withAutofocus.stateChanged.connect(self.multipointController.set_af_flag)
        self.checkbox_withReflectionAutofocus.stateChanged.connect(self.multipointController.set_reflection_af_flag)
        self.checkbox_genFocusMap.stateChanged.connect(self.multipointController.set_gen_focus_map_flag)
        self.checkbox_stitchOutput.toggled.connect(self.display_stitcher_widget)
        self.list_configurations.itemSelectionChanged.connect(self.emit_selected_channels)
        self.navigationViewer.signal_draw_scan_grid.connect(self.set_live_scan_coordinates)
        self.combobox_shape.currentTextChanged.connect(self.update_well_coordinates)
        self.entry_scan_size.valueChanged.connect(self.update_well_coordinates)
        self.entry_overlap.valueChanged.connect(self.update_well_coordinates)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)
        self.multipointController.signal_acquisition_progress.connect(self.update_acquisition_progress)
        self.multipointController.signal_region_progress.connect(self.update_region_progress)
        self.signal_acquisition_started.connect(self.display_progress_bar)
        self.eta_timer.timeout.connect(self.update_eta_display)
        self.entry_minZ.valueChanged.connect(self.check_z_max)
        self.entry_maxZ.valueChanged.connect(self.check_z_min)
        self.entry_NZ.valueChanged.connect(self.update_dz)
        self.navigationController.zPos.connect(self.update_current_z)

    def update_region_progress(self, current_fov, num_fovs):
        self.progress_bar.setMaximum(num_fovs)
        self.progress_bar.setValue(current_fov)

        if self.acquisition_start_time is not None and current_fov > 0:
            elapsed_time = time.time() - self.acquisition_start_time

            # Calculate total processed FOVs and total FOVs
            if self.num_regions > 1:
                current_region = int(self.progress_label.text().split('/')[0].split(' ')[1])
            else:
                current_region = 1
            processed_fovs = (current_region - 1) * num_fovs + current_fov
            total_fovs = self.num_regions * num_fovs
            remaining_fovs = total_fovs - processed_fovs

            # Calculate ETA
            fov_per_second = processed_fovs / elapsed_time
            self.eta_seconds = remaining_fovs / fov_per_second if fov_per_second > 0 else 0
            self.update_eta_display()

            # Start or restart the timer
            self.eta_timer.start(1000)  # Update every 1000 ms (1 second)

    def update_acquisition_progress(self, current_region, num_regions):
        if current_region == 1:  # First region
            self.acquisition_start_time = time.time()
            self.num_regions = num_regions
        if num_regions <= 1:
            self.progress_label.setText("Progress")
        else:
            self.progress_label.setText(f"Region {current_region}/{num_regions}")
        self.progress_bar.setValue(0)

    def update_eta_display(self):
        if self.eta_seconds > 0:
            self.eta_seconds -= 1  # Decrease by 1 second
            hours, remainder = divmod(int(self.eta_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                eta_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                eta_str = f"{minutes:02d}:{seconds:02d}"
            self.eta_label.setText(f"{eta_str}")
        else:
            self.eta_timer.stop()
            self.eta_label.setText("00:00")

    def display_progress_bar(self, show):
        self.progress_label.setVisible(show)
        self.progress_bar.setVisible(show)
        self.eta_label.setVisible(show)
        if show:
            self.progress_bar.setValue(0)
            self.progress_label.setText("Region 0/0")
            self.eta_label.setText("--:--")
            self.acquisition_start_time = None
        else:
            self.eta_timer.stop()

    def set_default_scan_size(self):
        self.set_default_shape()
        if self.navigationViewer.sample == 'glass slide':
            self.entry_scan_size.setEnabled(True)
            self.entry_well_coverage.setEnabled(False)
        else:
            self.entry_well_coverage.setEnabled(True)
            self.entry_well_coverage.setValue(100)
            self.update_scan_size_from_coverage()

    def update_coverage_from_scan_size(self):
        if self.scanCoordinates.format != 0 and hasattr(self.scanCoordinates, 'well_size_mm'):
            well_size = self.scanCoordinates.well_size_mm
            if self.combobox_shape.currentText() == 'Circle':
                fov_size_mm = (self.objectiveStore.get_pixel_size() / 1000) * Acquisition.CROP_WIDTH
                well_size += fov_size_mm * (1 + math.sqrt(2))
            scan_size = self.entry_scan_size.value()
            coverage = (scan_size / well_size) * 100
            print('COVERAGE', coverage)
            self.entry_well_coverage.setValue(coverage)

    def update_scan_size_from_coverage(self):
        if hasattr(self.scanCoordinates, 'well_size_mm'):
            well_size = self.scanCoordinates.well_size_mm
            if self.combobox_shape.currentText() == 'Circle':
                fov_size_mm = (self.objectiveStore.get_pixel_size() / 1000) * Acquisition.CROP_WIDTH
                well_size += fov_size_mm * (1 + math.sqrt(2))
            coverage = self.entry_well_coverage.value()
            scan_size = (coverage / 100) * well_size
            print('SIZE', scan_size)
            self.entry_scan_size.setValue(scan_size)

    def update_dz(self):
        z_min = self.entry_minZ.value()
        z_max = self.entry_maxZ.value()
        nz = self.entry_NZ.value()
        dz = (z_max - z_min) / (nz - 1) if nz > 1 else 0
        self.entry_deltaZ.setValue(dz)

    def set_z_min(self):
        z_value = self.navigationController.z_pos_mm * 1000  # Convert to μm
        self.entry_minZ.setValue(z_value)
        self.navigationController.zPos.disconnect(self.update_current_z)
        self.update_dz()

    def set_z_max(self):
        z_value = self.navigationController.z_pos_mm * 1000  # Convert to μm
        self.entry_maxZ.setValue(z_value)
        self.navigationController.zPos.disconnect(self.update_current_z)
        self.update_dz()

    def check_z_max(self, z_value):
        if self.entry_maxZ.value() < self.entry_minZ.value():
            self.entry_maxZ.setValue(self.entry_minZ.value())
        print("update min z:", self.entry_minZ.value())
        self.update_dz()

    def check_z_min(self, z_value):
        if self.entry_maxZ.value() < self.entry_minZ.value():
            self.entry_minZ.setValue(self.entry_maxZ.value())
        print("update max z:", self.entry_maxZ.value())
        self.update_dz()

    def update_current_z(self, z_pos_um):
        if z_pos_um < self.entry_minZ.value():
            self.entry_minZ.setValue(z_pos_um)
        elif z_pos_um > self.entry_maxZ.value():
            self.entry_maxZ.setValue(z_pos_um)
        self.update_dz()

    def init_z(self, z_pos_mm=None):
        if z_pos_mm is None:
            z_pos_mm = self.navigationController.z_pos_mm 

        self.entry_minZ.blockSignals(True)
        self.entry_maxZ.blockSignals(True)
        self.navigationController.zPos.disconnect(self.update_current_z)

        self.entry_minZ.setValue(z_pos_mm*1000)
        print("init min z:", self.entry_minZ.value())
        self.entry_maxZ.setValue(z_pos_mm*1000)
        print("init max z:", self.entry_maxZ.value())

        self.navigationController.zPos.connect(self.update_current_z)
        self.entry_minZ.blockSignals(False)
        self.entry_maxZ.blockSignals(False)

    def set_default_shape(self):
        if self.scanCoordinates.format in [384, 1536]:
            self.combobox_shape.setCurrentText('Square')
        elif self.scanCoordinates.format != 0:
            self.combobox_shape.setCurrentText('Circle')

    def set_live_scan_coordinates(self, x_mm, y_mm):
        if self.scanCoordinates.format == 0 and self.multipointController.parent.recordTabWidget.currentWidget() == self:
            if self.region_coordinates:
                print("Clear live coordinates")
                self.clear_regions()
            else:
                print("No live coordinates")
            print("Add current location")
            self.add_region('current', x_mm, y_mm)
            
    def set_well_coordinates(self, selected):
        self.well_selected = selected and bool(self.scanCoordinates.get_selected_wells())
        print("well selected?", self.well_selected)
        if hasattr(self.multipointController.parent, 'recordTabWidget') and self.multipointController.parent.recordTabWidget.currentWidget() == self:
            if self.scanCoordinates.format == 0:
                x = self.navigationController.x_pos_mm
                y = self.navigationController.y_pos_mm
                self.set_live_scan_coordinates(x, y)

            elif self.well_selected:
                # Get the set of currently selected well IDs
                selected_well_ids = set(self.scanCoordinates.name)
                
                # Remove regions that are no longer selected
                for well_id in list(self.region_coordinates.keys()):
                    if well_id not in selected_well_ids:
                        self.remove_region(well_id)
                
                # Add regions for selected wells
                for well_id, (x, y) in zip(self.scanCoordinates.name, self.scanCoordinates.coordinates_mm):
                    if well_id not in self.region_coordinates:
                        self.add_region(well_id, x, y)
                
                self.signal_update_navigation_viewer.emit()
                print(f"Updated region coordinates: {len(self.region_coordinates)} wells")

            else:
                print("Clear well coordinates")
                self.clear_regions()

    def update_well_coordinates(self):
        if self.well_selected and self.multipointController.parent.recordTabWidget.currentWidget() == self:
            if len(self.region_coordinates) > 0:
                self.navigationViewer.clear_overlay()
            for well_id, well_coord in self.region_coordinates.items():
                self.add_region(well_id, well_coord[0], well_coord[1])
            
            self.signal_update_navigation_viewer.emit()
            print(f"Updated region coordinates: {len(self.region_coordinates)} regions")
        elif self.scanCoordinates.format == 0:
            x = self.navigationController.x_pos_mm
            y = self.navigationController.y_pos_mm
            self.set_live_scan_coordinates(x, y)

    def update_region_z_level(self, well_id, new_z):
        if len(self.region_coordinates[well_id]) == 3:
            # [x, y, z] -> [x, y, new_z]
            self.region_coordinates[well_id][2] = new_z
        else: 
            # [x, y] -> [x, y, new_z]
            self.region_coordinates[well_id].append[new_z]
        print(f"Updated z-level to {new_z} for region {well_id}")

    def add_region(self, well_id, x, y):
        z = self.navigationController.z_pos_mm
        action = "Updated" if well_id in self.region_coordinates else "Added"
        
        self.region_coordinates[well_id] = [float(x), float(y)] #, float(z)]
        
        scan_coordinates = self.create_region_coordinates(
            self.objectiveStore,
            x, y,
            scan_size_mm=self.entry_scan_size.value(),
            overlap_percent=self.entry_overlap.value(),
            shape=self.combobox_shape.currentText()
        )
        self.region_coordinates_map[well_id] = scan_coordinates
        
        print(f"{action} Region: {well_id} - x={x:.3f}, y={y:.3f}") #, z={z:.3f}")
        print("Size:", self.entry_scan_size.value())
        print("Shape:", self.combobox_shape.currentText())
        print("# fovs in region:", len(scan_coordinates))

    def remove_region(self, well_id):
        if well_id in self.region_coordinates:
            del self.region_coordinates[well_id]
            
            if well_id in self.region_coordinates_map:
                region_scan_coordinates = self.region_coordinates_map.pop(well_id)
                for coord in region_scan_coordinates:
                    self.navigationViewer.deregister_fov_to_image(coord[0], coord[1])
            
            print(f"Removed region: {well_id}")

    def clear_regions(self):
        self.navigationViewer.clear_overlay()
        self.region_coordinates.clear()
        self.region_coordinates_map.clear()
        print("Cleared all regions")

    def create_region_coordinates(self, objectiveStore, center_x, center_y, scan_size_mm=None, overlap_percent=10, shape='Square'):
        if scan_size_mm is None:
            scan_size_mm = self.scanCoordinates.well_size_mm
        pixel_size_um = objectiveStore.get_pixel_size()
        fov_size_mm = (pixel_size_um / 1000) * Acquisition.CROP_WIDTH
        step_size_mm = fov_size_mm * (1 - overlap_percent / 100)
        
        steps = math.floor(scan_size_mm / step_size_mm)
        if shape == 'Circle':
            # check if corners of middle row/col all fit  
            if steps % 2 == 1:  # for odd steps
                tile_diagonal = math.sqrt(2) * fov_size_mm
                actual_scan_size_mm = (steps - 1) * step_size_mm + tile_diagonal
            else:  # for even steps
                actual_scan_size_mm = math.sqrt(((steps - 1) * step_size_mm + fov_size_mm)**2 + (step_size_mm + fov_size_mm)**2)
            
            if actual_scan_size_mm > scan_size_mm:
                actual_scan_size_mm -= step_size_mm
                steps -= 1
        else:
            actual_scan_size_mm = (steps - 1) * step_size_mm + fov_size_mm
        
        steps = max(1, steps)  # Ensure at least one step
        print("steps:", steps, "step_size_mm:", step_size_mm)
        print("scan size mm:", scan_size_mm)
        print("actual scan size mm:", actual_scan_size_mm)

        scan_coordinates = []
        for i in range(steps):
            row = []
            for j in range(steps):
                x = center_x + (j - (steps - 1) / 2) * step_size_mm
                y = center_y + (i - (steps - 1) / 2) * step_size_mm
                if shape == 'Square':
                    row.append((x, y))
                    self.navigationViewer.register_fov_to_image(x,y)
                elif shape == 'Circle':
                    radius = scan_size_mm / 2
                    x_rel = (j - (steps - 1) / 2) * step_size_mm
                    y_rel = (i - (steps - 1) / 2) * step_size_mm
                    corners = [
                        (x_rel - fov_size_mm / 2, y_rel - fov_size_mm / 2),  # Top-left
                        (x_rel + fov_size_mm / 2, y_rel - fov_size_mm / 2),  # Top-right
                        (x_rel - fov_size_mm / 2, y_rel + fov_size_mm / 2),  # Bottom-left
                        (x_rel + fov_size_mm / 2, y_rel + fov_size_mm / 2)   # Bottom-right
                    ]
                    if all(math.sqrt(cx**2 + cy**2) <= radius for cx, cy in corners):
                        row.append((x, y))
                        self.navigationViewer.register_fov_to_image(x,y) ### if show full grid 
                else:
                    raise ValueError(f"Unsupported shape: {shape}. Choose 'Square' or 'Circle'.")
            
            if i % 2 == 1:  # Reverse every other row
                row.reverse()
            
            scan_coordinates.extend(row)

        # Check if scan_coordinates is empty, and if so, add the center coordinate
        if not scan_coordinates and shape == 'Circle':
            scan_coordinates.append((center_x, center_y))
            self.navigationViewer.register_fov_to_image(center_x, center_y)

        ("update nav viewer")
        self.signal_update_navigation_viewer.emit()
        return scan_coordinates

    def create_scan_grid(self, objectiveStore, scan_size_mm=None, overlap_percent=10, shape='Square'):
        if scan_size_mm is None:
            scan_size_mm = self.scanCoordinates.well_size_mm

        pixel_size_um = objectiveStore.get_pixel_size()
        fov_size_mm = (pixel_size_um / 1000) * Acquisition.CROP_WIDTH
        step_size_mm = fov_size_mm * (1 - overlap_percent / 100)
        print("fov_size_mm:", fov_size_mm)
        print("step_size_mm:", step_size_mm)

        
        steps = math.floor(scan_size_mm / step_size_mm)
        if shape == 'Circle':
            # check if corners of middle row/col all fit  
            if steps % 2 == 1:  # for odd steps
                tile_diagonal = math.sqrt(2) * fov_size_mm
                actual_scan_size_mm = (steps - 1) * step_size_mm + tile_diagonal
            else:  # for even steps
                actual_scan_size_mm = math.sqrt(((steps - 1) * step_size_mm + fov_size_mm)**2 + (step_size_mm + fov_size_mm)**2)
            
            if actual_scan_size_mm > scan_size_mm:
                actual_scan_size_mm -= step_size_mm
                steps -= 1
        else:
            actual_scan_size_mm = (steps - 1) * step_size_mm + fov_size_mm
        
        steps = max(1, steps)  # Ensure at least one step
        print("steps:", steps)
        print("scan size mm:", scan_size_mm)
        print("actual scan size mm:", actual_scan_size_mm)

        region_skip_positions = []
        
        if shape == 'Circle':
            radius = scan_size_mm / 2
            for i in range(steps):
                for j in range(steps):
                    x_rel = (j - (steps - 1) / 2) * step_size_mm
                    y_rel = (i - (steps - 1) / 2) * step_size_mm
                    corners = [
                        (x_rel - fov_size_mm / 2, y_rel - fov_size_mm / 2),  # Top-left
                        (x_rel + fov_size_mm / 2, y_rel - fov_size_mm / 2),  # Top-right
                        (x_rel - fov_size_mm / 2, y_rel + fov_size_mm / 2),  # Bottom-left
                        (x_rel + fov_size_mm / 2, y_rel + fov_size_mm / 2)   # Bottom-right
                    ]
                    if any(math.sqrt(cx**2 + cy**2) > radius for cx, cy in corners):
                        region_skip_positions.append((i, j))
                        print(f"skipping {i}, {j}")

            # If all positions were skipped, clear the list and set steps to 1
            if len(region_skip_positions) == steps * steps:
                region_skip_positions.clear()
                steps = 1
                print("All positions were outside the circle. Reverting to single central position.")
        
        self.scanCoordinates.grid_skip_positions = region_skip_positions
        return steps, step_size_mm

    def toggle_acquisition(self, pressed):
        if not self.base_path_is_set:
            self.btn_startAcquisition.setChecked(False)
            QMessageBox.warning(self, "Warning", "Please choose base saving directory first")
            return

        if not self.use_coordinate_acquisition and self.navigationViewer.sample != 'glass slide' and not self.well_selected:
        #if self.navigationViewer.sample != 'glass slide' and self.well_selected == False:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please select a well to scan first")
            msg.exec_()
            return

        if not self.list_configurations.selectedItems():
            self.btn_startAcquisition.setChecked(False)
            QMessageBox.warning(self, "Warning", "Please select at least one imaging channel")
            return

        if pressed:
            self.setEnabled_all(False)

            scan_size_mm = self.entry_scan_size.value()
            overlap_percent = self.entry_overlap.value()
            shape = self.combobox_shape.currentText()
            self.multipointController.set_z_stacking_config(self.combobox_z_stack.currentIndex())

            if self.use_coordinate_acquisition:
                if len(self.region_coordinates) == 0:
                    # Use current location if no regions added
                    x = self.navigationController.x_pos_mm
                    y = self.navigationController.y_pos_mm
                    z = self.navigationController.z_pos_mm
                    self.region_coordinates['current'] = [x, y, z]
                    scan_coordinates = self.create_region_coordinates(
                        self.objectiveStore,
                        x, y,
                        scan_size_mm=scan_size_mm,
                        overlap_percent=overlap_percent,
                        shape=shape
                    )
                    self.region_coordinates_map['current'] = scan_coordinates

                # Calculate total number of positions for signal emission
                total_positions = sum(len(coords) for coords in self.region_coordinates_map.values())
                Nx = Ny = int(math.sqrt(total_positions))
                dx_mm = dy_mm = scan_size_mm / (Nx - 1) if Nx > 1 else scan_size_mm
                
            else:
                # Use grid-based acquisition
                if self.scanCoordinates.format == 0 or len(self.region_coordinates) == 0:
                    x = self.navigationController.x_pos_mm
                    y = self.navigationController.y_pos_mm
                    z = self.navigationController.z_pos_mm
                    self.region_coordinates['current'] = [x, y, z]
                steps, step_size_mm = self.create_scan_grid(
                    self.objectiveStore,
                    scan_size_mm=scan_size_mm,
                    overlap_percent=overlap_percent,
                    shape=shape
                )
                Nx = Ny = steps
                dx_mm = dy_mm = step_size_mm

                # Set up multipoint controller
                self.multipointController.set_NX(Nx)
                self.multipointController.set_NY(Ny)
                self.multipointController.set_deltaX(dx_mm)
                self.multipointController.set_deltaY(dy_mm)

            self.multipointController.set_deltaZ(self.entry_deltaZ.value())
            self.multipointController.set_NZ(self.entry_NZ.value())
            self.multipointController.set_deltat(self.entry_dt.value())
            self.multipointController.set_Nt(self.entry_Nt.value())
            self.multipointController.set_af_flag(self.checkbox_withAutofocus.isChecked())
            self.multipointController.set_reflection_af_flag(self.checkbox_withReflectionAutofocus.isChecked())
            self.multipointController.set_selected_configurations([item.text() for item in self.list_configurations.selectedItems()])
            self.multipointController.start_new_experiment(self.lineEdit_experimentID.text())

            # Emit signals
            self.signal_acquisition_started.emit(True)
            self.signal_acquisition_shape.emit(Nx, Ny, self.entry_NZ.value(),
                                               dx_mm, dy_mm, self.entry_deltaZ.value())
            print("Nx,Ny,Nz", Nx, Ny, self.entry_NZ.value())
            print("dx,dy,zd", dx_mm, dy_mm, self.entry_deltaZ.value())
            print("region coordinates:")
            for well_id, coords in self.region_coordinates.items():
                print(f"{well_id}: {coords}")

            # Start acquisition
            if self.use_coordinate_acquisition:
                self.multipointController.run_acquisition(location_list=self.region_coordinates, coordinate_dict=self.region_coordinates_map)
            else:
                if self.scanCoordinates.format == 0:
                    self.multipointController.run_acquisition(location_list=list(self.region_coordinates.values())) # glass slide
                else:
                    self.multipointController.run_acquisition() # wellplate
        else:
            self.multipointController.request_abort_aquisition()
            self.setEnabled_all(True)

    def acquisition_is_finished(self):
        self.signal_acquisition_started.emit(False)
        self.btn_startAcquisition.setChecked(False)
        self.set_well_coordinates(self.well_selected)
        self.setEnabled_all(True)

    def setEnabled_all(self, enabled):
        for widget in self.findChildren(QWidget):
            if (widget != self.btn_startAcquisition and
                widget != self.progress_bar and
                widget != self.progress_label and
                widget != self.eta_label):
                widget.setEnabled(enabled)
            
            if self.scanCoordinates.format == 0:
                self.entry_well_coverage.setEnabled(False)
            self.entry_deltaZ.setEnabled(False)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.multipointController.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True

    def set_deltaZ(self, value):
        mm_per_ustep = SCREW_PITCH_Z_MM/(self.multipointController.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_deltaZ.setValue(deltaZ)
        self.multipointController.set_deltaZ(deltaZ)

    def emit_selected_channels(self):
        selected_channels = [item.text() for item in self.list_configurations.selectedItems()]
        self.signal_acquisition_channels.emit(selected_channels)

    def display_stitcher_widget(self, checked):
        self.signal_stitcher_widget.emit(checked)
        if checked:
            self.checkbox_useCoordinateAcquisition.setChecked(not checked)
        self.checkbox_useCoordinateAcquisition.setVisible(not checked)


class StitcherWidget(QFrame):

    def __init__(self, configurationManager, *args, **kwargs):
        super(StitcherWidget, self).__init__(*args, **kwargs)
        self.configurationManager = configurationManager
        self.output_path = ""
        self.contrast_limit = None
        self.contrast_limits = {}
        self.initUI()

    def initUI(self):
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)  # Set frame style
        self.layout = QVBoxLayout(self)
        self.topLayout = QHBoxLayout()
        self.colLayout1 = QVBoxLayout()
        self.colLayout2 = QVBoxLayout()

        # Apply flatfield correction checkbox
        self.applyFlatfieldCheck = QCheckBox("Apply Flatfield Correction")
        self.colLayout2.addWidget(self.applyFlatfieldCheck)

        # Output format dropdown
        self.outputFormatLabel = QLabel('Select Output Format:', self)
        self.outputFormatCombo = QComboBox(self)
        self.outputFormatCombo.addItem("OME-ZARR")
        self.outputFormatCombo.addItem("OME-TIFF")
        self.colLayout1.addWidget(self.outputFormatLabel)
        self.colLayout1.addWidget(self.outputFormatCombo)

        # Use registration checkbox
        self.useRegistrationCheck = QCheckBox("Use Registration")
        self.useRegistrationCheck.toggled.connect(self.onRegistrationCheck)
        self.colLayout2.addWidget(self.useRegistrationCheck)

        # Select registration channel
        self.registrationChannelLabel = QLabel("Select Registration Channel:", self)
        self.registrationChannelLabel.setVisible(False)
        self.colLayout2.addWidget(self.registrationChannelLabel)
        self.registrationChannelCombo = QComboBox(self)
        self.registrationChannelLabel.setVisible(False)
        self.registrationChannelCombo.setVisible(False)
        self.colLayout2.addWidget(self.registrationChannelCombo)
        
        self.topLayout.addLayout(self.colLayout1)
        self.topLayout.addLayout(self.colLayout2)
        self.layout.addLayout(self.topLayout)

        # Button to view output in Napari
        self.viewOutputButton = QPushButton("View Output in Napari")
        self.viewOutputButton.setEnabled(False)  # Initially disabled
        self.viewOutputButton.setVisible(False)
        self.viewOutputButton.clicked.connect(self.viewOutputNapari)
        self.layout.addWidget(self.viewOutputButton)

        # Progress bar
        self.progressBar = QProgressBar()
        self.layout.addWidget(self.progressBar)
        self.progressBar.setVisible(False)  # Initially hidden

        # Status label
        self.statusLabel = QLabel("Status: Image Acquisition")
        self.layout.addWidget(self.statusLabel)
        self.statusLabel.setVisible(False)

    def onRegistrationCheck(self, checked):
        self.registrationChannelLabel.setVisible(checked)
        self.registrationChannelCombo.setVisible(checked)
        if checked:
            self.colLayout2.removeWidget(self.applyFlatfieldCheck)
            self.colLayout1.insertWidget(0, self.applyFlatfieldCheck)
        else:
            self.colLayout1.removeWidget(self.applyFlatfieldCheck)
            self.colLayout2.insertWidget(0, self.applyFlatfieldCheck)

    def updateRegistrationChannels(self, selected_channels):
        self.registrationChannelCombo.clear()  # Clear existing items
        self.registrationChannelCombo.addItems(selected_channels)

    def gettingFlatfields(self):
        self.statusLabel.setText('Status: Calculating Flatfield Images...')
        self.viewOutputButton.setVisible(False)
        self.viewOutputButton.setStyleSheet("")
        self.progressBar.setValue(0)
        self.statusLabel.setVisible(True)
        self.progressBar.setVisible(True)

    def startingStitching(self):
        self.statusLabel.setText('Status: Stitching Acquisition Scans...')
        self.viewOutputButton.setVisible(False)
        self.progressBar.setValue(0)
        self.statusLabel.setVisible(True)
        self.progressBar.setVisible(True)

    def updateProgressBar(self, value, total):
        self.progressBar.setMaximum(total)
        self.progressBar.setValue(value)
        self.progressBar.setVisible(True)

    def startingSaving(self, stitch_complete=False):
        if stitch_complete:
            self.statusLabel.setText('Status: Saving Complete Acquisition Image...')
        else:
            self.statusLabel.setText('Status: Saving Stitched Image...')
        self.statusLabel.setVisible(True)
        self.progressBar.setRange(0, 0)  # indeterminate mode.
        self.progressBar.setVisible(True)

    def finishedSaving(self, output_path, dtype):
        self.statusLabel.setVisible(False)
        self.progressBar.setVisible(False)
        self.viewOutputButton.setVisible(True)
        self.viewOutputButton.setStyleSheet("background-color: #C2C2FF")
        self.viewOutputButton.setEnabled(True)
        try: 
            self.viewOutputButton.clicked.disconnect()
        except TypeError:
            pass
        self.viewOutputButton.clicked.connect(self.viewOutputNapari)

        self.output_path = output_path
        if np.issubdtype(dtype, np.integer):  # Check if dtype is an integer type
            self.contrast_limit = (np.iinfo(dtype).min, np.iinfo(dtype).max)
        elif np.issubdtype(dtype, np.floating):  # floating point type
            self.contrast_limit = (0.0, 1.0)
        else:
            self.contrast_limit = None
            raise ValueError("Unsupported dtype")

    def saveContrastLimits(self, layer_name, min_val, max_val):
        self.contrast_limits[layer_name] = (min_val, max_val)
        #print(f"Stitcher saved contrast limits for {layer_name}: ({min_val}, {max_val})")

    def extractWavelength(self, name):
        # Split the string and find the wavelength number immediately after "Fluorescence"
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]  # Assuming '488 nm Ex' and taking '488'
        for color in ['R', 'G', 'B']:
            if color in parts or "full_" + color in parts:
                return color
        return None

    def generateColormap(self, channel_info):
        """Convert a HEX value to a normalized RGB tuple."""
        c0 = (0, 0, 0)
        c1 = (((channel_info['hex'] >> 16) & 0xFF) / 255,  # Normalize the Red component
             ((channel_info['hex'] >> 8) & 0xFF) / 255,      # Normalize the Green component
             (channel_info['hex'] & 0xFF) / 255)             # Normalize the Blue component
        return Colormap(colors=[c0, c1], controls=[0, 1], name=channel_info['name'])

    def viewOutputNapari(self):
        try:
            napari_viewer = napari.Viewer()
            if ".ome.zarr" in self.output_path:
                napari_viewer.open(self.output_path, plugin='napari-ome-zarr', contrast_limits=self.contrast_limit)
            else:
                napari_viewer.open(self.output_path, contrast_limits=self.contrast_limit)

            for layer in napari_viewer.layers:
                layer_name = layer.name.replace("_", " ").replace("full ", "full_")
                channel_info = CHANNEL_COLORS_MAP.get(self.extractWavelength(layer_name), {'hex': 0xFFFFFF, 'name': 'gray'})

                # Check if Napari has a colormap with this name and use it; otherwise, create a new one
                if channel_info['name'] in AVAILABLE_COLORMAPS:
                    layer.colormap = AVAILABLE_COLORMAPS[channel_info['name']]
                else:
                    layer.colormap = self.generateColormap(channel_info)

                if layer_name in self.contrast_limits:
                    layer.contrast_limits = self.contrast_limits[layer_name]
                else:
                    layer.contrast_limits = self.contrast_limit  # Default contrast limits

        except Exception as e:
            QMessageBox.critical(self, "Error Opening in Napari", str(e))
            print(f"An error occurred while opening output in Napari: {e}")

    def resetUI(self):
        self.output_path = ""
        self.contrast_limit = None
        self.contrast_limits = {}

        # Reset UI components to their default states
        self.applyFlatfieldCheck.setChecked(False)
        self.outputFormatCombo.setCurrentIndex(0)  # Assuming the first index is the default
        self.useRegistrationCheck.setChecked(False)
        self.registrationChannelCombo.clear()  # Clear existing items
        self.registrationChannelLabel.setVisible(False)
        self.registrationChannelCombo.setVisible(False)

        # Reset the visibility and state of buttons and labels
        self.viewOutputButton.setEnabled(False)
        self.viewOutputButton.setVisible(False)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)
        self.statusLabel.setText("Status: Image Acquisition")
        self.statusLabel.setVisible(False)


class NapariLiveWidget(QWidget):
    signal_coordinates_clicked = Signal(int, int, int, int)
    signal_layer_contrast_limits = Signal(str, float, float)
    signal_newExposureTime = Signal(float)
    signal_newAnalogGain = Signal(float)
    signal_autoLevelSetting = Signal(bool)

    def __init__(self, streamHandler, liveController, configurationManager, wellSelectionWidget, show_trigger_options=True, show_display_options=True, show_autolevel=False, autolevel=False, parent=None):
        super().__init__(parent)
        self.streamHandler = streamHandler
        self.liveController = liveController
        self.configurationManager = configurationManager
        self.wellSelectionWidget = wellSelectionWidget
        self.live_layer_name = ""
        self.image_width = 0
        self.image_height = 0
        self.dtype = np.uint8
        self.channels = []
        self.init_live = False
        self.init_live_rgb = False
        self.contrast_limits = {}
        self.init_scale = False
        self.previous_scale = None
        self.previous_center = None
        self.last_was_autofocus = False
        self.fps_trigger = 10
        self.fps_display = 10
        self.currentConfiguration = self.configurationManager.configurations[0]

        self.initNapariViewer()
        self.addNapariGrayclipColormap()
        self.initControlWidgets(show_trigger_options, show_display_options, show_autolevel, autolevel)
        self.update_microscope_mode_by_name(self.currentConfiguration.name)

    def initNapariViewer(self):
        self.viewer = napari.Viewer(show=False)
        self.viewerWidget = self.viewer.window._qt_window
        self.viewer.dims.axis_labels = ['Y-axis', 'X-axis']
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewerWidget)
        self.setLayout(self.layout)
        self.customize_napari_viewer()

    def customize_napari_viewer(self):
        # Hide the status bar (which includes the activity button)
        if hasattr(self.viewer.window, '_status_bar'):
            self.viewer.window._status_bar.hide()
        
        # Hide the layer buttons
        if hasattr(self.viewer.window._qt_viewer, 'layerButtons'):
            self.viewer.window._qt_viewer.layerButtons.hide()

        # Hide or remove the layer control buttons
        if hasattr(self.viewer.window._qt_viewer, 'dockLayerControls'):
            layer_controls = self.viewer.window._qt_viewer.dockLayerControls.widget()
            if layer_controls is not None:
                # Look for a container of buttons within the layer controls
                button_container = layer_controls.findChild(QWidget, "button_container")
                if button_container:
                    button_container.hide()

    def initControlWidgets(self, show_trigger_options, show_display_options, show_autolevel, autolevel):

        # Microscope Configuration
        self.dropdown_modeSelection = QComboBox()
        for config in self.configurationManager.configurations:
            self.dropdown_modeSelection.addItem(config.name)
        self.dropdown_modeSelection.setCurrentText(self.currentConfiguration.name)
        self.dropdown_modeSelection.currentTextChanged.connect(self.update_microscope_mode_by_name)

        # Live button
        self.btn_live = QPushButton("Start Live")
        self.btn_live.setCheckable(True)
        self.btn_live.setStyleSheet("font-weight: bold; background-color: #A0A0F0")
        self.btn_live.clicked.connect(self.toggle_live)

        # Exposure Time
        self.entry_exposureTime = QDoubleSpinBox()
        self.entry_exposureTime.setRange(self.liveController.camera.EXPOSURE_TIME_MS_MIN, self.liveController.camera.EXPOSURE_TIME_MS_MAX)
        self.entry_exposureTime.setValue(self.currentConfiguration.exposure_time)
        self.entry_exposureTime.setSuffix(" ms")
        self.entry_exposureTime.valueChanged.connect(self.update_config_exposure_time)

        # Analog Gain
        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain.setRange(0, 24)
        self.entry_analogGain.setSingleStep(0.1)
        self.entry_analogGain.setValue(self.currentConfiguration.analog_gain)
        self.entry_analogGain.setSuffix("x")
        self.entry_analogGain.valueChanged.connect(self.update_config_analog_gain)

        # Illumination Intensity
        self.slider_illuminationIntensity = QSlider(Qt.Horizontal)
        self.slider_illuminationIntensity.setRange(0, 100)
        self.slider_illuminationIntensity.setValue(int(self.currentConfiguration.illumination_intensity))
        self.slider_illuminationIntensity.setTickPosition(QSlider.TicksBelow)
        self.slider_illuminationIntensity.setTickInterval(10)
        self.slider_illuminationIntensity.valueChanged.connect(self.update_config_illumination_intensity)
        self.label_illuminationIntensity = QLabel(str(self.slider_illuminationIntensity.value()) + "%")
        self.slider_illuminationIntensity.valueChanged.connect(lambda v: self.label_illuminationIntensity.setText(str(v) + "%"))

        # Trigger mode
        self.dropdown_triggerMode = QComboBox()
        trigger_modes = [
            ('Software', TriggerMode.SOFTWARE),
            ('Hardware', TriggerMode.HARDWARE),
            ('Continuous', TriggerMode.CONTINUOUS)
        ]
        for display_name, mode in trigger_modes:
            self.dropdown_triggerMode.addItem(display_name, mode)
        self.dropdown_triggerMode.currentIndexChanged.connect(self.on_trigger_mode_changed)
        # self.dropdown_triggerMode = QComboBox()
        # self.dropdown_triggerMode.addItems([TriggerMode.SOFTWARE, TriggerMode.HARDWARE, TriggerMode.CONTINUOUS])
        # self.dropdown_triggerMode.currentTextChanged.connect(self.liveController.set_trigger_mode)

        # Trigger FPS
        self.entry_triggerFPS = QDoubleSpinBox()
        self.entry_triggerFPS.setRange(0.02, 1000)
        self.entry_triggerFPS.setValue(self.fps_trigger)
        #self.entry_triggerFPS.setSuffix(" fps")
        self.entry_triggerFPS.valueChanged.connect(self.liveController.set_trigger_fps)


        # Display FPS
        self.entry_displayFPS = QDoubleSpinBox()
        self.entry_displayFPS.setRange(1, 240)
        self.entry_displayFPS.setValue(self.fps_display)
        #self.entry_displayFPS.setSuffix(" fps")
        self.entry_displayFPS.valueChanged.connect(self.streamHandler.set_display_fps)

        # Resolution Scaling
        self.slider_resolutionScaling = QSlider(Qt.Horizontal)
        self.slider_resolutionScaling.setRange(10, 100)
        self.slider_resolutionScaling.setValue(int(DEFAULT_DISPLAY_CROP))
        self.slider_resolutionScaling.setTickPosition(QSlider.TicksBelow)
        self.slider_resolutionScaling.setTickInterval(10)
        self.slider_resolutionScaling.valueChanged.connect(self.update_resolution_scaling)
        self.label_resolutionScaling = QLabel(str(self.slider_resolutionScaling.value()) + "%")
        self.slider_resolutionScaling.valueChanged.connect(lambda v: self.label_resolutionScaling.setText(str(v) + "%"))

        # Autolevel
        self.btn_autolevel = QPushButton('Autolevel')
        self.btn_autolevel.setCheckable(True)
        self.btn_autolevel.setChecked(autolevel)
        self.btn_autolevel.clicked.connect(self.signal_autoLevelSetting.emit)


        def make_row(label_widget, entry_widget, value_label=None):
            row = QHBoxLayout()
            row.addWidget(label_widget)
            row.addWidget(entry_widget)
            if value_label:
                row.addWidget(value_label)
            return row

        control_layout = QVBoxLayout()

        # Add widgets to layout
        config_label = QLabel('Configuration')
        top_row = make_row(config_label, self.dropdown_modeSelection)
        control_layout.addLayout(top_row)
        control_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        control_layout.addWidget(self.btn_live)
        control_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        row1 = make_row(QLabel('Exposure Time'), self.entry_exposureTime)
        control_layout.addLayout(row1)

        row2 = make_row(QLabel('Illumination'), self.slider_illuminationIntensity, self.label_illuminationIntensity)
        control_layout.addLayout(row2)

        row3 = make_row((QLabel('Analog Gain')), self.entry_analogGain)
        control_layout.addLayout(row3)
        control_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        if show_trigger_options:
            row0 = make_row(QLabel('Trigger Mode'), self.dropdown_triggerMode)
            control_layout.addLayout(row0)
            row00 = make_row(QLabel('Trigger FPS'), self.entry_triggerFPS)
            control_layout.addLayout(row00)
            control_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        if show_display_options:
            row4 = make_row((QLabel('Display FPS')), self.entry_displayFPS)
            control_layout.addLayout(row4)
            row5 = make_row(QLabel('Display Resolution'), self.slider_resolutionScaling, self.label_resolutionScaling)
            control_layout.addLayout(row5)
            control_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        if show_autolevel:
            control_layout.addWidget(self.btn_autolevel)
            control_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        control_layout.addStretch(1)

        live_controls_widget = QWidget()
        live_controls_widget.setLayout(control_layout)

        layer_controls_widget = self.viewer.window._qt_viewer.dockLayerControls.widget()
        layer_list_widget = self.viewer.window._qt_viewer.dockLayerList.widget()
        self.viewer.window._qt_viewer.layerButtons.hide()

        self.viewer.window.remove_dock_widget(self.viewer.window._qt_viewer.dockLayerControls)
        self.viewer.window.remove_dock_widget(self.viewer.window._qt_viewer.dockLayerList)
        # self.dock_live_controls = self.viewer.window.add_dock_widget(dock_live_controls, area='left', name='live controls', tabify=True)

        # Add the actual dock widgets
        self.dock_layer_controls = self.viewer.window.add_dock_widget(layer_controls_widget, area='left', name='layer controls', tabify=True)
        self.dock_layer_list = self.viewer.window.add_dock_widget(layer_list_widget, area='left', name='layer list', tabify=True)
        self.dock_live_controls = self.viewer.window.add_dock_widget(live_controls_widget, area='left', name='live controls', tabify=True)

        self.viewer.window.window_menu.addAction(self.dock_live_controls.toggleViewAction())
        
        well_selector_layout = QVBoxLayout() 
        title_label = QLabel("Well Selector")  
        title_label.setAlignment(Qt.AlignCenter)  # Center the title
        #title_label.setStyleSheet("font-weight: bold;")  # Optional: style the title
        well_selector_layout.addWidget(title_label) 

        well_selector_row = QHBoxLayout()
        well_selector_row.addStretch(1)
        well_selector_row.addWidget(self.wellSelectionWidget)
        well_selector_row.addStretch(1)
        well_selector_layout.addLayout(well_selector_row)
        
        well_selector_dock_widget = QWidget()
        well_selector_dock_widget.setLayout(well_selector_layout)
        self.dock_well_selector = self.viewer.window.add_dock_widget(well_selector_dock_widget, area='bottom', name='well selector', tabify=True)

        self.print_window_menu_items()

    def print_window_menu_items(self):
        print("Items in window_menu:")
        for action in self.viewer.window.window_menu.actions():
            print(action.text())

    def toggle_live(self, pressed):
        if pressed:
            self.liveController.start_live()
            self.btn_live.setText("Stop Live")
        else:
            self.liveController.stop_live()
            self.btn_live.setText("Start Live")

    def toggle_live_controls(self, show):
        if show:
            self.dock_live_controls.show()
        else:
            self.dock_live_controls.hide()

    def toggle_well_selector(self, show):
        if show:
            self.dock_well_selector.show()
        else:
            self.dock_well_selector.hide()

    def replace_well_selector(self, wellSelector):
        self.viewer.window.remove_dock_widget(self.dock_well_selector)
        self.wellSelectionWidget = wellSelector
        well_selector_layout = QHBoxLayout()
        well_selector_layout.addStretch(1)  # Add stretch on the left
        well_selector_layout.addWidget(self.wellSelectionWidget)
        well_selector_layout.addStretch(1)  # Add stretch on the right
        well_selector_dock_widget = QWidget()
        well_selector_dock_widget.setLayout(well_selector_layout)
        self.dock_well_selector = self.viewer.window.add_dock_widget(well_selector_dock_widget, area='bottom', name='well selector', tabify=True)

    def set_microscope_mode(self,config):
        self.dropdown_modeSelection.setCurrentText(config.name)

    def update_microscope_mode_by_name(self, current_microscope_mode_name):
        self.currentConfiguration = next((config for config in self.configurationManager.configurations if config.name == current_microscope_mode_name), None)
        if self.currentConfiguration:
            self.liveController.set_microscope_mode(self.currentConfiguration)
            self.entry_exposureTime.setValue(self.currentConfiguration.exposure_time)
            self.entry_analogGain.setValue(self.currentConfiguration.analog_gain)
            self.slider_illuminationIntensity.setValue(int(self.currentConfiguration.illumination_intensity))

    def update_config_exposure_time(self, new_value):
        self.currentConfiguration.exposure_time = new_value
        self.configurationManager.update_configuration(self.currentConfiguration.id, 'ExposureTime', new_value)
        self.signal_newExposureTime.emit(new_value)

    def update_config_analog_gain(self, new_value):
        self.currentConfiguration.analog_gain = new_value
        self.configurationManager.update_configuration(self.currentConfiguration.id, 'AnalogGain', new_value)
        self.signal_newAnalogGain.emit(new_value)

    def update_config_illumination_intensity(self, new_value):
        self.currentConfiguration.illumination_intensity = new_value
        self.configurationManager.update_configuration(self.currentConfiguration.id, 'IlluminationIntensity', new_value)
        self.liveController.set_illumination(self.currentConfiguration.illumination_source, new_value)

    def update_resolution_scaling(self, value):
        self.streamHandler.set_display_resolution_scaling(value)
        self.liveController.set_display_resolution_scaling(value)

    def on_trigger_mode_changed(self, index):
        # Get the actual value using user data
        actual_value = self.dropdown_triggerMode.itemData(index)
        print(f"Selected: {self.dropdown_triggerMode.currentText()} (actual value: {actual_value})")

    def addNapariGrayclipColormap(self):
        if hasattr(napari.utils.colormaps.AVAILABLE_COLORMAPS, 'grayclip'):
            return
        grayclip = []
        for i in range(255):
            grayclip.append([i / 255, i / 255, i / 255])
        grayclip.append([1, 0, 0])
        napari.utils.colormaps.AVAILABLE_COLORMAPS['grayclip'] = napari.utils.Colormap(name='grayclip', colors=grayclip)

    def initLiveLayer(self, channel, image_height, image_width, image_dtype, rgb=False):
        """Initializes the full canvas for each channel based on the acquisition parameters."""
        self.viewer.layers.clear()
        self.image_width = image_width
        self.image_height = image_height
        self.dtype = np.dtype(image_dtype)
        self.channels.append(channel)
        self.live_layer_name = channel
        contrast_limits = self.getContrastLimits()
        if rgb == True:
            canvas = np.zeros((image_height, image_width, 3), dtype=self.dtype)
        else:
            canvas = np.zeros((image_height, image_width), dtype=self.dtype)
        layer = self.viewer.add_image(canvas, name=channel, visible=True, rgb=rgb, colormap='grayclip',
                                      contrast_limits=contrast_limits, blending='additive')
        layer.mouse_double_click_callbacks.append(self.onDoubleClick)
        layer.events.contrast_limits.connect(self.signalContrastLimits)  # Connect to contrast limits event
        if not self.init_scale:
            self.resetView()
            self.previous_scale = self.viewer.camera.zoom
            self.previous_center = self.viewer.camera.center
        else:
            self.viewer.camera.zoom = self.previous_scale
            self.viewer.camera.center = self.previous_center

    def updateLiveLayer(self, image, from_autofocus=False):
        """Updates the appropriate slice of the canvas with the new image data."""
        rgb = len(image.shape) >= 3
        if not rgb and not self.init_live:
            self.initLiveLayer("Live View", image.shape[0], image.shape[1], image.dtype, rgb)
            self.init_live = True
            self.init_live_rgb = False
            print("init live")
        elif rgb and not self.init_live_rgb:
            self.initLiveLayer("Live View", image.shape[0], image.shape[1], image.dtype, rgb)
            self.init_live_rgb = True
            self.init_live = False
            print("init live rgb")
        
        layer = self.viewer.layers["Live View"]
        layer.data = image

        if from_autofocus:
            # save viewer scale
            if not self.last_was_autofocus:
                self.previous_scale = self.viewer.camera.zoom
                self.previous_center = self.viewer.camera.center
            # resize to cropped view
            self.resetView()
            self.last_was_autofocus = True
        else:
            if not self.init_scale:
                # init viewer scale
                self.resetView()
                self.previous_scale = self.viewer.camera.zoom
                self.previous_center = self.viewer.camera.center
                self.init_scale = True
            elif self.last_was_autofocus:
                # return to to original view
                self.viewer.camera.zoom = self.previous_scale
                self.viewer.camera.center = self.previous_center
            # save viewer scale
            self.previous_scale = self.viewer.camera.zoom
            self.previous_center = self.viewer.camera.center
            self.last_was_autofocus = False

        curr_layer_name = self.dropdown_modeSelection.currentText()
        if self.live_layer_name != curr_layer_name:
            self.live_layer_name = curr_layer_name
            layer.contrast_limits = self.contrast_limits.get(self.live_layer_name, self.getContrastLimits())
        layer.refresh()

    def onDoubleClick(self, layer, event):
        """Handle double-click events and emit centered coordinates if within the data range."""
        coords = layer.world_to_data(event.position)
        layer_shape = layer.data.shape[0:2] if len(layer.data.shape) >= 3 else layer.data.shape

        if coords is not None and (0 <= int(coords[-1]) < layer_shape[-1] and (0 <= int(coords[-2]) < layer_shape[-2])):
            x_centered = int(coords[-1] - layer_shape[-1] / 2)
            y_centered = int(coords[-2] - layer_shape[-2] / 2)
            # Emit the centered coordinates and dimensions of the layer's data array
            self.signal_coordinates_clicked.emit(x_centered, y_centered, layer_shape[-1], layer_shape[-2])

    def signalContrastLimits(self, event):
        layer = event.source
        layer_name = self.dropdown_modeSelection.currentText()
        min_val, max_val = map(float, layer.contrast_limits)  # or use int if necessary
        self.signal_layer_contrast_limits.emit(layer_name, min_val, max_val)
        self.contrast_limits[layer_name] = min_val, max_val

    def saveContrastLimits(self, layer_name, min_val, max_val):
        self.contrast_limits[layer_name] = (min_val, max_val)

    def getContrastLimits(self):
        if np.issubdtype(self.dtype, np.integer):
            return (np.iinfo(self.dtype).min, np.iinfo(self.dtype).max)
        elif np.issubdtype(self.dtype, np.floating):
            return (0.0, 1.0)
        return None

    def resetView(self):
        self.viewer.reset_view()

    def activate(self):
        print("ACTIVATING NAPARI LIVE WIDGET")
        self.viewer.window.activate()



class NapariMultiChannelWidget(QWidget):

    signal_layer_contrast_limits = Signal(str, float, float)

    def __init__(self, objectiveStore, grid_enabled=False, parent=None):
        super().__init__(parent)
        # Initialize placeholders for the acquisition parameters
        self.objectiveStore = objectiveStore
        self.image_width = 0
        self.image_height = 0
        self.dtype = np.uint8
        self.channels = set()
        self.contrast_limits = {}
        self.pixel_size_um = 1
        self.dz_um = 1
        self.Nz = 1
        self.layers_initialized = False
        self.acquisition_initialized = False
        self.viewer_scale_initialized = False
        self.update_layer_count = 0
        self.grid_enabled = grid_enabled

        # Initialize a napari Viewer without showing its standalone window.
        self.initNapariViewer()

    def initNapariViewer(self):
        self.viewer = napari.Viewer(show=False)
        if self.grid_enabled:
            self.viewer.grid.enabled = True
        self.viewer.dims.axis_labels = ['Z-axis', 'Y-axis', 'X-axis']
        self.viewerWidget = self.viewer.window._qt_window
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewerWidget)
        self.setLayout(self.layout)
        
    def initLayersShape(self, Nx, Ny, Nz, dx, dy, dz):
        pixel_size_um = self.objectiveStore.get_pixel_size()
        if self.Nz != Nz or self.dz_um != dz or self.pixel_size_um != pixel_size_um:
            self.acquisition_initialized = False
            self.Nz = Nz
            self.dz_um = dz
            self.pixel_size_um = pixel_size_um
        
    def initChannels(self, channels):
        self.channels = set(channels)

    def extractWavelength(self, name):
        # Split the string and find the wavelength number immediately after "Fluorescence"
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]  # Assuming '488 nm Ex' and taking '488'
        for color in ['R', 'G', 'B']:
            if color in parts or f"full_{color}" in parts:
                return color
        return None

    def generateColormap(self, channel_info):
        """Convert a HEX value to a normalized RGB tuple."""
        positions = [0, 1]
        c0 = (0, 0, 0)
        c1 = (((channel_info['hex'] >> 16) & 0xFF) / 255,  # Normalize the Red component
             ((channel_info['hex'] >> 8) & 0xFF) / 255,      # Normalize the Green component
             (channel_info['hex'] & 0xFF) / 255)             # Normalize the Blue component
        return Colormap(colors=[c0, c1], controls=[0, 1], name=channel_info['name'])

    def initLayers(self, image_height, image_width, image_dtype):
        """Initializes the full canvas for each channel based on the acquisition parameters."""
        #self.viewer.layers.clear()
        if self.acquisition_initialized:
            for layer in list(self.viewer.layers):
                if layer.name not in self.channels:
                    self.viewer.layers.remove(layer)
        else:
            self.viewer.layers.clear()
            self.acquisition_initialized = True
        self.image_width = image_width
        self.image_height = image_height
        self.dtype = np.dtype(image_dtype)
        self.layers_initialized = True
        self.update_layer_count = 0

    def updateLayers(self, image, i, j, k, channel_name):
        """Updates the appropriate slice of the canvas with the new image data."""
        if not self.layers_initialized:
            self.initLayers(image.shape[0], image.shape[1], image.dtype)
 
        rgb = len(image.shape) == 3
        if channel_name not in self.viewer.layers:
            self.channels.add(channel_name)
            if rgb:
                color = None  # RGB images do not need a colormap
                canvas = np.zeros((self.Nz, self.image_height, self.image_width, 3), dtype=self.dtype)
            else:
                channel_info = CHANNEL_COLORS_MAP.get(self.extractWavelength(channel_name), {'hex': 0xFFFFFF, 'name': 'gray'})
                if channel_info['name'] in AVAILABLE_COLORMAPS:
                    color = AVAILABLE_COLORMAPS[channel_info['name']]
                else:
                    color = self.generateColormap(channel_info)
                canvas = np.zeros((self.Nz, self.image_height, self.image_width), dtype=self.dtype)
            
            limits = self.getContrastLimits(self.dtype)
            layer = self.viewer.add_image(canvas, name=channel_name, visible=True, rgb=rgb,
                                          colormap=color, contrast_limits=limits, blending='additive',
                                          scale=(self.dz_um, self.pixel_size_um, self.pixel_size_um))
            print(f"multi channel - dz_um:{self.dz_um}, pixel_y_um:{self.pixel_size_um}, pixel_x_um:{self.pixel_size_um}")
            layer.contrast_limits = self.contrast_limits.get(channel_name, limits)
            layer.events.contrast_limits.connect(self.signalContrastLimits)

            if not self.viewer_scale_initialized:
                self.resetView()
                self.viewer_scale_initialized = True

        layer = self.viewer.layers[channel_name]
        layer.data[k] = image
        layer.contrast_limits = self.contrast_limits.get(layer.name, self.getContrastLimits(self.dtype))
        self.update_layer_count += 1
        if self.update_layer_count % len(self.channels) == 0:
            if self.Nz > 1:
                self.viewer.dims.set_point(0, k * self.dz_um)
            for layer in self.viewer.layers:
                layer.refresh()

    def updateRTPLayers(self, image, channel_name):
        """Updates the appropriate slice of the canvas with the new image data."""
        if not self.layers_initialized:
            self.initLayers(image.shape[0], image.shape[1], image.dtype)

        rgb = len(image.shape) == 3
        if channel_name not in self.viewer.layers:
            self.channels.add(channel_name)
            if rgb:
                color = None  # RGB images do not need a colormap
                canvas = np.zeros((self.image_height, self.image_width, 3), dtype=self.dtype)
            else:
                channel_info = CHANNEL_COLORS_MAP.get(self.extractWavelength(channel_name), {'hex': 0xFFFFFF, 'name': 'gray'})
                if channel_info['name'] in AVAILABLE_COLORMAPS:
                    color = AVAILABLE_COLORMAPS[channel_info['name']]
                else:
                    color = self.generateColormap(channel_info)
                canvas = np.zeros((self.image_height, self.image_width), dtype=self.dtype)

            limits = self.getContrastLimits(self.dtype)
            layer = self.viewer.add_image(canvas, name=channel_name, visible=True, rgb=rgb,
                                          colormap=color, contrast_limits=limits, blending='additive')
            layer.contrast_limits = self.contrast_limits.get(channel_name, limits)
            layer.events.contrast_limits.connect(self.signalContrastLimits)

            self.resetView()

        layer = self.viewer.layers[channel_name]
        layer.data = image
        layer.contrast_limits = self.contrast_limits.get(layer.name, self.getContrastLimits(self.dtype))
        layer.refresh()

    def getContrastLimits(self, dtype):
        if np.issubdtype(dtype, np.integer):
            return (np.iinfo(dtype).min, np.iinfo(dtype).max)
        elif np.issubdtype(dtype, np.floating):
            return (0.0, 1.0)
        return None

    def signalContrastLimits(self, event):
        layer = event.source
        min_val, max_val = map(float, layer.contrast_limits)  # or use int if necessary
        self.signal_layer_contrast_limits.emit(layer.name, min_val, max_val)
        self.contrast_limits[layer.name] = min_val, max_val

    def saveContrastLimits(self, layer_name, min_val, max_val):
        self.contrast_limits[layer_name] = (min_val, max_val)

    def resetView(self):
        self.viewer.reset_view()
        for layer in self.viewer.layers:
            layer.refresh()

    def activate(self):
        print("ACTIVATING NAPARI MULTICHANNEL WIDGET")
        self.viewer.window.activate()


class NapariTiledDisplayWidget(QWidget):

    signal_coordinates_clicked = Signal(int, int, int, int, int, int, float, float)
    signal_layer_contrast_limits = Signal(str, float, float)

    def __init__(self, objectiveStore, parent=None):
        super().__init__(parent)
        # Initialize placeholders for the acquisition parameters
        self.objectiveStore = objectiveStore
        self.downsample_factor = PRVIEW_DOWNSAMPLE_FACTOR
        self.image_width = 0
        self.image_height = 0
        self.dtype = np.uint8
        self.channels = set()
        self.Nx = 1
        self.Ny = 1
        self.Nz = 1
        self.dz_um = 1
        self.pixel_size_um = 1
        self.layers_initialized = False
        self.acquisition_initialized = False
        self.viewer_scale_initialized = False
        self.contrast_limits = {}
        self.initNapariViewer()

    def initNapariViewer(self):
        self.viewer = napari.Viewer(show=False) #, ndisplay=3)
        self.viewerWidget = self.viewer.window._qt_window
        self.viewer.dims.axis_labels = ['Z-axis', 'Y-axis', 'X-axis']
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewerWidget)
        self.setLayout(self.layout)
        
    def initLayersShape(self, Nx, Ny, Nz, dx, dy, dz):
        self.acquisition_initialized = False
        self.Nx = Nx
        self.Ny = Ny
        self.Nz = Nz
        self.dx_mm = dx
        self.dy_mm = dy
        self.dz_um = dz
        pixel_size_um = self.objectiveStore.get_pixel_size()
        self.pixel_size_um = pixel_size_um * self.downsample_factor

    def initChannels(self, channels):
        self.channels = set(channels)

    def extractWavelength(self, name):
        # Split the string and find the wavelength number immediately after "Fluorescence"
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]  # Assuming '488 nm Ex' and taking '488'
        for color in ['R', 'G', 'B']:
            if color in parts or f"full_{color}" in parts:
                return color
        return None

    def generateColormap(self, channel_info):
        """Convert a HEX value to a normalized RGB tuple."""
        c0 = (0, 0, 0)
        c1 = (((channel_info['hex'] >> 16) & 0xFF) / 255,  # Normalize the Red component
             ((channel_info['hex'] >> 8) & 0xFF) / 255,      # Normalize the Green component
             (channel_info['hex'] & 0xFF) / 255)             # Normalize the Blue component
        return Colormap(colors=[c0, c1], controls=[0, 1], name=channel_info['name'])

    def initLayers(self, image_height, image_width, image_dtype):
        """Initializes the full canvas for each channel based on the acquisition parameters."""
        if self.acquisition_initialized:
            for layer in list(self.viewer.layers):
                if layer.name not in self.channels:
                    self.viewer.layers.remove(layer)
        else:
            self.viewer.layers.clear()
            self.acquisition_initialized = True
        self.image_width = image_width // self.downsample_factor
        self.image_height = image_height // self.downsample_factor
        self.dtype = np.dtype(image_dtype)
        self.resetView()
        self.layers_initialized = True
        self.viewer_scale_initialized = False
        self.layers_initialized = True

    def updateLayers(self, image, i, j, k, channel_name):
        """Updates the appropriate slice of the canvas with the new image data."""

        if i == -1 or j == -1:
            print("no tiled preview for coordinate acquisition")
            return 
        rgb = len(image.shape) == 3  # Check if image is RGB based on shape
        if not self.layers_initialized:
           self.initLayers(image.shape[0], image.shape[1], image.dtype)
 
        if channel_name not in self.viewer.layers:
            self.channels.add(channel_name)
            if rgb:
                color = None  # No colormap for RGB images
                canvas = np.zeros((self.Nz, self.Ny * self.image_height, self.Nx * self.image_width, 3), dtype=self.dtype)
            else:
                channel_info = CHANNEL_COLORS_MAP.get(self.extractWavelength(channel_name), {'hex': 0xFFFFFF, 'name': 'gray'})
                if channel_info['name'] in AVAILABLE_COLORMAPS:
                    color = AVAILABLE_COLORMAPS[channel_info['name']]
                else:
                    color = self.generateColormap(channel_info)
                canvas = np.zeros((self.Nz, self.Ny * self.image_height, self.Nx * self.image_width), dtype=self.dtype)

            limits = self.getContrastLimits(self.dtype)
            layer = self.viewer.add_image(canvas, name=channel_name, visible=True, rgb=rgb, 
                                          colormap=color, contrast_limits=limits, blending='additive', 
                                          scale=(self.dz_um, self.pixel_size_um, self.pixel_size_um))
            print(f"tiled display - dz_um:{self.dz_um}, pixel_y_um:{self.pixel_size_um}, pixel_x_um:{self.pixel_size_um}")
            layer.contrast_limits = self.contrast_limits.get(channel_name, limits)
            layer.events.contrast_limits.connect(self.signalContrastLimits)
            layer.mouse_double_click_callbacks.append(self.onDoubleClick)

        image = cv2.resize(image, (self.image_width, self.image_height), interpolation=cv2.INTER_AREA)
        
        if not self.viewer_scale_initialized:
            self.resetView()
            self.viewer_scale_initialized = True
        self.viewer.dims.set_point(0, k * self.dz_um)
        layer = self.viewer.layers[channel_name]
        layer.contrast_limits = self.contrast_limits.get(layer.name, self.getContrastLimits(self.dtype))
        layer_data = layer.data
        y_slice = slice(i * self.image_height, (i + 1) * self.image_height)
        x_slice = slice(j * self.image_width, (j + 1) * self.image_width)
        if rgb:
            layer_data[k, y_slice, x_slice, :] = image
        else:
            layer_data[k, y_slice, x_slice] = image
        layer.data = layer_data
        layer.refresh()

    def signalContrastLimits(self, event):
        layer = event.source
        min_val, max_val = map(float, layer.contrast_limits) 
        self.signal_layer_contrast_limits.emit(layer.name, min_val, max_val)
        self.contrast_limits[layer.name] = min_val, max_val

    def getContrastLimits(self, dtype):
        if np.issubdtype(dtype, np.integer):
            return (np.iinfo(dtype).min, np.iinfo(dtype).max)
        elif np.issubdtype(dtype, np.floating):
            return (0.0, 1.0)
        return None

    def saveContrastLimits(self, layer_name, min_val, max_val):
        self.contrast_limits[layer_name] = (min_val, max_val)

    def onDoubleClick(self, layer, event):
        """Handle double-click events and emit centered coordinates if within the data range."""
        coords = layer.world_to_data(event.position) 
        layer_shape = layer.data.shape[0:3] if len(layer.data.shape) >= 4 else layer.data.shape

        if coords is not None and (0 <= int(coords[-1]) < layer_shape[-1] and (0 <= int(coords[-2]) < layer_shape[-2])):
            x_centered = int(coords[-1] - layer_shape[-1] / 2)
            y_centered = int(coords[-2] - layer_shape[-2] / 2)
            # Emit the centered coordinates and dimensions of the layer's data array
            self.signal_coordinates_clicked.emit(x_centered, y_centered,
                                                 layer_shape[-1], layer_shape[-2],
                                                 self.Nx, self.Ny,
                                                 self.dx_mm, self.dy_mm)

    def resetView(self):
        self.viewer.reset_view()
        for layer in self.viewer.layers:
            layer.refresh()

    def activate(self):
        print("ACTIVATING NAPARI TILED DISPLAY WIDGET")
        self.viewer.window.activate()


class NapariMosaicDisplayWidget(QWidget):

    signal_coordinates_clicked = Signal(float, float)  # x, y in mm
    signal_layer_contrast_limits = Signal(str, float, float)
    signal_clear_viewer = Signal()

    def __init__(self, objectiveStore, parent=None):
        super().__init__(parent)
        self.objectiveStore = objectiveStore
        self.downsample_factor = PRVIEW_DOWNSAMPLE_FACTOR  # Initialize with a default downsample factor
        self.viewer = napari.Viewer(show=False)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewer.window._qt_window)
        
        # Add button to clear all layers
        self.clear_button = QPushButton("Clear Mosaic View")
        self.clear_button.clicked.connect(self.clearAllLayers)
        self.layout.addWidget(self.clear_button)
        
        self.setLayout(self.layout)
        self.viewer_pixel_size_mm = 1
        self.dz_um = None
        self.Nz = None
        self.channels = set()
        self.viewer_extents = [] # [min_y, max_y, min_x, max_x]
        self.top_left_coordinate = None  # [y, x] in mm
        self.contrast_limits = {}

    def initChannels(self, channels):
        self.channels = set(channels)

    def initLayersShape(self, Nx, Ny, Nz, dx, dy, dz):
        self.Nz = 1
        self.dz_um = dz

    def extractWavelength(self, name):
        # Split the string and find the wavelength number immediately after "Fluorescence"
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]  # Assuming '488 nm Ex' and taking '488'
        for color in ['R', 'G', 'B']:
            if color in parts or f"full_{color}" in parts:
                return color
        return None

    def generateColormap(self, channel_info):
        """Convert a HEX value to a normalized RGB tuple."""
        c0 = (0, 0, 0)
        c1 = (((channel_info['hex'] >> 16) & 0xFF) / 255,  # Normalize the Red component
             ((channel_info['hex'] >> 8) & 0xFF) / 255,      # Normalize the Green component
             (channel_info['hex'] & 0xFF) / 255)             # Normalize the Blue component
        return Colormap(colors=[c0, c1], controls=[0, 1], name=channel_info['name'])

    def updateMosaic(self, image, x_mm, y_mm, k, channel_name):
        # Calculate the pixel size for this image
        image_pixel_size_um = self.objectiveStore.get_pixel_size() * self.downsample_factor
        image_pixel_size_mm = image_pixel_size_um / 1000

        # Downsample the image
        if self.downsample_factor != 1:
            image = cv2.resize(image, (image.shape[1] // self.downsample_factor, image.shape[0] // self.downsample_factor), interpolation=cv2.INTER_AREA)

        # Adjust x_mm and y_mm to be the center of the image
        x_mm -= (image.shape[1] * image_pixel_size_mm) / 2
        y_mm -= (image.shape[0] * image_pixel_size_mm) / 2

        if not self.viewer.layers:
            # This is the first image, so set the viewer_pixel_size_mm
            self.dtype = image.dtype
            self.viewer_pixel_size_mm = image_pixel_size_mm
            self.viewer_extents = [y_mm, y_mm + image.shape[0] * image_pixel_size_mm, 
                                   x_mm, x_mm + image.shape[1] * image_pixel_size_mm]
            self.top_left_coordinate = [y_mm, x_mm]
        else:
            # Scale the image to match the viewer's resolution if necessary
            if image_pixel_size_mm != self.viewer_pixel_size_mm:
                scale_factor = image_pixel_size_mm / self.viewer_pixel_size_mm
                image = cv2.resize(image, (int(image.shape[1] * scale_factor), int(image.shape[0] * scale_factor)), interpolation=cv2.INTER_LINEAR)


        if channel_name not in self.viewer.layers:
            # Create a new layer for this channel
            channel_info = CHANNEL_COLORS_MAP.get(self.extractWavelength(channel_name), {'hex': 0xFFFFFF, 'name': 'gray'})
            if channel_info['name'] in AVAILABLE_COLORMAPS:
                color = AVAILABLE_COLORMAPS[channel_info['name']]
            else:
                color = self.generateColormap(channel_info)
            
            # Use the viewer's pixel size for all layers
            layer = self.viewer.add_image(
                np.zeros_like(image), name=channel_name, rgb=len(image.shape) == 3, colormap=color,
                visible=True, blending='additive', scale=(self.viewer_pixel_size_mm * 1000, self.viewer_pixel_size_mm * 1000)
            )
            layer.mouse_double_click_callbacks.append(self.onDoubleClick)
            layer.events.contrast_limits.connect(self.signalContrastLimits)

        # Get the layer for the channel
        layer = self.viewer.layers[channel_name]

        # Update extents to include the new image
        self.viewer_extents[0] = min(self.viewer_extents[0], y_mm)
        self.viewer_extents[1] = max(self.viewer_extents[1], y_mm + image.shape[0] * self.viewer_pixel_size_mm)
        self.viewer_extents[2] = min(self.viewer_extents[2], x_mm)
        self.viewer_extents[3] = max(self.viewer_extents[3], x_mm + image.shape[1] * self.viewer_pixel_size_mm)

        # Store the previous top-left coordinate
        prev_top_left = self.top_left_coordinate.copy()
        # Update top_left_coordinate to the new minimum values
        self.top_left_coordinate = [self.viewer_extents[0], self.viewer_extents[2]]

        # Call updateLayer to handle the layer update
        self.updateLayer(layer, image, x_mm, y_mm, k, prev_top_left)

        # Update contrast limits if necessary
        limits = self.getContrastLimits(self.dtype)
        if channel_name in self.contrast_limits:
            layer.contrast_limits = self.contrast_limits.get(channel_name, limits)

        layer.refresh()
    

    def updateLayer(self, layer, image, x_mm, y_mm, k, prev_top_left):
        # Calculate new mosaic size and position
        mosaic_height = int(math.ceil((self.viewer_extents[1] - self.viewer_extents[0]) / self.viewer_pixel_size_mm))
        mosaic_width = int(math.ceil((self.viewer_extents[3] - self.viewer_extents[2]) / self.viewer_pixel_size_mm))

        is_rgb = len(image.shape) == 3 and image.shape[2] == 3
        if layer.data.shape[:2] != (mosaic_height, mosaic_width):
            print("shifting mosaic...", layer.data.shape, (mosaic_height, mosaic_width))
            for mosaic in self.viewer.layers:
                if len(mosaic.data.shape) == 3 and mosaic.data.shape[2] == 3:
                    new_data = np.zeros((mosaic_height, mosaic_width, 3), dtype=mosaic.data.dtype)
                else:
                    new_data = np.zeros((mosaic_height, mosaic_width), dtype=mosaic.data.dtype)
 
                # Calculate offsets for the existing data based on previous and new top-left coordinates
                y_offset = int(math.floor((prev_top_left[0] - self.top_left_coordinate[0]) / self.viewer_pixel_size_mm))
                x_offset = int(math.floor((prev_top_left[1] - self.top_left_coordinate[1]) / self.viewer_pixel_size_mm))
 
                # Ensure the offsets do not exceed the bounds of the new data shape
                y_end = min(y_offset + mosaic.data.shape[0], new_data.shape[0])
                x_end = min(x_offset + mosaic.data.shape[1], new_data.shape[1])
 
                # Shift existing data
                if len(mosaic.data.shape) == 3 and mosaic.data.shape[2] == 3:
                    new_data[y_offset:y_end, x_offset:x_end, :] = mosaic.data[:y_end-y_offset, :x_end-x_offset, :]
                else:
                    new_data[y_offset:y_end, x_offset:x_end] = mosaic.data[:y_end-y_offset, :x_end-x_offset]
                mosaic.data = new_data
            self.resetView()


        # Insert new image
        y_pos = int(math.floor((y_mm - self.top_left_coordinate[0]) / self.viewer_pixel_size_mm))
        x_pos = int(math.floor((x_mm - self.top_left_coordinate[1]) / self.viewer_pixel_size_mm))

        # Ensure the indices are within bounds
        y_end = min(y_pos + image.shape[0], layer.data.shape[0])
        x_end = min(x_pos + image.shape[1], layer.data.shape[1])

        # Insert the image data
        if is_rgb:
            layer.data[y_pos:y_end, x_pos:x_end, :] = image[:y_end - y_pos, :x_end - x_pos, :]
        else:
            layer.data[y_pos:y_end, x_pos:x_end] = image[:y_end - y_pos, :x_end - x_pos]
        layer.refresh()

    def getContrastLimits(self, dtype):
        if np.issubdtype(dtype, np.integer):
            return (np.iinfo(dtype).min, np.iinfo(dtype).max)
        elif np.issubdtype(dtype, np.floating):
            return (0.0, 1.0)
        return None

    def signalContrastLimits(self, event):
        layer = event.source
        min_val, max_val = map(float, layer.contrast_limits)
        self.signal_layer_contrast_limits.emit(layer.name, min_val, max_val)
        self.contrast_limits[layer.name] = (min_val, max_val)

    def saveContrastLimits(self, layer_name, min_val, max_val):
        self.contrast_limits[layer_name] = (min_val, max_val)

    def onDoubleClick(self, layer, event):
        coords = layer.world_to_data(event.position)
        if coords is not None:
            x_mm = self.top_left_coordinate[1] + coords[-1] * self.viewer_pixel_size_mm
            y_mm = self.top_left_coordinate[0] + coords[-2] * self.viewer_pixel_size_mm
            print("clicked x,y:", (x_mm, y_mm))
            self.signal_coordinates_clicked.emit(x_mm, y_mm)

    def resetView(self):
        self.viewer.reset_view()
        for layer in self.viewer.layers:
            layer.refresh()

    def clearAllLayers(self):
        self.viewer.layers.clear()
        self.viewer_extents = None
        self.top_left_coordinate = None
        self.channels = set()
        self.dz_um = None
        self.Nz = None
        self.signal_clear_viewer.emit()

    def activate(self):
        print("ACTIVATING NAPARI MOSAIC WIDGET")
        self.viewer.window.activate()


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

        # self.dropdown_objective = QComboBox()
        # self.dropdown_objective.addItems(list(OBJECTIVES.keys()))
        # self.dropdown_objective.setCurrentText(DEFAULT_OBJECTIVE)
        self.objectivesWidget = ObjectivesWidget(self.objectiveStore)

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
        # grid_line0.addWidget(tmp,1,2)
        # grid_line0.addWidget(self.dropdown_objective, 1,3)
        grid_line0.addWidget(tmp,1,2)
        grid_line0.addWidget(self.objectivesWidget, 1,3)

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
        #self.dropdown_objective.currentIndexChanged.connect(self.update_pixel_size)
        self.objectivesWidget.dropdown.currentIndexChanged.connect(self.update_pixel_size)
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

    def update_pixel_size(self): 
        objective = self.objectiveStore.current_objective
        self.trackingController.objective = objective
        objective_info = self.objectiveStore.objectives_dict[objective]
        magnification = objective_info["magnification"]
        objective_tube_lens_mm = objective_info["tube_lens_f_mm"]
        tube_lens_mm = TUBE_LENS_MM
        pixel_size_um = CAMERA_PIXEL_SIZE_UM[CAMERA_SENSOR]
        pixel_size_xy = pixel_size_um / (magnification / (objective_tube_lens_mm / tube_lens_mm))
        self.trackingController.update_pixel_size(pixel_size_xy)
        print(f'pixel size is {pixel_size_xy:.2f} um')


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
        self.checkbox_withReflectionAutofocus.setEnabled(enabled)
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
            experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')
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
        if not self.laserAutofocusController.is_initialized:
            self.btn_set_reference.setEnabled(False)

        self.label_displacement = QLabel()
        self.label_displacement.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        self.btn_measure_displacement = QPushButton("Measure displacement")
        self.btn_measure_displacement.setCheckable(False)
        self.btn_measure_displacement.setChecked(False)
        self.btn_measure_displacement.setDefault(False)
        if not self.laserAutofocusController.is_initialized:
            self.btn_measure_displacement.setEnabled(False)

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
        if not self.laserAutofocusController.is_initialized:
            self.btn_move_to_target.setEnabled(False)
        
        self.grid = QVBoxLayout()

        line0 = QHBoxLayout()
        line0.addWidget(self.btn_initialize)
        line0.addWidget(self.btn_set_reference)
        self.grid.addLayout(line0)

        line1 = QHBoxLayout()
        line1.addWidget(QLabel('Displacement (um)'))
        line1.addWidget(self.label_displacement)
        line1.addWidget(self.btn_measure_displacement)
        self.grid.addLayout(line1)

        line2 = QHBoxLayout()
        line2.addWidget(QLabel('Target (um)'))
        line2.addWidget(self.entry_target)
        line2.addWidget(self.btn_move_to_target)
        self.grid.addLayout(line2)

        self.setLayout(self.grid)

        # make connections
        self.btn_initialize.clicked.connect(self.init_controller)
        self.btn_set_reference.clicked.connect(self.laserAutofocusController.set_reference)
        self.btn_measure_displacement.clicked.connect(self.laserAutofocusController.measure_displacement)
        self.btn_move_to_target.clicked.connect(self.move_to_target)
        self.laserAutofocusController.signal_displacement_um.connect(self.label_displacement.setNum)

    def init_controller(self):
        self.laserAutofocusController.initialize_auto()
        if self.laserAutofocusController.is_initialized:
            self.btn_set_reference.setEnabled(True)
            self.btn_measure_displacement.setEnabled(True)
            self.btn_move_to_target.setEnabled(True)

    def move_to_target(self,target_um):
        self.laserAutofocusController.move_to_target(self.entry_target.value())


class WellplateFormatWidget(QWidget):

    signalWellplateSettings = Signal(int, float, float, int, int, float, float, int)

    def __init__(self):
        super().__init__()
        # Initialize default values
        self.wellplate_format = WELLPLATE_FORMAT  # Default format
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout(self)
        self.label = QLabel("Wellplate Format", self)
        self.comboBox = QComboBox(self)
        self.comboBox.addItem("glass slide", 0)
        self.comboBox.addItem("6 wells", 6)
        self.comboBox.addItem("12 wells", 12)
        self.comboBox.addItem("24 wells", 24)
        self.comboBox.addItem("96 wells", 96)
        self.comboBox.addItem("384 wells", 384)
        self.comboBox.addItem("1536 wells", 1536)
        layout.addWidget(self.label)
        layout.addWidget(self.comboBox)
        self.comboBox.currentIndexChanged.connect(self.wellplateChanged)
        index = self.comboBox.findData(self.wellplate_format)
        if index >= 0:
            self.comboBox.setCurrentIndex(index)

    def wellplateChanged(self, index):
        self.wellplate_format = self.comboBox.itemData(index)
        self.setWellplateSettings(self.wellplate_format)

    def setWellplateSettings(self, wellplate_format):
        # Define settings for each wellplate format
        settings = {
            # Desired order: a1_x_mm, a1_y_mm, a1_x_pixel, a1_y_pixel, well_size_mm, well_spacing_mm, number_of_skip
            0: (0, 0, 0, 0, 0, 0, 0),
            6: (24.55, 23.01, 297, 209, 34.94, 39.2, 0),
            12: (24.75, 16.26, 297, 209, 22.05, 26, 0),
            24: (24.45, 22.07, 144, 108, 15.54, 19.3, 0), # 24: (17.05, 13.67, 144, 108, 15.54, 19.3, 0),
            96: (11.31, 10.75, 171, 138, 6.21, 9, 0),
            384: (12.05, 9.05, 144, 108, 3.3, 4.5, 1),
            1536: (11.0, 7.86, 144, 108, 1.5, 2.25, 0)
        }
        if wellplate_format in settings:
            self.signalWellplateSettings.emit(wellplate_format, *settings[wellplate_format])


class WellSelectionWidget(QTableWidget):

    signal_wellSelected = Signal(bool)
    signal_wellSelectedPos = Signal(float, float)

    def __init__(self, format_, *args, **kwargs):
        super(WellSelectionWidget, self).__init__(*args, **kwargs)  # Initialize the base QTableWidget
        self.well_size_mm = WELL_SIZE_MM
        self.spacing_mm = WELL_SPACING_MM
        self.number_of_skip = NUMBER_OF_SKIP
        self.a1_x_mm = A1_X_MM
        self.a1_y_mm = A1_Y_MM
        self.a1_x_pixel = A1_X_PIXEL
        self.a1_y_pixel = A1_Y_PIXEL
        self.cellDoubleClicked.connect(self.onDoubleClick)
        # self.cellClicked.connect(self.onSingleClick)
        self.itemSelectionChanged.connect(self.onSelectionChanged)
        self.setFormat(format_)

    def setFormat(self, format_):
        self.format = format_
        print("setting wellplate format")
        self.setupLayout(format_)
        self.initUI()
        self.setData()

    def setupLayout(self, format_):
        format_settings = { # format: (rows, cols, spacing_mm)
            0: (1, 1, 0),
            6: (2, 3, 39.2),
            12: (3, 4, 26),
            24: (4, 6, 18),
            96: (8, 12, 9),
            384: (16, 24, 4.5),
            1536: (32, 48, 2.25)
        }
        self.rows, self.columns, self.spacing_mm = format_settings.get(format_, (1, 1, 0))
        self.setRowCount(self.rows)
        self.setColumnCount(self.columns)
        if format_ == 0:
            self.signal_wellSelected.emit(True)

    def initUI(self):
        # Set fixed size for rows and columns
        cell_size = int(5 * self.spacing_mm)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(cell_size)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setDefaultSectionSize(cell_size)

        # Disable editing, scrollbars, and other interactions
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.NoFocus)
        self.setTabKeyNavigation(False)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDragDropOverwriteMode(False)
        self.setMouseTracking(False)

        # Calculate and set the fixed size
        margin = 4  # Add a small margin to account for borders
        width = (self.columnCount() * cell_size) + self.verticalHeader().width() + margin
        height = (self.rowCount() * cell_size) + self.horizontalHeader().height() + margin
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        if USE_NAPARI_FOR_LIVE_VIEW:
             self.set_white_boundaries_style()


    def wheelEvent(self, event):
        # Ignore wheel events to prevent scrolling
        event.ignore()

    def set_white_boundaries_style(self):
        style = """
        QTableWidget {
            gridline-color: white;
            border: 1px solid white;
        }
        QTableWidget::item {
            border: 1px solid white;
        }
        QHeaderView::section {
            color: white;
        }
        """
        self.setStyleSheet(style)

    def setData(self):
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                item = self.item(i, j)
                if not item:  # Create a new item if none exists
                    item = QTableWidgetItem()
                    self.setItem(i, j, item)
                # Reset to selectable by default
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        # Apply non-selectability as needed
        if self.format in [96, 384]:
            skip = 1  # Skip is always 1 for 96 and 384 formats
        else:
            skip = self.number_of_skip

        if skip > 0:
            for i in range(skip):
                for j in range(self.columns):  # Apply to rows
                    self.item(i, j).setFlags(self.item(i, j).flags() & ~Qt.ItemIsSelectable)
                    self.item(self.rows - 1 - i, j).setFlags(self.item(self.rows - 1 - i, j).flags() & ~Qt.ItemIsSelectable)
                for k in range(self.rows):  # Apply to columns
                    self.item(k, i).setFlags(self.item(k, i).flags() & ~Qt.ItemIsSelectable)
                    self.item(k, self.columns - 1 - i).setFlags(self.item(k, self.columns - 1 - i).flags() & ~Qt.ItemIsSelectable)

        # Update row headers
        row_headers = [chr(ord('A') + i) for i in range(self.rows)]
        self.setVerticalHeaderLabels(row_headers)

    def updateWellplateSettings(self, format_, a1_x_mm, a1_y_mm, a1_x_pixel, a1_y_pixel, well_size_mm, well_spacing_mm, number_of_skip):
        self.format = format_
        self.a1_x_mm = a1_x_mm
        self.a1_y_mm = a1_y_mm
        self.a1_x_pixel = a1_x_pixel
        self.a1_y_pixel = a1_y_pixel
        self.well_size_mm = well_size_mm
        self.spacing_mm = well_spacing_mm
        self.number_of_skip = number_of_skip
        print(self.format, self.a1_x_mm, self.a1_y_mm, self.a1_x_pixel, self.a1_y_pixel, self.well_size_mm, self.spacing_mm, self.number_of_skip)
        self.setFormat(format_)

    def onDoubleClick(self,row,col):
        print("double click well", row, col)
        if (row >= 0 + self.number_of_skip and row <= self.rows-1-self.number_of_skip ) and ( col >= 0 + self.number_of_skip and col <= self.columns-1-self.number_of_skip ):
            x_mm = col*self.spacing_mm + self.a1_x_mm + WELLPLATE_OFFSET_X_mm
            y_mm = row*self.spacing_mm + self.a1_y_mm + WELLPLATE_OFFSET_Y_mm
            self.signal_wellSelectedPos.emit(x_mm,y_mm)
            print("well location:", (x_mm,y_mm))
            self.signal_wellSelected.emit(True)
        else:
            self.signal_wellSelected.emit(False)
 
    # def onSingleClick(self,row,col):
    #     print("single click well", row, col)
    #     if (row >= 0 + self.number_of_skip and row <= self.rows-1-self.number_of_skip ) and ( col >= 0 + self.number_of_skip and col <= self.columns-1-self.number_of_skip ):
    #         self.signal_wellSelected.emit(True)
    #     else:
    #         self.signal_wellSelected.emit(False)

    def onSelectionChanged(self):
        selected_cells = self.get_selected_cells()
        self.signal_wellSelected.emit(bool(selected_cells))
            
    def get_selected_cells(self):
        list_of_selected_cells = []
        print("getting selected cells...")
        if self.format == 0:
            return list_of_selected_cells
        for index in self.selectedIndexes():
            row, col = index.row(), index.column()
            # Check if the cell is within the allowed bounds
            if (row >= 0 + self.number_of_skip and row <= self.rows - 1 - self.number_of_skip) and \
               (col >= 0 + self.number_of_skip and col <= self.columns - 1 - self.number_of_skip):
                list_of_selected_cells.append((row, col))
        if list_of_selected_cells:
            print("wells:",list_of_selected_cells)
        else:
            print("no wells")
        return list_of_selected_cells


class Well1536SelectionWidget(QWidget):

    signal_wellSelectedPos = Signal(float,float)

    def __init__(self):
        super().__init__()
        self.format = 1536
        self.selected_cells = {}  # Dictionary to keep track of selected cells and their colors
        self.current_cell = None  # To track the current (green) cell
        self.rows = 32
        self.columns = 48
        self.spacing_mm = 2.25
        self.number_of_skip = 0
        self.well_size_mm = 1.5
        self.a1_x_mm = 11.0      # measured stage position - to update
        self.a1_y_mm = 7.86      # measured stage position - to update
        self.a1_x_pixel = 144    # coordinate on the png - to update
        self.a1_y_pixel = 108    # coordinate on the png - to update
        self.initUI()

    def initUI(self):
        self.setWindowTitle('1536 Well Plate')
        self.setGeometry(100, 100, 550, 400)

        self.a = 10

        self.image = QPixmap(48*self.a, 32*self.a)
        self.image.fill(QColor('white'))
        self.label = QLabel()
        self.label.setPixmap(self.image)

        self.cell_input = QLineEdit(self)
        go_button = QPushButton('Go to well', self)
        go_button.clicked.connect(self.go_to_cell)

        self.selection_input = QLineEdit(self)
        select_button = QPushButton('Select wells', self)
        select_button.clicked.connect(self.select_cells)

        layout = QGridLayout()

        layout.addWidget(self.label,0,0,3,1)

        layout.addWidget(QLabel("Well Navigation"),1,1)
        layout.addWidget(self.cell_input,1,2)
        layout.addWidget(go_button,1,3)

        layout.addWidget(QLabel("Well Selection"),2,1)
        layout.addWidget(self.selection_input,2,2)
        layout.addWidget(select_button,2,3)

        self.setLayout(layout)

    def redraw_wells(self):
        self.image.fill(QColor('white'))  # Clear the pixmap first
        painter = QPainter(self.image)
        painter.setPen(QColor('white'))
        # Draw selected cells in red
        for (row, col), color in self.selected_cells.items():
            painter.setBrush(QColor(color))
            painter.drawRect(col * self.a, row * self.a, self.a, self.a)
        # Draw current cell in green
        if self.current_cell:
            painter.setBrush(QColor('#ff7f0e'))
            row, col = self.current_cell
            painter.drawRect(col * self.a, row * self.a, self.a, self.a)
        painter.end()
        self.label.setPixmap(self.image)

    def go_to_cell(self):
        cell_desc = self.cell_input.text().strip()
        match = re.match(r'([A-Za-z]+)(\d+)', cell_desc)
        if match:
            row_part, col_part = match.groups()
            row_index = self.row_to_index(row_part)
            col_index = int(col_part) - 1
            self.current_cell = (row_index, col_index)  # Update the current cell
            self.redraw_wells()  # Redraw with the new current cell
            x_mm = col_index * self.spacing_mm + self.a1_x_mm + WELLPLATE_OFFSET_X_mm
            y_mm = row_index * self.spacing_mm + self.a1_y_mm + WELLPLATE_OFFSET_Y_mm
            self.signal_wellSelectedPos.emit(x_mm,y_mm)

    def select_cells(self):
        # first clear selection
        self.selected_cells = {}

        pattern = r'([A-Za-z]+)(\d+):?([A-Za-z]*)(\d*)'
        cell_descriptions = self.selection_input.text().split(',')
        for desc in cell_descriptions:
            match = re.match(pattern, desc.strip())
            if match:
                start_row, start_col, end_row, end_col = match.groups()
                start_row_index = self.row_to_index(start_row)
                start_col_index = int(start_col) - 1

                if end_row and end_col:  # It's a range
                    end_row_index = self.row_to_index(end_row)
                    end_col_index = int(end_col) - 1
                    for row in range(min(start_row_index, end_row_index), max(start_row_index, end_row_index) + 1):
                        for col in range(min(start_col_index, end_col_index), max(start_col_index, end_col_index) + 1):
                            self.selected_cells[(row, col)] = '#1f77b4'
                else:  # It's a single cell
                    self.selected_cells[(start_row_index, start_col_index)] = '#1f77b4'
        self.redraw_wells()

    def row_to_index(self, row):
        index = 0
        for char in row:
            index = index * 26 + (ord(char.upper()) - ord('A') + 1)
        return index - 1

    def onSelectionChanged(self):
        selected_cells = self.get_selected_cells()

    def get_selected_cells(self):
        list_of_selected_cells = list(self.selected_cells.keys())
        return(list_of_selected_cells)

class LedMatrixSettingsDialog(QDialog):
    def __init__(self,led_array):
        self.led_array = led_array
        super().__init__()
        self.setWindowTitle("LED Matrix Settings")

        self.layout = QVBoxLayout()

        # Add QDoubleSpinBox for LED intensity (0-1)
        self.NA_spinbox = QDoubleSpinBox()
        self.NA_spinbox.setRange(0, 1)
        self.NA_spinbox.setSingleStep(0.01)
        self.NA_spinbox.setValue(self.led_array.NA)

        NA_layout = QHBoxLayout()
        NA_layout.addWidget(QLabel("NA"))
        NA_layout.addWidget(self.NA_spinbox)

        self.layout.addLayout(NA_layout)
        self.setLayout(self.layout)

        # add ok/cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.update_NA)

    def update_NA(self):
        self.led_array.set_NA(self.NA_spinbox.value())
