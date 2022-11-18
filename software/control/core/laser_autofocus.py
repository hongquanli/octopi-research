import os 
os.environ["QT_API"] = "pyqt5"

# qt libraries
from qtpy.QtCore import QObject, Signal

from control._def import *

import time
import numpy as np
import scipy
import scipy.signal

import control.microcontroller as microcontroller
import control.camera as camera
from control.core import LiveController,NavigationController

class LaserAutofocusController(QObject):

    image_to_display = Signal(np.ndarray)
    signal_displacement_um = Signal(float)

    def __init__(self,
        microcontroller:microcontroller.Microcontroller,
        camera:camera.Camera, # focus camera (?)
        liveController:LiveController,
        navigationController:NavigationController,
        has_two_interfaces:bool=True,
        use_glass_top:bool=True
    ):
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.camera = camera
        self.liveController = liveController
        self.navigationController = navigationController

        self.is_initialized = False
        self.x_reference = 0.0
        self.pixel_to_um:float = 1.0
        self.x_offset:int = 0
        self.y_offset:int = 0
        self.x_width:int = 3088
        self.y_width:int = 2064

        self.has_two_interfaces = has_two_interfaces # e.g. air-glass and glass water, set to false when (1) using oil immersion (2) using 1 mm thick slide (3) using metal coated slide or Si wafer
        self.use_glass_top = use_glass_top
        self.spot_spacing_pixels = None # spacing between the spots from the two interfaces (unit: pixel)

    def initialize_manual(self, x_offset:int, y_offset:int, width:int, height:int, pixel_to_um:float, x_reference:float):
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
        self.camera.set_exposure_time(MACHINE_CONFIG.FOCUS_CAMERA_EXPOSURE_TIME_MS)
        self.camera.set_analog_gain(MACHINE_CONFIG.FOCUS_CAMERA_ANALOG_GAIN)
        
        # turn on the laser
        self.microcontroller.turn_on_AF_laser()
        self.wait_till_operation_is_completed()

        # get laser spot location
        x,y = self._get_laser_spot_centroid()

        # turn off the laser
        self.microcontroller.turn_off_AF_laser()
        self.wait_till_operation_is_completed()

        x_offset = x - MACHINE_CONFIG.LASER_AF_CROP_WIDTH/2
        y_offset = y - MACHINE_CONFIG.LASER_AF_CROP_HEIGHT/2
        print('laser spot location on the full sensor is (' + str(int(x)) + ',' + str(int(y)) + ')')

        # set camera crop
        self.initialize_manual(x_offset, y_offset, MACHINE_CONFIG.LASER_AF_CROP_WIDTH, MACHINE_CONFIG.LASER_AF_CROP_HEIGHT, 1, x)

        # move z
        self.navigationController.move_z(-0.018)
        self.wait_till_operation_is_completed()
        self.navigationController.move_z(0.012)
        self.wait_till_operation_is_completed()
        time.sleep(0.02)
        x0,y0 = self._get_laser_spot_centroid()
        self.navigationController.move_z(0.006)
        self.wait_till_operation_is_completed()
        time.sleep(0.02)
        x1,y1 = self._get_laser_spot_centroid()

        # calculate the conversion factor
        self.pixel_to_um = 6.0/(x1-x0)
        print('pixel to um conversion factor is ' + str(self.pixel_to_um) + ' um/pixel')
        # for simulation
        if x1-x0 == 0:
            self.pixel_to_um = 0.4

        # set reference
        self.x_reference = x1

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
        for i in range(MACHINE_CONFIG.LASER_AF_AVERAGING_N):
            # send camera trigger
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:            
                self.camera.send_trigger()
            elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                # self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
                raise Exception("unimplemented") # to edit

            time.sleep(MACHINE_CONFIG.FOCUS_CAMERA_EXPOSURE_TIME_MS)
            
            # read camera frame
            image = self.camera.read_frame()
            # optionally display the image
            if MACHINE_CONFIG.LASER_AF_DISPLAY_SPOT_IMAGE:
                self.image_to_display.emit(image)
            # calculate centroid
            x,y = self._caculate_centroid(image)
            tmp_x = tmp_x + x
            tmp_y = tmp_y + y
        x = tmp_x/MACHINE_CONFIG.LASER_AF_AVERAGING_N
        y = tmp_y/MACHINE_CONFIG.LASER_AF_AVERAGING_N
        return x,y

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(MACHINE_CONFIG.SLEEP_TIME_S)
  