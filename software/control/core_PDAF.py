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

class PDAFController(QObject):

    def __init__(self):
        QObject.__init__(self)
        self.image1_received = False
        self.image2_received = False

    def register_image_from_camera_1(self,image):
        self.image1 = image
        self.image1_received = True
        if(self.image2_received):
            self.compute_defocus()

    def register_image_from_camera_2(self,image):
        self.image2 = image
        self.image2_received = True

    def compute_defocus(self):
        print('computing defocus')
        I1 = np.array(self.image1,dtype=np.int)
        I2 = np.array(self.image2,dtype=np.int)
        I1 = I1 - np.mean(I1)
        I2 = I2 - np.mean(I2)

        xcorr = cv2.filter2D(I1,cv2.CV_32F,I2)
        # cv2.imshow('xcorr',np.array(255*xcorr/np.max(xcorr), dtype = np.uint8 ))
        # cv2.imshow('xcorr',self.image2)
        cv2.imshow('xcorr',np.array(255*xcorr/np.max(xcorr),dtype=np.uint8))
        print(np.max(xcorr))
        cv2.waitKey(15)  
        pass


    def close(self):
        pass

class TwoCamerasPDAFCalibrationController(QObject):

    acquisitionFinished = Signal()
    image_to_display_camera1 = Signal(np.ndarray)
    image_to_display_camera2 = Signal(np.ndarray)
    signal_current_configuration = Signal(Configuration)

    z_pos = Signal(float)

    def __init__(self,camera1,camera2,navigationController,liveController1,liveController2,configurationManager):
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

    # def _on_acquisitionTimer_timeout(self):
    #     # check if the last single acquisition is ongoing
    #     if self.single_acquisition_in_progress is True:
    #         self.time_point = self.time_point + 1
    #         # stop the timer if number of time points is equal to Nt (despite some time points may have been skipped)
    #         if self.time_point >= self.Nt:
    #             self.acquisitionTimer.stop()
    #         else:
    #             print('the last acquisition has not completed, skip time point ' + str(self.time_point))
    #         return
    #     # if not, run single acquisition
    #     self._run_single_acquisition()

    def _run_multipoint_single(self):
        
        self.FOV_counter = 0
        print('multipoint acquisition - time point ' + str(self.time_point))

        # do the multipoint acquisition

        # for each time point, create a new folder
        current_path = os.path.join(self.base_path,self.experiment_ID,str(self.time_point))
        os.mkdir(current_path)

        # z-stack
        for k in range(self.NZ):

            file_ID = str(k)

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
            
            # QApplication.processEvents()

            # move z
            if k < self.NZ - 1:
                self.navigationController.move_z_usteps(self.deltaZ_usteps)
        
        # move z back
        self.navigationController.move_z_usteps(-self.deltaZ_usteps*(self.NZ-1))

        # update FOV counter
        self.FOV_counter = self.FOV_counter + 1


    # def _run_single_acquisition(self):

    #     self.single_acquisition_in_progress = True
        
    #     # stop live
    #     if self.liveController.is_live:
    #         self.liveController.was_live_before_multipoint = True
    #         self.liveController.stop_live() # @@@ to do: also uncheck the live button
    #     else:
    #         self.liveController.was_live_before_multipoint = False

    #     # disable callback
    #     if self.camera.callback_is_enabled:
    #         self.camera.callback_was_enabled_before_multipoint = True
    #         self.camera.stop_streaming()
    #         self.camera.disable_callback()
    #         self.camera.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
    #     else:
    #         self.camera.callback_was_enabled_before_multipoint = False

    #     self._run_multipoint_single()
                        
    #     # re-enable callback
    #     if self.camera.callback_was_enabled_before_multipoint:
    #         self.camera.stop_streaming()
    #         self.camera.enable_callback()
    #         self.camera.start_streaming()
    #         self.camera.callback_was_enabled_before_multipoint = False
        
    #     if self.liveController.was_live_before_multipoint:
    #         self.liveController.start_live()

    #     # emit acquisitionFinished signal
    #     self.acquisitionFinished.emit()
        
    #     # update time_point for the next scheduled single acquisition (if any)
    #     self.time_point = self.time_point + 1

    #     if self.time_point >= self.Nt:
    #         print('Multipoint acquisition finished')
    #         if self.acquisitionTimer.isActive():
    #             self.acquisitionTimer.stop()
    #         self.acquisitionFinished.emit()
    #         QApplication.processEvents()

    #     self.single_acquisition_in_progress = False