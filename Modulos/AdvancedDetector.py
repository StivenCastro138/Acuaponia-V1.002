import cv2
import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from PIL import Image

from Config.Config import Config
from .SpineMeasurer import SpineMeasurer

logger = logging.getLogger(__name__)

try:
    import moondream as md_lib  # type: ignore
    MOONDREAM_API_AVAILABLE = True
except ImportError:
    MOONDREAM_API_AVAILABLE = False
    logger.warning("Libreria 'moondream' no instalada.")

try:
    from .SegmentationRefiner import SegmentationRefiner
    REFINER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"SegmentationRefiner no disponible: {e}")
    REFINER_AVAILABLE = False

@dataclass
class BiometryResult:
    """Estructura de datos para encapsular el resultado del análisis."""
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
    Orquestador de Visión Artificial Avanzada para detección y medición de peces.
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
                logger.error(f"Error critico cargando MobileSAM: {e}")
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

    def analyze_frame(self, image_bgr: np.ndarray) -> Optional[BiometryResult]:
        """
        Pipeline completo: Detección -> Segmentación -> Esqueletización.
        Retorna un objeto BiometryResult estructurado.
        """
        # 1. Detección (Bounding Box)
        raw_box = self.detect_fish(image_bgr)
        
        if raw_box is None:
            return None

        # Resultado base si falla la segmentación
        result = BiometryResult(bbox=raw_box, source="detector_raw")

        if not self.refiner:
            return result

        try:
            # 2. Segmentación (Refinamiento con SAM)
            mask = self.refiner.get_body_mask(image_bgr, list(raw_box))
            
            if mask is None or cv2.countNonZero(mask) == 0:
                logger.warning("Segmentacion fallida (mascara vacia), retornando caja cruda.")
                return result

            result.mask = mask

            # 3. Derivar geometría refinada desde la máscara
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return result
            
            largest_contour = max(contours, key=cv2.contourArea)
            result.contour = largest_contour
            
            # Recalcular Bounding Box ajustado a la máscara
            x, y, w, h = cv2.boundingRect(largest_contour)
            result.bbox = (x, y, x + w, y + h)
            result.source = "segmentation_refined"

            # 4. Esqueletización (Biometría)
            if w > Config.MIN_BOX_SIZE_PX and h > Config.MIN_BOX_SIZE_PX:
                spine_len, skeleton_img = SpineMeasurer.get_spine_info(mask)
                result.spine_length = spine_len
                result.spine_visualization = skeleton_img
                
                logger.info(f"Biometria exitosa: Longitud={spine_len:.1f}px, Box={result.bbox}")
            else:
                logger.warning(f"Objeto muy pequeno para medir: {w}x{h}")

            return result

        except Exception as e:
            logger.error(f"Error en pipeline de analisis avanzado: {e}", exc_info=True)
            return result 

    def _detect_with_api(self, image_bgr: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Wrapper para la API de Moondream."""
        if not self.api_model:
            return None

        try:
            h_img, w_img = image_bgr.shape[:2]
            # Conversión eficiente BGR -> RGB
            img_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(img_rgb)
            
            # Prompt específico para biometría lateral
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
                    logger.debug(f"Deteccion ignorada por tamano pequeno: {w_box}x{h_box}")
                    return None

                return (real_x1, real_y1, real_x2, real_y2)

        except Exception as e:
            logger.error(f"Error API Moondream: {e}")
            return None