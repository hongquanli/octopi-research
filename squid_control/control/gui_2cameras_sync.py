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
import control.microcontroller2 as microcontroller2
from control._def import *

import pyqtgraph.dockarea as dock
SINGLE_WINDOW = True # set to False if use separate windows for display and control

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, is_simulation = False, *args, **kwargs):
		super().__init__(*args, **kwargs)

		channels = ['ch 1','ch 2']
		self.channels = channels

		self.imageDisplayWindow = {}
		for i in range(len(channels)):
			self.imageDisplayWindow[channels[i]] = core.ImageDisplayWindow(draw_crosshairs=True)

		# load objects
		self.camera = {}
		if is_simulation:
			for i in range(len(channels)):
				self.camera[channels[i]] = camera.Camera_Simulation(sn=CAMERA_SN[channels[i]],is_global_shutter=True,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			self.microcontroller = microcontroller.Microcontroller_Simulation()
			self.microcontroller2 = microcontroller2.Microcontroller2_Simulation()
		else:
			for i in range(len(channels)):
				self.camera[channels[i]] = camera.Camera(sn=CAMERA_SN[channels[i]],is_global_shutter=True,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
			self.microcontroller = microcontroller.Microcontroller_Simulation()
			self.microcontroller2 = microcontroller2.Microcontroller2()

		# open the camera
		for i in range(len(channels)): 
			self.camera[channels[i]].open()
			self.camera[channels[i]].set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()

		# configure the actuators
		self.microcontroller.configure_actuators()

		# navigation controller and widget
		self.navigationController = core.NavigationController(self.microcontroller)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController)
			
		self.configurationManager = {}
		self.streamHandler = {}
		self.liveController = {}
		self.imageSaver = {}

		self.cameraSettingWidget = {}
		self.liveControlWidget = {}
		self.cameraTabWidget = QTabWidget()

		for i in range(len(channels)): 
			# controllers
			self.configurationManager[channels[i]] = core.ConfigurationManager(filename=str(Path.home()) + "/configurations_" + channels[i] + ".xml")
			self.streamHandler[channels[i]] = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
			self.liveController[channels[i]] = core.LiveController(self.camera[channels[i]],self.microcontroller,self.configurationManager[channels[i]],use_internal_timer_for_hardware_trigger=False)
			self.imageSaver[channels[i]] = core.ImageSaver(image_format=Acquisition.IMAGE_FORMAT)
			# widgets
			self.cameraSettingWidget[channels[i]] = widgets.CameraSettingsWidget(self.camera[channels[i]],include_gain_exposure_time=False)
			self.liveControlWidget[channels[i]] = widgets.LiveControlWidget(self.streamHandler[channels[i]],self.liveController[channels[i]],self.configurationManager[channels[i]])
			# self.recordingControlWidget[channels[i]] = widgets.RecordingWidget(self.streamHandler[channels[i]],self.imageSaver[channels[i]])
			self.cameraTabWidget.addTab(self.liveControlWidget[channels[i]], channels[i])
			# self.liveControlWidget[channels[i]].setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
			# self.liveControlWidget[channels[i]].resize(self.liveControlWidget[channels[i]].minimumSizeHint())
			# self.liveControlWidget[channels[i]].adjustSize()
		self.cameraTabWidget.resize(self.cameraTabWidget.minimumSizeHint())
		self.cameraTabWidget.adjustSize()

		# self.recordTabWidget = QTabWidget()
		# for i in range(len(channels)): 
		# 	self.recordTabWidget.addTab(self.recordingControlWidget[channels[i]], "Simple Recording")
		self.multiCameraRecordingWidget = widgets.MultiCameraRecordingWidget(self.streamHandler,self.imageSaver,self.channels)

		# trigger control
		self.triggerControlWidget = widgets.TriggerControlWidget(self.microcontroller2)

		# layout widgets
		layout = QVBoxLayout() #layout = QStackedLayout()
		# layout.addWidget(self.cameraSettingWidget)
		layout.addWidget(self.cameraTabWidget)
		layout.addWidget(self.triggerControlWidget)
		layout.addWidget(self.multiCameraRecordingWidget)
		# layout.addWidget(self.navigationWidget)
		# layout.addWidget(self.recordTabWidget)
		layout.addStretch()
		
		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		# self.centralWidget.setFixedSize(self.centralWidget.minimumSize())
		# self.centralWidget.setFixedWidth(self.centralWidget.minimumWidth())
		# self.centralWidget.setMaximumWidth(self.centralWidget.minimumWidth())
		self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())
		
		dock_display = {}
		for i in range(len(channels)):
			dock_display[channels[i]] = dock.Dock('Image Display ' + channels[i] , autoOrientation = False)
			dock_display[channels[i]].showTitleBar()
			dock_display[channels[i]].addWidget(self.imageDisplayWindow[channels[i]].widget)
			dock_display[channels[i]].setStretch(x=100,y=None)
		dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
		# dock_controlPanel.showTitleBar()
		dock_controlPanel.addWidget(self.centralWidget)
		dock_controlPanel.setStretch(x=1,y=None)
		dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())
		main_dockArea = dock.DockArea()
		for i in range(len(channels)):
			if i == 0:
				main_dockArea.addDock(dock_display[channels[i]])
			else:
				main_dockArea.addDock(dock_display[channels[i]],'right')
		main_dockArea.addDock(dock_controlPanel,'right')
		self.setCentralWidget(main_dockArea)
		desktopWidget = QDesktopWidget()
		height_min = 0.9*desktopWidget.height()
		width_min = 0.96*desktopWidget.width()
		self.setMinimumSize(width_min,height_min)

		# make connections
		for i in range(len(channels)): 
			self.streamHandler[channels[i]].signal_new_frame_received.connect(self.liveController[channels[i]].on_new_frame)
			self.streamHandler[channels[i]].image_to_display.connect(self.imageDisplayWindow[channels[i]].display_image)
			self.streamHandler[channels[i]].packet_image_to_write.connect(self.imageSaver[channels[i]].enqueue)
			self.liveControlWidget[channels[i]].signal_newExposureTime.connect(self.cameraSettingWidget[channels[i]].set_exposure_time)
			self.liveControlWidget[channels[i]].signal_newAnalogGain.connect(self.cameraSettingWidget[channels[i]].set_analog_gain)
			self.liveControlWidget[channels[i]].update_camera_settings()
			self.triggerControlWidget.signal_toggle_live.connect(self.liveControlWidget[channels[i]].btn_live.setChecked)
			self.triggerControlWidget.signal_toggle_live.connect(self.liveControlWidget[channels[i]].toggle_live)
			self.triggerControlWidget.signal_trigger_mode.connect(self.liveControlWidget[channels[i]].set_trigger_mode)
			self.triggerControlWidget.signal_trigger_fps.connect(self.liveControlWidget[channels[i]].entry_triggerFPS.setValue)
			self.camera[channels[i]].set_callback(self.streamHandler[channels[i]].on_new_frame)
			self.camera[channels[i]].enable_callback()
		self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.navigationController.home()
		for i in range(len(self.channels)): 
			self.liveController[self.channels[i]].stop_live()
			self.camera[self.channels[i]].close()
			self.imageSaver[self.channels[i]].close()
		self.microcontroller.close()
