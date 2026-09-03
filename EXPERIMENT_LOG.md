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
| NOM-002 | Is meaningful, systematic residual error present in Unreal rollouts? | Day 2 | Completed: bounded negative result |
| NOM-CAUSAL-001 | Does a current-snapshot nominal expose causal parameter-schedule mismatch? | Day 2 | Completed |
| VAR-DATA-001 | Does the deterministic schedule produce valid stop/reverse/turn coverage? | Day 2 | Completed |
| NOM-ROLL-001 | How does faithful nominal error compound over 0.5/1.0/1.5 s? | Day 2 | Completed |
| FACING-001 | Does an explicit antipodal tie-break remove the known angular rollout spike? | Day 2 | Completed |
| PERT-SCHEDULE-001 | Can one controlled Mover velocity kick be scheduled without frame-skip or duplicate ambiguity? | Day 2 | Completed |
| RES-CONTRACT-001 | Is the planar residual target causal, invertible, and exactly zero-identical? | Day 3 | Completed |
| RES-DATASET-001 | Are residual examples consecutive, episode-safe, and free of future/event leakage? | Day 3 | Completed |
| RES-MODEL-SMOKE-001 | Do matched MLPs satisfy size, fallback, shape, gradient, and seed invariants? | Day 3 | Completed |
| RES-COLLECTION-001 | Does a distinct schedule reproduce valid causal residual structure? | Day 3 | Completed: five train/two validation accepted |
| RES-001 | Does residual learning improve held-out recursive prediction over nominal? | Day 3 | Completed: no-history gate passed |
| RES-002 | Does four-step history improve post-perturbation prediction over no history? | Day 3 | Completed: bounded negative result |
| CEM-001 | Does fixed-seed CEM recover known optima in toy costs deterministically? | Day 4 | Completed: core optimizer accepted |
| OFFPLAN-001 | Does the frozen residual change fair CEM rankings, and what model-risk does that reveal? | Day 4 | Completed: offline integration accepted; live claim blocked |
| CEM-BUDGET-001 | Can a smaller CEM budget meet 100 ms without exceeding the frozen validation-quality loss? | Day 4/6 | Completed: no budget eligible |
| CTRL-001 | Does residual MPC improve the paired timed-gate outcome over nominal MPC? | Day 5 | Planned |
| CTRL-002 | Does history improve paired post-push recovery? | Day 5 | Planned |
| OOD-001 | Where does performance degrade under held-out movement parameters? | Day 5 | Planned |
| EXPLOIT-001 | Is selected-plan predicted return more optimistic than realized return? | Day 5 | Planned |
| RUNTIME-001 | Does the exact frozen offline planner meet the 100 ms compute deadline? | Day 4/6 | Completed: nominal passes; residual fails |

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

Authoritative-state isolated compile gate (2026-08-31):

- Added a version-1 reflected state packet and a pure builder, separately from episode persistence and reset.
- The packet names all units and frames and carries finalized global position, full world velocity, local planar velocity, yaw plus sine/cosine, world angular velocity, movement mode, end-of-step time, step duration, Mover step frame, resimulation status, validity, and monotonic callback sequence.
- The bridge samples the sync state passed directly into `OnPostFinalize`, including when automation is disabled. It retains the latest sample in memory and logs the first valid sample plus every configurable 60th sample by default.
- Reviewer preserved callback sequence separately from Mover chronology because finalization can include resimulation. Episode logging must later reject or replace duplicate/rewound simulation times rather than assuming callbacks are unique transitions.
- Invalid source, time, timestep, or non-finite state fails closed to `valid=false` and zero state values.
- Compiled automation covers a hand-calculated yaw-90 observation, full-world versus planar-local velocity, yaw normalization and sine/cosine, sequence advancement, missing source, NaN rejection, and zero timestep.
- Strict universal Mac Editor Development, Game Development, and Game Shipping package builds pass in 46 seconds. The editor library contains `arm64` and `x86_64`; SHA-256 is `7ddf3507039171bd6f8181eed2ed9bed432f995550e952bc7373efff84d230c8`.
- Copied only committed plugin source into the closed sample and verified source parity. The actual universal `GameAnimationSampleEditor` target built successfully in 17.84 seconds across 12 actions; deployed editor library SHA-256 is `f7f772ba23579628a7c8cf5ea8bfc1775a278f336849fa4ecf68fa982c0da2bd`.
- Headless NullRHI execution found all three MotionWorld tests and completed sanitizer, coordinate, and authoritative-state tests with `Result={Success}`. Map Check reported 0 errors and 0 warnings.
- A live PIE run with automation disabled emitted 13 throttled finalized samples spanning sequence 0-720, Mover step frame 1-721, and simulation time 0.071-39.317 seconds. An exact audit found zero invalid packets, resimulations, non-monotonic sequences/frames/times, or non-positive steps.
- Runtime states include rest, high-speed translation, turning, near-zero motion, and a transition from `Walking` to `Traversing` with world Z increasing from about 88 cm to 338 cm. At yaw approximately -45 degrees, world velocity `(266.25, -266.25)` cm/s becomes local planar velocity `(376.53, approximately 0)` cm/s, providing a live frame-consistency check.
- Reviewer limitation: periodic state alone cannot distinguish an obstacle stop from released input. This run captured traversal rather than a simple blocking collision. The earlier command-echo collision observation remains separate; later episode logging must pair every state with the applied action and event labels before making causal collision claims.
- D-014 passes. Episode identity, per-step persistence, reset, and animation-root diagnostics remain deliberately unimplemented.

Artifacts: `DECISIONS.md` D-011/D-012/D-013/D-014, `THEORY.md` sections 11-14, `unreal/Plugins/MotionWorld`, the Sunday runbook API audit, `theory/D011_UNREAL_BRIDGE_THEORY.tex`, and `output/pdf/D011_UNREAL_BRIDGE_THEORY.pdf`.

### Causal-transition contract isolated compile gate (2026-08-31)

- Added a version-1 reflected transition packet that names episode identity, transition sequence,
  previous/next finalized states, applied world/local desired velocity, measured start/end/delta
  time, automation provenance, validity, and rejection reason.
- The local action is computed with the previous state's yaw. The valid oracle uses previous yaw
  `90` degrees, next yaw `45` degrees, and world action `(0, 200, 0)` cm/s; the expected local action
  is `(200, 0, 0)` cm/s. This makes an endpoint-frame leakage bug visible.
- Reviewer requires sequence and available Mover frames to advance exactly once, time to increase,
  derived delta to agree with the next state's reported step within 1 ms, both states to be valid
  protocol-1 forward-simulation snapshots, and the action to be finite, planar desired velocity.
- Invalid candidates fail closed with explicit reasons. Focused cases cover missing identity,
  unsupported action semantics, NaN/infinity, vertical action, resimulation, gaps, frame metadata
  changes, invalid negative frames, repeated time, timestep mismatch, schema mismatch, and invalid
  state.
- Strict universal Mac Editor Development, Game Development, and Game Shipping package compilation
  succeeded. This proves type/API compatibility, not runtime capture. Actual-sample automation and
  the later `GetLastInputCmd()` recorder integration remain separate gates.
- Deployed only the committed plugin source into the closed Game Animation Sample and verified an
  empty follow-up `rsync` dry run. The actual universal `GameAnimationSampleEditor` target built in
  17.29 seconds. Its MotionWorld dylib contains `arm64` and `x86_64`; SHA-256 is
  `c1e9ca142d5e2bd9686235bac0fa22307567b1a8c2c19b9b9f1d78cf3c179856`.
- Headless NullRHI execution found exactly four MotionWorld tests. Sanitizer, coordinate, state, and
  causal-pairing suites each completed with `Result={Success}`, and the queue ended with `4 tests
  performed`. D-015 therefore passes as a pure contract. Live consumed-input pairing, episode
  buffering, persistence, and reset are still unimplemented and receive no credit from this test.

### In-memory episode recorder isolated compile gate (2026-08-31)

- UE 5.8 source audit confirms the simulation stores `StartData.InputCmd` as
  `CachedLastUsedInputCmd` and caches the timestep before the backend finalizes the frame and emits
  `OnPostFinalize`. This supports the intended prior-state / just-used-action / current-state join.
- Added an opt-in recorder with explicit episode identity, first-state seeding, attempted-pair
  sequence numbers, per-reason rejection counts, recovery seeding, a 4096-row default limit, and a
  stop-without-overwrite capacity policy. BeginPlay auto-start exists only as a disabled-by-default
  live-test convenience.
- A compiled test exercises inactive behavior, invalid IDs/capacities, seed semantics, exact causal
  endpoints and local action conversion, unsupported-action rejection, visible sequence gaps,
  recovery, capacity stop, episode restart, invalid seed handling, and resimulation de-seeding.
- Reviewer notes that Mover exposes the consumed packet but not producer identity. `automated=true`
  is therefore assigned only when the velocity packet matches MotionWorld's last finite submitted
  command while automation is enabled.
- Reviewer added an `EndPlay` stop-summary because the in-memory buffer is destroyed when PIE ends;
  this preserves the final observed/attempted/recorded/rejected/capacity counters in the log.
- Strict non-unity universal Mac Editor Development, Game Development, and Game Shipping builds
  pass. Actual-sample automation and a live episode are pending; no runtime pairing claim is made.
- Deployed only committed source into the closed sample and verified source parity. The actual
  universal Editor build passed in 96.55 seconds under high memory pressure. Its MotionWorld dylib
  contains `arm64` and `x86_64`; SHA-256 is
  `bc032b0a21f41b48df203fb98ba67075629c231f15e1f861d7664273208c7bad`.
- Headless NullRHI execution found exactly five MotionWorld tests. Command sanitization, coordinate
  conversion, episode recorder, authoritative state, and transition pairing all completed with
  `Result={Success}`; the queue ended with `5 tests performed`.
- Live PIE episode 1601 started with automation enabled and a character-local desired velocity of
  `(200, 0, 0)` cm/s. State sequence 0 seeded the recorder at Mover frame 1. The first accepted row
  paired state 0 to 1 with the consumed action resolving to world `(200, 0, 0)` cm/s; diagnostic
  rows remained consecutive through transition 899 / state 900.
- The EndPlay summary reconciled 923 observations into 922 attempted and 922 recorded transitions,
  with `rejected=0`, `rejected_seeds=0`, and `capacity_drops=0`. This passes the live chronology gate
  and accepts D-016. The roughly 52-second run remained below the 4096-row limit.
- Scope boundary: rows are retained only in memory and summarized to the Unreal log. Durable file
  persistence and deterministic reset are still unimplemented and receive no credit from this gate.
- Preserved evidence: `evidence/unreal/d016_episode_1601.log`, including the source-log SHA-256 at
  capture time.

### Verified Mover-owned character reset compile gate (2026-08-31)

- Added a pure reset target/verifier. It fails closed on invalid targets/tolerances/states,
  resimulation, position/yaw/linear-speed/angular-speed mismatch, and wrong movement mode. Its test
  also proves shortest-angle yaw wrapping and inclusive tolerance boundaries.
- Integrated an opt-in Mover reset lifecycle: stop the prior recorder, lock and zero the command,
  mark Smooth Walking's generated-move history stale, queue teleport then non-additive zero velocity
  in the anchor mode, and start a new episode only after a newer finalized state passes verification.
- Reviewer added fixed reset-frame facing intent, bounded verification failure, command-restoration
  deferral, rejection of episode start while reset is pending, and an explicit same-session proof
  sequence. When opted in, it resets into episode 1701, records 60 accepted transitions, then resets
  into 1702. Pre-reset anchor distance and post-reset residual errors are logged.
- Strict universal Mac Editor Development, Game Development, and Game Shipping builds pass. The
  packaged editor dylib contains `arm64` and `x86_64`; SHA-256 is
  `3dadef2b3927efe1e9b52e73d2b057c7f5c3e46c9d04e725a80ef6fa5c900a18`.
- The focused verifier executed successfully in a disposable host. The first launch attempt against
  `BuildPlugin`'s removed temporary `.uproject` was not a test failure; wrapping the packaged plugin
  in a disposable minimal host made the test executable.
- Copied only committed source into the closed Game Animation Sample and verified an empty rsync
  parity check. Its universal `GameAnimationSampleEditor` target built successfully in 36.93 seconds.
  The deployed editor dylib contains both architectures; SHA-256 is
  `56843d72210e04030e03f8979b291b454b9f55dbeb1d9e0e4d74300a5b9ff8e6`.
- Headless NullRHI execution found exactly six actual-sample MotionWorld tests. Command, coordinate,
  recorder, reset verifier, authoritative state, and causal pairing all completed with `Success`.
- Scope boundary: compilation and pure verification do not prove that queued effects reset the live
  sample. Two same-session PIE resets and their episode boundaries remain the D-017 acceptance gate.
- Preserved automation evidence: `evidence/unreal/d017_actual_automation.log`.

### D-017 live attempt 1 — proof trigger inactive (2026-08-31)

- Candidate observed one apparent teleport followed by the character stopping at an obstacle.
- Log audit shows this was the sample level's existing teleport dock, not MotionWorld: Mover warned
  that its simulated location near `X=1551.63 cm` disagreed with an out-of-band component location
  at `X=2500 cm`. No `MotionWorld reset`, episode 1701, or transition message was emitted.
- The bridge itself was active with automation enabled and local `(200, 0, 0) cm/s`; it captured the
  reset anchor and continued emitting valid finalized states. Therefore command/state integration
  did not fail, but the default-off live-test trigger was not enabled on the Blueprint class used to
  spawn the pawn.
- Asset inspection supports the configuration diagnosis: the saved Blueprint contains overridden
  command properties but no serialized `bRequestResetAfterWarmupOnBeginPlay` property name, which
  would be present if its value differed from the C++ default `false`.
- Result: invalid as reset evidence; D-017 remains open. Reconfigure the component on the
  `SandboxCharacter_Mover` Blueprint class, compile and save it, then rerun and require two verified
  MotionWorld reset messages plus clean episode 1701/1702 boundaries.

### D-017 live attempt 2 — accepted (2026-08-31)

- The candidate observed repeated returns to the anchor, followed by normal restored forward
  control. The later stop against an obstacle is expected because collision blocks executed motion
  while the open-loop controller continues requesting local-forward velocity.
- Reset 1701 was requested 483.813 cm from the anchor and reset 1702 was requested 509.037 cm from
  it. Each passed on the first newer finalized state at `(-795.49, 0.00, 88.27) cm`, yaw `0 deg`,
  mode `Walking`, with `0.000` position/yaw/linear-speed/angular-speed error.
