"""L8 D9 tests — explanation stack."""
from __future__ import annotations

from pathlib import Path

import pytest

from macro_pipeline.ui.explanation_stack import (
    Explanation,
    ExplanationLevel,
    ExplanationStack,
)


REPO_ROOT = Path(__file__).parent.parent
EXPLANATIONS_YAML = (
    REPO_ROOT / "macro_pipeline" / "ui" / "data" / "explanations.yaml"
)


# ===========================================================================
# Explanation dataclass
# ===========================================================================


def test_explanation_valid() -> None:
    """POS: valid Explanation."""
    e = Explanation(
        metric_id="x",
        level=ExplanationLevel.L1,
        text="example text",
    )
    assert e.metric_id == "x"


def test_explanation_empty_metric_id_raises() -> None:
    """NEG: empty metric_id raises."""
    with pytest.raises(ValueError, match="metric_id"):
        Explanation(
            metric_id="",
            level=ExplanationLevel.L1,
            text="text",
        )


def test_explanation_empty_text_raises() -> None:
    """NEG: empty text raises."""
    with pytest.raises(ValueError, match="text required"):
        Explanation(
            metric_id="x",
            level=ExplanationLevel.L1,
            text="   ",
        )


def test_explanation_non_enum_level_raises() -> None:
    """NEG: non-ExplanationLevel level raises TypeError."""
    with pytest.raises(TypeError, match="ExplanationLevel"):
        Explanation(
            metric_id="x",
            level="L1",  # type: ignore[arg-type]
            text="text",
        )


# ===========================================================================
# ExplanationStack
# ===========================================================================


def test_explanation_stack_loads_real_yaml() -> None:
    """POS: load actual repo explanations.yaml."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    metric_ids = stack.metric_ids()
    assert len(metric_ids) >= 20  # L8 §13 deliverable checklist minimum


def test_explanation_stack_get_l1_confidence() -> None:
    """POS-inv: get L1 for confidence_score."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    exp = stack.get("confidence_score", ExplanationLevel.L1)
    assert exp is not None
    assert exp.metric_id == "confidence_score"
    assert exp.level == ExplanationLevel.L1
    assert exp.text


def test_explanation_stack_get_l3_includes_vision_section() -> None:
    """POS-inv: L3 explanations include vision_section reference."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    exp = stack.get("conviction_score", ExplanationLevel.L3)
    assert exp is not None
    assert exp.vision_section is not None


def test_explanation_stack_get_all_levels() -> None:
    """POS-inv: get_all_levels returns full dict for fully-covered metric."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    levels = stack.get_all_levels("confidence_score")
    assert ExplanationLevel.L1 in levels
    assert ExplanationLevel.L2 in levels
    assert ExplanationLevel.L3 in levels


def test_explanation_stack_missing_metric_returns_none() -> None:
    """POS: unknown metric returns None (graceful)."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    exp = stack.get("totally_made_up_metric", ExplanationLevel.L1)
    assert exp is None


def test_explanation_stack_coverage_counts() -> None:
    """POS-inv: coverage returns per-level counts."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    coverage = stack.coverage()
    assert "L1" in coverage
    assert "L2" in coverage
    assert "L3" in coverage
    assert coverage["L1"] >= 20  # PD18 L8 §13 minimum
    assert coverage["L2"] >= 20
    assert coverage["L3"] >= 20


def test_explanation_stack_missing_file_raises(tmp_path: Path) -> None:
    """NEG: missing YAML file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        ExplanationStack(tmp_path / "nonexistent.yaml")


def test_explanation_stack_malformed_yaml_raises(tmp_path: Path) -> None:
    """NEG: YAML without 'explanations' key raises."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("foo: bar\n", encoding="utf-8")
    with pytest.raises(ValueError, match="explanations"):
        ExplanationStack(bad_yaml)


def test_explanation_stack_non_list_explanations_raises(tmp_path: Path) -> None:
    """NEG: explanations not a list raises."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("explanations: not_a_list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="list"):
        ExplanationStack(bad_yaml)


def test_explanation_stack_non_mapping_root_raises(tmp_path: Path) -> None:
    """NEG: YAML root not a mapping raises."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        ExplanationStack(bad_yaml)


def test_explanation_stack_loads_22_plus_metric_ids() -> None:
    """POS: at least 22 unique metric IDs covered (per Strategic L8 minimum)."""
    stack = ExplanationStack(EXPLANATIONS_YAML)
    assert len(stack.metric_ids()) >= 22
