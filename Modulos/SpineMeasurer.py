"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Medidor de Columna Vertebral (SpineMeasurer.py)
DESCRIPCIÓN: Motor de geometría computacional avanzado. Utiliza algoritmos de esqueletización,
             teoría de grafos y ajuste de curvas (Splines) para medir la longitud real
             de un organismo curvado con precisión sub-píxel.
"""

import cv2
import numpy as np
import logging
import networkx as nx
from scipy.interpolate import splprep, splev
from typing import Tuple, Optional

from Config.Config import Config

logger = logging.getLogger(__name__)

class SpineMeasurer:
    """
    Motor de medición biométrica de alta precisión basado en análisis topológico (Grafos + Splines).
    """
    
    @staticmethod
    def get_spine_info(mask_uint8: np.ndarray) -> Tuple[float, Optional[np.ndarray]]:
        if mask_uint8 is None or cv2.countNonZero(mask_uint8) < 100:
            return 0.0, None

        # 1. Limpieza de máscara
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel, iterations=1)

        # 2. Esqueletización y primer recorte
        try:
            skeleton = cv2.ximgproc.thinning(binary, thinningType=cv2.ximgproc.THINNING_ZHANGSUEN)
            skeleton = cv2.bitwise_and(skeleton, binary) # Candado 1
        except Exception as e:
            logger.error(f"Error en esqueletizacion: {e}")
            return 0.0, None

        # 3. Análisis de Grafo
        ordered_points_yx = SpineMeasurer._get_longest_path_graph(skeleton)
        if ordered_points_yx is None:
            return 0.0, skeleton

        # 4. Medición Sub-píxel con DIBUJO PROTEGIDO
        # Ahora devolvemos la visualización de la curva ya recortada
        length_px, visualization = SpineMeasurer._calculate_spline_and_visualize(ordered_points_yx, binary)
        
        return length_px, visualization

    @staticmethod
    def _calculate_spline_and_visualize(points_yx: np.ndarray, mask_limit: np.ndarray) -> Tuple[float, np.ndarray]:
        """
        Calcula longitud y genera la imagen roja asegurando que nada se salga del pez.
        """
        h, w = mask_limit.shape
        curve_viz = np.zeros((h, w), dtype=np.uint8)
        
        if len(points_yx) < 5:
            # Si hay pocos puntos, dibujar líneas rectas simples
            for i in range(len(points_yx)-1):
                p1 = (int(points_yx[i][1]), int(points_yx[i][0]))
                p2 = (int(points_yx[i+1][1]), int(points_yx[i+1][0]))
                cv2.line(curve_viz, p1, p2, 255, 1)
            final_viz = cv2.bitwise_and(curve_viz, mask_limit)
            return float(cv2.countNonZero(final_viz)), final_viz

        try:
            y, x = points_yx[:, 0], points_yx[:, 1]
            tck, u = splprep([y, x], s=0.05, k=3) 
            u_fine = np.linspace(0, 1, len(x) * 15) 
            new_points = splev(u_fine, tck)
            v_y, v_x = new_points[0], new_points[1]

            # Dibujamos el spline en un lienzo temporal
            for i in range(len(v_x) - 1):
                p1 = (int(v_x[i]), int(v_y[i]))
                p2 = (int(v_x[i+1]), int(v_y[i+1]))
                # Verificación de bordes de imagen
                if (0 <= p1[1] < h and 0 <= p1[0] < w and 0 <= p2[1] < h and 0 <= p2[0] < w):
                    cv2.line(curve_viz, p1, p2, 255, 1)

            # EL SEGURO FINAL: Bitwise AND con la máscara
            # Esto borra cualquier píxel rojo que la matemática haya tirado fuera del pez
            guaranteed_spine = cv2.bitwise_and(curve_canvas := curve_viz, mask_limit)
            
            return float(cv2.countNonZero(guaranteed_spine)), guaranteed_spine

        except Exception:
            return 0.0, mask_limit # Fallback
        
    @staticmethod
    def _get_longest_path_graph(skeleton: np.ndarray) -> Optional[np.ndarray]:
        """
        Convierte esqueleto a grafo y busca el diámetro (camino más largo).
        """
        ys, xs = np.where(skeleton > 0)
        pixels = np.column_stack((ys, xs))
        
        if len(pixels) < Config.MIN_SKELETON_PIXELS:
            return None

        G = nx.Graph()
        pixel_set = set(map(tuple, pixels))
        
        for y, x in pixels:
            G.add_node((y, x))
            neighbors = [
                (y, x+1), (y+1, x-1), (y+1, x), (y+1, x+1)
            ]
            for ny, nx_coord in neighbors:
                if (ny, nx_coord) in pixel_set:
                    dist = np.sqrt((ny-y)**2 + (nx_coord-x)**2) 
                    G.add_edge((y, x), (ny, nx_coord), weight=dist)

        if not nx.is_connected(G):
            largest_cc = max(nx.connected_components(G), key=len)
            G = G.subgraph(largest_cc).copy()

        if G.number_of_nodes() < Config.MIN_SKELETON_PIXELS:
            return None

        endpoints = [node for node, degree in G.degree() if degree == 1]

        if not endpoints:
            endpoints = [list(G.nodes())[0]]
        
        try:
            # 1. BFS desde nodo arbitrario para hallar u 
            start_node = endpoints[0] if endpoints else list(G.nodes())[0]
            lengths_from_start = nx.single_source_dijkstra_path_length(G, start_node)
            u = max(lengths_from_start, key=lengths_from_start.get)
            
            # 2. BFS desde u para hallar v 
            lengths_from_u = nx.single_source_dijkstra_path_length(G, u)
            v = max(lengths_from_u, key=lengths_from_u.get)
            
            # 3. Recuperar el camino
            best_path = nx.shortest_path(G, u, v, weight='weight')
            
        except Exception as e:
            logger.error("Error en busqueda de camino grafo.", exc_info=True)
            return None

        return np.array(best_path)
        
    @staticmethod
    def _skeletonize_fallback(img: np.ndarray) -> np.ndarray:
        """Fallback lento usando morfología estándar."""
        skel = np.zeros(img.shape, np.uint8)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        temp = img.copy()
        
        while True:
            eroded = cv2.erode(temp, element)
            temp_open = cv2.dilate(eroded, element)
            temp_sub = cv2.subtract(temp, temp_open)
            skel = cv2.bitwise_or(skel, temp_sub)
            temp = eroded.copy()
            if cv2.countNonZero(temp) == 0:
                break
        return skel