"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Interfaz de Validación de Captura (CaptureDecisionDialog.py)
DESCRIPCIÓN: Implementa un diálogo modal de decisión que permite al operario:
             1. Inspeccionar visualmente la calidad de los frames capturados.
             2. Seleccionar el flujo de procesamiento (Descartar, Manual o IA).
             3. Prevenir el ingreso de datos basura al sistema (Human-in-the-loop).
"""

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
    Diálogo modal de alto nivel para la validación de tomas fotográficas.
    
    Gestiona la visualización del par estéreo (cámara lateral y cenital) y 
    retorna códigos de estado estandarizados para controlar el flujo del programa.
    """
    RESULT_DISCARD = 0
    RESULT_IA = 1
    RESULT_MANUAL = 2

    def __init__(self, frame_left: np.ndarray, frame_top: np.ndarray, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Validación de Captura Biométrica")
        self.setModal(True)
        
        screen = QApplication.primaryScreen().availableGeometry()

        MAX_SCALE = 0.7

        h, w = frame_left.shape[:2]   # FHD = 1080x1920

        # Espacio máximo permitido para la ventana
        max_win_w = int(screen.width() * 0.5) - 80
        max_win_h = int(screen.height() * 0.5) - 200

        # Escala por ancho (dos cámaras)
        scale_w = max_win_w / (w * 2)

        # Escala por alto (una sola)
        scale_h = max_win_h / h

        # Escala final segura
        scale = min(MAX_SCALE, scale_w, scale_h)

        self.display_w = int(w * scale)
        self.display_h = int(h * scale)

        window_width = self.display_w * 2 + 80
        window_height = self.display_h + 200

        self.setFixedSize(window_width, window_height)
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

        main_layout.addWidget(preview_group) 

        decision_layout = QHBoxLayout()
        decision_layout.setSpacing(20)

        # --- Botón Descartar ---
        self.btn_discard = QPushButton("Descartar\n(Esc)")
        self.btn_discard.setProperty("class", "warning") 
        self.btn_discard.style().unpolish(self.btn_discard)
        self.btn_discard.style().polish(self.btn_discard)
        self.btn_discard.setCursor(Qt.PointingHandCursor)
        self.btn_discard.setToolTip("Eliminar esta captura y volver al video en vivo para repetir la toma.")
        self.btn_discard.clicked.connect(self.reject_capture)

        # --- Botón Manual (Info) ---
        self.btn_use_manual = QPushButton("Medición Manual\n(M)")
        self.btn_use_manual.setProperty("class", "info") 
        self.btn_use_manual.style().unpolish(self.btn_use_manual)
        self.btn_use_manual.style().polish(self.btn_use_manual)
        self.btn_use_manual.setCursor(Qt.PointingHandCursor)
        self.btn_use_manual.setToolTip("Ingresar las medidas manualmente.")
        self.btn_use_manual.clicked.connect(self.accept_manual)

        # --- Botón IA (Primary/Success) ---
        self.btn_use_ai = QPushButton("Procesar con IA\n(Enter)")
        self.btn_use_ai.setProperty("class", "success") 
        self.btn_use_ai.style().unpolish(self.btn_use_ai)
        self.btn_use_ai.style().polish(self.btn_use_ai)
        self.btn_use_ai.setCursor(Qt.PointingHandCursor)
        self.btn_use_ai.setToolTip("Ejecutar la IA de detección para obtener medidas automáticas.")
        self.btn_use_ai.clicked.connect(self.accept_ai)
        self.btn_use_ai.setDefault(True) 

        decision_layout.addWidget(self.btn_discard, 1)
        decision_layout.addWidget(self.btn_use_manual, 1)
        decision_layout.addWidget(self.btn_use_ai, 1)
        
        main_layout.addLayout(decision_layout)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _create_image_label(self, tooltip: str) -> QLabel:
        lbl = QLabel()
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setToolTip(tooltip)
        return lbl

    def _display_frame(self, frame: np.ndarray, label: QLabel):
        """Muestra el frame asegurando contigüidad de memoria (Fix BufferError)."""
        if frame is None:
            label.setText("SIN SEÑAL")
            return

        try:
            frame_contig = np.ascontiguousarray(frame)
            frame_rgb = cv2.cvtColor(frame_contig, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            label.original_pixmap = QPixmap.fromImage(qt_image)
            label.setFixedSize(self.display_w, self.display_h)

            scaled = label.original_pixmap.scaled(
                self.display_w,
                self.display_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            label.setPixmap(scaled)
            
        except Exception as e:
            logger.error(f"Error renderizando preview: {e}.")
            label.setText("⚠️ ERROR DE RENDER")

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