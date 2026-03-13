"""
PROYECTO: FishTrace - Trazabilidad de Crecimiento de Peces
MÓDULO: Pasarela de Captura Móvil (Mobile Gateway)
DESCRIPCIÓN: Servidor web ligero (Flask) que expone una interfaz HTML5 responsiva
             para permitir la captura remota de imágenes desde dispositivos móviles
             en la misma red local (LAN).
             
INTEGRACIÓN: Actúa como un servicio secundario que alimenta la cola de procesamiento
             de la aplicación principal.
"""

from flask import Flask, request, render_template_string, jsonify
from PIL import Image, ImageDraw, ImageFont
from queue import Queue, Full
import os
import time
import logging
import socket
from pathlib import Path

from Config.Config import Config

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN DE FLASK
# ============================================================================

flask_app = Flask(__name__)

# Límite de tamaño de archivo (16MB)
flask_app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Cola thread-safe para comunicación con la app principal
mobile_capture_queue = Queue(maxsize=10)  

# Dimensiones objetivo para el collage
TARGET_HEIGHT = Config.TARGET_HEIGHT
TARGET_QUALITY = Config.TARGET_QUALITY

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_local_ip():
    """Obtiene la IP local del servidor para mostrar al usuario."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def resize_keep_aspect(image, target_height):
    """Redimensiona imagen manteniendo aspect ratio."""
    aspect_ratio = image.width / image.height
    new_width = int(target_height * aspect_ratio)
    return image.resize((new_width, target_height), Image.Resampling.LANCZOS)

def add_label_to_image(image, label_text):
    """Agrega etiqueta en la esquina superior de la imagen."""
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    
    bbox_height = 40
    draw.rectangle([(0, 0), (img_copy.width, bbox_height)], 
                   fill=(0, 0, 0, 180))
    
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    draw.text((10, 10), label_text, fill=(255, 255, 255), font=font)
    return img_copy

def cleanup_temp_files(directory, pattern="MOB_"):
    """Limpia archivos temporales antiguos (>1 hora)."""
    try:
        now = time.time()
        for file in Path(directory).glob(f"{pattern}*"):
            if now - file.stat().st_mtime > 3600:  
                file.unlink()
                logger.info(f"Limpieza: {file.name} eliminado")
    except Exception as e:
        logger.warning(f"Error en limpieza: {e}")

# ============================================================================
# RUTAS DE FLASK
# ============================================================================

@flask_app.route('/', methods=['GET'])
def mobile_page():
    """Página HTML responsive para captura móvil."""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>🐟 Biometría Móvil</title>
        <style>
            :root {
                --primary: #00b4d8; 
                --bg: #1e1e1e; 
                --paper: #252526;
                --text: #e0e0e0; 
                --border: #3e3e42; 
                --success: #2a9d8f;
                --warning: #f77f00;
                --input-bg: #333333;
            }
            * { box-sizing: border-box; }
            body { 
                margin: 0; background: var(--bg); color: var(--text); 
                font-family: -apple-system, sans-serif; padding-bottom: 30px;
            }
            header { 
                padding: 20px; background: linear-gradient(135deg, var(--primary), #0096c7);
                text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }
            .container { padding: 20px; max-width: 600px; margin: 0 auto; }
            
            .photo-slot { 
                background: var(--paper); border: 2px dashed var(--border); 
                border-radius: 12px; padding: 20px; margin-bottom: 20px; text-align: center;
            }
            .preview { width: 100%; max-height: 200px; object-fit: contain; margin: 15px 0; display: none; border-radius: 8px; }
            .btn-select { background: var(--primary); color: white; padding: 12px; border-radius: 8px; width: 100%; display: inline-block; font-weight: bold; }
            
            /* Estilos del Formulario de Medidas */
            .measurements-card {
                background: var(--paper); border-radius: 12px; padding: 20px;
                margin-bottom: 20px; border: 1px solid var(--border);
            }
            .measurements-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
            .input-group { margin-bottom: 10px; }
            .input-group.full { grid-column: span 2; }
            label { display: block; font-size: 12px; color: var(--primary); margin-bottom: 5px; font-weight: bold; }
            input[type="number"] {
                width: 100%; background: var(--input-bg); border: 1px solid var(--border);
                color: white; padding: 12px; border-radius: 8px; font-size: 16px;
            }

            #btnSend {
                background: linear-gradient(135deg, var(--success), #238276);
                color: white; border: none; padding: 20px; border-radius: 12px; 
                width: 100%; font-size: 18px; font-weight: bold; margin-top: 20px; display: none;
            }
            input[type="file"] { display: none; }
            .status { text-align: center; padding: 15px; border-radius: 8px; margin: 20px 0; display: none; }
        </style>
    </head>
    <body>
        <header>
            <h1>🐟 Captura FishTrace</h1>
            <p>Registro de Biometría</p>
        </header>
        
        <div class="container">
            <div class="photo-slot" id="slot1">
                <label for="input1" class="btn-select">📷 CAPTURAR FOTO LATERAL *</label>
                <img id="prev1" class="preview">
                <input type="file" id="input1" accept="image/*" capture="environment">
            </div>

            <div class="photo-slot" id="slot2">
                <label for="input2" class="btn-select">📷 CAPTURAR FOTO CENITAL</label>
                <img id="prev2" class="preview">
                <input type="file" id="input2" accept="image/*" capture="environment">
            </div>

            <div class="measurements-card">
                <div class="measurements-grid">
                    <div class="input-group full">
                        <label>PESO (gr)</label>
                        <input type="number" id="peso" placeholder="0.00" step="0.01">
                    </div>
                    <div class="input-group">
                        <label>LONGITUD (cm)</label>
                        <input type="number" id="longitud" placeholder="0.0" step="0.1">
                    </div>
                    <div class="input-group">
                        <label>ANCHO (cm)</label>
                        <input type="number" id="ancho" placeholder="0.0" step="0.1">
                    </div>
                    <div class="input-group">
                        <label>ALTO (cm)</label>
                        <input type="number" id="alto" placeholder="0.0" step="0.1">
                    </div>
                </div>
            </div>

            <div id="status" class="status"></div>
            <button id="btnSend">🚀 ENVIAR AL SISTEMA</button>
        </div>

        <script>
            const input1 = document.getElementById('input1');
            const prev1 = document.getElementById('prev1');
            const input2 = document.getElementById('input2');
            const prev2 = document.getElementById('prev2');
            const btnSend = document.getElementById('btnSend');

            function checkShowButton() {
                if (input1.files.length > 0) {
                    btnSend.style.display = 'block';
                }
            }

            input1.onchange = (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (ex) => {
                        prev1.src = ex.target.result;
                        prev1.style.display = 'block';
                        checkShowButton();
                    };
                    reader.readAsDataURL(file);
                }
            };

            input2.onchange = (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (ex) => {
                        prev2.src = ex.target.result;
                        prev2.style.display = 'block';
                        checkShowButton();
                    };
                    reader.readAsDataURL(file);
                }
            };

            btnSend.onclick = async () => {
                btnSend.disabled = true;
                btnSend.innerHTML = '⏳ SUBIENDO...';
                
                const formData = new FormData();
                if (input1.files[0]) formData.append("foto1", input1.files[0]);
                if (input2.files[0]) formData.append("foto2", input2.files[0]);
                
                // Valores numéricos
                formData.append("peso", document.getElementById('peso').value);
                formData.append("longitud", document.getElementById('longitud').value);
                formData.append("ancho", document.getElementById('ancho').value);
                formData.append("alto", document.getElementById('alto').value);

                try {
                    const res = await fetch("/upload", { method: "POST", body: formData });
                    if (res.ok) {
                        alert("✅ Datos enviados con éxito");
                        location.reload();
                    } else {
                        throw new Error("Error en servidor");
                    }
                } catch (e) {
                    alert("❌ Error de conexión");
                    btnSend.disabled = false;
                    btnSend.innerHTML = '🚀 ENVIAR AL SISTEMA';
                }
            };
        </script>
    </body>
    </html>
    """)

