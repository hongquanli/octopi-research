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

import math
import json
import pandas as pd

class StreamHandler(QObject):

    image_to_display = Signal(np.ndarray)
    packet_image_to_write = Signal(np.ndarray, int, float)
    packet_image_for_tracking = Signal(np.ndarray, int, float)
    signal_new_frame_received = Signal()

    def __init__(self,crop_width=Acquisition.CROP_WIDTH,crop_height=Acquisition.CROP_HEIGHT,display_resolution_scaling=1):
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

        # moved down (so that it does not modify the camera.current_frame, which causes minor problems for simulation) - 1/30/2022
        # # rotate and flip - eventually these should be done in the camera
        # camera.current_frame = utils.rotate_and_flip_image(camera.current_frame,rotate_image_angle=camera.rotate_image_angle,flip_image=camera.flip_image)

        # crop image
        image_cropped = utils.crop_image(camera.current_frame,self.crop_width,self.crop_height)
        image_cropped = np.squeeze(image_cropped)
        
        # # rotate and flip - moved up (1/10/2022)
        # image_cropped = utils.rotate_and_flip_image(image_cropped,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
        # added on 1/30/2022
        image_cropped = utils.rotate_and_flip_image(image_cropped,rotate_image_angle=camera.rotate_image_angle,flip_image=camera.flip_image)

        # send image to display
        time_now = time.time()
        if time_now-self.timestamp_last_display >= 1/self.fps_display:
            # self.image_to_display.emit(cv2.resize(image_cropped,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
            self.image_to_display.emit(utils.crop_image(image_cropped,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)))
            self.timestamp_last_display = time_now

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

class ImageSaver(QObject):

    stop_recording = Signal()

    def __init__(self,image_format='bmp'):
        QObject.__init__(self)
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
            if ( self.recording_time_limit>0 ) and ( time.time()-self.recording_start_time >= self.recording_time_limit ):
                self.stop_recording.emit()
            # when using self.queue.put(str_), program can be slowed down despite multithreading because of the block and the GIL
        except:
            print('imageSaver queue is full, image discarded')

    def set_base_path(self,path):
        self.base_path = path

    def set_recording_time_limit(self,time_limit):
        self.recording_time_limit = time_limit

    def start_new_experiment(self,experiment_ID):
        # generate unique experiment ID
        self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f')
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


class ImageSaver_Tracking(QObject):
    def __init__(self,base_path,image_format='bmp'):
        QObject.__init__(self)
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


'''
class ImageSaver_MultiPointAcquisition(QObject):
'''

class ImageDisplay(QObject):

    image_to_display = Signal(np.ndarray)

    def __init__(self):
        QObject.__init__(self)
        self.queue = Queue(10) # max 10 items in the queue
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
                [image,frame_ID,timestamp] = self.queue.get(timeout=0.1)
                self.image_lock.acquire(True)
                self.image_to_display.emit(image)
                self.image_lock.release()
                self.queue.task_done()
            except:
                pass

    # def enqueue(self,image,frame_ID,timestamp):
    def enqueue(self,image):
        try:
            self.queue.put_nowait([image,None,None])
            # when using self.queue.put(str_) instead of try + nowait, program can be slowed down despite multithreading because of the block and the GIL
            pass
        except:
            print('imageDisplay queue is full, image discarded')

    def emit_directly(self,image):
        self.image_to_display.emit(image)

    def close(self):
        self.queue.join()
        self.stop_signal_received = True
        self.thread.join()

class Configuration:
    def __init__(self,mode_id=None,name=None,camera_sn=None,exposure_time=None,analog_gain=None,illumination_source=None,illumination_intensity=None):
        self.id = mode_id
        self.name = name
        self.exposure_time = exposure_time
        self.analog_gain = analog_gain
        self.illumination_source = illumination_source
        self.illumination_intensity = illumination_intensity
        self.camera_sn = camera_sn

class LiveController(QObject):

    def __init__(self,camera,microcontroller,configurationManager,control_illumination=True):
        QObject.__init__(self)
        self.camera = camera
        self.microcontroller = microcontroller
        self.configurationManager = configurationManager
        self.currentConfiguration = None
        self.trigger_mode = TriggerMode.SOFTWARE # @@@ change to None
        self.is_live = False
        self.was_live_before_autofocus = False
        self.was_live_before_multipoint = False
        self.control_illumination = control_illumination
        self.illumination_on = False

        self.fps_trigger = 1;
        self.timer_trigger_interval = (1/self.fps_trigger)*1000

        self.timer_trigger = QTimer()
        self.timer_trigger.setInterval(self.timer_trigger_interval)
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
        self.camera.start_streaming()
        if self.trigger_mode == TriggerMode.SOFTWARE or self.trigger_mode == TriggerMode.HARDWARE:
            self._start_triggerred_acquisition()

    def stop_live(self):
        if self.is_live:
            self.is_live = False
            if self.trigger_mode == TriggerMode.SOFTWARE:
                self._stop_triggerred_acquisition()
            # self.camera.stop_streaming() # 20210113 this line seems to cause problems when using af with multipoint
            if self.trigger_mode == TriggerMode.CONTINUOUS:
            	self.camera.stop_streaming()
            if self.trigger_mode == TriggerMode.HARDWARE:
                self._stop_triggerred_acquisition()
            if self.control_illumination:
                self.turn_off_illumination()

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
        self.timer_trigger.setInterval(self.timer_trigger_interval)

    def _stop_triggerred_acquisition(self):
        self.timer_trigger.stop()

    # trigger mode and settings
    def set_trigger_mode(self,mode):
        if mode == TriggerMode.SOFTWARE:
            self.camera.set_software_triggered_acquisition()
            if self.is_live:
                self._start_triggerred_acquisition()
        if mode == TriggerMode.HARDWARE:
            if self.trigger_mode == TriggerMode.SOFTWARE:
                self._stop_triggerred_acquisition()
            # self.camera.reset_camera_acquisition_counter()
            self.camera.set_hardware_triggered_acquisition()
            self.microcontroller.set_strobe_delay_us(self.camera.strobe_delay_us)
        if mode == TriggerMode.CONTINUOUS: 
            if self.trigger_mode == TriggerMode.SOFTWARE:
                self._stop_triggerred_acquisition()
            self.camera.set_continuous_acquisition()
        self.trigger_mode = mode

    def set_trigger_fps(self,fps):
        if self.trigger_mode == TriggerMode.SOFTWARE or self.trigger_mode == TriggerMode.HARDWARE:
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

