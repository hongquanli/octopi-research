#!/usr/bin/env python
# coding: utf-8
'''
Created on 2023-12-12
@author:fdy
'''

import ctypes
from ctypes import *
from enum import Enum
import time

#加载SDK动态库
# 32bit
#TUSDKdll = OleDLL("./lib/x86/TUCam.dll")
# 64bit
TUSDKdll = cdll.LoadLibrary("libTUCam.so.1")

#  class typedef enum TUCAM status:
class TUCAMRET(Enum):
    TUCAMRET_SUCCESS          = 0x00000001
    TUCAMRET_FAILURE          = 0x80000000

    # initialization error
    TUCAMRET_NO_MEMORY        = 0x80000101
    TUCAMRET_NO_RESOURCE      = 0x80000102
    TUCAMRET_NO_MODULE        = 0x80000103
    TUCAMRET_NO_DRIVER        = 0x80000104
    TUCAMRET_NO_CAMERA        = 0x80000105
    TUCAMRET_NO_GRABBER       = 0x80000106
    TUCAMRET_NO_PROPERTY      = 0x80000107

    TUCAMRET_FAILOPEN_CAMERA  = 0x80000110
    TUCAMRET_FAILOPEN_BULKIN  = 0x80000111
    TUCAMRET_FAILOPEN_BULKOUT = 0x80000112
    TUCAMRET_FAILOPEN_CONTROL = 0x80000113
    TUCAMRET_FAILCLOSE_CAMERA = 0x80000114

    TUCAMRET_FAILOPEN_FILE    = 0x80000115
    TUCAMRET_FAILOPEN_CODEC   = 0x80000116
    TUCAMRET_FAILOPEN_CONTEXT = 0x80000117

    # status error
    TUCAMRET_INIT             = 0x80000201
    TUCAMRET_BUSY             = 0x80000202
    TUCAMRET_NOT_INIT         = 0x80000203
    TUCAMRET_EXCLUDED         = 0x80000204
    TUCAMRET_NOT_BUSY         = 0x80000205
    TUCAMRET_NOT_READY        = 0x80000206
    # wait error
    TUCAMRET_ABORT            = 0x80000207
    TUCAMRET_TIMEOUT          = 0x80000208
    TUCAMRET_LOSTFRAME        = 0x80000209
    TUCAMRET_MISSFRAME        = 0x8000020A
    TUCAMRET_USB_STATUS_ERROR = 0x8000020B

    # calling error
    TUCAMRET_INVALID_CAMERA   = 0x80000301
    TUCAMRET_INVALID_HANDLE   = 0x80000302
    TUCAMRET_INVALID_OPTION   = 0x80000303
    TUCAMRET_INVALID_IDPROP   = 0x80000304
    TUCAMRET_INVALID_IDCAPA   = 0x80000305
    TUCAMRET_INVALID_IDPARAM  = 0x80000306
    TUCAMRET_INVALID_PARAM    = 0x80000307
    TUCAMRET_INVALID_FRAMEIDX = 0x80000308
    TUCAMRET_INVALID_VALUE    = 0x80000309
    TUCAMRET_INVALID_EQUAL    = 0x8000030A
    TUCAMRET_INVALID_CHANNEL  = 0x8000030B
    TUCAMRET_INVALID_SUBARRAY = 0x8000030C
    TUCAMRET_INVALID_VIEW     = 0x8000030D
    TUCAMRET_INVALID_PATH     = 0x8000030E
    TUCAMRET_INVALID_IDVPROP  = 0x8000030F

    TUCAMRET_NO_VALUETEXT     = 0x80000310
    TUCAMRET_OUT_OF_RANGE     = 0x80000311

    TUCAMRET_NOT_SUPPORT      = 0x80000312
    TUCAMRET_NOT_WRITABLE     = 0x80000313
    TUCAMRET_NOT_READABLE     = 0x80000314

    TUCAMRET_WRONG_HANDSHAKE  = 0x80000410
    TUCAMRET_NEWAPI_REQUIRED  = 0x80000411

    TUCAMRET_ACCESSDENY       = 0x80000412

    TUCAMRET_NO_CORRECTIONDATA = 0x80000501

    TUCAMRET_INVALID_PRFSETS   = 0x80000601
    TUCAMRET_INVALID_IDPPROP   = 0x80000602

    TUCAMRET_DECODE_FAILURE    = 0x80000701
    TUCAMRET_COPYDATA_FAILURE  = 0x80000702
    TUCAMRET_ENCODE_FAILURE    = 0x80000703
    TUCAMRET_WRITE_FAILURE     = 0x80000704

    # camera or bus trouble
    TUCAMRET_FAIL_READ_CAMERA  = 0x83001001
    TUCAMRET_FAIL_WRITE_CAMERA = 0x83001002
    TUCAMRET_OPTICS_UNPLUGGED  = 0x83001003

    TUCAMRET_RECEIVE_FINISH    = 0x00000002
    TUCAMRET_EXTERNAL_TRIGGER  = 0x00000003

