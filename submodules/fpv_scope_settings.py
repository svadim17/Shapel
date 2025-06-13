from PyQt5.QtWidgets import QDockWidget, QWidget, QHBoxLayout, QPushButton, QSpacerItem, QSizePolicy, QVBoxLayout, \
    QColorDialog, QDialog, QLabel, QSlider, QSpinBox, QGroupBox, QCheckBox, QLineEdit, QRadioButton
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QSignalMapper


class FpvScopeSettings(QDockWidget, QWidget):

    signal_manual_mode_state = pyqtSignal(bool)

    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_

        self.setWindowTitle('FPV Scope settings')
        self.setWidget(QWidget())

        self.main_layout = QHBoxLayout()  # create vertical layout for buttons
        self.main_layout.setAlignment(Qt.AlignLeft)
        self.widget().setLayout(self.main_layout)

        self.create_widgets()
        self.add_widgets_to_layout()

    def create_widgets(self):
        self.radio_btn_auto = QRadioButton('Auto mode')
        self.radio_btn_auto.setChecked(True)
        self.radio_btn_manual = QRadioButton('Manual mode')

        self.radio_btn_auto.toggled.connect(self.btn_radio_changed)
        self.radio_btn_manual.toggled.connect(self.btn_radio_changed)

        self.l_cur_freq = QLabel('Current frequency')
        self.le_cur_freq = QLineEdit()
        self.le_cur_freq.setReadOnly(True)
        self.le_cur_freq.setMaximumWidth(100)
        self.le_cur_freq.setText('5325')

    def add_widgets_to_layout(self):
        cur_freq_layout = QVBoxLayout()
        cur_freq_layout.setAlignment(Qt.AlignLeft)
        cur_freq_layout.addWidget(self.l_cur_freq)
        cur_freq_layout.addWidget(self.le_cur_freq)

        radio_layout = QVBoxLayout()
        radio_layout.addWidget(self.radio_btn_auto)
        radio_layout.addWidget(self.radio_btn_manual)

        self.main_layout.addLayout(radio_layout)
        self.main_layout.addSpacing(10)
        self.main_layout.addLayout(cur_freq_layout)

    def change_mode_on_manual(self, freq: str):
        self.radio_btn_manual.setChecked(True)
        self.le_cur_freq.setText(freq)
        self.logger.info('FPV Scope mode was changed on manual')

    def btn_radio_changed(self):
        if self.radio_btn_manual.isChecked():
            self.logger.info('FPV Scope mode was changed on manual')
            self.signal_manual_mode_state.emit(True)

        elif self.radio_btn_auto.isChecked():
            self.logger.info('FPV Scope mode was changed on auto')
            self.signal_manual_mode_state.emit(False)
