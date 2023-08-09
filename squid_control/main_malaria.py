# set QT_API environment variable
import os 
import argparse
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.gui_malaria as gui

parser = argparse.ArgumentParser()
parser.add_argument("--simulation", help="Run the GUI with simulated hardware.", action = 'store_true')
args = parser.parse_args()

if __name__ == "__main__":

    app = QApplication([])
    app.setStyle('Fusion')
    if(args.simulation):
        win = gui.OctopiGUI(is_simulation = True)
    else:
        win = gui.OctopiGUI()
    win.show()
    app.exec_() #sys.exit(app.exec_())
