# app specific libraries
import time
import squid_control.control.widgets as widgets
import squid_control.control.camera as camera
import squid_control.control.core as core
import squid_control.control.microcontroller as microcontroller
from squid_control.control._def import *

microcontroller = microcontroller.Microcontroller(version=CONTROLLER_VERSION)
navigationController = core.NavigationController(microcontroller)

'''
# home y
navigationController.home_y()
t0 = time.time()
while microcontroller.is_busy():
	time.sleep(0.005)
	if time.time() - t0 > 10:
		print('y homing timeout, the program will exit')
		exit()

# home x
navigationController.home_x()
t0 = time.time()
while microcontroller.is_busy():
	time.sleep(0.005)
	if time.time() - t0 > 10:
		print('x homing timeout, the program will exit')
		exit()
'''

# move x and y by 5 mm each
navigationController.move_x(5)
while microcontroller.is_busy():
	time.sleep(0.005)
navigationController.move_y(5)
while microcontroller.is_busy():
	time.sleep(0.005)

# move x and y by -5 mm each
navigationController.move_x(-5)
while microcontroller.is_busy():
	time.sleep(0.005)
navigationController.move_y(-5)
while microcontroller.is_busy():
	time.sleep(0.005)