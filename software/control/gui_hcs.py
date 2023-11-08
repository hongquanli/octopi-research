# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
from control._def import *

if SUPPORT_LASER_AUTOFOCUS:
	import control.core_displacement_measurement as core_displacement_measurement

import pyqtgraph.dockarea as dock
import time

SINGLE_WINDOW = True # set to False if use separate windows for display and control

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, is_simulation = False, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load window
		if ENABLE_TRACKING:
			self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
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
			if SUPPORT_LASER_AUTOFOCUS:
				self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
				self.camera_focus = camera.Camera_Simulation()
			else:
				self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			self.microcontroller = microcontroller.Microcontroller_Simulation()
		else:
			try:
				if SUPPORT_LASER_AUTOFOCUS:
					sn_camera_main = camera.get_sn_by_model(MAIN_CAMERA_MODEL)
					sn_camera_focus = camera.get_sn_by_model(FOCUS_CAMEARA_MODEL)
					self.camera = camera.Camera(sn=sn_camera_main,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
					self.camera.open()
					self.camera_focus = camera.Camera(sn=sn_camera_focus)
					self.camera_focus.open()
				else:
					self.camera = camera.Camera(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
					self.camera.open()
			except:
				if SUPPORT_LASER_AUTOFOCUS:
					self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
					self.camera.open()
					self.camera_focus = camera.Camera_Simulation()
					self.camera_focus.open()
				else:
					self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
					self.camera.open()
				print('! camera not detected, using simulated camera !')
			self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION,sn='12769610')

		# reset the MCU
		self.microcontroller.reset()

		# reinitialize motor drivers and DAC (in particular for V2.1 driver board where PG is not functional)
		self.microcontroller.initialize_drivers()
		
		# configure the actuators
		self.microcontroller.configure_actuators()
			
		self.configurationManager = core.ConfigurationManager(filename='./channel_configurations.xml')
		self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
		self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController = core.NavigationController(self.microcontroller)
		self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController,is_for_wellplate=True)
		self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.scanCoordinates = core.ScanCoordinates()
		self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
		if ENABLE_TRACKING:
			self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
		self.imageSaver = core.ImageSaver()
		self.imageDisplay = core.ImageDisplay()
		self.navigationViewer = core.NavigationViewer(sample=str(WELLPLATE_FORMAT)+' well plate')

		'''
		if HOMING_ENABLED_Z:
			# retract the objective
			self.navigationController.home_z()
			# wait for the operation to finish
			t0 = time.time()
			while self.microcontroller.is_busy():
				time.sleep(0.005)
				if time.time() - t0 > 10:
					print('z homing timeout, the program will exit')
					exit()
			print('objective retracted')

		if HOMING_ENABLED_Z and HOMING_ENABLED_X and HOMING_ENABLED_Y:
			# self.navigationController.set_x_limit_pos_mm(100)
			# self.navigationController.set_x_limit_neg_mm(-100)
			# self.navigationController.set_y_limit_pos_mm(100)
			# self.navigationController.set_y_limit_neg_mm(-100)
			# self.navigationController.home_xy() 
			# for the new design, need to home y before home x; x also needs to be at > + 10 mm when homing y
			self.navigationController.move_x(12)
			while self.microcontroller.is_busy(): # to do, add a blocking option move_x()
				time.sleep(0.005)
			
			self.navigationController.home_y()
			t0 = time.time()
			while self.microcontroller.is_busy():
				time.sleep(0.005)
				if time.time() - t0 > 10:
					print('y homing timeout, the program will exit')
					exit()
			
			self.navigationController.home_x()
			t0 = time.time()
			while self.microcontroller.is_busy():
				time.sleep(0.005)
				if time.time() - t0 > 10:
					print('x homing timeout, the program will exit')
					exit()
	
			print('xy homing completed')

			# move to (20 mm, 20 mm)
			self.navigationController.move_x(20)
			while self.microcontroller.is_busy():
				time.sleep(0.005)
			self.navigationController.move_y(20)
			while self.microcontroller.is_busy():
				time.sleep(0.005)

			self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
			self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
			self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
			self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
			self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

		if HOMING_ENABLED_Z:
			# move the objective back
			self.navigationController.move_z(DEFAULT_Z_POS_MM)
			# wait for the operation to finish
			t0 = time.time() 
			while self.microcontroller.is_busy():
				time.sleep(0.005)
				if time.time() - t0 > 5:
					print('z return timeout, the program will exit')
					exit()
		'''

		# retract the objective
		self.navigationController.home_z()
		# wait for the operation to finish
		t0 = time.time()
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 10:
				print('z homing timeout, the program will exit')
				exit()
		print('objective retracted')
		self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

		# home XY, set zero and set software limit
		print('home xy')
		timestamp_start = time.time()
		# x needs to be at > + 20 mm when homing y
		self.navigationController.move_x(20) # to-do: add blocking code
		while self.microcontroller.is_busy():
			time.sleep(0.005)
		# home y
		self.navigationController.home_y()
		t0 = time.time()
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 10:
				print('y homing timeout, the program will exit')
				exit()
		self.navigationController.zero_y()
		# home x
		self.navigationController.home_x()
		t0 = time.time()
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 10:
				print('y homing timeout, the program will exit')
				exit()
		self.navigationController.zero_x()
		self.slidePositionController.homing_done = True

		# move to scanning position
		self.navigationController.move_x(20)
		while self.microcontroller.is_busy():
			time.sleep(0.005)
		self.navigationController.move_y(20)
		while self.microcontroller.is_busy():
			time.sleep(0.005)

		# move z
		self.navigationController.move_z_to(DEFAULT_Z_POS_MM)
		# wait for the operation to finish
		t0 = time.time() 
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 5:
				print('z return timeout, the program will exit')
				exit()
		
		# open the camera
		# camera start streaming
		# self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
		# self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
		self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()

		# load widgets
		self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
		self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True,show_autolevel=True,autolevel=True)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='384 well plate')
		self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
		self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
		if ENABLE_TRACKING:
			self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
		self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)
		self.multiPointWidget2 = widgets.MultiPointWidget2(self.navigationController,self.navigationViewer,self.multipointController,self.configurationManager)

		self.recordTabWidget = QTabWidget()
		if ENABLE_TRACKING:
			self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
		#self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
		self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint (Wellplate)")
		self.wellSelectionWidget = widgets.WellSelectionWidget(WELLPLATE_FORMAT)
		self.scanCoordinates.add_well_selector(self.wellSelectionWidget)

		if ENABLE_FLEXIBLE_MULTIPOINT:
			self.recordTabWidget.addTab(self.multiPointWidget2, "Flexible Multipoint")

		# layout widgets
		layout = QVBoxLayout() #layout = QStackedLayout()
		#layout.addWidget(self.cameraSettingWidget)
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
			height_min = 0.9*desktopWidget.height()
			width_min = 0.96*desktopWidget.width()
			self.setMinimumSize(int(width_min),int(height_min))
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
		self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x)))
		self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x)))
		self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x)))
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

		# load vs scan position switching
		self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
		self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
		self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
		self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
		self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)

		# display the FOV in the viewer
		self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
		self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)

		# (double) click to move to a well
		self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)

		# camera
		self.camera.set_callback(self.streamHandler.on_new_frame)

		# laser autofocus
		if SUPPORT_LASER_AUTOFOCUS:

			# controllers
			self.configurationManager_focus_camera = core.ConfigurationManager(filename='./focus_camera_configurations.xml')
			self.streamHandler_focus_camera = core.StreamHandler()
			self.liveController_focus_camera = core.LiveController(self.camera_focus,self.microcontroller,self.configurationManager_focus_camera,control_illumination=False,for_displacement_measurement=True)
			self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
			self.imageDisplayWindow_focus = core.ImageDisplayWindow(draw_crosshairs=True)
			self.displacementMeasurementController = core_displacement_measurement.DisplacementMeasurementController()
			self.laserAutofocusController = core.LaserAutofocusController(self.microcontroller,self.camera_focus,self.liveController_focus_camera,self.navigationController,has_two_interfaces=HAS_TWO_INTERFACES,use_glass_top=USE_GLASS_TOP)

			# camera
			self.camera_focus.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
			self.camera_focus.set_callback(self.streamHandler_focus_camera.on_new_frame)
			self.camera_focus.enable_callback()
			self.camera_focus.start_streaming()

			# widgets
			self.cameraSettingWidget_focus_camera = widgets.CameraSettingsWidget(self.camera_focus,include_gain_exposure_time=False)
			self.liveControlWidget_focus_camera = widgets.LiveControlWidget(self.streamHandler_focus_camera,self.liveController_focus_camera,self.configurationManager_focus_camera,show_display_options=True)
			self.waveformDisplay = widgets.WaveformDisplay(N=1000,include_x=True,include_y=False)
			self.displacementMeasurementWidget = widgets.DisplacementMeasurementWidget(self.displacementMeasurementController,self.waveformDisplay)
			self.laserAutofocusControlWidget = widgets.LaserAutofocusControlWidget(self.laserAutofocusController)

			self.recordTabWidget.addTab(self.laserAutofocusControlWidget, "Laser Autofocus Control")

			dock_laserfocus_image_display = dock.Dock('Focus Camera Image Display', autoOrientation = False)
			dock_laserfocus_image_display.showTitleBar()
			dock_laserfocus_image_display.addWidget(self.imageDisplayWindow_focus.widget)
			dock_laserfocus_image_display.setStretch(x=100,y=100)

			dock_laserfocus_liveController = dock.Dock('Focus Camera Controller', autoOrientation = False)
			dock_laserfocus_liveController.showTitleBar()
			dock_laserfocus_liveController.addWidget(self.liveControlWidget_focus_camera)
			dock_laserfocus_liveController.setStretch(x=100,y=100)
			# dock_laserfocus_liveController.setFixedHeight(self.liveControlWidget_focus_camera.minimumSizeHint().height())
			dock_laserfocus_liveController.setFixedWidth(self.liveControlWidget_focus_camera.minimumSizeHint().width())

			dock_waveform = dock.Dock('Displacement Measurement', autoOrientation = False)
			dock_waveform.showTitleBar()
			dock_waveform.addWidget(self.waveformDisplay)
			dock_waveform.setStretch(x=100,y=40)

			dock_displayMeasurement =  dock.Dock('Displacement Measurement Control', autoOrientation = False)
			dock_displayMeasurement.showTitleBar()
			dock_displayMeasurement.addWidget(self.displacementMeasurementWidget)
			dock_displayMeasurement.setStretch(x=100,y=40)
			dock_displayMeasurement.setFixedWidth(self.displacementMeasurementWidget.minimumSizeHint().width())

			laserfocus_dockArea = dock.DockArea()
			laserfocus_dockArea.addDock(dock_laserfocus_image_display)
			laserfocus_dockArea.addDock(dock_laserfocus_liveController,'right',relativeTo=dock_laserfocus_image_display)
			if SHOW_LEGACY_DISPLACEMENT_MEASUREMENT_WINDOWS:
				laserfocus_dockArea.addDock(dock_waveform,'bottom',relativeTo=dock_laserfocus_liveController)
				laserfocus_dockArea.addDock(dock_displayMeasurement,'bottom',relativeTo=dock_waveform)

			# self.imageDisplayWindow_focus.widget
			self.imageDisplayTabs.addTab(laserfocus_dockArea,"Laser-based Focus")

			# connections
			self.liveControlWidget_focus_camera.signal_newExposureTime.connect(self.cameraSettingWidget_focus_camera.set_exposure_time)
			self.liveControlWidget_focus_camera.signal_newAnalogGain.connect(self.cameraSettingWidget_focus_camera.set_analog_gain)
			self.liveControlWidget_focus_camera.update_camera_settings()

			self.streamHandler_focus_camera.signal_new_frame_received.connect(self.liveController_focus_camera.on_new_frame)
			self.streamHandler_focus_camera.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

			self.streamHandler_focus_camera.image_to_display.connect(self.displacementMeasurementController.update_measurement)
			self.displacementMeasurementController.signal_plots.connect(self.waveformDisplay.plot)
			self.displacementMeasurementController.signal_readings.connect(self.displacementMeasurementWidget.display_readings)
			self.laserAutofocusController.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

		if INCLUDE_FLUIDICS:

			import fluidics.controllers as controllers_fluidics
			import fluidics.widgets as widgets_fluidics

			is_simulation=False
			log_measurements=False
			debug_mode=False

			if(is_simulation):
				self.teensy41 = controllers_fluidics.Microcontroller_Simulation()
			else:
				serial_number = '9037670'
				self.teensy41 = controllers_fluidics.Microcontroller(serial_number)
				print("Connected to fluidics teensy")
			self.fluidController = controllers_fluidics.FluidController(self.teensy41,log_measurements)
			self.logger = controllers_fluidics.Logger()

			# load widgets
			self.chillerWidget = widgets_fluidics.ChillerWidget(self.fluidController)
			self.preUseCheckWidget = widgets_fluidics.PreUseCheckWidget(self.fluidController)
			self.logWidget = QListWidget()
			# self.triggerWidget = widgets_fluidics.TriggerWidget(self.triggerController)
			self.sequenceWidget = widgets_fluidics.SequenceWidget(self.fluidController)
			self.manualFlushWidget = widgets_fluidics.ManualFlushWidget(self.fluidController)
			self.manualControlWidget = widgets_fluidics.ManualControlWidget(self.fluidController)
			self.microcontrollerStateDisplayWidget = widgets_fluidics.MicrocontrollerStateDisplayWidget()

			self.arbitraryCommandWidget = widgets_fluidics.ArbitraryCommandWidget(self.fluidController)

			# disable preuse check before it is fully implemented
			# self.preUseCheckWidget.setEnabled(False)

			# layout widgets (linear)
			'''
			layout = QGridLayout()
			layout.addWidget(QLabel('Chiller'),0,0)
			layout.addWidget(self.chillerWidget,0,1)
			layout.addWidget(QLabel('Pre-Use Check'),1,0)
			layout.addWidget(self.preUseCheckWidget,1,1)
			layout.addWidget(QLabel('Sequences'),4,0)
			layout.addWidget(self.sequenceWidget,4,1)
			# layout.addWidget(self.triggerWidget,8,0)
			layout.addWidget(QLabel('Manual Flush'),9,0) # (End of Experiment)
			layout.addWidget(self.manualFlushWidget,9,1)
			layout.addWidget(self.logWidget,10,0,1,2)
			'''

			# layout widgets (using tabs)  - start
			tab1_layout = QGridLayout()
			# tab1_layout.addWidget(QLabel('Chiller'),0,0)
			# tab1_layout.addWidget(self.chillerWidget,0,1)
			tab1_layout.addWidget(QLabel('Pre-Use Check'),1,0)
			tab1_layout.addWidget(self.preUseCheckWidget,1,1)
			tab1_layout.addWidget(QLabel('Sequences'),4,0)
			tab1_layout.addWidget(self.sequenceWidget,4,1)
			tab1_widget = QWidget()
			
			tab1_widget.setLayout(tab1_layout)
			tab2_widget = self.manualControlWidget

			self.tabWidget = QTabWidget()
			self.tabWidget.addTab(tab1_widget, "Run Experiments")
			self.tabWidget.addTab(tab2_widget, "Settings and Manual Control")
			
			layout = QGridLayout()
			layout.addWidget(self.tabWidget,0,0)

			# layout.addWidget(self.logWidget,1,0)
			# @@@ the code below is to put the ListWidget into a frame - code may be improved
			self.framedLogWidget = QFrame()
			framedLogWidget_layout = QHBoxLayout() 
			framedLogWidget_layout.addWidget(self.logWidget)
			self.framedLogWidget.setLayout(framedLogWidget_layout)
			self.framedLogWidget.setFrameStyle(QFrame.Panel | QFrame.Raised)
			'''
			mcuStateDisplay = QGridLayout()
			mcuStateDisplay.addWidget(QLabel('Controller State'),0,0)
			mcuStateDisplay.addWidget(self.microcontrollerStateDisplayWidget,0,1)
			layout.addLayout(mcuStateDisplay,1,0)
			'''
			layout.addWidget(self.microcontrollerStateDisplayWidget,1,0)
			if debug_mode:
				layout.addWidget(self.arbitraryCommandWidget,2,0)
			layout.addWidget(self.framedLogWidget,3,0)
			# layout widgets (using tabs)  - end

			# connecting signals to slots
			# @@@ to do: addItem and scrollToBottom need to happen in sequence - create a function for this
			self.chillerWidget.log_message.connect(self.logWidget.addItem)
			self.preUseCheckWidget.log_message.connect(self.logWidget.addItem)
			self.fluidController.log_message.connect(self.logWidget.addItem)
			# self.triggerController.log_message.connect(self.logWidget.addItem)
			self.sequenceWidget.log_message.connect(self.logWidget.addItem)
			self.manualFlushWidget.log_message.connect(self.logWidget.addItem)
			self.manualControlWidget.log_message.connect(self.logWidget.addItem)

			self.chillerWidget.log_message.connect(self.logWidget.scrollToBottom)
			self.preUseCheckWidget.log_message.connect(self.logWidget.scrollToBottom)
			self.fluidController.log_message.connect(self.logWidget.scrollToBottom)
			# self.triggerController.log_message.connect(self.logWidget.scrollToBottom)
			self.sequenceWidget.log_message.connect(self.logWidget.scrollToBottom)
			self.manualFlushWidget.log_message.connect(self.logWidget.scrollToBottom)
			self.manualControlWidget.log_message.connect(self.logWidget.scrollToBottom)
			
			self.chillerWidget.log_message.connect(self.logger.log)
			self.preUseCheckWidget.log_message.connect(self.logger.log)
			self.fluidController.log_message.connect(self.logger.log)
			# self.triggerController.log_message.connect(self.logger.log)
			self.sequenceWidget.log_message.connect(self.logger.log)
			self.manualFlushWidget.log_message.connect(self.logger.log)
			self.manualControlWidget.log_message.connect(self.logger.log)

			self.fluidController.signal_log_highlight_current_item.connect(self.highlight_current_log_item)

			self.sequenceWidget.signal_disable_manualControlWidget.connect(self.disableManualControlWidget)
			self.sequenceWidget.signal_enable_manualControlWidget.connect(self.enableManualControlWidget)
			self.manualControlWidget.signal_disable_userinterface.connect(self.disableSequenceWidget)
			self.manualControlWidget.signal_enable_userinterface.connect(self.enableSequenceWidget)
			self.preUseCheckWidget.signal_disable_manualControlWidget.connect(self.disableManualControlWidget)
			self.preUseCheckWidget.signal_disable_sequenceWidget.connect(self.disableSequenceWidget)
			self.fluidController.signal_preuse_check_result.connect(self.preUseCheckWidget.show_preuse_check_result)

			self.fluidController.signal_uncheck_all_sequences.connect(self.sequenceWidget.uncheck_all_sequences)

			self.fluidController.signal_initialize_stopwatch_display.connect(self.logWidget.addItem)
			self.fluidController.signal_initialize_stopwatch_display.connect(self.logWidget.scrollToBottom)
			self.fluidController.signal_update_stopwatch_display.connect(self.update_stopwatch_display)

			# connections for displaying the MCU state
			self.fluidController.signal_MCU_CMD_UID.connect(self.microcontrollerStateDisplayWidget.label_MCU_CMD_UID.setNum)
			self.fluidController.signal_MCU_CMD.connect(self.microcontrollerStateDisplayWidget.label_CMD.setNum)
			self.fluidController.signal_MCU_CMD_status.connect(self.microcontrollerStateDisplayWidget.label_CMD_status.setText)
			self.fluidController.signal_MCU_internal_program.connect(self.microcontrollerStateDisplayWidget.label_MCU_internal_program.setText)
			self.fluidController.signal_MCU_CMD_time_elapsed.connect(self.microcontrollerStateDisplayWidget.label_MCU_CMD_time_elapsed.setNum)

			self.fluidController.signal_pump_power.connect(self.microcontrollerStateDisplayWidget.label_pump_power.setText)
			self.fluidController.signal_selector_valve_position.connect(self.microcontrollerStateDisplayWidget.label_selector_valve_position.setNum)
			self.fluidController.signal_pressure.connect(self.microcontrollerStateDisplayWidget.label_pressure.setText)
			self.fluidController.signal_vacuum.connect(self.microcontrollerStateDisplayWidget.label_vacuum.setText)
			self.fluidController.signal_bubble_sensor_1.connect(self.microcontrollerStateDisplayWidget.label_bubble_sensor_downstream.setNum)
			self.fluidController.signal_bubble_sensor_2.connect(self.microcontrollerStateDisplayWidget.label_bubble_sensor_upstream.setNum)
			self.fluidController.signal_flow_upstream.connect(self.microcontrollerStateDisplayWidget.label_flowrate_upstream.setText)
			self.fluidController.signal_volume_ul.connect(self.microcontrollerStateDisplayWidget.label_dispensed_volume.setText)

			# highlight current sequence
			self.fluidController.signal_highlight_current_sequence.connect(self.sequenceWidget.select_row_using_sequence_name)

			# connection for the manual control
			self.fluidController.signal_uncheck_manual_control_enabled.connect(self.manualControlWidget.uncheck_enable_manual_control_button)

			# transfer the layout to the central widget
			self.fluidics_gui = QWidget()
			self.fluidics_gui.setLayout(layout)
			self.imageDisplayTabs.addTab(self.fluidics_gui, "Fluidics")

			# add the sequential imaging controller and widget
			self.squentialImagingController = core.SquentialImagingController(microscope = self, fluidics_controller = self.fluidController, fluidics_sequence_widget = self.sequenceWidget)
			self.sequentialImagingWidgets = widgets.SequentialImagingWidgets(self.squentialImagingController)
			self.recordTabWidget.addTab(self.sequentialImagingWidgets, 'Sequential Imaging')


	if INCLUDE_FLUIDICS:

		def disableManualControlWidget(self):
			self.tabWidget.setTabEnabled(1,False)
			self.preUseCheckWidget.setEnabled(False)

		def enableManualControlWidget(self):
			self.tabWidget.setTabEnabled(1,True)
			self.preUseCheckWidget.setEnabled(True)

		def disableSequenceWidget(self):
			self.tabWidget.setTabEnabled(0,False)

		def enableSequenceWidget(self):
			self.tabWidget.setTabEnabled(0,True)

		def update_stopwatch_display(self,text):
			if 'stop watch remaining time' in self.logWidget.item(self.logWidget.count()-1).text():
				# use this if statement to prevent other messages being overwritten
				self.logWidget.item(self.logWidget.count()-1).setText(text)

		def highlight_current_log_item(self):
			self.logWidget.setCurrentRow(self.logWidget.count()-1)

	def closeEvent(self, event):
		
		# move the objective to a defined position upon exit
		self.navigationController.move_x(0.1) # temporary bug fix - move_x needs to be called before move_x_to if the stage has been moved by the joystick
		while self.microcontroller.is_busy():
			time.sleep(0.005)
		self.navigationController.move_x_to(30)
		while self.microcontroller.is_busy():
			time.sleep(0.005)
		self.navigationController.move_y(0.1) # temporary bug fix - move_y needs to be called before move_y_to if the stage has been moved by the joystick
		while self.microcontroller.is_busy():
			time.sleep(0.005)
		self.navigationController.move_y_to(30)
		while self.microcontroller.is_busy():
			time.sleep(0.005)

		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		if not SINGLE_WINDOW:
			self.imageDisplayWindow.close()
			self.imageArrayDisplayWindow.close()
			self.tabbedImageDisplayWindow.close()
		if SUPPORT_LASER_AUTOFOCUS:
			self.camera_focus.close()
			self.imageDisplayWindow_focus.close()
		self.microcontroller.close()

		if INCLUDE_FLUIDICS:
			self.fluidController.close()
			self.sequenceWidget.close()

		event.accept()
