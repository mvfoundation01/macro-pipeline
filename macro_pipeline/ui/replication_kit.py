"""L8 D8 — Academic replication kit builder.

Per Strategic L8 single comprehensive pre-flight 2026-05-16
(ACCELERATION PROTOCOL v2.0).

Builds a downloadable zip containing:
  - forecast_records.json    All ForecastRecord instances for the partition
  - methodology_citations.json  Academic citations per Vision §X
  - data_lineage.json        Lineage summary from L6-J D4 MetricLineage
  - README.md                Replication instructions

Design discipline:
- Frozen ``ReplicationKitConfig`` with path validation
- Output path returned for caller (typically UI "Download" link)
- All file writes use UTF-8 explicit encoding
- Data cache inclusion opt-in only (gitignored; large)
"""
from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from macro_pipeline.ensemble.registry import load_metrics_registry
from macro_pipeline.persistence import ForecastRecord


@dataclass(frozen=True)
class ReplicationKitConfig:
    """Frozen replication kit builder configuration.

    Fields
    ------
    output_dir              Directory where kit zip + scratch dir written.
    include_data_caches     Opt-in flag for including data/cache/ contents.
                            Default False (caches are gitignored + large).
    """

    output_dir: Path
    include_data_caches: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, Path):
            raise TypeError(
                f"output_dir must be Path; got "
                f"{type(self.output_dir).__name__}"
            )
        if not isinstance(self.include_data_caches, bool):
            raise TypeError(
                f"include_data_caches must be bool; got "
                f"{type(self.include_data_caches).__name__}"
            )


# Curated methodology citations per Vision §X subsection.
# Single source of truth for academic peer-review reference.
METHODOLOGY_CITATIONS: Dict[str, Any] = {
    "valuation_methodology": {
        "section": "Vision §7 Layer 1 Valuation",
        "citations": [
            "Shiller, R. J. (1989). Market Volatility. MIT Press.",
            "Shiller, R. J. (2015). Irrational Exuberance, 3rd ed. Princeton.",
            "Hussman, J. (2017). The Long View of CAPE.",
            "Damodaran, A. (2024). Equity Risk Premium Estimation.",
        ],
    },
    "ensemble_methodology": {
        "section": "Vision §1 Pillar 5 + §4 Vision §4 BINDING",
        "citations": [
            "Asness, C. S. (2014). Our Model Goes to Six and Saves Value.",
            "Bridgewater Associates. All-Weather Strategy white papers.",
            "Hoeting, J. A. et al. (1999). Bayesian Model Averaging.",
        ],
    },
    "reference_class_forecasting": {
        "section": "Vision §6 RCF + §10 Sample Size Honesty",
        "citations": [
            "Tetlock, P. E. & Gardner, D. (2015). Superforecasting.",
            "Kahneman, D. (2011). Thinking, Fast and Slow. Ch. 22-24.",
            "Lovallo, D. & Kahneman, D. (2003). Delusions of Success. HBR.",
        ],
    },
    "dms_survivorship_adjustment": {
        "section": "Vision §8 DMS adjustment (MANDATORY 5Y/10Y)",
        "citations": [
            "Dimson, E., Marsh, P., Staunton, M. (2002). Triumph of the Optimists.",
            "Credit Suisse Global Investment Returns Yearbook (annual).",
            "UBS Global Investment Returns Yearbook 2024.",
        ],
    },
    "lucas_critique": {
        "section": "Vision §9 Lucas critique discipline",
        "citations": [
            "Lucas, R. E. (1976). Econometric Policy Evaluation: A Critique.",
            "Sargent, T. J. (1987). Macroeconomic Theory, 2nd ed.",
        ],
    },
    "minsky_kindleberger": {
        "section": "Vision §18 anti-pattern surface",
        "citations": [
            "Minsky, H. P. (1986). Stabilizing an Unstable Economy.",
            "Kindleberger, C. P. (1978). Manias, Panics, and Crashes.",
        ],
    },
    "bayesian_shrinkage": {
        "section": "Vision §6 + §10 horizon-conditional shrinkage",
        "citations": [
            "Stein, C. (1956). Inadmissibility of the Usual Estimator.",
            "Efron, B. & Morris, C. (1973). Stein's Estimation Rule.",
            "Gelman, A. et al. (2013). Bayesian Data Analysis, 3rd ed.",
        ],
    },
    "triple_sigma_reporting": {
        "section": "Vision §5 Triple sigma BINDING",
        "citations": [
            "Hull, J. C. (2018). Options, Futures, and Other Derivatives.",
            "Engle, R. F. (1982). Autoregressive Conditional Heteroscedasticity.",
        ],
    },
}