# typedef enum information id
class TUCAM_IDINFO(Enum):
    TUIDI_BUS                = 0x01
    TUIDI_VENDOR             = 0x02
    TUIDI_PRODUCT            = 0x03
    TUIDI_VERSION_API        = 0x04
    TUIDI_VERSION_FRMW       = 0x05
    TUIDI_VERSION_FPGA       = 0x06
    TUIDI_VERSION_DRIVER     = 0x07
    TUIDI_TRANSFER_RATE      = 0x08
    TUIDI_CAMERA_MODEL       = 0x09
    TUIDI_CURRENT_WIDTH      = 0x0A
    TUIDI_CURRENT_HEIGHT     = 0x0B
    TUIDI_CAMERA_CHANNELS    = 0x0C
    TUIDI_BCDDEVICE          = 0x0D
    TUIDI_TEMPALARMFLAG      = 0x0E
    TUIDI_UTCTIME            = 0x0F
    TUIDI_LONGITUDE_LATITUDE = 0x10
    TUIDI_WORKING_TIME       = 0x11
    TUIDI_FAN_SPEED          = 0x12
    TUIDI_FPGA_TEMPERATURE   = 0x13
    TUIDI_PCBA_TEMPERATURE   = 0x14
    TUIDI_ENV_TEMPERATURE    = 0x15
    TUIDI_DEVICE_ADDRESS     = 0x16
    TUIDI_USB_PORT_ID        = 0x17
    TUIDI_CONNECTSTATUS      = 0x18
    TUIDI_TOTALBUFFRAMES     = 0x19
    TUIDI_CURRENTBUFFRAMES   = 0x1A
    TUIDI_HDRRATIO           = 0x1B
    TUIDI_HDRKHVALUE         = 0x1C
    TUIDI_ZEROTEMPERATURE_VALUE = 0x1D
    TUIDI_ENDINFO            = 0x1F

# typedef enum capability id
class TUCAM_IDCAPA(Enum):
    TUIDC_RESOLUTION = 0x00
    TUIDC_PIXELCLOCK = 0x01
    TUIDC_BITOFDEPTH = 0x02
    TUIDC_ATEXPOSURE = 0x03
    TUIDC_HORIZONTAL = 0x04
    TUIDC_VERTICAL   = 0x05
    TUIDC_ATWBALANCE = 0x06
    TUIDC_FAN_GEAR   = 0x07
    TUIDC_ATLEVELS   = 0x08
    TUIDC_SHIFT      = 0x09
    TUIDC_HISTC      = 0x0A
    TUIDC_CHANNELS   = 0x0B
    TUIDC_ENHANCE    = 0x0C
    TUIDC_DFTCORRECTION = 0x0D
    TUIDC_ENABLEDENOISE = 0x0E
    TUIDC_FLTCORRECTION = 0x0F
    TUIDC_RESTARTLONGTM = 0x10
    TUIDC_DATAFORMAT    = 0x11
    TUIDC_DRCORRECTION  = 0x12
    TUIDC_VERCORRECTION = 0x13
    TUIDC_MONOCHROME    = 0x14
    TUIDC_BLACKBALANCE  = 0x15
    TUIDC_IMGMODESELECT = 0x16
    TUIDC_CAM_MULTIPLE  = 0x17
    TUIDC_ENABLEPOWEEFREQUENCY = 0x18
    TUIDC_ROTATE_R90   = 0x19
    TUIDC_ROTATE_L90   = 0x1A
    TUIDC_NEGATIVE     = 0x1B
    TUIDC_HDR          = 0x1C
    TUIDC_ENABLEIMGPRO = 0x1D
    TUIDC_ENABLELED    = 0x1E
    TUIDC_ENABLETIMESTAMP  = 0x1F
    TUIDC_ENABLEBLACKLEVEL = 0x20
    TUIDC_ATFOCUS          = 0x21
    TUIDC_ATFOCUS_STATUS   = 0x22
    TUIDC_PGAGAIN          = 0x23
    TUIDC_ATEXPOSURE_MODE  = 0x24
    TUIDC_BINNING_SUM      = 0x25
    TUIDC_BINNING_AVG      = 0x26
    TUIDC_FOCUS_C_MOUNT    = 0x27
    TUIDC_ENABLEPI          = 0x28
    TUIDC_ATEXPOSURE_STATUS = 0x29
    TUIDC_ATWBALANCE_STATUS = 0x2A
    TUIDC_TESTIMGMODE       = 0x2B
    TUIDC_SENSORRESET       = 0x2C
    TUIDC_PGAHIGH           = 0x2D
    TUIDC_PGALOW            = 0x2E
    TUIDC_PIXCLK1_EN        = 0x2F
    TUIDC_PIXCLK2_EN        = 0x30
    TUIDC_ATLEVELGEAR       = 0x31
    TUIDC_ENABLEDSNU        = 0x32
    TUIDC_ENABLEOVERLAP     = 0x33
    TUIDC_CAMSTATE          = 0x34
    TUIDC_ENABLETRIOUT      = 0x35
    TUIDC_ROLLINGSCANMODE   = 0x36
    TUIDC_ROLLINGSCANLTD    = 0x37
    TUIDC_ROLLINGSCANSLIT   = 0x38
    TUIDC_ROLLINGSCANDIR    = 0x39
    TUIDC_ROLLINGSCANRESET  = 0x3A
    TUIDC_ENABLETEC         = 0x3B
    TUIDC_ENABLEBLC         = 0x3C
    TUIDC_ENABLETHROUGHFOG  = 0x3D
    TUIDC_ENABLEGAMMA       = 0x3E
    TUIDC_ENABLEFILTER      = 0x3F
    TUIDC_ENABLEHLC         = 0x40
    TUIDC_CAMPARASAVE       = 0x41
    TUIDC_CAMPARALOAD       = 0x42
    TUIDC_ENABLEISP         = 0x43
    TUIDC_BUFFERHEIGHT      = 0x44
    TUIDC_VISIBILITY        = 0x45
    TUIDC_SHUTTER           = 0x46
    TUIDC_SIGNALFILTER      = 0x47
    TUIDC_ENDCAPABILITY     = 0x48


