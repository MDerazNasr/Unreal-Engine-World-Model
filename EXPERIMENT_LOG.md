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
| VAR-DATA-001 | Does the deterministic schedule produce valid stop/reverse/turn coverage? | Day 2 | Completed |
| NOM-ROLL-001 | How does faithful nominal error compound over 0.5/1.0/1.5 s? | Day 2 | Completed |
| FACING-001 | Does an explicit antipodal tie-break remove the known angular rollout spike? | Day 2 | Completed |
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
