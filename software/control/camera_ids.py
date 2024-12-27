import time
import numpy as np
import threading

from control._def import *

from ids_peak import ids_peak
from ids_peak_ipl import ids_peak_ipl
from ids_peak import ids_peak_ipl_extension

import squid.logging
log = squid.logging.get_logger(__name__)

def get_sn_by_model(model_name):
    ids_peak.Library.Initialize()
    device_manager = ids_peak.DeviceManager.Instance()
    device_manager.Update()
    if device_manager.Devices().empty():
        log.error('iDS camera not found.')
        # TODO(imo): Propagate error in some way and handle
        return
    devices = device_manager.Devices()
    for i in range(devices.size()):
        dev = device_manager.Devices()[i].OpenDevice(ids_peak.DeviceAccessType_Control)
        nodemap = dev.RemoteDevice().NodeMaps()[i]
        sn = nodemap.FindNode("DeviceSerialNumber").Value()
        mn = nodemap.FindNode("DeviceModelName").Value()
        #if mn == model_name:
            #return nodemap.FindNode("DeviceSerialNumber").Value()
        log.debug(f"get_sn_by_model: {mn}")
        return sn

    ids_peak.Library.Close()

    return None


class Camera(object):
    def __init__(self, sn=None, resolution=(1920,1080), is_global_shutter=False, rotate_image_angle=None, flip_image=None):
        self.log = squid.logging.get_logger(self.__class__.__name__)

        ids_peak.Library.Initialize()
        self.device_manager = ids_peak.DeviceManager.Instance()

        self.device = None
        self.datastream = None
        self.nodemap = None
        self.buffer_list = None
        self.image_converter = None

        self.exposure_time = 1  # ms
        self.analog_gain = 1
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

        self.GAIN_MAX = 31.6
        self.GAIN_MIN = 1.0
        self.GAIN_STEP = 0.01
        self.EXPOSURE_TIME_MS_MIN = 0.015
        self.EXPOSURE_TIME_MS_MAX = 1999
        
        self.rotate_image_angle = rotate_image_angle
        self.flip_image = flip_image
        self.is_global_shutter = is_global_shutter
        self.sn = sn

        self.ROI_offset_x = 0
        self.ROI_offset_y = 0
        self.ROI_width = 1936
        self.ROI_height = 1096

        self.OffsetX = 0
        self.OffsetY = 0
        self.Width = 1920
        self.Height = 1080

        self.WidthMax = 1920
        self.HeightMax = 1080

    def open(self, index=0):
        self.device_manager.Update()
        if self.device_manager.Devices().empty():
            self.log.error('iDS camera not found.')
            # TODO(imo): Propagate error in some way and handle
            return
        self.device = self.device_manager.Devices()[index].OpenDevice(ids_peak.DeviceAccessType_Control)
        if self.device is None:
            self.log.error('Cannot open iDS camera.')
            # TODO(imo): Propagate error in some way and handle
            return
        self.nodemap = self.device.RemoteDevice().NodeMaps()[0]

        self._camera_init()
        self.log.info('iDS camera opened.')

    def open_by_sn(self, sn):
        self.device_manager.Update()
        for i in range(self.device_manager.Devices().size()):
            dev = self.device_manager.Devices()[i]
            nodemap = dev.RemoteDevice().NodeMaps()[i]
            if sn == nodemap.FindNode("DeviceSerialNumber").Value():
                self.device = dev.OpenDevice(ids_peak.DeviceAccessType_Control)
                if self.device is None:
                    self.log.error('Cannot open iDS camera.')
                    # TODO(imo): Propagate error in some way and handle
                    return
                self.nodemap = nodemap
                self._camera_init()
                self.log.info(f'iDS camera opened by sn={sn}.')
                return
        self.log.error('No iDS camera is opened.')
        # TODO(imo): Propagate error in some way and handle
        return

    def _camera_init(self):
        gain_node = self.nodemap.FindNode("Gain")
        self.log.info(f'gain: min={gain_node.Minimum()}, max={gain_node.Maximum()}, increment={gain_node.Increment()}')

        # initialize software trigger
        entries = []
        for entry in self.nodemap.FindNode("TriggerSelector").Entries():
            if (entry.AccessStatus() != ids_peak.NodeAccessStatus_NotAvailable
                and entry.AccessStatus() != ids_peak.NodeAccessStatus_NotImplemented):
                entries.append(entry.SymbolicValue())

        if len(entries) == 0:
            raise Exception("Software Trigger not supported")
        elif "ExposureStart" not in entries:
            self.nodemap.FindNode("TriggerSelector").SetCurrentEntry(entries[0])
        else:
            self.nodemap.FindNode("TriggerSelector").SetCurrentEntry("ExposureStart")

        # initialize image converter
        self.image_converter = ids_peak_ipl.ImageConverter()

        # Open device's datastream
        ds = self.device.DataStreams()
        if ds.empty():
            self.log.error("Device has no datastream!")
            # TODO(imo): Propagate error in some way and handle
        else:
            self.datastream = ds[0].OpenDataStream()

    def close(self):
        self.stop_streaming()
        self.disable_callback()
        self._revoke_buffer()

        ids_peak.Library.Close()

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
        self.log.info("callback enabled")

    def _wait_and_callback(self):
        while True:
            if self.stop_waiting:
                break
            try:
                buffer = self.datastream.WaitForFinishedBuffer(2000)
                if buffer is not None:
                    self._on_new_frame(buffer)
            except Exception as e:
                pass

    def _on_new_frame(self, buffer):
        image = self.read_frame(no_wait=True, buffer=buffer)
        if image is False:
            # TODO(imo): Propagate error in some way and handle
            self.log.error('Cannot get new frame from buffer.')
            return
        if self.image_locked:
            # TODO(imo): Propagate error in some way and handle
            self.log.error('Last image is still being processed; a frame is dropped')
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
        self.log.info("callback disabled")

    def set_analog_gain(self, gain):
        if gain < self.GAIN_MIN:
            gain = self.GAIN_MIN
        elif gain > self.GAIN_MAX:
            gain = self.GAIN_MAX
        self.nodemap.FindNode("GainSelector").SetCurrentEntry("AnalogAll")
        self.nodemap.FindNode("Gain").SetValue(gain)
        self.analog_gain = gain

    def set_exposure_time(self, exposure_time):
        if exposure_time < self.EXPOSURE_TIME_MS_MIN:
            exposure_time = self.EXPOSURE_TIME_MS_MIN
        elif exposure_time > self.EXPOSURE_TIME_MS_MAX:
            exposure_time = self.EXPOSURE_TIME_MS_MAX
        self.nodemap.FindNode("ExposureTime").SetValue(exposure_time * 1000)
        self.exposure_time = exposure_time

    def set_continuous_acquisition(self):
        pass

    def set_software_triggered_acquisition(self):
        try:
            self.nodemap.FindNode("TriggerMode").SetCurrentEntry("On")
            self.nodemap.FindNode("TriggerSource").SetCurrentEntry("Software")
            self.trigger_mode = TriggerMode.SOFTWARE
        except Exception as e:
            self.log.error(f"Cannot set Software trigger", e)

    def set_hardware_triggered_acquisition(self):
        self.nodemap.FindNode("TriggerMode").SetCurrentEntry("On")
        self.nodemap.FindNode("TriggerSource").SetCurrentEntry("Line0")
        self.trigger_mode = TriggerMode.HARDWARE

    def set_pixel_format(self, pixel_format): 
        self.log.debug(f"Pixel format={pixel_format}")
        was_streaming = False
        if self.is_streaming:
            was_streaming = True
            self.stop_streaming()
        try:
            if pixel_format == 'MONO10':
                self.nodemap.FindNode("PixelFormat").SetCurrentEntry("Mono10g40IDS")
            elif pixel_format == 'MONO12':
                self.nodemap.FindNode("PixelFormat").SetCurrentEntry("Mono12g24IDS")
            else:
                raise Exception('Wrong pixel format.')
            self.pixel_format = pixel_format

            if was_streaming:
                self.start_streaming()
        except Exception as e:
            self.log.error("Cannot change pixelformat", e)

    def send_trigger(self):
        if self.is_streaming:
            self.nodemap.FindNode("TriggerSoftware").Execute()
            self.nodemap.FindNode("TriggerSoftware").WaitUntilDone()
            self.log.debug('Trigger sent')

    def read_frame(self, no_wait=False, buffer=None):
        if not no_wait:
            buffer = self.datastream.WaitForFinishedBuffer(2000)
            self.log.debug("Buffered image!")

        # Convert image and make deep copy
        if self.pixel_format == 'MONO10':
            output_pixel_format = ids_peak_ipl.PixelFormatName_Mono10
        elif self.pixel_format == 'MONO12':
            output_pixel_format = ids_peak_ipl.PixelFormatName_Mono12

        ipl_image = ids_peak_ipl_extension.BufferToImage(buffer)
        ipl_converted = self.image_converter.Convert(ipl_image, output_pixel_format)
        numpy_image = ipl_converted.get_numpy_1D().copy()

        self.current_frame = np.frombuffer(numpy_image, dtype=np.uint16).reshape(ipl_converted.Height(), ipl_converted.Width())

        self.datastream.QueueBuffer(buffer)

        return self.current_frame

    def start_streaming(self, extra_buffer=1):
        if self.is_streaming:
            return
        
        # Allocate image buffer for image acquisition
        self._revoke_buffer()
        self._allocate_buffer(extra_buffer)
        for buffer in self.buffer_list:
            self.datastream.QueueBuffer(buffer)

        # Lock parameters that should not be accessed during acquisition
        self.nodemap.FindNode("TLParamsLocked").SetValue(1)

        # Pre-allocate conversion buffers to speed up first image conversion
        # while the acquisition is running
        # NOTE: Re-create the image converter, so old conversion buffers
        #       get freed
        input_pixel_format = ids_peak_ipl.PixelFormat(
            self.nodemap.FindNode("PixelFormat").CurrentEntry().Value())
        if self.pixel_format == 'MONO10':
            output_pixel_format = ids_peak_ipl.PixelFormatName_Mono10
        elif self.pixel_format == 'MONO12':
            output_pixel_format = ids_peak_ipl.PixelFormatName_Mono12

        self.image_converter.PreAllocateConversion(
            input_pixel_format, output_pixel_format, self.Width, self.Height)

        self.datastream.StartAcquisition()
        self.nodemap.FindNode("AcquisitionStart").Execute()
        self.nodemap.FindNode("AcquisitionStart").WaitUntilDone()
        self.is_streaming = True
        self.log.info("ids started streaming")

    def _revoke_buffer(self):
        if self.datastream is None:
            self.log.error("No datastream!")
            # TODO(imo): Propagate error in some way and handle
            return

        try:
            # Remove buffers from the announced pool
            for buffer in self.datastream.AnnouncedBuffers():
                self.datastream.RevokeBuffer(buffer)
            self.buffer_list = None
        except Exception as e:
            self.log.error("Error revoking buffers", e)

    def _allocate_buffer(self, extra_buffer):
        if self.datastream is None:
            self.log.error("No datastream!")
            return

        try:
            self.buffer_list = []
            payload_size = self.nodemap.FindNode("PayloadSize").Value()
            buffer_amount = self.datastream.NumBuffersAnnouncedMinRequired() + extra_buffer

            for _ in range(buffer_amount):
                buffer = self.datastream.AllocAndAnnounceBuffer(payload_size)
                self.buffer_list.append(buffer)

            self.log.debug("Allocated buffers!")
        except Exception as e:
            self.log.error("Error allocating buffers", e)

    def stop_streaming(self):
        if self.is_streaming:
            try:
                self.nodemap.FindNode("AcquisitionStop").Execute()

                self.datastream.StopAcquisition(ids_peak.AcquisitionStopMode_Default)
                # Discard all buffers from the acquisition engine
                # They remain in the announced buffer pool
                self.datastream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)

                # Unlock parameters
                self.nodemap.FindNode("TLParamsLocked").SetValue(0)

                self.is_streaming = False
            except Exception as e:
                self.log.error("stop_streaming error", e)

    def set_ROI(self, offset_x=None, offset_y=None, width=None, height=None):
        pass


