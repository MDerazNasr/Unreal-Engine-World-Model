# MotionWorld Decision Log

This is a living record. Add an entry before or immediately after every material design change.

## Required template

```text
Decision ID:
Status: proposed | accepted | superseded | rejected
Decision:
Why:
Alternatives considered:
Evidence:
Main assumption:
How it could fail:
How I tested it:
Related config/commit/experiment:
```

## D-001 - Narrow state-space world model

Status: accepted

Decision: Model authoritative short-horizon character dynamics rather than pixels, poses, or the entire Unreal world.

Why: CEM needs hundreds of inexpensive batched futures, and the interview role values end-to-end applied ML rather than model scale alone.

Alternatives considered: visual diffusion world model; full learned transition without structure; pose generator.

Evidence: The decision-relevant state is low-dimensional and directly available from Unreal.

Main assumption: Short-horizon actor state contains enough information for the chosen scenarios when augmented with limited history and known nominal state.

How it could fail: Important contact or controller state is unobserved for longer than the history window.

How I tested it: Planned no-history/history comparison and error stratification.

Related config/commit/experiment: pending.

## D-002 - Fair nominal baseline

Status: accepted

Decision: Reproduce known Smooth Walking dynamics and carry known internal spring state; do not ask the residual network to rediscover equations available to the planner.

Why: A deliberately weak nominal model would invalidate the causal comparison.

Alternatives considered: clipped-acceleration-only predictor; current specification's reduced visible-state approximation.

Evidence: Smooth Walking explicitly uses acceleration and intermediate velocity/rotation spring state and warns about external-force synchronization and timestep sensitivity.

Main assumption: Required parameters and enough state can be obtained, mirrored, or synchronized reliably.

How it could fail: Mover hides internal values required for exact synchronization.

How I tested it: Day-1 API feasibility audit followed by recorded one-step and recursive comparisons.

Related config/commit/experiment: pending.

## D-003 - Authoritative actor state

Status: accepted

Decision: Use post-movement actor/capsule state for dynamics; record animation root and toe transforms only for animation QA.

Why: Gameplay collision state and rendered animation can deliberately diverge. Mixing them makes targets inconsistent.

Alternatives considered: animation-root position as model state; hybrid state source.

Evidence: Motion Matching responds to the movement trajectory while animation techniques separately manage visual displacement and foot locking.

Main assumption: Post-movement state can be sampled at a deterministic point in the tick.

How it could fail: Sampling order changes or logging occurs before the authoritative movement update.

How I tested it: Planned tick-order integration test and separate actor/root traces.

Related config/commit/experiment: pending.

## D-004 - Component workflow

Status: accepted

Decision: Every component follows understand -> derive -> implement small unit -> test independently -> explain -> commit.

Why: This keeps generated implementation subordinate to personally owned reasoning.

Alternatives considered: end-to-end generation followed by retrospective understanding.

Evidence: Small modules and commits make mathematical and implementation errors easier to identify and revert.

Main assumption: The schedule can preserve a short teaching/review step at every gate.

How it could fail: Demo pressure encourages skipping derivation or independent tests.

How I tested it: Every day in `PROJECT_PLAN.md` includes Builder, Reviewer, Examiner, and candidate-teaching checkpoints.

Related config/commit/experiment: documentation foundation.

## D-005 - Branch and commit policy

Status: accepted

Decision: Use one short-lived branch per coherent milestone, merge only after its gate passes, and create small tested commits within the branch.

Why: Isolates risk without creating unnecessary concurrent integration work in a deadline-compressed solo build.

Alternatives considered: all work directly on `main`; one long-lived feature branch; a branch for every tiny file.

Evidence: The repository begins from one small initial commit and has no compatibility obligations yet.

Main assumption: Milestones remain separable and are merged sequentially.

How it could fail: Unreal assets create large binary conflicts across overlapping branches.

How I tested it: Branch-close checklist requires tests, documentation, clean diff, and memory handoff before merge.

Related config/commit/experiment: `docs/project-foundation`.

## D-006 - AnimGen is not P0

Status: accepted

Decision: Use Game Animation Sample/Mover first; attempt AnimGen only after the central causal comparison works.

Why: AnimGen is experimental and adds integration surface without strengthening the core state-dynamics claim.

Alternatives considered: begin with AnimGen because it is recent and interviewer-visible.

Evidence: Current Epic documentation marks the plugin experimental and lists a substantial dependency graph.

Main assumption: Game Animation Sample provides sufficient presentation quality.

How it could fail: Desired-velocity control cannot be introduced cleanly in the sample.

How I tested it: Day-1 feasibility gate with Manny plus Mover fallback.

Related config/commit/experiment: pending.

## D-007 - No target leakage into character dynamics

Status: accepted

Decision: The residual dynamics model receives character state, known nominal state/history representation, and candidate action; target and simple obstacle geometry remain planner context.

