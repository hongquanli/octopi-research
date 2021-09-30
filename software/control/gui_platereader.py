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
import control.microcontroller as microcontroller

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		self.camera = camera.Camera_Simulation()
		self.microcontroller = microcontroller.Microcontroller_Simulation()
		
		self.configurationManager = core.ConfigurationManager(filename=str(Path.home()) + "/configurations_platereader.xml")
		self.streamHandler = core.StreamHandler()
		self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController = core.NavigationController(self.microcontroller)
		self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager)
		self.trackingController = core.TrackingController(self.microcontroller,self.navigationController)
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
		self.plateReaderWidget = widgets.PlatereaderWidget(self.multipointController,self.configurationManager,show_configurations=False)

		# layout widgets
		layout = QGridLayout() #layout = QStackedLayout()
		#layout.addWidget(self.cameraSettingWidget,0,0)
		layout.addWidget(self.liveControlWidget,1,0)
		layout.addWidget(self.autofocusWidget,3,0)
		layout.addWidget(self.plateReaderWidget,4,0)
		
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
		self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
		# self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		# self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		# self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)
		self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
		# self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
		self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
		self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
		self.liveControlWidget.update_camera_settings()

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.navigationController.home()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplayWindow.close()
		self.microcontroller.close()