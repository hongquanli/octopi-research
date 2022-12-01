# qt libraries
from qtpy.QtCore import Qt, QEvent, Signal
from qtpy.QtWidgets import QMainWindow, QTabWidget, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDesktopWidget, QSlider, QCheckBox, QWidget

import numpy

# app specific libraries
import control.widgets as widgets
from control.camera import Camera
import control.core as core
import control.microcontroller as microcontroller
from control.hcs import HCSController
from control._def import *
import control.core_displacement_measurement as core_displacement_measurement

import pyqtgraph as pg
import pyqtgraph.dockarea as dock

from PIL import ImageEnhance, Image
import time

from control.typechecker import TypecheckFunction
from typing import Union


def seconds_to_long_time(sec:float)->str:
    hours=int(sec//3600)
    sec-=hours*3600
    minutes=int(sec//60)
    sec-=minutes*60
    return f"{hours:3}h {minutes:2}m {sec:4.1f}s"

class OctopiGUI(QMainWindow):

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
    def autofocusController(self)->core.AutoFocusController:
        return self.hcs_controller.autofocusController
    @property
    def multipointController(self)->core.MultiPointController:
        return self.hcs_controller.multipointController
    @property
    def imageSaver(self)->core.ImageSaver:
        return self.hcs_controller.imageSaver
    @property
    def camera(self)->Camera:
        return self.hcs_controller.camera
    @property
    def focus_camera(self)->Camera:
        return self.hcs_controller.focus_camera
    @property
    def microcontroller(self)->microcontroller.Microcontroller:
        return self.hcs_controller.microcontroller
    @property
    def configurationManager_focus_camera(self)->core.ConfigurationManager:
        return self.hcs_controller.configurationManager_focus_camera
    @property
    def streamHandler_focus_camera(self)->core.StreamHandler:
        return self.hcs_controller.streamHandler_focus_camera
    @property
    def liveController_focus_camera(self)->core.LiveController:
        return self.hcs_controller.liveController_focus_camera
    @property
    def displacementMeasurementController(self)->core_displacement_measurement.DisplacementMeasurementController:
        return self.hcs_controller.displacementMeasurementController
    @property
    def laserAutofocusController(self)->core.LaserAutofocusController:
        return self.hcs_controller.laserAutofocusController

    # @TypecheckFunction # dont check because signal cannot yet be checked properly
    def start_experiment(self,experiment_data_target_folder:str,imaging_channel_list:List[str])->Optional[Signal]:
        self.navigationViewer.register_preview_fovs()

        well_list=self.wellSelectionWidget.currently_selected_well_indices

        af_channel=self.multipointController.autofocus_channel_name if self.multipointController.do_autofocus else None

        return self.hcs_controller.acquire(
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
        ).finished

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

            elapsed_time_str=seconds_to_long_time(time_elapsed_since_start)
            if self.acquisition_progress==self.total_num_acquisitions:
                self.multiPointWidget.progress_bar.setFormat(f"done. (acquired {self.total_num_acquisitions:4} images in {elapsed_time_str})")
            else:
                approx_time_left_str=seconds_to_long_time(approx_time_left)
                done_percent=int(self.acquisition_progress*100/self.total_num_acquisitions)
                progress_bar_text=f"completed {self.acquisition_progress:4}/{self.total_num_acquisitions:4} images ({done_percent:2}%) in {elapsed_time_str} (eta: {approx_time_left_str})"
                self.multiPointWidget.progress_bar.setFormat(progress_bar_text)

    def abort_experiment(self):
        self.multipointController.request_abort_aquisition()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hcs_controller=HCSController()

        self.streamHandler.packet_image_to_write.connect(self.imageSaver.enqueue)
        self.streamHandler.signal_new_frame_received.connect(self.liveController.on_new_frame)

        # load window
        self.imageDisplayWindow = widgets.ImageDisplayWindow(draw_crosshairs=True)
        self.imageArrayDisplayWindow = widgets.ImageArrayDisplayWindow(self.configurationManager,window_title="HCS microscope control")

        # image display windows
        self.imageDisplayTabs = QTabWidget()
        self.imageDisplayTabs.addTab(self.imageDisplayWindow.widget, "Live View")
        self.imageDisplayTabs.addTab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition")

        default_well_plate=WELLPLATE_NAMES[MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT]

        # load widgets
        self.imageDisplay           = widgets.ImageDisplay()
        self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
        self.wellSelectionWidget    = widgets.WellSelectionWidget(MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT)
        self.liveControlWidget      = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager)
        self.navigationWidget       = widgets.NavigationWidget(self.navigationController,widget_configuration=default_well_plate)
        self.dacControlWidget       = widgets.DACControWidget(self.microcontroller) # currently unused
        self.autofocusWidget        = widgets.AutoFocusWidget(self.autofocusController)
        self.recordingControlWidget = widgets.RecordingWidget(self.streamHandler,self.imageSaver) # currently unused
        self.multiPointWidget       = widgets.MultiPointWidget(self.multipointController,self.configurationManager,self.start_experiment,self.abort_experiment)
        self.navigationViewer       = widgets.NavigationViewer(sample=default_well_plate)

        self.add_image_format_options()
        self.add_image_inspection()

        liveWidget_layout=QVBoxLayout()
        liveWidget_layout.addWidget(self.navigationWidget)
        liveWidget_layout.addWidget(widgets.as_dock(self.autofocusWidget,"Software AF",True))
        # laser AF widgets
        ADD_LASER_AF_WIDGETS=True
        if ADD_LASER_AF_WIDGETS:
            self.laserAutofocusControlWidget=widgets.as_dock(
                widgets.LaserAutofocusControlWidget(self.laserAutofocusController),
                title="Laser AF",minimize_height=True
            )
            liveWidget_layout.addWidget(self.laserAutofocusControlWidget)
        liveWidget_layout.addWidget(widgets.as_dock(self.histogramWidget,"Histogram"))
        liveWidget_layout.addLayout(self.backgroundSliderContainer)
        liveWidget_layout.addLayout(self.imageEnhanceWidget)
        self.liveWidget=widgets.as_widget(liveWidget_layout)

        self.recordTabWidget = QTabWidget()
        self.recordTabWidget.addTab(self.multiPointWidget, "Multipoint Acquisition")
        self.recordTabWidget.addTab(self.liveWidget, "Live Investigation")

        clear_history_button=QPushButton("clear history")
        clear_history_button.clicked.connect(self.navigationViewer.clear_imaged_positions)

        wellplate_selector=QComboBox()
        wellplate_types_str=list(WELLPLATE_NAMES.values())
        wellplate_selector.addItems(wellplate_types_str)
        # disable 6 and 24 well wellplates, because images of these plates are missing
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

        self.multiPointWidget.grid.addWidget(self.wellSelectionWidget,5,0)
        self.multiPointWidget.grid.addLayout(self.navigationViewWrapper,6,0)

        # layout widgets
        layout = QVBoxLayout()
        layout.addLayout(self.image_pixel_format_widgets)
        layout.addWidget(self.liveControlWidget)
        if MACHINE_DISPLAY_CONFIG.SHOW_DAC_CONTROL:
            layout.addWidget(self.dacControlWidget)
        layout.addWidget(self.recordTabWidget)
        layout.addStretch()
        
        # transfer the layout to the central widget
        self.centralWidget:QWidget = widgets.as_widget(layout)
        
        desktopWidget = QDesktopWidget()
        width_min = int(0.96*desktopWidget.width())
        height_min = int(0.9*desktopWidget.height())
        
        dock_display = dock.Dock('Image Display', autoOrientation = False)
        dock_display.showTitleBar()
        dock_display.addWidget(self.imageDisplayTabs)
        dock_display.setStretch(x=100,y=100)

        dock_controlPanel = dock.Dock('Controls', autoOrientation = False)
        # dock_controlPanel.showTitleBar()
        dock_controlPanel.addWidget(self.centralWidget)
        dock_controlPanel.setStretch(x=1,y=None)
        dock_controlPanel.setFixedWidth(width_min*0.25)

        main_dockArea = dock.DockArea()
        main_dockArea.addDock(dock_display)
        main_dockArea.addDock(dock_controlPanel,'right')

        self.setCentralWidget(main_dockArea)
        self.setMinimumSize(width_min,height_min)

        ADD_LASER_AF_IMAGE_VIEW=True
        if ADD_LASER_AF_IMAGE_VIEW:
            self.liveControlWidget_focus_camera = widgets.LiveControlWidget(self.streamHandler_focus_camera,self.liveController_focus_camera,self.configurationManager_focus_camera)
            self.imageDisplayWindow_focus = widgets.ImageDisplayWindow(draw_crosshairs=True)

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

            laserfocus_dockArea = dock.DockArea()
            laserfocus_dockArea.addDock(dock_laserfocus_image_display)
            laserfocus_dockArea.addDock(dock_laserfocus_liveController,'right',relativeTo=dock_laserfocus_image_display)

            # connections
            self.liveControlWidget_focus_camera.update_camera_settings()

            self.streamHandler_focus_camera.signal_new_frame_received.connect(self.liveController_focus_camera.on_new_frame)
            self.streamHandler_focus_camera.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

            self.streamHandler_focus_camera.image_to_display.connect(self.displacementMeasurementController.update_measurement)
            self.laserAutofocusController.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

            # self.imageDisplayWindow_focus.widget
            self.imageDisplayTabs.addTab(laserfocus_dockArea,"Laser-based Focus")

        # make connections
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
        self.camera_pixel_format_widget.setToolTip("camera pixel format\n\nMONO8 means monochrome (grey-scale) 8bit\nMONO12 means monochrome 12bit\n\nmore bits can capture more detail (8bit can capture 2^8 intensity values, 12bit can capture 2^12), but also increase file size")
        self.camera_pixel_format_widget.addItems(image_formats)
        self.camera_pixel_format_widget.currentIndexChanged.connect(lambda index:self.camera.set_pixel_format(image_formats[index]))
        self.camera_pixel_format_widget.setCurrentIndex(0) # 8 bit is default (there is a bug where 8 bit is hardware default, but setting it to 8 bit while in this default state produces weird images. so set 8bit as display default, and only actually call the function to change the format when the format is actually changed, i.e. connect to format change signal only after this default is displayed)
        
        compression_tooltip="enable image file compression (not supported for bmp)"
        self.image_compress_widget=QCheckBox()
        self.image_compress_widget.stateChanged.connect(self.set_image_compression)
        self.image_compress_widget.setToolTip(compression_tooltip)

        self.image_compress_widget_container=QHBoxLayout()
        compression_label=QLabel("compression")
        compression_label.setToolTip(compression_tooltip)
        self.image_compress_widget_container.addWidget(compression_label)
        self.image_compress_widget_container.addWidget(self.image_compress_widget)

        self.image_format_widget=QComboBox()
        self.image_format_widget.setToolTip("change file format for images acquired with the multi point acquisition function")
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

        self.backgroundSlider=QSlider(Qt.Horizontal)
        self.backgroundSlider.setTickPosition(QSlider.TicksBelow)
        self.backgroundSlider.setRange(1,255)
        self.backgroundSlider.setSingleStep(1)
        self.backgroundSlider.setTickInterval(16)
        self.backgroundSlider.valueChanged.connect(self.set_background)
        self.backgroundSlider.setValue(10)

        self.backgroundSNRValueText=QLabel("SNR: undefined")

        self.backgroundHeader=QHBoxLayout()
        self.backgroundHeader.addWidget(QLabel("Background"))
        self.backgroundHeader.addWidget(self.backgroundSNRValueText)

        self.backgroundSliderContainer=QVBoxLayout()
        self.backgroundSliderContainer.addLayout(self.backgroundHeader)
        self.backgroundSliderContainer.addWidget(self.backgroundSlider)
        

    def set_background(self,new_background_value:int):
        self.backgroundSlider.value=new_background_value
        self.processLiveImage()
        #print(f"set background to {new_background_value}")

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
                image=numpy.uint8(image>>8)

            foreground_mask=image>self.backgroundSlider.value
            snr_text="SNR: undefined"
            if foreground_mask.any():
                if image_mean!=0:
                    foreground_mean=image[foreground_mask].mean()
                    background_mean=image[~foreground_mask].mean()

                    snr_value=foreground_mean/background_mean
                    
                    snr_text=f"SNR: {snr_value:.1f}"
            self.backgroundSNRValueText.setText(snr_text)

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
        
        self.imageSaver.close()
        self.imageDisplay.close()

        self.hcs_controller.close()
        
        event.accept()
