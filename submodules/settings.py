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
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.conf = {}
        self.conf_drons = {}
        self.lang_conf = {}
        self.configuration_conf = {}
        self.setWindowTitle(self.tr('Settings'))
        self.drons = []

        self.read_conf()

        self.tabWidget = QTabWidget()
        self.main_layout.addWidget(self.tabWidget)

        self.connection = ConnectionSettingsWidget(logger_=self.logger, default_camera=self.conf['connection']['default_camera'])
        self.tabWidget.addTab(self.connection, self.tr('Connection'))
        self.debug = DebugWidget(logger_=self.logger)
        if self.conf['widgets']['settingsDebug']:
            self.tabWidget.addTab(self.debug, self.tr('Debug'))

        self.btn_dump_conf = QPushButton(self.tr('Save config'))
        self.btn_dump_conf.clicked.connect(self.dump_conf)
        self.btn_dump_gains_conf = QPushButton(self.tr('Save gains'))
        self.btn_dump_gains_conf.clicked.connect(self.dump_conf_drons)
        self.add_buttons_to_layout()

        self.calibration_coefficients = None
        self.peleng_coefficients = None
        self.sensivity_coeff = None

        self.set_conf()

        self.database = DataBaseWidget(logger_=self.logger)
        self.tabWidget.addTab(self.database, self.tr('Database'))

        if self.conf['widgets']['settingsConfiguration']:
            self.configuration = ConfigurationWidget(configuration_conf=self.configuration_conf, logger_=self.logger)

        if self.conf['widgets']['settingsAdministrator']:
            self.administrator = AdminSettings(logger_=self.logger)


    def add_buttons_to_layout(self):
        btns_layout = QHBoxLayout()
        btns_layout.addWidget(self.btn_dump_gains_conf)
        self.main_layout.addLayout(btns_layout)

        self.connection.main_layout.addWidget(self.btn_dump_conf, alignment=Qt.AlignBottom)

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
            self.connection.set_conf(self.conf['connection'])
            self.debug.set_conf(self.conf['debug'])
            self.calibration_coefficients = self.conf['calibration_coefficients']
            self.peleng_coefficients = self.conf['peleng_coefficients']
            self.sensivity_coeff = self.conf['sensivity_coeff']
        except:
            self.logger.exception('Can\'t load config')


