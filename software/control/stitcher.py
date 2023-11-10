import subprocess
import shutil
import tifffile
import threading
import queue
import cv2
import time

def ashlar(inputpath, outputpath, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs):
    """
    :brief Uses subprocess Popen to call ashlar with arguments
    :param inputpath: String, path to input file, assumed multipage TIFF
        with metadata Pixels DimensionOrder (XYCZT)
        defined, as well as ID, SizeC/T/X/Y/Z, and Type
    :param outputpath: String, path to output file
    :param kwargs: For other arguments to Ashlar, see labsyspharm/ashlar
        on Github. All arguments must be given in their "word" form, omitting
        the double dash at the start and replacing internal dashes with underscores.
        Only use 0 and 1 for False and True values
    :param stdin: stdin to pass to subprocess handler, defaults to dev null
    :param stdout: stdout to pass to subprocess handler, defaults to dev null
    :param stderr: stderr to pass to subprocess handler, defaults to dev null
    :return: A subprocess.Popen object representing the ongoing ashlar process.
        Can be polled or waited for.
    """
    if shutil.which("ashlar") == None: # raise exception if ashlar can't be found
        raise Exception("No command found")
    cmd_path = shutil.which("ashlar")
    cmd_list = [cmd_path, inputpath, "-o", outputpath]
    for k in kwargs.keys(): # input other args to ashlar
        cmd_list.append("--"+str(k).replace("_","-"))
        cmd_list.append(str(kwargs[k]))
    return subprocess.Popen(cmd_list, stdin=stdin, stdout=stdout, stderr=stderr)

def default_image_reader(filepath):
    """
    :brief: default image reader to pass to the ometiff writer, patterned after
        the example with Rinni's example_3x3 data
    :param filepath: path to image file
    :return: ndarray with image data
    """
    img = cv2.imread(filepath)
    img = cv2.cvtColor(img,cv2.COLOR_RGB2BGR)
    return img

def queued_ometiff_writer(outputpath, file_queue, bigtiff= True,\
        image_reader=default_image_reader, queue_timeout=None):
    """
    :brief: receives images in a queue until a termination signal is reached, and
        writes each tile to an OME TIFF file
    :param outputpath: path to write OME TIFF with tiles to
    :param: file_queue: queue.Queue object with objects that are dicts in the form
        {"filepath": (string), "metadata": (dict)}, where the dict in
        "metadata" is passed to tifffile.TiffWriter. If an object is in the form
        {"filepath":0}, this terminates the process
    :param bigtiff: Whether to pass bigtiff = True to tiffwriter. Default True
    :param image_reader: function that takes a file path as arguments and returns
            an ndarray. Defaults to function modeled on the example_3x3 examples
    :param queue_timeout: timeout in seconds when waiting for a file to become
        available. default None
    """
    with tifffile.TiffWriter(outputpath, bigtiff=bigtiff) as tif:
        while True:
            tile_info = None
            try:
                tile_info = file_queue.get(timeout=queue_timeout)
            except queue.Empty:
                break
            if tile_info["filepath"] == 0:
                file_queue.task_done()
                break
            else:
                img = image_reader(tile_info["filepath"])
                metadata = tile_info["metadata"]
                tif.write(img, metadata=metadata)
                file_queue.task_done()

def queued_ashlar_waiter(ometiff_writer_thread, process_slot, inputpath, outputpath, courtesy_wait=1, **kwargs):
    """
    :brief: Wrapper around ashlar to make it wait for a file queue to finish
        processing and put the ashlar process in a list. Meant to be run in
        a thread
    :param ometiff_writer_thread: thread object to wait
    :param process_slot: list to put ashlar process (a subprocess.Popen() object)
        into
    :param inputpath: OME-TIFF file path to give to ashlar as input
    :param outputpath: OME-TIFF file path for ashlar to write its output to
    :param courtesy_wait: wait in seconds after which to run ashlar
    :param kwargs: all other arguments to pass to ashlar call
    """
    ometiff_writer_thread.join()
    time.sleep(courtesy_wait)
    ashlar_process = ashlar(inputpath, outputpath, **kwargs)
    process_slot[0] = ashlar_process