- Episode 1701 seeded at state sequence 60, recorded transitions `60→61` through `119→120`, then
  stopped with `recorded=60`, `rejected=0`, `rejected_seeds=0`, and `capacity_drops=0` before the
  second reset was queued at state 121.
- Episode 1702 seeded from verified reset state 122; its first row was `122→123`. It ended with
  `recorded=1189`, `rejected=0`, `rejected_seeds=0`, and `capacity_drops=0`. Thus no accepted row
  bridges the old trajectory, teleport frame, or two episode identities.
- Interpretation: D-017's character-level deterministic reset gate passes. This does not yet claim
  reset of a timed gate, target, external actors, animation-graph history, random generators,
  learned observation history, or planner warm starts.
- Preserved evidence: `evidence/unreal/d017_live_reset_1701_1702.log`.

### D-018 atomic episode export compile/automation gate (2026-08-31)

- Added a schema-version-1 UTF-8 JSON Lines exporter with header, accepted transition records, and
  completeness footer. It streams one row at a time to a unique sibling temporary file and
  publishes with a no-replace move only after the complete file closes.
- The first focused execution rejected Unreal's project-relative automation path. This exposed a
  real portability defect because `ProjectSavedDir()` can also be relative. The exporter now
  canonicalizes internally; the unchanged test then reached all validation branches.
- A second focused execution found that an empty episode was classified as inconsistent stats
  before reaching its more precise `no_transitions` result. Validation order was corrected and the
  focused test passed.
- Runtime integration is opt-in. On normal stop or capacity stop it writes beneath
  `Saved/MotionWorld/Episodes` and reports result, row count, duration, and canonical path. Export
  is outside the per-frame callback path except at the terminal stop.
- The strict Python loader checks exact keys/types, finite numerics, protocol/schema versions,
  declared units/frames, chronology, local/world conversion, episode identity, shared endpoints,
  header/footer counts, and completeness. Eleven Python tests and Ruff pass.
- Strict universal Mac Editor Development, Game Development, and Game Shipping builds pass. The
  closed real sample source matches the repository, its universal Editor build passes, and all
  seven actual-sample MotionWorld tests complete with `Success`. Deployed dylib SHA-256 is
  `6de38f0d3f4f51aee3d0f6a545aa90a1ddf1df68b99e5c5b53b1338328941224`.
- Scope boundary: no real episode file has yet been produced. Target, obstacle, collision,
  termination, scenario seed, and animation diagnostics remain outside schema v1 until their
  authoritative sources exist.
- Preserved automation evidence: `evidence/unreal/d018_actual_automation.log`.

### D-018 live episode 1801 — accepted (2026-08-31)

- The opt-in bridge seeded episode 1801 at state sequence 0 / Mover frame 1 and stopped with 459
  observations, 458 attempted transitions, 458 recorded transitions, zero rejected transitions,
  zero rejected seeds, and zero capacity drops.
- Atomic export published 458 rows in 15.809 ms. The resulting file is 600027 bytes and has exactly
  460 lines: one header, 458 transition records, and one complete footer. No sibling `.tmp` file
  remains.
- The independent Python command returned `valid=true episode=1801 transitions=458 attempted=458
  rejected=0 capacity_drops=0`; it therefore rechecked every nested state/action record rather than
  trusting Unreal's success log.
- Raw-file SHA-256 is `154ab619c883076572d6336a5c785ef8386fd385ffcf33a1d5e801ac24a35bca`.
  The generated trajectory remains under the sample's `Saved` directory and is not committed.
- D-018 passes. The file makes character dynamics durable, but it is not yet a complete timed-gate
  scenario episode because target, obstacle, event, termination, and scenario-seed fields do not
  exist yet.
- Preserved audit: `evidence/unreal/d018_live_episode_1801.log`.

### D-019 deterministic timed-gate kernel/actor — integration pending (2026-08-31)

- Implemented a fail-closed sinusoidal schedule evaluated from immutable configuration and absolute
  scenario time, plus explicit collision > forward crossing > timeout event priority.
- Reviewer enforced that the motion axis lies in the fixed crossing plane and rejected unknown
  motion enums, preventing editor configuration from silently changing the task definition.
- Added a separate runtime actor with a blocking box as gameplay geometry and a collision-disabled
  engine cube as visualization. The actor resets its clock/collision counters and never integrates
  position incrementally.
- Strict universal Mac Editor/Development/Shipping builds pass. The real sample universal Editor
  target built successfully, then executed `MotionWorld.Gate.DeterministicScheduleAndEvents`:
  one test found, one success, exit code zero.
- Runtime spawn/reset/event alignment, episode schema v2, and live collision/success/timeout evidence
  remain required; this checkpoint does not claim a working arena yet.
- Preserved automation audit: `evidence/unreal/d019_gate_kernel_automation.log`.
- Added opt-in bridge integration through a separate `AMotionWorldArenaManager`: it derives the
  gate frame from the verified reset anchor, owns spawn/reset and terminal state, consumes collision
  evidence at finalized character observations, and stops recording only after the terminal step is
  offered to the recorder. The default remains disabled.
- The first real-sample integration compile exposed one missing complete-type include for `UWorld`;
  adding `Engine/World.h` fixed it without a design change. The rebuilt universal target passed.
- Post-integration strict universal Editor/Development/Shipping builds pass. The actual sample then
  ran all eight MotionWorld tests successfully with exit code zero, preserving default-off behavior.
- Schema v2 writes optional immutable timed-gate metadata, analytically reconstructed previous/next
  obstacle states on every row, collision/crossing flags, terminal reason, terminal scenario time,
  and collision count. Character-only v2 rows use explicit null scenario fields; Python continues
  to accept the preserved v1 episode format.
- Unreal's focused exporter test passes in the actual sample after Reviewer checks required terminal
  time equality, forward-plane success, deadline-respecting timeout, and collision-count semantics.
  Strict universal Editor/Development/Shipping builds also pass.
- The independent Python loader recomputes every gate phase/position/velocity from the schedule and
  rejects false success, early timeout, event/summary disagreement, non-orthogonal frames, unknown
  fields, and all prior chronology/action errors. Full Python result: 16 passed; Ruff passed.
- Final exact-deployment regression found all eight MotionWorld tests and all eight succeeded with
  exit code zero. Repository/sample source parity differs only in a directory timestamp.

# D-019 live timed-gate attempt 1 — invalid (2026-09-01)

**Hypothesis:** With warmup reset enabled, the bridge will reset the controlled
character, start episode 1901, run the deterministic moving-gate scenario, emit
one terminal outcome, and export a schema-v2 episode.

**Configuration:** Local-frame automation at 200 cm/s; warmup 30 valid samples;
episode ID and gate seed 1901; gate 600 cm forward; amplitude 200 cm; period 4 s;
timeout 8 s.

**Observed:** The gate spawned and moved sideways. Runtime logging detected a
gate collision at scenario time 4.311357 s and terminated the arena. However,
the log contained no queued/verified reset, no recording lifecycle, and no
export. After termination, collision was disabled while forward automation
continued, making the character appear to pass through the gate.

**Conclusion:** Invalid trial. Gate motion and collision-event wiring received
useful feasibility evidence, but no scenario result is accepted because the
deterministic reset and recording preconditions were absent. See
`evidence/unreal/d019_live_attempt_1_invalid.log`.

**Reviewer finding:** Terminal handling must stop the agent and preserve the
gate's physical collision while freezing its motion. Attempt 2 must also verify
the runtime warmup-reset property before PIE.

## D-019 terminal-safety correction — pre-live validation (2026-09-01)

**Hypothesis:** A terminal arena observation can preserve causal episode data while making the
post-terminal visualization safe and unambiguous.

**Change:** Scenario events now run only during a verified recording. Same-observation physics
callbacks are coalesced. At terminal, the gate freezes but remains physically collidable and both
stored velocity frames become zero exactly once; echo checking waits until zero is submitted.

**Result:** The strict isolated universal Editor/Development/Shipping builds passed. The exact
Game Animation Sample universal Editor target passed, all eight actual-project MotionWorld tests
succeeded, and all 16 Python tests plus Ruff passed. Deployed source matches the repository.

**Interpretation:** Static and automated evidence supports the correction, but physical behavior
is not accepted until live attempt 2 proves reset, terminal stop, retained collision, export, and
independent schema-v2 validation. See `evidence/unreal/d019_terminal_safety_automation.log`.

## D-019 live timed-gate attempt 2 — accepted collision episode (2026-09-01)

**Hypothesis:** With the saved warmup-reset trigger and corrected terminal policy, episode 1901
will begin only after verified reset, preserve the collision-causing transition, stop the character,
freeze a still-solid gate, export schema v2, and pass independent validation.

**Result:** Reset verified on its first finalized check with zero position, facing, linear-speed,
and angular-speed error. The runtime produced one `gate_collision` classification and one collision
count. The gate reported `collision_retained=true`; the next Mover command echo was exactly zero
with `match=true`. The recorder accepted 70/70 attempted transitions with no rejected seed, row,
or capacity drop and exported in 4.616 ms.

**Independent result:** The strict Python reader accepted the 72-line, 132925-byte schema-v2 file
with exit code 0. SHA-256 is
`4547c55febe873fb27c93a017b7bdc5f0654e0a8db3202ee3949a1026739900b`.

**Conclusion:** Accepted as one live collision episode and as end-to-end evidence for deterministic
character/arena reset, causal recording, terminal safe-stop, and durable scenario export. It does
not establish same-seed repeatability or live success/timeout behavior. See
`evidence/unreal/d019_live_episode_1901.log`.

## D-019 same-seed repeat — episodes 1901 and 1902 (2026-09-01)

**Hypothesis:** Repeating seed 1901 from the same verified anchor under the same constant action
will preserve the analytic scenario and terminal outcome despite ordinary frame-time variation.

**Controlled change:** Only the unique episode ID changed from 1901 to 1902. Scenario seed/config,
anchor, action, controller, executable, and level remained fixed.

**Result:** Both resets matched exactly in position, velocity, and yaw. Both independent files
validated, every action was automated local `(200,0,0)` cm/s, and both ended with one gate collision.
The physical collision-time difference was 3.995 ms; terminal agent positions differed by 0.153 cm
and terminal gate centers by 0.818 cm. Episode 1901 used 70 steps (median 49 ms, p95 59.55 ms), while
1902 used 62 (median 56 ms, p95 74.95 ms).

**Interpretation:** Accepted as same-seed scenario repeatability under observed variable stepping.
The result supports absolute-time gate evaluation: the schedule and outcome remain stable without
requiring identical row counts. It does not provide a variance estimate from only two trials. See
`evidence/unreal/d019_same_seed_1901_1902.log`.

## D-020 animation-root diagnostic — closed-editor validation (2026-09-01)

**Hypothesis:** Visual animation-root motion can be measured without contaminating the gameplay
state or episode schema.

**Implementation:** A separate fail-closed diagnostic is aligned to the finalized authoritative
sequence/time. Default-off runtime capture queries Mover's primary skeletal visual, reads bone zero
from the current public pose buffer, and emits session-tagged rows with `model_input=false`. Logging
has an interval and hard capacity. A strict Python reader verifies protocol, source identity,
chronology, finite values, and recomputed actor-to-root offsets before plotting.

**Reviewer finding:** `USkeletalMeshComponent::AreBoneTransformsValid()` cannot be called here
because the UE 5.8 override is protected. The rejected first integration build exposed this. The
runtime now uses only public evidence: registered component, nonempty skeleton, and nonempty
component-space transform buffer; the pure builder still fails closed.

**Result:** The corrected strict universal Editor/Development/Shipping builds pass. All 19 Python
tests and Ruff pass. A three-row synthetic session parsed successfully and produced a visually
inspected 1980x802 actor-versus-root/offset plot. This validates the tooling, not the real sample.

**Exact-sample result:** The closed Game Animation Sample universal Editor build passed in 118.50
seconds. Deployed source matches the repository, the dylib contains x86_64 and arm64, and all eight
actual-project MotionWorld tests returned `Success` with exit code zero.

**Acceptance boundary:** A live trace/plot must still pass before D-020 or Day 1 is closed. See
`evidence/unreal/d020_animation_diagnostic_pre_live.log`.

## D-020 live animation-root diagnostic — accepted (2026-09-01)

**Configuration:** Default sample pawn, human input, MotionWorld automation/episode/reset/arena
features disabled; only animation-root diagnostics enabled at interval 1 with a 512-row cap.

**Result:** Session `7C88DBC1E840` produced 356 valid rows, zero invalid rows, 356 logged rows, and no
capacity stop over 19.117 s. The actor moved 1776.814 cm along world X. The independent parser
accepted the protocol, session identity, 356 strictly ordered sequences/times, finite transforms,
fixed source identity (`SkeletalMesh/root`), and every recomputed root offset.

**Observed animation behavior:** Animation-root and actor XY coincided for every row, so median and
maximum planar offset were both 0 cm. Vertical root-minus-actor offset was normally -88 cm and
briefly reached -86.549 cm at movement onset. This is evidence that this selected root is in-place
for this sample/trace; it is not evidence that all animation roots always match gameplay motion.

**Durable artifacts:** The validated 356-row CSV has 357 lines and SHA-256
`ba19a7f9deb7a17086dc1f50f50480624a0c11ab86ba08b215e9eff7a0ecdea2`. The visually inspected
three-panel PNG has SHA-256
`fef564b3cc88c501384b3bace772fc2a55e26e5d0f49bcaf4e36ccfa752e0c0e`. See
`evidence/unreal/d020_live_animation_trace.csv`,
`evidence/plots/d020_live_actor_vs_animation_root.png`, and
`evidence/unreal/d020_live_animation_diagnostic.log`.

**Claim boundary:** This diagnostic never entered authoritative state, causal transitions, or model
input. No reliable toe/contact telemetry was collected, so no foot-sliding claim is made.

**Closeout:** After preserving the CSV and plot, the candidate disabled animation-root diagnostics,
compiled/saved the Blueprint, and closed Unreal. The installed sample is back in its default-off
evidence state.

## NOM-CONTEXT-001 - Versioned nominal-context recording boundary (2026-09-02)

**Hypothesis:** Live Smooth Walking parameters and five known internal-state fields can be attached to
causal episode transitions without redefining authoritative gameplay state or accepting off-by-one
context joins.

**Implementation:** Added nominal-context protocol 1, transition protocol 2, and episode schema 3.
Recording now captures reflection data whenever an episode is active or reset verification is pending,
even when diagnostic logging is disabled. Each transition requires aligned previous/next context and
stores completed-step parameters from the next finalized snapshot. The atomic exporter writes explicit
capture/timing/future-availability provenance. Python strictly reads schemas 1, 2, and 3.

