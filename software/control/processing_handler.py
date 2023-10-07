import threading
import queue
import numpy as np
import pandas as pd

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

def default_upload_fn(I,score, dataHandler, multiPointWorker = None):
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
        dataHandler.add_data(images,score_df)
    if multiPointWorker is not None:
        try:
            multiPointWorker.async_detection_stats["Total Parasites"] += len(score)
        except:
            multiPointWorker.async_detection_stats["Total Parasites"] = 0
            multiPointWorker.async_detection_stats["Total Parasites"] += len(score)


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

