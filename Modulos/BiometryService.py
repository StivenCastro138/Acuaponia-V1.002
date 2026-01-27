"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Servicio de Lógica Biométrica (BiometryService.py)
DESCRIPCIÓN: Controlador principal de la lógica de negocio. Orquestador que coordina:
             1. La detección por IA (AdvancedDetector).
             2. La conversión fotogramétrica (Píxeles -> Centímetros).
             3. La estimación volumétrica y de peso.
             4. La validación de calidad de los datos (QA/QC).
"""

import cv2
import logging
import numpy as np
from typing import Optional, Tuple, Dict

from Config.Config import Config
from .MorphometricAnalyzer import MorphometricAnalyzer
from .MeasurementValidator import MeasurementValidator

logger = logging.getLogger(__name__)

class BiometryService:
    """
    Fachada que simplifica el proceso de medición para la interfaz gráfica.
    Encapsula toda la complejidad del análisis de estereovisión.
    """

    def __init__(self, advanced_detector):
        self.detector = advanced_detector

    def analyze_and_annotate(
        self, 
        img_lat: np.ndarray, 
        img_top: np.ndarray, 
        scale_lat_front: float, 
        scale_lat_back: float, 
        scale_top_front: float, 
        scale_top_back: float, 
        draw_box: bool = True, 
        draw_skeleton: bool = True
    ) -> Tuple[Optional[Dict[str, float]], np.ndarray, np.ndarray]:
        """
        Flujo Maestro de Análisis Biométrico.
        
        Realiza el análisis simultáneo de vistas lateral y cenital, fusiona los datos
        geométricos y genera las visualizaciones para el usuario.
        """
        
        if img_lat is None or img_top is None:
            logger.error("Imagenes de entrada son None.")
            return None, img_lat, img_top

        if not self._is_detector_ready():
            logger.error("Detector IA no listo o no asignado.")
            return None, img_lat, img_top

        try:
            # ============================================================
            # FASE 1: DETECCIÓN Y SEGMENTACIÓN (Deep Learning)
            # ============================================================
            res_lat = self.detector.analyze_frame(img_lat)
            res_top = self.detector.analyze_frame(img_top)

            if not res_lat or not res_lat.bbox:
                logger.warning("No se detecto pez en vista lateral.")
                return None, img_lat, img_top

            has_top = res_top and res_top.bbox is not None
            if not has_top:
                logger.warning("No se detecto pez en vista cenital. Se limitara el calculo.")

            # ============================================================
            # FASE 2: FOTOGRAMETRÍA (Cálculo de Escalas Dinámicas)
            # ============================================================
            y_center_lat = (res_lat.bbox[1] + res_lat.bbox[3]) / 2
            px_to_cm_lat = Config.calcular_escala_proporcional(
                valor_y=y_center_lat,
                max_y=img_lat.shape[0],
                escala_frente=scale_lat_front,
                escala_fondo=scale_lat_back
            )

            px_to_cm_top = 0.0
            if has_top:
                y_center_top = (res_top.bbox[1] + res_top.bbox[3]) / 2
                px_to_cm_top = Config.calcular_escala_proporcional(
                    valor_y=y_center_top,
                    max_y=img_top.shape[0],
                    escala_frente=scale_top_front,
                    escala_fondo=scale_top_back
                )

            if px_to_cm_lat <= 0:
                logger.error(f"Escala lateral invalida: {px_to_cm_lat}. Abortando medicion.")
                return None, img_lat, img_top

            # ============================================================
            # 3. ESTIMACIÓN BIOMÉTRICA (cm)
            # ============================================================
            metrics = MorphometricAnalyzer.estimate_from_dual_boxes(
                box_lat=res_lat.bbox,
                box_top=res_top.bbox if has_top else None, 
                scale_lat=px_to_cm_lat,
                scale_top=px_to_cm_top
            )

            # ============================================================
            # 4. REFINAMIENTO CON ESQUELETO 
            # ============================================================
            spine_cm_lat = res_lat.spine_length * px_to_cm_lat
            spine_cm_top = (res_top.spine_length * px_to_cm_top) if has_top else 0.0

            current_len = metrics.get('length_cm', 0)
            best_length = max(current_len, spine_cm_lat, spine_cm_top)
            
            if best_length > 0:
                metrics['length_cm'] = round(best_length, 2)
                
                derived = MorphometricAnalyzer._calculate_derived_metrics(
                    length=metrics['length_cm'],
                    height=metrics.get('height_cm', 0),
                    width=metrics.get('width_cm', 0)
                )
                metrics.update(derived)

            # ============================================================
            # 5. VALIDACIÓN 
            # ============================================================
            warnings = MeasurementValidator.validate_measurement(metrics)
            if warnings:
                logger.info(f"Validacion biometrica warnings: {warnings}.")
                metrics['_warnings'] = warnings

            # ============================================================
            # 6. ANOTACIÓN VISUAL
            # ============================================================
            img_lat_ann = self._draw_result(img_lat, res_lat, (255, 255, 0), "LAT", draw_box, draw_skeleton)
            
            img_top_ann = img_top.copy()
            if has_top:
                img_top_ann = self._draw_result(img_top, res_top, (255, 120, 0), "TOP", draw_box, draw_skeleton)
            
            return metrics, img_lat_ann, img_top_ann

        except Exception as e:
            logger.error(f"Error critico: {e}", exc_info=True)
            return None, img_lat, img_top

    def _draw_result(self, image: np.ndarray, result, color: Tuple[int,int,int], label: str, show_box: bool, show_skel: bool) -> np.ndarray:
        """
        Motor de renderizado para visualización de datos en pantalla (On-Screen Display).
        Dibuja cajas, textos y morfología sobre la imagen original.
        """
        if result is None or image is None: 
            return image
        
        vis = image.copy()
        h, w = vis.shape[:2]
        
        # Factores dinámicos
        thickness = max(2, int(w / 600))
        font_scale = max(0.6, w / 1200)

        # 1. Contorno 
        if result.contour is not None:
             cv2.drawContours(vis, [result.contour], -1, color, 1)

        # 2. Caja 
        if show_box and result.bbox:
            x1, y1, x2, y2 = result.bbox
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)
            
            # Etiqueta
            txt = f"{label}"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            cv2.rectangle(vis, (x1, y1 - th - 10), (x1 + tw, y1), color, -1)
            cv2.putText(vis, txt, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), thickness)

        # 3. Esqueleto 
        if show_skel and result.spine_visualization is not None:
            skel_mask = result.spine_visualization

            if skel_mask.shape[:2] == (h, w):

                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                skel_dilated = cv2.dilate(skel_mask, kernel, iterations=1)
                vis[skel_dilated > 0] = (0, 0, 255) # Rojo

                if result.spine_length > 0:
                    info_txt = f"Skel: {int(result.spine_length)}px"
                    cv2.putText(vis, info_txt, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,255), thickness)

        return vis

    def _is_detector_ready(self) -> bool:
        """Verifica si el detector ha sido inyectado y está listo."""
        return self.detector is not None and getattr(self.detector, 'is_ready', False)

    def validate_scales(self, **scales):
        """Valida diccionario de escalas."""
        for name, value in scales.items():
            if value is None or value <= 0:
                return False, f"{name} inválida ({value})"
        return True, "OK"