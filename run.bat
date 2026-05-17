@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===============================================================
echo  MACRO FORECAST TERMINAL - One-click Launcher (Windows) [L11.2]
echo ===============================================================
echo.

REM === Phase 1: detect best Python via py launcher cascade ===
set PYTHON_CMD=
set PYTHON_DESC=

where py >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    REM Try py -3.13 first (preferred — most recent supported version)
    py -3.13 -c "" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_CMD=py -3.13"
        set "PYTHON_DESC=Python 3.13 (py launcher)"
        goto :python_found
    )
    REM Fallback to py -3.12
    py -3.12 -c "" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_CMD=py -3.12"
        set "PYTHON_DESC=Python 3.12 (py launcher)"
        goto :python_found
    )
)

REM === Phase 2: fallback to PATH python (validated by check_python_version.py) ===
where python >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Khong tim thay Python 3.12 hoac 3.13 tren may.
    echo.
    echo Cai Python 3.13 tu:
    echo   https://www.python.org/downloads/release/python-31313/
    echo.
    echo Hoac neu da co Python install manager:
    echo   py install 3.13
    echo.
    echo Khi cai dat, nho TICH O "Add Python to PATH"!
    echo.
    pause
    exit /b 1
)

python scripts\check_python_version.py
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo Pipeline yeu cau Python 3.12 hoac 3.13. Cai dat tai:
    echo   https://www.python.org/downloads/release/python-31313/
    echo Hoac dung Python install manager:
    echo   py install 3.13
    echo Sau khi cai, dong cua so nay va chay lai run.bat
    echo.
    pause
    exit /b 1
)
set "PYTHON_CMD=python"
set "PYTHON_DESC=Python (PATH, da validate)"

:python_found
echo [INFO] Su dung: !PYTHON_DESC!
!PYTHON_CMD! --version
echo.

REM === Phase 3: venv create if missing ===
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Tao virtual environment lan dau (mat ~30 giay)...
    !PYTHON_CMD! -m venv .venv
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Khong the tao venv.
        pause
        exit /b 1
    )
)

REM === Phase 4: install dependencies if first run ===
.venv\Scripts\python.exe -c "import flask" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [INFO] Cai dat dependencies lan dau (mat 3-8 phut)...
    echo        Vui long doi, dung tat cua so nay.
    echo.
    .venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    .venv\Scripts\python.exe -m pip install -e . --quiet
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Cai dat phu thuoc that bai.
        pause
        exit /b 1
    )
    .venv\Scripts\python.exe -m pip install flask --quiet
    echo [OK] Cai dat hoan tat.
    echo.
)

REM === Phase 5: generate Excel templates if missing ===
if not exist "macro_pipeline\webapp\static\templates\yield-curve.xlsx" (
    echo [INFO] Tao Excel templates...
    .venv\Scripts\python.exe scripts\generate_excel_templates.py
)

REM === Phase 6: launch via standalone_launcher (auto-opens browser + handles port conflicts) ===
echo.
echo [INFO] Dang khoi dong Macro Forecast Terminal...
echo [INFO] Browser se tu dong mo tai: http://localhost:8000
echo.
echo Nhan Ctrl+C de dung server.
echo.

.venv\Scripts\python.exe -m macro_pipeline.standalone_launcher

endlocal
