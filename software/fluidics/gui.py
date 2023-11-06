# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import controllers
import widgets

class STARmapAutomationControllerGUI(QMainWindow):

	def __init__(self, is_simulation=False, log_measurements=False, debug_mode=False, *args, **kwargs):
		super().__init__(*args, **kwargs)

		# load objects
		# self.triggerController = controllers.TriggerController()
		# self.triggerController = controllers.TriggerController_simulation()
		#elf.fluidController = controllers.FluidController()

		if(is_simulation):
			self.teensy41 = controllers.Microcontroller_Simulation()
		else:
			serial_number = '9037670'
			self.teensy41 = controllers.Microcontroller(serial_number)
		self.fluidController = controllers.FluidController(self.teensy41,log_measurements)
		self.logger = controllers.Logger()

		# load widgets
		self.chillerWidget = widgets.ChillerWidget(self.fluidController)
		self.preUseCheckWidget = widgets.PreUseCheckWidget(self.fluidController)
		self.logWidget = QListWidget()
		# self.triggerWidget = widgets.TriggerWidget(self.triggerController)
		self.sequenceWidget = widgets.SequenceWidget(self.fluidController)
		self.manualFlushWidget = widgets.ManualFlushWidget(self.fluidController)
		self.manualControlWidget = widgets.ManualControlWidget(self.fluidController)
		self.microcontrollerStateDisplayWidget = widgets.MicrocontrollerStateDisplayWidget()

		self.arbitraryCommandWidget = widgets.ArbitraryCommandWidget(self.fluidController)

		# disable preuse check before it is fully implemented
		# self.preUseCheckWidget.setEnabled(False)

		# layout widgets (linear)
		'''
		layout = QGridLayout()
		layout.addWidget(QLabel('Chiller'),0,0)
		layout.addWidget(self.chillerWidget,0,1)
		layout.addWidget(QLabel('Pre-Use Check'),1,0)
		layout.addWidget(self.preUseCheckWidget,1,1)
		layout.addWidget(QLabel('Sequences'),4,0)
		layout.addWidget(self.sequenceWidget,4,1)
		# layout.addWidget(self.triggerWidget,8,0)
		layout.addWidget(QLabel('Manual Flush'),9,0) # (End of Experiment)
		layout.addWidget(self.manualFlushWidget,9,1)
		layout.addWidget(self.logWidget,10,0,1,2)
		'''

		# layout widgets (using tabs)  - start
		tab1_layout = QGridLayout()
		# tab1_layout.addWidget(QLabel('Chiller'),0,0)
		# tab1_layout.addWidget(self.chillerWidget,0,1)
		tab1_layout.addWidget(QLabel('Pre-Use Check'),1,0)
		tab1_layout.addWidget(self.preUseCheckWidget,1,1)
		tab1_layout.addWidget(QLabel('Sequences'),4,0)
		tab1_layout.addWidget(self.sequenceWidget,4,1)
		tab1_widget = QWidget()
		
		tab1_widget.setLayout(tab1_layout)
		tab2_widget = self.manualControlWidget

		self.tabWidget = QTabWidget()
		self.tabWidget.addTab(tab1_widget, "Run Experiments")
		self.tabWidget.addTab(tab2_widget, "Settings and Manual Control")
		
		layout = QGridLayout()
		layout.addWidget(self.tabWidget,0,0)

		# layout.addWidget(self.logWidget,1,0)
		# @@@ the code below is to put the ListWidget into a frame - code may be improved
		self.framedLogWidget = QFrame()
		framedLogWidget_layout = QHBoxLayout() 
		framedLogWidget_layout.addWidget(self.logWidget)
		self.framedLogWidget.setLayout(framedLogWidget_layout)
		self.framedLogWidget.setFrameStyle(QFrame.Panel | QFrame.Raised)
		'''
		mcuStateDisplay = QGridLayout()
		mcuStateDisplay.addWidget(QLabel('Controller State'),0,0)
		mcuStateDisplay.addWidget(self.microcontrollerStateDisplayWidget,0,1)
		layout.addLayout(mcuStateDisplay,1,0)
		'''
		layout.addWidget(self.microcontrollerStateDisplayWidget,1,0)
		if debug_mode:
			layout.addWidget(self.arbitraryCommandWidget,2,0)
		layout.addWidget(self.framedLogWidget,3,0)
		# layout widgets (using tabs)  - end

		# connecting signals to slots
		# @@@ to do: addItem and scrollToBottom need to happen in sequence - create a function for this
		self.chillerWidget.log_message.connect(self.logWidget.addItem)
		self.preUseCheckWidget.log_message.connect(self.logWidget.addItem)
		self.fluidController.log_message.connect(self.logWidget.addItem)
		# self.triggerController.log_message.connect(self.logWidget.addItem)
		self.sequenceWidget.log_message.connect(self.logWidget.addItem)
		self.manualFlushWidget.log_message.connect(self.logWidget.addItem)
		self.manualControlWidget.log_message.connect(self.logWidget.addItem)

		self.chillerWidget.log_message.connect(self.logWidget.scrollToBottom)
		self.preUseCheckWidget.log_message.connect(self.logWidget.scrollToBottom)
		self.fluidController.log_message.connect(self.logWidget.scrollToBottom)
		# self.triggerController.log_message.connect(self.logWidget.scrollToBottom)
		self.sequenceWidget.log_message.connect(self.logWidget.scrollToBottom)
		self.manualFlushWidget.log_message.connect(self.logWidget.scrollToBottom)
		self.manualControlWidget.log_message.connect(self.logWidget.scrollToBottom)
		
		self.chillerWidget.log_message.connect(self.logger.log)
		self.preUseCheckWidget.log_message.connect(self.logger.log)
		self.fluidController.log_message.connect(self.logger.log)
		# self.triggerController.log_message.connect(self.logger.log)
		self.sequenceWidget.log_message.connect(self.logger.log)
		self.manualFlushWidget.log_message.connect(self.logger.log)
		self.manualControlWidget.log_message.connect(self.logger.log)

		self.fluidController.signal_log_highlight_current_item.connect(self.highlight_current_log_item)

		self.sequenceWidget.signal_disable_manualControlWidget.connect(self.disableManualControlWidget)
		self.sequenceWidget.signal_enable_manualControlWidget.connect(self.enableManualControlWidget)
		self.manualControlWidget.signal_disable_userinterface.connect(self.disableSequenceWidget)
		self.manualControlWidget.signal_enable_userinterface.connect(self.enableSequenceWidget)
		self.preUseCheckWidget.signal_disable_manualControlWidget.connect(self.disableManualControlWidget)
		self.preUseCheckWidget.signal_disable_sequenceWidget.connect(self.disableSequenceWidget)
		self.fluidController.signal_preuse_check_result.connect(self.preUseCheckWidget.show_preuse_check_result)

		self.fluidController.signal_uncheck_all_sequences.connect(self.sequenceWidget.uncheck_all_sequences)

		self.fluidController.signal_initialize_stopwatch_display.connect(self.logWidget.addItem)
		self.fluidController.signal_initialize_stopwatch_display.connect(self.logWidget.scrollToBottom)
		self.fluidController.signal_update_stopwatch_display.connect(self.update_stopwatch_display)

		# connections for displaying the MCU state
		self.fluidController.signal_MCU_CMD_UID.connect(self.microcontrollerStateDisplayWidget.label_MCU_CMD_UID.setNum)
		self.fluidController.signal_MCU_CMD.connect(self.microcontrollerStateDisplayWidget.label_CMD.setNum)
		self.fluidController.signal_MCU_CMD_status.connect(self.microcontrollerStateDisplayWidget.label_CMD_status.setText)
		self.fluidController.signal_MCU_internal_program.connect(self.microcontrollerStateDisplayWidget.label_MCU_internal_program.setText)
		self.fluidController.signal_MCU_CMD_time_elapsed.connect(self.microcontrollerStateDisplayWidget.label_MCU_CMD_time_elapsed.setNum)

		self.fluidController.signal_pump_power.connect(self.microcontrollerStateDisplayWidget.label_pump_power.setText)
		self.fluidController.signal_selector_valve_position.connect(self.microcontrollerStateDisplayWidget.label_selector_valve_position.setNum)
		self.fluidController.signal_pressure.connect(self.microcontrollerStateDisplayWidget.label_pressure.setText)
		self.fluidController.signal_vacuum.connect(self.microcontrollerStateDisplayWidget.label_vacuum.setText)
		self.fluidController.signal_bubble_sensor_1.connect(self.microcontrollerStateDisplayWidget.label_bubble_sensor_downstream.setNum)
		self.fluidController.signal_bubble_sensor_2.connect(self.microcontrollerStateDisplayWidget.label_bubble_sensor_upstream.setNum)
		self.fluidController.signal_flow_upstream.connect(self.microcontrollerStateDisplayWidget.label_flowrate_upstream.setText)
		self.fluidController.signal_volume_ul.connect(self.microcontrollerStateDisplayWidget.label_dispensed_volume.setText)

		# highlight current sequence
		self.fluidController.signal_highlight_current_sequence.connect(self.sequenceWidget.select_row_using_sequence_name)

		# connection for the manual control
		self.fluidController.signal_uncheck_manual_control_enabled.connect(self.manualControlWidget.uncheck_enable_manual_control_button)

		# transfer the layout to the central widget
		self.centralWidget = QWidget()
		self.centralWidget.setLayout(layout)
		self.setCentralWidget(self.centralWidget)

	def disableManualControlWidget(self):
		self.tabWidget.setTabEnabled(1,False)
		self.preUseCheckWidget.setEnabled(False)

	def enableManualControlWidget(self):
		self.tabWidget.setTabEnabled(1,True)
		self.preUseCheckWidget.setEnabled(True)

	def disableSequenceWidget(self):
		self.tabWidget.setTabEnabled(0,False)

	def enableSequenceWidget(self):
		self.tabWidget.setTabEnabled(0,True)

	def update_stopwatch_display(self,text):
		if 'stop watch remaining time' in self.logWidget.item(self.logWidget.count()-1).text():
			# use this if statement to prevent other messages being overwritten
			self.logWidget.item(self.logWidget.count()-1).setText(text)

	def highlight_current_log_item(self):
		self.logWidget.setCurrentRow(self.logWidget.count()-1)
		
	def closeEvent(self, event):
		self.fluidController.close()
		self.sequenceWidget.close()
		event.accept()
