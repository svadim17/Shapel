import math
from PyQt5.QtWidgets import QDockWidget, QWidget, QHBoxLayout, QPushButton, QSpacerItem, QSizePolicy, QVBoxLayout, \
    QColorDialog, QDialog, QLabel, QSlider, QSpinBox, QGroupBox
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QSignalMapper
from submodules.basic import Dron


class DronsCtrlWidget(QDockWidget, QWidget):
    # signal_slider_gain_changed = pyqtSignal(bool)
    signal_drons_config_changed = pyqtSignal(dict)
    signal_threshold_changed = pyqtSignal(int)
    signal_btn_random_signals = pyqtSignal(bool)
    signal_gains_changed = pyqtSignal(dict)

    def __init__(self, drons: list, threshold: int):
        super().__init__()
        self.setWindowTitle(self.tr('Drones'))
        self.setWidget(QWidget())

        # drons.pop(0)
        # drons.pop(5)
        self.main_layout = QVBoxLayout()  # create vertical layout for buttons
        self.main_layout.setAlignment(Qt.AlignTop)
        self.widget().setLayout(self.main_layout)
        self.dron_counter = 0
        self.drons = drons

        self.btn_dron_settings = [None] * len(drons)
        self.color_rect = [None] * len(drons)
        self.dialogs = [None] * len(drons)

        self.mapper_open_gain_settings = QSignalMapper()
        self.mapper_set_color = QSignalMapper()
        for dron in drons:
            btn_name = (dron.name).replace('-2.4G', '').replace('-5.8G', '')
            self.btn_dron_settings[self.dron_counter] = QPushButton(btn_name)  # create buttons
            self.btn_dron_settings[self.dron_counter].setCheckable(False)
            self.dialogs[self.dron_counter] = Drons_detect_settings(dron)
            self.dialogs[self.dron_counter].signal_gain_changed.connect(self.update_config)
            self.mapper_open_gain_settings.setMapping(self.btn_dron_settings[self.dron_counter], self.dron_counter)
            self.btn_dron_settings[self.dron_counter].clicked.connect(
                self.mapper_open_gain_settings.map)  # send signal to open threshold settings

            self.color_rect[self.dron_counter] = QPushButton()  # create widget for color rectangles
            self.mapper_set_color.setMapping(self.color_rect[self.dron_counter], self.dron_counter)
            self.color_rect[self.dron_counter].clicked.connect(self.mapper_set_color.map)
            self.color_rect[self.dron_counter].setStyleSheet(f"background-color: rgb({dron.color[0]},"
                                                             f" {dron.color[1]},"
                                                             f" {dron.color[2]})")

            self.dron_counter += 1

        self.customize_btns()
        self.add_widgets_to_layout()

        self.mapper_open_gain_settings.mapped[int].connect(self.open_gain_settings)
        self.mapper_set_color.mapped[int].connect(self.set_color)

        self.main_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.change_btn_color(True, [], [])

    def customize_btns(self):
        for i in range(len(self.btn_dron_settings)):
            self.btn_dron_settings[i].setMaximumWidth(160)
            self.btn_dron_settings[i].setMinimumWidth(135)
            self.btn_dron_settings[i].setFixedHeight(33)
            self.color_rect[i].setFixedSize(17, 33)

    def add_widgets_to_layout(self):
        self.box_2g4 = QGroupBox(self.tr('2.4 GHz'))
        self.box_5g8 = QGroupBox(self.tr('5.8 GHz'))

        btns_24_layout = QVBoxLayout()
        btns_24_layout.setAlignment(Qt.AlignTop)
        btns_58_layout = QVBoxLayout()
        btns_58_layout.setAlignment(Qt.AlignTop)

        for i in range(int(len(self.btn_dron_settings) / 2)):
            if not (i == 0 or i == 6):
                temp_layout_1 = QHBoxLayout()
                temp_layout_1.addWidget(self.color_rect[i])
                temp_layout_1.addWidget(self.btn_dron_settings[i])
                btns_24_layout.addLayout(temp_layout_1)

                temp_layout_2 = QHBoxLayout()
                temp_layout_2.addWidget(self.color_rect[int(len(self.btn_dron_settings) / 2) + i])
                temp_layout_2.addWidget(self.btn_dron_settings[int(len(self.btn_dron_settings) / 2) + i])
                btns_58_layout.addLayout(temp_layout_2)

        self.box_2g4.setLayout(btns_24_layout)
        self.box_5g8.setLayout(btns_58_layout)

        self.main_layout.addWidget(self.box_2g4)
        self.main_layout.addWidget(self.box_5g8)

    def set_calibration(self, coeff: list):
        for i in range(len(self.dialogs)):
            self.dialogs[i].set_calibration(coeff[i])

    def set_color(self, a):
        color = QColorDialog.getColor()
        rgb_color = (color.red(), color.green(), color.blue())
        self.color_rect[a].setStyleSheet(f"background-color : rgb{rgb_color}")
        self.drons[a].color = list(rgb_color)

        self.signal_drons_config_changed.emit(self.drons[a].collect())

    def update_gains(self, gains: list):
        updated_dron_name = gains.pop(0)
        for index, dron in enumerate(self.drons):
            if dron.name == updated_dron_name:
                dron_index = index
                break
            else:
                return
        self.dialogs[dron_index].set_gains(gains)

    def update_config(self, a):
        self.signal_drons_config_changed.emit(a)

    def change_btn_color(self, status: bool, numb_of_exceed_signals: list, new_btn_colors: list):
        # Change button color on default
        for i in range(len(self.btn_dron_settings)):
            self.btn_dron_settings[i].setStyleSheet("color: ; background-color: ")

        # Change button color on warning color
        if status:
            for i in range(len(numb_of_exceed_signals)):
                color = new_btn_colors[i]
                self.btn_dron_settings[numb_of_exceed_signals[i]].setStyleSheet(f"color: rgb(0, 0, 0);"
                                                                                f" background-color:"
                                                                                f" rgb({color[0]}, {color[1]}, {color[2]})")

    def open_gain_settings(self, num):
        self.dialogs[num].show()