# typedef enum property id
class TUCAM_IDPROP(Enum):
    TUIDP_GLOBALGAIN  = 0x00
    TUIDP_EXPOSURETM  = 0x01
    TUIDP_BRIGHTNESS  = 0x02
    TUIDP_BLACKLEVEL  = 0x03
    TUIDP_TEMPERATURE = 0x04
    TUIDP_SHARPNESS   = 0x05
    TUIDP_NOISELEVEL  = 0x06
    TUIDP_HDR_KVALUE  = 0x07

    # image process property
    TUIDP_GAMMA       = 0x08
    TUIDP_CONTRAST    = 0x09
    TUIDP_LFTLEVELS   = 0x0A
    TUIDP_RGTLEVELS   = 0x0B
    TUIDP_CHNLGAIN    = 0x0C
    TUIDP_SATURATION  = 0x0D
    TUIDP_CLRTEMPERATURE   = 0x0E
    TUIDP_CLRMATRIX        = 0x0F
    TUIDP_DPCLEVEL         = 0x10
    TUIDP_BLACKLEVELHG     = 0x11
    TUIDP_BLACKLEVELLG     = 0x12
    TUIDP_POWEEFREQUENCY   = 0x13
    TUIDP_HUE              = 0x14
    TUIDP_LIGHT            = 0x15
    TUIDP_ENHANCE_STRENGTH = 0x16
    TUIDP_NOISELEVEL_3D    = 0x17
    TUIDP_FOCUS_POSITION   = 0x18

    TUIDP_FRAME_RATE       = 0x19
    TUIDP_START_TIME       = 0x1A
    TUIDP_FRAME_NUMBER     = 0x1B
    TUIDP_INTERVAL_TIME    = 0x1C
    TUIDP_GPS_APPLY        = 0x1D
    TUIDP_AMB_TEMPERATURE  = 0x1E
    TUIDP_AMB_HUMIDITY     = 0x1F
    TUIDP_AUTO_CTRLTEMP    = 0x20

    TUIDP_AVERAGEGRAY      = 0x21
    TUIDP_AVERAGEGRAYTHD   = 0x22
    TUIDP_ENHANCETHD       = 0x23
    TUIDP_ENHANCEPARA      = 0x24
    TUIDP_EXPOSUREMAX      = 0x25
    TUIDP_EXPOSUREMIN      = 0x26
    TUIDP_GAINMAX          = 0x27
    TUIDP_GAINMIN          = 0x28
    TUIDP_THROUGHFOGPARA   = 0x29
    TUIDP_ATLEVEL_PERCENTAGE = 0x2A
    TUIDP_TEMPERATURE_TARGET = 0x2B

    TUIDP_PIXELRATIO       = 0x2C

    TUIDP_ENDPROPERTY      = 0x2D

# typedef enum calculate roi id
class TUCAM_IDCROI(Enum):
    TUIDCR_WBALANCE   = 0x00
    TUIDCR_BBALANCE   = 0x01
    TUIDCR_BLOFFSET   = 0x02
    TUIDCR_FOCUS      = 0x03
    TUIDCR_EXPOSURETM = 0x04
    TUIDCR_END        = 0x05

# typedef enum the capture mode
class TUCAM_CAPTURE_MODES(Enum):
    TUCCM_SEQUENCE            = 0x00
    TUCCM_TRIGGER_STANDARD    = 0x01
    TUCCM_TRIGGER_SYNCHRONOUS = 0x02
    TUCCM_TRIGGER_GLOBAL      = 0x03
    TUCCM_TRIGGER_SOFTWARE    = 0x04
    TUCCM_TRIGGER_GPS         = 0x05
    TUCCM_TRIGGER_STANDARD_NONOVERLAP = 0x11

# typedef enum the image formats
class TUIMG_FORMATS(Enum):
    TUFMT_RAW = 0x01
    TUFMT_TIF = 0x02
    TUFMT_PNG = 0x04
    TUFMT_JPG = 0x08
    TUFMT_BMP = 0x10

# typedef enum the register formats
class TUREG_FORMATS(Enum):
    TUREG_SN   = 0x01
    TUREG_DATA = 0x02

# trigger mode
# typedef enum the trigger exposure time mode
class TUCAM_TRIGGER_EXP(Enum):
    TUCTE_EXPTM = 0x00
    TUCTE_WIDTH = 0x01

#  typedef enum the trigger edge mode
class TUCAM_TRIGGER_EDGE(Enum):
    TUCTD_RISING  = 0x01
    TUCTD_FAILING = 0x00

# outputtrigger mode
# typedef enum the output trigger port mode
class TUCAM_OUTPUTTRG_PORT(Enum):
    TUPORT_ONE   = 0x00
    TUPORT_TWO   = 0x01
    TUPORT_THREE = 0x02

# typedef enum the output trigger kind mode
class TUCAM_OUTPUTTRG_KIND(Enum):
    TUOPT_GND       = 0x00
    TUOPT_VCC       = 0x01
    TUOPT_IN        = 0x02
    TUOPT_EXPSTART  = 0x03
    TUOPT_EXPGLOBAL = 0x04
    TUOPT_READEND   = 0x05

# typedef enum the output trigger edge mode
class TUCAM_OUTPUTTRG_EDGE(Enum):
    TUOPT_RISING     = 0x00
    TUOPT_FAILING    = 0x01

# typedef enum the frame formats
class TUFRM_FORMATS(Enum):
    TUFRM_FMT_RAW    = 0x10
    TUFRM_FMT_USUAl  = 0x11
    TUFRM_FMT_RGB888 = 0x12

# element type
class TUELEM_TYPE(Enum):
    TU_ElemValue       = 0x00
    TU_ElemBase        = 0x01
    TU_ElemInteger     = 0x02
    TU_ElemBoolean     = 0x03
    TU_ElemCommand     = 0x04
    TU_ElemFloat       = 0x05
    TU_ElemString      = 0x06
    TU_ElemRegister    = 0x07
    TU_ElemCategory    = 0x08
    TU_ElemEnumeration = 0x09
    TU_ElemEnumEntry   = 0x0A
    TU_ElemPort        = 0x0B

# access mode of a node
class TUACCESS_MODE(Enum):
    TU_AM_NI = 0x00
    TU_AM_NA = 0x01
    TU_AM_WO = 0x02
    TU_AM_RO = 0x03
    TU_AM_RW = 0x04

