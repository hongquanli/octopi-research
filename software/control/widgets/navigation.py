# qt libraries
from qtpy.QtWidgets import QFrame, QLabel, QDoubleSpinBox, QPushButton, QGridLayout, QMessageBox, QVBoxLayout

from control._def import *

from typing import Optional, Union, List, Tuple

from control.core import SlidePositionController

class NavigationWidget(QFrame):
    def __init__(self, navigationController, slidePositionController:Optional[SlidePositionController]=None, widget_configuration:str = 'full', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigationController = navigationController
        self.slidePositionController = slidePositionController
        self.widget_configuration = widget_configuration
        self.slide_position = None
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.label_Xpos = QLabel()
        self.label_Xpos.setNum(0)
        self.label_Xpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dX = QDoubleSpinBox()
        self.entry_dX.setMinimum(0) 
        self.entry_dX.setMaximum(25) 
        self.entry_dX.setSingleStep(0.2)
        self.entry_dX.setValue(0)
        self.entry_dX.setDecimals(3)
        self.entry_dX.setKeyboardTracking(False)
        self.btn_moveX_forward = QPushButton('Forward')
        self.btn_moveX_forward.setDefault(False)
        self.btn_moveX_backward = QPushButton('Backward')
        self.btn_moveX_backward.setDefault(False)

        self.btn_home_X = QPushButton('Home X')
        self.btn_home_X.setDefault(False)
        self.btn_home_X.setEnabled(MACHINE_CONFIG.HOMING_ENABLED_X)
        self.btn_zero_X = QPushButton('Zero X')
        self.btn_zero_X.setDefault(False)
        
        self.label_Ypos = QLabel()
        self.label_Ypos.setNum(0)
        self.label_Ypos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dY = QDoubleSpinBox()
        self.entry_dY.setMinimum(0)
        self.entry_dY.setMaximum(25)
        self.entry_dY.setSingleStep(0.2)
        self.entry_dY.setValue(0)
        self.entry_dY.setDecimals(3)
        self.entry_dY.setKeyboardTracking(False)
        self.btn_moveY_forward = QPushButton('Forward')
        self.btn_moveY_forward.setDefault(False)
        self.btn_moveY_backward = QPushButton('Backward')
        self.btn_moveY_backward.setDefault(False)

        self.btn_home_Y = QPushButton('Home Y')
        self.btn_home_Y.setDefault(False)
        self.btn_home_Y.setEnabled(MACHINE_CONFIG.HOMING_ENABLED_Y)
        self.btn_zero_Y = QPushButton('Zero Y')
        self.btn_zero_Y.setDefault(False)

        self.label_Zpos = QLabel()
        self.label_Zpos.setNum(0)
        self.label_Zpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dZ = QDoubleSpinBox()
        self.entry_dZ.setMinimum(0) 
        self.entry_dZ.setMaximum(1000) 
        self.entry_dZ.setSingleStep(0.2)
        self.entry_dZ.setValue(0)
        self.entry_dZ.setDecimals(3)
        self.entry_dZ.setKeyboardTracking(False)
        self.btn_moveZ_forward = QPushButton('Forward')
        self.btn_moveZ_forward.setDefault(False)
        self.btn_moveZ_backward = QPushButton('Backward')
        self.btn_moveZ_backward.setDefault(False)

        self.btn_home_Z = QPushButton('Home Z')
        self.btn_home_Z.setDefault(False)
        self.btn_home_Z.setEnabled(MACHINE_CONFIG.HOMING_ENABLED_Z)
        self.btn_zero_Z = QPushButton('Zero Z')
        self.btn_zero_Z.setDefault(False)

        self.btn_load_slide = QPushButton('To Slide Loading Position')
        
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('X (mm)'), 0,0)
        grid_line0.addWidget(self.label_Xpos, 0,1)
        grid_line0.addWidget(self.entry_dX, 0,2)
        grid_line0.addWidget(self.btn_moveX_forward, 0,3)
        grid_line0.addWidget(self.btn_moveX_backward, 0,4)
        
        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Y (mm)'), 0,0)
        grid_line1.addWidget(self.label_Ypos, 0,1)
        grid_line1.addWidget(self.entry_dY, 0,2)
        grid_line1.addWidget(self.btn_moveY_forward, 0,3)
        grid_line1.addWidget(self.btn_moveY_backward, 0,4)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Z (um)'), 0,0)
        grid_line2.addWidget(self.label_Zpos, 0,1)
        grid_line2.addWidget(self.entry_dZ, 0,2)
        grid_line2.addWidget(self.btn_moveZ_forward, 0,3)
        grid_line2.addWidget(self.btn_moveZ_backward, 0,4)
        
        grid_line3 = QGridLayout()
        if self.widget_configuration == 'full':
            grid_line3.addWidget(self.btn_zero_X, 0,3)
            grid_line3.addWidget(self.btn_zero_Y, 0,4)
            grid_line3.addWidget(self.btn_zero_Z, 0,5)
            grid_line3.addWidget(self.btn_home_X, 0,0)
            grid_line3.addWidget(self.btn_home_Y, 0,1)
            grid_line3.addWidget(self.btn_home_Z, 0,2)
        elif self.widget_configuration == 'malaria':
            grid_line3.addWidget(self.btn_load_slide, 0,0,1,2)
            grid_line3.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3.addWidget(self.btn_zero_Z, 0,3,1,1)
        elif self.widget_configuration == WELLPLATE_NAMES[384]:
            grid_line3.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3.addWidget(self.btn_zero_Z, 0,3,1,1)
        elif self.widget_configuration == WELLPLATE_NAMES[96]:
            grid_line3.addWidget(self.btn_home_Z, 0,2,1,1)
            grid_line3.addWidget(self.btn_zero_Z, 0,3,1,1)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        self.grid.addLayout(grid_line3,3,0)
        self.setLayout(self.grid)

        self.entry_dX.valueChanged.connect(self.set_deltaX)
        self.entry_dY.valueChanged.connect(self.set_deltaY)
        self.entry_dZ.valueChanged.connect(self.set_deltaZ)

        self.btn_moveX_forward.clicked.connect(self.move_x_forward)
        self.btn_moveX_backward.clicked.connect(self.move_x_backward)
        self.btn_moveY_forward.clicked.connect(self.move_y_forward)
        self.btn_moveY_backward.clicked.connect(self.move_y_backward)
        self.btn_moveZ_forward.clicked.connect(self.move_z_forward)
        self.btn_moveZ_backward.clicked.connect(self.move_z_backward)

        self.btn_home_X.clicked.connect(self.home_x)
        self.btn_home_Y.clicked.connect(self.home_y)
        self.btn_home_Z.clicked.connect(self.home_z)
        self.btn_zero_X.clicked.connect(self.zero_x)
        self.btn_zero_Y.clicked.connect(self.zero_y)
        self.btn_zero_Z.clicked.connect(self.zero_z)

        self.btn_load_slide.clicked.connect(self.switch_position)
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF");
        
    def move_x_forward(self):
        self.navigationController.move_x(self.entry_dX.value())
    def move_x_backward(self):
        self.navigationController.move_x(-self.entry_dX.value())
    def move_y_forward(self):
        self.navigationController.move_y(self.entry_dY.value())
    def move_y_backward(self):
        self.navigationController.move_y(-self.entry_dY.value())
    def move_z_forward(self):
        self.navigationController.move_z(self.entry_dZ.value()/1000)
    def move_z_backward(self):
        self.navigationController.move_z(-self.entry_dZ.value()/1000) 

    def set_deltaX(self,value):
        mm_per_ustep = MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.navigationController.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X) # to implement a get_x_microstepping() in multipointController
        deltaX = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_dX.setValue(deltaX)
    def set_deltaY(self,value):
        mm_per_ustep = MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.navigationController.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y)
        deltaY = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_dY.setValue(deltaY)
    def set_deltaZ(self,value):
        mm_per_ustep = MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_dZ.setValue(deltaZ)

    def home_x(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel) # type: ignore
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.home_x()

    def home_y(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel) # type: ignore
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.home_y()

    def home_z(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run homing")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel) # type: ignore
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.navigationController.home_z()

    def zero_x(self):
        self.navigationController.zero_x()

    def zero_y(self):
        self.navigationController.zero_y()

    def zero_z(self):
        self.navigationController.zero_z()

    def slot_slide_loading_position_reached(self):
        self.slide_position = 'loading'
        self.btn_load_slide.setStyleSheet("background-color: #C2FFC2");
        self.btn_load_slide.setText('To Slide Scanning Position')
        self.btn_moveX_forward.setEnabled(False)
        self.btn_moveX_backward.setEnabled(False)
        self.btn_moveY_forward.setEnabled(False)
        self.btn_moveY_backward.setEnabled(False)
        self.btn_moveZ_forward.setEnabled(False)
        self.btn_moveZ_backward.setEnabled(False)

    def slot_slide_scanning_position_reached(self):
        self.slide_position = 'scanning'
        self.btn_load_slide.setStyleSheet("background-color: #C2C2FF");
        self.btn_load_slide.setText('To Slide Loading Position')
        self.btn_moveX_forward.setEnabled(True)
        self.btn_moveX_backward.setEnabled(True)
        self.btn_moveY_forward.setEnabled(True)
        self.btn_moveY_backward.setEnabled(True)
        self.btn_moveZ_forward.setEnabled(True)
        self.btn_moveZ_backward.setEnabled(True)

    def switch_position(self):
        assert not self.slidePositionController is None
        if self.slide_position != 'loading':
            self.slidePositionController.move_to_slide_loading_position()
        else:
            self.slidePositionController.move_to_slide_scanning_position()

import pyqtgraph as pg
import numpy as np
import cv2
from enum import Enum

class Color(tuple,Enum):
    LIGHT_BLUE=(0xAD,0xD8,0xE6)
    RED=(255,0,0)
    LIGHT_GREY=(160,)*3


class NavigationViewer(QFrame):

    def __init__(self, sample:str = 'glass slide', invertX:bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setBackground("w")
        ## lock the aspect ratio so pixels are always square
        self.graphics_widget.view = self.graphics_widget.addViewBox(invertX=invertX,invertY=True,lockAspect=True)
        ## Create image item
        self.graphics_widget.img = pg.ImageItem(border='w')
        self.graphics_widget.view.addItem(self.graphics_widget.img)
        # make sure plate view is always visible, from view.getState()['viewRange']:
        max_state=[[-70.74301114861895, 1579.743011148619], [-254.9490586181788, 1264.9490586181787]]
        min_state=[[733.5075292478979, 886.8248563569729], [484.2505774030056, 639.926632621451]]
        ((max_lowerx,max_upperx),(max_lowery,max_uppery))=max_state
        ((min_lowerx,min_upperx),(min_lowery,min_uppery))=min_state
        self.graphics_widget.view.setLimits(            
            xMin=max_lowerx,
            xMax=max_upperx,
            yMin=max_lowery,
            yMax=max_uppery,

            minXRange=min_upperx-min_lowerx,
            maxXRange=max_upperx-max_lowerx,
            minYRange=min_uppery-min_lowery,
            maxYRange=max_uppery-max_lowery,
        )

        self.grid = QVBoxLayout()
        self.grid.addWidget(self.graphics_widget)
        self.setLayout(self.grid)
 
        self.last_fov_drawn=None
        self.set_wellplate_type(sample)
 
        self.location_update_threshold_mm = 0.4    
 
        self.box_color = Color.RED
        self.box_line_thickness = 2
 
        self.x_mm = None
        self.y_mm = None
 
        self.update_display()

        self.preview_fovs=[]

        MUTABLE_MACHINE_CONFIG.wellplate_format_change.connect(self.set_wellplate_type)

    def set_wellplate_type(self,wellplate_type:Union[str,int]):
        if type(wellplate_type)==int:
            new_wellplate_type=WELLPLATE_NAMES[wellplate_type]
        else:
            new_wellplate_type=wellplate_type

        wellplate_type_image={
            'glass slide'        : 'images/slide carrier_828x662.png',
            WELLPLATE_NAMES[384] : 'images/384 well plate_1509x1010.png',
            WELLPLATE_NAMES[96]  : 'images/96 well plate_1509x1010.png',
            WELLPLATE_NAMES[24]  : 'images/24 well plate_1509x1010.png',
            WELLPLATE_NAMES[12]  : 'images/12 well plate_1509x1010.png',
            WELLPLATE_NAMES[6]   : 'images/6 well plate_1509x1010.png'
        }
        assert new_wellplate_type in wellplate_type_image, f"{new_wellplate_type} is not a valid plate type"
 
        self.background_image=cv2.imread(wellplate_type_image[new_wellplate_type])
 
        # current image is..
        self.current_image = np.copy(self.background_image)
        # current image display is..
        self.current_image_display = np.copy(self.background_image)
        self.image_height = self.background_image.shape[0]
        self.image_width = self.background_image.shape[1]
 
        self.sample = new_wellplate_type
 
        camera_pixel_size_um=MachineConfiguration.CAMERA_PIXEL_SIZE_UM[MACHINE_CONFIG.CAMERA_SENSOR]
        if new_wellplate_type == 'glass slide':
            self.origin_bottom_left_x = 200
            self.origin_bottom_left_y = 120
            self.mm_per_pixel = 0.1453
            self.fov_size_mm = 3000*camera_pixel_size_um/(50/9)/1000
        else:
            self.location_update_threshold_mm = 0.05
            WELLPLATE_IMAGE_LENGTH_IN_PIXELS=1509 # images in path(software/images) are 1509x1010
            WELLPLATE_384_LENGTH_IN_MM=127.8 # from https://www.thermofisher.com/document-connect/document-connect.html?url=https://assets.thermofisher.com/TFS-Assets%2FLSG%2Fmanuals%2Fcms_042831.pdf
            self.mm_per_pixel = WELLPLATE_384_LENGTH_IN_MM/WELLPLATE_IMAGE_LENGTH_IN_PIXELS # 0.084665 was the hardcoded value, which is closer to this number as calculated from the width of the plate at 85.5mm/1010px=0.0846535
            self.fov_size_mm = 3000*camera_pixel_size_um/(50/10)/1000 # '50/10' = tube_lens_mm/objective_magnification ?
            self.origin_bottom_left_x = MACHINE_CONFIG.X_ORIGIN_384_WELLPLATE_PIXEL - (MACHINE_CONFIG.X_MM_384_WELLPLATE_UPPERLEFT)/self.mm_per_pixel
            self.origin_bottom_left_y = MACHINE_CONFIG.Y_ORIGIN_384_WELLPLATE_PIXEL - (MACHINE_CONFIG.Y_MM_384_WELLPLATE_UPPERLEFT)/self.mm_per_pixel
 
        self.clear_imaged_positions()
 
    @TypecheckFunction
    def update_current_location(self,x_mm:Optional[float],y_mm:Optional[float]):
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

    @TypecheckFunction
    def coord_to_bb(self,x_mm:float,y_mm:float)->Tuple[Tuple[int,int],Tuple[int,int]]:
        if self.sample == 'glass slide':
            topleft_x:int=round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel)
            topleft_y:int=round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel)

            top_left = (topleft_x,topleft_y)

            bottomright_x:int=round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel)
            bottomright_y:int=round(self.image_height - (self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel)
            
            bottom_right = (bottomright_x, bottomright_y)
        else:
            topleft_x:int=round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel - self.fov_size_mm/2/self.mm_per_pixel)
            topleft_y:int=round((self.origin_bottom_left_y + y_mm/self.mm_per_pixel) - self.fov_size_mm/2/self.mm_per_pixel)

            top_left = (topleft_x,topleft_y)

            bottomright_x:int=round(self.origin_bottom_left_x + x_mm/self.mm_per_pixel + self.fov_size_mm/2/self.mm_per_pixel)
            bottomright_y:int=round((self.origin_bottom_left_y + y_mm/self.mm_per_pixel) + self.fov_size_mm/2/self.mm_per_pixel)

            bottom_right = (bottomright_x,bottomright_y)

        return top_left,bottom_right

    def clear_imaged_positions(self):
        self.current_image = np.copy(self.background_image)
        if not self.last_fov_drawn is None:
            self.draw_current_fov(*self.last_fov_drawn)
        self.update_display()

    def update_display(self):
        """
        needs to be called when self.current_image_display has been flushed
        e.g. after self.draw_current_fov() or self.clear_slide(), which is done currently
        """
        self.graphics_widget.img.setImage(self.current_image_display,autoLevels=False)

    def clear_slide(self):
        self.current_image = np.copy(self.background_image)
        self.current_image_display = np.copy(self.background_image)
        self.update_display()
    
    # this is used to draw an arbitrary fov onto the displayed image view
    @TypecheckFunction
    def draw_fov(self,x_mm:float,y_mm:float,color:Tuple[int,int,int],foreground:bool=True):
        current_FOV_top_left, current_FOV_bottom_right=self.coord_to_bb(x_mm,y_mm)
        if foreground:
            img_target=self.current_image_display
        else:
            img_target=self.current_image
        cv2.rectangle(img_target, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)

    # this is used to draw the fov when running acquisition
    # draw onto background buffer so that when live view is updated, the live view fov is drawn on top of the already imaged positions
    @TypecheckFunction
    def register_fov(self,x_mm:float,y_mm:float,color:Tuple[int,int,int] = Color.LIGHT_BLUE):
        current_FOV_top_left, current_FOV_bottom_right=self.coord_to_bb(x_mm,y_mm)
        cv2.rectangle(self.current_image, current_FOV_top_left, current_FOV_bottom_right, color, self.box_line_thickness)

    def register_preview_fovs(self):
        for x,y in self.preview_fovs:
            self.draw_fov(x,y,Color.LIGHT_GREY,foreground=False)

    # this is used to draw the fov when moving around live
    @TypecheckFunction
    def draw_current_fov(self,x_mm:float,y_mm:float):
        self.current_image_display = np.copy(self.current_image)
        self.draw_fov(x_mm,y_mm,self.box_color)
        self.update_display()

        self.last_fov_drawn=(x_mm,y_mm)
