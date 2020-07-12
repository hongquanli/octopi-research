# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import control.utils as utils
from control._def import *
import control.tracking as tracking

from queue import Queue
from threading import Thread, Lock
import time
import numpy as np
import pyqtgraph as pg
import cv2
from datetime import datetime

class StreamHandler(QObject):

    image_to_display = Signal(np.ndarray)
    packet_image_to_write = Signal(np.ndarray, int, float)
    packet_image_for_tracking = Signal(np.ndarray, int, float)
    signal_new_frame_received = Signal()

    def __init__(self,crop_width=Acquisition.CROP_WIDTH,crop_height=Acquisition.CROP_HEIGHT,display_resolution_scaling=0.5):
        QObject.__init__(self)
        self.fps_display = 1
        self.fps_save = 1
        self.fps_track = 1
        self.timestamp_last_display = 0
        self.timestamp_last_save = 0
        self.timestamp_last_track = 0

        self.crop_width = crop_width
        self.crop_height = crop_height
        self.display_resolution_scaling = display_resolution_scaling

        self.save_image_flag = False
        self.track_flag = False
        self.handler_busy = False

        # for fps measurement
        self.timestamp_last = 0
        self.counter = 0
        self.fps_real = 0

    def start_recording(self):
        self.save_image_flag = True

    def stop_recording(self):
        self.save_image_flag = False

    def start_tracking(self):
        self.tracking_flag = True

    def stop_tracking(self):
        self.tracking_flag = False

    def set_display_fps(self,fps):
        self.fps_display = fps

    def set_save_fps(self,fps):
        self.fps_save = fps

    def set_crop(self,crop_width,height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def set_display_resolution_scaling(self, display_resolution_scaling):
        self.display_resolution_scaling = display_resolution_scaling/100
        print(self.display_resolution_scaling)

    def on_new_frame(self, camera):

        camera.image_locked = True
        self.handler_busy = True
        self.signal_new_frame_received.emit() # self.liveController.turn_off_illumination()

        # measure real fps
        timestamp_now = round(time.time())
        if timestamp_now == self.timestamp_last:
            self.counter = self.counter+1
        else:
            self.timestamp_last = timestamp_now
            self.fps_real = self.counter
            self.counter = 0
            print('real camera fps is ' + str(self.fps_real))

        # crop image
        image_cropped = utils.crop_image(camera.current_frame,self.crop_width,self.crop_height)

        # send image to display
        time_now = time.time()
        if time_now-self.timestamp_last_display >= 1/self.fps_display:
            # self.image_to_display.emit(cv2.resize(image_cropped,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
            self.image_to_display.emit(utils.crop_image(image_cropped,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)))
            self.timestamp_last_display = time_now

        # send image to write
        if self.save_image_flag and time_now-self.timestamp_last_save >= 1/self.fps_save:
            if camera.is_color:
                image_cropped = cv2.cvtColor(image_cropped,cv2.COLOR_RGB2BGR)
            self.packet_image_to_write.emit(image_cropped,camera.frame_ID,camera.timestamp)
            self.timestamp_last_save = time_now

        # send image to track
        if self.track_flag and time_now-self.timestamp_last_track >= 1/self.fps_track:
            # track is a blocking operation - it needs to be
            # @@@ will cropping before emitting the signal lead to speedup?
            self.packet_image_for_tracking.emit(image_cropped,camera.frame_ID,camera.timestamp)
            self.timestamp_last_track = time_now

        self.handler_busy = False
        camera.image_locked = False

    '''
    def on_new_frame_from_simulation(self,image,frame_ID,timestamp):
        # check whether image is a local copy or pointer, if a pointer, needs to prevent the image being modified while this function is being executed
        
        self.handler_busy = True

        # crop image
        image_cropped = utils.crop_image(image,self.crop_width,self.crop_height)

        # send image to display
        time_now = time.time()
        if time_now-self.timestamp_last_display >= 1/self.fps_display:
            self.image_to_display.emit(cv2.resize(image_cropped,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
            self.timestamp_last_display = time_now

        # send image to write
        if self.save_image_flag and time_now-self.timestamp_last_save >= 1/self.fps_save:
            self.packet_image_to_write.emit(image_cropped,frame_ID,timestamp)
            self.timestamp_last_save = time_now

        # send image to track
        if time_now-self.timestamp_last_display >= 1/self.fps_track:
            # track emit
            self.timestamp_last_track = time_now

        self.handler_busy = False
    '''

