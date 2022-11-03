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
    else:
        c=gui.HCSController()
        c.acquire(
            well_list=[(1,1)], # (0,0) is A1
            channels=["Fluorescence 561 nm Ex"],
            experiment_id="/home/pharmbio/Downloads/testdirfordata",
            # grid_data
            # af_channel
            # plate_type
        ).finished.connect(
            lambda:c.acquire(
                [(2,2)],
                ["Fluorescence 561 nm Ex"],
                "/home/pharmbio/Downloads/testdirfordata",
            ).finished.connect(
                lambda:c.close()
            )
        )

    sys.exit(app.exec())