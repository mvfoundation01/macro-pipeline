"""Gate 3 combined validation (Yahoo + CFTC TFF)."""
from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("FRED_API_KEY"):
    pytest.skip(
        "FRED_API_KEY not set (required for src.config import)",
        allow_module_level=True,
    )

from src.loaders.cftc_tff_spx import load_cftc_tff_spx
from src.loaders.yahoo_loader import load_yahoo_all
from src.validation import validate_gate3


def test_gate3_passes():
    yh_df, yh_meta = load_yahoo_all()
    cftc_df, cftc_meta = load_cftc_tff_spx()
    report = validate_gate3(yh_df, yh_meta, cftc_df, cftc_meta)
    assert report.passed, "Gate 3 must pass:\n" + report.render()
