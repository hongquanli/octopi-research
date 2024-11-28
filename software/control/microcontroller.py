import platform
import serial
import serial.tools.list_ports
import time
import numpy as np
import threading
from crc import CrcCalculator, Crc8
import struct

from qtpy.QtCore import QTimer

import squid.logging
from control._def import *


# add user to the dialout group to avoid the need to use sudo

# done (7/20/2021) - remove the time.sleep in all functions (except for __init__) to 
# make all callable functions nonblocking, instead, user should check use is_busy() to
# check if the microcontroller has finished executing the more recent command

# to do (7/28/2021) - add functions for configuring the stepper motors
class CommandAborted(RuntimeError):
    """
    If we send a command and it needs to abort for any reason (too many retries,
    timeout waiting for the mcu to acknowledge, etc), the Microcontroller class will throw this
    for wait and progress check operations until a new command is started.

    This does mean that if you don't check for command completion, you may miss these errors!
    """
    def __init__(self, command_id, reason):
        super().__init__(reason)
        self.command_id = command_id


class SimSerial:
    @staticmethod
    def response_bytes_for(command_id, execution_status, x, y, z, theta, joystick_button, switch):
        """
        - command ID (1 byte)
        - execution status (1 byte)
        - X pos (4 bytes)
        - Y pos (4 bytes)
        - Z pos (4 bytes)
        - Theta (4 bytes)
        - buttons and switches (1 byte)
        - reserved (4 bytes)
        - CRC (1 byte)
        """
        crc_calculator = CrcCalculator(Crc8.CCITT,table_based=True)

        button_state = joystick_button << BIT_POS_JOYSTICK_BUTTON | switch << BIT_POS_SWITCH
        reserved_state = 0 # This is just filler for the 4 reserved bytes.
        response = bytearray(struct.pack(">BBiiiiBi", command_id, execution_status, x, y, z, theta, button_state, reserved_state))
        response.append(crc_calculator.calculate_checksum(response))
        return response

    def __init__(self):
        self.in_waiting = 0
        self.response_buffer = []

        self.x = 0
        self.y = 0
        self.z = 0
        self.theta = 0
        self.joystick_button = False
        self.switch = False

        self.closed = False

    def respond_to(self, write_bytes):
        # Just immediately respond that the command was successful.  We can
        # implement specific command handlers here in the future for eg:
        # correct position tracking and such.
        self.response_buffer.extend(SimSerial.response_bytes_for(
            write_bytes[0],
            CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS,
            self.x,
            self.y,
            self.z,
            self.theta,
            self.joystick_button,
            self.switch))

        self.in_waiting = len(self.response_buffer)

    def close(self):
        self.closed = True

    def write(self, data):
        if self.closed:
            raise IOError("Closed")
        self.respond_to(data)

    def read(self, count=1):
        if self.closed:
            raise IOError("Closed")

        response = bytearray()
        for i in range(count):
            if not len(self.response_buffer):
                break
            response.append(self.response_buffer.pop(0))

        self.in_waiting = len(self.response_buffer)
        return response


