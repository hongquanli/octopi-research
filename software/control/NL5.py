import control.RCM_API
import json

class NL5:
    
    def __init__(self):

        self.rcm = RCM_API.RCM_API()
        self.rcm.initialize_device(simulated=False)
        self.load_settings()

    def set_scan_amplitude(self,amplitude):
        self.scan_amplitude = amplitude
        self.rcm.set_float_parameter(self.rcm.AMPLITUDE_X,amplitude)

    def set_offset_x(self,offset_x):
        self.offset_x = offset_x
        self.rcm.set_float_parameter(self.rcm.OFFSET_SCAN_X,offset_x)

    def start_acquisition(self):
        ret = self.rcm.start_acquisition()

    def start_continuous_acquisition(self):
        self.rcm.start_acquisition()

    def stop_continuous_acquisition(self):
        self.rcm.stop_continuous_acquisition()

    def set_bypass(self, enabled):
        if enabled:
            self.rcm.set_bypass(1)
        else:
            self.rcm.set_bypass(0)

    def set_active_channel(self, channel):
        self.active_channel = channel
        for i in range(1, 5):
            self.rcm.set_integer_parameter(getattr(self.rcm, f'LASER_{i}_SELECTED'), 1 if i == channel else 0)

    def set_laser_power(self,channel,power):
        self.rcm.set_integer_parameter(getattr(self.rcm,f'LASER_{channel}_POWER'),power)

    def set_bypass_offset(self, offset):
        self.bypass_offset = offset
        self.rcm.set_float_parameter(self.rcm.BYPASS_OFFSET,offset)

    def set_line_speed(self,speed,save_setting=False):
        self.line_speed = speed
        self.rcm.set_integer_parameter(self.rcm.LINE_FREQUENCY,speed) # speed in mrad/s
        if save_setting:
            self.save_settings()

    def set_fov_x(self,fov_x):
        self.fov_x = fov_x
        self.rcm.set_integer_parameter(self.rcm.FIELD_OF_VIEW_X,fov_x)
        self.save_settings()

    def set_exposure_delay(self,exposure_delay_ms):
        self.exposure_delay_ms = exposure_delay_ms
        self.rcm.set_integer_parameter(self.rcm.EXPOSURE_DELAY,exposure_delay_ms)

    def load_settings(self):
        try:
            with open('NL5_settings.json', 'r') as file:
                settings = json.load(file)
                self.scan_amplitude = settings.get("scan_amplitude", 70.0)
                self.offset_x = settings.get("offset_x", 0.0)
                self.bypass_offset = settings.get("bypass_offset", 0.0)
                self.fov_x = settings.get("fov_x", 2048)
                self.exposure_delay_ms = settings.get("exposure_delay_ms", 30)
                self.line_speed = settings.get("line_speed", 3000)

        except FileNotFoundError:
            self.scan_amplitude = 70.0
            self.offset_x = 0.0
            self.bypass_offset = 0.0
            self.exposure_delay_ms = 30
            self.line_speed = 3000
            self.fov_x = 2048
    
    def save_settings(self):
        settings = {
            "scan_amplitude": self.scan_amplitude,
            "offset_x": self.offset_x,
            "bypass_offset": self.bypass_offset,
            "fov_x": self.fov_x,
            "exposure_delay_ms": self.exposure_delay_ms,
            "line_speed": self.line_speed
        }
        with open('NL5_settings.json', 'w') as file:
            json.dump(settings, file)


class NL5_Simulation:

    def __init__(self):
        self.load_settings()

    def set_scan_amplitude(self,amplitude):
        self.scan_amplitude = amplitude
        pass

    def set_offset_x(self,offset_x):
        self.offset_x = offset_x
        pass

    def start_acquisition(self):
        pass

    def start_continuous_acquisition(self):
        pass

    def stop_continuous_acquisition(self):
        pass

    def set_bypass(self, enabled):
        pass

    def set_active_channel(self, channel):
        pass

    def set_laser_power(self,channel,power):
        pass

    def set_bypass_offset(self, offset):
        self.bypass_offset = offset
        pass

    def set_line_speed(self,speed, save_setting = False):
        self.line_speed = speed
        if save_setting:
            self.save_settings()

    def set_fov_x(self,fov_x):
        self.fov_x = fov_x
        self.save_settings()

    def set_exposure_delay(self,exposure_delay_ms):
        self.exposure_delay_ms = exposure_delay_ms
        pass

    def load_settings(self):
        try:
            with open('NL5_settings.json', 'r') as file:
                settings = json.load(file)
                self.scan_amplitude = settings.get("scan_amplitude", 70.0)
                self.offset_x = settings.get("offset_x", 0.0)
                self.bypass_offset = settings.get("bypass_offset", 0.0)
                self.fov_x = settings.get("fov_x", 2048)
                self.exposure_delay_ms = settings.get("exposure_delay_ms", 30)
                self.line_speed = settings.get("line_speed", 3000)

        except FileNotFoundError:
            self.scan_amplitude = 70.0
            self.offset_x = 0.0
            self.bypass_offset = 0.0
            self.exposure_delay_ms = 30
            self.line_speed = 3000
            self.fov_x = 2048
    
    def save_settings(self):
        settings = {
            "scan_amplitude": self.scan_amplitude,
            "offset_x": self.offset_x,
            "bypass_offset": self.bypass_offset,
            "fov_x": self.fov_x,
            "exposure_delay_ms": self.exposure_delay_ms,
            "line_speed": self.line_speed
        }
        with open('NL5_settings.json', 'w') as file:
            json.dump(settings, file)