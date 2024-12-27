# set QT_API environment variable
import logging
import os 
import glob
import argparse
os.environ["QT_API"] = "pyqt5"

import sys

# qt libraries
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# app specific libraries
import control.gui_malaria as gui

from configparser import ConfigParser
from control.widgets import ConfigEditorBackwardsCompatible, ConfigEditorForAcquisitions
from control._def import CACHED_CONFIG_FILE_PATH
import squid.logging

def show_config(cfp, configpath, main_gui):
    config_widget = ConfigEditorBackwardsCompatible(cfp, configpath, main_gui)
    config_widget.exec_()

def show_acq_config(cfm):
    acq_config_widget = ConfigEditorForAcquisitions(cfm)
    acq_config_widget.exec_()


if __name__ == "__main__":
    log = squid.logging.get_logger("main_malaria")

    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation", help="Run the GUI with simulated hardware.", action="store_true")
    parser.add_argument("--verbose", help="Turn on verbose (DEBUG) logging.", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        squid.logging.set_stdout_log_level(logging.DEBUG)

    legacy_config = False
    cf_editor_parser = ConfigParser()
    config_files = glob.glob('.' + '/' + 'configuration*.ini')
    if config_files:
        cf_editor_parser.read(CACHED_CONFIG_FILE_PATH)
    else:
        log.warning('configuration*.ini file not found, defaulting to legacy configuration')
        legacy_config = True
    app = QApplication([])
    app.setStyle('Fusion')
    if args.simulation:
        win = gui.MalariaGUI(is_simulation = True)
    else:
        win = gui.MalariaGUI()
       
    acq_config_action = QAction("Acquisition Settings", win)
    acq_config_action.triggered.connect(lambda : show_acq_config(win.configurationManager))

    file_menu = QMenu("File", win)
    file_menu.addAction(acq_config_action)

    if not legacy_config:
        config_action = QAction("Microscope Settings", win)
        config_action.triggered.connect(lambda : show_config(cf_editor_parser, config_files[0], win))
        file_menu.addAction(config_action)
    
    menu_bar = win.menuBar()
    menu_bar.addMenu(file_menu)
    win.show()
    sys.exit(app.exec_())
