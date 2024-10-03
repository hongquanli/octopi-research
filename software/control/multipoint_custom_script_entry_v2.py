import os
import time
import cv2
import numpy as np
import pandas as pd
import imageio as iio
from control._def import *
import control.utils as utils

BACKLASH_USTEPS = 160

def multipoint_custom_script_entry(worker, current_path, region_id, fov, i, j):
    print(f'In custom script; t={worker.time_point}, region={region_id}, fov={fov}: {i}_{j}')
    
    perform_autofocus(worker, region_id)
    prepare_z_stack(worker)
    acquire_z_stack(worker, current_path, region_id, fov, i, j)

def perform_autofocus(worker, region_id):
    if worker.do_reflection_af:
        perform_laser_autofocus(worker)
    else:
        perform_contrast_autofocus(worker, region_id)

def perform_laser_autofocus(worker):
    if not worker.microscope.laserAutofocusController.is_initialized:
        initialize_laser_autofocus(worker)
    else:
        worker.microscope.laserAutofocusController.move_to_target(0)
        if worker.navigationController.get_pid_control_flag(2) is False:
            worker.microscope.laserAutofocusController.move_to_target(0)

def initialize_laser_autofocus(worker):
    print("Initializing reflection AF")
    worker.microscope.laserAutofocusController.initialize_auto()
    if worker.do_autofocus and ((worker.NZ == 1) or worker.z_stacking_config == 'FROM CENTER'):
        perform_contrast_autofocus(worker, 0)
    worker.microscope.laserAutofocusController.set_reference()

def perform_contrast_autofocus(worker, region_id):
    if ((worker.NZ == 1 or worker.z_stacking_config == 'FROM CENTER') 
        and worker.do_autofocus 
        and (worker.af_fov_count % Acquisition.NUMBER_OF_FOVS_PER_AF == 0)):
        config_AF = get_autofocus_config(worker)
        worker.signal_current_configuration.emit(config_AF)
        worker.autofocusController.autofocus()
        worker.autofocusController.wait_till_autofocus_has_completed()
        if len(worker.scan_coordinates_mm[region_id]) == 3:
            worker.scan_coordinates_mm[region_id][2] = worker.navigationController.z_pos_mm
            update_widget_z_level(worker, region_id)

def update_widget_z_level(worker, region_id):
    if worker.coordinate_dict is not None:
        worker.microscope.multiPointWidgetGrid.update_region_z_level(region_id, worker.navigationController.z_pos_mm)
    elif worker.multiPointController.location_list is not None:
        try:
            worker.microscope.multiPointWidget2._update_z(region_id, worker.navigationController.z_pos_mm)
        except:
            print("Failed to update flexible widget z")
        try:
            worker.microscope.multiPointWidgetGrid.update_region_z_level(region_id, worker.navigationController.z_pos_mm)
        except:
            print("Failed to update grid widget z")

def get_autofocus_config(worker):
    configuration_name_AF = MULTIPOINT_AUTOFOCUS_CHANNEL
    return next((config for config in worker.configurationManager.configurations if config.name == configuration_name_AF))

def prepare_z_stack(worker):
    if worker.NZ > 1:
        if worker.z_stacking_config == 'FROM CENTER':
            worker.navigationController.move_z_usteps(-worker.deltaZ_usteps * round((worker.NZ - 1) / 2))
            worker.wait_till_operation_is_completed()
            time.sleep(SCAN_STABILIZATION_TIME_MS_Z / 1000)
        worker.navigationController.move_z_usteps(-BACKLASH_USTEPS)
        worker.wait_till_operation_is_completed()
        worker.navigationController.move_z_usteps(BACKLASH_USTEPS)
        worker.wait_till_operation_is_completed()
        time.sleep(SCAN_STABILIZATION_TIME_MS_Z / 1000)

