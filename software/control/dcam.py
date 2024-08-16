"""Module to control DCAM on the console.
This imports dcamapi4 and implements functions and classes 
Dcamapi and Dcam to make DCAM easier to use.
Dcamapi initializes DCAM only.
The declarations of classes and functions in this file 
are subject to change without notice.
"""

__date__ = '2021-06-30'
__copyright__ = 'Copyright (C) 2021-2024 Hamamatsu Photonics K.K.'

from control.dcamapi4 import *
# DCAM-API v4 module

import numpy as np
# pip install numpy
# allocated to receive the image data


# ==== DCAMAPI helper functions ====

def dcammisc_setupframe(hdcam, bufframe: DCAMBUF_FRAME):
    """Setup DCAMBUF_FRAME instance.
    Setup DCAMBUF_FRAME instance based on camera setting with hdcam.

    Args:
        hdcam (c_void_p): DCAM handle.
        bufframe (DCAMBUF_FRAME): Frame information.
    
    Returns:
        DCAMERR: DCAMERR value.
    """
    fValue = c_double()
    idprop = DCAM_IDPROP.IMAGE_PIXELTYPE
    err = dcamprop_getvalue(hdcam, idprop, byref(fValue))
    if not err.is_failed():
        bufframe.type = int(fValue.value)

        idprop = DCAM_IDPROP.IMAGE_WIDTH
        err = dcamprop_getvalue(hdcam, idprop, byref(fValue))
        if not err.is_failed():
            bufframe.width = int(fValue.value)
            
            idprop = DCAM_IDPROP.IMAGE_HEIGHT
            err = dcamprop_getvalue(hdcam, idprop, byref(fValue))
            if not err.is_failed():
                bufframe.height = int(fValue.value)
                
                idprop = DCAM_IDPROP.FRAMEBUNDLE_MODE
                err = dcamprop_getvalue(hdcam, idprop, byref(fValue))
                if not err.is_failed() and int(fValue.value) == DCAMPROP.MODE.ON:
                    idprop = DCAM_IDPROP.FRAMEBUNDLE_ROWBYTES
                    err = dcamprop_getvalue(hdcam, idprop, byref(fValue))
                    if not err.is_failed():
                        bufframe.rowbytes = int(fValue.value)
                else:
                    idprop = DCAM_IDPROP.IMAGE_ROWBYTES
                    err = dcamprop_getvalue(hdcam, idprop, byref(fValue))
                    if not err.is_failed():
                        bufframe.rowbytes = int(fValue.value)

    return err


def dcammisc_alloc_ndarray(frame: DCAMBUF_FRAME, framebundlenum=1):
    """Allocate NumPy ndarray.
    Allocate NumPy ndarray based on information of DCAMBUF_FRAME.

    Args:
        frame (DCAMBUF_FRAME): Frame information.
        framebundlenum (int): Frame Bundle number.
    
    Returns:
        NumPy ndarray: NumPy ndarray buffer.
        bool: False if failed to allocate NumPy ndarray buffer.
    """
    height = frame.height * framebundlenum
        
    if frame.type == DCAM_PIXELTYPE.MONO16:
        return np.zeros((height, frame.width), dtype='uint16')

    if frame.type == DCAM_PIXELTYPE.MONO8:
        return np.zeros((height, frame.width), dtype='uint8')

    return False


# ==== declare Dcamapi class ====


