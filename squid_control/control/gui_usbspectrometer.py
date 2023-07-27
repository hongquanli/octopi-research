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

import control.widgets_usbspectrometer as widgets_usbspectrometer
import control.core_usbspectrometer as core_usbspectrometer
import control.spectrometer_oceanoptics as spectrometer

import pyqtgraph.dockarea as dock
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
			self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
		self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow() 
		# self.imageDisplayWindow.show()
		# self.imageArrayDisplayWindow.show()

		# image display windows
		self.imageDisplayTabs = QTabWidget()
		self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
		# self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

		# load objects
		if is_simulation:
			self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			self.microcontroller = microcontroller.Microcontroller_Simulation()
			self.spectrometer = spectrometer.Spectrometer_Simulation()
		else:
			self.camera = camera.Camera(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			try:
				self.microcontroller = microcontroller.Microcontroller()
			except:
				print('! Microcontroller not detected, using simulated microcontroller !')
				self.microcontroller = microcontroller.Microcontroller_Simulation()
			try:
				self.spectrometer = spectrometer.Spectrometer()
			except:
				print('! Spectrometer not detected, using simulated microcontroller !')
				self.spectrometer = spectrometer.Spectrometer_Simulation()

		# configure the actuators
		self.microcontroller.configure_actuators()
			
		self.configurationManager = core.ConfigurationManager('./channel_configurations.xml')
		self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
		self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController = core.NavigationController(self.microcontroller)
		self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,self.spectrometer)
		if ENABLE_TRACKING:
			self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
		self.imageSaver = core.ImageSaver(image_format=Acquisition.IMAGE_FORMAT)
		self.imageDisplay = core.ImageDisplay()
		self.spectrometerStreamHandler = core_usbspectrometer.SpectrumStreamHandler()
		self.spectrumSaver = core_usbspectrometer.SpectrumSaver()

		# open the camera
		# camera start streaming
		self.camera.open()
		# self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
		# self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
		self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()
		if ENABLE_STROBE_OUTPUT:
			self.camera.set_line3_to_exposure_active()

		self.spectrometer.set_callback(self.spectrometerStreamHandler.on_new_measurement)

		# load widgets
		self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
		self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController)
		self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
		self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
		self.spectrumRecordingWidget = widgets_usbspectrometer.RecordingWidget(self.spectrometerStreamHandler,self.spectrumSaver)
		if ENABLE_TRACKING:
			self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
		self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)

		self.recordTabWidget = QTabWidget()
		if ENABLE_TRACKING:
			self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
		self.recordTabWidget.addTab(self.recordingControlWidget, "Recording - Camera")
		self.recordTabWidget.addTab(self.spectrumRecordingWidget, "Recording - Spectrometer")
		self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")
		self.spectrometerControlWidget = widgets_usbspectrometer.SpectrometerControlWidget(self.spectrometer,self.spectrometerStreamHandler)
		self.spectrumDisplay = widgets_usbspectrometer.SpectrumDisplay()

		# layout widgets
		layout = QVBoxLayout() #layout = QStackedLayout()
		layout.addWidget(self.cameraSettingWidget)
		layout.addWidget(self.liveControlWidget)
		layout.addWidget(self.navigationWidget)
		if SHOW_DAC_CONTROL:
			layout.addWidget(self.dacControlWidget)
		layout.addWidget(self.autofocusWidget)
		layout.addWidget(self.spectrometerControlWidget)
		layout.addWidget(self.recordTabWidget)
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
			dock_display.setStretch(x=100,y=60)
			dock_spectrum = dock.Dock('Spectrum', autoOrientation = False)
			dock_spectrum.showTitleBar()
			dock_spectrum.addWidget(self.spectrumDisplay)
			dock_spectrum.setStretch(x=100,y=40)
			dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
			dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
			# dock_controlPanel.showTitleBar()
			dock_controlPanel.addWidget(self.centralWidget)
			dock_controlPanel.setStretch(x=1,y=None)
			dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())
			main_dockArea = dock.DockArea()
			main_dockArea.addDock(dock_display)
			main_dockArea.addDock(dock_spectrum,'bottom')
			main_dockArea.addDock(dock_controlPanel,'right')
			self.setCentralWidget(main_dockArea)
			desktopWidget = QDesktopWidget()
			height_min = 0.9*desktopWidget.height()
			width_min = 0.96*desktopWidget.width()
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
		self.multipointController.spectrum_to_display.connect(self.spectrumDisplay.plot)
		self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
		self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
		self.liveControlWidget.update_camera_settings()
		self.spectrometerStreamHandler.spectrum_to_display.connect(self.spectrumDisplay.plot)
		self.spectrometerStreamHandler.spectrum_to_write.connect(self.spectrumSaver.enqueue)

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.navigationController.home()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		self.spectrometer.close()
		self.spectrumSaver.close()
		if not SINGLE_WINDOW:
			self.imageDisplayWindow.close()
			self.imageArrayDisplayWindow.close()
			self.tabbedImageDisplayWindow.close()
		self.microcontroller.close()