**Reviewer finding:** Reset verification can start a new episode during the same post-finalize callback.
Capturing only while the recorder was already active would have missed that seed frame. Pending-reset
frames now capture context too. The first full actual-sample automation run also exposed a test fixture
that changed a state's sequence without changing its attached context; the new mismatch check correctly
fired before the test's intended skipped-sequence assertion. The fixture now moves both labels together.

**Validation:** Strict isolated universal Mac Editor Development, Game Development, and Game Shipping
builds succeeded. The actual Game Animation Sample universal Editor build succeeded; its deployed dylib
is arm64+x86_64. All ten filtered MotionWorld tests completed with `Success`. The startup log contains an
unrelated UE `DataflowNodes` member-initialization error before the filtered suite; it is preserved and is
not counted as a MotionWorld test result. The final raw log SHA-256 is
`dc47130a2369bbc1ea15063938bdab4480d98506126704eebe4cd2159ba90b03` and the deployed dylib SHA-256 is
`e74a812121728f29d2f63e345bf228205ac4634f517c189b98b7e56a62a756ab`.

**Python result:** The pinned Python 3.12 environment passed 92 tests. Eighteen episode tests include
legacy v1/v2 acceptance and adversarial v3 context cases. Focused Ruff checks and formatting pass.

**Acceptance boundary:** The contract, exporter, and independent loader are accepted. We have not yet
captured a live exported schema-v3 episode, measured a nominal prediction error, or implemented the
faithful Smooth Walking predictor. `theta_step` remains an observed-after-step label until its mutation
timing and causal future selector are established.

**Commits:** `fbe8b38`, `5be47f0`.

### NOM-CONTEXT-001 live acceptance addendum

The actual sample exported schema-v3 file
`episode_1902_20260902T095709Z_D4626AD19F4A.jsonl`: 119/119 attempted transitions were recorded with
zero rejected seeds, rejected transitions, or capacity drops. Independent Python validation accepted
all 121 JSONL records. A separate all-row audit confirmed transition protocol 2, automated actions,
state/context alignment at both endpoints, exact completed-step/next-parameter equality, and exact
hidden endpoint continuity. Timestep ranged from 0.021 to 0.054 s; spring velocity reached 165 cm/s
and spring acceleration norm reached 475.505 cm/s^2.

The intended unique ID `2701` did not persist; the file reused episode ID `1902`, which already names
an earlier schema-v2 trial. Therefore this file closes the live serialization boundary but is
quarantined from dataset manifests. Straight motion produced no angular response, so turning/facing
coverage remains open. Raw file SHA-256:
`65b6ba374d556cc0e69f729b65489cee6dc3e7dfa60d5e9a4b1c2128d2efe30a`.

## FEAS-001 branch-close audit (2026-09-01)

**Claim under review:** The Day 1 engineering system is sufficiently reliable to begin offline
nominal-model work without claiming that the final interview demo is complete.

**Fresh checks:** The project-local Python environment passed 20/20 tests, Ruff passed, and
`git diff --check` passed. The latest exact Game Animation Sample universal build and all eight
actual-project MotionWorld automation tests remain applicable because no Unreal source changed
after that validation; later commits only record evidence, safe Blueprint defaults, and teach-back.

**Decision:** Accept the bounded engineering gate for external control, finalized authoritative
state, Mover-owned reset, causal episode identity, timed-gate events, bounded persistence, strict
independent loading, and visual-only animation diagnostics. Proceed to Day 2.

**Not established:** Bitwise/full-hidden-state determinism, live success or timeout trials, a varied
training dataset, nominal/residual prediction quality, MPC improvement, OOD behavior, runtime
latency, deployment, or the final video.

## NOM-000 Python coordinate contract (2026-09-01)

**Hypothesis:** A typed Python implementation of the documented planar rotation will reproduce the
executed Unreal coordinate convention and invert scalar or batched conversions within numerical
tolerance.

**Configuration:** NumPy float64; fixed random seed 27116; 512 local vectors sampled uniformly from
`[-500, 500]` on each axis; yaw 37 degrees for the random round trip; absolute recovery tolerance
`1e-12`. Cardinal tests use the same cases as the Unreal automation suite.

**Result:** All 18 focused tests passed. Cardinal and local-right signs match Unreal. Every random
vector recovered after local-to-world-to-local conversion, vector length was preserved, and the
point example `(1000,500) + R(90 deg)(200,0) = (1000,700)` passed. Invalid dimensions, non-finite
values, and bare numeric yaw failed closed. Focused Ruff and `git diff --check` passed.

**Interpretation:** Accept the Python coordinate kernel. This establishes mathematical and golden-
case agreement, not live Python-to-Unreal transport. Candidate explanation and blank-page
derivation remain required before closing Section 3.1.

## ORACLE-001 bounded-velocity teaching proof (2026-09-01)

**Hypothesis:** The implementation will reproduce the hand-derived bounded-acceleration transition,
will not overshoot a reachable target velocity, and will preserve the same equation under batching.

**Configuration:** Float64 NumPy; scalar hand case `(p=0 cm, v=200 cm/s, desired=500 cm/s,
a_max=800 cm/s^2, dt=1/60 s)`; fixed random seed 27116 for 1,024 independent invariant cases;
optional target speed limit 500 cm/s.

**Result:** All 34 focused tests passed. The hand case returned `v_next=213.333333 cm/s`,
`p_next=3.444444 cm`, and applied acceleration 800 cm/s^2. Rest, below-clamp, at-clamp, stop,
reversal, target limiting, above-limit observed velocity, and zero-acceleration cases passed. Batch
results matched repeated scalar calls. Every random case obeyed `abs(delta_v) <= a_max * dt`, the
declared trapezoidal position equation, and the requested speed bound. Invalid timestep,
acceleration, speed limit, shape, and non-finite state/action values failed closed.

**Interpretation:** Accept this module as a teaching/test oracle only. It is not evidence about
Unreal prediction accuracy and cannot serve as the fair nominal baseline because it omits planar
directional response, springs, facing, collision, and known/hidden controller state.

## SYN-001 deterministic 2D backend proof (2026-09-01)

**Label:** `SYNTHETIC / NOT UNREAL EVIDENCE`

**Hypothesis:** A local seeded reset plus analytic stepping will exactly reproduce a complete episode
for identical configuration/actions, while a declared hidden target lag produces a visible,
controlled mismatch from a direct lag-free predictor.

**Configuration:** Default 100 ms toy step, 300 cm/s legal action norm, 600 cm/s^2 acceleration,
0.35 s hidden-lag time constant, absolute-time sinusoidal gate, seed 27116 for the plot. Tests also
cover a deterministic step-indexed push and fast swept gate crossing.

**Result:** All 15 focused backend tests passed. Same seed/config/actions yielded exactly equal
immutable episodes and consecutive sequence IDs; different seeds changed reset state. Analytic gate,
action range, hidden lag, one-shot push, collision priority, anti-tunnelling sweep, timeout, terminal
guard, and invalid configuration cases passed. The headless plot is 2160x900 PNG with SHA-256
`a368b767544b84357799efa9c8244f18e69f30576007842c368977d2cb36aa98`; visual inspection found clear
trajectory and speed separation with an explicit synthetic-only title.

**Interpretation:** Accept the toy backend as deterministic pipeline infrastructure. The mismatch is
constructed, so it says nothing about whether real Unreal residuals exist or whether learning or MPC
will improve the real task.

## NOM-DIAG-001 bounded Smooth Walking diagnostic — pre-live accepted (2026-09-02)

**Hypothesis:** The plugin can inspect the UE 5.8 Smooth Walking parameter contract and create a
fail-closed, model-isolated diagnostic seam for its five known spring-state fields without including
Epic's private state header.

**Configuration:** Active-mode parameters are read from public UObject metadata. Finalized sync
state is traversed through `FMoverDataCollection::GetDataArray()` and exactly five named properties
are reflected from `SmoothWalkingState`. Capture is default-off at `OnPostFinalize`, logs every 60th
authoritative sample by default, caps output at 512 rows by default (hard clamp 10,000), and labels
every row `model_input=false`.

**Result:** The final strict universal Mac Editor Development, Game Development, and Game Shipping
builds passed in 2 min 3 s. Deployed repository source matched the closed Game Animation Sample
exactly; its first full universal Editor build passed in 318.51 s and the final hardened incremental
rebuild passed in 17.00 s. The dylib contains arm64 and x86_64 and has SHA-256
`b05c982a77285ad6bfa9030f0e23c4923e1036f116ce24a96a604ac882d283cd`. All nine actual-project
MotionWorld tests passed with exit code zero, including `MotionWorld.Diagnostics.SmoothWalking`.
The complete 87-test Python suite and Ruff also pass.

**Reviewer checks:** The pure builder rejects incomplete identity, missing parameters/state, wrong
parameter count, non-finite parameters, invalid physical ranges, and non-finite vectors/quaternion.
Reflection rejects the wrong active mode, missing/type-mismatched properties, and invalid values.
No diagnostic field enters `FMotionWorldStateSample`, `FMotionWorldTransitionSample`, or episode
serialization.

**Interpretation:** Accept the bounded implementation and closed-editor API/compile evidence. Do
not yet freeze the Python nominal parameters or claim live hidden-state access. One opt-in Walking
PIE trace must still show the actual Blueprint-derived mode class, all runtime parameter values, and
a valid reflected state row; diagnostics must then be restored off. See
`evidence/unreal/nom_smooth_walking_diagnostic_automation.log`.

### Live attempt 1 — rejected (2026-09-02)

The candidate opened `SandboxCharacter_Mover`, changed settings, compiled, saved, and ran a valid
human-controlled Walking trace. Authoritative samples prove movement from rest through forward
motion, turning, and return to rest over sequences 0–300. However, BeginPlay logged only the normal
bridge-ready line: no Smooth Walking diagnostic session-start, row, invalid-row, capacity, or
session-stop message exists. Therefore the runtime diagnostic flag was false and this trace contains
no parameter/state evidence. The run is rejected rather than reused. See
`evidence/unreal/nom_smooth_walking_live_attempt_1_invalid.log`.

### Live attempt 2 — accepted (2026-09-02)

**Configuration:** Human control; automation, episode recording, timed gate, animation diagnostics,
and all model input disabled. Only Smooth Walking diagnostics were enabled at interval 10 with a
128-row cap. The candidate moved forward, turned, released input, and stopped PIE.

**Result:** Session `FF6768704542` captured 1,422 valid and zero invalid finalized states. Exactly 128
rows were logged before the expected cap, covering sequences 0–1270 in exact increments of 10. All
rows were `Walking`, class `BP_MovementMode_Walking_C`, protocol 1, and `model_input=false`.

**Parameter finding:** Parameters changed within the trace. The observed `(acceleration,
deceleration,facing smoothing)` regimes were `(800,20000,0.2)` for the startup row,
`(500,1000,0.2)`, and `(800,300,0.4)`. All other mapped parameters were stable: directional factor
1, turning strength 8, both velocity smoothing times 0.1 s, both compensations 0, outside-influence
smoothing 0.05 s, double-facing spring false, and documented deadzones. This rejects a constant C++-
default baseline.

**State finding:** Spring velocity was nonzero in 29/128 rows with maximum norm 375 cm/s; spring
acceleration was nonzero in 17/128 with maximum norm 1017.247 cm/s^2; intermediate velocity was
nonzero in 27/128 with maximum norm 375 cm/s; intermediate angular velocity was nonzero in 13/128
with maximum norm 2.770309 rad/s. Every facing quaternion was finite and unit length within
`2.64e-10`.

**Interpretation:** Accept the live reflection seam and D-026 state/parameter contract. Do not treat
the raw diagnostic as training data. Next, version the parameter/internal-state context in the
episode/protocol schema, then port the nominal equations to accept explicit parameter schedules.
The 162-line bounded raw excerpt is 137,200 bytes with SHA-256
`2bbeab642a571b87b141b3bd6161ac73625fb4c6ccd5bab567a34ec1302517cf`; see
`evidence/unreal/nom_smooth_walking_live_session_FF6768704542.log`.

## NOM-001 faithful one-step Smooth Walking evaluation (2026-09-02)

**Hypothesis:** A source-faithful port supplied with the real previous observable state, all five
known spring fields, completed-step parameter snapshot, actual timestep, and known input preparation
will reproduce non-contact Unreal steps, while a physical collision will create a decision-relevant
finalized-state mismatch.

**Configuration:** Accepted schema-v3 interface episode 1902; 119 transitions; retrospective
one-step evaluation; explicit effective max speed 165 cm/s; desired facing held at previous facing
because schema v3 does not record orientation intent; float64 Python equations using UE 5.8's
`InvExpApprox`; episode SHA-256 `65b6ba37...d2efe30a`. This file is excluded from training because
episode ID 1902 was reused.

**Reviewer finding:** The first evaluation used the recorded 200 cm/s packet directly. Rows 0-9
matched, then error began exactly when the engine's intermediate velocity reached 165 cm/s. Source
re-audit confirmed `SimpleWalkingMode` clamps velocity input by `MaxSpeedOverride` or shared
`UCommonLegacyMovementSettings::MaxSpeed` before Smooth Walking. That known transform was added as
an explicit tested module; the evaluator refuses to choose the missing setting implicitly.

**Result:** All 174 Python tests pass. Across 118 non-collision rows, maximum planar one-step
position error is `4.68e-7 cm` and maximum planar velocity error is `3.12e-6 cm/s`. At the one gate-
collision row, position error is `0.420935 cm` and velocity error is `15.033388 cm/s`. Spring
velocity, spring acceleration, and intermediate velocity still match at that row because those
fields describe the generated controller proposal, while authoritative movement records collision-
resolved execution. Yaw/angular error is zero in this straight episode.

**Interpretation:** Accept the translational equation port and the proposal-versus-execution
boundary for this narrow run. Meaningful residual error exists at contact, but a single terminal
collision is not enough data to train or claim systematic generalization. Before varied collection,
capture effective max speed in the versioned context and eliminate the unrecorded orientation
intent. The plot, row metrics, and machine-readable summary are in
`artifacts/nominal/episode_1902/`.

## NOM-CONTRACT-002 schema-v4 causal-input gate (2026-09-02)

**Hypothesis:** MotionWorld can record Simple Walking's effective speed preparation and complete
orientation input at the same causal transition boundary, without weakening strict validation or
breaking historical schema readers.

**Configuration:** Unreal 5.8.2 Game Animation Sample; diagnostic/context protocol 2; transition
protocol 3; episode schema 4; automation owns orientation by holding the last finalized facing;
legacy schemas 1-3 remain strict read-only inputs. No PIE data was collected in this gate.

