import os 
import sys
#from squid_control.control.processing_handler import ProcessingHandler
from squid_control.control.stitcher import Stitcher, default_image_reader

import squid_control.control.utils as utils
from squid_control.control._def import *
import squid_control.control.tracking as tracking
try:
    from squid_control.control.multipoint_custom_script_entry import *
    print('custom multipoint script found')
except:
    pass

from queue import Queue
from threading import Thread, Lock
import time
import numpy as np
import scipy
import scipy.signal
import cv2
from datetime import datetime

from lxml import etree as ET
from pathlib import Path
import squid_control.control.utils_config as utils_config

import math
import json
import pandas as pd

import imageio as iio

import subprocess
import threading
class ObjectiveStore:
    def __init__(self, objectives_dict = OBJECTIVES, default_objective = DEFAULT_OBJECTIVE):
        self.objectives_dict = objectives_dict
        self.default_objective = default_objective
        self.current_objective = default_objective

class StreamHandler():


    def __init__(self,crop_width=Acquisition.CROP_WIDTH,crop_height=Acquisition.CROP_HEIGHT,display_resolution_scaling=1):
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

    def set_crop(self,crop_width,crop_height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def set_display_resolution_scaling(self, display_resolution_scaling):
        self.display_resolution_scaling = display_resolution_scaling/100
        print(self.display_resolution_scaling)

    def on_new_frame(self, camera):

        if camera.is_live:

            camera.image_locked = True
            self.handler_busy = True

            # measure real fps
            timestamp_now = round(time.time())
            if timestamp_now == self.timestamp_last:
                self.counter = self.counter+1
            else:
                self.timestamp_last = timestamp_now
                self.fps_real = self.counter
                self.counter = 0
                print('real camera fps is ' + str(self.fps_real))

            # moved down (so that it does not modify the camera.current_frame, which causes minor problems for simulation) - 1/30/2022
            # # rotate and flip - eventually these should be done in the camera
            # camera.current_frame = utils.rotate_and_flip_image(camera.current_frame,rotate_image_angle=camera.rotate_image_angle,flip_image=camera.flip_image)

            # crop image
            image_cropped = utils.crop_image(camera.current_frame,self.crop_width,self.crop_height)
            image_cropped = np.squeeze(image_cropped)
            
            # # rotate and flip - moved up (1/10/2022)
            # image_cropped = utils.rotate_and_flip_image(image_cropped,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            # added on 1/30/2022
            # @@@ to move to camera 
            image_cropped = utils.rotate_and_flip_image(image_cropped,rotate_image_angle=camera.rotate_image_angle,flip_image=camera.flip_image)

            # send image to display
            time_now = time.time()
            if time_now-self.timestamp_last_display >= 1/self.fps_display:
                self.timestamp_last_display = time_now

            # send image to write
            if self.save_image_flag and time_now-self.timestamp_last_save >= 1/self.fps_save:
                if camera.is_color:
                    image_cropped = cv2.cvtColor(image_cropped,cv2.COLOR_RGB2BGR)
                self.timestamp_last_save = time_now

            # send image to track
            if self.track_flag and time_now-self.timestamp_last_track >= 1/self.fps_track:
                # track is a blocking operation - it needs to be

                self.timestamp_last_track = time_now

            self.handler_busy = False
            camera.image_locked = False

    '''
    def on_new_frame_from_simulation(self,image,frame_ID,timestamp):
        # check whether image is a local copy or pointer, if a pointer, needs to prevent the image being modified while this function is being executed
        
        self.handler_busy = True

        # crop image
        image_cropped = utils.crop_image(image,self.crop_width,self.crop_height)

        # send image to display
        time_now = time.time()
        if time_now-self.timestamp_last_display >= 1/self.fps_display:
            self.image_to_display.emit(cv2.resize(image_cropped,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
            self.timestamp_last_display = time_now

        # send image to write
        if self.save_image_flag and time_now-self.timestamp_last_save >= 1/self.fps_save:
            self.packet_image_to_write.emit(image_cropped,frame_ID,timestamp)
            self.timestamp_last_save = time_now

        # send image to track
        if time_now-self.timestamp_last_display >= 1/self.fps_track:
            # track emit
            self.timestamp_last_track = time_now

        self.handler_busy = False
    '''

class ImageSaver():


    def __init__(self,image_format=Acquisition.IMAGE_FORMAT):
        self.base_path = './'
        self.experiment_ID = ''
        self.image_format = image_format
        self.max_num_image_per_folder = 1000
        self.queue = Queue(10) # max 10 items in the queue
        self.image_lock = Lock()
        self.stop_signal_received = False
        self.thread = Thread(target=self.process_queue)
        self.thread.start()
        self.counter = 0
        self.recording_start_time = 0
        self.recording_time_limit = -1

    def process_queue(self):
        while True:
            # stop the thread if stop signal is received
            if self.stop_signal_received:
                return
            # process the queue
            try:
                [image,frame_ID,timestamp] = self.queue.get(timeout=0.1)
                self.image_lock.acquire(True)
                folder_ID = int(self.counter/self.max_num_image_per_folder)
                file_ID = int(self.counter%self.max_num_image_per_folder)
                # create a new folder
                if file_ID == 0:
                    os.mkdir(os.path.join(self.base_path,self.experiment_ID,str(folder_ID)))

                if image.dtype == np.uint16:
                    # need to use tiff when saving 16 bit images
                    saving_path = os.path.join(self.base_path,self.experiment_ID,str(folder_ID),str(file_ID) + '_' + str(frame_ID) + '.tiff')
                    iio.imwrite(saving_path,image)
                else:
                    saving_path = os.path.join(self.base_path,self.experiment_ID,str(folder_ID),str(file_ID) + '_' + str(frame_ID) + '.' + self.image_format)
                    cv2.imwrite(saving_path,image)

                self.counter = self.counter + 1
                self.queue.task_done()
                self.image_lock.release()
            except:
                pass
                            
    def enqueue(self,image,frame_ID,timestamp):
        try:
            self.queue.put_nowait([image,frame_ID,timestamp])
        except:
            print('imageSaver queue is full, image discarded')

    def set_base_path(self,path):
        self.base_path = path

    def set_recording_time_limit(self,time_limit):
        self.recording_time_limit = time_limit

    def start_new_experiment(self,experiment_ID,add_timestamp=True):
        if add_timestamp:
            # generate unique experiment ID
            self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f')
        else:
            self.experiment_ID = experiment_ID
        self.recording_start_time = time.time()
        # create a new folder
        try:
            os.mkdir(os.path.join(self.base_path,self.experiment_ID))
            # to do: save configuration
        except:
            pass
        # reset the counter
        self.counter = 0

    def close(self):
        self.queue.join()
        self.stop_signal_received = True
        self.thread.join()


class ImageSaver_Tracking():
    def __init__(self,base_path,image_format='bmp'):
        
        self.base_path = base_path
        self.image_format = image_format
        self.max_num_image_per_folder = 1000
        self.queue = Queue(100) # max 100 items in the queue
        self.image_lock = Lock()
        self.stop_signal_received = False
        self.thread = Thread(target=self.process_queue)
        self.thread.start()

    def process_queue(self):
        while True:
            # stop the thread if stop signal is received
            if self.stop_signal_received:
                return
            # process the queue
            try:
                [image,frame_counter,postfix] = self.queue.get(timeout=0.1)
                self.image_lock.acquire(True)
                folder_ID = int(frame_counter/self.max_num_image_per_folder)
                file_ID = int(frame_counter%self.max_num_image_per_folder)
                # create a new folder
                if file_ID == 0:
                    os.mkdir(os.path.join(self.base_path,str(folder_ID)))
                if image.dtype == np.uint16:
                    saving_path = os.path.join(self.base_path,str(folder_ID),str(file_ID) + '_' + str(frame_counter) + '_' + postfix + '.tiff')
                    iio.imwrite(saving_path,image)
                else:
                    saving_path = os.path.join(self.base_path,str(folder_ID),str(file_ID) + '_' + str(frame_counter) + '_' + postfix + '.' + self.image_format)
                    cv2.imwrite(saving_path,image)
                self.queue.task_done()
                self.image_lock.release()
            except:
                pass
                            
    def enqueue(self,image,frame_counter,postfix):
        try:
            self.queue.put_nowait([image,frame_counter,postfix])
        except:
            print('imageSaver queue is full, image discarded')

    def close(self):
        self.queue.join()
        self.stop_signal_received = True
        self.thread.join()



class Configuration:
    def __init__(self,mode_id=None,name=None,camera_sn=None,exposure_time=None,analog_gain=None,illumination_source=1,illumination_intensity=60, z_offset=None, pixel_format=None, _pixel_format_options=None):
        self.id = mode_id
        self.name = name
        self.exposure_time = exposure_time
        self.analog_gain = analog_gain
        self.illumination_source = illumination_source
        self.illumination_intensity = illumination_intensity
        self.camera_sn = camera_sn
        self.z_offset = z_offset
        self.pixel_format = pixel_format
        if self.pixel_format is None:
            self.pixel_format = "default"
        self._pixel_format_options = _pixel_format_options
        if _pixel_format_options is None:
            self._pixel_format_options = self.pixel_format

class LiveController():
    def __init__(self,camera,microcontroller,configurationManager,control_illumination=True,use_internal_timer_for_hardware_trigger=True,for_displacement_measurement=False):
        self.camera = camera
        self.microcontroller = microcontroller
        self.configurationManager = configurationManager
        self.currentConfiguration = None
        self.trigger_mode = TriggerMode.SOFTWARE # @@@ change to None
        self.is_live = False
        self.control_illumination = control_illumination
        self.illumination_on = False
        self.use_internal_timer_for_hardware_trigger = use_internal_timer_for_hardware_trigger # use QTimer vs timer in the MCU
        self.for_displacement_measurement = for_displacement_measurement

        self.fps_trigger = 1
        self.timer_trigger_interval = (1/self.fps_trigger)*1000

        self.timer_trigger = QTimer()
        self.timer_trigger.setInterval(int(self.timer_trigger_interval))
        self.timer_trigger.timeout.connect(self.trigger_acquisition)

        self.trigger_ID = -1

        self.fps_real = 0
        self.counter = 0
        self.timestamp_last = 0

        self.display_resolution_scaling = DEFAULT_DISPLAY_CROP/100

    # illumination control
    def turn_on_illumination(self):
        self.microcontroller.turn_on_illumination()
        self.illumination_on = True

    def turn_off_illumination(self):
        self.microcontroller.turn_off_illumination()
        self.illumination_on = False

    def set_illumination(self,illumination_source,intensity):
        if illumination_source < 10: # LED matrix
            self.microcontroller.set_illumination_led_matrix(illumination_source,r=(intensity/100)*LED_MATRIX_R_FACTOR,g=(intensity/100)*LED_MATRIX_G_FACTOR,b=(intensity/100)*LED_MATRIX_B_FACTOR)
        else:
            self.microcontroller.set_illumination(illumination_source,intensity)

    def start_live(self):
        self.is_live = True
        self.camera.is_live = True
        self.camera.start_streaming()
        if self.trigger_mode == TriggerMode.SOFTWARE or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
            self.camera.enable_callback() # in case it's disabled e.g. by the laser AF controller
            self._start_triggerred_acquisition()
        # if controlling the laser displacement measurement camera
        if self.for_displacement_measurement:
            self.microcontroller.set_pin_level(MCU_PINS.AF_LASER,1)

    def stop_live(self):
        if self.is_live:
            self.is_live = False
            self.camera.is_live = False
            if hasattr(self.camera,'stop_exposure'):
                self.camera.stop_exposure()
            if self.trigger_mode == TriggerMode.SOFTWARE:
                self._stop_triggerred_acquisition()
            # self.camera.stop_streaming() # 20210113 this line seems to cause problems when using af with multipoint
            if self.trigger_mode == TriggerMode.CONTINUOUS:
                self.camera.stop_streaming()
            if ( self.trigger_mode == TriggerMode.SOFTWARE ) or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
                self._stop_triggerred_acquisition()
            if self.control_illumination:
                self.turn_off_illumination()
            # if controlling the laser displacement measurement camera
            if self.for_displacement_measurement:
                self.microcontroller.set_pin_level(MCU_PINS.AF_LASER,0)

    # software trigger related
    def trigger_acquisition(self):
        if self.trigger_mode == TriggerMode.SOFTWARE:
            if self.control_illumination and self.illumination_on == False:
                self.turn_on_illumination()
            self.trigger_ID = self.trigger_ID + 1
            self.camera.send_trigger()
            # measure real fps
            timestamp_now = round(time.time())
            if timestamp_now == self.timestamp_last:
                self.counter = self.counter+1
            else:
                self.timestamp_last = timestamp_now
                self.fps_real = self.counter
                self.counter = 0
                # print('real trigger fps is ' + str(self.fps_real))
        elif self.trigger_mode == TriggerMode.HARDWARE:
            self.trigger_ID = self.trigger_ID + 1
            self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)

    def _start_triggerred_acquisition(self):
        self.timer_trigger.start()

    def _set_trigger_fps(self,fps_trigger):
        self.fps_trigger = fps_trigger
        self.timer_trigger_interval = (1/self.fps_trigger)*1000
        self.timer_trigger.setInterval(int(self.timer_trigger_interval))

    def _stop_triggerred_acquisition(self):
        self.timer_trigger.stop()

    # trigger mode and settings
    def set_trigger_mode(self,mode):
        if mode == TriggerMode.SOFTWARE:
            if self.is_live and ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
                self._stop_triggerred_acquisition()
            self.camera.set_software_triggered_acquisition()
            if self.is_live:
                self._start_triggerred_acquisition()
        if mode == TriggerMode.HARDWARE:
            if self.trigger_mode == TriggerMode.SOFTWARE and self.is_live:
                self._stop_triggerred_acquisition()
            # self.camera.reset_camera_acquisition_counter()
            self.camera.set_hardware_triggered_acquisition()
            self.microcontroller.set_strobe_delay_us(self.camera.strobe_delay_us)
            if self.is_live and self.use_internal_timer_for_hardware_trigger:
                self._start_triggerred_acquisition()
        if mode == TriggerMode.CONTINUOUS: 
            if ( self.trigger_mode == TriggerMode.SOFTWARE ) or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
                self._stop_triggerred_acquisition()
            self.camera.set_continuous_acquisition()
        self.trigger_mode = mode

    def set_trigger_fps(self,fps):
        if ( self.trigger_mode == TriggerMode.SOFTWARE ) or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
            self._set_trigger_fps(fps)
    
    # set microscope mode
    # @@@ to do: change softwareTriggerGenerator to TriggerGeneratror
    def set_microscope_mode(self,configuration):

        self.currentConfiguration = configuration
        print("setting microscope mode to " + self.currentConfiguration.name)
        
        # temporarily stop live while changing mode
        if self.is_live is True:
            self.timer_trigger.stop()
            if self.control_illumination:
                self.turn_off_illumination()

        # set camera exposure time and analog gain
        self.camera.set_exposure_time(self.currentConfiguration.exposure_time)
        self.camera.set_analog_gain(self.currentConfiguration.analog_gain)

        # set illumination
        if self.control_illumination:
            self.set_illumination(self.currentConfiguration.illumination_source,self.currentConfiguration.illumination_intensity)

        # restart live 
        if self.is_live is True:
            if self.control_illumination:
                self.turn_on_illumination()
            self.timer_trigger.start()

    def get_trigger_mode(self):
        return self.trigger_mode

    # slot
    def on_new_frame(self):
        if self.fps_trigger <= 5:
            if self.control_illumination and self.illumination_on == True:
                self.turn_off_illumination()

    def set_display_resolution_scaling(self, display_resolution_scaling):
        self.display_resolution_scaling = display_resolution_scaling/100

