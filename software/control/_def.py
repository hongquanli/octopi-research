from dataclasses import dataclass, field
import json
from pathlib import Path

class TriggerMode:
    SOFTWARE = 'Software Trigger'
    HARDWARE = 'Hardware Trigger'
    CONTINUOUS = 'Continuous Acqusition'

class Acquisition:
    CROP_WIDTH:int = 3000
    CROP_HEIGHT:int = 3000
    NUMBER_OF_FOVS_PER_AF:int = 3
    IMAGE_FORMAT:str = 'bmp'
    IMAGE_DISPLAY_SCALING_FACTOR:float = 0.3
    DX:float = 0.9
    DY:float = 0.9
    DZ:float = 1.5

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

USE_SEPARATE_MCU_FOR_DAC:bool = False

class CMD_SET:
    MOVE_X:int = 0
    MOVE_Y:int = 1
    MOVE_Z:int = 2
    MOVE_THETA:int = 3
    HOME_OR_ZERO:int = 5
    TURN_ON_ILLUMINATION:int = 10
    TURN_OFF_ILLUMINATION:int = 11
    SET_ILLUMINATION:int = 12
    SET_ILLUMINATION_LED_MATRIX:int = 13
    ACK_JOYSTICK_BUTTON_PRESSED:int = 14
    ANALOG_WRITE_ONBOARD_DAC:int = 15
    MOVETO_X:int = 6
    MOVETO_Y:int = 7
    MOVETO_Z:int = 8
    SET_LIM:int = 9
    SET_LIM_SWITCH_POLARITY:int = 20
    CONFIGURE_STEPPER_DRIVER:int = 21
    SET_MAX_VELOCITY_ACCELERATION:int = 22
    SET_LEAD_SCREW_PITCH:int = 23
    SET_OFFSET_VELOCITY:int = 24
    SEND_HARDWARE_TRIGGER:int = 30
    SET_STROBE_DELAY:int = 31
    INITIALIZE:int = 254
    RESET:int = 255

class CMD_SET2:
    ANALOG_WRITE_DAC8050X:int = 0
    SET_CAMERA_TRIGGER_FREQUENCY:int = 1
    START_CAMERA_TRIGGERING:int = 2
    STOP_CAMERA_TRIGGERING:int = 3

BIT_POS_JOYSTICK_BUTTON = 0
BIT_POS_SWITCH = 1

class HOME_OR_ZERO:
    HOME_NEGATIVE:int = 1 # motor moves along the negative direction (MCU coordinates)
    HOME_POSITIVE:int = 0 # motor moves along the negative direction (MCU coordinates)
    ZERO:int = 2

class AXIS:
    X:int = 0
    Y:int = 1
    Z:int = 2
    THETA:int = 3
    XY:int = 4

class LIMIT_CODE:
    X_POSITIVE:int = 0
    X_NEGATIVE:int = 1
    Y_POSITIVE:int = 2
    Y_NEGATIVE:int = 3
    Z_POSITIVE:int = 4
    Z_NEGATIVE:int = 5

class LIMIT_SWITCH_POLARITY:
    ACTIVE_LOW:int = 0
    ACTIVE_HIGH:int = 1
    DISABLED:int = 2

class ILLUMINATION_CODE:
    ILLUMINATION_SOURCE_LED_ARRAY_FULL:int = 0
    ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:int = 1
    ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:int = 2
    ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:int = 3
    ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA:int = 4
    ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT:int = 5
    ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT:int = 6
    ILLUMINATION_SOURCE_LED_EXTERNAL_FET:int = 20
    ILLUMINATION_SOURCE_405NM:int = 11
    ILLUMINATION_SOURCE_488NM:int = 12
    ILLUMINATION_SOURCE_638NM:int = 13
    ILLUMINATION_SOURCE_561NM:int = 14
    ILLUMINATION_SOURCE_730NM:int = 15

class CAMERA:
    ROI_OFFSET_X_DEFAULT:int = 0
    ROI_OFFSET_Y_DEFAULT:int = 0
    ROI_WIDTH_DEFAULT:int = 3000
    ROI_HEIGHT_DEFAULT:int = 3000

class VOLUMETRIC_IMAGING:
    NUM_PLANES_PER_VOLUME:int = 20