**Result:** The real universal `GameAnimationSampleEditor` build succeeded across 28 actions in
213.19 seconds. The actual-project headless suite found 11 MotionWorld tests and all 11 completed with
`Success`. Python passed 180 tests in 6.08 seconds. Focused formatting and full Ruff lint passed.

**Reviewer checks:** Missing or non-finite orientation rejects the transition. Zero planar orientation
must explicitly fall back to previous facing. A bounded max speed must cite either mode override or
common legacy settings; an unbounded mode must use the declared zero placeholder. Completed-step
preparation must equal the next context. Export re-derives action-facing semantics before writing.
Python independently rejects mismatched speed/facing fields and keeps valid v1-v3 evidence readable.

**Interpretation:** Accept schema-v4 implementation and closed-editor verification. Do not claim live
capture until a uniquely identified episode shows `effective_max_speed_cm_per_s=165`, recorded facing
intent, zero recorder rejections, and strict Python acceptance. Fixed-facing automation also means a
separate explicit turning-action design is required before collecting turning coverage.

### Live episode 4001 — accepted (2026-09-02)

**Configuration:** Unique episode 4001; automated character-local `(200,0,0)` cm/s request; fixed
recorded facing; verified warmup reset; timed-gate seed 1901; diagnostics off; schema-v4 export on.

**Result:** Reset passed on attempt one with zero position, facing, linear-speed, and angular-speed
error. The recorder accepted 105/105 transitions with zero rejected rows, rejected seeds, or capacity
drops. One gate collision terminated the run at scenario time 3.486473 s. The complete export has 107
JSONL records, 558302 bytes, and SHA-256 `1f36a132...a76f04f6`; the independent loader returns
`valid=true`. Every transition is protocol 3, every context is protocol 2, and every completed-step
preparation records max speed 165 cm/s from `mode_override`. Every action records orientation
`[1,0,0]`, desired yaw 0 degrees, and fallback false.

**Reviewer correction:** The earlier schema-v3 evaluation correctly identified the effective numeric
limit from behavior but called the shared setting its main assumption. Schema v4 proves that this
Blueprint supplies 165 through the movement mode override. The value was right; its provenance was
previously unknowable and is now corrected.

**Equation replay:** The evaluator was run with no manual max-speed or facing arguments. Across 104
non-collision rows, maximum planar position error is `5.75e-7 cm` and maximum planar velocity error is
`6.93e-6 cm/s`. The collision row has `2.374 cm` position error and `74.189 cm/s` velocity error while
all three translational internal-state errors are exactly zero. The visually inspected plot contains
one visible spike aligned with the recorded collision. Artifacts are under
`artifacts/nominal/episode_4001_schema_v4/`; plot SHA-256 begins `b6647a59`.

**Interpretation:** Accept the live causal-input contract and straight non-contact nominal parity.
Episode 4001 is uniquely identified and may serve as interface/evaluation evidence, but it is not a
training dataset: one straight trajectory and one terminal contact provide no turn, stop, reverse,
push, or repeated-contact coverage. Next define an explicit facing/turn action before varied
collection, then evaluate recursive 0.5/1.0/1.5-second rollouts.

## VAR-DATA-001 deterministic varied-action schedule — closed-editor gate (2026-09-02)

**Question:** Can one reset-bounded episode deterministically request forward, stop, reverse,
lateral, diagonal, and turning behavior while recording complete schema-v4 causal inputs?

**Hypothesis:** An absolute-time, piecewise-constant world-velocity schedule with velocity-derived
facing will create reproducible action strata without camera/controller leakage, then stop and export
automatically.

**Configuration:** Default-off schedule; 0.8-second motion phases, 0.4-second intermediate stops,
0.5-second final stop; speeds 200 forward, 150 reverse, 140 lateral, and 100/100 diagonal cm/s;
timed gate prohibited; total duration 5.3 seconds. Live episode 4101 is pending.

**Closed-editor result:** The actual universal `GameAnimationSampleEditor` build passed for arm64 and
x86_64. The headless run found 12 tests and all 12 succeeded. The first run correctly failed the new
boundary test at the 4.8-second transition because repeated floating-point accumulation placed the
boundary one representable value away from the closed-form timestamp. Production and tests now use
the same explicit sums, and the rerun passed.

**Reviewer findings:** An accidental reset-path edit was removed before compilation. Start rejects
an invalid schedule, timed-gate overlap, or missing finalized seed. Completion occurs only after the
current finalized transition is recorded, preserving causal ownership of the last applied action.
This does not yet prove live movement, coverage proportions, collision-free execution, file export,
or loader acceptance.

**Decision/next action:** Accept the pure schedule and lifecycle integration for a live episode 4101.
After capture, audit phase/action diversity, orientation semantics, stop/reversal dynamics, reset,
row counts, and schema-v4 validity before crediting any Section 7 collection item.

**Artifacts:** `evidence/unreal/var_data_001_schedule_automation.log`; Unreal source and tests under
`unreal/Plugins/MotionWorld`.

### Live episode 4101 — accepted (2026-09-02)

**Configuration:** The accepted default D-030 schedule, verified warmup reset, unique episode ID
4101, schema-v4 export, timed gate off, diagnostics off, and no manual input. Although the candidate
believed they had accidentally entered 1702, the runtime start/reset/header/export all independently
identify 4101; no 1702 file was produced.

**Result:** Reset passed on its first verification with zero position, facing, linear-speed, and
angular-speed error. All phases occurred in order at elapsed times 0.000, 0.807, 1.203, 2.014, 2.417,
3.262, 4.025, and 4.823 seconds. Completion fired at 5.302 seconds. The recorder accepted 191/191
transitions with zero rejected rows, rejected seeds, or capacity drops, and exported a complete file
in 27.773 ms. The strict Python loader returned `valid=true`. File SHA-256 is
`4fdd65f0...e09afb`.

**Coverage:** Six distinct world-action vectors occurred: forward 31 rows, reverse 31, right 30,
left 22, diagonal 29, and zero 48. Realized diagnostics count 59 braking rows, two velocity-sign
reversal rows, and 141 rows with absolute yaw change above 0.1 degrees. Character-local actions span
X `[-150,200]` and Y `[-149.819,141.140]` cm/s. Maximum realized speed is 164.983 cm/s; yaw spans
-179.573 to 178.807 degrees; actual timesteps span 0.018–0.084 seconds. No collision occurred.

**Nominal finding:** Retrospective one-step translation remains effectively exact: maximum planar
position error is `5.17e-7 cm` and velocity error `5.30e-6 cm/s`. One exact-reverse boundary row has
16.266 degrees yaw error and 677.733 deg/s yaw-rate error; all other yaw errors are at numerical-noise
scale. The row records -180-degree intent, while the next internal quaternion represents -179 degrees
for one step before changing to the equivalent 180-degree form. This is preserved as a known
quaternion/preprocessing edge and is not yet credited as learned residual structure.

**Decision/next action:** Accept live varied coverage and use it for recursive 0.5/1.0/1.5-second
nominal evaluation. Resolve or explicitly model the exact-opposite quaternion edge before calling the
nominal baseline fair for rotation. More episodes, complete episode-level splits, contact, and pushes
are still required before residual training claims.

**Artifacts:** `evidence/unreal/var_data_001_live_episode_4101.log` and
`artifacts/nominal/episode_4101_varied/`. The raw Unreal episode remains outside Git; its content hash
and provenance are committed.

## NOM-ROLL-001 recursive nominal rollout on episode 4101 (2026-09-02)

**Question:** When intermediate real states are withheld, how does faithful nominal error compound
over 0.5, 1.0, and 1.5 seconds of varied recorded actions?

**Method:** Initialize from each eligible real previous state/context once. Recursively advance the
predicted observable and internal state under recorded schema-v4 actions, recorded variable
timesteps, and explicitly retrospective completed-step parameters. Compare at the first finalized
boundary at or after each requested horizon. No intermediate observation or hidden-state re-seeding.

**Result:** There are 173, 154, and 136 complete windows at 0.5, 1.0, and 1.5 seconds. Actual endpoint
ranges are 0.500–0.567, 1.000–1.066, and 1.500–1.581 seconds. Maximum translational errors over all
windows are `8.35e-6 cm` position and `1.65e-5 cm/s` velocity. Median yaw errors are
`5.31e-6`, `8.82e-6`, and `1.22e-5` degrees, yet p95 yaw errors are 82.917, 94.194, and 39.768
degrees; maxima are 174.296, 174.296, and 89.390 degrees.

**Reviewer localization:** At 0.5/1.0/1.5 seconds, 19/39/35 windows have yaw error above one degree.
Every one crosses transition 46; zero non-crossing windows exceed one degree. Maximum non-crossing
yaw errors are only `2.21e-5`, `1.79e-5`, and `1.81e-5` degrees. The large tail is therefore the
identified exact-opposite quaternion edge compounding through recursive rotation, not diffuse model
failure. Translation remains unaffected.

**Interpretation:** The nominal translation is source-faithful for this collision-free episode. The
rotation baseline is not yet fair at exact opposite facing and must be resolved or represented before
residual training. This episode alone supplies no systematic learnable free-space residual and does
not satisfy NOM-002 contact/push/generalization evidence. The result also demonstrates why median,
p95, and failure localization must all be reported.

**Validation:** Ten focused rollout tests and 190 full tests pass; Ruff passes on all Python source.
The recursive-state trap proves no intermediate teacher forcing. Plot reviewed visually.

**Artifacts:** `artifacts/nominal/episode_4101_varied/recursive_rollouts.csv`,
`recursive_summary.json`, `recursive_error.png`, and
`evidence/unreal/nom_roll_001_episode_4101.log`.

## FACING-001 explicit antipodal tie-break — closed-editor accepted (2026-09-02)

**Question:** Can the velocity-only facing policy remove the exact-180-degree ambiguity without
changing the reverse velocity action or hiding the failure inside a learned residual?

**Hypothesis:** Keeping reverse velocity at `(-150,0,0)` cm/s while setting orientation intent to a
unit -179.5-degree vector will select one quaternion arc deterministically and remove transition-46-
style angular tails in a replacement varied episode.

**Prepared configuration:** Default tie-break 0.5 degrees clockwise; accepted range 0.25–5 degrees;
all schedule timings and translational velocities unchanged. The schedule and reverse stop share the
same target.

**Closed-editor evidence:** UE 5.8 source uses an explicit opposite-vector branch inside
`FQuat::FindBetween`; episode 4101 localizes every recursive yaw error above one degree to the exact
opposite transition. C++ tests are prepared for velocity preservation, unit facing, exact -179.5
degrees, clockwise sign, and invalid zero tie-break rejection. The actual universal sample build
succeeded in 158.65 seconds, and all 12 MotionWorld tests passed. An isolated cold BuildPlugin run
passed header/reflection generation, then was deliberately stopped without acceptance when Unreal
reported 14.7/16 GB committed memory while compiling 62 universal actions. The lower-memory actual-
sample incremental build used 12 actions and completed successfully.

**Acceptance gate:** Actual universal sample build, complete MotionWorld automation suite, and one
new unique live episode. The new first reverse row must record -179.5 degrees, and one-step/recursive
angular evaluation must no longer show the episode-4101 spike.

**Current decision:** Accept the closed-editor implementation and regression gate. Keep the
experiment `In progress` until the new live episode and angular reevaluation pass.

**Artifact:** `evidence/unreal/facing_001_antipodal_automation.log`.

### Unique live episode 4201 — accepted

The first live attempt repeated embedded ID 4101 because the operator changed
`BeginPlayEpisodeId`; warmup-reset runs are controlled by `BeginPlayResetEpisodeId`. That file is
excluded from manifests. After correcting the exact property to 4201, reset passed exactly and all
eight phases executed. The recorder accepted 193/193 attempted transitions with no rejection or
loss, exported schema 4, and the independent loader returned `valid=true`.

Every reverse row records a -179.5-degree target. The first row's reflected internal target is
-179.0 degrees for one frame, causing only 0.024337 degrees maximum one-step yaw error. Recursive
yaw maxima at 0.5/1.0/1.5 seconds are 0.042917/0.042917/0.029078 degrees, compared with
174.296/174.296/89.390 in episode 4101. Translation remains at micro-numerical parity. Both plots
were inspected visually and preserve the small spike with truthful axes.

Accept FACING-001 live. This is a known-input-policy correction, not learned residual improvement.
Episode 4201 still supplies no systematic free-space residual and no collision/push evidence.

Artifacts: `artifacts/nominal/episode_4201_antipodal/` and
`evidence/unreal/facing_001_live_episode_4201.log`.

## PERT-SCHEDULE-001 deterministic external velocity intervention (2026-09-02)

**Hypothesis:** An absolute-time state machine can request exactly one bounded planar velocity kick,
even when a frame arrives late, while preserving explicit pre-event and recovery intervals.

**Configuration:** 1.5 s warmup, one additive world-space `(0,250,0)` cm/s request, and 2.0 s
post-event observation. The public type and evidence call this a velocity perturbation rather than a
force or mass-based impulse.

**Closed-editor result:** The actual universal Game Animation Sample target compiled the new source
in 49.28 s; the final excessive-bound test rebuild took 14.98 s. The focused
`MotionWorld.Collection.ExternalPerturbationSchedule` test passed. It covers exact
half-open boundaries, a nine-second late frame before queue confirmation, duplicate prevention,
completion, and fail-closed timing/vector bounds.

**Causal schema gate:** Schema 5 / transition protocol 4 adds a separate event label keyed to the
previous finalized state sequence and Mover frame. The header declares evaluation-only semantics and
stores the schedule; export and Python validation require exactly one matching event with sufficient
post-event duration. Legacy schemas remain readable without synthesized labels. The actual universal
sample build succeeded in 126.84 seconds; all 13 MotionWorld tests and 196 Python tests pass.

**Closed-editor runtime gate:** The default-off bridge integration queues the effect only after a
recorded finalized state, retains a pending label for the next causal row, aborts on any recording
failure, and completes/exports only after the event row and full recovery duration exist. Timed gate,
varied action, and perturbation schedules are mutually exclusive. The actual universal sample rebuilt
in 19.99 seconds; all 13 MotionWorld tests passed again.

**Reviewer boundary:** This proves the schedule, storage contract, and compiled runtime control flow.
It does not yet prove that Mover applies the requested delta in live PIE, that the next live callback
contains exactly one event, or that recovery contains a learnable residual. Those remain required
before the experiment can be completed.

**Artifacts:** `evidence/unreal/pert_schedule_001_automation.log` and
`evidence/unreal/pert_schema_v5_automation.log`.
Closed-editor runtime evidence: `evidence/unreal/pert_runtime_closed_editor_automation.log`.

### Live episode 4301 — accepted

