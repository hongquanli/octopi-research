# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy
from pathlib import Path

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.core_PDAF as core_PDAF
import control.microcontroller as microcontroller

class Internal_States():
	def __init__(self):
		self.w = 500
		self.h = 500
		self.x = 1500
		self.y = 1500

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, is_simulation=False,*args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		if is_simulation:
			self.microcontroller = microcontroller.Microcontroller_Simulation()
			self.camera_1 = camera.Camera_Simulation(sn='FW0200050063') # tracking
			self.camera_2 = camera.Camera_Simulation(sn='FW0200050068')	# fluorescence
		else:
			self.microcontroller = microcontroller.Microcontroller()
			self.camera_1 = camera.Camera(sn='FW0200050063') # tracking
			self.camera_2 = camera.Camera(sn='FW0200050068')	# fluorescence

		self.internal_states = Internal_States()
		
		self.navigationController = core.NavigationController(self.microcontroller)
		self.PDAFController = core_PDAF.PDAFController(self.internal_states)

		self.configurationManager = core.ConfigurationManager(filename=str(Path.home()) + "/configurations_PDAF.xml")

		self.streamHandler_1 = core.StreamHandler()
		self.liveController_1 = core.LiveController(self.camera_1,self.microcontroller,self.configurationManager,control_illumination=False)
		self.imageSaver_1 = core.ImageSaver()

		self.streamHandler_2 = core.StreamHandler()
		self.liveController_2 = core.LiveController(self.camera_2,self.microcontroller,self.configurationManager,control_illumination=True)
		self.imageSaver_2 = core.ImageSaver()

		self.twoCamerasPDAFCalibrationController = core_PDAF.TwoCamerasPDAFCalibrationController(self.camera_1,self.camera_2,self.navigationController,self.liveController_1,self.liveController_2,self.configurationManager)
		
		# open the camera
		# camera start streaming
		self.camera_1.open()
		self.camera_1.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera_1.set_callback(self.streamHandler_1.on_new_frame)
		self.camera_1.enable_callback()

		self.camera_2.open()
		self.camera_2.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera_2.set_callback(self.streamHandler_2.on_new_frame)
		self.camera_2.enable_callback()

		# load widgets
		self.navigationWidget = widgets.NavigationWidget(self.navigationController)
		self.cameraSettingWidget_1 = widgets.CameraSettingsWidget(self.camera_1,self.liveController_1)
		self.liveControlWidget_1 = widgets.LiveControlWidget(self.streamHandler_1,self.liveController_1,self.configurationManager)
		self.cameraSettingWidget_2 = widgets.CameraSettingsWidget(self.camera_2,self.liveController_2)
		self.liveControlWidget_2 = widgets.LiveControlWidget(self.streamHandler_2,self.liveController_2,self.configurationManager)
		
		# layout widgets
		layout = QGridLayout() #layout = QStackedLayout()
		layout.addWidget(self.cameraSettingWidget_1,0,0)
		layout.addWidget(self.liveControlWidget_1,1,0)
		layout.addWidget(self.cameraSettingWidget_2,0,1)
		layout.addWidget(self.liveControlWidget_2,1,1)

		layout.addWidget(self.navigationWidget,7,0)

		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.setCentralWidget(self.centralWidget)

		# load window
		self.imageDisplayWindow_1 = core.ImageDisplayWindow('camera 1')
		self.imageDisplayWindow_1.show()
		self.imageDisplayWindow_2 = core.ImageDisplayWindow('camera 2')
		self.imageDisplayWindow_2.show()

		# make connections
		self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)

		self.streamHandler_1.signal_new_frame_received.connect(self.liveController_1.on_new_frame)
		self.streamHandler_1.image_to_display.connect(self.imageDisplayWindow_1.display_image)
		self.streamHandler_1.packet_image_to_write.connect(self.imageSaver_1.enqueue)
		#self.streamHandler_1.packet_image_for_tracking.connect(self.trackingController.on_new_frame)

		self.liveControlWidget_1.signal_newExposureTime.connect(self.cameraSettingWidget_1.set_exposure_time)
		self.liveControlWidget_1.signal_newAnalogGain.connect(self.cameraSettingWidget_1.set_analog_gain)
		self.liveControlWidget_1.update_camera_settings()

		self.streamHandler_2.signal_new_frame_received.connect(self.liveController_2.on_new_frame)
		self.streamHandler_2.image_to_display.connect(self.imageDisplayWindow_2.display_image)
		self.streamHandler_2.packet_image_to_write.connect(self.imageSaver_2.enqueue)

		self.liveControlWidget_2.signal_newExposureTime.connect(self.cameraSettingWidget_2.set_exposure_time)
		self.liveControlWidget_2.signal_newAnalogGain.connect(self.cameraSettingWidget_2.set_analog_gain)
		self.liveControlWidget_2.update_camera_settings()

		self.streamHandler_1.image_to_display.connect(self.PDAFController.register_image_from_camera_1) 
		self.streamHandler_2.image_to_display.connect(self.PDAFController.register_image_from_camera_2) 
		

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.liveController_1.stop_live()
		self.camera_1.close()
		self.imageSaver_1.close()
		self.imageDisplayWindow_1.close()
		self.liveController_2.stop_live()
		self.camera_2.close()
		self.imageSaver_2.close()
		self.imageDisplayWindow_2.close()
