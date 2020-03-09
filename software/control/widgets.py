# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

from control._def import *

class CameraSettingsWidget(QFrame):

    def __init__(self, camera, liveController, main=None, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.camera = camera
        self.liveController = liveController
        # add components to self.grid
        self.add_components()        
        # set frame style
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):

        # add buttons and input fields
        self.entry_exposureTime = QDoubleSpinBox()
        self.entry_exposureTime.setMinimum(self.camera.EXPOSURE_TIME_MS_MIN) 
        self.entry_exposureTime.setMaximum(self.camera.EXPOSURE_TIME_MS_MAX) 
        self.entry_exposureTime.setSingleStep(1)
        self.entry_exposureTime.setValue(20)
        self.camera.set_exposure_time(20)

        self.entry_analogGain = QDoubleSpinBox()
        self.entry_analogGain.setMinimum(self.camera.GAIN_MIN) 
        self.entry_analogGain.setMaximum(self.camera.GAIN_MAX) 
        self.entry_analogGain.setSingleStep(self.camera.GAIN_STEP)
        self.entry_analogGain.setValue(0)
        self.camera.set_analog_gain(0)

        self.entry_exposureTimeBFPreset = QDoubleSpinBox()
        self.entry_exposureTimeBFPreset.setMinimum(self.camera.EXPOSURE_TIME_MS_MIN)
        self.entry_exposureTimeBFPreset.setMaximum(self.camera.EXPOSURE_TIME_MS_MAX)
        self.entry_exposureTimeBFPreset.setSingleStep(1)
        self.entry_exposureTimeBFPreset.setValue(20)
        self.liveController.set_exposure_time_bfdf_preset(20)

        self.entry_analogGainBFPreset = QDoubleSpinBox()
        self.entry_analogGainBFPreset.setMinimum(self.camera.GAIN_MIN) 
        self.entry_analogGainBFPreset.setMaximum(self.camera.GAIN_MAX) 
        self.entry_analogGainBFPreset.setSingleStep(self.camera.GAIN_STEP)
        self.entry_analogGainBFPreset.setValue(0)
        self.liveController.set_analog_gain_bfdf_preset(0)

        self.entry_exposureTimeFLPreset = QDoubleSpinBox()
        self.entry_exposureTimeFLPreset.setMinimum(self.camera.EXPOSURE_TIME_MS_MIN)
        self.entry_exposureTimeFLPreset.setMaximum(self.camera.EXPOSURE_TIME_MS_MAX)
        self.entry_exposureTimeFLPreset.setSingleStep(1)
        self.entry_exposureTimeFLPreset.setValue(100)
        self.liveController.set_exposure_time_fl_preset(100)

        self.entry_analogGainFLPreset = QDoubleSpinBox()
        self.entry_analogGainFLPreset.setMinimum(self.camera.GAIN_MIN) 
        self.entry_analogGainFLPreset.setMaximum(self.camera.GAIN_MAX) 
        self.entry_analogGainFLPreset.setSingleStep(self.camera.GAIN_STEP)
        self.entry_analogGainFLPreset.setValue(10)
        self.liveController.set_analog_gain_fl_preset(10)

        self.entry_exposureTimeFLPreviewPreset = QDoubleSpinBox()
        self.entry_exposureTimeFLPreviewPreset.setMinimum(self.camera.EXPOSURE_TIME_MS_MIN)
        self.entry_exposureTimeFLPreviewPreset.setMaximum(self.camera.EXPOSURE_TIME_MS_MAX)
        self.entry_exposureTimeFLPreviewPreset.setSingleStep(1)
        self.entry_exposureTimeFLPreviewPreset.setValue(20)
        self.liveController.set_exposure_time_fl_preview_preset(20)

        self.entry_analogGainFLPreviewPreset = QDoubleSpinBox()
        self.entry_analogGainFLPreviewPreset.setMinimum(self.camera.GAIN_MIN) 
        self.entry_analogGainFLPreviewPreset.setMaximum(self.camera.GAIN_MAX) 
        self.entry_analogGainFLPreviewPreset.setSingleStep(self.camera.GAIN_STEP)
        self.entry_analogGainFLPreviewPreset.setValue(24)
        self.liveController.set_analog_gain_fl_preview_preset(24)

        self.btn_brightFieldPreset = QPushButton("BF/DF Preset")
        self.btn_brightFieldPreset.setDefault(False)
        self.btn_fluorescencePreset = QPushButton("FL Preset")
        self.btn_fluorescencePreset.setDefault(False)
        self.btn_fluorescencePreviewPreset = QPushButton("FL Preview Preset")
        self.btn_fluorescencePreviewPreset.setDefault(False)

        # connection
        self.btn_brightFieldPreset.clicked.connect(self.load_bf_preset)
        self.btn_fluorescencePreset.clicked.connect(self.load_fl_preset)
        self.btn_fluorescencePreviewPreset.clicked.connect(self.load_fl_preview_preset)
        self.entry_exposureTime.valueChanged.connect(self.camera.set_exposure_time)
        self.entry_analogGain.valueChanged.connect(self.camera.set_analog_gain)
        self.entry_exposureTimeBFPreset.valueChanged.connect(self.liveController.set_exposure_time_bfdf_preset)
        self.entry_analogGainBFPreset.valueChanged.connect(self.liveController.set_analog_gain_bfdf_preset)
        self.entry_exposureTimeFLPreset.valueChanged.connect(self.liveController.set_exposure_time_fl_preset)
        self.entry_analogGainFLPreset.valueChanged.connect(self.liveController.set_analog_gain_fl_preset)
        self.entry_exposureTimeFLPreviewPreset.valueChanged.connect(self.liveController.set_exposure_time_fl_preview_preset)
        self.entry_analogGainFLPreviewPreset.valueChanged.connect(self.liveController.set_analog_gain_fl_preview_preset)

        # layout
        grid_ctrl = QGridLayout()
        grid_ctrl.addWidget(QLabel('Exposure Time (ms)'), 0,0)
        grid_ctrl.addWidget(self.entry_exposureTime, 0,1)
        grid_ctrl.addWidget(QLabel('Analog Gain'), 1,0)
        grid_ctrl.addWidget(self.entry_analogGain, 1,1)

        grid_ctrl_preset = QGridLayout()
        grid_ctrl_preset.addWidget(self.entry_exposureTimeBFPreset, 0,0)
        grid_ctrl_preset.addWidget(self.entry_analogGainBFPreset, 0,1)
        grid_ctrl_preset.addWidget(self.btn_brightFieldPreset, 0,2)
        grid_ctrl_preset.addWidget(self.entry_exposureTimeFLPreset, 1,0)
        grid_ctrl_preset.addWidget(self.entry_analogGainFLPreset, 1,1)
        grid_ctrl_preset.addWidget(self.btn_fluorescencePreset, 1,2)
        grid_ctrl_preset.addWidget(self.entry_exposureTimeFLPreviewPreset, 2,0)
        grid_ctrl_preset.addWidget(self.entry_analogGainFLPreviewPreset, 2,1)
        grid_ctrl_preset.addWidget(self.btn_fluorescencePreviewPreset, 2,2)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_ctrl,0,0)
        self.grid.addLayout(grid_ctrl_preset,1,0)

        self.setLayout(self.grid)

    def load_bf_preset(self):
        self.entry_exposureTime.setValue(self.entry_exposureTimeBFPreset.value())
        self.entry_exposureTime.repaint() # update doesn't work
        self.entry_analogGain.setValue(self.entry_analogGainBFPreset.value())
        self.entry_analogGain.repaint()

    def load_fl_preset(self):
        self.entry_exposureTime.setValue(self.entry_exposureTimeFLPreset.value())
        self.entry_exposureTime.repaint() # update doesn't work
        self.entry_analogGain.setValue(self.entry_analogGainFLPreset.value())
        self.entry_analogGain.repaint()

    def load_fl_preview_preset(self):
        self.entry_exposureTime.setValue(self.entry_exposureTimeFLPreviewPreset.value())
        self.entry_exposureTime.repaint() # update doesn't work
        self.entry_analogGain.setValue(self.entry_analogGainFLPreviewPreset.value())
        self.entry_analogGain.repaint()

