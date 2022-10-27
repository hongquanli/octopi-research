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

SINGLE_WINDOW = True # set to False if use separate windows for display and control

class HCSController():
	@TypecheckFunction
	def __init__(self,well_selection_widget:widgets.WellSelectionWidget):
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
		self.navigationViewer:        core.NavigationViewer        = core.NavigationViewer(sample=str(MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT)+' well plate')
		self.scanCoordinates:         core.ScanCoordinates         = core.ScanCoordinates(well_selection_widget,self.navigationViewer)
		self.multipointController:    core.MultiPointController    = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates)
		self.imageSaver:              core.ImageSaver              = core.ImageSaver()
		self.imageDisplay:            core.ImageDisplay            = core.ImageDisplay()

		if MACHINE_CONFIG.HOMING_ENABLED_Z:
			# retract the objective
			self.navigationController.home_z()
			# wait for the operation to finish
			self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005, timeout_msg='z homing timeout, the program will exit')

			print('objective retracted')

			if MACHINE_CONFIG.HOMING_ENABLED_Z and MACHINE_CONFIG.HOMING_ENABLED_X and MACHINE_CONFIG.HOMING_ENABLED_Y:
				# self.navigationController.set_x_limit_pos_mm(100)
				# self.navigationController.set_x_limit_neg_mm(-100)
				# self.navigationController.set_y_limit_pos_mm(100)
				# self.navigationController.set_y_limit_neg_mm(-100)
				# self.navigationController.home_xy() 
				# for the new design, need to home y before home x; x also needs to be at > + 10 mm when homing y
				self.navigationController.move_x(12)
				self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005)
				
				self.navigationController.home_y()
				self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005, timeout_msg='y homing timeout, the program will exit')
				
				self.navigationController.home_x()
				self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005, timeout_msg='x homing timeout, the program will exit')
		
				print('xy homing completed')

				# move to (20 mm, 20 mm)
				self.navigationController.move_x(20)
				self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005)
				self.navigationController.move_y(20)
				self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005)

				self.navigationController.set_x_limit_pos_mm(MACHINE_CONFIG.SOFTWARE_POS_LIMIT.X_POSITIVE)
				self.navigationController.set_x_limit_neg_mm(MACHINE_CONFIG.SOFTWARE_POS_LIMIT.X_NEGATIVE)
				self.navigationController.set_y_limit_pos_mm(MACHINE_CONFIG.SOFTWARE_POS_LIMIT.Y_POSITIVE)
				self.navigationController.set_y_limit_neg_mm(MACHINE_CONFIG.SOFTWARE_POS_LIMIT.Y_NEGATIVE)
				self.navigationController.set_z_limit_pos_mm(MACHINE_CONFIG.SOFTWARE_POS_LIMIT.Z_POSITIVE)

			# move the objective back
			self.navigationController.move_z(MACHINE_CONFIG.DEFAULT_Z_POS_MM)
			# wait for the operation to finish
			self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005, timeout_msg='z return timeout, the program will exit')

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load window
		self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
		self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow()

		# image display windows
		self.imageDisplayTabs = QTabWidget()
		self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
		self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

		# load one widget that is used by a controller
		self.wellSelectionWidget = widgets.WellSelectionWidget(MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT)

		self.hcs_controller=HCSController(self.wellSelectionWidget)
		
		self.camera=self.hcs_controller.camera
		self.microcontroller=self.hcs_controller.microcontroller
			
		self.configurationManager:    core.ConfigurationManager    = self.hcs_controller.configurationManager
		self.streamHandler:           core.StreamHandler           = self.hcs_controller.streamHandler
		self.liveController:          core.LiveController          = self.hcs_controller.liveController
		self.navigationController:    core.NavigationController    = self.hcs_controller.navigationController
		self.slidePositionController: core.SlidePositionController = self.hcs_controller.slidePositionController
		self.autofocusController:     core.AutoFocusController     = self.hcs_controller.autofocusController
		self.navigationViewer:        core.NavigationViewer        = self.hcs_controller.navigationViewer
		self.scanCoordinates:         core.ScanCoordinates         = self.hcs_controller.scanCoordinates
		self.multipointController:    core.MultiPointController    = self.hcs_controller.multipointController
		self.imageSaver:              core.ImageSaver              = self.hcs_controller.imageSaver
		self.imageDisplay:            core.ImageDisplay            = self.hcs_controller.imageDisplay
		
		# open the camera
		self.camera.set_software_triggered_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()

		# load widgets
		self.cameraSettingWidget    = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
		self.liveControlWidget      = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True)
		self.navigationWidget       = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='384 well plate')
		self.dacControlWidget       = widgets.DACControWidget(self.microcontroller)
		self.autofocusWidget        = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
		self.multiPointWidget       = widgets.MultiPointWidget(self.multipointController,self.configurationManager)

		self.recordTabWidget = QTabWidget()
		#self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
		self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")

		clear_history_button=QPushButton("clear history")
		clear_history_button.clicked.connect(self.navigationViewer.clear_imaged_positions)

		wellplate_selector=QComboBox()
		wellplate_type_names=[f"{i} well plate" for i in [6,12,24,96,384]]
		wellplate_selector.addItems(wellplate_type_names)
		# disable 6 and 24 well wellplates, because the images displaying them are missing
		for wpt in [0,2]:
			item=wellplate_selector.model().item(wpt)
			item.setFlags(item.flags() & ~Qt.ItemIsEnabled) # type: ignore
		wellplate_selector.setCurrentIndex(wellplate_type_names.index(f"{MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT} well plate"))
		wellplate_selector.currentIndexChanged.connect(lambda wellplate_type: self.set_wellplate_type(wellplate_type_names[wellplate_type]))
 
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
		# self.centralWidget.setFixedSize(self.centralWidget.minimumSize())
		# self.centralWidget.setFixedWidth(self.centralWidget.minimumWidth())
		# self.centralWidget.setMaximumWidth(self.centralWidget.minimumWidth())
		self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())
		
		if SINGLE_WINDOW:
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
	def set_wellplate_type(self,wellplate_type:str):
		self.navigationViewer.set_wellplate_type(wellplate_type)
		self.wellSelectionWidget.set_wellplate_type(wellplate_type)

	@TypecheckFunction
	def closeEvent(self, event:QEvent):
		
		# move the objective to a defined position upon exit
		self.navigationController.move_x(0.1) # temporary bug fix - move_x needs to be called before move_x_to if the stage has been moved by the joystick
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		self.navigationController.move_x_to(30)
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		self.navigationController.move_y(0.1) # temporary bug fix - move_y needs to be called before move_y_to if the stage has been moved by the joystick
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		self.navigationController.move_y_to(30)
		self.microcontroller.wait_till_operation_is_completed(5, 0.005)

		event.accept()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		if not SINGLE_WINDOW:
			self.imageDisplayWindow.close()
			self.imageArrayDisplayWindow.close()
			self.tabbedImageDisplayWindow.close()
		self.microcontroller.close()
