import serial
from serial.tools import list_ports
import time

class SerialDevice:
    """
    General wrapper for serial devices, with
    automating device finding based on VID/PID
    or serial number.
    """
    def __init__(self, port=None, VID=None,PID=None,SN=None, baudrate=9600, read_timeout=1, **kwargs):
        # Initialize the serial connection
        self.port = port
        self.VID = VID
        self.PID = PID
        self.SN = SN

        self.baudrate = baudrate
        self.read_timeout = read_timeout
        self.serial_kwargs = kwargs
        
        self.serial = None

        if VID is not None and PID is not None:
            for d in list_ports.comports():
                if d.vid == VID and d.pid == PID:
                    self.port = d.device
                    break
        if SN is not None:
            for d in list_ports.comports():
                if d.serial_number == SN:
                    self.port = d.device
                    break

        if self.port is not None:
            self.serial = serial.Serial(self.port, baudrate=baudrate, timeout=read_timeout, **kwargs)

    def open_ser(self, SN=None, VID=None, PID=None, baudrate =None, read_timeout=None,**kwargs):
        if self.serial is not None and not self.serial.is_open:
            self.serial.open()
        
        if SN is None:
            SN = self.SN

        if VID is None:
            VID = self.VID

        if PID is None:
            PID = self.PID

        if baudrate is None:
            baudrate = self.baudrate

        if read_timeout is None:
            read_timeout = self.read_timeout

        for k in self.serial_kwargs.keys():
            if k not in kwargs:
                kwargs[k] = self.serial_kwargs[k]

        if self.serial is None:
            if VID is not None and PID is not None:
                for d in list_ports.comports():
                    if d.vid == VID and d.pid == PID:
                        self.port = d.device
                        break
            if SN is not None:
                for d in list_ports.comports():
                    if d.serial_number == SN:
                        self.port = d.device
                        break
            if self.port is not None:
                self.serial = serial.Serial(self.port,**kwargs)


    def write_and_check(self, command, expected_response, max_attempts=3, attempt_delay=1, check_prefix=True):
        # Write a command and check the response
        for attempt in range(max_attempts):
            self.serial.write(command.encode())
            time.sleep(0.1)  # Wait for the command to be sent

            response = self.serial.readline().decode().strip()
            if response == expected_response:
                return response
            
            if check_prefix:
                if response.startswith(expected_response):
                    return response

            else:
                time.sleep(attempt_delay)  # Wait before retrying

        raise RuntimeError("Max attempts reached without receiving expected response.")

    def close(self):
        # Close the serial connection
        self.serial.close()

class XLight_Simulation:
    def __init__(self):
        self.emission_wheel_pos = 1
        self.dichroic_wheel_pos = 1
        self.disk_motor_state = False
        self.spinning_disk_pos = 0

    def set_emission_filter(self,position, extraction=False):
        self.emission_wheel_pos = position
        return position

    def get_emission_filter(self):
        return self.emission_wheel_pos

    def set_dichroic(self, position, extraction=False):
        self.dichroic_wheel_pos = position
        return position

    def get_dichroic(self):
        return self.dichroic_wheel_pos

    
    def set_disk_position(self, position):
        self.spinning_disk_pos = position
        return position

    def get_disk_position(self):
        return self.spinning_disk_pos

    def set_disk_motor_state(self, state):
        self.disk_motor_state = state
        return state

    def get_disk_motor_state(self):
        return self.disk_motor_state

# CrestOptics X-Light Port specs:
# 9600 baud
# 8 data bits
# 1 stop bit
# No parity
# no flow control

