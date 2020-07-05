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

class OctopiGUI(QMainWindow):

	# variables
	fps_software_trigger = 100

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		self.microcontroller = microcontroller.Microcontroller()
		self.navigationController = core.NavigationController(self.microcontroller)

		# load widgets
		self.navigationWidget = widgets.NavigationWidget(self.navigationController)
		
		# layout widgets
		layout = QGridLayout() #layout = QStackedLayout()
		layout.addWidget(self.navigationWidget,2,0)

		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.setCentralWidget(self.centralWidget)

		# make connections
		self.navigationController.xPos.connect(self.navigationWidget.label_Xpos.setNum)
		self.navigationController.yPos.connect(self.navigationWidget.label_Ypos.setNum)
		self.navigationController.zPos.connect(self.navigationWidget.label_Zpos.setNum)

	def closeEvent(self, event):
		event.accept()
		self.navigationController.home()