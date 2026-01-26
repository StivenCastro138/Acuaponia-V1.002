import cv2
import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QDoubleSpinBox, QGroupBox,
    QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from Config.Config import Config
import logging

logger = logging.getLogger(__name__)


class CalibradorEscalaVivo:
    """
    Calibrador de escala cm/px para uso desde GUI (Qt).
    Permite elegir cámara y distancia de referencia.
    """

    def __init__(self, camara_index=0, verbose=True):
        self.camara_index = camara_index
        self.verbose = verbose

        self.puntos = []
        self.modo_calibracion = False
        self.frame_congelado = None
        self.cm_reales = 10.0 

    # ======================================================================
    # UTILS
    # ======================================================================

    def log(self, msg):
        """Log con timestamp."""
        if self.verbose:
            logger.info(msg)
            print(f"[Calibrador] {msg}")

    def medir_distancia_pixeles(self, p1, p2):
        """Calcula distancia euclidiana entre dos puntos."""
        return np.hypot(p2[0] - p1[0], p2[1] - p1[1])

    def configurar_camara(self, cap):
        """Configura resolución y codec de la cámara."""
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.SAVE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.SAVE_HEIGHT)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.log(f"Resolución cámara {self.camara_index}: {w}x{h}")
        
        return w, h

    # ======================================================================
    # MOUSE CALLBACK
    # ======================================================================

    def seleccionar_puntos(self, event, x, y, flags, param):
        """Callback para selección de puntos con click izquierdo."""
        if event == cv2.EVENT_LBUTTONDOWN and self.modo_calibracion:
            if len(self.puntos) < 2:
                self.puntos.append((x, y))
                self.log(f"Punto {len(self.puntos)}: ({x}, {y})")
                
                # Feedback sonoro (opcional)
                # print('\a')  # Beep del sistema

    # ======================================================================
    # API PRINCIPAL PARA QT
    # ======================================================================

    def calibrar_en_vivo(self, camara_index=None, cm_reales=None):
        """
        Ejecuta calibración en vivo con OpenCV.
        
        Args:
            camara_index: Índice de cámara (None = usar self.camara_index)
            cm_reales: Distancia real en cm (None = usar self.cm_reales)
        
        Returns:
            float: Escala cm/px calculada, o None si se cancela
        """
        
        # Usar parámetros proporcionados o valores por defecto
        if camara_index is not None:
            self.camara_index = camara_index
        if cm_reales is not None:
            self.cm_reales = cm_reales

        self.log(f"Iniciando calibración: Cámara {self.camara_index}, Referencia {self.cm_reales} cm")

        # Abrir cámara
        cap = cv2.VideoCapture(self.camara_index)
        
        if not cap.isOpened():
            self.log(f"❌ Error: No se pudo abrir cámara {self.camara_index}")
            return None

        w, h = self.configurar_camara(cap)

        # Crear ventana
        window_name = f"Calibración - Cámara {self.camara_index}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        cv2.setMouseCallback(window_name, self.seleccionar_puntos)

        # Reiniciar estado
        self.puntos.clear()
        self.modo_calibracion = False
        self.frame_congelado = None

        # Loop principal
        while True:
            # ========== MODO PREVIEW (NO CONGELADO) ==========
            if not self.modo_calibracion:
                ret, frame = cap.read()
                if not ret:
                    self.log("❌ Error al leer frame de cámara")
                    break

                # Dibujar overlay de instrucciones
                self._dibujar_instrucciones_preview(frame)
                
                cv2.imshow(window_name, frame)

            # ========== MODO CALIBRACIÓN (CONGELADO) ==========
            else:
                display = self.frame_congelado.copy()

                # Dibujar puntos seleccionados
                for i, p in enumerate(self.puntos):
                    cv2.circle(display, p, 8, (0, 255, 0), -1)
                    cv2.circle(display, p, 10, (255, 255, 255), 2)
                    
                    # Número del punto
                    cv2.putText(
                        display,
                        str(i + 1),
                        (p[0] + 15, p[1] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 255, 0),
                        2,
                    )

                # Dibujar línea entre puntos si hay 2
                if len(self.puntos) == 2:
                    cv2.line(display, self.puntos[0], self.puntos[1], (0, 255, 0), 3)
                    
                    # Calcular y mostrar distancia
                    d_px = self.medir_distancia_pixeles(*self.puntos)
                    escala_temp = self.cm_reales / d_px if d_px > 0 else 0
                    
                    # Info en pantalla
                    info_text = [
                        f"Distancia: {d_px:.1f} px",
                        f"Referencia: {self.cm_reales} cm",
                        f"Escala: {escala_temp:.6f} cm/px"
                    ]
                    
                    y_offset = 80
                    for i, text in enumerate(info_text):
                        cv2.putText(
                            display,
                            text,
                            (20, y_offset + i * 35),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (0, 255, 255),
                            2,
                        )

                # Dibujar instrucciones de calibración
                self._dibujar_instrucciones_calibracion(display)
                
                cv2.imshow(window_name, display)

            # ========== MANEJO DE TECLAS ==========
            key = cv2.waitKey(1) & 0xFF

            # ESPACIO: Congelar imagen
            if key == 32 and not self.modo_calibracion:
                self.frame_congelado = frame.copy()
                self.modo_calibracion = True
                self.puntos.clear()
                self.log("🎯 Modo calibración activado. Selecciona 2 puntos.")

            # R: Reiniciar puntos
            elif key == ord('r') or key == ord('R'):
                self.puntos.clear()
                self.log("🔄 Puntos reiniciados")

            # ENTER: Confirmar calibración
            elif key == 13 and len(self.puntos) == 2:
                distancia_px = self.medir_distancia_pixeles(*self.puntos)
                
                if distancia_px <= 0:
                    self.log("❌ Error: Distancia inválida")
                    continue
                
                escala = self.cm_reales / distancia_px
                
                self.log(f"✅ Calibración exitosa:")
                self.log(f"   Distancia: {distancia_px:.2f} px")
                self.log(f"   Referencia: {self.cm_reales} cm")
                self.log(f"   Escala: {escala:.6f} cm/px")
                
                cap.release()
                cv2.destroyAllWindows()
                return escala

            # ESC: Cancelar
            elif key == 27:
                self.log("❌ Calibración cancelada por el usuario")
                break

        # Limpieza
        cap.release()
        cv2.destroyAllWindows()
        return None

    # ======================================================================
    # FUNCIONES AUXILIARES DE DIBUJO
    # ======================================================================

    def _dibujar_instrucciones_preview(self, frame):
        """Dibuja overlay con instrucciones en modo preview."""
        h, w = frame.shape[:2]
        
        # Fondo semi-transparente
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 100), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Título
        cv2.putText(
            frame,
            f"CALIBRACION - Referencia: {self.cm_reales} cm",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 255),
            2,
        )
        
        # Instrucciones
        cv2.putText(
            frame,
            "ESPACIO: Congelar imagen | ESC: Salir",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        
        # Cruz central (guía)
        cx, cy = w // 2, h // 2
        cv2.line(frame, (cx - 30, cy), (cx + 30, cy), (0, 255, 0), 1)
        cv2.line(frame, (cx, cy - 30), (cx, cy + 30), (0, 255, 0), 1)

    def _dibujar_instrucciones_calibracion(self, frame):
        """Dibuja overlay con instrucciones en modo calibración."""
        h, w = frame.shape[:2]
        
        # Fondo semi-transparente
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 60), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Estado
        puntos_texto = f"Puntos: {len(self.puntos)}/2"
        if len(self.puntos) == 2:
            instruccion = "ENTER: Confirmar | R: Reiniciar | ESC: Cancelar"
            color = (0, 255, 0)
        else:
            instruccion = "Click en 2 puntos | R: Reiniciar | ESC: Cancelar"
            color = (0, 255, 255)
        
        cv2.putText(
            frame,
            f"{puntos_texto} - {instruccion}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )


# ==========================================================================
# DIÁLOGO DE CONFIGURACIÓN PARA QT
# ==========================================================================

class DialogoCalibracion(QDialog):
    """
    Diálogo Qt para configurar parámetros antes de calibrar.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Configurar Calibración")
        self.setModal(True)
        self.setFixedSize(450, 350)
        
        self.camara_seleccionada = Config.CAM_LEFT_INDEX
        self.distancia_cm = 10.0
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Construye la interfaz del diálogo."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # ===== GRUPO: SELECCIÓN DE CÁMARA =====
        group_cam = QGroupBox("📹 Seleccionar Cámara")
        group_cam_layout = QVBoxLayout()
        
        self.combo_camara = QComboBox()
        self.combo_camara.addItem(
            f"🔹 Cámara Lateral (índice {Config.CAM_LEFT_INDEX})", 
            Config.CAM_LEFT_INDEX
        )
        self.combo_camara.addItem(
            f"🔹 Cámara Cenital (índice {Config.CAM_TOP_INDEX})", 
            Config.CAM_TOP_INDEX
        )
        
        group_cam_layout.addWidget(QLabel("Selecciona qué cámara quieres calibrar:"))
        group_cam_layout.addWidget(self.combo_camara)
        group_cam.setLayout(group_cam_layout)
        layout.addWidget(group_cam)
        
        # ===== GRUPO: DISTANCIA DE REFERENCIA =====
        group_dist = QGroupBox("📏 Distancia de Referencia")
        group_dist_layout = QVBoxLayout()
        
        label_dist = QLabel(
            "Ingresa la distancia REAL (en cm) del objeto\n"
            "que medirás entre los dos puntos:"
        )
        label_dist.setWordWrap(True)
        
        self.spin_distancia = QDoubleSpinBox()
        self.spin_distancia.setRange(0.1, 200.0)
        self.spin_distancia.setValue(10.0)
        self.spin_distancia.setDecimals(2)
        self.spin_distancia.setSuffix(" cm")
        self.spin_distancia.setSingleStep(0.5)
        
        # Presets comunes
        presets_layout = QHBoxLayout()
        btn_7cm = QPushButton("7 cm")
        btn_22cm = QPushButton("20 cm")
        
        btn_7cm.clicked.connect(lambda: self.spin_distancia.setValue(7.0))
        btn_22cm.clicked.connect(lambda: self.spin_distancia.setValue(22.0))
        
        presets_layout.addWidget(btn_7cm)
        presets_layout.addWidget(btn_22cm)
        
        group_dist_layout.addWidget(label_dist)
        group_dist_layout.addWidget(self.spin_distancia)
        group_dist_layout.addWidget(QLabel("Valores comunes:"))
        group_dist_layout.addLayout(presets_layout)
        group_dist.setLayout(group_dist_layout)
        layout.addWidget(group_dist)
        
        # ===== BOTONES =====
        btn_layout = QHBoxLayout()
        
        btn_iniciar = QPushButton("🚀 Iniciar Calibración")
        btn_iniciar.setStyleSheet("""
            QPushButton {
                background-color: #00b4d8;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0096c7;
            }
        """)
        btn_iniciar.clicked.connect(self.accept)
        
        btn_cancelar = QPushButton("❌ Cancelar")
        btn_cancelar.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        btn_cancelar.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_iniciar)
        btn_layout.addWidget(btn_cancelar)
        layout.addLayout(btn_layout)
    
    def get_configuracion(self):
        """
        Retorna la configuración seleccionada.
        
        Returns:
            tuple: (camara_index, distancia_cm)
        """
        return (
            self.combo_camara.currentData(),
            self.spin_distancia.value()
        )


# ==========================================================================
# FUNCIÓN WRAPPER PARA USAR DESDE LA APP PRINCIPAL
# ==========================================================================

def ejecutar_calibracion(parent=None):
    """
    Ejecuta el flujo completo de calibración con diálogo de configuración.
    
    Args:
        parent: Widget padre de Qt (opcional)
    
    Returns:
        dict: {
            'escala': float,
            'camara': int,
            'distancia_cm': float,
            'success': bool
        }
    """
    
    # 1. Mostrar diálogo de configuración
    dialogo = DialogoCalibracion(parent)
    
    if dialogo.exec() != QDialog.DialogCode.Accepted:
        logger.info("Calibracion cancelada por el usuario")
        return {'success': False, 'escala': None}
    
    # 2. Obtener configuración
    camara_idx, distancia_cm = dialogo.get_configuracion()
    
    logger.info(f"Configuracion: Camara {camara_idx}, Distancia {distancia_cm} cm")
    
    # 3. Ejecutar calibración
    calibrador = CalibradorEscalaVivo(camara_index=camara_idx, verbose=True)
    escala = calibrador.calibrar_en_vivo(
        camara_index=camara_idx,
        cm_reales=distancia_cm
    )
    
    # 4. Retornar resultado
    if escala is not None:
        return {
            'success': True,
            'escala': escala,
            'camara': camara_idx,
            'distancia_cm': distancia_cm
        }
    else:
        return {
            'success': False,
            'escala': None
        }