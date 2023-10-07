# set QT_API environment variable
import os 
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

from control.spot_image_display import *

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
		self.imageArrayDisplayWindow = core.ImageArrayDisplayWindow() 
		# self.imageDisplayWindow.show()
		# self.imageArrayDisplayWindow.show()

		# image display windows
		self.imageDisplayTabs = QTabWidget()
		self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
		self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

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
		self.navigationController = core.NavigationController(self.microcontroller)
		self.slidePositionController = core.SlidePositionController(self.navigationController,self.liveController)
		self.autofocusController = core.AutoFocusController(self.camera,self.navigationController,self.liveController)
		self.multipointController = core.MultiPointController(self.camera,self.navigationController,self.liveController,self.autofocusController,self.configurationManager,parent=self)
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
				exit()
		print('objective retracted')

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


		# raise the objective
		self.navigationController.move_z(DEFAULT_Z_POS_MM)
		# wait for the operation to finish
		t0 = time.time() 
		while self.microcontroller.is_busy():
			time.sleep(0.005)
			if time.time() - t0 > 5:
				print('z return timeout, the program will exit')
				exit()

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
		if ENABLE_TRACKING:
			self.trackingControlWidget = widgets.TrackingControllerWidget(self.trackingController,self.configurationManager,show_configurations=TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS)
		self.multiPointWidget = widgets.MultiPointWidget(self.multipointController,self.configurationManager)

		self.recordTabWidget = QTabWidget()
		if ENABLE_TRACKING:
			self.recordTabWidget.addTab(self.trackingControlWidget, "Tracking")
		#self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
		self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")

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

		# Display of detection result
		# core
		self.dataHandler = DataHandler()
		self.dataHandler.set_number_of_images_per_page(NUM_ROWS*num_cols)

		self.dataHandler_similarity = DataHandler(is_for_similarity_search=True)
		self.dataHandler_similarity.set_number_of_images_per_page(NUM_ROWS*num_cols)

		self.dataHandler_umap_selection = DataHandler(is_for_selected_images=True)
		self.dataHandler_umap_selection.set_number_of_images_per_page(NUM_ROWS*num_cols)

		# widgets
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

		# tab widget
		self.gallery_tab = QTabWidget()
		self.gallery_tab.addTab(self.gallery,'Full Dataset')
		#self.gallery_tab.addTab(self.gallery_similarity,'Similarity Search')
		#self.gallery_tab.addTab(self.gallery_umap_selection,dimentionality_reduction + ' Selection')

		# layout = QVBoxLayout()
		# #layout.addWidget(self.dataLoaderWidget)
		# #layout.addWidget(self.gallerySettings)
		# layout.addWidget(self.gallery_tab)
		# #layout.addWidget(self.trainingAndVisualizationWidget)

		# centralWidget = QWidget()
		# centralWidget.setLayout(layout)
		# #self.setCentralWidget(centralWidget)

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

		self.imageDisplayTabs.addTab(self.gallery, "Detection Result")

		# dev mode
		if False:

			annotation_pd = pd.read_csv('/home/cephla/Documents/tmp/score.csv',index_col='index')
			images = np.load('/home/cephla/Documents/tmp/test.npy')
			self.dataHandler.load_images(images)
			self.dataHandler.load_predictions(annotation_pd)

			self.dataHandler.add_data(images,annotation_pd)

		# deep learning classification
		self.classification_th = 0.8
		# model
		model_path = '/home/cephla/Documents/tmp/model_perf_r34_b32.pt'
		if torch.cuda.is_available():
		    self.model = torch.load(model_path)
		else:
		    self.model = torch.load(model_path,map_location=torch.device('cpu'))
		    print('<<< using cpu >>>')

		# cuda
		self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
		self.model = self.model.to(self.device)
		dummy_input = torch.randn(1024, 4, 31, 31)  # Adjust as per your input shape
		if torch.cuda.is_available():
		    dummy_input = dummy_input.cuda()
		_ = self.model(dummy_input)

	def closeEvent(self, event):
		event.accept()
		# self.softwareTriggerGenerator.stop() @@@ => 
		self.navigationController.home()
		self.liveController.stop_live()
		self.camera.close()
		self.imageSaver.close()
		self.imageDisplay.close()
		if not SINGLE_WINDOW:
			self.imageDisplayWindow.close()
			self.imageArrayDisplayWindow.close()
			self.tabbedImageDisplayWindow.close()
		self.microcontroller.close()


	
