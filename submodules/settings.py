import time
import yaml
import pygame
from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QApplication, \
    QGridLayout, QSlider, QPushButton, QDoubleSpinBox, QSpacerItem, QSizePolicy, QAbstractSpinBox, QCheckBox, \
    QSpinBox, QTableWidget, QTableWidgetItem, QCalendarWidget, QWidget, QGroupBox, QLineEdit, QHeaderView, \
    QAbstractItemView
from PyQt5.QtGui import QIcon, QPixmap, QColor
from submodules.connection import *
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSize
import os
from os import walk
from submodules.basic import Dron
import subprocess
import sys
from PyQt5.QtMultimedia import QCameraInfo


class SettingsWidget(QWidget):
    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.conf = {}
        self.conf_drons = {}
        self.lang_conf = {}
        self.configuration_conf = {}
        self.setLayout(QVBoxLayout())
        self.setWindowTitle(self.tr('Settings'))
        self.drons = []

        self.tabWidget = QTabWidget()
        self.layout().addWidget(self.tabWidget)

        self.connection = ConnectionSettingsWidget(logger_=self.logger)
        self.tabWidget.addTab(self.connection, self.tr('Connection'))
        self.debug = DebugWidget(logger_=self.logger)
        self.tabWidget.addTab(self.debug, self.tr('Debug'))

        self.btn_dump_conf = QPushButton(self.tr('Save config'))
        self.layout().addWidget(self.btn_dump_conf)
        self.btn_dump_conf.clicked.connect(self.dump_conf)

        self.calibration_coefficients = None
        self.peleng_coefficients = None
        self.sensivity_coeff = None

        self.set_conf()

        self.database = DataBaseWidget(logger_=self.logger)
        self.tabWidget.addTab(self.database, ('Database'))

        if self.conf['widgets']['settingsConfiguration']:
            self.configuration = ConfigurationWidget(configuration_conf=self.configuration_conf, logger_=self.logger)

    def dump_conf(self):
        try:
            with open('config.yaml', 'w') as f:
                self.collect_conf()
                yaml.dump(self.conf, f, sort_keys=False)
                self.logger.success('config.yaml was saved!')
        except Exception as e:
            self.logger.error(f'Error with dump config: {e}')

    def dump_conf_drons(self):
        try:
            with open('config_drons.yaml', 'w') as f:
                yaml.dump(self.conf_drons, f, sort_keys=False)
                self.logger.success('config_drons.yaml was saved!')
        except Exception as e:
            self.logger.error(f'Error with dump drones config: {e}')

    def read_conf(self):
        try:
            with open('config.yaml', encoding='utf-8') as f:
                self.conf = dict(yaml.load(f, Loader=yaml.SafeLoader))

            with open('config_drons.yaml', encoding='utf-8') as f2:
                self.drons = []
                self.conf_drons = dict(yaml.load(f2, Loader=yaml.SafeLoader))
                for dict_name, conf in self.conf_drons.items():
                    self.drons.append(Dron(dict_name, conf))

            with open('configuration.yaml', encoding='utf-8') as f4:
                self.configuration_conf = dict(yaml.load(f4, Loader=yaml.SafeLoader))

            self.logger.success(f'Configs were read!')
        except Exception as e:
            self.logger.error(f'Error with reading config: {e}')

    def collect_conf(self):
        self.conf.update(self.connection.collect_conf())
        self.conf.update(self.debug.collect_conf())

    def set_conf(self):
        try:
            self.read_conf()
            self.connection.set_conf(self.conf['connection'])
            self.debug.set_conf(self.conf['debug'])
            self.calibration_coefficients = self.conf['calibration_coefficients']
            self.peleng_coefficients = self.conf['peleng_coefficients']
            self.sensivity_coeff = self.conf['sensivity_coeff']
        except:
            self.logger.exception('Can\'t load config')


