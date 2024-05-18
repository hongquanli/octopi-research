import os 
# app specific libraries
import squid_control.control.camera as camera
import squid_control.control.core_reef as core
import squid_control.control.microcontroller as microcontroller
from squid_control.control._def import *
import logging
import squid_control.control.serial_peripherals as serial_peripherals
import squid_control.control.utils_.image_processing as im_processing
import matplotlib.path as mpath
if SUPPORT_LASER_AUTOFOCUS:
    import squid_control.control.core_displacement_measurement as core_displacement_measurement

import time

class SquidController:
    fps_software_trigger= 100

    def __init__(self,is_simulation = True, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.data_channel = None
        #load objects
        if is_simulation:
            if ENABLE_SPINNING_DISK_CONFOCAL:
                self.xlight = serial_peripherals.XLight_Simulation()
            if SUPPORT_LASER_AUTOFOCUS:
                self.camera = camera.Camera_Simulation(rotate_image_angle = ROTATE_IMAGE_ANGLE, flip_image=FLIP_IMAGE)
                self.camera_focus = camera.Camera_Simulation()
            else:
                self.camera = camera.Camera_Simulation(rotate_image_angle = ROTATE_IMAGE_ANGLE, flip_image=FLIP_IMAGE)
            self.microcontroller = microcontroller.Microcontroller_Simulation()
        else:
            if ENABLE_SPINNING_DISK_CONFOCAL:
                self.xlight = serial_peripherals.xlight()
            try:
                if SUPPORT_LASER_AUTOFOCUS:
                    sn_camera_main = camera.get_sn_by_model(MAIN_CAMERA_MODEL)
                    sn_camera_focus = camera.get_sn_by_model(FOCUS_CAMERA_MODEL)
                    self.camera = camera.Camera(sn=sn_camera_main,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                    self.camera.open()
                    self.camera_focus = camera.Camera(sn=sn_camera_focus)
                    self.camera_focus.open()
                else:
                    self.camera = camera.Camera(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                    self.camera.open()
            except:
                if SUPPORT_LASER_AUTOFOCUS:
                    self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                    self.camera.open()
                    self.camera_focus = camera.Camera_Simulation()
                    self.camera_focus.open()
                else:
                    self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                    self.camera.open()
                print('! camera not detected, using simulated camera !')
            self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)

        # reset the MCU
        self.microcontroller.reset()

        # reinitialize motor deivers and DAC  (in particular for V2.1 driver board where PG is not functional)
        self.microcontroller.initialize_drivers()
        
        # configure the actuators
        self.microcontroller.configure_actuators()

        self.configurationManager = core.ConfigurationManager(filename='./squid_control/channel_configurations.xml')

        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
        self.navigationController = core.NavigationController(self.microcontroller)
        self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController,is_for_wellplate=True)
        self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
        self.scanCoordinates = core.ScanCoordinates()
        self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
        #self.plateReaderNavigationController = core.PlateReaderNavigationController(self.microcontroller)
        if ENABLE_TRACKING:
            self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
        
        # open the camera
        # camera start streaming
        # self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
        # self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
        self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
        self.camera.set_callback(self.streamHandler.on_new_frame)
        # self.camera.enable_callback()
        # # camera

        self.camera.start_streaming()

        # set the configuration of class liveController (LED mode, expore time, etc.)
        self.liveController.set_microscope_mode(self.configurationManager.configurations[0])

        # laser autofocus
        if SUPPORT_LASER_AUTOFOCUS:

            # controllers
            self.configurationManager_focus_camera = core.ConfigurationManager(filename='./squid_control/focus_camera_configurations.xml')
            self.streamHandler_focus_camera = core.StreamHandler()
            self.liveController_focus_camera = core.LiveController(self.camera_focus,self.microcontroller,self.configurationManager_focus_camera,control_illumination=False,for_displacement_measurement=True)
            self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
            
            self.displacementMeasurementController = core_displacement_measurement.DisplacementMeasurementController()
            self.laserAutofocusController = core.LaserAutofocusController(self.microcontroller,self.camera_focus,self.liveController_focus_camera,self.navigationController,has_two_interfaces=HAS_TWO_INTERFACES,use_glass_top=USE_GLASS_TOP)

            # camera
            self.camera_focus.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
            # self.camera_focus.set_callback(self.streamHandler_focus_camera.on_new_frame)
            # self.camera_focus.enable_callback()
            self.camera_focus.start_streaming()
        

        self.illuminate_channels_for_scan = ['BF LED matrix full','Fluorescence 405 nm Ex']


        # retract the object
        self.navigationController.home_z()
        # wait for the operation to finish
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('z homing timeout, the program will exit')
                exit()
        print('objective retracted')
        self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

        # home XY, set zero and set software limit
        print('home xy')
        timestamp_start = time.time()
        # x needs to be at > + 20 mm when homing y
        self.navigationController.move_x(20) # to-do: add blocking code
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        # home y
        self.navigationController.home_y()
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('y homing timeout, the program will exit')
                exit()
        self.navigationController.zero_y()
        # home x
        self.navigationController.home_x()
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('y homing timeout, the program will exit')
                exit()
        self.navigationController.zero_x()
        self.slidePositionController.homing_done = True

        # move to scanning position
        self.navigationController.move_x(20)
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        self.navigationController.move_y(20)
        while self.microcontroller.is_busy():
            time.sleep(0.005)

        # move z
        self.navigationController.move_z_to(DEFAULT_Z_POS_MM)
        # wait for the operation to finish
        t0 = time.time() 
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 5:
                print('z return timeout, the program will exit')
                exit()

        # set software limits        
        self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
        self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
        self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
        self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
            
    def move_to_scaning_position(self):
        # move to scanning position
        self.navigationController.move_z_to(0.4)
        self.navigationController.move_x(20)
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        self.navigationController.move_y(20)
        while self.microcontroller.is_busy():
            time.sleep(0.005)

        # move z
        self.navigationController.move_z_to(DEFAULT_Z_POS_MM)
        # wait for the operation to finish
        t0 = time.time() 
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 5:
                print('z return timeout, the program will exit')
                exit()
    
    
    def plate_scan(self,well_plate_type='test', illuminate_channels=['BF LED matrix full'], do_autofocus=True, action_ID='testPlateScan'):
        # start the acquisition loop
        self.move_to_scaning_position()
        location_list = self.multipointController.get_location_list()
        self.multipointController.set_base_path(DEFAULT_SAVING_PATH)
        self.multipointController.set_selected_configurations(illuminate_channels)
        self.multipointController.do_autofocus = do_autofocus
        self.autofocusController.set_deltaZ(1.524)
        self.multipointController.start_new_experiment(action_ID)
        self.multipointController.run_acquisition_reef(location_list=location_list)
    
    def do_autofocus(self):
        self.autofocusController.set_deltaZ(1.524)
        self.autofocusController.set_N(15)
        self.autofocusController.autofocus()
        self.autofocusController.wait_till_autofocus_has_completed()

        
    def scan_well_plate(self, action_ID='01'):
        # start the acquisition loop
        location_list = self.multipointController.get_location_list(rows=3,cols=3)
        self.multipointController.set_base_path(DEFAULT_SAVING_PATH)
        self.multipointController.set_selected_configurations(self.illuminate_channels_for_scan)
        self.multipointController.do_autofocus = True
        self.multipointController.start_new_experiment(action_ID)
        self.multipointController.run_acquisition_reef(location_list=location_list)
        
    def platereader_move_to_well(self,row,column, wellplate_type='24'):
        if wellplate_type == '6':
            wellplate_format = WELLPLATE_FORMAT_6
        elif wellplate_type == '24':
            wellplate_format = WELLPLATE_FORMAT_24
        elif wellplate_type == '96':
            wellplate_format = WELLPLATE_FORMAT_96
        elif wellplate_type == '384':
            wellplate_format = WELLPLATE_FORMAT_384 
        
        if column != 0 and column != None:
            mm_per_ustep_X = SCREW_PITCH_X_MM/(self.navigationController.x_microstepping*FULLSTEPS_PER_REV_X)
            x_mm = wellplate_format.A1_X_MM + (int(column)-1)*wellplate_format.WELL_SPACING_MM
            x_usteps = STAGE_MOVEMENT_SIGN_X*round(x_mm/mm_per_ustep_X)
            self.microcontroller.move_x_to_usteps(x_usteps)
        if row != 0 and row != None:
            mm_per_ustep_Y = SCREW_PITCH_Y_MM/(self.navigationController.y_microstepping*FULLSTEPS_PER_REV_Y)
            y_mm = wellplate_format.A1_Y_MM + (ord(row) - ord('A'))*wellplate_format.WELL_SPACING_MM
            y_usteps = STAGE_MOVEMENT_SIGN_Y*round(y_mm/mm_per_ustep_Y)
            self.microcontroller.move_y_to_usteps(y_usteps)
    
    def is_point_in_octagon_border(self, x, y, z):
        if z >= 4.5 or z <= 0.1:
            return False
        # Create a Path object from octagon points
        path = mpath.Path(OCTAGON_LIMIT_FOR_WELLPLATE)
        
        # Check if the point (x, y) is inside the octagon
        return path.contains_point((x, y))
    
    def move_x_to_safely(self, x):
        x_pos,y_pos, z_pos, *_ = self.navigationController.update_pos(microcontroller=self.microcontroller)

        if self.is_point_in_octagon_border(x, y_pos, z_pos):
            self.navigationController.move_x_to(x)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
        else:
            return False, x_pos, y_pos, z_pos, x
        return True, x_pos, y_pos, z_pos, x
    
    def move_y_to_safely(self, y):
        x_pos,y_pos, z_pos, *_ = self.navigationController.update_pos(microcontroller=self.microcontroller)

        if self.is_point_in_octagon_border(x_pos, y, z_pos):
            self.navigationController.move_y_to(y)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
        else:
            return False, x_pos, y_pos, z_pos, y
        return True, x_pos, y_pos, z_pos, y

    def move_z_to_safely(self, z):
        x_pos,y_pos, z_pos, *_ = self.navigationController.update_pos(microcontroller=self.microcontroller)

        if self.is_point_in_octagon_border(x_pos, y_pos, z):
            self.navigationController.move_z_to(z)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
        else:
            return False, x_pos, y_pos, z_pos, z
        return True, x_pos, y_pos, z_pos, z


    def move_by_distance_safely(self, dx, dy, dz):
        x_pos,y_pos, z_pos, *_ = self.navigationController.update_pos(microcontroller=self.microcontroller)

        if self.is_point_in_octagon_border(x_pos+dx, y_pos+dy, z_pos+dz):
            self.navigationController.move_x(dx)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
            self.navigationController.move_y(dy)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
            self.navigationController.move_z(dz)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
        else:
            return False, x_pos, y_pos, z_pos, x_pos+dx, y_pos+dy, z_pos+dz
        return True, x_pos, y_pos, z_pos, x_pos+dx, y_pos+dy, z_pos+dz
    
    def home_stage(self):
        # retract the object
        self.navigationController.home_z()
        # wait for the operation to finish
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('z homing timeout, the program will exit')
                exit()
        print('objective retracted')
        self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

        # home XY, set zero and set software limit
        print('home xy')
        timestamp_start = time.time()
        # x needs to be at > + 20 mm when homing y
        self.navigationController.move_x(20) # to-do: add blocking code
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        # home y
        self.navigationController.home_y()
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('y homing timeout, the program will exit')
                exit()
        self.navigationController.zero_y()
        # home x
        self.navigationController.home_x()
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('y homing timeout, the program will exit')
                exit()
        self.navigationController.zero_x()
        self.slidePositionController.homing_done = True

        # move to scanning position
        self.navigationController.move_x(20)
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        self.navigationController.move_y(20)
        while self.microcontroller.is_busy():
            time.sleep(0.005)

        # move z
        self.navigationController.move_z_to(DEFAULT_Z_POS_MM)
        # wait for the operation to finish
        t0 = time.time() 
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 5:
                print('z return timeout, the program will exit')
                exit()

    def close(self):

        # move the objective to a defined position upon exit
        self.navigationController.move_x(0.1) # temporary bug fix - move_x needs to be called before move_x_to if the stage has been moved by the joystick
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        self.navigationController.move_x_to(30)
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        self.navigationController.move_y(0.1) # temporary bug fix - move_y needs to be called before move_y_to if the stage has been moved by the joystick
        while self.microcontroller.is_busy():
            time.sleep(0.005)
        self.navigationController.move_y_to(30)
        while self.microcontroller.is_busy():
            time.sleep(0.005)

        self.liveController.stop_live()
        self.camera.close()
        self.imageSaver.close()
        self.imageDisplay.close()
        if SUPPORT_LASER_AUTOFOCUS:
            self.camera_focus.close()
            #self.imageDisplayWindow_focus.close()
        self.microcontroller.close()