class CMD_EXECUTION_STATUS:
    COMPLETED_WITHOUT_ERRORS:int = 0
    IN_PROGRESS:int = 1
    CMD_CHECKSUM_ERROR:int = 2
    CMD_INVALID:int = 3
    CMD_EXECUTION_ERROR:int = 4
    ERROR_CODE_EMPTYING_THE_FLUDIIC_LINE_FAILED:int = 100

@dataclass(frozen=True)
class ObjectiveData:
    magnification:float
    NA:float
    tube_lens_f_mm:float

@dataclass(frozen=True)
class AutofocusConfig:
    STOP_THRESHOLD:float = 0.85
    CROP_WIDTH:int = 800
    CROP_HEIGHT:int = 800

@dataclass(frozen=True)
class SoftwareStagePositionLimits:
    X_POSITIVE:float = 56
    X_NEGATIVE:float = -0.5
    Y_POSITIVE:float = 56
    Y_NEGATIVE:float = -0.5
    Z_POSITIVE:float = 6

class FocusMeasureOperators:
    """ focus measure operators - GLVA has worked well for darkfield/fluorescence, and LAPE has worked well for brightfield """
    GLVA:str="GLVA"
    LAPE:str="LAPE"

class ControllerType:
    DUE:str='Arduino Due'
    TEENSY:str='Teensy'

###########################################################
#### machine specific configurations - to be overridden ###
###########################################################
from typing import Optional, Dict, List

from control.typechecker import TypecheckClass, ClosedRange, ClosedSet

