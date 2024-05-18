from configparser import ConfigParser
import os
import glob
import numpy as np
from pathlib import Path
from pydantic import BaseModel

from enum import Enum
from typing import Optional, Literal, List
from squid_control.control.camera import TriggerModeSetting

import json


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
        if key.startswith("_") and key.endswith("options"):
            continue
        actualkey = key.upper()
        actualvalue = conf_attribute_reader(value)
        setattr(myclass, actualkey, actualvalue)


class AcquisitionSetting(BaseModel):
    CROP_WIDTH: int = 3000
    CROP_HEIGHT: int = 3000
    NUMBER_OF_FOVS_PER_AF: int = 3
    IMAGE_FORMAT: str = "bmp"
    IMAGE_DISPLAY_SCALING_FACTOR: float = 0.3
    DX: float = 0.9
    DY: float = 0.9
    DZ: float = 1.5
    NX: int = 1
    NY: int = 1


class PosUpdate(BaseModel):
    INTERVAL_MS: float = 25


class MicrocontrollerDefSetting(BaseModel):
    MSG_LENGTH: int = 24
    CMD_LENGTH: int = 8
    N_BYTES_POS: int = 4


class Microcontroller2Def(Enum):
    MSG_LENGTH = 4
    CMD_LENGTH = 8
    N_BYTES_POS = 4


class MCU_PINS(Enum):
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


# class LIMIT_SWITCH_POLARITY(BaseModel):
#     ACTIVE_LOW: int = 0
#     ACTIVE_HIGH: int = 1
#     DISABLED: int = 2
#     X_HOME: int= 1
#     Y_HOME: int= 1
#     Z_HOME: int= 2


class ILLUMINATION_CODE(Enum):
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


class VolumetricImagingSetting(BaseModel):
    NUM_PLANES_PER_VOLUME: int = 20


class CmdExecutionStatus(BaseModel):
    COMPLETED_WITHOUT_ERRORS: int = 0
    IN_PROGRESS: int = 1
    CMD_CHECKSUM_ERROR: int = 2
    CMD_INVALID: int = 3
    CMD_EXECUTION_ERROR: int = 4
    ERROR_CODE_EMPTYING_THE_FLUDIIC_LINE_FAILED: int = 100


class CameraConfig(BaseModel):
    ROI_OFFSET_X_DEFAULT: int = 0
    ROI_OFFSET_Y_DEFAULT: int = 0
    ROI_WIDTH_DEFAULT: int = 3104
    ROI_HEIGHT_DEFAULT: int = 2084


class PlateReaderSetting(BaseModel):
    NUMBER_OF_ROWS: int = 8
    NUMBER_OF_COLUMNS: int = 12
    ROW_SPACING_MM: int = 9
    COLUMN_SPACING_MM: int = 9
    OFFSET_COLUMN_1_MM: int = 20
    OFFSET_ROW_A_MM: int = 20


class AFSetting(BaseModel):
    STOP_THRESHOLD: float = 0.85
    CROP_WIDTH: int = 800
    CROP_HEIGHT: int = 800


class TrackingSetting(BaseModel):
    SEARCH_AREA_RATIO: int = 10
    CROPPED_IMG_RATIO: int = 10
    BBOX_SCALE_FACTOR: float = 1.2
    DEFAULT_TRACKER: str = "csrt"
    INIT_METHODS: list = ["roi"]
    DEFAULT_INIT_METHOD: str = "roi"


class SlidPoisitonSetting(BaseModel):
    LOADING_X_MM: int = 30
    LOADING_Y_MM: int = 55
    SCANNING_X_MM: int = 3
    SCANNING_Y_MM: int = 3


class OutputGainSetting(BaseModel):
    REFDIV: bool = False
    CHANNEL0_GAIN: bool = False
    CHANNEL1_GAIN: bool = False
    CHANNEL2_GAIN: bool = False
    CHANNEL3_GAIN: bool = False
    CHANNEL4_GAIN: bool = False
    CHANNEL5_GAIN: bool = False
    CHANNEL6_GAIN: bool = False
    CHANNEL7_GAIN: bool = True


