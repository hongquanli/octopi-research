import serial
import time
import re
import threading

class PriorStage():
    def __init__(self, sn, baudrate=115200, timeout=0.1, parent=None):
        port = [p.device for p in serial.tools.list_ports.comports() if sn == p.serial_number]
        self.serial = serial.Serial(port[0], baudrate=baudrate, timeout=timeout)
        self.current_baudrate = baudrate

        # Position information
        self.x_pos = 0
        self.y_pos = 0
        self.z_pos = 0  # Always 0 for Prior stage
        self.theta_pos = 0  # Always 0 for Prior stage

        # Button and switch state
        self.button_and_switch_state = 0
        self.joystick_button_pressed = 0
        self.signal_joystick_button_pressed_event = False
        self.switch_state = 0
        self.joystick_enabled = False

        # Prior-specific properties
        self.stage_microsteps_per_mm = 100000   # Stage property
        self.user_unit = None
        self.stage_model = None
        self.stage_limits = None
        self.resolution = 0.1
        self.x_direction = 1    # 1 or -1
        self.y_direction = 1    # 1 or -1
        self.speed = 200    # Default value
        self.acceleration = 500  # Default value

        # Position updating callback
        self.pos_callback_external = None
        self.serial_lock = threading.Lock()
        self.position_updating_event = threading.Event()
        self.position_updating_thread = threading.Thread(target=self.return_position_info, daemon=True)

        self.set_baudrate(baudrate)

        self.initialize()
        self.position_updating_thread.start()

    def set_baudrate(self, baud):
        allowed_baudrates = {9600: '96', 19200: '19', 38400: '38', 115200: '115'}
        if baud not in allowed_baudrates:
            print('Baudrate not allowed. Setting baudrate to 9600')
            baud_command = "BAUD 96"
        else:
            baud_command = "BAUD " + allowed_baudrates[baud]
        print(baud_command)

        for bd in allowed_baudrates:
            self.serial.baudrate = bd
            self.serial.write(b'\r')
            time.sleep(0.1)
            self.serial.flushInput()

            self.send_command(baud_command)

            self.serial.baudrate = baud
        
            try:
                test_response = self.send_command("$")  # Send a simple query command
                if not test_response:
                    raise Exception("No response received after changing baud rate")
                else:
                    self.current_baudrate = baud
                    print(f"Baud rate successfully changed to {baud}")
                    return
            except Exception as e:
                # If verification fails, try to revert to the original baud rate
                self.serial.baudrate = self.current_baudrate
                print(f"Serial baudrate: {bd}")
                print(f"Failed to verify communication at new baud rate: {e}")

        raise Exception("Failed to set baudrate.")
        
    def initialize(self):
        self.send_command("COMP 0")  # Set to standard mode
        self.send_command("BLSH 1")  # Enable backlash correction
        self.send_command("RES,S," + str(self.resolution))  # Set resolution
        response = self.send_command("H 0")     # Joystick enabled
        self.joystick_enabled = True
        self.user_unit = self.stage_microsteps_per_mm * self.resolution
        self.get_stage_info()
        self.set_acceleration(self.acceleration)
        self.set_max_speed(self.speed)

    def send_command(self, command):
        with self.serial_lock:
            self.serial.write(f"{command}\r".encode())
            response = self.serial.readline().decode().strip()
            if response.startswith('E'):
                raise Exception(f"Error from controller: {response}")
            return response

    def get_stage_info(self):
        stage_info = self.send_command("STAGE")
        self.stage_model = re.search(r'STAGE\s*=\s*(\S+)', stage_info).group(1)
        print("Stage model: ", self.stage_model)

    def mm_to_steps(self, mm):
        return int(mm * self.user_unit)

    def steps_to_mm(self, steps):
        return steps / self.user_unit

    def set_max_speed(self, speed=1000):
        """Set the maximum speed of the stage. Range is 1 to 1000."""
        if 1 <= speed <= 1000:
            response = self.send_command(f"SMS {speed}")
            print(f"Maximum speed set to {speed}. Response: {response}")
        else:
            raise ValueError("Speed must be between 1 and 1000")

    def get_max_speed(self):
        """Get the current maximum speed setting."""
        response = self.send_command("SMS")
        print(f"Current maximum speed: {response}")
        return int(response)

    def set_acceleration(self, acceleration=1000):
        """Set the acceleration of the stage. Range is 1 to 1000."""
        if 1 <= acceleration <= 1000:
            response = self.send_command(f"SAS {acceleration}")
            self.acceleration = acceleration
            print(f"Acceleration set to {acceleration}. Response: {response}")
        else:
            raise ValueError("Acceleration must be between 1 and 1000")

    def get_acceleration(self):
        """Get the current acceleration setting."""
        response = self.send_command("SAS")
        print(f"Current acceleration: {response}")
        return int(response)

    def set_callback(self, function):
        self.pos_callback_external = function

    def return_position_info(self):
        while not self.position_updating_event.is_set():
            if self.pos_callback_external is not None:
                self.pos_callback_external(self)

    def home_xy(self):
        """Home the XY stage."""
        self.send_command("M")  # 'M' command moves stage to (0,0,0)
        self.wait_for_stop()
        self.x_pos = 0
        self.y_pos = 0
        print('finished homing')

    def home_x(self):
        self.move_relative(-self.x_pos, 0)
        self.x_pos = 0

    def home_y(self):
        self.move_relative(0, -self.y_pos)
        self.y_pos = 0

    def zero_xy(self):
        self.send_command("Z")
        self.x_pos = 0
        self.y_pos = 0

    def zero_x(self):
        self.set_pos(0, self.y_pos)

    def zero_y(self):
        self.set_pos(self.x_pos, 0)

    def get_pos(self):
        response = self.send_command("P")
        x, y, z = map(int, response.split(','))
        self.x_pos = x
        self.y_pos = y
        return x, y, 0, 0  # Z and theta are 0

    def set_pos(self, x, y, z=0):
        self.send_command(f"P {x},{y},{z}")
        self.x_pos = x
        self.y_pos = y

    def move_relative_mm(self, x_mm, y_mm):
        x_steps = self.mm_to_steps(x_mm)
        y_steps = self.mm_to_steps(y_mm)
        return self.move_relative(x_steps, y_steps)

    def move_absolute_mm(self, x_mm, y_mm):
        x_steps = self.mm_to_steps(x_mm)
        y_steps = self.mm_to_steps(y_mm)
        return self.move_absolute(x_steps, y_steps)

    def move_absolute_x_mm(self, x_mm):
        x_steps = self.mm_to_steps(x_mm)
        return self.move_absolute_x(x_steps)

    def move_absolute_y_mm(self, y_mm):
        y_steps = self.mm_to_steps(y_mm)
        return self.move_absolute_y(y_steps)

    def move_relative(self, x, y, blocking=True):
        x = x * self.x_direction
        y = y * self.y_direction
        self.send_command(f"GR {x},{y}")
        if blocking:
            self.wait_for_stop()
        else:
            threading.Thread(target=self.wait_for_stop, daemon=True).start()

    def move_absolute(self, x, y, blocking=True):
        x = x * self.x_direction
        y = y * self.y_direction
        self.send_command(f"G {x},{y}")
        if blocking:
            self.wait_for_stop()
        else:
            threading.Thread(target=self.wait_for_stop, daemon=True).start()

    def move_absolute_x(self, x, blocking=True):
        x = x * self.x_direction
        self.send_command(f"GX {x}")
        if blocking:
            self.wait_for_stop()
        else:
            threading.Thread(target=self.wait_for_stop, daemon=True).start()

    def move_absolute_y(self, y, blocking=True):
        y = y * self.y_direction
        self.send_command(f"GY {y}")
        if blocking:
            self.wait_for_stop()
        else:
            threading.Thread(target=self.wait_for_stop, daemon=True).start()

    def enable_joystick(self):
        self.send_command("J")
        self.joystick_enabled = True

    def disable_joystick(self):
        self.send_command("H")
        self.joystick_enabled = False

    def wait_for_stop(self):
        while True:
            status = int(self.send_command("$,S"))
            if status == 0:
                self.get_pos()
                print('xy position: ', self.x_pos, self.y_pos)
                break
            time.sleep(0.05)

    def stop(self):
        return self.send_command("K")

    def close(self):
        self.disable_joystick()
        self.position_updating_event.set()
        self.position_updating_thread.join()
        self.serial.close()
        print('Stage closed')

    def home_z(self):
        pass

    def zero_z(self):
        pass

