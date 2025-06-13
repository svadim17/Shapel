from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont


class CalibrationWindow(QDialog):

    def __init__(self, center_pos, sensivity_coeff):
        super().__init__()
        self.sensivity_coeff = sensivity_coeff
        self.setWindowTitle('Calibration settings')
        self.create_controls()
        self.add_widgets_to_layout()

    def create_controls(self):
        self.l_spb_calibration_time = QLabel('Calibration time (sec)')
        self.spb_calibration_time = QSpinBox()
        self.spb_calibration_time.setFixedSize(QSize(100, 40))
        self.spb_calibration_time.setRange(5, 120)
        self.spb_calibration_time.setSingleStep(5)

        self.btn_calibrate = QPushButton('Calibrate')

        self.progressBar = QProgressBar()
        self.progressBar.setFixedSize(300, 10)
        self.progressBar.setStyleSheet("border: 2px solid grey;")

    def change_value_progressBar(self, current_value, accum_numb_for_auto_thr):
        self.progressBar.setMaximum(accum_numb_for_auto_thr)
        if current_value == accum_numb_for_auto_thr:
            self.progressBar.setValue(0)
        else:
            self.progressBar.setValue(current_value)
            if self.progressBar.value() == accum_numb_for_auto_thr - 1:
                self.close()

    def add_widgets_to_layout(self):
        self.main_layout = QVBoxLayout()            # main window layout
        self.setLayout(self.main_layout)

        self.cntrls_layout = QHBoxLayout()          # controls layout

        self.spb_layout = QVBoxLayout()             # spinbox of count receives layout
        self.spb_layout.addWidget(self.l_spb_calibration_time, alignment=Qt.AlignCenter)
        self.spb_layout.addWidget(self.spb_calibration_time, alignment=Qt.AlignCenter)
        self.spb_layout.addStretch(0)

        self.cntrls_layout.addLayout(self.spb_layout)

        self.main_layout.addLayout(self.cntrls_layout)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.btn_calibrate, alignment=Qt.AlignCenter)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.progressBar, alignment=Qt.AlignCenter)

    def open_calibration_window(self):
        self.show()
