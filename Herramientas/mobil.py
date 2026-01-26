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
    
    # Fondo semitransparente para el texto
    bbox_height = 40
    draw.rectangle([(0, 0), (img_copy.width, bbox_height)], 
                   fill=(0, 0, 0, 180))
    
    # Texto
    try:
        # Intentar cargar fuente del sistema
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
            if now - file.stat().st_mtime > 3600:  # 1 hora
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
            }
            * { box-sizing: border-box; }
            body { 
                margin: 0; 
                background: var(--bg); 
                color: var(--text); 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
                padding-bottom: 30px;
                -webkit-font-smoothing: antialiased;
            }
            header { 
                padding: 20px; 
                background: linear-gradient(135deg, var(--primary), #0096c7);
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }
            header h1 { margin: 0; font-size: 24px; }
            header p { margin: 5px 0 0; font-size: 12px; opacity: 0.9; }
            
            .container { padding: 20px; max-width: 600px; margin: 0 auto; }
            
            .photo-slot { 
                background: var(--paper); 
                border: 2px dashed var(--border); 
                border-radius: 12px; 
                padding: 20px; 
                margin-bottom: 20px; 
                text-align: center;
                transition: all 0.3s ease;
            }
            .photo-slot.has-image { 
                border: 2px solid var(--success); 
                background: rgba(42, 157, 143, 0.1);
            }
            .photo-slot.optional {
                opacity: 0.7;
            }
            
            .label-tag { 
                font-size: 16px; 
                font-weight: bold; 
                color: var(--primary); 
                margin-bottom: 10px;
            }
            .required { color: var(--warning); font-size: 12px; }
            
            .preview { 
                width: 100%; 
                max-height: 250px; 
                object-fit: contain; 
                margin: 15px 0; 
                display: none; 
                border-radius: 8px; 
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            }
            
            .btn-select {
                background: var(--primary); 
                color: white; 
                border: none;
                padding: 16px 24px; 
                border-radius: 8px; 
                width: 100%; 
                font-weight: bold;
                font-size: 16px;
                cursor: pointer; 
                display: inline-block;
                transition: all 0.2s;
                text-transform: uppercase;
            }
            .btn-select:active {
                transform: scale(0.98);
                background: #0096c7;
            }
            
            #btnSend {
                background: linear-gradient(135deg, var(--success), #238276);
                color: white; 
                border: none;
                padding: 20px; 
                border-radius: 12px; 
                width: 100%; 
                font-size: 18px;
                font-weight: bold; 
                cursor: pointer; 
                margin-top: 20px; 
                display: none;
                box-shadow: 0 4px 12px rgba(42, 157, 143, 0.4);
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            #btnSend:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            
            input[type="file"] { display: none; }
            
            .hint { 
                font-size: 12px; 
                color: #888; 
                margin-top: 10px; 
            }
            
            .status {
                text-align: center;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                display: none;
            }
            .status.success {
                background: rgba(42, 157, 143, 0.2);
                border: 1px solid var(--success);
                color: var(--success);
                display: block;
            }
            .status.error {
                background: rgba(247, 127, 0, 0.2);
                border: 1px solid var(--warning);
                color: var(--warning);
                display: block;
            }
            
            .checkmark {
                display: inline-block;
                margin-left: 10px;
                font-size: 20px;
            }
        </style>
    </head>
    <body>
        <header>
            <h1>🐟 Captura Biométrica</h1>
            <p>Sistema de Medición de Truchas</p>
        </header>
        
        <div class="container">
            <!-- Foto Lateral (Obligatoria) -->
            <div class="photo-slot" id="slot1">
                <div class="label-tag">
                    📸 VISTA LATERAL
                    <span class="required">* OBLIGATORIA</span>
                </div>
                <img id="prev1" class="preview" alt="Vista lateral">
                <label for="input1" class="btn-select">
                    📷 Capturar / Seleccionar
                </label>
                <input type="file" id="input1" accept="image/*" capture="environment">
                <div class="hint">Fotografía el pez de costado</div>
            </div>

            <!-- Foto Cenital (Opcional) -->
            <div class="photo-slot optional" id="slot2">
                <div class="label-tag">
                    📸 VISTA CENITAL
                    <span style="color: #888; font-size: 12px;">(Opcional)</span>
                </div>
                <img id="prev2" class="preview" alt="Vista cenital">
                <label for="input2" class="btn-select">
                    📷 Capturar / Seleccionar
                </label>
                <input type="file" id="input2" accept="image/*" capture="environment">
                <div class="hint">Fotografía el pez desde arriba</div>
            </div>

            <div id="status" class="status"></div>
            
            <button id="btnSend">
                🚀 ENVIAR AL SISTEMA
            </button>
        </div>

        <script>
            const inputs = [
                document.getElementById('input1'), 
                document.getElementById('input2')
            ];
            const previews = [
                document.getElementById('prev1'), 
                document.getElementById('prev2')
            ];
            const slots = [
                document.getElementById('slot1'), 
                document.getElementById('slot2')
            ];
            const btnSend = document.getElementById('btnSend');
            const statusDiv = document.getElementById('status');

            // Manejo de selección de imágenes
            inputs.forEach((input, index) => {
                input.onchange = (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        // Validar tamaño (16MB)
                        if (file.size > 16 * 1024 * 1024) {
                            alert('⚠️ Imagen muy grande. Máximo 16MB permitido.');
                            return;
                        }

                        const reader = new FileReader();
                        reader.onload = (ex) => {
                            previews[index].src = ex.target.result;
                            previews[index].style.display = 'block';
                            slots[index].classList.add('has-image');
                            checkReady();
                        };
                        reader.readAsDataURL(file);
                    }
                };
            });

            function checkReady() {
                // Mostrar botón solo si hay al menos la foto lateral
                if (inputs[0].files[0]) {
                    btnSend.style.display = 'block';
                }
            }

            btnSend.onclick = async () => {
                btnSend.disabled = true;
                btnSend.innerHTML = '⏳ SUBIENDO...';
                statusDiv.className = 'status';
                statusDiv.style.display = 'none';
                
                const formData = new FormData();
                if (inputs[0].files[0]) formData.append("foto1", inputs[0].files[0]);
                if (inputs[1].files[0]) formData.append("foto2", inputs[1].files[0]);

                try {
                    const res = await fetch("/upload", { 
                        method: "POST", 
                        body: formData 
                    });
                    
                    if (res.ok) {
                        statusDiv.className = 'status success';
                        statusDiv.innerHTML = `
                            <strong>✅ ¡Éxito!</strong><br>
                            Imágenes recibidas correctamente.<br>
                            <small>Completa el registro en la PC.</small>
                        `;
                        
                        // Limpiar formulario
                        setTimeout(() => {
                            location.reload();
                        }, 3000);
                    } else {
                        throw new Error('Error del servidor');
                    }
                } catch (e) {
                    statusDiv.className = 'status error';
                    statusDiv.innerHTML = `
                        <strong>❌ Error</strong><br>
                        No se pudo conectar al servidor.<br>
                        <small>Verifica la conexión WiFi.</small>
                    `;
                    
                    btnSend.disabled = false;
                    btnSend.innerHTML = '🔄 REINTENTAR';
                }
            };
        </script>
    </body>
    </html>
    """)

@flask_app.route('/upload', methods=['POST'])
def upload_from_mobile():
    """
    Recibe imágenes del móvil, crea collage y notifica a la app.
    
    Returns:
        HTML de confirmación o error 400
    """
    global mobile_capture_queue
    
    try:
        # Limpiar archivos antiguos antes de procesar
        cleanup_temp_files(Config.IMAGES_MANUAL_DIR)
        
        received_images = []
        temp_paths = []

        # 1. Guardar archivos temporales
        for key in ("foto1", "foto2"):
            if key not in request.files:
                continue
                
            file_obj = request.files[key]
            if not file_obj.filename:
                continue

            # Crear nombre único
            timestamp = int(time.time() * 1000)  
            temp_filename = f"MOB_{timestamp}_{key}.jpg"
            temp_path = os.path.join(Config.IMAGES_MANUAL_DIR, temp_filename)
            
            # Guardar archivo
            file_obj.save(temp_path)
            temp_paths.append(temp_path)
            
            # Abrir y validar imagen
            try:
                img = Image.open(temp_path).convert("RGB")
                received_images.append((img, key))
                logger.info(f"Imagen recibida: {key} ({img.size})")
            except Exception as e:
                logger.error(f"Error al procesar {key}: {e}")
                # Limpiar archivo corrupto
                os.remove(temp_path)
                continue

        if not received_images:
            return jsonify({"error": "No se recibieron imágenes válidas"}), 400

        # 2. Crear collage o guardar imagen única
        timestamp = int(time.time())
        result_path = os.path.join(
            Config.IMAGES_MANUAL_DIR,
            f"MOBILE_{timestamp}.jpg"
        )

        if len(received_images) == 2:
            # --- COLLAGE DUAL ---
            img1, label1 = received_images[0]
            img2, label2 = received_images[1]
            
            # Redimensionar manteniendo aspecto
            img1_resized = resize_keep_aspect(img1, TARGET_HEIGHT)
            img2_resized = resize_keep_aspect(img2, TARGET_HEIGHT)
            
            # Agregar etiquetas
            img1_labeled = add_label_to_image(img1_resized, "LATERAL")
            img2_labeled = add_label_to_image(img2_resized, "CENITAL")
            
            # Crear collage horizontal
            total_width = img1_labeled.width + img2_labeled.width
            collage = Image.new("RGB", (total_width, TARGET_HEIGHT), (30, 30, 30))
            collage.paste(img1_labeled, (0, 0))
            collage.paste(img2_labeled, (img1_labeled.width, 0))
            
            collage.save(result_path, quality=TARGET_QUALITY, optimize=True)
            logger.info(f"Collage creado: {result_path}")
            
        elif len(received_images) == 1:
            # --- IMAGEN ÚNICA ---
            img, label = received_images[0]
            img_resized = resize_keep_aspect(img, TARGET_HEIGHT)
            img_labeled = add_label_to_image(img_resized, "LATERAL")
            img_labeled.save(result_path, quality=TARGET_QUALITY, optimize=True)
            logger.info(f"Imagen unica guardada: {result_path}")

        # 3. Notificar a la aplicación principal
        try:
            mobile_capture_queue.put(result_path, block=False)
            logger.info(f"Imagen encolada para procesamiento: {result_path}")
        except Full:
            logger.warning("Cola de captura movil llena. Imagen guardada pero no encolada.")

        # 4. Limpiar archivos temporales
        for temp_path in temp_paths:
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"No se pudo eliminar {temp_path}: {e}")

        return """
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: -apple-system, sans-serif;
                    background: #1e1e1e;
                    color: #e0e0e0;
                    text-align: center;
                    padding: 50px 20px;
                }
                h1 { color: #2a9d8f; }
                p { line-height: 1.6; }
                .emoji { font-size: 64px; margin: 20px; }
            </style>
        </head>
        <body>
            <div class="emoji">✅</div>
            <h1>¡Imágenes Recibidas!</h1>
            <p>Las fotografías se procesaron correctamente.</p>
            <p><strong>Continúa en la computadora</strong> para completar el registro biométrico.</p>
        </body>
        </html>
        """

    except Exception as e:
        logger.error(f"Error en upload_from_mobile: {e}", exc_info=True)
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
    
    Args:
        host: IP del servidor (0.0.0.0 = todas las interfaces)
        port: Puerto del servidor
        debug: Modo debug de Flask
    """
    local_ip = get_local_ip()
    
    logger.info("=" * 70)
    logger.info("SERVIDOR DE CAPTURA MOVIL INICIADO")
    logger.info("=" * 70)
    logger.info(f"Accede desde tu movil en:")
    logger.info(f"  🌐 http://{local_ip}:{port}")
    logger.info(f"  🌐 http://localhost:{port} (solo en esta PC)")
    logger.info("=" * 70)
    
    # Imprimir en consola también
    print("\n" + "=" * 70)
    print("🐟 SERVIDOR DE CAPTURA MÓVIL INICIADO")
    print("=" * 70)
    print(f"\n📱 Accede desde tu móvil en:")
    print(f"   http://{local_ip}:{port}\n")
    print("💡 Asegúrate de que el móvil esté en la misma red WiFi")
    print("=" * 70 + "\n")
    
    flask_app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True,
        use_reloader=False  
    )

if __name__ == '__main__':
    # Iniciar servidor
    start_flask_server(
        host='0.0.0.0',
        port=5000,
        debug=Config.DEBUG_MODE
    )