class ImageSaver(QObject):

    stop_recording = Signal()

    def __init__(self,image_format='bmp'):
        QObject.__init__(self)
        self.base_path = './'
        self.experiment_ID = ''
        self.image_format = image_format
        self.max_num_image_per_folder = 1000
        self.queue = Queue(10) # max 10 items in the queue
        self.image_lock = Lock()
        self.stop_signal_received = False
        self.thread = Thread(target=self.process_queue)
        self.thread.start()
        self.counter = 0
        self.recording_start_time = 0
        self.recording_time_limit = -1

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
                saving_path = os.path.join(self.base_path,self.experiment_ID,str(folder_ID),str(file_ID) + '.' + self.image_format)
                
                cv2.imwrite(saving_path,image)
                self.counter = self.counter + 1
                self.queue.task_done()
                self.image_lock.release()
            except:
                pass
                            
    def enqueue(self,image,frame_ID,timestamp):
        try:
            self.queue.put_nowait([image,frame_ID,timestamp])
            if ( self.recording_time_limit>0 ) and ( time.time()-self.recording_start_time >= self.recording_time_limit ):
                self.stop_recording.emit()
            # when using self.queue.put(str_), program can be slowed down despite multithreading because of the block and the GIL
        except:
            print('imageSaver queue is full, image discarded')

    def set_base_path(self,path):
        self.base_path = path

    def set_recording_time_limit(self,time_limit):
        self.recording_time_limit = time_limit

    def start_new_experiment(self,experiment_ID):
        # generate unique experiment ID
        self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d %H-%M-%-S.%f')
        self.recording_start_time = time.time()
        # create a new folder
        try:
            os.mkdir(os.path.join(self.base_path,self.experiment_ID))
        except:
            pass
        # reset the counter
        self.counter = 0

    def close(self):
        self.queue.join()
        self.stop_signal_received = True
        self.thread.join()

'''
class ImageSaver_MultiPointAcquisition(QObject):
'''

class ImageDisplay(QObject):

    image_to_display = Signal(np.ndarray)

    def __init__(self):
        QObject.__init__(self)
        self.queue = Queue(10) # max 10 items in the queue
        self.image_lock = Lock()
        self.stop_signal_received = False
        self.thread = Thread(target=self.process_queue)
        self.thread.start()        
        
    def process_queue(self):
        while True:
            # stop the thread if stop signal is received
            if self.stop_signal_received:
                return
            # process the queue
            try:
                [image,frame_ID,timestamp] = self.queue.get(timeout=0.1)
                self.image_lock.acquire(True)
                self.image_to_display.emit(image)
                self.image_lock.release()
                self.queue.task_done()
            except:
                pass

    # def enqueue(self,image,frame_ID,timestamp):
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

