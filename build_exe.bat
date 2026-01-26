@echo off
title Compilador FishTrace V1.2 
set "APP_NAME=FishTrace"
set "EXE_PATH=%CD%\dist\%APP_NAME%\%APP_NAME%.exe"
set "ICO_PATH=%CD%\logo.ico"

set "DESKTOP_PATH=%USERPROFILE%\Desktop\%APP_NAME%.lnk"
if exist "%USERPROFILE%\OneDrive\Escritorio" set "DESKTOP_PATH=%USERPROFILE%\OneDrive\Escritorio\%APP_NAME%.lnk"

echo ===========================================
echo 1. Usando Python 3.11 para instalar dependencias
echo ===========================================
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip uninstall pyqt6 pyqt6-plugins pyqt6-qt6 -y
py -3.11 -m pip install pyinstaller pyqtdarktheme==2.1.0 darkdetect
py -3.11 -m pip install -r requirements.txt

echo.
echo 2. Limpiando archivos temporales...
if exist build rd /s /q build
if exist dist rd /s /q dist

echo.
echo 3. Generando ejecutable con Python 3.11...
py -3.11 -m PyInstaller --noconfirm --onedir --windowed ^
 --name "%APP_NAME%" ^
 --icon "logo.ico" ^
 --exclude-module PyQt6 ^
 --add-data "Config;Config" ^
 --add-data "Modulos;Modulos" ^
 --add-data "BasedeDatos;BasedeDatos" ^
 --add-data "Modelos;Modelos" ^
 --add-data "Herramientas;Herramientas" ^
 "app.py"

echo.
echo 4. Creando acceso directo en el Escritorio...
powershell -ExecutionPolicy Bypass -Command ^
 "$ws = New-Object -ComObject WScript.Shell; " ^
 "$s = $ws.CreateShortcut('%DESKTOP_PATH%'); " ^
 "$s.TargetPath = '%EXE_PATH%'; " ^
 "$s.WorkingDirectory = '%CD%\dist\%APP_NAME%'; " ^
 "if (Test-Path '%ICO_PATH%') { $s.IconLocation = '%ICO_PATH%' }; " ^
 "$s.Save()"

echo ===========================================
echo PROCESO FINALIZADO
echo ===========================================
pause