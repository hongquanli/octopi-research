from enum import Enum


class TriggerModeSetting(Enum):
    SOFTWARE = "Software Trigger"
    HARDWARE = "Hardware Trigger"
    CONTINUOUS = "Continuous Acqusition"


def get_camera(camera_type):
    if camera_type == "Toupcam":
        try:
            import squid_control.control.camera.camera_toupcam as camera
        except:
            print("Problem importing Toupcam, defaulting to default camera")
            import squid_control.control.camera.camera_default as camera
        try:
            import squid_control.control.camera.camera_toupcam as camera_fc
        except:
            print("Problem importing Toupcam for focus, defaulting to default camera")
            import squid_control.control.camera as camera_fc
    elif camera_type == "FLIR":
        try:
            import squid_control.control.camera.camera_flir as camera
        except:
            print("Problem importing FLIR camera, defaulting to default camera")
            import squid_control.control.camera.camera_default as camera
        try:
            import squid_control.control.camera.camera_flir as camera_fc
        except:
            print(
                "Problem importing FLIR camera for focus, defaulting to default camera"
            )
            import squid_control.control.camera as camera_fc
    else:
        import squid_control.control.camera.camera_default as camera

        camera_fc = camera
    return camera, camera_fc
