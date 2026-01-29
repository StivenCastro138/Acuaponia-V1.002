"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Servicio de Sensores IoT (SensorService.py)
DESCRIPCIÓN: Cliente HTTP encargado de la adquisición de telemetría ambiental.
             Actúa como un puente entre la API de calidad del agua (WOC) y el 
             sistema local, normalizando los datos para su persistencia.
"""

import requests
import logging

logger = logging.getLogger(__name__)

class SensorService:
    """
    Fachada para la integración con dispositivos de monitoreo remoto.
    """
    
    API_URL = "https://nuevanaturalezaapi-net.fly.dev/api/Dispositivoes/WOC"
    
    FIELD_MAPPING = {
        "Turbidez": "api_turbidity_ntu",
        "Temperatura del ambiente": "api_air_temp_c",
        "Conductividad": "api_cond_us_cm",
        "Humedad del ambiente": "api_rel_humidity",
        "PH": "api_ph",
        "Temperatura del agua": "api_water_temp_c",
        "Oxigeno Disuelto": "api_do_mg_l"
    }

    @staticmethod
    def get_water_quality_data():
        """
        Consulta la API, procesa la lista de diccionarios y retorna
        un diccionario plano listo para DatabaseManager.
        """
        try:
            # 1. Adquisición de Datos
            response = requests.get(SensorService.API_URL, timeout=5)
            
            if response.status_code != 200:
                logger.error(f"Fallo en API IoT: HTTP {response.status_code}.")
                return {}

            raw_data = response.json() 

            # 2. Normalización de Estructura 
            flat_data = {}
            if isinstance(raw_data, list):
                for item in raw_data:
                    flat_data.update(item)
            elif isinstance(raw_data, dict):
                flat_data = raw_data

            # 3. Transformación y Mapeo 
            db_data = {}
            for api_key, db_column in SensorService.FIELD_MAPPING.items():
                value = flat_data.get(api_key, 0.0)
                
                try:
                    db_data[db_column] = float(value)
                except (ValueError, TypeError):
                    db_data[db_column] = 0.0
                    logger.warning(f"Dato no numerico recibido para {api_key}: {value}.")

            logger.info("Telemetria ambiental sincronizada correctamente.")
            return db_data

        except requests.exceptions.Timeout:
            logger.warning("Timeout: La API de sensores tardó demasiado en responder.")
            return {}
        except requests.exceptions.ConnectionError:
            logger.warning("Sin conexion: No se pudo contactar al servidor de sensores.")
            return {}
        except Exception as e:
            logger.error(f"Error critico en servicio de sensores: {e}.")
            return {}