class LiveControlWidget(QFrame):
    def __init__(self, streamHandler, liveController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.liveController = liveController
        self.streamHandler = streamHandler
        self.fps_trigger = 10
        self.fps_display = 10
        self.liveController.set_trigger_fps(self.fps_trigger)
        self.streamHandler.set_display_fps(self.fps_display)
        
        self.triggerMode = TriggerMode.SOFTWARE
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        # line 0: trigger mode
        self.triggerMode = None
        self.dropdown_triggerManu = QComboBox()
        self.dropdown_triggerManu.addItems([TriggerMode.SOFTWARE,TriggerMode.HARDWARE,TriggerMode.CONTINUOUS])

        # line 1: fps
        self.entry_triggerFPS = QDoubleSpinBox()
        self.entry_triggerFPS.setMinimum(0.02) 
        self.entry_triggerFPS.setMaximum(200) 
        self.entry_triggerFPS.setSingleStep(1)
        self.entry_triggerFPS.setValue(self.fps_trigger)

        # line 2: choose microscope mode / toggle live mode @@@ change mode to microscope_mode
        self.dropdown_modeSelection = QComboBox()
        self.dropdown_modeSelection.addItems([MicroscopeMode.BFDF, MicroscopeMode.FLUORESCENCE, MicroscopeMode.FLUORESCENCE_PREVIEW])
        self.dropdown_modeSelection.setCurrentText(MicroscopeMode.BFDF)
        self.liveController.set_microscope_mode(self.dropdown_modeSelection.currentText())

        self.btn_live = QPushButton("Live")
        self.btn_live.setCheckable(True)
        self.btn_live.setChecked(False)
        self.btn_live.setDefault(False)

        # line 3: display fps and resolution scaling
        self.entry_displayFPS = QDoubleSpinBox()
        self.entry_displayFPS.setMinimum(1) 
        self.entry_displayFPS.setMaximum(240) 
        self.entry_displayFPS.setSingleStep(1)
        self.entry_displayFPS.setValue(self.fps_display)

        self.slider_resolutionScaling = QSlider(Qt.Horizontal)
        self.slider_resolutionScaling.setTickPosition(QSlider.TicksBelow)
        self.slider_resolutionScaling.setMinimum(10)
        self.slider_resolutionScaling.setMaximum(100)
        self.slider_resolutionScaling.setValue(50)
        self.slider_resolutionScaling.setSingleStep(10)

        # connections
        self.entry_triggerFPS.valueChanged.connect(self.liveController.set_trigger_fps)
        self.entry_displayFPS.valueChanged.connect(self.streamHandler.set_display_fps)
        self.slider_resolutionScaling.valueChanged.connect(self.streamHandler.set_display_resolution_scaling)
        self.dropdown_modeSelection.currentIndexChanged.connect(self.update_microscope_mode)
        self.dropdown_triggerManu.currentIndexChanged.connect(self.update_trigger_mode)
        self.btn_live.clicked.connect(self.toggle_live)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('Trigger Mode'), 0,0)
        grid_line0.addWidget(self.dropdown_triggerManu, 0,1)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Trigger FPS'), 0,0)
        grid_line1.addWidget(self.entry_triggerFPS, 0,1)
        grid_line1.addWidget(self.dropdown_modeSelection, 0,2)
        grid_line1.addWidget(self.btn_live, 0,3)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Display FPS'), 0,0)
        grid_line2.addWidget(self.entry_displayFPS, 0,1)
        grid_line2.addWidget(QLabel('Display Resolution'), 0,2)
        grid_line2.addWidget(self.slider_resolutionScaling,0,3)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        self.setLayout(self.grid)

    def toggle_live(self,pressed):
        if pressed:
            self.liveController.start_live()
        else:
            self.liveController.stop_live()

    def update_microscope_mode(self,index):
        self.liveController.turn_off_illumination()
        self.liveController.set_microscope_mode(self.dropdown_modeSelection.currentText())

    def update_trigger_mode(self):
        self.set_trigger_mode(self.dropdown_triggerManu.currentText())

