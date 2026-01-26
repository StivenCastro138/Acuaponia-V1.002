from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                               QLabel, QLineEdit, QDoubleSpinBox, QTextEdit, 
                               QPushButton, QGroupBox, QWidget, QDateTimeEdit)
from PySide6.QtCore import Qt, QDateTime
from Modulos.MorphometricAnalyzer import MorphometricAnalyzer

class EditMeasurementDialog(QDialog):
    
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
        self.setWindowTitle("Editar Registro")
        self.setFixedWidth(500)
        
        # 1. Normalización de Datos
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

        ts_str = str(self.measurement_data.get('timestamp', ''))
        qdate = QDateTime.fromString(ts_str, "yyyy-MM-dd HH:mm:ss")
        
        if not qdate.isValid():
            qdate = QDateTime.currentDateTime()
            
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
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setToolTip("Cancelar edición del registro actual.")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Guardar Cambios")
        btn_save.setProperty("class", "success")
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

        # --- ACTUALIZAR UI ---
        
        # A. Factor K (Semáforo de Salud)
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
        """Retorna el diccionario limpio para la BD"""
        record_id = self.measurement_data.get('id')
        new_timestamp = self.dt_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        
        return {
            'id': record_id,  
            'timestamp': new_timestamp,
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
            'volume_cm3': self.spin_volume.value()
        }