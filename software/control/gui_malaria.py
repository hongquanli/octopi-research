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
from control._def import *
import control.core as core
import control.widgets as widgets
import control.camera as camera
import control.microcontroller as microcontroller
if ENABLE_STITCHER:
    import control.stitcher as stitcher

import pyqtgraph.dockarea as dock
import time

SINGLE_WINDOW = True # set to False if use separate windows for display and control

from control.spot_image_display import *

from control.interactive_m2unet_inference import M2UnetInteractiveModel as m2u

class OctopiGUI(QMainWindow):

    # variables
    fps_software_trigger = 100

    def __init__(self, is_simulation = False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # load objects
        if is_simulation:
            self.classification_test_mode = True
            self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
            self.microcontroller = microcontroller.Microcontroller_Simulation()
        else:
            self.classification_test_mode = False
            try:
                self.camera = camera.Camera(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                self.camera.open()
            except:
                self.camera = camera.Camera_Simulation(rotate_image_angle=ROTATE_IMAGE_ANGLE,flip_image=FLIP_IMAGE)
                self.camera.open()
                self.classification_test_mode = True
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

        # core
        self.objectiveStore = core.ObjectiveStore(parent=self)
        self.configurationManager = core.ConfigurationManager()
        self.streamHandler = core.StreamHandler(display_resolution_scaling=DEFAULT_DISPLAY_CROP/100)
        self.liveController = core.LiveController(self.camera,self.microcontroller,self.configurationManager)
        self.navigationController = core.NavigationController(self.microcontroller, self.objectiveStore, parent=self)
        self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
        self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
        self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,parent=self)
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

        # load widgets
        self.objectivesWidget = widgets.ObjectivesWidget(self.objectiveStore)
        self.cameraSettingWidget = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
        self.liveControlWidget = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager,show_display_options=True)
        self.navigationWidget = widgets.NavigationWidget(self.navigationController,self.slidePositionController,widget_configuration='malaria')
        self.dacControlWidget = widgets.DACControWidget(self.microcontroller)
        self.autofocusWidget = widgets.AutoFocusWidget(self.autofocusController)
        self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver)
        self.focusMapWidget = widgets.FocusMapWidget(self.autofocusController)
        if ENABLE_STITCHER:
            self.stitcherWidget = widgets.StitcherWidget(self.configurationManager)
        if ENABLE_TRACKING:
            self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
        self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)
        self.objectivesWidget = widgets.ObjectivesWidget(self.objectiveStore)

        # acquisition tabs
        self.recordTabWidget = QTabWidget()
        if ENABLE_TRACKING:
            self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
            self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
        #self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
        self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")
        if DO_FLUORESCENCE_RTP:
            self.statsDisplayWidget = widgets.StatsDisplayWidget()
            self.dataHandler = DataHandler()
            self.dataHandler.set_number_of_images_per_page(NUM_ROWS*num_cols)
            self.dataHandler_similarity = DataHandler(is_for_similarity_search=True)
            self.dataHandler_similarity.set_number_of_images_per_page(NUM_ROWS*num_cols)
            self.dataHandler_umap_selection = DataHandler(is_for_selected_images=True)
            self.dataHandler_umap_selection.set_number_of_images_per_page(NUM_ROWS*num_cols)
            self.recordTabWidget.addTab(self.statsDisplayWidget, "Detection Stats")
            self.dataLoaderWidget = DataLoaderWidget(self.dataHandler)
            self.gallery = GalleryViewWidget(NUM_ROWS,num_cols,self.dataHandler,is_main_gallery=True)
            self.gallery_similarity = GalleryViewWidget(NUM_ROWS,num_cols,self.dataHandler_similarity,dataHandler2=self.dataHandler,is_for_similarity_search=True)
            self.gallery_umap_selection = GalleryViewWidget(NUM_ROWS,num_cols,self.dataHandler_umap_selection,dataHandler2=self.dataHandler)
            self.gallerySettings = GalleryViewSettingsWidget()
            self.trainingAndVisualizationWidget = TrainingAndVisualizationWidget(self.dataHandler)
            '''
            self.plots = {}
            self.plots['Labels'] = PiePlotWidget()
            self.plots['Annotation Progress'] = BarPlotWidget()
            self.plots['Inference Result'] = HistogramPlotWidget()
            self.plots['Similarity'] = StemPlotWidget()
            self.plots[dimentionality_reduction] = ScatterPlotWidget()
            '''
        self.recordTabWidget.addTab(self.focusMapWidget, "Contrast Focus Map")

        # image display tabs
        self.imageDisplayTabs = QTabWidget()
        if USE_NAPARI_FOR_LIVE_VIEW:
            self.napariLiveWidget = widgets.NapariLiveWidget(self.liveControlWidget)
            self.imageDisplayTabs.addTab(self.napariLiveWidget, "Live View")
        else:
            if ENABLE_TRACKING:
                self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
                self.imageDisplayWindow.show_ROI_selector()
            else:
                self.imageDisplayWindow = core.ImageDisplayWindow(draw_crosshairs=True)
            self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")

        if USE_NAPARI_FOR_MULTIPOINT:
            self.napariMultiChannelWidget = widgets.NapariMultiChannelWidget(self.objectiveStore)
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

        if DO_FLUORESCENCE_RTP:
            if USE_NAPARI_FOR_MULTIPOINT:
                self.napariRTPWidget = widgets.NapariMultiChannelWidget(grid_enabled=True)
                self.imageDisplayTabs.addTab(self.napariRTPWidget, "Segmentation")
            self.imageDisplayTabs.addTab(self.gallery, "Detection Result")

        # layout widgets
        frame = QFrame()
        frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
        # Creating the top row layout and adding widgets
        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(self.objectivesWidget)
        frame.setLayout(top_row_layout)  # Set the layout on the frame
        layout = QVBoxLayout() #layout = QStackedLayout()
        layout.addWidget(frame)
        # layout.addWidget(self.cameraSettingWidget)
        # layout.addWidget(self.dataLoaderWidget)
        # layout.addWidget(self.gallerySettings)
        # self.gallery_tab = QTabWidget()
        # self.gallery_tab.addTab(self.gallery,'Full Dataset')
        # layout.addWidget(self.gallery_tab)
        # layout.addWidget(self.trainingAndVisualizationWidget)
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
        self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
        # self.streamHandler.packet_image_for_tracking.connect(self.trackingController.on_new_frame)
        self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x)))
        self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x)))
        self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x)))
        self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
        self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)
        self.objectivesWidget.signal_objective_changed.connect(self.navigationViewer.on_objective_changed)
        self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
        self.multiPointWidget.signal_acquisition_started.connect(self.navigationWidget.toggle_navigation_controls)

        if DO_FLUORESCENCE_RTP:
            self.multipointController.detection_stats.connect(self.statsDisplayWidget.display_stats)

        if ENABLE_TRACKING:
            self.navigationController.signal_joystick_button_pressed.connect(self.trackingControlWidget.slot_joystick_button_pressed)
        else:
            self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)

        if ENABLE_STITCHER:
            self.multipointController.signal_stitcher.connect(self.startStitcher)
            self.multiPointWidget.signal_stitcher_widget.connect(self.toggleStitcherWidget)
            self.multiPointWidget.signal_acquisition_channels.connect(self.stitcherWidget.updateRegistrationChannels) # change enabled registration channels

        if USE_NAPARI_FOR_LIVE_VIEW:
            self.autofocusController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=True))
            self.streamHandler.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.multipointController.image_to_display.connect(lambda image: self.napariLiveWidget.updateLiveLayer(image, from_autofocus=False))
            self.napariLiveWidget.signal_coordinates_clicked.connect(self.navigationController.move_from_click)
            if ENABLE_STITCHER:
                self.napariLiveWidget.signal_layer_contrast_limits.connect(self.stitcherWidget.saveContrastLimits)
        else:
            self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
            self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image)
            self.imageDisplayWindow.image_click_coordinates.connect(self.navigationController.move_from_click)

        if USE_NAPARI_FOR_MULTIPOINT:
            self.multiPointWidget.signal_acquisition_channels.connect(self.napariMultiChannelWidget.initChannels)
            self.multiPointWidget.signal_acquisition_shape.connect(self.napariMultiChannelWidget.initLayersShape)
            self.multipointController.napari_layers_init.connect(self.napariMultiChannelWidget.initLayers)
            self.multipointController.napari_layers_update.connect(self.napariMultiChannelWidget.updateLayers)
            if ENABLE_STITCHER:
                self.napariMultiChannelWidget.signal_layer_contrast_limits.connect(self.stitcherWidget.saveContrastLimits)
            if DO_FLUORESCENCE_RTP:
                self.multipointController.napari_rtp_layers_update.connect(self.napariRTPWidget.updateRTPLayers)
            if USE_NAPARI_FOR_LIVE_VIEW:
                self.napariMultiChannelWidget.signal_layer_contrast_limits.connect(self.napariLiveWidget.saveContrastLimits)
                self.napariLiveWidget.signal_layer_contrast_limits.connect(self.napariMultiChannelWidget.saveContrastLimits)
        else:
            self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)

        if SHOW_TILED_PREVIEW:
            if USE_NAPARI_FOR_TILED_DISPLAY:
                self.multiPointWidget.signal_acquisition_channels.connect(self.napariTiledDisplayWidget.initChannels)
                self.multiPointWidget.signal_acquisition_shape.connect(self.napariTiledDisplayWidget.initLayersShape)
                self.multipointController.napari_layers_init.connect(self.napariTiledDisplayWidget.initLayers)
                self.multipointController.napari_layers_update.connect(self.napariTiledDisplayWidget.updateLayers)
                self.napariTiledDisplayWidget.signal_coordinates_clicked.connect(self.navigationController.scan_preview_move_from_click)
                if ENABLE_STITCHER:
                    self.napariTiledDisplayWidget.signal_layer_contrast_limits.connect(self.stitcherWidget.saveContrastLimits)
                if USE_NAPARI_FOR_LIVE_VIEW:
                    self.napariTiledDisplayWidget.signal_layer_contrast_limits.connect(self.napariLiveWidget.saveContrastLimits)
                    self.napariLiveWidget.signal_layer_contrast_limits.connect(self.napariTiledDisplayWidget.saveContrastLimits)
                if USE_NAPARI_FOR_MULTIPOINT:
                    self.napariTiledDisplayWidget.signal_layer_contrast_limits.connect(self.napariMultiChannelWidget.saveContrastLimits)
                    self.napariMultiChannelWidget.signal_layer_contrast_limits.connect(self.napariTiledDisplayWidget.saveContrastLimits)
            else:
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

        if DO_FLUORESCENCE_RTP:
            # connect
            self.dataHandler.signal_set_total_page_count.connect(self.gallery.set_total_pages)
            self.dataHandler.signal_populate_page0.connect(self.gallery.populate_page0)

            self.dataHandler_similarity.signal_set_total_page_count.connect(self.gallery_similarity.set_total_pages)
            self.dataHandler_similarity.signal_populate_page0.connect(self.gallery_similarity.populate_page0)

            self.dataHandler_umap_selection.signal_set_total_page_count.connect(self.gallery_umap_selection.set_total_pages)
            self.dataHandler_umap_selection.signal_populate_page0.connect(self.gallery_umap_selection.populate_page0)

            # similarity search
            self.gallery.signal_similaritySearch.connect(self.dataHandler_similarity.populate_similarity_search)
            # signal_updatePage will only be emitted by non-main galleries - (annotating in other galleries will not change the displayed annotations in the current page of the main gallery)

            self.gallery_similarity.signal_similaritySearch.connect(self.dataHandler_similarity.populate_similarity_search)
            self.gallery_similarity.signal_updatePage.connect(self.gallery.update_page)

            self.gallery_umap_selection.signal_similaritySearch.connect(self.dataHandler_similarity.populate_similarity_search)
            self.gallery_umap_selection.signal_updatePage.connect(self.gallery.update_page)

            # get selected images in UMAP scatter plot
            ##self.plots[dimentionality_reduction].signal_selected_points.connect(self.dataHandler.prepare_selected_images)
            self.dataHandler.signal_selected_images.connect(self.dataHandler_umap_selection.populate_selected_images)

            # show selected images in UMAP
            self.gallery.signal_selected_images_idx_for_umap.connect(self.dataHandler.to_umap_embedding)
            self.gallery_similarity.signal_selected_images_idx_for_umap.connect(self.dataHandler.to_umap_embedding)
            self.gallery_umap_selection.signal_selected_images_idx_for_umap.connect(self.dataHandler.to_umap_embedding)

            #self.dataHandler.signal_umap_embedding.connect(self.plots[dimentionality_reduction].show_points)

            # clear the overlay when images are de-selected
            #self.gallery.signal_selection_cleared.connect(self.plots[dimentionality_reduction].clear_overlay)
            #self.gallery_similarity.signal_selection_cleared.connect(self.plots[dimentionality_reduction].clear_overlay)
            #self.gallery_umap_selection.signal_selection_cleared.connect(self.plots[dimentionality_reduction].clear_overlay)

            # gallery settings
            self.gallerySettings.signal_numRowsPerPage.connect(self.gallery.set_number_of_rows)
            self.gallerySettings.signal_numImagesPerPage.connect(self.dataHandler.set_number_of_images_per_page)
            self.gallerySettings.signal_k_similaritySearch.connect(self.dataHandler.set_k_similar)

            self.gallerySettings.signal_numImagesPerPage.connect(self.dataHandler_similarity.set_number_of_images_per_page)
            self.gallerySettings.signal_numRowsPerPage.connect(self.gallery_similarity.set_number_of_rows)
            self.gallerySettings.signal_k_similaritySearch.connect(self.dataHandler_similarity.set_k_similar)

            self.gallerySettings.signal_numImagesPerPage.connect(self.dataHandler_umap_selection.set_number_of_images_per_page)
            self.gallerySettings.signal_numRowsPerPage.connect(self.gallery_umap_selection.set_number_of_rows)
            self.gallerySettings.signal_k_similaritySearch.connect(self.dataHandler_umap_selection.set_k_similar)

            # plots
            '''
            self.dataHandler.signal_annotation_stats.connect(self.plots['Labels'].update_plot)
            self.dataHandler.signal_annotation_stats.connect(self.plots['Annotation Progress'].update_plot)
            self.dataHandler.signal_predictions.connect(self.plots['Inference Result'].update_plot)
            self.dataHandler.signal_distances.connect(self.plots['Similarity'].update_plot)
            self.dataHandler.signal_UMAP_visualizations.connect(self.plots[dimentionality_reduction].update_plot)
            '''

            # dev mode
            if False:
                annotation_pd = pd.read_csv('tmp/score.csv',index_col='index')
                images = np.load('tmp/test.npy')
                self.dataHandler.load_images(images)
                self.dataHandler.load_predictions(annotation_pd)
                self.dataHandler.add_data(images,annotation_pd)

            # deep learning classification
            self.classification_th = CLASSIFICATION_TH
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            # model
            #model_path = 'tmp/model_perf_r34_b32.pt'
            model_path = CLASSIFICATION_MODEL_PATH

            self.model = models.ResNet(model='resnet18', n_channels=4, n_classes=2)  # Adjust parameters as needed
            state_dict = torch.load(model_path, map_location=torch.device('cpu') if not torch.cuda.is_available() else None)
            self.model.load_state_dict(state_dict)
            self.model = self.model.to(self.device)

            if TWO_CLASSIFICATION_MODELS:
                model_path2 = CLASSIFICATION_MODEL_PATH2
                self.model2 = models.ResNet(model='resnet18', n_channels=4, n_classes=2)  # Adjust parameters as needed
                state_dict = torch.load(model_path, map_location=torch.device('cpu') if not torch.cuda.is_available() else None)
                self.model2.load_state_dict(state_dict)
                self.model2 = self.model2.to(self.device)
            else:
                self.model2 = None

            dummy_input = torch.randn(256, 4, 31, 31)  # Adjust as per your input shape
            if torch.cuda.is_available():
                dummy_input = dummy_input.cuda()
            dummy_model = self.model(dummy_input)
            if TWO_CLASSIFICATION_MODELS:
                dummy_model2 = self.model2(dummy_input)
            #model_path = 'models/m2unet_model_flat_erode1_wdecay5_smallbatch/model_4000_11.pth'
            #segmentation_model_path=SEGMENTATION_MODEL_PATH
            segmentation_model_path = 'models/m2unet_model_flat_erode1_wdecay5_smallbatch/model_4000_11.pth'
            assert os.path.exists(segmentation_model_path)
            use_trt_segmentation=USE_TRT_SEGMENTATION
            self.segmentation_model = m2u(pretrained_model=segmentation_model_path, use_trt=use_trt_segmentation)
            # run some dummy data thru model - warm-up
            dummy_data = (255 * np.random.rand(3000,3000)).astype(np.uint8)
            self.segmentation_model.predict_on_images(dummy_data)
            del dummy_input
            del dummy_data
            print('done')

        self.navigationController.move_to_cached_position()

    def toggleStitcherWidget(self, checked):
        central_layout = self.centralWidget.layout()
        if checked:
            central_layout.insertWidget(central_layout.count() - 2, self.stitcherWidget)
            self.stitcherWidget.show()
        else:
            central_layout.removeWidget(self.stitcherWidget)
            self.stitcherWidget.hide()
            self.stitcherWidget.setParent(None)

    def startStitcher(self, acquisition_path):
        if self.multiPointWidget.checkbox_stitchOutput.isChecked():
            # Fetch settings from StitcherWidget controls
            apply_flatfield = self.stitcherWidget.applyFlatfieldCheck.isChecked()
            use_registration = self.stitcherWidget.useRegistrationCheck.isChecked()
            registration_channel = self.stitcherWidget.registrationChannelCombo.currentText()
            output_name = self.multiPointWidget.lineEdit_experimentID.text()
            if output_name == "":
                output_name = "stitched"
            output_format = ".ome.zarr" if self.stitcherWidget.outputFormatCombo.currentText() == "OME-ZARR" else ".ome.tiff"

            self.stitcherThread = stitcher.Stitcher(input_folder=acquisition_path, output_name=output_name, output_format=output_format,
                                           apply_flatfield=apply_flatfield, use_registration=use_registration, registration_channel=registration_channel)

            # Connect signals to slots
            self.stitcherThread.update_progress.connect(self.stitcherWidget.updateProgressBar)
            self.stitcherThread.getting_flatfields.connect(self.stitcherWidget.gettingFlatfields)
            self.stitcherThread.starting_stitching.connect(self.stitcherWidget.startingStitching)
            self.stitcherThread.starting_saving.connect(self.stitcherWidget.startingSaving)
            self.stitcherThread.finished_saving.connect(self.stitcherWidget.finishedSaving)
            # Start the thread
            self.stitcherThread.start()

    def closeEvent(self, event):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

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

    def toggleStitcherWidget(self, checked):
        central_layout = self.centralWidget.layout()
        if checked:
            central_layout.insertWidget(central_layout.count() - 2, self.stitcherWidget)
            self.stitcherWidget.show()
        else:
            central_layout.removeWidget(self.stitcherWidget)
            self.stitcherWidget.hide()
            self.stitcherWidget.setParent(None)

    def startStitcher(self, acquisition_path):
        if self.multiPointWidget.checkbox_stitchOutput.isChecked():
            # Fetch settings from StitcherWidget controls
            apply_flatfield = self.stitcherWidget.applyFlatfieldCheck.isChecked()
            use_registration = self.stitcherWidget.useRegistrationCheck.isChecked()
            registration_channel = self.stitcherWidget.registrationChannelCombo.currentText()
            output_name = self.multiPointWidget.lineEdit_experimentID.text()
            if output_name == "":
                output_name = "stitched"
            output_format = ".ome.zarr" if self.stitcherWidget.outputFormatCombo.currentText() == "OME-ZARR" else ".ome.tiff"

            self.stitcherThread = core.Stitcher(input_folder=acquisition_path,
                                                output_name=output_name, output_format=output_format,
                                                apply_flatfield=apply_flatfield,
                                                use_registration=use_registration, registration_channel=registration_channel)

            # Connect signals to slots
            self.stitcherThread.update_progress.connect(self.stitcherWidget.updateProgressBar)
            self.stitcherThread.getting_flatfields.connect(self.stitcherWidget.gettingFlatfields)
            self.stitcherThread.starting_stitching.connect(self.stitcherWidget.startingStitching)
            self.stitcherThread.starting_saving.connect(self.stitcherWidget.startingSaving)
            self.stitcherThread.finished_saving.connect(self.stitcherWidget.finishedSaving)
            # Start the thread
            self.stitcherThread.start()
