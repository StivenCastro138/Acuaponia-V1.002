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
                escala_fondo=scale_lat_back,
                es_cenital=False
            )

            px_to_cm_top = 0.0
            if has_top:
                y_center_top = (res_top.bbox[1] + res_top.bbox[3]) / 2
                px_to_cm_top = Config.calcular_escala_proporcional(
                    valor_y=y_center_top,
                    max_y=img_top.shape[0],
                    escala_frente=scale_top_front,
                    escala_fondo=scale_top_back,
                    es_cenital=True
                )

            if px_to_cm_lat <= 0:
                logger.error(f"Escala lateral invalida: {px_to_cm_lat}. Abortando medicion.")
                return None, img_lat, img_top

            lat_box_len_px = max(
                abs(res_lat.bbox[2] - res_lat.bbox[0]),
                abs(res_lat.bbox[3] - res_lat.bbox[1])
            )
            length_lat_cm_raw = lat_box_len_px * px_to_cm_lat

            length_top_cm_raw = 0.0
            if has_top:
                top_box_len_px = max(
                    abs(res_top.bbox[2] - res_top.bbox[0]),
                    abs(res_top.bbox[3] - res_top.bbox[1])
                )
                length_top_cm_raw = top_box_len_px * px_to_cm_top

            # ============================================================
            # 3. ESTIMACIÓN BIOMÉTRICA (cm)
            # Prioridad: contornos refinados por SAM -> fallback por cajas
            # ============================================================
            has_lat_contour = res_lat.contour is not None and len(res_lat.contour) >= 5
            has_top_contour = has_top and res_top.contour is not None and len(res_top.contour) >= 5

            if has_lat_contour:
                metrics = MorphometricAnalyzer.compute_advanced_metrics(
                    contour_lat=res_lat.contour,
                    contour_top=res_top.contour if has_top_contour else None,
                    scale_lat=px_to_cm_lat,
                    scale_top=px_to_cm_top if has_top else 0.0,
                    spine_length_px=res_lat.spine_length if res_lat.spine_length > 0 else None
                )
                metrics['measurement_mode'] = 'advanced_contour'
                if has_top and not has_top_contour:
                    metrics.setdefault('_warnings', []).append(
                        "Vista cenital sin contorno confiable: ancho estimado con fallback anatómico."
                    )
            else:
                metrics = MorphometricAnalyzer.estimate_from_dual_boxes(
                    box_lat=res_lat.bbox,
                    box_top=res_top.bbox if has_top else None,
                    scale_lat=px_to_cm_lat,
                    scale_top=px_to_cm_top
                )
                metrics['measurement_mode'] = 'fallback_box'

            # ============================================================
            # 4. REFINAMIENTO CON ESQUELETO 
            # ============================================================
            spine_cm_lat = res_lat.spine_length * px_to_cm_lat
            spine_cm_top = (res_top.spine_length * px_to_cm_top) if has_top else 0.0

            metrics['has_top_view'] = bool(has_top)
            metrics['length_lat_cm_raw'] = round(length_lat_cm_raw, 2)
            metrics['length_top_cm_raw'] = round(length_top_cm_raw, 2)
            metrics['spine_lat_cm'] = round(spine_cm_lat, 2)
            metrics['spine_top_cm'] = round(spine_cm_top, 2)
            metrics['box_lat'] = tuple(map(int, res_lat.bbox)) if res_lat and res_lat.bbox else None
            metrics['box_top'] = tuple(map(int, res_top.bbox)) if has_top and res_top and res_top.bbox else None

            current_len = float(metrics.get('length_cm', 0) or 0)
            best_length = current_len

            if current_len > 0:
                tol = max(0.01, float(Config.LENGTH_FUSION_TOLERANCE_RATIO))
                w_spine = min(0.95, max(0.0, float(Config.LENGTH_FUSION_SPINE_WEIGHT)))
                w_top = min(0.95, max(0.0, float(Config.LENGTH_FUSION_TOP_WEIGHT)))

                num = current_len
                den = 1.0

                if spine_cm_lat > 0:
                    diff_lat = abs(spine_cm_lat - current_len) / current_len
                    if diff_lat <= tol:
                        num += spine_cm_lat * w_spine
                        den += w_spine

                if spine_cm_top > 0:
                    diff_top = abs(spine_cm_top - current_len) / current_len
                    if diff_top <= tol:
                        num += spine_cm_top * w_top
                        den += w_top

                best_length = num / den if den > 0 else current_len
            else:
                candidates = [value for value in (spine_cm_lat, spine_cm_top) if value > 0]
                best_length = sum(candidates) / len(candidates) if candidates else 0
            
            if best_length > 0:
                metrics['length_cm'] = round(best_length, 2)
                
                derived = MorphometricAnalyzer._calculate_derived_metrics(
                    length=metrics['length_cm'],
                    height=metrics.get('height_cm', 0),
                    width=metrics.get('width_cm', 0),
                    lat_area=metrics.get('lat_area_cm2'),
                    top_area=metrics.get('top_area_cm2'),
                    is_bent=bool(metrics.get('is_bent', False))
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
            img_lat_ann = self._draw_result(img_lat, res_lat, (0, 0, 255), "LAT", draw_box, draw_skeleton)
            
            img_top_ann = img_top.copy()
            if has_top:
                img_top_ann = self._draw_result(img_top, res_top, (0, 0, 255), "TOP", draw_box, draw_skeleton)
            
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
            cv2.drawContours(vis, [result.contour], -1, color, 2)

        # 2. Caja 
        if show_box and result.bbox:
            x1, y1, x2, y2 = result.bbox
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)
            
            # Etiqueta
            txt = f"{label}"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            cv2.rectangle(vis, (x1, y1 - th - 10), (x1 + tw, y1), color, -1)
            cv2.putText(vis, txt, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255,255,255), thickness)

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