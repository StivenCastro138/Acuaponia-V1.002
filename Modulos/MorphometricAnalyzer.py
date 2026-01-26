import math
import cv2
import numpy as np
import logging
from typing import Dict, Optional, Tuple
from Config.Config import Config

logger = logging.getLogger(__name__)

class MorphometricAnalyzer:
    """
    Motor de cálculo científico para biometría de peces.
    """

    @staticmethod
    def compute_advanced_metrics(
        contour_lat: Optional[np.ndarray], 
        contour_top: Optional[np.ndarray], 
        scale_lat: float, 
        scale_top: float,
        spine_length_px: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Cálculo de ALTA PRECISIÓN con detección de dobleces y Áreas 3D.
        """
        l_cm, h_cm, w_cm = 0.0, 0.0, 0.0
        real_area_lat_cm2 = 0.0
        real_area_top_cm2 = 0.0
        curvature_index = 1.0
        is_bent = False
        
        # ------------------------------------------------------------
        # 1. ANÁLISIS VISTA LATERAL (Perfil)
        # ------------------------------------------------------------
        if contour_lat is not None and len(contour_lat) >= 5:
            rect_lat = cv2.minAreaRect(contour_lat)
            (dim1, dim2) = rect_lat[1]
            
            box_length_px = max(dim1, dim2)
            box_height_px = min(dim1, dim2)
            
            # --- DETECCIÓN DE DOBLECES ---
            if spine_length_px and spine_length_px > 0:
                curvature_index = spine_length_px / box_length_px

                if curvature_index > Config.BENDING_THRESHOLD:
                    is_bent = True
                    logger.debug(f"Curvatura detectada. Indice={curvature_index:.3f}")

                l_cm = spine_length_px * scale_lat
            else:
                l_cm = box_length_px * scale_lat

            h_cm = box_height_px * scale_lat

            # ✅ CÁLCULO ÁREA LATERAL
            area_px = cv2.contourArea(contour_lat)
            real_area_lat_cm2 = area_px * (scale_lat ** 2)

        # ------------------------------------------------------------
        # 2. ANÁLISIS VISTA CENITAL (Dorso)
        # ------------------------------------------------------------
        if contour_top is not None and len(contour_top) >= 5:
            rect_top = cv2.minAreaRect(contour_top)
            (dim1_t, dim2_t) = rect_top[1]
            w_cm = min(dim1_t, dim2_t) * scale_top
            
            # ✅ CÁLCULO ÁREA CENITAL
            area_top_px = cv2.contourArea(contour_top)
            real_area_top_cm2 = area_top_px * (scale_top ** 2)
        else:
            # Estimación si falla la vista superior
            w_ratio = Config.DEFAULT_WIDTH_RATIO
            w_cm = h_cm * w_ratio
            # Estimación de área cenital basada en rectángulo teórico
            real_area_top_cm2 = (l_cm * w_cm) * 0.85 

        # ------------------------------------------------------------
        # 3. RESTRICCIONES Y CÁLCULO FINAL
        # ------------------------------------------------------------
        l_cm, h_cm, w_cm = MorphometricAnalyzer._apply_biological_constraints(l_cm, h_cm, w_cm)
        
        metrics = {
            'length_cm': round(l_cm, 2),
            'height_cm': round(h_cm, 2),
            'width_cm': round(w_cm, 2),
            'curvature_index': round(curvature_index, 3),
            'is_bent': is_bent
        }
        
        # Calcular biomasa pasando ambas áreas
        derived = MorphometricAnalyzer._calculate_derived_metrics(
            length=l_cm, 
            height=h_cm, 
            width=w_cm, 
            lat_area=real_area_lat_cm2,
            top_area=real_area_top_cm2,
            is_bent=is_bent
        )
        metrics.update(derived)
        
        return metrics

    @staticmethod
    def estimate_from_dual_boxes(
        box_lat: Optional[Tuple[int, int, int, int]], 
        box_top: Optional[Tuple[int, int, int, int]], 
        scale_lat: float, 
        scale_top: float
    ) -> Dict[str, float]:
        """
        FALLBACK: Estimación rápida basada en cajas.
        """
        if not box_lat: 
            return MorphometricAnalyzer._calculate_derived_metrics(0,0,0)
        
        w_box_lat = abs(box_lat[2] - box_lat[0])
        h_box_lat = abs(box_lat[3] - box_lat[1])
        
        l_cm = max(w_box_lat, h_box_lat) * scale_lat
        h_cm = min(w_box_lat, h_box_lat) * scale_lat
        
        # Estimación básica de área lateral (rectángulo * factor de forma pez)
        est_lat_area = (l_cm * h_cm) * 0.65
        
        w_cm = 0.0
        est_top_area = 0.0
        
        if box_top:
            w_box_top = abs(box_top[2] - box_top[0])
            h_box_top = abs(box_top[3] - box_top[1])
            w_cm = min(w_box_top, h_box_top) * scale_top
            est_top_area = (l_cm * w_cm) * 0.85
        else:
            w_ratio = Config.DEFAULT_WIDTH_RATIO
            w_cm = h_cm * w_ratio
            est_top_area = (l_cm * w_cm) * 0.85

        l_cm, h_cm, w_cm = MorphometricAnalyzer._apply_biological_constraints(l_cm, h_cm, w_cm)
        
        metrics = {
            'length_cm': round(l_cm, 2),
            'height_cm': round(h_cm, 2),
            'width_cm': round(w_cm, 2),
            'curvature_index': 1.0, 
            'is_bent': False
        }
        
        metrics.update(MorphometricAnalyzer._calculate_derived_metrics(
            l_cm, h_cm, w_cm, 
            lat_area=est_lat_area, 
            top_area=est_top_area
        ))
        
        return metrics

    @staticmethod
    def _calculate_derived_metrics(
        length: float, 
        height: float, 
        width: float, 
        lat_area: Optional[float] = None,
        top_area: Optional[float] = None,
        is_bent: bool = False
    ) -> Dict[str, float]:
        """
        Núcleo optimizado para coincidir con la Base de Datos.
        """
        if length <= 0.1:
            return {
                'weight_g': 0.0,
                'condition_factor': 0.0,
                'volume_cm3': 0.0,
                'lat_area_cm2': 0.0,
                'top_area_cm2': 0.0
            }

        # --- 1. MODELO LONGITUD–PESO ---
        k = Config.WEIGHT_K
        exp = Config.WEIGHT_EXP
        weight_stat = k * (length ** exp)

        # --- 2. MODELO VOLUMÉTRICO ---
        density = Config.TROUT_DENSITY
        shape_coef = Config.FORM_FACTOR
        volume = shape_coef * (math.pi / 6) * length * height * width
        weight_vol = volume * density

        # --- 3. FUSIÓN OPTIMIZADA ---
        alpha = 0.94 if is_bent else 0.88
        weight = (weight_stat * alpha) + (weight_vol * (1 - alpha))

        # --- 4. CORRECCIÓN POR LONGITUD ---
        if length < 14.5:
            weight *= 0.90
        elif length > 15.5:
            weight *= 1.12

        # --- 5. FACTOR DE CONDICIÓN ---
        k_factor = (100 * weight) / (length ** 3)

        # ✅ NOMBRES CORRECTOS PARA BASE DE DATOS
        return {
            'weight_g': round(weight, 2),
            'condition_factor': round(k_factor, 3),
            'volume_cm3': round(volume, 2),
            'lat_area_cm2': round(lat_area if lat_area else (length * height * 0.65), 2),
            'top_area_cm2': round(top_area if top_area else (length * width * 0.85), 2)
        }

    @staticmethod
    def _apply_biological_constraints(l: float, h: float, w: float) -> Tuple[float, float, float]:
        """Límites anatómicos para filtrar basura."""
        if l <= 0: return 0.0, 0.0, 0.0
        
        max_h_ratio = Config.MAX_HEIGHT_RATIO
        max_w_ratio = Config.MAX_WIDTH_RATIO_ADULT
        
        h = min(h, l * max_h_ratio)
        w = min(w, l * max_w_ratio)
        return l, h, w