import os 
os.environ["QT_API"] = "pyqt5"

# qt libraries
from qtpy.QtCore import QObject, Signal, QMutex, QEventLoop
from qtpy.QtWidgets import QApplication

from control._def import *

import time
import numpy as np
import scipy
import scipy.signal

import control.microcontroller as microcontroller
import control.camera as camera
from control.core import LiveController,NavigationController

import matplotlib.pyplot as plt

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
        self.x_reference = None
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

        # get laser spot location
        x,y = self._get_laser_spot_centroid()

        x_offset = x - MACHINE_CONFIG.LASER_AF_CROP_WIDTH/2
        y_offset = y - MACHINE_CONFIG.LASER_AF_CROP_HEIGHT/2
        #print('laser spot location on the full sensor is (' + str(int(x)) + ',' + str(int(y)) + ')')

        # set camera crop
        self.initialize_manual(x_offset, y_offset, MACHINE_CONFIG.LASER_AF_CROP_WIDTH, MACHINE_CONFIG.LASER_AF_CROP_HEIGHT, 1.0, x)

        # move z
        self.navigationController.move_z(-0.018,{})
        self.navigationController.move_z(0.012,{},True)

        x0,y0 = self._get_laser_spot_centroid()

        self.navigationController.move_z(0.006,{},True)

        x1,y1 = self._get_laser_spot_centroid()

        # calculate the conversion factor
        self.pixel_to_um = 6.0/(x1-x0)
        #print(f'pixel to um conversion factor is {self.pixel_to_um:.3f} um/pixel')
        # for simulation
        if x1-x0 == 0:
            self.pixel_to_um = 0.4

        # set reference
        self.x_reference = x1

        print("laser AF initialization done")

    def measure_displacement(self):
        assert self.is_initialized and not self.x_reference is None

        # turn on the laser
        self.microcontroller.turn_on_AF_laser()

        # get laser spot location
        x,y = self._get_laser_spot_centroid(num_images=MACHINE_CONFIG.LASER_AF_AVERAGING_N_FAST)

        # turn off the laser
        self.microcontroller.turn_off_AF_laser(completion={})

        # calculate displacement
        displacement_um = (x - self.x_reference)*self.pixel_to_um
        self.signal_displacement_um.emit(displacement_um)

        return displacement_um

    def move_to_target(self,target_um:float,currently_repeating:bool=False):
        current_displacement_um = self.measure_displacement()

        um_to_move = target_um - current_displacement_um
        if np.abs(um_to_move)<MACHINE_CONFIG.LASER_AUTOFOCUS_TARGET_MOVE_REPEAT_THRESHOLD_UM:
            return

        if currently_repeating:
            print(f"repeating laser af 'movement to target' (off by {um_to_move} after first move)")

        # limit the range of movement
        um_to_move = min(um_to_move,200)
        um_to_move = max(um_to_move,-200)

        self.navigationController.move_z(um_to_move/1000,wait_for_completion={})

        if not currently_repeating:
            self.move_to_target(target_um,currently_repeating=True)

    def set_reference(self):
        assert self.is_initialized

        self.microcontroller.turn_on_AF_laser(completion={})
        x,y = self._get_laser_spot_centroid()
        self.microcontroller.turn_off_AF_laser(completion={})
        self.x_reference = x
        self.signal_displacement_um.emit(0)

    def _get_laser_spot_centroid(self,num_images:Optional[int]=None):
        """
            get position of laser dot on camera sensor to calculated displacement from

            num_images is number of images that are taken to calculate the average dot position from (eliminates some noise). defaults to a large number for higher precision.
        """

        if self.camera.callback_is_enabled:
            callback_was_enabled=True
            self.camera.disable_callback()
        else:
            callback_was_enabled=False

        tmp_x = 0
        tmp_y = 0

        start_time=time.time()
        imaging_times=[]

        if num_images is None:
            num_images=MACHINE_CONFIG.LASER_AF_AVERAGING_N_PRECISE

        for i in range(num_images):
            DEBUG_THIS_STUFF=False

            # try acquiring camera image until one arrives (can sometimes miss an image for some reason)
            image=None
            current_counter=0
            take_image_start_time=time.time()
            while image is None:
                if DEBUG_THIS_STUFF:
                    print(f"{current_counter=}")
                    current_counter+=1

                self.microcontroller.turn_on_AF_laser(completion={})

                # take image
                self.liveController.trigger_acquisition()
                self.liveController.end_acquisition() # callback disabled -> do this manually
                image = self.camera.read_frame()

                self.microcontroller.turn_off_AF_laser(completion={})

            imaging_times.append(time.time()-take_image_start_time)

            # optionally display the image
            if MACHINE_CONFIG.LASER_AF_DISPLAY_SPOT_IMAGE:
                self.image_to_display.emit(image)

            # calculate centroid
            x,y = self._calculate_centroid(image)

            if DEBUG_THIS_STUFF and False:
                print(f"{x = } {(MACHINE_CONFIG.LASER_AF_CROP_WIDTH/2) = }")
                print(f"{y = } {(MACHINE_CONFIG.LASER_AF_CROP_HEIGHT/2) = }")

                plt.imshow(image,cmap="gist_gray")
                plt.scatter([x],[y],marker="x",c="green")
                plt.show()

            tmp_x += x
            tmp_y += y

        if DEBUG_THIS_STUFF:
            imaging_times_str=", ".join([f"{i:.3f}" for i in imaging_times])
            print(f"calculated centroid in {(time.time()-start_time):.3f}s ({imaging_times_str})")

        if callback_was_enabled:
            self.camera.enable_callback()

        x = tmp_x/num_images
        y = tmp_y/num_images


        return x,y

    def _calculate_centroid(self,image):
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
            try:
                peak_0_location = peak_locations[idx[-1]]
            except IndexError:
                raise Exception("did not find first peak in laser AF image. this is a bug.")
            try:
                peak_1_location = peak_locations[idx[-2]] # for air-glass-water, the smaller peak corresponds to the glass-water interface
            except IndexError:
                raise Exception("did not find second peak in laser AF image. this is a bug.")
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

  