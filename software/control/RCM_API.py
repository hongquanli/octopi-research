import ctypes
from ctypes import c_int, c_char_p, create_string_buffer
from pycparser import c_parser, c_ast, parse_file
import re
import sys

C_TO_CTYPES = {
    'void': None,
    'int': ctypes.c_int,
    'char': ctypes.c_char,
    'char*': ctypes.c_char_p,
    'bool': ctypes.c_bool,
    'double': ctypes.c_double,
    # Add more mappings as needed
}

def extract_macros_from_header(file_path):
    macros = {}
    with open(file_path, 'r') as file:
        for line in file:
            # Ignore lines containing keywords like "_declspec"
            if "_declspec" in line or "_BUILD_DLL_" in line:
                continue
            match = re.match(r'#define\s+(\w+)\s+(\d+)', line)
            if match:
                name, value = match.groups()
                macros[name] = int(value)
    return macros


def extract_functions_from_header(file_path):
    functions = []
    with open(file_path, 'r') as file:
        content = file.read()
        # Match function prototypes
        matches = re.findall(r'\b(\w[\w\s\*]+)\s+(\w+)\s*\(([^)]*)\)\s*;', content)
        for ret_type, func_name, params in matches:
            param_list = []
            if params.strip():  # Check if there are parameters
                for param in params.split(','):
                    param = param.strip()
                    param_type = ' '.join(param.split()[:-1])
                    param_list.append(C_TO_CTYPES.get(param_type.strip(), ctypes.c_void_p))
            functions.append({
                'name': func_name,
                # 'return_type': C_TO_CTYPES.get(ret_type.strip(), ctypes.c_void_p),
                'return_type': c_int,
                'arg_types': param_list
            })
    return functions


class RCM_API:
    def __init__(self):

        # Load the header
        macros = extract_macros_from_header('./RCM_API.h')
        functions = extract_functions_from_header('./RCM_API.h')

        # Load the DLL
        self.rcm_api = ctypes.CDLL('.\\RCM_API.dll')
        
        # Set constants from macros
        for name, value in macros.items():
            setattr(self, name, int(value))
            # print(name + ' ' + str(value))
        self.ERR_OK = -1

        # Dynamically define functions from the header file
        for func in functions:
            # print(func)
            func_name = func['name']
            ret_type = func['return_type']
            arg_types = func['arg_types']
            function = getattr(self.rcm_api, func_name)
            function.restype = ret_type
            function.argtypes = arg_types
            setattr(self, func_name, function)

    def get_string_parameter(self, param: int):
        buffer = create_string_buffer(100)
        result = self.getStringParameter(param, buffer)
        if result == self.ERR_OK:
            return buffer.value.decode()
        else:
            return None

    def set_integer_parameter(self, param: int, value: int):
        return self.setIntegerParameter(param, value)

    def set_float_parameter(self, param: int, value: float):
        return self.setFloatParameter(param, value)

    def initialize_device(self, simulated: bool):
        return self.initializeDevice(simulated)

    def get_device_type(self):
        return self.getDeviceType()

    def start_acquisition(self):
        return self.startAcquisition()

    def set_bypass(self, mode: int):
        return self.setBypass(mode)

    def start_continuous_acquisition(self):
        return self.startContinuousAcquisition()

    def stop_continuous_acquisition(self):
        return self.stopContinuousAcquisition()

    def get_full_error(self):
        err_code = c_int()
        buffer = create_string_buffer(100)
        result = self.getFullError(ctypes.byref(err_code), buffer)
        if result == self.ERR_OK:
            return err_code.value, buffer.value.decode()
        else:
            return None