class Stitcher():
    """
    :brief: Spawns a process for combining tiles as they are acquired
        into an OME TIFF file, followed by running ashlar to stitch them
        together.
    """
    def __init__(self, tiled_file_path="", stitched_file_path="", ashlar_args = {},
                 auto_run_ashlar = False, image_reader = default_image_reader):
        """
        :brief: Initializes class, creates control variables.
        :param tiled_file_path: output file to write the tiled OME-TIFF to, to
                        pass to ashlar as an input
        :param stitched_file_path: output file to write ashlar's stitching to
        :param ashlar_args: dict of additional arguments to ashlar besides I/O file,
                        will be unpacked and passed to ashlar wrapper. can also put
                        stdin/stdout/stderr for the ashlar process here
        :param auto_run_ashlar: Whether to automatically run ashlar after all tiles
                        are acquired
        :param image_reader: function to pass to queued_ometiff_writer as an image reader
        """
        self.file_queue = queue.Queue() # queue_object loaded with dicts in the form
                                    # {"filepath": (string), "metadata": (dict)}, where
                                    # filepath is the path to a tile and metadata is a
                                    # dictionary to be passed to a tifffile.TiffWriter.write
                                    # function
                                    # a dict in the form {"filepath":0} can be put to indicate
                                    # the last tile has been read
        self.auto_run_ashlar = auto_run_ashlar # if True, when "all_tiles_acquired" in
                                    # controldict is set to True, after last
                                    # tile has been written with OME tiff, calls
                                    # ashlar wrapper with tiled_file_path as input,
                                    # stitched_file_path as output, and ashlar_args
                                    # as additional keyword arguments
        self.tiled_file_path = tiled_file_path
        self.stitched_file_path = stitched_file_path
        self.ashlar_args = ashlar_args
        self.ashlar_process_list = [None] # stores ashlar process, a subprocess.Popen object, at
                                 # index 0. If ashlar has not been started yet, this
                                 # list contains None at index 0
        self.ashlar_waiter_thread = None
        self.image_reader = image_reader
        self.ometiff_writer_thread = None
    def add_tile(self, filepath, metadata):
        """
        :brief: Adds a tile by path and metadata
        :param filepath: file path of tile
        :param metadata: dict to be passed to a TiffWriter when writing this
            to a combined OME TIFF file
        """
        self.file_queue.put({"filepath":filepath,"metadata":metadata})
    def all_tiles_added(self, auto_run_ashlar= None,\
            inputpath=None,\
            outputpath=None,\
            courtesy_wait=0.5,\
            **kwargs):
        if auto_run_ashlar == None:
            auto_run_ashlar = self.auto_run_ashlar
        if inputpath == None:
            inputpath = self.tiled_file_path
        if outputpath == None:
            outputpath = self.stitched_file_path
        """
        :brief: Sends signal to queued tiff writer that all tiles have been added,
            and blocks until the whole OME TIFF has been written.
        :param auto_run_ashlar: Whether to spin up an ashlar instance immediately after.
        :param inputpath: input path to give to ashlar
        :param outputpath: output path to give to ashlar
        :param courtesy_wait: how long for the ashlar waiter to wait after all tiles
            have been written
        :param kwargs: all other arguments to give to ashlar
        """
        self.file_queue.put({"filepath":0,"metadata":0})
        if auto_run_ashlar:
            self.ashlar_waiter_thread = threading.Thread(target=queued_ashlar_waiter,\
                    args=[self.ometiff_writer_thread, self.ashlar_process_list, inputpath,outputpath,\
                        courtesy_wait],\
                    kwargs=kwargs)
            self.ashlar_waiter_thread.start()
    def start_ometiff_writer(self, outputpath=None, bigtiff= True,\
            image_reader=None, queue_timeout=None):
        """
        :brief: start OME-TIFF writer
        :param outputpath: path to write tiled TIFF file to
        :param bigtiff: bigtiff argument to pass to TiffWriter
        :param image_reader: image reader function to pass to TIFF writer when parsing tiles
        :param queue_timeout: queue_timeout parameter to pass to TIFF writer
        """
        if outputpath == None:
            outputpath = self.tiled_file_path
        if image_reader == None:
            image_reader = self.image_reader
        self.ometiff_writer_thread = threading.Thread(target=queued_ometiff_writer,\
                    args=[outputpath, self.file_queue, bigtiff, image_reader,queue_timeout])
        self.ometiff_writer_thread.start()
    def run_ashlar(self, inputpath=None,outputpath=None,\
            courtesy_wait=0.5,**kwargs):
        """
        :brief: spin up a thread that waits to run ashlar once all tiles have been run through.
            ONLY CALL IF all_tiles_added HAS BEEN CALLED WITH auto_run_ashlar=False
        """
        if inputpath==None:
            inputpath = self.tiled_file_path
        if outputpath == None:
            outputpath = self.stitched_file_path
        self.ashlar_waiter_thread = threading.Thread(target=queued_ashlar_waiter,\
                args=[self.ometiff_writer_thread,self.ashlar_process_list,inputpath,outputpath,\
                courtesy_wait],\
                kwargs=kwargs)
        self.ashlar_waiter_thread.start()
