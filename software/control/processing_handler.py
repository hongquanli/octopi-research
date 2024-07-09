import threading
import queue
import numpy as np
import pandas as pd
import control.utils as utils
from control._def import *
import time

def default_image_preprocessor(image, callable_list):
    """
    :param image: ndarray representing an image
    :param callable_list: List of dictionaries in the form {'func': callable,
    'args': list of positional args, 'kwargs': dict of keyword args}. The function
    should take an image ndarray as its first positional argument,
    and the image should
    not be included in the collection of args/kwargs
    :return: Image with the elements of callable_list applied in sequence
    """
    output_image = np.copy(image)
    for c in callable_list:
        output_image = c['func'](output_image, *c['args'],**c['kwargs'])
    return output_image

def default_upload_fn(I,score, dataHandler, sort=False,disp_th=None):
    """
    :brief: designed to be called by default_process_fn that's using
        the pre-existing process_fov method
    """
    if I is None or len(I) == 0:
        return
    images = I*255
    score_df = pd.DataFrame(score, columns=["output"])

    if dataHandler.images is None:
        dataHandler.load_images(images)
        dataHandler.load_predictions(score_df)
    else:
        dataHandler.add_data(images,score_df,sort=sort,disp_th=disp_th)


def default_process_fn(process_fn, *process_args, **process_kwargs):
    """
    :brief: meant to be queued with args being [process_fov, (all args for process_fov)]
        and kwargs being {'dataHandler': self.microscope.dataHandler,
        'upload_fn':default_upload_fn}
    :return: A process task, i.e. dict of 'function' (callable), 'args' (list), and
     'kwargs' (dict)
    """
    dataHandler = process_kwargs['dataHandler'] # should be a DataHandler instance
    process_kwargs.pop('dataHandler')
    upload_fn = process_kwargs['upload_fn'] # this should be a callable
    process_kwargs.pop('upload_fn')
    multiPointWorker = None
    try:
        multiPointWorker = process_kwargs['multiPointWorker']
        process_kwargs.pop('multiPointWorker')
    except:
        pass
    I, score = process_fn(*process_args, **process_kwargs)
    if I is None or score is None:
        return None
    return_dict = {}
    return_dict['function'] = upload_fn
    return_dict['args'] = [I, score, dataHandler]
    return_dict['kwargs'] = {'multiPointWorker':multiPointWorker}
    return return_dict


def process_fn_with_count_and_display(process_fn, *process_args, **process_kwargs):
    """
    :brief: meant to be queued with args being [process_fov, (all args for process_fov)]
        and kwargs being {'dataHandler': self.microscope.dataHandler,
        'upload_fn':default_upload_fn,
        'multiPointWorker':the MultiPointWorker object calling this}.
        This version really meant to be used with process_fov
        and the DPC segmentation code
    :return: A process task, i.e. dict of 'function' (callable), 'args' (list), and
     'kwargs' (dict)
    """
    # Extract required kwargs
    dataHandler = process_kwargs.pop('dataHandler')
    upload_fn = process_kwargs.pop('upload_fn')
    i = process_kwargs.pop('i')
    j = process_kwargs.pop('j')
    k = process_kwargs.pop('k')

    # Optional kwargs with default values
    multiPointWorker = process_kwargs.pop('multiPointWorker', None)
    sort = process_kwargs.pop('sort', False)
    disp_th = process_kwargs.pop('disp_th', None)

    no_cells = 0
    no_positives = 0
    overlay = None
    dpc_image = None

    if multiPointWorker is not None:
        bf_L = process_args[1]
        bf_R = process_args[2]

        bf_L_area = bf_L.shape[0] * bf_L.shape[1]
        bf_R_area = bf_R.shape[0] * bf_R.shape[1]
        biggest_area = max(bf_L_area, bf_R_area)
        rbc_ratio = biggest_area / (multiPointWorker.crop ** 2)

        dpc_image = utils.generate_dpc(bf_L, bf_R, use_gpu=True)
        process_args = list(process_args)  # Convert to list to append dpc_image
        process_args.append(dpc_image)  # Add dpc_image to args
        process_args = tuple(process_args)  # Add dpc_image to args
        dpc_uint8 = (255 * dpc_image).astype(np.uint8)

        if multiPointWorker.crop > 0:
            bf_L = utils.centerCrop(bf_L, multiPointWorker.crop)
            bf_R = utils.centerCrop(bf_R, multiPointWorker.crop)
            dpc_uint8 = utils.centerCrop(dpc_uint8, multiPointWorker.crop)

        result = multiPointWorker.model.predict_on_images(dpc_uint8)
        # probs = (255 * (result - np.min(result)) / (np.max(result) - np.min(result))).astype(np.uint8)
        threshold = 0.5
        mask = (255 * (result > threshold)).astype(np.uint8)
        color_mask, no_cells = utils.colorize_mask_get_counts(mask)
        overlay = utils.overlay_mask_dpc(color_mask, dpc_uint8)

    I, score = process_fn(*process_args, **process_kwargs)
    if I is None or score is None: 
        return
    no_positives = len(score)

    if multiPointWorker is not None:
        new_counts = {
            "Counted RBC": no_cells,
            "Estimated Total RBC": int(no_cells * rbc_ratio),
            "Total Positives": no_positives,
            "# FOV Processed": 1
        }
        print("emitting detection stats ...")
        print(new_counts)
        multiPointWorker.signal_update_stats.emit(new_counts)
        print("emitting overlay")
        multiPointWorker.image_to_display_multi.emit(overlay, 12)
        multiPointWorker.image_to_display_multi.emit(dpc_uint8, 13)

        if USE_NAPARI_FOR_MULTIPOINT or USE_NAPARI_FOR_TILED_DISPLAY:
            print("emitting segmentation image...")
            multiPointWorker.napari_rtp_layers_update.emit(overlay, "Segmentation Overlay")
            multiPointWorker.napari_rtp_layers_update.emit(dpc_uint8, "DPC")

    return {
        'function': upload_fn,
        'args': [I, score, dataHandler],
        'kwargs': {'sort': sort, 'disp_th': disp_th}
    }


