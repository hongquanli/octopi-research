import tkinter as tk
import threading
import time
from time import sleep

# External packages

# from picamera import PiCamera
# import picamera.array
from scipy import misc
from scipy.ndimage.filters import laplace
import numpy
import numpy as np
from numpy import std
from numpy import square
from numpy import mean
# import matplotlib.pyplot as plt

# Local modules

import gpio
import imaging
import motion

class Application(tk.Frame):

    def __init__(self, master=None):
        super().__init__(master)
        #self.pack()
        self.grid()
        self.create_widgets()

        self.il = None


    ### illumination control ###
    def enable_led(self):
        self.btn_led.config(relief='sunken')
        imaging.ILLUMINATIONS['bf'].device.enable()

    def disable_led(self):
        self.btn_led.config(relief='raised')
        imaging.ILLUMINATIONS['bf'].device.disable()

    def toggle_led(self):
        if imaging.ILLUMINATIONS['bf'].device.state:
            self.disable_led()
        else:
            self.enable_led()

    def enable_laser(self):
        self.btn_laser.config(relief='sunken')
        imaging.ILLUMINATIONS['fluor'].device.enable()

    def disable_laser(self):
        self.btn_laser.config(relief='raised')
        imaging.ILLUMINATIONS['fluor'].device.disable()

    def toggle_laser(self):
        if imaging.ILLUMINATIONS['fluor'].device.state:
            self.disable_laser()
        else:
            self.enable_laser()

    def disable_bf(self):
        self.btn_bf.config(relief='raised')
        self.disable_led()
        self.il = None

    def disable_fluor(self):
        self.btn_fluor.config(relief='raised')
        self.disable_laser()
        self.il = None

    def toggle_bf(self,tog=[0]):
        tog[0] = not tog[0]
        if tog[0]:
            self.disable_fluor()
            self.var_exposure_time.set(self.var_exposure_time_bf.get())
            self.il = imaging.ILLUMINATIONS['bf']
            self.il.exposure_time = int(float(self.var_exposure_time_bf.get()))
            imaging.set_illumination(self.il, cam)
            self.btn_bf.config(relief='sunken')
            self.enable_led()
        else:
            self.disable_bf()

    def toggle_fluor(self,tog=[0]):
        tog[0] = not tog[0]
        if tog[0]:
            self.disable_bf()
            self.var_exposure_time.set(self.var_exposure_time_fluor.get())
            self.il = imaging.ILLUMINATIONS['fluor']
            self.il.exposure_time = int(float(self.var_exposure_time_bf.get()))
            imaging.set_illumination(self.il, cam)
            self.btn_fluor.config(relief='sunken')
            self.enable_laser()
        else:
            self.disable_fluor()

    def toggle_recording(self,tog=[0]):
        tog[0] = not tog[0]
        if tog[0]:
            self.btn_record.config(relief='sunken')
            # camera.resolution = '1920x1080'
            # camera.start_recording(self.entry_filename.get() + '_' + str(self.entry_ss.get()) + 'ms_' + str(self.scale_zoom.get()) + 'x.h264')
        else:
            self.btn_record.config(relief='raised')
            # camera.stop_recording()

    def x_move(self, direction):
        x_stepper.move(
            direction, int(self.entry_x_step.get()), float(self.entry_x_delay.get())
        )
        self.label_xPos.config(text=str(x_stepper.position))

    def y_move(self, direction):
        y_stepper.move(
            direction, int(self.entry_y_step.get()), float(self.entry_y_delay.get())
        )
        self.label_yPos.config(text=str(y_stepper.position))



    ### create widgets ###
    def create_widgets(self):

        # x #
        self.label_x = tk.Label(self,text='x')
        self.entry_x_step = tk.Entry(self,width = 5)
        self.entry_x_delay = tk.Entry(self,width = 5)
        self.entry_x_step.insert(0,"256")
        self.entry_x_delay.insert(0,"0.0002")
        self.btn_x_forward = tk.Button(
            self, text="Forward", command=lambda: self.x_move(1)
        )
        self.btn_x_backward = tk.Button(
            self, text="Backward", command=lambda: self.x_move(-1)
        )
        self.label_xPos = tk.Label(self,text='0')

        # y #
        self.label_y = tk.Label(self,text='y')
        self.entry_y_step = tk.Entry(self,width = 5)
        self.entry_y_delay = tk.Entry(self,width = 5)
        self.entry_y_step.insert(0,"256")
        self.entry_y_delay.insert(0,"0.0002")
        self.btn_y_forward = tk.Button(
            self, text="Forward", command=lambda: self.y_move(1)
        )
        self.btn_y_backward = tk.Button(
            self, text="Backward", command=lambda: self.y_move(-1)
        )
        self.label_yPos = tk.Label(self,text='0')

        # quit
        self.quit = tk.Button(
          self, text="QUIT", fg="red", command=root.destroy
        )
        self.label_x.grid(row=1,column=0)
        self.entry_x_step.grid(row=1,column=1)
        self.entry_x_delay.grid(row=1,column=2)
        self.btn_x_forward.grid(row=1,column=3)
        self.btn_x_backward.grid(row=1,column=4)
        self.label_xPos.grid(row=1,column=5)

        self.label_y.grid(row=2,column=0)
        self.entry_y_step.grid(row=2,column=1)
        self.entry_y_delay.grid(row=2,column=2)
        self.btn_y_forward.grid(row=2,column=3)
        self.btn_y_backward.grid(row=2,column=4)
        self.label_yPos.grid(row=2,column=5)

        # seperation
        self.label_seperator = tk.Label(self,text='  ')
        self.label_seperator.grid(row=4,column=0)

        # shutter speed
        self.label_ss = tk.Label(self,text='SS (ms)')
        self.var_exposure_time = tk.StringVar()
        self.var_exposure_time.trace(
            'w', lambda name, index, mode, exposure_time=self.var_exposure_time.get(): set_exposure_time(exposure_time)
        )
        self.entry_ss = tk.Entry(self,width = 6,textvariable=self.var_exposure_time)
        self.entry_ss.insert(0,imaging.ILLUMINATIONS['bf'].exposure_time)
        self.label_ss.grid(row=5,column=0,sticky=tk.W)
        self.entry_ss.grid(row=5,column=1,sticky=tk.W)

        # LED and laser
        self.btn_led = tk.Button(
            self, text="LED", fg="black", command=self.toggle_led
        )
        self.btn_laser = tk.Button(
            self, text="laser", fg="blue", command=self.toggle_laser
        )
        self.btn_led.grid(row=5,column=3)
        self.btn_laser.grid(row=5,column=4)

        # seperation
        self.label_seperator = tk.Label(self,text='  ')
        self.label_seperator.grid(row=6,column=0)

        # preset modes - bf
        self.label_ss_bf = tk.Label(self,text='SS (ms)')
        self.var_exposure_time_bf = tk.StringVar()
        self.entry_ss_bf = tk.Entry(self,width = 6,textvariable=self.var_exposure_time_bf)
        self.entry_ss_bf.insert(0,imaging.ILLUMINATIONS['bf'].exposure_time)
        self.btn_bf = tk.Button(
            self, text="Bright Field", fg="black", command=self.toggle_bf
        )
        self.label_ss_bf.grid(row=7,column=0,sticky=tk.W)
        self.entry_ss_bf.grid(row=7,column=1,sticky=tk.W)
        self.btn_bf.grid(row=7,column=3,columnspan=2)

        # preset modes - fluorescence
        self.label_ss_fluor = tk.Label(self,text='SS (ms)')
        self.var_exposure_time_fluor = tk.StringVar()
        self.entry_ss_fluor = tk.Entry(self,width = 6,textvariable=self.var_exposure_time_fluor)
        self.entry_ss_fluor.insert(0,imaging.ILLUMINATIONS['fluor'].exposure_time)
        self.btn_fluor = tk.Button(
            self, text="Fluorescence", fg="black", command=self.toggle_fluor
        )
        self.label_ss_fluor.grid(row=8,column=0,sticky=tk.W)
        self.entry_ss_fluor.grid(row=8,column=1,sticky=tk.W)
        self.btn_fluor.grid(row=8,column=3,columnspan=2)

        # seperation
        self.label_seperator = tk.Label(self,text='  ')
        self.label_seperator.grid(row=9,column=0)

        # zoom
        self.label_zoom = tk.Label(self,text='Preview Zoom')
        self.scale_zoom = tk.Scale(
            self,from_=1, to=8, resolution=0.1, orient=tk.HORIZONTAL, length=275,
            command=lambda value:set_zoom(float(value), float(self.scale_size.get()))
        )
        self.scale_zoom.set(1)
        self.label_zoom.grid(row=10,column=0,sticky=tk.W)
        self.scale_zoom.grid(row=10,column=1,columnspan=4,sticky=tk.W)

        self.label_size = tk.Label(self,text='Preview Size')
        self.scale_size = tk.Scale(
            self,from_=0.1, to=1, resolution=0.05, orient=tk.HORIZONTAL, length=275,
            command=lambda value:set_size(float(value), float(self.scale_zoom.get()))
        )
        self.scale_size.set(0.75)
        self.label_size.grid(row=11,column=0,sticky=tk.W)
        self.scale_size.grid(row=11,column=1,columnspan=4,sticky=tk.W)

        # pan
        self.label_pan_x = tk.Label(self,text='Preview Pan X')
        self.scale_pan_x = tk.Scale(
            self,from_=0.1, to=0.9, resolution=0.01, orient=tk.HORIZONTAL, length=275,
            command=lambda value:cam.set_preview_center_ratios(width_ratio=float(value))
        )
        self.scale_pan_x.set(0.5)
        self.label_pan_x.grid(row=12,column=0,sticky=tk.W)
        self.scale_pan_x.grid(row=12,column=1,columnspan=4,sticky=tk.W)
        self.label_pan_y = tk.Label(self,text='Preview Pan Y')
        self.scale_pan_y = tk.Scale(
            self,from_=0.1, to=0.9, resolution=0.01, orient=tk.HORIZONTAL, length=275,
            command=lambda value:cam.set_preview_center_ratios(length_ratio=float(value))
        )
        self.scale_pan_y.set(0.5)
        self.label_pan_y.grid(row=13,column=0,sticky=tk.W)
        self.scale_pan_y.grid(row=13,column=1,columnspan=4,sticky=tk.W)

        # fine focusing
        self.label_focus = tk.Label(self,text='Focus (PZT)')
        self.scale_focus = tk.Scale(
            self,from_=0, to = 4095, resolution=1, orient=tk.HORIZONTAL, length = 275,
            command=lambda value:piezo.set(int(value))
        )
        self.scale_focus.set(0)
        self.label_focus.grid(row=14,column=0,sticky=tk.W)
        self.scale_focus.grid(row=14,column=1,columnspan=4,sticky=tk.W)


        # seperation
        self.label_seperator = tk.Label(self,text='  ')
        self.label_seperator.grid(row=15,column=0)

        # autofocus
        self.label_N = tk.Label(self,text='N')
        self.entry_N = tk.Entry(self,width = 5)
        self.label_step = tk.Label(self,text='step')
        self.entry_step = tk.Entry(self,width = 5)
        self.btn_autoFocus = tk.Button(
            self, text="Autofocus", fg="black",
            command=lambda:autofocus(
                int(self.entry_N.get()), int(self.entry_step.get()), self.scale_focus
            )
        )
        self.entry_N.insert(0,'15')
        self.entry_step.insert(0,'16')
        self.label_N.grid(row=16,column=0,sticky=tk.W)
        self.entry_N.grid(row=16,column=1,sticky=tk.W)
        self.label_step.grid(row=16,column=2,sticky=tk.W)
        self.entry_step.grid(row=16,column=3,sticky=tk.W)
        self.btn_autoFocus.grid(row=16,column=4,sticky=tk.W)

        # seperation
        self.label_seperator = tk.Label(self,text='  ')
        self.label_seperator.grid(row=17,column=0)

        # filename
        self.label_filename = tk.Label(self,text='Prefix')
        self.entry_filename = tk.Entry(self,width = 31)

        self.label_filename.grid(row=18,column=0,sticky=tk.W)
        self.entry_filename.grid(row=18,column=1,columnspan=4,sticky=tk.W)

        # capture
        self.btn_capture = tk.Button(
            self, text="Capture", fg="black", bg = "yellow", width = 32, height = 2,
            command=lambda: capture(self.entry_filename.get(), il=self.il)
        )
        self.btn_capture.grid(row=19,column=0,columnspan=5,rowspan=2)
        # record
        # self.btn_record = tk.Button(
        #     self, text="Record", fg="black", bg = "yellow", width = 32, height = 2,
        #     command=self.toggle_recording
        # )
        # self.btn_record.grid(row=20,column=0,columnspan=5,rowspan=2)


