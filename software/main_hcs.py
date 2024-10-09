# set QT_API environment variable
import os
import glob
import argparse
os.environ["QT_API"] = "pyqt5"
import qtpy

import sys

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.gui_hcs as gui

from configparser import ConfigParser
from control.widgets import ConfigEditorBackwardsCompatible, ConfigEditorForAcquisitions

from control._def import CACHED_CONFIG_FILE_PATH

import glob

parser = argparse.ArgumentParser()
parser.add_argument("--simulation", help="Run the GUI with simulated hardware.", action = 'store_true')
parser.add_argument("--performance", help="Run the GUI with minimal viewers.", action = 'store_true')
args = parser.parse_args()

def show_config(cfp, configpath, main_gui):
    config_widget = ConfigEditorBackwardsCompatible(cfp, configpath, main_gui)
    config_widget.exec_()

def show_acq_config(cfm):
    acq_config_widget = ConfigEditorForAcquisitions(cfm)
    acq_config_widget.exec_()

if __name__ == "__main__":
    legacy_config = False
    cf_editor_parser = ConfigParser()
    config_files = glob.glob('.' + '/' + 'configuration*.ini')
    if config_files:
        cf_editor_parser.read(CACHED_CONFIG_FILE_PATH)
    else:
        print('configuration*.ini file not found, defaulting to legacy configuration')
        legacy_config = True
    app = QApplication([])
    app.setStyle('Fusion')

    win = gui.OctopiGUI(is_simulation=args.simulation, performance_mode=args.performance)

    acq_config_action = QAction("Acquisition Settings", win)
    acq_config_action.triggered.connect(lambda : show_acq_config(win.configurationManager))

    file_menu = QMenu("File", win)
    file_menu.addAction(acq_config_action)

    if not legacy_config:
        config_action = QAction("Microscope Settings", win)
        config_action.triggered.connect(lambda : show_config(cf_editor_parser, config_files[0], win))
        file_menu.addAction(config_action)

    try:
        csw = win.cswWindow
        if csw is not None:
            csw_action = QAction("Camera Settings",win)
            csw_action.triggered.connect(csw.show)
            file_menu.addAction(csw_action)
    except AttributeError:
        pass

    try:
        csw_fc = win.cswfcWindow
        if csw_fc is not None:
            csw_fc_action = QAction("Camera Settings (Focus Camera)", win)
            csw_fc_action.triggered.connect(csw_fc.show)
            file_menu.addAction(csw_fc_action)
    except AttributeError:
        pass

    menu_bar = win.menuBar()
    menu_bar.addMenu(file_menu)
    win.show()
    sys.exit(app.exec_())