class NavigationController(QObject):

    xPos = Signal(float)
    yPos = Signal(float)
    zPos = Signal(float)
    thetaPos = Signal(float)
    xyPos = Signal(float,float)
    signal_joystick_button_pressed = Signal()

    def __init__(self,microcontroller):
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.x_pos_mm = 0
        self.y_pos_mm = 0
        self.z_pos_mm = 0
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

    def move_x_usteps(self,usteps):
        self.microcontroller.move_x_usteps(usteps)

    def move_y_usteps(self,usteps):
        self.microcontroller.move_y_usteps(usteps)

    def move_z_usteps(self,usteps):
        self.microcontroller.move_z_usteps(usteps)

    def update_pos(self,microcontroller):
        # get position from the microcontroller
        x_pos, y_pos, z_pos, theta_pos = microcontroller.get_pos()
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
        # emit the updated position
        self.xPos.emit(self.x_pos_mm)
        self.yPos.emit(self.y_pos_mm)
        self.zPos.emit(self.z_pos_mm*1000)
        self.thetaPos.emit(self.theta_pos_rad*360/(2*math.pi))
        self.xyPos.emit(self.x_pos_mm,self.y_pos_mm)

        if microcontroller.signal_joystick_button_pressed_event:
            if self.enable_joystick_button_action:
                self.signal_joystick_button_pressed.emit()
            print('joystick button pressed')
            microcontroller.signal_joystick_button_pressed_event = False

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
        

class SlidePositionControlWorker(QObject):
    
    finished = Signal()
    signal_stop_live = Signal()
    signal_resume_live = Signal()

    def __init__(self,slidePositionController,home_x_and_y_separately=False):
        QObject.__init__(self)
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
        if was_live:
            self.signal_stop_live.emit()
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
        if was_live:
            self.signal_resume_live.emit()
        self.slidePositionController.slide_loading_position_reached = True
        self.finished.emit()

    def move_to_slide_scanning_position(self):
        was_live = self.liveController.is_live
        if was_live:
            self.signal_stop_live.emit()
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
        if was_live:
            self.signal_resume_live.emit()
        self.slidePositionController.slide_scanning_position_reached = True
        self.finished.emit()

class SlidePositionController(QObject):

    signal_slide_loading_position_reached = Signal()
    signal_slide_scanning_position_reached = Signal()
    signal_clear_slide = Signal()

    def __init__(self,navigationController,liveController):
        QObject.__init__(self)
        self.navigationController = navigationController
        self.liveController = liveController
        self.slide_loading_position_reached = False
        self.slide_scanning_position_reached = False

    def move_to_slide_loading_position(self):
        # create a QThread object
        self.thread = QThread()
        # create a worker object
        self.slidePositionControlWorker = SlidePositionControlWorker(self)
        # move the worker to the thread
        self.slidePositionControlWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.slidePositionControlWorker.move_to_slide_loading_position)
        self.slidePositionControlWorker.signal_stop_live.connect(self.slot_stop_live,type=Qt.BlockingQueuedConnection)
        self.slidePositionControlWorker.signal_resume_live.connect(self.slot_resume_live,type=Qt.BlockingQueuedConnection)
        self.slidePositionControlWorker.finished.connect(self.signal_slide_loading_position_reached.emit)
        self.slidePositionControlWorker.finished.connect(self.slidePositionControlWorker.deleteLater)
        self.slidePositionControlWorker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.quit)
        # start the thread
        self.thread.start()

    def move_to_slide_scanning_position(self):
        # create a QThread object
        self.thread = QThread()
        # create a worker object
        self.slidePositionControlWorker = SlidePositionControlWorker(self)
        # move the worker to the thread
        self.slidePositionControlWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.slidePositionControlWorker.move_to_slide_scanning_position)
        self.slidePositionControlWorker.signal_stop_live.connect(self.slot_stop_live,type=Qt.BlockingQueuedConnection)
        self.slidePositionControlWorker.signal_resume_live.connect(self.slot_resume_live,type=Qt.BlockingQueuedConnection)
        self.slidePositionControlWorker.finished.connect(self.signal_slide_scanning_position_reached.emit)
        self.slidePositionControlWorker.finished.connect(self.slidePositionControlWorker.deleteLater)
        self.slidePositionControlWorker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.quit)
        # start the thread
        self.thread.start()
        self.signal_clear_slide.emit()

    def slot_stop_live(self):
        self.liveController.stop_live()

    def slot_resume_live(self):
        self.liveController.start_live()

class AutofocusWorker(QObject):

    finished = Signal()
    image_to_display = Signal(np.ndarray)
    # signal_current_configuration = Signal(Configuration)

    def __init__(self,autofocusController):
        QObject.__init__(self)
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
        self.finished.emit()

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)

    def run_autofocus(self):
        # @@@ to add: increase gain, decrease exposure time
        # @@@ can move the execution into a thread - done 08/21/2021
        focus_measure_vs_z = [0]*self.N
        focus_measure_max = 0

        z_af_offset_usteps = self.deltaZ_usteps*round(self.N/2)
        self.navigationController.move_z_usteps(-z_af_offset_usteps)
        self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        # can be moved to the firmware
        self.navigationController.move_z_usteps(-160)
        self.wait_till_operation_is_completed()
        self.navigationController.move_z_usteps(160)
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
            # tunr of the illumination if using software trigger
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                self.liveController.turn_off_illumination()
            image = utils.crop_image(image,self.crop_width,self.crop_height)
            self.image_to_display.emit(image)
            QApplication.processEvents()
            timestamp_0 = time.time()
            focus_measure = utils.calculate_focus_measure(image)
            timestamp_1 = time.time()
            print('             calculating focus measure took ' + str(timestamp_1-timestamp_0) + ' second')
            focus_measure_vs_z[i] = focus_measure
            print(i,focus_measure)
            focus_measure_max = max(focus_measure, focus_measure_max)
            if focus_measure < focus_measure_max*AF.STOP_THRESHOLD:
                break

        # move to the starting location
        self.navigationController.move_z_usteps(-steps_moved*self.deltaZ_usteps)
        self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        self.navigationController.move_z_usteps(-160)
        self.wait_till_operation_is_completed()
        self.navigationController.move_z_usteps(160)
        self.wait_till_operation_is_completed()

        # determine the in-focus position
        idx_in_focus = focus_measure_vs_z.index(max(focus_measure_vs_z))

        # move to the calculated in-focus position
        self.navigationController.move_z_usteps(idx_in_focus*self.deltaZ_usteps)
        self.wait_till_operation_is_completed()
        if idx_in_focus == 0:
            print('moved to the bottom end of the AF range')
        if idx_in_focus == self.N-1:
            print('moved to the top end of the AF range')