**Configuration:** Verified warmup reset; unique episode 4301; fixed character-local
`(150,0,0)` cm/s action; 1.5-second warmup; one scheduled additive world-space velocity request
`(0,250,0)` cm/s; 2.0-second post-event interval; gate and varied-action schedules off; schema 5.

**Identity and integrity:** Reset passed on attempt one at the anchor with exactly zero position,
facing, linear-speed, and angular-speed error. The run recorded 133/133 adjacent transitions with
zero rejection, rejected seeds, or capacity drops. The event was queued after finalized state 83 /
Mover frame 84 and attached once to transition 53 from state 83 to 84. Completion occurred only
after the full 3.5-second schedule, and the strict independent loader returned `valid=true`. Raw
episode SHA-256 is `e8bcecc12724f7e8a5ccf9c90cbc7249ae3703091dc713191f175f74cc60df0f`.

**Physical observation:** The event step lasted 0.023 s. Requested lateral change was +250 cm/s;
the finalized transition changed velocity by `(0.047391,233.479661,0)` cm/s, so its component along
the request was 93.392% of the requested magnitude. This ratio is descriptive, not proof of the
instantaneous API effect, because ordinary Mover dynamics also ran during that step. Lateral speed
fell below 10, 5, 1, and 0.1 cm/s after 0.281, 0.328, 0.416, and 0.549 s respectively. Final lateral
displacement was 24.433 cm.

**NOM-002 result:** Perturbation-aware one-step evaluation reports 53 pre-event, one event, and 79
post-event rows. Pre-event maximum planar position/velocity errors are `5.19e-7 cm` and
`7.14e-6 cm/s`. The hidden event row produces `5.370 cm` and `233.480 cm/s`. After the disturbed
state is observed and one-step evaluation re-seeds from it, post-event maxima return to
`4.25e-7 cm` and `9.40e-6 cm/s`. Recursive 0.5/1.0/1.5-second windows show the same causal split:
112 event-crossing windows have p95 endpoint position/velocity error `24.433 cm` / `165.362 cm/s`,
while 126 post-event windows have p95 `1.15e-5 cm` / `2.84e-14 cm/s`.

**Interpretation and decision:** Accept PERT-SCHEDULE-001 and complete NOM-002 as a bounded negative
result. The faithful retrospective nominal model explains recovery once the disturbed state is
observed. The event-causing row is not a learnable residual target because the event is intentionally
absent from model inputs. Training on that row would teach an average surprise or leak the schedule,
not predict an unpredictable push. Any Day-3 learned comparison must therefore target a genuinely
causal deployable-state limitation, such as reconstructing unavailable internal context from
history, and must be justified separately rather than weakening this baseline.

**Artifacts:** `artifacts/nominal/episode_4301_perturbation/` contains row metrics, summaries, and
three reviewed plots. The perturbation-aware evaluator commit is `f0d7348`. Runtime evidence is
`evidence/unreal/pert_runtime_live_episode_4301.log`.

## NOM-CAUSAL-001 current-snapshot and held-parameter nominal (2026-09-02)

**Question:** Does a deployable nominal predictor that sees only the current finalized context—not
the parameter snapshot observed after each future step—expose systematic, causal mismatch worth
modelling?

**Availability contract:** At a real observation boundary the predictor may use authoritative state
`s_t`, aligned Smooth Walking internal state `z_t`, current parameters/input preparation, and the
candidate action sequence. It may not read `s_(t+1)`, later internal context, completed-step/future
parameter snapshots, or external-event labels. During each recursive imagined future, the baseline
advances its own state and holds the initial current parameters until a separate causal selector is
defined.

**Implementation:** `02ae8bb` adds current-snapshot one-step inputs; `fc32430` adds held-current
recursive rollouts; `93fb741` gives every plot an explicit causal or retrospective title. Tests prove
that mutating later parameter/preparation snapshots cannot affect a rollout started earlier.

**Primary episode:** Use accepted corrected-facing episode 4201, SHA
`73717460108db8c3b9092e37cb7ef48c4ba5f8e4fdbbeb5252b210977270bfb5`.
The retrospective completed-step oracle has one-step maxima `3.13e-7 cm`, `5.49e-6 cm/s`, and
0.0243 degrees. The causal current-snapshot replay has maxima 0.0598 cm, 2.134 cm/s, and 8.761
degrees. All three position-error rows above 0.001 cm, all three velocity-error rows above 0.01
cm/s, and all 13 yaw-error rows above 0.1 degrees occur on one of 23 rows whose current parameter
snapshot differs from the completed-step snapshot; none occur off those rows.

**Recursive result:** With parameters held from each rollout start, episode-4201 p95 position /
velocity / yaw errors at 0.5 s are 22.971 cm / 76.587 cm/s / 43.103 degrees. At 1.0 s they are
38.071 cm / 76.547 cm/s / 48.600 degrees; at 1.5 s they are 38.841 cm / 69.666 cm/s / 46.387
degrees. Retrospective-oracle p95 position remains below `6.71e-6 cm`, velocity below
`1.47e-5 cm/s`, and yaw below 0.032 degrees across the same horizons.

**Reviewer interpretation:** This is a legitimate deployment gap, not permission to weaken Smooth
Walking equations. The unavailable quantity is the Game Animation Sample's future parameter regime,
not public Mover dynamics. A residual model may test whether current state/action and short history
predict the *effect* of that hidden schedule. It must not receive later parameter snapshots. A more
explicit causal parameter selector remains a valid alternative and must be acknowledged.

**Data limitation:** Episodes 4101 and 4201 repeat essentially one deterministic action schedule;
they are evaluation/proof data, not enough independent episodes for a credible train/validation/test
claim. Before training, collect episode-separated schedules with varied phase order, duration,
direction, and magnitude, and freeze manifests. Episode 4301 confirms that the held-current policy
does not turn the hidden kick into a causal target.

**Artifacts:** `artifacts/nominal/episode_{4101,4201,4301}_current_snapshot/`.

## RES-CONTRACT-001 residual target/composition invariants (2026-09-02)

**Question:** Can the residual target be represented without future-facing leakage, composed back
into nominal state, and disabled without changing the baseline?

**Method:** Define a frozen six-component output containing local planar position and velocity,
shortest signed yaw, and yaw-rate corrections. Use the previous observed facing as the local frame.
Reject vertical/time mismatch. Test hand-checkable rotation and angle-wrap cases, compute-then-compose
inversion, non-finite inputs, and exact zero identity.

**Result:** All 11 focused tests pass; all 213 repository tests pass. A world `+Y` error at a
90-degree reference facing becomes local `+X`; `+179` to `-179` becomes a `+2 degree` correction;
and difference followed by composition reconstructs the actual planar state. Exact zero returns the
nominal object, preventing angle normalization from introducing even a tiny floating-point change.

**Reviewer interpretation:** The contract establishes semantics, not learned performance. It does
not justify normalization values, model architecture, or a prediction claim. Normalization scales
must be fitted from training episodes only after episode-level splits are frozen.

**Implementation:** `motionworld/models/residual_contract.py` and
`tests/unit/test_residual_contract.py`.

## RES-DATASET-001 episode-safe example construction (2026-09-02)

**Question:** Can no-history and four-history learning examples be built without crossing resets,
mixing episodes, reading completed-step future parameters, or treating the hidden kick as predictable?

**Method:** Build each episode independently from the causal current-snapshot nominal. Require
adjacent state samples and consecutive transition sequences. A no-history example contains one
28-value query; a four-history example contains four consecutive queries flattened oldest-to-current.
Never construct a target for a row carrying the evaluation-only hidden external event. Reject
duplicate episode IDs when combining episodes.

**Result:** Fourteen focused tests pass. Mutating a completed-step parameter snapshot does not change
features or targets. A six-transition synthetic episode produces six no-history and three complete
four-history examples. Two four-transition episodes produce two independent history examples—not a
spurious cross-episode window. The accepted live episode 4201 loads into 193 no-history and 190
four-history examples with shapes 28/6 and 112/6 respectively. The full suite has 238 passing tests.

**Reviewer interpretation:** This proves construction and leakage invariants, not dataset diversity.
Episodes 4101 and 4201 remain near-duplicate schedules, so train/validation/test manifests and
normalization are still blocked on collecting independent action schedules.

**Implementation:** `motionworld/models/residual_dataset.py` and
`tests/unit/test_residual_dataset.py`.

## RES-MODEL-SMOKE-001 residual MLP implementation checks (2026-09-02)

**Question:** Do the initial no-history and four-history MLPs meet the size, exact fallback, tensor,
gradient, and reproducibility contracts before any performance experiment?

**Method:** Instantiate 28-input and 112-input models with matched 256/256/128 SiLU hidden layers and
six outputs. Zero-initialize the output layer. Exercise batches with a horizon prefix, float64 on CPU,
invalid shapes/configurations, gradient flow, an optimizer step, and repeated seeded initialization
and training.

**Result:** Fourteen focused tests pass. The models contain 106,886 and 128,390 parameters. Both
return bit-exact zero tensors before training, the output layer receives finite nonzero gradients,
one update changes predictions, and repeating the seeded optimizer step reproduces loss and state.

**Reviewer interpretation:** This is an implementation smoke test, not evidence that either model
generalizes. The history model has 21,504 additional first-layer weights, so any history benefit must
be interpreted with a size-controlled ablation if it is material.

**Implementation:** `motionworld/models/residual_mlp.py` and
`tests/unit/test_residual_mlp.py`.

## RES-COLLECTION-001 frozen collection and live episode 5101 (2026-09-02)

**Question:** Does a separately identified, shorter and lower-speed varied schedule pass the strict
data boundary and reproduce the causal parameter-regime target rather than an equation or logging
failure?

**Pre-training split decision:** `configs/residual_collection_plan.yaml` freezes five train episodes
(5101-5105), two validation episodes (5201-5202), and two untouched test episodes (5301-5302), each
with a distinct configuration. Three tests enforce unique IDs, disjoint split labels, distinct valid
schedules, and exact accepted-file provenance. Raw Epic data remains external and untracked.

**Episode 5101 configuration:** 0.55 s motion phases, 0.25 s intermediate stops, 0.35 s final stop;
120/90/110/75 cm/s forward/reverse/lateral/diagonal-component speeds; 0.5-degree reverse-facing tie
break. The schedule is 3.6 s versus episode 4201's 5.3 s default schedule.

**Integrity and coverage:** Reset passed on attempt one with zero position, facing, linear-speed, and
angular-speed error. The run completed at 3.620 s, recorded 130/130 transitions without loss, exported
schema 5, and passed the independent loader. Six realized actions contain 20 forward, 20 reverse, 20
right, 20 left, 19 diagonal, and 31 zero rows. All rows are Walking and event-free. It yields 130
no-history and 127 four-history examples. Raw SHA-256 is
`eb437123d88dcf0c7b96b7f4fa5e2d75f502c2b70bc08408094b154693c3eaae`.

**Scientific audit:** Retrospective maxima remain `2.273e-7 cm`, `4.906e-6 cm/s`, `0.029629 deg`,
and `1.058 deg/s`, confirming equation fidelity. Causal current-snapshot maxima are 0.076833 cm,
2.561111 cm/s, 7.128842 deg, and 254.601485 deg/s. All 3 position errors above 0.001 cm, all 3
velocity errors above 0.01 cm/s, all 13 yaw errors above 0.1 deg, and all 17 yaw-rate errors above
1 deg/s occur on parameter-change rows; none occur off-change. Held-parameter recursive p95 position
error is 14.820/19.986/12.784 cm at 0.5/1.0/1.5 s.

**Reviewer interpretation:** Accept 5101 into the training split. This reproduces the causal target
under changed duration and action magnitudes, but one episode is not sufficient for training or a
coverage claim. The schema stores realized actions rather than the editable schedule as a named
header object, so the frozen plan/evidence preserves configuration provenance explicitly. Test
episodes remain unavailable for model selection.

**Evidence:** `evidence/unreal/res_collection_live_episode_5101.log` and
`configs/residual_collection_plan.yaml`.

### Rejected 5102 attempt: training configuration embedded as validation ID 5201

The next technically valid run exported 151/151 schema-v5 transitions with exact reset and no loss,
but its runtime/header/row/footer/filename identity is 5201 while its realized 4.3-second,
80/130/70/55 cm/s schedule is the frozen training-5102 configuration. No 5102 file exists. SHA-256
is `4c5629c510fdb9a2ca15646694dd90950687e4e0a4b1bb87cab4333bccf79305`.

Quarantine the file from all splits. Renaming cannot repair embedded identity, and accepting it as
5201 would replace the predeclared validation configuration after observing the run. Retry by changing
only `BeginPlayResetEpisodeId` to 5102. Evidence:
`evidence/unreal/res_collection_rejected_5201_wrong_config.log`.

### Corrected training episode 5102 — accepted

The corrected run preserves the frozen 4.3-second 80/130/70/55 cm/s schedule under embedded ID 5102.
Reset passed exactly; 156/156 schema-v5 transitions passed the strict loader with no loss or event;
the raw SHA is `a70492872c8b5d55cf669b500c44a703cba6d6e14d8bb21a057cd8efb67094b1`.
It produces 156 no-history and 153 four-history examples.

The retrospective maximum position/velocity/yaw/yaw-rate errors are `2.704e-7 cm`, `4.886e-6 cm/s`,
0.033340 degrees, and 1.11136 deg/s. Causal maxima are 0.076833 cm, 2.561111 cm/s, 8.233250 degrees,
and 274.441667 deg/s. Every material error again occurs on a parameter-change row: 3/3 position,
3/3 velocity, 14/14 yaw, and 18/18 yaw-rate rows, with zero off-change violations. Accept 5102 into
train; keep the wrong-ID 5201 attempt quarantined. Evidence:
`evidence/unreal/res_collection_live_episode_5102.log`.

### Training episode 5103 — accepted

Episode 5103 uses the frozen short, high-speed schedule: 0.40-second motion phases, 0.35-second
intermediate stops, a 0.25-second final stop, and 160/60/145/100 cm/s
forward/reverse/lateral/diagonal-component speeds. Reset passed exactly on its first attempt. The
2.957-second run recorded 105/105 schema-v5 transitions with no rejection, capacity loss, external
event, or movement-mode change. It yields 105 no-history and 102 four-history examples, bringing the
accepted training total to 391 and 382 respectively. Raw SHA-256 is
`59e4d5a2f0c6a2b2f4b3212d17335b8ead8a5d1f6ae947c86904e22f81626abf`.

