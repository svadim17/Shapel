from PyQt5 import Qt, QtGui
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QApplication, QPushButton, QGridLayout, QLabel, QScrollArea, QFrame, QSizePolicy, QDialog,
                             QSpinBox, QGroupBox)
from PyQt5.QtMultimedia import QCameraInfo, QCamera
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtCore import Qt, pyqtSignal, QSize
import numpy as np
import pyqtgraph as pg
from pyqtgraph import LinearRegionItem
import yaml
import math
from submodules.select_fpv_scope_mode import FPVScopeModeWindow


class FPVScopeWidget(QDockWidget, QWidget):
    signal_freq_point_clicked = pyqtSignal(int, str)
    signal_exceed_threshold = pyqtSignal(bool)
    signal_threshold_change = pyqtSignal(int, int)
    signal_all_thresholds_change = pyqtSignal(list)
    signal_fpvScope_mode = pyqtSignal(str, int)
    signal_change_radio_btn = pyqtSignal(bool)

    def __init__(self, configuration_conf: dict, delay_on_max: int, logger_):
        super().__init__()
        self.logger = logger_
        self.setWindowTitle(self.tr('FPV Scope'))
        self.configuration_conf = configuration_conf
        self.freqs_dict = configuration_conf['fpv_scope_frequencies']
        self.fpv_default_values = configuration_conf['fpv_scope_default_values']
        self.manual_mode = False
        self.selected_up_index = None
        self.increase_thr = 10

        self.freqs, self.freqs_len, self.thresholds, self.x_indices = self.get_data_from_dict()
        self.fpv_coeff_values = np.random.uniform(1, 10, self.freqs_len)
        self.fpv_rssi_values = np.random.uniform(1, 5, self.freqs_len)

        self.fpvModeWidnow = FPVScopeModeWindow(wait_time=delay_on_max)
        self.fpvModeWidnow.signal_manual_mode_chosen.connect(self.change_mode_on_manual)
        self.fpvModeWidnow.signal_increase_threshold.connect(self.increase_exceeded_threshold)

        self.central_widget = QWidget(self)
        self.setWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.create_graph()
        self.add_widgets_to_layout()

    def get_data_from_dict(self):
        frequencies = []
        threshold_values = []
        for band in self.freqs_dict.values():
            for freq_dict in band:
                freq = list(freq_dict.keys())[0]
                threshold = freq_dict[freq]['threshold']
                frequencies.append(freq)
                threshold_values.append(threshold)

        sorted_indices = np.argsort(frequencies)
        frequencies = np.array(frequencies)[sorted_indices]
        threshold_values = np.array(threshold_values)[sorted_indices]
        n = len(frequencies)
        x_indices = np.arange(n)
        return frequencies, n, threshold_values.tolist(), x_indices

    def create_graph(self):
        self.graphWindow = pg.GraphicsLayoutWidget()
        self.graphWindow.setWindowTitle(self.tr('Frequencies'))
        self.plot = self.graphWindow.addPlot()
        self.plot.vb.setMouseEnabled(x=False, y=False)
        self.plot.setLabel('bottom', self.tr('Frequency (MHz)'))
        self.plot.setLabel('left', 'Value (%)')
        self.plot.setYRange(-2, 102)

        # Настраиваем вертикальные метки на оси X
        axis = self.plot.getAxis('bottom')
        axis.setStyle(tickFont=QFont('Arial', 9))
        str_freqs = []
        for i in range(len(self.freqs)):
            if i % 3 == 0:
                str_freqs.append(str(self.freqs[i]))
            else:
                str_freqs.append('')

        axis.setTicks([[(i, freq) for i, freq in enumerate(str_freqs)]])

        self.add_background_regions()
        self.create_graph_widgets()

    def create_graph_widgets(self):
        # Линия вверх
        self.fpv_coeff_line = pg.PlotDataItem(
            x=self.x_indices,
            y=self.fpv_coeff_values,
            pen=pg.mkPen(color='b', width=2),
            name='FPV coeff'
        )
        self.plot.addItem(self.fpv_coeff_line)

        self.fpv_coeff_scatter = pg.ScatterPlotItem(
            x=self.x_indices,
            y=self.fpv_coeff_values,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(255, 255, 255, 180),
            size=10,
            symbol='o'
        )
        self.fpv_coeff_scatter.sigClicked.connect(self.on_upward_point_clicked)
        self.plot.addItem(self.fpv_coeff_scatter)

        # Линия вниз
        self.rssi_line = pg.PlotDataItem(
            x=self.x_indices,
            y=self.fpv_rssi_values,
            pen=pg.mkPen(color='y', width=2),
            name='RSSI'
        )
        self.plot.addItem(self.rssi_line)

        # Линия порога
        self.threshold_line = pg.PlotDataItem(
            x=self.x_indices,
            y=self.thresholds,
            pen=pg.mkPen(color='r', style=Qt.PenStyle.DashLine, width=2),
            name='Threshold'
        )
        self.plot.addItem(self.threshold_line)

        # Узлы для порога
        self.threshold_scatter = DraggableScatter(self.x_indices, self.thresholds, self.threshold_line)
        self.threshold_scatter.signal_threshold_changed.connect(self.update_thresholds)
        self.plot.addItem(self.threshold_scatter)

        # Легенда
        legend = pg.LegendItem((100, 80), offset=(60, 1))
        legend.setParentItem(self.plot)
        legend.addItem(self.threshold_line, self.tr('Threshold'))
        legend.addItem(self.fpv_coeff_line, self.tr('FPV Coeff'))
        legend.addItem(self.rssi_line, self.tr('RSSI'))

        self.btn_threshold = QPushButton()
        self.btn_threshold.setToolTip(self.tr('Auto threshold'))
        self.btn_threshold.setIcon(QIcon(r'assets/icons/threshold.png'))
        self.btn_threshold.setFixedSize(30, 30)
        self.btn_threshold.clicked.connect(self.reset_threshold)
        proxy = pg.Qt.QtWidgets.QGraphicsProxyWidget()
        proxy.setWidget(self.btn_threshold)
        self.plot.scene().addItem(proxy)

    def add_background_regions(self):
        freq_ranges = [(1080, 1360), (3170, 3470), (4990, 6028)]
        colors = [(135, 255, 255, 30), (255, 135, 255, 30), (255, 255, 135, 30)]
        c = 0
        for f_min, f_max in freq_ranges:
            # Находим соответствующие индексы X
            x_range = []
            for i, freq in enumerate(self.freqs):
                if f_min <= freq <= f_max:
                    x_range.append(i)
            if x_range:
                region = LinearRegionItem(values=(x_range[0] - 0.5, x_range[-1] + 0.5), brush=colors[c])
                region.setMovable(False)
                region.setZValue(-10)
                self.plot.addItem(region)
                c += 1

    def add_widgets_to_layout(self):
        self.main_layout.addWidget(self.graphWindow)

    def update_thresholds(self, new_values, data_type: str):
        try:
            if data_type == 'init':
                """ init thresholds from remote control """
                self.thresholds = new_values
                self.logger.info(f'FPV Scope init threshold was updated')
            elif data_type == 'auto':
                """ clicked auto threshold button """
                for i in range(len(self.thresholds)):
                    self.thresholds[i] = int(self.fpv_coeff_values[i] + new_values)
                    if self.thresholds[i] > 100:
                        self.thresholds[i] = 100
                self.signal_all_thresholds_change.emit(self.thresholds)
                self.logger.info(f'FPV Scope threshold was updated on auto values')
            elif data_type == 'manual':
                """ manual changing one scatter """
                index, value = new_values[0], new_values[1]
                self.thresholds[index] = value
                self.signal_threshold_change.emit(index, value)
                self.logger.info(f'FPV Scope threshold was updated on manual value')
            elif data_type == 'increased':
                self.thresholds[self.exceeded_freq] = int(self.fpv_coeff_values[self.exceeded_freq] + self.increase_thr)
                if self.thresholds[self.exceeded_freq] > 100:
                    self.thresholds[self.exceeded_freq] = 100
                self.signal_threshold_change.emit(self.exceeded_freq, self.thresholds[self.exceeded_freq])
                self.logger.info(f'FPV Scope warning threshold was increased on 10')
            self.is_exceed_threshold()
            self.threshold_line.setData(x=self.x_indices, y=self.thresholds)
            self.threshold_scatter.update_threshold(new_threshold=self.thresholds)

        except Exception as e:
            self.logger.error(f'Error with updating FPV Scope threshold! {e}')

    def reset_threshold(self):
        self.update_thresholds(new_values=self.increase_thr, data_type='auto')
        self.logger.info(f'Default threshold was changed on automatic values (increase on {self.increase_thr}')

    def increase_exceeded_threshold(self):
        if self.exceeded_freq is not None:
            self.update_thresholds(new_values=0, data_type='increased')

    def on_upward_point_clicked(self, scatter, points):
        if not points:
            return
        point = points[0]
        index = int(point.pos().x())
        self.select_upward_point(index)
        self.change_mode_on_manual(status=True)

    def select_upward_point(self, index: int):
        for point in self.fpv_coeff_scatter.points():
            point.setBrush(pg.mkBrush(255, 255, 255, 180))
            point.setSize(10)

        if 0 <= index < len(self.fpv_coeff_scatter.points()):
            point = self.fpv_coeff_scatter.points()[index]
            point.setBrush(pg.mkBrush(255, 0, 0, 180))
            point.setSize(14)
            self.selected_up_index = index
            self.signal_freq_point_clicked.emit(index, str(self.freqs[index]))
            self.logger.info(f'Selected freq: {self.freqs[index]}')

    def keyPressEvent(self, event):
        if not self.manual_mode:
            return

        if self.selected_up_index is None:
            self.selected_up_index = 0
        elif event.key() == Qt.Key_Right:
            self.selected_up_index = (self.selected_up_index + 1) % self.freqs_len
        elif event.key() == Qt.Key_Left:
            self.selected_up_index = (self.selected_up_index - 1) % self.freqs_len
        else:
            return

        self.select_upward_point(self.selected_up_index)
        self.change_mode_on_manual(True)

    def change_mode_on_manual(self, status: bool):
        self.manual_mode = status
        if status:
            if self.selected_up_index is None:
                # self.signal_fpvScope_mode.emit('manual', 0)
                if self.exceeded_freq is None:
                    self.signal_fpvScope_mode.emit('manual', 0)
                else:
                    self.signal_fpvScope_mode.emit('manual', self.exceeded_freq)   # если нажата кнопка из вспылвающего окна
            else:
                self.signal_fpvScope_mode.emit('manual', self.selected_up_index)
            self.signal_change_radio_btn.emit(False)
        else:
            self.signal_fpvScope_mode.emit('auto', 0)
            self.clear_selected_point()
            self.signal_change_radio_btn.emit(True)

    def clear_selected_point(self):
        for point in self.fpv_coeff_scatter.points():
            point.setBrush(pg.mkBrush(255, 255, 255, 180))
            point.setSize(10)
        self.selected_up_index = None

    def collect_config(self):
        conf = {}
        for band, freq_list in self.freqs_dict.items():
            conf[band] = []
            for freq_dict in freq_list:
                freq = list(freq_dict.keys())[0]
                idx = list(self.freqs).index(freq)      # индекс частоты в self.freqs
                threshold_value = self.thresholds[idx]
                conf[band].append({freq: {'threshold': threshold_value}})
        self.configuration_conf['fpv_scope_frequencies'] = conf

    def dump_configuration_conf(self):
        try:
            self.collect_config()
            with open('configuration.yaml', 'w') as f:
                yaml.dump(self.configuration_conf, f, sort_keys=False)
            self.logger.success(f'configuration.yaml was saved!')
        except Exception as e:
            self.logger.error(f'Error with saving configuration.yaml : {e}')

    def normalize_value(self, value, default_min_value, default_max_value):
        value = default_min_value if value < default_min_value else value
        value = default_max_value if value > default_max_value else value
        percent_value = 100 * (value - default_min_value) / (default_max_value - default_min_value)
        return percent_value

    def is_exceed_threshold(self):
        exceeded_indexes = []
        for i in range(len(self.x_indices)):
            if self.fpv_coeff_values[i] > self.thresholds[i]:
                exceeded_indexes.append(i)

        view_box = self.plot.getViewBox()
        if exceeded_indexes:
            view_box.setBackgroundColor(QtGui.QColor(255, 110, 110, 60))
            self.signal_exceed_threshold.emit(True)
            if not self.manual_mode:
                self.fpvModeWidnow.open_window()
            self.exceeded_freq = exceeded_indexes[-1]
        else:
            view_box.setBackgroundColor(QtGui.QColor(0, 0, 0))
            self.signal_exceed_threshold.emit(False)
            self.exceeded_freq = None

    def update_graph(self, packet: dict):
        """ FPV Scope Data packet: {'1G2': [{'freq': 1080, 'rssi': 808, 'fpv_coeff': 8},
                                           {'freq': 1120, 'rssi': 749, 'fpv_coeff': 13}, ... """
        # Начинаем с текущих значений, чтобы сохранить те, что не обновляются
        new_fpv_coeff = self.fpv_coeff_values.copy()
        new_rssi = self.fpv_rssi_values.copy()
        # self.logger.info(packet)
        for band, data in packet.items():
            default_fpv_min, default_fpv_max = self.fpv_default_values[band]['fpv_coeff']
            default_rssi_min, default_rssi_max = self.fpv_default_values[band]['rssi']

            for freq_dict in data:
                freq = freq_dict['freq']
                if freq not in self.freqs:
                    self.logger.warning(f'Unknown freq {freq} from from fpvScope packet.')
                    continue

                index = np.where(self.freqs == freq)[0][0]
                norm_fpv_coeff = self.normalize_value(freq_dict['fpv_coeff'], default_fpv_min, default_fpv_max)
                norm_rssi = self.normalize_value(freq_dict['rssi'], default_rssi_min, default_rssi_max)

                new_fpv_coeff[index] = norm_fpv_coeff
                new_rssi[index] = norm_rssi

        # Сохраняем обновлённые значения
        self.fpv_coeff_values = new_fpv_coeff
        self.fpv_rssi_values = new_rssi

        # Update graphs
        self.fpv_coeff_line.setData(self.x_indices, self.fpv_coeff_values)
        self.fpv_coeff_scatter.setData(self.x_indices, self.fpv_coeff_values)
        self.rssi_line.setData(self.x_indices, self.fpv_rssi_values)

        # Восстановить подсветку выбранной точки
        if self.selected_up_index is not None:
            self.select_upward_point(self.selected_up_index)

        self.is_exceed_threshold()


