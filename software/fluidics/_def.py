Port = {}
Port['1'] = 1
Port['2'] = 2
Port['3'] = 3
Port['4'] = 4
Port['5'] = 5
Port['6'] = 6
Port['Stripping Buffer'] = 7
Port['Rendering Buffer'] = 8
Port['H2 Buffer'] = 9
# Port['DAPI'] = 10
Port['Air'] = 11
Port['Vacuum'] = 0

INCUBATION_TIME_MAX_MIN = 60*12
FLOW_TIME_MAX = 60 # in seconds
PRESSURE_FULL_SCALE_PSI = 5
PRESSURE_LOOP_COEFFICIENTS_FULL_SCALE = 100

SEQUENCE_ATTRIBUTES_KEYS = ['Sequence','Fluidic Port','Flow Time (s)','Incubation Time (min)','Post-Fill Fluidic Port', 'Post-Fill Flow Time (s)', 'Repeat','Include']
SEQUENCE_NAME = ['Remove Medium','Stripping Buffer Wash','Rendering Buffer Wash','Hybridize','Rendering Buffer Wash 2','Imaging Buffer Wash','Add Imaging Buffer']

TIMER_CHECK_MCU_STATE_INTERVAL_MS = 10 # make it half of send_update_interval_us in the firmware
# TIMER_CHECK_MCU_STATE_INTERVAL_MS = 500 # for simulation
TIMER_CHECK_SEQUENCE_EXECUTION_STATE_INTERVAL_MS = 50

# MCU
MCU_CMD_LENGTH = 15
MCU_MSG_LENGTH = 25

# MCU - COMPUTER
T_DIFF_COMPUTER_MCU_MISMATCH_FAULT_THRESHOLD_SECONDS = 3

class SUBSEQUENCE_TYPE:
	MCU_CMD = 'MCU CMD'
	COMPUTER_STOPWATCH = 'COMPUTER STOPWATCH'

PRINT_DEBUG_INFO = False

# status of command execution on the MCU
class CMD_EXECUTION_STATUS:
	COMPLETED_WITHOUT_ERRORS = 0
	IN_PROGRESS = 1
	CMD_CHECKSUM_ERROR = 2
	CMD_INVALID = 3
	CMD_EXECUTION_ERROR = 4
	ERROR_CODE_EMPTYING_THE_FLUDIIC_LINE_FAILED = 100
	ERROR_CODE_PREUSE_CHECK_FAILED = 110

#########################################################
############   Computer -> MCU command set   ############
#########################################################
class CMD_SET:
	CLEAR = 0
	REMOVE_MEDIUM = 1
	ADD_MEDIUM = 2
	EMPTY_FLUIDIC_LINE = 3
	SET_SELECTOR_VALVE = 10
	SET_10MM_SOLENOID_VALVE = 11
	SET_SOLENOID_VALVE_B = 12
	SET_SOLENOID_VALVE_C = 13
	DISABLE_MANUAL_CONTROL = 20
	ENABLE_PRESSURE_CONTROL_LOOP = 30
	SET_PRESSURE_CONTROL_SETPOINT_PSI = 31
	SET_PRESSURE_CONTROL_LOOP_P_COEFFICIENT = 32
	SET_PRESSURE_CONTROL_LOOP_I_COEFFICIENT = 33
	PREUSE_CHECK_PRESSURE = 40
	PREUSE_CHECK_VACUUM = 41

class CMD_SET_DESCRIPTION:
	CLEAR = 'Clear'
	REMOVE_MEDIUM = 'Remove Medium'
	ADD_MEDIUM = 'Add Medium'
	EMPTY_LINE = 'Empty the line'
	SET_SELECTOR_VALVE = '' # the description is manually added (with parameters)
	SET_10MM_SOLENOID_VALVE = '' # the description is manually added (with parameters)
	SET_SOLENOID_VALVE_B = '' # the description is manually added (with parameters)
	SET_SOLENOID_VALVE_C = '' # the description is manually added (with parameters)
	ENABLE_MANUAL_CONTROL = ''

