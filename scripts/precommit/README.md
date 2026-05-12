# Pre-commit hooks for L5 build phase

Two local Python validators enforcing build-phase audit discipline:

| Hook | AP | Scope | Detail |
|---|---|---|---|
| `validate_dual_grep_in_verification.py` | AP-AUTH-41 v6 STRENGTHENED | `docs/**/*.md` verification tables | Every alignment claim must include BOTH `pos:` and `neg:` grep evidence per anchor |
| `validate_no_cumulative_arithmetic.py` | AP-AUTH-42 NEW v6 | `docs/**/*.md` active proof-contract prose | Hard-coded cumulative arithmetic (e.g., `602 + 78 = 680`) is forbidden; use symbolic wording |

## Install (one-time per clone or worktree)

```bash
python scripts/precommit/install_hook.py
```

Idempotent. Writes `<git-dir>/hooks/pre-commit` that invokes both validators
on staged `docs/**/*.md` files.

Pre-commit framework users: `.pre-commit-config.yaml` is in the repo root
for `pre-commit install` (forward-compat; framework not currently a
project dependency).

## Self-test

```bash
python scripts/precommit/tests/run_hook_self_tests.py
```

Runs each validator against its paired pass/fail fixture; expects 4/4 pass.

## Bypass policy

Per Strategic prompt (L5-A code execution §3):
> PRE-COMMIT BYPASS IS A CIRCLE-OF-FIRE OFFENSE. Never use `--no-verify`.
> If hook fires falsely, fix hook (AP register addition); do NOT bypass.

## Origin

Build plan ref: `claude/layer-5-build-plan @ 32cce8b ITEM 6`.
v6 spec ref: `LAYER_5_BUILD_SPEC.md @ 9f848bb` §12 (AP-AUTH-41 v6 + AP-AUTH-42 NEW).