def acquire_z_stack(worker, current_path, region_id, fov, i, j):
    total_images = worker.NZ * len(worker.selected_configurations)
    for z_level in range(worker.NZ):
        acquire_single_z_plane(worker, current_path, region_id, fov, i, j, z_level, total_images)
        if z_level < worker.NZ - 1:
            move_to_next_z_plane(worker)
    
    if worker.NZ > 1:
        move_z_stack_back(worker)
    
    worker.af_fov_count += 1

def acquire_single_z_plane(worker, current_path, region_id, fov, i, j, z_level, total_images):
    if i is not None and j is not None:
        file_ID = f"{region_id}_{i}_{j}_{z_level}"
    else:
        file_ID = f"{region_id}_{fov}_{z_level}"

    current_round_images = {}
    for config_idx, config in enumerate(worker.selected_configurations):
        acquire_image_for_configuration(worker, config, file_ID, current_path, current_round_images, i, j, z_level)
        
        # Calculate current image number and emit progress signal
        current_image = (fov * total_images) + (z_level * len(worker.selected_configurations)) + config_idx + 1
        worker.signal_region_progress.emit(current_image, worker.total_scans)

    if worker.multiPointController.do_fluorescence_rtp:
        run_real_time_processing(worker, current_round_images, i, j, z_level)

    update_coordinates_dataframe(worker, region_id, z_level, fov, i, j)

    # Check for abort after each z-plane
    if check_for_abort(worker, current_path, region_id):
        return

def acquire_image_for_configuration(worker, config, file_ID, current_path, current_round_images, i, j, z_level):
    worker.handle_z_offset(config, True)  # Added this line to perform config z-offset

    if 'USB Spectrometer' not in config.name and 'RGB' not in config.name:
        acquire_camera_image(worker, config, file_ID, current_path, current_round_images, i, j, z_level)
    elif 'RGB' in config.name:
        acquire_rgb_image(worker, config, file_ID, current_path, current_round_images, i, j, z_level)
    else:
        acquire_spectrometer_data(worker, config, file_ID, current_path, i, j, z_level)

    worker.handle_z_offset(config, False)  # Added this line to undo z-offset

def acquire_camera_image(worker, config, file_ID, current_path, current_round_images, i, j, z_level):
    worker.signal_current_configuration.emit(config)
    worker.wait_till_operation_is_completed()

    image = capture_image(worker, config)
    if image is not None:
        process_and_save_image(worker, image, file_ID, config, current_path, current_round_images, i, j, z_level)

def capture_image(worker, config):
    if worker.liveController.trigger_mode == TriggerMode.SOFTWARE:
        return capture_image_software_trigger(worker)
    elif worker.liveController.trigger_mode == TriggerMode.HARDWARE:
        return capture_image_hardware_trigger(worker, config)
    else:
        return worker.camera.read_frame()

def capture_image_software_trigger(worker):
    worker.liveController.turn_on_illumination()
    worker.wait_till_operation_is_completed()
    worker.camera.send_trigger()
    image = worker.camera.read_frame()
    worker.liveController.turn_off_illumination()
    return image

def capture_image_hardware_trigger(worker, config):
    if 'Fluorescence' in config.name and ENABLE_NL5 and NL5_USE_DOUT:
        worker.camera.image_is_ready = False
        worker.microscope.nl5.start_acquisition()
        return worker.camera.read_frame(reset_image_ready_flag=False)
    else:
        worker.microcontroller.send_hardware_trigger(control_illumination=True, illumination_on_time_us=worker.camera.exposure_time * 1000)
        return worker.camera.read_frame()

def process_and_save_image(worker, image, file_ID, config, current_path, current_round_images, i, j, z_level):
    image = utils.crop_image(image, worker.crop_width, worker.crop_height)
    image = utils.rotate_and_flip_image(image, rotate_image_angle=worker.camera.rotate_image_angle, flip_image=worker.camera.flip_image)
    image_to_display = utils.crop_image(image, round(worker.crop_width * worker.display_resolution_scaling), round(worker.crop_height * worker.display_resolution_scaling))
    worker.image_to_display.emit(image_to_display)
    worker.image_to_display_multi.emit(image_to_display, config.illumination_source)

    save_image(worker, image, file_ID, config, current_path)
    worker.update_napari(image, config.name, i, j, z_level)

    current_round_images[config.name] = np.copy(image)