class ConnectionSettingsWidget(QWidget):

    def __init__(self, logger_, default_camera):
        super().__init__()
        self.logger = logger_
        self.default_camera = default_camera
        self.main_layout = QVBoxLayout()
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
        preferred_index = 0
        for index, cam in enumerate(available_cameras):
            description = str(cam.description())
            self.cb_camera.addItem(description, cam)
            if self.default_camera in description:
                preferred_index = index
        self.cb_camera.setCurrentIndex(preferred_index)

        self.box_change_ip = QGroupBox(self.tr('Change IP address'))
        self.le_new_ip = QLineEdit()
        self.le_new_ip.setPlaceholderText(self.tr('Enter new IP address'))
        self.le_new_port = QLineEdit()
        self.le_new_port.setPlaceholderText(self.tr('Enter new port'))
        self.btn_change_ip = QPushButton(self.tr('Change'))

    def add_widgets_to_layout(self):
        main_tab_layout = QHBoxLayout()
        main_tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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

        main_tab_layout.addLayout(left_layout)
        main_tab_layout.addSpacing(20)
        main_tab_layout.addLayout(right_layout)

        self.main_layout.addLayout(main_tab_layout)
        self.main_layout.addItem(spacerItem)

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
                                          'port_numb': self.le_port_numb.text(),
                                          'default_camera': self.cb_camera.currentText()}}
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

        self.digital_sound_path = r'assets/sounds/digital_channel/'
        self.l_digital_channel = QLabel(self.tr('Digital channel'))
        self.cb_digital_sound = QComboBox()
        for sound_name in self.get_all_files(dir=self.digital_sound_path):
            self.cb_digital_sound.addItem(sound_name)
        self.btn_play_digital_sound = QPushButton()
        self.btn_play_digital_sound.setIcon(QIcon(r'assets/icons/play_sound.png'))
        self.btn_play_digital_sound.setFixedSize(26, 26)
        self.btn_play_digital_sound.clicked.connect(lambda: self.event_check_sound(type='digital'))

        self.analog_sound_path = r'assets/sounds/analog_channel/'
        self.l_analog_channel = QLabel(self.tr('Analog channel'))
        self.cb_analog_sound = QComboBox()
        for sound_name in self.get_all_files(dir=self.analog_sound_path):
            self.cb_analog_sound.addItem(sound_name)
        self.btn_play_analog_sound = QPushButton()
        self.btn_play_analog_sound.setIcon(QIcon(r'assets/icons/play_sound.png'))
        self.btn_play_analog_sound.setFixedSize(26, 26)
        self.btn_play_analog_sound.clicked.connect(lambda: self.event_check_sound(type='analog'))

        self.box_other = QGroupBox(self.tr('Other'))
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
        box_other_layout.addWidget(self.chb_peleng_level)
        box_other_layout.addWidget(self.chb_average_peleng)
        box_other_layout.addWidget(self.chb_average_spectrum)
        self.box_other.setLayout(box_other_layout)

        box_sound_layout = QVBoxLayout()
        box_sound_layout.setAlignment(Qt.AlignTop)

        box_digital_sound_layout = QHBoxLayout()
        cb_digital_sound_layout = QVBoxLayout()
        cb_digital_sound_layout.addWidget(self.l_digital_channel)
        cb_digital_sound_layout.addWidget(self.cb_digital_sound)
        box_digital_sound_layout.addLayout(cb_digital_sound_layout)
        box_digital_sound_layout.addWidget(self.btn_play_digital_sound, alignment=Qt.AlignBottom)

        box_analog_sound_layout = QHBoxLayout()
        cb_analog_sound_layout = QVBoxLayout()
        cb_analog_sound_layout.addWidget(self.l_analog_channel)
        cb_analog_sound_layout.addWidget(self.cb_analog_sound)
        box_analog_sound_layout.addLayout(cb_analog_sound_layout)
        box_analog_sound_layout.addWidget(self.btn_play_analog_sound, alignment=Qt.AlignBottom)

        box_sound_layout.addLayout(box_digital_sound_layout)
        box_sound_layout.addSpacing(20)
        box_sound_layout.addLayout(box_analog_sound_layout)
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
                          'warning_digital_sound': self.cb_digital_sound.currentText(),
                          'warning_analog_sound': self.cb_analog_sound.currentText(),
                          'levels_in_peleng': bool(self.chb_peleng_level.checkState()),
                          'average_levels_for_peleng': bool(self.chb_average_peleng.checkState()),
                          'average_spectrum': bool(self.chb_average_spectrum.checkState())}}
        return conf

    def set_conf(self, conf: dict):
        try:
            self.cb_connection_type.setCurrentText(conf['connection_type'])
            self.cb_record.setCurrentText(conf['player_record'])
            self.cb_digital_sound.setCurrentText(conf['warning_digital_sound'])
            self.cb_analog_sound.setCurrentText(conf['warning_analog_sound'])
            self.chb_peleng_level.setChecked(conf['levels_in_peleng'])
            self.chb_average_peleng.setChecked(conf['average_levels_for_peleng'])
            self.chb_average_spectrum.setChecked(conf['average_spectrum'])
            self.digital_sound = pygame.mixer.Sound(self.digital_sound_path + self.cb_digital_sound.currentText())
            self.analog_sound = pygame.mixer.Sound(self.analog_sound_path + self.cb_analog_sound.currentText())
        except:
            self.logger.error('Can\'t load debug conf')

    def event_play_digital_sound(self, status: bool):
        if status and self.sound_flag:
            self.digital_sound.play()

    def event_play_analog_sound(self, status: bool):
        if status and self.sound_flag:
            self.analog_sound.play()

    def event_check_sound(self, type: str):
        if type == 'digital':
            pygame.mixer.music.load(self.digital_sound_path + self.cb_digital_sound.currentText())
            pygame.mixer.music.play()
        elif type == 'analog':
            pygame.mixer.music.load(self.analog_sound_path + self.cb_analog_sound.currentText())
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


