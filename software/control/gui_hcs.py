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

from control._def import *

# app specific libraries
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
elif CAMERA_TYPE == "Hamamatsu":
    try:
        import control.camera_hamamatsu as camera
    except:
        print("Problem importing Hamamatsu camera, defaulting to default camera")
        import control.camera as camera
elif CAMERA_TYPE == "iDS":
    try:
        import control.camera_ids as camera
    except:
        print("Problem importing iDS camera, defaulting to default camera")
        import control.camera as camera
elif CAMERA_TYPE == "Tucsen":
    try:
        import control.camera_tucsen as camera
    except:
        print("Problem importing Tucsen camera, defaulting to default camera")
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
import control.widgets as widgets
import control.serial_peripherals as serial_peripherals

if ENABLE_STITCHER:
    import control.stitcher as stitcher

if SUPPORT_LASER_AUTOFOCUS:
    import control.core_displacement_measurement as core_displacement_measurement

import pyqtgraph.dockarea as dock
import serial
import time

SINGLE_WINDOW = True # set to False if use separate windows for display and control

class OctopiGUI(QMainWindow):

    # variables
    fps_software_trigger = 100

    def __init__(self, is_simulation = False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # load objects
        if is_simulation:
            if ENABLE_SPINNING_DISK_CONFOCAL:
                self.xlight = serial_peripherals.XLight_Simulation()
            if ENABLE_NL5:
                import control.NL5 as NL5
                self.nl5 = NL5.NL5_Simulation()
            if ENABLE_CELLX:
                self.cellx = serial_peripherals.CellX_Simulation()
            if SUPPORT_LASER_AUTOFOCUS:
                self.camera_focus = camera_fc.Camera_Simulation()
            self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            self.camera.set_pixel_format(DEFAULT_PIXEL_FORMAT)

            if USE_ZABER_EMISSION_FILTER_WHEEL:
                self.emission_filter_wheel = serial_peripherals.FilterController_Simulation(115200, 8, serial.PARITY_NONE, serial.STOPBITS_ONE)
            if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
                self.emission_filter_wheel = serial_peripherals.Optospin_Simulation(SN=None)

            self.microcontroller = microcontroller.Microcontroller_Simulation()
        else:
            if ENABLE_SPINNING_DISK_CONFOCAL:
                self.xlight = serial_peripherals.XLight(XLIGHT_SERIAL_NUMBER,XLIGHT_SLEEP_TIME_FOR_WHEEL)
            if ENABLE_NL5:
                print('initializing NL5 ...')
                import control.NL5 as NL5
                self.nl5 = NL5.NL5()
                print('NL5 initialized')
            if ENABLE_CELLX:
                print('initializing CellX ...')
                self.cellx = serial_peripherals.CellX(CELLX_SN)
                for channel in [1,2,3,4]:
                    self.cellx.set_modulation(channel,CELLX_MODULATION)
                    self.cellx.turn_on(channel)
                print('CellX initialized')
            if USE_LDI_SERIAL_CONTROL:
                print('initializing LDI ...')
                self.ldi = serial_peripherals.LDI()
                self.ldi.run()
                print('LDI initialized')
                self.ldi.set_intensity_mode(LDI_INTENSITY_MODE)
                self.ldi.set_shutter_mode(LDI_SHUTTER_MODE)
            if SUPPORT_LASER_AUTOFOCUS:
                sn_camera_focus = camera_fc.get_sn_by_model(FOCUS_CAMERA_MODEL)
                self.camera_focus = camera_fc.Camera(sn=sn_camera_focus)
                self.camera_focus.open()
                self.camera_focus.set_pixel_format('MONO8')
            sn_camera_main = camera.get_sn_by_model(MAIN_CAMERA_MODEL)
            self.camera = camera.Camera(sn=sn_camera_main,rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            self.camera.open()
            self.camera.set_pixel_format(DEFAULT_PIXEL_FORMAT) # bug: comment out for confocal?

            if USE_ZABER_EMISSION_FILTER_WHEEL:
                self.emission_filter_wheel = serial_peripherals.FilterController(FILTER_CONTROLLER_SERIAL_NUMBER, 115200, 8, serial.PARITY_NONE, serial.STOPBITS_ONE)
            if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
                self.emission_filter_wheel = serial_peripherals.Optospin(SN=FILTER_CONTROLLER_SERIAL_NUMBER)

            self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION,sn=CONTROLLER_SN)

        if USE_ZABER_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.start_homing()
        if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.set_speed(OPTOSPIN_EMISSION_FILTER_WHEEL_SPEED_HZ)

        # reset the MCU
        self.microcontroller.reset()
        time.sleep(0.5)

        # reinitialize motor drivers and DAC (in particular for V2.1 driver board where PG is not functional)
        self.microcontroller.initialize_drivers()
        time.sleep(0.5)

        # configure the actuators
        self.microcontroller.configure_actuators()

        print('load channel_configurations.xml')
        self.configurationManager = core.ConfigurationManager(filename='./channel_configurations.xml')
        self.objectiveStore = core.ObjectiveStore(parent=self) # todo: add widget to select/save objective save
        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager,parent=self)
        self.navigationController = core.NavigationController(self.microcontroller, self.objectiveStore, parent=self)
        self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController,is_for_wellplate=True)
        self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
        self.scanCoordinates = core.ScanCoordinates()
        self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
        if ENABLE_TRACKING:
            self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
        self.imageSaver = core.ImageSaver()
        self.imageDisplay = core.ImageDisplay()
        self.navigationViewer = core.NavigationViewer(self.objectiveStore, sample=str(WELLPLATE_FORMAT)+' well plate')
        if HOMING_ENABLED_Z:
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

        self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)
        self.navigationController.set_z_limit_neg_mm(SOFTWARE_POS_LIMIT.Z_NEGATIVE)

        # home XY, set zero and set software limit
        if HOMING_ENABLED_X and HOMING_ENABLED_Y:
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
                    sys.exit(1)
            self.navigationController.zero_y()
            # home x
            self.navigationController.home_x()
            t0 = time.time()
            while self.microcontroller.is_busy():
                time.sleep(0.005)
                if time.time() - t0 > 10:
                    print('x homing timeout, the program will exit')
                    sys.exit(1)
            self.navigationController.zero_x()
            self.slidePositionController.homing_done = True

        if USE_ZABER_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.wait_for_homing_complete()

        self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
        self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
        self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
        self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
        self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)

        # move to scanning position
        if HOMING_ENABLED_X and HOMING_ENABLED_Y:
            self.navigationController.move_x(20)
            while self.microcontroller.is_busy():
                time.sleep(0.005)
            self.navigationController.move_y(20)
            while self.microcontroller.is_busy():
                time.sleep(0.005)

        # set piezo arguments
        if ENABLE_OBJECTIVE_PIEZO is True:
            if OBJECTIVE_PIEZO_CONTROL_VOLTAGE_RANGE == 5:
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

        # open the camera
        # camera start streaming
        # self.camera.set_reverse_x(CAMERA_REVERSE_X) # these are not implemented for the cameras in use
        # self.camera.set_reverse_y(CAMERA_REVERSE_Y) # these are not implemented for the cameras in use
        self.camera.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
        self.camera.set_callback(self.streamHandler.on_new_frame)
        self.camera.enable_callback()

        # only toupcam need reset strobe argument when camera's argument change 
        if CAMERA_TYPE == "Toupcam":
            self.camera.set_reset_strobe_delay_function(self.liveController.reset_strobe_arugment)

        # load widgets
        if ENABLE_SPINNING_DISK_CONFOCAL:
            self.spinningDiskConfocalWidget = widgets.SpinningDiskConfocalWidget(self.xlight, self.configurationManager)
        if ENABLE_NL5:
            import control.NL5Widget as NL5Widget
            self.nl5Wdiget = NL5Widget.NL5Widget(self.nl5)
        if CAMERA_TYPE == "Toupcam":
            self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera, include_gain_exposure_time=False, include_camera_temperature_setting = True, include_camera_auto_wb_setting = False)
        else:
            self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera, include_gain_exposure_time=False, include_camera_temperature_setting = False, include_camera_auto_wb_setting = True)
        self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True,show_autolevel=True,autolevel=True)
        self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration=f'{WELLPLATE_FORMAT} well plate')
        self.navigationBarWidget = widgets.NavigationBarWidget(self.navigationController,self.slidePositionController,add_z_buttons=False)
        self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
        self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
        if USE_ZABER_EMISSION_FILTER_WHEEL or USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.filterControllerWidget = widgets.FilterControllerWidget(self.emission_filter_wheel, self.liveController)
        self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
        self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)
        self.multiPointWidget2 = widgets.MultiPointWidget2(self.navigationController,self.navigationViewer,self.multipointController,self.configurationManager,scanCoordinates=None)
        self.multiPointWidgetGrid = widgets.MultiPointWidgetGrid(self.navigationController,self.navigationViewer,self.multipointController,self.objectiveStore,self.configurationManager,self.scanCoordinates)
        self.piezoWidget = widgets.PiezoWidget(self.navigationController)
        self.wellplateFormatWidget = widgets.WellplateFormatWidget()
        self.objectivesWidget = widgets.ObjectivesWidget(self.objectiveStore)
        self.sampleSettingsWidget = widgets.SampleSettingsWidget(self.objectivesWidget,self.wellplateFormatWidget)
        if ENABLE_TRACKING:
            self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
        if ENABLE_STITCHER:
            self.stitcherWidget = widgets.StitcherWidget(self.configurationManager)
        if WELLPLATE_FORMAT != 1536:
            self.wellSelectionWidget = widgets.WellSelectionWidget(WELLPLATE_FORMAT)
        else:
            self.wellSelectionWidget = widgets.Well1536SelectionWidget()
        self.scanCoordinates.add_well_selector(self.wellSelectionWidget)

        # image display tabs
        self.imageDisplayTabs = QTabWidget()
        if USE_NAPARI_FOR_LIVE_VIEW:
            self.napariLiveWidget = widgets.NapariLiveWidget(self.streamHandler, self.liveController, self.navigationController, self.configurationManager, self.wellSelectionWidget)
            self.imageDisplayTabs.addTab(self.napariLiveWidget, "Live View")
        else:
            if ENABLE_TRACKING:
                self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
                self.imageDisplayWindow.show_ROI_selector()
            else:
                self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True,show_LUT=True,autoLevels=True)
            self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
        if USE_NAPARI_FOR_MULTIPOINT:
            self.napariMultiChannelWidget = widgets.NapariMultiChannelWidget(self.objectiveStore)
            # self.napariMultiChannelWidget.set_pixel_size_um(3.76*2/60)
            # ^ for 60x, IMX571, 2x2 binning, to change to using objective and camera config
            self.imageDisplayTabs.addTab(self.napariMultiChannelWidget, "Multichannel Acquisition")
        else:
            self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow()
            self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")
        if SHOW_TILED_PREVIEW:
            if USE_NAPARI_FOR_TILED_DISPLAY:
                self.napariTiledDisplayWidget = widgets.NapariTiledDisplayWidget(self.objectiveStore)
                self.imageDisplayTabs.addTab(self.napariTiledDisplayWidget, "Tiled Preview")
            else:
                self.imageDisplayWindow_scan_preview = core.ImageDisplayWindow(draw_crosshairs=True)
                self.imageDisplayTabs.addTab(self.imageDisplayWindow_scan_preview.widget, "Tiled Preview")

        if USE_NAPARI_FOR_MOSAIC_DISPLAY:
            self.napariMosaicDisplayWidget = widgets.NapariMosaicDisplayWidget(self.objectiveStore)
            self.imageDisplayTabs.addTab(self.napariMosaicDisplayWidget, "Mosaic View")

        # acquisition tabs
        self.recordTabWidget = QTabWidget()
        if ENABLE_SCAN_GRID:
            self.recordTabWidget.addTab(self.multiPointWidgetGrid, "Wellplate Multipoint")
        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.recordTabWidget.addTab(self.multiPointWidget2, "Flexible Multipoint")
        # self.recordTabWidget.addTab(self.multiPointWidget, "Custom Multipoint")
        if ENABLE_TRACKING:
            self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
        if ENABLE_RECORDING:
            self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
        self.recordTabWidget.currentChanged.connect(lambda: self.resizeCurrentTab(self.recordTabWidget))
        self.resizeCurrentTab(self.recordTabWidget)

        self.cameraTabWidget = QTabWidget()
        self.cameraTabWidget.addTab(self.navigationWidget,"Stages")
        if ENABLE_OBJECTIVE_PIEZO:
            self.cameraTabWidget.addTab(self.piezoWidget,"Piezo")
        if ENABLE_NL5:
            self.cameraTabWidget.addTab(self.nl5Wdiget,"NL5")
        if ENABLE_SPINNING_DISK_CONFOCAL:
            self.cameraTabWidget.addTab(self.spinningDiskConfocalWidget,"Confocal")
        if USE_ZABER_EMISSION_FILTER_WHEEL or USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.cameraTabWidget.addTab(self.filterControllerWidget,"Emission Filter")
        self.cameraTabWidget.addTab(self.cameraSettingWidget,'Camera')
        self.cameraTabWidget.addTab(self.autofocusWidget,"Contrast AF")
        self.cameraTabWidget.currentChanged.connect(lambda: self.resizeCurrentTab(self.cameraTabWidget))
        self.resizeCurrentTab(self.cameraTabWidget)

        layout = QVBoxLayout()
        # layout.addWidget(self.sampleSettingsWidget) # at top 
        if USE_NAPARI_FOR_LIVE_CONTROL:
            layout.addWidget(self.navigationWidget)
            layout.addWidget(self.cameraTabWidget)
        else:
            #self.microscopeControlTabWidget = QTabWidget()
            #self.microscopeControlTabWidget.addTab(self.liveControlWidget,"Live Controls")
            #self.microscopeControlTabWidget.addTab(self.navigationWidget,"Stages")
            #layout.addWidget(self.microscopeControlTabWidget)
            layout.addWidget(self.liveControlWidget)
            layout.addWidget(self.cameraTabWidget)
            
        if SHOW_DAC_CONTROL:
            layout.addWidget(self.dacControlWidget)
        layout.addWidget(self.recordTabWidget)
        if ENABLE_STITCHER:
            layout.addWidget(self.stitcherWidget)
            self.stitcherWidget.hide()
        layout.addWidget(self.sampleSettingsWidget) # at bottom above viewer
        layout.addWidget(self.navigationViewer)
        # layout.addWidget(self.sampleSettingsWidget) # at bottom

        # transfer the layout to the central widget
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(layout)
        self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())

        if SINGLE_WINDOW:
            dock_display = dock.Dock('Image Display', autoOrientation = False)
            dock_display.showTitleBar()

            dock_display.addWidget(self.imageDisplayTabs)
            dock_display.addWidget(self.navigationBarWidget)
            dock_display.setStretch(x=100,y=100)

            self.dock_wellSelection = dock.Dock('Well Selector', autoOrientation = False)
            self.dock_wellSelection.showTitleBar()
            if not USE_NAPARI_WELL_SELECTION:
                self.dock_wellSelection.addWidget(self.wellSelectionWidget)
            #self.dock_wellSelection.addWidget(self.wellplateFormatWidget) # todo: add widget to select wellplate format
            self.dock_wellSelection.setFixedHeight(self.dock_wellSelection.minimumSizeHint().height())
            dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
            # dock_controlPanel.showTitleBar()
            dock_controlPanel.addWidget(self.centralWidget)
            #set central widget stretch 
            dock_controlPanel.setStretch(x=1,y=None)
            dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())

            main_dockArea = dock.DockArea()
            main_dockArea.addDock(dock_display)
            if not USE_NAPARI_WELL_SELECTION:
                main_dockArea.addDock(self.dock_wellSelection,'bottom')
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
            width = 0.96 * desktopWidget.height()
            height = width
            self.tabbedImageDisplayWindow.setFixedSize(int(width), int(height))
            self.tabbedImageDisplayWindow.show()

        '''
        try:
            self.cswWindow = widgets.WrapperWindow(self.cameraSettingWidget)
        except AttributeError:
            pass

        try:
            self.cswfcWindow = widgets.WrapperWindow(self.cameraSettingWidget_focus_camera)
        except AttributeError:
            pass
        '''

        # make connections
        self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
        self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
        # self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
        self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x) + " mm"))
        self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x) + " mm"))
        self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x) + " μm"))
        self.navigationController.xPos.connect(self.navigationBarWidget.update_x_position)
        self.navigationController.yPos.connect(self.navigationBarWidget.update_y_position)
        self.navigationController.zPos.connect(self.navigationBarWidget.update_z_position)
        if ENABLE_TRACKING:
            self.navigationController.signal_joystick_button_pressed.connect(self.trackingControlWidget.slot_joystick_button_pressed)
        else:
            self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)

        self.multiPointWidget.signal_acquisition_started.connect(self.navigationWidget.toggle_navigation_controls)
        self.multiPointWidget.signal_acquisition_started.connect(self.toggleAcquisitionStart)
        if ENABLE_STITCHER:
            self.multipointController.signal_stitcher.connect(self.startStitcher)
            self.multiPointWidget.signal_stitcher_widget.connect(self.toggleStitcherWidget)
            self.multiPointWidget.signal_acquisition_channels.connect(self.stitcherWidget.updateRegistrationChannels) # change enabled registration channels
            self.multiPointWidget.signal_acquisition_z_levels.connect(self.stitcherWidget.updateRegistrationZLevels)

        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.multiPointWidget2.signal_acquisition_started.connect(self.navigationWidget.toggle_navigation_controls)
            self.multiPointWidget2.signal_acquisition_started.connect(self.toggleAcquisitionStart)
            if ENABLE_STITCHER:
                self.multiPointWidget2.signal_stitcher_widget.connect(self.toggleStitcherWidget)
                self.multiPointWidget2.signal_acquisition_channels.connect(self.stitcherWidget.updateRegistrationChannels)
                self.multiPointWidget2.signal_acquisition_z_levels.connect(self.stitcherWidget.updateRegistrationZLevels)

        if ENABLE_SCAN_GRID:
            self.multiPointWidgetGrid.signal_acquisition_started.connect(self.navigationWidget.toggle_navigation_controls)
            self.multiPointWidgetGrid.signal_acquisition_started.connect(self.toggleAcquisitionStart)
            if ENABLE_STITCHER:
                self.multiPointWidgetGrid.signal_stitcher_widget.connect(self.toggleStitcherWidget)
                self.multiPointWidgetGrid.signal_acquisition_channels.connect(self.stitcherWidget.updateRegistrationChannels)
                self.multiPointWidgetGrid.signal_acquisition_z_levels.connect(self.stitcherWidget.updateRegistrationZLevels)

        self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
        self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
        self.liveControlWidget.signal_start_live.connect(self.onStartLive)
        self.liveControlWidget.update_camera_settings()

        # load vs scan position switching
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
        self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)

        # display the FOV in the viewer
        self.objectivesWidget.signal_objective_changed.connect(self.navigationViewer.on_objective_changed)
        self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
        self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)
        self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
        self.multipointController.signal_z_piezo_um.connect(self.piezoWidget.update_displacement_um_display)
        self.multiPointWidgetGrid.signal_z_stacking.connect(self.multipointController.set_z_stacking_config)

        self.recordTabWidget.currentChanged.connect(self.onTabChanged)
        self.imageDisplayTabs.currentChanged.connect(self.onDisplayTabChanged)

        if USE_NAPARI_FOR_LIVE_VIEW:
            self.multipointController.signal_current_configuration.connect(self.napariLiveWidget.set_microscope_mode)
            self.autofocusController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=True))
            self.streamHandler.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.multipointController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.napariLiveWidget.signal_coordinates_clicked.connect(self.navigationController.move_from_click)
            self.liveControlWidget.signal_live_configuration.connect(self.napariLiveWidget.set_live_configuration)
            self.napariLiveWidget.signal_layer_contrast_limits.connect(self.updateContrastLimits)
            if USE_NAPARI_FOR_LIVE_CONTROL:
                self.napariLiveWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
                self.napariLiveWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
                self.napariLiveWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel)
        else:
            self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
            self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image) # may connect streamHandler directly to imageDisplayWindow
            self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.liveControlWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel) # todo: replicate for napari (autolevel)
            self.imageDisplayWindow.image_click_coordinates.connect(self.navigationController.move_from_click)

        if USE_NAPARI_FOR_MULTIPOINT:
            self.multiPointWidget.signal_acquisition_channels.connect(self.napariMultiChannelWidget.initChannels)
            self.multiPointWidget.signal_acquisition_shape.connect(self.napariMultiChannelWidget.initLayersShape)
            if ENABLE_FLEXIBLE_MULTIPOINT:
                self.multiPointWidget2.signal_acquisition_channels.connect(self.napariMultiChannelWidget.initChannels)
                self.multiPointWidget2.signal_acquisition_shape.connect(self.napariMultiChannelWidget.initLayersShape)
            if ENABLE_SCAN_GRID:
                self.multiPointWidgetGrid.signal_acquisition_channels.connect(self.napariMultiChannelWidget.initChannels)
                self.multiPointWidgetGrid.signal_acquisition_shape.connect(self.napariMultiChannelWidget.initLayersShape)

            self.multipointController.napari_layers_init.connect(self.napariMultiChannelWidget.initLayers)
            self.multipointController.napari_layers_update.connect(self.napariMultiChannelWidget.updateLayers)
            self.napariMultiChannelWidget.signal_layer_contrast_limits.connect(self.updateContrastLimits)
        else:
            self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)

        if SHOW_TILED_PREVIEW:
            if USE_NAPARI_FOR_TILED_DISPLAY:
                self.multiPointWidget.signal_acquisition_channels.connect(self.napariTiledDisplayWidget.initChannels)
                self.multiPointWidget.signal_acquisition_shape.connect(self.napariTiledDisplayWidget.initLayersShape)
                if ENABLE_FLEXIBLE_MULTIPOINT:
                    self.multiPointWidget2.signal_acquisition_channels.connect(self.napariTiledDisplayWidget.initChannels)
                    self.multiPointWidget2.signal_acquisition_shape.connect(self.napariTiledDisplayWidget.initLayersShape)
                if ENABLE_SCAN_GRID:
                    self.multiPointWidgetGrid.signal_acquisition_channels.connect(self.napariTiledDisplayWidget.initChannels)
                    self.multiPointWidgetGrid.signal_acquisition_shape.connect(self.napariTiledDisplayWidget.initLayersShape)

                self.multipointController.napari_layers_init.connect(self.napariTiledDisplayWidget.initLayers)
                self.multipointController.napari_layers_update.connect(self.napariTiledDisplayWidget.updateLayers)
                self.napariTiledDisplayWidget.signal_coordinates_clicked.connect(self.navigationController.scan_preview_move_from_click)
                self.napariTiledDisplayWidget.signal_layer_contrast_limits.connect(self.updateContrastLimits)
            else:
                self.multipointController.image_to_display_tiled_preview.connect(self.imageDisplayWindow_scan_preview.display_image)
                self.imageDisplayWindow_scan_preview.image_click_coordinates.connect(self.navigationController.scan_preview_move_from_click)

        if USE_NAPARI_FOR_MOSAIC_DISPLAY:
            self.multiPointWidget.signal_acquisition_channels.connect(self.napariMosaicDisplayWidget.initChannels)
            self.multiPointWidget.signal_acquisition_shape.connect(self.napariMosaicDisplayWidget.initLayersShape)
            if ENABLE_FLEXIBLE_MULTIPOINT:
                self.multiPointWidget2.signal_acquisition_channels.connect(self.napariMosaicDisplayWidget.initChannels)
                self.multiPointWidget2.signal_acquisition_shape.connect(self.napariMosaicDisplayWidget.initLayersShape)
            if ENABLE_SCAN_GRID:
                self.multiPointWidgetGrid.signal_acquisition_channels.connect(self.napariMosaicDisplayWidget.initChannels)
                self.multiPointWidgetGrid.signal_acquisition_shape.connect(self.napariMosaicDisplayWidget.initLayersShape)

            self.multipointController.napari_mosaic_update.connect(self.napariMosaicDisplayWidget.updateMosaic)
            self.napariMosaicDisplayWidget.signal_coordinates_clicked.connect(self.navigationController.move_from_click_mosaic)
            self.napariMosaicDisplayWidget.signal_clear_viewer.connect(self.navigationViewer.clear_slide)
            # self.napariMosaicDisplayWidget.signal_layer_contrast_limits.connect(self.updateContrastLimits)

        # (double) click to move to a well
        self.wellplateFormatWidget.signalWellplateSettings.connect(self.wellSelectionWidget.updateWellplateSettings)
        self.wellplateFormatWidget.signalWellplateSettings.connect(self.navigationViewer.update_wellplate_settings)
        self.wellplateFormatWidget.signalWellplateSettings.connect(self.scanCoordinates.update_wellplate_settings)
        self.wellplateFormatWidget.signalWellplateSettings.connect(lambda format_, *args: self.onWellplateChanged(format_))

        self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)
        self.wellSelectionWidget.signal_wellSelected.connect(self.multiPointWidget.set_well_selected)
        if ENABLE_SCAN_GRID:
            self.wellSelectionWidget.signal_wellSelected.connect(self.multiPointWidgetGrid.set_well_coordinates)
            self.objectivesWidget.signal_objective_changed.connect(self.multiPointWidgetGrid.update_well_coordinates)
            self.multiPointWidgetGrid.signal_update_navigation_viewer.connect(self.navigationViewer.update_current_location)

        # camera
        self.camera.set_callback(self.streamHandler.on_new_frame)

        # laser autofocus
        if SUPPORT_LASER_AUTOFOCUS:

            # controllers
            self.configurationManager_focus_camera = core.ConfigurationManager(filename='./focus_camera_configurations.xml')
            self.streamHandler_focus_camera = core.StreamHandler()
            self.liveController_focus_camera = core.LiveController(self.camera_focus,self.microcontroller,self.configurationManager_focus_camera, self, control_illumination=False,for_displacement_measurement=True)
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
                self.cameraSettingWidget_focus_camera = widgets.CameraSettingsWidget(self.camera_focus, include_gain_exposure_time = False, include_camera_temperature_setting = True, include_camera_auto_wb_setting = False)
            else:
                self.cameraSettingWidget_focus_camera = widgets.CameraSettingsWidget(self.camera_focus, include_gain_exposure_time = False, include_camera_temperature_setting = False, include_camera_auto_wb_setting = True)
            self.liveControlWidget_focus_camera = widgets.LiveControlWidget(self.streamHandler_focus_camera,self.liveController_focus_camera,self.configurationManager_focus_camera) #,show_display_options=True)
            self.waveformDisplay = widgets.WaveformDisplay(N=1000,include_x=True,include_y=False)
            self.displacementMeasurementWidget = widgets.DisplacementMeasurementWidget(self.displacementMeasurementController,self.waveformDisplay)
            self.laserAutofocusControlWidget = widgets.LaserAutofocusControlWidget(self.laserAutofocusController)

            self.cameraTabWidget.insertTab(self.cameraTabWidget.indexOf(self.autofocusWidget) + 1, self.laserAutofocusControlWidget, "Laser AF")

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
            self.imageDisplayTabs.addTab(laserfocus_dockArea,"Laser-Based Focus")

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

        if HOMING_ENABLED_X and HOMING_ENABLED_Y and HOMING_ENABLED_Z:
            self.navigationController.move_to_cached_position()
            while self.microcontroller.is_busy():
                time.sleep(0.005)
            if ENABLE_SCAN_GRID:
                self.multiPointWidgetGrid.init_z()

        # Create the menu bar
        menubar = self.menuBar()
        # Add the "Settings" menu
        settings_menu = menubar.addMenu("Settings")
        if SUPPORT_SCIMICROSCOPY_LED_ARRAY:
            # Add the "LED Matrix" action
            led_matrix_action = QAction("LED Matrix", self)
            led_matrix_action.triggered.connect(self.openLedMatrixSettings)
            settings_menu.addAction(led_matrix_action)

    def openLedMatrixSettings(self):
        if SUPPORT_SCIMICROSCOPY_LED_ARRAY:
            dialog = widgets.LedMatrixSettingsDialog(self.liveController.led_array) # to move led_arry outside liveController
            dialog.exec_()

    def onTabChanged(self, index):
        acquisitionWidget = self.recordTabWidget.widget(index)
        is_multipoint = (index == self.recordTabWidget.indexOf(self.multiPointWidget))
        is_scan_grid = (index == self.recordTabWidget.indexOf(self.multiPointWidgetGrid)) if ENABLE_SCAN_GRID else False
        self.toggleWellSelector((is_multipoint or is_scan_grid) and self.wellSelectionWidget.format != 0)
        if is_scan_grid:
            self.wellSelectionWidget.onSelectionChanged()
        else:
            self.multiPointWidgetGrid.clear_regions()
        try:
            if ENABLE_STITCHER:
                self.toggleStitcherWidget(acquisitionWidget.checkbox_stitchOutput.isChecked())
            acquisitionWidget.emit_selected_channels()
        except AttributeError:
            pass

    def resizeCurrentTab(self, tabWidget):
        current_widget = tabWidget.currentWidget()
        if current_widget:
            total_height = current_widget.sizeHint().height()  + tabWidget.tabBar().height()
            tabWidget.resize(tabWidget.width(), total_height)
            tabWidget.setMaximumHeight(total_height)
            tabWidget.updateGeometry()
            self.updateGeometry()

    def onDisplayTabChanged(self, index):
        # activate the corresponding napari widget on tab changes
        current_widget = self.imageDisplayTabs.widget(index)
        if hasattr(current_widget, 'viewer'):
            current_widget.activate()

    def onWellplateChanged(self, format_):
        if format_ == 0:
            self.toggleWellSelector(False)
            self.multipointController.inverted_objective = False
            self.navigationController.inverted_objective = False
            self.slidePositionController.setParent(None)
            self.slidePositionController.deleteLater()
            self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
            self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
            self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
            self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
            self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
            self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)
            self.navigationBarWidget.replace_slide_controller(self.slidePositionController)
        else:
            self.toggleWellSelector(True)
            self.multipointController.inverted_objective = True
            self.navigationController.inverted_objective = True
            self.slidePositionController.setParent(None)
            self.slidePositionController.deleteLater()
            self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController,is_for_wellplate=True)
            self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
            self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
            self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
            self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)
            self.navigationBarWidget.replace_slide_controller(self.slidePositionController)

            if format_ == 1536:
                self.wellSelectionWidget.setParent(None)
                self.wellSelectionWidget.deleteLater()
                self.wellSelectionWidget = widgets.Well1536SelectionWidget()
                self.scanCoordinates.add_well_selector(self.wellSelectionWidget)
                if USE_NAPARI_WELL_SELECTION:
                     self.napariLiveWidget.replace_well_selector(self.wellSelectionWidget)
                else:
                    self.dock_wellSelection.addWidget(self.wellSelectionWidget)
                self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)

            elif isinstance(self.wellSelectionWidget, widgets.Well1536SelectionWidget):
                self.wellSelectionWidget.setParent(None)
                self.wellSelectionWidget.deleteLater()
                self.wellSelectionWidget = widgets.WellSelectionWidget(format_)
                self.scanCoordinates.add_well_selector(self.wellSelectionWidget)
                if USE_NAPARI_WELL_SELECTION:
                    self.napariLiveWidget.replace_well_selector(self.wellSelectionWidget)
                else:
                    self.dock_wellSelection.addWidget(self.wellSelectionWidget)
                self.wellSelectionWidget.signal_wellSelected.connect(self.multiPointWidget.set_well_selected)
                self.wellplateFormatWidget.signalWellplateSettings.connect(self.wellSelectionWidget.updateWellplateSettings)
                self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)
            
            if ENABLE_SCAN_GRID:
                self.wellSelectionWidget.signal_wellSelected.connect(self.multiPointWidgetGrid.set_well_coordinates)

        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.multiPointWidget2.clear_only_location_list()
        if ENABLE_SCAN_GRID:
            self.multiPointWidgetGrid.clear_regions()
            self.multiPointWidgetGrid.set_default_scan_size()
        self.wellSelectionWidget.onSelectionChanged()

    def toggleWellSelector(self, show):
        if USE_NAPARI_WELL_SELECTION:
            self.napariLiveWidget.toggle_well_selector(show)
        else:
            self.dock_wellSelection.setVisible(show)
        self.wellSelectionWidget.setVisible(show)

    def toggleAcquisitionStart(self, acquisition_started):
        current_index = self.recordTabWidget.currentIndex()
        for index in range(self.recordTabWidget.count()):
            self.recordTabWidget.setTabEnabled(index, not acquisition_started or index == current_index)

        is_multipoint = (current_index == self.recordTabWidget.indexOf(self.multiPointWidget))
        is_scan_grid = (current_index == self.recordTabWidget.indexOf(self.multiPointWidgetGrid)) if ENABLE_SCAN_GRID else False
        if (is_multipoint or is_scan_grid) and self.wellSelectionWidget.format != 0:
            self.toggleWellSelector(not acquisition_started)
        if is_scan_grid:
            self.navigationViewer.on_acquisition_start(acquisition_started)
            self.multiPointWidgetGrid.display_progress_bar(acquisition_started)
        if is_multipoint:
            self.navigationViewer.on_acquisition_start(acquisition_started)
            self.multiPointWidget2.display_progress_bar(acquisition_started)

    def toggleStitcherWidget(self, checked):
        if checked:
            self.stitcherWidget.show()
        else:
            self.stitcherWidget.hide()

    def onStartLive(self):
        self.imageDisplayTabs.setCurrentIndex(0)

    def startStitcher(self, acquisition_path):
        acquisitionWidget = self.recordTabWidget.currentWidget()
        if acquisitionWidget.checkbox_stitchOutput.isChecked():
            # Fetch settings from StitcherWidget controls
            apply_flatfield = self.stitcherWidget.applyFlatfieldCheck.isChecked()
            use_registration = self.stitcherWidget.useRegistrationCheck.isChecked()
            registration_channel = self.stitcherWidget.registrationChannelCombo.currentText()
            registration_z_level = self.stitcherWidget.registrationZCombo.value()
            overlap_percent = self.multiPointWidgetGrid.entry_overlap.value()
            output_name = acquisitionWidget.lineEdit_experimentID.text()
            if output_name == "":
                output_name = "stitched"
            output_format = ".ome.zarr" if self.stitcherWidget.outputFormatCombo.currentText() == "OME-ZARR" else ".ome.tiff"

            if self.recordTabWidget.currentIndex() == self.recordTabWidget.indexOf(self.multiPointWidgetGrid):
                self.stitcherThread = stitcher.CoordinateStitcher(input_folder=acquisition_path, output_name=output_name, output_format=output_format, 
                                                apply_flatfield=apply_flatfield, overlap_percent=overlap_percent,
                                                use_registration=use_registration, registration_channel=registration_channel, registration_z_level=registration_z_level)
            else:
                self.stitcherThread = stitcher.Stitcher(input_folder=acquisition_path, output_name=output_name, output_format=output_format,
                                                apply_flatfield=apply_flatfield, 
                                                use_registration=use_registration, registration_channel=registration_channel, registration_z_level=registration_z_level)

            self.stitcherWidget.setStitcherThread(self.stitcherThread)
            # Connect signals to slots
            self.stitcherThread.update_progress.connect(self.stitcherWidget.updateProgressBar)
            self.stitcherThread.getting_flatfields.connect(self.stitcherWidget.gettingFlatfields)
            self.stitcherThread.starting_stitching.connect(self.stitcherWidget.startingStitching)
            self.stitcherThread.starting_saving.connect(self.stitcherWidget.startingSaving)
            self.stitcherThread.finished_saving.connect(self.stitcherWidget.finishedSaving)
            # Start the thread
            self.stitcherThread.start()

    def updateContrastLimits(self, channel, min_val, max_val):
        if USE_NAPARI_FOR_LIVE_VIEW:
            self.napariLiveWidget.saveContrastLimits(channel, min_val, max_val)
        if USE_NAPARI_FOR_MULTIPOINT:
            self.napariMultiChannelWidget.saveContrastLimits(channel, min_val, max_val)
        if USE_NAPARI_FOR_TILED_DISPLAY and SHOW_TILED_PREVIEW:
            self.napariTiledDisplayWidget.saveContrastLimits(channel, min_val, max_val)
        if USE_NAPARI_FOR_MOSAIC_DISPLAY:
            self.napariMosaicDisplayWidget.saveContrastLimits(channel, min_val, max_val)
        if ENABLE_STITCHER:
            self.stitcherWidget.saveContrastLimits(channel, min_val, max_val)

    def closeEvent(self, event):
        self.navigationController.cache_current_position()

        if USE_ZABER_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.set_emission_filter(1)
        if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.set_emission_filter(1)
            self.emission_filter_wheel.close()
        if ENABLE_STITCHER:
            self.stitcherWidget.closeEvent(event)

        # move the objective to a defined position upon exit
        if HOMING_ENABLED_X and HOMING_ENABLED_Y:
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
        self.camera.stop_streaming()
        self.camera.close()

        if ENABLE_CELLX:
            for channel in [1,2,3,4]:
                self.cellx.turn_off(channel)
            self.cellx.close()

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
