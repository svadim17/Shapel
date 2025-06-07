import queue
import time
import os
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QWidget, QGridLayout, QApplication, QAction, QToolBar, QTabWidget, QSizePolicy, QSlider, \
    QPushButton
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt
from loguru import logger
import qdarktheme
import yaml
import sys
from submodules.settings import SettingsWidget
from submodules.connection import EmulationTread, TCPTread, PlayerTread, CtrlMode
from submodules.processing import Processor
from submodules.drons import DronsCtrlWidget
from submodules.radar import PowerLevelWidget
from submodules.peleng import PelengWidget
from submodules.calibration import CalibrationWindow
from submodules.fpv_video import FPVVideoWidget
from submodules.fpv_scope import FPVScopeWidget
from submodules.connection import (EmulationTread, TCPTread, PlayerTread, CtrlMode, SerialSpinTread)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        central_widget = QWidget(self)
        self.grid = QGridLayout(central_widget)
        self.setCentralWidget(central_widget)
        self.setWindowTitle('Shapelle v25.23.5')
        self.setWindowIcon(QIcon('assets/logo/logo.jpeg'))
        self.logger = logger

        self.settingsWidget = SettingsWidget(logger_=self.logger)

        self.init_widgets_status()
        self.calibrationWidget = CalibrationWindow(self.geometry().center(), self.settingsWidget.conf['sensivity_coeff'])
        self.create_actions()
        self.create_toolbar()

        self.processor = Processor(self.settingsWidget.conf, self.settingsWidget.conf_drons)
        self.init_dronesWidget()
        self.init_pelengWidget()
        if self.levelWidget_status:
            self.init_levelWidget()
        if self.fpvVideoWidget_status:
            self.init_fpvVideoWidget()
        if self.fpvScopeWidget_status:
            self.init_fpvScopeWidget()
        self.init_dataBase_logging()

        self.connection = None
        self.set_connection_type(self.settingsWidget.debug.cb_connection_type.currentText())
        self.link_events()

        self.add_widgets_to_grid()

    def init_widgets_status(self):
        self.dronesWidget_status = True
        self.pelengWidget_status = True
        self.levelWidget_status = bool(self.settingsWidget.conf['widgets']['levelWidget'])
        self.fpvVideoWidget_status = bool(self.settingsWidget.conf['widgets']['fpvVideoWidget'])
        self.fpvScopeWidget_status = bool(self.settingsWidget.conf['widgets']['fpvScopeWidget'])

        self.dronesWidget_show = True
        self.pelengWidget_show = True
        self.levelWidget_show = bool(self.settingsWidget.conf['widgets_show']['levelWidget'])
        self.fpvVideoWidget_show = bool(self.settingsWidget.conf['widgets_show']['fpvVideoWidget'])
        self.fpvScopeWidget_show = bool(self.settingsWidget.conf['widgets_show']['fpvScopeWidget'])

        self.DataBaseLog_flag = False

    def create_actions(self):
        self.act_start = QAction('Start')
        self.act_start.setIcon(QIcon(f'assets/icons/btn_start.png'))
        self.act_start.setCheckable(True)
        self.act_start.triggered.connect(self.change_connection_state)

        self.act_settings = QAction('Settings')
        self.act_settings.setIcon(QIcon(f'assets/icons/btn_settings.png'))
        self.act_settings.triggered.connect(self.settingsWidget.show)

        self.act_drones = QAction('Drones')
        self.act_drones.setIcon(QIcon(f'assets/icons/drones_on.png'))
        self.act_drones.triggered.connect(self.open_dronesWidget)

        self.act_peleng = QAction('Peleng')
        self.act_peleng.setIcon(QIcon(f'assets/icons/peleng_on.png'))
        self.act_peleng.triggered.connect(self.open_pelengWidget)

        if self.levelWidget_status:
            icon_state = '_on' if self.levelWidget_show else ''
            self.act_levels = QAction('Levels')
            self.act_levels.setIcon(QIcon(f'assets/icons/levels{icon_state}.png'))
            self.act_levels.triggered.connect(self.open_levelsWidget)

        if self.fpvVideoWidget_status:
            icon_state = '_on' if self.fpvVideoWidget_show else ''
            self.act_fpv_video = QAction('FPV Video')
            self.act_fpv_video.setIcon(QIcon(f'assets/icons/fpv_video{icon_state}.png'))
            self.act_fpv_video.triggered.connect(self.open_fpvVideoWidget)

        if self.fpvScopeWidget_status:
            icon_state = '_on' if self.fpvScopeWidget_show else ''
            self.act_fpv_scope = QAction('FPV Scope')
            self.act_fpv_scope.setIcon(QIcon(f'assets/icons/fpv_scope{icon_state}.png'))
            self.act_fpv_scope.triggered.connect(self.open_fpvScopeWidget)

        self.btn_auto_threshold = QPushButton()
        self.btn_auto_threshold.setIcon(QIcon(rf'assets/icons/refresh.png'))
        self.btn_auto_threshold.setFixedSize(28, 28)
        self.btn_auto_threshold.clicked.connect(self.calibrationWidget.open_calibration_window)

        self.act_sound = QAction('Sound')
        self.act_sound.setIcon(QIcon(f'assets/icons/sound_on.png'))
        self.act_sound.setCheckable(True)
        self.act_sound.triggered.connect(self.enable_sound)

    def create_toolbar(self):
        self.toolBar = QToolBar('Toolbar')
        self.toolBar.addAction(self.act_start)
        self.toolBar.addAction(self.act_settings)
        self.toolBar.addAction(self.act_drones)
        self.toolBar.addAction(self.act_peleng)
        if self.levelWidget_status:
            self.toolBar.addAction(self.act_levels)
        if self.fpvVideoWidget_status:
            self.toolBar.addAction(self.act_fpv_video)
        if self.fpvScopeWidget_status:
            self.toolBar.addAction(self.act_fpv_scope)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolBar.addWidget(spacer)
        self.toolBar.addAction(self.act_sound)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolBar)

        # Toolbar Threshold
        self.tool_bar_threshold = QToolBar('Threshold')
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.tool_bar_threshold)
        self.slider_threshold = QSlider(Qt.Vertical)
        self.slider_threshold.setMaximum(4000)
        self.slider_threshold.setValue(self.settingsWidget.conf['threshold'])
        slider_style = "QSlider::handle {width: 40px;}"  # change the size of a handle slider_threshold
        self.slider_threshold.setStyleSheet(slider_style)
        self.tool_bar_threshold.addWidget(self.slider_threshold)
        self.tool_bar_threshold.addWidget(self.btn_auto_threshold)

    def init_dronesWidget(self):
        self.dronesWidget = DronsCtrlWidget(self.settingsWidget.drons, int(self.settingsWidget.conf['threshold']))
        self.processor.sig_warning.connect(self.dronesWidget.change_btn_color)
        self.dronesWidget.signal_drons_config_changed.connect(lambda drons_conf:
                                                            self.settingsWidget.conf_drons.update(drons_conf))
        self.dronesWidget.signal_drons_config_changed.connect(lambda drons_conf: self.processor.update_gains(
            [list(drons_conf.values())[0].get('name')] + list(drons_conf.values())[0].get('gains')))
        self.dronesWidget.signal_drons_config_changed.connect(lambda drons_conf: self.connection.conf_drons.update(drons_conf))
        self.processor.sig_calibration_coeff.connect(self.dronesWidget.set_calibration)

    def init_pelengWidget(self):
        self.pelengWidget = PelengWidget(self.settingsWidget.conf, self.settingsWidget.conf_drons, self.logger)
        self.pelengWidget.change_view_levels_flag(self.settingsWidget.debug.chb_peleng_level.checkState())
        self.processor.sig_peleng.connect(self.pelengWidget.draw_peleng)
        self.settingsWidget.debug.chb_average_peleng.clicked.connect(self.processor.change_average_flag)
        self.slider_threshold.valueChanged.connect(self.pelengWidget.change_threshold)
        self.dronesWidget.signal_drons_config_changed.connect(lambda drons_conf:
                                                              self.pelengWidget.load_conf_drons(drons_conf))
        self.settingsWidget.debug.chb_peleng_level.clicked.connect(self.pelengWidget.change_view_levels_flag)

    def init_levelWidget(self):
        self.levelWidget = PowerLevelWidget(self.settingsWidget.conf, self.settingsWidget.conf_drons)
        self.processor.sig_sector_levels.connect(self.levelWidget.processing_data)
        self.slider_threshold.valueChanged.connect(self.levelWidget.change_threshold)
        self.dronesWidget.signal_drons_config_changed.connect(lambda drons_conf: self.levelWidget.load_conf_drons(drons_conf))

    def init_fpvVideoWidget(self):
        self.fpvVideoWidget = FPVVideoWidget(self.settingsWidget.connection.cb_camera.currentData(), self.logger)

    def init_fpvScopeWidget(self):
        self.fpvScopeWidget = FPVScopeWidget(freqs_dict=self.settingsWidget.configuration_conf['fpv_scope_frequencies'])

    def init_dataBase_logging(self):
        if not self.DataBaseLog_flag:
            from submodules.database_logging import DataBaseLog
            try:
                self.DataBaseLog
            except:
                self.DataBaseLog = DataBaseLog()
            if self.settingsWidget.debug.chb_database_log.checkState():
                self.processor.sig_warning_database.connect(self.DataBaseLog.append_table)
            self.DataBaseLog.signal_request_dataframe.connect(self.settingsWidget.database.receive_requested_data)
            self.DataBaseLog_flag = True
        else:
            try:
                self.processor.sig_warning_database.disconnect(self.DataBaseLog.append_table)
            except:
                pass
            self.DataBaseLog_flag = False

    def add_widgets_to_grid(self):
        self.tab_top_left = QTabWidget()
        self.tab_top_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.dronesWidget_status:
            self.dronesWidget_ind = self.tab_top_left.addTab(self.dronesWidget, 'Drones')
        self.grid.addWidget(self.tab_top_left, 0, 0, 1, 1, Qt.AlignTop)

        self.tab_medium_left = QTabWidget()
        self.tab_medium_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.fpvVideoWidget_status:
            self.fpvVideoWidget_ind = self.tab_medium_left.addTab(self.fpvVideoWidget, 'FPV Video')
        if self.fpvVideoWidget_ind is not None and not self.fpvVideoWidget_show:
            self.tab_medium_left.widget(self.fpvVideoWidget_ind).hide()
            self.tab_medium_left.setTabText(self.fpvVideoWidget_ind, "")
        self.grid.addWidget(self.tab_medium_left, 1, 0, 1, 1, Qt.AlignTop)

        self.tab_top_right = QTabWidget()
        self.tab_top_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if self.pelengWidget_status:
            self.pelengWidget_ind = self.tab_top_right.addTab(self.pelengWidget, 'Peleng')
        if self.levelWidget_status:
            self.levelWidget_ind = self.tab_top_right.addTab(self.levelWidget, 'Levels')
        if self.levelWidget_ind is not None and not self.levelWidget_show:
            self.tab_top_right.widget(self.levelWidget_ind).hide()
            self.tab_top_right.setTabText(self.levelWidget_ind, "")
        self.grid.addWidget(self.tab_top_right, 0, 1, 2, 2, Qt.AlignTop)

        if self.fpvScopeWidget_status and self.fpvScopeWidget_show:
            self.grid.addWidget(self.fpvScopeWidget, 2, 0, 1, 3, Qt.AlignTop)

    def open_dronesWidget(self):
        if self.dronesWidget_show:
            self.tab_top_left.widget(self.dronesWidget_ind).hide()
            self.tab_top_left.setTabEnabled(self.dronesWidget_ind, False)
            self.tab_top_left.setTabText(self.dronesWidget_ind, "")  # Или "Скрыто"
            self.act_drones.setIcon(QIcon(f'assets/icons/drones.png'))
            self.dronesWidget_show = False
        else:
            self.tab_top_left.widget(self.dronesWidget_ind).show()
            self.tab_top_left.setTabEnabled(self.dronesWidget_ind, True)
            self.tab_top_left.setTabText(self.dronesWidget_ind, "Drones")
            self.act_drones.setIcon(QIcon(f'assets/icons/drones_on.png'))
            self.dronesWidget_show = True

    def open_pelengWidget(self):
        if self.pelengWidget_show:
            self.tab_top_right.widget(self.pelengWidget_ind).hide()
            self.tab_top_right.setTabEnabled(self.pelengWidget_ind, False)
            self.tab_top_right.setTabText(self.pelengWidget_ind, "")  # Или "Скрыто"
            self.act_peleng.setIcon(QIcon(f'assets/icons/peleng.png'))
            self.pelengWidget_show = False
        else:
            self.tab_top_right.widget(self.pelengWidget_ind).show()
            self.tab_top_right.setTabEnabled(self.pelengWidget_ind, True)
            self.tab_top_right.setTabText(self.pelengWidget_ind, "Peleng")
            self.act_peleng.setIcon(QIcon(f'assets/icons/peleng_on.png'))
            self.pelengWidget_show = True

    def open_levelsWidget(self):
        if self.levelWidget.isVisible():
            self.tab_top_right.widget(self.levelWidget_ind).hide()
            self.tab_top_right.setTabEnabled(self.levelWidget_ind, False)
            self.tab_top_right.setTabText(self.levelWidget_ind, "")  # Или "Скрыто"
            self.act_levels.setIcon(QIcon(f'assets/icons/levels.png'))
            self.levelWidget_show = False
        else:
            self.tab_top_right.widget(self.levelWidget_ind).show()
            self.tab_top_right.setTabEnabled(self.levelWidget_ind, True)
            self.tab_top_right.setTabText(self.levelWidget_ind, "Levels")
            self.act_levels.setIcon(QIcon(f'assets/icons/levels_on.png'))
            self.levelWidget_show = True

    def open_fpvVideoWidget(self):
        if self.fpvVideoWidget.isVisible():
            self.tab_medium_left.widget(self.fpvVideoWidget_ind).hide()
            self.tab_medium_left.setTabEnabled(self.fpvVideoWidget_ind, False)
            self.tab_medium_left.setTabText(self.fpvVideoWidget_ind, "")  # Или "Скрыто"
            self.act_fpv_video.setIcon(QIcon(f'assets/icons/fpv_video.png'))
            self.fpvVideoWidget_show = False
        else:
            self.tab_medium_left.widget(self.fpvVideoWidget_ind).show()
            self.tab_medium_left.setTabEnabled(self.fpvVideoWidget_ind, True)
            self.tab_medium_left.setTabText(self.fpvVideoWidget_ind, "FPV Video")
            self.act_fpv_video.setIcon(QIcon(f'assets/icons/fpv_video_on.png'))
            self.fpvVideoWidget_show = True

    def open_fpvScopeWidget(self):
        if self.fpvScopeWidget.isVisible():
            self.grid.removeWidget(self.fpvScopeWidget)
            self.fpvScopeWidget.setParent(None)
            self.act_fpv_scope.setIcon(QIcon(f'assets/icons/fpv_scope.png'))
            self.fpvScopeWidget_show = False
        else:
            self.grid.addWidget(self.fpvScopeWidget, 2, 0, 1, 3)
            self.act_fpv_scope.setIcon(QIcon(f'assets/icons/fpv_scope_on.png'))
            self.fpvScopeWidget_show = True

    def set_connection_type(self, mode='emulation'):
        if self.connection is not None:
            self.connection.close()
        try:
            frequencies =[self.settingsWidget.conf_drons[key]['frequency'] for key in self.settingsWidget.conf_drons]
            if mode == 'emulation' or mode == 'Emulation':
                self.connection = EmulationTread(len(self.settingsWidget.conf_drons.keys()),
                                                 self.settingsWidget.connection.spb_timeout.value())
            elif mode == 'tcp' or mode == 'TCP' or mode == 'Tcp':
                self.connection = TCPTread(calibration_coeff=self.settingsWidget.conf['calibration_coefficients'],
                                           frequencies=frequencies,
                                           thread_timeout=self.settingsWidget.connection.spb_timeout.value(),
                                           logger_=self.logger)
            elif mode == 'player' or mode == 'Player':
                self.connection = PlayerTread(number_of_drons=len(self.settingsWidget.conf_drons.keys()),
                                              record=self.settingsWidget.conf['debug']['player_record'],
                                              thread_timeout=self.settingsWidget.connection.spb_timeout.value(),
                                              logger_=self.logger)
                self.settingsWidget.debug.cb_record.currentTextChanged.connect(self.connection.record_changed)
            else:
                self.connection = EmulationTread(number_of_drons=len(self.settings.conf_drons.keys()),
                                                 thread_timeout=self.settings.connection.spb_timeout.value(),
                                                 logger_=self.logger)
            self.logger.info(f'Initialized {mode} connection.')
        except Exception as e:
            self.logger.error(f'Error with open {mode} connection: {e}')
        self.connection.signal_levels.connect(self.processor.receive_levels)

    def change_connection_state(self, status: bool):
        if status:
            self.act_start.setIcon(QIcon(f'assets/icons/btn_stop.png'))
            self.levelWidget.clear_plot()
            try:
                if self.settingsWidget.debug.cb_connection_type.currentText() == 'TCP':
                    self.connection.open(self.settingsWidget.connection.le_ip_address.text(),
                                         self.settingsWidget.connection.cb_port_numb.currentText())
                else:
                    self.connection.open(self.settingsWidget.connection.cb_port_numb.currentText())
            except Exception as e:
                self.logger.error(f'No connection with {self.settingsWidget.connection.cb_port_numb.currentText()}\n{e}')
        else:
            self.act_start.setIcon(QIcon(f'assets/icons/btn_start.png'))
            self.connection.close()

    def link_events(self):
        self.processor.sig_auto_threshold.connect(self.change_threshold)
        self.processor.sig_progrBar_value.connect(self.calibrationWidget.change_value_progressBar)

        self.slider_threshold.valueChanged.connect(self.processor.change_threshold)
        self.slider_threshold.valueChanged.connect(lambda threshold: self.settingsWidget.conf.update({'threshold': threshold}))
        self.slider_threshold.valueChanged.connect(self.connection.threshold_changed)

        # Threshold signals for TCP connection
        self.connection.signal_threshold.connect(self.processor.change_threshold)
        self.connection.signal_threshold.connect(self.change_threshold)
        self.connection.signal_threshold.connect(lambda threshold: self.settingsWidget.conf.update({'threshold': threshold}))

        # Calibration coefficients signal for TCP connection
        self.connection.signal_calibration.connect(self.dronesWidget.set_calibration)

        # Drons gains signal for TCP connection
        self.connection.signal_drons_gains.connect(self.processor.update_gains)
        self.connection.signal_drons_gains.connect(self.dronesWidget.update_gains)

        self.settingsWidget.debug.cb_connection_type.currentTextChanged.connect(self.set_connection_type)
        self.settingsWidget.connection.spb_timeout.valueChanged.connect(self.connection.set_timeout)
        self.settingsWidget.connection.btn_send_detect_settings.clicked.connect(self.connection.send_detect_settings)
        self.settingsWidget.connection.btn_receive_detect_settings.clicked.connect(self.connection.receive_detect_settings)
        self.settingsWidget.connection.cb_camera.currentTextChanged.connect(lambda: self.fpvVideoWidget.change_camera(
            self.settingsWidget.connection.cb_camera.currentData()))
        self.settingsWidget.debug.chb_database_log.stateChanged.connect(self.database_log_changed)

        self.settingsWidget.database.btn_search.clicked.connect(lambda: self.DataBaseLog.get_data_from_database(
                                        cur_date=self.settingsWidget.database.calendar.selectedDate().toString("yyyy-MM-dd"),
                                        cur_time=self.settingsWidget.database.cb_time.currentData()))

        self.btn_auto_threshold.clicked.connect(self.calibrationWidget.open_calibration_window)
        self.calibrationWidget.btn_calibrate.clicked.connect(self.processor.reset_receive_counter)
        self.calibrationWidget.spb_calibration_time.setValue(self.processor.calibration_time)
        self.calibrationWidget.spb_calibration_time.valueChanged.connect(self.processor.change_calibration_time)
        self.calibrationWidget.cntrl_sensivity.valueChanged.connect(lambda coeff:
                                                                     self.settingsWidget.conf.update({'sensivity_coeff': coeff}))
        self.calibrationWidget.cntrl_sensivity.valueChanged.connect(self.processor.change_sensivity_coeff)

    def change_threshold(self, value):
        self.slider_threshold.setValue(value)

    def enable_sound(self, status: bool):
        if status:
            self.act_sound.setIcon(QIcon(rf'assets/icons/sound_on.png'))
        else:
            self.act_sound.setIcon(QIcon(rf'assets/icons/sound_off.png'))
        self.settingsWidget.debug.sound_flag_changed(status)

    def database_log_changed(self, status):
        if status:
            self.init_dataBase_logging()
            # self.processor.sig_warning_database.connect(self.DataBaseLog.append_table)
        else:
            self.processor.sig_warning_database.disconnect(self.DataBaseLog.append_table)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    qdarktheme.setup_theme(theme='dark')
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