@flask_app.route('/upload', methods=['POST'])
def upload_from_mobile():
    """
    Recibe imagen y medidas del móvil, procesa y notifica a la app principal.
    """
    global mobile_capture_queue
    
    try:
        cleanup_temp_files(Config.IMAGES_MANUAL_DIR)
        
        # 1. Capturar las medidas del formulario (Nuevos campos)
        medidas = {
            "peso": request.form.get('peso', ""),
            "longitud": request.form.get('longitud', ""),
            "ancho": request.form.get('ancho', ""),
            "alto": request.form.get('alto', ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        received_images = []
        temp_paths = []

        # 2. Guardar la imagen recibida
        for key in ("foto1", "foto2"):
            if key not in request.files: continue
            file_obj = request.files[key]
            if not file_obj.filename: continue

            timestamp_ms = int(time.time() * 1000)
            temp_filename = f"MOB_{timestamp_ms}_{key}.jpg"
            temp_path = os.path.join(Config.IMAGES_MANUAL_DIR, temp_filename)
            
            file_obj.save(temp_path)
            temp_paths.append(temp_path)
            
            try:
                img = Image.open(temp_path).convert("RGB")
                received_images.append((img, key))
            except Exception as e:
                logger.error(f"Error procesando imagen: {e}")
                continue

        if not received_images:
            return jsonify({"error": "No se recibió imagen"}), 400

        # 3. Procesar imagen (Redimensionar/Etiquetar)
        timestamp = int(time.time())
        result_path = os.path.join(Config.IMAGES_MANUAL_DIR, f"MOBILE_{timestamp}.jpg")

        if len(received_images) == 2:
            # Si llegaron ambas fotos, hacemos un collage lado a lado
            img1_resized = resize_keep_aspect(received_images[0][0], TARGET_HEIGHT)
            img2_resized = resize_keep_aspect(received_images[1][0], TARGET_HEIGHT)
            
            # Crear lienzo para el collage
            total_width = img1_resized.width + img2_resized.width
            collage = Image.new('RGB', (total_width, TARGET_HEIGHT))
            collage.paste(img1_resized, (0, 0))
            collage.paste(img2_resized, (img1_resized.width, 0))
            
            img_labeled = add_label_to_image(collage, "CAPTURA REMOTA (LATERAL + CENITAL)")
            img_labeled.save(result_path, quality=TARGET_QUALITY, optimize=True)
            
        else:
            # Si solo llegó una foto (ej. solo la lateral)
            img, label = received_images[0]
            img_resized = resize_keep_aspect(img, TARGET_HEIGHT)
            
            etiqueta = "LATERAL" if label == "foto1" else "CENITAL"
            img_labeled = add_label_to_image(img_resized, f"CAPTURA REMOTA ({etiqueta})")
            img_labeled.save(result_path, quality=TARGET_QUALITY, optimize=True)

        # 4. ENVIAR PAQUETE A LA MAIN WINDOW
        # Ahora enviamos un diccionario con la ruta Y las medidas
        paquete_datos = {
            "path": result_path,
            "medidas": medidas
        }

        try:
            mobile_capture_queue.put(paquete_datos, block=False)
            logger.info(f"Paquete enviado a la cola: {medidas}")
        except Full:
            logger.warning("Cola llena")

        # Limpieza de temporales
        for tp in temp_paths: os.remove(tp)

        return jsonify({"status": "success", "message": "Datos encolados"}), 200

    except Exception as e:
        logger.error(f"Error en upload: {e}")
        return jsonify({"error": str(e)}), 500


@flask_app.route('/ping', methods=['GET'])
def ping():
    """Endpoint para verificar que el servidor está activo."""
    return jsonify({
        "status": "online",
        "server": "TroutBiometry Mobile Capture",
        "version": "2.0"
    })

@flask_app.errorhandler(413)
def request_entity_too_large(error):
    """Manejo de archivos muy grandes."""
    return jsonify({
        "error": "Archivo muy grande. Máximo 16MB permitido."
    }), 413

# ============================================================================
# INICIALIZACIÓN
# ============================================================================

def start_flask_server(host='0.0.0.0', port=5000, debug=False):
    """
    Inicia el servidor Flask.
    """
    local_ip = get_local_ip()
    
    logger.info("=" * 70)
    logger.info("SERVIDOR DE CAPTURA MOVIL INICIADO")
    logger.info("=" * 70)
    logger.info(f"Accede desde tu movil en:")
    logger.info(f"  🌐 http://{local_ip}:{port}")
    logger.info(f"  🌐 http://localhost:{port} (solo en esta PC)")
    logger.info("=" * 70)
    
    flask_app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True,
        use_reloader=False  
    )

if __name__ == '__main__':
    start_flask_server(
        host='0.0.0.0',
        port=5000,
        debug=Config.DEBUG_MODE
    )