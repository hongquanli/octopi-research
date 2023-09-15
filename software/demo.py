import control.core as core
import control.microcontroller as microcontroller
from control._def import *
import time

def print_positon_stats():
        xp, yp, zp, _ = microcontroller.get_pos()
        xe, ye, ze    = microcontroller.get_enc()
        print(time.time())
        print(f"X positon: {xp}")
        print(f"X encoder: {xe}")
        print(f"Y positon: {yp}")
        print(f"Y encoder: {ye}")
        print(f"Z positon: {zp}")
        print(f"Z encoder: {ze}")

microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)
navigationController = core.NavigationController(microcontroller)

# configure PID
microcontroller.configure_stage_pid(2, transitions_per_revolution=3000, flip_direction=True)

# microcontroller.turn_on_stage_pid(0)
# microcontroller.turn_on_stage_pid(1)

microcontroller.turn_off_stage_pid(2)
displacement = 5

navigationController.move_x(displacement)
while microcontroller.is_busy():
	print_positon_stats()
	time.sleep(0.001)

navigationController.move_x(-displacement)
while microcontroller.is_busy():
        print_positon_stats()
	time.sleep(0.001)
