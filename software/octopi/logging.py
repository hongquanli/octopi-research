import logging
import threading
from typing import Optional, Type
from types import TracebackType
import sys

_octopi_root_logger_name="octopi"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Returns the top level octopi logger instance by default, or a logger in the octopi
    logging hierarchy if a non-None name is given.
    """
    if name is None:
        return logging.getLogger(_octopi_root_logger_name)
    else:
        return logging.getLogger(_octopi_root_logger_name).getChild(name)


def set_log_level(level):
    """
    All octopi-research code should use this set_log_level method, and the corresponding octopi.logging.get_logger,
    to control octopi-research-only logging.

    This does not modify the log level of loggers outside the octopi logger hierarchy! If global logging control
    is needed the normal logging package tools can be used instead.
    """
    octopi_root_logger = get_logger()
    octopi_root_logger.setLevel(level)

    # There's no `getAllChildren` method on the logger or its manager, so we just grab the manager
    # for our root logger and then check all other loggers to see if they start with our root logger prefix
    # to find all the octopi specific logger.
    for (name, logger) in octopi_root_logger.manager.loggerDict.items():
        if name.startswith(_octopi_root_logger_name):
            logger.setLevel(level)

def register_crash_handler(handler):
    """
    We want to make sure any uncaught exceptions are logged, so we have this mechanism for putting a hook into
    the python system that does custom logging when an exception bubbles all the way to the top.

    NOTE: We do our best below, but it is a really bad idea for your handler to raise an exception.
    """
    # The sys.excepthook docs are a good entry point for all of this
    # (here: https://docs.python.org/3/library/sys.html#sys.excepthook), but essentially there are 3 different ways
    # threads of execution can blow up.  We want to catch and log all 3 of them.
    old_excepthook = sys.excepthook
    old_thread_excepthook = threading.excepthook
    # The unraisable hook doesn't have the same signature as the excepthooks, but we can sort of shoehorn the arguments
    # into the same signature.  Also, this is an extremely rare (I'm not sure I've ever seen it?) failure mode, so
    # it should be okay.
    old_unraisable_hook = sys.unraisablehook

    logger = get_logger()

    def new_excepthook(exception_type: Type[BaseException], value: BaseException, tb: TracebackType):
        try:
            handler(exception_type, value, tb)
        except BaseException as e:
            logger.critical("Custom excepthook handler raised exception", e)
        old_excepthook(exception_type, value, tb)

    def new_thread_excepthook(exception_type: Type[BaseException], value: BaseException, tb: TracebackType):
        try:
            handler(exception_type, value, tb)
        except BaseException as e:
            logger.critical("Custom thread excepthook handler raised exception", e)
        old_thread_excepthook(exception_type, value, tb)

    def new_unraisable_hook(info):
        exception_type = info["exception_type"]
        tb = info["exception_traceback"]
        value = info["exception_value"]
        try:
            handler(exception_type, value, tb)
        except BaseException as e:
            logger.critical("Custom unraisable hook handler raised exception", e)
        old_unraisable_hook(info)

    logger.info(f"Registering custom excepthook, threading excepthook, and unraisable hook using handler={handler.__name__}")
    sys.excepthook = new_excepthook
    threading.excepthook = new_thread_excepthook
    sys.unraisablehook = new_unraisable_hook