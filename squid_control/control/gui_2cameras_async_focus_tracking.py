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
import control.core_PDAF as core_PDAF
import control.microcontroller as microcontroller

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		self.camera_1 = camera.Camera_Simulation(sn='FW0190110139')
		self.camera_2 = camera.Camera_Simulation(sn='FU0190090030')
		self.microcontroller = microcontroller.Microcontroller_Simulation()

		self.PDAFController = core_PDAF.PDAFController()
		
		self.streamHandler_1 = core.StreamHandler()
		self.streamHandler_2 = core.StreamHandler()
		self.liveController_1 = core.LiveController(self.camera_1,self.microcontroller)
		self.liveController_2 = core.LiveController(self.camera_2,self.microcontroller)
		self.navigationController = core.NavigationController(self.microcontroller)
		self.autofocusController = core.AutoFocusController(self.camera_1,self.navigationController,self.liveController_1)
		self.trackingController = core.TrackingController(self.microcontroller,self.navigationController)
		self.imageSaver_1 = core.ImageSaver()
		self.imageSaver_2 = core.ImageSaver()
		self.imageDisplay_1 = core.ImageDisplay()
		self.imageDisplay_2 = core.ImageDisplay()

		# open the cameras
		self.camera_1.open()
		self.camera_1.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera_1.set_callback(self.streamHandler_1.on_new_frame)
		self.camera_1.enable_callback()

		self.camera_2.open()
		self.camera_2.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera_2.set_callback(self.streamHandler_2.on_new_frame)
		self.camera_2.enable_callback()

		# load widgets
		self.cameraSettingWidget_1 = widgets.CameraSettingsWidget(self.camera_1,self.liveController_1)
		self.liveControlWidget_1 = widgets.LiveControlWidget(self.streamHandler_1,self.liveController_1)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController)
		self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget_1 = widgets.RecordingWidget(self.streamHandler_1,self.imageSaver_1)
		self.trackingControlWidget = widgets.TrackingControllerWidget(self.streamHandler_1,self.trackingController)

		self.cameraSettingWidget_2 = widgets.CameraSettingsWidget(self.camera_2,self.liveController_2)
		self.liveControlWidget_2 = widgets.LiveControlWidget(self.streamHandler_2,self.liveController_2)
		self.recordingControlWidget_2 = widgets.RecordingWidget(self.streamHandler_2,self.imageSaver_2)
		
		# layout widgets
		layout = QGridLayout() #layout = QStackedLayout()
		# layout.addWidget(self.cameraSettingWidget_1,0,0)
		layout.addWidget(self.liveControlWidget_1,1,0)
		# layout.addWidget(self.navigationWidget,2,0)
		# layout.addWidget(self.autofocusWidget,3,0)
		# layout.addWidget(self.recordingControlWidget_1,4,0)
		
		# layout.addWidget(self.cameraSettingWidget_2,5,0)
		layout.addWidget(self.liveControlWidget_2,6,0)
		# layout.addWidget(self.recordingControlWidget_2,7,0)

		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.setCentralWidget(self.centralWidget)

		# load window
		self.imageDisplayWindow_1 = core.ImageDisplayWindow()
		self.imageDisplayWindow_1.show()
		self.imageDisplayWindow_2 = core.ImageDisplayWindow()
		self.imageDisplayWindow_2.show()

		# make connections
		self.streamHandler_1.signal_new_frame_received.connect(self.liveController_1.on_new_frame)
		self.streamHandler_1.image_to_display.connect(self.imageDisplay_1.enqueue)
		self.streamHandler_1.packet_image_to_write.connect(self.imageSaver_1.enqueue)
		self.streamHandler_1.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
		self.imageDisplay_1.image_to_display.connect(self.imageDisplayWindow_1.display_image) # may connect streamHandler directly to imageDisplayWindow

		self.streamHandler_2.signal_new_frame_received.connect(self.liveController_2.on_new_frame)
		self.streamHandler_2.image_to_display.connect(self.imageDisplay_2.enqueue)
		self.streamHandler_2.packet_image_to_write.connect(self.imageSaver_2.enqueue)
		self.imageDisplay_2.image_to_display.connect(self.imageDisplayWindow_2.display_image) # may connect streamHandler directly to imageDisplayWindow
		
		self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)
		self.autofocusController.image_to_display.connect(self.imageDisplayWindow_1.display_image)

		self.streamHandler_1.image_to_display.connect(self.PDAFController.register_image_from_camera_1)
		self.streamHandler_2.image_to_display.connect(self.PDAFController.register_image_from_camera_2)


	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.liveController_1.stop_live()
		self.camera_1.close()
		self.imageSaver_1.close()
		self.imageDisplay_1.close()
		self.imageDisplayWindow_1.close()
		self.liveController_2.stop_live()
		self.camera_2.close()
		self.imageSaver_2.close()
		self.imageDisplay_2.close()
		self.imageDisplayWindow_2.close()
