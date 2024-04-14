# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import pandas as pd
import numpy as np
import time
import cv2
from control._def import *
import control.utils as utils

def multipoint_custom_script_entry(multiPointWorker,time_point,current_path,coordinate_id,coordiante_name,i,j):
    
    print( 'in custom script; t ' + str(multiPointWorker.time_point) + ', location ' + coordiante_name + ': ' +  str(i) + '_' + str(j) )

    # autofocus

    # if z location is included in the scan coordinates
    if multiPointWorker.use_scan_coordinates and multiPointWorker.scan_coordinates_mm.shape[1] == 3 :

        if multiPointWorker.do_autofocus:
            
            # autofocus for every FOV in the first scan and update the coordinates
            if multiPointWorker.time_point == 0:

                configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                config_AF = next((config for config in multiPointWorker.configurationManager.configurations if config.name == configuration_name_AF))
                multiPointWorker.signal_current_configuration.emit(config_AF)
                multiPointWorker.autofocusController.autofocus()
                multiPointWorker.autofocusController.wait_till_autofocus_has_completed()
                multiPointWorker.scan_coordinates_mm[coordinate_id,2] = multiPointWorker.navigationController.z_pos_mm

            # in subsequent scans, autofocus at the first FOV and offset the rest
            else:

                if coordinate_id == 0:

                    z0 = multiPointWorker.scan_coordinates_mm[0,2]
                    configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                    config_AF = next((config for config in multiPointWorker.configurationManager.configurations if config.name == configuration_name_AF))
                    multiPointWorker.signal_current_configuration.emit(config_AF)
                    multiPointWorker.autofocusController.autofocus()
                    multiPointWorker.autofocusController.wait_till_autofocus_has_completed()
                    multiPointWorker.scan_coordinates_mm[0,2] = multiPointWorker.navigationController.z_pos_mm
                    offset = multiPointWorker.scan_coordinates_mm[0,2] - z0
                    print('offset is ' + str(offset))
                    multiPointWorker.scan_coordinates_mm[1:,2] = multiPointWorker.scan_coordinates_mm[1:,2] + offset

                else:

                    pass


    # if z location is not included in the scan coordinates
    else:
        if multiPointWorker.do_reflection_af == False:
            # perform AF only if when not taking z stack or doing z stack from center
            if ( (multiPointWorker.NZ == 1) or Z_STACKING_CONFIG == 'FROM CENTER' ) and (multiPointWorker.do_autofocus) and (multiPointWorker.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
            # temporary: replace the above line with the line below to AF every FOV
            # if (multiPointWorker.NZ == 1) and (multiPointWorker.do_autofocus):
                configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                config_AF = next((config for config in multiPointWorker.configurationManager.configurations if config.name == configuration_name_AF))
                multiPointWorker.signal_current_configuration.emit(config_AF)
                multiPointWorker.autofocusController.autofocus()
                multiPointWorker.autofocusController.wait_till_autofocus_has_completed()
        else:
           # initialize laser autofocus
            if multiPointWorker.reflection_af_initialized==False:
                # initialize the reflection AF
                multiPointWorker.microscope.laserAutofocusController.initialize_auto()
                multiPointWorker.reflection_af_initialized = True
                # do contrast AF for the first FOV
                if multiPointWorker.do_autofocus and ( (multiPointWorker.NZ == 1) or Z_STACKING_CONFIG == 'FROM CENTER' ) :
                    configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
                    config_AF = next((config for config in multiPointWorker.configurationManager.configurations if config.name == configuration_name_AF))
                    multiPointWorker.signal_current_configuration.emit(config_AF)
                    multiPointWorker.autofocusController.autofocus()
                    multiPointWorker.autofocusController.wait_till_autofocus_has_completed()
                # set the current plane as reference
                multiPointWorker.microscope.laserAutofocusController.set_reference()
            else:
                multiPointWorker.microscope.laserAutofocusController.move_to_target(0)
                multiPointWorker.microscope.laserAutofocusController.move_to_target(0) # for stepper in open loop mode, repeat the operation to counter backlash 

    if (multiPointWorker.NZ > 1):
        # move to bottom of the z stack
        if Z_STACKING_CONFIG == 'FROM CENTER':
            multiPointWorker.navigationController.move_z_usteps(-multiPointWorker.deltaZ_usteps*round((multiPointWorker.NZ-1)/2))
            multiPointWorker.wait_till_operation_is_completed()
            time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
        # maneuver for achiving uniform step size and repeatability when using open-loop control
        multiPointWorker.navigationController.move_z_usteps(-160)
        multiPointWorker.wait_till_operation_is_completed()
        multiPointWorker.navigationController.move_z_usteps(160)
        multiPointWorker.wait_till_operation_is_completed()
        time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)

    # z-stack
    for k in range(multiPointWorker.NZ):
        
        file_ID = coordiante_name + str(i) + '_' + str(j if multiPointWorker.x_scan_direction==1 else multiPointWorker.NX-1-j) + '_' + str(k)
        # metadata = dict(x = multiPointWorker.navigationController.x_pos_mm, y = multiPointWorker.navigationController.y_pos_mm, z = multiPointWorker.navigationController.z_pos_mm)
        # metadata = json.dumps(metadata)

        # iterate through selected modes
        for config in multiPointWorker.selected_configurations:

            if 'USB Spectrometer' not in config.name:

                if time_point%10 != 0:

                    if 'Fluorescence' in config.name:
                        # only do fluorescence every 10th timepoint
                        continue

                # update the current configuration
                multiPointWorker.signal_current_configuration.emit(config)
                multiPointWorker.wait_till_operation_is_completed()
                # trigger acquisition (including turning on the illumination)
                if multiPointWorker.liveController.trigger_mode == TriggerMode.SOFTWARE:
                    multiPointWorker.liveController.turn_on_illumination()
                    multiPointWorker.wait_till_operation_is_completed()
                    multiPointWorker.camera.send_trigger()
                elif multiPointWorker.liveController.trigger_mode == TriggerMode.HARDWARE:
                    multiPointWorker.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=multiPointWorker.camera.exposure_time*1000)
                # read camera frame
                image = multiPointWorker.camera.read_frame()
                if image is None:
                    print('multiPointWorker.camera.read_frame() returned None')
                    continue
                # tunr of the illumination if using software trigger
                if multiPointWorker.liveController.trigger_mode == TriggerMode.SOFTWARE:
                    multiPointWorker.liveController.turn_off_illumination()
                # process the image -  @@@ to move to camera
                image = utils.crop_image(image,multiPointWorker.crop_width,multiPointWorker.crop_height)
                image = utils.rotate_and_flip_image(image,rotate_image_angle=multiPointWorker.camera.rotate_image_angle,flip_image=multiPointWorker.camera.flip_image)
                # multiPointWorker.image_to_display.emit(cv2.resize(image,(round(multiPointWorker.crop_width*multiPointWorker.display_resolution_scaling), round(multiPointWorker.crop_height*multiPointWorker.display_resolution_scaling)),cv2.INTER_LINEAR))
                image_to_display = utils.crop_image(image,round(multiPointWorker.crop_width*multiPointWorker.display_resolution_scaling), round(multiPointWorker.crop_height*multiPointWorker.display_resolution_scaling))
                multiPointWorker.image_to_display.emit(image_to_display)
                multiPointWorker.image_to_display_multi.emit(image_to_display,config.illumination_source)
                if image.dtype == np.uint16:
                    saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.tiff')
                    if multiPointWorker.camera.is_color:
                        if 'BF LED matrix' in config.name:
                            if MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
                                image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                            elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
                                image = image[:,:,1]
                    iio.imwrite(saving_path,image)
                else:
                    saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '.' + Acquisition.IMAGE_FORMAT)
                    if multiPointWorker.camera.is_color:
                        if 'BF LED matrix' in config.name:
                            if MULTIPOINT_BF_SAVING_OPTION == 'Raw':
                                image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                            elif MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
                                image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
                            elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
                                image = image[:,:,1]
                        else:
                            image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                    cv2.imwrite(saving_path,image)
                QApplication.processEvents()
            
            else:

                if multiPointWorker.usb_spectrometer != None:
                    for l in range(N_SPECTRUM_PER_POINT):
                        data = multiPointWorker.usb_spectrometer.read_spectrum()
                        multiPointWorker.spectrum_to_display.emit(data)
                        saving_path = os.path.join(current_path, file_ID + '_' + str(config.name).replace(' ','_') + '_' + str(l) + '.csv')
                        np.savetxt(saving_path,data,delimiter=',')

        # add the coordinate of the current location
        new_row = pd.DataFrame({'i':[i],'j':[multiPointWorker.NX-1-j],'k':[k],
                                'x (mm)':[multiPointWorker.navigationController.x_pos_mm],
                                'y (mm)':[multiPointWorker.navigationController.y_pos_mm],
                                'z (um)':[multiPointWorker.navigationController.z_pos_mm*1000]},
                                )
        multiPointWorker.coordinates_pd = pd.concat([multiPointWorker.coordinates_pd, new_row], ignore_index=True)

        # register the current fov in the navigationViewer 
        multiPointWorker.signal_register_current_fov.emit(multiPointWorker.navigationController.x_pos_mm,multiPointWorker.navigationController.y_pos_mm)

        # check if the acquisition should be aborted
        if multiPointWorker.multiPointController.abort_acqusition_requested:
            multiPointWorker.liveController.turn_off_illumination()
            multiPointWorker.navigationController.move_x_usteps(-multiPointWorker.dx_usteps)
            multiPointWorker.wait_till_operation_is_completed()
            multiPointWorker.navigationController.move_y_usteps(-multiPointWorker.dy_usteps)
            multiPointWorker.wait_till_operation_is_completed()
            if multiPointWorker.navigationController.get_pid_control_flag(2) is False:
                _usteps_to_clear_backlash = max(160,20*multiPointWorker.navigationController.z_microstepping)
                multiPointWorker.navigationController.move_z_usteps(-multiPointWorker.dz_usteps-_usteps_to_clear_backlash)
                multiPointWorker.wait_till_operation_is_completed()
                multiPointWorker.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                multiPointWorker.wait_till_operation_is_completed()
            else:
                multiPointWorker.navigationController.move_z_usteps(-multiPointWorker.dz_usteps)
                multiPointWorker.wait_till_operation_is_completed()

            multiPointWorker.coordinates_pd.to_csv(os.path.join(current_path,'coordinates.csv'),index=False,header=True)
            multiPointWorker.navigationController.enable_joystick_button_action = True
            return

        if multiPointWorker.NZ > 1:
            # move z
            if k < multiPointWorker.NZ - 1:
                multiPointWorker.navigationController.move_z_usteps(multiPointWorker.deltaZ_usteps)
                multiPointWorker.wait_till_operation_is_completed()
                time.sleep(SCAN_STABILIZATION_TIME_MS_Z/1000)
                multiPointWorker.dz_usteps = multiPointWorker.dz_usteps + multiPointWorker.deltaZ_usteps
    
    if multiPointWorker.NZ > 1:
        # move z back
        if Z_STACKING_CONFIG == 'FROM CENTER':
            if multiPointWorker.navigationController.get_pid_control_flag(2) is False:
                _usteps_to_clear_backlash = max(160,20*multiPointWorker.navigationController.z_microstepping)
                multiPointWorker.navigationController.move_z_usteps( -multiPointWorker.deltaZ_usteps*(multiPointWorker.NZ-1) + multiPointWorker.deltaZ_usteps*round((multiPointWorker.NZ-1)/2) - _usteps_to_clear_backlash)
                multiPointWorker.wait_till_operation_is_completed()
                multiPointWorker.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                multiPointWorker.wait_till_operation_is_completed()
            else:
                multiPointWorker.navigationController.move_z_usteps( -multiPointWorker.deltaZ_usteps*(multiPointWorker.NZ-1) + multiPointWorker.deltaZ_usteps*round((multiPointWorker.NZ-1)/2) )
                multiPointWorker.wait_till_operation_is_completed()

            multiPointWorker.dz_usteps = multiPointWorker.dz_usteps - multiPointWorker.deltaZ_usteps*(multiPointWorker.NZ-1) + multiPointWorker.deltaZ_usteps*round((multiPointWorker.NZ-1)/2)
        else:
            if multiPointWorker.navigationController.get_pid_control_flag(2) is False:
                _usteps_to_clear_backlash = max(160,20*multiPointWorker.navigationController.z_microstepping)
                multiPointWorker.navigationController.move_z_usteps(-multiPointWorker.deltaZ_usteps*(multiPointWorker.NZ-1) - _usteps_to_clear_backlash)
                multiPointWorker.wait_till_operation_is_completed()
                multiPointWorker.navigationController.move_z_usteps(_usteps_to_clear_backlash)
                multiPointWorker.wait_till_operation_is_completed()
            else:
                multiPointWorker.navigationController.move_z_usteps(-multiPointWorker.deltaZ_usteps*(multiPointWorker.NZ-1))
                multiPointWorker.wait_till_operation_is_completed()

            multiPointWorker.dz_usteps = multiPointWorker.dz_usteps - multiPointWorker.deltaZ_usteps*(multiPointWorker.NZ-1)

    # update FOV counter
    multiPointWorker.FOV_counter = multiPointWorker.FOV_counter + 1