The retrospective maximum position/velocity/yaw/yaw-rate errors are `6.787e-7 cm`,
`7.550e-6 cm/s`, 0.029629 degrees, and 1.05817 deg/s. Causal maxima are 0.179031 cm,
4.711360 cm/s, 5.619680 degrees, and 224.787194 deg/s. Every material error remains confined to a
parameter-change row: 3/3 position, 3/3 velocity, 12/12 yaw, and 17/17 yaw-rate rows, with zero
off-change violations. Held-parameter recursive p95 position error is 21.253/32.238/28.688 cm at
0.5/1.0/1.5 seconds. Accept 5103 into train; validation and test remain unused. Evidence:
`evidence/unreal/res_collection_live_episode_5103.log`.

### Training episode 5104 — accepted

Episode 5104 uses the frozen long, symmetric forward/reverse schedule: 0.90-second motion phases,
0.15-second intermediate stops, a 0.50-second final stop, and 145/145/95/60 cm/s
forward/reverse/lateral/diagonal-component speeds. Reset passed exactly on its first attempt. The
5.322-second run recorded 190/190 schema-v5 transitions with no rejection, capacity loss, external
event, or movement-mode change. It yields 190 no-history and 187 four-history examples, bringing the
accepted training total to 581 and 569 respectively. Raw SHA-256 is
`3a67867880654362434c496c0f81a184bc77e4b3e0ac2237dfdfb6c0554b5427`.

The retrospective maximum position/velocity/yaw/yaw-rate errors are `5.946e-7 cm`,
`9.347e-6 cm/s`, 0.035246 degrees, and 1.13697 deg/s. Causal maxima are 0.067925 cm,
2.342242 cm/s, 7.469170 degrees, and 266.756048 deg/s. Every material error remains confined to a
parameter-change row: 3/3 position, 3/3 velocity, 12/12 yaw, and 16/16 yaw-rate rows, with zero
off-change violations. Held-parameter recursive p95 position error is 18.504/28.875/28.914 cm at
0.5/1.0/1.5 seconds. Accept 5104 into train; validation and test remain unused. Evidence:
`evidence/unreal/res_collection_live_episode_5104.log`.

### Training episode 5105 — accepted

Episode 5105 uses the final frozen training schedule: 0.65-second motion phases, 0.45-second
intermediate stops, a 0.30-second final stop, and 100/155/130/85 cm/s
forward/reverse/lateral/diagonal-component speeds. Reset passed exactly on its first attempt. The
4.467-second run recorded 159/159 schema-v5 transitions with no rejection, capacity loss, external
event, or movement-mode change. It yields 159 no-history and 156 four-history examples, bringing the
complete five-episode training split to 740 and 725 respectively. Raw SHA-256 is
`d9e352128462909effb1b4ad45398a0db0a70aaeaef60f0ef874f09a063c2152`.

The retrospective maximum position/velocity/yaw/yaw-rate errors are `4.405e-7 cm`,
`6.135e-6 cm/s`, 0.031467 degrees, and 1.08507 deg/s. Causal maxima are 0.059764 cm,
2.134424 cm/s, 6.977431 degrees, and 227.335427 deg/s. Every material error remains confined to a
parameter-change row: 3/3 position, 3/3 velocity, 13/13 yaw, and 17/17 yaw-rate rows, with zero
off-change violations. Held-parameter recursive p95 position error is 12.166/30.904/31.817 cm at
0.5/1.0/1.5 seconds. Accept 5105 into train. The complete training split is now frozen; validation
5201-5202 and test 5301-5302 remain unused. Evidence:
`evidence/unreal/res_collection_live_episode_5105.log`.

### Validation episode 5201 — accepted

The correct validation run uses its frozen 0.50-second motion phases, 0.30-second intermediate
stops, 0.45-second final stop, and 135/105/80/95 cm/s forward/reverse/lateral/diagonal-component
speeds. This distinguishes it from the earlier technically valid but quarantined 5201 file, whose
80/130/70/55 schedule belonged to training episode 5102. The new run reset exactly on its first
attempt and recorded 117/117 schema-v5 transitions without rejection, capacity loss, external event,
or movement-mode change. It yields 117 no-history and 114 four-history validation examples. Raw
SHA-256 is `7ef1cc4756e2e49a0f94a15b61fc553e4f595dffebad85dd5ca86855d22336aa`.

Retrospective maximum position/velocity/yaw/yaw-rate errors are `3.086e-7 cm`, `7.556e-6 cm/s`,
0.071295 degrees, and 1.48532 deg/s. Causal maxima are 0.097029 cm, 3.032150 cm/s, 5.739069
degrees, and 212.558112 deg/s. Every material error is confined to a parameter-change row: 3/3
position, 3/3 velocity, 13/13 yaw, and 17/17 yaw-rate rows, with zero off-change violations.
Held-parameter recursive p95 position error is 16.836/23.585/17.724 cm at 0.5/1.0/1.5 seconds.
Accept this new artifact into validation only; do not train on it. Evidence:
`evidence/unreal/res_collection_live_validation_5201.log`.

### Rejected 5202 attempt: accepted 5201 identity and wrong stop duration

The attempted validation-5202 run is technically complete but cannot enter any split. Runtime,
header, rows, footer, and filename all embed episode ID 5201, which is already the identity of an
accepted validation artifact. The realized speeds are the frozen 5202 values
70/150/120/65 cm/s, but the two intermediate stops each lasted 0.80 seconds rather than the frozen
0.25 seconds. Consequently runtime declared and executed a 5.800-second schedule instead of the
predeclared 4.700 seconds.

The file contains 205/205 valid schema-v5 transitions, an exact first-attempt reset, zero loss, and
SHA-256 `f7b2b89cd629eb6ba43915c7ef6f80a148f142f82c215545d126681fb52460a0`. These technical
properties do not repair its duplicate identity or changed configuration. Quarantine it from every
split; do not rename it or reinterpret it as another 5201 run. Retry only after setting episode ID
5202 and intermediate-stop duration 0.25 seconds, then compile/save both values. Evidence:
`evidence/unreal/res_collection_rejected_5202_wrong_id_and_stop.log`.

### Rejected corrected-ID 5202 attempt: wrong motion-phase duration

The second validation-5202 attempt fixes the embedded identity and the 0.25-second intermediate
stops, but executes 0.50-second motion phases rather than the frozen 0.80 seconds. Runtime therefore
declares a 3.200-second schedule instead of 4.700 seconds. Its 70/150/120/65 cm/s speeds and
0.20-second final stop are correct.

The artifact is technically complete: exact first-attempt reset, 116/116 valid schema-v5
transitions, zero rejection/loss/events, and SHA-256
`e6468408acd2a5da27eba2686a9800273ede09acae34e3825727f6fe4ab53dfc`. Quarantine it from every
split rather than changing the frozen validation schedule after observation. Keep all other values
unchanged, set only motion-phase duration to 0.80 seconds, compile/save, and rerun. Evidence:
`evidence/unreal/res_collection_rejected_5202_wrong_motion_duration.log`.

### Corrected validation episode 5202 — accepted

The third attempt matches every frozen field: embedded ID 5202; 0.80-second motion phases;
0.25-second intermediate stops; 0.20-second final stop; and 70/150/120/65 cm/s
forward/reverse/lateral/diagonal-component speeds. Runtime declared 4.700 seconds and completed at
4.708 seconds. Reset passed exactly on its first attempt, and 166/166 schema-v5 transitions recorded
without rejection, capacity loss, external event, or movement-mode change. It yields 166 no-history
and 163 four-history validation examples. Raw SHA-256 is
`34c3df8e3dbe893e7d89fdba001b8afd244af93dad2c2b3758b965feb5934ba1`.

Retrospective maximum position/velocity/yaw/yaw-rate errors are `8.441e-7 cm`, `1.049e-5 cm/s`,
0.026062 degrees, and 1.00238 deg/s. Causal maxima are 0.086523 cm, 2.791070 cm/s, 6.976427
degrees, and 258.386184 deg/s. Every material error is confined to a parameter-change row: 3/3
position, 3/3 velocity, 11/11 yaw, and 15/15 yaw-rate rows, with zero off-change violations.
Held-parameter recursive p95 position error is 14.897/30.779/31.242 cm at 0.5/1.0/1.5 seconds.
Accept this artifact into validation only. The two validation episodes provide 283 no-history and
277 four-history examples; training remains 740/725. Both test episodes remain untouched. Evidence:
`evidence/unreal/res_collection_live_validation_5202.log`.

### RES-DATASET-AUDIT-001 — accepted manifest and coverage gate

Hypothesis: The seven accepted train/validation files can be reconstructed solely from the frozen
plan while rejecting modified bytes, duplicate identity, rejected attempts, and accidental test
access.

Configuration: Resolve only entries marked `accepted`; require train/validation split membership,
filename basenames, exact SHA-256, embedded episode ID, strict schema validation, unique global
transition identity, realized action equality to the frozen speed configuration, and disjoint
accepted/rejected filenames and hashes. Pending test entries must contain no observed file metadata
and are never opened.

Result: Valid. Five training episodes yield 740 transitions / 740 no-history / 725 four-history
examples. Two validation episodes yield 283 / 283 / 277. The audit reports `test_opened=0`; both
validation schedules are exact-configuration novel relative to training. Training contains 117/115/
116/113/111/168 forward/reverse/right/left/diagonal/stop transitions; validation contains
43/44/45/40/50/61. All rows are Walking. Train and validation contain 112 and 44 parameter-change
transitions, respectively. Every material causal residual occurs in that stratum; parameter-stable
rows have zero material violations.

Limitations: These accepted learning splits contain no collision or external-perturbation rows and
use one deterministic eight-phase family. This is a bounded free-space scheduler/context residual
experiment, not a general collision model. Test episodes 5301/5302 remain uncollected and unopened.

Artifacts: `artifacts/residual/dataset_audit/{manifest.json,coverage.json,coverage.png,README.md,
artifact_hashes.json}`. The plot was visually checked for readable labels and honest train/validation
comparisons. Seven focused and 262 total tests, Ruff, and diff checks pass.

## RES-001 — frozen one-step residual training and validation

Hypothesis: A small residual MLP can predict the causal execution mismatch around runtime parameter
changes better than the faithful hold-current nominal model on unseen episodes.

Configuration: Manifest SHA-256 `4c5d921194d339ba0617c930ce1ae41497ac5e04b14280c9ea8610bc3cc4d770`;
train episodes 5101-5105; validation 5201-5202; tests 5301-5302 sealed. Both MLPs use widths
256/256/128, SiLU, zero-initialized output, CPU float32, seed 20260903, AdamW at 0.001 with 0.0001
weight decay, batch 128, and exactly 1,500 uniform-with-replacement updates. The objective is
normalized Huber plus a 0.01 normalized correction-magnitude penalty. Input and target scales are
fit from training only; validation is first opened after both fixed final-step checkpoints exist.

Result: Accepted. Across 277 common validation rows, no-history mean position/velocity/yaw/yaw-rate
error is `0.000226 cm / 0.008249 cm/s / 0.045138 deg / 1.34570 deg/s`, versus nominal
`0.001210 / 0.042378 / 0.137137 / 5.27441`. On 42 parameter-change rows, no-history p95 is
`0.002381 cm / 0.107696 cm/s / 0.917758 deg / 18.9772 deg/s`, versus nominal
`0.052315 / 1.93760 / 3.60379 / 188.180`. Four-history also improves that stratum but is weaker
than no-history. Stable-row nominal error is near numerical precision, and both learned models add
small error there; the aggregate p95 position and velocity values are consequently misleading and
remain stratified.

Checkpoint SHA-256: no-history
`d979549b30bd01b3a304697074c295caf6c7fa16a4a8e25a08c15eec1da7a4f6`; four-history
`da4e2281c50b5ff329dd41ea3b02811ba634a35c461923c7afc240c11872c30f`.
Artifacts: `artifacts/residual/training_001/`. Training and validation plots were visually checked.
No test artifact was opened.

## RES-002 — teacher-forcing-free recursive held-out comparison

Hypothesis: One-step gains survive compounding when predictions, including imagined history, feed
subsequent predictions without recorded intermediate states.

Configuration: Use the frozen RES-001 checkpoints and identical eligible endpoints for nominal,
no-history, and four-history. Seed each rollout from one real finalized state, apply recorded future
actions and timesteps, hold the seed's current causal parameter context, and advance all observable
and nominal hidden state recursively. Horizons are 0.5/1.0/1.5 seconds. No validation checkpoint
selection or test inspection occurs.

Result: Gate passed for no-history. Common-window p95 metrics are:

| Horizon | Model | Position cm | Velocity cm/s | Yaw deg | Yaw rate deg/s |
|---:|---|---:|---:|---:|---:|
| 0.5 s | Nominal | 16.719 | 64.394 | 46.156 | 292.599 |
| 0.5 s | No history | 14.395 | 57.483 | 20.151 | 102.550 |
| 0.5 s | Four history | 15.929 | 63.153 | 41.792 | 255.780 |
| 1.0 s | Nominal | 30.222 | 61.151 | 97.287 | 441.489 |
| 1.0 s | No history | 27.934 | 55.206 | 30.691 | 75.100 |
| 1.0 s | Four history | 29.404 | 57.820 | 40.385 | 125.581 |
| 1.5 s | Nominal | 31.229 | 66.629 | 52.302 | 361.373 |
| 1.5 s | No history | 28.964 | 58.558 | 11.583 | 66.670 |
| 1.5 s | Four history | 30.391 | 63.116 | 25.787 | 106.986 |

No-history improves p95 position by 13.9/7.6/7.3%, velocity by 10.7/9.7/12.1%, yaw by
56.3/68.5/77.9%, and yaw rate by 65.0/83.0/81.6%. Select it for planner integration. Do not claim
history helps: it consistently loses to the simpler checkpoint. Longer stable-only strata are empty
because every long window crosses a scripted parameter change; the report records null, not zero.

Limitations: Both validation episodes use the same eight-phase family as training, no accepted row
contains contact or an external push, and improved prediction does not establish improved control.
The first evaluator attempts exposed missing nominal stratum metadata and invalid empty-stratum
aggregation; only reporting code changed, and the successful run retained the same checkpoints and
data. Artifacts: `artifacts/residual/recursive_001/`. The final plot was visually checked.

## CEM-001 — deterministic quadratic optimizer oracle

Hypothesis: Fixed-seed bounded CEM selects low-cost elites, concentrates its distribution, respects
the physical speed limit, and approaches a known two-dimensional optimum reproducibly.

Configuration: Synthetic quadratic target `[90, -55]` cm/s; 256 candidates; 32 elites; three
iterations; initial standard deviation 110 cm/s; variance floor 5 cm/s; population-variance momentum
0.1; maximum L2 speed 165 cm/s; PCG64 seed 20260903. The oracle uses one knot/one step to isolate
optimizer behavior. The separately frozen planned runtime shape is five knots expanded across 15
100 ms planning steps over 1.5 seconds, with three approximately 33.3 ms dynamics substeps per
planning step.

