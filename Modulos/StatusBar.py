import time
import os
import psutil
import logging
from typing import Optional, Final, Dict, Any

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Slot, QTimer
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
        "cameras": "Estado de conexión de los sensores."
    }

    UPDATE_INTERVAL_HW: Final[float] = 1.0  

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._last_hw_update: float = 0.0
        self._process: psutil.Process = psutil.Process(os.getpid())
        self._gpu_handle: Any = None
        self._nvml_initialized: bool = False
        
        # Llamada inicial a cpu_percent
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
                logger.info(f"NVML no disponible: {e}")
                self._gpu_handle = None

    def init_ui(self) -> None:
        self.layout_main = QHBoxLayout(self) 
        self.layout_main.setContentsMargins(15, 0, 15, 0)
        self.layout_main.setSpacing(10)
        self.setObjectName("StatusBar")
        
        # 1. Estado Global
        self.lbl_status = self._create_label("● Iniciando...", self.HELP_TEXTS["status"], "info")
        self.layout_main.addWidget(self.lbl_status)
        self.layout_main.addStretch()

        # 2. Telemetría
        self.lbl_ia_time = self._create_label("IA: -- ms", self.HELP_TEXTS["ia"], "info")
        self.lbl_fps = self._create_label("FPS: 0.0", self.HELP_TEXTS["fps"], "normal")
        
        # CPU / RAM
        self.lbl_cpu = self._create_label("CPU: 0%", self.HELP_TEXTS["cpu"], "dim")
        self.lbl_ram = self._create_label("RAM: -- MB", self.HELP_TEXTS["ram"], "dim")
        
        # GPU (state="accent" reemplaza a COLOR_GPU)
        self.lbl_gpu_load = self._create_label("GPU: 0%", self.HELP_TEXTS["gpu"], "accent") 
        self.lbl_vram = self._create_label("VRAM: -- MB", self.HELP_TEXTS["vram"], "accent")
        
        self.lbl_measurements = self._create_label("Hoy: 0", self.HELP_TEXTS["measurements"], "warning")
        self.lbl_cameras = self._create_label("📹 --", self.HELP_TEXTS["cameras"], "normal")

        # Agregamos widgets 
        widgets_telemetry = [
            self.lbl_ia_time, self.lbl_fps, 
            self.lbl_cpu, self.lbl_ram,   
            self.lbl_gpu_load, self.lbl_vram,
            self.lbl_measurements, self.lbl_cameras
        ]

        for i, w in enumerate(widgets_telemetry):
            if (w == self.lbl_vram or w == self.lbl_gpu_load) and not self._gpu_handle:
                w.hide()
            else:
                self.layout_main.addWidget(w)
                if i < len(widgets_telemetry) - 1:
                     line = QFrame()
                     line.setFrameShape(QFrame.Shape.VLine)
                     line.setObjectName("StatusSeparator") 
                     self.layout_main.addWidget(line)

    def _create_label(self, text: str, tooltip: str, state_type: str) -> QLabel:
        """Crea labels usando Propiedades Dinámicas"""
        lbl = QLabel(text)
        lbl.setToolTip(tooltip)
        lbl.setProperty("state", state_type) 
        return lbl

    # =========================================================================
    #  MÉTODOS PÚBLICOS (Slots) - LOGICA INTACTA, SOLO CAMBIA EL ESTILO
    # =========================================================================

    @Slot(str, str)
    def set_status(self, message: str, state: str = "info"):
        clean_message = message.lstrip("● ")
        self.lbl_status.setText(f"● {clean_message}")
        self._update_label_state(self.lbl_status, state)

    @Slot(float)
    def set_ia_time(self, ms: float):
        self.lbl_ia_time.setText(f"IA: {ms:.1f}ms")
        # Logica original: > 3000ms es peligro
        if ms > 3000:
            self._update_label_state(self.lbl_ia_time, "error") # error = COLOR_DANGER
        else:
            self._update_label_state(self.lbl_ia_time, "info")  # info = COLOR_INFO

    @Slot(int)
    def set_measurement_count(self, count: int):
        self.lbl_measurements.setText(f"Hoy: {count}")

    @Slot(bool)
    def set_camera_status(self, ok: bool):
        if ok:
            self.lbl_cameras.setText("📹 OK")
            self._update_label_state(self.lbl_cameras, "success") # success = COLOR_SUCCESS
        else:
            self.lbl_cameras.setText("📹 ERR")
            self._update_label_state(self.lbl_cameras, "error")   # error = COLOR_DANGER

    @Slot(float)
    def update_system_info(self, fps: Optional[float] = None):
        current_time = time.time()
        
        # 1. Actualizar FPS
        if fps is not None:
            self.lbl_fps.setText(f"FPS: {fps:.1f}")
            # Lógica original: < 15 FPS es peligro
            if fps < 15.0:
                self._update_label_state(self.lbl_fps, "error")
            else:
                self._update_label_state(self.lbl_fps, "normal") # normal = palette(text)

        # 2. Refresco Hardware
        if current_time - self._last_hw_update >= self.UPDATE_INTERVAL_HW:
            self._update_cpu_stats()
            self._update_gpu_stats()
            self._last_hw_update = current_time

    def _update_cpu_stats(self) -> None:
        try:
            # CPU 
            cpu_percent = psutil.cpu_percent(interval=None) 
            self.lbl_cpu.setText(f"CPU: {int(cpu_percent)}%")
            
            # Lógica original: > 85% Rojo, > 60% Amarillo
            if cpu_percent > 85:
                self._update_label_state(self.lbl_cpu, "error")
            elif cpu_percent > 60:
                self._update_label_state(self.lbl_cpu, "warning")
            else:
                self._update_label_state(self.lbl_cpu, "dim") # dim = COLOR_TEXT_DIM

            # RAM 
            mem_info = self._process.memory_info()
            mem_mb = mem_info.rss / 1024**2
            self.lbl_ram.setText(f"RAM: {int(mem_mb)}MB")
        except Exception as e:
            logger.debug(f"Error CPU stats: {e}", exc_info=True)

    def _update_gpu_stats(self) -> None:
        if not self._gpu_handle:
            return
            
        try:
            utilization = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
            gpu_load = utilization.gpu
            
            self.lbl_gpu_load.setText(f"GPU: {gpu_load}%")
            
            # Lógica original: > 90% Amarillo
            if gpu_load > 90:
                self._update_label_state(self.lbl_gpu_load, "warning")
            else:
                self._update_label_state(self.lbl_gpu_load, "accent") # accent = COLOR_GPU

            # VRAM
            info = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
            vram_mb = info.used / 1024**2
            self.lbl_vram.setText(f"VRAM: {int(vram_mb)}MB")
            
        except Exception as e:
            logger.debug(f"Error GPU Stats: {e}", exc_info=True)

    def closeEvent(self, event: QCloseEvent):
        if self._nvml_initialized:
            try:
                pynvml.nvmlShutdown()
            except: pass
        event.accept()

    # --- HELPER PRIVADO (La clave para que el estilo funcione) ---
    def _update_label_state(self, label: QLabel, new_state: str):
        if label.property("state") != new_state:
            label.setProperty("state", new_state)
            label.style().unpolish(label)
            label.style().polish(label)