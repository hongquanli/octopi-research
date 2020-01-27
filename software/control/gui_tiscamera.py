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
import control.widgets_tracking as widgets_tracking
import control.camera_TIS as camera
import control.core as core
import control.core_tracking as core_tracking
import control.microcontroller as microcontroller

SIMULATION = True

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		if SIMULATION is True:
			self.camera = camera.Camera_Simulation()
			self.microcontroller = microcontroller.Microcontroller_Simulation()
		else:
			self.camera = camera.Camera(sn=17910085)
			self.microcontroller = microcontroller.Microcontroller()
		
		self.streamHandler = core.StreamHandler()
		self.liveController = core.LiveController(self.camera,self.microcontroller)
		self.navigationController = core.NavigationController(self.microcontroller)
		#self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		#self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController)
		self.trackingController = core_tracking.TrackingController(self.microcontroller,self.navigationController)
		self.imageSaver = core.ImageSaver()
		self.imageDisplay = core.ImageDisplay()

		'''
		# thread
		self.thread_multiPoint = QThread()
		self.thread_multiPoint.start()
		self.multipointController.moveToThread(self.thread_multiPoint)
		'''

		# open the camera
		# camera start streaming
		self.camera.open()
		self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()

		# load widgets
		self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,self.liveController)
		self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController)
		#self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
		self.trackingControlWidget = widgets_tracking.TrackingControllerWidget(self.streamHandler,self.trackingController)
		#self.multiPointWidget = widgets.MultiPointWidget(self.multipointController)

		self.recordTabWidget = QTabWidget()
		self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
		self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
		#self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")

		# layout widgets
		layout = QGridLayout() #layout = QStackedLayout()
		layout.addWidget(self.cameraSettingWidget,0,0)
		layout.addWidget(self.liveControlWidget,1,0)
		layout.addWidget(self.navigationWidget,2,0)
		#layout.addWidget(self.autofocusWidget,3,0)
		layout.addWidget(self.recordTabWidget,4,0)
		
		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.setCentralWidget(self.centralWidget)

		# load window
		self.imageDisplayWindow = core.ImageDisplayWindow('Main Display')
		self.imageDisplayWindow.show()

		self.imageDisplayWindow_ThresholdedImage = core.ImageDisplayWindow('Thresholded Image')
		self.imageDisplayWindow_ThresholdedImage.show()

		# make connections
		self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
		self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
		self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
		self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
		self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image) # may connect streamHandler directly to imageDisplayWindow
		self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)
		#self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
		#self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)

		self.camera.start_streaming()

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		self.imageDisplayWindow.close()
		self.imageDisplayWindow_ThresholdedImage.close()
