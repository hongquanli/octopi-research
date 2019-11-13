# updated on 11/12/2019

import time
import numpy as np

# do we need to import serial here?

class Piezo():
    pass

class Stepper():
    def __init__(self, motorID, serialPort, initial_position=0, steps_per_mm=1600):
        self.position = initial_position
        self.motorID = motorID
        self.ser = serialPort
        self.steps_per_mm = steps_per_mm

    def move(self, distance):
        
        direction = int((np.sign(distance)+1)/2)
        n_microsteps = abs(distance*self.steps_per_mm)
        if n_microsteps > 65535:
            n_microsteps = 65535

        cmd_str = '0000'
        cmd = bytearray(cmd_str.encode())
        cmd[0] = self.motorID
        cmd[1] = direction
        cmd[2] = int(n_microsteps) >> 8
        cmd[3] = int(n_microsteps) & 0xff
        self.ser.write(cmd)
        time.sleep(0.05)

        self.position = self.position + distance