# camera control

def set_zoom(zoom, size):
    cam.set_preview_roi_ratios(
        length_ratio=float(1 / zoom), width_ratio=float(1 / zoom)
    )
    cam.set_preview_resize_factor(float(size) * zoom)

def set_size(size, zoom):
    cam.set_preview_resize_factor(float(size) * float(zoom))

def set_exposure_time(exposure_time):
    if exposure_time == '':
        return

    cam.set_exposure(int(float(exposure_time)))

def capture(prefix, il):
    imaging.save_image(cam.last_numpy_image, prefix, il=il)

def autofocus(N,step,scale_focus):
    FM = [0]*N
    use_video_port = True
    splitter_port=0
    resize=None
    dt = 0.003
    FM_max = 0
    j = 0

    DACcode = scale_focus.get()

    # start_time = time.time()
    prefix = 'Z autofocus, 1080p'

    timestamp = time.time()
    # camera.resolution = '1920x1080'
    for i in range(N):
        j = j + 1
        # actuate
        # z_move('f',step,0.001)
        DACcode = DACcode + step
        scale_focus.set(DACcode)

        app.update()
        sleep(1)
        img = cam.last_numpy_image
        ROI = img[:,:,1]
        lap = laplace(ROI)
        fm = mean(square(lap))
        print(i, DACcode, fm)
        FM[i] = fm
        FM_max = max(fm,FM_max)
        if fm < FM_max*0.85:
            break

    print('time:')
    print(time.time()-timestamp)
    idx = FM.index(max(FM))
    print(idx)
    # plt.plot(FM)

    DACcode = DACcode - step*j
    scale_focus.set(DACcode)

    DACcode = DACcode + step*(idx+1)
    scale_focus.set(DACcode)

    #z_move('b',step*j,dt)
    #z_move('f',step*(idx+1),dt)
    #object.z_pos = object.z_pos + step*(idx+1)
    #object.label_zPos.config(text = str(object.z_pos))

    # camera.resolution = '3280x2464'
    imaging.ILLUMINATIONS['bf'].device.enable()


