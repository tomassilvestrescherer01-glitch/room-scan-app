@echo off
REM Wrapper para el Programador de tareas de Windows.
REM Ajustá la ruta de abajo a donde tengas el proyecto.
REM Usa confirmar_y_facturar.py: antes de facturar muestra un cartel
REM preguntando si confirmás. Para que se vea, la tarea programada
REM tiene que correr con la sesión de Windows iniciada (no "en segundo
REM plano sin que nadie esté logueado").

set PROYECTO_DIR=C:\ruta\a\arca-facturacion

REM Cuando pasen a producción (certificado real + categoría resuelta),
REM cambiar esta línea a config.produccion.ini.
set ARCA_CONFIG=%PROYECTO_DIR%\config\config.homologacion.ini

cd /d "%PROYECTO_DIR%"
py confirmar_y_facturar.py >> "%PROYECTO_DIR%\scheduler\log.txt" 2>&1