class TU_VISIBILITY(Enum):
    TU_VS_Beginner            = 0x00
    TU_VS_Expert              = 0x01
    TU_VS_Guru                = 0x02
    TU_VS_Invisible           = 0x03
    TU_VS_UndefinedVisibility = 0x10

class TU_REPRESENTATION(Enum):
    TU_REPRESENTATION_LINEAR      = 0x00
    TU_REPRESENTATION_LOGARITHMIC = 0x01
    TU_REPRESENTATION_BOOLEAN     = 0x02
    TU_REPRESENTATION_PURE_NUMBER = 0x03
    TU_REPRESENTATION_HEX_NUMBER  = 0x04
    TU_REPRESENTATION_UNDEFINDED  = 0x05
    TU_REPRESENTATION_IPV4ADDRESS = 0x06
    TU_REPRESENTATION_MACADDRESS  = 0x07
    TU_REPRESENTATION_TIMESTAMP   = 0x08
    TU_REPRESENTATION_PTPFRAMECNT = 0x09

class TUXML_DEVICE(Enum):
    TU_CAMERA_XML     = 0x00
    TU_CAMERALINK_XML = 0x01

# struct defines
# the camera initialize struct
class TUCAM_INIT(Structure):
    _fields_ = [
        ("uiCamCount",     c_uint32),
        ("pstrConfigPath", c_char_p)   # c_char * 8   c_char_p
    ]
# the camera open struct
class TUCAM_OPEN(Structure):
    _fields_ = [
        ("uiIdxOpen",     c_uint32),
        ("hIdxTUCam",     c_void_p)     # ("hIdxTUCam",     c_void_p)
    ]

# the image open struct
class TUIMG_OPEN(Structure):
    _fields_ = [
        ("pszfileName",   c_void_p),
        ("hIdxTUImg",     c_void_p)
    ]

# the camera value text struct
class TUCAM_VALUE_INFO(Structure):
    _fields_ = [
        ("nID",        c_int32),
        ("nValue",     c_int32),
        ("pText",      c_char_p),
        ("nTextSize",  c_int32)
    ]

# the camera value text struct
class TUCAM_VALUE_TEXT(Structure):
    _fields_ = [
        ("nID",       c_int32),
        ("dbValue",   c_double),
        ("pText",     c_char_p),
        ("nTextSize", c_int32)
    ]

# the camera capability attribute
class TUCAM_CAPA_ATTR(Structure):
    _fields_ = [
        ("idCapa",   c_int32),
        ("nValMin",  c_int32),
        ("nValMax",  c_int32),
        ("nValDft",  c_int32),
        ("nValStep", c_int32)
    ]

# the camera property attribute
class TUCAM_PROP_ATTR(Structure):
    _fields_ = [
        ("idProp",    c_int32),
        ("nIdxChn",   c_int32),
        ("dbValMin",  c_double),
        ("dbValMax",  c_double),
        ("dbValDft",  c_double),
        ("dbValStep", c_double)
    ]

# the camera roi attribute
class TUCAM_ROI_ATTR(Structure):
    _fields_ = [
        ("bEnable",    c_int32),
        ("nHOffset",   c_int32),
        ("nVOffset",   c_int32),
        ("nWidth",     c_int32),
        ("nHeight",    c_int32)
    ]

# the camera multi roi attribute
# the camera size attribute
class TUCAM_SIZE_ATTR(Structure):
    _fields_ = [
        ("nHOffset",   c_int32),
        ("nVOffset",   c_int32),
        ("nWidth",     c_int32),
        ("nHeight",    c_int32)
    ]

class TUCAM_MULTIROI_ATTR(Structure):
    _fields_ = [
        ("bLimit",     c_int32),
        ("nROIStatus", c_int32),
        ("sizeAttr",   TUCAM_SIZE_ATTR)
    ]

# the camera roi calculate attribute
class TUCAM_CALC_ROI_ATTR(Structure):
    _fields_ = [
        ("bEnable",    c_int32),
        ("idCalc",     c_int32),
        ("nHOffset",   c_int32),
        ("nVOffset",   c_int32),
        ("nWidth",     c_int32),
        ("nHeight",    c_int32)
    ]

# the camera trigger attribute
class TUCAM_TRIGGER_ATTR(Structure):
    _fields_ = [
        ("nTgrMode",     c_int32),
        ("nExpMode",     c_int32),
        ("nEdgeMode",    c_int32),
        ("nDelayTm",     c_int32),
        ("nFrames",      c_int32),
        ("nBufFrames",   c_int32)
    ]

# the camera trigger out attribute
class TUCAM_TRGOUT_ATTR(Structure):
    _fields_ = [
        ("nTgrOutPort",     c_int32),
        ("nTgrOutMode",     c_int32),
        ("nEdgeMode",       c_int32),
        ("nDelayTm",        c_int32),
        ("nWidth",          c_int32)
    ]

# the camera any bin attribute
class TUCAM_BIN_ATTR(Structure):
    _fields_ = [
        ("bEnable",   c_int32),
        ("nMode",     c_int32),
        ("nWidth",    c_int32),
        ("nHeight",   c_int32)
    ]

# Define the struct of image header
class TUCAM_IMG_HEADER(Structure):
    _fields_ = [
        ("szSignature",  c_char * 8),
        ("usHeader",     c_ushort),
        ("usOffset",     c_ushort),
        ("usWidth",      c_ushort),
        ("usHeight",     c_ushort),
        ("uiWidthStep",  c_uint),
        ("ucDepth",      c_ubyte),
        ("ucFormat",     c_ubyte),
        ("ucChannels",   c_ubyte),
        ("ucElemBytes",  c_ubyte),
        ("ucFormatGet",  c_ubyte),
        ("uiIndex",      c_uint),
        ("uiImgSize",    c_uint),
        ("uiRsdSize",    c_uint),
        ("uiHstSize",    c_uint),
        ("pImgData",     c_void_p),
        ("pImgHist",     c_void_p),
        ("usLLevels",    c_ushort),
        ("usRLevels",    c_ushort),
        ("ucRsd1",       c_char * 64),
        ("dblExposure",  c_double),
        ("ucRsd2",       c_char * 170),
        ("dblTimeStamp", c_double),
        ("dblTimeLast",  c_double),
        ("ucRsd3",       c_char * 32),
        ("ucGPSTimeStampYear",  c_ubyte),
        ("ucGPSTimeStampMonth", c_ubyte),
        ("ucGPSTimeStampDay",   c_ubyte),
        ("ucGPSTimeStampHour",  c_ubyte),
        ("ucGPSTimeStampMin",   c_ubyte),
        ("ucGPSTimeStampSec",   c_ubyte),
        ("nGPSTimeStampNs", c_int),
        ("ucRsd4",       c_char * 639)
    ]