class MCU_CMD_PARAMETERS:
	CONSTANT_POWER = 0
	CONSTANT_PRESSURE = 1
	CONSTANT_FLOW = 2
	VOLUME_CONTROL = 3

class MCU_CMD_PARAMETERS_DESCRIPTION:
	CONSTANT_POWER = 'constant power'
	CONSTANT_PRESSURE = 'constant pressure'
	CONSTANT_FLOW = 'constant flow'
	VOLUME_CONTROL = 'volume control'

class MCU_CONSTANTS:
	# pressure sensor SSCMRRV015PD2A3
	_output_min = 1638; # 10% of 2^14
	_output_max = 14745; # 90% of 2^14
	_p_min = -15; # psi
	_p_max = 15; # psi
	VOLUME_UL_MAX = 5000
	SCALE_FACTOR_FLOW = 10 # Scale Factor for flow rate measurement, ul/min, SLF3S-0600F

class DEFAULT_VALUES:
	aspiration_pump_power = 0.3
	vacuum_aspiration_time_s = 8
	aspiration_timeout_limit_s = 60 # to replace vacuum_aspiration_time_s once bubble sensor is in place
	# control_type_for_adding_medium = MCU_CMD_PARAMETERS.CONSTANT_POWER
	control_type_for_adding_medium = MCU_CMD_PARAMETERS.CONSTANT_PRESSURE
	pump_power_for_adding_medium_constant_power_mode = 0.8
	pressure_loop_p_gain = 1
	pressure_loop_i_gain = 1
	pressure_setpoint_for_pumping_fluid_constant_pressure_mode = 4.9

class PREUSE_CHECK_SETTINGS:
	TARGET_PRESSURE_AIR_PATH_PSI = 3
	TIMEOUT_S = 10

#########################################################
###############   MCU Internal Programs   ###############
#########################################################

#MCU_INTERNAL_PROGRAMS = ['','Remove Medium','Ramp Up Pressure','Pump Fluid','Empty Fluidic Line','Preuse Check (Pressure)','Preuse Check (Vacuum)']
MCU_INTERNAL_PROGRAMS = ['IDLE','LOAD_MEDIUM_START','LOAD_MEDIUM','VENT_VB0','UNLOAD_START','CLEAR_START','Preuse Check (Pressure)','Preuse Check (Vacuum)','BUBBLE_START','BUBBLE_FINISH']
MCU_STATUS = ['DONE','EX', 'INV', 'ERR']
# status of internal program execution on the MCU

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
byte 12-13	: pressure sensor 1 reading (vacuum)
byte 14-15	: pressure sensor 2 reading (pressure)
byte 16-17	: flow sensor 1 reading (downstream)
byte 18-19	: flow sensor 2 reading (upstream)
byte 20     : elapsed time since the start of the last internal program (in seconds)
byte 21-22  : volume (ul), range: 0 - 5000
byte 23-24  : reserved

#########################################################
#########   Computer -> MCU command structure   #########
#########################################################
byte 0-1	: computer -> MCU CMD counter
byte 2		: cmd from host computer
byte 3		: payload 1 (1 byte) - e.g. control type [constant power, constant pressure, constant flow, volume]
byte 4		: payload 2 (1 byte) - e.g. fluidic port
byte 5-6	: payload 3 (2 byte) - e.g. power, pressure, flow rate or volume setting
byte 7-10	: payload 4 (4 byte) - e.g. duration in ms
byte 11-14	: reserved (4 byte) (including checksum)

'''


# sequences
'''
1. strip - volume (time) [1.2 ml] - wait time - number of times [2]
2. PBST wash - volume (time) [1.2 ml] - wait time - number of cycles [3]
3. sequencing mixture - all available - wait time
4. wash (post ligation) - volume (time) - wait time - number of cycles [3]
4. imaging buffer - volume (time) [1.2 ml]
5. DAPI - volume (time) [1.2 ml] - wait time
'''
