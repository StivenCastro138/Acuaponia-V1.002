"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Punto de Entrada Principal (app.py)
DESCRIPCIÓN: Inicializa el entorno, verifica dependencias de IA y lanza la 
             interfaz gráfica de usuario (GUI).
"""

import cv2
import os
import logging
from PySide6.QtWidgets import QApplication

from Config.Config import Config
from Modulos.MainWindow import MainWindow

logger = logging.getLogger(__name__)
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
# ============================================================================
# PROCEDIMIENTO PRINCIPAL (MAIN)
# ============================================================================
def main():
    """
    Inicializa los directorios del sistema, configura el estilo de la 
    aplicación y lanza la ventana principal.
    """
    
    # 1. Creación de la estructura de carpetas necesaria para la persistencia de datos
    folders = [
        Config.OUT_DIR, 
        Config.IMAGES_AUTO_DIR, 
        Config.IMAGES_MANUAL_DIR, 
        Config.REPORTS_DIR, 
        Config.CSV_DIR, 
        Config.GRAPHS_DIR
    ]
    
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
    
    # 2. Inicialización de la aplicación
    app = QApplication([])
    app.setStyle('Fusion')
    
    # 3. Lanzamiento de la interfaz de usuario
    window = MainWindow()
    window.show()
    
    logger.info("Sistema FishTrace iniciado correctamente.")
    
    # 4. Ciclo de eventos de la aplicación
    exit_code = app.exec()
    
    # 5. Limpieza de recursos al cerrar
    cv2.destroyAllWindows()
    return exit_code

if __name__ == "__main__":
    main()