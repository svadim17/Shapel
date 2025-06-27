from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon


class FPVScopeModeWindow(QDialog):
    signal_manual_mode_chosen = pyqtSignal(bool)
    signal_increase_threshold = pyqtSignal(bool)

    def __init__(self, wait_time: int):
        super().__init__()
        self.setWindowTitle(self.tr('Detected FPV'))
        self.setWindowIcon(QIcon('./assets/icons/warning.png'))
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.main_layout = QVBoxLayout()            # main window layout
        self.main_layout.setAlignment(Qt.AlignTop)
        self.setLayout(self.main_layout)

        self.wait_time = wait_time          # in seconds
        self.current_value = 0                  # Счетчик времени
        self.timer = QTimer(self)               # Таймер для обновления прогресс-бара
        self.timer.timeout.connect(self.update_progress)

        self.create_controls()
        self.add_widgets_to_layout()

    def create_controls(self):
        self.btn_increase_thr = QPushButton(self.tr('Increase threshold'))
        self.btn_increase_thr.clicked.connect(self.btn_increase_thr_clicked)
        self.btn_increase_thr.setFocusPolicy(Qt.NoFocus)
        self.btn_increase_thr.setMaximumWidth(220)
        self.btn_increase_thr.setMinimumWidth(180)

        self.btn_auto_mode = QPushButton(self.tr('Continue scanning'))
        self.btn_auto_mode.clicked.connect(self.btn_auto_mode_clicked)
        self.btn_auto_mode.setFocusPolicy(Qt.NoFocus)
        self.btn_auto_mode.setMaximumWidth(220)
        self.btn_auto_mode.setMinimumWidth(180)

        self.btn_manual_mode = QPushButton(self.tr('Manual channels settings'))
        self.btn_manual_mode.clicked.connect(self.btn_manual_mode_clicked)
        self.btn_manual_mode.setFocusPolicy(Qt.NoFocus)
        self.btn_manual_mode.setMaximumWidth(220)
        self.btn_manual_mode.setMinimumWidth(180)

        self.progressBar = QProgressBar()
        self.progressBar.setFixedSize(300, 15)
        self.progressBar.setStyleSheet("border: 2px solid grey;")
        self.progressBar.setMaximum(self.wait_time)

    def add_widgets_to_layout(self):
        self.main_layout.addWidget(self.btn_increase_thr, alignment=Qt.AlignCenter)
        self.main_layout.addWidget(self.btn_auto_mode, alignment=Qt.AlignCenter)
        self.main_layout.addWidget(self.btn_manual_mode, alignment=Qt.AlignCenter)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.progressBar, alignment=Qt.AlignCenter)

    def change_wait_time(self, value: int):
        self.wait_time = value
        self.progressBar.setMaximum(self.wait_time)

    def update_progress(self):
        self.current_value += 1
        remaining = self.wait_time - self.current_value
        self.progressBar.setValue(self.current_value)
        self.progressBar.setFormat(self.tr(f'{remaining}...'))

        if self.current_value >= self.wait_time:
            self.timer.stop()
            self.signal_manual_mode_chosen.emit(False)
            self.close()

    def btn_increase_thr_clicked(self):
        self.timer.stop()
        self.signal_increase_threshold.emit(True)
        self.signal_manual_mode_chosen.emit(False)
        self.close()

    def btn_auto_mode_clicked(self):
        self.timer.stop()
        self.signal_manual_mode_chosen.emit(False)
        self.close()

    def btn_manual_mode_clicked(self):
        self.timer.stop()
        self.signal_manual_mode_chosen.emit(True)
        self.close()

    def open_window(self):
        self.current_value = 0
        self.progressBar.setMaximum(self.wait_time)
        self.progressBar.setMinimum(0)
        self.progressBar.setValue(0)
        self.progressBar.setFormat(self.tr(f'{self.wait_time}...'))
        self.timer.start(1000)
        self.show()
