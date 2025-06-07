import threading
import select
import socket
import json
import serial
import random
import enum
import numpy as np
import platform
from submodules import basic
from PyQt5 import QtCore
from PyQt5.QtSerialPort import QSerialPortInfo
from loguru import logger
import yaml


# Define constants for port settings
PARITY_NONE, PARITY_EVEN, PARITY_ODD, PARITY_MARK, PARITY_SPACE = 'N', 'E', 'O', 'M', 'S'
STOPBITS_ONE, STOPBITS_ONE_POINT_FIVE, STOPBITS_TWO = (1, 1.5, 2)
FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS = (5, 6, 7, 8)

logger.add('logs/circle.txt', level='DEBUG')


def get_available_ports():                          # find available ports
    ports = QSerialPortInfo.availablePorts()        # get info about ports
    portsName = [p.portName() for p in ports]       # get ports names
    return portsName


def list_of_tuples_to_list(data_tuple):
    flat_list = []
    for sublist in data_tuple:
        for item in sublist:
            flat_list.append(item)
    data_list = flat_list
    return data_list


class CtrlMode(enum.IntEnum):
    levels = 0
    spectrum_24 = 2
    spectrum_58 = 10
    frequencies = 0


class TCPTread(QtCore.QThread):
    signal_levels = QtCore.pyqtSignal(basic.Packet_levels)
    signal_spectrum = QtCore.pyqtSignal(dict)
    signal_frequencies = QtCore.pyqtSignal(dict)
    signal_threshold = QtCore.pyqtSignal(int)
    signal_calibration = QtCore.pyqtSignal(list)
    signal_drons_gains = QtCore.pyqtSignal(list)

    def __init__(self, calibration_coeff: dict, frequencies, thread_timeout, logger_):
        QtCore.QThread.__init__(self)
        self.logger = logger_
        self.name = 'TCP'
        self.number_of_drons = len(frequencies)
        self.thread_timeout = thread_timeout                 # data update interval (in ms)
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.run_flag = False
        self.setup_data_changed_flag = False

        self.temp_ant_for_random = 0            # var for random signals emulation
        self.full_data = {}
        self.cmd_count = 0
        self.coeff = calibration_coeff
        self.frequencies = frequencies
        self.record_file = None
        self.record_flag = False
        self.serial_mode_type = 'levels'
        self.frequencies_packet = {}
        self.setup_dict_to_send = {}
        self.sectors = 6

        self.number_of_drons_on_low_freq = int(self.number_of_drons / 2)
        self.number_of_drons_on_high_freq = 2
        self.actual_numb_of_freq_drons = [1, 2, 3, 4, 5, 6, 17, 18]

        self.gains_to_send = []
        self.threshold = None
        self.drons_gains = []
        self.drons = []
        self.conf_drons = {}
        self.config = {}
        self.read_configs()

    def send_detect_settings(self):
        self.drons_gains = []
        self.drons = []

        # Read drons gains from config
        for dict_name, conf in self.conf_drons.items():
            self.drons.append(basic.Dron(dict_name, conf))
        for i in range(len(self.drons)):
            self.drons_gains.append(self.drons[i].gains)
        self.drons_gains = sum(self.drons_gains, [])            # convert list of lists to one list

        # Read threshold from config if it is the first time
        if self.threshold is None:
            self.threshold = self.config['threshold']

        # Send data by TCP
        sender = b'\x0a'
        receiver = b'\x0d'
        code = b'\xaa'
        end_mark = b'\x5a' * 4

        threshold_in_bytes = self.threshold.to_bytes(2, 'little')
        drons_gains_in_bytes = bytes(self.drons_gains)

        data = threshold_in_bytes + drons_gains_in_bytes

        data_length = (len(data)).to_bytes(1, 'little')

        command = sender + receiver + code + data_length + data + end_mark

        self.client.send(command)
        self.logger.success(f'Threshold and gains were sent by command {command}')
        self.msleep(100)

    def receive_detect_settings(self):
        command = b'\x0a\x0d\xab\x00'
        self.logger.info(f'Sending command {command} to receive detect settings.')
        self.client.send(command)
        self.msleep(100)

    def read_configs(self):
        with open('config_drons.yaml', encoding='utf-8') as file:
            self.conf_drons = dict(yaml.load(file, Loader=yaml.SafeLoader))

        with open('config.yaml', encoding='utf-8') as file1:
            self.config = dict(yaml.load(file1, Loader=yaml.SafeLoader))

    def threshold_changed(self, value):
        self.threshold = value

    def stop_reading(self):
        self.run_flag = False
        self.client.close()

    def start_reading(self, address):
        pass

    def is_open(self):                  # check (open or not)
        pass

    def open(self, ip_address: str, port: str):
        port = int(port)
        self.logger.info(f'Connecting to {ip_address}:{port}')

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(2)       # in seconds
        self.run_flag = True
        # self.client.connect((address))
        try:
            self.client.connect((ip_address, port))
            self.logger.success(f'Connected to {ip_address}:{port}')
            self.start()
        except Exception as e:
            self.logger.error(f'Can\'t connect to {ip_address}:{port}')

    def close(self):
        self.run_flag = False
        self.client.close()

    def set_baudrate(self, value):          # define data transfer rate
        pass

    def set_timeout(self, value):           # timeout to wait data
        self.thread_timeout = value

    def set_parity(self, value):            # setting the parity bit
        pass

    def set_stopbits(self, value):          # setting a count of stop bits
        pass

    def set_bytesize(self, value):          # setting the size of byte
        pass

    def send_new_freq_to_controller(self, new_freq: dict):
        try:
            self.logger.info('Writing new frequencies to controller...')
            start_code = b'\x0a\x0d\xf1'
            sender = b'\x0a'
            receiver = b'\x0d'
            end_mark = b'\xfa' * 4
            for key, value in new_freq.items():
                freq_in_bytes = b''
                code = (key + 207).to_bytes(1, 'little')
                for i in range(len(value)):
                    freq_in_bytes += (int(value[i])).to_bytes(2, 'big')
                length = (len(freq_in_bytes)).to_bytes(1, 'little')
                data = start_code + sender + receiver + code + \
                       length + freq_in_bytes + \
                       end_mark
                self.logger.trace(f'Command to send freqs: {data.hex()}')
                self.client.send(data)

            self.logger.success('Command was sent. Starting receive...')

            self.msleep(100)
        except Exception as e:
            print(f'Error sending data: {str(e)}')

    def send_cmd_for_change_mode(self, mode: CtrlMode, type: str):
        try:
            self.logger.info(f'Changing mode on {type}')
            sender = b'\x0a'
            receiver = b'\x0d'

            if type == 'freq':
                self.frequencies_packet.clear()
                code = b'\xf0'
                data = sender + receiver + code + \
                       mode.to_bytes(1, 'little')
                self.client.send(data)

            elif (type == 'levels' or type == 'spectrum24' or
                  type == 'spectrum58'):
                code = b'\xfb'
                inf_lenght = b'\x01'
                data = sender + receiver + code + \
                       inf_lenght + \
                       mode.to_bytes(1, 'little')
                self.client.send(data)

            if type == 'freq':
                self.msleep(3000)

            self.logger.success('Command was sent. Starting receive...')
            self.msleep(100)
        except Exception as e:
            self.logger.error(f'Error sending data: {str(e)}')

    def unpack_frequencies(self, freq_numb, freq_samples):
        if freq_numb in self.actual_numb_of_freq_drons:
            self.logger.trace(f'freq_numb= {freq_numb}\nsamples= {freq_samples}')
            self.frequencies_packet.update({freq_numb: freq_samples})
        if len(self.frequencies_packet) == self.number_of_drons_on_low_freq + self.number_of_drons_on_high_freq:
            self.signal_frequencies.emit(self.frequencies_packet)
            # print(self.frequencies_packet)

    def unpack_data(self, type_of_packet: int, sector_number: int, data):
        # print('type_of_packet= ', type_of_packet)
        # print('sector_number= ', sector_number)
        # print('data= ', data.hex(' '))
        # for i in range(len(data) // 4):
        #     print(' ', int.from_bytes(data[i * 4: (i * 4) + 4], 'little'))

        if type_of_packet == 1:
            end_marker = b'\x5a\x5a\x5a\x5a'
        elif type_of_packet == 3:
            end_marker = b'\xa5\xa5\xa5\xa5\x5a\x5a\x5a\x5a'
        else:
            end_marker = b'\x5a\x5a\x5a\x5a'

        if (type_of_packet == 1) and (data[-len(end_marker):] == end_marker):
            data = data[0:-len(end_marker)]       # data without end marker
            signals_int = []
            for i in range(len(data)//4):
                signals_int.append(int.from_bytes(data[i*4: (i*4)+4], 'little'))

            signals_int = self.signlas_levels_sort(signals_int)
            # print(signals_int)
            packet = basic.Packet_levels(sector_number, signals_int)
            if packet is not None:
                self.signal_levels.emit(packet)

        elif (type_of_packet == 3) and (data[-len(end_marker):] == end_marker):
            data = data[0:-len(end_marker)]       # data without end marker
            signals = np.frombuffer(data, np.float32)
            self.signal_spectrum.emit({"antenna": sector_number, "values": signals / 1000})

    def signlas_levels_sort(self, signals):
        """ На вход функции приходит список signals из 48 элементов (16 значений низкой частоты дискретизации на 2,4ГГц,
        16 значений низкой частоты дискретизации на 5,8ГГц, 8 значений высокой частоты дискретизации на 2,4ГГц,
        8 начений высокой частоты дискретизации на 5,8ГГц). Функция отбрасывает все лишнее и создает список из 12 чисел
        (6 дронов на 2,4ГГц и 6 дронов на 5,8ГГЦ). А значения разных частот дискретизации суммируются между
        соответствующими дронами """

        signals_low_freq = signals[:self.number_of_drons_on_low_freq] + signals[16:16+self.number_of_drons_on_low_freq]
        signals_high_freq = signals[32:32+self.number_of_drons_on_high_freq] + signals[40:40+self.number_of_drons_on_high_freq]

        # Суммирование low_freq со значениями high_freq в соответствии по дронам
        signals_low_freq[2] += signals_high_freq[0]
        signals_low_freq[3] += signals_high_freq[1]
        new_signals = signals_low_freq
        return new_signals

    def collect_data_from_server(self, threshold, gains_list):
        self.signal_threshold.emit(threshold)       # apply new threshold

        # split gains list
        splitted_gains_list = [gains_list[i:i + 6] for i in range(0, len(gains_list), 6)]

        for i in range(self.number_of_drons):
            # gains_list_to_send = self.conf_drons[list(self.conf_drons.keys())[0]]['name'] + splitted_gains_list[i]
            splitted_gains_list[i].insert(0, self.conf_drons[list(self.conf_drons.keys())[i]]['name'])
            self.signal_drons_gains.emit(splitted_gains_list[i])

    def run(self):                          # run thread
        freq_marker = b''
        start_counter = 0
        start_marker = b'\xff'
        data = b''
        temp = b''
        while self.run_flag:
            # try:
            new_data = self.client.recv(1)
            if new_data == start_marker:        # compare with start byte marker
                start_counter += 1
            elif new_data == b'\x0d':
                start_counter = 0
                data = b''
                freq_samples = []
                if self.client.recv(1) == b'\x0a':
                    freq_numb = self.client.recv(1)
                    if (freq_numb >= b'\xd0') and (freq_numb <= b'\xe7'):
                        self.logger.info('Reading frequencies from controller ...')
                        self.msleep(100)
                        freq_numb = int.from_bytes(freq_numb, 'little') - 207      # % to pick one number
                        freq_length = int.from_bytes(self.client.recv(1), 'little')

                        for i in range(int(freq_length / 2)):       # because 2 bytes on every frequency
                            freq_samples.append(int.from_bytes(self.client.recv(2), 'big'))
                        self.unpack_frequencies(freq_numb, freq_samples)
                    elif freq_numb == b'\xab':
                        data_length = self.client.recv(1)
                        if data_length == b'\x4a':
                            self.logger.info('Reading detect settings.')
                            threshold = int.from_bytes(self.client.recv(2), 'little')
                            gains = []
                            for i in range(self.number_of_drons * self.sectors):
                                gains.append(int.from_bytes(self.client.recv(1), 'little'))
                            end_mark = int.from_bytes(self.client.recv(4), 'little')
                            self.logger.info(f'New threshold from server: {threshold}')
                            self.logger.info(f'New gains from server: {gains}')
                            self.collect_data_from_server(threshold, gains)
            else:
                start_counter = 0
            if start_counter == 4:  # compare with full start marker
                data = b''  # clear array
                type_of_packet = int.from_bytes(self.client.recv(1), 'little')
                sector_number = int.from_bytes(self.client.recv(1), 'little')
                packet_lenght = int.from_bytes(self.client.recv(4), 'little')
                if type_of_packet == 3:
                    end_flag_lenght = 8
                elif type_of_packet == 1:
                    end_flag_lenght = 4
                else:
                    end_flag_lenght = 4
                data = self.client.recv(packet_lenght + end_flag_lenght)

                # print(data.hex(' '))
                self.unpack_data(type_of_packet, sector_number, data)
                start_counter = 0
            # except:
            #     print('No connection!')
            #     self.signal_warning.emit('No connection!')
            self.msleep(self.thread_timeout)


class EmulationTread(QtCore.QThread):

    signal_levels = QtCore.pyqtSignal(basic.Packet_levels)
    signal_spectrum = QtCore.pyqtSignal(dict)
    signal_frequencies = QtCore.pyqtSignal(dict)
    signal_threshold = QtCore.pyqtSignal(int)
    signal_calibration = QtCore.pyqtSignal(list)
    signal_drons_gains = QtCore.pyqtSignal(list)

    def __init__(self, number_of_drons, thread_timeout, logger_):
        self.logger = logger_
        QtCore.QThread.__init__(self)
        self.name = 'Emulation'
        self.number_of_drons = number_of_drons
        self.tread_timeout = thread_timeout                 # data update interval (in ms)
        self.started_flag = False
        self.temp_ant_for_random = 0
        self.mode = CtrlMode.levels
        # self.language = self.settings.conf['view']['language']
        self.threshold = None
        self.drons_gains = []
        self.drons = []
        self.conf_drons = {}
        self.config = {}
        self.read_configs()

    def send_detect_settings(self):
        self.logger.info('Unable to send detect settings in Emulation mode!')

    def receive_detect_settings(self):
        self.logger.info('Unable to receive detect settings in Emulation mode!')

    def read_configs(self):
        with open('config_drons.yaml', encoding='utf-8') as file:
            self.conf_drons = dict(yaml.load(file, Loader=yaml.SafeLoader))

        with open('config.yaml', encoding='utf-8') as file1:
            self.config = dict(yaml.load(file1, Loader=yaml.SafeLoader))

    def threshold_changed(self, value):
        self.threshold = value

    def lang_changed(self, lang):
        self.language = lang

    def open(self, port_name: str):             # open port
        self.started_flag = True
        self.start()            # start thread
        self.logger.info(f'Recieve in mode {self.name} started!')

    def close(self):                # close port
        self.started_flag = False
        self.logger.info('Emulation stopped!')

    def is_open(self):                  # check (open or not)
        pass

    def set_baudrate(self, value):          # define data transfer rate
        pass

    def set_timeout(self, value):           # timeout in ms to wait data
        self.tread_timeout = value

    def set_parity(self, value):            # setting the parity bit
        pass

    def set_stopbits(self, value):          # setting a count of stop bits
        pass

    def set_bytesize(self, value):          # setting the size of byte
        pass

    def setup_data_changed(self, value):
        pass

    def send_new_freq_to_controller(self, new_freq: dict):
        pass

    def send_new_threshold(self, value: int):
        pass

    def send_new_calibr_coeff(self, coeff: list):
        pass

    def send_new_drons_gains(self, drons_gains: list):
        pass

    def start_reading(self):
        pass

    def stop_reading(self):
        pass

    def send_cmd_for_change_mode(self, mode: CtrlMode, type: str):
        self.mode = mode
        self.logger.info(f'{mode.name}: сommand sent!')

    def run(self):                          # run thread
        while self.started_flag:
            if self.mode == CtrlMode.levels:
                signals = [0] * self.number_of_drons
                # if checked:
                if self.temp_ant_for_random == 6:
                    self.temp_ant_for_random = 0
                for i in range(self.number_of_drons):
                    signals[i] = random.randint(5, 100)
                self.temp_ant_for_random += 1
                pack = basic.Packet_levels(antenna=self.temp_ant_for_random, values=signals)
                self.signal_levels.emit(pack)
            elif self.mode == CtrlMode.spectrum_24 or self.mode == CtrlMode.spectrum_58:
                if self.temp_ant_for_random == 6:
                    self.temp_ant_for_random = 0
                self.temp_ant_for_random += 1
                self.signal_spectrum.emit({"antenna": self.temp_ant_for_random,
                                           "values": random.sample(range(1, 1025), 1024)})
            self.msleep(self.tread_timeout)


class PlayerTread(QtCore.QThread):

    signal_levels = QtCore.pyqtSignal(basic.Packet_levels)
    signal_spectrum = QtCore.pyqtSignal(dict)
    signal_end_file = QtCore.pyqtSignal(bool)
    signal_frequencies = QtCore.pyqtSignal(dict)
    signal_threshold = QtCore.pyqtSignal(int)
    signal_calibration = QtCore.pyqtSignal(list)
    signal_drons_gains = QtCore.pyqtSignal(list)

    def __init__(self, number_of_drons, record, thread_timeout, logger_):
        self.logger = logger_
        QtCore.QThread.__init__(self)
        self.name = 'Player'
        self.number_of_drons = number_of_drons
        self.thread_timeout = thread_timeout               # data update interval (in ms)
        self.started_flag = False
        self.temp_ant_for_random = 0
        self.mode = CtrlMode.levels
        self.player_record = 'records/' + record
        self.file_position = 0
        self.threshold = None
        self.drons_gains = []
        self.drons = []
        self.conf_drons = {}
        self.config = {}
        self.read_configs()
        # self.notification_end_file = RecordEnd()
        # self.language = self.settings.conf['view']['language']

    def send_detect_settings(self):
        self.logger.info('This function is available only in TCP mode!')

    def receive_detect_settings(self):
        self.logger.info('This function is available only in TCP mode!')

    def read_configs(self):
        with open('config_drons.yaml', encoding='utf-8') as file:
            self.conf_drons = dict(yaml.load(file, Loader=yaml.SafeLoader))

        with open('config.yaml', encoding='utf-8') as file1:
            self.config = dict(yaml.load(file1, Loader=yaml.SafeLoader))

    def threshold_changed(self, value):
        self.threshold = value

    def lang_changed(self, lang):
        self.language = lang

    def is_open(self):                  # check (open or not)
        pass

    def set_baudrate(self, value):          # define data transfer rate
        pass

    def set_timeout(self, value):           # timeout in ms to wait data
        self.thread_timeout = value

    def set_parity(self, value):            # setting the parity bit
        pass

    def set_stopbits(self, value):          # setting a count of stop bits
        pass

    def set_bytesize(self, value):          # setting the size of byte
        pass

    def setup_data_changed(self, value):
        pass

    def send_new_freq_to_controller(self, new_freq: dict):
        pass

    def send_new_threshold(self, value: int):
        pass

    def send_new_calibr_coeff(self, coeff: list):
        pass

    def send_new_drons_gains(self, drons_gains: list):
        pass

    def open(self, port_name: str):             # open port
        self.started_flag = True
        self.start()            # start thread
        self.logger.success(f'Recieve in mode {self.name} started!')

    def close(self):                # close port
        self.started_flag = False
        self.logger.info('Playback stopped!')
        self.file_position = 0

    def send_cmd_for_change_mode(self, mode: CtrlMode, type: str):
        self.logger.info('This function is available only in TCP mode!')

    def record_changed(self, record):
        self.player_record = 'records/' + record
        print(self.player_record)

    def start_reading(self):
        pass

    def stop_reading(self):
        pass

    def run(self):
        with open(self.player_record, 'r') as f:                         # run thread
            # file_position = 0
            while self.started_flag:
                if self.mode == CtrlMode.levels:
                    try:
                        f.seek(self.file_position)           # go to position
                        line = eval(f.readline())
                        self.file_position = f.tell()        # get postion
                    except:
                        self.close()
                        # self.notification_end_file.show()
                        self.signal_end_file.emit(True)

                    pack = basic.Packet_levels(antenna=line['antenna'],
                                        values=line['values'])
                    try:
                        self.signal_levels.emit(pack)
                    except:
                        self.started_flag = False
                elif self.mode == CtrlMode.spectrum_24 or self.mode == CtrlMode.spectrum_58:
                    try:
                        f.seek(self.file_position)  # go to position
                        line = eval(f.readline())
                        self.file_position = f.tell()  # get postion
                    except:
                        self.close()
                    try:
                        self.signal_spectrum.emit({"antenna": line['antenna'],
                                                   "values": line['values']})
                    except:
                        self.close()
                self.msleep(self.thread_timeout)


class SerialSpinTread(QtCore.QThread):
    signal_set_angle = QtCore.pyqtSignal(str)
    signal_spin_done = QtCore.pyqtSignal(bool)
    signal_ready = QtCore.pyqtSignal()

    def __init__(self, logger_, port_name='COM5', baudrate=9600):
        QtCore.QThread.__init__(self)
        self.logger = logger_
        self.port_name = port_name
        self.baudrate = baudrate
        self.serial_port = None
        self.running = False

        self.signal_set_angle.connect(self.handle_angle)

    def handle_angle(self, angle: str):
        result = self.send_new_angle(angle)
        self.signal_spin_done.emit(result == '01')

    def send_new_angle(self, angle: str):
        """Отправка команды на устройство"""
        if not self.running or not self.serial_port or not self.serial_port.is_open:
            self.logger.error("Cannot send command to spinner: port not open or thread not running")
            return
        try:
            command = f"Angle:{angle}\r\n"
            self.serial_port.write(command.encode())
            self.logger.trace(f"Command to spinner sent: {command.strip()}")
            response = self.serial_port.read(1)
            return response.hex() if response else None

        except Exception as e:
            self.logger.error(f"Serial error during command: {str(e)}")
            return None

    def set_port(self, port_name: str):
        self.port_name = port_name

    def run(self):
        self.logger.trace("Spinner Thread started")
        try:
            self.serial_port = serial.Serial(port=self.port_name, baudrate=self.baudrate, timeout=1)
            self.logger.success(f"Connected to spinner: {self.port_name}")
            self.running = True
            self.signal_ready.emit()        # show that port is open

            while self.running:
                self.msleep(100)  # Небольшая пауза для снижения нагрузки
        except serial.SerialException as e:
            self.logger.error(f"Spinner serial error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                self.logger.info("Spinner serial port closed")

    def stop(self):
        """Остановка потока"""
        self.running = False
        self.wait()

