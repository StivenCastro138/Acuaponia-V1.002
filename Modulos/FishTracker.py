import cv2
import numpy as np
import time
from collections import deque

class FishTracker:
    def __init__(self, max_history=30):
        self.positions = deque(maxlen=max_history)
        self.measurements = deque(maxlen=max_history)
        self.timestamps = deque(maxlen=max_history)
        
        self.max_length_change = 2.0  
        self.max_cv_threshold = 10.0  
    
    def update(self, contour, metrics, timestamp=None):
        """Agrega nueva medición al historial si hay un contorno válido"""
        if contour is not None and metrics:
            M = cv2.moments(contour)
            if M['m00'] != 0:
                cx = M['m10'] / M['m00']
                cy = M['m01'] / M['m00']
                self.positions.append((cx, cy))
                self.measurements.append(metrics)
                self.timestamps.append(timestamp or time.time())
    
    def get_smoothed_measurement(self):
        """
        Retorna medición suavizada.
        """
        if len(self.measurements) < 3:
            return None 

        # Extracción robusta de series de datos 
        lengths = [float(m.get('length_cm', 0)) for m in self.measurements]
        heights = [float(m.get('height_cm', 0)) for m in self.measurements]
        widths = [float(m.get('width_cm', 0)) for m in self.measurements]
        weights_g = [float(m.get('weight_g', 0)) for m in self.measurements]
        lat_areas = [float(m.get('lat_area_cm2', m.get('area_cm2', 0))) for m in self.measurements]
        zen_areas = [float(m.get('top_area_cm2', 0)) for m in self.measurements]
        volumes = [float(m.get('volume_cm3', 0)) for m in self.measurements]

        # Verificar estabilidad 
        if np.std(lengths) > self.max_length_change:
            return None 
        
        # Pesos exponenciales 
        w = np.linspace(0.5, 1.0, len(self.measurements))
        w /= w.sum()
        
        # Cálculo de promedios ponderados
        smoothed = {
            'length_cm': np.average(lengths, weights=w),
            'height_cm': np.average(heights, weights=w),
            'width_cm': np.average(widths, weights=w),
            'weight_g': np.average(weights_g, weights=w),
            'lat_area_cm2': np.average(lat_areas, weights=w),
            'top_area_cm2': np.average(zen_areas, weights=w),
            'volume_cm3': np.average(volumes, weights=w),
            'confidence': self.measurements[-1].get('confidence', 0.8)
        }
        
        return smoothed

    def get_tracking_stats(self):
        """Calcula la calidad del tracking basándose en la estabilidad"""
        
        count = len(self.measurements)
        if count == 0:
            return {'quality': 0, 'is_consistent': False, 'cv': 100.0}
        
        if count < 5:
            return {
                'quality': 100,      
                'is_consistent': True, 
                'cv': 0.0        
            }
        
        lengths = [m.get('length_cm', 0) for m in self.measurements]
        mean_l = np.mean(lengths)
        
        if mean_l == 0: return {'quality': 0, 'is_consistent': False, 'cv': 100.0}
        
        cv = (np.std(lengths) / mean_l) * 100
        quality = max(0, 100 - (cv * 10))
        
        return {
            'quality': min(100, quality),
            'is_consistent': cv < self.max_cv_threshold,
            'cv': cv
        }
    
    def clear(self):
        self.positions.clear()
        self.measurements.clear()
        self.timestamps.clear()