class Dcamapi:
    # class instance
    __lasterr = DCAMERR.SUCCESS  # the last error from functions with dcamapi_ prefix.
    __bInitialized = False  # Once Dcamapi.init() is called, then True.  Dcamapi.uninit() reset this.
    __devicecount = 0

    @classmethod
    def __result(cls, errvalue):
        """Keep last error code.
        Internal use. Keep last error code.
        """
        if errvalue < 0:
            cls.__lasterr = errvalue
            return False

        return True

    @classmethod
    def lasterr(cls):
        """Return last error code.
        Return last error code of Dcamapi member functions.
        """
        return cls.__lasterr

    @classmethod
    def init(cls, *initparams):
        """Initialize DCAM-API.
        Initialize DCAM-API.
        Do not call this when Dcam object exists because constructor of Dcam ececute this.
        After calling close(), call this again if you need to resume measurement.

        Returns:
            bool: True if initialize DCAM-API was succeeded. False if dcamapi_init() returned DCAMERR except SUCCESS. lasterr() returns the DCAMERR value.
        """
        if cls.__bInitialized:
            return cls.__result(DCAMERR.ALREADYINITIALIZED)  # dcamapi_init() is called. New Error.

        paraminit = DCAMAPI_INIT()
        err = dcamapi_init(byref(paraminit))
        cls.__bInitialized = True
        if cls.__result(err) is False:
            return False

        cls.__devicecount = paraminit.iDeviceCount
        return True, cls.__devicecount

    @classmethod
    def uninit(cls):
        """Uninitialize DCAM-API.
        Uninitialize DCAM-API.
        After using DCAM-API, call this function to close all resources.

        Returns:
            bool: True if uninitialize DCAM-API was succeeded.
        """
        if cls.__bInitialized:
            dcamapi_uninit()
            cls.__lasterr = DCAMERR.SUCCESS
            cls.__bInitialized = False
            cls.__devicecount = 0

        return True

    @classmethod
    def get_devicecount(cls):
        """Return number of connected cameras.
        Return number of connected cameras.

        Returns:
            int: Number of connected cameras.
            bool: False if not initialized.
        """
        if not cls.__bInitialized:
            return False

        return cls.__devicecount

# ==== Dcam class ====


