from qtpy.QtWidgets import QFrame, QPushButton, QLabel, QDoubleSpinBox, QGridLayout

from control.core import LaserAutofocusController

class LaserAutofocusControlWidget(QFrame):
    def __init__(self, laserAutofocusController:LaserAutofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.laserAutofocusController = laserAutofocusController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.btn_initialize = QPushButton("Initialize")
        self.btn_initialize.setCheckable(False)
        self.btn_initialize.setChecked(False)
        self.btn_initialize.setDefault(False)

        self.btn_set_reference = QPushButton("Set as reference plane")
        self.btn_set_reference.setCheckable(False)
        self.btn_set_reference.setChecked(False)
        self.btn_set_reference.setDefault(False)

        self.label_displacement = QLabel()
        self.label_displacement.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        self.btn_measure_displacement = QPushButton("Measure displacement")
        self.btn_measure_displacement.setCheckable(False)
        self.btn_measure_displacement.setChecked(False)
        self.btn_measure_displacement.setDefault(False)

        self.entry_target = QDoubleSpinBox()
        self.entry_target.setMinimum(-100)
        self.entry_target.setMaximum(100)
        self.entry_target.setSingleStep(0.01)
        self.entry_target.setDecimals(2)
        self.entry_target.setValue(0)
        self.entry_target.setKeyboardTracking(False)

        self.btn_move_to_target = QPushButton("Move to target")
        self.btn_move_to_target.setCheckable(False)
        self.btn_move_to_target.setChecked(False)
        self.btn_move_to_target.setDefault(False)

        self.grid = QGridLayout()
        self.grid.addWidget(self.btn_initialize,0,0,1,3)
        self.grid.addWidget(self.btn_set_reference,1,0,1,3)
        self.grid.addWidget(QLabel('Displacement (um)'),2,0)
        self.grid.addWidget(self.label_displacement,2,1)
        self.grid.addWidget(self.btn_measure_displacement,2,2)
        self.grid.addWidget(QLabel('Target (um)'),3,0)
        self.grid.addWidget(self.entry_target,3,1)
        self.grid.addWidget(self.btn_move_to_target,3,2)
        self.grid.setRowStretch(self.grid.rowCount(), 1)

        self.setLayout(self.grid)

        # make connections
        self.btn_initialize.clicked.connect(self.laserAutofocusController.initialize_auto)
        self.btn_set_reference.clicked.connect(self.laserAutofocusController.set_reference)
        self.btn_measure_displacement.clicked.connect(self.laserAutofocusController.measure_displacement)
        self.btn_move_to_target.clicked.connect(self.move_to_target)
        self.laserAutofocusController.signal_displacement_um.connect(self.label_displacement.setNum)

    def move_to_target(self,target_um):
        self.laserAutofocusController.move_to_target(self.entry_target.value())