def save_image(worker, image, file_ID, config, current_path):
    if image.dtype == np.uint16:
        saving_path = os.path.join(current_path, f"{file_ID}_{config.name.replace(' ', '_')}.tiff")
    else:
        saving_path = os.path.join(current_path, f"{file_ID}_{config.name.replace(' ', '_')}.{Acquisition.IMAGE_FORMAT}")
    
    if worker.camera.is_color and 'BF LED matrix' in config.name:
        image = process_color_image(image)
    
    iio.imwrite(saving_path, image)

def process_color_image(image):
    if MULTIPOINT_BF_SAVING_OPTION == 'RGB2GRAY':
        return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    elif MULTIPOINT_BF_SAVING_OPTION == 'Green Channel Only':
        return image[:, :, 1]
    return image

def acquire_rgb_image(worker, config, file_ID, current_path, current_round_images, i, j, z_level):
    rgb_channels = ['BF LED matrix full_R', 'BF LED matrix full_G', 'BF LED matrix full_B']
    images = {}

    for channel_config in worker.configurationManager.configurations:
        if channel_config.name in rgb_channels:
            worker.signal_current_configuration.emit(channel_config)
            worker.wait_till_operation_is_completed()
            image = capture_image(worker, channel_config)
            if image is not None:
                image = utils.crop_image(image, worker.crop_width, worker.crop_height)
                image = utils.rotate_and_flip_image(image, rotate_image_angle=worker.camera.rotate_image_angle, flip_image=worker.camera.flip_image)
                images[channel_config.name] = np.copy(image)

    if images:
        process_and_save_rgb_image(worker, images, file_ID, config, current_path, current_round_images, i, j, z_level)

def process_and_save_rgb_image(worker, images, file_ID, config, current_path, current_round_images, i, j, z_level):
    if len(images['BF LED matrix full_R'].shape) == 3:
        handle_rgb_channels(worker, images, file_ID, current_path, config, i, j, z_level)
    else:
        construct_rgb_image(worker, images, file_ID, current_path, config, i, j, z_level)

def handle_rgb_channels(worker, images, file_ID, current_path, config, i, j, z_level):
    for channel in ['BF LED matrix full_R', 'BF LED matrix full_G', 'BF LED matrix full_B']:
        image_to_display = utils.crop_image(images[channel], round(worker.crop_width * worker.display_resolution_scaling), round(worker.crop_height * worker.display_resolution_scaling))
        worker.image_to_display.emit(image_to_display)
        worker.image_to_display_multi.emit(image_to_display, config.illumination_source)
        worker.update_napari(images[channel], channel, i, j, z_level)
        file_name = f"{file_ID}_{channel.replace(' ', '_')}{'.tiff' if images[channel].dtype == np.uint16 else '.' + Acquisition.IMAGE_FORMAT}"
        iio.imwrite(os.path.join(current_path, file_name), images[channel])

def construct_rgb_image(worker, images, file_ID, current_path, config, i, j, z_level):
    rgb_image = np.zeros((*images['BF LED matrix full_R'].shape, 3), dtype=images['BF LED matrix full_R'].dtype)
    rgb_image[:, :, 0] = images['BF LED matrix full_R']
    rgb_image[:, :, 1] = images['BF LED matrix full_G']
    rgb_image[:, :, 2] = images['BF LED matrix full_B']

    image_to_display = utils.crop_image(rgb_image, round(worker.crop_width * worker.display_resolution_scaling), round(worker.crop_height * worker.display_resolution_scaling))
    worker.image_to_display.emit(image_to_display)
    worker.image_to_display_multi.emit(image_to_display, config.illumination_source)

    worker.update_napari(rgb_image, config.name, i, j, z_level)

    file_name = f"{file_ID}_BF_LED_matrix_full_RGB{'.tiff' if rgb_image.dtype == np.uint16 else '.' + Acquisition.IMAGE_FORMAT}"
    iio.imwrite(os.path.join(current_path, file_name), rgb_image)

