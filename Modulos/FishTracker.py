"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Rastreador Temporal (FishTracker.py)
DESCRIPCIÓN: Implementa lógica de suavizado temporal para estabilizar las mediciones
             biométricas a lo largo de una secuencia de video. Reduce el "jitter" (ruido)
             causado por micro-movimientos del pez o fluctuaciones de la segmentación.
"""

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
    
    def update(self, contour_left, contour_top, metrics, timestamp=None):
        """Actualiza tracking usando ambas vistas (fusión espacial)."""

        if not metrics:
            return

        centroids = []

        # Lateral
        if contour_left is not None:
            M = cv2.moments(contour_left)
            if M['m00'] != 0:
                centroids.append((
                    M['m10'] / M['m00'],
                    M['m01'] / M['m00']
                ))

        # Cenital
        if contour_top is not None:
            M = cv2.moments(contour_top)
            if M['m00'] != 0:
                centroids.append((
                    M['m10'] / M['m00'],
                    M['m01'] / M['m00']
                ))

        if not centroids:
            return

        cx = np.mean([c[0] for c in centroids])
        cy = np.mean([c[1] for c in centroids])

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
        """Evalúa estabilidad biométrica + espacial."""

        count = len(self.measurements)

        if count < 5:
            return {'quality': 0, 'is_consistent': False, 'cv': 100.0}

        lengths = [m.get('length_cm', 0) for m in self.measurements]
        mean_l = np.mean(lengths)

        if mean_l == 0:
            return {'quality': 0, 'is_consistent': False, 'cv': 100.0}

        cv = (np.std(lengths) / mean_l) * 100

        xs = [p[0] for p in self.positions]
        ys = [p[1] for p in self.positions]

        motion = np.std(xs) + np.std(ys)

        # Penalización combinada
        quality = 100 - (cv * 5) - (motion * 0.05)
        quality = max(0, min(100, quality))

        return {
            'quality': quality,
            'is_consistent': cv < self.max_cv_threshold and motion < 15,
            'cv': cv
        }

    def clear(self):
        self.positions.clear()
        self.measurements.clear()
        self.timestamps.clear()