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

