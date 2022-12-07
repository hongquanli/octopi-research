# qt libraries
from qtpy.QtCore import QObject, QTimer, Signal
from qtpy.QtWidgets import QApplication

from control._def import *
import time
import numpy

from typing import Optional, List, Union, Tuple

import control.microcontroller as microcontroller
import control.camera as camera
from control.core import ConfigurationManager, Configuration, StreamHandler
import control.utils as utils

class LiveController(QObject):

    start_live_signal=Signal()
    stop_live_signal=Signal()

    @property
    def timer_trigger_interval_ms(self)->int:
        """ timer trigger interval in msec"""
        return int(self.timer_trigger_interval_s*1000)

    @property
    def timer_trigger_interval_s(self)->float:
        """ timer trigger interval in sec"""
        return 1/self.fps_trigger

    def __init__(self,
        camera:camera.Camera,
        microcontroller:microcontroller.Microcontroller,
        configurationManager:ConfigurationManager,
        stream_handler:StreamHandler,
        control_illumination:bool=True,
        use_internal_timer_for_hardware_trigger:bool=True,
        for_displacement_measurement:bool=False
    ):

        QObject.__init__(self)
        self.camera = camera
        self.microcontroller = microcontroller
        self.configurationManager:ConfigurationManager = configurationManager
        self.stream_handler=stream_handler
        self.currentConfiguration:Optional[Configuration] = None
        self.trigger_mode:TriggerMode = TriggerMode.SOFTWARE
        self.is_live:bool = False
        self.control_illumination = control_illumination
        self.illumination_on:bool = False
        self.use_internal_timer_for_hardware_trigger = use_internal_timer_for_hardware_trigger # use QTimer vs timer in the MCU
        self.for_displacement_measurement=for_displacement_measurement

        self.fps_trigger:float = MACHINE_CONFIG.DEFAULT_TRIGGER_FPS

        self.timer_trigger = QTimer()
        self.timer_trigger.setInterval(self.timer_trigger_interval_ms)
        self.timer_trigger.timeout.connect(self.trigger_acquisition)

        self.trigger_ID = -1

        self.fps_real:int = 0
        self.counter:int = 0
        self.timestamp_last:int = 0

        self.image_acquisition_in_progress:bool=False
        self.image_acquisition_queued:bool=False
        self.time_image_requested=time.time()
        self.stop_requested=False

        if for_displacement_measurement:
            self.currentConfiguration=self.configurationManager.configurations[0]

    def snap(self,config:Configuration=None,crop:bool=True,override_crop_width:Optional[int]=None,override_crop_height:Optional[int]=None)->numpy.ndarray:
        """
        if 'crop' is True, the image will be cropped to the streamhandlers requested height and width. 'override_crop_[height,width]' override the respective value
        """
        if self.camera.callback_is_enabled:
            callback_was_enabled=True
            self.camera.disable_callback()
        else:
            callback_was_enabled=False

        """ prepare camera and lights """
        self.set_microscope_mode(config)
        self.camera.start_streaming()
        self.camera.is_live=True

        """ take image """
        self.trigger_acquisition()
        image = self.camera.read_frame()
        self.end_acquisition()

        """ de-prepare camera and lights """
        self.camera.is_live=False
        self.camera.stop_streaming()

        if callback_was_enabled:
            self.camera.enable_callback()

        crop_height=override_crop_height or self.stream_handler.crop_height
        crop_width=override_crop_width or self.stream_handler.crop_width

        image_cropped=image
        if crop:
            image_cropped = utils.crop_image(image_cropped,crop_width,crop_height)
        image_cropped = numpy.squeeze(image_cropped)
        image_cropped = utils.rotate_and_flip_image(image_cropped,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)
        if crop:
            image_cropped = utils.crop_image(image_cropped,round(crop_width), round(crop_height))

        return image_cropped

    # illumination control
    def turn_on_illumination(self):
        if self.control_illumination and not self.illumination_on:
            self.microcontroller.turn_on_illumination()
            self.microcontroller.wait_till_operation_is_completed(timeout_limit_s=None,time_step=0.001)
            self.illumination_on = True

    def turn_off_illumination(self):
        if self.control_illumination and self.illumination_on:
            self.microcontroller.turn_off_illumination()
            self.microcontroller.wait_till_operation_is_completed(timeout_limit_s=None,time_step=0.001)
            self.illumination_on = False

    def set_illumination(self,illumination_source:int,intensity:float):
        if illumination_source < 10: # LED matrix
            self.microcontroller.set_illumination_led_matrix(illumination_source,r=(intensity/100)*MACHINE_CONFIG.LED_MATRIX_R_FACTOR,g=(intensity/100)*MACHINE_CONFIG.LED_MATRIX_G_FACTOR,b=(intensity/100)*MACHINE_CONFIG.LED_MATRIX_B_FACTOR)
        else:
            self.microcontroller.set_illumination(illumination_source,intensity)

    def start_live(self):
        if self.image_acquisition_in_progress:
            self.stream_handler.signal_new_frame_received.connect(self.start_live)
            return

        self.is_live = True
        self.camera.is_live = True
        self.camera.start_streaming()
        if self.trigger_mode == TriggerMode.SOFTWARE or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
            self.camera.enable_callback() # in case it's disabled e.g. by the laser AF controller
            self._start_triggered_acquisition()
        # if controlling the laser displacement measurement camera
        if self.for_displacement_measurement:
            self.microcontroller.turn_on_AF_laser(completion={})

        self.start_live_signal.emit()

    def stop_live(self):
        self.stop_requested=True
        if self.image_acquisition_in_progress or self.image_acquisition_queued:
            return

        if self.is_live:
            self.is_live = False
            self.camera.is_live = False
            self.camera.stop_streaming()
            if self.trigger_mode == TriggerMode.CONTINUOUS:
                self.camera.stop_streaming()
                self.turn_off_illumination()
            if self.trigger_mode == TriggerMode.SOFTWARE or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
                self._stop_triggered_acquisition()

            # if controlling the laser displacement measurement camera
            if self.for_displacement_measurement:
                self.microcontroller.turn_off_AF_laser(completion={})

            self.camera.stop_streaming()

            self.stop_requested=False
            self.image_acquisition_in_progress=False
            self.image_acquisition_queued=False

            self.stop_live_signal.emit()

    # actually take an image
    def trigger_acquisition(self):
        if self.stop_requested:
            return

        if self.image_acquisition_in_progress:
            if self.image_acquisition_queued:
                print("! warning: image acquisition requested while already in progress. !")
                return

            self.image_acquisition_queued=True
            return

        self.trigger_ID = self.trigger_ID + 1
        self.image_acquisition_in_progress=True
        self.time_image_requested=time.time()
        #print(f"taking an image (img id: {self.trigger_ID:9} )")
        if self.trigger_mode == TriggerMode.SOFTWARE:
            if not self.for_displacement_measurement:
                self.turn_on_illumination()
            else:
                self.microcontroller.turn_on_AF_laser()

            self.camera.send_trigger()

        elif self.trigger_mode == TriggerMode.HARDWARE:
            self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)

        self.stream_handler.signal_new_frame_received.connect(self.end_acquisition)

    def end_acquisition(self):
        self.stream_handler.signal_new_frame_received.disconnect(self.end_acquisition)

        #imaging_time=time.time()-self.time_image_requested
        #print(f"real imaging time: {imaging_time*1000:6.3f} ms") # this shows a 40ms delay vs exposure time. why?

        if self.trigger_mode == TriggerMode.SOFTWARE:
            if not self.for_displacement_measurement:
                self.turn_off_illumination()
            else:
                self.microcontroller.turn_off_AF_laser()

        self.image_acquisition_in_progress=False
        self.image_acquisition_queued=False

        if self.stop_requested:
            self.stop_live()
            return

        if self.image_acquisition_queued:
            self.trigger_acquisition()

    def _start_triggered_acquisition(self):
        self.timer_trigger.start()

    def _set_trigger_fps(self,fps_trigger:float):
        """ set frames per second for trigger """
        self.fps_trigger = fps_trigger
        #print(f"setting trigger interval to {self.timer_trigger_interval_ms} ms")
        self.timer_trigger.setInterval(self.timer_trigger_interval_ms)

    def _stop_triggered_acquisition(self):
        self.timer_trigger.stop()

    # trigger mode and settings
    def set_trigger_mode(self,mode:str):
        if mode == TriggerMode.SOFTWARE:
            if self.is_live and ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
                self._stop_triggered_acquisition()

            self.camera.set_software_triggered_acquisition()
            if self.is_live:
                self._start_triggered_acquisition()

        elif mode == TriggerMode.HARDWARE:
            if self.trigger_mode == TriggerMode.SOFTWARE and self.is_live:
                self._stop_triggered_acquisition()

            # self.camera.reset_camera_acquisition_counter()
            self.camera.set_hardware_triggered_acquisition()
            self.microcontroller.set_strobe_delay_us(self.camera.strobe_delay_us)
            if self.is_live and self.use_internal_timer_for_hardware_trigger:
                self._start_triggered_acquisition()

        elif mode == TriggerMode.CONTINUOUS: 
            if ( self.trigger_mode == TriggerMode.SOFTWARE ) or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
                self._stop_triggered_acquisition()

            self.camera.set_continuous_acquisition()
        else:
            assert False

        self.trigger_mode = mode

    def set_trigger_fps(self,fps:float):
        if ( self.trigger_mode == TriggerMode.SOFTWARE ) or ( self.trigger_mode == TriggerMode.HARDWARE and self.use_internal_timer_for_hardware_trigger ):
            self._set_trigger_fps(fps)
    
    # set microscope mode
    # @@@ to do: change softwareTriggerGenerator to TriggerGeneratror
    def set_microscope_mode(self,configuration:Configuration):
        self.currentConfiguration = configuration
        # print("setting microscope mode to " + self.currentConfiguration.name)
        
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
