# MotionWorld

MotionWorld is an action-conditioned residual state-space world model for character control in
Unreal Engine. A learned model corrects a faithful, inexpensive character predictor so that
model-predictive control can evaluate many candidate futures without cloning the full engine.

**Evidence achieved:** the UE 5.8.2 movement/reset/logger bridge works; episode-safe train and
validation data were captured; a residual MLP improves held-out recursive prediction; and a fair
offline CEM comparison proves that the model changes selected actions. **Not achieved:** no live
nominal-versus-residual MPC execution has been run, the residual planner misses its 100 ms p95
deadline, and no final-test episode has been opened. The project therefore makes no control-win
claim.

The project is being built as a reproducible applied-ML research demonstration. Its central claim is deliberately causal:

> Nominal prediction is wrong -> the residual predicts that error -> the planner selects a different action -> same-seed Unreal execution improves.

The first three links have bounded evidence. The last link remains unproven. See
[INTERVIEW_PACKAGE.md](INTERVIEW_PACKAGE.md) for the concise evidence map and fallback demo.

## Living documents

- [PROJECT_SPEC.md](PROJECT_SPEC.md) - exact system contract and acceptance criteria
- [PROJECT_PLAN.md](PROJECT_PLAN.md) - deadline-adjusted execution plan, gates, branches, and deliverables
- [RECOVERY_CHECKLIST.md](RECOVERY_CHECKLIST.md) - active dependency-ordered plan for completing the live causal-control target
- [CHECKLIST.md](CHECKLIST.md) - historical original-plan checklist retained for audit and traceability
- [THEORY.md](THEORY.md) - equations, hand calculations, assumptions, and teaching notes
- [DECISIONS.md](DECISIONS.md) - design decisions and rejected alternatives
- [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) - hypotheses, configurations, results, and interpretations
- [INTERVIEW_DEFENSE.md](INTERVIEW_DEFENSE.md) - difficult questions and evidence-backed answers

## Active runbook

- [Sunday 30 August - Unreal feasibility](runbooks/2026-08-30-sunday.md)
- [Interview fallback demo](runbooks/interview_fallback.md)

## Python environment

MotionWorld uses the project-local Python 3.12 environment resolved by `uv`. Install `uv`, then
recreate the exact locked environment with:

```bash
uv sync --frozen --python 3.12
uv run python scripts/verify_environment.py
uv run pytest
uv run ruff check .
uv run python scripts/verify_interview_package.py
```

Unit-test oracles run on CPU by default for deterministic comparison. MPS availability is reported
separately and may be used for measured training experiments once numerical behavior is validated.

## Candidate study material

- [D-011 Unreal bridge theory](output/pdf/D011_UNREAL_BRIDGE_THEORY.pdf) - compiled five-page
  handout covering the integration boundary, equations, assumptions, failure modes, memory-warning
  classification, acceptance tests, and required interview teach-back.
- [D-011 LaTeX source](theory/D011_UNREAL_BRIDGE_THEORY.tex)

## Unreal plugin

The source-controlled [MotionWorld plugin](unreal/Plugins/MotionWorld/README.md) is kept separate
from the licensed Game Animation Sample. Its opt-in command bridge, finalized-state sampler,
fail-closed causal-transition contract, and bounded in-memory episode recorder have passed strict
UE 5.8.2 builds for universal Mac Editor Development, Game Development, and Game Shipping targets.
The recorder's live chronology gate captured 922 consecutive action-state transitions with no
rejected pair or capacity loss.
A Mover-owned deterministic character reset and fail-closed finalized-state verifier pass strict
builds, actual-sample automation, and two live same-session resets with identical verified seed
states and no transition crossing either reset boundary.
An opt-in atomic JSON Lines exporter and strict Python validator pass isolated, actual-sample, and
live-file gates. Episode 1801 exported 458 accepted transitions with zero rejection/capacity loss;
the independent loader validated every row and the completeness footer.
Schema version 2 remains backward-compatible with that version-1 evidence and adds optional timed-
gate configuration, per-transition analytic obstacle state/event labels, and a reconciled terminal
summary. Both Unreal and Python independently reject schedule, crossing, timeout, or count drift.

No positive result is assumed. A reproducible negative result with a clear diagnosis is a valid research outcome.

## Provenance and licensing

The repository contains only project-specific source, small derived evidence, configurations, and
documentation. Epic's licensed Game Animation Sample, Unreal generated directories, and raw local
episode captures are excluded. Reproducing Unreal evidence requires acquiring the Game Animation
Sample separately through Epic and copying the source-controlled plugin into that local project.
