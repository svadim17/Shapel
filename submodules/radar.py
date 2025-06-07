import numpy as np
import math
import pyqtgraph as pg
from submodules import basic
from PyQt5 import Qt
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QGraphicsEllipseItem
from PyQt5.QtWidgets import QDockWidget, QWidget
from PyQt5.QtGui import QColor, QPen
from pyqtgraph import TextItem


class PowerLevelWidget(QDockWidget, QWidget):

    signal_warning = pyqtSignal(bool, list, list)
    signal_warning_log = pyqtSignal(str)

    # slider_value_changed_signal = pyqtSignal(int, int)
    def __init__(self, config, drons_config):
        super().__init__()
        # self.setMaximumHeight(600)
        self.setTitleBarWidget(QWidget())
        self.graphWindow = pg.GraphicsLayoutWidget()
        self.setWidget(self.graphWindow)
        self.plot = self.graphWindow.addPlot()
        self.plot.vb.setMouseEnabled(x=False, y=False)
        # self.graphWindow.setBackground(QtGui.QColor(100, 100, 100))
        self.plot.hideButtons()
        self.plot.setAspectLocked(True)
        # self.plot.setAspectLocked()
        self.show_axis(False)

        self.config_drons = {}
        self.config = {}
        self.type_of_signals = [None]
        self.colors = [None]
        self.gain_value = [None]
        self.threshold = None
        self.sectors = None

        self.load_conf(config)
        self.load_conf_drons(drons_config)

        # self.slider_value_changed_signal.connect(self.processing_data)
        self.first_receive_flag = 0
        self.flag_warning = 0
        self.receive_counter = 0

        self.label_sector = [0] * self.sectors
        self.sector_label = [None] * self.sectors
        self.radar_radius = 3500
        self.grid_line_length = self.radar_radius + 300
        self.angle = 360 / self.sectors                                   # self.angle of every sector
        self.number_of_drons = len(self.type_of_signals)                  # number of drons (signals on every sector)
        self.number_of_signals = self.sectors * self.number_of_drons           # total number of signals
        self.angle_step = math.floor(360 / self.number_of_signals)        # step between every type of dron's signals
        self.angle_shift = ((360 / self.sectors) % self.number_of_drons) / 2   # for placing signals on center of sector
        self.temp_ant_for_random = 1        # variable for modeling random signal power

        self.power_of_signals = [None] * self.number_of_drons

        self.segments_counter = 0
        self.segments_in_sector = [None] * (self.number_of_drons * self.sectors)

        self.drone_mapping = dict(enumerate(self.config_drons.keys()))
        self.sector_numbering()
        self.draw_graph()

    def load_conf(self, conf):
        self.config.update(conf)
        self.threshold = self.config['threshold']
        self.sectors = self.config['number_of_sectors']

    def load_conf_drons(self, conf):
        self.config_drons.update(conf)
        self.type_of_signals = [self.config_drons[key]['name'] for key in self.config_drons.keys()]
        self.colors = [self.config_drons[key]['color'] for key in self.config_drons.keys()]
        self.gain_value = [self.config_drons[key]['gains'] for key in self.config_drons.keys()]

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
            circle.setZValue(10)            # to show on top of other objects with the Z number below
            self.plot.addItem(circle)

        # Add threshold circle
        self.thr_circle = pg.QtWidgets.QGraphicsEllipseItem(-self.threshold, -self.threshold, self.threshold * 2,
                                                            self.threshold * 2)
        self.thr_circle.setPen(pg.mkPen(1))
        self.thr_circle.setZValue(11)       # to show on top of other objects with the Z number below
        self.plot.addItem(self.thr_circle)

        # Add polar grid lines
        self.grid_line = [None] * 3
        self.grid_line[0] = pg.PlotCurveItem([-self.grid_line_length, self.grid_line_length], [0, 0],
                                             pen=pg.mkPen(width=0.7))
        self.grid_line[1] = pg.PlotCurveItem([-(self.grid_line_length*np.cos(np.radians(self.angle))),
                                              self.grid_line_length*np.cos(np.radians(self.angle))],
                                             [-(self.grid_line_length*np.sin(np.radians(self.angle))),
                                              self.grid_line_length*np.sin(np.radians(self.angle))],
                                             pen=pg.mkPen(width=0.7))
        self.grid_line[2] = pg.PlotCurveItem([self.grid_line_length*np.cos(np.radians(self.angle)),
                                              -(self.grid_line_length*np.cos(np.radians(self.angle)))],
                                             [-(self.grid_line_length*np.sin(np.radians(self.angle))),
                                              self.grid_line_length*np.sin(np.radians(self.angle))],
                                             pen=pg.mkPen(width=0.7))
        self.plot.addItem(self.grid_line[0])
        self.plot.addItem(self.grid_line[1])
        self.plot.addItem(self.grid_line[2])

    def clear_plot(self):
        for i in range(len(self.segments_in_sector)):
            self.plot.removeItem(self.segments_in_sector[i])

    def processing_data(self, packet: basic.Sector_levels):
        sector = packet.antenna + 3                                  # +3 because of indexing
        for i in range(len(packet.levels)):
            self.power_of_signals[i] = packet.levels[i]
            if self.power_of_signals[i] > 3500:
                self.power_of_signals[i] = 3500
        ###########################################
        if self.segments_counter == self.number_of_drons * self.sectors:
            for i in range(len(self.segments_in_sector)):
                self.plot.removeItem(self.segments_in_sector[i])
                self.segments_counter = 0
        ############################################
        self.create_segments(sector, packet.levels, self.power_of_signals)

    # Add segments (count = 8)
    def create_segments(self, sector, signals, power_of_signals):
        # if self.segments_counter == self.number_of_drons * self.sectors:
        #     self.segments_counter = 0
        for i in range(self.segments_counter, self.segments_counter + len(signals)):
            # if self.segments_in_sector[i] is not None:
            #     self.plot.removeItem(self.segments_in_sector[i])
            angle_start = int(self.angle * sector + (i % self.number_of_drons) * self.angle_step + self.angle_shift)    # determine start angle to plot every signal
            color = self.colors[i % self.number_of_drons]                                   # get the color of signal
            self.segments_in_sector[i] = QGraphicsEllipseItem(
                -power_of_signals[i - (self.segments_counter + len(signals))],
                -power_of_signals[i - (self.segments_counter + len(signals))],
                power_of_signals[i - (self.segments_counter + len(signals))] * 2,
                power_of_signals[i - (self.segments_counter + len(signals))] * 2)
            self.segments_in_sector[i].setStartAngle(angle_start * 16)       # start angle (mull on 16 because function need)
            self.segments_in_sector[i].setSpanAngle(self.angle_step * 16)    # step angle (mull on 16 because function need)
            pen = QPen(QColor(0, 0, 0), 5, Qt.SolidLine)
            self.segments_in_sector[i].setPen(pen)
            self.segments_in_sector[i].setBrush(QColor(color[0], color[1], color[2]))

            self.plot.addItem(self.segments_in_sector[i])
        self.segments_counter += self.number_of_drons

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

    # Add sector numbering
    def sector_numbering(self):
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



