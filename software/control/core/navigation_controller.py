# qt libraries
from qtpy.QtCore import QObject, Signal # type: ignore
from qtpy.QtWidgets import QFrame, QVBoxLayout

from control._def import *

import numpy as np
import pyqtgraph as pg
import cv2

import math

from typing import Optional, List, Union, Tuple

import control.microcontroller as microcontroller

class NavigationController(QObject):

    xPos = Signal(float)
    yPos = Signal(float)
    zPos = Signal(float)
    thetaPos = Signal(float)
    xyPos = Signal(float,float)
    signal_joystick_button_pressed = Signal()

    def __init__(self,microcontroller:microcontroller.Microcontroller):
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.x_pos_mm = 0
        self.y_pos_mm = 0
        self.z_pos_mm = 0
        self.z_pos = 0
        self.theta_pos_rad = 0
        self.x_microstepping = MACHINE_CONFIG.MICROSTEPPING_DEFAULT_X
        self.y_microstepping = MACHINE_CONFIG.MICROSTEPPING_DEFAULT_Y
        self.z_microstepping = MACHINE_CONFIG.MICROSTEPPING_DEFAULT_Z
        self.theta_microstepping = MACHINE_CONFIG.MICROSTEPPING_DEFAULT_THETA
        self.enable_joystick_button_action:bool = True

        # to be moved to gui for transparency
        self.microcontroller.set_callback(self.update_pos)

        # self.timer_read_pos = QTimer()
        # self.timer_read_pos.setInterval(PosUpdate.INTERVAL_MS)
        # self.timer_read_pos.timeout.connect(self.update_pos)
        # self.timer_read_pos.start()

    def move_x(self,delta):
        self.microcontroller.move_x_usteps(int(delta/(MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X))))

    def move_y(self,delta):
        self.microcontroller.move_y_usteps(int(delta/(MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y))))

    def move_z(self,delta):
        self.microcontroller.move_z_usteps(int(delta/(MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z))))

    def move_x_to(self,delta):
        self.microcontroller.move_x_to_usteps(int(delta/(MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X))))

    def move_y_to(self,delta):
        self.microcontroller.move_y_to_usteps(int(delta/(MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y))))

    def move_z_to(self,delta):
        self.microcontroller.move_z_to_usteps(int(delta/(MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z))))

    def move_x_usteps(self,usteps):
        self.microcontroller.move_x_usteps(usteps)

    def move_y_usteps(self,usteps):
        self.microcontroller.move_y_usteps(usteps)

    def move_z_usteps(self,usteps):
        self.microcontroller.move_z_usteps(usteps)

    def update_pos(self,microcontroller):
        # get position from the microcontroller
        x_pos, y_pos, z_pos, theta_pos = microcontroller.get_pos()
        self.z_pos = z_pos
        
        # calculate position in mm or rad
        if MACHINE_CONFIG.USE_ENCODER_X:
            self.x_pos_mm = x_pos*MACHINE_CONFIG.ENCODER_POS_SIGN_X*MACHINE_CONFIG.ENCODER_STEP_SIZE_X_MM
        else:
            self.x_pos_mm = x_pos*MACHINE_CONFIG.STAGE_POS_SIGN_X*(MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X))

        if MACHINE_CONFIG.USE_ENCODER_Y:
            self.y_pos_mm = y_pos*MACHINE_CONFIG.ENCODER_POS_SIGN_Y*MACHINE_CONFIG.ENCODER_STEP_SIZE_Y_MM
        else:
            self.y_pos_mm = y_pos*MACHINE_CONFIG.STAGE_POS_SIGN_Y*(MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y))

        if MACHINE_CONFIG.USE_ENCODER_Z:
            self.z_pos_mm = z_pos*MACHINE_CONFIG.ENCODER_POS_SIGN_Z*MACHINE_CONFIG.ENCODER_STEP_SIZE_Z_MM
        else:
            self.z_pos_mm = z_pos*MACHINE_CONFIG.STAGE_POS_SIGN_Z*(MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z))

        if MACHINE_CONFIG.USE_ENCODER_THETA:
            self.theta_pos_rad = theta_pos*MACHINE_CONFIG.ENCODER_POS_SIGN_THETA*MACHINE_CONFIG.ENCODER_STEP_SIZE_THETA
        else:
            self.theta_pos_rad = theta_pos*MACHINE_CONFIG.STAGE_POS_SIGN_THETA*(2*math.pi/(self.theta_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_THETA))
        # emit the updated position
        self.xPos.emit(self.x_pos_mm)
        self.yPos.emit(self.y_pos_mm)
        self.zPos.emit(self.z_pos_mm*1000)
        self.thetaPos.emit(self.theta_pos_rad*360/(2*math.pi))
        self.xyPos.emit(self.x_pos_mm,self.y_pos_mm)

        if microcontroller.signal_joystick_button_pressed_event:
            if self.enable_joystick_button_action:
                self.signal_joystick_button_pressed.emit()
            print('joystick button pressed')
            microcontroller.signal_joystick_button_pressed_event = False

    def home_x(self):
        self.microcontroller.home_x()

    def home_y(self):
        self.microcontroller.home_y()

    def home_z(self):
        self.microcontroller.home_z()

    def home_theta(self):
        self.microcontroller.home_theta()

    def home_xy(self):
        self.microcontroller.home_xy()

    def zero_x(self):
        self.microcontroller.zero_x()

    def zero_y(self):
        self.microcontroller.zero_y()

    def zero_z(self):
        self.microcontroller.zero_z()

    def zero_theta(self):
        self.microcontroller.zero_theta()

    def home(self):
        pass

    def set_x_limit_pos_mm(self,value_mm):
        if MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X > 0:
            self.microcontroller.set_lim(LIMIT_CODE.X_POSITIVE,int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.X_NEGATIVE,MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X*int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X))))

    def set_x_limit_neg_mm(self,value_mm):
        if MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X > 0:
            self.microcontroller.set_lim(LIMIT_CODE.X_NEGATIVE,int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.X_POSITIVE,MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_X*int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X))))

    def set_y_limit_pos_mm(self,value_mm):
        if MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Y_POSITIVE,int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Y_NEGATIVE,MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y*int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y))))

    def set_y_limit_neg_mm(self,value_mm):
        if MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Y_NEGATIVE,int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Y_POSITIVE,MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Y*int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y))))

    def set_z_limit_pos_mm(self,value_mm):
        if MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Z > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Z_POSITIVE,int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Z_NEGATIVE,MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Z*int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z))))

    def set_z_limit_neg_mm(self,value_mm):
        if MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Z > 0:
            self.microcontroller.set_lim(LIMIT_CODE.Z_NEGATIVE,int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z))))
        else:
            self.microcontroller.set_lim(LIMIT_CODE.Z_POSITIVE,MACHINE_CONFIG.STAGE_MOVEMENT_SIGN_Z*int(value_mm/(MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z))))
    
    def move_to(self,x_mm,y_mm):
        self.move_x_to(x_mm)
        self.move_y_to(y_mm)

