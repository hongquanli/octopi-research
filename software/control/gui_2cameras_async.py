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
import control.microcontroller as microcontroller

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		self.microcontroller = microcontroller.Microcontroller_Simulation()
		self.navigationController = core.NavigationController(self.microcontroller)

		self.camera_1 = camera.Camera_Simulation(sn='FW0190110139') # tracking
		self.camera_2 = camera.Camera_Simulation(sn='FU0190090030')	# fluorescence
		
		self.configurationManager_1 = core.ConfigurationManager(filename=str(Path.home()) + "/configurations_tracking.xml")
		self.configurationManager_2 = core.ConfigurationManager(filename=str(Path.home()) + "/configurations_fluorescence.xml")

		self.streamHandler_1 = core.StreamHandler()
		self.liveController_1 = core.LiveController(self.camera_1,self.microcontroller,self.configurationManager_1,control_illumination=False)
		#self.autofocusControlle_1 = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		#self.multipointController_1 = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager)
		self.imageSaver_1 = core.ImageSaver()

		self.streamHandler_2 = core.StreamHandler()
		self.liveController_2 = core.LiveController(self.camera_2,self.microcontroller,self.configurationManager_2,control_illumination=True)
		self.autofocusController_2 = core.AutoFocusController(self.camera_2,self.navigationController,self.liveController_2)
		self.multipointController_2 = core.MultiPointController(self.camera_2,self.navigationController,self.liveController_2,self.autofocusController_2,self.configurationManager_2)
		self.imageSaver_2 = core.ImageSaver()

		self.trackingController = core.TrackingController(self.microcontroller,self.navigationController)
		
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
		self.liveControlWidget_1 = widgets.LiveControlWidget(self.streamHandler_1,self.liveController_1,self.configurationManager_1)
		self.recordingControlWidget_1 = widgets.RecordingWidget(self.streamHandler_1,self.imageSaver_1)
		#self.trackingControlWidget = widgets.TrackingControllerWidget(self.streamHandler_1,self.trackingController)

		self.cameraSettingWidget_2 = widgets.CameraSettingsWidget(self.camera_2,self.liveController_2)
		self.liveControlWidget_2 = widgets.LiveControlWidget(self.streamHandler_2,self.liveController_2,self.configurationManager_2)
		#self.recordingControlWidget_2 = widgets.RecordingWidget(self.streamHandler_2,self.imageSaver_2)
		self.multiPointWidget_2 = widgets.MultiPointWidget(self.multipointController_2,self.configurationManager_2)
		
		# layout widgets
		layout = QGridLayout() #layout = QStackedLayout()
		layout.addWidget(self.cameraSettingWidget_1,0,0)
		layout.addWidget(self.liveControlWidget_1,1,0)
		layout.addWidget(self.navigationWidget,2,0)
		#layout.addWidget(self.autofocusWidget,3,0)
		layout.addWidget(self.recordingControlWidget_1,4,0)
		
		layout.addWidget(self.cameraSettingWidget_2,5,0)
		layout.addWidget(self.liveControlWidget_2,6,0)
		#layout.addWidget(self.recordingControlWidget_2,7,0)
		layout.addWidget(self.multiPointWidget_2,8,0)

		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.setCentralWidget(self.centralWidget)

		# load window
		self.imageDisplayWindow_1 = core.ImageDisplayWindow('Tracking')
		self.imageDisplayWindow_1.show()
		self.imageDisplayWindow_2 = core.ImageDisplayWindow('Fluorescence')
		self.imageDisplayWindow_2.show()
		self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow('Multi-channel') 
		self.imageArrayDisplayWindow.show()

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
		
		self.multipointController_2.image_to_display.connect(self.imageDisplayWindow_2.display_image)
		self.multipointController_2.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)
		self.multipointController_2.signal_current_configuration.connect(self.liveControlWidget_2.set_microscope_mode)
		

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
		self.imageArrayDisplayWindow.close()
