import struct
import threading
import time
from collections import deque
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
import ipaddress


# Define constants for port settings
PARITY_NONE, PARITY_EVEN, PARITY_ODD, PARITY_MARK, PARITY_SPACE = 'N', 'E', 'O', 'M', 'S'
STOPBITS_ONE, STOPBITS_ONE_POINT_FIVE, STOPBITS_TWO = (1, 1.5, 2)
FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS = (5, 6, 7, 8)


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
    signal_fpvScope_packet = QtCore.pyqtSignal(dict)
    signal_fpvData_packet = QtCore.pyqtSignal(dict)
    signal_success_change_ip = QtCore.pyqtSignal(bool)
    signal_new_calibr_coeff = QtCore.pyqtSignal(dict)
    signal_fpvScope_thresholds = QtCore.pyqtSignal(list, str)
    signal_peleng_shift_angles = QtCore.pyqtSignal(dict)

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

    def is_open(self):                  # check (open or not)
        pass

    def open(self, ip_address: str, port: str):
        port = int(port)
        self.logger.info(f'Connecting to {ip_address}:{port}')

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(5)       # in seconds
        self.run_flag = True
        # self.client.connect((address))
        try:
            self.client.connect((ip_address, port))
            self.logger.success(f'Connected to {ip_address}:{port}')
            self.start()
            self.send_cmd_for_calibr_coeff()
            self.msleep(100)
            self.send_cmd_for_fpvScope_thresholds()
            self.msleep(100)
            self.send_cmd_to_receive_detect_settings()
            self.msleep(100)
            self.send_cmd_for_shift_angles()
        except Exception as e:
            self.logger.error(f'Can\'t connect to {ip_address}:{port}')

    def close(self):
        self.run_flag = False
        self.client.close()

    def set_baudrate(self, value):          # define data transfer rate
        pass

    def set_timeout(self, value):           # timeout to wait data
        self.thread_timeout = value

    def unpack_frequencies(self, freq_numb, freq_samples):
        if freq_numb in self.actual_numb_of_freq_drons:
            self.logger.trace(f'freq_numb= {freq_numb}\nsamples= {freq_samples}')
            self.frequencies_packet.update({freq_numb: freq_samples})
        if len(self.frequencies_packet) == self.number_of_drons_on_low_freq + self.number_of_drons_on_high_freq:
            self.signal_frequencies.emit(self.frequencies_packet)

    def unpack_data(self, type_of_packet: int, sector_number: int, data):
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

    def is_valid_new_ip(self, ip: str, port: str) -> bool:
        ip_status, port_status = False, False
        try:
            ipaddress.IPv4Address(ip)
            ip_status = True
        except ValueError:
            return False
        if 49152 < int(port) < 65535:
            port_status = True
        else:
            return False
        if ip_status and port_status:
            return True

    def send_cmd_to_receive_detect_settings(self):
        try:
            command = b'\x0a\x0d\xab\x00'
            self.client.send(command)
            self.logger.info(f'Command {command} to receive detect settings was sent.')
        except Exception as e:
            self.logger.error(f'Error with sending command to receive detect settings.')
        self.msleep(100)

    def send_cmd_for_shift_angles(self):
        try:
            command = b'\x0a\x0d\xa2\x00'
            self.client.send(command)
            self.logger.info(f'Command {command} to receive peleng shift angles was sent.')
        except Exception as e:
            self.logger.error(f'Error with sending command to receive peleng shift angles.')
        self.msleep(100)

    def send_detect_settings(self):
        try:
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
            self.logger.info(f'Threshold and gains were sent by command {command}')
        except Exception as e:
            self.logger.error(f'Error with sending threshold and gains! {e}')
        self.msleep(100)

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
            self.logger.error(f'Error sending data: {str(e)}')

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
            self.logger.error(f'Error sending data: {e}')

    def send_command_to_change_ip(self, new_ip: str, new_port: str):
        try:
            if self.is_valid_new_ip(new_ip, new_port):
                sender = b'\x0a'
                receiver = b'\x0d'
                code = b'\x10'
                data_length = b'\x06'
                ip_big_endian = socket.inet_aton(new_ip)
                port = struct.pack('<H', int(new_port))

                command = sender + receiver + code + data_length + ip_big_endian + port
                self.client.send(command)
                self.logger.info(f'Requested for changing IP address on {new_ip}:{new_port} ...')
            else:
                self.logger.error(f'Invalid new IP address or port!')
        except Exception as e:
            self.logger.error(f'Error with request for change IP! {e}')

    def send_cmd_for_calibr_coeff(self):
        try:
            sender = b'\x0a'
            receiver = b'\x0d'
            code = b'\xad'
            command = sender + receiver + code
            self.client.send(command)
            self.logger.info(f'Requested for calibration coefficients.')
        except Exception as e:
            self.logger.error(f'Error with request for calibration coefficients! {e}')

    def send_cmd_for_fpvScope_thresholds(self):
        try:
            sender = b'\x0a'
            receiver = b'\x0d'
            code = b'\xae'
            data_length = b'\x00'
            command = sender + receiver + code + data_length
            self.client.send(command)
            self.logger.info(f'Requested for all FPV Scope thresholds ...')
        except Exception as e:
            self.logger.error(f'Error with request for all FPV Scope thresholds! {e}')

    def send_all_fpvScope_thresholds(self, values: list[int]):
        try:
            sender = b'\x0a'
            receiver = b'\x0d'
            code = b'\xae'
            data_length = (len(values)).to_bytes(1, 'little')
            values_in_bytes = bytes(values)
            command = sender + receiver + code + data_length + values_in_bytes
            self.client.send(command)
            self.logger.info(f'All FPV Scope thresholds were sent.')
        except Exception as e:
            self.logger.error(f'Error with sending all FPV Scope thresholds! {e}')

    def send_fpvScope_threshold(self, index: int, value: int):
        try:
            sender = b'\x0a'
            receiver = b'\x0d'
            code = b'\xaf'
            index_in_bytes = index.to_bytes(1, 'little')
            value_in_bytes = value.to_bytes(1, 'little')
            command = sender + receiver + code + index_in_bytes + value_in_bytes
            self.client.send(command)
            self.logger.info(f'FPV Scope threshold was sent.')
        except Exception as e:
            self.logger.error(f'Error with sending FPV Scope threshold! {e}')

    def send_cmd_to_change_fpvScope_mode(self, mode: str, freq_index: int):
        try:
            sender = b'\x0a'
            receiver = b'\x0d'
            code = b'\xa1'
            command = bytes()
            if mode == 'auto':
                fpv_mode = b'\x01'
                command = sender + receiver + code + fpv_mode
                self.client.send(command)
            elif mode == 'manual':
                fpv_mode = b'\x02'
                freq_index_in_bytes = freq_index.to_bytes(1, 'little')
                command = sender + receiver + code + fpv_mode + freq_index_in_bytes
            self.client.send(command)
            self.logger.info(f'FPV Scope mode was sent on {mode}.')
        except Exception as e:
            self.logger.error(f'Error with sending FPV Scope threshold! {e}')

    def send_peleng_shift_angles(self, new_angles: dict):
        try:
            sender = b'\x0a'
            receiver = b'\x0d'
            code = b'\xa2'
            length = b'\x02'
            angle_2G4 = new_angles['2400'].to_bytes(1, 'little', signed=True)
            angle_5G8 = new_angles['5800'].to_bytes(1, 'little', signed=True)
            command = sender + receiver + code + length + angle_2G4 + angle_5G8
            self.client.send(command)
            self.logger.info(f'New peleng shift angles were sent: {new_angles}')
        except Exception as e:
            self.logger.error(f'Error with sending new peleng shift angles! {e}')

    def handle_data_packet(self):
        type_of_packet = int.from_bytes(self.recv_exact(1), 'little')
        sector_number = int.from_bytes(self.recv_exact(1), 'little')
        packet_length = int.from_bytes(self.recv_exact(4), 'little')

        if type_of_packet == 3:
            end_flag_length = 8
        else:
            end_flag_length = 4

        data = self.recv_exact(packet_length + end_flag_length)
        self.unpack_data(type_of_packet, sector_number, data)

    def handle_freq_packet(self, freq_numb):
        self.logger.info('Reading frequencies from controller ...')

        freq_samples = []
        freq_numb = int.from_bytes(freq_numb, 'little') - 207
        freq_length = int.from_bytes(self.recv_exact(1), 'little')
        for i in range(int(freq_length / 2)):  # because 2 bytes on every frequency
            freq_samples.append(int.from_bytes(self.client.recv(2), 'big'))
        self.unpack_frequencies(freq_numb, freq_samples)

    def handle_detect_settings(self):
        self.logger.info('Reading detect settings.')

        data_length = self.recv_exact(1)
        if data_length == b'\x4a':
            threshold = int.from_bytes(self.recv_exact(2), 'little')
            gains = []
            for i in range(self.number_of_drons * self.sectors):
                gains.append(int.from_bytes(self.recv_exact(1), 'little'))
            end_mark = int.from_bytes(self.recv_exact(4), 'little')
            self.logger.info(f'New threshold from server: {threshold}')
            self.logger.info(f'New gains from server: {gains}')
            self.collect_data_from_server(threshold, gains)

    def handle_fpv_data(self):
        try:
            data_length = int.from_bytes(self.recv_exact(1), 'little')
            all_fpv_data = self.recv_exact(data_length)

            # Unpack data
            fpv_data = {}
            offset = 0
            while offset + 2 <= len(all_fpv_data):          # 5 bytes for sector(1), ADC(2) and dispersion(2)
                sector = all_fpv_data[offset]
                average_ADC_value = int.from_bytes(all_fpv_data[offset + 1:offset + 2], 'little')
                fpv_data.update({sector: average_ADC_value})
                offset += 2

            self.signal_fpvData_packet.emit(fpv_data)
            # print(f'FPV Data packet: {fpv_data}')
        except Exception as e:
            self.logger.error(f'Error with handle FPV Data! {e}')

    def handle_fpvScope_data(self):
        try:
            # self.logger.trace('Reading FPV Scope data.')
            data_length = int.from_bytes(self.recv_exact(2), 'little')
            all_freqs_data = self.recv_exact(data_length)

            # Unpack data
            if len(all_freqs_data) % 6 != 0:
                self.logger.warning(f'Unexpected fpvScope data length: {len(all_freqs_data)} not divisible by 6.')

            num_blocks = len(all_freqs_data) // 6
            fpvScope_data = {'1G2': [], '3G3': [], '5G8': []}
            for i in range(num_blocks):
                offset = i * 6
                freq = int.from_bytes(all_freqs_data[offset:offset + 2], 'little')
                rssi = int.from_bytes(all_freqs_data[offset + 2:offset + 4], 'little')
                fpv_coeff = int.from_bytes(all_freqs_data[offset + 4:offset + 6], 'little')
                packet = {'freq': freq, 'rssi': rssi, 'fpv_coeff': fpv_coeff}
                if 1080 <= freq <= 1258:
                    fpvScope_data['1G2'].append(packet)
                elif 1080 <= freq <= 1258:
                    fpvScope_data['3G3'].append(packet)
                elif 4990 <= freq <= 6028:
                    fpvScope_data['5G8'].append(packet)

            self.signal_fpvScope_packet.emit(fpvScope_data)
            # print(f'FPV Scope Data packet: {fpvScope_data}')
        except Exception as e:
            self.logger.error(f'Error with handle FPV Scope data! {e}')

    def handle_new_ip_response(self):
        try:
            data_length = self.recv_exact(1)
            status = self.recv_exact(1)
            if status == b'\x00':
                self.logger.success(f'IP address changed!')
                self.signal_success_change_ip.emit(True)
            elif status == b'\x01':
                self.logger.error(f'Error with changing IP address!')
            else:
                self.logger.error(f'Unknown response: {status.hex()}')
        except Exception as e:
            self.logger.error(f'Error with handle setting up new IP response! {e}')

    def handle_change_gain_response(self):
        try:
            status = self.recv_exact(1)
            if status == b'\x00':
                self.logger.success(f'Remote control applied new threshold and gains!')
            else:
                self.logger.warning(f'Remote control didn`t apply new threshold and gains!')
        except Exception as e:
            self.logger.error(f'Error with handle changing gain response! {e}')

    def handle_calibr_coeff(self):
        try:
            calibr_coeff_2G4 = list(self.recv_exact(6))     # list for convert to int
            calibr_coeff_5G8 = list(self.recv_exact(6))
            for i in range(6):
                calibr_coeff_2G4[i] /= 100
                calibr_coeff_5G8[i] /= 100
            self.logger.info('Received calibration coefficients')

            new_coeffs = {2400: calibr_coeff_2G4, 5800: calibr_coeff_5G8}
            self.signal_new_calibr_coeff.emit(new_coeffs)
        except Exception as e:
            self.logger.error(f'Error with receive calibration coefficients! {e}')

    def handle_fpvScope_threshold(self):
        try:
            data_length = int.from_bytes(self.recv_exact(1), 'little')
            if data_length != 1:
                all_thresholds = list(self.recv_exact(data_length))
                self.logger.info('Received FPV Scope thresholds')
                self.signal_fpvScope_thresholds.emit(all_thresholds, 'init')
            else:
                response = self.recv_exact(1)
                self.logger.info('Remote control received all thresholds')
        except Exception as e:
            self.logger.error(f'Error with receive FPV Scope thresholds! {e}')

    def handle_peleng_shift_angles(self):
        try:
            length = int.from_bytes(self.recv_exact(1), 'little')
            if length == 2:
                shift_angles = self.recv_exact(length)
                shift_angles_dict = {'2400': int.from_bytes(shift_angles[0:1], 'little', signed=True),
                                     '5800': int.from_bytes(shift_angles[1:2], 'little', signed=True)}
                self.logger.info(f'Received peleng shift angles: {shift_angles_dict}')
                self.signal_peleng_shift_angles.emit(shift_angles_dict)
            elif length == 1:
                self.logger.info(f'Peleng shift angles were set successful!')
            else:
                self.logger.error(f'Unknown response length from setting peleng shift angles!')
        except Exception as e:
            self.logger.error(f'Error with receive peleng shift angles! {e}')

    def recv_exact(self, n):
        data = b''
        while len(data) < n:
            packet = self.client.recv(n - len(data))
            if not packet:
                raise ConnectionError("Connection lost during recv_exact.")
            data += packet
        return data

    def run(self):
        buffer = bytearray()    # for check start marker
        while self.run_flag:
            try:
                byte = self.client.recv(1)
                if not byte:
                    self.logger.warning('TCP: empty packet, it can be disconnected!')
                    continue

                buffer.append(byte[0])
                if len(buffer) > 4:
                    buffer.pop(0)

                if bytes(buffer) == b'\xff\xff\xff\xff':
                    self.handle_data_packet()
                    buffer.clear()
                    continue

                if byte == b'\x0d':
                    try:
                        if self.recv_exact(1) == b'\x0a':
                            cmd = self.recv_exact(1)
                            if b'\xd0' <= cmd <= b'\xe7':
                                self.handle_freq_packet(cmd)        # frequency packet
                            elif cmd == b'\xab':
                                self.handle_detect_settings()       # detect settings packet
                            elif cmd == b'\x0e':
                                self.handle_fpv_data()              # fpv data packet
                            elif cmd == b'\x0f':
                                self.handle_fpvScope_data()              # fpvScope data packet
                            elif cmd == b'\x10':
                                self.handle_new_ip_response()
                            elif cmd == b'\xaa':
                                self.handle_change_gain_response()      # response about receive new threshold and gains
                            elif cmd == b'\xad':
                                self.handle_calibr_coeff()
                            elif cmd == b'\xae':
                                self.handle_fpvScope_threshold()
                            elif cmd == b'\xa2':
                                self.handle_peleng_shift_angles()
                            else:
                                self.logger.warning(f'Received unknown code: {cmd.hex()}')
                    except Exception as e:
                        self.logger.warning(f'Error parsing command: {e}')
                        continue

                self.msleep(self.thread_timeout)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError) as e:
                self.logger.error(f'Connection closed unexpectedly: {e}')
                self.run_flag = False
                break
            except Exception as e:
                self.logger.error(f'Critical error in TCP thread: {e}')
                self.run_flag = False
                break


