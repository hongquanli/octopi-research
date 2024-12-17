# set QT_API environment variable
import argparse
import glob
import logging
import os
os.environ["QT_API"] = "pyqt5"
import signal
import sys

# qt libraries
from qtpy.QtWidgets import *
from qtpy.QtGui import *

import squid.logging
squid.logging.setup_uncaught_exception_logging()

# app specific libraries
import control.gui_hcs as gui
from configparser import ConfigParser
from control.widgets import ConfigEditorBackwardsCompatible, ConfigEditorForAcquisitions
from control._def import CACHED_CONFIG_FILE_PATH
from control.console import ConsoleThread


def show_config(cfp, configpath, main_gui):
    config_widget = ConfigEditorBackwardsCompatible(cfp, configpath, main_gui)
    config_widget.exec_()


def show_acq_config(cfm):
    acq_config_widget = ConfigEditorForAcquisitions(cfm)
    acq_config_widget.exec_()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation", help="Run the GUI with simulated hardware.", action='store_true')
    parser.add_argument("--live-only", help="Run the GUI only the live viewer.", action='store_true')
    parser.add_argument("--verbose", help="Turn on verbose logging (DEBUG level)", action="store_true")
    args = parser.parse_args()

    log = squid.logging.get_logger("main_hcs")

    if args.verbose:
        log.info("Turning on debug logging.")
        squid.logging.set_stdout_log_level(logging.DEBUG)

    if not squid.logging.add_file_logging(f"{squid.logging.get_default_log_directory()}/main_hcs.log"):
        log.error("Couldn't setup logging to file!")
        sys.exit(1)

    legacy_config = False
    cf_editor_parser = ConfigParser()
    config_files = glob.glob('.' + '/' + 'configuration*.ini')
    if config_files:
        cf_editor_parser.read(CACHED_CONFIG_FILE_PATH)
    else:
        log.error('configuration*.ini file not found, defaulting to legacy configuration')
        legacy_config = True
    app = QApplication([])
    app.setStyle('Fusion')
    # This allows shutdown via ctrl+C even after the gui has popped up.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    win = gui.HighContentScreeningGui(is_simulation=args.simulation, live_only_mode=args.live_only)

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

    console_locals = {
        'microscope': win.microscope
    }

    console_thread = ConsoleThread(console_locals)
    console_thread.start()

    sys.exit(app.exec_())
