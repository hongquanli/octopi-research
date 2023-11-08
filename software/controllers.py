# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# other libraries
import fluidics.utils as utils
import platform
import serial
import serial.tools.list_ports
import io
import sys
import time
import queue
from pathlib import Path
import numpy as np
from datetime import datetime

PRINT_DEBUG_INFO = True

from fluidics._def import *

'''
trigger control
'''

INTERVAL_SCANNING_TRIGGER_IN_ms = 50
BYTE_SEND_TRIGGER = 'T'.encode()
BYTE_TRIGGER_RECEIVED = 'T'.encode()

class trigger_controller_arduino(object):
	def __init__(self):
		# locate serial port
		arduino_ports = [
				p.device
				for p in serial.tools.list_ports.comports()
				if 'Arduino' in p.description]
		if not arduino_ports:
			raise IOError("No Arduino found")
		if len(arduino_ports) > 1:
			warnings.warn('Multiple Arduinos found - using the first')
			print('Using Arduino found at : {}'.format(arduino_ports[0]))			
		# establish serial communication
		self.serial = serial.Serial(arduino_ports[0],2000000)
		utils.print_message('Trigger Controller Connected')
		time.sleep(0.2)
	
	def __del__(self):
		self.serial.close()

	def send_trigger(self):
		self.serial.write(BYTE_SEND_TRIGGER)

class TriggerController(QObject):

	triggerReceived = Signal()
	log_message = Signal(str)
	signal_log_highlight_current_item = Signal()

	def __init__(self):
		QObject.__init__(self)
		self.microcontroller = trigger_controller_arduino()
		self.timer_listening_for_trigger_in = QTimer()
		self.timer_listening_for_trigger_in.setInterval(INTERVAL_SCANNING_TRIGGER_IN_ms)
		self.timer_listening_for_trigger_in.timeout.connect(self.scan_trigger_in)
		self.timer_listening_for_trigger_in.start()
		self.trigger_received = False

	def send_trigger(self):
		self.microcontroller.send_trigger()
		self.log_message.emit(utils.timestamp() + 'Microscope Trigger Sent')
		self.signal_clear_highlight.emit()
		self.signal_highlight_current_sequence.emit(self.current_sequence.sequence_name)
		QApplication.processEvents()

	def scan_trigger_in(self):
		if self.microcontroller.serial.in_waiting==0:
			return
		byte_received = self.microcontroller.serial.read()
		if byte_received == BYTE_TRIGGER_RECEIVED:
			self.trigger_received = True
			self.triggerReceived.emit()
			self.log_message.emit(utils.timestamp() + 'Trigger Received - Imaging Completed')
			self.signal_clear_highlight.emit()
			self.signal_log_highlight_current_item.emit()
			QApplication.processEvents()

class TriggerController_simulation(QObject):

	triggerReceived = Signal()
	log_message = Signal(str)
	signal_log_highlight_current_item = Signal()

	def __init__(self):
		QObject.__init__(self)
		self.timer_listening_for_trigger_in = QTimer()
		self.timer_listening_for_trigger_in.setInterval(3000)
		self.timer_listening_for_trigger_in.timeout.connect(self.scan_trigger_in)
		# self.timer_listening_for_trigger_in.start()
		self.trigger_received = False

	def send_trigger(self):
		self.log_message.emit(utils.timestamp() + 'Microscope Trigger Sent')
		self.signal_clear_highlight.emit()
		self.signal_log_highlight_current_item.emit()
		QApplication.processEvents()

	def scan_trigger_in(self):
		self.trigger_received = True
		self.triggerReceived.emit()
		self.log_message.emit(utils.timestamp() + 'Trigger Received - Imaging Completed')
		self.signal_clear_highlight.emit()
		self.signal_log_highlight_current_item.emit()
		QApplication.processEvents()

'''
fluid control
'''

class Microcontroller(object):
	def __init__(self,serial_number):
		self.serial = None
		self.tx_buffer_length = MCU_CMD_LENGTH
		self.rx_buffer_length = MCU_MSG_LENGTH

		controller_ports = [ p.device for p in serial.tools.list_ports.comports() if serial_number == p.serial_number]
		if not controller_ports:
			raise IOError("No Controller Found")
		self.serial = serial.Serial(controller_ports[0],2000000)
		utils.print_message('Teensy connected')
		# clear counter - @@@ to add

	def __del__(self):
		self.serial.close()

	def read_received_packet_nowait(self):
		# wait to receive data
		if self.serial.in_waiting==0:
			return None
		if self.serial.in_waiting % self.rx_buffer_length != 0:
			return None
		
		# get rid of old data
		num_bytes_in_rx_buffer = self.serial.in_waiting
		if num_bytes_in_rx_buffer > self.rx_buffer_length:
			# print('getting rid of old data')
			for i in range(num_bytes_in_rx_buffer-self.rx_buffer_length):
				self.serial.read()

		# read the buffer
		data=[]
		for i in range(self.rx_buffer_length):
			data.append(ord(self.serial.read()))
		return data

	def send_command(self,cmd):
		self.serial.write(cmd)