class SoftwarePosLimitSetting(BaseModel):
    X_POSITIVE: float = 56
    X_NEGATIVE: float = -0.5
    Y_POSITIVE: float = 56
    Y_NEGATIVE: float = -0.5
    Z_POSITIVE: float = 6


class FlipImageSetting(Enum):
    Horizontal = "Horizontal"
    Vertical = "Vertical"
    Both = "Both"


class BaseConfig(BaseModel):
    MicrocontrollerDef: MicrocontrollerDefSetting = MicrocontrollerDefSetting()
    VOLUMETRIC_IMAGING: VolumetricImagingSetting = VolumetricImagingSetting()
    CMD_EXECUTION_STATUS: CmdExecutionStatus = CmdExecutionStatus()
    CAMERA_CONFIG: CameraConfig = CameraConfig()
    PLATE_READER: PlateReaderSetting = PlateReaderSetting()
    AF: AFSetting = AFSetting()
    Tracking: TrackingSetting = TrackingSetting()
    SLIDE_POSITION: SlidPoisitonSetting = SlidPoisitonSetting()
    OUTPUT_GAINS: OutputGainSetting = OutputGainSetting()
    SOFTWARE_POS_LIMIT: SoftwarePosLimitSetting = SoftwarePosLimitSetting()
    Acquisition: AcquisitionSetting = AcquisitionSetting()
    USE_SEPARATE_MCU_FOR_DAC: bool = False

    BIT_POS_JOYSTICK_BUTTON: int = 0
    BIT_POS_SWITCH: int = 1

    ###########################################################
    #### machine specific configurations - to be overridden ###
    ###########################################################
    ROTATE_IMAGE_ANGLE: Optional[float] = None
    FLIP_IMAGE: Optional[FlipImageSetting] = None  #

    CAMERA_REVERSE_X: bool = False
    CAMERA_REVERSE_Y: bool = False

    DEFAULT_TRIGGER_MODE: TriggerModeSetting = TriggerModeSetting.SOFTWARE

    # note: XY are the in-plane axes, Z is the focus axis

    # change the following so that "backward" is "backward" - towards the single sided hall effect sensor
    STAGE_MOVEMENT_SIGN_X: int = -1
    STAGE_MOVEMENT_SIGN_Y: int = 1
    STAGE_MOVEMENT_SIGN_Z: int = -1
    STAGE_MOVEMENT_SIGN_THETA: int = 1

    STAGE_POS_SIGN_X: int = -1
    STAGE_POS_SIGN_Y: int = 1
    STAGE_POS_SIGN_Z: int = -1
    STAGE_POS_SIGN_THETA: int = 1

    TRACKING_MOVEMENT_SIGN_X: int = 1
    TRACKING_MOVEMENT_SIGN_Y: int = 1
    TRACKING_MOVEMENT_SIGN_Z: int = 1
    TRACKING_MOVEMENT_SIGN_THETA: int = 1

    USE_ENCODER_X: bool = False
    USE_ENCODER_Y: bool = False
    USE_ENCODER_Z: bool = False
    USE_ENCODER_THETA: bool = False

    ENCODER_POS_SIGN_X: float = 1
    ENCODER_POS_SIGN_Y: float = 1
    ENCODER_POS_SIGN_Z: float = 1
    ENCODER_POS_SIGN_THETA: float = 1

    ENCODER_STEP_SIZE_X_MM: float = 100e-6
    ENCODER_STEP_SIZE_Y_MM: float = 100e-6
    ENCODER_STEP_SIZE_Z_MM: float = 100e-6
    ENCODER_STEP_SIZE_THETA: float = 1

    FULLSTEPS_PER_REV_X: float = 200
    FULLSTEPS_PER_REV_Y: float = 200
    FULLSTEPS_PER_REV_Z: float = 200
    FULLSTEPS_PER_REV_THETA: float = 200

    # beginning of actuator specific configurations

    SCREW_PITCH_X_MM: float = 1
    SCREW_PITCH_Y_MM: float = 1
    SCREW_PITCH_Z_MM: float = 0.012 * 25.4

    MICROSTEPPING_DEFAULT_X: float = 8
    MICROSTEPPING_DEFAULT_Y: float = 8
    MICROSTEPPING_DEFAULT_Z: float = 8
    MICROSTEPPING_DEFAULT_THETA: float = 8  # not used, to be removed

    X_MOTOR_RMS_CURRENT_mA: float = 490
    Y_MOTOR_RMS_CURRENT_mA: float = 490
    Z_MOTOR_RMS_CURRENT_mA: float = 490

    X_MOTOR_I_HOLD: float = 0.5
    Y_MOTOR_I_HOLD: float = 0.5
    Z_MOTOR_I_HOLD: float = 0.5

    MAX_VELOCITY_X_mm: float = 25
    MAX_VELOCITY_Y_mm: float = 25
    MAX_VELOCITY_Z_mm: float = 2

    MAX_ACCELERATION_X_mm: float = 500
    MAX_ACCELERATION_Y_mm: float = 500
    MAX_ACCELERATION_Z_mm: float = 20

    # config encoder arguments
    HAS_ENCODER_X: bool = False
    HAS_ENCODER_Y: bool = False
    HAS_ENCODER_Z: bool = False

    # enable PID control
    ENABLE_PID_X: bool = False
    ENABLE_PID_Y: bool = False
    ENABLE_PID_Z: bool = False

    # flip direction True or False
    ENCODER_FLIP_DIR_X: bool = False
    ENCODER_FLIP_DIR_Y: bool = False
    ENCODER_FLIP_DIR_Z: bool = False

    # distance for each count (um)
    ENCODER_RESOLUTION_UM_X: float = 0.05
    ENCODER_RESOLUTION_UM_Y: float = 0.05
    ENCODER_RESOLUTION_UM_Z: float = 0.1

    # end of actuator specific configurations

    SCAN_STABILIZATION_TIME_MS_X: float = 160
    SCAN_STABILIZATION_TIME_MS_Y: float = 160
    SCAN_STABILIZATION_TIME_MS_Z: float = 20
    HOMING_ENABLED_X: bool = False
    HOMING_ENABLED_Y: bool = False
    HOMING_ENABLED_Z: bool = False

    SLEEP_TIME_S: float = 0.005

    LED_MATRIX_R_FACTOR: float = 0
    LED_MATRIX_G_FACTOR: float = 0
    LED_MATRIX_B_FACTOR: float = 1

    DEFAULT_SAVING_PATH: str = str(Path.home()) + "/Downloads"

    DEFAULT_PIXEL_FORMAT: str = "MONO12"

    DEFAULT_DISPLAY_CROP: int = (
        100  # value ranges from 1 to 100 - image display crop size
    )

    CAMERA_PIXEL_SIZE_UM: dict = {
        "IMX290": 2.9,
        "IMX178": 2.4,
        "IMX226": 1.85,
        "IMX250": 3.45,
        "IMX252": 3.45,
        "IMX273": 3.45,
        "IMX264": 3.45,
        "IMX265": 3.45,
        "IMX571": 3.76,
        "PYTHON300": 4.8,
    }
    OBJECTIVES: dict = {
        "2x": {"magnification": 2, "NA": 0.10, "tube_lens_f_mm": 180},
        "4x": {"magnification": 4, "NA": 0.13, "tube_lens_f_mm": 180},
        "10x": {"magnification": 10, "NA": 0.25, "tube_lens_f_mm": 180},
        "10x (Mitutoyo)": {"magnification": 10, "NA": 0.25, "tube_lens_f_mm": 200},
        "20x (Boli)": {"magnification": 20, "NA": 0.4, "tube_lens_f_mm": 180},
        "20x (Nikon)": {"magnification": 20, "NA": 0.45, "tube_lens_f_mm": 200},
        "20x": {"magnification": 20, "NA": 0.4, "tube_lens_f_mm": 180},
        "40x": {"magnification": 40, "NA": 0.6, "tube_lens_f_mm": 180},
    }
    TUBE_LENS_MM: float = 50
    CAMERA_SENSOR: str = "IMX226"
    DEFAULT_OBJECTIVE: str = "10x (Mitutoyo)"
    TRACKERS: List[str] = [
        "csrt",
        "kcf",
        "mil",
        "tld",
        "medianflow",
        "mosse",
        "daSiamRPN",
    ]
    DEFAULT_TRACKER: str = "csrt"

    ENABLE_TRACKING: bool = False
    TRACKING_SHOW_MICROSCOPE_CONFIGURATIONS: bool = (
        False  # set to true when doing multimodal acquisition
    )

    SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S: float = 10
    SLIDE_POTISION_SWITCHING_HOME_EVERYTIME: bool = False

    SHOW_AUTOLEVEL_BTN: bool = False
    AUTOLEVEL_DEFAULT_SETTING: bool = False

    MULTIPOINT_AUTOFOCUS_CHANNEL: str = "BF LED matrix full"
    # MULTIPOINT_AUTOFOCUS_CHANNEL:str = 'BF LED matrix left half'
    MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT: bool = False
    MULTIPOINT_BF_SAVING_OPTION: str = "Raw"
    # MULTIPOINT_BF_SAVING_OPTION:str = 'RGB2GRAY'
    # MULTIPOINT_BF_SAVING_OPTION:str = 'Green Channel Only'

    DEFAULT_MULTIPOINT_NX: int = 1
    DEFAULT_MULTIPOINT_NY: int = 1

    ENABLE_FLEXIBLE_MULTIPOINT: bool = False

    CAMERA_SN: dict = {
        "ch 1": "SN1",
        "ch 2": "SN2",
    }  # for multiple cameras, to be overwritten in the configuration file

    ENABLE_STROBE_OUTPUT: bool = False

    Z_STACKING_CONFIG: str = "FROM CENTER"  # 'FROM BOTTOM', 'FROM TOP'

    # plate format
    WELLPLATE_FORMAT: int = 384

    # for 384 well plate
    X_MM_384_WELLPLATE_UPPERLEFT: int = 0
    Y_MM_384_WELLPLATE_UPPERLEFT: int = 0
    DEFAULT_Z_POS_MM: int = 2
    X_ORIGIN_384_WELLPLATE_PIXEL: int = 177  # upper left of B2
    Y_ORIGIN_384_WELLPLATE_PIXEL: int = 141  # upper left of B2
    NUMBER_OF_SKIP_384: int = 1
    A1_X_MM_384_WELLPLATE: float = 12.05
    A1_Y_MM_384_WELLPLATE: float = 9.05
    WELL_SPACING_MM_384_WELLPLATE: float = 4.5
    WELL_SIZE_MM_384_WELLPLATE: float = 3.3
    # B1 upper left corner in piexel: x = 124, y = 141
    # B1 upper left corner in mm: x = 12.13 mm - 3.3 mm/2, y = 8.99 mm + 4.5 mm - 3.3 mm/2
    # B2 upper left corner in pixel: x = 177, y = 141

    WELLPLATE_OFFSET_X_mm: float = 0  # x offset adjustment for using different plates
    WELLPLATE_OFFSET_Y_mm: float = 0  # y offset adjustment for using different plates

    # for USB spectrometer
    N_SPECTRUM_PER_POINT: int = 5

    # focus measure operator
    FOCUS_MEASURE_OPERATOR: str = (
        "LAPE"  # 'GLVA' # LAPE has worked well for bright field images; GLVA works well for darkfield/fluorescence
    )

    # controller version
    CONTROLLER_VERSION: str = "Arduino Due"  # 'Teensy'

    # How to read Spinnaker nodemaps, options are INDIVIDUAL or VALUE
    CHOSEN_READ: str = "INDIVIDUAL"

    # laser autofocus
    SUPPORT_LASER_AUTOFOCUS: bool = False
    MAIN_CAMERA_MODEL: str = "MER2-1220-32U3M"
    FOCUS_CAMERA_MODEL: str = "MER2-630-60U3M"
    FOCUS_CAMERA_EXPOSURE_TIME_MS: int = 2
    FOCUS_CAMERA_ANALOG_GAIN: int = 0
    LASER_AF_AVERAGING_N: int = 5
    LASER_AF_DISPLAY_SPOT_IMAGE: bool = True
    LASER_AF_CROP_WIDTH: int = 1536
    LASER_AF_CROP_HEIGHT: int = 256
    HAS_TWO_INTERFACES: bool = True
    USE_GLASS_TOP: bool = True
    SHOW_LEGACY_DISPLACEMENT_MEASUREMENT_WINDOWS: bool = False
    MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT: bool = False
    RUN_CUSTOM_MULTIPOINT: bool = False
    CUSTOM_MULTIPOINT_FUNCTION: str = None
    RETRACT_OBJECTIVE_BEFORE_MOVING_TO_LOADING_POSITION: bool = True
    OBJECTIVE_RETRACTED_POS_MM: float = 0.1
    CLASSIFICATION_MODEL_PATH: str = "/home/cephla/Documents/tmp/model_perf_r34_b32.pt"
    SEGMENTATION_MODEL_PATH: str = (
        "/home/cephla/Documents/tmp/model_segmentation_1073_9.pth"
    )
    CLASSIFICATION_TEST_MODE: bool = False
    USE_TRT_SEGMENTATION: bool = False
    SEGMENTATION_CROP: int = 1500
    DISP_TH_DURING_MULTIPOINT: float = 0.95
    SORT_DURING_MULTIPOINT: bool = False
    DO_FLUORESCENCE_RTP: bool = False
    ENABLE_SPINNING_DISK_CONFOCAL: bool = False
    INVERTED_OBJECTIVE: bool = False
    ILLUMINATION_INTENSITY_FACTOR: float = 0.6
    CAMERA_TYPE: Literal["Default"] = "Default"
    FOCUS_CAMERA_TYPE: Literal["Default"] = "Default"
    LASER_AF_CHARACTERIZATION_MODE: bool = False

    # limit switch
    X_HOME_SWITCH_POLARITY: int = 1
    Y_HOME_SWITCH_POLARITY: int = 1
    Z_HOME_SWITCH_POLARITY: int = 2

    # for 96 well plate
    NUMBER_OF_SKIP: int = 0
    WELL_SIZE_MM: float = 6.21
    WELL_SPACING_MM: int = 9
    A1_X_MM: float = 14.3
    A1_Y_MM: float = 11.36

    SHOW_DAC_CONTROL: bool = False
    CACHE_CONFIG_FILE_PATH: str = None
    CHANNEL_CONFIGURATIONS_PATH: str = ""
    LAST_COORDS_PATH: str = ""


    def read_config(self, config_path):
        cached_config_file_path = None

        try:
            with open(CONFIG.CACHE_CONFIG_FILE_PATH, "r") as file:
                for line in file:
                    cached_config_file_path = line
                    break
        except FileNotFoundError:
            cached_config_file_path = None

        config_files = [config_path]
        if config_files:
            if len(config_files) > 1:
                if cached_config_file_path in config_files:
                    print(
                        "defaulting to last cached config file at "
                        + cached_config_file_path
                    )
                    config_files = [cached_config_file_path]
                else:
                    print(
                        "multiple machine configuration files found, the program will exit"
                    )
                    exit()
            print("load machine-specific configuration")
            # exec(open(config_files[0]).read())
            cfp = ConfigParser()
            cfp.read(config_files[0])
            var_items = list(self.model_fields.keys())
            for var_name in var_items:
                if type(getattr(self, var_name)) is type:
                    continue
                varnamelower = var_name.lower()
                if varnamelower not in cfp.options("GENERAL"):
                    continue
                value = cfp.get("GENERAL", varnamelower)
                actualvalue = conf_attribute_reader(value)
                setattr(self, var_name, actualvalue)
            for classkey in var_items:
                myclass = None
                classkeyupper = classkey.upper()
                pop_items = None
                try:
                    pop_items = cfp.items(classkeyupper)
                except:
                    continue
                if type(getattr(self, classkey)) is not type:
                    continue
                myclass = getattr(self, classkey)
                populate_class_from_dict(myclass, pop_items)
            with open(CONFIG.CACHE_CONFIG_FILE_PATH, "w") as file:
                file.write(str(config_files[0]))
            cached_config_file_path = config_files[0]
        else:
            print("configuration*.ini file not found, defaulting to legacy configuration")
            config_files = glob.glob("." + "/" + "configuration*.txt")
            if config_files:
                if len(config_files) > 1:
                    print(
                        "multiple machine configuration files found, the program will exit"
                    )
                    exit()
                print("load machine-specific configuration")
                exec(open(config_files[0]).read())
            else:
                print("machine-specific configuration not present, the program will exit")
                exit()
        return cached_config_file_path