class RecordingWidget(QFrame):
    def __init__(self, streamHandler, imageSaver, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imageSaver = imageSaver # for saving path control
        self.streamHandler = streamHandler
        self.base_path_is_set = False
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')

        self.lineEdit_experimentID = QLineEdit()

        self.entry_saveFPS = QDoubleSpinBox()
        self.entry_saveFPS.setMinimum(0.02) 
        self.entry_saveFPS.setMaximum(200) 
        self.entry_saveFPS.setSingleStep(1)
        self.entry_saveFPS.setValue(1)
        self.streamHandler.set_save_fps(1)

        self.entry_timeLimit = QSpinBox()
        self.entry_timeLimit.setMinimum(-1) 
        self.entry_timeLimit.setMaximum(60*60*24*30) 
        self.entry_timeLimit.setSingleStep(1)
        self.entry_timeLimit.setValue(-1)

        self.btn_record = QPushButton("Record")
        self.btn_record.setCheckable(True)
        self.btn_record.setChecked(False)
        self.btn_record.setDefault(False)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Saving Path'))
        grid_line1.addWidget(self.lineEdit_savingDir, 0,1)
        grid_line1.addWidget(self.btn_setSavingDir, 0,2)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Experiment ID'), 0,0)
        grid_line2.addWidget(self.lineEdit_experimentID,0,1)

        grid_line3 = QGridLayout()
        grid_line3.addWidget(QLabel('Saving FPS'), 0,0)
        grid_line3.addWidget(self.entry_saveFPS, 0,1)
        grid_line3.addWidget(QLabel('Time Limit (s)'), 0,2)
        grid_line3.addWidget(self.entry_timeLimit, 0,3)
        grid_line3.addWidget(self.btn_record, 0,4)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line1,0,0)
        self.grid.addLayout(grid_line2,1,0)
        self.grid.addLayout(grid_line3,2,0)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_record.clicked.connect(self.toggle_recording)
        self.entry_saveFPS.valueChanged.connect(self.streamHandler.set_save_fps)
        self.entry_timeLimit.valueChanged.connect(self.imageSaver.set_recording_time_limit)
        self.imageSaver.stop_recording.connect(self.stop_recording)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.imageSaver.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True

    def toggle_recording(self,pressed):
        if self.base_path_is_set == False:
            self.btn_record.setChecked(False)
            msg = QMessageBox()
            msg.setText("Please choose base saving directory first")
            msg.exec_()
            return
        if pressed:
            self.lineEdit_experimentID.setEnabled(False)
            self.btn_setSavingDir.setEnabled(False)
            self.imageSaver.start_new_experiment(self.lineEdit_experimentID.text())
            self.streamHandler.start_recording()
        else:
            self.streamHandler.stop_recording()
            self.lineEdit_experimentID.setEnabled(True)
            self.btn_setSavingDir.setEnabled(True)

    # stop_recording can be called by imageSaver
    def stop_recording(self):
        self.lineEdit_experimentID.setEnabled(True)
        self.btn_record.setChecked(False)
        self.streamHandler.stop_recording()
        self.btn_setSavingDir.setEnabled(True)

