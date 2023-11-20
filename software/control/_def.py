import os
import glob
import numpy as np
from pathlib import Path
from configparser import ConfigParser
import json

def conf_attribute_reader(string_value):
    """
    :brief: standardized way for reading config entries
    that are strings, in priority order
    dict/list (via json) -> int -> float -> string
    REMEMBER TO ENCLOSE PROPERTY NAMES IN LISTS/DICTS IN
    DOUBLE QUOTES
    """
    actualvalue = str(string_value).strip()
    try:
        if str(actualvalue) == "True" or str(actualvalue) == "true":
            return True
        if str(actualvalue) == "False" or str(actualvalue) == "false":
            return False
    except:
        pass
    try:
        actualvalue = json.loads(actualvalue)
    except:
        try:
            actualvalue = int(str(actualvalue))
        except:
            try:
                actualvalue = float(actualvalue)
            except:
                actualvalue = str(actualvalue)
    return actualvalue


def populate_class_from_dict(myclass, options):
    """
    :brief: helper function to establish a compatibility
        layer between new way of storing config and current
        way of accessing it. assumes all class attributes are
        all-uppercase, and pattern-matches attributes in
        priority order dict/list (json) -> -> int -> float-> string
    REMEMBER TO ENCLOSE PROPERTY NAMES IN LISTS IN DOUBLE QUOTES
    """
    for key, value in options:
        if key.startswith('_') and key.endswith('options'):
            continue
        actualkey = key.upper()
        actualvalue = conf_attribute_reader(value)
        setattr(myclass, actualkey, actualvalue)

class TriggerMode:
    SOFTWARE = 'Software Trigger'
    HARDWARE = 'Hardware Trigger'
    CONTINUOUS = 'Continuous Acqusition'

class Acquisition:
    CROP_WIDTH = 3000
    CROP_HEIGHT = 3000
    NUMBER_OF_FOVS_PER_AF = 3
    IMAGE_FORMAT = 'bmp'
    IMAGE_DISPLAY_SCALING_FACTOR = 0.3
    DX = 0.9
    DY = 0.9
    DZ = 1.5

class PosUpdate:
    INTERVAL_MS = 25

class MicrocontrollerDef:
    MSG_LENGTH = 24
    CMD_LENGTH = 8
    N_BYTES_POS = 4

class Microcontroller2Def:
    MSG_LENGTH = 4
    CMD_LENGTH = 8
    N_BYTES_POS = 4

USE_SEPARATE_MCU_FOR_DAC = False

class MCU_PINS:
    PWM1 = 5
    PWM2 = 4
    PWM3 = 22
    PWM4 = 3
    PWM5 = 23
    PWM6 = 2
    PWM7 = 1
    PWM9 = 6
    PWM10 = 7
    PWM11 = 8
    PWM12 = 9
    PWM13 = 10
    PWM14 = 15
    PWM15 = 24
    PWM16 = 25
    AF_LASER = 15

class CMD_SET:
    MOVE_X = 0
    MOVE_Y = 1
    MOVE_Z = 2
    MOVE_THETA = 3
    HOME_OR_ZERO = 5
    TURN_ON_ILLUMINATION = 10
    TURN_OFF_ILLUMINATION = 11
    SET_ILLUMINATION = 12
    SET_ILLUMINATION_LED_MATRIX = 13
    ACK_JOYSTICK_BUTTON_PRESSED = 14
    ANALOG_WRITE_ONBOARD_DAC = 15
    MOVETO_X = 6
    MOVETO_Y = 7
    MOVETO_Z = 8
    SET_LIM = 9
    SET_LIM_SWITCH_POLARITY = 20
    CONFIGURE_STEPPER_DRIVER = 21
    SET_MAX_VELOCITY_ACCELERATION = 22
    SET_LEAD_SCREW_PITCH = 23
    SET_OFFSET_VELOCITY = 24
    CONFIGURE_STAGE_PID = 25
    ENABLE_STAGE_PID = 26
    DISABLE_STAGE_PID = 27
    SEND_HARDWARE_TRIGGER = 30
    SET_STROBE_DELAY = 31
    SET_PIN_LEVEL = 41
    INITIALIZE = 254
    RESET = 255

