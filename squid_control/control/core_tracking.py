# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import control.utils as utils
from control._def import *
import control.tracking as tracking

from queue import Queue
from threading import Thread, Lock
import time
import numpy as np
import pyqtgraph as pg
import cv2
from datetime import datetime

class TrackingController(QObject):
    def __init__(self,microcontroller,navigationController):
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.navigationController = navigationController
        self.tracker_xy = tracking.Tracker_XY()
        self.tracker_z = tracking.Tracker_Z()
        self.pid_controller_x = tracking.PID_Controller()
        self.pid_controller_y = tracking.PID_Controller()
        self.pid_controller_z = tracking.PID_Controller()
        self.tracking_frame_counter = 0

    def on_new_frame(self,image,frame_ID,timestamp):
        # initialize the tracker when a new track is started
        if self.tracking_frame_counter == 0:
            # initialize the tracker
            # initialize the PID controller
            pass

        # crop the image, resize the image 
        # [to fill]

        # get the location
        [x,y] = self.tracker_xy.track(image)
        z = self.track_z.track(image)
        # note that z tracking may use a different image from a different camera, we can implement two different on_new_frame callback function, one for xy tracking and one for z tracking
        # another posibility is to read the current frame(s) from the z tracking camera (instead of using callback) when a new frame for XY tracking arrives
        # if would be ideal if xy and z tracking runs in independent threads (processes?) (not Threading) and push error correction commands to a shared queue
        # more thoughts are needed

        # get motion commands
        dx = self.pid_controller_x.get_actuation(x)
        dy = self.pid_controller_y.get_actuation(y)
        dz = self.pid_controller_z.get_actuation(z)

        # read current location from the microcontroller
        current_stage_position = self.microcontroller.read_received_packet()

        # save the coordinate information (possibly enqueue image for saving here to if a separate ImageSaver object is being used) before the next movement
        # [to fill]

        # generate motion commands
        motion_commands = self.generate_motion_commands(self,dx,dy,dz)

        # send motion commands
        self.microcontroller.send_command(motion_commands)

    def start_a_new_track(self):
        self.tracking_frame_counter = 0