# set QT_API environment variable
import os 
import sys

# qt libraries
os.environ["QT_API"] = "pyqt5"
import qtpy
import pyqtgraph as pg
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# control 
from control._def import *
from control.processing_handler import ProcessingHandler
from control.processing_pipeline import *
#from control.stitcher import Stitcher, default_image_reader
from control.multipoint_built_in_functionalities import malaria_rtp

import control.utils as utils
import control.utils_config as utils_config
import control.tracking as tracking
import control.serial_peripherals as serial_peripherals

try:
    from control.multipoint_custom_script_entry import *
    print('custom multipoint script found')
except:
    pass

from queue import Queue
from threading import Thread, Lock
from pathlib import Path
from datetime import datetime
import time
import subprocess
import shutil
from lxml import etree
import json
import math
import random
import numpy as np
import pandas as pd
import scipy.signal
import cv2
import imageio as iio


class ObjectiveStore:
    def __init__(self, objectives_dict = OBJECTIVES, default_objective = DEFAULT_OBJECTIVE):
        self.objectives_dict = objectives_dict
        self.default_objective = default_objective
        self.current_objective = default_objective

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
            # @@@ to move to camera 
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

    def __init__(self,image_format=Acquisition.IMAGE_FORMAT):
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
            if ( self.recording_time_limit>0 ) and ( time.time()-self.recording_start_time >= self.recording_time_limit ):
                self.stop_recording.emit()
            # when using self.queue.put(str_), program can be slowed down despite multithreading because of the block and the GIL
        except:
            print('imageSaver queue is full, image discarded')

    def set_base_path(self,path):
        self.base_path = path

    def set_recording_time_limit(self,time_limit):
        self.recording_time_limit = time_limit

    def start_new_experiment(self,experiment_ID,add_timestamp=True):
        if add_timestamp:
            # generate unique experiment ID
            self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')
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
    def __init__(self,mode_id=None,name=None,color=None,camera_sn=None,exposure_time=None,analog_gain=None,illumination_source=None,illumination_intensity=None,z_offset=None,pixel_format=None,_pixel_format_options=None,emission_filter_position=None):
        self.id = mode_id
        self.name = name
        self.color = color
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
        self.emission_filter_position = emission_filter_position

class LiveController(QObject):

    def __init__(self,camera,microcontroller,configurationManager,parent=None,control_illumination=True,use_internal_timer_for_hardware_trigger=True,for_displacement_measurement=False):
        QObject.__init__(self)
        self.microscope = parent
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

        self.fps_trigger = 1;
        self.timer_trigger_interval = (1/self.fps_trigger)*1000

        self.timer_trigger = QTimer()
        self.timer_trigger.setInterval(int(self.timer_trigger_interval))
        self.timer_trigger.timeout.connect(self.trigger_acquisition)

        self.trigger_ID = -1

        self.fps_real = 0
        self.counter = 0
        self.timestamp_last = 0

        self.display_resolution_scaling = DEFAULT_DISPLAY_CROP/100

        if USE_LDI_SERIAL_CONTROL:
            self.ldi = serial_peripherals.LDI()
      
        if SUPPORT_SCIMICROSCOPY_LED_ARRAY:
            # to do: add error handling
            self.led_array = serial_peripherals.SciMicroscopyLEDArray(SCIMICROSCOPY_LED_ARRAY_SN,SCIMICROSCOPY_LED_ARRAY_DISTANCE,SCIMICROSCOPY_LED_ARRAY_TURN_ON_DELAY)
            self.led_array.set_NA(SCIMICROSCOPY_LED_ARRAY_DEFAULT_NA)

    # illumination control
    def turn_on_illumination(self):
        if USE_LDI_SERIAL_CONTROL and 'Fluorescence' in self.currentConfiguration.name:
            self.ldi.set_active_channel_shutter(1)
        elif SUPPORT_SCIMICROSCOPY_LED_ARRAY and 'LED matrix' in self.currentConfiguration.name:
            self.led_array.turn_on_illumination()
        else:
            self.microcontroller.turn_on_illumination()
        self.illumination_on = True

    def turn_off_illumination(self):
        if USE_LDI_SERIAL_CONTROL and 'Fluorescence' in self.currentConfiguration.name:
            self.ldi.set_active_channel_shutter(0)
        elif SUPPORT_SCIMICROSCOPY_LED_ARRAY and 'LED matrix' in self.currentConfiguration.name:
            self.led_array.turn_off_illumination()
        else:
            self.microcontroller.turn_off_illumination()
        self.illumination_on = False

    def set_illumination(self,illumination_source,intensity,update_channel_settings=True):
        if illumination_source < 10: # LED matrix
            if SUPPORT_SCIMICROSCOPY_LED_ARRAY:
                # set color
                if 'BF LED matrix full_R' in self.currentConfiguration.name:
                    self.led_array.set_color((1,0,0))
                elif 'BF LED matrix full_G' in self.currentConfiguration.name:
                    self.led_array.set_color((0,1,0))
                elif 'BF LED matrix full_B' in self.currentConfiguration.name:
                    self.led_array.set_color((0,0,1))
                else:
                    self.led_array.set_color(SCIMICROSCOPY_LED_ARRAY_DEFAULT_COLOR)
                # set intensity
                self.led_array.set_brightness(intensity)
                # set mode
                if 'BF LED matrix left half' in self.currentConfiguration.name:
                    self.led_array.set_illumination('dpc.l')
                if 'BF LED matrix right half' in self.currentConfiguration.name:
                    self.led_array.set_illumination('dpc.r')
                if 'BF LED matrix top half' in self.currentConfiguration.name:
                    self.led_array.set_illumination('dpc.t')
                if 'BF LED matrix bottom half' in self.currentConfiguration.name:
                    self.led_array.set_illumination('dpc.b')
                if 'BF LED matrix full' in self.currentConfiguration.name:
                    self.led_array.set_illumination('bf')
                if 'DF LED matrix' in self.currentConfiguration.name:
                    self.led_array.set_illumination('df')
            else:
                self.microcontroller.set_illumination_led_matrix(illumination_source,r=(intensity/100)*LED_MATRIX_R_FACTOR,g=(intensity/100)*LED_MATRIX_G_FACTOR,b=(intensity/100)*LED_MATRIX_B_FACTOR)
        else:
            # update illumination
            if USE_LDI_SERIAL_CONTROL and 'Fluorescence' in self.currentConfiguration.name:
                # set LDI active channel
                print('set active channel to ' + str(illumination_source))
                self.ldi.set_active_channel(int(illumination_source))
                if update_channel_settings:
                    # set intensity for active channel
                    print('set intensity')
                    self.ldi.set_intensity(int(illumination_source),intensity)
            elif ENABLE_NL5 and NL5_USE_DOUT and 'Fluorescence' in self.currentConfiguration.name:
                wavelength = int(self.currentConfiguration.name[13:16])
                self.microscope.nl5.set_active_channel(NL5_WAVENLENGTH_MAP[wavelength])
                if NL5_USE_AOUT and update_channel_settings:
                    self.microscope.nl5.set_laser_power(NL5_WAVENLENGTH_MAP[wavelength],int(intensity))
                if ENABLE_CELLX:
                    self.microscope.cellx.set_laser_power(NL5_WAVENLENGTH_MAP[wavelength],int(intensity))
            else:
                self.microcontroller.set_illumination(illumination_source,intensity)

            # set emission filter position
            if 'Fluorescence' in self.currentConfiguration.name:
                try:
                    self.microscope.xlight.set_emission_filter(XLIGHT_EMISSION_FILTER_MAPPING[illumination_source],extraction=False,validate=XLIGHT_VALIDATE_WHEEL_POS)
                except Exception as e:
                    print('not setting emission filter position due to ' + str(e))

                if USE_ZABER_EMISSION_FILTER_WHEEL:
                    try:
                        self.microscope.emission_filter_wheel.set_emission_filter(str(self.currentConfiguration.emission_filter_position))
                    except Exception as e:
                        print('not setting emission filter position due to ' + str(e))


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
            if ENABLE_NL5 and NL5_USE_DOUT:
                self.microscope.nl5.start_acquisition()
            else:
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

class NavigationController(QObject):

    xPos = Signal(float)
    yPos = Signal(float)
    zPos = Signal(float)
    thetaPos = Signal(float)
    xyPos = Signal(float,float)
    signal_joystick_button_pressed = Signal()

    # x y z axis pid enable flag
    pid_enable_flag = [False, False, False]


    def __init__(self,microcontroller, parent=None):
        # parent should be set to OctopiGUI instance to enable updates
        # to camera settings, e.g. binning, that would affect click-to-move
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.parent = parent
        self.x_pos_mm = 0
        self.y_pos_mm = 0
        self.z_pos_mm = 0
        self.z_pos = 0
        self.theta_pos_rad = 0
        self.x_microstepping = MICROSTEPPING_DEFAULT_X
        self.y_microstepping = MICROSTEPPING_DEFAULT_Y
        self.z_microstepping = MICROSTEPPING_DEFAULT_Z
        self.click_to_move = False
        self.theta_microstepping = MICROSTEPPING_DEFAULT_THETA
        self.enable_joystick_button_action = True

        # to be moved to gui for transparency
        self.microcontroller.set_callback(self.update_pos)

        # self.timer_read_pos = QTimer()
        # self.timer_read_pos.setInterval(PosUpdate.INTERVAL_MS)
        # self.timer_read_pos.timeout.connect(self.update_pos)
        # self.timer_read_pos.start()

        # scan start position
        self.scan_begin_position_x = 0
        self.scan_begin_position_y = 0

    def set_flag_click_to_move(self, flag):
        self.click_to_move = flag

    def get_flag_click_to_move(self):
        return self.click_to_move


    def scan_preview_move_from_click(self, click_x, click_y, image_width, image_height, Nx=1, Ny=1, dx_mm=0.9, dy_mm=0.9):
        """
        napariTiledDisplay uses the Nx, Ny, dx_mm, dy_mm fields to move to the correct fov first
        imageArrayDisplayWindow assumes only a single fov (default values do not impact calculation but this is less correct)
        """
        # check if click to move enabled
        if not self.click_to_move:
            print("allow click to move")
            return
        # restore to raw coordicate
        click_x = image_width / 2.0 + click_x
        click_y = image_height / 2.0 - click_y
        print("click - (x, y):", (click_x, click_y))
        cx = click_x * Nx // image_width
        cy = click_y * Ny // image_height
        print("fov - (col, row):", (cx, cy))
        pixel_sign_x = 1
        pixel_sign_y = 1 if INVERTED_OBJECTIVE else -1
 
        # move to selected fov
        self.move_x_to(self.scan_begin_position_x+dx_mm*cx*pixel_sign_x)
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)
        self.move_y_to(self.scan_begin_position_y-dy_mm*cy*pixel_sign_y)
        while self.microcontroller.is_busy():
            time.sleep(SLEEP_TIME_S)

        # move to actual click, offset from center fov
        tile_width = (image_width / Nx) * PRVIEW_DOWNSAMPLE_FACTOR
        tile_height = (image_height / Ny) * PRVIEW_DOWNSAMPLE_FACTOR
        offset_x = (click_x * PRVIEW_DOWNSAMPLE_FACTOR) % tile_width
        offset_y = (click_y * PRVIEW_DOWNSAMPLE_FACTOR) % tile_height
        offset_x_centered = int(offset_x - tile_width / 2)
        offset_y_centered = int(tile_height / 2 - offset_y)
        self.move_from_click(offset_x_centered, offset_y_centered, tile_width, tile_height)

    def move_from_click(self, click_x, click_y, image_width, image_height):
        if self.click_to_move:
            try:
                highest_res = (0,0)
                for res in self.parent.camera.res_list:
                    if res[0] > highest_res[0] or res[1] > higest_res[1]:
                        highest_res = res
                resolution = self.parent.camera.resolution

                try:
                    pixel_binning_x = highest_res[0]/resolution[0]
                    pixel_binning_y = highest_res[1]/resolution[1]
                    if pixel_binning_x < 1:
                        pixel_binning_x = 1
                    if pixel_binning_y < 1:
                        pixel_binning_y = 1
                except:
                    pixel_binning_x=1
                    pixel_binning_y=1
            except AttributeError:
                pixel_binning_x = 1
                pixel_binning_y = 1

            try:
                current_objective = self.parent.objectiveStore.current_objective
                objective_info = self.parent.objectiveStore.objectives_dict.get(current_objective, {})
            except (AttributeError, KeyError):
                objective_info = OBJECTIVES[DEFAULT_OBJECTIVE]

            magnification = objective_info["magnification"]
            objective_tube_lens_mm = objective_info["tube_lens_f_mm"]
            tube_lens_mm = TUBE_LENS_MM
            pixel_size_um = CAMERA_PIXEL_SIZE_UM[CAMERA_SENSOR]

            pixel_size_xy = pixel_size_um/(magnification/(objective_tube_lens_mm/tube_lens_mm))

            pixel_size_x = pixel_size_xy*pixel_binning_x
            pixel_size_y = pixel_size_xy*pixel_binning_y

            pixel_sign_x = 1
            pixel_sign_y = 1 if INVERTED_OBJECTIVE else -1

            delta_x = pixel_sign_x*pixel_size_x*click_x/1000.0
            delta_y = pixel_sign_y*pixel_size_y*click_y/1000.0

            if not IS_HCS:
                delta_x /= 2.2
                delta_y /= 2.2

            self.move_x(delta_x)
            self.move_y(delta_y)

    def move_to_cached_position(self):
        if not os.path.isfile("cache/last_coords.txt"):
            return
        with open("cache/last_coords.txt","r") as f:
            for line in f:
                try:
                    x,y,z = line.strip("\n").strip().split(",")
                    x = float(x)
                    y = float(y)
                    z = float(z)
                    self.move_to(x,y)
                    self.move_z_to(z)
                    break
                except:
                    pass
                break

    def cache_current_position(self):
        with open("cache/last_coords.txt","w") as f:
            f.write(",".join([str(self.x_pos_mm),str(self.y_pos_mm),str(self.z_pos_mm)]))

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
    
    def move_to(self,x_mm,y_mm):
        self.move_x_to(x_mm)
        self.move_y_to(y_mm)

    def configure_encoder(self, axis, transitions_per_revolution,flip_direction):
        self.microcontroller.configure_stage_pid(axis, transitions_per_revolution=int(transitions_per_revolution), flip_direction=flip_direction)

    def set_pid_control_enable(self, axis, enable_flag):
        self.pid_enable_flag[axis] = enable_flag;
        if self.pid_enable_flag[axis] is True:
            self.microcontroller.turn_on_stage_pid(axis)
        else:
            self.microcontroller.turn_off_stage_pid(axis)

    def turnoff_axis_pid_control(self):
        for i in range(len(self.pid_enable_flag)):
            if self.pid_enable_flag[i] is True:
                self.microcontroller.turn_off_stage_pid(i)

    def get_pid_control_flag(self, axis):
        return self.pid_enable_flag[axis]

    def keep_scan_begin_position(self, x, y):
        self.scan_begin_position_x = x
        self.scan_begin_position_y = y

    def set_axis_PID_arguments(self, axis, pid_p, pid_i, pid_d):
        self.microcontroller.set_pid_arguments(axis, pid_p, pid_i, pid_d)

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
                sys.exit(1)

    def move_to_slide_loading_position(self):
        was_live = self.liveController.is_live
        if was_live:
            self.signal_stop_live.emit()

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

        if was_live:
            self.signal_resume_live.emit()

        self.slidePositionController.slide_loading_position_reached = True
        self.finished.emit()

    def move_to_slide_scanning_position(self):
        was_live = self.liveController.is_live
        if was_live:
            self.signal_stop_live.emit()

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
            if self.navigationController.get_pid_control_flag(2) is False:
                _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                self.navigationController.microcontroller.move_z_to_usteps(self.slidePositionController.z_pos - STAGE_MOVEMENT_SIGN_Z*_usteps_to_clear_backlash)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
                self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
            else:
                self.navigationController.microcontroller.move_z_to_usteps(self.slidePositionController.z_pos)
                self.wait_till_operation_is_completed(timestamp_start, SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S)
            self.slidePositionController.objective_retracted = False
            print('z position restored')
        
        if was_live:
            self.signal_resume_live.emit()

        self.slidePositionController.slide_scanning_position_reached = True
        self.finished.emit()

