from dataclasses import dataclass, field
import json
from pathlib import Path
from enum import Enum

from typing import Optional, Dict, List, ClassVar, Any, Tuple

from control.typechecker import TypecheckClass, ClosedRange, ClosedSet, TypecheckFunction
from qtpy.QtCore import Signal, QObject

class TriggerMode(str,Enum):
    SOFTWARE = 'Software Trigger'
    HARDWARE = 'Hardware Trigger'
    CONTINUOUS = 'Continuous Acqusition'

class ImageFormat(Enum):
    BMP=0
    TIFF=1
    TIFF_COMPRESSED=2

class Acquisition:
    """ config stuff for (multi point) image acquisition """
    
    CROP_WIDTH:int = 3000
    """ crop width for images after recording from camera sensor """
    CROP_HEIGHT:int = 3000
    """ crop height for images after recording from camera sensor """
    NUMBER_OF_FOVS_PER_AF:int = 3
    IMAGE_FORMAT:ImageFormat = ImageFormat.TIFF
    """ file format used for images saved after multi point image acquisition """
    IMAGE_DISPLAY_SCALING_FACTOR:ClosedRange[float](0.0,1.0) = 1.0
    """ this _crops_ the image display for the multi point acquisition """

class DefaultMultiPointGrid:
    """ multi point grid defaults """

    DEFAULT_Nx:int = 1
    DEFAULT_Ny:int = 1
    DEFAULT_Nz:int = 1
    DEFAULT_Nt:int = 1

    DEFAULT_DX_MM:float = 0.9
    DEFAULT_DY_MM:float = 0.9
    DEFAULT_DZ_MM:float = 1.5e3
    DEFAULT_DT_S:float = 1.0

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
    SEND_HARDWARE_TRIGGER = 30
    SET_STROBE_DELAY = 31
    SET_PIN_LEVEL = 41
    INITIALIZE = 254
    RESET = 255

class CMD_SET2: # enum
    ANALOG_WRITE_DAC8050X:int = 0
    SET_CAMERA_TRIGGER_FREQUENCY:int = 1
    START_CAMERA_TRIGGERING:int = 2
    STOP_CAMERA_TRIGGERING:int = 3

BIT_POS_JOYSTICK_BUTTON = 0
BIT_POS_SWITCH = 1

class HOME_OR_ZERO: # enum
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

class LIMIT_SWITCH_POLARITY: # enum
    ACTIVE_LOW:int = 0
    ACTIVE_HIGH:int = 1
    DISABLED:int = 2

class ILLUMINATION_CODE: # enum
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

class CMD_EXECUTION_STATUS: # enum
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
    # limits that have popped up in other places (X_POSITIVE:float = 56, X_NEGATIVE:float = -0.5, Y_POSITIVE:float = 56, Y_NEGATIVE:float = -0.5) are likely used for another stage type!
    X_POSITIVE:float = 112.5
    X_NEGATIVE:float = 10
    Y_POSITIVE:float = 76
    Y_NEGATIVE:float = 6
    Z_POSITIVE:float = 10

class FocusMeasureOperators(str,Enum):
    """ focus measure operators - GLVA has worked well for darkfield/fluorescence, and LAPE has worked well for brightfield """
    GLVA="GLVA"
    LAPE="LAPE"

class ControllerType(str,Enum):
    DUE='Arduino Due'
    TEENSY='Teensy'

class BrightfieldSavingMode(str,Enum):
    RAW='Raw'
    RGB2GRAY='RGB2GRAY'
    GREEN_ONLY='Green Channel Only'

###########################################################
#### machine specific configurations - to be overridden ###
###########################################################

