"""Layer 5-B Task B1 — Ridge return-forecast regression.

Spec ref: ``LAYER_5_BUILD_SPEC.md`` v6 @ ``9f848bb`` §5.B.1.0 (task split v3
per S-9) + §5.B.1.1 (public API; lines 631-722) + §5.B.1.2/.3/.4 (nested
walk-forward CV + HAC SE + block bootstrap) + §5.B.5.B (13 tests v3) +
§5.B.6 (Gate 19 sub-criteria 8-14 + 19-22) + §5.B.7 (proof contract 1, 6-9,
12-14). Closes S-9 RETURN_POSITIVE circularity (resolution: Task B1 does
NOT consume ``positive_return_probability`` — it is downstream output of
Task B2). Closes ChatGPT v2 §D.2.

Public API
----------
``RidgeFitResult``                 Frozen dataclass; one fit per (horizon × schedule × fold).
``fit_return_forecast_task_b1``    Task B1's public entry point.
``LAMBDA_GRID_DEFAULT``            Re-exported from ``composite_refit`` for spec proof item 3 alignment.
``BOOTSTRAP_ITERATIONS_DEFAULT``   B=1000 per spec §5.B.1.4.

Method (per spec §5.B.3)
------------------------
* Estimator: closed-form Ridge ``β̂ = (X'X + λI)⁻¹X'y``; ``α̂ = ȳ − β̂x̄``.
* Outer loop: ``schedule.folds`` (L5-A walk-forward).
* Inner loop: time-ordered contiguous blocks (``inner_fold_count=5``)
  WITHOUT contamination gap for λ selection (mirrors Task A inner-CV
  policy at ``composite_refit.py:23-37``; outer CV preserves OOS integrity
  via ``gap_months``).
* Feature standardization: train-only z-score per spec §2.5 audit #5
  (recomputed per fold; never reused across folds).
* HAC SE: ``analysis.newey_west_hac.fit_ols_hac`` with
  ``maxlags = horizon_months − 1`` (spec §5.B.1.3); bandwidth sensitivity
  at ``{horizon_months − 1, Andrews, max(2, horizon_months // 4)}``.
* Block bootstrap: B=1000 with ``block_size = horizon_months // 2``;
  sensitivity at ``{h/4, h/2, h, 2h}`` (spec §5.B.1.4).

Inputs (per spec §5.B.1.1)
--------------------------
* ``schedule`` — ``WalkForwardSchedule`` (L5-A output for ONE horizon ×
  schedule_type pair).
* ``crps_calibrated_panel`` — ``pd.DataFrame`` with one calibrated CRPS
  probability column indexed by month (post-RM-6 CRPS isotonic output).
* ``cdrs_calibrated_panel`` — ``pd.DataFrame`` with twenty calibrated CDRS
  probability columns (4 horizons × 5 thresholds) indexed by month
  (post-RM-6 CDRS isotonic output).
* ``macro_features`` — ``pd.DataFrame`` of exogenous valuation / real-rate
  features indexed by month (the regression covariates beyond the
  calibrated probabilities).
* ``forward_returns`` — ``pd.Series`` of forward real total returns
  on ``PRIMARY_REGRESSION_TARGET = "SHILLER_TR_PRICE"`` aligned to
  ``schedule.horizon`` (produced upstream by
  ``analysis.regression_target.forward_return_series``).

**``positive_return_probability`` / RETURN_POSITIVE column is REJECTED**
by input schema validation: Task B1 produces the return forecast that
Task B2 then calibrates into ``positive_return_probability`` — including
it as a B1 input would re-introduce the ChatGPT v2 §D.2 circularity that
S-9 resolved. The AST-audit test
``test_task_b1_does_not_consume_return_positive_calibrated_probability``
(promoted from §5.B.5.B2 per D-B1-3 disposition) enforces this contract.

File-location note (D-B1-1 Strategic disposition 2026-05-13)
-----------------------------------------------------------
Spec proof contract item 1 references ``macro_pipeline.models.ridge_cv``;
this module lives at ``macro_pipeline.models.return_forecast`` to mirror
Task A's noun-based naming precedent (``composite_refit.py``) and keep
the two L5-B estimator families in sibling modules. The wording drift is
tracked in ``L5B_BACKLOG.md`` as ``L5b-7`` (doc-only); zero functional
impact.

L5b-A (tag ``l5b-a-accept``, 2026-05-15) — stationary block bootstrap
---------------------------------------------------------------------
**FIRST original OOS hardening sub-phase post-kickoff sprint.** Closes
ChatGPT 5.5 Dim-3 OOS rigor mandate + build plan §3.1 L5b-A scope
("Replace fixed block bootstrap in L5-B1 with stationary block
bootstrap. Add geometric-block-length sampler.") via the AP-AUTH-54
fourth-instance internal-implementation variant pattern (heavy
envelope after KICK-4 reference):

* ``_sample_stationary_block_lengths`` NEW helper (Politis-Romano
  1994). Draws block lengths from ``Geometric(1/mean_block_length)``
  with the memoryless property; sums until cumulative >=  ``n_obs``;
  caller truncates. Reference: Politis & Romano (1994) "The
  Stationary Bootstrap" JASA 89:1303-1313.
* ``_block_bootstrap_residual_se`` body refactored from fixed-block
  to stationary sampling. Each bootstrap iteration: (1) draws
  geometric block lengths via ``_sample_stationary_block_lengths``;
  (2) draws uniform start indices on ``{0, ..., n_train-1}``; (3)
  assembles blocks with cyclic wrapping (``residuals[(s + j) %
  n_train]``); (4) truncates concatenated series to ``n_train``;
  (5) refits Ridge with same ``lambda_star``; (6) computes
  bootstrap-sample SE. The pre-L5b-A fixed-block sampling is
  replaced entirely (correctness fix per Politis-Romano institutional
  default, not a policy choice).
* ``BootstrapDiagnostics`` extended with seventh no-default field
  ``block_length_distribution: Literal["fixed", "geometric"]`` per
  AP-AUTH-54 step #2. Field count expansion via the 1-field-vs-2-field
  envelope discussion (Strategic disposition 3 APPROVED the 1-field
  variant superseding §3.4 2-field proposal): ``block_size`` field
  retains polymorphic semantic per the discriminator — for
  ``"fixed"`` it is the exact block length; for ``"geometric"`` it is
  the geometric distribution mean parameter. Documented in
  ``BootstrapDiagnostics`` field comment + class docstring.
* Fallback-flag taxonomy preserved by construction (integer
  floor-division ``n_train // block_size`` invariant across fixed ↔
  geometric variants per ITEM 6 of L5b-A read-and-plan). K5.4 test
  (KICK-5 sensitivity-sweep "2h" fallback "B_halved" verification)
  survives verbatim post-L5b-A; no test recalibration needed.
* R1 SE-drift empirical evidence (pre-flight ITEM 2 snapshot + Phase
  6 post-refactor re-snapshot at 5Y/expanding, B=50, fold 0..4 SE
  means):

    PRE-refactor (fixed-block):   [0.129,   0.099,   0.193,   0.154,   0.237]
    POST-refactor (stationary):   [0.12876, 0.09842, 0.19391, 0.15431, 0.23558]
    Ratio (post / pre):           [0.998,   0.994,   1.005,   1.002,   0.994]

  Post-refactor SE values within 1% of pre-refactor baseline (well
  inside Strategic §6 ±20% tolerance band). On this AR-noise-
  dominated synthetic fixture the methodological change is small;
  on real time-series data with stronger serial dependence the
  stationary variant's correctness advantage will be more
  pronounced.
* Gate 19-B1 extension: criteria 30-32 (L5b-A NEW) verify (i)
  ``block_length_distribution`` no-default field via Option Y
  signature inspection; (ii) AST audit on
  ``_block_bootstrap_residual_se`` body confirms
  ``_sample_stationary_block_lengths`` invocation; (iii) runtime
  probe confirms every fold has ``block_length_distribution ==
  "geometric"``.

**AP-AUTH-54 envelope characterization (4 instances)**: KICK-4
heaviest (helper refactor + field + AST audit) / KICK-5 medium
(tuple-return helper + dual fields + probe) / KICK-6 lightest
(dataclass discipline only) / **L5b-A heavy** (helper refactor +
field + AST audit + runtime probe — comparable to KICK-4 reference
weight; closes the envelope range with this 4th instance).

AP-AUTH-54 cited as governing pattern (fourth instance; first
original OOS hardening sub-phase post-kickoff). No new AP-AUTH
codification at L5b-A.

L5b-KICK-6 (tag ``l5b-kick-6-accept``, 2026-05-15) — inference labeling
-----------------------------------------------------------------------
Closes the ChatGPT 5.5 IMPORTANT #5 reviewer flag ("Separate Ridge
forecast inference from feature significance. Regularized coefficients
do not support naive per-feature inference. Ridge return p-values are
necessarily proxy diagnostics, not coefficient-level inferential
p-values for every feature.") via the AP-AUTH-53 sixth instance /
AP-AUTH-54 third internal-implementation variant pattern (lightest-
weight envelope: dataclass discipline only, no helper refactor):

* **Sxx-18 NOT triggered** (verified at read-and-plan ITEM 0).
  Empirical evidence chain: ``return_forecast.py:998-1005`` calls
  ``fit_ols_hac(y_test, forecast_test, ...)`` (univariate forecast-
  vs-realized regression); ``newey_west_hac.py:48`` docstring
  unambiguously states "Fit y = alpha + beta * x + eps with
  Newey-West HAC SE" (single-x regression). The
  ``p_value_beta_hac`` field IS the slope p-value of this calibration
  regression, NOT a Ridge per-feature coefficient inference statistic.
  Reviewer's interpretation correct; KICK-6 scope is labeling clarity
  (not algorithm correction).
* **Misleading docstring rewritten**: pre-KICK-6 line 324 inline
  comment said "ridge fits y on full X — use overall F-test p
  surrogate" — both misleading (Ridge doesn't admit per-feature
  p-values; no F-test surrogate is computed). Rewritten to explicitly
  cite the univariate forecast-vs-realized regression and disclaim
  Ridge coefficient inference. K6.2 POS-invariant test pins the
  rewrite via source-substring inspection.
* **``InferenceLabel`` tri-state Literal**:
    - ``"forecast_vs_realized"`` — institutionally correct label for
      Ridge fits in this module; default post-KICK-6.
    - ``"feature_significance"`` — per-feature coefficient inference;
      reserved for future OLS variants where standard sampling theory
      applies.
    - ``"diagnostic_only"`` — reported as illustrative but not
      statistically inferential.
* **First ``__post_init__`` on ``RidgeFitResult``**: tri-state
  validation enforced at construction time. Mirrors KICK-3
  ``BinDiagnosticStatus`` + KICK-5 ``BootstrapDiagnostics`` validator
  precedents. Frozen-dataclass compatibility verified (validator is
  read-only; no ``object.__setattr__`` calls).
* **AP-AUTH-54 lightest-weight envelope variance**: KICK-6 does not
  refactor any helper (step #1 N/A); the entire AP-AUTH-54 mechanism
  is satisfied via steps #2-4 (no-default field + Option Y gate
  inspection + pre-flight empirical evidence). Strategic confirmed
  this is within the natural AP-AUTH-54 envelope; no sub-variant
  codification needed. KICK-4 was the heaviest instance (helper
  refactor + field + AST audit); KICK-5 was medium (tuple-return
  helper + dual fields + probe); KICK-6 is the lightest.
* **Gate 19-B1 extension**: criteria 28-29 (KICK-6 NEW) verify (i)
  ``inference_label`` no-default field via Option Y signature
  inspection; (ii) runtime probe confirms every fold has
  ``inference_label == "forecast_vs_realized"``.

AP-AUTH-54 cited as governing pattern (third instance after KICK-4 +
KICK-5; lightest-weight envelope variance documented inline). No new
AP-AUTH codification at KICK-6.

L5b-KICK-5 (tag ``l5b-kick-5-accept``, 2026-05-15) — bootstrap diagnostics
--------------------------------------------------------------------------
Closes the ChatGPT 5.5 IMPORTANT #6 reviewer flag ("Add a bootstrap
diagnostics table. Per horizon/fold: n_train, n_eff, block_size,
block_count, B_effective, fallback flag. Edge-case fallback matters
most at 10Y.") via the AP-AUTH-53 fifth-instance / AP-AUTH-54 internal-
implementation variant (AP-AUTH-54 codified at this commit; second
internal-implementation variant after KICK-4):

* ``BootstrapDiagnostics`` NEW frozen dataclass with six no-default
  fields: ``n_train``, ``n_eff``, ``block_size``, ``block_count``,
  ``B_effective``, ``fallback_flag``. The ``__post_init__`` validator
  enforces the tri-state ``Literal`` taxonomy
  ``{"none", "B_halved", "bs1_degenerate"}`` (mirrors KICK-3
  ``BinDiagnosticStatus`` validator pattern).
* ``_block_bootstrap_residual_se`` return type changed from
  ``np.ndarray`` to ``tuple[np.ndarray, BootstrapDiagnostics]``. The
  helper now tracks ``fallback_flag`` through its control flow and
  emits a populated diagnostics instance on every call (including the
  ``len(y_test) < 2`` edge case where ``B_effective=0``).
  ``horizon_months`` is a new required keyword-only argument used to
  compute ``BootstrapDiagnostics.n_eff = n_train // horizon_months``.
* ``_compute_block_size_sensitivity`` return type changed from
  ``dict[str, float]`` to
  ``tuple[dict[str, float], dict[str, BootstrapDiagnostics]]``. Each
  sensitivity-block-size key carries its own diagnostics, exposing the
  reviewer-flagged sensitivity-sweep fallback surface ("sensitivity
  settings can hit low block counts and fall back").
* ``RidgeFitResult`` gains two no-default fields per AP-AUTH-54 step
  #2: ``bootstrap_diagnostics`` (primary call) and
  ``block_size_sensitivity_diagnostics`` (per-sensitivity-block-size
  dict). Bare construction without these fields raises ``TypeError``.
* L5-D scope-out (Strategic-confirmed at ITEM 0a): the reviewer
  concern explicitly targets BLOCK bootstrap edge-case fallback
  ("block bootstrap primary sizing", "block counts"). L5-D's
  ``_bootstrap_threshold_se`` is a BLOCK-FREE residual bootstrap with
  no ``block_size`` / ``block_count`` / fallback semantics; applying
  the diagnostics dataclass there would be ceremonial. Gate 23 NOT
  extended at KICK-5.
* Empirical evidence (captured in pre-flight ITEM 0b + commit-time
  K5.4 test): at 5Y/expanding with B=10, the ``"2h"`` sensitivity
  block size (= 120 months) triggers ``"B_halved"`` fallback on all
  10 folds (block_count = 2 at every fold). KICK-5 makes this state
  explicit in ``block_size_sensitivity_diagnostics["2h"]
  .fallback_flag``.
* Gate 19-B1 extension: criteria 25-27 (KICK-5 NEW) verify (i) both
  KICK-5 fields no-default via Option Y signature inspection, (ii)
  ``BootstrapDiagnostics`` six-field schema, (iii) runtime probe
  synthesizes a fit and confirms primary + sweep diagnostics
  populated with valid tri-state ``fallback_flag``.

AP-AUTH-54 codified at this commit (second internal-implementation
variant after KICK-4; pattern repeats → codify, mirroring AP-AUTH-53
codification at KICK-2).

L5b-KICK-4 (tag ``l5b-kick-4-accept``, 2026-05-15) — inner-CV scaler purity
--------------------------------------------------------------------------
Closes the Codex 5.5 IMPORTANT reviewer flag ("L5-B1: Recompute z-score
scalers inside inner λ CV blocks, matching Task A's pattern. Inner λ
selection receives outer-train-z-scored data and does not recompute
scalers inside inner blocks. This does not leak outer test data, but
it weakens nested-CV purity.") via the AP-AUTH-53 reviewer-driven-
kickoff-item pattern (fourth instance):

* **Internal-implementation variant** (Strategic disposition
  2026-05-15): KICK-4 modifies an internal nested-CV helper, not a
  public production boundary like KICK-2 (forecast σ) or KICK-3
  (Brier reliability). The wrapper-pattern that KICK-2/-3 used does
  not apply here. Instead, the AP-AUTH-53 mechanism is satisfied via
  (a) in-place refactor of the private helper
  ``_select_lambda_inner_cv_ridge`` and (b) a no-default field
  ``inner_cv_scaler_recomputed: bool`` on ``RidgeFitResult`` that
  exposes the post-refactor invariant for downstream gating. If this
  internal-implementation variant repeats at KICK-5+, Strategic will
  codify it as AP-AUTH-54.
* **Refactor (Phase 2)**: ``_select_lambda_inner_cv_ridge`` now
  receives the RAW (un-z-scored) ``X_train`` and re-fits a fresh
  z-scaler on each inner-train slice via
  ``_zscore_fit_transform(X_tr_raw)``, applying the resulting
  statistics to the inner-test slice via ``_zscore_transform``. This
  mirrors Task A's pattern at ``composite_refit.py:177-178`` exactly.
  Pre-KICK-4 the helper received pre-z-scored ``X_train_z`` and
  reused outer-train statistics across inner blocks — methodologically
  impure (no test contamination, but inner-CV statistics computed on
  a superset of inner-train).
* **Outer Ridge fit unchanged**: ``X_train_z`` and ``X_test_z`` at
  the outer-CV scope still use the outer-train scaler statistics
  ``(mean_tr, std_tr)`` per spec §2.5 audit #5. The K4.3 structural
  invariant test verifies this provenance.
* **Pre-vs-post λ delta** (empirically captured at Phase 4):
  ``lambda_selected`` UNCHANGED across 396 synthetic-fixture folds
  (all bind at grid-edge λ=100.0 both pre and post — the synthetic
  fixture is high-noise white-noise data that wants maximal Ridge
  shrinkage regardless of scaler statistics);
  ``lambda_log10_sd_across_5fold`` newly non-zero on 6 of 217 1Y
  folds with max σ=0.2400 (methodological signature of the refactor:
  re-fit scalers introduce natural inner-fold variance previously
  suppressed by the shared-scaler pattern).
* **Sxx-15** triage: NOT triggered. Zero production scoring callers
  of ``fit_return_forecast_task_b1`` exist; only consumers are
  ``tests/test_return_forecast.py`` (now 19 tests) +
  ``macro_pipeline.validation.validate_gate19_l5b_task_b1_subcriteria``
  (Gate 19-B1). Prospective-only marker in ``L5B_BACKLOG.md`` per
  AP-AUTH-46 gratuitous-Sxx guard.
* **Gate 19-B1 extension**: criteria 23 + 24 (KICK-4 NEW) verify (i)
  the ``inner_cv_scaler_recomputed`` no-default field is present and
  set at runtime via Option Y signature inspection, and (ii) the
  ``_select_lambda_inner_cv_ridge`` body re-fits z-scalers per inner
  block via AST audit (substring ``_zscore_fit_transform(X_tr`` must
  be present in the helper source).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm

from macro_pipeline.analysis.newey_west_hac import fit_ols_hac
from macro_pipeline.analysis.r_squared_panel import HORIZONS
from macro_pipeline.analysis.walk_forward_cv import WalkForwardSchedule
from macro_pipeline.models.composite_refit import LAMBDA_GRID_DEFAULT


# L5b-KICK-5 (tag ``l5b-kick-5-accept``, 2026-05-15): block-bootstrap
# fallback-state taxonomy per ChatGPT 5.5 IMPORTANT #6 reviewer flag.
# Mirrors KICK-3 ``BinDiagnosticStatus`` + KICK-4 ``CellLabel`` Literal
# precedents. Per AP-AUTH-53 step #3, the dataclass fields carrying
# this value have no default — caller intent forced at construction.
BootstrapFallbackFlag = Literal[
    "none",
    "B_halved",
    "bs1_degenerate",
]
_VALID_BOOTSTRAP_FALLBACK_FLAGS: frozenset[str] = frozenset({
    "none",
    "B_halved",
    "bs1_degenerate",
})


# L5b-A (tag ``l5b-a-accept``, 2026-05-15): block-length distribution
# discriminator per ChatGPT 5.5 Dim-3 stationary block bootstrap
# (Politis-Romano 1994) institutional default. Tri-state Literal
# (binary plus reserved future variant) — ``"fixed"`` is the pre-L5b-A
# legacy variant; ``"geometric"`` is the post-L5b-A institutional
# default. Mirrors KICK-5 ``BootstrapFallbackFlag`` Literal precedent.
# Per AP-AUTH-54 step #2, the dataclass field carrying this value has
# no default — caller intent forced at construction time.
BlockLengthDistribution = Literal[
    "fixed",
    "geometric",
]
_VALID_BLOCK_LENGTH_DISTRIBUTIONS: frozenset[str] = frozenset({
    "fixed",
    "geometric",
})


# L5b-KICK-6 (tag ``l5b-kick-6-accept``, 2026-05-15): Ridge inference
# labeling taxonomy per ChatGPT 5.5 IMPORTANT #5 reviewer flag.
# Mirrors KICK-5 ``BootstrapFallbackFlag`` Literal precedent. Per
# AP-AUTH-53 step #3 / AP-AUTH-54 step #2, the dataclass field carrying
# this value has no default — caller intent forced at construction.
#
# Semantic taxonomy:
#   "forecast_vs_realized" — p-value is from univariate
#       ``realized = α + β·forecast + ε`` regression diagnostic
#       (the institutionally correct label for Ridge fits in this
#       module; this IS what ``p_value_beta_hac`` computes).
#   "feature_significance" — per-feature coefficient inference (NOT
#       applicable to Ridge under standard sampling theory; reserved
#       for future OLS variants).
#   "diagnostic_only" — p-value reported as illustrative but not
#       statistically inferential (regime instability or sample-size
#       conditions invalidating standard inference).
InferenceLabel = Literal[
    "forecast_vs_realized",
    "feature_significance",
    "diagnostic_only",
]
_VALID_INFERENCE_LABELS: frozenset[str] = frozenset({
    "forecast_vs_realized",
    "feature_significance",
    "diagnostic_only",
})


@dataclass(frozen=True)
class BootstrapDiagnostics:
    """Per-bootstrap-call diagnostics surface for the L5-B1 block
    bootstrap (closes ChatGPT 5.5 IMPORTANT #6 reviewer flag via the
    AP-AUTH-53 reviewer-driven-kickoff-item pattern, fifth instance,
    internal-implementation variant per AP-AUTH-54 codified at
    ``l5b-kick-5-accept``).

    All seven fields no-default per AP-AUTH-53 step #3 (six baseline
    KICK-5 fields plus one L5b-A discriminator). The ``__post_init__``
    validator enforces (a) the tri-state ``fallback_flag`` taxonomy
    (KICK-5) and (b) the binary ``block_length_distribution`` taxonomy
    (L5b-A). Both validators mirror the KICK-3 ``BinDiagnosticStatus``
    validator pattern.

    Fields
    ------
    n_train
        Rows in the training block fed to this bootstrap call.
    n_eff
        Effective non-overlapping sample size
        (= ``n_train // horizon_months``); semantically aligned with
        ``RidgeFitResult.n_eff_nonoverlap_train``.
    block_size
        **Polymorphic semantic per `block_length_distribution`
        discriminator (L5b-A)**:
          - When ``block_length_distribution == "fixed"`` (pre-L5b-A
            legacy variant): exact block length actually used,
            AFTER any fallback collapse.
          - When ``block_length_distribution == "geometric"`` (L5b-A
            post-refactor institutional default per Politis-Romano):
            the geometric distribution MEAN parameter (``mean_block_length``
            = ``1 / p``). The actual block lengths drawn per bootstrap
            iteration are random with this expected value.
        Under either variant, when ``fallback_flag == "bs1_degenerate"``
        this collapses to 1.
    block_count
        Number of blocks available (``n_train // block_size``) AFTER
        any fallback collapse. Under the ``"geometric"`` variant this
        is the EXPECTED block count under integer floor-division (the
        actual count drawn per iteration is random). Under the
        ``"bs1_degenerate"`` fallback this is ``n_train`` (iid).
    B_effective
        Actual bootstrap iterations executed. Equals the requested
        ``bootstrap_iterations`` when ``fallback_flag == "none"``;
        halved (``// 2``) when ``fallback_flag == "B_halved"``;
        equals requested when ``fallback_flag == "bs1_degenerate"``
        (the bs=1 collapse path runs the requested iteration count
        on the degenerate iid resampler).
    fallback_flag
        Tri-state ``Literal``:
        - ``"none"``: block_count >= 4; primary path
        - ``"B_halved"``: 2 <= block_count < 4; B halved per R1
          mitigation
        - ``"bs1_degenerate"``: block_count < 2; block_size collapsed
          to 1 (iid bootstrap)
        Per ITEM 6 of L5b-A read-and-plan: the fallback trigger
        condition uses integer floor-division ``n_train //
        block_size``, which is invariant across the fixed ↔ geometric
        variants. K5.4 test survives verbatim post-L5b-A.
    block_length_distribution
        Binary ``Literal`` (L5b-A NEW):
        - ``"fixed"``: pre-L5b-A legacy variant (deterministic block
          length = ``block_size``)
        - ``"geometric"``: L5b-A post-refactor institutional default
          (random block lengths drawn from Geometric(1/block_size) per
          Politis-Romano 1994 stationary block bootstrap)
    """

    n_train: int
    n_eff: int
    block_size: int
    block_count: int
    B_effective: int
    fallback_flag: BootstrapFallbackFlag
    block_length_distribution: BlockLengthDistribution  # L5b-A no-default per AP-AUTH-54 step #2

    def __post_init__(self) -> None:
        # KICK-5 NEG test K5.5 contract: tri-state validation enforced
        # at construction time. Mirrors KICK-3 ``BinDiagnosticStatus``
        # validator precedent.
        if self.fallback_flag not in _VALID_BOOTSTRAP_FALLBACK_FLAGS:
            raise ValueError(
                f"fallback_flag={self.fallback_flag!r} must be one of "
                f"{sorted(_VALID_BOOTSTRAP_FALLBACK_FLAGS)} "
                "(spec L5b-KICK-5 tri-state; AP-AUTH-53 step #3 + "
                "AP-AUTH-54 internal-implementation variant)"
            )
        # L5b-A NEG test A.4 contract: binary tri-state validation
        # enforced at construction time. Same validator pattern as
        # fallback_flag above.
        if self.block_length_distribution not in _VALID_BLOCK_LENGTH_DISTRIBUTIONS:
            raise ValueError(
                f"block_length_distribution={self.block_length_distribution!r} "
                f"must be one of {sorted(_VALID_BLOCK_LENGTH_DISTRIBUTIONS)} "
                "(spec L5b-A binary discriminator per Politis-Romano "
                "1994 stationary block bootstrap; AP-AUTH-54 step #2)"
            )


# Per spec §5.B.1.4 line 745: B = 1000 block-bootstrap iterations.
BOOTSTRAP_ITERATIONS_DEFAULT: int = 1000

# Per spec §5.B.2 item 4 + AP-AUTH-44: skip folds below this nominal-train
# floor (mirrors UNDERPOWERED_N_NOMINAL_MIN from analysis.effective_sample_size).
_MIN_N_TRAIN_OBS: int = 24
_MIN_N_TEST_OBS: int = 1

# Sentinel column name that must NEVER appear in Task B1 input panels
# (closes ChatGPT v2 §D.2 circularity per S-9).
_FORBIDDEN_INPUT_COLUMNS: frozenset[str] = frozenset({
    "positive_return_probability",
    "RETURN_POSITIVE",
})

# Spec §5.B.1.4: block-size sensitivity at {h/4, h/2, h, 2h}.
# Spec §5.B.1.4: bandwidth sensitivity at {h−1, Andrews, max(2, h//4)}.
_BLOCK_SIZE_LABELS: tuple[str, ...] = ("h/4", "h/2", "h", "2h")
_HAC_BANDWIDTH_LABELS: tuple[str, ...] = ("h-1", "andrews", "h//4_floor")


@dataclass(frozen=True)
class RidgeFitResult:
    """One Task B1 Ridge return-forecast result for a single
    (horizon × schedule × fold).

    Fields per spec §5.B.1.1 lines 631-661 plus two sensitivity-report
    fields (``block_size_sensitivity_se``, ``hac_bandwidth_sensitivity_se``)
    required by Gate 19 criteria 11 + 12 (spec §5.B.6) but not enumerated
    in the spec dataclass definition itself (per spec §5.B.1.4 line 748:
    "sensitivity profile stored in fit metadata"). Storing them on the
    dataclass is the simplest route.
    """

    fold_id: int
    horizon: str                                    # "1Y" | "3Y" | "5Y" | "10Y"
    schedule_type: str                              # "expanding" | "rolling_20y"
    lambda_selected: float                          # inner-CV-selected λ
    lambda_grid: tuple[float, ...]
    lambda_log10_sd_across_5fold: float             # diagnostic — log10(λ) SD across inner folds
    coefficient_sign_flip_rate: float               # diagnostic — rate of β sign flips vs prior outer fold
    coef: np.ndarray                                # β̂ vector (length = n_features)
    intercept: float
    forecast_train: np.ndarray                      # in-sample predictions
    forecast_test: np.ndarray                       # OOS forecast on outer test window
    r_squared: float                                # in-sample R²
    r_squared_oos: float                            # OOS R²
    residual_se_hac: float                          # HAC SE @ maxlags = horizon_months − 1
    p_value_beta_hac: float                         # L5b-KICK-6: Newey-West HAC p-value for the slope coefficient of the univariate forecast-vs-realized regression (realized = α + β·forecast + ε), computed via fit_ols_hac(y_test, forecast_test). NOT a Ridge coefficient inference statistic — Ridge does not admit per-feature p-values under standard sampling theory. See inference_label field for taxonomy.
    bootstrap_residual_se_distribution: np.ndarray  # B=1000 block-bootstrap residual SEs
    bootstrap_block_size: int                       # primary block size (= horizon_months // 2)
    hac_maxlags: int                                # primary HAC maxlags (= horizon_months − 1)
    n_train_obs: int
    n_test_obs: int
    n_eff_nonoverlap_train: int                     # = n_train_obs // horizon_months
    grid_edge_bind: bool                            # True if lambda_selected ∈ {grid[0], grid[-1]}
    block_size_sensitivity_se: dict[str, float]     # {"h/4": se, "h/2": se, "h": se, "2h": se}
    hac_bandwidth_sensitivity_se: dict[str, float]  # {"h-1": se, "andrews": se, "h//4_floor": se}
    fit_timestamp: pd.Timestamp
    inner_cv_scaler_recomputed: bool                # L5b-KICK-4: True iff inner-CV re-fit z-scaler per inner block (Task A parity); no default per AP-AUTH-53 step #3
    bootstrap_diagnostics: BootstrapDiagnostics     # L5b-KICK-5: primary block-bootstrap call diagnostics surface; no default per AP-AUTH-54 step #2
    block_size_sensitivity_diagnostics: dict[str, BootstrapDiagnostics]  # L5b-KICK-5: per-sensitivity-block-size diagnostics; keys match _BLOCK_SIZE_LABELS; no default
    inference_label: InferenceLabel                 # L5b-KICK-6: tri-state taxonomy labeling p_value_beta_hac as forecast-vs-realized model diagnostic (NOT per-feature Ridge inference); no default per AP-AUTH-54 step #2

    def __post_init__(self) -> None:
        # L5b-KICK-6 NEG test K6.3 contract: tri-state validation
        # enforced at construction time. Mirrors KICK-3
        # ``BinDiagnosticStatus`` + KICK-5 ``BootstrapDiagnostics``
        # ``__post_init__`` validator precedents. First
        # ``__post_init__`` on ``RidgeFitResult`` itself; frozen-
        # dataclass compatibility identical to the precedents
        # (object.__setattr__ not invoked; validator is read-only).
        if self.inference_label not in _VALID_INFERENCE_LABELS:
            raise ValueError(
                f"inference_label={self.inference_label!r} must be one of "
                f"{sorted(_VALID_INFERENCE_LABELS)} "
                "(spec L5b-KICK-6 tri-state per ChatGPT 5.5 IMPORTANT "
                "#5; AP-AUTH-53 step #3 + AP-AUTH-54 internal-"
                "implementation variant)"
            )


def _zscore_fit_transform(
    X_train: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Train-only z-scoring per spec §2.5 audit #5. Returns (X_train_z, mean, std).

    Duplicates the helper at ``composite_refit.py:96`` (private to Task A;
    same numerical contract).
    """
    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0, ddof=0)
    # Avoid divide-by-zero on degenerate columns (zero-variance feature).
    std = np.where(std < 1e-12, 1.0, std)
    X_train_z = (X_train - mean) / std
    return X_train_z, mean, std


def _zscore_transform(
    X: np.ndarray, mean: np.ndarray, std: np.ndarray,
) -> np.ndarray:
    return (X - mean) / std


def _build_inner_blocks(
    n_train: int, n_inner_folds: int,
) -> list[tuple[slice, slice]]:
    """Time-ordered contiguous blocks for inner CV (NO contamination gap).

    Duplicates ``composite_refit.py:135``; same contract per spec §5.B.1.2.
    """
    fold_size = max(1, n_train // (n_inner_folds + 1))
    blocks: list[tuple[slice, slice]] = []
    for k in range(n_inner_folds):
        train_end = fold_size * (k + 1)
        test_start = train_end
        test_end = min(test_start + fold_size, n_train)
        if train_end >= test_end or train_end < 2:
            break
        blocks.append((slice(0, train_end), slice(test_start, test_end)))
    return blocks


def _fit_ridge_closed_form(
    X: np.ndarray, y: np.ndarray, lam: float,
) -> tuple[np.ndarray, float]:
    """Closed-form Ridge per spec §5.B.3: β̂ = (X'X + λI)⁻¹X'y; α̂ = ȳ − β̂x̄.

    Assumes X is already z-scored (so component-wise x̄ ≈ 0 and α̂ ≈ ȳ).
    Uses ``np.linalg.solve`` for numerical stability over ``np.linalg.inv``.
    """
    n_features = X.shape[1]
    XtX = X.T @ X
    XtX_reg = XtX + lam * np.eye(n_features)
    Xty = X.T @ y
    beta = np.linalg.solve(XtX_reg, Xty)
    # X is z-scored ⇒ column means ≈ 0 ⇒ intercept = y mean.
    intercept = float(y.mean())
    return beta, intercept


def _select_lambda_inner_cv_ridge(
    X_train: np.ndarray,
    y_train: np.ndarray,
    lambda_grid: tuple[float, ...],
    inner_fold_count: int,
) -> tuple[float, float]:
    """Inner-CV λ selection: minimize mean OOS MSE across inner blocks.

    Returns ``(lambda_star, lambda_log10_sd_across_5fold)``.

    ``lambda_log10_sd_across_5fold`` is the SD of ``log10(per-inner-fold
    best λ)`` across the inner folds — diagnostic for Gate 19 criterion 13
    (closes ChatGPT E.6 / L5-RISK-6 per spec §5.B.5.B B8).

    L5b-KICK-4 (tag ``l5b-kick-4-accept``, 2026-05-15): the parameter
    ``X_train`` is the RAW (un-z-scored) outer-train feature matrix.
    Each inner block re-fits its own z-scaler on the inner-train slice
    via ``_zscore_fit_transform(X_tr_raw)`` and applies the resulting
    statistics to the inner-test slice via
    ``_zscore_transform(X_te_raw, mean_tr_inner, std_tr_inner)``. This
    matches Task A's pattern at ``composite_refit.py:177-178`` and
    closes the Codex 5.5 IMPORTANT reviewer flag on nested-CV purity
    (inner blocks must NOT inherit outer-train scaler statistics).
    Pre-KICK-4 behavior received a pre-z-scored ``X_train_z`` from the
    caller; that path is deleted (correctness fix, not a policy choice).
    """
    blocks = _build_inner_blocks(len(X_train), inner_fold_count)
    if not blocks:
        # Too few obs for inner CV: pick mid-grid λ (graceful degradation).
        return float(lambda_grid[len(lambda_grid) // 2]), float("nan")

    # mse_matrix[lam_idx][fold_idx]
    mse_matrix: list[list[float]] = [[] for _ in lambda_grid]
    for tr_slice, te_slice in blocks:
        X_tr_raw = X_train[tr_slice]
        y_tr = y_train[tr_slice]
        X_te_raw = X_train[te_slice]
        y_te = y_train[te_slice]
        if len(X_tr_raw) < 2 or len(X_te_raw) == 0:
            continue
        # KICK-4: re-fit z-scaler on inner-train slice (Task A parity per
        # composite_refit.py:177-178). NEVER inherit outer-train statistics.
        X_tr, mean_tr_inner, std_tr_inner = _zscore_fit_transform(X_tr_raw)
        X_te = _zscore_transform(X_te_raw, mean_tr_inner, std_tr_inner)
        for lam_idx, lam in enumerate(lambda_grid):
            beta, alpha = _fit_ridge_closed_form(X_tr, y_tr, lam)
            y_hat = X_te @ beta + alpha
            mse_matrix[lam_idx].append(float(np.mean((y_te - y_hat) ** 2)))

    mean_mse_per_lambda = [
        (float(np.mean(m)) if m else float("inf"))
        for m in mse_matrix
    ]
    best_idx = int(np.argmin(mean_mse_per_lambda))
    lambda_star = float(lambda_grid[best_idx])

    # Per-fold best λ → SD of log10 distribution.
    n_inner = len(mse_matrix[0]) if mse_matrix and mse_matrix[0] else 0
    per_fold_best_lam: list[float] = []
    for fold_idx in range(n_inner):
        mses_at_fold = [mse_matrix[lam_idx][fold_idx] for lam_idx in range(len(lambda_grid))]
        argmin_lam_idx = int(np.argmin(mses_at_fold))
        per_fold_best_lam.append(float(lambda_grid[argmin_lam_idx]))

    if per_fold_best_lam:
        lambda_log10_sd = float(
            np.std(np.log10(np.asarray(per_fold_best_lam)), ddof=0)
        )
    else:
        lambda_log10_sd = float("nan")

    return lambda_star, lambda_log10_sd


def _newey_west_automatic_maxlags(n_obs: int) -> int:
    """Newey-West (1994) automatic bandwidth selector.

    ``L = floor(4 * (T/100)^(2/9))`` where ``T`` = number of residuals.

    Drop-in for the spec §5.B.1.4 "Andrews-automatic" label: statsmodels
    does not accept the literal ``cov_kwds={'maxlags': 'andrews'}`` string
    the spec sketches; this NW-1994 automatic rule is the reproducible
    interpretation (commented in the bandwidth-sensitivity report under
    the same ``"andrews"`` label for spec-mirror traceability).
    """
    if n_obs < 1:
        return 0
    return max(0, int(np.floor(4.0 * (n_obs / 100.0) ** (2.0 / 9.0))))


def _hac_beta_se_at_maxlags(
    y_test: np.ndarray, forecast_test: np.ndarray, maxlags: int,
) -> float:
    """Direct statsmodels HAC SE of the regression coefficient β at an
    explicit ``maxlags`` override.

    Returns ``nan`` when fewer than 2 aligned observations or the forecast
    has zero variance. The HAC-corrected SE of β is the
    bandwidth-DEPENDENT quantity per Andrews (1991) / NW (1987); the raw
    residual SD reported in ``RidgeFitResult.residual_se_hac`` is
    bandwidth-INVARIANT (so it would be a degenerate sensitivity
    diagnostic). The bandwidth-sensitivity report below stores
    ``bse[β]`` so spec test B6 ``..._h_minus_1_andrews_lower`` exercises
    a quantity that actually varies with the maxlags choice.
    """
    n = len(y_test)
    if n < 2:
        return float("nan")
    if float(np.std(forecast_test, ddof=0)) == 0.0:
        return float("nan")
    X = sm.add_constant(forecast_test)
    try:
        model = sm.OLS(y_test, X).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": max(0, int(maxlags))},
        )
    except Exception:
        return float("nan")
    return float(model.bse[1])


def _compute_hac_bandwidth_sensitivity(
    y_test: np.ndarray, forecast_test: np.ndarray, horizon_months: int,
) -> dict[str, float]:
    """Three-bandwidth HAC SE-of-β sensitivity per spec §5.B.1.4 item 2.

    Labels: ``"h-1"`` = ``horizon_months − 1`` (primary mirror);
    ``"andrews"`` = NW-1994 automatic (see ``_newey_west_automatic_maxlags``);
    ``"h//4_floor"`` = ``max(2, horizon_months // 4)``.

    The values are HAC standard errors of the regression coefficient β
    (not residual SDs), since those vary with the bandwidth choice and
    therefore expose the sensitivity the spec test B6 is designed to
    surface.
    """
    if len(y_test) < 2:
        return {label: float("nan") for label in _HAC_BANDWIDTH_LABELS}
    residuals_len = len(y_test)
    bandwidths = {
        "h-1": max(0, horizon_months - 1),
        "andrews": _newey_west_automatic_maxlags(residuals_len),
        "h//4_floor": max(2, horizon_months // 4),
    }
    sensitivity: dict[str, float] = {}
    for label in _HAC_BANDWIDTH_LABELS:
        sensitivity[label] = _hac_beta_se_at_maxlags(
            y_test, forecast_test, bandwidths[label],
        )
    return sensitivity


def _sample_stationary_block_lengths(
    n_obs: int,
    mean_block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Politis-Romano (1994) geometric block-length sampler.

    Returns an array of block lengths drawn from Geometric(p) with
    ``p = 1 / mean_block_length`` (memoryless property). Continues
    drawing until the cumulative block length reaches or exceeds
    ``n_obs``, so the caller is guaranteed ``sum(returned_array) >=
    n_obs``. The caller truncates the assembled block sequence to
    exactly ``n_obs`` length.

    Reference: Politis & Romano (1994) "The Stationary Bootstrap"
    JASA 89:1303-1313. The geometric distribution is the standard
    institutional choice for the block-length distribution; its
    memoryless property ensures the resulting bootstrap sample is
    asymptotically stationary regardless of where in the original
    series the blocks are sampled.

    L5b-A (tag ``l5b-a-accept``, 2026-05-15): first original OOS
    hardening sub-phase post-kickoff sprint. Closes ChatGPT 5.5 Dim-3
    OOS rigor mandate (stationary block bootstrap as institutional
    default for serial-dependent residuals; eliminates manual block-
    size tuning via random block lengths).

    Parameters
    ----------
    n_obs
        Total number of observations to cover (typically ``n_train``).
        Block lengths are drawn until cumulative sum reaches or
        exceeds this; caller truncates.
    mean_block_length
        Geometric distribution mean parameter; must be >= 1. Lower
        bound 1 is the degenerate iid-resampling case (``p = 1.0``;
        all blocks length 1).
    rng
        Pre-constructed ``np.random.Generator`` for determinism.

    Returns
    -------
    np.ndarray
        Length-variable array of block lengths (dtype int). The
        invariant ``sum(returned) >= n_obs`` holds; the array length
        equals the number of blocks drawn (typically close to
        ``n_obs / mean_block_length`` in expectation).
    """
    p = 1.0 / max(int(mean_block_length), 1)
    lengths: list[int] = []
    cumulative = 0
    # numpy ``rng.geometric(p)`` returns the trial number of the first
    # success on the support {1, 2, 3, ...} with mean = 1/p. This
    # matches the Politis-Romano geometric distribution convention.
    while cumulative < n_obs:
        L = int(rng.geometric(p))
        lengths.append(L)
        cumulative += L
    return np.asarray(lengths, dtype=int)


def _block_bootstrap_residual_se(
    X_train_z: np.ndarray,
    y_train: np.ndarray,
    X_test_z: np.ndarray,
    y_test: np.ndarray,
    forecast_train: np.ndarray,
    lambda_star: float,
    bootstrap_iterations: int,
    block_size: int,
    rng: np.random.Generator,
    *,
    horizon_months: int,
) -> tuple[np.ndarray, BootstrapDiagnostics]:
    """Residual block-bootstrap of OOS residual SE per spec §5.B.1.4.

    Procedure (mirrors spec text "refit Ridge, compute raw_score_test per
    resample, accumulate bootstrap_residual_se_distribution"):
      1. Compute training residuals ``e = y_train − forecast_train``.
      2. For ``b = 1..B``: block-bootstrap ``e → e*_b`` (concatenate
         random contiguous blocks of length ``block_size``); form
         ``y*_b = forecast_train + e*_b``; refit Ridge with the same
         ``lambda_star`` on ``(X_train_z, y*_b) → (β*_b, α*_b)``;
         compute new test forecast ``forecast_test_b = X_test_z β*_b
         + α*_b``; ``se_b = std(y_test − forecast_test_b, ddof=1)``.
      3. Return the length-``B`` array of ``se_b`` values.

    R1 mitigation (pre-flight risk): if ``n_train // block_size < 4``,
    emit a ``UserWarning`` and halve ``B`` for this call. If
    ``n_train // block_size < 2``, fall back to ``block_size = 1`` and
    emit a stronger warning (graceful degradation; Sxx-13 candidate at
    ACCEPT report time).

    L5b-KICK-5 (tag ``l5b-kick-5-accept``, 2026-05-15): return type
    changed from ``np.ndarray`` to ``tuple[np.ndarray,
    BootstrapDiagnostics]`` to surface the fallback-state diagnostics
    that the existing warning-only path was hiding from downstream
    consumers. Closes ChatGPT 5.5 IMPORTANT #6 reviewer flag via the
    AP-AUTH-53 fifth-instance / AP-AUTH-54 internal-implementation
    variant pattern. ``horizon_months`` keyword-only argument added to
    populate ``BootstrapDiagnostics.n_eff``; pre-KICK-5 callers must
    update tuple unpacking.

    L5b-A (tag ``l5b-a-accept``, 2026-05-15): bootstrap sampling
    upgraded from fixed-block to **stationary block bootstrap (Politis-
    Romano 1994)**. The ``block_size`` parameter is now interpreted as
    the GEOMETRIC distribution MEAN parameter (was previously the exact
    block length). Each bootstrap iteration draws random block lengths
    from ``Geometric(1/block_size)`` via
    ``_sample_stationary_block_lengths`` and assembles blocks with
    cyclic wrapping. Closes ChatGPT 5.5 Dim-3 OOS rigor mandate:
    stationary block bootstrap is the institutional default for serial-
    dependent residuals because random block lengths converge to the
    correct asymptotic distribution without manual block-size tuning.
    The fallback-flag taxonomy is preserved (integer floor-division
    arithmetic ``n_train // block_size`` invariant across fixed ↔
    geometric variants per ITEM 6 analysis). Returned
    ``BootstrapDiagnostics.block_length_distribution`` is
    ``"geometric"`` post-refactor.

    Returns
    -------
    tuple[np.ndarray, BootstrapDiagnostics]
        ``(se_dist, diagnostics)`` where ``se_dist`` has shape
        ``(B_effective,)`` (``B_effective`` may be < B per R1
        mitigation) and ``diagnostics`` records the fallback state
        plus the post-L5b-A ``block_length_distribution="geometric"``
        discriminator. Returns ``(empty_array,
        diagnostics_with_B_effective_0)`` when ``n_test < 2``.
    """
    n_train = len(y_train)
    bs = max(1, int(block_size))
    block_count = n_train // bs if bs > 0 else 0
    b_effective = bootstrap_iterations
    fallback_flag: BootstrapFallbackFlag = "none"

    if block_count < 2:
        warnings.warn(
            f"block_bootstrap: block_count={block_count} < 2 for "
            f"n_train={n_train}, block_size={bs}; falling back to "
            "block_size=1 (iid bootstrap)",
            stacklevel=3,
        )
        bs = 1
        block_count = n_train
        fallback_flag = "bs1_degenerate"
    elif block_count < 4:
        b_effective = max(1, bootstrap_iterations // 2)
        warnings.warn(
            f"block_bootstrap: block_count={block_count} < 4 for "
            f"n_train={n_train}, block_size={bs}; halving B to "
            f"{b_effective} per R1 mitigation",
            stacklevel=3,
        )
        fallback_flag = "B_halved"

    # KICK-5 edge case: y_test too short for residual SE; return empty
    # array but still populate diagnostics with B_effective=0.
    if len(y_test) < 2:
        diagnostics_empty = BootstrapDiagnostics(
            n_train=n_train,
            n_eff=n_train // max(horizon_months, 1),
            block_size=bs,
            block_count=block_count,
            B_effective=0,
            fallback_flag=fallback_flag,
            block_length_distribution="geometric",  # L5b-A: stationary default
        )
        return np.empty(0, dtype=float), diagnostics_empty

    residuals_train = y_train - forecast_train
    se_dist = np.empty(b_effective, dtype=float)

    # L5b-A: stationary block bootstrap (Politis-Romano 1994). For each
    # bootstrap iteration, draw random block lengths from
    # Geometric(1/bs); for each block, draw a random start index
    # uniformly on {0, ..., n_train-1}; assemble blocks with cyclic
    # wrapping (residuals[(s + j) mod n_train]); truncate concatenated
    # series to n_train. Replaces the pre-L5b-A fixed-block sampling
    # at the same loop position.
    for b in range(b_effective):
        block_lengths = _sample_stationary_block_lengths(n_train, bs, rng)
        block_starts = rng.integers(0, n_train, size=len(block_lengths))
        e_pieces: list[np.ndarray] = []
        total = 0
        for s, L in zip(block_starts, block_lengths):
            take = min(int(L), n_train - total)
            if take <= 0:
                break
            # Cyclic indexing per Politis-Romano: wrap around the
            # original series boundary so the sample is asymptotically
            # stationary regardless of starting index.
            idx = (int(s) + np.arange(take)) % n_train
            e_pieces.append(residuals_train[idx])
            total += take
            if total >= n_train:
                break
        e_star = np.concatenate(e_pieces)[:n_train]
        y_star = forecast_train + e_star
        beta_b, alpha_b = _fit_ridge_closed_form(X_train_z, y_star, lambda_star)
        forecast_test_b = X_test_z @ beta_b + alpha_b
        se_dist[b] = float(np.std(y_test - forecast_test_b, ddof=1))

    diagnostics = BootstrapDiagnostics(
        n_train=n_train,
        n_eff=n_train // max(horizon_months, 1),
        block_size=bs,
        block_count=block_count,
        B_effective=b_effective,
        fallback_flag=fallback_flag,
        block_length_distribution="geometric",  # L5b-A: stationary default
    )
    return se_dist, diagnostics


def _compute_block_size_sensitivity(
    X_train_z: np.ndarray,
    y_train: np.ndarray,
    X_test_z: np.ndarray,
    y_test: np.ndarray,
    forecast_train: np.ndarray,
    lambda_star: float,
    bootstrap_iterations: int,
    horizon_months: int,
    sensitivity_block_sizes: tuple[int, ...],
    rng: np.random.Generator,
) -> tuple[dict[str, float], dict[str, BootstrapDiagnostics]]:
    """Four-block-size mean residual-SE sensitivity per spec §5.B.1.4 item 1.

    Labels: ``"h/4"``, ``"h/2"`` (primary mirror), ``"h"``, ``"2h"``.

    Each label runs a separate block-bootstrap; the first dict stores
    the MEAN of that distribution (a single number per label) so the
    result is compact (full distributions per label would 4× the memory
    cost).

    L5b-KICK-5 (tag ``l5b-kick-5-accept``, 2026-05-15): return type
    extended from ``dict[str, float]`` to
    ``tuple[dict[str, float], dict[str, BootstrapDiagnostics]]`` to
    surface per-sensitivity-block-size fallback diagnostics. The
    reviewer concern from ChatGPT 5.5 IMPORTANT #6 explicitly targets
    this path ("sensitivity settings can hit low block counts and fall
    back, as warnings surfaced in the targeted run"). Empirical probe
    at 5Y/expanding with B=10 confirms ``"2h"`` triggers
    ``"B_halved"`` on all 10 folds. KICK-5 makes this state explicit
    in the dataclass surface rather than implicit in warning text.
    """
    se_out: dict[str, float] = {}
    diag_out: dict[str, BootstrapDiagnostics] = {}

    if len(y_test) < 2:
        # Edge case: residual SE undefined; populate NaN SE per label,
        # but still emit valid diagnostics with B_effective=0.
        n_train_local = len(y_train)
        n_eff_local = n_train_local // max(horizon_months, 1)
        sizes = dict(zip(_BLOCK_SIZE_LABELS, sensitivity_block_sizes))
        for label in _BLOCK_SIZE_LABELS:
            bs_local = max(1, sizes[label])
            bc_local = n_train_local // bs_local if bs_local > 0 else 0
            se_out[label] = float("nan")
            diag_out[label] = BootstrapDiagnostics(
                n_train=n_train_local,
                n_eff=n_eff_local,
                block_size=bs_local,
                block_count=bc_local,
                B_effective=0,
                fallback_flag="none",
                block_length_distribution="geometric",  # L5b-A: stationary default
            )
        return se_out, diag_out

    sizes = dict(zip(_BLOCK_SIZE_LABELS, sensitivity_block_sizes))
    for label in _BLOCK_SIZE_LABELS:
        bs = max(1, sizes[label])
        dist, diag = _block_bootstrap_residual_se(
            X_train_z, y_train, X_test_z, y_test, forecast_train,
            lambda_star, bootstrap_iterations, bs, rng,
            horizon_months=horizon_months,
        )
        se_out[label] = float(np.mean(dist)) if dist.size > 0 else float("nan")
        diag_out[label] = diag
    return se_out, diag_out


def _default_block_size_sensitivity_grid(horizon_months: int) -> tuple[int, int, int, int]:
    """Spec §5.B.1.4 item 1 default block-size grid ``{h/4, h/2, h, 2h}``."""
    return (
        max(1, horizon_months // 4),
        max(1, horizon_months // 2),
        max(1, horizon_months),
        max(1, 2 * horizon_months),
    )


def _validate_b1_input_schema(
    crps_calibrated_panel: pd.DataFrame,
    cdrs_calibrated_panel: pd.DataFrame,
    macro_features: pd.DataFrame,
    lambda_grid: tuple[float, ...],
) -> None:
    """Spec §5.B.1.1 + §5.B.5.B B1/B10 + Standing Order #4 AST-audit contract.

    Raises ``ValueError`` on:
      * empty ``lambda_grid`` or any non-positive value (test B10).
      * any input panel containing a column in ``_FORBIDDEN_INPUT_COLUMNS``
        (test B2-1 promoted per D-B1-3; closes ChatGPT v2 §D.2).
      * CRPS panel column count != 1 (test B1 strict schema).
      * CDRS panel column count != 20 (test B1 strict schema).
    """
    if not lambda_grid:
        raise ValueError("lambda_grid must be non-empty")
    for lam in lambda_grid:
        if lam <= 0:
            raise ValueError(
                f"lambda_grid contains non-positive value {lam!r}; "
                "Ridge requires λ > 0"
            )

    for panel_name, panel in (
        ("crps_calibrated_panel", crps_calibrated_panel),
        ("cdrs_calibrated_panel", cdrs_calibrated_panel),
        ("macro_features", macro_features),
    ):
        forbidden = set(panel.columns) & _FORBIDDEN_INPUT_COLUMNS
        if forbidden:
            raise ValueError(
                f"{panel_name} contains forbidden column(s) "
                f"{sorted(forbidden)}: Task B1 does NOT consume "
                "RETURN_POSITIVE outputs (would re-introduce ChatGPT v2 "
                "§D.2 circularity resolved by S-9)"
            )

    if len(crps_calibrated_panel.columns) != 1:
        raise ValueError(
            f"crps_calibrated_panel must have exactly 1 calibrated column "
            f"(post-RM-6 CRPS); got {len(crps_calibrated_panel.columns)}"
        )
    if len(cdrs_calibrated_panel.columns) != 20:
        raise ValueError(
            f"cdrs_calibrated_panel must have exactly 20 calibrated columns "
            f"(post-RM-6 CDRS; 4 horizons × 5 thresholds); "
            f"got {len(cdrs_calibrated_panel.columns)}"
        )


def _assemble_feature_matrix(
    crps_calibrated_panel: pd.DataFrame,
    cdrs_calibrated_panel: pd.DataFrame,
    macro_features: pd.DataFrame,
    forward_returns: pd.Series,
    date_lo: pd.Timestamp,
    date_hi: pd.Timestamp,
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """Slice inputs to ``[date_lo, date_hi]``, inner-join on the monthly
    index, drop NaN rows, return ``(X, y, dates_kept)``.

    Column order in ``X``: CRPS (1) + CDRS (20) + macro (M) =
    ``1 + 20 + len(macro_features.columns)``.
    """
    def _window(df_or_s):
        return df_or_s.loc[(df_or_s.index >= date_lo) & (df_or_s.index <= date_hi)]

    crps_w = _window(crps_calibrated_panel)
    cdrs_w = _window(cdrs_calibrated_panel)
    macro_w = _window(macro_features)
    fr_w = _window(forward_returns).rename("__y__")

    combined = pd.concat(
        [crps_w, cdrs_w, macro_w, fr_w], axis=1, join="inner",
    ).dropna()

    if combined.empty:
        n_features = 1 + 20 + len(macro_features.columns)
        return (
            np.empty((0, n_features)),
            np.empty(0),
            pd.DatetimeIndex([]),
        )

    y = combined["__y__"].to_numpy(dtype=float)
    feature_cols = [c for c in combined.columns if c != "__y__"]
    X = combined[feature_cols].to_numpy(dtype=float)
    return X, y, combined.index


def fit_return_forecast_task_b1(
    schedule: WalkForwardSchedule,
    crps_calibrated_panel: pd.DataFrame,
    cdrs_calibrated_panel: pd.DataFrame,
    macro_features: pd.DataFrame,
    forward_returns: pd.Series,
    *,
    lambda_grid: tuple[float, ...] = LAMBDA_GRID_DEFAULT,
    inner_fold_count: int = 5,
    bootstrap_iterations: int = BOOTSTRAP_ITERATIONS_DEFAULT,
    block_size_sensitivity: tuple[int, ...] | None = None,
    random_seed: int = 42,
) -> tuple[RidgeFitResult, ...]:
    """Task B1 (v3 per S-9): Ridge return-forecast regression with
    nested walk-forward λ selection + HAC SE + block bootstrap.

    Parameters
    ----------
    schedule
        ``WalkForwardSchedule`` from L5-A. One call processes one
        (horizon × schedule_type) pair; the function emits one
        ``RidgeFitResult`` per ``schedule.folds`` entry.
    crps_calibrated_panel
        ``pd.DataFrame`` indexed by month with exactly one calibrated
        CRPS-probability column (post-RM-6 isotonic output).
    cdrs_calibrated_panel
        ``pd.DataFrame`` indexed by month with twenty calibrated
        CDRS-probability columns (post-RM-6 isotonic output; 4 horizons
        × 5 thresholds).
    macro_features
        ``pd.DataFrame`` of exogenous regression covariates (valuation,
        real-rate, etc.) indexed by month.
    forward_returns
        ``pd.Series`` of forward real total returns on
        ``PRIMARY_REGRESSION_TARGET`` aligned to ``schedule.horizon``.

    Keyword-only
    ------------
    lambda_grid
        λ values to search inner-CV. Default ``LAMBDA_GRID_DEFAULT``
        (11 log-spaced points 1e-4..1e2). Widen via S-2 trigger if
        ``grid_edge_bind`` rate >10% across folds.
    inner_fold_count
        Inner-CV fold count for λ selection. Default 5.
    bootstrap_iterations
        B-bootstrap residual resamples. Default 1000.
    block_size_sensitivity
        If ``None``, uses ``{h/4, h/2, h, 2h}`` default sweep per
        spec §5.B.1.4. Explicit tuple overrides.
    random_seed
        Determinism control for bootstrap; default 42.

    Returns
    -------
    tuple[RidgeFitResult, ...]
        One result per ``schedule.folds`` entry. Underpowered folds
        (per spec §5.B.2 item 4) are skipped with a warning; the
        returned tuple may be shorter than ``len(schedule.folds)``.

    Raises
    ------
    ValueError
        If input schemas violate spec contract (e.g.,
        ``positive_return_probability`` column present; lambda_grid
        contains non-positive values; CRPS panel has !=1 calibrated
        column or CDRS panel has !=20 calibrated columns under strict
        validation).
    """
    _validate_b1_input_schema(
        crps_calibrated_panel,
        cdrs_calibrated_panel,
        macro_features,
        lambda_grid,
    )

    if schedule.horizon not in HORIZONS:
        raise ValueError(
            f"unknown horizon {schedule.horizon!r}; expected one of "
            f"{sorted(HORIZONS.keys())}"
        )
    horizon_months = HORIZONS[schedule.horizon]

    sensitivity_block_sizes = (
        block_size_sensitivity
        if block_size_sensitivity is not None
        else _default_block_size_sensitivity_grid(horizon_months)
    )

    rng = np.random.default_rng(random_seed)
    results: list[RidgeFitResult] = []
    fit_ts = pd.Timestamp.utcnow()

    for fold in schedule.folds:
        X_train, y_train, _train_dates = _assemble_feature_matrix(
            crps_calibrated_panel, cdrs_calibrated_panel,
            macro_features, forward_returns,
            fold.train_start, fold.train_end,
        )
        X_test, y_test, _test_dates = _assemble_feature_matrix(
            crps_calibrated_panel, cdrs_calibrated_panel,
            macro_features, forward_returns,
            fold.test_start, fold.test_end,
        )

        n_train = len(y_train)
        n_test = len(y_test)
        n_eff_train = n_train // horizon_months if horizon_months > 0 else 0

        # Underpowered fold guard (spec §5.B.2 item 4).
        if (
            n_train < _MIN_N_TRAIN_OBS
            or n_eff_train < 3
            or n_test < _MIN_N_TEST_OBS
        ):
            warnings.warn(
                f"Skipping fold {fold.fold_id} "
                f"(horizon={schedule.horizon}, "
                f"schedule={schedule.schedule_type}): "
                f"n_train={n_train}, n_eff={n_eff_train}, n_test={n_test} "
                "below threshold (spec §5.B.2 item 4)",
                stacklevel=2,
            )
            continue

        # Train-only z-scoring; never reuse statistics across folds.
        # OUTER scaler statistics — used for outer Ridge fit at lines
        # 686-688 below, AND for outer-test projection (X_test_z). The
        # inner-CV λ selection now receives the RAW outer-train matrix
        # and re-fits scalers per inner block (KICK-4 Task A parity).
        X_train_z, mean_tr, std_tr = _zscore_fit_transform(X_train)
        X_test_z = _zscore_transform(X_test, mean_tr, std_tr)

        # Inner-CV λ selection (KICK-4: pass RAW X_train, not X_train_z).
        # Helper re-fits z-scaler on each inner-train slice per Task A
        # precedent at composite_refit.py:177-178; closes Codex 5.5
        # IMPORTANT reviewer flag on nested-CV purity.
        lambda_star, lambda_log10_sd = _select_lambda_inner_cv_ridge(
            X_train, y_train, lambda_grid, inner_fold_count,
        )

        # Refit closed-form Ridge on the full outer training window.
        beta, alpha = _fit_ridge_closed_form(X_train_z, y_train, lambda_star)
        forecast_train = X_train_z @ beta + alpha
        forecast_test = X_test_z @ beta + alpha

        # R² in-sample + OOS.
        ss_tot_tr = float(np.sum((y_train - y_train.mean()) ** 2))
        ss_res_tr = float(np.sum((y_train - forecast_train) ** 2))
        r_squared = (
            1.0 - (ss_res_tr / ss_tot_tr) if ss_tot_tr > 0 else float("nan")
        )

        ss_tot_te = float(np.sum((y_test - y_test.mean()) ** 2))
        ss_res_te = float(np.sum((y_test - forecast_test) ** 2))
        r_squared_oos = (
            1.0 - (ss_res_te / ss_tot_te) if ss_tot_te > 0 else float("nan")
        )

        # HAC SE on the (y_test, forecast_test) regression per spec §5.B.1.3.
        # Wrapper used for the primary call (mirrors spec literal); direct
        # statsmodels used inside ``_compute_hac_bandwidth_sensitivity`` for
        # bandwidth overrides per spec §5.B.1.4 item 2.
        if n_test >= 2:
            hac_primary = fit_ols_hac(
                pd.Series(y_test),
                pd.Series(forecast_test),
                horizon_months=horizon_months,
            )
            if hac_primary is not None:
                residual_se_hac = float(hac_primary.residual_se)
                p_value_beta_hac = float(hac_primary.p_value_beta_NW)
            else:
                residual_se_hac = float("nan")
                p_value_beta_hac = float("nan")
        else:
            residual_se_hac = float("nan")
            p_value_beta_hac = float("nan")

        hac_bandwidth_sensitivity = _compute_hac_bandwidth_sensitivity(
            y_test, forecast_test, horizon_months,
        )

        # Block bootstrap of residual SE per spec §5.B.1.4. Primary block
        # size = horizon_months // 2; sensitivity sweep at {h/4, h/2, h, 2h}.
        # KICK-5: both helpers now return tuples carrying
        # BootstrapDiagnostics. Primary call returns
        # (se_dist, diagnostics); sensitivity sweep returns
        # (se_dict, diagnostics_dict). Per AP-AUTH-54 internal-
        # implementation variant: refactor exposes fallback state to
        # the public RidgeFitResult dataclass without changing the
        # public fit_return_forecast_task_b1 signature.
        primary_block_size = max(1, horizon_months // 2)
        bootstrap_dist, bootstrap_diag = _block_bootstrap_residual_se(
            X_train_z, y_train, X_test_z, y_test, forecast_train,
            lambda_star, bootstrap_iterations, primary_block_size, rng,
            horizon_months=horizon_months,
        )
        block_size_sensitivity_map, block_size_sensitivity_diag_map = (
            _compute_block_size_sensitivity(
                X_train_z, y_train, X_test_z, y_test, forecast_train,
                lambda_star, bootstrap_iterations, horizon_months,
                sensitivity_block_sizes, rng,
            )
        )

        # Grid edge bind (spec §5.B.2 item 1).
        grid_edge_bind = (
            lambda_star == lambda_grid[0] or lambda_star == lambda_grid[-1]
        )
        if grid_edge_bind:
            warnings.warn(
                f"lambda_selected={lambda_star:.4g} binds at grid edge "
                f"for fold {fold.fold_id} "
                f"(horizon={schedule.horizon}, "
                f"schedule={schedule.schedule_type}); "
                "widen grid via S-2 trigger if >10% rate across folds",
                stacklevel=2,
            )

        results.append(RidgeFitResult(
            fold_id=fold.fold_id,
            horizon=schedule.horizon,
            schedule_type=schedule.schedule_type,
            lambda_selected=lambda_star,
            lambda_grid=lambda_grid,
            lambda_log10_sd_across_5fold=lambda_log10_sd,
            coefficient_sign_flip_rate=0.0,  # populated post-loop (Phase 5)
            coef=beta,
            intercept=alpha,
            forecast_train=forecast_train,
            forecast_test=forecast_test,
            r_squared=r_squared,
            r_squared_oos=r_squared_oos,
            residual_se_hac=residual_se_hac,
            p_value_beta_hac=p_value_beta_hac,
            bootstrap_residual_se_distribution=bootstrap_dist,
            bootstrap_block_size=primary_block_size,
            hac_maxlags=horizon_months - 1,
            n_train_obs=n_train,
            n_test_obs=n_test,
            n_eff_nonoverlap_train=n_eff_train,
            grid_edge_bind=grid_edge_bind,
            block_size_sensitivity_se=block_size_sensitivity_map,
            hac_bandwidth_sensitivity_se=hac_bandwidth_sensitivity,
            fit_timestamp=fit_ts,
            inner_cv_scaler_recomputed=True,  # KICK-4: Task A parity per AP-AUTH-53 step #3
            bootstrap_diagnostics=bootstrap_diag,  # KICK-5: primary call diagnostics per AP-AUTH-54
            block_size_sensitivity_diagnostics=block_size_sensitivity_diag_map,  # KICK-5: per-sensitivity-size diagnostics
            inference_label="forecast_vs_realized",  # KICK-6: p_value_beta_hac is univariate calibration regression diagnostic, NOT Ridge per-feature inference; AP-AUTH-54 step #2
        ))

    # Post-pass: coefficient_sign_flip_rate vs immediately-prior outer fold
    # (Phase 5 portion; left at 0.0 for fold 0). Stored on the frozen
    # dataclass via ``dataclasses.replace``.
    if len(results) >= 2:
        updated: list[RidgeFitResult] = [results[0]]
        for i in range(1, len(results)):
            b_curr = results[i].coef
            b_prev = results[i - 1].coef
            flips = float(np.mean(
                (np.sign(b_curr) != np.sign(b_prev)).astype(float)
            ))
            updated.append(replace(results[i], coefficient_sign_flip_rate=flips))
        results = updated

    return tuple(results)


__all__ = [
    "BOOTSTRAP_ITERATIONS_DEFAULT",
    "LAMBDA_GRID_DEFAULT",
    "RidgeFitResult",
    "fit_return_forecast_task_b1",
]
