@echo off
title Crear OrganizadorPC.exe
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo No se ha encontrado Python. Instalalo desde https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Instalando herramientas...
%PY% -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 goto error

echo Creando el ejecutable, puede tardar un par de minutos...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name "OrganizadorPC" --icon "assets\icon.ico" --add-data "assets;assets" --collect-all customtkinter main.py
if errorlevel 1 goto error

echo.
echo  Listo. El programa esta en la carpeta "dist":  dist\OrganizadorPC.exe
echo  Puedes copiarlo donde quieras y crear un acceso directo en el escritorio.
echo.
explorer dist
pause
exit /b 0

:error
echo.
echo  Ha ocurrido un error al crear el ejecutable.
pause
exit /b 1
