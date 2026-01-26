import cv2
import time 
import numpy as np
import logging
from Config.Config import Config
from .FishAnatomyValidator import FishAnatomyValidator
from Modelos.AIDetector import AIDetector 

logger = logging.getLogger(__name__)

class FishDetector:
    def __init__(self):
        self.use_chroma_key = True
        
        # Rangos iniciales
        self.hue_min = 35
        self.hue_max = 85
        self.sat_min = 40
        self.sat_max = 255
        self.val_min = 40
        self.val_max = 255

        # Kernels para CPU (Fallback)
        self.kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.kernel_medium = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        self.anatomy_validator = FishAnatomyValidator()
        self.ai = AIDetector() 
        self.last_result_time = time.time()
        self.min_process_interval = 0.05  
        self._last_cached_mask = None

        # --- OPTIMIZACIÓN GPU (CUDA) ---
        self.use_cuda = False
        self.gpu_filter_morph_open = None
        self.gpu_filter_morph_close = None
        self.gpu_filter_gauss = None

        try:
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.use_cuda = True
                # Pre-compilar filtros en GPU (Lo hacemos una vez aquí, no en cada frame)
                # Filtro MORPH_OPEN (kernel pequeño)
                self.gpu_filter_morph_open = cv2.cuda.createMorphologyFilter(
                    cv2.MORPH_OPEN, cv2.CV_8UC1, self.kernel_small
                )
                # Filtro MORPH_CLOSE (kernel mediano)
                self.gpu_filter_morph_close = cv2.cuda.createMorphologyFilter(
                    cv2.MORPH_CLOSE, cv2.CV_8UC1, self.kernel_medium
                )
                # Filtro Gaussiano
                self.gpu_filter_gauss = cv2.cuda.createGaussianFilter(
                    cv2.CV_8UC1, cv2.CV_8UC1, (3, 3), 0
                )
                logger.info("FishDetector: Aceleracion CUDA activada.")
            else:
                logger.warning("FishDetector: No se detecto CUDA. Usando CPU.")
        except Exception as e:
            logger.error(f"Error iniciando CUDA en FishDetector: {e}")
            self.use_cuda = False

    def detect_fish_ai(self, frame):
        """ VERSIÓN POTENCIADA POR IA """
        height, width = frame.shape[:2]
        
        # 1. Pedir máscara a la IA (Asumimos que AIDetector maneja su propia aceleración interna)
        mask_ai = self.ai.get_fish_mask(frame)
        
        # 2. Si la IA no encontró nada, intentar Chroma Key tradicional (Optimizado)
        if np.sum(mask_ai) == 0:
            return self.detect_fish_chroma_key(frame)
            
        # 3. Limpieza post-IA
        # Nota: Si la IA devuelve CPU numpy, usamos CPU para morfología simple 
        # para evitar el costo de upload/download para una operación pequeña.
        mask_ai = cv2.morphologyEx(mask_ai, cv2.MORPH_CLOSE, 
                                   self.kernel_medium)
        
        # 4. Encontrar contorno
        contours, _ = cv2.findContours(mask_ai, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            roi = cv2.boundingRect(largest_contour)
            self._last_cached_mask = (mask_ai, roi)
            return mask_ai, roi
            
        return np.zeros((height, width), dtype=np.uint8), (0,0,width,height)

    def detect_fish_chroma_key(self, frame, camera_id='left'):
        """ Sin validación anatómica - Versión Híbrida CPU/GPU """
        current_time = time.time()
        
        # Control de framerate
        if current_time - self.last_result_time < self.min_process_interval:
            if hasattr(self, '_last_cached_mask') and self._last_cached_mask is not None:
                return self._last_cached_mask
        
        self.last_result_time = current_time
        height, width = frame.shape[:2]

        mask_fish = None

        # --- RAMA GPU ---
        if self.use_cuda:
            try:
                mask_fish = self._process_gpu_pipeline(frame)
            except Exception as e:
                logger.error(f"Fallo en pipeline GPU, usando CPU: {e}")
                self.use_cuda = False # Desactivar si falla para evitar crash loop
        
        # --- RAMA CPU (Fallback) ---
        if mask_fish is None:
            mask_fish = self._process_cpu_pipeline(frame)

        # --- POST-PROCESAMIENTO (Común en CPU) ---
        # findContours no existe en Python CUDA, así que siempre lo hacemos en CPU
        # al final. La ganancia está en que la máscara ya llega lista.
        contours, _ = cv2.findContours(mask_fish, cv2.RETR_EXTERNAL, 
                                     cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            valid_contours = [c for c in contours 
                            if Config.MIN_CONTOUR_AREA <= cv2.contourArea(c) <= Config.MAX_CONTOUR_AREA]
            
            if valid_contours:
                largest_contour = max(valid_contours, key=cv2.contourArea)
                
                # Crear máscara limpia final
                mask_clean = np.zeros_like(mask_fish)
                cv2.drawContours(mask_clean, [largest_contour], -1, 255, -1)
                
                # Suavizado final muy leve
                mask_clean = cv2.GaussianBlur(mask_clean, (3, 3), 0)
                mask_clean = cv2.threshold(mask_clean, 200, 255, cv2.THRESH_BINARY)[1]
                
                roi = (0, 0, width, height)
                self._last_cached_mask = (mask_clean, roi)
                
                return mask_clean, roi
        
        # No se encontró pez
        empty_mask = np.zeros((height, width), dtype=np.uint8)
        roi = (0, 0, width, height)
        
        self._last_cached_mask = (empty_mask, roi)
        return empty_mask, roi

    def _process_gpu_pipeline(self, frame):
        """Pipeline completo de procesamiento de imagen en GPU"""
        # 1. Upload
        gpu_frame = cv2.cuda_GpuMat()
        gpu_frame.upload(frame)
        
        # 2. Convertir a HSV
        gpu_hsv = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_BGR2HSV)
        
        # 3. Separar canales (Split) para simular inRange
        gpu_h, gpu_s, gpu_v = cv2.cuda.split(gpu_hsv)
        
        # 4. Thresholding paralelo por canal (Simulación de inRange)
        # HUE
        _, gpu_h1 = cv2.cuda.threshold(gpu_h, self.hue_min, 255, cv2.THRESH_BINARY)
        _, gpu_h2 = cv2.cuda.threshold(gpu_h, self.hue_max, 255, cv2.THRESH_BINARY_INV)
        # SAT
        _, gpu_s1 = cv2.cuda.threshold(gpu_s, self.sat_min, 255, cv2.THRESH_BINARY)
        _, gpu_s2 = cv2.cuda.threshold(gpu_s, self.sat_max, 255, cv2.THRESH_BINARY_INV)
        # VAL
        _, gpu_v1 = cv2.cuda.threshold(gpu_v, self.val_min, 255, cv2.THRESH_BINARY)
        _, gpu_v2 = cv2.cuda.threshold(gpu_v, self.val_max, 255, cv2.THRESH_BINARY_INV)
        
        # 5. Combinar máscaras (Bitwise AND)
        # Esto es muy rápido en GPU
        gpu_mask = cv2.cuda.bitwise_and(gpu_h1, gpu_h2)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_s1)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_s2)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_v1)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_v2)
        
        # 6. Invertir (Bitwise NOT)
        gpu_mask_fish = cv2.cuda.bitwise_not(gpu_mask)
        
        # 7. Operaciones Morfológicas (Usando filtros pre-compilados)
        gpu_mask_fish = self.gpu_filter_morph_open.apply(gpu_mask_fish)
        gpu_mask_fish = self.gpu_filter_morph_close.apply(gpu_mask_fish)
        
        # 8. Gaussian Blur
        gpu_mask_fish = self.gpu_filter_gauss.apply(gpu_mask_fish)
        
        # 9. Threshold final para binarizar tras el blur
        _, gpu_mask_fish = cv2.cuda.threshold(gpu_mask_fish, 200, 255, cv2.THRESH_BINARY)
        
        # 10. Download (Solo descargamos la máscara binaria final, muy ligero)
        return gpu_mask_fish.download()

    def _process_cpu_pipeline(self, frame):
        """Pipeline original de CPU como respaldo"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        lower_green = np.array([self.hue_min, self.sat_min, self.val_min])
        upper_green = np.array([self.hue_max, self.sat_max, self.val_max])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        mask_fish = cv2.bitwise_not(mask_green)
        
        mask_fish = cv2.morphologyEx(mask_fish, cv2.MORPH_OPEN, 
                                     self.kernel_small, iterations=1)
        mask_fish = cv2.morphologyEx(mask_fish, cv2.MORPH_CLOSE, 
                                     self.kernel_medium, iterations=1)
        
        mask_fish = cv2.GaussianBlur(mask_fish, (3, 3), 0)
        mask_fish = cv2.threshold(mask_fish, 200, 255, cv2.THRESH_BINARY)[1]
        
        return mask_fish

    def compute_confidence_score(self, contour, mask, frame):
        """ Cálculo simplificado (CPU) """
        if contour is None or len(contour) < 5:
            return 0.0
        
        try:
            area = cv2.contourArea(contour)
            
            # Área válida
            if Config.MIN_CONTOUR_AREA <= area <= Config.MAX_CONTOUR_AREA:
                area_score = 0.9
            else:
                area_score = 0.5
            
            # Aspect ratio
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = max(w, h) / max(min(w, h), 1)
            
            if 2.5 <= aspect_ratio <= 5.0:
                aspect_score = 1.0
            else:
                aspect_score = 0.6
            
            # Score final
            return (area_score * 0.6 + aspect_score * 0.4)
            
        except:
            return 0.5
        
    def set_hsv_ranges(self, h_min, h_max, s_min, s_max, v_min, v_max):
        """
        Actualiza dinámicamente los rangos de color.
        """
        self.hue_min = h_min
        self.hue_max = h_max
        self.sat_min = s_min
        self.sat_max = s_max
        self.val_min = v_min
        self.val_max = v_max