class ConnectionSettingsWidget(QWidget):

    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_
        self.main_layout = QHBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.main_layout)

        self.create_widgets()
        self.add_widgets_to_layout()

    def create_widgets(self):
        self.box_timeout = QGroupBox(self.tr('Timeout'))
        self.spb_timeout = QSpinBox()
        self.spb_timeout.setSingleStep(1)
        self.spb_timeout.setMaximum(5000)

        self.box_tcp = QGroupBox(self.tr('TCP (remote control)'))
        self.l_ip_address = QLabel(self.tr('IP address'))
        self.le_ip_address = QLineEdit()
        self.l_port_numb = QLabel(self.tr('Port number'))
        self.le_port_numb = QLineEdit()
        self.le_port_numb.setText('55555')
        self.btn_check_tcp_connection = QPushButton(self.tr('Check TCP'))
        self.btn_check_tcp_connection.clicked.connect(self.btn_check_tcp_clicked)
        self.status_icon = QLabel()
        self.status_icon.setPixmap(QPixmap('assets/icons/unknown.png'))

        self.box_detect_config = QGroupBox(self.tr('Detect config'))
        self.btn_send_detect_settings = QPushButton(self.tr('Send config'))
        self.btn_receive_detect_settings = QPushButton(self.tr('Receive config'))

        self.box_camera = QGroupBox(self.tr('Camera device'))
        self.cb_camera = QComboBox()
        self.cb_camera.setFixedWidth(250)
        available_cameras = QCameraInfo.availableCameras()
        for cam in available_cameras:
            self.cb_camera.addItem(str(cam.description()), cam)

        self.box_change_ip = QGroupBox(self.tr('Change IP address'))
        self.le_new_ip = QLineEdit()
        self.le_new_ip.setPlaceholderText(self.tr('Enter new IP address'))
        self.le_new_port = QLineEdit()
        self.le_new_port.setPlaceholderText(self.tr('Enter new port'))
        self.btn_change_ip = QPushButton(self.tr('Change'))

    def add_widgets_to_layout(self):
        spacerItem = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)

        box_tcp_layout = QVBoxLayout()
        ip_layout = QVBoxLayout()
        ip_layout.addWidget(self.l_ip_address)
        ip_layout.addWidget(self.le_ip_address)
        port_layout = QVBoxLayout()
        port_layout.addWidget(self.l_port_numb)
        port_layout.addWidget(self.le_port_numb)
        check_layout = QHBoxLayout()
        check_layout.addWidget(self.btn_check_tcp_connection)
        check_layout.addWidget(self.status_icon)
        box_tcp_layout.addLayout(ip_layout)
        box_tcp_layout.addSpacing(10)
        box_tcp_layout.addLayout(port_layout)
        box_tcp_layout.addSpacing(10)
        box_tcp_layout.addLayout(check_layout)
        self.box_tcp.setLayout(box_tcp_layout)

        box_camera_layout = QVBoxLayout()
        box_camera_layout.addWidget(self.cb_camera)
        self.box_camera.setLayout(box_camera_layout)

        box_detect_config_layout = QVBoxLayout()
        box_detect_config_layout.addWidget(self.btn_send_detect_settings)
        box_detect_config_layout.addWidget(self.btn_receive_detect_settings)
        self.box_detect_config.setLayout(box_detect_config_layout)

        box_timeout_layout = QVBoxLayout()
        box_timeout_layout.addWidget(self.spb_timeout)
        self.box_timeout.setLayout(box_timeout_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.box_timeout)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.box_camera)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.box_detect_config)

        box_change_ip_layout = QHBoxLayout()
        box_change_ip_layout.addWidget(self.le_new_ip)
        box_change_ip_layout.addWidget(self.le_new_port)
        box_change_ip_layout.addWidget(self.btn_change_ip)
        self.box_change_ip.setLayout(box_change_ip_layout)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.box_tcp)
        left_layout.addSpacing(10)
        left_layout.addWidget(self.box_change_ip)

        self.main_layout.addLayout(left_layout)
        self.main_layout.addSpacing(20)
        self.main_layout.addLayout(right_layout)

    def btn_check_tcp_clicked(self):
        self.set_loading_icon()

        """ Выполнение в потоке, чтобы добавить индикацию выполнения функции """
        temp_thread = QThread()
        if sys.platform.startswith("win"):
            temp_thread.run = lambda: self.check_TCP_connection_windows()
        else:
            temp_thread.run = lambda: self.check_TCP_connection()
        temp_thread.start()     # start thread
        temp_thread.join()      # wait for end

    def check_TCP_connection_windows(self):
        response = subprocess.run(["ping", self.le_ip_address.text(), "-n", "2"],
                                  capture_output=True, text=True, encoding='cp866')
        self.logger.info(response.stdout)
        err_str = 'Заданный узел недоступен'
        if response.returncode == 0 and err_str not in response.stdout:
            self.status_icon.setPixmap(QPixmap('assets/icons/ok.png'))
        else:
            # Check for errors in the output
            if "Destination host unreachable" in response.stderr:
                self.logger.error("Host unreachable")
            else:
                self.logger.error(f"Error: {response.stderr}")
            self.status_icon.setPixmap(QPixmap('assets/icons/error.png'))

    def check_TCP_connection(self):
        response = os.system(f"ping {self.le_ip_address.text()} -c 2")
        if response == 0:       # success
            self.status_icon.setPixmap(QPixmap('assets/icons/ok.png'))
        else:                   # fail
            self.status_icon.setPixmap(QPixmap('assets/icons/error.png'))

    def update_tcp_parameters(self, status: bool):
        if status:
            self.le_ip_address.setText(self.le_new_ip.text())
            self.le_port_numb.setText(self.le_new_port.text())

    def set_loading_icon(self):
        self.status_icon.setPixmap(QPixmap('assets/icons/loading.png'))

    def collect_conf(self):
        connection_conf = {'connection': {'timeout': self.spb_timeout.value(),
                                          'ip_address': self.le_ip_address.text(),
                                           'port_numb': self.le_port_numb.text()}}
        return connection_conf

    def set_conf(self, conf: dict):
        try:
            self.spb_timeout.setValue(conf['timeout'])
            self.le_ip_address.setText(conf['ip_address'])
            self.le_port_numb.setText(conf['port_numb'])
        except Exception as e:
            self.logger.error(f'Can\'t load serial conf: {e}')


