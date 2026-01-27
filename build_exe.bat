@echo off
title Compilador FishTrace V1.2 
set "APP_NAME=FishTrace"
set "EXE_PATH=%CD%\dist\%APP_NAME%\%APP_NAME%.exe"
set "ICO_PATH=%CD%\logo.ico"

set "DESKTOP_PATH=%USERPROFILE%\Desktop\%APP_NAME%.lnk"
if exist "%USERPROFILE%\OneDrive\Escritorio" set "DESKTOP_PATH=%USERPROFILE%\OneDrive\Escritorio\%APP_NAME%.lnk"

echo ===========================================
echo 1. Preparando entorno y dependencias
echo ===========================================
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip uninstall pyqt6 pyqt6-plugins pyqt6-qt6 -y
py -3.11 -m pip install pyinstaller pyqtdarktheme==2.1.0 darkdetect
py -3.11 -m pip install -r requirements.txt

echo.
echo 2. Limpiando compilaciones anteriores...
if exist build rd /s /q build
if exist dist rd /s /q dist

echo.
echo 3. Generando ejecutable (.exe) con icono...
REM 
py -3.11 -m PyInstaller --noconfirm --onedir --windowed ^
 --name "%APP_NAME%" ^
 --icon "%ICO_PATH%" ^
 --exclude-module PyQt6 ^
 --add-data "Config;Config" ^
 --add-data "Modulos;Modulos" ^
 --add-data "BasedeDatos;BasedeDatos" ^
 --add-data "Herramientas;Herramientas" ^
 "app.py"

REM 
if %ERRORLEVEL% NEQ 0 (
    color 4F
    echo.
    echo ===========================================
    echo ERROR CRITICO: La compilacion ha fallado.
    echo No se ha creado el archivo .exe.
    echo Revise los errores arriba (letras rojas).
    echo ===========================================
    pause
    exit /b
)
color 07

echo.
echo 4. Creando acceso directo con icono en el Escritorio...
powershell -ExecutionPolicy Bypass -Command ^
 "$ws = New-Object -ComObject WScript.Shell; " ^
 "$s = $ws.CreateShortcut('%DESKTOP_PATH%'); " ^
 "$s.TargetPath = '%EXE_PATH%'; " ^
 "$s.WorkingDirectory = '%CD%\dist\%APP_NAME%'; " ^
 "$s.IconLocation = '%ICO_PATH%'; " ^
 "$s.Save()"

echo.
echo 5. Iniciando aplicacion automaticamente...
if exist "%EXE_PATH%" (
    start "" "%EXE_PATH%"
) else (
    echo Error: No se encuentra el archivo ejecutable.
    pause
)

echo ===========================================
echo PROCESO FINALIZADO EXITOSAMENTE
echo ===========================================
pause