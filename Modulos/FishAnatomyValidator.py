"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Validador de Anatomía (FishAnatomyValidator.py)
DESCRIPCIÓN: Motor de reglas heurísticas basado en geometría computacional.
             Analiza la morfología de los contornos detectados para filtrar falsos positivos
             (ruido, burbujas, objetos extraños) y asegurar que solo se midan peces reales.
"""

import cv2
import numpy as np
import logging

from Config.Config import Config

logger = logging.getLogger(__name__)

class FishAnatomyValidator:
    """
    Valida que el objeto detectado sea realmente un pez mediante análisis anatómico.
    """

    def __init__(self):
        self.last_errors = []
        self.last_confidence = 0.0
        self.validated = False

    # ----------------------------------------------------------------------
    # VALIDACIÓN PRINCIPAL
    # ----------------------------------------------------------------------
    def validate_anatomy(self, contour, mask=None):
        if contour is None or len(contour) < 10:
            return False, 0.0

        if mask is None:
            x, y, w, h = cv2.boundingRect(contour)
            temp_mask = np.zeros((h + 10, w + 10), dtype=np.uint8)
            cv2.drawContours(temp_mask, [contour - [x - 5, y - 5]], -1, 255, -1)
            mask_to_use = temp_mask
        else:
            x, y, w, h = cv2.boundingRect(contour)
            mask_to_use = mask[y:y + h, x:x + w]

        return self.validate_is_fish(contour, mask_to_use)[:2]

    # ----------------------------------------------------------------------
    # TESTS ANATÓMICOS
    # ----------------------------------------------------------------------
    def validate_is_fish(self, contour, mask, frame=None):
        if contour is None:
            return False, 0.0, {"error": "Sin contorno"}

        details = {}
        scores = []

        try:
            # 1. Aspect Ratio
            rect = cv2.minAreaRect(contour)
            L = max(rect[1])
            H = min(rect[1])
            aspect = L / max(H, 0.1)

            aspect_valid = Config.MIN_ASPECT_RATIO <= aspect <= Config.MAX_ASPECT_RATIO
            scores.append((1.0 if aspect_valid else 0.4) * 0.40)
            details["aspect_ratio"] = {"value": aspect, "valid": aspect_valid}

            # 2. Solidez
            area = cv2.contourArea(contour)
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0

            solidity_valid = Config.MIN_SOLIDITY <= solidity <= Config.MAX_SOLIDITY
            scores.append((1.0 if solidity_valid else 0.3) * 0.25)
            details["solidity"] = {"value": solidity, "valid": solidity_valid}

            # 3. Simetría
            h_m = mask.shape[0]
            if h_m > 5:
                mid = h_m // 2
                top = mask[:mid, :]
                bottom = cv2.flip(mask[h_m - mid:h_m, :], 0)

                union = cv2.bitwise_or(top, bottom)
                inter = cv2.bitwise_and(top, bottom)
                symmetry = np.sum(inter) / np.sum(union) if np.sum(union) > 0 else 0
            else:
                symmetry = 0

            sym_valid = symmetry >= Config.MIN_SYMMETRY
            scores.append((1.0 if sym_valid else 0.5) * 0.25)
            details["symmetry"] = {"value": symmetry, "valid": sym_valid}

            # 4. Rectitud
            rectitud = (2 * L + 2 * H) / (cv2.arcLength(contour, True) / 1.5)
            rectitud_valid = rectitud > 0.8
            scores.append((1.0 if rectitud_valid else 0.6) * 0.10)

            final_confidence = sum(scores)
            is_valid = aspect_valid and solidity_valid and final_confidence >= 0.70

            details["final_confidence"] = final_confidence
            details["verdict"] = "FISH ✓" if is_valid else "NOT FISH ✗"

            self.last_confidence = final_confidence
            self.validated = is_valid

            return is_valid, final_confidence, details

        except Exception as e:
            logger.error(f"Error en validacion anatomica: {e}.")
            return False, 0.0, {"error": str(e)}

    def draw_validation_overlay(self, frame, contour, details):
        """
        Dibuja los resultados de la validación anatómica sobre el frame.
        """
        if frame is None or contour is None or not details:
            return frame

        res_frame = frame.copy()

        is_fish = details.get("verdict") == "FISH ✓"
        color = (0, 255, 0) if is_fish else (0, 0, 255)

        # Contorno
        cv2.drawContours(res_frame, [contour], -1, color, 2)

        # Bounding box
        x, y, w, h = cv2.boundingRect(contour)
        cv2.rectangle(res_frame, (x, y), (x + w, y + h), color, 1)

        # Texto principal
        conf = details.get("final_confidence", 0.0)
        label = f"{details.get('verdict', 'UNKNOWN')} ({conf:.1%})"

        cv2.putText(
            res_frame,
            label,
            (x, max(15, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA
        )

        return res_frame