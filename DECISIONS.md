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

Status: accepted; strict builds, actual-sample automation, and visible local-axis control pass

Decision: Make character-local velocity the default planner-facing command frame (`+X` forward, `+Y` right). Resolve it to Mover world space using yaw from the current `FMoverDefaultSyncState`. Retain explicit world mode only for engine diagnostics, and provide the inverse world-to-local function for later authoritative velocity observations.

Why: A local action has stable semantics as the character turns and matches the project specification. Using the same authoritative Mover orientation for both directions prevents camera, controller, animation, and gameplay frames from being mixed.

Alternatives considered: Keep world-space actions throughout the ML system; use camera yaw; use the rendered mesh transform; rotate through full pitch/roll for a planar ground controller; combine conversion with state logging before testing it independently.

Evidence: The Unreal planar yaw equations are implemented as a pure module. Compiled automation cases cover yaw 0, 90, 180, and -90 degrees, local right at 90 degrees, vertical removal, and a non-cardinal local/world round trip. Strict universal Mac Editor/Development/Shipping builds pass.

Main assumption: The Mover default sync-state orientation at input production is the gameplay-facing frame intended by the planner. P0 movement is planar.

How it could fail: Axis signs are wrong, degrees are treated as radians, orientation comes from the wrong subsystem, sync state is unavailable, or a rotated packet echoes but visible motion is inconsistent. Missing/invalid state fails closed and is forbidden from reporting `match=true`.

How I tested it: Strict universal Editor/Development/Shipping compilation passes. The actual universal sample target builds in 18.02 seconds. A headless actual-sample run executes both MotionWorld tests: 2 succeeded, 0 failed/warnings, total 0.0322 seconds. At one unchanged initial facing, the candidate observed steady local-forward and local-right automatic paths approximately 90 degrees apart, then restored automation disabled and the local request to zero. The retained runtime log independently captures the local-right trial at authoritative yaw 0 degrees: requested local `(0, 200, 0)` cm/s resolved and echoed as world `(0, 200, 0)` cm/s with `match=true`. The forward trial was visually observed but was not separately retained in the current log; its yaw-0 mapping is covered by the executed cardinal automation test.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`.

## D-014 - Versioned finalized authoritative-state snapshot

Status: accepted; strict builds, actual-sample automation, and live finalized-state evidence pass

Decision: Capture a version-1 gameplay-state snapshot from the `FMoverDefaultSyncState` supplied directly to `OnPostFinalize`. Store explicit world position, world velocity, character-local planar velocity, yaw plus sine/cosine facing, world angular velocity, movement mode, end-of-step simulation time, step duration, Mover frame, resimulation flag, validity, and a monotonic callback sequence. Keep this in memory with throttled diagnostic logging; do not add episode file I/O or reset in the same slice.

Why: A learned transition needs the executed post-collision outcome, not the requested action or animation-root transform. Explicit units, frames, timing, and validity prevent silent dataset corruption and make the boundary independently testable before persistence is added.

Alternatives considered: Sample actor tick; read the rendered mesh; log only requested commands; add CSV/UDP/reset simultaneously; use yaw alone as the learned facing feature; assume every finalization callback is a unique forward simulation step.

Evidence: UE 5.8.2 declares `OnPostFinalize` immutable and game-thread-only but notes that it may represent resimulation. `FMoverDefaultSyncState` exposes world-space getters for location, velocity, orientation, and angular velocity. `GetLastTimeStep()` exposes start time, step duration, server frame, and resimulation flags.

Main assumption: The standalone Game Animation Sample's finalized Mover state is the correct gameplay/collision source of truth, and its normal forward run supplies a finite positive timestep.

How it could fail: A missing default sync block, non-finite data, duplicate/rewound simulation time, an incorrect end-of-step timestamp, coordinate-frame leakage, or a logging rate that harms runtime. Invalid state fails closed; timestep/resimulation metadata remains explicit; later episode logging must deduplicate by simulation chronology rather than callback count alone.

How I tested it: The pure builder tests a hand-calculated yaw-90 conversion, world/local separation, yaw normalization and sine/cosine, sequence advancement, missing source, non-finite input, and non-positive timestep. Strict universal Mac Editor Development, Game Development, and Game Shipping builds pass. The actual universal sample target built in 17.84 seconds, and all three MotionWorld tests completed with `Success`. A live default-off PIE run retained 13 throttled samples over sequences 0-720 and simulation times 0.071-39.317 seconds with zero invalid, resimulated, non-monotonic, or non-positive-step samples. The stream covers rest, translation, turning, near-zero motion, and a `Traversing` mode change with elevated world Z. At yaw approximately -45 degrees, world velocity `(266.25, -266.25)` cm/s resolves to local `(376.53, approximately 0)` cm/s as expected.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`.

