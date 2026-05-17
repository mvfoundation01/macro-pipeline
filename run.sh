#!/usr/bin/env bash
# L11.2 — Mac/Linux one-click launcher with python3.13 → python3.12 → python3 cascade.
set -e
cd "$(dirname "$0")"

echo "==============================================================="
echo " MACRO FORECAST TERMINAL - One-click Launcher (Unix) [L11.2]"
echo "==============================================================="
echo

# === Phase 1: detect best Python via explicit version cascade ===
PYTHON_CMD=""
PYTHON_DESC=""

if command -v python3.13 >/dev/null 2>&1; then
    PYTHON_CMD="python3.13"
    PYTHON_DESC="Python 3.13 (explicit)"
elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_CMD="python3.12"
    PYTHON_DESC="Python 3.12 (explicit)"
elif command -v python3 >/dev/null 2>&1; then
    # Generic python3 — validate via check script before accepting.
    if python3 scripts/check_python_version.py >/dev/null 2>&1; then
        PYTHON_CMD="python3"
        PYTHON_DESC="python3 (validated)"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "[ERROR] Không tìm thấy Python 3.12 hoặc 3.13."
    echo "Cài Python 3.13 từ: https://www.python.org/downloads/release/python-31313/"
    echo "Trên macOS với Homebrew: brew install python@3.13"
    exit 1
fi

echo "[INFO] Sử dụng: $PYTHON_DESC"
$PYTHON_CMD --version
echo

# === Phase 2: venv + install ===
if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Tạo virtual environment lần đầu..."
    $PYTHON_CMD -m venv .venv
fi

if ! .venv/bin/python -c "import flask" 2>/dev/null; then
    echo "[INFO] Cài đặt dependencies lần đầu (3-8 phút)..."
    .venv/bin/python -m pip install --upgrade pip --quiet
    .venv/bin/python -m pip install -e . --quiet
    # L12 — flask + werkzeug now pulled in by `pip install -e .` via pyproject.toml
fi

if [ ! -f "macro_pipeline/webapp/static/templates/yield-curve.xlsx" ]; then
    echo "[INFO] Tạo Excel templates..."
    .venv/bin/python scripts/generate_excel_templates.py
fi

echo
echo "[INFO] Khởi động Macro Forecast Terminal..."
echo "[INFO] Browser sẽ tự mở tại: http://localhost:8000"
echo

# standalone_launcher opens the browser itself (after 2s), so no need to also
# call xdg-open/open here — would result in duplicate tabs.
.venv/bin/python -m macro_pipeline.standalone_launcher
