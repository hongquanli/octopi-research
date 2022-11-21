from multiprocessing.sharedctypes import Value
from qtpy.QtCore import Qt, QThread, QObject
from qtpy.QtWidgets import QApplication

# app specific libraries
from control._def import *
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
import control.core_displacement_measurement as core_displacement_measurement

from control.typechecker import TypecheckFunction

from typing import List, Tuple, Callable

class HCSController(QObject):
    def __init__(self,home:bool=True):
        super().__init__()

        if not home:
            print("warning: disabled homing on startup can lead to misalignment of the stage. proceed at your own risk. (may damage objective, and/or run into software stage position limits, which can lead to unexpected behaviour)")

        # load objects
        try:
            sn_camera_main = camera.get_sn_by_model(MACHINE_CONFIG.MAIN_CAMERA_MODEL)
            self.camera = camera.Camera(sn=sn_camera_main,rotate_image_angle=MACHINE_CONFIG.ROTATE_IMAGE_ANGLE,flip_image=MACHINE_CONFIG.FLIP_IMAGE)
            self.camera.open()
        except Exception as e:
            print('! imaging camera not detected !')
            raise e

        try:
            sn_camera_focus = camera.get_sn_by_model(MACHINE_CONFIG.FOCUS_CAMERA_MODEL)
            self.focus_camera = camera.Camera(sn=sn_camera_focus,used_for_laser_autofocus=True)
            self.focus_camera.open()
        except Exception as e:
            print('! laser AF camera not detected !')
            raise e

        try:
            self.microcontroller:microcontroller.Microcontroller = microcontroller.Microcontroller(version=MACHINE_CONFIG.CONTROLLER_VERSION)
        except Exception as e:
            print("! microcontroller not detected !")
            raise e

        # reset the MCU
        self.microcontroller.reset()
        # reinitialize motor drivers and DAC (in particular for V2.1 driver board where PG is not functional)
        self.microcontroller.initialize_drivers()
        # configure the actuators
        self.microcontroller.configure_actuators()

        self.configurationManager:    core.ConfigurationManager    = core.ConfigurationManager(filename='./channel_config_main_camera.xml')
        self.streamHandler:           core.StreamHandler           = core.StreamHandler()
        self.liveController:          core.LiveController          = core.LiveController(self.camera,self.microcontroller,self.configurationManager,on_frame_acquired=self.streamHandler.signal_new_frame_received)

        self.navigationController:    core.NavigationController    = core.NavigationController(self.microcontroller)
        self.autofocusController:     core.AutoFocusController     = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
        self.multipointController:    core.MultiPointController    = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager)
        self.imageSaver:              core.ImageSaver              = core.ImageSaver()

        # open the camera
        self.camera.set_software_triggered_acquisition()
        self.camera.set_callback(self.streamHandler.on_new_frame)
        self.camera.enable_callback()

        if home:
            self.navigationController.home(home_x=MACHINE_CONFIG.HOMING_ENABLED_X,home_y=MACHINE_CONFIG.HOMING_ENABLED_Y,home_z=MACHINE_CONFIG.HOMING_ENABLED_Z)

        self.num_running_experiments=0

        LASER_AF_ENABLED=True
        if LASER_AF_ENABLED:
            # controllers
            self.configurationManager_focus_camera = core.ConfigurationManager(filename='./channel_config_focus_camera.xml')
            self.streamHandler_focus_camera = core.StreamHandler()
            self.liveController_focus_camera = core.LiveController(self.focus_camera,self.microcontroller,self.configurationManager_focus_camera,on_frame_acquired=self.streamHandler_focus_camera.signal_new_frame_received,control_illumination=False,for_displacement_measurement=True)

            self.displacementMeasurementController = core_displacement_measurement.DisplacementMeasurementController()
            self.laserAutofocusController = core.LaserAutofocusController(self.microcontroller,self.focus_camera,self.liveController_focus_camera,self.navigationController,has_two_interfaces=MACHINE_CONFIG.HAS_TWO_INTERFACES,use_glass_top=MACHINE_CONFIG.USE_GLASS_TOP)

            # camera
            self.focus_camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
            self.focus_camera.set_callback(self.streamHandler_focus_camera.on_new_frame)
            self.focus_camera.enable_callback()
            self.focus_camera.start_streaming()

    #@TypecheckFunction
    def acquire(self,
        well_list:List[Tuple[int,int]],
        channels:List[str],
        experiment_id:str,
        grid_data:Dict[str,dict]={
            'x':{'d':0.9,'N':1},
            'y':{'d':0.9,'N':1},
            'z':{'d':0.9,'N':1},
            't':{'d':0.9,'N':1},
        },
        af_channel:Optional[str]=None,
        plate_type:ClosedSet[Optional[int]](None,6,12,24,96,384)=None,

        set_num_acquisitions_callback:Optional[Callable[[int],None]]=None,
        on_new_acquisition:Optional[Callable[[str],None]]=None,
    )->Optional[QThread]:
        # set objective and well plate type from machine config (or.. should be part of imaging configuration..?)
        # set wells to be imaged <- acquire.well_list argument
        # set grid per well to be imaged
        # set lighting settings per channel
        # set selection and order of channels to be imaged <- acquire.channels argument

        # calculate physical imaging positions on wellplate given plate type and well selection
        wellplate_format=WELLPLATE_FORMATS[plate_type if not plate_type is None else MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT]

        # validate well positions (should be on the plate, given selected wellplate type)
        if wellplate_format.number_of_skip>0:
            for well_row,well_column in well_list:
                if well_row<0 or well_column<0:
                    raise ValueError(f"are you mad?! {well_row=} {well_column=}")

                if well_row>=wellplate_format.rows:
                    raise ValueError(f"{well_row=} is out of bounds {wellplate_format}")
                if well_column>=wellplate_format.columns:
                    raise ValueError(f"{well_column=} is out of bounds {wellplate_format}")

                if well_row<wellplate_format.number_of_skip:
                    raise ValueError(f"well {well_row=} out of bounds {wellplate_format}")
                if well_row>=(wellplate_format.rows-wellplate_format.number_of_skip):
                    raise ValueError(f"well {well_row=} out of bounds {wellplate_format}")

                if well_column<wellplate_format.number_of_skip:
                    raise ValueError(f"well {well_column=} out of bounds {wellplate_format}")
                if well_column>=(wellplate_format.columns-wellplate_format.number_of_skip):
                    raise ValueError(f"well {well_column=} out of bounds {wellplate_format}")

        well_list_names:List[str]=[wellplate_format.well_name(*c) for c in well_list]
        well_list_physical_pos:List[Tuple[float,float]]=[wellplate_format.convert_well_index(*c) for c in well_list]

        # print well names as debug info
        print("imaging wells: ",", ".join(well_list_names))

        # set autofocus parameters
        if af_channel is None:
            self.multipointController.set_af_flag(False)
        else:
            assert af_channel in [c.name for c in self.configurationManager.configurations], f"{af_channel} is not a valid (AF) channel"
            if af_channel!=MUTABLE_MACHINE_CONFIG.MULTIPOINT_AUTOFOCUS_CHANNEL:
                MUTABLE_MACHINE_CONFIG.MULTIPOINT_AUTOFOCUS_CHANNEL=af_channel
            self.multipointController.set_af_flag(True)

        # set grid data per well
        self.multipointController.set_NX(grid_data['x']['N'])
        self.multipointController.set_NY(grid_data['y']['N'])
        self.multipointController.set_NZ(grid_data['z']['N'])
        self.multipointController.set_Nt(grid_data['t']['N'])
        self.multipointController.set_deltaX(grid_data['x']['d'])
        self.multipointController.set_deltaY(grid_data['y']['d'])
        self.multipointController.set_deltaZ(grid_data['z']['d'])
        self.multipointController.set_deltat(grid_data['t']['d'])

        for i,(well_row,well_column) in enumerate(well_list):
            well_x_mm,well_y_mm=well_list_physical_pos[i]
            for x_grid_item,y_grid_item in self.multipointController.grid_positions_for_well(well_x_mm,well_y_mm):
                if self.fov_exceeds_well_boundary(well_row,well_column,x_grid_item,y_grid_item):
                    raise ValueError(f"at least one grid item is outside the bounds of the well! well size is {wellplate_format.well_size_mm}mm")

        # set list of imaging channels
        self.multipointController.set_selected_configurations(channels)

        # set image saving location
        self.multipointController.set_base_path(path="/home/pharmbio/Downloads")
        self.multipointController.prepare_folder_for_new_experiment(experiment_ID=experiment_id) # todo change this to a callback (so that each image can be handled in a callback, not as batch or whatever)

        # start experiment, and return thread that actually does the imaging (thread.finished can be connected to some callback)
        return self.multipointController.run_experiment((well_list_names,well_list_physical_pos),set_num_acquisitions_callback,on_new_acquisition)

    @TypecheckFunction
    def fov_exceeds_well_boundary(self,well_row:int,well_column:int,x_mm:float,y_mm:float)->bool:
        wellplate_format=WELLPLATE_FORMATS[MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT]

        well_center_x_mm,well_center_y_mm=wellplate_format.convert_well_index(well_row,well_column)

        # assuming wells are square (even though they are round-ish)
        well_left_boundary=well_center_x_mm-wellplate_format.well_size_mm/2
        well_right_boundary=well_center_x_mm+wellplate_format.well_size_mm/2
        assert well_left_boundary<well_right_boundary
        well_upper_boundary=well_center_y_mm+wellplate_format.well_size_mm/2
        well_lower_boundary=well_center_y_mm-wellplate_format.well_size_mm/2
        assert well_lower_boundary<well_upper_boundary

        is_in_bounds=x_mm>=well_left_boundary and x_mm<=well_right_boundary and y_mm<=well_upper_boundary and y_mm>=well_lower_boundary

        return not is_in_bounds

    @TypecheckFunction
    def close(self):
        # make sure the lasers are turned off!
        self.microcontroller.turn_off_illumination()

        # move the objective to a defined position upon exit
        self.navigationController.move_x(0.1) # temporary bug fix - move_x needs to be called before move_x_to if the stage has been moved by the joystick
        self.microcontroller.wait_till_operation_is_completed(5, 0.005)

        self.navigationController.move_x_to(30.0)
        self.microcontroller.wait_till_operation_is_completed(5, 0.005)

        self.navigationController.move_y(0.1) # temporary bug fix - move_y needs to be called before move_y_to if the stage has been moved by the joystick
        self.microcontroller.wait_till_operation_is_completed(5, 0.005)

        self.navigationController.move_y_to(30.0)
        self.microcontroller.wait_till_operation_is_completed(5, 0.005)

        self.liveController.stop_live()
        self.camera.close()
        self.focus_camera.close()
        self.imageSaver.close()
        self.microcontroller.close()

        QApplication.quit()

    # todo add callbacks to be triggered on image acquisition (e.g. for histograms, saving to disk etc.)
