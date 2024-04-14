# set QT_API environment variable
import os 
import sys
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.gui_PDAF_calibration as gui

if __name__ == "__main__":

    app = QApplication([])
    win = gui.OctopiGUI(is_simulation=True)
    win.show()
    sys.exit(app.exec_())
