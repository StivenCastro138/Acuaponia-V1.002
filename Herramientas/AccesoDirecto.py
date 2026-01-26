import os
import sys
import winshell
from pathlib import Path
from win32com.client import Dispatch
from PIL import Image, ImageDraw

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

APP_NAME = "Sistema Medición Truchas"
APP_DESCRIPTION = "Sistema de medición biométrica de truchas con visión artificial"
ICON_NAME = "trucha.ico"

# ============================================================================
# CREAR ICONO PERSONALIZADO
# ============================================================================

def crear_icono_trucha():
    """Crea el icono.ico."""
    
    try:
        
        size = 256
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        for i in range(size//2, 0, -1):
            opacity = int(255 * (i / (size//2)))
            color = (30, 144, 255, opacity) 
            draw.ellipse([size//2-i, size//2-i, size//2+i, size//2+i], 
                        fill=color, outline=None)
        
        fish_color = (255, 140, 0, 255)  
        draw.ellipse([40, 90, 200, 166], fill=fish_color, outline=(0,0,0,255), width=3)
        
        draw.polygon([(200, 128), (240, 100), (240, 156)], 
                    fill=fish_color, outline=(0,0,0,255))
        
        draw.polygon([(100, 90), (120, 60), (140, 90)], 
                    fill=fish_color, outline=(0,0,0,255))
        
        draw.ellipse([160, 115, 180, 135], fill=(255,255,255,255), outline=(0,0,0,255))
        draw.ellipse([167, 122, 173, 128], fill=(0,0,0,255))
        
        spot_color = (139, 69, 19, 200)  
        spots = [(70,110), (90,130), (120,115), (150,140), (110,145)]
        for x, y in spots:
            draw.ellipse([x-4, y-4, x+4, y+4], fill=spot_color)
        
        icon_path = Path(__file__).parent / ICON_NAME
        
        sizes = [(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)]
        images = [img.resize(size, Image.Resampling.LANCZOS) for size in sizes]
        
        # Guardar como .ico
        images[0].save(icon_path, format='ICO', sizes=[size for size in sizes])
        
        print(f"✅ Icono creado: {icon_path}")
        return icon_path
        
    except ImportError:
        print("⚠️  Pillow no instalado. Usando icono genérico de Python.")
        print("   Para icono personalizado: pip install Pillow")
        return None

# ============================================================================
# CREAR ARCHIVO .BAT CON PRIVILEGIOS
# ============================================================================

def crear_bat_launcher():
    """Crea archivo .bat que ejecuta Python como administrador."""
    
    script_path = Path(__file__).parent.parent / "app.py"
    python_exe = sys.executable
    
    # Contenido del .bat con solicitud de permisos admin
    bat_content = f"""@echo off
title {APP_NAME}
color 0A

REM Verificar permisos de administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Ejecutando con privilegios de administrador...
    goto :run
) else (
    echo Solicitando permisos de administrador...
    goto :UAC
)

:UAC
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\\getadmin.vbs"
    echo UAC.ShellExecute "{python_exe}", "{script_path}", "{script_path.parent}", "runas", 1 >> "%temp%\\getadmin.vbs"
    "%temp%\\getadmin.vbs"
    del "%temp%\\getadmin.vbs"
    exit /B

:run
    cd /d "{script_path.parent}"
    start "" /max "{python_exe}" "{script_path}"
    exit
"""
    
    bat_path = script_path.parent / "Launcher_Admin.bat"
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    
    print(f"✅ Launcher creado: {bat_path}")
    return bat_path

# ============================================================================
# CREAR ACCESO DIRECTO EN ESCRITORIO
# ============================================================================

def crear_acceso_directo(bat_path, icon_path=None):
    """Crea acceso directo en el escritorio con icono y configuración."""
    
    try:
        # Obtener ruta del escritorio
        desktop = winshell.desktop()
        shortcut_path = os.path.join(desktop, f"{APP_NAME}.lnk")
        
        # Crear acceso directo
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        
        # Configurar propiedades
        shortcut.TargetPath = str(bat_path)
        shortcut.WorkingDirectory = str(bat_path.parent)
        shortcut.Description = APP_DESCRIPTION
        shortcut.WindowStyle = 3 
        
        if icon_path and icon_path.exists():
            shortcut.IconLocation = str(icon_path)
        else:
            shortcut.IconLocation = f"{sys.executable},0"
        
        # Guardar
        shortcut.save()
        
        print(f"✅ Acceso directo creado en escritorio: {shortcut_path}")
        print(f"   Nombre: {APP_NAME}")
        print(f"   Ventana: Maximizada")
        print(f"   Admin: Solicitará permisos al ejecutar")
        
        return shortcut_path
        
    except Exception as e:
        print(f"❌ Error al crear acceso directo: {e}")
        print(f"   Alternativa: Arrastra '{bat_path}' al escritorio manualmente")
        return None

# ============================================================================
# CREAR ARCHIVO .VBS PARA EJECUCIÓN SILENCIOSA (OPCIONAL)
# ============================================================================

def crear_vbs_launcher(bat_path):
    """Crea launcher VBS que ejecuta el .bat sin mostrar consola."""
    
    vbs_content = f"""Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{bat_path}" & chr(34), 0
Set WshShell = Nothing
"""
    
    vbs_path = bat_path.parent / "Launcher_Silencioso.vbs"
    with open(vbs_path, 'w', encoding='utf-8') as f:
        f.write(vbs_content)
    
    print(f"✅ Launcher silencioso creado: {vbs_path}")
    print(f"   (No muestra ventana de comandos)")
    return vbs_path

# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """Ejecuta la configuración completa."""
    
    print("="*70)
    print(f"  {APP_NAME} - Configurador de Acceso Directo")
    print("="*70)
    print()
    
    print("[1/4] Creando icono personalizado...")
    icon_path = crear_icono_trucha()
    print()
    
    # Crear archivo .bat
    print("[2/4] Creando launcher con privilegios...")
    bat_path = crear_bat_launcher()
    print()

    print("[3/4] Creando launcher silencioso (opcional)...")
    vbs_path = crear_vbs_launcher(bat_path)
    print()
    
    # Crear acceso directo en escritorio
    print("[4/4] Creando acceso directo en escritorio...")
    shortcut_path = crear_acceso_directo(bat_path, icon_path)
    print()
    
    print("="*70)
    print("✅ CONFIGURACIÓN COMPLETADA")
    print("="*70)
    print()
    print("Archivos creados:")
    print(f"  📄 {bat_path.name} - Launcher con admin")
    print(f"  📄 {vbs_path.name} - Launcher silencioso")
    if icon_path:
        print(f"  🎨 {ICON_NAME} - Icono personalizado")
    if shortcut_path:
        print(f"  🔗 Acceso directo en escritorio")
    print()
    print("Uso:")
    print(f"  1. Haz doble clic en '{APP_NAME}' en tu escritorio")
    print(f"  2. Acepta los permisos de administrador (UAC)")
    print(f"  3. La aplicación se abrirá maximizada")
    print()
    print("Nota: El launcher solicitará permisos de admin cada vez que lo ejecutes.")
    print("      Esto es necesario para acceso a cámaras y hardware.")
    print()

# ============================================================================
# EJECUCIÓN
# ============================================================================

if __name__ == "__main__":
    try:
        main()
        input("\nPresiona ENTER para salir...")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        input("\nPresiona ENTER para salir...")
        sys.exit(1)