class EmulationTread(QtCore.QThread):

    signal_levels = QtCore.pyqtSignal(basic.Packet_levels)
    signal_spectrum = QtCore.pyqtSignal(dict)
    signal_frequencies = QtCore.pyqtSignal(dict)
    signal_threshold = QtCore.pyqtSignal(int)
    signal_calibration = QtCore.pyqtSignal(list)
    signal_drons_gains = QtCore.pyqtSignal(list)
    signal_success_change_ip = QtCore.pyqtSignal(bool)
    signal_fpvScope_packet = QtCore.pyqtSignal(dict)
    signal_fpvData_packet = QtCore.pyqtSignal(list)
    signal_new_calibr_coeff = QtCore.pyqtSignal(dict)
    signal_fpvScope_thresholds = QtCore.pyqtSignal(list)

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
    signal_fpvScope_packet = QtCore.pyqtSignal(dict)
    signal_fpvData_packet = QtCore.pyqtSignal(list)
    signal_success_change_ip = QtCore.pyqtSignal(bool)
    signal_new_calibr_coeff = QtCore.pyqtSignal(dict)
    signal_fpvScope_thresholds = QtCore.pyqtSignal(list)

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
    signal_new_calibr_coeff = QtCore.pyqtSignal(dict)
    signal_fpvScope_thresholds = QtCore.pyqtSignal(list)

    def __init__(self, logger_, port_name='COM5', baudrate=9600):
        QtCore.QThread.__init__(self)
        self.logger = logger_
        self.port_name = port_name
        self.baudrate = baudrate
        self.serial_port = None
        self.running = False

        self.signal_set_angle.connect(self.handle_angle)

    def handle_angle(self, angle: str):
        if not self.running or not self.serial_port or not self.serial_port.is_open:
            self.logger.error("Port not ready in handle_angle")
            self.signal_spin_done.emit(False)
            return
        result = self.send_new_angle(angle)
        if result == '01':
            self.logger.info("Angle set successfully.")
            self.signal_spin_done.emit(True)
        else:
            self.signal_spin_done.emit(False)
            self.logger.error("Failed to set angle.")

    def send_new_angle(self, angle: str):
        """Отправка команды на устройство"""
        retries = 3
        for attempt in range(retries):
            if not self.running or not self.serial_port or not self.serial_port.is_open:
                self.logger.error("Cannot send command to spinner: port not open or thread not running")
                return
            try:
                self.serial_port.reset_input_buffer()
                command = f"Angle:{angle}"
                self.serial_port.write(command.encode())
                self.logger.info(f"Command to spinner sent: {command.strip()}")

                # Ждем ответ (например, 1 байт подтверждения)
                start_time = time.time()
                while self.serial_port.in_waiting == 0 and (time.time() - start_time) < 5.0:
                    self.msleep(50)

                if self.serial_port.in_waiting:
                    response = self.serial_port.read(1)
                    self.logger.info(f"Received response from spinner: {response.hex()}")
                    return response.hex() if response else None
                else:
                    self.logger.warning("No response from spinner within timeout")
            except Exception as e:
                self.logger.error(f"Serial error during command: {str(e)}")

            if attempt < retries - 1:
                self.msleep(500)
        return None

    def set_port(self, port_name: str):
        self.port_name = port_name

    def open_serial_port(self):
        try:
            self.serial_port = serial.Serial(port=self.port_name, baudrate=self.baudrate, timeout=2)
            self.logger.success(f"Connected to spinner: {self.port_name}")
            self.msleep(500)
            return True
        except serial.SerialException as e:
            self.logger.error(f"SerialException on open spinner port: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"General error on open spinner port: {str(e)}")
            return False

    def close_serial_port(self):
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
                self.logger.info("Spinner serial port closed")
            except Exception as e:
                self.logger.error(f"Error closing serial spinner port: {str(e)}")
        else:
            self.logger.info(f'Spinner port is not open')
        self.serial_port = None

    def run(self):
        self.logger.info("Spinner Thread started")
        if not self.open_serial_port():
            self.running = False
            return
        self.running = True
        self.signal_ready.emit()
        try:
            while self.running:
                self.msleep(100)  # Небольшая пауза для снижения нагрузки
        except Exception as e:
            self.logger.error(f"Error in spinner thread: {str(e)}")
        finally:
            self.running = False
            self.close_serial_port()

    def stop(self):
        """ Остановка потока """
        self.running = False
        self.wait()
        self.logger.info("Spinner Thread stopped")