class Dcam:
    def __init__(self, iDevice=0):
        self.__lasterr = DCAMERR.SUCCESS
        self.__iDevice = iDevice
        self.__hdcam = 0
        self.__hdcamwait = 0
        self.__bufframe = DCAMBUF_FRAME()

    def __repr__(self):
        return 'Dcam()'

    def __result(self, errvalue):
        """Keep last error code.
        Internal use. Keep last error code.
        """
        if errvalue < 0:
            self.__lasterr = errvalue
            return False

        return True

    def lasterr(self):
        """Return last error code.
        Return last error code of Dcam member functions.
        """
        return self.__lasterr

    def is_opened(self):
        """Check DCAM handle is opened.
        Check DCAM handle is opened.

        Returns:
            bool: True if DCAM handle is opened. False if DCAM handle is not opened.
        """
        if self.__hdcam == 0:
            return False
        else:
            return True

    def dev_open(self, index=-1):
        """Get DCAM handle.
        Get DCAM handle for controling camera.
        After calling close(), call this again if you need to resume measurement.

        Args:
            index (int): Device index.

        Returns:
            bool: True if get DCAM handle was succeeded. False if dcamdev_open() returned DCAMERR except SUCCESS. lasterr() returns the DCAMERR value.
        """
        if self.is_opened():
            return self.__result(DCAMERR.ALREADYOPENED)  # instance is already opened. New Error.

        paramopen = DCAMDEV_OPEN()
        if index >= 0:
            paramopen.index = index
        else:
            paramopen.index = self.__iDevice

        ret = self.__result(dcamdev_open(byref(paramopen)))
        if ret is False:
            return False

        self.__hdcam = paramopen.hdcam
        return True

    def dev_close(self):
        """Close DCAM handle.
        Close DCAM handle.
        Call this if you need to close the current device.

        Returns:
            bool: True if close DCAM handle was succeeded.
        """
        if self.is_opened():
            self.__close_hdcamwait()
            dcamdev_close(self.__hdcam)
            self.__lasterr = DCAMERR.SUCCESS
            self.__hdcam = 0

        return True

    def dev_getstring(self, idstr: DCAM_IDSTR):
        """Get string of device.
        Get string of device.

        Args:
            idstr (DCAM_IDSTR): String id.

        Returns:
            string: Device information specified by DCAM_IDSTR.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if self.is_opened():
            hdcam = self.__hdcam
        else:
            hdcam = self.__iDevice

        paramdevstr = DCAMDEV_STRING()
        paramdevstr.iString = idstr
        paramdevstr.alloctext(256)

        ret = self.__result(dcamdev_getstring(hdcam, byref(paramdevstr)))
        if ret is False:
            return False

        return paramdevstr.text.decode()

    # dcamprop functions

    def prop_getattr(self, idprop: DCAM_IDPROP):
        """Get property attribute.
        Get property attribute.

        args:
            idprop (DCAM_IDPROP): Property id.

        Returns:
            DCAMPROP_ATTR: Attribute information of the property.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        propattr = DCAMPROP_ATTR()
        propattr.iProp = idprop
        ret = self.__result(dcamprop_getattr(self.__hdcam, byref(propattr)))
        if ret is False:
            return False

        return propattr

    def prop_getvalue(self, idprop: DCAM_IDPROP):
        """Get property value.
        Get property value.

        args:
            idprop (DCAM_IDPROP): Property id.

        Returns:
            float: Property value of property id.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cDouble = c_double()
        ret = self.__result(dcamprop_getvalue(self.__hdcam, idprop, byref(cDouble)))
        if ret is False:
            return False

        return cDouble.value

    def prop_setvalue(self, idprop: DCAM_IDPROP, fValue):
        """Set property value.
        Set property value.

        args:
            idprop (DCAM_IDPROP): Property id.
            fValue (float): Setting value.

        Returns:
            bool: True if set property value was succeeded. False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        ret = self.__result(dcamprop_setvalue(self.__hdcam, idprop, fValue))
        if ret is False:
            return False

        return True

    def prop_setgetvalue(self, idprop: DCAM_IDPROP, fValue, option=0):
        """Set and get property value.
        Set and get property value.

        args:
            idprop (DCAM_IDPROP): Property id.
            fValue (float): Input value for setting and receive actual set value by ref.

        Returns:
            float: Accurate value set in device.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cDouble = c_double(fValue)
        cOption = c_int32(option)
        ret = self.__result(dcamprop_setgetvalue(self.__hdcam, idprop, byref(cDouble), cOption))
        if ret is False:
            return False

        return cDouble.value

    def prop_queryvalue(self, idprop: DCAM_IDPROP, fValue, option=0):
        """Query property value.
        Query property value.

        Args:
            idprop (DCAM_IDPROP): Property id.
            fValue (float): Value of property.

        Returns:
            float: Property value specified by option.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cDouble = c_double(fValue)
        cOption = c_int32(option)
        ret = self.__result(dcamprop_queryvalue(self.__hdcam, idprop, byref(cDouble), cOption))
        if ret is False:
            return False

        return cDouble.value

    def prop_getnextid(self, idprop: DCAM_IDPROP):
        """Get next property id.
        Get next property id.

        Args:
            idprop (DCAM_IDPROP): Property id.

        Returns:
            DCAM_IDPROP: Next property id.
            bool: False if no more property or error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cIdprop = c_int32(idprop)
        cOption = c_int32(0)  # search next ID

        ret = self.__result(dcamprop_getnextid(self.__hdcam, byref(cIdprop), cOption))
        if ret is False:
            return False

        return cIdprop.value

    def prop_getname(self, idprop: DCAM_IDPROP):
        """Get name of property.
        Get name of property.

        Args:
            idprop (DCAM_IDPROP): Property id.

        Returns:
            string: Caracter string of property id.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        textbuf = create_string_buffer(256)
        ret = self.__result(dcamprop_getname(self.__hdcam, idprop, textbuf, sizeof(textbuf)))
        if ret is False:
            return False

        return textbuf.value.decode()

    def prop_getvaluetext(self, idprop: DCAM_IDPROP, fValue):
        """Get text of property value.
        Get text of property value.

        Args:
            idprop (DCAM_IDPROP): Property id.
            fValue (float): Setting value.

        Returns:
            string: Caracter string of property value.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        paramvaluetext = DCAMPROP_VALUETEXT()
        paramvaluetext.iProp = idprop
        paramvaluetext.value = fValue
        paramvaluetext.alloctext(256)

        ret = self.__result(dcamprop_getvaluetext(self.__hdcam, byref(paramvaluetext)))
        if ret is False:
            return False

        return paramvaluetext.text.decode()

    # dcambuf functions

    def buf_alloc(self, nFrame):
        """Alloc DCAM internal buffer.
        Alloc DCAM internal buffer.

        Arg:
            nFrame (int): Number of frames.

        Returns:
            bool: True if buffer is prepared. False if buffer is not prepared. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cFrame = c_int32(nFrame)
        ret = self.__result(dcambuf_alloc(self.__hdcam, cFrame))
        if ret is False:
            return False

        return self.__result(dcammisc_setupframe(self.__hdcam, self.__bufframe))

    def buf_release(self):
        """Release DCAM internal buffer.
        Release DCAM internal buffer.

        Returns:
            bool: True if release DCAM internal buffser was succeeded. False if error happens during releasing buffer. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cOption = c_int32(0)
        return self.__result(dcambuf_release(self.__hdcam, cOption))

    def buf_getframe(self, iFrame):
        """Return DCAMBUF_FRAME instance.
        Return DCAMBUF_FRAME instance with image data specified by iFrame.

        Arg:
            iFrame (int): Index of target frame.

        Returns:
            (aFrame, npBuf): aFrame is DCAMBUF_FRAME, npBuf is NumPy buffer.
            bool: False if error happens. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.
        
        framebundlenum = 1

        fValue = c_double()
        err = dcamprop_getvalue(self.__hdcam, DCAM_IDPROP.FRAMEBUNDLE_MODE, byref(fValue))
        if not err.is_failed() and int(fValue.value) == DCAMPROP.MODE.ON:
            err = dcamprop_getvalue(self.__hdcam, DCAM_IDPROP.FRAMEBUNDLE_NUMBER, byref(fValue))
            if not err.is_failed():
                framebundlenum = int(fValue.value)
            else:
                return False
        
        npBuf = dcammisc_alloc_ndarray(self.__bufframe, framebundlenum)
        if npBuf is False:
            return self.__result(DCAMERR.INVALIDPIXELTYPE)

        aFrame = DCAMBUF_FRAME()
        aFrame.iFrame = iFrame

        aFrame.buf = npBuf.ctypes.data_as(c_void_p)
        aFrame.rowbytes = self.__bufframe.rowbytes
        aFrame.type = self.__bufframe.type
        aFrame.width = self.__bufframe.width
        aFrame.height = self.__bufframe.height

        ret = self.__result(dcambuf_copyframe(self.__hdcam, byref(aFrame)))
        if ret is False:
            return False

        return (aFrame, npBuf)

    def buf_getframedata(self, iFrame):
        """Return NumPy buffer.
        Return NumPy buffer of image data specified by iFrame.

        Arg:
            iFrame (int): Index of target frame.

        Returns:
            npBuf: NumPy buffer.
            bool: False if error happens. lasterr() returns the DCAMERR value.
        """
        ret = self.buf_getframe(iFrame)
        if ret is False:
            return False

        return ret[1]

    def buf_getlastframedata(self):
        """Return NumPy buffer of last updated.
        Return NumPy buffer of image data of last updated frame.

        Returns:
            npBuf: NumPy buffer.
            bool: False if error happens. lasterr() returns the DCAMERR value.
        """
        return self.buf_getframedata(-1)

    # dcamcap functions

    def cap_start(self, bSequence=True):
        """Start capturing.
        Start capturing.

        Arg:
            bSequence (bool): False means SNAPSHOT, others means SEQUENCE.

        Returns:
            bool: True if start capture. False if error happened.  lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        if bSequence:
            mode = DCAMCAP_START.SEQUENCE
        else:
            mode = DCAMCAP_START.SNAP

        return self.__result(dcamcap_start(self.__hdcam, mode))

    def cap_snapshot(self):
        """Capture snapshot.
        Capture snapshot. Get the frames specified in buf_alloc().

        Returns:
            bool: True if start snapshot. False if error happened. lasterr() returns the DCAMERR value.
        """
        return self.cap_start(False)

    def cap_stop(self):
        """Stop capturing.
        Stop capturing.

        Returns:
            bool: True if Stop capture. False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        return self.__result(dcamcap_stop(self.__hdcam))

    def cap_status(self):
        """Get capture status.
        Get capture status.

        Returns:
            DCAMCAP_STATUS: Current capturing status.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cStatus = c_int32()
        ret = self.__result(dcamcap_status(self.__hdcam, byref(cStatus)))
        if ret is False:
            return False

        return cStatus.value

    def cap_transferinfo(self):
        """Get transfer info.
        Get transfer info.

        Returns:
            DCAMCAP_TRANSFERINFO: Current image transfer status.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        paramtransferinfo = DCAMCAP_TRANSFERINFO()
        ret = self.__result(dcamcap_transferinfo(self.__hdcam, byref(paramtransferinfo)))
        if ret is False:
            return False

        return paramtransferinfo

    def cap_firetrigger(self):
        """Fire software trigger.
        Fire software trigger.

        Returns:
            bool: True if firing trigger was succeeded. False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.is_opened():
            return self.__result(DCAMERR.INVALIDHANDLE)  # instance is not opened yet.

        cOption = c_int32(0)
        ret = self.__result(dcamcap_firetrigger(self.__hdcam, cOption))
        if ret is False:
            return False

        return True


    # dcamwait functions

    def __open_hdcamwait(self):
        """Get DCAMWAIT handle.
        Get DCAMWAIT handle.

        Returns:
            bool: True if get DCAMWAIT handle was succeeded. False if error happened. lasterr() returns the DCAMERR value.
        """
        if not self.__hdcamwait == 0:
            return True

        paramwaitopen = DCAMWAIT_OPEN()
        paramwaitopen.hdcam = self.__hdcam
        ret = self.__result(dcamwait_open(byref(paramwaitopen)))
        if ret is False:
            return False

        if paramwaitopen.hwait == 0:
            return self.__result(DCAMERR.INVALIDWAITHANDLE)

        self.__hdcamwait = paramwaitopen.hwait
        return True

    def __close_hdcamwait(self):
        """Close DCAMWAIT handle.
        Close DCAMWAIT handle.

        Returns:
            bool: True if close DCAMWAIT handle was succeeded. False if error happened. lasterr() returns the DCAMERR value.
        """

        if self.__hdcamwait == 0:
            return True

        ret = self.__result(dcamwait_close(self.__hdcamwait))
        if ret is False:
            return False

        self.__hdcamwait = 0
        return True

    def wait_event(self, eventmask: DCAMWAIT_CAPEVENT, timeout_millisec):
        """Wait specified event.
        Wait specified event.

        Arg:
            eventmask (DCAMWAIT_CAPEVENT): Event mask to wait.
            timeout_millisec (int): Timeout by milliseconds.

        Returns:
            DCAMWAIT_CAPEVENT: Happened event.
            bool: False if error happened. lasterr() returns the DCAMERR value.
        """
        ret = self.__open_hdcamwait()
        if ret is False:
            return False

        paramwaitstart = DCAMWAIT_START()
        paramwaitstart.eventmask = eventmask
        paramwaitstart.timeout = timeout_millisec
        ret = self.__result(dcamwait_start(self.__hdcamwait, byref(paramwaitstart)))
        if ret is False:
            return False

        return paramwaitstart.eventhappened

    def wait_capevent_frameready(self, timeout_millisec):
        """Wait DCAMWAIT_CAPEVENT.FRAMEREADY event.
        Wait DCAMWAIT_CAPEVENT.FRAMEREADY event.

        Arg:
            timeout_millisec (int): Timeout by milliseconds.

        Returns:
            bool: True if wait capture. False if error happened. lasterr() returns the DCAMERR value.
        """
        ret = self.wait_event(DCAMWAIT_CAPEVENT.FRAMEREADY, timeout_millisec)
        if ret is False:
            return False

        # ret is DCAMWAIT_CAPEVENT.FRAMEREADY

        return True