class AutoFocusController(QObject):

    z_pos = Signal(float)
    autofocusFinished = Signal()
    image_to_display = Signal(np.ndarray)

    def __init__(self,camera,navigationController,liveController):
        QObject.__init__(self)
        self.camera = camera
        self.navigationController = navigationController
        self.liveController = liveController
        self.N = None
        self.deltaZ = None
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

    def set_crop(self,crop_width,height):
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
            self.camera.stop_streaming()
            self.camera.disable_callback()
            self.camera.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
        else:
            self.callback_was_enabled_before_autofocus = False

        self.autofocus_in_progress = True

        # create a QThread object
        try:
            if self.thread.isRunning():
                print('*** autofocus thread is still running ***')
                self.thread.terminate()
                self.thread.wait()
                print('*** autofocus threaded manually stopped ***')
        except:
            pass
        self.thread = QThread()
        # create a worker object
        self.autofocusWorker = AutofocusWorker(self)
        # move the worker to the thread
        self.autofocusWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.autofocusWorker.run)
        self.autofocusWorker.finished.connect(self._on_autofocus_completed)
        self.autofocusWorker.finished.connect(self.autofocusWorker.deleteLater)
        self.autofocusWorker.finished.connect(self.thread.quit)
        self.autofocusWorker.image_to_display.connect(self.slot_image_to_display)
        # self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.thread.quit)
        # start the thread
        self.thread.start()
        
    def _on_autofocus_completed(self):
        # re-enable callback
        if self.callback_was_enabled_before_autofocus:
            self.camera.stop_streaming()
            self.camera.enable_callback()
            self.camera.start_streaming()
        
        # re-enable live if it's previously on
        if self.was_live_before_autofocus:
            self.liveController.start_live()

        # emit the autofocus finished signal to enable the UI
        self.autofocusFinished.emit()
        QApplication.processEvents()
        print('autofocus finished')

        # update the state
        self.autofocus_in_progress = False

    def slot_image_to_display(self,image):
        #self.image_to_display.emit(image)
        pass

    def wait_till_autofocus_has_completed(self):
        while self.autofocus_in_progress == True:
            time.sleep(0.005)
        print('autofocus wait has completed, exit wait')

class MultiPointWorker(QObject):

    finished = Signal()
    image_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    signal_current_configuration = Signal(Configuration)
    signal_register_current_fov = Signal(float,float)

    def __init__(self,multiPointController):
        QObject.__init__(self)
        self.multiPointController = multiPointController

        self.camera = self.multiPointController.camera
        self.microcontroller = self.multiPointController.microcontroller
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
        self.crop_width = self.multiPointController.crop_width
        self.crop_height = self.multiPointController.crop_height
        self.display_resolution_scaling = self.multiPointController.display_resolution_scaling
        self.counter = self.multiPointController.counter
        self.experiment_ID = self.multiPointController.experiment_ID
        self.base_path = self.multiPointController.base_path
        self.selected_configurations = self.multiPointController.selected_configurations

        self.timestamp_acquisition_started = self.multiPointController.timestamp_acquisition_started
        self.time_point = 0

    def run(self):
        while self.time_point < self.Nt:
            # continous acquisition
            if self.dt == 0:
                self.run_single_time_point()
                if self.multiPointController.abort_acqusition_requested:
                    break
                self.time_point = self.time_point + 1
            # timed acquisition
            else:
                self.run_single_time_point()
                if self.multiPointController.abort_acqusition_requested:
                    break
                self.time_point = self.time_point + 1
                # check if the aquisition has taken longer than dt or integer multiples of dt, if so skip the next time point(s)
                while time.time() > self.timestamp_acquisition_started + self.time_point*self.dt:
                    print('skip time point ' + str(self.time_point+1))
                    self.time_point = self.time_point+1
                if self.time_point == self.Nt:
                    break # no waiting after taking the last time point
                # wait until it's time to do the next acquisition
                while time.time() < self.timestamp_acquisition_started + self.time_point*self.dt:
                    time.sleep(0.05)
        self.finished.emit()

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)

    def run_single_time_point(self):

        # disable joystick button action
        self.navigationController.enable_joystick_button_action = False

        self.FOV_counter = 0
        print('multipoint acquisition - time point ' + str(self.time_point+1))
        
        # for each time point, create a new folder
        current_path = os.path.join(self.base_path,self.experiment_ID,str(self.time_point))
        os.mkdir(current_path)

        # create a dataframe to save coordinates
        coordinates_pd = pd.DataFrame(columns = ['i', 'j', 'k', 'x (mm)', 'y (mm)', 'z (um)'])

        x_scan_direction = 1
        dx_usteps = 0
        dy_usteps = 0
        dz_usteps = 0

        # along y
        for i in range(self.NY):

            self.FOV_counter = 0 # so that AF at the beginning of each new row

            # along x
            for j in range(self.NX):

                if (self.NZ > 1):
                    # maneuver for achiving uniform step size and repeatability when using open-loop control
                    self.navigationController.move_z_usteps(-160)
                    self.wait_till_operation_is_completed()
                    self.navigationController.move_z_usteps(160)
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

                # z-stack
                for k in range(self.NZ):

                    # perform AF only if when not taking z stack
                    if (self.NZ == 1) and (self.do_autofocus) and (self.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
                    # temporary: replace the above line with the line below to AF every FOV
                    # if (self.NZ == 1) and (self.do_autofocus):
                        configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                        config_AF = next((config for config in self.configurationManager.configurations if config.name == configuration_name_AF))
                        self.signal_current_configuration.emit(config_AF)
                        self.autofocusController.autofocus()
                        self.autofocusController.wait_till_autofocus_has_completed()

                    '''
                    # moved to before each z-stack on 12/29/2021
                    if (self.NZ > 1):
                        # maneuver for achiving uniform step size and repeatability when using open-loop control
                        self.navigationController.move_z_usteps(80)
                        self.wait_till_operation_is_completed()
                        self.navigationController.move_z_usteps(-80)
                        self.wait_till_operation_is_completed()
                        time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
                    '''
                    
                    file_ID = str(i) + '_' + str(j if x_scan_direction==1 else self.NX-1-j) + '_' + str(k)
                    # metadata = dict(x = self.navigationController.x_pos_mm, y = self.navigationController.y_pos_mm, z = self.navigationController.z_pos_mm)
                    # metadata = json.dumps(metadata)

                    # iterate through selected modes
                    for config in self.selected_configurations:
                        # update the current configuration
                        self.signal_current_configuration.emit(config)
                        self.wait_till_operation_is_completed()
                        # trigger acquisition (including turning on the illumination)
                        if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                            self.liveController.turn_on_illumination()
                            self.wait_till_operation_is_completed()
                            self.camera.send_trigger()
                        elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                            self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
                        # read camera frame
                        image = self.camera.read_frame()
                        # tunr of the illumination if using software trigger
                        if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                            self.liveController.turn_off_illumination()
                        # process the image
                        image = utils.crop_image(image,self.crop_width,self.crop_height)
                        # self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
                        image_to_display = utils.crop_image(image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling))
                        self.image_to_display.emit(image_to_display)
                        self.image_to_display_multi.emit(image_to_display,config.illumination_source)
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
                        # tifffile.imsave(saving_path, image, description=metadata)
                        QApplication.processEvents()

                    # add the coordinate of the current location
                    coordinates_pd = coordinates_pd.append({'i':i,'j':j,'k':k,
                                                            'x (mm)':self.navigationController.x_pos_mm,
                                                            'y (mm)':self.navigationController.y_pos_mm,
                                                            'z (um)':self.navigationController.z_pos_mm*1000},
                                                            ignore_index = True)

                    # register the current fov in the navigationViewer 
                    self.signal_register_current_fov.emit(self.navigationController.x_pos_mm,self.navigationController.y_pos_mm)

                    # check if the acquisition should be aborted
                    if self.multiPointController.abort_acqusition_requested:
                        self.liveController.turn_off_illumination()
                        self.navigationController.move_x_usteps(-dx_usteps)
                        self.wait_till_operation_is_completed()
                        self.navigationController.move_y_usteps(-dy_usteps)
                        self.wait_till_operation_is_completed()
                        self.navigationController.move_z_usteps(-dz_usteps)
                        self.wait_till_operation_is_completed()
                        coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
                        self.navigationController.enable_joystick_button_action = True
                        return

                    if self.NZ > 1:
                        # move z
                        if k < self.NZ - 1:
                            self.navigationController.move_z_usteps(self.deltaZ_usteps)
                            self.wait_till_operation_is_completed()
                            time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
                            dz_usteps = dz_usteps + self.deltaZ_usteps
                
                if self.NZ > 1:
                    # move z back
                    self.navigationController.move_z_usteps(-self.deltaZ_usteps*(self.NZ-1))
                    self.wait_till_operation_is_completed()
                    dz_usteps = dz_usteps - self.deltaZ_usteps*(self.NZ-1)

                # update FOV counter
                self.FOV_counter = self.FOV_counter + 1

                if self.NX > 1:
                    # move x
                    if j < self.NX - 1:
                        self.navigationController.move_x_usteps(x_scan_direction*self.deltaX_usteps)
                        self.wait_till_operation_is_completed()
                        time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)
                        dx_usteps = dx_usteps + x_scan_direction*self.deltaX_usteps

            '''
            # instead of move back, reverse scan direction (12/29/2021)
            if self.NX > 1:
                # move x back
                self.navigationController.move_x_usteps(-self.deltaX_usteps*(self.NX-1))
                self.wait_till_operation_is_completed()
                time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)
            '''
            x_scan_direction = -x_scan_direction

            if self.NY > 1:
                # move y
                if i < self.NY - 1:
                    self.navigationController.move_y_usteps(self.deltaY_usteps)
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
                    dy_usteps = dy_usteps + self.deltaY_usteps

        if self.NY > 1:
            # move y back
            self.navigationController.move_y_usteps(-self.deltaY_usteps*(self.NY-1))
            self.wait_till_operation_is_completed()
            time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
            dy_usteps = dy_usteps - self.deltaY_usteps*(self.NY-1)

        # move x back at the end of the scan
        if x_scan_direction == -1:
            self.navigationController.move_x_usteps(-self.deltaX_usteps*(self.NX-1))
            self.wait_till_operation_is_completed()
            time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)

        coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
        self.navigationController.enable_joystick_button_action = True

