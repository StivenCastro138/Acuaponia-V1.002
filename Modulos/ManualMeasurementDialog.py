from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGridLayout,
                               QDoubleSpinBox, QMessageBox, QDialog, QLineEdit, QFrame)
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt

from .MeasurementValidator import MeasurementValidator

class ManualMeasurementDialog(QDialog):
    """
    Diálogo de entrada de datos manuales.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📥 Registro de Medición Manual")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        # Estado de datos
        self.result_data = {}
        
        self.init_ui()
        self._apply_styles()
    
    def _apply_styles(self):
        """Estilo moderno y limpio."""
        self.setStyleSheet("""
            QDialog { background-color: #f5f7fa; }
            QLabel { color: #2c3e50; font-weight: bold; font-size: 10pt; }
            QLineEdit, QDoubleSpinBox { 
                padding: 8px; 
                border: 2px solid #bdc3c7; 
                border-radius: 6px; 
                background: white;
                font-size: 11pt;
            }
            QLineEdit:focus, QDoubleSpinBox:focus { border: 2px solid #3498db; }
            QPushButton#btn_ok { 
                background-color: #27ae60; color: white; font-weight: bold; 
                padding: 10px; border-radius: 6px; min-width: 100px;
            }
            QPushButton#btn_cancel { 
                background-color: #e74c3c; color: white; font-weight: bold; 
                padding: 10px; border-radius: 6px; min-width: 100px;
            }
        """)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Encabezado
        header = QLabel("📋 Ingrese las Medidas del Ejemplar")
        header.setStyleSheet("font-size: 14pt; color: #1a237e; margin-bottom: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Contenedor del Formulario
        form_frame = QFrame()
        form_frame.setStyleSheet("background: #ffffff; border-radius: 10px; padding: 10px;")
        form_layout = QGridLayout(form_frame)
        form_layout.setVerticalSpacing(12)
        
        # --- ID DEL PEZ ---
        form_layout.addWidget(QLabel("🆔 ID del Pez:"), 0, 0)
        self.txt_fish_id = QLineEdit()
        self.txt_fish_id.setPlaceholderText("Ej: 101")
        self.txt_fish_id.setValidator(QIntValidator(1, 999999))
        form_layout.addWidget(self.txt_fish_id, 0, 1)
        
        # --- LONGITUD ---
        form_layout.addWidget(QLabel("📏 Longitud (cm):"), 1, 0)
        self.spin_length = QDoubleSpinBox()
        self.spin_length.setRange(0.5, 120.0)
        self.spin_length.setDecimals(2)
        self.spin_length.setValue(15.0)
        self.spin_length.setSuffix(" cm")
        form_layout.addWidget(self.spin_length, 1, 1)
        
        # --- ALTURA ---
        form_layout.addWidget(QLabel("📐 Altura Lomo (cm):"), 2, 0)
        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(0.1, 40.0)
        self.spin_height.setDecimals(2)
        self.spin_height.setValue(3.5)
        self.spin_height.setSuffix(" cm")
        form_layout.addWidget(self.spin_height, 2, 1)
        
        # --- ANCHO ---
        form_layout.addWidget(QLabel("⇳ Ancho Dorso (cm):"), 3, 0)
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(0.1, 30.0)
        self.spin_width.setDecimals(2)
        self.spin_width.setValue(2.0)
        self.spin_width.setSuffix(" cm")
        form_layout.addWidget(self.spin_width, 3, 1)
        
        # --- PESO ---
        form_layout.addWidget(QLabel("⚖️ Peso Real (g):"), 4, 0)
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0.1, 8000.0)
        self.spin_weight.setDecimals(1)
        self.spin_weight.setValue(50.0)
        self.spin_weight.setSuffix(" g")
        form_layout.addWidget(self.spin_weight, 4, 1)
        
        # --- NOTAS ---
        form_layout.addWidget(QLabel("📝 Notas:"), 5, 0)
        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Ej: Hembra madura, lote A1")
        form_layout.addWidget(self.txt_notes, 5, 1)
        
        layout.addWidget(form_frame)
        
        # Botones de Acción
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_ok = QPushButton("✓ Guardar Registro")
        self.btn_ok.setObjectName("btn_ok")
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ok.clicked.connect(self.accept_data)
        
        self.btn_cancel = QPushButton("✗ Cancelar")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        
        layout.addLayout(btn_layout)

    def accept_data(self):
        """Valida y guarda los datos."""
        fish_id = self.txt_fish_id.text().strip()
        
        if not fish_id:
            QMessageBox.critical(self, "Error", "El ID del pez es obligatorio.")
            self.txt_fish_id.setFocus()
            return
            
        # Preparar métricas para validación biológica
        metrics = {
            'length_cm': self.spin_length.value(),
            'height_cm': self.spin_height.value(),
            'weight_g': self.spin_weight.value(),
            'condition_factor': (100 * self.spin_weight.value()) / (self.spin_length.value()**3)
        }
        
        # Usamos nuestro validador avanzado
        warnings = MeasurementValidator.validate_measurement(metrics)
        
        if warnings:
            # Si hay advertencias biológicas, preguntamos al usuario si está seguro
            warn_text = "Se han detectado inconsistencias biológicas:\n\n" + "\n".join(warnings)
            warn_text += "\n\n¿Desea guardar estos datos de todos modos?"
            
            reply = QMessageBox.warning(self, "Advertencia Biológica", warn_text, 
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.No:
                return

        # Construir diccionario final
        self.result_data = {
            'fish_id': fish_id,
            'length_cm': self.spin_length.value(),
            'manual_height_cm': self.spin_height.value(),
            'manual_width_cm': self.spin_width.value(),  
            'weight_g': self.spin_weight.value(),
            'manual_length_cm': self.spin_length.value(),  
            'manual_weight_g': self.spin_weight.value(), 
            'measurement_type': 'manual',
            'notes': self.txt_notes.text().strip()
        }
        
        self.accept()
    
    def get_data(self):
        """Retorna los datos capturados."""
        return self.result_data