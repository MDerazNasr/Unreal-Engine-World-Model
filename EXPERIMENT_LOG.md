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

### FEAS-000 - Python environment bootstrap

Date/time: 2026-08-30
Owner: Mohamed Deraz Nasr with Codex Builder/Reviewer passes
Status: completed

Question: Can the Python numerical/test environment be recreated on the interview machine with a fixed Python and dependency lock?

Hypothesis: A Python 3.12 `uv` project can install the standard ML/test stack on Apple Silicon, import every required package, run deterministic CPU smoke calculations, expose MPS capability, and pass tests/lint.

Controls/fairness constraints: Project-local environment; committed Python constraint and lockfile; CPU is the deterministic reference; MPS availability is reported separately.

Git commit: `fbe0ade` on `feature/unreal-feasibility`.

Hardware/software: Apple M4, 16 GB RAM, macOS 26.5.2 arm64, Python 3.12.13, `uv` 0.12.2, PyTorch 2.13.0, NumPy 2.5.2, SciPy 1.18.1, scikit-learn 1.9.0, Matplotlib 3.11.1, PyYAML 6.0.3.

Procedure:

1. Resolve/install from `pyproject.toml` using Python 3.12 and write `uv.lock`.
2. Re-run `uv sync --frozen --python 3.12` so dependency resolution cannot change.
3. Run `scripts/verify_environment.py`.
4. Run `pytest -q` and `ruff check .` through `.venv/bin`.
5. Re-run the verifier outside the sandbox to distinguish real MPS capability from sandbox visibility.

Results: Dependency lock created; frozen synchronization checked all 35 packages without changing resolution; required packages imported; three tests passed (latest run: 5.72 s); lint and `git diff --check` passed; CPU seeded tensor calculation repeated exactly; MPS is built and available outside the sandbox.

Interpretation: The Python environment gate is ready for deterministic CPU development with optional measured MPS training. The sandbox can report MPS unavailable even when the host supports it, so hardware claims must use the validated host result.

Reviewer findings: `uv run` inside the restricted sandbox cannot access the default user cache, but direct `.venv/bin` execution succeeds. This is an execution-environment restriction, not a project dependency failure; normal README commands remain valid in a user terminal.

Decision/next action: Accept D-010. Commit the environment/skeleton slice, then define typed protocol contracts while Unreal 5.8 installs.

Artifacts and reproduction command: `pyproject.toml`, `uv.lock`, `.python-version`, `scripts/verify_environment.py`, `tests/unit/test_environment.py`; commands are documented in `README.md`.

### FEAS-001 - Unreal desired-velocity and state feasibility

Date/time: 2026-08-30
Owner: Mohamed Deraz Nasr with Codex Mentor/Reviewer API audit
Status: in progress; acquisition, static API audit, and unmodified locomotion complete; programmatic control not yet tested

Question: Can the UE 5.8 Game Animation Sample accept programmatic desired velocity, expose finalized authoritative movement state, reset episode state, and produce a valid deterministic episode log?

Hypothesis: A small project plugin component can supply `EMoveInputType::Velocity` through Mover's existing input-production path and sample finalized `FMoverDefaultSyncState` without modifying Epic sample assets.

Controls/fairness constraints: Keep the downloaded sample unmodified until a minimal plugin compiles; distinguish static API evidence from runtime evidence; treat the Mover updated component/sync state as authoritative and the primary visual component as diagnostic; do not mark locomotion, reset, or logging complete without runtime proof.

Verified environment:

- UE 5.8.2, changelist 56702186, compatible changelist 55116800, promoted `++UE5+Release-5.8` build.
- `GameAnimationSample.uproject` has `EngineAssociation` 5.8 and enables Mover, ChaosMover, NetworkPrediction, MoverExamples, PoseSearch, MotionWarping, and Locomotor.
- The project contains a universal Mac `GameAnimationSample` editor binary but no visible project `Source/` directory.
- Exact local engine and sample paths are stored only in private task memory.

Static API/asset audit:

- Playable asset: `/Game/Blueprints/SandboxCharacter_Mover`; native parent `APawn`; implements `IMoverInputProducerInterface`; owns `CharacterMoverComponent`.
- Walking asset: `/Game/Blueprints/MovementModes/BP_MovementMode_Walking`; native parent `USmoothWalkingMode`.
- Command type: `FCharacterDefaultInputs` in module `Mover`; `SetMoveInput(EMoveInputType::Velocity, DesiredVelocity)` uses units per second and is world-space unless movement-base-relative input is enabled.
- Extension point: `UMoverComponent::BeginPlay` gathers owner components implementing `IMoverInputProducerInterface`; `ProduceInput` invokes gathered producers.
- Final sampling point: `UMoverComponent::OnPostFinalize`, guaranteed on the game thread after state finalization.
- Authoritative state: `FMoverDefaultSyncState::{GetLocation_WorldSpace, GetVelocity_WorldSpace, GetOrientation_WorldSpace}` plus angular velocity in the same state; `GetPrimaryVisualComponent()` is the animation/visual diagnostic boundary.
- Installed source evidence: `Mover/Public/MoverComponent.h`, `Mover/Private/MoverComponent.cpp`, `Mover/Public/MoverDataModelTypes.h`, and `Mover/Public/DefaultMovementSet/Modes/SmoothWalkingMode.h`.

Runtime baseline evidence:

- The candidate entered Play In Editor and manually verified that the unmodified character moves and turns.
- The log identifies `SandboxCharacter_Mover_C_0`, reports a 60 Hz PIE world, no Blueprint recompilation, and latest PIE startup in 0.498 s.
- The candidate reported a memory warning. Its exact UI text is not yet captured. The engine log contains no out-of-memory, video-memory-exhaustion, or texture-pool-over-budget error.
- First-load work included a 6000×6000 texture build with a 2404 MB working-memory estimate and extensive animation compression/shader compilation. Unreal initially reported an 8601 MB texture budget and later a 1000 MB streaming-pool size.
- At diagnosis time Unreal Editor resident memory was approximately 0.9 GB; macOS reported 22% system memory free and no throttled pages. These observations do not identify the earlier warning's exact source.

Preliminary interpretation: Installation compatibility and baseline locomotion are verified, and UE 5.8.2 exposes all essential command and observation primitives. The memory warning is an open operational risk, not currently evidence of an engine failure. Runtime feasibility remains unproven until plugin compilation, command echo, executed movement, reset, and episode logging pass.

Reviewer findings: The sample pawn is not `AMoverExamplesCharacter`; it is an `APawn` Blueprint with its own large input graph. Calling the MoverExamples `RequestMoveByVelocity` helper would therefore be an incorrect integration assumption. An isolated input-producer component is the smallest source-controlled seam, but its ordering assumption must be tested explicitly. Do not diagnose or tune around the memory warning until its exact text or screenshot identifies whether it is a macOS, Metal/RHI, texture-streaming, or editor warning.

Decision/next action: Candidate reviews proposed D-011 and supplies the exact memory-warning text or screenshot. After approval, stop PIE, scaffold and compile the empty plugin, then test the command echo before adding logging or reset logic.

Artifacts: `DECISIONS.md` D-011 and the Sunday runbook API audit.
