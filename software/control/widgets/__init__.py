# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"

from qtpy.QtWidgets import QWidget
import pyqtgraph.dockarea as dock

from .autofocus import AutoFocusWidget
from .dac_control import DACControWidget
from .live_control import LiveControlWidget
from .multi_point import MultiPointWidget
from .navigation import NavigationWidget, NavigationViewer
from .recording import RecordingWidget
from .well_selection import WellSelectionWidget
from .image_display import ImageDisplay, ImageDisplayWindow, ImageArrayDisplayWindow
from .laser_autofocus import LaserAutofocusControlWidget

def as_widget(layout)->QWidget:
    w=QWidget()
    w.setLayout(layout)
    return w

def as_dock(widget:QWidget,title:str,minimize_height:bool=False):
    temp_dock = dock.Dock(title, autoOrientation = False)
    temp_dock.showTitleBar()
    temp_dock.addWidget(widget)
    temp_dock.setStretch(x=100,y=100)

    ret = dock.DockArea()
    ret.addDock(temp_dock)

    if minimize_height:
        ret.setFixedHeight(ret.minimumSizeHint().height())

    return ret