import ctypes
from ctypes import *

import squid.logging
from control.TUCam import *
import numpy as np
import threading
import time

from control._def import *

def get_sn_by_model(model_name):
    TUCAMINIT = TUCAM_INIT(0, './control'.encode('utf-8'))
    TUCAM_Api_Init(pointer(TUCAMINIT))
    
    for i in range(TUCAMINIT.uiCamCount):
        TUCAMOPEN = TUCAM_OPEN(i, 0)
        TUCAM_Dev_Open(pointer(TUCAMOPEN))
        TUCAMVALUEINFO = TUCAM_VALUE_INFO(TUCAM_IDINFO.TUIDI_CAMERA_MODEL.value, 0, 0, 0)
        TUCAM_Dev_GetInfo(TUCAMOPEN.hIdxTUCam, pointer(TUCAMVALUEINFO))
        if TUCAMVALUEINFO.pText == model_name:
            TUCAM_Reg_Read = TUSDKdll.TUCAM_Reg_Read
            cSN = (c_char * 64)()
            pSN = cast(cSN, c_char_p)
            TUCAMREGRW = TUCAM_REG_RW(1, pSN, 64)
            TUCAM_Reg_Read(TUCAMOPEN.hIdxTUCam, TUCAMREGRW)
            sn = string_at(pSN).decode('utf-8')

            TUCAM_Dev_Close(TUCAMOPEN.hIdxTUCam)
            TUCAM_Api_Uninit()
            return sn

        TUCAM_Dev_Close(TUCAMOPEN.hIdxTUCam)
    
    TUCAM_Api_Uninit()
    return None