class DebugWidget(QWidget):

    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignTop)
        self.setLayout(self.main_layout)

        pygame.mixer.init()
        self.sound_flag = True

        self.create_widgets()
        self.add_widgets_to_layout()

    def create_widgets(self):
        self.box_connection = QGroupBox(self.tr('Connection'))
        self.l_connection_type = QLabel(self.tr('Connection type'))
        self.cb_connection_type = QComboBox()
        self.cb_connection_type.addItems(['TCP', 'Emulation', 'Player'])
        self.l_record = QLabel(self.tr('Record for \'player\''))
        self.cb_record = QComboBox()
        for record_name in self.get_all_files(dir='records'):
            self.cb_record.addItem(record_name)

        self.box_sound = QGroupBox(self.tr('Sound'))
        self.cb_sound = QComboBox()
        self.sound_path = r'assets/sounds/'
        for sound_name in self.get_all_files(dir=self.sound_path):
            self.cb_sound.addItem(sound_name)
        self.btn_play_sound = QPushButton()
        self.btn_play_sound.setIcon(QIcon(r'assets/icons/play_sound.png'))
        self.btn_play_sound.setFixedSize(26, 26)
        self.btn_play_sound.clicked.connect(self.event_check_sound)

        self.box_other = QGroupBox(self.tr('Other'))
        self.chb_database_log = QCheckBox(self.tr('Enable DataBase Logging'))
        self.chb_database_log.setTristate(False)
        self.chb_peleng_level = QCheckBox(self.tr('Consider signal levels in Peleng'))
        self.chb_peleng_level.setTristate(False)
        self.chb_average_peleng = QCheckBox(self.tr('Average pelengs'))
        self.chb_average_peleng.setTristate(False)
        self.chb_average_spectrum = QCheckBox(self.tr('Average spectrum'))
        self.chb_average_spectrum.setTristate(False)

    def add_widgets_to_layout(self):
        box_connection_layout = QHBoxLayout()
        conn_type_layout = QVBoxLayout()
        conn_type_layout.addWidget(self.l_connection_type)
        conn_type_layout.addWidget(self.cb_connection_type)
        record_layout = QVBoxLayout()
        record_layout.addWidget(self.l_record)
        record_layout.addWidget(self.cb_record)
        box_connection_layout.addLayout(conn_type_layout)
        box_connection_layout.addSpacing(50)
        box_connection_layout.addLayout(record_layout)
        self.box_connection.setLayout(box_connection_layout)

        box_other_layout = QVBoxLayout()
        box_other_layout.addWidget(self.chb_database_log)
        box_other_layout.addWidget(self.chb_peleng_level)
        box_other_layout.addWidget(self.chb_average_peleng)
        box_other_layout.addWidget(self.chb_average_spectrum)
        self.box_other.setLayout(box_other_layout)

        box_sound_layout = QHBoxLayout()
        box_sound_layout.setAlignment(Qt.AlignTop)
        box_sound_layout.addWidget(self.cb_sound)
        box_sound_layout.addWidget(self.btn_play_sound)
        self.box_sound.setLayout(box_sound_layout)

        line_layout = QHBoxLayout()
        line_layout.addWidget(self.box_other)
        line_layout.addSpacing(50)
        line_layout.addWidget(self.box_sound)

        self.main_layout.addWidget(self.box_connection)
        self.main_layout.addSpacing(20)
        self.main_layout.addLayout(line_layout)

    def get_all_files(self, dir: str):
        files = []
        for (dirpath, dirnames, filenames) in walk(dir):
            files.extend(filenames)
        return files

    def collect_conf(self):
        conf = {'debug': {'connection_type': self.cb_connection_type.currentText(),
                          'player_record': self.cb_record.currentText(),
                          'database_logging': bool(self.chb_database_log.checkState()),
                          'warning_sound': self.cb_sound.currentText(),
                          'levels_in_peleng': bool(self.chb_peleng_level.checkState()),
                          'average_levels_for_peleng': bool(self.chb_average_peleng.checkState()),
                          'average_spectrum': bool(self.chb_average_spectrum.checkState())}}
        return conf

    def set_conf(self, conf: dict):
        try:
            self.cb_connection_type.setCurrentText(conf['connection_type'])
            self.cb_record.setCurrentText(conf['player_record'])
            self.chb_database_log.setChecked(conf['database_logging'])
            self.cb_sound.setCurrentText(conf['warning_sound'])
            self.chb_peleng_level.setChecked(conf['levels_in_peleng'])
            self.chb_average_peleng.setChecked(conf['average_levels_for_peleng'])
            # self.chb_leds_activation.setChecked(conf['led_activation'])
            self.chb_average_spectrum.setChecked(conf['average_spectrum'])
        except:
            self.logger.error('Can\'t load debug conf')

    def event_play_sound(self, status: bool):
        pygame.mixer.music.load(self.sound_path + self.cb_sound.currentText())
        if status and self.sound_flag:
            pygame.mixer.music.play()
        else:
            pygame.mixer.stop()

    def event_check_sound(self, status: bool):
        pygame.mixer.music.load(self.sound_path + self.cb_sound.currentText())
        pygame.mixer.music.play()

    def sound_flag_changed(self, status):
        self.sound_flag = status


