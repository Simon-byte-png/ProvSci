@echo off
setlocal
set "ROOT_DIR=%~dp0.."
if "%~1"=="" (set "HOST=127.0.0.1") else (set "HOST=%~1")
if "%~2"=="" (set "PORT=4173") else (set "PORT=%~2")
set "PYTHONPATH=%ROOT_DIR%\src;%PYTHONPATH%"
cd /d "%ROOT_DIR%"
python "%ROOT_DIR%\scripts\run_product_app.py" %HOST% %PORT%