class Camera(object):
    def __init__(self, sn=None, resolution=(6240, 4168), is_global_shutter=False, rotate_image_angle=None, flip_image=None):
        self.log = squid.logging.get_logger(self.__class__.__name__)

        self.sn = sn
        self.resolution = resolution
        self.is_global_shutter = is_global_shutter
        self.rotate_image_angle = rotate_image_angle
        self.flip_image = flip_image

        self.TUCAMINIT = TUCAM_INIT(0, './control'.encode('utf-8'))
        self.TUCAMOPEN = TUCAM_OPEN(0, 0)
        self.trigger_attr = TUCAM_TRIGGER_ATTR()
        self.m_frame = None     # buffer
        
        self.exposure_time = 1  # ms
        self.analog_gain = 0
        self.is_streaming = False
        self.pixel_format = None
        self.is_color = False

        self.frame_ID = -1
        self.frame_ID_software = -1
        self.frame_ID_offset_hardware_trigger = 0
        self.timestamp = 0
        self.trigger_mode = None

        self.image_locked = False
        self.current_frame = None
        self.callback_is_enabled = False
        self.new_image_callback_external = None
        self.stop_waiting = False

        self.temperature_reading_callback = None
        self.terminate_read_temperature_thread = False
        self.temperature_reading_thread = threading.Thread(target=self.check_temperature, daemon=True)

        self.GAIN_MAX = 20.0
        self.GAIN_MIN = 0.0
        self.GAIN_STEP = 1.0
        self.EXPOSURE_TIME_MS_MIN = 0.0347
        self.EXPOSURE_TIME_MS_MAX = 31640472.76

        self.ROI_offset_x = 0
        self.ROI_offset_y = 0
        self.ROI_width = 6240
        self.ROI_height = 4168

        self.OffsetX = 0
        self.OffsetY = 0
        self.Width = 6240
        self.Height = 4168

        self.WidthMax = 6240
        self.HeightMax = 4168
        self.binning_options = {
            (6240, 4168): 0, (3120, 2084): 1, (2080, 1388): 2, (1560, 1040): 3, 
            (1248, 832): 4, (1040, 692): 5, (780, 520): 6, (388, 260): 7
        }

    def open(self, index=0):
        TUCAM_Api_Init(pointer(self.TUCAMINIT))
        self.log.info(f'Connect {self.TUCAMINIT.uiCamCount} camera(s)')
        
        if index >= self.TUCAMINIT.uiCamCount:
            self.log.error('Camera index out of range')
            # TODO(imo): Propagate error in some way and handle
            return

        self.TUCAMOPEN = TUCAM_OPEN(index, 0)
        TUCAM_Dev_Open(pointer(self.TUCAMOPEN))

        # TODO(imo): Propagate error in some way and handle
        if self.TUCAMOPEN.hIdxTUCam == 0:
            self.log.error('Open Tucsen camera failure!')
        else:
            self.log.info('Open Tucsen camera success!')

        self.set_temperature(20)
        self.temperature_reading_thread.start()

    def open_by_sn(self, sn):
        TUCAM_Api_Init(pointer(self.TUCAMINIT))
        
        for i in range(self.TUCAMINIT.uiCamCount):
            TUCAMOPEN = TUCAM_OPEN(i, 0)
            TUCAM_Dev_Open(pointer(TUCAMOPEN))

            TUCAM_Reg_Read = TUSDKdll.TUCAM_Reg_Read
            cSN = (c_char * 64)()
            pSN = cast(cSN, c_char_p)
            TUCAMREGRW = TUCAM_REG_RW(1, pSN, 64)
            TUCAM_Reg_Read(TUCAMOPEN.hIdxTUCam, TUCAMREGRW)

            if string_at(pSN).decode('utf-8') == sn:
                self.TUCAMOPEN = TUCAMOPEN
                self.set_temperature(20)
                self.temperature_reading_thread.start()
                self.log.info(f'Open the camera success! sn={sn}')
                return
            else:
                TUCAM_Dev_Close(TUCAMOPEN.hIdxTUCam)

        # TODO(imo): Propagate error in some way and handle
        self.log.error('No camera with the specified serial number found')

    def close(self):
        self.disable_callback()
        self.terminate_read_temperature_thread = True
        self.temperature_reading_thread.join()
        TUCAM_Buf_Release(self.TUCAMOPEN.hIdxTUCam)
        TUCAM_Dev_Close(self.TUCAMOPEN.hIdxTUCam)
        TUCAM_Api_Uninit()
        self.log.info('Close Tucsen camera success')

    def set_callback(self, function):
        self.new_image_callback_external = function

    def enable_callback(self):
        if self.callback_is_enabled:
            return

        if not self.is_streaming:
            self.start_streaming()

        self.stop_waiting = False
        self.callback_thread = threading.Thread(target=self._wait_and_callback)
        self.callback_thread.start()

        self.callback_is_enabled = True
        self.log.debug('enable callback')

    def _wait_and_callback(self):
        while not self.stop_waiting:
            result = TUCAM_Buf_WaitForFrame(self.TUCAMOPEN.hIdxTUCam, pointer(self.m_frame), int(self.exposure_time + 1000))
            if result == TUCAMRET.TUCAMRET_SUCCESS:
                self._on_new_frame(self.m_frame)

        TUCAM_Buf_AbortWait(self.TUCAMOPEN.hIdxTUCam)
        TUCAM_Cap_Stop(self.TUCAMOPEN.hIdxTUCam)
        TUCAM_Buf_Release(self.TUCAMOPEN.hIdxTUCam)

    def _on_new_frame(self, frame):
        # TODO(imo): Propagate error in some way and handle
        if frame is False:
            self.log.error('Cannot get new frame from buffer.')
            return
        if self.image_locked:
            self.log.error('Last image is still being processed; a frame is dropped')
            return

        self.current_frame = self._convert_frame_to_numpy(frame)

        self.frame_ID_software += 1
        self.frame_ID += 1 

        # frame ID for hardware triggered acquisition
        if self.trigger_mode == TriggerMode.HARDWARE:
            if self.frame_ID_offset_hardware_trigger == None:
                self.frame_ID_offset_hardware_trigger = self.frame_ID
            self.frame_ID = self.frame_ID - self.frame_ID_offset_hardware_trigger

        self.timestamp = time.time()
        self.new_image_callback_external(self)

    def disable_callback(self):
        if not self.callback_is_enabled:
            return

        was_streaming = self.is_streaming

        self.stop_waiting = True
        self.is_streaming = False

        if hasattr(self, 'callback_thread'):
            self.callback_thread.join()
            del self.callback_thread
        self.callback_is_enabled = False

        if was_streaming:
            self.start_streaming()
        self.log.debug('disable callback')

    def set_temperature_reading_callback(self, func):
        self.temperature_reading_callback = func

    def set_temperature(self, temperature):
        t = temperature * 10 + 500
        result = TUCAM_Prop_SetValue(self.TUCAMOPEN.hIdxTUCam, TUCAM_IDPROP.TUIDP_TEMPERATURE.value, c_double(t), 0)

    def get_temperature(self):
        t = c_double(0)
        TUCAM_Prop_GetValue(self.TUCAMOPEN.hIdxTUCam, TUCAM_IDPROP.TUIDP_TEMPERATURE.value, pointer(t), 0)
        return t.value

    def check_temperature(self):
        while self.terminate_read_temperature_thread == False:
            time.sleep(2)
            temperature = self.get_temperature()
            if self.temperature_reading_callback is not None:
                try:
                    self.temperature_reading_callback(temperature)
                except TypeError as ex:
                    self.log.error("Temperature read callback failed due to error: "+repr(ex))
                    # TODO(imo): Propagate error in some way and handle
                    pass

    def set_resolution(self, width, height):
        was_streaming = False
        if self.is_streaming:
            self.stop_streaming()
            was_streaming = True

        if not (width, height) in self.binning_options:
            self.log.error(f"No suitable binning found for resolution {width}x{height}")
            # TODO(imo): Propagate error in some way and handle
            return

        bin_value = c_int(self.binning_options[(width, height)])
        try:
            TUCAM_Capa_SetValue(self.TUCAMOPEN.hIdxTUCam, TUCAM_IDCAPA.TUIDC_BINNING_SUM.value, bin_value)

        except Exception:
            self.log.error('Cannot set binning.')
            # TODO(imo): Propagate error in some way and handle

        if was_streaming:
            self.start_streaming()

    def set_auto_exposure(self, enable=False):
        value = 1 if enable else 0
        TUCAM_Capa_SetValue(self.TUCAMOPEN.hIdxTUCam, TUCAM_IDCAPA.TUIDC_ATEXPOSURE.value, value)

        if enable:
            self.log.info("Auto exposure enabled")
        else:
            self.log.info("Auto exposure disabled")

    def set_exposure_time(self, exposure_time):
        # Disable auto-exposure
        TUCAM_Capa_SetValue(self.TUCAMOPEN.hIdxTUCam, TUCAM_IDCAPA.TUIDC_ATEXPOSURE.value, 0)
        # Set the exposure time
        TUCAM_Prop_SetValue(self.TUCAMOPEN.hIdxTUCam, TUCAM_IDPROP.TUIDP_EXPOSURETM.value, c_double(exposure_time), 0)
        self.exposure_time = exposure_time

    def set_analog_gain(self, gain):
        # Gain0: System Gain (DN/e-): 1.28; Full Well Capacity (e-): 49000; Readout Noise (e-): 2.7(Median), 3.3(RMS)
        # Gain1: System Gain (DN/e-): 3.98; Full Well Capacity (e-): 15700; Readout Noise (e-): 1.0(Median), 1.3(RMS)
        # Gain2: System Gain (DN/e-): 8.0; Full Well Capacity (e-): 7800; Readout Noise (e-): 0.95(Median), 1.2(RMS)
        # Gain3: System Gain (DN/e-): 20; Full Well Capacity (e-): 3000; Readout Noise (e-): 0.85(Median), 1.0(RMS)
        if gain < 2:
            value = 0
        elif gain >= 2 and gain < 4:
            value = 1
        elif gain >= 4 and gain < 9:
            value = 2
        else:
            value = 3
        TUCAM_Prop_SetValue(self.TUCAMOPEN.hIdxTUCam, TUCAM_IDPROP.TUIDP_GLOBALGAIN.value, c_double(value), 0)
        self.analog_gain = value

    def set_pixel_format(self, pixel_format):
        # TUIDC_BINNING_SUM value: [0, 6]
        # 0: "1*1Normal"; 1: "2*2Bin_Sum"; 2: "3*3Bin_Sum"; 3: "4*4Bin_Sum"; 4: "6*6Bin_Sum"; 5: "8*8Bin_Sum"; 6: "16*16Bin_Sum"
        # 0: 12bit; 1: 14bit; 2: 15bit; others: 16bit
        pass

    def set_continuous_acquisition(self):
        self.trigger_attr.nTgrMode = TUCAM_CAPTURE_MODES.TUCCM_SEQUENCE.value
        self.trigger_attr.nBufFrames = 1
        TUCAM_Cap_SetTrigger(self.TUCAMOPEN.hIdxTUCam, self.trigger_attr)
        self.trigger_mode = TriggerMode.CONTINUOUS

    def set_software_triggered_acquisition(self):
        self.trigger_attr.nTgrMode = TUCAM_CAPTURE_MODES.TUCCM_TRIGGER_SOFTWARE.value
        self.trigger_attr.nBufFrames = 1
        TUCAM_Cap_SetTrigger(self.TUCAMOPEN.hIdxTUCam, self.trigger_attr)
        self.trigger_mode = TriggerMode.SOFTWARE

    def set_hardware_triggered_acquisition(self):
        self.trigger_attr.nTgrMode = TUCAM_CAPTURE_MODES.TUCCM_TRIGGER_STANDARD.value
        self.trigger_attr.nBufFrames = 1
        TUCAM_Cap_SetTrigger(self.TUCAMOPEN.hIdxTUCam, self.trigger_attr)
        self.frame_ID_offset_hardware_trigger = None
        self.trigger_mode = TriggerMode.HARDWARE

    def set_ROI(self, offset_x=None, offset_y=None, width=None, height=None):
        roi_attr = TUCAM_ROI_ATTR()
        roi_attr.bEnable = 1
        roi_attr.nHOffset = offset_x if offset_x is not None else self.ROI_offset_x
        roi_attr.nVOffset = offset_y if offset_y is not None else self.ROI_offset_y
        roi_attr.nWidth = width if width is not None else self.ROI_width
        roi_attr.nHeight = height if height is not None else self.ROI_height

        was_streaming = False
        if self.is_streaming:
            self.stop_streaming()
            was_streaming = True

        try:
            TUCAM_Cap_SetROI(self.TUCAMOPEN.hIdxTUCam, roi_attr)

            self.ROI_offset_x = roi_attr.nHOffset
            self.ROI_offset_y = roi_attr.nVOffset
            self.ROI_width = roi_attr.nWidth
            self.ROI_height = roi_attr.nHeight

        except Exception:
            self.log.error('Cannot set ROI.')
            # TODO(imo): Propagate error in some way and handle

        if was_streaming:
            self.start_streaming()

    def send_trigger(self):
        if self.trigger_mode == TriggerMode.SOFTWARE:
            TUCAM_Cap_DoSoftwareTrigger(self.TUCAMOPEN.hIdxTUCam)
            self.log.debug("Trigger sent")

    def start_streaming(self):
        if self.is_streaming:
            return

        self.m_frame = TUCAM_FRAME()
        self.m_frame.pBuffer = 0
        self.m_frame.ucFormatGet = TUFRM_FORMATS.TUFRM_FMT_USUAl.value
        self.m_frame.uiRsdSize = 1

        result = TUCAM_Buf_Alloc(self.TUCAMOPEN.hIdxTUCam, pointer(self.m_frame))
        if result != TUCAMRET.TUCAMRET_SUCCESS:
            raise Exception("Failed to allocate buffer")
        result = TUCAM_Cap_Start(self.TUCAMOPEN.hIdxTUCam, self.trigger_attr.nTgrMode)
        if result != TUCAMRET.TUCAMRET_SUCCESS:
            TUCAM_Buf_Release(self.TUCAMOPEN.hIdxTUCam)
            raise Exception("Failed to start capture")

        self.is_streaming = True
        self.log.info('TUCam Camera starts streaming')

    def stop_streaming(self):
        if not self.is_streaming:
            return

        TUCAM_Cap_Stop(self.TUCAMOPEN.hIdxTUCam)
        TUCAM_Buf_Release(self.TUCAMOPEN.hIdxTUCam)
        self.is_streaming = False
        self.log.info('TUCam Camera streaming stopped')

    def read_frame(self):
        result = TUCAM_Buf_WaitForFrame(self.TUCAMOPEN.hIdxTUCam, pointer(self.m_frame), int(self.exposure_time + 1000))
        if result == TUCAMRET.TUCAMRET_SUCCESS:            
            self.current_frame = self._convert_frame_to_numpy(self.m_frame)
            TUCAM_Buf_AbortWait(self.TUCAMOPEN.hIdxTUCam)
            return self.current_frame
    
        return None

    def _convert_frame_to_numpy(self, frame):
        buf = create_string_buffer(frame.uiImgSize)
        pointer_data = c_void_p(frame.pBuffer + frame.usHeader)
        memmove(buf, pointer_data, frame.uiImgSize)

        data = bytes(buf)
        image_np = np.frombuffer(data, dtype=np.uint16)
        image_np = image_np.reshape((frame.usHeight, frame.usWidth))

        return image_np


