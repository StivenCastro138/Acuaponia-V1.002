@echo off
title Instalador y Compilador FishTrace
set "APP_NAME=FishTrace"

echo ===========================================
echo 1. Instalando dependencias (Necesario tras clonar)
echo ===========================================
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip uninstall pyqt6 pyqt6-plugins pyqt6-qt6 -y
py -3.11 -m pip install pyinstaller pyqtdarktheme==2.1.0 darkdetect
py -3.11 -m pip install -r requirements.txt

echo.
echo 2. Limpiando carpetas temporales...
if exist build rd /s /q build
if exist dist rd /s /q dist
if exist "%APP_NAME%.exe" del /f /q "%APP_NAME%.exe"

echo.
echo 3. Compilando FishTrace...
py -3.11 -m PyInstaller --noconfirm --onefile --windowed ^
 --name "%APP_NAME%" ^
 --icon "logo.ico" ^
 --exclude-module PyQt6 ^
 "app.py"

echo.
echo 4. Organizando archivos finales...
if exist "dist\%APP_NAME%.exe" (
    move /y "dist\%APP_NAME%.exe" "%CD%\"
)

rd /s /q build
rd /s /q dist

echo ===========================================
echo PROCESO COMPLETADO
echo El ejecutable esta en la raiz junto a tus carpetas.
echo ===========================================
pause