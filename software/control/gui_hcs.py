# qt libraries
from qtpy.QtCore import Qt, QEvent
from qtpy.QtWidgets import QMainWindow, QTabWidget, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDesktopWidget, QSlider, QCheckBox

import numpy

# app specific libraries
import control.widgets as widgets
import control.camera as camera
import control.core as core
import control.microcontroller as microcontroller
from control.hcs import HCSController
from control._def import *

import pyqtgraph as pg
import pyqtgraph.dockarea as dock

from PIL import ImageEnhance, Image
import time

from control.typechecker import TypecheckFunction
from typing import Union

class OctopiGUI(QMainWindow):

    # variables
    fps_software_trigger = 100

    @property
    def configurationManager(self)->core.ConfigurationManager:
        return self.hcs_controller.configurationManager
    @property
    def streamHandler(self)->core.StreamHandler:
        return self.hcs_controller.streamHandler
    @property
    def liveController(self)->core.LiveController:
        return self.hcs_controller.liveController
    @property
    def navigationController(self)->core.NavigationController:
        return self.hcs_controller.navigationController
    @property
    def slidePositionController(self)->core.SlidePositionController:
        return self.hcs_controller.slidePositionController
    @property
    def autofocusController(self)->core.AutoFocusController:
        return self.hcs_controller.autofocusController
    @property
    def multipointController(self)->core.MultiPointController:
        return self.hcs_controller.multipointController
    @property
    def imageSaver(self)->core.ImageSaver:
        return self.hcs_controller.imageSaver
    @property
    def camera(self)->camera.Camera:
        return self.hcs_controller.camera
    @property
    def microcontroller(self)->microcontroller.Microcontroller:
        return self.hcs_controller.microcontroller

    @TypecheckFunction
    def start_experiment(self,experiment_data_target_folder:str,imaging_channel_list:List[str]):
        self.navigationViewer.register_preview_fovs()

        well_list=self.wellSelectionWidget.currently_selected_well_indices

        af_channel=self.multipointController.autofocus_channel_name if self.multipointController.do_autofocus else None

        self.hcs_controller.acquire(
            well_list,
            imaging_channel_list,
            experiment_data_target_folder,
            grid_data={
                'x':{'d':self.multipointController.deltaX,'N':self.multipointController.NX},
                'y':{'d':self.multipointController.deltaY,'N':self.multipointController.NY},
                'z':{'d':self.multipointController.deltaZ,'N':self.multipointController.NZ},
                't':{'d':self.multipointController.deltat,'N':self.multipointController.Nt},
            },
            af_channel=af_channel,
            set_num_acquisitions_callback=self.set_num_acquisitions,
            on_new_acquisition=self.on_step_completed,
        )

    def set_num_acquisitions(self,num:int):
        self.acquisition_progress=0
        self.total_num_acquisitions=num
        self.acquisition_start_time=time.monotonic()
        self.multiPointWidget.progress_bar.setValue(0)
        self.multiPointWidget.progress_bar.setMinimum(0)
        self.multiPointWidget.progress_bar.setMaximum(num)

    def on_step_completed(self,step:str):
        if step=="x": # x (in well)
            pass
        elif step=="y": # y (in well)
            pass
        elif step=="z": # z (in well)
            pass
        elif step=="t": # time
            pass
        elif step=="c": # channel
            # this is the innermost callback
            # for each one of these, one image is actually taken

            self.acquisition_progress+=1
            self.multiPointWidget.progress_bar.setValue(self.acquisition_progress)

            time_elapsed_since_start=time.monotonic()-self.acquisition_start_time
            approx_time_left=time_elapsed_since_start/self.acquisition_progress*(self.total_num_acquisitions-self.acquisition_progress)
            self.multiPointWidget.progress_bar.setFormat(f"completed {self.acquisition_progress:4}/{self.total_num_acquisitions:4} in {time_elapsed_since_start:8.1f}s (eta: {approx_time_left:8.1f}s)")

    def abort_experiment(self):
        self.multipointController.request_abort_aquisition()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hcs_controller=HCSController()

        # load window
        self.imageDisplayWindow = widgets.ImageDisplayWindow(draw_crosshairs=True)
        self.imageArrayDisplayWindow = widgets.ImageArrayDisplayWindow(self.configurationManager,window_title="HCS microscope control")

        # image display windows
        self.imageDisplayTabs = QTabWidget()
        self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
        self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

        # these widgets are used by a controller (which already tells us that there is something very wrong!)
        default_well_plate=WELLPLATE_NAMES[MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT]
        self.wellSelectionWidget = widgets.WellSelectionWidget(MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT)
        
        # open the camera
        self.camera.set_software_triggered_acquisition()
        self.camera.set_callback(self.streamHandler.on_new_frame)
        self.camera.enable_callback()

        # load widgets
        self.imageDisplay           = widgets.ImageDisplay()
        self.liveControlWidget      = widgets.LiveControlWidget(self.hcs_controller.streamHandler,self.hcs_controller.liveController,self.hcs_controller.configurationManager,show_display_options=True)
        self.navigationWidget       = widgets.NavigationWidget(self.hcs_controller.navigationController,self.hcs_controller.slidePositionController,widget_configuration=default_well_plate)
        self.dacControlWidget       = widgets.DACControWidget(self.microcontroller)
        self.autofocusWidget        = widgets.AutoFocusWidget(self.hcs_controller.autofocusController)
        self.recordingControlWidget = widgets.RecordingWidget(self.hcs_controller.streamHandler,self.hcs_controller.imageSaver)
        self.multiPointWidget       = widgets.MultiPointWidget(self.hcs_controller.multipointController,self.hcs_controller.configurationManager,self.start_experiment,self.abort_experiment)
        self.navigationViewer       = widgets.NavigationViewer(sample=default_well_plate)

        self.recordTabWidget = QTabWidget()
        #self.recordTabWidget.addTab(self.recordingControlWidget, "Simple Recording")
        self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")

        clear_history_button=QPushButton("clear history")
        clear_history_button.clicked.connect(self.navigationViewer.clear_imaged_positions)

        wellplate_selector=QComboBox()
        wellplate_types_str=list(WELLPLATE_NAMES.values())
        wellplate_selector.addItems(wellplate_types_str)
        # disable 6 and 24 well wellplates, because the images displaying them are missing
        for wpt in [0,2]:
            item=wellplate_selector.model().item(wpt)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled) # type: ignore
        wellplate_selector.setCurrentIndex(wellplate_types_str.index(default_well_plate))
        wellplate_selector.currentIndexChanged.connect(lambda wellplate_type_index:setattr(MUTABLE_MACHINE_CONFIG,"WELLPLATE_FORMAT",tuple(WELLPLATE_FORMATS.keys())[wellplate_type_index]))
 
        wellplate_overview_header=QHBoxLayout()
        wellplate_overview_header.addWidget(QLabel("wellplate overview"))
        wellplate_overview_header.addWidget(clear_history_button)
        wellplate_overview_header.addWidget(QLabel("change plate type:"))
        wellplate_overview_header.addWidget(wellplate_selector)

        self.navigationViewWrapper=QVBoxLayout()
        self.navigationViewWrapper.addLayout(wellplate_overview_header)
        self.navigationViewWrapper.addWidget(self.navigationViewer)

        self.add_image_format_options()
        self.add_image_inspection()

        # layout widgets
        layout = QVBoxLayout()
        layout.addLayout(self.image_pixel_format_widgets)
        layout.addWidget(self.liveControlWidget)
        layout.addWidget(self.navigationWidget)
        if MACHINE_DISPLAY_CONFIG.SHOW_DAC_CONTROL:
            layout.addWidget(self.dacControlWidget)
        layout.addWidget(self.autofocusWidget)
        layout.addWidget(self.recordTabWidget)
        layout.addLayout(self.navigationViewWrapper)
        layout.addWidget(self.histogramWidget)
        layout.addLayout(self.imageEnhanceWidget)
        layout.addStretch()
        
        # transfer the layout to the central widget
        self.centralWidget:QWidget = QWidget()
        self.centralWidget.setLayout(layout)
        self.centralWidget.setFixedWidth(self.centralWidget.minimumSizeHint().width())
        
        if MACHINE_DISPLAY_CONFIG.SINGLE_WINDOW:
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
            height_min = int(0.9*desktopWidget.height())
            width_min = int(0.96*desktopWidget.width())
            self.setMinimumSize(width_min,height_min)
        else:
            self.setCentralWidget(self.centralWidget)
            self.tabbedImageDisplayWindow = QMainWindow()
            self.tabbedImageDisplayWindow.setCentralWidget(self.imageDisplayTabs)
            self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint) # type: ignore
            self.tabbedImageDisplayWindow.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint) # type: ignore
            desktopWidget = QDesktopWidget()
            width = int(0.96*desktopWidget.height())
            height = width
            self.tabbedImageDisplayWindow.setFixedSize(width,height)
            self.tabbedImageDisplayWindow.show()

        # make connections
        self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)
        self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
        self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
        self.imageDisplay.image_to_display.connect(self.processLiveImage) # internally calls self.imageDisplayWindow.display_image, among other things
        self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x)))
        self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x)))
        self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x)))
        self.navigationController.signal_joystick_button_pressed.connect(self.autofocusController.autofocus)
        self.autofocusController.image_to_display.connect(self.imageDisplayWindow.display_image)
        self.multipointController.image_to_display.connect(self.imageDisplayWindow.display_image)
        self.multipointController.signal_current_configuration.connect(self.liveControlWidget.set_microscope_mode)
        self.multipointController.image_to_display_multi.connect(self.imageArrayDisplayWindow.display_image)

        self.liveControlWidget.signal_newExposureTime.connect(self.camera.set_exposure_time)
        self.liveControlWidget.signal_newAnalogGain.connect(self.camera.set_analog_gain)
        self.liveControlWidget.update_camera_settings()

        self.slidePositionController.signal_slide_loading_position_reached.connect(self.navigationWidget.slot_slide_loading_position_reached)
        self.slidePositionController.signal_slide_loading_position_reached.connect(self.multiPointWidget.disable_the_start_aquisition_button)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.navigationWidget.slot_slide_scanning_position_reached)
        self.slidePositionController.signal_slide_scanning_position_reached.connect(self.multiPointWidget.enable_the_start_aquisition_button)
        self.slidePositionController.signal_clear_slide.connect(self.navigationViewer.clear_slide)

        self.navigationController.xyPos.connect(self.navigationViewer.update_current_location)
        self.multipointController.signal_register_current_fov.connect(self.navigationViewer.register_fov)

        self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)

        # if well selection changes, or dx/y or Nx/y change, redraw preview
        self.wellSelectionWidget.itemSelectionChanged.connect(self.on_well_selection_change)

        self.multiPointWidget.entry_deltaX.valueChanged.connect(self.on_well_selection_change)
        self.multiPointWidget.entry_deltaY.valueChanged.connect(self.on_well_selection_change)

        self.multiPointWidget.entry_NX.valueChanged.connect(self.on_well_selection_change)
        self.multiPointWidget.entry_NY.valueChanged.connect(self.on_well_selection_change)

    def add_image_format_options(self):
        image_formats=['MONO8','MONO12']

        self.camera_pixel_format_widget=QComboBox()
        self.camera_pixel_format_widget.addItems(image_formats)
        self.camera_pixel_format_widget.setCurrentIndex(0) # 8 bit is default (there is a bug where 8 bit is hardware default, but setting it to 8 bit while in this default state produces weird images. so set 8bit as display default, and only actually call the function to change the format when the format is actually changed, i.e. connect to format change signal only after this default is displayed)
        self.camera_pixel_format_widget.currentIndexChanged.connect(lambda index:self.camera.set_pixel_format(image_formats[index]))
        
        self.image_compress_widget=QCheckBox()
        self.image_compress_widget.stateChanged.connect(self.set_image_compression)
        self.image_compress_widget.setToolTip("enable image file compression (not supported for bmp)")

        self.image_compress_widget_container=QHBoxLayout()
        self.image_compress_widget_container.addWidget(QLabel("compression"))
        self.image_compress_widget_container.addWidget(self.image_compress_widget)

        self.image_format_widget=QComboBox()
        self.image_format_widget.addItems(["BMP","TIF"])
        self.image_format_widget.currentIndexChanged.connect(self.set_image_format)
        self.image_format_widget.setCurrentIndex(list(ImageFormat).index(Acquisition.IMAGE_FORMAT))

        self.image_pixel_format_widgets=QHBoxLayout()
        self.image_pixel_format_widgets.addWidget(self.camera_pixel_format_widget)
        self.image_pixel_format_widgets.addWidget(self.image_format_widget)
        self.image_pixel_format_widgets.addLayout(self.image_compress_widget_container)

    @TypecheckFunction
    def set_image_format(self,index:int):
        Acquisition.IMAGE_FORMAT=list(ImageFormat)[index]
        if Acquisition.IMAGE_FORMAT==ImageFormat.TIFF:
            self.image_compress_widget.setDisabled(False)
        else:
            self.image_compress_widget.setDisabled(True)
            self.image_compress_widget.setCheckState(False)

    @TypecheckFunction
    def set_image_compression(self,state:Union[int,bool]):
        if type(state)==int:
            state=bool(state)

        if state:
            if Acquisition.IMAGE_FORMAT==ImageFormat.TIFF:
                Acquisition.IMAGE_FORMAT=ImageFormat.TIFF_COMPRESSED
            else:
                raise Exception("enabled compression even though current image file format does not support compression. this is a bug.")
        else:
            if Acquisition.IMAGE_FORMAT==ImageFormat.TIFF_COMPRESSED:
                Acquisition.IMAGE_FORMAT=ImageFormat.TIFF
            else:
                raise Exception("disabled compression while a format that is not compressed tiff was selected. this is a bug.")

    def add_image_inspection(self,
        brightness_adjust_min:int=5,
        brightness_adjust_max:int=15,

        contrast_adjust_min:int=5,
        contrast_adjust_max:int=15,

        histogram_log_display_default:bool=True
    ):
        self.histogramWidget=pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")
        self.histogramWidget.view=self.histogramWidget.addViewBox()

        # add panel to change image settings
        self.imageBrightnessSliderContainer=QVBoxLayout()
        self.imageBrightnessSliderContainer.addWidget(QLabel("Brightness"))
        self.imageBrightnessSlider=QSlider(Qt.Horizontal)
        self.imageBrightnessSlider.setTickPosition(QSlider.TicksBelow)
        self.imageBrightnessSlider.setRange(brightness_adjust_min,brightness_adjust_max)
        self.imageBrightnessSlider.setSingleStep(1)
        self.imageBrightnessSlider.setTickInterval(5)
        self.imageBrightnessSlider.setValue(10)
        self.imageBrightnessSlider.valueChanged.connect(self.set_brightness)
        self.imageBrightnessSlider.value=1.0
        self.imageBrightnessSliderContainer.addWidget(self.imageBrightnessSlider)
        self.imageBrightnessLabel=QHBoxLayout()
        self.imageBrightnessLabel.addWidget(QLabel(f"{brightness_adjust_min/10}"),0,Qt.AlignLeft)
        self.imageBrightnessLabel.addWidget(QLabel(f"{self.imageBrightnessSlider.value}"),0,Qt.AlignCenter)
        self.imageBrightnessLabel.addWidget(QLabel(f"{brightness_adjust_max/10}"),0,Qt.AlignRight)
        self.imageBrightnessSliderContainer.addLayout(self.imageBrightnessLabel)

        self.imageContrastSliderContainer=QVBoxLayout()
        self.imageContrastSliderContainer.addWidget(QLabel("Contrast"))
        self.imageContrastSlider=QSlider(Qt.Horizontal)
        self.imageContrastSlider.setTickPosition(QSlider.TicksBelow)
        self.imageContrastSlider.setRange(contrast_adjust_min,contrast_adjust_max)
        self.imageContrastSlider.setSingleStep(1)
        self.imageContrastSlider.setTickInterval(5)
        self.imageContrastSlider.setValue(10)
        self.imageContrastSlider.valueChanged.connect(self.set_contrast)
        self.imageContrastSlider.value=1.0
        self.imageContrastSliderContainer.addWidget(self.imageContrastSlider)
        self.imageContrastLabel=QHBoxLayout()
        self.imageContrastLabel.addWidget(QLabel(f"{contrast_adjust_min/10}"),0,Qt.AlignLeft)
        self.imageContrastLabel.addWidget(QLabel(f"{self.imageContrastSlider.value}"),0,Qt.AlignCenter)
        self.imageContrastLabel.addWidget(QLabel(f"{contrast_adjust_max/10}"),0,Qt.AlignRight)
        self.imageContrastSliderContainer.addLayout(self.imageContrastLabel)

        self.histogramLogScaleContainer=QVBoxLayout()
        self.histogramLogScaleLabel=QLabel("log")
        self.histogramLogScaleContainer.addWidget(self.histogramLogScaleLabel)
        self.histogramLogScaleCheckbox=QCheckBox()
        self.histogram_log_scale=histogram_log_display_default
        self.histogramLogScaleCheckbox.setCheckState(self.histogram_log_scale*2) # convert from bool to weird tri-stateable value (i.e. 0,1,2 where 0 is unchecked, 2 is checked, and 1 is in between. if this is set to 1, the button will become to tri-stable)
        self.histogramLogScaleCheckbox.stateChanged.connect(self.setHistogramLogScale)
        self.histogramLogScaleCheckbox.setToolTip("calculate histogram with log scale?")
        self.histogramLogScaleContainer.addWidget(self.histogramLogScaleCheckbox)

        self.imageEnhanceWidget=QHBoxLayout()
        self.imageEnhanceWidget.addLayout(self.imageBrightnessSliderContainer)
        self.imageEnhanceWidget.addLayout(self.imageContrastSliderContainer)
        self.imageEnhanceWidget.addLayout(self.histogramLogScaleContainer)
        self.last_raw_image=None
        self.last_image_data=None

    @TypecheckFunction
    def setHistogramLogScale(self,state:Union[bool,int]):
        if type(state)==int:
            state=bool(state)

        self.histogram_log_scale=state
        self.processLiveImage(calculate_histogram=True)

    @TypecheckFunction
    def set_brightness(self,value:int):
        """ value<1 darkens image, value>1 brightens image """

        # convert qslider value to actual factor
        factor=value/10
        self.imageBrightnessSlider.value=factor

        self.processLiveImage()

    @TypecheckFunction
    def set_contrast(self,value:int):
        """ value<1 decreases image contrast, value>1 increases image contrast """

        # convert qslider value to actal factor
        factor=value/10
        self.imageContrastSlider.value=factor

        self.processLiveImage()

    # callback for newly acquired images in live view (that saves last live image and recalculates histogram or image view on request based on last live image)
    @TypecheckFunction
    def processLiveImage(self,image_data:Optional[numpy.ndarray]=None,calculate_histogram:Optional[bool]=None):
        """ set histogram according to new image. clear internal buffer on request (used by the brightness/contrast adjust functions. acquiring new image clears buffer, setting histogram for adjusted images should not clear buffer) """

        # if there is a new image, save it, and force histogram calculation
        if not image_data is None:
            self.last_image_data=image_data
            calculate_histogram=True

        # calculate histogram
        if calculate_histogram is None:
            calculate_histogram=self.histogram_log_scale

        if calculate_histogram and not self.last_image_data is None:
            image_data=self.last_image_data
            if image_data.dtype==numpy.uint8:
                max_value=2**8-1
            # 12 bit pixel data type is stretched to fit 16 bit range neatly (with the 4 least significant bits always zero)
            elif image_data.dtype==numpy.uint16:
                max_value=2**16-1
            else:
                raise Exception(f"{image_data.dtype=} unimplemented")

            bins=numpy.linspace(0,max_value,129,dtype=image_data.dtype)
            hist,bins=numpy.histogram(image_data,bins=bins)
            hist=hist.astype(numpy.float32)
            if self.histogram_log_scale:
                hist_nonzero_mask=hist!=0
                hist[hist_nonzero_mask]=numpy.log(hist[hist_nonzero_mask])
            hist=hist/hist.max() # normalize to [0;1]

            self.histogramWidget.view.setLimits(
                xMin=0,
                xMax=max_value,
                yMin=0.0,
                yMax=1.0,
                minXRange=bins[4],
                maxXRange=bins[-1],
                minYRange=1.0,
                maxYRange=1.0,
            )

            try:
                self.histogramWidget.plot_data.clear()
                self.histogramWidget.plot_data.plot(x=bins[:-1],y=hist)
            except:
                self.histogramWidget.plot_data=self.histogramWidget.addPlot(0,0,title="Histogram",x=bins[:-1],y=hist,viewBox=self.histogramWidget.view)
                self.histogramWidget.plot_data.hideAxis("left")

        # if there is data to display, apply contrast/brightness settings, then actually display the data
        # also do not actually apply enhancement if brightness and contrast are set to 1.0 (which does not nothing)
        if not self.last_image_data is None:
            image=self.last_image_data

            # since integer conversion truncates or whatever instead of scaling, scale manually
            if image.dtype==numpy.uint16:
                image=numpy.uint8(image>>(16-8))

            if not (self.imageBrightnessSlider.value==1.0 and self.imageContrastSlider.value==1.0):
                # convert to uint8 for pillow image enhancement (not sure why uint8 is required..?)

                image=Image.fromarray(image)
                if self.imageBrightnessSlider.value!=1.0:
                    brightness_enhancer = ImageEnhance.Brightness(image)
                    image=brightness_enhancer.enhance(self.imageBrightnessSlider.value)

                if self.imageContrastSlider.value!=1.0:
                    contrast_enhancer = ImageEnhance.Contrast(image)
                    image=contrast_enhancer.enhance(self.imageContrastSlider.value)

                image=numpy.asarray(image) # numpy.array could also be used, but asarray does not copy the image data (read only view)

            # display newly enhanced image
            self.imageDisplayWindow.display_image(image)

        # if there is neither a new nor an old image, only brightness/contrast settings have been changed but there is nothing to display

    def on_well_selection_change(self):
        # clear display
        self.navigationViewer.clear_slide()

        # make sure the current selection is contained in selection buffer, then draw each pov
        self.wellSelectionWidget.itemselectionchanged()
        preview_fov_list=[]
        for well_row,well_column in self.wellSelectionWidget.currently_selected_well_indices:
            x_well,y_well=WELLPLATE_FORMATS[MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT].convert_well_index(well_row,well_column)
            for x_grid_item,y_grid_item in self.multipointController.grid_positions_for_well(x_well,y_well):
                LIGHT_GREY=(160,)*3
                if self.hcs_controller.fov_exceeds_well_boundary(well_row,well_column,x_grid_item,y_grid_item):
                    grid_item_color=(255,50,140)
                else:
                    grid_item_color=LIGHT_GREY

                self.navigationViewer.draw_fov(x_grid_item,y_grid_item,color=grid_item_color)
                preview_fov_list.append((x_grid_item,y_grid_item))

        self.navigationViewer.preview_fovs=preview_fov_list
        
        # write view to display buffer
        if not self.navigationViewer.last_fov_drawn is None:
            self.navigationViewer.draw_fov(*self.navigationViewer.last_fov_drawn,self.navigationViewer.box_color)

    @TypecheckFunction
    def closeEvent(self, event:QEvent):
        
        event.accept()
        self.imageSaver.close()
        self.imageDisplay.close()
        if not MACHINE_DISPLAY_CONFIG.SINGLE_WINDOW:
            self.imageDisplayWindow.close()
            self.imageArrayDisplayWindow.close()
            self.tabbedImageDisplayWindow.close()

        self.hcs_controller.close()