class DataBaseWidget(QWidget):
    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_
        self.selected_date = ''
        self.selected_time = ''

        self.init_ui()
        self.setMinimumSize(500, 400)

    def init_ui(self):
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.create_controls()
        self.create_table()
        self.add_widgets_to_layout()

    def create_controls(self):
        # Calendar
        self.calendar = QCalendarWidget()
        self.calendar.setMinimumSize(200, 170)
        self.calendar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # Time selector
        self.l_time = QLabel(self.tr('Time, hour'))
        self.cb_time = QComboBox()
        self.cb_time.addItem('0-24', '24/7')
        for hour in range(24):
            self.cb_time.addItem(f"{hour}-{hour + 1}", f"{hour}:00:00")
        self.cb_time.setMinimumWidth(100)
        self.cb_time.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cb_time.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Search button
        self.btn_search = QPushButton(self.tr('Search'))
        self.btn_search.setFixedSize(100, 30)

    def create_table(self):
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            self.tr('Date'), self.tr('Time'), self.tr('Drone'), self.tr('Angle')
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(150)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        for i in range(self.table.columnCount()):
            self.table.horizontalHeaderItem(i).setTextAlignment(Qt.AlignCenter)
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)

    def add_widgets_to_layout(self):
        spacerItem = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)

        # Calendar layout
        calendar_layout = QVBoxLayout()
        calendar_layout.addWidget(self.calendar, alignment=Qt.AlignCenter)

        # Time layout
        time_layout = QVBoxLayout()
        time_layout.addWidget(self.l_time, alignment=Qt.AlignCenter | Qt.AlignTop)
        time_layout.addWidget(self.cb_time, alignment=Qt.AlignCenter | Qt.AlignTop)
        time_layout.addItem(spacerItem)

        # Button layout
        btn_layout = QVBoxLayout()
        btn_layout.addWidget(self.btn_search, alignment=Qt.AlignCenter | Qt.AlignTop)

        # Top controls layout
        controls_layout = QHBoxLayout()
        controls_layout.addLayout(calendar_layout)
        controls_layout.addSpacing(20)
        controls_layout.addLayout(time_layout)
        controls_layout.addSpacing(20)
        controls_layout.addLayout(btn_layout)
        controls_layout.setContentsMargins(10, 10, 10, 10)

        # Final assembly
        self.main_layout.addLayout(controls_layout)
        self.main_layout.addWidget(self.table)
        self.main_layout.addStretch()
        self.main_layout.setSpacing(10)

    def resize_table(self, row_count: int):
        self.table.setRowCount(row_count)

    def request_status_update(self, status: bool):
        if status:
            for i in range(self.table.columnCount()):
                self.table.setItem(0, i, QTableWidgetItem(''))
        else:
            no_data = [self.tr('No'), self.tr('warnings'), self.tr('at this'), self.tr('time!')]
            for i, text in enumerate(no_data):
                self.table.setItem(0, i, self._make_item(text))

    def receive_requested_data(self, dataframe):
        if len(dataframe):
            self.resize_table(len(dataframe))
            self.request_status_update(True)
            for i in range(len(dataframe)):
                for j in range(self.table.columnCount()):
                    item = self._make_item(str(dataframe.iloc[i, j]))
                    self.table.setItem(i, j, item)
        else:
            self.resize_table(1)
            self.request_status_update(False)

    def _make_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        return item


