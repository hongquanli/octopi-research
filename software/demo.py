import control.core as core
import control.microcontroller as microcontroller
from control._def import *
import time

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
	print(microcontroller.get_enc())
	time.sleep(0.01)

navigationController.move_x(-displacement)
while microcontroller.is_busy():
        print(microcontroller.get_enc())
	time.sleep(0.01)
