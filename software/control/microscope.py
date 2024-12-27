import serial
import time

from PyQt5.QtCore import QObject

import control.core as core
from control._def import *
import control

if CAMERA_TYPE == "Toupcam":
    import control.camera_toupcam as camera
import control.microcontroller as microcontroller
import control.serial_peripherals as serial_peripherals


class Microscope(QObject):

    def __init__(self, microscope=None, is_simulation=False):
        super().__init__()
        if microscope is None:
            self.initialize_camera(is_simulation=is_simulation)
            self.initialize_microcontroller(is_simulation=is_simulation)
            self.initialize_core_components()
            self.initialize_peripherals()
        else:
            self.camera = microscope.camera
            self.microcontroller = microscope.microcontroller
            self.configurationManager = microscope.microcontroller
            self.objectiveStore = microscope.objectiveStore
            self.streamHandler = microscope.streamHandler
            self.liveController = microscope.liveController
            self.navigationController = microscope.navigationController
            self.autofocusController = microscope.autofocusController
            self.slidePositionController = microscope.slidePositionController
            if USE_ZABER_EMISSION_FILTER_WHEEL:
                self.emission_filter_wheel = microscope.emission_filter_wheel
            elif USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
                self.emission_filter_wheel = microscope.emission_filter_wheel

    def initialize_camera(self, is_simulation):
        if is_simulation:
            self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE, flip_image=FLIP_IMAGE)
        else:
            sn_camera_main = camera.get_sn_by_model(MAIN_CAMERA_MODEL)
            self.camera = camera.Camera(sn=sn_camera_main, rotate_image_angle=ROTATE_IMAGE_ANGLE, flip_image=FLIP_IMAGE)
        
        self.camera.open()
        self.camera.set_pixel_format(DEFAULT_PIXEL_FORMAT)
        self.camera.set_software_triggered_acquisition()

    def initialize_microcontroller(self, is_simulation):
        if is_simulation:
            self.microcontroller = microcontroller.Microcontroller(existing_serial=control.microcontroller.SimSerial())
        else:
            self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION, sn=CONTROLLER_SN)
        
        self.microcontroller.reset()
        time.sleep(0.5)
        self.microcontroller.initialize_drivers()
        time.sleep(0.5)
        self.microcontroller.configure_actuators()

        self.home_x_and_y_separately = False

    def initialize_core_components(self):
        self.configurationManager = core.ConfigurationManager(filename='./channel_configurations.xml')
        self.objectiveStore = core.ObjectiveStore()
        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera, self.microcontroller, self.configurationManager, self)
        self.navigationController = core.NavigationController(self.microcontroller, self.objectiveStore)
        self.autofocusController = core.AutoFocusController(self.camera, self.navigationController, self.liveController)
        self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController)

    def initialize_peripherals(self):
        if USE_ZABER_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel = serial_peripherals.FilterController(FILTER_CONTROLLER_SERIAL_NUMBER, 115200, 8, serial.PARITY_NONE, serial.STOPBITS_ONE)
            self.emission_filter_wheel.start_homing()
        elif USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel = serial_peripherals.Optospin(SN=FILTER_CONTROLLER_SERIAL_NUMBER)
            self.emission_filter_wheel.set_speed(OPTOSPIN_EMISSION_FILTER_WHEEL_SPEED_HZ)

    def set_channel(self,channel):
        self.liveController.set_channel(channel)

    def acquire_image(self):
        # turn on illumination and send trigger
        if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
            self.liveController.turn_on_illumination()
            self.waitForMicrocontroller()
            self.camera.send_trigger()
        elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
            self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
        
        # read a frame from camera
        image = self.camera.read_frame()
        if image is None:
            print('self.camera.read_frame() returned None')
        
        # tunr off the illumination if using software trigger
        if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
            self.liveController.turn_off_illumination()
        
        return image

    def home_xyz(self):
        if HOMING_ENABLED_Z:
            self.navigationController.home_z()
            self.waitForMicrocontroller(10, 'z homing timeout')
        if HOMING_ENABLED_X and HOMING_ENABLED_Y:
            self.navigationController.move_x(20)
            self.waitForMicrocontroller()
            self.navigationController.home_y()
            self.waitForMicrocontroller(10, 'y homing timeout')
            self.navigationController.zero_y()
            self.navigationController.home_x()
            self.waitForMicrocontroller(10, 'x homing timeout')
            self.navigationController.zero_x()
            self.slidePositionController.homing_done = True

    def move_x(self,distance,blocking=True):
        self.navigationController.move_x(distance)
        if blocking:
            self.waitForMicrocontroller()

    def move_y(self,distance,blocking=True):
        self.navigationController.move_y(distance)
        if blocking:
            self.waitForMicrocontroller()

    def move_x_to(self,position,blocking=True):
        self.navigationController.move_x_to(position)
        if blocking:
            self.waitForMicrocontroller()

    def move_y_to(self,position,blocking=True):
        self.navigationController.move_y_to(position)
        if blocking:
            self.waitForMicrocontroller()

    def get_x(self):
        return self.navigationController.x_pos_mm

    def get_y(self):
        return self.navigationController.y_pos_mm

    def get_z(self):
        return self.navigationController.z_pos_mm

    def move_z_to(self,z_mm,blocking=True):
        clear_backlash = True if (z_mm < self.navigationController.z_pos_mm and self.navigationController.get_pid_control_flag(2)==False) else False
        # clear backlash if moving backward in open loop mode
        self.navigationController.move_z_to(z_mm)
        if blocking:
            self.waitForMicrocontroller()
            if clear_backlash:
                _usteps_to_clear_backlash = 160
                self.navigationController.move_z_usteps(-_usteps_to_clear_backlash)
                self.waitForMicrocontroller()
                self.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                self.waitForMicrocontroller()

    def start_live(self):
        self.camera.start_streaming()
        self.liveController.start_live()

    def stop_live(self):
        self.liveController.stop_live()
        self.camera.stop_streaming()

    def waitForMicrocontroller(self, timeout=5.0, error_message=None):
        try:
            self.microcontroller.wait_till_operation_is_completed(timeout)
        except TimeoutError as e:
            self.log.error(error_message or "Microcontroller operation timed out!")
            raise e

    def close(self):
        self.stop_live()
        self.camera.close()
        self.microcontroller.close()
        if USE_ZABER_EMISSION_FILTER_WHEEL or USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.close()