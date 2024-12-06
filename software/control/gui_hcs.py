# set QT_API environment variable
import os
os.environ["QT_API"] = "pyqt5"
import serial
import time
from typing import Optional

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

from control._def import *

# app specific libraries
import control.widgets as widgets
import pyqtgraph.dockarea as dock
import squid.logging
import control.microscope

log = squid.logging.get_logger(__name__)

if CAMERA_TYPE == "Toupcam":
    try:
        import control.camera_toupcam as camera
    except:
        log.warning("Problem importing Toupcam, defaulting to default camera")
        import control.camera as camera
elif CAMERA_TYPE == "FLIR":
    try:
        import control.camera_flir as camera
    except:
        log.warning("Problem importing FLIR camera, defaulting to default camera")
        import control.camera as camera
elif CAMERA_TYPE == "Hamamatsu":
    try:
        import control.camera_hamamatsu as camera
    except:
        log.warning("Problem importing Hamamatsu camera, defaulting to default camera")
        import control.camera as camera
elif CAMERA_TYPE == "iDS":
    try:
        import control.camera_ids as camera
    except:
        log.warning("Problem importing iDS camera, defaulting to default camera")
        import control.camera as camera
elif CAMERA_TYPE == "Tucsen":
    try:
        import control.camera_tucsen as camera
    except:
        log.warning("Problem importing Tucsen camera, defaulting to default camera")
        import control.camera as camera
else:
    import control.camera as camera

if FOCUS_CAMERA_TYPE == "Toupcam":
    try:
        import control.camera_toupcam as camera_fc
    except:
        log.warning("Problem importing Toupcam for focus, defaulting to default camera")
        import control.camera as camera_fc
elif FOCUS_CAMERA_TYPE == "FLIR":
    try:
        import control.camera_flir as camera_fc
    except:
        log.warning("Problem importing FLIR camera for focus, defaulting to default camera")
        import control.camera as camera_fc
else:
    import control.camera as camera_fc

if USE_PRIOR_STAGE:
    from control.stage_prior import PriorStage
    from control.navigation_prior import NavigationController_PriorStage

import control.core as core
import control.microcontroller as microcontroller
import control.serial_peripherals as serial_peripherals

if ENABLE_STITCHER:
    import control.stitcher as stitcher

if SUPPORT_LASER_AUTOFOCUS:
    import control.core_displacement_measurement as core_displacement_measurement

SINGLE_WINDOW = True # set to False if use separate windows for display and control