Result: Accepted for the optimizer only. The returned first action is
`[88.565541, -55.906396]` cm/s, 1.696828 cm/s from the known optimum. Best cost changes
`180.797693 -> 5.120032 -> 2.879227`; the first-knot distribution-mean distance changes
`7.153812 -> 2.841872 -> 0.778799` cm/s. The maximum sampled norm is exactly 165 cm/s, and two
runs reproduce the result exactly. A separate clean-directory rerun byte-matches the JSON, PNG, and
README.

Rejected attempt: Applying the original 15-knot runtime shape directly to the quadratic oracle
returned 88.275 cm/s first-action error because the frozen budget was searching 30 dimensions. This
motivated the explicit five-knot runtime design and the one-knot mathematical oracle. It is not
accepted evidence and was overwritten before commit.

Limitations: This proves sampling, bounds, elite updates, convergence direction, and determinism. It
does not prove the five-knot optimizer solves the timed gate, meets latency, or improves Unreal
control. Those remain the planning-cost and paired-controller gates. Artifacts:
`artifacts/planning/cem_001/`; the convergence plot was visually inspected.

## PLANCOST-001 — independent analytic cost oracles

Question: Do all five planned cost components have the intended sign, unit, geometry, and temporal
behavior before they influence CEM?

Result: Unit gate passed. Fourteen tests independently verify terminal distance, moving-gate swept
collision, capsule clearance plus safety margin, action first/second differences, and the visible
weighted sum. A diagonal path initially labelled a miss was correctly classified as clipping the
expanded gate corner; the hand expectation, not the geometry algorithm, was corrected. No cost
weights have been selected from validation or final test outcomes.

Limitations: The swept test linearly interpolates relative motion between analytic 100 ms boundary
positions; continuous sinusoidal curvature is not exact inside the interval. Actual sample capsule
geometry and provisional weights must be frozen before integrated controller evidence. No claim
about CEM task success is made. Implementation: `motionworld/planning/cost.py`; commit `8c22ae9`.

## OFFPLAN-001 — paired offline nominal/residual planner integration

Question: With every fairness-critical input held fixed, does the frozen residual model change CEM
candidate rankings and chosen actions, and does cross-evaluation expose model-risk before live use?

Configuration: Accepted validation episode 5202 transition 0 supplies the complete observable,
nominal hidden state, parameters, and effective 165 cm/s bound. Only world X/Y is counterfactually
relocated to `[-100, 0]` cm; the goal is `[100, 0]` cm. The analytic gate uses the Unreal defaults
X=0 cm, Y amplitude=200 cm, period=4 s, half extents 30x150 cm, plus a provisional 42 cm agent
radius and 20 cm safety margin. CEM uses seed 20260903, 256 candidates, 32 elites, three iterations,
five knots, 15 planning steps, and three dynamics substeps per step. Weights were frozen after one
exploratory pilot and before opening final test episodes. They are provisional dimensional
hypotheses, not learned truths.

Result: Integration and fairness gate passed. Both controllers consume byte-identical physical
candidates in iteration one, the shared noise hash is
`20bd9b1287bf7423163c9042920c341720d2833e610ac5ba84553ec40dbdcaf6`, and later batches diverge
only after model-specific elite updates. Nominal chooses `[40.192, -139.872]` cm/s with predicted
cost 106.476; residual chooses `[23.420, -102.090]` cm/s with predicted cost 86.081. Both models
classify their own selected path as collision-free.

Reviewer finding: The result is not a control win. Under the residual model, the nominal plan is a
collision with cost 10070.711. Under the nominal model, the residual plan has cost 216.360. This
large cross-model disagreement means CEM is acting on decision-relevant model differences, but it
also creates a serious model-exploitation risk. Only same-seed Unreal execution can determine which
prediction is closer to reality.

Reproducibility/runtime: Fifty-eight focused tests, 350 total tests, and Ruff pass. A second clean
run byte-matches every artifact file. The correctness-first Python paired call takes approximately
10 seconds, so the 100 ms online deadline currently fails by roughly two orders of magnitude. This
measurement is invocation-level diagnostic timing, not the formal RUNTIME-001 latency benchmark.
The float32 residual's batch-256 versus batch-1 re-evaluation differs by `8.77e-6` cost units and is
recorded within an explicit tolerance. Test files opened: zero.

Artifacts: `artifacts/planning/offplan_001/{summary.json,cross_evaluated_paths.csv,
offline_paired_planner.png,README.md,artifact_hashes.json}`. The four-panel plot was visually
checked. Commit provenance: `5d02bbc`.

## RUNTIME-001 — complete offline planner latency

Question: After a parity-checked vectorization, does one complete nominal or residual MPC call fit
inside the 100 ms compute deadline on the development machine?

Configuration: Apple arm64 Mac, Python 3.12.13, PyTorch 2.13.0 CPU, one Torch thread. Use the frozen
OFFPLAN-001 query and 256/32/3 CEM budget, five knots, 15 planning steps, and three dynamics
substeps per step. Warm up three complete calls per controller, then time 30 per controller in
alternating order. Dataset loading, Unreal transport, rendering, and action application are outside
the measured region. Test files remain sealed.

Result: Nominal median/p95 is `70.709/81.549 ms`, with 0/30 missed 100 ms deadlines. Residual
median/p95 is `149.655/169.401 ms`, with 30/30 misses. Therefore the nominal Python compute path
passes this bounded offline deadline and the residual path fails. This is not end-to-end Unreal
latency and cold-start latency remains unmeasured.

Optimization evidence: The original correctness-first scalar rollout took about 1.99 seconds for
one 256-candidate residual batch. The vectorized backend takes about 0.044 seconds for the same
batch, a 45x pilot speedup, with maximum differences of `9.77e-14 cm` position and `3.55e-15 rad`
yaw. The integrated paired solve falls from roughly 10 seconds to 0.244 seconds and retains the
same selected first actions. Randomized parity tests cover turns, stops, nonzero hidden state,
single/double facing springs, and nonzero learned corrections.

Interpretation: Vectorization removed the accidental Python-per-candidate bottleneck, but the
learned controller still cannot honestly run at 10 Hz with this budget. The next experiment must
trade candidate/iteration budget or compiled inference against solution quality; wiring a 150 ms
planner into a 100 ms loop would create stale actions.

Artifacts: `artifacts/planning/runtime_001/`. Full raw passing suite after vectorization: 358 tests.
Runtime implementation commit: `314b603`; deadline-count addition: `041b28b`.

## CEM-BUDGET-001 — validation-only runtime/quality trade-off

Question: Can we reduce CEM candidates or iterations enough for both controllers to meet 100 ms p95
without exceeding 10% p95 positive predicted-cost regret or introducing a newly predicted collision?

Prospective configuration: Freeze eight budgets before execution, preserve the 1/8 elite fraction,
use prefixes of the full reference's random tensor, and compare against 256 candidates/32 elites/
three iterations. Evaluate both models on ten predeclared snapshots—five each from validation
episodes 5201 and 5202. Runtime uses 20 alternating calls per controller after two warm-ups on the
canonical first validation query. Final test episodes remain sealed.

Result: No budget is eligible. Five two-iteration budgets from 64 to 192 candidates pass runtime,
with residual p95 increasing from 63.142 to 92.209 ms, but worst-model p95 positive cost regret is
43.47-68.97%, far above 10%. The 256-candidate/two-iteration budget nearly reaches runtime at
104.632 ms and gives residual regret 7.31%, but nominal regret remains 32.48%. Three-iteration
128/192-candidate variants miss runtime and fail quality. No budget introduces a newly predicted
collision, but that alone is insufficient.

Interpretation: Iteration three is decision-relevant, and simply reducing the search budget trades
away too much model-predicted solution quality under the predeclared gate. The threshold is not
relaxed after seeing the result. Preserve the full 256/32/3 budget and optimize residual inference
or model size next. Predicted cost is still not realized Unreal return.

Artifacts: `artifacts/planning/budget_sweep_001/`; the runtime/quality plot was visually reviewed.
Sweep implementation/freeze commit: `7d2de6f`. Test files opened: zero.

## RESIDUAL-COMPRESS-001 — validation-only residual width sweep

Question: Can a smaller no-history residual MLP preserve recursive prediction and reference-model
planning behavior while moving the unchanged 256/32/3 CEM call below 100 ms p95?

Prospective configuration: Commit four widths—192/192/96, 128/128/64, 96/96/48, and 64/64/32—
before training. Inherit the original train-only normalization, seed 20260903, 1,500 optimizer
steps, loss, batch size, and fixed-final-step checkpoint rule. Require every 0.5/1.0/1.5-second
recursive p95 metric to degrade by no more than 15% versus the frozen full-width checkpoint.
Require at most 10% p95 positive planner regret and zero new predicted collisions over ten frozen
validation queries, with candidate-selected actions cross-evaluated by the reference model. Require
complete residual CEM p95 at or below 100 ms over 20 calls after two warm-ups. Test files stay sealed.

Result: No candidate is eligible. Only 128/128/64 passes recursive quality (8.43% worst p95
degradation). Planner p95 positive regret is 10227.6%, 10693.8%, 6400.2%, and 9014.7% from largest
to smallest, and all introduce at least one new reference-predicted collision. Runtime median/p95
is 135.758/137.515, 125.516/184.242, 120.603/135.987, and 114.695/117.234 ms. Parameter counts
are 61,734, 28,870, 17,046, and 8,294 versus 106,886 in the reference.

Interpretation: Network width alone is not the solution. The near-monotonic median speedup is real,
but even the smallest model misses the deadline, while all candidate planners exploit or disagree
with the reference dynamics badly. The 128/128/64 result is the clearest warning that acceptable
recursive p95 error does not guarantee acceptable downstream decisions. Keep the negative result,
do not relax thresholds, and prioritize the honest offline package/defense over an unsafe live
10 Hz claim.

Additional profiling: Two Torch threads produce only a small exploratory improvement over one;
four/eight are worse. NumPy MLP inference, Torch tracing, and `torch.compile` are no faster for this
small repeated network. Dynamic int8 conversion fails because the installed Apple PyTorch build has
no quantized linear engine. These probes are diagnostic, not accepted performance artifacts.

Artifacts: `artifacts/residual/compression_001/`; the plot was visually reviewed. Prospective
freeze commit: `342720b`; runner commit/provenance: `56899c8`. Test files opened: zero.

## TSTEP-001 — reconcile planner dynamics substeps

Question: Should each 100 ms planning step use three `1/30 s` substeps, six `1/60 s` substeps, or
future recorded Unreal `dt` values?

Method: Strictly audit the seven SHA-256-approved train/validation episodes, opening zero pending
test files. Measure all 1,023 recorded transition durations. For physical comparison, select 74
validation windows spanning exactly 100 ms whose action and current movement parameters remain
constant. Linearly interpolate the authoritative endpoint between its surrounding finalized
samples, then roll the same observed state, hidden state, parameters, and local action under
recorded-`dt`, fixed-30, and fixed-60 schedules. Separately time complete 256/32/3 CEM calls under
both fixed schedules using one CPU thread, three warmups, and 30 alternating calls per controller.

Result: Train `dt` median/p95/max is `28.000/32.050/95.000 ms`; validation is
`27.000/40.900/96.000 ms`. Fixed-30 versus fixed-60 p95 errors are `0.539 vs 1.184 cm` position,
`2.320 vs 3.362 cm/s` velocity, `3.916 vs 3.288 deg` yaw, and `41.587 vs 40.460 deg/s` yaw rate.
Complete fixed-30 nominal/residual CEM p95 is `93.897/230.265 ms`; fixed-60 is
`143.565/371.585 ms`.

Decision: Select three `1/30 s` substeps. They better reproduce translation, preserve existing
scalar/vectorized parity, and keep nominal offline computation below 100 ms. The modest fixed-60
yaw advantage cannot compensate for worse translation and a failed nominal deadline. Recorded
future `dt` is a retrospective oracle, never a live input. Residual MPC still fails the runtime
gate; TSTEP-001 does not change that negative result.

Limitations: The physical comparison uses free-space constant-context windows and interpolated
100 ms endpoints. It does not establish collision fidelity or end-to-end latency. Fixed-30 nominal
p95 leaves little transport/application margin, and the 30-call latency samples remain bounded
benchmarks rather than live control evidence.

Artifacts: `artifacts/recovery/timestep_policy_001/`. Test files opened: zero.

## R0-EVAL-CONTRACT-001 — freeze separate prediction and control evaluation drafts

Question: What exact evidence would count as positive, negative, or unresolved before final data is
available?

Decision: Reserve 5301/5302 solely for recursive free-space prediction evaluation. Their frozen
schedules contain no contact, push, or setting override, so those prediction strata are explicitly
predeclared absent. Separately freeze 12 controller identities for timed-gate, post-push,
interpolated-deceleration, and OOD-deceleration execution. Nominal and residual MPC share each seed,
candidate noise, cost, horizon, budget, and scenario; only the transition model differs.

Primary analysis: Mean paired timed-gate success difference, residual minus nominal, with 10,000
paired percentile-bootstrap resamples at seed 20260905. Twelve pairs are planned and at least ten
must be valid. Positive requires at least +0.10 observed effect, an interval strictly above zero,
the collision and sub-100-ms runtime guardrails, and all four causal links. Significant harm or a
failed safety/runtime guardrail is negative; the exact complement is unresolved.

Integrity: Controller failures remain outcomes. Only predeclared infrastructure defects can
invalidate an attempt, which remains logged and may be retried once under the same identity. No
post-result seed substitution is permitted. The initial 42/96 cm capsule hypothesis was rejected by
a headless UE 5.8.2 query: transient construction of the actual `SandboxCharacter_Mover` found one
capsule with 30 cm radius and 86 cm half-height at unit scale. The final-control draft was corrected
before result collection; historical offline artifacts retain their declared provisional 42 cm
radius. Fourteen focused tests pass without accessing test episode bytes.

Pre-result review correction: A 700 cm push target with a 3.5 s timeout was unreachable under the
165 cm/s action cap, and world `+Y` was not intrinsically lateral under a relative reset yaw. The
reconciled draft uses a reachable reset-local 500 cm push target, 6 s timeout, a kick at 1.5 s,
4.5 s of post-kick observation, and a reset-local +Y 250 cm/s velocity delta transformed once to
world space at scenario start. The 0.10 primary effect is explicitly a proportion difference equal
to 10 percentage points.

Artifacts: `configs/final_prediction_manifest.yaml`, `configs/final_control_manifest.yaml`,
`motionworld/evaluation/contracts.py`, and `tests/unit/test_final_evaluation_contracts.py`.