class DraggableScatter(pg.ScatterPlotItem):
    signal_threshold_changed = pyqtSignal(list, str)

    def __init__(self, x, y, line_item):
        super().__init__(x=x, y=y, symbol='o', size=8, pen='y', brush='r')
        self.x_data = np.array(x)
        self.y_data = np.array(y)
        self.line_item = line_item                  # Ссылка на линию порога
        self.threshold_min, self.threshold_max = 5, 100             # Ограничение порога
        self.dragged_point = None

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            ev.ignore()
            return
        pos = self.getViewBox().mapSceneToView(ev.scenePos())
        x_data, y_data = self.getData()
        distances = np.hypot(x_data - pos.x(), y_data - pos.y())
        self.dragged_point = np.argmin(distances)
        if distances[self.dragged_point] > 0.95:  # Порог расстояния для клика
            self.dragged_point = None
            ev.ignore()
        else:
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self.dragged_point is not None:
            pos = self.getViewBox().mapSceneToView(ev.scenePos())
            new_y = np.clip(pos.y(), self.threshold_min, self.threshold_max)
            self.y_data[self.dragged_point] = new_y
            self.setData(x=self.x_data, y=self.y_data)
            self.line_item.setData(x=self.x_data, y=self.y_data)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        if self.dragged_point is not None:
            index = self.dragged_point
            value = self.y_data[index]
            self.signal_threshold_changed.emit([index, int(value)], 'manual')
        self.dragged_point = None
        ev.accept()

    def update_threshold(self, new_threshold: list):
        self.y_data = np.array(new_threshold)
        self.setData(x=self.x_data, y=self.y_data)
        self.line_item.setData(x=self.x_data, y=self.y_data)


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = FPVScope()
    window.show()
    sys.exit(app.exec())
