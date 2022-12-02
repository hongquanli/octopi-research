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
from control.gui import *

import pyqtgraph as pg
import pyqtgraph.dockarea as dock

from PIL import ImageEnhance, Image
import time

from control.typechecker import TypecheckFunction
from typing import Union

LIVE_BUTTON_IDLE_TEXT="Start Live"
LIVE_BUTTON_RUNNING_TEXT="Stop Live"

LIVE_BUTTON_TOOLTIP="""start/stop live image view

displays each image that is recorded by the camera

useful for manual investigation of a plate and/or imaging settings. Note that this can lead to strong photobleaching. Consider using the snapshot button instead (labelled 'snap')"""
BTN_SNAP_TOOLTIP="take single image (minimizes bleaching for manual testing)"

exposure_time_tooltip="exposure time is the time the camera sensor records an image. Higher exposure time means more time to record light emitted from a sample, which also increases bleaching (the light source is activate as long as the camera sensor records the light)"
analog_gain_tooltip="analog gain increases the camera sensor sensitiviy. Higher gain will make the image look brighter so that a lower exposure time can be used, but also introduces more noise."
channel_offset_tooltip="channel specific z offset used in multipoint acquisition to focus properly in channels that are not in focus at the same time the nucleus is (given the nucleus is the channel that is used for focusing)"

