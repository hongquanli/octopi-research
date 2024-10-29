"""Version: 57.26813.20241028
We use ctypes to call into the toupcam.dll/libtoupcam.so/libtoupcam.dylib API,
the python class Toupcam is a thin wrapper class to the native api of toupcam.dll/libtoupcam.so/libtoupcam.dylib.
So the manual en.html(English) and hans.html(Simplified Chinese) are also applicable for programming with toupcam.py.
See them in the 'doc' directory:
   (1) en.html, English
   (2) hans.html, Simplified Chinese
"""
import sys, ctypes, os.path

TOUPCAM_MAX = 128

TOUPCAM_FLAG_CMOS                = 0x00000001          # cmos sensor
TOUPCAM_FLAG_CCD_PROGRESSIVE     = 0x00000002          # progressive ccd sensor
TOUPCAM_FLAG_CCD_INTERLACED      = 0x00000004          # interlaced ccd sensor
TOUPCAM_FLAG_ROI_HARDWARE        = 0x00000008          # support hardware ROI
TOUPCAM_FLAG_MONO                = 0x00000010          # monochromatic
TOUPCAM_FLAG_BINSKIP_SUPPORTED   = 0x00000020          # support bin/skip mode
TOUPCAM_FLAG_USB30               = 0x00000040          # usb3.0
TOUPCAM_FLAG_TEC                 = 0x00000080          # Thermoelectric Cooler
TOUPCAM_FLAG_USB30_OVER_USB20    = 0x00000100          # usb3.0 camera connected to usb2.0 port
TOUPCAM_FLAG_ST4                 = 0x00000200          # ST4
TOUPCAM_FLAG_GETTEMPERATURE      = 0x00000400          # support to get the temperature of the sensor
TOUPCAM_FLAG_HIGH_FULLWELL       = 0x00000800          # high fullwell capacity
TOUPCAM_FLAG_RAW10               = 0x00001000          # pixel format, RAW 10bits
TOUPCAM_FLAG_RAW12               = 0x00002000          # pixel format, RAW 12bits
TOUPCAM_FLAG_RAW14               = 0x00004000          # pixel format, RAW 14bits
TOUPCAM_FLAG_RAW16               = 0x00008000          # pixel format, RAW 16bits
TOUPCAM_FLAG_FAN                 = 0x00010000          # cooling fan
TOUPCAM_FLAG_TEC_ONOFF           = 0x00020000          # Thermoelectric Cooler can be turn on or off, support to set the target temperature of TEC
TOUPCAM_FLAG_ISP                 = 0x00040000          # ISP (Image Signal Processing) chip
TOUPCAM_FLAG_TRIGGER_SOFTWARE    = 0x00080000          # support software trigger
TOUPCAM_FLAG_TRIGGER_EXTERNAL    = 0x00100000          # support external trigger
TOUPCAM_FLAG_TRIGGER_SINGLE      = 0x00200000          # only support trigger single: one trigger, one image
TOUPCAM_FLAG_BLACKLEVEL          = 0x00400000          # support set and get the black level
TOUPCAM_FLAG_AUTO_FOCUS          = 0x00800000          # support auto focus
TOUPCAM_FLAG_BUFFER              = 0x01000000          # frame buffer
TOUPCAM_FLAG_DDR                 = 0x02000000          # use very large capacity DDR (Double Data Rate SDRAM) for frame buffer. The capacity is not less than one full frame
TOUPCAM_FLAG_CG                  = 0x04000000          # support Conversion Gain mode: HCG, LCG
TOUPCAM_FLAG_YUV411              = 0x08000000          # pixel format, yuv411
TOUPCAM_FLAG_VUYY                = 0x10000000          # pixel format, yuv422, VUYY
TOUPCAM_FLAG_YUV444              = 0x20000000          # pixel format, yuv444
TOUPCAM_FLAG_RGB888              = 0x40000000          # pixel format, RGB888
TOUPCAM_FLAG_RAW8                = 0x80000000          # pixel format, RAW 8 bits
TOUPCAM_FLAG_GMCY8               = 0x0000000100000000  # pixel format, GMCY, 8 bits
TOUPCAM_FLAG_GMCY12              = 0x0000000200000000  # pixel format, GMCY, 12 bits
TOUPCAM_FLAG_UYVY                = 0x0000000400000000  # pixel format, yuv422, UYVY
TOUPCAM_FLAG_CGHDR               = 0x0000000800000000  # Conversion Gain: HCG, LCG, HDR
TOUPCAM_FLAG_GLOBALSHUTTER       = 0x0000001000000000  # global shutter
TOUPCAM_FLAG_FOCUSMOTOR          = 0x0000002000000000  # support focus motor
TOUPCAM_FLAG_PRECISE_FRAMERATE   = 0x0000004000000000  # support precise framerate & bandwidth, see TOUPCAM_OPTION_PRECISE_FRAMERATE & TOUPCAM_OPTION_BANDWIDTH
TOUPCAM_FLAG_HEAT                = 0x0000008000000000  # support heat to prevent fogging up
TOUPCAM_FLAG_LOW_NOISE           = 0x0000010000000000  # support low noise mode (Higher signal noise ratio, lower frame rate)
TOUPCAM_FLAG_LEVELRANGE_HARDWARE = 0x0000020000000000  # hardware level range, put(get)_LevelRangeV2
TOUPCAM_FLAG_EVENT_HARDWARE      = 0x0000040000000000  # hardware event, such as exposure start & stop
TOUPCAM_FLAG_LIGHTSOURCE         = 0x0000080000000000  # embedded light source
TOUPCAM_FLAG_FILTERWHEEL         = 0x0000100000000000  # astro filter wheel
TOUPCAM_FLAG_GIGE                = 0x0000200000000000  # 1 Gigabit GigE
TOUPCAM_FLAG_10GIGE              = 0x0000400000000000  # 10 Gigabit GigE
TOUPCAM_FLAG_5GIGE               = 0x0000800000000000  # 5 Gigabit GigE
TOUPCAM_FLAG_25GIGE              = 0x0001000000000000  # 2.5 Gigabit GigE
TOUPCAM_FLAG_AUTOFOCUSER         = 0x0002000000000000  # astro auto focuser
TOUPCAM_FLAG_LIGHT_SOURCE        = 0x0004000000000000  # stand alone light source
TOUPCAM_FLAG_CAMERALINK          = 0x0008000000000000  # camera link
TOUPCAM_FLAG_CXP                 = 0x0010000000000000  # CXP: CoaXPress
TOUPCAM_FLAG_RAW12PACK           = 0x0020000000000000  # pixel format, RAW 12bits packed
TOUPCAM_FLAG_SELFTRIGGER         = 0x0040000000000000  # self trigger
TOUPCAM_FLAG_RAW11               = 0x0080000000000000  # pixel format, RAW 11bits
TOUPCAM_FLAG_GHOPTO              = 0x0100000000000000  # ghopto sensor

TOUPCAM_EVENT_EXPOSURE           = 0x0001          # exposure time or gain changed
TOUPCAM_EVENT_TEMPTINT           = 0x0002          # white balance changed, Temp/Tint mode
TOUPCAM_EVENT_CHROME             = 0x0003          # reversed, do not use it
TOUPCAM_EVENT_IMAGE              = 0x0004          # live image arrived, use PullImageXXXX to get this image
TOUPCAM_EVENT_STILLIMAGE         = 0x0005          # snap (still) frame arrived, use PullStillImageXXXX to get this frame
TOUPCAM_EVENT_WBGAIN             = 0x0006          # white balance changed, RGB Gain mode
TOUPCAM_EVENT_TRIGGERFAIL        = 0x0007          # trigger failed
TOUPCAM_EVENT_BLACK              = 0x0008          # black balance changed
TOUPCAM_EVENT_FFC                = 0x0009          # flat field correction status changed
TOUPCAM_EVENT_DFC                = 0x000a          # dark field correction status changed
TOUPCAM_EVENT_ROI                = 0x000b          # roi changed
TOUPCAM_EVENT_LEVELRANGE         = 0x000c          # level range changed
TOUPCAM_EVENT_AUTOEXPO_CONV      = 0x000d          # auto exposure convergence
TOUPCAM_EVENT_AUTOEXPO_CONVFAIL  = 0x000e          # auto exposure once mode convergence failed
TOUPCAM_EVENT_FPNC               = 0x000f          # fix pattern noise correction status changed
TOUPCAM_EVENT_ERROR              = 0x0080          # generic error
TOUPCAM_EVENT_DISCONNECTED       = 0x0081          # camera disconnected
TOUPCAM_EVENT_NOFRAMETIMEOUT     = 0x0082          # no frame timeout error
TOUPCAM_EVENT_FOCUSPOS           = 0x0084          # focus positon
TOUPCAM_EVENT_NOPACKETTIMEOUT    = 0x0085          # no packet timeout
TOUPCAM_EVENT_EXPO_START         = 0x4000          # hardware event: exposure start
TOUPCAM_EVENT_EXPO_STOP          = 0x4001          # hardware event: exposure stop
TOUPCAM_EVENT_TRIGGER_ALLOW      = 0x4002          # hardware event: next trigger allow
TOUPCAM_EVENT_HEARTBEAT          = 0x4003          # hardware event: heartbeat, can be used to monitor whether the camera is alive
TOUPCAM_EVENT_TRIGGER_IN         = 0x4004          # hardware event: trigger in
TOUPCAM_EVENT_FACTORY            = 0x8001          # restore factory settings

TOUPCAM_OPTION_NOFRAME_TIMEOUT        = 0x01       # no frame timeout: 0 => disable, positive value (>= NOFRAME_TIMEOUT_MIN) => timeout milliseconds. default: disable
TOUPCAM_OPTION_THREAD_PRIORITY        = 0x02       # set the priority of the internal thread which grab data from the usb device.
                                                   #   Win: iValue: 0 => THREAD_PRIORITY_NORMAL; 1 => THREAD_PRIORITY_ABOVE_NORMAL; 2 => THREAD_PRIORITY_HIGHEST; 3 => THREAD_PRIORITY_TIME_CRITICAL; default: 1; see: https://docs.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setthreadpriority
                                                   #   Linux & macOS: The high 16 bits for the scheduling policy, and the low 16 bits for the priority; see: https://linux.die.net/man/3/pthread_setschedparam
                                                   #
TOUPCAM_OPTION_RAW                    = 0x04       # raw data mode, read the sensor "raw" data. This can be set only while camea is NOT running. 0 = rgb, 1 = raw, default value: 0
TOUPCAM_OPTION_HISTOGRAM              = 0x05       # 0 = only one, 1 = continue mode
TOUPCAM_OPTION_BITDEPTH               = 0x06       # 0 = 8 bits mode, 1 = 16 bits mode
TOUPCAM_OPTION_FAN                    = 0x07       # 0 = turn off the cooling fan, [1, max] = fan speed, set to "-1" means to use default fan speed
TOUPCAM_OPTION_TEC                    = 0x08       # 0 = turn off the thermoelectric cooler, 1 = turn on the thermoelectric cooler
TOUPCAM_OPTION_LINEAR                 = 0x09       # 0 = turn off the builtin linear tone mapping, 1 = turn on the builtin linear tone mapping, default value: 1
TOUPCAM_OPTION_CURVE                  = 0x0a       # 0 = turn off the builtin curve tone mapping, 1 = turn on the builtin polynomial curve tone mapping, 2 = logarithmic curve tone mapping, default value: 2
TOUPCAM_OPTION_TRIGGER                = 0x0b       # 0 = video mode, 1 = software or simulated trigger mode, 2 = external trigger mode, 3 = external + software trigger, default value = 0
TOUPCAM_OPTION_RGB                    = 0x0c       # 0 => RGB24; 1 => enable RGB48 format when bitdepth > 8; 2 => RGB32; 3 => 8 Bits Grey (only for mono camera); 4 => 16 Bits Grey (only for mono camera when bitdepth > 8); 5 => 64(RGB64)
TOUPCAM_OPTION_COLORMATIX             = 0x0d       # enable or disable the builtin color matrix, default value: 1
TOUPCAM_OPTION_WBGAIN                 = 0x0e       # enable or disable the builtin white balance gain, default value: 1
TOUPCAM_OPTION_TECTARGET              = 0x0f       # get or set the target temperature of the thermoelectric cooler, in 0.1 degree Celsius. For example, 125 means 12.5 degree Celsius, -35 means -3.5 degree Celsius. Set "-2730" or below means using the default for that model
TOUPCAM_OPTION_AUTOEXP_POLICY         = 0x10       # auto exposure policy:
                                                   #     0: Exposure Only
                                                   #     1: Exposure Preferred
                                                   #     2: Gain Only
                                                   #     3: Gain Preferred
                                                   #     default value: 1
                                                   #
TOUPCAM_OPTION_FRAMERATE              = 0x11       # limit the frame rate, the default value 0 means no limit
TOUPCAM_OPTION_DEMOSAIC               = 0x12       # demosaic method for both video and still image: BILINEAR = 0, VNG(Variable Number of Gradients) = 1, PPG(Patterned Pixel Grouping) = 2, AHD(Adaptive Homogeneity Directed) = 3, EA(Edge Aware) = 4, see https://en.wikipedia.org/wiki/Demosaicing
                                                   #   In terms of CPU usage, EA is the lowest, followed by BILINEAR, and the others are higher.
                                                   #   default value: 0
TOUPCAM_OPTION_DEMOSAIC_VIDEO         = 0x13       # demosaic method for video
TOUPCAM_OPTION_DEMOSAIC_STILL         = 0x14       # demosaic method for still image
TOUPCAM_OPTION_BLACKLEVEL             = 0x15       # black level
TOUPCAM_OPTION_MULTITHREAD            = 0x16       # multithread image processing
TOUPCAM_OPTION_BINNING                = 0x17       # binning
                                                   #     0x01: (no binning)
                                                   #     n: (saturating add, n*n), 0x02(2*2), 0x03(3*3), 0x04(4*4), 0x05(5*5), 0x06(6*6), 0x07(7*7), 0x08(8*8). The Bitdepth of the data remains unchanged.
                                                   #     0x40 | n: (unsaturated add, n*n, works only in RAW mode), 0x42(2*2), 0x43(3*3), 0x44(4*4), 0x45(5*5), 0x46(6*6), 0x47(7*7), 0x48(8*8). The Bitdepth of the data is increased. For example, the original data with bitdepth of 12 will increase the bitdepth by 2 bits and become 14 after 2*2 binning.
                                                   #     0x80 | n: (average, n*n), 0x82(2*2), 0x83(3*3), 0x84(4*4), 0x85(5*5), 0x86(6*6), 0x87(7*7), 0x88(8*8). The Bitdepth of the data remains unchanged.
                                                   # The final image size is rounded down to an even number, such as 640/3 to get 212
                                                   #
TOUPCAM_OPTION_ROTATE                 = 0x18       # rotate clockwise: 0, 90, 180, 270
TOUPCAM_OPTION_CG                     = 0x19       # Conversion Gain:
                                                   #     0 = LCG
                                                   #     1 = HCG
                                                   #     2 = HDR (for camera with flag TOUPCAM_FLAG_CGHDR)
                                                   #     2 = MCG (for camera with flag TOUPCAM_FLAG_GHOPTO)
                                                   #
TOUPCAM_OPTION_PIXEL_FORMAT           = 0x1a       # pixel format
TOUPCAM_OPTION_FFC                    = 0x1b       # flat field correction
                                                   #     set:
                                                   #         0: disable
                                                   #         1: enable
                                                   #         -1: reset
                                                   #         (0xff000000 | n): set the average number to n, [1~255]
                                                   #     get:
                                                   #         (val & 0xff): 0 => disable, 1 => enable, 2 => inited
                                                   #         ((val & 0xff00) >> 8): sequence
                                                   #         ((val & 0xff0000) >> 16): average number
                                                   #
TOUPCAM_OPTION_DDR_DEPTH              = 0x1c       # the number of the frames that DDR can cache
                                                   #     1: DDR cache only one frame
                                                   #     0: Auto:
                                                   #         => one for video mode when auto exposure is enabled
                                                   #         => full capacity for others
                                                   #     1: DDR can cache frames to full capacity
                                                   #
TOUPCAM_OPTION_DFC                    = 0x1d       # dark field correction
                                                   #     set:
                                                   #         0: disable
                                                   #         1: enable
                                                   #         -1: reset
                                                   #         (0xff000000 | n): set the average number to n, [1~255]
                                                   #     get:
                                                   #         (val & 0xff): 0 => disable, 1 => enable, 2 => inited
                                                   #         ((val & 0xff00) >> 8): sequence
                                                   #         ((val & 0xff0000) >> 16): average number
                                                   #
TOUPCAM_OPTION_SHARPENING             = 0x1e       # Sharpening: (threshold << 24) | (radius << 16) | strength)
                                                   #     strength: [0, 500], default: 0 (disable)
                                                   #     radius: [1, 10]
                                                   #     threshold: [0, 255]
                                                   #
TOUPCAM_OPTION_FACTORY                = 0x1f       # restore the factory settings
TOUPCAM_OPTION_TEC_VOLTAGE            = 0x20       # get the current TEC voltage in 0.1V, 59 mean 5.9V; readonly
TOUPCAM_OPTION_TEC_VOLTAGE_MAX        = 0x21       # TEC maximum voltage in 0.1V
TOUPCAM_OPTION_DEVICE_RESET           = 0x22       # reset usb device, simulate a replug
TOUPCAM_OPTION_UPSIDE_DOWN            = 0x23       # upsize down:
                                                   #     1: yes
                                                   #     0: no
                                                   #     default: 1 (win), 0 (linux/macos)
                                                   #
TOUPCAM_OPTION_FOCUSPOS               = 0x24       # focus positon
TOUPCAM_OPTION_AFMODE                 = 0x25       # auto focus mode, see ToupcamAFMode
TOUPCAM_OPTION_AFSTATUS               = 0x27       # auto focus status, see ToupcamAFStaus
TOUPCAM_OPTION_TESTPATTERN            = 0x28       # test pattern:
                                                   #     0: off
                                                   #     3: monochrome diagonal stripes
                                                   #     5: monochrome vertical stripes
                                                   #     7: monochrome horizontal stripes
                                                   #     9: chromatic diagonal stripes
                                                   #
TOUPCAM_OPTION_AUTOEXP_THRESHOLD      = 0x29       # threshold of auto exposure, default value: 5, range = [2, 15]
TOUPCAM_OPTION_BYTEORDER              = 0x2a       # Byte order, BGR or RGB: 0 => RGB, 1 => BGR, default value: 1(Win), 0(macOS, Linux, Android)
TOUPCAM_OPTION_NOPACKET_TIMEOUT       = 0x2b       # no packet timeout: 0 => disable, positive value (>= NOPACKET_TIMEOUT_MIN) => timeout milliseconds. default: disable
TOUPCAM_OPTION_MAX_PRECISE_FRAMERATE  = 0x2c       # get the precise frame rate maximum value in 0.1 fps, such as 115 means 11.5 fps. E_NOTIMPL means not supported
TOUPCAM_OPTION_PRECISE_FRAMERATE      = 0x2d       # precise frame rate current value in 0.1 fps. use TOUPCAM_OPTION_MAX_PRECISE_FRAMERATE, TOUPCAM_OPTION_MIN_PRECISE_FRAMERATE to get the range. if the set value is out of range, E_INVALIDARG will be returned
TOUPCAM_OPTION_BANDWIDTH              = 0x2e       # bandwidth, [1-100]%
TOUPCAM_OPTION_RELOAD                 = 0x2f       # reload the last frame in trigger mode
TOUPCAM_OPTION_CALLBACK_THREAD        = 0x30       # dedicated thread for callback: 0 => disable, 1 => enable, default: 0
TOUPCAM_OPTION_FRONTEND_DEQUE_LENGTH  = 0x31       # frontend (raw) frame buffer deque length, range: [2, 1024], default: 4
                                                   # All the memory will be pre-allocated when the camera starts, so, please attention to memory usage
                                                   #