class ThreadedPreview():
    def __init__(self, cam):
        self.thread = None
        self.cam = cam
        self.active = False

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Thread needs to be stopped first!')

        self.thread = threading.Thread(target=self.run, name='CameraPreview')
        self.active = True
        self.thread.start()

    def run(self):
        cam.start_streaming()
        try:
            while self.active:
                imaging.preview_once(cam)
        except KeyboardInterrupt:
            print('Quitting!')


    def stop(self):
        self.active = False
        self.thread.join()
        self.thread = None
        cam.stop_streaming()
#======================================================================#
#======================================================================#
#======================================================================#

# init.
gpio.connect()

x_stepper = motion.Stepper(17, 27, 22)
x_stepper.connect()
y_stepper = motion.Stepper(10, 9, 11)
y_stepper.connect()

bus = gpio.I2CBus()
bus.connect()
piezo = motion.Piezo(bus)

for il in imaging.ILLUMINATIONS.values():
    il.device.connect()

# set up camera
cam = imaging.USBCamera()
cam.connect()
cam.set_preview_roi_ratios(length_ratio=0.9, width_ratio=0.9)
cam.set_preview_resize_factor(0.75)
# camera = PiCamera(resolution='3280x2464',sensor_mode=2,framerate=15)
# camera = PiCamera(resolution='1920x1080',sensor_mode=2,framerate=15)
# camera = PiCamera(resolution='1920x1080',sensor_mode=1,framerate = 30)
# camera.iso = 60
# camera.exposure_mode = 'off'
# camera.shutter_speed = 500
# camera.awb_mode = 'off'
# camera.awb_gains = (2,1)
# camera.start_preview(resolution=(1920, 1080),fullscreen=False, window=(200, 0, 1080, 1080))
cam.set_continuous_acquisition()

# create GUI
root = tk.Tk()
app = Application(master=root)
app.toggle_bf()
preview = ThreadedPreview(cam)
preview.start()
app.mainloop()

# exit routine
# camera.stop_preview()
preview.stop()
for il in imaging.ILLUMINATIONS.values():
    il.device.disable()
cam.disconnect()
gpio.disconnect()
