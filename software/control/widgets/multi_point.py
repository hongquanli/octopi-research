# qt libraries
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFrame, QPushButton, QLineEdit, QDoubleSpinBox, QSpinBox, QListWidget, QGridLayout, QCheckBox, QLabel, QAbstractItemView, QComboBox, QHBoxLayout, QMessageBox, QFileDialog, QProgressBar, QDesktopWidget
from qtpy.QtGui import QIcon

from control._def import *

from typing import Optional, Union, List, Tuple, Callable

from control.core import MultiPointController, ConfigurationManager
from control.typechecker import TypecheckFunction

class MultiPointWidget(QFrame):
    def __init__(self,
        multipointController:MultiPointController,
        configurationManager:ConfigurationManager,
        start_experiment:Callable[[str,List[str]],None],
        abort_experiment:Callable[[],None],
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        
        self.multipointController = multipointController
        self.configurationManager = configurationManager
        self.start_experiment=start_experiment
        self.abort_experiment=abort_experiment

        self.base_path_is_set = False

        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    @TypecheckFunction
    def add_components(self):

        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')

        self.lineEdit_savingDir.setText(MACHINE_DISPLAY_CONFIG.DEFAULT_SAVING_PATH)
        self.multipointController.set_base_path(MACHINE_DISPLAY_CONFIG.DEFAULT_SAVING_PATH)
        self.base_path_is_set = True

        self.lineEdit_experimentID = QLineEdit()

        self.entry_deltaX = QDoubleSpinBox()
        self.entry_deltaX.setMinimum(0) 
        self.entry_deltaX.setMaximum(5) 
        self.entry_deltaX.setSingleStep(0.1)
        self.entry_deltaX.setValue(Acquisition.DEFAULT_DX_MM)
        self.entry_deltaX.setDecimals(3)
        self.entry_deltaX.setKeyboardTracking(False)

        self.entry_NX = QSpinBox()
        self.entry_NX.setMinimum(1) 
        self.entry_NX.setMaximum(50) 
        self.entry_NX.setSingleStep(1)
        self.entry_NX.setValue(1)
        self.entry_NX.setKeyboardTracking(False)

        self.entry_deltaY = QDoubleSpinBox()
        self.entry_deltaY.setMinimum(0) 
        self.entry_deltaY.setMaximum(5) 
        self.entry_deltaY.setSingleStep(0.1)
        self.entry_deltaY.setValue(Acquisition.DEFAULT_DX_MM)
        self.entry_deltaY.setDecimals(3)
        self.entry_deltaY.setKeyboardTracking(False)
        
        self.entry_NY = QSpinBox()
        self.entry_NY.setMinimum(1) 
        self.entry_NY.setMaximum(50) 
        self.entry_NY.setSingleStep(1)
        self.entry_NY.setValue(1)
        self.entry_NY.setKeyboardTracking(False)

        self.entry_deltaZ = QDoubleSpinBox()
        self.entry_deltaZ.setMinimum(0) 
        self.entry_deltaZ.setMaximum(1000) 
        self.entry_deltaZ.setSingleStep(0.2)
        self.entry_deltaZ.setValue(Acquisition.DEFAULT_DZ_MM)
        self.entry_deltaZ.setDecimals(3)
        self.entry_deltaZ.setKeyboardTracking(False)
        
        self.entry_NZ = QSpinBox()
        self.entry_NZ.setMinimum(1) 
        self.entry_NZ.setMaximum(100) 
        self.entry_NZ.setSingleStep(1)
        self.entry_NZ.setValue(1)
        self.entry_NZ.setKeyboardTracking(False)
        
        self.entry_dt = QDoubleSpinBox()
        self.entry_dt.setMinimum(0) 
        self.entry_dt.setMaximum(12*3600) 
        self.entry_dt.setSingleStep(1)
        self.entry_dt.setValue(0)
        self.entry_dt.setKeyboardTracking(False)

        self.entry_Nt = QSpinBox()
        self.entry_Nt.setMinimum(1) 
        self.entry_Nt.setMaximum(50000)   # @@@ to be changed
        self.entry_Nt.setSingleStep(1)
        self.entry_Nt.setValue(1)
        self.entry_Nt.setKeyboardTracking(False)

        self.list_configurations = QListWidget()
        for microscope_configuration in self.configurationManager.configurations:
            self.list_configurations.addItems([microscope_configuration.name])
        self.list_configurations.setSelectionMode(QAbstractItemView.MultiSelection) # ref: https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum
        self.list_configurations.setDragDropMode(QAbstractItemView.InternalMove) # allow moving items within list

        self.checkbox_withAutofocus = QCheckBox('With AF')
        self.checkbox_withAutofocus.setToolTip("enable autofocus for multipoint acquisition\nfor each well the autofocus will be calculated in the channel selected below")
        self.checkbox_withAutofocus.setChecked(MACHINE_DISPLAY_CONFIG.MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.multipointController.set_af_flag(MACHINE_DISPLAY_CONFIG.MULTIPOINT_AUTOFOCUS_ENABLE_BY_DEFAULT)
        self.btn_startAcquisition = QPushButton('Start Acquisition')
        self.btn_startAcquisition.setCheckable(True)
        self.btn_startAcquisition.setChecked(False)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('Saving Path'))
        grid_line0.addWidget(self.lineEdit_savingDir, 0,1)
        grid_line0.addWidget(self.btn_setSavingDir, 0,2)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Experiment ID'), 0,0)
        grid_line1.addWidget(self.lineEdit_experimentID,0,1)

        grid_line2 = QGridLayout()
        dx_tooltip="acquire grid of images (Nx images with dx mm in between acquisitions; dx does not matter if Nx is 1)\ncan be combined with dy/Ny and dz/Nz and dt/Nt for a total of Nx * Ny * Nz * Nt images"
        qtlabel_dx=QLabel('dx (mm)')
        qtlabel_dx.setToolTip(dx_tooltip)
        grid_line2.addWidget(qtlabel_dx, 0,0)
        grid_line2.addWidget(self.entry_deltaX, 0,1)
        qtlabel_Nx=QLabel('Nx')
        qtlabel_Nx.setToolTip(dx_tooltip)
        grid_line2.addWidget(qtlabel_Nx, 0,2)
        grid_line2.addWidget(self.entry_NX, 0,3)
 
        dy_tooltip="acquire grid of images (Ny images with dy mm in between acquisitions; dy does not matter if Ny is 1)\ncan be combined with dx/Nx and dz/Nz and dt/Nt for a total of Nx*Ny*Nz*Nt images"
        qtlabel_dy=QLabel('dy (mm)')
        qtlabel_dy.setToolTip(dy_tooltip)
        grid_line2.addWidget(qtlabel_dy, 1,0)
        grid_line2.addWidget(self.entry_deltaY, 1,1)
        qtlabel_Ny=QLabel('Ny')
        qtlabel_Ny.setToolTip(dy_tooltip)
        grid_line2.addWidget(qtlabel_Ny, 1,2)
        grid_line2.addWidget(self.entry_NY, 1,3)
 
        dz_tooltip="acquire z-stack of images (Nz images with dz µm in between acquisitions; dz does not matter if Nz is 1)\ncan be combined with dx/Nx and dy/Ny and dt/Nt for a total of Nx*Ny*Nz*Nt images"
        qtlabel_dz=QLabel('dz (um)')
        qtlabel_dz.setToolTip(dx_tooltip)
        grid_line2.addWidget(qtlabel_dz, 2,0)
        grid_line2.addWidget(self.entry_deltaZ, 2,1)
        qtlabel_Nz=QLabel('Nz')
        qtlabel_Nz.setToolTip(dx_tooltip)
        grid_line2.addWidget(qtlabel_Nz, 2,2)
        grid_line2.addWidget(self.entry_NZ, 2,3)
 
        dt_tooltip="acquire time-series of 'Nt' images, with 'dt' seconds in between acquisitions (dt does not matter if Nt is 1)\ncan be combined with dx/Nx and dy/Ny and dz/Nz for a total of Nx*Ny*Nz*Nt images"
        qtlabel_dt=QLabel('dt (s)')
        qtlabel_dt.setToolTip(dt_tooltip)
        grid_line2.addWidget(qtlabel_dt, 3,0)
        grid_line2.addWidget(self.entry_dt, 3,1)
        qtlabel_Nt=QLabel('Nt')
        qtlabel_Nt.setToolTip(dt_tooltip)
        grid_line2.addWidget(qtlabel_Nt, 3,2)
        grid_line2.addWidget(self.entry_Nt, 3,3)

        af_channel_dropdown=QComboBox()
        af_channel_dropdown.setToolTip("set channel that will be used for autofocus measurements")
        channel_names=[microscope_configuration.name for microscope_configuration in self.configurationManager.configurations]
        af_channel_dropdown.addItems(channel_names)
        af_channel_dropdown.setCurrentIndex(channel_names.index(self.multipointController.autofocus_channel_name))
        af_channel_dropdown.currentIndexChanged.connect(lambda index:setattr(MUTABLE_MACHINE_CONFIG,"MULTIPOINT_AUTOFOCUS_CHANNEL",channel_names[index]))

        grid_multipoint_acquisition_config=QGridLayout()
        grid_multipoint_acquisition_config.addWidget(self.checkbox_withAutofocus,0,0)
        grid_multipoint_acquisition_config.addWidget(af_channel_dropdown,1,0)
        grid_multipoint_acquisition_config.addWidget(self.btn_startAcquisition,2,0)

        grid_line3 = QHBoxLayout()
        grid_line3.addWidget(self.list_configurations)
        grid_line3.addLayout(grid_multipoint_acquisition_config)

        self.progress_bar=QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        self.grid.addLayout(grid_line3,3,0)
        self.grid.addWidget(self.progress_bar,4,0)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        self.entry_deltaX.valueChanged.connect(self.set_deltaX)
        self.entry_deltaY.valueChanged.connect(self.set_deltaY)
        self.entry_deltaZ.valueChanged.connect(self.set_deltaZ)
        self.entry_dt.valueChanged.connect(self.multipointController.set_deltat)
        self.entry_NX.valueChanged.connect(self.multipointController.set_NX)
        self.entry_NY.valueChanged.connect(self.multipointController.set_NY)
        self.entry_NZ.valueChanged.connect(self.multipointController.set_NZ)
        self.entry_Nt.valueChanged.connect(self.multipointController.set_Nt)
        self.checkbox_withAutofocus.stateChanged.connect(self.multipointController.set_af_flag)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)

    @TypecheckFunction
    def set_deltaX(self,value:float):
        mm_per_ustep = MACHINE_CONFIG.SCREW_PITCH_X_MM/(self.multipointController.navigationController.x_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_X) # to implement a get_x_microstepping() in multipointController
        deltaX = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_deltaX.setValue(deltaX)
        self.multipointController.set_deltaX(deltaX)

    @TypecheckFunction
    def set_deltaY(self,value:float):
        mm_per_ustep = MACHINE_CONFIG.SCREW_PITCH_Y_MM/(self.multipointController.navigationController.y_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Y)
        deltaY = round(value/mm_per_ustep)*mm_per_ustep
        self.entry_deltaY.setValue(deltaY)
        self.multipointController.set_deltaY(deltaY)

    @TypecheckFunction
    def set_deltaZ(self,value:float):
        mm_per_ustep = MACHINE_CONFIG.SCREW_PITCH_Z_MM/(self.multipointController.navigationController.z_microstepping*MACHINE_CONFIG.FULLSTEPS_PER_REV_Z)
        deltaZ = round(value/1000/mm_per_ustep)*mm_per_ustep*1000
        self.entry_deltaZ.setValue(deltaZ)
        self.multipointController.set_deltaZ(deltaZ)

    @TypecheckFunction
    def set_saving_dir(self,_state:Any=None):
        dialog = QFileDialog(options=QFileDialog.DontUseNativeDialog)
        dialog.setWindowModality(Qt.ApplicationModal)
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        if save_dir_base!="":
            self.multipointController.set_base_path(save_dir_base)
            self.lineEdit_savingDir.setText(save_dir_base)
            self.base_path_is_set = True

    @TypecheckFunction
    def toggle_acquisition(self,pressed:bool):
        if self.base_path_is_set == False:
            self.btn_startAcquisition.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return

        if pressed:
            # @@@ to do: add a widgetManger to enable and disable widget 
            # @@@ to do: emit signal to widgetManager to disable other widgets
            self.setEnabled_all(False)

            experiment_data_target_folder:str=self.lineEdit_experimentID.text()
            imaging_channel_list:List[str]=[item.text() for item in self.list_configurations.selectedItems()]

            self.start_experiment(
                experiment_data_target_folder,
                imaging_channel_list
            )
        else:
            self.abort_experiment()
            self.setEnabled_all(True)

    @TypecheckFunction
    def acquisition_is_finished(self):
        self.btn_startAcquisition.setChecked(False)
        self.setEnabled_all(True)

    @TypecheckFunction
    def setEnabled_all(self,enabled:bool,exclude_btn_startAcquisition:bool=True):
        self.btn_setSavingDir.setEnabled(enabled)
        self.lineEdit_savingDir.setEnabled(enabled)
        self.lineEdit_experimentID.setEnabled(enabled)
        self.entry_deltaX.setEnabled(enabled)
        self.entry_NX.setEnabled(enabled)
        self.entry_deltaY.setEnabled(enabled)
        self.entry_NY.setEnabled(enabled)
        self.entry_deltaZ.setEnabled(enabled)
        self.entry_NZ.setEnabled(enabled)
        self.entry_dt.setEnabled(enabled)
        self.entry_Nt.setEnabled(enabled)
        self.list_configurations.setEnabled(enabled)
        self.checkbox_withAutofocus.setEnabled(enabled)
        if exclude_btn_startAcquisition is not True:
            self.btn_startAcquisition.setEnabled(enabled)

    @TypecheckFunction
    def disable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(False)

    @TypecheckFunction
    def enable_the_start_aquisition_button(self):
        self.btn_startAcquisition.setEnabled(True)
