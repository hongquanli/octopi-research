# set QT_API environment variable
import os

os.environ["QT_API"] = "pyqt5"

# qt libraries
from qtpy.QtCore import Qt, QEvent
from qtpy.QtWidgets import QMainWindow, QTabWidget, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDesktopWidget

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

from control.typechecker import TypecheckFunction

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
        )

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
        self.cameraSettingWidget    = widgets.CameraSettingsWidget(self.camera,include_gain_exposure_time=False)
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

        self.histogramWidget=pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")
        self.histogramWidget.view=self.histogramWidget.addViewBox()

        # layout widgets
        layout = QVBoxLayout()
        #layout.addWidget(self.cameraSettingWidget)
        layout.addWidget(self.liveControlWidget)
        layout.addWidget(self.navigationWidget)
        if MACHINE_DISPLAY_CONFIG.SHOW_DAC_CONTROL:
            layout.addWidget(self.dacControlWidget)
        layout.addWidget(self.autofocusWidget)
        layout.addWidget(self.recordTabWidget)
        layout.addLayout(self.navigationViewWrapper)
        layout.addWidget(self.histogramWidget)
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
        self.imageDisplay.image_to_display.connect(self.imageDisplayWindow.display_image) # may connect streamHandler directly to imageDisplayWindow
        self.imageDisplay.image_to_display.connect(self.setHistogram)
        self.navigationController.xPos.connect(lambda x:self.navigationWidget.label_Xpos.setText("{:.2f}".format(x)))
        self.navigationController.yPos.connect(lambda x:self.navigationWidget.label_Ypos.setText("{:.2f}".format(x)))
        self.navigationController.zPos.connect(lambda x:self.navigationWidget.label_Zpos.setText("{:.2f}".format(x)))
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

        self.wellSelectionWidget.signal_wellSelectedPos.connect(self.navigationController.move_to)

        # if well selection changes, or dx/y or Nx/y change, redraw preview
        self.wellSelectionWidget.itemSelectionChanged.connect(self.on_well_selection_change)

        self.multiPointWidget.entry_deltaX.valueChanged.connect(self.on_well_selection_change)
        self.multiPointWidget.entry_deltaY.valueChanged.connect(self.on_well_selection_change)

        self.multiPointWidget.entry_NX.valueChanged.connect(self.on_well_selection_change)
        self.multiPointWidget.entry_NY.valueChanged.connect(self.on_well_selection_change)


    def setHistogram(self,image_data):
        if image_data.dtype==numpy.uint8:
            max_value=255
        elif image_data.dtype==numpy.uint16:
            max_value=2**16
        else:
            raise Exception(f"{image_data.dtype=} unimplemented")

        hist,bins=numpy.histogram(image_data,bins=numpy.linspace(0,max_value,101,dtype=image_data.dtype))
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