class Camera_Simulation(object):
    
    def __init__(self, sn=None, is_global_shutter=False, rotate_image_angle=None, flip_image=None):
        self.log = squid.logging.get_logger(self.__class__.__name__
                                            )
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

        self.pixel_format = 'MONO12'

        self.is_live = False

        self.Width = 1920
        self.Height = 1080
        self.WidthMax = 1920
        self.HeightMax = 1080
        self.OffsetX = 0
        self.OffsetY = 0

        self.new_image_callback_external = None

    def open(self, index=0):
        pass

    def set_callback(self, function):
        self.new_image_callback_external = function

    def enable_callback(self):
        self.callback_is_enabled = True

    def disable_callback(self):
        self.callback_is_enabled = False

    def open_by_sn(self, sn):
        pass

    def close(self):
        pass

    def set_exposure_time(self, exposure_time):
        pass

    def set_analog_gain(self, analog_gain):
        pass

    def start_streaming(self):
        self.frame_ID_software = 0

    def stop_streaming(self):
        pass

    def set_pixel_format(self, pixel_format):
        self.pixel_format = pixel_format
        self.log.info(f"pixel_format={pixel_format}")
        self.frame_ID = 0

    def set_continuous_acquisition(self):
        pass

    def set_software_triggered_acquisition(self):
        pass

    def set_hardware_triggered_acquisition(self):
        pass

    def send_trigger(self):
        self.log.info('send trigger')
        self.frame_ID = self.frame_ID + 1
        self.timestamp = time.time()
        if self.frame_ID == 1:
            self.current_frame = np.random.randint(255, size=(2000,2000), dtype=np.uint8)
            self.current_frame[901:1100,901:1100] = 200
        else:
            self.current_frame = np.roll(self.current_frame, 10, axis=0)
            pass 
            # self.current_frame = np.random.randint(255,size=(768,1024),dtype=np.uint8)
        if self.new_image_callback_external is not None and self.callback_is_enabled:
            self.new_image_callback_external(self)

    def read_frame(self):
        return self.current_frame

    def _on_frame_callback(self, user_param, raw_image):
        pass

    def set_ROI(self, offset_x=None, offset_y=None, width=None, height=None):
        pass

    def set_line3_to_strobe(self):
        pass