class NavigationViewer(QFrame):

    def __init__(self, sample = 'glass slide', invertX = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setBackground("w")
        self.graphics_widget.view = self.graphics_widget.addViewBox(invertX=invertX,invertY=True)
        ## lock the aspect ratio so pixels are always square
        self.graphics_widget.view.setAspectLocked(True)
        ## Create image item
        self.graphics_widget.img = pg.ImageItem(border='w')
        self.graphics_widget.view.addItem(self.graphics_widget.img)

        self.grid = QVBoxLayout()
        self.grid.addWidget(self.graphics_widget)
        self.setLayout(self.grid)
 
        self.last_fov_drawn=None
        self.set_wellplate_type(sample)
 
        self.location_update_threshold_mm = 0.4    
 
        self.box_color = (255, 0, 0)
        self.box_line_thickness = 2
 
        self.x_mm = None
        self.y_mm = None
 
        self.update_display()
 
    def set_wellplate_type(self,wellplate_type:str):
        wellplate_type_image={
            'glass slide'    : 'images/slide carrier_828x662.png',
            '384 well plate' : 'images/384 well plate_1509x1010.png',
            '96 well plate'  : 'images/96 well plate_1509x1010.png',
            '24 well plate'  : 'images/24 well plate_1509x1010.png',
            '12 well plate'  : 'images/12 well plate_1509x1010.png',
            '6 well plate'   : 'images/6 well plate_1509x1010.png'
        }
        assert wellplate_type in wellplate_type_image, f"{wellplate_type} is not a valid plate type"
 
        self.background_image=cv2.imread(wellplate_type_image[wellplate_type])
 
        self.current_image = np.copy(self.background_image)
        self.current_image_display = np.copy(self.background_image)
        self.image_height = self.background_image.shape[0]
        self.image_width = self.background_image.shape[1]
 
        self.sample = wellplate_type
 
        if wellplate_type == 'glass slide':
            self.origin_bottom_left_x = 200
            self.origin_bottom_left_y = 120
            self.mm_per_pixel = 0.1453
            self.fov_size_mm = 3000*1.85/(50/9)/1000
        else:
            self.location_update_threshold_mm = 0.05
            self.mm_per_pixel = 0.084665
            self.fov_size_mm = 3000*1.85/(50/10)/1000
            self.origin_bottom_left_x = MACHINE_CONFIG.X_ORIGIN_384_WELLPLATE_PIXEL - (MACHINE_CONFIG.X_MM_384_WELLPLATE_UPPERLEFT)/self.mm_per_pixel
            self.origin_bottom_left_y = MACHINE_CONFIG.Y_ORIGIN_384_WELLPLATE_PIXEL - (MACHINE_CONFIG.Y_MM_384_WELLPLATE_UPPERLEFT)/self.mm_per_pixel
 
        self.clear_imaged_positions()
 
    def update_current_location(self,x_mm,y_mm):
        if self.x_mm != None and self.y_mm != None:
            # update only when the displacement has exceeded certain value
            if abs(x_mm - self.x_mm) > self.location_update_threshold_mm or abs(y_mm - self.y_mm) > self.location_update_threshold_mm:
                self.draw_current_fov(x_mm,y_mm)
                self.update_display()
                self.x_mm = x_mm
                self.y_mm = y_mm
        else:
            self.draw_current_fov(x_mm,y_mm)
            self.update_display()
            self.x_mm = x_mm
            self.y_mm = y_mm

    def draw_current_fov(self,x_mm,y_mm):
        self.current_image_display = np.copy(self.current_image)
        if self.sample == 'glass slide':
            current_FOV_top_left = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        else:
            current_FOV_top_left = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        cv2.rectangle(self.current_image_display, current_FOV_top_left, current_FOV_bottom_right, self.box_color, self.box_line_thickness)

        self.last_fov_drawn=(x_mm,y_mm)

    def clear_imaged_positions(self):
        self.current_image = np.copy(self.background_image)
        if not self.last_fov_drawn is None:
            self.draw_current_fov(self.last_fov_drawn[0],self.last_fov_drawn[1])
        self.update_display()

    def update_display(self):
        self.graphics_widget.img.setImage(self.current_image_display,autoLevels=False)

    def clear_slide(self):
        self.current_image = np.copy(self.background_image)
        self.current_image_display = np.copy(self.background_image)
        self.update_display()

    def register_fov(self,x_mm,y_mm):
        color = (0,0,255)
        if self.sample == 'glass slide':
            current_FOV_top_left = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        else:
            current_FOV_top_left = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel))
            current_FOV_bottom_right = (round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel),
                                    round((self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel))
        cv2.rectangle(self.current_image, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)
