# qt libraries
from qtpy.QtCore import QObject, QThread, Signal # type: ignore
from qtpy.QtWidgets import QApplication

import control.utils as utils
from control._def import *

import time
import numpy as np

from typing import Optional, List, Union, Tuple

import control.camera as camera
from control.core import NavigationController, LiveController
from control.microcontroller import Microcontroller

class AutofocusWorker(QObject):

    finished = Signal()
    image_to_display = Signal(np.ndarray)
    # signal_current_configuration = Signal(Configuration)

    def __init__(self,autofocusController):
        QObject.__init__(self)
        self.autofocusController = autofocusController

        self.camera:camera.Camera = self.autofocusController.camera
        self.microcontroller:Microcontroller = self.autofocusController.navigationController.microcontroller
        self.navigationController = self.autofocusController.navigationController
        self.liveController = self.autofocusController.liveController

        self.N = self.autofocusController.N
        self.deltaZ = self.autofocusController.deltaZ
        self.deltaZ_usteps = self.autofocusController.deltaZ_usteps
        
        self.crop_width = self.autofocusController.crop_width
        self.crop_height = self.autofocusController.crop_height

    def run(self):
        self.run_autofocus()
        self.finished.emit()

    def run_autofocus(self):
        # @@@ to add: increase gain, decrease exposure time
        # @@@ can move the execution into a thread - done 08/21/2021
        focus_measure_vs_z:List[float] = [0]*self.N
        focus_measure_max:float = 0

        z_af_offset_usteps = self.deltaZ_usteps*round(self.N/2)
        # self.navigationController.move_z_usteps(-z_af_offset_usteps) # combine with the back and forth maneuver below
        # self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        # can be moved to the firmware
        _usteps_to_clear_backlash = max(160,20*self.navigationController.z_microstepping)
        self.navigationController.move_z_usteps(-_usteps_to_clear_backlash-z_af_offset_usteps,wait_for_completion={})
        self.navigationController.move_z_usteps(_usteps_to_clear_backlash,wait_for_completion={})

        steps_moved = 0
        for i in range(self.N):
            self.navigationController.move_z_usteps(self.deltaZ_usteps,wait_for_completion={})
            steps_moved = steps_moved + 1

            # trigger acquisition (including turning on the illumination)
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                self.liveController.turn_on_illumination()
                self.camera.send_trigger()

            elif self.liveController.trigger_mode == TriggerMode.HARDWARE:
                self.microcontroller.send_hardware_trigger(control_illumination=True,illumination_on_time_us=self.camera.exposure_time*1000)

            # read camera frame
            image = self.camera.read_frame()

            # turn off the illumination if using software trigger
            if self.liveController.trigger_mode == TriggerMode.SOFTWARE:
                self.liveController.turn_off_illumination()

            image = utils.crop_image(image,self.crop_width,self.crop_height)
            self.image_to_display.emit(image)

            QApplication.processEvents()

            focus_measure = utils.calculate_focus_measure(image,MUTABLE_MACHINE_CONFIG.FOCUS_MEASURE_OPERATOR)
            focus_measure_vs_z[i] = focus_measure
            focus_measure_max = max(focus_measure, focus_measure_max)
            if focus_measure < focus_measure_max*MACHINE_CONFIG.AF.STOP_THRESHOLD:
                break

        # determine the in-focus position
        idx_in_focus = focus_measure_vs_z.index(max(focus_measure_vs_z))

        # move to the starting location
        # self.navigationController.move_z_usteps(-steps_moved*self.deltaZ_usteps) # combine with the back and forth maneuver below
        # self.wait_till_operation_is_completed()

        # maneuver for achiving uniform step size and repeatability when using open-loop control
        self.navigationController.move_z_usteps(-_usteps_to_clear_backlash-steps_moved*self.deltaZ_usteps,wait_for_completion={})
        self.navigationController.move_z_usteps(_usteps_to_clear_backlash+(idx_in_focus+1)*self.deltaZ_usteps,wait_for_completion={})

        # move to the calculated in-focus position
        # self.navigationController.move_z_usteps(idx_in_focus*self.deltaZ_usteps)
        # self.wait_till_operation_is_completed() # combine with the movement above

        if idx_in_focus == 0:
            print('moved to the bottom end of the AF range (this is not good)')

        elif idx_in_focus == self.N-1:
            print('moved to the top end of the AF range (this is not good)')

