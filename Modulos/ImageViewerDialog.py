"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Visor y Auditoría de Imágenes (ImageViewerDialog.py)
DESCRIPCIÓN: Interfaz gráfica especializada para la inspección forense de capturas.
             Permite visualizar pares estéreos, consultar la ficha técnica del espécimen
             y ejecutar re-análisis de IA bajo demanda para corregir datos históricos.
"""

import cv2
import os
import numpy as np
import logging
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QGroupBox, QMessageBox, QDialog, QSizePolicy)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QImage, QDesktopServices

from BasedeDatos.DatabaseManager import DatabaseManager 
from Config.Config import Config
from .MeasurementValidator import MeasurementValidator 
from .BiometryService import BiometryService

logger = logging.getLogger(__name__)

class ImageViewerDialog(QDialog):
    def __init__(self, image_path_combined, measurement_info, advanced_detector, 
                 scale_lat_front, scale_lat_back, scale_top_front, scale_top_back, parent=None, on_update_callback=None, report_style=None):
        super().__init__(parent)
        self.report_style = report_style 
        
        self.image_path_combined = image_path_combined
        self.measurement_info = measurement_info 
        self.advanced_detector = advanced_detector
        self.on_update_callback = on_update_callback

        self.scale_lat_front = scale_lat_front
        self.scale_lat_back = scale_lat_back
        self.scale_top_front = scale_top_front
        self.scale_top_back = scale_top_back

        self.setWindowTitle("Auditoría Biométrica")
        self.setModal(True)

        self.db_manager = DatabaseManager() 
        self.info_label = None 

        self.original_image = None
        self.image_lateral = None
        self.image_top = None
        self.is_dual_format = False 
        
        if os.path.exists(self.image_path_combined):
            self.original_image = cv2.imread(self.image_path_combined)

        if self.original_image is None:
            QMessageBox.critical(self, "Error", "No se pudo cargar la imagen.")
            self.reject()
            return

        h, w, _ = self.original_image.shape
        if w == 3840 and h == 1080:
            self.is_dual_format = True
            mid = w // 2
            self.image_lateral = self.original_image[:, :mid]
            self.image_top = self.original_image[:, mid:]
            img_h, img_w = self.image_lateral.shape[:2]
            total_w = img_w * 2
        else:
            self.is_dual_format = False
            img_h, img_w = h, w
            total_w = img_w
        screen = QApplication.primaryScreen().availableGeometry()

        MAX_SCREEN_RATIO = 0.5  
        MAX_IMG_RATIO = 0.7     

        max_win_w = int(screen.width() * MAX_SCREEN_RATIO) - 80
        max_win_h = int(screen.height() * MAX_SCREEN_RATIO) - 220

        scale_w = max_win_w / total_w
        scale_h = max_win_h / img_h

        self.scale = min(1.0, MAX_IMG_RATIO, scale_w, scale_h)

        self.display_w = int(img_w * self.scale)
        self.display_h = int(img_h * self.scale)

        if self.is_dual_format:
            self.setFixedSize(self.display_w * 2 + 80, self.display_h + 220)
        else:
            self.setFixedSize(self.display_w + 80, self.display_h + 220)
                    
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        self.info_group = QGroupBox("Expediente del Ejemplar")
        self.info_group.setToolTip("Resumen de los datos biométricos actuales registrados en la base de datos.")
        self.info_group.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 1px solid palette(mid); margin-top: 6px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        self.info_layout = QVBoxLayout(self.info_group)
        self.setup_info_label()
        self.main_layout.addWidget(self.info_group)

        images_container = QHBoxLayout()
        images_container.setSpacing(20)

        def create_panel(title, img, label_obj, tooltip_text):
            grp = QGroupBox(title)
            grp.setStyleSheet("QGroupBox { font-weight: bold; }")
            grp.setToolTip(tooltip_text)
            
            lyt = QVBoxLayout(grp)
            lyt.setContentsMargins(5, 15, 5, 5)
            
            label_obj.setFixedSize(self.display_w, self.display_h)
            label_obj.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label_obj.setStyleSheet("border: 2px solid palette(mid); border-radius: 4px; background-color: palette(base);")
            
            self.display_image(img, label_obj)
            lyt.addWidget(label_obj)
            return grp

        if self.is_dual_format:
            self.label_lateral = QLabel()
            self.label_top = QLabel()
            
            p_lat = create_panel(
                "Vista Lateral (Perfil)", 
                self.image_lateral, 
                self.label_lateral,
                "Cámara encargada de medir Longitud y Altura del lomo del pez."
            )
            p_top = create_panel(
                "Vista Cenital (Dorso)", 
                self.image_top, 
                self.label_top,
                "Cámara encargada de medir el Ancho dorsal del pez."
            )
            
            images_container.addWidget(p_lat)
            images_container.addWidget(p_top)
            
        else:
            self.label_full = QLabel()
            title = "Imagen Original Completa"
            if self.original_image is not None:
                h, w, _ = self.original_image.shape
                title += f" ({w}x{h} px)"
            
            p_full = create_panel(
                title, 
                self.original_image, 
                self.label_full,
                "<b>Imagen Raw:</b><br>Visualización completa de la captura original.<br><i>(La IA está desactivada porque no cumple el formato)</i>"
            )
            images_container.addWidget(p_full)

        self.main_layout.addLayout(images_container)

        actions_group = QGroupBox("Acciones Técnicas")
        actions_group.setToolTip("Herramientas de procesamiento y control.")
        actions_group.setStyleSheet("QGroupBox { font-weight: bold; background-color: palette(alternate-base); }")
        actions_layout = QHBoxLayout(actions_group)

        # Botón Re-Analizar (IA)
        self.analyze_button = QPushButton("Re-Analizar con IA (3D)")
        self.analyze_button.setProperty("class", "primary")
        self.analyze_button.style().unpolish(self.analyze_button)
        self.analyze_button.style().polish(self.analyze_button)
        self.analyze_button.setCursor(Qt.PointingHandCursor)
        self.analyze_button.setMinimumHeight(45)
        self.analyze_button.setToolTip("Re-analiza el modelo usando IA y actualiza la reconstrucción 3D.")
        
        self.btn_open_external = QPushButton("Ver Foto")
        self.btn_open_external.setProperty("class", "info") 
        self.btn_open_external.style().unpolish(self.btn_open_external)
        self.btn_open_external.style().polish(self.btn_open_external)
        self.btn_open_external.setCursor(Qt.PointingHandCursor)
        self.btn_open_external.setMinimumHeight(45)
        self.btn_open_external.setToolTip("Abre la imagen original en el visor de fotos predeterminado del SO.")
        self.btn_open_external.clicked.connect(self.open_external_viewer)
        actions_layout.addWidget(self.btn_open_external)

        actions_layout.addStretch()

        if self.is_dual_format and self.advanced_detector and self.advanced_detector.is_ready:
            self.analyze_button.setEnabled(True)
            self.analyze_button.setToolTip(
                "<b>Ejecutar Diagnóstico Biométrico:</b><br>"
                "Procesa las imágenes nuevamente para recalcular:<br>"
                "• Dimensiones (Largo, Alto, Ancho)<br>"
                "• Peso estimado<br>"
                "• Factor de Condición (K)"
            )
            self.analyze_button.clicked.connect(self.run_ia_analysis)
        else:
            self.analyze_button.setEnabled(False)
            self.analyze_button.setProperty("class", "secondary")
            if not self.is_dual_format:
                self.analyze_button.setText("IA Deshabilitada (Formato incompatible)")
                self.analyze_button.setToolTip("La IA requiere una imagen combinada exacta de 3840x1080 px.")
            else:
                self.analyze_button.setText("IA No Disponible")
                self.analyze_button.setToolTip("El modelo de Inteligencia Artificial no se ha cargado correctamente.")

        actions_layout.addWidget(self.analyze_button)
        actions_layout.addStretch()

        btn_close = QPushButton("Cerrar")
        btn_close.setProperty("class", "warning")
        btn_close.style().unpolish(btn_close)
        btn_close.style().polish(btn_close)
        btn_close.setMinimumHeight(45)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("Cierra esta ventana sin guardar cambios.")
        btn_close.clicked.connect(self.reject)
        actions_layout.addWidget(btn_close)
        
        self.main_layout.addWidget(actions_group)
        
    def open_external_viewer(self):
        """Abre la imagen usando el visor predeterminado del SO"""
        path = self.image_path_combined
        
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Archivo no encontrado", "La imagen original ya no existe en el disco.")
            return
            
        file_url = QUrl.fromLocalFile(os.path.abspath(path))
        
        if not QDesktopServices.openUrl(file_url):
            QMessageBox.warning(self, "Error", "No se pudo abrir el visor de imágenes del sistema.")

    def setup_info_label(self):
        """Genera el reporte adaptable al tema (Light/Dark Fix)"""
        
        def get_val(key_primary, key_alias=None, default=0.0):
            val = self.measurement_info.get(key_primary)
            
            if val is not None and val != "":
                try: 
                    f_val = float(val)
                    if f_val > 0.001: 
                        return f_val
                except: pass
            
            if key_alias:
                val = self.measurement_info.get(key_alias)
                if val is not None and val != "":
                    try: return float(val)
                    except: pass
                    
            return float(default)

        # Datos Base
        l = get_val('manual_length_cm', 'length_cm')
        h = get_val('manual_height_cm', 'height_cm')
        w = get_val('manual_width_cm', 'width_cm')
        weight = get_val('manual_weight_g', 'weight_g')
        
        lat_area = get_val('lat_area_cm2')
        top_area = get_val('top_area_cm2')
        vol = get_val('volume_cm3')
        
        # Cálculos Biológicos
        k = (100 * weight / (l ** 3)) if l > 0 else 0
        
        # Semáforo de Salud
        if k < 0.95:
            state_salud, txt_salud = "error", "BAJO PESO (Crítico)"
        elif 0.95 <= k <= 1.6:
            state_salud, txt_salud = "success", "SALUDABLE (Óptimo)"
        else:
            state_salud, txt_salud = "warning", "SOBREPESO"

        # Etapa de Vida
        if weight < 5: etapa = "Alevino"
        elif weight < 50: etapa = "Juvenil"
        else: etapa = "Engorde"

        # Badge de Tipo
        tipo_str = str(self.measurement_info.get('measurement_type', '')).lower()
        if "auto" in tipo_str:
            tipo_txt, tipo_state = "🤖 IA Automática", "auto"
        elif "ia_refined" in tipo_str:
             tipo_txt, tipo_state = "✨ IA Refinada (3D)", "success"
        else:
            tipo_txt, tipo_state = "🖐️ Manual / Editado", "manual"

        # HTML Adaptativo
        html = f"""
        <b>ID:</b> {self.measurement_info.get('id', 'N/A')}<br>
        <b>Fecha:</b> {self.measurement_info.get('timestamp', 'N/A')}<br><br>
        <b>Tipo:</b> {tipo_txt}<br><br>

        <b>📏 MORFOMETRÍA</b><br>
        • Largo Estimado: {l:.2f} cm<br>
        • Alto Estimado: {h:.2f} cm<br>
        • Ancho Estimado: {w:.2f} cm<br>
        • Área Lateral Estimado: {lat_area:.1f} cm²<br>
        • Área Cenital Estimado: {top_area:.1f} cm²<br>
        • Volumen Estimado: {vol:.1f} cm³<br><br>

        <b>⚖️ PRODUCCIÓN & SALUD</b><br>
        • Peso Estimado: {weight:.1f} g ({etapa})<br>
        • Factor K: {k:.3f}<br>
        • Diagnóstico: {txt_salud}
        """

        
        if not hasattr(self, 'info_label') or self.info_label is None:
            self.info_label = QLabel()
            self.info_label.setTextFormat(Qt.TextFormat.RichText)
            self.info_label.setWordWrap(True)
            self.info_label.setToolTip("Datos actuales del registro.")
            self.info_layout.addWidget(self.info_label) 

        self.info_label.setText(html)
        
        # Propiedades dinámicas
        self.info_label.setProperty("state", state_salud)
        self.info_label.setProperty("tipo", tipo_state)
        
        # Refrescar estilos
        self.info_label.style().unpolish(self.info_label)
        self.info_label.style().polish(self.info_label)

    def run_ia_analysis(self):
        """Ejecuta análisis completo y genera REPORTE DETALLADO"""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.analyze_button.setText("Escaneando Biometría 3D...")
        self.analyze_button.setEnabled(False)
        QApplication.processEvents() 

        try:
            service = BiometryService(self.advanced_detector)
            metrics, img_lat_ann, img_top_ann = service.analyze_and_annotate(
                img_lat=self.image_lateral, img_top=self.image_top,
                scale_lat_front=self.scale_lat_front, scale_lat_back=self.scale_lat_back,
                scale_top_front=self.scale_top_front, scale_top_back=self.scale_top_back,
                draw_box=True, draw_skeleton=True
            )

            if not metrics:
                QApplication.restoreOverrideCursor()
                self.reset_button_state()
                QMessageBox.warning(self, "Fallo de Detección", "No se pudo identificar el espécimen.")
                return

            self.display_image(img_lat_ann, self.label_lateral)
            self.display_image(img_top_ann, self.label_top)

            k_val = metrics.get('condition_factor', 0)
            weight = metrics.get('weight_g', 0)
            length = metrics.get('length_cm', 0)
            lat_area = metrics.get('lat_area_cm2', metrics.get('lat_area_cm2', 0))
            top_area = metrics.get('top_area_cm2', metrics.get('top_area_cm2', 0))
            
            if weight < 5: etapa = "Alevino"
            elif weight < 50: etapa = "Juvenil"
            else: etapa = "Engorde"
            
            k_coef = Config.WEIGHT_K
            exp_coef = Config.WEIGHT_EXP
            
            peso_teorico = k_coef * (length ** exp_coef)
            diff_pct = 0
            if peso_teorico > 0:
                diff_pct = ((weight - peso_teorico) / peso_teorico) * 100

            errores = MeasurementValidator.validate_measurement(metrics)
            
            QApplication.restoreOverrideCursor()
            self.reset_button_state()
            QApplication.processEvents()

            titulo = "✅ ANÁLISIS COMPLETADO" if not errores else "⚠️ ANÁLISIS CON OBSERVACIONES"
            icono = QMessageBox.Icon.Information if not errores else QMessageBox.Icon.Warning

            col_k = "green" if 0.9 <= k_val <= 1.5 else "red"
            col_diff = "green" if abs(diff_pct) < 15 else "orange"

            reporte_html = f"""
                            <h3 style="margin-top:0;">📋 Auditoría Biométrica</h3>
                            <hr>

                            <b>🧬 Identificación</b><br>
                            • Etapa Estimada: <b>{etapa}</b><br>
                            • Estado Salud (K): <span style="color:{col_k}; font-weight:bold;">{k_val:.3f}</span><br>
                            <br>

                            <div style="display:flex; gap:30px; align-items:flex-start;">

                                <!-- MORFOMETRÍA -->
                                <div style="flex:1;">
                                    <b>📏 Morfometría (Precisión)</b><br>
                                    • Largo Total Estimado: {length:.2f} cm<br>
                                    • Altura Máxima Estimada: {metrics['height_cm']:.2f} cm<br>
                                    • Ancho Dorsal Estimado: {metrics['width_cm']:.2f} cm<br>
                                    • Área Lateral Estimada: {metrics['lat_area_cm2']:.1f} cm²<br>
                                    • Área Cenital Estimada: {metrics['top_area_cm2']:.1f} cm²<br>
                                    • Volumen Estimado: {metrics['volume_cm3']:.1f} cm³<br>
                                </div>

                                <!-- PESO -->
                                <div style="flex:0.8;">
                                    <b>⚖️ Análisis de Peso</b><br>
                                    • Peso IA Estimado: <b>{weight:.1f} g</b><br>
                                    • Peso Teórico (Tabla): {peso_teorico:.1f} g<br>
                                    • Desviación: <span style="color:{col_diff};">{diff_pct:+.1f}%</span>
                                </div>

                            </div>
                            """

            if errores:
                style = self.report_style if self.report_style else {}
                bg = style.get('anomaly_bg', '#ffebee')
                border = style.get('anomaly_border', 'red')
                text = style.get('text', '#000000')

                reporte_html += f"""
                <br><br>
                <div style='background-color:{bg}; 
                            padding:10px; 
                            border:1px solid {border}; 
                            border-radius:5px;
                            color: {text};'>
                    <b style='color:{border};'>🚨 Anomalías detectadas:</b>
                    <ul style='margin-top:5px;'>
                """
                for err in errores:
                    reporte_html += f"<li>{err}</li>"
                reporte_html += "</ul></div>"

            reporte_html += "<hr><br><b>¿Desea actualizar la Base de Datos con estos resultados?</b>"

            confirm = QMessageBox(self)
            confirm.setWindowTitle("Resultados IA")
            confirm.setTextFormat(Qt.TextFormat.RichText)
            confirm.setText(titulo)
            confirm.setInformativeText(reporte_html)
            confirm.setIcon(icono)
            
            btn_si = confirm.addButton(
                "Guardar y Actualizar",
                QMessageBox.ButtonRole.AcceptRole
            )
            btn_si.setProperty("class", "success")
            btn_si.setCursor(Qt.PointingHandCursor)
            btn_si.setToolTip("Guardar los datos actuales y actualizar el registro en la base de datos.")

            btn_no = confirm.addButton(
                "Descartar",
                QMessageBox.ButtonRole.RejectRole
            )
            btn_no.setProperty("class", "warning")
            btn_no.setCursor(Qt.PointingHandCursor)
            btn_no.setToolTip("Descartar los cambios y cerrar sin guardar.")

            for btn in (btn_si, btn_no):
                btn.style().unpolish(btn)
                btn.style().polish(btn)

            confirm.exec()

            if confirm.clickedButton() == btn_si:
                self.update_database(metrics)

        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.reset_button_state()
            logger.error(f"Error IA: {e}.")
            QMessageBox.critical(self, "Error Critico", f"Error durante el analisis:\n{e}")

    def reset_button_state(self):
        self.analyze_button.setText("Re-Analizar con IA (3D)")
        self.analyze_button.setEnabled(True)

    def update_database(self, metrics):
        """Actualiza la BD fusionando los datos existentes con los nuevos de la IA"""
        m_id = self.measurement_info.get('id')
        
        full_data_to_save = self.measurement_info.copy()
        
        new_values = {
            'length_cm': metrics['length_cm'], 
            'weight_g': metrics['weight_g'],
            'volume_cm3': metrics['volume_cm3'], 
            
            'height_cm': metrics['height_cm'],    
            'width_cm': metrics['width_cm'],         

            'manual_length_cm': metrics['length_cm'],
            'manual_height_cm': metrics['height_cm'],
            'manual_width_cm': metrics['width_cm'],
            'manual_weight_g': metrics['weight_g'],
            
            'lat_area_cm2': metrics.get('lat_area_cm2', 0),   
            'top_area_cm2': metrics.get('top_area_cm2', 0), 
            
            'notes': f"{self.measurement_info.get('notes', '')} [IA Refinada]", 
            'measurement_type': 'ia_refined'
        }
        
        full_data_to_save.update(new_values)
        
        if self.db_manager.update_measurement(m_id, full_data_to_save):
            
            self.measurement_info.update(new_values)
            
            if self.on_update_callback: 
                self.on_update_callback()
                
            self.setup_info_label() 
            
            QMessageBox.information(self, "Éxito", "Registro actualizado correctamente con datos de IA.")
        else:
            QMessageBox.warning(self, "Error", "No se pudo actualizar la base de datos.")

    def display_image(self, cv_image, label: QLabel):
        if cv_image is None:
            label.setText("Sin Imagen")
            return

        cv_image = np.ascontiguousarray(cv_image)
        h, w, ch = cv_image.shape
        bytes_per_line = ch * w

        qt_img = QImage(
            cv_image.data, w, h, bytes_per_line,
            QImage.Format.Format_RGB888
        ).rgbSwapped()

        pixmap = QPixmap.fromImage(qt_img)

        scaled = pixmap.scaled(
            label.width(),
            label.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        label.setPixmap(scaled)