# the camera frame struct
class TUCAM_FRAME(Structure):
    _fields_ = [
        ("szSignature",  c_char * 8),
        ("usHeader",     c_ushort),
        ("usOffset",     c_ushort),
        ("usWidth",      c_ushort),
        ("usHeight",     c_ushort),
        ("uiWidthStep",  c_uint),
        ("ucDepth",      c_ubyte),
        ("ucFormat",     c_ubyte),
        ("ucChannels",   c_ubyte),
        ("ucElemBytes",  c_ubyte),
        ("ucFormatGet",  c_ubyte),
        ("uiIndex",      c_uint),
        ("uiImgSize",    c_uint),
        ("uiRsdSize",    c_uint),
        ("uiHstSize",    c_uint),
        ("pBuffer",      c_void_p)
    ]

# the camera frame struct
class TUCAM_RAWIMG_HEADER(Structure):
    _fields_ = [
        ("usWidth",      c_ushort),
        ("usHeight",     c_ushort),
        ("usXOffset",    c_ushort),
        ("usYOffset",    c_ushort),
        ("usXPadding",   c_ushort),
        ("usYPadding",   c_ushort),
        ("usOffset",     c_ushort),
        ("ucDepth",      c_ubyte),
        ("ucChannels",   c_ubyte),
        ("ucElemBytes",  c_ubyte),
        ("uiIndex",      c_uint),
        ("uiImgSize",    c_uint),
        ("uiPixelFormat", c_uint),
        ("dblExposure",  c_double),
        ("pImgData",     c_void_p),
        ("dblTimeStamp", c_double),
        ("dblTimeLast",  c_double)
    ]

# the file save struct
class TUCAM_FILE_SAVE(Structure):
    _fields_ = [
        ("nSaveFmt",     c_int32),
        ("pstrSavePath", c_char_p),
        ("pFrame",       POINTER(TUCAM_FRAME))
    ]

# the record save struct
class TUCAM_REC_SAVE(Structure):
    _fields_ = [
        ("nCodec",       c_int32),
        ("pstrSavePath", c_char_p),
        ("fFps",         c_float)
    ]

# the register read/write struct
class TUCAM_REG_RW(Structure):
    _fields_ = [
        ("nRegType",     c_int32),
        ("pBuf",         c_char_p),
        ("nBufSize",     c_int32)
    ]

# the subtract background struct
class TUCAM_IMG_BACKGROUND(Structure):
    _fields_ = [
        ("bEnable",   c_int32),
        ("ImgHeader", TUCAM_RAWIMG_HEADER)
    ]

# the math struct
class TUCAM_IMG_MATH(Structure):
    _fields_ = [
        ("bEnable", c_int32),
        ("nMode",   c_int32),
        ("usGray",  c_ushort)
    ]

# the genicam node element
class TUCAM_VALUEINT(Structure):
    _fields_ = [
        ("nVal",     c_int64),
        ("nMin",     c_int64),
        ("nMax",     c_int64),
        ("nStep",    c_int64),
        ("nDefault", c_int64)
    ]

class TUCAM_VALUEDOUBLE(Structure):
    _fields_ = [
        ("dbVal",     c_double),
        ("dbMin",     c_double),
        ("dbMax",     c_double),
        ("dbStep",    c_double),
        ("dbDefault", c_double)
    ]

class TUCAM_UNION(Union):
     _fields_ = [
         ("Int64",  TUCAM_VALUEINT),
         ("Double", TUCAM_VALUEDOUBLE)
     ]

class TUCAM_ELEMENT(Structure):
    _fields_ = [
        ("IsLocked",         c_uint8),
        ("Level",            c_uint8),
        ("Representation",   c_ushort),
        ("Type",             c_int32),  #TUELEM_TYPE
        ("Access",           c_int32),  #TUACCESS_MODE
        ("Visibility",       c_int32),  #TU_VISIBILITY
        ("nReserve",         c_int32),
        ("uValue",           TUCAM_UNION),
        ("pName",            c_char_p),
        ("pDisplayName",     c_char_p),
        ("pTransfer",        c_char_p),
        ("pDesc",            c_char_p),
        ("pUnit",            c_char_p),
        ("pEntries",         ctypes.POINTER(ctypes.c_char_p)),
        ("PollingTime",      c_int64),
        ("DisplayPrecision", c_int64)
    ]

BUFFER_CALLBACK  = eval('CFUNCTYPE')(c_void_p)
CONTEXT_CALLBACK = eval('CFUNCTYPE')(c_void_p)

# the API fuction
# Initialize uninitialize and misc
TUCAM_Api_Init   = TUSDKdll.TUCAM_Api_Init
TUCAM_Api_Uninit = TUSDKdll.TUCAM_Api_Uninit
TUCAM_Dev_Open   = TUSDKdll.TUCAM_Dev_Open
TUCAM_Dev_Open.argtypes = [POINTER(TUCAM_OPEN)]
TUCAM_Dev_Open.restype  = TUCAMRET
TUCAM_Dev_Close  = TUSDKdll.TUCAM_Dev_Close
TUCAM_Dev_Close.argtypes = [c_void_p]
TUCAM_Dev_Close.restype  = TUCAMRET

