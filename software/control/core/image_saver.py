# qt libraries
from qtpy.QtCore import QObject, Signal # type: ignore

import control.utils as utils
from control._def import *

from queue import Queue
from threading import Thread, Lock
import time
import numpy as np
from datetime import datetime
import os
import numpy

import imageio as iio
import tifffile

from typing import Optional, List, Union, Tuple
from control.typechecker import TypecheckFunction

class ImageSaver(QObject):

    stop_recording = Signal()

    @TypecheckFunction
    def __init__(self,image_format:ImageFormat=Acquisition.IMAGE_FORMAT):
        QObject.__init__(self)
        self.base_path:str = './'
        self.experiment_ID:str = ''
        self.image_format:ImageFormat = image_format
        self.max_num_image_per_folder:int = 1000
        self.queue:Queue = Queue(10) # max 10 items in the queue
        self.image_lock:Lock = Lock()
        self.stop_signal_received:bool = False
        self.thread = Thread(target=self.process_queue) # type: ignore
        self.thread.start()
        self.counter:int = 0
        self.recording_start_time:float = 0.0
        self.recording_time_limit:float = -1.0

    @TypecheckFunction
    def path_from(base_path:str,experiment_ID:str,folder_ID:str,file_ID:str,frame_ID:str)->str:
        p=os.path.join(base_path,experiment_ID,str(folder_ID),str(file_ID) + '_' + str(frame_ID))
        return p

    #@TypecheckFunction
    def save_image(path:str,image:numpy.ndarray,file_format:ImageFormat):
        if image.dtype == np.uint16 and file_format != ImageFormat.TIFF_COMPRESSED:
            file_format=ImageFormat.TIFF

        # need to use tiff when saving 16 bit images
        if file_format in (ImageFormat.TIFF_COMPRESSED,ImageFormat.TIFF):
            if file_format==ImageFormat.TIFF_COMPRESSED:
                tifffile.imwrite(path + '.tiff',image,compression=8) # adobe deflate / zlib compression
            else:
                iio.imwrite(path + '.tiff',image)
        else:
            assert file_format==ImageFormat.BMP
            iio.imwrite(path + '.bmp',image)

    @TypecheckFunction
    def process_queue(self):
        while True:
            # stop the thread if stop signal is received
            if self.stop_signal_received:
                return
            # process the queue
            try:
                [image,frame_ID,timestamp] = self.queue.get(timeout=0.1)
                self.image_lock.acquire(True)
                folder_ID = int(self.counter/self.max_num_image_per_folder)
                file_ID = int(self.counter%self.max_num_image_per_folder)
                # create a new folder
                if file_ID == 0:
                    os.mkdir(os.path.join(self.base_path,self.experiment_ID,str(folder_ID)))

                saving_path = ImageSaver.path_from(
                    base_path=self.base_path,
                    experiment_ID=self.experiment_ID,
                    folder_ID=str(folder_ID),
                    file_ID=str(file_ID),
                    frame_ID=str(frame_ID))

                ImageSaver.save_image(saving_path,image,self.image_format)

                self.counter = self.counter + 1
                self.queue.task_done()
                self.image_lock.release()
            except:
                pass
                            
    def enqueue(self,image,frame_ID:int,timestamp):
        try:
            self.queue.put_nowait([image,frame_ID,timestamp])
            if ( self.recording_time_limit>0 ) and ( time.time()-self.recording_start_time >= self.recording_time_limit ):
                self.stop_recording.emit()
            # when using self.queue.put(str_), program can be slowed down despite multithreading because of the block and the GIL
        except:
            print('imageSaver queue is full, image discarded')

    @TypecheckFunction
    def set_base_path(self,path:str):
        self.base_path = path

    @TypecheckFunction
    def set_recording_time_limit(self,time_limit:float):
        self.recording_time_limit = time_limit

    @TypecheckFunction
    def prepare_folder_for_new_experiment(self,experiment_ID:str,add_timestamp:bool=True):
        if add_timestamp:
            # generate unique experiment ID
            self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%-S.%f')
        else:
            self.experiment_ID = experiment_ID
        self.recording_start_time = time.time()
        # create a new folder
        try:
            os.mkdir(os.path.join(self.base_path,self.experiment_ID))
            # to do: save configuration
        except:
            pass
        # reset the counter
        self.counter = 0

    @TypecheckFunction
    def close(self):
        self.queue.join()
        self.stop_signal_received = True
        self.thread.join()
