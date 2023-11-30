import control.toupcam as toupcam
from control.camera_toupcam import Camera
from control._def import *
import time

camera = Camera(resolution=(6224,4168), rotate_image_angle = ROTATE_IMAGE_ANGLE, flip_image=FLIP_IMAGE)

camera.open()

camera.set_gain_mode('HCG')

camera.set_continuous_acquisition()

print(camera.get_awb_ratios())

camera.start_streaming()

time.sleep(1.0)

print(camera.get_awb_ratios())

camera.close()
