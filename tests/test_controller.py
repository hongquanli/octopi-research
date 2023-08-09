from squid_control.control.core import LiveController


def test_controller():
    """Test that the controller can be instantiated."""
    controller = LiveController()
    assert controller