CAMERA_PIXEL_FORMAT_TOOLTIP="camera pixel format\n\nMONO8 means monochrome (grey-scale) 8bit\nMONO12 means monochrome 12bit\n\nmore bits can capture more detail (8bit can capture 2^8 intensity values, 12bit can capture 2^12), but also increase file size"


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

        default_well_plate=WELLPLATE_NAMES[MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT]

        # load widgets
        self.imageDisplay           = widgets.ImageDisplay()
        self.streamHandler.image_to_display.connect(self.imageDisplay.enqueue)
        self.wellSelectionWidget    = widgets.WellSelectionWidget(MUTABLE_MACHINE_CONFIG.WELLPLATE_FORMAT)
        self.liveControlWidget      = widgets.LiveControlWidget(self.streamHandler,self.liveController,self.configurationManager)
        self.navigationWidget       = widgets.NavigationWidget(self.navigationController,widget_configuration=default_well_plate)
        self.autofocusWidget        = widgets.AutoFocusWidget(self.autofocusController)
        self.multiPointWidget       = widgets.MultiPointWidget(self.multipointController,self.configurationManager,self.start_experiment,self.abort_experiment)
        self.navigationViewer       = widgets.NavigationViewer(sample=default_well_plate)

        self.imagingModes=VBox(*[
            Grid([
                Label(config.name).widget
            ],[Grid([
                Label("exposure time").widget,
                SpinBoxDouble(
                    minimum=self.liveController.camera.EXPOSURE_TIME_MS_MIN,
                    maximum=self.liveController.camera.EXPOSURE_TIME_MS_MAX,step=1.0,
                    default=config.exposure_time,tooltip=exposure_time_tooltip,
                    on_valueChanged=[
                        config.set_exposure_time,
                        self.configurationManager.save_configurations
                    ]
                ).widget,
                Label("gain").widget,
                SpinBoxDouble(
                    minimum=0.0,maximum=24.0,step=0.1,
                    default=config.analog_gain,tooltip=analog_gain_tooltip,
                    on_valueChanged=[
                        config.set_analog_gain,
                        self.configurationManager.save_configurations
                    ]
                ).widget,
                Label("offset").widget,
                SpinBoxDouble(
                    minimum=-30.0,maximum=30.0,step=0.1,
                    default=config.channel_z_offset,tooltip=channel_offset_tooltip,
                    on_valueChanged=[
                        config.set_offset,
                        self.configurationManager.save_configurations
                    ]
                ).widget,
                # disabled because unused
                #Label("illumination").widget,
                #SpinBoxDouble(
                #    minimum=0.1,maximum=100.0,step=0.1,
                #    default=config.illumination_intensity,
                #    on_valueChanged=[
                #        config.set_illumination_intensity,
                #        self.configurationManager.save_configurations
                #    ]
                #).widget
            ])])
            for config in self.configurationManager.configurations
        ]).widget

        self.laserAutofocusControlWidget=Dock(
            widgets.LaserAutofocusControlWidget(self.laserAutofocusController),
            title="Laser AF",minimize_height=True
        ).widget

        self.add_image_inspection()

        self.liveWidget=VBox(
            self.navigationWidget,
            Dock(self.autofocusWidget,"Software AF",True).widget,
            self.laserAutofocusControlWidget,
            Dock(self.histogramWidget,"Histogram").widget,
            self.backgroundSliderContainer,
            self.imageEnhanceWidget
        ).widget

        self.recordTabWidget = TabBar(
            Tab(self.multiPointWidget, "Multipoint Acquisition"),
            Tab(self.imagingModes,"Channel config"),
            Tab(self.liveWidget, "Setup"),
        ).widget

        clear_history_button=Button("clear history",on_clicked=self.navigationViewer.clear_imaged_positions).widget

        wellplate_selector=QComboBox()
        wellplate_types_str=list(WELLPLATE_NAMES.values())
        wellplate_selector.addItems(wellplate_types_str)
        # disable 6 and 24 well wellplates, because images of these plates are missing
        for wpt in [0,2]:
            item=wellplate_selector.model().item(wpt)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled) # type: ignore
        wellplate_selector.setCurrentIndex(wellplate_types_str.index(default_well_plate))
        wellplate_selector.currentIndexChanged.connect(lambda wellplate_type_index:setattr(MUTABLE_MACHINE_CONFIG,"WELLPLATE_FORMAT",tuple(WELLPLATE_FORMATS.keys())[wellplate_type_index]))
 
        wellplate_overview_header=HBox( QLabel("wellplate overview"), clear_history_button, QLabel("change plate type:"), wellplate_selector ).layout

        self.navigationViewWrapper=VBox(
            wellplate_overview_header,
            self.navigationViewer
        ).layout

        self.multiPointWidget.grid.layout.addWidget(self.wellSelectionWidget,5,0)
        self.multiPointWidget.grid.layout.addLayout(self.navigationViewWrapper,6,0)

        # layout widgets
        layout = VBox(
            self.liveControlWidget,
            self.recordTabWidget
        ).layout
        layout.addStretch()
        
        # transfer the layout to the central widget
        self.centralWidget:QWidget = as_widget(layout)
        
        desktopWidget = QDesktopWidget()
        width_min = int(0.96*desktopWidget.width())
        height_min = int(0.9*desktopWidget.height())

        # laser af section
        self.liveControlWidget_focus_camera = widgets.LiveControlWidget(self.streamHandler_focus_camera,self.liveController_focus_camera,self.configurationManager_focus_camera)
        self.imageDisplayWindow_focus = widgets.ImageDisplayWindow(draw_crosshairs=True)

        dock_laserfocus_image_display = Dock(
            widget=self.imageDisplayWindow_focus.widget,
            title='Focus Camera Image Display'
        ).widget
        dock_laserfocus_liveController = Dock(
            title='Focus Camera Controller',
            widget=self.liveControlWidget_focus_camera,
            fixed_width=self.liveControlWidget_focus_camera.minimumSizeHint().width()
        ).widget

        laserfocus_dockArea = dock.DockArea()
        laserfocus_dockArea.addDock(dock_laserfocus_image_display)
        laserfocus_dockArea.addDock(dock_laserfocus_liveController,'right',relativeTo=dock_laserfocus_image_display)

        # connections
        self.liveControlWidget_focus_camera.update_camera_settings()

        self.streamHandler_focus_camera.signal_new_frame_received.connect(self.liveController_focus_camera.on_new_frame)
        self.streamHandler_focus_camera.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

        self.streamHandler_focus_camera.image_to_display.connect(self.displacementMeasurementController.update_measurement)
        self.laserAutofocusController.image_to_display.connect(self.imageDisplayWindow_focus.display_image)

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

        # image display windows
        self.imageDisplayTabs = TabBar(
            Tab(self.imageDisplayWindow.widget, "Live View"),
            Tab(self.imageArrayDisplayWindow.widget, "Multichannel Acquisition"),
            Tab(laserfocus_dockArea,"Laser-based Focus"),
        ).widget

        main_dockArea = dock.DockArea()
        main_dockArea.addDock(Dock(
            title='Image Display',
            widget=self.imageDisplayTabs
        ).widget)
        main_dockArea.addDock(Dock(
            title='Controls',
            widget=self.centralWidget, 
            fixed_width=width_min*0.25, stretch_x=1,stretch_y=None
        ).widget,'right')

        self.setCentralWidget(main_dockArea)
        self.setMinimumSize(width_min,height_min)

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
        self.imageBrightnessSlider=QSlider(Qt.Horizontal)
        self.imageBrightnessSlider.setTickPosition(QSlider.TicksBelow)
        self.imageBrightnessSlider.setRange(brightness_adjust_min,brightness_adjust_max)
        self.imageBrightnessSlider.setSingleStep(1)
        self.imageBrightnessSlider.setTickInterval(5)
        self.imageBrightnessSlider.setValue(10)
        self.imageBrightnessSlider.valueChanged.connect(self.set_brightness)
        self.imageBrightnessSlider.value=1.0
        self.imageBrightnessLabel=QHBoxLayout()
        self.imageBrightnessLabel.addWidget(QLabel(f"{brightness_adjust_min/10}"),0,Qt.AlignLeft)
        self.imageBrightnessLabel.addWidget(QLabel(f"{self.imageBrightnessSlider.value}"),0,Qt.AlignCenter)
        self.imageBrightnessLabel.addWidget(QLabel(f"{brightness_adjust_max/10}"),0,Qt.AlignRight)

        self.imageBrightnessSliderContainer=VBox(
            QLabel("Brightness"),
            self.imageBrightnessSlider,
            self.imageBrightnessLabel,
        ).layout

        self.imageContrastSlider=QSlider(Qt.Horizontal)
        self.imageContrastSlider.setTickPosition(QSlider.TicksBelow)
        self.imageContrastSlider.setRange(contrast_adjust_min,contrast_adjust_max)
        self.imageContrastSlider.setSingleStep(1)
        self.imageContrastSlider.setTickInterval(5)
        self.imageContrastSlider.setValue(10)
        self.imageContrastSlider.valueChanged.connect(self.set_contrast)
        self.imageContrastSlider.value=1.0
        self.imageContrastLabel=QHBoxLayout()
        self.imageContrastLabel.addWidget(QLabel(f"{contrast_adjust_min/10}"),0,Qt.AlignLeft)
        self.imageContrastLabel.addWidget(QLabel(f"{self.imageContrastSlider.value}"),0,Qt.AlignCenter)
        self.imageContrastLabel.addWidget(QLabel(f"{contrast_adjust_max/10}"),0,Qt.AlignRight)

        self.imageContrastSliderContainer=VBox(
            QLabel("Contrast"),
            self.imageContrastSlider,
            self.imageContrastLabel,
        ).layout

        self.histogramLogScaleCheckbox=QCheckBox()
        self.histogram_log_scale=histogram_log_display_default
        self.histogramLogScaleCheckbox.setCheckState(self.histogram_log_scale*2) # convert from bool to weird tri-stateable value (i.e. 0,1,2 where 0 is unchecked, 2 is checked, and 1 is in between. if this is set to 1, the button will become to tri-stable)
        self.histogramLogScaleCheckbox.stateChanged.connect(self.setHistogramLogScale)
        self.histogramLogScaleCheckbox.setToolTip("calculate histogram with log scale?")

        self.histogramLogScaleContainer=VBox(
            QLabel("log"),
            self.histogramLogScaleCheckbox
        ).layout

        self.imageEnhanceWidget=HBox(
            self.imageBrightnessSliderContainer,
            self.imageContrastSliderContainer,
            self.histogramLogScaleContainer,
        ).layout
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

        self.backgroundHeader=HBox( QLabel("Background"), self.backgroundSNRValueText ).layout

        self.backgroundSliderContainer=VBox(
            self.backgroundHeader,
            self.backgroundSlider
        ).layout
        

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
                self.histogramWidget.plot_data.plot(x=bins[:-1],y=hist,pen=pg.mkPen(color="red"))
            except:
                self.histogramWidget.plot_data=self.histogramWidget.addPlot(0,0,title="Histogram",x=bins[:-1],y=hist,viewBox=self.histogramWidget.view,pen=pg.mkPen(color="red"))
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
            if foreground_mask.any() and not foreground_mask.all():
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
