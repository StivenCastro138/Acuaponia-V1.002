# 📖 FishTracer V1.0 — Wiki Técnica

## Tabla de Contenidos

1. [Visión General](#1-visión-general)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Módulos Principales](#3-módulos-principales)
4. [Flujo de Datos (Pipeline)](#4-flujo-de-datos-pipeline)
5. [Funciones Clave](#5-funciones-clave)
6. [Dependencias y Tecnologías](#6-dependencias-y-tecnologías)
7. [Índice de Archivos](#7-índice-de-archivos)
8. [Modelo de Datos](#8-modelo-de-datos)
9. [Configuración y Calibración](#9-configuración-y-calibración)

---

## 1. Visión General

**FishTracer** es un sistema de visión por computadora diseñado para la medición biométrica no invasiva de truchas arcoíris (*Oncorhynchus mykiss*) en entornos de acuicultura. Desarrollado en el **Laboratorio LESTOMA** de la Universidad de Cundinamarca, Colombia.

### Problema que Resuelve
- Eliminación de la manipulación manual de peces (que causa 1-2% de mortalidad)
- Automatización de mediciones biométricas (longitud, alto, ancho, peso)
- Trazabilidad completa del crecimiento con base de datos relacional

### Capacidades Principales
| Capacidad | Tecnología |
|-----------|-----------|
| Detección semántica del pez | Fishdream (VLM) |
| Segmentación de contorno | Pipeline HSV + GrabCut |
| Medición de longitud curva | Esqueletización + B-Spline |
| Estimación de peso/volumen | Modelo alométrico 3D |
| Captura dual sincronizada | 2 cámaras (lateral + cenital) en threads |
| Validación QA/QC | Motor de reglas biológicas |
| Persistencia | SQLite + exportación CSV |
| Acceso remoto | API Flask + Ngrok |
| Monitoreo ambiental | IoT Sensors (WOC API) |

---

## 2. Arquitectura del Sistema

### 2.1 Organización por Capas

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CAPA 1: PRESENTACIÓN (GUI - Qt)                   │
│  MainWindow · CaptureDecisionDialog · EditMeasurementDialog         │
│  StatusBar · SensorBar · ImageViewerDialog                          │
├─────────────────────────────────────────────────────────────────────┤
│                CAPA 2: ORQUESTACIÓN (Worker Threads)                │
│  FrameProcessor (QThread) · OptimizedCamera (threading)             │
│  SimpleMotionDetector · FishTracker                                 │
├─────────────────────────────────────────────────────────────────────┤
│             CAPA 3: PROCESAMIENTO IA & MEDICIÓN                     │
│  AdvancedDetector · SegmentationRefiner · SpineMeasurer             │
│  BiometryService · MorphometricAnalyzer · FishAnatomyValidator      │
│  MeasurementValidator · FishDetector                                │
├─────────────────────────────────────────────────────────────────────┤
│              CAPA 4: DATOS Y SERVICIOS EXTERNOS                     │
│  DatabaseManager (SQLite) · ApiService (Flask) · SensorService      │
│  Mobile Gateway (mobil.py) · Config                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Patrón de Concurrencia

```
[Main Thread - Qt Event Loop]
       │
       ├──► OptimizedCamera (Thread A) ──► Cámara Lateral (1920×1080)
       │
       ├──► OptimizedCamera (Thread B) ──► Cámara Cenital (1920×1080)
       │
       ├──► FrameProcessor (QThread) ──► Pipeline de IA
       │         │
       │         └──► BiometryService → AdvancedDetector → Segmentation → Spine
       │
       ├──► ApiService (Thread) ──► Flask Server (port 5001)
       │         │
       │         └──► Ngrok Tunnel (público)
       │
       └──► SensorService (Thread) ──► Polling IoT cada 1s
```

---

## 3. Módulos Principales

### 3.1 Capa de Presentación

#### `MainWindow.py` (10,381 líneas)
**Rol:** Controlador maestro de la GUI. Integra video en tiempo real, panel de control, dashboard de telemetría y gestión del ciclo de vida del sistema.

**Responsabilidades:**
- Visualización de video dual (lateral + cenital)
- Control de captura (manual / automática)
- Dashboard de crecimiento con gráficas matplotlib
- Configuración de HSV y escalas
- Exportación PDF / CSV
- Integración con sensores IoT
- Generación de QR para acceso móvil

#### `CaptureDecisionDialog.py`
**Rol:** Diálogo modal "Human-in-the-loop". Permite al operario elegir entre:
- `RESULT_DISCARD (0)` — Descartar captura
- `RESULT_IA (1)` — Procesar con IA (automático)
- `RESULT_MANUAL (2)` — Ingreso manual de medidas

#### `EditMeasurementDialog.py`
**Rol:** Formulario de auditoría y corrección de datos históricos con validación en tiempo real contra modelos alométricos.

#### `StatusBar.py`
**Rol:** Widget de telemetría en tiempo real: CPU, RAM, GPU, VRAM, FPS, latencia IA, estado API.

#### `SensorBar.py`
**Rol:** Barra superior con visualización de variables ambientales (temperatura, pH, oxígeno disuelto, turbidez).

---

### 3.2 Capa de Orquestación

#### `FrameProcessor.py` (QThread)
**Rol:** Worker thread dedicado al procesamiento intensivo. Desacopla la lógica de visión artificial del hilo de GUI.

**Pipeline interno:**
1. Verifica estabilidad de escena (`SimpleMotionDetector`)
2. Invoca `BiometryService.analyze_and_annotate()`
3. Valida resultados (longitud > 0)
4. Actualiza tracker temporal (`FishTracker`)
5. Calcula confianza y empaqueta resultado
6. Emite señal `result_ready` hacia GUI

#### `OptimizedCamera.py`
**Rol:** Driver asíncrono de cámara. Patrón "Threaded Video Capture" para captura sin bloqueo.

**Características:**
- Thread daemon para I/O de cámara
- Buffer de tamaño 1 (siempre frame más reciente)
- Soporte MSMF/DShow (Windows)
- Resolución 1920×1080 @ 60 FPS

#### `SimpleMotionDetector.py`
**Rol:** Trigger de estabilidad. Solo permite análisis biométrico cuando la escena está estática (pez quieto).

**Implementación:**
- Pipeline CPU o CUDA (detección automática)
- Diferencia absoluta entre frames consecutivos
- Historial de N frames para confirmar estabilidad
- Umbral configurable (default: 8.0)

#### `FishTracker.py`
**Rol:** Suavizado temporal. Reduce jitter en mediciones usando promedio ponderado exponencial.

---

### 3.3 Capa de IA y Medición

#### `AdvancedDetector.py`
**Rol:** Orquestador central de IA. Implementa patrón "Chain of Responsibility":

```
Cadena de Detección:
  1. Fishdream API (remoto, alta precisión) ──► si falla ──►
  2. Classic HSV Fallback (local, sin dependencia de red)
```

**Pipeline de Precisión (`analyze_frame`):**
1. Detección del pez (Fishdream o HSV)
2. Mejora de imagen (CLAHE)
3. Segmentación de cuerpo (SegmentationRefiner)
4. Refinamiento de bordes (GrabCut)
5. Bloqueo estricto de caja (evitar fuga de máscara)
6. Extracción de contorno
7. Medición de columna vertebral (SpineMeasurer)

#### `SegmentationRefiner.py`
**Rol:** Convierte bounding boxes en máscaras binarias de alta precisión usando modelos de segmentación.

**Proceso:**
1. Predicción de máscara con modelo de segmentación
2. Filtrado de componentes (mayor blob)
3. Limpieza de aletas (apertura morfológica proporcional)
4. Validación de área (no reducir más del 20%)

#### `SpineMeasurer.py`
**Rol:** Motor de geometría computacional para medir longitud real de organismos curvados.

**Algoritmo:**
1. Limpieza morfológica de máscara
2. Esqueletización (Zhang-Suen thinning)
3. Conversión de esqueleto a grafo (NetworkX)
4. Búsqueda del diámetro del grafo (camino más largo)
5. Ajuste B-Spline cúbica para precisión sub-píxel
6. Medición sobre curva (longitud de arco)

#### `BiometryService.py`
**Rol:** Fachada que orquesta el flujo completo de medición:
1. Detección y segmentación (ambas vistas)
2. Fotogrametría (cálculo de escalas dinámicas px→cm)
3. Estimación biométrica (contornos o cajas)
4. Fusión de longitud (esqueleto + vistas)
5. Validación QA/QC
6. Anotación visual

#### `MorphometricAnalyzer.py`
**Rol:** Motor de cálculo científico. Transforma geometría cruda en variables biológicas:
- Longitud fusionada (lateral + cenital + spine)
- Alto y ancho con corrección de escorzo 3D
- Peso estimado (modelo alométrico: W = K × L^b)
- Volumen (aproximación elipsoidal)
- Factor de condición K de Fulton
- Área lateral y cenital

#### `MeasurementValidator.py`
**Rol:** Motor de reglas de negocio QA/QC:
- Validación de rangos físicos (4-50 cm)
- Factor K aceptable (0.80 - 2.20)
- Consistencia peso vs longitud (desviación < 45%)
- Geometría morfológica (relación de aspecto)
- Calidad de silueta (ocupación)
- Coherencia estéreo (lateral vs cenital < 25% discrepancia)

#### `FishDetector.py`
**Rol:** Segmentación en tiempo real por color (Chroma Key) con soporte CPU/CUDA.

#### `FishAnatomyValidator.py`
**Rol:** Valida que el objeto detectado sea realmente un pez mediante:
- Relación de aspecto (2.5 - 7.0)
- Solidez (0.75 - 0.97)
- Simetría bilateral (≥ 0.70)
- Rectitud del contorno

---

### 3.4 Capa de Datos y Servicios

#### `DatabaseManager.py`
**Rol:** CRUD completo sobre SQLite con:
- Tabla `measurements`: 29 columnas (biometría + ambiente + metadata)
- Tabla `calibrations`: Histórico de calibraciones
- Tabla `species_profiles`: Perfiles biológicos por especie
- Migraciones automáticas de esquema
- Índices de rendimiento

#### `ApiService.py`
**Rol:** Servidor Flask con endpoints REST:
- `GET /api/health` — Estado del sistema
- `GET /api/last_report` — Último reporte por tanda
- Polling de sensores cada 1 segundo
- Tunnel Ngrok para acceso público
- Cache con TTL configurable

#### `SensorService.py`
**Rol:** Cliente HTTP para IoT. Consume API de calidad del agua (WOC):
- Turbidez, pH, oxígeno disuelto
- Temperatura del agua y ambiente
- Conductividad, humedad

#### `mobil.py`
**Rol:** Gateway de captura móvil. Servidor Flask con UI HTML5 responsiva para captura remota desde celulares en LAN.

---

## 4. Flujo de Datos (Pipeline)

### 4.1 Flujo Automático (Sin intervención humana)

```
[Cámaras]───┐
  Lateral    │──► OptimizedCamera (threads)
  Cenital    │         │
             │         ▼
             │    QTimer (GUI) lee frames
             │         │
             │         ▼
             │    ¿Escena estable? ──No──► Esperar...
             │         │Yes
             │         ▼
             │    FrameProcessor.add_frame()
             │         │
             │         ▼
             │    BiometryService.analyze_and_annotate()
             │         │
             │         ├──► AdvancedDetector.analyze_frame(img_lat)
             │         │         │
             │         │         ├──► Fishdream API (detect)
             │         │         │    ¿Disponible? ──No──► HSV Fallback
             │         │         │         │Yes
             │         │         │         ▼
             │         │         │    Bounding Box
             │         │         │         │
             │         │         ├──► SegmentationRefiner.get_body_mask()
             │         │         ├──► GrabCut Refinement
             │         │         └──► SpineMeasurer.get_spine_info()
             │         │
             │         ├──► AdvancedDetector.analyze_frame(img_top)
             │         │
             │         ├──► MorphometricAnalyzer (cálculos biométricos)
             │         │
             │         ├──► Fusión de longitud (Spine + Vistas)
             │         │
             │         └──► MeasurementValidator (QA/QC)
             │                   │
             │                   ▼
             │              ¿Medición válida? ──No──► Descartar
             │                   │Yes
             │                   ▼
             │              FishTracker.update() (suavizado temporal)
             │                   │
             │                   ▼
             │              ¿Estable (N frames)? ──No──► Continuar acumulando
             │                   │Yes
             │                   ▼
             │              AUTO_CAPTURE_SAVE_DELAY (17s)
             │                   │
             │                   ▼
             │              DatabaseManager.save()
             │              + Guardar imagen collage
```

### 4.2 Flujo Semiautomático (Human-in-the-loop)

```
[Usuario presiona "Capturar"]
       │
       ▼
  CaptureDecisionDialog
       │
       ├──► [Descartar] ──► Volver a video en vivo
       │
       ├──► [Medición Manual] ──► Formulario manual ──► DB
       │
       └──► [Procesar con IA] ──► Pipeline completo (igual que automático)
                    │
                    ▼
              Resultado mostrado al usuario
                    │
                    ▼
              ¿Usuario acepta? ──No──► EditMeasurementDialog
                    │Yes                      │
                    ▼                         ▼
              DatabaseManager.save()    Corrección manual ──► DB
```

---

## 5. Funciones Clave

### Entry Point
| Función | Archivo | Descripción |
|---------|---------|-------------|
| `main()` | `app.py` | Inicializa sistema, crea directorios, lanza API y GUI |

### Pipeline de Medición
| Función | Archivo | Descripción |
|---------|---------|-------------|
| `FrameProcessor.run()` | `FrameProcessor.py` | Loop principal del worker thread |
| `FrameProcessor.process_frames()` | `FrameProcessor.py` | Orquestador de un ciclo de análisis |
| `BiometryService.analyze_and_annotate()` | `BiometryService.py` | Flujo maestro: detección → medición → validación |
| `AdvancedDetector.analyze_frame()` | `AdvancedDetector.py` | Pipeline de precisión total (7 pasos) |
| `AdvancedDetector.detect_fish()` | `AdvancedDetector.py` | Chain of Responsibility para detección |
| `SegmentationRefiner.get_body_mask()` | `SegmentationRefiner.py` | Segmentación + limpieza de aletas |
| `SpineMeasurer.get_spine_info()` | `SpineMeasurer.py` | Esqueletización + grafo + B-Spline |
| `MorphometricAnalyzer.compute_advanced_metrics()` | `MorphometricAnalyzer.py` | Cálculo biométrico de alta precisión |

### Fotogrametría
| Función | Archivo | Descripción |
|---------|---------|-------------|
| `Config.calcular_escala_proporcional()` | `Config.py` | Escala cm/px con corrección óptica (aire-acrílico-agua) |

### Validación
| Función | Archivo | Descripción |
|---------|---------|-------------|
| `MeasurementValidator.validate_measurement()` | `MeasurementValidator.py` | Auditoría QA/QC de datos biométricos |
| `FishAnatomyValidator.validate_is_fish()` | `FishAnatomyValidator.py` | Validación morfológica del objeto |
| `SimpleMotionDetector.is_stable()` | `SimpleMotionDetector.py` | Trigger de estabilidad de escena |

### Persistencia
| Función | Archivo | Descripción |
|---------|---------|-------------|
| `DatabaseManager.init_database()` | `DatabaseManager.py` | Creación de esquema y migraciones |
| `DatabaseManager.save_measurement()` | `DatabaseManager.py` | Inserción de registro biométrico |

### Servicios Externos
| Función | Archivo | Descripción |
|---------|---------|-------------|
| `ApiService.start()` | `ApiService.py` | Lanza Flask + Ngrok en threads |
| `SensorService.get_water_quality_data()` | `SensorService.py` | Adquisición de telemetría IoT |

---

## 6. Dependencias y Tecnologías

### Core
| Paquete | Versión | Uso |
|---------|---------|-----|
| Python | 3.11+ | Lenguaje principal |
| PySide6 | ≥6.6 | GUI (Qt6) |
| OpenCV | ≥4.8 | Visión por computadora |
| NumPy | ≥1.26 | Cálculos numéricos |
| PyTorch | ≥2.1 | Infraestructura de IA |

### IA / Deep Learning
| Paquete | Versión | Uso |
|---------|---------|-----|
| moondream | 0.2.0 | VLM para detección semántica (Fishdream) |
| ultralytics | ≥8.0 | SAM/MobileSAM para segmentación |

### Científico
| Paquete | Uso |
|---------|-----|
| scipy | B-Spline interpolation, curve fitting |
| networkx | Análisis de grafos (esqueleto) |
| matplotlib | Gráficas de crecimiento |

### Web / Comunicación
| Paquete | Uso |
|---------|-----|
| Flask | API REST local |
| flask-cors | CORS para API |
| pyngrok | Tunnel público |
| qrcode | Generación QR para móvil |

### Sistema
| Paquete | Uso |
|---------|-----|
| psutil | Monitoreo CPU/RAM |
| nvidia-ml-py | Monitoreo GPU/VRAM |
| reportlab | Generación de PDFs |
| qdarktheme | Tema oscuro para Qt |

---

## 7. Índice de Archivos

```
FishTracer_V1.0/
├── app.py                          # Entry point
├── requirements.txt                # Dependencias Python
├── build_exe.bat                   # Script de compilación Windows
├── logo.ico                        # Icono de la aplicación
├── save_ok.wav                     # Sonido de confirmación
├── LICENSE                         # MIT License
│
├── Config/
│   ├── __init__.py
│   └── Config.py                   # Configuración centralizada (328 líneas)
│
├── Modulos/
│   ├── __init__.py
│   ├── MainWindow.py               # GUI principal (10,381 líneas)
│   ├── FrameProcessor.py           # Worker thread de procesamiento (381 líneas)
│   ├── AdvancedDetector.py         # Orquestador de IA (355 líneas)
│   ├── BiometryService.py          # Servicio de biometría (275 líneas)
│   ├── SegmentationRefiner.py      # Refinador con modelo de segmentación (148 líneas)
│   ├── SpineMeasurer.py            # Medidor de columna vertebral (176 líneas)
│   ├── MorphometricAnalyzer.py     # Cálculos científicos (337 líneas)
│   ├── MeasurementValidator.py     # Validación QA/QC (105 líneas)
│   ├── FishDetector.py             # Detector HSV CPU/GPU (237 líneas)
│   ├── FishTracker.py              # Suavizado temporal (137 líneas)
│   ├── FishAnatomyValidator.py     # Validador anatómico (148 líneas)
│   ├── SimpleMotionDetector.py     # Detector de estabilidad (193 líneas)
│   ├── OptimizedCamera.py          # Driver de cámara async (71 líneas)
│   ├── CaptureDecisionDialog.py    # Diálogo de decisión (183 líneas)
│   ├── EditMeasurementDialog.py    # Editor de registros (506 líneas)
│   ├── ImageViewerDialog.py        # Visor de imágenes
│   ├── StatusBar.py                # Barra de telemetría (337 líneas)
│   ├── SensorBar.py                # Barra de sensores
│   └── ApiService.py               # API Flask + Ngrok (496 líneas)
│
├── BasedeDatos/
│   ├── __init__.py
│   └── DatabaseManager.py          # Gestión SQLite (922 líneas)
│
├── Herramientas/
│   ├── SensorService.py            # Cliente IoT (77 líneas)
│   └── mobil.py                    # Gateway móvil Flask (1,190 líneas)
│
└── docs/
    ├── WIKI.md                     # Este documento
    └── ARCHITECTURE.md             # Diagrama de arquitectura
```

---

## 8. Modelo de Datos

### Tabla `measurements` (Principal)
| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | INTEGER PK | Auto-incremento |
| timestamp | TEXT | Fecha/hora ISO |
| fish_id | TEXT | Identificador del pez |
| length_cm | REAL | Longitud automática (cm) |
| height_cm | REAL | Alto automático (cm) |
| width_cm | REAL | Ancho automático (cm) |
| weight_g | REAL | Peso estimado (g) |
| manual_length_cm | REAL | Longitud manual (cm) |
| manual_height_cm | REAL | Alto manual (cm) |
| manual_width_cm | REAL | Ancho manual (cm) |
| manual_weight_g | REAL | Peso manual (g) |
| lat_area_cm2 | REAL | Área lateral (cm²) |
| top_area_cm2 | REAL | Área cenital (cm²) |
| volume_cm3 | REAL | Volumen estimado (cm³) |
| confidence_score | REAL | Score de confianza (0-1) |
| notes | TEXT | Observaciones |
| image_path | TEXT | Ruta del collage guardado |
| measurement_type | TEXT | 'auto' / 'manual' / 'ia' |
| validation_errors | TEXT | Warnings de QA/QC |
| api_air_temp_c | REAL | Temperatura ambiente (°C) |
| api_water_temp_c | REAL | Temperatura agua (°C) |
| api_rel_humidity | REAL | Humedad relativa (%) |
| api_abs_humidity_g_m3 | REAL | Humedad absoluta (g/m³) |
| api_ph | REAL | pH del agua |
| api_cond_us_cm | REAL | Conductividad (µS/cm) |
| api_do_mg_l | REAL | Oxígeno disuelto (mg/L) |
| api_turbidity_ntu | REAL | Turbidez (NTU) |
| batch_id | TEXT | ID de tanda/lote |

### Tabla `calibrations`
Historial de calibraciones con escalas (cm/px) y rangos HSV para ambas cámaras.

### Tabla `species_profiles`
Perfiles biológicos por especie con constantes alométricas (K, exponente, factor de forma).

---

## 9. Configuración y Calibración

### Escalas de Fotogrametría
El sistema implementa interpolación lineal entre dos escalas por cámara para corregir la distorsión por profundidad (Ley de Snell en 3 medios: aire → acrílico → agua):

| Parámetro | Valor Default | Descripción |
|-----------|---------------|-------------|
| SCALE_LAT_FRONT | 0.00635786 cm/px | Lateral zona cercana (7cm) |
| SCALE_LAT_BACK | 0.01827964 cm/px | Lateral zona lejana (22cm) |
| SCALE_TOP_FRONT | 0.004429 cm/px | Cenital zona cercana |
| SCALE_TOP_BACK | 0.013108 cm/px | Cenital zona lejana |

### Modelo Biológico
| Parámetro | Valor | Uso |
|-----------|-------|-----|
| TROUT_DENSITY | 1.04 g/cm³ | Densidad del tejido |
| FORM_FACTOR | 1.07 | Ajuste volumétrico |
| WEIGHT_K | 0.2 | Constante alométrica |
| WEIGHT_EXP | 1.88 | Exponente W = K×L^b |
| BENDING_THRESHOLD | 1.4 | Umbral de curvatura |

### Correcciones Empíricas de Salida
| Factor | Valor | Descripción |
|--------|-------|-------------|
| LENGTH_CORRECTION | 0.951 | Anti-sesgo longitud |
| HEIGHT_CORRECTION | 0.967 | Anti-sesgo alto |
| WIDTH_CORRECTION | 0.707 | Anti-sesgo ancho |
| WEIGHT_CORRECTION | 0.936 | Anti-sesgo peso |

---

*Documentación generada automáticamente a partir del análisis estático del código fuente de FishTracer V1.0.*