class LiveController(QObject):

    def __init__(self,camera,microcontroller):
        QObject.__init__(self)
        self.camera = camera
        self.microcontroller = microcontroller
        self.microscope_mode = None
        self.trigger_mode = TriggerMode.SOFTWARE # @@@ change to None
        self.is_live = False
        self.was_live_before_autofocus = False
        self.was_live_before_multipoint = False

        self.fps_software_trigger = 1;
        self.timer_software_trigger_interval = (1/self.fps_software_trigger)*1000

        self.timer_software_trigger = QTimer()
        self.timer_software_trigger.setInterval(self.timer_software_trigger_interval)
        self.timer_software_trigger.timeout.connect(self.trigger_acquisition_software)

        self.trigger_ID = -1

        self.fps_real = 0
        self.counter = 0
        self.timestamp_last = 0

        self.exposure_time_bfdf_preset = None
        self.exposure_time_fl_preset = None
        self.exposure_time_fl_preview_preset = None
        self.analog_gain_bfdf_preset = None
        self.analog_gain_fl_preset = None
        self.analog_gain_fl_preview_preset = None

    # illumination control
    def turn_on_illumination(self):
        if self.mode == MicroscopeMode.BFDF:
            self.microcontroller.toggle_LED(1)
        else:
            self.microcontroller.toggle_laser(1)

    def turn_off_illumination(self):
        if self.mode == MicroscopeMode.BFDF:
            self.microcontroller.toggle_LED(0)
        else:
            self.microcontroller.toggle_laser(0)

    def start_live(self):
        self.is_live = True
        if self.trigger_mode == TriggerMode.SOFTWARE:
            self._start_software_triggerred_acquisition()

    def stop_live(self):
    	if self.is_live:
            self.is_live = False
            if self.trigger_mode == TriggerMode.SOFTWARE:
                self._stop_software_triggerred_acquisition()
            self.turn_off_illumination()

    # software trigger related
    def trigger_acquisition_software(self):
        self.turn_on_illumination()
        self.trigger_ID = self.trigger_ID + 1
        self.camera.send_trigger()
        # measure real fps
        timestamp_now = round(time.time())
        if timestamp_now == self.timestamp_last:
            self.counter = self.counter+1
        else:
            self.timestamp_last = timestamp_now
            self.fps_real = self.counter
            self.counter = 0
            print('real trigger fps is ' + str(self.fps_real))

    def _start_software_triggerred_acquisition(self):
        self.timer_software_trigger.start()

    def _set_software_trigger_fps(self,fps_software_trigger):
        self.fps_software_trigger = fps_software_trigger
        self.timer_software_trigger_interval = (1/self.fps_software_trigger)*1000
        self.timer_software_trigger.setInterval(self.timer_software_trigger_interval)

    def _stop_software_triggerred_acquisition(self):
        self.timer_software_trigger.stop()

    # trigger mode and settings
    def set_trigger_mode(self,mode):
        if mode == TriggerMode.SOFTWARE:
            self.camera.set_software_triggered_acquisition()
        if mode == TriggerMode.HARDWARE:
            self.camera.set_hardware_triggered_acquisition()
        if mode == TriggerMode.CONTINUOUS:
            self.camera.set_continuous_acquisition()

    def set_trigger_fps(self,fps):
        if self.trigger_mode == TriggerMode.SOFTWARE:
            self._set_software_trigger_fps(fps)
    
    # set microscope mode
    # @@@ to do: change softwareTriggerGenerator to TriggerGeneratror
    def set_microscope_mode(self,mode):
        print("setting microscope mode to " + mode)
        
        # temporarily stop live while changing mode
        if self.is_live is True:
            self.timer_software_trigger.stop()
            self.turn_off_illumination()
        
        self.mode = mode
        if self.mode == MicroscopeMode.BFDF:
            self.camera.set_exposure_time(self.exposure_time_bfdf_preset)
            self.camera.set_analog_gain(self.analog_gain_bfdf_preset)
        elif self.mode == MicroscopeMode.FLUORESCENCE:
            self.camera.set_exposure_time(self.exposure_time_fl_preset)
            self.camera.set_analog_gain(self.analog_gain_fl_preset)
        elif self.mode == MicroscopeMode.FLUORESCENCE_PREVIEW:
            self.camera.set_exposure_time(self.exposure_time_fl_preview_preset)
            self.camera.set_analog_gain(self.analog_gain_fl_preview_preset)

        # restart live 
        if self.is_live is True:
            self.turn_on_illumination()
            self.timer_software_trigger.start()

    def get_trigger_mode(self):
        return self.trigger_mode

    def set_exposure_time_bfdf_preset(self,exposure_time):
        self.exposure_time_bfdf_preset = exposure_time
    def set_exposure_time_fl_preset(self,exposure_time):
        self.exposure_time_fl_preset = exposure_time
    def set_exposure_time_fl_preview_preset(self,exposure_time):
        self.exposure_time_fl_preview_preset = exposure_time
    def set_analog_gain_bfdf_preset(self,analog_gain):
        self.analog_gain_bfdf_preset = analog_gain
    def set_analog_gain_fl_preset(self,analog_gain):
        self.analog_gain_fl_preset = analog_gain
    def set_analog_gain_fl_preview_preset(self,analog_gain):
        self.analog_gain_fl_preview_preset = analog_gain

    # slot
    def on_new_frame(self):
        if self.fps_software_trigger <= 5:
            self.turn_off_illumination()