class HighContentScreeningGui(QMainWindow):
    fps_software_trigger = 100

    def __init__(self, is_simulation=False, live_only_mode=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.microcontroller: Optional[microcontroller.Microcontroller] = None

        self.log = squid.logging.get_logger(self.__class__.__name__)
        self.live_only_mode = live_only_mode or LIVE_ONLY_MODE
        self.performance_mode = False
        self.napari_connections = {}

        self.loadObjects(is_simulation)

        self.setupHardware()

        self.loadWidgets()

        self.setupLayout()

        self.makeConnections()

        self.microscope = control.microscope.Microscope(self)

        # Move to cached position
        if HOMING_ENABLED_X and HOMING_ENABLED_Y and HOMING_ENABLED_Z:
            self.navigationController.move_to_cached_position()
            self.waitForMicrocontroller()
            if ENABLE_WELLPLATE_MULTIPOINT:
                self.wellplateMultiPointWidget.init_z()
            self.flexibleMultiPointWidget.init_z()

        # Create the menu bar
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        if SUPPORT_SCIMICROSCOPY_LED_ARRAY:
            led_matrix_action = QAction("LED Matrix", self)
            led_matrix_action.triggered.connect(self.openLedMatrixSettings)
            settings_menu.addAction(led_matrix_action)

    def loadObjects(self, is_simulation):
        if is_simulation:
            self.loadSimulationObjects()
        else:
            try:
                self.loadHardwareObjects()
            except Exception:
                self.log.error("---- !! ERROR CONNECTING TO HARDWARE !! ----", stack_info=True, exc_info=True)
                raise

        # Common object initialization
        self.objectiveStore = core.ObjectiveStore(parent=self)
        self.configurationManager = core.ConfigurationManager(filename='./channel_configurations.xml')
        self.contrastManager = core.ContrastManager()
        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera, self.microcontroller, self.configurationManager, parent=self)
        if USE_PRIOR_STAGE:
            self.navigationController = NavigationController_PriorStage(self.priorstage, self.microcontroller, self.objectiveStore, parent=self)
        else:
            self.navigationController = core.NavigationController(self.microcontroller, self.objectiveStore, parent=self)
        self.slidePositionController = core.SlidePositionController(self.navigationController, self.liveController, is_for_wellplate=True)
        self.autofocusController = core.AutoFocusController(self.camera, self.navigationController, self.liveController)
        self.scanCoordinates = core.ScanCoordinates()
        self.multipointController = core.MultiPointController(self.camera, self.navigationController, self.liveController, self.autofocusController, self.configurationManager, scanCoordinates=self.scanCoordinates, parent=self)
        self.imageSaver = core.ImageSaver()
        self.imageDisplay = core.ImageDisplay()
        if ENABLE_TRACKING:
            self.trackingController = core.TrackingController(self.camera, self.microcontroller, self.navigationController, self.configurationManager, self.liveController, self.autofocusController, self.imageDisplayWindow)
        if WELLPLATE_FORMAT == 'glass slide':
            self.navigationViewer = core.NavigationViewer(self.objectiveStore, sample='4 glass slide')
        else:
            self.navigationViewer = core.NavigationViewer(self.objectiveStore, sample=WELLPLATE_FORMAT)

        if SUPPORT_LASER_AUTOFOCUS:
            self.configurationManager_focus_camera = core.ConfigurationManager(filename='./focus_camera_configurations.xml')
            self.streamHandler_focus_camera = core.StreamHandler()
            self.liveController_focus_camera = core.LiveController(self.camera_focus,self.microcontroller,self.configurationManager_focus_camera, self, control_illumination=False,for_displacement_measurement=True)
            self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,scanCoordinates=self.scanCoordinates,parent=self)
            self.imageDisplayWindow_focus = core.ImageDisplayWindow(draw_crosshairs=True, show_LUT=False, autoLevels=False)
            self.displacementMeasurementController = core_displacement_measurement.DisplacementMeasurementController()
            self.laserAutofocusController = core.LaserAutofocusController(self.microcontroller,self.camera_focus,self.liveController_focus_camera,self.navigationController,has_two_interfaces=HAS_TWO_INTERFACES,use_glass_top=USE_GLASS_TOP,look_for_cache=False)

    def loadSimulationObjects(self):
        self.log.debug("Loading simulated hardware objects...")
        # Initialize simulation objects
        if ENABLE_SPINNING_DISK_CONFOCAL:
            self.xlight = serial_peripherals.XLight_Simulation()
        if ENABLE_NL5:
            import control.NL5 as NL5
            self.nl5 = NL5.NL5_Simulation()
        if ENABLE_CELLX:
            self.cellx = serial_peripherals.CellX_Simulation()
        if SUPPORT_LASER_AUTOFOCUS:
            self.camera_focus = camera_fc.Camera_Simulation()
        if USE_LDI_SERIAL_CONTROL:
            self.ldi = serial_peripherals.LDI_Simulation()
        self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE, flip_image=FLIP_IMAGE)
        self.camera.set_pixel_format(DEFAULT_PIXEL_FORMAT)
        if USE_ZABER_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel = serial_peripherals.FilterController_Simulation(115200, 8, serial.PARITY_NONE, serial.STOPBITS_ONE)
        if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel = serial_peripherals.Optospin_Simulation(SN=None)
        self.microcontroller = microcontroller.Microcontroller(existing_serial=microcontroller.SimSerial(),is_simulation=True)

    def loadHardwareObjects(self):
        # Initialize hardware objects
        if ENABLE_SPINNING_DISK_CONFOCAL:
            try:
                self.xlight = serial_peripherals.XLight(XLIGHT_SERIAL_NUMBER, XLIGHT_SLEEP_TIME_FOR_WHEEL)
            except Exception:
                self.log.error("Error initializing Spinning Disk Confocal")
                raise

        if ENABLE_NL5:
            try:
                import control.NL5 as NL5
                self.nl5 = NL5.NL5()
            except Exception:
                self.log.error("Error initializing NL5")
                raise

        if ENABLE_CELLX:
            try:
                self.cellx = serial_peripherals.CellX(CELLX_SN)
                for channel in [1,2,3,4]:
                    self.cellx.set_modulation(channel, CELLX_MODULATION)
                    self.cellx.turn_on(channel)
            except Exception:
                self.log.error("Error initializing CellX")
                raise

        if USE_LDI_SERIAL_CONTROL:
            try:
                self.ldi = serial_peripherals.LDI()
                self.ldi.run()
                self.ldi.set_intensity_mode(LDI_INTENSITY_MODE)
                self.ldi.set_shutter_mode(LDI_SHUTTER_MODE)
            except Exception:
                self.log.error("Error initializing LDI")
                raise

        if SUPPORT_LASER_AUTOFOCUS:
            try:
                sn_camera_focus = camera_fc.get_sn_by_model(FOCUS_CAMERA_MODEL)
                self.camera_focus = camera_fc.Camera(sn=sn_camera_focus)
                self.camera_focus.open()
                self.camera_focus.set_pixel_format('MONO8')
            except Exception:
                self.log.error(f"Error initializing Laser Autofocus Camera")
                raise

        try:
            sn_camera_main = camera.get_sn_by_model(MAIN_CAMERA_MODEL)
            self.camera = camera.Camera(sn=sn_camera_main, rotate_image_angle=ROTATE_IMAGE_ANGLE, flip_image=FLIP_IMAGE)
            self.camera.open()
            self.camera.set_pixel_format(DEFAULT_PIXEL_FORMAT)
        except Exception:
            self.log.error("Error initializing Main Camera")
            raise

        if USE_ZABER_EMISSION_FILTER_WHEEL:
            try:
                self.emission_filter_wheel = serial_peripherals.FilterController(FILTER_CONTROLLER_SERIAL_NUMBER, 115200, 8, serial.PARITY_NONE, serial.STOPBITS_ONE)
            except Exception:
                self.log.error("Error initializing Zaber Emission Filter Wheel")
                raise

        if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            try:
                self.emission_filter_wheel = serial_peripherals.Optospin(SN=FILTER_CONTROLLER_SERIAL_NUMBER)
            except Exception:
                self.log.error("Error initializing Optospin Emission Filter Wheel")
                raise

        if USE_PRIOR_STAGE:
            try:
                self.priorstage = PriorStage(PRIOR_STAGE_SN, parent=self)
            except Exception:
                self.log.error("Error initializing Prior Stage")
                raise

        try:
            self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION, sn=CONTROLLER_SN)
        except Exception:
            self.log.error(f"Error initializing Microcontroller")
            raise

    def setupHardware(self):
        # Setup hardware components
        if USE_ZABER_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.start_homing()
        if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.set_speed(OPTOSPIN_EMISSION_FILTER_WHEEL_SPEED_HZ)

        if not self.microcontroller:
            raise ValueError("Microcontroller must be none-None for hardware setup.")

        try:
            self.microcontroller.reset()
            time.sleep(0.5)
            self.microcontroller.initialize_drivers()
            time.sleep(0.5)
            self.microcontroller.configure_actuators()

            if HAS_ENCODER_X:
                self.navigationController.set_axis_PID_arguments(0, PID_P_X, PID_I_X, PID_D_X)
                self.navigationController.configure_encoder(0, (SCREW_PITCH_X_MM * 1000) / ENCODER_RESOLUTION_UM_X, ENCODER_FLIP_DIR_X)
                self.navigationController.set_pid_control_enable(0, ENABLE_PID_X)
            if HAS_ENCODER_Y:
                self.navigationController.set_axis_PID_arguments(1, PID_P_Y, PID_I_Y, PID_D_Y)
                self.navigationController.configure_encoder(1, (SCREW_PITCH_Y_MM * 1000) / ENCODER_RESOLUTION_UM_Y, ENCODER_FLIP_DIR_Y)
                self.navigationController.set_pid_control_enable(1, ENABLE_PID_Y)
            if HAS_ENCODER_Z:
                self.navigationController.set_axis_PID_arguments(2, PID_P_Z, PID_I_Z, PID_D_Z)
                self.navigationController.configure_encoder(2, (SCREW_PITCH_Z_MM * 1000) / ENCODER_RESOLUTION_UM_Z, ENCODER_FLIP_DIR_Z)
                self.navigationController.set_pid_control_enable(2, ENABLE_PID_Z)
            time.sleep(0.5)

            self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
            self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
            self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
            self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)
            self.navigationController.set_z_limit_pos_mm(SOFTWARE_POS_LIMIT.Z_POSITIVE)
            self.navigationController.set_z_limit_neg_mm(SOFTWARE_POS_LIMIT.Z_NEGATIVE)

            if HOMING_ENABLED_Z:
                self.navigationController.home_z()
                self.waitForMicrocontroller(10, 'z homing timeout')
            if HOMING_ENABLED_X and HOMING_ENABLED_Y:
                self.navigationController.move_x(20)
                self.waitForMicrocontroller()
                self.navigationController.home_y()
                self.waitForMicrocontroller(10, 'y homing timeout')
                self.navigationController.zero_y()
                self.navigationController.home_x()
                self.waitForMicrocontroller(10, 'x homing timeout')
                self.navigationController.zero_x()
                self.slidePositionController.homing_done = True
            if USE_ZABER_EMISSION_FILTER_WHEEL:
                self.emission_filter_wheel.wait_for_homing_complete()
            if HOMING_ENABLED_X and HOMING_ENABLED_Y:
                self.navigationController.move_x(20)
                self.waitForMicrocontroller()
                self.navigationController.move_y(20)
                self.waitForMicrocontroller()

            if ENABLE_OBJECTIVE_PIEZO:
                OUTPUT_GAINS.CHANNEL7_GAIN = (OBJECTIVE_PIEZO_CONTROL_VOLTAGE_RANGE == 5)
            div = 1 if OUTPUT_GAINS.REFDIV else 0
            gains = sum(getattr(OUTPUT_GAINS, f'CHANNEL{i}_GAIN') << i for i in range(8))
            self.microcontroller.configure_dac80508_refdiv_and_gain(div, gains)
            self.microcontroller.set_dac80508_scaling_factor_for_illumination(ILLUMINATION_INTENSITY_FACTOR)
        except TimeoutError as e:
            # If we can't recover from a timeout, at least do our best to make sure the system is left in a safe
            # and restartable state.
            self.log.error("Setup timed out, resetting microcontroller before failing gui setup")
            self.microcontroller.reset()
            raise e
        self.camera.set_software_triggered_acquisition()
        self.camera.set_callback(self.streamHandler.on_new_frame)
        self.camera.enable_callback()

        if CAMERA_TYPE == "Toupcam":
            self.camera.set_reset_strobe_delay_function(self.liveController.reset_strobe_arugment)

        if SUPPORT_LASER_AUTOFOCUS:
            self.camera_focus.set_software_triggered_acquisition() #self.camera.set_continuous_acquisition()
            self.camera_focus.set_callback(self.streamHandler_focus_camera.on_new_frame)
            self.camera_focus.enable_callback()
            self.camera_focus.start_streaming()

    def waitForMicrocontroller(self, timeout=5.0, error_message=None):
        try:
            self.microcontroller.wait_till_operation_is_completed(timeout)
        except TimeoutError as e:
            self.log.error(error_message or "Microcontroller operation timed out!")
            raise e

    def loadWidgets(self):
        # Initialize all GUI widgets
        if ENABLE_SPINNING_DISK_CONFOCAL:
            self.spinningDiskConfocalWidget = widgets.SpinningDiskConfocalWidget(self.xlight, self.configurationManager)
        if ENABLE_NL5:
            import control.NL5Widget as NL5Widget
            self.nl5Wdiget = NL5Widget.NL5Widget(self.nl5)

        if CAMERA_TYPE == "Toupcam":
            self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera, include_gain_exposure_time=False, include_camera_temperature_setting=True, include_camera_auto_wb_setting=False)
        else:
            self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera, include_gain_exposure_time=False, include_camera_temperature_setting=False, include_camera_auto_wb_setting=True)
        self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler, self.liveController, self.configurationManager, show_display_options=True, show_autolevel=True, autolevel=True)
        self.navigationWidget = widgets.NavigationWidget(self.navigationController, self.slidePositionController, widget_configuration=f'{WELLPLATE_FORMAT} well plate')
        self.navigationBarWidget = widgets.NavigationBarWidget(self.navigationController, self.slidePositionController, add_z_buttons=False)
        self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
        self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
        self.piezoWidget = widgets.PiezoWidget(self.navigationController)
        self.objectivesWidget = widgets.ObjectivesWidget(self.objectiveStore)

        if USE_ZABER_EMISSION_FILTER_WHEEL or USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.filterControllerWidget = widgets.FilterControllerWidget(self.emission_filter_wheel, self.liveController)

        self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler, self.imageSaver)
        self.wellplateFormatWidget = widgets.WellplateFormatWidget(self.navigationController, self.navigationViewer, self.streamHandler, self.liveController)
        if WELLPLATE_FORMAT != '1536 well plate':
            self.wellSelectionWidget = widgets.WellSelectionWidget(WELLPLATE_FORMAT, self.wellplateFormatWidget)
        else:
            self.wellSelectionWidget = widgets.Well1536SelectionWidget()
        self.scanCoordinates.add_well_selector(self.wellSelectionWidget)

        if SUPPORT_LASER_AUTOFOCUS:
            if FOCUS_CAMERA_TYPE == "Toupcam":
                self.cameraSettingWidget_focus_camera = widgets.CameraSettingsWidget(self.camera_focus, include_gain_exposure_time = False, include_camera_temperature_setting = True, include_camera_auto_wb_setting = False)
            else:
                self.cameraSettingWidget_focus_camera = widgets.CameraSettingsWidget(self.camera_focus, include_gain_exposure_time = False, include_camera_temperature_setting = False, include_camera_auto_wb_setting = True)
            self.liveControlWidget_focus_camera = widgets.LiveControlWidget(self.streamHandler_focus_camera,self.liveController_focus_camera,self.configurationManager_focus_camera, stretch=False) #,show_display_options=True)
            self.waveformDisplay = widgets.WaveformDisplay(N=1000,include_x=True,include_y=False)
            self.displacementMeasurementWidget = widgets.DisplacementMeasurementWidget(self.displacementMeasurementController,self.waveformDisplay)
            self.laserAutofocusControlWidget = widgets.LaserAutofocusControlWidget(self.laserAutofocusController)

            self.imageDisplayWindow_focus = core.ImageDisplayWindow(draw_crosshairs=True)
            self.waveformDisplay = widgets.WaveformDisplay(N=1000, include_x=True, include_y=False)
            self.displacementMeasurementWidget = widgets.DisplacementMeasurementWidget(self.displacementMeasurementController, self.waveformDisplay)
            self.laserAutofocusControlWidget = widgets.LaserAutofocusControlWidget(self.laserAutofocusController)

        self.imageDisplayTabs = QTabWidget()
        if self.live_only_mode:
            if ENABLE_TRACKING:
                self.imageDisplayWindow = core.ImageDisplayWindow(self.liveController, self.contrastManager, draw_crosshairs=True)
                self.imageDisplayWindow.show_ROI_selector()
            else:
                self.imageDisplayWindow = core.ImageDisplayWindow(self.liveController, self.contrastManager, draw_crosshairs=True, show_LUT=True, autoLevels=True)
            #self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
            self.imageDisplayTabs = self.imageDisplayWindow.widget
            self.napariMosaicDisplayWidget = None
        else:
            self.setupImageDisplayTabs()

        self.flexibleMultiPointWidget = widgets.FlexibleMultiPointWidget(self.navigationController, self.navigationViewer, self.multipointController, self.objectiveStore, self.configurationManager, scanCoordinates=None)
        self.wellplateMultiPointWidget = widgets.WellplateMultiPointWidget(self.navigationController, self.navigationViewer, self.multipointController, self.objectiveStore, self.configurationManager, self.scanCoordinates, self.napariMosaicDisplayWidget)
        self.sampleSettingsWidget = widgets.SampleSettingsWidget(self.objectivesWidget, self.wellplateFormatWidget)

        if ENABLE_TRACKING:
            self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController, self.configurationManager, show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
        if ENABLE_STITCHER:
            self.stitcherWidget = widgets.StitcherWidget(self.configurationManager, self.contrastManager)

        self.recordTabWidget = QTabWidget()
        self.setupRecordTabWidget()

        self.cameraTabWidget = QTabWidget()
        self.setupCameraTabWidget()

    def setupImageDisplayTabs(self):
        if USE_NAPARI_FOR_LIVE_VIEW:
            self.napariLiveWidget = widgets.NapariLiveWidget(self.streamHandler, self.liveController, self.navigationController, self.configurationManager, self.contrastManager, self.wellSelectionWidget)
            self.imageDisplayTabs.addTab(self.napariLiveWidget, "Live View")
        else:
            if ENABLE_TRACKING:
                self.imageDisplayWindow = core.ImageDisplayWindow(self.liveController, self.contrastManager, draw_crosshairs=True)
                self.imageDisplayWindow.show_ROI_selector()
            else:
                self.imageDisplayWindow = core.ImageDisplayWindow(self.liveController, self.contrastManager, draw_crosshairs=True, show_LUT=True, autoLevels=True)
            self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")

        if not self.live_only_mode:
            if USE_NAPARI_FOR_MULTIPOINT:
                self.napariMultiChannelWidget = widgets.NapariMultiChannelWidget(self.objectiveStore, self.contrastManager)
                self.imageDisplayTabs.addTab(self.napariMultiChannelWidget, "Multichannel Acquisition")
            else:
                self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow()
                self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

            if SHOW_TILED_PREVIEW:
                if USE_NAPARI_FOR_TILED_DISPLAY:
                    self.napariTiledDisplayWidget = widgets.NapariTiledDisplayWidget(self.objectiveStore, self.contrastManager)
                    self.imageDisplayTabs.addTab(self.napariTiledDisplayWidget, "Tiled Preview")
                else:
                    self.imageDisplayWindow_scan_preview = core.ImageDisplayWindow(draw_crosshairs=True)
                    self.imageDisplayTabs.addTab(self.imageDisplayWindow_scan_preview.widget, "Tiled Preview")

            if USE_NAPARI_FOR_MOSAIC_DISPLAY:
                self.napariMosaicDisplayWidget = widgets.NapariMosaicDisplayWidget(self.objectiveStore, self.contrastManager)
                self.imageDisplayTabs.addTab(self.napariMosaicDisplayWidget, "Mosaic View")

        if SUPPORT_LASER_AUTOFOCUS:
            dock_laserfocus_image_display = dock.Dock('Focus Camera Image Display', autoOrientation=False)
            dock_laserfocus_image_display.showTitleBar()
            dock_laserfocus_image_display.addWidget(self.imageDisplayWindow_focus.widget)
            dock_laserfocus_image_display.setStretch(x=100, y=100)

            dock_laserfocus_liveController = dock.Dock('Focus Camera Controller', autoOrientation=False)
            dock_laserfocus_liveController.showTitleBar()
            dock_laserfocus_liveController.addWidget(self.liveControlWidget_focus_camera)
            dock_laserfocus_liveController.setStretch(x=100, y=100)
            dock_laserfocus_liveController.setFixedWidth(self.liveControlWidget_focus_camera.minimumSizeHint().width())

            dock_waveform = dock.Dock('Displacement Measurement', autoOrientation=False)
            dock_waveform.showTitleBar()
            dock_waveform.addWidget(self.waveformDisplay)
            dock_waveform.setStretch(x=100, y=40)

            dock_displayMeasurement = dock.Dock('Displacement Measurement Control', autoOrientation=False)
            dock_displayMeasurement.showTitleBar()
            dock_displayMeasurement.addWidget(self.displacementMeasurementWidget)
            dock_displayMeasurement.setStretch(x=100, y=40)
            dock_displayMeasurement.setFixedWidth(self.displacementMeasurementWidget.minimumSizeHint().width())

            laserfocus_dockArea = dock.DockArea()
            laserfocus_dockArea.addDock(dock_laserfocus_image_display)
            laserfocus_dockArea.addDock(dock_laserfocus_liveController, 'right', relativeTo=dock_laserfocus_image_display)
            if SHOW_LEGACY_DISPLACEMENT_MEASUREMENT_WINDOWS:
                laserfocus_dockArea.addDock(dock_waveform, 'bottom', relativeTo=dock_laserfocus_liveController)
                laserfocus_dockArea.addDock(dock_displayMeasurement, 'bottom', relativeTo=dock_waveform)

            self.imageDisplayTabs.addTab(laserfocus_dockArea, "Laser-Based Focus")

    def setupRecordTabWidget(self):
        if ENABLE_WELLPLATE_MULTIPOINT:
            self.recordTabWidget.addTab(self.wellplateMultiPointWidget, "Wellplate Multipoint")
        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.recordTabWidget.addTab(self.flexibleMultiPointWidget, "Flexible Multipoint")
        if ENABLE_TRACKING:
            self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
        if ENABLE_RECORDING:
            self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
        self.recordTabWidget.currentChanged.connect(lambda: self.resizeCurrentTab(self.recordTabWidget))
        self.resizeCurrentTab(self.recordTabWidget)

    def setupCameraTabWidget(self):
        if not USE_NAPARI_FOR_LIVE_CONTROL or self.live_only_mode:
            self.cameraTabWidget.addTab(self.navigationWidget, "Stages")
        if ENABLE_OBJECTIVE_PIEZO:
            self.cameraTabWidget.addTab(self.piezoWidget, "Piezo")
        if ENABLE_NL5:
            self.cameraTabWidget.addTab(self.nl5Wdiget, "NL5")
        if ENABLE_SPINNING_DISK_CONFOCAL:
            self.cameraTabWidget.addTab(self.spinningDiskConfocalWidget, "Confocal")
        if USE_ZABER_EMISSION_FILTER_WHEEL or USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.cameraTabWidget.addTab(self.filterControllerWidget, "Emission Filter")
        self.cameraTabWidget.addTab(self.cameraSettingWidget, 'Camera')
        self.cameraTabWidget.addTab(self.autofocusWidget, "Contrast AF")
        if SUPPORT_LASER_AUTOFOCUS:
            self.cameraTabWidget.addTab(self.laserAutofocusControlWidget, "Laser AF")
        self.cameraTabWidget.currentChanged.connect(lambda: self.resizeCurrentTab(self.cameraTabWidget))
        self.resizeCurrentTab(self.cameraTabWidget)

    def setupLayout(self):
        layout = QVBoxLayout()

        if USE_NAPARI_FOR_LIVE_CONTROL and not self.live_only_mode:
            layout.addWidget(self.navigationWidget)
        else:
            layout.addWidget(self.liveControlWidget)

        layout.addWidget(self.cameraTabWidget)

        if SHOW_DAC_CONTROL:
            layout.addWidget(self.dacControlWidget)

        layout.addWidget(self.recordTabWidget)

        if ENABLE_STITCHER:
            layout.addWidget(self.stitcherWidget)
            self.stitcherWidget.hide()

        layout.addWidget(self.sampleSettingsWidget)
        layout.addWidget(self.navigationViewer)

        # Add performance mode toggle button
        if not self.live_only_mode:
            self.performanceModeToggle = QPushButton("Enable Performance Mode")
            self.performanceModeToggle.setCheckable(True)
            self.performanceModeToggle.setChecked(self.performance_mode)
            self.performanceModeToggle.clicked.connect(self.togglePerformanceMode)
            layout.addWidget(self.performanceModeToggle)

        self.centralWidget = QWidget()
        self.centralWidget.setLayout(layout)
        self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())

        if SINGLE_WINDOW:
            self.setupSingleWindowLayout()
        else:
            self.setupMultiWindowLayout()

    def setupSingleWindowLayout(self):
        main_dockArea = dock.DockArea()

        dock_display = dock.Dock('Image Display', autoOrientation=False)
        dock_display.showTitleBar()
        dock_display.addWidget(self.imageDisplayTabs)
        if SHOW_NAVIGATION_BAR:
            dock_display.addWidget(self.navigationBarWidget)
        dock_display.setStretch(x=100, y=100)
        main_dockArea.addDock(dock_display)

        self.dock_wellSelection = dock.Dock('Well Selector', autoOrientation=False)
        self.dock_wellSelection.showTitleBar()
        if not USE_NAPARI_WELL_SELECTION or self.live_only_mode:
            self.dock_wellSelection.addWidget(self.wellSelectionWidget)
            self.dock_wellSelection.setFixedHeight(self.dock_wellSelection.minimumSizeHint().height())
            main_dockArea.addDock(self.dock_wellSelection, 'bottom')

        dock_controlPanel = dock.Dock('Controls', autoOrientation=False)
        dock_controlPanel.addWidget(self.centralWidget)
        dock_controlPanel.setStretch(x=1, y=None)
        dock_controlPanel.setFixedWidth(dock_controlPanel.minimumSizeHint().width())
        main_dockArea.addDock(dock_controlPanel, 'right')
        self.setCentralWidget(main_dockArea)

        desktopWidget = QDesktopWidget()
        height_min = 0.9 * desktopWidget.height()
        width_min = 0.96 * desktopWidget.width()
        self.setMinimumSize(int(width_min), int(height_min))
        self.onTabChanged(self.recordTabWidget.currentIndex())

    def setupMultiWindowLayout(self):
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

    def makeConnections(self):
        self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
        self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
        # self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
        self.navigationController.xPos.connect(lambda x: self.navigationWidget.label_Xpos.setText("{:.2f}".format(x) + " mm"))
        self.navigationController.yPos.connect(lambda x: self.navigationWidget.label_Ypos.setText("{:.2f}".format(x) + " mm"))
        self.navigationController.zPos.connect(lambda x: self.navigationWidget.label_Zpos.setText("{:.2f}".format(x) + " μm"))

        if SHOW_NAVIGATION_BAR:
            self.navigationController.xPos.connect(self.navigationBarWidget.update_x_position)
            self.navigationController.yPos.connect(self.navigationBarWidget.update_y_position)
            self.navigationController.zPos.connect(self.navigationBarWidget.update_z_position)

        if ENABLE_TRACKING:
            self.navigationController.signal_joystick_button_pressed.connect(self.trackingControlWidget.slot_joystick_button_pressed)
        else:
            self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)

        if ENABLE_STITCHER:
            self.multipointController.signal_stitcher.connect(self.startStitcher)

        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.flexibleMultiPointWidget.signal_acquisition_started.connect(self.toggleAcquisitionStart)
            if ENABLE_STITCHER:
                self.flexibleMultiPointWidget.signal_stitcher_widget.connect(self.toggleStitcherWidget)
                self.flexibleMultiPointWidget.signal_acquisition_channels.connect(self.stitcherWidget.updateRegistrationChannels)
                self.flexibleMultiPointWidget.signal_stitcher_z_levels.connect(self.stitcherWidget.updateRegistrationZLevels)

        if ENABLE_WELLPLATE_MULTIPOINT:
            self.wellplateMultiPointWidget.signal_acquisition_started.connect(self.toggleAcquisitionStart)
            if ENABLE_STITCHER:
                self.wellplateMultiPointWidget.signal_stitcher_widget.connect(self.toggleStitcherWidget)
                self.wellplateMultiPointWidget.signal_acquisition_channels.connect(self.stitcherWidget.updateRegistrationChannels)
                self.wellplateMultiPointWidget.signal_stitcher_z_levels.connect(self.stitcherWidget.updateRegistrationZLevels)

        self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
        self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
        if not self.live_only_mode:
            self.liveControlWidget.signal_start_live.connect(self.onStartLive)
        self.liveControlWidget.update_camera_settings()

        self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
        #self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
        #self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
        self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)
        self.navigationViewer.signal_coordinates_clicked.connect(self.navigationController.move_from_click_mosaic)
        self.objectivesWidget.signal_objective_changed.connect(self.navigationViewer.on_objective_changed)
        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.objectivesWidget.signal_objective_changed.connect(self.flexibleMultiPointWidget.update_fov_positions)
        self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
        self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)
        self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
        self.multipointController.signal_z_piezo_um.connect(self.piezoWidget.update_displacement_um_display)
        self.wellplateMultiPointWidget.signal_z_stacking.connect(self.multipointController.set_z_stacking_config)

        self.recordTabWidget.currentChanged.connect(self.onTabChanged)
        if not self.live_only_mode:
            self.imageDisplayTabs.currentChanged.connect(self.onDisplayTabChanged)

        if USE_NAPARI_FOR_LIVE_VIEW and not self.live_only_mode:
            self.multipointController.signal_current_configuration.connect(self.napariLiveWidget.set_microscope_mode)
            self.autofocusController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=True))
            self.streamHandler.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.multipointController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.napariLiveWidget.signal_coordinates_clicked.connect(self.navigationController.move_from_click)
            self.liveControlWidget.signal_live_configuration.connect(self.napariLiveWidget.set_live_configuration)

            if USE_NAPARI_FOR_LIVE_CONTROL:
                self.napariLiveWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
                self.napariLiveWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
                self.napariLiveWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel)
        else:
            self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
            self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.liveControlWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel)
            self.imageDisplayWindow.image_click_coordinates.connect(self.navigationController.move_from_click)

        self.makeNapariConnections()

        self.wellplateFormatWidget.signalWellplateSettings.connect(self.navigationViewer.update_wellplate_settings)
        self.wellplateFormatWidget.signalWellplateSettings.connect(self.scanCoordinates.update_wellplate_settings)
        self.wellplateFormatWidget.signalWellplateSettings.connect(lambda format_, *args: self.onWellplateChanged(format_))

        self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)
        #self.wellSelectionWidget.signal_wellSelected.connect(self.multiPointWidget.set_well_selected)
        if ENABLE_WELLPLATE_MULTIPOINT:
            self.wellSelectionWidget.signal_wellSelected.connect(self.wellplateMultiPointWidget.set_well_coordinates)
            self.objectivesWidget.signal_objective_changed.connect(self.wellplateMultiPointWidget.update_coordinates)
            self.wellplateMultiPointWidget.signal_update_navigation_viewer.connect(self.navigationViewer.update_current_location)

        if SUPPORT_LASER_AUTOFOCUS:
            self.liveControlWidget_focus_camera.signal_newExposureTime.connect(self.cameraSettingWidget_focus_camera.set_exposure_time)
            self.liveControlWidget_focus_camera.signal_newAnalogGain.connect(self.cameraSettingWidget_focus_camera.set_analog_gain)
            self.liveControlWidget_focus_camera.update_camera_settings()

            self.streamHandler_focus_camera.signal_new_frame_received.connect(self.liveController_focus_camera.on_new_frame)
            self.streamHandler_focus_camera.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

            self.streamHandler_focus_camera.image_to_display.connect(self.displacementMeasurementController.update_measurement)
            self.displacementMeasurementController.signal_plots.connect(self.waveformDisplay.plot)
            self.displacementMeasurementController.signal_readings.connect(self.displacementMeasurementWidget.display_readings)
            self.laserAutofocusController.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

        self.camera.set_callback(self.streamHandler.on_new_frame)

    def makeNapariConnections(self):
        """Initialize all Napari connections in one place"""
        self.napari_connections = {
            'napariLiveWidget': [],
            'napariMultiChannelWidget': [],
            'napariTiledDisplayWidget': [],
            'napariMosaicDisplayWidget': []
        }

        # Setup live view connections
        if USE_NAPARI_FOR_LIVE_VIEW and not self.live_only_mode:
            self.napari_connections['napariLiveWidget'] = [
                (self.multipointController.signal_current_configuration, self.napariLiveWidget.set_microscope_mode),
                (self.autofocusController.image_to_display,
                 lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=True)),
                (self.streamHandler.image_to_display,
                 lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False)),
                (self.multipointController.image_to_display,
                 lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False)),
                (self.napariLiveWidget.signal_coordinates_clicked, self.navigationController.move_from_click),
                (self.liveControlWidget.signal_live_configuration, self.napariLiveWidget.set_live_configuration)
            ]

            if USE_NAPARI_FOR_LIVE_CONTROL:
                self.napari_connections['napariLiveWidget'].extend([
                    (self.napariLiveWidget.signal_newExposureTime, self.cameraSettingWidget.set_exposure_time),
                    (self.napariLiveWidget.signal_newAnalogGain, self.cameraSettingWidget.set_analog_gain),
                    (self.napariLiveWidget.signal_autoLevelSetting, self.imageDisplayWindow.set_autolevel)
                ])
        else:
            # Non-Napari display connections
            self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
            self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.liveControlWidget.signal_autoLevelSetting.connect(self.imageDisplayWindow.set_autolevel)
            self.imageDisplayWindow.image_click_coordinates.connect(self.navigationController.move_from_click)

        if not self.live_only_mode:
            # Setup multichannel widget connections
            if USE_NAPARI_FOR_MULTIPOINT:
                self.napari_connections['napariMultiChannelWidget'] = [
                    (self.multipointController.napari_layers_init, self.napariMultiChannelWidget.initLayers),
                    (self.multipointController.napari_layers_update, self.napariMultiChannelWidget.updateLayers)
                ]

                if ENABLE_FLEXIBLE_MULTIPOINT:
                    self.napari_connections['napariMultiChannelWidget'].extend([
                        (self.flexibleMultiPointWidget.signal_acquisition_channels, self.napariMultiChannelWidget.initChannels),
                        (self.flexibleMultiPointWidget.signal_acquisition_shape, self.napariMultiChannelWidget.initLayersShape)
                    ])

                if ENABLE_WELLPLATE_MULTIPOINT:
                    self.napari_connections['napariMultiChannelWidget'].extend([
                        (self.wellplateMultiPointWidget.signal_acquisition_channels, self.napariMultiChannelWidget.initChannels),
                        (self.wellplateMultiPointWidget.signal_acquisition_shape, self.napariMultiChannelWidget.initLayersShape)
                    ])
            else:
                self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)

            # Setup tiled display widget connections
            if SHOW_TILED_PREVIEW and USE_NAPARI_FOR_TILED_DISPLAY:
                self.napari_connections['napariTiledDisplayWidget'] = [
                    (self.multipointController.napari_layers_init, self.napariTiledDisplayWidget.initLayers),
                    (self.multipointController.napari_layers_update, self.napariTiledDisplayWidget.updateLayers),
                    (self.napariTiledDisplayWidget.signal_coordinates_clicked,
                     self.navigationController.scan_preview_move_from_click)
                ]

                if ENABLE_FLEXIBLE_MULTIPOINT:
                    self.napari_connections['napariTiledDisplayWidget'].extend([
                        (self.flexibleMultiPointWidget.signal_acquisition_channels, self.napariTiledDisplayWidget.initChannels),
                        (self.flexibleMultiPointWidget.signal_acquisition_shape, self.napariTiledDisplayWidget.initLayersShape)
                    ])

                if ENABLE_WELLPLATE_MULTIPOINT:
                    self.napari_connections['napariTiledDisplayWidget'].extend([
                        (self.wellplateMultiPointWidget.signal_acquisition_channels, self.napariTiledDisplayWidget.initChannels),
                        (self.wellplateMultiPointWidget.signal_acquisition_shape, self.napariTiledDisplayWidget.initLayersShape)
                    ])

            # Setup mosaic display widget connections
            if USE_NAPARI_FOR_MOSAIC_DISPLAY:
                self.napari_connections['napariMosaicDisplayWidget'] = [
                    (self.multipointController.napari_mosaic_update, self.napariMosaicDisplayWidget.updateMosaic),
                    (self.napariMosaicDisplayWidget.signal_coordinates_clicked,
                     self.navigationController.move_from_click_mosaic),
                    (self.napariMosaicDisplayWidget.signal_update_viewer, self.navigationViewer.update_slide)
                ]

                if ENABLE_FLEXIBLE_MULTIPOINT:
                    self.napari_connections['napariMosaicDisplayWidget'].extend([
                        (self.flexibleMultiPointWidget.signal_acquisition_channels, self.napariMosaicDisplayWidget.initChannels),
                        (self.flexibleMultiPointWidget.signal_acquisition_shape, self.napariMosaicDisplayWidget.initLayersShape)
                    ])

                if ENABLE_WELLPLATE_MULTIPOINT:
                    self.napari_connections['napariMosaicDisplayWidget'].extend([
                        (self.wellplateMultiPointWidget.signal_acquisition_channels, self.napariMosaicDisplayWidget.initChannels),
                        (self.wellplateMultiPointWidget.signal_acquisition_shape, self.napariMosaicDisplayWidget.initLayersShape),
                        (self.wellplateMultiPointWidget.signal_draw_shape, self.napariMosaicDisplayWidget.enable_shape_drawing),
                        (self.napariMosaicDisplayWidget.signal_shape_drawn, self.wellplateMultiPointWidget.update_manual_shape)
                    ])

            # Make initial connections
            self.updateNapariConnections()

    def updateNapariConnections(self):
        # Update Napari connections based on performance mode. Live widget connections are preserved
        for widget_name, connections in self.napari_connections.items():
            if widget_name != 'napariLiveWidget':  # Always keep the live widget connected
                widget = getattr(self, widget_name, None)
                if widget:
                    for signal, slot in connections:
                        if self.performance_mode:
                            try:
                                signal.disconnect(slot)
                            except TypeError:
                                # Connection might not exist, which is fine
                                pass
                        else:
                            try:
                                signal.connect(slot)
                            except TypeError:
                                # Connection might already exist, which is fine
                                pass

    def toggleNapariTabs(self):
        # Enable/disable Napari tabs based on performance mode
        for i in range(1, self.imageDisplayTabs.count()):
            widget = self.imageDisplayTabs.widget(i)
            self.imageDisplayTabs.setTabEnabled(i, not self.performance_mode)

        if self.performance_mode:
            # Switch to the NapariLiveWidget tab if it exists
            for i in range(self.imageDisplayTabs.count()):
                if isinstance(self.imageDisplayTabs.widget(i), widgets.NapariLiveWidget):
                    self.imageDisplayTabs.setCurrentIndex(i)
                    break

    def togglePerformanceMode(self):
        self.performance_mode = self.performanceModeToggle.isChecked()
        button_txt = "Disable" if self.performance_mode else "Enable"
        self.performanceModeToggle.setText(button_txt + " Performance Mode")
        self.updateNapariConnections()
        self.toggleNapariTabs()
        print(f"Performance mode {'enabled' if self.performance_mode else 'disabled'}")

    def openLedMatrixSettings(self):
        if SUPPORT_SCIMICROSCOPY_LED_ARRAY:
            dialog = widgets.LedMatrixSettingsDialog(self.liveController.led_array)
            dialog.exec_()

    def onTabChanged(self, index):
        acquisitionWidget = self.recordTabWidget.widget(index)
        is_flexible = (index == self.recordTabWidget.indexOf(self.flexibleMultiPointWidget))
        is_scan_grid = (index == self.recordTabWidget.indexOf(self.wellplateMultiPointWidget)) if ENABLE_WELLPLATE_MULTIPOINT else False
        self.toggleWellSelector(is_scan_grid and self.wellSelectionWidget.format != 'glass slide')
        
        if is_scan_grid:
            self.navigationViewer.clear_overlay()
            self.wellSelectionWidget.onSelectionChanged()
        else:
            self.wellplateMultiPointWidget.clear_regions()

        if is_flexible:
            self.flexibleMultiPointWidget.update_fov_positions()

        if ENABLE_STITCHER:
            self.toggleStitcherWidget(acquisitionWidget.checkbox_stitchOutput.isChecked())
        acquisitionWidget.emit_selected_channels()


    def resizeCurrentTab(self, tabWidget):
        current_widget = tabWidget.currentWidget()
        if current_widget:
            total_height = current_widget.sizeHint().height() + tabWidget.tabBar().height()
            tabWidget.resize(tabWidget.width(), total_height)
            tabWidget.setMaximumHeight(total_height)
            tabWidget.updateGeometry()
            self.updateGeometry()

    def onDisplayTabChanged(self, index):
        current_widget = self.imageDisplayTabs.widget(index)
        if hasattr(current_widget, 'viewer'):
            current_widget.activate()

    def onWellplateChanged(self, format_):
        if isinstance(format_, QVariant):
            format_ = format_.value()

        if format_ == 'glass slide':
            self.toggleWellSelector(False)
            self.multipointController.inverted_objective = False
            self.navigationController.inverted_objective = False
            self.setupSlidePositionController(is_for_wellplate=False)
        else:
            self.toggleWellSelector(True)
            self.multipointController.inverted_objective = True
            self.navigationController.inverted_objective = True
            self.setupSlidePositionController(is_for_wellplate=True)

            if format_ == '1536 well plate':
                self.replaceWellSelectionWidget(widgets.Well1536SelectionWidget())
            elif isinstance(self.wellSelectionWidget, widgets.Well1536SelectionWidget):
                self.replaceWellSelectionWidget(widgets.WellSelectionWidget(format_, self.wellplateFormatWidget))
                self.connectWellSelectionWidget()

        if ENABLE_FLEXIBLE_MULTIPOINT:
            self.flexibleMultiPointWidget.clear_only_location_list()
        if ENABLE_WELLPLATE_MULTIPOINT:
            self.wellplateMultiPointWidget.clear_regions()
            self.wellplateMultiPointWidget.set_default_scan_size()
        self.wellSelectionWidget.onSelectionChanged()

    def setupSlidePositionController(self, is_for_wellplate):
        self.slidePositionController.setParent(None)
        self.slidePositionController.deleteLater()
        self.slidePositionController = core.SlidePositionController(self.navigationController, self.liveController, is_for_wellplate=is_for_wellplate)
        self.connectSlidePositionController()

    def connectSlidePositionController(self):
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
        #self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
        #self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
        self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)
        if SHOW_NAVIGATION_BAR:
            self.navigationBarWidget.replace_slide_controller(self.slidePositionController)
        self.navigationWidget.replace_slide_controller(self.slidePositionController)

    def replaceWellSelectionWidget(self, new_widget):
        self.wellSelectionWidget.setParent(None)
        self.wellSelectionWidget.deleteLater()
        self.wellSelectionWidget = new_widget
        self.scanCoordinates.add_well_selector(self.wellSelectionWidget)
        if USE_NAPARI_WELL_SELECTION and not self.performance_mode and not self.live_only_mode:
            self.napariLiveWidget.replace_well_selector(self.wellSelectionWidget)
        else:
            self.dock_wellSelection.addWidget(self.wellSelectionWidget)

    def connectWellSelectionWidget(self):
        #self.wellSelectionWidget.signal_wellSelected.connect(self.multiPointWidget.set_well_selected)
        self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)
        self.wellplateFormatWidget.signalWellplateSettings.connect(self.wellSelectionWidget.updateWellplateSettings)
        if ENABLE_WELLPLATE_MULTIPOINT:
            self.wellSelectionWidget.signal_wellSelected.connect(self.wellplateMultiPointWidget.set_well_coordinates)

    def toggleWellSelector(self, show):
        if USE_NAPARI_WELL_SELECTION and not self.performance_mode and not self.live_only_mode:
            self.napariLiveWidget.toggle_well_selector(show)
        else:
            self.dock_wellSelection.setVisible(show)
        self.wellSelectionWidget.setVisible(show)

    def toggleAcquisitionStart(self, acquisition_started):
        self.navigationWidget.toggle_click_to_move(acquisition_started)
        current_index = self.recordTabWidget.currentIndex()
        for index in range(self.recordTabWidget.count()):
            self.recordTabWidget.setTabEnabled(index, not acquisition_started or index == current_index)
        if acquisition_started:
            self.liveControlWidget.toggle_autolevel(not acquisition_started)
        
        is_scan_grid = (current_index == self.recordTabWidget.indexOf(self.wellplateMultiPointWidget)) if ENABLE_WELLPLATE_MULTIPOINT else False
        if is_scan_grid and self.wellSelectionWidget.format != 'glass slide':
            self.toggleWellSelector(not acquisition_started)

        self.recordTabWidget.currentWidget().display_progress_bar(acquisition_started)
        self.navigationViewer.on_acquisition_start(acquisition_started)

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
            apply_flatfield = self.stitcherWidget.applyFlatfieldCheck.isChecked()
            use_registration = self.stitcherWidget.useRegistrationCheck.isChecked()
            registration_channel = self.stitcherWidget.registrationChannelCombo.currentText()
            registration_z_level = self.stitcherWidget.registrationZCombo.value()
            overlap_percent = self.wellplateMultiPointWidget.entry_overlap.value()
            output_name = acquisitionWidget.lineEdit_experimentID.text() or "stitched"
            output_format = ".ome.zarr" if self.stitcherWidget.outputFormatCombo.currentText() == "OME-ZARR" else ".ome.tiff"

            stitcher_class = stitcher.CoordinateStitcher if self.recordTabWidget.currentIndex() == self.recordTabWidget.indexOf(self.wellplateMultiPointWidget) else stitcher.Stitcher
            self.stitcherThread = stitcher_class(
                input_folder=acquisition_path,
                output_name=output_name,
                output_format=output_format,
                apply_flatfield=apply_flatfield,
                overlap_percent=overlap_percent,
                use_registration=use_registration,
                registration_channel=registration_channel,
                registration_z_level=registration_z_level
            )

            self.stitcherWidget.setStitcherThread(self.stitcherThread)
            self.connectStitcherSignals()
            self.stitcherThread.start()

    def connectStitcherSignals(self):
        self.stitcherThread.update_progress.connect(self.stitcherWidget.updateProgressBar)
        self.stitcherThread.getting_flatfields.connect(self.stitcherWidget.gettingFlatfields)
        self.stitcherThread.starting_stitching.connect(self.stitcherWidget.startingStitching)
        self.stitcherThread.starting_saving.connect(self.stitcherWidget.startingSaving)
        self.stitcherThread.finished_saving.connect(self.stitcherWidget.finishedSaving)

    def closeEvent(self, event):
        self.navigationController.cache_current_position()

        if USE_ZABER_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.set_emission_filter(1)
        if USE_OPTOSPIN_EMISSION_FILTER_WHEEL:
            self.emission_filter_wheel.set_emission_filter(1)
            self.emission_filter_wheel.close()
        if ENABLE_STITCHER:
            self.stitcherWidget.closeEvent(event)
        if SUPPORT_LASER_AUTOFOCUS:
            self.liveController_focus_camera.stop_live()
            self.camera_focus.close()
            self.imageDisplayWindow_focus.close()

        self.liveController.stop_live()
        self.camera.stop_streaming()
        self.camera.close()

        if HOMING_ENABLED_X and HOMING_ENABLED_Y:
            self.navigationController.move_x(0.1)
            self.waitForMicrocontroller()
            self.navigationController.move_x_to(30)
            self.waitForMicrocontroller()
            self.navigationController.move_y(0.1)
            self.waitForMicrocontroller()
            self.navigationController.move_y_to(30)
            self.waitForMicrocontroller()

        self.navigationController.turnoff_axis_pid_control()

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
