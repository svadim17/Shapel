from PyQt5.QtWidgets import QDockWidget, QWidget, QHBoxLayout, QPushButton, QSpacerItem, QSizePolicy, QVBoxLayout, \
    QColorDialog, QDialog, QLabel, QSlider, QSpinBox, QGroupBox, QCheckBox, QLineEdit, QRadioButton
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QSignalMapper


class FpvScopeSettings(QDockWidget, QWidget):
    signal_manual_mode_state = pyqtSignal(bool)
    signal_fpvScope_mode = pyqtSignal(str, int)

    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_

        self.setWindowTitle(self.tr('FPV Scope settings'))
        self.setWidget(QWidget())

        self.main_layout = QHBoxLayout()  # create vertical layout for buttons
        self.main_layout.setAlignment(Qt.AlignLeft)
        self.widget().setLayout(self.main_layout)

        self.manual_mode = False

        self.create_widgets()
        self.add_widgets_to_layout()

    def create_widgets(self):
        self.radio_btn_auto = QRadioButton(self.tr('Auto mode'))
        self.radio_btn_auto.setChecked(True)
        self.radio_btn_manual = QRadioButton(self.tr('Manual mode'))

        self.radio_btn_auto.toggled.connect(self.btn_radio_changed)
        self.radio_btn_manual.toggled.connect(self.btn_radio_changed)

        self.l_cur_freq = QLabel(self.tr('Current frequency'))
        self.le_cur_freq = QLineEdit()
        self.le_cur_freq.setReadOnly(True)
        self.le_cur_freq.setMaximumWidth(100)
        self.le_cur_freq.setText('5325')

        self.l_delay_on_max = QLabel(self.tr('Delay on max [s]'))
        self.spb_delay_on_max = QSpinBox()
        self.spb_delay_on_max.setFixedSize(QSize(100, 40))
        self.spb_delay_on_max.setRange(1, 15)
        self.spb_delay_on_max.setValue(5)
        self.spb_delay_on_max.setSingleStep(1)

    def add_widgets_to_layout(self):
        radio_layout = QVBoxLayout()
        radio_layout.addWidget(self.radio_btn_auto)
        radio_layout.addWidget(self.radio_btn_manual)

        cur_freq_layout = QVBoxLayout()
        cur_freq_layout.setAlignment(Qt.AlignLeft)
        cur_freq_layout.addWidget(self.l_cur_freq)
        cur_freq_layout.addWidget(self.le_cur_freq)

        delay_on_max_layout = QVBoxLayout()
        delay_on_max_layout.addWidget(self.l_delay_on_max)
        delay_on_max_layout.addWidget(self.spb_delay_on_max)

        self.main_layout.addLayout(radio_layout)
        self.main_layout.addSpacing(10)
        self.main_layout.addLayout(delay_on_max_layout)
        self.main_layout.addSpacing(10)
        self.main_layout.addLayout(cur_freq_layout)

    def change_mode_on_manual(self, index: int, freq: str):
        self.radio_btn_manual.setChecked(True)
        self.le_cur_freq.setText(freq)
        self.manual_mode = True
        self.signal_fpvScope_mode.emit('manual', index)
        self.logger.info('FPV Scope mode was changed on manual')

    def btn_radio_changed(self):
        if self.radio_btn_manual.isChecked():
            self.manual_mode = True
            self.signal_manual_mode_state.emit(True)
            self.signal_fpvScope_mode.emit('manual', 0)
        elif self.radio_btn_auto.isChecked():
            self.signal_manual_mode_state.emit(False)
            self.signal_fpvScope_mode.emit('auto', 0)
            self.manual_mode = False

    def change_radio_button_on_auto(self, status: bool):
        if status:
            self.radio_btn_auto.setChecked(True)
        else:
            self.radio_btn_manual.setChecked(True)

