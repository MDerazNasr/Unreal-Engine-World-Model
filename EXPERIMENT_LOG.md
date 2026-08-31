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
Status: in progress; acquisition, static API audit, unmodified locomotion, isolated plugin build, and live sample module-load gate complete; programmatic control not yet tested

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
- The candidate described the UI warning as running low on memory; exact source/UI wording is still not captured. The engine log contains no out-of-memory, video-memory-exhaustion, or texture-pool-over-budget error.
- First-load work included a 6000×6000 texture build with a 2404 MB working-memory estimate and extensive animation compression/shader compilation. Unreal initially reported an 8601 MB texture budget and later a 1000 MB streaming-pool size.
- At diagnosis time Unreal Editor resident memory was approximately 0.9 GB; macOS reported 22% system memory free and no throttled pages. These observations do not identify the earlier warning's exact source.

Preliminary interpretation: Installation compatibility and baseline locomotion are verified, and UE 5.8.2 exposes all essential command and observation primitives. The memory warning is an open operational risk, not currently evidence of an engine failure. Runtime feasibility remains unproven until plugin compilation, command echo, executed movement, reset, and episode logging pass.

Empty-plugin build gate:

- Candidate approved D-011 after the design explanation.
- Implementation/evidence commit: `d2218fe` (`Add compiled MotionWorld Unreal plugin`).
- Added a behavior-free runtime module under `unreal/Plugins/MotionWorld` with only `Core`, `CoreUObject`, `Engine`, and `Mover` dependencies.
- First strict `BuildPlugin` attempt under `/tmp` compiled source but failed at link because UE's build accelerator retained `/tmp` while Clang resolved temporary object paths under `/private/tmp`.
- Retrying with the canonical `/private/tmp` package path succeeded for universal Mac Editor Development, Game Development, and Game Shipping targets.
- The packaged editor library is a universal Mach-O containing `arm64` and `x86_64`; disposable package size is 956 KiB; SHA-256 is `2b4cb48f0b86e683f0576f80a45f952ae9100074601c6e85f5cfc3b0e0ececc1`.
- Strict-includes mode disabled unity builds and precompiled-header shortcuts, so the tiny module had to be self-contained.
- UE emitted one unrelated warning for a missing `MetalShaderConverter/include/metal_irconverter_ext` engine directory during game builds; both builds still succeeded. This warning is recorded and not attributed to MotionWorld.

Live sample integration gate (2026-08-31):

- Copied only the tracked, behavior-free MotionWorld plugin into the local Game Animation Sample and explicitly enabled it in the local project descriptor. A recoverable pre-edit descriptor backup was retained outside the repository.
- Built the actual `GameAnimationSampleEditor` target in Development configuration for universal Mac (`arm64+x86_64`) with hot reload and UBA disabled. The build completed successfully in 36.35 seconds across 19 actions.
- The deployed MotionWorld editor library is a universal Mach-O; SHA-256 is `22925a5d59592e1d0af2f2bbd0f6c0fa2bca8922ae5b327e6919a4e5162f118d`.
- Reopened the sample. Its startup log records both plugin mounting and `InternalLoadLibrary: 'MotionWorld'`, followed by engine initialization and Map Check with 0 errors and 0 warnings.
- The plugin still contains no control, observation, reset, or logging behavior. Candidate confirmation that ordinary Play-In-Editor movement remains unchanged is the final pass-through check for this gate.
- The candidate subsequently confirmed ordinary movement and turning remained unchanged with the plugin enabled. The pass-through gate therefore passes.

Command-echo compile gate (2026-08-31):

- Added an opt-in `UMotionWorldBridgeComponent` implementing `IMoverInputProducerInterface`; automation defaults off.
- Added a pure command sanitizer that rejects NaN/infinity, projects to XY, and clamps magnitude without changing planar direction. The raw Unreal probe uses world-space cm/s; it does not yet implement the specification's character-local model boundary.
- Added Unreal automation cases for zero, exact maximum, oversized diagonal, reverse, vertical projection, and NaN rejection.
- The first strict compile exposed an invalid Unreal numeric-limits spelling and a runtime-selected `UE_LOG` severity; both were corrected narrowly. The final strict universal Mac Editor Development, Game Development, and Game Shipping package build succeeded in 43 seconds.
- Reviewer added an explicit game-thread guard because the current component fields are not a thread-safe mailbox. UE 5.8's standalone backend and global input-production switch both default to game-thread execution.
- Packaged editor library is a 365 KiB universal Mach-O (`arm64+x86_64`); SHA-256 is `ec46da5c14825bd0e0585ca8902c84ee0407551ef7b28437ee61d6bfe8abe111`.
- Copied the committed source into the closed local sample and verified tracked files match. The actual universal `GameAnimationSampleEditor` target compiled successfully in 32.20 seconds across 14 actions; deployed library SHA-256 is `9df746690ab4d6436c97f3ab01a7263454a58570d4f656d9f3c633497c38c9d8`.
- Ran `MotionWorld.Command.SanitizeWorldVelocity` through a headless, NullRHI actual-sample Editor process. The report records 1 succeeded, 0 failed, 0 warnings, and 0.0149 seconds test duration.
- At this build/test checkpoint, component attachment and a live `GetLastInputCmd()` match remained pending. No programmatic movement claim was made.

