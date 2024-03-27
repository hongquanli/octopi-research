# set QT_API environment variable
import os 
import time
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

from control._def import *

# app specific libraries
import control.widgets as widgets


if CAMERA_TYPE == "Toupcam":
    try:
        import control.camera_toupcam as camera
    except:
        print("Problem importing Toupcam, defaulting to default camera")
        import control.camera as camera
elif CAMERA_TYPE == "FLIR":
    try:
        import control.camera_flir as camera
    except:
        print("Problem importing FLIR camera, defaulting to default camera")
        import control.camera as camera
else:
    import control.camera as camera

if FOCUS_CAMERA_TYPE == "Toupcam":
    try:
        import control.camera_toupcam as camera_fc
    except:
        print("Problem importing Toupcam for focus, defaulting to default camera")
        import control.camera as camera_fc
elif FOCUS_CAMERA_TYPE == "FLIR":
    try:
        import control.camera_flir as camera_fc
    except:
        print("Problem importing FLIR camera for focus, defaulting to default camera")
        import control.camera as camera_fc
else:
    import control.camera as camera_fc



import control.core as core
import control.microcontroller as microcontroller

import control.serial_peripherals as serial_peripherals

if SUPPORT_LASER_AUTOFOCUS:
    import control.core_displacement_measurement as core_displacement_measurement

import pyqtgraph.dockarea as dock
import time

SINGLE_WINDOW = True # set to False if use separate windows for display and control

