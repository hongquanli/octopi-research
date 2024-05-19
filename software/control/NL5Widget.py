import sys
from PyQt5.QtWidgets import QApplication, QWidget, QGridLayout, QVBoxLayout, QLabel, QDoubleSpinBox, QSpinBox, QPushButton, QCheckBox, QDialog, QDialogButtonBox
from PyQt5.QtCore import Qt


class NL5SettingsDialog(QDialog):
    def __init__(self, nl5):
        super().__init__()
        self.nl5 = nl5
        self.setWindowTitle("NL5 Settings")
        
        layout = QGridLayout()
        
        # Scan amplitude control
        layout.addWidget(QLabel("Scan Amplitude"), 0, 0)
        self.scan_amplitude_input = QDoubleSpinBox()
        self.scan_amplitude_input.setValue(self.nl5.scan_amplitude)
        layout.addWidget(self.scan_amplitude_input, 0, 1)
        
        # Offset X control
        layout.addWidget(QLabel("Offset X"), 1, 0)
        self.offset_x_input = QDoubleSpinBox()
        self.offset_x_input.setValue(self.nl5.offset_x)
        layout.addWidget(self.offset_x_input, 1, 1)
        
        # Bypass offset control
        layout.addWidget(QLabel("Bypass Offset"), 2, 0)
        self.bypass_offset_input = QDoubleSpinBox()
        self.bypass_offset_input.setValue(self.nl5.bypass_offset)
        layout.addWidget(self.bypass_offset_input, 2, 1)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 3, 0, 1, 2)
        
        self.setLayout(layout)

    def accept(self):
        self.nl5.set_scan_amplitude(self.scan_amplitude_input.value())
        self.nl5.set_offset_x(self.offset_x_input.value())
        self.nl5.set_bypass_offset(self.bypass_offset_input.value())
        self.nl5.save_settings()
        super().accept()


class NL5Widget(QWidget):
    def __init__(self, nl5):
        super().__init__()
        
        self.nl5 = nl5
        
        # Create layout
        layout = QGridLayout()
        
        # Exposure delay control
        layout.addWidget(QLabel("Exposure Delay"), 0, 0)
        self.exposure_delay_input = QSpinBox()
        self.exposure_delay_input.setValue(self.nl5.exposure_delay_ms)
        self.exposure_delay_input.valueChanged.connect(self.update_exposure_delay)
        layout.addWidget(self.exposure_delay_input, 0, 1, 1, 3)
        
        # Line speed control
        layout.addWidget(QLabel("Line Speed"), 1, 0)
        self.line_speed_input = QSpinBox()
        self.line_speed_input.setMaximum(10000)
        self.line_speed_input.setValue(self.nl5.line_speed)
        self.line_speed_input.valueChanged.connect(self.update_line_speed)
        layout.addWidget(self.line_speed_input, 1, 1)
        
        # FOV X control
        layout.addWidget(QLabel("FOV X"), 1, 2)
        self.fov_x_input = QSpinBox()
        self.fov_x_input.setMaximum(4000)
        self.fov_x_input.setValue(self.nl5.fov_x)
        self.fov_x_input.valueChanged.connect(self.update_fov_x)
        layout.addWidget(self.fov_x_input, 1, 3)

        # Bypass control
        self.bypass_button = QPushButton("Enable Bypass")
        self.bypass_button.setCheckable(True)
        self.bypass_button.toggled.connect(self.update_bypass)
        layout.addWidget(self.bypass_button, 2, 0, 1, 4)
        
        # Start acquisition button
        self.start_acquisition_button = QPushButton("Start Acquisition")
        self.start_acquisition_button.clicked.connect(self.nl5.start_acquisition)
        layout.addWidget(self.start_acquisition_button, 3, 0, 1, 4)

        # NL5 Settings button
        self.settings_button = QPushButton("NL5 Settings")
        self.settings_button.clicked.connect(self.show_settings_dialog)
        layout.addWidget(self.settings_button, 4, 0, 1, 4)
        
        self.setLayout(layout)
    
    def show_settings_dialog(self):
        dialog = NL5SettingsDialog(self.nl5)
        dialog.exec_()
    
    def update_bypass(self, checked):
        self.nl5.set_bypass(checked)
        self.start_acquisition_button.setEnabled(not checked)
    
    def update_exposure_delay(self, value):
        self.nl5.set_exposure_delay(value)
    
    def update_line_speed(self, value):
        self.nl5.set_line_speed(value)
    
    def update_fov_x(self, value):
        self.nl5.set_fov_x(value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    import NL5
    nl5 = NL5.NL5()
    widget = NL5Widget(nl5)
    widget.show()
    
    sys.exit(app.exec_())