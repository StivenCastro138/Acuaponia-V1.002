import cv2
import os
import numpy as np
import logging
from PySide6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QGroupBox, QMessageBox, QDialog, QSizePolicy)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QImage, QDesktopServices

from BasedeDatos.DatabaseManager import DatabaseManager 
from .MeasurementValidator import MeasurementValidator 
from .BiometryService import BiometryService
from Config.Config import Config

logger = logging.getLogger(__name__)

class ImageViewerDialog(QDialog):
    def __init__(self, image_path_combined, measurement_info, advanced_detector, 
                 scale_lat_front, scale_lat_back, scale_top_front, scale_top_back, parent=None, on_update_callback=None, report_style=None):
        super().__init__(parent)
        self.report_style = report_style 
        
        # --- DATOS ---
        self.image_path_combined = image_path_combined
        self.measurement_info = measurement_info 
        self.advanced_detector = advanced_detector
        self.on_update_callback = on_update_callback
        
        # Escalas
        self.scale_lat_front = scale_lat_front
        self.scale_lat_back = scale_lat_back
        self.scale_top_front = scale_top_front
        self.scale_top_back = scale_top_back
        
        # Configuración Ventana
        self.setWindowTitle("Auditoría Biométrica")
        self.setModal(True)
        self.setMinimumSize(1300, 850)

        self.db_manager = DatabaseManager() 
        self.info_label = None 

        # --- LÓGICA DE CARGA DE IMAGEN INTELIGENTE ---
        self.original_image = None
        self.image_lateral = None
        self.image_top = None
        self.is_dual_format = False 
        
        if os.path.exists(self.image_path_combined):
            self.original_image = cv2.imread(self.image_path_combined)
            if self.original_image is not None:
                h, w, _ = self.original_image.shape
                if w == 3840 and h == 1080:
                    self.is_dual_format = True
                    mid = w // 2
                    self.image_lateral = self.original_image[:, :mid]
                    self.image_top = self.original_image[:, mid:]
                else:
                    self.is_dual_format = False
                    
        screen = QApplication.primaryScreen().availableGeometry()
        window_width = int(screen.width() * 0.5)
        window_height = int(((window_width / 2) * 9 / 16) + screen.height() * 0.09)

        self.resize(window_width, window_height)
        
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. FICHA TÉCNICA
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        self.info_group = QGroupBox("Expediente del Ejemplar")
        self.info_group.setToolTip("Resumen de los datos biométricos actuales registrados en la base de datos.")
        self.info_group.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 1px solid palette(mid); margin-top: 6px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        self.info_layout = QVBoxLayout(self.info_group)
        self.setup_info_label()
        self.main_layout.addWidget(self.info_group)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. VISOR DE IMÁGENES (Con Tooltips en Paneles)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        images_container = QHBoxLayout()
        images_container.setSpacing(20)

        # Helper para crear paneles con tooltip
        def create_panel(title, img, label_obj, tooltip_text):
            grp = QGroupBox(title)
            grp.setStyleSheet("QGroupBox { font-weight: bold; }")
            grp.setToolTip(tooltip_text)
            
            lyt = QVBoxLayout(grp)
            lyt.setContentsMargins(5, 15, 5, 5)
            
            label_obj.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label_obj.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
            label_obj.setStyleSheet("border: 2px solid palette(mid); border-radius: 4px; background-color: palette(base);")
            
            self.display_image(img, label_obj)
            lyt.addWidget(label_obj)
            return grp

        if self.is_dual_format:
            # Formato Correcto (3840x1080)
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
            
            images_container.addWidget(p_lat, stretch=1)
            images_container.addWidget(p_top, stretch=1)
            
        else:
            # CASO B: Formato Incorrecto
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
            images_container.addWidget(p_full, stretch=1)

        self.main_layout.addLayout(images_container, stretch=1)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. BARRA DE HERRAMIENTAS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        actions_group = QGroupBox("Acciones Técnicas")
        actions_group.setToolTip("Herramientas de procesamiento y control.")
        actions_group.setStyleSheet("QGroupBox { font-weight: bold; background-color: palette(alternate-base); }")
        actions_layout = QHBoxLayout(actions_group)

        # Botón Re-Analizar (IA)
        self.analyze_button = QPushButton("Re-Analizar con IA (3D)")
        self.analyze_button.setProperty("class", "primary")
        self.analyze_button.setCursor(Qt.PointingHandCursor)
        self.analyze_button.setMinimumHeight(45)
        self.analyze_button.setToolTip("Re-analiza el modelo usando IA y actualiza la reconstrucción 3D.")
        
        self.btn_open_external = QPushButton("Ver Foto")
        self.btn_open_external.setProperty("class", "info") 
        self.btn_open_external.setCursor(Qt.PointingHandCursor)
        self.btn_open_external.setMinimumHeight(45)
        self.btn_open_external.setToolTip("Abre la imagen original en el visor de fotos predeterminado del SO.")
        self.btn_open_external.clicked.connect(self.open_external_viewer)
        actions_layout.addWidget(self.btn_open_external)

        actions_layout.addStretch()

        # LÓGICA DE BLOQUEO DE IA
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
            # 1. Intenta buscar el nombre exacto (ej: manual_length_cm)
            val = self.measurement_info.get(key_primary)
            if val is not None and val != "":
                try: return float(val)
                except: pass
            
            # 2. Si falla, intenta buscar el backup (ej: length_cm)
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
        tipo_str = str(self.measurement_info.get('type', '')).lower()
        if "auto" in tipo_str:
            tipo_txt, tipo_state = "🤖 IA Automática", "auto"
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
            # 1. Instanciar servicio y procesar
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

            # 2. Actualizar visualización
            self.display_image(img_lat_ann, self.label_lateral)
            self.display_image(img_top_ann, self.label_top)

            # 3. CÁLCULOS AVANZADOS
            k_val = metrics.get('condition_factor', 0)
            weight = metrics.get('weight_g', 0)
            length = metrics.get('length_cm', 0)
            
            if weight < 5: etapa = "Alevino"
            elif weight < 50: etapa = "Juvenil"
            else: etapa = "Engorde"
            
            # Comparativa Teórica
            k_coef = Config.WEIGHT_K
            exp_coef = Config.WEIGHT_EXP
            
            peso_teorico = k_coef * (length ** exp_coef)
            diff_pct = 0
            if peso_teorico > 0:
                diff_pct = ((weight - peso_teorico) / peso_teorico) * 100

            errores = MeasurementValidator.validate_measurement(metrics)
            
            # 4. RESTAURAR BOTÓN (Antes del Popup)
            QApplication.restoreOverrideCursor()
            self.reset_button_state()
            QApplication.processEvents()

            # 5. REPORTE FINAL (HTML)
            titulo = "✅ ANÁLISIS COMPLETADO" if not errores else "⚠️ ANÁLISIS CON OBSERVACIONES"
            icono = QMessageBox.Icon.Information if not errores else QMessageBox.Icon.Warning

            col_k = "green" if 0.9 <= k_val <= 1.5 else "red"
            col_diff = "green" if abs(diff_pct) < 15 else "orange"

            lat_area = metrics.get('lat_area_cm2', metrics.get('lat_area_cm2', 0))
            top_area = metrics.get('top_area_cm2', metrics.get('top_area_cm2', 0))
            reporte_html = f"""
            <h3 style="margin-top:0;">📋 Auditoría Biométrica</h3>
            <hr>
            <b>🧬 Identificación</b><br>
            • Etapa Estimada: <b>{etapa}</b><br>
            • Estado Salud (K): <span style="color:{col_k}; font-weight:bold;">{k_val:.3f}</span><br>
            <br>
            <b>📏 Morfometría (Precisión)</b><br>
            • Largo Total Estimado: {length:.2f} cm<br>
            • Altura Máxima Estimada: {metrics['height_cm']:.2f} cm<br>
            • Ancho Dorsal Estimado: {metrics['width_cm']:.2f} cm<br>
            • Área Lateral Estimada: {metrics['lat_area_cm2']:.1f} cm²<br> • Área Cenital Estimada: {metrics['top_area_cm2']:.1f} cm²<br>
            • Volumen Estimado: {metrics['volume_cm3']:.1f} cm³<br>
            <br>
            <b>⚖️ Análisis de Peso</b><br>
            • Peso IA Estimado: <b>{weight:.1f} g</b><br>
            • Peso Teórico (Tabla): {peso_teorico:.1f} g<br>
            • Desviación: <span style="color:{col_diff};">{diff_pct:+.1f}%</span>
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

            # Botón Descartar (WARNING)
            btn_no = confirm.addButton(
                "Descartar",
                QMessageBox.ButtonRole.RejectRole
            )
            btn_no.setProperty("class", "warning")
            btn_no.setCursor(Qt.PointingHandCursor)
            btn_no.setToolTip("Descartar los cambios y cerrar sin guardar.")

            # 🔥 Forzar reaplicación de estilos QSS
            for btn in (btn_si, btn_no):
                btn.style().unpolish(btn)
                btn.style().polish(btn)

            confirm.exec()

            if confirm.clickedButton() == btn_si:
                self.update_database(metrics)

        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.reset_button_state()
            logger.error(f"Error IA: {e}")
            QMessageBox.critical(self, "Error Critico", f"Error durante el analisis:\n{e}")

    def reset_button_state(self):
        self.analyze_button.setText("Re-Analizar con IA (3D)")
        self.analyze_button.setEnabled(True)

    def update_database(self, metrics):
        """Actualiza la BD fusionando los datos existentes con los nuevos de la IA"""
        m_id = self.measurement_info.get('id')
        
        # 1. CREAR COPIA DE LOS DATOS ACTUALES (Para no perder fish_id, paths, etc.)
        # Si no haces esto, DatabaseManager pondrá en blanco lo que falte.
        full_data_to_save = self.measurement_info.copy()
        
        # 2. PREPARAR LOS NUEVOS DATOS DE LA IA
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
        
        # 3. FUSIONAR (Sobrescribir los viejos con los nuevos)
        full_data_to_save.update(new_values)
        
        # 4. ENVIAR EL PAQUETE COMPLETO A LA BD
        if self.db_manager.update_measurement(m_id, full_data_to_save):
            
            # 5. Si salió bien, actualizamos la memoria local de la ventana
            self.measurement_info.update(new_values)
            
            # Callback para refrescar la tabla principal (MainWindow)
            if self.on_update_callback: 
                self.on_update_callback()
                
            # Refrescar el panel de información lateral
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
        
        qt_img = QImage(cv_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        
        pixmap = QPixmap.fromImage(qt_img).scaled(label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(pixmap)

    def resizeEvent(self, event):
        if self.is_dual_format:
            if self.image_lateral is not None: self.display_image(self.image_lateral, self.label_lateral)
            if self.image_top is not None: self.display_image(self.image_top, self.label_top)
        else:
            if self.original_image is not None: self.display_image(self.original_image, self.label_full)
        super().resizeEvent(event)