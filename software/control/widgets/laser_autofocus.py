from qtpy.QtWidgets import QApplication, QFrame, QLabel, QDoubleSpinBox, QGridLayout

from control.core import LaserAutofocusController
from control.gui import *

SET_REFERENCE_BUTTON_TEXT_IDLE="Set as reference plane"
SET_REFERENCE_BUTTON_TEXT_IN_PROGRESS="setting reference plane (in progress)"
INITIALIZE_BUTTON_TEXT_IDLE="Initialize"
INITIALIZE_BUTTON_TEXT_IN_PROGRESS="initializing (in progress)"
MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE="Measure displacement"
MEASURE_DISPLACEMENT_BUTTON_TEXT_IN_PROGRESS="Measure displacement (in progress)"
MOVE_TO_TARGET_BUTTON_TEXT_IDLE="Move to target"
MOVE_TO_TARGET_BUTTON_TEXT_IN_PROGRESS="Move to target (in progress)"

BTN_INITIALIZE_TOOLTIP="after moving into focus, click this. (only needs to be done once after program startup, this does some internal setup)"
BTN_SET_REFERENCE_TOOLTIP="after moving into focus, click this to set the current focus plane. when 'moving to target' after this has been clicked, the target will always be relative to this plane."
BTN_MEASURE_DISPLACEMENT_TOOLTIP="measure distance between current and reference focus plane."
BTN_MOVE_TO_TARGET_TOOLTIP="move to a focus plane with a given distance to the reference plane that was set earlier."

class LaserAutofocusControlWidget(QFrame):
    def __init__(self, laserAutofocusController:LaserAutofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.laserAutofocusController = laserAutofocusController

        self.add_components()

        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.btn_initialize = Button(INITIALIZE_BUTTON_TEXT_IDLE,checkable=False,checked=False,default=False,tooltip=BTN_INITIALIZE_TOOLTIP,on_clicked=self.initialize).widget
        self.btn_set_reference = Button(SET_REFERENCE_BUTTON_TEXT_IDLE,checkable=False,checked=False,default=False,tooltip=BTN_SET_REFERENCE_TOOLTIP,on_clicked=self.set_reference).widget

        self.label_displacement = QLabel()
        self.label_displacement.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.laserAutofocusController.signal_displacement_um.connect(self.label_displacement.setNum)

        self.btn_measure_displacement = Button(MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE,checkable=False,checked=False,default=False,tooltip=BTN_MEASURE_DISPLACEMENT_TOOLTIP,on_clicked=self.measure_displacement).widget

        self.entry_target = SpinBoxDouble(minimum=-100.0,maximum=100.0,step=0.01,num_decimals=2,default=0.0,keyboard_tracking=False).widget
        self.btn_move_to_target = Button(MOVE_TO_TARGET_BUTTON_TEXT_IDLE,checkable=False,checked=False,default=False,tooltip=BTN_MOVE_TO_TARGET_TOOLTIP,on_clicked=self.move_to_target).widget

        self.grid = Grid(
            GridItem(self.btn_initialize,0,0,1,3),
            GridItem(self.btn_set_reference,1,0,1,3),
            [
                QLabel('Displacement (um)'),
                self.label_displacement,
                self.btn_measure_displacement,
            ],
            [
                QLabel('Target (um)'),
                self.entry_target,
                self.btn_move_to_target,
            ],
        ).layout

        self.grid.setRowStretch(self.grid.rowCount(), 1)

        self.setLayout(self.grid)

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
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.

        try:
            self.laserAutofocusController.initialize_auto()
            initialization_failed=False
        except:
            initialization_failed=True

        self.btn_initialize.setDisabled(False)
        self.btn_initialize.setText(INITIALIZE_BUTTON_TEXT_IDLE)
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.

        if initialization_failed:
            print("there was a problem initializing the laser autofocus. is the plate in focus?")
            return

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
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.

        self.laserAutofocusController.set_reference()

        self.btn_set_reference.setDisabled(False)
        self.btn_set_reference.setText(SET_REFERENCE_BUTTON_TEXT_IDLE)
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.

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
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.
        
        self.laserAutofocusController.measure_displacement()

        self.btn_measure_displacement.setDisabled(False)
        self.btn_measure_displacement.setText(MEASURE_DISPLACEMENT_BUTTON_TEXT_IDLE)
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.

    def move_to_target(self,target_um):
        self.btn_move_to_target.setDisabled(True)
        self.btn_move_to_target.setText(MOVE_TO_TARGET_BUTTON_TEXT_IN_PROGRESS)
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.

        self.laserAutofocusController.move_to_target(self.entry_target.value())
        self.laserAutofocusController.measure_displacement()

        self.btn_move_to_target.setDisabled(False)
        self.btn_move_to_target.setText(MOVE_TO_TARGET_BUTTON_TEXT_IDLE)
        QApplication.processEvents() # process GUI events, i.e. actually display the changed text etc.