# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import QEvent
from qtpy.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QDesktopWidget

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
from control._def import *

from control.typechecker import TypecheckFunction

import pyqtgraph.dockarea as dock

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load window
		self.imageDisplayWindow = widgets.ImageDisplayWindow(draw_crosshairs=True,autoLevels=MACHINE_DISPLAY_CONFIG.AUTOLEVEL_DEFAULT_SETTING)
		self.imageArrayDisplayWindow = widgets.ImageArrayDisplayWindow()

		# image display windows
		self.imageDisplayTabs = QTabWidget()
		self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
		self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

		# load objects
		try:
			self.camera = camera.Camera(rotate_image_angle=MACHINE_CONFIG.ROTATE_IMAGE_ANGLE,flip_image=MACHINE_CONFIG.FLIP_IMAGE)
			self.camera.open()
		except Exception as e:
			print('! camera not detected !')
			raise e

		try:
			self.microcontroller = microcontroller.Microcontroller(version=MACHINE_CONFIG.CONTROLLER_VERSION)
		except Exception as e:
			print('! Microcontroller not detected !')
			raise e

		# reset the MCU
		self.microcontroller.reset()

		# configure the actuators
		self.microcontroller.configure_actuators()
			
		self.configurationManager = core.ConfigurationManager('./channel_configurations.xml')
		self.streamHandler = core.StreamHandler(display_resolution_scaling=MACHINE_DISPLAY_CONFIG.DEFAULT_DISPLAY_CROP/100)
		self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
		self.navigationController = core.NavigationController(self.microcontroller)
		self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager)
		self.imageSaver = core.ImageSaver(image_format=Acquisition.IMAGE_FORMAT)
		self.imageDisplay = widgets.ImageDisplay()

		# set up the camera
		self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
		self.camera.set_callback(self.streamHandler.on_new_frame)
		self.camera.enable_callback()
		if MACHINE_CONFIG.ENABLE_STROBE_OUTPUT:
			self.camera.set_line3_to_exposure_active()

		# load widgets
		self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
		self.liveControlWidget = widgets.LiveControlWidget(
			self.streamHandler,self.liveController,self.configurationManager,
			show_trigger_options=True,show_display_options=True,
			show_autolevel=MACHINE_DISPLAY_CONFIG.SHOW_AUTOLEVEL_BTN,
			autolevel=MACHINE_DISPLAY_CONFIG.AUTOLEVEL_DEFAULT_SETTING)
		self.navigationWidget = widgets.NavigationWidget(self.navigationController)
		self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
		self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
		self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
		self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)

		self.recordTabWidget = QTabWidget()
		self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
		self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")

		# layout widgets
		layout = QVBoxLayout() #layout = QStackedLayout()
		layout.addWidget(self.cameraSettingWidget)
		layout.addWidget(self.liveControlWidget)
		layout.addWidget(self.navigationWidget)
		if MACHINE_DISPLAY_CONFIG.SHOW_DAC_CONTROL:
			layout.addWidget(self.dacControlWidget)
		layout.addWidget(self.autofocusWidget)
		layout.addWidget(self.recordTabWidget)
		layout.addStretch()
		
		# transfer the layout to the central widget
		self.centralWidget:QWidget = QWidget()
		self.centralWidget.setLayout(layout)
		# self.centralWidget.setFixedSize(self.centralWidget.minimumSize())
		# self.centralWidget.setFixedWidth(self.centralWidget.minimumWidth())
		# self.centralWidget.setMaximumWidth(self.centralWidget.minimumWidth())
		self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())
		
		if MACHINE_DISPLAY_CONFIG.SINGLE_WINDOW:
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
			width_min = int(0.96*desktopWidget.width())
			self.setMinimumSize(width_min,height_min)
		else:
			self.setCentralWidget(self.centralWidget)
			self.tabbedImageDisplayWindow = QMainWindow()
			self.tabbedImageDisplayWindow.setCentralWidget(self.imageDisplayTabs)
			self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint) # type: ignore
			self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint) # type: ignore
			desktopWidget = QDesktopWidget()
			width = int(0.96*desktopWidget.height())
			height = width
			self.tabbedImageDisplayWindow.setFixedSize(width,height)
			self.tabbedImageDisplayWindow.show()

		# make connections
		self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
		self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
		self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
		self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image) # may connect streamHandler directly to imageDisplayWindow
		self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)
		self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)
		self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
		self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
		self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)
		self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
		self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
		self.liveControlWidget.update_camera_settings()
		self.liveControlWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel)

	@TypecheckFunction
	def closeEvent(self, event:QEvent):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.navigationController.home()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		if not MACHINE_DISPLAY_CONFIG.SINGLE_WINDOW:
			self.imageDisplayWindow.close()
			self.imageArrayDisplayWindow.close()
			self.tabbedImageDisplayWindow.close()
		self.microcontroller.close()
