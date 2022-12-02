# qt libraries
from qtpy.QtWidgets import QFrame, QDoubleSpinBox, QSpinBox, QGridLayout, QLabel

from control._def import *
from control.gui import *

from typing import Optional, Union, List, Tuple

DZ_TOOLTIP="use autofocus by taking z-stack of images (NZ images, with dz um distance between images), then \ncalculating a focus metric and choosing the image plane with the best metric.\n\nthe images are taken in the channel that is currently selected for live view (led+micro will be turned on if they are off)\n\nthis will take a few seconds"

DEFAULT_NZ=10
DEFAULT_DELTAZ=1.524

class AutoFocusWidget(QFrame):
    def __init__(self, autofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autofocusController = autofocusController

        self.add_components()

        self.autofocusController.autofocusFinished.connect(self.autofocus_is_finished)
        self.autofocusController.set_N(DEFAULT_NZ)
        self.set_deltaZ(DEFAULT_DELTAZ)

        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.entry_delta = SpinBoxDouble(minimum=0.0,maximum=20.0,step=0.2,num_decimals=3,default=DEFAULT_DELTAZ,keyboard_tracking=False,on_valueChanged=self.set_deltaZ).widget

        self.entry_N = SpinBoxInteger(minimum=3,maximum=20,step=1,default=DEFAULT_NZ,keyboard_tracking=False,on_valueChanged=self.autofocusController.set_N).widget

        self.btn_autofocus = Button('Autofocus',default=False,checkable=True,checked=False,tooltip=DZ_TOOLTIP,on_clicked=self.autofocusController.autofocus).widget

        # layout
        qtlabel_dz=Label('delta Z (um)',tooltip=DZ_TOOLTIP).widget
        qtlabel_Nz=Label('N Z planes',tooltip=DZ_TOOLTIP).widget

        grid_line0 = Grid([ qtlabel_dz, self.entry_delta, qtlabel_Nz, self.entry_N, self.btn_autofocus ]).layout
        
        self.grid = Grid(
            [grid_line0]
        ).layout
        self.setLayout(self.grid)

    def set_deltaZ(self,value):
        mm_per_ustep = MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.autofocusController.navigationController.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_delta.setValue(deltaZ)
        self.autofocusController.set_deltaZ(deltaZ)

    def autofocus_is_finished(self):
        self.btn_autofocus.setChecked(False)
