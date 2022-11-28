# qt libraries
from qtpy.QtCore import QObject, Signal # type: ignore

import control.utils as utils
from control._def import *
from control import camera

import time
import numpy as np
import cv2

from typing import Optional, List, Union, Tuple
from control.typechecker import TypecheckFunction

class StreamHandler(QObject):

    image_to_display = Signal(np.ndarray)
    packet_image_to_write = Signal(np.ndarray, int, float)
    packet_image_for_tracking = Signal(np.ndarray, int, float)
    signal_new_frame_received = Signal()

    def __init__(self,
        crop_width:int=Acquisition.CROP_WIDTH,
        crop_height:int=Acquisition.CROP_HEIGHT,
    ):
        QObject.__init__(self)
        self.fps_save:float = 1.0
        self.fps_track:float = 1.0
        self.timestamp_last_display = 0
        self.timestamp_last_save = 0
        self.timestamp_last_track = 0

        self.crop_width = crop_width
        self.crop_height = crop_height

        self.save_image_flag = False
        self.track_flag = False
        self.handler_busy = False

        # for fps measurement
        self.timestamp_last = 0
        self.counter = 0
        self.fps_real = 0

        self.last_image=None

    def start_recording(self):
        self.save_image_flag = True

    def stop_recording(self):
        self.save_image_flag = False

    def start_tracking(self):
        self.tracking_flag = True

    def stop_tracking(self):
        self.tracking_flag = False

    def set_save_fps(self,fps):
        self.fps_save = fps

    @TypecheckFunction
    def set_crop(self,crop_width:int,crop_height:int):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def process_image(self,camera):
        image_cropped = utils.crop_image(camera.current_frame,self.crop_width,self.crop_height)
        image_cropped = np.squeeze(image_cropped)
        image_cropped = utils.rotate_and_flip_image(image_cropped,rotate_image_angle=camera.rotate_image_angle,flip_image=camera.flip_image)

        return utils.crop_image(image_cropped,round(self.crop_width), round(self.crop_height))

    def on_new_frame(self, camera:camera.Camera):
        """ this is registered as callback when the camera has recorded an image """
        if camera.is_live:
            camera.image_locked = True
            self.handler_busy = True
            self.signal_new_frame_received.emit() # self.liveController.turn_off_illumination()

            # measure real fps
            MEASURE_REAL_FPS=False
            if MEASURE_REAL_FPS:
                timestamp_now = round(time.time())
                if timestamp_now == self.timestamp_last:
                    self.counter += 1
                else:
                    self.timestamp_last = timestamp_now
                    self.fps_real = self.counter
                    self.counter = 0
                    print('real camera fps is ' + str(self.fps_real))

            self.last_image=self.process_image(camera)

            # send image to display
            time_now = time.time()

            # there was an fps limit here at some point, but each image that was recorded after an image acquisition got triggered should also be displayed
            # self.image_to_display.emit(cv2.resize(image_cropped,(round(self.crop_width), round(self.crop_height)),cv2.INTER_LINEAR))
            self.image_to_display.emit(self.last_image)
            self.timestamp_last_display = time_now

            # send image to write
            if self.save_image_flag and time_now-self.timestamp_last_save >= 1/self.fps_save:
                if camera.is_color:
                    packet_image = cv2.cvtColor(self.last_image,cv2.COLOR_RGB2BGR)
                else:
                    packet_image=self.last_image
                self.packet_image_to_write.emit(packet_image,camera.frame_ID,camera.timestamp)
                self.timestamp_last_save = time_now

            self.handler_busy = False
            camera.image_locked = False
