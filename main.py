import queue
import time
import os
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QWidget, QGridLayout, QApplication, QAction, QToolBar, QTabWidget, QSizePolicy, QSlider, \
    QPushButton, QDockWidget, QVBoxLayout, QMainWindow, QSplashScreen
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import Qt, QTranslator
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
from submodules.fpv_scope_settings import FpvScopeSettings
from submodules.record_calibration import RecordCalibration
from submodules.connection import (EmulationTread, TCPTread, PlayerTread, CtrlMode, SerialSpinTread)
from submodules.database_logging import DataBaseLog


# for handler_id in list(logger._core.handlers.keys()):
#     logger.remove(handler_id)
# log_format = ("<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | {extra} | <yellow>Line {line: >4} ({file}):</yellow> <b>{message}</b>")
# # logger.add(sys.stderr, format=log_format, colorize=True, backtrace=True, diagnose=True)
# logger.add("application_logs/file_{time}.log",
#            level="TRACE",
#            format=log_format,
#            colorize=False,
#            backtrace=True,
#            diagnose=True,
#            rotation='10 MB',
#            retention='14 days',
#            enqueue=True)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle('Shapel v25.28.4')
        self.setWindowIcon(QIcon('assets/logo/logo.jpeg'))
        self.logger = logger

        # Минимизируем центральный виджет
        central_widget = QWidget()
        self.main_layout = QVBoxLayout()
        central_widget.setLayout(self.main_layout)
        central_widget.setFixedWidth(0)
        central_widget.setMinimumHeight(0)

        central_widget.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self.setCentralWidget(central_widget)

        # Включаем вложенное размещение и разделители
        self.setDockNestingEnabled(True)
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)

        self.settingsWidget = SettingsWidget(logger_=self.logger)

        self.init_widgets_status()
        self.calibrationWidget = CalibrationWindow(self.geometry().center(), self.settingsWidget.conf['sensivity_coeff'])
        self.create_actions()
        self.create_toolbar()
        self.create_threshold_dock()

        self.processor = Processor(self.settingsWidget.conf, self.settingsWidget.conf_drons, self.logger)
        self.init_dronesWidget()
        self.init_pelengWidget()
        if self.levelWidget_status:
            self.init_levelWidget()
        if self.fpvVideoWidget_status:
            self.init_fpvVideoWidget()
        if self.fpvScopeWidget_status:
            self.init_fpvScopeWidget()
        if self.recordCalibrationWidget_status:
            self.init_recordCalibrationWidget()
        if self.settingsConfiguration_status:
            self.init_settingsConfiguration()
        if self.settingsAdminWidget_status:
            self.init_settingsAdminWidget()
        self.init_dataBase_logging()

        self.connection = None
        self.set_connection_type(self.settingsWidget.debug.cb_connection_type.currentText())
        self.link_events()

        self.add_widgets_to_window()

    def init_widgets_status(self):
        self.dronesWidget_status = True
        self.pelengWidget_status = True
        self.levelWidget_status = bool(self.settingsWidget.conf['widgets']['levelWidget'])
        self.fpvVideoWidget_status = bool(self.settingsWidget.conf['widgets']['fpvVideoWidget'])
        self.fpvScopeWidget_status = bool(self.settingsWidget.conf['widgets']['fpvScopeWidget'])
        self.recordCalibrationWidget_status = bool(self.settingsWidget.conf['widgets']['recordCalibrationWidget'])
        self.settingsConfiguration_status = bool(self.settingsWidget.conf['widgets']['settingsConfiguration'])
        self.settingsAdminWidget_status = bool(self.settingsWidget.conf['widgets']['settingsAdministrator'])

    def create_actions(self):
        self.act_start = QAction(self.tr('Start'))
        self.act_start.setIcon(QIcon(f'assets/icons/btn_start.png'))
        self.act_start.setCheckable(True)
        self.act_start.triggered.connect(self.change_connection_state)

        self.act_settings = QAction(self.tr('Settings'))
        self.act_settings.setIcon(QIcon(f'assets/icons/btn_settings.png'))
        self.act_settings.triggered.connect(self.settingsWidget.show)

        self.btn_auto_threshold = QPushButton()
        self.btn_auto_threshold.setIcon(QIcon(rf'assets/icons/refresh.png'))
        self.btn_auto_threshold.setFixedSize(28, 28)
        self.btn_auto_threshold.clicked.connect(self.calibrationWidget.open_calibration_window)

        self.act_sound = QAction(self.tr('Sound'))
        self.act_sound.setIcon(QIcon(f'assets/icons/sound_on.png'))
        self.act_sound.setCheckable(True)
        self.act_sound.triggered.connect(self.enable_sound)

    def create_toolbar(self):
        self.toolBar = QToolBar(self.tr('Toolbar'))
        self.toolBar.addAction(self.act_start)
        self.toolBar.addAction(self.act_settings)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolBar.addWidget(spacer)
        self.toolBar.addAction(self.act_sound)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolBar)

    def create_threshold_dock(self):
        # Toolbar Threshold
        self.thresholdDock = QDockWidget()
        self.thresholdDock.setTitleBarWidget(QWidget())
        self.thresholdDock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.thresholdDock.setMaximumWidth(30)

        slider_container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        slider_container.setLayout(layout)
        self.slider_threshold = QSlider(Qt.Vertical)
        self.slider_threshold.setMaximum(4000)
        self.slider_threshold.setValue(self.settingsWidget.conf['threshold'])
        slider_style = "QSlider::handle {width: 40px;}"  # change the size of a handle slider_threshold
        self.slider_threshold.setStyleSheet(slider_style)
        self.slider_threshold.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.btn_auto_threshold.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        layout.addWidget(self.slider_threshold)
        layout.addWidget(self.btn_auto_threshold)
        self.thresholdDock.setWidget(slider_container)

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
        self.processor.sig_fpvPeleng.connect(self.pelengWidget.draw_fpvPeleng)
        # self.processor.sig_warning.connect(self.pelengWidget.change_background_color)
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
        self.settingsWidget.connection.cb_camera.currentTextChanged.connect(lambda: self.fpvVideoWidget.change_camera(
            self.settingsWidget.connection.cb_camera.currentData()))

    def init_fpvScopeWidget(self):
        self.fpvScopeSettingsWidget = FpvScopeSettings(self.logger)
        self.fpvScopeWidget = FPVScopeWidget(self.settingsWidget.configuration_conf,
                                             self.fpvScopeSettingsWidget.spb_delay_on_max.value(),
                                             self.logger)

        self.settingsWidget.btn_dump_conf.clicked.connect(self.fpvScopeWidget.dump_configuration_conf)
        self.fpvScopeWidget.signal_freq_point_clicked.connect(self.fpvScopeSettingsWidget.change_mode_on_manual)
        self.fpvScopeWidget.signal_exceed_threshold.connect(self.settingsWidget.debug.event_play_analog_sound)
        self.fpvScopeSettingsWidget.signal_manual_mode_state.connect(self.fpvScopeWidget.change_mode_on_manual)
        self.fpvScopeSettingsWidget.spb_delay_on_max.valueChanged.connect(self.fpvScopeWidget.fpvModeWidnow.change_wait_time)

    def init_recordCalibrationWidget(self):
        self.recordCalibrationWidget = RecordCalibration(self.settingsWidget.conf, self.settingsWidget.conf_drons, self.logger)

    def init_settingsConfiguration(self):
        self.settingsWidget.tabWidget.addTab(self.settingsWidget.configuration, self.tr('Configuration'))

    def init_settingsAdminWidget(self):
        self.settingsWidget.tabWidget.addTab(self.settingsWidget.administrator, self.tr('Administrator'))

    def init_dataBase_logging(self):
        self.DataBaseLog = DataBaseLog()
        self.processor.sig_warning_database.connect(self.DataBaseLog.append_table)
        self.DataBaseLog.signal_request_dataframe.connect(self.settingsWidget.database.receive_requested_data)

    def add_widgets_to_window(self):
        # Peleng и Levels (верхний правый)
        self.pelengWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.pelengWidget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.pelengWidget.setMinimumWidth(600)
        self.addDockWidget(Qt.RightDockWidgetArea, self.pelengWidget)

        # Drones (верхний левый)
        self.dronesWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.dronesWidget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.dronesWidget.setMaximumWidth(200)  # Максимальная ширина для гибкости
        self.addDockWidget(Qt.RightDockWidgetArea, self.dronesWidget)
        self.splitDockWidget(self.pelengWidget, self.dronesWidget, Qt.Horizontal)  # Размещаем справа от pelengWidget

        # FPV Video (средний левый, если включено) и FPV Scope Settings
        if self.fpvVideoWidget_status:
            self.fpvVideoWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.fpvVideoWidget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.fpvVideoWidget.setMinimumWidth(300)
            self.fpvVideoWidget.setMinimumHeight(300)
            self.addDockWidget(Qt.LeftDockWidgetArea, self.fpvVideoWidget)

        if self.recordCalibrationWidget_status:
            self.recordCalibrationWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.recordCalibrationWidget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.recordCalibrationWidget.setMaximumWidth(500)
            if self.fpvVideoWidget_status:
                self.tabifyDockWidget(self.fpvVideoWidget, self.recordCalibrationWidget)
            else:
                self.addDockWidget(Qt.LeftDockWidgetArea, self.recordCalibrationWidget)

        # Threshold Dock
        self.addDockWidget(Qt.RightDockWidgetArea, self.thresholdDock)
        self.splitDockWidget(self.dronesWidget, self.thresholdDock, Qt.Horizontal)  # Размещаем справа от pelengWidget

        if self.levelWidget_status:
            self.levelWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.levelWidget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.levelWidget.setMinimumWidth(300)
            self.tabifyDockWidget(self.pelengWidget, self.levelWidget)  # Добавляем levelWidget как вкладку к pelengWidget

        # FPV Scope (нижняя часть, если включено)
        if self.fpvScopeWidget_status:
            self.fpvScopeWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.fpvScopeWidget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.fpvScopeWidget.setMaximumHeight(550)
            self.fpvScopeWidget.setMinimumHeight(300)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.fpvScopeWidget)

            self.fpvScopeSettingsWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.fpvScopeSettingsWidget.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
            self.fpvScopeSettingsWidget.setMaximumHeight(100)
            self.addDockWidget(Qt.LeftDockWidgetArea, self.fpvScopeSettingsWidget)
            if self.fpvVideoWidget_status:
                self.splitDockWidget(self.fpvVideoWidget, self.fpvScopeSettingsWidget, Qt.Vertical)

    def set_connection_type(self, mode='emulation'):
        if self.connection is not None:
            self.connection.close()
        try:
            frequencies =[self.settingsWidget.conf_drons[key]['frequency'] for key in self.settingsWidget.conf_drons]
            if mode == 'emulation' or mode == 'Emulation':
                self.connection = EmulationTread(len(self.settingsWidget.conf_drons.keys()),
                                                 self.settingsWidget.connection.spb_timeout.value(),
                                                 self.logger)
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
        self.connection.signal_fpvData_packet.connect(self.processor.receive_fpvData)

    def change_connection_state(self, status: bool):
        if status:
            self.act_start.setIcon(QIcon(f'assets/icons/btn_stop.png'))
            if self.levelWidget_status:
                self.levelWidget.clear_plot()
            try:
                if self.settingsWidget.debug.cb_connection_type.currentText() == 'TCP':
                    self.connection.open(self.settingsWidget.connection.le_ip_address.text(),
                                         self.settingsWidget.connection.le_port_numb.text())
                else:
                    self.connection.open(self.settingsWidget.connection.le_port_numb.text())
            except Exception as e:
                self.logger.error(f'No connection with {self.settingsWidget.connection.le_port_numb.text()}\n{e}')
        else:
            self.act_start.setIcon(QIcon(f'assets/icons/btn_start.png'))
            self.connection.close()

    def link_events(self):
        self.processor.sig_auto_threshold.connect(self.change_threshold)
        self.processor.sig_progrBar_value.connect(self.calibrationWidget.change_value_progressBar)
        self.processor.sig_warning.connect(self.settingsWidget.debug.event_play_digital_sound)

        self.slider_threshold.valueChanged.connect(self.processor.change_threshold)
        self.slider_threshold.valueChanged.connect(lambda threshold: self.settingsWidget.conf.update({'threshold': threshold}))
        self.slider_threshold.valueChanged.connect(self.connection.threshold_changed)

        # Threshold signals for TCP connection
        self.connection.signal_threshold.connect(self.processor.change_threshold)
        self.connection.signal_threshold.connect(self.change_threshold)
        self.connection.signal_threshold.connect(lambda threshold: self.settingsWidget.conf.update({'threshold': threshold}))
        self.connection.signal_success_change_ip.connect(self.settingsWidget.connection.update_tcp_parameters)

        self.connection.signal_new_calibr_coeff.connect(self.processor.update_calibration_coeff)
        self.connection.signal_fpvScope_thresholds.connect(self.fpvScopeWidget.update_thresholds)
        self.connection.signal_peleng_shift_angles.connect(self.processor.change_shift_angle)

        # Calibration coefficients signal for TCP connection
        self.connection.signal_calibration.connect(self.dronesWidget.set_calibration)

        # Drons gains signal for TCP connection
        self.connection.signal_drons_gains.connect(self.processor.update_gains)
        self.connection.signal_drons_gains.connect(self.dronesWidget.update_gains)

        self.settingsWidget.debug.cb_connection_type.currentTextChanged.connect(self.set_connection_type)
        self.settingsWidget.connection.spb_timeout.valueChanged.connect(self.connection.set_timeout)
        self.settingsWidget.connection.btn_change_ip.clicked.connect(lambda: self.connection.send_command_to_change_ip(
                                                            new_ip=self.settingsWidget.connection.le_new_ip.text(),
                                                            new_port=self.settingsWidget.connection.le_new_port.text()))
        self.settingsWidget.connection.btn_send_detect_settings.clicked.connect(self.connection.send_detect_settings)
        self.settingsWidget.connection.btn_receive_detect_settings.clicked.connect(self.connection.send_cmd_to_receive_detect_settings)

        self.settingsWidget.database.btn_search.clicked.connect(lambda: self.DataBaseLog.get_data_from_database(
                                        cur_date=self.settingsWidget.database.calendar.selectedDate().toString("yyyy-MM-dd"),
                                        cur_time=self.settingsWidget.database.cb_time.currentData()))

        self.btn_auto_threshold.clicked.connect(self.calibrationWidget.open_calibration_window)
        self.calibrationWidget.btn_calibrate.clicked.connect(self.processor.reset_receive_counter)
        self.calibrationWidget.spb_calibration_time.setValue(self.processor.calibration_time)
        self.calibrationWidget.spb_calibration_time.valueChanged.connect(self.processor.change_calibration_time)

        if self.recordCalibrationWidget_status:
            self.connection.signal_levels.connect(self.recordCalibrationWidget.accumulate_signals)
            self.processor.sig_norm_levels_and_pelengs.connect(self.recordCalibrationWidget.accumulate_norm_signals)

        if self.fpvScopeWidget_status:
            self.connection.signal_fpvScope_packet.connect(self.fpvScopeWidget.update_graph)
            self.fpvScopeWidget.signal_all_thresholds_change.connect(self.connection.send_all_fpvScope_thresholds)
            self.fpvScopeWidget.signal_threshold_change.connect(self.connection.send_fpvScope_threshold)
            self.fpvScopeWidget.signal_fpvScope_mode.connect(self.connection.send_cmd_to_change_fpvScope_mode)
            self.fpvScopeWidget.signal_change_radio_btn.connect(self.fpvScopeSettingsWidget.change_radio_button_on_auto)

        if self.settingsConfiguration_status:
            self.connection.signal_frequencies.connect(self.settingsWidget.configuration.set_data_to_table)
            self.settingsWidget.configuration.btn_read_controller.clicked.connect(
                lambda: self.connection.send_cmd_for_change_mode(CtrlMode.frequencies, type='freq'))
            self.settingsWidget.configuration.signal_freq_to_controller.connect(self.connection.send_new_freq_to_controller)

        if self.settingsAdminWidget_status:
            self.settingsWidget.administrator.signal_peleng_shift_angles.connect(self.connection.send_peleng_shift_angles)
            self.settingsWidget.administrator.signal_peleng_shift_angles.connect(self.processor.change_shift_angle)
            self.connection.signal_peleng_shift_angles.connect(self.settingsWidget.administrator.set_current_angles)

    def change_threshold(self, value):
        self.slider_threshold.setValue(value)

    def enable_sound(self, status: bool):
        if status:
            self.act_sound.setIcon(QIcon(rf'assets/icons/sound_on.png'))
        else:
            self.act_sound.setIcon(QIcon(rf'assets/icons/sound_off.png'))
        self.settingsWidget.debug.sound_flag_changed(status)

    def load_data(self, splash):
        splash.setFont(font)
        for i in range(1, 11):
            time.sleep(0.05)  # <-- эмулируем загрузку
            QApplication.processEvents()


