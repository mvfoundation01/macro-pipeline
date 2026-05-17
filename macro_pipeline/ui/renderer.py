"""L8 D1 — Main UI renderer orchestrating all forecast pages.

Per Strategic L8 single comprehensive pre-flight 2026-05-16.

Renders forecast results from L7 ``ParquetForecastStore`` into HTML
dark financial terminal pages. Eight pages total:
  - forecast_results.html (D2)
  - macro_snapshot.html (D3)
  - scenarios.html (D4)
  - drawdown_risk.html (D5)
  - analogs.html (D6)
  - sector_factor.html (D7)
  - academic/index.html (D8)
  - educational/index.html (D9)

Design discipline:
- Jinja2 templates with autoescape for XSS safety
- Frozen ``UIConfig`` with path validation
- NaN-safe number formatting filters (return "N/A")
- Defense-in-depth: UI module is purely consumer of L7 persistence;
  no direct invocation of ``aggregate_ensemble`` (caller orchestrates)
"""
from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from macro_pipeline.persistence import ForecastRecord, ParquetForecastStore


def _pct_filter(x: Any) -> str:
    """Format as percent with +/- sign; return 'N/A' on None/NaN/non-numeric."""
    if x is None:
        return "N/A"
    try:
        f = float(x)
    except (TypeError, ValueError):
        return "N/A"
    if not math.isfinite(f):
        return "N/A"
    return f"{f * 100:+.2f}%"


def _bps_filter(x: Any) -> str:
    """Format as basis points with +/- sign; return 'N/A' on None/NaN."""
    if x is None:
        return "N/A"
    try:
        f = float(x)
    except (TypeError, ValueError):
        return "N/A"
    if not math.isfinite(f):
        return "N/A"
    return f"{f:+.0f} bps"


def _num_filter(x: Any, digits: int = 2) -> str:
    """Format as fixed-decimal number; return 'N/A' on None/NaN."""
    if x is None:
        return "N/A"
    try:
        f = float(x)
    except (TypeError, ValueError):
        return "N/A"
    if not math.isfinite(f):
        return "N/A"
    return f"{f:,.{digits}f}"


def _signed_class_filter(x: Any) -> str:
    """Return CSS class 'bullish' / 'bearish' / 'neutral' based on sign."""
    if x is None:
        return "neutral"
    try:
        f = float(x)
    except (TypeError, ValueError):
        return "neutral"
    if not math.isfinite(f):
        return "neutral"
    if f > 0:
        return "bullish"
    if f < 0:
        return "bearish"
    return "neutral"


@dataclass(frozen=True)
class UIConfig:
    """Frozen UI renderer configuration.

    Fields
    ------
    template_dir          Path to Jinja2 templates root.
    static_dir            Path to static assets (CSS/JS).
    output_dir            Path where rendered HTML reports written.
    persistence_store     ParquetForecastStore for forecast records.

    Invariants:
      - template_dir, static_dir exist on construction
      - output_dir created if missing (writable)
    """

    template_dir: Path
    static_dir: Path
    output_dir: Path
    persistence_store: ParquetForecastStore

    def __post_init__(self) -> None:
        for fname in ("template_dir", "static_dir"):
            path = getattr(self, fname)
            if not isinstance(path, Path):
                raise TypeError(
                    f"{fname} must be Path; got {type(path).__name__}"
                )
            if not path.exists():
                raise ValueError(f"{fname} does not exist: {path}")
            if not path.is_dir():
                raise ValueError(f"{fname} must be a directory: {path}")
        if not isinstance(self.output_dir, Path):
            raise TypeError(
                f"output_dir must be Path; got "
                f"{type(self.output_dir).__name__}"
            )
        if not isinstance(self.persistence_store, ParquetForecastStore):
            raise TypeError(
                f"persistence_store must be ParquetForecastStore; got "
                f"{type(self.persistence_store).__name__}"
            )


class ForecastUIRenderer:
    """Render forecast outputs as HTML dark financial terminal pages.

    Usage
    -----
    >>> store = ParquetForecastStore(Path("./forecasts"))
    >>> config = UIConfig(
    ...     template_dir=Path("./templates"),
    ...     static_dir=Path("./static"),
    ...     output_dir=Path("./reports"),
    ...     persistence_store=store,
    ... )
    >>> renderer = ForecastUIRenderer(config)
    >>> output_path = renderer.render_full_report("2026-05")
    """

    def __init__(self, config: UIConfig) -> None:
        self.config = config
        self._env = Environment(
            loader=FileSystemLoader(str(config.template_dir)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.filters["pct"] = _pct_filter
        self._env.filters["bps"] = _bps_filter
        self._env.filters["num"] = _num_filter
        self._env.filters["signed_class"] = _signed_class_filter
        # L9 D5 performance: template cache for repeated renders.
        self._template_cache: dict[str, Any] = {}

    def _get_template_cached(self, template_name: str) -> Any:
        """L9 D5 — Cached template lookup; avoids repeated FileSystemLoader hits."""
        if template_name not in self._template_cache:
            self._template_cache[template_name] = self._env.get_template(template_name)
        return self._template_cache[template_name]

    def render_full_report(self, partition: str) -> Path:
        """Render all 8 pages for a given month partition.

        Parameters
        ----------
        partition
            Month partition as ``"YYYY-MM"``.

        Returns
        -------
        Path
            Directory containing rendered HTML report (index.html + pages
            + static/).

        Raises
        ------
        ValueError
            If partition has no records in the persistence store.
        """
        records = self.config.persistence_store.read(partition)
        if not records:
            raise ValueError(
                f"No records found for partition {partition!r}"
            )

        # Parse metadata_json into dict for template access.
        parsed_records: List[Dict[str, Any]] = []
        for r in records:
            try:
                meta = json.loads(r.metadata_json) if r.metadata_json else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            parsed_records.append(
                {
                    "forecast_id": r.forecast_id,
                    "timestamp_utc": r.timestamp_utc,
                    "horizon": r.horizon,
                    "point_estimate_annualized": r.point_estimate_annualized,
                    "sigma_annualized": r.sigma_annualized,
                    "confidence": r.confidence,
                    "conviction": r.conviction,
                    "code_sha": r.code_sha,
                    "metric_outputs": meta,
                }
            )

        generated_at = datetime.now(timezone.utc).isoformat()
        common_ctx = {
            "partition": partition,
            "generated_at": generated_at,
            "records": parsed_records,
        }

        output_path = self.config.output_dir / f"report_{partition}"
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "academic").mkdir(exist_ok=True)
        (output_path / "educational").mkdir(exist_ok=True)

        # Render all pages.
        page_template_pairs = [
            ("index.html", "index.html"),
            ("forecast_results.html", "forecast_results.html"),
            ("macro_snapshot.html", "macro_snapshot.html"),
            ("scenarios.html", "scenarios.html"),
            ("drawdown_risk.html", "drawdown_risk.html"),
            ("analogs.html", "analogs.html"),
            ("sector_factor.html", "sector_factor.html"),
            ("academic/index.html", "academic/index.html"),
            ("educational/index.html", "educational/index.html"),
        ]
        for template_name, output_name in page_template_pairs:
            tmpl = self._get_template_cached(template_name)  # L9 D5 cache
            html = tmpl.render(**common_ctx)
            (output_path / output_name).write_text(html, encoding="utf-8")

        # Copy static assets.
        static_target = output_path / "static"
        if static_target.exists():
            shutil.rmtree(static_target)
        shutil.copytree(self.config.static_dir, static_target)

        return output_path
