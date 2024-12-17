import logging as py_logging
import logging.handlers
import os.path
import threading
from typing import Optional, Type
from types import TracebackType
import sys
import platformdirs

_squid_root_logger_name = "squid"
_baseline_log_format = "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
_baseline_log_dateformat = "%Y-%m-%d %H:%M:%S"


# The idea for this CustomFormatter is cribbed from https://stackoverflow.com/a/56944256
class _CustomFormatter(py_logging.Formatter):
    GRAY = "\x1b[38;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    FORMAT = _baseline_log_format

    FORMATS = {
        py_logging.DEBUG: GRAY + FORMAT + RESET,
        py_logging.INFO: GRAY + FORMAT + RESET,
        py_logging.WARNING: YELLOW + FORMAT + RESET,
        py_logging.ERROR: RED + FORMAT + RESET,
        py_logging.CRITICAL: BOLD_RED + FORMAT + RESET
    }

    # NOTE(imo): The datetime hackery is so that we can have millisecond timestamps using a period instead
    # of comma.  The default asctime + datefmt uses a comma.
    FORMATTERS = {level: py_logging.Formatter(fmt, datefmt=_baseline_log_dateformat) for (level, fmt) in FORMATS.items()}

    def format(self, record):
        return self.FORMATTERS[record.levelno].format(record)

_COLOR_STREAM_HANDLER = py_logging.StreamHandler()
_COLOR_STREAM_HANDLER.setFormatter(_CustomFormatter())

# Make sure the squid root logger has all the handlers we want setup.  We could move this into a helper so it
# isn't done at the module level, but not needing to remember to call some helper to setup formatting is nice.
# Also set the default logging level to INFO on the stream handler, but DEBUG on the root logger so we can have
# other loggers at different levels.
_COLOR_STREAM_HANDLER.setLevel(py_logging.INFO)
py_logging.getLogger(_squid_root_logger_name).addHandler(_COLOR_STREAM_HANDLER)
py_logging.getLogger(_squid_root_logger_name).setLevel(py_logging.DEBUG)


def get_logger(name: Optional[str] = None) -> py_logging.Logger:
    """
    Returns the top level squid logger instance by default, or a logger in the squid
    logging hierarchy if a non-None name is given.
    """
    if name is None:
        logger = py_logging.getLogger(_squid_root_logger_name)
    else:
        logger = py_logging.getLogger(_squid_root_logger_name).getChild(name)

    return logger

log = get_logger(__name__)

def set_stdout_log_level(level):
    """
    All squid code should use this set_stdout_log_level method, and the corresponding squid.logging.get_logger,
    to control squid-only logging.

    This does not modify the log level of loggers outside the squid logger hierarchy! If global logging control
    is needed the normal logging package tools can be used instead.  It also leaves FileHandler log levels such that
    they can always be outputting everything (regardless of what we set the stdout log level to)
    """
    squid_root_logger = get_logger()

    for handler in squid_root_logger.handlers:
        # We always want the file handlers to capture everything, so don't touch them.
        if isinstance(handler, logging.FileHandler):
            continue
        handler.setLevel(level)


def register_crash_handler(handler, call_existing_too=True):
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
        if call_existing_too:
            old_excepthook(exception_type, value, tb)

    def new_thread_excepthook(hook_args: threading.ExceptHookArgs):
        exception_type = hook_args.exc_type
        value = hook_args.exc_type
        tb = hook_args.exc_traceback
        try:
            handler(exception_type, value, type(tb))
        except BaseException as e:
            logger.critical("Custom thread excepthook handler raised exception", e)
        if call_existing_too:
            old_thread_excepthook(exception_type, value, type(tb))

    def new_unraisable_hook(info):
        exception_type = info.exc_type
        tb = info.exc_traceback
        value = info.exc_value
        try:
            handler(exception_type, value, type(tb))
        except BaseException as e:
            logger.critical("Custom unraisable hook handler raised exception", e)
        if call_existing_too:
            old_unraisable_hook(info)

    logger.info(f"Registering custom excepthook, threading excepthook, and unraisable hook using handler={handler.__name__}")
    sys.excepthook = new_excepthook
    threading.excepthook = new_thread_excepthook
    sys.unraisablehook = new_unraisable_hook


def setup_uncaught_exception_logging():
    """
    This will make sure uncaught exceptions are sent to the root squid logger as error messages.
    """
    logger = get_logger()
    def uncaught_exception_logger(exception_type: Type[BaseException], value: BaseException, tb: TracebackType):
        logger.exception("Uncaught Exception!", exc_info=value)

    register_crash_handler(uncaught_exception_logger, call_existing_too=False)

def get_default_log_directory():
    return platformdirs.user_log_path(_squid_root_logger_name, "cephla")

def add_file_logging(log_filename, replace_existing=False):
    root_logger = get_logger()
    abs_path = os.path.abspath(log_filename)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.handlers.BaseRotatingHandler):
            if handler.baseFilename == abs_path:
                if replace_existing:
                    root_logger.removeHandler(handler)
                else:
                    log.error(f"RotatingFileHandler already exists for {abs_path}, and replace_existing==False!")
                    return False

    log_file_existed = False
    if os.path.isfile(abs_path):
        log_file_existed = True

    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    # For now, don't worry about rollover after a certain size or time.  Just get a new file per call.
    new_handler = logging.handlers.RotatingFileHandler(abs_path, maxBytes=0, backupCount=25)
    new_handler.setLevel(py_logging.DEBUG)

    formatter = py_logging.Formatter(fmt=_baseline_log_format, datefmt=_baseline_log_dateformat)
    new_handler.setFormatter(formatter)

    log.info(f"Adding new file logger writing to file '{new_handler.baseFilename}'")
    root_logger.addHandler(new_handler)

    # We want a new log file every time we start, so force one at startup if the log file already existed.
    if log_file_existed:
        new_handler.doRollover()

    return True