class AutoFocusController(QObject):
    """
    runs autofocus procedure on request\n
    can be configured between creation and request
    """

    z_pos = Signal(float)
    autofocusFinished = Signal()
    image_to_display = Signal(np.ndarray)

    def __init__(self,camera:camera.Camera,navigationController:NavigationController,liveController:LiveController):
        QObject.__init__(self)
        self.camera = camera
        self.navigationController = navigationController
        self.liveController = liveController
        self.N:int = 1 # arbitrary value of type
        self.deltaZ:float = 0.1 # arbitrary value of type
        self.deltaZ_usteps:int = 1 # arbitrary value of type
        self.crop_width:int = MACHINE_CONFIG.AF.CROP_WIDTH
        self.crop_height:int = MACHINE_CONFIG.AF.CROP_HEIGHT
        self.autofocus_in_progress:bool = False
        self.thread:Optional[QThread] = None

    def set_N(self,N:int):
        self.N = N

    def set_deltaZ(self,deltaZ_um:float):
        mm_per_ustep_Z = MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.navigationController.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z)
        self.deltaZ = deltaZ_um/1000
        self.deltaZ_usteps = round((deltaZ_um/1000)/mm_per_ustep_Z)

    def set_crop(self,crop_width:int,crop_height:int):
        self.crop_width = crop_width
        self.crop_height = crop_height

    def autofocus(self):
        # stop live
        if self.liveController.is_live:
            self.was_live_before_autofocus = True
            self.liveController.stop_live()
        else:
            self.was_live_before_autofocus = False

        # temporarily disable call back -> image does not go through streamHandler
        if self.camera.callback_is_enabled:
            self.callback_was_enabled_before_autofocus = True
            self.camera.disable_callback()
        else:
            self.callback_was_enabled_before_autofocus = False

        self.autofocus_in_progress = True
        self.camera.start_streaming() # work around a bug, explained in MultiPointController.run_experiment

        # create a QThread object
        if not self.thread is None and self.thread.isRunning():
            print('*** autofocus thread is still running ***')
            self.thread.terminate()
            self.thread.wait()
            print('*** autofocus threaded manually stopped ***')

        self.thread = QThread()
        # create a worker object
        self.autofocusWorker = AutofocusWorker(self)
        # move the worker to the thread
        self.autofocusWorker.moveToThread(self.thread)
        # connect signals and slots
        self.thread.started.connect(self.autofocusWorker.run)
        self.autofocusWorker.finished.connect(self._on_autofocus_completed)
        self.autofocusWorker.finished.connect(self.autofocusWorker.deleteLater)
        self.autofocusWorker.finished.connect(self.thread.quit)
        self.autofocusWorker.image_to_display.connect(self.slot_image_to_display)
        # self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.thread.quit)
        # start the thread
        self.thread.start()
        
    def _on_autofocus_completed(self):
        # re-enable callback
        if self.callback_was_enabled_before_autofocus:
            self.camera.enable_callback()
        
        # re-enable live if it's previously on
        if self.was_live_before_autofocus:
            self.liveController.start_live()

        # emit the autofocus finished signal to enable the UI
        self.autofocusFinished.emit()
        QApplication.processEvents()
        #print('autofocus finished')

        # update the state
        self.autofocus_in_progress = False

    def slot_image_to_display(self,image):
        self.image_to_display.emit(image)

    def wait_till_autofocus_has_completed(self):
        while self.autofocus_in_progress == True:
            time.sleep(0.005)
        #print('autofocus wait has completed, exit wait')