## R1-OBS-001 — bounded causal observation contract

Question: Can Unreal's authoritative control snapshot be represented without mixing model inputs,
planner-only context, or stale identities?

Decision: Define `motionworld_control` observation v1 as deterministic compact UTF-8 JSON, maximum
16,384 bytes. Preserve separate episode, control-observation, and finalized-state sequences; require
the nominal-context sequence to equal the state sequence. Transmit only verified non-resimulated
state with known current nominal context and explicit optional-payload validity.

The complete deterministic timed-gate configuration/current state and target are planner-only.
`causal_dynamics_context` strips planner/scenario data before feature construction. Tests attack
missing/extra keys, coercible types, unsupported versions/controllers, non-finite values, wrong
dimensions/norms, stale action identity, invalid terminal state, duplicate keys, invalid UTF-8,
oversize, animation-root injection, and validity disagreement. Final-test bytes opened: zero.

## R1-ACT-001 — bounded action and sequence-admission contract

Question: Can Python return a diagnosable planner result without allowing validly encoded but stale,
future, duplicate, or cross-reset work to affect Unreal?

Decision: Define the v1 action as deterministic UTF-8 JSON bounded to 8,192 bytes. The command is
one character-local planar velocity tied to an episode and source observation. Controller/model,
monotonic planner duration, and explicit zero-action fallback are required. The selected trajectory
(maximum 32 steps) and exact cost breakdown are optional diagnostic telemetry only.

Result: Structural validation and current-observation admission are separate. Admission rejects
wrong episodes, sequences below/above the outstanding sequence, and replayed accepted sequences.
The existing Unreal command path already performs the required final clamp after local-to-world
conversion, so no redundant sanitizer was added. Focused action/observation/runtime tests pass
59/59; the full suite passes 458/458. Repository-wide Ruff, environment/package verification, and
`git diff --check` pass. Final-test episode bytes opened: zero.

## R1-TRANS-001 — bounded nonblocking loopback UDP

Question: Can Unreal and Python exchange bounded protocol bytes without waiting on Unreal's game
thread or letting malformed traffic allocate or process without a fixed limit?

Decision: Freeze IPv4 loopback UDP endpoints `127.0.0.1:52580` (Unreal) and `:52581` (Python), one
strict UTF-8 JSON object per datagram, 16,384-byte observations, 8,192-byte actions, 32 diagnostic
trajectory steps, a 65,507-byte raw receive ceiling, and 16 datagrams per nonblocking poll. Reject
unknown senders and empty/oversized traffic before JSON parsing. Do not retransmit obsolete control
work; semantic identity rejects duplicates/reordering and the runtime deadline handles loss.

Serialization review found that Python's prior 64-bit integer bound exceeded Unreal JSON's exact
binary64 integer range. All wire integers are now bounded to `2^53-1`; planner diagnostic timestamps
use monotonic microseconds rather than nanoseconds.

Result: The 75 focused protocol/runtime tests and all 474 Python tests pass. Repository-wide Ruff,
environment/package verification, and diff checks pass. Strict UE 5.8 universal Editor, Development, and
Shipping builds pass. The first Unreal test failed because macOS `HasPendingData` described queued
bytes rather than a dependable next-datagram length, causing a valid packet to be rejected when an
oversized packet followed it. Classification now uses the actual bytes returned into a fixed full-UDP
buffer. The corrected focused Unreal automation test passes. Evidence:
`evidence/unreal/r1_transport_udp_automation.log`. The byte transport remains isolated from gameplay.
Final-test episode bytes opened: zero.

## R1-XLANG-001 — shared protocol fixtures and Unreal action admission

Question: Do Python and Unreal agree on the exact version-1 wire semantics, including optional and
zero boundaries, or are their independently passing implementations merely self-consistent?

Decision: Package one full observation fixture and two action fixtures under
`Resources/ProtocolFixtures/v1`. Python strictly parses and canonicalizes the observation/action
bytes. Unreal parses the Python actions into typed fields and separately admits only the expected
episode and observation. Both sides reject bounded malformed data; the Unreal corpus explicitly
covers invalid UTF-8, truncated JSON, duplicate keys, wrong vector size, unsupported version,
infinite binary64 results, unsafe integers, wrong episode, future/stale sequence, and replay.

Result: The new Python cross-language suite passes 21/21; the combined focused protocol slice passes
83/83; and all 495 Python tests pass. Ruff, deterministic environment verification, interview-package
verification, and `git diff --check` pass. Strict universal UE 5.8 Editor Development, Game
Development, and Game Shipping builds pass. Headless Unreal automation discovered exactly one
`MotionWorld.Protocol.CrossLanguageFixtures` test and completed it successfully with exit code zero.
Evidence: `evidence/unreal/r1_cross_language_automation.log`. Fixtures contain no checkpoint/model
state and stay below frozen byte limits. This proves the isolated language boundary, not live UDP
deadlines or gameplay integration. Final-test episode bytes opened: zero.

## R1-GATE-001 — actual-sample protocol correctness

Question: Does the isolated version-1 protocol still compile and enforce its byte/semantic boundary
when deployed into the real UE 5.8 Game Animation Sample, without creating an early gameplay path?

Procedure: With Unreal closed, deploy only repository-owned plugin source, config, resources,
descriptor, and README; preserve generated/sample-owned directories. Verify source and fixture
parity, build `GameAnimationSampleEditor Mac Development` for arm64+x86_64, then run the complete
`MotionWorld.Protocol` automation prefix headlessly in that project. Separately search production
references for any transport/parser-to-bridge application path.

Result: Exact-sample universal compilation succeeded in 359.83 seconds. Automation discovered two
tests—`BoundedNonblockingUdp` and `CrossLanguageFixtures`—and both completed successfully; the test
process exited zero. Production references stop at isolated byte transport and typed validation;
neither file references the bridge, Mover, or an application function. Thus R1 cannot mutate
gameplay, even from a valid packet. Evidence:
`evidence/unreal/r1_actual_sample_protocol_automation.log`. The complete isolated protocol slice is
committed as `d85eeaf`. Gate R1 passes 6/6; Section 2 is 41/41. Final-test episode bytes opened: zero.

## R2-SVC-001 — bounded latest-only Python service lifecycle

Question: Can the Python side start cleanly, receive only configured loopback observations, validate
before planner dispatch, abandon obsolete work, expose bounded status, and release all I/O without
depending on notebook/import history?

Decision: Add a strict service config, installed/module entry points, one nonblocking UDP owner, a
bounded episode/sequence state machine, and a latest-only daemon planner worker. Supersession signals
cooperative cancellation and replaces pending work; completion identity is rechecked before strict
action serialization. Health diagnostics expose only bounded labels/counters. CLI execution uses an
honestly labelled zero safe-fallback planner until R2.3.

Result: Fourteen focused lifecycle tests pass. They include actual loopback datagrams, a blocked
planner superseded by a newer observation, proof that only the new identity is transmitted, active
shutdown cancellation, socket rebinding, bounded identity memory, and a subprocess configuration
load. The installed `motionworld-control-service --check-config` command returns `config_valid` from a
frozen clean environment. Two first-run test races were corrected by waiting for the worker callback
and receiver readability; neither required a service-semantic change. Final-test episode bytes
opened: zero.

## R2-NET-001 — default-off Unreal network runtime lifecycle

Question: Can the actual Game Animation Sample host a bounded 10 Hz Unreal network controller that
rejects temporally ineligible actions and reaches a deterministic safe stop without weakening the
existing bridge's authoritative state or command boundary?

Method: Implement the schedule/deadline/fallback rules in a pure runtime kernel, serialize real
finalized state plus aligned Smooth Walking context into observation v1, and put UDP ownership in a
separate default-off actor component. Compile with strict includes and unity disabled for universal
Mac Editor/Development/Shipping targets. Deploy repository-owned source only into the actual UE
5.8.2 sample, build its universal Editor target, and run the `MotionWorld.Network` automation prefix
headlessly. Run all Python tests and Ruff. Do not open final-test episode files.

Result: Strict isolated builds pass for universal Mac Editor Development, Game Development, and
Game Shipping. The actual sample universal Editor build passes. Automation discovers exactly two
tests. `ObservationSerialization` passes default-off, bounded schema, previous-action chronology,
and aligned-context checks. `RuntimeLifecycle` passes first/boundary emission, no catch-up burst,
current identity admission, exclusive deadline, first/second hold, third-miss zero, and stopped-state
checks. Both pass with zero warnings/errors from the tests. The complete Python suite passes 509/509
and Ruff passes.

One first automation run failed four assertions because the test used literal `20.2` as the result
of `20.1 + 0.1`; binary64 represented the computed deadline a few quadrillionths later. The fixture
was corrected to test misses at 101 ms, safely beyond the boundary. The production comparison stayed
exclusive, and a separate exact-boundary action assertion remained. This was a test-oracle precision
error, not a fallback-policy change.

Interpretation: R2.2's implementation and bounded automation obligations pass. This does not prove
that a Python action traverses the complete live loop, that 100 consecutive intervals reconcile, or
that service-loss behavior is visible in a running pawn. Those remain R2.3-R2.5 and Gate R2.
Evidence: `evidence/unreal/r2_runtime_lifecycle_automation.log`. Final-test episodes 5301/5302 were
not opened.

## R2-CTRL-001 — bounded echo/reactive controller code gate

Question: Can deliberately simple, stateless Python controllers produce bounded current-identity
actions from real protocol observations, including a world-space target expressed through
authoritative character yaw, without weakening the Unreal safety boundary?

Method: Add strict controller parameters in service-config schema 2. Exercise stop, forward, right,
diagonal, reverse, over-speed, configured-bound, observed-bound, yaw-zero/yaw-90, arrival,
target-absent, cancellation, and new-episode cases. Extend Unreal's optional planner target with
finite validation and exact absent/present JSON shapes. Build the plugin for universal Mac Editor,
Development, and Shipping with strict includes/unity disabled; build and test the actual sample.

Result: Controller tests pass 20/20, service tests 15/15, and the complete Python suite 530/530.
Ruff passes. The initial strict C++ build usefully failed on unavailable UE convenience methods;
the implementation now performs explicit component finite checks and the test uses
`std::numeric_limits`. The corrected three-target universal plugin build and actual-sample universal
Editor build pass. Actual-sample automation completes both `MotionWorld.Network` tests successfully;
raw evidence is `evidence/unreal/r2_controller_automation.log`. No final-test files were opened.

Interpretation: The first two R2.3 implementation items pass. Live stop/direction/bound, yaw,
sequence, and reset evidence remain open, so neither R2.3 nor Gate R2 is accepted yet.

Live-evidence readiness: Added a default-off 2,048-line cap and session identity around explicit
observation-sent, action-accepted, reset-boundary, episode-start, and EndPlay-summary records. The
control path and default behavior are unchanged. Strict universal Editor/Development/Shipping
plugin compilation passes, the actual universal sample builds, and both network automation tests
pass. Evidence: `evidence/unreal/r2_live_evidence_instrumentation_automation.log`. The next result
must come from PIE; automation is not substituted for live proof.

Live attempt 1 result: rejected. PIE enabled the network component on ports 52580/52581 and verified
resets 7201/7202, but the bounded evidence switch remained off and the bridge's varied-action
schedule remained on. The schedule's later `ProduceInput` command overwrote the Python safe-zero
echo, so neither visible motion nor bridge echo lines can be attributed to network control. The raw
diagnostic excerpt and rejection rationale are preserved in
`evidence/unreal/r2_live_attempt_1_invalid.log`; it earns no R2.3 checklist credit.

Corrective result: Network enablement now rejects the competing varied schedule before opening the
transport. Strict non-unity universal Mac Editor/Development/Shipping plugin builds pass. The exact
source deployed into the actual Game Animation Sample builds for universal Editor, and its focused
automation finds exactly two `MotionWorld.Network` tests; both pass, including true/false
single-owner assertions. Full Python remains 530/530 and Ruff passes. Evidence:
`evidence/unreal/r2_action_owner_guard_automation.log`. A clean live retry still remains required.

Live attempt 2 result: accepted for the stop, applied-identity, and cross-reset non-reuse claims.
Session `02334940284C` emitted 269 observations and accepted 267 exact-zero echo actions across
episodes 7211/7212. Every accepted source had been emitted, and every acceptance reports current
identity plus arrival before the exclusive deadline. Latency was 23.495/39.852/87.524 ms
min/median/max. Both episode-zero observations explicitly omit previous action. The 7211 reset
boundary cleared outstanding/action state before 7212 restarted at observation zero. One response
to superseded 7211 observation 8 was rejected stale; it was never applied. The final emitted 7212
observation was followed immediately by teardown. There were no misses, holds, safe stops,
malformed messages, or evidence drops. Exact lines and audit are preserved in
`evidence/unreal/r2_live_echo_stop_sequence_reset.log`. Direction/bound and nonzero-yaw proof remain.

Direction-trial preparation: freeze five named schema-v2 service configs for forward `(100,0)`,
right `(0,100)`, diagonal `(100,100)`, reverse `(-100,0)`, and deliberately oversized
`(1000,1000)` local cm/s. The default `control_service.yaml` remains safe-zero. Unit tests load every
named file and bind its label to the intended vector and localhost endpoint. This removes manual
Python-config editing as a source of trial drift; each live run still receives fresh episode IDs.

Forward result: accepted session `31E1BBC5684B`, episode 7221. The candidate observed steady
straight-forward motion. Unreal accepted 224/224 current, before-deadline actions and the bridge
independently retained 224 exact local `(100,0)` to world `(100,0)` Mover echoes with `match=true`
at zero yaw. Latency min/median/p95/max was 14.714/19.813/27.873/51.494 ms. Sampled X moved from
-800.00 to 1352.09 cm with zero sampled Y range and 100.00 cm/s maximum sampled X velocity. No
rejection, stale packet, malformed packet, miss, hold, safe stop, or evidence drop occurred.
Evidence: `evidence/unreal/r2_live_echo_forward.log`. Aggregate direction/bound and nonzero-yaw
items remain open.

Right result: accepted session `FA65DFAE6B4C`, episode 7231. The candidate observed rightward
strafing with facing retained. Unreal accepted 136 right actions; all were current, before deadline,
and exact local/world `(0,100)` cm/s. The bridge retained 137 matching right echoes because one
superseded response caused one declared miss/hold of the prior validated command. Latency
min/median/p95/max was 13.518/20.951/34.418/55.351 ms. Sampled Y moved 1208.07 cm with zero X range
and yaw held at zero. There was no malformed message, safe stop, or evidence drop. Evidence:
`evidence/unreal/r2_live_echo_right.log`. Aggregate direction/bound remains open.
