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
from control.core import *
import control.tracking as tracking

from queue import Queue
from threading import Thread, Lock
import time
import numpy as np
import pyqtgraph as pg
import cv2
from datetime import datetime

import skimage # pip3 install -U scikit-image
import skimage.registration

class PDAFController(QObject):

    # input: stream from camera 1, stream from camera 2
    # input: from internal_states shared variables
    # output: amount of defocus, which may be read by or emitted to focusTrackingController (that manages focus tracking on/off, PID coefficients)

    def __init__(self,internal_states):
        QObject.__init__(self)
        self.coefficient_shift2defocus = 1
        self.registration_upsample_factor = 5
        self.image1_received = False
        self.image2_received = False
        self.locked = False
        self.shared_variables = internal_states

    def register_image_from_camera_1(self,image):
        if(self.locked==True):
            return
        self.image1 = np.copy(image)
        self.image1_received = True
        if(self.image2_received):
            self.calculate_defocus()

    def register_image_from_camera_2(self,image):
        if(self.locked==True):
            return
        self.image2 = np.copy(image)
        self.image2 = np.fliplr(self.image2) # can be flipud depending on camera orientation
        self.image2_received = True
        if(self.image1_received):
            self.calculate_defocus()

    def calculate_defocus(self):
        self.locked = True
        # cropping parameters
        self.x = self.shared_variables.x
        self.y = self.shared_variables.y
        self.w = self.shared_variables.w*2 # double check which dimension to multiply
        self.h = self.shared_variables.h
        # crop
        self.image1 = self.image1[(self.y-int(self.h/2)):(self.y+int(self.h/2)),(self.x-int(self.w/2)):(self.x+int(self.w/2))]
        self.image2 = self.image2[(self.y-int(self.h/2)):(self.y+int(self.h/2)),(self.x-int(self.w/2)):(self.x+int(self.w/2))] # additional offsets may need to be added
        shift = self._compute_shift_from_image_pair()
        self.defocus = shift*self.coefficient_shift2defocus
        self.image1_received = False
        self.image2_received = False
        self.locked = False

    def _compute_shift_from_image_pair(self):
        # method 1: calculate 2D cross correlation -> find peak or centroid
        '''
        I1 = np.array(self.image1,dtype=np.int)
        I2 = np.array(self.image2,dtype=np.int)
        I1 = I1 - np.mean(I1)
        I2 = I2 - np.mean(I2)
        xcorr = cv2.filter2D(I1,cv2.CV_32F,I2)
        cv2.imshow('xcorr',np.array(255*xcorr/np.max(xcorr),dtype=np.uint8))
        cv2.waitKey(15)  
        '''
        # method 2: use skimage.registration.phase_cross_correlation
        shifts,error,phasediff = skimage.registration.phase_cross_correlation(self.image1,self.image2,upsample_factor=self.registration_upsample_factor,space='real')
        print(shifts) # for debugging
        return shifts[0] # can be shifts[1] - depending on camera orientation

    def close(self):
        pass

