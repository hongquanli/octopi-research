import os
import time

from control._def import *

class SquidFilterWheelWrapper:

    def __init__(self, navigationController):

        if navigationController is None:
            raise Exception("Error, navigationController is need by the SquidFilterWheelWrapper")

        # emission filter position
        self.w_pos_index = 0

        self.navigationController = navigationController

    def homing(self):
        # make sure the start homing position is not at homing position  
        starttime = time.time() 
        self.navigationController.home_w()
        # for homing action, need much more timeout time
        self.navigationController.wait_till_operation_is_completed(15)
        # judge whether the current position is at homing position or not
        if time.time() - starttime > 0.02:
            # move offset, could be modified later
            self.navigationController.move_w(SQUID_FILTERWHEEL_OFFSET)

        self.w_pos_index = 0
        
    def next_position(self):
        if self.w_pos_index < SQUID_FILTERWHEEL_MAX_INDEX:
            self.navigationController.move_w(SCREW_PITCH_W_MM / (SQUID_FILTERWHEEL_MAX_INDEX + 1))
            self.navigationController.wait_till_operation_is_completed()
            self.w_pos_index += 1 

    def previous_position(self):
        if self.w_pos_index > SQUID_FILTERWHEEL_MIN_INDEX:
            self.navigationController.move_w(-(SCREW_PITCH_W_MM / (SQUID_FILTERWHEEL_MAX_INDEX + 1)))
            self.navigationController.wait_till_operation_is_completed()
            self.w_pos_index -= 1

    def set_emission(self, pos):
        if pos in range(SQUID_FILTERWHEEL_MIN_INDEX, SQUID_FILTERWHEEL_MAX_INDEX + 1): 
            if pos != self.w_pos_index:
                self.navigationController.move_w((pos - self.w_pos_index) * SCREW_PITCH_W_MM / (SQUID_FILTERWHEEL_MAX_INDEX + 1))
                self.navigationController.wait_till_operation_is_completed()
                self.w_pos_index = pos


class SquidFilterWheelWrapper_Simulation:

    def __init__(self, navigationController):
        # emission filter position
        self.w_pos_index = 0

        self.navigationController = navigationController

    def homing(self):
        pass

    def next_position(self):
        pass

    def previous_position(self):
        pass

    def set_emission(self, pos):
        pass