class Drons_detect_settings(QDialog):
    signal_gain_changed = pyqtSignal(dict)

    def __init__(self, dron: Dron):
        super().__init__()
        self.dron = dron
        self.setWindowTitle(self.dron.name + self.tr(' |  Gain'))
        self.setFixedSize(QSize(270, 370))
        # self.move(40, 100)
        sliders_layout = QVBoxLayout()
        self.setLayout(sliders_layout)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        if self.parent():
            parent_center = self.parent().geometry().center()
            self.move(parent_center - self.rect().center())

        self.sectors = len(self.dron.gains)

        # Initialization of sliders
        self.label_slider_ant = [None] * self.sectors
        self.label_slider_value = [None] * self.sectors
        self.slider_ant = [None] * self.sectors
        self.slider_layout = [None] * self.sectors

        # Add sliders for every antenna (count = 6)
        for i in range(self.sectors):
            # Add numering for sliders
            self.slider_layout[i] = QHBoxLayout()
            self.label_slider_ant[i] = QLabel(str(i + 1))
            self.label_slider_ant[i].setStyleSheet("font-size: 15pt; color: rgb(255, 184, 65)")
            self.slider_layout[i].addWidget(self.label_slider_ant[i])

            self.slider_ant[i] = QSlider(Qt.Horizontal)  # create horizontal slider
            self.slider_ant[i].setTickPosition(QSlider.TicksBelow)  # enable ticks below
            self.slider_ant[i].setRange(0, 100)
            self.slider_ant[i].setValue(self.dron.gains[i])
            self.slider_layout[i].addWidget(self.slider_ant[i])

            # Change the size of a handle slider
            slider_style = "QSlider::handle {width: 24px;}"
            self.slider_ant[i].setStyleSheet(slider_style)

            # Set up connection for show real value of slider
            self.label_slider_value[i] = QLabel(str(self.slider_ant[i].value()))
            self.slider_layout[i].addWidget(self.label_slider_value[i])
            self.slider_ant[i].valueChanged.connect(lambda value, index=i: self.on_slider_value_changed(index, value))
            sliders_layout.addLayout(self.slider_layout[i])

        # Add reset gain controls
        self.l_spb_reset = QLabel(self.tr('All gains'))
        self.spb_reset_gain = QSpinBox()
        self.spb_reset_gain.setFixedSize(70, 30)
        self.spb_reset_gain.setRange(0, 200)
        self.spb_reset_gain.setSingleStep(1)
        self.spb_reset_gain.setValue(self.dron.gains[0])
        self.spb_reset_gain.setStyleSheet("QSpinBox::up-button {height: 20px;}"
                                          "QSpinBox::down-button {height: 20px;}")
        self.spb_reset_gain.valueChanged.connect(self.event_reset_gains)

        reset_settings_layout = QVBoxLayout()
        reset_settings_layout.setAlignment(Qt.AlignCenter)
        reset_settings_layout.addWidget(self.l_spb_reset)
        reset_settings_layout.addWidget(self.spb_reset_gain)
        sliders_layout.addLayout(reset_settings_layout)

    def event_reset_gains(self):
        for i in range(len(self.slider_ant)):
            self.slider_ant[i].setValue(self.spb_reset_gain.value())
        self.dron.gains = self.get_gains()

    def set_calibration(self, coeff):

        for i in range(len(self.slider_ant)):
            self.dron.gains[i] = math.ceil(self.dron.gains[i] * float(coeff))
            self.slider_ant[i].setValue(self.dron.gains[i])
        self.signal_gain_changed.emit(self.dron.collect())

    def get_gains(self):
        gains = []
        for slider in self.slider_ant:
            gains.append(slider.value())
        return gains

    def set_gains(self, gains):
        for i in range(len(self.slider_ant)):
            self.slider_ant[i].setValue(gains[i])

    # def closeEvent(self, event):
    #     self.dron.gains = self.get_gains()
    #     # print('self.dron.gains = ', self.dron.gains)
    #     self.signal_gain_changed.emit(self.dron.collect())

    def on_slider_value_changed(self, index, value):
        self.label_slider_value[index].setText(str(value))
        self.dron.gains[index] = value
        self.signal_gain_changed.emit(self.dron.collect())

    def showEvent(self, event):
        for i in range(len(self.slider_ant)):
            self.slider_ant[i].setValue(self.dron.gains[i])
