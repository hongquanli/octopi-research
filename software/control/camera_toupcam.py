import argparse
import cv2
import time
import numpy as np
try:
    import control.gxipy as gx
except:
    print('gxipy import error')

from control._def import *

import threading
import control.toupcam as toupcam

class Camera(object):

    @staticmethod
    def _event_callback(nEvent, camera):
        if nEvent == toupcam.TOUPCAM_EVENT_IMAGE:
            if camera.is_streaming:
                camera._on_frame_callback()
                camera._software_trigger_sent = False
                # print('  >>> new frame callback')

    def _on_frame_callback(self):
        
        # check if the last image is still locked
        if self.image_locked:
            print('last image is still being processed, a frame is dropped')
            return

        # get the image from the camera
        try:
            self.camera.PullImageV2(self.buf, self.pixel_size_byte*8, None) # the second camera is number of bits per pixel - ignored in RAW mode
            # print('  >>> pull image ok, current frame # = {}'.format(self.frame_ID))
        except toupcam.HRESULTException as ex:
            print('pull image failed, hr=0x{:x}'.format(ex.hr))

        # increament frame ID
        self.frame_ID_software += 1
        self.frame_ID += 1
        self.timestamp = time.time()

        # right now support the raw format only
        if self.data_format == 'RGB':
            if self.pixel_format == 'RGB24':
                # self.current_frame = QImage(self.buf, self.w, self.h, (self.w * 24 + 31) // 32 * 4, QImage.Format_RGB888)
                print('convert buffer to image not yet implemented for the RGB format')
            return()
        else:
            if self.pixel_size_byte == 1:
                raw_image = np.frombuffer(self.buf, dtype='uint8')
            elif self.pixel_size_byte == 2:
                raw_image = np.frombuffer(self.buf, dtype='uint16')
            self.current_frame = raw_image.reshape(self.height,self.width)

        # for debugging
        print(self.current_frame.shape)
        print(self.current_frame.dtype)

        # frame ID for hardware triggered acquisition
        if self.trigger_mode == TriggerMode.HARDWARE:
            if self.frame_ID_offset_hardware_trigger == None:
                self.frame_ID_offset_hardware_trigger = self.frame_ID
            self.frame_ID = self.frame_ID - self.frame_ID_offset_hardware_trigger

        self.image_is_ready = True

        if self.callback_is_enabled == True:
            self.new_image_callback_external(self)

    def _TDIBWIDTHBYTES(w):
        return (w * 24 + 31) // 32 * 4

    def __init__(self,sn=None,resolution=None,is_global_shutter=False,rotate_image_angle=None,flip_image=None):

        # many to be purged
        self.sn = sn
        self.is_global_shutter = is_global_shutter
        self.device_info_list = None
        self.device_index = 0
        self.camera = None
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
        self.callback_was_enabled_before_autofocus = False
        self.callback_was_enabled_before_multipoint = False
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

        # toupcam
        self.data_format = 'RAW'
        self.devices = toupcam.Toupcam.EnumV2()
        self.image_is_ready = False
        self._toupcam_pullmode_started = False
        self._software_trigger_sent = False
        self._last_software_trigger_timestamp = None
        if resolution != None:
            self.resolution = resolution

        # toupcam temperature
        self.terminate_read_temperature_thread = False
        self.thread_read_temperature = threading.Thread(target=self.check_temperature, daemon=True)
        
    def check_temperature(self):
        while self.terminate_read_temperature_thread == False:
            time.sleep(2)
            # print('[ camera temperature: ' + str(self.get_temperature()) + ' ]')
            self.temperature_reading_callback(self.get_temperature())

    def open(self,index=0):
        if len(self.devices) > 0:
            print('{}: flag = {:#x}, preview = {}, still = {}'.format(self.devices[0].displayname, self.devices[0].model.flag, self.devices[0].model.preview, self.devices[0].model.still))
            for r in self.devices[index].model.res:
                print('\t = [{} x {}]'.format(r.width, r.height))
            self.camera = toupcam.Toupcam.Open(self.devices[index].id)            

            # RGB format: The output of every pixel contains 3 componants which stand for R/G/B value respectively. This output is a processed output from the internal color processing engine.
            # RAW format: In this format, the output is the raw data directly output from the sensor. The RAW format is for the users that want to skip the internal color processing and obtain the raw data for user-specific purpose. With the raw format output enabled, the functions that are related to the internal color processing will not work, such as Toupcam_put_Hue or Toupcam_AwbOnce function and so on
            
            # set temperature
            # print('max fan speed is ' + str(self.camera.FanMaxSpeed()))
            self.set_fan_speed(1)
            self.set_temperature(0)

            self.set_data_format('RAW')
            self.set_pixel_format('MONO8') # 'MONO16'
            self.set_auto_exposure(False)
            if self.resolution != None:
                self.set_resolution(self.resolution[0],self.resolution[1]) # buffer created when setting resolution
            else:
                # self.set_resolution(0) # buffer created when setting resolution, # use the max resolution # to create the function with one input
                pass
            self._update_buffer_settings()
            
            if self.camera:
                if self.buf:
                    try:
                        self.camera.StartPullModeWithCallback(self._event_callback, self)
                    except toupcam.HRESULTException as ex:
                        print('failed to start camera, hr=0x{:x}'.format(ex.hr))
                        exit()
                self._toupcam_pullmode_started = True
            else:
                print('failed to open camera')
                exit()
        else:
            print('no camera found')

        self.is_color = False
        if self.is_color:
            pass

        self.thread_read_temperature.start()

    def set_callback(self,function):
        self.new_image_callback_external = function

    def set_temperature_reading_callback(self, func):
        self.temperature_reading_callback = func

    def enable_callback(self):
        self.callback_is_enabled = True

    def disable_callback(self):
        self.callback_is_enabled = False

    def open_by_sn(self,sn):
        pass

    def close(self):
        self.terminate_read_temperature_thread = True
        self.thread_read_temperature.join()
        self.set_fan_speed(0)
        self.camera.Close()
        self.camera = None
        self.buf = None
        self.last_raw_image = None
        self.last_converted_image = None
        self.last_numpy_image = None

    def set_exposure_time(self,exposure_time):
        # exposure time in ms
        self.camera.put_ExpoTime(int(exposure_time*1000))
        # use_strobe = (self.trigger_mode == TriggerMode.HARDWARE) # true if using hardware trigger
        # if use_strobe == False or self.is_global_shutter:
        #     self.exposure_time = exposure_time
        #     self.camera.ExposureTime.set(exposure_time * 1000)
        # else:
        #     # set the camera exposure time such that the active exposure time (illumination on time) is the desired value
        #     self.exposure_time = exposure_time
        #     # add an additional 500 us so that the illumination can fully turn off before rows start to end exposure
        #     camera_exposure_time = self.exposure_delay_us + self.exposure_time*1000 + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1) + 500 # add an additional 500 us so that the illumination can fully turn off before rows start to end exposure
        #     self.camera.ExposureTime.set(camera_exposure_time)
        self.exposure_time = exposure_time

    def update_camera_exposure_time(self):
        pass
        # use_strobe = (self.trigger_mode == TriggerMode.HARDWARE) # true if using hardware trigger
        # if use_strobe == False or self.is_global_shutter:
        #     self.camera.ExposureTime.set(self.exposure_time * 1000)
        # else:
        #     camera_exposure_time = self.exposure_delay_us + self.exposure_time*1000 + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1) + 500 # add an additional 500 us so that the illumination can fully turn off before rows start to end exposure
        #     self.camera.ExposureTime.set(camera_exposure_time)

    def set_analog_gain(self,analog_gain):
        self.analog_gain = analog_gain
        # self.camera.Gain.set(analog_gain)

    def get_awb_ratios(self):
        pass

    def set_wb_ratios(self, wb_r=None, wb_g=None, wb_b=None):
        pass

    def set_reverse_x(self,value):
        pass

    def set_reverse_y(self,value):
        pass

    def start_streaming(self):
        if self.buf and (self._toupcam_pullmode_started == False):
            try:
                self.camera.StartPullModeWithCallback(self._event_callback, self)
                self._toupcam_pullmode_started = True
            except toupcam.HRESULTException as ex:
                print('failed to start camera, hr=0x{:x}'.format(ex.hr))
                exit()
        print('  start streaming')
        self.is_streaming = True

    def stop_streaming(self):
        self.camera.Stop()
        self.is_streaming = False
        self._toupcam_pullmode_started = False

    def set_pixel_format(self,pixel_format):

        # if self.is_streaming == True:
        #     was_streaming = True
        #     self.stop_streaming()
        # else:
        #     was_streaming = False

        if self._toupcam_pullmode_started:
            self.camera.Stop()

        if self.data_format == 'RAW':
            if pixel_format == 'MONO8':
                self.pixel_size_byte = 1
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,0)
            elif pixel_format == 'MONO12':
                self.pixel_size_byte = 2
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,1)
            elif pixel_format == 'MONO14':
                self.pixel_size_byte = 2
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,1)
            elif pixel_format == 'MONO16':
                self.pixel_size_byte = 2
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,1)
        else:
            # RGB data format
            if pixel_format == 'MONO8':
                self.pixel_size_byte = 1
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,0)
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_RGB,3) # for monochrome camera only
            if pixel_format == 'MONO12':
                self.pixel_size_byte = 2
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,1)
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_RGB,4) # for monochrome camera only
            if pixel_format == 'MONO14':
                self.pixel_size_byte = 2
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,1)
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_RGB,4) # for monochrome camera only
            if pixel_format == 'MONO16':
                self.pixel_size_byte = 2
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,1)
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_RGB,4) # for monochrome camera only
            if pixel_format == 'RGB24':
                self.pixel_size_byte = 3
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,0)
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_RGB,0)
            if pixel_format == 'RGB32':
                self.pixel_size_byte = 4
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,0)
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_RGB,2)
            if pixel_format == 'RGB48':
                self.pixel_size_byte = 6
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_BITDEPTH,1)
                self.camera.put_Option(toupcam.TOUPCAM_OPTION_RGB,1)

        if self._toupcam_pullmode_started:
            self._update_buffer_settings()
            if self.buf:
                try:
                    self.camera.StartPullModeWithCallback(self._event_callback, self)
                except toupcam.HRESULTException as ex:
                    print('failed to start camera, hr=0x{:x}'.format(ex.hr))
                    exit()

        #     if pixel_format == 'BAYER_RG8':
        #         self.camera.PixelFormat.set(gx.GxPixelFormatEntry.BAYER_RG8)
        #         self.pixel_size_byte = 1
        #     if pixel_format == 'BAYER_RG12':
        #         self.camera.PixelFormat.set(gx.GxPixelFormatEntry.BAYER_RG12)
        #         self.pixel_size_byte = 2
        #     self.pixel_format = pixel_format
        # else:
        #     print("pixel format is not implemented or not writable")

        # if was_streaming:
        #    self.start_streaming()

        # # update the exposure delay and strobe delay
        # self.exposure_delay_us = self.exposure_delay_us_8bit*self.pixel_size_byte
        # self.strobe_delay_us = self.exposure_delay_us + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1)

        # It is forbidden to call Toupcam_put_Option with TOUPCAM_OPTION_BITDEPTH in the callback context of 
        # PTOUPCAM_EVENT_CALLBACK and PTOUPCAM_DATA_CALLBACK_V3, the return value is E_WRONG_THREAD

    def set_auto_exposure(self,enabled):
        self.camera.put_AutoExpoEnable(enabled)

    def set_data_format(self,data_format):
        self.data_format = data_format
        if data_format == 'RGB':
            self.camera.put_Option(toupcam.TOUPCAM_OPTION_RAW,0) # 0 is RGB mode, 1 is RAW mode
        elif data_format == 'RAW':
            self.camera.put_Option(toupcam.TOUPCAM_OPTION_RAW,1) # 1 is RAW mode, 0 is RGB mode

    def set_resolution(self,width,height):
        self.camera.put_Size(width,height)

    def _update_buffer_settings(self):
        # resize the buffer
        width, height = self.camera.get_Size()
        self.width = width
        self.height = height
        # calculate buffer size
        if (self.data_format == 'RGB') & (self.pixel_size_byte != 4):
            bufsize = _TDIBWIDTHBYTES(self.width * self.pixel_size_byte * 8) * height
        else:
            bufsize = width * self.pixel_size_byte * height
        print('image size: {} x {}, bufsize = {}'.format(width, height, bufsize))
        # create the buffer
        self.buf = bytes(bufsize)

    def get_temperature(self):
        return self.camera.get_Temperature()/10

    def set_temperature(self,temperature):
        self.camera.put_Temperature(int(temperature*10))

    def set_fan_speed(self,speed):
        self.camera.put_Option(toupcam.TOUPCAM_OPTION_FAN,speed)

    def set_continuous_acquisition(self):
        self.camera.put_Option(toupcam.TOUPCAM_OPTION_TRIGGER,0)
        self.trigger_mode = TriggerMode.CONTINUOUS
        # self.update_camera_exposure_time()

    def set_software_triggered_acquisition(self):
        self.camera.put_Option(toupcam.TOUPCAM_OPTION_TRIGGER,1)
        self.trigger_mode = TriggerMode.SOFTWARE
        # self.update_camera_exposure_time()

    def set_hardware_triggered_acquisition(self):
        self.camera.put_Option(toupcam.TOUPCAM_OPTION_TRIGGER,2)
        self.frame_ID_offset_hardware_trigger = None
        self.trigger_mode = TriggerMode.HARDWARE
        # self.update_camera_exposure_time()

    def set_gain_mode(self,mode):
        if mode == 'LCG':
            self.camera.put_Option(toupcam.TOUPCAM_OPTION_CG,0)
        elif mode == 'HCG':
            self.camera.put_Option(toupcam.TOUPCAM_OPTION_CG,1)
        elif mode == 'HDR':
            self.camera.put_Option(toupcam.TOUPCAM_OPTION_CG,2)
            
    def send_trigger(self):
        if self._last_software_trigger_timestamp!= None:
            if (time.time() - self._last_software_trigger_timestamp) > (self.exposure_time*1000*1.02 + 4):
                print('last software trigger timed out')
                self._software_trigger_sent = False
        if self.is_streaming and self._software_trigger_sent == False:
            self.camera.Trigger(1)
            self._software_trigger_sent = True
            self._last_software_trigger_timestamp = time.time()
            print('  >>> trigger sent')
        else:
            if self.is_streaming == False:
                print('trigger not sent - camera is not streaming')
            else:
                print('trigger not sent - waiting for the last trigger to complete')

    def read_frame(self):
        self.image_is_ready = False
        self.send_trigger()
        timestamp_t0 = time.time()
        while (time.time() - timestamp_t0) <= self.exposure_time*1000*1.02 + 4:
            time.sleep(0.005)
            if self.image_is_ready:
                return self.current_frame
        print('read frame timed out')
    
    def set_ROI(self,offset_x=None,offset_y=None,width=None,height=None):
        # if offset_x is not None:
        #     self.ROI_offset_x = offset_x
        #     # stop streaming if streaming is on
        #     if self.is_streaming == True:
        #         was_streaming = True
        #         self.stop_streaming()
        #     else:
        #         was_streaming = False
        #     # update the camera setting
        #     if self.camera.OffsetX.is_implemented() and self.camera.OffsetX.is_writable():
        #         self.camera.OffsetX.set(self.ROI_offset_x)
        #     else:
        #         print("OffsetX is not implemented or not writable")
        #     # restart streaming if it was previously on
        #     if was_streaming == True:
        #         self.start_streaming()

        # if offset_y is not None:
        #     self.ROI_offset_y = offset_y
        #         # stop streaming if streaming is on
        #     if self.is_streaming == True:
        #         was_streaming = True
        #         self.stop_streaming()
        #     else:
        #         was_streaming = False
        #     # update the camera setting
        #     if self.camera.OffsetY.is_implemented() and self.camera.OffsetY.is_writable():
        #         self.camera.OffsetY.set(self.ROI_offset_y)
        #     else:
        #         print("OffsetX is not implemented or not writable")
        #     # restart streaming if it was previously on
        #     if was_streaming == True:
        #         self.start_streaming()

        # if width is not None:
        #     self.ROI_width = width
        #     # stop streaming if streaming is on
        #     if self.is_streaming == True:
        #         was_streaming = True
        #         self.stop_streaming()
        #     else:
        #         was_streaming = False
        #     # update the camera setting
        #     if self.camera.Width.is_implemented() and self.camera.Width.is_writable():
        #         self.camera.Width.set(self.ROI_width)
        #     else:
        #         print("OffsetX is not implemented or not writable")
        #     # restart streaming if it was previously on
        #     if was_streaming == True:
        #         self.start_streaming()

        # if height is not None:
        #     self.ROI_height = height
        #     # stop streaming if streaming is on
        #     if self.is_streaming == True:
        #         was_streaming = True
        #         self.stop_streaming()
        #     else:
        #         was_streaming = False
        #     # update the camera setting
        #     if self.camera.Height.is_implemented() and self.camera.Height.is_writable():
        #         self.camera.Height.set(self.ROI_height)
        #     else:
        #         print("Height is not implemented or not writable")
        #     # restart streaming if it was previously on
        #     if was_streaming == True:
        #         self.start_streaming()
        pass

    def reset_camera_acquisition_counter(self):
        # if self.camera.CounterEventSource.is_implemented() and self.camera.CounterEventSource.is_writable():
        #     self.camera.CounterEventSource.set(gx.GxCounterEventSourceEntry.LINE2)
        # else:
        #     print("CounterEventSource is not implemented or not writable")

        # if self.camera.CounterReset.is_implemented():
        #     self.camera.CounterReset.send_command()
        # else:
        #     print("CounterReset is not implemented")
        pass

    def set_line3_to_strobe(self):
        # # self.camera.StrobeSwitch.set(gx.GxSwitchEntry.ON)
        # self.camera.LineSelector.set(gx.GxLineSelectorEntry.LINE3)
        # self.camera.LineMode.set(gx.GxLineModeEntry.OUTPUT)
        # self.camera.LineSource.set(gx.GxLineSourceEntry.STROBE)
        pass

    def set_line3_to_exposure_active(self):
        # # self.camera.StrobeSwitch.set(gx.GxSwitchEntry.ON)
        # self.camera.LineSelector.set(gx.GxLineSelectorEntry.LINE3)
        # self.camera.LineMode.set(gx.GxLineModeEntry.OUTPUT)
        # self.camera.LineSource.set(gx.GxLineSourceEntry.EXPOSURE_ACTIVE)
        pass

