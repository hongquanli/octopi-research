# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import control.utils as utils
from control._def import *

import time
import numpy as np
import cv2

class DisplacementMeasurementController(QObject):

    signal_readings = Signal(list)
    signal_plots = Signal(np.ndarray,np.ndarray)

    def __init__(self, x_offset = 0, y_offset = 0, x_scaling = 1, y_scaling = 1, N_average=1, N=10000):

        QObject.__init__(self)
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.x_scaling = x_scaling
        self.y_scaling = y_scaling
        self.N_average = N_average
        self.N = N # length of array to emit
        self.t_array = np.array([])
        self.x_array = np.array([])
        self.y_array = np.array([])

    def update_measurement(self,image):

        t = time.time()

        if len(image.shape)==3:
            image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)

        h,w = image.shape
        x,y = np.meshgrid(range(w),range(h))
        I = image.astype(float)
        I = I - np.amin(I)
        I[I/np.amax(I)<0.2] = 0
        x = np.sum(x*I)/np.sum(I)
        y = np.sum(y*I)/np.sum(I)
        
        x = x - self.x_offset
        y = y - self.y_offset
        x = x*self.x_scaling
        y = y*self.y_scaling

        self.t_array = np.append(self.t_array,t)
        self.x_array = np.append(self.x_array,x)
        self.y_array = np.append(self.y_array,y)

        self.signal_plots.emit(self.t_array[-self.N:], np.vstack((self.x_array[-self.N:],self.y_array[-self.N:])))
        self.signal_readings.emit([np.mean(self.x_array[-self.N_average:]),np.mean(self.y_array[-self.N_average:])])

    def update_settings(self,x_offset,y_offset,x_scaling,y_scaling,N_average,N):
        self.N = N
        self.N_average = N_average
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.x_scaling = x_scaling
        self.y_scaling = y_scaling