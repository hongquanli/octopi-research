import argparse
import cv2
import time
import numpy as np
import threading

from control.dcam import Dcam, Dcamapi
from control.dcamapi4 import *
from control._def import *

def get_sn_by_model(model_name):
    try:
        _, count = Dcamapi.init()
    except TypeError:
        print('Cannot init Hamamatsu Camera.')
        sys.exit(1)

    for i in range(count):
        d = Dcam(i)
        sn = d.dev_getstring(DCAM_IDSTR.CAMERAID)
        if sn is not False:
            Dcamapi.uninit()
            print('Hamamatsu Camera ' + sn)
            return sn
        
    Dcamapi.uninit()
    return None 


class Camera(object):
    def __init__(self,sn=None, resolution=(2304,2304), is_global_shutter=False, rotate_image_angle=None, flip_image=None):
        self.dcam = None
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

        self.GAIN_MAX = 0
        self.GAIN_MIN = 0
        self.GAIN_STEP = 0
        self.EXPOSURE_TIME_MS_MIN = 0.017633
        self.EXPOSURE_TIME_MS_MAX = 10000.0046
        
        self.rotate_image_angle = rotate_image_angle
        self.flip_image = flip_image
        self.is_global_shutter = is_global_shutter
        self.sn = sn

        self.ROI_offset_x = 0
        self.ROI_offset_y = 0
        self.ROI_width = 2304
        self.ROI_height = 2304

        self.OffsetX =  0
        self.OffsetY = 0
        self.Width = 2304
        self.Height = 2304

        self.WidthMax = 2304
        self.HeightMax = 2304

    def open(self, index=0):
        result = Dcamapi.init()
        self.dcam = Dcam(index)
        result = self.dcam.dev_open(index) and result
        print('Hamamatsu Camera opened: ' + str(result))
        
    def open_by_sn(self, sn):
        unopened = 0
        success, count = Dcamapi.init()
        if success:
            for i in count:
                d = Dcam(i)
                if sn == d.dev_getstring(DCAM_IDSTR.CAMERAID):
                    self.dcam = d
                    print(self.dcam.dev_open(index))
                else:
                    unopened += 1
        if unopened == count or not success:
            print('Hamamatsu Camera open_by_sn: No camera is opened.')

    def close(self):
        self.disable_callback()
        result = self.dcam.dev_close() and Dcamapi.uninit()
        print('Hamamatsu Camera closed: ' + str(result))

    def set_callback(self, function):
        self.new_image_callback_external = function

    def enable_callback(self):
        if not self.is_streaming:
            self.start_streaming()

        self.stop_waiting = False
        self.callback_thread = threading.Thread(target=self._wait_and_callback)
        self.callback_thread.start()

        self.callback_is_enabled = True

    def _wait_and_callback(self):
        # Note: DCAM API doesn't provide a direct callback mechanism
        # This implementation uses the wait_event method to simulate a callback
        while True:
            if self.stop_waiting:
                break
            event = self.dcam.wait_event(DCAMWAIT_CAPEVENT.FRAMEREADY, 1000)
            if event is not False:
                self._on_new_frame()
        
    def _on_new_frame(self):
        image = self.read_frame(no_wait=True)
        if image is False:
            print('Cannot get new frame from buffer.')
            return
        if self.image_locked:
            print('Last image is still being processed; a frame is dropped')
            return

        self.current_frame = image
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
        if self.is_streaming:
            self.stop_streaming()

        self.stop_waiting = True
        self.callback_thread.join()
        del self.callback_thread
        self.callback_is_enabled = False

        if was_streaming:
            self.start_streaming()
        
    def set_analog_gain(self, gain):
        pass

    def set_exposure_time(self, exposure_time):
        if self.dcam.prop_setvalue(DCAM_IDPROP.EXPOSURETIME, exposure_time / 1000):
            self.exposure_time = exposure_time

    def set_continuous_acquisition(self):
        if self.dcam.prop_setvalue(DCAM_IDPROP.TRIGGERSOURCE, DCAMPROP.TRIGGERSOURCE.INTERNAL):
            self.trigger_mode = TriggerMode.SOFTWARE

    def set_software_triggered_acquisition(self):
        if self.dcam.prop_setvalue(DCAM_IDPROP.TRIGGERSOURCE, DCAMPROP.TRIGGERSOURCE.SOFTWARE):
            self.trigger_mode = TriggerMode.SOFTWARE

    def set_hardware_triggered_acquisition(self):
        if self.dcam.prop_setvalue(DCAM_IDPROP.TRIGGERSOURCE, DCAMPROP.TRIGGERSOURCE.EXTERNAL):
            self.frame_ID_offset_hardware_trigger = None
            self.trigger_mode = TriggerMode.HARDWARE

    def set_pixel_format(self, pixel_format):
        was_streaming = False
        if self.is_streaming:
            was_streaming = True
            self.stop_streaming()

        self.pixel_format = pixel_format

        if pixel_format == 'MONO8':
            result = self.dcam.prop_setvalue(DCAM_IDPROP.IMAGE_PIXELTYPE, DCAM_PIXELTYPE.MONO8)
        elif pixel_format == 'MONO16':
            result = self.dcam.prop_setvalue(DCAM_IDPROP.IMAGE_PIXELTYPE, DCAM_PIXELTYPE.MONO16)

        if was_streaming:
            self.start_streaming()

        print('Set pixel format: ' + str(result))

    def send_trigger(self):
        if self.is_streaming:
            if not self.dcam.cap_firetrigger():
                print('trigger not sent - firetrigger failed')
        else:
            print('trigger not sent - camera is not streaming')

    def read_frame(self, no_wait=False):
        if no_wait:
            return self.dcam.buf_getlastframedata()
       	else:
            if self.dcam.wait_capevent_frameready(5000) is not False:
                data = self.dcam.buf_getlastframedata()
                return data

            dcamerr = self.dcam.lasterr()
            if dcamerr.is_timeout():
                print('===: timeout')

            print('-NG: Dcam.wait_event() fails with error {}'.format(dcamerr))
        
    def start_streaming(self, buffer_frame_num=1):
        if self.dcam.buf_alloc(buffer_frame_num):
            if self.dcam.cap_start(True):
                self.is_streaming = True
                print('Hamamatsu Camera starts streaming')
            else:
                self.dcam.buf_release()
        print('Hamamatsu Camera cannot start streaming')

    def stop_streaming(self):
        if self.dcam.cap_stop() and self.dcam.buf_release():
            self.is_streaming = False
            print('Hamamatsu Camera streaming stopped')
        else:
            print('Hamamatsu Camera cannot stop streaming')

    def set_ROI(self,offset_x=None,offset_y=None,width=None,height=None):
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
        self.is_streaming = False

        self.GAIN_MAX = 0
        self.GAIN_MIN = 0
        self.GAIN_STEP = 0
        self.EXPOSURE_TIME_MS_MIN = 0.01
        self.EXPOSURE_TIME_MS_MAX = 4000

        self.trigger_mode = None

        self.pixel_format = 'MONO16'

        self.is_live = False

        self.Width = 3000
        self.Height = 3000
        self.WidthMax = 4000
        self.HeightMax = 3000
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
        print(pixel_format)
        self.frame_ID = 0

    def set_continuous_acquisition(self):
        pass

    def set_software_triggered_acquisition(self):
        pass

    def set_hardware_triggered_acquisition(self):
        pass

    def send_trigger(self):
        print('send trigger')
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
