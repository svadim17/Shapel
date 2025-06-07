from PyQt5.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QApplication, QPushButton, QGridLayout, QLabel, QScrollArea, QFrame, QSizePolicy)
from PyQt5.QtMultimedia import QCameraInfo, QCamera
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtCore import Qt
import numpy as np
import pyqtgraph as pg


class FPVScopeWidget(QDockWidget, QWidget):

    def __init__(self, freqs_dict: dict):
        super().__init__()
        self.setTitleBarWidget(QWidget())
        self.freqs, self.freqs_len, self.thresholds, self.x_indices = self.get_data_from_dict(freqs_dict)

        self.upward_values = np.random.uniform(10, 45, self.freqs_len)        # временные значения вверх
        self.downward_values = -np.random.uniform(8, 16, self.freqs_len)     # временные значения вниз

        # self.setWidget(QWidget(self))
        # self.widget().setLayout(QVBoxLayout())
        self.central_widget = QWidget(self)
        self.setWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.create_graph()
        self.add_widgets_to_layout()

    def get_data_from_dict(self, freqs_dict: dict):
        frequencies = []
        threshold_values = []
        for band in freqs_dict.values():
            for freq_dict in band:
                freq = list(freq_dict.keys())[0]
                threshold = freq_dict[freq]['threshold']
                frequencies.append(freq)
                threshold_values.append(threshold)

        # Сортируем частоты и пороги
        sorted_indices = np.argsort(frequencies)
        frequencies = np.array(frequencies)[sorted_indices]
        threshold_values = np.array(threshold_values)[sorted_indices]
        n = len(frequencies)

        # Индексы для оси X
        x_indices = np.arange(n)
        return frequencies, n, threshold_values, x_indices

    def create_graph(self):
        # Создаем окно графика
        self.graphWindow = pg.GraphicsLayoutWidget()
        self.graphWindow.setWindowTitle('Frequencies')
        self.plot = self.graphWindow.addPlot()
        self.plot.vb.setMouseEnabled(x=False, y=False)
        self.plot.setLabel('bottom', 'Frequency (MHz)')
        self.plot.setLabel('left', 'Value')
        self.plot.setYRange(-60, 120)  # Диапазон по y для наглядности

        # Настраиваем ось X с метками частот
        axis = self.plot.getAxis('bottom')
        axis.setTicks([[(i, str(freq)) for i, freq in enumerate(self.freqs)]])
        axis.setStyle(tickTextOffset=10, tickTextHeight=30, tickTextWidth=100)

        self.create_graph_widgets()

    def create_graph_widgets(self):
        # Гистограммы вверх
        up_bars = pg.BarGraphItem(
            x=self.x_indices,
            height=self.upward_values,
            width=0.4,
            brush='b',
            pen='w',
            name='Значения вверх'
        )
        self.plot.addItem(up_bars)

        # Гистограммы вниз
        down_bars = pg.BarGraphItem(
            x=self.x_indices,
            height=self.downward_values,
            width=0.4,
            brush='r',
            pen='w',
            name='Значения вниз'
        )
        self.plot.addItem(down_bars)

        # Линия порога
        threshold_line = pg.PlotDataItem(
            x=self.x_indices,
            y=self.thresholds,
            pen='y',
            name='Порог'
        )
        self.plot.addItem(threshold_line)

        # Добавляем узлы порога
        threshold_scatter = DraggableScatter(self.x_indices, self.thresholds, threshold_line)
        self.plot.addItem(threshold_scatter)

        # Добавляем легенду
        legend = pg.LegendItem((80, 60), offset=(70, 20))
        legend.setParentItem(self.plot)
        legend.addItem(up_bars, 'Values')
        legend.addItem(down_bars, 'RSSI values')
        legend.addItem(threshold_line, 'Threshold')

    def add_widgets_to_layout(self):
        # self.widget().layout().addWidget(self.graphWindow)
        self.main_layout.addWidget(self.graphWindow)

    def channel_selected(self, band, channel):
        print(f'Clicked channel {channel} on band {band}')

    def change_camera(self, camera):
        print(f'New camera: {camera.description()}')

        self.camera.stop()          # stop current camera
        self.camera.deleteLater()

        self.camera = QCamera(camera)
        self.camera.setViewfinder(self.viewfinder)
        self.camera.start()


class DraggableScatter(pg.ScatterPlotItem):
    """ Создание интерактивных узлов порога """
    def __init__(self, x, y, line_item):
        super().__init__(x=x, y=y, symbol='t', size=5, pen='y', brush='g')
        self.x_data = np.array(x)
        self.y_data = np.array(y)
        self.line_item = line_item  # Ссылка на линию порога
        self.y_min = -100  # Ограничение порога
        self.y_max = 100
        self.dragged_point = None

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            ev.ignore()
            return
        pos = self.getViewBox().mapSceneToView(ev.scenePos())
        x_data, y_data = self.getData()
        distances = np.hypot(x_data - pos.x(), y_data - pos.y())
        self.dragged_point = np.argmin(distances)
        if distances[self.dragged_point] > 0.5:  # Порог расстояния для клика
            self.dragged_point = None
            ev.ignore()
        else:
            ev.accept()

    def mouseMoveEvent(self, ev):
        if self.dragged_point is not None:
            pos = self.getViewBox().mapSceneToView(ev.scenePos())
            new_y = np.clip(pos.y(), self.y_min, self.y_max)
            self.y_data[self.dragged_point] = new_y
            self.setData(x=self.x_data, y=self.y_data)
            self.line_item.setData(x=self.x_data, y=self.y_data)
            ev.accept()

    def mouseReleaseEvent(self, ev):
        self.dragged_point = None
        ev.accept()


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = FPVScope()
    window.show()
    sys.exit(app.exec())
