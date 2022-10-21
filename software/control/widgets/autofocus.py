# qt libraries
from qtpy.QtWidgets import QFrame, QDoubleSpinBox, QSpinBox, QPushButton, QGridLayout, QLabel

from control._def import *

from typing import Optional, Union, List, Tuple

class AutoFocusWidget(QFrame):
    def __init__(self, autofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autofocusController = autofocusController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.entry_delta = QDoubleSpinBox()
        self.entry_delta.setMinimum(0) 
        self.entry_delta.setMaximum(20) 
        self.entry_delta.setSingleStep(0.2)
        self.entry_delta.setDecimals(3)
        self.entry_delta.setValue(1.524)
        self.entry_delta.setKeyboardTracking(False)
        self.autofocusController.set_deltaZ(1.524)

        self.entry_N = QSpinBox()
        self.entry_N.setMinimum(3) 
        self.entry_N.setMaximum(20) 
        self.entry_N.setSingleStep(1)
        self.entry_N.setValue(10)
        self.entry_N.setKeyboardTracking(False)
        self.autofocusController.set_N(10)

        self.btn_autofocus = QPushButton('Autofocus')
        self.btn_autofocus.setDefault(False)
        self.btn_autofocus.setCheckable(True)
        self.btn_autofocus.setChecked(False)

        # layout
        grid_line0 = QGridLayout()
        dz_tooltip="use autofocus by taking z-stack of images (NZ images, with dz um distance between images), then \ncalculating a focus metric and choosing the image plane with the best metric.\n\nthe images are taken in the channel that is currently selected for live view (led+micro will be turned on if they are off)\n\nthis will take a few seconds"
        self.btn_autofocus.setToolTip(dz_tooltip)
        qtlabel_dz=QLabel('delta Z (um)')
        qtlabel_dz.setToolTip(dz_tooltip)
        grid_line0.addWidget(qtlabel_dz, 0,0)
        grid_line0.addWidget(self.entry_delta, 0,1)
        qtlabel_Nz=QLabel('N Z planes')
        qtlabel_Nz.setToolTip(dz_tooltip)
        grid_line0.addWidget(qtlabel_Nz, 0,2)
        grid_line0.addWidget(self.entry_N, 0,3)
        grid_line0.addWidget(self.btn_autofocus, 0,4)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.setLayout(self.grid)
        
        # connections
        self.btn_autofocus.clicked.connect(self.autofocusController.autofocus)
        self.entry_delta.valueChanged.connect(self.set_deltaZ)
        self.entry_N.valueChanged.connect(self.autofocusController.set_N)
        self.autofocusController.autofocusFinished.connect(self.autofocus_is_finished)

    def set_deltaZ(self,value):
        mm_per_ustep = SCREW_PITCH_Z_MM/(self.autofocusController.navigationController.z_microstepping*FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_delta.setValue(deltaZ)
        self.autofocusController.set_deltaZ(deltaZ)

    def autofocus_is_finished(self):
        self.btn_autofocus.setChecked(False)