Why: Target/scenario correlations can reduce validation error without representing execution dynamics.

Alternatives considered: include all logged observation fields in the MLP.

Evidence: The target affects the next actor state through the selected action, while simple obstacle motion and clearance are analytically known.

Main assumption: Contact effects can be represented without goal features.

How it could fail: Obstacle/contact context is genuinely required to predict execution error.

How I tested it: Near-contact error strata and a documented contact-context ablation if needed.

Related config/commit/experiment: pending.

## D-008 - Deadline-compressed evidence ladder

Status: accepted

Decision: Preserve the specification's scientific gates but execute them on a dated five-build-day schedule, with an explicit evidence ladder from theory proof through full Unreal control proof.

Why: The interview is Friday 4 September at 15:00, leaving fewer implementation days than the PDF's seven-day assumption.

Alternatives considered: Pretend all seven stages are full calendar days; remove evaluation gates to save time; claim synthetic results as project results.

Evidence: Calendar check and environment inventory on 30 August 2026.

Main assumption: A small Python test double can de-risk interfaces while Unreal installs without diverting work from the real experiment.

How it could fail: Time spent polishing the synthetic proof delays engine integration, or the Unreal download/toolchain consumes the critical path.

How I tested it: Dated stop/go deadlines and a code freeze are recorded in `PROJECT_PLAN.md`; every package claim must state its achieved evidence level.

Related config/commit/experiment: `PLAN-002`; `docs/project-foundation`.

## D-009 - Python 3.12 ML environment

Status: accepted

Decision: Use a project-local `uv` environment based on `/opt/homebrew/bin/python3.12`; do not use the system/default Python 3.14 for training.

Why: Python 3.12 is available and broadly supported by the requested ML stack, while the detected Python 3.14 environment has no PyTorch.

Alternatives considered: Install packages globally into Python 3.14; use an unspecified Conda environment.

Evidence: Environment inventory on 30 August 2026.

Main assumption: Required PyTorch packages support the Apple Silicon/Python 3.12 combination.

How it could fail: Package resolution or MPS-specific operators fail; CPU execution remains the deterministic fallback for this small model.

How I tested it: Installation and import smoke tests are the first implementation task; versions will be frozen in the lockfile.

Related config/commit/experiment: `PLAN-002`.

## D-010 - CPU reference and measured MPS acceleration

Status: accepted

Decision: Use CPU float64/float32 computations as deterministic unit-test oracles. Permit Apple MPS for measured training experiments only after the relevant implementation passes CPU tests and CPU/MPS numerical parity is checked.

Why: Exact repeatability and transparent tolerances matter more than training speed for unit tests. The M4 GPU is available and can accelerate later training, but accelerator kernels and numerical order may differ.

Alternatives considered: Make MPS the default for every test; disable MPS entirely.

Evidence: PyTorch 2.13.0 reports MPS built and available outside the sandbox. The fixed-seed CPU smoke operation repeated exactly, and three environment tests passed.

Main assumption: The planned sub-500K-parameter model and dataset can train acceptably on CPU if an MPS operation is unsupported.

How it could fail: CPU training is too slow for the deadline, or MPS numerical differences change model behavior materially.

How I tested it: Environment verifier reports CPU/MPS capabilities; later model work will add explicit parity tolerances and runtime measurements.

Related config/commit/experiment: `FEAS-000`; `scripts/verify_environment.py`.

## D-011 - Isolated Unreal bridge component

Status: accepted by the candidate; behavior-free live integration and human-control parity pass, runtime ordering remains an explicit test gate

Decision: Track MotionWorld as an isolated project plugin rather than editing Epic's downloaded sample module or licensed assets. Attach a `UMotionWorldBridgeComponent` to the sample Mover pawn. When automated control is enabled, the component participates in Mover input production and overwrites `FCharacterDefaultInputs` with a clamped world-space velocity command. It samples the finalized `FMoverDefaultSyncState` through `OnPostFinalize`.

Why: The sample contains licensed Blueprint/assets and a precompiled `GameAnimationSample` module without a visible `Source/` directory. UE 5.8.2 explicitly supports actor components implementing `IMoverInputProducerInterface`, and the Mover component gathers them at `BeginPlay`. `OnPostFinalize` provides finalized state on the game thread and keeps gameplay/collision state separate from the visual mesh.

Alternatives considered: Modify the sample Blueprint's large `ProduceInput` graph directly; replace the pawn; edit the opaque sample module; sample ordinary actor tick; use `OnPostMovement`, whose state is still mutable.

Evidence: Installed UE 5.8.2 source in `MoverComponent.h/.cpp` and `MoverDataModelTypes.h`; sample asset inspection identifies `/Game/Blueprints/SandboxCharacter_Mover`, `CharacterMoverComponent`, and a walking Blueprint derived from `USmoothWalkingMode`.

