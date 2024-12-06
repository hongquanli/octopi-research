import os
import sys
import glob
from pathlib import Path
from configparser import ConfigParser
import json
import csv

import squid.logging

log = squid.logging.get_logger(__name__)


def conf_attribute_reader(string_value):
    """
    :brief: standardized way for reading config entries
    that are strings, in priority order
    None -> bool -> dict/list (via json) -> int -> float -> string
    REMEMBER TO ENCLOSE PROPERTY NAMES IN LISTS/DICTS IN
    DOUBLE QUOTES
    """
    actualvalue = str(string_value).strip()
    try:
        if str(actualvalue) == "None":
            return None
    except:
        pass
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
    CONTINUOUS = 'Continuous Acquisition'

class Acquisition:
    CROP_WIDTH = 3000
    CROP_HEIGHT = 3000
    NUMBER_OF_FOVS_PER_AF = 3
    IMAGE_FORMAT = 'bmp'
    IMAGE_DISPLAY_SCALING_FACTOR = 0.3
    PSEUDO_COLOR = False
    MERGE_CHANNELS = False
    PSEUDO_COLOR_MAP = {
    "405": {"hex": 0x0000FF},   # blue
    "488": {"hex": 0x00FF00},   # green
    "561": {"hex": 0xFFCF00},   # yellow
    "638": {"hex": 0xFF0000},   # red
    "730": {"hex": 0x770000}    # dark red
    }
    DX = 0.9
    DY = 0.9
    DZ = 1.5
    NX = 1
    NY = 1

class PosUpdate:
    INTERVAL_MS = 25

class MicrocontrollerDef:
    MSG_LENGTH = 24
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
    SET_DAC80508_REFDIV_GAIN = 16
    SET_ILLUMINATION_INTENSITY_FACTOR = 17
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
    SET_HOME_SAFETY_MERGIN = 28
    SET_PID_ARGUMENTS = 29
    SEND_HARDWARE_TRIGGER = 30
    SET_STROBE_DELAY = 31
    SET_AXIS_DISABLE_ENABLE = 32
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
    ILLUMINATION_SOURCE_LED_ARRAY_FULL = 0
    ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF = 1
    ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF = 2
    ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR = 3
    ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA = 4
    ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT = 5
    ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT = 6
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

class CAMERA_CONFIG:
    ROI_OFFSET_X_DEFAULT = 0
    ROI_OFFSET_Y_DEFAULT = 0
    ROI_WIDTH_DEFAULT = 3104
    ROI_HEIGHT_DEFAULT = 2084

PRINT_CAMERA_FPS = True

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

# config encoder arguments
HAS_ENCODER_X = False
HAS_ENCODER_Y = False
HAS_ENCODER_Z = False

# enable PID control
ENABLE_PID_X  = False
ENABLE_PID_Y  = False
ENABLE_PID_Z  = False

# PID arguments
PID_P_X = int(1<<12)
PID_I_X = int(0)
PID_D_X = int(0)

PID_P_Y = int(1<<12)
PID_I_Y = int(0)
PID_D_Y = int(0)

PID_P_Z = int(1<<12)
PID_I_Z = int(0)
PID_D_Z = int(1)

# flip direction True or False
ENCODER_FLIP_DIR_X = True
ENCODER_FLIP_DIR_Y = True
ENCODER_FLIP_DIR_Z = True

# distance for each count (um)
ENCODER_RESOLUTION_UM_X = 0.05
ENCODER_RESOLUTION_UM_Y = 0.05
ENCODER_RESOLUTION_UM_Z = 0.1

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

TUBE_LENS_MM = 50
CAMERA_SENSOR = 'IMX226'
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

class OUTPUT_GAINS:
    REFDIV = False
    CHANNEL0_GAIN = False
    CHANNEL1_GAIN = False
    CHANNEL2_GAIN = False
    CHANNEL3_GAIN = False
    CHANNEL4_GAIN = False
    CHANNEL5_GAIN = False
    CHANNEL6_GAIN = False
    CHANNEL7_GAIN = True

SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S = 10
SLIDE_POTISION_SWITCHING_HOME_EVERYTIME = False

