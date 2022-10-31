# set QT_API environment variable
import os

os.environ["QT_API"] = "pyqt5"

# qt libraries
from qtpy.QtCore import Qt, QEvent
from qtpy.QtWidgets import QMainWindow, QTabWidget, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDesktopWidget

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
from control._def import *

import pyqtgraph.dockarea as dock

from control.typechecker import TypecheckFunction

from typing import List, Tuple, Callable

class HCSController():
	#@TypecheckFunction
	def __init__(self,well_selection_generator:Callable[[],Tuple[List[str],List[Tuple[float,float]]]]):
		# load objects
		try:
			self.camera = camera.Camera(rotate_image_angle=MACHINE_CONFIG.ROTATE_IMAGE_ANGLE,flip_image=MACHINE_CONFIG.FLIP_IMAGE)
			self.camera.open()
		except Exception as e:
			print('! camera not detected !')
			raise e

		self.microcontroller:microcontroller.Microcontroller = microcontroller.Microcontroller(version=MACHINE_CONFIG.CONTROLLER_VERSION)

		# reset the MCU
		self.microcontroller.reset()
		
		# configure the actuators
		self.microcontroller.configure_actuators()

		self.configurationManager:    core.ConfigurationManager    = core.ConfigurationManager(filename='./channel_configurations.xml')
		self.streamHandler:           core.StreamHandler           = core.StreamHandler(display_resolution_scaling=MACHINE_DISPLAY_CONFIG.DEFAULT_DISPLAY_CROP/100)
		self.liveController:          core.LiveController          = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController:    core.NavigationController    = core.NavigationController(self.microcontroller)
		self.slidePositionController: core.SlidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
		self.autofocusController:     core.AutoFocusController     = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.multipointController:    core.MultiPointController    = core.MultiPointController(
			self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,
			well_selection_generator,self.start_experiment,self.abort_experiment)
		self.imageSaver:              core.ImageSaver              = core.ImageSaver()

		self.navigationController.home()

	def acquire(self,
		well_list:List[Tuple[int,int]],
		channels:List[str],
		af_channel:str,
	):
		# set objective and well plate type from machine config (or.. should be part of imaging configuration..?)
		# set wells to be imaged <- acquire.well_list argument
		# set grid per well to be imaged
		# set lighting settings per channel
		# set selection and order of channels to be imaged <- acquire.channels argument

		pass

	@TypecheckFunction
	def start_experiment(self,experiment_data_target_folder:str,imaging_channel_list:List[str]):
		self.multipointController.prepare_folder_for_new_experiment(experiment_data_target_folder)
		self.multipointController.set_selected_configurations(imaging_channel_list)
		self.multipointController.run_experiment()

	def abort_experiment(self):
		self.multipointController.request_abort_aquisition()

	# add callbacks to be triggered on image acquisition (e.g. for histograms, saving to disk etc.)

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	@property
	def configurationManager(self)->core.ConfigurationManager:
		return self.hcs_controller.configurationManager
	@property
	def streamHandler(self)->core.StreamHandler:
		return self.hcs_controller.streamHandler
	@property
	def liveController(self)->core.LiveController:
		return self.hcs_controller.liveController
	@property
	def navigationController(self)->core.NavigationController:
		return self.hcs_controller.navigationController
	@property
	def slidePositionController(self)->core.SlidePositionController:
		return self.hcs_controller.slidePositionController
	@property
	def autofocusController(self)->core.AutoFocusController:
		return self.hcs_controller.autofocusController
	@property
	def multipointController(self)->core.MultiPointController:
		return self.hcs_controller.multipointController
	@property
	def imageSaver(self)->core.ImageSaver:
		return self.hcs_controller.imageSaver
	@property
	def camera(self)->camera.Camera:
		return self.hcs_controller.camera
	@property
	def microcontroller(self)->microcontroller.Microcontroller:
		return self.hcs_controller.microcontroller

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load window
		self.imageDisplayWindow = widgets.ImageDisplayWindow(draw_crosshairs=True)
		self.imageArrayDisplayWindow = widgets.ImageArrayDisplayWindow()

		# image display windows
		self.imageDisplayTabs = QTabWidget()
		self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
		self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

		# these widgets are used by a controller (which already tells us that there is something very wrong!)
		default_well_plate=str(MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT)+' well plate'
		self.wellSelectionWidget = widgets.WellSelectionWidget(MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT)

		self.hcs_controller=HCSController(well_selection_generator=self.wellSelectionWidget.widget_well_indices_to_physical_positions)
		
		# open the camera
		self.camera.set_software_triggered_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()

		# load widgets
		self.imageDisplay           = widgets.ImageDisplay()
		self.cameraSettingWidget    = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
		self.liveControlWidget      = widgets.LiveControlWidget(self.hcs_controller.streamHandler,self.hcs_controller.liveController,self.hcs_controller.configurationManager,show_display_options=True)
		self.navigationWidget       = widgets.NavigationWidget(self.hcs_controller.navigationController,self.hcs_controller.slidePositionController,widget_configuration=default_well_plate)
		self.dacControlWidget       = widgets.DACControWidget(self.microcontroller)
		self.autofocusWidget        = widgets.AutoFocusWidget(self.hcs_controller.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.hcs_controller.streamHandler,self.hcs_controller.imageSaver)
		self.multiPointWidget       = widgets.MultiPointWidget(self.hcs_controller.multipointController,self.hcs_controller.configurationManager)
		self.navigationViewer       = widgets.NavigationViewer(sample=default_well_plate)

		self.recordTabWidget = QTabWidget()
		#self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
		self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")

		clear_history_button=QPushButton("clear history")
		clear_history_button.clicked.connect(self.navigationViewer.clear_imaged_positions)

		wellplate_selector=QComboBox()
		wellplate_types_int=[k for k in WELLPLATE_FORMATS.keys()]
		wellplate_types_str=[f"{i} well plate" for i in wellplate_types_int]
		wellplate_selector.addItems(wellplate_types_str)
		# disable 6 and 24 well wellplates, because the images displaying them are missing
		for wpt in [0,2]:
			item=wellplate_selector.model().item(wpt)
			item.setFlags(item.flags() & ~Qt.ItemIsEnabled) # type: ignore
		wellplate_selector.setCurrentIndex(wellplate_types_str.index(default_well_plate))
		wellplate_selector.currentIndexChanged.connect(lambda wellplate_type_index:setattr(MUTABLE_MACHINE_CONFIG,"WELLPLATE_FORMAT",wellplate_types_int[wellplate_type_index]))
 
		wellplate_overview_header=QHBoxLayout()
		wellplate_overview_header.addWidget(QLabel("wellplate overview"))
		wellplate_overview_header.addWidget(clear_history_button)
		wellplate_overview_header.addWidget(QLabel("change plate type:"))
		wellplate_overview_header.addWidget(wellplate_selector)

		navigationviewer_widget=QVBoxLayout()
		navigationviewer_widget.addLayout(wellplate_overview_header)
		navigationviewer_widget.addWidget(self.navigationViewer)

		# layout widgets
		layout = QVBoxLayout() #layout = QStackedLayout()
		#layout.addWidget(self.cameraSettingWidget)
		layout.addWidget(self.liveControlWidget)
		layout.addWidget(self.navigationWidget)
		if MACHINE_DISPLAY_CONFIG.SHOW_DAC_CONTROL:
			layout.addWidget(self.dacControlWidget)
		layout.addWidget(self.autofocusWidget)
		layout.addWidget(self.recordTabWidget)
		layout.addLayout(navigationviewer_widget)
		layout.addStretch()
		
		# transfer the layout to the central widget
		self.centralWidget:QWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())
		
		if MACHINE_DISPLAY_CONFIG.SINGLE_WINDOW:
			dock_display = dock.Dock('Image Display', autoOrientation = False)
			dock_display.showTitleBar()
			dock_display.addWidget(self.imageDisplayTabs)
			dock_display.setStretch(x=100,y=100)
			dock_wellSelection = dock.Dock('Well Selector', autoOrientation = False)
			dock_wellSelection.showTitleBar()
			dock_wellSelection.addWidget(self.wellSelectionWidget)
			dock_wellSelection.setFixedHeight(dock_wellSelection.minimumSizeHint().height())
			dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
			# dock_controlPanel.showTitleBar()
			dock_controlPanel.addWidget(self.centralWidget)
			dock_controlPanel.setStretch(x=1,y=None)
			dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())
			main_dockArea = dock.DockArea()
			main_dockArea.addDock(dock_display)
			main_dockArea.addDock(dock_wellSelection,'bottom')
			main_dockArea.addDock(dock_controlPanel,'right')
			self.setCentralWidget(main_dockArea)
			desktopWidget = QDesktopWidget()
			height_min = int(0.9*desktopWidget.height())
			width_min = int(0.96*desktopWidget.width())
			self.setMinimumSize(width_min,height_min)
		else:
			self.setCentralWidget(self.centralWidget)
			self.tabbedImageDisplayWindow = QMainWindow()
			self.tabbedImageDisplayWindow.setCentralWidget(self.imageDisplayTabs)
			self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint) # type: ignore
			self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint) # type: ignore
			desktopWidget = QDesktopWidget()
			width = int(0.96*desktopWidget.height())
			height = width
			self.tabbedImageDisplayWindow.setFixedSize(width,height)
			self.tabbedImageDisplayWindow.show()

		# make connections
		self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
		self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
		self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
		self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image) # may connect streamHandler directly to imageDisplayWindow
		self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x)))
		self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x)))
		self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x)))
		self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)
		self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
		self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)

		self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
		self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
		self.liveControlWidget.update_camera_settings()

		self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
		self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
		self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
		self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
		self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)

		self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
		self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)

		self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)

	@TypecheckFunction
	def closeEvent(self, event:QEvent):
		
		# move the objective to a defined position upon exit
		self.navigationController.move_x(0.1) # temporary bug fix - move_x needs to be called before move_x_to if the stage has been moved by the joystick
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		self.navigationController.move_x_to(30.0)
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		self.navigationController.move_y(0.1) # temporary bug fix - move_y needs to be called before move_y_to if the stage has been moved by the joystick
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		self.navigationController.move_y_to(30.0)
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		event.accept()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		if not MACHINE_DISPLAY_CONFIG.SINGLE_WINDOW:
			self.imageDisplayWindow.close()
			self.imageArrayDisplayWindow.close()
			self.tabbedImageDisplayWindow.close()
		self.microcontroller.close()