Main assumption: `bGatherInputFromAllInputProducerComponents` remains enabled and the bridge component is gathered after the pawn producer, as implemented by UE 5.8.2. The experiment is initially standalone/local rather than networked.

How it could fail: Producer ordering changes, a sample setting disables component gathering, or the Blueprint rewrites the same command after the component. In that case, explicitly set a composite input producer rather than relying on ordering.

How I tested it: The behavior-free plugin compiled and packaged for universal Mac Editor Development, Game Development, and Game Shipping targets with strict includes. It also compiled inside the actual sample's universal Development Editor target, loaded during startup, and reached a 0-error/0-warning Map Check. The candidate confirmed manual movement and turning remained unchanged with the plugin enabled. The later command-path proof must inspect `GetLastInputCmd()` and show that the commanded `EMoveInputType::Velocity` and vector exactly match the clamped command.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`; `d2218fe`.

## D-012 - Bounded world-space command echo before local-frame control

Status: accepted; sanitizer automation and live-sample command echo pass

Decision: First prove the raw Mover seam with an opt-in planar world-space velocity command. Reject non-finite input, remove vertical input, clamp planar magnitude to 600 cm/s by default, preserve existing world-space facing intent, and compare the post-finalization `GetLastInputCmd()` packet with the quantized submitted command. Keep automation disabled by default and keep the final model-facing character-local action adapter as a separate next slice.

Why: This isolates input-production and producer-ordering risk from coordinate-conversion risk. Echoing the retained packet proves more than observing that our callback ran, while default-off behavior preserves the sample baseline.

Alternatives considered: Add networking, logging, reset, and coordinate conversion simultaneously; infer command success only from visible movement; expose unbounded Blueprint velocity; overwrite input even when automation is disabled.

Evidence: UE 5.8.2 source shows the pawn producer is added before gathered component producers, `SetMoveInput` quantizes to 0.01 cm/s, `GetLastInputCmd()` exposes the most recently used packet, and standalone asynchronous input production defaults off. The strict universal Mac Editor/Development/Shipping build passes after Reviewer-requested game-thread enforcement.

Main assumption: The current standalone sample leaves component gathering enabled and runs input production on the game thread. World-space velocity is only the engine probe; the planner contract remains character-local.

How it could fail: Another producer runs after the bridge, component gathering is disabled, input production is moved off-thread, or the sample interprets the retained command differently than expected. Echo mismatch must stop the experiment rather than be hidden.

How I tested it: Boundary cases for zero, exact maximum, oversized diagonal input, reverse input, vertical projection, and NaN rejection compile into the Unreal automation suite. The actual sample target compiled for universal Mac, and a headless actual-sample Editor run executed the suite: 1 test succeeded, 0 failed, 0 warnings, in 0.0149 seconds. The candidate attached the component locally with automation disabled; three PIE starts logged readiness on `SandboxCharacter_Mover_C_0`, and manual movement remained unchanged. PIE then retained both zero and `(200, 0, 0)` cm/s velocity packets with `match=true`; the character moved steadily, collision stopped executed motion, jump remained available, and the final session logged automation disabled.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`.

## D-013 - Character-local planner action resolved from authoritative Mover yaw

Status: implementation compiles strictly; actual-sample test execution and live rotated-command proof are pending

Decision: Make character-local velocity the default planner-facing command frame (`+X` forward, `+Y` right). Resolve it to Mover world space using yaw from the current `FMoverDefaultSyncState`. Retain explicit world mode only for engine diagnostics, and provide the inverse world-to-local function for later authoritative velocity observations.

Why: A local action has stable semantics as the character turns and matches the project specification. Using the same authoritative Mover orientation for both directions prevents camera, controller, animation, and gameplay frames from being mixed.

Alternatives considered: Keep world-space actions throughout the ML system; use camera yaw; use the rendered mesh transform; rotate through full pitch/roll for a planar ground controller; combine conversion with state logging before testing it independently.

Evidence: The Unreal planar yaw equations are implemented as a pure module. Compiled automation cases cover yaw 0, 90, 180, and -90 degrees, local right at 90 degrees, vertical removal, and a non-cardinal local/world round trip. Strict universal Mac Editor/Development/Shipping builds pass.

Main assumption: The Mover default sync-state orientation at input production is the gameplay-facing frame intended by the planner. P0 movement is planar.

How it could fail: Axis signs are wrong, degrees are treated as radians, orientation comes from the wrong subsystem, sync state is unavailable, or a rotated packet echoes but visible motion is inconsistent. Missing/invalid state fails closed and is forbidden from reporting `match=true`.

How I tested it: Strict compilation passes. Next execute both MotionWorld automation tests in the actual sample, then compare local forward commands under visibly different starting yaws and inspect the logged resolved world vectors.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`.