## D-015 - Fail-closed causal transition contract

Status: accepted; strict builds and actual-sample automation pass

Decision: Represent one learning candidate as `(previous finalized state, applied desired-velocity
action, measured step duration, next finalized state)` under explicit episode and transition IDs.
Convert the action to character-local coordinates using the previous state's yaw. Reject invalid,
resimulated, non-adjacent, unsupported-schema, non-increasing-time, timestep-mismatched,
non-finite, or non-planar candidates rather than repairing them silently.

Why: A dynamics model learns cause and effect. Pairing an action with the wrong state interval, or
using the outcome's orientation to encode the input, creates label leakage and teaches a physically
false transition. Explicit rejection reasons make dataset loss measurable instead of invisible.

Alternatives considered: Log independent state and action streams and join them later by callback
order; use the next state's yaw; accept gaps and resimulation; force every step to `1/60` seconds;
mix direction-intent and desired-velocity packets; add file persistence in the same slice.

Evidence: A pure reflected builder and focused Unreal automation test cover one hand-calculated
valid transition plus missing IDs, unsupported input type, NaN/infinity, vertical action,
resimulation, state/frame gaps, changing frame availability, invalid negative frames, repeated time,
timestep disagreement, unknown schema, and invalid state. The valid test intentionally changes yaw
from `90` to `45` degrees so using the wrong endpoint frame cannot pass accidentally.

Main assumption: The following recorder can call this builder from `OnPostFinalize` with the cached
prior state and the velocity payload from Mover's `GetLastInputCmd()` for the step that just ended.
The observed runtime has variable step lengths, so measured `delta_t` remains part of every row.

How it could fail: Callback/input chronology differs from the assumed Mover contract; a legitimate
step omits or changes frame metadata; the 1 ms time-consistency tolerance is too strict; or future
input types need distinct schemas. The recorder must count rejection reasons and live-test action
alignment before any dataset is trusted.

How I tested it: Strict universal Mac Editor Development, Game Development, and Game Shipping
compilation passes. The deployed source matches the closed sample, whose universal Editor target
built in 17.29 seconds. A headless actual-sample run found all four MotionWorld tests and completed
the command, coordinate, state, and causal-pairing suites with `Success`; the queue ended after four
tests with no D-015 failure.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`.

## D-016 - Bounded in-memory episode recorder

Status: accepted; strict builds, actual-sample automation, and live PIE chronology gate pass

Decision: Add an opt-in, game-thread-owned recorder with explicit episode start/stop, first-state
seeding, attempt-based transition sequence numbers, per-reason rejection counts, recovery seeding,
and a hard non-overwriting capacity. At `OnPostFinalize`, pair the cached prior finalized state with
Mover's most recently used velocity packet and the newly finalized state. Keep persistence and
reset out of this slice.

Why: The transition contract only validates supplied values. A recorder is required to prove the
live temporal join and to make missing or rejected data observable. A fixed buffer prevents a long
PIE session from consuming unbounded memory or silently overwriting the beginning of an episode.

Alternatives considered: Independent state/action logs joined offline; automatic recording by
default; accepted-row-only numbering; overwrite-oldest ring buffer; keep an invalid/resimulated
endpoint as the next seed; add CSV and reset simultaneously.

Evidence: UE 5.8 assigns `CachedLastUsedInputCmd` and the matching timestep at the end of simulation
before the backend calls `FinalizeFrame` and broadcasts `OnPostFinalize`. The pure recorder test
covers disabled behavior, invalid start parameters, first-state seeding, a valid hand-calculated
pair, unsupported-action rejection, recovery with a visible sequence gap, capacity stop without
overwrite, restart clearing, invalid seed rejection, and resimulation de-seeding. Strict universal
Editor Development, Game Development, and Game Shipping builds pass. In live PIE, episode 1601
seeded state 0 and recorded 922 consecutive transitions from 923 observations under the consumed
character-local `(200, 0, 0)` cm/s command. The first pair was state 0 to 1; periodic evidence
continued through pair 899 to 900; the EndPlay summary reported `attempted=922`, `recorded=922`,
`rejected=0`, `rejected_seeds=0`, and `capacity_drops=0`.

Main assumption: `GetLastInputCmd()` and `GetLastTimeStep()` still describe the simulation step
whose state is being finalized for the standalone sample. Match-based automation provenance is
sufficient for this experiment because MotionWorld disables movement-base-relative input and
verifies the consumed velocity against its quantized submission.

How it could fail: An unchanged-frame callback reuses stale timestep/input metadata; another input
producer writes the same velocity; a delegate changes automation between production/finalization;
or normal callbacks violate the strict adjacency/timestep tolerance. The live run must inspect
every rejection count and the exact state/frame/time/action sequence before persistence is allowed.

How I tested it: Repository tests, Ruff, and diff checks pass. Unreal Header Tool generated the new
reflected API, and strict non-unity universal builds pass for all three targets. Deployed source
matches the closed sample; its universal Editor target built successfully, and a headless run found
five MotionWorld tests and completed every suite with `Success`. The live opt-in episode reconciled
every adjacent observation into one accepted transition with no rejection or capacity loss.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`.

