import cv2
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGridLayout, QSpinBox, QDoubleSpinBox,
    QGroupBox, QTextEdit, QProgressBar, QTabWidget, QComboBox,
    QCheckBox, QFileDialog, QMessageBox, QDialog, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QListWidget, QListWidgetItem, QSplitter, QSizePolicy,
    QDateEdit, QTimeEdit, QAbstractItemView, QStyle, QFrame, QInputDialog,QTabBar
)
from PySide6.QtCore import (QTimer, Qt, QCoreApplication, QDate, QTime, QSize)
from PySide6.QtGui import (QImage, QPixmap, QIntValidator, QColor, QFont, QIcon)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak 
from reportlab.platypus import Image as PDFImage 
from reportlab.lib.pagesizes import A4 
from reportlab.lib import colors 
from reportlab.lib.styles import getSampleStyleSheet
import qdarktheme 
import threading, qrcode
import urllib.request
import shutil
import darkdetect 
import time 
import os
import json
import sqlite3
from datetime import datetime
import logging
import csv
from BasedeDatos.DatabaseManager import DatabaseManager
from Config.Config import Config
from .FishDetector import FishDetector
from .FishTracker import FishTracker
from .FrameProcessor import FrameProcessor
from .StatusBar import StatusBar
from .MeasurementValidator import MeasurementValidator
from .EditMeasurementDialog import EditMeasurementDialog
from .BiometryService import BiometryService
from .ImageViewerDialog import ImageViewerDialog
from Modulos.AdvancedDetector import AdvancedDetector
from .FishAnatomyValidator import FishAnatomyValidator
from .CaptureDecisionDialog import CaptureDecisionDialog
from .OptimizedCamera import OptimizedCamera
from .ClickableLabel import ClickableLabel
from Herramientas.mobil import start_flask_server, mobile_capture_queue, get_local_ip

logger = logging.getLogger(__name__)

os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "OFF"

