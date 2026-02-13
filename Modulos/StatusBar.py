"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Barra de Estado y Telemetría (StatusBar.py)
DESCRIPCIÓN: Widget personalizado que reside en la parte inferior de la ventana principal.
             Proporciona monitoreo en tiempo real de los recursos del sistema (CPU, RAM, GPU)
             y métricas de rendimiento de la aplicación (FPS, Latencia de Inferencia).
"""

import time
import os
import psutil
import logging
from typing import Optional, Final, Dict, Any
import qtawesome as qta  
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFrame, QPushButton, QApplication
from PySide6.QtCore import Slot, QTimer, Qt
from PySide6.QtGui import QCloseEvent

try:
    import pynvml 
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning, module="pynvml")
except ImportError:
    pynvml = None

logger = logging.getLogger(__name__)

class StatusBar(QWidget):
    
    HELP_TEXTS: Final[Dict[str, str]] = {
        "status": "Estado global del sistema.",
        "ia": "Latencia de inferencia por frame.",
        "fps": "Frames por segundo.",
        "cpu": "Uso total del procesador.",    
        "ram": "Uso de memoria RAM del proceso actual.",
        "gpu": "Uso de núcleos de procesamiento gráfico.", 
        "vram": "Uso de memoria de video.",
        "measurements": "Contador de mediciones validadas.",
        "cameras": "Estado de conexión de los sensores.",
        "api": "Estado de la API Cloud. Haz clic para copiar la URL pública."
    }

    UPDATE_INTERVAL_HW: Final[float] = 1.0  

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._current_api_url = None
        self._last_hw_update: float = 0.0
        self._process: psutil.Process = psutil.Process(os.getpid())
        self._gpu_handle: Any = None
        self._nvml_initialized: bool = False
        self.theme_colors: Dict[str, str] = {} 
        
        psutil.cpu_percent(interval=None) 

        self.setFixedHeight(35)
        self._init_hardware_monitors()
        self.init_ui()
        
        self.timer_hw = QTimer(self)
        self.timer_hw.timeout.connect(lambda: self.update_system_info())
        self.timer_hw.start(1000)

    def _init_hardware_monitors(self) -> None:
        if pynvml:
            try:
                pynvml.nvmlInit()
                self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self._nvml_initialized = True
            except Exception as e:
                logger.info(f"NVML no disponible: {e}.")
                self._gpu_handle = None

    def init_ui(self) -> None:
        self.layout_main = QHBoxLayout(self) 
        self.layout_main.setContentsMargins(15, 0, 15, 0)
        self.layout_main.setSpacing(10)
        self.setObjectName("StatusBar")
        
        # 1. Estado Global
        self.btn_status = self._create_metric("Iniciando...", "fa5s.info-circle", self.HELP_TEXTS["status"], "info")
        self.layout_main.addWidget(self.btn_status)
        self.layout_main.addStretch() 
        
        # API 
        self.btn_api = self._create_metric("API: --", "fa5s.globe", self.HELP_TEXTS["api"], "dim")
        self.btn_api.setProperty("interactive", True)
        self.btn_api.setCursor(Qt.PointingHandCursor)
        self.btn_api.clicked.connect(self._on_api_clicked)

        # 2. Telemetría
        self.btn_ia = self._create_metric("IA: -- ms", "fa5s.microchip", self.HELP_TEXTS["ia"], "info")
        self.btn_fps = self._create_metric("FPS: 0.0", "fa5s.film", self.HELP_TEXTS["fps"], "normal")
        
        # CPU / RAM
        self.btn_cpu = self._create_metric("CPU: 0%", "fa5s.server", self.HELP_TEXTS["cpu"], "dim")
        self.btn_ram = self._create_metric("RAM: -- MB", "fa5s.memory", self.HELP_TEXTS["ram"], "dim")
        
        # GPU 
        self.btn_gpu = self._create_metric("GPU: 0%", "fa5s.layer-group", self.HELP_TEXTS["gpu"], "accent") 
        self.btn_vram = self._create_metric("VRAM: -- MB", "fa5s.hdd", self.HELP_TEXTS["vram"], "accent")
        
        # Sensores
        self.btn_measurements = self._create_metric("Hoy: 0", "fa5s.ruler-horizontal", self.HELP_TEXTS["measurements"], "warning")
        self.btn_cameras = self._create_metric("--", "fa5s.video", self.HELP_TEXTS["cameras"], "normal")

        widgets_telemetry = [
            self.btn_ia, self.btn_fps, 
            self.btn_cpu, self.btn_ram,   
            self.btn_gpu, self.btn_vram,
            self.btn_measurements, self.btn_cameras,
            self.btn_api
        ]

        for i, w in enumerate(widgets_telemetry):
            if (w == self.btn_vram or w == self.btn_gpu) and not self._gpu_handle:
                w.hide()
            else:
                self.layout_main.addWidget(w)
                if i < len(widgets_telemetry) - 1:
                     line = QFrame()
                     line.setFrameShape(QFrame.Shape.VLine)
                     line.setObjectName("StatusSeparator") 
                     self.layout_main.addWidget(line)

    def _create_metric(self, text: str, icon_name: str, tooltip: str, initial_state: str) -> QPushButton:
        """Crea un botón plano configurado para parecer una etiqueta con icono"""
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFlat(True) 
        
        btn.setProperty("icon_name", icon_name)
        btn.setProperty("state", initial_state)
        
        return btn

    def update_theme_colors(self, palette: Dict[str, str]):
        """
        Actualiza el diccionario de colores y repinta todos los iconos.
        """
        self.theme_colors = palette
        for btn in self.findChildren(QPushButton):
            self._refresh_icon_color(btn)

    def _refresh_icon_color(self, btn: QPushButton):
        """Genera el icono nuevamente con el color correcto según el estado actual"""
        state = btn.property("state")
        icon_name = btn.property("icon_name")
        
        if not icon_name: return

        hex_color = self.theme_colors.get(state, "#7f8c8d")
        
        btn.setIcon(qta.icon(icon_name, color=hex_color))

    def _update_btn_state(self, btn: QPushButton, new_state: str):
        """Cambia el estado lógico, actualiza el estilo CSS y el color del icono"""
        if btn.property("state") != new_state:
            btn.setProperty("state", new_state)
            
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            
            self._refresh_icon_color(btn)

    @Slot(str, str)
    def set_status(self, message: str, state: str = "info"):
        clean = message.lstrip("● ") 
        self.btn_status.setText(clean)
        self._update_btn_state(self.btn_status, state)

    @Slot(float)
    def set_ia_time(self, ms: float):
        self.btn_ia.setText(f"IA: {ms:.1f}ms")
        state = "error" if ms > 3000 else "info"
        self._update_btn_state(self.btn_ia, state)

    @Slot(int)
    def set_measurement_count(self, count: int):
        self.btn_measurements.setText(f"Hoy: {count}")

    @Slot(bool)
    def set_camera_status(self, ok: bool):
        if ok:
            self.btn_cameras.setText("OK")
            self._update_btn_state(self.btn_cameras, "success") 
        else:
            self.btn_cameras.setText("ERROR")
            self._update_btn_state(self.btn_cameras, "error")   

    @Slot(float)
    def update_system_info(self, fps: Optional[float] = None):
        current_time = time.time()
        
        # 1. Actualizar FPS
        if fps is not None:
            self.btn_fps.setText(f"FPS: {fps:.1f}")
            state = "error" if fps < 15.0 else "normal"
            self._update_btn_state(self.btn_fps, state)

        # 2. Refresco Hardware
        if current_time - self._last_hw_update >= self.UPDATE_INTERVAL_HW:
            self._update_cpu_stats()
            self._update_gpu_stats()
            self._last_hw_update = current_time
            
    @Slot(str, str, str)
    def update_api_status(self, text: str, state: str, url: Optional[str]):
        self.btn_api.setText(f"API: {text}")
        self._current_api_url = url
        self._update_btn_state(self.btn_api, state)

    def _on_api_clicked(self):
        url_to_copy = getattr(self, "_current_api_url", None)
        if url_to_copy:
            if "localhost" in url_to_copy:
                 self.set_status("URL Local copiada", "warning")
            else:
                 self.set_status("URL Global copiada", "success")
            QApplication.clipboard().setText(url_to_copy)
        else:
            self.set_status("API no disponible", "error")
            
    def _update_cpu_stats(self) -> None:
        try:
            cpu = psutil.cpu_percent(interval=None) 
            self.btn_cpu.setText(f"CPU: {int(cpu)}%")
            
            if cpu > 85: self._update_btn_state(self.btn_cpu, "error")
            elif cpu > 60: self._update_btn_state(self.btn_cpu, "warning")
            else: self._update_btn_state(self.btn_cpu, "dim")

            mem = self._process.memory_info().rss / 1024**2
            self.btn_ram.setText(f"RAM: {int(mem)}MB")
        except: pass

    def _update_gpu_stats(self) -> None:
        if not self._gpu_handle: return
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
            self.btn_gpu.setText(f"GPU: {util.gpu}%")
            
            if util.gpu > 90: self._update_btn_state(self.btn_gpu, "warning")
            else: self._update_btn_state(self.btn_gpu, "accent")

            mem = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle).used / 1024**2
            self.btn_vram.setText(f"VRAM: {int(mem)}MB")
        except: pass

    def closeEvent(self, event: QCloseEvent):
        if self._nvml_initialized:
            try: pynvml.nvmlShutdown()
            except: pass
        event.accept()