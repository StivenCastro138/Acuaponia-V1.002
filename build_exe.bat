@echo off
title Instalador y Compilador FishTrace V1.2
set "APP_NAME=FishTrace"

echo ======================================================
echo           INSTALADOR INICIAL DE FISHTRACE
echo ======================================================
echo.

echo [+] Verificando e instalando dependencias necesarias...
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip uninstall pyqt6 pyqt6-plugins pyqt6-qt6 -y
py -3.11 -m pip install pyinstaller pyqtdarktheme==2.1.0 darkdetect
py -3.11 -m pip install -r requirements.txt

echo.
echo [+] Limpiando espacio de trabajo...
if exist build rd /s /q build
if exist dist rd /s /q dist
if exist "%APP_NAME%.exe" del /f /q "%APP_NAME%.exe"

echo.
echo [+] Generando el ejecutable FishTrace.exe...
echo (Esto puede tardar un minuto la primera vez)
py -3.11 -m PyInstaller --noconfirm --onefile --windowed ^
 --name "%APP_NAME%" ^
 --icon "logo.ico" ^
 --exclude-module PyQt6 ^
 "app.py"

echo.
if exist "dist\%APP_NAME%.exe" (
    move /y "dist\%APP_NAME%.exe" "%CD%\"
)

rd /s /q build
rd /s /q dist

echo.
echo ======================================================
echo          INSTALACIÓN FINALIZADA CON ÉXITO
echo ======================================================
echo El ejecutable ya esta en la carpeta raiz. 
echo Al abrirlo se crearan las carpetas de Base de Datos y Eventos.
echo.
pause