import cv2
import numpy as np
from typing import Optional
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                               QGroupBox, QDialog, QWidget, QSizePolicy, QApplication)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QKeyEvent
import logging

logger = logging.getLogger(__name__)

class CaptureDecisionDialog(QDialog):
    """
    Diálogo modal estandarizado para validar la calidad de la captura.
    """
    RESULT_DISCARD = 0
    RESULT_IA = 1
    RESULT_MANUAL = 2

    def __init__(self, frame_left: np.ndarray, frame_top: np.ndarray, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Validación de Captura Biométrica")
        self.setModal(True)
        
        # Ajuste dinámico de tamaño según pantalla
        screen = QApplication.primaryScreen().availableGeometry()
        window_width = int(screen.width() * 0.5)
        window_height = int(((window_width / 2) * 9 / 16) + screen.height() * 0.1)

        self.resize(window_width, window_height)

        self._init_ui(frame_left, frame_top)

    def _init_ui(self, frame_left, frame_top):
        # 1. Layout Principal y Configuración
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 2. Grupo de Vista Previa con estilo estandarizado
        preview_group = QGroupBox("Inspección de Calidad Visual")
        preview_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        preview_group.setToolTip("Verifique que el pez esté claramente visible y centrado en ambas cámaras.")
        
        preview_layout = QHBoxLayout(preview_group)
        preview_layout.setSpacing(15)
        
        self.lbl_left = self._create_image_label("Cámara encargada de medir Longitud y Altura del lomo del pez.")
        self.lbl_top = self._create_image_label("Cámara encargada de medir el Ancho dorsal del pez.")

        preview_layout.addWidget(self.lbl_left)
        preview_layout.addWidget(self.lbl_top)
        
        self._display_frame(frame_left, self.lbl_left)
        self._display_frame(frame_top, self.lbl_top)

        main_layout.addWidget(preview_group, stretch=1) 

        # 3. Botonera de Decisión con Clases CSS Globales
        decision_layout = QHBoxLayout()
        decision_layout.setSpacing(20)

        # --- Botón Descartar (Secondary/Warning) ---
        self.btn_discard = QPushButton("Descartar\n(Esc)")
        self.btn_discard.setProperty("class", "warning") # Clase para Rojo/Riesgo
        self.btn_discard.setCursor(Qt.PointingHandCursor)
        self.btn_discard.setToolTip("Eliminar esta captura y volver al video en vivo para repetir la toma.")
        self.btn_discard.clicked.connect(self.reject_capture)

        # --- Botón Manual (Info) ---
        self.btn_use_manual = QPushButton("Medición Manual\n(M)")
        self.btn_use_manual.setProperty("class", "info") # Clase para Azul Claro
        self.btn_use_manual.setCursor(Qt.PointingHandCursor)
        self.btn_use_manual.setToolTip("Ingresar las medidas manualmente.")
        self.btn_use_manual.clicked.connect(self.accept_manual)

        # --- Botón IA (Primary/Success) ---
        self.btn_use_ai = QPushButton("Procesar con IA\n(Enter)")
        self.btn_use_ai.setProperty("class", "success") # Clase para Verde/Confirmación
        self.btn_use_ai.setCursor(Qt.PointingHandCursor)
        self.btn_use_ai.setToolTip("Ejecutar la IA de detección para obtener medidas automáticas.")
        self.btn_use_ai.clicked.connect(self.accept_ai)
        self.btn_use_ai.setDefault(True) 

        decision_layout.addWidget(self.btn_discard, 1)
        decision_layout.addWidget(self.btn_use_manual, 1)
        decision_layout.addWidget(self.btn_use_ai, 1)
        
        main_layout.addLayout(decision_layout)

        # Eliminamos setStyleSheet fijo del fondo para que use el del tema activo
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _create_image_label(self, tooltip: str) -> QLabel:
        """Factory de labels para las cámaras."""
        lbl = QLabel()
        lbl.setMinimumSize(320, 240)
        lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored) 
        # Usamos la clase video-feed definida en tu CSS global
        lbl.setProperty("class", "video-feed") 
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setToolTip(tooltip)
        return lbl

    def _display_frame(self, frame: np.ndarray, label: QLabel):
        """Muestra el frame asegurando contigüidad de memoria (Fix BufferError)."""
        if frame is None:
            label.setText("SIN SEÑAL")
            return

        try:
            # Asegurar que los datos sean contiguos para QImage
            frame_contig = np.ascontiguousarray(frame)
            frame_rgb = cv2.cvtColor(frame_contig, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            
            label.original_pixmap = QPixmap.fromImage(qt_image)
            self._update_label_scaling(label)
            
        except Exception as e:
            logger.error(f"Error renderizando preview: {e}")
            label.setText("⚠️ ERROR DE RENDER")

    def _update_label_scaling(self, label: QLabel):
        """Ajusta la imagen al tamaño dinámico del label."""
        if hasattr(label, 'original_pixmap') and label.original_pixmap:
            scaled = label.original_pixmap.scaled(
                label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            label.setPixmap(scaled)

    def resizeEvent(self, event):
        """Mantiene las imágenes ajustadas si el usuario estira el diálogo."""
        self._update_label_scaling(self.lbl_left)
        self._update_label_scaling(self.lbl_top)
        super().resizeEvent(event)

    # --- Lógica de Retorno ---
    def accept_ai(self): self.done(self.RESULT_IA)
    def accept_manual(self): self.done(self.RESULT_MANUAL)
    def reject_capture(self): self.done(self.RESULT_DISCARD)

    def keyPressEvent(self, event: QKeyEvent):
        """Atajos de teclado para flujo rápido de trabajo."""
        key = event.key()
        if key in (Qt.Key_Enter, Qt.Key_Return):
            self.accept_ai()
        elif key == Qt.Key_Escape:
            self.reject_capture()
        elif key == Qt.Key_M:
            self.accept_manual()
        else:
            super().keyPressEvent(event)
            
    def closeEvent(self, event):
        """Si se cierra la ventana con la X, equivale a descartar."""
        self.done(self.RESULT_DISCARD)