class SlidePositionController(QObject):

    signal_slide_loading_position_reached = Signal()
    signal_slide_scanning_position_reached = Signal()
    signal_clear_slide = Signal()

    def __init__(self,navigationController,liveController,is_for_wellplate=False):
        QObject.__init__(self)
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
        # self.slidePositionControlWorker.finished.connect(self.threadFinished,type=Qt.BlockingQueuedConnection)
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
        # self.slidePositionControlWorker.finished.connect(self.threadFinished,type=Qt.BlockingQueuedConnection)
        # start the thread
        print('before thread.start()')
        self.thread.start()
        self.signal_clear_slide.emit()

    def slot_stop_live(self):
        self.liveController.stop_live()

    def slot_resume_live(self):
        self.liveController.start_live()

    # def threadFinished(self):
    # 	print('========= threadFinished ========= ')

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
        # self.navigationController.move_z_usteps(-z_af_offset_usteps) # combine with the back and forth maneuver below
        # self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        # can be moved to the firmware
        if self.navigationController.get_pid_control_flag(2) is False:
            _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
            self.navigationController.move_z_usteps(-_usteps_to_clear_backlash-z_af_offset_usteps)
            self.wait_till_operation_is_completed()
            self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
            self.wait_till_operation_is_completed()
        else:
            self.navigationController.move_z_usteps(-z_af_offset_usteps)
            self.wait_till_operation_is_completed()

        steps_moved = 0
        for i in range(self.N):
            self.navigationController.move_z_usteps(self.deltaZ_usteps)
            self.wait_till_operation_is_completed()
            steps_moved = steps_moved + 1
            # trigger acquisition (including turning on the illumination) and read frame
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                self.liveController.turn_on_illumination()
                self.wait_till_operation_is_completed()
                self.camera.send_trigger()
                image = self.camera.read_frame()
            elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                if 'Fluorescence' in config.name and ENABLE_NL5 and NL5_USE_DOUT:
                    self.camera.image_is_ready = False # to remove
                    self.microscope.nl5.start_acquisition()
                    image = self.camera.read_frame(reset_image_ready_flag=False)
                else:
                    self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
                    image = self.camera.read_frame()
            if image is None:
                continue
            # tunr of the illumination if using software trigger
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                self.liveController.turn_off_illumination()
            
            image = utils.rotate_and_flip_image(image,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)
            self.image_to_display.emit(image)
            image = utils.crop_image(image,self.crop_width,self.crop_height)
            #image_to_display = utils.crop_image(image,round(self.crop_width* self.liveController.display_resolution_scaling), round(self.crop_height* self.liveController.display_resolution_scaling))

            QApplication.processEvents()
            timestamp_0 = time.time()
            focus_measure = utils.calculate_focus_measure(image,FOCUS_MEASURE_OPERATOR)
            timestamp_1 = time.time()
            print('             calculating focus measure took ' + str(timestamp_1-timestamp_0) + ' second')
            focus_measure_vs_z[i] = focus_measure
            print(i,focus_measure)
            focus_measure_max = max(focus_measure, focus_measure_max)
            if focus_measure < focus_measure_max*AF.STOP_THRESHOLD:
                break

        QApplication.processEvents()

        # move to the starting location
        # self.navigationController.move_z_usteps(-steps_moved*self.deltaZ_usteps) # combine with the back and forth maneuver below
        # self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        if self.navigationController.get_pid_control_flag(2) is False:
            _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
            self.navigationController.move_z_usteps(-_usteps_to_clear_backlash-steps_moved*self.deltaZ_usteps)
            # determine the in-focus position
            idx_in_focus = focus_measure_vs_z.index(max(focus_measure_vs_z))
            self.wait_till_operation_is_completed()
            self.navigationController.move_z_usteps(_usteps_to_clear_backlash+(idx_in_focus+1)*self.deltaZ_usteps)
            self.wait_till_operation_is_completed()
        else:
            # determine the in-focus position
            idx_in_focus = focus_measure_vs_z.index(max(focus_measure_vs_z))
            self.navigationController.move_z_usteps((idx_in_focus+1)*self.deltaZ_usteps-steps_moved*self.deltaZ_usteps)
            self.wait_till_operation_is_completed()

        QApplication.processEvents()

        # move to the calculated in-focus position
        # self.navigationController.move_z_usteps(idx_in_focus*self.deltaZ_usteps)
        # self.wait_till_operation_is_completed() # combine with the movement above
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
        self.focus_map_coords = []
        self.use_focus_map = False

    def set_N(self,N):
        self.N = N

    def set_deltaZ(self,deltaZ_um):
        mm_per_ustep_Z = SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        self.deltaZ = deltaZ_um/1000
        self.deltaZ_usteps = round((deltaZ_um/1000)/mm_per_ustep_Z)

    def set_crop(self,crop_width,crop_height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def autofocus(self, focus_map_override=False):
        if self.use_focus_map and (not focus_map_override):
            self.autofocus_in_progress = True
            self.navigationController.microcontroller.wait_till_operation_is_completed()
            x = self.navigationController.x_pos_mm
            y = self.navigationController.y_pos_mm
            
            # z here is in mm because that's how the navigation controller stores it
            target_z = utils.interpolate_plane(*self.focus_map_coords[:3], (x,y))
            print(f"Interpolated target z as {target_z} mm from focus map, moving there.")
            self.navigationController.move_z_to(target_z)
            self.navigationController.microcontroller.wait_till_operation_is_completed()
            self.autofocus_in_progress = False
            self.autofocusFinished.emit()
            return
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
            self.camera.enable_callback()
        
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
        self.image_to_display.emit(image)

    def wait_till_autofocus_has_completed(self):
        while self.autofocus_in_progress == True:
            QApplication.processEvents()
            time.sleep(0.005)
        print('autofocus wait has completed, exit wait')

    def set_focus_map_use(self, enable):
        if not enable:
            print("Disabling focus map.")
            self.use_focus_map = False
            return
        if len(self.focus_map_coords) < 3:
            print("Not enough coordinates (less than 3) for focus map generation, disabling focus map.")
            self.use_focus_map = False
            return
        x1,y1,_ = self.focus_map_coords[0]
        x2,y2,_ = self.focus_map_coords[1]
        x3,y3,_ = self.focus_map_coords[2]

        detT = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if detT == 0:
            print("Your 3 x-y coordinates are linear, cannot use to interpolate, disabling focus map.")
            self.use_focus_map = False
            return

        if enable:
            print("Enabling focus map.")
            self.use_focus_map = True

    def clear_focus_map(self):
        self.focus_map_coords = []
        self.set_focus_map_use(False)

    def gen_focus_map(self, coord1,coord2,coord3):
        """
        Navigate to 3 coordinates and get your focus-map coordinates
        by autofocusing there and saving the z-values.
        :param coord1-3: Tuples of (x,y) values, coordinates in mm.
        :raise: ValueError if coordinates are all on the same line
        """
        x1,y1 = coord1
        x2,y2 = coord2
        x3,y3 = coord3
        detT = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if detT == 0:
            raise ValueError("Your 3 x-y coordinates are linear")
        
        self.focus_map_coords = []

        for coord in [coord1,coord2,coord3]:
            print(f"Navigating to coordinates ({coord[0]},{coord[1]}) to sample for focus map")
            self.navigationController.move_to(coord[0],coord[1])
            self.navigationController.microcontroller.wait_till_operation_is_completed()
            print("Autofocusing")
            self.autofocus(True)
            self.wait_till_autofocus_has_completed()
            #self.navigationController.microcontroller.wait_till_operation_is_completed()
            x = self.navigationController.x_pos_mm
            y = self.navigationController.y_pos_mm
            z = self.navigationController.z_pos_mm
            print(f"Adding coordinates ({x},{y},{z}) to focus map")
            self.focus_map_coords.append((x,y,z))

        print("Generated focus map.")

    def add_current_coords_to_focus_map(self):
        if len(self.focus_map_coords) >= 3:
            print("Replacing last coordinate on focus map.")
        self.navigationController.microcontroller.wait_till_operation_is_completed()
        print("Autofocusing")
        self.autofocus(True)
        self.wait_till_autofocus_has_completed()
        #self.navigationController.microcontroller.wait_till_operation_is_completed()
        x = self.navigationController.x_pos_mm
        y = self.navigationController.y_pos_mm
        z = self.navigationController.z_pos_mm
        if len(self.focus_map_coords) >= 2:
            x1,y1,_ = self.focus_map_coords[0]
            x2,y2,_ = self.focus_map_coords[1]
            x3 = x
            y3 = y

            detT = (y2-y3) * (x1-x3) + (x3-x2) * (y1-y3)
            if detT == 0:
                raise ValueError("Your 3 x-y coordinates are linear. Navigate to a different coordinate or clear and try again.")
        if len(self.focus_map_coords) >= 3:
            self.focus_map_coords.pop()
        self.focus_map_coords.append((x,y,z))
        print(f"Added triple ({x},{y},{z}) to focus map")


class MultiPointWorker(QObject):

    finished = Signal()
    image_to_display = Signal(np.ndarray)
    spectrum_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    image_to_display_tiled_preview = Signal(np.ndarray)
    signal_current_configuration = Signal(Configuration)
    signal_register_current_fov = Signal(float,float)
    signal_detection_stats = Signal(object)
    signal_z_piezo_um = Signal(float)
    napari_rtp_layers_update = Signal(np.ndarray, str)
    napari_layers_update = Signal(np.ndarray, int, int, int, str)
    napari_layers_init = Signal(int, int, object)
    signal_update_stats = Signal(object)

    def __init__(self,multiPointController):
        QObject.__init__(self)
        self.multiPointController = multiPointController

        self.signal_update_stats.connect(self.update_stats)
        self.start_time = 0
        self.processingHandler = multiPointController.processingHandler
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
        self.use_piezo = self.multiPointController.use_piezo
        self.detection_stats = {}
        self.async_detection_stats = {}

        self.timestamp_acquisition_started = self.multiPointController.timestamp_acquisition_started
        self.time_point = 0

        self.microscope = self.multiPointController.parent
        try:
            self.model = self.microscope.segmentation_model
        except:
            pass
        self.crop = SEGMENTATION_CROP

        # hard-coded model initialization
        #model_path = 'models/m2unet_model_flat_erode1_wdecay5_smallbatch/laptop-model_4000_11.engine'
        self.t_dpc = []
        self.t_inf = []
        self.t_over=[]

        self.tiled_preview = None
        

    def update_stats(self, new_stats):
        for k in new_stats.keys():
            try:
                self.detection_stats[k]+=new_stats[k]
            except:
                self.detection_stats[k] = 0
                self.detection_stats[k]+=new_stats[k]
        if "Total RBC" in self.detection_stats and "Total Positives" in self.detection_stats:
            self.detection_stats["Positives per 5M RBC"] = 5e6*(self.detection_stats["Total Positives"]/self.detection_stats["Total RBC"])
        self.signal_detection_stats.emit(self.detection_stats)

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
        self.processingHandler.processing_queue.join()
        self.processingHandler.upload_queue.join()
        elapsed_time = time.perf_counter_ns()-self.start_time
        print("Time taken for acquisition/processing: "+str(elapsed_time/10**9))
        self.finished.emit()

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

        slide_path = os.path.join(self.base_path, self.experiment_ID)

        # create a dataframe to save coordinates
        if IS_HCS:
            if self.use_piezo:
                self.coordinates_pd = pd.DataFrame(columns = ['well', 'i', 'j', 'k', 'x (mm)', 'y (mm)', 'z (um)', 'z_piezo (um)', 'time'])
            else:
                self.coordinates_pd = pd.DataFrame(columns = ['well', 'i', 'j', 'k', 'x (mm)', 'y (mm)', 'z (um)', 'time'])
        else:
            if self.use_piezo:
                self.coordinates_pd = pd.DataFrame(columns = ['i', 'j', 'k', 'x (mm)', 'y (mm)', 'z (um)', 'z_piezo (um)', 'time'])
            else:
                self.coordinates_pd = pd.DataFrame(columns = ['i', 'j', 'k', 'x (mm)', 'y (mm)', 'z (um)', 'time'])

        n_regions = len(self.scan_coordinates_mm)

        for coordinate_id in range(n_regions):
            coordiante_mm = self.scan_coordinates_mm[coordinate_id]         
            if self.scan_coordinates_name is None:
                # flexible scan, use a sequencial ID
                coordinate_name = str(coordinate_id)
            else:
                coordinate_name = self.scan_coordinates_name[coordinate_id]
            
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
                        if self.navigationController.get_pid_control_flag(2) is False:
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

            if USE_NAPARI_FOR_MULTIPOINT or USE_NAPARI_FOR_TILED_DISPLAY:
                init_napari_layers = False

            # reset piezo to home position
            if self.use_piezo:
                self.z_piezo_um = OBJECTIVE_PIEZO_HOME_UM
                dac = int(65535 * (self.z_piezo_um / OBJECTIVE_PIEZO_RANGE_UM))
                self.navigationController.microcontroller.analog_write_onboard_DAC(7, dac)
                if self.liveController.trigger_mode == TriggerMode.SOFTWARE: # for hardware trigger, delay is in waiting for the last row to start exposure
                    time.sleep(MULTIPOINT_PIEZO_DELAY_MS/1000)
                if MULTIPOINT_PIEZO_UPDATE_DISPLAY:
                    self.signal_z_piezo_um.emit(self.z_piezo_um)

            # along y
            for i in range(self.NY):

                self.FOV_counter = 0 # for AF, so that AF at the beginning of each new row

                # along x
                for j in range(self.NX):

                    if RUN_CUSTOM_MULTIPOINT and "multipoint_custom_script_entry" in globals():

                        print('run custom multipoint')
                        multipoint_custom_script_entry(self,self.time_point,current_path,coordinate_id,coordinate_name,i,j)

                    else:

                        # autofocus
                        if self.do_reflection_af == False:
                            # contrast-based AF; perform AF only if when not taking z stack or doing z stack from center
                            if ( (self.NZ == 1) or Z_STACKING_CONFIG == 'FROM CENTER' ) and (self.do_autofocus) and (self.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
                            # temporary: replace the above line with the line below to AF every FOV
                            # if (self.NZ == 1) and (self.do_autofocus):
                                configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                                config_AF = next((config for config in self.configurationManager.configurations if config.name == configuration_name_AF))
                                self.signal_current_configuration.emit(config_AF)
                                if (self.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0) or self.autofocusController.use_focus_map:
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
                            if self.microscope.laserAutofocusController.is_initialized==False:
                                # initialize the reflection AF
                                self.microscope.laserAutofocusController.initialize_auto()
                                # do contrast AF for the first FOV (if contrast AF box is checked)
                                if self.do_autofocus and ( (self.NZ == 1) or Z_STACKING_CONFIG == 'FROM CENTER' ) :
                                    configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                                    config_AF = next((config for config in self.configurationManager.configurations if config.name == configuration_name_AF))
                                    self.signal_current_configuration.emit(config_AF)
                                    self.autofocusController.autofocus()
                                    self.autofocusController.wait_till_autofocus_has_completed()
                                # set the current plane as reference
                                self.microscope.laserAutofocusController.set_reference()
                            else:
                                try:
                                    if self.navigationController.get_pid_control_flag(2) is False:
                                        self.microscope.laserAutofocusController.move_to_target(0)
                                        self.microscope.laserAutofocusController.move_to_target(0) # for stepper in open loop mode, repeat the operation to counter backlash
                                    else:
                                        self.microscope.laserAutofocusController.move_to_target(0)
                                except:
                                    file_ID = coordinate_name + str(i) + '_' + str(j if self.x_scan_direction==1 else self.NX-1-j)
                                    saving_path = os.path.join(current_path, file_ID + '_focus_camera.bmp')
                                    iio.imwrite(saving_path,self.microscope.laserAutofocusController.image) 
                                    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! laser AF failed !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')

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
                            
                            # Ensure that i/y-indexing is always top to bottom
                            sgn_i = -1 if self.deltaY >= 0 else 1
                            if INVERTED_OBJECTIVE: # to do
                                sgn_i = -sgn_i
                            sgn_j = self.x_scan_direction if self.deltaX >= 0 else -self.x_scan_direction

                            real_i = self.NY-1-i if sgn_i == -1 else i
                            real_j = j if sgn_j == 1 else self.NX-1-j

                            file_ID = coordinate_name + str(real_i) + '_' + str(real_j) + '_' + str(k)
                            # metadata = dict(x = self.navigationController.x_pos_mm, y = self.navigationController.y_pos_mm, z = self.navigationController.z_pos_mm)
                            # metadata = json.dumps(metadata)

                            # laser af characterization mode
                            if LASER_AF_CHARACTERIZATION_MODE:
                                image = self.microscope.laserAutofocusController.get_image()
                                saving_path = os.path.join(current_path, file_ID + '_laser af camera' + '.bmp')
                                iio.imwrite(saving_path,image)

                            # I_fluorescence = None
                            # I_left = None
                            # I_right = None

                            # dpc_L = None
                            # dpc_R = None
                            
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

                                if 'USB Spectrometer' not in config.name and 'RGB' not in config.name:
                                    # update the current configuration
                                    self.signal_current_configuration.emit(config)
                                    self.wait_till_operation_is_completed()
                                    # trigger acquisition (including turning on the illumination) and read frame
                                    if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                        self.liveController.turn_on_illumination()
                                        self.wait_till_operation_is_completed()
                                        self.camera.send_trigger()
                                        image = self.camera.read_frame()
                                    elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                                        if 'Fluorescence' in config.name and ENABLE_NL5 and NL5_USE_DOUT:
                                            self.camera.image_is_ready = False # to remove
                                            self.microscope.nl5.start_acquisition()
                                            image = self.camera.read_frame(reset_image_ready_flag=False)
                                        else:
                                            self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
                                            image = self.camera.read_frame()
                                    
                                    if image is None:
                                        print('self.camera.read_frame() returned None')
                                        continue
                                    # tunr of the illumination if using software trigger
                                    if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                        self.liveController.turn_off_illumination()

                                    # process the image -  @@@ to move to camera
                                    image = utils.crop_image(image,self.crop_width,self.crop_height)
                                    image = utils.rotate_and_flip_image(image,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)
                                    # self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))

                                    image_to_display = utils.crop_image(image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling))
                                    self.image_to_display.emit(image_to_display)
                                    self.image_to_display_multi.emit(image_to_display,config.illumination_source)

                                    if image.dtype == np.uint16:
                                        saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.tiff')
                                        if self.camera.is_color:
                                            if 'BF LED matrix' in config.name:
                                                if MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
                                                    image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                                elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
                                                    image = image[:,:,1]
                                        iio.imwrite(saving_path,image)
                                    else:
                                        saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.' + Acquisition.IMAGE_FORMAT)
                                        if self.camera.is_color:
                                            if 'BF LED matrix' in config.name:
                                                if MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
                                                    image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                                elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
                                                    image = image[:,:,1]
                                        # if 'Fluorescence 405' not in config.name:
                                        #     image = np.stack((image,) * 3, axis=-1) #simulation RGB
                                        iio.imwrite(saving_path,image)

                                    if USE_NAPARI_FOR_MULTIPOINT or USE_NAPARI_FOR_TILED_DISPLAY:
                                        if not init_napari_layers:
                                            print("init napari layers")
                                            init_napari_layers = True
                                            self.napari_layers_init.emit(image.shape[0],image.shape[1], image.dtype)
                                        self.napari_layers_update.emit(image, real_i, real_j, k, config.name)

                                    current_round_images[config.name] = np.copy(image)

                                    # dpc generation
                                    keys_to_check = ['BF LED matrix left half', 'BF LED matrix right half', 'BF LED matrix top half', 'BF LED matrix bottom half']
                                    if all(key in current_round_images for key in keys_to_check):
                                        # generate dpc
                                        pass

                                    # RGB generation
                                    keys_to_check = ['BF LED matrix full_R', 'BF LED matrix full_G', 'BF LED matrix full_B']
                                    if all(key in current_round_images for key in keys_to_check):
                                        print('constructing RGB image')
                                        print(current_round_images['BF LED matrix full_R'].dtype)
                                        size = current_round_images['BF LED matrix full_R'].shape
                                        rgb_image = np.zeros((*size, 3),dtype=current_round_images['BF LED matrix full_R'].dtype)
                                        print(rgb_image.shape)
                                        rgb_image[:, :, 0] = current_round_images['BF LED matrix full_R']
                                        rgb_image[:, :, 1] = current_round_images['BF LED matrix full_G']
                                        rgb_image[:, :, 2] = current_round_images['BF LED matrix full_B']

                                        # send image to display
                                        image_to_display = utils.crop_image(rgb_image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling))

                                        # write the image
                                        if len(rgb_image.shape) == 3:
                                            print('writing RGB image')
                                            if rgb_image.dtype == np.uint16:
                                                iio.imwrite(os.path.join(current_path, file_ID + '_BF_LED_matrix_full_RGB.tiff'), rgb_image)
                                            else:
                                                iio.imwrite(os.path.join(current_path, file_ID + '_BF_LED_matrix_full_RGB.' + Acquisition.IMAGE_FORMAT),rgb_image)

                                    # if config.name == 'BF LED matrix left half':
                                    #     I_left = np.copy(image)
                                    #     dpc_L = I_left
                                    # elif config.name == 'BF LED matrix right half':
                                    #     I_right = np.copy(image)
                                    #     dpc_R = I_right
                                    # elif config.name == 'Fluorescence 405 nm Ex':
                                    #     I_fluorescence = np.copy(image)

                                    QApplication.processEvents()

                                # RGB
                                elif 'RGB' in config.name:
                                    # go through the channels
                                    channels = ['BF LED matrix full_R', 'BF LED matrix full_G', 'BF LED matrix full_B']
                                    images = {}

                                    for config_ in self.configurationManager.configurations:
                                        if config_.name in channels:
                                            # update the current configuration
                                            self.signal_current_configuration.emit(config_)
                                            self.wait_till_operation_is_completed()

                                            # trigger acquisition (including turning on the illumination)
                                            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                                self.liveController.turn_on_illumination()
                                                self.wait_till_operation_is_completed()
                                                self.camera.send_trigger()
                                            elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                                                self.microcontroller.send_hardware_trigger(control_illumination=True, illumination_on_time_us=self.camera.exposure_time * 1000)

                                            # read camera frame
                                            image = self.camera.read_frame()
                                            if image is None:
                                                print('self.camera.read_frame() returned None')
                                                continue

                                            # turn off the illumination if using software trigger
                                            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                                self.liveController.turn_off_illumination()

                                            # process the image  -  @@@ to move to camera
                                            image = utils.crop_image(image, self.crop_width, self.crop_height)
                                            image = utils.rotate_and_flip_image(image, rotate_image_angle=self.camera.rotate_image_angle, flip_image=self.camera.flip_image)

                                            # add the image to dictionary
                                            images[config_.name] = np.copy(image)

                                    # Check if the image is RGB or monochrome
                                    i_size = images['BF LED matrix full_R'].shape
                                    i_dtype = images['BF LED matrix full_R'].dtype

                                    if len(i_size) == 3:
                                        # If already RGB, write and emit individual channels
                                        print('writing R, G, B channels')

                                        for channel in channels:
                                            image_to_display = utils.crop_image(images[channel], round(self.crop_width * self.display_resolution_scaling), round(self.crop_height * self.display_resolution_scaling))
                                            self.image_to_display.emit(image_to_display)
                                            self.image_to_display_multi.emit(image_to_display, config.illumination_source)

                                            if USE_NAPARI_FOR_MULTIPOINT or USE_NAPARI_FOR_TILED_DISPLAY:
                                                if not init_napari_layers:
                                                    print(f"init napari {channel} layer")
                                                    init_napari_layers = True
                                                    self.napari_layers_init.emit(i_size[0], i_size[1], i_dtype)
                                                self.napari_layers_update.emit(images[channel], real_i, real_j, k, config.name)

                                            file_name = file_ID + '_' + channel.replace(' ', '_') + ('.tiff' if i_dtype == np.uint16 else '.' + Acquisition.IMAGE_FORMAT)
                                            iio.imwrite(os.path.join(current_path, file_name), images[channel])

                                    else:
                                        # If monochrome, reconstruct RGB image
                                        print('constructing RGB image')

                                        rgb_image = np.zeros((*i_size, 3), dtype=i_dtype)
                                        rgb_image[:, :, 0] = images['BF LED matrix full_R']
                                        rgb_image[:, :, 1] = images['BF LED matrix full_G']
                                        rgb_image[:, :, 2] = images['BF LED matrix full_B']

                                        # send image to display
                                        image_to_display = utils.crop_image(rgb_image, round(self.crop_width * self.display_resolution_scaling), round(self.crop_height * self.display_resolution_scaling))
                                        self.image_to_display.emit(image_to_display)
                                        self.image_to_display_multi.emit(image_to_display, config.illumination_source)

                                        if USE_NAPARI_FOR_MULTIPOINT or USE_NAPARI_FOR_TILED_DISPLAY:
                                            if not init_napari_layers:
                                                print("init napari rgb layer")
                                                init_napari_layers = True
                                                print(rgb_image.dtype)
                                                self.napari_layers_init.emit(rgb_image.shape[0], rgb_image.shape[1], rgb_image.dtype)
                                            self.napari_layers_update.emit(rgb_image, real_i, real_j, k, config.name)

                                        # write the RGB image
                                        print('writing RGB image')
                                        file_name = file_ID + '_BF_LED_matrix_full_RGB' + ('.tiff' if rgb_image.dtype == np.uint16 else '.' + Acquisition.IMAGE_FORMAT)
                                        iio.imwrite(os.path.join(current_path, file_name), rgb_image)

                                # USB spectrometer
                                else:
                                    if self.usb_spectrometer != None:
                                        for l in range(N_SPECTRUM_PER_POINT):
                                            data = self.usb_spectrometer.read_spectrum()
                                            self.spectrum_to_display.emit(data)
                                            saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '_' + str(l) + '.csv')
                                            np.savetxt(saving_path,data,delimiter=',')
                                
                                
                                if config.z_offset is not None: # undo Z offset
                                                                # assume z_offset is in um
                                    if config.z_offset != 0.0:
                                        print("Moving back from Z offset "+str(config.z_offset))
                                        self.navigationController.move_z(-config.z_offset/1000)
                                        self.wait_till_operation_is_completed()
                                        time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

                            # tiled preview
                            if not USE_NAPARI_FOR_TILED_DISPLAY and SHOW_TILED_PREVIEW and 'BF LED matrix left half' in current_round_images:
                                # initialize the variable
                                if self.tiled_preview is None:
                                    size = current_round_images['BF LED matrix left half'].shape
                                    if len(size) == 2:
                                        self.tiled_preview = np.zeros((int(self.NY*size[0]/PRVIEW_DOWNSAMPLE_FACTOR),self.NX*int(size[1]/PRVIEW_DOWNSAMPLE_FACTOR)),dtype=current_round_images['BF LED matrix full'].dtype)
                                    else:
                                        self.tiled_preview = np.zeros((int(self.NY*size[0]/PRVIEW_DOWNSAMPLE_FACTOR),self.NX*int(size[1]/PRVIEW_DOWNSAMPLE_FACTOR),size[2]),dtype=current_round_images['BF LED matrix full'].dtype)
                                # downsample the image
                                I = current_round_images['BF LED matrix left half']
                                width = int(I.shape[1]/PRVIEW_DOWNSAMPLE_FACTOR)
                                height = int(I.shape[0]/PRVIEW_DOWNSAMPLE_FACTOR)
                                I = cv2.resize(I, (width,height), interpolation=cv2.INTER_AREA)
                                # populate the tiled_preview
                                if sgn_j == 1:
                                    self.tiled_preview[(self.NY-i-1)*height:(self.NY-i)*height, j*width:(j+1)*width, ] = I
                                else:
                                    self.tiled_preview[(self.NY-i-1)*height:(self.NY-i)*height, (self.NX-j-1)*width:(self.NX-j)*width, ] = I
                                # emit the result
                                self.image_to_display_tiled_preview.emit(self.tiled_preview)

                            # real time processing 
                            acquired_image_configs = list(current_round_images.keys())
                            if 'BF LED matrix left half' in current_round_images and 'BF LED matrix right half' in current_round_images and 'Fluorescence 405 nm Ex' in current_round_images and self.multiPointController.do_fluorescence_rtp:
                                print("try real time processing")
                                try:
                                    if (self.microscope.model is None) or (self.microscope.device is None) or (self.microscope.classification_th is None) or (self.microscope.dataHandler is None):
                                        raise AttributeError('microscope missing model, device, classification_th, and/or dataHandler')
                                    I_fluorescence = current_round_images['Fluorescence 405 nm Ex']
                                    I_left = current_round_images['BF LED matrix left half']
                                    I_right = current_round_images['BF LED matrix right half']
                                    malaria_rtp(I_fluorescence, I_left, I_right, real_i, real_j, k, self,
                                                classification_test_mode=CLASSIFICATION_TEST_MODE,
                                                sort_during_multipoint=SORT_DURING_MULTIPOINT,
                                                disp_th_during_multipoint=DISP_TH_DURING_MULTIPOINT)
                                except AttributeError as e:
                                    print(repr(e))

                            # add the coordinate of the current location
                            if IS_HCS:
                                if self.use_piezo:
                                    new_row = pd.DataFrame({'well': coordiante_name.replace("_", ""),
                                                            'i':[self.NY-1-i if sgn_i == -1 else i],'j':[j if sgn_j == 1 else self.NX-1-j],'k':[k],
                                                            'x (mm)':[self.navigationController.x_pos_mm],
                                                            'y (mm)':[self.navigationController.y_pos_mm],
                                                            'z (um)':[self.navigationController.z_pos_mm*1000],
                                                            'z_piezo (um)':[self.z_piezo_um-OBJECTIVE_PIEZO_HOME_UM],
                                                            'time':datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')})
                                else:
                                    new_row = pd.DataFrame({'well': coordiante_name.replace("_", ""),
                                                            'i':[self.NY-1-i if sgn_i == -1 else i],'j':[j if sgn_j == 1 else self.NX-1-j],'k':[k],
                                                            'x (mm)':[self.navigationController.x_pos_mm],
                                                            'y (mm)':[self.navigationController.y_pos_mm],
                                                            'z (um)':[self.navigationController.z_pos_mm*1000],
                                                            'time':datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')})
                            else:
                                if self.use_piezo:
                                    new_row = pd.DataFrame({'i':[self.NY-1-i if sgn_i == -1 else i],'j':[j if sgn_j == 1 else self.NX-1-j],'k':[k],
                                                            'x (mm)':[self.navigationController.x_pos_mm],
                                                            'y (mm)':[self.navigationController.y_pos_mm],
                                                            'z (um)':[self.navigationController.z_pos_mm*1000],
                                                            'z_piezo (um)':[self.z_piezo_um-OBJECTIVE_PIEZO_HOME_UM],
                                                            'time':datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')})
                                else:
                                    new_row = pd.DataFrame({'i':[self.NY-1-i if sgn_i == -1 else i],'j':[j if sgn_j == 1 else self.NX-1-j],'k':[k],
                                                            'x (mm)':[self.navigationController.x_pos_mm],
                                                            'y (mm)':[self.navigationController.y_pos_mm],
                                                            'z (um)':[self.navigationController.z_pos_mm*1000],
                                                            'time':datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')})

                            self.coordinates_pd = pd.concat([self.coordinates_pd, new_row], ignore_index=True)

                            # register the current fov in the navigationViewer
                            self.signal_register_current_fov.emit(self.navigationController.x_pos_mm,self.navigationController.y_pos_mm)

                            # check if the acquisition should be aborted
                            if self.multiPointController.abort_acqusition_requested:
                                self.liveController.turn_off_illumination()
                                self.navigationController.move_x_usteps(-self.dx_usteps)
                                self.wait_till_operation_is_completed()
                                self.navigationController.move_y_usteps(-self.dy_usteps)
                                self.wait_till_operation_is_completed()

                                if self.navigationController.get_pid_control_flag(2) is False:
                                    _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                                    self.navigationController.move_z_usteps(-self.dz_usteps-_usteps_to_clear_backlash)
                                    self.wait_till_operation_is_completed()
                                    self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                                    self.wait_till_operation_is_completed()
                                else:
                                    self.navigationController.move_z_usteps(-self.dz_usteps)
                                    self.wait_till_operation_is_completed()

                                self.coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
                                self.navigationController.enable_joystick_button_action = True
                                return

                            if self.NZ > 1:
                                # move z
                                if k < self.NZ - 1:
                                    if self.use_piezo:
                                        self.z_piezo_um += self.deltaZ*1000
                                        dac = int(65535 * (self.z_piezo_um / OBJECTIVE_PIEZO_RANGE_UM))
                                        self.navigationController.microcontroller.analog_write_onboard_DAC(7, dac)
                                        if self.liveController.trigger_mode == TriggerMode.SOFTWARE: # for hardware trigger, delay is in waiting for the last row to start exposure
                                            time.sleep(MULTIPOINT_PIEZO_DELAY_MS/1000)
                                        if MULTIPOINT_PIEZO_UPDATE_DISPLAY:
                                            self.signal_z_piezo_um.emit(self.z_piezo_um)
                                    else:
                                        self.navigationController.move_z_usteps(self.deltaZ_usteps)
                                        self.wait_till_operation_is_completed()
                                        time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
                                        self.dz_usteps = self.dz_usteps + self.deltaZ_usteps

                        if self.NZ > 1:
                            # move z back
                            if self.use_piezo:
                                self.z_piezo_um = OBJECTIVE_PIEZO_HOME_UM
                                dac = int(65535 * (self.z_piezo_um / OBJECTIVE_PIEZO_RANGE_UM))
                                self.navigationController.microcontroller.analog_write_onboard_DAC(7, dac)
                                if self.liveController.trigger_mode == TriggerMode.SOFTWARE: # for hardware trigger, delay is in waiting for the last row to start exposure
                                    time.sleep(MULTIPOINT_PIEZO_DELAY_MS/1000)
                                if MULTIPOINT_PIEZO_UPDATE_DISPLAY:
                                    self.signal_z_piezo_um.emit(self.z_piezo_um)
                            else:
                                _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                                if Z_STACKING_CONFIG == 'FROM CENTER':
                                    if self.navigationController.get_pid_control_flag(2) is False:
                                        _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                                        self.navigationController.move_z_usteps( -self.deltaZ_usteps*(self.NZ-1) + self.deltaZ_usteps*round((self.NZ-1)/2) - _usteps_to_clear_backlash)
                                        self.wait_till_operation_is_completed()
                                        self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                                        self.wait_till_operation_is_completed()
                                    else:
                                        self.navigationController.move_z_usteps( -self.deltaZ_usteps*(self.NZ-1) + self.deltaZ_usteps*round((self.NZ-1)/2) )
                                        self.wait_till_operation_is_completed()
                                    self.dz_usteps = self.dz_usteps - self.deltaZ_usteps*(self.NZ-1) + self.deltaZ_usteps*round((self.NZ-1)/2)
                                else:
                                    if self.navigationController.get_pid_control_flag(2) is False:
                                        _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                                        self.navigationController.move_z_usteps(-self.deltaZ_usteps*(self.NZ-1) - _usteps_to_clear_backlash)
                                        self.wait_till_operation_is_completed()
                                        self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                                        self.wait_till_operation_is_completed()
                                    else:
                                        self.navigationController.move_z_usteps(-self.deltaZ_usteps*(self.NZ-1))
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

            if SHOW_TILED_PREVIEW and IS_HCS:
                self.navigationController.keep_scan_begin_position(self.navigationController.x_pos_mm, self.navigationController.y_pos_mm)

            if n_regions == 1:
                # only move to the start position if there's only one region in the scan
                if self.NY > 1:
                    # move y back
                    self.navigationController.move_y_usteps(-self.deltaY_usteps*(self.NY-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
                    self.dy_usteps = self.dy_usteps - self.deltaY_usteps*(self.NY-1)
                
                if SHOW_TILED_PREVIEW and not IS_HCS:
                    self.navigationController.keep_scan_begin_position(self.navigationController.x_pos_mm, self.navigationController.y_pos_mm)

                # move x back at the end of the scan
                if self.x_scan_direction == -1:
                    self.navigationController.move_x_usteps(-self.deltaX_usteps*(self.NX-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)

                # move z back
                if self.navigationController.get_pid_control_flag(2) is False:
                    _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                    self.navigationController.microcontroller.move_z_to_usteps(z_pos - STAGE_MOVEMENT_SIGN_Z*_usteps_to_clear_backlash)
                    self.wait_till_operation_is_completed()
                    self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                    self.wait_till_operation_is_completed()
                else:
                    self.navigationController.microcontroller.move_z_to_usteps(z_pos)
                    self.wait_till_operation_is_completed()

        # finished region scan
        self.coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
        self.navigationController.enable_joystick_button_action = True
        print(time.time())
        print(time.time()-start)

class MultiPointController(QObject):

    acquisitionFinished = Signal()
    image_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    image_to_display_tiled_preview = Signal(np.ndarray)
    spectrum_to_display = Signal(np.ndarray)
    signal_current_configuration = Signal(Configuration)
    signal_register_current_fov = Signal(float,float)
    detection_stats = Signal(object)
    signal_stitcher = Signal(str)
    napari_rtp_layers_update = Signal(np.ndarray, str)
    napari_layers_update = Signal(np.ndarray, int, int, int, str)
    napari_layers_init = Signal(int, int, object)
    signal_z_piezo_um = Signal(float)

    def __init__(self,camera,navigationController,liveController,autofocusController,configurationManager,usb_spectrometer=None,scanCoordinates=None,parent=None):
        QObject.__init__(self)

        self.camera = camera
        self.processingHandler = ProcessingHandler()
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
        self.gen_focus_map = False
        self.focus_map_storage = []
        self.already_using_fmap = False
        self.do_segmentation = False
        self.do_fluorescence_rtp = DO_FLUORESCENCE_RTP
        self.crop_width = Acquisition.CROP_WIDTH
        self.crop_height = Acquisition.CROP_HEIGHT
        self.display_resolution_scaling = Acquisition.IMAGE_DISPLAY_SCALING_FACTOR
        self.counter = 0
        self.experiment_ID = None
        self.base_path = None
        self.use_piezo = MULTIPOINT_USE_PIEZO_FOR_ZSTACKS #TODO: change to false and get value from widget
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
    def set_gen_focus_map_flag(self, flag):
        self.gen_focus_map = flag
        if not flag:
            self.autofocusController.set_focus_map_use(False)
    def set_stitch_tiles_flag(self, flag):
        self.do_stitch_tiles = flag
    def set_segmentation_flag(self, flag):
        self.do_segmentation = flag
    def set_fluorescence_rtp_flag(self, flag):
        self.do_fluorescence_rtp = flag
    def set_crop(self,crop_width,height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def set_base_path(self,path):
        self.base_path = path

    def start_new_experiment(self,experiment_ID): # @@@ to do: change name to prepare_folder_for_new_experiment
        # generate unique experiment ID
        self.experiment_ID = experiment_ID.replace(' ','_') + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')
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
            try:
                objective_info = OBJECTIVES[DEFAULT_OBJECTIVE]
                acquisition_parameters['objective'] = {}
                for k in objective_info.keys():
                    acquisition_parameters['objective'][k] = objective_info[k]
                acquisition_parameters['objective']['name']=DEFAULT_OBJECTIVE
            except:
                pass
        acquisition_parameters['sensor_pixel_size_um'] = CAMERA_PIXEL_SIZE_UM[CAMERA_SENSOR]
        acquisition_parameters['tube_lens_mm'] = TUBE_LENS_MM
        f = open(os.path.join(self.base_path,self.experiment_ID)+"/acquisition parameters.json","w")
        f.write(json.dumps(acquisition_parameters))
        f.close()

    def set_selected_configurations(self, selected_configurations_name):
        self.selected_configurations = []
        for configuration_name in selected_configurations_name:
            self.selected_configurations.append(next((config for config in self.configurationManager.configurations if config.name == configuration_name)))
        
    def run_acquisition(self, location_list=None): # @@@ to do: change name to run_experiment
        print('start multipoint')
        print(str(self.Nt) + '_' + str(self.NX) + '_' + str(self.NY) + '_' + str(self.NZ))

        if location_list is not None:
            print(location_list)
            self.location_list = location_list
        else:
            self.location_list = None

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

        # set current tabs
        if self.parent is not None:
            configs = [config.name for config in self.selected_configurations]
            print(configs)
            if DO_FLUORESCENCE_RTP and 'BF LED matrix left half' in configs and 'BF LED matrix right half' in configs and 'Fluorescence 405 nm Ex' in configs:
                self.parent.recordTabWidget.setCurrentWidget(self.parent.statsDisplayWidget)
                if USE_NAPARI_FOR_MULTIPOINT:
                    self.parent.imageDisplayTabs.setCurrentWidget(self.parent.napariRTPWidget)
                else:
                    self.parent.imageDisplayTabs.setCurrentWidget(self.parent.imageArrayDisplayWindow.widget)
            elif USE_NAPARI_FOR_TILED_DISPLAY:
                self.parent.imageDisplayTabs.setCurrentWidget(self.parent.napariTiledDisplayWidget)
            else:
                self.parent.imageDisplayTabs.setCurrentIndex(0)

        # run the acquisition
        self.timestamp_acquisition_started = time.time()

        if SHOW_TILED_PREVIEW:
            self.navigationController.keep_scan_begin_position(self.navigationController.x_pos_mm, self.navigationController.y_pos_mm)

        # create a QThread object
        if self.gen_focus_map and not self.do_reflection_af:
            print("Generating focus map for multipoint grid")
            starting_x_mm = self.navigationController.x_pos_mm
            starting_y_mm = self.navigationController.y_pos_mm
            fmap_Nx = max(2,self.NX-1)
            fmap_Ny = max(2,self.NY-1)
            fmap_dx = self.deltaX
            fmap_dy = self.deltaY
            if abs(fmap_dx) < 0.1 and fmap_dx != 0.0:
                fmap_dx = 0.1*fmap_dx/(abs(fmap_dx))
            elif fmap_dx == 0.0:
                fmap_dx = 0.1
            if abs(fmap_dy) < 0.1 and fmap_dy != 0.0:
                 fmap_dy = 0.1*fmap_dy/(abs(fmap_dy))
            elif fmap_dy == 0.0:
                fmap_dy = 0.1
            try:
                self.focus_map_storage = []
                self.already_using_fmap = self.autofocusController.use_focus_map
                for x,y,z in self.autofocusController.focus_map_coords:
                    self.focus_map_storage.append((x,y,z))
                coord1 = (starting_x_mm, starting_y_mm)
                coord2 = (starting_x_mm+fmap_Nx*fmap_dx,starting_y_mm)
                coord3 = (starting_x_mm,starting_y_mm+fmap_Ny*fmap_dy)
                self.autofocusController.gen_focus_map(coord1, coord2, coord3)
                self.autofocusController.set_focus_map_use(True)
                self.navigationController.move_to(starting_x_mm, starting_y_mm)
                self.navigationController.microcontroller.wait_till_operation_is_completed()
            except ValueError:
                print("Invalid coordinates for focus map, aborting.")
                return

        self.thread = QThread()
        # create a worker object
        self.processingHandler.start_processing()
        self.processingHandler.start_uploading()
        self.multiPointWorker = MultiPointWorker(self)
        # move the worker to the thread
        self.multiPointWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.multiPointWorker.run)
        self.multiPointWorker.signal_detection_stats.connect(self.slot_detection_stats)
        self.multiPointWorker.finished.connect(self._on_acquisition_completed)
        self.multiPointWorker.finished.connect(self.multiPointWorker.deleteLater)
        self.multiPointWorker.finished.connect(self.thread.quit)
        self.multiPointWorker.image_to_display.connect(self.slot_image_to_display)
        self.multiPointWorker.image_to_display_multi.connect(self.slot_image_to_display_multi)
        self.multiPointWorker.image_to_display_tiled_preview.connect(self.slot_image_to_display_tiled_preview)
        self.multiPointWorker.spectrum_to_display.connect(self.slot_spectrum_to_display)
        self.multiPointWorker.signal_current_configuration.connect(self.slot_current_configuration,type=Qt.BlockingQueuedConnection)
        self.multiPointWorker.signal_register_current_fov.connect(self.slot_register_current_fov)
        self.multiPointWorker.napari_layers_init.connect(self.slot_napari_layers_init)
        self.multiPointWorker.napari_rtp_layers_update.connect(self.slot_napari_rtp_layers_update)
        self.multiPointWorker.napari_layers_update.connect(self.slot_napari_layers_update)
        self.multiPointWorker.signal_z_piezo_um.connect(self.slot_z_piezo_um)
        # self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.thread.quit)
        # start the thread
        self.thread.start()

    def _on_acquisition_completed(self):
        # restore the previous selected mode
        if self.gen_focus_map:
            self.autofocusController.clear_focus_map()
            for x,y,z in self.focus_map_storage:
                self.autofocusController.focus_map_coords.append((x,y,z))
            self.autofocusController.use_focus_map = self.already_using_fmap
        self.signal_current_configuration.emit(self.configuration_before_running_multipoint)

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
        self.processingHandler.end_processing()
        if self.parent is not None:
            try:
                self.parent.dataHandler.set_number_of_images_per_page(self.old_images_per_page)
                self.parent.dataHandler.sort('Sort by prediction score')
                self.parent.dataHandler.signal_populate_page0.emit()
            except:
                pass
        self.acquisitionFinished.emit()
        #self.signal_stitcher.emit("/Users/soham/Documents/cephla/scan-data/5x5_4_channels_2024-05-19_00-45-46.094077")
        self.signal_stitcher.emit(os.path.join(self.base_path,self.experiment_ID))
        QApplication.processEvents()

    def request_abort_aquisition(self):
        self.abort_acqusition_requested = True

    def slot_detection_stats(self, stats):
        self.detection_stats.emit(stats)

    def slot_image_to_display(self,image):
        self.image_to_display.emit(image)

    def slot_image_to_display_tiled_preview(self,image):
        self.image_to_display_tiled_preview.emit(image)

    def slot_spectrum_to_display(self,data):
        self.spectrum_to_display.emit(data)

    def slot_image_to_display_multi(self,image,illumination_source):
        self.image_to_display_multi.emit(image,illumination_source)

    def slot_current_configuration(self,configuration):
        self.signal_current_configuration.emit(configuration)

    def slot_register_current_fov(self,x_mm,y_mm):
        self.signal_register_current_fov.emit(x_mm,y_mm)

    def slot_napari_rtp_layers_update(self, image, channel):
        self.napari_rtp_layers_update.emit(image, channel)

    def slot_napari_layers_update(self, image, i, j, k, channel):
        self.napari_layers_update.emit(image, i, j, k, channel)

    def slot_napari_layers_init(self, image_height, image_width, dtype):
        self.napari_layers_init.emit(image_height, image_width, dtype)

    def slot_z_piezo_um(self, displacement_um):
        self.signal_z_piezo_um.emit(displacement_um)


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
            self.camera.disable_callback()
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
            self.camera.enable_callback()
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
        self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')
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
        self.txt_file.write('t0: ' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f') + '\n')
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
                print('tracker: object not found')
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


class Stitcher(Thread, QObject):

    update_progress = Signal(int, int)
    getting_flatfields = Signal()
    starting_stitching = Signal()
    starting_saving = Signal(bool)
    finished_saving = Signal(str, object) 

    def __init__(self, input_folder, output_name='', output_format=".ome.zarr", apply_flatfield=0, use_registration=0, registration_channel=''):
        Thread.__init__(self)
        QObject.__init__(self)
        self.input_folder = input_folder
        self.image_folder = None
        self.output_name = output_name + output_format
        self.apply_flatfield = apply_flatfield
        self.use_registration = use_registration
        if use_registration:
            self.registration_channel = registration_channel

        self.selected_modes = self.extract_selected_modes(self.input_folder)
        self.acquisition_params = self.extract_acquisition_parameters(self.input_folder)
        self.time_points = self.get_time_points(self.input_folder)
        print("timepoints:", self.time_points)
        self.is_reversed = self.determine_directions(self.image_folder) # init: top to bottom, left to right
        print(self.is_reversed)
        self.is_rgb = {}
        self.wells = []
        self.channel_names = []
        self.mono_channel_names = []
        self.channel_colors = []
        self.num_z = self.num_c = 1
        self.num_cols = self.num_rows = 1
        self.input_height = self.input_width = 0
        self.v_shift = self.h_shift = (0,0)
        self.max_x_overlap = self.max_y_overlap = 0
        self.flatfields = {}
        self.stitching_data = {}
        self.stitched_images = None
        self.chunks = None
        self.dtype = np.uint16
        # self.overlap_percent = Acquisition.OVERLAP_PERCENT

    def get_time_points(self, input_folder):
        try: # detects directories named as integers, representing time points.
            time_points = [d for d in os.listdir(input_folder) if os.path.isdir(os.path.join(input_folder, d)) and d.isdigit()]
            time_points.sort(key=int)
            return time_points
        except Exception as e:
            print(f"Error detecting time points: {e}")
            return ['0']

    def extract_selected_modes(self, input_folder):
        try:
            configs_path = os.path.join(input_folder, 'configurations.xml')
            tree = etree.parse(configs_path)
            root = tree.getroot()
            selected_modes = {}
            for mode in root.findall('.//mode'):
                if mode.get('Selected') == '1':
                    mode_id = mode.get('ID')
                    selected_modes[mode_id] = {
                        'Name': mode.get('Name'),
                        'ExposureTime': mode.get('ExposureTime'),
                        'AnalogGain': mode.get('AnalogGain'),
                        'IlluminationSource': mode.get('IlluminationSource'),
                        'IlluminationIntensity': mode.get('IlluminationIntensity')
                    }
            return selected_modes
        except Exception as e:
            print(f"Error reading selected modes: {e}")

    def extract_acquisition_parameters(self, input_folder):
        acquistion_params_path = os.path.join(input_folder, 'acquisition parameters.json')
        with open(acquistion_params_path, 'r') as file:
            acquisition_params = json.load(file)
        return acquisition_params

    def extract_wavelength(self, name):
        # Split the string and find the wavelength number immediately after "Fluorescence"
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]  # Assuming '488 nm Ex' and taking '488'
        for color in ['R', 'G', 'B']:
            if color in parts:
                return color
        return None


    def determine_directions(self, image_folder):
        return {'rows': self.acquisition_params.get("row direction", False), 
                'cols': self.acquisition_params.get("col direction", False), 
                'z-planes': False}
        # coordinates = pd.read_csv(os.path.join(image_folder, 'coordinates.csv'))
        # if IS_WELLPLATE:
        #     try:
        #         first_well = coordinates['well'].unique()[0]
        #         coordinates = coordinates[coordinates['well'] == first_well]
        #     except Exception as e:
        #         print("no coordinates.csv well data:", e)
        
        # i_rev = not coordinates.sort_values(by='i')['y (mm)'].is_monotonic_increasing
        # j_rev = not coordinates.sort_values(by='j')['x (mm)'].is_monotonic_increasing
        # k_rev = not coordinates.sort_values(by='k')['z (um)'].is_monotonic_increasing
        # return {'rows': i_rev, 'cols': j_rev, 'z-planes': k_rev}

    def parse_filenames(self, time_point):
        # Initialize directories and read files
        self.image_folder = os.path.join(self.input_folder, str(time_point))
        # print("processing image folder:", self.image_folder)
        all_files = os.listdir(self.image_folder)
        sorted_input_files = sorted(
            [filename for filename in all_files if filename.endswith((".bmp", ".tiff")) and 'focus_camera' not in filename]
        )
        if not sorted_input_files:
            raise Exception("No valid files found in directory.")

        input_extension = os.path.splitext(sorted_input_files[0])[1]
        max_i, max_j, max_k = 0, 0, 0
        wells, channel_names = set(), set()

        for filename in sorted_input_files:
            if IS_WELLPLATE:
                well, i, j, k, channel_name = os.path.splitext(filename)[0].split('_', 4) 
            else:
                well = '0'
                i, j, k, channel_name = os.path.splitext(filename)[0].split('_', 3)

            channel_name = channel_name.replace("_", " ").replace("full ", "full_")
            i, j, k = int(i), int(j), int(k)

            wells.add(well)
            channel_names.add(channel_name)
            max_i, max_j, max_k = max(max_i, i), max(max_j, j), max(max_k, k)

            tile_info = {
                'filepath': os.path.join(self.image_folder, filename),
                'well': well, 
                'channel': channel_name, 
                'z_level': k, 
                'row': i, 
                'col': j
            }
            self.stitching_data.setdefault(well, {}).setdefault(channel_name, {}).setdefault(k, {}).setdefault((i, j), tile_info)



        self.wells = sorted(wells)
        self.channel_names = sorted(channel_names)
        self.num_z, self.num_cols, self.num_rows = max_k + 1, max_j + 1, max_i + 1

        first_coord = f"{self.wells[0]}_0_0_0_" if IS_WELLPLATE else "0_0_0_"
        found_dims = False
        mono_channel_names = []

        for channel in self.channel_names:
            filename = first_coord + channel.replace(" ", "_") + input_extension
            image = dask_imread(os.path.join(self.image_folder, filename))[0]

            if not found_dims:
                self.dtype = np.dtype(image.dtype)
                self.input_height, self.input_width = image.shape[:2]
                self.chunks = (1, 1, 1, self.input_height, self.input_width)
                found_dims = True
                print("chunks", self.chunks)

            if len(image.shape) == 3:
                self.is_rgb[channel] = True
                mono_channel_names.extend([f"{channel} R", f"{channel} G", f"{channel} B"])
            else:
                self.is_rgb[channel] = False
                mono_channel_names.append(channel)

        self.mono_channel_names = mono_channel_names
        self.num_c = len(mono_channel_names)
        self.channel_colors = [CHANNEL_COLORS_HEX.get(self.extract_wavelength(name), 0xFFFFFF) for name in self.mono_channel_names]
        print(self.mono_channel_names)

    def get_flatfields(self, progress_callback=None):
        def process_images(images, channel_name):
            images = np.array(images)
            basic = BaSiC(get_darkfield=False, smoothness_flatfield=1)
            basic.fit(images)
            channel_index = self.mono_channel_names.index(channel_name)
            self.flatfields[channel_index] = basic.flatfield
            if progress_callback:
                progress_callback(channel_index + 1, self.num_c)

        # Iterate only over the channels you need to process
        for channel in self.channel_names:
            all_tiles = []
            # Collect tiles from all wells and z-levels for the current channel
            for well in self.wells:
                for z_level in self.stitching_data[well][channel]:
                    for row_col, tile_info in self.stitching_data[well][channel][z_level].items():
                        all_tiles.append(tile_info)

            # Shuffle and select a subset of tiles for flatfield calculation
            random.shuffle(all_tiles)
            selected_tiles = all_tiles[:min(32, len(all_tiles))]

            if self.is_rgb[channel]:
                # Process each color channel if the channel is RGB
                images_r = [dask_imread(tile['filepath'])[0][:, :, 0] for tile in selected_tiles]
                images_g = [dask_imread(tile['filepath'])[0][:, :, 1] for tile in selected_tiles]
                images_b = [dask_imread(tile['filepath'])[0][:, :, 2] for tile in selected_tiles]
                process_images(images_r, channel + ' R')
                process_images(images_g, channel + ' G')
                process_images(images_b, channel + ' B')
            else:
                # Process monochrome images
                images = [dask_imread(tile['filepath'])[0] for tile in selected_tiles]
                process_images(images, channel)

    def normalize_image(self, img):
        img_min, img_max = img.min(), img.max()
        img_normalized = (img - img_min) / (img_max - img_min)
        scale_factor = np.iinfo(self.dtype).max if np.issubdtype(self.dtype, np.integer) else 1
        return (img_normalized * scale_factor).astype(self.dtype)

    def visualize_image(self, img1, img2, title):
        if title == 'horizontal':
            combined_image = np.hstack((img1, img2))
        else:
            combined_image = np.vstack((img1, img2))
        cv2.imwrite(f"{self.input_folder}/{title}.png", combined_image)

    def calculate_horizontal_shift(self, img1_path, img2_path, max_overlap, margin_ratio=0.2):
        try:
            img1 = dask_imread(img1_path)[0].compute()
            img2 = dask_imread(img2_path)[0].compute()
            img1 = self.normalize_image(img1)
            img2 = self.normalize_image(img2)

            margin = int(self.input_height * margin_ratio)
            img1_roi, img2_roi = img1[margin:-margin, -max_overlap:], img2[margin:-margin, :max_overlap]
            img1_roi, img2_roi = img1_roi.astype(self.dtype), img2_roi.astype(self.dtype)

            self.visualize_image(img1_roi, img2_roi, "horizontal")
            shift, error, diffphase = phase_cross_correlation(img1_roi, img2_roi, upsample_factor=10)
            return round(shift[0]), round(shift[1] - img1_roi.shape[1])
        except Exception as e:
            print(f"Error calculating horizontal shift: {e}")
            return (0, 0)

    def calculate_vertical_shift(self, img1_path, img2_path, max_overlap, margin_ratio=0.2):
        try:
            img1 = dask_imread(img1_path)[0].compute()
            img2 = dask_imread(img2_path)[0].compute()
            img1 = self.normalize_image(img1)
            img2 = self.normalize_image(img2)

            margin = int(self.input_width * margin_ratio)
            img1_roi, img2_roi = img1[-max_overlap:, margin:-margin], img2[:max_overlap, margin:-margin]
            img1_roi, img2_roi = img1_roi.astype(self.dtype), img2_roi.astype(self.dtype)

            self.visualize_image(img1_roi, img2_roi, "vertical")
            shift, error, diffphase = phase_cross_correlation(img1_roi, img2_roi, upsample_factor=10)
            return round(shift[0] - img1_roi.shape[0]), round(shift[1])
        except Exception as e:
            print(f"Error calculating vertical shift: {e}")
            return (0, 0)

    def calculate_shifts(self, well="", z_level=0):
        well = self.wells[0] if well not in self.wells else well
        self.registration_channel = self.registration_channel if self.registration_channel in self.channel_names else self.channel_names[0]

        # Calculate estimated overlap from acquisition parameters
        dx_mm = self.acquisition_params['dx(mm)']
        dy_mm = self.acquisition_params['dy(mm)']
        obj_mag = self.acquisition_params['objective']['magnification']
        obj_tube_lens_mm = self.acquisition_params['objective']['tube_lens_f_mm']
        sensor_pixel_size_um = self.acquisition_params['sensor_pixel_size_um']
        tube_lens_mm = self.acquisition_params['tube_lens_mm']

        obj_focal_length_mm = obj_tube_lens_mm / obj_mag
        actual_mag = tube_lens_mm / obj_focal_length_mm
        pixel_size_um = sensor_pixel_size_um / actual_mag
        print("pixel_size_um:", pixel_size_um)

        dx_pixels = dx_mm * 1000 / pixel_size_um 
        dy_pixels = dy_mm * 1000 / pixel_size_um
        print("dy_pixels", dy_pixels, ", dx_pixels:", dx_pixels)
        
        self.max_x_overlap = round(abs(self.input_width - dx_pixels) / 2)
        self.max_y_overlap = round(abs(self.input_height - dy_pixels) / 2)
        print("objective calculated - vertical overlap:", self.max_y_overlap, ", horizontal overlap:", self.max_x_overlap)

        col_left, col_right = (self.num_cols - 1) // 2, (self.num_cols - 1) // 2 + 1
        if self.is_reversed['cols']:
            col_left, col_right = col_right, col_left

        row_top, row_bottom = (self.num_rows - 1) // 2, (self.num_rows - 1) // 2 + 1
        if self.is_reversed['rows']:
            row_top, row_bottom = row_bottom, row_top

        for (row, col), tile_info in self.stitching_data[well][self.registration_channel][z_level].items():
            if col == col_left and row == row_top:
                img1_path = tile_info['filepath']
            elif col == col_left and row == row_bottom:
                img2_path_vertical = tile_info['filepath']
            elif col == col_right and row == row_top:
                img2_path_horizontal = tile_info['filepath']

        if img1_path is None:
            raise Exception(
                f"No input file found for c:{self.registration_channel} k:{z_level} "
                f"j:{col_left} i:{row_top}"
            )

        self.v_shift = (
            self.calculate_vertical_shift(img1_path, img2_path_vertical, self.max_y_overlap)
            if self.max_y_overlap > 0 and img2_path_vertical and img1_path != img2_path_vertical else (0, 0)
        )
        self.h_shift = (
            self.calculate_horizontal_shift(img1_path, img2_path_horizontal, self.max_x_overlap)
            if self.max_x_overlap > 0 and img2_path_horizontal and img1_path != img2_path_horizontal else (0, 0)
        )
        print("vertical shift:", self.v_shift, ", horizontal shift:", self.h_shift)

    def calculate_dynamic_shifts(self, well, channel, z_level, row, col):
        h_shift, v_shift = self.h_shift, self.v_shift

        # Check for left neighbor
        if (row, col - 1) in self.stitching_data[well][channel][z_level]:
            left_tile_path = self.stitching_data[well][channel][z_level][row, col - 1]['filepath']
            current_tile_path = self.stitching_data[well][channel][z_level][row, col]['filepath']
            # Calculate horizontal shift
            new_h_shift = self.calculate_horizontal_shift(left_tile_path, current_tile_path, abs(self.h_shift[1]))

            # Check if the new horizontal shift is within 10% of the precomputed shift
            if self.h_shift == (0,0) or (0.95 * abs(self.h_shift[1]) <= abs(new_h_shift[1]) <= 1.05 * abs(self.h_shift[1]) and 
                0.95 * abs(self.h_shift[0]) <= abs(new_h_shift[0]) <= 1.05 * abs(self.h_shift[0])):
                print("new h shift", new_h_shift, h_shift)
                h_shift = new_h_shift

        # Check for top neighbor
        if (row - 1, col) in self.stitching_data[well][channel][z_level]:
            top_tile_path = self.stitching_data[well][channel][z_level][row - 1, col]['filepath']
            current_tile_path = self.stitching_data[well][channel][z_level][row, col]['filepath']
            # Calculate vertical shift
            new_v_shift = self.calculate_vertical_shift(top_tile_path, current_tile_path, abs(self.v_shift[0]))

            # Check if the new vertical shift is within 10% of the precomputed shift
            if self.v_shift == (0,0) or (0.95 * abs(self.v_shift[0]) <= abs(new_v_shift[0]) <= 1.05 * abs(self.v_shift[0]) and 
                0.95 * abs(self.v_shift[1]) <= abs(new_v_shift[1]) <= 1.05 * abs(self.v_shift[1])):
                print("new v shift", new_v_shift, v_shift)
                v_shift = new_v_shift

        return h_shift, v_shift

    def init_output(self, time_point, well):
        output_folder = os.path.join(self.input_folder, f"{time_point}_stitched")
        os.makedirs(output_folder, exist_ok=True)
        self.output_path = os.path.join(output_folder, f"{well}_{self.output_name}" if IS_WELLPLATE else self.output_name)

        x_max = (self.input_width + ((self.num_cols - 1) * (self.input_width + self.h_shift[1])) + # horizontal width with overlap
                abs((self.num_rows - 1) * self.v_shift[1])) # horizontal shift from vertical registration
        y_max = (self.input_height + ((self.num_rows - 1) * (self.input_height + self.v_shift[0])) + # vertical height with overlap
                abs((self.num_cols - 1) * self.h_shift[0])) # vertical shift from horizontal registration
        if self.use_registration and FULL_REGISTRATION:
            y_max *= 1.05
            x_max *= 1.05
        tczyx_shape = (1, self.num_c, self.num_z, y_max, x_max)
        print(f"(t:{time_point}, well:{well}) output shape: {tczyx_shape}")
        return da.zeros(tczyx_shape, dtype=self.dtype, chunks=self.chunks)

    def stitch_images(self, time_point, well, progress_callback=None):
        self.stitched_images = self.init_output(time_point, well)
        total_tiles = sum(1 for channel_data in self.stitching_data[well].values() 
                                  for z_data in channel_data.values() 
                                  for row_col in z_data.keys())
        processed_tiles = 0

        for z_level in range(self.num_z):

            for row in range(self.num_rows):
                row = self.num_rows - 1 - row if self.is_reversed['rows'] else row

                for col in range(self.num_cols):
                    col = self.num_cols - 1 - col if self.is_reversed['cols'] else col

                    if self.use_registration and FULL_REGISTRATION and z_level == 0:
                        if (row, col) in self.stitching_data[well][self.registration_channel][z_level]:
                            tile_info = self.stitching_data[well][self.registration_channel][z_level][(row, col)]
                            self.h_shift, self.v_shift = self.calculate_dynamic_shifts(well, self.registration_channel, z_level, row, col)

                    # Now apply the same shifts to all channels
                    for channel in self.channel_names:
                        if (row, col) in self.stitching_data[well][channel][z_level]:
                            tile_info = self.stitching_data[well][channel][z_level][(row, col)]
                            tile = dask_imread(tile_info['filepath'])[0]
                            #tile = tile[:, ::-1]
                            if self.is_rgb[channel]:
                                for color_idx, color in enumerate(['R', 'G', 'B']):
                                    tile_color = tile[:, :, color_idx]
                                    color_channel = f"{channel} {color}"
                                    self.stitch_single_image(tile_color, z_level, self.mono_channel_names.index(color_channel), row, col)
                                    processed_tiles += 1
                            else:
                                self.stitch_single_image(tile, z_level, self.mono_channel_names.index(channel), row, col)
                                processed_tiles += 1
                        if progress_callback is not None:
                            progress_callback(processed_tiles, total_tiles)

    def stitch_single_image(self, tile, z_level, channel_idx, row, col):
        #print(tile.shape)
        if self.apply_flatfield:
            tile = (tile / self.flatfields[channel_idx]).clip(min=np.iinfo(self.dtype).min, 
                                                              max=np.iinfo(self.dtype).max).astype(self.dtype)
        # Determine crop for tile edges 
        top_crop = max(0, (-self.v_shift[0] // 2) - abs(self.h_shift[0]) // 2) if row > 0 else 0
        bottom_crop = max(0, (-self.v_shift[0] // 2) - abs(self.h_shift[0]) // 2) if row < self.num_rows - 1 else 0
        left_crop = max(0, (-self.h_shift[1] // 2) - abs(self.v_shift[1]) // 2) if col > 0 else 0
        right_crop = max(0, (-self.h_shift[1] // 2) - abs(self.v_shift[1]) // 2) if col < self.num_cols - 1 else 0

        tile = tile[top_crop:tile.shape[0]-bottom_crop, left_crop:tile.shape[1]-right_crop]

        # Initialize starting coordinates based on tile position and shift
        y = row * (self.input_height + self.v_shift[0]) + top_crop
        if self.h_shift[0] < 0:
            y -= (self.num_cols - 1 - col) * self.h_shift[0]  # Moves up if negative
        else:
            y += col * self.h_shift[0]  # Moves down if positive

        x = col * (self.input_width + self.h_shift[1]) + left_crop
        if self.v_shift[1] < 0:
            x -= (self.num_rows - 1 - row) * self.v_shift[1]  # Moves left if negative
        else:
            x += row * self.v_shift[1]  # Moves right if positive
        
        # Place cropped tile on the stitched image canvas
        self.stitched_images[0, channel_idx, z_level, y:y+tile.shape[0], x:x+tile.shape[1]] = tile
        # print(f" col:{col}, \trow:{row},\ty:{y}-{y+tile.shape[0]}, \tx:{x}-{x+tile.shape[-1]}")

    def save_as_ome_tiff(self):
        dz_um = self.acquisition_params.get("dz(um)", None)
        sensor_pixel_size_um = self.acquisition_params.get("sensor_pixel_size_um", None)
        dims = "TCZYX"
        # if self.is_rgb:
        #     dims += "S"

        ome_metadata = OmeTiffWriter.build_ome(
            image_name=[os.path.basename(self.output_path)],
            data_shapes=[self.stitched_images.shape],
            data_types=[self.stitched_images.dtype],
            dimension_order=[dims],
            channel_names=[self.mono_channel_names],
            physical_pixel_sizes=[types.PhysicalPixelSizes(dz_um, sensor_pixel_size_um, sensor_pixel_size_um)],
            #is_rgb=self.is_rgb
            #channel colors
        )
        OmeTiffWriter.save(
            data=self.stitched_images,
            uri=self.output_path,
            ome_xml=ome_metadata,
            dimension_order=[dims]
            #channel colors / names
        )
        self.stitched_images = None

    def save_as_ome_zarr(self):
        dz_um = self.acquisition_params.get("dz(um)", None)
        sensor_pixel_size_um = self.acquisition_params.get("sensor_pixel_size_um", None)
        dims = "TCZYX"
        intensity_min = np.iinfo(self.dtype).min
        intensity_max = np.iinfo(self.dtype).max
        channel_minmax = [(intensity_min, intensity_max)] * self.num_c
        for i in range(self.num_c):
            print(f"Channel {i}:", self.mono_channel_names[i], " \tColor:", self.channel_colors[i], " \tPixel Range:", channel_minmax[i])

        zarr_writer = OmeZarrWriter(self.output_path)
        zarr_writer.build_ome(
            size_z=self.num_z,
            image_name=os.path.basename(self.output_path),
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            channel_minmax=channel_minmax
        )
        zarr_writer.write_image(
            image_data=self.stitched_images,
            image_name=os.path.basename(self.output_path),
            physical_pixel_sizes=types.PhysicalPixelSizes(dz_um, sensor_pixel_size_um, sensor_pixel_size_um),
            channel_names=self.mono_channel_names,
            channel_colors=self.channel_colors,
            dimension_order=dims,
            scale_num_levels=5,
            chunk_dims=self.chunks
        )
        self.stitched_images = None

    def create_complete_ome_zarr(self):
        """ Creates a complete OME-ZARR with proper channel metadata. """
        final_path = os.path.join(self.input_folder, self.output_name.replace(".ome.zarr","") + "_complete_acquisition.ome.zarr")
        if len(self.time_points) == 1:
            zarr_path = os.path.join(self.input_folder, f"0_stitched", self.output_name)
            #final_path = zarr_path
            shutil.copytree(zarr_path, final_path)
        else:
            store = ome_zarr.io.parse_url(final_path, mode="w").store
            root_group = zarr.group(store=store)
            intensity_min = np.iinfo(self.dtype).min
            intensity_max = np.iinfo(self.dtype).max

            data = self.load_and_merge_timepoints()
            ome_zarr.writer.write_image(
                image=data,
                group=root_group,
                axes="tczyx",
                channel_names=self.mono_channel_names,
                storage_options=dict(chunks=self.chunks)
            )

            channel_info = [{
                "label": self.mono_channel_names[i],
                "color": f"{self.channel_colors[i]:06X}",
                "window": {"start": intensity_min, "end": intensity_max},
                "active": True
            } for i in range(self.num_c)]

            # Assign the channel metadata to the image group
            root_group.attrs["omero"] = {"channels": channel_info}

            print(f"all data saved in HCS OME-ZARR format at: {final_path}")
            root = zarr.open(final_path, mode='r')
            print(root.tree())
        self.finished_saving.emit(final_path, self.dtype)

    def create_hcs_ome_zarr(self):
        """Creates a hierarchical Zarr file in the HCS OME-ZARR format for visualization in napari."""
        hcs_path = os.path.join(self.input_folder, self.output_name.replace(".ome.zarr","") + "_complete_acquisition.ome.zarr")
        if len(self.time_points) == 1 and len(self.wells) == 1:
            stitched_zarr_path = os.path.join(self.input_folder, f"0_stitched", f"{self.wells[0]}_{self.output_name}")
            #hcs_path = stitched_zarr_path # replace next line with this if no copy wanted
            shutil.copytree(stitched_zarr_path, hcs_path)
        else:
            store = ome_zarr.io.parse_url(hcs_path, mode="w").store
            root_group = zarr.group(store=store)

            # Retrieve row and column information for plate metadata
            rows, columns = self.get_rows_and_columns()
            well_paths = [f"{well_id[0]}/{well_id[1:]}" for well_id in sorted(self.wells)]
            print(well_paths)
            ome_zarr.writer.write_plate_metadata(root_group, rows, [str(col) for col in columns], well_paths)

            # Loop over each well and save its data
            for well_id in self.wells:
                row, col = well_id[0], well_id[1:]
                row_group = root_group.require_group(row)
                well_group = row_group.require_group(col)
                self.write_well_and_metadata(well_id, well_group)

            print(f"All data saved in HCS OME-ZARR format at: {hcs_path}")
            channel_info = []

            root_group.attrs["omero"] = {"channels": channel_info}
            root = zarr.open(hcs_path, mode='r')
            print(root.tree())
        self.finished_saving.emit(hcs_path, self.dtype)

    def write_well_and_metadata(self, well_id, well_group):
        """Process and save data for a single well across all timepoints."""
        # Load data from precomputed Zarrs for each timepoint
        data = self.load_and_merge_timepoints(well_id)
        intensity_min = np.iinfo(self.dtype).min
        intensity_max = np.iinfo(self.dtype).max
        #dataset = well_group.create_dataset("data", data=data, chunks=(1, 1, 1, self.input_height, self.input_width), dtype=data.dtype)
        field_paths = ["0"]  # Assuming single field of view
        ome_zarr.writer.write_well_metadata(well_group, field_paths)
        for fi, field in enumerate(field_paths):
            image_group = well_group.require_group(str(field))
            ome_zarr.writer.write_image(image=data,
                                        group=image_group,
                                        axes="tczyx",
                                        channel_names=self.mono_channel_names,
                                        storage_options=dict(chunks=self.chunks)
                                        )
            channel_info = [{
                "label": self.mono_channel_names[c],
                "color": f"{self.channel_colors[c]:06X}",
                "window": {"start": intensity_min, "end": intensity_max},
                "active": True
            } for c in range(self.num_c)]

            image_group.attrs["omero"] = {"channels": channel_info}

    def pad_to_largest(self, array, target_shape):
        if array.shape == target_shape:
            return array
        pad_widths = [(0, max(0, ts - s)) for s, ts in zip(array.shape, target_shape)]
        return da.pad(array, pad_widths, mode='constant', constant_values=0)

    def load_and_merge_timepoints(self, well_id=''):
        """Load and merge data for a well from Zarr files for each timepoint."""
        t_data = []
        t_shapes = []
        for t in self.time_points:
            if IS_WELLPLATE:
                filepath = f"{well_id}_{self.output_name}"
            else:
                filepath = f"{self.output_name}"
            zarr_path = os.path.join(self.input_folder, f"{t}_stitched", filepath)
            print("t:", t, "well:", well_id, "\t", zarr_path)
            z = zarr.open(zarr_path, mode='r')
            # Ensure that '0' contains the data and it matches expected dimensions
            x_max = self.input_width + ((self.num_cols - 1) * (self.input_width + self.h_shift[1])) + abs((self.num_rows - 1) * self.v_shift[1])
            y_max = self.input_height + ((self.num_rows - 1) * (self.input_height + self.v_shift[0])) + abs((self.num_cols - 1) * self.h_shift[0])
            t_array = da.from_zarr(z['0'], chunks=self.chunks)
            t_data.append(t_array)
            t_shapes.append(t_array.shape)

        # Concatenate arrays along the existing time axis if multiple timepoints are present
        if len(t_data) > 1:
            max_shape = tuple(max(s) for s in zip(*t_shapes))
            padded_data = [self.pad_to_largest(t, max_shape) for t in t_data]
            data = da.concatenate(padded_data, axis=0)
            print(f"(merged timepoints, well:{well_id}) output shape: {data.shape}")
            return data
        elif len(t_data) == 1:
            data = t_data[0]
            return data
        else:
            raise ValueError("no data loaded from timepoints.")

    def get_rows_and_columns(self):
        """Utility to extract rows and columns from well identifiers."""
        rows = set()
        columns = set()
        for well_id in self.wells:
            rows.add(well_id[0])  # Assuming well_id like 'A1'
            columns.add(int(well_id[1:]))
        return sorted(rows), sorted(columns)

    def run(self):
        # Main stitching logic
        try:
            for time_point in self.time_points:
                print(f"starting t:{time_point}...")
                self.parse_filenames(time_point) # 

                if self.apply_flatfield:
                    print(f"getting flatfields...")
                    self.getting_flatfields.emit()
                    self.get_flatfields(progress_callback=self.update_progress.emit)

                if self.use_registration:
                    print(f"calculating shifts...")
                    self.calculate_shifts()

                for well in self.wells:
                    self.starting_stitching.emit()
                    print(f"stitching...")
                    self.stitch_images(time_point, well, progress_callback=self.update_progress.emit)

                    self.starting_saving.emit(not STITCH_COMPLETE_ACQUISITION)
                    print(f"saving...")
                    if ".ome.tiff" in self.output_path:
                        self.save_as_ome_tiff()
                    else:
                        self.save_as_ome_zarr()
                    if well != '0':
                        print(f"...done saving well:{well}")
                print(f"...finished t:{time_point}")

            if STITCH_COMPLETE_ACQUISITION and ".ome.zarr" in self.output_name:
                self.starting_saving.emit(True)
                if IS_WELLPLATE:
                    self.create_hcs_ome_zarr()
                    print(f"...done saving complete hcs successfully")
                else:
                    self.create_complete_ome_zarr()
                    print(f"...done saving complete successfully")
            else:
                self.finished_saving.emit(self.output_path, self.dtype)

        except Exception as e:
            print(f"error While Stitching: {e}")


class ImageDisplayWindow(QMainWindow):

    image_click_coordinates = Signal(int, int, int, int)

    def __init__(self, window_title='', draw_crosshairs = False, show_LUT=False, autoLevels=False):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.widget = QWidget()
        self.show_LUT = show_LUT
        self.autoLevels = autoLevels

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')

        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.view = self.graphics_widget.addViewBox()
        self.graphics_widget.view.invertY()
        
        ## lock the aspect ratio so pixels are always square
        self.graphics_widget.view.setAspectLocked(True)
        
        ## Create image item
        if self.show_LUT:
            self.graphics_widget.view = pg.ImageView()
            self.graphics_widget.img = self.graphics_widget.view.getImageItem()
            self.graphics_widget.img.setBorder('w')
            self.graphics_widget.view.ui.roiBtn.hide()
            self.graphics_widget.view.ui.menuBtn.hide()
            # self.LUTWidget = self.graphics_widget.view.getHistogramWidget()
            # self.LUTWidget.autoHistogramRange()
            # self.graphics_widget.view.autolevels()
        else:
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

        # ## flag of setting scaling level 
        # self.flag_image_scaling_level_init = False

        ## Layout
        layout = QGridLayout()
        if self.show_LUT:
            layout.addWidget(self.graphics_widget.view, 0, 0) 
        else:
            layout.addWidget(self.graphics_widget, 0, 0) 
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)

        # set window size
        desktopWidget = QDesktopWidget();
        width = min(desktopWidget.height()*0.9,1000) #@@@TO MOVE@@@#
        height = width
        self.setFixedSize(int(width),int(height))
        if self.show_LUT:
            self.graphics_widget.view.getView().scene().sigMouseClicked.connect(self.mouse_clicked)
        else:
            self.graphics_widget.view.scene().sigMouseClicked.connect(self.mouse_clicked)
        
    def is_within_image(self, coordinates):
        try:
            image_width = self.graphics_widget.img.width()
            image_height = self.graphics_widget.img.height()

            return 0 <= coordinates.x() < image_width and 0 <= coordinates.y() < image_height
        except:
            return False

    def mouse_clicked(self, evt):
        try:
            pos = evt.pos()
            if self.show_LUT:
                view_coord = self.graphics_widget.view.getView().mapSceneToView(pos)
            else:
                view_coord = self.graphics_widget.view.mapSceneToView(pos)
            image_coord = self.graphics_widget.img.mapFromView(view_coord)
        except:
            return

        if self.is_within_image(image_coord):
            x_pixel_centered = int(image_coord.x() - self.graphics_widget.img.width()/2)
            y_pixel_centered = int(image_coord.y() - self.graphics_widget.img.height()/2)
            self.image_click_coordinates.emit(x_pixel_centered, y_pixel_centered, self.graphics_widget.img.width(), self.graphics_widget.img.height()) 

    def display_image(self,image):
        # def set_autoLevels_value():
        #     if self.autoLevels is True:
        #         self.graphics_widget.img.setImage(image,autoLevels=self.autoLevels)
        #     else:
        #         if self.flag_image_scaling_level_init is False:
        #             self.graphics_widget.img.setImage(image, autoLevels = True)
        #             self.flag_image_scaling_level_init = True
        #         else:
        #             self.graphics_widget.img.setImage(image,autoLevels=self.autoLevels)

        if ENABLE_TRACKING:
            image = np.copy(image)
            self.image_height = image.shape[0],
            self.image_width = image.shape[1]
            if(self.draw_rectangle):
                cv2.rectangle(image, self.ptRect1, self.ptRect2,(255,255,255) , 4)
                self.draw_rectangle = False
            self.graphics_widget.img.setImage(image,autoLevels=self.autoLevels)
            # set_autoLevels_value()
        else:
            self.graphics_widget.img.setImage(image,autoLevels=self.autoLevels)
            # set_autoLevels_value()

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

    def set_autolevel(self,enabled):
        self.autoLevels = enabled
        print('set autolevel to ' + str(enabled))

class NavigationViewer(QFrame):

    def __init__(self, sample = 'glass slide', invertX = False, *args, **kwargs):
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

        if sample == 'glass slide':
            self.background_image = cv2.imread('images/slide carrier_828x662.png')
        elif sample == '384 well plate':
            self.background_image = cv2.imread('images/384 well plate_1509x1010.png')
        elif sample == '96 well plate':
            self.background_image = cv2.imread('images/96 well plate_1509x1010.png')
        elif sample == '24 well plate':
            self.background_image = cv2.imread('images/24 well plate_1509x1010.png')
        elif sample == '12 well plate':
            self.background_image = cv2.imread('images/12 well plate_1509x1010.png')
        elif sample == '6 well plate':
            self.background_image = cv2.imread('images/6 well plate_1509x1010.png')
        elif sample == '1536 well plate':
            self.background_image = cv2.imread('images/1536 well plate_1509x1010.png')
        
        self.current_image = np.copy(self.background_image)
        self.current_image_display = np.copy(self.background_image)
        self.image_height = self.background_image.shape[0]
        self.image_width = self.background_image.shape[1]

        self.location_update_threshold_mm = 0.2
        self.sample = sample

        if sample == 'glass slide':
            self.origin_x_pixel = 200
            self.origin_y_pixel = 120
            self.mm_per_pixel = 0.1453
            self.fov_size_mm = 3000*1.85/(50/9)/1000
        else:
            self.location_update_threshold_mm = 0.05
            self.mm_per_pixel = 0.084665
            self.fov_size_mm = 3000*1.85/(50/10)/1000
            self.origin_x_pixel = A1_X_PIXEL - (A1_X_MM)/self.mm_per_pixel
            self.origin_y_pixel = A1_Y_PIXEL - (A1_Y_MM)/self.mm_per_pixel

        self.box_color = (255, 0, 0)
        self.box_line_thickness = 2

        self.x_mm = None
        self.y_mm = None

        self.update_display()

    def update_current_location(self,x_mm,y_mm):
        if self.x_mm != None and self.y_mm != None:
            # update only when the displacement has exceeded certain value
            if abs(x_mm - self.x_mm) > self.location_update_threshold_mm or abs(y_mm - self.y_mm) > self.location_update_threshold_mm:
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
        if self.sample == 'glass slide':
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        else:
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        cv2.rectangle(self.current_image_display, current_FOV_top_left, current_FOV_bottom_right, self.box_color, self.box_line_thickness)

    def update_display(self):
        self.graphics_widget.img.setImage(self.current_image_display,autoLevels=False)

    def clear_slide(self):
        self.current_image = np.copy(self.background_image)
        self.current_image_display = np.copy(self.background_image)
        self.update_display()

    def register_fov(self,x_mm,y_mm):
        color = (0,0,255)
        if self.sample == 'glass slide':
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        else:
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        cv2.rectangle(self.current_image, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)

    def register_fov_to_image(self,x_mm,y_mm):
        color = (252,174,30)
        if self.sample == 'glass slide':
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        else:
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        cv2.rectangle(self.current_image, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)

    def deregister_fov_to_image(self,x_mm,y_mm):
        color = (255,255,255)
        if self.sample == 'glass slide':
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        else:
            current_FOV_top_left = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
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
        self.graphics_widget_1.view.invertY()

        self.graphics_widget_2 = pg.GraphicsLayoutWidget()
        self.graphics_widget_2.view = self.graphics_widget_2.addViewBox()
        self.graphics_widget_2.view.setAspectLocked(True)
        self.graphics_widget_2.img = pg.ImageItem(border='w')
        self.graphics_widget_2.view.addItem(self.graphics_widget_2.img)
        self.graphics_widget_2.view.invertY()

        self.graphics_widget_3 = pg.GraphicsLayoutWidget()
        self.graphics_widget_3.view = self.graphics_widget_3.addViewBox()
        self.graphics_widget_3.view.setAspectLocked(True)
        self.graphics_widget_3.img = pg.ImageItem(border='w')
        self.graphics_widget_3.view.addItem(self.graphics_widget_3.img)
        self.graphics_widget_3.view.invertY()

        self.graphics_widget_4 = pg.GraphicsLayoutWidget()
        self.graphics_widget_4.view = self.graphics_widget_4.addViewBox()
        self.graphics_widget_4.view.setAspectLocked(True)
        self.graphics_widget_4.img = pg.ImageItem(border='w')
        self.graphics_widget_4.view.addItem(self.graphics_widget_4.img)
        self.graphics_widget_4.view.invertY()
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
        self.setFixedSize(int(width),int(height))

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
    def __init__(self,filename="channel_configurations.xml"):
        QObject.__init__(self)
        self.config_filename = filename
        self.configurations = []
        self.read_configurations()
        
    def save_configurations(self):
        self.write_configuration(self.config_filename)

    def write_configuration(self,filename):
        self.config_xml_tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)

    def read_configurations(self):
        print('read config')
        if(os.path.isfile(self.config_filename)==False):
            utils_config.generate_default_configuration(self.config_filename)
            print('genenrate default config files')
        self.config_xml_tree = etree.parse(self.config_filename)
        self.config_xml_tree_root = self.config_xml_tree.getroot()
        self.num_configurations = 0
        for mode in self.config_xml_tree_root.iter('mode'):
            self.num_configurations += 1
            # print("name:", mode.get('Name'), "color:", self.get_channel_color(mode.get('Name')))
            self.configurations.append(
                Configuration(
                    mode_id = mode.get('ID'),
                    name = mode.get('Name'),
                    color = self.get_channel_color(mode.get('Name')),
                    exposure_time = float(mode.get('ExposureTime')),
                    analog_gain = float(mode.get('AnalogGain')),
                    illumination_source = int(mode.get('IlluminationSource')),
                    illumination_intensity = float(mode.get('IlluminationIntensity')),
                    camera_sn = mode.get('CameraSN'),
                    z_offset = float(mode.get('ZOffset')),
                    pixel_format = mode.get('PixelFormat'),
                    _pixel_format_options = mode.get('_PixelFormat_options'),
                    emission_filter_position = int(mode.get('EmissionFilterPosition', 1))
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
        for conf in self.configurations:
            self.update_configuration_without_writing(conf.id, "Selected", 0)
        for conf in selected_configurations:
            self.update_configuration_without_writing(conf.id, "Selected", 1)
        self.write_configuration(filename)
        for conf in selected_configurations:
            self.update_configuration_without_writing(conf.id, "Selected", 0)

    def get_channel_color(self, channel):
        channel_info = CHANNEL_COLORS_MAP.get(self.extract_wavelength(channel), {'hex': 0xFFFFFF, 'name': 'gray'})
        return channel_info['hex']

    def extract_wavelength(self, name):
        # Split the string and find the wavelength number immediately after "Fluorescence"
        parts = name.split()
        if 'Fluorescence' in parts:
            index = parts.index('Fluorescence') + 1
            if index < len(parts):
                return parts[index].split()[0]  # Assuming 'Fluorescence 488 nm Ex' and taking '488'
        for color in ['R', 'G', 'B']:
            if color in parts or "full_" + color in parts:
                return color
        return None

class PlateReaderNavigationController(QObject):

    signal_homing_complete = Signal()
    signal_current_well = Signal(str)

    def __init__(self,microcontroller):
        QObject.__init__(self)
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

class ScanCoordinates(object):
    def __init__(self):
        self.coordinates_mm = []
        self.name = []
        self.well_selector = None

    def _index_to_row(self,index):
        index += 1
        row = ""
        while index > 0:
            index -= 1
            row = chr(index % 26 + ord('A')) + row
            index //= 26
        return row

    def add_well_selector(self,well_selector):
        self.well_selector = well_selector

    def get_selected_wells(self):
        # get selected wells from the widget
        selected_wells = self.well_selector.get_selected_cells()
        selected_wells = np.array(selected_wells)
        # clear the previous selection
        self.coordinates_mm = []
        self.name = []
        if len(selected_wells) == 0:
            return
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
                x_mm = A1_X_MM + column*WELL_SPACING_MM + WELLPLATE_OFFSET_X_mm
                y_mm = A1_Y_MM + row*WELL_SPACING_MM + WELLPLATE_OFFSET_Y_mm
                self.coordinates_mm.append((x_mm,y_mm))
                self.name.append(self._index_to_row(row)+str(column+1))
            _increasing = not _increasing


class LaserAutofocusController(QObject):

    image_to_display = Signal(np.ndarray)
    signal_displacement_um = Signal(float)

    def __init__(self,microcontroller,camera,liveController,navigationController,has_two_interfaces=True,use_glass_top=True, look_for_cache=True):
        QObject.__init__(self)
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

        self.image = None # for saving the focus camera image for debugging when centroid cannot be found

        if look_for_cache:
            cache_path = "cache/laser_af_reference_plane.txt"
            try:
                with open(cache_path, "r") as cache_file:
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
            cache_path = Path("cache/laser_af_reference_plane.txt")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(cache_string)
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

        if x1-x0 == 0:
            # for simulation
             self.pixel_to_um = 0.4
        else:
            # calculate the conversion factor
            self.pixel_to_um = 6.0/(x1-x0)
        print('pixel to um conversion factor is ' + str(self.pixel_to_um) + ' um/pixel')

        # set reference
        self.x_reference = x1

        if self.look_for_cache:
            cache_path = "cache/laser_af_reference_plane.txt"
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
                cache_path = Path("cache/laser_af_reference_plane.txt")
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
        self.signal_displacement_um.emit(displacement_um)
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
        self.signal_displacement_um.emit(0)

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
            self.image = image
            # optionally display the image
            if LASER_AF_DISPLAY_SPOT_IMAGE:
                self.image_to_display.emit(image)
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

    def get_image(self):
        # turn on the laser
        self.microcontroller.turn_on_AF_laser()
        self.wait_till_operation_is_completed()
        # send trigger, grab image and display image
        self.camera.send_trigger()
        image = self.camera.read_frame()
        self.image_to_display.emit(image)
        # turn off the laser
        self.microcontroller.turn_off_AF_laser()
        self.wait_till_operation_is_completed()
        return image
