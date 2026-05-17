@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  MACRO FORECAST TERMINAL - One-click Launcher (Windows)
echo ============================================================
echo.

REM Step 1: detect Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python chua duoc cai dat tren may.
    echo.
    echo Vui long tai Python 3.12 tu:
    echo   https://www.python.org/downloads/release/python-3128/
    echo.
    echo Khi cai dat, nho TICH O "Add Python to PATH"!
    echo.
    pause
    exit /b 1
)

REM Step 2: show Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [INFO] Python version: !PYVER!

REM Step 3: create venv if missing
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Tao virtual environment lan dau (mat ~30 giay)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Khong the tao venv.
        pause
        exit /b 1
    )
)

REM Step 4: install dependencies if first run
.venv\Scripts\python.exe -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Cai dat dependencies lan dau (mat 3-8 phut)...
    echo        Vui long doi, dung tat cua so nay.
    echo.
    .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    .venv\Scripts\python.exe -m pip install -e . --quiet
    .venv\Scripts\python.exe -m pip install flask --quiet
    if errorlevel 1 (
        echo [ERROR] Cai dat that bai.
        pause
        exit /b 1
    )
    echo [OK] Cai dat hoan tat.
    echo.
)

REM Step 5: generate Excel templates if missing
if not exist "macro_pipeline\webapp\static\templates\yield-curve.xlsx" (
    echo [INFO] Tao Excel templates...
    .venv\Scripts\python.exe scripts\generate_excel_templates.py
)

REM Step 6: launch
echo.
echo [INFO] Dang khoi dong Macro Forecast Terminal...
echo [INFO] Browser se tu dong mo tai: http://localhost:8000
echo.
echo Nhan Ctrl+C de dung server.
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"
.venv\Scripts\python.exe -m macro_pipeline.webapp.app

endlocal
