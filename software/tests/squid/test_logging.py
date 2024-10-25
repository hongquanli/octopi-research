import logging
import tempfile

import squid.logging

def test_root_logger():
    root_logger = squid.logging.get_logger()
    assert root_logger.name == squid.logging._squid_root_logger_name

def test_children_loggers():
    child_a = "a"
    child_b = "b"

    child_a_logger = squid.logging.get_logger(child_a)
    child_b_logger = child_a_logger.getChild(child_b)

    assert child_a_logger.name == f"{squid.logging._squid_root_logger_name}.{child_a}"
    assert child_b_logger.name == f"{squid.logging._squid_root_logger_name}.{child_a}.{child_b}"

def test_file_loggers():
    log_file_name = tempfile.mktemp()

    def line_count():
        with open(log_file_name, "r") as fh:
            return len(list(fh))

    def contains(string):
        with open(log_file_name, "r") as fh:
            for l in fh:
                if string in l:
                    return True
        return False

    assert squid.logging.add_file_logging(log_file_name)
    assert not squid.logging.add_file_logging(log_file_name)

    initial_line_count = line_count()
    log = squid.logging.get_logger("log test")
    squid.logging.set_stdout_log_level(logging.DEBUG)

    log.debug("debug msg")
    debug_ling_count = line_count()
    assert debug_ling_count > initial_line_count

    squid.logging.set_stdout_log_level(logging.INFO)

    a_debug_message = "another message but when stdout is at INFO"
    log.debug(a_debug_message)
    assert line_count() > debug_ling_count
    assert contains(a_debug_message)