Attached-component pass-through gate (2026-08-31):

- Candidate added `Motion World Bridge` to the local `SandboxCharacter_Mover` Blueprint, left automation disabled, compiled/saved it, and confirmed ordinary movement still works. This local binary asset change is not committed.
- Three PIE starts log `MotionWorld bridge ready on 'SandboxCharacter_Mover_C_0'; automation=disabled, max_planar_speed=600.00 cm/s.` This proves the component exists on the playable pawn and reaches `BeginPlay`.
- No command-echo log is present, which is the correct default-off behavior. The next gate must enable one bounded fixed command and capture `match=true`.
- The low-memory warning reappeared. At inspection macOS reported 19% free memory and zero throttled pages; Unreal's resident RSS was approximately 563 MiB, but unified/GPU allocations can contribute to system pressure. The Unreal log still contains no OOM, video-memory-exhaustion, or texture-pool-over-budget error. Do not claim a specific warning source without its screenshot.

Fixed-command echo gate (2026-08-31):

- With automation enabled, PIE retained a zero velocity packet and multiple `(200, 0, 0)` cm/s world-space packets. Every captured echo reports velocity type implicitly through the match predicate and `requested == submitted == echoed`, with `match=true`.
- Candidate observed steady automatic motion without keyboard input. The pawn stopped against scene collision while the desired command remained active; pressing Space jumped over the obstruction and the same velocity command continued.
- Interpretation: the bridge intentionally replaces only `MoveInput`, preserving the sample's jump and facing fields. Collision demonstrates that requested velocity is an action, not the executed outcome; the transition model must predict the effect of dynamics and environment constraints.
- The final PIE initialization reports `automation=disabled`, verifying restoration of the safe default. No `Mover did not retain` or other MotionWorld error appears.
- One unrelated sample `LogStateTree` validation error appears in a later default-off session; it does not coincide with a MotionWorld failure and is not attributed to this component.
- D-012 passes. This proves the raw world-space Mover command seam, not yet the specification's character-local action conversion or authoritative state stream.

Reviewer findings: The sample pawn is not `AMoverExamplesCharacter`; it is an `APawn` Blueprint with its own large input graph. Calling the MoverExamples `RequestMoveByVelocity` helper would therefore be an incorrect integration assumption. An isolated input-producer component is the smallest source-controlled seam, but its ordering assumption must be tested explicitly. Do not diagnose or tune around the memory warning until its exact text or screenshot identifies whether it is a macOS, Metal/RHI, texture-streaming, or editor warning.

Decision/next action: Add the smallest finalized authoritative-state sample with explicit world/local frames, units, validity, and a monotonic sample sequence. Verify that in memory and through a throttled diagnostic log before adding episode file logging or reset behavior. Keep input and state responsibilities separately testable. Treat the low-memory warning as an operational risk; its originating UI remains unconfirmed without a screenshot.

Character-local adapter compile gate (2026-08-31):

- Added pure local-to-world and world-to-local planar velocity rotations using Unreal yaw in degrees; the bridge obtains yaw from `FMoverDefaultSyncState`.
- Character-local (`+X` forward, `+Y` right) is the default command frame. Direct world mode remains explicit for diagnostics and backward comparison.
- Added compiled cardinal-angle, local-right, vertical-projection, and arbitrary-angle round-trip automation checks.
- Reviewer required echo success to include finite-input and resolved-frame predicates, preventing a fail-closed zero packet from appearing valid merely because zero echoed correctly.
- Strict universal Mac Editor Development, Game Development, and Game Shipping package builds pass.
- Deployed committed source into the closed sample and verified tracked-file parity. The actual universal `GameAnimationSampleEditor` target built successfully in 18.02 seconds; deployed editor library SHA-256 is `fa5faa8a2b83a63cf75b86c22d9bb43be86589300f0ad4ab60617f4de88c9b0a`.
- Headless actual-sample execution ran the entire MotionWorld namespace: 2 succeeded, 0 failed, 0 warnings, total 0.0322 seconds. Both the sanitizer and coordinate round-trip/cardinal tests pass together.
- At one unchanged initial facing, the candidate ran local forward `(200, 0, 0)` cm/s and local right `(0, 200, 0)` cm/s and observed steady automatic paths approximately 90 degrees apart. The candidate then restored automation disabled and the local request to zero.
- The retained runtime log independently captures the right trial at authoritative yaw 0 degrees: requested local `(0, 200, 0)` cm/s resolved and echoed as world `(0, 200, 0)` cm/s with `match=true`.
- The forward trial was candidate-observed but is not separately present in the current runtime log. Its exact yaw-0 mapping is covered by the executed cardinal-angle automation test; it is not labeled as separately log-captured.
- The combined compiled, headless, logged, and visual evidence is sufficient for D-013 to pass.

Artifacts: `DECISIONS.md` D-011/D-012/D-013, `THEORY.md` sections 11-13, `unreal/Plugins/MotionWorld`, the Sunday runbook API audit, `theory/D011_UNREAL_BRIDGE_THEORY.tex`, and `output/pdf/D011_UNREAL_BRIDGE_THEORY.pdf`.
