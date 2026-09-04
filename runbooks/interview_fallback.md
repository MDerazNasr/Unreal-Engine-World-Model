# Interview fallback demo runbook

Use this when live Unreal or a Python service is unreliable. Target duration: 75–90 seconds.

## Before the call

- Open `docs/INTERVIEW_PACKAGE.md` at the evidence ladder.
- Open the architecture SVG and the three plots in the sequence below.
- Keep the repository at the release-candidate commit with a clean working tree.
- Do not open or generate final-test episodes 5301/5302 during rehearsal.

## Spoken sequence

**0–15 seconds — hypothesis and boundary**

“MotionWorld asks whether a cheap learned residual can correct a faithful Unreal character model
well enough to change short-horizon control. Unreal remains ground truth; Python predicts and plans.”

Show `artifacts/interview/architecture.svg`.

**15–35 seconds — prediction evidence**

“I split whole episodes, fit normalization on training only, and evaluated recursively without
teacher forcing. The no-history residual consistently reduces the tail error at 0.5, 1.0, and
1.5 seconds. Four-step history was weaker, so I retained that negative result.”

Show `artifacts/residual/recursive_001/recursive_comparison.png`.

**35–55 seconds — planning causality and risk**

“Nominal and residual MPC share state, cost, horizon, budget, seed, and the exact first candidate
population. They select different first actions. Cross-evaluation shows severe disagreement, so I
call this decision relevance—not control success—and treat planner exploitation as a risk.”

Show `artifacts/planning/offplan_001/offline_paired_planner.png`.

**55–75 seconds — honest failure**

“The nominal planner passes 100 ms p95, but the residual is about 169 ms and misses all deadlines.
I prospectively tested smaller search budgets and smaller networks; neither passed quality and
runtime together. I did not relax the gates afterward.”

Show `artifacts/planning/budget_sweep_001/budget_sweep.png`, then
`artifacts/residual/compression_001/width_sweep.png`.

**75–90 seconds — conclusion**

“The strongest supported result is better bounded validation prediction and a changed fair offline
decision. The missing decisive link is same-seed Unreal control. My next step is a deadline-safe
live loop and frozen paired execution, not a stronger claim.”

## If challenged

- “Why not use the lower-cost residual plan as proof?” — Cost is computed by its own model; Unreal
  must adjudicate.
- “Why not accept the smaller model?” — One passed recursive accuracy but all failed reference-model
  plan cross-evaluation and runtime.
- “Why no final test?” — Test data stays sealed until the system and claims are frozen; opening it
  now would convert it into validation data.
- “Is this still a world model?” — It is an action-conditioned learned transition correction used
  for recursive counterfactual state rollouts; it is narrow, not a visual foundation model.
