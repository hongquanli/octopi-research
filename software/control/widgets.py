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
import itertools
import numpy as np
from scipy.spatial import Delaunay
import shutil
from control._def import *
from PIL import Image, ImageDraw, ImageFont


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
            if self.disk_position_state == 1:
                self.config_manager.config_filename = "confocal_configurations.xml"
            else:
                self.config_manager.config_filename = "widefield_configurations.xml"
            self.config_manager.configurations = []
            self.config_manager.read_configurations()

        self.btn_toggle_widefield.clicked.connect(self.toggle_disk_position)
        self.btn_toggle_motor.clicked.connect(self.toggle_motor)

        self.slider_illumination_iris.valueChanged.connect(self.update_illumination_iris)
        self.spinbox_illumination_iris.valueChanged.connect(self.update_illumination_iris)
        self.slider_emission_iris.valueChanged.connect(self.update_emission_iris)
        self.spinbox_emission_iris.valueChanged.connect(self.update_emission_iris)
        self.dropdown_filter_slider.valueChanged.connect(self.set_filter_slider)

    def init_ui(self):

        emissionFilterLayout = QHBoxLayout()
        emissionFilterLayout.addWidget(QLabel("Emission Position"))
        self.dropdown_emission_filter = QComboBox(self)
        self.dropdown_emission_filter.addItems([str(i+1) for i in range(8)])
        emissionFilterLayout.addWidget(self.dropdown_emission_filter)

        dichroicLayout = QHBoxLayout()
        dichroicLayout.addWidget(QLabel("Dichroic Position"))
        self.dropdown_dichroic = QComboBox(self)
        self.dropdown_dichroic.addItems([str(i+1) for i in range(5)])
        dichroicLayout.addWidget(self.dropdown_dichroic)

        illuminationIrisLayout = QHBoxLayout()
        illuminationIrisLayout.addWidget(QLabel("Illumination Iris"))
        self.slider_illumination_iris = QSlider(Qt.Horizontal)
        self.slider_illumination_iris.setRange(0, 100)
        self.spinbox_illumination_iris = QSpinBox()
        self.spinbox_illumination_iris.setRange(0, 100)
        self.spinbox_illumination_iris.setKeyboardTracking(False)
        illuminationIrisLayout.addWidget(self.slider_illumination_iris)
        illuminationIrisLayout.addWidget(self.spinbox_illumination_iris)

        emissionIrisLayout = QHBoxLayout()
        emissionIrisLayout.addWidget(QLabel("Emission Iris"))
        self.slider_emission_iris = QSlider(Qt.Horizontal)
        self.slider_emission_iris.setRange(0, 100)
        self.spinbox_emission_iris = QSpinBox()
        self.spinbox_emission_iris.setRange(0, 100)
        self.spinbox_emission_iris.setKeyboardTracking(False)
        emissionIrisLayout.addWidget(self.slider_emission_iris)
        emissionIrisLayout.addWidget(self.spinbox_emission_iris)

        filterSliderLayout = QHBoxLayout()
        filterSliderLayout.addWidget(QLabel("Filter Slider"))
        #self.dropdown_filter_slider = QComboBox(self)
        #self.dropdown_filter_slider.addItems(["0", "1", "2", "3"])
        self.dropdown_filter_slider = QSlider(Qt.Horizontal)
        self.dropdown_filter_slider.setRange(0, 3)
        self.dropdown_filter_slider.setTickPosition(QSlider.TicksBelow)
        self.dropdown_filter_slider.setTickInterval(1)
        filterSliderLayout.addWidget(self.dropdown_filter_slider)

        self.btn_toggle_widefield = QPushButton("Switch to Confocal")

        self.btn_toggle_motor = QPushButton("Disk Motor On")
        self.btn_toggle_motor.setCheckable(True)

        layout = QGridLayout(self)

        # row 1
        if self.xlight.has_dichroic_filter_slider:
            layout.addLayout(filterSliderLayout,0,0,1,2)
        layout.addWidget(self.btn_toggle_motor,0,2)
        layout.addWidget(self.btn_toggle_widefield,0,3)

        # row 2
        if self.xlight.has_dichroic_filters_wheel:
            layout.addWidget(QLabel("Dichroic Filter Wheel"),1,0)
            layout.addWidget(self.dropdown_dichroic,1,1)
        if self.xlight.has_illumination_iris_diaphragm:
            layout.addLayout(illuminationIrisLayout,1,2,1,2)

        # row 3
        if self.xlight.has_emission_filters_wheel:
            layout.addWidget(QLabel("Emission Filter Wheel"),2,0)
            layout.addWidget(self.dropdown_emission_filter,2,1)
        if self.xlight.has_emission_iris_diaphragm:
            layout.addLayout(emissionIrisLayout,2,2,1,2)

        layout.setColumnStretch(2,1)
        layout.setColumnStretch(3,1)
        self.setLayout(layout)


    def disable_all_buttons(self):
        self.dropdown_emission_filter.setEnabled(False)
        self.dropdown_dichroic.setEnabled(False)
        self.btn_toggle_widefield.setEnabled(False)
        self.btn_toggle_motor.setEnabled(False)
        self.slider_illumination_iris.setEnabled(False)
        self.spinbox_illumination_iris.setEnabled(False)
        self.slider_emission_iris.setEnabled(False)
        self.spinbox_emission_iris.setEnabled(False)
        self.dropdown_filter_slider.setEnabled(False)

    def enable_all_buttons(self):
        self.dropdown_emission_filter.setEnabled(True)
        self.dropdown_dichroic.setEnabled(True)
        self.btn_toggle_widefield.setEnabled(True)
        self.btn_toggle_motor.setEnabled(True)
        self.slider_illumination_iris.setEnabled(True)
        self.spinbox_illumination_iris.setEnabled(True)
        self.slider_emission_iris.setEnabled(True)
        self.spinbox_emission_iris.setEnabled(True)
        self.dropdown_filter_slider.setEnabled(True)

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

    def update_illumination_iris(self, value):
        self.disable_all_buttons()
        # Update both slider and spinbox to ensure they're in sync
        self.slider_illumination_iris.setValue(value)
        self.spinbox_illumination_iris.setValue(value)
        self.xlight.set_illumination_iris(value)
        self.enable_all_buttons()

    def update_emission_iris(self, value):
        self.disable_all_buttons()
        # Update both slider and spinbox to ensure they're in sync
        self.slider_emission_iris.setValue(value)
        self.spinbox_emission_iris.setValue(value)
        self.xlight.set_emission_iris(value)
        self.enable_all_buttons()

    def set_filter_slider(self, index):
        self.disable_all_buttons()
        position = str(self.dropdown_filter_slider.value())
        self.xlight.set_filter_slider(position)
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
        self.dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dropdown.addItems(self.objectiveStore.objectives_dict.keys())
        self.dropdown.currentTextChanged.connect(self.on_objective_changed)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("Objective Lens"))
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
        self.dropdown_pixelFormat.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))
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
            res_options = [f"{res[0]} x {res[1]}" for res in self.camera.res_list]
            self.dropdown_res = QComboBox()
            self.dropdown_res.addItems(res_options)
            self.dropdown_res.setCurrentText(current_res_string)

            self.dropdown_res.currentTextChanged.connect(self.change_full_res)
        except AttributeError as ae:
            print(ae)
            self.dropdown_res = QComboBox()
            self.dropdown_res.setEnabled(False)
            pass
        format_line.addWidget(QLabel(" FOV Resolution"))
        format_line.addWidget(self.dropdown_res)
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
        roi_line.addWidget(QLabel('Height'))
        roi_line.addWidget(self.entry_ROI_height)
        roi_line.addStretch()
        roi_line.addWidget(QLabel('Y-offset'))
        roi_line.addWidget(self.entry_ROI_offset_y)
        roi_line.addStretch()
        roi_line.addWidget(QLabel('Width'))
        roi_line.addWidget(self.entry_ROI_width)
        roi_line.addStretch()
        roi_line.addWidget(QLabel('X-offset'))
        roi_line.addWidget(self.entry_ROI_offset_x)
        self.camera_layout.addLayout(roi_line)

        if DISPLAY_TOUPCAMER_BLACKLEVEL_SETTINGS is True:
            blacklevel_line = QHBoxLayout()
            blacklevel_line.addWidget(QLabel('Black Level'))

            self.label_blackLevel = QSpinBox()
            self.label_blackLevel.setMinimum(0)
            self.label_blackLevel.setMaximum(31)
            self.label_blackLevel.valueChanged.connect(self.update_blacklevel)
            self.label_blackLevel.setSuffix(" ")

            blacklevel_line.addWidget(self.label_blackLevel)

            self.camera_layout.addLayout(blacklevel_line)

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

    def update_blacklevel(self, blacklevel):
        try:
            self.camera.set_blacklevel(blacklevel)
        except AttributeError:
            pass


class LiveControlWidget(QFrame):

    signal_newExposureTime = Signal(float)
    signal_newAnalogGain = Signal(float)
    signal_autoLevelSetting = Signal(bool)
    signal_live_configuration = Signal(object)
    signal_start_live = Signal()

    def __init__(self, streamHandler, liveController, configurationManager=None, show_trigger_options=True, show_display_options=False, show_autolevel = False, autolevel=False, stretch=True, main=None, *args, **kwargs):
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

        self.add_components(show_trigger_options,show_display_options,show_autolevel,autolevel,stretch)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.update_microscope_mode_by_name(self.currentConfiguration.name)

        self.is_switching_mode = False # flag used to prevent from settings being set by twice - from both mode change slot and value change slot; another way is to use blockSignals(True)

    def add_components(self,show_trigger_options,show_display_options,show_autolevel,autolevel,stretch):
        # line 0: trigger mode
        self.triggerMode = None
        self.dropdown_triggerManu = QComboBox()
        self.dropdown_triggerManu.addItems([TriggerMode.SOFTWARE,TriggerMode.HARDWARE,TriggerMode.CONTINUOUS])
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dropdown_triggerManu.setSizePolicy(sizePolicy)

        # line 1: fps
        self.entry_triggerFPS = QDoubleSpinBox()
        self.entry_triggerFPS.setMinimum(0.02)
        self.entry_triggerFPS.setMaximum(1000)
        self.entry_triggerFPS.setSingleStep(1)
        self.entry_triggerFPS.setValue(self.fps_trigger)
        self.entry_triggerFPS.setDecimals(0)

        # line 2: choose microscope mode / toggle live mode
        self.dropdown_modeSelection = QComboBox()
        for microscope_configuration in self.configurationManager.configurations:
            self.dropdown_modeSelection.addItems([microscope_configuration.name])
        self.dropdown_modeSelection.setCurrentText(self.currentConfiguration.name)
        self.dropdown_modeSelection.setSizePolicy(sizePolicy)

        self.btn_live = QPushButton("Start Live")
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(False)
        self.btn_live.setDefault(False)
        self.btn_live.setStyleSheet("background-color: #C2C2FF")
        self.btn_live.setSizePolicy(sizePolicy)

        # line 3: exposure time and analog gain associated with the current mode
        self.entry_exposureTime = QDoubleSpinBox()
        self.entry_exposureTime.setMinimum(self.liveController.camera.EXPOSURE_TIME_MS_MIN)
        self.entry_exposureTime.setMaximum(self.liveController.camera.EXPOSURE_TIME_MS_MAX)
        self.entry_exposureTime.setSingleStep(1)
        self.entry_exposureTime.setSuffix(' ms')
        self.entry_exposureTime.setValue(0)
        self.entry_exposureTime.setSizePolicy(sizePolicy)

        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain.setMinimum(0)
        self.entry_analogGain.setMaximum(24)
        # self.entry_analogGain.setSuffix('x')
        self.entry_analogGain.setSingleStep(0.1)
        self.entry_analogGain.setValue(0)
        self.entry_analogGain.setSizePolicy(sizePolicy)

        self.slider_illuminationIntensity = QSlider(Qt.Horizontal)
        self.slider_illuminationIntensity.setTickPosition(QSlider.TicksBelow)
        self.slider_illuminationIntensity.setMinimum(0)
        self.slider_illuminationIntensity.setMaximum(100)
        self.slider_illuminationIntensity.setValue(100)
        self.slider_illuminationIntensity.setSingleStep(2)

        self.entry_illuminationIntensity = QDoubleSpinBox()
        self.entry_illuminationIntensity.setMinimum(0)
        self.entry_illuminationIntensity.setMaximum(100)
        self.entry_illuminationIntensity.setSingleStep(1)
        self.entry_illuminationIntensity.setSuffix('%')
        self.entry_illuminationIntensity.setValue(100)

        # line 4: display fps and resolution scaling
        self.entry_displayFPS = QDoubleSpinBox()
        self.entry_displayFPS.setMinimum(1)
        self.entry_displayFPS.setMaximum(240)
        self.entry_displayFPS.setSingleStep(1)
        self.entry_displayFPS.setDecimals(0)
        self.entry_displayFPS.setValue(self.fps_display)

        self.slider_resolutionScaling = QSlider(Qt.Horizontal)
        self.slider_resolutionScaling.setTickPosition(QSlider.TicksBelow)
        self.slider_resolutionScaling.setMinimum(10)
        self.slider_resolutionScaling.setMaximum(100)
        self.slider_resolutionScaling.setValue(DEFAULT_DISPLAY_CROP)
        self.slider_resolutionScaling.setSingleStep(10)

        self.label_resolutionScaling = QSpinBox()
        self.label_resolutionScaling.setMinimum(10)
        self.label_resolutionScaling.setMaximum(100)
        self.label_resolutionScaling.setValue(self.slider_resolutionScaling.value())
        self.label_resolutionScaling.setSuffix(" %")
        self.slider_resolutionScaling.setSingleStep(5)

        self.slider_resolutionScaling.valueChanged.connect(lambda v: self.label_resolutionScaling.setValue(round(v)))
        self.label_resolutionScaling.valueChanged.connect(lambda v: self.slider_resolutionScaling.setValue(round(v)))

        # autolevel
        self.btn_autolevel = QPushButton('Autolevel')
        self.btn_autolevel.setCheckable(True)
        self.btn_autolevel.setChecked(autolevel)

        # Determine the maximum width needed
        self.entry_illuminationIntensity.setMinimumWidth(self.btn_live.sizeHint().width())
        self.btn_autolevel.setMinimumWidth(self.btn_autolevel.sizeHint().width())

        max_width = max(
            self.btn_autolevel.minimumWidth(),
            self.entry_illuminationIntensity.minimumWidth()
        )

        # Set the fixed width for all three widgets
        self.entry_illuminationIntensity.setFixedWidth(max_width)
        self.btn_autolevel.setFixedWidth(max_width)

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
        self.btn_autolevel.toggled.connect(self.signal_autoLevelSetting.emit)

        # layout
        grid_line1 = QHBoxLayout()
        grid_line1.addWidget(QLabel('Live Configuration'))
        grid_line1.addWidget(self.dropdown_modeSelection, 2)
        grid_line1.addWidget(self.btn_live, 1)

        grid_line2 = QHBoxLayout()
        grid_line2.addWidget(QLabel('Exposure Time'))
        grid_line2.addWidget(self.entry_exposureTime)
        gain_label = QLabel(' Analog Gain')
        gain_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid_line2.addWidget(gain_label)
        grid_line2.addWidget(self.entry_analogGain)
        if show_autolevel:
            grid_line2.addWidget(self.btn_autolevel)

        grid_line4 = QHBoxLayout()
        grid_line4.addWidget(QLabel('Illumination'))
        grid_line4.addWidget(self.slider_illuminationIntensity)
        grid_line4.addWidget(self.entry_illuminationIntensity)

        grid_line0 = QHBoxLayout()
        if show_trigger_options:
            grid_line0.addWidget(QLabel('Trigger Mode'))
            grid_line0.addWidget(self.dropdown_triggerManu)
            grid_line0.addWidget(QLabel('Trigger FPS'))
            grid_line0.addWidget(self.entry_triggerFPS)

        grid_line05 = QHBoxLayout()
        show_dislpay_fps = False
        if show_display_options:
            resolution_label = QLabel('Display Resolution')
            resolution_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid_line05.addWidget(resolution_label)
            grid_line05.addWidget(self.slider_resolutionScaling)
            if show_dislpay_fps:
                grid_line05.addWidget(QLabel('Display FPS'))
                grid_line05.addWidget(self.entry_displayFPS)
            else:
                grid_line05.addWidget(self.label_resolutionScaling)

        self.grid = QVBoxLayout()
        if show_trigger_options:
            self.grid.addLayout(grid_line0)
        self.grid.addLayout(grid_line1)
        self.grid.addLayout(grid_line2)
        self.grid.addLayout(grid_line4)
        if show_display_options:
            self.grid.addLayout(grid_line05)
        if not stretch:
            self.grid.addStretch()
        self.setLayout(self.grid)


    def toggle_live(self,pressed):
        if pressed:
            self.liveController.start_live()
            self.btn_live.setText('Stop Live')
            self.signal_start_live.emit()
        else:
            self.liveController.stop_live()
            self.btn_live.setText('Start Live')

    def toggle_autolevel(self,autolevel_on):
        self.btn_autolevel.setChecked(autolevel_on)

    def update_camera_settings(self):
        self.signal_newAnalogGain.emit(self.entry_analogGain.value())
        self.signal_newExposureTime.emit(self.entry_exposureTime.value())

    def update_microscope_mode_by_name(self,current_microscope_mode_name):
        self.is_switching_mode = True
        # identify the mode selected (note that this references the object in self.configurationManager.configurations)
        self.currentConfiguration = next((config for config in self.configurationManager.configurations if config.name == current_microscope_mode_name), None)
        self.signal_live_configuration.emit(self.currentConfiguration)
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
        self.navigationController = navigationController
        self.slider_value = 0.00
        self.add_components()

    def add_components(self):
        # Row 1: Slider and Double Spin Box for direct control
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setMinimum(0)
        self.slider.setMaximum(int(OBJECTIVE_PIEZO_RANGE_UM * 100))  # Multiplied by 100 for 0.01 precision

        self.spinBox = QDoubleSpinBox(self)
        self.spinBox.setRange(0.0, OBJECTIVE_PIEZO_RANGE_UM)
        self.spinBox.setDecimals(2)
        self.spinBox.setSingleStep(0.01)
        self.spinBox.setSuffix(' μm')

        # Row 3: Home Button
        self.home_btn = QPushButton(f" Set to {OBJECTIVE_PIEZO_HOME_UM} μm ", self)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.home_btn)
        hbox1.addWidget(self.slider)
        hbox1.addWidget(self.spinBox)

        # Row 2: Increment Double Spin Box, Move Up and Move Down Buttons
        self.increment_spinBox = QDoubleSpinBox(self)
        self.increment_spinBox.setRange(0.0, 100.0)
        self.increment_spinBox.setDecimals(2)
        self.increment_spinBox.setSingleStep(1)
        self.increment_spinBox.setValue(1.00)
        self.increment_spinBox.setSuffix(' μm')
        self.move_up_btn = QPushButton("Move Up", self)
        self.move_down_btn = QPushButton("Move Down", self)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.increment_spinBox)
        hbox2.addWidget(self.move_up_btn)
        hbox2.addWidget(self.move_down_btn)

        # Vertical Layout to include all HBoxes
        vbox = QVBoxLayout()
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)

        self.setLayout(vbox)

        # Connect signals and slots
        self.slider.valueChanged.connect(self.update_from_slider)
        self.spinBox.valueChanged.connect(self.update_from_spinBox)
        self.move_up_btn.clicked.connect(lambda: self.adjust_position(True))
        self.move_down_btn.clicked.connect(lambda: self.adjust_position(False))
        self.home_btn.clicked.connect(self.home)

    def update_from_slider(self, value):
        self.slider_value = value / 100  # Convert back to float with two decimal places
        self.update_spinBox()
        self.update_piezo_position()

    def update_from_spinBox(self, value):
        self.slider_value = value
        self.update_slider()
        self.update_piezo_position()

    def update_spinBox(self):
        self.spinBox.blockSignals(True)
        self.spinBox.setValue(self.slider_value)
        self.spinBox.blockSignals(False)

    def update_slider(self):
        self.slider.blockSignals(True)
        self.slider.setValue(int(self.slider_value * 100))
        self.slider.blockSignals(False)

    def update_piezo_position(self):
        displacement_um = self.slider_value
        self.navigationController.set_piezo_um(displacement_um)

    def adjust_position(self, up):
        increment = self.increment_spinBox.value()
        if up:
            self.slider_value = min(OBJECTIVE_PIEZO_RANGE_UM, self.slider_value + increment)
        else:
            self.slider_value = max(0, self.slider_value - increment)
        self.update_spinBox()
        self.update_slider()
        self.update_piezo_position()

    def home(self):
        self.slider_value = OBJECTIVE_PIEZO_HOME_UM
        self.update_spinBox()
        self.update_slider()
        self.update_piezo_position()

    def update_displacement_um_display(self, displacement):
        self.slider_value = round(displacement, 2)
        self.update_spinBox()
        self.update_slider()


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

        self.grid = QVBoxLayout()
        self.grid.addLayout(grid_line1)
        self.grid.addLayout(grid_line2)
        self.grid.addLayout(grid_line3)
        self.grid.addWidget(self.btn_record)
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
        self.flag_click_to_move = navigationController.click_to_move
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        x_label = QLabel('X :')
        x_label.setFixedWidth(20)
        self.label_Xpos = QLabel()
        self.label_Xpos.setNum(0)
        self.label_Xpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dX = QDoubleSpinBox()
        self.entry_dX.setMinimum(0)
        self.entry_dX.setMaximum(25)
        self.entry_dX.setSingleStep(0.2)
        self.entry_dX.setValue(0)
        self.entry_dX.setDecimals(3)
        self.entry_dX.setSuffix(' mm')
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

        self.checkbox_clickToMove = QCheckBox('Click to Move')
        self.checkbox_clickToMove.setChecked(False)
        self.checkbox_clickToMove.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))

        y_label = QLabel('Y :')
        y_label.setFixedWidth(20)
        self.label_Ypos = QLabel()
        self.label_Ypos.setNum(0)
        self.label_Ypos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dY = QDoubleSpinBox()
        self.entry_dY.setMinimum(0)
        self.entry_dY.setMaximum(25)
        self.entry_dY.setSingleStep(0.2)
        self.entry_dY.setValue(0)
        self.entry_dY.setDecimals(3)
        self.entry_dY.setSuffix(' mm')

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

        z_label = QLabel('Z :')
        z_label.setFixedWidth(20)
        self.label_Zpos = QLabel()
        self.label_Zpos.setNum(0)
        self.label_Zpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dZ = QDoubleSpinBox()
        self.entry_dZ.setMinimum(0)
        self.entry_dZ.setMaximum(1000)
        self.entry_dZ.setSingleStep(0.2)
        self.entry_dZ.setValue(0)
        self.entry_dZ.setDecimals(3)
        self.entry_dZ.setSuffix(' μm')
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

        self.btn_load_slide = QPushButton('Move To Loading Position')
        self.btn_load_slide.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        grid_line0 = QGridLayout()
        grid_line0.addWidget(x_label, 0,0)
        grid_line0.addWidget(self.label_Xpos, 0,1)
        grid_line0.addWidget(self.entry_dX, 0,2)
        grid_line0.addWidget(self.btn_moveX_forward, 0,3)
        grid_line0.addWidget(self.btn_moveX_backward, 0,4)

        grid_line0.addWidget(y_label, 1,0)
        grid_line0.addWidget(self.label_Ypos, 1,1)
        grid_line0.addWidget(self.entry_dY, 1,2)
        grid_line0.addWidget(self.btn_moveY_forward, 1,3)
        grid_line0.addWidget(self.btn_moveY_backward, 1,4)

        grid_line0.addWidget(z_label, 2,0)
        grid_line0.addWidget(self.label_Zpos, 2,1)
        grid_line0.addWidget(self.entry_dZ, 2,2)
        grid_line0.addWidget(self.btn_moveZ_forward, 2,3)
        grid_line0.addWidget(self.btn_moveZ_backward, 2,4)

        grid_line3 = QHBoxLayout()

        if self.widget_configuration == 'full':
            grid_line3.addWidget(self.btn_home_X)
            grid_line3.addWidget(self.btn_home_Y)
            grid_line3.addWidget(self.btn_home_Z)
            grid_line3.addWidget(self.btn_zero_X)
            grid_line3.addWidget(self.btn_zero_Y)
            grid_line3.addWidget(self.btn_zero_Z)
        else:
            grid_line3.addWidget(self.btn_load_slide, 1)
            grid_line3.addWidget(self.btn_home_Z, 1)
            grid_line3.addWidget(self.btn_zero_Z, 1)

        if not ENABLE_CLICK_TO_MOVE_BY_DEFAULT:
            grid_line3.addWidget(self.checkbox_clickToMove, 1)

        self.grid = QVBoxLayout()
        self.grid.addLayout(grid_line0)
        self.grid.addLayout(grid_line3)
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

    def toggle_click_to_move(self, started):
        if started:
            self.flag_click_to_move = self.navigationController.get_flag_click_to_move()
            self.setEnabled_all(False)
            self.checkbox_clickToMove.setChecked(False) # should set navigationController.click_to_move to False
            self.navigationController.click_to_move = False
            print("set click to move off")
        else:
            self.setEnabled_all(True)
            self.checkbox_clickToMove.setChecked(self.flag_click_to_move)
            self.navigationController.click_to_move = self.flag_click_to_move
            print("restored click to move to", "on" if self.flag_click_to_move else "off")

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
        mm_per_ustep = self.navigationController.get_mm_per_ustep_X()
        deltaX = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_dX.setValue(deltaX)
    def set_deltaY(self,value):
        mm_per_ustep = self.navigationController.get_mm_per_ustep_Y()
        deltaY = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_dY.setValue(deltaY)
    def set_deltaZ(self,value):
        mm_per_ustep = self.navigationController.get_mm_per_ustep_Z()
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
        self.btn_load_slide.setText('Move to Scanning Position')
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
        self.btn_load_slide.setText('Move to Loading Position')
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

    def replace_slide_controller(self, slidePositionController):
        self.slidePositionController = slidePositionController
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.slot_slide_loading_position_reached)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.slot_slide_scanning_position_reached)


