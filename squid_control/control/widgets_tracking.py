# set QT_API environment variable
import os

import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

from squid_control.control.config import CONFIG


class TrackingControllerWidget(QFrame):
    def __init__(
        self, multipointController, navigationController, main=None, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.multipointController = multipointController
        self.navigationController = navigationController
        self.base_path_is_set = False
        # self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
