"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Refinador de Segmentación Basado en SAM (SegmentationRefiner.py)
DESCRIPCIÓN: Implementa el modelo 'Segment Anything Model' (Meta AI) para convertir
             cajas delimitadoras (Bounding Boxes) en máscaras binarias de alta precisión.
             Es fundamental para separar el cuerpo del pez del fondo y de sus propias aletas.
"""

import cv2
import numpy as np
import logging
import torch
import gc
from typing import Optional, List
from ultralytics import SAM

logger = logging.getLogger(__name__)

class SegmentationRefiner:
    """
    Refinador de siluetas de alta precisión basado en SAM (Segment Anything Model).
    """
    
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = None
        self._init_model()

    def _init_model(self):
        """Carga el modelo apropiado según el hardware."""
        if self.device == 'cuda':
            torch.cuda.empty_cache()
            gpu_name = torch.cuda.get_device_name(0)
            logger.info("[SAM-GPU] NVIDIA %s vinculada.", gpu_name)

            self.model_name = "sam_l.pt" 
        else:
            logger.info("[SAM-CPU] Usando modo ligero (MobileSAM).")
            self.model_name = "mobile_sam.pt"

        try:
            self.model = SAM(self.model_name)
            if self.device == 'cuda':
                dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
                self.model.predict(source=dummy_img, verbose=False)
        except Exception as e:
            logger.error("Error critico cargando SAM.", exc_info=True)
            self.model = None

    def get_body_mask(self, image_bgr: np.ndarray, box: List[int]) -> Optional[np.ndarray]:
        """
        Segmenta el pez y limpia aletas/ruido SIN reducir el tamaño del cuerpo.
        """
        if self.model is None or box is None or image_bgr is None: 
            return None

        try:
            use_half = (self.device == 'cuda')

            with torch.no_grad():
                results = self.model.predict(
                    source=image_bgr,
                    bboxes=[box], 
                    device=self.device,
                    retina_masks=False,  
                    verbose=False,
                    conf=0.5,
                    half=use_half
                )

            if not results or results[0].masks is None:
                return None

            mask_raw = results[0].masks.data[0].cpu().numpy()
            
            h_img, w_img = image_bgr.shape[:2]
            mask_uint8 = (mask_raw * 255).astype(np.uint8)
            
            if mask_uint8.shape[:2] != (h_img, w_img):
                mask_uint8 = cv2.resize(mask_uint8, (w_img, h_img), interpolation=cv2.INTER_NEAREST)

            
            # 1. Filtrado de Componentes 
            mask_clean = self._keep_largest_blob(mask_uint8)
            if mask_clean is None: return None

            # 2. Limpieza de Aletas 
            w_box = abs(box[2] - box[0])
            h_box = abs(box[3] - box[1])
            min_dim = min(w_box, h_box)
            
            k_size = max(3, int(min_dim * 0.03)) 
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
            
            body_mask_refined = cv2.morphologyEx(mask_clean, cv2.MORPH_OPEN, kernel, iterations=1)

            area_orig = cv2.countNonZero(mask_clean)
            area_new = cv2.countNonZero(body_mask_refined)
            
            if area_new == 0 or area_new < (area_orig * 0.8):
                logger.debug("Refinamiento demasiado agresivo, usando mascara base.")
                return mask_clean

            return body_mask_refined

        except Exception as e:
            logger.error("Error en pipeline de segmentación SAM.", exc_info=True)
            return None

    def _keep_largest_blob(self, mask: np.ndarray) -> Optional[np.ndarray]:
        """Mantiene solo el objeto blanco más grande (el pez)."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return None
        
        largest_cnt = max(contours, key=cv2.contourArea)
        
        if cv2.contourArea(largest_cnt) < 100: return None
        
        clean_mask = np.zeros_like(mask)
        cv2.drawContours(clean_mask, [largest_cnt], -1, 255, thickness=cv2.FILLED)
        return clean_mask

    def get_box_and_contour(self, image, box_moondream):
        """Calcula la caja técnica refinada por segmentación."""
        mask = self.get_body_mask(image, box_moondream)
        
        if mask is None:
            return box_moondream, None
            
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return box_moondream, None
            
        best_cnt = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(best_cnt)
        
        return (x, y, x+w, y+h), best_cnt

    def __del__(self):
        """Limpieza segura de recursos GPU."""
        try:
            if self.model:
                del self.model
            if hasattr(self, 'device') and self.device == 'cuda':
                torch.cuda.empty_cache()
                gc.collect()
        except Exception as e:
            logger.error("Error liberando recursos SAM.", exc_info=True)