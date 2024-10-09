# set QT_API environment variable
import os 
import sys
import time
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import time
import numpy as np

from control._def import *

class NavigationController_PriorStage(QObject):

    xPos = Signal(float)
    yPos = Signal(float)
    zPos = Signal(float)
    thetaPos = Signal(float)
    xyPos = Signal(float,float)
    signal_joystick_button_pressed = Signal()

    def __init__(self,priorstage, microcontroller, objectivestore, parent=None):
        # parent should be set to OctopiGUI instance to enable updates
        # to camera settings, e.g. binning, that would affect click-to-move
        QObject.__init__(self)
        self.stage = priorstage
        self.microcontroller = microcontroller
        self.parent = parent
        self.objectiveStore = objectivestore
        self.x_pos_mm = 0
        self.y_pos_mm = 0

        # We are not using z and theta
        self.z_pos_mm = 0
        self.z_pos = 0
        self.mm_per_ustep_Z = 0.1
        self.theta_pos_rad = 0
        self.click_to_move = False
        self.z_microstepping = 1 
        self.theta_microstepping = 0.1

        # Joystick methods to be implemented
        self.enable_joystick_button_action = True

        # to be moved to gui for transparency
        self.stage.set_callback(self.update_pos)

        # scan start position
        self.scan_begin_position_x = 0
        self.scan_begin_position_y = 0

    def get_mm_per_ustep_X(self):
        return self.stage.steps_to_mm(1)

    def get_mm_per_ustep_Y(self):
        return self.stage.steps_to_mm(1)

    def get_mm_per_ustep_Z(self):
        return 0.1

    def set_flag_click_to_move(self, flag):
        self.click_to_move = flag

    def get_flag_click_to_move(self):
        return self.click_to_move

    def scan_preview_move_from_click(self, click_x, click_y, image_width, image_height, Nx=1, Ny=1, dx_mm=0.9, dy_mm=0.9):
        """
        napariTiledDisplay uses the Nx, Ny, dx_mm, dy_mm fields to move to the correct fov first
        imageArrayDisplayWindow assumes only a single fov (default values do not impact calculation but this is less correct)
        """
        # check if click to move enabled
        if not self.click_to_move:
            print("allow click to move")
            return
        # restore to raw coordicate
        click_x = image_width / 2.0 + click_x
        click_y = image_height / 2.0 - click_y
        print("click - (x, y):", (click_x, click_y))
        fov_col = click_x * Nx // image_width
        fov_row = click_y * Ny // image_height
        print("image - (col, row):", (fov_col, fov_row))
        end_position_x = Ny % 2 # right side or left side
        fov_col = Nx - (fov_col + 1) if end_position_x else fov_col
        fov_row = fov_row
        print("fov - (col, row):", fov_col, fov_row)

        pixel_sign_x = (-1)**end_position_x # inverted
        pixel_sign_y = -1 if INVERTED_OBJECTIVE else 1
        print("pixel_sign_x, pixel_sign_y", pixel_sign_x, pixel_sign_y)
 
        # move to selected fov
        self.move_to(self.scan_begin_position_x+dx_mm*fov_col*pixel_sign_x, 
            self.scan_begin_position_y+dy_mm*fov_row*pixel_sign_y)

        # move to actual click, offset from center fov
        tile_width = (image_width / Nx) * PRVIEW_DOWNSAMPLE_FACTOR
        tile_height = (image_height / Ny) * PRVIEW_DOWNSAMPLE_FACTOR
        offset_x = (click_x * PRVIEW_DOWNSAMPLE_FACTOR) % tile_width
        offset_y = (click_y * PRVIEW_DOWNSAMPLE_FACTOR) % tile_height
        offset_x_centered = int(offset_x - tile_width / 2)
        offset_y_centered = int(tile_height / 2 - offset_y)
        self.move_from_click(offset_x_centered, offset_y_centered, tile_width, tile_height)

    def move_from_click(self, click_x, click_y, image_width, image_height):
        if self.click_to_move:
            pixel_size_um = self.objectiveStore.pixel_size_um
            #pixel_binning_x, pixel_binning_y = self.get_pixel_binning()
            #pixel_size_x = pixel_size_um * pixel_binning_x
            #pixel_size_y = pixel_size_um * pixel_binning_y

            pixel_sign_x = 1
            pixel_sign_y = 1 if INVERTED_OBJECTIVE else -1

            #delta_x = pixel_sign_x * pixel_size_x * click_x / 1000.0
            #delta_y = pixel_sign_y * pixel_size_y * click_y / 1000.0
            delta_x = pixel_sign_x * pixel_size_um * click_x / 1000.0
            delta_y = pixel_sign_y * pixel_size_um * click_y / 1000.0

            if not IS_HCS:
                delta_x /= 2
                delta_y /= 2

            self.move_xy(delta_x, delta_y)

    def move_from_click_mosaic(self, x_mm, y_mm):
        if self.click_to_move:
            self.move_to(x_mm, y_mm)

    def get_pixel_binning(self):
        try:
            highest_res = max(self.parent.camera.res_list, key=lambda res: res[0] * res[1])
            resolution = self.parent.camera.resolution
            pixel_binning_x = max(1, highest_res[0] / resolution[0])
            pixel_binning_y = max(1, highest_res[1] / resolution[1])
        except AttributeError:
            pixel_binning_x = 1
            pixel_binning_y = 1
        return pixel_binning_x, pixel_binning_y

    def move_to_cached_position(self):
        if not os.path.isfile("cache/last_coords.txt"):
            return
        with open("cache/last_coords.txt","r") as f:
            for line in f:
                try:
                    x,y,z = line.strip("\n").strip().split(",")
                    x = float(x)
                    y = float(y)
                    z = float(z)
                    self.move_to(x,y)
                    self.move_z_to(z)
                    break
                except:
                    pass
                break

    def cache_current_position(self):
        with open("cache/last_coords.txt","w") as f:
            f.write(",".join([str(self.x_pos_mm),str(self.y_pos_mm),str(self.z_pos_mm)]))

    def move_x(self,delta):
        self.stage.move_relative_mm(delta, 0)

    def move_y(self,delta):
        self.stage.move_relative_mm(0, delta)

    def move_z(self,delta):
        pass

    def move_xy(self, x_mm, y_mm):
        self.stage.move_relative_mm(x_mm, y_mm)

    def move_x_to(self,delta):
        self.stage.move_absolute_x_mm(delta)

    def move_y_to(self,delta):
        self.stage.move_absolute_y_mm(delta)

    def move_z_to(self,delta):
        pass

    def move_to(self,x_mm,y_mm):
        self.stage.move_absolute_mm(x_mm, y_mm)

    def move_x_usteps(self,usteps):
        self.stage.move_relative(usteps, 0)

    def move_y_usteps(self,usteps):
        self.stage.move_relative(0, usteps)

    def move_z_usteps(self,usteps):
        pass

    def move_x_to_usteps(self,usteps):
        self.stage.move_absolute_x(usteps)

    def move_y_to_usteps(self,usteps):
        self.stage.move_absolute_y(usteps)

    def move_z_to_usteps(self,usteps):
        pass

    def update_pos(self,stage):
        # get position from the stage
        x_pos, y_pos, z_pos, theta_pos = stage.get_pos()

        self.x_pos_mm = stage.steps_to_mm(x_pos)
        self.y_pos_mm = stage.steps_to_mm(y_pos)

        # emit the updated position
        self.xPos.emit(self.x_pos_mm)
        self.yPos.emit(self.y_pos_mm)
        self.zPos.emit(self.z_pos_mm*1000)      # not in use
        self.thetaPos.emit(1)                   # not in use
        self.xyPos.emit(self.x_pos_mm,self.y_pos_mm)

        # Joystick button to be implemented
        if stage.signal_joystick_button_pressed_event:
            if self.enable_joystick_button_action:
                self.signal_joystick_button_pressed.emit()
            print('joystick button pressed')
            stage.signal_joystick_button_pressed_event = False

    def home_x(self):
        self.stage.home_x()

    def home_y(self):
        self.stage.home_y()

    def home_z(self):
        pass

    def home_theta(self):
        pass

    def home_xy(self):
        self.stage.home_xy()

    def zero_x(self):
        self.stage.zero_x()

    def zero_y(self):
        self.stage.zero_y()

    def zero_z(self):
        pass

    def zero_theta(self):
        pass

    def home(self):
        pass

    def set_x_limit_pos_mm(self,value_mm):
        pass

    def set_x_limit_neg_mm(self,value_mm):
        pass

    def set_y_limit_pos_mm(self,value_mm):
        pass

    def set_y_limit_neg_mm(self,value_mm):
        pass

    def set_z_limit_pos_mm(self,value_mm):
        pass

    def set_z_limit_neg_mm(self,value_mm):
        pass

    def configure_encoder(self, axis, transitions_per_revolution,flip_direction):
        pass

    def set_pid_control_enable(self, axis, enable_flag):
        pass

    def turnoff_axis_pid_control(self):
        pass

    def get_pid_control_flag(self, axis):
        return False

    def keep_scan_begin_position(self, x, y):
        self.scan_begin_position_x = x
        self.scan_begin_position_y = y

    def set_axis_PID_arguments(self, axis, pid_p, pid_i, pid_d):
        pass

    def set_piezo_um(self, z_piezo_um):
        dac = int(65535 * (z_piezo_um / OBJECTIVE_PIEZO_RANGE_UM))
        dac = 65535 - dac if OBJECTIVE_PIEZO_FLIP_DIR else dac
        self.microcontroller.analog_write_onboard_DAC(7, dac)