class NavigationController(QObject):

    xPos = Signal(float)
    yPos = Signal(float)
    zPos = Signal(float)

    def __init__(self,microcontroller):
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.x_pos = 0
        self.y_pos = 0
        self.z_pos = 0
        self.timer_read_pos = QTimer()
        self.timer_read_pos.setInterval(PosUpdate.INTERVAL_MS)
        self.timer_read_pos.timeout.connect(self.update_pos)
        self.timer_read_pos.start()

    def move_x(self,delta):
        self.microcontroller.move_x(delta)
        self.x_pos = self.x_pos + delta
        #self.xPos.emit(self.x_pos)

    def move_y(self,delta):
        self.microcontroller.move_y(delta)
        self.y_pos = self.y_pos + delta
        #self.yPos.emit(self.y_pos)

    def move_z(self,delta):
        self.microcontroller.move_z(delta)
        self.z_pos = self.z_pos + delta
        #self.zPos.emit(self.z_pos*1000)

    def update_pos(self):
        pos = self.microcontroller.read_received_packet_nowait()
        if pos is None:
            return
        self.x_pos = utils.unsigned_to_signed(pos[0:3],MicrocontrollerDef.N_BYTES_POS)/Motion.STEPS_PER_MM_XY # @@@TODO@@@: move to microcontroller?
        self.y_pos = utils.unsigned_to_signed(pos[3:6],MicrocontrollerDef.N_BYTES_POS)/Motion.STEPS_PER_MM_XY # @@@TODO@@@: move to microcontroller?
        self.z_pos = utils.unsigned_to_signed(pos[6:9],MicrocontrollerDef.N_BYTES_POS)/Motion.STEPS_PER_MM_Z  # @@@TODO@@@: move to microcontroller?
        self.xPos.emit(self.x_pos)
        self.yPos.emit(self.y_pos)
        self.zPos.emit(self.z_pos*1000)

    def home(self):
        self.microcontroller.move_x(-self.x_pos)
        self.microcontroller.move_y(-self.y_pos)

