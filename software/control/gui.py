from qtpy.QtWidgets import QFrame, QPushButton, QLineEdit, QDoubleSpinBox, \
    QSpinBox, QListWidget, QGridLayout, QCheckBox, QLabel, QAbstractItemView, \
    QComboBox, QHBoxLayout, QVBoxLayout, QMessageBox, QFileDialog, QProgressBar, \
    QDesktopWidget, QWidget, QTableWidget, QSizePolicy, QTableWidgetItem, \
    QApplication, QTabWidget
from qtpy.QtGui import QIcon

from typing import Optional, Union, List, Tuple, Callable, Any

import pyqtgraph.dockarea as dock

class ManagedObject:
    def __init__(self):
        self.value=None
    def __eq__(self,other):
        if self.value is None:
            self.value=other
            return other
        else:
            return self.value

class ObjectManager:
    def __init__(self):
        self.managed_objects={}
    def __getattr__(self,key):
        if key in self.managed_objects:
            managed_object=self.managed_objects[key]
        else:
            managed_object=ManagedObject()
            self.managed_objects[key]=managed_object

        if managed_object.value is None:
            return managed_object
        else:
            return managed_object.value

def as_widget(layout)->QWidget:
    w=QWidget()
    w.setLayout(layout)
    return w

class HasLayout():
    pass
class HasWidget():
    pass

def try_add_member(adder,addee,*args,**kwargs):
    if isinstance(addee,HasLayout):
        adder.addLayout(addee.layout,*args,**kwargs)
    elif isinstance(addee,HasWidget):
        adder.addWidget(addee.widget,*args,**kwargs)
    else:
        try:
            adder.addWidget(addee,*args,**kwargs)
        except TypeError:
            adder.addLayout(addee,*args,**kwargs)

class GridItem:
    def __init__(self,widget,a,b,c,d):
        self.widget=widget
        self.a=a
        self.b=b
        self.c=c
        self.d=d

class Grid(HasLayout,HasWidget):
    def __init__(self,*args,**kwargs):
        self.layout=QGridLayout()
        for outer_index,outer_arg in enumerate(args):
            if isinstance(outer_arg,GridItem):
                self.layout.addWidget(outer_arg.widget,outer_arg.a,outer_arg.b,outer_arg.c,outer_arg.d)
                continue

            try:
                _discard=outer_arg.__iter__
                can_be_iterated_over=True
            except:
                can_be_iterated_over=False

            if can_be_iterated_over:
                for inner_index,inner_arg in enumerate(outer_arg):
                    if not inner_arg is None: # inner args can be NONE to allow for some easy padding between elements
                        try_add_member(self.layout,inner_arg,outer_index,inner_index)
            else:
                try_add_member(self.layout,outer_arg,outer_index,0)

    @property
    def widget(self):
        return as_widget(self.layout)

class HBox(HasLayout,HasWidget):
    def __init__(self,*args):
        self.layout=QHBoxLayout()
        for arg in args:
            try_add_member(self.layout,arg)

    @property
    def widget(self):
        return as_widget(self.layout)

class VBox(HasLayout,HasWidget):
    def __init__(self,*args):
        self.layout=QVBoxLayout()
        for arg in args:
            try_add_member(self.layout,arg)

    @property
    def widget(self):
        return as_widget(self.layout)

class SpinBoxDouble(HasWidget):
    def __init__(self,
        minimum:Optional[float]=None,
        maximum:Optional[float]=None,
        default:Optional[float]=None,
        step:Optional[float]=None,
        num_decimals=None,
        keyboard_tracking=None,
        tooltip:Optional[str]=None,

        **kwargs,
    ):
        self.widget=QDoubleSpinBox()

        if not minimum is None:
            self.widget.setMinimum(minimum) 
        if not maximum is None:
            self.widget.setMaximum(maximum)
        if not step is None:
            self.widget.setSingleStep(step)
        if not default is None:
            self.widget.setValue(default)
        if not num_decimals is None:
            self.widget.setDecimals(num_decimals)
        if not keyboard_tracking is None:
            self.widget.setKeyboardTracking(keyboard_tracking)
        if not tooltip is None:
            self.widget.setToolTip(tooltip)

        for key,value in kwargs.items():
            if key.startswith("on_"):
                signal_name=key[3:]
                assert len(signal_name)>0

                if isinstance(value,list):
                    for callback in value:
                        getattr(self.widget,signal_name).connect(callback)
                else:
                    getattr(self.widget,signal_name).connect(value)