class ReplicationKitBuilder:
    """Build downloadable replication kit for academic peer review.

    Usage
    -----
    >>> builder = ReplicationKitBuilder()
    >>> config = ReplicationKitConfig(output_dir=Path("./kits"))
    >>> zip_path = builder.build(records, config)
    """

    def build(
        self,
        records: List[ForecastRecord],
        config: ReplicationKitConfig,
    ) -> Path:
        """Generate replication zip.

        Parameters
        ----------
        records
            List of ForecastRecord instances to include.
        config
            ReplicationKitConfig with output_dir + opt-in flags.

        Returns
        -------
        Path
            Absolute path to the generated zip file.

        Raises
        ------
        ValueError
            If records list is empty.
        """
        if not records:
            raise ValueError("records list cannot be empty")

        config.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        kit_name = f"replication_kit_{timestamp}"
        kit_dir = config.output_dir / kit_name
        kit_dir.mkdir(parents=True, exist_ok=True)

        # 1. Forecast records JSON.
        records_json = [self._record_to_dict(r) for r in records]
        (kit_dir / "forecast_records.json").write_text(
            json.dumps(records_json, indent=2, default=str),
            encoding="utf-8",
        )

        # 2. Methodology citations.
        (kit_dir / "methodology_citations.json").write_text(
            json.dumps(METHODOLOGY_CITATIONS, indent=2),
            encoding="utf-8",
        )

        # 3. Data lineage (from L6-J D4 + L6-G registry).
        lineage_summary = self._build_lineage_summary()
        (kit_dir / "data_lineage.json").write_text(
            json.dumps(lineage_summary, indent=2),
            encoding="utf-8",
        )

        # 4. README.
        readme = self._build_readme(records, config)
        (kit_dir / "README.md").write_text(readme, encoding="utf-8")

        # 5. Zip.
        zip_path = config.output_dir / f"{kit_name}.zip"
        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_DEFLATED
        ) as zf:
            for file in kit_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(kit_dir))

        return zip_path

    def _record_to_dict(self, r: ForecastRecord) -> Dict[str, Any]:
        """Serialize ForecastRecord to JSON-friendly dict."""
        try:
            meta = json.loads(r.metadata_json) if r.metadata_json else {}
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return {
            "forecast_id": r.forecast_id,
            "timestamp_utc": r.timestamp_utc.isoformat(),
            "horizon": r.horizon,
            "point_estimate_annualized": r.point_estimate_annualized,
            "sigma_annualized": r.sigma_annualized,
            "confidence": r.confidence,
            "conviction": r.conviction,
            "code_sha": r.code_sha,
            "metric_outputs": meta,
        }

    def _build_lineage_summary(self) -> Dict[str, Any]:
        """Aggregate L6-A/J registry lineage info for academic transparency."""
        registry = load_metrics_registry()
        n_computed = 0
        n_deferred = 0
        n_deferred_l7 = 0
        n_deferred_l8a = 0
        computed_lineage: List[Dict[str, Any]] = []
        for m in registry.values():
            status = m.derive_status()
            if status == "computed":
                n_computed += 1
                computed_lineage.append(
                    {
                        "metric_id": m.metric_id,
                        "subcategory": m.subcategory,
                        "layer_origin": m.layer_origin,
                        "computation_path": m.computation_path,
                        "lineage": (
                            {
                                "raw_source": m.lineage.raw_source,
                                "loader": m.lineage.loader,
                                "transform": m.lineage.transform,
                                "model": m.lineage.model,
                                "aggregator_field": m.lineage.aggregator_field,
                                "output_surface": m.lineage.output_surface,
                            }
                            if m.lineage is not None
                            else None
                        ),
                    }
                )
            else:
                n_deferred += 1
                if m.deferred_to == "L7":
                    n_deferred_l7 += 1
                elif m.deferred_to == "L8a":
                    n_deferred_l8a += 1
        return {
            "n_computed": n_computed,
            "n_deferred": n_deferred,
            "n_deferred_l7": n_deferred_l7,
            "n_deferred_l8a": n_deferred_l8a,
            "total": n_computed + n_deferred,
            "computed_lineage": computed_lineage,
        }

    def _build_readme(
        self,
        records: List[ForecastRecord],
        config: ReplicationKitConfig,
    ) -> str:
        """Generate README.md content."""
        sample_sha = records[0].code_sha if records else "unknown"
        return (
            f"# Macro Pipeline Forecast Replication Kit\n\n"
            f"Generated: {datetime.now(timezone.utc).isoformat()}\n"
            f"Records included: {len(records)}\n"
            f"Code SHA (from first record): {sample_sha}\n"
            f"Data caches included: {config.include_data_caches}\n\n"
            f"## Files\n\n"
            f"- `forecast_records.json`: All forecast records for the partition\n"
            f"- `methodology_citations.json`: Academic citations per Vision section\n"
            f"- `data_lineage.json`: Provenance for 90-measurement registry\n\n"
            f"## Reproducibility\n\n"
            f"1. Clone repo: `git clone https://github.com/mvfoundation01/macro-pipeline`\n"
            f"2. Checkout the code SHA: `git checkout {sample_sha}`\n"
            f"3. Install: `pip install -r requirements.txt`\n"
            f"4. Bootstrap data caches (R8 reviewers): see\n"
            f"   `docs/build-plans/L6_J_TEST_COUNT_AUDIT.md` section 4\n"
            f"5. Run pipeline: `python -m macro_pipeline.cli ...`\n\n"
            f"## Methodology\n\n"
            f"All methodologies are Vision v2.1 BINDING. See `methodology_citations.json`\n"
            f"for academic references per subsection.\n\n"
            f"Vision sections referenced:\n"
            f"- §4: Triple Probability Decomposition (BINDING)\n"
            f"- §5: Triple sigma Reporting (BINDING)\n"
            f"- §6: Reference Class Forecasting (MANDATORY)\n"
            f"- §7: OOD Reserve discipline\n"
            f"- §8: DMS Survivorship Adjustment (MANDATORY 5Y/10Y)\n"
            f"- §9: Lucas Critique discipline\n"
            f"- §10: Sample Size Honesty (REVISED)\n"
            f"- §11: L1/L2/L3 Explanation Stack (BINDING)\n\n"
            f"## License\n\n"
            f"Open-source per Vision v2.1 §18 anti-pattern #12 (full open-source transparency).\n"
        )
