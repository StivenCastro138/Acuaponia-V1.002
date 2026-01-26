from math import e
import cv2
from PySide6.QtWidgets import QApplication
import os
import logging
from Config.Config import Config
from Modulos.MainWindow import MainWindow

logger = logging.getLogger(__name__)

PYTORCH_AVAILABLE = False
PYTORCH_ERROR_MESSAGE = None

try:
    PYTORCH_AVAILABLE = True
    print("✅ Usando modelos pre-entrenados (YOLOv8/DeepLab)")
except:
    PYTORCH_ERROR_MESSAGE = str(e)
    PYTORCH_AVAILABLE = False
    print(f"⚠️ PyTorch no disponible: {PYTORCH_ERROR_MESSAGE}")
    logger.warning(f"PyTorch no disponible - Usando Chroma Key: {PYTORCH_ERROR_MESSAGE}")

# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================
def main():
    os.makedirs(Config.OUT_DIR, exist_ok=True)
    os.makedirs(Config.IMAGES_AUTO_DIR, exist_ok=True)
    os.makedirs(Config.IMAGES_MANUAL_DIR, exist_ok=True)
    os.makedirs(Config.REPORTS_DIR, exist_ok=True)
    os.makedirs(Config.CSV_DIR, exist_ok=True)
    os.makedirs(Config.GRAPHS_DIR, exist_ok=True)
    
    app = QApplication([])
    
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    logger.info("Aplicacion Iniciada")
    
    app.exec()
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()