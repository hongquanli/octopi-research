import platform
import serial
import serial.tools.list_ports
import time
import numpy as np

from control._def import *

# temporary
class Microcontroller2():
    def __init__(self,serial_number):
        self.serial = None
        self.platform_name = platform.system()
        self.tx_buffer_length = Microcontroller2Def.CMD_LENGTH
        self.rx_buffer_length = Microcontroller2Def.MSG_LENGTH

        self._cmd_id = 0
        self._cmd_id_mcu = None # command id of mcu's last received command 
        self._cmd_execution_status = None
        self.mcu_cmd_execution_in_progress = False
        self.last_command = None
        self.timeout_counter = 0

        controller_ports = [ p.device for p in serial.tools.list_ports.comports() if manufacturer == 'Teensyduino']
        if not controller_ports:
            raise IOError("No Teensy Found")
        self.serial = serial.Serial(controller_ports[0],2000000)
        print('Teensy connected')

        self.new_packet_callback_external = None
        self.terminate_reading_received_packet_thread = False
        self.thread_read_received_packet = threading.Thread(target=self.read_received_packet, daemon=True)
        self.thread_read_received_packet.start()

    def close(self):
        self.serial.close()

    def analog_write_DAC8050x(self,dac,value):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.ANALOG_WRITE_ONBOARD_DAC
        cmd[2] = dac
        cmd[3] = (value >> 8) & 0xff
        cmd[4] = value & 0xff
        self.send_command(cmd)
    
    def send_command(self,command):
        self._cmd_id = (self._cmd_id + 1)%256
        command[0] = self._cmd_id
        # command[self.tx_buffer_length-1] = self._calculate_CRC(command)
        self.serial.write(command)
        self.mcu_cmd_execution_in_progress = True
        self.last_command = command
        self.timeout_counter = 0

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
            - CRC (1 byte)
            '''
            self._cmd_id_mcu = msg[0]
            self._cmd_execution_status = msg[1]
            if (self._cmd_id_mcu == self._cmd_id) and (self._cmd_execution_status == CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS):
                if self.mcu_cmd_execution_in_progress == True:
                    self.mcu_cmd_execution_in_progress = False
                    print('   mcu command ' + str(self._cmd_id) + ' complete')
                elif self._cmd_id_mcu != self._cmd_id and self.last_command != None:
                    self.timeout_counter = self.timeout_counter + 1
                    if self.timeout_counter > 10:
                        self.resend_last_command()
                        print('      *** resend the last command')
            # print('command id ' + str(self._cmd_id) + '; mcu command ' + str(self._cmd_id_mcu) + ' status: ' + str(msg[1]) )

            if self.new_packet_callback_external is not None:
                self.new_packet_callback_external(self)

    def is_busy(self):
        return self.mcu_cmd_execution_in_progress

    def set_callback(self,function):
        self.new_packet_callback_external = function

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

class Microcontroller2_Simulation():
    def __init__(self,parent=None):
        self.serial = None
        self.platform_name = platform.system()
        self.tx_buffer_length = MicrocontrollerDef.CMD_LENGTH
        self.rx_buffer_length = MicrocontrollerDef.MSG_LENGTH

        self._cmd_id = 0
        self._cmd_id_mcu = None # command id of mcu's last received command 
        self._cmd_execution_status = None
        self.mcu_cmd_execution_in_progress = False

         # for simulation
        self.timestamp_last_command = time.time() # for simulation only
        self._mcu_cmd_execution_status = None
        self.timer_update_command_execution_status = QTimer()
        self.timer_update_command_execution_status.timeout.connect(self._simulation_update_cmd_execution_status)

        self.new_packet_callback_external = None
        self.terminate_reading_received_packet_thread = False
        self.thread_read_received_packet = threading.Thread(target=self.read_received_packet, daemon=True)
        self.thread_read_received_packet.start()

    def close(self):
        self.terminate_reading_received_packet_thread = True
        self.thread_read_received_packet.join()

    def analog_write_DAC8050x(self,dac,value):
        cmd = bytearray(self.tx_buffer_length)
        cmd[1] = CMD_SET.ANALOG_WRITE_ONBOARD_DAC
        cmd[2] = dac
        cmd[3] = (value >> 8) & 0xff
        cmd[4] = value & 0xff
        self.send_command(cmd)

    def read_received_packet(self):
        while self.terminate_reading_received_packet_thread == False:
            # only for simulation - update the command execution status
            if time.time() - self.timestamp_last_command > 0.05: # in the simulation, assume all the operation takes 0.05s to complete
                if self._mcu_cmd_execution_status !=  CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS:
                    self._mcu_cmd_execution_status = CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS
                    print('   mcu command ' + str(self._cmd_id) + ' complete')

            # read and parse message
            msg=[]
            for i in range(self.rx_buffer_length):
                msg.append(0)

            msg[0] = self._cmd_id
            msg[1] = self._mcu_cmd_execution_status

            self._cmd_id_mcu = msg[0]
            self._cmd_execution_status = msg[1]
            if (self._cmd_id_mcu == self._cmd_id) and (self._cmd_execution_status == CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS):
                self.mcu_cmd_execution_in_progress = False
            # print('mcu_cmd_execution_in_progress: ' + str(self.mcu_cmd_execution_in_progress))
            
            if self.new_packet_callback_external is not None:
                self.new_packet_callback_external(self)

            time.sleep(0.005) # simulate MCU packet transmission interval
    
    def set_callback(self,function):
        self.new_packet_callback_external = function

    def is_busy(self):
        return self.mcu_cmd_execution_in_progress

    def send_command(self,command):
        self._cmd_id = (self._cmd_id + 1)%256
        command[0] = self._cmd_id
        # command[self.tx_buffer_length-1] = self._calculate_CRC(command)
        self.mcu_cmd_execution_in_progress = True
        # for simulation
        self._mcu_cmd_execution_status = CMD_EXECUTION_STATUS.IN_PROGRESS
        # self.timer_update_command_execution_status.setInterval(2000)
        # self.timer_update_command_execution_status.start()
        # print('start timer')
        # timer cannot be started from another thread
        self.timestamp_last_command = time.time()

    def _simulation_update_cmd_execution_status(self):
        # print('simulation - MCU command execution finished')
        # self._mcu_cmd_execution_status = CMD_EXECUTION_STATUS.COMPLETED_WITHOUT_ERRORS
        # self.timer_update_command_execution_status.stop()
        pass # timer cannot be started from another thread