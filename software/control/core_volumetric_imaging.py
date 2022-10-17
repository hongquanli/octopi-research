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

from lxml import etree as ET
from pathlib import Path
import control.utils_config as utils_config


class StreamHandler(QObject):

    image_to_display = Signal(np.ndarray)
    packet_image_to_write = Signal(np.ndarray, int, float)
    packet_image_for_tracking = Signal(np.ndarray, int, float)
    packet_image_for_array_display = Signal(np.ndarray, int)
    signal_new_frame_received = Signal()

    def __init__(self,crop_width=Acquisition.CROP_WIDTH,crop_height=Acquisition.CROP_HEIGHT,display_resolution_scaling=0.5):
        QObject.__init__(self)
        self.fps_display = 1
        self.fps_save = 1
        self.fps_track = 1
        self.timestamp_last_display = 0
        self.timestamp_last_save = 0
        self.timestamp_last_track = 0

        self.crop_width = crop_width
        self.crop_height = crop_height
        self.display_resolution_scaling = display_resolution_scaling

        self.save_image_flag = False
        self.track_flag = False
        self.handler_busy = False

        # for fps measurement
        self.timestamp_last = 0
        self.counter = 0
        self.fps_real = 0

    def start_recording(self):
        self.save_image_flag = True

    def stop_recording(self):
        self.save_image_flag = False

    def start_tracking(self):
        self.tracking_flag = True

    def stop_tracking(self):
        self.tracking_flag = False

    def set_display_fps(self,fps):
        self.fps_display = fps

    def set_save_fps(self,fps):
        self.fps_save = fps

    def set_crop(self,crop_width,height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def set_display_resolution_scaling(self, display_resolution_scaling):
        self.display_resolution_scaling = display_resolution_scaling/100
        print(self.display_resolution_scaling)

    def on_new_frame(self, camera):

        camera.image_locked = True
        self.handler_busy = True
        self.signal_new_frame_received.emit() # self.liveController.turn_off_illumination()

        # measure real fps
        timestamp_now = round(time.time())
        if timestamp_now == self.timestamp_last:
            self.counter = self.counter+1
        else:
            self.timestamp_last = timestamp_now
            self.fps_real = self.counter
            self.counter = 0
            print('real camera fps is ' + str(self.fps_real))

        # crop image
        image_cropped = utils.crop_image(camera.current_frame,self.crop_width,self.crop_height)
        image_cropped = np.squeeze(image_cropped)

        # send image to display
        time_now = time.time()
        if time_now-self.timestamp_last_display >= 1/self.fps_display:
            # self.image_to_display.emit(cv2.resize(image_cropped,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
            self.image_to_display.emit(utils.crop_image(image_cropped,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)))
            self.timestamp_last_display = time_now

        # send image to array display
        self.packet_image_for_array_display.emit(image_cropped,(camera.frame_ID - camera.frame_ID_offset_hardware_trigger - 1) % VOLUMETRIC_IMAGING.NUM_PLANES_PER_VOLUME)

        # send image to write
        if self.save_image_flag and time_now-self.timestamp_last_save >= 1/self.fps_save:
            if camera.is_color:
                image_cropped = cv2.cvtColor(image_cropped,cv2.COLOR_RGB2BGR)
            self.packet_image_to_write.emit(image_cropped,camera.frame_ID,camera.timestamp)
            self.timestamp_last_save = time_now

        # send image to track
        if self.track_flag and time_now-self.timestamp_last_track >= 1/self.fps_track:
            # track is a blocking operation - it needs to be
            # @@@ will cropping before emitting the signal lead to speedup?
            self.packet_image_for_tracking.emit(image_cropped,camera.frame_ID,camera.timestamp)
            self.timestamp_last_track = time_now

        self.handler_busy = False
        camera.image_locked = False


class ImageArrayDisplayWindow(QMainWindow):

    def __init__(self, window_title=''):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.widget = QWidget()

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')

        self.sub_windows = []
        for i in range(9):
            self.sub_windows.append(pg.GraphicsLayoutWidget())
            self.sub_windows[i].view = self.sub_windows[i].addViewBox(enableMouse=True)
            self.sub_windows[i].img = pg.ImageItem(border='w')
            self.sub_windows[i].view.setAspectLocked(True)
            self.sub_windows[i].view.addItem(self.sub_windows[i].img)

        ## Layout
        layout = QGridLayout()
        layout.addWidget(self.sub_windows[0], 0, 0)
        layout.addWidget(self.sub_windows[1], 0, 1)
        layout.addWidget(self.sub_windows[2], 0, 2)
        layout.addWidget(self.sub_windows[3], 1, 0) 
        layout.addWidget(self.sub_windows[4], 1, 1) 
        layout.addWidget(self.sub_windows[5], 1, 2) 
        layout.addWidget(self.sub_windows[6], 2, 0) 
        layout.addWidget(self.sub_windows[7], 2, 1) 
        layout.addWidget(self.sub_windows[8], 2, 2) 
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)

        # set window size
        desktopWidget = QDesktopWidget();
        width = min(desktopWidget.height()*0.9,1000) #@@@TO MOVE@@@#
        height = width
        self.setFixedSize(width,height)

    def display_image(self,image,i):
        if i < 9:
            self.sub_windows[i].img.setImage(image,autoLevels=False)
            self.sub_windows[i].view.autoRange(padding=0)