class AutoFocusController(QObject):

    z_pos = Signal(float)
    autofocusFinished = Signal()
    image_to_display = Signal(np.ndarray)

    def __init__(self,camera,navigationController,liveController):
        QObject.__init__(self)
        self.camera = camera
        self.navigationController = navigationController
        self.liveController = liveController
        self.N = None
        self.deltaZ = None
        self.crop_width = AF.CROP_WIDTH
        self.crop_height = AF.CROP_HEIGHT

    def set_N(self,N):
        self.N = N

    def set_deltaZ(self,deltaZ_um):
        self.deltaZ = deltaZ_um/1000

    def set_crop(self,crop_width,height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def autofocus(self):

        # stop live
        if self.liveController.is_live:
            self.liveController.was_live_before_autofocus = True
            self.liveController.stop_live()

        # temporarily disable call back -> image does not go through streamHandler
        if self.camera.callback_is_enabled:
            self.camera.callback_was_enabled_before_autofocus = True
            self.camera.stop_streaming()
            self.camera.disable_callback()
            self.camera.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
        
        # @@@ to add: increase gain, decrease exposure time
        # @@@ can move the execution into a thread
        focus_measure_vs_z = [0]*self.N
        focus_measure_max = 0

        z_af_offset = self.deltaZ*round(self.N/2)
        self.navigationController.move_z(-z_af_offset)

        steps_moved = 0
        for i in range(self.N):
            self.navigationController.move_z(self.deltaZ)
            steps_moved = steps_moved + 1
            self.liveController.turn_on_illumination()
            self.camera.send_trigger()
            image = self.camera.read_frame()
            self.liveController.turn_off_illumination()
            image = utils.crop_image(image,self.crop_width,self.crop_height)
            self.image_to_display.emit(image)
            QApplication.processEvents()
            timestamp_0 = time.time() # @@@ to remove
            focus_measure = utils.calculate_focus_measure(image)
            timestamp_1 = time.time() # @@@ to remove
            print('             calculating focus measure took ' + str(timestamp_1-timestamp_0) + ' second')
            focus_measure_vs_z[i] = focus_measure
            print(i,focus_measure)
            focus_measure_max = max(focus_measure, focus_measure_max)
            if focus_measure < focus_measure_max*AF.STOP_THRESHOLD:
                break

        idx_in_focus = focus_measure_vs_z.index(max(focus_measure_vs_z))
        self.navigationController.move_z((idx_in_focus-steps_moved)*self.deltaZ)
        if idx_in_focus == 0:
            print('moved to the bottom end of the AF range')
        if idx_in_focus == self.N-1:
            print('moved to the top end of the AF range')

        if self.camera.callback_was_enabled_before_autofocus:
            self.camera.stop_streaming()
            self.camera.enable_callback()
            self.camera.start_streaming()
            self.camera.callback_was_enabled_before_autofocus = False

        if self.liveController.was_live_before_autofocus:
            self.liveController.start_live()
            self.liveController.was_live = False
        
        print('autofocus finished')
        self.autofocusFinished.emit()

class MultiPointController(QObject):

    acquisitionFinished = Signal()
    image_to_display = Signal(np.ndarray)

    x_pos = Signal(float)
    y_pos = Signal(float)
    z_pos = Signal(float)

    def __init__(self,camera,navigationController,liveController,autofocusController):
        QObject.__init__(self)

        self.camera = camera
        self.navigationController = navigationController
        self.liveController = liveController
        self.autofocusController = autofocusController
        self.NX = 1
        self.NY = 1
        self.NZ = 1
        self.Nt = 1
        self.deltaX = Acquisition.DX
        self.deltaY = Acquisition.DY
        self.deltaZ = Acquisition.DZ/1000
        self.deltat = 0
        self.do_bfdf = False
        self.do_fluorescence = False
        self.do_autofocus = False
        self.crop_width = Acquisition.CROP_WIDTH
        self.crop_height = Acquisition.CROP_HEIGHT
        self.display_resolution_scaling = Acquisition.IMAGE_DISPLAY_SCALING_FACTOR
        self.counter = 0
        self.experiment_ID = None
        self.base_path = None

    def set_NX(self,N):
        self.NX = N
    def set_NY(self,N):
        self.NY = N
    def set_NZ(self,N):
        self.NZ = N
    def set_Nt(self,N):
        self.Nt = N
    def set_deltaX(self,delta):
        self.deltaX = delta
    def set_deltaY(self,delta):
        self.deltaY = delta
    def set_deltaZ(self,delta_um):
        self.deltaZ = delta_um/1000
    def set_deltat(self,delta):
        self.deltat = delta
    def set_bfdf_flag(self,flag):
        self.do_bfdf = flag
    def set_fluorescence_flag(self,flag):
        self.do_fluorescence = flag
    def set_af_flag(self,flag):
        self.do_autofocus = flag

    def set_crop(self,crop_width,height):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def set_base_path(self,path):
        self.base_path = path

    def start_new_experiment(self,experiment_ID): # @@@ to do: change name to prepare_folder_for_new_experiment
        # generate unique experiment ID
        self.experiment_ID = experiment_ID + '_' + datetime.now().strftime('%Y-%m-%d %H-%M-%-S.%f')
        self.recording_start_time = time.time()
        # create a new folder
        try:
            os.mkdir(os.path.join(self.base_path,self.experiment_ID))
        except:
            pass
        
    def run_acquisition(self): # @@@ to do: change name to run_experiment
        print('start multipoint')
        print(str(self.Nt) + '_' + str(self.NX) + '_' + str(self.NY) + '_' + str(self.NZ))

        self.time_point = 0
        self.single_acquisition_in_progress = False
        self.acquisitionTimer = QTimer()
        self.acquisitionTimer.setInterval(self.deltat*1000)
        self.acquisitionTimer.timeout.connect(self._on_acquisitionTimer_timeout)
        self.acquisitionTimer.start()
        self.acquisitionTimer.timeout.emit() # trigger the first acquisition

    '''
    def run_acquisition(self):
        # stop live
        if self.liveController.is_live:
            self.liveController.was_live = True
            self.liveController.stop_live() # @@@ to do: also uncheck the live button

        thread = Thread(target=self.acquisition_thread)
        thread.start()
        thread.join()
        # restart live
        if self.liveController.was_live:
            self.liveController.start_live()
        # emit acquisitionFinished signal
        self.acquisitionFinished.emit()

    def acquisition_thread(self):

        if self.liveController.get_trigger_mode() == TriggerMode.SOFTWARE: # @@@ to do: move trigger mode to camera
            
            print('start multipoint')
            print(str(self.Nt) + '_' + str(self.NX) + '_' + str(self.NY) + '_' + str(self.NZ))

            # disable callback
            if self.camera.callback_is_enabled:
                self.camera.callback_is_enabled = False
                self.camera.callback_was_enabled = True
                self.camera.stop_streaming()
                self.camera.disable_callback()
                self.camera.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
            
            # do the multipoint acquisition
            for l in range(self.Nt):

                # for each time point, create a new folder
                os.mkdir(os.path.join(self.base_path,self.experiment_ID,str(l)))
                current_path = os.path.join(self.base_path,self.experiment_ID,str(l))

                # along y
                for i in range(self.NY):

                    # along x
                    for j in range(self.NX):

                        # z-stack
                        for k in range(self.NZ):

                            # perform AF only if when not taking z stack
                            if (self.NZ == 1) and (self.do_autofocus) and (self.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
                                self.autofocusController.autofocus()

                            file_ID = str(i) + '_' + str(j) + '_' + str(k)

                            # take bf
                            if self.do_bfdf:
                                self.liveController.set_microscope_mode(MicroscopeMode.BFDF)
                                self.liveController.turn_on_illumination()
                                self.camera.send_trigger()
                                image = self.camera.read_frame()
                                self.liveController.turn_off_illumination()
                                image = utils.crop_image(image,self.crop_width,self.crop_height)
                                saving_path = os.path.join(current_path, file_ID + '_bf' + '.' + Acquisition.IMAGE_FORMAT)
                                cv2.imwrite(saving_path,image)
                                self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))

                            # take fluorescence
                            if self.do_fluorescence:
                                self.liveController.set_microscope_mode(MicroscopeMode.FLUORESCENCE)
                                self.liveController.turn_on_illumination()
                                self.camera.send_trigger()
                                image = self.camera.read_frame()
                                self.liveController.turn_off_illumination()
                                image = utils.crop_image(image,self.crop_width,self.crop_height)
                                saving_path = os.path.join(current_path, file_ID + '_fluorescence' + '.' + Acquisition.IMAGE_FORMAT)
                                cv2.imwrite(saving_path,image)
                                self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))

                            # move z
                            if k < self.NZ - 1:
                                self.navigationController.move_z(self.deltaZ)

                        # move z back
                        self.navigationController.move_z(-self.deltaZ*(self.NZ-1))

                        # move x
                        if j < self.NX - 1:
                            self.navigationController.move_x(self.deltaX)

                    # move x back
                    self.navigationController.move_x(-self.deltaX*(self.NX-1))

                    # move y
                    if i < self.NY - 1:
                        self.navigationController.move_y(self.deltaY)

                # move y back
                self.navigationController.move_y(-self.deltaY*(self.NY-1))
                            
                # sleep until the next acquisition # @@@ to do: change to timer instead
                if l < self.Nt - 1:
                    time.sleep(self.deltat)

            print('Multipoint acquisition finished')

            # re-enable callback
            if self.camera.callback_was_enabled:
                self.camera.stop_streaming()
                self.camera.enable_callback()
                self.camera.start_streaming()
                self.camera.callback_is_enabled = True
                self.camera.callback_was_enabled = False
    '''
    def _on_acquisitionTimer_timeout(self):
    	# check if the last single acquisition is ongoing
        if self.single_acquisition_in_progress is True:
            # skip time point if self.deltat is nonzero
            if self.deltat > 0.1: # @@@ to do: make this more elegant - note that both self.deltat is not 0 and self.deltat is not .0 don't work
                self.time_point = self.time_point + 1
                # stop the timer if number of time points is equal to Nt (despite some time points may have been skipped)
                if self.time_point >= self.Nt:
                    self.acquisitionTimer.stop()
                else:
                	print('the last acquisition has not completed, skip time point ' + str(self.time_point))
            return
        # if not, run single acquisition
        self._run_single_acquisition()

    def _run_single_acquisition(self):           
        self.single_acquisition_in_progress = True
        self.FOV_counter = 0

        print('multipoint acquisition - time point ' + str(self.time_point))

        # stop live
        if self.liveController.is_live:
            self.liveController.was_live_before_multipoint = True
            self.liveController.stop_live() # @@@ to do: also uncheck the live button

        # disable callback
        if self.camera.callback_is_enabled:
            self.camera.callback_was_enabled_before_multipoint = True
            self.camera.stop_streaming()
            self.camera.disable_callback()
            self.camera.start_streaming() # @@@ to do: absorb stop/start streaming into enable/disable callback - add a flag is_streaming to the camera class
        
        # do the multipoint acquisition

        # for each time point, create a new folder
        current_path = os.path.join(self.base_path,self.experiment_ID,str(self.time_point))
        os.mkdir(current_path)

        # along y
        for i in range(self.NY):

            # along x
            for j in range(self.NX):

                # z-stack
                for k in range(self.NZ):

                    # perform AF only if when not taking z stack
                    if (self.NZ == 1) and (self.do_autofocus) and (self.FOV_counter%Acquisition.NUMBER_OF_FOVS_PER_AF==0):
                        self.autofocusController.autofocus()

                    file_ID = str(i) + '_' + str(j) + '_' + str(k)

                    # take bf
                    if self.do_bfdf:
                        self.liveController.set_microscope_mode(MicroscopeMode.BFDF)
                        self.liveController.turn_on_illumination()
                        print('take bf image')
                        self.camera.send_trigger() 
                        image = self.camera.read_frame()
                        self.liveController.turn_off_illumination()
                        image = utils.crop_image(image,self.crop_width,self.crop_height)
                        saving_path = os.path.join(current_path, file_ID + '_bf' + '.' + Acquisition.IMAGE_FORMAT)
                        # self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
                        self.image_to_display.emit(utils.crop_image(image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)))
                        if self.camera.is_color:
                            image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)
                        cv2.imwrite(saving_path,image)
                        QApplication.processEvents()

                    # take fluorescence
                    if self.do_fluorescence:
                        self.liveController.set_microscope_mode(MicroscopeMode.FLUORESCENCE)
                        self.liveController.turn_on_illumination()
                        self.camera.send_trigger()
                        image = self.camera.read_frame()
                        print('take fluorescence image')
                        self.liveController.turn_off_illumination()
                        image = utils.crop_image(image,self.crop_width,self.crop_height)
                        saving_path = os.path.join(current_path, file_ID + '_fluorescence' + '.' + Acquisition.IMAGE_FORMAT)
                        self.image_to_display.emit(utils.crop_image(image,round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)))
                        # self.image_to_display.emit(cv2.resize(image,(round(self.crop_width*self.display_resolution_scaling), round(self.crop_height*self.display_resolution_scaling)),cv2.INTER_LINEAR))
                        if self.camera.is_color:
                            image = cv2.cvtColor(image,cv2.COLOR_RGB2BGR)                        
                        cv2.imwrite(saving_path,image)                        
                        QApplication.processEvents()
                    
                    if self.do_bfdf is not True and self.do_fluorescence is not True:
                        QApplication.processEvents()

                    # move z
                    if k < self.NZ - 1:
                        self.navigationController.move_z(self.deltaZ)
                
                # move z back
                self.navigationController.move_z(-self.deltaZ*(self.NZ-1))

                # update FOV counter
                self.FOV_counter = self.FOV_counter + 1

                # move x
                if j < self.NX - 1:
                    self.navigationController.move_x(self.deltaX)

            # move x back
            self.navigationController.move_x(-self.deltaX*(self.NX-1))

            # move y
            if i < self.NY - 1:
                self.navigationController.move_y(self.deltaY)

        # move y back
        self.navigationController.move_y(-self.deltaY*(self.NY-1))
                        
        # re-enable callback
        if self.camera.callback_was_enabled_before_multipoint:
            self.camera.stop_streaming()
            self.camera.enable_callback()
            self.camera.start_streaming()
            self.camera.callback_was_enabled_before_multipoint = False
        
        if self.liveController.was_live_before_multipoint:
            self.liveController.start_live()
            # emit acquisitionFinished signal
            self.acquisitionFinished.emit()
        
        # update time_point for the next scheduled single acquisition (if any)
        self.time_point = self.time_point + 1

        if self.time_point >= self.Nt:
            print('Multipoint acquisition finished')
            if self.acquisitionTimer.isActive():
            	self.acquisitionTimer.stop()
            self.acquisitionFinished.emit()

        self.single_acquisition_in_progress = False

