import argparse
import cv2
import time
import numpy as np

from control.gxipy import gxiapi
try:
    import control.gxipy as gx
except:
    print('gxipy import error')

from control._def import *
from typing import Optional, Any

from control.typechecker import TypecheckFunction

class Camera(object):

    @TypecheckFunction
    def __init__(self,sn:Optional[str]=None,is_global_shutter:bool=False,rotate_image_angle:Optional[int]=None,flip_image:Optional[str]=None):

        # many to be purged
        self.sn = sn
        self.is_global_shutter = is_global_shutter
        self.device_manager = gx.DeviceManager()
        self.device_info_list = None
        self.device_index = 0
        self.camera:Optional[gxiapi.Device] = None
        self.is_color = None
        self.gamma_lut = None
        self.contrast_lut = None
        self.color_correction_param = None

        self.rotate_image_angle = rotate_image_angle
        self.flip_image = flip_image

        self.exposure_time = 1 # unit: ms
        self.analog_gain = 0
        self.frame_ID = -1
        self.frame_ID_software = -1
        self.frame_ID_offset_hardware_trigger = 0
        self.timestamp = 0

        self.image_locked = False
        self.current_frame = None

        self.callback_is_enabled = False
        self.is_streaming = False

        self.GAIN_MAX = 24
        self.GAIN_MIN = 0
        self.GAIN_STEP = 1
        self.EXPOSURE_TIME_MS_MIN = 0.01
        self.EXPOSURE_TIME_MS_MAX = 4000

        self.ROI_offset_x = CAMERA.ROI_OFFSET_X_DEFAULT
        self.ROI_offset_y = CAMERA.ROI_OFFSET_X_DEFAULT
        self.ROI_width = CAMERA.ROI_WIDTH_DEFAULT
        self.ROI_height = CAMERA.ROI_HEIGHT_DEFAULT

        self.trigger_mode = None
        self.pixel_size_byte = 1

        # below are values for IMX226 (MER2-1220-32U3M) - to make configurable 
        self.row_period_us = 10
        self.row_numbers = 3036
        self.exposure_delay_us_8bit = 650
        self.exposure_delay_us = self.exposure_delay_us_8bit*self.pixel_size_byte
        self.strobe_delay_us = self.exposure_delay_us + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1)

        self.pixel_format = None # use the default pixel format

        self.is_live = False # this determines whether a new frame received will be handled in the streamHandler
        # mainly for discarding the last frame received after stop_live() is called, where illumination is being turned off during exposure

    @TypecheckFunction
    def open(self,index:int=0):
        (device_num, self.device_info_list) = self.device_manager.update_device_list()
        if device_num == 0:
            raise RuntimeError('Could not find any USB camera devices!')
        if self.sn is None:
            self.device_index = index
            self.camera = self.device_manager.open_device_by_index(index + 1)
        else:
            self.camera = self.device_manager.open_device_by_sn(self.sn)

        assert not self.camera is None
        self.is_color = self.camera.PixelColorFilter.is_implemented()
        # self._update_image_improvement_params()
        # self.camera.register_capture_callback(self,self._on_frame_callback)
        if self.is_color:
            # self.set_wb_ratios(self.get_awb_ratios())
            print(self.get_awb_ratios())
            # self.set_wb_ratios(1.28125,1.0,2.9453125)
            self.set_wb_ratios(2,1,2)

        # temporary
        self.camera.AcquisitionFrameRate.set(1000)
        self.camera.AcquisitionFrameRateMode.set(gx.GxSwitchEntry.ON)

        # turn off device link throughput limit
        self.camera.DeviceLinkThroughputLimitMode.set(gx.GxSwitchEntry.OFF)

    def set_callback(self,function):
        self.new_image_callback_external = function

    @TypecheckFunction
    def enable_callback(self):
        # stop streaming
        if self.is_streaming:
            was_streaming = True
            self.stop_streaming()
        else:
            was_streaming = False
        # enable callback
        user_param:Optional[Any] = None
        assert not self.camera is None
        self.camera.register_capture_callback(user_param,self._on_frame_callback)
        self.callback_is_enabled = True
        # resume streaming if it was on
        if was_streaming:
            self.start_streaming()

    @TypecheckFunction
    def disable_callback(self):
        # stop streaming
        if self.is_streaming:
            was_streaming = True
            self.stop_streaming()
        else:
            was_streaming = False
        # disable call back
        assert not self.camera is None
        self.camera.unregister_capture_callback()
        self.callback_is_enabled = False
        # resume streaming if it was on
        if was_streaming:
            self.start_streaming()

    @TypecheckFunction
    def open_by_sn(self,sn:str):
        (device_num, self.device_info_list) = self.device_manager.update_device_list()
        if device_num == 0:
            raise RuntimeError('Could not find any USB camera devices!')

        self.camera = self.device_manager.open_device_by_sn(sn)
        assert not self.camera is None
        self.is_color = self.camera.PixelColorFilter.is_implemented()
        self._update_image_improvement_params() # type: ignore

        '''
        if self.is_color is True:
            self.camera.register_capture_callback(_on_color_frame_callback)
        else:
            self.camera.register_capture_callback(_on_frame_callback)
        '''

    @TypecheckFunction
    def close(self):
        assert not self.camera is None
        self.camera.close_device()
        self.device_info_list = None
        self.camera = None
        self.is_color = None
        self.gamma_lut = None
        self.contrast_lut = None
        self.color_correction_param = None
        self.last_raw_image = None
        self.last_converted_image = None
        self.last_numpy_image = None

    @TypecheckFunction
    def set_exposure_time(self,exposure_time:float):
        assert not self.camera is None
        use_strobe = (self.trigger_mode == TriggerMode.HARDWARE) # true if using hardware trigger
        if use_strobe == False or self.is_global_shutter:
            self.exposure_time = exposure_time
            self.camera.ExposureTime.set(exposure_time * 1000)
        else:
            # set the camera exposure time such that the active exposure time (illumination on time) is the desired value
            self.exposure_time = exposure_time
            # add an additional 500 us so that the illumination can fully turn off before rows start to end exposure
            camera_exposure_time = self.exposure_delay_us + self.exposure_time*1000 + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1) + 500 # add an additional 500 us so that the illumination can fully turn off before rows start to end exposure
            self.camera.ExposureTime.set(camera_exposure_time)

    @TypecheckFunction
    def update_camera_exposure_time(self):
        assert not self.camera is None
        use_strobe = (self.trigger_mode == TriggerMode.HARDWARE) # true if using hardware trigger
        if use_strobe == False or self.is_global_shutter:
            self.camera.ExposureTime.set(self.exposure_time * 1000)
        else:
            camera_exposure_time = self.exposure_delay_us + self.exposure_time*1000 + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1) + 500 # add an additional 500 us so that the illumination can fully turn off before rows start to end exposure
            self.camera.ExposureTime.set(camera_exposure_time)

    @TypecheckFunction
    def set_analog_gain(self,analog_gain:float):
        assert not self.camera is None
        self.analog_gain = analog_gain
        self.camera.Gain.set(analog_gain)

    @TypecheckFunction
    def get_awb_ratios(self):
        assert not self.camera is None
        self.camera.BalanceWhiteAuto.set(2)
        self.camera.BalanceRatioSelector.set(0)
        awb_r = self.camera.BalanceRatio.get()
        self.camera.BalanceRatioSelector.set(1)
        awb_g = self.camera.BalanceRatio.get()
        self.camera.BalanceRatioSelector.set(2)
        awb_b = self.camera.BalanceRatio.get()
        return (awb_r, awb_g, awb_b)

    @TypecheckFunction
    def set_wb_ratios(self, wb_r:Optional[float]=None, wb_g:Optional[float]=None, wb_b:Optional[float]=None):
        assert not self.camera is None
        self.camera.BalanceWhiteAuto.set(0)
        if wb_r is not None:
            self.camera.BalanceRatioSelector.set(0)
            awb_r = self.camera.BalanceRatio.set(wb_r)
        if wb_g is not None:
            self.camera.BalanceRatioSelector.set(1)
            awb_g = self.camera.BalanceRatio.set(wb_g)
        if wb_b is not None:
            self.camera.BalanceRatioSelector.set(2)
            awb_b = self.camera.BalanceRatio.set(wb_b)

    @TypecheckFunction
    def set_reverse_x(self,value:bool):
        assert not self.camera is None
        self.camera.ReverseX.set(value)

    @TypecheckFunction
    def set_reverse_y(self,value:bool):
        assert not self.camera is None
        self.camera.ReverseY.set(value)

    @TypecheckFunction
    def start_streaming(self):
        assert not self.camera is None
        self.camera.stream_on()
        self.is_streaming = True

    @TypecheckFunction
    def stop_streaming(self):
        assert not self.camera is None
        self.camera.stream_off()
        self.is_streaming = False

    @TypecheckFunction
    def set_pixel_format(self,pixel_format:str):
        assert not self.camera is None
        if self.is_streaming == True:
            was_streaming = True
            self.stop_streaming()
        else:
            was_streaming = False

        if self.camera.PixelFormat.is_implemented() and self.camera.PixelFormat.is_writable():
            if pixel_format == 'MONO8':
                self.camera.PixelFormat.set(gx.GxPixelFormatEntry.MONO8)
                self.pixel_size_byte = 1
            if pixel_format == 'MONO12':
                self.camera.PixelFormat.set(gx.GxPixelFormatEntry.MONO12)
                self.pixel_size_byte = 2
            if pixel_format == 'MONO14':
                self.camera.PixelFormat.set(gx.GxPixelFormatEntry.MONO14)
                self.pixel_size_byte = 2
            if pixel_format == 'MONO16':
                self.camera.PixelFormat.set(gx.GxPixelFormatEntry.MONO16)
                self.pixel_size_byte = 2
            if pixel_format == 'BAYER_RG8':
                self.camera.PixelFormat.set(gx.GxPixelFormatEntry.BAYER_RG8)
                self.pixel_size_byte = 1
            if pixel_format == 'BAYER_RG12':
                self.camera.PixelFormat.set(gx.GxPixelFormatEntry.BAYER_RG12)
                self.pixel_size_byte = 2
            self.pixel_format = pixel_format
        else:
            print("pixel format is not implemented or not writable")

        if was_streaming:
           self.start_streaming()

        # update the exposure delay and strobe delay
        self.exposure_delay_us = self.exposure_delay_us_8bit*self.pixel_size_byte
        self.strobe_delay_us = self.exposure_delay_us + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1)

    @TypecheckFunction
    def set_continuous_acquisition(self):
        assert not self.camera is None
        self.camera.TriggerMode.set(gx.GxSwitchEntry.OFF)
        self.trigger_mode = TriggerMode.CONTINUOUS
        self.update_camera_exposure_time()

    @TypecheckFunction
    def set_software_triggered_acquisition(self):
        assert not self.camera is None
        self.camera.TriggerMode.set(gx.GxSwitchEntry.ON)
        self.camera.TriggerSource.set(gx.GxTriggerSourceEntry.SOFTWARE)
        self.trigger_mode = TriggerMode.SOFTWARE
        self.update_camera_exposure_time()

    @TypecheckFunction
    def set_hardware_triggered_acquisition(self):
        assert not self.camera is None
        self.camera.TriggerMode.set(gx.GxSwitchEntry.ON)
        self.camera.TriggerSource.set(gx.GxTriggerSourceEntry.LINE2)
        # self.camera.TriggerSource.set(gx.GxTriggerActivationEntry.RISING_EDGE)
        self.frame_ID_offset_hardware_trigger = None
        self.trigger_mode = TriggerMode.HARDWARE
        self.update_camera_exposure_time()

    @TypecheckFunction
    def send_trigger(self):
        assert not self.camera is None
        if self.is_streaming:
            self.camera.TriggerSoftware.send_command()
        else:
            print('trigger not sent - camera is not streaming')

    @TypecheckFunction
    def read_frame(self)->np.ndarray:
        assert not self.camera is None
        raw_image = self.camera.data_stream[self.device_index].get_image()
        if self.is_color:
            rgb_image = raw_image.convert("RGB")
            numpy_image = rgb_image.get_numpy_array()
            if self.pixel_format == 'BAYER_RG12':
                numpy_image = numpy_image << 4
        else:
            numpy_image = raw_image.get_numpy_array()
            if self.pixel_format == 'MONO12':
                numpy_image = numpy_image << 4
        # self.current_frame = numpy_image
        return numpy_image

    @TypecheckFunction
    def _on_frame_callback(self, user_param:Optional[Any], raw_image:Optional[gxiapi.RawImage]):
        if raw_image is None:
            print("Getting image failed.")
            return
        if raw_image.get_status() != 0:
            print("Got an incomplete frame")
            return
        if self.image_locked:
            print('last image is still being processed, a frame is dropped')
            return
        if self.is_color:
            rgb_image = raw_image.convert("RGB")
            numpy_image = rgb_image.get_numpy_array()
            if self.pixel_format == 'BAYER_RG12':
                numpy_image = numpy_image << 4
        else:
            numpy_image = raw_image.get_numpy_array()
            if self.pixel_format == 'MONO12':
                numpy_image = numpy_image << 4
        if numpy_image is None:
            return
        self.current_frame = numpy_image
        self.frame_ID_software = self.frame_ID_software + 1
        self.frame_ID = raw_image.get_frame_id()
        if self.trigger_mode == TriggerMode.HARDWARE:
            if self.frame_ID_offset_hardware_trigger == None:
                self.frame_ID_offset_hardware_trigger = self.frame_ID
            self.frame_ID = self.frame_ID - self.frame_ID_offset_hardware_trigger
        self.timestamp = time.time()
        self.new_image_callback_external(self)

        # self.frameID = self.frameID + 1
        # print(self.frameID)
    
    @TypecheckFunction
    def set_ROI(self,offset_x:Optional[int]=None,offset_y:Optional[int]=None,width:Optional[int]=None,height:Optional[int]=None):
        assert not self.camera is None
        if offset_x is not None:
            self.ROI_offset_x = offset_x
            # stop streaming if streaming is on
            if self.is_streaming == True:
                was_streaming = True
                self.stop_streaming()
            else:
                was_streaming = False
            # update the camera setting
            if self.camera.OffsetX.is_implemented() and self.camera.OffsetX.is_writable():
                self.camera.OffsetX.set(self.ROI_offset_x)
            else:
                print("OffsetX is not implemented or not writable")
            # restart streaming if it was previously on
            if was_streaming == True:
                self.start_streaming()

        if offset_y is not None:
            self.ROI_offset_y = offset_y
                # stop streaming if streaming is on
            if self.is_streaming == True:
                was_streaming = True
                self.stop_streaming()
            else:
                was_streaming = False
            # update the camera setting
            if self.camera.OffsetY.is_implemented() and self.camera.OffsetY.is_writable():
                self.camera.OffsetY.set(self.ROI_offset_y)
            else:
                print("OffsetX is not implemented or not writable")
            # restart streaming if it was previously on
            if was_streaming == True:
                self.start_streaming()

        if width is not None:
            self.ROI_width = width
            # stop streaming if streaming is on
            if self.is_streaming == True:
                was_streaming = True
                self.stop_streaming()
            else:
                was_streaming = False
            # update the camera setting
            if self.camera.Width.is_implemented() and self.camera.Width.is_writable():
                self.camera.Width.set(self.ROI_width)
            else:
                print("OffsetX is not implemented or not writable")
            # restart streaming if it was previously on
            if was_streaming == True:
                self.start_streaming()

        if height is not None:
            self.ROI_height = height
            # stop streaming if streaming is on
            if self.is_streaming == True:
                was_streaming = True
                self.stop_streaming()
            else:
                was_streaming = False
            # update the camera setting
            if self.camera.Height.is_implemented() and self.camera.Height.is_writable():
                self.camera.Height.set(self.ROI_height)
            else:
                print("Height is not implemented or not writable")
            # restart streaming if it was previously on
            if was_streaming == True:
                self.start_streaming()

    def reset_camera_acquisition_counter(self):
        assert not self.camera is None
        if self.camera.CounterEventSource.is_implemented() and self.camera.CounterEventSource.is_writable(): # type: ignore
            self.camera.CounterEventSource.set(gx.GxCounterEventSourceEntry.LINE2) # type: ignore
        else:
            print("CounterEventSource is not implemented or not writable")

        if self.camera.CounterReset.is_implemented(): # type: ignore
            self.camera.CounterReset.send_command() # type: ignore
        else:
            print("CounterReset is not implemented")

    def set_line3_to_strobe(self):
        assert not self.camera is None
        # self.camera.StrobeSwitch.set(gx.GxSwitchEntry.ON)
        self.camera.LineSelector.set(gx.GxLineSelectorEntry.LINE3)
        self.camera.LineMode.set(gx.GxLineModeEntry.OUTPUT)
        self.camera.LineSource.set(gx.GxLineSourceEntry.STROBE)

    def set_line3_to_exposure_active(self):
        assert not self.camera is None
        # self.camera.StrobeSwitch.set(gx.GxSwitchEntry.ON)
        self.camera.LineSelector.set(gx.GxLineSelectorEntry.LINE3)
        self.camera.LineMode.set(gx.GxLineModeEntry.OUTPUT)
        self.camera.LineSource.set(gx.GxLineSourceEntry.EXPOSURE_ACTIVE)

    