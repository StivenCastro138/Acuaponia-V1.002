import cv2
import numpy as np
from ultralytics import YOLO

class AIDetector:
    def __init__(self):
        self.model = YOLO('yolo11n-seg.pt') 
        
    def get_fish_mask(self, frame):
        """
        Usa IA para encontrar el pez y retornar una máscara binaria.
        Solo detecta la clase 'fish' (id 73 en el dataset COCO).
        """
        # Ejecutamos la predicción (conf 0.5 para ser seguros)
        results = self.model.predict(frame, classes=[73], conf=0.4, verbose=False)
        
        height, width = frame.shape[:2]
        
        for r in results:
            if r.masks is not None:
                # Obtenemos la máscara de la primera detección de pez
                mask_data = r.masks.data[0].cpu().numpy()
                # Redimensionamos la máscara al tamaño original del frame
                full_mask = cv2.resize(mask_data, (width, height))
                # Convertimos a formato 8-bit (0 y 255)
                binary_mask = (full_mask > 0.5).astype(np.uint8) * 255
                return binary_mask
                
        return np.zeros((height, width), dtype=np.uint8)