class MultiPointController(QObject):

    acquisitionFinished = Signal()
    image_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    signal_current_configuration = Signal(Configuration)
    signal_register_current_fov = Signal(float,float)

    def __init__(self,camera,navigationController,liveController,autofocusController,configurationManager):
        QObject.__init__(self)

        self.camera = camera
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
        self.crop_width = Acquisition.CROP_WIDTH
        self.crop_height = Acquisition.CROP_HEIGHT
        self.display_resolution_scaling = Acquisition.IMAGE_DISPLAY_SCALING_FACTOR
        self.counter = 0
        self.experiment_ID = None
        self.base_path = None
        self.selected_configurations = []

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

    def set_crop(self,crop_width,height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def set_base_path(self,path):
        self.base_path = path

    def start_new_experiment(self,experiment_ID): # @@@ to do: change name to prepare_folder_for_new_experiment
        # generate unique experiment ID
        self.experiment_ID = experiment_ID.replace(' ','_') + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f')
        self.recording_start_time = time.time()
        # create a new folder
        os.mkdir(os.path.join(self.base_path,self.experiment_ID))
        self.configurationManager.write_configuration(os.path.join(self.base_path,self.experiment_ID)+"/configurations.xml") # save the configuration for the experiment
        acquisition_parameters = {'dx(mm)':self.deltaX, 'Nx':self.NX, 'dy(mm)':self.deltaY, 'Ny':self.NY, 'dz(um)':self.deltaZ*1000,'Nz':self.NZ,'dt(s)':self.deltat,'Nt':self.Nt,'with AF':self.do_autofocus}
        f = open(os.path.join(self.base_path,self.experiment_ID)+"/acquisition parameters.json","w")
        f.write(json.dumps(acquisition_parameters))
        f.close()


    def set_selected_configurations(self, selected_configurations_name):
        self.selected_configurations = []
        for configuration_name in selected_configurations_name:
            self.selected_configurations.append(next((config for config in self.configurationManager.configurations if config.name == configuration_name)))
        
    def run_acquisition(self): # @@@ to do: change name to run_experiment
        print('start multipoint')
        print(str(self.Nt) + '_' + str(self.NX) + '_' + str(self.NY) + '_' + str(self.NZ))

        self.abort_acqusition_requested = False

        self.configuration_before_running_multipoint = self.liveController.currentConfiguration
        # stop live
        if self.liveController.is_live:
            self.liveController.was_live_before_multipoint = True
            self.liveController.stop_live() # @@@ to do: also uncheck the live button
        else:
            self.liveController.was_live_before_multipoint = False

        # disable callback
        if self.camera.callback_is_enabled:
            self.camera.callback_was_enabled_before_multipoint = True
            self.camera.stop_streaming()
            self.camera.disable_callback()
            self.camera.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
        else:
            self.camera.callback_was_enabled_before_multipoint = False

        # run the acquisition
        self.timestamp_acquisition_started = time.time()
        # create a QThread object
        self.thread = QThread()
        # create a worker object
        self.multiPointWorker = MultiPointWorker(self)
        # move the worker to the thread
        self.multiPointWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.multiPointWorker.run)
        self.multiPointWorker.finished.connect(self._on_acquisition_completed)
        self.multiPointWorker.finished.connect(self.multiPointWorker.deleteLater)
        self.multiPointWorker.finished.connect(self.thread.quit)
        self.multiPointWorker.image_to_display.connect(self.slot_image_to_display)
        self.multiPointWorker.image_to_display_multi.connect(self.slot_image_to_display_multi)
        self.multiPointWorker.signal_current_configuration.connect(self.slot_current_configuration,type=Qt.BlockingQueuedConnection)
        self.multiPointWorker.signal_register_current_fov.connect(self.slot_register_current_fov)
        # self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.thread.quit)
        # start the thread
        self.thread.start()

    def _on_acquisition_completed(self):
        # restore the previous selected mode
        self.signal_current_configuration.emit(self.configuration_before_running_multipoint)

        # re-enable callback
        if self.camera.callback_was_enabled_before_multipoint:
            self.camera.stop_streaming()
            self.camera.enable_callback()
            self.camera.start_streaming()
            self.camera.callback_was_enabled_before_multipoint = False
        
        # re-enable live if it's previously on
        if self.liveController.was_live_before_multipoint:
            self.liveController.start_live()
        
        # emit the acquisition finished signal to enable the UI
        self.acquisitionFinished.emit()
        QApplication.processEvents()

    def request_abort_aquisition(self):
        self.abort_acqusition_requested = True

    def slot_image_to_display(self,image):
        self.image_to_display.emit(image)

    def slot_image_to_display_multi(self,image,illumination_source):
        self.image_to_display_multi.emit(image,illumination_source)

    def slot_current_configuration(self,configuration):
        self.signal_current_configuration.emit(configuration)

    def slot_register_current_fov(self,x_mm,y_mm):
        self.signal_register_current_fov.emit(x_mm,y_mm)