from qtpy.QtCore import *

class ProcessingHandler(QObject):
    """
    :brief: Handler class for parallelizing FOV processing. GENERAL NOTE:
        REMEMBER TO PASS COPIES OF IMAGES WHEN QUEUEING THEM FOR PROCESSING
    """
    finished = Signal(bool)

    def __init__(self):
        super().__init__()
        self.processing_queue = queue.Queue() # elements in this queue are
                                              # dicts in the form
                                              # {'function': callable, 'args':list
                                              # of positional arguments to pass,
                                              # 'kwargs': dict of kwargs to pass}
                                              # a dict in the form {'function':'end'}
                                              # will cause processing to terminate
                                              # the function called should return
                                              # a dict in the same form it received,
                                              # in appropriate form to pass to the
                                              # upload queue

        self.upload_queue = queue.Queue()     # elements in this queue are
                                              # dicts in the form
                                              # {'function': callable, 'args':list
                                              # of positional arguments to pass,
                                              # 'kwargs': dict of kwargs to pass}
                                              # a dict in the form {'function':'end'}
                                              # will cause the uploading to terminate
        self.processing_thread = None
        self.uploading_thread = None

    def processing_queue_handler(self, queue_timeout=None):
        while True:
            processing_task = None
            try:
                processing_task = self.processing_queue.get(timeout=queue_timeout)
            except queue.Empty:
                break
            if processing_task['function'] == 'end':
                self.processing_queue.task_done()
                break
            else:
                upload_task = processing_task['function'](
                                                *processing_task['args'],
                                                **processing_task['kwargs'])
                if upload_task is not None:
                    self.upload_queue.put(upload_task)
                self.processing_queue.task_done()

    def upload_queue_handler(self, queue_timeout=None):
        while True:
            upload_task = None
            try:
                upload_task = self.upload_queue.get(timeout=queue_timeout)
            except queue.Empty:
                break
            if upload_task['function'] == 'end':
                self.upload_queue.task_done()
                break
            else:
                upload_task['function'](*upload_task['args'],**upload_task['kwargs'])
                self.upload_queue.task_done()

    def start_processing(self, queue_timeout=None):
        self.processing_thread =\
        threading.Thread(target=self.processing_queue_handler, args=[queue_timeout])
        self.processing_thread.start()
    def start_uploading(self,queue_timeout=None):
        self.uploading_thread =\
        threading.Thread(target=self.upload_queue_handler,args=[queue_timeout])
        self.uploading_thread.start()
    def end_uploading(self, *args, **kwargs):
        return {'function':'end'}
    def end_processing(self):
        starttime = time.time()
        self.wait_for_processing_completion()
        self.processing_queue.put({'function':self.end_uploading,'args':[],
                                   'kwargs':{}})
        self.processing_queue.put({'function':'end'})

        print("additional time to finish processing", time.time()-starttime)
        self.finished.emit(True)
        print("All processing and uploading tasks are completed.")

    def wait_for_processing_completion(self, timeout=None):
        print("end processing... wait for all processing tasks")
        self.processing_queue.join()
        self.upload_queue.join()