class SpinBoxInteger(HasWidget):
    def __init__(self,
        minimum:Optional[int]=None,
        maximum:Optional[int]=None,
        default:Optional[int]=None,
        step:Optional[int]=None,
        num_decimals=None,
        keyboard_tracking=None,
        tooltip:Optional[str]=None,

        **kwargs,
    ):
        self.widget=QSpinBox()

        if not minimum is None:
            self.widget.setMinimum(minimum) 
        if not maximum is None:
            self.widget.setMaximum(maximum)
        if not step is None:
            self.widget.setSingleStep(step)
        if not default is None:
            self.widget.setValue(default)
        if not num_decimals is None:
            self.widget.setDecimals(num_decimals)
        if not keyboard_tracking is None:
            self.widget.setKeyboardTracking(keyboard_tracking)
        if not tooltip is None:
            self.widget.setToolTip(tooltip)

        for key,value in kwargs.items():
            if key.startswith("on_"):
                signal_name=key[3:]
                assert len(signal_name)>0

                if isinstance(value,list):
                    for callback in value:
                        getattr(self.widget,signal_name).connect(callback)
                else:
                    getattr(self.widget,signal_name).connect(value)

class Label(HasWidget):
    def __init__(self,
        text:str,
        tooltip:Optional[str]=None,
        text_color:Optional[str]=None,
        background_color:Optional[str]=None
    ):
        self.widget=QLabel(text)
        if not tooltip is None:
            self.widget.setToolTip(tooltip)
        stylesheet=""
        if not text_color is None:
            stylesheet+=f"color : {text_color} ; "
        if not background_color is None:
            stylesheet+=f"background-color : {background_color} ; "
        if len(stylesheet)>0:
            final_stylesheet=f"QLabel {{ { stylesheet } }}"
            self.widget.setStyleSheet(final_stylesheet)


class Button(HasWidget):
    def __init__(self,
        text:str,
        default:Optional[bool]=None,
        enabled:Optional[bool]=None,
        checkable:Optional[bool]=None,
        checked:Optional[bool]=None,
        tooltip:Optional[str]=None,

        **kwargs,
    ):
        self.widget=QPushButton(text)
        if not default is None:
            self.widget.setDefault(default)
        if not enabled is None:
            self.widget.setEnabled(enabled)
        if not checkable is None:
            self.widget.setCheckable(checkable)
        if not checked is None:
            self.widget.setChecked(checked)
        if not tooltip is None:
            self.widget.setToolTip(tooltip)

        for key,value in kwargs.items():
            if key.startswith("on_"):
                signal_name=key[3:]
                assert len(signal_name)>0

                if isinstance(value,list):
                    for callback in value:
                        getattr(self.widget,signal_name).connect(callback)
                else:
                    getattr(self.widget,signal_name).connect(value)

class Tab(HasWidget):
    def __init__(self,widget,title:Optional[str]=None):
        assert isinstance(widget,QWidget)
        self.widget=widget
        self.title=title

class TabBar(HasWidget):
    def __init__(self,*args):
        self.widget=QTabWidget()
        for tab in args:
            if isinstance(tab,Tab):
                self.widget.addTab(tab.widget,tab.title)
            else:
                assert isinstance(tab,QWidget)
                self.widget.addTab(tab)


class Dock(HasWidget):
    def __init__(self,widget:QWidget,title:str,minimize_height:bool=False,fixed_width:Optional[Any]=None,stretch_x:Optional[int]=100,stretch_y:Optional[int]=100):
        self.widget = dock.Dock(title, autoOrientation = False)
        self.widget.showTitleBar()
        self.widget.addWidget(widget)
        self.widget.setStretch(x=stretch_x,y=stretch_y)

        if not fixed_width is None:
            self.widget.setFixedWidth(fixed_width)

        if minimize_height:
            self.widget.setFixedHeight(self.widget.minimumSizeHint().height())

class DockArea(HasWidget):
    def __init__(self,*args):
        self.widget=dock.DockArea()
        for dock in args:
            self.widget.addDock(temp_dock)

        if minimize_height:
            self.widget.setFixedHeight(self.widget.minimumSizeHint().height())

class Dropdown(HasWidget):
    def __init__(self,
        items:List[Any],
        current_index:int,
        tooltip:Optional[str]=None,

        **kwargs,
    ):
        self.widget=QComboBox()
        self.widget.addItems(items)
        self.widget.setCurrentIndex(current_index)

        if not tooltip is None:
            self.widget.setToolTip(tooltip)

        for key,value in kwargs.items():
            if key.startswith("on_"):
                signal_name=key[3:]
                assert len(signal_name)>0

                if isinstance(value,list):
                    for callback in value:
                        getattr(self.widget,signal_name).connect(callback)
                else:
                    getattr(self.widget,signal_name).connect(value)