# Get some device information (VID/PID/Version)
TUCAM_Dev_GetInfo   = TUSDKdll.TUCAM_Dev_GetInfo
TUCAM_Dev_GetInfo.argtypes = [c_void_p, POINTER(TUCAM_VALUE_INFO)]
TUCAM_Dev_GetInfo.restype  = TUCAMRET
TUCAM_Dev_GetInfoEx = TUSDKdll.TUCAM_Dev_GetInfoEx
TUCAM_Dev_GetInfoEx.argtypes = [c_uint, POINTER(TUCAM_VALUE_INFO)]
TUCAM_Dev_GetInfoEx.restype  = TUCAMRET

# Capability control
TUCAM_Capa_GetAttr      = TUSDKdll.TUCAM_Capa_GetAttr
TUCAM_Capa_GetAttr.argtypes = [c_void_p, POINTER(TUCAM_CAPA_ATTR)]
TUCAM_Capa_GetAttr.restype  = TUCAMRET
TUCAM_Capa_GetValue     = TUSDKdll.TUCAM_Capa_GetValue
TUCAM_Capa_GetValue.argtypes = [c_void_p, c_int32, c_void_p]
TUCAM_Capa_GetValue.restype  = TUCAMRET
TUCAM_Capa_SetValue     = TUSDKdll.TUCAM_Capa_SetValue
TUCAM_Capa_SetValue.argtypes = [c_void_p, c_int32, c_int32]
TUCAM_Capa_SetValue.restype  = TUCAMRET
TUCAM_Capa_GetValueText = TUSDKdll.TUCAM_Capa_GetValueText
TUCAM_Capa_GetValueText.argtypes = [c_void_p, POINTER(TUCAM_VALUE_TEXT)]
TUCAM_Capa_GetValueText.restype  = TUCAMRET

# Property control
TUCAM_Prop_GetAttr       = TUSDKdll.TUCAM_Prop_GetAttr
TUCAM_Prop_GetAttr.argtypes = [c_void_p, POINTER(TUCAM_PROP_ATTR)]
TUCAM_Prop_GetAttr.restype  = TUCAMRET
TUCAM_Prop_GetValue      = TUSDKdll.TUCAM_Prop_GetValue
TUCAM_Prop_GetValue.argtypes = [c_void_p, c_int32, c_void_p, c_int32]
TUCAM_Prop_GetValue.restype  = TUCAMRET
TUCAM_Prop_SetValue      = TUSDKdll.TUCAM_Prop_SetValue
TUCAM_Prop_SetValue.argtypes = [c_void_p, c_int32, c_double, c_int32]
TUCAM_Prop_SetValue.restype  = TUCAMRET
TUCAM_Prop_GetValueText  = TUSDKdll.TUCAM_Prop_GetValueText
TUCAM_Prop_GetValueText.argtypes = [c_void_p, POINTER(TUCAM_VALUE_TEXT), c_int32]
TUCAM_Prop_GetValueText.restype  = TUCAMRET

# Buffer control
TUCAM_Buf_Alloc          = TUSDKdll.TUCAM_Buf_Alloc
TUCAM_Buf_Alloc.argtypes = [c_void_p, POINTER(TUCAM_FRAME)]
TUCAM_Buf_Alloc.restype  = TUCAMRET
TUCAM_Buf_Release        = TUSDKdll.TUCAM_Buf_Release
TUCAM_Buf_Release.argtypes = [c_void_p]
TUCAM_Buf_Release.restype  = TUCAMRET
TUCAM_Buf_AbortWait      = TUSDKdll.TUCAM_Buf_AbortWait
TUCAM_Buf_AbortWait.argtypes = [c_void_p]
TUCAM_Buf_AbortWait.restype  = TUCAMRET
TUCAM_Buf_WaitForFrame   = TUSDKdll.TUCAM_Buf_WaitForFrame
TUCAM_Buf_WaitForFrame.argtypes = [c_void_p, POINTER(TUCAM_FRAME), c_int32]
TUCAM_Buf_WaitForFrame.restype  = TUCAMRET
TUCAM_Buf_CopyFrame      = TUSDKdll.TUCAM_Buf_CopyFrame
TUCAM_Buf_CopyFrame.argtypes = [c_void_p, POINTER(TUCAM_FRAME)]
TUCAM_Buf_CopyFrame.restype  = TUCAMRET

# Buffer CallBack Function
TUCAM_Buf_DataCallBack   = TUSDKdll.TUCAM_Buf_DataCallBack
TUCAM_Buf_DataCallBack.argtypes = [c_void_p, BUFFER_CALLBACK, c_void_p]
TUCAM_Buf_DataCallBack.restype  = TUCAMRET
# Get Buffer Data
TUCAM_Buf_GetData        = TUSDKdll.TUCAM_Buf_GetData
TUCAM_Buf_GetData.argtypes = [c_void_p, POINTER(TUCAM_RAWIMG_HEADER)]
TUCAM_Buf_GetData.restype  = TUCAMRET

# Capturing control
TUCAM_Cap_SetROI         = TUSDKdll.TUCAM_Cap_SetROI
TUCAM_Cap_SetROI.argtypes = [c_void_p, TUCAM_ROI_ATTR]
TUCAM_Cap_SetROI.restype  = TUCAMRET
TUCAM_Cap_GetROI         = TUSDKdll.TUCAM_Cap_GetROI
TUCAM_Cap_GetROI.argtypes = [c_void_p, POINTER(TUCAM_ROI_ATTR)]
TUCAM_Cap_GetROI.restype  = TUCAMRET

