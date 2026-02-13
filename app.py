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
from Modulos.ApiService import ApiService

logger = logging.getLogger(__name__)
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"

def main():
    """
    Inicializa los directorios del sistema, configura el estilo de la 
    aplicación y lanza la ventana principal.
    """
    
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
        
    api_service = ApiService(port=5001)
    api_service.start() 
    logger.info(f"Servicio API iniciado. Tunnel: {api_service.get_public_url()}.")
    
    app = QApplication([])
    app.setStyle('Fusion')
    
    window = MainWindow(api_service=api_service)
    window.show()
    
    logger.info("Sistema FishTrace iniciado correctamente.")
    
    exit_code = app.exec()
    
    cv2.destroyAllWindows()
    return exit_code

if __name__ == "__main__":
    main()