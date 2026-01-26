import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FishAnatomyValidator:
    """
    Valida que el objeto detectado sea realmente un pez mediante análisis anatómico avanzado.
    Optimizado para trabajar con máscaras de IA y detectar peces en posición de medición.
    """
    
    def __init__(self):
        # Rangos válidos optimizados para truchas y peces alargados
        self.MIN_ASPECT_RATIO = 2.5   # Un pez debe ser al menos 2.5 veces más largo que alto
        self.MAX_ASPECT_RATIO = 7.0   
        self.MIN_SOLIDITY = 0.75     # Evita formas "huecas" o muy irregulares
        self.MAX_SOLIDITY = 0.97     
        self.MIN_SYMMETRY = 0.70      # Simetría entre mitad superior e inferior
        self.MIN_TAPER_RATIO = 1.05  # La cabeza debe ser ligeramente más ancha que la cola
        self.MIN_LENGTH = 5.0  # Valor por defecto
        self.MAX_LENGTH = 50.0 # Valor por defecto
        
        logger.info("FishAnatomyValidator v2 (optimizado por Ia) inicializado")
        
    def set_bounds(self, min_len, max_len):
        """
        Actualiza los límites de longitud permitidos para la validación.
        """
        self.MIN_LENGTH = min_len
        self.MAX_LENGTH = max_len
        logger.info(f"FishAnatomyValidator: Limites actualizados a {min_len}cm - {max_len}cm")

    def validate_anatomy(self, contour, mask=None):
        """
        Método de entrada principal para el FishDetector.
        Retorna (es_pez: bool, confianza: float)
        """
        if contour is None or len(contour) < 10:
            return False, 0.0

        # Si no hay máscara, creamos una local rápida basada en el contorno
        if mask is None:
            x, y, w, h = cv2.boundingRect(contour)
            temp_mask = np.zeros((h + 10, w + 10), dtype=np.uint8)
            cv2.drawContours(temp_mask, [contour - [x-5, y-5]], -1, 255, -1)
            mask_to_use = temp_mask
        else:
            # Si hay máscara, recortamos al área del pez para procesar rápido
            x, y, w, h = cv2.boundingRect(contour)
            mask_to_use = mask[y:y+h, x:x+w]

        is_valid, confidence, _ = self.validate_is_fish(contour, mask_to_use, None)
        return is_valid, confidence

    def validate_is_fish(self, contour, mask, frame=None):
        """
        Ejecuta la batería completa de tests anatómicos.
        """
        if contour is None:
            return False, 0.0, {"error": "Sin contorno"}
        
        details = {}
        scores = []
        
        try:
            # 1. Aspect Ratio Real (Usando Bounding Box orientado)
            rect = cv2.minAreaRect(contour)
            L = max(rect[1])
            H = min(rect[1])
            aspect = L / max(H, 0.1)
            
            aspect_valid = self.MIN_ASPECT_RATIO <= aspect <= self.MAX_ASPECT_RATIO
            aspect_score = 1.0 if aspect_valid else 0.4
            scores.append(aspect_score * 0.40) # 40% del peso total
            details['aspect_ratio'] = {"value": aspect, "valid": aspect_valid}

            # 2. Solidez (Evita detectar "manchas" o suciedad)
            area = cv2.contourArea(contour)
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            
            solidity_valid = self.MIN_SOLIDITY <= solidity <= self.MAX_SOLIDITY
            solidity_score = 1.0 if solidity_valid else 0.3
            scores.append(solidity_score * 0.25) # 25% del peso total
            details['solidity'] = {"value": solidity, "valid": solidity_valid}

            # 3. Simetría Bilateral (Espejo)
            # Volteamos la máscara y comparamos coincidencia
            h_m, w_m = mask.shape[:2]
            if h_m > 5:
                # Dividir máscara en mitad superior e inferior
                mid = h_m // 2
                top_half = mask[0:mid, :]
                bottom_half = mask[h_m-mid:h_m, :] # Asegurar mismo tamaño
                bottom_flipped = cv2.flip(bottom_half, 0)
                
                # Calcular intersección sobre unión (IoU) de las mitades
                intersection = cv2.bitwise_and(top_half, bottom_flipped)
                union = cv2.bitwise_or(top_half, bottom_flipped)
                
                sum_union = np.sum(union)
                symmetry = np.sum(intersection) / sum_union if sum_union > 0 else 0
            else:
                symmetry = 0

            sym_valid = symmetry >= self.MIN_SYMMETRY
            sym_score = 1.0 if sym_valid else 0.5
            scores.append(sym_score * 0.25) # 25% del peso total
            details['symmetry'] = {"value": symmetry, "valid": sym_valid}

            # 4. Test de Rectitud (Evita medir peces doblados)
            # La longitud del arco del contorno vs el perímetro del convex hull
            rectitud = (2 * L + 2 * H) / (cv2.arcLength(contour, True) / 1.5)
            rectitud_valid = rectitud > 0.8
            scores.append((1.0 if rectitud_valid else 0.6) * 0.10) # 10% del peso total

            # Veredicto Final
            final_confidence = sum(scores)
            # Un pez es válido si pasa el aspecto y la solidez, y tiene > 70% total
            is_valid = aspect_valid and solidity_valid and final_confidence >= 0.70
            
            details['final_confidence'] = final_confidence
            details['verdict'] = "FISH ✓" if is_valid else "NOT FISH ✗"
            
            return is_valid, final_confidence, details
            
        except Exception as e:
            logger.error(f"Error en validacion anatomica: {str(e)}")
            return False, 0.0, {"error": str(e)}

    def draw_validation_overlay(self, frame, contour, details):
        """
        Dibuja los resultados de la validación sobre la imagen para monitoreo.
        """
        if frame is None or contour is None or details is None:
            return frame
        
        res_frame = frame.copy()
        is_fish = details.get('verdict') == "FISH ✓"
        color = (0, 255, 0) if is_fish else (0, 0, 255)
        
        # Bounding Box y Contorno
        x, y, w, h = cv2.boundingRect(contour)
        cv2.drawContours(res_frame, [contour], -1, color, 2)
        cv2.rectangle(res_frame, (x, y), (x+w, y+h), color, 1)
        
        # Textos
        conf = details.get('final_confidence', 0)
        cv2.putText(res_frame, f"{details.get('verdict')} ({conf:.1%})", 
                    (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return res_frame