TOUPCAM_OPTION_FRAME_DEQUE_LENGTH     = 0x31       # alias of TOUPCAM_OPTION_FRONTEND_DEQUE_LENGTH
TOUPCAM_OPTION_MIN_PRECISE_FRAMERATE  = 0x32       # get the precise frame rate minimum value in 0.1 fps, such as 15 means 1.5 fps
TOUPCAM_OPTION_SEQUENCER_ONOFF        = 0x33       # sequencer trigger: on/off
TOUPCAM_OPTION_SEQUENCER_NUMBER       = 0x34       # sequencer trigger: number, range = [1, 255]
TOUPCAM_OPTION_SEQUENCER_EXPOTIME     = 0x01000000 # sequencer trigger: exposure time, iOption = TOUPCAM_OPTION_SEQUENCER_EXPOTIME | index, iValue = exposure time
                                                   #   For example, to set the exposure time of the third group to 50ms, call:
                                                   #     Toupcam_put_Option(TOUPCAM_OPTION_SEQUENCER_EXPOTIME | 3, 50000)
                                                   #
TOUPCAM_OPTION_SEQUENCER_EXPOGAIN     = 0x02000000 # sequencer trigger: exposure gain, iOption = TOUPCAM_OPTION_SEQUENCER_EXPOGAIN | index, iValue = gain
TOUPCAM_OPTION_DENOISE                = 0x35       # denoise, strength range: [0, 100], 0 means disable
TOUPCAM_OPTION_HEAT_MAX               = 0x36       # get maximum level: heat to prevent fogging up
TOUPCAM_OPTION_HEAT                   = 0x37       # heat to prevent fogging up
TOUPCAM_OPTION_LOW_NOISE              = 0x38       # low noise mode (Higher signal noise ratio, lower frame rate): 1 => enable
TOUPCAM_OPTION_POWER                  = 0x39       # get power consumption, unit: milliwatt
TOUPCAM_OPTION_GLOBAL_RESET_MODE      = 0x3a       # global reset mode
TOUPCAM_OPTION_OPEN_ERRORCODE         = 0x3b       # get the open camera error code
TOUPCAM_OPTION_FLUSH                  = 0x3d       # 1 = hard flush, discard frames cached by camera DDR (if any)
                                                   # 2 = soft flush, discard frames cached by toupcam.dll (if any)
                                                   # 3 = both flush
                                                   # Toupcam_Flush means 'both flush'
                                                   # return the number of soft flushed frames if successful, HRESULT if failed
                                                   #
TOUPCAM_OPTION_NUMBER_DROP_FRAME      = 0x3e       # get the number of frames that have been grabbed from the USB but dropped by the software
TOUPCAM_OPTION_DUMP_CFG               = 0x3f       # 0 = when camera is stopped, do not dump configuration automatically
                                                   # 1 = when camera is stopped, dump configuration automatically
                                                   # -1 = explicitly dump configuration once
                                                   # default: 1
                                                   #
TOUPCAM_OPTION_DEFECT_PIXEL           = 0x40       # Defect Pixel Correction: 0 => disable, 1 => enable; default: 1
TOUPCAM_OPTION_BACKEND_DEQUE_LENGTH   = 0x41       # backend (pipelined) frame buffer deque length (Only available in pull mode), range: [2, 1024], default: 3
                                                   # All the memory will be pre-allocated when the camera starts, so, please attention to memory usage
                                                   #
TOUPCAM_OPTION_LIGHTSOURCE_MAX        = 0x42       # get the light source range, [0 ~ max]
TOUPCAM_OPTION_LIGHTSOURCE            = 0x43       # light source
TOUPCAM_OPTION_HEARTBEAT              = 0x44       # Heartbeat interval in millisecond, range = [TOUPCAM_HEARTBEAT_MIN, TOUPCAM_HEARTBEAT_MAX], 0 = disable, default: disable
TOUPCAM_OPTION_FRONTEND_DEQUE_CURRENT = 0x45       # get the current number in frontend deque
TOUPCAM_OPTION_BACKEND_DEQUE_CURRENT  = 0x46       # get the current number in backend deque
TOUPCAM_OPTION_EVENT_HARDWARE         = 0x04000000 # enable or disable hardware event: 0 => disable, 1 => enable; default: disable
                                                   #     (1) iOption = TOUPCAM_OPTION_EVENT_HARDWARE, master switch for notification of all hardware events
                                                   #     (2) iOption = TOUPCAM_OPTION_EVENT_HARDWARE | (event type), a specific type of sub-switch
                                                   # Only if both the master switch and the sub-switch of a particular type remain on are actually enabled for that type of event notification.
                                                   #
TOUPCAM_OPTION_PACKET_NUMBER          = 0x47       # get the received packet number
TOUPCAM_OPTION_FILTERWHEEL_SLOT       = 0x48       # filter wheel slot number
TOUPCAM_OPTION_FILTERWHEEL_POSITION   = 0x49       # filter wheel position:
                                                   #     set:
                                                   #         -1: calibrate
                                                   #         val & 0xff: position between 0 and N-1, where N is the number of filter slots
                                                   #         (val >> 8) & 0x1: direction, 0 => clockwise spinning, 1 => auto direction spinning
                                                   #     get:
                                                   #         -1: in motion
                                                   #         val: position arrived
                                                   #
TOUPCAM_OPTION_AUTOEXPOSURE_PERCENT   = 0x4a       # auto exposure percent to average:
                                                   #     1~99: peak percent average
                                                   #     0 or 100: full roi average, means "disabled"
                                                   #
TOUPCAM_OPTION_ANTI_SHUTTER_EFFECT    = 0x4b       # anti shutter effect: 1 => disable, 0 => disable; default: 0
TOUPCAM_OPTION_CHAMBER_HT             = 0x4c       # get chamber humidity & temperature:
                                                   #     high 16 bits: humidity, in 0.1%, such as: 325 means humidity is 32.5%
                                                   #     low 16 bits: temperature, in 0.1 degrees Celsius, such as: 32 means 3.2 degrees Celsius
                                                   #
TOUPCAM_OPTION_ENV_HT                 = 0x4d       # get environment humidity & temperature
TOUPCAM_OPTION_EXPOSURE_PRE_DELAY     = 0x4e       # exposure signal pre-delay, microsecond
TOUPCAM_OPTION_EXPOSURE_POST_DELAY    = 0x4f       # exposure signal post-delay, microsecond
TOUPCAM_OPTION_AUTOEXPO_CONV          = 0x50       # get auto exposure convergence status: 1(YES) or 0(NO), -1(NA)
TOUPCAM_OPTION_AUTOEXPO_TRIGGER       = 0x51       # auto exposure on trigger mode: 0 => disable, 1 => enable; default: 0
TOUPCAM_OPTION_LINE_PRE_DELAY         = 0x52       # specified line signal pre-delay, microsecond
TOUPCAM_OPTION_LINE_POST_DELAY        = 0x53       # specified line signal post-delay, microsecond
TOUPCAM_OPTION_TEC_VOLTAGE_MAX_RANGE  = 0x54       # get the tec maximum voltage range:
                                                   #     high 16 bits: max
                                                   #     low 16 bits: min
TOUPCAM_OPTION_HIGH_FULLWELL          = 0x55       # high fullwell capacity: 0 => disable, 1 => enable
TOUPCAM_OPTION_DYNAMIC_DEFECT         = 0x56       # dynamic defect pixel correction:
                                                   #     dead pixel ratio, t1: high 16 bits: [0, 100], means: [0.0, 1.0]
                                                   #     hot pixel ratio, t2: low 16 bits: [0, 100], means: [0.0, 1.0]
TOUPCAM_OPTION_HDR_KB                 = 0x57       # HDR synthesize
                                                   #     K (high 16 bits): [1, 25500]
                                                   #     B (low 16 bits): [0, 65535]
                                                   #     0xffffffff => set to default
TOUPCAM_OPTION_HDR_THRESHOLD          = 0x58       # HDR synthesize
                                                   #     threshold: [1, 4094]
                                                   #     0xffffffff => set to default
TOUPCAM_OPTION_GIGETIMEOUT            = 0x5a       # For GigE cameras, the application periodically sends heartbeat signals to the camera to keep the connection to the camera alive.
                                                   # If the camera doesn't receive heartbeat signals within the time period specified by the heartbeat timeout counter, the camera resets the connection.
                                                   # When the application is stopped by the debugger, the application cannot send the heartbeat signals
                                                   #     0 => auto: when the camera is opened, enable if no debugger is present or disable if debugger is present
                                                   #     1 => enable
                                                   #     2 => disable
                                                   #     default: auto
TOUPCAM_OPTION_EEPROM_SIZE            = 0x5b       # get EEPROM size
TOUPCAM_OPTION_OVERCLOCK_MAX          = 0x5c       # get overclock range: [0, max]
TOUPCAM_OPTION_OVERCLOCK              = 0x5d       # overclock, default: 0
TOUPCAM_OPTION_RESET_SENSOR           = 0x5e       # reset sensor
TOUPCAM_OPTION_ISP                    = 0x5f       # Enable hardware ISP: 0 => auto (disable in RAW mode, otherwise enable), 1 => enable, -1 => disable; default: 0
TOUPCAM_OPTION_AUTOEXP_EXPOTIME_DAMP  = 0x60       # Auto exposure damp: damping coefficient (thousandths). The larger the damping coefficient, the smoother and slower the exposure time changes
TOUPCAM_OPTION_AUTOEXP_GAIN_DAMP      = 0x61       # Auto exposure damp: damping coefficient (thousandths). The larger the damping coefficient, the smoother and slower the gain changes
TOUPCAM_OPTION_MOTOR_NUMBER           = 0x62       # range: [1, 20]
TOUPCAM_OPTION_MOTOR_POS              = 0x10000000 # range: [1, 702]
TOUPCAM_OPTION_PSEUDO_COLOR_START     = 0x63       # Pseudo: start color, BGR format
TOUPCAM_OPTION_PSEUDO_COLOR_END       = 0x64       # Pseudo: end color, BGR format
TOUPCAM_OPTION_PSEUDO_COLOR_ENABLE    = 0x65       # Pseudo: -1 => custom: use startcolor & endcolor to generate the colormap
                                                   #     0 => disable
                                                   #     1 => spot
                                                   #     2 => spring
                                                   #     3 => summer
                                                   #     4 => autumn
                                                   #     5 => winter
                                                   #     6 => bone
                                                   #     7 => jet
                                                   #     8 => rainbow
                                                   #     9 => deepgreen
                                                   #     10 => ocean
                                                   #     11 => cool
                                                   #     12 => hsv
                                                   #     13 => pink
                                                   #     14 => hot
                                                   #     15 => parula
                                                   #     16 => magma
                                                   #     17 => inferno
                                                   #     18 => plasma
                                                   #     19 => viridis
                                                   #     20 => cividis
                                                   #     21 => twilight
                                                   #     22 => twilight_shifted
                                                   #     23 => turbo
                                                   #     24 => red
                                                   #     25 => green
                                                   #     26 => blue
                                                   #
TOUPCAM_OPTION_LOW_POWERCONSUMPTION   = 0x66       # Low Power Consumption: 0 => disable, 1 => enable
TOUPCAM_OPTION_FPNC                   = 0x67       # Fix Pattern Noise Correction
                                                   #     set:
                                                   #         0: disable
                                                   #         1: enable
                                                   #        -1: reset
                                                   #         (0xff000000 | n): set the average number to n, [1~255]
                                                   #     get: 
                                                   #         (val & 0xff): 0 => disable, 1 => enable, 2 => inited
                                                   #         ((val & 0xff00) >> 8): sequence
                                                   #         ((val & 0xff0000) >> 16): average number
                                                   #
TOUPCAM_OPTION_OVEREXP_POLICY         = 0x68       # Auto exposure over exposure policy: when overexposed,
                                                   #     0 => directly reduce the exposure time/gain to the minimum value; or
                                                   #     1 => reduce exposure time/gain in proportion to current and target brightness.
                                                   #     n(n>1) => first adjust the exposure time to (maximum automatic exposure time * maximum automatic exposure gain) * n / 1000, and then adjust according to the strategy of 1
                                                   # The advantage of policy 0 is that the convergence speed is faster, but there is black screen.
                                                   # Policy 1 avoids the black screen, but the convergence speed is slower.
                                                   # Default: 0
TOUPCAM_OPTION_READOUT_MODE           = 0x69       # Readout mode: 0 = IWR (Integrate While Read), 1 = ITR (Integrate Then Read)
                                                   #   The working modes of the detector readout circuit can be divided into two types: ITR and IWR. Using the IWR readout mode can greatly increase the frame rate. In the ITR mode, the integration of the (n+1)th frame starts after all the data of the nth frame are read out, while in the IWR mode, the data of the nth frame is read out at the same time when the (n+1)th frame is integrated
TOUPCAM_OPTION_TAILLIGHT              = 0x6a       # Turn on/off tail Led light: 0 => off, 1 => on; default: on
TOUPCAM_OPTION_LENSSTATE              = 0x6b       # Load/Save lens state to EEPROM: 0 => load, 1 => save
TOUPCAM_OPTION_AWB_CONTINUOUS         = 0x6c       # Auto White Balance: continuous mode
                                                   #     0:  disable (default)
                                                   #     n>0: every n millisecond(s)
                                                   #     n<0: every -n frame
TOUPCAM_OPTION_TECTARGET_RANGE        = 0x6d       # TEC target range: min(low 16 bits) = (short)(val & 0xffff), max(high 16 bits) = (short)((val >> 16) & 0xffff)
TOUPCAM_OPTION_CDS                    = 0x6e       # Correlated Double Sampling
TOUPCAM_OPTION_LOW_POWER_EXPOTIME     = 0x6f       # Low Power Consumption: Enable if exposure time is greater than the set value
TOUPCAM_OPTION_ZERO_OFFSET            = 0x70       # Sensor output offset to zero: 0 => disable, 1 => eanble; default: 0
TOUPCAM_OPTION_GVCP_TIMEOUT           = 0x71       # GVCP Timeout: millisecond, range = [3, 75], default: 15
                                                   #   Unless in very special circumstances, generally no modification is required, just use the default value
TOUPCAM_OPTION_GVCP_RETRY             = 0x72       # GVCP Retry: range = [2, 8], default: 4
                                                   #   Unless in very special circumstances, generally no modification is required, just use the default value
TOUPCAM_OPTION_GVSP_WAIT_PERCENT      = 0x73       # GVSP wait percent: range = [0, 100], default = (trigger mode: 100, realtime: 0, other: 1)
TOUPCAM_OPTION_RESET_SEQ_TIMESTAMP    = 0x74       # Reset to 0: 1 => seq; 2 => timestamp; 3 => both

TOUPCAM_PIXELFORMAT_RAW8              = 0x00
TOUPCAM_PIXELFORMAT_RAW10             = 0x01
TOUPCAM_PIXELFORMAT_RAW12             = 0x02
TOUPCAM_PIXELFORMAT_RAW14             = 0x03
TOUPCAM_PIXELFORMAT_RAW16             = 0x04
TOUPCAM_PIXELFORMAT_YUV411            = 0x05
TOUPCAM_PIXELFORMAT_VUYY              = 0x06
TOUPCAM_PIXELFORMAT_YUV444            = 0x07
TOUPCAM_PIXELFORMAT_RGB888            = 0x08
TOUPCAM_PIXELFORMAT_GMCY8             = 0x09   # map to RGGB 8 bits
TOUPCAM_PIXELFORMAT_GMCY12            = 0x0a   # map to RGGB 12 bits
TOUPCAM_PIXELFORMAT_UYVY              = 0x0b
TOUPCAM_PIXELFORMAT_RAW12PACK         = 0x0c
TOUPCAM_PIXELFORMAT_RAW11             = 0x0d
TOUPCAM_PIXELFORMAT_HDR8HL            = 0x0e   # HDR, Bitdepth: 8, Conversion Gain: High + Low
TOUPCAM_PIXELFORMAT_HDR10HL           = 0x0f   # HDR, Bitdepth: 10, Conversion Gain: High + Low
TOUPCAM_PIXELFORMAT_HDR11HL           = 0x10   # HDR, Bitdepth: 11, Conversion Gain: High + Low
TOUPCAM_PIXELFORMAT_HDR12HL           = 0x11   # HDR, Bitdepth: 12, Conversion Gain: High + Low
TOUPCAM_PIXELFORMAT_HDR14HL           = 0x12   # HDR, Bitdepth: 14, Conversion Gain: High + Low

TOUPCAM_FRAMEINFO_FLAG_SEQ            = 0x00000001   # frame sequence number
TOUPCAM_FRAMEINFO_FLAG_TIMESTAMP      = 0x00000002   # timestamp
TOUPCAM_FRAMEINFO_FLAG_EXPOTIME       = 0x00000004   # exposure time
TOUPCAM_FRAMEINFO_FLAG_EXPOGAIN       = 0x00000008   # exposure gain
TOUPCAM_FRAMEINFO_FLAG_BLACKLEVEL     = 0x00000010   # black level
TOUPCAM_FRAMEINFO_FLAG_SHUTTERSEQ     = 0x00000020   # sequence shutter counter
TOUPCAM_FRAMEINFO_FLAG_GPS            = 0x00000040   # GPS
TOUPCAM_FRAMEINFO_FLAG_AUTOFOCUS      = 0x00000080   # auto focus: uLum & uFV
TOUPCAM_FRAMEINFO_FLAG_COUNT          = 0x00000100   # timecount, framecount, tricount
TOUPCAM_FRAMEINFO_FLAG_STILL          = 0x00008000   # still image

TOUPCAM_IOCONTROLTYPE_GET_SUPPORTEDMODE            = 0x01  # 0x01 => Input, 0x02 => Output, (0x01 | 0x02) => support both Input and Output
TOUPCAM_IOCONTROLTYPE_GET_GPIODIR                  = 0x03  # 0x01 => Input, 0x02 => Output
TOUPCAM_IOCONTROLTYPE_SET_GPIODIR                  = 0x04
TOUPCAM_IOCONTROLTYPE_GET_FORMAT                   = 0x05  # 0x00 => not connected
                                                           # 0x01 => Tri-state: Tri-state mode (Not driven)
                                                           # 0x02 => TTL: TTL level signals
                                                           # 0x03 => LVDS: LVDS level signals
                                                           # 0x04 => RS422: RS422 level signals
                                                           # 0x05 => Opto-coupled
