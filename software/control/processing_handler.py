import threading
import queue
import numpy as np
import pandas as pd
import control.utils as utils

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
    if len(I) == 0:
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
    dataHandler = process_kwargs['dataHandler'] # should be a DataHandler instance
    process_kwargs.pop('dataHandler')
    upload_fn = process_kwargs['upload_fn'] # this should be a callable
    process_kwargs.pop('upload_fn')
    multiPointWorker = None
    no_cells = 0
    no_positives = 0
    overlay = None
    dpc_image = None
    try:
        multiPointWorker = process_kwargs['multiPointWorker']
        process_kwargs.pop('multiPointWorker')
    except:
        pass
    sort = False
    disp_th = None
    try:
        sort = process_kwargs['sort']
        process_kwargs.pop('sort')
    except:
        pass
    try:
        disp_th = process_kwargs['disp_th']
        process_kwargs.pop('disp_th')
    except:
        pass
    if multiPointWorker is not None:
        dpc_L = process_args[1]
        dpc_R = process_args[2]
        dpc_L_area = dpc_L.shape[0]*dpc_L.shape[1]
        dpc_R_area = dpc_R.shape[0]*dpc_R.shape[1]
        biggest_area = max(dpc_L_area,dpc_R_area)
        rbc_ratio = biggest_area/(multiPointWorker.crop**2)
        if multiPointWorker.crop > 0:
            dpc_L = utils.centerCrop(dpc_L, multiPointWorker.crop)
            dpc_R = utils.centerCrop(dpc_R, multiPointWorker.crop)
        dpc_image = utils.generate_dpc(dpc_L, dpc_R)
        result = multiPointWorker.model.predict_on_images(dpc_image)
        probs = (255 * (result - np.min(result))/(np.max(result) - np.min(result))).astype(np.uint8)
        threshold = 0.5
        mask = (255*(result > threshold)).astype(np.uint8)
        color_mask, no_cells = utils.colorize_mask_get_counts(mask)
        overlay = utils.overlay_mask_dpc(color_mask, dpc_image)
    I, score = process_fn(*process_args, **process_kwargs)
    no_positives = len(score)
    if multiPointWorker is not None:
        new_counts = {"Counted RBC": no_cells, "Estimated Total RBC":int(no_cells*rbc_ratio) , "Total Positives": no_positives,
                "# FOV Processed":1}
        multiPointWorker.signal_update_stats.emit(new_counts)
        multiPointWorker.image_to_display_multi.emit(overlay, 12)
        multiPointWorker.image_to_display_multi.emit(dpc_image, 13)
    return_dict = {}
    return_dict['function'] = upload_fn
    return_dict['args'] = [I, score, dataHandler]
    return_dict['kwargs'] = {'sort':sort,'disp_th':disp_th}
    return return_dict



class ProcessingHandler():
    """
    :brief: Handler class for parallelizing FOV processing. GENERAL NOTE:
        REMEMBER TO PASS COPIES OF IMAGES WHEN QUEUEING THEM FOR PROCESSING
    """
    def __init__(self):
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
        self.processing_queue.put({'function':self.end_uploading,'args':[],
                                   'kwargs':{}})
        self.processing_queue.put({'function':'end'})