@TypecheckClass
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

    SCREW_PITCH_X_MM:float = 2.54
    SCREW_PITCH_Y_MM:float = 2.54
    SCREW_PITCH_Z_MM:float = 0.3 # 0.012*25.4 was written here at some point, not sure why. the motor makes _the_ weird noise during homing when set to the latter term, instead of 0.3

    MICROSTEPPING_DEFAULT_X:int = 256
    MICROSTEPPING_DEFAULT_Y:int = 256
    MICROSTEPPING_DEFAULT_Z:int = 256
    MICROSTEPPING_DEFAULT_THETA:int = 256

    X_MOTOR_RMS_CURRENT_mA:int = 1000
    Y_MOTOR_RMS_CURRENT_mA:int = 1000
    Z_MOTOR_RMS_CURRENT_mA:int = 500

    X_MOTOR_I_HOLD:ClosedRange[float](0.0,1.0) = 0.25
    Y_MOTOR_I_HOLD:ClosedRange[float](0.0,1.0) = 0.25
    Z_MOTOR_I_HOLD:ClosedRange[float](0.0,1.0) = 0.5

    MAX_VELOCITY_X_mm:float = 40.0
    MAX_VELOCITY_Y_mm:float = 40.0
    MAX_VELOCITY_Z_mm:float = 2.0

    MAX_ACCELERATION_X_mm:float = 500.0
    MAX_ACCELERATION_Y_mm:float = 500.0
    MAX_ACCELERATION_Z_mm:float = 100.0

    # end of actuator specific configurations

    SCAN_STABILIZATION_TIME_MS_X:float = 160.0
    SCAN_STABILIZATION_TIME_MS_Y:float = 160.0
    SCAN_STABILIZATION_TIME_MS_Z:float = 20.0

    # limit switch
    X_HOME_SWITCH_POLARITY:int = LIMIT_SWITCH_POLARITY.ACTIVE_HIGH
    Y_HOME_SWITCH_POLARITY:int = LIMIT_SWITCH_POLARITY.ACTIVE_HIGH
    Z_HOME_SWITCH_POLARITY:int = LIMIT_SWITCH_POLARITY.ACTIVE_LOW

    HOMING_ENABLED_X:bool = False
    HOMING_ENABLED_Y:bool = False
    HOMING_ENABLED_Z:bool = False

    SLEEP_TIME_S:float = 0.005

    LED_MATRIX_R_FACTOR:int = 1
    LED_MATRIX_G_FACTOR:int = 1
    LED_MATRIX_B_FACTOR:int = 1

    CAMERA_PIXEL_SIZE_UM:ClassVar[Dict[str,float]]={
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
    }

    OBJECTIVES:ClassVar[Dict[str,ObjectiveData]]={
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
    }

    TUBE_LENS_MM:float = 50.0
    CAMERA_SENSOR:str = 'IMX226'

    TRACKERS:ClassVar[List[str]] = ['csrt', 'kcf', 'mil', 'tld', 'medianflow','mosse','daSiamRPN']
    DEFAULT_TRACKER:ClosedSet[str]('csrt', 'kcf', 'mil', 'tld', 'medianflow','mosse','daSiamRPN') = 'csrt'

    AF:AutofocusConfig=AutofocusConfig()

    SOFTWARE_POS_LIMIT:SoftwareStagePositionLimits=SoftwareStagePositionLimits(
        X_POSITIVE = 112.5,
        X_NEGATIVE = 10,
        Y_POSITIVE = 76,
        Y_NEGATIVE = 6,
        Z_POSITIVE = 6
    )

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

    CONTROLLER_VERSION:ControllerType = ControllerType.TEENSY

    MAIN_CAMERA_MODEL:str="MER2-1220-32U3M"
    FOCUS_CAMERA_MODEL:str="MER2-630-60U3M"

    FOCUS_CAMERA_EXPOSURE_TIME_MS:float = 2.0
    FOCUS_CAMERA_ANALOG_GAIN:float = 0.0
    LASER_AF_AVERAGING_N_PRECISE:int = 5
    LASER_AF_AVERAGING_N_FAST:int = 2
    LASER_AF_DISPLAY_SPOT_IMAGE:bool = False # display laser af image every time when displacement is measured (even in multi point acquisition mode)
    LASER_AF_CROP_WIDTH:int = 1536
    LASER_AF_CROP_HEIGHT:int = 256
    HAS_TWO_INTERFACES:bool = True
    USE_GLASS_TOP:bool = True
    SHOW_LEGACY_DISPLACEMENT_MEASUREMENT_WINDOWS:bool = False
    LASER_AUTOFOCUS_TARGET_MOVE_THRESHOLD_UM:float = 0.3 # when moving to target, if absolute measured displacement after movement is larger than this value, repeat move to target (repeat max once) - note that the usual um/pixel value is 0.4
    LASER_AUTOFOCUS_MOVEMENT_BOUNDARY_LOWER:float=-200.0 # when moving to target, no matter the measured displacement, move not further away from the current position than this value
    LASER_AUTOFOCUS_MOVEMENT_BOUNDARY_UPPER:float=200.0 # when moving to target, no matter the measured displacement, move not further away from the current position than this value

    MULTIPOINT_REFLECTION_AUTOFOCUS_ENABLE_BY_DEFAULT:bool = False

    DEFAULT_TRIGGER_FPS:float=5.0

    def from_json(filename:str):
        try:
            with open(filename,"r",encoding="utf-8") as json_file:
                kwargs=json.decoder.JSONDecoder().decode(json_file.read())

        except FileNotFoundError:
            kwargs={}

        return MachineConfiguration(**kwargs)