@TypecheckClass
@dataclass
class MachineConfiguration:
    # hardware specific stuff
    ROTATE_IMAGE_ANGLE:ClosedSet[int](-90,0,90,180)=0
    
    FLIP_IMAGE:ClosedSet[Optional[str]](None,'Vertical','Horizontal','Both')=None

    # note: XY are the in-plane axes, Z is the focus axis

    # change the following so that "backward" is "backward" - towards the single sided hall effect sensor
    STAGE_MOVEMENT_SIGN_X:int = 1
    STAGE_MOVEMENT_SIGN_Y:int = 1
    STAGE_MOVEMENT_SIGN_Z:int = -1
    STAGE_MOVEMENT_SIGN_THETA:int = 1

    STAGE_POS_SIGN_X:int = STAGE_MOVEMENT_SIGN_X
    STAGE_POS_SIGN_Y:int = STAGE_MOVEMENT_SIGN_Y
    STAGE_POS_SIGN_Z:int = STAGE_MOVEMENT_SIGN_Z
    STAGE_POS_SIGN_THETA:int = STAGE_MOVEMENT_SIGN_THETA

    USE_ENCODER_X:bool = False
    USE_ENCODER_Y:bool = False
    USE_ENCODER_Z:bool = False
    USE_ENCODER_THETA:bool = False

    ENCODER_POS_SIGN_X:int = 1
    ENCODER_POS_SIGN_Y:int = 1
    ENCODER_POS_SIGN_Z:int = 1
    ENCODER_POS_SIGN_THETA:int = 1

    ENCODER_STEP_SIZE_X_MM:float = 100e-6
    ENCODER_STEP_SIZE_Y_MM:float = 100e-6
    ENCODER_STEP_SIZE_Z_MM:float = 100e-6
    ENCODER_STEP_SIZE_THETA:float = 1.0

    FULLSTEPS_PER_REV_X:int = 200
    FULLSTEPS_PER_REV_Y:int = 200
    FULLSTEPS_PER_REV_Z:int = 200
    FULLSTEPS_PER_REV_THETA:int = 200

    # beginning of actuator specific configurations

    SCREW_PITCH_X_MM:float = 1.0
    SCREW_PITCH_Y_MM:float = 1.0
    SCREW_PITCH_Z_MM:float = 0.012*25.4

    MICROSTEPPING_DEFAULT_X:int = 8
    MICROSTEPPING_DEFAULT_Y:int = 8
    MICROSTEPPING_DEFAULT_Z:int = 8
    MICROSTEPPING_DEFAULT_THETA:int = 8

    X_MOTOR_RMS_CURRENT_mA:int = 490
    Y_MOTOR_RMS_CURRENT_mA:int = 490
    Z_MOTOR_RMS_CURRENT_mA:int = 490

    X_MOTOR_I_HOLD:ClosedRange[float](0.0,1.0) = 0.5
    Y_MOTOR_I_HOLD:ClosedRange[float](0.0,1.0) = 0.5
    Z_MOTOR_I_HOLD:ClosedRange[float](0.0,1.0) = 0.5

    MAX_VELOCITY_X_mm:float = 25.0
    MAX_VELOCITY_Y_mm:float = 25.0
    MAX_VELOCITY_Z_mm:float = 2.0

    MAX_ACCELERATION_X_mm:float = 500.0
    MAX_ACCELERATION_Y_mm:float = 500.0
    MAX_ACCELERATION_Z_mm:float = 20.0

    # end of actuator specific configurations

    SCAN_STABILIZATION_TIME_MS_X:float = 160.0
    SCAN_STABILIZATION_TIME_MS_Y:float = 160.0
    SCAN_STABILIZATION_TIME_MS_Z:float = 20.0

    # limit switch
    X_HOME_SWITCH_POLARITY:int = LIMIT_SWITCH_POLARITY.ACTIVE_HIGH
    Y_HOME_SWITCH_POLARITY:int = LIMIT_SWITCH_POLARITY.ACTIVE_HIGH
    Z_HOME_SWITCH_POLARITY:int = LIMIT_SWITCH_POLARITY.ACTIVE_LOW

    HOMING_ENABLED_X:bool = True
    HOMING_ENABLED_Y:bool = True
    HOMING_ENABLED_Z:bool = False

    SLEEP_TIME_S:float = 0.005

    LED_MATRIX_R_FACTOR:int = 1
    LED_MATRIX_G_FACTOR:int = 1
    LED_MATRIX_B_FACTOR:int = 1

    DEFAULT_SAVING_PATH:str = field(default_factory=lambda:str(Path.home()/"Downloads"))

    # image display crop size 
    DEFAULT_DISPLAY_CROP:ClosedRange[int](1,100) = 100

    CAMERA_PIXEL_SIZE_UM:Dict[str,float]=field(default_factory=lambda:{
        'IMX290':    2.9,
        'IMX178':    2.4,
        'IMX226':    1.85,
        'IMX250':    3.45,
        'IMX252':    3.45,
        'IMX273':    3.45,
        'IMX264':    3.45,
        'IMX265':    3.45,
        'IMX571':    3.76,
        'PYTHON300': 4.8
    })

    OBJECTIVES:Dict[str,ObjectiveData] = field(default_factory=lambda: {
        '2x':ObjectiveData(
            magnification=2,
            NA=0.10,
            tube_lens_f_mm=180
        ),
        '4x':ObjectiveData(
            magnification=4,
            NA=0.13,
            tube_lens_f_mm=180
        ),
        '10x':ObjectiveData(
            magnification=10,
            NA=0.25,
            tube_lens_f_mm=180
        ),
        '10x (Mitutoyo)':ObjectiveData(
            magnification=10,
            NA=0.25,
            tube_lens_f_mm=200
        ),
        '20x (Boli)':ObjectiveData(
            magnification=20,
            NA=0.4,
            tube_lens_f_mm=180
        ),
        '20x (Nikon)':ObjectiveData(
            magnification=20,
            NA=0.45,
            tube_lens_f_mm=200
        ),
        '40x':ObjectiveData(
            magnification=40,
            NA=0.6,
            tube_lens_f_mm=180
        )
    })

    TUBE_LENS_MM:float = 50.0
    CAMERA_SENSOR:str = 'IMX226'
    TRACKERS:List[str] = field(default_factory= lambda:['csrt', 'kcf', 'mil', 'tld', 'medianflow','mosse','daSiamRPN'])
    DEFAULT_TRACKER:ClosedSet[str]('csrt', 'kcf', 'mil', 'tld', 'medianflow','mosse','daSiamRPN') = 'csrt'

    AF:AutofocusConfig=field(default_factory=lambda: AutofocusConfig())

    SHOW_DAC_CONTROL:bool = False

    class SLIDE_POSITION:
        LOADING_X_MM:float = 30
        LOADING_Y_MM:float = 55
        SCANNING_X_MM:float = 3
        SCANNING_Y_MM:float = 3

    SLIDE_POTISION_SWITCHING_TIMEOUT_LIMIT_S:float = 10.0
    SLIDE_POTISION_SWITCHING_HOME_EVERYTIME:bool = False

    SOFTWARE_POS_LIMIT:SoftwareStagePositionLimits=field(default=SoftwareStagePositionLimits())

    SHOW_AUTOLEVEL_BTN:bool = False

    CAMERA_SN:Dict[str,str] = field(default_factory=lambda:{'ch 1':'SN1','ch 2': 'SN2'}) # for multiple cameras, to be overwritten in the configuration file

    ENABLE_STROBE_OUTPUT:bool = False

    Z_STACKING_CONFIG:ClosedSet[str]('FROM CENTER', 'FROM BOTTOM', 'FROM TOP') = 'FROM CENTER'

    # for 384 well plate
    X_MM_384_WELLPLATE_UPPERLEFT:float = 0.0
    Y_MM_384_WELLPLATE_UPPERLEFT:float = 0.0
    DEFAULT_Z_POS_MM:float = 2.0
    X_ORIGIN_384_WELLPLATE_PIXEL:int = 177 # upper left of B2 (corner opposite from clamp)
    Y_ORIGIN_384_WELLPLATE_PIXEL:int = 141 # upper left of B2 (corner opposite from clamp)
    # B1 upper left corner in pixel: x = 124, y = 141
    # B1 upper left corner in mm: x = 12.13 mm - 3.3 mm/2, y = 8.99 mm + 4.5 mm - 3.3 mm/2
    # B2 upper left corner in pixel: x = 177, y = 141

    WELLPLATE_OFFSET_X_mm:float = 0.0 # x offset adjustment for using different plates
    WELLPLATE_OFFSET_Y_mm:float = 0.0 # y offset adjustment for using different plates

    FOCUS_MEASURE_OPERATOR:str = field(default=FocusMeasureOperators.LAPE)

    CONTROLLER_VERSION:str = ControllerType.TEENSY

    MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT:bool = True

    # things that can change in hardware (manual changes)

    DEFAULT_OBJECTIVE:str = '10x (Mitutoyo)'
    # default plate format
    WELLPLATE_FORMAT:ClosedSet[int](6,12,24,96,384) = 384

    # things that can change in software
    DEFAULT_TRIGGER_MODE:ClosedSet[str]('Software Trigger','Hardware Trigger','Continuous Acqusition') = TriggerMode.SOFTWARE
    AUTOLEVEL_DEFAULT_SETTING:bool = False

    MULTIPOINT_AUTOFOCUS_CHANNEL:str = 'BF LED matrix full'
    MULTIPOINT_BF_SAVING_OPTION:ClosedSet[str]('Raw','RGB2GRAY','Green Channel Only') = 'Raw'