class NavigationWidget(QFrame):
    def __init__(self, navigationController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigationController = navigationController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.label_Xpos = QLabel()
        self.label_Xpos.setNum(0)
        self.label_Xpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dX = QDoubleSpinBox()
        self.entry_dX.setMinimum(0) 
        self.entry_dX.setMaximum(5) 
        self.entry_dX.setSingleStep(0.2)
        self.entry_dX.setValue(0)
        self.btn_moveX_forward = QPushButton('Forward')
        self.btn_moveX_forward.setDefault(False)
        self.btn_moveX_backward = QPushButton('Backward')
        self.btn_moveX_backward.setDefault(False)
        
        self.label_Ypos = QLabel()
        self.label_Ypos.setNum(0)
        self.label_Ypos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dY = QDoubleSpinBox()
        self.entry_dY.setMinimum(0)
        self.entry_dY.setMaximum(5)
        self.entry_dY.setSingleStep(0.2)
        self.entry_dY.setValue(0)
        self.btn_moveY_forward = QPushButton('Forward')
        self.btn_moveY_forward.setDefault(False)
        self.btn_moveY_backward = QPushButton('Backward')
        self.btn_moveY_backward.setDefault(False)

        self.label_Zpos = QLabel()
        self.label_Zpos.setNum(0)
        self.label_Zpos.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.entry_dZ = QDoubleSpinBox()
        self.entry_dZ.setMinimum(0) 
        self.entry_dZ.setMaximum(1000) 
        self.entry_dZ.setSingleStep(0.2)
        self.entry_dZ.setValue(0)
        self.btn_moveZ_forward = QPushButton('Forward')
        self.btn_moveZ_forward.setDefault(False)
        self.btn_moveZ_backward = QPushButton('Backward')
        self.btn_moveZ_backward.setDefault(False)
        
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('X (mm)'), 0,0)
        grid_line0.addWidget(self.label_Xpos, 0,1)
        grid_line0.addWidget(self.entry_dX, 0,2)
        grid_line0.addWidget(self.btn_moveX_forward, 0,3)
        grid_line0.addWidget(self.btn_moveX_backward, 0,4)

        grid_line1 = QGridLayout()
        grid_line1.addWidget(QLabel('Y (mm)'), 0,0)
        grid_line1.addWidget(self.label_Ypos, 0,1)
        grid_line1.addWidget(self.entry_dY, 0,2)
        grid_line1.addWidget(self.btn_moveY_forward, 0,3)
        grid_line1.addWidget(self.btn_moveY_backward, 0,4)

        grid_line2 = QGridLayout()
        grid_line2.addWidget(QLabel('Z (um)'), 0,0)
        grid_line2.addWidget(self.label_Zpos, 0,1)
        grid_line2.addWidget(self.entry_dZ, 0,2)
        grid_line2.addWidget(self.btn_moveZ_forward, 0,3)
        grid_line2.addWidget(self.btn_moveZ_backward, 0,4)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        self.setLayout(self.grid)

        self.btn_moveX_forward.clicked.connect(self.move_x_forward)
        self.btn_moveX_backward.clicked.connect(self.move_x_backward)
        self.btn_moveY_forward.clicked.connect(self.move_y_forward)
        self.btn_moveY_backward.clicked.connect(self.move_y_backward)
        self.btn_moveZ_forward.clicked.connect(self.move_z_forward)
        self.btn_moveZ_backward.clicked.connect(self.move_z_backward)
        
    def move_x_forward(self):
        self.navigationController.move_x(self.entry_dX.value())
        print('move x')
    def move_x_backward(self):
        self.navigationController.move_x(-self.entry_dX.value())
    def move_y_forward(self):
        self.navigationController.move_y(self.entry_dY.value())
    def move_y_backward(self):
        self.navigationController.move_y(-self.entry_dY.value())
    def move_z_forward(self):
        self.navigationController.move_z(self.entry_dZ.value()/1000)
    def move_z_backward(self):
        self.navigationController.move_z(-self.entry_dZ.value()/1000)