## D-017 - Verified Mover-owned character reset

Status: accepted; strict builds, actual-sample automation, and live same-session repeatability pass

Decision: Capture a valid finalized gameplay anchor, then reset through Mover's queued teleport and
non-additive zero-velocity effects. Stop the old episode before queuing, force a zero command during
the reset frame, mark Smooth Walking's prior generated-move state stale, and start the new episode
only after a bounded post-finalization verifier accepts position, yaw, velocities, and movement
mode. Keep the global callback sequence monotonic while restarting episode-local transition IDs.

Why: Actor transform alone is not the simulation state. Mover can otherwise retain authoritative
velocity, cached floor/base information, and Smooth Walking spring history, or overwrite a direct
scene transform on its next frame. Delaying recorder start prevents a teleport from becoming a
false learned transition.

Alternatives considered: Direct `SetActorTransform`; direct mutation of Mover's protected cached
state; accept the first callback without verification; start recording before the teleport; reset
the animation graph and whole arena in the same slice; treat a new PIE session as reset evidence.

Evidence: UE 5.8's public API queues instant effects into the simulation. Its teleport effect writes
the finalized transform and invalidates floor/base cache entries; its non-additive velocity effect
writes linear velocity, zero angular velocity, and an explicit movement mode. Smooth Walking source
shows that a stale `DidGenerateMove` entry reinitializes all five spring/intermediate quantities
from current velocity/facing. `OnPostFinalize` supplies the authoritative state needed for a
fail-closed acceptance check.

Main assumption: The standalone sample uses the inspected non-async Mover path and its registered
`Walking` mode is the same Smooth Walking implementation whose rollback marker was audited.

How it could fail: Another queued effect, modifier, or layered move acts after reset; teleport is
collision-adjusted; the reset anchor is unsafe; a backend changes effect ordering; the rollback
marker cannot be written externally; or an external system mutates gameplay state before
finalization. The verifier must reject these observable mismatches, and the implementation must not
claim reset of unobservable animation or arena state.

How I tested it: The pure verifier executes exact, wrapped-yaw, inclusive-boundary, invalid target,
invalid tolerance, invalid/resimulated state, position, facing, linear/angular velocity, and mode
cases. Strict non-unity universal Mac Editor Development, Game Development, and Game Shipping builds
pass. The committed source matches the actual closed sample; its universal Editor target builds,
and all six actual-sample MotionWorld tests complete with `Success`. In one live PIE session, reset
1701 moved 483.813 cm and reset 1702 moved 509.037 cm. Both were accepted on their first newer
finalized sample at the same pose and mode with zero measured position, yaw, linear-speed, and
angular-speed error. Episode 1701 recorded 60 consecutive transitions with zero rejection before
the second reset; episode 1702 then seeded only from the verified post-reset state and recorded
1,189 consecutive transitions with zero rejection before PIE ended. No training transition spans
either reset boundary.

Related config/commit/experiment: `FEAS-001`; `unreal/Plugins/MotionWorld`.

## D-018 - Atomic versioned episode export

