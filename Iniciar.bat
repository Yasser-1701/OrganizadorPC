@echo off
title Organizador PC
cd /d "%~dp0"
echo.
echo  === Organizador PC ===
echo.

rem ---- 0. Comprobar que el ZIP esta descomprimido ----
if not exist "%~dp0main.py" goto nounzip
if not exist "%~dp0orgpc\ui\app.py" goto nounzip

rem ---- 1. Buscar Python ----
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (
    python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY goto nopython
echo  [1/4] Python encontrado:
%PY% --version

rem ---- 2. Version minima ----
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 goto oldpython

rem ---- 3. Tkinter (parte de Python) ----
%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 goto notk
echo  [2/4] Tkinter OK

rem ---- 4. Dependencias ----
%PY% -c "import customtkinter, psutil, PIL.ImageTk" >nul 2>nul
if not errorlevel 1 goto depsok
echo  [3/4] Instalando dependencias, solo la primera vez...
%PY% -m pip install --upgrade pip >nul 2>nul
%PY% -m pip install "customtkinter==6.0.0" psutil pillow
%PY% -c "import customtkinter, psutil, PIL.ImageTk" >nul 2>nul
if errorlevel 1 goto piperror
:depsok
echo  [3/4] Dependencias OK

rem ---- 5. Abrir la app (con consola visible si falla) ----
echo  [4/4] Abriendo Organizador PC...
rem pythonw abre la app sin ventana negra (los errores salen en una ventana propia)
set "PYW=pythonw"
if "%PY%"=="py -3" set "PYW=pyw -3"
start "" %PYW% main.py
if errorlevel 1 (
    %PY% main.py
    if errorlevel 1 goto apperror
)
exit /b 0

:nounzip
echo  Faltan archivos: parece que has abierto Iniciar.bat desde DENTRO del ZIP.
echo.
echo  1. Cierra esta ventana
echo  2. Haz clic derecho sobre el archivo .zip y elige "Extraer todo..."
echo  3. Entra en la carpeta extraida y abre Iniciar.bat desde ahi
goto fin

:nopython
echo  No se ha encontrado Python en este PC (o es el acceso directo de la Microsoft Store).
echo.
echo  1. Descargalo de https://www.python.org/downloads/
echo  2. En la primera pantalla del instalador marca "Add python.exe to PATH"
echo  3. Cierra esta ventana y vuelve a abrir Iniciar.bat
echo.
echo  O desde una consola:  winget install Python.Python.3.12
goto fin

:oldpython
echo  Tu version de Python es demasiado antigua. Instala la 3.12 desde https://www.python.org/downloads/
goto fin

:notk
echo  Tu Python no tiene "tkinter" (la parte de ventanas).
echo  Vuelve a ejecutar el instalador de Python, elige "Modify" y marca "tcl/tk and IDLE".
goto fin

:piperror
echo.
echo  No se pudieron instalar las dependencias. Revisa tu conexion a internet
echo  y manda una captura de esta ventana.
goto fin

:apperror
echo.
echo  La app se ha cerrado con un error. Manda una captura de esta ventana.

:fin
echo.
pause
exit /b 1
