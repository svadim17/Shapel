from PyQt5.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QApplication, QPushButton, QGridLayout, QLabel, QScrollArea, QFrame, QSizePolicy,
                             QSpacerItem)
from PyQt5.QtMultimedia import QCameraInfo, QCamera
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtCore import Qt


class FPVVideoWidget(QDockWidget, QWidget):

    def __init__(self, camera, logger_):
        super().__init__()
        self.logger = logger_
        self.setWindowTitle(self.tr('FPV Video'))

        self.setWidget(QWidget())
        self.main_layout = QVBoxLayout()  # create vertical layout for buttons
        # self.main_layout.setAlignment(Qt.AlignTop)
        self.widget().setLayout(self.main_layout)

        self.viewfinder = QCameraViewfinder()
        self.camera = QCamera(camera)
        self.camera.setViewfinder(self.viewfinder)
        self.camera.start()

        self.add_widgets_to_layout()

    def add_widgets_to_layout(self):
        self.main_layout.addWidget(self.viewfinder)

    def change_camera(self, camera):
        self.logger.info(f'Camera was changed on: {camera.description()}')

        self.camera.stop()          # stop current camera
        self.camera.deleteLater()

        self.camera = QCamera(camera)
        self.camera.setViewfinder(self.viewfinder)
        self.camera.start()


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = FPVVideoWidget(QCamera(QCameraInfo.availableCameras()[0]))
    window.show()
    sys.exit(app.exec())
