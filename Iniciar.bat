@echo off
title Organizador PC
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY goto nopython

if exist ".dependencias_ok" goto run
echo Instalando dependencias, solo la primera vez...
%PY% -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto piperror
echo ok> ".dependencias_ok"

:run
start "" %PY%w main.py
exit /b 0

:nopython
echo.
echo  No se ha encontrado Python en este PC.
echo.
echo  1. Descargalo de https://www.python.org/downloads/
echo  2. Durante la instalacion marca la casilla "Add python.exe to PATH"
echo  3. Vuelve a abrir este archivo
echo.
echo  O instalalo desde una consola con:  winget install Python.Python.3.12
echo.
pause
exit /b 1

:piperror
echo.
echo  No se pudieron instalar las dependencias. Revisa tu conexion a internet.
pause
exit /b 1