class Camera_Simulation(object):
    
    def __init__(self,sn=None,is_global_shutter=False,rotate_image_angle=None,flip_image=None):
        # many to be purged
        self.sn = sn
        self.is_global_shutter = is_global_shutter
        self.device_info_list = None
        self.device_index = 0
        self.camera = None
        self.is_color = None
        self.gamma_lut = None
        self.contrast_lut = None
        self.color_correction_param = None

        self.rotate_image_angle = rotate_image_angle
        self.flip_image = flip_image

        self.exposure_time = 0
        self.analog_gain = 0
        self.frame_ID = 0
        self.frame_ID_software = -1
        self.frame_ID_offset_hardware_trigger = 0
        self.timestamp = 0

        self.image_locked = False
        self.current_frame = None

        self.callback_is_enabled = False
        self.callback_was_enabled_before_autofocus = False
        self.callback_was_enabled_before_multipoint = False

        self.GAIN_MAX = 24
        self.GAIN_MIN = 0
        self.GAIN_STEP = 1
        self.EXPOSURE_TIME_MS_MIN = 0.01
        self.EXPOSURE_TIME_MS_MAX = 4000

        self.trigger_mode = None
        self.pixel_size_byte = 1

        # below are values for IMX226 (MER2-1220-32U3M) - to make configurable 
        self.row_period_us = 10
        self.row_numbers = 3036
        self.exposure_delay_us_8bit = 650
        self.exposure_delay_us = self.exposure_delay_us_8bit*self.pixel_size_byte
        self.strobe_delay_us = self.exposure_delay_us + self.row_period_us*self.pixel_size_byte*(self.row_numbers-1)

        self.pixel_format = 'MONO8'

    def open(self,index=0):
        pass

    def set_callback(self,function):
        self.new_image_callback_external = function

    def set_temperature_reading_callback(self, func):
        self.temperature_reading_callback = func

    def enable_callback(self):
        self.callback_is_enabled = True

    def disable_callback(self):
        self.callback_is_enabled = False

    def open_by_sn(self,sn):
        pass

    def close(self):
        pass

    def set_exposure_time(self,exposure_time):
        pass

    def update_camera_exposure_time(self):
        pass

    def set_analog_gain(self,analog_gain):
        pass

    def get_awb_ratios(self):
        pass

    def set_wb_ratios(self, wb_r=None, wb_g=None, wb_b=None):
        pass

    def start_streaming(self):
        self.frame_ID_software = 0

    def stop_streaming(self):
        pass

    def set_pixel_format(self,pixel_format):
        self.pixel_format = pixel_format
        print(pixel_format)
        self.frame_ID = 0

    def get_temperature(self):
        return 0

    def set_temperature(self,temperature):
        pass

    def set_fan_speed(self,speed):
        pass

    def set_continuous_acquisition(self):
        pass

    def set_software_triggered_acquisition(self):
        pass

    def set_hardware_triggered_acquisition(self):
        pass

    def send_trigger(self):
        self.frame_ID = self.frame_ID + 1
        self.timestamp = time.time()
        if self.frame_ID == 1:
            if self.pixel_format == 'MONO8':
                self.current_frame = np.random.randint(255,size=(2000,2000),dtype=np.uint8)
                self.current_frame[901:1100,901:1100] = 200
            elif self.pixel_format == 'MONO12':
                self.current_frame = np.random.randint(4095,size=(2000,2000),dtype=np.uint16)
                self.current_frame[901:1100,901:1100] = 200*16
                self.current_frame = self.current_frame << 4
            elif self.pixel_format == 'MONO16':
                self.current_frame = np.random.randint(65535,size=(2000,2000),dtype=np.uint16)
                self.current_frame[901:1100,901:1100] = 200*256
        else:
            self.current_frame = np.roll(self.current_frame,10,axis=0)
            pass 
            # self.current_frame = np.random.randint(255,size=(768,1024),dtype=np.uint8)
        if self.new_image_callback_external is not None and self.callback_is_enabled:
            self.new_image_callback_external(self)

    def read_frame(self):
        return self.current_frame

    def _on_frame_callback(self, user_param, raw_image):
        pass

    def set_ROI(self,offset_x=None,offset_y=None,width=None,height=None):
        pass

    def reset_camera_acquisition_counter(self):
        pass

    def set_line3_to_strobe(self):
        pass

    def set_line3_to_exposure_active(self):
        pass