class XLight:
    """Wrapper for communicating with CrestOptics X-Light devices over serial"""
    def __init__(self, SN="A106QADU"):
        """
        Provide serial number (default is that of the device
        cephla already has) for device-finding purposes. Otherwise, all
        XLight devices should use the same serial protocol
        """
        self.serial_connection = SerialDevice(SN=SN,baudrate=9600,
                bytesize=serial.EIGHTBITS,stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE, 
                xonxoff=False,rtscts=False,dsrdtr=False)
        self.serial_connection.open_ser()
    
    def set_emission_filter(self,position,extraction=False):
        if str(position) not in ["1","2","3","4","5","6","7","8"]:
            raise ValueError("Invalid emission filter wheel position!")
        position_to_write = str(position)
        position_to_read = str(position)
        if extraction:
            position_to_write+="m"

        current_pos = self.serial_connection.write_and_check("B"+position_to_write+"\r","B"+position_to_read)
        self.emission_wheel_pos = int(current_pos[1])
        return self.emission_wheel_pos

    def get_emission_filter(self):
        current_pos = self.serial_connection.write_and_check("rB\r","rB")
        self.emission_wheel_pos = int(current_pos[2])
        return self.emission_wheel_pos

    def set_dichroic(self, position,extraction=False):
        if str(position) not in ["1","2","3","4","5"]:
            raise ValueError("Invalid dichroic wheel position!")
        position_to_write = str(position)
        position_to_read = str(position)
        if extraction:
            position_to_write+="m"

        current_pos = self.serial_connection.write_and_check("C"+position_to_write+"\r","C"+position_to_read)
        self.dichroic_wheel_pos = int(current_pos[1])
        return self.dichroic_wheel_pos


    def get_dichroic(self):
        current_pos = self.serial_connection.write_and_check("rC\r","rC")
        self.dichroic_wheel_pos = int(current_pos[2])
        return self.dichroic_wheel_pos


    def set_disk_position(self,position):
        if str(position) not in ["0","1","2","wide field","confocal"]:
            raise ValueError("Invalid disk position!")
        if position == "wide field":
            position = "0"

        if position == "confocal":
            position = "1'"

        position_to_write = str(position)
        position_to_read = str(position)

        current_pos = self.serial_connection.write_and_check("D"+position_to_write+"\r","D"+position_to_read)
        self.spinning_disk_pos = int(current_pos[1])
        return self.spinning_disk_pos

    def get_disk_position(self):
        current_pos = self.serial_connection.write_and_check("rD\r","rD")
        self.spinning_disk_pos = int(current_pos[2])
        return self.spinning_disk_pos

    def set_disk_motor_state(self, state):
        """Set True for ON, False for OFF"""
        if state:
            state_to_write = "1"
        else:
            state_to_write = "0"

        current_pos = self.serial_connection.write_and_check("N"+state_to_write+"\r","N"+state_to_write)

        self.disk_motor_state = bool(int(current_pos[1]))

    def get_disk_motor_state(self):
        """Return True for on, Off otherwise"""
        current_pos = self.serial_connection.write_and_check("rN\r","rN")
        self.disk_motor_state = bool(int(current_pos[2]))
        return self.disk_motor_state

class LDI:
    """Wrapper for communicating with LDI over serial"""
    def __init__(self, SN="00000001"):
        """
        Provide serial number (default is that of the device
        cephla already has) for device-finding purposes. Otherwise, all
        XLight devices should use the same serial protocol
        """
        self.serial_connection = SerialDevice(SN=SN,baudrate=9600,
                bytesize=serial.EIGHTBITS,stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE, 
                xonxoff=False,rtscts=False,dsrdtr=False)
        self.serial_connection.open_ser()
    
    def run(self):
        self.serial_connection.write_and_check("run!\r","ok")

    def set_intensity(self,channel,intensity):
        channel = str(channel)
        intensity = "{:.2f}".format(intensity)
        print('set:'+channel+'='+intensity+'\r')
        self.serial_connection.write_and_check('set:'+channel+'='+intensity+'\r',"ok")
        print('active channel: ' + str(self.active_channel))
    
    def set_shutter(self,channel,state):
        channel = str(channel)
        state = str(state)
        self.serial_connection.write_and_check('shutter:'+channel+'='+state+'\r',"ok")

    def get_shutter_state(self):
        self.serial_connection.write_and_check('shutter?\r','')

    def set_active_channel(self,channel):
        self.active_channel = channel
        print('[set active channel to ' + str(channel) + ']')

    def set_active_channel_shutter(self,state):
        channel = str(self.active_channel)
        state = str(state)
        print('shutter:'+channel+'='+state+'\r')
        self.serial_connection.write_and_check('shutter:'+channel+'='+state+'\r',"ok")