class SOFTWARE_POS_LIMIT:
    X_POSITIVE = 56
    X_NEGATIVE = -0.5
    Y_POSITIVE = 56
    Y_NEGATIVE = -0.5
    Z_POSITIVE = 7
    Z_NEGATIVE = 0.05

SHOW_AUTOLEVEL_BTN = False
AUTOLEVEL_DEFAULT_SETTING = False

MULTIPOINT_AUTOFOCUS_CHANNEL = 'BF LED matrix full'
# MULTIPOINT_AUTOFOCUS_CHANNEL = 'BF LED matrix left half'
MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT = False
MULTIPOINT_BF_SAVING_OPTION = 'Raw'
# MULTIPOINT_BF_SAVING_OPTION = 'RGB2GRAY'
# MULTIPOINT_BF_SAVING_OPTION = 'Green Channel Only'

DEFAULT_MULTIPOINT_NX=1
DEFAULT_MULTIPOINT_NY=1

ENABLE_FLEXIBLE_MULTIPOINT = True
USE_OVERLAP_FOR_FLEXIBLE = True
ENABLE_WELLPLATE_MULTIPOINT = True
ENABLE_RECORDING = False

CAMERA_SN = {'ch 1':'SN1','ch 2': 'SN2'} # for multiple cameras, to be overwritten in the configuration file

ENABLE_STROBE_OUTPUT = False

ACQUISITION_PATTERN = 'S-Pattern' # 'S-Pattern', 'Unidirectional'
FOV_PATTERN = 'Unidirectional' # 'S-Pattern', 'Unidirectional'

Z_STACKING_CONFIG = 'FROM BOTTOM' # 'FROM BOTTOM', 'FROM TOP'
Z_STACKING_CONFIG_MAP = {
    0: 'FROM BOTTOM',
    1: 'FROM CENTER',
    2: 'FROM TOP'
}

DEFAULT_Z_POS_MM = 2

WELLPLATE_OFFSET_X_mm = 0 # x offset adjustment for using different plates
WELLPLATE_OFFSET_Y_mm = 0 # y offset adjustment for using different plates

# for USB spectrometer
N_SPECTRUM_PER_POINT = 5

# focus measure operator
FOCUS_MEASURE_OPERATOR = 'LAPE' # 'GLVA' # LAPE has worked well for bright field images; GLVA works well for darkfield/fluorescence

# controller version
CONTROLLER_VERSION = 'Arduino Due' # 'Teensy'

#How to read Spinnaker nodemaps, options are INDIVIDUAL or VALUE
CHOSEN_READ = 'INDIVIDUAL'

# laser autofocus
SUPPORT_LASER_AUTOFOCUS = True
MAIN_CAMERA_MODEL = 'MER2-1220-32U3M'
FOCUS_CAMERA_MODEL = 'MER2-630-60U3M'
FOCUS_CAMERA_EXPOSURE_TIME_MS = 2
FOCUS_CAMERA_ANALOG_GAIN = 0
LASER_AF_AVERAGING_N = 5
LASER_AF_DISPLAY_SPOT_IMAGE = True
LASER_AF_CROP_WIDTH = 1536
LASER_AF_CROP_HEIGHT = 256
HAS_TWO_INTERFACES = True
LASER_AF_RANGE = 200
USE_GLASS_TOP = True
SHOW_LEGACY_DISPLACEMENT_MEASUREMENT_WINDOWS = False

MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT = False
MULTIPOINT_CONTRAST_AUTOFOCUS_ENABLE_BY_DEFAULT = False

RUN_CUSTOM_MULTIPOINT = False

RETRACT_OBJECTIVE_BEFORE_MOVING_TO_LOADING_POSITION = True
OBJECTIVE_RETRACTED_POS_MM = 0.1

TWO_CLASSIFICATION_MODELS = False
CLASSIFICATION_MODEL_PATH = "models/resnet18_en/version1/best.pt"
CLASSIFICATION_MODEL_PATH2 = "models/resnet18_en/version2/best.pt"
CLASSIFICATION_TEST_MODE = False
CLASSIFICATION_TH = 0.3

SEGMENTATION_MODEL_PATH = "models/m2unet_model_flat_erode1_wdecay5_smallbatch/model_4000_11.pth"
ENABLE_SEGMENTATION = True
USE_TRT_SEGMENTATION = False
SEGMENTATION_CROP = 1500

