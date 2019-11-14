import time

import gpio

class Piezo(gpio.DAC):
    pass


class Stepper(gpio.Device):
    def __init__(self, enable_pin, step_pin, dir_pin, initial_position=0):
        self.enable_pin = enable_pin
        self.enable_device = gpio.DigitalDevice(enable_pin)
        self.step_pin = step_pin
        self.step_device = gpio.DigitalDevice(step_pin, inverted=True)
        self.dir_pin = dir_pin
        self.dir_device = gpio.DigitalDevice(dir_pin, inverted=True)

        self.position = initial_position

    def connect(self):
        self.enable_device.connect()
        self.step_device.connect()
        self.dir_device.connect()

    def move(self, direction, steps, dt):
        if direction == 1:
            self.dir_device.enable()
        elif direction == -1:
            self.dir_device.disable()
        else:
            raise ValueError('Unsupported stepper direction: {}'.format(direction))

        steps = int(steps)
        dt = float(dt)
        self.position = self.position + direction * steps
        self.enable_device.enable()
        for i in range(steps):
            self.step_device.enable()
            time.sleep(dt / 2)
            self.step_device.disable()
            time.sleep(dt / 2)
        self.enable_device.disable()