def acquire_spectrometer_data(worker, config, file_ID, current_path, i, j, z_level):
    if worker.usb_spectrometer is not None:
        for l in range(N_SPECTRUM_PER_POINT):
            data = worker.usb_spectrometer.read_spectrum()
            worker.spectrum_to_display.emit(data)
            saving_path = os.path.join(current_path, f"{file_ID}_{config.name.replace(' ', '_')}_{l}.csv")
            np.savetxt(saving_path, data, delimiter=',')

def update_coordinates_dataframe(worker, region_id, z_level, fov, i, j):
    if i is None or j is None:
        worker.update_coordinates_dataframe(region_id, z_level, fov)
    else:
        worker.update_coordinates_dataframe(region_id, z_level, i=i, j=j)
    worker.signal_register_current_fov.emit(worker.navigationController.x_pos_mm, worker.navigationController.y_pos_mm)

def run_real_time_processing(worker, current_round_images, i, j, z_level):
    acquired_image_configs = list(current_round_images.keys())
    if 'BF LED matrix left half' in current_round_images and 'BF LED matrix right half' in current_round_images and 'Fluorescence 405 nm Ex' in current_round_images:
        try:
            print("real time processing", worker.count_rtp)
            if (worker.microscope.model is None) or (worker.microscope.device is None) or (worker.microscope.classification_th is None) or (worker.microscope.dataHandler is None):
                raise AttributeError('microscope missing model, device, classification_th, and/or dataHandler')
            I_fluorescence = current_round_images['Fluorescence 405 nm Ex']
            I_left = current_round_images['BF LED matrix left half']
            I_right = current_round_images['BF LED matrix right half']
            if len(I_left.shape) == 3:
                I_left = cv2.cvtColor(I_left, cv2.COLOR_RGB2GRAY)
            if len(I_right.shape) == 3:
                I_right = cv2.cvtColor(I_right, cv2.COLOR_RGB2GRAY)
            malaria_rtp(I_fluorescence, I_left, I_right, i, j, z_level, worker,
                        classification_test_mode=worker.microscope.classification_test_mode,
                        sort_during_multipoint=SORT_DURING_MULTIPOINT,
                        disp_th_during_multipoint=DISP_TH_DURING_MULTIPOINT)
            worker.count_rtp += 1
        except AttributeError as e:
            print(repr(e))

def move_to_next_z_plane(worker):
    if worker.use_piezo:
        worker.z_piezo_um += worker.deltaZ * 1000
        dac = int(65535 * (worker.z_piezo_um / OBJECTIVE_PIEZO_RANGE_UM))
        worker.navigationController.microcontroller.analog_write_onboard_DAC(7, dac)
        if worker.liveController.trigger_mode == TriggerMode.SOFTWARE:
            time.sleep(MULTIPOINT_PIEZO_DELAY_MS / 1000)
        if MULTIPOINT_PIEZO_UPDATE_DISPLAY:
            worker.signal_z_piezo_um.emit(worker.z_piezo_um)
    else:
        worker.navigationController.move_z_usteps(worker.deltaZ_usteps)
        worker.wait_till_operation_is_completed()
        time.sleep(SCAN_STABILIZATION_TIME_MS_Z / 1000)
        worker.dz_usteps = worker.dz_usteps + worker.deltaZ_usteps

