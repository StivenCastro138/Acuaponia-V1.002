import cv2
from PySide6.QtCore import QThread, Signal, QObject
import time
import queue
import logging
import numpy as np
from .FishDetector import FishDetector
from .FishTracker import FishTracker
from .SimpleMotionDetector import SimpleMotionDetector
from .BiometryService import BiometryService
from Config.Config import Config

logger = logging.getLogger(__name__)

class ProcessorSignals(QObject):
    """Clase para agrupar todas las señales del procesador"""
    result_ready = Signal(dict)
    progress_update = Signal(str)
    ia_time_ready = Signal(float) 
    roi_status = Signal(bool)

class FrameProcessor(QThread):
    result_ready = Signal(dict)
    progress_update = Signal(str)  
    
    def __init__(self, moondream_detector_instance):
        super().__init__()
        self.signals = ProcessorSignals()
        self.queue = queue.Queue(maxsize=1)
        self.running = True
        
        # Módulos auxiliares
        self.chroma_detector = FishDetector() 
        self.tracker = FishTracker()
        self.motion_detector = SimpleMotionDetector(threshold=12)
        
        # Servicio de biometría
        self.biometry_service = BiometryService(moondream_detector_instance)
        
        self.processing = False
        self.frame_count = 0
        self.skip_validation = False 
        self.capture_requested = False
        
        self.moondream_detector = moondream_detector_instance
        self._check_ai_status()

    def _check_ai_status(self):
        if self.moondream_detector and hasattr(self.moondream_detector, 'is_ready') and self.moondream_detector.is_ready:
            self.signals.progress_update.emit("✅ IA Avanzada + Spine Measurer listos.")
        else:
            self.signals.progress_update.emit("⚠️ Modo básico (Solo Cajas).")

    def add_frame(self, frame_left, frame_top, params):
        try:
            if not self.queue.empty():
                try: 
                    self.queue.get_nowait()
                except queue.Empty: 
                    pass
            
            self.capture_requested = True
            self.queue.put((frame_left, frame_top, params))
            return True 
        except Exception as e:
            logger.error(f"Error anadiendo frame a cola: {e}")
            return False 

    def run(self):
        """Loop principal optimizado."""
        logger.info("FrameProcessor iniciado.")
        while self.running:
            try:
                frame_left, frame_top, params = self.queue.get(timeout=0.1)
                
                # Verificar estabilidad
                should_process = (
                    self.motion_detector.is_stable(frame_left) or 
                    self.capture_requested or
                    Config.DEBUG_MODE
                )
                self.capture_requested = False 

                if not should_process and not self.skip_validation:
                    # --- OPTIMIZACIÓN PUNTO 3 (UI LAG) ---
                    # Solo emitir señal a la UI cada 30 frames (aprox 1 seg) para no congelar la app
                    if self.frame_count % 30 == 0:
                        motion_level = self.motion_detector.get_motion_level()
                        self.signals.progress_update.emit(
                            f"⏳ Esperando estabilidad... ({motion_level:.1f}%)"
                        )
                    
                    self.queue.task_done()
                    self.frame_count += 1
                    continue

                # Procesar frames
                self.signals.progress_update.emit("🔬 Iniciando análisis biométrico...")
                result = self.process_frames(frame_left, frame_top, params)
                
                if result:
                    self.result_ready.emit(result)
                    self.signals.result_ready.emit(result)
                else:
                    self.result_ready.emit({})
                
                self.queue.task_done()
                self.frame_count += 1
                
            except queue.Empty: 
                continue
            except Exception as e:
                logger.error(f"Error en FrameProcessor loop: {str(e)}")
                self.result_ready.emit({})

    def process_frames(self, frame_left, frame_top, params):
        try:
            start_time = time.time()
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 1. ✅ EXTRACCIÓN DE PARÁMETROS (INCLUYE HSV INDEPENDIENTES)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            scale_front_left = params.get('scale_front_left', 0.006666)
            scale_back_left = params.get('scale_back_left', 0.014926)
            scale_front_top = params.get('scale_front_top', 0.004348)
            scale_back_top = params.get('scale_back_top', 0.012582)

            # ✅ NUEVO: Extraer valores HSV independientes
            hsv_left = {
                'h_min': params.get('hue_left_min', 35),
                'h_max': params.get('hue_left_max', 85),
                's_min': params.get('sat_left_min', 40),
                's_max': params.get('sat_left_max', 255),
                'v_min': params.get('val_left_min', 40),
                'v_max': params.get('val_left_max', 255)
            }
            
            hsv_top = {
                'h_min': params.get('hue_top_min', 35),
                'h_max': params.get('hue_top_max', 85),
                's_min': params.get('sat_top_min', 40),
                's_max': params.get('sat_top_max', 255),
                'v_min': params.get('val_top_min', 40),
                'v_max': params.get('val_top_max', 255)
            }

            # 2. VALIDACIÓN DE ESTABILIDAD
            is_stable = self.motion_detector.is_stable(frame_left)
            if not is_stable and not self.skip_validation and not Config.DEBUG_MODE:
                return None

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 3. ✅ ANÁLISIS BIOMETRYSERVICE (Con parámetros HSV)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            self.signals.progress_update.emit("🧠 Analizando con BiometryService...")
            ia_start = time.time()
            
            try:
                metrics, img_lat_ann, img_top_ann = self.biometry_service.analyze_and_annotate(
                    img_lat=frame_left,
                    img_top=frame_top,
                    scale_lat_front=scale_front_left,
                    scale_lat_back=scale_back_left,
                    scale_top_front=scale_front_top,
                    scale_top_back=scale_back_top,                   
                    draw_box=Config.DEBUG_MODE,   
                    draw_skeleton=Config.DEBUG_MODE
                )

                if Config.DEBUG_MODE and img_lat_ann is not None:
                    cv2.imshow('DEBUG: Skeleton', img_lat_ann)
                    
            except Exception as e:
                logger.error(f"Error en BiometryService: {e}")
                self.signals.progress_update.emit(f"❌ Error en análisis: {str(e)}")
                return None
            
            ia_end = time.time()
            ia_time_ms = (ia_end - ia_start) * 1000
            self.signals.ia_time_ready.emit(ia_time_ms)

            # 4. VALIDACIÓN DE RESULTADOS
            if not metrics or metrics.get('length_cm', 0) <= 0:
                self.signals.progress_update.emit("❌ No se detectó pez.")
                self.signals.roi_status.emit(False)
                return None

            self.signals.roi_status.emit(True)
            self.signals.progress_update.emit("✅ Análisis completado.")

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 5. ✅ TRACKER (Ahora con HSV lateral específico)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            contour_lat = self._retrieve_contour_for_tracker(frame_left, hsv_left)
            
            self.tracker.update(contour_lat, metrics, timestamp=start_time)

            # 6. CALCULAR CONFIANZA
            confidence = self._calculate_confidence(metrics, is_stable, ia_time_ms)

            # 7. CONSTRUIR RESULTADO
            result = {
                'frame_left': img_lat_ann if img_lat_ann is not None else frame_left,
                'frame_top': img_top_ann if img_top_ann is not None else frame_top,
                'contour_left': contour_lat,
                'contour_top': None,
                'metrics': metrics,
                'smoothed_metrics': self.tracker.get_smoothed_measurement(),
                'is_consistent': self.tracker.get_tracking_stats()['is_consistent'],
                'confidence': confidence,
                'processing_time': (time.time() - start_time) * 1000,
                'ia_time': ia_time_ms,
                'is_stable': is_stable,
                'scale_left': scale_front_left,
                'scale_top': scale_front_top,
                'status': metrics.get('status', 'Procesado'),
                'frame_count': self.frame_count
            }

            logger.info(
                f"Frame procesado: L={metrics['length_cm']:.1f}cm, "
                f"Conf={confidence:.1%}, T={ia_time_ms:.0f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Error critico en process_frames: {str(e)}", exc_info=True)
            self.signals.progress_update.emit(f"❌ Error: {str(e)}")
            return None

    def _retrieve_contour_for_tracker(self, clean_frame, hsv_params):
        """
        ✅ VERSIÓN CORREGIDA: Acepta parámetros HSV específicos para la cámara
        
        Args:
            clean_frame: Frame de la cámara
            hsv_params: Dict con h_min, h_max, s_min, s_max, v_min, v_max
        """
        if clean_frame is None:
            return None
        
        try:
            # ✅ Aplicar chroma key con valores HSV específicos de esta cámara
            lower = np.array([hsv_params['h_min'], hsv_params['s_min'], hsv_params['v_min']])
            upper = np.array([hsv_params['h_max'], hsv_params['s_max'], hsv_params['v_max']])
            
            # Convertir a HSV
            hsv = cv2.cvtColor(clean_frame, cv2.COLOR_BGR2HSV)
            
            # Crear máscara del FONDO (verde)
            mask_background = cv2.inRange(hsv, lower, upper)
            
            # Invertir para obtener máscara del PEZ
            mask = cv2.bitwise_not(mask_background)
            
            # Limpieza morfológica
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            
            if Config.DEBUG_MODE:
                cv2.imshow('DEBUG: Mask', mask)

            if mask is None or mask.size == 0:
                return None
            
            # Encontrar contorno
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filtro rápido de área
            valid = [c for c in contours if cv2.contourArea(c) >= 500]
            return max(valid, key=cv2.contourArea) if valid else None

        except Exception as e:
            logger.debug(f"No se pudo extraer contorno para tracker: {e}")
            return None

    def _calculate_confidence(self, metrics, is_stable, ia_time_ms):
        """Calcula score de confianza."""
        confidence = 0.8
        
        if is_stable: confidence += 0.1
        if ia_time_ms > 3000: confidence -= 0.1
        
        tracker_stats = self.tracker.get_tracking_stats()
        if tracker_stats['is_consistent']: confidence += 0.05
        
        length = metrics.get('length_cm', 0)
        weight = metrics.get('weight_g', 0)
        
        if length < Config.MIN_LENGTH_CM or length > Config.MAX_LENGTH_CM: confidence -= 0.2
        if weight <= 0: confidence -= 0.1
        
        k_factor = metrics.get('condition_factor', 0)
        if 0.8 <= k_factor <= 1.8: confidence += 0.05
        
        return max(0.0, min(1.0, confidence))

    def stop(self):
        logger.info("Deteniendo FrameProcessor...")
        self.running = False
        try:
            while not self.queue.empty():
                self.queue.get_nowait()
                self.queue.task_done()
        except queue.Empty:
            pass
    
    def set_hsv_ranges(self, h_min, h_max, s_min, s_max, v_min, v_max):
        if hasattr(self.chroma_detector, 'set_hsv_ranges'):
            self.chroma_detector.set_hsv_ranges(h_min, h_max, s_min, s_max, v_min, v_max)
            logger.info(f"HSV ranges updated")