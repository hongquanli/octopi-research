# set QT_API environment variable
import os 
import sys
import argparse
os.environ["QT_API"] = "pyqt5"

# qt libraries
from qtpy.QtWidgets import *

# app specific libraries
import control.gui as gui

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation", help="Run the GUI with simulated hardware.", action="store_true")
    parser.add_argument("--verbose", help="Turn on verbose (DEBUG) level logging.", action="store_true")
    args = parser.parse_args()

    app = QApplication([])
    app.setStyle('Fusion')
    if args.simulation:
        win = gui.OctopiGUI(is_simulation = True)
    else:
        win = gui.OctopiGUI()
    win.show()
    sys.exit(app.exec_())
