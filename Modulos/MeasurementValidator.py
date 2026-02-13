"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Validador de Integridad de Mediciones (MeasurementValidator.py)
DESCRIPCIÓN: Motor de reglas de negocio (Business Rules Engine) que audita los datos 
             biométricos antes de su persistencia. Aplica restricciones biológicas, 
             geométricas y estereoscópicas para filtrar falsos positivos.
"""

from typing import Dict, List

from Config.Config import Config

class MeasurementValidator:
    """
    Filtro de Sanidad de Datos.
    """

    @staticmethod
    def validate_measurement(metrics: Dict[str, float]) -> List[str]:
        """
        Analiza un set de métricas y devuelve una lista de advertencias.
        """
        errors = []
        
        length = metrics.get('length_cm', 0.0)
        weight = metrics.get('weight_g', 0.0)
        height = metrics.get('height_cm', 0.0)
        width = metrics.get('width_cm', 0.0)
        lat_area = float(metrics.get('lat_area_cm2', 0.0))
        top_area = float(metrics.get('top_area_cm2', 0.0))
        k_factor = metrics.get('condition_factor', 0.0)

        # 1. Validar Rangos Físicos 
        if not (Config.MIN_LENGTH_CM <= length <= Config.MAX_LENGTH_CM):
            errors.append(f"⚠️ Longitud inverosimil ({length:.2f} cm). Rango permitido: {Config.MIN_LENGTH_CM}-{Config.MAX_LENGTH_CM}cm")
            return errors
        
        # 2. Validar Factor de Condición 
        if k_factor > 0:
            if k_factor < Config.MIN_K_FACTOR:
                 errors.append(f"⚠️ Factor K muy bajo ({k_factor:.2f}). Posible pez extremadamente delgado o error de largo.")
            elif k_factor > Config.MAX_K_FACTOR:
                 errors.append(f"⚠️ Factor K excesivo ({k_factor:.2f}). Verifique si el largo se subestimo.")
        
        # 3. Validar Consistencia Peso vs Longitud 
        if length > 0 and weight > 0:
            
            expected_weight = Config.WEIGHT_K * (length ** Config.WEIGHT_EXP)
            
            if expected_weight > 0:
                diff_percent = abs(weight - expected_weight) / expected_weight
                
                if diff_percent > Config.MAX_WEIGHT_DEVIATION:
                    msg_type = "Excesivamente pesado" if weight > expected_weight else "Excesivamente liviano"
                    errors.append(f"⚠️ Peso sospechoso: {msg_type} para {length:.1f}cm (Desviacion {int(diff_percent*100)}%)")
        
        # 4. Validar Geometría (Morfología)
        if length > 0:
            # A. Relación de Aspecto 
            ratio_height = height / length
            
            if ratio_height > Config.MAX_HEIGHT_RATIO:
                errors.append(f"⚠️ Altura anormal ({ratio_height:.2f}x largo). Posible pez doblado o error de camara.")
            elif ratio_height < Config.MIN_HEIGHT_RATIO:
                errors.append(f"⚠️ Altura insuficiente ({ratio_height:.2f}x largo).")

            # B. Validación de Segmentación 
            if lat_area > 0 and height > 0:
                bbox_lat = length * height
                occ_lat = lat_area / bbox_lat
                if occ_lat > Config.MAX_OCCUPANCY_RATIO:
                    errors.append("⚠️ Lateral: Contorno muy rectangular (Fallo IA).")
                elif occ_lat < Config.MIN_OCCUPANCY_RATIO:
                     errors.append("⚠️ Lateral: Área muy pequeña (Ruido).")
                         
            if top_area > 0 and width > 0:
                bbox_top = length * width  
                if bbox_top > 0:
                    occ_top = top_area / bbox_top
                    if occ_top > Config.MAX_TOP_OCCUPANCY_RATIO: 
                        errors.append(f"⚠️ Cenital: Contorno rectangular ({occ_top:.2f}).")
                    elif occ_top < Config.MIN_TOP_OCCUPANCY_RATIO: 
                        errors.append(f"⚠️ Cenital: Objeto muy delgado ({occ_top:.2f}).")
        
        if lat_area > 0 and top_area > 0:
            if top_area > (lat_area * Config.MAX_AREA_INVERSION_TOLERANCE):
                errors.append(
                    f"⚠️ Incoherencia Espacial: Área Top ({top_area:.0f}) > Lateral ({lat_area:.0f}). "
                    "Posible pez nadando de lado o cámaras invertidas."
                )

        return errors