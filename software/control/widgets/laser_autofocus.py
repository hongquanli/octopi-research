from qtpy.QtWidgets import QFrame, QPushButton, QLabel, QDoubleSpinBox, QGridLayout

from control.core import LaserAutofocusController

SET_REFERENCE_BUTTON_TEXT_IDLE="Set as reference plane"
SET_REFERENCE_BUTTON_TEXT_IN_PROGRESS="setting reference plane (in progress)"
INITIALIZE_BUTTON_TEXT_IDLE="Initialize"
INITIALIZE_BUTTON_TEXT_IN_PROGRESS="initializing (in progress)"
MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE="Measure displacement"
MEASURE_DISPLACEMENT_BUTTON_TEXT_IN_PROGRESS="Measure displacement (in progress)"
MOVE_TO_TARGET_BUTTON_TEXT_IDLE="Move to target"
MOVE_TO_TARGET_BUTTON_TEXT_IN_PROGRESS="Move to target (in progress)"

class LaserAutofocusControlWidget(QFrame):
    def __init__(self, laserAutofocusController:LaserAutofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.laserAutofocusController = laserAutofocusController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.btn_initialize = QPushButton(INITIALIZE_BUTTON_TEXT_IDLE)
        self.btn_initialize.setCheckable(False)
        self.btn_initialize.setChecked(False)
        self.btn_initialize.setDefault(False)
        self.btn_initialize.setToolTip("after moving into focus, click this. (only needs to be done once after program startup, this does some internal setup)")

        self.btn_set_reference = QPushButton(SET_REFERENCE_BUTTON_TEXT_IDLE)
        self.btn_set_reference.setCheckable(False)
        self.btn_set_reference.setChecked(False)
        self.btn_set_reference.setDefault(False)
        self.btn_set_reference.setToolTip("after moving into focus, click this to set the current focus plane. when 'moving to target' after this has been clicked, the target will always be relative to this plane.")

        self.label_displacement = QLabel()
        self.label_displacement.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        self.btn_measure_displacement = QPushButton(MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE)
        self.btn_measure_displacement.setCheckable(False)
        self.btn_measure_displacement.setChecked(False)
        self.btn_measure_displacement.setDefault(False)
        self.btn_measure_displacement.setToolTip("measure distance between current and reference focus plane.")

        self.entry_target = QDoubleSpinBox()
        self.entry_target.setMinimum(-100)
        self.entry_target.setMaximum(100)
        self.entry_target.setSingleStep(0.01)
        self.entry_target.setDecimals(2)
        self.entry_target.setValue(0)
        self.entry_target.setKeyboardTracking(False)

        self.btn_move_to_target = QPushButton(MOVE_TO_TARGET_BUTTON_TEXT_IDLE)
        self.btn_move_to_target.setCheckable(False)
        self.btn_move_to_target.setChecked(False)
        self.btn_move_to_target.setDefault(False)
        self.btn_move_to_target.setToolTip("move to a focus plane with a given distance to the reference plane that was set earlier.")

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
        self.btn_initialize.clicked.connect(self.initialize)
        self.btn_set_reference.clicked.connect(self.set_reference)
        self.btn_measure_displacement.clicked.connect(self.measure_displacement)
        self.btn_move_to_target.clicked.connect(self.move_to_target)
        self.laserAutofocusController.signal_displacement_um.connect(self.label_displacement.setNum)

        self.has_been_initialized=False
        self.reference_was_set=False

        # with no initialization and no reference, not allowed to do anything
        self.btn_set_reference.setDisabled(True)
        self.btn_set_reference.setText(SET_REFERENCE_BUTTON_TEXT_IDLE+" (not initialized)")
        self.btn_measure_displacement.setDisabled(True)
        self.btn_measure_displacement.setText(MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE+" (not initialized)")
        self.btn_move_to_target.setDisabled(True)
        self.btn_move_to_target.setText(MOVE_TO_TARGET_BUTTON_TEXT_IDLE+" (not initialized)")
        self.entry_target.setDisabled(True)

    def initialize(self):
        """ automatically initialize laser autofocus """

        self.btn_initialize.setDisabled(True)
        self.btn_initialize.setText(INITIALIZE_BUTTON_TEXT_IN_PROGRESS)

        self.laserAutofocusController.initialize_auto()

        self.btn_initialize.setDisabled(False)
        self.btn_initialize.setText(INITIALIZE_BUTTON_TEXT_IDLE)

        # allow setting of a reference after initialization
        if not self.has_been_initialized:
            self.has_been_initialized=True

            self.btn_set_reference.setDisabled(False)
            self.btn_set_reference.setText(SET_REFERENCE_BUTTON_TEXT_IDLE)

            self.btn_measure_displacement.setText(MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE+" (no reference set)")
            self.btn_move_to_target.setText(MOVE_TO_TARGET_BUTTON_TEXT_IDLE+" (no reference set)")

    def set_reference(self):
        self.btn_set_reference.setDisabled(True)
        self.btn_set_reference.setText(SET_REFERENCE_BUTTON_TEXT_IN_PROGRESS)

        self.laserAutofocusController.set_reference()

        self.btn_set_reference.setDisabled(False)
        self.btn_set_reference.setText(SET_REFERENCE_BUTTON_TEXT_IDLE)

        # allow actual use of laser AF now
        if not self.reference_was_set:
            self.reference_was_set=True

            self.btn_measure_displacement.setDisabled(False)
            self.btn_measure_displacement.setText(MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE)

            self.btn_move_to_target.setDisabled(False)
            self.btn_move_to_target.setText(MOVE_TO_TARGET_BUTTON_TEXT_IDLE)
            self.entry_target.setDisabled(False)

    def measure_displacement(self):
        self.btn_measure_displacement.setDisabled(True)
        self.btn_measure_displacement.setText(MEASURE_DISPLACEMENT_BUTTON_TEXT_IN_PROGRESS)
        
        self.laserAutofocusController.measure_displacement()

        self.btn_measure_displacement.setDisabled(False)
        self.btn_measure_displacement.setText(MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE)

    def move_to_target(self,target_um):
        self.btn_move_to_target.setDisabled(True)
        self.btn_move_to_target.setText(MOVE_TO_TARGET_BUTTON_TEXT_IN_PROGRESS)

        self.laserAutofocusController.move_to_target(self.entry_target.value())
        self.laserAutofocusController.measure_displacement()

        self.btn_move_to_target.setDisabled(False)
        self.btn_move_to_target.setText(MOVE_TO_TARGET_BUTTON_TEXT_IDLE)