class ConfigurationWidget(QWidget):
    signal_freq_to_controller = pyqtSignal(dict)

    def __init__(self, configuration_conf: dict, logger_):
        super().__init__()
        self.configuration_conf = configuration_conf
        self.logger = logger_
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.number_of_drons = None
        self.dron_freq = {}
        self.dron_names = []
        self.configuration_freqs_conf = configuration_conf['drons_freqs']

        self.read_freq_from_conf()
        self.changed_table_items = []

        # Create table of drones frequencies
        self.freq_out_table = QTableWidget()
        self.freq_out_table.cellChanged.connect(self.table_item_changed)


        self.setup_table()
        self.set_data_to_table(data={0: [0, 0, 0, 0, 0, 0, 0, 0], 1: [0, 0, 0, 0, 0, 0, 0, 0],
                                     2: [0, 0, 0, 0, 0, 0, 0, 0], 3: [0, 0, 0, 0, 0, 0, 0, 0],
                                     4: [0, 0, 0, 0, 0, 0, 0, 0], 5: [0, 0, 0, 0, 0, 0, 0, 0],
                                     6: [0, 0, 0, 0, 0, 0, 0, 0], 7: [0, 0, 0, 0, 0, 0, 0, 0],
                                     8: [0, 0, 0, 0, 0, 0, 0, 0], 9: [0, 0, 0, 0, 0, 0, 0, 0],
                                     10: [0, 0, 0, 0, 0, 0, 0, 0], 11: [0, 0, 0, 0, 0, 0, 0, 0],
                                     12: [0, 0, 0, 0, 0, 0, 0, 0], 13: [0, 0, 0, 0, 0, 0, 0, 0],
                                     14: [0, 0, 0, 0, 0, 0, 0, 0], 15: [0, 0, 0, 0, 0, 0, 0, 0]})
        self.create_buttons()
        self.add_to_layout()

    def create_buttons(self):
        self.main_label = QLabel(self.tr('Frequency settings'))

        self.btn_read_file = QPushButton(self.tr('Read from file'))
        self.btn_read_file.setFixedSize(155, 30)
        self.btn_read_file.clicked.connect(self.set_data_to_table)

        self.btn_read_controller = QPushButton(self.tr('Read from controller'))
        self.btn_read_controller.setFixedSize(210, 30)

        self.btn_write_file = QPushButton(self.tr('Write to file'))
        self.btn_write_file.setFixedSize(140, 30)
        self.btn_write_file.clicked.connect(self.write_data_to_file)

        self.btn_write_controller = QPushButton(self.tr('Write to controller'))
        self.btn_write_controller.setFixedSize(190, 30)
        self.btn_write_controller.clicked.connect(self.write_data_to_controller)

    def add_to_layout(self):
        btns_layout = QHBoxLayout()
        btns_layout.addWidget(self.btn_read_file)
        btns_layout.addWidget(self.btn_read_controller)
        btns_layout.addWidget(self.btn_write_file)
        btns_layout.addWidget(self.btn_write_controller)

        self.main_layout.addWidget(self.freq_out_table)
        self.main_layout.addLayout(btns_layout)

    def read_freq_from_conf(self):
        try:
            with open('configuration.yaml', encoding='utf-8') as f4:
                self.configuration_freqs_conf = dict(yaml.load(f4, Loader=yaml.SafeLoader))['drons_freqs']
            self.number_of_drons = len(self.configuration_freqs_conf)
            for dron, value in self.configuration_freqs_conf.items():
                name = value['name']
                values = value['frequencies']
                self.dron_freq[name] = values
                self.dron_names.append(name)
        except Exception as e:
            self.logger.error(f'Can\'t load conf: {e}')

    def setup_table(self):
        self.freq_out_table.setColumnCount(self.number_of_drons)
        self.freq_out_table.setRowCount(len(list(self.dron_freq.values())[0]))
        self.freq_out_table.setHorizontalHeaderLabels(self.dron_names)

        # Aligning all headers to center
        for i in range(self.number_of_drons):
            self.freq_out_table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
        self.freq_out_table.resizeColumnsToContents()       # resize of the columns by content

        # To resize table on full template
        self.freq_out_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.freq_out_table.horizontalHeader().setStretchLastSection(True)

    def set_data_to_table(self, data={}):
        if data:            # if not empty
            pass
        elif not data:      # if empty
            self.read_freq_from_conf()
            data = self.dron_freq
        column_counter = 0
        for value in data.values():
            while len(value) <= (self.freq_out_table.rowCount()):
                value.append(0)                                             # add zero for full list
            row_counter = 0
            for i in range(self.freq_out_table.rowCount()):
                self.freq_out_table.setItem(row_counter, column_counter, QTableWidgetItem(str(value[i])))
                row_counter += 1
            column_counter += 1
        self.changed_table_items.clear()

    def write_data_to_file(self):
        for i in range(self.freq_out_table.columnCount()):
            values = []
            for j in range(self.freq_out_table.rowCount()):
                values.append(self.freq_out_table.item(j, i).text())
            self.collect_configuration_conf(i, values)
        self.dump_configuration_conf()
        self.update_configuration_conf()

    def change_dron_names(self, name: str):
        ind_dash, ind_space, new_name = None, None, None
        ind_dash = name.find('-')
        ind_space = name.find(' ')
        if ind_dash != -1:
            new_name = name[:ind_dash]
        elif ind_space != -1:
            new_name = name[:ind_space]
        return new_name

    def collect_configuration_conf(self, i, values):
        dron_name = list(self.configuration_freqs_conf.keys())[i]
        self.configuration_freqs_conf[dron_name]['frequencies'] = values

    def dump_configuration_conf(self):
        with open('configuration.yaml', 'w') as f:
            self.configuration_conf['drons_freqs'].update(self.configuration_freqs_conf)
            yaml.dump(self.configuration_conf, f, sort_keys=False)

    def update_configuration_conf(self):
        with open('configuration.yaml') as f4:
            self.configuration_freqs_conf = dict(yaml.load(f4, Loader=yaml.SafeLoader))
        self.read_freq_from_conf()

    def write_data_to_controller(self):
        new_freq_to_controller = {}
        for i in range(len(self.changed_table_items)):
            values = []
            for j in range(0, self.freq_out_table.rowCount()):
                temp_value = self.freq_out_table.item(j, self.changed_table_items[i]).text()
                if temp_value == '0':
                    pass
                else:
                    values.append(self.freq_out_table.item(j, self.changed_table_items[i]).text())

            """ Сравнивается колнка с 7 и 8, потому что под 7 и 8 колонкой находятся частоты в таблице для выкокой
            частоты дискретизации, а для их отправки нужно отправлять в контроллер другой шифр! """
            if self.changed_table_items[i] == 6 or self.changed_table_items[i] == 7:
                self.changed_table_items[i] += 10  # 9 потому что индексация с 0, а 1 добавляется при отправке фулл пакета
            new_freq_to_controller.update({self.changed_table_items[i] + 1: values})
        self.changed_table_items.clear()
        self.logger.info(f'changed freq = {new_freq_to_controller}')
        self.signal_freq_to_controller.emit(new_freq_to_controller)

    def table_item_changed(self, row, column):
        self.changed_table_items.append(column)


