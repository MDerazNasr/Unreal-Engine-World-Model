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

No positive result is assumed. A reproducible negative result with a clear diagnosis is a valid research outcome.
