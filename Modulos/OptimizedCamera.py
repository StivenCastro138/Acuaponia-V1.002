import cv2
import threading
import logging
from Config.Config import Config

logger = logging.getLogger(__name__)

class OptimizedCamera:
    def __init__(self, camera_index):
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH) 
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, Config.PREVIEW_FPS)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, Config.BUFFERSIZE)
                
        # Threading para captura continua
        self.latest_frame = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        
    def start(self):
        """Inicia el hilo de captura"""
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        return self
    
    def _capture_loop(self):
        """Loop de captura en thread separado"""
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.latest_frame = frame
    
    def read(self):
        """Obtiene el frame más reciente (thread-safe)"""
        with self.lock:
            if self.latest_frame is not None:
                return True, self.latest_frame.copy()
            return False, None
    
    def stop(self):
        """Detiene el hilo de captura"""
        self.running = False
        if self.thread:
            self.thread.join()
        self.cap.release()
    
    def isOpened(self):
        """Verifica si la cámara está abierta"""
        return self.cap.isOpened()
    
    def release(self):
        """Alias para compatibilidad con llamadas tipo OpenCV"""
        self.stop()
