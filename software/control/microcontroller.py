import platform
import serial
import serial.tools.list_ports
import time
import numpy as np
import threading
from crc import CrcCalculator, Crc8

from control._def import *

# add user to the dialout group to avoid the need to use sudo

# done (7/20/2021) - remove the time.sleep in all functions (except for __init__) to 
# make all callable functions nonblocking, instead, user should check use is_busy() to
# check if the microcontroller has finished executing the more recent command

# to do (7/28/2021) - add functions for configuring the stepper motors

class Microcontroller():    
    def __init__(self,version='Arduino Due',sn=None,parent=None):
        self.serial:serial.Serial = None # type:ignore
        self.platform_name = platform.system()
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
        self.timeout_counter = 0
        self.last_command_timestamp = time.time()

        self.crc_calculator = CrcCalculator(Crc8.CCITT,table_based=True)
        self.retry = 0

        print('connecting to controller based on ' + version)

        if version =='Arduino Due':
            controller_ports = [p.device for p in serial.tools.list_ports.comports() if 'Arduino Due' == p.description] # autodetect - based on Deepak's code
        else:
            if sn is not None:
                controller_ports = [ p.device for p in serial.tools.list_ports.comports() if sn == p.serial_number]
            else:
                controller_ports = [ p.device for p in serial.tools.list_ports.comports() if p.manufacturer == 'Teensyduino']
        
        if not controller_ports:
            raise IOError("no controller found")
        if len(controller_ports) > 1:
            print('multiple controller found - using the first')
        
        self.serial:serial.Serial = serial.Serial(controller_ports[0],2000000)
        time.sleep(0.2)
        print('controller connected')

        self.new_packet_callback_external = None
        self.terminate_reading_received_packet_thread = False
        self.thread_read_received_packet = threading.Thread(target=self.read_received_packet, daemon=True)
        self.thread_read_received_packet.start()
        
    def close(self):
        self.terminate_reading_received_packet_thread = True
        self.thread_read_received_packet.join()
        self.serial.close()

    def reset(self):
        self._cmd_id = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.RESET
        self.send_command(cmd)
        print('reset the microcontroller') # debug

    def initialize_drivers(self):
        self._cmd_id = 0
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.INITIALIZE
        self.send_command(cmd)
        print('initialize the drivers') # debug

    def turn_on_illumination(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.TURN_ON_ILLUMINATION
        self.send_command(cmd)

    def turn_off_illumination(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.TURN_OFF_ILLUMINATION
        self.send_command(cmd)

    def set_illumination(self,illumination_source:int,intensity:float):#,r=None,g=None,b=None):
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
        cmd[3] = min(int(r*255),255)
        cmd[4] = min(int(g*255),255)
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

    '''
    def move_x(self,delta):
        direction = int((np.sign(delta)+1)/2)
        n_microsteps = abs(delta*Motion.STEPS_PER_MM_XY)
        if n_microsteps > 65535:
            n_microsteps = 65535
        cmd = bytearray(self.tx_buffer_length)
        cmd[0] = CMD_SET.MOVE_X
        cmd[1] = direction
        cmd[2] = int(n_microsteps) >> 8
        cmd[3] = int(n_microsteps) & 0xff
        self.serial.write(cmd)
    '''

    def move_x_usteps(self,usteps):
        direction = MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X*np.sign(usteps)
        n_microsteps_abs = abs(usteps)
        # if n_microsteps_abs exceed the max value that can be sent in one go
        while n_microsteps_abs >= (2**32)/2:
            n_microsteps_partial_abs = (2**32)/2 - 1
            n_microsteps_partial = direction*n_microsteps_partial_abs
            payload = self._int_to_payload(n_microsteps_partial,4)
            cmd = bytearray(self.tx_buffer_length)
            cmd[1] = CMD_SET.MOVE_X
            cmd[2] = payload >> 24
            cmd[3] = (payload >> 16) & 0xff
            cmd[4] = (payload >> 8) & 0xff
            cmd[5] = payload & 0xff
            self.send_command(cmd)
            # while self.mcu_cmd_execution_in_progress == True:
            #     time.sleep(self._motion_status_checking_interval)
            n_microsteps_abs = n_microsteps_abs - n_microsteps_partial_abs

        n_microsteps = direction*n_microsteps_abs
        payload = self._int_to_payload(n_microsteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVE_X
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)

    def move_x_to_usteps(self,usteps):
        payload = self._int_to_payload(MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X*usteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVETO_X
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    '''
    def move_y(self,delta):
        direction = int((np.sign(delta)+1)/2)
        n_microsteps = abs(delta*Motion.STEPS_PER_MM_XY)
        if n_microsteps > 65535:
            n_microsteps = 65535
        cmd = bytearray(self.tx_buffer_length)
        cmd[0] = CMD_SET.MOVE_Y
        cmd[1] = direction
        cmd[2] = int(n_microsteps) >> 8
        cmd[3] = int(n_microsteps) & 0xff
        self.serial.write(cmd)
    '''

    def move_y_usteps(self,usteps):
        direction = MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y*np.sign(usteps)
        n_microsteps_abs = abs(usteps)
        # if n_microsteps_abs exceed the max value that can be sent in one go
        while n_microsteps_abs >= (2**32)/2:
            n_microsteps_partial_abs = (2**32)/2 - 1
            n_microsteps_partial = direction*n_microsteps_partial_abs
            payload = self._int_to_payload(n_microsteps_partial,4)
            cmd = bytearray(self.tx_buffer_length)
            cmd[1] = CMD_SET.MOVE_Y
            cmd[2] = payload >> 24
            cmd[3] = (payload >> 16) & 0xff
            cmd[4] = (payload >> 8) & 0xff
            cmd[5] = payload & 0xff
            self.send_command(cmd)
            # while self.mcu_cmd_execution_in_progress == True:
            #     time.sleep(self._motion_status_checking_interval)
            n_microsteps_abs = n_microsteps_abs - n_microsteps_partial_abs

        n_microsteps = direction*n_microsteps_abs
        payload = self._int_to_payload(n_microsteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVE_Y
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)
    
    def move_y_to_usteps(self,usteps):
        payload = self._int_to_payload(MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y*usteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVETO_Y
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    '''
    def move_z(self,delta):
        direction = int((np.sign(delta)+1)/2)
        n_microsteps = abs(delta*Motion.STEPS_PER_MM_Z)
        if n_microsteps > 65535:
            n_microsteps = 65535
        cmd = bytearray(self.tx_buffer_length)
        cmd[0] = CMD_SET.MOVE_Z
        cmd[1] = 1-direction
        cmd[2] = int(n_microsteps) >> 8
        cmd[3] = int(n_microsteps) & 0xff
        self.serial.write(cmd)
    '''

    def move_z_usteps(self,usteps):
        direction = MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Z*np.sign(usteps)
        n_microsteps_abs = abs(usteps)
        # if n_microsteps_abs exceed the max value that can be sent in one go
        while n_microsteps_abs >= (2**32)/2:
            n_microsteps_partial_abs = (2**32)/2 - 1
            n_microsteps_partial = direction*n_microsteps_partial_abs
            payload = self._int_to_payload(n_microsteps_partial,4)
            cmd = bytearray(self.tx_buffer_length)
            cmd[1] = CMD_SET.MOVE_Z
            cmd[2] = payload >> 24
            cmd[3] = (payload >> 16) & 0xff
            cmd[4] = (payload >> 8) & 0xff
            cmd[5] = payload & 0xff
            self.send_command(cmd)
            # while self.mcu_cmd_execution_in_progress == True:
            #     time.sleep(self._motion_status_checking_interval)
            n_microsteps_abs = n_microsteps_abs - n_microsteps_partial_abs

        n_microsteps = direction*n_microsteps_abs
        payload = self._int_to_payload(n_microsteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVE_Z
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)

    def move_z_to_usteps(self,usteps):
        payload = self._int_to_payload(usteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVETO_Z
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)

    def move_theta_usteps(self,usteps):
        direction = MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_THETA*np.sign(usteps)
        n_microsteps_abs = abs(usteps)
        # if n_microsteps_abs exceed the max value that can be sent in one go
        while n_microsteps_abs >= (2**32)/2:
            n_microsteps_partial_abs = (2**32)/2 - 1
            n_microsteps_partial = direction*n_microsteps_partial_abs
            payload = self._int_to_payload(n_microsteps_partial,4)
            cmd = bytearray(self.tx_buffer_length)
            cmd[1] = CMD_SET.MOVE_THETA
            cmd[2] = payload >> 24
            cmd[3] = (payload >> 16) & 0xff
            cmd[4] = (payload >> 8) & 0xff
            cmd[5] = payload & 0xff
            self.send_command(cmd)
            # while self.mcu_cmd_execution_in_progress == True:
            #     time.sleep(self._motion_status_checking_interval)
            n_microsteps_abs = n_microsteps_abs - n_microsteps_partial_abs

        n_microsteps = direction*n_microsteps_abs
        payload = self._int_to_payload(n_microsteps,4)
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.MOVE_THETA
        cmd[2] = payload >> 24
        cmd[3] = (payload >> 16) & 0xff
        cmd[4] = (payload >> 8) & 0xff
        cmd[5] = payload & 0xff
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)

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
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.X
        cmd[3] = int((MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

    def home_y(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Y
        cmd[3] = int((MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

    def home_z(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Z
        cmd[3] = int((MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Z+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

    def home_theta(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = 3
        cmd[3] = int((MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_THETA+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

    def home_xy(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.XY
        cmd[3] = int((MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        cmd[4] = int((MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y+1)/2) # "move backward" if SIGN is 1, "move forward" if SIGN is -1
        self.send_command(cmd)

    def zero_x(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.X
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

    def zero_y(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Y
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

    def zero_z(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.Z
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

    def zero_theta(self):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.HOME_OR_ZERO
        cmd[2] = AXIS.THETA
        cmd[3] = HOME_OR_ZERO.ZERO
        self.send_command(cmd)
        # while self.mcu_cmd_execution_in_progress == True:
        #     time.sleep(self._motion_status_checking_interval)
        #     # to do: add timeout

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
        self.set_leadscrew_pitch(AXIS.X,MACHINE_CONFIG.SCREW_PITCH_X_MM)
        self.wait_till_operation_is_completed()
        self.set_leadscrew_pitch(AXIS.Y,MACHINE_CONFIG.SCREW_PITCH_Y_MM)
        self.wait_till_operation_is_completed()
        self.set_leadscrew_pitch(AXIS.Z,MACHINE_CONFIG.SCREW_PITCH_Z_MM)
        self.wait_till_operation_is_completed()
        # stepper driver (microstepping,rms current and I_hold)
        self.configure_motor_driver(AXIS.X,MACHINE_CONFIG.MICROSTEPPING_DEFAULT_X,MACHINE_CONFIG.X_MOTOR_RMS_CURRENT_mA,MACHINE_CONFIG.X_MOTOR_I_HOLD)
        self.wait_till_operation_is_completed()
        self.configure_motor_driver(AXIS.Y,MACHINE_CONFIG.MICROSTEPPING_DEFAULT_Y,MACHINE_CONFIG.Y_MOTOR_RMS_CURRENT_mA,MACHINE_CONFIG.Y_MOTOR_I_HOLD)
        self.wait_till_operation_is_completed()
        self.configure_motor_driver(AXIS.Z,MACHINE_CONFIG.MICROSTEPPING_DEFAULT_Z,MACHINE_CONFIG.Z_MOTOR_RMS_CURRENT_mA,MACHINE_CONFIG.Z_MOTOR_I_HOLD)
        self.wait_till_operation_is_completed()
        # max velocity and acceleration
        self.set_max_velocity_acceleration(AXIS.X,MACHINE_CONFIG.MAX_VELOCITY_X_mm,MACHINE_CONFIG.MAX_ACCELERATION_X_mm)
        self.wait_till_operation_is_completed()
        self.set_max_velocity_acceleration(AXIS.Y,MACHINE_CONFIG.MAX_VELOCITY_Y_mm,MACHINE_CONFIG.MAX_ACCELERATION_Y_mm)
        self.wait_till_operation_is_completed()
        self.set_max_velocity_acceleration(AXIS.Z,MACHINE_CONFIG.MAX_VELOCITY_Z_mm,MACHINE_CONFIG.MAX_ACCELERATION_Z_mm)
        self.wait_till_operation_is_completed()
        # home switch
        self.set_limit_switch_polarity(AXIS.X,MACHINE_CONFIG.X_HOME_SWITCH_POLARITY)
        self.wait_till_operation_is_completed()
        self.set_limit_switch_polarity(AXIS.Y,MACHINE_CONFIG.Y_HOME_SWITCH_POLARITY)
        self.wait_till_operation_is_completed()
        self.set_limit_switch_polarity(AXIS.Z,MACHINE_CONFIG.Z_HOME_SWITCH_POLARITY)
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

    def send_command(self,command):
        self._cmd_id = (self._cmd_id + 1)%256
        command[0] = self._cmd_id
        command[-1] = self.crc_calculator.calculate_checksum(command[:-1])
        self.serial.write(command)
        self.mcu_cmd_execution_in_progress = True
        self.last_command = command
        self.timeout_counter = 0
        self.last_command_timestamp = time.time()
        self.retry = 0

    def resend_last_command(self):
        self.serial.write(self.last_command)
        self.mcu_cmd_execution_in_progress = True
        self.timeout_counter = 0
        self.retry = self.retry + 1

    def read_received_packet(self):
        while self.terminate_reading_received_packet_thread == False:
            # wait to receive data
            if self.serial.in_waiting==0:
                continue
            if self.serial.in_waiting % self.rx_buffer_length != 0:
                continue
            
            # get rid of old data
            num_bytes_in_rx_buffer = self.serial.in_waiting
            if num_bytes_in_rx_buffer > self.rx_buffer_length:
                # print('getting rid of old data')
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
                if self.mcu_cmd_execution_in_progress == True:
                    self.mcu_cmd_execution_in_progress = False
                    # print('   mcu command ' + str(self._cmd_id) + ' complete')
            elif self._cmd_id_mcu != self._cmd_id and time.time() - self.last_command_timestamp > 5 and self.last_command != None:
                self.timeout_counter = self.timeout_counter + 1
                if self.timeout_counter > 10:
                    self.resend_last_command()
                    print('      *** resend the last command')
            elif self._cmd_execution_status == CMD_EXECUTION_STATUS.CMD_CHECKSUM_ERROR:
                print('! cmd checksum error, resending command')
                if self.retry > 10:
                    print('!! resending command failed for more than 10 times, the program will exit')
                    exit()
                else:
                    self.resend_last_command()
            
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

    def wait_till_operation_is_completed(self, timeout_limit_s:int=5, time_step:float=0.02, timeout_msg='Error - microcontroller timeout, the program will exit'):
        timestamp_start = time.time()
        while self.is_busy():
            time.sleep(time_step)
            if time.time() - timestamp_start > timeout_limit_s:
                print(timeout_msg)
                exit()

    def _int_to_payload(self,signed_int,number_of_bytes):
        if signed_int >= 0:
            payload = signed_int
        else:
            payload = 2**(8*number_of_bytes) + signed_int # find two's completement
        return payload

    def _payload_to_int(self,payload,number_of_bytes):
        signed = 0
        for i in range(number_of_bytes):
            signed = signed + int(payload[i])*(256**(number_of_bytes-1-i))
        if signed >= 256**number_of_bytes/2:
            signed = signed - 256**number_of_bytes
        return signed