class CMD_SET2:
    ANALOG_WRITE_DAC8050X = 0
    SET_CAMERA_TRIGGER_FREQUENCY = 1
    START_CAMERA_TRIGGERING = 2
    STOP_CAMERA_TRIGGERING = 3

BIT_POS_JOYSTICK_BUTTON = 0
BIT_POS_SWITCH = 1

class HOME_OR_ZERO:
    HOME_NEGATIVE = 1 # motor moves along the negative direction (MCU coordinates)
    HOME_POSITIVE = 0 # motor moves along the negative direction (MCU coordinates)
    ZERO = 2

class AXIS:
    X = 0
    Y = 1
    Z = 2
    THETA = 3
    XY = 4

class LIMIT_CODE:
    X_POSITIVE = 0
    X_NEGATIVE = 1
    Y_POSITIVE = 2
    Y_NEGATIVE = 3
    Z_POSITIVE = 4
    Z_NEGATIVE = 5

class LIMIT_SWITCH_POLARITY:
    ACTIVE_LOW = 0
    ACTIVE_HIGH = 1
    DISABLED = 2
    X_HOME= 1
    Y_HOME= 1
    Z_HOME= 2


class ILLUMINATION_CODE:
    ILLUMINATION_SOURCE_LED_ARRAY_FULL = 0;
    ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF = 1
    ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF = 2
    ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR = 3
    ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA = 4;
    ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT = 5;
    ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT = 6;
    ILLUMINATION_SOURCE_LED_EXTERNAL_FET = 20
    ILLUMINATION_SOURCE_405NM = 11
    ILLUMINATION_SOURCE_488NM = 12
    ILLUMINATION_SOURCE_638NM = 13
    ILLUMINATION_SOURCE_561NM = 14
    ILLUMINATION_SOURCE_730NM = 15

class VOLUMETRIC_IMAGING:
    NUM_PLANES_PER_VOLUME = 20

class CMD_EXECUTION_STATUS:
    COMPLETED_WITHOUT_ERRORS = 0
    IN_PROGRESS = 1
    CMD_CHECKSUM_ERROR = 2
    CMD_INVALID = 3
    CMD_EXECUTION_ERROR = 4
    ERROR_CODE_EMPTYING_THE_FLUDIIC_LINE_FAILED = 100


###########################################################
#### machine specific configurations - to be overridden ###
###########################################################
ROTATE_IMAGE_ANGLE = None
FLIP_IMAGE = None # 'Horizontal', 'Vertical', 'Both'

CAMERA_REVERSE_X = False
CAMERA_REVERSE_Y = False

DEFAULT_TRIGGER_MODE = TriggerMode.SOFTWARE

# note: XY are the in-plane axes, Z is the focus axis

# change the following so that "backward" is "backward" - towards the single sided hall effect sensor
STAGE_MOVEMENT_SIGN_X = -1
STAGE_MOVEMENT_SIGN_Y = 1
STAGE_MOVEMENT_SIGN_Z = -1
STAGE_MOVEMENT_SIGN_THETA = 1

STAGE_POS_SIGN_X = STAGE_MOVEMENT_SIGN_X
STAGE_POS_SIGN_Y = STAGE_MOVEMENT_SIGN_Y
STAGE_POS_SIGN_Z = STAGE_MOVEMENT_SIGN_Z
STAGE_POS_SIGN_THETA = STAGE_MOVEMENT_SIGN_THETA

TRACKING_MOVEMENT_SIGN_X = 1
TRACKING_MOVEMENT_SIGN_Y = 1
TRACKING_MOVEMENT_SIGN_Z = 1
TRACKING_MOVEMENT_SIGN_THETA = 1

USE_ENCODER_X = False
USE_ENCODER_Y = False
USE_ENCODER_Z = False
USE_ENCODER_THETA = False

ENCODER_POS_SIGN_X = 1
ENCODER_POS_SIGN_Y = 1
ENCODER_POS_SIGN_Z = 1
ENCODER_POS_SIGN_THETA = 1

ENCODER_STEP_SIZE_X_MM = 100e-6
ENCODER_STEP_SIZE_Y_MM = 100e-6
ENCODER_STEP_SIZE_Z_MM = 100e-6
ENCODER_STEP_SIZE_THETA = 1

