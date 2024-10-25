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