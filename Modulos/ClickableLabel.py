import cv2
from PySide6.QtWidgets import (QLabel)
from PySide6.QtCore import (Qt)
from PySide6.QtGui import (QImage, QPixmap)
import os
import logging

logger = logging.getLogger(__name__)


os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_frame = None
        self.pause_callback = None

    def update_frame(self, frame):
        if frame is not None:
            self.original_frame = cv2.resize(
                frame, (1920, 1080), interpolation=cv2.INTER_CUBIC
            )
        else:
            self.original_frame = None

    # CLICK SIMPLE → pausar / reanudar
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.pause_callback:
                self.pause_callback()

    # DOBLE CLICK → vista ampliada
    def mouseDoubleClickEvent(self, event):
        if self.original_frame is None:
            return

        rgb_image = cv2.cvtColor(self.original_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(
            rgb_image.data, w, h, bytes_per_line,
            QImage.Format.Format_RGB888
        )

        self.popout = QLabel()
        self.popout.setWindowTitle("Vista Ampliada HD (1920x1080)")
        self.popout.setPixmap(QPixmap.fromImage(qt_image))
        self.popout.setWindowFlags(Qt.WindowType.Window)
        self.popout.show()