class OctopiGUI(QMainWindow):

    # variables
    fps_software_trigger = 100

    def __init__(self, is_simulation = False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # load window
        if ENABLE_TRACKING:
            self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
            self.imageDisplayWindow.show_ROI_selector()
        else:
            self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True,show_LUT=True,autoLevels=True)
        self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow() 
        # self.imageDisplayWindow.show()
        # self.imageArrayDisplayWindow.show()

        # image display windows
        self.imageDisplayTabs = QTabWidget()
        self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
        self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")
        
        self.objectiveStore = core.ObjectiveStore()

        # load objects
        if is_simulation:
            if ENABLE_SPINNING_DISK_CONFOCAL:
                self.xlight = serial_peripherals.XLight_Simulation()
            if SUPPORT_LASER_AUTOFOCUS:
                self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                self.camera_focus = camera_fc.Camera_Simulation()
            else:
                self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            self.microcontroller = microcontroller.Microcontroller_Simulation()
        else:
            if ENABLE_SPINNING_DISK_CONFOCAL:
                self.xlight = serial_peripherals.XLight()
            try:
                if SUPPORT_LASER_AUTOFOCUS:
                    sn_camera_main = camera.get_sn_by_model(MAIN_CAMERA_MODEL)
                    sn_camera_focus = camera_fc.get_sn_by_model(FOCUS_CAMERA_MODEL)
                    self.camera = camera.Camera(sn=sn_camera_main,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                    self.camera.open()
                    self.camera_focus = camera_fc.Camera(sn=sn_camera_focus)
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
        time.sleep(0.5)

        # reinitialize motor drivers and DAC (in particular for V2.1 driver board where PG is not functional)
        self.microcontroller.initialize_drivers()
        time.sleep(0.5)

        # configure the actuators
        self.microcontroller.configure_actuators()

        self.configurationManager = core.ConfigurationManager(filename='./channel_configurations.xml')

        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
        self.navigationController = core.NavigationController(self.microcontroller, parent=self)
        self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController,is_for_wellplate=True)
        self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
        self.scanCoordinates = core.ScanCoordinates()
        self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
        if ENABLE_TRACKING:
            self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
        self.imageSaver = core.ImageSaver()
        self.imageDisplay = core.ImageDisplay()
        self.navigationViewer = core.NavigationViewer(sample=str(WELLPLATE_FORMAT)+' well plate')
        '''
        if HOMING_ENABLED_Z:
            # retract the objective
            self.navigationController.home_z()
            # wait for the operation to finish
            t0 = time.time()
            while self.microcontroller.is_busy():
                time.sleep(0.005)
                if time.time() - t0 > 10:
                    print('z homing timeout, the program will exit')
                    exit()
            print('objective retracted')

        if HOMING_ENABLED_Z and HOMING_ENABLED_X and HOMING_ENABLED_Y:
            # self.navigationController.set_x_limit_pos_mm(100)
            # self.navigationController.set_x_limit_neg_mm(-100)
            # self.navigationController.set_y_limit_pos_mm(100)
            # self.navigationController.set_y_limit_neg_mm(-100)
            # self.navigationController.home_xy() 
            # for the new design, need to home y before home x; x also needs to be at > + 10 mm when homing y
            self.navigationController.move_x(12)
            while self.microcontroller.is_busy(): # to do, add a blocking option move_x()
                time.sleep(0.005)

            self.navigationController.home_y()
            t0 = time.time()
            while self.microcontroller.is_busy():
                time.sleep(0.005)
                if time.time() - t0 > 10:
                    print('y homing timeout, the program will exit')
                    exit()

            self.navigationController.home_x()
            t0 = time.time()
            while self.microcontroller.is_busy():
                time.sleep(0.005)
                if time.time() - t0 > 10:
                    print('x homing timeout, the program will exit')
                    exit()

            print('xy homing completed')

            # move to (20 mm, 20 mm)
            self.navigationController.move_x(20)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
            self.navigationController.move_y(20)
            while self.microcontroller.is_busy():
                time.sleep(0.005)

            self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
            self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
            self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
            self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
            self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

        if HOMING_ENABLED_Z:
            # move the objective back
            self.navigationController.move_z(DEFAULT_Z_POS_MM)
            # wait for the operation to finish
            t0 = time.time() 
            while self.microcontroller.is_busy():
                time.sleep(0.005)
                if time.time() - t0 > 5:
                    print('z return timeout, the program will exit')
                    exit()
        '''

        # retract the objective
        self.navigationController.home_z()
        # wait for the operation to finish
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('z homing timeout, the program will exit')
                exit()
        print('objective retracted')

        # set encoder arguments
        # set axis pid control enable
        # only ENABLE_PID_X and HAS_ENCODER_X are both enable, can be enable to PID
        if HAS_ENCODER_X == True:
            self.navigationController.configure_encoder(0, (SCREW_PITCH_X_MM * 1000) / ENCODER_RESOLUTION_UM_X, ENCODER_FLIP_DIR_X)
            self.navigationController.set_pid_control_enable(0, ENABLE_PID_X)
        if HAS_ENCODER_Y == True:
            self.navigationController.configure_encoder(1, (SCREW_PITCH_Y_MM * 1000) / ENCODER_RESOLUTION_UM_Y, ENCODER_FLIP_DIR_Y)
            self.navigationController.set_pid_control_enable(1, ENABLE_PID_Y)
        if HAS_ENCODER_Z == True:
            self.navigationController.configure_encoder(2, (SCREW_PITCH_Z_MM * 1000) / ENCODER_RESOLUTION_UM_Z, ENCODER_FLIP_DIR_Z)
            self.navigationController.set_pid_control_enable(2, ENABLE_PID_Z)
        time.sleep(0.5)

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

        # set output's gains
        div = 1 if OUTPUT_GAINS.REFDIV is True else 0
        gains  = OUTPUT_GAINS.CHANNEL0_GAIN << 0 
        gains += OUTPUT_GAINS.CHANNEL1_GAIN << 1 
        gains += OUTPUT_GAINS.CHANNEL2_GAIN << 2 
        gains += OUTPUT_GAINS.CHANNEL3_GAIN << 3 
        gains += OUTPUT_GAINS.CHANNEL4_GAIN << 4 
        gains += OUTPUT_GAINS.CHANNEL5_GAIN << 5 
        gains += OUTPUT_GAINS.CHANNEL6_GAIN << 6 
        gains += OUTPUT_GAINS.CHANNEL7_GAIN << 7 
        self.microcontroller.configure_dac80508_refdiv_and_gain(div, gains)

        # set illumination intensity factor
        global ILLUMINATION_INTENSITY_FACTOR
        self.microcontroller.set_dac80508_scaling_factor_for_illumination(ILLUMINATION_INTENSITY_FACTOR)

        # open the camera
        # camera start streaming
        # self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
        # self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
        self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
        self.camera.set_callback(self.streamHandler.on_new_frame)
        self.camera.enable_callback()

        # load widgets
        if ENABLE_SPINNING_DISK_CONFOCAL:
            self.spinningDiskConfocalWidget = widgets.SpinningDiskConfocalWidget(self.xlight, self.configurationManager)

        if CAMERA_TYPE == "Toupcam":
            self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=True, include_camera_temperature_setting = True)
        else:
            self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera, include_gain_exposure_time=True, include_camera_temperature_setting=False)
        self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True,show_autolevel=True,autolevel=True)
        self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='384 well plate')
        self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
        self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
        self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
        if ENABLE_TRACKING:
            self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
        self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)
        self.multiPointWidget2 = widgets.MultiPointWidget2(self.navigationController,self.navigationViewer,self.multipointController,self.configurationManager)

        self.recordTabWidget = QTabWidget()
        if ENABLE_TRACKING:
            self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
        #self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
        self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint (Wellplate)")
        self.wellSelectionWidget = widgets.WellSelectionWidget(WELLPLATE_FORMAT)
        self.scanCoordinates.add_well_selector(self.wellSelectionWidget)

        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.recordTabWidget.addTab(self.multiPointWidget2, "Flexible Multipoint")
        if ENABLE_SPINNING_DISK_CONFOCAL:
            self.recordTabWidget.addTab(self.spinningDiskConfocalWidget,"Spinning Disk Confocal")

        # layout widgets
        layout = QVBoxLayout() #layout = QStackedLayout()
        #layout.addWidget(self.cameraSettingWidget)
        layout.addWidget(self.liveControlWidget)
        layout.addWidget(self.navigationWidget)
        if SHOW_DAC_CONTROL:
            layout.addWidget(self.dacControlWidget)
        layout.addWidget(self.autofocusWidget)
        layout.addWidget(self.recordTabWidget)
        layout.addWidget(self.navigationViewer)
        layout.addStretch()

        # transfer the layout to the central widget
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(layout)
        # self.centralWidget.setFixedSize(self.centralWidget.minimumSize())
        # self.centralWidget.setFixedWidth(self.centralWidget.minimumWidth())
        # self.centralWidget.setMaximumWidth(self.centralWidget.minimumWidth())
        self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())

        if SINGLE_WINDOW:
            dock_display = dock.Dock('Image Display', autoOrientation = False)
            dock_display.showTitleBar()
            dock_display.addWidget(self.imageDisplayTabs)
            dock_display.setStretch(x=100,y=100)
            dock_wellSelection = dock.Dock('Well Selector', autoOrientation = False)
            dock_wellSelection.showTitleBar()
            dock_wellSelection.addWidget(self.wellSelectionWidget)
            dock_wellSelection.setFixedHeight(dock_wellSelection.minimumSizeHint().height())
            dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
            # dock_controlPanel.showTitleBar()
            dock_controlPanel.addWidget(self.centralWidget)
            dock_controlPanel.setStretch(x=1,y=None)
            dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())
            main_dockArea = dock.DockArea()
            main_dockArea.addDock(dock_display)
            main_dockArea.addDock(dock_wellSelection,'bottom')
            main_dockArea.addDock(dock_controlPanel,'right')
            self.setCentralWidget(main_dockArea)
            desktopWidget = QDesktopWidget()
            height_min = 0.9*desktopWidget.height()
            width_min = 0.96*desktopWidget.width()
            self.setMinimumSize(int(width_min),int(height_min))
        else:
            self.setCentralWidget(self.centralWidget)
            self.tabbedImageDisplayWindow = QMainWindow()
            self.tabbedImageDisplayWindow.setCentralWidget(self.imageDisplayTabs)
            self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
            self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
            desktopWidget = QDesktopWidget()
            width = 0.96*desktopWidget.height()
            height = width
            self.tabbedImageDisplayWindow.setFixedSize(width,height)
            self.tabbedImageDisplayWindow.show()

        try:
            self.cswWindow = widgets.WrapperWindow(self.cameraSettingWidget)
        except AttributeError:
            pass

        try:
            self.cswfcWindow = widgets.WrapperWindow(self.cameraSettingWidget_focus_camera)
        except AttributeError:
            pass

        # make connections
        self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
        self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
        self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
        # self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
        self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image) # may connect streamHandler directly to imageDisplayWindow
        self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x)))
        self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x)))
        self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x)))
        if ENABLE_TRACKING:
            self.navigationController.signal_joystick_button_pressed.connect(self.trackingControlWidget.slot_joystick_button_pressed)
        else:
            self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)
        self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
        self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
        self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
        self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)

        self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
        self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
        self.liveControlWidget.update_camera_settings()
        self.liveControlWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel)

        # load vs scan position switching
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
        self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)

        # display the FOV in the viewer
        self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
        self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)

        # (double) click to move to a well
        self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)

        # camera
        self.camera.set_callback(self.streamHandler.on_new_frame)

        # laser autofocus
        if SUPPORT_LASER_AUTOFOCUS:

            # controllers
            self.configurationManager_focus_camera = core.ConfigurationManager(filename='./focus_camera_configurations.xml')
            self.streamHandler_focus_camera = core.StreamHandler()
            self.liveController_focus_camera = core.LiveController(self.camera_focus,self.microcontroller,self.configurationManager_focus_camera,control_illumination=False,for_displacement_measurement=True)
            self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
            self.imageDisplayWindow_focus = core.ImageDisplayWindow(draw_crosshairs=True)
            self.displacementMeasurementController = core_displacement_measurement.DisplacementMeasurementController()
            self.laserAutofocusController = core.LaserAutofocusController(self.microcontroller,self.camera_focus,self.liveController_focus_camera,self.navigationController,has_two_interfaces=HAS_TWO_INTERFACES,use_glass_top=USE_GLASS_TOP,look_for_cache=False)

            # camera
            self.camera_focus.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
            self.camera_focus.set_callback(self.streamHandler_focus_camera.on_new_frame)
            self.camera_focus.enable_callback()
            self.camera_focus.start_streaming()

            # widgets
            if FOCUS_CAMERA_TYPE == "Toupcam":
                self.cameraSettingWidget_focus_camera = widgets.CameraSettingsWidget(self.camera_focus,include_gain_exposure_time=True, include_camera_temperature_setting = True)
            else:
                self.cameraSettingWidget_focus_camera = widgets.CameraSettingsWidget(self.camera_focus, include_gain_exposure_time=True, include_camera_temperature_setting=False)

            self.liveControlWidget_focus_camera = widgets.LiveControlWidget(self.streamHandler_focus_camera,self.liveController_focus_camera,self.configurationManager_focus_camera,show_display_options=True)
            self.waveformDisplay = widgets.WaveformDisplay(N=1000,include_x=True,include_y=False)
            self.displacementMeasurementWidget = widgets.DisplacementMeasurementWidget(self.displacementMeasurementController,self.waveformDisplay)
            self.laserAutofocusControlWidget = widgets.LaserAutofocusControlWidget(self.laserAutofocusController)

            self.recordTabWidget.addTab(self.laserAutofocusControlWidget, "Laser Autofocus Control")

            dock_laserfocus_image_display = dock.Dock('Focus Camera Image Display', autoOrientation = False)
            dock_laserfocus_image_display.showTitleBar()
            dock_laserfocus_image_display.addWidget(self.imageDisplayWindow_focus.widget)
            dock_laserfocus_image_display.setStretch(x=100,y=100)

            dock_laserfocus_liveController = dock.Dock('Focus Camera Controller', autoOrientation = False)
            dock_laserfocus_liveController.showTitleBar()
            dock_laserfocus_liveController.addWidget(self.liveControlWidget_focus_camera)
            dock_laserfocus_liveController.setStretch(x=100,y=100)
            # dock_laserfocus_liveController.setFixedHeight(self.liveControlWidget_focus_camera.minimumSizeHint().height())
            dock_laserfocus_liveController.setFixedWidth(self.liveControlWidget_focus_camera.minimumSizeHint().width())

            dock_waveform = dock.Dock('Displacement Measurement', autoOrientation = False)
            dock_waveform.showTitleBar()
            dock_waveform.addWidget(self.waveformDisplay)
            dock_waveform.setStretch(x=100,y=40)

            dock_displayMeasurement =  dock.Dock('Displacement Measurement Control', autoOrientation = False)
            dock_displayMeasurement.showTitleBar()
            dock_displayMeasurement.addWidget(self.displacementMeasurementWidget)
            dock_displayMeasurement.setStretch(x=100,y=40)
            dock_displayMeasurement.setFixedWidth(self.displacementMeasurementWidget.minimumSizeHint().width())

            laserfocus_dockArea = dock.DockArea()
            laserfocus_dockArea.addDock(dock_laserfocus_image_display)
            laserfocus_dockArea.addDock(dock_laserfocus_liveController,'right',relativeTo=dock_laserfocus_image_display)
            if SHOW_LEGACY_DISPLACEMENT_MEASUREMENT_WINDOWS:
                laserfocus_dockArea.addDock(dock_waveform,'bottom',relativeTo=dock_laserfocus_liveController)
                laserfocus_dockArea.addDock(dock_displayMeasurement,'bottom',relativeTo=dock_waveform)

            # self.imageDisplayWindow_focus.widget
            self.imageDisplayTabs.addTab(laserfocus_dockArea,"Laser-based Focus")

            # connections
            self.liveControlWidget_focus_camera.signal_newExposureTime.connect(self.cameraSettingWidget_focus_camera.set_exposure_time)
            self.liveControlWidget_focus_camera.signal_newAnalogGain.connect(self.cameraSettingWidget_focus_camera.set_analog_gain)
            self.liveControlWidget_focus_camera.update_camera_settings()

            self.streamHandler_focus_camera.signal_new_frame_received.connect(self.liveController_focus_camera.on_new_frame)
            self.streamHandler_focus_camera.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

            self.streamHandler_focus_camera.image_to_display.connect(self.displacementMeasurementController.update_measurement)
            self.displacementMeasurementController.signal_plots.connect(self.waveformDisplay.plot)
            self.displacementMeasurementController.signal_readings.connect(self.displacementMeasurementWidget.display_readings)
            self.laserAutofocusController.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

        self.imageDisplayWindow.image_click_coordinates.connect(self.navigationController.move_from_click)

        self.navigationController.move_to_cached_position()

    def closeEvent(self, event):

        self.navigationController.cache_current_position()

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

        self.navigationController.turnoff_axis_pid_control()

        self.liveController.stop_live()
        self.camera.close()
        self.imageSaver.close()
        self.imageDisplay.close()
        if not SINGLE_WINDOW:
            self.imageDisplayWindow.close()
            self.imageArrayDisplayWindow.close()
            self.tabbedImageDisplayWindow.close()
        if SUPPORT_LASER_AUTOFOCUS:
            self.liveController_focus_camera.stop_live()
            self.camera_focus.close()
            self.imageDisplayWindow_focus.close()
        self.microcontroller.close()

        try:
            self.cswWindow.closeForReal(event)
        except AttributeError:
            pass

        try:
            self.cswfcWindow.closeForReal(event)
        except AttributeError:
            pass

        event.accept()
