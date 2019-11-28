# library for daheng camera developed by Ethan Li

import argparse
import cv2
import time
from datetime import datetime

try:
    import gxipy as gx
except ImportError:
    print('Cannot use galaxy-based USB cameras!')


def roi_image(
    numpy_image, length_center_ratio=0.5, width_center_ratio=0.5,
    length_roi_ratio=1.0, width_roi_ratio=1.0
):
    image_length = numpy_image.shape[0]
    image_width = numpy_image.shape[1]
    roi_length_center = int(image_length * length_center_ratio)
    roi_width_center = int(image_width * width_center_ratio)
    roi_length_half = int(image_length * length_roi_ratio / 2)
    roi_width_half = int(image_width * width_roi_ratio / 2)
    roi_left = max(0, roi_length_center - roi_length_half)
    roi_right = min(image_length, roi_length_center + roi_length_half)
    roi_top = max(0, roi_width_center - roi_width_half)
    roi_bottom = min(image_width, roi_width_center + roi_width_half)

    return numpy_image[
        roi_left:roi_right, roi_top:roi_bottom
    ]


def resize_image(numpy_image, resize_factor=1.0, resize_interpolation=cv2.INTER_LINEAR):
    resized_length = int(numpy_image.shape[0] * resize_factor)
    resized_width = int(numpy_image.shape[1] * resize_factor)
    resized_dims = (resized_width, resized_length)
    return cv2.resize(
        numpy_image, resized_dims, interpolation=resize_interpolation
    )


class Camera(object):
    pass


class USBCamera(Camera):
    def __init__(self):
        self.device_manager = gx.DeviceManager()
        self.device_info_list = None
        self.device_index = 0
        self.camera = None
        self.is_color = None
        self.gamma_lut = None
        self.contrast_lut = None
        self.color_correction_param = None

        # Previews
        self.preview_length_center_ratio = 0.5
        self.preview_width_center_ratio = 0.5
        self.preview_length_roi_ratio = 1.0
        self.preview_width_roi_ratio = 1.0
        self.preview_resize_factor = 1.0

        # Caching
        self.last_raw_image = None
        self.last_converted_image = None
        self.last_numpy_image = None

    def connect(self, index=0):
        """Connect to a camera."""
        (device_num, self.device_info_list) = self.device_manager.update_device_list()
        if device_num == 0:
            raise RuntimeError('Could not find any USB camera devices!')
        self.device_index = index
        self.camera = self.device_manager.open_device_by_index(index + 1)
        self.is_color = self.camera.PixelColorFilter.is_implemented()
        self._update_image_improvement_params()

    def disconnect(self):
        """Disconnect from the camera."""
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

    def set_continuous_acquisition(self):
        self.camera.TriggerMode.set(gx.GxSwitchEntry.OFF)

    def set_triggered_acquisition(self):
        device_info = self.device_info_list[self.device_index]
        self.camera.TriggerMode.set(gx.GxSwitchEntry.ON)
        if device_info.get('device_class') != gx.GxDeviceClassList.USB2:
            self.camera.TriggerSource.set(gx.GxTriggerSourceEntry.SOFTWARE)
        self.camera.data_stream[self.device_index].flush_queue()

    def set_hardwareTriggered_acquisition(self):
        device_info = self.device_info_list[self.device_index]
        self.camera.TriggerMode.set(gx.GxSwitchEntry.ON)
        if device_info.get('device_class') != gx.GxDeviceClassList.USB2:
            self.camera.TriggerSource.set(gx.GxTriggerSourceEntry.LINE0)
        self.camera.data_stream[self.device_index].flush_queue()

    def set_exposure(self, exposure_time):
        self.camera.ExposureTime.set(exposure_time * 1000)

    def set_gain(self, gain):
        self.camera.Gain.set(gain)

    def _update_image_improvement_params(self):
        if not self.is_color:
            return

        if self.camera.GammaParam.is_readable():
            gamma_value = self.camera.GammaParam.get()
            self.gamma_lut = gx.Utility.get_gamma_lut(gamma_value)
        else:
            self.gamma_lut = None

        if self.camera.ContrastParam.is_readable():
            contrast_value = self.camera.ContrastParam.get()
            contrast_lut = gx.Utility.get_contrast_lut(contrast_value)
        else:
            self.contrast_lut = None

        if self.camera.ColorCorrectionParam.is_readable():
            self.color_correction_param = self.camera.ColorCorrectionParam.get()
        else:
            self.color_correction_param = 0

    def get_awb_ratios(self):
        self.camera.BalanceWhiteAuto.set(2)
        self.camera.BalanceRatioSelector.set(0)
        awb_r = self.camera.BalanceRatio.get()
        self.camera.BalanceRatioSelector.set(1)
        awb_g = self.camera.BalanceRatio.get()
        self.camera.BalanceRatioSelector.set(2)
        awb_b = self.camera.BalanceRatio.get()
        return (awb_r, awb_g, awb_b)

    def set_wb_ratios(self, wb_r=None, wb_g=None, wb_b=None):
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

    def start_streaming(self):
        self.camera.stream_on()

    def stop_streaming(self):
        self.camera.stream_off()

    def send_trigger(self):
        self.camera.TriggerSoftware.send_command()

    def get_next_image(self):
        raw_image = self.camera.data_stream[self.device_index].get_image()
        if raw_image is None:
            # raise RuntimeError('Failed to get image!')
            return self.last_raw_image
        self.last_raw_image = raw_image
        return raw_image

    def get_image_numpy(self):
        raw_image = self.camera.data_stream[self.device_index].get_image()
        numpy_image = raw_image.get_numpy_array()
        return numpy_image

    def process_image(self, raw_image):
        if self.is_color:
            converted_image = raw_image.convert('RGB')
        else:
            converted_image = raw_image
        if converted_image is None:
            raise RuntimeError('Failed to convert colors!')
        if self.is_color:
            converted_image.image_improvement(
                self.color_correction_param, self.contrast_lut, self.gamma_lut
            )

        numpy_image = converted_image.get_numpy_array()
        if numpy_image is None:
            raise RuntimeError('Image converts to null numpy array!')

        self.last_converted_image = converted_image
        self.last_numpy_image = numpy_image
        return (converted_image, numpy_image)

    def set_preview_center_ratios(self, length_ratio=None, width_ratio=None):
        if length_ratio is not None:
            self.preview_length_center_ratio = min(max(length_ratio, 0.0), 1.0)
        if width_ratio is not None:
            self.preview_width_center_ratio = min(max(width_ratio, 0.0), 1.0)

    def set_preview_roi_ratios(self, length_ratio=None, width_ratio=None):
        if length_ratio is not None:
            self.preview_length_roi_ratio = min(max(length_ratio, 0.0), 1.0)
        if width_ratio is not None:
            self.preview_width_roi_ratio = min(max(width_ratio, 0.0), 1.0)

    def set_preview_resize_factor(self, factor):
        self.preview_resize_factor = max(factor, 0.0)

    def get_preview(self, numpy_image, resize_interpolation=cv2.INTER_NEAREST):
        preview_image = roi_image(
            numpy_image,
            self.preview_length_center_ratio, self.preview_width_center_ratio,
            self.preview_length_roi_ratio, self.preview_width_roi_ratio
        )

        preview_image = resize_image(
            preview_image, self.preview_resize_factor, resize_interpolation
        )

        return preview_image