class TwoCamerasPDAFCalibrationController(QObject):

    acquisitionFinished = Signal()
    image_to_display_camera1 = Signal(np.ndarray)
    image_to_display_camera2 = Signal(np.ndarray)
    signal_current_configuration = Signal(Configuration)

    z_pos = Signal(float)

    def __init__(self,camera1,camera2,navigationController,liveController1,liveController2,configurationManager=None):
        QObject.__init__(self)

        self.camera1 = camera1
        self.camera2 = camera2
        self.navigationController = navigationController
        self.liveController1 = liveController1
        self.liveController2 = liveController2
        self.configurationManager = configurationManager
        self.NZ = 1
        self.Nt = 1
        self.deltaZ = Acquisition.DZ/1000
        self.deltaZ_usteps = round((Acquisition.DZ/1000)*Motion.STEPS_PER_MM_Z)
        self.crop_width = Acquisition.CROP_WIDTH
        self.crop_height = Acquisition.CROP_HEIGHT
        self.display_resolution_scaling = Acquisition.IMAGE_DISPLAY_SCALING_FACTOR
        self.counter = 0
        self.experiment_ID = None
        self.base_path = None

    def set_NX(self,N):
        self.NX = N
    def set_NY(self,N):
        self.NY = N
    def set_NZ(self,N):
        self.NZ = N
    def set_Nt(self,N):
        self.Nt = N
    def set_deltaX(self,delta):
        self.deltaX = delta
        self.deltaX_usteps = round(delta*Motion.STEPS_PER_MM_XY)
    def set_deltaY(self,delta):
        self.deltaY = delta
        self.deltaY_usteps = round(delta*Motion.STEPS_PER_MM_XY)
    def set_deltaZ(self,delta_um):
        self.deltaZ = delta_um/1000
        self.deltaZ_usteps = round((delta_um/1000)*Motion.STEPS_PER_MM_Z)
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
        self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d %H-%M-%-S.%f')
        self.recording_start_time = time.time()
        # create a new folder
        try:
            os.mkdir(os.path.join(self.base_path,self.experiment_ID))
            if self.configurationManager:
                self.configurationManager.write_configuration(os.path.join(self.base_path,self.experiment_ID)+"/configurations.xml") # save the configuration for the experiment
        except:
            pass

    def set_selected_configurations(self, selected_configurations_name):
        self.selected_configurations = []
        for configuration_name in selected_configurations_name:
            self.selected_configurations.append(next((config for config in self.configurationManager.configurations if config.name == configuration_name)))
        
    def run_acquisition(self): # @@@ to do: change name to run_experiment
        print('start multipoint')
        
        # stop live
        if self.liveController1.is_live:
            self.liveController1.was_live_before_multipoint = True
            self.liveController1.stop_live() # @@@ to do: also uncheck the live button
        else:
            self.liveController1.was_live_before_multipoint = False
        # stop live
        if self.liveController2.is_live:
            self.liveController2.was_live_before_multipoint = True
            self.liveController2.stop_live() # @@@ to do: also uncheck the live button
        else:
            self.liveController2.was_live_before_multipoint = False

        # disable callback
        if self.camera1.callback_is_enabled:
            self.camera1.callback_was_enabled_before_multipoint = True
            self.camera1.stop_streaming()
            self.camera1.disable_callback()
            self.camera1.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
        else:
            self.camera1.callback_was_enabled_before_multipoint = False
        # disable callback
        if self.camera2.callback_is_enabled:
            self.camera2.callback_was_enabled_before_multipoint = True
            self.camera2.stop_streaming()
            self.camera2.disable_callback()
            self.camera2.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
        else:
            self.camera2.callback_was_enabled_before_multipoint = False

        for self.time_point in range(self.Nt):
            self._run_multipoint_single()

        # re-enable callback
        if self.camera1.callback_was_enabled_before_multipoint:
            self.camera1.stop_streaming()
            self.camera1.enable_callback()
            self.camera1.start_streaming()
            self.camera1.callback_was_enabled_before_multipoint = False
        # re-enable callback
        if self.camera2.callback_was_enabled_before_multipoint:
            self.camera2.stop_streaming()
            self.camera2.enable_callback()
            self.camera2.start_streaming()
            self.camera2.callback_was_enabled_before_multipoint = False

        if self.liveController1.was_live_before_multipoint:
            self.liveController1.start_live()
        if self.liveController2.was_live_before_multipoint:
            self.liveController2.start_live()

        # emit acquisitionFinished signal
        self.acquisitionFinished.emit()
        QApplication.processEvents()

    def _run_multipoint_single(self):
        # for each time point, create a new folder
        current_path = os.path.join(self.base_path,self.experiment_ID,str(self.time_point))
        os.mkdir(current_path)
        
        # z-stack
        for k in range(self.NZ):
            file_ID = str(k)
            if self.configurationManager:
                # iterate through selected modes
                for config in self.selected_configurations:
                    self.signal_current_configuration.emit(config)
                    self.camera1.send_trigger() 
                    image = self.camera1.read_frame()
                    image = utils.crop_image(image,self.crop_width,self.crop_height)
                    saving_path = os.path.join(current_path, 'camera1_' + file_ID + str(config.name) + '.' + Acquisition.IMAGE_FORMAT)
                    image_to_display = utils.crop_image(image,round(self.crop_width*self.liveController1.display_resolution_scaling), round(self.crop_height*self.liveController1.display_resolution_scaling))
                    self.image_to_display_camera1.emit(image_to_display)
                    if self.camera1.is_color:
                        image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                    cv2.imwrite(saving_path,image)

                    self.camera2.send_trigger() 
                    image = self.camera2.read_frame()
                    image = utils.crop_image(image,self.crop_width,self.crop_height)
                    saving_path = os.path.join(current_path, 'camera2_' + file_ID + str(config.name) + '.' + Acquisition.IMAGE_FORMAT)
                    image_to_display = utils.crop_image(image,round(self.crop_width*self.liveController2.display_resolution_scaling), round(self.crop_height*self.liveController2.display_resolution_scaling))
                    self.image_to_display_camera2.emit(image_to_display)
                    if self.camera2.is_color:
                        image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                    cv2.imwrite(saving_path,image)
                    QApplication.processEvents()
            else:
                self.camera1.send_trigger() 
                image = self.camera1.read_frame()
                image = utils.crop_image(image,self.crop_width,self.crop_height)
                saving_path = os.path.join(current_path, 'camera1_' + file_ID + '.' + Acquisition.IMAGE_FORMAT)
                image_to_display = utils.crop_image(image,round(self.crop_width*self.liveController1.display_resolution_scaling), round(self.crop_height*self.liveController1.display_resolution_scaling))
                self.image_to_display_camera1.emit(image_to_display)
                if self.camera1.is_color:
                    image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                cv2.imwrite(saving_path,image)

                self.camera2.send_trigger() 
                image = self.camera2.read_frame()
                image = utils.crop_image(image,self.crop_width,self.crop_height)
                saving_path = os.path.join(current_path, 'camera2_' + file_ID + '.' + Acquisition.IMAGE_FORMAT)
                image_to_display = utils.crop_image(image,round(self.crop_width*self.liveController2.display_resolution_scaling), round(self.crop_height*self.liveController2.display_resolution_scaling))
                self.image_to_display_camera2.emit(image_to_display)
                if self.camera2.is_color:
                    image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                cv2.imwrite(saving_path,image)
                QApplication.processEvents()
            # move z
            if k < self.NZ - 1:
                self.navigationController.move_z_usteps(self.deltaZ_usteps)
        
        # move z back
        self.navigationController.move_z_usteps(-self.deltaZ_usteps*(self.NZ-1))