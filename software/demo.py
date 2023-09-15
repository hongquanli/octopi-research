import control.core as core
import control.microcontroller as microcontroller
from control._def import *
import time

N_REPETITIONS = 100

def print_positon_stats(t0):
        xp, yp, zp, _ = microcontroller.get_pos()
        xe, ye, ze    = microcontroller.get_enc()
        print(f"{time.time()-t0}, {xp}, {yp}, {zp}, {xe}, {ye}, {ze}")
        
microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)
navigationController = core.NavigationController(microcontroller)

# configure PID
microcontroller.configure_stage_pid(0, transitions_per_revolution=3000, flip_direction=True)
microcontroller.configure_stage_pid(1, transitions_per_revolution=3000, flip_direction=True)
microcontroller.configure_stage_pid(2, transitions_per_revolution=3000, flip_direction=True)
# microcontroller.turn_on_stage_pid(0)
# microcontroller.turn_on_stage_pid(1)

#microcontroller.turn_off_stage_pid(2)
microcontroller.turn_on_stage_pid(0)
microcontroller.turn_on_stage_pid(1)
microcontroller.turn_on_stage_pid(2)
displacement = 1

t0 = time.time()
while (time.time() - t0) < 0:
        print_positon_stats(t0)
        time.sleep(0.1)

t0 = time.time()
navigationController.move_z(displacement)
while microcontroller.is_busy():
        print_positon_stats(t0)
        time.sleep(0.01)
        
time.sleep(0.50)

t0 = time.time()
navigationController.move_z(-displacement)
while microcontroller.is_busy():
        print_positon_stats(t0)
        time.sleep(0.01)
        
# repetition testing

t0 = time.time()
print("Start position: ")
print_positon_stats(t0)
for _ in range(N_REPETITIONS):
        navigationController.move_z(displacement)
        while microcontroller.is_busy():
                time.sleep(0.01)
        print_positon_stats(t0)
        navigationController.move_z(-displacement)
        while microcontroller.is_busy():
                time.sleep(0.01)
        print_positon_stats(t0)
print("End position: ")
print_positon_stats(t0)