class NavigationBarWidget(QWidget):
    def __init__(self, navigationController=None, slidePositionController=None, add_z_buttons=True,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigationController = navigationController
        self.slidePositionController = slidePositionController
        self.add_z_buttons = add_z_buttons
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 4)  # Reduce vertical margins to make it thinner

        # Move to Loading Position button
        self.btn_load_slide = QPushButton('Move To Loading Position')
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF")
        self.btn_load_slide.clicked.connect(self.switch_position)

        # Click to Move checkbox
        self.checkbox_clickToMove = QCheckBox('Click to Move')
        self.checkbox_clickToMove.setChecked(False)

        # Home Z and Zero Z
        if self.add_z_buttons:
            if self.slidePositionController is not None:
                layout.addWidget(self.btn_load_slide)
                layout.addSpacing(10)

            self.btn_home_Z = QPushButton('Home Z')
            self.btn_home_Z.clicked.connect(self.home_z)
            layout.addWidget(self.btn_home_Z)
            layout.addSpacing(20)

            self.btn_zero_Z = QPushButton('Zero Z')
            self.btn_zero_Z.clicked.connect(self.zero_z)
            layout.addWidget(self.btn_zero_Z)
            layout.addSpacing(20)

            if self.navigationController is not None:
                layout.addWidget(self.checkbox_clickToMove)
                layout.addSpacing(10)

        # X position
        x_label = QLabel('X:')
        self.label_Xpos = QLabel('00.000 mm')
        self.label_Xpos.setFixedWidth(self.label_Xpos.sizeHint().width())
        #self.label_Xpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        # Y position
        y_label = QLabel('Y:')
        self.label_Ypos = QLabel('00.000 mm')
        self.label_Ypos.setFixedWidth(self.label_Ypos.sizeHint().width())
        #self.label_Ypos.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        # Z position
        z_label = QLabel('Z:')
        self.label_Zpos = QLabel('0000.000 μm')
        self.label_Zpos.setFixedWidth(self.label_Zpos.sizeHint().width())
        #self.label_Zpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        # Add widgets to layout
        layout.addStretch(1)
        layout.addSpacing(10)
        layout.addWidget(x_label)
        layout.addWidget(self.label_Xpos)
        layout.addSpacing(10)
        layout.addWidget(y_label)
        layout.addWidget(self.label_Ypos)
        layout.addSpacing(10)
        layout.addWidget(z_label)
        layout.addWidget(self.label_Zpos)
        layout.addSpacing(10)
        layout.addStretch(1)

        self.setLayout(layout)
        self.setFixedHeight(self.sizeHint().height())  # Set fixed height to make it as thin as possible
        self.connect_signals()

    def update_x_position(self, x):
        self.label_Xpos.setText(f"{x:.3f} mm")

    def update_y_position(self, y):
        self.label_Ypos.setText(f"{y:.3f} mm")

    def update_z_position(self, z):
        self.label_Zpos.setText(f"{z:.3f} μm")

    def home_z(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing\n(Sets current Z to 0 μm)")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.home_z()

    def zero_z(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to zero\n(Moves Z to 0 μm)")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.zero_z()

    def switch_position(self):
        if self.btn_load_slide.text() == 'Move To Loading Position':
            self.slidePositionController.move_to_slide_loading_position()
        else:
            self.slidePositionController.move_to_slide_scanning_position()
        self.btn_load_slide.setEnabled(False)

    def slot_slide_loading_position_reached(self):
        self.btn_load_slide.setText('Move to Scanning Position')
        self.btn_load_slide.setStyleSheet("background-color: #C2FFC2")
        self.btn_load_slide.setEnabled(True)

    def slot_slide_scanning_position_reached(self):
        self.btn_load_slide.setText('Move To Loading Position')
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF")
        self.btn_load_slide.setEnabled(True)

    def replace_slide_controller(self, slidePositionController):
        self.slidePositionController = slidePositionController
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.slot_slide_loading_position_reached)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.slot_slide_scanning_position_reached)

    def connect_signals(self):
        if self.navigationController is not None:
            self.checkbox_clickToMove.stateChanged.connect(self.navigationController.set_flag_click_to_move)
        if self.slidePositionController is not None:
            self.slidePositionController.signal_slide_loading_position_reached.connect(self.slot_slide_loading_position_reached)
            self.slidePositionController.signal_slide_scanning_position_reached.connect(self.slot_slide_scanning_position_reached)


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
        grid_line1 = QHBoxLayout()
        grid_line1.addWidget(QLabel('DAC0'))
        grid_line1.addWidget(self.slider_DAC0)
        grid_line1.addWidget(self.entry_DAC0)
        grid_line1.addWidget(QLabel('DAC1'))
        grid_line1.addWidget(self.slider_DAC1)
        grid_line1.addWidget(self.entry_DAC1)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line1,1,0)
        self.setLayout(self.grid)

    def set_DAC0(self,value):
        self.microcontroller.analog_write_onboard_DAC(0,round(value*65535/100))

    def set_DAC1(self,value):
        self.microcontroller.analog_write_onboard_DAC(1,round(value*65535/100))


