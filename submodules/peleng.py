import pyqtgraph as pg
import numpy as np
from submodules import basic
from PyQt5 import Qt, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsEllipseItem, QVBoxLayout, QGraphicsPathItem
from PyQt5.QtWidgets import QDockWidget, QWidget
from PyQt5.QtGui import QColor, QPen, QPainterPath
from pyqtgraph import TextItem
from math import isnan


class PelengWidget(QDockWidget, QWidget):

    def __init__(self, config, drons_config, logger_):
        super().__init__()
        self.logger = logger_
        self.setWindowTitle(self.tr('Peleng'))
        self.setWidget(QWidget(self))
        self.widget().setLayout(QVBoxLayout())
        self.widget().layout().setContentsMargins(0, 0, 0, 0)
        self.widget().layout().setSpacing(0)

        self.graphWindow = pg.GraphicsLayoutWidget()
        # self.graphWindow.setBackground(QtGui.QColor(100, 100, 100))
        self.widget().layout().addWidget(self.graphWindow)
        self.plot = self.graphWindow.addPlot()
        self.plot.vb.setMouseEnabled(x=False, y=False)
        self.plot.setAspectLocked(True)
        self.plot.hideButtons()
        self.show_axis(False)

        self.config = {}
        self.config_drons = {}
        self.type_of_signals = None
        self.colors = None
        self.number_of_drons = None      # number of drons (signals on every sector)
        self.threshold = None
        self.sectors = 6
        self.deviation = 8          # deviation of peleng and the width of peleng segment

        self.load_conf(config)
        self.load_conf_drons(drons_config)

        self.radar_radius = 3500
        self.grid_line_length = self.radar_radius + 300
        self.sector_label = [None] * self.sectors
        self.degree_label = [None] * self.sectors
        self.angle = 360 / self.sectors                 # angle of every sector

        self.full_pack_2D = np.zeros((self.sectors, self.number_of_drons), dtype=np.int32)
        self.max_signals = {}
        self.peleng_line = [None] * self.number_of_drons
        self.peleng = [None] * self.number_of_drons
        self.peleng_power = [None] * self.number_of_drons
        self.values_max_with_gain = [0] * self.number_of_drons
        self.values_nearest_max_with_gain = [0] * self.number_of_drons

        self.view_lvls_flag = True

        self.sector_highlights = [None] * self.sectors          # Инициализация массива подсветок

        self.radar_labeling()
        self.draw_graph()
        self.draw_additional_axis()

    def load_conf(self, config):
        self.config.update(config)
        self.sectors = self.config['number_of_sectors']
        self.threshold = self.config['threshold']
        self.a_24 = self.config['peleng_coefficients'][24]['a']
        self.b_24 = self.config['peleng_coefficients'][24]['b']
        self.a_58 = self.config['peleng_coefficients'][58]['a']
        self.b_58 = self.config['peleng_coefficients'][58]['b']

    def load_conf_drons(self, conf):
        self.config_drons.update(conf)
        self.type_of_signals = [self.config_drons[key]['name'] for key in self.config_drons.keys()]
        self.colors = [self.config_drons[key]['color'] for key in self.config_drons.keys()]
        self.number_of_drons = len(self.type_of_signals)

    def show_axis(self, show: bool):
            self.plot.showAxis('bottom', show)
            self.plot.showAxis('left', show)

    def draw_graph(self):
        # Add circles
        for r in range(500, self.radar_radius + 500, 500):
            circle = pg.QtWidgets.QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
            # Make last circle bigger and set up the width
            if r == self.radar_radius:
                circle.setPen(pg.mkPen(0.7))
            else:
                circle.setPen(pg.mkPen(0.2))
            circle.setZValue(10)  # to show on top of other objects with the Z number below
            self.plot.addItem(circle)

        # Add threshold circle
        self.thr_circle = pg.QtWidgets.QGraphicsEllipseItem(-self.threshold, -self.threshold, self.threshold * 2,
                                                            self.threshold * 2)
        self.thr_circle.setPen(pg.mkPen(1))
        self.thr_circle.setZValue(11)       # to show on top of other objects with the Z number below
        self.plot.addItem(self.thr_circle)

        # Add polar grid lines
        pen = QPen(QColor(255, 184, 65))
        pen.setWidth(15)
        self.grid_line = [None] * 3
        self.grid_line[0] = pg.PlotCurveItem([-self.grid_line_length, self.grid_line_length], [0, 0],
                                             pen=pen)
        self.grid_line[1] = pg.PlotCurveItem([-(self.grid_line_length*np.cos(np.radians(self.angle))),
                                              self.grid_line_length*np.cos(np.radians(self.angle))],
                                             [-(self.grid_line_length*np.sin(np.radians(self.angle))),
                                              self.grid_line_length*np.sin(np.radians(self.angle))],
                                             pen=pen)
        self.grid_line[2] = pg.PlotCurveItem([self.grid_line_length*np.cos(np.radians(self.angle)),
                                              -(self.grid_line_length*np.cos(np.radians(self.angle)))],
                                             [-(self.grid_line_length*np.sin(np.radians(self.angle))),
                                              self.grid_line_length*np.sin(np.radians(self.angle))],
                                             pen=pen)

        self.plot.addItem(self.grid_line[0])
        self.plot.addItem(self.grid_line[1])
        self.plot.addItem(self.grid_line[2])

    def radar_labeling(self):
        # Sector numbering
        label_const = 300
        for i in range(self.sectors):
            self.sector_label[i] = TextItem(text=str(i + 1), color=(255, 184, 65), anchor=(0.5, 0.5))
            self.plot.addItem(self.sector_label[i])
            self.sector_label[i].setTextWidth(30)
            self.sector_label[i].setFont(pg.QtGui.QFont("Arial", 16))

        self.sector_label[0].setPos(0, self.radar_radius + label_const * 1.5)
        self.sector_label[1].setPos(self.radar_radius + label_const, np.sin(np.radians(30)) * self.radar_radius)
        self.sector_label[2].setPos(self.radar_radius + label_const, - np.sin(np.radians(30)) * self.radar_radius)
        self.sector_label[3].setPos(0, - (self.radar_radius + label_const * 1.5))
        self.sector_label[4].setPos(- self.radar_radius, - np.sin(np.radians(30)) * self.radar_radius)
        self.sector_label[5].setPos(- self.radar_radius, np.sin(np.radians(30)) * self.radar_radius)

        # Degrees numbering
        label_const = 300
        degree = 30
        for i in range(self.sectors):
            self.degree_label[i] = TextItem(text=str(degree) + '°', color='w', anchor=(0.5, 0.5))
            self.plot.addItem(self.degree_label[i])
            self.degree_label[i].setTextWidth(35)
            self.degree_label[i].setFont(pg.QtGui.QFont("Arial", 8))
            degree += 60

        self.degree_label[0].setPos(self.grid_line_length / 2 + label_const,
                                    (self.grid_line_length + label_const) * np.sin(np.radians(60)))
        self.degree_label[1].setPos(self.grid_line_length + label_const, 0)
        self.degree_label[2].setPos(self.grid_line_length / 2 + label_const,
                                    - (self.grid_line_length + label_const) * np.sin(np.radians(60)))
        self.degree_label[3].setPos(- self.grid_line_length / 2 - label_const,
                                    - (self.grid_line_length + label_const) * np.sin(np.radians(60)))
        self.degree_label[4].setPos(- self.grid_line_length - label_const, 0)
        self.degree_label[5].setPos(- self.grid_line_length / 2 - label_const,
                                    (self.grid_line_length + label_const) * np.sin(np.radians(60)))

    def draw_additional_axis(self):
        """ This function add additional axis and labels for axis """
        # Add axis
        degree = [20, 40, 80, 100, 140, 160]
        axis_numb = int((self.sectors * 2) / 2)       # 2 axis on every sector
        additional_axis = [None] * axis_numb
        for i in range(axis_numb):
            additional_axis[i] = pg.PlotCurveItem([-(self.grid_line_length * np.cos(np.radians(degree[i]))),
                                                   self.grid_line_length * np.cos(np.radians(degree[i]))],
                                                  [-(self.grid_line_length * np.sin(np.radians(degree[i]))),
                                                   self.grid_line_length * np.sin(np.radians(degree[i]))],
                                                  pen=pg.mkPen(width=0.3))
            self.plot.addItem(additional_axis[i])

        # Add labels
        label_const = 200
        labels_names = [70, 50, 10, 350, 310, 290, 250, 230, 190, 170, 130, 110]
        labels_degrees = [20, 40, 80, 100, 140, 160, 200, 220, 260, 280, 320, 340]
        degree_labels = [None] * len(labels_names)
        for i in range(len(labels_names)):
            degree_labels[i] = TextItem(text=str(labels_names[i]) + '°', color='w', anchor=(0.5, 0.5))
            degree_labels[i].setTextWidth(35)
            degree_labels[i].setFont(pg.QtGui.QFont("Arial", 8))
            self.plot.addItem(degree_labels[i])

        degree_labels[0].setPos(self.grid_line_length + label_const,
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[0])))
        degree_labels[1].setPos(self.grid_line_length * 0.8 + label_const,
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[1])))
        degree_labels[2].setPos(self.grid_line_length * 0.2 + 50,
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[2])))
        degree_labels[3].setPos(-self.grid_line_length * 0.2,
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[3])))
        degree_labels[4].setPos(-(self.grid_line_length * 0.8 + label_const),
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[4])))
        degree_labels[5].setPos(- (self.grid_line_length + label_const),
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[5])))
        degree_labels[6].setPos(-(self.grid_line_length + label_const),
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[6])))
        degree_labels[7].setPos(-(self.grid_line_length * 0.8 + label_const),
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[7])))
        degree_labels[8].setPos(-self.grid_line_length * 0.2,
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[8])))
        degree_labels[9].setPos(self.grid_line_length * 0.2 + 50,
                                (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[9])))
        degree_labels[10].setPos(self.grid_line_length * 0.8 + label_const,
                                 (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[10])))
        degree_labels[11].setPos(self.grid_line_length + label_const,
                                 (self.grid_line_length + label_const) * np.sin(np.radians(labels_degrees[11])))

    def draw_peleng(self, pelengs:list[basic.Peleng]):
        for i in range(self.number_of_drons):
            self.plot.removeItem(self.peleng[i])

        sector_power_map = {}  # Словарь: сектор -> макс мощность в нем

        for i in range(len(pelengs)):
            if isnan(pelengs[i].angle):     # check if peleng is NaN
                self.logger.warning(f"Skipping peleng {i} due to NaN angle")
                continue  # skip this peleng
            start_angle = int(pelengs[i].angle - 90 - 30)

            if self.view_lvls_flag:
                if pelengs[i].power > self.radar_radius:
                    power = self.radar_radius
                else:
                    power = pelengs[i].power
            else:
                power = self.radar_radius

            self.peleng[i] = QGraphicsEllipseItem(-power, -power, power * 2, power * 2)
            self.peleng[i].setStartAngle(start_angle * 16)
            self.peleng[i].setSpanAngle(int(self.deviation / 2) * 16)       # 8 degrees because it is error rate
            pen = QPen(QColor(0, 0, 0), 5, Qt.SolidLine)
            self.peleng[i].setPen(pen)
            self.peleng[i].setBrush(QColor(pelengs[i].color[0], pelengs[i].color[1], pelengs[i].color[2]))
            self.plot.addItem(self.peleng[i])

            angle_step = (360 / self.sectors)
            sector_angle = (360 - pelengs[i].angle + 90 + 30) % 360
            sector_ind = int(sector_angle // angle_step)

            # Обновляем мощность в секторе
            if sector_ind not in sector_power_map or power > sector_power_map[sector_ind]:
                sector_power_map[sector_ind] = power

            # Подсветка сектора, где мощность выше порога
            for sector in range(self.sectors):
                power = sector_power_map.get(sector, 0)
                if power > self.threshold:
                    self.highlight_on_sector(sector)
                else:
                    self.highlight_off_sector(sector)

    def change_threshold(self, value: int):
        self.plot.removeItem(self.thr_circle)  # Remove threshold circle
        self.threshold = value
        self.draw_threshold_circle()

    # Add threshold circle
    def draw_threshold_circle(self):
        self.thr_circle = pg.QtWidgets.QGraphicsEllipseItem(-self.threshold, -self.threshold, self.threshold * 2, self.threshold * 2)
        self.thr_circle.setPen(pg.mkPen(1))
        self.thr_circle.setZValue(11)        # to show on top of other objects with the Z number below
        self.plot.addItem(self.thr_circle)

    def change_view_levels_flag(self, status: bool):
        self.view_lvls_flag = status

    def highlight_on_sector(self, sector_index: int):
        if self.sector_highlights[sector_index] is not None:
            return  # Уже подсвечен

        color = QColor(0, 255, 0)
        opacity = 0.2

        angle_step = (360 / self.sectors)
        angle_start = sector_index * angle_step
        angle_end = angle_start + angle_step

        # Построение пути сектора
        path = QPainterPath()
        path.moveTo(0, 0)
        for angle_deg in np.linspace(angle_start, angle_end, 100):
            angle_rad = np.radians(angle_deg)
            x = self.radar_radius * np.cos(angle_rad)
            y = self.radar_radius * np.sin(angle_rad)
            path.lineTo(x, y)
        path.closeSubpath()

        sector_item = QGraphicsPathItem(path)
        brush = QtGui.QBrush(color)
        brush.setStyle(Qt.SolidPattern)
        brush.setColor(color)
        sector_item.setBrush(brush)
        sector_item.setOpacity(opacity)
        sector_item.setZValue(5)

        pen = QtGui.QPen(Qt.NoPen)
        sector_item.setPen(pen)

        self.plot.addItem(sector_item)
        self.sector_highlights[sector_index] = sector_item

    def highlight_off_sector(self, sector_index: int):
        if not hasattr(self, 'sector_highlights'):
            return

        if self.sector_highlights[sector_index] is not None:
            self.plot.removeItem(self.sector_highlights[sector_index])
            self.sector_highlights[sector_index] = None
