import argparse
import cv2
import time
import numpy as np
import threading
try:
    import seabreeze as sb
    import seabreeze.spectrometers
except:
    print('seabreeze import error')

# installation: $ pip3 install seabreeze
# installation: $ seabreeze_os_setup

from control._def import *

class Spectrometer(object):

    def __init__(self,sn=None):
        if sn == None:
            self.spectrometer = sb.spectrometers.Spectrometer.from_first_available()
        else:
            self.spectrometer = sb.spectrometers.Spectrometer.Spectrometer.from_serial_number(sn)

        self.new_data_callback_external = None

        self.streaming_started = False
        self.streaming_paused = False
        self.stop_streaming = False
        self.is_reading_spectrum = False

        self.thread_streaming = threading.Thread(target=self.stream, daemon=True)

    def set_integration_time_ms(self,integration_time_ms):
        self.spectrometer.integration_time_micros(int(1000*integration_time_ms))

    def read_spectrum(self,correct_dark_counts=False,correct_nonlinearity=False):
        self.is_reading_spectrum = True
        data = self.spectrometer.spectrum(correct_dark_counts,correct_nonlinearity)
        self.is_reading_spectrum = False
        return data

    def set_callback(self,function):
        self.new_data_callback_external = function

    def start_streaming(self):
        if self.streaming_started == False:
            self.streaming_started = True
            self.streaming_paused = False
            self.thread_streaming.start()
        else:
            self.streaming_paused = False

    def pause_streaming(self):
        self.streaming_paused = True

    def resume_streaming(self):
        self.streaming_paused = False

    def stream(self):
        while self.stop_streaming == False:
            if self.streaming_paused:
                time.sleep(0.05)
                continue
            # avoid conflict
            while self.is_reading_spectrum:
                time.sleep(0.05)
            if self.new_data_callback_external != None:
                self.new_data_callback_external(self.read_spectrum())

    def close(self):
        if self.streaming_started:
            self.stop_streaming = True
            self.thread_streaming.join()
        self.spectrometer.close()

class Spectrometer_Simulation(object):
    
    def __init__(self,sn=None):
        self.new_data_callback_external = None
        self.streaming_started = False
        self.stop_streaming = False
        self.streaming_paused = False
        self.is_reading_spectrum = False
        self.thread_streaming = threading.Thread(target=self.stream, daemon=True)

    def set_integration_time_us(self,integration_time_us):
        pass

    def read_spectrum(self,correct_dark_counts=False,correct_nonlinearity=False):
        N = 4096
        wavelength = np.linspace(400,1100,N)
        intensity = np.random.randint(0,65536,N)
        return np.stack((wavelength,intensity))
    
    def set_callback(self,function):
        self.new_data_callback_external = function

    def start_streaming(self):
        if self.streaming_started == False:
            self.streaming_started = True
            self.streaming_paused = False
            self.thread_streaming.start()
        else:
            self.streaming_paused = False

    def pause_streaming(self):
        self.streaming_paused = True

    def resume_streaming(self):
        self.streaming_paused = False

    def stream(self):
        while self.stop_streaming == False:
            if self.streaming_paused:
                time.sleep(0.05)
                continue
            # avoid conflict
            while self.is_reading_spectrum:
                time.sleep(0.05)
            if self.new_data_callback_external != None:
                print('read spectrum...')
                self.new_data_callback_external(self.read_spectrum())

    def close(self):
        if self.streaming_started:
            self.stop_streaming = True
            self.thread_streaming.join()