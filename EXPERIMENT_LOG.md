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
