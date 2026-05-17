#!/usr/bin/env bash
# L10 D8 — Mac/Linux one-click launcher.
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo " MACRO FORECAST TERMINAL - One-click Launcher (Mac/Linux)"
echo "============================================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python chưa được cài đặt."
    echo "Hãy cài Python 3.12 hoặc 3.13 từ: https://www.python.org/downloads/"
    exit 1
fi

# L11.1 — validate version range via standalone Python script (single source
# of truth shared with run.bat; avoids fragile shell-level version parsing).
if ! python3 scripts/check_python_version.py; then
    echo
    echo "Pipeline yêu cầu Python 3.12 hoặc 3.13. Cài đặt tại:"
    echo "  https://www.python.org/downloads/"
    exit 1
fi

if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Tạo virtual environment lần đầu..."
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import flask" 2>/dev/null; then
    echo "[INFO] Cài đặt dependencies lần đầu (3-8 phút)..."
    .venv/bin/python -m pip install --upgrade pip --quiet
    .venv/bin/python -m pip install -e . --quiet
    .venv/bin/python -m pip install flask --quiet
fi

if [ ! -f "macro_pipeline/webapp/static/templates/yield-curve.xlsx" ]; then
    echo "[INFO] Tạo Excel templates..."
    .venv/bin/python scripts/generate_excel_templates.py
fi

echo
echo "[INFO] Khởi động Macro Forecast Terminal..."
echo "[INFO] Browser sẽ tự mở tại: http://localhost:8000"
echo

(sleep 3 && (xdg-open http://localhost:8000 2>/dev/null || open http://localhost:8000 2>/dev/null)) &
.venv/bin/python -m macro_pipeline.webapp.app
