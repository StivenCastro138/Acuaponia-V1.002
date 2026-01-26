@echo off
title Compilador de Proyecto Acuaponia
echo ===========================================
echo Preparando entorno para crear el .exe
echo ===========================================

:: Instalar dependencias necesarias
echo 1. Verificando PyInstaller y dependencias...
pip install pyinstaller
pip install -r requirements.txt

:: Limpiar compilaciones anteriores si existen
if exist build rd /s /q build
if exist dist rd /s /q dist

echo 2. Iniciando compilacion con PyInstaller...
pyinstaller --noconfirm --onedir --windowed ^
 --name "FishTrace" ^
 --icon "logo.ico" ^
 --add-data "Config;Config" ^
 --add-data "Modulos;Modulos" ^
 --add-data "BasedeDatos;BasedeDatos" ^
 --add-data "Modelos;Modelos" ^
 --add-data "Herramientas;Herramientas" ^
 "app.py"

echo ===========================================
echo PROCESO FINALIZADO
echo El ejecutable esta en: dist/FishTrace/FishTrace.exe
echo ===========================================
pause