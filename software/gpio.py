try:
    import Jetson.GPIO as GPIO
except ImportError:
    print('Cannot use Jetson GPIO!')

try:
    import smbus  # sudo apt-get install python3-smbus i2c-tools; sudo i2cdetect -y 0
except ImportError:
    print('Cannot use I2C-based DACs!')


class Device(object):
    def connect(self):
        pass


class DigitalDevice(Device):
    def __init__(self, pin, inverted=False):
        self.pin = pin
        self.inverted = inverted
        self.state = None

    def connect(self):
        initial_value = GPIO.HIGH if self.inverted else GPIO.LOW
        GPIO.setup(self.pin, GPIO.OUT, initial=initial_value)
        self.state = False

    def enable(self):
        if self.inverted:
            GPIO.output(self.pin, GPIO.LOW)
        else:
            GPIO.output(self.pin, GPIO.HIGH)
        self.state = True

    def disable(self):
        if self.inverted:
            GPIO.output(self.pin, GPIO.HIGH)
        else:
            GPIO.output(self.pin, GPIO.LOW)
        self.state = False


class I2CBus(Device):
    def __init__(self, bus_index=1):
        self.device = None
        self.bus_index = bus_index

    def connect(self):
        self.device = smbus.SMBus(self.bus_index)


class DAC(object):
    def __init__(self, bus, addr=0x62):
        self.addr = addr
        self.bus = bus

    def set(self, value):
        value = int(value)
        self.bus.device.write_byte_data(self.addr, (value >> 8) & 0xFF, value & 0xFF)




def connect():
    GPIO.setmode(GPIO.BCM)

def disconnect():
    GPIO.cleanup()