FULLSTEPS_PER_REV_X = 200
FULLSTEPS_PER_REV_Y = 200
FULLSTEPS_PER_REV_Z = 200
FULLSTEPS_PER_REV_THETA = 200

# beginning of actuator specific configurations

SCREW_PITCH_X_MM = 1
SCREW_PITCH_Y_MM = 1
SCREW_PITCH_Z_MM = 0.012*25.4

MICROSTEPPING_DEFAULT_X = 8
MICROSTEPPING_DEFAULT_Y = 8
MICROSTEPPING_DEFAULT_Z = 8
MICROSTEPPING_DEFAULT_THETA = 8 # not used, to be removed

X_MOTOR_RMS_CURRENT_mA = 490
Y_MOTOR_RMS_CURRENT_mA = 490
Z_MOTOR_RMS_CURRENT_mA = 490

X_MOTOR_I_HOLD = 0.5
Y_MOTOR_I_HOLD = 0.5
Z_MOTOR_I_HOLD = 0.5

MAX_VELOCITY_X_mm = 25
MAX_VELOCITY_Y_mm = 25
MAX_VELOCITY_Z_mm = 2

MAX_ACCELERATION_X_mm = 500
MAX_ACCELERATION_Y_mm = 500
MAX_ACCELERATION_Z_mm = 20

# end of actuator specific configurations

SCAN_STABILIZATION_TIME_MS_X = 160
SCAN_STABILIZATION_TIME_MS_Y = 160
SCAN_STABILIZATION_TIME_MS_Z = 20
HOMING_ENABLED_X = True
HOMING_ENABLED_Y = True
HOMING_ENABLED_Z = False

SLEEP_TIME_S = 0.005

LED_MATRIX_R_FACTOR = 0
LED_MATRIX_G_FACTOR = 0
LED_MATRIX_B_FACTOR = 1

DEFAULT_SAVING_PATH = str(Path.home()) + "/Downloads"

DEFAULT_PIXEL_FORMAT = 'MONO12'

class PLATE_READER:
    NUMBER_OF_ROWS = 8
    NUMBER_OF_COLUMNS = 12
    ROW_SPACING_MM = 9
    COLUMN_SPACING_MM = 9
    OFFSET_COLUMN_1_MM = 20
    OFFSET_ROW_A_MM = 20

DEFAULT_DISPLAY_CROP = 100 # value ranges from 1 to 100 - image display crop size 

CAMERA_PIXEL_SIZE_UM = {'IMX290':2.9,'IMX178':2.4,'IMX226':1.85,'IMX250':3.45,'IMX252':3.45,'IMX273':3.45,'IMX264':3.45,'IMX265':3.45,'IMX571':3.76,'PYTHON300':4.8}
OBJECTIVES = {'2x':{'magnification':2, 'NA':0.10, 'tube_lens_f_mm':180}, 
                '4x':{'magnification':4, 'NA':0.13, 'tube_lens_f_mm':180}, 
                '10x':{'magnification':10, 'NA':0.25, 'tube_lens_f_mm':180}, 
                '10x (Mitutoyo)':{'magnification':10, 'NA':0.25, 'tube_lens_f_mm':200},
                '20x (Boli)':{'magnification':20, 'NA':0.4, 'tube_lens_f_mm':180}, 
                '20x (Nikon)':{'magnification':20, 'NA':0.45, 'tube_lens_f_mm':200}, 
                '40x':{'magnification':40, 'NA':0.6, 'tube_lens_f_mm':180}}
TUBE_LENS_MM = 50
CAMERA_SENSOR = 'IMX226'
DEFAULT_OBJECTIVE = '10x (Mitutoyo)'
TRACKERS = ['csrt', 'kcf', 'mil', 'tld', 'medianflow','mosse','daSiamRPN']
DEFAULT_TRACKER = 'csrt'

ENABLE_TRACKING = False
TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS = False # set to true when doing multimodal acquisition
if ENABLE_TRACKING:
    DEFAULT_DISPLAY_CROP = 100

class AF:
    STOP_THRESHOLD = 0.85
    CROP_WIDTH = 800
    CROP_HEIGHT = 800