class MainWindow(QMainWindow):

    SPIN_CONFIGS = {
        'length': {'range': (0.1, 200.0), 'decimals': 2, 'suffix': ' cm'},
        'height': {'range': (0.1, 100.0), 'decimals': 2, 'suffix': ' cm'},
        'width':  {'range': (0.1, 100.0), 'decimals': 2, 'suffix': ' cm'},
        'weight': {'range': (0.1, 1000.0), 'decimals': 1, 'suffix': ' g'},
        'area': {'range': (0.1, 1000.0), 'decimals': 1, 'suffix': ' cm2'},
        'volume': {'range': (0.1, 1000.0), 'decimals': 1, 'suffix': ' cm3'},
        'hue_min': {'range': (0.1, 1000.0), 'decimals': 1},
        'hue_max': {'range': (0.1, 1000.0), 'decimals': 1},
        'sat_min': {'range': (0.1, 1000.0), 'decimals': 1},
        'sat_max': {'range': (0.1, 1000.0), 'decimals': 1},
        'val_min': {'range': (0.1, 1000.0), 'decimals': 1},
        'val_max': {'range': (0.1, 1000.0), 'decimals': 1},
    }
    EMOJI_STATES = {
        "✅": "success", "✓": "success", "💾": "success", "🚀": "success",
        "❌": "error", "⛔": "error", "🗑️": "error", 
        "⚠️": "warning", "⏳": "warning", 
        "🔄": "info", "🔍": "info", "📊": "info", "✏️": "info",
        "📷": "info", "▶️": "info", "⚙️": "info", "🧠": "info"
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistema Avanzado de Medición de Peces v1.3")
        self.setGeometry(100, 100, 1600, 1000)
            
        # CONFIGURACIÓN INICIAL DE LÓGICA 
        os.makedirs(Config.OUT_DIR, exist_ok=True)
        self.db = DatabaseManager()
        
        self.advanced_detector = AdvancedDetector()
        self.processor = FrameProcessor(self.advanced_detector)
        self.detector = FishDetector() 
        self.tracker = FishTracker()
        self.anatomy_validator = FishAnatomyValidator()

        # VARIABLES DE ESTADO 
        self.cap_left = None
        self.cap_top = None
        self.current_frame_left = None 
        self.current_frame_top = None
        self.auto_capture_enabled = False
        self.last_result = None
        self.scale_front_left = Config.SCALE_LAT_FRONT
        self.scale_back_left = Config.SCALE_LAT_BACK
        self.scale_front_top = Config.SCALE_TOP_FRONT
        self.scale_back_top = Config.SCALE_TOP_BACK
        self.preview_fps = Config.PREVIEW_FPS
        self.processing_lock = False  
        self.current_tab = 1          

        # INICIALIZAR UI

        self.load_config()
        self.init_ui()
        self.sync_ui_with_config()
        self.apply_appearance()
        self.toggle_theme("Sistema")

        # CONEXIONES DE SEÑALES Y TIMERS 
        if hasattr(self.processor, 'signals'):
            self.processor.signals.ia_time_ready.connect(self.status_bar.set_ia_time)
        
        # Conecta el progreso y resultados
        self.processor.progress_update.connect(self.on_progress_update)
        self.processor.result_ready.connect(self.on_processing_complete)
        self.ram_timer = QTimer(self)
        self.ram_timer.timeout.connect(self.status_bar.update_system_info)  
        self.ram_timer.start(5000)
        
        try:
            count = self.db.get_today_measurements_count()
            self.status_bar.set_measurement_count(count)
        except Exception as e:
            logger.warning(f"Error al cargar contador inicial: {e}")
            
        self.cache_params = {
            'min_area': 5000,
            'max_area': 500000,
            'conf': 0.6,
            'hsv_lat': [0, 0, 0, 0, 0, 0], 
            'hsv_top': [0, 0, 0, 0, 0, 0]
        }
        
        self.spin_min_area.valueChanged.connect(self.update_cache)
        self.spin_max_area.valueChanged.connect(self.update_cache)
        self.spin_confidence.valueChanged.connect(self.update_cache)

        self.spin_hue_min_lat.valueChanged.connect(self.update_cache)
        self.spin_hue_max_lat.valueChanged.connect(self.update_cache)
        self.spin_sat_min_lat.valueChanged.connect(self.update_cache)
        self.spin_sat_max_lat.valueChanged.connect(self.update_cache)
        self.spin_val_min_lat.valueChanged.connect(self.update_cache)
        self.spin_val_max_lat.valueChanged.connect(self.update_cache)

        self.spin_hue_min_top.valueChanged.connect(self.update_cache)
        self.spin_hue_max_top.valueChanged.connect(self.update_cache)
        self.spin_sat_min_top.valueChanged.connect(self.update_cache)
        self.spin_sat_max_top.valueChanged.connect(self.update_cache)
        self.spin_val_min_top.valueChanged.connect(self.update_cache)
        self.spin_val_max_top.valueChanged.connect(self.update_cache)

        self.update_cache()
        logger.info("✅ Sistema de variables espejo (Cache) sincronizado.")
        
        # VARIABLES DE FPS Y ARRANQUE 
        self.adaptive_fps = True
        self.last_frame_time = time.time()
        self.frames_skipped = 0
        self.fps_counter = 0
        self.last_fps_update = time.time()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frames)

        self.processor.start()
        self.start_cameras()
        self.status_bar.set_status("🚀 Sistema listo. Esperando captura")
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)  
        main_layout.addWidget(self.tabs)
        
        measurement_tab = self.create_measurement_tab()
        self.tabs.addTab(measurement_tab, "Medición Automática")
        
        
        manual_tab = self.create_manual_tab()
        self.tabs.addTab(manual_tab, "Medición Manual")
        
        history_tab = self.create_history_tab()
        self.tabs.addTab(history_tab, "Historial")
             
        stats_tab = self.create_statistics_tab()
        self.tabs.addTab(stats_tab, "Estadísticas")
        
        settings_tab = self.create_settings_tab()
        self.tabs.addTab(settings_tab, " Configuración")
        
        self.status_bar = StatusBar(self)
        main_layout.addWidget(self.status_bar)
        
        self.tabs.tabBar().setTabToolTip(0, "Medición automática desde cámara y sensores")
        self.tabs.tabBar().setTabButton(0, QTabBar.RightSide, None)

        # Medición Manual
        self.tabs.tabBar().setTabToolTip(1, "Ingreso manual de datos de medición")

        # Historial
        self.tabs.tabBar().setTabToolTip(2, "Historial de mediciones guardadas")

        # Estadísticas
        self.tabs.tabBar().setTabToolTip(3, "Análisis y estadísticas de mediciones")

        # Configuración
        self.tabs.tabBar().setTabToolTip(4, "Parámetros y configuración del sistema")

        # Cursor tipo enlace (mano)
        self.tabs.tabBar().setCursor(Qt.PointingHandCursor)
            
    def on_processing_complete(self, result):
        """
        Coordina: Desbloqueo, Validación, UI, Auto-captura
        """
        # LIBERAR RECURSOS Y UI 
        self.processing_lock = False
        
        if hasattr(self, 'btn_capture'):
            self.btn_capture.setEnabled(True)
            self.btn_capture.setText("Capturar y Analizar")
            self.btn_capture.setProperty("class", "primary") 
            self.btn_capture.style().unpolish(self.btn_capture)
            self.btn_capture.style().polish(self.btn_capture)

        if hasattr(self, 'btn_manual_ai_assist'):
            self.btn_manual_ai_assist.setEnabled(True)
            self.btn_manual_ai_assist.setText("Analizar y Rellenar con IA")

        # VALIDACIÓN ROBUSTA DEL RESULTADO
        if not result or not isinstance(result, dict):
            self._show_error_result("❌ Error: No se recibió resultado del procesador")
            return
        
        metrics = result.get('metrics', {})
        if not metrics or not isinstance(metrics, dict):
            self._show_error_result("❌ Error: Resultado sin métricas válidas")
            return
        
        length_cm = metrics.get('length_cm')
        if length_cm is None or not isinstance(length_cm, (int, float)) or length_cm <= 0:
            self._show_error_result(
                "❌ La IA no pudo detectar el pez con claridad.\n\n"
                "💡 Sugerencias:\n"
                "   • Asegúrate de que el pez esté completamente visible\n"
                "   • Verifica la iluminación del fondo\n"
                "   • Ajusta los valores HSV en Configuración"
            )
            return

        # EXTRACCIÓN SEGURA DE DATOS
        self.last_result = result
        self.last_metrics = metrics

        if hasattr(self, 'tracker') and 'contour_left' in result:
            self.tracker.update(result['contour_left'], metrics)

        confidence = float(result.get('confidence', 0.0))
        
        # VALIDACIÓN ANATÓMICA Y BIOMÉTRICA
        val_anatomica = result.get('fish_validation_left', {})
        val_biometrica = MeasurementValidator.validate_measurement(metrics)
        
        warnings = []
        
        # Advertencias de detección
        if not val_anatomica.get('is_fish', True):
            warnings.append("⚠️ Forma anatómica inusual detectada")
        if result.get('contour_left') is None:
            warnings.append("⚠️ Falta contorno lateral")
        if confidence < Config.CONFIDENCE_THRESHOLD:
            warnings.append(f"⚠️ Confianza baja ({confidence:.0%})")
        
        # Advertencias biométricas
        warnings.extend(val_biometrica)
        
        # ACTUALIZAR VISTAS CON BOUNDING BOXES
        frame_l = result.get('frame_left')
        frame_t = result.get('frame_top')
        
        if frame_l is not None and frame_t is not None:
            frame_l_copy = frame_l.copy()
            frame_t_copy = frame_t.copy()
            
            # Dibujar bounding boxes
            for key, frame in [('box_lat', frame_l_copy), ('box_top', frame_t_copy)]:
                box = result.get(key)
                if box and len(box) == 4:
                    x1, y1, x2, y2 = map(int, box)
                    color = (0, 255, 0) if not warnings else (0, 165, 255)  
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
                    
                    # Etiqueta con confianza
                    label = f"{confidence:.0%}"
                    cv2.putText(frame, label, (x1, y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
            
            self.display_frame(frame_l_copy, self.lbl_left)
            self.display_frame(frame_t_copy, self.lbl_top)
        
        # ACTUALIZAR BARRA DE CONFIANZA CON ANIMACIÓN
        if hasattr(self, 'confidence_bar'):
            target_value = int(confidence * 100)
            
            self.confidence_bar.setValue(0) 
            self._animate_confidence(0, target_value) 

        # RELLENADO AUTOMÁTICO
        if self.tabs.currentIndex() == 1:  
            self._auto_fill_manual_form(metrics, confidence)

        # GENERAR REPORTE 
        self._update_results_report(metrics, confidence, warnings, result)

        # LÓGICA DE AUTO-CAPTURA 
        self._handle_stability_and_autocapture(result, confidence, warnings)

    def _animate_confidence(self, current_value, target_value):
        """
        Anima la barra de confianza usando QPropertyAnimation.
        Se adapta a la velocidad configurada.
        """
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        
        if not hasattr(self, 'confidence_bar'):
            return
        
        # Si las animaciones están desactivadas, saltar directo al valor
        if self.anim_duration == 0:
            self.confidence_bar.setValue(target_value)
            
            # Actualizar nivel
            if target_value >= 80:
                new_level = "high"
            elif target_value >= 60:
                new_level = "medium"
            else:
                new_level = "low"
            
            self.confidence_bar.setProperty("level", new_level)
            self.confidence_bar.style().unpolish(self.confidence_bar)
            self.confidence_bar.style().polish(self.confidence_bar)
            return
        
        # ✅ USAR QPropertyAnimation para animación suave
        anim = QPropertyAnimation(self.confidence_bar, b"value")
        anim.setDuration(self.anim_duration * 3)  # Más lento para que se note
        anim.setStartValue(current_value)
        anim.setEndValue(target_value)
        
        # Curva de animación según modo
        if self.anim_duration <= 150:
            anim.setEasingCurve(QEasingCurve.OutCubic)  # Rápida
        else:
            anim.setEasingCurve(QEasingCurve.OutElastic)  # Suave con rebote
        
        # Actualizar nivel al finalizar
        def update_level():
            val = self.confidence_bar.value()
            if val >= 80:
                new_level = "high"
            elif val >= 60:
                new_level = "medium"
            else:
                new_level = "low"
            
            self.confidence_bar.setProperty("level", new_level)
            self.confidence_bar.style().unpolish(self.confidence_bar)
            self.confidence_bar.style().polish(self.confidence_bar)
        
        anim.valueChanged.connect(lambda: update_level())
        anim.start()
        
        # Guardar referencia para evitar garbage collection
        self.confidence_bar._current_anim = anim

    def _set_results_style(self, style_key):
        """Aplica estilos centralizados usando ESTADOS, no CSS manual"""
        state = style_key 
        
        self.results_text.setProperty("state", state)
        self.results_text.style().unpolish(self.results_text)
        self.results_text.style().polish(self.results_text)
        
    def on_progress_update(self, message):
        """ Actualiza barra de estado y resultados con arquitectura de ESTADOS """
        
        if hasattr(self, 'status_bar'):
            state = "normal"
            
            for emoji, mapped_state in self.EMOJI_STATES.items():
                if emoji in message:
                    state = mapped_state
                    break
            
            self.status_bar.set_status(message, state)
        
        if not hasattr(self, 'results_text'): return
        
        important_keywords = ["Detectando", "Calculando", "Analizando", "Procesando", 
                              "Validando", "Midiendo", "Completado", "Finalizado", 
                              "Listo", "Error", "Fallo", "Advertencia", "✅", "❌", "⚠️"]
        
        if not any(k in message for k in important_keywords): return
        
        current_text = self.results_text.toPlainText()
        has_final_report = "═" in current_text and len(current_text) > 200 and "RESULTADOS" in current_text
        
        if has_final_report:
            if "❌" in message or "Error" in message:
                self.results_text.append(f"\n{message}")
            return
        
        if not current_text or "═" in current_text:
            self.results_text.clear()
            if "Error" in message or "❌" in message:
                self._set_results_style("error")
            elif "⚠️" in message:
                self._set_results_style("warning")
            elif "✅" in message or "Listo" in message:
                self._set_results_style("success") 
            else:
                self._set_results_style("info")
        
        if getattr(Config, 'DEBUG_MODE', False):
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            message = f"[{timestamp}] {message}"
        
        self.results_text.append(message)

        sb = self.results_text.verticalScrollBar()
        if sb.value() >= sb.maximum() - 50:
            sb.setValue(sb.maximum())

        if len(self.results_text.toPlainText()) > 5000: 
             self.results_text.setPlainText(self.results_text.toPlainText()[-4000:])

    def _show_error_result(self, message):
        """Muestra errores usando estilo centralizado y estados lógicos"""
        self.results_text.clear()
        
        self._set_results_style("error")
        self.results_text.setPlainText(message)
        
        if hasattr(self, 'status_bar'):
            self.status_bar.set_status("❌ Error en detección", "error")
            
        if hasattr(self, 'confidence_bar'):
            self.confidence_bar.setValue(0)
            self.confidence_bar.setProperty("state", "idle") 
            self.confidence_bar.style().unpolish(self.confidence_bar)
            self.confidence_bar.style().polish(self.confidence_bar)

    def get_next_fish_number(self) -> int:
        """Calcula el siguiente número secuencial basado en el total de registros"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM measurements")
                count = cursor.fetchone()[0]
                return count + 1
        except Exception as e:
            logger.error(f"Error calculando secuencia: {e}")
            return 1
        
    def _auto_fill_manual_form(self, metrics, confidence):
        """
        Rellena formulario manual con validación y estilos limpios
        """
        try:
            field_mapping = {
                'spin_manual_length': metrics.get('length_cm', 0.0),
                'spin_manual_weight': metrics.get('weight_g', 0.0),
                'spin_manual_height': metrics.get('height_cm', 0.0),
                'spin_manual_width': metrics.get('width_cm', metrics.get('thickness_cm', 0.0))
            }
            
            for widget_name, value in field_mapping.items():
                if hasattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    
                    widget.blockSignals(True)
                    widget.setValue(float(value) if value else 0.0)
                    widget.blockSignals(False)

                    widget.setProperty("state", "success")
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)

                    QTimer.singleShot(1000, lambda w=widget: self._reset_widget_style(w))
            
            if hasattr(self, 'txt_manual_fish_id') and not self.txt_manual_fish_id.text():
                
            
                if hasattr(self, 'db'):
                    next_num = self.db.get_next_fish_number()
                else:
                    next_num = int(time.time()) 
                
                auto_id = f"IA_{next_num}"
                self.txt_manual_fish_id.setText(auto_id)
            
                self.txt_manual_fish_id.setProperty("state", "success")
                self.txt_manual_fish_id.style().unpolish(self.txt_manual_fish_id)
                self.txt_manual_fish_id.style().polish(self.txt_manual_fish_id)
                
                QTimer.singleShot(2000, lambda: self._reset_widget_style(self.txt_manual_fish_id))

            if hasattr(self, 'btn_manual_save'):
                self.btn_manual_save.setEnabled(True)
                self.btn_manual_save.setProperty("class", "success")
                self.btn_manual_save.style().unpolish(self.btn_manual_save)
                self.btn_manual_save.style().polish(self.btn_manual_save)

            if hasattr(self, 'txt_manual_notes'):
                current_notes = self.txt_manual_notes.text()
                ia_note = f"[IA: {confidence:.0%} confianza]"
                
                if ia_note not in current_notes:
                    new_notes = f"{current_notes} {ia_note}".strip()
                    self.txt_manual_notes.setText(new_notes)
  
            self.status_bar.set_status(f"✅ Formulario rellenado (Confianza: {confidence:.0%})", "success")
            
            logger.info(f"Formulario manual auto-rellenado con confianza {confidence:.0%}.")
            
        except Exception as e:
            logger.error(f"Error en auto-rellenado manual: {e}.", exc_info=True)
            self.status_bar.set_status("⚠️ Error al rellenar formulario", "warning")

    def _reset_widget_style(self, widget):
        """Helper para limpiar el estado visual"""
        widget.setProperty("state", "") 
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _update_results_report(self, metrics, confidence, warnings, result):
        """Reporte visual con validación de datos"""
        
        length_cm = metrics.get('length_cm') or 0
        weight_g = metrics.get('weight_g') or 0
        height_cm = metrics.get('height_cm') or 0
        width_cm = metrics.get('width_cm') or 0
        lat_area_cm2 = metrics.get('lat_area_cm2') or 0
        top_area_cm2 = metrics.get('top_area_cm2') or 0
        volume_cm3 = metrics.get('volume_cm3') or 0

        warning_block = ""
        if warnings:
            warning_block = "⚠️ ADVERTENCIAS:\n" + "\n".join([f"   {w}" for w in warnings]) + "\n\n"
        
        if hasattr(self, 'tracker'):
            stats = self.tracker.get_tracking_stats()
            if stats['quality'] == 0 and confidence > 0.5:
                stats = {'quality': 100, 'is_consistent': True}
        else:
            stats = {'quality': 0, 'is_consistent': False}
        
        output = f"""
    {'═'*60}
    🐟 RESULTADOS DEL ANÁLISIS BIOMÉTRICO
    {'═'*60}

    {warning_block}📏 DIMENSIONES MORFOMÉTRICAS:
    • Longitud Estimada:  {length_cm:.2f} cm
    • Peso Estimado:   {weight_g:.1f} g
    • Altura Estimada:   {height_cm:.2f} cm
    • Ancho Estimado:   {width_cm:.2f} cm
    • Área Lateral Estimada: {lat_area_cm2:.2f} cm²
    • Área Cenital Estimada: {top_area_cm2:.2f} cm²
    • Volumen Estimado: {volume_cm3:.2f} cm³
    

    📊 MÉTRICAS DE CALIDAD:
    • Confianza IA:    {confidence:.1%} {'✓' if confidence >= 0.7 else '⚠️'}
    • Tracking:        {stats['quality']:.0f}% {'(Consistente)' if stats['is_consistent'] else '(Variable)'}
    • Estabilidad:     {'✓ Estable' if result.get('is_stable', False) else '⚠️ En Movimiento'}

    {'═'*60}
    {'✅ DATOS VALIDADOS - Listo para guardar' if not warnings else '⚠️ Revise las advertencias antes de guardar'}
    {'═'*60}
    """
        self._set_results_style("success" if not warnings else "warning")
        self.results_text.setPlainText(output)
        
        if hasattr(self, 'btn_save'):
            self.btn_save.setEnabled(True)
            self.btn_save.setCursor(Qt.PointingHandCursor)
            self.btn_save.setToolTip("Guarde la medición en la base de datos.")
            self.btn_save.setProperty("class", "success")
            self.btn_save.style().unpolish(self.btn_save)
            self.btn_save.style().polish(self.btn_save)

    def _handle_stability_and_autocapture(self, result, confidence, warnings):
        """Manejo optimizado de estabilidad y captura"""
        is_stable = result.get('is_stable', False)
        motion_level = result.get('motion_level', 0)
        
        # Lógica visual simplificada
        if is_stable:
            self.lbl_stability.setText("✅ PEZ ESTABLE")
            self.lbl_stability.setProperty("state", "ok") 
        else:
            self.lbl_stability.setText(f"⚠️ EN MOVIMIENTO ({motion_level:.0f}%)")
            self.lbl_stability.setProperty("state", "warn")
        
        self.lbl_stability.style().unpolish(self.lbl_stability)
        self.lbl_stability.style().polish(self.lbl_stability)
            
        if (self.auto_capture_enabled and is_stable and confidence >= Config.CONFIDENCE_THRESHOLD 
            and not self.processing_lock and len(warnings) == 0):
            
            self.processing_lock = True
            self.status_bar.set_status("💾 Guardando medición automática...", "success")
            try:
                self._save_measurement_silent()
                QTimer.singleShot(5000, self.unlock_after_save)
            except Exception as e:
                logger.error(f"Error en auto-guardado: {e}.")
                self.processing_lock = False
                self.status_bar.set_status(f"❌ Error al guardar: {str(e)}.", "error")

    def unlock_after_save(self):
        """Desbloqueo usando estilos centralizados"""
        self.processing_lock = False
        self.results_text.clear()
        self._set_results_style("ready")
        
        self.results_text.setPlainText(
            "🟢 SISTEMA LISTO PARA SIGUIENTE MEDICIÓN\n\n"
            "Esperando que coloques otro pez...\n\n"
            "💡 El sistema guardará automáticamente cuando detecte:\n"
            " • Pez completamente estable\n"
            " • Confianza ≥ 70%\n"
            " • Sin advertencias anatómicas"
        )
        
        self.lbl_stability.setText("🟢 ESPERANDO PEZ")
        self.lbl_stability.setProperty("state", "empty") 
        self.lbl_stability.style().unpolish(self.lbl_stability)
        self.lbl_stability.style().polish(self.lbl_stability)
        
        
        if hasattr(self, 'confidence_bar'):
             self.confidence_bar.setValue(0)
             self.confidence_bar.setProperty("state", "idle")
             self.confidence_bar.style().unpolish(self.confidence_bar)
             self.confidence_bar.style().polish(self.confidence_bar)
             
        self.status_bar.set_status("⏳ Listo para próxima captura")
        logger.info("Sistema desbloqueado, listo para siguiente medicion.")

    def force_unlock_if_stuck(self):
        """Desbloqueo de emergencia"""
        if self.processing_lock:
            logger.warning("Desbloqueo de emergencia activado")
            self.processing_lock = False
            if hasattr(self, 'btn_capture'):
                self.btn_capture.setEnabled(True)
                self.btn_capture.setText("📸 Capturar y Analizar")
                self.btn_capture.setProperty("class", "primary")
                self.btn_capture.style().unpolish(self.btn_capture)
                self.btn_capture.style().polish(self.btn_capture)
            
            self.results_text.clear()
            self._set_results_style("error")
            self.results_text.setPlainText(
                "❌ TIEMPO DE PROCESAMIENTO EXCEDIDO\n\n"
                "El análisis tardó demasiado.\n\n"
                "💡 Soluciones:\n"
                " • Intenta capturar de nuevo\n"
                " • Verifica la iluminación"
            )
            self.status_bar.set_status("⚠️ Procesamiento cancelado por timeout")
            
            if hasattr(self, 'processor') and hasattr(self.processor, 'queue'):
                try:
                    while not self.processor.queue.empty(): self.processor.queue.get_nowait()
                except: pass

    def on_tab_changed(self, index):
        """
        Se ejecuta cuando cambia la pestaña activa.
        """
        old_tab = self.current_tab
        self.current_tab = index
        
        if hasattr(self, 'processor') and hasattr(self.processor, 'motion_detector'):
            self.processor.motion_detector.reset()
        
        if hasattr(self, 'auto_capture_enabled') and self.auto_capture_enabled:
            self.auto_capture_enabled = False
            if hasattr(self, 'btn_auto_capture'):
                self.btn_auto_capture.setChecked(False)
                self.btn_auto_capture.setText("🔄 Auto-Captura")
                self.btn_auto_capture.setProperty("class", "secondary")
                self.btn_auto_capture.style().unpolish(self.btn_auto_capture)
                self.btn_auto_capture.style().polish(self.btn_auto_capture)
        
        self.preview_fps = Config.PREVIEW_FPS

        if hasattr(self, 'timer') and self.timer.isActive():
            fps_ms = int(1000 / self.preview_fps)  
            self.timer.setInterval(fps_ms)

        arrow = chr(0x2192) 
        logger.info(f"Pestana cambiada: {old_tab} {arrow} {index}, FPS: {self.preview_fps}")
        
    def create_measurement_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # VISORES DE VIDEO
        video_layout = QHBoxLayout()
        
        # Cámara Lateral
        left_group = QGroupBox("Vista Lateral (Perfil)")
        left_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        left_layout = QVBoxLayout(left_group)
        self.lbl_left = ClickableLabel()
        self.lbl_left.setMinimumSize(640, 360)
        self.lbl_left.setProperty("class", "video-lateral") 
        self.lbl_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_left.setToolTip("Cámara encargada de medir Longitud y Altura del lomo del pez.")
        left_layout.addWidget(self.lbl_left)
        
        self.lbl_stability = QLabel("⚪ Esperando espécimen...")
        self.lbl_stability.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self.lbl_stability)
        video_layout.addWidget(left_group)
        
        # Cámara Cenital
        top_group = QGroupBox("Vista Cenital (Dorso)")
        top_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        top_layout = QVBoxLayout(top_group)
        self.lbl_top = ClickableLabel()
        self.lbl_top.setMinimumSize(640, 360)
        self.lbl_top.setProperty("class", "video-cenital")
        self.lbl_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_top.setToolTip("Cámara encargada de medir el Ancho dorsal del pez.")
        top_layout.addWidget(self.lbl_top)
        
        self.lbl_roi = QLabel("📌 ROI: Activo")
        self.lbl_roi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self.lbl_roi)
        video_layout.addWidget(top_group)

        layout.addLayout(video_layout)
        
        # FICHA DE RESULTADOS
        results_group = QGroupBox("Diagnóstico Biométrico en Tiempo Real")
        results_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(250)
        self.results_text.setProperty("class", "report-text") 
        self.results_text.setPlaceholderText("Esperando detección para generar reporte...")
        results_layout.addWidget(self.results_text)
        
        confidence_layout = QHBoxLayout()
        lbl_conf = QLabel("Calidad de Detección:")
        lbl_conf.setStyleSheet("font-weight: bold;")
        confidence_layout.addWidget(lbl_conf)
        
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setMaximum(100)
        self.confidence_bar.setFormat("%p% Confianza")
        self.confidence_bar.setToolTip("Precisión estimada de la IA basada en la nitidez y posición del pez.")
        confidence_layout.addWidget(self.confidence_bar)
        results_layout.addLayout(confidence_layout)
        
        layout.addWidget(results_group)
        
        # BOTONERA TÉCNICA
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        self.btn_capture = QPushButton("Captura Forzada")
        self.btn_capture.setProperty("class", "primary") 
        self.btn_capture.style().unpolish(self.btn_capture) 
        self.btn_capture.style().polish(self.btn_capture)
        self.btn_capture.setCursor(Qt.PointingHandCursor)
        self.btn_capture.setToolTip("Captura y analiza inmediatamente lo que hay en cámara.")
        self.btn_capture.clicked.connect(self.capture_and_analyze)
        controls_layout.addWidget(self.btn_capture)
        
        
        self.btn_auto_capture = QPushButton("▶️ Activar Auto-Captura")
        self.btn_auto_capture.setCheckable(True)
        self.btn_auto_capture.setProperty("class", "secondary") 
        self.btn_auto_capture.style().unpolish(self.btn_auto_capture) 
        self.btn_auto_capture.style().polish(self.btn_auto_capture)
        self.btn_auto_capture.setCursor(Qt.PointingHandCursor)
        self.btn_auto_capture.setToolTip("El sistema detectará automáticamente cuando el pez esté quieto para medirlo.")
        self.btn_auto_capture.clicked.connect(self.toggle_auto_capture)
        controls_layout.addWidget(self.btn_auto_capture)
        
        self.btn_save = QPushButton("Guardar")
        self.btn_save.setProperty("class", "success")
        self.btn_save.style().unpolish(self.btn_save) 
        self.btn_save.style().polish(self.btn_save)
        self.btn_save.setCursor(Qt.ForbiddenCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.setToolTip("Primero debe haber una medición para guardar.")
        self.btn_save.clicked.connect(self.save_measurement)
        controls_layout.addWidget(self.btn_save)
        
        layout.addLayout(controls_layout)
        
        return widget
    
    def capture_and_analyze(self):
        """
        Captura frames y los envía al hilo de procesamiento con FEEDBACK VISUAL COMPLETO.
        """
        # VALIDACIONES CRÍTICAS
        if self.processing_lock:
            logger.warning("Procesamiento ya en curso, ignorando nueva captura.")
            self.status_bar.set_status("⚠️ Ya hay un análisis en proceso", "warning")
            return
        
        if not self.cap_left or not self.cap_top:
            QMessageBox.warning(self, "Error", "❌ Cámaras no disponibles")
            return
        
        # CAPTURA DE FRAMES
        ret_left, frame_left = self.cap_left.read()
        ret_top, frame_top = self.cap_top.read()
        
        if not (ret_left and ret_top):
            QMessageBox.warning(self, "Error", "❌ No se pudieron capturar frames")
            return
        
        # BLOQUEO DE INTERFAZ Y FEEDBACK VISUAL INMEDIATO
        self.processing_lock = True
        self.btn_capture.setEnabled(False)
        self.btn_capture.setText("⏳ Analizando...")
        self.btn_capture.setProperty("class", "warning") 
        self.btn_capture.style().unpolish(self.btn_capture)
        self.btn_capture.style().polish(self.btn_capture)
        
        self.status_bar.set_status("🔍 IA Procesando captura...", "info")
        if hasattr(self, 'confidence_bar'):
             self.confidence_bar.setValue(0)
             self.confidence_bar.setProperty("state", "idle")
             self.confidence_bar.style().unpolish(self.confidence_bar)
             self.confidence_bar.style().polish(self.confidence_bar)
     
        self.results_text.clear()
        self._set_results_style("warning")
        self.results_text.append("🔄 INICIANDO ANÁLISIS BIOMÉTRICO\n")
        self.results_text.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        self.results_text.append("⏱️ Procesando... (Esto puede tomar 10-15 segundos)\n")
        self.results_text.append("🔍 Detectando contornos en ambas cámaras...\n")
        self.results_text.append("📊 Calculando métricas morfométricas...\n")
        self.results_text.append("🤖 Ejecutando validación anatómica...\n")
        self.results_text.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        #  PREPARAR PARÁMETROS COMPLETOS 
        params = {
            'scales': {
                'lat_front': self.scale_front_left,
                'lat_back': self.scale_back_left,
                'top_front': self.scale_front_top,
                'top_back': self.scale_back_top
            },
            'hsv_lateral': self.cache_params['hsv_lat'],
            'hsv_cenital': self.cache_params['hsv_top'],
            'detection': {
                'min_area': self.cache_params['min_area'],
                'max_area': self.cache_params['max_area'],
                'confidence': self.cache_params['conf']
            }
        }
        
        # ENVIAR AL PROCESADOR 
        self.processor.add_frame(frame_left, frame_top, params)
        
        # SEGURO DE DESBLOQUEO
        QTimer.singleShot(20000, self.force_unlock_if_stuck)
        logger.info("Captura manual enviada al FrameProcessor con parametros completos.")    
        
    def sync_modules_parameters(self):
        """
        Sincroniza los parámetros de FishDetector, FishTracker y FishAnatomyValidator
        con los valores actuales de la interfaz.
        """
        # Sincronizar FishDetector
        hsv_params = (
        self.spin_hue_min.value(), self.spin_hue_max.value(),
        self.spin_sat_min.value(), self.spin_sat_max.value(),
        self.spin_val_min.value(), self.spin_val_max.value()
        )
        
        if hasattr(self, 'detector') and self.detector:
            self.detector.set_hsv_ranges(*hsv_params)
            
        if hasattr(self, 'processor') and hasattr(self.processor, 'chroma_detector'):
            self.processor.chroma_detector.set_hsv_ranges(*hsv_params)

        if hasattr(self, 'tracker') and self.tracker:
            self.tracker.min_confidence = self.spin_confidence.value()
            
        if hasattr(self, 'anatomy_validator') and self.anatomy_validator:
            self.anatomy_validator.set_bounds(
                min_len=self.spin_min_length.value(),
                max_len=self.spin_max_length.value()
            )
        
        self.status_bar.set_status("⚙️ Módulos sincronizados","info")

    def create_manual_tab(self):
        """Crea la pestaña de medición manual"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Vista previa
        preview_group = QGroupBox("Monitor de Captura")
        preview_layout = QHBoxLayout(preview_group)

        self.lbl_manual_left = ClickableLabel()
        self.lbl_manual_left.setText("Cámara Lateral")
        self.lbl_manual_left.setMinimumSize(580, 340)
        self.lbl_manual_left.setProperty("class", "video-lateral")
        self.lbl_manual_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_manual_left.setToolTip("Cámara encargada de medir Longitud y Altura del lomo del pez.")
        self.lbl_manual_left.pause_callback = self.toggle_camera_pause
        preview_layout.addWidget(self.lbl_manual_left)

        self.lbl_manual_top = ClickableLabel()
        self.lbl_manual_top.setText("Cámara Cenital")
        self.lbl_manual_top.setMinimumSize(580, 340)
        self.lbl_manual_top.setProperty("class", "video-cenital")
        self.lbl_manual_top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_manual_top.setToolTip("Cámara encargada de medir el Ancho dorsal del pez.")
        self.lbl_manual_top.pause_callback = self.toggle_camera_pause
        preview_layout.addWidget(self.lbl_manual_top)

        layout.addWidget(preview_group)
        
        # Controles de Captura Principal
        controls_container = QHBoxLayout()
        
        self.btn_qr =QPushButton("Cargar Imagen del Móvil")
        self.btn_qr.setProperty("class", "info") 
        self.btn_qr.style().unpolish(self.btn_qr) 
        self.btn_qr.style().polish(self.btn_qr)
        self.btn_qr.setCursor(Qt.PointingHandCursor)
        self.btn_qr.setToolTip("Cargar una fotografía en vivo desde el celular.")
        self.btn_qr.clicked.connect(self.launch_qr_capture)
        self.btn_qr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        controls_container.addWidget(self.btn_qr, 2)
        
        self.btn_load_image = QPushButton("Cargar Imagen del PC")
        self.btn_load_image.setProperty("class", "info") 
        self.btn_load_image.style().unpolish(self.btn_load_image) 
        self.btn_load_image.style().polish(self.btn_load_image)
        self.btn_load_image.setCursor(Qt.PointingHandCursor)
        self.btn_load_image.setToolTip("Cargar una fotografía de un pez guardada previamente en el equipo.")
        self.btn_load_image.clicked.connect(self.load_external_image)
        self.btn_load_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        controls_container.addWidget(self.btn_load_image, 3)
        
        self.btn_manual_capture = QPushButton("Capturar Foto")
        self.btn_manual_capture.setProperty("class", "success")
        self.btn_manual_capture.style().unpolish(self.btn_manual_capture)
        self.btn_manual_capture.style().polish(self.btn_manual_capture)
        self.btn_manual_capture.setCursor(Qt.PointingHandCursor)
        self.btn_manual_capture.setToolTip("Congelar la imagen de las cámaras para iniciar la medición.")
        self.btn_manual_capture.clicked.connect(self.handle_manual_capture_popout)
        self.btn_manual_capture.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        controls_container.addWidget(self.btn_manual_capture, 5)

        layout.addLayout(controls_container)

        # CONTENEDOR DE DECISIÓN
        self.capture_decision_group = QWidget()
        decision_layout = QHBoxLayout(self.capture_decision_group)
        decision_layout.setContentsMargins(0, 0, 0, 0)
        
        # Botón Asistente IA
        self.btn_manual_ai_assist = QPushButton("Asistente IA")
        self.btn_manual_ai_assist.setProperty("class", "primary")
        self.btn_manual_ai_assist.style().unpolish(self.btn_manual_ai_assist)
        self.btn_manual_ai_assist.style().polish(self.btn_manual_ai_assist)
        self.btn_manual_ai_assist.setCursor(Qt.PointingHandCursor)
        self.btn_manual_ai_assist.setToolTip("Utilizar Inteligencia Artificial para detectar las medidas automáticamente sobre la foto capturada.")
        self.btn_manual_ai_assist.clicked.connect(self.run_ai_assist_manual)
        decision_layout.addWidget(self.btn_manual_ai_assist)
        
        # Botón Descartar
        self.btn_manual_discard = QPushButton("Cancelar")
        self.btn_manual_discard.setProperty("class", "warning")
        self.btn_manual_discard.style().unpolish(self.btn_manual_discard)
        self.btn_manual_discard.style().polish(self.btn_manual_discard) 
        self.btn_manual_discard.setCursor(Qt.PointingHandCursor)
        self.btn_manual_discard.setToolTip("Borrar la captura actual y volver al modo de video en vivo.")
        self.btn_manual_discard.clicked.connect(self.discard_manual_photo)
        decision_layout.addWidget(self.btn_manual_discard)

        # Botón Guardar
        self.btn_manual_save = QPushButton("Guardar")
        self.btn_manual_save.setProperty("class", "success")
        self.btn_manual_save.style().unpolish(self.btn_manual_save)
        self.btn_manual_save.style().polish(self.btn_manual_save)
        self.btn_manual_save.setCursor(Qt.PointingHandCursor)
        self.btn_manual_save.setToolTip("Guardar los datos actuales y la fotografía en la base de datos.")
        self.btn_manual_save.clicked.connect(self.save_manual_measurement)
        self.btn_manual_save.setEnabled(False) 
        decision_layout.addWidget(self.btn_manual_save)

        self.capture_decision_group.setVisible(False)
        layout.addWidget(self.capture_decision_group)
        
        # Formulario de entrada
        form_group = QGroupBox("Formulario de Biometría")
        form_layout = QGridLayout(form_group)
        form_layout.setSpacing(10)
        
        # ID Pez
        form_layout.addWidget(QLabel("ID del Pez (Diario):"), 0, 0)
        self.txt_manual_fish_id = QLineEdit()
        self.txt_manual_fish_id.setPlaceholderText("Ej: 1")
        self.txt_manual_fish_id.setValidator(QIntValidator(1, 999999))
        self.txt_manual_fish_id.setToolTip("Número identificador único para el pez en la jornada de hoy.")
        form_layout.addWidget(self.txt_manual_fish_id, 0, 1)
        
        def create_biometric_spin(suffix, tooltip):
            sb = QDoubleSpinBox()
            sb.setRange(0.1, 5000.0)
            sb.setDecimals(1)
            sb.setSuffix(f" {suffix}")
            sb.setToolTip(tooltip)
            return sb

        self.spin_manual_length = create_biometric_spin("cm", "Longitud estándar del pez.")
        form_layout.addWidget(QLabel("Longitud:"), 1, 0)
        form_layout.addWidget(self.spin_manual_length, 1, 1)
        
        self.spin_manual_height = create_biometric_spin("cm", "Altura máxima del cuerpo del pez.")
        form_layout.addWidget(QLabel("Altura:"), 2, 0)
        form_layout.addWidget(self.spin_manual_height, 2, 1)

        self.spin_manual_width = create_biometric_spin("cm", "Ancho dorsal del pez.")
        form_layout.addWidget(QLabel("Ancho:"), 3, 0)
        form_layout.addWidget(self.spin_manual_width, 3, 1)
        
        self.spin_manual_weight = create_biometric_spin("g", "Peso corporal total.")
        form_layout.addWidget(QLabel("Peso:"), 4, 0)
        form_layout.addWidget(self.spin_manual_weight, 4, 1)
        
        # Notas y Info adicional
        form_layout.addWidget(QLabel("Notas:"), 5, 0)
        self.txt_manual_notes = QLineEdit()
        self.txt_manual_notes.setPlaceholderText("Observaciones (Ej: salud, color, anomalías)")
        self.txt_manual_notes.setToolTip("Observaciones y notas del pez.")
        form_layout.addWidget(self.txt_manual_notes, 5, 1)

        form_layout.addWidget(QLabel("Archivo:"), 6, 0)
        self.lbl_filename_preview = QLabel("Pendiente...")
        self.lbl_filename_preview.setProperty("class", "report-text")
        self.lbl_filename_preview.setProperty("state", "empty")
        self.lbl_filename_preview.setToolTip("Nombre del archivo.")
        form_layout.addWidget(self.lbl_filename_preview, 6, 1)

        # Factor K con estilo visual
        form_layout.addWidget(QLabel("Factor K:"), 7, 0)
        self.lbl_k_factor_preview = QLabel("--")
        self.lbl_k_factor_preview.setAlignment(Qt.AlignCenter)
        self.lbl_k_factor_preview.setToolTip("Índice de bienestar corporal del pez.")
        self.lbl_k_factor_preview.setProperty("state", "empty")
        form_layout.addWidget(self.lbl_k_factor_preview, 7, 1)
        
        # Conexiones de señales
        self.spin_manual_length.valueChanged.connect(lambda: self.btn_manual_save.setEnabled(True))
        self.spin_manual_weight.valueChanged.connect(lambda: self.btn_manual_save.setEnabled(True))
        self.txt_manual_fish_id.textChanged.connect(self.update_filename_preview)
        self.spin_manual_length.valueChanged.connect(self.update_filename_preview)
        self.spin_manual_length.valueChanged.connect(self.update_k_factor_preview)
        self.spin_manual_height.valueChanged.connect(self.update_filename_preview)
        self.spin_manual_width.valueChanged.connect(self.update_filename_preview)
        self.spin_manual_weight.valueChanged.connect(self.update_filename_preview)
        self.spin_manual_weight.valueChanged.connect(self.update_k_factor_preview)
        
        layout.addWidget(form_group)
        layout.addStretch()
        
        self.update_k_factor_preview()
        if hasattr(self, 'generate_daily_id'):
             self.generate_daily_id()
             
        return widget

    def handle_manual_capture_popout(self):
        """Manejador estandarizado de la captura manual"""
        if self.current_frame_left is None or self.current_frame_top is None:
            QMessageBox.warning(self, "Error de Señal", "No se detectó imagen en las cámaras para capturar.")
            return

        frame_l = self.current_frame_left.copy()
        frame_t = self.current_frame_top.copy()

        dialog = CaptureDecisionDialog(frame_l, frame_t, self)
        decision = dialog.exec() 

        if decision in [1, 2]: 
            self.manual_frame_left = frame_l
            self.manual_frame_top = frame_t
            
            self.display_frame(self.manual_frame_left, self.lbl_manual_left)
            self.display_frame(self.manual_frame_top, self.lbl_manual_top)
            
            self.btn_manual_capture.setEnabled(False)
            self.btn_load_image.setEnabled(False)
            self.capture_decision_group.setVisible(True)
            
            if decision == 1:
                self.status_bar.set_status("🔍 Procesando biometría con IA...", "info")
                self.run_ai_assist_manual() 
            
            elif decision == 2:
                self.btn_manual_save.setEnabled(True)
                self.txt_manual_fish_id.setFocus()
                self.status_bar.set_status("✏️ Modo Manual: Ingrese los datos y guarde el registro.", "info")
                
        else: 
            self.status_bar.set_status("🗑️ Captura descartada. Cámara en vivo.", "warning")
            
    def _calculate_k_factor(self, length_cm, weight_g):
        """Calcula el Factor K de Fulton con validación."""
        if length_cm <= 0 or weight_g <= 0:
            return None
        return 100 * weight_g / (length_cm ** 3)
    
    def _get_k_status(self, k_value):
        """
        Determina el estado del Factor K.
        """
        if k_value is None:
            return ("empty", "--")
        
        opt_min, opt_max = getattr(Config, 'K_FACTOR_OPTIMAL', (1.0, 1.4))
        acc_min, acc_max = getattr(Config, 'K_FACTOR_ACCEPTABLE', (0.8, 1.8))
        
        if opt_min <= k_value <= opt_max:
            return ("ok", "ÓPTIMO")
        elif acc_min <= k_value <= acc_max:
            return ("warn", "ACEPTABLE")
        return ("bad", "ANORMAL")   
               
    def update_k_factor_preview(self):
        """Actualiza la etiqueta K-Factor usando ESTADOS, no colores manuales"""
        length_cm = self.spin_manual_length.value()
        weight_g = self.spin_manual_weight.value()

        k = self._calculate_k_factor(length_cm, weight_g)
        state_code, status_text = self._get_k_status(k)

        if k is not None:
            self.lbl_k_factor_preview.setText(f"{k:.3f} ({status_text})")
        else:
            self.lbl_k_factor_preview.setText(f"{status_text}")
            
        if self.lbl_k_factor_preview.property("state") != state_code:
            self.lbl_k_factor_preview.setProperty("state", state_code)
            self.lbl_k_factor_preview.style().unpolish(self.lbl_k_factor_preview)
            self.lbl_k_factor_preview.style().polish(self.lbl_k_factor_preview)

    def _create_k_factor_label(self, parent_layout):
        """Crea el label del Factor K configurado para el sistema de temas."""
        lbl_k = QLabel("Factor K: --")
        lbl_k.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_k.setMinimumHeight(45)
        lbl_k.setProperty("state", "empty") 
        
        lbl_k.setToolTip("Índice de bienestar corporal del pez.")
        parent_layout.addWidget(lbl_k)
        return lbl_k
    
    def _update_k_factor_display(self, lbl_k, length, weight):
        """Motor visual único para actualizar cualquier label de Factor K."""
        k_value = self._calculate_k_factor(length, weight)
        state, status = self._get_k_status(k_value)
        
        if k_value is None:
            lbl_k.setText(f"Factor K: {status}")
        else:
            lbl_k.setText(f"Factor K: {k_value:.3f} - {status}")

        if lbl_k.property("state") != state:
            lbl_k.setProperty("state", state)
            lbl_k.style().unpolish(lbl_k)
            lbl_k.style().polish(lbl_k)
           
    def _create_biometric_spinbox(self, field_type):
        """
        Crea un QDoubleSpinBox pre-configurado según el tipo de campo.
        Integrado con el sistema de temas mediante clases.
        """

        config = self.SPIN_CONFIGS.get(field_type)
        if not config:
            logger.error(f"Configuración no encontrada para: {field_type}")
            return QDoubleSpinBox()

        spin = QDoubleSpinBox()
        spin.setRange(*config['range'])
        spin.setDecimals(config['decimals'])
        spin.setSuffix(config['suffix'])
        spin.setCursor(Qt.IBeamCursor)
        
        return spin
    
    def load_external_image(self):
        """Carga una imagen externa y la analiza como medición manual"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Seleccionar Imagen del Pez",
            "",
            "Imágenes (*.jpg *.jpeg *.png *.bmp);;Todos los archivos (*.*)"
        )
        
        if not filename:
            return
        
        image = cv2.imread(filename)
        if image is None:
            QMessageBox.critical(self, "Error de Carga", 
                                "No se pudo interpretar el archivo de imagen.")
            return
        
        # Sincronizar con la interfaz principal
        self.display_frame(image, self.lbl_manual_left)
        self.display_frame(image, self.lbl_manual_top)
        self.manual_frame_left = image.copy()
        self.manual_frame_top = image.copy()
        
        # Crear diálogo
        dialog = QDialog(self)
        dialog.setWindowTitle("Registro de Medición Externa")
        dialog.setModal(True)
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        
        # Banner informativo
        info = QLabel(f"📂 Origen: {os.path.basename(filename)}")
        info.setProperty("state", "info") 
        layout.addWidget(info)
        
        # Formulario
        form_group = QGroupBox("Datos Biométricos")
        form_layout = QGridLayout(form_group)
        form_layout.setSpacing(10)
        
        # ID
        txt_fish_id = QLineEdit()
        if hasattr(self, 'db'):
            next_num = self.db.get_next_fish_number()
            txt_fish_id.setText(f"EXT_{next_num}") 
        
        txt_fish_id.setPlaceholderText("Ej: Lote_01")
        txt_fish_id.setToolTip("Número identificador único para el pez.")
        
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setSpecialValueText("Seleccione fecha")
        date_edit.setDate(QDate(2025, 10, 1))  
        date_edit.setMinimumDate(QDate(2000, 1, 1))
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setToolTip("Fecha en la que se midió el pez.")

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(QTime(9, 0))  
        time_edit.setToolTip("Hora en la que se midió el pez.")

        
        # ✅ USAR MÉTODO HELPER EXISTENTE
        spin_length = self._create_biometric_spinbox('length')
        spin_length.setToolTip("Longitud estándar del pez.")
        
        spin_height = self._create_biometric_spinbox('height')
        spin_height.setToolTip("Altura máxima del cuerpo del pez.")
        
        spin_width = self._create_biometric_spinbox('width')
        spin_width.setToolTip("Ancho dorsal del pez.")
        
        spin_weight = self._create_biometric_spinbox('weight')
        spin_weight.setToolTip("Peso corporal total.")
        
        txt_notes = QLineEdit()
        txt_notes.setPlaceholderText("Observaciones opcionales...")
        txt_notes.setToolTip("Observaciones y notas del pez.")
        
        # Agregar al grid
        fields = [
            ("ID del Pez:", txt_fish_id),
            ("Fecha:", date_edit),
            ("Hora:", time_edit),
            ("Longitud:", spin_length),
            ("Altura:", spin_height),
            ("Ancho:", spin_width),
            ("Peso:", spin_weight),
            ("Notas:", txt_notes)
        ]
        
        for i, (label, widget) in enumerate(fields):
            form_layout.addWidget(QLabel(label), i, 0)
            form_layout.addWidget(widget, i, 1)
        
        layout.addWidget(form_group)
        
        lbl_k_factor = self._create_k_factor_label(layout)
        
        def update_k():
            self._update_k_factor_display(
                lbl_k_factor,
                spin_length.value(),
                spin_weight.value()
            )
        
        spin_length.valueChanged.connect(update_k)
        spin_weight.valueChanged.connect(update_k)
        
        # Botonera
        btn_layout = QHBoxLayout()
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("class", "warning")
        btn_cancel.setToolTip("Cancelar guardado del registro actual.")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_save = QPushButton("Guardar")
        btn_save.setToolTip("Guardar los datos actuales y la fotografía en la base de datos.")
        btn_save.setProperty("class", "success")
        btn_save.setCursor(Qt.PointingHandCursor)
        
        def save_and_close():
            if not txt_fish_id.text().strip():
                QMessageBox.warning(dialog, "Datos Faltantes", 
                                    "El ID del pez es obligatorio.")
                return
            
            if date_edit.date() == date_edit.minimumDate():
                QMessageBox.warning(
                    dialog,
                    "Fecha requerida",
                    "Debe seleccionar una fecha válida."
                )
                return
            
            # Preparar datos
            fish_id = txt_fish_id.text().strip()
            qdate = date_edit.date()
            qtime = time_edit.time()

            timestamp = datetime(
                qdate.year(),
                qdate.month(),
                qdate.day(),
                qtime.hour(),
                qtime.minute()
            )
            filename_save = (
                f"EXTERNO"
                f"{fish_id}_"
                f"{timestamp.strftime('%Y%m%d_%H%M%S')}_"
                f"LNAcm_"
                f"HNAcm_"
                f"WNAcm_"
                f"PNAg.jpg"
            )
            filepath = os.path.join(Config.IMAGES_MANUAL_DIR, filename_save)
            
            # Anotar imagen
            img_ann = image.copy()
            cv2.putText(img_ann, f"ID: {fish_id} (EXTERNA)", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imwrite(filepath, img_ann)
            
            data = {
                'timestamp': timestamp.isoformat(),
                'fish_id': fish_id,
                'measurement_type': 'manual_externo_pc',
                
                # Campos principales
                'length_cm': spin_length.value(),
                'height_cm': spin_height.value(),
                'width_cm': spin_width.value(),
                'weight_g': spin_weight.value(),
                
                # Campos duplicados para compatibilidad
                'manual_length_cm': spin_length.value(),
                'manual_height_cm': spin_height.value(),
                'manual_width_cm': spin_width.value(),
                'manual_weight_g': spin_weight.value(),
                
                # Campos técnicos
                'lat_area_cm2': 0,
                'top_area_cm2': 0,
                'volume_cm3': 0,
                'confidence_score': 1.0,
                
                # Metadatos
                'notes': f"[IMAGEN EXTERNA PC] {txt_notes.text()}",
                'image_path': filepath,
                'validation_errors': ''
            }
            
            self.db.save_measurement(data)
            self.refresh_history()
            dialog.accept()
            QMessageBox.information(self, "✅ Guardado", 
                                    "La medición externa se registró correctamente.")
        
        btn_save.clicked.connect(save_and_close)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.Accepted:
            self.status_bar.set_status("✅ Imagen externa procesada y guardada.", "success")
        else:
            self.status_bar.set_status("🗑️ Carga externa cancelada.", "warning")

    def _process_external_capture(self, image_path, is_mobile=False):
        """Diálogo de registro biométrico para fotos externas/móviles"""
        image = cv2.imread(image_path)
        if image is None:
            QMessageBox.critical(self, "Error", 
                                "No se pudo cargar la imagen capturada.")
            return
        
        # Actualizar vistas previas
        self.display_frame(image, self.lbl_manual_left)
        self.display_frame(image, self.lbl_manual_top)
        self.manual_frame_left = image.copy()
        self.manual_frame_top = image.copy()
        
        # Crear diálogo
        dialog = QDialog(self)
        dialog.setWindowTitle("Registro de Biometría")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        
        # Banner
        origin_text = "📱 Dispositivo Móvil (QR)" if is_mobile else "💻 Explorador de Archivos"
        banner = QLabel(f"Origen: {origin_text}")
        banner.setProperty("state", "info")
        layout.addWidget(banner)
        
        # Formulario
        form_group = QGroupBox("Detalles del Pez")
        form_grid = QGridLayout(form_group)
        form_grid.setSpacing(10)
        
        txt_id = QLineEdit()
        if hasattr(self, 'db'):
             prefix = "QR" if is_mobile else "EXT"
             txt_id.setText(f"{prefix}_{self.db.get_next_fish_number()}")
            
        txt_id.setPlaceholderText("Ej: TRUCHA-001")
        txt_id.setToolTip("Número identificador único para el pez.")
        
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setSpecialValueText("Seleccione fecha")
        date_edit.setDate(QDate(2025, 10, 1))   
        date_edit.setMinimumDate(QDate(2025, 10, 1))
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setToolTip("Fecha en la que se midió el pez.")

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(QTime(9, 0))  
        time_edit.setToolTip("Hora en la que se midió el pez.")
        
        spin_length = self._create_biometric_spinbox('length')
        spin_length.setToolTip("Longitud estándar del pez.")
        
        spin_height = self._create_biometric_spinbox('height')
        spin_height.setToolTip("Altura máxima del cuerpo.")
        
        spin_width = self._create_biometric_spinbox('width')
        spin_width.setToolTip("Ancho dorsal del pez.")
        
        spin_weight = self._create_biometric_spinbox('weight')
        spin_weight.setToolTip("Peso corporal total.")
        
        txt_notes = QLineEdit()
        txt_notes.setPlaceholderText("Observaciones opcionales...")
        txt_notes.setToolTip("Observaciones y notas del pez.")
        

        fields = [
            ("ID Pez:", txt_id),
            ("Fecha:", date_edit),
            ("Hora:", time_edit),
            ("Longitud:", spin_length),
            ("Altura:", spin_height),
            ("Ancho:", spin_width),
            ("Peso:", spin_weight),
            ("Notas:", txt_notes)
        ]
        
        for i, (label, widget) in enumerate(fields):
            form_grid.addWidget(QLabel(label), i, 0)
            form_grid.addWidget(widget, i, 1)
        
        layout.addWidget(form_group)
        
        lbl_k = self._create_k_factor_label(layout)
        
        def update_k_realtime():
            self._update_k_factor_display(lbl_k, spin_length.value(), spin_weight.value())
        
        spin_length.valueChanged.connect(update_k_realtime)
        spin_weight.valueChanged.connect(update_k_realtime)
        
        # Botonera
        btn_layout = QHBoxLayout()
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("class", "warning")
        btn_cancel.setToolTip("Cancelar guardado del registro actual.")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_save = QPushButton("Guardar")
        btn_save.setProperty("class", "success")
        btn_save.setToolTip("Guardar los datos actuales y la fotografía en la base de datos.")
        btn_save.setCursor(Qt.PointingHandCursor)
        
        def save_final():
            if not txt_id.text().strip():
                QMessageBox.warning(dialog, "Error", "El ID del pez es obligatorio.")
                return
            if date_edit.date() == date_edit.minimumDate():
                QMessageBox.warning(
                    dialog,
                    "Fecha requerida",
                    "Debe seleccionar una fecha válida."
                )
                return

         
            try:
                qdate = date_edit.date()
                qtime = time_edit.time()

                timestamp = datetime(
                    qdate.year(),
                    qdate.month(),
                    qdate.day(),
                    qtime.hour(),
                    qtime.minute()
                )

                data = {
                    'timestamp': timestamp.isoformat(),
                    'fish_id': txt_id.text().strip(),
                    'measurement_type': 'manual_qr' if is_mobile else 'manual_pc',
                    
                    # Campos principales
                    'length_cm': spin_length.value(),
                    'height_cm': spin_height.value(),
                    'width_cm': spin_width.value(),
                    'weight_g': spin_weight.value(),
                    
                    # Campos duplicados para compatibilidad
                    'manual_length_cm': spin_length.value(),
                    'manual_height_cm': spin_height.value(),
                    'manual_width_cm': spin_width.value(),
                    'manual_weight_g': spin_weight.value(),
                    
                    # Campos técnicos
                    'lat_area_cm2': 0,
                    'top_area_cm2': 0,
                    'volume_cm3': 0,
                    'confidence_score': 1.0,
                    
                    # Metadatos
                    'image_path': image_path,
                    'notes': f"[IMAGEN EXTERNA QR] {txt_notes.text()}",
                    'validation_errors': ''
                }
                
                db = getattr(self, 'db_manager', getattr(self, 'db', None))
                if db:
                    db.save_measurement(data)
                    self.refresh_history()
                    dialog.accept()
                else:
                    raise Exception("Base de datos no disponible")
                        
            except Exception as e:
                logger.error(f"Error guardando captura externa: {e}")
                QMessageBox.critical(dialog, "Error", f"No se pudo guardar: {str(e)}")
        
        btn_save.clicked.connect(save_final)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.Accepted:
            self.status_bar.set_status("✅ Medición externa guardada con éxito", "success")
        else:
            self.status_bar.set_status("🗑️ Captura externa descartada", "warning")         

    def launch_qr_capture(self):
        """
        Muestra diálogo con QR para captura remota con diseño estandarizado.
        """
        pc_ip = get_local_ip() 
        port = 5000
        url = f"http://{pc_ip}:{port}/"
        qr_path = os.path.join(Config.IMAGES_MANUAL_DIR, "temp_qr.png")

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,  
                box_size=10,
                border=2
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(qr_path)
        except Exception as e:
            logger.error(f"Error generando QR: {e}.")
            self.status_bar.set_status("❌ Error al generar código QR", "error")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Captura Remota Móvil")
        dialog.setFixedSize(450, 620)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        lbl_title = QLabel("Captura desde Móvil")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setProperty("class", "header-text") 
        layout.addWidget(lbl_title)

        lbl_instructions = QLabel(
            "1. Escanea el código QR con tu celular\n"
            "2. Captura las fotos (lateral + cenital)\n"
            "3. Envía las imágenes al sistema"
        )
        lbl_instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_instructions.setProperty("class", "report-text") 
        lbl_instructions.setProperty("state", "info")
        layout.addWidget(lbl_instructions)
        

        lbl_qr = QLabel()
        pixmap = QPixmap(qr_path)
        if not pixmap.isNull():
            lbl_qr.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_qr.setStyleSheet("background-color: white; padding: 15px; border-radius: 10px;")
        layout.addWidget(lbl_qr)
        
        lbl_status = QLabel("Esperando captura del móvil...")
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status.setProperty("state", "warning") 
        layout.addWidget(lbl_status)

        btn_layout = QHBoxLayout()
        
        btn_test = QPushButton("Verificar")
        btn_test.setProperty("class", "primary") 
        btn_test.clicked.connect(lambda: os.system(f'start {url}'))  
        btn_test.setToolTip("Verífica que la página este activa.")
        
        btn_cancel = QPushButton("Cerrar")
        btn_cancel.setProperty("class", "warning") 
        btn_cancel.setToolTip("Cerrar el código QR.")
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(btn_test)
        btn_layout.addWidget(btn_test)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        if not hasattr(self, "_flask_started") or not self._flask_started:
            try:
                flask_thread = threading.Thread(
                    target=start_flask_server,
                    kwargs={'host': '0.0.0.0', 'port': port, 'debug': Config.DEBUG_MODE},
                    daemon=True, name="FlaskMobileServer"
                )
                flask_thread.start()
                self._flask_started = True
                self.status_bar.set_status(f"🌐 Servidor activo en {pc_ip}", "success")
            except Exception as e:
                logger.error(f"Error al iniciar Flask: {e}.")
                self.status_bar.set_status("❌ Error al iniciar servidor", "error")
                dialog.reject()
                return
        else:
            self.status_bar.set_status(f"🌐 Servidor reanudado en {pc_ip}", "info")
        
        timer = QTimer(dialog)
        timer.setInterval(300)

        def check_mobile_capture():
            """Verifica si llegó una captura desde el móvil."""
            if not mobile_capture_queue.empty():
                try:
                    # Obtener ruta de la imagen
                    image_path = mobile_capture_queue.get(block=False)
                    
                    Config.logger.info(f"Captura móvil recibida: {image_path}")
                    
                    # Detener timer
                    timer.stop()
                    
                    # Actualizar estado
                    lbl_status.setText("✅ ¡Imagen recibida!")
                    lbl_status.setStyleSheet("""
                        padding: 10px;
                        color: #2a9d8f;
                        font-weight: bold;
                    """)
                    
                    # Cerrar diálogo después de un breve delay para feedback visual
                    QTimer.singleShot(800, dialog.accept)
                    
                    # Procesar la imagen capturada
                    QTimer.singleShot(900, lambda: self._process_external_capture(
                        image_path, 
                        is_mobile=True
                    ))
                    
                except Exception as e:
                    Config.logger.error(f"Error procesando captura móvil: {e}")
                    lbl_status.setText("❌ Error al procesar imagen")
                    lbl_status.setStyleSheet("color: #e63946;")
        
        timer.timeout.connect(check_mobile_capture)
        timer.start()
        
        
        try:
            result = dialog.exec()
            
            # Detener timer al cerrar
            timer.stop()
            
            # Limpiar archivo QR temporal
            try:
                if os.path.exists(qr_path):
                    os.remove(qr_path)
            except Exception as e:
                logger.warning(f"No se pudo eliminar QR temporal: {e}")
            
            # Actualizar estado según resultado
            if result == QDialog.DialogCode.Accepted:
                self.status_bar.set_status("✅ Captura móvil procesada correctamente")
            else:
                self.status_bar.set_status("⛔ Captura móvil cancelada")
                logger.info("Usuario cancelo captura movil.")
        
        except Exception as e:
            logger.error(f"Error en dialogo de captura QR: {e}.", exc_info=True)
            self.status_bar.set_status("❌ Error en captura móvil")

    def verify_flask_server(ip, port=5000, timeout=2):
        """
        Verifica si el servidor Flask está activo.
        """
        url = f"http://{ip}:{port}/ping"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                if response.status == 200:
                    data = response.read().decode('utf-8')
                    return "online" in data.lower()
                return False
        except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
            return False
        except Exception as e:
            logger.debug(f"Error inesperado verificando servidor: {e}")
            return False

    def update_filename_preview(self):
        """Actualiza el preview del nombre de archivo con estados lógicos"""
        fish_id = self.txt_manual_fish_id.text().strip()
        length_cm = self.spin_manual_length.value()
        height_cm = self.spin_manual_height.value()  
        width_cm = self.spin_manual_width.value()   
        weight_g = self.spin_manual_weight.value()
        
        if fish_id:
            timestamp = datetime.now()

            filename = (
                f"MANUAL_"
                f"{fish_id}_"
                f"{timestamp.strftime('%Y%m%d_%H%M%S')}_"
                f"L{length_cm:.1f}cm_"
                f"H{height_cm:.1f}cm_"
                f"W{width_cm:.1f}cm_"
                f"P{weight_g:.1f}g.jpg"
            )

            self.lbl_filename_preview.setText(filename)

            self.lbl_filename_preview.setProperty("state", "success")
        else:
            self.lbl_filename_preview.setText("⚠️ Ingrese un ID para generar el nombre")
            self.lbl_filename_preview.setProperty("state", "error")

        self.lbl_filename_preview.style().unpolish(self.lbl_filename_preview)
        self.lbl_filename_preview.style().polish(self.lbl_filename_preview)

    def refresh_daily_counter(self):
        """Actualiza el contador de la barra de estado con los datos de HOY"""
        db = getattr(self, 'db_manager', getattr(self, 'db', None))
        
        if db and hasattr(self, 'status_bar'):
            try:
                count_today = db.get_today_measurements_count()
                self.status_bar.set_measurement_count(count_today)
            except Exception as e:

                logger.error(f"Error al refrescar contador diario: {e}.")
                self.status_bar.set_measurement_count(0)

    def discard_manual_photo(self):
        """Limpia la foto capturada y resetea la interfaz con estados limpios"""
        self.manual_frame_left = None
        self.manual_frame_top = None
        
        self.capture_decision_group.setVisible(False)
        self.btn_manual_capture.setEnabled(True)
        self.btn_load_image.setEnabled(True)
        
        self.spin_manual_length.setValue(0.0)
        self.spin_manual_height.setValue(0.0) 
        self.spin_manual_width.setValue(0.0)
        self.spin_manual_weight.setValue(0.0)
        self.txt_manual_notes.clear()
        
        widgets_to_reset = [
            self.spin_manual_length, self.spin_manual_weight, 
            self.spin_manual_height, self.spin_manual_width,
            self.txt_manual_fish_id
        ]
        
        for w in widgets_to_reset:
            w.setProperty("state", "") 
            w.style().unpolish(w)
            w.style().polish(w)

        self.update_k_factor_preview() #
        self.update_filename_preview()
        
        self.status_bar.set_status("🔄 Cámara en vivo lista para nueva captura", "info")
        
        logger.info("Captura manual descartada, volviendo a video en vivo.")
    
    def run_ai_assist_manual(self):
        """
        Ejecuta el análisis de IA sobre la foto capturada manualmente
        """
        # 1. Validación
        if self.manual_frame_left is None or self.manual_frame_top is None:
            QMessageBox.warning(self, "Error", "No hay fotos capturadas para analizar.")
            return

        # 2. Feedback UI
        self.btn_manual_ai_assist.setEnabled(False)
        self.btn_manual_ai_assist.setText("⏳ IA Analizando...")
        self.status_bar.set_status("🤖 BiometryService analizando captura", "info")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            # 3. Instanciar servicio
            service = BiometryService(self.advanced_detector)

            # 4. Ejecutar análisis 
            metrics, img_lat_ann, img_top_ann = service.analyze_and_annotate(
                img_lat=self.manual_frame_left,
                img_top=self.manual_frame_top,
                scale_lat_front=self.scale_front_left,
                scale_lat_back=self.scale_back_left,
                scale_top_front=self.scale_front_top,
                scale_top_back=self.scale_back_top,
                draw_box=True,     
                draw_skeleton=True
            )

            if metrics and metrics.get('length_cm', 0) > 0:
                # 5. Construir resultado compatible
                result_fake = {
                    'metrics': metrics,
                    'confidence': metrics.get('confidence', 0.95),
                    'frame_left': img_lat_ann,
                    'frame_top': img_top_ann,
                    'is_stable': True,
                    'fish_validation_left': {'is_fish': True},
                    'contour_left': True,
                    'contour_top': True
                }

                # 6. Actualizar UI unificada
                self.on_processing_complete(result_fake)

                self.display_frame(img_lat_ann, self.lbl_manual_left)
                self.display_frame(img_top_ann, self.lbl_manual_top)

                self.status_bar.set_status("✅ Análisis de BiometryService completo", "success")
            
            else:
                self.status_bar.set_status("❌ La IA no detectó el pez claramente", "warning")
                self._set_results_style("error")
                self.results_text.setPlainText("❌ Error: No se pudo identificar la biometría en esta foto.\nIntente reubicar el pez o mejorar la iluminación.")

        except Exception as e:
            logger.error(f"Error en run_ai_assist_manual: {e}")
            self.status_bar.set_status(f"❌ Error de IA: {str(e)}", "error")
            self._set_results_style("error")

        finally:
            QApplication.restoreOverrideCursor()
            self.btn_manual_ai_assist.setEnabled(True)
            self.btn_manual_ai_assist.setText("🤖 Asistente IA")

    def save_measurement(self):
        """
        Guarda mediciones automáticas con TODOS los campos
        
        """

        if not self.last_result or self.processing_lock:
            logger.warning("No hay resultado para guardar o sistema bloqueado")
            return
        
        metrics = self.last_result.get('metrics', {})
        if not metrics:
            logger.error("Resultado sin metricas validas")
            return

        validation_errors = MeasurementValidator.validate_measurement(metrics)
        
        if validation_errors and not self.auto_capture_enabled:
            errors_text = "\n".join(validation_errors)
            reply = QMessageBox.question(
                self, "⚠️ Validación", 
                f"Se detectaron las siguientes advertencias:\n\n{errors_text}\n\n"
                "¿Desea guardar de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        try:
            QApplication.processEvents()
            
            length_cm = float(metrics.get('length_cm', 0.0))
            weight_g = float(metrics.get('weight_g', 0.0))
     
            height_cm = float(metrics.get('height_cm', 0.0))
            width_cm = float(metrics.get('width_cm', metrics.get('thickness_cm', 0.0)))
            
            lat_area_cm2 = float(metrics.get('lat_area_cm2', 0.0))
            top_area_cm2 = float(metrics.get('top_area_cm2', 0.0))
            volume_cm3 = float(metrics.get('volume_cm3', 0.0))
            confidence = float(self.last_result.get('confidence', 0.8))
            
            timestamp = datetime.now()
            
            try:
                count_today = self.db.get_today_measurements_count()
                fish_id = str(count_today + 1)  
                logger.info(f"Using daily counter for fish_id: {fish_id}")
            except:
                fish_id = f"AUTO_{timestamp.strftime('%Y%m%d_%H%M%S')}"
                logger.warning(f"Daily counter failed, using timestamp: {fish_id}")
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # PREPARAR NOMBRE DE ARCHIVO DESCRIPTIVO
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            filename_parts = [
                f"auto_{fish_id}",
                f"L{length_cm:.1f}cm"
            ]
            
            # ✅ Solo agregar al nombre si existen
            if height_cm > 0:
                filename_parts.append(f"H{height_cm:.1f}cm")
            if width_cm > 0:
                filename_parts.append(f"W{width_cm:.1f}cm")
            
            filename_parts.extend([
                f"P{weight_g:.1f}g",
                timestamp.strftime('%Y%m%d_%H%M%S')
            ])
            
            filename = "_".join(filename_parts) + ".jpg"
            filepath = os.path.join(Config.IMAGES_AUTO_DIR, filename)
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # PREPARAR IMAGEN CON ANOTACIONES
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            frame_left = self.last_result['frame_left'].copy()
            frame_top = self.last_result['frame_top'].copy()
            
            # Dibujar contornos si existen
            contour_left = self.last_result.get('contour_left')
            contour_top = self.last_result.get('contour_top')
            
            if contour_left is not None and isinstance(contour_left, np.ndarray) and len(contour_left) >= 3:
                cv2.drawContours(frame_left, [contour_left], -1, (0, 255, 0), 3)
            
            if contour_top is not None and isinstance(contour_top, np.ndarray) and len(contour_top) >= 3:
                cv2.drawContours(frame_top, [contour_top], -1, (0, 255, 0), 3)
            
            # Combinar frames
            combined = np.hstack((
                cv2.resize(frame_left, (Config.SAVE_WIDTH, Config.SAVE_HEIGHT)),
                cv2.resize(frame_top, (Config.SAVE_WIDTH, Config.SAVE_HEIGHT))
            ))
            
            # ✅ MEJORADO: Anotaciones con TODAS las dimensiones
            font = cv2.FONT_HERSHEY_SIMPLEX
            y_pos = 30
            
            # Encabezado
            cv2.putText(combined, f"AUTO: Pez #{fish_id}", (10, y_pos), 
                        font, 0.9, (0, 255, 255), 2)
            
            # Dimensiones principales
            y_pos += 40
            dimensions_text = f"L: {length_cm:.2f}cm"
            if height_cm > 0:
                dimensions_text += f" | H: {height_cm:.2f}cm"
            if width_cm > 0:
                dimensions_text += f" | W: {width_cm:.2f}cm"
            
            cv2.putText(combined, dimensions_text, (10, y_pos), 
                        font, 0.7, (0, 255, 0), 2)
            
            # Peso
            y_pos += 35
            cv2.putText(combined, f"Peso: {weight_g:.1f}g", (10, y_pos), 
                        font, 0.7, (0, 255, 0), 2)
            
            # Confianza
            y_pos += 35
            cv2.putText(combined, f"Confianza: {confidence:.0%}", (10, y_pos), 
                        font, 0.7, (0, 255, 0), 2)
            
            # Timestamp
            y_pos += 35
            cv2.putText(combined, timestamp.strftime('%Y-%m-%d %H:%M:%S'), (10, y_pos), 
                        font, 0.6, (180, 180, 180), 2)
            
            # Guardar imagen
            cv2.imwrite(filepath, combined)
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # PREPARAR DATOS PARA BASE DE DATOS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            data = {
                'timestamp': timestamp.isoformat(),
                'fish_id': fish_id,  
                
                # Dimensiones principales
                'length_cm': length_cm,
                'height_cm': height_cm, 
                'width_cm': width_cm,    
                'weight_g': weight_g,
                
                'manual_length_cm': length_cm,
                'manual_height_cm': height_cm,  
                'manual_width_cm': width_cm,    
                'manual_weight_g': weight_g,
                
                # Campos calculados
                'lat_area_cm2': lat_area_cm2,
                'top_area_cm2': top_area_cm2,
                'volume_cm3': volume_cm3,
                
                # Metadatos
                'confidence_score': confidence,
                'scale_lateral': self.last_result.get('scale_left', self.scale_front_left),
                'scale_top': self.last_result.get('scale_top', self.scale_front_top),
                'image_path': filepath,
                'measurement_type': 'auto',
                'notes': '[Medición Semiautomática]',
                'validation_errors': ', '.join(validation_errors) if validation_errors else ''
            }
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # GUARDAR EN BASE DE DATOS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            measurement_id = self.db.save_measurement(data)
            
            # ✅ Logging detallado
            logger.info(
                f"Auto measurement saved: "
                f"ID={measurement_id}, "
                f"FishID={fish_id}, "
                f"L={length_cm:.1f}cm, "
                f"H={height_cm:.1f}cm, "
                f"W={width_cm:.1f}cm, "
                f"P={weight_g:.1f}g, "
                f"Conf={confidence:.0%}"
            )
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ACTUALIZAR INTERFAZ
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            self.btn_save.setEnabled(False)
            
            # Actualizar historial
            self.current_page_offset = 0
            QApplication.processEvents()
            self.refresh_history()
            self.refresh_daily_counter()
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # NOTIFICACIÓN SEGÚN MODO
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if self.auto_capture_enabled:
                self.status_bar.set_status(f"✅ Pez #{fish_id} guardado con éxito", "success")
            else:
                self.status_bar.set_status(f"✅ Pez #{fish_id} guardado con éxito", "success")
                message_parts = [
                    f"✅ Medición #{measurement_id} guardada correctamente\n",
                    f"🐟 Pez ID: {fish_id}\n",
                    f"📄 Archivo: {filename}\n\n",
                    "📊 DIMENSIONES:\n",
                    f"   • Longitud: {length_cm:.1f} cm\n"
                ]
                
                if height_cm > 0:
                    message_parts.append(f"   • Altura: {height_cm:.1f} cm\n")
                if width_cm > 0:
                    message_parts.append(f"   • Ancho: {width_cm:.1f} cm\n")
                
                message_parts.append(f"   • Peso: {weight_g:.1f} g\n")
                message_parts.append(f"\n🎯 Confianza: {confidence:.0%}")
                
                QMessageBox.information(self, "✅ Guardado Exitoso", "".join(message_parts))
            
        except Exception as e:
            logger.error(f"Error en save_measurement: {e}", exc_info=True)
            
            if not self.auto_capture_enabled:
                QMessageBox.critical(self, "❌ Error", f"No se pudo guardar la medición:\n\n{str(e)}")
            else:
                self.status_bar.set_status(f"❌ Error al guardar: {str(e)}", "error")  
    
    def save_manual_measurement(self):
        """
        Guarda medición manual COMPLETA:
        """

        fish_id = str(self.txt_manual_fish_id.text().strip())
        
        try:
            length_cm = float(self.spin_manual_length.value())
            height_cm = float(self.spin_manual_height.value())
            width_cm = float(self.spin_manual_width.value())
            weight_g = float(self.spin_manual_weight.value())
        except ValueError:
            QMessageBox.warning(self, "Error", "Valores numéricos inválidos.")
            return

        notes = str(self.txt_manual_notes.text().strip())
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PASO 2: VALIDACIONES
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if not fish_id:
            QMessageBox.warning(self, "⚠️ Campo Requerido", "Debe ingresar un ID para el pez.")
            self.status_bar.set_status("⚠️ Falta ID del pez", "warning")
            self.txt_manual_fish_id.setFocus()
            return

        if len(fish_id) > 50:
            QMessageBox.warning(self, "⚠️ ID Largo", "El ID no puede superar los 50 caracteres.")
            return
        
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', fish_id):
            QMessageBox.warning(self, "⚠️ ID Inválido", "Solo letras, números, guiones y guiones bajos.")
            return
        
        if not hasattr(self, 'manual_frame_left') or self.manual_frame_left is None:
            QMessageBox.warning(self, "⚠️ Sin Imagen", "Falta la captura lateral.")
            return
        if not hasattr(self, 'manual_frame_top') or self.manual_frame_top is None:
            QMessageBox.warning(self, "⚠️ Sin Imagen", "Falta la captura cenital.")
            return

        # Validación lógica
        if length_cm <= 0 or weight_g <= 0:
            reply = QMessageBox.question(
                self, "⚠️ Valores Cero", 
                "Longitud o peso son 0. ¿Guardar de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No: return

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PASO 3: GUARDAR IMAGEN (CON TODOS LOS DIBUJOS ORIGINALES)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        try:
            timestamp = datetime.now()
            safe_fish_id = re.sub(r'[^\w\-]', '_', fish_id)
            
            filename = (
                f"{safe_fish_id}_"
                f"L{length_cm:.1f}_"
                f"P{weight_g:.1f}_"
                f"{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            )
            filepath = os.path.join(Config.IMAGES_MANUAL_DIR, filename)
            os.makedirs(Config.IMAGES_MANUAL_DIR, exist_ok=True)
            
            # --- Resize y Combine ---
            frame_left_resized = cv2.resize(self.manual_frame_left, (Config.SAVE_WIDTH, Config.SAVE_HEIGHT), interpolation=cv2.INTER_CUBIC)
            frame_top_resized = cv2.resize(self.manual_frame_top, (Config.SAVE_WIDTH, Config.SAVE_HEIGHT), interpolation=cv2.INTER_CUBIC)
            combined = np.hstack((frame_left_resized, frame_top_resized))
            
            # --- DIBUJO DETALLADO (Restaurado) ---
            font = cv2.FONT_HERSHEY_SIMPLEX
            color_cyan = (0, 255, 255)
            color_green = (0, 255, 0)
            color_gray = (150, 150, 150)

            # 1. Título con fondo
            cv2.rectangle(combined, (0, 0), (combined.shape[1], 50), (40, 40, 40), -1)
            cv2.putText(combined, f"MEDICION MANUAL: {fish_id}", (10, 35), font, 1.2, color_cyan, 3)
            
            # 2. Dimensiones
            y_offset = 80
            cv2.putText(combined, 
                        f"L: {length_cm:.1f} cm | H: {height_cm:.1f} cm | W: {width_cm:.1f} cm",
                        (10, y_offset), font, 0.9, color_green, 2)
            
            y_offset += 40
            cv2.putText(combined, f"Peso: {weight_g:.1f} g", 
                        (10, y_offset), font, 0.9, color_green, 2)
            
            # 3. Factor K con Lógica de Colores
            if length_cm > 0 and weight_g > 0:
                k_factor = 100 * weight_g / (length_cm ** 3)
                y_offset += 40
                
                # Semáforo de colores
                if 0.8 <= k_factor <= 1.8:
                    k_color = (0, 255, 0)  # Verde
                    k_status = "OPTIMO"
                elif 0.5 <= k_factor <= 2.5:
                    k_color = (0, 165, 255)  # Naranja
                    k_status = "ACEPTABLE"
                else:
                    k_color = (0, 0, 255)  # Rojo
                    k_status = "ANORMAL"
                
                cv2.putText(combined, f"Factor K: {k_factor:.3f} ({k_status})",
                            (10, y_offset), font, 0.8, k_color, 2)
            
            # 4. Timestamp
            y_offset += 40
            cv2.putText(combined, timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        (10, y_offset), font, 0.7, color_gray, 2)
            
            # 5. Notas (Truncadas)
            if notes:
                y_offset += 35
                display_notes = notes[:80] + "..." if len(notes) > 80 else notes
                cv2.putText(combined, f"Notas: {display_notes}",
                            (10, y_offset), font, 0.6, color_gray, 1)
            
            # 6. Etiquetas de Vistas (Abajo)
            cv2.putText(combined, "Vista Lateral", (20, combined.shape[0] - 20), font, 0.8, color_gray, 2)
            cv2.putText(combined, "Vista Cenital", (Config.SAVE_WIDTH + 20, combined.shape[0] - 20), font, 0.8, color_gray, 2)
            
            # Guardar
            if not cv2.imwrite(filepath, combined):
                raise IOError("Fallo cv2.imwrite")
                
        except Exception as e:
            QMessageBox.critical(self, "Error Guardando Imagen", f"{e}")
            return

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PASO 4: PREPARAR DATOS (BLINDADOS + COMPLETOS)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        ai_lat_area = 0.0
        ai_top_area = 0.0
        ai_vol = 0.0
        # Intentar recuperar datos de IA si existen
        if hasattr(self, 'last_metrics') and self.last_metrics:
            ai_lat_area = float(self.last_metrics.get('lat_area_cm2', 0))
            ai_top_area = float(self.last_metrics.get('top_area_cm2', 0))
            ai_vol = float(self.last_metrics.get('volume_cm3', 0))

        data = {
            'timestamp': timestamp.isoformat(),
            'fish_id': str(fish_id),
            
            # Floats
            'length_cm': float(length_cm),
            'height_cm': float(height_cm),
            'width_cm': float(width_cm),
            'weight_g': float(weight_g),
            
            # Manuales
            'manual_length_cm': float(length_cm),
            'manual_height_cm': float(height_cm),
            'manual_width_cm': float(width_cm),
            'manual_weight_g': float(weight_g),
            
            # IA
            'lat_area_cm2': float(ai_lat_area),
            'top_area_cm2': float(ai_top_area),
            'volume_cm3': float(ai_vol),
            
            'confidence_score': 1.0,
            'measurement_type': 'manual', 
            'notes': str(notes),
            'image_path': str(filepath),
            'validation_errors': '',
            
            # API (Nulos explícitos)
            'api_air_temp_c': None, 'api_water_temp_c': None, 'api_ph': None,
            'api_rel_humidity': None, 'api_abs_humidity_g_m3': None, 
            'api_cond_us_cm': None, 'api_do_mg_l': None
        }
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PASO 5: GUARDAR EN BD
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        try:
            m_id = self.db.save_measurement(data)
            
            self.status_bar.set_status(f"✅ Registro Manual #{m_id} guardado", "success")
            
            # Éxito y Limpieza
            QMessageBox.information(self, "Guardado", f"Medición #{m_id} guardada con éxito.")
            self.discard_manual_photo()
            self.refresh_history()
            self.generate_daily_id()
            self.refresh_daily_counter()
            
                
        except Exception as e:
            logger.error(f"Error BD: {e}")
            self.status_bar.set_status("❌ Error de Base de Datos", "error")
            QMessageBox.critical(self, "Error Base de Datos", f"No se pudo registrar en la BD:\n{e}")
            # Intentar borrar la imagen huérfana
            if os.path.exists(filepath): os.remove(filepath)
 
    def _save_measurement_silent(self):
        """
        Versión silenciosa de guardado BLINDADA y con DIBUJO DE CONTORNOS ORIGINAL.
        """
        # Validación inicial
        if not self.last_result or not self.last_metrics:
            return False
        
        try:
            metrics = self.last_metrics
            timestamp = datetime.now()
            
            # --- 1. EXTRACCIÓN SEGURA (BLINDAJE) ---
            # Usamos float() para asegurar que la BD reciba números, no texto
            length_cm = float(metrics.get('length_cm', 0))
            height_cm = float(metrics.get('height_cm', 0))
            width_cm = float(metrics.get('width_cm', 0))
            weight_g = float(metrics.get('weight_g', 0))
            
            # Áreas y volumen
            lat_area = float(metrics.get('lat_area_cm2', 0))
            top_area = float(metrics.get('top_area_cm2', 0))
            vol = float(metrics.get('volume_cm3', 0))
            
            # Calculamos Factor K para la imagen
            factor_k = float(metrics.get('condition_factor', 0))
            confidence = float(self.last_result.get('confidence', 0))

            # --- 2. PREPARAR IMAGEN ---
            # Generar nombre de archivo único
            filename = f"AUTO_{timestamp.strftime('%Y%m%d_%H%M%S')}_L{length_cm:.1f}.jpg"
            filepath = os.path.join(Config.IMAGES_AUTO_DIR, filename)
            os.makedirs(Config.IMAGES_AUTO_DIR, exist_ok=True)
            
            # Copiar frames originales
            frame_left = self.last_result['frame_left'].copy()
            frame_top = self.last_result['frame_top'].copy()
            
            # --- 3. DIBUJAR CONTORNOS (TU CÓDIGO ORIGINAL RESTAURADO) ---
            contour_left = self.last_result.get('contour_left')
            contour_top = self.last_result.get('contour_top')
            
            # Dibujo Vista Lateral
            if contour_left is not None and isinstance(contour_left, np.ndarray) and len(contour_left) >= 3:
                cv2.drawContours(frame_left, [contour_left], -1, (0, 255, 0), 3)
                x, y, w, h = cv2.boundingRect(contour_left)
                cv2.rectangle(frame_left, (x, y), (x+w, y+h), (0, 255, 255), 2)
            
            # Dibujo Vista Cenital
            if contour_top is not None and isinstance(contour_top, np.ndarray) and len(contour_top) >= 3:
                cv2.drawContours(frame_top, [contour_top], -1, (0, 255, 0), 3)
                x, y, w, h = cv2.boundingRect(contour_top)
                cv2.rectangle(frame_top, (x, y), (x+w, y+h), (0, 255, 255), 2)
            
            # Combinar imágenes
            combined = np.hstack((
                cv2.resize(frame_left, (Config.SAVE_WIDTH, Config.SAVE_HEIGHT)),
                cv2.resize(frame_top, (Config.SAVE_WIDTH, Config.SAVE_HEIGHT))
            ))
            
            # --- 4. DIBUJAR TEXTOS EN LA IMAGEN ---
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(combined, f"AUTO-CAPTURA", (10, 30), font, 0.9, (0, 255, 255), 2)
            cv2.putText(combined, f"Longitud: {length_cm:.2f} cm", (10, 65), font, 0.8, (0, 255, 0), 2)
            cv2.putText(combined, f"Altura: {height_cm:.2f} cm", (10, 100), font, 0.8, (0, 255, 0), 2) # Corregí posición Y para que no se superponga
            cv2.putText(combined, f"Ancho: {width_cm:.2f} cm", (10, 135), font, 0.8, (0, 255, 0), 2)
            cv2.putText(combined, f"Peso: {weight_g:.1f} g", (10, 170), font, 0.8, (0, 255, 0), 2)
            cv2.putText(combined, f"K: {factor_k:.2f} | Conf: {confidence:.0%}", (10, 205), font, 0.8, (0, 255, 0), 2)
            cv2.putText(combined, timestamp.strftime('%Y-%m-%d %H:%M:%S'), (10, 240), font, 0.7, (180, 180, 180), 2)
            
            # Guardar en disco
            cv2.imwrite(filepath, combined)
            
            # --- 5. PREPARAR DICCIONARIO BASE DE DATOS (ESTRUCTURA CORRECTA) ---
            try:
                count_today = self.db.get_today_measurements_count()
                fish_id = f"AUTO_{str(count_today + 1)  }"
                logger.info(f"Using daily counter for fish_id: {fish_id}")
            except:
                fish_id = f"AUTO_{timestamp.strftime('%Y%m%d_%H%M%S')}"
                logger.warning(f"Daily counter failed, using timestamp: {fish_id}")
            
            data = {
                'timestamp': timestamp.isoformat(),
                'fish_id': str(fish_id),
                
                # Datos principales (Floats)
                'length_cm': length_cm,
                'height_cm': height_cm,   
                'width_cm': width_cm,
                'weight_g': weight_g,
                
                # Datos Manuales (En auto se ponen en 0.0 para que la BD no falle)
                'manual_length_cm': 0.0,
                'manual_height_cm': 0.0,
                'manual_width_cm': 0.0,
                'manual_weight_g': 0.0,
                
                # Datos Avanzados
                'lat_area_cm2': lat_area,
                'top_area_cm2': top_area,
                'volume_cm3': vol,
                
                'confidence_score': confidence,
                'image_path': str(filepath),
                'measurement_type': 'auto',
                'notes': '[Medición Automática]',
                'validation_errors': '',
                
                # Datos API (Nulos explícitos)
                'api_air_temp_c': None,
                'api_water_temp_c': None,
                'api_rel_humidity': None,
                'api_abs_humidity_g_m3': None,
                'api_ph': None,
                'api_cond_us_cm': None,
                'api_do_mg_l': None
            }
            
            # --- 6. GUARDAR Y ACTUALIZAR ---
            measurement_id = self.db.save_measurement(data)
            
            self.btn_save.setEnabled(False)
            
            # Actualizar interfaz sin bloquear
            QTimer.singleShot(100, self.refresh_history)
            QTimer.singleShot(100, self.refresh_daily_counter)
            
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"✅ Auto-Guardado #{measurement_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error silent save: {e}")
            return False
        
    def generate_daily_id(self):
        """Genera un ID consecutivo basado en la fecha de hoy (Lógica Optimizada)"""
        try:
            db = getattr(self, 'db_manager', getattr(self, 'db', None))
            
            if db:
                next_id = db.get_next_fish_number()
            else:
                next_id = 1

            if hasattr(self, 'txt_manual_fish_id'):
                self.txt_manual_fish_id.setText(str(next_id))

                self.txt_manual_fish_id.setProperty("state", "info")
                self.txt_manual_fish_id.style().unpolish(self.txt_manual_fish_id)
                self.txt_manual_fish_id.style().polish(self.txt_manual_fish_id)

                QTimer.singleShot(2000, lambda: self._reset_widget_state(self.txt_manual_fish_id))
                
        except Exception as e:
            logger.error(f"Error generando ID diario: {e}.")
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status("⚠️ Error al auto-generar ID", "warning")

    def _reset_widget_state(self, widget):
        """Helper para limpiar estados visuales temporales"""
        if widget and widget.property("state") != "":
            widget.setProperty("state", "")
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def create_history_tab(self):
        """Crea la pestaña de historial con Búsqueda, Filtros y Tooltips Profesionales"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. BARRA DE ACCIONES SUPERIOR (CRUD)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        top_controls = QHBoxLayout()
        
        # Título de Sección
        lbl_title = QLabel("Gestión de Registros")
        lbl_title.setProperty("class", "header-text")
        top_controls.addWidget(lbl_title)
        
        top_controls.addStretch()
        
        # --- Botón Recargar ---
        btn_refresh = QPushButton("Recargar")
        btn_refresh.setProperty("class", "secondary")
        btn_refresh.style().unpolish(btn_refresh)
        btn_refresh.style().polish(btn_refresh)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setToolTip("Recarga la tabla con la información más reciente")
        btn_refresh.clicked.connect(self.refresh_history)
        top_controls.addWidget(btn_refresh)

        # --- Botón Editar ---
        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("class", "info")
        btn_edit.style().unpolish(btn_edit)
        btn_edit.style().polish(btn_edit)
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setToolTip("Abre un editor para cambiar notas o corregir<br>"
                                "datos de la fila seleccionada.")
        btn_edit.clicked.connect(self.edit_selected_measurement)
        top_controls.addWidget(btn_edit)
        
        # --- Botón Eliminar ---
        btn_delete = QPushButton("Eliminar")
        btn_delete.setProperty("class", "warning")
        btn_delete.style().unpolish(btn_delete)
        btn_delete.style().polish(btn_delete)
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.setToolTip("Elimina permanentemente la medición seleccionada<br>"
                                "y su imagen asociada.")
        btn_delete.clicked.connect(self.delete_selected_measurement)
        top_controls.addWidget(btn_delete)
        
        layout.addLayout(top_controls)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. PANEL DE BÚSQUEDA AVANZADA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        filter_group = QGroupBox("Filtros de Búsqueda")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setSpacing(10)

        # --- Fila 1: Búsqueda de Texto y Tipo ---
        
        # Buscador
        filter_layout.addWidget(QLabel("Texto (ID, Pez, Notas):"), 0, 0)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Ej: pez_05, error, 123...")
        self.txt_search.setClearButtonEnabled(True) 
        self.txt_search.setToolTip(
            "Escribe el ID del pez, el número de registro<br>"
            "o palabras clave contenidas en las notas."
        )
        self.txt_search.returnPressed.connect(self.reset_pagination_and_refresh) 
        filter_layout.addWidget(self.txt_search, 0, 1)

        # Tipo
        filter_layout.addWidget(QLabel("Tipo de Medición:"), 0, 2)
        self.combo_filter_type = QComboBox()
        self.combo_filter_type.setCursor(Qt.PointingHandCursor)
        self.combo_filter_type.addItems(["Todos", "auto", "manual", "ia_refined","manual_qr","manual_externo_pc"]) 
        self.combo_filter_type.setToolTip(
            "<b>Filtrar por Origen de Medición</b><br><br>"
            "⚙️ <b>Automática</b>: Generada por el sistema.<br>"
            "✋ <b>Manual</b>: Ingresada directamente.<br>"
            "📱 <b>Manual (QR)</b>: Enviada desde celular.<br>"
            "💻 <b>Manual (PC)</b>: Importada desde el equipo.<br>"
            "🧠 <b>IA Refinada</b>: Ajustada por algoritmo."
        )
        self.combo_filter_type.currentTextChanged.connect(self.reset_pagination_and_refresh)
        filter_layout.addWidget(self.combo_filter_type, 0, 3)

        # --- Fila 2: Fechas y Botones ---
        
        # Fecha Desde
        filter_layout.addWidget(QLabel("Desde:"), 1, 0)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        self.date_from.setDate(QDate.currentDate().addDays(-90)) 
        self.date_from.setToolTip("Fecha inicial del rango de búsqueda.")
        filter_layout.addWidget(self.date_from, 1, 1)

        # Fecha Hasta
        filter_layout.addWidget(QLabel("Hasta:"), 1, 2)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        self.date_to.setDate(QDate.currentDate()) 
        self.date_to.setToolTip("Fecha final del rango de búsqueda (inclusive).")
        filter_layout.addWidget(self.date_to, 1, 3)
        
        # Botones de Filtro
        btn_container = QHBoxLayout()
        
        btn_search = QPushButton("Buscar")
        btn_search.setProperty("class", "primary")
        btn_search.style().unpolish(btn_search)
        btn_search.style().polish(btn_search)
        btn_search.setCursor(Qt.PointingHandCursor)
        btn_search.setToolTip("Aplica los filtros de texto, tipo y fecha seleccionados.")
        btn_search.clicked.connect(self.reset_pagination_and_refresh)
        btn_container.addWidget(btn_search)
        btn_search.style().unpolish(btn_search)
        btn_search.style().polish(btn_search)

        btn_clear = QPushButton("Limpiar")
        btn_clear.setProperty("class", "secondary")
        btn_clear.style().unpolish(btn_clear)
        btn_clear.style().polish(btn_clear)
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setToolTip("Reinicia todos los filtros a su estado original.")
        btn_clear.clicked.connect(self.clear_filters) 
        btn_container.addWidget(btn_clear)
        
        filter_layout.addLayout(btn_container, 1, 4)

        layout.addWidget(filter_group)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. TABLA PROFESIONAL
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        self.table_history = QTableWidget()
        self.table_history.setColumnCount(11)
        self.table_history.setHorizontalHeaderLabels([
            "ID", "Fecha/Hora", "Tipo", "Pez ID", "Largo (cm)", 
            "Alto (cm)", "Ancho (cm)", "Peso (g)", "Factor K", "Confianza", "Notas"
        ])
        
        # Ajustes de Tabla
        self.table_history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive) 
        self.table_history.horizontalHeader().setStretchLastSection(True)
        self.table_history.setAlternatingRowColors(True)
        self.table_history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_history.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_history.verticalHeader().setVisible(False)
        self.table_history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table_history.setToolTip("💡 <b>Tip:</b> Haz <b>doble clic</b> en una fila para ver la foto de la medición.")
        
        self.table_history.cellDoubleClicked.connect(self.view_measurement_image)
        layout.addWidget(self.table_history)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. BARRA DE PAGINACIÓN (ABAJO)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        pagination_layout = QHBoxLayout()
        
        self.lbl_total_records = QLabel("Total: 0 registros")
        self.lbl_total_records.setStyleSheet("color: gray; font-style: italic;")
        pagination_layout.addWidget(self.lbl_total_records)
        
        pagination_layout.addStretch()
        
        pagination_layout.addWidget(QLabel("Mostrar:"))
        self.combo_limit = QComboBox()
        self.combo_limit.setCursor(Qt.PointingHandCursor)
        self.combo_limit.addItems(["25", "50", "100", "500"])
        self.combo_limit.setToolTip("Cantidad de filas a mostrar por página.")
        self.combo_limit.currentTextChanged.connect(self.reset_pagination_and_refresh)
        pagination_layout.addWidget(self.combo_limit)
        
        pagination_layout.addSpacing(20)

        # --- BOTÓN ANTERIOR (CON ICONO NATIVO) ---
        self.btn_prev_page = QPushButton() 
        self.btn_prev_page.setFixedSize(30, 30)
        self.btn_prev_page.setProperty("class", "secondary")
        self.btn_prev_page.style().unpolish(self.btn_prev_page)
        self.btn_prev_page.style().polish(self.btn_prev_page)
        self.btn_prev_page.setCursor(Qt.PointingHandCursor)
        self.btn_prev_page.setToolTip("Ir a la página anterior.")
        icon_left = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft)
        self.btn_prev_page.setIcon(icon_left)
        
        self.btn_prev_page.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.btn_prev_page)

        # --- INFORMACIÓN DE PÁGINA ---
        self.lbl_page_info = QLabel("1")
        self.lbl_page_info.setAlignment(Qt.AlignCenter)
        self.lbl_page_info.setFixedWidth(30)
        self.lbl_page_info.setProperty("class", "report-text")
        pagination_layout.addWidget(self.lbl_page_info)

        # --- BOTÓN SIGUIENTE (CON ICONO NATIVO) ---
        self.btn_next_page = QPushButton() 
        self.btn_next_page.setFixedSize(30, 30)
        self.btn_next_page.setProperty("class", "secondary")
        self.btn_next_page.style().unpolish(self.btn_next_page)
        self.btn_next_page.style().polish(self.btn_next_page)
        self.btn_next_page.setCursor(Qt.PointingHandCursor)
        self.btn_next_page.setToolTip("Ir a la página siguiente.")
        icon_right = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight)
        self.btn_next_page.setIcon(icon_right)
        
        self.btn_next_page.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.btn_next_page)

        layout.addLayout(pagination_layout)
        
        # Inicializar
        self.current_page = 1
        self.refresh_history()
        
        return widget

    def clear_filters(self):
        """Resetea los filtros y limpia la búsqueda visualmente"""
        self.txt_search.clear()
        self.combo_filter_type.setCurrentIndex(0) 
        
        self.date_from.setDate(QDate.currentDate().addDays(-90))
        self.date_to.setDate(QDate.currentDate())

        if hasattr(self, 'status_bar'):
            self.status_bar.set_status("🧹 Filtros reiniciados", "info")
            
        self.reset_pagination_and_refresh()

    def reset_pagination_and_refresh(self):
        """Reinicia el puntero y refresca toda la data relacionada"""
        self.current_page_offset = 0
        self.refresh_history()
        self.refresh_daily_counter()
        self.sender().clearFocus()

    def next_page(self):
        """Avanza de página basado en el límite seleccionado"""
        limit = int(self.combo_limit.currentText())
        self.current_page_offset += limit
        self.refresh_history()

    def prev_page(self):
        """Retrocede de página asegurando no llegar a números negativos"""
        limit = int(self.combo_limit.currentText())
        if self.current_page_offset >= limit:
            self.current_page_offset -= limit
            self.refresh_history()
        else:
            self.current_page_offset = 0 # 
    
    def refresh_history(self):

        if not hasattr(self, 'db'): return
        
        if not hasattr(self, 'current_page_offset'):
            self.current_page_offset = 0


        search_text = self.txt_search.text().strip()
        
        filter_type = self.combo_filter_type.currentText()
        if filter_type == "Todos": filter_type = None
        elif filter_type == "Automáticas": filter_type = "auto"
        elif filter_type == "Manuales": filter_type = "manual"
        
        date_start = self.date_from.date().toString("yyyy-MM-dd")
        date_end = self.date_to.date().toString("yyyy-MM-dd")
        
        try:
            limit = int(self.combo_limit.currentText())
        except:
            limit = 25

        # 2. Obtener datos (Vienen en el orden de MEASUREMENT_COLUMNS)
        measurements = self.db.get_filtered_measurements(
            limit=limit, 
            offset=self.current_page_offset,
            search_query=search_text,
            filter_type=filter_type,
            date_start=date_start,
            date_end=date_end
        )
        
        self.table_history.setRowCount(0)
        
        if not measurements:
            self.lbl_total_records.setText("No se encontraron registros.")
            self.lbl_page_info.setText("0")
            return

        self.table_history.setRowCount(len(measurements))
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # MAPA DE INDICES (Basado estrictamente en tu DatabaseManager.py)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 0:id, 1:timestamp, 2:fish_id, 3:length_cm, 4:height_cm, 5:width_cm, 6:weight_g
        # 7:manual_length, 8:manual_height, 9:manual_width, 10:manual_weight
        # 14:confidence, 15:notes, 16:image_path, 17:measurement_type
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        for row, m in enumerate(measurements):
            
            # --- FUNCIÓN SEGURA INTERNA ---
            def get_safe(idx, default=""):
                try:
                    val = m[idx]
                    return val if val is not None else default
                except IndexError:
                    return default

            # 1. ID (Columna 0) -> Index 0
            val_id = get_safe(0, 0)
            self.table_history.setItem(row, 0, QTableWidgetItem(str(val_id)))
            
            # 2. FECHA (Columna 1) -> Index 1
            ts_str = str(get_safe(1, ""))
            try:
                # Cortar microsegundos si existen para que se vea limpio
                if "." in ts_str: ts_str = ts_str.split(".")[0] 
                ts_obj = datetime.fromisoformat(ts_str)
                ts_nice = ts_obj.strftime('%d/%m/%Y %H:%M')
            except:
                ts_nice = ts_str
            self.table_history.setItem(row, 1, QTableWidgetItem(ts_nice))
            
            # 3. TIPO (Columna 2) -> Index 17 (¡AQUÍ ESTABA EL ERROR!)
            val_type = str(get_safe(17, "auto")).upper()
            item_type = QTableWidgetItem(val_type)
            
            # Colores
            if "MANUAL" in val_type:
                item_type.setBackground(QColor("#fff3cd")) # Amarillo
                item_type.setForeground(QColor("#856404"))
            elif "IA" in val_type:
                item_type.setBackground(QColor("#d4edda")) # Verde
                item_type.setForeground(QColor("#155724"))
            else:
                item_type.setBackground(QColor("#e7f1ff")) # Azul
            
            self.table_history.setItem(row, 2, item_type)
            
            # 4. PEZ ID (Columna 3) -> Index 2
            val_fish = str(get_safe(2, "-"))
            self.table_history.setItem(row, 3, QTableWidgetItem(val_fish))
            
            # --- VALORES NUMÉRICOS ---
            def format_num(idx, decimals=2):
                try:
                    val = float(get_safe(idx, 0))
                    return f"{val:.{decimals}f}"
                except: return "0.00"

            # 5. LARGO (Columna 4) -> Index 3 (length_cm)
            self.table_history.setItem(row, 4, QTableWidgetItem(format_num(3)))
            
            # 6. ALTO (Columna 5) -> Index 8 (manual_height) o Index 4 (height_cm)
            # Priorizamos manual si existe (>0), si no usamos el de IA
            h_manual = float(get_safe(8, 0))
            h_ia = float(get_safe(4, 0))
            val_h = h_manual if h_manual > 0 else h_ia
            self.table_history.setItem(row, 5, QTableWidgetItem(f"{val_h:.2f}"))
            
            # 7. ANCHO (Columna 6) -> Index 9 (manual_width) o Index 5 (width_cm)
            w_manual = float(get_safe(9, 0))
            w_ia = float(get_safe(5, 0))
            val_w = w_manual if w_manual > 0 else w_ia
            self.table_history.setItem(row, 6, QTableWidgetItem(f"{val_w:.2f}"))
            
            # 8. PESO (Columna 7) -> Index 6 (weight_g)
            # Nota: Si usas peso manual está en index 10, pero usualmente mostramos el principal
            weight_val = float(get_safe(6, 0))
            self.table_history.setItem(row, 7, QTableWidgetItem(f"{weight_val:.2f}"))
            
            # 9. FACTOR K (Columna 8) -> Calculado
            l_val = float(get_safe(3, 0)) # Usamos largo IA para estandarizar
            if l_val > 0 and weight_val > 0:
                k = (100 * weight_val) / (l_val ** 3)
                k_str = f"{k:.3f}"
            else:
                k_str = "-"
            self.table_history.setItem(row, 8, QTableWidgetItem(k_str))
            
            # 10. CONFIANZA (Columna 9) -> Index 14
            conf = float(get_safe(14, 0))
            item_conf = QTableWidgetItem(f"{conf:.0%}")
            if conf < 0.85 and conf > 0:
                item_conf.setForeground(QColor("red"))
                item_conf.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table_history.setItem(row, 9, item_conf)
            
            # 11. NOTAS (Columna 10) -> Index 15
            val_notes = str(get_safe(15, ""))
            self.table_history.setItem(row, 10, QTableWidgetItem(val_notes))

        # 3. Paginación UI
        limit = int(self.combo_limit.currentText())
        current_page = (self.current_page_offset // limit) + 1
        self.lbl_page_info.setText(str(current_page))
        
        count_shown = len(measurements)
        self.lbl_total_records.setText(f"Mostrando {count_shown} registros")
        
        self.btn_prev_page.setEnabled(self.current_page_offset > 0)
        self.btn_next_page.setEnabled(count_shown == limit)
        
        if hasattr(self, 'refresh_daily_counter'):
            self.refresh_daily_counter()
  
    def create_statistics_tab(self):
        """Crea la pestaña de estadísticas """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        controls = QHBoxLayout()

        btn_generate_stats = QPushButton("Generar Estadísticas")
        btn_generate_stats.setProperty("class", "primary")  
        btn_generate_stats.style().unpolish(btn_generate_stats)
        btn_generate_stats.style().polish(btn_generate_stats)
        btn_generate_stats.setCursor(Qt.PointingHandCursor)
        btn_generate_stats.setToolTip(
            "Analiza las mediciones de la base de datos, calcula promedios<br>"
            "y genera los gráficos visuales en la galería."
        )
        btn_generate_stats.clicked.connect(self.generate_statistics)
        controls.addWidget(btn_generate_stats)
        
        controls.addStretch()
        layout.addLayout(controls)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- LADO IZQUIERDO: GALERÍA ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0,0,0,0)
        
        lbl_gallery = QLabel("Explorador de Gráficos")
        lbl_gallery.setProperty("class", "header-text") 
        left_layout.addWidget(lbl_gallery)
        
        self.gallery_list = QListWidget()
        self.gallery_list.setProperty("class", "gallery-list")
        self.gallery_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery_list.setIconSize(QSize(220, 160))
        self.gallery_list.setSpacing(10) 
        self.gallery_list.itemDoubleClicked.connect(self.open_enlarged_graph)
        left_layout.addWidget(self.gallery_list)
        
        # --- LADO DERECHO: REPORTE TEXTUAL ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0,0,0,0)
        
        lbl_report = QLabel("Reporte Detallado")
        lbl_report.setProperty("class", "header-text")
        right_layout.addWidget(lbl_report)
        
        self.stats_text = QTextEdit()
        self.stats_text.setProperty("class", "report-text")
        self.stats_text.setReadOnly(True)
        right_layout.addWidget(self.stats_text)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(right_container)
        self.splitter.setStretchFactor(0, 6) 
        self.splitter.setStretchFactor(1, 4) 
        layout.addWidget(self.splitter)
        
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 5, 0, 0) 
        
        grp_graphs = QGroupBox("Exportar Gráfico Individual")
        grid_graphs = QGridLayout(grp_graphs)
        grid_graphs.setSpacing(8)
        
        buttons_config = [
            ("📏 Longitudes", 'length', 
             "<b>HISTOGRAMA DE TALLAS:</b><br>Exporta la distribución de frecuencias<br>de las longitudes detectadas.", 0, 0),
             
            ("⚖️ Pesos", 'weight', 
             "<b>DISTRIBUCIÓN DE PESO:</b><br>Exporta el histograma de biomasa<br>estimada de la población.", 0, 1),
             
            ("📈 Correlación", 'correlation', 
             "<b>RELACIÓN L/P:</b><br>Gráfico de dispersión que muestra la<br>salud del crecimiento (Largo vs Peso).", 0, 2),
             
            ("⏱ Evolución", 'timeline', 
             "<b>CRECIMIENTO TEMPORAL:</b><br>Muestra la tendencia de crecimiento<br>a lo largo de las fechas de muestreo.", 1, 0),
             
            ("↕️ Alturas", 'height', 
             "<b>MORFOMETRÍA (H):</b><br>Distribución de las alturas corporales.", 1, 1),
             
            ("↔️ Anchos", 'width', 
             "<b>MORFOMETRÍA (W):</b><br>Distribución del grosor de los peces.", 1, 2),
        ]

        for text, key, tip, r, c in buttons_config:
            btn = QPushButton(text)
            btn.setProperty("class", "secondary")
            btn.setCursor(Qt.PointingHandCursor)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked, x=key: self.export_individual_graph(x))
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred) 
            grid_graphs.addWidget(btn, r, c)

        bottom_layout.addWidget(grp_graphs, stretch=7) 

        grp_tools = QGroupBox("Datos y Sistema")
        tools_layout = QVBoxLayout(grp_tools)
        tools_layout.setSpacing(8)
        
        # Botón CSV
        btn_csv = QPushButton("Exportar CSV (Excel)")
        btn_csv.setProperty("class", "success") 
        btn_csv.style().unpolish(btn_csv)
        btn_csv.style().polish(btn_csv)
        btn_csv.setCursor(Qt.PointingHandCursor)
        btn_csv.setToolTip(
            "Descarga todas las mediciones en formato .CSV"
        )
        btn_csv.clicked.connect(self.export_to_csv)
        tools_layout.addWidget(btn_csv)
        
        btn_export_stats = QPushButton("Exportar Gráficos (PNG)")
        btn_export_stats.setProperty("class", "success") 
        btn_export_stats.style().unpolish(btn_export_stats) 
        btn_export_stats.style().polish(btn_export_stats)  
        btn_export_stats.setCursor(Qt.PointingHandCursor)
        btn_export_stats.setToolTip(
            "Guarda los gráficos actuales como archivos de imagen (PNG)."
        )
        btn_export_stats.clicked.connect(self.export_statistics)
        tools_layout.addWidget(btn_export_stats)

        btn_export_pdf = QPushButton("Reporte PDF")
        btn_export_pdf.setProperty("class", "success") 
        btn_export_pdf.style().unpolish(btn_export_pdf) 
        btn_export_pdf.style().polish(btn_export_pdf)       
        btn_export_pdf.setCursor(Qt.PointingHandCursor)
        btn_export_pdf.setToolTip(
            "Genera un documento PDF formal que incluye:<br>"
            "• Tabla de resumen de datos.<br>"
            "• Todos los gráficos generados visualmente."
        )
        btn_export_pdf.clicked.connect(self.export_stats_pdf)  
        tools_layout.addWidget(btn_export_pdf)
        
        # Botón Abrir Carpeta
        btn_folder = QPushButton("Abrir Carpeta de Resultados")
        btn_folder.setProperty("class", "info")
        btn_folder.style().unpolish(btn_folder) 
        btn_folder.style().polish(btn_folder)
        btn_folder.setCursor(Qt.PointingHandCursor)
        btn_folder.setToolTip(
            "Abre el explorador de Windows en la carpeta<br>"
            "donde se guardan los gráficos y reportes."
        )
        btn_folder.clicked.connect(self.open_output_folder) 
        tools_layout.addWidget(btn_folder)
        
        bottom_layout.addWidget(grp_tools, stretch=3)
        
        layout.addWidget(bottom_widget)
        
        return widget
    
    def open_output_folder(self):
        """Abre la carpeta de resultados en el explorador del sistema"""
        import platform
        import subprocess
        
        path = os.path.abspath(Config.OUT_DIR)
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                self.status_bar.set_status("❌ Error al crear carpeta de salida", "error")
                return

        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin": 
                subprocess.Popen(["open", path])
            else:  
                subprocess.Popen(["xdg-open", path])
            
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"📂 Carpeta abierta: {os.path.basename(path)}", "info")
                
        except Exception as e:
            logger.error(f"Error abriendo carpeta de salida: {e}.")
            QMessageBox.warning(self, "Error", f"No se pudo abrir la carpeta:\n{str(e)}")
    
    def add_graph_to_gallery(self, figure, title):
        """
        Convierte una figura de Matplotlib en un icono de alta calidad y lo añade al explorador.
        Optimizado para evitar pixelado en la miniatura.
        """
        canvas = FigureCanvas(figure)
        canvas.draw()
        
        width, height = canvas.get_width_height()
        image = QImage(canvas.buffer_rgba(), width, height, QImage.Format.Format_RGBA8888)
        pixmap = QPixmap.fromImage(image)

        thumb_size = self.gallery_list.iconSize()
        thumbnail = pixmap.scaled(
            thumb_size, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        item = QListWidgetItem(QIcon(thumbnail), title)

        item.setData(Qt.ItemDataRole.UserRole, pixmap)

        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.gallery_list.addItem(item)

    def open_enlarged_graph(self, item):
        """Abre una ventana modal con la imagen en alta resolución"""
        pixmap = item.data(Qt.ItemDataRole.UserRole)
        title = item.text()
        
        if not pixmap or pixmap.isNull():
            self.status_bar.set_status("❌ Error al recuperar el gráfico", "error")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Visualización Detallada: {title}")
        dialog.setMinimumSize(900, 650) 
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        lbl_image = QLabel()

        lbl_image.setPixmap(pixmap.scaled(
            dialog.size() * 0.95, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        ))
        lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        scroll_area.setWidget(lbl_image)
        layout.addWidget(scroll_area)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_close = QPushButton("Cerrar")
        btn_close.setProperty("class", "secondary")
        btn_close.setFixedWidth(120)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
 
        if hasattr(self, 'status_bar'):
            self.status_bar.set_status(f"👁️ Visualizando: {title}", "info")
        
        dialog.exec()

    def export_individual_graph(self, graph_type):
        """
        Exporta gráficos individuales - SIEMPRE EN MODO CLARO (Fondo Blanco)
        Ideal para reportes y documentos.
        """
        measurements = self.db.get_filtered_measurements(limit=2000)
        
        if not measurements:
            QMessageBox.warning(self, "Advertencia", "No hay mediciones para exportar")
            return
        
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import numpy as np
            from datetime import datetime
            import os
            import sqlite3
            from BasedeDatos.DatabaseManager import MEASUREMENT_COLUMNS
            
            # --- RESET TOTAL DE ESTILOS ---
            plt.close('all')
            plt.rcParams.update(plt.rcParamsDefault) # Restablece todo a valores de fábrica
            plt.style.use('default')                 # Fuerza el estilo por defecto (blanco)
            
            # Colores forzados para reporte
            TEXT_COLOR = 'black'
            GRID_COLOR = '#cccccc'
            BG_COLOR = 'white'
            
            # --- DETECCIÓN DE COLUMNAS ---
            columns_info = {col: i for i, col in enumerate(MEASUREMENT_COLUMNS)}
            
            def get_val(m, field, default=0.0):
                if field in columns_info:
                    idx = columns_info[field]
                    if idx < len(m):
                        val = m[idx]
                        if val is None or val == "": return default
                        try: return float(val)
                        except: return default
                return default
            
            def get_str(m, field):
                if field in columns_info:
                    idx = columns_info[field]
                    if idx < len(m):
                        return str(m[idx]) if m[idx] is not None else ""
                return ""

            # Crear figura con fondo blanco explícito
            fig, ax = plt.subplots(figsize=(10, 6), dpi=100)
            fig.patch.set_facecolor(BG_COLOR)
            ax.set_facecolor(BG_COLOR)
            
            filename = ""
            has_data = False
            
            # 1. LONGITUDES
            if graph_type == 'length':
                data = [get_val(m, 'length_cm') for m in measurements if get_val(m, 'length_cm') > 0]
                if data:
                    ax.hist(data, bins=20, color='#3498db', alpha=0.8, edgecolor='black')
                    ax.set_title('Distribución de Longitudes (cm)', color=TEXT_COLOR, fontweight='bold')
                    ax.set_xlabel('Longitud (cm)', color=TEXT_COLOR)
                    ax.axvline(np.mean(data), color='red', linestyle='--', label=f'Promedio: {np.mean(data):.2f}')
                    filename = f'longitudes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    has_data = True

            # 2. PESOS
            elif graph_type == 'weight':
                data = [get_val(m, 'weight_g') for m in measurements if get_val(m, 'weight_g') > 0]
                if data:
                    ax.hist(data, bins=20, color='#e67e22', alpha=0.8, edgecolor='black')
                    ax.set_title('Distribución de Pesos (g)', color=TEXT_COLOR, fontweight='bold')
                    ax.set_xlabel('Peso (g)', color=TEXT_COLOR)
                    ax.axvline(np.mean(data), color='red', linestyle='--', label=f'Promedio: {np.mean(data):.2f}')
                    filename = f'pesos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    has_data = True

            # 3. ALTURAS
            elif graph_type == 'height':
                data = []
                for m in measurements:
                    v = get_val(m, 'manual_height_cm')
                    if v <= 0: v = get_val(m, 'height_cm')
                    if v > 0: data.append(v)
                if data:
                    ax.hist(data, bins=15, color='#1abc9c', alpha=0.8, edgecolor='black')
                    ax.set_title('Distribución de Alturas (cm)', color=TEXT_COLOR, fontweight='bold')
                    ax.set_xlabel('Altura (cm)', color=TEXT_COLOR)
                    ax.axvline(np.mean(data), color='red', linestyle='--', label=f'Promedio: {np.mean(data):.2f}')
                    filename = f'alturas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    has_data = True

            # 4. ANCHOS
            elif graph_type == 'width':
                data = []
                for m in measurements:
                    v = get_val(m, 'manual_width_cm')
                    if v <= 0: v = get_val(m, 'width_cm')
                    if v > 0: data.append(v)
                if data:
                    ax.hist(data, bins=15, color='#9b59b6', alpha=0.8, edgecolor='black')
                    ax.set_title('Distribución de Anchos (cm)', color=TEXT_COLOR, fontweight='bold')
                    ax.set_xlabel('Ancho (cm)', color=TEXT_COLOR)
                    ax.axvline(np.mean(data), color='red', linestyle='--', label=f'Promedio: {np.mean(data):.2f}')
                    filename = f'anchos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    has_data = True

            # 5. CORRELACIÓN
            elif graph_type == 'correlation':
                l_list, w_list = [], []
                for m in measurements:
                    l = get_val(m, 'length_cm')
                    w = get_val(m, 'weight_g')
                    if l > 0 and w > 0:
                        l_list.append(l); w_list.append(w)
                if len(l_list) > 2:
                    ax.scatter(l_list, w_list, color='#2980b9', alpha=0.6, edgecolors='black')
                    try:
                        z = np.polyfit(l_list, w_list, 3)
                        p = np.poly1d(z)
                        xp = np.linspace(min(l_list), max(l_list), 100)
                        ax.plot(xp, p(xp), color='#c0392b', linewidth=2, label='Tendencia')
                    except: pass
                    ax.set_title('Relación Longitud vs Peso', color=TEXT_COLOR, fontweight='bold')
                    ax.set_xlabel('Longitud (cm)', color=TEXT_COLOR)
                    ax.set_ylabel('Peso (g)', color=TEXT_COLOR)
                    filename = f'correlacion_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    has_data = True

            # 6. TIMELINE (PROMEDIO DIARIO)
            elif graph_type == 'timeline':
                daily = {}
                for m in measurements:
                    l = get_val(m, 'length_cm')
                    ts = get_str(m, 'timestamp')
                    if l > 0 and ts:
                        try:
                            day = datetime.fromisoformat(ts).date()
                            if day not in daily: daily[day] = []
                            daily[day].append(l)
                        except: pass
                
                if daily:
                    d_sorted = sorted(daily.keys())
                    avgs = [np.mean(daily[d]) for d in d_sorted]
                    ax.plot(d_sorted, avgs, 'o-', color='#2c3e50', linewidth=2, label='Promedio Diario')
                    ax.fill_between(d_sorted, avgs, alpha=0.1, color='#2c3e50')
                    ax.set_title('Crecimiento Promedio Diario', color=TEXT_COLOR, fontweight='bold')
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)
                    filename = f'timeline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    has_data = True

            # --- CONFIGURACIÓN FINAL DE EJES ---
            ax.tick_params(axis='x', colors=TEXT_COLOR)
            ax.tick_params(axis='y', colors=TEXT_COLOR)
            ax.spines['bottom'].set_color(TEXT_COLOR)
            ax.spines['top'].set_color(TEXT_COLOR)
            ax.spines['left'].set_color(TEXT_COLOR)
            ax.spines['right'].set_color(TEXT_COLOR)
            ax.grid(True, linestyle='--', alpha=0.4, color=GRID_COLOR)

            if not has_data:
                ax.text(0.5, 0.5, 'Sin datos suficientes', ha='center', color='red')
                filename = f"vacio_{graph_type}.png"
            else:
                ax.legend(facecolor='white', edgecolor='#cccccc')

            # Guardar
            output_dir = os.path.join("Resultados", "Graficos")
            os.makedirs(output_dir, exist_ok=True)
            path = os.path.join(output_dir, filename)
            
            # GUARDADO FORZANDO BLANCO
            plt.savefig(path, bbox_inches='tight', dpi=300, facecolor='white', transparent=False)
            plt.close(fig)
            
            if has_data:
                QMessageBox.information(self, "Éxito", f"Gráfico guardado:\n{path}")
            else:
                QMessageBox.warning(self, "Aviso", "Gráfico vacío (sin datos válidos).")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error exportando:\n{e}")
            logger.error(f"Export Error: {e}")
    
    def refresh_theme(self):
        """Refresco rápido del tema actual"""

        self.apply_appearance()

    def apply_animations(self, mode: str):
        """
        Configura animaciones VISIBLES usando QPropertyAnimation (Qt nativo).
        """
        app = QApplication.instance()
        
        # 1. Efectos de sistema básicos
        enabled = mode != "Desactivadas"
        app.setEffectEnabled(Qt.UI_AnimateCombo, enabled)
        app.setEffectEnabled(Qt.UI_AnimateTooltip, enabled)
        app.setEffectEnabled(Qt.UI_FadeMenu, enabled)
        app.setEffectEnabled(Qt.UI_FadeTooltip, enabled)
        
        # 2. Duración global de animaciones
        if mode == "Desactivadas":
            self.anim_duration = 0
        elif mode == "Normales":
            self.anim_duration = 150
        else:  # Suaves
            self.anim_duration = 300
        
        # 3. ✅ APLICAR ANIMACIONES PROGRAMÁTICAS
        if enabled:
            self._setup_button_animations()
            self._setup_widget_effects()
        
        logger.info(f"✨ Animaciones: {mode} ({self.anim_duration}ms)")
        
        if hasattr(self, 'status_bar'):
            status_map = {
                "Desactivadas": "❌ SIN animaciones",
                "Normales": "⚡ Animaciones RÁPIDAS",
                "Suaves": "🌊 Animaciones SUAVES"
            }
            self.status_bar.set_status(f"🎨 {status_map[mode]}", "info")

    def _setup_button_animations(self):
        """
        Aplica efecto visual de "pulso" a botones importantes.
        Compatible con PyQt/PySide - NO usa CSS3.
        """
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        
        # Lista de botones críticos
        critical_buttons = []
        
        # Recopilar todos los botones que tengan clase CSS
        for btn in self.findChildren(QPushButton):
            btn_class = btn.property("class")
            if btn_class in ["primary", "success", "warning", "info"]:
                critical_buttons.append(btn)
        
        logger.debug(f"Configurando animaciones en {len(critical_buttons)} botones")
        
        for btn in critical_buttons:
            # Evitar duplicar si ya tiene animación
            if hasattr(btn, '_has_animation'):
                continue
            
            # Guardar evento original
            btn._original_press = btn.mousePressEvent
            btn._original_release = btn.mouseReleaseEvent
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ANIMACIÓN 1: Efecto de "Brillo" al hacer clic
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            def create_press_handler(button):
                def on_press(event):
                    if self.anim_duration == 0:
                        button._original_press(event)
                        return
                    
                    # Crear efecto de opacidad
                    if not hasattr(button, '_opacity_effect'):
                        button._opacity_effect = QGraphicsOpacityEffect()
                        button.setGraphicsEffect(button._opacity_effect)
                    
                    # Animación: Bajar opacidad
                    anim = QPropertyAnimation(button._opacity_effect, b"opacity")
                    anim.setDuration(self.anim_duration // 2)
                    anim.setStartValue(1.0)
                    anim.setEndValue(0.7)
                    anim.setEasingCurve(QEasingCurve.OutCubic)
                    anim.start()
                    
                    button._press_anim = anim  # Guardar referencia
                    button._original_press(event)
                
                return on_press
            
            def create_release_handler(button):
                def on_release(event):
                    if self.anim_duration == 0:
                        button._original_release(event)
                        return
                    
                    # Animación: Restaurar opacidad
                    if hasattr(button, '_opacity_effect'):
                        anim = QPropertyAnimation(button._opacity_effect, b"opacity")
                        anim.setDuration(self.anim_duration)
                        anim.setStartValue(0.7)
                        anim.setEndValue(1.0)
                        anim.setEasingCurve(QEasingCurve.OutBounce)
                        anim.start()
                    
                    button._original_release(event)
                
                return on_release
            
            btn.mousePressEvent = create_press_handler(btn)
            btn.mouseReleaseEvent = create_release_handler(btn)
            btn._has_animation = True

    def _setup_widget_effects(self):
        """
        Efectos visuales en widgets especiales (tabs, progress bars, etc.)
        """
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ANIMACIÓN 1: Fade entre pestañas
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if hasattr(self, 'tabs') and not hasattr(self.tabs, '_fade_setup'):
            def animate_tab_change(index):
                if self.anim_duration == 0:
                    return
                
                widget = self.tabs.widget(index)
                if widget:
                    # Crear efecto de opacidad
                    if not hasattr(widget, '_opacity_effect'):
                        widget._opacity_effect = QGraphicsOpacityEffect()
                        widget.setGraphicsEffect(widget._opacity_effect)
                    
                    # Fade in
                    anim = QPropertyAnimation(widget._opacity_effect, b"opacity")
                    anim.setDuration(self.anim_duration)
                    anim.setStartValue(0.0)
                    anim.setEndValue(1.0)
                    anim.setEasingCurve(QEasingCurve.InOutQuad)
                    anim.start()
                    
                    # Guardar para evitar garbage collection
                    widget._fade_anim = anim
            
            self.tabs.currentChanged.connect(animate_tab_change)
            self.tabs._fade_setup = True
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ANIMACIÓN 2: Hover en botones secundarios
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        for btn in self.findChildren(QPushButton):
            if btn.property("class") == "secondary" and not hasattr(btn, '_hover_setup'):
                btn._original_enter = btn.enterEvent
                btn._original_leave = btn.leaveEvent
                
                def create_hover_enter(button):
                    def on_enter(event):
                        if self.anim_duration > 0:
                            # Crear animación de tamaño (sutil)
                            button.setStyleSheet(button.styleSheet() + """
                                QPushButton { font-size: 1.05em; }
                            """)
                        button._original_enter(event)
                    return on_enter
                
                def create_hover_leave(button):
                    def on_leave(event):
                        if self.anim_duration > 0:
                            # Restaurar
                            button.setStyleSheet(button.styleSheet().replace(
                                "font-size: 1.05em;", ""
                            ))
                        button._original_leave(event)
                    return on_leave
                
                btn.enterEvent = create_hover_enter(btn)
                btn.leaveEvent = create_hover_leave(btn)
                btn._hover_setup = True

    def apply_appearance(self):
        """Lee los valores de los widgets y sincroniza el motor de estilos"""
        try:
            theme = self.combo_theme.currentText()
            font_size = int(self.combo_font_size.currentText() or 11)
            density = self.combo_density.currentText()
            animations = self.combo_animations.currentText()

            # ✅ FORZAR ACTUALIZACIÓN: Llamamos a toggle_theme que reconstruye TODO el CSS
            self.toggle_theme(theme, font_size, density)

            self.apply_animations(animations)
    
            if hasattr(self, 'status_bar'):
                # ✅ Indicador visual de si el alto contraste está activo
                anim_status = {
                "Desactivadas": "❌ SIN animaciones",
                "Normales": "⚡ Animaciones NORMALES (150ms)",
                "Suaves": "🌊 Animaciones SUAVES (300ms)"
                }.get(animations, "")
                
                self.status_bar.set_status(
                    f"✨ Tema: {theme} | Densidad: {density} | {anim_status}", 
                    "info"
                )
                
        except Exception as e:
            logger.error(f"Error aplicando configuración visual: {e}")

    def toggle_theme(self, text, font_size=11, density="Normal"):
        """
        Motor de estilos estandarizado para la aplicación.
        Controla Temas, Densidad, Fuentes y Estados Biométricos.
        """
        # 1. DETERMINAR SI USAR MODO OSCURO
        if text == "Sistema":
            is_dark = darkdetect.isDark() 
            theme_mode = "dark" if is_dark else "light"
        else:
            is_dark = (text == "Oscuro")
            theme_mode = "dark" if is_dark else "light"

        qdarktheme.setup_theme(theme_mode)
        self.is_currently_dark = is_dark

        # 2. CONFIGURAR DENSIDAD VISUAL (Padding y Alturas)
        if density == "Súper Compacta":
            row_h = 18         
            padding_val = 0     
            btn_padding = "1px 4px"
        elif density == "Compacta":
            row_h = 24
            padding_val = 2
            btn_padding = "4px 8px"
        elif density == "Cómoda":
            row_h = 42
            padding_val = 12
            btn_padding = "12px 24px"
        else: 
            row_h = 32
            padding_val = 6
            btn_padding = "8px 16px"

        # Aplicar altura de filas a todas las tablas de la app
        for table in self.findChildren(QTableWidget):
            table.verticalHeader().setDefaultSectionSize(row_h)
         
        c_high = "rgba(42, 157, 143, 0.12)"
        c_medium = "rgba(231, 111, 81, 0.12)"
        c_low = "rgba(231, 76, 60, 0.12)"
        # 3. DEFINICIÓN DE PALETA TÉCNICA
        if is_dark:
            # ---------- MODO OSCURO ----------
            c_primary_base, c_primary_hover = "#00b4d8", "#48cae4"
            c_success_base, c_success_hover = "#2a9d8f", "#2ec4b6"
            c_info_base, c_info_hover = "#4ea8de", "#74c0fc"   
            c_secondary_base, c_secondary_hover = "#2b2f33", "#3a3f44"
            c_disable_base, c_disable_hover =  "#1f2428", "#2a3035"
            c_warning_base, c_warning_hover = "#e76f51", "#f4a261"
            c_error_base ="#e74c3c"
            
            
            text_col   = "#e0e0e0"
            bg_paper   = "#1e1e1e"     
            border_div = "#2f2f33" 
            c_sec_text = "#dee2e6"
            item_hover = "rgba(78, 168, 222, 0.18)"

            self.report_style = {
                'bg': bg_paper,
                'text': text_col,
                'header': c_primary_hover,
                'accent': c_primary_base,
                'row': '#2d2d2d',
                'border': border_div,
                'val_color': c_success_base
            }
        else:
            # ---------- MODO CLARO ----------
            c_primary_base, c_primary_hover = "#0077b6", "#005f8b"
            c_success_base, c_success_hover = "#264653", "#2f5f73"
            c_info_base, c_info_hover       = "#023e8a", "#00296b"
            c_warning_base, c_warning_hover = "#d62828", "#a61e1e"
            c_secondary_base, c_secondary_hover = "#f1f3f5", "#dee2e6"
            c_disable_base, c_disable_hover =  "#d6d9dc", "#cfd4d8"
            c_error_base ="#e74c3c"
            
            text_col   = "#2c3e50"
            bg_paper   = "#ffffff"
            c_sec_text = "#212529"
            border_div = "#ced4da"
            item_hover = "rgba(0, 119, 182, 0.08)"

            self.report_style = {
                'bg': bg_paper,
                'text': text_col,
                'header': c_primary_base,
                'accent': c_primary_base,
                'row': '#f8f9fa',
                'border': border_div,
                'val_color': c_success_base
            }


        # 4. CONSTRUCCIÓN DE LA HOJA DE ESTILO (CSS)
        custom_css = f"""
            /* Configuración Global */
            * {{
                font-size: {font_size}px;
            }}
            
            * , QHeaderView::section, QTableWidget, QLineEdit, QComboBox {{
                font-size: {font_size}px;
            }}
            
            /* Dentro de custom_css en toggle_theme */
            QDoubleSpinBox[class="biometric-input"] {{
                padding: {padding_val}px;
                border: 1px solid {border_div};
                border-radius: 4px;
                background-color: {bg_paper};
                color: {text_col};
                min-width: 100px;
            }}

            /* Resalte cuando el usuario está editando */
            QDoubleSpinBox[class="biometric-input"]:focus {{
                border: 2px solid {c_primary_base};
            }}

        /* --- ESTILOS DE LA BARRA DE ESTADO --- */
            #StatusBar {{
                background-color: {bg_paper};
                border-top: 1px solid {border_div};
            }}
            
            /* Separador Vertical */
            #StatusSeparator {{
                background-color: {border_div}; 
                margin: 8px 2px;
                min-width: 1px;
                max-width: 1px;
            }}

            /* Labels Genéricos de la Barra */
            #StatusBar QLabel {{
                font-family: 'Segoe UI', sans-serif;
                font-size: 10pt;
                padding: 0 4px;
            }}

            /* --- ESTADOS DE COLOR (TEXTO) --- */
            
            /* Normal (Texto base) */
            #StatusBar QLabel[state="normal"] {{ color: {text_col}; }}
            
            /* Dim (Texto secundario / gris) */
            #StatusBar QLabel[state="dim"] {{ color: {c_sec_text}; }}
            
            /* Info (Azul) */
            #StatusBar QLabel[state="info"] {{ color: {c_info_base}; font-weight: bold; }}
            
            /* Success (Verde) */
            #StatusBar QLabel[state="success"] {{ color: {c_success_base}; font-weight: bold; }}
            
            /* Warning (Naranja) */
            #StatusBar QLabel[state="warning"] {{ color: {c_warning_base}; font-weight: bold; }}
            
            /* Error (Rojo) */
            #StatusBar QLabel[state="error"] {{ color: {c_error_base}; font-weight: bold; }}
            
            /* Accent (Para GPU - Usaremos el Primary o un color especial) */
            #StatusBar QLabel[state="accent"] {{ color: {c_primary_base}; font-weight: bold; }}

            /* --- BOTONES CON CLASES --- */
            QPushButton[class] {{
                border-radius: 6px;
                padding: {btn_padding};
                font-weight: bold;
                font-family: "Segoe UI", sans-serif;
                border: none;
            }}

            QPushButton[class="primary"] {{ background-color: {c_primary_base}; color: #ffffff; }}
            QPushButton[class="primary"]:hover {{ background-color: {c_primary_hover}; }}

            QPushButton[class="success"] {{ background-color: {c_success_base}; color: #ffffff; }}
            QPushButton[class="success"]:hover {{ background-color: {c_success_hover}; }}
            QPushButton[class="success"]:checked {{background-color: {c_success_hover};}}
            QPushButton[class="success"]:checked:hover {{background-color: {c_success_base};}}

            QPushButton[class="info"] {{ background-color: {c_info_base}; color: #ffffff; }}
            QPushButton[class="info"]:hover {{ background-color: {c_info_hover}; }}

            QPushButton[class="warning"] {{ background-color: {c_warning_base}; color: #ffffff; }}
            QPushButton[class="warning"]:hover {{ background-color: {c_warning_hover}; }}

            QPushButton[class="secondary"] {{background-color: {c_secondary_base}; color: {c_sec_text}; border: 1px solid {border_div};}}
            QPushButton[class="secondary"]:hover {{background-color: {c_secondary_hover}; color: {c_sec_text}; border: 1px solid {border_div};}}
            
            QPushButton:disabled {{background-color: {c_disable_base}; color: {c_sec_text}; border: 1px solid {border_div};opacity: 0.6;}}
            QPushButton:disabled:hover {{background-color: {c_disable_hover};}}

            /* --- ESTADOS DEL REPORTE DE RESULTADOS --- */
            
            /* Estado Normal / Info / Ready */
            QTextEdit[class="report-text"][state="ready"],
            QTextEdit[class="report-text"][state="info"] {{
                border: 1px solid {c_info_base};
                background-color: {bg_paper}; 
                color: {text_col};
            }}

            /* Estado Éxito (Verde) */
            QTextEdit[class="report-text"][state="success"] {{
                border: 2px solid {c_success_base};
                background-color: {c_high};
                color: {text_col};
            }}

            /* Estado Advertencia (Naranja) */
            QTextEdit[class="report-text"][state="warning"] {{
                border: 2px solid {c_warning_base};
                background-color: {c_medium};
                color: {text_col};
            }}

            /* Estado Error (Rojo) */
            QTextEdit[class="report-text"][state="error"] {{
                border: 2px solid {c_error_base};
                background-color: {c_low};
                color: {text_col};
            }}


            /* --- VISORES DE CÁMARA --- */
            QLabel[class="video-feed"] {{
                border: 2px solid {border_div};
                background-color: #000000;
                border-radius: 8px;
            }}
            QLabel[class="video-lateral"] {{
                border: 3px solid {c_primary_base};
                border-radius: 8px;
                background-color: #000000;
            }}
            QLabel[class="video-cenital"] {{
                border: 3px solid {c_success_base};
                border-radius: 8px;
                background-color: #000000;
            }}

            
            /* --- NIVELES DE CONFIANZA (Semaforización) --- */
            QProgressBar[level="high"]::chunk {{
                background-color: {c_high};
                border: 1.5px solid {c_success_base};
                border-radius: 4px;
            }}
            QProgressBar[level="medium"]::chunk {{
                background-color: {c_medium};
                border: 1.5px solid {c_warning_base};
                border-radius: 4px;
            }}
            QProgressBar[level="low"]::chunk {{
                background-color: {c_low};
                border: 1.5px solid {c_error_base};
                border-radius: 4px;
            }}

            /* --- ESTADOS DEL FACTOR K (SEMÁFORO) --- */
            QLabel[state="empty"] {{
                background-color: rgba(255, 255, 255, 0.04);
                color: {text_col};
                border: 1px dashed {border_div};
                border-radius: 4px;
                padding: 5px;
                font-style: italic;
            }}
            QLabel[state="ok"] {{
                background-color: {c_high};
                color: {text_col};
                border: 1.5px solid {c_success_base};
                border-radius: 4px;
                padding: 5px;
            }}
            QLabel[state="warn"] {{
                background-color: {c_medium};
                color: {text_col};
                border: 1.5px solid {c_warning_base};
                border-radius: 4px;
                padding: 5px;
            }}
            QLabel[state="bad"] {{
                background-color: {c_low};
                color: {text_col};
                border: 1.5px solid {c_error_base};
                border-radius: 4px;
                padding: 5px;
            }}
            QLabel[state="success"] {{
                color: {c_success_base};
                font-weight: bold;
            }}
            QLabel[state="warning"] {{
                color: {c_warning_base};
                font-weight: bold;
            }}
            QLabel[state="error"] {{
                color: {c_error_base};
                font-weight: bold;
            }}

            /* --- BADGES DE TIPO --- */
            QLabel[tipo="auto"] .badge {{ font-weight: bold; }}
            QLabel[tipo="manual"] .badge {{ font-style: italic; }}

            /* --- COMPONENTES DE DATOS --- */
            QTableWidget {{
                background-color: {bg_paper};
                gridline-color: {border_div};
            }}
            QTableWidget::item {{
                padding: {padding_val}px;
            }}
            QHeaderView::section {{
                background-color: {c_primary_base};
                color: #ffffff;
                font-weight: bold;
                border: none;
            }}
            QTextEdit[class="report-text"] {{
                background-color: {bg_paper};
                border: 1px solid {border_div};
                border-radius: 6px;
                padding: 10px;
            }}
            QLabel[class="report-text"] {{
                font-family: 'Consolas', 'Courier New', monospace;
            }}
        """

        # --- CAPA DE ALTO CONTRASTE ---
        high_contrast_css = ""
        if hasattr(self, "chk_high_contrast") and self.chk_high_contrast.isChecked():
            high_contrast_css = """
                QWidget { background-color: #000000; color: #ffffff; border-color: #ffffff; }
                QPushButton { border: 2px solid #ffffff; background-color: #000000; color: #ffffff; }
                QPushButton:hover { background-color: #ffffff; color: #000000; }
                QLabel { color: #ffffff; font-weight: bold; }
                QHeaderView::section { background-color: #ffffff; color: #000000; }
            """

        # 5. APLICACIÓN FINAL
        app = QApplication.instance()
        app.setStyleSheet(
            qdarktheme.load_stylesheet(theme_mode) +
            custom_css +
            high_contrast_css
        )
        
        self.update_report_html()
        
        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _configure_widget_animations(self, enabled: bool, duration: int):
        """
        Aplica animaciones programáticas a widgets específicos.
        Se ejecuta después de cambiar el modo de animación.
        """
        if not enabled:
            return  # Si están desactivadas, no hacemos nada
        
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QAbstractAnimation
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ANIMACIÓN 1: Botones principales (Feedback visual al hacer clic)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        primary_buttons = [
            self.btn_capture,
            self.btn_save,
            self.btn_manual_capture,
            self.btn_manual_save
        ]
        
        for btn in primary_buttons:
            if not hasattr(btn, '_animation_setup'):
                btn._original_click = btn.mousePressEvent
                
                def animated_click(event, button=btn):
                    # Animación de "presión"
                    anim = QPropertyAnimation(button, b"geometry")
                    anim.setDuration(duration // 3)  # Rápido
                    
                    original_geo = button.geometry()
                    pressed_geo = original_geo.adjusted(2, 2, -2, -2)  # Reducir 2px
                    
                    anim.setStartValue(original_geo)
                    anim.setEndValue(pressed_geo)
                    anim.setEasingCurve(QEasingCurve.OutCubic)
                    anim.start(QAbstractAnimation.DeleteWhenStopped)
                    
                    # Restaurar después
                    def restore():
                        restore_anim = QPropertyAnimation(button, b"geometry")
                        restore_anim.setDuration(duration // 2)
                        restore_anim.setStartValue(pressed_geo)
                        restore_anim.setEndValue(original_geo)
                        restore_anim.setEasingCurve(QEasingCurve.OutBounce)
                        restore_anim.start(QAbstractAnimation.DeleteWhenStopped)
                    
                    QTimer.singleShot(duration // 3, restore)
                    button._original_click(event)
                
                btn.mousePressEvent = animated_click
                btn._animation_setup = True
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ANIMACIÓN 2: Tabs (Desplazamiento suave al cambiar)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if hasattr(self, 'tabs') and not hasattr(self.tabs, '_animation_setup'):
            self.tabs._original_tab_change = self.tabs.currentChanged
            
            def animated_tab_change(index):
                # Crear animación de fade
                fade_widget = self.tabs.currentWidget()
                if fade_widget:
                    fade_anim = QPropertyAnimation(fade_widget, b"windowOpacity")
                    fade_anim.setDuration(duration)
                    fade_anim.setStartValue(0.0)
                    fade_anim.setEndValue(1.0)
                    fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
                    fade_anim.start(QAbstractAnimation.DeleteWhenStopped)
                
                self.tabs._original_tab_change.emit(index)
            
            self.tabs.currentChanged.disconnect()
            self.tabs.currentChanged.connect(animated_tab_change)
            self.tabs._animation_setup = True
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ANIMACIÓN 3: Barra de confianza (Animación suave existente mejorada)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if hasattr(self, 'confidence_bar'):
            # Ya tienes _animate_confidence, pero podemos mejorarla
            # La velocidad se adapta según self.anim_duration
            pass  # Tu código actual ya está bien
        
        logger.debug(f"Animaciones aplicadas a {len(primary_buttons)} botones y widgets críticos")        
    
    
    
    
        
    def create_settings_tab(self):
        """Crea la pestaña de configuración"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # ---------------------------------------------
        # APARIENCIA
        # ---------------------------------------------
        appearance_group = QGroupBox("Apariencia")
        appearance_layout = QHBoxLayout(appearance_group)

        # Tema
        appearance_layout.addWidget(QLabel("Tema:"))
        self.combo_theme = QComboBox()
        self.combo_theme.setCursor(Qt.PointingHandCursor)
        self.combo_theme.addItems(["Sistema", "Claro", "Oscuro"])
        self.combo_theme.setCurrentText("Sistema")
        self.combo_theme.setToolTip(
            "Cambia el esquema de colores de la aplicación."
        )
        appearance_layout.addWidget(self.combo_theme)

        # Alto contraste
        self.chk_high_contrast = QCheckBox("Alto contraste")
        self.chk_high_contrast.setCursor(Qt.PointingHandCursor)
        self.chk_high_contrast.setToolTip(
            "Mejora la legibilidad usando colores de alto contraste."
        )
        appearance_layout.addWidget(self.chk_high_contrast)
        self.chk_high_contrast.stateChanged.connect(self.apply_appearance)

        # Tamaño de fuente
        appearance_layout.addWidget(QLabel("Fuente:"))
        self.combo_font_size = QComboBox()
        self.combo_font_size.setCursor(Qt.PointingHandCursor)
        self.combo_font_size.addItems(["6", "8", "10", "11", "12", "14", "16"])
        self.combo_font_size.setToolTip(
            "Ajusta el tamaño del texto en toda la interfaz."
        )
        appearance_layout.addWidget(self.combo_font_size)

        # Densidad
        appearance_layout.addWidget(QLabel("Densidad:"))
        self.combo_density = QComboBox()
        self.combo_density.setCursor(Qt.PointingHandCursor)
        self.combo_density.addItems(["Súper Compacta","Compacta", "Normal", "Cómoda"])
        self.combo_density.setToolTip(
            "Define el espaciado entre elementos de la interfaz."
        )
        appearance_layout.addWidget(self.combo_density)

        # Animaciones
        appearance_layout.addWidget(QLabel("Animaciones:"))
        self.combo_animations = QComboBox()
        self.combo_animations.setCursor(Qt.PointingHandCursor)
        self.combo_animations.addItems(["Desactivadas", "Normales", "Suaves"])
        self.combo_animations.setToolTip(
            "Controla la suavidad de las animaciones visuales."
        )
        appearance_layout.addWidget(self.combo_animations)
        layout.addWidget(appearance_group)

        for w in (self.combo_theme, self.combo_font_size, self.combo_density, self.combo_animations):
            w.blockSignals(True) 
            
        self.combo_theme.setCurrentText("Sistema")
        self.combo_font_size.setCurrentText("11")
        self.combo_density.setCurrentText("Normal")
        self.combo_animations.setCurrentText("Normales")
        self.chk_high_contrast.setChecked(False)

        for w in (self.combo_theme, self.combo_font_size, self.combo_density, self.combo_animations):
            w.blockSignals(False)
            w.currentTextChanged.connect(self.apply_appearance)

        # ---------------------------------------------
        # 2. CÁMARAS
        # ---------------------------------------------
        eng_group = QGroupBox("Hardware")
        eng_layout = QGridLayout(eng_group)
        eng_layout.setSpacing(10)

        # Índices de Cámara
        eng_layout.addWidget(QLabel("Cámara Lateral:"), 0, 0)
        self.spin_cam_left = QSpinBox()
        self.spin_cam_left.setRange(0, 10)
        eng_layout.addWidget(self.spin_cam_left, 0, 1)

        eng_layout.addWidget(QLabel("Cámara Cenital:"), 0, 2)
        self.spin_cam_top = QSpinBox()
        self.spin_cam_top.setRange(0, 10)
        eng_layout.addWidget(self.spin_cam_top, 0, 3)

        # Separador visual
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        eng_layout.addWidget(line, 1, 0, 1, 4)
        
        # Botón de Re-conexión
        btn_reconnect = QPushButton("Reconectar Cámaras")
        btn_reconnect.setProperty("class", "info")
        btn_reconnect.style().unpolish(btn_reconnect) 
        btn_reconnect.style().polish(btn_reconnect)
        btn_reconnect.setToolTip("Reconectar las cámaras.")
        btn_reconnect.clicked.connect(self.reconnect_cameras)
        eng_layout.addWidget(btn_reconnect, 5, 0, 1, 4)

        layout.addWidget(eng_group)
        
        # =============================================
        # 3. CALIBRACIÓN DE ESCALAS (Tu código integrado)
        # =============================================
        manual_group = QGroupBox("Calibración de Escalas (cm/px)")
        manual_group.setToolTip("Define cuántos centímetros reales equivale 1 píxel en pantalla.")
        manual_layout = QGridLayout(manual_group)
        
        # Encabezados para ordenarlo visualmente
        manual_layout.addWidget(QLabel("<b>Parámetro</b>"), 0, 0)
        manual_layout.addWidget(QLabel("<b>Cámara Lateral</b>"), 0, 1)
        manual_layout.addWidget(QLabel("<b>Cámara Cenital</b>"), 0, 2)

        manual_layout.addWidget(QLabel("Escala Frente:"), 1, 0)
        
        # Lateral Frente
        self.spin_scale_front_left = QDoubleSpinBox()
        self.spin_scale_front_left.setRange(0.00001, 1.0)
        self.spin_scale_front_left.setValue(getattr(self, 'scale_front_left', 0.006666))
        self.spin_scale_front_left.setDecimals(6)
        self.spin_scale_front_left.setSingleStep(0.0001)
        self.spin_scale_front_left.setToolTip("cm/px para objetos pegados al tanque (Lateral)")
        manual_layout.addWidget(self.spin_scale_front_left, 1, 1)

        # Cenital Frente
        self.spin_scale_front_top = QDoubleSpinBox()
        self.spin_scale_front_top.setRange(0.00001, 1.0)
        self.spin_scale_front_top.setValue(getattr(self, 'scale_front_top', 0.004348))
        self.spin_scale_front_top.setDecimals(6)
        self.spin_scale_front_top.setSingleStep(0.0001)
        self.spin_scale_front_top.setToolTip("cm/px para objetos pegados al tanque (Cenital)")
        manual_layout.addWidget(self.spin_scale_front_top, 1, 2)
        
        manual_layout.addWidget(QLabel("Escala Fondo:"), 2, 0)

        # Lateral Fondo
        self.spin_scale_back_left = QDoubleSpinBox()
        self.spin_scale_back_left.setRange(0.00001, 1.0)
        self.spin_scale_back_left.setValue(getattr(self, 'scale_back_left', 0.014926))
        self.spin_scale_back_left.setDecimals(6)
        self.spin_scale_back_left.setSingleStep(0.0001)
        self.spin_scale_back_left.setToolTip("cm/px para el fondo del tanque (Lateral)")
        manual_layout.addWidget(self.spin_scale_back_left, 2, 1)

        # Cenital Fondo
        self.spin_scale_back_top = QDoubleSpinBox()
        self.spin_scale_back_top.setRange(0.00001, 1.0)
        self.spin_scale_back_top.setValue(getattr(self, 'scale_back_top', 0.012582))
        self.spin_scale_back_top.setDecimals(6)
        self.spin_scale_back_top.setSingleStep(0.0001)
        self.spin_scale_back_top.setToolTip("cm/px para el fondo del tanque (Cenital)")
        manual_layout.addWidget(self.spin_scale_back_top, 2, 2)
        
        # Botones específicos de calibración 
        calib_btn_layout = QHBoxLayout()
        
        btn_default = QPushButton("Restaurar Fábrica")
        btn_default.setProperty("class", "warning")
        btn_default.style().unpolish(btn_default)
        btn_default.style().polish(btn_default)
        btn_default.setCursor(Qt.PointingHandCursor)
        btn_default.setToolTip("Carga los valores de escala predeterminados.")
        btn_default.clicked.connect(self.load_default_calibration)
        calib_btn_layout.addWidget(btn_default, 5)
        
        btn_apply_manual = QPushButton("Aplicar Escalas")
        btn_apply_manual.setProperty("class", "success")
        btn_apply_manual.style().unpolish(btn_apply_manual) 
        btn_apply_manual.style().polish(btn_apply_manual)
        btn_apply_manual.setCursor(Qt.PointingHandCursor)
        btn_apply_manual.setToolTip("Aplica estos valores de escala inmediatamente.")
        btn_apply_manual.clicked.connect(self.apply_manual_calibration)
        calib_btn_layout.addWidget(btn_apply_manual, 4.5)
        
        btn_calibraty = QPushButton("Calibrar")
        btn_calibraty.setProperty("class", "empty")   #arreglar   info
        btn_calibraty.style().unpolish(btn_calibraty) 
        btn_calibraty.style().polish(btn_calibraty)
        btn_calibraty.setCursor(Qt.PointingHandCursor)
        btn_calibraty.setToolTip("SOON...")
        #btn_calibraty.setToolTip("Abre la aplicación de calibración de escalas.")
        btn_calibraty.clicked.connect(self.open_live_calibration)
        calib_btn_layout.addWidget(btn_calibraty, 0.5)
        btn_calibraty.setEnabled(False) #arreglar
        
        manual_layout.addLayout(calib_btn_layout, 3, 0, 1, 3) 
        
        layout.addWidget(manual_group)
        
    
        # ---------------------------------------------
        # 4. DETECCIÓN 
        # ---------------------------------------------
        detection_group = QGroupBox("Parámetros de Detección (Filtros)")
        detection_layout = QGridLayout(detection_group)
        
        # --- Área Mínima ---
        detection_layout.addWidget(QLabel("Área Mínima Contorno:"), 0, 0)
        self.spin_min_area = QSpinBox()
        self.spin_min_area.setRange(10, 10000)
        self.spin_min_area.setValue(Config.MIN_CONTOUR_AREA)
        self.spin_min_area.setSuffix(" px")
        # Tooltip
        self.spin_min_area.setToolTip(
            "Ignora objetos más pequeños que este valor (en píxeles).\n"
            "Aumente este valor para filtrar ruido, burbujas o suciedad pequeña."
        )
        detection_layout.addWidget(self.spin_min_area, 0, 1)
        
        # --- Área Máxima ---
        detection_layout.addWidget(QLabel("Área Máxima Contorno:"), 1, 0)
        self.spin_max_area = QSpinBox()
        self.spin_max_area.setRange(1000, 1000000)
        self.spin_max_area.setValue(Config.MAX_CONTOUR_AREA)
        self.spin_max_area.setSuffix(" px")
        # Tooltip
        self.spin_max_area.setToolTip(
            "Ignora objetos más grandes que este valor.\n"
            "Útil para evitar detectar la mano del operario o reflejos grandes."
        )
        detection_layout.addWidget(self.spin_max_area, 1, 1)
        
        # --- Confianza ---
        detection_layout.addWidget(QLabel("Umbral Confianza:"), 2, 0)
        self.spin_confidence = QDoubleSpinBox()
        self.spin_confidence.setRange(0.0, 1.0)
        self.spin_confidence.setValue(Config.CONFIDENCE_THRESHOLD)
        self.spin_confidence.setDecimals(2)
        self.spin_confidence.setSingleStep(0.05)
        # Tooltip
        self.spin_confidence.setToolTip(
            "Nivel de certeza requerido para considerar válida una detección."
        )
        detection_layout.addWidget(self.spin_confidence, 2, 1)
        
        layout.addWidget(detection_group)
        
        
        # ---------------------------------------------
        # 5. VALIDACIÓN BIOLÓGICA
        # ---------------------------------------------
        validation_group = QGroupBox("Parámetros de Validación (Medidas Reales)")
        validation_layout = QGridLayout(validation_group)
        
        # --- Longitud Mínima ---
        validation_layout.addWidget(QLabel("Longitud Mínima (cm):"), 0, 0)
        self.spin_min_length = QDoubleSpinBox()
        self.spin_min_length.setRange(0.1, 100.0)
        self.spin_min_length.setValue(Config.MIN_LENGTH_CM)
        self.spin_min_length.setSuffix(" cm")
        # Tooltip
        self.spin_min_length.setToolTip(
            "Medida mínima aceptable en centímetros."
        )
        validation_layout.addWidget(self.spin_min_length, 0, 1)
        
        # --- Longitud Máxima ---
        validation_layout.addWidget(QLabel("Longitud Máxima (cm):"), 1, 0)
        self.spin_max_length = QDoubleSpinBox()
        self.spin_max_length.setRange(1.0, 200.0)
        self.spin_max_length.setValue(Config.MAX_LENGTH_CM)
        self.spin_max_length.setSuffix(" cm")
        # Tooltip
        self.spin_max_length.setToolTip(
            "Medida máxima aceptable en centímetros."
        )
        validation_layout.addWidget(self.spin_max_length, 1, 1)
        
        layout.addWidget(validation_group)
        
        # ---------------------------------------------
        # 6. CHROMA KEY (HSV)
        # ---------------------------------------------

        chroma_group = QGroupBox("Calibración de Color (Chroma Key)")
        chroma_group.setToolTip("Ajuste los rangos HSV para aislar el fondo de cada cámara.")
        chroma_layout = QVBoxLayout(chroma_group)

        # Usamos un TabWidget o un Splitter interno si quieres ahorrar espacio, 
        # pero para el laboratorio lo mejor es tenerlo a la vista:
        hsv_container = QHBoxLayout()

        # --- PANEL CÁMARA LATERAL ---
        group_hsv_lat = QGroupBox("Cámara Lateral (Fondo)")
        layout_hsv_lat = QGridLayout(group_hsv_lat)
        
        self.spin_hue_min_lat = self._add_hsv_spin(layout_hsv_lat, "Hue Mín:", 0, 0, 35, 179)
        self.spin_hue_max_lat = self._add_hsv_spin(layout_hsv_lat, "Hue Máx:", 0, 2, 85, 179)
        self.spin_sat_min_lat = self._add_hsv_spin(layout_hsv_lat, "Sat Mín:", 1, 0, 40, 255)
        self.spin_sat_max_lat = self._add_hsv_spin(layout_hsv_lat, "Sat Máx:", 1, 2, 255, 255)
        self.spin_val_min_lat = self._add_hsv_spin(layout_hsv_lat, "Val Mín:", 2, 0, 40, 255)
        self.spin_val_max_lat = self._add_hsv_spin(layout_hsv_lat, "Val Máx:", 2, 2, 255, 255)
        
        # --- PANEL CÁMARA CENITAL ---
        group_hsv_top = QGroupBox("Cámara Cenital (Fondo)")
        layout_hsv_top = QGridLayout(group_hsv_top)
        
        self.spin_hue_min_top = self._add_hsv_spin(layout_hsv_top, "Hue Mín:", 0, 0, 35, 179)
        self.spin_hue_max_top = self._add_hsv_spin(layout_hsv_top, "Hue Máx:", 0, 2, 85, 179)
        self.spin_sat_min_top = self._add_hsv_spin(layout_hsv_top, "Sat Mín:", 1, 0, 40, 255)
        self.spin_sat_max_top = self._add_hsv_spin(layout_hsv_top, "Sat Máx:", 1, 2, 255, 255)
        self.spin_val_min_top = self._add_hsv_spin(layout_hsv_top, "Val Mín:", 2, 0, 40, 255)
        self.spin_val_max_top = self._add_hsv_spin(layout_hsv_top, "Val Máx:", 2, 2, 255, 255)

        hsv_container.addWidget(group_hsv_lat)
        hsv_container.addWidget(group_hsv_top)
        chroma_layout.addLayout(hsv_container)

        # Botón de Calibración Unificado
        btn_fine_tune = QPushButton("Abrir Calibrador de Color en Vivo")
        btn_fine_tune.setProperty("class", "info")
        btn_fine_tune.style().unpolish(btn_fine_tune)
        btn_fine_tune.style().polish(btn_fine_tune)
        btn_fine_tune.setCursor(Qt.PointingHandCursor)
        btn_fine_tune.clicked.connect(self.open_fine_tune_calibration)
        chroma_layout.addWidget(btn_fine_tune)

        layout.addWidget(chroma_group)

        # ---------------------------------------------
        # 7. GUARDAR
        # ---------------------------------------------
        btn_save_config = QPushButton("Guardar Configuración")
        btn_save_config.setProperty("class", "primary")
        btn_save_config.style().unpolish(btn_save_config)
        btn_save_config.style().polish(btn_save_config)
        btn_save_config.setCursor(Qt.PointingHandCursor)
        btn_save_config.clicked.connect(self.save_config)
        btn_save_config.setToolTip("Guarda todos los cambios actuales en el archivo de configuración.")
        layout.addWidget(btn_save_config)

        for w in (self.combo_theme, self.combo_font_size, self.combo_density):
            w.currentTextChanged.connect(self.apply_appearance)

        scroll.setWidget(widget)
        return scroll
    
    def _add_hsv_spin(self, layout, label, row, col, default, max_val):
        """Helper para crear spins HSV rápidamente"""
        layout.addWidget(QLabel(label), row, col)
        spin = QSpinBox()
        spin.setRange(0, max_val)
        spin.setValue(default)
        layout.addWidget(spin, row, col + 1)
        return spin
    
    def _create_scale_spin(self):
        """Helper para crear SpinBoxes de escala uniformes"""
        sb = QDoubleSpinBox()
        sb.setDecimals(6)
        sb.setRange(0.000001, 1.0)
        sb.setSingleStep(0.0001)
        return sb
    
    def open_live_calibration(self):
        from Herramientas.ScaleMedition import CalibradorEscalaVivo

        opciones = [
            "Cámara Lateral - Frente",
            "Cámara Lateral - Fondo",
            "Cámara Cenital - Frente",
            "Cámara Cenital - Fondo"
        ]

        seleccion, ok = QInputDialog.getItem(
            self, "Seleccionar Calibración",
            "¿Qué plano desea calibrar ahora?",
            opciones, 0, False
        )
        if not ok:
            return

        if "Lateral" in seleccion:
            cam_index = self.spin_cam_left.value()
            target_spin = self.spin_scale_front_left if "Frente" in seleccion else self.spin_scale_back_left
        else:
            cam_index = self.spin_cam_top.value()
            target_spin = self.spin_scale_front_top if "Frente" in seleccion else self.spin_scale_back_top

        try:
            self.status_bar.set_status(f"📏 Calibrando {seleccion}...", "info")

            calibrador = CalibradorEscalaVivo(camara_index=cam_index)
            escala = calibrador.calibrar_en_vivo(
                camara_index=cam_index,
                cm_reales=10.0
            )

            if escala is None:
                self.status_bar.set_status("⚠️ Calibración cancelada", "warning")
                return

            target_spin.setValue(escala)
            target_spin.setProperty("state", "success")
            target_spin.style().polish(target_spin)

            QMessageBox.information(
                self, "Calibración Exitosa",
                f"{seleccion}\nNueva escala: {escala:.6f} cm/px"
            )

        except Exception as e:
            logger.exception("Error en calibración en vivo")
            QMessageBox.critical(
                self, "Error de Hardware",
                f"No se pudo acceder a la cámara {cam_index}"
            )

    
    def load_default_calibration(self):
        """Carga los valores de calibración predeterminados de fábrica"""

        DEF_VALUES = {
            'FL': Config.SCALE_LAT_FRONT, 'BL': Config.SCALE_LAT_BACK,
            'FT': Config.SCALE_TOP_FRONT, 'BT':Config.SCALE_TOP_BACK
        }
        
        reply = QMessageBox.question(
            self, "Restaurar Fábrica", 
            "¿Desea restaurar los valores de escala predeterminados?\n\n"
            "Esto sobrescribirá cualquier calibración manual actual.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
            
        if reply == QMessageBox.StandardButton.Yes:
            self.spin_scale_front_left.setValue(DEF_VALUES['FL'])
            self.spin_scale_back_left.setValue(DEF_VALUES['BL'])
            self.spin_scale_front_top.setValue(DEF_VALUES['FT'])
            self.spin_scale_back_top.setValue(DEF_VALUES['BT'])

            self.apply_manual_calibration(silent=True)
            self.status_bar.set_status("🔄 Valores de fábrica restaurados", "warning")

    def apply_manual_calibration(self, silent=False):
        """Sincroniza las variables del motor de IA con los SpinBoxes de la UI"""
        try:
            self.scale_front_left = self.spin_scale_front_left.value()
            self.scale_back_left  = self.spin_scale_back_left.value()
            self.scale_front_top  = self.spin_scale_front_top.value()
            self.scale_back_top   = self.spin_scale_back_top.value()
            
            widgets = [
                self.spin_scale_front_left, self.spin_scale_back_left,
                self.spin_scale_front_top, self.spin_scale_back_top
            ]
            
            for w in widgets:
                w.setProperty("state", "success")
                w.style().unpolish(w)
                w.style().polish(w)
            
            msg = f"Escalas actualizadas: L:{self.scale_front_left:.5f} | T:{self.scale_front_top:.5f}"
            logger.info(msg)
            
            if not silent:
                self.status_bar.set_status(f"✅ {msg}", "success")

            QTimer.singleShot(2000, lambda: self._clear_scales_highlight(widgets))

        except Exception as e:
            logger.error(f"Error aplicando calibración: {e}")
            self.status_bar.set_status("❌ Error al aplicar escalas", "error")

    def _clear_scales_highlight(self, widgets):
        """Limpia el resalte de éxito de los campos de escala"""
        for w in widgets:
            w.setProperty("state", "")
            w.style().unpolish(w)
            w.style().polish(w)

    def create_no_camera_image(self):
        """Genera un placeholder elegante cuando la cámara falla"""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (35, 35, 35) 
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, "CAMARA NO DISPONIBLE", (140, 220), font, 1.1, (255, 255, 255), 3)
        cv2.putText(img, "Verifique conexion USB", (170, 270), font, 0.7, (180, 180, 180), 2)
        return img

    def start_cameras(self):
        """
        Inicia el streaming de video con arquitectura de estados
        """
        
        try:

            self.cap_left = OptimizedCamera(Config.CAM_LEFT_INDEX).start()
            self.cap_top = OptimizedCamera(Config.CAM_TOP_INDEX).start()
            
            left_ok = self.cap_left.isOpened()
            top_ok = self.cap_top.isOpened()
            
            if not left_ok or not top_ok:
                error_msg = "❌ Error de hardware en:\n"
                if not left_ok: error_msg += f"- Cámara Lateral (ID: {Config.CAM_LEFT_INDEX})\n"
                if not top_ok:  error_msg += f"- Cámara Cenital (ID: {Config.CAM_TOP_INDEX})\n"
                
                QMessageBox.critical(self, "Error de Cámaras", error_msg)
                
                no_cam_img = self.create_no_camera_image()
                for lbl in [self.lbl_left, self.lbl_top, self.lbl_manual_left, self.lbl_manual_top]:
                    self.display_frame(no_cam_img, lbl)
                
                self.status_bar.set_camera_status(False)
                self.status_bar.set_status("⚠️ Hardware de cámara no detectado", "error")
                return
            
            self.timer.start(16)
            self.status_bar.set_camera_status(True)
            self.status_bar.set_status("🚀 Sistema de visión activo", "success")
            fps_ms = int(1000 / Config.PREVIEW_FPS)  
            self.timer.start(fps_ms)
            self.last_frame_time = time.time()
            

            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al iniciar cámaras:\n{str(e)}")
            logger.error(f"Error al iniciar camaras: {str(e)}")

            # Mostrar imagen "No Cámara"
            no_cam_img = self.create_no_camera_image()
            self.display_frame(no_cam_img, self.lbl_left)
            self.display_frame(no_cam_img, self.lbl_top)
            
            self.status_bar.set_camera_status(False)
            self.status_bar.set_status("❌ Error crítico de inicialización", "error")
            
    def toggle_camera_pause(self):
        """Pausa o reanuda el visor de video"""
        if not self.cap_left and not self.cap_top: return
    
        if self.timer.isActive():
            self.timer.stop()
            self.status_bar.set_status("⏸️ Streaming pausado", "warning")
        else:
            self.timer.start(16)
            self.status_bar.set_status("▶️ Streaming reanudado", "success")
    
    def reconnect_cameras(self):
        """Libera y reconecta los puertos USB de forma segura"""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.status_bar.set_status("🔄 Reiniciando puertos USB...", "info")

        try:
            if hasattr(self, 'timer'): self.timer.stop()

            for cam in ['cap_left', 'cap_top']:
                obj = getattr(self, cam)
                if obj is not None:
                    try: obj.release()
                    except: pass
                    setattr(self, cam, None)

            Config.CAM_LEFT_INDEX = self.spin_cam_left.value()
            Config.CAM_TOP_INDEX = self.spin_cam_top.value()

            # Reiniciar
            self.start_cameras()
            self.status_bar.set_status("📷 Cámaras conectadas.", "info")
        finally:
            QApplication.restoreOverrideCursor()
     
    def update_frames(self):
        """🚀 MOTOR ULTRA-RÁPIDO: Mantiene 60 FPS estables"""
        if self.current_tab not in [0, 1] or not self.cap_left or not self.cap_top:
            return
        
        # 1. Captura de frames (Thread-Safe)
        ret_l, frame_l = self.cap_left.read()
        ret_t, frame_t = self.cap_top.read()
        if not (ret_l and ret_t): return

        # Guardamos referencia para cuentagotas (sin copiar memoria)
        self.current_frame_left = frame_l
        self.current_frame_top = frame_t

        # 2. Renderizado en UI (Usamos el frame directo, sin resize previo)
        if self.current_tab == 0:  
            self.display_frame(frame_l, self.lbl_left)
            self.display_frame(frame_t, self.lbl_top)

            # 3. Lógica de Procesamiento IA (Solo si no está bloqueado)
            if self.auto_capture_enabled and not self.processing_lock:
                # Construimos el diccionario usando la CACHÉ, NO los widgets
                params = {
                    'scales': {
                        'lat_front': self.scale_front_left, 'lat_back': self.scale_back_left,
                        'top_front': self.scale_front_top, 'top_back': self.scale_back_top
                    },
                    'hsv_lateral': self.cache_params['hsv_lat'],
                    'hsv_cenital': self.cache_params['hsv_top'],
                    'detection': {
                        'min_area': self.cache_params['min_area'],
                        'max_area': self.cache_params['max_area'],
                        'confidence': self.cache_params['conf']
                    }
                }
                self.processing_lock = True
                self.processor.add_frame(frame_l, frame_t, params)
                
        elif self.current_tab == 1:
            self.display_frame(frame_l, self.lbl_manual_left)
            self.display_frame(frame_t, self.lbl_manual_top)

        # 4. Contador de FPS (Monitor de salud del sistema)
        self.fps_counter += 1
        now = time.time()
        if now - self.last_fps_update >= 1.0:
            if hasattr(self, 'status_bar'):
                self.status_bar.update_system_info(fps=self.fps_counter)
            self.fps_counter = 0
            self.last_fps_update = now
    
    def display_frame(self, frame, label, is_mask=False):
        """
        Muestra el frame forzando una relación de aspecto 16:9.
        """
        if frame is None: return
        
        try:
            # 1. Dimensiones del contenedor (Label)
            win_w = label.width()
            win_h = label.height()
            if win_w < 10 or win_h < 10: return

            # 2. FORZAR 16:9 (Matemática de Proporción)
            target_aspect = 16 / 9
            
            # Calculamos el tamaño ideal basado en el espacio disponible
            if win_w / win_h > target_aspect:
                # El label es muy ancho: ajustamos por la altura
                new_h = win_h
                new_w = int(win_h * target_aspect)
            else:
                # El label es muy alto: ajustamos por la anchura
                new_w = win_w
                new_h = int(win_w / target_aspect)

            # 3. Redimensionar el frame de OpenCV
            frame_resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # 4. Conversión a QImage (Color o Máscara)
            if is_mask or len(frame_resized.shape) == 2:
                h, w = frame_resized.shape
                q_img = QImage(frame_resized.data, w, h, w, QImage.Format.Format_Grayscale8)
            else:
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                h, w, ch = frame_rgb.shape
                q_img = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)

            # 5. Mostrar y Centrar
            pixmap = QPixmap.fromImage(q_img)

            label.setUpdatesEnabled(False)
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setUpdatesEnabled(True)

        except Exception as e:
            logger.error(f"Error en display_frame: {e}")
            
            
    def update_cache(self):
        """Actualiza la caché de parámetros para el motor de visión"""
        self.cache_params['min_area'] = self.spin_min_area.value()
        self.cache_params['max_area'] = self.spin_max_area.value()
        self.cache_params['conf'] = self.spin_confidence.value()
        
        # Sincronizar HSV Lateral
        self.cache_params['hsv_lat'] = [
            self.spin_hue_min_lat.value(), self.spin_hue_max_lat.value(),
            self.spin_sat_min_lat.value(), self.spin_sat_max_lat.value(),
            self.spin_val_min_lat.value(), self.spin_val_max_lat.value()
        ]
        # Sincronizar HSV Cenital
        self.cache_params['hsv_top'] = [
            self.spin_hue_min_top.value(), self.spin_hue_max_top.value(),
            self.spin_sat_min_top.value(), self.spin_sat_max_top.value(),
            self.spin_val_min_top.value(), self.spin_val_max_top.value()
        ]
    
    def toggle_auto_capture(self, checked):
        """Activa/desactiva la captura automática con feedback visual de estado"""
        self.auto_capture_enabled = checked
        
        if checked:
            self.btn_auto_capture.setText("⏸️ Detener Auto-Captura")
            self.btn_auto_capture.setProperty("class", "secondary")
            self.status_bar.set_status("🚀 Detección IA activa: Buscando ejemplares...", "success")
            logger.info("Auto-captura habilitada.")
        else:
            self.btn_auto_capture.setText("▶️ Iniciar Auto-Captura")
            self.btn_auto_capture.setProperty("class", "secondary")
            self.status_bar.set_status("⏸️ Monitoreo automático pausado", "warning")
            
            self.processing_lock = False
            logger.info("Auto-captura deshabilitada.")
        
        self.btn_auto_capture.style().unpolish(self.btn_auto_capture)
        self.btn_auto_capture.style().polish(self.btn_auto_capture)
    
    
    
    def delete_selected_measurement(self):
        """Elimina de forma segura la medición seleccionada y su evidencia fotográfica"""
        selected_items = self.table_history.selectedItems()
        if not selected_items:
            self.status_bar.set_status("⚠️ Seleccione una fila para eliminar", "warning")
            return
        
        row = self.table_history.currentRow()
        try:
            measurement_id = int(self.table_history.item(row, 0).text())
            fish_id = self.table_history.item(row, 3).text()
        except (AttributeError, ValueError) as e:
            logger.error(f"Error al recuperar ID de la tabla: {e}")
            return

        reply = QMessageBox.question(
            self, "Confirmar Eliminación",
            f"¿Está seguro de eliminar permanentemente esta medición?\n\n"
            f"🔹 ID Registro: {measurement_id}\n"
            f"🔹 ID Pez: {fish_id}\n\n"
            f"Esta acción borrará la imagen y el dato de la base de datos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._execute_measurement_deletion(measurement_id)

    def _execute_measurement_deletion(self, measurement_id):
        """Lógica interna de borrado físico y lógico"""
        try:
            image_path = self.db.get_image_path(measurement_id)
            
            success = self.db.delete_measurement(measurement_id)
            
            if success:
                if image_path and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                        logger.info(f"Archivo eliminado: {image_path}")
                    except OSError as e:
                        logger.warning(f"No se pudo borrar el archivo físico: {e}")

                self.status_bar.set_status(f"🗑️ Medición {measurement_id} eliminada correctamente", "success")
                self.refresh_history()
                self.refresh_daily_counter()
            else:
                QMessageBox.critical(self, "Error", "No se pudo eliminar el registro de la base de datos.")

        except Exception as e:
            logger.error(f"Fallo crítico en proceso de eliminación: {e}")
            self.status_bar.set_status("❌ Error al procesar la eliminación", "error")
    
    def edit_selected_measurement(self):
        """Edita la medición seleccionada abriendo un Diálogo Estilizado"""
        selected_items = self.table_history.selectedItems()
        if not selected_items:
            self.status_bar.set_status("⚠️ Seleccione una fila para editar", "warning")
            return

        row = self.table_history.currentRow()
        try:
            measurement_id = int(self.table_history.item(row, 0).text())
        except (AttributeError, ValueError):
            self.status_bar.set_status("❌ Error al identificar el registro", "error")
            return

        measurement_data = self.db.get_measurement_as_dict(measurement_id)
        
        if not measurement_data:
            QMessageBox.critical(self, "Error de Datos", f"No se encontró el registro {measurement_id}")
            return

        dialog = EditMeasurementDialog(measurement_data, parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.get_updated_data()
            
            if self.db.update_measurement(measurement_id, updated_data):
                self.status_bar.set_status(f"✅ Registro {measurement_id} actualizado con éxito", "success")
                logger.info(f"Edición manual exitosa: ID {measurement_id}")
                
                self.refresh_history()
            else:
                QMessageBox.critical(self, "Error de Guardado", "No se pudieron persistir los cambios en la base de datos.")
   
    def view_measurement_image(self):
        """
        Abre el visor de imágenes pasando TODOS los datos de la BD.
        """
        # 1. Validación de selección
        selected = self.table_history.selectedItems()
        if not selected:
            self.status_bar.set_status("⚠️ Seleccione una medición para ver la imagen", "warning")
            return
        
        row = self.table_history.currentRow()
        try:
            m_id = int(self.table_history.item(row, 0).text())
        except (AttributeError, ValueError): return

        # 2. Obtener datos COMPLETOS de la BD
        m_data = self.db.get_measurement_as_dict(m_id)
        
        if not m_data:
            self.status_bar.set_status("❌ No se pudo recuperar la información de la BD", "error")
            return

        # 3. Extraer ruta de imagen con validación
        image_path = str(m_data.get('image_path', ""))
        
        if not image_path or not os.path.exists(image_path):
            self.status_bar.set_status(f"🖼️ Imagen no encontrada en: {image_path}", "error")
            QMessageBox.warning(self, "Archivo no encontrado", 
                              f"La imagen asociada al registro {m_id} no existe en el disco.")
            return

        # 4. ¡ESTE ERA EL ERROR! 
        # No crees un diccionario nuevo recortado. Usa m_data directamente.
        measurement_info = m_data 

        # 5. Lanzar Visor
        try:
            self.status_bar.set_status(f"🔍 Visualizando registro {m_id}...", "info")
            
            dialog = ImageViewerDialog(
                image_path,
                measurement_info,  
                self.advanced_detector,
                getattr(self, 'scale_front_left', 1.0),
                getattr(self, 'scale_back_left', 1.0),
                getattr(self, 'scale_front_top', 1.0),
                getattr(self, 'scale_back_top', 1.0),
                parent=self,  # Es bueno pasar self como parent
                on_update_callback=self.refresh_history
            )
            
            if dialog.exec():
                self.refresh_history()
                
        except Exception as e:
            logger.error(f"Error crítico en visor: {e}")
            QMessageBox.critical(self, "Error de Visor", f"No se pudo cargar el componente visual:\n{e}")

    
    def export_statistics(self):
        """
        Exporta Panel Gráfico (PNG) - BLINDADO y con FONDO BLANCO (Estilo Reporte)
        """
        # 1. Obtener datos
        measurements = self.db.get_filtered_measurements(limit=1000)
        
        if not measurements:
            QMessageBox.warning(self, "Advertencia", "No Hay Mediciones Para Exportar")
            return
        
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import numpy as np
            from BasedeDatos.DatabaseManager import MEASUREMENT_COLUMNS
            
            # --- CORRECCIÓN DE ESTILO ---
            # Forzamos estilo 'default' o 'seaborn' para que el PNG salga con fondo blanco
            # ideal para documentos, independiente de si la app está en modo oscuro.
            plt.style.use('default') 
            # -----------------------------

            # 2. Preparar salida
            output_dir = os.path.join("Resultados", "Graficos")
            os.makedirs(output_dir, exist_ok=True)
            
            # 3. DETECCIÓN DINÁMICA DE COLUMNAS
            col_map = {col: i for i, col in enumerate(MEASUREMENT_COLUMNS)}
            
            # --- HELPER DE EXTRACCIÓN NUMÉRICA SEGURA ---
            def get_val(row, col_name, default=0.0):
                if col_name in col_map:
                    idx = col_map[col_name]
                    if idx < len(row):
                        val = row[idx]
                        if val is None or val == "":
                            return default
                        try:
                            return float(val)
                        except:
                            return default
                return default

            def get_str(row, col_name):
                if col_name in col_map:
                    idx = col_map[col_name]
                    if idx < len(row):
                        return str(row[idx]) if row[idx] is not None else ""
                return ""
            # --------------------------------------------

            # Extraer datos usando el helper seguro
            lengths = [get_val(m, 'length_cm') for m in measurements if get_val(m, 'length_cm') > 0]
            weights = [get_val(m, 'weight_g') for m in measurements if get_val(m, 'weight_g') > 0]
            
            heights = []
            widths = []
            for m in measurements:
                h = get_val(m, 'manual_height_cm')
                if h <= 0: h = get_val(m, 'height_cm')
                if h > 0: heights.append(h)

                w = get_val(m, 'manual_width_cm')
                if w <= 0: w = get_val(m, 'width_cm')
                if w > 0: widths.append(w)
            
            dates, dates_lengths = [], []
            for m in measurements:
                l = get_val(m, 'length_cm')
                if l > 0:
                    ts_str = get_str(m, 'timestamp')
                    if ts_str:
                        try:
                            dates.append(datetime.fromisoformat(ts_str))
                            dates_lengths.append(l)
                        except: pass
            
            # 4. CONFIGURAR LIENZO
            plt.close('all') 
            fig = plt.figure(figsize=(18, 12), constrained_layout=True)
            # Forzar fondo blanco explícito en la figura
            fig.patch.set_facecolor('white')
            
            gs = fig.add_gridspec(3, 2)
            fig.suptitle(f'Reporte Gráfico de Trazabilidad - {datetime.now().strftime("%d/%m/%Y")}', fontsize=20, fontweight='bold', color='black')
            
            # --- FILA 1 ---
            ax1 = fig.add_subplot(gs[0, 0])
            if lengths:
                ax1.hist(lengths, bins=20, edgecolor='black', color='#3498db', alpha=0.7)
                ax1.axvline(np.mean(lengths), color='red', linestyle='dashed', linewidth=1)
                ax1.set_title(f'Distribución de Longitudes (n={len(lengths)})', fontweight='bold', color='black')
                ax1.set_xlabel('Longitud (cm)', color='black')
                ax1.tick_params(colors='black')

            ax2 = fig.add_subplot(gs[0, 1])
            if weights:
                ax2.hist(weights, bins=20, edgecolor='black', color='#e67e22', alpha=0.7)
                ax2.axvline(np.mean(weights), color='red', linestyle='dashed', linewidth=1)
                ax2.set_title(f'Distribución de Pesos (n={len(weights)})', fontweight='bold', color='black')
                ax2.set_xlabel('Peso (g)', color='black')
                ax2.tick_params(colors='black')

            # --- FILA 2 ---
            ax3 = fig.add_subplot(gs[1, 0])
            if lengths and weights:
                min_len = min(len(lengths), len(weights))
                ax3.scatter(lengths[:min_len], weights[:min_len], alpha=0.6, color='#27ae60', edgecolors='darkgreen')
                ax3.set_title('Relación Peso vs. Longitud', fontweight='bold', color='black')
                ax3.set_xlabel('Longitud (cm)', color='black')
                ax3.set_ylabel('Peso (g)', color='black')
                ax3.grid(True, linestyle='--', alpha=0.5)
                ax3.tick_params(colors='black')

            ax4 = fig.add_subplot(gs[1, 1])
            if len(dates) > 1:
                ax4.plot(dates, dates_lengths, 'o-', color='#8e44ad', markersize=4, alpha=0.8)
                ax4.set_title('Evolución del Crecimiento', fontweight='bold', color='black')
                ax4.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
                plt.setp(ax4.xaxis.get_majorticklabels(), rotation=30)
                ax4.grid(True, alpha=0.3)
                ax4.tick_params(colors='black')

            # --- FILA 3 ---
            ax5 = fig.add_subplot(gs[2, 0])
            if heights:
                ax5.hist(heights, bins=15, edgecolor='black', color='#00ced1', alpha=0.7)
                ax5.axvline(np.mean(heights), color='red', linestyle='dashed', linewidth=1)
                ax5.set_title(f'Distribución de Alturas (n={len(heights)})', fontweight='bold', color='black')
                ax5.set_xlabel('Altura (cm)', color='black')
                ax5.tick_params(colors='black')

            ax6 = fig.add_subplot(gs[2, 1])
            if widths:
                ax6.hist(widths, bins=15, edgecolor='black', color='#ff00ff', alpha=0.7)
                ax6.axvline(np.mean(widths), color='red', linestyle='dashed', linewidth=1)
                ax6.set_title(f'Distribución de Anchos (n={len(widths)})', fontweight='bold', color='black')
                ax6.set_xlabel('Ancho (cm)', color='black')
                ax6.tick_params(colors='black')

            # Guardar
            filename = f'Panel_Estadistico_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            save_path = os.path.join(output_dir, filename)
            
            # Guardamos con facecolor='white' explícitamente
            plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white', transparent=False)
            plt.close(fig)
            
            QMessageBox.information(self, "Éxito", f"Imagen guardada en:\n{save_path}")
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"📊 Gráfico se han generado en:\n{save_path}", "success")
            
        except ImportError:
            QMessageBox.warning(self, "Error", "Falta librería matplotlib.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error exportando imagen:\n{e}")
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"❌ Error generando los gráficos.", "error")
            logger.error(f"Error export statistics: {e}")

    def export_to_csv(self):
        """
        Exporta a CSV leyendo DIRECTAMENTE la estructura real de la Base de Datos.
        Soluciona problemas de columnas desordenadas, datos corridos o campos nuevos.
        """
        # 1. Preparar ruta de guardado
        try:
            from Config import Config
            report_dir = getattr(Config, 'CSV_DIR', os.path.join("Resultados", "CSV"))
        except:
            report_dir = os.path.join("Resultados", "CSV")
            
        os.makedirs(report_dir, exist_ok=True)
        default_name = f"Base_Datos_Full_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        default_path = os.path.join(report_dir, default_name)

        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar CSV", default_path, "CSV Files (*.csv)"
        )
        if not filename: 
            return
        
        conn = None
        try:
            import csv
            import sqlite3
            
            # 2. CONEXIÓN DIRECTA A LA BASE DE DATOS
            conn = sqlite3.connect(self.db.db_path)
            conn.row_factory = sqlite3.Row 
            cursor = conn.cursor()
            
            # 3. OBTENER DATOS Y ESTRUCTURA REAL
            cursor.execute("SELECT * FROM measurements")
            rows = cursor.fetchall()
            
            if not rows:
                QMessageBox.warning(self, "Vacío", "La base de datos está vacía.")
                return

            # 4. DETECTAR NOMBRES DE COLUMNAS AUTOMÁTICAMENTE
            db_column_names = [desc[0] for desc in cursor.description]
            
            # Preparamos encabezados finales (DB + Cálculos Extra)
            final_headers = [name.upper() for name in db_column_names]
            final_headers.append("FACTOR_K_CALCULADO")

            # 5. ESCRIBIR EL ARCHIVO
            # utf-8-sig: Permite que Excel lea correctamente caracteres especiales (ñ, tildes)
            # delimiter=',': Estándar internacional (compatible con Excel, Python, R, etc.)
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=',')
                writer.writerow(final_headers)
                
                for row in rows:
                    # Variables para cálculo de K
                    l_val = 0.0
                    w_val = 0.0
                    cleaned_row = []

                    for col_name, val in zip(db_column_names, row):
                        # Guardar valores para cálculo de Factor K
                        if col_name == 'length_cm' and val:
                            try: 
                                l_val = float(val)
                            except: 
                                pass
                        elif col_name == 'weight_g' and val:
                            try: 
                                w_val = float(val)
                            except: 
                                pass
                        
                        # Limpieza y formato
                        if val is None:
                            cleaned_row.append("")
                        elif isinstance(val, float):
                            # CRÍTICO: Usar punto decimal SIEMPRE para compatibilidad
                            cleaned_row.append(f"{val:.4f}")
                        else:
                            cleaned_row.append(str(val))
                    
                    # --- CÁLCULO FACTOR K ---
                    # K = 100 * W / L³
                    k_factor = 0.0
                    if l_val > 0:
                        k_factor = (100 * w_val) / (l_val ** 3)
                    
                    cleaned_row.append(f"{k_factor:.4f}")
                    writer.writerow(cleaned_row)

            QMessageBox.information(
                self, "Éxito", 
                f"✅ Base de datos exportada correctamente:\n{filename}\n\n"
                f"📊 Total de registros: {len(rows)}"
            )
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"📊 CSV se ha generado en:\n{filename}", "success")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error crítico al exportar:\n{e}")
            logger.error(f"Error CSV Directo: {e}", exc_info=True)
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"❌ Error generando el CSV.", "error")
        finally:
            if conn: 
                conn.close()
            
    def export_stats_pdf(self):
        """
        Genera un REPORTE CIENTÍFICO COMPLETO:
        - Resumen Estadístico (Tablas)
        - Gráficos HD (Matplotlib)
        - Tabla de Datos (Últimos registros)
        """
        # 1. Configurar directorio de reportes (ANTES del diálogo)
        try:
            from Config import Config
            report_dir = getattr(Config, 'REPORTS_DIR', os.path.join("Resultados", "Reportes"))
        except:
            report_dir = os.path.join("Resultados", "Reportes")
        
        os.makedirs(report_dir, exist_ok=True)
        
        # 2. Diálogo de guardado
        default_name = f"Informe_Trazabilidad_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        default_path = os.path.join(report_dir, default_name)
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Informe Completo", default_path, "PDF Files (*.pdf)"
        )
        if not path: 
            return

        # 3. Obtener datos (Mapeo Seguro)
        measurements = self.db.get_filtered_measurements(limit=2000)
        if not measurements:
            QMessageBox.warning(self, "Sin Datos", "No hay registros para generar el informe.")
            return

        # Directorio temporal para gráficos (evitar conflictos)
        temp_plots_dir = os.path.join(report_dir, "_temp_plots")
        os.makedirs(temp_plots_dir, exist_ok=True)

        try:
            import matplotlib.pyplot as plt
            import numpy as np
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
            from reportlab.lib import colors
            from BasedeDatos.DatabaseManager import MEASUREMENT_COLUMNS
                        
            # --- MAPEO SEGURO DE DATOS ---
            col_map = {col: i for i, col in enumerate(MEASUREMENT_COLUMNS)}
            
            def get_val(m, field, default=0.0):
                if field in col_map:
                    idx = col_map[field]
                    if idx < len(m):
                        v = m[idx]
                        if v is None or v == "": return default
                        try: return float(v)
                        except: return default
                return default

            def get_str(m, field):
                if field in col_map:
                    idx = col_map[field]
                    if idx < len(m): return str(m[idx]) if m[idx] else ""
                return ""

            # Extraer listas limpias para estadísticas
            lengths = [get_val(m, 'length_cm') for m in measurements if get_val(m, 'length_cm') > 0]
            weights = [get_val(m, 'weight_g') for m in measurements if get_val(m, 'weight_g') > 0]
            heights = []
            widths = []
            
            # Lógica de prioridad manual/auto
            for m in measurements:
                h = get_val(m, 'manual_height_cm')
                if h <= 0: h = get_val(m, 'height_cm')
                if h > 0: heights.append(h)
                
                w = get_val(m, 'manual_width_cm')
                if w <= 0: w = get_val(m, 'width_cm')
                if w > 0: widths.append(w)

            # 4. CONFIGURACIÓN DEL DOCUMENTO PDF
            doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            styles = getSampleStyleSheet()
            
            # Estilos personalizados
            title_style = ParagraphStyle('MainTitle', parent=styles['Title'], fontSize=18, alignment=TA_CENTER, spaceAfter=10, textColor=colors.HexColor('#2c3e50'))
            subtitle_style = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, textColor=colors.HexColor('#7f8c8d'))
            h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=14, spaceBefore=15, spaceAfter=10, textColor=colors.HexColor('#2980b9'))
            normal_style = styles['Normal']
            
            elements = []

            # --- ENCABEZADO ---
            elements.append(Paragraph("INFORME TÉCNICO DE TRAZABILIDAD", title_style))
            elements.append(Paragraph(f"Proyecto LESTOMA - Laboratorio de Biometría", subtitle_style))
            elements.append(Paragraph(f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}", subtitle_style))
            elements.append(Spacer(1, 20))

            # --- SECCIÓN 1: RESUMEN ESTADÍSTICO (TABLA) ---
            elements.append(Paragraph("1. Resumen Estadístico Descriptivo", h2_style))
            
            # Función auxiliar para calcular fila de tabla
            def calc_row(name, data, unit):
                if not data: return [name, "0", "-", "-", "-", "-"]
                return [
                    name,
                    str(len(data)),
                    f"{np.mean(data):.2f} {unit}",
                    f"{np.min(data):.2f} {unit}",
                    f"{np.max(data):.2f} {unit}",
                    f"{np.std(data):.2f}"
                ]

            table_data = [
                ['Variable', 'N', 'Promedio', 'Mínimo', 'Máximo', 'Desv. Est.']
            ]
            table_data.append(calc_row("Longitud", lengths, "cm"))
            table_data.append(calc_row("Peso", weights, "g"))
            table_data.append(calc_row("Altura", heights, "cm"))
            table_data.append(calc_row("Ancho", widths, "cm"))

            # Estilo de la tabla
            t = Table(table_data, colWidths=[100, 50, 90, 90, 90, 70])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), (-1, -1), 1, colors.white),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor('#e8e8e8')])
            ]))
            elements.append(t)
            elements.append(Spacer(1, 25))

            # --- SECCIÓN 2: ANÁLISIS GRÁFICO ---
            elements.append(Paragraph("2. Análisis Gráfico (Distribuciones)", h2_style))
            
            # Configurar Matplotlib
            plt.style.use('default')
            plt.rcParams.update({'font.size': 9})

            def add_plot(data, title, xlabel, color, suffix):
                if not data: return
                fig, ax = plt.subplots(figsize=(7, 3.5), dpi=300)
                ax.hist(data, bins=20, color=color, alpha=0.75, edgecolor='black', linewidth=0.5)
                ax.axvline(np.mean(data), color='red', linestyle='--', linewidth=1, label='Media')
                ax.set_title(title, fontweight='bold', fontsize=10)
                ax.set_xlabel(xlabel)
                ax.set_ylabel("Frecuencia")
                ax.grid(True, linestyle=':', alpha=0.5)
                ax.legend()
                
                fpath = os.path.join(temp_plots_dir, f"p_{suffix}.png")
                plt.savefig(fpath, bbox_inches='tight')
                plt.close(fig)
                elements.append(Image(fpath, width=450, height=225))
                elements.append(Spacer(1, 10))

            add_plot(lengths, "Distribución de Longitudes", "cm", "#3498db", "len")
            add_plot(weights, "Distribución de Pesos", "g", "#e67e22", "wgt")
            
            # Correlación (Si hay datos)
            if lengths and weights:
                elements.append(Spacer(1, 10))
                fig, ax = plt.subplots(figsize=(7, 3.5), dpi=300)
                min_len = min(len(lengths), len(weights))
                ax.scatter(lengths[:min_len], weights[:min_len], alpha=0.6, c='#27ae60', edgecolors='black', s=20)
                ax.set_title("Relación Longitud vs. Peso")
                ax.set_xlabel("Longitud (cm)")
                ax.set_ylabel("Peso (g)")
                ax.grid(True, alpha=0.3)
                fpath = os.path.join(temp_plots_dir, "p_corr.png")
                plt.savefig(fpath, bbox_inches='tight')
                plt.close(fig)
                elements.append(Image(fpath, width=450, height=225))

            elements.append(PageBreak())

            # --- SECCIÓN 3: REGISTRO DE DATOS (TABLA DE MUESTRA) ---
            elements.append(Paragraph("3. Registro Detallado (Últimos 50)", h2_style))
            
            data_rows = [['ID', 'Fecha/Hora', 'Largo (cm)', 'Peso (g)', 'Altura (cm)', 'Ancho (cm)']]
            
            sorted_measurements = sorted(measurements, key=lambda x: get_str(x, 'timestamp'), reverse=True)[:50]

            for m in sorted_measurements:
                l = get_val(m, 'length_cm')
                w = get_val(m, 'weight_g')
                
                h = get_val(m, 'manual_height_cm')
                if h <= 0: h = get_val(m, 'height_cm')
                
                wid = get_val(m, 'manual_width_cm')
                if wid <= 0: wid = get_val(m, 'width_cm')

                ts = get_str(m, 'timestamp')
                try: ts_short = ts.split("T")[0]
                except: ts_short = ts

                fish_id = get_str(m, 'fish_id')

                data_rows.append([
                    str(fish_id),
                    ts_short,
                    f"{l:.2f}",
                    f"{w:.2f}" if w > 0 else "-",
                    f"{h:.2f}" if h > 0 else "-",
                    f"{wid:.2f}" if wid > 0 else "-"
                ])

            t_data = Table(data_rows, colWidths=[60, 90, 70, 70, 70, 70])
            t_data.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2980b9')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2f2')])
            ]))
            elements.append(t_data)
            
            elements.append(Spacer(1, 20))
            elements.append(Paragraph("Nota: Esta tabla muestra solo los últimos 50 registros para optimizar el tamaño del reporte.", subtitle_style))

            # 5. GENERAR PDF
            doc.build(elements)
            
            # 6. Limpiar archivos temporales DESPUÉS de generar el PDF
            try:
                import shutil
                shutil.rmtree(temp_plots_dir)
            except: 
                pass

            QMessageBox.information(
                self, "Informe Creado", 
                f"✅ El informe completo se ha generado en:\n{path}"
            )
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"📊 Informe completo se ha generado en:\n{path}", "success")

        except ImportError as ie:
            QMessageBox.critical(
                self, "Error", 
                f"Falta librería requerida.\n\nInstala con:\npip install reportlab matplotlib numpy"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error crítico generando PDF:\n{e}")
            logger.error(f"PDF Error: {e}", exc_info=True)
            if hasattr(self, 'status_bar'):
                self.status_bar.set_status(f"❌ Error generando el PDF.", "error")

        finally:
            # Asegurar limpieza incluso si hay errores
            try:
                import shutil
                if os.path.exists(temp_plots_dir):
                    shutil.rmtree(temp_plots_dir)
            except:
                pass
             
    def generate_statistics(self):
        """
        🚀 MOTOR ANALÍTICO: Procesa datos y genera el Dashboard visual.
        """
        if hasattr(self, 'stats_text'):
            self.stats_text.clear()
        if hasattr(self, 'gallery_list'):
            self.gallery_list.clear()
        
        # 1. Obtención de datos con Mapeo Dinámico
        measurements = self.db.get_filtered_measurements(limit=2000)
        
        if not measurements:
            self.stats_text.setHtml("<h3 style='color:#e74c3c; text-align:center;'>⚠️ No hay registros para analizar.</h3>")
            return

        # 2. Extracción segura (Prevención de errores de tipo)
        lengths, weights, dates, dates_lengths = [], [], [], []
        
        for m in measurements:
            try:
                # Extraemos forzando el tipo float para cálculos matemáticos
                l = float(self.db.get_field_value(m, 'length_cm', 0))
                w = float(self.db.get_field_value(m, 'weight_g', 0))
                ts = self.db.get_field_value(m, 'timestamp', "")

                if l > 0:
                    lengths.append(l)
                    if ts:
                        try:
                            dates.append(datetime.fromisoformat(str(ts)))
                            dates_lengths.append(l)
                        except: pass
                if w > 0:
                    weights.append(w)
            except: continue 

        # 3. Guardar estado para persistencia en el reporte
        self.current_stats_data = {
            'count': len(measurements),
            'lengths': lengths,
            'weights': weights,
            'dates': dates,
            'dates_lengths': dates_lengths,
            'heights': [l*0.3 for l in lengths], 
            'widths': [l*0.15 for l in lengths]   
        }

        # 4. Actualizar Visuales
        self.update_report_html()
        self.generate_graphs()
        if hasattr(self, 'status_bar'):
            self.status_bar.set_status(f"📊 Análisis de {len(measurements)} muestras completado", "success")
        
    def update_report_html(self):
        """Genera un reporte con diseño de Dashboard Corporativo"""
        if not hasattr(self, 'current_stats_data'): return

        d = self.current_stats_data
        style = self.report_style

        html = f"""
            <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                background-color: {style['bg']};
                color: {style['text']};
            }}

            .card {{
                border: 1px solid {style['border']};
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                background-color: {style['bg']};
            }}

            .title {{
                color: {style['header']};
                font-size: 18px;
                font-weight: bold;
                border-bottom: 2px solid {style['accent']};
                margin-bottom: 6px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}

            td {{
                padding: 8px;
                border-bottom: 1px solid {style['border']};
            }}

            tr.section td {{
                background-color: {style['row']};
                font-weight: bold;
            }}

            .val {{
                font-weight: bold;
                color: {style['val_color']};
                text-align: right;
            }}

            .badge {{
                background: {style['accent']};
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 11px;
            }}
        </style>
        <div class='card'>
            <span class='badge'>REPORTE OFICIAL</span>
            <div class='title'>Dashboard de Trazabilidad Biométrica</div>
            <p style='font-size: 11px;'>Muestras procesadas: <b>{d['count']}</b> | Fecha: {datetime.now().strftime('%d/%m/%Y')}</p>
            
            <table>
                <tr class="section">
                    <td colspan="2">📏 Biometría Longitudinal (cm)</td>
                </tr>
                <tr><td>Promedio de Talla</td><td class='val'>{np.mean(d['lengths']):.2f} cm</td></tr>
                <tr><td>Desviación Estándar</td><td class='val'>±{np.std(d['lengths']):.2f}</td></tr>
                
                <tr class="section">
                    <td colspan="2">⚖️ Análisis de Masa (g)</td>
                </tr>
                <tr><td>Peso Promedio</td><td class='val'>{np.mean(d['weights']):.2f} g</td></tr>
                <tr><td>Biomasa Total Estimada</td><td class='val'>{np.sum(d['weights'])/1000:.2f} kg</td></tr>
            </table>
        </div>
        """
        self.stats_text.setHtml(html)
        
    def generate_graphs(self):
        """Genera los 4 gráficos principales para la galería."""
        self.gallery_list.clear()
        if not hasattr(self, 'current_stats_data') or not self.current_stats_data:
            return

        data = self.current_stats_data
        plt.style.use('default')

        # 1. Histograma Longitudes
        if data['lengths']:
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.hist(data['lengths'], bins=15, color='#3498db', edgecolor='black', alpha=0.7)
            ax.set_title("Distribución de Longitudes")
            self.add_graph_to_gallery(fig, "Longitudes")
            plt.close(fig)

        # 2. Histograma Pesos
        if data['weights']:
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.hist(data['weights'], bins=15, color='#e67e22', edgecolor='black', alpha=0.7)
            ax.set_title("Distribución de Pesos")
            self.add_graph_to_gallery(fig, "Pesos")
            plt.close(fig)

        # 3. Correlación
        if data['lengths'] and data['weights']:
            fig, ax = plt.subplots(figsize=(5, 4))
            min_len = min(len(data['lengths']), len(data['weights']))
            ax.scatter(data['lengths'][:min_len], data['weights'][:min_len], color='#27ae60', alpha=0.6)
            ax.set_title("Relación Peso vs Largo")
            self.add_graph_to_gallery(fig, "Correlación")
            plt.close(fig)

        # 4. Línea de Tiempo
        if len(data['dates']) > 1:
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.plot(data['dates'], data['dates_lengths'], marker='o', color='#8e44ad')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30)
            fig.tight_layout()
            self.add_graph_to_gallery(fig, "Evolución Temporal")
            plt.close(fig)
 
    
    
    def save_config(self):
        Config.CAM_LEFT_INDEX = self.spin_cam_left.value()
        Config.CAM_TOP_INDEX = self.spin_cam_top.value()
        Config.MIN_CONTOUR_AREA = self.spin_min_area.value()
        Config.MAX_CONTOUR_AREA = self.spin_max_area.value()
        Config.CONFIDENCE_THRESHOLD = self.spin_confidence.value()
        Config.MIN_LENGTH_CM = self.spin_min_length.value()
        Config.MAX_LENGTH_CM = self.spin_max_length.value()

        # 2. Preparar Diccionarios para JSON y BD
        hsv_left = {
            'h_min': self.spin_hue_min_lat.value(), 'h_max': self.spin_hue_max_lat.value(),
            's_min': self.spin_sat_min_lat.value(), 's_max': self.spin_sat_max_lat.value(),
            'v_min': self.spin_val_min_lat.value(), 'v_max': self.spin_val_max_lat.value()
        }
        
        hsv_top = {
            'h_min': self.spin_hue_min_top.value(), 'h_max': self.spin_hue_max_top.value(),
            's_min': self.spin_sat_min_top.value(), 's_max': self.spin_sat_max_top.value(),
            'v_min': self.spin_val_min_top.value(), 'v_max': self.spin_val_max_top.value()
        }

        config_data = {
            'cam_left_index': Config.CAM_LEFT_INDEX,
            'cam_top_index': Config.CAM_TOP_INDEX,
            'min_contour_area': Config.MIN_CONTOUR_AREA,
            'max_contour_area': Config.MAX_CONTOUR_AREA,
            'confidence_threshold': Config.CONFIDENCE_THRESHOLD,
            'min_length_cm': Config.MIN_LENGTH_CM,
            'max_length_cm': Config.MAX_LENGTH_CM,
            'scale_front_left': self.scale_front_left,
            'scale_back_left': self.scale_back_left,
            'scale_front_top': self.scale_front_top,
            'scale_back_top': self.scale_back_top,
            'hsv_left': hsv_left,  
            'hsv_top': hsv_top
        }
        
        # Guardar en BD
        self.db.save_calibration(
            scale_lat_front=self.scale_front_left,
            scale_lat_back=self.scale_back_left,
            scale_top_front=self.scale_front_top,
            scale_top_back=self.scale_back_top,
            hsv_left=hsv_left,
            hsv_top=hsv_top,
            notes="Guardado desde GUI principal"
        )
        
        try:
            with open(Config.CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=4)
            
            self.status_bar.set_status("💾 Configuración guardada en disco y BD", "success")
            QMessageBox.information(self, "Éxito", "Configuración y Calibración guardadas correctamente.")
        except Exception as e:
            logger.error(f"Error escribiendo config.json: {e}")

    def load_config(self):
        """Carga la configuración siguiendo la jerarquía: Config.py -> config.json -> Base de Datos"""
        
        # 1. Valores Base (Config.py)
        self._load_base_values()

        # 2. Sobrescribir con config.json (Preferencias locales)
        if os.path.exists(Config.CONFIG_FILE):
            try:
                with open(Config.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self._parse_json_config(data)
                logger.info("Configuración cargada desde JSON.")
            except Exception as e:
                logger.error(f"Error en JSON: {e}")

        # 3. Sobrescribir con lo ÚLTIMO de la Base de Datos (Calibración más reciente)
        try:
            last_calib = self.db.get_latest_calibration()
            if last_calib:
                self._parse_db_calibration(last_calib)
                logger.info("Calibración final sincronizada con la Base de Datos.")
        except Exception as e:
            logger.warning(f"No se pudo acceder a la BD para calibración: {e}")

    def _load_base_values(self):
        """Inicializa las variables internas con valores seguros de Config.py"""
        # Escalas base
        self.scale_front_left = getattr(Config, 'SCALE_LAT_FRONT', 0.006666)
        self.scale_back_left  = getattr(Config, 'SCALE_LAT_BACK', 0.014926)
        self.scale_front_top  = getattr(Config, 'SCALE_TOP_FRONT', 0.004348)
        self.scale_back_top   = getattr(Config, 'SCALE_TOP_BACK', 0.012582)
        
        # HSV Lateral Base
        self.hsv_left_h_min = getattr(Config, 'HSV_H_MIN', 35)
        self.hsv_left_h_max = getattr(Config, 'HSV_H_MAX', 85)
        self.hsv_left_s_min = getattr(Config, 'HSV_S_MIN', 40)
        self.hsv_left_s_max = getattr(Config, 'HSV_S_MAX', 255)
        self.hsv_left_v_min = getattr(Config, 'HSV_V_MIN', 40)
        self.hsv_left_v_max = getattr(Config, 'HSV_V_MAX', 255)
        
        # HSV Cenital Base (Copiamos los mismos por defecto)
        self.hsv_top_h_min, self.hsv_top_h_max = self.hsv_left_h_min, self.hsv_left_h_max
        self.hsv_top_s_min, self.hsv_top_s_max = self.hsv_left_s_min, self.hsv_left_s_max
        self.hsv_top_v_min, self.hsv_top_v_max = self.hsv_left_v_min, self.hsv_left_v_max
        
        logger.info("Valores base inicializados desde memoria.")
        
    def sync_ui_with_config(self):
        """
        Sincroniza los widgets de la interfaz con las variables cargadas.
        Se debe llamar SOLO DESPUÉS de initUI().
        """
        logger.info("Sincronizando widgets con la configuración...")
        
        # Agrupamos widgets para bloquear sus señales temporalmente
        widgets_to_sync = [
            self.spin_cam_left, self.spin_cam_top,
            self.spin_min_area, self.spin_max_area,
            self.spin_confidence, self.spin_min_length, self.spin_max_length,
            self.spin_scale_front_left, self.spin_scale_back_left,
            self.spin_scale_front_top, self.spin_scale_back_top,
            self.spin_hue_min_lat, self.spin_hue_max_lat,
            self.spin_sat_min_lat, self.spin_sat_max_lat,
            self.spin_val_min_lat, self.spin_val_max_lat,
            self.spin_hue_min_top, self.spin_hue_max_top,
            self.spin_sat_min_top, self.spin_sat_max_top,
            self.spin_val_min_top, self.spin_val_max_top
        ]

        for w in widgets_to_sync:
            w.blockSignals(True)

        try:
            # --- Configuración General ---
            self.spin_cam_left.setValue(Config.CAM_LEFT_INDEX)
            self.spin_cam_top.setValue(Config.CAM_TOP_INDEX)
            self.spin_min_area.setValue(Config.MIN_CONTOUR_AREA)
            self.spin_max_area.setValue(Config.MAX_CONTOUR_AREA)
            self.spin_confidence.setValue(Config.CONFIDENCE_THRESHOLD)

            # --- Escalas de Fotogrametría ---
            self.spin_scale_front_left.setValue(self.scale_front_left)
            self.spin_scale_back_left.setValue(self.scale_back_left)
            self.spin_scale_front_top.setValue(self.scale_front_top)
            self.spin_scale_back_top.setValue(self.scale_back_top)

            # --- Chroma Key Lateral ---
            self.spin_hue_min_lat.setValue(self.hsv_left_h_min)
            self.spin_hue_max_lat.setValue(self.hsv_left_h_max)
            self.spin_sat_min_lat.setValue(self.hsv_left_s_min)
            self.spin_sat_max_lat.setValue(self.hsv_left_s_max)
            self.spin_val_min_lat.setValue(self.hsv_left_v_min)
            self.spin_val_max_lat.setValue(self.hsv_left_v_max)

            # --- Chroma Key Cenital ---
            self.spin_hue_min_top.setValue(self.hsv_top_h_min)
            self.spin_hue_max_top.setValue(self.hsv_top_h_max)
            self.spin_sat_min_top.setValue(self.hsv_top_s_min)
            self.spin_sat_max_top.setValue(self.hsv_top_s_max)
            self.spin_val_min_top.setValue(self.hsv_top_v_min)
            self.spin_val_max_top.setValue(self.hsv_top_v_max)

            self.status_bar.set_status("✅ Interfaz sincronizada con éxito", "success")

        except Exception as e:
            logger.error(f"Error sincronizando UI: {e}")
        
        finally:
            # Desbloquear señales para que el usuario pueda interactuar
            for w in widgets_to_sync:
                w.blockSignals(False)   
              
    def _parse_json_config(self, data):
        """Mapea el JSON plano a las variables de la instancia"""
        try:
            # 1. Configuración de Cámaras e IA
            Config.CAM_LEFT_INDEX = data.get('cam_left_index', Config.CAM_LEFT_INDEX)
            Config.CAM_TOP_INDEX = data.get('cam_top_index', Config.CAM_TOP_INDEX)
            Config.MIN_CONTOUR_AREA = data.get('min_contour_area', Config.MIN_CONTOUR_AREA)
            Config.MAX_CONTOUR_AREA = data.get('max_contour_area', Config.MAX_CONTOUR_AREA)
            Config.CONFIDENCE_THRESHOLD = data.get('confidence_threshold', Config.CONFIDENCE_THRESHOLD)
            Config.MIN_LENGTH_CM = data.get('min_length_cm', Config.MIN_LENGTH_CM)
            Config.MAX_LENGTH_CM = data.get('max_length_cm', Config.MAX_LENGTH_CM)

            # 2. Escalas Fotogramétricas
            self.scale_front_left = data.get('scale_front_left', self.scale_front_left)
            self.scale_back_left = data.get('scale_back_left', self.scale_back_left)
            self.scale_front_top = data.get('scale_front_top', self.scale_front_top)
            self.scale_back_top = data.get('scale_back_top', self.scale_back_top)

            # 3. HSV (Se aplica a ambos por defecto si el JSON es plano)
            if 'hsv_left' in data:
                h = data['hsv_left']
                self.hsv_left_h_min = h.get('h_min', 35)
                self.hsv_left_h_max = h.get('h_max', 85)
                self.hsv_left_s_min = h.get('s_min', 40)
                self.hsv_left_s_max = h.get('s_max', 255)
                self.hsv_left_v_min = h.get('v_min', 40)
                self.hsv_left_v_max = h.get('v_max', 255)

            # 4. HSV DUAL (Cenital)
            if 'hsv_top' in data:
                h = data['hsv_top']
                self.hsv_top_h_min = h.get('h_min', 35)
                self.hsv_top_h_max = h.get('h_max', 85)
                self.hsv_top_s_min = h.get('s_min', 40)
                self.hsv_top_s_max = h.get('s_max', 255)
                self.hsv_top_v_min = h.get('v_min', 40)
                self.hsv_top_v_max = h.get('v_max', 255)
            
        except Exception as e:
            logger.error(f"Error parseando JSON: {e}")                
                       
    def _parse_db_calibration(self, calib):
        """Mapea la fila de la BD a las variables de la instancia (Dual-Chroma)"""
        if not calib: return

        try:
            # 1. Escalas (Directo de las columnas de la tabla)
            self.scale_front_left = calib.get('scale_lat_front', self.scale_front_left)
            self.scale_back_left = calib.get('scale_lat_back', self.scale_back_left)
            self.scale_front_top = calib.get('scale_top_front', self.scale_front_top)
            self.scale_back_top = calib.get('scale_top_back', self.scale_back_top)

            # 2. HSV Lateral (Si los guardaste como diccionarios/objetos en la BD)
            if 'hsv_left' in calib and isinstance(calib['hsv_left'], dict):
                h = calib['hsv_left']
                self.hsv_left_h_min = h.get('h_min', self.hsv_left_h_min)
                self.hsv_left_h_max = h.get('h_max', self.hsv_left_h_max)
                self.hsv_left_s_min = h.get('s_min', self.hsv_left_s_min)
                self.hsv_left_s_max = h.get('s_max', self.hsv_left_s_max)
                self.hsv_left_v_min = h.get('v_min', self.hsv_left_v_min)
                self.hsv_left_v_max = h.get('v_max', self.hsv_left_v_max)

            # 3. HSV Cenital
            if 'hsv_top' in calib and isinstance(calib['hsv_top'], dict):
                h = calib['hsv_top']
                self.hsv_top_h_min = h.get('h_min', self.hsv_top_h_min)
                self.hsv_top_h_max = h.get('h_max', self.hsv_top_h_max)
                self.hsv_top_s_min = h.get('s_min', self.hsv_top_s_min)
                self.hsv_top_s_max = h.get('s_max', self.hsv_top_s_max)
                self.hsv_top_v_min = h.get('v_min', self.hsv_top_v_min)
                self.hsv_top_v_max = h.get('v_max', self.hsv_top_v_max)

        except Exception as e:
            logger.error(f"Error parseando Calibración de BD: {e}")
            
    def open_fine_tune_calibration(self):
        """
        CALIBRACIÓN INDEPENDIENTE POR CÁMARA CON VISTA PREVIA SEGURA
        """
        if not self.cap_left or not self.cap_top:
            QMessageBox.warning(self, "Error", "Cámaras no disponibles")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Calibración Chroma Key en Vivo")
        dialog.setMinimumSize(1400, 900)
        layout = QVBoxLayout(dialog)

        # 1. Cargar valores temporales (clonados de la configuración actual)
        self.temp_hsv_left = {
            'h_min': getattr(self, 'hsv_left_h_min', self.spin_hue_min_lat.value()),
            'h_max': getattr(self, 'hsv_left_h_max', self.spin_hue_max_lat.value()),
            's_min': getattr(self, 'hsv_left_s_min', self.spin_sat_min_lat.value()),
            's_max': getattr(self, 'hsv_left_s_max', self.spin_sat_max_lat.value()),
            'v_min': getattr(self, 'hsv_left_v_min', self.spin_val_min_lat.value()),
            'v_max': getattr(self, 'hsv_left_v_max', self.spin_val_max_lat.value())
        }
        
        self.temp_hsv_top = {
            'h_min': getattr(self, 'hsv_top_h_min', self.spin_hue_min_top.value()),
            'h_max': getattr(self, 'hsv_top_h_max', self.spin_hue_max_top.value()),
            's_min': getattr(self, 'hsv_top_s_min', self.spin_sat_min_top.value()),
            's_max': getattr(self, 'hsv_top_s_max', self.spin_sat_max_top.value()),
            'v_min': getattr(self, 'hsv_top_v_min', self.spin_val_min_top.value()),
            'v_max': getattr(self, 'hsv_top_v_max', self.spin_val_max_top.value())
        }

        # 2. Interfaz de Video
        grid_layout = QGridLayout()
        
        def create_video_block(title):
            lbl_title = QLabel(f"<b>{title}</b>")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            raw = QLabel()
            raw.setFixedSize(650, 380)
            raw.setStyleSheet("background-color: black; border: 2px solid #333;")
            raw.setCursor(Qt.CursorShape.CrossCursor)
            mask = QLabel()
            mask.setFixedSize(650, 380)
            mask.setStyleSheet("background-color: black; border: 2px solid #333;")
            return lbl_title, raw, mask

        t1, lbl_left_raw, lbl_left_mask = create_video_block("Cámara Lateral (Click para capturar color)")
        t2, lbl_top_raw, lbl_top_mask = create_video_block("Cámara Cenital (Click para capturar color)")

        grid_layout.addWidget(t1, 0, 0)
        grid_layout.addWidget(lbl_left_raw, 1, 0)
        grid_layout.addWidget(QLabel("Máscara Lateral"), 2, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(lbl_left_mask, 3, 0)

        grid_layout.addWidget(t2, 0, 1)
        grid_layout.addWidget(lbl_top_raw, 1, 1)
        grid_layout.addWidget(QLabel("Máscara Cenital"), 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        grid_layout.addWidget(lbl_top_mask, 3, 1)

        layout.addLayout(grid_layout)

        # 3. Lógica de captura de color al hacer click
        def capture_color(event, is_lateral=True):
            frame = self.current_frame_left if is_lateral else self.current_frame_top
            if frame is None: return
            
            # Mapeo de coordenadas del click al tamaño real del frame
            x = int(event.pos().x() * frame.shape[1] / 650)
            y = int(event.pos().y() * frame.shape[0] / 380)
            
            if 0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]:
                pixel_hsv = cv2.cvtColor(np.uint8([[frame[y, x]]]), cv2.COLOR_BGR2HSV)[0][0]
                target = self.temp_hsv_left if is_lateral else self.temp_hsv_top
                
                # Ajuste automático de rango alrededor del pixel tocado
                target['h_min'] = max(0, int(pixel_hsv[0]) - 12)
                target['h_max'] = min(179, int(pixel_hsv[0]) + 12)
                target['s_min'] = max(30, int(pixel_hsv[1]) - 50)
                target['v_min'] = max(30, int(pixel_hsv[2]) - 50)
                target['s_max'] = 255
                target['v_max'] = 255
                
                self.status_bar.set_status(f"🎯 Color capturado en {'Lateral' if is_lateral else 'Cenital'}", "info")

        lbl_left_raw.mousePressEvent = lambda e: capture_color(e, True)
        lbl_top_raw.mousePressEvent = lambda e: capture_color(e, False)
        
        # 4. Timer de actualización (Uso de display_frame estándar)
        timer = QTimer(dialog)
        
        def update_preview():
            # Procesar Cámara Lateral
            if self.cap_left and self.cap_left.isOpened():
                ret, frame = self.cap_left.read()
                if ret:
                    self.current_frame_left = frame.copy()
                    # Aplicar máscara con valores temporales
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    lower = np.array([self.temp_hsv_left['h_min'], self.temp_hsv_left['s_min'], self.temp_hsv_left['v_min']])
                    upper = np.array([self.temp_hsv_left['h_max'], self.temp_hsv_left['s_max'], self.temp_hsv_left['v_max']])
                    mask = cv2.bitwise_not(cv2.inRange(hsv, lower, upper))
                    
                    self.display_frame(frame, lbl_left_raw)
                    self.display_frame(mask, lbl_left_mask, is_mask=True)

            # Procesar Cámara Cenital
            if self.cap_top and self.cap_top.isOpened():
                ret, frame = self.cap_top.read()
                if ret:
                    self.current_frame_top = frame.copy()
                    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    lower = np.array([self.temp_hsv_top['h_min'], self.temp_hsv_top['s_min'], self.temp_hsv_top['v_min']])
                    upper = np.array([self.temp_hsv_top['h_max'], self.temp_hsv_top['s_max'], self.temp_hsv_top['v_max']])
                    mask = cv2.bitwise_not(cv2.inRange(hsv, lower, upper))
                    
                    self.display_frame(frame, lbl_top_raw)
                    self.display_frame(mask, lbl_top_mask, is_mask=True)

        timer.timeout.connect(update_preview)
        # 100ms es un balance seguro para evitar el error "Painter not active"
        timer.start(120) 
        
        # Detener timer al cerrar diálogo (CRUCIAL)
        dialog.finished.connect(timer.stop)

        # 5. Botones de Acción
        btns = QHBoxLayout()
        
        btn_reset = QPushButton("Restaurar Fábrica")
        btn_reset.setProperty("class", "warning")
        btn_reset.setToolTip("Cancelar la calibración actual.")
        btn_reset.clicked.connect(lambda: reset_values())
        
        def reset_values():
            default = {'h_min': 35, 'h_max': 85, 's_min': 40, 's_max': 255, 'v_min': 40, 'v_max': 255}
            self.temp_hsv_left = default.copy()
            self.temp_hsv_top = default.copy()
            self.status_bar.set_status("Valores reseteados", "info")

        btn_save = QPushButton("Guardar y Aplicar")
        btn_save.setProperty("class", "success")
        btn_save.setToolTip("Guardar los datos actuales en la base de datos.")
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(lambda: save_and_close())

        def save_and_close():
            # Sincronizar con variables globales de la clase
            # Lateral
            self.hsv_left_h_min = self.temp_hsv_left['h_min']
            self.hsv_left_h_max = self.temp_hsv_left['h_max']
            self.hsv_left_s_min = self.temp_hsv_left['s_min']
            self.hsv_left_s_max = self.temp_hsv_left['s_max']
            self.hsv_left_v_min = self.temp_hsv_left['v_min']
            self.hsv_left_v_max = self.temp_hsv_left['v_max']
            # Cenital
            self.hsv_top_h_min = self.temp_hsv_top['h_min']
            self.hsv_top_h_max = self.temp_hsv_top['h_max']
            self.hsv_top_s_min = self.temp_hsv_top['s_min']
            self.hsv_top_s_max = self.temp_hsv_top['s_max']
            self.hsv_top_v_min = self.temp_hsv_top['v_min']
            self.hsv_top_v_max = self.temp_hsv_top['v_max']

            # Actualizar SpinBoxes de la UI principal
            if hasattr(self, 'sync_ui_with_config'):
                self.sync_ui_with_config()
            
            # Guardar en archivo JSON para persistencia
            self.save_config() # Asumo que tienes este método o usa tu lógica de json.dump
            
            timer.stop()
            dialog.accept()
            self.status_bar.set_status("✅ Calibración dual aplicada", "success")

        btns.addWidget(btn_reset)
        btns.addStretch()
        btns.addWidget(btn_save)
        layout.addLayout(btns)

        dialog.exec()