# set QT_API environment variable
import os
os.environ["QT_API"] = "pyqt5"

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
from control._def import *

import pyqtgraph.dockarea as dock
import time

SINGLE_WINDOW = True # set to False if use separate windows for display and control

class MalariaGUI(QMainWindow):

    # variables
    fps_software_trigger = 100

    def __init__(self, is_simulation = False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log = squid.logging.get_logger(self.__class__.__name__)

        # load objects
        if is_simulation:
            self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            self.microcontroller = microcontroller.Microcontroller(existing_serial=microcontroller.SimSerial())
        else:
            try:
                self.camera = camera.Camera(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                self.camera.open()
            except:
                self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                self.camera.open()
                self.log.error("camera not detected, using simulated camera")
            try:
                self.microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)
            except:
                self.log.error("Microcontroller not detected, using simulated microcontroller")
                self.microcontroller = microcontroller.Microcontroller(existing_serial=microcontroller.SimSerial())

        # reset the MCU
        self.microcontroller.reset()

        # reinitialize motor drivers and DAC (in particular for V2.1 driver board where PG is not functional)
        self.microcontroller.initialize_drivers()

        # configure the actuators
        self.microcontroller.configure_actuators()
        self.objectiveStore = core.ObjectiveStore(parent=self)
        self.scanCoordinates = core.ScanCoordinates()
        self.configurationManager = core.ConfigurationManager()
        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
        self.navigationController = core.NavigationController(self.microcontroller, self.objectiveStore, parent=self)
        self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
        self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
        self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager)
        if ENABLE_TRACKING:
            self.trackingController = core.TrackingController(self.camera,self.microcontroller,self.navigationController,self.configurationManager,self.liveController,self.autofocusController,self.imageDisplayWindow)
        self.imageSaver = core.ImageSaver()
        self.imageDisplay = core.ImageDisplay()
        self.navigationViewer = core.NavigationViewer(self.objectiveStore)

        # retract the objective
        self.navigationController.home_z()
        # wait for the operation to finish
        t0 = time.time()
        while self.microcontroller.is_busy():
            time.sleep(0.005)
            if time.time() - t0 > 10:
                self.log.error('z homing timeout, the program will exit')
                sys.exit(1)
        self.log.info('objective retracted')

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
        self.log.info("start homing")
        self.slidePositionController.move_to_slide_scanning_position()
        while self.slidePositionController.slide_scanning_position_reached == False:
            time.sleep(0.005)
        self.log.info("homing finished")
        self.navigationController.set_x_limit_pos_mm(SOFTWARE_POS_LIMIT.X_POSITIVE)
        self.navigationController.set_x_limit_neg_mm(SOFTWARE_POS_LIMIT.X_NEGATIVE)
        self.navigationController.set_y_limit_pos_mm(SOFTWARE_POS_LIMIT.Y_POSITIVE)
        self.navigationController.set_y_limit_neg_mm(SOFTWARE_POS_LIMIT.Y_NEGATIVE)

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

        # only toupcam need reset strobe argument when camera's argument change 
        if CAMERA_TYPE == "Toupcam":
            self.camera.set_reset_strobe_delay_function(self.liveController.reset_strobe_arugment)

        # load widgets
        self.objectivesWidget = widgets.ObjectivesWidget(self.objectiveStore)
        self.contrastManager = core.ContrastManager()
        self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera, include_gain_exposure_time=False)
        self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True)
        self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='malaria')
        self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
        self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
        self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
        self.focusMapWidget = widgets.FocusMapWidget(self.autofocusController)
        if ENABLE_TRACKING:
            self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
        
        self.imageDisplayTabs = QTabWidget()
        if USE_NAPARI_FOR_LIVE_VIEW:
            self.napariLiveWidget = widgets.NapariLiveWidget(self.streamHandler, self.liveController, self.navigationController, self.configurationManager, self.contrastManager)
            self.imageDisplayTabs.addTab(self.napariLiveWidget, "Live View")
        else:
            if ENABLE_TRACKING:
                self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
                self.imageDisplayWindow.show_ROI_selector()
            else:
                self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
            self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")

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

        self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)
        self.multiPointWidgetGrid = widgets.MultiPointWidgetGrid(self.navigationController, self.navigationViewer, self.multipointController, self.objectiveStore, self.configurationManager, self.scanCoordinates, self.napariMosaicDisplayWidget)

        self.recordTabWidget = QTabWidget()
        self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")
        if ENABLE_SCAN_GRID:
            self.recordTabWidget.addTab(self.multiPointWidgetGrid, "Auto-Grid Multipoint")
        self.recordTabWidget.addTab(self.focusMapWidget, "Contrast Focus Map")
        if ENABLE_TRACKING:
            self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
        #self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
        self.recordTabWidget.currentChanged.connect(lambda: self.resizeCurrentTab(self.recordTabWidget))
        self.resizeCurrentTab(self.recordTabWidget)

        frame = QFrame()
        frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
        # Creating the top row layout and adding widgets
        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(self.objectivesWidget)
        top_row_layout.setContentsMargins(1, 1, 1, 1)
        frame.setLayout(top_row_layout)  # Set the layout on the frame


        # layout widgets
        layout = QVBoxLayout()
        #layout.addWidget(self.cameraSettingWidget)
        layout.addWidget(self.liveControlWidget)
        layout.addWidget(self.navigationWidget)
        if SHOW_DAC_CONTROL:
            layout.addWidget(self.dacControlWidget)
        layout.addWidget(self.autofocusWidget)
        layout.addWidget(self.recordTabWidget)
        layout.addWidget(frame)
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
        self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
        # self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
        self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x)))
        self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x)))
        self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x)))
        if ENABLE_TRACKING:
            self.navigationController.signal_joystick_button_pressed.connect(self.trackingControlWidget.slot_joystick_button_pressed)
        else:
            self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)
        self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
        self.multiPointWidget.signal_acquisition_started.connect(self.navigationWidget.toggle_navigation_controls)
        if ENABLE_SCAN_GRID:
            self.multiPointWidgetGrid.signal_acquisition_started.connect(self.navigationWidget.toggle_navigation_controls)

        if USE_NAPARI_FOR_LIVE_VIEW:
            self.autofocusController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=True))
            self.streamHandler.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.multipointController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.napariLiveWidget.signal_coordinates_clicked.connect(self.navigationController.move_from_click)
        else:
            self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
            self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.imageDisplayWindow.image_click_coordinates.connect(self.navigationController.move_from_click)

        if USE_NAPARI_FOR_MULTIPOINT:
            self.multiPointWidget.signal_acquisition_channels.connect(self.napariMultiChannelWidget.initChannels)
            self.multiPointWidget.signal_acquisition_shape.connect(self.napariMultiChannelWidget.initLayersShape)
            if ENABLE_SCAN_GRID:
                self.multiPointWidgetGrid.signal_acquisition_channels.connect(self.napariMultiChannelWidget.initChannels)
                self.multiPointWidgetGrid.signal_acquisition_shape.connect(self.napariMultiChannelWidget.initLayersShape)

            self.multipointController.napari_layers_init.connect(self.napariMultiChannelWidget.initLayers)
            self.multipointController.napari_layers_update.connect(self.napariMultiChannelWidget.updateLayers)

        else:
            self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)

        if SHOW_TILED_PREVIEW:
            if USE_NAPARI_FOR_TILED_DISPLAY:
                self.multiPointWidget.signal_acquisition_channels.connect(self.napariTiledDisplayWidget.initChannels)
                self.multiPointWidget.signal_acquisition_shape.connect(self.napariTiledDisplayWidget.initLayersShape)
                if ENABLE_SCAN_GRID:
                    self.multiPointWidgetGrid.signal_acquisition_channels.connect(self.napariTiledDisplayWidget.initChannels)
                    self.multiPointWidgetGrid.signal_acquisition_shape.connect(self.napariTiledDisplayWidget.initLayersShape)

                self.multipointController.napari_layers_init.connect(self.napariTiledDisplayWidget.initLayers)
                self.multipointController.napari_layers_update.connect(self.napariTiledDisplayWidget.updateLayers)
                self.napariTiledDisplayWidget.signal_coordinates_clicked.connect(self.navigationController.scan_preview_move_from_click)

            else:
                self.multipointController.image_to_display_tiled_preview.connect(self.imageDisplayWindow_scan_preview.display_image)
                self.imageDisplayWindow_scan_preview.image_click_coordinates.connect(self.navigationController.scan_preview_move_from_click)

        if USE_NAPARI_FOR_MOSAIC_DISPLAY:
            self.multiPointWidget.signal_acquisition_channels.connect(self.napariMosaicDisplayWidget.initChannels)
            self.multiPointWidget.signal_acquisition_shape.connect(self.napariMosaicDisplayWidget.initLayersShape)
            if ENABLE_SCAN_GRID:
                self.multiPointWidgetGrid.signal_acquisition_channels.connect(self.napariMosaicDisplayWidget.initChannels)
                self.multiPointWidgetGrid.signal_acquisition_shape.connect(self.napariMosaicDisplayWidget.initLayersShape)
                self.multiPointWidgetGrid.signal_draw_shape.connect(self.napariMosaicDisplayWidget.enable_shape_drawing)
                self.napariMosaicDisplayWidget.signal_shape_drawn.connect(self.multiPointWidgetGrid.update_manual_shape)

            self.multipointController.napari_mosaic_update.connect(self.napariMosaicDisplayWidget.updateMosaic)
            self.napariMosaicDisplayWidget.signal_coordinates_clicked.connect(self.navigationController.move_from_click_mosaic)
            self.napariMosaicDisplayWidget.signal_update_viewer.connect(self.navigationViewer.update_slide)

        self.liveControlWidget.signal_newExposureTime.connect(self.cameraSettingWidget.set_exposure_time)
        self.liveControlWidget.signal_newAnalogGain.connect(self.cameraSettingWidget.set_analog_gain)
        self.liveControlWidget.update_camera_settings()

        self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
        self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)
        self.objectivesWidget.signal_objective_changed.connect(self.navigationViewer.on_objective_changed)
        self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
        self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)

        self.navigationController.move_to_cached_position()

    def resizeCurrentTab(self, tabWidget):
        current_widget = tabWidget.currentWidget()
        if current_widget:
            total_height = current_widget.sizeHint().height() + tabWidget.tabBar().height()
            tabWidget.resize(tabWidget.width(), total_height)
            tabWidget.setMaximumHeight(total_height)
            tabWidget.updateGeometry()
            self.updateGeometry()

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