DISP_TH_DURING_MULTIPOINT = 0.95
SORT_DURING_MULTIPOINT = False

DO_FLUORESCENCE_RTP = False

INVERTED_OBJECTIVE = False

ILLUMINATION_INTENSITY_FACTOR = 0.6

CAMERA_TYPE = "Default"
FOCUS_CAMERA_TYPE = "Default"

# Spinning disk confocal integration
ENABLE_SPINNING_DISK_CONFOCAL = False
USE_LDI_SERIAL_CONTROL = False
LDI_INTENSITY_MODE = 'PC'
LDI_SHUTTER_MODE = 'PC'

XLIGHT_EMISSION_FILTER_MAPPING = {405:1,470:2,555:3,640:4,730:5}
XLIGHT_SERIAL_NUMBER = "B00031BE"
XLIGHT_SLEEP_TIME_FOR_WHEEL = 0.25
XLIGHT_VALIDATE_WHEEL_POS = False

# Confocal.nl NL5 integration
ENABLE_NL5 = False
ENABLE_CELLX = False
CELLX_SN = None
CELLX_MODULATION = 'EXT Digital'
NL5_USE_AOUT = False
NL5_USE_DOUT = True
NL5_TRIGGER_PIN = 2
NL5_WAVENLENGTH_MAP = {
    405: 1,
    470: 2, 488: 2,
    545: 3, 555: 3, 561: 3,
    637: 4, 638: 4, 640: 4
}

# Laser AF characterization mode
LASER_AF_CHARACTERIZATION_MODE = False

# Napari integration
USE_NAPARI_FOR_LIVE_VIEW = False
USE_NAPARI_FOR_MULTIPOINT = True
USE_NAPARI_FOR_TILED_DISPLAY = False
USE_NAPARI_FOR_MOSAIC_DISPLAY = True
USE_NAPARI_WELL_SELECTION = False
USE_NAPARI_FOR_LIVE_CONTROL = False
LIVE_ONLY_MODE = False

# Controller SN (needed when using multiple teensy-based connections)
CONTROLLER_SN = None

# Sci microscopy
SUPPORT_SCIMICROSCOPY_LED_ARRAY = False
SCIMICROSCOPY_LED_ARRAY_SN = None
SCIMICROSCOPY_LED_ARRAY_DISTANCE = 50
SCIMICROSCOPY_LED_ARRAY_DEFAULT_NA = 0.8
SCIMICROSCOPY_LED_ARRAY_DEFAULT_COLOR = [1,1,1]
SCIMICROSCOPY_LED_ARRAY_TURN_ON_DELAY = 0.03 # time to wait before trigger the camera (in seconds)

# Tiled preview
SHOW_TILED_PREVIEW = False
PRVIEW_DOWNSAMPLE_FACTOR = 5

# Navigation Bar (Stages)
SHOW_NAVIGATION_BAR = False
ENABLE_CLICK_TO_MOVE_BY_DEFAULT = True

# Stitcher
ENABLE_STITCHER = False
IS_HCS = False
DYNAMIC_REGISTRATION = False
STITCH_COMPLETE_ACQUISITION = False
CHANNEL_COLORS_MAP = {
    "405": {"hex": 0x3300FF, "name": "blue"},
    "488": {"hex": 0x1FFF00, "name": "green"},
    "561": {"hex": 0xFFCF00, "name": "yellow"},
    "638": {"hex": 0xFF0000, "name": "red"},
    "730": {"hex": 0x770000, "name": "dark red"},
    "R": {"hex": 0xFF0000, "name": "red"},
    "G": {"hex": 0x1FFF00, "name": "green"},
    "B": {"hex": 0x3300FF, "name": "blue"}
}