class AdminSettings(QWidget):
    signal_peleng_shift_angles = pyqtSignal(dict)

    def __init__(self, logger_):
        super().__init__()
        self.logger = logger_
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setLayout(self.main_layout)

        self.create_widgets()
        self.add_widgets_to_layout()

    def create_widgets(self):
        self.box_shift_angle = QGroupBox(self.tr('Peleng shift angle'))

        self.box_2G4 = QGroupBox(self.tr('2.4 GHz'))
        self.l_current_angle_2G4 = QLabel(self.tr('Current angle'))
        self.spb_current_angle_2G4 = QSpinBox()
        self.spb_current_angle_2G4.setReadOnly(True)
        self.l_new_angle_2G4 = QLabel(self.tr('New angle'))
        self.spb_new_angle_2G4 = QSpinBox()
        self.spb_new_angle_2G4.setRange(-30, 30)
        self.spb_new_angle_2G4.setSingleStep(1)
        self.spb_new_angle_2G4.setValue(0)

        self.box_5G8 = QGroupBox(self.tr('5.8 GHz'))
        self.l_current_angle_5G8 = QLabel(self.tr('Current angle'))
        self.spb_current_angle_5G8 = QSpinBox()
        self.spb_current_angle_5G8.setReadOnly(True)
        self.l_new_angle_5G8 = QLabel(self.tr('New angle'))
        self.spb_new_angle_5G8 = QSpinBox()
        self.spb_new_angle_5G8.setRange(-30, 30)
        self.spb_new_angle_5G8.setSingleStep(1)
        self.spb_new_angle_5G8.setValue(0)

        self.btn_set_new_angle = QPushButton(self.tr('Set new angle'))
        self.btn_set_new_angle.clicked.connect(self.btn_set_new_angle_clicked)

    def add_widgets_to_layout(self):
        box_correct_angle_layout_2G4 = QVBoxLayout()
        cur_angle_layout_2G4 = QHBoxLayout()
        cur_angle_layout_2G4.addWidget(self.l_current_angle_2G4)
        cur_angle_layout_2G4.addSpacing(20)
        cur_angle_layout_2G4.addWidget(self.spb_current_angle_2G4, alignment=Qt.AlignRight)
        new_angle_layout_2G4 = QHBoxLayout()
        new_angle_layout_2G4.addWidget(self.l_new_angle_2G4)
        new_angle_layout_2G4.addSpacing(20)
        new_angle_layout_2G4.addWidget(self.spb_new_angle_2G4, alignment=Qt.AlignRight)
        box_correct_angle_layout_2G4.addLayout(cur_angle_layout_2G4)
        box_correct_angle_layout_2G4.addSpacing(10)
        box_correct_angle_layout_2G4.addLayout(new_angle_layout_2G4)
        self.box_2G4.setLayout(box_correct_angle_layout_2G4)

        box_correct_angle_layout_5G8 = QVBoxLayout()
        cur_angle_layout_5G8 = QHBoxLayout()
        cur_angle_layout_5G8.addWidget(self.l_current_angle_5G8)
        cur_angle_layout_5G8.addSpacing(20)
        cur_angle_layout_5G8.addWidget(self.spb_current_angle_5G8, alignment=Qt.AlignRight)
        new_angle_layout_5G8 = QHBoxLayout()
        new_angle_layout_5G8.addWidget(self.l_new_angle_5G8)
        new_angle_layout_5G8.addSpacing(20)
        new_angle_layout_5G8.addWidget(self.spb_new_angle_5G8, alignment=Qt.AlignRight)
        box_correct_angle_layout_5G8.addLayout(cur_angle_layout_5G8)
        box_correct_angle_layout_5G8.addSpacing(10)
        box_correct_angle_layout_5G8.addLayout(new_angle_layout_5G8)
        self.box_5G8.setLayout(box_correct_angle_layout_5G8)

        boxes_2G4_5G8 = QHBoxLayout()
        boxes_2G4_5G8.addWidget(self.box_2G4)
        boxes_2G4_5G8.addWidget(self.box_5G8)

        box_shift_angle_layout = QVBoxLayout()
        box_shift_angle_layout.addLayout(boxes_2G4_5G8)
        box_shift_angle_layout.addWidget(self.btn_set_new_angle)
        self.box_shift_angle.setLayout(box_shift_angle_layout)

        self.main_layout.addWidget(self.box_shift_angle)

    def set_current_angles(self, new_angles: dict):
        self.spb_current_angle_2G4.setValue(new_angles['2400'])
        self.spb_current_angle_5G8.setValue(new_angles['5800'])

    def btn_set_new_angle_clicked(self):
        dict_to_send = {'2400': self.spb_new_angle_2G4.value(), '5800': self.spb_new_angle_5G8.value()}
        self.signal_peleng_shift_angles.emit(dict_to_send)


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    window = SettingsWidget()
    window.show()
    sys.exit(app.exec())