Status: accepted; strict builds, actual-sample automation, and independent live-file validation pass

Decision: Export one completed in-memory episode as UTF-8 JSON Lines under
`Saved/MotionWorld/Episodes`. Write a typed header, one object per already-accepted transition, and
a completeness footer to a unique temporary file; close and rename it without replacement. Keep
export opt-in and synchronous at episode stop. Independently validate the file in Python before it
can enter a dataset.

Why: A single JSON array duplicates the whole bounded episode in serialization memory, while CSV
flattens nested state/action structure and makes schema evolution ambiguous. JSON Lines has bounded
per-row serialization memory, remains human-inspectable, and supports strict record typing. A
temporary file plus no-replace publication prevents partial or older evidence from looking valid.

Alternatives considered: CSV; one monolithic JSON object; writing each row directly to the final
destination during play; overwriting `episode_<id>`; asynchronous export that copies the full
buffer; accepting any dictionary shape in Python.

Evidence: The C++ test publishes a two-row UTF-8 file and parses its header, transition, and footer.
It also proves no overwrite and rejects empty data, inconsistent counters, and mixed episode IDs
without publishing a destination. The Python loader passes valid and explicit-rejection-gap cases
and rejects missing footer, non-finite values, local/world action mismatch, mixed identity, broken
endpoint chains, and unknown fields. Strict universal Mac Editor/Development/Shipping and the real
sample Editor target build; all seven actual-sample MotionWorld tests pass.

Main assumption: Episode-stop export latency is acceptable because it is outside the per-frame
control path and episodes remain bounded. The live gate must measure it rather than assume it.

How it could fail: Disk permission or capacity failure; process termination before rename; schema
drift; file collision; invalid recorder counters; a corrupt transition; or a downstream parser that
silently accepts NaN, missing fields, reset leakage, or coordinate mismatch.

How I tested it: Strict C++ compilation and automation plus 11 Python tests and Ruff pass. Live
episode 1801 exported 458 of 458 attempted transitions with zero rejection or capacity loss in
15.809 ms. The 600027-byte file contains exactly one header, 458 rows, and one complete footer; the
independent Python command accepts every row, no temporary file remains, and the preserved file
hash is `154ab619...24a35bca`.

Related config/commit/experiment: `FEAS-001`; `bbe2355`; `ae56d35`; `8dcc732`.

## D-019 - Absolute-time deterministic timed gate

Status: pure kernel, runtime actor, and opt-in arena lifecycle compile under strict universal
targets; all eight actual-sample automation tests pass; persistence and live evidence remain pending

Decision: Define the P0 gate as a collidable box with sinusoidal sideways translation evaluated
directly from immutable configuration and scenario-relative time. Keep the success plane fixed
through the schedule origin. Resolve terminal events in the order collision, forward crossing,
timeout, and reject unknown/non-finite/degenerate configurations.

Why: Absolute-time evaluation gives the planner and Unreal the same analytic future without
frame-rate integration drift. A fixed success plane makes task completion unambiguous. Explicit
event priority prevents a coarse finalized step from being labelled both collision and success.

Alternatives considered: accumulate transform deltas every Tick; animate an opaque Blueprint
timeline; move the success plane with the blocker; use random motion before seeded lifecycle is
proved; treat overlap as both success and failure.

Evidence: The pure kernel and executed automation test cover start/quarter/full-period states,
repeat queries, forward/backward crossing, collision priority, inclusive timeout, invalid period,
unknown motion type, and a motion axis inconsistent with the success plane. Strict universal Mac
Editor/Development/Shipping compilation and the real sample universal Editor build pass. A separate
actor owns the authoritative collision box and a collision-disabled visual mesh; it recomputes its
transform from absolute time and resets collision evidence explicitly.

Main assumption: A sideways sinusoidal blocker is a sufficiently small but meaningful timed-gate
task for comparing identical-budget controllers.

How it could fail: Runtime Tick time may not share the scenario reset origin; collision callbacks
may not align with finalized character steps; actor scale could disagree with logged half-extents;
or an open sample area may allow trivial detours around the blocker.

How I tested it: Strict compilation is complete. The real sample universal Editor target builds,
and all eight actual-sample MotionWorld tests pass after integration. The next gates are scenario
schema validation and two same-seed live traces with collision/success/timeout trials.

Related config/commit/experiment: `FEAS-001`; pending.
