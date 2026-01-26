import cv2
import numpy as np
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

class SimpleMotionDetector:
    """
    Detector de estabilidad visual optimizado con NVIDIA CUDA.
    Mantiene los frames en la VRAM de la GPU para evitar descargas innecesarias.
    """
    
    def __init__(self, threshold: float = 8.0, history_size: int = 5, proc_width: int = 320):
        """
        Args:
            threshold: Sensibilidad (Más bajo = detecta movimientos más sutiles).
            history_size: Cuántos cuadros deben ser estables para dar el OK.
            proc_width: Ancho interno de procesamiento.
        """
        self.threshold = threshold 
        self.history_size = history_size
        self.proc_width = proc_width
        
        # Estado interno
        self.motion_history: deque = deque(maxlen=history_size)
        self.current_motion_val: float = 0.0
        
        # --- OPTIMIZACIÓN GPU ---
        self.use_cuda = False
        self.last_gpu_frame: Optional[cv2.cuda_GpuMat] = None
        self.gpu_filter = None

        try:
            # Intentar inicializar recursos CUDA
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.gpu_filter = cv2.cuda.createGaussianFilter(cv2.CV_8UC1, cv2.CV_8UC1, (15, 15), 0)
                self.use_cuda = True
                logger.info("SimpleMotionDetector: Aceleracion CUDA activada.")
            else:
                logger.warning("SimpleMotionDetector: No se detecto dispositivo CUDA. Usando CPU.")
        except Exception as e:
            logger.error(f"Error inicializando CUDA: {e}. Se usara CPU.")

        # Fallback para CPU
        self.last_frame_cpu: Optional[np.ndarray] = None
        
        logger.debug(
            "SimpleMotionDetector init | threshold=%.2f history=%d width=%d CUDA=%s",
            threshold, history_size, proc_width, self.use_cuda
        )
    
    def is_stable(self, frame: np.ndarray) -> bool:
        """
        Procesa un frame y determina si la escena está estática.
        """
        if frame is None or frame.size == 0:
            logger.warning("Frame invalido recibido en motion detector")
            return False
        
        if self.use_cuda:
            return self._is_stable_gpu(frame)
        else:
            return self._is_stable_cpu(frame)

    def _is_stable_gpu(self, frame: np.ndarray) -> bool:
        # 1. Upload a GPU (Única transferencia grande)
        gpu_frame = cv2.cuda_GpuMat()
        gpu_frame.upload(frame)
        
        # 2. Pipeline en GPU
        processed_gpu = self._preprocess_frame_gpu(gpu_frame)
        
        # Si es el primer frame, guardamos referencia en VRAM y salimos
        if self.last_gpu_frame is None:
            self.last_gpu_frame = processed_gpu
            return False
            
        # 3. Diferencia Absoluta en GPU
        gpu_diff = cv2.cuda.absdiff(self.last_gpu_frame, processed_gpu)
        
        # 4. Cálculo de media (Optimizado: calcSum evita descargar toda la imagen)
        # calcSum retorna (suma_canal1, suma_canal2, ...)
        diff_sum = cv2.cuda.calcSum(gpu_diff)[0]
        
        # Calculamos el promedio dividiendo por el número de píxeles
        size = processed_gpu.size()
        pixel_count = size[0] * size[1]
        self.current_motion_val = diff_sum / pixel_count if pixel_count > 0 else 0.0
        
        # 5. Actualizar referencia (Puntero en GPU)
        self.last_gpu_frame = processed_gpu
        
        return self._check_history_logic()

    def _preprocess_frame_gpu(self, gpu_frame: cv2.cuda_GpuMat) -> cv2.cuda_GpuMat:
        """Pipeline de limpieza de imagen ejecutado 100% en la tarjeta gráfica."""
        size = gpu_frame.size() # (width, height)
        w, h = size
        
        # Resize
        if w != self.proc_width:
            scale = self.proc_width / float(w)
            new_h = int(h * scale)
            gpu_small = cv2.cuda.resize(gpu_frame, (self.proc_width, new_h), interpolation=cv2.INTER_NEAREST)
        else:
            gpu_small = gpu_frame

        # Convertir a grises
        gpu_gray = cv2.cuda.cvtColor(gpu_small, cv2.COLOR_BGR2GRAY)
        
        # Blur (usando el filtro pre-compilado)
        return self.gpu_filter.apply(gpu_gray)

    def _is_stable_cpu(self, frame: np.ndarray) -> bool:
        """Lógica original de CPU como respaldo"""
        processed = self._preprocess_frame_cpu(frame)
        
        if self.last_frame_cpu is None:
            self.last_frame_cpu = processed
            return False
            
        frame_delta = cv2.absdiff(self.last_frame_cpu, processed)
        self.current_motion_val = np.mean(frame_delta)
        self.last_frame_cpu = processed 
        
        return self._check_history_logic()

    def _preprocess_frame_cpu(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w != self.proc_width:
            scale = self.proc_width / float(w)
            new_h = int(h * scale)
            small = cv2.resize(frame, (self.proc_width, new_h), interpolation=cv2.INTER_NEAREST)
        else:
            small = frame
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (15, 15), 0)

    def _check_history_logic(self) -> bool:
        """Lógica compartida de evaluación de historial"""
        self.motion_history.append(self.current_motion_val)
        
        if len(self.motion_history) < self.history_size:
            return False

        avg_history = np.mean(self.motion_history)
        is_stable_now = (self.current_motion_val < self.threshold)
        is_stable_trend = (avg_history < self.threshold)
        
        return is_stable_now and is_stable_trend
    
    def get_motion_level(self) -> float:
        """Retorna un valor normalizado 0-100 para la UI."""
        if not self.motion_history:
            return 0.0
        val = np.mean(self.motion_history)
        normalized = min(100.0, val * 4.0)
        return round(normalized, 1)
    
    def get_raw_metric(self) -> float:
        return round(self.current_motion_val, 2)
    
    def reset(self):
        """Reinicia el detector liberando memoria GPU."""
        self.last_gpu_frame = None
        self.last_frame_cpu = None
        self.motion_history.clear()
        self.current_motion_val = 0.0
        logger.debug("Motion detector reset")