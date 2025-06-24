import os
from PyQt5 import Qt
from PyQt5.QtCore import Qt, QSize, QTimer, QThread
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont
from submodules.basic import *
from datetime import datetime
from PyQt5.QtGui import QIcon
from PyQt5.QtSerialPort import QSerialPortInfo
from submodules.connection import get_available_ports, SerialSpinTread


class RecordCalibration(QDockWidget, QWidget):

    def __init__(self, config, drons_config, logger_):
        super().__init__()
        self.config = config
        self.config_drons = drons_config
        self.logger = logger_
        self.setWindowTitle(self.tr('Record Calibration'))

        self.spinner = SerialSpinTread(logger_)
        self.spinner.signal_ready.connect(self.on_spinner_ready)  # Подключаем сигнал здесь
        self.spinner.signal_spin_done.connect(self.on_angle_set_done)

        self.sectors = self.config['number_of_sectors']
        self.drons_names = [self.config_drons[key]['name'] for key in self.config_drons.keys()]
        self.number_of_drons = len(self.drons_names)

        self.setWidget(QWidget(self))
        self.main_layout = QVBoxLayout()
        self.widget().setLayout(self.main_layout)

        self.create_controls()
        self.add_widgets_to_layout()

        self.accum_numb = self.spb_accum_numb.value()
        self.selected_drone = self.cb_type_of_drone.currentText()
        self.selected_drone_ind = 0
        self.selected_degree = self.spb_degree.value()

        self.accum_packet = [[] for _ in range(self.sectors)]
        self.accum_counter = 666
        self.accum_status = False

        self.accum_norm_packet = [[] for _ in range(self.sectors)]
        self.accum_pelengs = []
        self.accum_pelengs_new_formula = []
        self.accum_norm_counter = 666
        self.accum_norm_status = False

        self.accum_done_flag = {'default_packet': False, 'norm_packet': False}

        self.autospin_status = False
        self.auto_record_status = False

        self.event_update_ports_name()

    def create_controls(self):
        self.box_settings = QGroupBox(self.tr('Main settings'))

        self.l_type_of_drone = QLabel(self.tr('Selected drone'))
        self.cb_type_of_drone = QComboBox()
        for i in range(self.number_of_drons):
            self.cb_type_of_drone.addItem(self.drons_names[i])
        self.cb_type_of_drone.currentTextChanged.connect(self.selected_drone_changed)

        self.l_filename = QLabel(self.tr('Filename'))
        self.le_filename = QLineEdit()

        self.l_selected_degree = QLabel(self.tr('Selected degree'))
        self.spb_degree = QSpinBox()
        self.spb_degree.setSuffix(' °')
        self.spb_degree.setFixedSize(QSize(120, 40))
        self.spb_degree.setRange(-360, 360)
        self.spb_degree.setSingleStep(1)
        self.spb_degree.setValue(0)
        self.spb_degree.valueChanged.connect(self.selected_degree_changed)

        self.l_accum_numb = QLabel(self.tr('Accumulation number'))
        self.spb_accum_numb = QSpinBox()
        # self.spb_accum_numb.setFixedSize(QSize(120, 40))
        self.spb_accum_numb.setRange(1, 50)
        self.spb_accum_numb.setSingleStep(1)
        self.spb_accum_numb.setValue(5)
        self.spb_accum_numb.valueChanged.connect(self.accum_numb_changed)

        self.box_autospin = QGroupBox(self.tr('Autospin settings'))

        self.l_port_name = QLabel(self.tr('Port name'))
        self.cb_port_name = QComboBox()
        self.cb_port_name.setFixedWidth(120)
        self.btn_update_port_name = QPushButton()
        self.btn_update_port_name.setIcon(QIcon(r'assets/icons/refresh.png'))
        self.btn_update_port_name.setFixedSize(26, 26)
        self.btn_update_port_name.clicked.connect(self.event_update_ports_name)

        self.btn_close_port = QPushButton(self.tr('Close COM port'))
        self.btn_close_port.clicked.connect(self.spinner.close_serial_port)

        self.l_degree_step = QLabel(self.tr('Degree step'))
        self.spb_degree_step = QSpinBox()
        self.spb_degree_step.setSuffix(' °')
        # self.spb_degree_step.setFixedWidth(120)
        self.spb_degree_step.setRange(-180, 180)
        self.spb_degree_step.setSingleStep(1)
        self.spb_degree_step.setValue(5)

        self.l_chb_autospin = QLabel(self.tr('Autospin'))
        self.chb_autospin = QCheckBox()
        self.chb_autospin.setChecked(False)
        self.chb_autospin.stateChanged.connect(self.chb_autospin_clicked)

        self.btn_record = QPushButton(self.tr('Record'))
        self.btn_record.setFixedSize(QSize(120, 30))
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self.btn_record_clicked)

        self.save_status = QLabel()

        self.progressBar = QProgressBar()
        self.progressBar.setFixedHeight(12)
        self.progressBar.setMinimumWidth(150)
        # self.progressBar.setFixedSize(420, 10)
        self.progressBar.setStyleSheet("border: 2px solid grey;")

        self.progressBar_norm = QProgressBar()
        self.progressBar_norm.setFixedHeight(12)
        self.progressBar_norm.setMinimumWidth(150)
        # self.progressBar.setFixedSize(420, 10)
        self.progressBar_norm.setStyleSheet("border: 2px solid grey;")

    def add_widgets_to_layout(self):
        selected_drone_layout = QVBoxLayout()
        selected_drone_layout.addWidget(self.l_type_of_drone)
        selected_drone_layout.addWidget(self.cb_type_of_drone)

        filename_layout = QVBoxLayout()
        filename_layout.addWidget(self.l_filename)
        filename_layout.addWidget(self.le_filename)

        selected_degree_layout = QVBoxLayout()
        selected_degree_layout.addWidget(self.l_selected_degree)
        selected_degree_layout.addWidget(self.spb_degree)

        accum_numb_layout = QVBoxLayout()
        accum_numb_layout.addWidget(self.l_accum_numb)
        accum_numb_layout.addWidget(self.spb_accum_numb)

        first_line_layout = QHBoxLayout()
        first_line_layout.addLayout(selected_drone_layout)
        first_line_layout.addSpacing(50)
        first_line_layout.addLayout(filename_layout)

        second_line_layout = QHBoxLayout()
        second_line_layout.addLayout(selected_degree_layout)
        second_line_layout.addSpacing(50)
        second_line_layout.addLayout(accum_numb_layout)

        box_settings_layout = QVBoxLayout()
        box_settings_layout.addLayout(first_line_layout)
        box_settings_layout.addSpacing(10)
        box_settings_layout.addLayout(second_line_layout)
        self.box_settings.setLayout(box_settings_layout)

        port_name_layout = QHBoxLayout()
        port_name_layout.addWidget(self.cb_port_name)
        port_name_layout.addWidget(self.btn_update_port_name)
        port_name_layout.addWidget(self.btn_close_port)
        degree_step_layout = QVBoxLayout()
        degree_step_layout.addWidget(self.l_degree_step)
        degree_step_layout.addWidget(self.spb_degree_step)
        chb_autospin_layout = QVBoxLayout()
        chb_autospin_layout.addWidget(self.l_chb_autospin)
        chb_autospin_layout.addWidget(self.chb_autospin)
        second_line_layout = QHBoxLayout()
        second_line_layout.addLayout(degree_step_layout)
        second_line_layout.addLayout(chb_autospin_layout)

        box_autospin_layout = QVBoxLayout()
        box_autospin_layout.setAlignment(Qt.AlignLeft)
        box_autospin_layout.addWidget(self.l_port_name)
        box_autospin_layout.addLayout(port_name_layout)
        box_autospin_layout.addSpacing(10)
        box_autospin_layout.addLayout(second_line_layout)
        self.box_autospin.setLayout(box_autospin_layout)

        self.main_layout.addWidget(self.box_autospin)
        self.main_layout.addWidget(self.box_settings)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.btn_record, alignment=Qt.AlignCenter)
        self.main_layout.addSpacing(5)
        self.main_layout.addWidget(self.save_status, alignment=Qt.AlignCenter)
        self.main_layout.addWidget(self.progressBar)
        self.main_layout.addWidget(self.progressBar_norm)

        self.main_layout.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def chb_autospin_clicked(self, state):
        self.autospin_status = bool(state)

    def selected_drone_changed(self, value: str):
        self.selected_drone = value
        self.selected_drone_ind = self.cb_type_of_drone.currentIndex()

    def selected_degree_changed(self, value: int):
        self.selected_degree = value

    def accum_numb_changed(self, value: int):
        self.accum_numb = value

    def btn_record_clicked(self, status):
        if status:
            if self.autospin_status:
                self.spinner.set_port(port_name=self.cb_port_name.currentText())
                self.spinner.start()
            else:
                self.start_accumulation()
        else:
            self.accum_status = False
            self.accum_norm_status = False
            self.auto_record_status = False
            self.clear_accumulation()
            self.save_status.setText(self.tr('Stopped'))
            try:
                self.spinner.stop()
            except Exception as e:
                self.logger.error(f'Error with stopping spinner thread: {e}')

    def on_spinner_ready(self):
        self.logger.success("Spinner is ready, sending angle...")
        angle = str(self.spb_degree.value())
        QTimer.singleShot(500, lambda: self.spinner.signal_set_angle.emit(angle))

    def on_angle_set_done(self, success: bool):
        if success:
            QTimer.singleShot(1000, self.start_accumulation)
        else:
            self.auto_record_status = False
            self.btn_record.setChecked(False)
            self.save_status.setText(self.tr('Failed to rotate spinner'))

    def start_accumulation(self):
        self.accum_status = True
        self.accum_norm_status = True
        self.auto_record_status = True
        self.save_status.setText(self.tr('Saving...'))

    def event_update_ports_name(self):
        self.cb_port_name.clear()
        for i in get_available_ports():
            self.cb_port_name.addItem(i)

    def change_value_progressBar(self, value):
        self.progressBar.setMaximum(self.accum_numb * self.sectors)
        if value == 666:
            self.progressBar.setValue(0)
        else:
            current_value = self.progressBar.value() + value
            self.progressBar.setValue(current_value)

    def change_value_progressBar_norm(self, value):
        self.progressBar_norm.setMaximum(self.accum_numb * self.sectors)

        if value == 666:
            self.progressBar_norm.setValue(0)
        else:
            current_value = self.progressBar_norm.value() + value
            self.progressBar_norm.setValue(current_value)

    def accumulate_signals(self, packet: Packet_levels):
        if self.accum_status:
            antenna_index = int(packet.antenna) - 1
            if len(self.accum_packet[antenna_index]) < self.accum_numb:
                self.accum_packet[antenna_index].append(packet.values[self.selected_drone_ind])
                self.change_value_progressBar(value=1)

            # проверка завершения накопления
            if all(len(self.accum_packet[i]) == self.accum_numb for i in range(self.sectors)):
                self.accum_status = False
                self.logger.info('Acccumulation of input signals finished!')
                self.on_accumulation_complete(is_norm=False)

    def clear_accumulation(self):
        for i in range(self.sectors):
            self.accum_packet[i] = []
            self.accum_packet[i] = []
        self.progressBar.setValue(0)
        self.progressBar_norm.setValue(0)

    def accumulate_norm_signals(self, packet: Packet_levels, pelengs: list, pelengs_new_formula: list):
        if self.accum_norm_status:
            antenna_index = int(packet.antenna) - 1
            if len(self.accum_norm_packet[antenna_index]) < self.accum_numb:
                self.accum_norm_packet[antenna_index].append(packet.values[self.selected_drone_ind])
                if len(pelengs) != 0:
                    self.accum_pelengs.append(pelengs[self.selected_drone_ind].angle)
                if len(pelengs_new_formula) != 0:
                    self.accum_pelengs_new_formula.append(pelengs_new_formula[self.selected_drone_ind].angle)

                self.change_value_progressBar_norm(value=1)

                if (all(len(self.accum_norm_packet[i]) == self.accum_numb for i in range(self.sectors))
                        and len(self.accum_pelengs) == self.accum_numb and len(self.accum_pelengs_new_formula) == self.accum_numb):
                    self.accum_norm_status = False
                    self.logger.info('Acccumulation of normalized signals finished!')
                    self.on_accumulation_complete(is_norm=True)

    def on_accumulation_complete(self, is_norm: bool):
        if is_norm:
            aver_peleng = self.average_pelengs(self.accum_pelengs)
            aver_peleng_new_formula = self.average_pelengs(self.accum_pelengs_new_formula)
            self.save_norm_data_to_file(self.average_accumulation(self.accum_norm_packet), aver_peleng, aver_peleng_new_formula)
            self.accum_norm_packet = [[] for _ in range(self.sectors)]
            self.accum_pelengs = []
            self.change_value_progressBar_norm(value=666)
            self.accum_done_flag['norm_packet'] = True
        else:
            self.save_data_to_file(self.average_accumulation(self.accum_packet))
            self.accum_packet = [[] for _ in range(self.sectors)]
            self.change_value_progressBar(value=666)
            self.accum_done_flag['default_packet'] = True

        if self.accum_done_flag['norm_packet'] and self.accum_done_flag['default_packet']:
            self.accum_done_flag = {'norm_packet': False, 'default_packet': False}        # сброс
            # После сохранения – если автоспин активен, передвинуться и ждать готовности
            if self.auto_record_status:
                new_degree = self.spb_degree.value() + self.spb_degree_step.value()
                if new_degree > 360 or new_degree < -360:
                    self.auto_record_status = False
                    self.save_status.setText(self.tr("Circle finished!"))
                    self.btn_record.setChecked(False)
                    self.logger.success(f'Finished to save all degrees!')
                    return
                self.spb_degree.setValue(new_degree)
                self.save_status.setText(self.tr(f'Moving to degree: {new_degree}'))
                self.spinner.signal_set_angle.emit(str(new_degree))

    def average_accumulation(self, data):
        averaged_accum = []
        for i in range(self.sectors):
            averaged_accum.append(round(sum(data[i]) / len(data[i])))
        # print(averaged_accum)
        return averaged_accum

    def average_pelengs(self, data):
        return round(sum(data)) / len(data)

    def save_data_to_file(self, averaged_accum):
        try:
            filename = datetime.now().strftime(f"{self.le_filename.text()} %d-%m-%y") + '.txt'
            if not os.path.isdir('calibration_records'):
                os.mkdir('calibration_records')
            if os.path.isfile('calibration_records/' + filename):
                self.record_file = open('calibration_records/' + filename, 'a')
            else:
                self.record_file = open('calibration_records/' + filename, 'w')

            # dict_to_save = {f'{self.selected_degree}': averaged_accum}
            data_to_save = f'{self.selected_degree}\t{averaged_accum[0]}\t{averaged_accum[1]}\t{averaged_accum[2]}\t{averaged_accum[3]}\t{averaged_accum[4]}\t{averaged_accum[5]}\t{self.selected_drone}'

            print(data_to_save)
            self.record_file.write(f'{data_to_save}\n')
            self.record_file.close()
            self.save_status.setText(self.tr('Successful saved!'))
            logger.success('Calibration data saved successful')
        except Exception as e:
            logger.error(f'Error with save calibration data: {e}')
            self.save_status.setText(self.tr('ERROR !'))

    def save_norm_data_to_file(self, averaged_accum, peleng, peleng_new_formula):
        try:
            filename = datetime.now().strftime(f"{self.le_filename.text()}_norm %d-%m-%y") + '.txt'

            if not os.path.isdir('calibration_records'):
                os.mkdir('calibration_records')
            if os.path.isfile('calibration_records/' + filename):
                self.record_file = open('calibration_records/' + filename, 'a')
            else:
                self.record_file = open('calibration_records/' + filename, 'w')

            # dict_to_save = {f'{self.selected_degree}': averaged_accum}
            data_to_save = f'{self.selected_degree}\t{averaged_accum[0]}\t{averaged_accum[1]}\t{averaged_accum[2]}\t{averaged_accum[3]}\t{averaged_accum[4]}\t{averaged_accum[5]}\t{self.selected_drone}\t{peleng}\t{peleng_new_formula}'

            print(data_to_save)
            self.record_file.write(f'{data_to_save}\n')
            self.record_file.close()
            self.save_status.setText(self.tr('Successful saved!'))
            logger.success('Calibration data saved successful')
        except Exception as e:
            logger.error(f'Error with save calibration data: {e}')
            self.save_status.setText(self.tr('ERROR !'))
