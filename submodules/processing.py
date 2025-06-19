import copy
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSlot, pyqtSignal
from datetime import datetime
from submodules.basic import *


class Processor(QtCore.QObject):
    sig_sector_levels = pyqtSignal(Sector_levels)
    sig_peleng = pyqtSignal(list)
    sig_peleng_new = pyqtSignal(list)
    sig_filtered_pelengs = pyqtSignal(list)
    sig_spectrum = pyqtSignal(Packet_spectrum)
    sig_warning = pyqtSignal(bool, list, list)
    sig_warning_logWidget = pyqtSignal(str)
    sig_warning_database = pyqtSignal(list)
    sig_warning_sound = pyqtSignal(int)
    sig_auto_threshold = pyqtSignal(int)
    sig_calibration_coeff = pyqtSignal(list)
    sig_progrBar_value = pyqtSignal(int, int)
    sig_drons_config_changed = pyqtSignal(dict)
    sig_norm_levels_and_pelengs = pyqtSignal(Packet_levels, list)
    sig_exceeded_sectors = pyqtSignal(list)

    def __init__(self, config: dict, dron_config: dict, logger_):
        super().__init__()
        self.dron_config = dron_config
        self.get_config(config)
        self.logger = logger_
        self.get_drons_config(dron_config)
        self.full_pack_2D = np.zeros((self.sectors, self.number_of_drons), dtype=np.int32)
        self.last_pelens = None
        self.deviation = 8              # WARNING (NEED TO TEST) !!!!!!!!!!!!!!!!!
        self.flag_warning = 0
        self.averaging_levels_flag = True
        self.averaging_pelengs_flag = False
        self.record_flag = False
        self.receive_counter = 666      # 666 for off auto-correction on start
        self.receive_accum = []
        self.extra_auto_gains = [None] * self.number_of_drons
        self.time_for_one_receive = 0.205           # in seconds for 1 antenna
        self.calibration_time = 30
        self.numb_of_auto_receives = 0
        self.no_warning_counter = 0
        self.no_warning_comparator = 50    # counter comparing with comparator to refresh buttons colors

    def change_average_flag(self, state: bool):
        self.averaging_levels_flag = state

    def get_config(self, conf: dict):
        self.config = conf
        self.sectors = self.config['number_of_sectors']
        self.threshold = self.config['threshold']
        self.calibr_coeff = self.config['calibration_coefficients']
        self.a_24 = self.config['peleng_coefficients'][24]['a']
        self.b_24 = self.config['peleng_coefficients'][24]['b']
        self.a_58 = self.config['peleng_coefficients'][58]['a']
        self.b_58 = self.config['peleng_coefficients'][58]['b']
        self.averaging_levels_flag = self.config['debug']['average_levels_for_peleng']
        self.sensivity_coeff = self.config['sensivity_coeff']
        # self.calibration_time = self.config['debug']['calibration_time']

    def get_drons_config(self, conf: dict):
        self.config_drons = conf
        self.drons = [Dron(key, value) for key, value in self.config_drons.items()]
        self.number_of_drons = len(self.config_drons.keys())
        self.colors = [dron.color for dron in self.drons]
        self.drones_name = [dron.name for dron in self.drons]

    def change_threshold(self, value: int):
        self.threshold = value

    def change_calibration_time(self, value):
        self.calibration_time = value
        self.numb_of_auto_receives = int(self.calibration_time / self.time_for_one_receive)
        while self.numb_of_auto_receives % 6 != 0:
            self.numb_of_auto_receives += 1

    def change_record_flag(self, status: bool):
        self.record_flag = status
        if status:
            self.record_file = open('records/' + datetime.now().strftime("record %d_%m_%y %H_%M") + '.txt', 'w')
        else:
            self.record_file.close()

    def data_log(self, packet: Packet_levels):
        self.record_file.write(f'{str(packet._asdict())}\n')

    def normalize_levels(self, packet: Packet_levels) -> Packet_levels:
        data = []
        for i in range(len(packet.values)):
            data.append(int(packet.values[i] / self.calibr_coeff[self.drons[i].frequency][packet.antenna-1]))
        return Packet_levels(packet.antenna, data)

    def amplifying_levels(self, packet: Packet_levels) -> Packet_levels:
        for i in range(len(packet.values)):
            packet.values[i] *= self.drons[i].gains[packet.antenna-1]
        return packet

    def update_gains(self, drons_gains: list):
        name_of_changed = drons_gains.pop(0)
        for i in range(len(self.drons)):
            if self.drons[i].name == name_of_changed:
                self.drons[i].gains = drons_gains

    def send_calibration_coeff(self):
        self.sig_calibration_coeff.emit(self.extra_auto_gains)
        self.logger.info(f'Calibration extra gains were sent')

    def find_sectors_for_peleng(self) -> list[Data_for_peleng]:
        max_signals = []
        max_dron_value = 0
        max_dron_antenna = None
        max_nearest_dron_value = 0
        max_nearest_dron_antenna = None
        full_pack_2D = np.transpose(self.full_pack_2D)
        for i in range(self.number_of_drons):
            for j in range(self.sectors):
                if full_pack_2D[i][j] >= max_dron_value:  # search max values (why +.any() - secret)
                    max_dron_value = full_pack_2D[i][j]
                    max_dron_antenna = j + 1
                    if (j + 1) == self.sectors:
                        temp_index = 0
                        if full_pack_2D[i][temp_index] >= full_pack_2D[i][j - 1]:  # !!!!! what will be if
                            max_nearest_dron_value = full_pack_2D[i][temp_index]  # max - first or last element !!!!!
                            max_nearest_dron_antenna = temp_index + 1
                        else:
                            max_nearest_dron_value = full_pack_2D[i][j - 1]
                            max_nearest_dron_antenna = j
                    elif (j - 1) < 0:
                        temp_index = self.sectors - 1
                        if full_pack_2D[i][j + 1] >= full_pack_2D[i][temp_index]:  # !!!!! what will be if
                            max_nearest_dron_value = full_pack_2D[i][j + 1]  # max - first or last element !!!!!
                            max_nearest_dron_antenna = j + 2
                        else:
                            max_nearest_dron_value = full_pack_2D[i][j - 1]
                            max_nearest_dron_antenna = temp_index + 1
                    else:
                        if full_pack_2D[i][j + 1] >= full_pack_2D[i][j - 1]:  # !!!!! what will be if
                            max_nearest_dron_value = full_pack_2D[i][j + 1]  # max - first or last element !!!!!
                            max_nearest_dron_antenna = j + 2
                        else:
                            max_nearest_dron_value = full_pack_2D[i][j - 1]
                            max_nearest_dron_antenna = j

            max_signals.append(Data_for_peleng(max_dron_antenna, max_dron_value,
                                               max_nearest_dron_antenna, max_nearest_dron_value))

            max_dron_value = 0
            max_nearest_dron_value = 0
        return max_signals

    def calculate_peleng(self, packets: list[Data_for_peleng]) -> list[Peleng]:
        '''Рассчёт угла для отрисовки пеленга'''
        pelengs = []
        numb_of_leds = [None] * len(packets)
        value_left, value_right, antenna_right, antenna_left = None, None, None, None
        for i in range(len(packets)):
            if packets[i].max_antenna == self.sectors and packets[i].nearest_antenna == 1:
                value_right = packets[i].nearest_value
                value_left = packets[i].max_value
                antenna_right = packets[i].nearest_antenna
                antenna_left = packets[i].max_antenna
            elif packets[i].max_antenna == 1 and packets[i].nearest_antenna == self.sectors:
                value_right = packets[i].max_value
                value_left = packets[i].nearest_value
                antenna_right = packets[i].max_antenna
                antenna_left = packets[i].nearest_antenna
            elif packets[i].max_antenna > packets[i].nearest_antenna:
                value_right = packets[i].max_value
                value_left = packets[i].nearest_value
                antenna_right = packets[i].max_antenna
                antenna_left = packets[i].nearest_antenna
            elif packets[i].max_antenna < packets[i].nearest_antenna:
                value_right = packets[i].nearest_value
                value_left = packets[i].max_value
                antenna_right = packets[i].nearest_antenna
                antenna_left = packets[i].max_antenna

            mini_angle = 0
            if 2400 == self.drons[i].frequency:
                denominator = value_left + value_right
                if denominator != 0:
                    mini_angle = ((value_right - value_left) / denominator) * self.a_24
                else:
                    self.logger.trace(f'Can`t calculate angle for {self.drons[i].name} 2.4G due to zero denominator')
            elif 5800 == self.drons[i].frequency:
                denominator = value_left + value_right
                if denominator != 0:
                    mini_angle = ((value_right - value_left) / denominator) * self.a_58
                else:
                    self.logger.trace(f'Can`t calculate angle for {self.drons[i].name} 5.8G due to zero denominator')
            else:
                # вызывается деление на 0, когда диапазон неизвестен
                self.logger.error(f'Unknown frequency for calculate peleng!')

            if mini_angle < -30:
                mini_angle = -30
            elif mini_angle > 30:
                mini_angle = 30

            angle = antenna_left * 360 / self.sectors - self.deviation/2 + mini_angle

            power = value_left + value_right

            pelengs.append(Peleng(self.drons[i].name, self.drons[i].color, angle, power))

        return pelengs

    def average_levels(self, packet: Packet_levels):
        if self.averaging_levels_flag:
            avr_lvls = self.full_pack_2D[packet.antenna - 1] * 0.5 + np.array(packet.values) * 0.5
            self.full_pack_2D[packet.antenna - 1][:] = avr_lvls.astype('int32')
        else:
            self.full_pack_2D[packet.antenna - 1][:] = packet.values

    def average_pelengs(self, pelengs: list[Peleng]):
        aver_pelengs = []
        if self.last_pelens is None:
            self.last_pelens = pelengs
            return pelengs
        else:
            for i in range(len(pelengs)):
                angle = self.last_pelens[i].angle * 0.3 + pelengs[i].angle * 0.7
                power = self.last_pelens[i].power * 0.3 + pelengs[i].power * 0.7
                aver_pelengs.append(Peleng(pelengs[i].name, pelengs[i].color, angle, power))
            self.last_pelens = aver_pelengs
        # print(aver_pelengs)
        return aver_pelengs

    def filter_pelengs(self, pelengs: list[Peleng]):
        pelengs_filtered = []
        i = 0
        numb_of_exceed_signals = []
        warning_msg = ''
        warning_list = []
        warnings_colors = []
        for peleng in pelengs:
            if peleng.power >= self.threshold:
                pelengs_filtered.append(peleng)
                numb_of_exceed_signals.append(i)
                warning_msg += f'Angle: {int(peleng.angle - 30)}°  {peleng.name} |'
                warning_dict = {}
                warning_dict['date'] = str(datetime.now().date())
                warning_dict['time'] = datetime.now().strftime("%H:%M:%S")
                warning_dict['name'] = peleng.name
                warning_dict['angle'] = int(peleng.angle)
                warning_list.append(warning_dict)
                warnings_colors.append(peleng.color)
                self.no_warning_counter = 0
            else:
                """ This for refreshing buttons colors if no warnings on duration of self.no_warning_comparator """
                self.no_warning_counter += 1
                if self.no_warning_counter == self.no_warning_comparator:
                    self.sig_warning.emit(False, [], [])
                    self.no_warning_counter = 0
            i += 1

        if len(pelengs_filtered):
            self.sig_warning_logWidget.emit(warning_msg)
            self.sig_warning_database.emit(warning_list)
            self.sig_warning.emit(True, numb_of_exceed_signals, warnings_colors)
            self.sig_filtered_pelengs.emit(pelengs_filtered)
            self.find_max_pelen_power(pelengs_filtered)

    def find_max_pelen_power(self, pelengs: list[Peleng]):
        max_peleng_power = 0
        for peleng in pelengs:
            if peleng.power > max_peleng_power:
                max_peleng_power = peleng.power
        self.sig_warning_sound.emit(max_peleng_power)

    def find_exceeded_sectors(self, pelengs: list[Peleng]):
        exceeded_sectors = []
        for peleng in pelengs:
            exceeded_sectors.append(int((peleng.angle) // (360 / self.sectors)))
        self.sig_exceeded_sectors.emit(exceeded_sectors)

    def reset_receive_counter(self):
        self.logger.info('Calibration started')
        self.receive_counter = 0
        self.receive_accum.clear()
        self.numb_of_auto_receives = int(self.calibration_time / self.time_for_one_receive)
        while self.numb_of_auto_receives % 6 != 0:
            self.numb_of_auto_receives += 1

    def fit_signals_to_threshold(self):
        self.numb_of_auto_receives = int(self.calibration_time / self.time_for_one_receive)
        while self.numb_of_auto_receives % 6 != 0:
            self.numb_of_auto_receives += 1

        dron_values = np.zeros((self.number_of_drons, self.numb_of_auto_receives), dtype=np.int32)    # init 2D array

        # Collect values for every dron (count = 'accum_numb' values for every dron)
        for j in range(self.number_of_drons):
            for i in range(self.numb_of_auto_receives):
                dron_values[j][i] = self.receive_accum[i][j]        # 2D array (8x60)

        for i in range(self.number_of_drons):
            self.extra_auto_gains[i] = (self.threshold * self.sensivity_coeff) / (max(dron_values[i]))

        self.send_calibration_coeff()

    def auto_calibration(self, ampl_levels):
        # # # Calibration # # #
        if self.receive_counter < self.numb_of_auto_receives:                   # counter for every antenna
            self.receive_accum.append(ampl_levels)
            self.receive_counter += 1
            self.sig_progrBar_value.emit(self.receive_counter, self.numb_of_auto_receives)
        elif self.receive_counter == self.numb_of_auto_receives:
            self.fit_signals_to_threshold()
            self.receive_counter = self.numb_of_auto_receives + 6666          # for turn off accumulation

    @pyqtSlot(Packet_levels)
    def receive_levels(self, packet: Packet_levels):
        if self.record_flag:
            self.data_log(packet)
        norm_lvls = self.normalize_levels(packet)
        ampl_lvls = self.amplifying_levels(copy.deepcopy(norm_lvls))

        self.auto_calibration(ampl_levels=ampl_lvls.values)     # calibration
        self.sig_sector_levels.emit(Sector_levels(ampl_lvls.antenna, self.drones_name, self.colors, ampl_lvls.values))
        self.average_levels(ampl_lvls)

        # Process pelengs
        if ampl_lvls.antenna == self.sectors:
            pelengs = self.calculate_peleng(self.find_sectors_for_peleng())
            if self.averaging_pelengs_flag:
                average_pelengs = self.average_pelengs(pelengs)
                self.sig_peleng.emit(average_pelengs)
                self.filter_pelengs(average_pelengs)
            else:
                self.sig_peleng.emit(pelengs)
                self.filter_pelengs(pelengs)
        else:
            pelengs = []
        self.sig_norm_levels_and_pelengs.emit(norm_lvls, pelengs)
