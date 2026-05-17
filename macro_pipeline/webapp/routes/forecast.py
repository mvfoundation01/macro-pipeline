"""L10 D4 — Forecast orchestration endpoints.

POST /forecast/run        Save uploads + parse + aggregate_ensemble + persist + redirect.
GET  /forecast/template/<name>  Download Excel template (yield-curve / credit-spreads / sentiment).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from macro_pipeline.ensemble.aggregator import aggregate_ensemble
from macro_pipeline.persistence import ForecastRecord, ParquetForecastStore
from macro_pipeline.webapp.data_ingestion import (
    ExcelDataIngester,
    ForecastInputsBuilder,
    IngestionResult,
)
from macro_pipeline.webapp.fred_fetcher import FREDFetcher
from macro_pipeline.webapp.local_data_manager import LocalDataManager
from macro_pipeline.webapp.yfinance_fetcher import YahooFetcher

# L12 v2 D9: which form fields are eligible for auto-fetch fallback when
# the user leaves them blank. Keeps backward-compat with L10/L11 tests that
# POST all 8 fields populated.
_AUTO_FETCH_FIELDS: tuple[str, ...] = (
    "sp500_current",
    "unemployment_rate",
    "payrolls_mom",
    "fed_funds_rate",
)


def _fill_auto_fetch_defaults(
    raw_form: dict[str, str | None],
) -> dict[str, str | None]:
    """Fill missing/empty L12 v2 auto-fetch fields from FRED + Yahoo.

    Returns a new dict with original keys plus auto-fetched substitutes for
    any empty value in ``_AUTO_FETCH_FIELDS``. Manual fields untouched.
    Failure-safe: per-field auto-fetch errors leave the field empty so the
    standard ``_parse_float`` reports the missing-field error to the user.
    """
    out = dict(raw_form)
    auto: dict[str, float | None] = dict.fromkeys(_AUTO_FETCH_FIELDS)
    needs_auto = [
        f for f in _AUTO_FETCH_FIELDS
        if not (out.get(f) or "").strip()
    ]
    if not needs_auto:
        return out
    try:
        fred = FREDFetcher()
        if fred.available:
            for field, result in fred.fetch_all_form_fields().items():
                if field in needs_auto and result.ok:
                    auto[field] = result.value
    except Exception:
        log.exception("FRED auto-fetch fallback failed during /forecast/run")
    try:
        for field, result in YahooFetcher().fetch_all_form_fields().items():
            if field in needs_auto and result.ok:
                auto[field] = result.value
    except Exception:
        log.exception("Yahoo auto-fetch fallback failed during /forecast/run")
    for field in needs_auto:
        if auto[field] is not None:
            out[field] = f"{auto[field]:.4f}"
    return out

log = logging.getLogger(__name__)

forecast_bp = Blueprint("forecast", __name__)

TEMPLATE_FILES = {
    "yield-curve": "yield-curve.xlsx",
    "credit-spreads": "credit-spreads.xlsx",
    "sentiment": "sentiment.xlsx",
}


def _parse_float(raw: str | None, field: str) -> float:
    """Parse form numeric field; raise ValueError with Vietnamese message."""
    if raw is None or raw.strip() == "":
        raise ValueError(f"Trường '{field}' không được để trống.")
    try:
        return float(raw.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Trường '{field}' phải là số (nhận được: {raw!r})."
        ) from exc


def _save_upload(file_storage, upload_dir: Path, prefix: str) -> Path | None:
    """Save a Werkzeug FileStorage to disk; return saved path (or None if empty)."""
    if file_storage is None or not file_storage.filename:
        return None
    safe = secure_filename(file_storage.filename)
    if not safe:
        return None
    target = upload_dir / f"{prefix}_{uuid.uuid4().hex[:8]}_{safe}"
    file_storage.save(str(target))
    return target


def _ingest_or_flash(
    ingester: ExcelDataIngester,
    path: Path | None,
    method_name: str,
    user_label: str,
) -> IngestionResult | None:
    """Run a single ingester method; flash + return None on failure."""
    if path is None:
        return None
    method = getattr(ingester, method_name)
    result = method(path)
    if not result.success:
        flash(
            f"Lỗi khi đọc file {user_label} ({path.name}): {result.error}",
            "error",
        )
        return None
    return result


@forecast_bp.route("/template/<name>")
def template(name: str):
    """Download Excel template by short name."""
    if name not in TEMPLATE_FILES:
        abort(404)
    filename = TEMPLATE_FILES[name]
    template_dir = (
        Path(current_app.static_folder) / "templates"  # type: ignore[arg-type]
    )
    if not (template_dir / filename).exists():
        flash(
            f"File template chưa được tạo: {filename}. Hãy chạy "
            "scripts/generate_excel_templates.py.",
            "error",
        )
        return redirect(url_for("home.index"))
    return send_from_directory(
        template_dir, filename, as_attachment=True
    )


@forecast_bp.route("/run", methods=["POST"])
def run():
    """L10 D4 / L12 v2 D3 — orchestrate forecast end-to-end.

    Wrapped in an outer try/except so a producer / Excel / aggregator failure
    renders the L12 v2 error.html page instead of letting Flask return a
    500-with-traceback (V's browser previously saw "internal server error"
    with no recovery affordance).
    """
    try:
        return _run_impl()
    except HTTPException:
        # 413 RequestEntityTooLarge + friends MUST stay 413 — Flask's default
        # handler turns these into the correct HTTP status code, not 500.
        raise
    except Exception as exc:  # noqa: BLE001 - last-resort recovery
        log.exception("Unexpected error in /forecast/run")
        from flask import render_template
        return render_template(
            "error.html",
            error_type="Internal Error",
            message=(
                f"Đã xảy ra lỗi không mong muốn ({type(exc).__name__}): {exc}. "
                "Xem console log (cửa sổ run.bat) để debug."
            ),
            details=f"{type(exc).__name__}: {exc}",
            recoverable=False,
        ), 500


def _run_impl():
    """The L10 /forecast/run body — extracted so the L12 v2 outer wrapper
    can catch ANY exception and render the friendly error page."""
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    forecast_store_dir = Path(current_app.config["FORECAST_STORE_DIR"])
    webapp_render_dir = Path(current_app.config["WEBAPP_RENDER_DIR"])

    # ---- Step 1: parse + validate numerical inputs ----
    # L12 v2 D9: 4 of the 8 fields are eligible for auto-fetch fallback when
    # the user leaves them blank (the form pre-fills them via the home route
    # auto-fetch, but a blank submit must still produce a usable forecast).
    raw_form = {f: request.form.get(f) for f, _ in (
        ("pmi_manufacturing", ""), ("pmi_services", ""), ("cape_ratio", ""),
        ("sp500_current", ""), ("payrolls_mom", ""), ("unemployment_rate", ""),
        ("core_cpi_yoy", ""), ("fed_funds_rate", ""),
    )}
    raw_form = _fill_auto_fetch_defaults(raw_form)

    field_specs = [
        ("pmi_manufacturing", "PMI Manufacturing"),
        ("pmi_services", "PMI Services"),
        ("cape_ratio", "CAPE Ratio"),
        ("sp500_current", "S&P 500 hiện tại"),
        ("payrolls_mom", "Nonfarm Payrolls MoM"),
        ("unemployment_rate", "Tỷ lệ thất nghiệp"),
        ("core_cpi_yoy", "Core CPI YoY"),
        ("fed_funds_rate", "Lãi suất Fed Funds"),
    ]
    numerical_inputs: dict[str, float] = {}
    try:
        for field, label in field_specs:
            numerical_inputs[field] = _parse_float(
                raw_form.get(field), label
            )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("home.index"))

    horizons_raw = request.form.getlist("horizons")
    horizons: list[int] = []
    for h in horizons_raw:
        try:
            horizons.append(int(h))
        except (TypeError, ValueError):
            continue
    if not horizons:
        horizons = [1, 3, 5, 10]

    # ---- Step 2: save uploaded files ----
    yield_curve_path = _save_upload(
        request.files.get("yield_curve_file"), upload_dir, "yield-curve"
    )
    credit_spreads_path = _save_upload(
        request.files.get("credit_spreads_file"), upload_dir, "credit-spreads"
    )
    sentiment_path = _save_upload(
        request.files.get("sentiment_file"), upload_dir, "sentiment"
    )

    # ---- Step 3: parse Excel uploads ----
    ingester = ExcelDataIngester()
    yield_curve_result = _ingest_or_flash(
        ingester, yield_curve_path, "parse_yield_curve", "yield curve"
    )
    credit_spreads_result = _ingest_or_flash(
        ingester, credit_spreads_path, "parse_credit_spreads", "credit spreads"
    )
    sentiment_result = _ingest_or_flash(
        ingester, sentiment_path, "parse_sentiment", "sentiment"
    )

    # Hard-fail only if all three are missing/failed AND the user uploaded
    # something. (All-None is acceptable — builder uses sensible defaults.)
    any_upload_attempted = (
        yield_curve_path is not None
        or credit_spreads_path is not None
        or sentiment_path is not None
    )
    any_ingest_ok = (
        yield_curve_result is not None
        or credit_spreads_result is not None
        or sentiment_result is not None
    )
    if any_upload_attempted and not any_ingest_ok:
        return redirect(url_for("home.index"))

    # L12 D6 — seed uploaded_data with whatever LocalDataManager auto-detected
    # from data/raw/{official,tradingview}/. Manual Excel uploads OVERRIDE
    # any category they cover (V's intent: a freshly-uploaded file always
    # supersedes the on-disk snapshot of that same category).
    try:
        uploaded_data: dict[str, dict] = LocalDataManager().build_uploaded_data()
    except Exception as exc:
        log.exception("LocalDataManager scan during POST failed")
        flash(
            f"Cảnh báo: không quét được dữ liệu cục bộ ({type(exc).__name__}). "
            "Forecast sẽ chỉ dùng file bạn upload + giá trị form.",
            "info",
        )
        uploaded_data = {}
    if yield_curve_result and yield_curve_result.data:
        uploaded_data["yield_curve"] = yield_curve_result.data
    if credit_spreads_result and credit_spreads_result.data:
        uploaded_data["credit_spreads"] = credit_spreads_result.data
    if sentiment_result and sentiment_result.data:
        uploaded_data["sentiment"] = sentiment_result.data

    # ---- Step 4: build ForecastInputs + run aggregator ----
    builder = ForecastInputsBuilder()
    try:
        forecast_inputs = builder.build(
            uploaded_data=uploaded_data,
            numerical_inputs=numerical_inputs,
            horizons=tuple(horizons),
        )
    except ValueError as exc:
        flash(f"Lỗi khi xây dựng dữ liệu forecast: {exc}", "error")
        return redirect(url_for("home.index"))
    provenance = dict(builder.last_provenance)

    try:
        ensemble_result = aggregate_ensemble(forecast_inputs)
    except Exception as exc:
        log.exception("aggregate_ensemble failed")
        flash(
            f"Lỗi khi chạy aggregator: {type(exc).__name__}: {exc}",
            "error",
        )
        return redirect(url_for("home.index"))

    # ---- Step 5: persist ForecastRecords + render report ----
    forecast_id_prefix = uuid.uuid4().hex[:12]
    now = datetime.now(UTC)
    partition = now.strftime("%Y-%m")
    code_sha = ensemble_result.replication_kit_metadata.get(
        "code_sha", "unknown"
    )

    records: list[ForecastRecord] = []
    for horizon_result in ensemble_result.horizons.values():
        td = horizon_result.triple_decomposition
        ts = horizon_result.triple_sigma
        pe = horizon_result.dms_adjusted_point_estimate
        records.append(
            ForecastRecord(
                forecast_id=f"{forecast_id_prefix}_h{horizon_result.horizon}",
                timestamp_utc=now,
                horizon=horizon_result.horizon,
                point_estimate_annualized=pe,
                sigma_annualized=ts.return_sigma,
                confidence=td.confidence,
                conviction=td.conviction,
                code_sha=code_sha,
                metadata_json=json.dumps(
                    dict(horizon_result.metric_outputs)
                ),
            )
        )

    store = ParquetForecastStore(forecast_store_dir)
    store.append(records)

    # ---- Step 6: render L8 report into webapp_renders dir ----
    from macro_pipeline.ui.renderer import ForecastUIRenderer, UIConfig

    ui_module_dir = Path(__file__).parent.parent.parent / "ui"
    ui_config = UIConfig(
        template_dir=ui_module_dir / "templates",
        static_dir=ui_module_dir / "static",
        output_dir=webapp_render_dir,
        persistence_store=store,
    )
    renderer = ForecastUIRenderer(ui_config)
    report_dir = renderer.render_full_report(partition)

    # L11 D9 — persist provenance alongside the report dir so the results
    # page can show "Producers run / Snapshot date / Fallbacks".
    provenance_path = report_dir / "PROVENANCE.json"
    serializable = {
        k: (list(v) if isinstance(v, tuple) else v)
        for k, v in provenance.items()
    }
    # Convert any tuples-of-tuples (e.g. fallbacks list) to JSON-safe lists.
    if "fallbacks" in serializable:
        serializable["fallbacks"] = [list(f) for f in serializable["fallbacks"]]
    provenance_path.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return redirect(url_for("results.show", partition=partition))