def load_translator(app, language):
    translator = QTranslator()
    # Путь к файлу перевода
    translation_file = os.path.join('translations', f'shapel_{language}.qm')
    if os.path.exists(translation_file):
        translator.load(translation_file)
        app.installTranslator(translator)
        return translator
    return None


if __name__ == '__main__':
    app = QApplication(sys.argv)
    font = QFont("Arial", 10)
    app.setFont(font)

    colors = {'[dark]': {'primary': "#4CAF50",
                       'background': "#212121",
                       'foreground': "#E0E0E0",
                       'input.background': "#2E2E2E",
                       'border': "#424242"}}
    qdarktheme.setup_theme(theme='dark', custom_colors=colors, additional_qss="QToolTip { "
                                                                              "background-color: #ffff99;"
                                                                              "color: #000000;"
                                                                              "border: 1px solid #000000;"
                                                                              "padding: 2px;}"
                                                                              
                                                                              "QCheckBox::indicator { "
                                                                              "width: 22px; "
                                                                              "height: 22px; "
                                                                              "}")
    with open('config.yaml') as f:
        conf = dict(yaml.load(f, Loader=yaml.SafeLoader))
    translator = load_translator(app=app, language=conf['language'])

    # 🚀 Splash screen
    splash = QSplashScreen(QtGui.QPixmap('assets/logo/splash_1.png'))
    splash.show()
    app.processEvents()


    main_window = MainWindow()
    main_window.load_data(splash)
    splash.finish(main_window)
    main_window.show()
    sys.exit(app.exec())
