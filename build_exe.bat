@echo off
title Compilador FishTrace V1.2 
set "APP_NAME=FishTrace"
set "EXE_PATH=%CD%\dist\%APP_NAME%\%APP_NAME%.exe"
set "ICO_PATH=%CD%\logo.ico"
set "DESKTOP_PATH=%USERPROFILE%\Desktop\%APP_NAME%.lnk"

echo ===========================================
echo 1. Resolviendo conflictos de dependencias...
pip uninstall pyqt6 pyqt6-plugins pyqt6-qt6 -y
pip install pyinstaller
pip install -r requirements.txt

echo.
echo 2. Limpiando compilaciones anteriores...
if exist build rd /s /q build
if exist dist rd /s /q dist

echo.
echo 3. Generando ejecutable (.exe)...
pyinstaller --noconfirm --onedir --windowed ^
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
powershell -Command "$s=[WScript.Shell]::new();$l=$s.CreateShortcut('%DESKTOP_PATH%');$l.TargetPath='%EXE_PATH%';$l.WorkingDirectory='%CD%\dist\%APP_NAME%';if(Test-Path '%ICO_PATH%'){$l.IconLocation='%ICO_PATH%'};$l.Save()"

if exist "%DESKTOP_PATH%" (
    echo [OK] Acceso directo creado exitosamente.
) else (
    echo [ERROR] No se pudo crear el acceso directo. Intenta ejecutar como Administrador.
)

echo ===========================================
echo PROCESO FINALIZADO
echo Carpeta del software: %CD%\dist\%APP_NAME%
echo ===========================================
pause