class TrackingController(QObject):
    def __init__(self,microcontroller,navigationController):
        QObject.__init__(self)
        self.microcontroller = microcontroller
        self.navigationController = navigationController
        self.tracker_xy = tracking.Tracker_XY()
        self.tracker_z = tracking.Tracker_Z()
        self.pid_controller_x = tracking.PID_Controller()
        self.pid_controller_y = tracking.PID_Controller()
        self.pid_controller_z = tracking.PID_Controller()
        self.tracking_frame_counter = 0

    def on_new_frame(self,image,frame_ID,timestamp):
        # initialize the tracker when a new track is started
        if self.tracking_frame_counter == 0:
            # initialize the tracker
            # initialize the PID controller
            pass

        # crop the image, resize the image 
        # [to fill]

        # get the location
        [x,y] = self.tracker_xy.track(image)
        z = self.track_z.track(image)

        # get motion commands
        dx = self.pid_controller_x.get_actuation(x)
        dy = self.pid_controller_y.get_actuation(y)
        dz = self.pid_controller_z.get_actuation(z)

        # read current location from the microcontroller
        current_stage_position = self.microcontroller.read_received_packet()

        # save the coordinate information (possibly enqueue image for saving here to if a separate ImageSaver object is being used) before the next movement
        # [to fill]

        # generate motion commands
        motion_commands = self.generate_motion_commands(self,dx,dy,dz)

        # send motion commands
        self.microcontroller.send_command(motion_commands)

    def start_a_new_track(self):
        self.tracking_frame_counter = 0

# from gravity machine
class ImageDisplayWindow(QMainWindow):

    def __init__(self, window_title=''):
        super().__init__()
        self.setWindowTitle(window_title)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.widget = QWidget()

        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.view = self.graphics_widget.addViewBox()
        
        ## lock the aspect ratio so pixels are always square
        self.graphics_widget.view.setAspectLocked(True)
        
        ## Create image item
        self.graphics_widget.img = pg.ImageItem(border='w')
        self.graphics_widget.view.addItem(self.graphics_widget.img)

        layout = QGridLayout()
        layout.addWidget(self.graphics_widget, 0, 0) 
        self.widget.setLayout(layout)
        self.setCentralWidget(self.widget)

        # set window size
        desktopWidget = QDesktopWidget();
        width = min(desktopWidget.height()*0.9,1000) #@@@TO MOVE@@@#
        height = width
        self.setFixedSize(width,height)

    def display_image(self,image):
        self.graphics_widget.img.setImage(image,autoLevels=False)
        # print('display image')
