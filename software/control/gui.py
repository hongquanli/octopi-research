from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFrame, QPushButton, QLineEdit, QDoubleSpinBox, \
    QSpinBox, QListWidget, QGridLayout, QCheckBox, QLabel, QAbstractItemView, \
    QComboBox, QHBoxLayout, QVBoxLayout, QMessageBox, QFileDialog, QProgressBar, \
    QDesktopWidget, QWidget, QTableWidget, QSizePolicy, QTableWidgetItem, \
    QApplication, QTabWidget, QStyleOption, QStyle
from qtpy.QtGui import QIcon, QPainter

from typing import Optional, Union, List, Tuple, Callable, Any

import pyqtgraph.dockarea as dock

from control.typechecker import *

def flatten(l:list):
    ret=[]

    for item in l:
        if isinstance(item,list):
            ret.extend(item)
        else:
            ret.append(item)

    return ret

assert [2,3,4,5]==flatten([2,[3,4],5])

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

class FileDialog:
    def __init__(self,
        mode:ClosedSet[str]('save','open'),

        directory:Optional[str]=None,
        caption:Optional[str]=None,
        filter_type:Optional[str]=None,
    ):
        self.window=QFileDialog()
        self.window.setWindowModality(Qt.ApplicationModal)
        self.mode=mode

        self.kwargs={'options':QFileDialog.DontUseNativeDialog}
        if not directory is None:
            self.kwargs['directory']=directory
        if not caption is None:
            self.kwargs['caption']=caption
        if not filter_type is None:
            self.kwargs['filter']=filter_type
            

    def run(self):
        if self.mode=='save':
            return self.window.getSaveFileName(**self.kwargs)[0]
        elif self.mode=='load':
            return self.window.getOpenFileName(**self.kwargs)[0]
        else:
            assert False

class MessageBox:
    def __init__(self,
        title:str,
        mode:ClosedSet[str]('information','critical','warning','question'),

        text:Optional[str]=None,
    ):
        self.window=QMessageBox(title=title,text=text or "")

        self.mode=mode

    def run(self):
        if self.mode=='information':
            self.window.information()
        if self.mode=='critical':
            self.window.critical()
        if self.mode=='warning':
            self.window.warning()
        if self.mode=='question':
            self.window.question()
        else:
            assert False

class BlankWidget(QWidget):
    def __init__(self,
        height:Optional[int]=None,
        width:Optional[int]=None,
        offset_left:Optional[int]=None,
        offset_top:Optional[int]=None,
        background_color:Optional[str]=None,

        children:list=[],

        tooltip:Optional[str]=None,

        **kwargs,
    ):
        QWidget.__init__(self)

        if not height is None and width is not None:
            self.resize(width,height)
        elif int(height is None) + int(width is None) == 1:
            assert False,"height and width must either both or neither be none"
        
        if not offset_left is None:
            self.move(offset_left,offset_top)
        elif int(offset_left is None) + int(offset_top is None) == 1:
            assert False,"height and width must either both or neither be none"
        
        if not background_color is None:
            self.setStyleSheet(f"QWidget {{ background-color: {background_color} ; }}")

        self.children=[]
        self.set_children(children)

        event_handlers={}
        for key,value in kwargs.items():
            assert key[:3]=='on_'

            event_name=key[3:]
            event_handlers[event_name]=value

            if not event_name in {
                'mouseDoubleClickEvent',
                'mouseMoveEvent',
                'mousePressEvent',
                'mouseReleaseEvent',
            }:
                raise ValueError(f"event type '{event_name}' unknown")

        self.event_handlers=event_handlers

    def set_children(self,new_children):
        # orphan old children
        old_children=self.children
        for old_child in old_children:
            old_child.setParent(None)
            old_child.show()

        # adopt new ones
        for child in new_children:
            child.setParent(self)
            child.show()

        # replace orphans
        self.children=new_children
        self.show()

    # this needs to be done for custom QWidgets for some reason (from https://forum.qt.io/topic/100691/custom-qwidget-setstylesheet-not-working-python/2)
    def paintEvent(self, pe):
        o = QStyleOption()
        o.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, o, p, self)

    def mouseDoubleClickEvent(self,event_data):
        if 'mouseDoubleClickEvent' in self.event_handlers:
            event_handlers=self.event_handlers['mouseDoubleClickEvent']
            if isinstance(event_handlers,list):
                for callback in event_handlers:
                    callback(event_data)
            else:
                event_handlers(event_data)
    def mouseMoveEvent(self,event_data):
        if 'mouseMoveEvent' in self.event_handlers:
            event_handlers=self.event_handlers['mouseMoveEvent']
            if isinstance(event_handlers,list):
                for callback in event_handlers:
                    callback(event_data)
            else:
                event_handlers(event_data)
    def mousePressEvent(self,event_data):
        if 'mousePressEvent' in self.event_handlers:
            event_handlers=self.event_handlers['mousePressEvent']
            if isinstance(event_handlers,list):
                for callback in event_handlers:
                    callback(event_data)
            else:
                event_handlers(event_data)
    def mouseReleaseEvent(self,event_data):
        if 'mouseReleaseEvent' in self.event_handlers:
            event_handlers=self.event_handlers['mouseReleaseEvent']
            if isinstance(event_handlers,list):
                for callback in event_handlers:
                    callback(event_data)
            else:
                event_handlers(event_data)