# MultiROI
TUCAM_Cap_SetMultiROI       = TUSDKdll.TUCAM_Cap_SetMultiROI
TUCAM_Cap_SetMultiROI.argtypes = [c_void_p, TUCAM_MULTIROI_ATTR]
TUCAM_Cap_SetMultiROI.restype  = TUCAMRET
TUCAM_Cap_GetMultiROI       = TUSDKdll.TUCAM_Cap_GetMultiROI
TUCAM_Cap_GetMultiROI.argtypes = [c_void_p, POINTER(TUCAM_MULTIROI_ATTR)]
TUCAM_Cap_GetMultiROI.restype  = TUCAMRET

# Trigger
TUCAM_Cap_SetTrigger        = TUSDKdll.TUCAM_Cap_SetTrigger
TUCAM_Cap_SetTrigger.argtypes = [c_void_p, TUCAM_TRIGGER_ATTR]
TUCAM_Cap_SetTrigger.restype  = TUCAMRET
TUCAM_Cap_GetTrigger        = TUSDKdll.TUCAM_Cap_GetTrigger
TUCAM_Cap_GetTrigger.argtypes = [c_void_p, POINTER(TUCAM_TRIGGER_ATTR)]
TUCAM_Cap_GetTrigger.restype  = TUCAMRET
TUCAM_Cap_DoSoftwareTrigger = TUSDKdll.TUCAM_Cap_DoSoftwareTrigger
TUCAM_Cap_DoSoftwareTrigger.argtypes = [c_void_p]
TUCAM_Cap_DoSoftwareTrigger.restype  = TUCAMRET

# Trigger Out
TUCAM_Cap_SetTriggerOut     = TUSDKdll.TUCAM_Cap_SetTriggerOut
TUCAM_Cap_SetTriggerOut.argtypes = [c_void_p, TUCAM_TRGOUT_ATTR]
TUCAM_Cap_SetTriggerOut.restype  = TUCAMRET
TUCAM_Cap_GetTriggerOut     = TUSDKdll.TUCAM_Cap_GetTriggerOut
TUCAM_Cap_SetTriggerOut.argtypes = [c_void_p, POINTER(TUCAM_TRGOUT_ATTR)]
TUCAM_Cap_SetTriggerOut.restype  = TUCAMRET

# Capturing
TUCAM_Cap_Start             = TUSDKdll.TUCAM_Cap_Start
TUCAM_Cap_Start.argtypes = [c_void_p, c_uint]
TUCAM_Cap_Start.restype  = TUCAMRET
TUCAM_Cap_Stop              = TUSDKdll.TUCAM_Cap_Stop
TUCAM_Cap_Stop.argtypes = [c_void_p]
TUCAM_Cap_Stop.restype  = TUCAMRET

# File control
# Image
TUCAM_File_SaveImage        = TUSDKdll.TUCAM_File_SaveImage
TUCAM_File_SaveImage.argtypes = [c_void_p, TUCAM_FILE_SAVE]
TUCAM_File_SaveImage.restype  = TUCAMRET

# Profiles
TUCAM_File_LoadProfiles     = TUSDKdll.TUCAM_File_LoadProfiles
TUCAM_File_LoadProfiles.argtypes = [c_void_p, c_void_p]
TUCAM_File_LoadProfiles.restype  = TUCAMRET
TUCAM_File_SaveProfiles     = TUSDKdll.TUCAM_File_SaveProfiles
TUCAM_File_SaveProfiles.argtypes = [c_void_p, c_void_p]
TUCAM_File_SaveProfiles.restype  = TUCAMRET

# Video
TUCAM_Rec_Start             = TUSDKdll.TUCAM_Rec_Start
TUCAM_Rec_Start.argtypes = [c_void_p, TUCAM_REC_SAVE]
TUCAM_Rec_Start.restype  = TUCAMRET
TUCAM_Rec_AppendFrame       = TUSDKdll.TUCAM_Rec_AppendFrame
TUCAM_Rec_AppendFrame.argtypes = [c_void_p, POINTER(TUCAM_FRAME)]
TUCAM_Rec_AppendFrame.restype  = TUCAMRET
TUCAM_Rec_Stop              = TUSDKdll.TUCAM_Rec_Stop
TUCAM_Rec_Stop.argtypes = [c_void_p]
TUCAM_Rec_Stop.restype  = TUCAMRET

TUIMG_File_Open             = TUSDKdll.TUIMG_File_Open
TUIMG_File_Open.argtypes = [POINTER(TUIMG_OPEN), POINTER(POINTER(TUCAM_FRAME))]
TUIMG_File_Open.restype  = TUCAMRET
TUIMG_File_Close            = TUSDKdll.TUIMG_File_Close
TUIMG_File_Close.argtypes = [c_void_p]
TUIMG_File_Close.restype  = TUCAMRET

# Calculatr roi
TUCAM_Calc_SetROI           = TUSDKdll.TUCAM_Calc_SetROI
TUCAM_Calc_SetROI.argtypes = [c_void_p, TUCAM_CALC_ROI_ATTR]
TUCAM_Calc_SetROI.restype  = TUCAMRET
TUCAM_Calc_GetROI           = TUSDKdll.TUCAM_Calc_GetROI
TUCAM_Calc_GetROI.argtypes = [c_void_p, POINTER(TUCAM_CALC_ROI_ATTR)]
TUCAM_Calc_GetROI.restype  = TUCAMRET

# Extened control
TUCAM_Reg_Read              = TUSDKdll.TUCAM_Reg_Read
TUCAM_Reg_Read.argtypes = [c_void_p, TUCAM_REG_RW]
TUCAM_Reg_Read.restype  = TUCAMRET
TUCAM_Reg_Write             = TUSDKdll.TUCAM_Reg_Write
TUCAM_Reg_Write.argtypes = [c_void_p, TUCAM_REG_RW]
TUCAM_Reg_Write.restype  = TUCAMRET

# Get GrayValue
TUCAM_Get_GrayValue         = TUSDKdll.TUCAM_Get_GrayValue
TUCAM_Get_GrayValue.argtypes = [c_void_p, c_int32, c_int32, c_void_p]
TUCAM_Get_GrayValue.restype  = TUCAMRET

