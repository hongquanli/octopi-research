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
    if True:
        app.setStyle('Fusion')
        win = gui.OctopiGUI()
        win.show()
        app.exec_()
    else:
        c=gui.HCSController()
        c.acquire(
            [(1,1)],
            ["Fluorescence 561 nm Ex"],
            "/home/pharmbio/Downloads/testdirfordata",
        ).finished.connect(
            lambda:c.acquire(
                [(2,2)],
                ["Fluorescence 561 nm Ex"],
                "/home/pharmbio/Downloads/testdirfordata",
            ).finished.connect(
                lambda:c.close()
            )
        )
        app.exec_()