# class DataBaseWidget(QWidget):
#     def __init__(self, logger_):
#         super().__init__()
#         self.main_layout = QVBoxLayout()
#         self.setLayout(self.main_layout)
#         self.selected_date = ''
#         self.selected_time = ''
#         self.create_controls()
#         self.add_widgets_to_layout()
#
#     def create_controls(self):
#         self.calendar = QCalendarWidget()
#         self.calendar.setMaximumHeight(100)
#         self.calendar.setMaximumWidth(300)
#
#         self.l_time = QLabel('Time, hour')
#         self.cb_time = QComboBox()
#         self.cb_time.addItem('0-24', '24/7')
#         for counter in range(24):
#             self.cb_time.addItem(str(counter) + '-' + str(counter + 1), str(counter) + ':00:00')
#         self.cb_time.setMaximumWidth(100)
#         self.cb_time.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
#
#         self.btn_search = QPushButton('Search')
#         self.btn_search.setFixedSize(QSize(120, 30))
#
#         self.table = QTableWidget()
#         self.table.setRowCount(5)
#         self.table.setColumnCount(4)
#         self.table.setHorizontalHeaderLabels(['Date', 'Time', 'Drone', 'Angle'])
#         for i in range(self.table.columnCount()):
#             self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
#         self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)     # to resize table on full template
#         self.table.horizontalHeader().setStretchLastSection(True)
#         self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)        # disable items editing
#
#     def add_widgets_to_layout(self):
#         calendar_layout = QVBoxLayout()
#         # calendar_layout.addWidget(self.l_date, alignment=Qt.AlignTop)
#         calendar_layout.addWidget(self.calendar, alignment=Qt.AlignTop)
#         calendar_layout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
#
#         time_layout = QVBoxLayout()
#         time_layout.addWidget(self.l_time, alignment=Qt.AlignTop)
#         time_layout.addSpacing(25)
#         time_layout.addWidget(self.cb_time, alignment=Qt.AlignTop)
#         time_layout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
#
#         btn_search_layout = QVBoxLayout()
#         btn_search_layout.addSpacing(50)
#         btn_search_layout.addWidget(self.btn_search, alignment=Qt.AlignTop)
#
#         controls_layout = QHBoxLayout()
#         controls_layout.addLayout(calendar_layout)
#         controls_layout.addLayout(time_layout)
#         controls_layout.addLayout(btn_search_layout)
#
#         self.main_layout.addLayout(controls_layout)
#
#         self.main_layout.addWidget(self.table)
#
#         self.main_layout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
#
#     def resize_table(self, row_count):
#         self.table.setRowCount(row_count)
#
#     def request_status_update(self, status: bool):
#         if status:
#             for i in range(self.table.columnCount()):
#                 self.table.setItem(0, i, QTableWidgetItem(''))
#         else:
#             self.table.setItem(0, 0, QTableWidgetItem('No'))
#             self.table.setItem(0, 1, QTableWidgetItem('warnings'))
#             self.table.setItem(0, 2, QTableWidgetItem('at this'))
#             self.table.setItem(0, 3, QTableWidgetItem('time!'))
#
#             for i in range(self.table.columnCount()):
#                 self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
#
#     def receive_requested_data(self, dataframe):
#         if len(dataframe):
#             self.resize_table(row_count=len(dataframe))
#             self.request_status_update(status=True)
#
#             for j in range(self.table.columnCount()):
#                 for i in range(self.table.rowCount()):
#                     self.table.setItem(i, j, QTableWidgetItem(str(dataframe.iloc[i, j])))
#         else:
#             self.resize_table(row_count=1)
#             self.request_status_update(status=False)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCalendarWidget, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt

