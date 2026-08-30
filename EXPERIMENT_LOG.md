# MotionWorld Experiment Log

No result belongs in the interview package unless it has an entry here and points to raw output, a frozen configuration, code revision, and seed list.

## Dataset and evaluation rules

- Split by complete episode, arena seed, obstacle layout, and movement regime.
- Freeze validation and test manifests before model selection.
- Never tune scenario geometry or cost weights on test seeds.
- Run nominal and residual controllers with identical candidate samples and budgets.
- Preserve negative results and failed runs.
- Mark exploratory plots clearly; do not promote them into final results silently.

## Experiment template

```text
Experiment ID:
Date/time:
Owner:
Status: planned | running | completed | invalid

Question:
Hypothesis:
Independent variable:
Dependent variables:
Controls/fairness constraints:
Dataset/split manifest:
Scenario seeds:
Config path and hash:
Checkpoint hash:
Git commit:
Hardware/software:

Procedure:
Expected failure signatures:
Results:
Uncertainty/statistics:
Interpretation:
Alternative explanations:
Reviewer findings:
Decision/next action:
Artifacts and reproduction command:
```

## Planned experiment registry

| ID | Question | Gate | Status |
|---|---|---|---|
| FEAS-001 | Can Unreal accept desired velocity, expose post-movement state, reset, and log deterministically? | Day 1 | Planned |
| NOM-001 | Does the nominal implementation pass hand-calculated and timestep tests? | Day 2 | Planned |
| NOM-002 | Is meaningful, systematic residual error present in Unreal rollouts? | Day 2 | Planned |
| RES-001 | Does residual learning improve held-out recursive prediction over nominal? | Day 3 | Planned |
| RES-002 | Does four-step history improve post-perturbation prediction over no history? | Day 3 | Planned |
| CEM-001 | Does fixed-seed CEM recover known optima in toy costs deterministically? | Day 4 | Planned |
| CTRL-001 | Does residual MPC improve the paired timed-gate outcome over nominal MPC? | Day 5 | Planned |
| CTRL-002 | Does history improve paired post-push recovery? | Day 5 | Planned |
| OOD-001 | Where does performance degrade under held-out movement parameters? | Day 5 | Planned |
| EXPLOIT-001 | Is selected-plan predicted return more optimistic than realized return? | Day 5 | Planned |
| RUNTIME-001 | Does the exact final planner meet median/p95/deadline requirements? | Day 6 | Planned |

## Artifact manifest

Final experiments will produce:

- immutable dataset split manifests;
- YAML configuration files;
- normalization statistics;
- model checkpoints and hashes;
- per-episode raw metrics;
- aggregate tables and bootstrap intervals;
- prediction plots;
- latency traces;
- video and exact reproduction commands.

Large raw datasets and checkpoints may remain untracked, but their hashes, provenance, and regeneration commands must be committed.

## Session entries

### PLAN-001 - Research and engineering protocol

Date/time: 2026-08-29  
Status: completed

Question: What process will keep the one-week implementation understandable, reviewable, and defensible?

Result: Adopted living documents, an Obsidian task handoff, gated component development, short-lived milestone branches, small tested commits, explicit Builder/Reviewer/Examiner passes, and stop/go criteria for every day.

Interpretation: Planning documentation is part of experimental validity, not administrative polish.

Artifacts: `PROJECT_SPEC.md`, `PROJECT_PLAN.md`, `THEORY.md`, `DECISIONS.md`, `EXPERIMENT_LOG.md`, `INTERVIEW_DEFENSE.md`.

### PLAN-002 - Deadline and environment inventory

Date/time: 2026-08-30
Status: completed

Question: What calendar and machine constraints determine the feasible critical path?

Result: The hard deadline is Friday 4 September at 15:00 Europe/Copenhagen. The machine is Apple M4 with 16 GB memory, Xcode 26.6, Apple Clang 21, `uv` 0.12.2, Python 3.12.13, CMake 4.2.1, and about 105 GiB free disk. Epic Games Launcher is present, but no `UnrealEditor.app` or Game Animation Sample was detected. Default Python 3.14.6 does not contain PyTorch.

Interpretation: The seven logical stages must be compressed into five build days plus interview morning. Unreal installation/sample acquisition is the immediate critical-path dependency. Python work will use a project-local 3.12 environment and proceed only on independent theory/contracts while installation is resolved.

Reviewer finding: Without an explicit evidence ladder, schedule pressure could lead to presenting a synthetic causal demonstration as engine evidence. The plan now distinguishes five evidence levels and requires the package to state the highest achieved level.

Artifacts: `PROJECT_PLAN.md`, decisions D-008 and D-009.
