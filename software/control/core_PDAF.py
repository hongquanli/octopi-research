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
import control.tracking as tracking

from queue import Queue
from threading import Thread, Lock
import time
import numpy as np
import pyqtgraph as pg
import cv2
from datetime import datetime


class PDAFController(QObject):

    def __init__(self):
        QObject.__init__(self)
        self.image1_received = False
        self.image2_received = False

    def register_image_from_camera_1(self,image):
        self.image1 = image
        self.image1_received = True
        if(self.image2_received):
            self.compute_defocus()

    def register_image_from_camera_2(self,image):
        self.image2 = image
        self.image2_received = True

    def compute_defocus(self):
        print('computing defocus')
        I1 = np.array(self.image1,dtype=np.int)
        I2 = np.array(self.image2,dtype=np.int)
        I1 = I1 - np.mean(I1)
        I2 = I2 - np.mean(I2)

        xcorr = cv2.filter2D(I1,cv2.CV_32F,I2)
        # cv2.imshow('xcorr',np.array(255*xcorr/np.max(xcorr), dtype = np.uint8 ))
        # cv2.imshow('xcorr',self.image2)
        cv2.imshow('xcorr',np.array(255*xcorr/np.max(xcorr),dtype=np.uint8))
        print(np.max(xcorr))
        cv2.waitKey(15)  
        pass


    def close(self):
        pass