class AutoFocusWidget(QFrame):
    def __init__(self, autofocusController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.autofocusController = autofocusController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.entry_delta = QDoubleSpinBox()
        self.entry_delta.setMinimum(0.2) 
        self.entry_delta.setMaximum(20) 
        self.entry_delta.setSingleStep(0.2)
        self.entry_delta.setValue(3)
        self.autofocusController.set_deltaZ(3)

        self.entry_N = QSpinBox()
        self.entry_N.setMinimum(3) 
        self.entry_N.setMaximum(20) 
        self.entry_N.setSingleStep(1)
        self.entry_N.setValue(10)
        self.autofocusController.set_N(10)

        self.btn_autofocus = QPushButton('Autofocus')
        self.btn_autofocus.setDefault(False)
        self.btn_autofocus.setCheckable(True)
        self.btn_autofocus.setChecked(False)

        # layout
        grid_line0 = QGridLayout()
        grid_line0.addWidget(QLabel('delta Z (um)'), 0,0)
        grid_line0.addWidget(self.entry_delta, 0,1)
        grid_line0.addWidget(QLabel('N Z planes'), 0,2)
        grid_line0.addWidget(self.entry_N, 0,3)
        grid_line0.addWidget(self.btn_autofocus, 0,4)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.setLayout(self.grid)
        
        # connections
        self.btn_autofocus.clicked.connect(self.autofocusController.autofocus)
        self.entry_delta.valueChanged.connect(self.autofocusController.set_deltaZ)
        self.entry_N.valueChanged.connect(self.autofocusController.set_N)
        self.autofocusController.autofocusFinished.connect(self.autofocus_is_finished)

    def autofocus_is_finished(self):
        self.btn_autofocus.setChecked(False)

class MultiPointWidget(QFrame):
    def __init__(self, multipointController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multipointController = multipointController
        self.base_path_is_set = False
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):

        self.btn_setSavingDir = QPushButton('Browse')
        self.btn_setSavingDir.setDefault(False)
        self.btn_setSavingDir.setIcon(QIcon('icon/folder.png'))
        
        self.lineEdit_savingDir = QLineEdit()
        self.lineEdit_savingDir.setReadOnly(True)
        self.lineEdit_savingDir.setText('Choose a base saving directory')

        self.lineEdit_experimentID = QLineEdit()

        self.entry_deltaX = QDoubleSpinBox()
        self.entry_deltaX.setMinimum(0.2) 
        self.entry_deltaX.setMaximum(5) 
        self.entry_deltaX.setSingleStep(1)
        self.entry_deltaX.setValue(Acquisition.DX)

        self.entry_NX = QSpinBox()
        self.entry_NX.setMinimum(1) 
        self.entry_NX.setMaximum(20) 
        self.entry_NX.setSingleStep(1)
        self.entry_NX.setValue(1)

        self.entry_deltaY = QDoubleSpinBox()
        self.entry_deltaY.setMinimum(0.2) 
        self.entry_deltaY.setMaximum(5) 
        self.entry_deltaY.setSingleStep(1)
        self.entry_deltaY.setValue(Acquisition.DX)
        
        self.entry_NY = QSpinBox()
        self.entry_NY.setMinimum(1) 
        self.entry_NY.setMaximum(20) 
        self.entry_NY.setSingleStep(1)
        self.entry_NY.setValue(1)

        self.entry_deltaZ = QDoubleSpinBox()
        self.entry_deltaZ.setMinimum(0) 
        self.entry_deltaZ.setMaximum(1000) 
        self.entry_deltaZ.setSingleStep(0.2)
        self.entry_deltaZ.setValue(Acquisition.DZ)
        
        self.entry_NZ = QSpinBox()
        self.entry_NZ.setMinimum(1) 
        self.entry_NZ.setMaximum(100) 
        self.entry_NZ.setSingleStep(1)
        self.entry_NZ.setValue(1)
        

        self.entry_dt = QDoubleSpinBox()
        self.entry_dt.setMinimum(0) 
        self.entry_dt.setMaximum(3600) 
        self.entry_dt.setSingleStep(1)
        self.entry_dt.setValue(1)

        self.entry_Nt = QSpinBox()
        self.entry_Nt.setMinimum(1) 
        self.entry_Nt.setMaximum(50000)   # @@@ to be changed
        self.entry_Nt.setSingleStep(1)
        self.entry_Nt.setValue(1)

        self.checkbox_bfdf = QCheckBox('BF/DF')
        self.checkbox_fluorescence = QCheckBox('Fluorescence')
        self.checkbox_withAutofocus = QCheckBox('With AF')
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
        grid_line2.addWidget(QLabel('dx (mm)'), 0,0)
        grid_line2.addWidget(self.entry_deltaX, 0,1)
        grid_line2.addWidget(QLabel('Nx'), 0,2)
        grid_line2.addWidget(self.entry_NX, 0,3)
        grid_line2.addWidget(QLabel('dy (mm)'), 0,4)
        grid_line2.addWidget(self.entry_deltaY, 0,5)
        grid_line2.addWidget(QLabel('Ny'), 0,6)
        grid_line2.addWidget(self.entry_NY, 0,7)

        grid_line2.addWidget(QLabel('dz (um)'), 1,0)
        grid_line2.addWidget(self.entry_deltaZ, 1,1)
        grid_line2.addWidget(QLabel('Nz'), 1,2)
        grid_line2.addWidget(self.entry_NZ, 1,3)
        grid_line2.addWidget(QLabel('dt (s)'), 1,4)
        grid_line2.addWidget(self.entry_dt, 1,5)
        grid_line2.addWidget(QLabel('Nt'), 1,6)
        grid_line2.addWidget(self.entry_Nt, 1,7)

        grid_line3 = QHBoxLayout()
        grid_line3.addWidget(self.checkbox_bfdf)
        grid_line3.addWidget(self.checkbox_fluorescence)
        grid_line3.addWidget(self.checkbox_withAutofocus)
        grid_line3.addWidget(self.btn_startAcquisition)

        self.grid = QGridLayout()
        self.grid.addLayout(grid_line0,0,0)
        self.grid.addLayout(grid_line1,1,0)
        self.grid.addLayout(grid_line2,2,0)
        self.grid.addLayout(grid_line3,3,0)
        self.setLayout(self.grid)

        # add and display a timer - to be implemented
        # self.timer = QTimer()

        # connections
        self.entry_deltaX.valueChanged.connect(self.multipointController.set_deltaX)
        self.entry_deltaY.valueChanged.connect(self.multipointController.set_deltaY)
        self.entry_deltaZ.valueChanged.connect(self.multipointController.set_deltaZ)
        self.entry_dt.valueChanged.connect(self.multipointController.set_deltat)
        self.entry_NX.valueChanged.connect(self.multipointController.set_NX)
        self.entry_NY.valueChanged.connect(self.multipointController.set_NY)
        self.entry_NZ.valueChanged.connect(self.multipointController.set_NZ)
        self.entry_Nt.valueChanged.connect(self.multipointController.set_Nt)
        self.checkbox_bfdf.stateChanged.connect(self.multipointController.set_bfdf_flag)
        self.checkbox_fluorescence.stateChanged.connect(self.multipointController.set_fluorescence_flag)
        self.checkbox_withAutofocus.stateChanged.connect(self.multipointController.set_af_flag)
        self.btn_setSavingDir.clicked.connect(self.set_saving_dir)
        self.btn_startAcquisition.clicked.connect(self.toggle_acquisition)
        self.multipointController.acquisitionFinished.connect(self.acquisition_is_finished)

    def set_saving_dir(self):
        dialog = QFileDialog()
        save_dir_base = dialog.getExistingDirectory(None, "Select Folder")
        self.multipointController.set_base_path(save_dir_base)
        self.lineEdit_savingDir.setText(save_dir_base)
        self.base_path_is_set = True

    def toggle_acquisition(self,pressed):
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
            self.multipointController.start_new_experiment(self.lineEdit_experimentID.text())
            self.multipointController.run_acquisition()
        else:
            # self.multipointController.stop_acquisition() # to implement
            self.setEnabled_all(True)

    def acquisition_is_finished(self):
        self.btn_startAcquisition.setChecked(False)
        self.setEnabled_all(True)

    def setEnabled_all(self,enabled,exclude_btn_startAcquisition=True):
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
        self.checkbox_bfdf.setEnabled(enabled)
        self.checkbox_fluorescence.setEnabled(enabled)
        self.checkbox_withAutofocus.setEnabled(enabled)
        if exclude_btn_startAcquisition is not True:
        	self.btn_startAcquisition.setEnabled(enabled)

class TrackingControllerWidget(QFrame):
    def __init__(self, multipointController, navigationController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.multipointController = multipointController
        self.navigationController = navigationController
        self.base_path_is_set = False
        # self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

