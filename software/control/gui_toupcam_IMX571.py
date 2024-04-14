# set QT_API environment variable
import os 
import sys
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.widgets as widgets
import control.camera_toupcam as camera
import control.core as core
import control.microcontroller as microcontroller
from control._def import *

import pyqtgraph.dockarea as dock
SINGLE_WINDOW = True # set to False if use separate windows for display and control

import time

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, is_simulation = False, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load window
		if ENABLE_TRACKING:
			self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True,show_LUT=True,autoLevels=True)
			self.imageDisplayWindow.show_ROI_selector()
		else:
			self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True,show_LUT=True,autoLevels=True)
		self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow() 
		# self.imageDisplayWindow.show()
		# self.imageArrayDisplayWindow.show()

		# image display windows
		self.imageDisplayTabs = QTabWidget()
		self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
		self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

		# load objects
		if is_simulation:
			self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			self.microcontroller = microcontroller.Microcontroller_Simulation()
		else:
			self.camera = camera.Camera(resolution=(6224,4168),rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			#self.camera = camera.Camera(resolution=(3104,2084))
			#self.camera = camera.Camera(resolution=(2064,1386))
			# 6224 x 4168
			# 3104 x 2084
			# 2064 x 1386
			try:
				self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)
			except:
				print('! Microcontroller not detected, using simulated microcontroller !')
				self.microcontroller = microcontroller.Microcontroller_Simulation()

		# reset the MCU
		self.microcontroller.reset()

		'''
		# reinitialize motor drivers and DAC (in particular for V2.1 driver board where PG is not functional)
		self.microcontroller.initialize_drivers()
		'''

		# configure the actuators
		self.microcontroller.configure_actuators()

		self.configurationManager = core.ConfigurationManager('./channel_configurations.xml')
		self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
		self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController = core.NavigationController(self.microcontroller)
		self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
		self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager)
		if ENABLE_TRACKING:
			self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
		self.imageSaver = core.ImageSaver(image_format=Acquisition.IMAGE_FORMAT)
		self.imageDisplay = core.ImageDisplay()
		self.navigationViewer = core.NavigationViewer()

		# homing
		'''
		self.navigationController.home_y()
		t0 = time.time()
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 10:
				print('y homing timeout, the program will exit')
				sys.exit(1)
		
		self.navigationController.home_x()
		t0 = time.time()
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 10:
				print('x homing timeout, the program will exit')
				sys.exit(1)
		'''
		'''
		self.slidePositionController.move_to_slide_scanning_position()
		while self.slidePositionController.slide_scanning_position_reached == False:
			time.sleep(0.005)
		print('homing finished')

		# retract the objective
		self.navigationController.home_z()
		# wait for the operation to finish
		t0 = time.time()
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 10:
				print('z homing timeout, the program will exit')
				sys.exit(1)
		print('objective retracted')
		self.navigationController.move_z(DEFAULT_Z_POS_MM)

		self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
		self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
		self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
		self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
		self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)
		'''

		# open the camera
		# camera start streaming
		self.camera.open()
		self.camera.set_gain_mode('HCG')
		# self.camera.camera.put_Roi(3112,2084,2048,2048)
		# self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
		# self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
		self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()
		if ENABLE_STROBE_OUTPUT:
			self.camera.set_line3_to_exposure_active()

		# load widgets
		self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False,include_camera_temperature_setting=True)
		self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_trigger_options=True,show_display_options=True,show_autolevel=True,autolevel=True)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='malaria')
		self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
		self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
		if ENABLE_TRACKING:
			self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
		self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)

		self.recordTabWidget = QTabWidget()
		if ENABLE_TRACKING:
			self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
		self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")
		self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")

		# layout widgets
		layout = QVBoxLayout() #layout = QStackedLayout()
		layout.addWidget(self.cameraSettingWidget)
		layout.addWidget(self.liveControlWidget)
		layout.addWidget(self.navigationWidget)
		if SHOW_DAC_CONTROL:
			layout.addWidget(self.dacControlWidget)
		layout.addWidget(self.autofocusWidget)
		layout.addWidget(self.recordTabWidget)
		layout.addWidget(self.navigationViewer)
		layout.addStretch()
		
		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		# self.centralWidget.setFixedSize(self.centralWidget.minimumSize())
		# self.centralWidget.setFixedWidth(self.centralWidget.minimumWidth())
		# self.centralWidget.setMaximumWidth(self.centralWidget.minimumWidth())
		self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())
		
		if SINGLE_WINDOW:
			dock_display = dock.Dock('Image Display', autoOrientation = False)
			dock_display.showTitleBar()
			dock_display.addWidget(self.imageDisplayTabs)
			dock_display.setStretch(x=100,y=None)
			dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
			# dock_controlPanel.showTitleBar()
			dock_controlPanel.addWidget(self.centralWidget)
			dock_controlPanel.setStretch(x=1,y=None)
			dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())
			main_dockArea = dock.DockArea()
			main_dockArea.addDock(dock_display)
			main_dockArea.addDock(dock_controlPanel,'right')
			self.setCentralWidget(main_dockArea)
			desktopWidget = QDesktopWidget()
			height_min = int(0.9*desktopWidget.height())
			width_min =int(0.96*desktopWidget.width())
			self.setMinimumSize(width_min,height_min)
		else:
			self.setCentralWidget(self.centralWidget)
			self.tabbedImageDisplayWindow = QMainWindow()
			self.tabbedImageDisplayWindow.setCentralWidget(self.imageDisplayTabs)
			self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
			self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
			desktopWidget = QDesktopWidget()
			width = 0.96*desktopWidget.height()
			height = width
			self.tabbedImageDisplayWindow.setFixedSize(width,height)
			self.tabbedImageDisplayWindow.show()

		# make connections
		self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
		self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
		self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
		# self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
		self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image) # may connect streamHandler directly to imageDisplayWindow
		self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)
		if ENABLE_TRACKING:
			self.navigationController.signal_joystick_button_pressed.connect(self.trackingControlWidget.slot_joystick_button_pressed)
		else:
			self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)
		self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
		self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)
		self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
		self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
		self.liveControlWidget.update_camera_settings()
		self.liveControlWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel)

		self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
		self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
		self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
		self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
		self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)
		self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
		self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.navigationController.home()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		if not SINGLE_WINDOW:
			self.imageDisplayWindow.close()
			self.imageArrayDisplayWindow.close()
			self.tabbedImageDisplayWindow.close()
		self.microcontroller.close()
