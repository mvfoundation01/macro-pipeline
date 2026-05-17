"""L7 alerting module skeleton.

Created at L6-K (2026-05-16) per ACCELERATION PROTOCOL v1.0 D7 pre-staging.
Empty stub at L6-K; populated at L7 single sub-phase per Strategic mandate.

Planned L7 scope (see docs/build-plans/L7_ARCHITECTURE_SKETCH.md):
- Detection logic: regime shift, threshold breach, OOD event
- Dispatch backends: email, Slack, webhook
- Alert severity tiers + reason codes (mirrors Vision §9 Lucas + §7 OOD
  reason-code disciplines from L6)
- Integration with macro_pipeline.scheduler for trigger-time evaluation

No functional code at L6-K. Importing from this module at L6-K returns
an empty namespace; L7 will populate this surface.
"""
from __future__ import annotations

__all__: list[str] = []