@TypecheckClass(check_assignment=True)
class MutableMachineConfiguration(QObject):
    # things that can change in hardware (manual changes)
    DEFAULT_OBJECTIVE:str = '10x (Mitutoyo)'
    WELLPLATE_FORMAT:ClosedSet[int](6,12,24,96,384) = 96

    # things that can change in software
    DEFAULT_TRIGGER_MODE:TriggerMode = TriggerMode.SOFTWARE
    FOCUS_MEASURE_OPERATOR:FocusMeasureOperators = FocusMeasureOperators.LAPE
    MULTIPOINT_AUTOFOCUS_CHANNEL:str = 'Fluorescence 561 nm Ex'
    MULTIPOINT_BF_SAVING_OPTION:BrightfieldSavingMode = BrightfieldSavingMode.RAW

    objective_change:Signal=Signal(str)
    wellplate_format_change:Signal=Signal(int)
    trigger_mode_change:Signal=Signal(TriggerMode)
    focuse_measure_operator_change:Signal=Signal(FocusMeasureOperators)
    autofocus_channel_change:Signal=Signal(str)
    brightfield_saving_mode_change:Signal=Signal(BrightfieldSavingMode)

    def __setattr__(self,name,value):
        {
            "DEFAULT_OBJECTIVE":self.objective_change,
            "WELLPLATE_FORMAT":self.wellplate_format_change,
            "DEFAULT_TRIGGER_MODE":self.trigger_mode_change,
            "FOCUS_MEASURE_OPERATOR":self.focuse_measure_operator_change,
            "MULTIPOINT_AUTOFOCUS_CHANNEL":self.autofocus_channel_change,
            "MULTIPOINT_BF_SAVING_OPTION":self.brightfield_saving_mode_change,
        }[name].emit(value)
        super().__setattr__(name,value)

    def from_json(filename:str):
        try:
            with open(filename,"r",encoding="utf-8") as json_file:
                kwargs=json.decoder.JSONDecoder().decode(json_file.read())

        except FileNotFoundError:
            kwargs={}

        return MutableMachineConfiguration(**kwargs)

@TypecheckClass
class MachineDisplayConfiguration:
    """ display settings """
    DEFAULT_SAVING_PATH:str = str(Path.home()/"Downloads")
    DEFAULT_DISPLAY_CROP:ClosedRange[int](1,100) = 100
    MULTIPOINT_SOFTWARE_AUTOFOCUS_ENABLE_BY_DEFAULT:bool = False
    MULTIPOINT_LASER_AUTOFOCUS_ENABLE_BY_DEFAULT:bool = True

    def from_json(filename:str):
        try:
            with open(filename,"r",encoding="utf-8") as json_file:
                kwargs=json.decoder.JSONDecoder().decode(json_file.read())

        except FileNotFoundError:
            kwargs={}

        return MachineDisplayConfiguration(**kwargs)


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

    @TypecheckFunction
    def convert_well_index(self,row:int,column:int)->Tuple[float,float]:
        wellplate_format_384=WELLPLATE_FORMATS[384]

        # offset for coordinate origin, required because origin was calibrated based on 384 wellplate, i guess. 
        # term in parenthesis is required because A1_x/y_mm actually referes to upper left corner of B2, not A1 (also assumes that number_of_skip==1)
        assert wellplate_format_384.number_of_skip==1
        origin_x_offset=MACHINE_CONFIG.X_MM_384_WELLPLATE_UPPERLEFT-(wellplate_format_384.A1_x_mm + wellplate_format_384.well_spacing_mm * wellplate_format_384.number_of_skip)
        origin_y_offset=MACHINE_CONFIG.Y_MM_384_WELLPLATE_UPPERLEFT-(wellplate_format_384.A1_y_mm + wellplate_format_384.well_spacing_mm * wellplate_format_384.number_of_skip)

        # physical position of the well on the wellplate that the cursor should move to
        well_on_plate_offset_x=column * self.well_spacing_mm + self.A1_x_mm
        well_on_plate_offset_y=row * self.well_spacing_mm + self.A1_y_mm

        # offset from top left of well to position within well where cursor/camera should go
        # should be centered, so offset is same in x and y
        well_cursor_offset_x=wellplate_format_384.well_size_mm/2
        well_cursor_offset_y=well_cursor_offset_x

        x_mm = origin_x_offset + MACHINE_CONFIG.WELLPLATE_OFFSET_X_mm \
            + well_on_plate_offset_x + well_cursor_offset_x
        y_mm = origin_y_offset + MACHINE_CONFIG.WELLPLATE_OFFSET_Y_mm \
            + well_on_plate_offset_y + well_cursor_offset_y

        return (x_mm,y_mm)

    @TypecheckFunction
    def well_name(self,row:int,column:int)->str:
        return chr(ord('A')+row)+f'{column+1:02}' # A01


WELLPLATE_FORMATS:Dict[int,WellplateFormatPhysical]={
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
WELLPLATE_NAMES:Dict[int,str]={
    i:f"{i} well plate"
    for i in WELLPLATE_FORMATS.keys()
}

MACHINE_CONFIG=MachineConfiguration.from_json("machine_config.json")

MACHINE_DISPLAY_CONFIG=MachineDisplayConfiguration.from_json("display_config.json")

MUTABLE_MACHINE_CONFIG=MutableMachineConfiguration.from_json("default_mutable_machine_config.json")
