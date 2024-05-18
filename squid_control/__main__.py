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
import squid_control.control.gui_hcs as gui

from squid_control.control.widgets import (
    ConfigEditorBackwardsCompatible,
    ConfigEditorForAcquisitions,
)

from squid_control.control.config import load_config

import glob
import argparse
from configparser import ConfigParser

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def show_config(cfp, configpath, main_gui):
    config_widget = ConfigEditorBackwardsCompatible(cfp, configpath, main_gui)
    config_widget.exec_()


def show_acq_config(cfm):
    acq_config_widget = ConfigEditorForAcquisitions(cfm)
    acq_config_widget.exec_()


def main():
    # add argparse options for loading configuration files
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--simulation", help="Run the GUI with simulated hardware.", action="store_true"
    )
    parser.add_argument("--config", help="Load a configuration file.", type=str)
    parser.add_argument("--multipoint-function", help="Load a multipoint function. format: ./custom_script.py:function_name", type=str)
    args = parser.parse_args()
    assert args.config is not None, "Please provide a configuration file."

    load_config(args.config, args.multipoint_function)


    # export QT_QPA_PLATFORM_PLUGIN_PATH=/home/weiouyang/miniconda3/envs/squid-control/lib/python3.10/site-packages/PyQt5/Qt/plugins
    # use sys.executable to get the path to the python interpreter, python version, and lib path
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(
        os.path.dirname(sys.executable),
        "lib",
        "python" + sys.version[:3],
        "site-packages",
        "PyQt5",
        "Qt",
        "plugins",
    )
    app = QApplication([])
    app.setStyle("Fusion")
    if args.simulation:
        win = gui.OctopiGUI(is_simulation=True)
    else:
        win = gui.OctopiGUI()

    acq_config_action = QAction("Acquisition Settings", win)
    acq_config_action.triggered.connect(
        lambda: show_acq_config(win.configurationManager)
    )

    file_menu = QMenu("File", win)
    file_menu.addAction(acq_config_action)


    config_action = QAction("Microscope Settings", win)
    cf_editor_parser = ConfigParser()
    cf_editor_parser.read(args.config)
    config_action.triggered.connect(
        lambda: show_config(cf_editor_parser, args.config, win)
    )
    file_menu.addAction(config_action)

    try:
        csw = win.cswWindow
        if csw is not None:
            csw_action = QAction("Camera Settings", win)
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


if __name__ == "__main__":
    main()