class DataBaseWidget(QWidget):
    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignTop)
        self.setLayout(self.main_layout)
        self.selected_date = ''
        self.selected_time = ''
        self.create_controls()
        self.add_widgets_to_layout()

        # Устанавливаем минимальный размер виджета
        self.setMinimumSize(500, 400)

    def create_controls(self):
        # Calendar
        self.calendar = QCalendarWidget()
        self.calendar.setMaximumHeight(170)  # Увеличиваем высоту для лучшей читаемости
        self.calendar.setMaximumWidth(250)  # Уменьшаем ширину для компактности
        self.calendar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)  # Фиксируем размер

        # Time
        self.l_time = QLabel(self.tr('Time, hour'))
        self.cb_time = QComboBox()
        self.cb_time.addItem('0-24', '24/7')
        for counter in range(24):
            self.cb_time.addItem(f"{counter}-{counter + 1}", f"{counter}:00:00")
        self.cb_time.setFixedWidth(100)  # Фиксированная ширина
        self.cb_time.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Search button
        self.btn_search = QPushButton(self.tr('Search'))
        self.btn_search.setFixedSize(100, 30)  # Уменьшаем ширину кнопки

        # Table
        self.table = QTableWidget()
        self.table.setRowCount(5)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([self.tr('Date'), self.tr('Time'), self.tr('Drone'), self.tr('Angle')])
        for i in range(self.table.columnCount()):
            self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Отключаем редактирование
        self.table.setMaximumHeight(300)  # Ограничиваем высоту таблицы
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # Фиксируем высоту, растягиваем по ширине

    def add_widgets_to_layout(self):
        # Calendar layout
        calendar_layout = QVBoxLayout()
        calendar_layout.addWidget(self.calendar, alignment=Qt.AlignCenter)
        calendar_layout.addStretch()  # Прижимаем календарь вверх

        # Time layout
        time_layout = QVBoxLayout()
        time_layout.addWidget(self.l_time, alignment=Qt.AlignCenter)
        time_layout.addWidget(self.cb_time, alignment=Qt.AlignCenter)
        time_layout.addStretch()  # Прижимаем элементы вверх

        # Search button layout
        btn_search_layout = QVBoxLayout()
        btn_search_layout.addWidget(self.btn_search, alignment=Qt.AlignCenter)
        btn_search_layout.addStretch()  # Прижимаем кнопку вверх

        # Controls layout (calendar + time + button)
        controls_layout = QHBoxLayout()
        controls_layout.addLayout(calendar_layout)
        controls_layout.addSpacing(20)  # Уменьшенный отступ между элементами
        controls_layout.addLayout(time_layout)
        controls_layout.addSpacing(20)
        controls_layout.addLayout(btn_search_layout)
        controls_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)  # Выравнивание влево и вверх
        controls_layout.setContentsMargins(10, 10, 10, 10)  # Отступы для аккуратности

        # Main layout
        self.main_layout.addLayout(controls_layout)
        self.main_layout.addWidget(self.table)  # Таблица растягивается по ширине
        self.main_layout.addStretch()  # Прижимаем содержимое вверх
        self.main_layout.setAlignment(Qt.AlignTop)  # Выравнивание всего содержимого вверх
        self.main_layout.setSpacing(10)  # Уменьшенный отступ между элем \

    def resize_table(self, row_count):
        self.table.setRowCount(row_count)

    def request_status_update(self, status: bool):
        if status:
            for i in range(self.table.columnCount()):
                self.table.setItem(0, i, QTableWidgetItem(''))
        else:
            self.table.setItem(0, 0, QTableWidgetItem(self.tr('No')))
            self.table.setItem(0, 1, QTableWidgetItem(self.tr('warnings')))
            self.table.setItem(0, 2, QTableWidgetItem(self.tr('at this')))
            self.table.setItem(0, 3, QTableWidgetItem(self.tr('time!')))
            for i in range(self.table.columnCount()):
                self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)

    def receive_requested_data(self, dataframe):
        if len(dataframe):
            self.resize_table(row_count=len(dataframe))
            self.request_status_update(status=True)
            for j in range(self.table.columnCount()):
                for i in range(self.table.rowCount()):
                    self.table.setItem(i, j, QTableWidgetItem(str(dataframe.iloc[i, j])))
        else:
            self.resize_table(row_count=1)
            self.request_status_update(status=False)


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    window = SettingsWidget()
    window.show()
    sys.exit(app.exec())