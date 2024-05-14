# set QT_API environment variable
import os 
import sys
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
from control._def import *

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
            self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
        if SHOW_TILED_PREVIEW:
            self.imageDisplayWindow_scan_preview = core.ImageDisplayWindow(draw_crosshairs=True)
        self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow() 
        # self.imageDisplayWindow.show()
        # self.imageArrayDisplayWindow.show()

        # image display windows
        self.imageDisplayTabs = QTabWidget()
        self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
        self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")
        if SHOW_TILED_PREVIEW:
            self.imageDisplayTabs.addTab(self.imageDisplayWindow_scan_preview.widget, "Tiled Preview")

        # load objects
        if is_simulation:
            self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            self.microcontroller = microcontroller.Microcontroller_Simulation()
        else:
            try:
                self.camera = camera.Camera(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                self.camera.open()
            except:
                self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                self.camera.open()
                print('! camera not detected, using simulated camera !')
            try:
                self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)
            except:
                print('! Microcontroller not detected, using simulated microcontroller !')
                self.microcontroller = microcontroller.Microcontroller_Simulation()

        # reset the MCU
        self.microcontroller.reset()

        # reinitialize motor drivers and DAC (in particular for V2.1 driver board where PG is not functional)
        self.microcontroller.initialize_drivers()

        # configure the actuators
        self.microcontroller.configure_actuators()

        self.configurationManager = core.ConfigurationManager()
        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
        self.navigationController = core.NavigationController(self.microcontroller, parent=self)
        self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
        self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
        self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager)
        if ENABLE_TRACKING:
            self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
        self.imageSaver = core.ImageSaver()
        self.imageDisplay = core.ImageDisplay()
        self.navigationViewer = core.NavigationViewer()

        # retract the objective
        self.navigationController.home_z()
        # wait for the operation to finish
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                print('z homing timeout, the program will exit')
                sys.exit(1)
        print('objective retracted')

        # set encoder arguments
        # set axis pid control enable
        # only ENABLE_PID_X and HAS_ENCODER_X are both enable, can be enable to PID
        if HAS_ENCODER_X == True:
            self.navigationController.set_axis_PID_arguments(0, PID_P_X, PID_I_X, PID_D_X)
            self.navigationController.configure_encoder(0, (SCREW_PITCH_X_MM * 1000) / ENCODER_RESOLUTION_UM_X, ENCODER_FLIP_DIR_X)
            self.navigationController.set_pid_control_enable(0, ENABLE_PID_X)
        if HAS_ENCODER_Y == True:
            self.navigationController.set_axis_PID_arguments(1, PID_P_Y, PID_I_Y, PID_D_Y)
            self.navigationController.configure_encoder(1, (SCREW_PITCH_Y_MM * 1000) / ENCODER_RESOLUTION_UM_Y, ENCODER_FLIP_DIR_Y)
            self.navigationController.set_pid_control_enable(1, ENABLE_PID_Y)
        if HAS_ENCODER_Z == True:
            self.navigationController.set_axis_PID_arguments(2, PID_P_Z, PID_I_Z, PID_D_Z)
            self.navigationController.configure_encoder(2, (SCREW_PITCH_Z_MM * 1000) / ENCODER_RESOLUTION_UM_Z, ENCODER_FLIP_DIR_Z)
            self.navigationController.set_pid_control_enable(2, ENABLE_PID_Z)

        time.sleep(0.5)

        # homing, set zero and set software limit
        self.navigationController.set_x_limit_pos_mm(100)
        self.navigationController.set_x_limit_neg_mm(-100)
        self.navigationController.set_y_limit_pos_mm(100)
        self.navigationController.set_y_limit_neg_mm(-100)
        print('start homing')
        self.slidePositionController.move_to_slide_scanning_position()
        while self.slidePositionController.slide_scanning_position_reached == False:
            time.sleep(0.005)
        print('homing finished')
        self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
        self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
        self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
        self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)

        # set piezo arguments
        if ENABLE_OBJECTIVE_PIEZO is True:
            if PIEZO_CONTROL_VOLTAGE_RANGE == 5:
                OUTPUT_GAINS.CHANNEL7_GAIN = True
            else:
                OUTPUT_GAINS.CHANNEL7_GAIN = False

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

        # set software limit
        self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
        self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
        self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
        self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
        self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

        # open the camera
        # camera start streaming
        # self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
        # self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
        self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
        self.camera.set_callback(self.streamHandler.on_new_frame)
        self.camera.enable_callback()

        # load widgets
        self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
        self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True)
        self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='malaria')
        self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
        self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
        self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
        self.focusMapWidget = widgets.FocusMapWidget(self.autofocusController)
        if ENABLE_TRACKING:
            self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
        self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)

        self.recordTabWidget = QTabWidget()
        if ENABLE_TRACKING:
            self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
        #self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
        self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")
        self.recordTabWidget.addTab(self.focusMapWidget, "Contrast Focus Map")

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
            dock_display.setStretch(x=100,y=None)
            dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
            # dock_controlPanel.showTitleBar()
            dock_controlPanel.addWidget(self.centralWidget)
            dock_controlPanel.setStretch(x=1,y=None)
            dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())
            main_dockArea = dock.DockArea()
            main_dockArea.addDock(dock_display)
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

        if SHOW_TILED_PREVIEW:
            self.multipointController.image_to_display_tiled_preview.connect(self.imageDisplayWindow_scan_preview.display_image)
            self.imageDisplayWindow_scan_preview.image_click_coordinates.connect(self.navigationController.scan_preview_move_from_click)

        self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
        self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
        self.liveControlWidget.update_camera_settings()

        self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
        self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)

        self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
        self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)
        
        self.imageDisplayWindow.image_click_coordinates.connect(self.navigationController.move_from_click)


        self.navigationController.move_to_cached_position()

    def closeEvent(self, event):
        self.navigationController.cache_current_position()
        event.accept()
        # self.softwareTriggerGenerator.stop() @@@ => 
        self.navigationController.home()
        self.navigationController.turnoff_axis_pid_control()

        self.liveController.stop_live()
        self.camera.close()
        self.imageSaver.close()
        self.imageDisplay.close()
        if not SINGLE_WINDOW:
            self.imageDisplayWindow.close()
            self.imageArrayDisplayWindow.close()
            self.tabbedImageDisplayWindow.close()
        self.microcontroller.close()
