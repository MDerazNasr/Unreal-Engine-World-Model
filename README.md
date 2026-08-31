# MotionWorld

MotionWorld is an action-conditioned residual state-space world model for real-time character control in Unreal Engine. A compact learned model corrects a faithful, inexpensive character predictor so that model-predictive control can evaluate many candidate futures without cloning the full engine simulation.

The project is being built as a reproducible applied-ML research demonstration. Its central claim is deliberately causal:

> Nominal prediction is wrong -> the residual predicts that error -> the planner selects a different action -> same-seed Unreal execution improves.

## Living documents

- [PROJECT_SPEC.md](PROJECT_SPEC.md) - exact system contract and acceptance criteria
- [PROJECT_PLAN.md](PROJECT_PLAN.md) - deadline-adjusted execution plan, gates, branches, and deliverables
- [CHECKLIST.md](CHECKLIST.md) - canonical atomic build, evidence, packaging, and interview-readiness checklist
- [THEORY.md](THEORY.md) - equations, hand calculations, assumptions, and teaching notes
- [DECISIONS.md](DECISIONS.md) - design decisions and rejected alternatives
- [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) - hypotheses, configurations, results, and interpretations
- [INTERVIEW_DEFENSE.md](INTERVIEW_DEFENSE.md) - difficult questions and evidence-backed answers

## Active runbook

- [Sunday 30 August - Unreal feasibility](runbooks/2026-08-30-sunday.md)

## Python environment

MotionWorld uses the project-local Python 3.12 environment resolved by `uv`. Install `uv`, then
recreate the exact locked environment with:

```bash
uv sync --frozen --python 3.12
uv run python scripts/verify_environment.py
uv run pytest
uv run ruff check .
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

No positive result is assumed. A reproducible negative result with a clear diagnosis is a valid research outcome.