class TrackingController(QObject):

    signal_tracking_stopped = Signal()
    image_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    signal_current_configuration = Signal(Configuration)

    def __init__(self,camera,microcontroller,navigationController,configurationManager,liveController,autofocusController,imageDisplayWindow):
        QObject.__init__(self)
        self.camera = camera
        self.microcontroller = microcontroller
        self.navigationController = navigationController
        self.configurationManager = configurationManager
        self.liveController = liveController
        self.autofocusController = autofocusController
        self.imageDisplayWindow = imageDisplayWindow
        self.tracker = tracking.Tracker_Image()
        # self.tracker_z = tracking.Tracker_Z()
        # self.pid_controller_x = tracking.PID_Controller()
        # self.pid_controller_y = tracking.PID_Controller()
        # self.pid_controller_z = tracking.PID_Controller()

        self.tracking_time_interval_s = 0

        self.crop_width = Acquisition.CROP_WIDTH
        self.crop_height = Acquisition.CROP_HEIGHT
        self.display_resolution_scaling = Acquisition.IMAGE_DISPLAY_SCALING_FACTOR
        self.counter = 0
        self.experiment_ID = None
        self.base_path = None
        self.selected_configurations = []

        self.flag_stage_tracking_enabled = True
        self.flag_AF_enabled = False
        self.flag_save_image = False
        self.flag_stop_tracking_requested = False

        self.pixel_size_um = None
        self.objective = None

    def start_tracking(self):
        
        # save pre-tracking configuration
        print('start tracking')
        self.configuration_before_running_tracking = self.liveController.currentConfiguration
        
        # stop live
        if self.liveController.is_live:
            self.was_live_before_tracking = True
            self.liveController.stop_live() # @@@ to do: also uncheck the live button
        else:
            self.was_live_before_tracking = False

        # disable callback
        if self.camera.callback_is_enabled:
            self.camera_callback_was_enabled_before_tracking = True
            self.camera.stop_streaming()
            self.camera.disable_callback()
            self.camera.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
        else:
            self.camera_callback_was_enabled_before_tracking = False

        # hide roi selector
        self.imageDisplayWindow.hide_ROI_selector()

        # run tracking
        self.flag_stop_tracking_requested = False
        # create a QThread object
        try:
            if self.thread.isRunning():
                print('*** previous tracking thread is still running ***')
                self.thread.terminate()
                self.thread.wait()
                print('*** previous tracking threaded manually stopped ***')
        except:
            pass
        self.thread = QThread()
        # create a worker object
        self.trackingWorker = TrackingWorker(self)
        # move the worker to the thread
        self.trackingWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.trackingWorker.run)
        self.trackingWorker.finished.connect(self._on_tracking_stopped)
        self.trackingWorker.finished.connect(self.trackingWorker.deleteLater)
        self.trackingWorker.finished.connect(self.thread.quit)
        self.trackingWorker.image_to_display.connect(self.slot_image_to_display)
        self.trackingWorker.image_to_display_multi.connect(self.slot_image_to_display_multi)
        self.trackingWorker.signal_current_configuration.connect(self.slot_current_configuration,type=Qt.BlockingQueuedConnection)
        # self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.thread.quit)
        # start the thread
        self.thread.start()

    def _on_tracking_stopped(self):

        # restore the previous selected mode
        self.signal_current_configuration.emit(self.configuration_before_running_tracking)

        # re-enable callback
        if self.camera_callback_was_enabled_before_tracking:
            self.camera.stop_streaming()
            self.camera.enable_callback()
            self.camera.start_streaming()
            self.camera_callback_was_enabled_before_tracking = False
        
        # re-enable live if it's previously on
        if self.was_live_before_tracking:
            self.liveController.start_live()

        # show ROI selector
        self.imageDisplayWindow.show_ROI_selector()
        
        # emit the acquisition finished signal to enable the UI
        self.signal_tracking_stopped.emit()
        QApplication.processEvents()

    def start_new_experiment(self,experiment_ID): # @@@ to do: change name to prepare_folder_for_new_experiment
        # generate unique experiment ID
        self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f')
        self.recording_start_time = time.time()
        # create a new folder
        try:
            os.mkdir(os.path.join(self.base_path,self.experiment_ID))
            self.configurationManager.write_configuration(os.path.join(self.base_path,self.experiment_ID)+"/configurations.xml") # save the configuration for the experiment
        except:
            print('error in making a new folder')
            pass

    def set_selected_configurations(self, selected_configurations_name):
        self.selected_configurations = []
        for configuration_name in selected_configurations_name:
            self.selected_configurations.append(next((config for config in self.configurationManager.configurations if config.name == configuration_name)))

    def toggle_stage_tracking(self,state):
        self.flag_stage_tracking_enabled = state > 0
        print('set stage tracking enabled to ' + str(self.flag_stage_tracking_enabled))

    def toggel_enable_af(self,state):
        self.flag_AF_enabled = state > 0
        print('set af enabled to ' + str(self.flag_AF_enabled))

    def toggel_save_images(self,state):
        self.flag_save_image = state > 0
        print('set save images to ' + str(self.flag_save_image))

    def set_base_path(self,path):
        self.base_path = path

    def stop_tracking(self):
        self.flag_stop_tracking_requested = True
        print('stop tracking requested')

    def slot_image_to_display(self,image):
        self.image_to_display.emit(image)

    def slot_image_to_display_multi(self,image,illumination_source):
        self.image_to_display_multi.emit(image,illumination_source)

    def slot_current_configuration(self,configuration):
        self.signal_current_configuration.emit(configuration)

    def update_pixel_size(self, pixel_size_um):
        self.pixel_size_um = pixel_size_um

    def update_tracker_selection(self,tracker_str):
        self.tracker.update_tracker_type(tracker_str)

    def set_tracking_time_interval(self,time_interval):
        self.tracking_time_interval_s = time_interval

    def update_image_resizing_factor(self,image_resizing_factor):
        self.image_resizing_factor = image_resizing_factor
        print('update tracking image resizing factor to ' + str(self.image_resizing_factor))
        self.pixel_size_um_scaled = self.pixel_size_um/self.image_resizing_factor

    # PID-based tracking
    '''
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
    '''