# Find color temperature index value according to RGB
TUCAM_Index_GetColorTemperature = TUSDKdll.TUCAM_Index_GetColorTemperature
TUCAM_Index_GetColorTemperature.argtypes = [c_void_p, c_int32, c_int32, c_int32, c_void_p]
TUCAM_Index_GetColorTemperature.restype  = TUCAMRET

# Set record save mode
TUCAM_Rec_SetAppendMode = TUSDKdll.TUCAM_Rec_SetAppendMode
TUCAM_Rec_SetAppendMode.argtypes = [c_void_p, c_uint]
TUCAM_Rec_SetAppendMode.restype  = TUCAMRET

# Any-BIN
TUCAM_Cap_SetBIN   = TUSDKdll.TUCAM_Cap_SetBIN
TUCAM_Cap_SetBIN.argtypes = [c_void_p, TUCAM_BIN_ATTR]
TUCAM_Cap_SetBIN.restype  = TUCAMRET
TUCAM_Cap_GetBIN   = TUSDKdll.TUCAM_Cap_GetBIN
TUCAM_Cap_GetBIN.argtypes = [c_void_p, POINTER(TUCAM_BIN_ATTR)]
TUCAM_Cap_GetBIN.restype  = TUCAMRET

# Subtract background
TUCAM_Cap_SetBackGround  = TUSDKdll.TUCAM_Cap_SetMath
TUCAM_Cap_SetBackGround.argtypes = [c_void_p, TUCAM_IMG_BACKGROUND]
TUCAM_Cap_SetBackGround.restype  = TUCAMRET
TUCAM_Cap_GetBackGround  = TUSDKdll.TUCAM_Cap_GetMath
TUCAM_Cap_GetBackGround.argtypes = [c_void_p, POINTER(TUCAM_IMG_BACKGROUND)]
TUCAM_Cap_GetBackGround.restype  = TUCAMRET

# Math
TUCAM_Cap_SetMath  = TUSDKdll.TUCAM_Cap_SetMath
TUCAM_Cap_SetMath.argtypes = [c_void_p, TUCAM_IMG_MATH]
TUCAM_Cap_SetMath.restype  = TUCAMRET
TUCAM_Cap_GetMath  = TUSDKdll.TUCAM_Cap_GetMath
TUCAM_Cap_GetMath.argtypes = [c_void_p, POINTER(TUCAM_IMG_MATH)]
TUCAM_Cap_GetMath.restype  = TUCAMRET

# GenICam Element Attribute pName
TUCAM_GenICam_ElementAttr = TUSDKdll.TUCAM_GenICam_ElementAttr
TUCAM_GenICam_ElementAttr.argtypes = [c_void_p, POINTER(TUCAM_ELEMENT), c_void_p, c_int32]
TUCAM_GenICam_ElementAttr.restype  = TUCAMRET

# GenICam Element Attribute Next
TUCAM_GenICam_ElementAttrNext = TUSDKdll.TUCAM_GenICam_ElementAttrNext
TUCAM_GenICam_ElementAttrNext.argtypes = [c_void_p, POINTER(TUCAM_ELEMENT), c_void_p, c_int32]
TUCAM_GenICam_ElementAttrNext.restype  = TUCAMRET

# GenICam Set Element Value
TUCAM_GenICam_SetElementValue = TUSDKdll.TUCAM_GenICam_SetElementValue
TUCAM_GenICam_SetElementValue.argtypes = [c_void_p, POINTER(TUCAM_ELEMENT), c_int32]
TUCAM_GenICam_SetElementValue.restype  = TUCAMRET

# GenICam Get Element Value
TUCAM_GenICam_GetElementValue = TUSDKdll.TUCAM_GenICam_GetElementValue
TUCAM_GenICam_GetElementValue.argtypes = [c_void_p, POINTER(TUCAM_ELEMENT), c_int32]
TUCAM_GenICam_GetElementValue.restype  = TUCAMRET

# GenICam Set Register Value
TUCAM_GenICam_SetRegisterValue = TUSDKdll.TUCAM_GenICam_SetRegisterValue
TUCAM_GenICam_SetRegisterValue.argtypes = [c_void_p, c_void_p, c_int64, c_int64]
TUCAM_GenICam_SetRegisterValue.restype  = TUCAMRET

# GenICam Get Register Value
TUCAM_GenICam_GetRegisterValue = TUSDKdll.TUCAM_GenICam_GetRegisterValue
TUCAM_GenICam_GetRegisterValue.argtypes = [c_void_p, c_void_p, c_int64, c_int64]
TUCAM_GenICam_GetRegisterValue.restype  = TUCAMRET

# Only CXP Support
TUCAM_Cap_AnnounceBuffer = TUSDKdll.TUCAM_Cap_AnnounceBuffer
TUCAM_Cap_AnnounceBuffer.argtypes = [c_void_p, c_uint, c_void_p]
TUCAM_Cap_AnnounceBuffer.restype  = TUCAMRET
TUCAM_Cap_ClearBuffer    = TUSDKdll.TUCAM_Cap_ClearBuffer
TUCAM_Cap_ClearBuffer.argtypes = [c_void_p]
TUCAM_Cap_ClearBuffer.restype  = TUCAMRET

# FFC Coefficient Load or Save
#TUCAM_File_LoadFFCCoefficient = TUSDKdll.TUCAM_File_LoadFFCCoefficient
#TUCAM_File_LoadFFCCoefficient.argtypes = [c_void_p, c_void_p]
#TUCAM_File_LoadFFCCoefficient.restype  = TUCAMRET
#TUCAM_File_SaveFFCCoefficient    = TUSDKdll.TUCAM_File_SaveFFCCoefficient
#TUCAM_File_SaveFFCCoefficient.argtypes = [c_void_p, c_void_p]
#TUCAM_File_SaveFFCCoefficient.restype  = TUCAMRET