class Microcontroller_Simulation(object):
	def __init__(self):
		self.serial = None
		self.tx_buffer_length = MCU_CMD_LENGTH
		self.rx_buffer_length = MCU_MSG_LENGTH
		utils.print_message('MCU simulator connected')		

		# for simulation 
		self.timer_update_command_execution_status = QTimer()
		self.timer_update_command_execution_status.timeout.connect(self._simulation_update_cmd_execution_status)
		self.cmd_execution_status = 0
		self.current_cmd = 0
		self.current_cmd_uid = 0
	
	def __del__(self):
		pass

	def read_received_packet_nowait(self):
		msg=[]
		for i in range(self.rx_buffer_length):
			msg.append(0)
		msg[0] = self.current_cmd_uid >> 8
		msg[1] = self.current_cmd_uid & 0xff
		msg[2] = self.current_cmd
		msg[3] = self.cmd_execution_status
		# if PRINT_DEBUG_INFO:
		# 	print('### msg from the MCU: ' + str(msg) + ']')
		return msg

	def send_command(self,cmd):
		self.current_cmd_uid = (cmd[0] << 8) + cmd[1]
		self.current_cmd = cmd[2]
		self.cmd_execution_status = CMD_EXECUTION_STATUS.IN_PROGRESS
		self.timer_update_command_execution_status.setInterval(2000)
		self.timer_update_command_execution_status.start()
		if PRINT_DEBUG_INFO:
			print('### cmd sent to mcu: ' + str(cmd))
			print('[ MCU current cmd uid is ' + str(self.current_cmd_uid) + ' ]')

	def _simulation_update_cmd_execution_status(self):
		print('simulation - MCU command execution finished')
		self.cmd_execution_status = CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS
		# self.cmd_execution_status = CMD_EXECUTION_STATUS.ERROR_CODE_EMPTYING_THE_FLUDIIC_LINE_FAILED
		# self.cmd_execution_status = CMD_EXECUTION_STATUS.ERROR_CODE_PREUSE_CHECK_FAILED
		# print('simulation - MCU command execution error')
		# self.cmd_execution_status = CMD_EXECUTION_STATUS.CMD_EXECUTION_ERROR
		self.timer_update_command_execution_status.stop()

