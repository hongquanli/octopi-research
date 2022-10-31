# qt libraries
from qtpy.QtCore import QObject, Signal, QThread, Qt # type: ignore
from qtpy.QtWidgets import QApplication

import control.utils as utils
from control._def import *

import os
import time
import numpy as np
import cv2
from datetime import datetime

import json
import pandas as pd

import imageio as iio

from typing import Optional, List, Union, Tuple, Callable

import control.camera as camera
from control.core import Configuration, NavigationController, LiveController, AutoFocusController, ConfigurationManager
#import control.widgets as widgets # not possible because circular import
from control.typechecker import TypecheckFunction
from control.widgets.well_selection import WellSelectionWidget

class MultiPointWorker(QObject):

    finished = Signal()
    image_to_display = Signal(np.ndarray)
    spectrum_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    signal_current_configuration = Signal(Configuration)
    signal_register_current_fov = Signal(float,float)

    def __init__(self,multiPointController,scan_coordinates:Tuple[List[str],List[Tuple[float,float]]]):
        super().__init__()
        self.multiPointController:MultiPointController = multiPointController

        # copy all (relevant) fields to unlock multipointcontroller on thread start
        self.camera = self.multiPointController.camera
        self.microcontroller = self.multiPointController.microcontroller
        self.navigationController = self.multiPointController.navigationController
        self.liveController = self.multiPointController.liveController
        self.autofocusController = self.multiPointController.autofocusController
        self.configurationManager = self.multiPointController.configurationManager
        self.NX = self.multiPointController.NX
        self.NY = self.multiPointController.NY
        self.NZ = self.multiPointController.NZ
        self.Nt = self.multiPointController.Nt
        self.deltaX = self.multiPointController.deltaX
        self.deltaX_usteps = self.multiPointController.deltaX_usteps
        self.deltaY = self.multiPointController.deltaY
        self.deltaY_usteps = self.multiPointController.deltaY_usteps
        self.deltaZ = self.multiPointController.deltaZ
        self.deltaZ_usteps = self.multiPointController.deltaZ_usteps
        self.dt = self.multiPointController.deltat
        self.do_autofocus = self.multiPointController.do_autofocus
        self.crop_width = self.multiPointController.crop_width
        self.crop_height = self.multiPointController.crop_height
        self.display_resolution_scaling = self.multiPointController.display_resolution_scaling
        self.counter = self.multiPointController.counter
        self.experiment_ID = self.multiPointController.experiment_ID
        self.base_path = self.multiPointController.base_path
        self.selected_configurations = self.multiPointController.selected_configurations

        self.timestamp_acquisition_started = self.multiPointController.timestamp_acquisition_started
        self.time_point = 0

        self.scan_coordinates_name,self.scan_coordinates_mm = scan_coordinates

    def run(self):
        while self.time_point < self.Nt:
            # continous acquisition
            if self.dt == 0:
                self.run_single_time_point()
                if self.multiPointController.abort_acqusition_requested:
                    break
                self.time_point = self.time_point + 1
            # timed acquisition
            else:
                self.run_single_time_point()
                if self.multiPointController.abort_acqusition_requested:
                    break
                self.time_point = self.time_point + 1
                # check if the aquisition has taken longer than dt or integer multiples of dt, if so skip the next time point(s)
                while time.time() > self.timestamp_acquisition_started + self.time_point*self.dt:
                    print('skip time point ' + str(self.time_point+1))
                    self.time_point = self.time_point+1
                if self.time_point == self.Nt:
                    break # no waiting after taking the last time point
                # wait until it's time to do the next acquisition
                while time.time() < self.timestamp_acquisition_started + self.time_point*self.dt:
                    time.sleep(0.05)
        self.finished.emit()

    def wait_till_operation_is_completed(self):
        while self.microcontroller.is_busy():
            time.sleep(MACHINE_CONFIG.SLEEP_TIME_S)

    def run_single_time_point(self):

        # disable joystick button action
        self.navigationController.enable_joystick_button_action = False

        self.FOV_counter = 0
        print('multipoint acquisition - time point ' + str(self.time_point+1))
        
        # for each time point, create a new folder
        current_path = os.path.join(self.base_path,self.experiment_ID,str(self.time_point))
        os.mkdir(current_path)

        # create a dataframe to save coordinates
        coordinates_pd = pd.DataFrame(columns = ['i', 'j', 'k', 'x (mm)', 'y (mm)', 'z (um)'])

        n_regions = len(self.scan_coordinates_name)
        for coordinate_id in range(n_regions):
            coordiante_mm = self.scan_coordinates_mm[coordinate_id]
            coordiante_name = self.scan_coordinates_name[coordinate_id]

            # move to the specified coordinate
            self.navigationController.move_x_to(coordiante_mm[0]-self.deltaX*(self.NX-1)/2)
            self.wait_till_operation_is_completed()
            time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_X/1000)
            self.navigationController.move_y_to(coordiante_mm[1]-self.deltaY*(self.NY-1)/2)
            self.wait_till_operation_is_completed()
            time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_Y/1000)
            # add '_' to the coordinate name
            coordiante_name = coordiante_name + '_'

            x_scan_direction = 1
            dx_usteps = 0
            dy_usteps = 0
            dz_usteps = 0
            z_pos = self.navigationController.z_pos

            # z stacking config
            if MACHINE_CONFIG.Z_STACKING_CONFIG == 'FROM TOP':
                self.deltaZ_usteps = -abs(self.deltaZ_usteps)

            # along y
            for i in range(self.NY):

                self.FOV_counter = 0 # so that AF at the beginning of each new row

                # along x
                for j in range(self.NX):

                    # perform AF only if when not taking z stack or doing z stack from center
                    if ( (self.NZ == 1) or MACHINE_CONFIG.Z_STACKING_CONFIG == 'FROM CENTER' ) and (self.do_autofocus) and (self.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
                    # temporary: replace the above line with the line below to AF every FOV
                    # if (self.NZ == 1) and (self.do_autofocus):
                        configuration_name_AF = self.multiPointController.autofocus_channel_name
                        config_AF = next((config for config in self.configurationManager.configurations if config.name == configuration_name_AF))
                        self.signal_current_configuration.emit(config_AF)
                        self.camera.start_streaming() # work around a bug, explained in MultiPointController.run_experiment
                        self.autofocusController.autofocus()
                        self.autofocusController.wait_till_autofocus_has_completed()
                    
                    if (self.NZ > 1):
                        # move to bottom of the z stack
                        if MACHINE_CONFIG.Z_STACKING_CONFIG == 'FROM CENTER':
                            self.navigationController.move_z_usteps(-self.deltaZ_usteps*round((self.NZ-1)/2))
                            self.wait_till_operation_is_completed()
                            time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_Z/1000)
                        # maneuver for achiving uniform step size and repeatability when using open-loop control
                        self.navigationController.move_z_usteps(-160)
                        self.wait_till_operation_is_completed()
                        self.navigationController.move_z_usteps(160)
                        self.wait_till_operation_is_completed()
                        time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_Z/1000)

                    # z-stack
                    for k in range(self.NZ):
                        
                        file_ID = coordiante_name + str(i) + '_' + str(j if x_scan_direction==1 else self.NX-1-j) + '_' + str(k)
                        # metadata = dict(x = self.navigationController.x_pos_mm, y = self.navigationController.y_pos_mm, z = self.navigationController.z_pos_mm)
                        # metadata = json.dumps(metadata)

                        # iterate through selected modes
                        for config in self.selected_configurations:
                            if 'USB Spectrometer' in config.name:
                                raise Exception("usb spectrometer not supported")

                            # update the current configuration
                            self.signal_current_configuration.emit(config)
                            self.wait_till_operation_is_completed()
                            # trigger acquisition (including turning on the illumination)
                            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                self.liveController.turn_on_illumination()
                                self.wait_till_operation_is_completed()
                                self.camera.send_trigger()
                            elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                                self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)
                            # read camera frame
                            image = self.camera.read_frame()
                            # tunr of the illumination if using software trigger
                            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                                self.liveController.turn_off_illumination()
                            # process the image -  @@@ to move to camera
                            image = utils.crop_image(image,self.crop_width,self.crop_height)
                            image = utils.rotate_and_flip_image(image,rotate_image_angle=self.camera.rotate_image_angle,flip_image=self.camera.flip_image)
                            # self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
                            image_to_display = utils.crop_image(image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling))
                            self.image_to_display.emit(image_to_display)
                            self.image_to_display_multi.emit(image_to_display,config.illumination_source)
                            if image.dtype == np.uint16:
                                saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.tiff')
                                if self.camera.is_color:
                                    if 'BF LED matrix' in config.name:
                                        if MUTABLE_MACHINE_CONFIG.MULTIPOINT_BF_SAVING_OPTION == BrightfieldSavingMode.RGB2GRAY:
                                            image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                        elif MUTABLE_MACHINE_CONFIG.MULTIPOINT_BF_SAVING_OPTION == BrightfieldSavingMode.GREEN_ONLY:
                                            image = image[:,:,1]
                                iio.imwrite(saving_path,image)
                            else:
                                saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.' + Acquisition.IMAGE_FORMAT)
                                if self.camera.is_color:
                                    if 'BF LED matrix' in config.name:
                                        if MUTABLE_MACHINE_CONFIG.MULTIPOINT_BF_SAVING_OPTION == BrightfieldSavingMode.RAW:
                                            image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                                        elif MUTABLE_MACHINE_CONFIG.MULTIPOINT_BF_SAVING_OPTION == BrightfieldSavingMode.RGB2GRAY:
                                            image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                                        elif MUTABLE_MACHINE_CONFIG.MULTIPOINT_BF_SAVING_OPTION == BrightfieldSavingMode.GREEN_ONLY:
                                            image = image[:,:,1]
                                    else:
                                        image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                                cv2.imwrite(saving_path,image)
                            QApplication.processEvents()

                        # add the coordinate of the current location
                        coordinates_pd = pd.concat([
                            coordinates_pd,
                            pd.DataFrame([{'i':i,'j':j,'k':k,
                                            'x (mm)':self.navigationController.x_pos_mm,
                                            'y (mm)':self.navigationController.y_pos_mm,
                                            'z (um)':self.navigationController.z_pos_mm*1000}])
                        ])

                        # register the current fov in the navigationViewer 
                        self.signal_register_current_fov.emit(self.navigationController.x_pos_mm,self.navigationController.y_pos_mm)

                        # check if the acquisition should be aborted
                        if self.multiPointController.abort_acqusition_requested:
                            self.liveController.turn_off_illumination()
                            self.navigationController.move_x_usteps(-dx_usteps)
                            self.wait_till_operation_is_completed()
                            self.navigationController.move_y_usteps(-dy_usteps)
                            self.wait_till_operation_is_completed()
                            self.navigationController.move_z_usteps(-dz_usteps)
                            self.wait_till_operation_is_completed()

                            coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
                            self.navigationController.enable_joystick_button_action = True

                            return

                        if self.NZ > 1:
                            # move z
                            if k < self.NZ - 1:
                                self.navigationController.move_z_usteps(self.deltaZ_usteps)
                                self.wait_till_operation_is_completed()
                                time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_Z/1000)
                                dz_usteps = dz_usteps + self.deltaZ_usteps
                    
                    if self.NZ > 1:
                        # move z back
                        if MACHINE_CONFIG.Z_STACKING_CONFIG == 'FROM CENTER':
                            self.navigationController.move_z_usteps( -self.deltaZ_usteps*(self.NZ-1) + self.deltaZ_usteps*round((self.NZ-1)/2) )
                            self.wait_till_operation_is_completed()
                            dz_usteps = dz_usteps - self.deltaZ_usteps*(self.NZ-1) + self.deltaZ_usteps*round((self.NZ-1)/2)
                        else:
                            self.navigationController.move_z_usteps(-self.deltaZ_usteps*(self.NZ-1))
                            self.wait_till_operation_is_completed()
                            dz_usteps = dz_usteps - self.deltaZ_usteps*(self.NZ-1)

                    # update FOV counter
                    self.FOV_counter = self.FOV_counter + 1

                    if self.NX > 1:
                        # move x
                        if j < self.NX - 1:
                            self.navigationController.move_x_usteps(x_scan_direction*self.deltaX_usteps)
                            self.wait_till_operation_is_completed()
                            time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_X/1000)
                            dx_usteps = dx_usteps + x_scan_direction*self.deltaX_usteps

                '''
                # instead of move back, reverse scan direction (12/29/2021)
                if self.NX > 1:
                    # move x back
                    self.navigationController.move_x_usteps(-self.deltaX_usteps*(self.NX-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(SCAN_STABILIZATION_TIME_MS_X/1000)
                '''
                x_scan_direction = -x_scan_direction

                if self.NY > 1:
                    # move y
                    if i < self.NY - 1:
                        self.navigationController.move_y_usteps(self.deltaY_usteps)
                        self.wait_till_operation_is_completed()
                        time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_Y/1000)
                        dy_usteps = dy_usteps + self.deltaY_usteps

            if n_regions == 1:
                # only move to the start position if there's only one region in the scan
                if self.NY > 1:
                    # move y back
                    self.navigationController.move_y_usteps(-self.deltaY_usteps*(self.NY-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_Y/1000)
                    dy_usteps = dy_usteps - self.deltaY_usteps*(self.NY-1)

                # move x back at the end of the scan
                if x_scan_direction == -1:
                    self.navigationController.move_x_usteps(-self.deltaX_usteps*(self.NX-1))
                    self.wait_till_operation_is_completed()
                    time.sleep(MACHINE_CONFIG.SCAN_STABILIZATION_TIME_MS_X/1000)

                # move z back
                self.navigationController.microcontroller.move_z_to_usteps(z_pos)
                self.wait_till_operation_is_completed()

        coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
        self.navigationController.enable_joystick_button_action = True

class MultiPointController(QObject):

    acquisitionFinished = Signal()
    image_to_display = Signal(np.ndarray)
    image_to_display_multi = Signal(np.ndarray,int)
    spectrum_to_display = Signal(np.ndarray)
    signal_current_configuration = Signal(Configuration)
    signal_register_current_fov = Signal(float,float)

    #@TypecheckFunction
    def __init__(self,
        camera:camera.Camera,
        navigationController:NavigationController,
        liveController:LiveController,
        autofocusController:AutoFocusController,
        configurationManager:ConfigurationManager,
        well_selection_generator:Optional[Callable[[],Tuple[List[str],List[Tuple[float,float]]]]],
        start_experiment:Callable[[str,List[str]],None],
        abort_experiment:Callable[[],None]
    ):
        QObject.__init__(self)

        self.camera = camera
        self.microcontroller = navigationController.microcontroller # to move to gui for transparency
        self.navigationController = navigationController
        self.liveController = liveController
        self.autofocusController = autofocusController
        self.configurationManager = configurationManager
        self.NX:int = 1
        self.NY:int = 1
        self.NZ:int = 1
        self.Nt:int = 1
        self.deltaX = Acquisition.DX
        self.deltaX_usteps:int = round(self.deltaX/self.mm_per_ustep_X)
        self.deltaY = Acquisition.DY
        self.deltaY_usteps:int = round(self.deltaY/self.mm_per_ustep_Y)
        self.deltaZ = Acquisition.DZ/1000
        self.deltaZ_usteps:int = round(self.deltaZ/self.mm_per_ustep_Z)
        self.deltat:float = 0.0
        self.do_autofocus:bool = False
        self.crop_width = Acquisition.CROP_WIDTH
        self.crop_height = Acquisition.CROP_HEIGHT
        self.display_resolution_scaling = Acquisition.IMAGE_DISPLAY_SCALING_FACTOR
        self.counter:int = 0
        self.experiment_ID: Optional[str] = None
        self.base_path:Optional[str]  = None
        self.selected_configurations = []
        self.autofocus_channel_name=MUTABLE_MACHINE_CONFIG.MULTIPOINT_AUTOFOCUS_CHANNEL
        self.thread:Optional[QThread]=None

        self.well_selection_generator = well_selection_generator

        self.start_experiment=start_experiment
        self.abort_experiment=abort_experiment

        # set some default values to avoid introducing new attributes outside constructor
        self.abort_acqusition_requested = False
        self.configuration_before_running_multipoint = self.liveController.currentConfiguration
        self.liveController_was_live_before_multipoint = False
        self.camera_callback_was_enabled_before_multipoint = False

    @property
    def mm_per_ustep_X(self):
        return MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.navigationController.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X)
    @property
    def mm_per_ustep_Y(self):
        return MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.navigationController.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y)
    @property
    def mm_per_ustep_Z(self):
        return MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z)

    @TypecheckFunction
    def set_NX(self,N:int):
        self.NX = N
    @TypecheckFunction
    def set_NY(self,N:int):
        self.NY = N
    @TypecheckFunction
    def set_NZ(self,N:int):
        self.NZ = N
    @TypecheckFunction
    def set_Nt(self,N:int):
        self.Nt = N

    @TypecheckFunction
    def set_deltaX(self,delta:float):
        self.deltaX = delta
        self.deltaX_usteps = round(delta/self.mm_per_ustep_X)
    @TypecheckFunction
    def set_deltaY(self,delta:float):
        self.deltaY = delta
        self.deltaY_usteps = round(delta/self.mm_per_ustep_Y)
    @TypecheckFunction
    def set_deltaZ(self,delta_um:float):
        self.deltaZ = delta_um/1000
        self.deltaZ_usteps = round((delta_um/1000)/self.mm_per_ustep_Z)
    @TypecheckFunction
    def set_deltat(self,delta:float):
        self.deltat = delta
    @TypecheckFunction
    def set_af_flag(self,flag:Union[int,bool]):
        if type(flag)==bool:
            self.do_autofocus=flag
        else:
            self.do_autofocus = {
                0:False,
                2:True
            }[flag]

    @TypecheckFunction
    def set_crop(self,crop_width:int,crop_height:int):
        self.crop_width = crop_width
        self.crop_height = crop_height

    @TypecheckFunction
    def set_base_path(self,path:str):
        self.base_path = path

    @TypecheckFunction
    def prepare_folder_for_new_experiment(self,experiment_ID:str):
        # generate unique experiment ID
        self.experiment_ID = experiment_ID.replace(' ','_') + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f')
        self.recording_start_time = time.time()

        # create a new folder
        assert not self.base_path is None
        os.mkdir(os.path.join(self.base_path,self.experiment_ID))
        self.configurationManager.write_configuration(os.path.join(self.base_path,self.experiment_ID)+"/configurations.xml") # save the configuration for the experiment
        acquisition_parameters = {'dx(mm)':self.deltaX, 'Nx':self.NX, 'dy(mm)':self.deltaY, 'Ny':self.NY, 'dz(um)':self.deltaZ*1000,'Nz':self.NZ,'dt(s)':self.deltat,'Nt':self.Nt,'with AF':self.do_autofocus}
        f = open(os.path.join(self.base_path,self.experiment_ID)+"/acquisition parameters.json","w")
        f.write(json.dumps(acquisition_parameters))
        f.close()

    def set_selected_configurations(self, selected_configurations_name):
        self.selected_configurations = []
        for configuration_name in selected_configurations_name:
            self.selected_configurations.append(next((config for config in self.configurationManager.configurations if config.name == configuration_name)))
        
    def run_experiment(self,well_selection:Optional[Tuple[List[str],List[Tuple[float,float]]]]=None):
        if well_selection is None:
            image_positions=self.well_selection_generator()
        else:
            image_positions=well_selection

        num_wells=len(image_positions[0])
        num_images_per_well=self.NX*self.NY*self.NZ*self.Nt
        num_channels=len(self.selected_configurations)

        self.abort_acqusition_requested = False
        self.liveController_was_live_before_multipoint = False
        self.camera_callback_was_enabled_before_multipoint = False
        self.configuration_before_running_multipoint = self.liveController.currentConfiguration

        if num_wells==0:
            print("no wells selected - not acquiring anything")
            self._on_acquisition_completed()
        elif num_images_per_well==0:
            print("no images per well - not acquiring anything")
            self._on_acquisition_completed()
        elif num_channels==0:
            print("no channels selected - not acquiring anything")
            self._on_acquisition_completed()
        else:
            print(f"start multipoint with {num_wells} wells, {num_images_per_well} images per well, {num_channels} channels, total={num_wells*num_images_per_well*num_channels} images (AF is {'on' if self.do_autofocus else 'off'})")
        
            # stop live
            if self.liveController.is_live:
                self.liveController_was_live_before_multipoint = True
                self.liveController.stop_live() # @@@ to do: also uncheck the live button

            # LiveController.start_live enables this, but LiveController.stop_live does not disable, and a comment there explains that this (turning streaming off) causes issues
            # with af in multipoint (the issue is a crash because the camera does not send a picture).
            # if the live button was not pressed before multipoint acquisition is started, camera is not yet streaming, therefore crash -> start streaming when multipoint starts
            self.camera.start_streaming()

            # disable callback
            if self.camera.callback_is_enabled:
                self.camera_callback_was_enabled_before_multipoint = True
                self.camera.disable_callback()

            # run the acquisition
            self.timestamp_acquisition_started = time.time()
            # create a QThread object
            self.thread = QThread()
            # create a worker object
            self.multiPointWorker = MultiPointWorker(self,image_positions)
            # move the worker to the thread
            self.multiPointWorker.moveToThread(self.thread)
            # connect signals and slots
            self.thread.started.connect(self.multiPointWorker.run)
            self.multiPointWorker.finished.connect(self._on_acquisition_completed)
            self.multiPointWorker.finished.connect(self.multiPointWorker.deleteLater)
            self.multiPointWorker.finished.connect(self.thread.quit)
            self.multiPointWorker.image_to_display.connect(self.slot_image_to_display)
            self.multiPointWorker.image_to_display_multi.connect(self.slot_image_to_display_multi)
            self.multiPointWorker.spectrum_to_display.connect(self.slot_spectrum_to_display)
            self.multiPointWorker.signal_current_configuration.connect(self.slot_current_configuration,type=Qt.BlockingQueuedConnection)
            self.multiPointWorker.signal_register_current_fov.connect(self.slot_register_current_fov)
            # self.thread.finished.connect(self.thread.deleteLater)
            self.thread.finished.connect(self.thread.quit)
            # start the thread
            self.thread.start()

    def _on_acquisition_completed(self):
        # restore the previous selected mode
        self.signal_current_configuration.emit(self.configuration_before_running_multipoint)

        # re-enable callback
        if self.camera_callback_was_enabled_before_multipoint:
            self.camera.enable_callback()
            self.camera_callback_was_enabled_before_multipoint = False
        
        # re-enable live if it's previously on
        if self.liveController_was_live_before_multipoint:
            self.liveController.start_live()
        
        # emit the acquisition finished signal to enable the UI
        self.acquisitionFinished.emit()
        QApplication.processEvents()

    def request_abort_aquisition(self):
        self.abort_acqusition_requested = True

    def slot_image_to_display(self,image):
        self.image_to_display.emit(image)

    def slot_spectrum_to_display(self,data):
        self.spectrum_to_display.emit(data)

    def slot_image_to_display_multi(self,image,illumination_source):
        self.image_to_display_multi.emit(image,illumination_source)

    def slot_current_configuration(self,configuration):
        self.signal_current_configuration.emit(configuration)

    def slot_register_current_fov(self,x_mm,y_mm):
        self.signal_register_current_fov.emit(x_mm,y_mm)