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
if DO_FLUORESCENCE_RTP:
    from control.processing_handler import ProcessingHandler
    from control.processing_pipeline import *
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
    def __init__(self, objectives_dict=OBJECTIVES, default_objective=DEFAULT_OBJECTIVE, parent=None):
        self.objectives_dict = objectives_dict
        self.default_objective = default_objective
        self.current_objective = default_objective
        self.tube_lens_mm = TUBE_LENS_MM
        self.sensor_pixel_size_um = CAMERA_PIXEL_SIZE_UM[CAMERA_SENSOR]
        self.pixel_binning = self.get_pixel_binning()
        self.pixel_size_um = self.calculate_pixel_size(self.current_objective)

    def get_pixel_size(self):
        return self.pixel_size_um

    def calculate_pixel_size(self, objective_name):
        objective = self.objectives_dict[objective_name]
        magnification = objective["magnification"]
        objective_tube_lens_mm = objective["tube_lens_f_mm"]
        pixel_size_um = self.sensor_pixel_size_um / (magnification / (objective_tube_lens_mm / self.tube_lens_mm)) 
        pixel_size_um *= self.pixel_binning
        return pixel_size_um

    def set_current_objective(self, objective_name):
        if objective_name in self.objectives_dict:
            self.current_objective = objective_name
            self.pixel_size_um = self.calculate_pixel_size(objective_name)
        else:
            raise ValueError(f"Objective {objective_name} not found in the store.")

    def get_current_objective_info(self):
        return self.objectives_dict[self.current_objective]

    def get_pixel_binning(self):
        try:
            highest_res = max(self.parent.camera.res_list, key=lambda res: res[0] * res[1])
            resolution = self.parent.camera.resolution
            pixel_binning = max(1, highest_res[0] / resolution[0])
        except AttributeError:
            pixel_binning = 1
        return pixel_binning

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

        self.enable_channel_auto_filter_switching = True

        if USE_LDI_SERIAL_CONTROL:
            self.ldi = self.microscope.ldi
      
        if SUPPORT_SCIMICROSCOPY_LED_ARRAY:
            # to do: add error handling
            self.led_array = serial_peripherals.SciMicroscopyLEDArray(SCIMICROSCOPY_LED_ARRAY_SN,SCIMICROSCOPY_LED_ARRAY_DISTANCE,SCIMICROSCOPY_LED_ARRAY_TURN_ON_DELAY)
            self.led_array.set_NA(SCIMICROSCOPY_LED_ARRAY_DEFAULT_NA)

    # illumination control
    def turn_on_illumination(self):
        if USE_LDI_SERIAL_CONTROL and 'Fluorescence' in self.currentConfiguration.name and LDI_SHUTTER_MODE == 'PC':
            self.ldi.set_active_channel_shutter(1)
        elif SUPPORT_SCIMICROSCOPY_LED_ARRAY and 'LED matrix' in self.currentConfiguration.name:
            self.led_array.turn_on_illumination()
        else:
            self.microcontroller.turn_on_illumination()
        self.illumination_on = True

    def turn_off_illumination(self):
        if USE_LDI_SERIAL_CONTROL and 'Fluorescence' in self.currentConfiguration.name and LDI_SHUTTER_MODE == 'PC':
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
                if LDI_SHUTTER_MODE == 'PC':
                    # set LDI active channel
                    print('set active channel to ' + str(illumination_source))
                    self.ldi.set_active_channel(int(illumination_source))
                if LDI_INTENSITY_MODE == 'PC':
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
        if ENABLE_SPINNING_DISK_CONFOCAL:
            try:
                self.microscope.xlight.set_emission_filter(XLIGHT_EMISSION_FILTER_MAPPING[illumination_source],extraction=False,validate=XLIGHT_VALIDATE_WHEEL_POS)
            except Exception as e:
                print('not setting emission filter position due to ' + str(e))

        if USE_ZABER_EMISSION_FILTER_WHEEL and self.enable_channel_auto_filter_switching:
            try:
                if self.currentConfiguration.emission_filter_position != self.microscope.emission_filter_wheel.current_index:
                    if ZABER_EMISSION_FILTER_WHEEL_BLOCKING_CALL:
                        self.microscope.emission_filter_wheel.set_emission_filter(self.currentConfiguration.emission_filter_position,blocking=True)
                    else:
                        self.microscope.emission_filter_wheel.set_emission_filter(self.currentConfiguration.emission_filter_position,blocking=False)
                        if self.trigger_mode == TriggerMode.SOFTWARE:
                            time.sleep(ZABER_EMISSION_FILTER_WHEEL_DELAY_MS/1000)
                        else:
                            time.sleep(max(0,ZABER_EMISSION_FILTER_WHEEL_DELAY_MS/1000-self.camera.strobe_delay_us/1e6))
            except Exception as e:
                print('not setting emission filter position due to ' + str(e))

        if USE_OPTOSPIN_EMISSION_FILTER_WHEEL and self.enable_channel_auto_filter_switching and OPTOSPIN_EMISSION_FILTER_WHEEL_TTL_TRIGGER == False:
            try:
                if self.currentConfiguration.emission_filter_position != self.microscope.emission_filter_wheel.current_index:
                    self.microscope.emission_filter_wheel.set_emission_filter(self.currentConfiguration.emission_filter_position)
                    if self.trigger_mode == TriggerMode.SOFTWARE:
                        time.sleep(OPTOSPIN_EMISSION_FILTER_WHEEL_DELAY_MS/1000)
                    elif self.trigger_mode == TriggerMode.HARDWARE:
                        time.sleep(max(0,OPTOSPIN_EMISSION_FILTER_WHEEL_DELAY_MS/1000-self.camera.strobe_delay_us/1e6))
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
    new_zPos_mm = Signal(float)
    thetaPos = Signal(float)
    xyPos = Signal(float,float)
    signal_joystick_button_pressed = Signal()

    # x y z axis pid enable flag
    pid_enable_flag = [False, False, False]


    def __init__(self,microcontroller, objectivestore, parent=None):
        # parent should be set to OctopiGUI instance to enable updates
        # to camera settings, e.g. binning, that would affect click-to-move
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.parent = parent
        self.objectiveStore = objectivestore
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
        fov_col = click_x * Nx // image_width
        fov_row = click_y * Ny // image_height
        print("image - (col, row):", (fov_col, fov_row))
        end_position_x = Ny % 2 # right side or left side
        fov_col = Nx - (fov_col + 1) if end_position_x else fov_col
        fov_row = fov_row
        print("fov - (col, row):", fov_col, fov_row)
        pixel_sign_x = (-1)**end_position_x # inverted
        pixel_sign_y = -1 if INVERTED_OBJECTIVE else 1
        print("pixel_sign_x, pixel_sign_y", pixel_sign_x, pixel_sign_y)
 
        # move to selected fov
        self.move_x_to(self.scan_begin_position_x+dx_mm*fov_col*pixel_sign_x)
        self.microcontroller.wait_till_operation_is_completed()
        self.move_y_to(self.scan_begin_position_y+dy_mm*fov_row*pixel_sign_y)
        self.microcontroller.wait_till_operation_is_completed()

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
            pixel_size_um = self.objectiveStore.get_pixel_size()

            pixel_sign_x = 1
            pixel_sign_y = 1 if INVERTED_OBJECTIVE else -1

            delta_x = pixel_sign_x * pixel_size_um * click_x / 1000.0
            delta_y = pixel_sign_y * pixel_size_um * click_y / 1000.0

            self.move_x(delta_x)
            self.microcontroller.wait_till_operation_is_completed()
            self.move_y(delta_y)
            self.microcontroller.wait_till_operation_is_completed()

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
        self.microcontroller.wait_till_operation_is_completed()
        self.move_y_to(y_mm)
        self.microcontroller.wait_till_operation_is_completed()

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

            image = utils.crop_image(image,self.crop_width,self.crop_height)
            image = utils.rotate_and_flip_image(image,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)
            self.image_to_display.emit(image)
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
    signal_update_stats = Signal(object)
    signal_z_piezo_um = Signal(float)
    napari_layers_init = Signal(int, int, object)
    napari_layers_update = Signal(np.ndarray, int, int, int, str) # image, i, j, k, channel
    napari_mosaic_update = Signal(np.ndarray, float, float, int, str) # image, x_mm, y_mm, k, channel
    napari_rtp_layers_update = Signal(np.ndarray, str)
    signal_acquisition_progress = Signal(int, int)
    signal_region_progress = Signal(int, int)

    def __init__(self,multiPointController):
        QObject.__init__(self)
        self.multiPointController = multiPointController

        self.signal_update_stats.connect(self.update_stats)
        self.start_time = 0
        if DO_FLUORESCENCE_RTP:
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
        self.af_fov_count = 0
        self.coordinate_dict = self.multiPointController.coordinate_dict
        self.use_scan_coordinates = self.multiPointController.use_scan_coordinates
        self.scan_coordinates_mm = self.multiPointController.scan_coordinates_mm
        self.scan_coordinates_name = self.multiPointController.scan_coordinates_name

        self.microscope = self.multiPointController.parent
        try:
            self.model = self.microscope.segmentation_model
        except:
            pass
        self.crop = SEGMENTATION_CROP

        self.t_dpc = []
        self.t_inf = []
        self.t_over = []

        if USE_NAPARI_FOR_MULTIPOINT or USE_NAPARI_FOR_TILED_DISPLAY:
            self.init_napari_layers = False

        self.tiled_preview = None
        self.count = 0
        

    def update_stats(self, new_stats):
        self.count += 1
        print("stats", self.count)
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
        if not self.camera.is_streaming:
            self.camera.start_streaming()

        while self.time_point < self.Nt:
            # check if abort acquisition has been requested
            if self.multiPointController.abort_acqusition_requested:
                break
            
            self.run_single_time_point()

            self.time_point = self.time_point + 1
            if self.dt == 0: # continous acquisition
                pass 
            else:  # timed acquisition

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

        elapsed_time = time.perf_counter_ns() - self.start_time
        print("Time taken for acquisition: " + str(elapsed_time/10**9))

        # End processing using the updated method
        if DO_FLUORESCENCE_RTP:
            self.processingHandler.processing_queue.join()
            self.processingHandler.upload_queue.join()
            self.processingHandler.end_processing()
        # time.sleep(0.2)
        # wait for signal_update_stats in process_fn_with_count_and_display
        print("Time taken for acquisition/processing: ", (time.perf_counter_ns() - self.start_time) / 1e9)
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
        self.initialize_coordinates_dataframe()

        # init z parameters
        self.initialize_z_stack()

        if self.coordinate_dict is not None:
            print("coordinate acquisition")
            self.run_coordinate_acquisition(current_path)
        else:
            print("grid acquisition")
            self.run_grid_acquisition(current_path)

        # finished region scan
        self.coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
        self.navigationController.enable_joystick_button_action = True
        print(time.time())
        print(time.time()-start)

    def initialize_z_stack(self):
        self.count_rtp = 0
        self.dz_usteps = 0 # accumulated z displacement
        self.z_pos = self.navigationController.z_pos # zpos at the beginning of the scan

        # z stacking config
        if Z_STACKING_CONFIG == 'FROM TOP':
            self.deltaZ_usteps = -abs(self.deltaZ_usteps)

        # reset piezo to home position
        if self.use_piezo:
            self.z_piezo_um = OBJECTIVE_PIEZO_HOME_UM
            dac = int(65535 * (self.z_piezo_um / OBJECTIVE_PIEZO_RANGE_UM))
            self.navigationController.microcontroller.analog_write_onboard_DAC(7, dac)
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE: # for hardware trigger, delay is in waiting for the last row to start exposure
                time.sleep(MULTIPOINT_PIEZO_DELAY_MS/1000)
            if MULTIPOINT_PIEZO_UPDATE_DISPLAY:
                self.signal_z_piezo_um.emit(self.z_piezo_um)

    def initialize_coordinates_dataframe(self):
        base_columns = ['z_level', 'x (mm)', 'y (mm)', 'z (um)', 'time']
        piezo_column = ['z_piezo (um)'] if self.use_piezo else []

        if IS_HCS:
            if self.coordinate_dict is not None:
                self.coordinates_pd = pd.DataFrame(columns=['region'] + base_columns + piezo_column)
            else:
                self.coordinates_pd = pd.DataFrame(columns=['region', 'i', 'j'] + base_columns + piezo_column)
        else:
            self.coordinates_pd = pd.DataFrame(columns=['i', 'j'] + base_columns + piezo_column)

    def update_coordinates_dataframe(self, region_id, i, j, z_level):
        base_data = {
            'z_level': [z_level],
            'x (mm)': [self.navigationController.x_pos_mm],
            'y (mm)': [self.navigationController.y_pos_mm],
            'z (um)': [self.navigationController.z_pos_mm * 1000],
            'time': [datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')]
        }
        piezo_data = {'z_piezo (um)': [self.z_piezo_um - OBJECTIVE_PIEZO_HOME_UM]} if self.use_piezo else {}

        if IS_HCS:
            if self.coordinate_dict is not None:
                new_row = pd.DataFrame({
                    'region': [region_id],
                    **base_data,
                    **piezo_data
                })
            else:
                new_row = pd.DataFrame({
                    'region': [self.scan_coordinates_name[region_id]],
                    'i': [i], 'j': [j],
                    **base_data,
                    **piezo_data
                })
        else:
            new_row = pd.DataFrame({
                'i': [i], 'j': [j],
                **base_data,
                **piezo_data
            })

        self.coordinates_pd = pd.concat([self.coordinates_pd, new_row], ignore_index=True)

    def calculate_grid_indices(self, i, j):
        # Ensure that i/y-indexing is always top to bottom
        sgn_i = -1 if self.deltaY >= 0 else 1
        sgn_i = -sgn_i if INVERTED_OBJECTIVE else sgn_i
        sgn_j = self.x_scan_direction if self.deltaX >= 0 else -self.x_scan_direction

        real_i = self.NY-1-i if sgn_i == -1 else i
        real_j = self.NX-1-j if sgn_j == -1 else j

        return sgn_i, sgn_j, real_i, real_j


    def move_to_coordinate(self, coordinate_mm):
        x_mm = coordinate_mm[0]
        self.navigationController.move_x_to(x_mm)
        self.wait_till_operation_is_completed()
        time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)

        y_mm = coordinate_mm[1]
        self.navigationController.move_y_to(y_mm)
        self.wait_till_operation_is_completed()
        time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
        
        # check if z is included in the coordinate
        if len(coordinate_mm) == 3:
            z_mm = coordinate_mm[2]
            if z_mm >= self.navigationController.z_pos_mm:
                self.navigationController.move_z_to(z_mm)
                self.wait_till_operation_is_completed()
            else:
                self.navigationController.move_z_to(z_mm)
                self.wait_till_operation_is_completed()
                # remove backlash
                if self.navigationController.get_pid_control_flag(2) is False:
                    _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
                    self.navigationController.move_z_usteps(-_usteps_to_clear_backlash) # to-do: combine this with the above
                    self.wait_till_operation_is_completed()
                    self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                    self.wait_till_operation_is_completed()
            time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

    def run_grid_acquisition(self, current_path):
        n_regions = len(self.scan_coordinates_mm)

        for region_id in range(n_regions):
            self.signal_acquisition_progress.emit(region_id + 1, n_regions)
            coordinate_mm = self.scan_coordinates_mm[region_id]

            self.x_scan_direction = 1
            self.dx_usteps = 0 # accumulated x displacement
            self.dy_usteps = 0 # accumulated y displacement

            if self.use_scan_coordinates:
                # Calculate grid size
                grid_size_x_mm = (self.NX - 1) * self.deltaX
                grid_size_y_mm = (self.NY - 1) * self.deltaY

                # Calculate top-left corner position
                start_x = coordinate_mm[0] - grid_size_x_mm / 2
                start_y = coordinate_mm[1] - grid_size_y_mm / 2
                if len(coordinate_mm) == 3:
                    self.move_to_coordinate([start_x, start_y, coordinate_mm[2]])
                else:
                    self.move_to_coordinate([start_x, start_y])

                self.wait_till_operation_is_completed()

            num_fovs = self.NX * self.NY - len(self.multiPointController.scanCoordinates.grid_skip_positions)
            fov_count = 0 # count fovs for progress

            for i in range(self.NY):
                self.af_fov_count = 0 # for AF, so that AF at the beginning of each new row

                for j in range(self.NX):
                    sgn_i, sgn_j, real_i, real_j = self.calculate_grid_indices(i, j)

                    if not self.multiPointController.scanCoordinates or (real_i, real_j) not in self.multiPointController.scanCoordinates.grid_skip_positions:
                        self.acquire_at_position(region_id, current_path, real_i, real_j)

                        fov_count += 1
                        self.signal_region_progress.emit(fov_count, num_fovs)

                    if self.multiPointController.abort_acqusition_requested:
                        self.handle_acquisition_abort(current_path, region_id)
                        return

                    if j < self.NX - 1:
                        self.move_to_next_x_position()

                if i < self.NY - 1:
                    self.move_to_next_y_position()

                self.x_scan_direction = -self.x_scan_direction

            self.finish_grid_scan(n_regions, region_id)

    def run_coordinate_acquisition(self, current_path):
        n_regions = len(self.scan_coordinates_mm)

        for region_index, (region_id, coordinates) in enumerate(self.coordinate_dict.items()):

            self.signal_acquisition_progress.emit(region_index + 1, n_regions)

            num_fovs = len(coordinates)

            for fov_count, coordinate_mm in enumerate(coordinates):

                self.move_to_coordinate(coordinate_mm)

                self.acquire_at_position(region_id, current_path)

                self.signal_region_progress.emit(fov_count, num_fovs)

                if self.multiPointController.abort_acqusition_requested:
                    self.handle_acquisition_abort(current_path, region_id)
                    return

    def acquire_at_position(self, region_id, current_path, i=None, j=None):

        self.perform_autofocus(region_id)

        if self.NZ > 1:
            self.prepare_z_stack()
        
        if self.coordinate_dict is not None:
            coordinate_name = region_id
        else:
            coordinate_name = self.scan_coordinates_name[region_id]

        x_mm = self.navigationController.x_pos_mm
        y_mm = self.navigationController.y_pos_mm

        for z_level in range(self.NZ):
            if i is not None and j is not None:
                file_ID = f"{coordinate_name}_{i}_{j}_{z_level}"
            else:
                file_ID = f"{coordinate_name}_x{x_mm:.3f}_y{y_mm:.3f}_z{z_level}"

            metadata = dict(x = self.navigationController.x_pos_mm, y = self.navigationController.y_pos_mm, z = self.navigationController.z_pos_mm)
            print("ID:", file_ID, "\nScan Coordinate:", metadata)
            
            # laser af characterization mode
            if LASER_AF_CHARACTERIZATION_MODE:
                image = self.microscope.laserAutofocusController.get_image()
                saving_path = os.path.join(current_path, file_ID + '_laser af camera' + '.bmp')
                iio.imwrite(saving_path,image)

            current_round_images = {}
            # iterate through selected modes
            for config in self.selected_configurations:

                self.handle_z_offset(config)

                # acquire image
                if 'USB Spectrometer' not in config.name and 'RGB' not in config.name:
                    self.acquire_camera_image(config, file_ID, current_path, current_round_images, i, j, z_level)
                elif 'RGB' in config.name:
                    self.acquire_rgb_image(config, file_ID, current_path, current_round_images, i, j, z_level)
                else:
                    self.acquire_spectrometer_data(config, file_ID, current_path, i, j, z_level)

                self.undo_z_offset(config)

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
                self.tiled_preview[real_i*height:(real_i+1)*height, real_j*width:(real_j+1)*width, ] = I
                # emit the result
                self.image_to_display_tiled_preview.emit(self.tiled_preview)

            # real time processing 
            acquired_image_configs = list(current_round_images.keys())
            if 'BF LED matrix left half' in current_round_images and 'BF LED matrix right half' in current_round_images and 'Fluorescence 405 nm Ex' in current_round_images and self.multiPointController.do_fluorescence_rtp:
                try:
                    print("real time processing", self.count_rtp)
                    if (self.microscope.model is None) or (self.microscope.device is None) or (self.microscope.classification_th is None) or (self.microscope.dataHandler is None):
                        raise AttributeError('microscope missing model, device, classification_th, and/or dataHandler')
                    I_fluorescence = current_round_images['Fluorescence 405 nm Ex']
                    I_left = current_round_images['BF LED matrix left half']
                    I_right = current_round_images['BF LED matrix right half']
                    if len(I_left.shape) == 3:
                        I_left = cv2.cvtColor(I_left,cv2.COLOR_RGB2GRAY)
                    if len(I_right.shape) == 3:
                        I_right = cv2.cvtColor(I_right,cv2.COLOR_RGB2GRAY)
                    malaria_rtp(I_fluorescence, I_left, I_right, i, j, z_level, self,
                                classification_test_mode=self.microscope.classification_test_mode,
                                sort_during_multipoint=SORT_DURING_MULTIPOINT,
                                disp_th_during_multipoint=DISP_TH_DURING_MULTIPOINT)
                    self.count_rtp += 1
                except AttributeError as e:
                    print(repr(e))

            self.update_coordinates_dataframe(region_id, i, j, z_level)
            self.signal_register_current_fov.emit(self.navigationController.x_pos_mm, self.navigationController.y_pos_mm)

            # check if the acquisition should be aborted
            if self.multiPointController.abort_acqusition_requested:
                self.handle_acquisition_abort(current_path, region_id)
                return

            # update FOV counter
            self.af_fov_count = self.af_fov_count + 1

            if z_level < self.NZ - 1:
                self.move_z_for_stack()

        if self.NZ > 1:
            self.move_z_back_after_stack()

    def perform_autofocus(self, region_id):
        if self.do_reflection_af == False:
            # contrast-based AF; perform AF only if when not taking z stack or doing z stack from center
            if ( (self.NZ == 1) or Z_STACKING_CONFIG == 'FROM CENTER' ) and (self.do_autofocus) and (self.af_fov_count%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
                configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                config_AF = next((config for config in self.configurationManager.configurations if config.name == configuration_name_AF))
                self.signal_current_configuration.emit(config_AF)
                if (self.af_fov_count%Acquisition.NUMBER_OF_FOVS_PER_AF==0) or self.autofocusController.use_focus_map:
                    self.autofocusController.autofocus()
                    self.autofocusController.wait_till_autofocus_has_completed()
                # update z location of scan_coordinates_mm after AF
                if len(self.scan_coordinates_mm[region_id]) == 3:
                    self.scan_coordinates_mm[region_id][2] = self.navigationController.z_pos_mm
                    # update the coordinate in the widget
                    if self.coordinate_dict is not None:
                        self.microscope.multiPointWidgetGrid.update_z_level(region_id, self.navigationController.z_pos_mm)
                    elif self.multiPointController.location_list is not None:
                        try:
                            self.microscope.multiPointWidget2._update_z(region_id, self.navigationController.z_pos_mm)
                        except:
                            print("failed update flexible widget z")
                            pass
                        try:
                            self.microscope.multiPointWidgetGrid.update_z_level(region_id, self.navigationController.z_pos_mm)
                        except:
                            print("failed update grid widget z")
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
                    file_ID = f"{region_id}_focus_camera.bmp"
                    saving_path = os.path.join(self.base_path, self.experiment_ID, str(self.time_point), file_ID)
                    iio.imwrite(saving_path, self.microscope.laserAutofocusController.image) 
                    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! laser AF failed !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')

    def prepare_z_stack(self):
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

    def handle_z_offset(self, config):
        if config.z_offset is not None:  # perform z offset for config, assume z_offset is in um
            if config.z_offset != 0.0:
                print("Moving to Z offset "+str(config.z_offset))
                self.navigationController.move_z(config.z_offset/1000)
                self.wait_till_operation_is_completed()
                time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

    def undo_z_offset(self, config):
        if config.z_offset is not None:  # undo Z offset, assume z_offset is in um
            if config.z_offset != 0.0:
                print("Moving back from Z offset "+str(config.z_offset))
                self.navigationController.move_z(-config.z_offset/1000)
                self.wait_till_operation_is_completed()
                time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

    def acquire_camera_image(self, config, file_ID, current_path, current_round_images, i, j, k):
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
            return

        # turn off the illumination if using software trigger
        if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
            self.liveController.turn_off_illumination()

        # process the image -  @@@ to move to camera
        image = utils.crop_image(image,self.crop_width,self.crop_height)
        image = utils.rotate_and_flip_image(image,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)

        image_to_display = utils.crop_image(image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling))
        self.image_to_display.emit(image_to_display)
        self.image_to_display_multi.emit(image_to_display,config.illumination_source)

        self.save_image(image, file_ID, config, current_path)
        self.update_napari(image, config.name, i, j, k)

        current_round_images[config.name] = np.copy(image)

        self.handle_dpc_generation(current_round_images)
        self.handle_rgb_generation(current_round_images, file_ID, current_path, i, j, k)

        QApplication.processEvents()

    def acquire_rgb_image(self, config, file_ID, current_path, current_round_images, i, j, k):
        # go through the channels
        rgb_channels = ['BF LED matrix full_R', 'BF LED matrix full_G', 'BF LED matrix full_B']
        images = {}

        for config_ in self.configurationManager.configurations:
            if config_.name in rgb_channels:
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
            self.handle_rgb_channels(images, file_ID, current_path, config, i, j, k)
        else:
            # If monochrome, reconstruct RGB image
            print('constructing RGB image')
            self.construct_rgb_image(images, file_ID, current_path, config, i, j, k)

    def acquire_spectrometer_data(self, config, file_ID, current_path):
        if self.usb_spectrometer != None:
            for l in range(N_SPECTRUM_PER_POINT):
                data = self.usb_spectrometer.read_spectrum()
                self.spectrum_to_display.emit(data)
                saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '_' + str(l) + '.csv')
                np.savetxt(saving_path,data,delimiter=',')

    def save_image(self, image, file_ID, config, current_path):
        if image.dtype == np.uint16:
            saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.tiff')
        else:
            saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.' + Acquisition.IMAGE_FORMAT)
        
        if self.camera.is_color:
            if 'BF LED matrix' in config.name:
                if MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
                    image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
                    image = image[:,:,1]
        iio.imwrite(saving_path,image)

    def update_napari(self, image, config_name, i, j, k):
        i = -1 if i is None else i
        j = -1 if j is None else j
        print("update napari:", i, j, k, config_name)

        if USE_NAPARI_FOR_MULTIPOINT or USE_NAPARI_FOR_TILED_DISPLAY:
            if not self.init_napari_layers:
                print("init napari layers")
                self.init_napari_layers = True
                self.napari_layers_init.emit(image.shape[0],image.shape[1], image.dtype)
            self.napari_layers_update.emit(image, i, j, k, config_name)
        if USE_NAPARI_FOR_MOSAIC_DISPLAY:
            self.napari_mosaic_update.emit(image, self.navigationController.x_pos_mm, self.navigationController.y_pos_mm, k, config_name)

    def handle_dpc_generation(self, current_round_images):
        keys_to_check = ['BF LED matrix left half', 'BF LED matrix right half', 'BF LED matrix top half', 'BF LED matrix bottom half']
        if all(key in current_round_images for key in keys_to_check):
            # generate dpc
            pass

    def handle_rgb_generation(self, current_round_images, file_ID, current_path, i, j, k):
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

    def handle_rgb_channels(self, images, file_ID, current_path, config, i, j, k):
        for channel in ['BF LED matrix full_R', 'BF LED matrix full_G', 'BF LED matrix full_B']:
            image_to_display = utils.crop_image(images[channel], round(self.crop_width * self.display_resolution_scaling), round(self.crop_height * self.display_resolution_scaling))
            self.image_to_display.emit(image_to_display)
            self.image_to_display_multi.emit(image_to_display, config.illumination_source)

            self.update_napari(images[channel], channel, i, j, k)

            file_name = file_ID + '_' + channel.replace(' ', '_') + ('.tiff' if images[channel].dtype == np.uint16 else '.' + Acquisition.IMAGE_FORMAT)
            iio.imwrite(os.path.join(current_path, file_name), images[channel])

    def construct_rgb_image(self, images, file_ID, current_path, config, i, j, k):
        rgb_image = np.zeros((*images['BF LED matrix full_R'].shape, 3), dtype=images['BF LED matrix full_R'].dtype)
        rgb_image[:, :, 0] = images['BF LED matrix full_R']
        rgb_image[:, :, 1] = images['BF LED matrix full_G']
        rgb_image[:, :, 2] = images['BF LED matrix full_B']

        # send image to display
        image_to_display = utils.crop_image(rgb_image, round(self.crop_width * self.display_resolution_scaling), round(self.crop_height * self.display_resolution_scaling))
        self.image_to_display.emit(image_to_display)
        self.image_to_display_multi.emit(image_to_display, config.illumination_source)

        self.update_napari(rgb_image, config.name, i, j, k)

        # write the RGB image
        print('writing RGB image')
        file_name = file_ID + '_BF_LED_matrix_full_RGB' + ('.tiff' if rgb_image.dtype == np.uint16 else '.' + Acquisition.IMAGE_FORMAT)
        iio.imwrite(os.path.join(current_path, file_name), rgb_image)

    def handle_acquisition_abort(self, current_path, region_id=0):
        if self.coordinate_dict is None:
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
        else:
            self.move_to_coordinate(self.scan_coordinates_mm[region_id])

        self.coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
        self.navigationController.enable_joystick_button_action = True

    def move_to_next_x_position(self):
        self.navigationController.move_x_usteps(self.x_scan_direction*self.deltaX_usteps)
        self.wait_till_operation_is_completed()
        time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)
        self.dx_usteps = self.dx_usteps + self.x_scan_direction*self.deltaX_usteps

    def move_to_next_y_position(self):
        self.navigationController.move_y_usteps(self.deltaY_usteps)
        self.wait_till_operation_is_completed()
        time.sleep(SCAN_STABILIZATION_TIME_MS_Y/1000)
        self.dy_usteps = self.dy_usteps + self.deltaY_usteps

    def move_z_for_stack(self):
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

    def move_z_back_after_stack(self):
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

    def finish_grid_scan(self, n_regions, region_id):
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
                self.navigationController.microcontroller.move_z_to_usteps(self.z_pos - STAGE_MOVEMENT_SIGN_Z*_usteps_to_clear_backlash)
                self.wait_till_operation_is_completed()
                self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                self.wait_till_operation_is_completed()
            else:
                self.navigationController.microcontroller.move_z_to_usteps(self.z_pos)
                self.wait_till_operation_is_completed()

    def update_tiled_preview(self, current_round_images, i, j, k):
        if SHOW_TILED_PREVIEW and 'BF LED matrix full' in current_round_images:
            # initialize the variable
            if self.tiled_preview is None:
                size = current_round_images['BF LED matrix full'].shape
                if len(size) == 2:
                    self.tiled_preview = np.zeros((int(self.NY*size[0]/PRVIEW_DOWNSAMPLE_FACTOR),self.NX*int(size[1]/PRVIEW_DOWNSAMPLE_FACTOR)),dtype=current_round_images['BF LED matrix full'].dtype)
                else:
                    self.tiled_preview = np.zeros((int(self.NY*size[0]/PRVIEW_DOWNSAMPLE_FACTOR),self.NX*int(size[1]/PRVIEW_DOWNSAMPLE_FACTOR),size[2]),dtype=current_round_images['BF LED matrix full'].dtype)
            # downsample the image
            I = current_round_images['BF LED matrix full']
            width = int(I.shape[1]/PRVIEW_DOWNSAMPLE_FACTOR)
            height = int(I.shape[0]/PRVIEW_DOWNSAMPLE_FACTOR)
            I = cv2.resize(I, (width,height), interpolation=cv2.INTER_AREA)
            # populate the tiled_preview
            self.tiled_preview[i*height:(i+1)*height, j*width:(j+1)*width,] = I
            # emit the result
            self.image_to_display_tiled_preview.emit(self.tiled_preview)


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
    napari_layers_init = Signal(int, int, object)
    napari_layers_update = Signal(np.ndarray, int, int, int, str) # image, i, j, k, channel
    napari_mosaic_update = Signal(np.ndarray, float, float, int, str) # image, x_mm, y_mm, k, channel
    signal_z_piezo_um = Signal(float)
    signal_acquisition_progress = Signal(int, int)
    signal_region_progress = Signal(int, int)

    def __init__(self,camera,navigationController,liveController,autofocusController,configurationManager,usb_spectrometer=None,scanCoordinates=None,parent=None):
        QObject.__init__(self)

        self.camera = camera
        if DO_FLUORESCENCE_RTP:
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
        self.scan_coordinates_mm = []
        self.scan_coordinates_name = []
        self.parent = parent
        self.start_time = 0
        self.old_images_per_page = 1
        try:
            if self.parent is not None:
                self.old_images_per_page = self.parent.dataHandler.n_images_per_page
        except:
            pass
        self.location_list = None # for flexible multipoint
        self.coordinate_dict = None # for coordinate grid vs postion grid

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

    def set_crop(self,crop_width, crop_height):
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
        # TODO: USE OBJECTIVE STORE DATA
        acquisition_parameters['sensor_pixel_size_um'] = CAMERA_PIXEL_SIZE_UM[CAMERA_SENSOR]
        acquisition_parameters['tube_lens_mm'] = TUBE_LENS_MM
        f = open(os.path.join(self.base_path,self.experiment_ID)+"/acquisition parameters.json","w")
        f.write(json.dumps(acquisition_parameters))
        f.close()

    def set_selected_configurations(self, selected_configurations_name):
        self.selected_configurations = []
        for configuration_name in selected_configurations_name:
            self.selected_configurations.append(next((config for config in self.configurationManager.configurations if config.name == configuration_name)))
        
    def run_acquisition(self, location_list=None, coordinate_dict=None):
        print('start multipoint')
        
        if coordinate_dict is not None:
            print('Using coordinate-based acquisition')
            total_points = sum(len(coords) for coords in coordinate_dict)
            self.coordinate_dict = coordinate_dict
            self.location_list = None
            self.use_scan_coordinates = False
            self.scan_coordinates_mm = location_list
            self.scan_coordinates_name = list(coordinate_dict.keys()) # list(coordinate_dict.keys()) if not wellplate
        elif location_list is not None:
            print('Using location list acquisition')
            self.coordinate_dict = None
            self.location_list = location_list
            self.use_scan_coordinates = True
            self.scan_coordinates_mm = location_list
            self.scan_coordinates_name = [f'R{i}' for i in range(len(location_list))]
        else:
            print(f"t_c_z_y_x: {self.Nt}_{len(self.selected_configurations)}_{self.NZ}_{self.NY}_{self.NX}")
            self.coordinate_dict = None
            self.location_list = None
            if self.scanCoordinates is not None and self.scanCoordinates.get_selected_wells():
                print('Using well plate scan')
                self.use_scan_coordinates = True
                self.scan_coordinates_mm = self.scanCoordinates.coordinates_mm
                self.scan_coordinates_name = self.scanCoordinates.name
            else:
                print('Using current location')
                self.use_scan_coordinates = False
                self.scan_coordinates_mm = [(self.navigationController.x_pos_mm, self.navigationController.y_pos_mm)]
                self.scan_coordinates_name = ['ROI']

        print("num regions:",len(self.scan_coordinates_mm))
        print("region ids:", self.scan_coordinates_name)
        print("region coordinates:", self.scan_coordinates_mm)

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
            
            elif USE_NAPARI_FOR_MOSAIC_DISPLAY and self.coordinate_dict is not None:
                self.parent.imageDisplayTabs.setCurrentWidget(self.parent.napariMosaicDisplayWidget)
                # self.parent.imageDisplayTabs. # disable naparitileddisplaywidget tab

            elif USE_NAPARI_FOR_TILED_DISPLAY:
                self.parent.imageDisplayTabs.setCurrentWidget(self.parent.napariTiledDisplayWidget)
            
            elif USE_NAPARI_FOR_MULTIPOINT:
                self.parent.imageDisplayTabs.setCurrentWidget(self.parent.napariMultiChannelWidget)
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
        if DO_FLUORESCENCE_RTP:
            self.processingHandler.start_processing()
            self.processingHandler.start_uploading()
        self.multiPointWorker = MultiPointWorker(self)
        # move the worker to the thread
        self.multiPointWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.multiPointWorker.run)
        self.multiPointWorker.signal_detection_stats.connect(self.slot_detection_stats)
        self.multiPointWorker.finished.connect(self._on_acquisition_completed)
        if DO_FLUORESCENCE_RTP:
            self.processingHandler.finished.connect(self.multiPointWorker.deleteLater)
            self.processingHandler.finished.connect(self.thread.quit)
        else:
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
        self.multiPointWorker.napari_mosaic_update.connect(self.slot_napari_mosaic_update)
        self.multiPointWorker.signal_z_piezo_um.connect(self.slot_z_piezo_um)
        self.multiPointWorker.signal_acquisition_progress.connect(self.slot_acquisition_progress)
        self.multiPointWorker.signal_region_progress.connect(self.slot_region_progress)

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
        if self.parent is not None:
            try:
                # self.parent.dataHandler.set_number_of_images_per_page(self.old_images_per_page)
                self.parent.dataHandler.sort('Sort by prediction score')
                self.parent.dataHandler.signal_populate_page0.emit()
            except:
                pass
        print("total time for acquisition + processing + reset:", time.time() - self.recording_start_time)
        self.acquisitionFinished.emit()
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

    def slot_napari_layers_init(self, image_height, image_width, dtype):
        self.napari_layers_init.emit(image_height, image_width, dtype)

    def slot_napari_layers_update(self, image, i, j, k, channel):
        self.napari_layers_update.emit(image, i, j, k, channel)

    def slot_napari_mosaic_update(self, image, x_mm, y_mm, k, channel):
        self.napari_mosaic_update.emit(image, x_mm, y_mm, k, channel)

    def slot_z_piezo_um(self, displacement_um):
        self.signal_z_piezo_um.emit(displacement_um)

    def slot_acquisition_progress(self, current_region, total_regions):
        self.signal_acquisition_progress.emit(current_region, total_regions)

    def slot_region_progress(self, current_fov, total_fovs):
        self.signal_region_progress.emit(current_fov, total_fovs)


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

    signal_draw_scan_grid = Signal(float, float)

    def __init__(self, objectivestore, sample = 'glass slide', invertX = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.sample = sample
        self.objectiveStore = objectivestore
        self.well_size_mm = WELL_SIZE_MM
        self.well_spacing_mm = WELL_SPACING_MM
        self.number_of_skip = NUMBER_OF_SKIP
        self.a1_x_mm = A1_X_MM
        self.a1_y_mm = A1_Y_MM
        self.a1_x_pixel = A1_X_PIXEL
        self.a1_y_pixel = A1_Y_PIXEL
        self.location_update_threshold_mm = 0.2
        self.box_color = (255, 0, 0)
        self.box_line_thickness = 2
        self.acquisition_size = Acquisition.CROP_HEIGHT
        self.x_mm = None
        self.y_mm = None
        self.acquisition_started = False

        print("navigation viewer:", sample)
        self.init_ui(invertX)
        self.load_background_image(sample)
        self.create_layers()
        self.update_display_properties(sample)
        # self.update_display()

    def init_ui(self, invertX):
        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setBackground("w")

        self.view = self.graphics_widget.addViewBox(invertX=invertX, invertY=True)
        self.view.setAspectLocked(True)

        self.grid = QVBoxLayout()
        self.grid.addWidget(self.graphics_widget)
        self.setLayout(self.grid)

    def load_background_image(self, sample):
        image_paths = {
            'glass slide': 'images/slide carrier_828x662.png',
            '6 well plate': 'images/6 well plate_1509x1010.png',
            '12 well plate': 'images/12 well plate_1509x1010.png',
            '24 well plate': 'images/24 well plate_1509x1010.png',
            '96 well plate': 'images/96 well plate_1509x1010.png',
            '384 well plate': 'images/384 well plate_1509x1010.png',
            '1536 well plate': 'images/1536 well plate_1509x1010.png'
        }
        self.view.clear()
        self.background_image = cv2.imread(image_paths.get(sample, 'images/slide carrier_828x662.png'))
        if len(self.background_image.shape) == 2:  # Grayscale image
            self.background_image = cv2.cvtColor(self.background_image, cv2.COLOR_GRAY2RGBA)
        elif self.background_image.shape[2] == 3:  # BGR image
            self.background_image = cv2.cvtColor(self.background_image, cv2.COLOR_BGR2RGBA)
        elif self.background_image.shape[2] == 4:  # BGRA image
            self.background_image = cv2.cvtColor(self.background_image, cv2.COLOR_BGRA2RGBA)

        self.background_image_copy = self.background_image.copy()
        self.image_height, self.image_width = self.background_image.shape[:2]
        self.background_item = pg.ImageItem(self.background_image)
        self.view.addItem(self.background_item)

    def create_layers(self):
        self.scan_overlay = np.zeros((self.image_height, self.image_width, 4), dtype=np.uint8)
        self.fov_overlay = np.zeros((self.image_height, self.image_width, 4), dtype=np.uint8)
        
        self.scan_overlay_item = pg.ImageItem()
        self.fov_overlay_item = pg.ImageItem()
        
        self.view.addItem(self.scan_overlay_item)
        self.view.addItem(self.fov_overlay_item)

    def update_display_properties(self, sample):
        if sample == 'glass slide':
            self.location_update_threshold_mm = 0.2
            self.mm_per_pixel = 0.1453
            self.origin_x_pixel = 200
            self.origin_y_pixel = 120
            if IS_HCS:
                self.view.invertX(True)
                self.view.invertY(False)
        else:
            self.location_update_threshold_mm = 0.05
            self.mm_per_pixel = 0.084665
            self.origin_x_pixel = self.a1_x_pixel - (self.a1_x_mm)/self.mm_per_pixel
            self.origin_y_pixel = self.a1_y_pixel - (self.a1_y_mm)/self.mm_per_pixel
            self.view.invertX(False)
            self.view.invertY(True)
        self.update_fov_size()

    def update_fov_size(self):
        pixel_size_um = self.objectiveStore.get_pixel_size()
        self.fov_size_mm = self.acquisition_size * pixel_size_um / 1000

    def on_objective_changed(self):
        self.clear_overlay()
        self.update_fov_size()
        if self.x_mm is not None and self.y_mm is not None:
            if self.sample == 'glass slide':
                self.signal_draw_scan_grid.emit(self.x_mm, self.y_mm)
            self.draw_current_fov(self.x_mm, self.y_mm)

    def on_acquisition_start(self, acquisition_started):
        self.acquisition_started = acquisition_started

    def update_wellplate_settings(self, sample_format, a1_x_mm, a1_y_mm, a1_x_pixel, a1_y_pixel, well_size_mm, well_spacing_mm, number_of_skip):
        if sample_format == 0:
            sample = 'glass slide'
        else:
            sample = f'{sample_format} well plate'
        self.sample = sample
        self.a1_x_mm = a1_x_mm
        self.a1_y_mm = a1_y_mm
        self.a1_x_pixel = a1_x_pixel
        self.a1_y_pixel = a1_y_pixel
        self.well_size_mm = well_size_mm
        self.well_spacing_mm = well_spacing_mm
        self.number_of_skip = number_of_skip
        self.load_background_image(sample)
        self.create_layers()
        self.update_display_properties(sample)
        self.draw_current_fov(self.x_mm,self.y_mm)

    def update_current_location(self, x_mm=None, y_mm=None):
        if x_mm is None and y_mm is None:
            self.draw_current_fov(self.x_mm, self.y_mm)

        elif self.x_mm is not None and self.y_mm is not None:
            # update only when the displacement has exceeded certain value
            if abs(x_mm - self.x_mm) > self.location_update_threshold_mm or abs(y_mm - self.y_mm) > self.location_update_threshold_mm:
                self.draw_current_fov(x_mm, y_mm)
                self.x_mm = x_mm
                self.y_mm = y_mm
                # update_live_scan_grid
                if self.sample == 'glass slide' and not self.acquisition_started:
                    self.signal_draw_scan_grid.emit(x_mm, y_mm)
        else:
            self.draw_current_fov(x_mm, y_mm)
            self.x_mm = x_mm
            self.y_mm = y_mm
            # update_live_scan_grid
            if self.sample == 'glass slide' and not self.acquisition_started:
                self.signal_draw_scan_grid.emit(x_mm, y_mm)

    def get_FOV_pixel_coordinates(self, x_mm, y_mm):
        if self.sample == 'glass slide':
            if INVERTED_OBJECTIVE:
                current_FOV_top_left = (
                    round(self.image_width - (self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel)),
                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel)
                )
                current_FOV_bottom_right = (
                    round(self.image_width - (self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel)),
                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel)
                )
            else:
                current_FOV_top_left = (
                    round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel)
                )
                current_FOV_bottom_right = (
                    round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                    round(self.image_height - (self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel)
                )
        else:
            current_FOV_top_left = (
                round(self.origin_x_pixel + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                round((self.origin_y_pixel + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel)
            )
            current_FOV_bottom_right = (
                round(self.origin_x_pixel + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                round((self.origin_y_pixel + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel)
            )
        return current_FOV_top_left, current_FOV_bottom_right

    def draw_current_fov(self, x_mm, y_mm):
        self.fov_overlay.fill(0)
        current_FOV_top_left, current_FOV_bottom_right = self.get_FOV_pixel_coordinates(x_mm, y_mm)
        cv2.rectangle(self.fov_overlay, current_FOV_top_left, current_FOV_bottom_right, (255, 0, 0, 255), self.box_line_thickness)
        self.fov_overlay_item.setImage(self.fov_overlay)

    def register_fov(self, x_mm, y_mm):
        color = (0, 0, 255, 255)  # Blue RGBA
        current_FOV_top_left, current_FOV_bottom_right = self.get_FOV_pixel_coordinates(x_mm, y_mm)
        cv2.rectangle(self.background_image, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)
        self.background_item.setImage(self.background_image)

    def register_fov_to_image(self, x_mm, y_mm):
        color = (252, 174, 30, 128)  # Yellow RGBA
        current_FOV_top_left, current_FOV_bottom_right = self.get_FOV_pixel_coordinates(x_mm, y_mm)
        cv2.rectangle(self.scan_overlay, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)
        self.scan_overlay_item.setImage(self.scan_overlay)

    def deregister_fov_to_image(self, x_mm, y_mm):
        current_FOV_top_left, current_FOV_bottom_right = self.get_FOV_pixel_coordinates(x_mm, y_mm)
        cv2.rectangle(self.scan_overlay, current_FOV_top_left, current_FOV_bottom_right, (0, 0, 0, 0), self.box_line_thickness)
        self.scan_overlay_item.setImage(self.scan_overlay)

    def clear_slide(self):
        self.background_image = self.background_image_copy.copy()
        self.background_item.setImage(self.background_image)
        self.clear_overlay()
        self.draw_current_fov(self.x_mm, self.y_mm)

    def clear_overlay(self):
        self.scan_overlay.fill(0)
        self.scan_overlay_item.setImage(self.scan_overlay)


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
            print("name:", mode.get('Name'), "color:", self.get_channel_color(mode.get('Name')))
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
        self.format = WELLPLATE_FORMAT
        self.a1_x_mm = A1_X_MM
        self.a1_y_mm = A1_Y_MM
        self.wellplate_offset_x_mm = WELLPLATE_OFFSET_X_mm
        self.wellplate_offset_y_mm = WELLPLATE_OFFSET_Y_mm
        self.well_spacing_mm = WELL_SPACING_MM
        self.well_size_mm = WELL_SIZE_MM
        self.grid_skip_positions = []

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

    def update_wellplate_settings(self, format_, a1_x_mm, a1_y_mm, a1_x_pixel, a1_y_pixel, size_mm, spacing_mm, number_of_skip):
        self.format = format_
        self.a1_x_mm = a1_x_mm
        self.a1_y_mm = a1_y_mm
        self.a1_x_pixel = a1_x_pixel
        self.a1_y_pixel = a1_y_pixel
        self.well_size_mm = size_mm
        self.well_spacing_mm = spacing_mm
        self.number_of_skip = number_of_skip

    def get_selected_wells(self):
        # get selected wells from the widget
        print("getting selected wells for acquisition")
        if not self.well_selector or self.format == 0:
            return False
        selected_wells = self.well_selector.get_selected_cells()
        selected_wells = np.array(selected_wells)
        # clear the previous selection
        self.coordinates_mm = []
        self.name = []
        if len(selected_wells) == 0:
            return False # if no well selected
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
                x_mm = self.a1_x_mm + column*self.well_spacing_mm + self.wellplate_offset_x_mm
                y_mm = self.a1_y_mm + row*self.well_spacing_mm + self.wellplate_offset_y_mm
                print("Scan Coordinates:", (x_mm, y_mm))
                self.coordinates_mm.append((x_mm,y_mm))
                self.name.append(self._index_to_row(row)+str(column+1))
            _increasing = not _increasing
        return len(selected_wells) # if wells selected


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