TOUPCAM_IOCONTROLTYPE_SET_FORMAT                   = 0x06
TOUPCAM_IOCONTROLTYPE_GET_OUTPUTINVERTER           = 0x07  # boolean, only support output signal
TOUPCAM_IOCONTROLTYPE_SET_OUTPUTINVERTER           = 0x08
TOUPCAM_IOCONTROLTYPE_GET_INPUTACTIVATION          = 0x09  # 0x00 => Rising edge, 0x01 => Falling edge, 0x02 => Level high, 0x03 => Level low
TOUPCAM_IOCONTROLTYPE_SET_INPUTACTIVATION          = 0x0a
TOUPCAM_IOCONTROLTYPE_GET_DEBOUNCERTIME            = 0x0b  # debouncer time in microseconds, range: [0, 20000]
TOUPCAM_IOCONTROLTYPE_SET_DEBOUNCERTIME            = 0x0c
TOUPCAM_IOCONTROLTYPE_GET_TRIGGERSOURCE            = 0x0d  # 0x00 => Opto-isolated input
                                                           # 0x01 => GPIO0
                                                           # 0x02 => GPIO1
                                                           # 0x03 => Counter
                                                           # 0x04 => PWM
                                                           # 0x05 => Software
TOUPCAM_IOCONTROLTYPE_SET_TRIGGERSOURCE            = 0x0e
TOUPCAM_IOCONTROLTYPE_GET_TRIGGERDELAY             = 0x0f  # Trigger delay time in microseconds, range: [0, 5000000]
TOUPCAM_IOCONTROLTYPE_SET_TRIGGERDELAY             = 0x10
TOUPCAM_IOCONTROLTYPE_GET_BURSTCOUNTER             = 0x11  # Burst Counter, range: [1 ~ 65535]
TOUPCAM_IOCONTROLTYPE_SET_BURSTCOUNTER             = 0x12
TOUPCAM_IOCONTROLTYPE_GET_COUNTERSOURCE            = 0x13  # 0x00 => Opto-isolated input, 0x01 => GPIO0, 0x02 => GPIO1
TOUPCAM_IOCONTROLTYPE_SET_COUNTERSOURCE            = 0x14
TOUPCAM_IOCONTROLTYPE_GET_COUNTERVALUE             = 0x15  # Counter Value, range: [1 ~ 65535]
TOUPCAM_IOCONTROLTYPE_SET_COUNTERVALUE             = 0x16
TOUPCAM_IOCONTROLTYPE_SET_RESETCOUNTER             = 0x18
TOUPCAM_IOCONTROLTYPE_GET_PWM_FREQ                 = 0x19
TOUPCAM_IOCONTROLTYPE_SET_PWM_FREQ                 = 0x1a
TOUPCAM_IOCONTROLTYPE_GET_PWM_DUTYRATIO            = 0x1b
TOUPCAM_IOCONTROLTYPE_SET_PWM_DUTYRATIO            = 0x1c
TOUPCAM_IOCONTROLTYPE_GET_PWMSOURCE                = 0x1d  # 0x00 => Opto-isolated input, 0x01 => GPIO0, 0x02 => GPIO1
TOUPCAM_IOCONTROLTYPE_SET_PWMSOURCE                = 0x1e
TOUPCAM_IOCONTROLTYPE_GET_OUTPUTMODE               = 0x1f  # 0x00 => Frame Trigger Wait
                                                           # 0x01 => Exposure Active
                                                           # 0x02 => Strobe
                                                           # 0x03 => User output
                                                           # 0x04 => Counter Output
                                                           # 0x05 => Timer Output
TOUPCAM_IOCONTROLTYPE_SET_OUTPUTMODE               = 0x20
TOUPCAM_IOCONTROLTYPE_GET_STROBEDELAYMODE          = 0x21  # boolean, 1 => delay, 0 => pre-delay; compared to exposure active signal
TOUPCAM_IOCONTROLTYPE_SET_STROBEDELAYMODE          = 0x22
TOUPCAM_IOCONTROLTYPE_GET_STROBEDELAYTIME          = 0x23  # Strobe delay or pre-delay time in microseconds, range: [0, 5000000]
TOUPCAM_IOCONTROLTYPE_SET_STROBEDELAYTIME          = 0x24
TOUPCAM_IOCONTROLTYPE_GET_STROBEDURATION           = 0x25  # Strobe duration time in microseconds, range: [0, 5000000]
TOUPCAM_IOCONTROLTYPE_SET_STROBEDURATION           = 0x26
TOUPCAM_IOCONTROLTYPE_GET_USERVALUE                = 0x27  # bit0 => Opto-isolated output
                                                           # bit1 => GPIO0 output
                                                           # bit2 => GPIO1 output
TOUPCAM_IOCONTROLTYPE_SET_USERVALUE                = 0x28
TOUPCAM_IOCONTROLTYPE_GET_UART_ENABLE              = 0x29  # enable: 1 => on; 0 => off
TOUPCAM_IOCONTROLTYPE_SET_UART_ENABLE              = 0x2a
TOUPCAM_IOCONTROLTYPE_GET_UART_BAUDRATE            = 0x2b  # baud rate: 0 => 9600; 1 => 19200; 2 => 38400; 3 => 57600; 4 => 115200
TOUPCAM_IOCONTROLTYPE_SET_UART_BAUDRATE            = 0x2c
TOUPCAM_IOCONTROLTYPE_GET_UART_LINEMODE            = 0x2d  # line mode: 0 => TX(GPIO_0)/RX(GPIO_1); 1 => TX(GPIO_1)/RX(GPIO_0)
TOUPCAM_IOCONTROLTYPE_SET_UART_LINEMODE            = 0x2e
TOUPCAM_IOCONTROLTYPE_GET_EXPO_ACTIVE_MODE         = 0x2f  # exposure time signal: 0 => specified line, 1 => common exposure time
TOUPCAM_IOCONTROLTYPE_SET_EXPO_ACTIVE_MODE         = 0x30
TOUPCAM_IOCONTROLTYPE_GET_EXPO_START_LINE          = 0x31  # exposure start line, default: 0
TOUPCAM_IOCONTROLTYPE_SET_EXPO_START_LINE          = 0x32
TOUPCAM_IOCONTROLTYPE_GET_EXPO_END_LINE            = 0x33  # exposure end line, default: 0
                                                           # end line must be no less than start line
TOUPCAM_IOCONTROLTYPE_SET_EXPO_END_LINE            = 0x34
TOUPCAM_IOCONTROLTYPE_GET_EXEVT_ACTIVE_MODE        = 0x35  # exposure event: 0 => specified line, 1 => common exposure time
TOUPCAM_IOCONTROLTYPE_SET_EXEVT_ACTIVE_MODE        = 0x36
TOUPCAM_IOCONTROLTYPE_GET_OUTPUTCOUNTERVALUE       = 0x37  # Output Counter Value, range: [0 ~ 65535]
TOUPCAM_IOCONTROLTYPE_SET_OUTPUTCOUNTERVALUE       = 0x38
TOUPCAM_IOCONTROLTYPE_SET_OUTPUT_PAUSE             = 0x3a  # Output pause: 1 => puase, 0 => unpause
TOUPCAM_IOCONTROLTYPE_GET_INPUT_STATE              = 0x3b  # Input state: 0 (low level) or 1 (high level)
TOUPCAM_IOCONTROLTYPE_GET_USER_PULSE_HIGH          = 0x3d  # User pulse high level time: us
TOUPCAM_IOCONTROLTYPE_SET_USER_PULSE_HIGH          = 0x3e
TOUPCAM_IOCONTROLTYPE_GET_USER_PULSE_LOW           = 0x3f  # User pulse low level time: us
TOUPCAM_IOCONTROLTYPE_SET_USER_PULSE_LOW           = 0x40
TOUPCAM_IOCONTROLTYPE_GET_USER_PULSE_NUMBER        = 0x41  # User pulse number: default 0
TOUPCAM_IOCONTROLTYPE_SET_USER_PULSE_NUMBER        = 0x42
TOUPCAM_IOCONTROLTYPE_GET_EXTERNAL_TRIGGER_NUMBER  = 0x43  # External trigger number
TOUPCAM_IOCONTROLTYPE_GET_DEBOUNCER_TRIGGER_NUMBER = 0x45  # Trigger signal number after debounce
TOUPCAM_IOCONTROLTYPE_GET_EFFECTIVE_TRIGGER_NUMBER = 0x47  # Effective trigger signal number

TOUPCAM_IOCONTROL_DELAYTIME_MAX                 = 5 * 1000 * 1000

TOUPCAM_AFMODE_CALIBRATE      = 0x0   # lens calibration mode
TOUPCAM_AFMODE_MANUAL         = 0x1   # manual focus mode
TOUPCAM_AFMODE_ONCE           = 0x2   # onepush focus mode
TOUPCAM_AFMODE_AUTO           = 0x3   # autofocus mode
TOUPCAM_AFMODE_NONE           = 0x4   # no active selection of focus mode
TOUPCAM_AFMODE_IDLE           = 0x5

TOUPCAM_AFSTATUS_NA           = 0x0   # Not available
TOUPCAM_AFSTATUS_PEAKPOINT    = 0x1   # Focus completed, find the focus position
TOUPCAM_AFSTATUS_DEFOCUS      = 0x2   # End of focus, defocus
TOUPCAM_AFSTATUS_NEAR         = 0x3   # Focusing ended, object too close
TOUPCAM_AFSTATUS_FAR          = 0x4   # Focusing ended, object too far
TOUPCAM_AFSTATUS_ROICHANGED   = 0x5   # Focusing ends, roi changes
TOUPCAM_AFSTATUS_SCENECHANGED = 0x6   # Focusing ends, scene changes
TOUPCAM_AFSTATUS_MODECHANGED  = 0x7   # The end of focusing and the change in focusing mode is usually determined by the user moderator
TOUPCAM_AFSTATUS_UNFINISH     = 0x8   # The focus is not complete. At the beginning of focusing, it will be set as incomplete
    
# AAF: Astro Auto Focuser
TOUPCAM_AAF_SETPOSITION     = 0x01
TOUPCAM_AAF_GETPOSITION     = 0x02
TOUPCAM_AAF_SETZERO         = 0x03
TOUPCAM_AAF_SETDIRECTION    = 0x05
TOUPCAM_AAF_GETDIRECTION    = 0x06
TOUPCAM_AAF_SETMAXINCREMENT = 0x07
TOUPCAM_AAF_GETMAXINCREMENT = 0x08
TOUPCAM_AAF_SETFINE         = 0x09
TOUPCAM_AAF_GETFINE         = 0x0a
TOUPCAM_AAF_SETCOARSE       = 0x0b
TOUPCAM_AAF_GETCOARSE       = 0x0c
TOUPCAM_AAF_SETBUZZER       = 0x0d
TOUPCAM_AAF_GETBUZZER       = 0x0e
TOUPCAM_AAF_SETBACKLASH     = 0x0f
TOUPCAM_AAF_GETBACKLASH     = 0x10
TOUPCAM_AAF_GETAMBIENTTEMP  = 0x12
TOUPCAM_AAF_GETTEMP         = 0x14  # in 0.1 degrees Celsius, such as: 32 means 3.2 degrees Celsius
TOUPCAM_AAF_ISMOVING        = 0x16
TOUPCAM_AAF_HALT            = 0x17
TOUPCAM_AAF_SETMAXSTEP      = 0x1b
TOUPCAM_AAF_GETMAXSTEP      = 0x1c
TOUPCAM_AAF_GETSTEPSIZE     = 0x1e
TOUPCAM_AAF_RANGEMIN        = 0xfd  # Range: min value
TOUPCAM_AAF_RANGEMAX        = 0xfe  # Range: max value
TOUPCAM_AAF_RANGEDEF        = 0xff  # Range: default value

# hardware level range mode
TOUPCAM_LEVELRANGE_MANUAL   = 0x0000 # manual
TOUPCAM_LEVELRANGE_ONCE     = 0x0001 # once
TOUPCAM_LEVELRANGE_CONTINUE = 0x0002 # continue
TOUPCAM_LEVELRANGE_ROI      = 0xffff # update roi rect only

# see rwc_Flash
TOUPCAM_FLASH_SIZE      = 0x00    # query total size
TOUPCAM_FLASH_EBLOCK    = 0x01    # query erase block size
TOUPCAM_FLASH_RWBLOCK   = 0x02    # query read/write block size
TOUPCAM_FLASH_STATUS    = 0x03    # query status
TOUPCAM_FLASH_READ      = 0x04    # read
TOUPCAM_FLASH_WRITE     = 0x05    # write
TOUPCAM_FLASH_ERASE     = 0x06    # erase

# HRESULT: error code
S_OK            = 0x00000000 # Success
S_FALSE         = 0x00000001 # Yet another success # Remark: Different from S_OK, such as internal values and user-set values have coincided, equivalent to noop
E_UNEXPECTED    = 0x8000ffff # Catastrophic failure # Remark: Generally indicates that the conditions are not met, such as calling put_Option setting some options that do not support modification when the camera is running, and so on
E_NOTIMPL       = 0x80004001 # Not supported or not implemented # Remark: This feature is not supported on this model of camera
E_ACCESSDENIED  = 0x80070005 # Permission denied # Remark: The program on Linux does not have permission to open the USB device, please enable udev rules file or run as root
E_OUTOFMEMORY   = 0x8007000e # Out of memory
E_INVALIDARG    = 0x80070057 # One or more arguments are not valid
E_POINTER       = 0x80004003 # Pointer that is not valid # Remark: Pointer is NULL
E_FAIL          = 0x80004005 # Generic failure
E_WRONG_THREAD  = 0x8001010e # Call function in the wrong thread
E_GEN_FAILURE   = 0x8007001f # Device not functioning # Remark: It is generally caused by hardware errors, such as cable problems, USB port problems, poor contact, camera hardware damage, etc
E_BUSY          = 0x800700aa # The requested resource is in use # Remark: The camera is already in use, such as duplicated opening/starting the camera, or being used by other application, etc
E_PENDING       = 0x8000000a # The data necessary to complete this operation is not yet available # Remark: No data is available at this time
E_TIMEOUT       = 0x8001011f # This operation returned because the timeout period expired

TOUPCAM_EXPOGAIN_DEF             = 100      # exposure gain, default value
TOUPCAM_EXPOGAIN_MIN             = 100      # exposure gain, minimum value
TOUPCAM_TEMP_DEF                 = 6503     # color temperature, default value
TOUPCAM_TEMP_MIN                 = 2000     # color temperature, minimum value
TOUPCAM_TEMP_MAX                 = 15000    # color temperature, maximum value
TOUPCAM_TINT_DEF                 = 1000     # tint
TOUPCAM_TINT_MIN                 = 200      # tint
TOUPCAM_TINT_MAX                 = 2500     # tint
TOUPCAM_HUE_DEF                  = 0        # hue
TOUPCAM_HUE_MIN                  = -180     # hue
TOUPCAM_HUE_MAX                  = 180      # hue
TOUPCAM_SATURATION_DEF           = 128      # saturation
TOUPCAM_SATURATION_MIN           = 0        # saturation
TOUPCAM_SATURATION_MAX           = 255      # saturation
TOUPCAM_BRIGHTNESS_DEF           = 0        # brightness
TOUPCAM_BRIGHTNESS_MIN           = -255     # brightness
TOUPCAM_BRIGHTNESS_MAX           = 255      # brightness
TOUPCAM_CONTRAST_DEF             = 0        # contrast
TOUPCAM_CONTRAST_MIN             = -255     # contrast
TOUPCAM_CONTRAST_MAX             = 255      # contrast
TOUPCAM_GAMMA_DEF                = 100      # gamma
TOUPCAM_GAMMA_MIN                = 20       # gamma
TOUPCAM_GAMMA_MAX                = 180      # gamma
TOUPCAM_AETARGET_DEF             = 120      # target of auto exposure
TOUPCAM_AETARGET_MIN             = 16       # target of auto exposure
TOUPCAM_AETARGET_MAX             = 220      # target of auto exposure
TOUPCAM_WBGAIN_DEF               = 0        # white balance gain
TOUPCAM_WBGAIN_MIN               = -127     # white balance gain
TOUPCAM_WBGAIN_MAX               = 127      # white balance gain
TOUPCAM_BLACKLEVEL_MIN           = 0        # minimum black level
TOUPCAM_BLACKLEVEL8_MAX          = 31       # maximum black level for bitdepth = 8
TOUPCAM_BLACKLEVEL10_MAX         = 31 * 4   # maximum black level for bitdepth = 10
TOUPCAM_BLACKLEVEL11_MAX         = 31 * 8   # maximum black level for bitdepth = 11
TOUPCAM_BLACKLEVEL12_MAX         = 31 * 16  # maximum black level for bitdepth = 12
TOUPCAM_BLACKLEVEL14_MAX         = 31 * 64  # maximum black level for bitdepth = 14
TOUPCAM_BLACKLEVEL16_MAX         = 31 * 256 # maximum black level for bitdepth = 16
TOUPCAM_SHARPENING_STRENGTH_DEF  = 0        # sharpening strength
TOUPCAM_SHARPENING_STRENGTH_MIN  = 0        # sharpening strength
TOUPCAM_SHARPENING_STRENGTH_MAX  = 500      # sharpening strength
TOUPCAM_SHARPENING_RADIUS_DEF    = 2        # sharpening radius
TOUPCAM_SHARPENING_RADIUS_MIN    = 1        # sharpening radius
TOUPCAM_SHARPENING_RADIUS_MAX    = 10       # sharpening radius
TOUPCAM_SHARPENING_THRESHOLD_DEF = 0        # sharpening threshold
TOUPCAM_SHARPENING_THRESHOLD_MIN = 0        # sharpening threshold
TOUPCAM_SHARPENING_THRESHOLD_MAX = 255      # sharpening threshold
TOUPCAM_AUTOEXPO_THRESHOLD_DEF   = 5        # auto exposure threshold
TOUPCAM_AUTOEXPO_THRESHOLD_MIN   = 2        # auto exposure threshold
TOUPCAM_AUTOEXPO_THRESHOLD_MAX   = 15       # auto exposure threshold
TOUPCAM_AUTOEXPO_DAMP_DEF        = 0        # auto exposure damping coefficient: thousandths
TOUPCAM_AUTOEXPO_DAMP_MIN        = 0        # auto exposure damping coefficient: thousandths
TOUPCAM_AUTOEXPO_DAMP_MAX        = 1000     # auto exposure damping coefficient: thousandths
TOUPCAM_BANDWIDTH_DEF            = 100      # bandwidth
TOUPCAM_BANDWIDTH_MIN            = 1        # bandwidth
TOUPCAM_BANDWIDTH_MAX            = 100      # bandwidth
TOUPCAM_DENOISE_DEF              = 0        # denoise
TOUPCAM_DENOISE_MIN              = 0        # denoise
TOUPCAM_DENOISE_MAX              = 100      # denoise
TOUPCAM_HEARTBEAT_MIN            = 100      # millisecond
TOUPCAM_HEARTBEAT_MAX            = 10000    # millisecond
TOUPCAM_AE_PERCENT_MIN           = 0        # auto exposure percent; 0 or 100 => full roi average, means "disabled"
TOUPCAM_AE_PERCENT_MAX           = 100
TOUPCAM_AE_PERCENT_DEF           = 10       # auto exposure percent: enabled, percentage = 10%
TOUPCAM_NOPACKET_TIMEOUT_MIN     = 500      # no packet timeout minimum: 500ms
TOUPCAM_NOFRAME_TIMEOUT_MIN      = 500      # no frame timeout minimum: 500ms
TOUPCAM_DYNAMIC_DEFECT_T1_MIN    = 0        # dynamic defect pixel correction, dead pixel ratio: the smaller the dead ratio is, the more stringent the conditions for processing dead pixels are, and fewer pixels will be processed
TOUPCAM_DYNAMIC_DEFECT_T1_MAX    = 100      # means: 1.0
TOUPCAM_DYNAMIC_DEFECT_T1_DEF    = 90       # means: 0.9
TOUPCAM_DYNAMIC_DEFECT_T2_MIN    = 0        # dynamic defect pixel correction, hot pixel ratio: the smaller the hot ratio is, the more stringent the conditions for processing hot pixels are, and fewer pixels will be processed
TOUPCAM_DYNAMIC_DEFECT_T2_MAX    = 100
TOUPCAM_DYNAMIC_DEFECT_T2_DEF    = 90
TOUPCAM_HDR_K_MIN                = 1        # HDR synthesize
TOUPCAM_HDR_K_MAX                = 25500
TOUPCAM_HDR_B_MIN                = 0
TOUPCAM_HDR_B_MAX                = 65535
TOUPCAM_HDR_THRESHOLD_MIN        = 0
TOUPCAM_HDR_THRESHOLD_MAX        = 4094
TOUPCAM_CDS_MIN                  = 0
TOUPCAM_CDS_MAX                  = 4094