class TrackingWorker(QObject):

    finished = Signal()
    image_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    signal_current_configuration = Signal(Configuration)

    def __init__(self,trackingController):
        QObject.__init__(self)
        self.trackingController = trackingController

        self.camera = self.trackingController.camera
        self.microcontroller = self.trackingController.microcontroller
        self.navigationController = self.trackingController.navigationController
        self.liveController = self.trackingController.liveController
        self.autofocusController = self.trackingController.autofocusController
        self.configurationManager = self.trackingController.configurationManager
        self.imageDisplayWindow = self.trackingController.imageDisplayWindow
        self.crop_width = self.trackingController.crop_width
        self.crop_height = self.trackingController.crop_height
        self.display_resolution_scaling = self.trackingController.display_resolution_scaling
        self.counter = self.trackingController.counter
        self.experiment_ID = self.trackingController.experiment_ID
        self.base_path = self.trackingController.base_path
        self.selected_configurations = self.trackingController.selected_configurations
        self.tracker = trackingController.tracker
        
        self.number_of_selected_configurations = len(self.selected_configurations)

        # self.tracking_time_interval_s = self.trackingController.tracking_time_interval_s
        # self.flag_stage_tracking_enabled = self.trackingController.flag_stage_tracking_enabled
        # self.flag_AF_enabled = False
        # self.flag_save_image = False
        # self.flag_stop_tracking_requested = False

        self.image_saver = ImageSaver_Tracking(base_path=os.path.join(self.base_path,self.experiment_ID),image_format='bmp')

    def run(self):

        tracking_frame_counter = 0
        t0 = time.time()

        # save metadata
        self.txt_file = open( os.path.join(self.base_path,self.experiment_ID,"metadata.txt"), "w+")
        self.txt_file.write('t0: ' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f') + '\n')
        self.txt_file.write('objective: ' + self.trackingController.objective + '\n')
        self.txt_file.close()

        # create a file for logging 
        self.csv_file = open( os.path.join(self.base_path,self.experiment_ID,"track.csv"), "w+")
        self.csv_file.write('dt (s), x_stage (mm), y_stage (mm), z_stage (mm), x_image (mm), y_image(mm), image_filename\n')

        # reset tracker
        self.tracker.reset()

        # get the manually selected roi
        init_roi = self.imageDisplayWindow.get_roi_bounding_box()
        self.tracker.set_roi_bbox(init_roi)

        # tracking loop
        while self.trackingController.flag_stop_tracking_requested == False:

            print('tracking_frame_counter: ' + str(tracking_frame_counter) )
            if tracking_frame_counter == 0:
                is_first_frame = True
            else:
                is_first_frame = False

            # timestamp
            timestamp_last_frame = time.time()

            # switch to the tracking config
            config = self.selected_configurations[0]
            self.signal_current_configuration.emit(config)
            self.wait_till_operation_is_completed()

            # do autofocus 
            if self.trackingController.flag_AF_enabled and tracking_frame_counter > 1:
                # do autofocus
                print('>>> autofocus')
                self.autofocusController.autofocus()
                self.autofocusController.wait_till_autofocus_has_completed()
                print('>>> autofocus completed')

            # get current position
            x_stage = self.navigationController.x_pos_mm
            y_stage = self.navigationController.y_pos_mm
            z_stage = self.navigationController.z_pos_mm

            # grab an image
            config = self.selected_configurations[0]
            if(self.number_of_selected_configurations > 1):
                self.signal_current_configuration.emit(config)
                self.wait_till_operation_is_completed()
                self.liveController.turn_on_illumination()        # keep illumination on for single configuration acqusition
                self.wait_till_operation_is_completed()
            t = time.time()
            self.camera.send_trigger() 
            image = self.camera.read_frame()
            if(self.number_of_selected_configurations > 1):
                self.liveController.turn_off_illumination()       # keep illumination on for single configuration acqusition
            # image crop, rotation and flip
            image = utils.crop_image(image,self.crop_width,self.crop_height)
            image = np.squeeze(image)
            image = utils.rotate_and_flip_image(image,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            # get image size
            image_shape = image.shape
            image_center = np.array([image_shape[1]*0.5,image_shape[0]*0.5])

            # image the rest configurations
            for config_ in self.selected_configurations[1:]:
                self.signal_current_configuration.emit(config_)
                self.wait_till_operation_is_completed()
                self.liveController.turn_on_illumination()
                self.wait_till_operation_is_completed()
                self.camera.send_trigger() 
                image_ = self.camera.read_frame()
                self.liveController.turn_off_illumination()
                image_ = utils.crop_image(image_,self.crop_width,self.crop_height)
                image_ = np.squeeze(image_)
                image_ = utils.rotate_and_flip_image(image_,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                # display image
                # self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
                image_to_display_ = utils.crop_image(image_,round(self.crop_width*self.liveController.display_resolution_scaling), round(self.crop_height*self.liveController.display_resolution_scaling))
                # self.image_to_display.emit(image_to_display_)
                self.image_to_display_multi.emit(image_to_display_,config_.illumination_source)
                # save image
                if self.trackingController.flag_save_image:
                    if self.camera.is_color:
                        image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                    self.image_saver.enqueue(image_,tracking_frame_counter,str(config_.name))

            # track
            objectFound,centroid,rect_pts = self.tracker.track(image, None, is_first_frame = is_first_frame)
            if objectFound == False:
                print('')
                break
            in_plane_position_error_pixel = image_center - centroid 
            in_plane_position_error_mm = in_plane_position_error_pixel*self.trackingController.pixel_size_um_scaled/1000
            x_error_mm = in_plane_position_error_mm[0]
            y_error_mm = in_plane_position_error_mm[1]

            # display the new bounding box and the image
            self.imageDisplayWindow.update_bounding_box(rect_pts)
            self.imageDisplayWindow.display_image(image)

            # move
            if self.trackingController.flag_stage_tracking_enabled:
                x_correction_usteps = int(x_error_mm/(SCREW_PITCH_X_MM/FULLSTEPS_PER_REV_X/self.navigationController.x_microstepping))
                y_correction_usteps = int(y_error_mm/(SCREW_PITCH_Y_MM/FULLSTEPS_PER_REV_Y/self.navigationController.y_microstepping))
                self.microcontroller.move_x_usteps(TRACKING_MOVEMENT_SIGN_X*x_correction_usteps)
                self.microcontroller.move_y_usteps(TRACKING_MOVEMENT_SIGN_Y*y_correction_usteps) 

            # save image
            if self.trackingController.flag_save_image:
                self.image_saver.enqueue(image,tracking_frame_counter,str(config.name))

            # save position data            
            # self.csv_file.write('dt (s), x_stage (mm), y_stage (mm), z_stage (mm), x_image (mm), y_image(mm), image_filename\n')
            self.csv_file.write(str(t)+','+str(x_stage)+','+str(y_stage)+','+str(z_stage)+','+str(x_error_mm)+','+str(y_error_mm)+','+str(tracking_frame_counter)+'\n')
            if tracking_frame_counter%100 == 0:
                self.csv_file.flush()

            # wait for movement to complete
            self.wait_till_operation_is_completed() # to do - make sure both x movement and y movement are complete

            # wait till tracking interval has elapsed
            while(time.time() - timestamp_last_frame < self.trackingController.tracking_time_interval_s):
                time.sleep(0.005)

            # increament counter 
            tracking_frame_counter = tracking_frame_counter + 1

        # tracking terminated
        self.csv_file.close()
        self.image_saver.close()
        self.finished.emit()

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)


class ImageDisplayWindow(QMainWindow):

    def __init__(self, window_title='', draw_crosshairs = False, invertX=False):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.widget = QWidget()

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')

        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.view = self.graphics_widget.addViewBox(invertX=invertX)
        
        ## lock the aspect ratio so pixels are always square
        self.graphics_widget.view.setAspectLocked(True)
        
        ## Create image item
        self.graphics_widget.img = pg.ImageItem(border='w')
        self.graphics_widget.view.addItem(self.graphics_widget.img)

        ## Create ROI
        self.roi_pos = (500,500)
        self.roi_size = (500,500)
        self.ROI = pg.ROI(self.roi_pos, self.roi_size, scaleSnap=True, translateSnap=True)
        self.ROI.setZValue(10)
        self.ROI.addScaleHandle((0,0), (1,1))
        self.ROI.addScaleHandle((1,1), (0,0))
        self.graphics_widget.view.addItem(self.ROI)
        self.ROI.hide()
        self.ROI.sigRegionChanged.connect(self.update_ROI)
        self.roi_pos = self.ROI.pos()
        self.roi_size = self.ROI.size()

        ## Variables for annotating images
        self.draw_rectangle = False
        self.ptRect1 = None
        self.ptRect2 = None
        self.DrawCirc = False
        self.centroid = None
        self.DrawCrossHairs = False
        self.image_offset = np.array([0, 0])

        ## Layout
        layout = QGridLayout()
        layout.addWidget(self.graphics_widget, 0, 0) 
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)

        # set window size
        desktopWidget = QDesktopWidget();
        width = min(desktopWidget.height()*0.9,1000) #@@@TO MOVE@@@#
        height = width
        self.setFixedSize(width,height)

    def display_image(self,image):
        if ENABLE_TRACKING:
            image = np.copy(image)
            self.image_height = image.shape[0],
            self.image_width = image.shape[1]
            if(self.draw_rectangle):
                cv2.rectangle(image, self.ptRect1, self.ptRect2,(255,255,255) , 4)
                self.draw_rectangle = False
            self.graphics_widget.img.setImage(image,autoLevels=False)
        else:
            self.graphics_widget.img.setImage(image,autoLevels=False)
       
    def update_ROI(self):
        self.roi_pos = self.ROI.pos()
        self.roi_size = self.ROI.size()

    def show_ROI_selector(self):
        self.ROI.show()

    def hide_ROI_selector(self):
        self.ROI.hide()

    def get_roi(self):
        return self.roi_pos,self.roi_size

    def update_bounding_box(self,pts):
        self.draw_rectangle=True
        self.ptRect1=(pts[0][0],pts[0][1])
        self.ptRect2=(pts[1][0],pts[1][1])

    def get_roi_bounding_box(self):
        self.update_ROI()
        width = self.roi_size[0]
        height = self.roi_size[1]
        xmin = max(0, self.roi_pos[0])
        ymin = max(0, self.roi_pos[1])
        return np.array([xmin, ymin, width, height])

class NavigationViewer(QFrame):

    def __init__(self, invertX = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setBackground("w")
        self.graphics_widget.view = self.graphics_widget.addViewBox(invertX=invertX,invertY=True)
        ## lock the aspect ratio so pixels are always square
        self.graphics_widget.view.setAspectLocked(True)
        ## Create image item
        self.graphics_widget.img = pg.ImageItem(border='w')
        self.graphics_widget.view.addItem(self.graphics_widget.img)

        self.grid = QVBoxLayout()
        self.grid.addWidget(self.graphics_widget)
        self.setLayout(self.grid)

        self.background_image = cv2.imread('images/slide carrier_828x662.png')
        self.current_image = np.copy(self.background_image)
        self.current_image_display = np.copy(self.background_image)
        self.image_height = self.background_image.shape[0]
        self.image_width = self.background_image.shape[1]

        self.origin_bottom_left_x = 175
        self.origin_bottom_left_y = 170
        self.mm_per_pixel = 0.1453
        self.fov_size_mm = 3000*1.85/(50/9)/1000

        self.box_color = (255, 0, 0)
        self.box_line_thickness = 2

        self.x_mm = None
        self.y_mm = None

        self.update_display()

    def update_current_location(self,x_mm,y_mm):
        if self.x_mm != None and self.y_mm != None:
            # update only when the displacement has exceeded certain value
            if abs(x_mm - self.x_mm) > 0.4 or abs(y_mm - self.y_mm) > 0.4:
                self.draw_current_fov(x_mm,y_mm)
                self.update_display()
                self.x_mm = x_mm
                self.y_mm = y_mm
        else:
            self.draw_current_fov(x_mm,y_mm)
            self.update_display()
            self.x_mm = x_mm
            self.y_mm = y_mm

    def draw_current_fov(self,x_mm,y_mm):
        self.current_image_display = np.copy(self.current_image)
        current_FOV_top_left = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
        current_FOV_bottom_right = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        cv2.rectangle(self.current_image_display, current_FOV_top_left, current_FOV_bottom_right, self.box_color, self.box_line_thickness)

    def update_display(self):
        self.graphics_widget.img.setImage(self.current_image_display,autoLevels=False)

    def clear_slide(self):
        self.current_image = np.copy(self.background_image)
        self.current_image_display = np.copy(self.background_image)
        self.update_display()

    def register_fov(self,x_mm,y_mm):
        color = (0,0,255)
        current_FOV_top_left = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
        current_FOV_bottom_right = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        cv2.rectangle(self.current_image, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)

class ImageArrayDisplayWindow(QMainWindow):

    def __init__(self, window_title=''):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.widget = QWidget()

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')

        self.graphics_widget_1 = pg.GraphicsLayoutWidget()
        self.graphics_widget_1.view = self.graphics_widget_1.addViewBox()
        self.graphics_widget_1.view.setAspectLocked(True)
        self.graphics_widget_1.img = pg.ImageItem(border='w')
        self.graphics_widget_1.view.addItem(self.graphics_widget_1.img)

        self.graphics_widget_2 = pg.GraphicsLayoutWidget()
        self.graphics_widget_2.view = self.graphics_widget_2.addViewBox()
        self.graphics_widget_2.view.setAspectLocked(True)
        self.graphics_widget_2.img = pg.ImageItem(border='w')
        self.graphics_widget_2.view.addItem(self.graphics_widget_2.img)

        self.graphics_widget_3 = pg.GraphicsLayoutWidget()
        self.graphics_widget_3.view = self.graphics_widget_3.addViewBox()
        self.graphics_widget_3.view.setAspectLocked(True)
        self.graphics_widget_3.img = pg.ImageItem(border='w')
        self.graphics_widget_3.view.addItem(self.graphics_widget_3.img)

        self.graphics_widget_4 = pg.GraphicsLayoutWidget()
        self.graphics_widget_4.view = self.graphics_widget_4.addViewBox()
        self.graphics_widget_4.view.setAspectLocked(True)
        self.graphics_widget_4.img = pg.ImageItem(border='w')
        self.graphics_widget_4.view.addItem(self.graphics_widget_4.img)

        ## Layout
        layout = QGridLayout()
        layout.addWidget(self.graphics_widget_1, 0, 0)
        layout.addWidget(self.graphics_widget_2, 0, 1)
        layout.addWidget(self.graphics_widget_3, 1, 0)
        layout.addWidget(self.graphics_widget_4, 1, 1) 
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)

        # set window size
        desktopWidget = QDesktopWidget();
        width = min(desktopWidget.height()*0.9,1000) #@@@TO MOVE@@@#
        height = width
        self.setFixedSize(width,height)

    def display_image(self,image,illumination_source):
        if illumination_source < 11:
            self.graphics_widget_1.img.setImage(image,autoLevels=False)
        elif illumination_source == 11:
            self.graphics_widget_2.img.setImage(image,autoLevels=False)
        elif illumination_source == 12:
            self.graphics_widget_3.img.setImage(image,autoLevels=False)
        elif illumination_source == 13:
            self.graphics_widget_4.img.setImage(image,autoLevels=False)

class ConfigurationManager(QObject):
    def __init__(self,filename=str(Path.home()) + "/configurations_default.xml"):
        QObject.__init__(self)
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
                    camera_sn = mode.get('CameraSN'))
            )

    def update_configuration(self,configuration_id,attribute_name,new_value):
        list = self.config_xml_tree_root.xpath("//mode[contains(@ID," + "'" + str(configuration_id) + "')]")
        mode_to_update = list[0]
        mode_to_update.set(attribute_name,str(new_value))
        self.save_configurations()

class PlateReaderNavigationController(QObject):

    signal_homing_complete = Signal()
    signal_current_well = Signal(str)

    def __init__(self,microcontroller):
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.x_pos_mm = 0
        self.y_pos_mm = 0
        self.z_pos_mm = 0
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
            x_usteps = round(x_mm/mm_per_ustep_X)
            self.move_x_to_usteps(x_usteps)
        if row != '':
            mm_per_ustep_Y = SCREW_PITCH_Y_MM/(self.y_microstepping*FULLSTEPS_PER_REV_Y)
            y_mm = PLATE_READER.OFFSET_ROW_A_MM + (ord(row) - ord('A'))*PLATE_READER.ROW_SPACING_MM
            y_usteps = round(y_mm/mm_per_ustep_Y)
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
        if self.is_homing and self.microcontroller.mcu_cmd_execution_in_progress == False:
            self.signal_homing_complete.emit()
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

        if self.is_scanning:
            self.signal_current_well.emit(row+column)

    def home(self):
        self.is_homing = True
        self.microcontroller.home_xy()

    def home_x(self):
        self.microcontroller.home_x()

    def home_y(self):
        self.microcontroller.home_y()
