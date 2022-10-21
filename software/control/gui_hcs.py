# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"

# qt libraries
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMainWindow, QTabWidget, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDesktopWidget

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
from control._def import *

import pyqtgraph.dockarea as dock

SINGLE_WINDOW = True # set to False if use separate windows for display and control

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load window
		self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
		self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow() 
		# self.imageDisplayWindow.show()
		# self.imageArrayDisplayWindow.show()

		# image display windows
		self.imageDisplayTabs = QTabWidget()
		self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
		self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

		# load objects
		try:
			self.camera = camera.Camera(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			self.camera.open()
		except Exception as e:
			print('! camera not detected, using simulated camera !')
			raise e
		self.microcontroller:microcontroller.Microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)

		# reset the MCU
		self.microcontroller.reset()
		
		# configure the actuators
		self.microcontroller.configure_actuators()
			
		self.configurationManager:core.ConfigurationManager = core.ConfigurationManager(filename='./channel_configurations.xml')
		self.streamHandler:core.StreamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
		self.liveController:core.LiveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController:core.NavigationController = core.NavigationController(self.microcontroller)
		self.slidePositionController:core.SlidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
		self.wellSelectionWidget = widgets.WellSelectionWidget(WELLPLATE_FORMAT)
		self.autofocusController:core.AutoFocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.navigationViewer:core.NavigationViewer = core.NavigationViewer(sample=str(WELLPLATE_FORMAT)+' well plate')		
		self.scanCoordinates:core.ScanCoordinates = core.ScanCoordinates(self.wellSelectionWidget,self.navigationViewer)
		self.multipointController:core.MultiPointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates)
		self.imageSaver:core.ImageSaver = core.ImageSaver()
		self.imageDisplay:core.ImageDisplay = core.ImageDisplay()

		if HOMING_ENABLED_Z:
			# retract the objective
			self.navigationController.home_z()
			# wait for the operation to finish
			self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005, timeout_msg='z homing timeout, the program will exit')

			print('objective retracted')

		if HOMING_ENABLED_Z and HOMING_ENABLED_X and HOMING_ENABLED_Y:
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

			self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
			self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
			self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
			self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
			self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

		if HOMING_ENABLED_Z:
			# move the objective back
			self.navigationController.move_z(DEFAULT_Z_POS_MM)
			# wait for the operation to finish
			self.microcontroller.wait_till_operation_is_completed(10, time_step=0.005, timeout_msg='z return timeout, the program will exit')
		
		# open the camera
		# camera start streaming
		# self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
		# self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
		self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()

		# load widgets
		self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
		self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='384 well plate')
		self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
		self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
		self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)

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
		wellplate_selector.setCurrentIndex(wellplate_type_names.index(f"{WELLPLATE_FORMAT} well plate"))
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
		if SHOW_DAC_CONTROL:
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

	def set_wellplate_type(self,wellplate_type:str):
		self.navigationViewer.set_wellplate_type(wellplate_type)
		self.wellSelectionWidget.set_wellplate_type(wellplate_type)

	def closeEvent(self, event):
		
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
