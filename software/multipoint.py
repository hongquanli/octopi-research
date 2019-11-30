import tkinter as tk
import datetime
import threading
import serial
import cv2
import motion
import numpy
from time import sleep
from datetime import datetime
import time
import numpy as np
import time
from numpy import std
from numpy import square
from numpy import mean

import imaging


############################################################################################
################                          Functions                         ################
############################################################################################
def enableLED(ser):
    cmd_str = '0000'
    cmd = bytearray(cmd_str.encode())
    cmd[0] = 3
    cmd[1] = 1
    ser.write(cmd)

def disableLED(ser):
    cmd_str = '0000'
    cmd = bytearray(cmd_str.encode())
    cmd[0] = 3
    cmd[1] = 0
    ser.write(cmd)

############################################################################################
################                         Parameters                         ################
############################################################################################
Nx = 3
Ny = 3
Nz = 10

Nt = 5

dx_mm = 1.6
dy_mm = 1.6
dz_um = 3
dt_s = 60

EXPERIMENT = ''

############################################################################################
################                         The Program                        ################
############################################################################################
ser = serial.Serial('/dev/ttyACM0', 12000000)

x_stepper = motion.Stepper(motorID=0, serialPort=ser, initial_position=0, steps_per_mm=1600)
y_stepper = motion.Stepper(motorID=1, serialPort=ser, initial_position=0, steps_per_mm=1600)
z_stepper = motion.Stepper(motorID=2, serialPort=ser, initial_position=0, steps_per_mm=5333)

cam = imaging.USBCamera()
cam.connect()
cam.set_preview_roi_ratios(length_ratio=0.9, width_ratio=0.9)
cam.set_preview_resize_factor(0.5)

# set up the camera to use software-triggered aquisition
cam.set_triggered_acquisition()

# set exposure time
cam.set_exposure(30)

# move z to lower limit
z_stepper.move(-(Nz/2)*dz_um/1000)

enableLED()
sleep(0.1)

# multipoint aquistion
for k in range(Nt):

    # move along y
    for i in range(Ny):

        # move along x
        for j in range(Nx):

            # z stack
            for l in range(Nz):
                # get image
                cam.send_trigger()
                img_numpy = cam.get_image_numpy()
                # optional preview
                img_preview = cam.get_preview(img_numpy)
                cv2.imshow('Preview', img_preview)
                cv2.waitKey(10)
                # save image
                cv2.imwrite(EXPERIMENT + str(k) + '_' + str(i) + '_' + str(j) + '_' + str(l) + '.PNG',img_numpy)
                if l! = Nz-1:
                    # move z forward
                    z_stepper.move(dz_um/1000)

            # move z back
            z_stepper.move(-(Nz-1)*dz_um/1000)
            
            if j != Nx - 1:
                # move x forward
                x_stepper.move(dx_mm)

        # move x back
        x_stepper.move(-(Nx-1)*dx_mm)

        if i != Ny - 1:
            # move y forward
            y_stepper.move(dy_mm)

    # move y back
    y_stepper.move(-(Ny-1)*dy_mm)

    disableLED()
    sleep(dt_s)
    enableLED()
    sleep(0.1)

# disconnect
cam.disconnect()

'''
############################################################################################
################                          Functions                         ################
############################################################################################
def autofocus(N,step,label_zPos):
    FM = [0]*(2*N+1)
    FM_max = 0
    step = step/1000

    z_stepper.move(-N*step);
    label_zPos.config(text = str(z_stepper.position))
    sleep(0.1)

    j = 0
    for i in range(2*N+1):
        
        z_stepper.move(step);
        label_zPos.config(text = str(z_stepper.position))
        j = j + 1 # number of steps that have been moved
        #app.update()
        sleep(0.02)

        img = cam.last_numpy_image
        ROI = img[1500-300:1500+300,2000-300:2000+300]
        lap = cv2.Laplacian(ROI,cv2.CV_16S)
        fm = mean(square(lap))
        print(i, fm)
        FM[i] = fm
        FM_max = max(fm,FM_max)
        if fm < FM_max*0.85:
            break
        
    idx = FM.index(max(FM))

    z_stepper.move(-j*step);
    z_stepper.move(step*(idx+1))
    label_zPos.config(text = str(z_stepper.position))
'''