class Camera_Simulation(object):
    
    def __init__(self,sn=None,is_global_shutter=False,rotate_image_angle=None,flip_image=None):
        self.log = squid.logging.get_logger(self.__class__.__name__)

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
        self.is_streaming = False

        self.GAIN_MAX = 0
        self.GAIN_MIN = 0
        self.GAIN_STEP = 0
        self.EXPOSURE_TIME_MS_MIN = 0.01
        self.EXPOSURE_TIME_MS_MAX = 4000

        self.trigger_mode = None

        self.pixel_format = 'MONO16'

        self.is_live = False

        self.Width = 6240
        self.Height = 4168
        self.WidthMax = 6240
        self.HeightMax = 4168
        self.OffsetX = 0
        self.OffsetY = 0

        self.new_image_callback_external = None


    def open(self,index=0):
        pass

    def set_callback(self,function):
        self.new_image_callback_external = function

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

    def set_analog_gain(self,analog_gain):
        pass

    def start_streaming(self):
        self.frame_ID_software = 0

    def stop_streaming(self):
        pass

    def set_pixel_format(self,pixel_format):
        self.pixel_format = pixel_format
        self.log.debug(f"Pixel format={pixel_format}")
        self.frame_ID = 0

    def set_continuous_acquisition(self):
        pass

    def set_software_triggered_acquisition(self):
        pass

    def set_hardware_triggered_acquisition(self):
        pass

    def send_trigger(self):
        self.log.debug('send trigger')
        self.frame_ID = self.frame_ID + 1
        self.timestamp = time.time()
        if self.frame_ID == 1:
            if self.pixel_format == 'MONO8':
                self.current_frame = np.random.randint(255,size=(2000,2000),dtype=np.uint8)
                self.current_frame[901:1100,901:1100] = 200
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

    def set_line3_to_strobe(self):
        pass