class Microcontroller:
    LAST_COMMAND_ACK_TIMEOUT = 0.5
    MAX_RETRY_COUNT = 5

    def __init__(self, version='Arduino Due', sn=None, existing_serial=None, is_simulation=False):
        self.is_simulation = is_simulation

        self.log = squid.logging.get_logger(self.__class__.__name__)

        self.tx_buffer_length = MicrocontrollerDef.CMD_LENGTH
        self.rx_buffer_length = MicrocontrollerDef.MSG_LENGTH

        self._cmd_id = 0
        self._cmd_id_mcu = None # command id of mcu's last received command 
        self._cmd_execution_status = None
        self.mcu_cmd_execution_in_progress = False

        self.x_pos = 0 # unit: microstep or encoder resolution
        self.y_pos = 0 # unit: microstep or encoder resolution
        self.z_pos = 0 # unit: microstep or encoder resolution
        self.theta_pos = 0 # unit: microstep or encoder resolution
        self.button_and_switch_state = 0
        self.joystick_button_pressed = 0
        self.signal_joystick_button_pressed_event = False
        self.switch_state = 0

        self.last_command = None
        self.last_command_send_timestamp = time.time()
        self.last_command_aborted_error = None

        self.crc_calculator = CrcCalculator(Crc8.CCITT,table_based=True)
        self.retry = 0

        self.log.debug("connecting to controller based on " + version)

        if existing_serial:
            self.serial = existing_serial
        else:
            if version =='Arduino Due':
                controller_ports = [p.device for p in serial.tools.list_ports.comports() if 'Arduino Due' == p.description] # autodetect - based on Deepak's code
            else:
                if sn is not None:
                    controller_ports = [ p.device for p in serial.tools.list_ports.comports() if sn == p.serial_number]
                else:
                    if sys.platform == 'win32':
                        controller_ports = [ p.device for p in serial.tools.list_ports.comports() if p.manufacturer == 'Microsoft']
                    else:
                        controller_ports = [ p.device for p in serial.tools.list_ports.comports() if p.manufacturer == 'Teensyduino']

            if not controller_ports:
                raise IOError("no controller found")
            if len(controller_ports) > 1:
                self.log.warning("multiple controller found - using the first")

            self.serial = serial.Serial(controller_ports[0],2000000)
        self.log.debug("controller connected")

        self.new_packet_callback_external = None
        self.terminate_reading_received_packet_thread = False
        self.thread_read_received_packet = threading.Thread(target=self.read_received_packet, daemon=True)
        self.thread_read_received_packet.start()
        
    def close(self):
        self.terminate_reading_received_packet_thread = True
        self.thread_read_received_packet.join()
        self.serial.close()

    def reset(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.RESET
        self.log.debug("reset the microcontroller")
        self.send_command(cmd)
        # On the microcontroller side, reset forces the command Id back to 0
        # so any responses will look like they are for command id 0.  Force that
        # here.
        self._cmd_id = 0

    def initialize_drivers(self):
        self._cmd_id = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.INITIALIZE
        self.send_command(cmd)
        self.log.debug("initialize the drivers")

    def turn_on_illumination(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.TURN_ON_ILLUMINATION
        self.send_command(cmd)

    def turn_off_illumination(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.TURN_OFF_ILLUMINATION
        self.send_command(cmd)

    def set_illumination(self,illumination_source,intensity):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_ILLUMINATION
        cmd[2] = illumination_source
        cmd[3] = int((intensity/100)*65535) >> 8
        cmd[4] = int((intensity/100)*65535) & 0xff
        self.send_command(cmd)

    def set_illumination_led_matrix(self,illumination_source,r,g,b):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_ILLUMINATION_LED_MATRIX
        cmd[2] = illumination_source
        cmd[3] = min(int(g*255),255)
        cmd[4] = min(int(r*255),255)
        cmd[5] = min(int(b*255),255)
        self.send_command(cmd)

    def send_hardware_trigger(self,control_illumination=False,illumination_on_time_us=0,trigger_output_ch=0):
        illumination_on_time_us = int(illumination_on_time_us)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SEND_HARDWARE_TRIGGER
        cmd[2] = (control_illumination<<7) + trigger_output_ch # MSB: whether illumination is controlled
        cmd[3] = illumination_on_time_us >> 24
        cmd[4] = (illumination_on_time_us >> 16) & 0xff
        cmd[5] = (illumination_on_time_us >> 8) & 0xff
        cmd[6] = illumination_on_time_us & 0xff
        self.send_command(cmd)

    def set_strobe_delay_us(self, strobe_delay_us, camera_channel=0):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_STROBE_DELAY
        cmd[2] = camera_channel
        cmd[3] = strobe_delay_us >> 24
        cmd[4] = (strobe_delay_us >> 16) & 0xff
        cmd[5] = (strobe_delay_us >> 8) & 0xff
        cmd[6] = strobe_delay_us & 0xff
        self.send_command(cmd)

    def set_axis_enable_disable(self, axis, status):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_AXIS_DISABLE_ENABLE
        cmd[2] = axis
        cmd[3] = status
        self.send_command(cmd)

    def _move_axis_usteps(self, usteps, axis_command_code, axis_direction_sign):
        direction = axis_direction_sign * np.sign(usteps)
        n_microsteps_abs = abs(usteps)
        # if n_microsteps_abs exceed the max value that can be sent in one go
        while n_microsteps_abs >= (2 ** 32) / 2:
            n_microsteps_partial_abs = (2 ** 32) / 2 - 1
            n_microsteps_partial = direction * n_microsteps_partial_abs
            payload = self._int_to_payload(n_microsteps_partial, 4)
            cmd = bytearray(self.tx_buffer_length)
            cmd[1] = axis_command_code
            cmd[2] = payload >> 24
            cmd[3] = (payload >> 16) & 0xff
            cmd[4] = (payload >> 8) & 0xff
            cmd[5] = payload & 0xff
            # TODO(imo): Since this issues multiple commands, there's no way to check for and abort failed
            # ones mid-move.
            self.send_command(cmd)

            n_microsteps_abs = n_microsteps_abs - n_microsteps_partial_abs
        n_microsteps = direction * n_microsteps_abs
        payload = self._int_to_payload(n_microsteps, 4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = axis_command_code
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    def move_x_usteps(self,usteps):
        if self.is_simulation:
            self.x_pos = self.x_pos + STAGE_MOVEMENT_SIGN_X*usteps
        self._move_axis_usteps(usteps, CMD_SET.MOVE_X, STAGE_MOVEMENT_SIGN_X)

    def move_x_to_usteps(self,usteps):
        if self.is_simulation:
            self.x_pos = usteps
        payload = self._int_to_payload(usteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVETO_X
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    def move_y_usteps(self,usteps):
        if self.is_simulation:
            self.y_pos = self.y_pos + STAGE_MOVEMENT_SIGN_Y*usteps
        self._move_axis_usteps(usteps, CMD_SET.MOVE_Y, STAGE_MOVEMENT_SIGN_Y)
    
    def move_y_to_usteps(self,usteps):
        if self.is_simulation:
            self.y_pos = usteps
        payload = self._int_to_payload(usteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVETO_Y
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    def move_z_usteps(self,usteps):
        if self.is_simulation:
            self.z_pos = self.z_pos + STAGE_MOVEMENT_SIGN_Z*usteps
        self._move_axis_usteps(usteps, CMD_SET.MOVE_Z, STAGE_MOVEMENT_SIGN_Z)

    def move_z_to_usteps(self,usteps):
        if self.is_simulation:
            self.z_pos = usteps
        payload = self._int_to_payload(usteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVETO_Z
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    def move_theta_usteps(self,usteps):
        if self.is_simulation:
            self.theta_pos = self.theta_pos + usteps
        self._move_axis_usteps(usteps, CMD_SET.MOVE_THETA, STAGE_MOVEMENT_SIGN_THETA)

    def set_off_set_velocity_x(self,off_set_velocity):
        # off_set_velocity is in mm/s
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_OFFSET_VELOCITY
        cmd[2] = AXIS.X
        off_set_velocity = off_set_velocity*1000000
        payload = self._int_to_payload(off_set_velocity,4)
        cmd[3] = payload >> 24
        cmd[4] = (payload >> 16) & 0xff
        cmd[5] = (payload >> 8) & 0xff
        cmd[6] = payload & 0xff
        self.send_command(cmd)

    def set_off_set_velocity_y(self,off_set_velocity):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_OFFSET_VELOCITY
        cmd[2] = AXIS.Y
        off_set_velocity = off_set_velocity*1000000
        payload = self._int_to_payload(off_set_velocity,4)
        cmd[3] = payload >> 24
        cmd[4] = (payload >> 16) & 0xff
        cmd[5] = (payload >> 8) & 0xff
        cmd[6] = payload & 0xff
        self.send_command(cmd)

    def home_x(self):
        if self.is_simulation:
            self.x_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.X
        cmd[3] = int((STAGE_MOVEMENT_SIGN_X+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)

    def home_y(self):
        if self.is_simulation:
            self.y_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Y
        cmd[3] = int((STAGE_MOVEMENT_SIGN_Y+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)

    def home_z(self):
        if self.is_simulation:
            self.z_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Z
        cmd[3] = int((STAGE_MOVEMENT_SIGN_Z+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)

    def home_theta(self):
        if self.is_simulation:
            self.theta_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = 3
        cmd[3] = int((STAGE_MOVEMENT_SIGN_THETA+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)

    def home_xy(self):
        if self.is_simulation:
            self.x_pos = 0
            self.y_pos = 0
        self.y_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.XY
        cmd[3] = int((STAGE_MOVEMENT_SIGN_X+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        cmd[4] = int((STAGE_MOVEMENT_SIGN_Y+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)

    def zero_x(self):
        if self.is_simulation:
            self.x_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.X
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)

    def zero_y(self):
        if self.is_simulation:
            self.y_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Y
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)

    def zero_z(self):
        if self.is_simulation:
            self.z_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Z
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)

    def zero_theta(self):
        if self.is_simulation:
            self.theta_pos = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.THETA
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)

    def configure_stage_pid(self, axis, transitions_per_revolution, flip_direction=False):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.CONFIGURE_STAGE_PID
        cmd[2] = axis
        cmd[3] = int(flip_direction)
        payload = self._int_to_payload(transitions_per_revolution,2)
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    def turn_on_stage_pid(self, axis):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.ENABLE_STAGE_PID
        cmd[2] = axis
        self.send_command(cmd)

    def turn_off_stage_pid(self, axis):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.DISABLE_STAGE_PID
        cmd[2] = axis
        self.send_command(cmd)

    def set_pid_arguments(self, axis, pid_p, pid_i, pid_d):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_PID_ARGUMENTS
        cmd[2] = int(axis)

        cmd[3] = (int(pid_p) >> 8) & 0xff
        cmd[4] = int(pid_p) & 0xff

        cmd[5] = int(pid_i)
        cmd[6] = int(pid_d)
        self.send_command(cmd)

    def set_lim(self,limit_code,usteps):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_LIM
        cmd[2] = limit_code
        payload = self._int_to_payload(usteps,4)
        cmd[3] = payload >> 24
        cmd[4] = (payload >> 16) & 0xff
        cmd[5] = (payload >> 8) & 0xff
        cmd[6] = payload & 0xff
        self.send_command(cmd)

    def set_limit_switch_polarity(self,axis,polarity):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_LIM_SWITCH_POLARITY
        cmd[2] = axis
        cmd[3] = polarity
        self.send_command(cmd)

    def set_home_safety_margin(self, axis, margin):
        margin = abs(margin)
        if margin > 0xFFFF:
            margin = 0xFFFF
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_HOME_SAFETY_MERGIN
        cmd[2] = axis
        cmd[3] = (margin >> 8) & 0xff
        cmd[4] = (margin) & 0xff
        self.send_command(cmd)

    def configure_motor_driver(self,axis,microstepping,current_rms,I_hold):
        # current_rms in mA
        # I_hold 0.0-1.0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.CONFIGURE_STEPPER_DRIVER
        cmd[2] = axis
        if microstepping == 1:
            cmd[3] = 0
        elif microstepping == 256:
            cmd[3] = 255 # max of uint8 is 255 - will be changed to 255 after received by the MCU
        else:
            cmd[3] = microstepping
        cmd[4] = current_rms >> 8
        cmd[5] = current_rms & 0xff
        cmd[6] = int(I_hold*255)
        self.send_command(cmd)

    def set_max_velocity_acceleration(self,axis,velocity,acceleration):
        # velocity: max 65535/100 mm/s
        # acceleration: max 65535/10 mm/s^2
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_MAX_VELOCITY_ACCELERATION
        cmd[2] = axis
        cmd[3] = int(velocity*100) >> 8
        cmd[4] = int(velocity*100) & 0xff
        cmd[5] = int(acceleration*10) >> 8
        cmd[6] = int(acceleration*10) & 0xff
        self.send_command(cmd)

    def set_leadscrew_pitch(self,axis,pitch_mm):
        # pitch: max 65535/1000 = 65.535 (mm)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_LEAD_SCREW_PITCH
        cmd[2] = axis
        cmd[3] = int(pitch_mm*1000) >> 8
        cmd[4] = int(pitch_mm*1000) & 0xff
        self.send_command(cmd)

    def configure_actuators(self):
        # lead screw pitch
        self.set_leadscrew_pitch(AXIS.X,SCREW_PITCH_X_MM)
        self.wait_till_operation_is_completed()
        self.set_leadscrew_pitch(AXIS.Y,SCREW_PITCH_Y_MM)
        self.wait_till_operation_is_completed()
        self.set_leadscrew_pitch(AXIS.Z,SCREW_PITCH_Z_MM)
        self.wait_till_operation_is_completed()
        # stepper driver (microstepping,rms current and I_hold)
        self.configure_motor_driver(AXIS.X,MICROSTEPPING_DEFAULT_X,X_MOTOR_RMS_CURRENT_mA,X_MOTOR_I_HOLD)
        self.wait_till_operation_is_completed()
        self.configure_motor_driver(AXIS.Y,MICROSTEPPING_DEFAULT_Y,Y_MOTOR_RMS_CURRENT_mA,Y_MOTOR_I_HOLD)
        self.wait_till_operation_is_completed()
        self.configure_motor_driver(AXIS.Z,MICROSTEPPING_DEFAULT_Z,Z_MOTOR_RMS_CURRENT_mA,Z_MOTOR_I_HOLD)
        self.wait_till_operation_is_completed()
        # max velocity and acceleration
        self.set_max_velocity_acceleration(AXIS.X,MAX_VELOCITY_X_mm,MAX_ACCELERATION_X_mm)
        self.wait_till_operation_is_completed()
        self.set_max_velocity_acceleration(AXIS.Y,MAX_VELOCITY_Y_mm,MAX_ACCELERATION_Y_mm)
        self.wait_till_operation_is_completed()
        self.set_max_velocity_acceleration(AXIS.Z,MAX_VELOCITY_Z_mm,MAX_ACCELERATION_Z_mm)
        self.wait_till_operation_is_completed()
        # home switch
        self.set_limit_switch_polarity(AXIS.X,X_HOME_SWITCH_POLARITY)
        self.wait_till_operation_is_completed()
        self.set_limit_switch_polarity(AXIS.Y,Y_HOME_SWITCH_POLARITY)
        self.wait_till_operation_is_completed()
        self.set_limit_switch_polarity(AXIS.Z,Z_HOME_SWITCH_POLARITY)
        self.wait_till_operation_is_completed()
        # home safety margin
        self.set_home_safety_margin(AXIS.X, int(X_HOME_SAFETY_MARGIN_UM))
        self.wait_till_operation_is_completed()
        self.set_home_safety_margin(AXIS.Y, int(Y_HOME_SAFETY_MARGIN_UM))
        self.wait_till_operation_is_completed()
        self.set_home_safety_margin(AXIS.Z, int(Z_HOME_SAFETY_MARGIN_UM))
        self.wait_till_operation_is_completed()

    def ack_joystick_button_pressed(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.ACK_JOYSTICK_BUTTON_PRESSED
        self.send_command(cmd)

    def analog_write_onboard_DAC(self,dac,value):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.ANALOG_WRITE_ONBOARD_DAC
        cmd[2] = dac
        cmd[3] = (value >> 8) & 0xff
        cmd[4] = value & 0xff
        self.send_command(cmd)

    def configure_dac80508_refdiv_and_gain(self, div, gains):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_DAC80508_REFDIV_GAIN
        cmd[2] = div
        cmd[3] = gains
        self.send_command(cmd)

    def set_pin_level(self,pin,level):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_PIN_LEVEL
        cmd[2] = pin
        cmd[3] = level
        self.send_command(cmd)

    def turn_on_AF_laser(self):
        self.set_pin_level(MCU_PINS.AF_LASER,1)

    def turn_off_AF_laser(self):
        self.set_pin_level(MCU_PINS.AF_LASER,0)

    def send_command(self,command):
        self._cmd_id = (self._cmd_id + 1)%256
        command[0] = self._cmd_id
        command[-1] = self.crc_calculator.calculate_checksum(command[:-1])
        self.serial.write(command)
        self.mcu_cmd_execution_in_progress = True
        self.last_command = command
        self.last_command_send_timestamp = time.time()
        self.retry = 0

        if self.last_command_aborted_error is not None:
            self.log.warning("Last command aborted and not cleared before new command sent!", self.last_command_aborted_error)
        self.last_command_aborted_error = None

    def abort_current_command(self, reason):
        self.log.error(f"Command id={self._cmd_id} aborted for reason='{reason}'")
        self.last_command_aborted_error = CommandAborted(reason=reason, command_id=self._cmd_id)
        self.mcu_cmd_execution_in_progress = False

    def acknowledge_aborted_command(self):
        if self.last_command_aborted_error is None:
            self.log.warning("Request to ack aborted command, but there is no aborted command.")

        self.last_command_aborted_error = None

    def resend_last_command(self):
        if self.last_command is not None:
            self.serial.write(self.last_command)
            self.mcu_cmd_execution_in_progress = True
            # We use the retry count for both checksum errors, and to keep track of
            # timeout re-attempts.
            self.last_command_send_timestamp = time.time()
            self.retry = self.retry + 1
        else:
            self.log.warning("resend requested with no last_command, something is wrong!")
            self.abort_current_command("Resend last requested with no last command")

    def read_received_packet(self):
        while self.terminate_reading_received_packet_thread == False:
            # wait to receive data
            if self.serial.in_waiting==0 or self.serial.in_waiting % self.rx_buffer_length != 0:
                # Sleep a negligible amount of time just to give other threads time to run.  Otherwise,
                # we run the rise of spinning forever here and not letting progress happen elsewhere.
                time.sleep(0.0001)
                continue
            
            # get rid of old data
            num_bytes_in_rx_buffer = self.serial.in_waiting
            if num_bytes_in_rx_buffer > self.rx_buffer_length:
                for i in range(num_bytes_in_rx_buffer-self.rx_buffer_length):
                    self.serial.read()
            
            # read the buffer
            msg=[]
            for i in range(self.rx_buffer_length):
                msg.append(ord(self.serial.read()))

            # parse the message
            '''
            - command ID (1 byte)
            - execution status (1 byte)
            - X pos (4 bytes)
            - Y pos (4 bytes)
            - Z pos (4 bytes)
            - Theta (4 bytes)
            - buttons and switches (1 byte)
            - reserved (4 bytes)
            - CRC (1 byte)
            '''
            self._cmd_id_mcu = msg[0]
            self._cmd_execution_status = msg[1]
            if (self._cmd_id_mcu == self._cmd_id) and (self._cmd_execution_status == CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS):
                if self.mcu_cmd_execution_in_progress:
                    self.mcu_cmd_execution_in_progress = False
                    self.log.debug("mcu command " + str(self._cmd_id) + " complete")
            elif self.mcu_cmd_execution_in_progress and self._cmd_id_mcu != self._cmd_id and time.time() - self.last_command_send_timestamp > self.LAST_COMMAND_ACK_TIMEOUT and self.last_command is not None:
                if self.retry > self.MAX_RETRY_COUNT:
                    self.abort_current_command(reason=f"Command timed out without an ack after {self.LAST_COMMAND_ACK_TIMEOUT} [s], and {self.retry} retries")
                else:
                    self.log.debug(f"command timed out without an ack after {self.LAST_COMMAND_ACK_TIMEOUT} [s], resending command")
                    self.resend_last_command()
            elif self.mcu_cmd_execution_in_progress and self._cmd_execution_status == CMD_EXECUTION_STATUS.CMD_CHECKSUM_ERROR:
                if self.retry > self.MAX_RETRY_COUNT:
                    self.abort_current_command(reason=f"Checksum error and 10 retries for {self._cmd_id}")
                else:
                    self.log.error("cmd checksum error, resending command")
                    self.resend_last_command()

            if self.is_simulation:
                pass
            else:
                self.x_pos = self._payload_to_int(msg[2:6],MicrocontrollerDef.N_BYTES_POS) # unit: microstep or encoder resolution
                self.y_pos = self._payload_to_int(msg[6:10],MicrocontrollerDef.N_BYTES_POS) # unit: microstep or encoder resolution
                self.z_pos = self._payload_to_int(msg[10:14],MicrocontrollerDef.N_BYTES_POS) # unit: microstep or encoder resolution
                self.theta_pos = self._payload_to_int(msg[14:18],MicrocontrollerDef.N_BYTES_POS) # unit: microstep or encoder resolution

            self.button_and_switch_state = msg[18]
            # joystick button
            tmp = self.button_and_switch_state & (1 << BIT_POS_JOYSTICK_BUTTON)
            joystick_button_pressed = tmp > 0
            if self.joystick_button_pressed == False and joystick_button_pressed == True:
                self.signal_joystick_button_pressed_event = True
                self.ack_joystick_button_pressed()
            self.joystick_button_pressed = joystick_button_pressed
            # switch
            tmp = self.button_and_switch_state & (1 << BIT_POS_SWITCH)
            self.switch_state = tmp > 0

            if self.new_packet_callback_external is not None:
                self.new_packet_callback_external(self)

    def get_pos(self):
        return self.x_pos, self.y_pos, self.z_pos, self.theta_pos

    def get_button_and_switch_state(self):
        return self.button_and_switch_state

    def is_busy(self):
        return self.mcu_cmd_execution_in_progress

    def set_callback(self,function):
        self.new_packet_callback_external = function

    def wait_till_operation_is_completed(self, timeout_limit_s=5):
        """
        Wait for the current command to complete.  If the wait times out, the current command isn't touched.  To
        abort it, you should call the abort_current_command(...) method.
        """
        timestamp_start = time.time()
        while self.is_busy() and self.last_command_aborted_error is None:
            time.sleep(0.02)
            if time.time() - timestamp_start > timeout_limit_s:
                raise TimeoutError(f"Current mcu operation timed out after {timeout_limit_s} [s].")

        if self.last_command_aborted_error is not None:
            raise self.last_command_aborted_error

    @staticmethod
    def _int_to_payload(signed_int,number_of_bytes):
        if signed_int >= 0:
            payload = signed_int
        else:
            payload = 2**(8*number_of_bytes) + signed_int # find two's completement
        return payload

    @staticmethod
    def _payload_to_int(payload,number_of_bytes):
        signed = 0
        for i in range(number_of_bytes):
            signed = signed + int(payload[i])*(256**(number_of_bytes-1-i))
        if signed >= 256**number_of_bytes/2:
            signed = signed - 256**number_of_bytes
        return signed
    
    def set_dac80508_scaling_factor_for_illumination(self, illumination_intensity_factor):
        if illumination_intensity_factor > 1:
            illumination_intensity_factor = 1

        if illumination_intensity_factor < 0:
            illumination_intensity_factor = 0.01

        factor = round(illumination_intensity_factor, 2) * 100
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.SET_ILLUMINATION_INTENSITY_FACTOR
        cmd[2] = int(factor)
        self.send_command(cmd)
