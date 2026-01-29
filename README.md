# 🐟 Sistema de Trazabilidad de Crecimiento de Trucha Arcoíris mediante Visión por Computadora

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/Status-En%20Desarrollo-orange.svg)

**Sistema no invasivo de monitoreo biométrico para acuicultura sostenible**

[Características](#-características-principales) •
[Instalación](#-instalación-rápida) •
[Uso](#-guía-de-uso) •
[Documentación](#-documentación) •
[Investigación](#-publicación-científica)

</div>

---

## 📋 Tabla de Contenidos

- [Descripción General](#-descripción-general)
- [Características Principales](#-características-principales)
- [Tecnologías Utilizadas](#-tecnologías-utilizadas)
- [Requisitos del Sistema](#-requisitos-del-sistema)
- [Instalación Rápida](#-instalación-rápida)
- [Configuración Inicial](#-configuración-inicial)
- [Guía de Uso](#-guía-de-uso)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Ventajas del Sistema](#-ventajas-del-sistema)
- [Publicación Científica](#-publicación-científica)
- [Equipo de Desarrollo](#-equipo-de-desarrollo)
- [Contribuciones](#-contribuciones)
- [Licencia](#-licencia)
- [Contacto](#-contacto)

---

## 🎯 Descripción General

Este proyecto es el resultado de una investigación académica desarrollada en el **Laboratorio Experimental de Sistemas Tecnológicos Orientados a Modelos Acuapónicos (LESTOMA)** de la **Universidad de Cundinamarca**, extensión Facatativá, Colombia.

El sistema implementa técnicas avanzadas de **visión por computadora** e **inteligencia artificial** para realizar el monitoreo no invasivo del crecimiento de truchas arcoíris (*Oncorhynchus mykiss*), eliminando la necesidad de manipulación manual que genera estrés y mortalidad en los peces.

### 🔬 Problema que Resuelve

En la acuicultura tradicional, el proceso de medición manual presenta varios desafíos:

- ⚠️ **Mortalidad del 1-2%** de las muestras debido al estrés por manipulación
- 💰 **Altos costos operativos** (50-60% del presupuesto es alimento)
- ⏱️ **Proceso lento y laborioso** que requiere personal especializado
- 📉 **Datos inconsistentes** por variabilidad en mediciones manuales
- 😰 **Estrés en los peces** que afecta su desarrollo y bienestar

### 💡 Solución Propuesta

Sistema automatizado que:

- 📸 Captura imágenes simultáneas desde dos cámaras (cenital y lateral)
- 🤖 Procesa automáticamente mediante algoritmos de Machine Learning
- 📏 Calcula dimensiones biométricas (largo, alto, ancho, peso)
- 💾 Almacena datos para trazabilidad histórica
- 🍽️ Ajusta automáticamente la dosificación de alimento

---

## ✨ Características Principales

### 🎥 Sistema de Captura Dual
- **Cámara Cenital**: Vista superior para medir longitud y ancho
- **Cámara Lateral**: Vista lateral para medir longitud y alto
- Captura sincronizada en tiempo real
- Resolución Full HD (1080p)

### 🧠 Inteligencia Artificial
- **Detección automática** del pez mediante modelo Moondream
- **Segmentación precisa** del contorno mediante técnicas de visión por computadora
- **Corrección de distorsión óptica** por refracción del agua y vidrio
- **Precisión del 93%** en medición longitudinal

### 📊 Análisis Biométrico
- Cálculo automático de:
  - ✅ Longitud (cm)
  - ✅ Alto (cm)
  - ✅ Ancho/Espesor (cm)
  - ✅ Peso estimado (g)
  - ✅ Factor de condición K

### 💾 Trazabilidad Completa
- Almacenamiento de historial de crecimiento
- Asignación de ID único por medición
- Registro de fecha y hora
- Base de datos relacional
- Exportación de datos para análisis

### 🔧 Interfaz Amigable
- Visualización en tiempo real de ambas cámaras
- Modo manual y automático de captura
- Resultados instantáneos
- Panel de control intuitivo

---

## 🛠️ Tecnologías Utilizadas

### Lenguajes y Frameworks
- **Python 3.8+** - Lenguaje principal
- **OpenCV** - Procesamiento de imágenes
- **NumPy** - Cálculos numéricos
- **Tkinter** - Interfaz gráfica

### Inteligencia Artificial
- **Moondream** - Detección de región de interés (ROI)
- **YOLOv8** - Segmentación avanzada
- **Algoritmos personalizados** - Corrección óptica y calibración

### Base de Datos
- **SQLite** - Almacenamiento local de datos
- **JSON** - Intercambio de datos entre módulos

### Hardware Recomendado
- **Cámaras**: 
  - Logitech C930e (1080p Full HD)
  - Kisonli HD-1081 (1080p Full HD)
- **Procesador**: AMD Ryzen 7 5800XT o superior (8 núcleos, 4.8 GHz)
- **GPU**: NVIDIA GeForce RTX 4060 o superior
- **RAM**: 24 GB mínimo
- **Sistema Operativo**: Windows 11 (recomendado)

---

## 💻 Requisitos del Sistema

### Requisitos Mínimos
- **OS**: Windows 10/11 (64-bit)
- **Procesador**: Intel i5 o AMD Ryzen 5 (4 núcleos)
- **RAM**: 8 GB
- **GPU**: NVIDIA GTX 1050 o superior (con soporte CUDA)
- **Almacenamiento**: 5 GB libres
- **Python**: 3.8 o superior

### Requisitos Recomendados
- **OS**: Windows 11 (64-bit)
- **Procesador**: AMD Ryzen 7 o Intel i7 (8+ núcleos)
- **RAM**: 16-24 GB
- **GPU**: NVIDIA RTX 3060 o superior
- **Almacenamiento**: 10 GB libres (SSD recomendado)
- **Cámaras**: 2x Full HD 1080p (USB 3.0)

---

## 🚀 Instalación Rápida

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/stivencastro138/acuaponia-v1.002.git
cd acuaponia-v1.002
```

### Paso 2: Configurar API de Moondream

1. Obtén tu clave API gratuita de Moondream en: [https://moondream.ai/](https://moondream.ai/)
2. Crea un archivo `.env` en la raíz del proyecto:

```bash
# Crear archivo .env
notepad .env
```

3. Agrega tu clave API:

```env
MOONDREAM_API_KEY=tu_clave_api_aqui
```

### Paso 3: Instalación Automática

Ejecuta el archivo batch para instalar todas las dependencias automáticamente:

```bash
build_exe.bat
```

Este script:
- ✅ Crea un entorno virtual de Python
- ✅ Instala todas las dependencias necesarias
- ✅ Descarga modelos de IA requeridos
- ✅ Configura la base de datos
- ✅ Compila el ejecutable (opcional)

**⏱️ Tiempo estimado**: 5-10 minutos (dependiendo de tu conexión a internet)

### Paso 4: Ejecutar la Aplicación

Después de la instalación, ejecuta:

```bash
python app.py
```

O utiliza el ejecutable generado en la carpeta `dist/`.

---

## ⚙️ Configuración Inicial

### 1. Calibración de Cámaras

Antes del primer uso, es necesario calibrar las cámaras:

1. Abre la aplicación
2. Ve a **Configuración > Calibración**
3. Coloca un objeto de tamaño conocido (regla calibrada)
4. Sigue las instrucciones en pantalla
5. Guarda los parámetros de calibración

### 2. Configuración del Túnel de Muestreo

**Distancia óptima cámara-vidrio**: **7 cm**

Esta distancia fue determinada experimentalmente y proporciona:
- ✅ Campo de visión completo del pez
- ✅ Minimiza distorsión óptica
- ✅ Mejor precisión en mediciones

### 3. Configuración de Iluminación

- Utiliza fondo **verde** para mejor contraste
- Iluminación uniforme sin sombras
- Evita reflejos directos en el vidrio

---

## 📖 Guía de Uso

### Modo Manual

1. **Iniciar captura**:
   - Haz clic en "Captura Manual"
   - Espera a que el pez esté completamente dentro del túnel
   - Presiona "Capturar Frame"

2. **Procesamiento**:
   - El sistema detecta automáticamente el pez
   - Se aplica corrección óptica
   - Se calculan las dimensiones biométricas

3. **Guardar resultados**:
   - Revisa las mediciones en pantalla
   - Haz clic en "Guardar Medición"
   - Los datos se almacenan en la base de datos

### Modo Automático

1. **Activar modo automático**:
   - Ve a **Configuración > Modo de Captura**
   - Selecciona "Automático"
   - Define intervalo de captura (recomendado: cada 5 segundos)

2. **Monitoreo en tiempo real**:
   - El sistema detecta automáticamente cuando un pez pasa
   - Captura y procesa las imágenes
   - Guarda los resultados automáticamente

3. **Revisión de datos**:
   - Accede a **Trazabilidad > Historial**
   - Filtra por fecha, ID o rango de tamaño
   - Exporta datos a CSV o Excel

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────┐
│                 ZONA DE MUESTREO                    │
│  ┌────────────┐        ┌────────────┐              │
│  │  TANQUE 1  │◄──────►│  TANQUE 2  │              │
│  └────────────┘        └────────────┘              │
│         │                     │                     │
│         │    ┌──────────┐     │                     │
│         └───►│  TÚNEL   │◄────┘                     │
│              │  DE PASO │                           │
│              └────┬─────┘                           │
│                   │                                 │
│         ┌─────────┴──────────┐                      │
│         │                    │                      │
│    ┌────▼────┐         ┌────▼────┐                 │
│    │ CÁMARA  │         │ CÁMARA  │                 │
│    │ CENITAL │         │ LATERAL │                 │
│    └────┬────┘         └────┬────┘                 │
└─────────┼───────────────────┼─────────────────────┘
          │                   │
          │     USB / Red     │
          └────────┬──────────┘
                   │
     ┌─────────────▼──────────────┐
     │  SISTEMA DE PROCESAMIENTO  │
     │                            │
     │  ┌──────────────────────┐  │
     │  │  MOONDREAM + YOLOv8  │  │
     │  │  (Detección de ROI)  │  │
     │  └──────────┬───────────┘  │
     │             │               │
     │  ┌──────────▼───────────┐  │
     │  │  OpenCV + Algoritmos │  │
     │  │  (Segmentación)      │  │
     │  └──────────┬───────────┘  │
     │             │               │
     │  ┌──────────▼───────────┐  │
     │  │  Corrección Óptica   │  │
     │  │  (Refracción)        │  │
     │  └──────────┬───────────┘  │
     │             │               │
     │  ┌──────────▼───────────┐  │
     │  │  Cálculo Biométrico  │  │
     │  │  (L, A, An, Peso)    │  │
     │  └──────────┬───────────┘  │
     └─────────────┼──────────────┘
                   │
     ┌─────────────▼──────────────┐
     │      BASE DE DATOS         │
     │  ┌──────────────────────┐  │
     │  │  Historial           │  │
     │  │  Trazabilidad        │  │
     │  │  Imágenes            │  │
     │  │  Datos Biométricos   │  │
     │  └──────────────────────┘  │
     └────────────────────────────┘
```

### Estructura de Directorios

```
acuaponia-v1.002/
│
├── app.py                      # Aplicación principal
├── build_exe.bat              # Script de instalación
├── requirements.txt           # Dependencias Python
├── logo.ico                   # Ícono de la aplicación
├── save_ok.wav               # Sonido de confirmación
│
├── BasedeDatos/              # Módulo de base de datos
│   ├── __init__.py
│   └── database_manager.py
│
├── Config/                   # Archivos de configuración
│   ├── calibration.json      # Parámetros de calibración
│   └── settings.json         # Configuración general
│
├── Herramientas/            # Utilidades y herramientas
│   ├── __init__.py
│   ├── image_processor.py   # Procesamiento de imágenes
│   └── optical_correction.py # Corrección óptica
│
├── Modulos/                 # Módulos principales
│   ├── __init__.py
│   ├── camera_module.py     # Control de cámaras
│   ├── ai_detection.py      # Detección con IA
│   ├── biometry.py          # Cálculos biométricos
│   └── ui_interface.py      # Interfaz gráfica
│
└── README.md                # Este archivo
```

---

## 🌟 Ventajas del Sistema

### 🐟 Beneficios para los Peces

| Método Tradicional | Este Sistema |
|-------------------|--------------|
| ❌ Manipulación manual estresante | ✅ Completamente no invasivo |
| ❌ Mortalidad 1-2% | ✅ 0% mortalidad por medición |
| ❌ Riesgo de pérdida de mucosa protectora | ✅ Sin contacto físico |
| ❌ Interrupción del comportamiento natural | ✅ Monitoreo durante paso natural |
| ❌ Susceptibilidad a enfermedades | ✅ Ambiente no alterado |

### 💰 Beneficios Económicos

- **Reducción de costos de alimento**: Ajuste preciso de dosificación (ahorro del 10-15%)
- **Menor mortalidad**: Reducción del 1-2% de pérdidas por manipulación
- **Optimización de mano de obra**: Automatización del proceso de medición
- **Mejor tasa de conversión alimenticia**: Alimentación basada en datos precisos

### 📊 Beneficios Operativos

- **Datos más consistentes y precisos**: 93% de precisión en mediciones longitudinales
- **Monitoreo continuo**: Posibilidad de medir semanalmente sin estrés
- **Trazabilidad completa**: Historial detallado de cada pez
- **Escalabilidad**: Puede monitorear grandes poblaciones eficientemente
- **Información en tiempo real**: Decisiones basadas en datos actualizados

### 🔬 Beneficios Científicos

- **Investigación no destructiva**: Estudios longitudinales sin afectar a los sujetos
- **Gran volumen de datos**: Muestreos frecuentes y completos
- **Reproducibilidad**: Mediciones estandarizadas y objetivas
- **Correlación multivariable**: Análisis de múltiples parámetros simultáneos

---

## 📚 Publicación Científica

Este proyecto forma parte de una investigación publicada en:

**Título**: *"Implementation of a prototype desktop software based on computer vision for the growth traceability of rainbow trout fish (Oncorhynchus mykiss) in the LESTOMA-UDEC Laboratory"*

**Revista**: I+T+C: Investigación - Tecnología - Ciencia  
**Volumen**: 1, Número 19  
**Año**: 2025  
**ISSN**: e-ISSN: 2805-7201

### 📖 Resumen de la Investigación

La investigación validó el sistema mediante un estudio de **mes y medio** con **100 ejemplares** de trucha arcoíris, comparando mediciones automáticas vs. manuales:

**Resultados clave**:
- ✅ **93% de precisión** en medición longitudinal
- ✅ **10% de desviación** en estimación de peso
- ✅ **0% de mortalidad** durante las mediciones automatizadas
- ✅ **Reducción significativa** del tiempo de medición

### 🔍 Metodología Científica

El sistema implementa corrección de **distorsión óptica** mediante la Ley de Snell:

```
d_real = (d_aparente - e) · (n_agua / n_vidrio) + e · (n_vidrio / n_aire)
```

Donde:
- `d_aparente`: Distancia medida en la imagen
- `d_real`: Distancia real corregida
- `e`: Espesor del vidrio (4mm)
- `n_aire ≈ 1.0003`
- `n_vidrio ≈ 1.5`
- `n_agua ≈ 1.333`

Además, se aplicaron **funciones polinómicas de corrección** para compensar variaciones según la posición del pez en el túnel:

```python
# Función polinómica promedio
y_promedio = 0.0011·x² - 0.0355·x + 7.5852
```

### 📄 Citar este Trabajo

Si utilizas este sistema en tu investigación, por favor cita:

```bibtex
@article{andrade2025,
  title={Implementation of a prototype desktop software based on computer vision for the growth traceability of rainbow trout fish (Oncorhynchus mykiss) in the LESTOMA-UDEC Laboratory},
  author={Andrade Ramírez, Jaime Eduardo and López Cruz, Ivone Gisela and Castro Martínez, Yeffersson Stiven and Flórez Lesmes, Alejandro},
  journal={I+T+C: Investigación - Tecnología - Ciencia},
  volume={1},
  number={19},
  year={2025},
  publisher={Universidad Comfacauca}
}
```

---

## 👥 Equipo de Desarrollo

### Investigadores Principales

<table>
  <tr>
    <td align="center">
      <strong>Jaime Eduardo Andrade Ramírez</strong><br>
      <em>Director del Proyecto</em><br>
      Universidad de Cundinamarca<br>
      📧 jeandrade@ucundinamarca.edu.co
    </td>
    <td align="center">
      <strong>Ivone Gisela López Cruz</strong><br>
      <em>Investigadora Principal</em><br>
      Universidad de Cundinamarca<br>
      📧 iglopez@ucundinamarca.edu.co
    </td>
  </tr>
  <tr>
    <td align="center">
      <strong>Yeffersson Stiven Castro Martínez</strong><br>
      <em>Desarrollador Principal</em><br>
      Universidad de Cundinamarca<br>
      📧 ystivencastro@ucundinamarca.edu.co<br>
      🔗 <a href="https://github.com/stivencastro138">GitHub</a>
    </td>
  </tr>
</table>

### 🏛️ Institución

**Universidad de Cundinamarca**  
Extensión Facatativá, Cundinamarca, Colombia

**Laboratorio**: LESTOMA (Laboratorio Experimental de Sistemas Tecnológicos Orientados a Modelos Acuapónicos)

---

## 🤝 Contribuciones

Este proyecto está en **desarrollo activo** y acepta contribuciones. Si deseas colaborar:

### Cómo Contribuir

1. **Fork** el repositorio
2. Crea una **rama** para tu feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. **Push** a la rama (`git push origin feature/AmazingFeature`)
5. Abre un **Pull Request**

### Áreas de Contribución

Estamos especialmente interesados en contribuciones en:

- 🎨 **Mejoras de interfaz**: Diseño UI/UX
- 🧠 **Modelos de IA**: Optimización de algoritmos de detección
- 📊 **Análisis de datos**: Nuevas métricas biométricas
- 🌐 **Internacionalización**: Traducción a otros idiomas
- 📖 **Documentación**: Tutoriales y guías
- 🐛 **Reportes de bugs**: Identificación y solución de errores

### Código de Conducta

Por favor, lee nuestro [Código de Conducta](CODE_OF_CONDUCT.md) antes de contribuir.

---

## 📜 Licencia

Este proyecto está licenciado bajo la **Licencia MIT** - ver el archivo [LICENSE](LICENSE) para más detalles.

```
MIT License

Copyright (c) 2025 Universidad de Cundinamarca - LESTOMA

Se concede permiso, de forma gratuita, a cualquier persona que obtenga una copia
de este software y archivos de documentación asociados (el "Software"), para 
utilizar el Software sin restricciones, incluyendo sin limitación los derechos 
de usar, copiar, modificar, fusionar, publicar, distribuir, sublicenciar y/o 
vender copias del Software, y permitir a las personas a las que se les 
proporcione el Software hacer lo mismo, sujeto a las siguientes condiciones:

El aviso de copyright anterior y este aviso de permiso se incluirán en todas 
las copias o porciones sustanciales del Software.

EL SOFTWARE SE PROPORCIONA "TAL CUAL", SIN GARANTÍA DE NINGÚN TIPO...
```

---

## 📞 Contacto

### Soporte Técnico
- 📧 Email: ystivencastro@ucundinamarca.edu.co
- 🐛 Issues: [GitHub Issues](https://github.com/stivencastro138/acuaponia-v1.002/issues)

### Investigación y Colaboración Académica
- 📧 Email: iglopez@ucundinamarca.edu.co
- 🏛️ Laboratorio LESTOMA-UDEC

### Redes Sociales
- 🔗 GitHub: [@stivencastro138](https://github.com/stivencastro138)

---

## 🙏 Agradecimientos

Agradecimientos especiales a:

- **Universidad de Cundinamarca** por el apoyo institucional
- **Laboratorio LESTOMA-UDEC** por las instalaciones y recursos
- Comunidad de **OpenCV** y **Python** por las herramientas open-source
- Todos los **colaboradores** y **testers** del proyecto

---

## 📅 Roadmap

### Versión Actual (v1.0)
- ✅ Sistema de captura dual de imágenes
- ✅ Detección automática con IA
- ✅ Corrección de distorsión óptica
- ✅ Cálculo de biometría básica
- ✅ Base de datos local

### Próximas Versiones

#### v1.1 (Q2 2025)
- 🔄 Mejora de precisión en estimación de peso
- 📊 Dashboard de análisis avanzado
- 📱 Aplicación móvil para monitoreo remoto
- ☁️ Sincronización en la nube

#### v2.0 (Q4 2025)
- 🌐 Sistema multi-tanque
- 🤖 Predicción de crecimiento con ML
- 📈 Análisis predictivo de alimentación
- 🔔 Sistema de alertas inteligente
- 🎯 Detección de comportamientos anormales

#### Futuro (2026+)
- 🦠 Detección temprana de enfermedades
- 🌡️ Integración con sensores ambientales
- 📊 Big Data analytics para optimización de producción
- 🏭 Versión industrial para granjas comerciales

---

## ❓ FAQ (Preguntas Frecuentes)

<details>
<summary><strong>¿Funciona con otras especies de peces?</strong></summary>

El sistema está optimizado para trucha arcoíris, pero puede adaptarse a otras especies con ajustes en los parámetros de calibración. Se requeriría reentrenamiento del modelo de IA para especies con morfología significativamente diferente.

</details>

<details>
<summary><strong>¿Necesito conocimientos de programación para usarlo?</strong></summary>

No. La interfaz gráfica está diseñada para ser intuitiva y no requiere conocimientos técnicos. Solo necesitas seguir la guía de instalación y calibración inicial.

</details>

<details>
<summary><strong>¿Puedo usar cámaras de otras marcas?</strong></summary>

Sí, el sistema es compatible con cualquier cámara USB que soporte resolución 1080p. Sin embargo, se recomienda calibrar específicamente para tu modelo de cámara.

</details>

<details>
<summary><strong>¿El sistema funciona en tiempo real?</strong></summary>

Sí, el procesamiento se realiza en tiempo real. El tiempo de análisis por pez es aproximadamente 2-3 segundos, dependiendo del hardware.

</details>

<details>
<summary><strong>¿Qué hago si la precisión es baja?</strong></summary>

1. Verifica la calibración de las cámaras
2. Asegúrate de que la distancia cámara-vidrio sea de 7 cm
3. Comprueba la iluminación (uniforme, sin reflejos)
4. Limpia el vidrio del túnel
5. Verifica que no haya burbujas en el agua

</details>

<details>
<summary><strong>¿Puedo exportar los datos?</strong></summary>

Sí, el sistema permite exportar a formato CSV, Excel y JSON para análisis posterior en otras herramientas.

</details>

---

<div align="center">

### ⭐ Si este proyecto te fue útil, ¡dale una estrella!

**Desarrollado con ❤️ por el equipo LESTOMA-UDEC**

[⬆️ Volver arriba](#-sistema-de-trazabilidad-de-crecimiento-de-trucha-arcoíris-mediante-visión-por-computadora)

---

**© 2025 Universidad de Cundinamarca - LESTOMA. Todos los derechos reservados.**

</div>
