"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Detector de Visión Avanzada (AdvancedDetector.py)
DESCRIPCIÓN: Actúa como orquestador central de las capacidades de Inteligencia Artificial.
             Integra modelos de lenguaje visual (VLM) para detección semántica y 
             modelos de segmentación (SAM) para la extracción precisa de siluetas.
"""

import cv2
import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from PIL import Image
import moondream as md_lib 

from Config.Config import Config
from .SpineMeasurer import SpineMeasurer
from .SegmentationRefiner import SegmentationRefiner

logger = logging.getLogger(__name__)

# ============================================================================
# GESTIÓN DE DEPENDENCIAS OPCIONALES (FALLBACKS)
# ============================================================================
try:
    MOONDREAM_API_AVAILABLE = True
except ImportError:
    MOONDREAM_API_AVAILABLE = False
    logger.warning("Libreria 'moondream' no instalada.")

try:
    REFINER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"SegmentationRefiner no disponible: {e}")
    REFINER_AVAILABLE = False

# ============================================================================
# ESTRUCTURAS DE DATOS
# ============================================================================
@dataclass
class BiometryResult:
    """
    Objeto de Transferencia de Datos (DTO) que encapsula el resultado completo 
    del análisis biométrico de un espécimen.
    """
    bbox: Tuple[int, int, int, int]  
    mask: Optional[np.ndarray] = None
    spine_length: float = 0.0
    spine_visualization: Optional[np.ndarray] = None
    contour: Optional[np.ndarray] = None
    confidence: float = 0.0
    source: str = "unknown"

    @property
    def is_valid(self) -> bool:
        """Valida si el resultado es útil para medición."""
        return self.spine_length > 0 and self.mask is not None


class AdvancedDetector:
    """
    Motor de Visión Artificial Híbrido.
    
    Implementa un patrón 'Chain of Responsibility' (Cadena de Responsabilidad) para 
    intentar diferentes estrategias de detección (Nube -> Local -> Clásico) hasta 
    obtener un resultado válido.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.is_ready = False
        self.detectors_chain: List[Dict[str, Any]] = []
        self.refiner: Optional[SegmentationRefiner] = None
        self.api_model = None

        self.api_key = api_key if api_key else getattr(Config, 'MOONDREAM_API_KEY', '')

        self._init_system()

    def _init_system(self) -> None: 
        logger.info("--- INICIALIZANDO DETECTOR AVANZADO ---")

        # 1. Inicializar API Moondream
        self.api_model = self._init_moondream_api()

        # 2. Inicializar Refinador (SAM)
        if REFINER_AVAILABLE:
            try:
                logger.info("Cargando modelo de segmentacion (MobileSAM)...")
                self.refiner = SegmentationRefiner()
                logger.info("Refinador de siluetas cargado.")
            except Exception as e:
                logger.error(f"Error critico cargando MobileSAM: {e}.")
                self.refiner = None
        else:
            logger.warning("SegmentationRefiner no esta disponible.")

        # 3. Construir cadena de responsabilidad
        self._create_detection_chain()

        if self.detectors_chain:
            self.is_ready = True
            logger.info("Detector Online listo.")
        else:
            logger.error("ERROR CRITICO: No hay detectores disponibles.")

    def _init_moondream_api(self) -> Any:
        if not MOONDREAM_API_AVAILABLE:
            return None
        
        if not self.api_key or len(self.api_key) < 10:
            logger.warning("API Key de Moondream invalida o no configurada.")
            return None
            
        try:
            return md_lib.vl(api_key=self.api_key)
        except Exception as e:
            logger.error(f"Excepcion al conectar con Moondream: {e}")
            return None
    def _prepare_image_for_moondream(self, image_bgr: np.ndarray) -> Image:
        """
        Filtro de Enfoque: Suaviza el fondo y oscurece sombras para que Moondream vea solo al pez.
        """
        # 1. Reducción de ruido bilateral (suaviza fondo sin borrar bordes del pez)
        smooth = cv2.bilateralFilter(image_bgr, 9, 75, 75)
        
        # 2. Ajuste de Gamma (oscurece el tanque para resaltar el brillo del pez)
        gamma = 0.8
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        focused_img = cv2.LUT(smooth, table)
        
        # Convertir a PIL para la API
        img_rgb = cv2.cvtColor(focused_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)
    
    def _create_detection_chain(self) -> None:
        """Registra los métodos de detección disponibles en orden de prioridad."""
        if self.api_model:
            self.detectors_chain.append({
                "name": "Moondream API",
                "method": self._detect_with_api,
                "type": "remote"
            })

    def detect_fish(self, image_bgr: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Ejecuta la cadena de detectores hasta encontrar un resultado válido.
        Retorna: (x1, y1, x2, y2) o None
        """
        if not self.is_ready:
            logger.error("Intento de deteccion sin sistema inicializado.")
            return None

        for detector in self.detectors_chain:
            try:
                box = detector["method"](image_bgr)
                if box:
                    return box
            except Exception as e:
                logger.error(f"Fallo en detector {detector['name']}: {e}")
                continue
        
        
        return None
    def _apply_clahe(self, image_bgr: np.ndarray) -> np.ndarray:
        """Mejora el contraste local (LAB space) para ver a través de agua turbia."""
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _refine_mask_with_grabcut(self, image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Ajusta los bordes de la máscara SAM exactamente a las escamas del pez."""
        if mask is None or np.sum(mask) == 0:
            return mask
        
        # Crear máscara de estados para GrabCut
        gc_mask = np.where(mask > 0, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype('uint8')
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        inner_core = cv2.erode(mask, kernel, iterations=2)
        gc_mask[inner_core > 0] = cv2.GC_FGD
        
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        
        try:
            cv2.grabCut(image_bgr, gc_mask, None, bgd_model, fgd_model, 2, cv2.GC_INIT_WITH_MASK)
            refined_mask = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype('uint8')
            return refined_mask
        except Exception as e:
            logger.debug(f"GrabCut falló, usando máscara original: {e}")
            return mask

    def analyze_frame(self, image_bgr: np.ndarray) -> Optional[BiometryResult]:
        """
        FLUJO DE PRECISIÓN TOTAL:
        1. Detección con Imagen Enfocada (Moondream).
        2. Segmentación con Imagen CLAHE (SAM).
        3. Refinamiento de Bordes (GrabCut).
        4. Suavizado Sub-píxel.
        5. Esqueleto Blindado.
        """
        # --- PASO 1: DETECCIÓN (USANDO EL FILTRO DE ENFOQUE) ---
        # No enviamos la imagen cruda, enviamos la imagen con Gamma corregido
        raw_box = self.detect_fish(image_bgr)
        
        if raw_box is None:
            return None

        # --- PASO 2: MEJORA DE IMAGEN PARA GEOMETRÍA ---
        processed_img = self._apply_clahe(image_bgr)
        result = BiometryResult(bbox=raw_box, source="hybrid_precision_v3")

        if not self.refiner:
            return result

        try:
            # 2. Segmentación (Refinamiento con SAM)
            mask = self.refiner.get_body_mask(image_bgr, list(raw_box))
            
            if mask is None or cv2.countNonZero(mask) == 0:
                return result

            # === NUEVO: BLOQUEO ESTRICTO DE CAJA ===
            # Creamos una jaula negra del tamaño de la imagen
            h_m, w_m = mask.shape[:2]
            strict_box_mask = np.zeros((h_m, w_m), dtype=np.uint8)
            x1, y1, x2, y2 = raw_box
            # Solo permitimos blanco DENTRO de la caja de Moondream
            strict_box_mask[y1:y2, x1:x2] = 255
            mask = cv2.bitwise_and(mask, strict_box_mask)
            # =======================================

            result.mask = mask

            # --- PASO 6: EXTRACCIÓN DE CONTORNOS ---
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return result
            
            largest_contour = max(contours, key=cv2.contourArea)
            result.contour = largest_contour
            
            # Recalcular caja final sobre la máscara perfecta
            x, y, w, h = cv2.boundingRect(largest_contour)
            result.bbox = (x, y, x + w, y + h)

            # --- PASO 7: COLUMNA (SPINE) ---
            # Aquí es donde SpineMeasurer aplica el bitwise_and con la máscara anterior
            if w > Config.MIN_BOX_SIZE_PX and h > Config.MIN_BOX_SIZE_PX:
                spine_len, skeleton_img = SpineMeasurer.get_spine_info(mask)
                result.spine_length = spine_len
                result.spine_visualization = skeleton_img
                
                logger.info(f"Pipeline de precisión final completado: {spine_len:.2f}px")

            return result

        except Exception as e:
            logger.error(f"Error en pipeline de alta precisión: {e}")
            return result

    def _detect_with_api(self, image_bgr: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Wrapper para la API de Moondream."""
        if not self.api_model:
            return None

        try:
            h_img, w_img = image_bgr.shape[:2]
            
            # LLAMADA AL FILTRO DE ENFOQUE ANTES DE ENVIAR A MOONDREAM
            pil_image = self._prepare_image_for_moondream(image_bgr)
            
            prompt = "detect a fish body side view suitable for measurement"
            result = self.api_model.detect(pil_image, prompt)
            
            if result and result.get("objects"):
                obj = result["objects"][0]
                
                # Conversión de coordenadas normalizadas a píxeles absolutos
                x_min, y_min = obj['x_min'], obj['y_min']
                x_max, y_max = obj['x_max'], obj['y_max']

                real_x1 = max(0, int(x_min * w_img))
                real_y1 = max(0, int(y_min * h_img))
                real_x2 = min(w_img, int(x_max * w_img))
                real_y2 = min(h_img, int(y_max * h_img))

                # Validación de dimensiones mínimas
                w_box = real_x2 - real_x1
                h_box = real_y2 - real_y1

                if w_box < Config.MIN_BOX_SIZE_PX or h_box < Config.MIN_BOX_SIZE_PX:
                    logger.debug(f"Deteccion ignorada por tamano pequeno: {w_box}x{h_box}.")
                    return None

                return (real_x1, real_y1, real_x2, real_y2)

        except Exception as e:
            logger.error(f"Error API Moondream: {e}.")
            return None