def show_preview(preview_image, window_name='Preview', poll_interval=10):
    if len(preview_image.shape) > 2:
        preview_image = cv2.cvtColor(preview_image, cv2.COLOR_RGB2BGR)

    cv2.imshow(window_name, preview_image)
    cv2.waitKey(poll_interval)


class Illumination():
    def __init__(
        self, name, pin, exposure_time, gain=0.0, wb_r=1.0, wb_g=1.0, wb_b=1.0
    ):
        self.name = name
        self.pin = pin
        self.isON = False
        self.exposure_time = exposure_time
        self.gain = gain
        self.wb_r = wb_r
        self.wb_g = wb_g
        self.wb_b = wb_b

    def get_wb_ratios(self):
        return {
            'wb_r': self.wb_r,
            'wb_g': self.wb_g,
            'wb_b': self.wb_b
        }


ILLUMINATIONS = {
    'bf': Illumination(
        'bf', 13, 50.0, wb_r=2.2265625, wb_g=1.0, wb_b=1.28515625  # exposure time and wb ratios are changed because the high-mag bf is using a damaged LED
    ),
    'fluor': Illumination(
        'fluor', 19, 400.0, gain=10.0, wb_r=2.21484375, wb_g=1.0, wb_b=1.390625
    )
}


def preview_once(cam):
    raw_image = cam.get_next_image()
    (converted_image, numpy_image) = cam.process_image(raw_image)
    preview_image = cam.get_preview(numpy_image)
    show_preview(preview_image)


def preview(cam, il=None):
    cam.set_continuous_acquisition()

    cam.start_streaming()
    try:
        while True:
            preview_once(cam)
    except KeyboardInterrupt:
        print('Quitting!')

def acquire_one(cam, il=None):
    cam.set_triggered_acquisition()
    cam.start_streaming()

    time.sleep(il.exposure_time * 1.5 / 1000)
    cam.send_trigger()
    raw_image = cam.get_next_image()
    (converted_image, numpy_image) = cam.process_image(raw_image)
    return numpy_image

def save_image(numpy_image, prefix, il=None):
    if len(numpy_image.shape) > 2:
        numpy_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

    if il is not None:
        filename = '{}_{}_{} ms exposure_{} gain.png'.format(
            prefix, il.name, il.exposure_time, il.gain
        )
    else:
        filename = '{}_{}.png'.format(
            prefix, datetime.now().strftime('%Y-%m-%d %H-%M-%S')
        )
    print('Saving as: {}'.format(filename))

    cv2.imwrite(filename, numpy_image, [cv2.IMWRITE_PNG_COMPRESSION, 3])

def capture(cam, prefix, il=None):
    numpy_image = acquire_one(cam, il=il)
    save_image(numpy_image, prefix, il=il)
    cam.set_continuous_acquisition()

def set_illumination(il, cam):
    cam.set_exposure(il.exposure_time)
    cam.set_gain(il.gain)
    cam.set_wb_ratios(**il.get_wb_ratios())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'mode', choices=['preview', 'capture'], help='Imaging mode.'
    )
    parser.add_argument(
        'illumination', choices=ILLUMINATIONS, help='Illumination mode.'
    )
    parser.add_argument(
        '--prefix', default='capture', help='Capture imaging mode filename prefix.'
    )
    args = parser.parse_args()

    for il in ILLUMINATIONS.values():
        il.connect()
    il = ILLUMINATIONS[args.illumination]

    cam = USBCamera()
    cam.connect()
    set_illumination(il, cam)
    cam.set_preview_roi_ratios(length_ratio=0.9, width_ratio=0.9)
    cam.set_preview_resize_factor(0.75)

    if args.mode == 'preview':
        preview(cam, il)
    elif args.mode == 'capture':
        capture(cam, args.prefix, il)

    cam.stop_streaming()
    cam.disconnect()

if __name__ == '__main__':
    main()