class NavigationController():



    def __init__(self,microcontroller):
        
        self.microcontroller = microcontroller
        self.x_pos_mm = 0
        self.y_pos_mm = 0
        self.z_pos_mm = 0
        self.z_pos = 0
        self.theta_pos_rad = 0
        self.x_microstepping = MICROSTEPPING_DEFAULT_X
        self.y_microstepping = MICROSTEPPING_DEFAULT_Y
        self.z_microstepping = MICROSTEPPING_DEFAULT_Z
        self.theta_microstepping = MICROSTEPPING_DEFAULT_THETA
        self.enable_joystick_button_action = True

        # to be moved to gui for transparency
        self.microcontroller.set_callback(self.update_pos)

        # self.timer_read_pos = QTimer()
        # self.timer_read_pos.setInterval(PosUpdate.INTERVAL_MS)
        # self.timer_read_pos.timeout.connect(self.update_pos)
        # self.timer_read_pos.start()

    def move_x(self,delta):
        self.microcontroller.move_x_usteps(int(delta/(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))))

    def move_y(self,delta):
        self.microcontroller.move_y_usteps(int(delta/(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))))

    def move_z(self,delta):
        self.microcontroller.move_z_usteps(int(delta/(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))))

    def move_x_to(self,delta):
        self.microcontroller.move_x_to_usteps(STAGE_MOVEMENT_SIGN_X*int(delta/(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))))

    def move_y_to(self,delta):
        self.microcontroller.move_y_to_usteps(STAGE_MOVEMENT_SIGN_Y*int(delta/(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))))

    def move_z_to(self,delta):
        self.microcontroller.move_z_to_usteps(STAGE_MOVEMENT_SIGN_Z*int(delta/(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))))

    def move_x_usteps(self,usteps):
        self.microcontroller.move_x_usteps(usteps)

    def move_y_usteps(self,usteps):
        self.microcontroller.move_y_usteps(usteps)

    def move_z_usteps(self,usteps):
        self.microcontroller.move_z_usteps(usteps)

    def update_pos(self,microcontroller):
        # get position from the microcontroller
        x_pos, y_pos, z_pos, theta_pos = microcontroller.get_pos()
        self.z_pos = z_pos
        # calculate position in mm or rad
        if USE_ENCODER_X:
            self.x_pos_mm = x_pos*ENCODER_POS_SIGN_X*ENCODER_STEP_SIZE_X_MM
        else:
            self.x_pos_mm = x_pos*STAGE_POS_SIGN_X*(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))
        if USE_ENCODER_Y:
            self.y_pos_mm = y_pos*ENCODER_POS_SIGN_Y*ENCODER_STEP_SIZE_Y_MM
        else:
            self.y_pos_mm = y_pos*STAGE_POS_SIGN_Y*(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))
        if USE_ENCODER_Z:
            self.z_pos_mm = z_pos*ENCODER_POS_SIGN_Z*ENCODER_STEP_SIZE_Z_MM
        else:
            self.z_pos_mm = z_pos*STAGE_POS_SIGN_Z*(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))
        if USE_ENCODER_THETA:
            self.theta_pos_rad = theta_pos*ENCODER_POS_SIGN_THETA*ENCODER_STEP_SIZE_THETA
        else:
            self.theta_pos_rad = theta_pos*STAGE_POS_SIGN_THETA*(2*math.pi/(self.theta_microstepping*FULLSTEPS_PER_REV_THETA))

        if microcontroller.signal_joystick_button_pressed_event:
            print('joystick button pressed')
            microcontroller.signal_joystick_button_pressed_event = False

        theta_pos=self.theta_pos_rad*360/(2*math.pi)

        return self.x_pos_mm , self.y_pos_mm , self.z_pos_mm , theta_pos
    
    def home_x(self):
        self.microcontroller.home_x()

    def home_y(self):
        self.microcontroller.home_y()

    def home_z(self):
        self.microcontroller.home_z()

    def home_theta(self):
        self.microcontroller.home_theta()

    def home_xy(self):
        self.microcontroller.home_xy()

    def zero_x(self):
        self.microcontroller.zero_x()

    def zero_y(self):
        self.microcontroller.zero_y()

    def zero_z(self):
        self.microcontroller.zero_z()

    def zero_theta(self):
        self.microcontroller.zero_tehta()

    def home(self):
        pass

    def set_x_limit_pos_mm(self,value_mm):
        if STAGE_MOVEMENT_SIGN_X > 0:
            self.microcontroller.set_lim(LIMIT_CODE.X_POSITIVE,int(value_mm/(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.X_NEGATIVE,STAGE_MOVEMENT_SIGN_X*int(value_mm/(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))))

    def set_x_limit_neg_mm(self,value_mm):
        if STAGE_MOVEMENT_SIGN_X > 0:
            self.microcontroller.set_lim(LIMIT_CODE.X_NEGATIVE,int(value_mm/(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.X_POSITIVE,STAGE_MOVEMENT_SIGN_X*int(value_mm/(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))))

    def set_y_limit_pos_mm(self,value_mm):
        if STAGE_MOVEMENT_SIGN_Y > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Y_POSITIVE,int(value_mm/(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Y_NEGATIVE,STAGE_MOVEMENT_SIGN_Y*int(value_mm/(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))))

    def set_y_limit_neg_mm(self,value_mm):
        if STAGE_MOVEMENT_SIGN_Y > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Y_NEGATIVE,int(value_mm/(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Y_POSITIVE,STAGE_MOVEMENT_SIGN_Y*int(value_mm/(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))))

    def set_z_limit_pos_mm(self,value_mm):
        if STAGE_MOVEMENT_SIGN_Z > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Z_POSITIVE,int(value_mm/(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Z_NEGATIVE,STAGE_MOVEMENT_SIGN_Z*int(value_mm/(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))))

    def set_z_limit_neg_mm(self,value_mm):
        if STAGE_MOVEMENT_SIGN_Z > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Z_NEGATIVE,int(value_mm/(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Z_POSITIVE,STAGE_MOVEMENT_SIGN_Z*int(value_mm/(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))))
    
    def move_to(self,x_mm,y_mm):
        self.move_x_to(x_mm)
        self.move_y_to(y_mm)

class SlidePositionControlWorker():
    

    def __init__(self,slidePositionController,home_x_and_y_separately=False):
        
        self.slidePositionController = slidePositionController
        self.navigationController = slidePositionController.navigationController
        self.microcontroller = self.navigationController.microcontroller
        self.liveController = self.slidePositionController.liveController
        self.home_x_and_y_separately = home_x_and_y_separately

    def wait_till_operation_is_completed(self,timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S):
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)
            if time.time() - timestamp_start > SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S:
                print('Error - slide position switching timeout, the program will exit')
                self.navigationController.move_x(0)
                self.navigationController.move_y(0)
                exit()

    def move_to_slide_loading_position(self):
        was_live = self.liveController.is_live

        # retract z
        timestamp_start = time.time()
        self.slidePositionController.z_pos = self.navigationController.z_pos # zpos at the beginning of the scan
        self.navigationController.move_z_to(OBJECTIVE_RETRACTED_POS_MM)
        self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
        print('z retracted')
        self.slidePositionController.objective_retracted = True
        
        # move to position
        # for well plate
        if self.slidePositionController.is_for_wellplate:
            # reset limits
            self.navigationController.set_x_limit_pos_mm(100)
            self.navigationController.set_x_limit_neg_mm(-100)
            self.navigationController.set_y_limit_pos_mm(100)
            self.navigationController.set_y_limit_neg_mm(-100)
            # home for the first time
            if self.slidePositionController.homing_done == False:
                print('running homing first')
                timestamp_start = time.time()
                # x needs to be at > + 20 mm when homing y
                self.navigationController.move_x(20)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                # home y
                self.navigationController.home_y()
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.zero_y()
                # home x
                self.navigationController.home_x()
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.zero_x()
                self.slidePositionController.homing_done = True
            # homing done previously
            else:
                timestamp_start = time.time()
                self.navigationController.move_x_to(20)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.move_y_to(SLIDE_POSITION.LOADING_Y_MM)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.move_x_to(SLIDE_POSITION.LOADING_X_MM)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
            # set limits again
            self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
            self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
            self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
            self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
        else:

            # for glass slide
            if self.slidePositionController.homing_done == False or SLIDE_POTISION_SWITCHING_HOME_EVERYTIME:
                if self.home_x_and_y_separately:
                    timestamp_start = time.time()
                    self.navigationController.home_x()
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.zero_x()
                    self.navigationController.move_x(SLIDE_POSITION.LOADING_X_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.home_y()
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.zero_y()
                    self.navigationController.move_y(SLIDE_POSITION.LOADING_Y_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                else:
                    timestamp_start = time.time()
                    self.navigationController.home_xy()
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.zero_x()
                    self.navigationController.zero_y()
                    self.navigationController.move_x(SLIDE_POSITION.LOADING_X_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.move_y(SLIDE_POSITION.LOADING_Y_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.slidePositionController.homing_done = True
            else:
                timestamp_start = time.time()
                self.navigationController.move_y(SLIDE_POSITION.LOADING_Y_MM-self.navigationController.y_pos_mm)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.move_x(SLIDE_POSITION.LOADING_X_MM-self.navigationController.x_pos_mm)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)


        self.slidePositionController.slide_loading_position_reached = True
        

    def move_to_slide_scanning_position(self):
        was_live = self.liveController.is_live


        # move to position
        # for well plate
        if self.slidePositionController.is_for_wellplate:
            # home for the first time
            if self.slidePositionController.homing_done == False:
                timestamp_start = time.time()

                # x needs to be at > + 20 mm when homing y
                self.navigationController.move_x(20)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                # home y
                self.navigationController.home_y()
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.zero_y()
                # home x
                self.navigationController.home_x()
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.zero_x()
                self.slidePositionController.homing_done = True
                # move to scanning position
                self.navigationController.move_x_to(SLIDE_POSITION.SCANNING_X_MM)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)

                self.navigationController.move_y_to(SLIDE_POSITION.SCANNING_Y_MM)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                   
            else:
                timestamp_start = time.time()
                self.navigationController.move_x_to(SLIDE_POSITION.SCANNING_X_MM)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.move_y_to(SLIDE_POSITION.SCANNING_Y_MM)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
        else:
            if self.slidePositionController.homing_done == False or SLIDE_POTISION_SWITCHING_HOME_EVERYTIME:
                if self.home_x_and_y_separately:
                    timestamp_start = time.time()
                    self.navigationController.home_y()
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.zero_y()
                    self.navigationController.move_y(SLIDE_POSITION.SCANNING_Y_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.home_x()
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.zero_x()
                    self.navigationController.move_x(SLIDE_POSITION.SCANNING_X_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                else:
                    timestamp_start = time.time()
                    self.navigationController.home_xy()
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.zero_x()
                    self.navigationController.zero_y()
                    self.navigationController.move_y(SLIDE_POSITION.SCANNING_Y_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                    self.navigationController.move_x(SLIDE_POSITION.SCANNING_X_MM)
                    self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.slidePositionController.homing_done = True
            else:
                timestamp_start = time.time()
                self.navigationController.move_y(SLIDE_POSITION.SCANNING_Y_MM-self.navigationController.y_pos_mm)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.move_x(SLIDE_POSITION.SCANNING_X_MM-self.navigationController.x_pos_mm)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)

        # restore z
        if self.slidePositionController.objective_retracted:
            _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
            self.navigationController.microcontroller.move_z_to_usteps(self.slidePositionController.z_pos - STAGE_MOVEMENT_SIGN_Z*_usteps_to_clear_backlash)
            self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
            self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
            self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
            self.slidePositionController.objective_retracted = False
            print('z position restored')
        

        self.slidePositionController.slide_scanning_position_reached = True

class SlidePositionController():

    def __init__(self,navigationController,liveController,is_for_wellplate=True):
        self.navigationController = navigationController
        self.liveController = liveController
        self.slide_loading_position_reached = False
        self.slide_scanning_position_reached = False
        self.homing_done = False
        self.is_for_wellplate = is_for_wellplate
        self.retract_objective_before_moving = RETRACT_OBJECTIVE_BEFORE_MOVING_TO_LOADING_POSITION
        self.objective_retracted = False
        self.thread = None

    def move_to_slide_loading_position(self):

        # create a worker object
        self.slidePositionControlWorker = SlidePositionControlWorker(self)

    def move_to_slide_scanning_position(self):
        # create a worker object
        self.slidePositionControlWorker = SlidePositionControlWorker(self)
        # move the worker to the thread
        self.slidePositionControlWorker.moveToThread(self.thread)

        # start the thread
        print('before thread.start()')

    def slot_stop_live(self):
        self.liveController.stop_live()

    def slot_resume_live(self):
        self.liveController.start_live()

    # def threadFinished(self):
    # 	print('========= threadFinished ========= ')

class AutofocusWorker():

    def __init__(self,autofocusController):
        self.autofocusController = autofocusController

        self.camera = self.autofocusController.camera
        self.microcontroller = self.autofocusController.navigationController.microcontroller
        self.navigationController = self.autofocusController.navigationController
        self.liveController = self.autofocusController.liveController

        self.N = self.autofocusController.N
        self.deltaZ = self.autofocusController.deltaZ
        self.deltaZ_usteps = self.autofocusController.deltaZ_usteps
        
        self.crop_width = self.autofocusController.crop_width
        self.crop_height = self.autofocusController.crop_height

    def run(self):
        self.run_autofocus()

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)

    def run_autofocus(self):
        # @@@ to add: increase gain, decrease exposure time
        # @@@ can move the execution into a thread - done 08/21/2021
        focus_measure_vs_z = [0]*self.N
        focus_measure_max = 0

        z_af_offset_usteps = self.deltaZ_usteps*round(self.N/2)
        # self.navigationController.move_z_usteps(-z_af_offset_usteps) # combine with the back and forth maneuver below
        # self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        # can be moved to the firmware
        _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
        self.navigationController.move_z_usteps(-_usteps_to_clear_backlash-z_af_offset_usteps)
        self.wait_till_operation_is_completed()
        self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
        self.wait_till_operation_is_completed()

        steps_moved = 0
        for i in range(self.N):
            self.navigationController.move_z_usteps(self.deltaZ_usteps)
            self.wait_till_operation_is_completed()
            steps_moved = steps_moved + 1
            # trigger acquisition (including turning on the illumination)
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                self.liveController.turn_on_illumination()
                self.wait_till_operation_is_completed()
                self.camera.send_trigger()
            elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
            # read camera frame
            image = self.camera.read_frame()
            if image is None:
                continue
            # tunr of the illumination if using software trigger
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                self.liveController.turn_off_illumination()
            image = utils.crop_image(image,self.crop_width,self.crop_height)
            image = utils.rotate_and_flip_image(image,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)
            
            timestamp_0 = time.time()
            focus_measure = utils.calculate_focus_measure(image,FOCUS_MEASURE_OPERATOR)
            timestamp_1 = time.time()
            print('             calculating focus measure took ' + str(timestamp_1-timestamp_0) + ' second')
            focus_measure_vs_z[i] = focus_measure
            print(i,focus_measure)
            focus_measure_max = max(focus_measure, focus_measure_max)
            if focus_measure < focus_measure_max*AF.STOP_THRESHOLD:
                break

        # move to the starting location
        # self.navigationController.move_z_usteps(-steps_moved*self.deltaZ_usteps) # combine with the back and forth maneuver below
        # self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        self.navigationController.move_z_usteps(-_usteps_to_clear_backlash-steps_moved*self.deltaZ_usteps)
        # determine the in-focus position
        idx_in_focus = focus_measure_vs_z.index(max(focus_measure_vs_z))
        self.wait_till_operation_is_completed()
        self.navigationController.move_z_usteps(_usteps_to_clear_backlash+(idx_in_focus+1)*self.deltaZ_usteps)
        self.wait_till_operation_is_completed()

        # move to the calculated in-focus position
        # self.navigationController.move_z_usteps(idx_in_focus*self.deltaZ_usteps)
        # self.wait_till_operation_is_completed() # combine with the movement above
        if idx_in_focus == 0:
            print('moved to the bottom end of the AF range')
        if idx_in_focus == self.N-1:
            print('moved to the top end of the AF range')

class AutoFocusController():


    def __init__(self,camera,navigationController,liveController):
        self.camera = camera
        self.navigationController = navigationController
        self.liveController = liveController
        self.N = 15
        self.deltaZ = None
        self.deltaZ_um = 1.524
        self.deltaZ_usteps = None
        self.crop_width = AF.CROP_WIDTH
        self.crop_height = AF.CROP_HEIGHT
        self.autofocus_in_progress = False

    def set_N(self,N):
        self.N = N

    def set_deltaZ(self,deltaZ_um):
        mm_per_ustep_Z = SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        self.deltaZ = deltaZ_um/1000
        self.deltaZ_usteps = round((deltaZ_um/1000)/mm_per_ustep_Z)
    
    ###########################
        # Set deltaZ!
    ###########################


    def set_crop(self,crop_width,crop_height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def autofocus(self):
        # stop live
        if self.liveController.is_live:
            self.was_live_before_autofocus = True
            self.liveController.stop_live()
        else:
            self.was_live_before_autofocus = False

        # temporarily disable call back -> image does not go through streamHandler
        if self.camera.callback_is_enabled:
            self.callback_was_enabled_before_autofocus = True
            self.camera.disable_callback()
        else:
            self.callback_was_enabled_before_autofocus = False

        self.autofocus_in_progress = True

        try:
            if self.thread.isRunning():
                print('*** autofocus thread is still running ***')
                self.thread.terminate()
                self.thread.wait()
                print('*** autofocus threaded manually stopped ***')
        except:
            pass
        
        # create a worker object
        self.autofocusWorker = AutofocusWorker(self)

        self.autofocusWorker.run()
        self._on_autofocus_completed()
        
    def _on_autofocus_completed(self):
        # re-enable callback
        if self.callback_was_enabled_before_autofocus:
            self.camera.enable_callback()
        
        # re-enable live if it's previously on
        if self.was_live_before_autofocus:
            self.liveController.start_live()

        print('autofocus finished')

        # update the state
        self.autofocus_in_progress = False


    def wait_till_autofocus_has_completed(self):
        while self.autofocus_in_progress == True:
            time.sleep(0.005)
        print('autofocus wait has completed, exit wait')

class MultiPointWorker():

    def __init__(self,multiPointController):
        self.multiPointController = multiPointController
        self.start_time = 0
        #self.processingHandler = multiPointController.processingHandler
        self.camera = self.multiPointController.camera
        self.microcontroller = self.multiPointController.microcontroller
        self.usb_spectrometer = self.multiPointController.usb_spectrometer
        self.navigationController = self.multiPointController.navigationController
        self.liveController = self.multiPointController.liveController
        self.autofocusController = self.multiPointController.autofocusController
        self.configurationManager = self.multiPointController.configurationManager
        self.NX = self.multiPointController.NX
        self.NY = self.multiPointController.NY
        self.NZ = self.multiPointController.NZ
        self.Nt = self.multiPointController.Nt
        self.deltaX = self.multiPointController.deltaX
        self.deltaX_usteps = self.multiPointController.deltaX_usteps
        self.deltaY = self.multiPointController.deltaY
        self.deltaY_usteps = self.multiPointController.deltaY_usteps
        self.deltaZ = self.multiPointController.deltaZ
        self.deltaZ_usteps = self.multiPointController.deltaZ_usteps
        self.dt = self.multiPointController.deltat
        self.do_autofocus = self.multiPointController.do_autofocus
        self.do_reflection_af= self.multiPointController.do_reflection_af
        self.crop_width = self.multiPointController.crop_width
        self.crop_height = self.multiPointController.crop_height
        self.display_resolution_scaling = self.multiPointController.display_resolution_scaling
        self.counter = self.multiPointController.counter
        self.experiment_ID = self.multiPointController.experiment_ID
        self.base_path = self.multiPointController.base_path
        self.selected_configurations = self.multiPointController.selected_configurations
        self.detection_stats = {}
        self.async_detection_stats = {}

        self.timestamp_acquisition_started = self.multiPointController.timestamp_acquisition_started
        self.time_point = 0

        self.microscope = self.multiPointController.parent

        self.t_dpc = []
        self.t_inf = []
        self.t_over=[]
        

    def update_stats(self, new_stats):
        for k in new_stats.keys():
            try:
                self.detection_stats[k]+=new_stats[k]
            except:
                self.detection_stats[k] = 0
                self.detection_stats[k]+=new_stats[k]
        if "Total RBC" in self.detection_stats and "Total Positives" in self.detection_stats:
            self.detection_stats["Positives per 5M RBC"] = 5e6*(self.detection_stats["Total Positives"]/self.detection_stats["Total RBC"])

    def run(self):

        self.start_time = time.perf_counter_ns()
        if self.camera.is_streaming == False:
             self.camera.start_streaming()

        if self.multiPointController.location_list is None:
            # use scanCoordinates for well plates or regular multipoint scan
            if self.multiPointController.scanCoordinates!=None:
                # use scan coordinates for the scan
                self.multiPointController.scanCoordinates.get_selected_wells()
                self.scan_coordinates_mm = self.multiPointController.scanCoordinates.coordinates_mm
                self.scan_coordinates_name = self.multiPointController.scanCoordinates.name
                self.use_scan_coordinates = True
            else:
                # use the current position for the scan
                self.scan_coordinates_mm = [(self.navigationController.x_pos_mm,self.navigationController.y_pos_mm)]
                self.scan_coordinates_name = ['']
                self.use_scan_coordinates = False
        else:
            # use location_list specified by the multipoint controlller
            self.scan_coordinates_mm = self.multiPointController.location_list
            self.scan_coordinates_name = None
            self.use_scan_coordinates = True

        while self.time_point < self.Nt:
            # check if abort acquisition has been requested
            if self.multiPointController.abort_acqusition_requested:
                break
            # run single time point
            self.run_single_time_point()
            self.time_point = self.time_point + 1
            # continous acquisition
            if self.dt == 0:
                pass
            # timed acquisition
            else:
                # check if the aquisition has taken longer than dt or integer multiples of dt, if so skip the next time point(s)
                while time.time() > self.timestamp_acquisition_started + self.time_point*self.dt:
                    print('skip time point ' + str(self.time_point+1))
                    self.time_point = self.time_point+1
                # check if it has reached Nt
                if self.time_point == self.Nt:
                    break # no waiting after taking the last time point
                # wait until it's time to do the next acquisition
                while time.time() < self.timestamp_acquisition_started + self.time_point*self.dt:
                    if self.multiPointController.abort_acqusition_requested:
                        break
                    time.sleep(0.05)
        # self.processingHandler.processing_queue.join()
        # self.processingHandler.upload_queue.join()
        elapsed_time = time.perf_counter_ns()-self.start_time
        print("Time taken for acquisition/processing: "+str(elapsed_time/10**9))
        

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)

    def run_single_time_point(self):
        start = time.time()
        print(time.time())
        # disable joystick button action
        self.navigationController.enable_joystick_button_action = False

        print('multipoint acquisition - time point ' + str(self.time_point+1))
        
        # for each time point, create a new folder
        current_path = os.path.join(self.base_path,self.experiment_ID,str(self.time_point))
        os.mkdir(current_path)

        # create a dataframe to save coordinates
        self.coordinates_pd = pd.DataFrame(columns = ['i', 'j', 'k', 'x (mm)', 'y (mm)', 'z (um)'])

        n_regions = len(self.scan_coordinates_mm)

        for coordinate_id in range(n_regions):

            coordiante_mm = self.scan_coordinates_mm[coordinate_id]
            print(coordiante_mm)

            if self.scan_coordinates_name is None:
                # flexible scan, use a sequencial ID
                coordiante_name = str(coordinate_id)
            else:
                coordiante_name = self.scan_coordinates_name[coordinate_id]
            
            if self.use_scan_coordinates:
                # move to the specified coordinate
                self.navigationController.move_x_to(coordiante_mm[0]-self.deltaX*(self.NX-1)/2)
                self.navigationController.move_y_to(coordiante_mm[1]-self.deltaY*(self.NY-1)/2)
                # check if z is included in the coordinate
                if len(coordiante_mm) == 3:
                    if coordiante_mm[2] >= self.navigationController.z_pos_mm:
                        self.navigationController.move_z_to(coordiante_mm[2])
                        self.wait_till_operation_is_completed()
                    else:
                        self.navigationController.move_z_to(coordiante_mm[2])
                        self.wait_till_operation_is_completed()
                        # remove backlash
                        _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                        self.navigationController.move_z_usteps(-_usteps_to_clear_backlash) # to-do: combine this with the above
                        self.wait_till_operation_is_completed()
                        self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                        self.wait_till_operation_is_completed()
                else:
                    self.wait_till_operation_is_completed()
                time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
                if len(coordiante_mm) == 3:
                    time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
                # add '_' to the coordinate name
                coordiante_name = coordiante_name + '_'

            self.x_scan_direction = 1
            self.dx_usteps = 0 # accumulated x displacement
            self.dy_usteps = 0 # accumulated y displacement
            self.dz_usteps = 0 # accumulated z displacement
            z_pos = self.navigationController.z_pos # zpos at the beginning of the scan

            # z stacking config
            if Z_STACKING_CONFIG == 'FROM TOP':
                self.deltaZ_usteps = -abs(self.deltaZ_usteps)

            # along y
            for i in range(self.NY):

                self.FOV_counter = 0 # for AF, so that AF at the beginning of each new row

                # along x
                for j in range(self.NX):

                    if RUN_CUSTOM_MULTIPOINT and "multipoint_custom_script_entry" in globals():

                        print('run custom multipoint')
                        multipoint_custom_script_entry(self,self.time_point,current_path,coordinate_id,coordiante_name,i,j)

                    else:

                        # autofocus
                        if self.do_reflection_af == False:
                            # contrast-based AF; perform AF only if when not taking z stack or doing z stack from center
                            if ( (self.NZ == 1) or Z_STACKING_CONFIG == 'FROM CENTER' ) and (self.do_autofocus) and (self.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
                            # temporary: replace the above line with the line below to AF every FOV
                            # if (self.NZ == 1) and (self.do_autofocus):
                                configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                                config_AF = next((config for config in self.configurationManager.configurations if config.name == configuration_name_AF))
                                self.autofocusController.autofocus()
                                self.autofocusController.wait_till_autofocus_has_completed()
                                # upate z location of scan_coordinates_mm after AF
                                if len(coordiante_mm) == 3:
                                    self.scan_coordinates_mm[coordinate_id,2] = self.navigationController.z_pos_mm
                                    # update the coordinate in the widget
                                    try:
                                        self.microscope.multiPointWidget2._update_z(coordinate_id,self.navigationController.z_pos_mm)
                                    except:
                                        pass
                        else:
                            # initialize laser autofocus if it has not been done
                            if self.laserAutofocusController.is_initialized==False:
                                # initialize the reflection AF
                                self.microscope.laserAutofocusController.initialize_auto()
                                # do contrast AF for the first FOV (if contrast AF box is checked)
                                if self.do_autofocus and ( (self.NZ == 1) or Z_STACKING_CONFIG == 'FROM CENTER' ) :
                                    configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                                    config_AF = next((config for config in self.configurationManager.configurations if config.name == configuration_name_AF))
                                    self.autofocusController.autofocus()
                                    self.autofocusController.wait_till_autofocus_has_completed()
                                # set the current plane as reference
                                self.microscope.laserAutofocusController.set_reference()
                            else:
                                self.microscope.laserAutofocusController.move_to_target(0)
                                self.microscope.laserAutofocusController.move_to_target(0) # for stepper in open loop mode, repeat the operation to counter backlash 

                        if (self.NZ > 1):
                            # move to bottom of the z stack
                            if Z_STACKING_CONFIG == 'FROM CENTER':
                                self.navigationController.move_z_usteps(-self.deltaZ_usteps*round((self.NZ-1)/2))
                                self.wait_till_operation_is_completed()
                                time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
                            # maneuver for achiving uniform step size and repeatability when using open-loop control
                            self.navigationController.move_z_usteps(-160)
                            self.wait_till_operation_is_completed()
                            self.navigationController.move_z_usteps(160)
                            self.wait_till_operation_is_completed()
                            time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

                        # z-stack
                        for k in range(self.NZ):

                            file_ID = coordiante_name + str(i) + '_' + str(j if self.x_scan_direction==1 else self.NX-1-j) + '_' + str(k)
                            # metadata = dict(x = self.navigationController.x_pos_mm, y = self.navigationController.y_pos_mm, z = self.navigationController.z_pos_mm)
                            # metadata = json.dumps(metadata)


                            current_round_images = {}
                            # iterate through selected modes
                            for config in self.selected_configurations:
                                if config.z_offset is not None: # perform z offset for config, assume
                                                                # z_offset is in um
                                    if config.z_offset != 0.0:
                                        print("Moving to Z offset "+str(config.z_offset))
                                        self.navigationController.move_z(config.z_offset/1000)
                                        self.wait_till_operation_is_completed()
                                        time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

                                if 'USB Spectrometer' not in config.name:
                                    # update the current configuration
                                    self.wait_till_operation_is_completed()
                                    # trigger acquisition (including turning on the illumination)
                                    if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                        self.liveController.turn_on_illumination()
                                        self.wait_till_operation_is_completed()
                                        self.camera.send_trigger([self.navigationController.x_pos_mm, self.navigationController.y_pos_mm])
                                    elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                                        self.microcontroller.send_hardware_trigger(control_illumination=True, illumination_on_time_us=self.camera.exposure_time*1000)
                                    # read camera frame
                                    old_pixel_format = self.camera.pixel_format
                                    if config.pixel_format is not None:
                                        if config.pixel_format != "" and config.pixel_format.lower() != "default":
                                            self.camera.set_pixel_format(config.pixel_format)
                                    
                                    image = self.camera.read_frame()
                                    

                                    if config.pixel_format is not None:
                                        if config.pixel_format != "" and config.pixel_format.lower() != "default":
                                            self.camera.set_pixel_format(old_pixel_format)
                                    if image is None:
                                        print('self.camera.read_frame() returned None')
                                        continue
                                    # tunr of the illumination if using software trigger
                                    if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                        self.liveController.turn_off_illumination()
                                    # process the image -  @@@ to move to camera
                                    image = utils.crop_image(image,self.crop_width,self.crop_height)
                                    image = utils.rotate_and_flip_image(image,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)
                                    image_to_display = utils.crop_image(image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling))
                                    stitcher_tile_path = None
                                    stitcher_of_interest = None
                                    stitcher_key = str(config.name)+"_Z_"+str(k)
                                    stitcher_tiled_file_path = os.path.join(current_path, "stitch_input_"+str(config.name).replace(' ','_')+"_Z_"+str(k)+'.tiff') 
                                    stitcher_stitched_file_path = os.path.join(current_path,"stitch_output_"+str(config.name).replace(' ','_')+"_Z_"+str(k)+'.ome.tiff')
                                    stitcher_default_options = {'align_channel':0,'maximum_shift':int(min(self.crop_width,self.crop_height)*0.05),'filter_sigma':1,'stdout':subprocess.STDOUT} # add to UI later
                                    if image.dtype == np.uint16:
                                        saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.tiff')
                                        if self.camera.is_color:
                                            if 'BF LED matrix' in config.name:
                                                if MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
                                                    image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                                elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
                                                    image = image[:,:,1]
                                        iio.imwrite(saving_path,image)
                                        stitcher_tile_path = saving_path
                                    else:
                                        saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.' + Acquisition.IMAGE_FORMAT)
                                        if self.camera.is_color:
                                            if 'BF LED matrix' in config.name:
                                                if MULTIPOINT_BF_SAVING_OPTION == 'Raw':
                                                    image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                                                elif MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
                                                    image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                                elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
                                                    image = image[:,:,1]
                                            else:
                                                image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                                        cv2.imwrite(saving_path,image)
                                        stitcher_tile_path = saving_path
                                    if self.multiPointController.do_stitch_tiles:
                                        try:
                                            stitcher_of_interest = self.multiPointController.tile_stitchers[stitcher_key]
                                        except:
                                            self.multiPointController.tile_stitchers[stitcher_key] = Stitcher(stitcher_tiled_file_path, stitcher_stitched_file_path, stitcher_default_options, auto_run_ashlar=True, image_reader = self.multiPointController.stitcher_image_reader)
                                            stitcher_of_interest = self.multiPointController.tile_stitchers[stitcher_key]
                                            stitcher_of_interest.start_ometiff_writer()
                                        tile_metadata = {
                                                'Pixels': {
                                                    'PhysicalSizeX': 1, # need to get microscope info for actual values for these, if they are necessary
                                                    'PhysicalSizeXUnit': 'μm',
                                                    'PhysicalSizeY': 1,
                                                    'PhysicalSizeYUnit': 'μm',
                                                    },
                                                'Plane': {
                                                    'PositionX':int((j if self.x_scan_direction==1 else self.NX-1-j)*self.crop_width),
                                                    'PositionY':int(i*self.crop_height)
                                                    }
                                                }
                                        stitcher_of_interest.add_tile(stitcher_tile_path, tile_metadata)
                                    

                                    current_round_images[config.name] = np.copy(image)

                                else:
                                    if self.usb_spectrometer != None:
                                        for l in range(N_SPECTRUM_PER_POINT):
                                            data = self.usb_spectrometer.read_spectrum()
                                            saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '_' + str(l) + '.csv')
                                            np.savetxt(saving_path,data,delimiter=',')
                                
                                
                                if config.z_offset is not None: # undo Z offset
                                                                # assume z_offset is in um
                                    if config.z_offset != 0.0:
                                        print("Moving back from Z offset "+str(config.z_offset))
                                        self.navigationController.move_z(-config.z_offset/1000)
                                        self.wait_till_operation_is_completed()
                                        time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

                                                            
                            # add the coordinate of the current location
                            new_row = pd.DataFrame({'i':[i],'j':[j if self.x_scan_direction==1 else self.NX-1-j],'k':[k],
                                                    'x (mm)':[self.navigationController.x_pos_mm],
                                                    'y (mm)':[self.navigationController.y_pos_mm],
                                                    'z (um)':[self.navigationController.z_pos_mm*1000]},
                                                    )
                            self.coordinates_pd = pd.concat([self.coordinates_pd, new_row], ignore_index=True)


                            # check if the acquisition should be aborted
                            if self.multiPointController.abort_acqusition_requested:
                                self.liveController.turn_off_illumination()
                                self.navigationController.move_x_usteps(-self.dx_usteps)
                                self.wait_till_operation_is_completed()
                                self.navigationController.move_y_usteps(-self.dy_usteps)
                                self.wait_till_operation_is_completed()
                                _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                                self.navigationController.move_z_usteps(-self.dz_usteps-_usteps_to_clear_backlash)
                                self.wait_till_operation_is_completed()
                                self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                                self.wait_till_operation_is_completed()
                                self.coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
                                self.navigationController.enable_joystick_button_action = True
                                return

                            if self.NZ > 1:
                                # move z
                                if k < self.NZ - 1:
                                    self.navigationController.move_z_usteps(self.deltaZ_usteps)
                                    self.wait_till_operation_is_completed()
                                    time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
                                    self.dz_usteps = self.dz_usteps + self.deltaZ_usteps

                        if self.NZ > 1:
                            # move z back
                            if Z_STACKING_CONFIG == 'FROM CENTER':
                                _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                                self.navigationController.move_z_usteps( -self.deltaZ_usteps*(self.NZ-1) + self.deltaZ_usteps*round((self.NZ-1)/2) - _usteps_to_clear_backlash)
                                self.wait_till_operation_is_completed()
                                self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                                self.wait_till_operation_is_completed()
                                self.dz_usteps = self.dz_usteps - self.deltaZ_usteps*(self.NZ-1) + self.deltaZ_usteps*round((self.NZ-1)/2)
                            else:
                                self.navigationController.move_z_usteps(-self.deltaZ_usteps*(self.NZ-1) - _usteps_to_clear_backlash)
                                self.wait_till_operation_is_completed()
                                self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                                self.wait_till_operation_is_completed()
                                self.dz_usteps = self.dz_usteps - self.deltaZ_usteps*(self.NZ-1)

                        # update FOV counter
                        self.FOV_counter = self.FOV_counter + 1

                    if self.NX > 1:
                        # move x
                        if j < self.NX - 1:
                            self.navigationController.move_x_usteps(self.x_scan_direction*self.deltaX_usteps)
                            self.wait_till_operation_is_completed()
                            time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)
                            self.dx_usteps = self.dx_usteps + self.x_scan_direction*self.deltaX_usteps

                # finished X scan
                '''
                # instead of move back, reverse scan direction (12/29/2021)
                if self.NX > 1:
                    # move x back
                    self.navigationController.move_x_usteps(-self.deltaX_usteps*(self.NX-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)
                '''
                self.x_scan_direction = -self.x_scan_direction

                if self.NY > 1:
                    # move y
                    if i < self.NY - 1:
                        self.navigationController.move_y_usteps(self.deltaY_usteps)
                        self.wait_till_operation_is_completed()
                        time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
                        self.dy_usteps = self.dy_usteps + self.deltaY_usteps

            # finished XY scan
            if n_regions == 1:
                # only move to the start position if there's only one region in the scan
                if self.NY > 1:
                    # move y back
                    self.navigationController.move_y_usteps(-self.deltaY_usteps*(self.NY-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
                    self.dy_usteps = self.dy_usteps - self.deltaY_usteps*(self.NY-1)

                # move x back at the end of the scan
                if self.x_scan_direction == -1:
                    self.navigationController.move_x_usteps(-self.deltaX_usteps*(self.NX-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)

                # move z back
                _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                self.navigationController.microcontroller.move_z_to_usteps(z_pos - STAGE_MOVEMENT_SIGN_Z*_usteps_to_clear_backlash)
                self.wait_till_operation_is_completed()
                self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                self.wait_till_operation_is_completed()

        # finished region scan
        self.coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
        self.navigationController.enable_joystick_button_action = True
        print(time.time())
        print(time.time()-start)
    


class MultiPointController():

    def __init__(self,camera,navigationController,liveController,autofocusController,configurationManager,usb_spectrometer=None,scanCoordinates=None,parent=None, stitcher_image_reader =default_image_reader):
        
        self.camera = camera
        self.stitcher_image_reader = stitcher_image_reader
        self.tile_stitchers = {}
        #self.processingHandler = ProcessingHandler()
        self.microcontroller = navigationController.microcontroller # to move to gui for transparency
        self.navigationController = navigationController
        self.liveController = liveController
        self.autofocusController = autofocusController
        self.configurationManager = configurationManager
        self.NX = 1
        self.NY = 1
        self.NZ = 1
        self.Nt = 1
        mm_per_ustep_X = SCREW_PITCH_X_MM/(self.navigationController.x_microstepping*FULLSTEPS_PER_REV_X)
        mm_per_ustep_Y = SCREW_PITCH_Y_MM/(self.navigationController.y_microstepping*FULLSTEPS_PER_REV_Y)
        mm_per_ustep_Z = SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        self.deltaX = Acquisition.DX
        self.deltaX_usteps = round(self.deltaX/mm_per_ustep_X)
        self.deltaY = Acquisition.DY
        self.deltaY_usteps = round(self.deltaY/mm_per_ustep_Y)
        self.deltaZ = Acquisition.DZ/1000
        self.deltaZ_usteps = round(self.deltaZ/mm_per_ustep_Z)
        self.deltat = 0
        self.do_autofocus = False
        self.do_reflection_af = False
        self.do_stitch_tiles = False
        self.crop_width = Acquisition.CROP_WIDTH
        self.crop_height = Acquisition.CROP_HEIGHT
        self.display_resolution_scaling = Acquisition.IMAGE_DISPLAY_SCALING_FACTOR
        self.counter = 0
        self.experiment_ID = None
        self.base_path = None
        self.selected_configurations = []
        self.usb_spectrometer = usb_spectrometer
        self.scanCoordinates = scanCoordinates
        self.parent = parent

        self.old_images_per_page = 1
        try:
            if self.parent is not None:
                self.old_images_per_page = self.parent.dataHandler.n_images_per_page
        except:
            pass
        self.location_list = None # for flexible multipoint

    def set_NX(self,N):
        self.NX = N
    def set_NY(self,N):
        self.NY = N
    def set_NZ(self,N):
        self.NZ = N
    def set_Nt(self,N):
        self.Nt = N
    def set_deltaX(self,delta):
        mm_per_ustep_X = SCREW_PITCH_X_MM/(self.navigationController.x_microstepping*FULLSTEPS_PER_REV_X)
        self.deltaX = delta
        self.deltaX_usteps = round(delta/mm_per_ustep_X)
    def set_deltaY(self,delta):
        mm_per_ustep_Y = SCREW_PITCH_Y_MM/(self.navigationController.y_microstepping*FULLSTEPS_PER_REV_Y)
        self.deltaY = delta
        self.deltaY_usteps = round(delta/mm_per_ustep_Y)
    def set_deltaZ(self,delta_um):
        mm_per_ustep_Z = SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        self.deltaZ = delta_um/1000
        self.deltaZ_usteps = round((delta_um/1000)/mm_per_ustep_Z)
    def set_deltat(self,delta):
        self.deltat = delta
    def set_af_flag(self,flag):
        self.do_autofocus = flag
    def set_reflection_af_flag(self,flag):
        self.do_reflection_af = flag
    def set_crop(self,crop_width,crop_height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def set_base_path(self,path):
        self.base_path = path
    
    def get_location_list(self, well_plate_type='test'):
        # Initialize parameters, default values are for 96-well plate
        # Initialize an empty list to store positions
        if well_plate_type =='test':
            start_x,start_y,start_z,distance,rows,cols = 22,18,0.3,2,2,1
        elif well_plate_type == '12':
            start_x,start_y,start_z,distance,rows,cols = 22,18,4.3,26,3,4
        elif well_plate_type == '24':
            #start_x,start_y,start_z,distance,rows,cols = 22,18,4.3,26,4,6
            # @@@ to do: add 24 well plate
            print("Error: '24' well plate type is not supported.")
            sys.exit(1)
        else:
            # Handle other unsupported well plate types
            print(f"Error: '{well_plate_type}' well plate type is not supported.")
            sys.exit(1)


        location_list = np.empty((0, 3), dtype=float)
        # Generate the positions
        for row in range(rows):
            for col in range(cols):
                x = start_x + col * distance
                y = start_y + row * distance
                # Assuming a default z-axis value, for example, 0
                z = start_z
                location_list = np.append(location_list, [[x, y, z]], axis=0)
        return location_list




    def start_new_experiment(self,experiment_ID): # @@@ to do: change name to prepare_folder_for_new_experiment
        # generate unique experiment ID
        self.experiment_ID = experiment_ID.replace(' ','_') + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.recording_start_time = time.time()
        # create a new folder
        os.mkdir(os.path.join(self.base_path,self.experiment_ID))
        configManagerThrowaway = ConfigurationManager(self.configurationManager.config_filename)
        configManagerThrowaway.write_configuration_selected(self.selected_configurations,os.path.join(self.base_path,self.experiment_ID)+"/configurations.xml") # save the configuration for the experiment
        acquisition_parameters = {'dx(mm)':self.deltaX, 'Nx':self.NX, 'dy(mm)':self.deltaY, 'Ny':self.NY, 'dz(um)':self.deltaZ*1000,'Nz':self.NZ,'dt(s)':self.deltat,'Nt':self.Nt,'with AF':self.do_autofocus,'with reflection AF':self.do_reflection_af}
        try: # write objective data if it is available
            current_objective = self.parent.objectiveStore.current_objective
            objective_info = self.parent.objectiveStore.objectives_dict.get(current_objective, {})
            acquisition_parameters['objective'] = {}
            for k in objective_info.keys():
                acquisition_parameters['objective'][k]=objective_info[k]
            acquisition_parameters['objective']['name']=current_objective
        except:
            pass
        f = open(os.path.join(self.base_path,self.experiment_ID)+"/acquisition parameters.json","w")
        f.write(json.dumps(acquisition_parameters))
        f.close()


    def set_selected_configurations(self, selected_configurations_name):
        self.selected_configurations = []
        for configuration_name in selected_configurations_name:
            self.selected_configurations.append(next((config for config in self.configurationManager.configurations if config.name == configuration_name)))
        
    def run_acquisition_reef(self, location_list=None,scanCoordinates=None): 
        print('start acuisition')
        self.tile_stitchers = {}
        print(str(self.Nt) + '_' + str(self.NX) + '_' + str(self.NY) + '_' + str(self.NZ))
        if location_list is not None:
            self.location_list = location_list
        else:
            self.location_list = None
        
        if scanCoordinates is None:
            self.scanCoordinates = None

        self.abort_acqusition_requested = False

        

        self.configuration_before_running_multipoint = self.liveController.currentConfiguration
        # stop live
        if self.liveController.is_live:
            self.liveController_was_live_before_multipoint = True
            self.liveController.stop_live() # @@@ to do: also uncheck the live button
        else:
            self.liveController_was_live_before_multipoint = False

        # disable callback
        if self.camera.callback_is_enabled:
            self.camera_callback_was_enabled_before_multipoint = True
            self.camera.disable_callback()
        else:
            self.camera_callback_was_enabled_before_multipoint = False

        if self.usb_spectrometer != None:
            if self.usb_spectrometer.streaming_started == True and self.usb_spectrometer.streaming_paused == False:
                self.usb_spectrometer.pause_streaming()
                self.usb_spectrometer_was_streaming = True
            else:
                self.usb_spectrometer_was_streaming = False

        if self.parent is not None:
            try:
                self.parent.imageDisplayTabs.setCurrentWidget(self.parent.imageArrayDisplayWindow.widget)
            except:
                pass
            try:
                self.parent.recordTabWidget.setCurrentWidget(self.parent.statsDisplayWidget)
            except:
                pass
        # run the acquisition
        self.timestamp_acquisition_started = time.time()
        # create a worker object
        #self.processingHandler.start_processing()
        #self.processingHandler.start_uploading()
        self.multiPointWorker = MultiPointWorker(self)
        worker_thread = threading.Thread(target=self.multiPointWorker.run)
        # Start the thread
        worker_thread.start()
        worker_thread.join()

    def _on_acquisition_completed(self):
        # restore the previous selected mode
        if self.do_stitch_tiles:
            for k in self.tile_stitchers.keys():
                self.tile_stitchers[k].all_tiles_added()
        

        # re-enable callback
        if self.camera_callback_was_enabled_before_multipoint:
            self.camera.enable_callback()
            self.camera_callback_was_enabled_before_multipoint = False
        
        # re-enable live if it's previously on
        if self.liveController_was_live_before_multipoint:
            self.liveController.start_live()

        if self.usb_spectrometer != None:
            if self.usb_spectrometer_was_streaming:
                self.usb_spectrometer.resume_streaming()
        
        # emit the acquisition finished signal to enable the UI
        #self.processingHandler.end_processing()
        if self.parent is not None:
            try:
                self.parent.dataHandler.set_number_of_images_per_page(self.old_images_per_page)
                self.parent.dataHandler.sort('Sort by prediction score')
            except:
                pass

    def request_abort_aquisition(self):
        self.abort_acqusition_requested = True

class PlateReaderNavigationController():

    def __init__(self,microcontroller):
        self.microcontroller = microcontroller
        self.x_pos_mm = 0
        self.y_pos_mm = 0
        self.z_pos_mm = 0
        self.z_pos = 0
        self.x_microstepping = MICROSTEPPING_DEFAULT_X
        self.y_microstepping = MICROSTEPPING_DEFAULT_Y
        self.z_microstepping = MICROSTEPPING_DEFAULT_Z
        self.column = ''
        self.row = ''

        # to be moved to gui for transparency
        self.microcontroller.set_callback(self.update_pos)

        self.is_homing = False
        self.is_scanning = False

    def move_x_usteps(self,usteps):
        self.microcontroller.move_x_usteps(usteps)

    def move_y_usteps(self,usteps):
        self.microcontroller.move_y_usteps(usteps)

    def move_z_usteps(self,usteps):
        self.microcontroller.move_z_usteps(usteps)

    def move_x_to_usteps(self,usteps):
        self.microcontroller.move_x_to_usteps(usteps)

    def move_y_to_usteps(self,usteps):
        self.microcontroller.move_y_to_usteps(usteps)

    def move_z_to_usteps(self,usteps):
        self.microcontroller.move_z_to_usteps(usteps)

    def moveto(self,column,row):
        if column != '':
            mm_per_ustep_X = SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X)
            x_mm = PLATE_READER.OFFSET_COLUMN_1_MM + (int(column)-1)*PLATE_READER.COLUMN_SPACING_MM
            x_usteps = STAGE_MOVEMENT_SIGN_X*round(x_mm/mm_per_ustep_X)
            self.move_x_to_usteps(x_usteps)
        if row != '':
            mm_per_ustep_Y = SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y)
            y_mm = PLATE_READER.OFFSET_ROW_A_MM + (ord(row) - ord('A'))*PLATE_READER.ROW_SPACING_MM
            y_usteps = STAGE_MOVEMENT_SIGN_Y*round(y_mm/mm_per_ustep_Y)
            self.move_y_to_usteps(y_usteps)

    def moveto_row(self,row):
        # row: int, starting from 0
        mm_per_ustep_Y = SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y)
        y_mm = PLATE_READER.OFFSET_ROW_A_MM + row*PLATE_READER.ROW_SPACING_MM
        y_usteps = round(y_mm/mm_per_ustep_Y)
        self.move_y_to_usteps(y_usteps)

    def moveto_column(self,column):
        # column: int, starting from 0
        mm_per_ustep_X = SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X)
        x_mm = PLATE_READER.OFFSET_COLUMN_1_MM + column*PLATE_READER.COLUMN_SPACING_MM
        x_usteps = round(x_mm/mm_per_ustep_X)
        self.move_x_to_usteps(x_usteps)

    def update_pos(self,microcontroller):
        # get position from the microcontroller
        x_pos, y_pos, z_pos, theta_pos = microcontroller.get_pos()
        self.z_pos = z_pos
        # calculate position in mm or rad
        if USE_ENCODER_X:
            self.x_pos_mm = x_pos*STAGE_POS_SIGN_X*ENCODER_STEP_SIZE_X_MM
        else:
            self.x_pos_mm = x_pos*STAGE_POS_SIGN_X*(SCREW_PITCH_X_MM/(self.x_microstepping*FULLSTEPS_PER_REV_X))
        if USE_ENCODER_Y:
            self.y_pos_mm = y_pos*STAGE_POS_SIGN_Y*ENCODER_STEP_SIZE_Y_MM
        else:
            self.y_pos_mm = y_pos*STAGE_POS_SIGN_Y*(SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y))
        if USE_ENCODER_Z:
            self.z_pos_mm = z_pos*STAGE_POS_SIGN_Z*ENCODER_STEP_SIZE_Z_MM
        else:
            self.z_pos_mm = z_pos*STAGE_POS_SIGN_Z*(SCREW_PITCH_Z_MM/(self.z_microstepping*FULLSTEPS_PER_REV_Z))
        # check homing status
        # if self.is_homing and self.microcontroller.mcu_cmd_execution_in_progress == False:
        #     self.signal_homing_complete.emit()
        # for debugging
        # print('X: ' + str(self.x_pos_mm) + ' Y: ' + str(self.y_pos_mm))
        # check and emit current position
        column = round((self.x_pos_mm - PLATE_READER.OFFSET_COLUMN_1_MM)/PLATE_READER.COLUMN_SPACING_MM)
        if column >= 0 and column <= PLATE_READER.NUMBER_OF_COLUMNS:
            column = str(column+1)
        else:
            column = ' '
        row = round((self.y_pos_mm - PLATE_READER.OFFSET_ROW_A_MM)/PLATE_READER.ROW_SPACING_MM)
        if row >= 0 and row <= PLATE_READER.NUMBER_OF_ROWS:
            row = chr(ord('A')+row)
        else:
            row = ' '

 

    def home(self):
        self.is_homing = True
        self.microcontroller.home_xy()

    def home_x(self):
        self.microcontroller.home_x()

    def home_y(self):
        self.microcontroller.home_y()

class ScanCoordinates(object):
    def __init__(self):
        self.coordinates_mm = []
        self.name = []
        self.well_selector = None

    def add_well_selector(self,well_selector):
        self.well_selector = well_selector

    def get_selected_wells(self):
        # get selected wells from the widget
        selected_wells = self.well_selector.get_selected_cells()
        selected_wells = np.array(selected_wells)
        # clear the previous selection
        self.coordinates_mm = []
        self.name = []
        # populate the coordinates
        rows = np.unique(selected_wells[:,0])
        _increasing = True
        for row in rows:
            items = selected_wells[selected_wells[:,0]==row]
            columns = items[:,1]
            columns = np.sort(columns)
            if _increasing==False:
                columns = np.flip(columns)
            for column in columns:
                x_mm = X_MM_384_WELLPLATE_UPPERLEFT + WELL_SIZE_MM_384_WELLPLATE/2 - (A1_X_MM_384_WELLPLATE+WELL_SPACING_MM_384_WELLPLATE*NUMBER_OF_SKIP_384) + column*WELL_SPACING_MM + A1_X_MM + WELLPLATE_OFFSET_X_mm
                y_mm = Y_MM_384_WELLPLATE_UPPERLEFT + WELL_SIZE_MM_384_WELLPLATE/2 - (A1_Y_MM_384_WELLPLATE+WELL_SPACING_MM_384_WELLPLATE*NUMBER_OF_SKIP_384) + row*WELL_SPACING_MM + A1_Y_MM + WELLPLATE_OFFSET_Y_mm
                self.coordinates_mm.append((x_mm,y_mm))
                self.name.append(chr(ord('A')+row)+str(column+1))
            _increasing = not _increasing


class LaserAutofocusController():



    def __init__(self,microcontroller,camera,liveController,navigationController,has_two_interfaces=True,use_glass_top=True, look_for_cache=True):
        self.microcontroller = microcontroller
        self.camera = camera
        self.liveController = liveController
        self.navigationController = navigationController

        self.is_initialized = False
        self.x_reference = 0
        self.pixel_to_um = 1
        self.x_offset = 0
        self.y_offset = 0
        self.x_width = 3088
        self.y_width = 2064

        self.has_two_interfaces = has_two_interfaces # e.g. air-glass and glass water, set to false when (1) using oil immersion (2) using 1 mm thick slide (3) using metal coated slide or Si wafer
        self.use_glass_top = use_glass_top
        self.spot_spacing_pixels = None # spacing between the spots from the two interfaces (unit: pixel)
        
        self.look_for_cache = look_for_cache
        
        
        if look_for_cache:
            # Directory of the current script (core_reef.py)
            current_script_dir = os.path.dirname(os.path.abspath(__file__))

            # Path to the laser_af_reference_plane.txt in the same directory
            laser_chche_path = os.path.join(current_script_dir, 'laser_af_reference_plane.txt')

            try:
                with open(laser_chche_path, "r") as cache_file:
                    for line in cache_file:
                        value_list = line.split(",")
                        x_offset = float(value_list[0])
                        y_offset = float(value_list[1])
                        width = int(value_list[2])
                        height = int(value_list[3])
                        pixel_to_um = float(value_list[4])
                        x_reference = float(value_list[5])
                        self.initialize_manual(x_offset,y_offset,width,height,pixel_to_um,x_reference)
                        break
            except (FileNotFoundError, ValueError,IndexError) as e:
                print("Unable to read laser AF state cache, exception below:")
                print(e)
                pass

    def initialize_manual(self, x_offset, y_offset, width, height, pixel_to_um, x_reference, write_to_cache=True):
        cache_string = ",".join([str(x_offset),str(y_offset), str(width),str(height), str(pixel_to_um), str(x_reference)])
        if write_to_cache:
            # Directory of the current script (core_reef.py)
            current_script_dir = os.path.dirname(os.path.abspath(__file__))
            # Path to the laser_af_reference_plane.txt in the same directory
            laser_chche_path = os.path.join(current_script_dir, 'laser_af_reference_plane.txt')
            laser_chche_path = Path(laser_chche_path)
            laser_chche_path.write_text(cache_string)
        # x_reference is relative to the full sensor
        self.pixel_to_um = pixel_to_um
        self.x_offset = int((x_offset//8)*8)
        self.y_offset = int((y_offset//2)*2)
        self.width = int((width//8)*8)
        self.height = int((height//2)*2)
        self.x_reference = x_reference - self.x_offset # self.x_reference is relative to the cropped region
        self.camera.set_ROI(self.x_offset,self.y_offset,self.width,self.height)
        self.is_initialized = True

    def initialize_auto(self):

        # first find the region to crop
        # then calculate the convert factor

        # set camera to use full sensor
        self.camera.set_ROI(0,0,None,None) # set offset first
        self.camera.set_ROI(0,0,3088,2064)
        # update camera settings
        self.camera.set_exposure_time(FOCUS_CAMERA_EXPOSURE_TIME_MS)
        self.camera.set_analog_gain(FOCUS_CAMERA_ANALOG_GAIN)
        
        # turn on the laser
        self.microcontroller.turn_on_AF_laser()
        self.wait_till_operation_is_completed()

        # get laser spot location
        x,y = self._get_laser_spot_centroid()

        # turn off the laser
        self.microcontroller.turn_off_AF_laser()
        self.wait_till_operation_is_completed()

        x_offset = x - LASER_AF_CROP_WIDTH/2
        y_offset = y - LASER_AF_CROP_HEIGHT/2
        print('laser spot location on the full sensor is (' + str(int(x)) + ',' + str(int(y)) + ')')

        # set camera crop
        self.initialize_manual(x_offset, y_offset, LASER_AF_CROP_WIDTH, LASER_AF_CROP_HEIGHT, 1, x)

        # turn on laser 
        self.microcontroller.turn_on_AF_laser()
        self.wait_till_operation_is_completed()

        # move z to - 6 um
        self.navigationController.move_z(-0.018)
        self.wait_till_operation_is_completed()
        self.navigationController.move_z(0.012)
        self.wait_till_operation_is_completed()
        time.sleep(0.02)

        # measure
        x0,y0 = self._get_laser_spot_centroid()

        # move z to 6 um
        self.navigationController.move_z(0.006)
        self.wait_till_operation_is_completed()
        time.sleep(0.02)

        # measure
        x1,y1 = self._get_laser_spot_centroid()

        # turn off laser
        self.microcontroller.turn_off_AF_laser()
        self.wait_till_operation_is_completed()

        # calculate the conversion factor
        self.pixel_to_um = 6.0/(x1-x0)
        print('pixel to um conversion factor is ' + str(self.pixel_to_um) + ' um/pixel')
        # for simulation
        if x1-x0 == 0:
            self.pixel_to_um = 0.4

        # set reference
        self.x_reference = x1

        if self.look_for_cache:
            cache_path =self.rootpath + "cache\\laser_af_reference_plane.txt"
            try:
                x_offset = None
                y_offset = None
                width = None
                height = None
                pixel_to_um = None
                x_reference = None
                with open(cache_path, "r") as cache_file:
                    for line in cache_file:
                        value_list = line.split(",")
                        x_offset = float(value_list[0])
                        y_offset = float(value_list[1])
                        width = int(value_list[2])
                        height = int(value_list[3])
                        pixel_to_um = self.pixel_to_um
                        x_reference = self.x_reference+self.x_offset
                        break
                cache_string = ",".join([str(x_offset),str(y_offset), str(width),str(height), str(pixel_to_um), str(x_reference)])
                cache_path = Path(self.rootpath+ "cache\\laser_af_reference_plane.txt")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(cache_string)
            except (FileNotFoundError, ValueError,IndexError) as e:
                print("Unable to read laser AF state cache, exception below:")
                print(e)
                pass


    def measure_displacement(self):
        # turn on the laser
        self.microcontroller.turn_on_AF_laser()
        self.wait_till_operation_is_completed()
        # get laser spot location
        x,y = self._get_laser_spot_centroid()
        # turn off the laser
        self.microcontroller.turn_off_AF_laser()
        self.wait_till_operation_is_completed()
        # calculate displacement
        displacement_um = (x - self.x_reference)*self.pixel_to_um
        return displacement_um

    def move_to_target(self,target_um):
        current_displacement_um = self.measure_displacement()
        um_to_move = target_um - current_displacement_um
        # limit the range of movement
        um_to_move = min(um_to_move,200)
        um_to_move = max(um_to_move,-200)
        self.navigationController.move_z(um_to_move/1000)
        self.wait_till_operation_is_completed()
        # update the displacement measurement
        self.measure_displacement()

    def set_reference(self):
        # turn on the laser
        self.microcontroller.turn_on_AF_laser()
        self.wait_till_operation_is_completed()
        # get laser spot location
        x,y = self._get_laser_spot_centroid()
        # turn off the laser
        self.microcontroller.turn_off_AF_laser()
        self.wait_till_operation_is_completed()
        self.x_reference = x

    def _caculate_centroid(self,image):
        if self.has_two_interfaces == False:
            h,w = image.shape
            x,y = np.meshgrid(range(w),range(h))
            I = image.astype(float)
            I = I - np.amin(I)
            I[I/np.amax(I)<0.2] = 0
            x = np.sum(x*I)/np.sum(I)
            y = np.sum(y*I)/np.sum(I)
            return x,y
        else:
            I = image
            # get the y position of the spots
            tmp = np.sum(I,axis=1)
            y0 = np.argmax(tmp)
            # crop along the y axis
            I = I[y0-96:y0+96,:]
            # signal along x
            tmp = np.sum(I,axis=0)
            # find peaks
            peak_locations,_ = scipy.signal.find_peaks(tmp,distance=100)
            idx = np.argsort(tmp[peak_locations])
            peak_0_location = peak_locations[idx[-1]]
            peak_1_location = peak_locations[idx[-2]] # for air-glass-water, the smaller peak corresponds to the glass-water interface
            self.spot_spacing_pixels = peak_1_location-peak_0_location
            '''
            # find peaks - alternative
            if self.spot_spacing_pixels is not None:
                peak_locations,_ = scipy.signal.find_peaks(tmp,distance=100)
                idx = np.argsort(tmp[peak_locations])
                peak_0_location = peak_locations[idx[-1]]
                peak_1_location = peak_locations[idx[-2]] # for air-glass-water, the smaller peak corresponds to the glass-water interface
                self.spot_spacing_pixels = peak_1_location-peak_0_location
            else:
                peak_0_location = np.argmax(tmp)
                peak_1_location = peak_0_location + self.spot_spacing_pixels
            '''
            # choose which surface to use
            if self.use_glass_top:
                x1 = peak_1_location
            else:
                x1 = peak_0_location
            # find centroid
            h,w = I.shape
            x,y = np.meshgrid(range(w),range(h))
            I = I[:,max(0,x1-64):min(w-1,x1+64)]
            x = x[:,max(0,x1-64):min(w-1,x1+64)]
            y = y[:,max(0,x1-64):min(w-1,x1+64)]
            I = I.astype(float)
            I = I - np.amin(I)
            I[I/np.amax(I)<0.1] = 0
            x1 = np.sum(x*I)/np.sum(I)
            y1 = np.sum(y*I)/np.sum(I)
            return x1,y0-96+y1

    def _get_laser_spot_centroid(self):
        # disable camera callback
        self.camera.disable_callback()
        tmp_x = 0
        tmp_y = 0
        for i in range(LASER_AF_AVERAGING_N):
            # send camera trigger
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:            
                self.camera.send_trigger()
            elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                # self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
                pass # to edit
            # read camera frame
            image = self.camera.read_frame()
            
            # calculate centroid
            x,y = self._caculate_centroid(image)
            tmp_x = tmp_x + x
            tmp_y = tmp_y + y
        x = tmp_x/LASER_AF_AVERAGING_N
        y = tmp_y/LASER_AF_AVERAGING_N
        return x,y

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)
        
class ConfigurationManager():
    def __init__(self,filename="squid_control/channel_configurations.xml"):
        self.config_filename = filename
        self.configurations = []
        self.read_configurations()
        
    def save_configurations(self):
        self.write_configuration(self.config_filename)

    def write_configuration(self,filename):
        self.config_xml_tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)

    def read_configurations(self):
        if(os.path.isfile(self.config_filename)==False):
            utils_config.generate_default_configuration(self.config_filename)
        self.config_xml_tree = ET.parse(self.config_filename)
        self.config_xml_tree_root = self.config_xml_tree.getroot()
        self.num_configurations = 0
        for mode in self.config_xml_tree_root.iter('mode'):
            self.num_configurations = self.num_configurations + 1
            self.configurations.append(
                Configuration(
                    mode_id = mode.get('ID'),
                    name = mode.get('Name'),
                    exposure_time = float(mode.get('ExposureTime')),
                    analog_gain = float(mode.get('AnalogGain')),
                    illumination_source = int(mode.get('IlluminationSource')),
                    illumination_intensity = float(mode.get('IlluminationIntensity')),
                    camera_sn = mode.get('CameraSN'),
                    z_offset = float(mode.get('ZOffset')),
                    pixel_format = mode.get('PixelFormat'),
                    _pixel_format_options = mode.get('_PixelFormat_options')
                )
            )

    def update_configuration(self,configuration_id,attribute_name,new_value):
        conf_list = self.config_xml_tree_root.xpath("//mode[contains(@ID," + "'" + str(configuration_id) + "')]")
        mode_to_update = conf_list[0]
        mode_to_update.set(attribute_name,str(new_value))
        self.save_configurations()

    def update_configuration_without_writing(self, configuration_id, attribute_name, new_value):
        conf_list = self.config_xml_tree_root.xpath("//mode[contains(@ID," + "'" + str(configuration_id) + "')]")
        mode_to_update = conf_list[0]
        mode_to_update.set(attribute_name,str(new_value))

    def write_configuration_selected(self,selected_configurations,filename): # to be only used with a throwaway instance
                                                                             # of this class
        for conf in self.configurations:
            self.update_configuration_without_writing(conf.id, "Selected", 0)
        for conf in selected_configurations:
            self.update_configuration_without_writing(conf.id, "Selected", 1)
        self.write_configuration(filename)
        for conf in selected_configurations:
            self.update_configuration_without_writing(conf.id, "Selected", 0)
