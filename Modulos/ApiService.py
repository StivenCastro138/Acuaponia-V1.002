"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces (LESTOMA-UDEC)
MÓDULO: Servicio de Interconectividad API (ApiService.py)
DESCRIPCIÓN: Servidor web ligero basado en Flask y Ngrok que expone los datos de 
             trazabilidad a internet. Provee un punto de acceso (endpoint) 
             consolidado que combina el último cierre biométrico (promedios históricos) 
             con las variables ambientales detectadas en tiempo real por los sensores.
"""

import threading
import sqlite3
import logging
import time
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request
from flask_cors import CORS  
from pyngrok import ngrok

from Config.Config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

class ApiService:
    def __init__(self, port=5000):
        self.ngrok_token = Config.NGROK_AUTHTOKEN.strip() if Config.NGROK_AUTHTOKEN else None
        self.port = port
        self.app = Flask(__name__)
        self.server_thread = None
        self.public_url = None
        self.running = False
        self._cache = {}
        self._cache_timeout = 60  

        # Configuración CORS
        CORS(self.app, resources={r"/api/*": {"origins": "*"}})
        self.app.config['JSON_SORT_KEYS'] = False

        # Configurar token de ngrok correctamente
        if self.ngrok_token:
            try:
                ngrok.set_auth_token(self.ngrok_token)
                logger.info("Ngrok authtoken configurado")
            except Exception as e:
                logger.error(f"Error configurando authtoken de ngrok: {e}")
        else:
            logger.warning("NGROK_AUTHTOKEN no definido en Config")

        self._setup_routes()


    def _setup_routes(self):
        """Configura todos los endpoints de la API."""
        
        # Decorador para caché simple
        def cached(timeout=60):
            def decorator(f):
                @wraps(f)
                def wrapper(*args, **kwargs):
                    cache_key = f.__name__
                    now = time.time()
                    
                    if cache_key in self._cache:
                        data, timestamp = self._cache[cache_key]
                        if now - timestamp < timeout:
                            logger.debug(f"Cache hit: {cache_key}")
                            return data
                    
                    result = f(*args, **kwargs)
                    self._cache[cache_key] = (result, now)
                    return result
                return wrapper
            return decorator

        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Endpoint de salud del servicio."""
            try:
                with sqlite3.connect(Config.DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM measurements")
                    count = cursor.fetchone()[0]
                
                return jsonify({
                    "status": "healthy",
                    "service": "FishTrace API",
                    "version": "2.0",
                    "database": "connected",
                    "total_measurements": count,
                    "timestamp": datetime.now().isoformat()
                }), 200
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({
                    "status": "unhealthy",
                    "error": str(e)
                }), 500

        @self.app.route('/api/last_report', methods=['GET'])
        @cached(timeout=60)
        def get_last_report():
            """
            Obtiene el último reporte consolidado de mediciones.
            Incluye datos biométricos, áreas, volumen y sensores ambientales.
            """
            try:
                with sqlite3.connect(Config.DB_NAME) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # 1. Encontrar la última fecha con mediciones válidas
                    cursor.execute("""
                        SELECT substr(timestamp, 1, 10) as f 
                        FROM measurements 
                        WHERE length_cm > 0 OR manual_length_cm > 0
                        ORDER BY timestamp DESC LIMIT 1
                    """)
                    res = cursor.fetchone()
                    
                    if not res:
                        return jsonify({
                            "success": False,
                            "error": "No hay mediciones registradas",
                            "data": None
                        }), 404
                    
                    ultima_fecha = res['f']

                    # 2. Consulta consolidada con manejo de NULL
                    query = """
                    SELECT 
                        substr(timestamp, 1, 10) as fecha,
                        COUNT(*) as total_muestras,
                        
                        -- Biometría (Prefiere manual si existe)
                        ROUND(AVG(CASE WHEN manual_length_cm > 0 THEN manual_length_cm ELSE length_cm END), 2) as longitud_cm,
                        ROUND(AVG(CASE WHEN manual_weight_g > 0 THEN manual_weight_g ELSE weight_g END), 2) as peso_g,
                        ROUND(AVG(CASE WHEN manual_height_cm > 0 THEN manual_height_cm ELSE height_cm END), 2) as alto_cm,
                        ROUND(AVG(CASE WHEN manual_width_cm > 0 THEN manual_width_cm ELSE width_cm END), 2) as ancho_cm,
                        
                        -- Áreas y Volumen
                        ROUND(AVG(lat_area_cm2), 2) as area_lateral_cm2,
                        ROUND(AVG(top_area_cm2), 2) as area_cenital_cm2,
                        ROUND(AVG(volume_cm3), 2) as volumen_cm3,
                        
                        -- Sensores (con filtro de valores válidos > 0)
                        ROUND(AVG(CASE WHEN api_air_temp_c > 0 THEN api_air_temp_c ELSE NULL END), 1) as temp_aire_c,
                        ROUND(AVG(CASE WHEN api_water_temp_c > 0 THEN api_water_temp_c ELSE NULL END), 1) as temp_agua_c,
                        ROUND(AVG(CASE WHEN api_ph > 0 THEN api_ph ELSE NULL END), 1) as ph,
                        ROUND(AVG(CASE WHEN api_do_mg_l > 0 THEN api_do_mg_l ELSE NULL END), 1) as oxigeno_mg_l,
                        ROUND(AVG(CASE WHEN api_rel_humidity > 0 THEN api_rel_humidity ELSE NULL END), 1) as humedad_rel,
                        ROUND(AVG(CASE WHEN api_turbidity_ntu > 0 THEN api_turbidity_ntu ELSE NULL END), 1) as turbidez_ntu,
                        ROUND(AVG(CASE WHEN api_cond_us_cm > 0 THEN api_cond_us_cm ELSE NULL END), 1) as conductividad_us
                        
                    FROM measurements 
                    WHERE substr(timestamp, 1, 10) = ?
                    """
                    cursor.execute(query, (ultima_fecha,))
                    reporte = cursor.fetchone()

                    # Construir respuesta estructurada
                    data = {
                        "fecha": reporte["fecha"],
                        "total_muestras": reporte["total_muestras"],
                        
                        "biometria": {
                            "longitud_cm": reporte["longitud_cm"],
                            "peso_g": reporte["peso_g"],
                            "alto_cm": reporte["alto_cm"],
                            "ancho_cm": reporte["ancho_cm"]
                        },
                        
                        "geometria": {
                            "area_lateral_cm2": reporte["area_lateral_cm2"],
                            "area_cenital_cm2": reporte["area_cenital_cm2"],
                            "volumen_cm3": reporte["volumen_cm3"]
                        },
                        
                        "sensores": {
                            "temperatura": {
                                "aire_c": reporte["temp_aire_c"],
                                "agua_c": reporte["temp_agua_c"]
                            },
                            "calidad_agua": {
                                "ph": reporte["ph"],
                                "oxigeno_mg_l": reporte["oxigeno_mg_l"],
                                "turbidez_ntu": reporte["turbidez_ntu"],
                                "conductividad_us": reporte["conductividad_us"]
                            },
                            "ambiente": {
                                "humedad_rel": reporte["humedad_rel"]
                            }
                        }
                    }

                    # Validar integridad de datos
                    warnings = []
                    if all(v is None or v == 0 for v in data["sensores"]["temperatura"].values()):
                        warnings.append("Sin datos de temperatura")
                    if all(v is None or v == 0 for v in data["sensores"]["calidad_agua"].values()):
                        warnings.append("Sin datos de calidad de agua")

                    response = {
                        "success": True,
                        "timestamp": datetime.now().isoformat(),
                        "data": data
                    }
                    
                    if warnings:
                        response["warnings"] = warnings

                    return jsonify(response), 200

            except sqlite3.Error as e:
                logger.error(f"Database error: {e}")
                return jsonify({
                    "success": False,
                    "error": "Error de base de datos",
                    "details": str(e)
                }), 500
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return jsonify({
                    "success": False,
                    "error": "Error interno del servidor",
                    "details": str(e)
                }), 500

        @self.app.route('/api/stats', methods=['GET'])
        def get_statistics():
            """Estadísticas generales del sistema."""
            try:
                with sqlite3.connect(Config.DB_NAME) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    # Estadísticas globales
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total_mediciones,
                            COUNT(DISTINCT substr(timestamp, 1, 10)) as dias_activos,
                            MIN(substr(timestamp, 1, 10)) as primera_medicion,
                            MAX(substr(timestamp, 1, 10)) as ultima_medicion,
                            ROUND(AVG(CASE WHEN manual_length_cm > 0 THEN manual_length_cm ELSE length_cm END), 2) as longitud_promedio,
                            ROUND(AVG(CASE WHEN manual_weight_g > 0 THEN manual_weight_g ELSE weight_g END), 2) as peso_promedio
                        FROM measurements
                        WHERE length_cm > 0 OR manual_length_cm > 0
                    """)
                    stats = cursor.fetchone()
                    
                    return jsonify({
                        "success": True,
                        "data": {
                            "total_mediciones": stats["total_mediciones"],
                            "dias_activos": stats["dias_activos"],
                            "primera_medicion": stats["primera_medicion"],
                            "ultima_medicion": stats["ultima_medicion"],
                            "promedios_historicos": {
                                "longitud_cm": stats["longitud_promedio"],
                                "peso_g": stats["peso_promedio"]
                            }
                        }
                    }), 200
                    
            except Exception as e:
                logger.error(f"Stats error: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500

        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({
                "success": False,
                "error": "Endpoint no encontrado",
                "available_endpoints": [
                    "/api/health",
                    "/api/last_report",
                    "/api/stats"
                ]
            }), 404

        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({
                "success": False,
                "error": "Error interno del servidor"
            }), 500

    def start(self):
        """Inicia el servidor Flask y abre el túnel público Ngrok."""
        if self.running:
            logger.warning("El servicio ya está en ejecución")
            return

        self.running = True

        # Iniciar Flask en thread separado
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="FlaskThread"
        )
        self.server_thread.start()

        # Esperar a que Flask inicie
        time.sleep(2)

        # Configurar túnel Ngrok
        try:
            # Cerrar túneles previos
            ngrok.kill()

            # Configurar token correctamente
            if self.ngrok_token:
                ngrok.set_auth_token(self.ngrok_token)
                logger.info("Authtoken de ngrok configurado correctamente")
            else:
                logger.warning("NGROK_AUTHTOKEN no definido en Config")
                raise ValueError("Token de ngrok no configurado")

            # Crear túnel HTTP
            tunnel = ngrok.connect(
                addr=self.port,
                proto="http"
            )

            self.public_url = tunnel.public_url
            logger.info(f"API pública disponible en: {self.public_url}")

        except Exception as e:
            logger.error(f"Error al configurar Ngrok: {e}")
            self.public_url = None

    def _run_server(self):
        """Ejecuta el servidor Flask."""
        try:
            logger.info(f"Iniciando servidor Flask en puerto {self.port}")
            self.app.run(
                host='0.0.0.0', 
                port=self.port, 
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            logger.error(f"Error en servidor Flask: {e}")
            self.running = False
            
    def get_status_info(self):
        # Prioridad absoluta a la URL pública de Ngrok
        if self.running and self.public_url:
            return "Online", "success", self.public_url
        
        # Si el servidor Flask corre pero Ngrok falló o está cargando
        elif self.running:
            return "Local", "warning", f"http://localhost:{self.port}"
        
        # Si nada está encendido
        return "Offline", "error", None
    
    def stop(self):
        """Detiene el servicio de forma ordenada."""
        if self.running:
            logger.info("Deteniendo servicio API...")
            try:
                ngrok.disconnect(self.public_url)
                ngrok.kill()
            except:
                pass
            self.running = False
            logger.info("Servicio API detenido")

    def get_public_url(self):
        """Retorna la URL pública del servicio."""
        return self.public_url if self.running else None