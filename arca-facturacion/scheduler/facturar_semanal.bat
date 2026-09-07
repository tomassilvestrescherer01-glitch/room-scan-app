@echo off
REM Wrapper para el Programador de tareas de Windows.
REM Ajustá las dos rutas de abajo a donde tengas el proyecto y tu Python.

set PROYECTO_DIR=C:\ruta\a\arca-facturacion
set PYTHON_EXE=C:\ruta\a\python.exe

REM Por defecto factura en PRODUCCIÓN. No tocar esta línea hasta haber
REM probado todo en homologación y haber pasado al certificado real.
set ARCA_CONFIG=%PROYECTO_DIR%\config\config.produccion.ini

cd /d "%PROYECTO_DIR%"
"%PYTHON_EXE%" emitir_factura_prueba.py >> "%PROYECTO_DIR%\scheduler\log.txt" 2>&1