MACHINE_CONFIG=MachineConfiguration(
    FLIP_IMAGE = 'Vertical',

    # beginning of actuator specific configurations

    SCREW_PITCH_X_MM = 2.54,
    SCREW_PITCH_Y_MM = 2.54,
    SCREW_PITCH_Z_MM = 0.3,

    MICROSTEPPING_DEFAULT_X = 256,
    MICROSTEPPING_DEFAULT_Y = 256,
    MICROSTEPPING_DEFAULT_Z = 256,
    MICROSTEPPING_DEFAULT_THETA = 256,

    X_MOTOR_RMS_CURRENT_mA = 1000,
    Y_MOTOR_RMS_CURRENT_mA = 1000,
    Z_MOTOR_RMS_CURRENT_mA = 500,

    X_MOTOR_I_HOLD = 0.25,
    Y_MOTOR_I_HOLD = 0.25,
    Z_MOTOR_I_HOLD = 0.5,

    MAX_VELOCITY_X_mm = 40.0,
    MAX_VELOCITY_Y_mm = 40.0,
    MAX_VELOCITY_Z_mm = 2.0,

    MAX_ACCELERATION_X_mm = 500.0,
    MAX_ACCELERATION_Y_mm = 500.0,
    MAX_ACCELERATION_Z_mm = 100.0,

    # end of actuator specific configurations

    SCAN_STABILIZATION_TIME_MS_X = 160.0,
    SCAN_STABILIZATION_TIME_MS_Y = 160.0,
    SCAN_STABILIZATION_TIME_MS_Z = 20.0,

    HOMING_ENABLED_X = True,
    HOMING_ENABLED_Y = True,
    HOMING_ENABLED_Z = True,

    SLEEP_TIME_S = 0.005,

    DEFAULT_SAVING_PATH = str(Path.home() / "Downloads"),

    # multipoint acquisition settings
    MULTIPOINT_AUTOFOCUS_CHANNEL = 'Fluorescence 561 nm Ex',
    MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT = True,
    MULTIPOINT_BF_SAVING_OPTION = 'Green Channel Only',

    TUBE_LENS_MM = 50.0,
    CAMERA_SENSOR = 'IMX226',
    DEFAULT_OBJECTIVE = '10x (Mitutoyo)',

    SOFTWARE_POS_LIMIT=SoftwareStagePositionLimits(
        X_POSITIVE = 112.5,
        X_NEGATIVE = 10,
        Y_POSITIVE = 76,
        Y_NEGATIVE = 6,
        Z_POSITIVE = 6
    ),
        
    # for 384 well plate
    X_MM_384_WELLPLATE_UPPERLEFT = 13.36,
    Y_MM_384_WELLPLATE_UPPERLEFT = 11.28,

    # for other plate format
    WELLPLATE_OFFSET_X_mm = 0.0,
    WELLPLATE_OFFSET_Y_mm = 0.0,

    # default z
    DEFAULT_Z_POS_MM = 4.677,

    # well plate format selection
    WELLPLATE_FORMAT = 96,

    FOCUS_MEASURE_OPERATOR = FocusMeasureOperators.GLVA,
    CONTROLLER_VERSION = ControllerType.TEENSY,
)