# Emission filter wheel
USE_ZABER_EMISSION_FILTER_WHEEL = False
ZABER_EMISSION_FILTER_WHEEL_DELAY_MS = 70
ZABER_EMISSION_FILTER_WHEEL_BLOCKING_CALL = False
USE_OPTOSPIN_EMISSION_FILTER_WHEEL = False
FILTER_CONTROLLER_SERIAL_NUMBER = 'A10NG007'
OPTOSPIN_EMISSION_FILTER_WHEEL_SPEED_HZ = 50
OPTOSPIN_EMISSION_FILTER_WHEEL_DELAY_MS = 70
OPTOSPIN_EMISSION_FILTER_WHEEL_TTL_TRIGGER = False

# Stage
USE_PRIOR_STAGE = False
PRIOR_STAGE_SN = ""

# camera blacklevel settings
DISPLAY_TOUPCAMER_BLACKLEVEL_SETTINGS = False
DEFAULT_BLACKLEVEL_VALUE = 3

def read_objectives_csv(file_path):
    objectives = {}
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            objectives[row['name']] = {
                'magnification': float(row['magnification']),
                'NA': float(row['NA']),
                'tube_lens_f_mm': float(row['tube_lens_f_mm'])
            }
    return objectives

def read_sample_formats_csv(file_path):
    sample_formats = {}
    with open(file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            format_ = str(row['format'])
            format_key = f"{format_} well plate" if format_.isdigit() else format_
            sample_formats[format_key] = {
                'a1_x_mm': float(row['a1_x_mm']),
                'a1_y_mm': float(row['a1_y_mm']),
                'a1_x_pixel': int(row['a1_x_pixel']),
                'a1_y_pixel': int(row['a1_y_pixel']),
                'well_size_mm': float(row['well_size_mm']),
                'well_spacing_mm': float(row['well_spacing_mm']),
                'number_of_skip': int(row['number_of_skip']),
                'rows': int(row['rows']),
                'cols': int(row['cols'])
            }
    return sample_formats

def load_formats():
    """Load formats, prioritizing cache for sample formats."""
    cache_path = 'cache'
    default_path = 'objective_and_sample_formats'

    # Load objectives (from default location)
    objectives = read_objectives_csv(os.path.join(default_path, 'objectives.csv'))

    # Try cache first for sample formats, fall back to default if not found
    cached_formats_path = os.path.join(cache_path, 'sample_formats.csv')
    default_formats_path = os.path.join(default_path, 'sample_formats.csv')

    if os.path.exists(cached_formats_path):
        print('Using cached sample formats')
        sample_formats = read_sample_formats_csv(cached_formats_path)
    else:
        print('Using default sample formats')
        sample_formats = read_sample_formats_csv(default_formats_path)

    return objectives, sample_formats


OBJECTIVES_CSV_PATH = 'objectives.csv'
SAMPLE_FORMATS_CSV_PATH = 'sample_formats.csv'

OBJECTIVES, WELLPLATE_FORMAT_SETTINGS = load_formats()

##########################################################
#### start of loading machine specific configurations ####
##########################################################
CACHED_CONFIG_FILE_PATH = None

# Piezo configuration items
Z_MOTOR_CONFIG = "STEPPER" # "STEPPER", "STEPPER + PIEZO", "PIEZO", "LINEAR"
ENABLE_OBJECTIVE_PIEZO = "PIEZO" in Z_MOTOR_CONFIG

# the value of OBJECTIVE_PIEZO_CONTROL_VOLTAGE_RANGE is 2.5 or 5
OBJECTIVE_PIEZO_CONTROL_VOLTAGE_RANGE = 5
OBJECTIVE_PIEZO_RANGE_UM = 300
OBJECTIVE_PIEZO_HOME_UM = 20
OBJECTIVE_PIEZO_FLIP_DIR = False

MULTIPOINT_USE_PIEZO_FOR_ZSTACKS = ENABLE_OBJECTIVE_PIEZO
MULTIPOINT_PIEZO_DELAY_MS = 20
MULTIPOINT_PIEZO_UPDATE_DISPLAY = True

AWB_RATIOS_R = 1.375
AWB_RATIOS_G = 1
AWB_RATIOS_B = 1.4141

try:
    with open("cache/config_file_path.txt", 'r') as file:
        for line in file:
            CACHED_CONFIG_FILE_PATH = line
            break
except FileNotFoundError:
    CACHED_CONFIG_FILE_PATH = None

config_files = glob.glob('.' + '/' + 'configuration*.ini')
if config_files:
    if len(config_files) > 1:
        if CACHED_CONFIG_FILE_PATH in config_files:
            log.info(f'defaulting to last cached config file at \'{CACHED_CONFIG_FILE_PATH}\'')
            config_files = [CACHED_CONFIG_FILE_PATH]
        else:
            log.error('multiple machine configuration files found, the program will exit')
            sys.exit(1)
    log.info('load machine-specific configuration')
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
    
    with open("cache/config_file_path.txt", 'w') as file:
        file.write(config_files[0])
    CACHED_CONFIG_FILE_PATH = config_files[0]
else:
    log.warning('configuration*.ini file not found, defaulting to legacy configuration')
    config_files = glob.glob('.' + '/' + 'configuration*.txt')
    if config_files:
        if len(config_files) > 1:
            log.error('multiple machine configuration files found, the program will exit')
            sys.exit(1)
        log.info('load machine-specific configuration')
        exec(open(config_files[0]).read())
    else:
        log.error('machine-specific configuration not present, the program will exit')
        sys.exit(1)

try:
    with open("cache/objective_and_sample_format.txt", 'r') as f:
        cached_settings = json.load(f)
        DEFAULT_OBJECTIVE = cached_settings.get('objective') if cached_settings.get('objective') in OBJECTIVES else '20x'
        WELLPLATE_FORMAT = str(cached_settings.get('wellplate_format'))
        WELLPLATE_FORMAT = WELLPLATE_FORMAT + ' well plate' if WELLPLATE_FORMAT.isdigit() else WELLPLATE_FORMAT
        if WELLPLATE_FORMAT not in WELLPLATE_FORMAT_SETTINGS:
            WELLPLATE_FORMAT = '96 well plate'
except (FileNotFoundError, json.JSONDecodeError):
    DEFAULT_OBJECTIVE = '20x'
    WELLPLATE_FORMAT = '96 well plate'

NUMBER_OF_SKIP = WELLPLATE_FORMAT_SETTINGS[WELLPLATE_FORMAT]['number_of_skip'] # num rows/cols to skip on wellplate edge
WELL_SIZE_MM = WELLPLATE_FORMAT_SETTINGS[WELLPLATE_FORMAT]['well_size_mm']
WELL_SPACING_MM = WELLPLATE_FORMAT_SETTINGS[WELLPLATE_FORMAT]['well_spacing_mm']
A1_X_MM = WELLPLATE_FORMAT_SETTINGS[WELLPLATE_FORMAT]['a1_x_mm'] # measured stage position - to update
A1_Y_MM = WELLPLATE_FORMAT_SETTINGS[WELLPLATE_FORMAT]['a1_y_mm'] # measured stage position - to update
A1_X_PIXEL = WELLPLATE_FORMAT_SETTINGS[WELLPLATE_FORMAT]['a1_x_pixel'] # coordinate on the png
A1_Y_PIXEL = WELLPLATE_FORMAT_SETTINGS[WELLPLATE_FORMAT]['a1_y_pixel'] # coordinate on the png

##########################################################
##### end of loading machine specific configurations #####
##########################################################

# objective piezo
if ENABLE_OBJECTIVE_PIEZO == False:
    MULTIPOINT_USE_PIEZO_FOR_ZSTACKS = False

# saving path
if not (DEFAULT_SAVING_PATH.startswith(str(Path.home()))):
    DEFAULT_SAVING_PATH = str(Path.home())+"/"+DEFAULT_SAVING_PATH.strip("/")

# limit switch
X_HOME_SWITCH_POLARITY = LIMIT_SWITCH_POLARITY.X_HOME
Y_HOME_SWITCH_POLARITY = LIMIT_SWITCH_POLARITY.Y_HOME
Z_HOME_SWITCH_POLARITY = LIMIT_SWITCH_POLARITY.Z_HOME

# home safety margin with (um) unit
X_HOME_SAFETY_MARGIN_UM = 50
Y_HOME_SAFETY_MARGIN_UM = 50
Z_HOME_SAFETY_MARGIN_UM = 600 

if ENABLE_TRACKING:
    DEFAULT_DISPLAY_CROP = Tracking.DEFAULT_DISPLAY_CROP
