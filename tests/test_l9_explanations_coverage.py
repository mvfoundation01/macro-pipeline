"""L9 D2 + D8 — explanation coverage cross-reference tests."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from macro_pipeline.ensemble.registry import load_metrics_registry
from macro_pipeline.ui.explanation_stack import ExplanationLevel, ExplanationStack


REPO_ROOT = Path(__file__).parent.parent
EXPLANATIONS_YAML = REPO_ROOT / "macro_pipeline" / "ui" / "data" / "explanations.yaml"


def test_l9_explanations_coverage_full_registry() -> None:
    """POS-inv: every metric_id in registry has an explanation entry."""
    exp_data = yaml.safe_load(open(EXPLANATIONS_YAML, encoding="utf-8"))
    exp_ids = {e["metric_id"] for e in exp_data["explanations"]}
    registry = load_metrics_registry()
    registry_ids = set(registry.keys())
    missing = registry_ids - exp_ids
    assert not missing, f"L9 D2 coverage gap: {sorted(missing)[:10]}"


def test_l9_explanations_yaml_loads_without_error() -> None:
    """POS: explanations YAML loads via ExplanationStack."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    assert len(stack.metric_ids()) >= 90


def test_l9_explanations_at_least_90_unique_metric_ids() -> None:
    """POS: at least 90 unique metric_ids in explanations.yaml."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    assert len(stack.metric_ids()) >= 90


def test_l9_explanations_each_registry_entry_has_l1() -> None:
    """POS-inv: every registry metric has at least L1 explanation."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    registry = load_metrics_registry()
    missing_l1 = []
    for metric_id in registry:
        if stack.get(metric_id, ExplanationLevel.L1) is None:
            missing_l1.append(metric_id)
    assert not missing_l1, f"Missing L1 coverage: {missing_l1[:5]}"


def test_l9_explanations_each_registry_entry_has_l2() -> None:
    """POS-inv: every registry metric has L2 explanation."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    registry = load_metrics_registry()
    missing = [
        mid for mid in registry
        if stack.get(mid, ExplanationLevel.L2) is None
    ]
    assert not missing, f"Missing L2 coverage: {missing[:5]}"


def test_l9_explanations_each_registry_entry_has_l3() -> None:
    """POS-inv: every registry metric has L3 explanation."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    registry = load_metrics_registry()
    missing = [
        mid for mid in registry
        if stack.get(mid, ExplanationLevel.L3) is None
    ]
    assert not missing, f"Missing L3 coverage: {missing[:5]}"
