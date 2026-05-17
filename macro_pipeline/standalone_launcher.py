"""L10 D11 — Standalone PyInstaller entry point.

When packaged with PyInstaller, this module runs inside the frozen exe.
It starts the Flask app + opens browser automatically + relocates the
upload/forecast directories to ``~/.macro_forecast_terminal/`` so the user
doesn't need write access to the exe's install location.
"""
from __future__ import annotations

import contextlib
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _get_resource_path() -> Path:
    """Return path to bundled resources (script-mode and frozen-exe-mode)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).parent.parent


def _open_browser_delayed(delay_seconds: float = 2.0) -> None:
    time.sleep(delay_seconds)
    webbrowser.open("http://localhost:8000")


def main() -> int:
    # L11.2 — Force UTF-8 stdout/stderr so Vietnamese strings print on Windows
    # consoles whose codepage isn't already 65001. run.bat sets the codepage
    # via `chcp 65001 >nul` before launching us, but direct `python -m`
    # invocations (smoke tests, ad-hoc dev runs) inherit the OS default cp1252.
    # `reconfigure` exists in Python 3.7+; errors='replace' rather than 'strict'
    # so an exotic terminal can degrade gracefully instead of crashing on a
    # single un-encodable glyph.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            with contextlib.suppress(Exception):
                stream.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print(" MACRO FORECAST TERMINAL - Standalone")
    print("=" * 60)
    print()
    print("[INFO] Khởi động server...")
    print("[INFO] Browser sẽ tự mở trong 2 giây tại: http://localhost:8000")
    print()
    print("Để dừng: đóng cửa sổ này (Alt+F4 hoặc click X)")
    print()

    threading.Thread(target=_open_browser_delayed, daemon=True).start()

    from macro_pipeline.webapp.app import create_app

    base_dir = Path.home() / ".macro_forecast_terminal"
    base_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(
        {
            "UPLOAD_DIR": base_dir / "uploads",
            "FORECAST_STORE_DIR": base_dir / "forecasts",
            "WEBAPP_RENDER_DIR": base_dir / "forecasts" / "webapp_renders",
        }
    )

    try:
        app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)
    except OSError as exc:
        if "address already in use" in str(exc).lower() or "10048" in str(exc):
            print(
                "[ERROR] Port 8000 đã được sử dụng. "
                "Hãy đóng app khác đang dùng port này rồi thử lại."
            )
        else:
            print(f"[ERROR] {exc}")
        with contextlib.suppress(EOFError):
            input("Nhấn Enter để thoát...")
        return 1
    except KeyboardInterrupt:
        print("\n[INFO] Server đã dừng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