##########################################################
#### start of loading machine specific configurations ####
##########################################################
#config_files = glob.glob('.' + '/' + 'configuration*.txt')
#if config_files:
#    if len(config_files) > 1:
#        print('multiple machine configuration files found, the program will exit')
#        exit()
#    print('load machine-specific configuration')
#    exec(open(config_files[0]).read())
#else:
#    print('machine-specifc configuration not present, the program will exit')
#    exit()
##########################################################
##### end of loading machine specific configurations #####
##########################################################

@dataclass(frozen=True)
class WellplateFormatPhysical:
    """ physical (and logical) well plate layout """
    well_size_mm:float
    well_spacing_mm:float
    A1_x_mm:float
    A1_y_mm:float
    """ layers of disabled outer wells """
    number_of_skip:int
    rows:int
    columns:int
 
WELLPLATE_FORMATS={
    6:WellplateFormatPhysical(
        well_size_mm = 34.94,
        well_spacing_mm = 39.2,
        A1_x_mm = 24.55,
        A1_y_mm = 23.01,
        number_of_skip = 0,
        rows = 2,
        columns = 3,
    ),
    12:WellplateFormatPhysical(
        well_size_mm = 22.05,
        well_spacing_mm = 26,
        A1_x_mm = 24.75,
        A1_y_mm = 16.86,
        number_of_skip = 0,
        rows = 3,
        columns = 4,
    ),
    24:WellplateFormatPhysical(
        well_size_mm = 15.54,
        well_spacing_mm = 19.3,
        A1_x_mm = 17.05,
        A1_y_mm = 13.67,
        number_of_skip = 0,
        rows = 4,
        columns = 6,
    ),
    96:WellplateFormatPhysical(
        well_size_mm = 6.21,
        well_spacing_mm = 9,
        A1_x_mm = 14.3,
        A1_y_mm = 11.36,
        number_of_skip = 0,
        rows = 8,
        columns = 12,
    ),
    384:WellplateFormatPhysical(
        well_size_mm = 3.3,
        well_spacing_mm = 4.5,
        A1_x_mm = 12.05,
        A1_y_mm = 9.05,
        number_of_skip = 1,
        rows = 16,
        columns = 24,
    )
}
 