@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===============================================================
echo  MACRO FORECAST TERMINAL - One-click Launcher [Windows L11.3]
echo ===============================================================
echo.

REM L11.3 DESIGN NOTES
REM   Flat goto structure — no nested `if (...) ( if (...) (...) )` blocks.
REM   Reason: L11.2's nested-if + unescaped parens in `echo (mat 3-8 phut)`
REM   tripped cmd's lazy parser ("... was unexpected at this time."). Flat
REM   structure removes the trigger entirely. Every error path lands at a
REM   labelled block at the bottom; `pause` + `exit /b 1` lives there once.
REM   PYTHON_DESC uses [brackets], not (parens), so the variable can be
REM   expanded inside any future construct without paren-counting risk.

REM ============================================================
REM  Phase 1 — Detect interpreter via py launcher cascade
REM ============================================================
set "PYTHON_CMD="
set "PYTHON_DESC="

where py >nul 2>&1
if errorlevel 1 goto :try_path_python

py -3.13 -c "import sys" >nul 2>&1
if errorlevel 1 goto :try_312
set "PYTHON_CMD=py -3.13"
set "PYTHON_DESC=Python 3.13 [py launcher]"
goto :python_found

:try_312
py -3.12 -c "import sys" >nul 2>&1
if errorlevel 1 goto :try_path_python
set "PYTHON_CMD=py -3.12"
set "PYTHON_DESC=Python 3.12 [py launcher]"
goto :python_found

REM ============================================================
REM  Phase 2 — Fallback to PATH python (gated by check script)
REM ============================================================
:try_path_python
where python >nul 2>&1
if errorlevel 1 goto :no_python

python scripts\check_python_version.py
if errorlevel 1 goto :wrong_version

set "PYTHON_CMD=python"
set "PYTHON_DESC=Python [PATH, validated]"
goto :python_found

REM ============================================================
REM  Phase 3 — Interpreter selected; create venv if missing
REM ============================================================
:python_found
echo [INFO] Su dung: !PYTHON_DESC!
!PYTHON_CMD! --version
echo.

if exist ".venv\Scripts\python.exe" goto :venv_ready

echo [INFO] Tao virtual environment lan dau, mat khoang 30 giay...
!PYTHON_CMD! -m venv .venv
if errorlevel 1 goto :venv_failed

REM ============================================================
REM  Phase 4 — Install dependencies on first run
REM ============================================================
:venv_ready
.venv\Scripts\python.exe -c "import flask" >nul 2>&1
if not errorlevel 1 goto :deps_ready

echo [INFO] Cai dependencies lan dau, mat khoang 3-8 phut...
echo        Vui long doi, dung tat cua so nay.
echo.
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -e . --quiet
if errorlevel 1 goto :pip_failed
.venv\Scripts\python.exe -m pip install flask --quiet
if errorlevel 1 goto :pip_failed
echo [OK] Cai dat hoan tat.
echo.

REM ============================================================
REM  Phase 5 — Generate Excel templates if missing, then launch
REM ============================================================
:deps_ready
if exist "macro_pipeline\webapp\static\templates\yield-curve.xlsx" goto :launch
echo [INFO] Tao Excel templates...
.venv\Scripts\python.exe scripts\generate_excel_templates.py

:launch
echo.
echo [INFO] Khoi dong Macro Forecast Terminal...
echo [INFO] Browser se tu dong mo tai: http://localhost:8000
echo.
echo Nhan Ctrl+C de dung server.
echo.
.venv\Scripts\python.exe -m macro_pipeline.standalone_launcher
goto :end

REM ============================================================
REM  Error labels (one paused exit per failure mode)
REM ============================================================
:no_python
echo [ERROR] Khong tim thay Python 3.12 hoac 3.13 tren may.
echo.
echo Cai Python 3.13 tu:
echo   https://www.python.org/downloads/release/python-31313/
echo.
echo Hoac neu da co Python install manager:
echo   py install 3.13
echo.
echo Khi cai dat, nho TICH O "Add Python to PATH".
echo.
pause
exit /b 1

:wrong_version
echo.
echo Pipeline yeu cau Python 3.12 hoac 3.13. Cai dat tai:
echo   https://www.python.org/downloads/release/python-31313/
echo Hoac dung Python install manager:
echo   py install 3.13
echo Sau khi cai, dong cua so nay va chay lai run.bat.
echo.
pause
exit /b 1

:venv_failed
echo [ERROR] Khong the tao venv. Kiem tra quyen ghi tai thu muc nay.
pause
exit /b 1

:pip_failed
echo [ERROR] Cai dat phu thuoc that bai. Kiem tra ket noi mang.
pause
exit /b 1

:end
endlocal
