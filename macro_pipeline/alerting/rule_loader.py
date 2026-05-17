"""L7 D6 — Alert rule YAML loader + evaluator.

Per Strategic L7 pre-flight 2026-05-16. Declarative rule schema in
``config/alert_rules.yaml`` consumed via ``load_alert_rules`` to
produce typed ``AlertRule`` instances; ``evaluate_rule_against_payload``
applies a single rule to a flat metric payload.

Operators supported (controlled vocabulary):
  ``>``  greater than (numeric)
  ``>=`` greater-or-equal (numeric)
  ``<``  less than (numeric)
  ``<=`` less-or-equal (numeric)
  ``==`` equality (any type)
  ``!=`` inequality (any type)

Threshold semantics: numeric operators use ``threshold`` field; equality
operators use ``value`` field (can be bool / str / number).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from macro_pipeline.alerting.alert_dispatcher import AlertSeverity


VALID_OPERATORS = frozenset({">", ">=", "<", "<=", "==", "!="})
NUMERIC_OPERATORS = frozenset({">", ">=", "<", "<="})
EQUALITY_OPERATORS = frozenset({"==", "!="})
VALID_ADAPTER_NAMES = frozenset({"email", "slack", "webhook"})


@dataclass(frozen=True)
class AlertRuleTrigger:
    """Trigger condition for an alert rule."""

    field: str
    operator: str
    horizon: Optional[int] = None
    threshold: Optional[float] = None
    value: Optional[Any] = None

    def __post_init__(self) -> None:
        if not self.field:
            raise ValueError("trigger.field must be non-empty")
        if self.operator not in VALID_OPERATORS:
            raise ValueError(
                f"trigger.operator {self.operator!r} not in "
                f"{sorted(VALID_OPERATORS)}"
            )
        if self.horizon is not None and self.horizon not in (1, 3, 5, 10):
            raise ValueError(
                f"trigger.horizon {self.horizon} not in (1, 3, 5, 10)"
            )
        if self.operator in NUMERIC_OPERATORS:
            if self.threshold is None:
                raise ValueError(
                    f"numeric operator {self.operator!r} requires "
                    f"trigger.threshold"
                )
            if not math.isfinite(self.threshold):
                raise ValueError(
                    f"trigger.threshold must be finite; got "
                    f"{self.threshold!r}"
                )
        if self.operator in EQUALITY_OPERATORS:
            if self.value is None and self.threshold is None:
                raise ValueError(
                    f"equality operator {self.operator!r} requires "
                    f"trigger.value (or .threshold for numerics)"
                )


@dataclass(frozen=True)
class AlertRule:
    """A single declarative alert rule loaded from YAML."""

    rule_id: str
    description: str
    trigger: AlertRuleTrigger
    severity: AlertSeverity
    adapters: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("rule_id required")
        if not isinstance(self.severity, AlertSeverity):
            raise TypeError(
                f"severity must be AlertSeverity; got "
                f"{type(self.severity).__name__}"
            )
        if not self.adapters:
            raise ValueError(f"rule {self.rule_id!r} adapters list empty")
        for adapter_name in self.adapters:
            if adapter_name not in VALID_ADAPTER_NAMES:
                raise ValueError(
                    f"rule {self.rule_id!r} adapter {adapter_name!r} "
                    f"not in {sorted(VALID_ADAPTER_NAMES)}"
                )


def load_alert_rules(path: Union[str, Path]) -> List[AlertRule]:
    """Load alert rules from a YAML file.

    Parameters
    ----------
    path
        Path to ``alert_rules.yaml`` file.

    Returns
    -------
    list[AlertRule]
        List of validated AlertRule instances. Order preserved from YAML.

    Raises
    ------
    FileNotFoundError
        If path does not exist.
    ValueError
        If schema_version missing or unsupported, or any rule invalid.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Alert rules file not found: {p}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(
            f"Alert rules YAML root must be mapping; got "
            f"{type(raw).__name__}"
        )
    schema_version = raw.get("schema_version")
    if schema_version != "v1":
        raise ValueError(
            f"Unsupported schema_version: {schema_version!r} (expected 'v1')"
        )
    rules_raw = raw.get("rules", [])
    if not isinstance(rules_raw, list):
        raise ValueError(
            f"rules must be list; got {type(rules_raw).__name__}"
        )

    rules: List[AlertRule] = []
    for rule_dict in rules_raw:
        if not isinstance(rule_dict, dict):
            raise ValueError(
                f"each rule must be mapping; got "
                f"{type(rule_dict).__name__}"
            )
        trigger_dict = rule_dict.get("trigger", {})
        if not isinstance(trigger_dict, dict):
            raise ValueError("rule.trigger must be mapping")
        trigger = AlertRuleTrigger(
            field=trigger_dict.get("field", ""),
            operator=trigger_dict.get("operator", ""),
            horizon=trigger_dict.get("horizon"),
            threshold=trigger_dict.get("threshold"),
            value=trigger_dict.get("value"),
        )
        severity_str = rule_dict.get("severity", "info")
        try:
            severity = AlertSeverity(severity_str)
        except ValueError as e:
            raise ValueError(
                f"rule {rule_dict.get('rule_id', '?')!r} invalid "
                f"severity {severity_str!r}"
            ) from e
        rule = AlertRule(
            rule_id=rule_dict.get("rule_id", ""),
            description=rule_dict.get("description", ""),
            trigger=trigger,
            severity=severity,
            adapters=list(rule_dict.get("adapters", [])),
        )
        rules.append(rule)
    return rules


def evaluate_rule_against_payload(
    rule: AlertRule,
    payload: Dict[str, Any],
    *,
    horizon: Optional[int] = None,
) -> bool:
    """Evaluate a single AlertRule against a flat metric payload.

    Returns True if the rule's trigger condition is met by the payload.

    Parameters
    ----------
    rule
        AlertRule instance.
    payload
        Flat dict of metric_id → value (e.g., HorizonResult.metric_outputs).
    horizon
        Current horizon being evaluated; rule's ``trigger.horizon`` (if
        set) must match this for evaluation to proceed.

    Returns
    -------
    bool
        True if condition met; False otherwise.
    """
    trigger = rule.trigger
    if trigger.horizon is not None and trigger.horizon != horizon:
        return False
    if trigger.field not in payload:
        return False
    actual = payload[trigger.field]
    op = trigger.operator

    if op == ">":
        return actual > trigger.threshold
    if op == ">=":
        return actual >= trigger.threshold
    if op == "<":
        return actual < trigger.threshold
    if op == "<=":
        return actual <= trigger.threshold
    if op == "==":
        expected = trigger.value if trigger.value is not None else trigger.threshold
        return actual == expected
    if op == "!=":
        expected = trigger.value if trigger.value is not None else trigger.threshold
        return actual != expected
    return False
