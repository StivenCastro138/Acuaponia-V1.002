import os
import logging


class Config:
    """
    Configuración centralizada del sistema de medición automática de truchas.

    Este módulo define:
    - Parámetros de cámaras y captura
    - Constantes de calibración geométrica
    - Parámetros biológicos y modelos de estimación
    - Umbrales de validación y control de calidad
    - Rutas de almacenamiento y logging
    """

    # ==========================================================================
    # API EXTERNA
    # ==========================================================================

    # Clave de acceso a la API de MoonDream (cargada desde variables de entorno)
    MOONDREAM_API_KEY = os.getenv("MOONDREAM_API_KEY")
    # Windows (PowerShell):
    # [System.Environment]::SetEnvironmentVariable("MOONDREAM_API_KEY", "TU_CLAVE_AQUI", "User")

    # ==========================================================================
    # CONFIGURACIÓN DE CÁMARAS
    # ==========================================================================

    # Índices físicos de las cámaras
    CAM_LEFT_INDEX = 1   # Cámara lateral
    CAM_TOP_INDEX = 0    # Cámara cenital

    # Resoluciones de captura y guardado
    CAMERA_WIDTH = 1920
    CAMERA_HEIGHT = 1080
    SAVE_WIDTH = 1920
    SAVE_HEIGHT = 1080

    # Parámetros de rendimiento
    PREVIEW_FPS = 60
    BUFFERSIZE = 1

    # Parámetros de salida visual
    TARGET_HEIGHT = 1080        # Altura objetivo del collage final
    TARGET_QUALITY = 100         # Calidad JPEG (0–100)

    # ==========================================================================
    # CALIBRACIÓN DE ESCALAS (cm / píxel)
    # ==========================================================================

    # Cámara lateral
    SCALE_LAT_FRONT = 0.006666   # Zona frontal (más cercana a la cámara)
    SCALE_LAT_BACK = 0.014926    # Zona trasera (más lejana)

    # Cámara cenital
    SCALE_TOP_FRONT = 0.004348
    SCALE_TOP_BACK = 0.0125825

    # ==========================================================================
    # SEGMENTACIÓN POR COLOR (HSV)
    # ==========================================================================

    # Rango HSV para detección del cuerpo de la trucha
    HSV_H_MIN = 35
    HSV_H_MAX = 85
    HSV_S_MIN = 40
    HSV_S_MAX = 255
    HSV_V_MIN = 40
    HSV_V_MAX = 255

    # ==========================================================================
    # PARÁMETROS BIOLÓGICOS
    # ==========================================================================

    # Densidad promedio del tejido de trucha (g/cm³)
    TROUT_DENSITY = 1.04

    # Factor de forma (ajuste volumétrico del modelo elipsoidal)
    FORM_FACTOR = 0.76

    # Relación alométrica Peso–Longitud: W = K * L^b
    WEIGHT_K = 0.0139
    WEIGHT_EXP = 3.02

    # ==========================================================================
    # PROPORCIONES ANATÓMICAS
    # ==========================================================================

    # Altura relativa respecto a la longitud total
    MIN_HEIGHT_RATIO = 0.14
    MAX_HEIGHT_RATIO = 0.35

    # Ancho relativo
    DEFAULT_WIDTH_RATIO = 0.18
    MAX_WIDTH_RATIO_ADULT = 0.22

    # Umbral de clasificación morfológica
    ALEVIN_THRESHOLD_CM = 15.0   # Alevín vs adulto

    # ==========================================================================
    # VALIDACIÓN DE MEDICIONES
    # ==========================================================================

    # Calidad geométrica
    MIN_SKELETON_PIXELS = 20
    BENDING_THRESHOLD = 1.10
    MIN_BOX_SIZE_PX = 15

    # Factor K de Fulton
    K_FACTOR_OPTIMAL = (0.9, 1.5)
    K_FACTOR_ACCEPTABLE = (0.7, 1.9)
    MIN_K_FACTOR = 0.80
    MAX_K_FACTOR = 2.20

    # Control de consistencia peso real vs estimado
    MAX_WEIGHT_DEVIATION = 0.45

    # Calidad de la silueta detectada
    MIN_OCCUPANCY_RATIO = 0.35
    MAX_OCCUPANCY_RATIO = 0.90

    # Rango morfométrico permitido
    MIN_LENGTH_CM = 4.0
    MAX_LENGTH_CM = 50.0

    # Área de contornos (normalizada a 640×480)
    MIN_CONTOUR_AREA = 1500
    MAX_CONTOUR_AREA = 20000

    # Confianza mínima de detección
    CONFIDENCE_THRESHOLD = 0.6

    # ==========================================================================
    # ESTABILIDAD TEMPORAL
    # ==========================================================================

    # Frames consecutivos requeridos para validar una medición estable
    STABILITY_FRAMES = 5

    # ==========================================================================
    # RUTAS Y DIRECTORIOS
    # ==========================================================================

    BASE_DIR = os.path.abspath(os.getcwd())

    OUT_DIR = os.path.join(BASE_DIR, "Resultados")
    DB_DIR = os.path.join(BASE_DIR, "BaseDeDatos")
    LOG_DIR = os.path.join(BASE_DIR, "Eventos")

    CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
    LOG_FILE = os.path.join(LOG_DIR, "app.log")

    IMAGES_AUTO_DIR = os.path.join(OUT_DIR, "Imagenes_Automaticas")
    IMAGES_MANUAL_DIR = os.path.join(OUT_DIR, "Imagenes_Manuales")
    REPORTS_DIR = os.path.join(OUT_DIR, "Reportes")
    CSV_DIR = os.path.join(OUT_DIR, "CSV")
    GRAPHS_DIR = os.path.join(OUT_DIR, "Graficos")

    # Directorios requeridos por el sistema
    DIRS_TO_CREATE = (
        OUT_DIR,
        DB_DIR,
        LOG_DIR,
        IMAGES_AUTO_DIR,
        IMAGES_MANUAL_DIR,
        REPORTS_DIR,
        CSV_DIR,
        GRAPHS_DIR,
    )

    # ==========================================================================
    # MODO DEBUG
    # ==========================================================================

    DEBUG_MODE = False

    # ==========================================================================
    # INICIALIZACIÓN DEL SISTEMA
    # ==========================================================================

    @classmethod
    def initialize(cls):
        """
        Inicializa la configuración del sistema:
        - Crea los directorios necesarios
        - Configura el sistema de logging
        - Verifica la disponibilidad de la API
        """
        for path in cls.DIRS_TO_CREATE:
            os.makedirs(path, exist_ok=True)

        logging.basicConfig(
            filename=cls.LOG_FILE,
            level=logging.DEBUG if cls.DEBUG_MODE else logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            filemode="a"
        )

        cls.logger = logging.getLogger(__name__)

        cls.logger.info("=" * 70)
        cls.logger.info("Sistema de Medición de Truchas - Inicializado")
        cls.logger.info("=" * 70)

        if not cls.MOONDREAM_API_KEY:
            cls.logger.error("API KEY no detectada. Verificar variables de entorno.")
        else:
            cls.logger.info("API KEY cargada correctamente.")

    # ==========================================================================
    # UTILIDADES
    # ==========================================================================

    @staticmethod
    def calcular_escala_proporcional(valor_y, max_y, escala_frente, escala_fondo):
        """
        Calcula una escala proporcional basada en la posición vertical del objeto.

        Se utiliza interpolación lineal para compensar la distorsión por perspectiva.

        Parámetros:
            valor_y (float): Posición vertical del objeto en píxeles
            max_y (float): Altura máxima de la imagen
            escala_frente (float): Escala en la zona cercana a la cámara
            escala_fondo (float): Escala en la zona lejana

        Retorna:
            float: Escala interpolada en cm/píxel
        """
        if max_y <= 0:
            return escala_frente

        proporcion = valor_y / max_y
        return escala_frente + (escala_fondo - escala_frente) * proporcion


# Inicialización automática de la configuración
Config.initialize()