class Tracking:
    SEARCH_AREA_RATIO = 10 #@@@ check
    CROPPED_IMG_RATIO = 10 #@@@ check
    BBOX_SCALE_FACTOR = 1.2
    DEFAULT_TRACKER = "csrt"
    INIT_METHODS = ["roi"]
    DEFAULT_INIT_METHOD = "roi"

SHOW_DAC_CONTROL = False

class SLIDE_POSITION:
    LOADING_X_MM = 30
    LOADING_Y_MM = 55
    SCANNING_X_MM = 3
    SCANNING_Y_MM = 3

SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S = 10
SLIDE_POTISION_SWITCHING_HOME_EVERYTIME = False

class SOFTWARE_POS_LIMIT:
    X_POSITIVE = 56
    X_NEGATIVE = -0.5
    Y_POSITIVE = 56
    Y_NEGATIVE = -0.5
    Z_POSITIVE = 6

SHOW_AUTOLEVEL_BTN = False
AUTOLEVEL_DEFAULT_SETTING = False

MULTIPOINT_AUTOFOCUS_CHANNEL = 'BF LED matrix full'
# MULTIPOINT_AUTOFOCUS_CHANNEL = 'BF LED matrix left half'
MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT = True
MULTIPOINT_BF_SAVING_OPTION = 'Raw'
# MULTIPOINT_BF_SAVING_OPTION = 'RGB2GRAY'
# MULTIPOINT_BF_SAVING_OPTION = 'Green Channel Only'

ENABLE_FLEXIBLE_MULTIPOINT = False

CAMERA_SN = {'ch 1':'SN1','ch 2': 'SN2'} # for multiple cameras, to be overwritten in the configuration file

ENABLE_STROBE_OUTPUT = False

Z_STACKING_CONFIG = 'FROM CENTER' # 'FROM BOTTOM', 'FROM TOP'

# plate format
WELLPLATE_FORMAT = 384

# for 384 well plate
X_MM_384_WELLPLATE_UPPERLEFT = 0
Y_MM_384_WELLPLATE_UPPERLEFT = 0
DEFAULT_Z_POS_MM = 2
X_ORIGIN_384_WELLPLATE_PIXEL = 177 # upper left of B2
Y_ORIGIN_384_WELLPLATE_PIXEL = 141 # upper left of B2
NUMBER_OF_SKIP_384 = 1
A1_X_MM_384_WELLPLATE = 12.05
A1_Y_MM_384_WELLPLATE = 9.05
WELL_SPACING_MM_384_WELLPLATE = 4.5
WELL_SIZE_MM_384_WELLPLATE = 3.3
# B1 upper left corner in piexel: x = 124, y = 141
# B1 upper left corner in mm: x = 12.13 mm - 3.3 mm/2, y = 8.99 mm + 4.5 mm - 3.3 mm/2
# B2 upper left corner in pixel: x = 177, y = 141

WELLPLATE_OFFSET_X_mm = 0 # x offset adjustment for using different plates
WELLPLATE_OFFSET_Y_mm = 0 # y offset adjustment for using different plates

# for USB spectrometer
N_SPECTRUM_PER_POINT = 5

# focus measure operator
FOCUS_MEASURE_OPERATOR = 'LAPE' # 'GLVA' # LAPE has worked well for bright field images; GLVA works well for darkfield/fluorescence

# controller version
CONTROLLER_VERSION = 'Arduino Due' # 'Teensy'

# laser autofocus
SUPPORT_LASER_AUTOFOCUS = False
MAIN_CAMERA_MODEL = 'MER2-1220-32U3M'
FOCUS_CAMEARA_MODEL = 'MER2-630-60U3M'
FOCUS_CAMERA_EXPOSURE_TIME_MS = 2
FOCUS_CAMERA_ANALOG_GAIN = 0
LASER_AF_AVERAGING_N = 5
LASER_AF_DISPLAY_SPOT_IMAGE = True
LASER_AF_CROP_WIDTH = 1536
LASER_AF_CROP_HEIGHT = 256
HAS_TWO_INTERFACES = True
USE_GLASS_TOP = True
SHOW_LEGACY_DISPLACEMENT_MEASUREMENT_WINDOWS = False

MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT = False

RUN_CUSTOM_MULTIPOINT = False

