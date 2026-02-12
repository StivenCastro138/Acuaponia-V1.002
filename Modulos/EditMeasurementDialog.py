"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Editor de Registros (EditMeasurementDialog.py)
DESCRIPCIÓN: Formulario avanzado para la modificación de datos históricos.
             Implementa validación en tiempo real (Live Validation) contra modelos
             alométricos para asistir al usuario en la corrección de errores.
"""
import os
import cv2
import glob
import numpy as np
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLabel, QLineEdit, QDoubleSpinBox, QTextEdit, 
                               QPushButton, QGroupBox, QWidget, QDateTimeEdit, QApplication)
from PySide6.QtCore import Qt, QDateTime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Modulos.MainWindow import MainWindow
from Modulos.MorphometricAnalyzer import MorphometricAnalyzer
from Config.Config import Config

class EditMeasurementDialog(QDialog):
    """
    Diálogo para auditoría y corrección de datos biométricos.
    
    Características:
    - Mapeo automático de tuplas de base de datos a campos editables.
    - Retroalimentación visual inmediata sobre la coherencia biológica (Factor K).
    - Preservación de la integridad referencial (ID inmutable).
    """
    
    # Mapeo de columnas
    COLUMN_NAMES = [
    'id',
    'timestamp',
    'fish_id',

    'length_cm',
    'height_cm',
    'width_cm',
    'weight_g',
    
    'manual_length_cm',
    'manual_height_cm',
    'manual_width_cm',
    'manual_weight_g',

    'lat_area_cm2',
    'top_area_cm2',
    'volume_cm3',
    'confidence_score',

    'notes',
    'image_path',
    'measurement_type',

    'validation_errors'
]

    def __init__(self, measurement_data, parent=None):
        super().__init__(parent)
        self.main_window: 'MainWindow' = parent
        self.setWindowTitle("Editar Registro")
        self.setFixedWidth(500)
        
        if isinstance(measurement_data, (list, tuple)):
            if len(measurement_data) == len(self.COLUMN_NAMES):
                self.measurement_data = dict(zip(self.COLUMN_NAMES, measurement_data))
            else:
                self.measurement_data = {}
        else:
            self.measurement_data = measurement_data

        self.init_ui()

    def safe_value(self, key, default=0.0):
        try:
            val = self.measurement_data.get(key)
            return float(val) if val is not None else default
        except:
            return default

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. ENCABEZADO E INFO
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        rec_id = self.measurement_data.get('id', 'N/A')
        lbl_title = QLabel(f"Editando Medición ID: {rec_id}")
        lbl_title.setProperty("state", "accent")
        layout.addWidget(lbl_title)

        mtype = self.measurement_data.get('measurement_type', 'auto').upper()
        info_group = QGroupBox("Información General")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        
        info_layout = QFormLayout(info_group) 
        
        self.dt_edit = QDateTimeEdit()
        self.dt_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dt_edit.setCalendarPopup(True) 
        self.dt_edit.setToolTip("Fecha y Hora en la que se midió el pez.")

        ts_str = self.measurement_data.get('timestamp')

        if ts_str:
            # Intento 1: formato estándar
            qdate = QDateTime.fromString(ts_str, "yyyy-MM-dd HH:mm:ss")
            
            # Intento 2: si viene con milisegundos
            if not qdate.isValid():
                qdate = QDateTime.fromString(ts_str, "yyyy-MM-dd HH:mm:ss.zzz")
                
            # Intento 3: ISO (muy común en SQLite)
            if not qdate.isValid():
                qdate = QDateTime.fromString(ts_str, Qt.ISODate)
                
            if not qdate.isValid():
                qdate = QDateTime.currentDateTime()
        else:
            qdate = QDateTime.currentDateTime()

        self.dt_edit.setDateTime(qdate)

            
        self.dt_edit.setDateTime(qdate)
        info_layout.addRow("Fecha/Hora:", self.dt_edit)

        lbl_type = QLabel(f"{mtype}")
        if 'MANUAL' in mtype:
            lbl_type.setProperty("state", "warning")
        elif 'IA' in mtype:
            lbl_type.setProperty("state", "success")
        else:
            lbl_type.setProperty("state", "info")
        info_layout.addRow("Tipo:", lbl_type)
        
        layout.addWidget(info_group)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. FORMULARIO EDITABLE
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # --- ID Pez ---
        self.txt_fish_id = QLineEdit(str(self.measurement_data.get('fish_id') or ""))
        self.txt_fish_id.setPlaceholderText("Ej: pez_05")
        self.txt_fish_id.setToolTip("Número identificador único para el pez.")
        form_layout.addRow("ID Pez:", self.txt_fish_id)

        # --- Longitud ---
        self.spin_length = QDoubleSpinBox()
        self.spin_length.setRange(0, 999.99)
        self.spin_length.setSuffix(" cm")
        len_val = self.safe_value('manual_length_cm') or self.safe_value('length_cm')
        self.spin_length.setValue(len_val)
        self.spin_length.setToolTip("Longitud estándar del pez.")
        form_layout.addRow("Largo:", self.spin_length)

        # --- Peso ---
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0, 9999.99)
        self.spin_weight.setSuffix(" g")
        wei_val = self.safe_value('manual_weight_g') or self.safe_value('weight_g')
        self.spin_weight.setValue(wei_val)
        self.spin_weight.setToolTip("Peso corporal total.")
        form_layout.addRow("Peso:", self.spin_weight)

        # --- Morfometría ---
        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(0, 999.99)
        self.spin_height.setSuffix(" cm")
        self.spin_height.setValue(self.safe_value('manual_height_cm') or self.safe_value('height_cm'))
        self.spin_height.setToolTip("Altura máxima del cuerpo del pez.")
        form_layout.addRow("Altura:", self.spin_height)

        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(0, 999.99)
        self.spin_width.setSuffix(" cm")
        self.spin_width.setValue(self.safe_value('manual_width_cm') or self.safe_value('width_cm'))
        self.spin_width.setToolTip("Ancho dorsal del pez.")
        form_layout.addRow("Ancho:", self.spin_width)
        
        # --- Científicos ---
        self.spin_lat_area = QDoubleSpinBox()
        self.spin_lat_area.setRange(0, 99999)
        self.spin_lat_area.setSuffix(" cm²")
        self.spin_lat_area.setValue(self.safe_value('lat_area_cm2'))
        self.spin_lat_area.setToolTip("Superficie detectada en la vista lateral.")
        form_layout.addRow("Área Lateral:", self.spin_lat_area)
        
        self.spin_top_area = QDoubleSpinBox()
        self.spin_top_area.setRange(0, 99999)
        self.spin_top_area.setSuffix(" cm²")
        self.spin_top_area.setValue(self.safe_value('top_area_cm2'))
        self.spin_top_area.setToolTip("Superficie detectada en la vista cenital.")
        form_layout.addRow("Área Cenital:", self.spin_top_area)

        self.spin_volume = QDoubleSpinBox()
        self.spin_volume.setRange(0, 99999)
        self.spin_volume.setSuffix(" cm³")
        self.spin_volume.setValue(self.safe_value('volume_cm3'))
        self.spin_volume.setToolTip("Cálculo basado en el modelo elipsoide.")
        form_layout.addRow("Volumen:", self.spin_volume)

        # --- Notas ---
        self.txt_notes = QTextEdit(str(self.measurement_data.get('notes') or ""))
        self.txt_notes.setPlaceholderText("Observaciones...")
        self.txt_notes.setMaximumHeight(60)
        self.txt_notes.setToolTip("Observaciones y notas del pez.")
        form_layout.addRow("Notas:", self.txt_notes)

        layout.addLayout(form_layout)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. DIAGNÓSTICO EN VIVO
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        calc_group = QGroupBox("Diagnóstico en Vivo")
        calc_group.setStyleSheet("QGroupBox { font-weight: bold; background-color: palette(alternate-base); }")
        calc_group.setToolTip("Cálculos automáticos basados en los valores que estás editando.")
        calc_layout = QHBoxLayout(calc_group)

        self.lbl_factor_k = QLabel("--")
        self.lbl_factor_k.setAlignment(Qt.AlignCenter)
        self.lbl_factor_k.setToolTip("Índice de bienestar corporal del pez.")
        calc_layout.addWidget(QLabel("Factor K:"))
        calc_layout.addWidget(self.lbl_factor_k)

        line = QWidget()
        line.setFixedWidth(1)
        line.setStyleSheet("background-color: gray;")
        calc_layout.addWidget(line)

        self.lbl_weight_expected = QLabel("--")
        self.lbl_weight_expected.setAlignment(Qt.AlignCenter)
        self.lbl_weight_expected.setToolTip("Peso estimado según la longitud ingresada.")
        calc_layout.addWidget(QLabel("Peso Estimado:"))
        calc_layout.addWidget(self.lbl_weight_expected)

        layout.addWidget(calc_group)

        self.spin_length.valueChanged.connect(self.update_calculated_info)
        self.spin_weight.valueChanged.connect(self.update_calculated_info)
        self.spin_height.valueChanged.connect(self.update_calculated_info)
        self.spin_width.valueChanged.connect(self.update_calculated_info)

        self.update_calculated_info()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. BOTONES
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("class", "warning")
        btn_cancel.style().unpolish(btn_cancel)
        btn_cancel.style().polish(btn_cancel)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setToolTip("Cancelar edición del registro actual.")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Guardar Cambios")
        btn_save.setProperty("class", "success")
        btn_save.style().unpolish(btn_save)
        btn_save.style().polish(btn_save)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setToolTip("Guardar los datos actuales en la base de datos.")
        btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def update_calculated_info(self):
        """Calcula feedback científico en tiempo real"""
        l = self.spin_length.value()
        h = self.spin_height.value()
        wi = self.spin_width.value()
        w_input = self.spin_weight.value() 

        # 1. Cálculo Teórico
        metrics_theory = MorphometricAnalyzer._calculate_derived_metrics(l, h, wi)
        expected_weight = metrics_theory.get('weight_g', 0)
        
        # 2. Cálculo Factor K Real
        k_real = 0.0
        if l > 0 and w_input > 0:
            k_real = (100 * w_input) / (l ** 3)

        # A. Factor K 
        self.lbl_factor_k.setText(f"{k_real:.3f}")
        if 0.9 <= k_real <= 1.5:
            self.lbl_factor_k.setProperty("state", "ok")
        else:
            self.lbl_factor_k.setProperty("state", "bad")
            
        self.lbl_factor_k.style().polish(self.lbl_factor_k)
        self.lbl_weight_expected.style().polish(self.lbl_weight_expected)

        # B. Peso Teórico vs Real
        text_expected = f"{expected_weight:.2f} g"
        self.lbl_weight_expected.setProperty("state", "normal")

        if w_input > 0 and expected_weight > 0:
            diff = abs(w_input - expected_weight) / expected_weight
            if diff > 0.30:
                self.lbl_weight_expected.setProperty("state", "warn")

        self.lbl_weight_expected.setText(text_expected)

    def get_updated_data(self):
        """Retorna el diccionario con los datos finales para ser guardados por MainWindow."""
        # IMPORTANTE: Aquí es donde MainWindow saca la información para el UPDATE de SQL
        return {
            'id': self.measurement_data.get('id'),
            'timestamp': self.dt_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            'fish_id': self.txt_fish_id.text().strip(),
            'measurement_type': 'manual', 
            'notes': self.txt_notes.toPlainText().strip(),
            'length_cm': self.spin_length.value(),
            'manual_length_cm': self.spin_length.value(),
            'weight_g': self.spin_weight.value(),
            'manual_weight_g': self.spin_weight.value(),
            'height_cm': self.spin_height.value(),
            'manual_height_cm': self.spin_height.value(),
            'width_cm': self.spin_width.value(),
            'manual_width_cm': self.spin_width.value(),
            'lat_area_cm2': self.spin_lat_area.value(),
            'top_area_cm2': self.spin_top_area.value(),
            'volume_cm3': self.spin_volume.value(),
            # PASO MAESTRO: Enviamos la ruta que actualizamos en el método accept()
            'image_path': self.measurement_data.get('image_path') 
        }
        
    def _find_image_forensic(self, old_path_db):
        """
        Busca la imagen usando múltiples estrategias, igual que MainWindow.view_measurement_image()
        
        ESTRATEGIA 1: Ruta directa de BD
        ESTRATEGIA 2: Búsqueda por nombre en Config.IMAGES_*_DIR
        ESTRATEGIA 3: Búsqueda por timestamp (patrón de fecha)
        
        Retorna: ruta absoluta del archivo encontrado, o None
        """
        # ──────────────────────────────────────────────────
        # CASO A: La ruta existe tal cual
        # ──────────────────────────────────────────────────
        if old_path_db and os.path.exists(old_path_db):
            print(f"✅ Imagen encontrada directamente: {old_path_db}")
            return old_path_db
        
        archivo_encontrado = None
        
        # ──────────────────────────────────────────────────
        # CASO B: Búsqueda por NOMBRE DE ARCHIVO
        # ──────────────────────────────────────────────────
        if old_path_db:
            fname = os.path.basename(old_path_db)
            
            # Usar Config.IMAGES_*_DIR (rutas absolutas configuradas)
            posibles = [
                os.path.join(Config.IMAGES_MANUAL_DIR, fname),
                os.path.join(Config.IMAGES_AUTO_DIR, fname),
            ]
            
            for p in posibles:
                if os.path.exists(p):
                    archivo_encontrado = p
                    print(f"✅ Imagen encontrada por nombre en: {p}")
                    break
        
        # ──────────────────────────────────────────────────
        # CASO C: BÚSQUEDA FORENSE POR TIMESTAMP
        # ──────────────────────────────────────────────────
        if not archivo_encontrado:
            ts_str = str(self.measurement_data.get('timestamp', ""))
            fish_id = str(self.measurement_data.get('fish_id', ""))
            
            try:
                # Convertir "2026-02-11 18:30:00" → "20260211_183000"
                ts_clean = ts_str.replace("-", "").replace(":", "").replace(" ", "_")
                key_search = ts_clean[:15]  # Primeros 15 caracteres
            except:
                key_search = "INVALIDO"
            
            # Directorios donde buscar
            search_dirs = [
                Config.IMAGES_MANUAL_DIR,
                Config.IMAGES_AUTO_DIR,
                os.getcwd()  # Como último recurso
            ]
            
            if len(key_search) > 10:  # Solo si la fecha parece válida
                for carpeta in search_dirs:
                    if not os.path.exists(carpeta):
                        continue
                    
                    # Buscar cualquier JPG que contenga esa fecha exacta
                    patron = os.path.join(carpeta, f"*{key_search}*.jpg")
                    coincidencias = glob.glob(patron)
                    
                    if coincidencias:
                        archivo_encontrado = coincidencias[0]
                        # Preferir el que tenga el mismo ID
                        for c in coincidencias:
                            if fish_id in os.path.basename(c):
                                archivo_encontrado = c
                                break
                        print(f"✅ Imagen encontrada por timestamp: {archivo_encontrado}")
                        break
        
        return archivo_encontrado
    
    # -------------------------------------------------------------------------
    # BUSCADOR "A PRUEBA DE FALLOS" DE LA VENTANA PRINCIPAL
    # -------------------------------------------------------------------------
    def _find_main_window(self):
        """Busca la MainWindow de forma segura para usar draw_fish_overlay."""
        curr = self.parent()
        while curr:
            if hasattr(curr, 'draw_fish_overlay'):
                return curr
            curr = curr.parent()
        # Búsqueda global si el parent falló
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'draw_fish_overlay'):
                return widget
        return None

    def accept(self):
        """
        Al dar clic en Guardar:
        1. Localiza la imagen vieja usando búsqueda forense robusta.
        2. Genera la nueva imagen con el overlay de texto negro.
        3. Crea el nuevo nombre de archivo (renombrado).
        4. Actualiza self.measurement_data para que get_updated_data() la devuelva corregida.
        """
        old_path_db = self.measurement_data.get('image_path', '')
        tipo_orig = self.measurement_data.get('measurement_type', 'MANUAL')
        main_app = self._find_main_window()

        if not main_app:
            print("⚠️ No se encontró MainWindow, guardando sin procesar imagen")
            super().accept()
            return

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 NUEVA LÓGICA: Usar búsqueda forense robusta
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        actual_path = self._find_image_forensic(old_path_db)

        # --- PROCESAMIENTO ---
        if actual_path:
            try:
                # Usamos los valores actuales de los widgets para el dibujo
                new_fish_id = self.txt_fish_id.text().strip()
                new_len = self.spin_length.value()
                new_weight = self.spin_weight.value()
                new_ts = self.dt_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")

                # Cargar imagen de forma segura (maneja caracteres Unicode en la ruta)
                with open(actual_path, "rb") as f:
                    img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_UNCHANGED)
                
                if img is not None:
                    # Dibujar Overlay
                    payload = {
                        "tipo": "EDITADO", "numero": new_fish_id,
                        "longitud": new_len, "peso": new_weight, "fecha": new_ts
                    }
                    img_new = main_app.draw_fish_overlay(img, payload)
                    
                    # Generar nombre nuevo
                    nuevo_nombre = main_app.generar_nombre_archivo(
                        tipo_orig, new_fish_id, new_len, 
                        self.spin_height.value(), self.spin_width.value(), 
                        new_weight, new_ts
                    )
                    
                    folder = os.path.dirname(actual_path)
                    new_path = os.path.join(folder, nuevo_nombre)
                    
                    # Guardar Físicamente
                    is_ok, buf = cv2.imencode(".jpg", img_new)
                    if is_ok:
                        buf.tofile(new_path)
                        # Borrar vieja si cambió
                        if os.path.abspath(actual_path) != os.path.abspath(new_path):
                            try: 
                                os.remove(actual_path)
                                print(f"🗑️ Archivo antiguo eliminado: {actual_path}")
                            except: 
                                pass
                        
                        # ACTUALIZAR RUTA EN MEMORIA (Para que el padre la guarde en BD)
                        self.measurement_data['image_path'] = new_path
                        print(f"✅ Imagen editada y renombrada a: {nuevo_nombre}")
                else:
                    print(f"❌ No se pudo decodificar la imagen: {actual_path}")
                    
            except Exception as e:
                print(f"❌ Error en Editor al procesar imagen: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ No se encontró la imagen física para editar.")
            print(f"   Ruta BD: {old_path_db}")
            print(f"   Fish ID: {self.measurement_data.get('fish_id')}")
            print(f"   Timestamp: {self.measurement_data.get('timestamp')}")

        super().accept()