def move_z_stack_back(worker):
    if worker.use_piezo:
        worker.z_piezo_um = OBJECTIVE_PIEZO_HOME_UM
        dac = int(65535 * (worker.z_piezo_um / OBJECTIVE_PIEZO_RANGE_UM))
        worker.navigationController.microcontroller.analog_write_onboard_DAC(7, dac)
        if worker.liveController.trigger_mode == TriggerMode.SOFTWARE:
            time.sleep(MULTIPOINT_PIEZO_DELAY_MS / 1000)
        if MULTIPOINT_PIEZO_UPDATE_DISPLAY:
            worker.signal_z_piezo_um.emit(worker.z_piezo_um)
    else:
        if worker.z_stacking_config == 'FROM CENTER':
            move_z_stack_back_from_center(worker)
        else:
            move_z_stack_back_from_top(worker)

def move_z_stack_back_from_center(worker):
    _usteps_to_clear_backlash = max(BACKLASH_USTEPS, 20 * worker.navigationController.z_microstepping)
    if worker.navigationController.get_pid_control_flag(2) is False:
        worker.navigationController.move_z_usteps(-worker.deltaZ_usteps * (worker.NZ - 1) + worker.deltaZ_usteps * round((worker.NZ - 1) / 2) - _usteps_to_clear_backlash)
        worker.wait_till_operation_is_completed()
        worker.navigationController.move_z_usteps(_usteps_to_clear_backlash)
        worker.wait_till_operation_is_completed()
    else:
        worker.navigationController.move_z_usteps(-worker.deltaZ_usteps * (worker.NZ - 1) + worker.deltaZ_usteps * round((worker.NZ - 1) / 2))
        worker.wait_till_operation_is_completed()
    worker.dz_usteps = worker.dz_usteps - worker.deltaZ_usteps * (worker.NZ - 1) + worker.deltaZ_usteps * round((worker.NZ - 1) / 2)

def move_z_stack_back_from_top(worker):
    _usteps_to_clear_backlash = max(BACKLASH_USTEPS, 20 * worker.navigationController.z_microstepping)
    if worker.navigationController.get_pid_control_flag(2) is False:
        worker.navigationController.move_z_usteps(-worker.deltaZ_usteps * (worker.NZ - 1) - _usteps_to_clear_backlash)
        worker.wait_till_operation_is_completed()
        worker.navigationController.move_z_usteps(_usteps_to_clear_backlash)
        worker.wait_till_operation_is_completed()
    else:
        worker.navigationController.move_z_usteps(-worker.deltaZ_usteps * (worker.NZ - 1))
        worker.wait_till_operation_is_completed()
    worker.dz_usteps = worker.dz_usteps - worker.deltaZ_usteps * (worker.NZ - 1)

def check_for_abort(worker, current_path, region_id):
    if worker.multiPointController.abort_acqusition_requested:
        worker.handle_acquisition_abort(current_path, region_id)
        return True
    return False

def move_stage_back(worker):
    worker.navigationController.move_x_usteps(-worker.dx_usteps)
    worker.wait_till_operation_is_completed()
    worker.navigationController.move_y_usteps(-worker.dy_usteps)
    worker.wait_till_operation_is_completed()
    move_z_back(worker)

def move_z_back(worker):
    if worker.navigationController.get_pid_control_flag(2) is False:
        _usteps_to_clear_backlash = max(BACKLASH_USTEPS, 20 * worker.navigationController.z_microstepping)
        worker.navigationController.move_z_usteps(-worker.dz_usteps - _usteps_to_clear_backlash)
        worker.wait_till_operation_is_completed()
        worker.navigationController.move_z_usteps(_usteps_to_clear_backlash)
        worker.wait_till_operation_is_completed()
    else:
        worker.navigationController.move_z_usteps(-worker.dz_usteps)
        worker.wait_till_operation_is_completed()

# This function is called by the MultiPointWorker's run_single_time_point method
def run_custom_multipoint(worker, current_path, region_id, fov, i, j):
    multipoint_custom_script_entry(worker, current_path, region_id, fov, i, j)