def TDIBWIDTHBYTES(bits):
    return ((bits + 31) // 32 * 4)

"""
------------------------------------------------------------------|
| Parameter               |   Range       |   Default             |
|-----------------------------------------------------------------|
| Auto Exposure Target    |   16~235      |   120                 |
| Exposure Gain           |   100~        |   100                 |
| Temp                    |   1000~25000  |   6503                |
| Tint                    |   100~2500    |   1000                |
| LevelRange              |   0~255       |   Low = 0, High = 255 |
| Contrast                |   -255~255    |   0                   |
| Hue                     |   -180~180    |   0                   |
| Saturation              |   0~255       |   128                 |
| Brightness              |   -255~255    |   0                   |
| Gamma                   |   20~180      |   100                 |
| WBGain                  |   -127~127    |   0                   |
------------------------------------------------------------------|
"""

class ToupcamResolution:
    def __init__(self, w, h):
        self.width = w
        self.height = h

class ToupcamFocusMotor:
    def __init__(self, imax, imin, idef, imaxabs, iminabs, zoneh, zonev):
        self.imax = imax                 # maximum auto focus sensor board positon
        self.imin = imin                 # minimum auto focus sensor board positon
        self.idef = idef                 # conjugate calibration positon
        self.imaxabs = imaxabs           # maximum absolute auto focus sensor board positon, micrometer
        self.iminabs = iminabs           # maximum absolute auto focus sensor board positon, micrometer
        self.zoneh = zoneh               # zone horizontal
        self.zonev = zonev               # zone vertical

class ToupcamFrameInfoV3:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.flag = 0                    # TOUPCAM_FRAMEINFO_FLAG_xxxx
        self.seq = 0                     # frame sequence number
        self.timestamp = 0               # microsecond
        self.shutterseq = 0              # sequence shutter counter
        self.expotime = 0                # expotime
        self.expogain = 0                # expogain
        self.blacklevel = 0              # black level

class ToupcamGps:
    def __init__(self):
       self.utcstart = 0    # exposure start time: nanosecond since epoch (00:00:00 UTC on Thursday, 1 January 1970, see https://en.wikipedia.org/wiki/Unix_time)
       self.utcend = 0      # exposure end time
       self.longitude = 0   # millionth of a degree, 0.000001 degree
       self.latitude = 0
       self.altitude = 0    # millimeter
       self.satellite = 0   # number of satellite
       self.reserved = 0    # not used

class ToupcamFrameInfoV4:
    def __init__(self):
        self.v3 = ToupcamFrameInfoV3()
        self.reserved = 0
        self.uLum = 0
        self.uFV = 0
        self.timecount = 0
        self.framecount = 0
        self.tricount = 0
        self.gps = ToupcamGps()

class ToupcamFrameInfoV2:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.flag = 0                    # TOUPCAM_FRAMEINFO_FLAG_xxxx
        self.seq = 0                     # frame sequence number
        self.timestamp = 0               # microsecond

class ToupcamModelV2:                    # camera model v2
    def __init__(self, name, flag, maxspeed, preview, still, maxfanspeed, ioctrol, xpixsz, ypixsz, res):
        self.name = name                 # model name, in Windows, we use unicode
        self.flag = flag                 # TOUPCAM_FLAG_xxx, 64 bits
        self.maxspeed = maxspeed         # number of speed level, same as Toupcam_get_MaxSpeed(), the speed range = [0, maxspeed], closed interval
        self.preview = preview           # number of preview resolution, same as Toupcam_get_ResolutionNumber()
        self.still = still               # number of still resolution, same as Toupcam_get_StillResolutionNumber()
        self.maxfanspeed = maxfanspeed   # maximum fan speed, fan speed range = [0, max], closed interval
        self.ioctrol = ioctrol           # number of input/output control
        self.xpixsz = xpixsz             # physical pixel size in micrometer
        self.ypixsz = ypixsz             # physical pixel size in micrometer
        self.res = res                   # ToupcamResolution

class ToupcamDeviceV2:
    def __init__(self, displayname, id, model):
        self.displayname = displayname   # display name
        self.id = id                     # unique and opaque id of a connected camera, for Toupcam_Open
        self.model = model               # ToupcamModelV2

class ToupcamSelfTrigger:
    def __init__(self, sensingLeft, sensingTop, sensingWidth, sensingHeight, hThreshold, lThreshold, expoTime, expoGain, hCount, lCount, reserved):
        self.sensingLeft = sensingLeft
        self.sensingTop = sensingTop
        self.sensingWidth = sensingWidth
        self.sensingHeight = sensingHeight  # Sensing Area
        self.hThreshold = hThreshold
        self.lThreshold = lThreshold        # threshold High side, threshold Low side
        self.expoTime = expoTime            # Exposure Time
        self.expoGain = expoGain            # Exposure Gain
        self.hCount = hCount
        self.lCount = lCount                # Count threshold High side, Count threshold Low side, thousandths of Sensing Area
        self.reserved = reserved

class ToupcamAFState:
    def __init__(self, AF_Mode, AF_Status, AF_LensAP_Update_Flag, AF_LensManual_Flag, Reserved0, Reserved1):
        self.AF_Mode = AF_Mode
        self.AF_Status = AF_Status
        self.AF_LensAP_Update_Flag = AF_LensAP_Update_Flag  # mark for whether the lens aperture is calibrated
        self.AF_LensManual_Flag = AF_LensManual_Flag        # if true, allows manual operation
        self.Reserved0 = Reserved0
        self.Reserved1 = Reserved1

if sys.platform == 'win32':
    class HRESULTException(OSError):
        def __init__(self, hr):
            OSError.__init__(self, None, ctypes.FormatError(hr).strip(), None)
            self.hr = hr
else:
    class HRESULTException(Exception):
        def __init__(self, hr):
            self.hr = hr

class Toupcam:
    class __Resolution(ctypes.Structure):
        _fields_ = [('width', ctypes.c_uint),
                    ('height', ctypes.c_uint)]

    class __RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_int),
                    ('top', ctypes.c_int),
                    ('right', ctypes.c_int),
                    ('bottom', ctypes.c_int)]

    class __ModelV2(ctypes.Structure):
        pass
        
    class __DeviceV2(ctypes.Structure):
        pass

    class __FocusMotor(ctypes.Structure):
        _fields_ = [('imax', ctypes.c_int),                # maximum auto focus sensor board positon
                    ('imin', ctypes.c_int),                # minimum auto focus sensor board positon
                    ('idef', ctypes.c_int),                # conjugate calibration positon
                    ('imaxabs', ctypes.c_int),             # maximum absolute auto focus sensor board positon, micrometer
                    ('iminabs', ctypes.c_int),             # maximum absolute auto focus sensor board positon, micrometer
                    ('zoneh', ctypes.c_int),               # zone horizontal
                    ('zonev', ctypes.c_int)]               # zone vertical

    class __FrameInfoV3(ctypes.Structure):
        _fields_ = [('width', ctypes.c_uint),
                    ('height', ctypes.c_uint),
                    ('flag', ctypes.c_uint),               # TOUPCAM_FRAMEINFO_FLAG_xxxx
                    ('seq', ctypes.c_uint),                # frame sequence number
                    ('timestamp', ctypes.c_longlong),      # microsecond
                    ('shutterseq', ctypes.c_uint),         # sequence shutter counter
                    ('expotime', ctypes.c_uint),           # expotime
                    ('expogain', ctypes.c_ushort),         # expogain
                    ('blacklevel', ctypes.c_ushort)]       # black level

    class __Gps(ctypes.Structure):
        _fields_ = [('utcstart', ctypes.c_longlong),       # UTC: exposure start time
                    ('utcend', ctypes.c_longlong),         # exposure end time
                    ('longitude', ctypes.c_int),           # millionth of a degree, 0.000001 degree
                    ('latitude', ctypes.c_int),
                    ('altitude', ctypes.c_int),            # millimeter
                    ('satellite', ctypes.c_ushort),        # number of satellite
                    ('reserved', ctypes.c_ushort)]         # not used

    class __FrameInfoV4(ctypes.Structure):
        pass

    class __FrameInfoV2(ctypes.Structure):
        _fields_ = [('width', ctypes.c_uint),
                    ('height', ctypes.c_uint),
                    ('flag', ctypes.c_uint),               # TOUPCAM_FRAMEINFO_FLAG_xxxx
                    ('seq', ctypes.c_uint),                # frame sequence number
                    ('timestamp', ctypes.c_longlong)]      # microsecond

    class __SelfTrigger(ctypes.Structure):
        _fields_ = [('sensingLeft', ctypes.c_uint),
                    ('sensingTop', ctypes.c_uint),
                    ('sensingWidth', ctypes.c_uint),
                    ('sensingHeight', ctypes.c_uint),      # Sensing Area
                    ('hThreshold', ctypes.c_uint),
                    ('lThreshold', ctypes.c_uint),         # threshold High side, threshold Low side
                    ('expoTime', ctypes.c_uint),           # Exposure Time
                    ('expoGain', ctypes.c_ushort),         # Exposure Gain
                    ('hCount', ctypes.c_ushort),
                    ('lCount', ctypes.c_ushort),           # Count threshold High side, Count threshold Low side, thousandths of Sensing Area
                    ('reserved', ctypes.c_ushort)]

    class __AFState(ctypes.Structure):
        _fields_ = [('AF_Status', ctypes.c_uint),
                    ('AF_LensAP_Update_Flag', ctypes.c_byte),  # mark for whether the lens aperture is calibrated
                    ('AF_LensManual_Flag', ctypes.c_byte),     # if true, allows manual operation
                    ('Reserved0', ctypes.c_byte),
                    ('Reserved1', ctypes.c_byte)]

    if sys.platform == 'win32':
        __EVENT_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_uint, ctypes.py_object)
        __PROGRESS_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_int, ctypes.py_object)
        __HOTPLUG_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_void_p)
        __HISTOGRAM_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.py_object)
    else:
        __EVENT_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.py_object)
        __PROGRESS_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.py_object)
        __HOTPLUG_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
        __HISTOGRAM_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.py_object)

    __lib = None
    __progress_fun = None
    __progress_ctx = None
    __progress_cb = None
    __hotplug_fun = None
    __hotplug_ctx = None
    __hotplug_cb = None
    __gigeenable_fun = None
    __gigeenable_ctx = None
    __gigeenable_cb = None

    @staticmethod
    def __errcheck(result, fun, args):
        if result < 0:
            raise HRESULTException(result)
        return args

    @staticmethod
    def __convertStr(x):
        if isinstance(x, str):
            return x
        else:
            return x.decode('ascii')

    @classmethod
    def Version(cls):
        """get the version of this dll, which is: 57.26813.20241028"""
        cls.__initlib()
        return cls.__lib.Toupcam_Version()

    @staticmethod
    def __convertResolution(a):
        t = []
        for i in range(0, a.preview):
            t.append(ToupcamResolution(a.res[i].width, a.res[i].height))
        return t

    @staticmethod
    def __convertModel(a):
        t = ToupcamModelV2(__class__.__convertStr(a.name), a.flag, a.maxspeed, a.preview, a.still, a.maxfanspeed, a.ioctrol, a.xpixsz, a.ypixsz, __class__.__convertResolution(a))
        return t

    @staticmethod
    def __convertDevice(a):
        return ToupcamDeviceV2(__class__.__convertStr(a.displayname), __class__.__convertStr(a.id), __class__.__convertModel(a.model.contents))

    @staticmethod
    def __gigeEnableCallbackFun(ctx):
        if __class__.__gigeenable_fun:
            __class__.__gigeenable_fun(__class__.__gigeenable_ctx)

    @classmethod
    def GigeEnable(cls, fun, ctx):
        """Initialize support for GigE cameras. If online/offline notifications are not required, the callback function can be set to None"""
        cls.__initlib()
        cls.__gigeenable_fun = fun
        cls.__gigeenable_ctx = ctx
        if cls.__gigeenable_fun is None:
            cls.__lib.Toupcam_GigeEnable(cls.__HOTPLUG_CALLBACK(0), None)
        else:
            cls.__gigeenable_cb = cls.__HOTPLUG_CALLBACK(cls.__gigeEnableCallbackFun)
            cls.__lib.Toupcam_GigeEnable(cls.__gigeenable_cb, None)

    @staticmethod
    def __hotplugCallbackFun(ctx):
        if __class__.__hotplug_fun:
            __class__.__hotplug_fun(__class__.__hotplug_ctx)

    @classmethod
    def HotPlug(cls, fun, ctx):
        """
        This function is only available on macOS and Linux, it's unnecessary on Windows & Android. To process the device plug in / pull out:
            (1) On Windows, please refer to the MSDN
                (a) Device Management, https://docs.microsoft.com/en-us/windows/win32/devio/device-management
                (b) Detecting Media Insertion or Removal, https://docs.microsoft.com/en-us/windows/win32/devio/detecting-media-insertion-or-removal
            (2) On Android, please refer to https://developer.android.com/guide/topics/connectivity/usb/host
            (3) On Linux / macOS, please call this function to register the callback function.
                When the device is inserted or pulled out, you will be notified by the callback funcion, and then call Toupcam_EnumV2(...) again to enum the cameras.
            (4) On macOS, IONotificationPortCreate series APIs can also be used as an alternative.
        """
        if sys.platform == 'win32' or sys.platform == 'android':
            raise HRESULTException(0x80004001)
        else:
            cls.__initlib()
            cls.__hotplug_fun = fun
            cls.__hotplug_ctx = ctx
            if cls.__hotplug_fun is None:
                cls.__lib.Toupcam_HotPlug(cls.__HOTPLUG_CALLBACK(0), None)
            else:
                cls.__hotplug_cb = cls.__HOTPLUG_CALLBACK(cls.__hotplugCallbackFun)
                cls.__lib.Toupcam_HotPlug(__hotplug_cb, None)

    @classmethod
    def EnumV2(cls):
        cls.__initlib()
        a = (cls.__DeviceV2 * TOUPCAM_MAX)()
        n = cls.__lib.Toupcam_EnumV2(a)
        arr = []
        for i in range(0, n):
            arr.append(cls.__convertDevice(a[i]))
        return arr

    @classmethod
    def EnumWithName(cls):
        cls.__initlib()
        a = (cls.__DeviceV2 * TOUPCAM_MAX)()
        n = cls.__lib.Toupcam_EnumWithName(a)
        arr = []
        for i in range(0, n):
            arr.append(cls.__convertDevice(a[i]))
        return arr

    def __init__(self, h):
        """the object of Toupcam must be obtained by classmethod Open or OpenByIndex, it cannot be obtained by obj = toupcam.Toupcam()"""
        self.__h = h
        self.__fun = None
        self.__ctx = None
        self.__cb = None
        self.__ctxhistogram = None
        self.__cbhistogram = None

    def __del__(self):
        self.Close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.Close()

    def __nonzero__(self):
        return self.__h is not None

    def __bool__(self):
        return self.__h is not None

    @classmethod
    def Open(cls, camId):
        """
        the object of Toupcam must be obtained by classmethod Open or OpenByIndex, it cannot be obtained by obj = toupcam.Toupcam()
        Open(None) means try to Open the first enumerated camera
        """
        cls.__initlib()
        if camId is None:
            h = cls.__lib.Toupcam_Open(None)
        elif sys.platform == 'win32':
            h = cls.__lib.Toupcam_Open(camId)
        else:
            h = cls.__lib.Toupcam_Open(camId.encode('ascii'))
        if h is None:
            return None
        return __class__(h)

    @classmethod
    def OpenByIndex(cls, index):
        """
        the object of Toupcam must be obtained by classmethod Open or OpenByIndex, it cannot be obtained by obj = toupcam.Toupcam()

        the same with Toupcam_Open, but use the index as the parameter. such as:
        index == 0, open the first camera,
        index == 1, open the second camera,
        etc
        """
        cls.__initlib()
        h = cls.__lib.Toupcam_OpenByIndex(index)
        if h is None:
            return None
        return __class__(h)

    def Close(self):
        if self.__h:
            self.__lib.Toupcam_Close(self.__h)
            self.__h = None

    @staticmethod
    def __eventCallbackFun(nEvent, ctx):
        if ctx:
            ctx.__callbackFun(nEvent)

    def __callbackFun(self, nEvent):
        if self.__fun:
            self.__fun(nEvent, self.__ctx)

    def StartPullModeWithCallback(self, fun, ctx):
        self.__fun = fun
        self.__ctx = ctx
        self.__cb = __class__.__EVENT_CALLBACK(__class__.__eventCallbackFun)
        self.__lib.Toupcam_StartPullModeWithCallback(self.__h, self.__cb, ctypes.py_object(self))

    @staticmethod
    def __convertFrameInfoV3(pInfo, x):
        pInfo.width = x.width
        pInfo.height = x.height
        pInfo.flag = x.flag
        pInfo.seq = x.seq
        pInfo.shutterseq = x.shutterseq
        pInfo.timestamp = x.timestamp
        pInfo.expotime = x.expotime
        pInfo.expogain = x.expogain
        pInfo.blacklevel = x.blacklevel
        
    @staticmethod
    def __convertGps(gps, x):
        gps.utcstart = x.utcstart
        gps.utcend = x.utcend
        gps.longitude = x.longitude
        gps.latitude = x.latitude
        gps.altitude = x.altitude
        gps.satellite = x.satellite
        gps.reserved = x.reserved

    @staticmethod
    def __convertFrameInfoV4(pInfo, x):
        __class__.__convertFrameInfoV3(pInfo.v3, x.v3)
        pInfo.reserved = x.reserved
        pInfo.uLum = x.uLum
        pInfo.uFV = x.uFV
        pInfo.timecount = x.timecount
        pInfo.framecount = x.framecount
        pInfo.tricount = x.tricount
        __class__.__convertGps(pInfo.gps, x.gps)

    @staticmethod
    def __convertFrameInfoV2(pInfo, x):
        pInfo.width = x.width
        pInfo.height = x.height
        pInfo.flag = x.flag
        pInfo.seq = x.seq
        pInfo.timestamp = x.timestamp

    """
        nWaitMS: The timeout interval, in milliseconds. If a non-zero value is specified, the function either successfully fetches the image or waits for a timeout.
                 If nWaitMS is zero, the function does not wait when there are no images to fetch; It always returns immediately; this is equal to PullImageV4.
        bStill: to pull still image, set to 1, otherwise 0
        bits: 24 (RGB24), 32 (RGB32), 48 (RGB48), 8 (Grey), 16 (Grey), 64 (RGB64).
              In RAW mode, this parameter is ignored.
              bits = 0 means using default bits (see TOUPCAM_OPTION_RGB).
              When bits and TOUPCAM_OPTION_RGB are inconsistent, format conversion will have to be performed, resulting in loss of efficiency.
              See the following bits and TOUPCAM_OPTION_RGB correspondence table:
                ----------------------------------------------------------------------------------------------------------------------
                | TOUPCAM_OPTION_RGB |   0 (RGB24)   |   1 (RGB48)   |   2 (RGB32)   |   3 (Grey8)   |  4 (Grey16)   |   5 (RGB64)   |
                |--------------------|---------------|---------------|---------------|---------------|---------------|---------------|
                | bits = 0           |      24       |       48      |      32       |       8       |       16      |       64      |
                |--------------------|---------------|---------------|---------------|---------------|---------------|---------------|
                | bits = 24          |      24       |       NA      | Convert to 24 | Convert to 24 |       NA      |       NA      |
                |--------------------|---------------|---------------|---------------|---------------|---------------|---------------|
                | bits = 32          | Convert to 32 |       NA      |       32      | Convert to 32 |       NA      |       NA      |
                |--------------------|---------------|---------------|---------------|---------------|---------------|---------------|
                | bits = 48          |      NA       |       48      |       NA      |       NA      | Convert to 48 | Convert to 48 |
                |--------------------|---------------|---------------|---------------|---------------|---------------|---------------|
                | bits = 8           | Convert to 8  |       NA      | Convert to 8  |       8       |       NA      |       NA      |
                |--------------------|---------------|---------------|---------------|---------------|---------------|---------------|
                | bits = 16          |      NA       | Convert to 16 |       NA      |       NA      |       16      | Convert to 16 |
                |--------------------|---------------|-----------|-------------------|---------------|---------------|---------------|
                | bits = 64          |      NA       | Convert to 64 |       NA      |       NA      | Convert to 64 |       64      |
                |--------------------|---------------|---------------|---------------|---------------|---------------|---------------|
        
        rowPitch: The distance from one row to the next row. rowPitch = 0 means using the default row pitch. rowPitch = -1 means zero padding, see below:
                ----------------------------------------------------------------------------------------------
                | format                             | 0 means default row pitch     | -1 means zero padding |
                |------------------------------------|-------------------------------|-----------------------|
                | RGB       | RGB24                  | TDIBWIDTHBYTES(24 * Width)    | Width * 3             |
                |           | RGB32                  | Width * 4                     | Width * 4             |
                |           | RGB48                  | TDIBWIDTHBYTES(48 * Width)    | Width * 6             |
                |           | GREY8                  | TDIBWIDTHBYTES(8 * Width)     | Width                 |
                |           | GREY16                 | TDIBWIDTHBYTES(16 * Width)    | Width * 2             |
                |           | RGB64                  | Width * 8                     | Width * 8             |
                |-----------|------------------------|-------------------------------|-----------------------|
                | RAW       | 8bits Mode             | Width                         | Width                 |
                |           | 10/12/14/16bits Mode   | Width * 2                     | Width * 2             |
                |-----------|------------------------|-------------------------------|-----------------------|
    """
    def PullImageV4(self, pImageData, bStill, bits, rowPitch, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_PullImageV4(self.__h, pImageData, bStill, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV4()
            self.__lib.Toupcam_PullImageV4(self.__h, pImageData, bStill, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV4(pInfo, x)

    def WaitImageV4(self, nWaitMS, pImageData, bStill, bits, rowPitch, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_WaitImageV4(self.__h, nWaitMS, pImageData, bStill, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV4()
            self.__lib.Toupcam_WaitImageV4(self.__h, nWaitMS, pImageData, bStill, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV4(pInfo, x)

    def PullImageV3(self, pImageData, bStill, bits, rowPitch, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_PullImageV3(self.__h, pImageData, bStill, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV3()
            self.__lib.Toupcam_PullImageV3(self.__h, pImageData, bStill, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV3(pInfo, x)

    def WaitImageV3(self, nWaitMS, pImageData, bStill, bits, rowPitch, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_WaitImageV3(self.__h, nWaitMS, pImageData, bStill, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV3()
            self.__lib.Toupcam_WaitImageV3(self.__h, nWaitMS, pImageData, bStill, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV3(pInfo, x)

    def PullImageV2(self, pImageData, bits, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_PullImageV2(self.__h, pImageData, bits, None)
        else:
            x = self.__FrameInfoV2()
            self.__lib.Toupcam_PullImageV2(self.__h, pImageData, bits, ctypes.byref(x))
            self.__convertFrameInfoV2(pInfo, x)

    def PullStillImageV2(self, pImageData, bits, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_PullStillImageV2(self.__h, pImageData, bits, None)
        else:
            x = self.__FrameInfoV2()
            self.__lib.Toupcam_PullStillImageV2(self.__h, pImageData, bits, ctypes.byref(x))
            self.__convertFrameInfoV2(pInfo, x)

    def PullImageWithRowPitchV2(self, pImageData, bits, rowPitch, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_PullImageWithRowPitchV2(self.__h, pImageData, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV2()
            self.__lib.Toupcam_PullImageWithRowPitchV2(self.__h, pImageData, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV2(pInfo, x)

    def PullStillImageWithRowPitchV2(self, pImageData, bits, rowPitch, pInfo):
        if pInfo is None:
            self.__lib.Toupcam_PullStillImageWithRowPitchV2(self.__h, pImageData, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV2()
            self.__lib.Toupcam_PullStillImageWithRowPitchV2(self.__h, pImageData, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV2(pInfo, x)

    def ResolutionNumber(self):
        return self.__lib.Toupcam_get_ResolutionNumber(self.__h)

    def StillResolutionNumber(self):
        """return (width, height)"""
        return self.__lib.Toupcam_get_StillResolutionNumber(self.__h)

    def MonoMode(self):
        return (self.__lib.Toupcam_get_MonoMode(self.__h) == 0)

    def MaxSpeed(self):
        """get the maximum speed, 'Frame Speed Level'"""
        return self.__lib.Toupcam_get_MaxSpeed(self.__h)

    def MaxBitDepth(self):
        """get the max bitdepth of this camera, such as 8, 10, 12, 14, 16"""
        return self.__lib.Toupcam_get_MaxBitDepth(self.__h)

    def FanMaxSpeed(self):
        """get the maximum fan speed, the fan speed range = [0, max], closed interval"""
        return self.__lib.Toupcam_get_FanMaxSpeed(self.__h)

    def Revision(self):
        """get the revision"""
        x = ctypes.c_ushort(0)
        self.__lib.Toupcam_get_Revision(self.__h, ctypes.byref(x))
        return x.value

    def SerialNumber(self):
        """get the serial number which is always 32 chars which is zero-terminated such as: TP110826145730ABCD1234FEDC56787"""
        str = (ctypes.c_char * 32)()
        self.__lib.Toupcam_get_SerialNumber(self.__h, str)
        return str.value.decode('ascii')

    def FwVersion(self):
        """get the camera firmware version, such as: 3.2.1.20140922"""
        str = (ctypes.c_char * 16)()
        self.__lib.Toupcam_get_FwVersion(self.__h, str)
        return str.value.decode('ascii')

    def HwVersion(self):
        """get the camera hardware version, such as: 3.2.1.20140922"""
        str = (ctypes.c_char * 16)()
        self.__lib.Toupcam_get_HwVersion(self.__h, str)
        return str.value.decode('ascii')

    def ProductionDate(self):
        """such as: 20150327"""
        str = (ctypes.c_char * 16)()
        self.__lib.Toupcam_get_ProductionDate(self.__h, str)
        return str.value.decode('ascii')

    def FpgaVersion(self):
        str = (ctypes.c_char * 16)()
        self.__lib.Toupcam_get_FpgaVersion(self.__h, str)
        return str.value.decode('ascii')

    def Field(self):
        return self.__lib.Toupcam_get_Field(self.__h)

    def Stop(self):
        self.__lib.Toupcam_Stop(self.__h)

    def Pause(self, bPause):
        '''1 => pause, 0 => continue'''
        self.__lib.Toupcam_Pause(self.__h, ctypes.c_int(1 if bPause else 0))

    def Snap(self, nResolutionIndex):
        """still image snap, nResolutionIndex = 0xffffffff means use the cureent preview resolution"""
        self.__lib.Toupcam_Snap(self.__h, ctypes.c_uint(nResolutionIndex))

    def SnapN(self, nResolutionIndex, nNumber):
        """multiple still image snap, nResolutionIndex = 0xffffffff means use the cureent preview resolution"""
        self.__lib.Toupcam_SnapN(self.__h, ctypes.c_uint(nResolutionIndex), ctypes.c_uint(nNumber))

    def SnapR(self, nResolutionIndex, nNumber):
        """multiple RAW still image snap, nResolutionIndex = 0xffffffff means use the cureent preview resolution"""
        self.__lib.Toupcam_SnapR(self.__h, ctypes.c_uint(nResolutionIndex), ctypes.c_uint(nNumber))

    def Trigger(self, nNumber):
        """
        soft trigger:
        nNumber:    0xffff:     trigger continuously
                    0:          cancel trigger
                    others:     number of images to be triggered
        """
        self.__lib.Toupcam_Trigger(self.__h, ctypes.c_ushort(nNumber))

    def TriggerSyncV4(self, nWaitMS, pImageData, bits, rowPitch, pInfo):
        """
        trigger synchronously
        nWaitMS:    0:              by default, exposure * 102% + 4000 milliseconds
                    0xffffffff:     wait infinite
                    other:          milliseconds to wait
        """
        if pInfo is None:
            self.__lib.Toupcam_TriggerSyncV4(self.__h, nWaitMS, pImageData, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV4()
            self.__lib.Toupcam_TriggerSyncV4(self.__h, nWaitMS, pImageData, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV4(pInfo, x)

    def TriggerSync(self, nWaitMS, pImageData, bits, rowPitch, pInfo):
        """
        trigger synchronously
        nWaitMS:    0:              by default, exposure * 102% + 4000 milliseconds
                    0xffffffff:     wait infinite
                    other:          milliseconds to wait
        """
        if pInfo is None:
            self.__lib.Toupcam_TriggerSync(self.__h, nWaitMS, pImageData, bits, rowPitch, None)
        else:
            x = self.__FrameInfoV3()
            self.__lib.Toupcam_TriggerSync(self.__h, nWaitMS, pImageData, bits, rowPitch, ctypes.byref(x))
            self.__convertFrameInfoV3(pInfo, x)

    def put_Size(self, nWidth, nHeight):
        self.__lib.Toupcam_put_Size(self.__h, ctypes.c_int(nWidth), ctypes.c_int(nHeight))

    def get_Size(self):
        """return (width, height)"""
        x = ctypes.c_int(0)
        y = ctypes.c_int(0)
        self.__lib.Toupcam_get_Size(self.__h, ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def put_eSize(self, nResolutionIndex):
        """
        put_Size, put_eSize, can be used to set the video output resolution BEFORE Start.
        put_Size use width and height parameters, put_eSize use the index parameter.
        for example, UCMOS03100KPA support the following resolutions:
            index 0:    2048,   1536
            index 1:    1024,   768
            index 2:    680,    510
        so, we can use put_Size(h, 1024, 768) or put_eSize(h, 1). Both have the same effect.
        """
        self.__lib.Toupcam_put_eSize(self.__h, ctypes.c_uint(nResolutionIndex))

    def get_eSize(self):
        x = ctypes.c_uint(0)
        self.__lib.Toupcam_get_eSize(self.__h, ctypes.byref(x))
        return x.value

    def get_FinalSize(self):
        """final size after ROI, rotate, binning"""
        x = ctypes.c_int(0)
        y = ctypes.c_int(0)
        self.__lib.Toupcam_get_FinalSize(self.__h, ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def get_Resolution(self, nResolutionIndex):
        """return (width, height)"""
        x = ctypes.c_int(0)
        y = ctypes.c_int(0)
        self.__lib.Toupcam_get_Resolution(self.__h, ctypes.c_uint(nResolutionIndex), ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def get_PixelSize(self, nResolutionIndex):
        """get the sensor pixel size, such as: 2.4um x 2.4um"""
        x = ctypes.c_float(0)
        y = ctypes.c_float(0)
        self.__lib.Toupcam_get_PixelSize(self.__h, ctypes.c_uint(nResolutionIndex), ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def get_ResolutionRatio(self, nResolutionIndex):
        """numerator/denominator, such as: 1/1, 1/2, 1/3"""
        x = ctypes.c_int(0)
        y = ctypes.c_int(0)
        self.__lib.Toupcam_get_ResolutionRatio(self.__h, ctypes.c_uint(nResolutionIndex), ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def get_RawFormat(self):
        """
        see: http://www.fourcc.org
        FourCC:
            MAKEFOURCC('G', 'B', 'R', 'G'), see http://www.siliconimaging.com/RGB%20Bayer.htm
            MAKEFOURCC('R', 'G', 'G', 'B')
            MAKEFOURCC('B', 'G', 'G', 'R')
            MAKEFOURCC('G', 'R', 'B', 'G')
            MAKEFOURCC('Y', 'Y', 'Y', 'Y'), monochromatic sensor
            MAKEFOURCC('Y', '4', '1', '1'), yuv411
            MAKEFOURCC('V', 'U', 'Y', 'Y'), yuv422
            MAKEFOURCC('U', 'Y', 'V', 'Y'), yuv422
            MAKEFOURCC('Y', '4', '4', '4'), yuv444
            MAKEFOURCC('R', 'G', 'B', '8'), RGB888
        """
        x = ctypes.c_uint(0)
        y = ctypes.c_uint(0)
        self.__lib.Toupcam_get_RawFormat(self.__h, ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def put_RealTime(self, val):
        """
        0: no realtime
            stop grab frame when frame buffer deque is full, until the frames in the queue are pulled away and the queue is not full
        1: realtime
            use minimum frame buffer. When new frame arrive, drop all the pending frame regardless of whether the frame buffer is full.
            If DDR present, also limit the DDR frame buffer to only one frame.
        2: soft realtime
            Drop the oldest frame when the queue is full and then enqueue the new frame
        default: 0
        """
        self.__lib.Toupcam_put_RealTime(self.__h, val)

    def get_RealTime(self):
        b = ctypes.c_int(0)
        self.__lib.Toupcam_get_RealTime(self.__h, b)
        return b.value

    def Flush(self):
        """Flush is obsolete, recommend using put_Option(h, TOUPCAM_OPTION_FLUSH, 3)"""
        self.__lib.Toupcam_Flush(self.__h)

    def get_AutoExpoEnable(self):
        """
        bAutoExposure:
           0: disable auto exposure
           1: auto exposure continue mode
           2: auto exposure once mode
        """
        b = ctypes.c_int(0)
        self.__lib.Toupcam_get_AutoExpoEnable(self.__h, b)
        return b.value

    def put_AutoExpoEnable(self, bAutoExposure):
        """
        bAutoExposure:
           0: disable auto exposure
           1: auto exposure continue mode
           2: auto exposure once mode
        """
        self.__lib.Toupcam_put_AutoExpoEnable(self.__h, ctypes.c_int(bAutoExposure))

    def get_AutoExpoTarget(self):
        x = ctypes.c_ushort(TOUPCAM_AETARGET_DEF)
        self.__lib.Toupcam_get_AutoExpoTarget(self.__h, ctypes.byref(x))
        return x.value

    def put_AutoExpoTarget(self, Target):
        self.__lib.Toupcam_put_AutoExpoTarget(self.__h, ctypes.c_int(Target))

    def put_AutoExpoRange(self, maxTime, minTime, maxGain, minGain):
        ''' set the maximum/minimal auto exposure time and agin. The default maximum auto exposure time is 350ms '''
        return self.__lib.Toupcam_put_AutoExpoRange(self.__h, ctypes.c_uint(maxTime), ctypes.c_uint(minTime), ctypes.c_ushort(maxGain), ctypes.c_ushort(minGain))

    def get_AutoExpoRange(self):
        maxTime = ctypes.c_uint(0)
        minTime = ctypes.c_uint(0)
        maxGain = ctypes.c_ushort(0)
        minGain = ctypes.c_ushort(0)
        self.__lib.Toupcam_get_AutoExpoRange(self.__h, ctypes.byref(maxTime), ctypes.byref(minTime), ctypes.byref(maxGain), ctypes.byref(minGain))
        return (maxTime.value, minTime.value, maxGain.value, minGain.value)

    def put_MaxAutoExpoTimeAGain(self, maxTime, maxGain):
        return self.__lib.Toupcam_put_MaxAutoExpoTimeAGain(self.__h, ctypes.c_uint(maxTime), ctypes.c_ushort(maxGain))

    def get_MaxAutoExpoTimeAGain(self):
        x = ctypes.c_uint(0)
        y = ctypes.c_ushort(0)
        self.__lib.Toupcam_get_MaxAutoExpoTimeAGain(self.__h, ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def put_MinAutoExpoTimeAGain(self, minTime, minGain):
        self.__lib.Toupcam_put_MinAutoExpoTimeAGain(self.__h, ctypes.c_uint(minTime), ctypes.c_ushort(minGain))

    def get_MinAutoExpoTimeAGain(self):
        x = ctypes.c_uint(0)
        y = ctypes.c_ushort(0)
        self.__lib.Toupcam_get_MinAutoExpoTimeAGain(self.__h, ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def get_ExpoTime(self):
        """in microseconds"""
        x = ctypes.c_uint(0)
        self.__lib.Toupcam_get_ExpoTime(self.__h, ctypes.byref(x))
        return x.value

    def get_RealExpoTime(self):
        """in microseconds"""
        x = ctypes.c_uint(0)
        self.__lib.Toupcam_get_RealExpoTime(self.__h, ctypes.byref(x))
        return x.value

    def put_ExpoTime(self, Time):
        self.__lib.Toupcam_put_ExpoTime(self.__h, ctypes.c_uint(Time))

    def get_ExpTimeRange(self):
        x = ctypes.c_uint(0)
        y = ctypes.c_uint(0)
        z = ctypes.c_uint(0)
        self.__lib.Toupcam_get_ExpTimeRange(self.__h, ctypes.byref(x), ctypes.byref(y), ctypes.byref(z))
        return (x.value, y.value, z.value)

    def get_ExpoAGain(self):
        """percent, such as 300"""
        x = ctypes.c_ushort(0)
        self.__lib.Toupcam_get_ExpoAGain(self.__h, ctypes.byref(x))
        return x.value

    def put_ExpoAGain(self, Gain):
        self.__lib.Toupcam_put_ExpoAGain(self.__h, ctypes.c_ushort(Gain))

    def get_ExpoAGainRange(self):
        """ return (min, max, default)"""
        x = ctypes.c_ushort(0)
        y = ctypes.c_ushort(0)
        z = ctypes.c_ushort(0)
        self.__lib.Toupcam_get_ExpoAGainRange(self.__h, ctypes.byref(x), ctypes.byref(y), ctypes.byref(z))
        return (x.value, y.value, z.value)

    def put_LevelRange(self, aLow, aHigh):
        if len(aLow) == 4 and len(aHigh) == 4:
            x = (ctypes.c_ushort * 4)(aLow[0], aLow[1], aLow[2], aLow[3])
            y = (ctypes.c_ushort * 4)(aHigh[0], aHigh[1], aHigh[2], aHigh[3])
            self.__lib.Toupcam_put_LevelRange(self.__h, x, y)
        else:
            raise HRESULTException(0x80070057)

    def get_LevelRange(self):
        x = (ctypes.c_ushort * 4)()
        y = (ctypes.c_ushort * 4)()
        self.__lib.Toupcam_get_LevelRange(self.__h, x, y)
        aLow = (x[0], x[1], x[2], x[3])
        aHigh = (y[0], y[1], y[2], y[3])
        return (aLow, aHigh)

    def put_LevelRangeV2(self, mode, roiX, roiY, roiWidth, roiHeight, aLow, aHigh):
        if len(aLow) == 4 and len(aHigh) == 4:
            x = (ctypes.c_ushort * 4)(aLow[0], aLow[1], aLow[2], aLow[3])
            y = (ctypes.c_ushort * 4)(aHigh[0], aHigh[1], aHigh[2], aHigh[3])
            rc = self.__RECT()
            rc.left = roiX
            rc.right = roiX + roiWidth
            rc.top = roiY
            rc.bottom = roiY + roiHeight
            self.__lib.Toupcam_put_LevelRangeV2(self.__h, mode, ctypes.byref(rc), x, y)
        else:
            raise HRESULTException(0x80070057)

    def get_LevelRangeV2(self):
        mode = ctypes.c_ushort(0)
        x = (ctypes.c_ushort * 4)()
        y = (ctypes.c_ushort * 4)()
        rc = self.__RECT()
        self.__lib.Toupcam_get_LevelRange(self.__h, mode, ctypes.byref(rc), x, y)
        aLow = (x[0], x[1], x[2], x[3])
        aHigh = (y[0], y[1], y[2], y[3])
        return (mode, (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top), aLow, aHigh)

    def put_Hue(self, Hue):
        self.__lib.Toupcam_put_Hue(self.__h, ctypes.c_int(Hue))

    def get_Hue(self):
        x = ctypes.c_int(TOUPCAM_HUE_DEF)
        self.__lib.Toupcam_get_Hue(self.__h, ctypes.byref(x))
        return x.value

    def put_Saturation(self, Saturation):
        self.__lib.Toupcam_put_Saturation(self.__h, ctypes.c_int(Saturation))

    def get_Saturation(self):
        x = ctypes.c_int(TOUPCAM_SATURATION_DEF)
        self.__lib.Toupcam_get_Saturation(self.__h, ctypes.byref(x))
        return x.value

    def put_Brightness(self, Brightness):
        self.__lib.Toupcam_put_Brightness(self.__h, ctypes.c_int(Brightness))

    def get_Brightness(self):
        x = ctypes.c_int(TOUPCAM_BRIGHTNESS_DEF)
        self.__lib.Toupcam_get_Brightness(self.__h, ctypes.byref(x))
        return x.value

    def get_Contrast(self):
        x = ctypes.c_int(TOUPCAM_CONTRAST_DEF)
        self.__lib.Toupcam_get_Contrast(self.__h, ctypes.byref(x))
        return x.value

    def put_Contrast(self, Contrast):
        self.__lib.Toupcam_put_Contrast(self.__h, ctypes.c_int(Contrast))

    def get_Gamma(self):
        x = ctypes.c_int(TOUPCAM_GAMMA_DEF)
        self.__lib.Toupcam_get_Gamma(self.__h, ctypes.byref(x))
        return x.value

    def put_Gamma(self, Gamma):
        self.__lib.Toupcam_put_Gamma(self.__h, ctypes.c_int(Gamma))

    def get_Chrome(self):
        """monochromatic mode"""
        b = ctypes.c_int(0)
        self.__lib.Toupcam_get_Chrome(self.__h, ctypes.byref(b)) < 0
        return (b.value != 0)

    def put_Chrome(self, bChrome):
        self.__lib.Toupcam_put_Chrome(self.__h, ctypes.c_int(1 if bChrome else 0))

    def get_VFlip(self):
        """vertical flip"""
        b = ctypes.c_int(0)
        self.__lib.Toupcam_get_VFlip(self.__h, ctypes.byref(b))
        return (b.value != 0)

    def put_VFlip(self, bVFlip):
        """vertical flip"""
        self.__lib.Toupcam_put_VFlip(self.__h, ctypes.c_int(1 if bVFlip else 0))

    def get_HFlip(self):
        """horizontal flip"""
        b = ctypes.c_int(0)
        self.__lib.Toupcam_get_HFlip(self.__h, ctypes.byref(b))
        return (b.value != 0)

    def put_HFlip(self, bHFlip):
        """horizontal flip"""
        self.__lib.Toupcam_put_HFlip(self.__h, ctypes.c_int(1 if bHFlip else 0))

    def get_Negative(self):
        """negative film"""
        b = ctypes.c_int(0)
        self.__lib.Toupcam_get_Negative(self.__h, ctypes.byref(b))
        return (b.value != 0)

    def put_Negative(self, bNegative):
        """negative film"""
        self.__lib.Toupcam_put_Negative(self.__h, ctypes.c_int(1 if bNegative else 0))

    def put_Speed(self, nSpeed):
        self.__lib.Toupcam_put_Speed(self.__h, ctypes.c_ushort(nSpeed))

    def get_Speed(self):
        x = ctypes.c_ushort(0)
        self.__lib.Toupcam_get_Speed(self.__h, ctypes.byref(x))
        return x.value

    def put_HZ(self, nHZ):
        """
        power supply:
            0 => 60HZ AC
            1 => 50Hz AC
            2 => DC
        """
        self.__lib.Toupcam_put_HZ(self.__h, ctypes.c_int(nHZ))

    def get_HZ(self):
        x = ctypes.c_int(0)
        self.__lib.Toupcam_get_HZ(self.__h, ctypes.byref(x))
        return x.value

    def put_Mode(self, bSkip):
        """skip or bin"""
        self.__lib.Toupcam_put_Mode(self.__h, ctypes.c_int(1 if bSkip else 0))

    def get_Mode(self):
        b = ctypes.c_int(0)
        self.__lib.Toupcam_get_Mode(self.__h, ctypes.byref(b))
        return (b.value != 0)

    def put_TempTint(self, nTemp, nTint):
        """White Balance, Temp/Tint mode"""
        self.__lib.Toupcam_put_TempTint(self.__h, ctypes.c_int(nTemp), ctypes.c_int(nTint))

    def get_TempTint(self):
        """White Balance, Temp/Tint mode"""
        x = ctypes.c_int(TOUPCAM_TEMP_DEF)
        y = ctypes.c_int(TOUPCAM_TINT_DEF)
        self.__lib.Toupcam_get_TempTint(self.__h, ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def put_WhiteBalanceGain(self, aGain):
        """White Balance, RGB Gain Mode"""
        if len(aGain) == 3:
            x = (ctypes.c_int * 3)(aGain[0], aGain[1], aGain[2])
            self.__lib.Toupcam_put_WhiteBalanceGain(self.__h, x)
        else:
            raise HRESULTException(0x80070057)

    def get_WhiteBalanceGain(self):
        """White Balance, RGB Gain Mode"""
        x = (ctypes.c_int * 3)()
        self.__lib.Toupcam_get_WhiteBalanceGain(self.__h, x)
        return (x[0], x[1], x[2])

    def put_AWBAuxRect(self, X, Y, Width, Height):
        rc = self.__RECT()
        rc.left = X
        rc.right = X + Width
        rc.top = Y
        rc.bottom = Y + Height
        self.__lib.Toupcam_put_AWBAuxRect(self.__h, ctypes.byref(rc))

    def get_AWBAuxRect(self):
        """return (left, top, width, height)"""
        rc = self.__RECT()
        self.__lib.Toupcam_get_AWBAuxRect(self.__h, ctypes.byref(rc))
        return (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top)

    def put_AEAuxRect(self, X, Y, Width, Height):
        rc = self.__RECT()
        rc.left = X
        rc.right = X + Width
        rc.top = Y
        rc.bottom = Y + Height
        self.__lib.Toupcam_put_AEAuxRect(self.__h, ctypes.byref(rc))

    def get_AEAuxRect(self):
        """return (left, top, width, height)"""
        rc = self.__RECT()
        self.__lib.Toupcam_get_AEAuxRect(self.__h, ctypes.byref(rc))
        return (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top)

    def put_BlackBalance(self, aSub):
        if len(aSub) == 3:
            x = (ctypes.c_ushort * 3)(aSub[0], aSub[1], aSub[2])
            self.__lib.Toupcam_put_BlackBalance(self.__h, x)
        else:
            raise HRESULTException(0x80070057)

    def get_BlackBalance(self):
        x = (ctypes.c_ushort * 3)()
        self.__lib.Toupcam_get_BlackBalance(self.__h, x)
        return (x[0], x[1], x[2])

    def put_ABBAuxRect(self, X, Y, Width, Height):
        rc = self.__RECT()
        rc.left = X
        rc.right = X + Width
        rc.top = Y
        rc.bottom = Y + Height
        self.__lib.Toupcam_put_ABBAuxRect(self.__h, ctypes.byref(rc))

    def get_ABBAuxRect(self):
        """return (left, top, width, height)"""
        rc = self.__RECT()
        self.__lib.Toupcam_get_ABBAuxRect(self.__h, ctypes.byref(rc))
        return (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top)

    def get_StillResolution(self, nResolutionIndex):
        x = ctypes.c_int(0)
        y = ctypes.c_int(0)
        self.__lib.Toupcam_get_StillResolution(self.__h, ctypes.c_uint(nResolutionIndex), ctypes.byref(x), ctypes.byref(y))
        return (x.value, y.value)

    def put_LEDState(self, iLed, iState, iPeriod):
        """
        led state:
            iLed: Led index, (0, 1, 2, ...)
            iState: 1 => Ever bright; 2 => Flashing; other => Off
            iPeriod: Flashing Period (>= 500ms)
        """
        self.__lib.Toupcam_put_LEDState(self.__h, ctypes.c_ushort(iLed), ctypes.c_ushort(iState), ctypes.c_ushort(iPeriod))

    def write_EEPROM(self, addr, pBuffer):
        self.__lib.Toupcam_write_EEPROM(self.__h, addr, pBuffer, ctypes.c_uint(len(pBuffer)))

    def read_EEPROM(self, addr, pBuffer):
        self.__lib.Toupcam_read_EEPROM(self.__h, addr, pBuffer, ctypes.c_uint(len(pBuffer)))

    def rwc_Flash(self, action, addr, pData):
        """
        Flash:
        action = TOUPCAM_FLASH_XXXX: read, write, erase, query total size, query read/write block size, query erase block size
        addr = address
        see democpp
        """
        self.__lib.Toupcam_rwc_Flash(self.__h, action, addr, ctypes.c_uint(len(pData)), pData)

    def write_Pipe(self, pipeId, pBuffer):
        self.__lib.Toupcam_write_Pipe(self.__h, pipeId, pBuffer, ctypes.c_uint(len(pBuffer)))

    def read_Pipe(self, pipeId, pBuffer):
        self.__lib.Toupcam_read_Pipe(self.__h, pipeId, pBuffer, ctypes.c_uint(len(pBuffer)))

    def feed_Pipe(self, pipeId):
        self.__lib.Toupcam_feed_Pipe(self.__h, ctypes.c_uint(pipeId))

    def write_UART(self, pBuffer):
        self.__lib.Toupcam_write_UART(self.__h, pBuffer, ctypes.c_uint(len(pBuffer)))

    def read_UART(self, pBuffer):
        self.__lib.Toupcam_read_UART(self.__h, pBuffer, ctypes.c_uint(len(pBuffer)))

    def put_Option(self, iOption, iValue):
        self.__lib.Toupcam_put_Option(self.__h, ctypes.c_uint(iOption), ctypes.c_int(iValue))

    def get_Option(self, iOption):
        x = ctypes.c_int(0)
        self.__lib.Toupcam_get_Option(self.__h, ctypes.c_uint(iOption), ctypes.byref(x))
        return x.value

    def get_PixelFormatSupport(self, cmd):
        """"
        cmd:
           0xff:     query the number
           0~number: query the nth pixel format
        output: TOUPCAM_PIXELFORMAT_xxxx
        """
        x = ctypes.c_int(0)
        self.__lib.Toupcam_get_PixelFormatSupport(self.__h, cmd, ctypes.byref(x))
        return x.value

    def put_Linear(self, v8, v16):
        self.__lib.Toupcam_put_Linear(self.__h, v8, v16)

    def put_Curve(self, v8, v16):
        self.__lib.Toupcam_put_Curve(self.__h, v8, v16)

    def put_ColorMatrix(self, v):
        if len(v) == 9:
            a = (ctypes.c_double * 9)(v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8])
            return self.__lib.Toupcam_put_ColorMatrix(self.__h, v)
        else:
            raise HRESULTException(0x80070057)

    def put_InitWBGain(self, v):
        if len(v) == 3:
            a = (ctypes.c_short * 3)(v[0], v[1], v[2])
            self.__lib.Toupcam_put_InitWBGain(self.__h, a)
        else:
            raise HRESULTException(0x80070057)

    def get_TecTargetRange(self):
        """TEC Target range: [min, max]"""
        x = ctypes.c_int(0)
        self.__lib.Toupcam_get_Option(self.__h, TOUPCAM_OPTION_TECTARGET_RANGE, ctypes.byref(x))
        low, high = x.value & 0xffff, (x.value >> 16) & 0xffff
        if low > 32767:
            low = low - 65536
        if high > 32767:
            high = high - 65536
        return (low, high)
    
    def get_Temperature(self):
        """get the temperature of the sensor, in 0.1 degrees Celsius (32 means 3.2 degrees Celsius, -35 means -3.5 degree Celsius)"""
        x = ctypes.c_short(0)
        self.__lib.Toupcam_get_Temperature(self.__h, ctypes.byref(x))
        return x.value

    def put_Temperature(self, nTemperature):
        """
        set the target temperature of the sensor or TEC, in 0.1 degrees Celsius (32 means 3.2 degrees Celsius, -35 means -3.5 degree Celsius)
        set "-2730" or below means using the default value of this model
        """
        self.__lib.Toupcam_put_Temperature(self.__h, ctypes.c_short(nTemperature))

    def put_Roi(self, xOffset, yOffset, xWidth, yHeight):
        """xOffset, yOffset, xWidth, yHeight: must be even numbers"""
        self.__lib.Toupcam_put_Roi(self.__h, ctypes.c_uint(xOffset), ctypes.c_uint(yOffset), ctypes.c_uint(xWidth), ctypes.c_uint(yHeight))

    def get_Roi(self):
        """return (xOffset, yOffset, xWidth, yHeight)"""
        x = ctypes.c_uint(0)
        y = ctypes.c_uint(0)
        w = ctypes.c_uint(0)
        h = ctypes.c_uint(0)
        self.__lib.Toupcam_get_Roi(self.__h, ctypes.byref(x), ctypes.byref(y), ctypes.byref(w), ctypes.byref(h))
        return (x.value, y.value, w.value, h.value)

    def put_RoiN(self, xOffset, yOffset, xWidth, yHeight):
        '''multiple Roi'''
        Num = len(xOffset)
        pxOffset = (ctypes.c_uint * Num)(*xOffset)
        pyOffset = (ctypes.c_uint * Num)(*yOffset)
        pxWidth = (ctypes.c_uint * Num)(*xWidth)
        pyHeight = (ctypes.c_uint * Num)(*yHeight)
        self.__lib.Toupcam_put_RoiN(self.__h, pxOffset, pyOffset, pxWidth, pyHeight, Num)

    def put_XY(self, x, y):
        self.__lib.Toupcam_put_XY(self.__h, ctypes.c_int(x), ctypes.c_int(y))

    def put_SelfTrigger(self, pSt):
        x = self.__SelfTrigger()
        x.sensingLeft = pSt.sensingLeft
        x.sensingTop = pSt.sensingTop
        x.sensingWidth = pSt.sensingWidth
        x.sensingHeight = pSt.sensingHeight
        x.hThreshold = pSt.hThreshold
        x.lThreshold = pSt.lThreshold
        x.expoTime = pSt.expoTime
        x.expoGain = pSt.expoGain
        x.hCount = pSt.hCount
        x.lCount = pSt.lCount
        x.reserved = pSt.reserved
        self.__lib.Toupcam_put_SelfTrigger(self.__h, ctypes.byref(x))

    def get_SelfTrigger(self, pSt):
        x = self.__SelfTrigger()
        self.__lib.Toupcam_get_SelfTrigger(self.__h, ctypes.byref(x))
        return ToupcamSelfTrigger(x.sensingLeft.value, x.sensingTop.value, x.sensingWidth.value, x.sensingHeight.value, x.hThreshold.value, x.lThreshold.value, x.expoTime.value, x.expoGain.value, x.hCount.value, x.lCount.value, x.reserved.value)

    def get_AFState(self):
        x = ctypes.c_uint(0)
        self.__lib.Toupcam_get_AFState(self.__h, ctypes.byref(x))
        return x.value

    def put_AFMode(self, mode):
        self.__lib.Toupcam_put_AFRoi(self.__h, ctypes.c_uint(mode))

    def put_AFRoi(self, xOffset, yOffset, xWidth, yHeight):
        self.__lib.Toupcam_put_AFRoi(self.__h, ctypes.c_uint(xOffset), ctypes.c_uint(yOffset), ctypes.c_uint(xWidth), ctypes.c_uint(yHeight))

    def put_AFAperture(self, iAperture):
        self.__lib.Toupcam_put_AFAperture(self.__h, ctypes.c_int(iAperture))

    def put_AFFMPos(self, iFMPos):
        self.__lib.Toupcam_put_AFFMPos(self.__h, ctypes.c_int(iFMPos))

    def get_FrameRate(self):
        """
        get the frame rate: framerate (fps) = Frame * 1000.0 / nTime
        return (Frame, Time, TotalFrame)
        """
        x = ctypes.c_uint(0)
        y = ctypes.c_uint(0)
        z = ctypes.c_uint(0)
        self.__lib.Toupcam_get_FrameRate(self.__h, ctypes.byref(x), ctypes.byref(y), ctypes.byref(z))
        return (x.value, y.value, z.value)

    def LevelRangeAuto(self):
        self.__lib.Toupcam_LevelRangeAuto(self.__h)

    def AwbOnce(self):
        """Auto White Balance "Once", Temp/Tint Mode"""
        self.__lib.Toupcam_AwbOnce(self.__h, None, None)

    def AwbOnePush(self):
        AwbOnce(self)

    def AwbInit(self):
        """Auto White Balance "Once", Temp/Tint Mode"""
        self.__lib.Toupcam_AwbInit(self.__h, None, None)

    def AbbOnce(self):
        self.__lib.Toupcam_AbbOnce(self.__h, None, None)

    def AbbOnePush(self):
        AbbOnce(self)

    def FfcOnce(self):
        self.__lib.Toupcam_FfcOnce(self.__h)

    def FfcOnePush(self):
        FfcOnce(self)

    def DfcOnce(self):
        self.__lib.Toupcam_DfcOnce(self.__h)

    def DfcOnePush(self):
        DfcOnce(self)

    def FpncOnce(self):
        self.__lib.Toupcam_FpncOnce(self.__h)

    def DfcExport(self, filePath):
        if sys.platform == 'win32':
            self.__lib.Toupcam_DfcExport(self.__h, filePath)
        else:
            self.__lib.Toupcam_DfcExport(self.__h, filePath.encode())

    def FfcExport(self, filePath):
        if sys.platform == 'win32':
            self.__lib.Toupcam_FfcExport(self.__h, filePath)
        else:
            self.__lib.Toupcam_FfcExport(self.__h, filePath.encode())

    def DfcImport(self, filePath):
        if sys.platform == 'win32':
            self.__lib.Toupcam_DfcImport(self.__h, filePath)
        else:
            self.__lib.Toupcam_DfcImport(self.__h, filePath.encode())

    def FfcImport(self, filePath):
        if sys.platform == 'win32':
            self.__lib.Toupcam_FfcImport(self.__h, filePath)
        else:
            self.__lib.Toupcam_FfcImport(self.__h, filePath.encode())

    def FpncExport(self, filePath):
        if sys.platform == 'win32':
            self.__lib.Toupcam_FpncExport(self.__h, filePath)
        else:
            self.__lib.Toupcam_FpncExport(self.__h, filePath.encode())

    def FpncImport(self, filePath):
        if sys.platform == 'win32':
            self.__lib.Toupcam_FpncImport(self.__h, filePath)
        else:
            self.__lib.Toupcam_FpncImport(self.__h, filePath.encode())

    def IoControl(self, ioLineNumber, eType, outVal):
        x = ctypes.c_int(0)
        self.__lib.Toupcam_IoControl(self.__h, ctypes.c_uint(ioLineNumber), ctypes.c_uint(eType), ctypes.c_int(outVal), ctypes.byref(x))
        return x.value

    def AAF(self, action, outVal):
        x = ctypes.c_int(0)
        self.__lib.Toupcam_AAF(self.__h, ctypes.c_int(action), ctypes.c_int(outVal), ctypes.byref(x))
        return x.value

    def get_FocusMotor(self):
        x = self.__FocusMotor()
        self.__lib.Toupcam_get_FocusMotor(self.__h, ctypes.byref(x))
        return ToupcamFocusMotor(x.imax.value, x.imin.value, x.idef.value, x.imaxabs.value, x.iminabs.value, x.zoneh.value, x.zonev.value)

    def set_Name(self, name):
        self.__lib.Toupcam_set_Name(self.__h, name.encode())

    def query_Name(self):
        str = (ctypes.c_char * 64)()
        self.__lib.Toupcam_query_Name(self.__h, str)
        return str.value.decode()

    @staticmethod
    def __histogramCallbackFun(aHist, nFlag, ctx):
        if ctx:
            ctx.__histogramFun(aHist, nFlag)

    def __histogramFun(self, aHist, nFlag):
        if self.__funhistogram:
            arraySize = 1 << (nFlag & 0x0f)
            if nFlag & 0x8000 == 0:
                arraySize *= 3
            self.__funhistogram(aHist, self.__ctxhistogram)

    def GetHistogram(self, fun, ctx):
        self.__funhistogram = fun
        self.__ctxhistogram = ctx
        self.__cbhistogram = __class__.__HISTOGRAM_CALLBACK(__class__.__histogramCallbackFun)
        self.__lib.Toupcam_GetHistogramV2(self.__h, self.__cbhistogram, ctypes.py_object(self))

    @classmethod
    def put_Name(cls, camId, name):
        cls.__initlib()
        if sys.platform == 'win32':
            return cls.__lib.Toupcam_put_Name(camId, name)
        else:
            return cls.__lib.Toupcam_put_Name(camId.encode('ascii'), name)

    @classmethod
    def get_Name(cls, camId):
        cls.__initlib()
        str = (ctypes.c_char * 64)()
        if sys.platform == 'win32':
            cls.__lib.Toupcam_get_Name(camId, str)
        else:
            cls.__lib.Toupcam_get_Name(camId.encode('ascii'), str)
        return str.value.decode()

    @classmethod
    def PixelFormatName(cls, pixelFormat):
        cls.__initlib()
        return cls.__lib.Toupcam_get_PixelFormatName(pixelFormat)

    @classmethod
    def Replug(cls, camId):
        """
        simulate replug:
        return > 0, the number of device has been replug
        return = 0, no device found
        return E_ACCESSDENIED if without UAC Administrator privileges
        for each device found, it will take about 3 seconds
        """
        cls.__initlib()
        if sys.platform == 'win32':
            return cls.__lib.Toupcam_Replug(camId)
        else:
            return cls.__lib.Toupcam_Replug(camId.encode('ascii'))

    @staticmethod
    def __progressCallbackFun(percent, ctx):
        if __class__.__progress_fun:
            __class__.__progress_fun(percent, __progress_ctx)

    @classmethod
    def Update(cls, camId, filePath, pFun, pCtx):
        """
        firmware update:
           camId: camera ID
           filePath: ufw file full path
           pFun: progress percent callback
        Please do not unplug the camera or lost power during the upgrade process, this is very very important.
        Once an unplugging or power outage occurs during the upgrade process, the camera will no longer be available and can only be returned to the factory for repair.
        """
        cls.__initlib()
        cls.__progress_fun = pFun
        cls.__progress_ctx = pCtx
        cls.__progress_cb = cls.__PROGRESS_CALLBACK(cls.__progressCallbackFun)
        if sys.platform == 'win32':
            return cls.__lib.Toupcam_Update(camId, filePath, __progress_cb, None)
        else:
            return cls.__lib.Toupcam_Update(camId.encode('ascii'), filePath.encode('ascii'), __progress_cb, None)

    @classmethod
    def Gain2TempTint(cls, gain):
        cls.__initlib()
        if len(gain) == 3:
            x = (ctypes.c_int * 3)(gain[0], gain[1], gain[2])
            temp = ctypes.c_int(TOUPCAM_TINT_DEF)
            tint = ctypes.c_int(TOUPCAM_TINT_DEF)
            cls.__lib.Toupcam_Gain2TempTint(x, ctypes.byref(temp), ctypes.byref(tint))
            return (temp.value, tint.value)
        else:
            raise HRESULTException(0x80070057)

    @classmethod
    def TempTint2Gain(cls, temp, tint):
        cls.__initlib()
        x = (ctypes.c_int * 3)()
        cls.__lib.Toupcam_TempTint2Gain(ctypes.c_int(temp), ctypes.c_int(tint), x)
        return (x[0], x[1], x[2])

    @classmethod
    def __initlib(cls):
        if cls.__lib is None:
            try: # Firstly try to load the library in the directory where this file is located
                # dir = os.path.dirname(os.path.realpath(__file__))
                dir_ = os.path.abspath(os.path.join(os.path.dirname(__file__),'..','drivers and libraries','toupcam'))
                if sys.platform == 'win32':
                    cls.__lib = ctypes.windll.LoadLibrary(os.path.join(dir_,'win','x64','toupcam.dll'))
                elif sys.platform.startswith('linux'):
                    cls.__lib = ctypes.cdll.LoadLibrary(os.path.join(dir_,'linux','x64','libtoupcam.so'))
                else:
                    cls.__lib = ctypes.cdll.LoadLibrary(os.path.join(dir_,'mac','libtoupcam.dylib'))
            except OSError:
                pass

            if cls.__lib is None:
                if sys.platform == 'win32':
                    cls.__lib = ctypes.windll.LoadLibrary("drivers and libraries/toupcam/windows/toupcam.dll")
                elif sys.platform.startswith('linux'):
                    cls.__lib = ctypes.cdll.LoadLibrary('libtoupcam.so')
                else:
                    cls.__lib = ctypes.cdll.LoadLibrary('libtoupcam.dylib')

            cls.__FrameInfoV4._fields_ = [
                        ('v3', cls.__FrameInfoV3),
                        ('reserved', ctypes.c_uint),
                        ('uLum', ctypes.c_uint),
                        ('uFV', ctypes.c_longlong),
                        ('timecount', ctypes.c_longlong),
                        ('framecount', ctypes.c_uint),
                        ('tricount', ctypes.c_uint),
                        ('gps', cls.__Gps)]

            if sys.platform == 'win32':
                cls.__ModelV2._fields_ = [                     # camera model v2 win32
                        ('name', ctypes.c_wchar_p),            # model name, in Windows, we use unicode
                        ('flag', ctypes.c_ulonglong),          # TOUPCAM_FLAG_xxx, 64 bits
                        ('maxspeed', ctypes.c_uint),           # number of speed level, same as Toupcam_get_MaxSpeed(), the speed range = [0, maxspeed], closed interval
                        ('preview', ctypes.c_uint),            # number of preview resolution, same as Toupcam_get_ResolutionNumber()
                        ('still', ctypes.c_uint),              # number of still resolution, same as Toupcam_get_StillResolutionNumber()
                        ('maxfanspeed', ctypes.c_uint),        # maximum fan speed, fan speed range = [0, max], closed interval
                        ('ioctrol', ctypes.c_uint),            # number of input/output control
                        ('xpixsz', ctypes.c_float),            # physical pixel size in micrometer
                        ('ypixsz', ctypes.c_float),            # physical pixel size in micrometer
                        ('res', cls.__Resolution * 16)]
                cls.__DeviceV2._fields_ = [                    # win32
                        ('displayname', ctypes.c_wchar * 64),  # display name
                        ('id', ctypes.c_wchar * 64),           # unique and opaque id of a connected camera, for Toupcam_Open
                        ('model', ctypes.POINTER(cls.__ModelV2))]
            else:
                cls.__ModelV2._fields_ = [                     # camera model v2 linux/mac
                        ('name', ctypes.c_char_p),             # model name
                        ('flag', ctypes.c_ulonglong),          # TOUPCAM_FLAG_xxx, 64 bits
                        ('maxspeed', ctypes.c_uint),           # number of speed level, same as Toupcam_get_MaxSpeed(), the speed range = [0, maxspeed], closed interval
                        ('preview', ctypes.c_uint),            # number of preview resolution, same as Toupcam_get_ResolutionNumber()
                        ('still', ctypes.c_uint),              # number of still resolution, same as Toupcam_get_StillResolutionNumber()
                        ('maxfanspeed', ctypes.c_uint),        # maximum fan speed
                        ('ioctrol', ctypes.c_uint),            # number of input/output control
                        ('xpixsz', ctypes.c_float),            # physical pixel size in micrometer
                        ('ypixsz', ctypes.c_float),            # physical pixel size in micrometer
                        ('res', cls.__Resolution * 16)]
                cls.__DeviceV2._fields_ = [                    # linux/mac
                        ('displayname', ctypes.c_char * 64),   # display name
                        ('id', ctypes.c_char * 64),            # unique and opaque id of a connected camera, for Toupcam_Open
                        ('model', ctypes.POINTER(cls.__ModelV2))]

            cls.__lib.Toupcam_Version.argtypes = None
            cls.__lib.Toupcam_EnumV2.restype = ctypes.c_uint
            cls.__lib.Toupcam_EnumV2.argtypes = [cls.__DeviceV2 * TOUPCAM_MAX]
            cls.__lib.Toupcam_EnumWithName.restype = ctypes.c_uint
            cls.__lib.Toupcam_EnumWithName.argtypes = [cls.__DeviceV2 * TOUPCAM_MAX]
            cls.__lib.Toupcam_put_Name.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Name.restype = ctypes.c_int
            cls.__lib.Toupcam_Open.restype = ctypes.c_void_p
            cls.__lib.Toupcam_Replug.restype = ctypes.c_int
            cls.__lib.Toupcam_Update.restype = ctypes.c_int
            if sys.platform == 'win32':
                cls.__lib.Toupcam_Version.restype = ctypes.c_wchar_p
                cls.__lib.Toupcam_put_Name.argtypes = [ctypes.c_wchar_p, ctypes.c_char_p]
                cls.__lib.Toupcam_get_Name.argtypes = [ctypes.c_wchar_p, ctypes.c_char * 64]
                cls.__lib.Toupcam_Open.argtypes = [ctypes.c_wchar_p]
                cls.__lib.Toupcam_Replug.argtypes = [ctypes.c_wchar_p]
                cls.__lib.Toupcam_Update.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, cls.__PROGRESS_CALLBACK, ctypes.py_object]
            else:
                cls.__lib.Toupcam_Version.restype = ctypes.c_char_p
                cls.__lib.Toupcam_put_Name.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                cls.__lib.Toupcam_get_Name.argtypes = [ctypes.c_char_p, ctypes.c_char * 64]
                cls.__lib.Toupcam_Open.argtypes = [ctypes.c_char_p]
                cls.__lib.Toupcam_Replug.argtypes = [ctypes.c_char_p]
                cls.__lib.Toupcam_Update.argtypes = [ctypes.c_char_p, ctypes.c_char_p, cls.__PROGRESS_CALLBACK, ctypes.py_object]
            cls.__lib.Toupcam_put_Name.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Name.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Replug.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Update.errcheck = cls.__errcheck
            cls.__lib.Toupcam_set_Name.restype = ctypes.c_int
            cls.__lib.Toupcam_set_Name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            cls.__lib.Toupcam_set_Name.errcheck = cls.__errcheck
            cls.__lib.Toupcam_query_Name.restype = ctypes.c_int
            cls.__lib.Toupcam_query_Name.argtypes = [ctypes.c_void_p, ctypes.c_char * 64]
            cls.__lib.Toupcam_query_Name.errcheck = cls.__errcheck
            cls.__lib.Toupcam_OpenByIndex.restype = ctypes.c_void_p
            cls.__lib.Toupcam_OpenByIndex.argtypes = [ctypes.c_uint]
            cls.__lib.Toupcam_Close.restype = None
            cls.__lib.Toupcam_Close.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_StartPullModeWithCallback.restype = ctypes.c_int
            cls.__lib.Toupcam_StartPullModeWithCallback.errcheck = cls.__errcheck
            cls.__lib.Toupcam_StartPullModeWithCallback.argtypes = [ctypes.c_void_p, cls.__EVENT_CALLBACK, ctypes.py_object]
            cls.__lib.Toupcam_PullImageV4.restype = ctypes.c_int
            cls.__lib.Toupcam_PullImageV4.errcheck = cls.__errcheck
            cls.__lib.Toupcam_PullImageV4.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV4)]
            cls.__lib.Toupcam_WaitImageV4.restype = ctypes.c_int
            cls.__lib.Toupcam_WaitImageV4.errcheck = cls.__errcheck
            cls.__lib.Toupcam_WaitImageV4.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV4)]
            cls.__lib.Toupcam_PullImageV3.restype = ctypes.c_int
            cls.__lib.Toupcam_PullImageV3.errcheck = cls.__errcheck
            cls.__lib.Toupcam_PullImageV3.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV3)]
            cls.__lib.Toupcam_WaitImageV3.restype = ctypes.c_int
            cls.__lib.Toupcam_WaitImageV3.errcheck = cls.__errcheck
            cls.__lib.Toupcam_WaitImageV3.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV3)]
            cls.__lib.Toupcam_PullImageV2.restype = ctypes.c_int
            cls.__lib.Toupcam_PullImageV2.errcheck = cls.__errcheck
            cls.__lib.Toupcam_PullImageV2.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV2)]
            cls.__lib.Toupcam_PullStillImageV2.restype = ctypes.c_int
            cls.__lib.Toupcam_PullStillImageV2.errcheck = cls.__errcheck
            cls.__lib.Toupcam_PullStillImageV2.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV2)]
            cls.__lib.Toupcam_PullImageWithRowPitchV2.restype = ctypes.c_int
            cls.__lib.Toupcam_PullImageWithRowPitchV2.errcheck = cls.__errcheck
            cls.__lib.Toupcam_PullImageWithRowPitchV2.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV2)]
            cls.__lib.Toupcam_PullStillImageWithRowPitchV2.restype = ctypes.c_int
            cls.__lib.Toupcam_PullStillImageWithRowPitchV2.errcheck = cls.__errcheck
            cls.__lib.Toupcam_PullStillImageWithRowPitchV2.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV2)]
            cls.__lib.Toupcam_Stop.restype = ctypes.c_int
            cls.__lib.Toupcam_Stop.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Stop.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_Pause.restype = ctypes.c_int
            cls.__lib.Toupcam_Pause.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Pause.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_Snap.restype = ctypes.c_int
            cls.__lib.Toupcam_Snap.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Snap.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            cls.__lib.Toupcam_SnapN.restype = ctypes.c_int
            cls.__lib.Toupcam_SnapN.errcheck = cls.__errcheck
            cls.__lib.Toupcam_SnapN.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
            cls.__lib.Toupcam_SnapR.restype = ctypes.c_int
            cls.__lib.Toupcam_SnapR.errcheck = cls.__errcheck
            cls.__lib.Toupcam_SnapR.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
            cls.__lib.Toupcam_Trigger.restype = ctypes.c_int
            cls.__lib.Toupcam_Trigger.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Trigger.argtypes = [ctypes.c_void_p, ctypes.c_ushort]
            cls.__lib.Toupcam_TriggerSyncV4.restype = ctypes.c_int
            cls.__lib.Toupcam_TriggerSyncV4.errcheck = cls.__errcheck
            cls.__lib.Toupcam_TriggerSyncV4.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV4)]
            cls.__lib.Toupcam_TriggerSync.restype = ctypes.c_int
            cls.__lib.Toupcam_TriggerSync.errcheck = cls.__errcheck
            cls.__lib.Toupcam_TriggerSync.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(cls.__FrameInfoV3)]
            cls.__lib.Toupcam_put_Size.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Size.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Size.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            cls.__lib.Toupcam_get_Size.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Size.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Size.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_eSize.restype = ctypes.c_int
            cls.__lib.Toupcam_put_eSize.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_eSize.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            cls.__lib.Toupcam_get_eSize.restype = ctypes.c_int
            cls.__lib.Toupcam_get_eSize.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_eSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_get_FinalSize.restype = ctypes.c_int
            cls.__lib.Toupcam_get_FinalSize.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_FinalSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_get_ResolutionNumber.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ResolutionNumber.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ResolutionNumber.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_get_Resolution.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Resolution.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Resolution.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)];
            cls.__lib.Toupcam_get_ResolutionRatio.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ResolutionRatio.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ResolutionRatio.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)];
            cls.__lib.Toupcam_get_Field.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Field.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Field.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_get_RawFormat.restype = ctypes.c_int
            cls.__lib.Toupcam_get_RawFormat.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_RawFormat.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_get_AutoExpoEnable.restype = ctypes.c_int
            cls.__lib.Toupcam_get_AutoExpoEnable.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_AutoExpoEnable.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_AutoExpoEnable.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AutoExpoEnable.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AutoExpoEnable.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_AutoExpoTarget.restype = ctypes.c_int
            cls.__lib.Toupcam_get_AutoExpoTarget.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_AutoExpoTarget.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_put_AutoExpoTarget.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AutoExpoTarget.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AutoExpoTarget.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_put_AutoExpoRange.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AutoExpoRange.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AutoExpoRange.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_ushort, ctypes.c_ushort]
            cls.__lib.Toupcam_get_AutoExpoRange.restype = ctypes.c_int
            cls.__lib.Toupcam_get_AutoExpoRange.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_AutoExpoRange.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_ushort), ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_put_MaxAutoExpoTimeAGain.restype = ctypes.c_int
            cls.__lib.Toupcam_put_MaxAutoExpoTimeAGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_MaxAutoExpoTimeAGain.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ushort]
            cls.__lib.Toupcam_get_MaxAutoExpoTimeAGain.restype = ctypes.c_int
            cls.__lib.Toupcam_get_MaxAutoExpoTimeAGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_MaxAutoExpoTimeAGain.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_put_MinAutoExpoTimeAGain.restype = ctypes.c_int
            cls.__lib.Toupcam_put_MinAutoExpoTimeAGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_MinAutoExpoTimeAGain.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ushort]
            cls.__lib.Toupcam_get_MinAutoExpoTimeAGain.restype = ctypes.c_int
            cls.__lib.Toupcam_get_MinAutoExpoTimeAGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_MinAutoExpoTimeAGain.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_put_ExpoTime.restype = ctypes.c_int
            cls.__lib.Toupcam_put_ExpoTime.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_ExpoTime.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            cls.__lib.Toupcam_get_ExpoTime.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ExpoTime.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ExpoTime.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_get_RealExpoTime.restype = ctypes.c_int
            cls.__lib.Toupcam_get_RealExpoTime.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_RealExpoTime.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_get_ExpTimeRange.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ExpTimeRange.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ExpTimeRange.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_put_ExpoAGain.restype = ctypes.c_int
            cls.__lib.Toupcam_put_ExpoAGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_ExpoAGain.argtypes = [ctypes.c_void_p, ctypes.c_ushort]
            cls.__lib.Toupcam_get_ExpoAGain.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ExpoAGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ExpoAGain.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_get_ExpoAGainRange.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ExpoAGainRange.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ExpoAGainRange.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort), ctypes.POINTER(ctypes.c_ushort), ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_AwbOnce.restype = ctypes.c_int
            cls.__lib.Toupcam_AwbOnce.errcheck = cls.__errcheck
            cls.__lib.Toupcam_AwbOnce.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            cls.__lib.Toupcam_AwbInit.restype = ctypes.c_int
            cls.__lib.Toupcam_AwbInit.errcheck = cls.__errcheck
            cls.__lib.Toupcam_AwbInit.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            cls.__lib.Toupcam_put_TempTint.restype = ctypes.c_int
            cls.__lib.Toupcam_put_TempTint.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_TempTint.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            cls.__lib.Toupcam_get_TempTint.restype = ctypes.c_int
            cls.__lib.Toupcam_get_TempTint.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_TempTint.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_WhiteBalanceGain.restype = ctypes.c_int
            cls.__lib.Toupcam_put_WhiteBalanceGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_WhiteBalanceGain.argtypes = [ctypes.c_void_p, (ctypes.c_int * 3)]
            cls.__lib.Toupcam_get_WhiteBalanceGain.restype = ctypes.c_int
            cls.__lib.Toupcam_get_WhiteBalanceGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_WhiteBalanceGain.argtypes = [ctypes.c_void_p, (ctypes.c_int * 3)]
            cls.__lib.Toupcam_put_BlackBalance.restype = ctypes.c_int
            cls.__lib.Toupcam_put_BlackBalance.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_BlackBalance.argtypes = [ctypes.c_void_p, (ctypes.c_ushort * 3)]
            cls.__lib.Toupcam_get_BlackBalance.restype = ctypes.c_int
            cls.__lib.Toupcam_get_BlackBalance.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_BlackBalance.argtypes = [ctypes.c_void_p, (ctypes.c_ushort * 3)]
            cls.__lib.Toupcam_AbbOnce.restype = ctypes.c_int
            cls.__lib.Toupcam_AbbOnce.errcheck = cls.__errcheck
            cls.__lib.Toupcam_AbbOnce.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            cls.__lib.Toupcam_FfcOnce.restype = ctypes.c_int
            cls.__lib.Toupcam_FfcOnce.errcheck = cls.__errcheck
            cls.__lib.Toupcam_FfcOnce.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_DfcOnce.restype = ctypes.c_int
            cls.__lib.Toupcam_DfcOnce.errcheck = cls.__errcheck
            cls.__lib.Toupcam_DfcOnce.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_FpncOnce.restype = ctypes.c_int
            cls.__lib.Toupcam_FpncOnce.errcheck = cls.__errcheck
            cls.__lib.Toupcam_FpncOnce.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_FfcExport.restype = ctypes.c_int
            cls.__lib.Toupcam_FfcExport.errcheck = cls.__errcheck
            cls.__lib.Toupcam_FfcImport.restype = ctypes.c_int
            cls.__lib.Toupcam_FfcImport.errcheck = cls.__errcheck
            cls.__lib.Toupcam_DfcExport.restype = ctypes.c_int
            cls.__lib.Toupcam_DfcExport.errcheck = cls.__errcheck
            cls.__lib.Toupcam_DfcImport.restype = ctypes.c_int
            cls.__lib.Toupcam_DfcImport.errcheck = cls.__errcheck
            cls.__lib.Toupcam_FpncExport.restype = ctypes.c_int
            cls.__lib.Toupcam_FpncExport.errcheck = cls.__errcheck
            cls.__lib.Toupcam_FpncImport.restype = ctypes.c_int
            cls.__lib.Toupcam_FpncImport.errcheck = cls.__errcheck
            if sys.platform == 'win32':
                cls.__lib.Toupcam_FfcExport.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
                cls.__lib.Toupcam_FfcImport.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
                cls.__lib.Toupcam_DfcExport.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
                cls.__lib.Toupcam_DfcImport.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
                cls.__lib.Toupcam_FpncExport.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
                cls.__lib.Toupcam_FpncImport.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
            else:
                cls.__lib.Toupcam_FfcExport.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                cls.__lib.Toupcam_FfcImport.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                cls.__lib.Toupcam_DfcExport.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                cls.__lib.Toupcam_DfcImport.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                cls.__lib.Toupcam_FpncExport.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                cls.__lib.Toupcam_FpncImport.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            cls.__lib.Toupcam_put_Hue.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Hue.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Hue.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Hue.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Hue.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Hue.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Saturation.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Saturation.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Saturation.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Saturation.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Saturation.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Saturation.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Brightness.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Brightness.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Brightness.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Brightness.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Brightness.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Brightness.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Contrast.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Contrast.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Contrast.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Contrast.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Contrast.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Contrast.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Gamma.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Gamma.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Gamma.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Gamma.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Gamma.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Gamma.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Chrome.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Chrome.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Chrome.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Chrome.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Chrome.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Chrome.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_VFlip.restype = ctypes.c_int
            cls.__lib.Toupcam_put_VFlip.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_VFlip.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_VFlip.restype = ctypes.c_int
            cls.__lib.Toupcam_get_VFlip.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_VFlip.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_HFlip.restype = ctypes.c_int
            cls.__lib.Toupcam_put_HFlip.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_HFlip.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_HFlip.restype = ctypes.c_int
            cls.__lib.Toupcam_get_HFlip.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_HFlip.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Negative.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Negative.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Negative.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Negative.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Negative.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Negative.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Speed.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Speed.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Speed.argtypes = [ctypes.c_void_p, ctypes.c_ushort]
            cls.__lib.Toupcam_get_Speed.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Speed.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Speed.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_get_MaxSpeed.restype = ctypes.c_int
            cls.__lib.Toupcam_get_MaxSpeed.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_MaxSpeed.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_get_FanMaxSpeed.restype = ctypes.c_int
            cls.__lib.Toupcam_get_FanMaxSpeed.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_FanMaxSpeed.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_get_MaxBitDepth.restype = ctypes.c_int
            cls.__lib.Toupcam_get_MaxBitDepth.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_MaxBitDepth.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_put_HZ.restype = ctypes.c_int
            cls.__lib.Toupcam_put_HZ.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_HZ.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_HZ.restype = ctypes.c_int
            cls.__lib.Toupcam_get_HZ.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_HZ.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_Mode.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Mode.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Mode.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_Mode.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Mode.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Mode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_AWBAuxRect.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AWBAuxRect.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AWBAuxRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__RECT)]
            cls.__lib.Toupcam_get_AWBAuxRect.restype = ctypes.c_int
            cls.__lib.Toupcam_get_AWBAuxRect.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_AWBAuxRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__RECT)]
            cls.__lib.Toupcam_put_AEAuxRect.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AEAuxRect.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AEAuxRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__RECT)]
            cls.__lib.Toupcam_get_AEAuxRect.restype = ctypes.c_int
            cls.__lib.Toupcam_get_AEAuxRect.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_AEAuxRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__RECT)]
            cls.__lib.Toupcam_put_ABBAuxRect.restype = ctypes.c_int
            cls.__lib.Toupcam_put_ABBAuxRect.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_ABBAuxRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__RECT)]
            cls.__lib.Toupcam_get_ABBAuxRect.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ABBAuxRect.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ABBAuxRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__RECT)]
            cls.__lib.Toupcam_get_MonoMode.restype = ctypes.c_int
            cls.__lib.Toupcam_get_MonoMode.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_MonoMode.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_get_StillResolutionNumber.restype = ctypes.c_int
            cls.__lib.Toupcam_get_StillResolutionNumber.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_StillResolutionNumber.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_get_StillResolution.restype = ctypes.c_int
            cls.__lib.Toupcam_get_StillResolution.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_StillResolution.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_put_RealTime.restype = ctypes.c_int
            cls.__lib.Toupcam_put_RealTime.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_RealTime.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_RealTime.restype = ctypes.c_int
            cls.__lib.Toupcam_get_RealTime.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_RealTime.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_Flush.restype = ctypes.c_int
            cls.__lib.Toupcam_Flush.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Flush.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_put_Temperature.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Temperature.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Temperature.argtypes = [ctypes.c_void_p, ctypes.c_short]
            cls.__lib.Toupcam_get_Temperature.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Temperature.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Temperature.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_short)]
            cls.__lib.Toupcam_get_Revision.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Revision.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Revision.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_get_SerialNumber.restype = ctypes.c_int
            cls.__lib.Toupcam_get_SerialNumber.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_SerialNumber.argtypes = [ctypes.c_void_p, ctypes.c_char * 32]
            cls.__lib.Toupcam_get_FwVersion.restype = ctypes.c_int
            cls.__lib.Toupcam_get_FwVersion.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_FwVersion.argtypes = [ctypes.c_void_p, ctypes.c_char * 16]
            cls.__lib.Toupcam_get_HwVersion.restype = ctypes.c_int
            cls.__lib.Toupcam_get_HwVersion.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_HwVersion.argtypes = [ctypes.c_void_p, ctypes.c_char * 16]
            cls.__lib.Toupcam_get_ProductionDate.restype = ctypes.c_int
            cls.__lib.Toupcam_get_ProductionDate.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_ProductionDate.argtypes = [ctypes.c_void_p, ctypes.c_char * 16]
            cls.__lib.Toupcam_get_FpgaVersion.restype = ctypes.c_int
            cls.__lib.Toupcam_get_FpgaVersion.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_FpgaVersion.argtypes = [ctypes.c_void_p, ctypes.c_char * 16]
            cls.__lib.Toupcam_get_PixelSize.restype = ctypes.c_int
            cls.__lib.Toupcam_get_PixelSize.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_PixelSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
            cls.__lib.Toupcam_put_LevelRange.restype = ctypes.c_int
            cls.__lib.Toupcam_put_LevelRange.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_LevelRange.argtypes = [ctypes.c_void_p, (ctypes.c_ushort * 4), (ctypes.c_ushort * 4)]
            cls.__lib.Toupcam_get_LevelRange.restype = ctypes.c_int
            cls.__lib.Toupcam_get_LevelRange.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_LevelRange.argtypes = [ctypes.c_void_p, (ctypes.c_ushort * 4), (ctypes.c_ushort * 4)]
            cls.__lib.Toupcam_put_LevelRangeV2.restype = ctypes.c_int
            cls.__lib.Toupcam_put_LevelRangeV2.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_LevelRangeV2.argtypes = [ctypes.c_void_p, ctypes.c_ushort, ctypes.POINTER(cls.__RECT), (ctypes.c_ushort * 4), (ctypes.c_ushort * 4)]
            cls.__lib.Toupcam_get_LevelRangeV2.restype = ctypes.c_int
            cls.__lib.Toupcam_get_LevelRangeV2.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_LevelRangeV2.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort), ctypes.POINTER(cls.__RECT), (ctypes.c_ushort * 4), (ctypes.c_ushort * 4)]
            cls.__lib.Toupcam_LevelRangeAuto.restype = ctypes.c_int
            cls.__lib.Toupcam_LevelRangeAuto.errcheck = cls.__errcheck
            cls.__lib.Toupcam_LevelRangeAuto.argtypes = [ctypes.c_void_p]
            cls.__lib.Toupcam_put_LEDState.restype = ctypes.c_int
            cls.__lib.Toupcam_put_LEDState.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_LEDState.argtypes = [ctypes.c_void_p, ctypes.c_ushort, ctypes.c_ushort, ctypes.c_ushort, ctypes.c_ushort]
            cls.__lib.Toupcam_write_EEPROM.restype = ctypes.c_int
            cls.__lib.Toupcam_write_EEPROM.errcheck = cls.__errcheck
            cls.__lib.Toupcam_write_EEPROM.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_uint]
            cls.__lib.Toupcam_read_EEPROM.restype = ctypes.c_int
            cls.__lib.Toupcam_read_EEPROM.errcheck = cls.__errcheck
            cls.__lib.Toupcam_read_EEPROM.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_uint]
            cls.__lib.Toupcam_rwc_Flash.restype = ctypes.c_int
            cls.__lib.Toupcam_rwc_Flash.errcheck = cls.__errcheck
            cls.__lib.Toupcam_rwc_Flash.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_char_p]
            cls.__lib.Toupcam_read_Pipe.restype = ctypes.c_int
            cls.__lib.Toupcam_read_Pipe.errcheck = cls.__errcheck
            cls.__lib.Toupcam_read_Pipe.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_uint]
            cls.__lib.Toupcam_write_Pipe.restype = ctypes.c_int
            cls.__lib.Toupcam_write_Pipe.errcheck = cls.__errcheck
            cls.__lib.Toupcam_write_Pipe.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_char_p, ctypes.c_uint]
            cls.__lib.Toupcam_feed_Pipe.restype = ctypes.c_int
            cls.__lib.Toupcam_feed_Pipe.errcheck = cls.__errcheck
            cls.__lib.Toupcam_feed_Pipe.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            cls.__lib.Toupcam_put_Option.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Option.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Option.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int]
            cls.__lib.Toupcam_get_Option.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Option.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Option.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_get_PixelFormatSupport.restype = ctypes.c_int
            cls.__lib.Toupcam_get_PixelFormatSupport.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_PixelFormatSupport.argtypes = [ctypes.c_void_p, ctypes.c_char, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_get_PixelFormatName.restype = ctypes.c_char_p
            cls.__lib.Toupcam_get_PixelFormatName.argtypes = [ctypes.c_int]
            cls.__lib.Toupcam_put_Roi.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Roi.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Roi.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
            cls.__lib.Toupcam_get_Roi.restype = ctypes.c_int
            cls.__lib.Toupcam_get_Roi.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_Roi.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_put_RoiN.restype = ctypes.c_int
            cls.__lib.Toupcam_put_RoiN.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_RoiN.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.c_uint]
            cls.__lib.Toupcam_put_XY.restype = ctypes.c_int
            cls.__lib.Toupcam_put_XY.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_XY.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            cls.__lib.Toupcam_put_SelfTrigger.restype = ctypes.c_int
            cls.__lib.Toupcam_put_SelfTrigger.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_SelfTrigger.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__SelfTrigger)]
            cls.__lib.Toupcam_get_SelfTrigger.restype = ctypes.c_int
            cls.__lib.Toupcam_get_SelfTrigger.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_SelfTrigger.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__SelfTrigger)]
            cls.__lib.Toupcam_get_LensInfo.restype = ctypes.c_int
            cls.__lib.Toupcam_get_LensInfo.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_LensInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_get_AFState.restype = ctypes.c_int
            cls.__lib.Toupcam_get_AFState.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_AFState.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_put_AFMode.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AFMode.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AFMode.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            cls.__lib.Toupcam_put_AFRoi.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AFRoi.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AFRoi.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
            cls.__lib.Toupcam_put_AFAperture.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AFAperture.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AFAperture.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_put_AFFMPos.restype = ctypes.c_int
            cls.__lib.Toupcam_put_AFFMPos.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_AFFMPos.argtypes = [ctypes.c_void_p, ctypes.c_int]
            cls.__lib.Toupcam_get_FocusMotor.restype = ctypes.c_int
            cls.__lib.Toupcam_get_FocusMotor.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_FocusMotor.argtypes = [ctypes.c_void_p, ctypes.POINTER(cls.__FocusMotor)]
            cls.__lib.Toupcam_IoControl.restype = ctypes.c_int
            cls.__lib.Toupcam_IoControl.errcheck = cls.__errcheck
            cls.__lib.Toupcam_IoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_AAF.restype = ctypes.c_int
            cls.__lib.Toupcam_AAF.errcheck = cls.__errcheck
            cls.__lib.Toupcam_AAF.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            cls.__lib.Toupcam_read_UART.restype = ctypes.c_int
            cls.__lib.Toupcam_read_UART.errcheck = cls.__errcheck
            cls.__lib.Toupcam_read_UART.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint]
            cls.__lib.Toupcam_write_UART.restype = ctypes.c_int
            cls.__lib.Toupcam_write_UART.errcheck = cls.__errcheck
            cls.__lib.Toupcam_write_UART.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint]
            cls.__lib.Toupcam_put_Linear.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Linear.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Linear.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_put_Curve.restype = ctypes.c_int
            cls.__lib.Toupcam_put_Curve.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_Curve.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ushort)]
            cls.__lib.Toupcam_put_ColorMatrix.restype = ctypes.c_int
            cls.__lib.Toupcam_put_ColorMatrix.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_ColorMatrix.argtypes = [ctypes.c_void_p, ctypes.c_double * 9]
            cls.__lib.Toupcam_put_InitWBGain.restype = ctypes.c_int
            cls.__lib.Toupcam_put_InitWBGain.errcheck = cls.__errcheck
            cls.__lib.Toupcam_put_InitWBGain.argtypes = [ctypes.c_void_p, ctypes.c_ushort * 3]
            cls.__lib.Toupcam_get_FrameRate.restype = ctypes.c_int
            cls.__lib.Toupcam_get_FrameRate.errcheck = cls.__errcheck
            cls.__lib.Toupcam_get_FrameRate.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
            cls.__lib.Toupcam_GetHistogramV2.restype = ctypes.c_int
            cls.__lib.Toupcam_GetHistogramV2.errcheck = cls.__errcheck
            cls.__lib.Toupcam_GetHistogramV2.argtypes = [ctypes.c_void_p, cls.__HISTOGRAM_CALLBACK, ctypes.py_object]
            cls.__lib.Toupcam_GigeEnable.restype = ctypes.c_int
            cls.__lib.Toupcam_GigeEnable.argtypes = [cls.__HOTPLUG_CALLBACK, ctypes.c_void_p]
            cls.__lib.Toupcam_Gain2TempTint.restype = ctypes.c_int
            cls.__lib.Toupcam_Gain2TempTint.errcheck = cls.__errcheck
            cls.__lib.Toupcam_Gain2TempTint.argtypes = [ctypes.c_int * 3, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)];
            cls.__lib.Toupcam_TempTint2Gain.restype = None
            cls.__lib.Toupcam_TempTint2Gain.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int * 3];
            if sys.platform != 'win32' and sys.platform != 'android':
                cls.__lib.Toupcam_HotPlug.restype = None
                cls.__lib.Toupcam_HotPlug.argtypes = [cls.__HOTPLUG_CALLBACK, ctypes.c_void_p]