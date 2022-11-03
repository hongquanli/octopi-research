# qt libraries
from qtpy.QtCore import QObject, Signal, Qt # type: ignore
from qtpy.QtWidgets import QMainWindow, QWidget, QGridLayout, QDesktopWidget, QVBoxLayout, QLabel

from control._def import *

from queue import Queue
from threading import Thread, Lock
import numpy as np
import pyqtgraph as pg

from typing import Optional, List, Union, Tuple

from control.core import ConfigurationManager

class ImageDisplay(QObject):

    image_to_display = Signal(np.ndarray)

    def __init__(self):
        QObject.__init__(self)
        self.queue = Queue(10) # max 10 items in the queue
        self.image_lock = Lock()
        self.stop_signal_received = False
        self.thread:Thread = Thread(target=self.process_queue)
        self.thread.start()
        
    def process_queue(self):
        while True:
            # stop the thread if stop signal is received
            if self.stop_signal_received:
                return
            # process the queue
            try:
                [image,_frame_ID,_timestamp] = self.queue.get(timeout=0.1)
                self.image_lock.acquire(True)
                self.image_to_display.emit(image)
                self.image_lock.release()
                self.queue.task_done()
            except:
                pass

    # def enqueue(self,image,frame_ID:int,timestamp):
    def enqueue(self,image):
        try:
            self.queue.put_nowait([image,None,None])
            # when using self.queue.put(str_) instead of try + nowait, program can be slowed down despite multithreading because of the block and the GIL
            pass
        except:
            print('imageDisplay queue is full, image discarded')

    def emit_directly(self,image):
        self.image_to_display.emit(image)

    def close(self):
        self.queue.join()
        self.stop_signal_received = True
        self.thread.join()


class ImageDisplayWindow(QMainWindow):

    def __init__(self, window_title='', draw_crosshairs = False, show_LUT=False, autoLevels=False):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint) # type: ignore
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint) # type: ignore
        self.widget = QWidget()
        self.show_LUT = show_LUT
        self.autoLevels = autoLevels

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')

        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.view = self.graphics_widget.addViewBox()
        self.graphics_widget.view.invertY()
        
        ## lock the aspect ratio so pixels are always square
        self.graphics_widget.view.setAspectLocked(True)
        
        ## Create image item
        if self.show_LUT:
            self.graphics_widget.view = pg.ImageView()
            self.graphics_widget.img = self.graphics_widget.view.getImageItem()
            self.graphics_widget.img.setBorder('w')
            self.graphics_widget.view.ui.roiBtn.hide()
            self.graphics_widget.view.ui.menuBtn.hide()
            # self.LUTWidget = self.graphics_widget.view.getHistogramWidget()
            # self.LUTWidget.autoHistogramRange()
            # self.graphics_widget.view.autolevels()
        else:
            self.graphics_widget.img = pg.ImageItem(border='w')
            self.graphics_widget.view.addItem(self.graphics_widget.img)

        ## Create ROI
        self.roi_pos = (500,500)
        self.roi_size = pg.Point(500,500)
        self.ROI = pg.ROI(self.roi_pos, self.roi_size, scaleSnap=True, translateSnap=True)
        self.ROI.setZValue(10)
        self.ROI.addScaleHandle((0,0), (1,1))
        self.ROI.addScaleHandle((1,1), (0,0))
        self.graphics_widget.view.addItem(self.ROI)
        self.ROI.hide()
        self.ROI.sigRegionChanged.connect(self.update_ROI)
        self.roi_pos = self.ROI.pos()
        self.roi_size = self.ROI.size()

        ## Variables for annotating images
        self.draw_rectangle = False
        self.ptRect1 = None
        self.ptRect2 = None
        self.DrawCirc = False
        self.centroid = None
        self.DrawCrossHairs = False
        self.image_offset = np.array([0, 0])

        ## Layout
        layout = QGridLayout()
        if self.show_LUT:
            layout.addWidget(self.graphics_widget.view, 0, 0) 
        else:
            layout.addWidget(self.graphics_widget, 0, 0) 
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)

        # set window size
        desktopWidget = QDesktopWidget()
        width = int(min(desktopWidget.height()*0.9,1000)) #@@@TO MOVE@@@#
        height = width
        self.setFixedSize(width,height)

    def display_image(self,image):
        self.graphics_widget.img.setImage(image,autoLevels=self.autoLevels)

    def update_ROI(self):
        self.roi_pos = self.ROI.pos()
        self.roi_size = self.ROI.size()

    def show_ROI_selector(self):
        self.ROI.show()

    def hide_ROI_selector(self):
        self.ROI.hide()

    def get_roi(self):
        return self.roi_pos,self.roi_size

    def update_bounding_box(self,pts):
        self.draw_rectangle=True
        self.ptRect1=(pts[0][0],pts[0][1])
        self.ptRect2=(pts[1][0],pts[1][1])

    def get_roi_bounding_box(self):
        self.update_ROI()
        width = self.roi_size[0]
        height = self.roi_size[1]
        xmin = max(0, self.roi_pos[0])
        ymin = max(0, self.roi_pos[1])
        return np.array([xmin, ymin, width, height])

    def set_autolevel(self,enabled):
        self.autoLevels = enabled
        print('set autolevel to ' + str(enabled))


class ImageArrayDisplayWindow(QMainWindow):

    def __init__(self, configurationManager:ConfigurationManager, window_title=''):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint) # type: ignore
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint) # type: ignore
        self.widget = QWidget()
        self.configurationManager=configurationManager

        # interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')

        self.set_image_displays({
            11:0,
            12:1,
            13:2,
            14:3,
            15:4,
        },num_rows=2,num_columns=3)

        self.setCentralWidget(self.widget)

        # set window size
        desktopWidget = QDesktopWidget()
        width = int(min(desktopWidget.height()*0.9,1000)) #@@@TO MOVE@@@#
        height = width
        self.setFixedSize(width,height)

    @TypecheckFunction
    def set_image_displays(self,channel_mappings:Dict[int,int],num_rows:int,num_columns:int):
        self.num_image_displays=len(channel_mappings)
        self.channel_mappings=channel_mappings
        self.graphics_widgets=[]
        image_display_layout = QGridLayout()

        assert num_rows*num_columns>=self.num_image_displays

        for i in range(self.num_image_displays):
            next_graphics_widget = pg.GraphicsLayoutWidget()
            next_graphics_widget.view = next_graphics_widget.addViewBox()
            next_graphics_widget.view.setAspectLocked(True)
            next_graphics_widget.img = pg.ImageItem(border='w')
            next_graphics_widget.view.addItem(next_graphics_widget.img)

            next_graphics_widget_wrapper=QVBoxLayout()
            illumination_source_code=list(channel_mappings.keys())[i]
            for c in self.configurationManager.configurations:
                if c.illumination_source==illumination_source_code:
                    channel_name=c.name
            next_graphics_widget_wrapper.addWidget(QLabel(channel_name))
            next_graphics_widget_wrapper.addWidget(next_graphics_widget)

            row=i//num_columns
            column=i%num_columns
            image_display_layout.addLayout(next_graphics_widget_wrapper, row, column)

            self.graphics_widgets.append(next_graphics_widget)

        self.widget.setLayout(image_display_layout)

    def display_image(self,image,channel_index:int):
        self.graphics_widgets[self.channel_mappings[channel_index]].img.setImage(image,autoLevels=False)
