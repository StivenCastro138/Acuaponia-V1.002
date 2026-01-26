import os
import logging

class Config:
    """
    Configuración centralizada para el sistema de medición de truchas.
    """
    
    # ============================================================================
    # API Y SEGURIDAD
    # ============================================================================
    
    # MOONDREAM_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXlfaWQiOiI2YmQ1NzcwMi1mMDc2LTQ5YmMtYjExYS05NGJlMzlhODM2ZmEiLCJvcmdfaWQiOiJDdFB6WTdSZmRUckw4U3R5a1JOcFo4NjdJYVZhZ0tBTSIsImlhdCI6MTc2MjgwNzk4NiwidmVyIjoxfQ.f-bsdQwxTm5QU8JRhhIV0zGwbYc1cre-qMLxkJTN93o"
    # MOONDREAM_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXlfaWQiOiIzMzNjODMyNy1kMGVhLTQxNzItODlmNi1hNmYxMzFiZTZmZTEiLCJvcmdfaWQiOiIzSHRnb3NkSjRIMm9Mdm9wUUMzYmxxNW05eTdoU0tBdiIsImlhdCI6MTc2MTg1ODU4NiwidmVyIjoxfQ.0p4LmxSUsH1XPmeLj4-mbfCIhMYiT6GTqt3yImdvByU"
    # MOONDREAM_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXlfaWQiOiI0MzFkNjdiNC01OWU1LTQ2YzQtYWJiNS1mM2VjNGYwMmNiMzciLCJvcmdfaWQiOiJTZTQxck9laHM5Y0tqcDdhVUt0bEZEZHFOT1BiYlUxbyIsImlhdCI6MTc2MTg3MzI1MywidmVyIjoxfQ.uL1yepTzbLwgzmUaLdcscEjNLul2B7kMxp4sYqeT7vA"
    MOONDREAM_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXlfaWQiOiIwMDA0MTBmOS03ZDk1LTQ1OTUtYTgxZC0yZjIwYzYyNzEwOGYiLCJvcmdfaWQiOiJHbmc2Z1BWcGxHUnhkOEczeVFWTUpFQWllVXY0ZGdWaSIsImlhdCI6MTc2ODUxNjU5NiwidmVyIjoxfQ.jB5kzhZ8PV-9uNgJ_R0Bg4CCWFCtv8OV4tTiWZ9tQOw"
    
    if not MOONDREAM_API_KEY:
        logging.warning("MOONDREAM_API_KEY no configurada. Algunas funciones no estaran disponibles.")
    
    # ============================================================================
    # CONFIGURACIÓN DE CÁMARAS
    # ============================================================================
    
    # Índices de cámaras 
    CAM_LEFT_INDEX = 1  # Cámara lateral
    CAM_TOP_INDEX = 0   # Cámara cenital
    
    # Resoluciones
    CAMERA_WIDTH = 1920   
    CAMERA_HEIGHT = 1080 
    SAVE_WIDTH = 1920
    SAVE_HEIGHT = 1080
    PREVIEW_FPS = 60  
    BUFFERSIZE = 1  
    
    # Dimensiones objetivo para el collage
    TARGET_HEIGHT = 1080
    TARGET_QUALITY = 95
    
    # ============================================================================
    # CALIBRACIÓN DE ESCALAS (cm/px)
    # ============================================================================
    
    # Cámara Lateral: interpolación lineal según profundidad Y
    SCALE_LAT_FRONT = 0.006666  # Parte frontal (cerca de cámara)
    SCALE_LAT_BACK = 0.014926   # Parte trasera (lejos de cámara)
    
    # Cámara Cenital: interpolación lineal según profundidad Y
    SCALE_TOP_FRONT = 0.004348  # Parte frontal
    SCALE_TOP_BACK = 0.0125825  # Parte trasera
    
    HSV_H_MIN = 35
    HSV_H_MAX = 85
    HSV_S_MIN = 40
    HSV_S_MAX = 255
    HSV_V_MIN = 40
    HSV_V_MAX = 255
    
    # ============================================================================
    # PARÁMETROS BIOLÓGICOS DE TRUCHAS
    # ============================================================================
    
    # Densidad promedio del tejido de trucha
    TROUT_DENSITY = 1.04  # g/cm³
    
    # Factor de forma (coeficiente de volumen/elipsoide)
    FORM_FACTOR = 0.76  
    
    # Relación Peso-Longitud (Ecuación Alométrica)
    WEIGHT_K = 0.0139      # Coeficiente
    WEIGHT_EXP = 3.02      # Exponente (~3 para crecimiento isométrico)
    
    # ============================================================================
    # PROPORCIONES ANATÓMICAS (Ratios relativos a longitud)
    # ============================================================================
    
    # Altura (alto) como porcentaje del largo
    MIN_HEIGHT_RATIO = 0.14  # Truchas muy delgadas
    MAX_HEIGHT_RATIO = 0.35  # Truchas robustas
    
    # Ancho como porcentaje del largo
    DEFAULT_WIDTH_RATIO = 0.18      # Valor típico
    MAX_WIDTH_RATIO_ADULT = 0.22    # Adultos robustos
    
    # Umbral para clasificar alevines vs adultos
    ALEVIN_THRESHOLD_CM = 15.0
    
    # ============================================================================
    # VALIDACIÓN DE MEDICIONES
    # ============================================================================
    
    # Validación de detecciones
    MIN_SKELETON_PIXELS = 20    # Longitud mínima del esqueleto morfológico
    BENDING_THRESHOLD = 1.10    # Curvatura máxima: ratio geodésica/euclidiana
    MIN_BOX_SIZE_PX = 15        # Tamaño mínimo del bounding box (px)
    
    K_FACTOR_OPTIMAL = (0.9, 1.5)      # Rango óptimo
    K_FACTOR_ACCEPTABLE = (0.7, 1.9)   # Rango aceptable
    
    # Factor K de Fulton 
    MIN_K_FACTOR = 0.80  # Desnutridas
    MAX_K_FACTOR = 2.20  # Sobrealimentadas
    
    # Desviación máxima entre peso medido y peso teórico
    MAX_WEIGHT_DEVIATION = 0.45  
    
    # Solidez de la silueta (Área / Área_BoundingBox)
    MIN_OCCUPANCY_RATIO = 0.35 
    MAX_OCCUPANCY_RATIO = 0.90  
    
    # Rango de longitudes válidas
    MIN_LENGTH_CM = 4.0
    MAX_LENGTH_CM = 50.0
    
    # Rango de áreas de contornos (píxeles a 640×480)
    MIN_CONTOUR_AREA = 1500   
    MAX_CONTOUR_AREA = 20000 
    
    # Umbral de confianza de detección
    CONFIDENCE_THRESHOLD = 0.6
    
    # ============================================================================
    # ESTABILIDAD Y FILTRADO
    # ============================================================================
    
    # Número de frames consecutivos para confirmar detección estable
    STABILITY_FRAMES = 5
    
    # ============================================================================
    # RUTAS Y DIRECTORIOS
    # ============================================================================
    
    BASE_DIR = os.path.abspath(os.getcwd())
    
    # Directorios principales
    OUT_DIR = os.path.join(BASE_DIR, "Resultados")
    DB_DIR = os.path.join(BASE_DIR, "BaseDeDatos")
    LOG_DIR = os.path.join(BASE_DIR, "Eventos")
    
    # Archivos de configuración
    CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
    LOG_FILE = os.path.join(LOG_DIR, "app.log")
    
    # Subdirectorios de salida
    IMAGES_AUTO_DIR = os.path.join(OUT_DIR, "Imagenes_Automaticas")
    IMAGES_MANUAL_DIR = os.path.join(OUT_DIR, "Imagenes_Manuales")
    REPORTS_DIR = os.path.join(OUT_DIR, "Reportes")
    CSV_DIR = os.path.join(OUT_DIR, "CSV")
    GRAPHS_DIR = os.path.join(OUT_DIR, "Graficos")
    
    # Lista de directorios a crear
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
    
    # ============================================================================
    # MODO DEBUG
    # ============================================================================
    
    DEBUG_MODE = False
    
    # ============================================================================
    # INICIALIZACIÓN
    # ============================================================================
    
    @classmethod
    def initialize(cls):
        """Crea directorios necesarios y configura logging."""
        # Crear directorios
        for path in cls.DIRS_TO_CREATE:
            os.makedirs(path, exist_ok=True)
        
        # Configurar logging
        logging.basicConfig(
            filename=cls.LOG_FILE,
            level=logging.DEBUG if cls.DEBUG_MODE else logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            filemode="a"
        )
        
        cls.logger = logging.getLogger(__name__)
        
        # Log inicial
        cls.logger.info("=" * 70)
        cls.logger.info("Sistema de Medicion de Truchas - Inicializado")
        cls.logger.info("=" * 70)
    
    # ============================================================================
    # MÉTODOS AUXILIARES
    # ============================================================================
    
    @staticmethod
    def calcular_escala_proporcional(valor_y, max_y, escala_frente, escala_fondo):
        """
        Interpolación lineal: 
        Si valor_y es max_y (ABAJO/FRENTE), devuelve escala_frente.
        Si valor_y es 0 (ARRIBA/FONDO), devuelve escala_fondo.
        """
        if max_y <= 0: return escala_frente
        
        proporcion = valor_y / max_y
        peso_fondo = proporcion
        
        return escala_frente + (escala_fondo - escala_frente) * peso_fondo
    
Config.initialize()