#######################################################
################# Sequence Defination #################
#######################################################
class Sequence():
	# TODO: Implement post-flow sequence
	#                 sequence_name,fluidic_port,flow_time_s,incubation_time_min,post_fluidic_port,post_flow_time_s,pressure_setting,aspiration_pump_power,aspiration_time_s,round_,port_name)
	def __init__(self,sequence_name,fluidic_port=None,flow_time_s=None,incubation_time_min=None,post_fluidic_port=None,post_flow_time_s=None,pressure_setting=None,aspiration_pump_power=None,aspiration_time_s=None,round_=1,port_name = None):
		self.sequence_name = sequence_name
		self.fluidic_port = fluidic_port
		self.flow_time_s = flow_time_s
		self.incubation_time_min = incubation_time_min
		self.post_fluidic_port = post_fluidic_port
		self.post_flow_time_s = post_flow_time_s
		self.pressure_setting = pressure_setting
		self.round = round_
		self.port_name = port_name

		self.sequence_started = False  # can be removed
		self.sequence_finished = False # can be removed
		self.queue_subsequences = queue.Queue()

		self.is_single_round_sequence = False

		self.disable_manual_control = False

		# populate the queue of subsequences, depending on the tyepes of the sequence
		# case 1: strip, wash (post-strip), ligate, wash (post-ligate), stain with DAPI
		# case 2: add imaging buffer
		# case 3: remove imaging buffer (can apply to removing any other liquid)

		# case 3, remove medium
		if sequence_name == 'Remove Medium':
			# subsequence 1
			mcu_command = Microcontroller_Command(CMD_SET.REMOVE_MEDIUM,payload3=int(65535*aspiration_pump_power),payload4=aspiration_time_s*1000)
			mcu_command.set_description(CMD_SET_DESCRIPTION.REMOVE_MEDIUM)
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True
			self.disable_manual_control = True

		# case 2, add imaging buffer
		if sequence_name == 'Add Imaging Buffer':
			# subsequence 1
			control_type = DEFAULT_VALUES.control_type_for_adding_medium
			if control_type == MCU_CMD_PARAMETERS.CONSTANT_POWER:
				pump_power = DEFAULT_VALUES.pump_power_for_adding_medium_constant_power_mode # *** make this adjustable in the GUI ***
				payload3 = pump_power*65535 # *** make this adjustable in the GUI ***
				# *** to do: add timeout limit ***
			if control_type == MCU_CMD_PARAMETERS.CONSTANT_PRESSURE:
				payload3 = ((DEFAULT_VALUES.pressure_setpoint_for_pumping_fluid_constant_pressure_mode)/PRESSURE_FULL_SCALE_PSI)*65535
			payload4 = flow_time_s*1000
			mcu_command = Microcontroller_Command(CMD_SET.ADD_MEDIUM,control_type,fluidic_port,payload3,payload4)
			mcu_command.set_description(CMD_SET_DESCRIPTION.ADD_MEDIUM + ' from port ' + str(fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			payload4 = post_flow_time_s * 1000
			if post_fluidic_port != 0:
				mcu_command = Microcontroller_Command(CMD_SET.ADD_MEDIUM,control_type,post_fluidic_port,payload3,payload4)
				mcu_command.set_description(CMD_SET_DESCRIPTION.ADD_MEDIUM + ' from port ' + str(post_fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
				self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			else:
				mcu_command = Microcontroller_Command(CMD_SET.EMPTY_FLUIDIC_LINE,control_type,post_fluidic_port,payload3,payload4)
				mcu_command.set_description(CMD_SET_DESCRIPTION.EMPTY_LINE + ' from port ' + str(post_fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
				self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))

			self.is_single_round_sequence = True
			self.disable_manual_control = True

		# case 1, add medium, incubate for specified amount of time, remove medium
		# use incubation_time_min to detect this kind of command
		if incubation_time_min is not None and incubation_time_min >= 0 and fluidic_port > 0:
			# subsequence 1: add medium
			control_type = DEFAULT_VALUES.control_type_for_adding_medium
			if control_type == MCU_CMD_PARAMETERS.CONSTANT_POWER:
				pump_power = DEFAULT_VALUES.pump_power_for_adding_medium_constant_power_mode # *** make this adjustable in the GUI ***
				payload3 = pump_power*65535 # *** make this adjustable in the GUI ***
				# *** to do: add timeout limit ***
			if control_type == MCU_CMD_PARAMETERS.CONSTANT_PRESSURE:
				payload3 = ((DEFAULT_VALUES.pressure_setpoint_for_pumping_fluid_constant_pressure_mode)/PRESSURE_FULL_SCALE_PSI)*65535
			payload4 = flow_time_s*1000
			mcu_command = Microcontroller_Command(CMD_SET.ADD_MEDIUM,control_type,fluidic_port,payload3,payload4)
			mcu_command.set_description(CMD_SET_DESCRIPTION.ADD_MEDIUM + ' from port ' + str(fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			payload4 = post_flow_time_s * 1000
			if post_fluidic_port != 0:
				mcu_command = Microcontroller_Command(CMD_SET.ADD_MEDIUM,control_type,post_fluidic_port,payload3,payload4)
				mcu_command.set_description(CMD_SET_DESCRIPTION.ADD_MEDIUM + ' from port ' + str(post_fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
				self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			else:
				mcu_command = Microcontroller_Command(CMD_SET.EMPTY_FLUIDIC_LINE,control_type,post_fluidic_port,payload3,payload4)
				mcu_command.set_description(CMD_SET_DESCRIPTION.EMPTY_LINE + ' from port ' + str(post_fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
				self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			# subsequence 2: incubate
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.COMPUTER_STOPWATCH,microcontroller_command=None,stopwatch_time_remaining_seconds=incubation_time_min*60))

			# subsequence 3: remove medium
			mcu_command = Microcontroller_Command(CMD_SET.REMOVE_MEDIUM,payload3=int(65535*aspiration_pump_power),payload4=aspiration_time_s*1000)
			mcu_command.set_description(CMD_SET_DESCRIPTION.REMOVE_MEDIUM)
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))

			self.is_single_round_sequence = False # for message display only, no other essence
			self.disable_manual_control = True

		# case 4: flush
		if sequence_name == 'Flush':
			control_type = DEFAULT_VALUES.control_type_for_adding_medium
			if control_type == MCU_CMD_PARAMETERS.CONSTANT_POWER:
				pump_power = DEFAULT_VALUES.pump_power_for_adding_medium_constant_power_mode # *** make this adjustable in the GUI ***
				payload3 = pump_power*65535 # *** make this adjustable in the GUI ***
				# *** to do: add timeout limit ***
			if control_type == MCU_CMD_PARAMETERS.CONSTANT_PRESSURE:
				payload3 = ((pressure_setting)/PRESSURE_FULL_SCALE_PSI)*65535
			payload4 = flow_time_s*1000
			mcu_command = Microcontroller_Command(CMD_SET.ADD_MEDIUM,control_type,fluidic_port,payload3,payload4)
			mcu_command.set_description('Flush line ' + str(fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			payload4 = post_flow_time_s * 1000
			if post_fluidic_port != 0:
				mcu_command = Microcontroller_Command(CMD_SET.ADD_MEDIUM,control_type,post_fluidic_port,payload3,payload4)
				mcu_command.set_description(CMD_SET_DESCRIPTION.ADD_MEDIUM + ' from port ' + str(post_fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
				self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			else:
				mcu_command = Microcontroller_Command(CMD_SET.EMPTY_FLUIDIC_LINE,control_type,post_fluidic_port,payload3,payload4)
				mcu_command.set_description(CMD_SET_DESCRIPTION.EMPTY_LINE + ' from port ' + str(post_fluidic_port) + ' using ' + MCU_CMD_PARAMETERS_DESCRIPTION.CONSTANT_POWER + ' mode, duration: ' + str(flow_time_s) + ' s')
				self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True
			self.disable_manual_control = True

		# preuse check sequences
		if sequence_name == 'Preuse Check (Pressure)':
			mcu_command = Microcontroller_Command(CMD_SET.PREUSE_CHECK_PRESSURE,payload2=fluidic_port,
				payload3=(pressure_setting/PRESSURE_FULL_SCALE_PSI)*65535,payload4=flow_time_s*1000)
			mcu_command.set_description('Preuse Check For Port ' + str(fluidic_port))
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True
			self.disable_manual_control = True

		if sequence_name == 'Preuse Check (Vacuum)':
			mcu_command = Microcontroller_Command(CMD_SET.PREUSE_CHECK_VACUUM,payload2=fluidic_port,
				payload3=(pressure_setting/PRESSURE_FULL_SCALE_PSI)*65535,payload4=flow_time_s*1000)
			mcu_command.set_description('Preuse Check (Vacuum)')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True
			self.disable_manual_control = True


		# manual control sequences
		# case 10
		if sequence_name == 'Set Selector Valve Position':
			mcu_command = Microcontroller_Command(CMD_SET.SET_SELECTOR_VALVE,payload2=fluidic_port)
			mcu_command.set_description('Set Selector Valve Position to ' + str(fluidic_port))
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Set 10 mm Valve State':
			mcu_command = Microcontroller_Command(CMD_SET.SET_10MM_SOLENOID_VALVE,payload2=fluidic_port)
			if fluidic_port == 0:
				mcu_command.set_description('Turn Off All 10 mm Valves')
			else:
				mcu_command.set_description('Turn On 10 mm valve ' + str(fluidic_port))
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Enable Manual Control':
			mcu_command = Microcontroller_Command(CMD_SET.DISABLE_MANUAL_CONTROL,payload1=0)
			mcu_command.set_description('Enable Manual Control (the hardware enable button still needs to be set)')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Disable Manual Control':
			mcu_command = Microcontroller_Command(CMD_SET.DISABLE_MANUAL_CONTROL,payload1=1)
			mcu_command.set_description('Disable Manual Control')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Connect Selector Valve and Chamber':
			mcu_command = Microcontroller_Command(CMD_SET.SET_SOLENOID_VALVE_B,payload1=1)
			mcu_command.set_description('Connect Selector Valve and Chamber')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Disconnect Selector Valve and Chamber':
			mcu_command = Microcontroller_Command(CMD_SET.SET_SOLENOID_VALVE_B,payload1=0)
			mcu_command.set_description('Disconnect Selector Valve and Chamber')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Enable Pressure Control Loop':
			mcu_command = Microcontroller_Command(CMD_SET.ENABLE_PRESSURE_CONTROL_LOOP,payload1=1)
			mcu_command.set_description('Enable Pressure Control Loop')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Disable Pressure Control Loop':
			mcu_command = Microcontroller_Command(CMD_SET.ENABLE_PRESSURE_CONTROL_LOOP,payload1=0)
			mcu_command.set_description('Disable Pressure Control Loop')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Set Pressure Control Setpoint (psi)':
			mcu_command = Microcontroller_Command(CMD_SET.SET_PRESSURE_CONTROL_SETPOINT_PSI,payload3=(pressure_setting/PRESSURE_FULL_SCALE_PSI)*65535)
			mcu_command.set_description('Set Pressure Control Setpoint to ' + str(pressure_setting) + ' psi')
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Set Pressure Loop P Coefficient':
			mcu_command = Microcontroller_Command(CMD_SET.SET_PRESSURE_CONTROL_LOOP_P_COEFFICIENT,payload4=(pressure_setting/PRESSURE_LOOP_COEFFICIENTS_FULL_SCALE)*4294967295)
			mcu_command.set_description('Set Pressure Loop P Coefficient to ' + str(pressure_setting))
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

		if sequence_name == 'Set Pressure Loop I Coefficient':
			mcu_command = Microcontroller_Command(CMD_SET.SET_PRESSURE_CONTROL_LOOP_I_COEFFICIENT,payload4=(pressure_setting/PRESSURE_LOOP_COEFFICIENTS_FULL_SCALE)*4294967295)
			mcu_command.set_description('Set Pressure Loop I Coefficient to ' + str(pressure_setting))
			self.queue_subsequences.put(Subsequence(SUBSEQUENCE_TYPE.MCU_CMD,mcu_command))
			self.is_single_round_sequence = True

class Subsequence():
	def __init__(self,subsequence_type=None,microcontroller_command=None,stopwatch_time_remaining_seconds=None):
		self.type = subsequence_type
		self.microcontroller_command = microcontroller_command
		self.stopwatch_time_remaining_seconds = stopwatch_time_remaining_seconds

# utility function for converting pressure sensor raw reading to psi
def constrain(val, min_val, max_val):
    return min(max_val, max(min_val, val))

class Microcontroller_Command():
	def __init__(self,cmd,payload1=0,payload2=0,payload3=0,payload4=0,timeout_limit=0):
		self.cmd = cmd
		self.payload1 = payload1
		self.payload2 = payload2
		self.payload3 = payload3
		self.payload4 = payload4
		self.description = ''
		self.timeout_limit = timeout_limit

	def get_ready_to_decorate_cmd_packet(self):
		return self._format_command()

	def get_description(self):
		return self.description

	def set_description(self,description):
		self.description = description

	def _format_command(self):
		cmd_packet = bytearray(MCU_CMD_LENGTH)
		cmd_packet[0] = 0 # reserved byte for UID
		cmd_packet[1] = 0 # reserved byte for UID
		cmd_packet[2] = self.cmd
		cmd_packet[3] = self.payload1
		cmd_packet[4] = int(self.payload2)
		cmd_packet[5] = int(self.payload3) >> 8
		cmd_packet[6] = int(self.payload3) & 0xff
		cmd_packet[7] = int(self.payload4) >> 24
		cmd_packet[8] = (int(self.payload4) >> 16) & 0xff
		cmd_packet[9] = (int(self.payload4) >> 8) & 0xff
		cmd_packet[10] = int(self.payload4) & 0xff
		print([b for b in cmd_packet])
		return cmd_packet

class FluidController(QObject):
	
	log_message = Signal(str)
	signal_log_highlight_current_item = Signal()
	signal_update_stopwatch_display = Signal(str)
	signal_initialize_stopwatch_display = Signal(str)
	signal_sequences_execution_started = Signal()
	signal_sequences_execution_stopped = Signal()
	signal_highlight_current_sequence = Signal(str)
	signal_clear_highlight = Signal()

	# for displaying the MCU states
	signal_MCU_CMD_UID = Signal(int)
	signal_MCU_CMD = Signal(int)     # @@@ to-do: map the command to the command description
	signal_MCU_CMD_status = Signal(str)
	signal_MCU_internal_program = Signal(str)
	signal_MCU_CMD_time_elapsed = Signal(int)

	signal_pump_power = Signal(str)
	signal_selector_valve_position = Signal(int)
	signal_pressure = Signal(str)
	signal_vacuum = Signal(str)
	signal_bubble_sensor_1 = Signal(bool)
	signal_bubble_sensor_2 = Signal(bool)
	signal_flow_upstream = Signal(str)
	signal_volume_ul = Signal(str)

	signal_uncheck_manual_control_enabled = Signal()

	signal_uncheck_all_sequences = Signal()

	signal_preuse_check_result = Signal(str,bool)

	def __init__(self,microcontroller,log_measurements=False):
		QObject.__init__(self)
		self.microcontroller = microcontroller		
		self.cmd_length = MCU_CMD_LENGTH

		# clear counter on both the computer and the MCU
		self.computer_to_MCU_command_counter = 0 # this is the UID
		self.computer_to_MCU_command = CMD_SET.CLEAR # when init the MCU in the firmware, set computer_to_MCU_command = 255 (reserved), so that there will be mismatch until proper communication
		mcu_cmd = Microcontroller_Command(self.computer_to_MCU_command)
		cmd_packet = mcu_cmd.get_ready_to_decorate_cmd_packet()
		cmd_packet = self._add_UID_to_mcu_command_packet(cmd_packet,self.computer_to_MCU_command_counter)
		self.microcontroller.send_command(cmd_packet)

		self.abort_sequences_requested = False
		self.sequences_in_progress = False
		self.current_sequence = None

		self.subsequences_in_progress = False
		self.current_subsequence = None
		self.current_stopwatch = None

		self.mcu_subsequence_in_progress = False
		self.computer_stopwatch_subsequence_in_progress = False

		self.queue_sequence = queue.Queue()
		self.queue_subsequence = queue.Queue()
		# self.queque_to_microcontroller_command_packet = queue.Queue() # no longer needed - each cmd correspond to one subsequence

		self.timer_check_microcontroller_state = QTimer()
		self.timer_check_microcontroller_state.setInterval(TIMER_CHECK_MCU_STATE_INTERVAL_MS)
		self.timer_check_microcontroller_state.timeout.connect(self._check_microcontroller_state)
		self.timer_check_microcontroller_state.start()

		self.timer_update_sequence_execution_state = QTimer()
		self.timer_update_sequence_execution_state.setInterval(TIMER_CHECK_SEQUENCE_EXECUTION_STATE_INTERVAL_MS)
		self.timer_update_sequence_execution_state.timeout.connect(self._update_sequence_execution_state)

		self.timestamp_last_computer_mcu_mismatch = None

		self.log_measurements = log_measurements
		if(self.log_measurements):
			self.measurement_file = open(os.path.join(Path.home(),"Downloads","Fluidic Controller Logged Measurement_" + datetime.now().strftime('%Y-%m-%d %H-%M-%S.%f') + ".csv"), "w+")
			self.counter_measurement_file_flush = 0

	def _add_UID_to_mcu_command_packet(self,cmd,command_UID):
		cmd[0] = command_UID >> 8
		cmd[1] = command_UID & 0xff
		return cmd

	def _current_stopwatch_timeout_callback(self):
		self.current_stopwatch.stop() # make sure to stop the stopwatch first
		self.computer_stopwatch_subsequence_in_progress = False
		self.log_message.emit(utils.timestamp() + '[ countdown of ' + str(self.current_subsequence.stopwatch_time_remaining_seconds/60) + ' min finished ]')
		self.signal_clear_highlight.emit()
		self.signal_log_highlight_current_item.emit()
		QApplication.processEvents()
		self.current_stopwatch = None
		self.current_subsequence = None

	# <<< core portion of the program>>>
	def _update_sequence_execution_state(self):
		# previous sequence finished execution, now try to load the next sequence
		if self.current_sequence == None and self.current_subsequence == None:
			# if the queue is not empty, load the next sequence to execute
			if self.queue_sequence.empty() == False:
				# start a new queued sequence if no abort sequence requested
				if self.abort_sequences_requested == False:
					# pull the next sequence from the queue
					self.current_sequence = self.queue_sequence.get()
					# logging (display round number for multiround sequences)
					if self.current_sequence.is_single_round_sequence == False:
						self.log_message.emit(utils.timestamp() + 'Execute ' + self.current_sequence.sequence_name + ', round ' + str(self.current_sequence.round+1))
					else:
						self.log_message.emit(utils.timestamp() + 'Execute ' + self.current_sequence.sequence_name)
					self.signal_clear_highlight.emit()
					self.signal_highlight_current_sequence.emit(self.current_sequence.sequence_name)
					QApplication.processEvents()
					self.sequence_started = True # can be removed
				# abort sequence is requested
				else:
					while self.queue_sequence.empty() == False:
						self.current_sequence = self.queue_sequence.get()
						if self.current_sequence.is_single_round_sequence == False:
							self.log_message.emit(utils.timestamp() + '! ' + self.current_sequence.sequence_name + ', round ' + str(self.current_sequence.round+1) + ' aborted')
						else:
							self.log_message.emit(utils.timestamp() + '! ' + self.current_sequence.sequence_name + ' aborted')
						self.signal_clear_highlight.emit()
						self.signal_highlight_current_sequence.emit(self.current_sequence.sequence_name)
						QApplication.processEvents()
						self.current_sequence.sequence_started = False
						# void the sequence
						self.current_sequence = None 
					self.signal_clear_highlight.emit()
					self.log_message.emit(utils.timestamp() + 'Abort completed')
					self.signal_clear_highlight.emit()
					self.signal_log_highlight_current_item.emit()
					QApplication.processEvents()
					return
			# if the queue is empty, set the sequences_in_progress flag to False
			else:
				self.sequences_in_progress = False
				self.timer_update_sequence_execution_state.stop()
				self.signal_uncheck_all_sequences.emit()
				self.signal_sequences_execution_stopped.emit()
				self.log_message.emit(utils.timestamp() + 'Finished executing all the selected sequences')
				self.signal_clear_highlight.emit()
				self.signal_log_highlight_current_item.emit()
				QApplication.processEvents()
				if PRINT_DEBUG_INFO:
					print('no more sequences in the queue')
				return
		# else:
		# [removed else, so that the new sequence can be executed in the same call of the callback function]
		# [if there's no current sequence, the function would have already returned]

		# work on the subsequences of the current sequence
		# [the below code is directly derived from the above]
		# if the queue is not empty, load the next subsequence to execute
		if self.current_subsequence == None:
			if self.current_sequence.queue_subsequences.empty() == False:
				if self.abort_sequences_requested == False:
					# start a new subsequence if no abort sequence requested
					self.current_subsequence = self.current_sequence.queue_subsequences.get()
					if self.current_subsequence.type == SUBSEQUENCE_TYPE.MCU_CMD:
						mcu_cmd = self.current_subsequence.microcontroller_command
						cmd_packet = mcu_cmd.get_ready_to_decorate_cmd_packet()
						# update the computer command counter and register the command
						self.computer_to_MCU_command_counter = self.computer_to_MCU_command_counter + 1 # UID for the command
						self.computer_to_MCU_command = cmd_packet[2]
						# set the mcu_subsequence_in_progress flag
						self.mcu_subsequence_in_progress = True # important: set it *after* the new UID is recorded , *before* sending the new command to MCU
						# send the command to the microcontroller
						cmd_with_uid = self._add_UID_to_mcu_command_packet(cmd_packet,self.computer_to_MCU_command_counter)
						self.microcontroller.send_command(cmd_with_uid)
						self.log_message.emit(utils.timestamp() + '[ microcontroller: ' + self.current_subsequence.microcontroller_command.get_description() +  ' ]')
						self.signal_clear_highlight.emit()
						self.signal_log_highlight_current_item.emit()
						QApplication.processEvents()
					elif self.current_subsequence.type == SUBSEQUENCE_TYPE.COMPUTER_STOPWATCH:
						self.current_stopwatch = QTimer()
						self.current_stopwatch.setInterval(self.current_subsequence.stopwatch_time_remaining_seconds*1000)
						# self.current_stopwatch.setInterval(self.current_subsequence.stopwatch_time_remaining_seconds*1000/60) # for simulation, speed up by 60x
						self.current_stopwatch.timeout.connect(self._current_stopwatch_timeout_callback)
						self.current_stopwatch.start()
						self.computer_stopwatch_subsequence_in_progress = True
						self.log_message.emit(utils.timestamp() + '[ countdown of ' + str(self.current_subsequence.stopwatch_time_remaining_seconds/60) + ' min started ]')
						self.signal_clear_highlight.emit()
						self.signal_log_highlight_current_item.emit()
						self.signal_initialize_stopwatch_display.emit(utils.timestamp() + '[ stop watch remaining time: ' + str(int(self.current_stopwatch.remainingTime()/1000)) + ' seconds ]') # @@@ change format to to x min x s
						self.signal_clear_highlight.emit()
						self.signal_log_highlight_current_item.emit()
						QApplication.processEvents()
				else:
					# abort sequence is requested
					while self.current_sequence.queue_subsequences.empty() == False:
						self.current_subsequence = self.current_sequence.queue_subsequences.get()
						self.current_subsequence = None
					self.current_sequence = None
					return
			else:
				# finished executing all the subsequences of the current sequence
				self.current_sequence.sequence_finished = True # can be removed
				self.current_sequence = None
				# can add a signal here to set the sequence text to green #TO-DO

		# case for updating the stopwatch display
		if self.computer_stopwatch_subsequence_in_progress == True:
			self.signal_update_stopwatch_display.emit(utils.timestamp() + '[ stop watch remaining time: ' + str(int(self.current_stopwatch.remainingTime()/1000)) + ' seconds ]') # @@@ change format to to x min x s
			self.signal_log_highlight_current_item.emit()

		# case for handling abort request during computer stopwatch countdown
		if self.computer_stopwatch_subsequence_in_progress == True and self.abort_sequences_requested == True:
			self.log_message.emit(utils.timestamp() + '[ countdown of ' + str(self.current_subsequence.stopwatch_time_remaining_seconds/60) + ' min aborted ]')
			self.signal_clear_highlight.emit()
			self.signal_log_highlight_current_item.emit()
			QApplication.processEvents()
			self.current_stopwatch.stop()
			self.current_stopwatch = None
			self.computer_stopwatch_subsequence_in_progress = False
			self.current_subsequence = None

	# <<< core portion of the computer - MCU interation >>>
	def _check_microcontroller_state(self):
		# check the microcontroller state, if mcu cmd execution has completed, send new mcu cmd in the queue
		msg = self.microcontroller.read_received_packet_nowait()
		if msg is None:
			return

		'''
		#########################################################
		#########   MCU -> Computer message structure   #########
		#########################################################
		byte 0-1	: computer -> MCU CMD counter (UID)
		byte 2  	: cmd from host computer (error checking through check sum => no need to transmit back the parameters associated with the command)
				  	<see below for command set>
		byte 3  	: status of the command
						- 1: in progress
						- 0: completed without errors
						- 2: error in cmd check sum
						- 3: invalid cmd
						- 4: error during execution
		byte 4  	: MCU internal program being executed
						- 0: idle
					  	<see below for command set>
		byte 5  	: state of valve A1,A2,B1,B2,bubble_sensor_1,bubble_sensor_2,x,x
		byte 6  	: state of valve C1-C7, manual input bit
		byte 7-8	: state of valve D1-D16
		byte 9		: state of selector valve
		byte 10-11	: pump power
		byte 12-13	: pressure sensor 1 reading
		byte 13-15	: pressure sensor 2 reading
		byte 16-17	: flow sensor 1 reading
		byte 18-19	: flow sensor 2 reading
		byte 20     : elapsed time since the start of the last internal program (in seconds)
		byte 21-22  : volume (ul), range: 0 - 5000
		byte 23-24  : reserved

		'''
		
		#print (' '.join('{:02x}'.format(x) for x in msg))
		# parse packet, step 0: display parsed packet (to add)
		MCU_received_command_UID = (msg[0] << 8) + msg[1] # the parentheses around << is necessary !!!
		MCU_received_command = msg[2]
		MCU_command_execution_status = msg[3]
		MCU_interal_program = msg[4]
		fluids = msg[5]
		MCU_CMD_time_elapsed = msg[20]
		if PRINT_DEBUG_INFO:
			try:
				print((MCU_STATUS[MCU_command_execution_status],MCU_INTERNAL_PROGRAMS[MCU_interal_program]))
			except:
				print("OOB")
				print((str(MCU_command_execution_status), str(MCU_interal_program)))
			
		# unpack fluids
		# fluids |= ((OCB350_0_reading) & 0x01) << 0;
		# fluids |= ((OCB350_0_debounced) & 0x01) << 1;
		# fluids |= ((OCB350_1_reading) & 0x01) << 2;
		# fluids |= ((OCB350_1_debounced) & 0x01) << 3;
		# fluids |= (((SLF3X_0_readings[SLF3X_FLAG_IDX] & SLF3X_NO_FLUID) != 0) & 0x01) << 4;
		# fluids |= ((SLF3X_0_debounced) & 0x01) << 5;
		bubble_0 =      ((fluids  & (0x01 << 0)) != 0)
		bubble_0_db =   ((fluids  & (0x01 << 1)) != 0)
		bubble_1 =      ((fluids  & (0x01 << 2)) != 0)
		bubble_1_db =   ((fluids  & (0x01 << 3)) != 0)
		flow_fluid =    ((fluids  & (0x01 << 4)) != 0)
		flow_fluid_db = ((fluids  & (0x01 << 5)) != 0)
		
		measurement_selector_valve_position = msg[9]
		measurement_pump_power = float((int(msg[10])<<8)+msg[11])/65535
		_vacuum_raw  = constrain((int(msg[12])<<8) + msg[13],MCU_CONSTANTS._output_min,MCU_CONSTANTS._output_max)
		_pressure_raw = constrain((int(msg[14])<<8) + msg[15],MCU_CONSTANTS._output_min,MCU_CONSTANTS._output_max)
		measurement_pressure = (_pressure_raw - MCU_CONSTANTS._output_min) * (MCU_CONSTANTS._p_max - MCU_CONSTANTS._p_min) / (MCU_CONSTANTS._output_max - MCU_CONSTANTS._output_min) + MCU_CONSTANTS._p_min
		measurement_vacuum = (_vacuum_raw - MCU_CONSTANTS._output_min) * (MCU_CONSTANTS._p_max - MCU_CONSTANTS._p_min) / (MCU_CONSTANTS._output_max - MCU_CONSTANTS._output_min) + MCU_CONSTANTS._p_min
		
		_iirvacuum_raw  = constrain((int(msg[18])<<8) + msg[19],MCU_CONSTANTS._output_min,MCU_CONSTANTS._output_max)
		_iirpressure_raw = constrain((int(msg[23])<<8) + msg[24],MCU_CONSTANTS._output_min,MCU_CONSTANTS._output_max)
		measurement_iirpressure = (_iirpressure_raw - MCU_CONSTANTS._output_min) * (MCU_CONSTANTS._p_max - MCU_CONSTANTS._p_min) / (MCU_CONSTANTS._output_max - MCU_CONSTANTS._output_min) + MCU_CONSTANTS._p_min
		measurement_iirvacuum = (_iirvacuum_raw - MCU_CONSTANTS._output_min) * (MCU_CONSTANTS._p_max - MCU_CONSTANTS._p_min) / (MCU_CONSTANTS._output_max - MCU_CONSTANTS._output_min) + MCU_CONSTANTS._p_min
		
		#bubble_sensor_1_state = MCU_valve_A_B_and_bubble_sensors & 0b00001000
		#bubble_sensor_2_state = MCU_valve_A_B_and_bubble_sensors & 0b00000100
		flow_upstream = float(int.from_bytes(msg[16:17+1], byteorder='big', signed=True))/MCU_CONSTANTS.SCALE_FACTOR_FLOW
		# print(flow_upstream)
		volume_ul = (float(int.from_bytes(msg[21:22+1], byteorder='big', signed=True))/32767)*MCU_CONSTANTS.VOLUME_UL_MAX

		self.signal_MCU_CMD_UID.emit(MCU_received_command_UID)
		self.signal_MCU_CMD.emit(MCU_received_command) # @@@ to-do: map the command to the command description
		self.signal_MCU_CMD_time_elapsed.emit(MCU_CMD_time_elapsed)

		try:
			self.signal_MCU_CMD_status.emit(MCU_STATUS[MCU_command_execution_status])
		except:
			self.signal_MCU_CMD_status.emit(str(MCU_command_execution_status))
		try:
			self.signal_MCU_internal_program.emit(MCU_INTERNAL_PROGRAMS[MCU_interal_program])
		except:
			self.signal_MCU_internal_program.emit(str(MCU_interal_program))

		self.signal_pump_power.emit('{:.2f}'.format(measurement_pump_power))
		self.signal_selector_valve_position.emit(measurement_selector_valve_position)
		self.signal_pressure.emit('{:.2f}'.format(measurement_pressure))
		self.signal_vacuum.emit('{:.2f}'.format(measurement_vacuum))

		self.signal_bubble_sensor_1.emit(bubble_0>0)
		self.signal_bubble_sensor_2.emit(bubble_1>0)

		self.signal_flow_upstream.emit('{:.1f}'.format(flow_upstream))
		self.signal_volume_ul.emit('{:.1f}'.format(volume_ul))

		# step 1: check if MCU is "up to date" with the computer in terms of command
		#if (MCU_received_command_UID != self.computer_to_MCU_command_counter) or (MCU_received_command != self.computer_to_MCU_command):
		#	if PRINT_DEBUG_INFO:
		#		print('computer\t UID = ' + str(self.computer_to_MCU_command_counter) + ', CMD = ' + str(self.computer_to_MCU_command))
		#		print('MCU\t\t UID = ' + str(MCU_received_command_UID) + ', CMD = ' + str(MCU_received_command))
		#		print('----------------')
		#	if self.timestamp_last_computer_mcu_mismatch == None:
		#		self.timestamp_last_computer_mcu_mismatch = time.time() # new mismatch, record time stamp
		#		if PRINT_DEBUG_INFO:
		#			print('a new MCU received cmd out of sync with computer cmd occured')
		#	else:
		#		t_diff = time.time() - self.timestamp_last_computer_mcu_mismatch
		#		if t_diff > T_DIFF_COMPUTER_MCU_MISMATCH_FAULT_THRESHOLD_SECONDS:
		#			print('Fault! MCU and computer out of sync for more than 3 seconds')
		#			# @@@@@ to-do: add error handling @@@@@ #
		#	return
		#else:
		#	self.timestamp_last_computer_mcu_mismatch = None

		# step 2: check command execution on MCU
		if (MCU_command_execution_status != CMD_EXECUTION_STATUS.IN_PROGRESS) and (MCU_command_execution_status != CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS):
			# @@@@@ to-do: add error handling @@@@@ #
			# return # no need to return here
			if MCU_command_execution_status == CMD_EXECUTION_STATUS.ERROR_CODE_EMPTYING_THE_FLUDIIC_LINE_FAILED:
				# can add a signal here to set the sequence text to green #TO-DO
				# abort all the steps that follows
				if self.mcu_subsequence_in_progress:
					self.mcu_subsequence_in_progress = False
					self.current_subsequence = None
					self.abort_sequences_requested = True
					print('cmd execution error, status code: ' + str(MCU_command_execution_status))
					print('emptying fluidic line failed, all subsequent sequences aborted')
					self.log_message.emit(utils.timestamp() + '! emptying fluidic line failed, all subsequent sequences aborted !')
					msg = QMessageBox()
					msg.setIcon(QMessageBox.Information)
					msg.setText("Emptying Fluidic Line Failed")
					msg.setInformativeText("The fludic path has been switched to port 24. Now use a syringe to manually empty the fluidic line.")
					msg.setWindowTitle("Warning")
					msg.setStandardButtons(QMessageBox.Ok)
					msg.setDefaultButton(QMessageBox.Ok)
					retval = msg.exec_()

			if MCU_command_execution_status == CMD_EXECUTION_STATUS.ERROR_CODE_PREUSE_CHECK_FAILED:
				if self.mcu_subsequence_in_progress:
					# show preuse check result
					self.signal_preuse_check_result.emit(self.current_sequence.port_name,False)
					# close the current subsequence
					self.mcu_subsequence_in_progress = False
					self.current_subsequence = None
					self.log_message.emit(utils.timestamp() + '! preuse check for port ' + self.current_sequence.port_name + ' failed !')
					if PRINT_DEBUG_INFO:
						print('moving to the next subsequence (if any)')


		if MCU_command_execution_status == CMD_EXECUTION_STATUS.IN_PROGRESS:
			# the commented section below is not necessary, as when MCU_received_command_UID and MCU_received_command are set or initialized to 0, 
			# MCU_command_execution_status will also be set to CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS, 
			# i.e. under no circumstances, CMD_EXECUTION_STATUS.IN_PROGRESS would occur when MCU_received_command_UID == 0 and MCU_received_command == 0
			'''
			if MCU_received_command_UID == 0 and MCU_received_command == 0:
				pass # wait for the first command -> go ahead to load new command
			else:
				# command execution in progress
				if PRINT_DEBUG_INFO:
					print('cmd being executed on the MCU')
				return 
			'''
			# command execution in progress
			if PRINT_DEBUG_INFO:
				# print('[ cmd being executed on the MCU ]')
				pass
			# return # no need to return here

		if MCU_command_execution_status == CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS:
			# command execucation has completed, can move to the next command
			# important: only move to the next subsequence upon completion of a *MCU* subsequence
			if self.mcu_subsequence_in_progress:
				# show preuse check result
				if self.current_sequence.port_name is not None:
					self.signal_preuse_check_result.emit(self.current_sequence.port_name,True)
					self.log_message.emit(utils.timestamp() + 'Preuse check for port ' + self.current_sequence.port_name + ' passed')
				# close the current subsequence
				self.mcu_subsequence_in_progress = False
				self.current_subsequence = None
				if PRINT_DEBUG_INFO:
					print('moving to the next subsequence (if any)')

		''' moved to handling of queue of subsequences
		# step 3: send the new command to MCU
		if self.queque_to_microcontroller_command_packet.empty() == False:
			# get the new command to execute
			cmd_packet = self.queque_to_microcontroller_command_packet.get()
			self.computer_to_MCU_command_counter = self.computer_to_MCU_command_counter + 1
			self.computer_to_MCU_command = cmd_packet[2]
			# send the command to the microcontroller
			cmd_with_uid = self._add_UID_to_mcu_command_packet(cmd_packet,self.computer_to_MCU_command_counter)
			self.microcontroller.send_command(cmd_with_uid)
		'''

		# log measurement
		if(self.log_measurements):
			line = str(time.time()) + ',' + \
				str(MCU_received_command_UID) + ',' + \
				str(MCU_received_command) + ',' + \
				str(MCU_command_execution_status) + ',' + \
				str(MCU_interal_program) + ',' + \
				str(MCU_CMD_time_elapsed) + ',' + \
				str(measurement_selector_valve_position) + ',' + \
				str(int(bubble_0)) + ',' + \
				str(int(bubble_0_db)) + ',' + \
				str(int(bubble_1)) + ',' + \
				str(int(bubble_1_db)) + ',' + \
				str(int(flow_fluid)) + ',' + \
				str(int(flow_fluid_db)) + ',' + \
				"{:.2f}".format(measurement_pump_power) + ',' + \
				"{:.2f}".format(measurement_pressure) + ',' + \
				"{:.2f}".format(measurement_vacuum) + ',' + \
				"{:.2f}".format(measurement_iirpressure) + ',' + \
				"{:.2f}".format(measurement_iirvacuum) + ',' + \
				"{:.2f}".format(flow_upstream) + ',' + \
				"{:.2f}".format(volume_ul) + '\n'
			self.measurement_file.write(line)
			self.counter_measurement_file_flush = self.counter_measurement_file_flush + 1
			# print(self.counter_measurement_file_flush)
			if self.counter_measurement_file_flush>=500:
				self.counter_measurement_file_flush = 0
				self.measurement_file.flush()

	def add_sequence(self,sequence_name,fluidic_port=None,flow_time_s=None,incubation_time_min=None,post_fluidic_port=None,post_flow_time_s=None,pressure_setting=None,aspiration_pump_power=None,aspiration_time_s=None,round_=1,port_name=None):
		print('adding sequence to the queue ' + sequence_name + ' - flow time: ' + str(flow_time_s) + ' s, incubation time: ' + str(incubation_time_min) + ' min, post-flow clear time: ' + str(post_flow_time_s) + 's [negative number means no removal]')
		sequence_to_add = Sequence(sequence_name,fluidic_port,flow_time_s,incubation_time_min,post_fluidic_port,post_flow_time_s,pressure_setting,aspiration_pump_power,aspiration_time_s,round_,port_name)
		self.queue_sequence.put(sequence_to_add)
		if sequence_to_add.disable_manual_control == True:
			self.signal_uncheck_manual_control_enabled.emit()
		
			
	def request_abort_sequences(self):
		self.abort_sequences_requested = True

	def start_sequence_execution(self):
		self.abort_sequences_requested = False
		self.sequences_in_progress = True
		self.signal_sequences_execution_started.emit()
		self.timer_update_sequence_execution_state.start()

	def send_arbitrary_command(self,cmd,payload1,payload2,payload3,payload4):
		mcu_cmd = Microcontroller_Command(cmd,payload1,payload2,payload3,payload4)
		cmd_packet = mcu_cmd.get_ready_to_decorate_cmd_packet()
		cmd_packet = self._add_UID_to_mcu_command_packet(cmd_packet,self.computer_to_MCU_command_counter)
		self.microcontroller.send_command(cmd_packet)

	def close(self):
		if(self.log_measurements):
			self.measurement_file.close()

class Logger(QObject):

	def __init__(self,filepath = os.path.join(Path.home(),"Documents","starmap-automation logs.txt")):
		QObject.__init__(self)
		self.file = open(filepath,'a')

	def log(self,log_message):
		self.file.write(log_message + '\n')

	def __del__(self):
		self.file.close()
		
	def close(self):
		self.file.close()
