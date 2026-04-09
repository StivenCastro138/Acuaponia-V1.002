"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Analizador Morfométrico (MorphometricAnalyzer.py)
DESCRIPCIÓN: Motor de cálculo científico. Transforma datos geométricos crudos (píxeles, 
             contornos, cajas) en variables biológicas precisas (gramos, cm, factor K).
             Implementa algoritmos híbridos que combinan modelos alométricos estadísticos 
             con aproximaciones volumétricas 3D.
"""

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
        Cálculo de ALTA PRECISIÓN con Compensación de Escorzo 3D.
        """
        l_lat_cm, h_cm, w_cm = 0.0, 0.0, 0.0
        length_top_support_cm = 0.0
        real_area_lat_cm2 = 0.0
        real_area_top_cm2 = 0.0
        curvature_index = 1.0
        is_bent = False

        if contour_lat is not None and len(contour_lat) >= 5:
            rect_lat = cv2.minAreaRect(contour_lat)
            (cx_lat, cy_lat), (width_lat, height_lat), angle_lat = rect_lat
            box_length_px = max(width_lat, height_lat)
            box_height_px = min(width_lat, height_lat)
            
            if spine_length_px and spine_length_px > 0:
                curvature_index = spine_length_px / box_length_px
                is_bent = curvature_index > Config.BENDING_THRESHOLD
                l_lat_cm = spine_length_px * scale_lat
            else:
                l_lat_cm = box_length_px * scale_lat

            h_cm = box_height_px * scale_lat
            real_area_lat_cm2 = cv2.contourArea(contour_lat) * (scale_lat ** 2)

        delta_z_cm = 0.0
        if contour_top is not None and len(contour_top) >= 5:
            rect_top = cv2.minAreaRect(contour_top)
            (cx_top, cy_top), (width_top, height_top), angle_top = rect_top

            w_cm = min(width_top, height_top) * scale_top
            length_top_support_cm = max(width_top, height_top) * scale_top

            delta_z_cm = length_top_support_cm
            real_area_top_cm2 = cv2.contourArea(contour_top) * (scale_top ** 2)
        else:
            w_cm = h_cm * Config.DEFAULT_WIDTH_RATIO
            real_area_top_cm2 = (l_lat_cm * w_cm) * 0.85 

        l_final_cm = MorphometricAnalyzer._fuse_supported_length(
            length_lat_cm=l_lat_cm,
            length_top_cm=length_top_support_cm
        )

        w_cm = MorphometricAnalyzer._stabilize_width(
            length=l_final_cm,
            height=h_cm,
            measured_width=w_cm,
            top_area=real_area_top_cm2,
            has_top_view=contour_top is not None and len(contour_top) >= 5
        )

        l_final_cm, h_cm, w_cm = MorphometricAnalyzer._apply_biological_constraints(l_final_cm, h_cm, w_cm)
        l_final_cm, h_cm, w_cm = MorphometricAnalyzer._apply_output_calibration(l_final_cm, h_cm, w_cm)
        
        metrics = {
            'length_cm': round(l_final_cm, 2),
            'height_cm': round(h_cm, 2),
            'width_cm': round(w_cm, 2),
            'length_top_support_cm': round(length_top_support_cm, 2),
            'curvature_index': round(curvature_index, 3),
            'is_bent': is_bent
        }
        
        metrics.update(MorphometricAnalyzer._calculate_derived_metrics(
            l_final_cm, h_cm, w_cm, real_area_lat_cm2, real_area_top_cm2, is_bent
        ))
        
        return metrics

    @staticmethod
    def estimate_from_dual_boxes(
        box_lat: Optional[Tuple[int, int, int, int]], 
        box_top: Optional[Tuple[int, int, int, int]], 
        scale_lat: float, 
        scale_top: float
    ) -> Dict[str, float]:
        """
        FALLBACK: Estimación con corrección de escorzo básica usando cajas.
        """
        if not box_lat: return MorphometricAnalyzer._calculate_derived_metrics(0,0,0)
        
        l_px_lat = abs(box_lat[2] - box_lat[0])
        h_px_lat = abs(box_lat[3] - box_lat[1])
        
        l_lat_cm = l_px_lat * scale_lat
        h_cm = h_px_lat * scale_lat
        
        w_cm = 0.0
        length_top_support_cm = 0.0
        if box_top:
            l_px_top = abs(box_top[2] - box_top[0])
            w_px_top = abs(box_top[3] - box_top[1])
            w_cm = min(l_px_top, w_px_top) * scale_top
            length_top_support_cm = max(l_px_top, w_px_top) * scale_top
        else:
            w_cm = h_cm * Config.DEFAULT_WIDTH_RATIO

        l_real_cm = MorphometricAnalyzer._fuse_supported_length(
            length_lat_cm=l_lat_cm,
            length_top_cm=length_top_support_cm
        )
        w_cm = MorphometricAnalyzer._stabilize_width(
            length=l_real_cm,
            height=h_cm,
            measured_width=w_cm,
            top_area=(l_real_cm * w_cm * 0.85) if w_cm > 0 else None,
            has_top_view=box_top is not None
        )
        l_real_cm, h_cm, w_cm = MorphometricAnalyzer._apply_biological_constraints(l_real_cm, h_cm, w_cm)
        l_real_cm, h_cm, w_cm = MorphometricAnalyzer._apply_output_calibration(l_real_cm, h_cm, w_cm)
        
        metrics = {
            'length_cm': round(l_real_cm, 2),
            'height_cm': round(h_cm, 2),
            'width_cm': round(w_cm, 2),
            'length_top_support_cm': round(length_top_support_cm, 2),
            'curvature_index': 1.0, 
            'is_bent': False
        }
        
        metrics.update(MorphometricAnalyzer._calculate_derived_metrics(
            l_real_cm, h_cm, w_cm,
            lat_area=(l_real_cm * h_cm * 0.65),
            top_area=(l_real_cm * w_cm * 0.85)
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
        width_for_volume = MorphometricAnalyzer._stabilize_width(
            length=length,
            height=height,
            measured_width=width,
            top_area=top_area,
            has_top_view=bool(top_area and top_area > 0)
        )
        volume = shape_coef * (math.pi / 6) * length * height * width_for_volume
        weight_vol = volume * density
        weight_vol = MorphometricAnalyzer._clamp_volumetric_weight(weight_vol, weight_stat)

        # --- 3. FUSIÓN OPTIMIZADA ---
        width_confidence = MorphometricAnalyzer._estimate_width_confidence(
            length=length,
            height=height,
            measured_width=width,
            top_area=top_area
        )
        alpha_low = Config.WEIGHT_ALPHA_LOW_CONF
        alpha_high = Config.WEIGHT_ALPHA_HIGH_CONF
        alpha = alpha_low - ((alpha_low - alpha_high) * width_confidence)
        if is_bent:
            alpha = min(0.97, alpha + 0.04)
        weight = (weight_stat * alpha) + (weight_vol * (1 - alpha))

        # --- 4. CORRECCIÓN POR LONGITUD ---
        if length < 14.5:
            weight *= Config.WEIGHT_SHORT_FISH_FACTOR
        elif length > 15.5:
            weight *= Config.WEIGHT_LONG_FISH_FACTOR

        # --- 5. CORRECCIÓN GLOBAL DE SESGO ---
        weight *= Config.WEIGHT_GLOBAL_BIAS

        # --- 6. AJUSTE FINAL DE PESO ---
        weight *= Config.WEIGHT_CORRECTION_FACTOR

        # --- 7. FACTOR DE CONDICIÓN ---
        k_factor = (100 * weight) / (length ** 3)

        return {
            'weight_g': round(weight, 2),
            'condition_factor': round(k_factor, 3),
            'volume_cm3': round(volume, 2),
            'lat_area_cm2': round(lat_area if lat_area else (length * height * 0.65), 2),
            'top_area_cm2': round(top_area if top_area else (length * width * 0.85), 2)
        }

    @staticmethod
    def _apply_output_calibration(length: float, height: float, width: float) -> Tuple[float, float, float]:
        """Aplica corrección global anti-sesgo sobre variables geométricas."""
        length_corr = max(0.0, length * float(Config.LENGTH_CORRECTION_FACTOR))
        height_corr = max(0.0, height * float(Config.HEIGHT_CORRECTION_FACTOR))
        width_corr = max(0.0, width * float(Config.WIDTH_CORRECTION_FACTOR))
        return length_corr, height_corr, width_corr

    @staticmethod
    def _fuse_supported_length(length_lat_cm: float, length_top_cm: float) -> float:
        """Usa la vista cenital solo como soporte conservador para no inflar longitud."""
        if length_lat_cm <= 0:
            return max(0.0, length_top_cm)
        if length_top_cm <= 0:
            return length_lat_cm

        discrepancy = abs(length_top_cm - length_lat_cm) / max(length_lat_cm, 1e-6)
        if discrepancy > float(Config.LENGTH_TOP_DISCREPANCY_RATIO):
            return length_lat_cm

        support_weight = float(Config.LENGTH_TOP_SUPPORT_WEIGHT)
        return (length_lat_cm * (1.0 - support_weight)) + (length_top_cm * support_weight)

    @staticmethod
    def _stabilize_width(
        length: float,
        height: float,
        measured_width: float,
        top_area: Optional[float] = None,
        has_top_view: bool = False
    ) -> float:
        """Regulariza el ancho usando anatomía esperada para evitar que contamine el peso."""
        if length <= 0:
            return max(0.0, measured_width)

        expected_width = height * float(Config.EXPECTED_WIDTH_HEIGHT_RATIO)
        min_width = length * float(Config.MIN_WIDTH_RATIO)
        max_width = length * float(Config.MAX_WIDTH_RATIO_ADULT)
        expected_width = max(min_width, min(max_width, expected_width))

        if measured_width <= 0 or not has_top_view:
            return expected_width

        confidence = MorphometricAnalyzer._estimate_width_confidence(
            length=length,
            height=height,
            measured_width=measured_width,
            top_area=top_area
        )
        return (measured_width * confidence) + (expected_width * (1.0 - confidence))

    @staticmethod
    def _estimate_width_confidence(
        length: float,
        height: float,
        measured_width: float,
        top_area: Optional[float] = None
    ) -> float:
        """Estima cuán confiable es el ancho cenital para usarlo en volumen/peso."""
        if length <= 0 or measured_width <= 0:
            return 0.0

        expected_width = height * float(Config.EXPECTED_WIDTH_HEIGHT_RATIO)
        min_width = length * float(Config.MIN_WIDTH_RATIO)
        max_width = length * float(Config.MAX_WIDTH_RATIO_ADULT)
        expected_width = max(min_width, min(max_width, expected_width))

        rel_error = abs(measured_width - expected_width) / max(expected_width, 1e-6)
        tolerance = max(0.05, float(Config.WIDTH_CONFIDENCE_TOLERANCE))
        confidence = max(0.0, 1.0 - (rel_error / tolerance))

        if top_area and top_area > 0 and measured_width > 0:
            occ = top_area / max(length * measured_width, 1e-6)
            if occ < Config.MIN_TOP_OCCUPANCY_RATIO or occ > Config.MAX_TOP_OCCUPANCY_RATIO:
                confidence *= 0.5

        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _clamp_volumetric_weight(weight_vol: float, weight_stat: float) -> float:
        """Evita que el componente volumétrico domine por errores geométricos aislados."""
        if weight_stat <= 0:
            return max(0.0, weight_vol)
        lower = weight_stat * float(Config.WEIGHT_VOL_LOWER_RATIO)
        upper = weight_stat * float(Config.WEIGHT_VOL_UPPER_RATIO)
        return max(lower, min(upper, weight_vol))

    @staticmethod
    def _apply_biological_constraints(l: float, h: float, w: float) -> Tuple[float, float, float]:
        """Límites anatómicos para filtrar basura."""
        if l <= 0: return 0.0, 0.0, 0.0
        
        max_h_ratio = Config.MAX_HEIGHT_RATIO
        max_w_ratio = Config.MAX_WIDTH_RATIO_ADULT
        
        h = min(h, l * max_h_ratio)
        w = min(w, l * max_w_ratio)
        return l, h, w