class AutoFocusWidget(QFrame):
    signal_autoLevelSetting = Signal(bool)

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
        self.entry_delta.setSuffix(' μm')
        self.entry_delta.setValue(1.524)
        self.entry_delta.setKeyboardTracking(False)
        self.entry_delta.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.autofocusController.set_deltaZ(1.524)

        self.entry_N = QSpinBox()
        self.entry_N.setMinimum(3)
        self.entry_N.setMaximum(10000)
        self.entry_N.setFixedWidth(self.entry_N.sizeHint().width())
        self.entry_N.setMaximum(20)
        self.entry_N.setSingleStep(1)
        self.entry_N.setValue(10)
        self.entry_N.setKeyboardTracking(False)
        self.entry_N.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.autofocusController.set_N(10)

        self.btn_autofocus = QPushButton('Autofocus')
        self.btn_autofocus.setDefault(False)
        self.btn_autofocus.setCheckable(True)
        self.btn_autofocus.setChecked(False)

        self.btn_autolevel = QPushButton('Autolevel')
        self.btn_autolevel.setCheckable(True)
        self.btn_autolevel.setChecked(False)
        self.btn_autolevel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # layout
        self.grid = QVBoxLayout()
        grid_line0 = QHBoxLayout()
        grid_line0.addWidget(QLabel('\u0394 Z'))
        grid_line0.addWidget(self.entry_delta)
        grid_line0.addSpacing(20)
        grid_line0.addWidget(QLabel('# of Z-Planes'))
        grid_line0.addWidget(self.entry_N)
        grid_line0.addSpacing(20)
        grid_line0.addWidget(self.btn_autolevel)

        self.grid.addLayout(grid_line0)
        self.grid.addWidget(self.btn_autofocus)
        self.setLayout(self.grid)

        # connections
        self.btn_autofocus.toggled.connect(lambda : self.autofocusController.autofocus(False))
        self.btn_autolevel.toggled.connect(self.signal_autoLevelSetting.emit)
        self.entry_delta.valueChanged.connect(self.set_deltaZ)
        self.entry_N.valueChanged.connect(self.autofocusController.set_N)
        self.autofocusController.autofocusFinished.connect(self.autofocus_is_finished)

    def set_deltaZ(self,value):
        mm_per_ustep = self.autofocusController.navigationController.get_mm_per_ustep_Z()
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
    signal_acquisition_z_levels = Signal(int)
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
        self.entry_dt.setSuffix(' s')
        self.entry_dt.setKeyboardTracking(False)

        self.entry_Nt = QSpinBox()
        self.entry_Nt.setMinimum(1)
        self.entry_Nt.setMaximum(5000)   # @@@ to be changed
        self.entry_Nt.setSingleStep(1)
        self.entry_Nt.setValue(1)
        self.entry_Nt.setKeyboardTracking(False)

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection) # ref: https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum

        self.checkbox_withAutofocus = QCheckBox('Contrast AF')
        self.checkbox_withAutofocus.setChecked(MULTIPOINT_CONTRAST_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MULTIPOINT_CONTRAST_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_genFocusMap = QCheckBox('Focus Map')
        self.checkbox_genFocusMap.setChecked(False)

        self.checkbox_withReflectionAutofocus = QCheckBox('Reflection AF')
        self.checkbox_withReflectionAutofocus.setChecked(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_stitchOutput = QCheckBox('Stitch Scans')
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

        grid_af = QGridLayout()
        grid_af.addItem(QSpacerItem(7, 1, QSizePolicy.Fixed, QSizePolicy.Minimum), 0, 0)
        grid_af.addWidget(self.checkbox_withAutofocus,0,1)
        if SUPPORT_LASER_AUTOFOCUS:
            grid_af.addWidget(self.checkbox_withReflectionAutofocus,1,1)
        grid_af.addWidget(self.checkbox_genFocusMap,2,1)
        if ENABLE_STITCHER:
            grid_af.addWidget(self.checkbox_stitchOutput,3,1)
        grid_af.addItem(QSpacerItem(6, 1, QSizePolicy.Fixed, QSizePolicy.Minimum), 0, 2)

        grid_line3 = QHBoxLayout()
        grid_line3.addWidget(self.list_configurations, 2)
        # grid_line3.addWidget(self.checkbox_withAutofocus)
        grid_line3.addLayout(grid_af, 1)
        grid_line3.addWidget(self.btn_startAcquisition, 1)

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
        self.entry_NZ.valueChanged.connect(self.signal_acquisition_z_levels.emit)
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
        mm_per_ustep = self.multipointController.navigationController.get_mm_per_ustep_X()
        deltaX = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_deltaX.setValue(deltaX)
        self.multipointController.set_deltaX(deltaX)

    def set_deltaY(self,value):
        mm_per_ustep = self.multipointController.navigationController.get_mm_per_ustep_Y()
        deltaY = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_deltaY.setValue(deltaY)
        self.multipointController.set_deltaY(deltaY)

    def set_deltaZ(self,value):
        mm_per_ustep = self.multipointController.navigationController.get_mm_per_ustep_Z()
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


class FlexibleMultiPointWidget(QFrame):

    signal_acquisition_started = Signal(bool) # true = started, false = finished
    signal_acquisition_channels = Signal(list) # list channels
    signal_acquisition_shape = Signal(int, float) # Nz, dz
    signal_stitcher_z_levels = Signal(int) # live Nz
    signal_stitcher_widget = Signal(bool) # signal start stitcher

    def __init__(self, navigationController, navigationViewer, multipointController, objectiveStore, configurationManager = None, main=None, scanCoordinates=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_used_locations = None
        self.last_used_location_ids = None
        self.multipointController = multipointController
        self.objectiveStore = objectiveStore
        self.configurationManager = configurationManager
        self.navigationController = navigationController
        self.navigationViewer = navigationViewer
        self.scanCoordinates = scanCoordinates
        self.base_path_is_set = False
        self.location_list = np.empty((0, 3), dtype=float)
        self.location_ids = np.empty((0,), dtype='<U20')
        self.region_coordinates = {} # region_id, region center coord
        self.region_fov_coordinates_dict = {} # region_id, region fov coords
        self.use_overlap = USE_OVERLAP_FOR_FLEXIBLE
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.acquisition_in_place = False

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
        self.lineEdit_experimentID.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.lineEdit_experimentID.setFixedWidth(96)

        self.dropdown_location_list = QComboBox()
        self.dropdown_location_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        self.btn_show_table_location_list = QPushButton('Edit') # Open / Edit

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
        self.entry_NX.setMaximum(1000)
        self.entry_NX.setMinimumWidth(self.entry_NX.sizeHint().width())
        self.entry_NX.setMaximum(50)
        self.entry_NX.setSingleStep(1)
        self.entry_NX.setValue(1)
        self.entry_NX.setKeyboardTracking(False)
        #self.entry_NX.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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
        self.entry_NY.setMaximum(1000)
        self.entry_NY.setMinimumWidth(self.entry_NX.sizeHint().width())
        self.entry_NY.setMaximum(50)
        self.entry_NY.setSingleStep(1)
        self.entry_NY.setValue(1)
        self.entry_NY.setKeyboardTracking(False)
        #self.entry_NY.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.entry_overlap = QDoubleSpinBox()
        self.entry_overlap.setRange(0, 99)
        self.entry_overlap.setDecimals(1) 
        self.entry_overlap.setSuffix(' %')
        self.entry_overlap.setValue(10)
        self.entry_overlap.setKeyboardTracking(False)

        self.entry_deltaZ = QDoubleSpinBox()
        self.entry_deltaZ.setMinimum(0)
        self.entry_deltaZ.setMaximum(1000)
        self.entry_deltaZ.setSingleStep(0.2)
        self.entry_deltaZ.setValue(Acquisition.DZ)
        self.entry_deltaZ.setDecimals(3)
        self.entry_deltaZ.setSuffix(' μm')
        self.entry_deltaZ.setKeyboardTracking(False)
        #self.entry_deltaZ.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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
        #self.entry_dt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.entry_Nt = QSpinBox()
        self.entry_Nt.setMinimum(1)
        self.entry_Nt.setMaximum(10000)   # @@@ to be changed
        self.entry_Nt.setSingleStep(1)
        self.entry_Nt.setValue(1)
        self.entry_Nt.setKeyboardTracking(False)

        # Calculate a consistent width
        max_delta_width = max(self.entry_deltaZ.sizeHint().width(),
                              self.entry_dt.sizeHint().width(),
                              self.entry_deltaX.sizeHint().width(),
                              self.entry_deltaY.sizeHint().width(),)
        self.entry_deltaZ.setFixedWidth(max_delta_width)
        self.entry_dt.setFixedWidth(max_delta_width)
        self.entry_deltaX.setFixedWidth(max_delta_width)
        self.entry_deltaY.setFixedWidth(max_delta_width)

        max_num_width = max(self.entry_NX.sizeHint().width(),
                            self.entry_NY.sizeHint().width(),
                            self.entry_NZ.sizeHint().width(),
                            self.entry_Nt.sizeHint().width())
        self.entry_NX.setFixedWidth(max_num_width)
        self.entry_NY.setFixedWidth(max_num_width)
        self.entry_NZ.setFixedWidth(max_num_width)
        self.entry_Nt.setFixedWidth(max_num_width)

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection) # ref: https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum

        self.checkbox_withAutofocus = QCheckBox('Contrast AF')
        self.checkbox_withAutofocus.setChecked(MULTIPOINT_CONTRAST_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MULTIPOINT_CONTRAST_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_withReflectionAutofocus = QCheckBox('Reflection AF')
        self.checkbox_withReflectionAutofocus.setChecked(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_reflection_af_flag(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_genFocusMap = QCheckBox('Focus Map')
        self.checkbox_genFocusMap.setChecked(False)

        self.checkbox_usePiezo = QCheckBox('Piezo Z-Stack')
        self.checkbox_usePiezo.setChecked(MULTIPOINT_USE_PIEZO_FOR_ZSTACKS)

        self.checkbox_stitchOutput = QCheckBox('Stitch Scans')
        self.checkbox_stitchOutput.setChecked(False)

        self.checkbox_set_z_range = QCheckBox('Set Z-range')
        self.checkbox_set_z_range.toggled.connect(self.toggle_z_range_controls)

        # Add new components for Z-range
        self.entry_minZ = QDoubleSpinBox()
        self.entry_minZ.setMinimum(SOFTWARE_POS_LIMIT.Z_NEGATIVE * 1000)  # Convert to μm
        self.entry_minZ.setMaximum(SOFTWARE_POS_LIMIT.Z_POSITIVE * 1000)  # Convert to μm
        self.entry_minZ.setSingleStep(1)  # Step by 1 μm
        self.entry_minZ.setValue(self.navigationController.z_pos_mm * 1000)  # Set to current position
        self.entry_minZ.setSuffix(" μm")
        #self.entry_minZ.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.set_minZ_button = QPushButton('Set')
        self.set_minZ_button.clicked.connect(self.set_z_min)

        self.entry_maxZ = QDoubleSpinBox()
        self.entry_maxZ.setMinimum(SOFTWARE_POS_LIMIT.Z_NEGATIVE * 1000)  # Convert to μm
        self.entry_maxZ.setMaximum(SOFTWARE_POS_LIMIT.Z_POSITIVE * 1000)  # Convert to μm
        self.entry_maxZ.setSingleStep(1)  # Step by 1 μm
        self.entry_maxZ.setValue(self.navigationController.z_pos_mm * 1000)  # Set to current position
        self.entry_maxZ.setSuffix(" μm")
        #self.entry_maxZ.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.set_maxZ_button = QPushButton('Set')
        self.set_maxZ_button.clicked.connect(self.set_z_max)

        self.combobox_z_stack = QComboBox()
        self.combobox_z_stack.addItems(['From Bottom (Z-min)', 'From Center', 'From Top (Z-max)'])

        self.btn_startAcquisition = QPushButton('Start\n Acquisition ')
        self.btn_startAcquisition.setStyleSheet("background-color: #C2C2FF")
        self.btn_startAcquisition.setCheckable(True)
        self.btn_startAcquisition.setChecked(False)
        #self.btn_startAcquisition.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.progress_label = QLabel('Region -/-')
        self.progress_bar = QProgressBar()
        self.eta_label = QLabel('--:--:--')
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.eta_label.setVisible(False)
        self.eta_timer = QTimer()

        # layout
        grid_line0  = QHBoxLayout()
        grid_line0.addWidget(QLabel('Saving Path'))
        grid_line0.addWidget(self.lineEdit_savingDir)
        grid_line0.addWidget(self.btn_setSavingDir)
        grid_line0.addWidget(QLabel('ID'))
        grid_line0.addWidget(self.lineEdit_experimentID)

        grid_line1 = QGridLayout()
        temp3 = QHBoxLayout()
        temp3.addWidget(QLabel('Location List'))
        temp3.addWidget(self.dropdown_location_list)
        grid_line1.addLayout(temp3, 0, 0, 1, 6)  # Span across all columns except the last
        grid_line1.addWidget(self.btn_show_table_location_list, 0, 6, 1, 2)  # Align with other buttons

        # Make all buttons span 2 columns for consistent width
        grid_line1.addWidget(self.btn_add, 1, 0, 1, 2)
        grid_line1.addWidget(self.btn_remove,1, 2 , 1, 2)
        grid_line1.addWidget(self.btn_next,1, 4, 1, 2)
        grid_line1.addWidget(self.btn_clear, 1, 6, 1, 2)

        grid_line1.addWidget(self.btn_import_locations, 2, 0, 1, 4)
        grid_line1.addWidget(self.btn_export_locations, 2, 4, 1, 4)

        # Create spacer items
        EDGE_SPACING = 4  # Adjust this value as needed
        edge_spacer = QSpacerItem(EDGE_SPACING, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)

        # Create first row layouts
        if self.use_overlap:
            xy_half = QHBoxLayout()
            xy_half.addWidget(QLabel('Nx'))
            xy_half.addWidget(self.entry_NX)
            xy_half.addStretch(1)
            xy_half.addWidget(QLabel('Ny'))
            xy_half.addWidget(self.entry_NY)
            xy_half.addSpacerItem(edge_spacer)

            overlap_half = QHBoxLayout()
            overlap_half.addSpacerItem(edge_spacer)
            overlap_half.addWidget(QLabel('FOV Overlap'), alignment=Qt.AlignRight)
            overlap_half.addWidget(self.entry_overlap)
        else:
            # Create alternate first row layouts (dx, dy) instead of (overlap %)
            x_half = QHBoxLayout()
            x_half.addWidget(QLabel('dx'))
            x_half.addWidget(self.entry_deltaX)
            x_half.addStretch(1)
            x_half.addWidget(QLabel('Nx'))
            x_half.addWidget(self.entry_NX)
            x_half.addSpacerItem(edge_spacer)

            y_half = QHBoxLayout()
            y_half.addSpacerItem(edge_spacer)
            y_half.addWidget(QLabel('dy'))
            y_half.addWidget(self.entry_deltaY)
            y_half.addStretch(1)
            y_half.addWidget(QLabel('Ny'))
            y_half.addWidget(self.entry_NY)

        # Create second row layouts
        dz_half = QHBoxLayout()
        dz_half.addWidget(QLabel('dz'))
        dz_half.addWidget(self.entry_deltaZ)
        dz_half.addStretch(1)
        dz_half.addWidget(QLabel('Nz'))
        dz_half.addWidget(self.entry_NZ)
        dz_half.addSpacerItem(edge_spacer)

        dt_half = QHBoxLayout()
        dt_half.addSpacerItem(edge_spacer)
        dt_half.addWidget(QLabel('dt'))
        dt_half.addWidget(self.entry_dt)
        dt_half.addStretch(1)
        dt_half.addWidget(QLabel('Nt'))
        dt_half.addWidget(self.entry_Nt)

        # Add the layouts to grid_line1
        if self.use_overlap:
            grid_line1.addLayout(xy_half, 3, 0, 1, 4)
            grid_line1.addLayout(overlap_half, 3, 4, 1, 4)
        else:
            grid_line1.addLayout(x_half, 3, 0, 1, 4)
            grid_line1.addLayout(y_half, 3, 4, 1, 4)
        grid_line1.addLayout(dz_half, 4, 0, 1, 4)
        grid_line1.addLayout(dt_half, 4, 4, 1, 4)

        self.z_min_layout = QHBoxLayout()
        self.z_min_layout.addWidget(self.set_minZ_button)
        self.z_min_layout.addWidget(QLabel('Z-min'), Qt.AlignRight)
        self.z_min_layout.addWidget(self.entry_minZ)
        self.z_min_layout.addSpacerItem(edge_spacer)

        self.z_max_layout = QHBoxLayout()
        self.z_max_layout.addSpacerItem(edge_spacer)
        self.z_max_layout.addWidget(self.set_maxZ_button)
        self.z_max_layout.addWidget(QLabel('Z-max'), Qt.AlignRight)
        self.z_max_layout.addWidget(self.entry_maxZ)

        grid_line1.addLayout(self.z_min_layout, 5, 0, 1, 4) # hide this in toggle
        grid_line1.addLayout(self.z_max_layout, 5, 4, 1, 4) # hide this in toggle

        grid_af = QVBoxLayout()
        grid_af.addWidget(self.checkbox_withAutofocus)
        if SUPPORT_LASER_AUTOFOCUS:
            grid_af.addWidget(self.checkbox_withReflectionAutofocus)
        grid_af.addWidget(self.checkbox_genFocusMap)
        if ENABLE_OBJECTIVE_PIEZO:
            grid_af.addWidget(self.checkbox_usePiezo)
        grid_af.addWidget(self.checkbox_set_z_range)
        if ENABLE_STITCHER:
            grid_af.addWidget(self.checkbox_stitchOutput)

        grid_config = QHBoxLayout()
        grid_config.addWidget(self.list_configurations)
        grid_config.addSpacerItem(edge_spacer)

        grid_acquisition = QHBoxLayout()
        grid_acquisition.addSpacerItem(edge_spacer)
        grid_acquisition.addLayout(grid_af)
        grid_acquisition.addWidget(self.btn_startAcquisition)

        grid_line1.addLayout(grid_config,6,0,3,4)
        grid_line1.addLayout(grid_acquisition,6,4,3,4)

        # Columns 0-3: Combined stretch factor = 4
        grid_line1.setColumnStretch(0, 1)
        grid_line1.setColumnStretch(1, 1)
        grid_line1.setColumnStretch(2, 1)
        grid_line1.setColumnStretch(3, 1)

        # Columns 4-7: Combined stretch factor = 4
        grid_line1.setColumnStretch(4, 1)
        grid_line1.setColumnStretch(5, 1)
        grid_line1.setColumnStretch(6, 1)
        grid_line1.setColumnStretch(7, 1)

        grid_line1.setRowStretch(0, 0)  # Location list row
        grid_line1.setRowStretch(1, 0)  # Button row
        grid_line1.setRowStretch(2, 0)  # Import/Export buttons
        grid_line1.setRowStretch(3, 0)  # Nx/Ny and overlap row
        grid_line1.setRowStretch(4, 0)  # dz/Nz and dt/Nt row
        grid_line1.setRowStretch(5, 0)  # Z-range row
        grid_line1.setRowStretch(6, 1)  # Configuration/AF row - allow this to stretch
        grid_line1.setRowStretch(7, 0)  # Last row

        # Row : Progress Bar
        row_progress_layout = QHBoxLayout()
        row_progress_layout.addWidget(self.progress_label)
        row_progress_layout.addWidget(self.progress_bar)
        row_progress_layout.addWidget(self.eta_label)

        self.grid = QVBoxLayout()
        self.grid.addLayout(grid_line0)
        self.grid.addLayout(grid_line1)
        self.grid.addLayout(row_progress_layout)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        if self.use_overlap:
            self.entry_overlap.valueChanged.connect(self.update_fov_positions)
        else:
            self.entry_deltaX.valueChanged.connect(self.update_fov_positions)
            self.entry_deltaY.valueChanged.connect(self.update_fov_positions)
        self.entry_NX.valueChanged.connect(self.update_fov_positions)
        self.entry_NY.valueChanged.connect(self.update_fov_positions)
        self.btn_add.clicked.connect(self.update_fov_positions)
        self.btn_remove.clicked.connect(self.update_fov_positions)
        self.entry_deltaZ.valueChanged.connect(self.set_deltaZ)
        self.entry_dt.valueChanged.connect(self.multipointController.set_deltat)
        self.entry_NX.valueChanged.connect(self.multipointController.set_NX)
        self.entry_NY.valueChanged.connect(self.multipointController.set_NY)
        self.entry_NZ.valueChanged.connect(self.multipointController.set_NZ)
        self.entry_NZ.valueChanged.connect(self.signal_stitcher_z_levels.emit)
        self.entry_Nt.valueChanged.connect(self.multipointController.set_Nt)
        self.checkbox_genFocusMap.toggled.connect(self.multipointController.set_gen_focus_map_flag)
        self.checkbox_withAutofocus.toggled.connect(self.multipointController.set_af_flag)
        self.checkbox_withReflectionAutofocus.toggled.connect(self.multipointController.set_reflection_af_flag)
        self.checkbox_usePiezo.toggled.connect(self.multipointController.set_use_piezo)
        self.checkbox_stitchOutput.toggled.connect(self.display_stitcher_widget)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)
        self.list_configurations.itemSelectionChanged.connect(self.emit_selected_channels)
        #self.combobox_z_stack.currentIndexChanged.connect(self.signal_z_stacking.emit)

        self.multipointController.signal_acquisition_progress.connect(self.update_acquisition_progress)
        self.multipointController.signal_region_progress.connect(self.update_region_progress)
        self.signal_acquisition_started.connect(self.display_progress_bar)
        self.eta_timer.timeout.connect(self.update_eta_display)

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

        self.toggle_z_range_controls(False)
        self.multipointController.set_use_piezo(self.checkbox_usePiezo.isChecked())

    def toggle_z_range_controls(self, state):
        is_visible = bool(state)

        # Hide/show widgets in z_min_layout
        for i in range(self.z_min_layout.count()):
            widget = self.z_min_layout.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(is_visible)
            widget = self.z_max_layout.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(is_visible)

        # Enable/disable NZ entry based on the inverse of is_visible
        self.entry_NZ.setEnabled(not is_visible)

        if not is_visible:
            try:
                self.entry_minZ.valueChanged.disconnect(self.update_z_max)
                self.entry_maxZ.valueChanged.disconnect(self.update_z_min)
                self.entry_minZ.valueChanged.disconnect(self.update_Nz)
                self.entry_maxZ.valueChanged.disconnect(self.update_Nz)
                self.entry_deltaZ.valueChanged.disconnect(self.update_Nz)
            except:
                pass
            # When Z-range is not specified, set Z-min and Z-max to current Z position
            current_z = self.navigationController.z_pos_mm * 1000
            self.entry_minZ.setValue(current_z)
            self.entry_maxZ.setValue(current_z)
        else:
            self.entry_minZ.valueChanged.connect(self.update_z_max)
            self.entry_maxZ.valueChanged.connect(self.update_z_min)
            self.entry_minZ.valueChanged.connect(self.update_Nz)
            self.entry_maxZ.valueChanged.connect(self.update_Nz)
            self.entry_deltaZ.valueChanged.connect(self.update_Nz)

        # Update the layout
        self.grid.update()
        self.updateGeometry()
        self.update()

    def init_z(self, z_pos_mm=None):
        if z_pos_mm is None:
            z_pos_mm = self.navigationController.z_pos_mm

        # block entry update signals
        self.entry_minZ.blockSignals(True)
        self.entry_maxZ.blockSignals(True)

        # set entry range values bith to current z pos
        self.entry_minZ.setValue(z_pos_mm*1000)
        self.entry_maxZ.setValue(z_pos_mm*1000)
        print("init z-level flexible:", self.entry_minZ.value())

        # reallow updates from entry sinals (signal enforces min <= max when we update either entry)
        self.entry_minZ.blockSignals(False)
        self.entry_maxZ.blockSignals(False)

    def set_z_min(self):
        z_value = self.navigationController.z_pos_mm * 1000  # Convert to μm
        self.entry_minZ.setValue(z_value)
        
    def set_z_max(self):
        z_value = self.navigationController.z_pos_mm * 1000  # Convert to μm
        self.entry_maxZ.setValue(z_value)

    def update_z_min(self, z_pos_um):
        if z_pos_um < self.entry_minZ.value():
            self.entry_minZ.setValue(z_pos_um)

    def update_z_max(self, z_pos_um):
        if z_pos_um > self.entry_maxZ.value():
            self.entry_maxZ.setValue(z_pos_um)

    def update_Nz(self):
        z_min = self.entry_minZ.value()
        z_max = self.entry_maxZ.value()
        dz = self.entry_deltaZ.value()
        nz = math.ceil((z_max - z_min) / dz) + 1
        self.entry_NZ.setValue(nz)

    def update_region_progress(self, current_fov, num_fovs):
        self.progress_bar.setMaximum(num_fovs)
        self.progress_bar.setValue(current_fov)

        if self.acquisition_start_time is not None and current_fov > 0:
            elapsed_time = time.time() - self.acquisition_start_time
            Nt = self.entry_Nt.value()
            dt = self.entry_dt.value()

            # Calculate total processed FOVs and total FOVs
            processed_fovs = (self.current_region - 1) * num_fovs + current_fov + self.current_time_point * self.num_regions * num_fovs
            total_fovs = self.num_regions * num_fovs * Nt
            remaining_fovs = total_fovs - processed_fovs

            # Calculate ETA
            fov_per_second = processed_fovs / elapsed_time
            self.eta_seconds = remaining_fovs / fov_per_second + (Nt - 1 - self.current_time_point) * dt if fov_per_second > 0 else 0
            self.update_eta_display()

            # Start or restart the timer
            self.eta_timer.start(1000)  # Update every 1000 ms (1 second)

    def update_acquisition_progress(self, current_region, num_regions, current_time_point):
        self.current_region = current_region
        self.current_time_point = current_time_point

        if self.current_region == 1 and self.current_time_point == 0:  # First region
            self.acquisition_start_time = time.time()
            self.num_regions = num_regions

        progress_parts = []
        # Update timepoint progress if there are multiple timepoints and the timepoint has changed
        if self.entry_Nt.value() > 1:
            progress_parts.append(f"Time {current_time_point + 1}/{self.entry_Nt.value()}")

        # Update region progress if there are multiple regions
        if num_regions > 1:
            progress_parts.append(f"Region {current_region}/{num_regions}")

        # Set the progress label text, ensuring it's not empty
        progress_text = "  ".join(progress_parts)
        self.progress_label.setText(progress_text if progress_text else "Progress")

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

    def create_region_coordinates(self, x_center, y_center, overlap_percent=10):
        """Convert grid parameters (NX, NY) to FOV coordinates based on overlap"""
        fov_size_mm = (self.objectiveStore.get_pixel_size() / 1000) * Acquisition.CROP_WIDTH
        step_size_mm = fov_size_mm * (1 - overlap_percent/100)

        # Calculate total grid size
        grid_width_mm = (self.entry_NX.value() - 1) * step_size_mm
        grid_height_mm = (self.entry_NY.value() - 1) * step_size_mm

        scan_coordinates = []
        for i in range(self.entry_NY.value()):
            row = []
            y = y_center - grid_height_mm/2 + i * step_size_mm
            for j in range(self.entry_NX.value()):
                x = x_center - grid_width_mm/2 + j * step_size_mm
                row.append((x, y))
                self.navigationViewer.register_fov_to_image(x, y)

            if i % 2 == 1:  # reverse even rows
                row.reverse()
            scan_coordinates.extend(row)

        # Region coordinates are already centered since x_center, y_center is grid center
        region_id = f'R{len(self.location_list)-1}'
        if region_id in self.region_coordinates:
            self.region_coordinates[region_id] = [x_center, y_center]

        return scan_coordinates

    def create_region_coordinates_with_step_size(self, x_center, y_center):
        grid_width_mm = (self.entry_NX.value() - 1) * self.entry_deltaX.value()
        grid_height_mm = (self.entry_NY.value() - 1) * self.entry_deltaY.value()

        # Pre-calculate step sizes and ranges
        x_steps = [x_center - grid_width_mm/2 + j * self.entry_deltaX.value()
                   for j in range(self.entry_NX.value())]
        y_steps = [y_center - grid_height_mm/2 + i * self.entry_deltaY.value()
                   for i in range(self.entry_NY.value())]

        scan_coordinates = []
        for i, y in enumerate(y_steps):
            row = [(x, y) for x in (x_steps if i % 2 == 0 else reversed(x_steps))]
            scan_coordinates.extend(row)
            for x, y in row:
                self.navigationViewer.register_fov_to_image(x, y)

        return scan_coordinates

    def update_fov_positions(self):
        self.navigationViewer.clear_overlay()
        self.region_coordinates.clear()
        self.region_fov_coordinates_dict.clear()

        for i, (x, y, z) in enumerate(self.location_list):
            region_id = self.location_ids[i]
            self.region_coordinates[region_id] = [x, y, z]
            if self.use_overlap:
                scan_coordinates = self.create_region_coordinates(x, y, overlap_percent=self.entry_overlap.value())
            else:
                scan_coordinates = self.create_region_coordinates_with_step_size(x, y)
            self.region_fov_coordinates_dict[region_id] = scan_coordinates

    def set_deltaZ(self,value):
        mm_per_ustep = self.multipointController.navigationController.get_mm_per_ustep_Z()
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

            # add the current location to the location list if the list is empty
            if len(self.location_list) == 0:
                self.add_location()
                self.acquisition_in_place = True

            self.update_fov_positions()

            if self.checkbox_set_z_range.isChecked():
                # Set Z-range (convert from μm to mm)
                minZ = self.entry_minZ.value() / 1000
                maxZ = self.entry_maxZ.value() / 1000
                self.multipointController.set_z_range(minZ, maxZ)

            self.setEnabled_all(False)
            # Set acquisition parameters
            self.multipointController.set_deltaZ(self.entry_deltaZ.value())
            self.multipointController.set_NZ(self.entry_NZ.value())
            self.multipointController.set_deltat(self.entry_dt.value())
            self.multipointController.set_Nt(self.entry_Nt.value())
            self.multipointController.set_use_piezo(self.checkbox_usePiezo.isChecked())
            self.multipointController.set_af_flag(self.checkbox_withAutofocus.isChecked())
            self.multipointController.set_reflection_af_flag(self.checkbox_withReflectionAutofocus.isChecked())
            self.multipointController.set_base_path(self.lineEdit_savingDir.text())
            self.multipointController.set_selected_configurations((item.text() for item in self.list_configurations.selectedItems()))
            self.multipointController.start_new_experiment(self.lineEdit_experimentID.text())

            # emit signals
            self.signal_acquisition_started.emit(True)
            self.signal_acquisition_shape.emit(self.entry_NZ.value(), self.entry_deltaZ.value())

            # Start coordinate-based acquisition
            self.multipointController.run_acquisition(location_list=self.region_coordinates, coordinate_dict=self.region_fov_coordinates_dict)
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
                location_str = 'x:' + str(round(x,3)) + 'mm  y:' + str(round(y,3)) + 'mm  z:' + str(round(1000*z,1)) + 'μm'
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
                # self.navigationViewer.register_fov_to_image(x,y)
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
        self.entry_NX.setEnabled(enabled)
        self.entry_NY.setEnabled(enabled)
        self.entry_deltaZ.setEnabled(enabled)
        self.entry_NZ.setEnabled(enabled)
        self.entry_dt.setEnabled(enabled)
        self.entry_Nt.setEnabled(enabled)
        if not self.use_overlap:
            self.entry_deltaX.setEnabled(enabled)
            self.entry_deltaY.setEnabled(enabled)
        else:
            self.entry_overlap.setEnabled(enabled)
        self.list_configurations.setEnabled(enabled)
        self.checkbox_genFocusMap.setEnabled(enabled)
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
        # Get raw positions without rounding
        x = self.navigationController.x_pos_mm
        y = self.navigationController.y_pos_mm
        z = self.navigationController.z_pos_mm
        name = f'R{len(self.location_ids)}'

        # Check for duplicates using rounded values for comparison
        if not np.any(np.all(self.location_list[:, :2] == [round(x,3), round(y,3)], axis=1)):
            # Store actual values in location_list
            self.location_list = np.vstack((self.location_list, [[x, y, z]]))
            self.location_ids = np.append(self.location_ids, name)

            # Display rounded values in UI
            location_str = f"x:{round(x,3)} mm  y:{round(y,3)} mm  z:{round(z*1000,1)} μm"
            self.dropdown_location_list.addItem(location_str)

            # Update table with rounded display values
            row = self.table_location_list.rowCount()
            self.table_location_list.insertRow(row)
            self.table_location_list.setItem(row, 0, QTableWidgetItem(str(round(x,3))))
            self.table_location_list.setItem(row, 1, QTableWidgetItem(str(round(y,3))))
            self.table_location_list.setItem(row, 2, QTableWidgetItem(str(round(z*1000,1))))
            self.table_location_list.setItem(row, 3, QTableWidgetItem(name))

            # Store actual values in region coordinates
            self.region_coordinates[name] = [x, y, z]
            if self.use_overlap:
                scan_coordinates = self.create_region_coordinates(x, y, overlap_percent=self.entry_overlap.value())
            else:
                scan_coordinates = self.create_region_coordinates_with_step_size(x, y)
            self.region_fov_coordinates_dict[name] = scan_coordinates

            print(f"Added Region: {name} - x={x}, y={y}, z={z}")
        else:
            print("Duplicate location not added.")

    def remove_location(self):
        index = self.dropdown_location_list.currentIndex()
        if index >= 0:
            # Get the region ID
            region_id = self.location_ids[index]
            print("Before Removal:")
            print(f"Location IDs: {self.location_ids}")
            print(f"Region FOV Coordinates Dict Keys: {list(self.region_fov_coordinates_dict.keys())}")

            # Remove overlays using actual stored coordinates
            if region_id in self.region_fov_coordinates_dict:
                for coord in self.region_fov_coordinates_dict[region_id]:
                    self.navigationViewer.deregister_fov_to_image(coord[0], coord[1])
                del self.region_fov_coordinates_dict[region_id]

            # Remove from data structures
            self.location_list = np.delete(self.location_list, index, axis=0)
            self.location_ids = np.delete(self.location_ids, index)
            if region_id in self.region_coordinates:
                del self.region_coordinates[region_id]

            # Update remaining IDs and UI
            for i in range(index, len(self.location_ids)):
                old_id = self.location_ids[i]
                new_id = f'R{i}'
                self.location_ids[i] = new_id

                # Update dictionaries
                self.region_coordinates[new_id] = self.region_coordinates.pop(old_id)
                self.region_fov_coordinates_dict[new_id] = self.region_fov_coordinates_dict.pop(old_id)

                # Update UI with rounded display values
                self.table_location_list.setItem(i, 3, QTableWidgetItem(new_id))
                x, y, z = self.location_list[i]
                location_str = f"x:{round(x,3)} mm  y:{round(y,3)} mm  z:{round(z*1000,1)} μm"
                self.dropdown_location_list.setItemText(i, location_str)

            # Update UI
            self.dropdown_location_list.removeItem(index)
            self.table_location_list.removeRow(index)

            print("After Removal:")
            print(f"Location IDs: {self.location_ids}")
            print(f"Region FOV Coordinates Dict Keys: {list(self.region_fov_coordinates_dict.keys())}")

            # Clear overlay if no locations remain
            if len(self.location_list) == 0:
                self.navigationViewer.clear_overlay()

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

    def next(self):
        index = self.dropdown_location_list.currentIndex()
        # max_index = self.dropdown_location_list.count() - 1
        # index = min(index + 1, max_index)
        num_regions = self.dropdown_location_list.count()
        index = (index + 1) % (num_regions)
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
        self.location_ids = np.empty((0,), dtype='<U20')
        self.region_coordinates.clear()
        self.region_fov_coordinates_dict.clear()

        self.dropdown_location_list.clear()
        self.table_location_list.setRowCount(0)
        self.navigationViewer.clear_overlay()

        print("Cleared all locations and overlays.")

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

    def cell_was_changed(self, row, column):
        # Get region ID
        old_id = self.location_ids[row]

        # Clear all FOVs for this region
        if old_id in self.region_fov_coordinates_dict:
            for coord in self.region_fov_coordinates_dict[old_id]:
                self.navigationViewer.deregister_fov_to_image(coord[0], coord[1])

        # Handle the changed value
        val_edit = self.table_location_list.item(row,column).text()

        if column < 2:  # X or Y coordinate changed
            self.location_list[row,column] = float(val_edit)
            x, y, z = self.location_list[row]

            # Update region coordinates and FOVs for new position
            self.region_coordinates[old_id] = [x, y, z]
            if self.use_overlap:
                scan_coordinates = self.create_region_coordinates(x, y, overlap_percent=self.entry_overlap.value())
            else:
                scan_coordinates = self.create_region_coordinates_with_step_size(x, y)
            self.region_fov_coordinates_dict[old_id] = scan_coordinates

        elif column == 2:  # Z coordinate changed
            z = float(val_edit)/1000
            self.location_list[row,2] = z
            self.region_coordinates[old_id][2] = z
        else:  # ID changed
            new_id = val_edit
            self.location_ids[row] = new_id
            # Update dictionary keys
            if old_id in self.region_coordinates:
                self.region_coordinates[new_id] = self.region_coordinates.pop(old_id)
            if old_id in self.region_fov_coordinates_dict:
                self.region_fov_coordinates_dict[new_id] = self.region_fov_coordinates_dict.pop(old_id)

        # Update UI
        location_str = f"x:{round(self.location_list[row,0],3)} mm  y:{round(self.location_list[row,1],3)} mm  z:{round(1000*self.location_list[row,2],3)} μm"
        self.dropdown_location_list.setItemText(row, location_str)
        self.go_to(row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            self.add_location()
        else:
            super().keyPressEvent(event)

    def _update_z(self,index,z_mm):
        self.location_list[index,2] = z_mm
        location_str = 'x:' + str(round(self.location_list[index,0],3)) + 'mm  y:' + str(round(self.location_list[index,1],3)) + 'mm  z:' + str(round(1000*z_mm,1)) + 'μm'
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
                    location_str = 'x:' + str(round(x,3)) + 'mm  y:' + str(round(y,3)) + 'mm  z:' + str(round(1000*z,1)) + 'μm'
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
                    if self.use_overlap:
                        scan_coordinates = self.create_region_coordinates(x, y, overlap_percent=self.entry_overlap.value())
                    else:
                        scan_coordinates = self.create_region_coordinates_with_step_size(x, y)
                    self.region_fov_coordinates_dict[name] = scan_coordinates
                else:
                    print("Duplicate values not added based on x and y.")
            print(self.location_list)


class WellplateMultiPointWidget(QFrame):

    signal_acquisition_started = Signal(bool)
    signal_acquisition_channels = Signal(list)
    signal_stitcher_z_levels = Signal(int)
    signal_acquisition_shape = Signal(int, float)
    signal_update_navigation_viewer = Signal()
    signal_stitcher_widget = Signal(bool)
    signal_z_stacking = Signal(int)
    signal_draw_shape = Signal(bool)

    def __init__(self, navigationController, navigationViewer, multipointController, objectiveStore, configurationManager, scanCoordinates, napariMosaicWidget=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objectiveStore = objectiveStore
        self.multipointController = multipointController
        self.navigationController = navigationController
        self.navigationViewer = navigationViewer
        self.scanCoordinates = scanCoordinates
        self.configurationManager = configurationManager
        if napariMosaicWidget is None:
            self.performance_mode = True
        else:
            self.napariMosaicWidget = napariMosaicWidget
            self.performance_mode = False
        self.acquisition_pattern = ACQUISITION_PATTERN
        self.fov_pattern = FOV_PATTERN
        self.base_path_is_set = False
        self.well_selected = False
        self.num_regions = 0
        self.region_coordinates = {} # region_id, region center coordinate
        self.region_fov_coordinates_dict = {} # region_id, region fov coordinates
        self.acquisition_start_time = None
        self.manual_shape = None
        self.eta_seconds = 0
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.set_default_scan_size()

    def add_components(self):

        self.entry_well_coverage = QDoubleSpinBox()
        self.entry_well_coverage.setRange(1, 999.99)
        self.entry_well_coverage.setValue(100)
        self.entry_well_coverage.setSuffix("%")
        btn_width = self.entry_well_coverage.sizeHint().width()

        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        self.btn_setSavingDir.setFixedWidth(btn_width)

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

        self.entry_overlap = QDoubleSpinBox()
        self.entry_overlap.setRange(0, 99)
        self.entry_overlap.setValue(10)
        self.entry_overlap.setSuffix("%")
        self.entry_overlap.setFixedWidth(btn_width)

        # Add z-min and z-max entries
        self.entry_minZ = QDoubleSpinBox()
        self.entry_minZ.setMinimum(SOFTWARE_POS_LIMIT.Z_NEGATIVE * 1000)  # Convert to μm
        self.entry_minZ.setMaximum(SOFTWARE_POS_LIMIT.Z_POSITIVE * 1000)  # Convert to μm
        self.entry_minZ.setSingleStep(1)  # Step by 1 μm
        self.entry_minZ.setValue(self.navigationController.z_pos_mm * 1000)  # Set to minimum
        self.entry_minZ.setSuffix(" μm")
        #self.entry_minZ.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.set_minZ_button = QPushButton('Set')
        self.set_minZ_button.clicked.connect(self.set_z_min)

        self.entry_maxZ = QDoubleSpinBox()
        self.entry_maxZ.setMinimum(SOFTWARE_POS_LIMIT.Z_NEGATIVE * 1000)  # Convert to μm
        self.entry_maxZ.setMaximum(SOFTWARE_POS_LIMIT.Z_POSITIVE * 1000)  # Convert to μm
        self.entry_maxZ.setSingleStep(1)  # Step by 1 μm
        self.entry_maxZ.setValue(self.navigationController.z_pos_mm * 1000)  # Set to maximum
        self.entry_maxZ.setSuffix(" μm")
        #self.entry_maxZ.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.set_maxZ_button = QPushButton('Set')
        self.set_maxZ_button.clicked.connect(self.set_z_max)

        self.entry_deltaZ = QDoubleSpinBox()
        self.entry_deltaZ.setMinimum(0)
        self.entry_deltaZ.setMaximum(1000)
        self.entry_deltaZ.setSingleStep(0.2)
        self.entry_deltaZ.setValue(Acquisition.DZ)
        self.entry_deltaZ.setDecimals(3)
        #self.entry_deltaZ.setEnabled(False)
        self.entry_deltaZ.setSuffix(" μm")
        self.entry_deltaZ.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.entry_NZ = QSpinBox()
        self.entry_NZ.setMinimum(1)
        self.entry_NZ.setMaximum(2000)
        self.entry_NZ.setSingleStep(1)
        self.entry_NZ.setValue(1)
        self.entry_NZ.setEnabled(False)

        self.entry_dt = QDoubleSpinBox()
        self.entry_dt.setMinimum(0)
        self.entry_dt.setMaximum(24*3600)
        self.entry_dt.setSingleStep(1)
        self.entry_dt.setValue(0)
        self.entry_dt.setSuffix(" s")
        self.entry_dt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.entry_Nt = QSpinBox()
        self.entry_Nt.setMinimum(1)
        self.entry_Nt.setMaximum(5000)
        self.entry_Nt.setSingleStep(1)
        self.entry_Nt.setValue(1)

        self.combobox_z_stack = QComboBox()
        self.combobox_z_stack.addItems(['From Bottom (Z-min)', 'From Center', 'From Top (Z-max)'])
        self.combobox_z_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection)

        # Add a combo box for shape selection
        self.combobox_shape = QComboBox()
        if self.performance_mode:
            self.combobox_shape.addItems(['Square', 'Circle'])
        else:
            self.combobox_shape.addItems(['Square', 'Circle', 'Manual'])
            self.combobox_shape.model().item(2).setEnabled(False)
        self.combobox_shape.setFixedWidth(btn_width)
        #self.combobox_shape.currentTextChanged.connect(self.on_shape_changed)

        self.checkbox_genFocusMap = QCheckBox('Focus Map')
        #self.checkbox_genFocusMap = QCheckBox('AF Map')
        self.checkbox_genFocusMap.setChecked(False)

        self.checkbox_withAutofocus = QCheckBox('Contrast AF')
        self.checkbox_withAutofocus.setChecked(MULTIPOINT_CONTRAST_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MULTIPOINT_CONTRAST_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_withReflectionAutofocus = QCheckBox('Reflection AF')
        self.checkbox_withReflectionAutofocus.setChecked(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_reflection_af_flag(MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT)

        self.checkbox_usePiezo = QCheckBox('Piezo Z-Stack')
        self.checkbox_usePiezo.setChecked(MULTIPOINT_USE_PIEZO_FOR_ZSTACKS)

        self.checkbox_set_z_range = QCheckBox('Set Z-range')
        self.checkbox_set_z_range.toggled.connect(self.toggle_z_range_controls)

        self.checkbox_stitchOutput = QCheckBox('Stitch Scans')
        self.checkbox_stitchOutput.setChecked(False)

        self.btn_startAcquisition = QPushButton('Start\n Acquisition ')
        self.btn_startAcquisition.setStyleSheet("background-color: #C2C2FF")
        self.btn_startAcquisition.setCheckable(True)
        self.btn_startAcquisition.setChecked(False)
        #self.btn_startAcquisition.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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
        row_1_layout.addWidget(QLabel('Well Shape'))
        row_1_layout.addWidget(self.combobox_shape)
        main_layout.addLayout(row_1_layout)

        # Well Coverage, Scan Size, and Overlap
        row_4_layout = QHBoxLayout()
        row_4_layout.addWidget(QLabel('Size'))
        row_4_layout.addWidget(self.entry_scan_size)
        #row_4_layout.addStretch(1)
        row_4_layout.addWidget(QLabel('FOV Overlap'))
        row_4_layout.addWidget(self.entry_overlap)
        #row_4_layout.addStretch(1)
        row_4_layout.addWidget(QLabel('Well Coverage'))
        row_4_layout.addWidget(self.entry_well_coverage)
        main_layout.addLayout(row_4_layout)

        grid = QGridLayout()

        # dz and Nz
        dz_layout = QHBoxLayout()
        dz_layout.addWidget(QLabel('dz'))
        dz_layout.addWidget(self.entry_deltaZ)
        dz_layout.addWidget(QLabel('Nz'))
        dz_layout.addWidget(self.entry_NZ)
        grid.addLayout(dz_layout, 0, 0)

         # dt and Nt
        dt_layout = QHBoxLayout()
        dt_layout.addWidget(QLabel('dt'))
        dt_layout.addWidget(self.entry_dt)
        dt_layout.addWidget(QLabel('Nt'))
        dt_layout.addWidget(self.entry_Nt)
        grid.addLayout(dt_layout, 0, 2)

        # Z-min
        self.z_min_layout = QHBoxLayout()
        self.z_min_layout.addWidget(self.set_minZ_button)
        min_label = QLabel('Z-min')
        min_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.z_min_layout.addWidget(min_label)
        self.z_min_layout.addWidget(self.entry_minZ)
        grid.addLayout(self.z_min_layout, 1, 0)

         # Z-max
        self.z_max_layout = QHBoxLayout()
        self.z_max_layout.addWidget(self.set_maxZ_button)
        max_label = QLabel('Z-max')
        max_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.z_max_layout.addWidget(max_label)
        self.z_max_layout.addWidget(self.entry_maxZ)
        grid.addLayout(self.z_max_layout, 1, 2)

        w = max(min_label.sizeHint().width(), max_label.sizeHint().width())
        min_label.setFixedWidth(w)
        max_label.setFixedWidth(w)

        # Configuration list
        grid.addWidget(self.list_configurations, 2, 0)

        # Options and Start button
        options_layout = QVBoxLayout()
        options_layout.addWidget(self.checkbox_withAutofocus)
        if SUPPORT_LASER_AUTOFOCUS:
            options_layout.addWidget(self.checkbox_withReflectionAutofocus)
        options_layout.addWidget(self.checkbox_genFocusMap)
        if ENABLE_OBJECTIVE_PIEZO:
            options_layout.addWidget(self.checkbox_usePiezo)
        options_layout.addWidget(self.checkbox_set_z_range)
        if ENABLE_STITCHER:
            options_layout.addWidget(self.checkbox_stitchOutput)

        bottom_right = QHBoxLayout()
        bottom_right.addLayout(options_layout)
        bottom_right.addSpacing(2)
        bottom_right.addWidget(self.btn_startAcquisition)

        grid.addLayout(bottom_right, 2, 2)
        spacer_widget = QWidget()
        spacer_widget.setFixedWidth(2)
        grid.addWidget(spacer_widget, 0, 1)

        # Set column stretches
        grid.setColumnStretch(0, 1)  # Middle spacer
        grid.setColumnStretch(1, 0)  # Middle spacer
        grid.setColumnStretch(2, 1)  # Middle spacer

        main_layout.addLayout(grid)
        # Row 5: Progress Bar
        row_progress_layout = QHBoxLayout()
        row_progress_layout.addWidget(self.progress_label)
        row_progress_layout.addWidget(self.progress_bar)
        row_progress_layout.addWidget(self.eta_label)
        main_layout.addLayout(row_progress_layout)
        self.toggle_z_range_controls(self.checkbox_set_z_range.isChecked())

        # Connections
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.entry_deltaZ.valueChanged.connect(self.set_deltaZ)
        self.entry_NZ.valueChanged.connect(self.multipointController.set_NZ)
        self.entry_dt.valueChanged.connect(self.multipointController.set_deltat)
        self.entry_Nt.valueChanged.connect(self.multipointController.set_Nt)
        self.entry_scan_size.valueChanged.connect(self.update_coverage_from_scan_size)
        self.entry_well_coverage.valueChanged.connect(self.update_scan_size_from_coverage)
        self.combobox_shape.currentTextChanged.connect(self.on_set_shape)
        self.entry_scan_size.valueChanged.connect(self.update_coordinates)
        self.entry_overlap.valueChanged.connect(self.update_coordinates)
        self.checkbox_withAutofocus.toggled.connect(self.multipointController.set_af_flag)
        self.checkbox_withReflectionAutofocus.toggled.connect(self.multipointController.set_reflection_af_flag)
        self.checkbox_genFocusMap.toggled.connect(self.multipointController.set_gen_focus_map_flag)
        self.checkbox_usePiezo.toggled.connect(self.multipointController.set_use_piezo)
        self.checkbox_stitchOutput.toggled.connect(self.display_stitcher_widget)
        self.list_configurations.itemSelectionChanged.connect(self.emit_selected_channels)
        self.navigationViewer.signal_update_live_scan_grid.connect(self.set_live_scan_coordinates)
        self.navigationViewer.signal_update_well_coordinates.connect(self.set_well_coordinates)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)
        self.multipointController.signal_acquisition_progress.connect(self.update_acquisition_progress)
        self.multipointController.signal_region_progress.connect(self.update_region_progress)
        self.signal_acquisition_started.connect(self.display_progress_bar)
        self.eta_timer.timeout.connect(self.update_eta_display)
        self.combobox_z_stack.currentIndexChanged.connect(self.signal_z_stacking.emit)
        if not self.performance_mode:
            self.napariMosaicWidget.signal_layers_initialized.connect(self.enable_manual_ROI)
        self.entry_NZ.valueChanged.connect(self.signal_stitcher_z_levels.emit)

    def enable_manual_ROI(self, enable):
        self.combobox_shape.model().item(2).setEnabled(enable)
        if not enable:
            self.set_default_shape()

    def update_region_progress(self, current_fov, num_fovs):
        self.progress_bar.setMaximum(num_fovs)
        self.progress_bar.setValue(current_fov)

        if self.acquisition_start_time is not None and current_fov > 0:
            elapsed_time = time.time() - self.acquisition_start_time
            Nt = self.entry_Nt.value()
            dt = self.entry_dt.value()

            # Calculate total processed FOVs and total FOVs
            processed_fovs = (self.current_region - 1) * num_fovs + current_fov + self.current_time_point * self.num_regions * num_fovs
            total_fovs = self.num_regions * num_fovs * Nt
            remaining_fovs = total_fovs - processed_fovs

            # Calculate ETA
            fov_per_second = processed_fovs / elapsed_time
            self.eta_seconds = remaining_fovs / fov_per_second + (Nt - 1 - self.current_time_point) * dt if fov_per_second > 0 else 0
            self.update_eta_display()

            # Start or restart the timer
            self.eta_timer.start(1000)  # Update every 1000 ms (1 second)

    def update_acquisition_progress(self, current_region, num_regions, current_time_point):
        self.current_region = current_region
        self.current_time_point = current_time_point

        if self.current_region == 1 and self.current_time_point == 0:  # First region
            self.acquisition_start_time = time.time()
            self.num_regions = num_regions

        progress_parts = []
        # Update timepoint progress if there are multiple timepoints and the timepoint has changed
        if self.entry_Nt.value() > 1:
            progress_parts.append(f"Time {current_time_point + 1}/{self.entry_Nt.value()}")

        # Update region progress if there are multiple regions
        if num_regions > 1:
            progress_parts.append(f"Region {current_region}/{num_regions}")

        # Set the progress label text, ensuring it's not empty
        progress_text = "  ".join(progress_parts)
        self.progress_label.setText(progress_text if progress_text else "Progress")

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

    def toggle_z_range_controls(self, is_visible):
        # Efficiently set visibility for all widgets in both layouts
        for layout in (self.z_min_layout, self.z_max_layout):
            for i in range(layout.count()):
                widget = layout.itemAt(i).widget()
                if widget:
                    widget.setVisible(is_visible)

        # Enable/disable NZ entry based on the inverse of is_visible
        self.entry_NZ.setEnabled(not is_visible)
        current_z = self.navigationController.z_pos_mm * 1000
        self.entry_minZ.setValue(current_z)
        self.entry_maxZ.setValue(current_z)

        # Safely connect or disconnect signals
        try:
            if is_visible:
                self.entry_minZ.valueChanged.connect(self.update_z_max)
                self.entry_maxZ.valueChanged.connect(self.update_z_min)
                self.entry_minZ.valueChanged.connect(self.update_Nz)
                self.entry_maxZ.valueChanged.connect(self.update_Nz)
                self.entry_deltaZ.valueChanged.connect(self.update_Nz)
            else:
                self.entry_minZ.valueChanged.disconnect(self.update_z_max)
                self.entry_maxZ.valueChanged.disconnect(self.update_z_min)
                self.entry_minZ.valueChanged.disconnect(self.update_Nz)
                self.entry_maxZ.valueChanged.disconnect(self.update_Nz)
                self.entry_deltaZ.valueChanged.disconnect(self.update_Nz)
        except TypeError:
            # Handle case where signals might not be connected/disconnected
            pass

        # Update the layout
        self.updateGeometry()
        self.update()

    def set_default_scan_size(self):
        self.set_default_shape()
        print(self.navigationViewer.sample)
        if 'glass slide' in self.navigationViewer.sample:
            self.entry_scan_size.setEnabled(True)
            self.entry_well_coverage.setEnabled(False)
        else:
            self.entry_well_coverage.setEnabled(True)
            self.entry_well_coverage.setValue(100)
            self.update_scan_size_from_coverage()

    def set_default_shape(self):
        if self.scanCoordinates.format in ['384 well plate', '1536 well plate']:
            self.combobox_shape.setCurrentText('Square')
        elif self.scanCoordinates.format != 0:
            self.combobox_shape.setCurrentText('Circle')

    def get_effective_well_size(self):
        well_size = self.scanCoordinates.well_size_mm
        if self.combobox_shape.currentText() == 'Circle':
            fov_size_mm = (self.objectiveStore.get_pixel_size() / 1000) * Acquisition.CROP_WIDTH
            return well_size + fov_size_mm * (1 + math.sqrt(2))
        return well_size

    def on_set_shape(self):
        shape = self.combobox_shape.currentText()
        if shape == 'Manual':
            self.signal_draw_shape.emit(True)
        else:
            self.signal_draw_shape.emit(False)
            self.update_coverage_from_scan_size()
            self.update_coordinates()

    def update_manual_shape(self, shapes_data_mm):
        self.clear_regions()
        if shapes_data_mm and len(shapes_data_mm) > 0:
            self.manual_shapes = shapes_data_mm
            print(f"Manual ROIs updated with {len(self.manual_shapes)} shapes")
        else:
            self.manual_shapes = None
            print("No valid shapes found, cleared manual ROIs")
        self.update_coordinates()

    def convert_pixel_to_mm(self, pixel_coords):
        # Convert pixel coordinates to millimeter coordinates
        mm_coords = pixel_coords * self.napariMosaicWidget.viewer_pixel_size_mm
        mm_coords += np.array([self.napariMosaicWidget.top_left_coordinate[1], self.napariMosaicWidget.top_left_coordinate[0]])
        return mm_coords

    def update_coverage_from_scan_size(self):
        if 'glass slide' not in self.navigationViewer.sample and hasattr(self.navigationViewer, 'well_size_mm'):
            effective_well_size = self.get_effective_well_size()
            scan_size = self.entry_scan_size.value()
            coverage = round((scan_size / effective_well_size) * 100, 2)
            print('COVERAGE', coverage)
            self.entry_well_coverage.setValue(coverage)

    def update_scan_size_from_coverage(self):
        if hasattr(self.navigationViewer, 'well_size_mm'):
            effective_well_size = self.get_effective_well_size()
            coverage = self.entry_well_coverage.value()
            scan_size = round((coverage / 100) * effective_well_size, 3)
            print('SIZE', scan_size)
            self.entry_scan_size.setValue(scan_size)

    def update_dz(self):
        z_min = self.entry_minZ.value()
        z_max = self.entry_maxZ.value()
        nz = self.entry_NZ.value()
        dz = (z_max - z_min) / (nz - 1) if nz > 1 else 0
        self.entry_deltaZ.setValue(dz)

    def update_Nz(self):
        z_min = self.entry_minZ.value()
        z_max = self.entry_maxZ.value()
        dz = self.entry_deltaZ.value()
        nz = math.ceil((z_max - z_min) / dz) + 1
        self.entry_NZ.setValue(nz)

    def set_z_min(self):
        z_value = self.navigationController.z_pos_mm * 1000  # Convert to μm
        self.entry_minZ.setValue(z_value)

    def set_z_max(self):
        z_value = self.navigationController.z_pos_mm * 1000  # Convert to μm
        self.entry_maxZ.setValue(z_value)

    def update_z_min(self, z_pos_um):
        if z_pos_um < self.entry_minZ.value():
            self.entry_minZ.setValue(z_pos_um)

    def update_z_max(self, z_pos_um):
        if z_pos_um > self.entry_maxZ.value():
            self.entry_maxZ.setValue(z_pos_um)

    def init_z(self, z_pos_mm=None):
        # sets initial z range form the current z position used after startup of the GUI
        if z_pos_mm is None:
            z_pos_mm = self.navigationController.z_pos_mm

        # block entry update signals
        self.entry_minZ.blockSignals(True)
        self.entry_maxZ.blockSignals(True)

        # set entry range values bith to current z pos
        self.entry_minZ.setValue(z_pos_mm*1000)
        self.entry_maxZ.setValue(z_pos_mm*1000)
        print("init z-level wellplate:", self.entry_minZ.value())

        # reallow updates from entry sinals (signal enforces min <= max when we update either entry)
        self.entry_minZ.blockSignals(False)
        self.entry_maxZ.blockSignals(False)

    def set_live_scan_coordinates(self, x_mm, y_mm):
        parent = self.multipointController.parent
        is_current_widget = (parent is not None and hasattr(parent, 'recordTabWidget') and
                             parent.recordTabWidget.currentWidget() == self)

        if self.combobox_shape.currentText() != 'Manual' and self.scanCoordinates.format == 'glass slide' and (parent is None or is_current_widget):

            if self.region_coordinates:
                self.clear_regions()

            self.add_region('current', x_mm, y_mm)

    def set_well_coordinates(self, selected):
        self.well_selected = selected and bool(self.scanCoordinates.get_selected_wells())
        if hasattr(self.multipointController.parent, 'recordTabWidget') and self.multipointController.parent.recordTabWidget.currentWidget() == self:
            if self.scanCoordinates.format == 'glass slide':
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

    def update_coordinates(self):
        shape = self.combobox_shape.currentText()
        if shape == 'Manual':
            self.region_fov_coordinates_dict.clear()
            self.region_coordinates.clear()
            if self.manual_shapes is not None:
                # Handle manual ROIs
                for i, manual_shape in enumerate(self.manual_shapes):
                    scan_coordinates = self.create_manual_region_coordinates(
                        self.objectiveStore,
                        manual_shape,
                        overlap_percent=self.entry_overlap.value()
                    )
                    if scan_coordinates:
                        if len(self.manual_shapes) <= 1:
                            region_name = f'manual'
                        else:
                            region_name = f'manual_{i}'
                        self.region_fov_coordinates_dict[region_name] = scan_coordinates
                        # Set the region coordinates to the center of the manual ROI
                        center = np.mean(manual_shape, axis=0)
                        self.region_coordinates[region_name] = [center[0], center[1]]
            else:
                print("No Manual ROI found")

        elif 'glass slide' in self.navigationViewer.sample:
            x = self.navigationController.x_pos_mm
            y = self.navigationController.y_pos_mm
            self.set_live_scan_coordinates(x, y)
        else:
            if len(self.region_coordinates) > 0:
                self.clear_regions()
            self.set_well_coordinates(True)

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
        self.region_fov_coordinates_dict[well_id] = scan_coordinates

        print(f"{action} Region: {well_id} - x={x:.3f}, y={y:.3f}") #, z={z:.3f}")
        # print("Size:", self.entry_scan_size.value())
        # print("Shape:", self.combobox_shape.currentText())
        # print("# fovs in region:", len(scan_coordinates))

    def remove_region(self, well_id):
        if well_id in self.region_coordinates:
            del self.region_coordinates[well_id]

            if well_id in self.region_fov_coordinates_dict:
                region_scan_coordinates = self.region_fov_coordinates_dict.pop(well_id)
                for coord in region_scan_coordinates:
                    self.navigationViewer.deregister_fov_to_image(coord[0], coord[1])

            print(f"Removed Region: {well_id}")

    def clear_regions(self):
        self.navigationViewer.clear_overlay()
        self.region_coordinates.clear()
        self.region_fov_coordinates_dict.clear()
        print("Cleared All Regions")

    def create_region_coordinates(self, objectiveStore, center_x, center_y, scan_size_mm=None, overlap_percent=10, shape='Square'):
        if shape == 'Manual':
            return self.create_manual_region_coordinates(objectiveStore, self.manual_shapes, overlap_percent)

        if scan_size_mm is None:
            scan_size_mm = self.scanCoordinates.well_size_mm
        pixel_size_um = objectiveStore.get_pixel_size()
        fov_size_mm = (pixel_size_um / 1000) * Acquisition.CROP_WIDTH
        step_size_mm = fov_size_mm * (1 - overlap_percent / 100)

        steps = math.floor(scan_size_mm / step_size_mm)
        if shape == 'Circle':
            tile_diagonal = math.sqrt(2) * fov_size_mm
            if steps % 2 == 1:  # for odd steps
                actual_scan_size_mm = (steps - 1) * step_size_mm + tile_diagonal
            else:  # for even steps
                actual_scan_size_mm = math.sqrt(((steps - 1) * step_size_mm + fov_size_mm)**2 + (step_size_mm + fov_size_mm)**2)

            if actual_scan_size_mm > scan_size_mm:
                actual_scan_size_mm -= step_size_mm
                steps -= 1
        else:
            actual_scan_size_mm = (steps - 1) * step_size_mm + fov_size_mm

        steps = max(1, steps)  # Ensure at least one step
        # print(f"steps: {steps}, step_size_mm: {step_size_mm}")
        # print(f"scan size mm: {scan_size_mm}")
        # print(f"actual scan size mm: {actual_scan_size_mm}")

        scan_coordinates = []
        half_steps = (steps - 1) / 2
        radius_squared = (scan_size_mm / 2) ** 2
        fov_size_mm_half = fov_size_mm / 2

        for i in range(steps):
            row = []
            y = center_y + (i - half_steps) * step_size_mm
            for j in range(steps):
                x = center_x + (j - half_steps) * step_size_mm
                if shape == 'Square' or (shape == 'Circle' and self._is_in_circle(x, y, center_x, center_y, radius_squared, fov_size_mm_half)):
                    row.append((x, y))
                    self.navigationViewer.register_fov_to_image(x, y)

            if self.fov_pattern == 'S-Pattern' and i % 2 == 1:
                row.reverse()
            scan_coordinates.extend(row)

        if not scan_coordinates and shape == 'Circle':
            scan_coordinates.append((center_x, center_y))
            self.navigationViewer.register_fov_to_image(center_x, center_y)

        self.signal_update_navigation_viewer.emit()
        return scan_coordinates

    def _is_in_circle(self, x, y, center_x, center_y, radius_squared, fov_size_mm_half):
        corners = [
            (x - fov_size_mm_half, y - fov_size_mm_half),
            (x + fov_size_mm_half, y - fov_size_mm_half),
            (x - fov_size_mm_half, y + fov_size_mm_half),
            (x + fov_size_mm_half, y + fov_size_mm_half)
        ]
        return all((cx - center_x)**2 + (cy - center_y)**2 <= radius_squared for cx, cy in corners)

    def create_scan_grid(self, objectiveStore, scan_size_mm=None, overlap_percent=10, shape='Square'):
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
        # print("steps:", steps)
        # print("scan size mm:", scan_size_mm)
        # print("actual scan size mm:", actual_scan_size_mm)

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

            # If all positions were skipped, clear the list and set steps to 1
            if len(region_skip_positions) == steps * steps:
                region_skip_positions.clear()
                steps = 1

        # self.scanCoordinates.grid_skip_positions = region_skip_positions
        return steps, step_size_mm

    def create_manual_region_coordinates(self, objectiveStore, shape_coords, overlap_percent):
        if shape_coords is None or len(shape_coords) < 3:
            print("Invalid manual ROI data")
            return []

        pixel_size_um = objectiveStore.get_pixel_size()
        fov_size_mm = (pixel_size_um / 1000) * Acquisition.CROP_WIDTH
        step_size_mm = fov_size_mm * (1 - overlap_percent / 100)

        # Ensure shape_coords is a numpy array
        shape_coords = np.array(shape_coords)
        if shape_coords.ndim == 1:
            shape_coords = shape_coords.reshape(-1, 2)
        elif shape_coords.ndim > 2:
            print(f"Unexpected shape of manual_shape: {shape_coords.shape}")
            return []

        # Calculate bounding box
        x_min, y_min = np.min(shape_coords, axis=0)
        x_max, y_max = np.max(shape_coords, axis=0)

        # Create a grid of points within the bounding box
        x_range = np.arange(x_min, x_max + step_size_mm, step_size_mm)
        y_range = np.arange(y_min, y_max + step_size_mm, step_size_mm)
        xx, yy = np.meshgrid(x_range, y_range)
        grid_points = np.column_stack((xx.ravel(), yy.ravel()))

        # # Use Delaunay triangulation for efficient point-in-polygon test
        # hull = Delaunay(shape_coords)
        # mask = hull.find_simplex(grid_points) >= 0

        # Use Ray Casting for point-in-polygon test
        mask = np.array([self.point_inside_polygon(x, y, shape_coords) for x, y in grid_points])

        # Filter points inside the polygon
        valid_points = grid_points[mask]

        # Sort points
        sorted_indices = np.lexsort((valid_points[:, 0], valid_points[:, 1]))
        sorted_points = valid_points[sorted_indices]

        # Apply S-Pattern if needed
        if self.fov_pattern == 'S-Pattern':
            unique_y = np.unique(sorted_points[:, 1])
            for i in range(1, len(unique_y), 2):
                mask = sorted_points[:, 1] == unique_y[i]
                sorted_points[mask] = sorted_points[mask][::-1]

        # Register FOVs
        for x, y in sorted_points:
            self.navigationViewer.register_fov_to_image(x, y)

        self.signal_update_navigation_viewer.emit()
        return sorted_points.tolist()

    def point_inside_polygon(self, x, y, poly):
        n = len(poly)
        inside = False
        p1x, p1y = poly[0]
        for i in range(n + 1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def sort_coordinates(self):
        print(f"Acquisition pattern: {self.acquisition_pattern}")

        if len(self.region_coordinates) <= 1:
            return

        def sort_key(item):
            key, coord = item
            if 'manual' in key:
                return (0, coord[1], coord[0])  # Manual coords: sort by y, then x
            else:
                row, col = key[0], int(key[1:])
                return (1, ord(row), col)  # Well coords: sort by row, then column

        sorted_items = sorted(self.region_coordinates.items(), key=sort_key)

        if self.acquisition_pattern == 'S-Pattern':
            # Group by row and reverse alternate rows
            rows = itertools.groupby(sorted_items, key=lambda x: x[1][1] if 'manual' in x[0] else x[0][0])
            sorted_items = []
            for i, (_, group) in enumerate(rows):
                row = list(group)
                if i % 2 == 1:
                    row.reverse()
                sorted_items.extend(row)

        # Update dictionaries efficiently
        self.region_coordinates = {k: v for k, v in sorted_items}
        self.region_fov_coordinates_dict = {k: self.region_fov_coordinates_dict[k]
                                            for k, _ in sorted_items
                                            if k in self.region_fov_coordinates_dict}

    def toggle_acquisition(self, pressed):
        if not self.base_path_is_set:
            self.btn_startAcquisition.setChecked(False)
            QMessageBox.warning(self, "Warning", "Please choose base saving directory first")
            return

        # if 'glass slide' in self.navigationViewer.sample and not self.well_selected: # will use current location
        #     self.btn_startAcquisition.setChecked(False)
        #     msg = QMessageBox()
        #     msg.setText("Please select a well to scan first")
        #     msg.exec_()
        #     return

        if not self.list_configurations.selectedItems():
            self.btn_startAcquisition.setChecked(False)
            QMessageBox.warning(self, "Warning", "Please select at least one imaging channel")
            return

        if pressed:
            self.setEnabled_all(False)

            scan_size_mm = self.entry_scan_size.value()
            overlap_percent = self.entry_overlap.value()
            shape = self.combobox_shape.currentText()

            self.sort_coordinates()

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
                self.region_fov_coordinates_dict['current'] = scan_coordinates

            # Calculate total number of positions for signal emission # not needed ever 
            total_positions = sum(len(coords) for coords in self.region_fov_coordinates_dict.values())
            Nx = Ny = int(math.sqrt(total_positions))
            dx_mm = dy_mm = scan_size_mm / (Nx - 1) if Nx > 1 else scan_size_mm

            if self.checkbox_set_z_range.isChecked():
                # Set Z-range (convert from μm to mm)
                minZ = self.entry_minZ.value() / 1000  # Convert from μm to mm
                maxZ = self.entry_maxZ.value() / 1000  # Convert from μm to mm
                self.multipointController.set_z_range(minZ, maxZ)
                print("set z-range", (minZ, maxZ))
            else:
                z = self.navigationController.z_pos_mm
                self.multipointController.set_z_range(z, z)

            self.multipointController.set_deltaZ(self.entry_deltaZ.value())
            self.multipointController.set_NZ(self.entry_NZ.value())
            self.multipointController.set_deltat(self.entry_dt.value())
            self.multipointController.set_Nt(self.entry_Nt.value())
            self.multipointController.set_use_piezo(self.checkbox_usePiezo.isChecked())
            self.multipointController.set_af_flag(self.checkbox_withAutofocus.isChecked())
            self.multipointController.set_reflection_af_flag(self.checkbox_withReflectionAutofocus.isChecked())
            self.multipointController.set_selected_configurations([item.text() for item in self.list_configurations.selectedItems()])
            self.multipointController.start_new_experiment(self.lineEdit_experimentID.text())

            # Emit signals
            self.signal_acquisition_started.emit(True)
            self.signal_acquisition_shape.emit(self.entry_NZ.value(), self.entry_deltaZ.value())

            # Start acquisition
            self.multipointController.run_acquisition(location_list=self.region_coordinates, coordinate_dict=self.region_fov_coordinates_dict)
    
        else:
            self.multipointController.request_abort_aquisition()
            self.setEnabled_all(True)

    def acquisition_is_finished(self):
        self.signal_acquisition_started.emit(False)
        self.btn_startAcquisition.setChecked(False)
        self.set_well_coordinates(self.well_selected)
        if self.combobox_shape.currentText() == 'Manual':
            self.signal_draw_shape.emit(True)
        self.setEnabled_all(True)

    def setEnabled_all(self, enabled):
        for widget in self.findChildren(QWidget):
            if (widget != self.btn_startAcquisition and
                widget != self.progress_bar and
                widget != self.progress_label and
                widget != self.eta_label):
                widget.setEnabled(enabled)

            if self.scanCoordinates.format == 'glass slide':
                self.entry_well_coverage.setEnabled(False)

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


class StitcherWidget(QFrame):

    def __init__(self, configurationManager, contrastManager, *args, **kwargs):
        super(StitcherWidget, self).__init__(*args, **kwargs)
        self.configurationManager = configurationManager
        self.contrastManager = contrastManager
        self.stitcherThread = None
        self.output_path = ""
        self.initUI()

    def initUI(self):
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)  # Set frame style
        self.layout = QVBoxLayout(self)
        self.rowLayout1 = QHBoxLayout()
        self.rowLayout2 = QHBoxLayout()

                # Use registration checkbox
        self.useRegistrationCheck = QCheckBox("Registration")
        self.useRegistrationCheck.toggled.connect(self.onRegistrationCheck)
        self.rowLayout1.addWidget(self.useRegistrationCheck)
        self.rowLayout1.addStretch()

        # Apply flatfield correction checkbox
        self.applyFlatfieldCheck = QCheckBox("Flatfield Correction")
        self.rowLayout1.addWidget(self.applyFlatfieldCheck)
        self.rowLayout1.addStretch()

        # Output format dropdown
        self.outputFormatLabel = QLabel('Output Format', self)
        self.outputFormatCombo = QComboBox(self)
        self.outputFormatCombo.addItem("OME-ZARR")
        self.outputFormatCombo.addItem("OME-TIFF")
        self.rowLayout1.addWidget(self.outputFormatLabel)
        self.rowLayout1.addWidget(self.outputFormatCombo)

        # Select registration channel
        self.registrationChannelLabel = QLabel("Registration Configuration", self)
        self.registrationChannelLabel.setVisible(False)
        self.rowLayout2.addWidget(self.registrationChannelLabel)
        self.registrationChannelCombo = QComboBox(self)
        self.registrationChannelLabel.setVisible(False)
        self.registrationChannelCombo.setVisible(False)
        self.registrationChannelCombo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rowLayout2.addWidget(self.registrationChannelCombo)

         # Select registration cz-level
        self.registrationZLabel = QLabel(" Z-Level", self)
        self.registrationZLabel.setVisible(False)
        self.rowLayout2.addWidget(self.registrationZLabel)
        self.registrationZCombo = QSpinBox(self)
        self.registrationZCombo.setSingleStep(1)
        self.registrationZCombo.setMinimum(0)
        self.registrationZCombo.setMaximum(0)
        self.registrationZCombo.setValue(0)
        self.registrationZLabel.setVisible(False)
        self.registrationZCombo.setVisible(False)
        self.rowLayout2.addWidget(self.registrationZCombo)

        self.layout.addLayout(self.rowLayout1)
        self.layout.addLayout(self.rowLayout2)
        self.setLayout(self.layout)

        # Button to view output in Napari
        self.viewOutputButton = QPushButton("View Output in Napari")
        self.viewOutputButton.setEnabled(False)  # Initially disabled
        self.viewOutputButton.setVisible(False)
        self.viewOutputButton.clicked.connect(self.viewOutputNapari)
        self.layout.addWidget(self.viewOutputButton)

        # Progress bar
        progress_row = QHBoxLayout()

        # Status label
        self.statusLabel = QLabel("Status: Image Acquisition")
        progress_row.addWidget(self.statusLabel)
        self.statusLabel.setVisible(False)

        self.progressBar = QProgressBar()
        progress_row.addWidget(self.progressBar)
        self.progressBar.setVisible(False)  # Initially hidden
        self.layout.addLayout(progress_row)

    def setStitcherThread(self, thread):
        self.stitcherThread = thread

    def onRegistrationCheck(self, checked):
        self.registrationChannelLabel.setVisible(checked)
        self.registrationChannelCombo.setVisible(checked)
        self.registrationZLabel.setVisible(checked)
        self.registrationZCombo.setVisible(checked)

    def updateRegistrationChannels(self, selected_channels):
        self.registrationChannelCombo.clear()  # Clear existing items
        self.registrationChannelCombo.addItems(selected_channels)

    def updateRegistrationZLevels(self, Nz):
        self.registrationZCombo.setMinimum(0)
        self.registrationZCombo.setMaximum(Nz - 1)

    def gettingFlatfields(self):
        self.statusLabel.setText('Status: Calculating Flatfields')
        self.viewOutputButton.setVisible(False)
        self.viewOutputButton.setStyleSheet("")
        self.progressBar.setValue(0)
        self.statusLabel.setVisible(True)
        self.progressBar.setVisible(True)

    def startingStitching(self):
        self.statusLabel.setText('Status: Stitching Scans')
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
            self.statusLabel.setText('Status: Saving Stitched Acquisition')
        else:
            self.statusLabel.setText('Status: Saving Stitched Region')
        self.statusLabel.setVisible(True)
        self.progressBar.setRange(0, 0)  # indeterminate mode.
        self.progressBar.setVisible(True)

    def finishedSaving(self, output_path, dtype):
        if self.stitcherThread is not None:
            self.stitcherThread.quit()
            self.stitcherThread.deleteLater()
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

    def updateContrastLimits(self, channel, min_val, max_val):
        self.contrastManager.update_limits(channel, min_val, max_val)

    def viewOutputNapari(self):
        try:
            napari_viewer = napari.Viewer()
            if ".ome.zarr" in self.output_path:
                napari_viewer.open(self.output_path, plugin='napari-ome-zarr')
            else:
                napari_viewer.open(self.output_path)

            for layer in napari_viewer.layers:
                layer_name = layer.name.replace("_", " ").replace("full ", "full_")
                channel_info = CHANNEL_COLORS_MAP.get(self.extractWavelength(layer_name), {'hex': 0xFFFFFF, 'name': 'gray'})

                if channel_info['name'] in AVAILABLE_COLORMAPS:
                    layer.colormap = AVAILABLE_COLORMAPS[channel_info['name']]
                else:
                    layer.colormap = self.generateColormap(channel_info)

                min_val, max_val = self.contrastManager.get_limits(layer_name)
                layer.contrast_limits = (min_val, max_val)

        except Exception as e:
            QMessageBox.critical(self, "Error Opening in Napari", str(e))
            print(f"An error occurred while opening output in Napari: {e}")

    def resetUI(self):
        self.output_path = ""

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

    def closeEvent(self, event):
        if self.stitcherThread is not None:
            self.stitcherThread.quit()
            self.stitcherThread.wait()
            self.stitcherThread.deleteLater()
            self.stitcherThread = None
        super().closeEvent(event)


class NapariLiveWidget(QWidget):
    signal_coordinates_clicked = Signal(int, int, int, int)
    signal_newExposureTime = Signal(float)
    signal_newAnalogGain = Signal(float)
    signal_autoLevelSetting = Signal(bool)

    def __init__(self, streamHandler, liveController, navigationController, configurationManager, contrastManager, wellSelectionWidget=None, show_trigger_options=True, show_display_options=True, show_autolevel=False, autolevel=False, parent=None):
        super().__init__(parent)
        self.streamHandler = streamHandler
        self.liveController = liveController
        self.navigationController = navigationController
        self.configurationManager = configurationManager
        self.wellSelectionWidget = wellSelectionWidget
        self.live_configuration = self.liveController.currentConfiguration
        self.image_width = 0
        self.image_height = 0
        self.dtype = np.uint8
        self.channels = set()
        self.init_live = False
        self.init_live_rgb = False
        self.init_scale = False
        self.previous_scale = None
        self.previous_center = None
        self.last_was_autofocus = False
        self.fps_trigger = 10
        self.fps_display = 10
        self.contrastManager = contrastManager

        self.initNapariViewer()
        self.addNapariGrayclipColormap()
        self.initControlWidgets(show_trigger_options, show_display_options, show_autolevel, autolevel)
        self.update_microscope_mode_by_name(self.live_configuration.name)

    def initNapariViewer(self):
        self.viewer = napari.Viewer(show=False)
        self.viewerWidget = self.viewer.window._qt_window
        self.viewer.dims.axis_labels = ['Y-axis', 'X-axis']
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewerWidget)
        self.setLayout(self.layout)
        self.customizeViewer()

    def customizeViewer(self):
        # Hide the status bar (which includes the activity button)
        if hasattr(self.viewer.window, '_status_bar'):
            self.viewer.window._status_bar.hide()

        # Hide the layer buttons
        if hasattr(self.viewer.window._qt_viewer, 'layerButtons'):
            self.viewer.window._qt_viewer.layerButtons.hide()

    def updateHistogram(self, layer):
        if self.histogram_widget is not None and layer.data is not None:
            self.pg_image_item.setImage(layer.data, autoLevels=False)
            self.histogram_widget.setLevels(*layer.contrast_limits)
            self.histogram_widget.setHistogramRange(layer.data.min(), layer.data.max())

            # Set the histogram widget's region to match the layer's contrast limits
            self.histogram_widget.region.setRegion(layer.contrast_limits)

            # Update colormap only if it has changed
            if hasattr(self, 'last_colormap') and self.last_colormap != layer.colormap.name:
                self.histogram_widget.gradient.setColorMap(self.createColorMap(layer.colormap))
            self.last_colormap = layer.colormap.name

    def createColorMap(self, colormap):
        colors = colormap.colors
        positions = np.linspace(0, 1, len(colors))
        return pg.ColorMap(positions, colors)

    def initControlWidgets(self, show_trigger_options, show_display_options, show_autolevel, autolevel):
        # Initialize histogram widget
        self.pg_image_item = pg.ImageItem()
        self.histogram_widget = pg.HistogramLUTWidget(image=self.pg_image_item)
        self.histogram_widget.setFixedWidth(100)
        self.histogram_dock = self.viewer.window.add_dock_widget(
            self.histogram_widget, area='right', name="hist"
        )
        self.histogram_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.histogram_dock.setTitleBarWidget(QWidget())
        self.histogram_widget.region.sigRegionChanged.connect(self.on_histogram_region_changed)
        self.histogram_widget.region.sigRegionChangeFinished.connect(self.on_histogram_region_changed)

        # Microscope Configuration
        self.dropdown_modeSelection = QComboBox()
        for config in self.configurationManager.configurations:
            self.dropdown_modeSelection.addItem(config.name)
        self.dropdown_modeSelection.setCurrentText(self.live_configuration.name)
        self.dropdown_modeSelection.currentTextChanged.connect(self.update_microscope_mode_by_name)

        # Live button
        self.btn_live = QPushButton("Start Live")
        self.btn_live.setCheckable(True)
        gradient_style = """
            QPushButton {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                                                  stop:0 #D6D6FF, stop:1 #C2C2FF);
                border-radius: 5px;
                color: black;
                border: 1px solid #A0A0A0;
            }
            QPushButton:checked {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                                                  stop:0 #FFD6D6, stop:1 #FFC2C2);
                border: 1px solid #A0A0A0;
            }
            QPushButton:hover {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                                                  stop:0 #E0E0FF, stop:1 #D0D0FF);
            }
            QPushButton:pressed {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                                                  stop:0 #9090C0, stop:1 #8080B0);
            }
        """
        self.btn_live.setStyleSheet(gradient_style)
        #self.btn_live.setStyleSheet("font-weight: bold; background-color: #7676F7") #6666D3
        current_height = self.btn_live.sizeHint().height()
        self.btn_live.setFixedHeight(int(current_height * 1.5))
        self.btn_live.clicked.connect(self.toggle_live)

        # Exposure Time
        self.entry_exposureTime = QDoubleSpinBox()
        self.entry_exposureTime.setRange(self.liveController.camera.EXPOSURE_TIME_MS_MIN, self.liveController.camera.EXPOSURE_TIME_MS_MAX)
        self.entry_exposureTime.setValue(self.live_configuration.exposure_time)
        self.entry_exposureTime.setSuffix(" ms")
        self.entry_exposureTime.valueChanged.connect(self.update_config_exposure_time)

        # Analog Gain
        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain.setRange(0, 24)
        self.entry_analogGain.setSingleStep(0.1)
        self.entry_analogGain.setValue(self.live_configuration.analog_gain)
        # self.entry_analogGain.setSuffix('x')
        self.entry_analogGain.valueChanged.connect(self.update_config_analog_gain)

        # Illumination Intensity
        self.slider_illuminationIntensity = QSlider(Qt.Horizontal)
        self.slider_illuminationIntensity.setRange(0, 100)
        self.slider_illuminationIntensity.setValue(int(self.live_configuration.illumination_intensity))
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
        control_layout.addWidget(self.dropdown_modeSelection)
        control_layout.addWidget(self.btn_live)
        control_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        row1 = make_row(QLabel('Exposure Time'), self.entry_exposureTime)
        control_layout.addLayout(row1)

        row2 = make_row(QLabel('Illumination'), self.slider_illuminationIntensity, self.label_illuminationIntensity)
        control_layout.addLayout(row2)

        row3 = make_row((QLabel('Analog Gain')), self.entry_analogGain)
        control_layout.addLayout(row3)
        control_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        if show_trigger_options:
            row0 = make_row(QLabel('Trigger Mode'), self.dropdown_triggerMode)
            control_layout.addLayout(row0)
            row00 = make_row(QLabel('Trigger FPS'), self.entry_triggerFPS)
            control_layout.addLayout(row00)
            control_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        if show_display_options:
            row4 = make_row((QLabel('Display FPS')), self.entry_displayFPS)
            control_layout.addLayout(row4)
            row5 = make_row(QLabel('Display Resolution'), self.slider_resolutionScaling, self.label_resolutionScaling)
            control_layout.addLayout(row5)
            control_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        if show_autolevel:
            control_layout.addWidget(self.btn_autolevel)
            control_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        control_layout.addStretch(1)

        add_live_controls = False
        if USE_NAPARI_FOR_LIVE_CONTROL or add_live_controls:
            live_controls_widget = QWidget()
            live_controls_widget.setLayout(control_layout)
            # layer_list_widget.setFixedWidth(270)

            layer_controls_widget = self.viewer.window._qt_viewer.dockLayerControls.widget()
            layer_list_widget = self.viewer.window._qt_viewer.dockLayerList.widget()

            self.viewer.window._qt_viewer.layerButtons.hide()
            self.viewer.window.remove_dock_widget(self.viewer.window._qt_viewer.dockLayerControls)
            self.viewer.window.remove_dock_widget(self.viewer.window._qt_viewer.dockLayerList)

            # Add the actual dock widgets
            self.dock_layer_controls = self.viewer.window.add_dock_widget(layer_controls_widget, area='left', name='layer controls', tabify=True)
            self.dock_layer_list = self.viewer.window.add_dock_widget(layer_list_widget, area='left', name='layer list', tabify=True)
            self.dock_live_controls = self.viewer.window.add_dock_widget(live_controls_widget, area='left', name='live controls', tabify=True)

            self.viewer.window.window_menu.addAction(self.dock_live_controls.toggleViewAction())

        if USE_NAPARI_WELL_SELECTION:
            well_selector_layout = QVBoxLayout()
            #title_label = QLabel("Well Selector")
            #title_label.setAlignment(Qt.AlignCenter)  # Center the title
            #title_label.setStyleSheet("font-weight: bold;")  # Optional: style the title
            #well_selector_layout.addWidget(title_label)

            well_selector_row = QHBoxLayout()
            well_selector_row.addStretch(1)
            well_selector_row.addWidget(self.wellSelectionWidget)
            well_selector_row.addStretch(1)
            well_selector_layout.addLayout(well_selector_row)
            well_selector_layout.addStretch()

            well_selector_dock_widget = QWidget()
            well_selector_dock_widget.setLayout(well_selector_layout)
            self.dock_well_selector = self.viewer.window.add_dock_widget(well_selector_dock_widget, area='bottom', name='well selector')
            self.dock_well_selector.setFixedHeight(self.dock_well_selector.minimumSizeHint().height())

        layer_controls_widget = self.viewer.window._qt_viewer.dockLayerControls.widget()
        layer_list_widget = self.viewer.window._qt_viewer.dockLayerList.widget()

        self.viewer.window._qt_viewer.layerButtons.hide()
        self.viewer.window.remove_dock_widget(self.viewer.window._qt_viewer.dockLayerControls)
        self.viewer.window.remove_dock_widget(self.viewer.window._qt_viewer.dockLayerList)
        self.print_window_menu_items()

    def print_window_menu_items(self):
        print("Items in window_menu:")
        for action in self.viewer.window.window_menu.actions():
            print(action.text())

    def on_histogram_region_changed(self):
        if self.live_configuration.name:
            min_val, max_val = self.histogram_widget.region.getRegion()
            self.updateContrastLimits(self.live_configuration.name, min_val, max_val)

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
        self.live_configuration = next((config for config in self.configurationManager.configurations if config.name == current_microscope_mode_name), None)
        if self.live_configuration:
            self.liveController.set_microscope_mode(self.live_configuration)
            self.entry_exposureTime.setValue(self.live_configuration.exposure_time)
            self.entry_analogGain.setValue(self.live_configuration.analog_gain)
            self.slider_illuminationIntensity.setValue(int(self.live_configuration.illumination_intensity))

    def update_config_exposure_time(self, new_value):
        self.live_configuration.exposure_time = new_value
        self.configurationManager.update_configuration(self.live_configuration.id, 'ExposureTime', new_value)
        self.signal_newExposureTime.emit(new_value)

    def update_config_analog_gain(self, new_value):
        self.live_configuration.analog_gain = new_value
        self.configurationManager.update_configuration(self.live_configuration.id, 'AnalogGain', new_value)
        self.signal_newAnalogGain.emit(new_value)

    def update_config_illumination_intensity(self, new_value):
        self.live_configuration.illumination_intensity = new_value
        self.configurationManager.update_configuration(self.live_configuration.id, 'IlluminationIntensity', new_value)
        self.liveController.set_illumination(self.live_configuration.illumination_source, new_value)

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
        if self.dtype != np.dtype(image_dtype):

            self.contrastManager.scale_contrast_limits(np.dtype(image_dtype)) # Fix This to scale existing contrast limits to new dtype range
            self.dtype = image_dtype

        self.channels.add(channel)
        self.live_configuration.name = channel

        if rgb:
            canvas = np.zeros((image_height, image_width, 3), dtype=self.dtype)
        else:
            canvas = np.zeros((image_height, image_width), dtype=self.dtype)
        limits = self.getContrastLimits(self.dtype)
        layer = self.viewer.add_image(canvas, name="Live View", visible=True, rgb=rgb, colormap='grayclip',
                                      contrast_limits=limits, blending='additive')
        layer.contrast_limits = self.contrastManager.get_limits(self.live_configuration.name, self.dtype)
        layer.mouse_double_click_callbacks.append(self.onDoubleClick)
        layer.events.contrast_limits.connect(self.signalContrastLimits)
        self.updateHistogram(layer)

        if not self.init_scale:
            self.resetView()
            self.previous_scale = self.viewer.camera.zoom
            self.previous_center = self.viewer.camera.center
        else:
            self.viewer.camera.zoom = self.previous_scale
            self.viewer.camera.center = self.previous_center

    def updateLiveLayer(self, image, from_autofocus=False):
        """Updates the canvas with the new image data."""
        if self.dtype != np.dtype(image.dtype):
            self.contrastManager.scale_contrast_limits(np.dtype(image.dtype))
            self.dtype = np.dtype(image.dtype)
            self.init_live = False
            self.init_live_rgb = False

        if not self.live_configuration.name:
            self.live_configuration.name = self.liveController.currentConfiguration.name
        rgb = len(image.shape) >= 3

        if not rgb and not self.init_live or 'Live View' not in self.viewer.layers:
            self.initLiveLayer(self.live_configuration.name, image.shape[0], image.shape[1], image.dtype, rgb)
            self.init_live = True
            self.init_live_rgb = False
            print("init live")
        elif rgb and not self.init_live_rgb:
            self.initLiveLayer(self.live_configuration.name, image.shape[0], image.shape[1], image.dtype, rgb)
            self.init_live_rgb = True
            self.init_live = False
            print("init live rgb")

        layer = self.viewer.layers["Live View"]
        layer.data = image
        layer.contrast_limits = self.contrastManager.get_limits(self.live_configuration.name)
        self.updateHistogram(layer)

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
        layer.refresh()

    def onDoubleClick(self, layer, event):
        """Handle double-click events and emit centered coordinates if within the data range."""
        if self.navigationController.get_flag_click_to_move():
            coords = layer.world_to_data(event.position)
            layer_shape = layer.data.shape[0:2] if len(layer.data.shape) >= 3 else layer.data.shape

            if coords is not None and (0 <= int(coords[-1]) < layer_shape[-1] and (0 <= int(coords[-2]) < layer_shape[-2])):
                x_centered = int(coords[-1] - layer_shape[-1] / 2)
                y_centered = int(coords[-2] - layer_shape[-2] / 2)
                # Emit the centered coordinates and dimensions of the layer's data array
                self.signal_coordinates_clicked.emit(x_centered, y_centered, layer_shape[-1], layer_shape[-2])
        else:
            self.resetView()

    def set_live_configuration(self, live_configuration):
        self.live_configuration = live_configuration

    def updateContrastLimits(self, channel, min_val, max_val):
        self.contrastManager.update_limits(channel, min_val, max_val)
        if "Live View" in self.viewer.layers:
            self.viewer.layers["Live View"].contrast_limits = (min_val, max_val)

    def signalContrastLimits(self, event):
        layer = event.source
        min_val, max_val = map(float, layer.contrast_limits)
        self.contrastManager.update_limits(self.live_configuration.name, min_val, max_val)

    def getContrastLimits(self, dtype):
        return self.contrastManager.get_default_limits()

    def resetView(self):
        self.viewer.reset_view()

    def activate(self):
        print("ACTIVATING NAPARI LIVE WIDGET")
        self.viewer.window.activate()


class NapariMultiChannelWidget(QWidget):

    def __init__(self, objectiveStore, contrastManager, grid_enabled=False, parent=None):
        super().__init__(parent)
        # Initialize placeholders for the acquisition parameters
        self.objectiveStore = objectiveStore
        self.contrastManager = contrastManager
        self.image_width = 0
        self.image_height = 0
        self.dtype = np.uint8
        self.channels = set()
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
        self.customizeViewer()

    def customizeViewer(self):
        # Hide the status bar (which includes the activity button)
        if hasattr(self.viewer.window, '_status_bar'):
            self.viewer.window._status_bar.hide()

        # Hide the layer buttons
        if hasattr(self.viewer.window._qt_viewer, 'layerButtons'):
            self.viewer.window._qt_viewer.layerButtons.hide()

    def initLayersShape(self, Nz, dz):
        pixel_size_um = self.objectiveStore.get_pixel_size()
        if self.Nz != Nz or self.dz_um != dz or self.pixel_size_um != pixel_size_um:
            self.acquisition_initialized = False
            self.Nz = Nz
            self.dz_um = dz if Nz > 1 and dz != 0 else 1.0
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
        if self.acquisition_initialized:
            for layer in list(self.viewer.layers):
                if layer.name not in self.channels:
                    self.viewer.layers.remove(layer)
        else:
            self.viewer.layers.clear()
            self.acquisition_initialized = True
            if self.dtype != np.dtype(image_dtype) and not USE_NAPARI_FOR_LIVE_VIEW:
                self.contrastManager.scale_contrast_limits(image_dtype)

        self.image_width = image_width
        self.image_height = image_height
        self.dtype = np.dtype(image_dtype)
        self.layers_initialized = True
        self.update_layer_count = 0

    def updateLayers(self, image, i, j, k, channel_name):
        """Updates the appropriate slice of the canvas with the new image data."""
        rgb = len(image.shape) == 3

        # Check if the layer exists and has a different dtype
        if self.dtype != np.dtype(image.dtype): # or self.viewer.layers[channel_name].data.dtype != image.dtype:
            # Remove the existing layer
            self.layers_initialized = False
            self.acquisition_initialized = False

        if not self.layers_initialized:
            self.initLayers(image.shape[0], image.shape[1], image.dtype)

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

            # print(f"multi channel - dz_um:{self.dz_um}, pixel_y_um:{self.pixel_size_um}, pixel_x_um:{self.pixel_size_um}")
            layer.contrast_limits = self.contrastManager.get_limits(channel_name)
            layer.events.contrast_limits.connect(self.signalContrastLimits)

            if not self.viewer_scale_initialized:
                self.resetView()
                self.viewer_scale_initialized = True
            else:
                layer.refresh()

        layer = self.viewer.layers[channel_name]
        layer.data[k] = image
        layer.contrast_limits = self.contrastManager.get_limits(channel_name)
        self.update_layer_count += 1
        if self.update_layer_count % len(self.channels) == 0:
            if self.Nz > 1:
                self.viewer.dims.set_point(0, k * self.dz_um)
            for layer in self.viewer.layers:
                layer.refresh()

    def updateRTPLayers(self, image, channel_name):
        """Updates the appropriate slice of the canvas with the new image data."""
        # Check if the layer exists and has a different dtype
        if self.dtype != image.dtype: # or self.viewer.layers[channel_name].data.dtype != image.dtype:
            # Remove the existing layer
            self.layers_initialized = False
            self.acquisition_initialized = False

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

            layer = self.viewer.add_image(canvas, name=channel_name, visible=True, rgb=rgb, colormap=color,
                                        blending='additive', contrast_limits=self.getContrastLimits(self.dtype))
            layer.events.contrast_limits.connect(self.signalContrastLimits)
            self.resetView()

        layer = self.viewer.layers[channel_name]
        layer.data = image
        layer.contrast_limits = self.contrastManager.get_limits(channel_name)
        layer.refresh()

    def signalContrastLimits(self, event):
        layer = event.source
        min_val, max_val = map(float, layer.contrast_limits)
        self.contrastManager.update_limits(layer.name, min_val, max_val)

    def getContrastLimits(self, dtype):
        return self.contrastManager.get_default_limits()

    def resetView(self):
        self.viewer.reset_view()
        for layer in self.viewer.layers:
            layer.refresh()

    def activate(self):
        print("ACTIVATING NAPARI MULTICHANNEL WIDGET")
        self.viewer.window.activate()


class NapariTiledDisplayWidget(QWidget):

    signal_coordinates_clicked = Signal(int, int, int, int, int, int, float, float)

    def __init__(self, objectiveStore, contrastManager, parent=None):
        super().__init__(parent)
        # Initialize placeholders for the acquisition parameters
        self.objectiveStore = objectiveStore
        self.contrastManager = contrastManager
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
        self.initNapariViewer()

    def initNapariViewer(self):
        self.viewer = napari.Viewer(show=False) #, ndisplay=3)
        self.viewerWidget = self.viewer.window._qt_window
        self.viewer.dims.axis_labels = ['Z-axis', 'Y-axis', 'X-axis']
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewerWidget)
        self.setLayout(self.layout)
        self.customizeViewer()

    def customizeViewer(self):
        # Hide the status bar (which includes the activity button)
        if hasattr(self.viewer.window, '_status_bar'):
            self.viewer.window._status_bar.hide()

        # Hide the layer buttons
        if hasattr(self.viewer.window._qt_viewer, 'layerButtons'):
            self.viewer.window._qt_viewer.layerButtons.hide()

    def initLayersShape(self, Nx, Ny, Nz, dx, dy, dz):
        self.acquisition_initialized = False
        self.Nx = Nx
        self.Ny = Ny
        self.Nz = Nz
        self.dx_mm = dx
        self.dy_mm = dy
        self.dz_um = dz if Nz > 1 and dz != 0 else 1.0
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
        self.layers_initialized = True
        self.resetView()
        self.viewer_scale_initialized = False

    def updateLayers(self, image, i, j, k, channel_name):
        """Updates the appropriate slice of the canvas with the new image data."""
        if i == -1 or j == -1:
            print("no tiled preview for coordinate acquisition")
            return

        # Check if the layer exists and has a different dtype
        if self.dtype != image.dtype:
            # Remove the existing layer
            self.layers_initialized = False
            self.acquisition_initialized = False

        if not self.layers_initialized:
            self.initLayers(image.shape[0], image.shape[1], image.dtype)

        rgb = len(image.shape) == 3  # Check if image is RGB based on shape
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
            # print(f"tiled display - dz_um:{self.dz_um}, pixel_y_um:{self.pixel_size_um}, pixel_x_um:{self.pixel_size_um}")
            layer.contrast_limits = self.contrastManager.get_limits(channel_name)
            layer.events.contrast_limits.connect(self.signalContrastLimits)
            layer.mouse_double_click_callbacks.append(self.onDoubleClick)

        image = cv2.resize(image, (self.image_width, self.image_height), interpolation=cv2.INTER_AREA)

        if not self.viewer_scale_initialized:
            self.resetView()
            self.viewer_scale_initialized = True
        self.viewer.dims.set_point(0, k * self.dz_um)
        layer = self.viewer.layers[channel_name]
        layer.contrast_limits = self.contrastManager.get_limits(channel_name)
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
        self.contrastManager.update_limits(layer.name, min_val, max_val)

    def getContrastLimits(self, dtype):
        return self.contrastManager.get_default_limits()

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
    signal_update_viewer = Signal()
    signal_layers_initialized = Signal(bool)
    signal_shape_drawn = Signal(list)

    def __init__(self, objectiveStore, contrastManager, parent=None):
        super().__init__(parent)
        self.objectiveStore = objectiveStore
        self.contrastManager = contrastManager
        self.downsample_factor = PRVIEW_DOWNSAMPLE_FACTOR
        self.viewer = napari.Viewer(show=False)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewer.window._qt_window)
        self.layers_initialized = False
        self.shape_layer = None
        self.shapes_mm = []
        self.is_drawing_shape = False

        # add clear button
        self.clear_button = QPushButton("Clear Mosaic View")
        self.clear_button.clicked.connect(self.clearAllLayers)
        self.layout.addWidget(self.clear_button)

        self.setLayout(self.layout)
        self.customizeViewer()
        self.viewer_pixel_size_mm = 1
        self.dz_um = None
        self.Nz = None
        self.channels = set()
        self.viewer_extents = []  # [min_y, max_y, min_x, max_x]
        self.top_left_coordinate = None  # [y, x] in mm
        self.mosaic_dtype = None

    def customizeViewer(self):
        # hide status bar
        if hasattr(self.viewer.window, '_status_bar'):
            self.viewer.window._status_bar.hide()

        self.viewer.bind_key('D', self.toggle_draw_mode)

    def toggle_draw_mode(self, viewer):
        self.is_drawing_shape = not self.is_drawing_shape

        if 'Manual ROI' not in self.viewer.layers:
            self.shape_layer = self.viewer.add_shapes(name='Manual ROI', edge_width=40, edge_color='red', face_color='transparent')
            self.shape_layer.events.data.connect(self.on_shape_change)
        else:
            self.shape_layer = self.viewer.layers['Manual ROI']

        if self.is_drawing_shape:
            self.shape_layer.mode = 'add_polygon'
        else:
            self.shape_layer.mode = 'pan_zoom'

        self.on_shape_change()

    def enable_shape_drawing(self, enable):
        if enable:
            self.toggle_draw_mode(self.viewer)
        else:
            self.is_drawing_shape = False
            if self.shape_layer is not None:
                self.shape_layer.mode = 'pan_zoom'

    def on_shape_change(self, event=None):
        if self.shape_layer is not None and len(self.shape_layer.data) > 0:
            # convert shapes to mm coordinates
            self.shapes_mm = [self.convert_shape_to_mm(shape) for shape in self.shape_layer.data]
        else:
            self.shapes_mm = []
        self.signal_shape_drawn.emit(self.shapes_mm)

    def convert_shape_to_mm(self, shape_data):
        shape_data_mm = []
        for point in shape_data:
            coords = self.viewer.layers[0].world_to_data(point)
            x_mm = self.top_left_coordinate[1] + coords[1] * self.viewer_pixel_size_mm
            y_mm = self.top_left_coordinate[0] + coords[0] * self.viewer_pixel_size_mm
            shape_data_mm.append([x_mm, y_mm])
        return np.array(shape_data_mm)

    def convert_mm_to_viewer_shapes(self, shapes_mm):
        viewer_shapes = []
        for shape_mm in shapes_mm:
            viewer_shape = []
            for point_mm in shape_mm:
                x_data = (point_mm[0] - self.top_left_coordinate[1]) / self.viewer_pixel_size_mm
                y_data = (point_mm[1] - self.top_left_coordinate[0]) / self.viewer_pixel_size_mm
                world_coords = self.viewer.layers[0].data_to_world([y_data, x_data])
                viewer_shape.append(world_coords)
            viewer_shapes.append(viewer_shape)
        return viewer_shapes

    def update_shape_layer_position(self, prev_top_left, new_top_left):
        if self.shape_layer is None or len(self.shapes_mm) == 0:
            return
        try:
            # update top_left_coordinate
            self.top_left_coordinate = new_top_left

            # convert mm coordinates to viewer coordinates
            new_shapes = self.convert_mm_to_viewer_shapes(self.shapes_mm)

            # update shape layer data
            self.shape_layer.data = new_shapes
        except Exception as e:
            print(f"Error updating shape layer position: {e}")
            import traceback
            traceback.print_exc()

    def initChannels(self, channels):
        self.channels = set(channels)

    def initLayersShape(self, Nz, dz):
        self.Nz = 1
        self.dz_um = dz

    def extractWavelength(self, name):
        # extract wavelength from channel name
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]
        for color in ['R', 'G', 'B']:
            if color in parts or f"full_{color}" in parts:
                return color
        return None

    def generateColormap(self, channel_info):
        # generate colormap from hex value
        c0 = (0, 0, 0)
        c1 = (((channel_info['hex'] >> 16) & 0xFF) / 255,
             ((channel_info['hex'] >> 8) & 0xFF) / 255,
             (channel_info['hex'] & 0xFF) / 255)
        return Colormap(colors=[c0, c1], controls=[0, 1], name=channel_info['name'])

    def updateMosaic(self, image, x_mm, y_mm, k, channel_name):
        # calculate pixel size
        image_pixel_size_um = self.objectiveStore.get_pixel_size() * self.downsample_factor
        image_pixel_size_mm = image_pixel_size_um / 1000
        image_dtype = image.dtype

        # downsample image
        if self.downsample_factor != 1:
            image = cv2.resize(image, (image.shape[1] // self.downsample_factor, image.shape[0] // self.downsample_factor), interpolation=cv2.INTER_AREA)

        # adjust image position
        x_mm -= (image.shape[1] * image_pixel_size_mm) / 2
        y_mm -= (image.shape[0] * image_pixel_size_mm) / 2

        if not self.viewer.layers:
            # initialize first layer
            self.layers_initialized = True
            self.signal_layers_initialized.emit(self.layers_initialized)
            self.viewer_pixel_size_mm = image_pixel_size_mm
            self.viewer_extents = [y_mm, y_mm + image.shape[0] * image_pixel_size_mm,
                                   x_mm, x_mm + image.shape[1] * image_pixel_size_mm]
            self.top_left_coordinate = [y_mm, x_mm]
            self.mosaic_dtype = image_dtype
        else:
            # convert image dtype and scale if necessary
            image = self.convertImageDtype(image, self.mosaic_dtype)
            if image_pixel_size_mm != self.viewer_pixel_size_mm:
                scale_factor = image_pixel_size_mm / self.viewer_pixel_size_mm
                image = cv2.resize(image, (int(image.shape[1] * scale_factor), int(image.shape[0] * scale_factor)), interpolation=cv2.INTER_LINEAR)

        if channel_name not in self.viewer.layers:
            # create new layer for channel
            channel_info = CHANNEL_COLORS_MAP.get(self.extractWavelength(channel_name), {'hex': 0xFFFFFF, 'name': 'gray'})
            if channel_info['name'] in AVAILABLE_COLORMAPS:
                color = AVAILABLE_COLORMAPS[channel_info['name']]
            else:
                color = self.generateColormap(channel_info)

            layer = self.viewer.add_image(
                np.zeros_like(image), name=channel_name, rgb=len(image.shape) == 3, colormap=color,
                visible=True, blending='additive', scale=(self.viewer_pixel_size_mm * 1000, self.viewer_pixel_size_mm * 1000)
            )
            layer.mouse_double_click_callbacks.append(self.onDoubleClick)
            layer.events.contrast_limits.connect(self.signalContrastLimits)

        # get layer for channel
        layer = self.viewer.layers[channel_name]

        # update extents
        self.viewer_extents[0] = min(self.viewer_extents[0], y_mm)
        self.viewer_extents[1] = max(self.viewer_extents[1], y_mm + image.shape[0] * self.viewer_pixel_size_mm)
        self.viewer_extents[2] = min(self.viewer_extents[2], x_mm)
        self.viewer_extents[3] = max(self.viewer_extents[3], x_mm + image.shape[1] * self.viewer_pixel_size_mm)

        # store previous top-left coordinate
        prev_top_left = self.top_left_coordinate.copy() if self.top_left_coordinate else None
        self.top_left_coordinate = [self.viewer_extents[0], self.viewer_extents[2]]

        # update layer
        self.updateLayer(layer, image, x_mm, y_mm, k, prev_top_left)

        # update contrast limits
        min_val, max_val = self.contrastManager.get_limits(channel_name)
        scaled_min = self.convertValue(min_val, self.contrastManager.acquisition_dtype, self.mosaic_dtype)
        scaled_max = self.convertValue(max_val, self.contrastManager.acquisition_dtype, self.mosaic_dtype)
        layer.contrast_limits = (scaled_min, scaled_max)
        layer.refresh()

    def updateLayer(self, layer, image, x_mm, y_mm, k, prev_top_left):
        # calculate new mosaic size and position
        mosaic_height = int(math.ceil((self.viewer_extents[1] - self.viewer_extents[0]) / self.viewer_pixel_size_mm))
        mosaic_width = int(math.ceil((self.viewer_extents[3] - self.viewer_extents[2]) / self.viewer_pixel_size_mm))

        is_rgb = len(image.shape) == 3 and image.shape[2] == 3
        if layer.data.shape[:2] != (mosaic_height, mosaic_width):
            # calculate offsets for existing data
            y_offset = int(math.floor((prev_top_left[0] - self.top_left_coordinate[0]) / self.viewer_pixel_size_mm))
            x_offset = int(math.floor((prev_top_left[1] - self.top_left_coordinate[1]) / self.viewer_pixel_size_mm))

            for mosaic in self.viewer.layers:
                if mosaic.name != 'Manual ROI':
                    if len(mosaic.data.shape) == 3 and mosaic.data.shape[2] == 3:
                        new_data = np.zeros((mosaic_height, mosaic_width, 3), dtype=mosaic.data.dtype)
                    else:
                        new_data = np.zeros((mosaic_height, mosaic_width), dtype=mosaic.data.dtype)

                    # ensure offsets don't exceed bounds
                    y_end = min(y_offset + mosaic.data.shape[0], new_data.shape[0])
                    x_end = min(x_offset + mosaic.data.shape[1], new_data.shape[1])

                    # shift existing data
                    if len(mosaic.data.shape) == 3 and mosaic.data.shape[2] == 3:
                        new_data[y_offset:y_end, x_offset:x_end, :] = mosaic.data[:y_end-y_offset, :x_end-x_offset, :]
                    else:
                        new_data[y_offset:y_end, x_offset:x_end] = mosaic.data[:y_end-y_offset, :x_end-x_offset]
                    mosaic.data = new_data

            if 'Manual ROI' in self.viewer.layers:
                self.update_shape_layer_position(prev_top_left, self.top_left_coordinate)

            self.resetView()

        # insert new image
        y_pos = int(math.floor((y_mm - self.top_left_coordinate[0]) / self.viewer_pixel_size_mm))
        x_pos = int(math.floor((x_mm - self.top_left_coordinate[1]) / self.viewer_pixel_size_mm))

        # ensure indices are within bounds
        y_end = min(y_pos + image.shape[0], layer.data.shape[0])
        x_end = min(x_pos + image.shape[1], layer.data.shape[1])

        # insert image data
        if is_rgb:
            layer.data[y_pos:y_end, x_pos:x_end, :] = image[:y_end - y_pos, :x_end - x_pos, :]
        else:
            layer.data[y_pos:y_end, x_pos:x_end] = image[:y_end - y_pos, :x_end - x_pos]
        layer.refresh()

    def convertImageDtype(self, image, target_dtype):
        # convert image to target dtype
        if image.dtype == target_dtype:
            return image

        # get full range of values for both dtypes
        if np.issubdtype(image.dtype, np.integer):
            input_info = np.iinfo(image.dtype)
            input_min, input_max = input_info.min, input_info.max
        else:
            input_min, input_max = np.min(image), np.max(image)

        if np.issubdtype(target_dtype, np.integer):
            output_info = np.iinfo(target_dtype)
            output_min, output_max = output_info.min, output_info.max
        else:
            output_min, output_max = 0.0, 1.0

        # normalize and scale image
        image_normalized = (image.astype(np.float64) - input_min) / (input_max - input_min)
        image_scaled = image_normalized * (output_max - output_min) + output_min

        return image_scaled.astype(target_dtype)

    def convertValue(self, value, from_dtype, to_dtype):
        # Convert value from one dtype range to another
        from_info = np.iinfo(from_dtype)
        to_info = np.iinfo(to_dtype)

        # Normalize the value to [0, 1] range
        normalized = (value - from_info.min) / (from_info.max - from_info.min)

        # Scale to the target dtype range
        return normalized * (to_info.max - to_info.min) + to_info.min

    def signalContrastLimits(self, event):
        layer = event.source
        min_val, max_val = map(float, layer.contrast_limits)

        # Convert the new limits from mosaic_dtype to acquisition_dtype
        acquisition_min = self.convertValue(min_val, self.mosaic_dtype, self.contrastManager.acquisition_dtype)
        acquisition_max = self.convertValue(max_val, self.mosaic_dtype, self.contrastManager.acquisition_dtype)

        # Update the ContrastManager with the new limits
        self.contrastManager.update_limits(layer.name, acquisition_min, acquisition_max)

    def getContrastLimits(self, dtype):
        return self.contrastManager.get_default_limits()

    def onDoubleClick(self, layer, event):
        coords = layer.world_to_data(event.position)
        if coords is not None:
            x_mm = self.top_left_coordinate[1] + coords[-1] * self.viewer_pixel_size_mm
            y_mm = self.top_left_coordinate[0] + coords[-2] * self.viewer_pixel_size_mm
            print(f"move from click: ({x_mm:.6f}, {y_mm:.6f})")
            self.signal_coordinates_clicked.emit(x_mm, y_mm)

    def resetView(self):
        self.viewer.reset_view()
        for layer in self.viewer.layers:
            layer.refresh()

    def clear_shape(self):
        if self.shape_layer is not None:
            self.viewer.layers.remove(self.shape_layer)
            self.shape_layer = None
            self.is_drawing_shape = False
            self.signal_shape_drawn.emit([])

    def clearAllLayers(self):
        self.clear_shape()
        self.viewer.layers.clear()
        self.viewer_extents = None
        self.top_left_coordinate = None
        self.dtype = None
        self.channels = set()
        self.dz_um = None
        self.Nz = None
        self.layers_initialized = False
        self.signal_layers_initialized.emit(self.layers_initialized)
        self.signal_update_viewer.emit()

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
        # self.dropdown_tracker
        # self.dropdown_objective
        self.checkbox_set_z_range.setEnabled(enabled)
        self.list_configurations.setEnabled(enabled)

    def update_tracker(self, index):
        self.trackingController.update_tracker_selection(self.dropdown_tracker.currentText())

    def update_pixel_size(self):
        objective = self.dropdown_objective.currentText()
        self.trackingController.objective = objective
        # self.internal_state.data['Objective'] = self.objective
        pixel_size_um = CAMERA_PIXEL_SIZE_UM[CAMERA_SENSOR] / ( TUBE_LENS_MM/ (OBJECTIVES[objective]['tube_lens_f_mm']/OBJECTIVES[objective]['magnification']) )
        self.trackingController.update_pixel_size(pixel_size_um)
        print('pixel size is ' + str(pixel_size_um) + ' μm')

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
        print(f'pixel size is {pixel_size_xy:.2f} μm')

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
        self.plotWidget.plot(x[-self.N:],y[-self.N:],pen=pg.mkPen(color=color,width=4),name=label,clear=clear)

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

        self.btn_set_reference = QPushButton(" Set Reference ")
        self.btn_set_reference.setCheckable(False)
        self.btn_set_reference.setChecked(False)
        self.btn_set_reference.setDefault(False)
        if not self.laserAutofocusController.is_initialized:
            self.btn_set_reference.setEnabled(False)

        self.label_displacement = QLabel()
        self.label_displacement.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        self.btn_measure_displacement = QPushButton("Measure Displacement")
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

        self.btn_move_to_target = QPushButton("Move to Target")
        self.btn_move_to_target.setCheckable(False)
        self.btn_move_to_target.setChecked(False)
        self.btn_move_to_target.setDefault(False)
        if not self.laserAutofocusController.is_initialized:
            self.btn_move_to_target.setEnabled(False)

        self.grid = QGridLayout()

        self.grid.addWidget(self.btn_initialize,0,0,1,2)
        self.grid.addWidget(self.btn_set_reference,0,2,1,2)

        self.grid.addWidget(QLabel('Displacement (um)'),1,0)
        self.grid.addWidget(self.label_displacement,1,1)
        self.grid.addWidget(self.btn_measure_displacement,1,2,1,2)

        self.grid.addWidget(QLabel('Target (um)'),2,0)
        self.grid.addWidget(self.entry_target,2,1)
        self.grid.addWidget(self.btn_move_to_target,2,2,1,2)
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

    signalWellplateSettings = Signal(QVariant, float, float, int, int, float, float, int, int, int)

    def __init__(self, navigationController, navigationViewer, streamHandler, liveController):
        super().__init__()
        self.navigationController = navigationController
        self.navigationViewer = navigationViewer
        self.streamHandler = streamHandler
        self.liveController = liveController
        self.wellplate_format = WELLPLATE_FORMAT
        self.csv_path = SAMPLE_FORMATS_CSV_PATH # 'sample_formats.csv'
        self.initUI()

    def initUI(self):
        layout = QHBoxLayout(self)
        self.label = QLabel("Sample Format", self)
        self.comboBox = QComboBox(self)
        self.populate_combo_box()
        self.comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.label)
        layout.addWidget(self.comboBox)
        self.comboBox.currentIndexChanged.connect(self.wellplateChanged)
        index = self.comboBox.findData(self.wellplate_format)
        if index >= 0:
            self.comboBox.setCurrentIndex(index)

    def populate_combo_box(self):
        self.comboBox.clear()
        for format_, settings in WELLPLATE_FORMAT_SETTINGS.items():
            self.comboBox.addItem(format_, format_)

        # Add custom item and set its font to italic
        self.comboBox.addItem("calibrate format...", 'custom')
        index = self.comboBox.count() - 1  # Get the index of the last item
        font = QFont()
        font.setItalic(True)
        self.comboBox.setItemData(index, font, Qt.FontRole)

    def wellplateChanged(self, index):
        self.wellplate_format = self.comboBox.itemData(index)
        if self.wellplate_format == "custom":
            calibration_dialog = WellplateCalibration(self, self.navigationController, self.navigationViewer, self.streamHandler, self.liveController)
            result = calibration_dialog.exec_()
            if result == QDialog.Rejected:
                # If the dialog was closed without adding a new format, revert to the previous selection
                prev_index = self.comboBox.findData(self.wellplate_format)
                self.comboBox.setCurrentIndex(prev_index)
        else:
            self.setWellplateSettings(self.wellplate_format)

    def setWellplateSettings(self, wellplate_format):
        if wellplate_format in WELLPLATE_FORMAT_SETTINGS:
            settings = WELLPLATE_FORMAT_SETTINGS[wellplate_format]
        elif wellplate_format == 'glass slide':
            self.signalWellplateSettings.emit(QVariant('glass slide'), 0, 0, 0, 0, 0, 0, 0, 1, 1)
            return
        else:
            print(f"Wellplate format {wellplate_format} not recognized")
            return

        self.signalWellplateSettings.emit(
            QVariant(wellplate_format),
            settings['a1_x_mm'],
            settings['a1_y_mm'],
            settings['a1_x_pixel'],
            settings['a1_y_pixel'],
            settings['well_size_mm'],
            settings['well_spacing_mm'],
            settings['number_of_skip'],
            settings['rows'],
            settings['cols']
        )

    def getWellplateSettings(self, wellplate_format):
        if wellplate_format in WELLPLATE_FORMAT_SETTINGS:
            settings = WELLPLATE_FORMAT_SETTINGS[wellplate_format]
        elif wellplate_format == 'glass slide':
            settings = {
                'format': 'glass slide',
                'a1_x_mm': 0,
                'a1_y_mm': 0,
                'a1_x_pixel': 0,
                'a1_y_pixel': 0,
                'well_size_mm': 0,
                'well_spacing_mm': 0,
                'number_of_skip': 0,
                'rows': 1,
                'cols': 1
            }
        else:
            return None
        return settings

    def add_custom_format(self, name, settings):
        self.WELLPLATE_FORMAT_SETTINGS[name] = settings
        self.populate_combo_box()
        index = self.comboBox.findData(name)
        if index >= 0:
            self.comboBox.setCurrentIndex(index)
        self.wellplateChanged(index)

    def save_formats_to_csv(self):
        cache_path = os.path.join('cache', self.csv_path)
        os.makedirs('cache', exist_ok=True)

        fieldnames = ['format', 'a1_x_mm', 'a1_y_mm', 'a1_x_pixel', 'a1_y_pixel', 'well_size_mm', 'well_spacing_mm', 'number_of_skip', 'rows', 'cols']
        with open(cache_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for format_, settings in WELLPLATE_FORMAT_SETTINGS.items():
                writer.writerow({**{'format': format_}, **settings})

    @staticmethod
    def parse_csv_row(row):
        return {
            'a1_x_mm': float(row['a1_x_mm']),
            'a1_y_mm': float(row['a1_y_mm']),
            'a1_x_pixel': int(row['a1_x_pixel']),
            'a1_y_pixel': int(row['a1_y_pixel']),
            'well_size_mm': float(row['well_size_mm']),
            'well_spacing_mm': float(row['well_spacing_mm']),
            'number_of_skip': int(row['number_of_skip']),
            'rows': int(row['rows']),
            'cols': int(row['cols'])
        }


class WellplateCalibration(QDialog):

    def __init__(self, wellplateFormatWidget, navigationController, navigationViewer, streamHandler, liveController):
        super().__init__()
        self.setWindowTitle("Well Plate Calibration")
        self.wellplateFormatWidget = wellplateFormatWidget
        self.navigationController = navigationController
        self.navigationViewer = navigationViewer
        self.streamHandler = streamHandler
        self.liveController = liveController
        self.was_live = self.liveController.is_live
        self.corners = [None, None, None]
        self.show_virtual_joystick = True # FLAG
        self.initUI()
        # Initially allow click-to-move and hide the joystick controls
        self.clickToMoveCheckbox.setChecked(True)
        self.toggleVirtualJoystick(False)

    def initUI(self):
        layout = QHBoxLayout(self)  # Change to QHBoxLayout to have two columns

        # Left column for existing controls
        left_layout = QVBoxLayout()

        # Add radio buttons for selecting mode
        self.mode_group = QButtonGroup(self)
        self.new_format_radio = QRadioButton("Add New Format")
        self.calibrate_format_radio = QRadioButton("Calibrate Existing Format")
        self.mode_group.addButton(self.new_format_radio)
        self.mode_group.addButton(self.calibrate_format_radio)
        self.new_format_radio.setChecked(True)
        
        left_layout.addWidget(self.new_format_radio)
        left_layout.addWidget(self.calibrate_format_radio)

        # Existing format selection (initially hidden)
        self.existing_format_combo = QComboBox(self)
        self.populate_existing_formats()
        self.existing_format_combo.hide()
        left_layout.addWidget(self.existing_format_combo)

        # Connect radio buttons to toggle visibility
        self.new_format_radio.toggled.connect(self.toggle_input_mode)
        self.calibrate_format_radio.toggled.connect(self.toggle_input_mode)

        self.form_layout = QFormLayout()

        self.nameInput = QLineEdit(self)
        self.nameInput.setPlaceholderText("custom well plate")
        self.form_layout.addRow("Sample Name:", self.nameInput)

        self.rowsInput = QSpinBox(self)
        self.rowsInput.setRange(1, 100)
        self.rowsInput.setValue(8)
        self.form_layout.addRow("# Rows:", self.rowsInput)

        self.colsInput = QSpinBox(self)
        self.colsInput.setRange(1, 100)
        self.colsInput.setValue(12)
        self.form_layout.addRow("# Columns:", self.colsInput)

        # Add new inputs for plate dimensions
        self.plateWidthInput = QDoubleSpinBox(self)
        self.plateWidthInput.setRange(10, 500)  # Adjust range as needed
        self.plateWidthInput.setValue(127.76)  # Default value for a standard 96-well plate
        self.plateWidthInput.setSuffix(' mm')
        self.form_layout.addRow("Plate Width:", self.plateWidthInput)

        self.plateHeightInput = QDoubleSpinBox(self)
        self.plateHeightInput.setRange(10, 500)  # Adjust range as needed
        self.plateHeightInput.setValue(85.48)  # Default value for a standard 96-well plate
        self.plateHeightInput.setSuffix(' mm')
        self.form_layout.addRow("Plate Height:", self.plateHeightInput)

        self.wellSpacingInput = QDoubleSpinBox(self)
        self.wellSpacingInput.setRange(0.1, 100)
        self.wellSpacingInput.setValue(9)
        self.wellSpacingInput.setSingleStep(0.1)
        self.wellSpacingInput.setDecimals(2)
        self.wellSpacingInput.setSuffix(' mm')
        self.form_layout.addRow("Well Spacing:", self.wellSpacingInput)

        left_layout.addLayout(self.form_layout)

        points_layout = QGridLayout()
        self.cornerLabels = []
        self.setPointButtons = []
        navigate_label = QLabel("Navigate to and Select\n3 Points on the Edge of Well A1")
        navigate_label.setAlignment(Qt.AlignCenter)
        # navigate_label.setStyleSheet("font-weight: bold;")
        points_layout.addWidget(navigate_label, 0, 0, 1, 2)
        for i in range(1, 4):
            label = QLabel(f"Point {i}: N/A")
            button = QPushButton("Set Point")
            button.setFixedWidth(button.sizeHint().width())
            button.clicked.connect(lambda checked, index=i-1: self.setCorner(index))
            points_layout.addWidget(label, i, 0)
            points_layout.addWidget(button, i, 1)
            self.cornerLabels.append(label)
            self.setPointButtons.append(button)

        points_layout.setColumnStretch(0,1)
        left_layout.addLayout(points_layout)

        # Add 'Click to Move' checkbox
        self.clickToMoveCheckbox = QCheckBox("Click to Move")
        self.clickToMoveCheckbox.stateChanged.connect(self.toggleClickToMove)
        left_layout.addWidget(self.clickToMoveCheckbox)

        # Add 'Show Virtual Joystick' checkbox
        self.showJoystickCheckbox = QCheckBox("Virtual Joystick")
        self.showJoystickCheckbox.stateChanged.connect(self.toggleVirtualJoystick)
        left_layout.addWidget(self.showJoystickCheckbox)

        self.calibrateButton = QPushButton("Calibrate")
        self.calibrateButton.clicked.connect(self.calibrate)
        self.calibrateButton.setEnabled(False)
        left_layout.addWidget(self.calibrateButton)

        # Add left column to main layout
        layout.addLayout(left_layout)

        self.live_viewer = CalibrationLiveViewer(parent=self)
        self.streamHandler.image_to_display.connect(self.live_viewer.display_image)
        #self.live_viewer.signal_calibration_viewer_click.connect(self.navigationController.move_from_click)

        if not self.was_live:
            self.liveController.start_live()

        # when the dialog closes i want to # self.liveController.stop_live() if live was stopped before. . . if it was on before, leave it on
        layout.addWidget(self.live_viewer)

        # Right column for joystick and sensitivity controls
        self.right_layout = QVBoxLayout()
        self.right_layout.addStretch(1)

        self.joystick = Joystick(self)
        self.joystick.joystickMoved.connect(self.moveStage)
        self.right_layout.addWidget(self.joystick, 0, Qt.AlignTop | Qt.AlignHCenter)

        self.right_layout.addStretch(1)

        # Create a container widget for sensitivity label and slider
        sensitivity_layout = QVBoxLayout()

        sensitivityLabel = QLabel("Joystick Sensitivity")
        sensitivityLabel.setAlignment(Qt.AlignCenter)
        sensitivity_layout.addWidget(sensitivityLabel)

        self.sensitivitySlider = QSlider(Qt.Horizontal)
        self.sensitivitySlider.setMinimum(1)
        self.sensitivitySlider.setMaximum(100)
        self.sensitivitySlider.setValue(50)
        self.sensitivitySlider.setTickPosition(QSlider.TicksBelow)
        self.sensitivitySlider.setTickInterval(10)

        label_width = sensitivityLabel.sizeHint().width()
        self.sensitivitySlider.setFixedWidth(label_width)

        sensitivity_layout.addWidget(self.sensitivitySlider, 0, Qt.AlignHCenter)

        self.right_layout.addLayout(sensitivity_layout)

        layout.addLayout(self.right_layout)

        if not self.was_live:
            self.liveController.start_live()

    def toggleVirtualJoystick(self, state):
        if state:
            self.joystick.show()
            self.sensitivitySlider.show()
            self.right_layout.itemAt(self.right_layout.indexOf(self.joystick)).widget().show()
            self.right_layout.itemAt(self.right_layout.count() - 1).layout().itemAt(0).widget().show()  # Show sensitivity label
            self.right_layout.itemAt(self.right_layout.count() - 1).layout().itemAt(1).widget().show()  # Show sensitivity slider
        else:
            self.joystick.hide()
            self.sensitivitySlider.hide()
            self.right_layout.itemAt(self.right_layout.indexOf(self.joystick)).widget().hide()
            self.right_layout.itemAt(self.right_layout.count() - 1).layout().itemAt(0).widget().hide()  # Hide sensitivity label
            self.right_layout.itemAt(self.right_layout.count() - 1).layout().itemAt(1).widget().hide()  # Hide sensitivity slider

    # def updateCursorPosition(self, x, y):
    #     x_mm = self.navigationController.x_pos_mm + (x - self.live_viewer.width() / 2) * self.navigationController.x_mm_per_pixel
    #     y_mm = self.navigationController.y_pos_mm + (y - self.live_viewer.height() / 2) * self.navigationController.y_mm_per_pixel

    def moveStage(self, x, y):
        sensitivity = self.sensitivitySlider.value() / 50.0  # Normalize to 0-2 range
        max_speed = 0.1 * sensitivity
        exponent = 2

        dx = math.copysign(max_speed * abs(x)**exponent, x)
        dy = math.copysign(max_speed * abs(y)**exponent, y)

        self.navigationController.move_x(dx)
        self.navigationController.move_y(dy)

    def toggleClickToMove(self, state):
        if state == Qt.Checked:
            self.navigationController.set_flag_click_to_move(True)
            self.live_viewer.signal_calibration_viewer_click.connect(self.viewerClicked)
        else:
            self.live_viewer.signal_calibration_viewer_click.disconnect(self.viewerClicked)
            self.navigationController.set_flag_click_to_move(False)

    def viewerClicked(self, x, y, width, height):
        if self.clickToMoveCheckbox.isChecked():
            self.navigationController.move_from_click(x, y, width, height)

    def setCorner(self, index):
        if self.corners[index] is None:
            x = self.navigationController.x_pos_mm
            y = self.navigationController.y_pos_mm

            # Check if the new point is different from existing points
            if any(corner is not None and np.allclose([x, y], corner) for corner in self.corners):
                QMessageBox.warning(self, "Duplicate Point", "This point is too close to an existing point. Please choose a different location.")
                return

            self.corners[index] = (x, y)
            self.cornerLabels[index].setText(f"Point {index+1}: ({x:.2f}, {y:.2f})")
            self.setPointButtons[index].setText("Clear Point")
        else:
            self.corners[index] = None
            self.cornerLabels[index].setText(f"Point {index+1}: Not set")
            self.setPointButtons[index].setText("Set Point")

        self.calibrateButton.setEnabled(all(corner is not None for corner in self.corners))

    def populate_existing_formats(self):
        self.existing_format_combo.clear()
        for format_ in WELLPLATE_FORMAT_SETTINGS:
            self.existing_format_combo.addItem(f"{format_} well plate", format_)

    def toggle_input_mode(self):
        if self.new_format_radio.isChecked():
            self.existing_format_combo.hide()
            for i in range(self.form_layout.rowCount()):
                self.form_layout.itemAt(i, QFormLayout.FieldRole).widget().show()
                self.form_layout.itemAt(i, QFormLayout.LabelRole).widget().show()
        else:
            self.existing_format_combo.show()
            for i in range(self.form_layout.rowCount()):
                self.form_layout.itemAt(i, QFormLayout.FieldRole).widget().hide()
                self.form_layout.itemAt(i, QFormLayout.LabelRole).widget().hide()

    def calibrate(self):
        try:
            if self.new_format_radio.isChecked():
                if not self.nameInput.text() or not all(self.corners):
                    QMessageBox.warning(self, "Incomplete Information", "Please fill in all fields and set 3 corner points before calibrating.")
                    return

                name = self.nameInput.text()
                rows = self.rowsInput.value()
                cols = self.colsInput.value()
                well_spacing_mm = self.wellSpacingInput.value()
                plate_width_mm = self.plateWidthInput.value()
                plate_height_mm = self.plateHeightInput.value()

                center, radius = self.calculate_circle(self.corners)
                well_size_mm = radius * 2
                a1_x_mm, a1_y_mm = center
                scale = 1 / 0.084665
                a1_x_pixel = round(a1_x_mm * scale)
                a1_y_pixel = round(a1_y_mm * scale)

                new_format = {
                    'a1_x_mm': a1_x_mm,
                    'a1_y_mm': a1_y_mm,
                    'a1_x_pixel': a1_x_pixel,
                    'a1_y_pixel': a1_y_pixel,
                    'well_size_mm': well_size_mm,
                    'well_spacing_mm': well_spacing_mm,
                    'number_of_skip': 0,
                    'rows': rows,
                    'cols': cols,
                }

                self.wellplateFormatWidget.add_custom_format(name, new_format)
                self.wellplateFormatWidget.save_formats_to_csv()
                self.create_wellplate_image(name, new_format, plate_width_mm, plate_height_mm)
                self.wellplateFormatWidget.setWellplateSettings(name)
                success_message = f"New format '{name}' has been successfully created and calibrated."

            else:
                selected_format = self.existing_format_combo.currentData()
                if not all(self.corners):
                    QMessageBox.warning(self, "Incomplete Information", "Please set 3 corner points before calibrating.")
                    return

                center, radius = self.calculate_circle(self.corners)
                well_size_mm = radius * 2
                a1_x_mm, a1_y_mm = center

                # Get the existing format settings
                existing_settings = WELLPLATE_FORMAT_SETTINGS[selected_format]

                # # Calculate the offset between the original 0,0 pixel and 0,0 mm
                # original_offset_x = existing_settings['a1_x_mm'] - (existing_settings['a1_x_pixel'] * 0.084665)
                # original_offset_y = existing_settings['a1_y_mm'] - (existing_settings['a1_y_pixel'] * 0.084665)
                # # Calculate new pixel coordinates using the original offset
                # a1_x_pixel = round((a1_x_mm - original_offset_x) / 0.084665)
                # a1_y_pixel = round((a1_y_mm - original_offset_y) / 0.084665)

                print(f"Updating existing format {selected_format} well plate")
                print(f"OLD: 'a1_x_mm': {existing_settings['a1_x_mm']}, 'a1_y_mm': {existing_settings['a1_y_mm']}, 'well_size_mm': {existing_settings['well_size_mm']}")
                print(f"NEW: 'a1_x_mm': {a1_x_mm}, 'a1_y_mm': {a1_y_mm}, 'well_size_mm': {well_size_mm}") 

                updated_settings = {
                    'a1_x_mm': a1_x_mm,
                    'a1_y_mm': a1_y_mm,
                    # 'a1_x_pixel': a1_x_pixel,
                    # 'a1_y_pixel': a1_y_pixel,
                    'well_size_mm': well_size_mm,
                }

                WELLPLATE_FORMAT_SETTINGS[selected_format].update(updated_settings)

                self.wellplateFormatWidget.save_formats_to_csv()
                self.wellplateFormatWidget.setWellplateSettings(selected_format)
                success_message = f"Format '{selected_format} well plate' has been successfully recalibrated."

            # Update the WellplateFormatWidget's combo box to reflect the newly calibrated format
            self.wellplateFormatWidget.populate_combo_box()
            index = self.wellplateFormatWidget.comboBox.findData(selected_format if self.calibrate_format_radio.isChecked() else name)
            if index >= 0:
                self.wellplateFormatWidget.comboBox.setCurrentIndex(index)

            # Display success message
            QMessageBox.information(self, "Calibration Successful", success_message)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Calibration Error", f"An error occurred during calibration: {str(e)}")

    def create_wellplate_image(self, name, format_data, plate_width_mm, plate_height_mm):

        scale = 1 / 0.084665
        def mm_to_px(mm):
            return round(mm * scale)

        width = mm_to_px(plate_width_mm)
        height = mm_to_px(plate_height_mm)
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        rows, cols = format_data['rows'], format_data['cols']
        well_spacing_mm = format_data['well_spacing_mm']
        well_size_mm = format_data['well_size_mm']
        a1_x_mm, a1_y_mm = format_data['a1_x_mm'], format_data['a1_y_mm']

        def draw_left_slanted_rectangle(draw, xy, slant, width=4, outline='black', fill=None):
            x1, y1, x2, y2 = xy

            # Define the polygon points
            points = [
                (x1 + slant, y1),  # Top-left after slant
                (x2, y1),          # Top-right
                (x2, y2),          # Bottom-right
                (x1 + slant, y2),  # Bottom-left after slant
                (x1, y2 - slant),  # Bottom of left slant
                (x1, y1 + slant)   # Top of left slant
            ]

            # Draw the filled polygon with outline
            draw.polygon(points, fill=fill, outline=outline, width=width)

        # Draw the outer rectangle with rounded corners
        corner_radius = 20
        draw.rounded_rectangle([0, 0, width-1, height-1], radius=corner_radius, outline='black', width=4, fill='grey')

        # Draw the inner rectangle with left slanted corners
        margin = 20
        slant = 40
        draw_left_slanted_rectangle(draw,
                                    [margin, margin, width-margin, height-margin],
                                    slant, width=4, outline='black', fill='lightgrey')

        # Function to draw a circle
        def draw_circle(x, y, diameter):
            radius = diameter / 2
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], outline='black', width=4, fill='white')

        # Draw the wells
        for row in range(rows):
            for col in range(cols):
                x = mm_to_px(a1_x_mm + col * well_spacing_mm)
                y = mm_to_px(a1_y_mm + row * well_spacing_mm)
                draw_circle(x, y, mm_to_px(well_size_mm))

        # Load a default font
        font_size = 30
        font = ImageFont.load_default().font_variant(size=font_size)

        # Add column labels
        for col in range(cols):
            label = str(col + 1)
            x = mm_to_px(a1_x_mm + col * well_spacing_mm)
            y = mm_to_px((a1_y_mm - well_size_mm/2) / 2)
            bbox = font.getbbox(label)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((x - text_width/2, y), label, fill="black", font=font)

        # Add row labels
        for row in range(rows):
            label = chr(65 + row) if row < 26 else chr(65 + row // 26 - 1) + chr(65 + row % 26)
            x = mm_to_px((a1_x_mm - well_size_mm/2 ) / 2)
            y = mm_to_px(a1_y_mm + row * well_spacing_mm)
            bbox = font.getbbox(label)
            text_height = bbox[3] - bbox[1]
            text_width = bbox[2] - bbox[0]
            draw.text((x + 20 - text_width/2, y - text_height + 1), label, fill="black", font=font)

        image_path = os.path.join('images', f'{name.replace(" ", "_")}.png')
        image.save(image_path)
        print(f"Wellplate image saved as {image_path}")
        return image_path

    @staticmethod
    def calculate_circle(points):
        # Convert points to numpy array
        points = np.array(points)

        # Calculate the center and radius of the circle
        A = np.array([points[1] - points[0], points[2] - points[0]])
        b = np.sum(A * (points[1:3] + points[0]) / 2, axis=1)
        center = np.linalg.solve(A, b)

        # Calculate the radius
        radius = np.mean(np.linalg.norm(points - center, axis=1))

        return center, radius

    def closeEvent(self, event):
        # Stop live view if it wasn't initially on
        if not self.was_live:
            self.liveController.stop_live()
        super().closeEvent(event)

    def accept(self):
        # Stop live view if it wasn't initially on
        if not self.was_live:
            self.liveController.stop_live()
        super().accept()

    def reject(self):
        # This method is called when the dialog is closed without accepting
        if not self.was_live:
            self.liveController.stop_live()
        sample = self.navigationViewer.sample

        # Convert sample string to format int
        if 'glass slide' in sample:
            sample_format = 'glass slide'
        else:
            try:
                sample_format = int(sample.split()[0])
            except (ValueError, IndexError):
                print(f"Unable to parse sample format from '{sample}'. Defaulting to 0.")
                sample_format = 'glass slide'

        # Set dropdown to the current sample format
        index = self.wellplateFormatWidget.comboBox.findData(sample_format)
        if index >= 0:
            self.wellplateFormatWidget.comboBox.setCurrentIndex(index)

        # Update wellplate settings
        self.wellplateFormatWidget.setWellplateSettings(sample_format)

        super().reject()


class CalibrationLiveViewer(QWidget):

    signal_calibration_viewer_click = Signal(int, int, int, int)
    signal_mouse_moved = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.initial_zoom_set = False
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = pg.GraphicsLayoutWidget()
        self.viewbox = self.view.addViewBox()
        self.viewbox.setAspectLocked(True)
        self.viewbox.invertY(True)

        # Set appropriate panning limits based on the acquisition image or plate size
        xmax = int(Acquisition.CROP_WIDTH * Acquisition.IMAGE_DISPLAY_SCALING_FACTOR)
        ymax = int(Acquisition.CROP_HEIGHT * Acquisition.IMAGE_DISPLAY_SCALING_FACTOR)
        self.viewbox.setLimits(xMin=0, xMax=xmax, yMin=0, yMax=ymax)

        self.img_item = pg.ImageItem()
        self.viewbox.addItem(self.img_item)

        # Add fixed crosshair
        pen = QPen(QColor(255, 0, 0))  # Red color
        pen.setWidth(4)

        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self.viewbox.addItem(self.crosshair_h)
        self.viewbox.addItem(self.crosshair_v)

        layout.addWidget(self.view)

        # Connect double-click event
        self.view.scene().sigMouseClicked.connect(self.onMouseClicked)

        # Set fixed size for the viewer
        self.setFixedSize(500, 500)

        # Initialize with a blank image
        self.display_image(np.zeros((xmax, ymax)))

    def setCrosshairPosition(self):
        center = self.viewbox.viewRect().center()
        self.crosshair_h.setPos(center.y())
        self.crosshair_v.setPos(center.x())

    def display_image(self, image):
        # Step 1: Update the image
        self.img_item.setImage(image)

        # Step 2: Get the image dimensions
        image_width = image.shape[1]
        image_height = image.shape[0]

        # Step 3: Calculate the center of the image
        image_center_x = image_width / 2
        image_center_y = image_height / 2

        # Step 4: Calculate the current view range
        current_view_range = self.viewbox.viewRect()

        # Step 5: If it's the first image or initial zoom hasn't been set, center the image
        if not self.initial_zoom_set:
            self.viewbox.setRange(xRange=(0, image_width), yRange=(0, image_height), padding=0)
            self.initial_zoom_set = True  # Mark initial zoom as set

        # Step 6: Always center the view around the image center (for seamless transitions)
        else:
            self.viewbox.setRange(
                xRange=(image_center_x - current_view_range.width() / 2,
                        image_center_x + current_view_range.width() / 2),
                yRange=(image_center_y - current_view_range.height() / 2,
                        image_center_y + current_view_range.height() / 2),
                padding=0
            )

        # Step 7: Ensure the crosshair is updated
        self.setCrosshairPosition()

    # def mouseMoveEvent(self, event):
    #     self.signal_mouse_moved.emit(event.x(), event.y())

    def onMouseClicked(self, event):
        # Map the scene position to view position
        if event.double(): # double click to move
            pos = event.pos()
            scene_pos = self.viewbox.mapSceneToView(pos)

            # Get the x, y coordinates
            x, y = int(scene_pos.x()), int(scene_pos.y())
            # Ensure the coordinates are within the image boundaries
            image_shape = self.img_item.image.shape
            if 0 <= x < image_shape[1] and 0 <= y < image_shape[0]:
                # Adjust the coordinates to be relative to the center of the image
                x_centered = x - image_shape[1] // 2
                y_centered = y - image_shape[0] // 2
                # Emit the signal with the clicked coordinates and image size
                self.signal_calibration_viewer_click.emit(x_centered, y_centered, image_shape[1], image_shape[0])
            else:
                print("click was outside the image bounds.")
        else:
            print("single click only detected")

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            scale_factor = 0.9
        else:
            scale_factor = 1.1

        # Get the center of the viewbox
        center = self.viewbox.viewRect().center()

        # Scale the view
        self.viewbox.scaleBy((scale_factor, scale_factor), center)

        # Update crosshair position after scaling
        self.setCrosshairPosition()

        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setCrosshairPosition()


class Joystick(QWidget):
    joystickMoved = Signal(float, float)  # Emits x and y values between -1 and 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200)
        self.inner_radius = 40
        self.max_distance = self.width() // 2 - self.inner_radius
        self.outer_radius = int(self.width() * 3 / 8)
        self.current_x = 0
        self.current_y = 0
        self.is_pressed = False
        self.timer = QTimer(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate the painting area
        paint_rect = QRectF(0, 0, 200, 200)

        # Draw outer circle
        painter.setBrush(QColor(230, 230, 230))  # Light grey fill
        painter.setPen(QPen(QColor(100, 100, 100), 2))  # Dark grey outline
        painter.drawEllipse(paint_rect.center(), self.outer_radius, self.outer_radius)

        # Draw inner circle (joystick position)
        painter.setBrush(QColor(100, 100, 100))
        painter.setPen(Qt.NoPen)
        joystick_x = paint_rect.center().x() + self.current_x * self.max_distance
        joystick_y = paint_rect.center().y() + self.current_y * self.max_distance
        painter.drawEllipse(QPointF(joystick_x, joystick_y), self.inner_radius, self.inner_radius)

    def mousePressEvent(self, event):
        if QRectF(0, 0, 200, 200).contains(event.pos()):
            self.is_pressed = True
            self.updateJoystickPosition(event.pos())
            self.timer.timeout.connect(self.update_position)
            self.timer.start(10)

    def mouseMoveEvent(self, event):
        if self.is_pressed and QRectF(0, 0, 200, 200).contains(event.pos()):
            self.updateJoystickPosition(event.pos())

    def mouseReleaseEvent(self, event):
        self.is_pressed = False
        self.updateJoystickPosition(QPointF(100, 100))  # Center position
        self.timer.timeout.disconnect(self.update_position)
        self.joystickMoved.emit(0, 0)

    def update_position(self):
        if self.is_pressed:
            self.joystickMoved.emit(self.current_x, -self.current_y)

    def updateJoystickPosition(self, pos):
        center = QPointF(100, 100)
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        distance = math.sqrt(dx**2 + dy**2)

        if distance > self.max_distance:
            dx = dx * self.max_distance / distance
            dy = dy * self.max_distance / distance

        self.current_x = dx / self.max_distance
        self.current_y = dy / self.max_distance
        self.update()


class WellSelectionWidget(QTableWidget):

    signal_wellSelected = Signal(bool)
    signal_wellSelectedPos = Signal(float, float)

    def __init__(self, format_, wellplateFormatWidget, *args, **kwargs):
        super(WellSelectionWidget, self).__init__(*args, **kwargs)
        self.wellplateFormatWidget = wellplateFormatWidget
        self.wellplateFormatWidget.signalWellplateSettings.connect(self.updateWellplateSettings)
        self.cellDoubleClicked.connect(self.onDoubleClick)
        self.itemSelectionChanged.connect(self.onSelectionChanged)
        self.fixed_height = 400
        self.setFormat(format_)

    def setFormat(self, format_):
        self.format = format_
        settings = self.getWellplateSettings(self.format)
        self.rows = settings['rows']
        self.columns = settings['cols']
        self.spacing_mm = settings['well_spacing_mm']
        self.number_of_skip = settings['number_of_skip']
        self.a1_x_mm = settings['a1_x_mm']
        self.a1_y_mm = settings['a1_y_mm']
        self.a1_x_pixel = settings['a1_x_pixel']
        self.a1_y_pixel = settings['a1_y_pixel']
        self.well_size_mm = settings['well_size_mm']

        self.setRowCount(self.rows)
        self.setColumnCount(self.columns)
        self.initUI()
        self.setData()

    def initUI(self):
        # Disable editing, scrollbars, and other interactions
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.verticalScrollBar().setDisabled(True)
        self.horizontalScrollBar().setDisabled(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setTabKeyNavigation(False)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDragDropOverwriteMode(False)
        self.setMouseTracking(False)

        if self.format == '1536 well plate':
            font = QFont()
            font.setPointSize(6)  # You can adjust this value as needed
        else:
            font = QFont()
        self.horizontalHeader().setFont(font)
        self.verticalHeader().setFont(font)

        self.setLayout()

    def setLayout(self):
        # Calculate available space and cell size
        header_height = self.horizontalHeader().height()
        available_height = self.fixed_height - header_height  # Fixed height of 408 pixels

        # Calculate cell size based on the minimum of available height and width
        cell_size = available_height // self.rowCount()

        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(cell_size)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setDefaultSectionSize(cell_size)

        # Ensure sections do not resize
        self.verticalHeader().setMinimumSectionSize(cell_size)
        self.verticalHeader().setMaximumSectionSize(cell_size)
        self.horizontalHeader().setMinimumSectionSize(cell_size)
        self.horizontalHeader().setMaximumSectionSize(cell_size)

        row_header_width = self.verticalHeader().width()

        # Calculate total width and height
        total_height = (self.rowCount() * cell_size) + header_height
        total_width = (self.columnCount() * cell_size) + row_header_width

        # Set the widget's fixed size
        self.setFixedHeight(total_height)
        self.setFixedWidth(total_width)

        # Force the widget to update its layout
        self.updateGeometry()
        self.viewport().update()

    def getWellplateSettings(self, wellplate_format):
        return self.wellplateFormatWidget.getWellplateSettings(wellplate_format)

    def updateWellplateSettings(self, format_, a1_x_mm, a1_y_mm, a1_x_pixel, a1_y_pixel, well_size_mm, well_spacing_mm, number_of_skip, rows, cols):
        if isinstance(format_, QVariant):
            format_ = format_.value()
        self.setFormat(format_)

    def setData(self):
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                item = self.item(i, j)
                if not item:  # Create a new item if none exists
                    item = QTableWidgetItem()
                    self.setItem(i, j, item)
                # Reset to selectable by default
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        if self.number_of_skip > 0 and self.format != 0:
            for i in range(self.number_of_skip):
                for j in range(self.columns):  # Apply to rows
                    self.item(i, j).setFlags(self.item(i, j).flags() & ~Qt.ItemIsSelectable)
                    self.item(self.rows - 1 - i, j).setFlags(self.item(self.rows - 1 - i, j).flags() & ~Qt.ItemIsSelectable)
                for k in range(self.rows):  # Apply to columns
                    self.item(k, i).setFlags(self.item(k, i).flags() & ~Qt.ItemIsSelectable)
                    self.item(k, self.columns - 1 - i).setFlags(self.item(k, self.columns - 1 - i).flags() & ~Qt.ItemIsSelectable)

        # Update row headers
        row_headers = []
        for i in range(self.rows):
            if i < 26:
                label = chr(ord('A') + i)
            else:
                first_letter = chr(ord('A') + (i // 26) - 1)
                second_letter = chr(ord('A') + (i % 26))
                label = first_letter + second_letter
            row_headers.append(label)
        self.setVerticalHeaderLabels(row_headers)

        # Adjust vertical header width after setting labels
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def onDoubleClick(self, row, col):
        print("double click well", row, col)
        if (row >= 0 + self.number_of_skip and row <= self.rows-1-self.number_of_skip ) and ( col >= 0 + self.number_of_skip and col <= self.columns-1-self.number_of_skip ):
            x_mm = col*self.spacing_mm + self.a1_x_mm + WELLPLATE_OFFSET_X_mm
            y_mm = row*self.spacing_mm + self.a1_y_mm + WELLPLATE_OFFSET_Y_mm
            self.signal_wellSelectedPos.emit(x_mm,y_mm)
            print("well location:", (x_mm,y_mm))
            self.signal_wellSelected.emit(True)
        else:
            self.signal_wellSelected.emit(False)

    def onSingleClick(self,row,col):
        print("single click well", row, col)
        if (row >= 0 + self.number_of_skip and row <= self.rows-1-self.number_of_skip ) and ( col >= 0 + self.number_of_skip and col <= self.columns-1-self.number_of_skip ):
            self.signal_wellSelected.emit(True)
        else:
            self.signal_wellSelected.emit(False)

    def onSelectionChanged(self):
        selected_cells = self.get_selected_cells()
        self.signal_wellSelected.emit(bool(selected_cells))

    def get_selected_cells(self):
        list_of_selected_cells = []
        print("getting selected cells...")
        if self.format == 'glass slide':
            return list_of_selected_cells
        for index in self.selectedIndexes():
            row, col = index.row(), index.column()
            # Check if the cell is within the allowed bounds
            if (row >= 0 + self.number_of_skip and row <= self.rows - 1 - self.number_of_skip) and \
               (col >= 0 + self.number_of_skip and col <= self.columns - 1 - self.number_of_skip):
                list_of_selected_cells.append((row, col))
        if list_of_selected_cells:
            print("cells:", list_of_selected_cells)
        else:
            print("no cells")
        return list_of_selected_cells

    def resizeEvent(self, event):
        self.initUI()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        # Ignore wheel events to prevent scrolling
        event.ignore()

    def scrollTo(self, index, hint=QAbstractItemView.EnsureVisible):
        pass

    def set_white_boundaries_style(self):
        style = """
        QTableWidget {
            gridline-color: white;
            border: 1px solid white;
        }
        QHeaderView::section {
            color: white;
        }
        """
        # QTableWidget::item {
        #     border: 1px solid white;
        # }
        self.setStyleSheet(style)


class Well1536SelectionWidget(QWidget):

    signal_wellSelected = Signal(bool)
    signal_wellSelectedPos = Signal(float,float)

    def __init__(self):
        super().__init__()
        self.format = '1536 well plate'
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
        self.setGeometry(100, 100, 750, 400)  # Increased width to accommodate controls

        self.a = 11
        image_width = 48 * self.a
        image_height = 32 * self.a

        self.image = QPixmap(image_width, image_height)
        self.image.fill(QColor('white'))
        self.label = QLabel()
        self.label.setPixmap(self.image)
        self.label.setFixedSize(image_width, image_height)
        self.label.setAlignment(Qt.AlignCenter)

        self.cell_input = QLineEdit(self)
        self.cell_input.setPlaceholderText("e.g. AE12 or B4")
        go_button = QPushButton('Go to well', self)
        go_button.clicked.connect(self.go_to_cell)
        self.selection_input = QLineEdit(self)
        self.selection_input.setPlaceholderText("e.g. A1:E48, X1, AC24, Z2:AF6, ...")
        self.selection_input.editingFinished.connect(self.select_cells)

        # Create navigation buttons
        up_button = QPushButton('↑', self)
        left_button = QPushButton('←', self)
        right_button = QPushButton('→', self)
        down_button = QPushButton('↓', self)
        add_button = QPushButton('Select', self)

        # Connect navigation buttons to their respective functions
        up_button.clicked.connect(self.move_up)
        left_button.clicked.connect(self.move_left)
        right_button.clicked.connect(self.move_right)
        down_button.clicked.connect(self.move_down)
        add_button.clicked.connect(self.add_current_well)

        layout = QHBoxLayout()
        layout.addWidget(self.label)

        layout_controls = QVBoxLayout()
        layout_controls.addStretch(2)

        # Add navigation buttons in a + sign layout
        layout_move = QGridLayout()
        layout_move.addWidget(up_button, 0, 2)
        layout_move.addWidget(left_button, 1, 1)
        layout_move.addWidget(add_button, 1, 2)
        layout_move.addWidget(right_button, 1, 3)
        layout_move.addWidget(down_button, 2, 2)
        layout_move.setColumnStretch(0, 1)
        layout_move.setColumnStretch(4, 1)
        layout_controls.addLayout(layout_move)

        layout_controls.addStretch(1)

        layout_input = QGridLayout()
        layout_input.addWidget(QLabel("Well Navigation"), 0, 0)
        layout_input.addWidget(self.cell_input, 0, 1)
        layout_input.addWidget(go_button, 0, 2)
        layout_input.addWidget(QLabel("Well Selection"), 1, 0)
        layout_input.addWidget(self.selection_input, 1, 1, 1, 2)
        layout_controls.addLayout(layout_input)

        control_widget = QWidget()
        control_widget.setLayout(layout_controls)
        control_widget.setFixedHeight(image_height)  # Set the height of controls to match the image

        layout.addWidget(control_widget)
        self.setLayout(layout)

    def move_up(self):
        if self.current_cell:
            row, col = self.current_cell
            if row > 0:
                self.current_cell = (row - 1, col)
                self.update_current_cell()

    def move_left(self):
        if self.current_cell:
            row, col = self.current_cell
            if col > 0:
                self.current_cell = (row, col - 1)
                self.update_current_cell()

    def move_right(self):
        if self.current_cell:
            row, col = self.current_cell
            if col < self.columns - 1:
                self.current_cell = (row, col + 1)
                self.update_current_cell()

    def move_down(self):
        if self.current_cell:
            row, col = self.current_cell
            if row < self.rows - 1:
                self.current_cell = (row + 1, col)
                self.update_current_cell()

    def add_current_well(self):
        if self.current_cell:
            row, col = self.current_cell
            cell_name = f"{chr(65 + row)}{col + 1}"

            if (row, col) in self.selected_cells:
                # If the well is already selected, remove it
                del self.selected_cells[(row, col)]
                self.remove_well_from_selection_input(cell_name)
                print(f"Removed well {cell_name}")
            else:
                # If the well is not selected, add it
                self.selected_cells[(row, col)] = '#1f77b4'  # Add to selected cells with blue color
                self.add_well_to_selection_input(cell_name)
                print(f"Added well {cell_name}")

            self.redraw_wells()
            self.signal_wellSelected.emit(bool(self.selected_cells))

    def add_well_to_selection_input(self, cell_name):
        current_selection = self.selection_input.text()
        if current_selection:
            self.selection_input.setText(f"{current_selection}, {cell_name}")
        else:
            self.selection_input.setText(cell_name)

    def remove_well_from_selection_input(self, cell_name):
        current_selection = self.selection_input.text()
        cells = [cell.strip() for cell in current_selection.split(',')]
        if cell_name in cells:
            cells.remove(cell_name)
            self.selection_input.setText(', '.join(cells))

    def update_current_cell(self):
        self.redraw_wells()
        row, col = self.current_cell
        if row < 26:
            row_label = chr(65 + row)
        else:
            row_label = chr(64 + (row // 26)) + chr(65 + (row % 26))
        # Update cell_input with the correct label (e.g., A1, B2, AA1, etc.)
        self.cell_input.setText(f"{row_label}{col + 1}")

        x_mm = col * self.spacing_mm + self.a1_x_mm + WELLPLATE_OFFSET_X_mm
        y_mm = row * self.spacing_mm + self.a1_y_mm + WELLPLATE_OFFSET_Y_mm
        self.signal_wellSelectedPos.emit(x_mm, y_mm)

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
            painter.setBrush(Qt.NoBrush)  # No fill
            painter.setPen(QPen(QColor('red'), 2))  # Red outline, 2 pixels wide
            row, col = self.current_cell
            painter.drawRect(col * self.a+2, row * self.a+2, self.a-3, self.a-3)
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
        if self.selected_cells:
            self.signal_wellSelected.emit(True)

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


class SampleSettingsWidget(QFrame):
    def __init__(self, ObjectivesWidget, WellplateFormatWidget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objectivesWidget = ObjectivesWidget
        self.wellplateFormatWidget = WellplateFormatWidget

        # Set up the layout
        top_row_layout = QGridLayout()
        top_row_layout.setSpacing(2)
        top_row_layout.setContentsMargins(0, 2, 0, 2)
        top_row_layout.addWidget(self.objectivesWidget, 0, 0)
        top_row_layout.addWidget(self.wellplateFormatWidget, 0, 1)
        self.setLayout(top_row_layout)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

        # Connect signals for saving settings
        self.objectivesWidget.signal_objective_changed.connect(self.save_settings)
        self.wellplateFormatWidget.signalWellplateSettings.connect(lambda *args: self.save_settings())

    def save_settings(self):
        """Save current objective and wellplate format to cache"""
        os.makedirs('cache', exist_ok=True)
        data = {
            'objective': self.objectivesWidget.dropdown.currentText(),
            'wellplate_format': self.wellplateFormatWidget.wellplate_format
        }

        with open('cache/objective_and_sample_format.txt', 'w') as f:
            json.dump(data, f)

