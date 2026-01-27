"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Motor de Detección en Tiempo Real (FishDetector.py)
DESCRIPCIÓN: Implementa algoritmos de visión por computadora para la segmentación 
             por color (Chroma Key). Cuenta con una arquitectura híbrida (CPU/GPU) 
             que utiliza aceleración CUDA cuando está disponible para maximizar los FPS.
"""

import cv2
import time 
import numpy as np
import logging

from Config.Config import Config
from .FishAnatomyValidator import FishAnatomyValidator

logger = logging.getLogger(__name__)

class FishDetector:
    def __init__(self):
        self.use_chroma_key = True

        self.kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.kernel_medium = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        self.anatomy_validator = FishAnatomyValidator()
        self.last_result_time = time.time()
        self.min_process_interval = 0.05  
        self._last_cached_mask = None

        self.use_cuda = False
        self.gpu_filter_morph_open = None
        self.gpu_filter_morph_close = None
        self.gpu_filter_gauss = None

        try:
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self.use_cuda = True
                # Filtro MORPH_OPEN 
                self.gpu_filter_morph_open = cv2.cuda.createMorphologyFilter(
                    cv2.MORPH_OPEN, cv2.CV_8UC1, self.kernel_small
                )
                # Filtro MORPH_CLOSE (
                self.gpu_filter_morph_close = cv2.cuda.createMorphologyFilter(
                    cv2.MORPH_CLOSE, cv2.CV_8UC1, self.kernel_medium
                )
                # Filtro Gaussiano
                self.gpu_filter_gauss = cv2.cuda.createGaussianFilter(
                    cv2.CV_8UC1, cv2.CV_8UC1, (3, 3), 0
                )
                logger.info("Aceleracion CUDA activada.")
            else:
                logger.warning("No se detecto CUDA. Usando CPU.")
        except Exception as e:
            logger.error(f"Error iniciando CUDA: {e}.")
            self.use_cuda = False

    def detect_fish_chroma_key(self, frame, camera_id='left'):
        """ Sin validación anatómica - Versión Híbrida CPU/GPU """
        current_time = time.time()

        if current_time - self.last_result_time < self.min_process_interval:
            if hasattr(self, '_last_cached_mask') and self._last_cached_mask is not None:
                return self._last_cached_mask
        
        self.last_result_time = current_time
        height, width = frame.shape[:2]

        mask_fish = None

        if self.use_cuda:
            try:
                mask_fish = self._process_gpu_pipeline(frame)
            except Exception as e:
                logger.error(f"Fallo en pipeline GPU, usando CPU: {e}")
                self.use_cuda = False 
                
        if mask_fish is None:
            mask_fish = self._process_cpu_pipeline(frame)

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
        
        # 3. Separar canales
        gpu_h, gpu_s, gpu_v = cv2.cuda.split(gpu_hsv)
        
        # 4. Thresholding paralelo por canal 
        _, gpu_h1 = cv2.cuda.threshold(gpu_h, Config.HSV_H_MIN, 255, cv2.THRESH_BINARY)
        _, gpu_h2 = cv2.cuda.threshold(gpu_h, Config.HSV_H_MAX, 255, cv2.THRESH_BINARY_INV)
        _, gpu_s1 = cv2.cuda.threshold(gpu_s, Config.HSV_S_MIN, 255, cv2.THRESH_BINARY)
        _, gpu_s2 = cv2.cuda.threshold(gpu_s, Config.HSV_S_MAX, 255, cv2.THRESH_BINARY_INV)
        _, gpu_v1 = cv2.cuda.threshold(gpu_v, Config.HSV_V_MIN, 255, cv2.THRESH_BINARY)
        _, gpu_v2 = cv2.cuda.threshold(gpu_v, Config.HSV_V_MAX, 255, cv2.THRESH_BINARY_INV)
        
        # 5. Combinar máscaras 
        gpu_mask = cv2.cuda.bitwise_and(gpu_h1, gpu_h2)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_s1)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_s2)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_v1)
        gpu_mask = cv2.cuda.bitwise_and(gpu_mask, gpu_v2)
        
        # 6. Invertir 
        gpu_mask_fish = cv2.cuda.bitwise_not(gpu_mask)
        
        # 7. Operaciones Morfológicas 
        gpu_mask_fish = self.gpu_filter_morph_open.apply(gpu_mask_fish)
        gpu_mask_fish = self.gpu_filter_morph_close.apply(gpu_mask_fish)
        
        # 8. Gaussian Blur
        gpu_mask_fish = self.gpu_filter_gauss.apply(gpu_mask_fish)
        
        # 9. Threshold final para binarizar tras el blur
        _, gpu_mask_fish = cv2.cuda.threshold(gpu_mask_fish, 200, 255, cv2.THRESH_BINARY)
        
        # 10. Download
        return gpu_mask_fish.download()

    def _process_cpu_pipeline(self, frame):
        """Pipeline original de CPU como respaldo"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        lower_green = np.array([Config.HSV_H_MIN, Config.HSV_S_MIN, Config.HSV_V_MIN])
        upper_green = np.array([Config.HSV_H_MAX, Config.HSV_S_MAX, Config.HSV_V_MAX])
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
        Config.HSV_H_MIN = h_min
        Config.HSV_H_MAX = h_max
        Config.HSV_S_MIN = s_min
        Config.HSV_S_MAX = s_max
        Config.HSV_V_MIN = v_min
        Config.HSV_V_MAX = v_max