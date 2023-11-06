# set QT_API environment variable
import os 
os.environ["QT_API"] = "pyqt5"
import qtpy

# qt libraries
from qtpy.QtCore import *
from qtpy.QtWidgets import *
from qtpy.QtGui import *

# xml
from lxml import etree as ET

# app specific libraries
from datetime import datetime
import threading
import fluidics.utils as utils
import fluidics.utils_config as utils_config

from fluidics._def import * 

class PreUseCheckWidget(QFrame):

    log_message = Signal(str)
    signal_disable_manualControlWidget = Signal()
    signal_disable_sequenceWidget = Signal()

    def __init__(self, fluidController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fluidController = fluidController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        
        # create and layout the checkboxes
        hbox_1 = QHBoxLayout()
        self.checkbox = {}
        for port_name in Port.keys():
            port = Port[port_name]
            if port_name == str(port) or port_name == 'Vacuum' :
                checkbox_text =  port_name
            else:
                checkbox_text = port_name + ' (' + str(port) + ')'
            self.checkbox[port_name] = QCheckBox(checkbox_text)
            self.checkbox[port_name].setChecked(True)
            hbox_1.addWidget(self.checkbox[port_name])

        # target pressure 
        self.entry_target_pressure = QDoubleSpinBox()
        self.entry_target_pressure.setMinimum(0)
        self.entry_target_pressure.setMaximum(5.0) 
        self.entry_target_pressure.setSingleStep(0.1)
        self.entry_target_pressure.setValue(4.0)
        hbox_2 = QHBoxLayout()
        hbox_2.addWidget(QLabel('Target Pressure (psi)'))
        hbox_2.addWidget(self.entry_target_pressure)

        # target vacuum 
        self.entry_target_vacuum = QDoubleSpinBox()
        self.entry_target_vacuum.setMinimum(-4.0)
        self.entry_target_vacuum.setMaximum(0) 
        self.entry_target_vacuum.setSingleStep(0.1)
        self.entry_target_vacuum.setValue(-1.0)
        # hbox_3 = QHBoxLayout()
        hbox_2.addWidget(QLabel('\t Target Vacuum (psi)'))
        hbox_2.addWidget(self.entry_target_vacuum)
       
        # add buttons
        self.button_preuse_check = QPushButton('Run Pre-Use Check')
        self.button_preuse_check.setCheckable(False)
        self.button_preuse_check.clicked.connect(self.run_preuse_check)

        vbox = QVBoxLayout()
        vbox.addLayout(hbox_1)
        vbox.addLayout(hbox_2)
        vbox.addWidget(self.button_preuse_check)

        hbox = QHBoxLayout()
        # hbox.addWidget(QLabel('[Pre-use Check]]'))
        hbox.addLayout(vbox)
        self.setLayout(hbox)

        self.fluidController.signal_sequences_execution_stopped.connect(self.enable_preuse_check_widget)

    # def run_preuse_check(self,pressed):
    #     if pressed:
    #         for port_name in Port.keys():
    #             if(self.checkbox[port_name].isChecked()==True):
    #                 print('checking port ' + port_name )
    #                 self.log_message.emit(utils.timestamp() + 'preuse check for ' + port_name)
    #                 QApplication.processEvents()
    #     self.button_preuse_check.setChecked(False)
    #     QApplication.processEvents()

    def run_preuse_check(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run preuse check")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            # print a seperator for visuals
            self.log_message.emit('--------------------------------')
            # go through ports for pressure check
            for port_name in Port.keys():
                if(self.checkbox[port_name].isChecked()==True):
                    self.clear_preuse_check_result(port_name)
                    self.log_message.emit(utils.timestamp() + 'Run preuse check for ' + port_name)
                    QApplication.processEvents()
                    if port_name == 'Vacuum':
                        self.fluidController.add_sequence('Preuse Check (Vacuum)',0,
                            flow_time_s=PREUSE_CHECK_SETTINGS.TIMEOUT_S,pressure_setting=abs(self.entry_target_vacuum.value()),port_name=port_name)
                    elif port_name == 'Air':
                        self.fluidController.add_sequence('Preuse Check (Pressure)',Port[port_name],
                            flow_time_s=PREUSE_CHECK_SETTINGS.TIMEOUT_S,pressure_setting=PREUSE_CHECK_SETTINGS.TARGET_PRESSURE_AIR_PATH_PSI,port_name=port_name)
                    else:
                        self.fluidController.add_sequence('Preuse Check (Pressure)',Port[port_name],
                            flow_time_s=PREUSE_CHECK_SETTINGS.TIMEOUT_S,pressure_setting=self.entry_target_pressure.value(),port_name=port_name)
            self.fluidController.start_sequence_execution()
            # disable widgets
            self.signal_disable_manualControlWidget.emit()
            self.signal_disable_sequenceWidget.emit()
            self.disable_preuse_check_widget()
            QApplication.processEvents()
        else:
            self.log_message.emit(utils.timestamp() + 'no action.')
            QApplication.processEvents()

    def enable_preuse_check_widget(self):
        self.setEnabled(True)

    def disable_preuse_check_widget(self):
        self.setEnabled(False)

    def show_preuse_check_result(self,port_name,passed):
        if passed == True:
            self.checkbox[port_name].setStyleSheet("color: white;"
                "background-color: green")
        else:
            self.checkbox[port_name].setStyleSheet("color: white;"
                "background-color: red")

    def clear_preuse_check_result(self,port_name):
        self.checkbox[port_name].setStyleSheet("")

class TriggerWidget(QFrame):

    def __init__(self, triggerController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.triggerController = triggerController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.button_trigger_microscope = QPushButton('Trigger Microscope')
        self.button_trigger_microscope.clicked.connect(self.trigger_microscope)
        hbox = QHBoxLayout() 
        hbox.addWidget(QLabel('[Manual Microscope Trigger]'))
        hbox.addWidget(self.button_trigger_microscope)
        self.setLayout(hbox)

    def trigger_microscope(self,pressed):
        #if pressed:
        self.triggerController.send_trigger()

class SequenceEntry(QWidget):
    def __init__(self, sequence_name = None, port_name = None, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sequence_name = sequence_name
        self.port_name = port_name
        '''
        # using list 
        self.attributes = []
        self.attributes.append(QLabel(self.sequence_name))
        self.attributes.append(QCheckBox('Include'))
        self.attributes.append(QDoubleSpinBox())
        self.attributes.append(QDoubleSpinBox()) # incubation_time
        self.attributes.append(QSpinBox()) # repeat
        '''
        # using dictionary
        self.attributes_key = SEQUENCE_ATTRIBUTES_KEYS
        self.attributes = {}
        self.attributes['Sequence'] = QLabel(self.sequence_name)
        self.attributes['Fluidic Port'] = QSpinBox()
        self.attributes['Fluidic Port'].setMinimum(1) # 0: virtual port - does not care
        self.attributes['Fluidic Port'].setMaximum(24)
        self.attributes['Flow Time (s)'] = QDoubleSpinBox()
        self.attributes['Flow Time (s)'].setMinimum(0) # -1: no flow
        self.attributes['Flow Time (s)'].setMaximum(FLOW_TIME_MAX) 
        self.attributes['Post-Fill Fluidic Port'] = QSpinBox()
        self.attributes['Post-Fill Fluidic Port'].setMinimum(0) # 0: virtual port - does not care
        self.attributes['Post-Fill Fluidic Port'].setMaximum(24)
        self.attributes['Post-Fill Flow Time (s)'] = QDoubleSpinBox()
        self.attributes['Post-Fill Flow Time (s)'].setMinimum(0) # -1: no flow
        self.attributes['Post-Fill Flow Time (s)'].setMaximum(FLOW_TIME_MAX) 
        self.attributes['Incubation Time (min)'] = QDoubleSpinBox()
        self.attributes['Incubation Time (min)'].setDecimals(1)
        self.attributes['Incubation Time (min)'].setMinimum(0) # -1: no incubation
        self.attributes['Incubation Time (min)'].setMaximum(INCUBATION_TIME_MAX_MIN)
        self.attributes['Repeat'] = QSpinBox()
        self.attributes['Repeat'].setMinimum(1)
        self.attributes['Repeat'].setMaximum(25) # change to 25 for testing
        self.attributes['Include'] = QCheckBox()
        # manually make sure the keys are included in SEQUENCE_ATTRIBUTES_KEYS
        
class SequenceWidget(QFrame):

    log_message = Signal(str)
    signal_disable_manualControlWidget = Signal()
    signal_enable_manualControlWidget = Signal()

    def __init__(self, fluidController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fluidController = fluidController
        self.abort_requested = False
        self.config_filename = 'settings_default.xml'
        self.add_components()
        self.load_sequence_settings(self.config_filename)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def close(self):
        self.save_sequence_settings(self.config_filename)

    def add_components(self):

        self.tableWidget = QTableWidget(len(SEQUENCE_NAME),len(SEQUENCE_ATTRIBUTES_KEYS),self)
        self.tableWidget.setHorizontalHeaderLabels(SEQUENCE_ATTRIBUTES_KEYS)
        
        # create the sequences, set the attributes and add the sequences into the tabel
        self.sequences = {}
        self.row_number = {}
        for i in range(len(SEQUENCE_NAME)):
            sequence_name = SEQUENCE_NAME[i]
            self.sequences[sequence_name] = SequenceEntry(sequence_name)
            # insert attributes of the current sequence into the table
            for j in range(len(SEQUENCE_ATTRIBUTES_KEYS)):
                attribute_key = SEQUENCE_ATTRIBUTES_KEYS[j]
                self.tableWidget.setCellWidget(i,j,self.sequences[sequence_name].attributes[attribute_key])
            # self.tableWidget.setCellWidget(i,0,self.sequences[sequence_name].attributes['Label'])
            self.row_number[sequence_name] = i

        # test
        # item = self.tableWidget.findItems('Add Imaging Buffer',Qt.MatchContains)
        # print(item)
        # item[0].setBackgroundColor(Qt.blue)
        # self.tableWidget.selectRow(1)

        # set sequence-specific attributes
        self.sequences['Add Imaging Buffer'].attributes['Incubation Time (min)'].setMinimum(-1)
        self.sequences['Add Imaging Buffer'].attributes['Incubation Time (min)'].setValue(-1)
        self.sequences['Remove Medium'].attributes['Flow Time (s)'].setMinimum(-1) 
        self.sequences['Remove Medium'].attributes['Flow Time (s)'].setValue(-1)

        self.sequences['Add Imaging Buffer'].attributes['Incubation Time (min)'].setEnabled(False)
        self.sequences['Remove Medium'].attributes['Flow Time (s)'].setEnabled(False) 
        # self.sequences['Hybridize'].attributes['Repeat'].setEnabled(False) # change to false for testing
        self.sequences['Add Imaging Buffer'].attributes['Repeat'].setEnabled(False)
        self.sequences['Remove Medium'].attributes['Repeat'].setEnabled(False)
        self.sequences['Remove Medium'].attributes['Incubation Time (min)'].setEnabled(False)
        # self.sequences['Stain with DAPI'].attributes['Repeat'].setEnabled(False) # change to false for testing
        self.sequences['Remove Medium'].attributes['Fluidic Port'].setMinimum(0)
        self.sequences['Remove Medium'].attributes['Fluidic Port'].setValue(0)
        self.sequences['Remove Medium'].attributes['Fluidic Port'].setEnabled(False)

        # port mapping
        self.sequences['Stripping Buffer Wash'].attributes['Fluidic Port'].setValue(Port['Stripping Buffer'])
        self.sequences['Stripping Buffer Wash'].attributes['Fluidic Port'].setEnabled(False)
        self.sequences['Rendering Buffer Wash'].attributes['Fluidic Port'].setValue(Port['Rendering Buffer'])
        self.sequences['Rendering Buffer Wash'].attributes['Fluidic Port'].setEnabled(False)
        # self.sequences['Rendering Buffer Wash 2'].attributes['Fluidic Port'].setValue(Port['Rendering Buffer'])
        # self.sequences['Rendering Buffer Wash 2)'].attributes['Fluidic Port'].setEnabled(False)
        self.sequences['Imaging Buffer Wash'].attributes['Fluidic Port'].setValue(Port['H2 Buffer'])
        self.sequences['Imaging Buffer Wash'].attributes['Fluidic Port'].setEnabled(False)
        self.sequences['Add Imaging Buffer'].attributes['Fluidic Port'].setValue(Port['H2 Buffer'])
        self.sequences['Add Imaging Buffer'].attributes['Fluidic Port'].setEnabled(False)
        # self.sequences['Hybridize'].attributes['Fluidic Port'].setMaximum(11)

        '''
        # changed to disable instead of no buttons
        self.sequences['Hybridize'].attributes['Repeat'].setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.sequences['Add Imaging Buffer'].attributes['Repeat'].setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.sequences['Remove Medium'].attributes['Repeat'].setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.sequences['Stain with DAPI'].attributes['Repeat'].setButtonSymbols(QAbstractSpinBox.NoButtons)
        '''

        # set table size - reference: https://stackoverflow.com/questions/8766633/how-to-determine-the-correct-size-of-a-qtablewidget
        self.tableWidget.resizeColumnsToContents()
        self.tableWidget.setFixedSize(self.tableWidget.horizontalHeader().length() + 
                   self.tableWidget.verticalHeader().width(),self.tableWidget.verticalHeader().length() + 
                   self.tableWidget.horizontalHeader().height())
        self.tableWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tableWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # aspiration settings
        self.entry_aspiration_pump_power = QDoubleSpinBox()
        self.entry_aspiration_pump_power.setKeyboardTracking(False)
        self.entry_aspiration_pump_power.setMinimum(0)
        self.entry_aspiration_pump_power.setMaximum(1)
        self.entry_aspiration_pump_power.setDecimals(2)
        self.entry_aspiration_pump_power.setSingleStep(0.01)
        self.entry_aspiration_pump_power.setValue(DEFAULT_VALUES.aspiration_pump_power)

        self.entry_aspiration_time_s = QDoubleSpinBox()
        self.entry_aspiration_time_s.setKeyboardTracking(False)
        self.entry_aspiration_time_s.setMinimum(0)
        self.entry_aspiration_time_s.setMaximum(PRESSURE_LOOP_COEFFICIENTS_FULL_SCALE)
        self.entry_aspiration_time_s.setDecimals(1)
        self.entry_aspiration_time_s.setSingleStep(1)
        self.entry_aspiration_time_s.setValue(DEFAULT_VALUES.vacuum_aspiration_time_s)

        hbox_aspiration_settings = QHBoxLayout()
        hbox_aspiration_settings.addWidget(QLabel(' Aspiration Settings: '))
        hbox_aspiration_settings.addWidget(QLabel('Pump Power'))
        hbox_aspiration_settings.addWidget(self.entry_aspiration_pump_power)
        hbox_aspiration_settings.addWidget(QLabel('Duration (s)'))
        hbox_aspiration_settings.addWidget(self.entry_aspiration_time_s)
        hbox_aspiration_settings.addStretch()

        # settings loading and saveing
        self.lineEdit_setting_file = QLineEdit()
        self.lineEdit_setting_file.setReadOnly(True)
        self.lineEdit_setting_file.setText(self.config_filename)
        # self.btn_select_setting_file = QPushButton('Browse')
        # self.btn_select_setting_file.setDefault(False)
        # self.btn_select_setting_file.setIcon(QIcon('icon/folder.png'))
        self.button_save = QPushButton('Save Setttings')
        self.button_load = QPushButton('Load Setttings')
        self.button_save.setIcon(QIcon('icon/folder.png'))
        self.button_load.setIcon(QIcon('icon/folder.png'))

        hbox_settings_loading_and_saving = QHBoxLayout()
        hbox_settings_loading_and_saving.addWidget(self.button_save)
        # hbox_settings_loading_and_saving.addWidget(self.btn_select_setting_file)
        hbox_settings_loading_and_saving.addWidget(self.button_load)
        hbox_settings_loading_and_saving.addWidget(self.lineEdit_setting_file)
        hbox_settings_loading_and_saving.addStretch()

        # start and stop
        self.button_run = QPushButton('Run Selected Sequences')
        self.button_stop = QPushButton('Abort')
        self.button_run.setFixedWidth(264)
        #self.button_run.setFixedHeight(50)
        self.button_stop.setFixedWidth(240)
        #self.button_stop.setFixedHeight(50)

        # grid_btns = QGridLayout()
        # grid_btns.addWidget(self.button_save,0,0)
        # grid_btns.addWidget(self.button_load,0,1)
        # grid_btns.addWidget(self.button_run,1,0)
        # grid_btns.addWidget(self.button_stop,1,1)
        grid_btns = QHBoxLayout()
        grid_btns.addWidget(self.button_run)
        grid_btns.addWidget(self.button_stop)
        grid_btns.addStretch()

        vbox = QVBoxLayout()
        vbox.addLayout(hbox_settings_loading_and_saving)
        vbox.addLayout(hbox_aspiration_settings)
        vbox.addWidget(self.tableWidget)
        vbox.addLayout(grid_btns)
        self.setLayout(vbox)

        # make connections
        self.button_run.clicked.connect(self.run_sequences)
        self.button_stop.clicked.connect(self.request_to_abort_sequences)
        # @@@ need to make sure button_stop is still clickable while self.run_sequences() is being executed - done [4/7/2021]
        self.button_stop.setEnabled(False) # the current implementation of run_sequences is blocking, yet abort is possible through a flag in FluidController. Actually the flag can be in the widget. Maybe use in both places, so that for example, wait can be aborted [addressed 4/7/2021]
        # self.button_save.setEnabled(False) # saving settings to be implemented, disable the button for now
        self.fluidController.signal_sequences_execution_stopped.connect(self.enable_widgets_except_for_abort_btn)

        self.button_load.clicked.connect(self.load_user_selected_sequence_settings)
        self.button_save.clicked.connect(self.saveas_sequence_settings)

    def load_sequence_settings(self,filename):

        # create the config file if it does not alreay exist
        if(os.path.isfile(filename)==False):
            utils_config.generate_default_configuration(filename)
            print('creating default configurations')

        # read and parse the config file
        self.config_xml_tree = ET.parse(filename)
        self.config_xml_tree_root = self.config_xml_tree.getroot()
        for sequence in self.config_xml_tree_root.iter('sequence'):
            name = sequence.get('Name')
            self.sequences[name].attributes['Repeat'].setValue(int(sequence.get('Repeat')))
            self.sequences[name].attributes['Fluidic Port'].setValue(0)
            self.sequences[name].attributes['Flow Time (s)'].setValue(float(sequence.get('Flow_Time_in_second')))
            self.sequences[name].attributes['Incubation Time (min)'].setValue(float(sequence.get('Incubation_Time_in_minute')))
            self.sequences[name].attributes['Post-Fill Fluidic Port'].setValue(float(0))
            self.sequences[name].attributes['Post-Fill Flow Time (s)'].setValue(float(0))
        for aspiration_setting in self.config_xml_tree_root.iter('aspiration_setting'):
            self.entry_aspiration_pump_power.setValue(float(aspiration_setting.get('Pump_Power')))
            self.entry_aspiration_time_s.setValue(float(aspiration_setting.get('Duration_Seconds')))

    def load_user_selected_sequence_settings(self):
        dialog = QFileDialog()
        filename, _filter = dialog.getOpenFileName(None,'Open File','.','XML files (*.xml)')
        if filename:
            self.config_filename = filename
            self.load_sequence_settings(filename)
            self.lineEdit_setting_file.setText(filename)

    def saveas_sequence_settings(self):
        dialog = QFileDialog()
        filename, _filter = dialog.getSaveFileName(None,'Save File','.','XML files (*.xml)')
        if filename:
            self.save_sequence_settings(filename)
            self.lineEdit_setting_file.setText(filename)
            self.config_filename = filename

    def save_sequence_settings(self,filename):
        # update the xml tree based on the current settings
        # sequence settings
        for sequence_name in self.sequences.keys():
            list_ = self.config_xml_tree_root.xpath("//sequence[contains(@Name," + "'" + str(sequence_name) + "')]")
            if list_:
                sequence_to_update = list_[0]
                sequence_to_update.set('Fluidic_Port',str(self.sequences[sequence_name].attributes['Fluidic Port'].value()))
                sequence_to_update.set('Repeat',str(self.sequences[sequence_name].attributes['Repeat'].value()))
                sequence_to_update.set('Incubation_Time_in_minute',str(self.sequences[sequence_name].attributes['Incubation Time (min)'].value()))
                sequence_to_update.set('Flow_Time_in_second',str(self.sequences[sequence_name].attributes['Flow Time (s)'].value()))
                sequence_to_update.set('Post_Fill_Fluidic_Port',str(self.sequences[sequence_name].attributes['Post-Fill Fluidic Port'].value()))
                sequence_to_update.set('Post_Flow_Time_in_second',str(self.sequences[sequence_name].attributes['Post-Fill Flow Time (s)'].value()))
        # aspiration settings
        list_ = self.config_xml_tree_root.xpath("//aspiration_setting")
        if list_:
            aspiration_setting = list_[0]
            aspiration_setting.set('Pump_Power',str(self.entry_aspiration_pump_power.value()))
            aspiration_setting.set('Duration_Seconds',str(self.entry_aspiration_time_s.value()))
        # save the configurations
        self.config_xml_tree.write(filename, encoding="utf-8", xml_declaration=True, pretty_print=True)
        print('sequence settings saved to ' + str(filename))    

    def run_sequences(self):
        # check if any sequence is selected
        at_least_one_sequence_is_selected = False
        for i in range(len(SEQUENCE_NAME)):
            current_sequence = self.sequences[SEQUENCE_NAME[i]]
            if current_sequence.attributes['Include'].isChecked() == True:
                at_least_one_sequence_is_selected = True
                break;
        if(at_least_one_sequence_is_selected is False):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("No sequence is selected")
            msg.setInformativeText("Check the \"include\" check box for sequences that you want to run")
            msg.setWindowTitle("Warning")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.setDefaultButton(QMessageBox.Ok)
            retval = msg.exec_()
            return

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to run the selected sequences")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.abort_requested = False
            self.disable_widgets_except_for_abort_btn() 
            # print a seperator for visuals
            self.log_message.emit('--------------------------------')
            # go through sequences and execute *selected* sequences
            counter = 0
            for i in range(len(SEQUENCE_NAME)):
                current_sequence = self.sequences[SEQUENCE_NAME[i]]
                if current_sequence.attributes['Include'].isChecked() == True:
                    for k in range(current_sequence.attributes['Repeat'].value()):
                        self.log_message.emit(utils.timestamp() + 'Add ' + SEQUENCE_NAME[i] + ', round ' + str(k+1) + ' to the queue')
                        QApplication.processEvents()
                        ################################################################
                        ##### let the backend fluidController execute the sequence #####
                        ################################################################
                        self.fluidController.add_sequence(
                            SEQUENCE_NAME[i],
                            current_sequence.attributes['Fluidic Port'].value(),
                            current_sequence.attributes['Flow Time (s)'].value(),
                            current_sequence.attributes['Incubation Time (min)'].value(),
                            current_sequence.attributes['Post-Fill Fluidic Port'].value(),
                            current_sequence.attributes['Post-Fill Flow Time (s)'].value(),
                            pressure_setting=None,
                            aspiration_pump_power=self.entry_aspiration_pump_power.value(),
                            aspiration_time_s=self.entry_aspiration_time_s.value(),
                            round_ = k)
                        counter = counter + 1
            if counter > 0:
                self.fluidController.start_sequence_execution()
        else:
            self.log_message.emit(utils.timestamp() + 'no action.')
            QApplication.processEvents()
    
    def run_sequence_at_port(self, hybridization_port, include_all = True):
        counter = 0
        for i in range(len(SEQUENCE_NAME)):
            current_sequence = self.sequences[SEQUENCE_NAME[i]]
            # If hybridizing, use the hybridization port
            if SEQUENCE_NAME[i] == 'Hybridize':
                fluidic_port = hybridization_port
            else:
                fluidic_port = current_sequence.attributes['Fluidic Port'].value()
            if (current_sequence.attributes['Include'].isChecked() == True) or include_all:
                for k in range(current_sequence.attributes['Repeat'].value()):
                    self.log_message.emit(utils.timestamp() + 'Add ' + SEQUENCE_NAME[i] + ', round ' + str(k+1) + ' to the queue')
                    QApplication.processEvents()
                        ################################################################
                        ##### let the backend fluidController execute the sequence #####
                        ################################################################
                    self.fluidController.add_sequence(
                        SEQUENCE_NAME[i],
                        fluidic_port,
                        current_sequence.attributes['Flow Time (s)'].value(),
                        current_sequence.attributes['Incubation Time (min)'].value(),
                        current_sequence.attributes['Post-Fill Fluidic Port'].value(),
                        current_sequence.attributes['Post-Fill Flow Time (s)'].value(),
                        pressure_setting=None,
                        aspiration_pump_power=self.entry_aspiration_pump_power.value(),
                        aspiration_time_s=self.entry_aspiration_time_s.value(),
                        round_ = k)
                    counter = counter + 1
        if counter > 0:
            self.fluidController.start_sequence_execution()
        return
        
    def request_to_abort_sequences(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click Abort to stop advancing to the next sequence")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Abort | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        retval = msg.exec_()
        if QMessageBox.Abort == retval:
            self.abort_requested = True
            self.fluidController.request_abort_sequences()
            self.log_message.emit(utils.timestamp() + 'Abort requested')
            QApplication.processEvents()
        else:
            pass

    def disable_widgets_except_for_abort_btn(self):
        self.signal_disable_manualControlWidget.emit()
        self.entry_aspiration_time_s.setEnabled(False)
        self.entry_aspiration_pump_power.setEnabled(False)
        self.tableWidget.setEnabled(False)
        self.lineEdit_setting_file.setEnabled(False)
        self.button_load.setEnabled(False)
        self.button_save.setEnabled(False)
        self.button_run.setEnabled(False)
        self.button_stop.setEnabled(True)
        QApplication.processEvents()

    def enable_widgets_except_for_abort_btn(self):
        self.entry_aspiration_time_s.setEnabled(True)
        self.entry_aspiration_pump_power.setEnabled(True)
        self.tableWidget.setEnabled(True)
        self.lineEdit_setting_file.setEnabled(True)
        self.button_load.setEnabled(True)
        self.button_save.setEnabled(True)
        self.button_run.setEnabled(True)
        self.button_stop.setEnabled(False)
        self.signal_enable_manualControlWidget.emit()
        QApplication.processEvents()

    def select_row_using_sequence_name(self,sequence_name):
        if sequence_name in self.row_number.keys():
            self.tableWidget.selectRow(self.row_number[sequence_name])

    def deselect_rows(self):
        self.tableWidget.clearSelection()

    def uncheck_all_sequences(self):
        for sequence_name in self.sequences.keys():
            self.sequences[sequence_name].attributes['Include'].setCheckState(Qt.Unchecked);

'''
#########################################################
#########   MCU -> Computer message structure   #########
#########################################################
byte 0-1    : computer -> MCU CMD counter (UID)
byte 2      : cmd from host computer (error checking through check sum => no need to transmit back the parameters associated with the command)
            <see below for command set>
byte 3      : status of the command
                - 1: in progress
                - 0: completed without errors
                - 2: error in cmd check sum
                - 3: invalid cmd
                - 4: error during execution
byte 4      : MCU internal program being executed
                - 0: idle
                <see below for command set>
byte 5      : state of valve A1,A2,B1,B2,bubble_sensor_1,bubble_sensor_2,x,x
byte 6      : state of valve C1-C7, manual input bit
byte 7-8    : pump power
byte 9-10   : pressure sensor 1 reading
byte 11-12  : pressure sensor 2 reading
byte 13-14  : flow sensor 1 reading
byte 15-16  : flow sensor 2 reading
byte 17-19  : reserved
'''

class MicrocontrollerStateDisplayWidget(QFrame):
    def __init__(self, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):
        self.label_MCU_CMD_UID = QLabel()
        self.label_CMD = QLabel()
        self.label_CMD_status = QLabel()
        self.label_MCU_internal_program = QLabel()
        self.label_MCU_CMD_time_elapsed = QLabel()

        self.label_pump_power = QLabel()
        self.label_selector_valve_position = QLabel()
        self.label_pressure = QLabel()
        self.label_vacuum = QLabel()
        self.label_bubble_sensor_upstream = QLabel()
        self.label_bubble_sensor_downstream = QLabel()

        self.label_flowrate_upstream = QLabel()
        self.label_dispensed_volume = QLabel()

        self.label_MCU_CMD_UID.setFixedWidth(50)
        self.label_CMD.setFixedWidth(30)
        self.label_CMD_status.setFixedWidth(50)
        self.label_MCU_internal_program.setFixedWidth(130)
        self.label_pump_power.setFixedWidth(50)
        self.label_selector_valve_position.setFixedWidth(30)
        self.label_pressure.setFixedWidth(50)
        self.label_vacuum.setFixedWidth(50)
        self.label_flowrate_upstream.setFixedWidth(50)
        self.label_dispensed_volume.setFixedWidth(50)

        self.label_MCU_CMD_UID.setFrameStyle(QFrame.Panel | QFrame.Sunken)        
        self.label_CMD.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.label_CMD_status.setFrameStyle(QFrame.Panel | QFrame.Sunken)        
        self.label_MCU_internal_program.setFrameStyle(QFrame.Panel | QFrame.Sunken) 
        self.label_MCU_CMD_time_elapsed.setFrameStyle(QFrame.Panel | QFrame.Sunken) 
        self.label_pump_power.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.label_selector_valve_position.setFrameStyle(QFrame.Panel | QFrame.Sunken)        
        self.label_pressure.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.label_vacuum.setFrameStyle(QFrame.Panel | QFrame.Sunken)        
        self.label_bubble_sensor_upstream.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.label_bubble_sensor_downstream.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.label_flowrate_upstream.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.label_dispensed_volume.setFrameStyle(QFrame.Panel | QFrame.Sunken)

        hbox1 = QHBoxLayout()
        hbox2 = QHBoxLayout()
        hbox3 = QHBoxLayout()
        # hbox4 = QHBoxLayout()

        tmp = QLabel('CMD UID')
        tmp.setFixedWidth(80)
        hbox1.addWidget(tmp)
        hbox1.addWidget(self.label_MCU_CMD_UID)

        tmp = QLabel('CMD')
        tmp.setFixedWidth(100)
        hbox1.addWidget(tmp)
        hbox1.addWidget(self.label_CMD)

        tmp = QLabel('CMD Status')
        tmp.setFixedWidth(80)
        hbox1.addWidget(tmp)
        hbox1.addWidget(self.label_CMD_status)

        tmp = QLabel('MCU Internal Program')
        hbox1.addWidget(tmp)
        hbox1.addWidget(self.label_MCU_internal_program)

        tmp = QLabel('Time Elapsed (s)')
        tmp.setFixedWidth(100)
        hbox1.addWidget(tmp)
        hbox1.addWidget(self.label_MCU_CMD_time_elapsed)
        hbox1.addStretch()

        tmp = QLabel('Pump Power')
        tmp.setFixedWidth(80)
        hbox2.addWidget(tmp)
        hbox2.addWidget(self.label_pump_power)

        tmp = QLabel('Rotary Valve Pos')
        tmp.setFixedWidth(100)
        hbox2.addWidget(tmp)
        hbox2.addWidget(self.label_selector_valve_position)
        #hbox2.addStretch()

        tmp = QLabel('Pressure (psi)')
        tmp.setFixedWidth(80)
        hbox2.addWidget(tmp)
        hbox2.addWidget(self.label_pressure)

        tmp = QLabel('Vacuum (psi)')
        tmp.setFixedWidth(80)
        hbox2.addWidget(tmp)
        hbox2.addWidget(self.label_vacuum)
        hbox2.addWidget(QLabel('Bubble Sensor (in)'))
        hbox2.addWidget(self.label_bubble_sensor_upstream) # 0 - liquid present
        hbox2.addWidget(QLabel('Bubble Sensor (out)'))
        hbox2.addWidget(self.label_bubble_sensor_downstream) # 0 - liquid present
        hbox2.addStretch()

        tmp = QLabel('Flow Rate (ul/min)')
        tmp.setFixedWidth(110)
        hbox3.addWidget(tmp)
        hbox3.addWidget(self.label_flowrate_upstream)
        tmp = QLabel('Dispensed Volume (ul)')
        tmp.setFixedWidth(140)
        hbox3.addWidget(tmp)
        hbox3.addWidget(self.label_dispensed_volume)
        hbox3.addStretch()

        vbox = QVBoxLayout()
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        vbox.addLayout(hbox3)
        self.setLayout(vbox)


class ManualFlushWidget(QFrame):

    log_message = Signal(str)

    def __init__(self, fluidController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fluidController = fluidController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):

        self.entry_volume_ul = QDoubleSpinBox()
        self.entry_volume_ul.setMinimum(0)
        self.entry_volume_ul.setMaximum(1000) 
        self.entry_volume_ul.setSingleStep(5)
        self.entry_volume_ul.setValue(0)

        self.entry_flowrate_ul_per_s = QDoubleSpinBox()
        self.entry_flowrate_ul_per_s.setMinimum(0) 
        self.entry_flowrate_ul_per_s.setMaximum(20) 
        self.entry_flowrate_ul_per_s.setSingleStep(0.1)
        self.entry_flowrate_ul_per_s.setValue(0)

        self.checkbox_bypass = QCheckBox('bypass')

        self.button_bleach = QPushButton('Bleach')
        self.button_bleach.clicked.connect(self.bleach)
        
        hbox = QHBoxLayout() 
        # hbox.addWidget(QLabel('[Manual Bleach]'))
        hbox.addWidget(QLabel('Volume (uL)'))
        hbox.addWidget(self.entry_volume_ul)
        hbox.addWidget(QLabel('Flowrate (uL/s)'))
        hbox.addWidget(self.entry_flowrate_ul_per_s)
        hbox.addWidget(self.checkbox_bypass)
        hbox.addWidget(self.button_bleach)
        self.setLayout(hbox)

    def bleach(self):
        if self.checkbox_bypass.isChecked() == True:
            bypass = BYPASS.TRUE
            flow_through = 'by pass'
        else:
            bypass = BYPASS.FALSE
            flow_through = 'flow cell'
        volume_ul = self.entry_volume_ul.value()
        flowrate_ul_per_s = self.entry_flowrate_ul_per_s.value()
        self.log_message.emit(utils.timestamp() + 'flow ' + str(volume_ul) + ' ul bleach through ' + flow_through + ' at ' + str(flowrate_ul_per_s) + ' ul/s.')
        QApplication.processEvents()
        self.fluidController.bleach(bypass,volume_ul,flowrate_ul_per_s)

'''
class SettingsWidget(QWidget):

    log_message = Signal(str)

    def __init__(self, fluidController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fluidController = fluidController
        self.add_components()

    def add_components(self):

        pass

        # setKeyboardTracking(False)
'''


class ManualControlWidget(QWidget):

    log_message = Signal(str)
    # signal_aspiration_time_s = Signal(float)
    # signal_aspiration_power = Signal(float)
    signal_disable_userinterface = Signal()
    signal_enable_userinterface = Signal()

    def __init__(self, fluidController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fluidController = fluidController
        self.add_components()
        # self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):

        # self.entry_selector_valve_position = QSpinBox()
        # self.entry_selector_valve_position.setMinimum(1)
        # self.entry_selector_valve_position.setMaximum(24)
        # self.entry_selector_valve_position.setFixedWidth(40)

        self.btn_enable_manual_control = QPushButton('Enable Control Through the Physical Knob and Switches')
        self.btn_enable_manual_control.setCheckable(True)
        self.btn_enable_manual_control.setChecked(True)
        self.btn_enable_manual_control.setDefault(False)

        self.dropdown_selector_valve_position = QComboBox()
        self.dropdown_selector_valve_position.addItem('')
        for i in range(24):
            self.dropdown_selector_valve_position.addItem(str(i+1))
        self.dropdown_selector_valve_position.setFixedWidth(70)

        # self.entry_10mm_solenoid_valve_selection = QSpinBox()
        # self.entry_10mm_solenoid_valve_selection.setMinimum(0)
        # self.entry_10mm_solenoid_valve_selection.setMaximum(16)
        # self.entry_10mm_solenoid_valve_selection.setFixedWidth(40)

        self.dropdown_10mm_solenoid_valve_selection = QComboBox()
        self.dropdown_10mm_solenoid_valve_selection.addItem('-')
        for i in range(16):
            self.dropdown_10mm_solenoid_valve_selection.addItem(str(i+1))
        self.dropdown_10mm_solenoid_valve_selection.setFixedWidth(70)

        self.btn_connect_selector_valve_to_chamber = QPushButton('Connect Selector Valve to Chamber')
        self.btn_connect_selector_valve_to_chamber.setCheckable(True)
        self.btn_connect_selector_valve_to_chamber.setChecked(False)
        self.btn_connect_selector_valve_to_chamber.setDefault(False)

        # pressure loop settings
        self.entry_p_gain = QDoubleSpinBox()
        self.entry_p_gain.setKeyboardTracking(False)
        self.entry_p_gain.setMinimum(0)
        self.entry_p_gain.setMaximum(PRESSURE_LOOP_COEFFICIENTS_FULL_SCALE)
        self.entry_p_gain.setDecimals(5)
        self.entry_p_gain.setSingleStep(0.01)
        self.entry_p_gain.setValue(DEFAULT_VALUES.pressure_loop_p_gain)

        self.entry_i_gain = QDoubleSpinBox()
        self.entry_i_gain.setKeyboardTracking(False)
        self.entry_i_gain.setMinimum(0)
        self.entry_i_gain.setMaximum(PRESSURE_LOOP_COEFFICIENTS_FULL_SCALE)
        self.entry_i_gain.setDecimals(5)
        self.entry_i_gain.setSingleStep(0.01)
        self.entry_i_gain.setValue(DEFAULT_VALUES.pressure_loop_p_gain)

        self.entry_pressure_setpoint_psi = QDoubleSpinBox()
        self.entry_pressure_setpoint_psi.setKeyboardTracking(False)
        self.entry_pressure_setpoint_psi.setMinimum(0)
        self.entry_pressure_setpoint_psi.setMaximum(5)
        self.entry_pressure_setpoint_psi.setDecimals(2)
        self.entry_pressure_setpoint_psi.setSingleStep(0.01)
        self.entry_pressure_setpoint_psi.setValue(0)

        self.btn_enable_pressure_loop = QPushButton('Enable Pressure Loop')
        self.btn_enable_pressure_loop.setCheckable(True)
        self.btn_enable_pressure_loop.setChecked(False)
        self.btn_enable_pressure_loop.setDefault(False)

        # # vaccum settings
        # self.entry_aspiration_pump_power = QDoubleSpinBox()
        # self.entry_aspiration_pump_power.setKeyboardTracking(False)
        # self.entry_aspiration_pump_power.setMinimum(0)
        # self.entry_aspiration_pump_power.setMaximum(1)
        # self.entry_aspiration_pump_power.setDecimals(3)
        # self.entry_aspiration_pump_power.setSingleStep(0.01)
        # self.entry_aspiration_pump_power.setValue(DEFAULT_VALUES.aspiration_pump_power)

        # self.entry_aspiration_time_s = QDoubleSpinBox()
        # self.entry_aspiration_time_s.setKeyboardTracking(False)
        # self.entry_aspiration_time_s.setMinimum(0)
        # self.entry_aspiration_time_s.setMaximum(PRESSURE_LOOP_COEFFICIENTS_FULL_SCALE)
        # self.entry_aspiration_time_s.setDecimals(2)
        # self.entry_aspiration_time_s.setSingleStep(0.01)
        # self.entry_aspiration_time_s.setValue(DEFAULT_VALUES.vacuum_aspiration_time_s)

        hbox0 = QHBoxLayout()
        tmp = QLabel('Enable Control Through the Physical Knob and Switches')
        hbox0.addWidget(tmp)
        hbox0.addWidget(self.btn_enable_manual_control)
        hbox0.addStretch()

        # tmp.setFixedWidth(190)
        # hbox0.addWidget(tmp)
        # hbox0.addWidget(self.dropdown_selector_valve_position)
        # hbox0.addStretch()

        hbox1 = QHBoxLayout()
        tmp = QLabel('Set Selector Valve Position To')
        tmp.setFixedWidth(190)
        hbox1.addWidget(tmp)
        hbox1.addWidget(self.dropdown_selector_valve_position)
        hbox1.addWidget(QLabel('(select a port will also turn on the corresponding 10 mm solenoid valve)'))
        hbox1.addStretch()

        hbox2 = QHBoxLayout()
        tmp = QLabel('Turn On 10mm Solenoid Valve #')
        tmp.setFixedWidth(190)
        hbox2.addWidget(tmp)
        hbox2.addWidget(self.dropdown_10mm_solenoid_valve_selection)
        hbox2.addWidget(QLabel('(select 1-16 to turn on one of the valves, enter 0 to turn off all the valves)'))
        hbox2.addStretch()

        hbox3 = QHBoxLayout()
        tmp = QLabel('Isolation Valve Control')
        # tmp.setFixedWidth(190)
        hbox3.addWidget(tmp)
        hbox3.addWidget(self.btn_connect_selector_valve_to_chamber)
        hbox3.addStretch()

        hbox4 = QHBoxLayout()
        tmp = QLabel('Pressure Loop Settings  p gain')
        # tmp.setFixedWidth(160)
        hbox4.addWidget(tmp)
        hbox4.addWidget(self.entry_p_gain)
        tmp = QLabel('i gain')
        tmp.setFixedWidth(40)
        hbox4.addWidget(tmp)
        hbox4.addWidget(self.entry_i_gain)
        hbox4.addStretch()

        hbox5 = QHBoxLayout()
        tmp = QLabel('Pressure set point (psi)')
        tmp.setFixedWidth(140)
        hbox5.addWidget(tmp)
        self.entry_pressure_setpoint_psi.setFixedWidth(60)
        hbox5.addWidget(self.entry_pressure_setpoint_psi)
        hbox5.addWidget(self.btn_enable_pressure_loop)
        hbox5.addStretch()

        # hbox6 = QHBoxLayout()
        # tmp = QLabel('Aspiration settings   Pump Power (0-1)')
        # tmp.setFixedWidth(200)
        # hbox6.addWidget(tmp)
        # hbox6.addWidget(self.entry_aspiration_pump_power)
        # tmp = QLabel('Duration (seconds)')
        # tmp.setFixedWidth(120)
        # hbox6.addWidget(tmp)
        # hbox6.addWidget(self.entry_aspiration_time_s)
        # hbox6.addStretch()

        ##################################
        ############# flush ##############
        ##################################
        # create and layout the checkboxes
        hbox_1 = QHBoxLayout()
        self.checkbox = {}
        for port_name in Port.keys():
            port = Port[port_name]
            if port_name == str(port):
                checkbox_text =  port_name
            else:
                checkbox_text = port_name + ' (' + str(port) + ')'
            self.checkbox[port_name] = QCheckBox(checkbox_text)
            self.checkbox[port_name].setChecked(True)
            hbox_1.addWidget(self.checkbox[port_name])

        # target pressure 
        self.entry_target_pressure = QDoubleSpinBox()
        self.entry_target_pressure.setMinimum(0)
        self.entry_target_pressure.setMaximum(5.0) 
        self.entry_target_pressure.setSingleStep(0.1)
        self.entry_target_pressure.setValue(DEFAULT_VALUES.pressure_setpoint_for_pumping_fluid_constant_pressure_mode)
        hbox_2 = QHBoxLayout()
        hbox_2.addWidget(QLabel('Flush Pressure Setpoint (psi)'))
        hbox_2.addWidget(self.entry_target_pressure)
        # hbox_2.addStretch()

        self.entry_flush_duration = QDoubleSpinBox()
        self.entry_flush_duration.setMinimum(0)
        self.entry_flush_duration.setMaximum(300) 
        self.entry_flush_duration.setSingleStep(0.1)
        self.entry_flush_duration.setValue(15)
        hbox_2.addWidget(QLabel('Flush Duration (s)'))
        hbox_2.addWidget(self.entry_flush_duration)
       
        # add buttons
        self.btn_flush = QPushButton('Flush')
        self.btn_flush.setCheckable(True)

        vbox_flush = QVBoxLayout()
        vbox_flush.addLayout(hbox_1)
        vbox_flush.addLayout(hbox_2)
        vbox_flush.addWidget(self.btn_flush)


        '''
        framedHbox0 = frameWidget(hbox0)
        framedHbox1 = frameWidget(hbox1)
        framedHbox2 = frameWidget(hbox2)
        framedHbox3 = frameWidget(hbox3)
        framedHbox4 = frameWidget(hbox4)
        framedHbox6 = frameWidget(hbox6)
        framedHbox5 = frameWidget(hbox5)
        hlayout = QHBoxLayout()
        hlayout.addWidget(framedHbox4)
        hlayout.addWidget(framedHbox5)
        
        vbox = QVBoxLayout()
        vbox.addWidget(framedHbox6)
        vbox.addWidget(QHLine())
        vbox.addLayout(hlayout)
        vbox.addWidget(QHLine())
        vbox.addWidget(framedHbox0)
        vbox.addWidget(framedHbox1)
        vbox.addWidget(framedHbox2)
        vbox.addWidget(framedHbox3)
        vbox.addWidget(QHLine())
        vbox.addStretch()
        '''

        # vlayout1 = QVBoxLayout()
        # vlayout1.addLayout(hbox6)
        # vlayout1_framed = frameWidget(vlayout1)

        framedHbox4 = frameWidget(hbox4)

        vlayout2 = QVBoxLayout()
        vlayout2.addLayout(hbox0)
        vlayout2.addLayout(hbox1)
        vlayout2.addLayout(hbox2)
        vlayout2.addLayout(hbox3)
        vlayout2.addLayout(hbox5)
        vlayout2_framed = frameWidget(vlayout2)
                
        vbox = QVBoxLayout()
        # vbox.addWidget(vlayout1_framed)
        vbox.addWidget(framedHbox4)
        vbox.addWidget(vlayout2_framed)
        vbox.addWidget(frameWidget(vbox_flush))
        vbox.addStretch()

        self.setLayout(vbox)

        self.dropdown_selector_valve_position.currentTextChanged.connect(self.update_selector_valve)
        self.dropdown_10mm_solenoid_valve_selection.currentTextChanged.connect(self.update_10mm_solenoid_valves)
        self.btn_enable_manual_control.clicked.connect(self.enable_manual_control)
        self.btn_connect_selector_valve_to_chamber.clicked.connect(self.update_isolation_valve)

        self.entry_pressure_setpoint_psi.valueChanged.connect(self.set_pressure_control_setpoint)
        self.entry_p_gain.valueChanged.connect(self.set_pressure_loop_p_coefficient)
        self.entry_i_gain.valueChanged.connect(self.set_pressure_loop_i_coefficient)
        self.btn_enable_pressure_loop.clicked.connect(self.enable_pressure_loop)

        self.btn_flush.clicked.connect(self.flush)
        self.fluidController.signal_sequences_execution_stopped.connect(self.enable_user_interface)        

    def update_selector_valve(self,pos_str):
        if pos_str != '':
            self.fluidController.add_sequence('Set Selector Valve Position',int(pos_str))
            self.fluidController.start_sequence_execution()
            # self.fluidController.add_sequence('Set 10 mm Valve State',int(pos_str))
            self.dropdown_10mm_solenoid_valve_selection.setCurrentText(pos_str)
        
    def update_10mm_solenoid_valves(self,pos_str):
        if pos_str == '-':
            self.fluidController.add_sequence('Set 10 mm Valve State',int(0))
            self.fluidController.start_sequence_execution()
        else:
            self.fluidController.add_sequence('Set 10 mm Valve State',int(pos_str))
            self.fluidController.start_sequence_execution()

    def update_isolation_valve(self,pressed):
        if pressed:
            self.fluidController.add_sequence('Connect Selector Valve and Chamber')
            self.fluidController.start_sequence_execution()
        else:
            self.fluidController.add_sequence('Disconnect Selector Valve and Chamber')
            self.fluidController.start_sequence_execution()

    def enable_manual_control(self,pressed):
        if pressed :
            self.fluidController.add_sequence('Enable Manual Control')
            self.fluidController.start_sequence_execution()
            self.btn_enable_pressure_loop.setChecked(False) # todo: check if this is also implemented in the firmware
            self.repaint()
        else:
            self.fluidController.add_sequence('Disable Manual Control')
            self.fluidController.start_sequence_execution()

    def enable_pressure_loop(self,pressed):
        if pressed :
            self.fluidController.add_sequence('Enable Pressure Control Loop')
            self.fluidController.start_sequence_execution()
            self.btn_enable_manual_control.setChecked(False)
            self.repaint()
        else:
            self.fluidController.add_sequence('Disable Pressure Control Loop')
            self.fluidController.start_sequence_execution()

    def set_pressure_control_setpoint(self,value):
        self.fluidController.add_sequence('Set Pressure Control Setpoint (psi)',pressure_setting=value)
        self.fluidController.start_sequence_execution()

    def set_pressure_loop_p_coefficient(self,value):
        self.fluidController.add_sequence('Set Pressure Loop P Coefficient',pressure_setting=value)
        self.fluidController.start_sequence_execution()

    def set_pressure_loop_i_coefficient(self,value):
        self.fluidController.add_sequence('Set Pressure Loop I Coefficient',pressure_setting=value)
        self.fluidController.start_sequence_execution()

    def uncheck_enable_manual_control_button(self):
        self.btn_enable_manual_control.setChecked(False)
        self.btn_connect_selector_valve_to_chamber.setChecked(False)
        self.btn_enable_pressure_loop.setChecked(False)
        self.dropdown_selector_valve_position.setCurrentText('')
        self.dropdown_10mm_solenoid_valve_selection.setCurrentText('-')

    # def set_aspiration_time(self,value):
    #     self.signal_aspiration_time_s.emit(value)

    # def set_aspiration_power(self,value):
    #     self.signal_aspiration_power.emit(value)

    def flush(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Confirm your action")
        msg.setInformativeText("Click OK to flush the selected lines")
        msg.setWindowTitle("Confirmation")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)

        retval = msg.exec_()
        if QMessageBox.Ok == retval:
            self.signal_disable_userinterface.emit()
            counter = 0
            for port_name in Port.keys():
                if(self.checkbox[port_name].isChecked()==True):
                    self.fluidController.add_sequence('Flush',Port[port_name],flow_time_s=10,pressure_setting=3)
                    counter = counter + 1
            if counter > 0:
                self.fluidController.start_sequence_execution()
                self.disable_user_interface()
            else:
                self.btn_flush.setChecked(False)

    def disable_user_interface(self):
        self.setEnabled(False)

    def enable_user_interface(self):
        self.setEnabled(True)
        self.btn_flush.setChecked(False)
        self.signal_enable_userinterface.emit()
        self.repaint()

class ChillerWidget(QFrame):

    log_message = Signal(str)

    def __init__(self, fluidController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fluidController = fluidController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):

        self.entry_temperature = QDoubleSpinBox()
        self.entry_temperature.setMinimum(0)
        self.entry_temperature.setMaximum(25) 
        self.entry_temperature.setSingleStep(1)
        self.entry_temperature.setValue(4)

        self.button_set_temp = QPushButton('Set Temperature')
        self.button_check_temp = QPushButton('Check Temperature')
        self.button_set_temp.clicked.connect(self.set_chiller_temperature)
        self.button_check_temp.clicked.connect(self.check_chiller_temperature)
        
        hbox = QHBoxLayout() 
        # hbox.addWidget(QLabel('[Chiller]'))
        hbox.addWidget(QLabel('Temperature (degree C)'))
        hbox.addWidget(self.entry_temperature)
        hbox.addWidget(self.button_set_temp)
        hbox.addWidget(self.button_check_temp)
        self.setLayout(hbox)

    def set_chiller_temperature(self):
        temperature = self.entry_temperature.value()
        self.log_message.emit(utils.timestamp() + 'set chiller temperature to ' + str(temperature) + ' degree C.')
        QApplication.processEvents()
        self.fluidController.set_chiller_temperature(temperature)

    def check_chiller_temperature(self):
        self.log_message.emit(utils.timestamp() + 'check chiller temperature.')
        QApplication.processEvents()
        self.fluidController.check_chiller_temperature()

class ArbitraryCommandWidget(QFrame):

    def __init__(self, fluidController, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fluidController = fluidController
        self.add_components()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def add_components(self):

        # Define widgets
        self.cmd = QSpinBox()
        self.cmd.setMaximum(255)  # 1 byte

        self.payload1 = QSpinBox()
        self.payload1.setMaximum(255)  # 1 byte

        self.payload2 = QSpinBox()
        self.payload2.setMaximum(255)  # 1 byte

        self.payload3 = QSpinBox()
        self.payload3.setMaximum(65535)  # 2 bytes

        self.payload4 = QSpinBox()
        self.payload4.setMaximum(2147483647)  # 4 bytes

        self.button = QPushButton('Submit')

        self.button.clicked.connect(self.on_submit)

        # Layout
        layout = QHBoxLayout()
        layout.addWidget(QLabel('CMD (1 byte):'))
        layout.addWidget(self.cmd)
        layout.addWidget(QLabel('Payload 1 (1 byte):'))
        layout.addWidget(self.payload1)
        layout.addWidget(QLabel('Payload 2 (1 byte):'))
        layout.addWidget(self.payload2)
        layout.addWidget(QLabel('Payload 3 (2 bytes):'))
        layout.addWidget(self.payload3)
        layout.addWidget(QLabel('Payload 4 (4 bytes):'))
        layout.addWidget(self.payload4)
        layout.addWidget(self.button)

        self.setLayout(layout)

    def on_submit(self):
        # Extract values
        cmd = self.cmd.value()
        payload1 = self.payload1.value()
        payload2 = self.payload2.value()
        payload3 = self.payload3.value()
        payload4 = self.payload4.value()

        print("CMD: ", cmd)
        print("Payload 1: ", payload1)
        print("Payload 2: ", payload2)
        print("Payload 3: ", payload3)
        print("Payload 4: ", payload4)
        self.fluidController.send_arbitrary_command(cmd,payload1,payload2,payload3,payload4)

def main():
    app = QApplication(sys.argv)

    main_widget = MainWidget()
    main_widget.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()



def main():
    app = QApplication(sys.argv)

    main_widget = MainWidget()
    main_widget.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()



class frameWidget(QFrame):

    def __init__(self, layout, main=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.setLayout(layout)

class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