RETRACT_OBJECTIVE_BEFORE_MOVING_TO_LOADING_POSITION = True
OBJECTIVE_RETRACTED_POS_MM = 0.1

CLASSIFICATION_MODEL_PATH ="/home/cephla/Documents/tmp/model_perf_r34_b32.pt"
SEGMENTATION_MODEL_PATH = "/home/cephla/Documents/tmp/model_segmentation_1073_9.pth"
CLASSIFICATION_TEST_MODE=False

USE_TRT_SEGMENTATION=False
SEGMENTATION_CROP=1500

DISP_TH_DURING_MULTIPOINT=0.95
SORT_DURING_MULTIPOINT = False

DO_FLUORESCENCE_RTP = False
STITCH_TILES_WITH_ASHLAR = False

##########################################################
#### start of loading machine specific configurations ####
##########################################################
config_files = glob.glob('.' + '/' + 'configuration*.ini')
if config_files:
    if len(config_files) > 1:
        print('multiple machine configuration files found, the program will exit')
        exit()
    print('load machine-specific configuration')
    #exec(open(config_files[0]).read())
    cfp = ConfigParser()
    cfp.read(config_files[0])
    var_items = list(locals().keys())
    for var_name in var_items:
        if type(locals()[var_name]) is type:
            continue
        varnamelower = var_name.lower()
        if varnamelower not in cfp.options("GENERAL"):
            continue
        value = cfp.get("GENERAL",varnamelower)
        actualvalue = conf_attribute_reader(value)
        locals()[var_name] = actualvalue
    for classkey in var_items:
        myclass = None
        classkeyupper = classkey.upper()
        pop_items = None
        try:
            pop_items = cfp.items(classkeyupper)
        except:
            continue
        if type(locals()[classkey]) is not type:
            continue
        myclass = locals()[classkey]
        populate_class_from_dict(myclass,pop_items)
else:
    print('configuration*.ini file not found, defaulting to legacy configuration')
    config_files = glob.glob('.' + '/' + 'configuration*.txt')
    if config_files:
        if len(config_files) > 1:
            print('multiple machine configuration files found, the program will exit')
            exit()
        print('load machine-specific configuration')
        exec(open(config_files[0]).read())
    else:
        print('machine-specifc configuration not present, the program will exit')
        exit()
##########################################################
##### end of loading machine specific configurations #####
##########################################################
# saving path
if not (DEFAULT_SAVING_PATH.startswith(str(Path.home()))):
    DEFAULT_SAVING_PATH = str(Path.home())+"/"+DEFAULT_SAVING_PATH.strip("/")

# limit switch
X_HOME_SWITCH_POLARITY = LIMIT_SWITCH_POLARITY.X_HOME
Y_HOME_SWITCH_POLARITY = LIMIT_SWITCH_POLARITY.Y_HOME
Z_HOME_SWITCH_POLARITY = LIMIT_SWITCH_POLARITY.Z_HOME

if WELLPLATE_FORMAT == 384:
    WELL_SIZE_MM = 3.3
    WELL_SPACING_MM = 4.5
    NUMBER_OF_SKIP = 1
    A1_X_MM = 12.05
    A1_Y_MM = 9.05
elif WELLPLATE_FORMAT == 96:
    NUMBER_OF_SKIP = 0
    WELL_SIZE_MM = 6.21
    WELL_SPACING_MM = 9
    A1_X_MM = 14.3
    A1_Y_MM = 11.36
elif WELLPLATE_FORMAT == 24:
    NUMBER_OF_SKIP = 0
    WELL_SIZE_MM = 15.54
    WELL_SPACING_MM = 19.3
    A1_X_MM = 17.05
    A1_Y_MM = 13.67
elif WELLPLATE_FORMAT == 12:
    NUMBER_OF_SKIP = 0
    WELL_SIZE_MM = 22.05
    WELL_SPACING_MM = 26
    A1_X_MM = 24.75
    A1_Y_MM = 16.86
elif WELLPLATE_FORMAT == 6:
    NUMBER_OF_SKIP = 0
    WELL_SIZE_MM = 34.94
    WELL_SPACING_MM = 39.2
    A1_X_MM = 24.55
    A1_Y_MM = 23.01
