"""L10 D1 / L12 D7 / L12 v2 D9+D11 — Home (input form + auto-fetch + local files)."""
from __future__ import annotations

import logging

from flask import Blueprint, render_template

from macro_pipeline.webapp.fred_fetcher import FetchResult, FREDFetcher
from macro_pipeline.webapp.local_data_manager import LocalDataManager
from macro_pipeline.webapp.yfinance_fetcher import YahooFetcher

log = logging.getLogger(__name__)
home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    """Render the input form.

    Injects three independent template contexts:

      * ``detected_files`` / ``local_categories`` — L12 D7 panel listing
        which raw CSVs LocalDataManager picked up.
      * ``auto_fetched``  — L12 v2 D9 dict of ``FetchResult`` per auto field
        (sp500_current / unemployment_rate / payrolls_mom / fed_funds_rate).
        Each entry is ``FetchResult(value=None, as_of=None)`` if the source
        was unavailable; the template then renders the field as manual.
      * ``fred_available`` — bool, True iff ``FRED_API_KEY`` resolved to a
        working client. Drives the "FRED key chưa được set" callout.

    Auto-fetch is best-effort: any fetcher failure leaves the dict entry as
    ``FetchResult.empty()`` and the template renders that field as manual.
    """
    detected: dict = {}
    scan_error: str | None = None
    try:
        detected = LocalDataManager().scan()
    except Exception as exc:
        log.exception("LocalDataManager.scan() failed")
        scan_error = f"{type(exc).__name__}: {exc}"

    local_categories: set[str] = {
        cat
        for cat in ("yield_curve", "credit_spreads", "sentiment")
        if detected.get(cat)
    }

    # ---- L12 v2 D9: auto-fetch on home load ----
    fred_fetcher = FREDFetcher()
    yahoo_fetcher = YahooFetcher()
    auto_fetched: dict[str, FetchResult] = {}
    try:
        auto_fetched.update(fred_fetcher.fetch_all_form_fields())
        auto_fetched.update(yahoo_fetcher.fetch_all_form_fields())
    except Exception:
        log.exception("Auto-fetch on home page failed")

    return render_template(
        "input.html",
        detected_files=detected,
        local_categories=local_categories,
        scan_error=scan_error,
        auto_fetched=auto_fetched,
        fred_available=fred_fetcher.available,
    )