CONFIG = BaseConfig()


def load_config(config_path, multipoint_function):
    global CONFIG
    home_dir = Path.home()
    config_dir = home_dir / '.squid-control'

    # Ensure the .squid-control directory exists
    config_dir.mkdir(exist_ok=True)

    current_dir = Path(__file__).parent
    if not str(config_path).endswith(".ini"):
        config_path = current_dir / ("../configurations/configuration_" + str(config_path) + ".ini")


    CONFIG.CACHE_CONFIG_FILE_PATH = str(config_dir / 'cache_config_file_path.txt')
    CONFIG.CHANNEL_CONFIGURATIONS_PATH = str(config_dir / 'channel_configurations.xml')
    CONFIG.LAST_COORDS_PATH = str(config_dir / 'last_coords.txt')

    if config_path and not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file {config_path} not found.")

    cf_editor_parser = ConfigParser()
    # Read the config
    cached_config_file_path = CONFIG.read_config(config_path)
    CONFIG.STAGE_POS_SIGN_X = CONFIG.STAGE_MOVEMENT_SIGN_X
    CONFIG.STAGE_POS_SIGN_Y = CONFIG.STAGE_MOVEMENT_SIGN_Y
    CONFIG.STAGE_POS_SIGN_Z = CONFIG.STAGE_MOVEMENT_SIGN_Z
    CONFIG.STAGE_POS_SIGN_THETA = CONFIG.STAGE_MOVEMENT_SIGN_THETA
    if multipoint_function:
        CONFIG.RUN_CUSTOM_MULTIPOINT = True
        CONFIG.CUSTOM_MULTIPOINT_FUNCTION = multipoint_function

    # saving path
    if not (CONFIG.DEFAULT_SAVING_PATH.startswith(str(Path.home()))):
        CONFIG.DEFAULT_SAVING_PATH = (
            str(Path.home()) + "/" + CONFIG.DEFAULT_SAVING_PATH.strip("/")
        )

    if CONFIG.ENABLE_TRACKING:
        CONFIG.DEFAULT_DISPLAY_CROP = CONFIG.Tracking.DEFAULT_DISPLAY_CROP

    if CONFIG.WELLPLATE_FORMAT == 384:
        CONFIG.WELL_SIZE_MM = 3.3
        CONFIG.WELL_SPACING_MM = 4.5
        CONFIG.NUMBER_OF_SKIP = 1
        CONFIG.A1_X_MM = 12.05
        CONFIG.A1_Y_MM = 9.05
    elif CONFIG.WELLPLATE_FORMAT == 96:
        CONFIG.NUMBER_OF_SKIP = 0
        CONFIG.WELL_SIZE_MM = 6.21
        CONFIG.WELL_SPACING_MM = 9
        CONFIG.A1_X_MM = 14.3
        CONFIG.A1_Y_MM = 11.36
    elif CONFIG.WELLPLATE_FORMAT == 24:
        CONFIG.NUMBER_OF_SKIP = 0
        CONFIG.WELL_SIZE_MM = 15.54
        CONFIG.WELL_SPACING_MM = 19.3
        CONFIG.A1_X_MM = 17.05
        CONFIG.A1_Y_MM = 13.67
    elif CONFIG.WELLPLATE_FORMAT == 12:
        CONFIG.NUMBER_OF_SKIP = 0
        CONFIG.WELL_SIZE_MM = 22.05
        CONFIG.WELL_SPACING_MM = 26
        CONFIG.A1_X_MM = 24.75
        CONFIG.A1_Y_MM = 16.86
    elif CONFIG.WELLPLATE_FORMAT == 6:
        CONFIG.NUMBER_OF_SKIP = 0
        CONFIG.WELL_SIZE_MM = 34.94
        CONFIG.WELL_SPACING_MM = 39.2
        CONFIG.A1_X_MM = 24.55
        CONFIG.A1_Y_MM = 23.01

    if os.path.exists(cached_config_file_path):
        cf_editor_parser.read(cached_config_file_path)
    else:
        return False





    
