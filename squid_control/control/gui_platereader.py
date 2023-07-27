# set QT_API environment variable
import os 
from pathlib import Path
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
import control.core_platereader as core_platereader
import control.microcontroller as microcontroller

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, is_simulation = False, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		if is_simulation:
			self.camera = camera.Camera_Simulation()
			self.microcontroller = microcontroller.Microcontroller_Simulation()
		else:
			self.camera = camera.Camera()
			self.microcontroller = microcontroller.Microcontroller()
		
		self.configurationManager = core.ConfigurationManager(filename=str(Path.home()) + "/configurations_platereader.xml")
		self.streamHandler = core.StreamHandler()
		self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController = core.NavigationController(self.microcontroller)
		self.plateReaderNavigationController = core.PlateReaderNavigationController(self.microcontroller)
		self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.plateReadingController = core_platereader.PlateReadingController(self.camera,self.plateReaderNavigationController,self.liveController,self.autofocusController,self.configurationManager)
		self.imageSaver = core.ImageSaver()

		# open the camera
		# camera start streaming
		self.camera.open()
		self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()

		# load widgets
		self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
		self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_trigger_options=False,show_display_options=False)
		self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.plateReaderAcquisitionWidget = widgets.PlateReaderAcquisitionWidget(self.plateReadingController,self.configurationManager,show_configurations=False)
		self.plateReaderNavigationWidget = widgets.PlateReaderNavigationWidget(self.plateReaderNavigationController)

		# layout widgets
		layout = QGridLayout() #layout = QStackedLayout()
		#layout.addWidget(self.cameraSettingWidget,0,0)
		layout.addWidget(self.liveControlWidget,1,0)
		layout.addWidget(self.plateReaderNavigationWidget,2,0)
		layout.addWidget(self.autofocusWidget,3,0)
		layout.addWidget(self.plateReaderAcquisitionWidget,4,0)
		
		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.setCentralWidget(self.centralWidget)

		# load window
		self.imageDisplayWindow = core.ImageDisplayWindow()
		self.imageDisplayWindow.show()

		# make connections
		self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
		self.streamHandler.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
		# self.plateReaderNavigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		# self.plateReaderNavigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		# self.plateReaderNavigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)
		self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
		# self.plateReadingController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.plateReadingController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
		self.plateReadingController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
		self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
		self.liveControlWidget.update_camera_settings()

		self.microcontroller.set_callback(self.plateReaderNavigationController.update_pos)
		self.plateReaderNavigationController.signal_homing_complete.connect(self.plateReaderNavigationWidget.slot_homing_complete)
		self.plateReaderNavigationController.signal_homing_complete.connect(self.plateReaderAcquisitionWidget.slot_homing_complete)
		self.plateReaderNavigationController.signal_current_well.connect(self.plateReaderNavigationWidget.update_current_location)

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		# self.plateReaderNavigationController.home()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplayWindow.close()
		self.microcontroller.close()