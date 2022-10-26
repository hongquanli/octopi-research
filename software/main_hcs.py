# set QT_API environment variable
import os
os.environ["QT_API"] = "pyqt5"
import sys

# qt libraries
from qtpy.QtWidgets import QApplication

# app specific libraries
import control.gui_hcs as gui

if __name__ == "__main__":
    app = QApplication([])
    app.setStyle('Fusion')
    win = gui.OctopiGUI()
    win.show()
    app.exec_()
