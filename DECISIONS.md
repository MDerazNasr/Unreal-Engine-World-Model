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

Status: pure kernel, runtime actor, opt-in lifecycle, independently validated schema v2, one live
collision episode, and a two-run same-seed repeat pass; live success/timeout remain pending

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
and all eight actual-sample MotionWorld tests passed after integration. The v2 focused exporter test
passes in the real sample; 16 Python unit tests and Ruff pass. Live episode 1901 reset with zero
measured verification error, recorded 70/70 attempted transitions, classified one collision, safely
stopped, exported in 4.616 ms, and passed strict independent Python validation. Episode 1902 held
the seed/config/action fixed under a different frame-time distribution, independently validated,
repeated the collision within 3.995 ms runtime time and 0.153 cm terminal agent position. Live
success/timeout remain stronger follow-up evidence rather than established facts.

Related config/commit/experiment: `FEAS-001`; live episodes 1901/1902; `dc09bbf`; `7cbc007`.

## D-020 - Animation root is separate QA telemetry

Status: accepted; pure contract, bounded default-off runtime capture, strict parser/CSV/plotter,
exact-sample universal build/tests, and one live manual-movement trace pass

Decision: Read the skeletal root from Mover's own primary visual component using bone index zero,
and store it in `FMotionWorldAnimationDiagnosticSample`, never in `FMotionWorldStateSample` or a
training transition. Align it to the latest authoritative sequence at `OnPostFinalize` and label
the source as the current animation pose buffer. Defer toe metrics until reliable contact labels
exist.

Why: Gameplay collision follows Mover's finalized state, while Motion Matching may offset the mesh
and root for presentation. A separate type makes accidental state-source substitution visible in
code review. Mover's primary visual is a stronger source than choosing an arbitrary mesh component,
and bone index zero avoids assuming a skeleton-specific root name.

Alternatives considered: use the animation root as model state; use the mesh component transform
as if it were the root bone; find the first skeletal mesh independently of Mover; hard-code a
mannequin component or bone name; claim toe sliding without contact state.

Evidence: UE 5.8.2 source documents `GetPrimaryVisualComponent()` and world-space
`GetBoneTransform(int32)`. The pure builder requires a valid non-resimulated authoritative state,
primary skeletal source, a registered nonempty public pose buffer, explicit component/root names,
and finite transforms. The protected `AreBoneTransformsValid()` override is deliberately not used.
Runtime rows carry a unique session ID, authoritative sequence/time, explicit capture-phase and
`model_input=false` guards, while logging is default-off, interval-throttled, and capacity-bounded.

Main assumption: The current skeletal pose buffer observed during `OnPostFinalize` is useful for
QA alignment even though animation evaluation may belong to the preceding visual update.

How it could fail: The primary visual is not skeletal; pose transforms are not valid yet; pose and
Mover time are offset by an animation tick; root index zero is visually uninformative; or logging
volume causes runtime noise.

How I tested it: The automation contract covers valid aligned data, explicit world-centimetre root
offset, missing visual source, and non-finite transform rejection. Strict universal
Editor/Development/Shipping builds pass. Twenty Python tests and Ruff pass, including rejection
of sequence and offset corruption. A three-row synthetic trace passed strict parsing and generated
a visually inspected plot. The exact sample universal build and all eight actual-project tests pass.
A live default-automation-off session produced 356/356 valid rows with no capacity loss. Independent
parsing/CSV export passed: planar root offset was exactly zero; vertical offset ranged from -88.000
to -86.549 cm around movement onset. The actor traversed 1776.814 cm. The result establishes this
sample's in-place root behavior for this trace, not a universal animation-system property.

Related config/commit/experiment: `FEAS-001`; `7ab91f4`.

### D-019a - Terminal events stop control but do not erase physics

Decision: Evaluate arena events only while a verified timed-gate episode is actively recording.
At the first terminal event, freeze the gate at its measured pose while retaining blocking
collision, coalesce multiple physics callbacks before one authoritative observation into one
collision event, and replace both local- and world-frame desired-velocity requests with zero.

Why: The terminal transition belongs to the action that was already applied, so it must be recorded
before control changes. Afterward, continuing to command motion or deleting the obstacle makes a
correct collision look like a pass-through. Clearing both command frames prevents a later frame
switch from reviving a stale nonzero request.

Alternatives considered: Disable collision at termination; destroy the gate; disable automation
and fall back to unowned sample input; zero only the currently selected command frame; classify
gate events during the unrecorded warmup period.

Evidence: Live attempt 1 produced two same-step physics callbacks, one terminal classification,
then visually passed through because collision was disabled while automation remained nonzero.
The correction has a pure regression assertion that both stored command frames become exactly zero.
Strict isolated universal Editor/Development/Shipping builds, the exact sample universal Editor
build, eight actual-project MotionWorld tests, and all 16 Python tests pass. A second live attempt
remains required before acceptance.

Main assumption: A zero desired velocity submitted on the next Mover production step, together with
the still-solid frozen gate, is the least surprising safe terminal behavior.

How it could fail: The sample may decelerate rather than stop instantaneously; terminal processing
could run before the terminal observation is recorded; collision might be altered elsewhere; or a
new reset might fail to re-arm the one-shot safe stop.

How I tested it: Strict builds and automation pass as recorded in
`evidence/unreal/d019_terminal_safety_automation.log`; the live reset/record/export/terminal audit
is pending.

Related config/commit/experiment: `FEAS-001`; D-019 live attempt 1; `95573a3`.

## D-021 - Explicit typed planar coordinate contract in Python

Status: accepted for the Day 2 coordinate kernel; candidate blank-page derivation remains open

Decision: Use Unreal world `+X/+Y` and character-local forward/right `+X/+Y`, with model-facing yaw
stored in a finite `YawRadians` wrapper. Keep vector rotation separate from point
rotation-plus-translation. Support scalar and batched NumPy arrays, validate the final dimension and
finite values, and fail on a bare numeric yaw.

Why: The nominal model, residual model, and planner must interpret every action and velocity exactly
as the Unreal bridge does. Explicit angle construction exposes the degrees-to-radians boundary, and
separate point/vector functions prevent accidentally translating a velocity.

Alternatives considered: accept unlabelled float angles; use degrees throughout Python; combine
points and vectors in one helper; depend on implicit NumPy broadcasting without shape checks; copy
coordinate equations into each future module.

Evidence: The equations and 90-degree hand calculation are recorded in `THEORY.md`. The Python
cardinal results match the already executed Unreal C++ convention: local forward maps to world `+X`,
`+Y`, `-X`, and `-Y` at yaw 0, 90, 180, and -90 degrees, respectively; local right at yaw 90 maps to
world `-X`.

Main assumption: Planar yaw is sufficient for the ground-movement model; pitch, roll, and vertical
motion are outside this coordinate kernel.

How it could fail: A caller may deliberately construct `YawRadians` from a value that was actually
measured in degrees; no numeric API can infer that semantic mistake. Incorrect origins, mismatched
batch shapes, or later duplicated conversion code could also reintroduce frame errors.

How I tested it: Eighteen focused tests cover the Unreal cardinal convention, local right, a
fixed-seed batch of 512 random round trips, norm preservation, explicit point translation and
inverse conversion, vector/point separation, degree conversion, bare-angle rejection, malformed
dimensions, and non-finite vectors/yaws. Focused Ruff and `git diff --check` pass.

Related config/commit/experiment: `NOM-000`; Day 2 coordinate contract.

## D-022 - Keep the bounded-velocity module as a scalar teaching oracle

Status: accepted for equation and test validation; not accepted as the nominal baseline

Decision: Implement one-dimensional bounded acceleration with trapezoidal position integration as
a pure scalar function plus a same-shaped batch wrapper. Optionally clamp the desired target speed,
but never instantaneously clamp an observed speed produced by an external force. Return the applied
acceleration and limited target explicitly.

Why: This is the smallest transparent calculation that proves command, acceleration, timestep,
velocity, and position semantics before adding Smooth Walking's coupled planar and spring dynamics.
Scalar and batch paths share one calculation so batching cannot silently change the equation.

Alternatives considered: begin directly with the full Smooth Walking implementation; call the
componentwise scalar clip a realistic 2D acceleration rule; instantaneously clamp current velocity
to the normal speed limit; omit the position update; allow NumPy to broadcast mismatched batches.

Evidence: The code maps directly to the three equations in `THEORY.md`. The recorded hand case starts
at 200 cm/s, requests 500 cm/s, uses 800 cm/s^2 and 1/60 s, and produces 213.333 cm/s plus 3.444 cm
displacement.

Main assumption: Independent scalar examples are sufficient for teaching and detecting clamp or
timestep errors before the faithful model exists.

How it could fail: Treating this oracle as the final nominal model would create an unfairly weak
baseline. Componentwise use in 2D would give a different diagonal acceleration magnitude. A large
timestep can also be numerically valid here while being an inappropriate approximation of Unreal.

How I tested it: Thirty-four focused tests cover rest, unclamped and clamped acceleration, the hand
calculation, stopping without overshoot, reversal, target speed limiting, above-limit external
velocity, zero acceleration, scalar/batch parity, 1,024 fixed-seed invariant cases, and fail-closed
validation of timestep, parameters, shapes, and every state/action input.

Related config/commit/experiment: `ORACLE-001`; Day 2 bounded-velocity teaching oracle.

## D-023 - Use a transparent deterministic toy backend for pipeline proof only

Status: accepted as synthetic infrastructure; excluded from Unreal evidence

Decision: Define immutable observable position/velocity/time/step state and a separately named
hidden lagged-target state. Derive reset phase and lateral offset from a local seeded generator,
enforce a vector-norm action bound, evaluate the gate from absolute time, apply an optional
step-indexed push, use swept collision, and log complete identity/action/state/event transitions.

Why: We need a cheap controlled system in which the source of prediction mismatch is known. It can
prove determinism, episode plumbing, event priority, and plotting before real data is available,
while making the hidden-state assumption inspectable instead of mysterious.

Alternatives considered: label toy trajectories as Unreal evidence; hide the lag implementation;
use global randomness; update the gate incrementally; check collision only at the endpoint; omit
episode and sequence identity; wait for every real-data dependency before testing the pipeline.

Evidence: Fifteen focused tests cover same/different-seed reset, the analytic quarter-period gate,
visible hidden lag, exact full-episode replay, action rejection, one-shot push, collision priority,
swept anti-tunnelling behavior, terminal protection, and invalid configuration. The generated
2160x900 plot is visibly stamped `SYNTHETIC / NOT UNREAL EVIDENCE` and separates a lag-free direct
predictor from the synthetic hidden-lag trajectory and speed response.

Main assumption: A first-order hidden target lag is sufficient to exercise the history/residual
pipeline mechanics; it is not assumed to match Mover.

How it could fail: The team could overinterpret an intentionally easy synthetic mismatch, tune the
real method to toy behavior, or confuse the direct lag-free comparison with the forthcoming faithful
nominal model. The moving gate is evaluated at the end-step analytic pose during swept collision,
which is deterministic but not continuous relative-motion collision detection.

How I tested it: Same seed/config/actions produce exactly equal immutable episodes with consecutive
sequence IDs and a synthetic label. Reviewer replaced endpoint collision with a swept segment test.
The plot was generated headlessly and visually inspected; PNG SHA-256 begins `a368b767`.

Related config/commit/experiment: `SYN-001`; Day 2 deterministic synthetic backend.

## D-024 - Port installed Smooth Walking equations before choosing approximations

Status: source map accepted; live sample parameters and hidden-state capture still open

Decision: Base the nominal predictor on installed UE 5.8.2 `SmoothWalkingMode`, `SmoothWalkingState`,
`SimpleWalkingMode`, `WalkingMode`, and `SpringMath` source. Carry all five known spring-state fields,
use Unreal's rational inverse-exponential approximation, and use proposed-velocity explicit Euler
position integration. Do not freeze C++ defaults until the live Blueprint-derived mode is inspected.

Why: Replacing spring state, smoothing kernels, update order, or integration with convenient textbook
versions would make the nominal baseline unfairly weak and give the residual credit for known code.

Alternatives considered: extend the scalar teaching oracle; use exact `exp`; use trapezoidal
position integration; omit private-header state without disclosure; assume class defaults equal the
sample's runtime values; model collision inside the free-space controller without evidence.

Evidence: Version-matched source establishes input preparation, persistent state, external-influence
synchronization, acceleration/deceleration branches, directional and turning response, spring/deadzone
updates, quaternion facing, proposed-velocity integration, and subsequent collision handling. The
mapping is preserved in `research/ue58_smooth_walking_map.md`.

Main assumption: The installed source matches the 5.8.2 sample binary and the active sample mode
derives from this Smooth Walking path; runtime class/parameter capture must verify the latter.

How it could fail: The Blueprint can override `GenerateWalkMove` or modify parameters dynamically;
the private state type may be inaccessible safely; planar angle springs may differ from yaw-only
quaternion behavior; float/approximation details may create drift; collision mismatch may dominate.

How I tested it: Read the complete installed update path and exact spring kernels. Cross-checked that
`FSmoothWalkingState` is copied through sync state, `FMoverDataCollection` exposes public iteration,
and Walking Mode integrates `ProposedMove.LinearVelocity*dt`. No Python parity claim is made yet.

Related config/commit/experiment: UE 5.8.2 source audit; nominal mapping milestone.

## D-025 - Inspect runtime Smooth Walking state through bounded public reflection

Status: implementation and closed-editor verification accepted; live PIE capture open

Decision: Add a default-off diagnostic at Mover `OnPostFinalize`. Read the active
`USmoothWalkingMode` object through public UObject property metadata, and inspect the finalized
`FMoverDataCollection` through its public iterator for a `SmoothWalkingState` entry. Reflect exactly
the five source-mapped state fields by name and type. Keep this packet separate from authoritative
state, transitions, episodes, and model input; fail closed and bound all logging.

Why: The fair nominal model needs the sample's actual parameter overrides and a declared policy for
known controller state. Epic's `SmoothWalkingState.h` is private, so including it would create an
invalid project dependency. Public reflection gives us a narrow UE-5.8 diagnostic without weakening
module boundaries or pretending inaccessible state does not exist.

Alternatives considered: include the private engine header; copy the private struct layout; assume
C++ defaults; omit all spring state; estimate hidden state before checking whether bounded telemetry
is possible; add the diagnostic fields to training transitions.

Evidence: The reflected parameter list is limited to the 14 source-mapped floats plus the double-
spring flag. The state list is limited to spring velocity, spring acceleration, intermediate
velocity, intermediate facing, and intermediate angular velocity. The isolated strict plugin built
for universal Mac Editor Development, Game Development, and Game Shipping. The exact Game Animation
Sample universal Editor target built, and all nine actual-project tests passed, including the new
Smooth Walking reflection/validation test.

Main assumption: UE 5.8 runtime reflection preserves the audited class and property names, and the
active sample sync collection contains the expected `SmoothWalkingState` entry while Walking is
active. A live trace must verify both assumptions before values are frozen into Python.

How it could fail: The Blueprint may replace or dynamically alter the mode; a future engine version
may rename a property; the sync entry may be absent during another movement mode; a reflected type
may change; capturing internal state could be confused with making it a deployable model input.

How I tested it: Actual-project automation reads UE 5.8 `USmoothWalkingMode` defaults through
reflection, checks the 14-value contract, and tests complete, missing, out-of-range, NaN, and
infinite inputs. The builder independently rejects invalid parameters and hidden state. Runtime
logging is opt-in, interval-throttled, capped at 10,000 rows, and labelled `model_input=false`.

Related config/commit/experiment: `NOM-DIAG-001`; `MotionWorld.Diagnostics.SmoothWalking`.

## D-026 - Condition nominal dynamics on live parameters and carry all known state

Status: accepted; episode/protocol schema implementation pending

Decision: Define nominal state `z` as the five audited Smooth Walking fields: three world-space
vectors for spring velocity, spring acceleration, and intermediate velocity; one world quaternion
for intermediate facing; and one world-space rad/s vector for intermediate angular velocity. Pass a
time-indexed parameter snapshot to the nominal transition. If the UE 5.8 reflection contract is
missing, wrong-mode, or invalid, mark nominal context invalid rather than inventing zero state.

Why: Live session `FF6768704542` proves both that the fields are safely available and that the sample
changes acceleration, deceleration, and facing smoothing during one trace. A single constant setting
or zeroed spring state would knowingly weaken the baseline and transfer known controller behavior to
the residual network.

Alternatives considered: freeze C++ defaults; freeze the first live parameter row; zero all state at
every observation; infer state only from history; use recorded future parameters in deployable MPC;
silently drop rows whose context reflection fails.

Evidence: All 1,422 finalized state reads were valid and all 128 bounded logged rows used
`BP_MovementMode_Walking_C`. Acceleration was 500/800 cm/s^2, deceleration 300/1000 plus a one-row
startup 20000 value, and facing smoothing 0.2/0.4 s. Spring velocity reached 375 cm/s, spring
acceleration norm 1017.25 cm/s^2, and intermediate angular velocity 2.7703 rad/s. Quaternion unit-
norm error was at most `2.64e-10`.

Main assumption: A causal parameter selector or runtime controller metadata can supply the parameter
schedule used for imagined futures. Until that selector is mapped, future recorded parameter rows
are privileged evaluation context and cannot be used by the deployable planner.

How it could fail: Blueprint regime logic may depend on gait/controller variables absent from the
planning packet; reflection names may change with Unreal versions; world-frame internal vectors may
be transformed inconsistently during batched local-frame planning; a missing-context filter could
bias evaluation toward easy Walking frames.

How I tested it: Verified one session identity, exact step-10 logged chronology, fixed Walking mode/
class, finite values, three observed parameter regimes, nonzero internal response, quaternion norm,
zero invalid count, bounded-cap behavior, automation disabled, and `model_input=false`. Raw bounded
evidence is preserved with SHA-256 `2bbeab64...02517cf`.

Related config/commit/experiment: `NOM-DIAG-001`; session `FF6768704542`.

## D-027 - Version nominal context separately and require endpoint alignment

Status: accepted through live schema-v3 interface validation; varied collection still required

Decision: Keep authoritative state protocol 1 unchanged. Add nominal-context protocol 1 containing
the active Smooth Walking class/name, all 15 runtime parameter values, and the five audited internal
state fields. Upgrade causal transitions to protocol 2 and episode files to schema 3. Each row stores
previous and next context plus a completed-step parameter snapshot copied from the next finalized
context. Reject missing, invalid, unsupported, or state-sequence/mode-misaligned context. Continue to
read legacy schema-1 and schema-2 files, but never synthesize context for them.

Why: Position and velocity alone do not determine Smooth Walking's next response because its spring
memory persists between steps, and the live Blueprint changes parameters over time. Separating the
context protocol avoids redefining gameplay state while still giving the faithful nominal model the
known variables it needs. Explicit endpoint alignment prevents a plausible but scientifically fatal
off-by-one join.

Alternatives considered: enlarge authoritative state protocol 1; freeze one parameter regime; infer
all controller memory from short history; attach context only to the next state; silently fill missing
context with zeros; break old episode loading; treat the next observed parameter snapshot as guaranteed
future planner information.

Evidence: Strict isolated universal Mac Editor Development, Game Development, and Game Shipping
builds passed. The actual universal Game Animation Sample Editor target passed. All ten filtered
MotionWorld tests passed in the actual sample after one test fixture was corrected to move its context
sequence together with its deliberately skipped state sequence. The pinned Python 3.12 environment
passed 92 tests; focused schema tests cover v1/v2 compatibility, valid v3, wrong sequence, mismatched
completed-step parameters, broken hidden endpoint continuity, and invalid quaternion state.

Main assumption: Parameters read at the next `OnPostFinalize` boundary governed the step that just
completed. This is recorded as an assumption in every v3 header. The data does not establish which
future regime is causally knowable to MPC.

How it could fail: Blueprint logic could mutate a parameter after move generation but before capture;
non-Walking modes do not satisfy this contract; reflected names may change; filtering invalid contexts
could bias the dataset; an online planner could accidentally consume recorded future regimes.

How I tested it: Fail-closed C++ tests attack protocol, range, finite-state, quaternion, sequence,
mode, seed, continuity, and atomic-export paths. Python independently rechecks exact keys, provenance,
ranges, quaternion norm, endpoint alignment, parameter duplication, and cross-row hidden continuity.
The first full actual-sample run exposed a mixed-purpose test fixture; the corrected run completed all
ten MotionWorld tests with `Success`.

Related config/commit/experiment: `NOM-CONTEXT-001`; commits `fbe8b38`, `5be47f0`.

Live acceptance addendum: one 119-transition schema-v3 episode passed the independent loader and
full-context audit with zero rejected rows. Its episode ID reused `1902` instead of the intended
unique `2701`, so it is interface evidence only and must not enter a split manifest under a duplicated
episode identity. See `evidence/unreal/nom_schema_v3_live_episode_1902.log`.

## D-028 - Keep known input preparation outside the learned residual

Status: equation, runtime input capture, and retrospective one-step evidence accepted; varied
turning/contact collection remains open

Decision: Treat `SimpleWalkingMode` velocity preparation as part of the nominal baseline. Clamp the
recorded velocity-input packet by an explicit effective max speed before calling the tested Smooth
Walking transition. Never infer that limit silently inside the model or let the residual receive
credit for correcting a known clamp. Keep desired facing explicit until automation makes it a
deterministic recorded input.

Why: `FCharacterDefaultInputs` records the 200 cm/s request, while `SimpleWalkingMode` can clamp it
before `GenerateWalkMove`. An initial all-row evaluation matched transitions 0-9 nearly exactly but
began systematic divergence at transition 10, exactly when the engine's intermediate velocity
reached 165 cm/s. This was a missing known transformation, not evidence for learning.

Alternatives considered: train the residual on the clamp error; cap actions at an inferred plateau
without declaring it; weaken the nominal acceleration; record only the post-clamp target; ignore
facing because the accepted run is straight.

Evidence: With an explicitly supplied 165 cm/s limit, all 118 non-collision rows in the accepted
schema-v3 episode have maximum one-step planar position error `4.68e-7 cm` and maximum planar
velocity error `3.12e-6 cm/s`. The one recorded collision row has `0.421 cm` position error and
`15.033 cm/s` velocity error, while the internal spring state still matches, correctly separating
controller proposal from environmental execution. A dedicated norm-clamp module has rest, below-
limit, vector-direction, zero-limit, shape, finite, and invalid-limit tests.

Main assumption: The explicit 165 cm/s evaluation value is the effective shared setting for this
run. Its behavior is strongly identified by the transition boundary, but schema v3 does not record
the setting and therefore does not make it planner-available.

How it could fail: Max speed may change with gait or shared settings; `MaxSpeedOverride` can replace
the shared value; an orientation intent preserved from another input producer can affect facing;
contact/ramp behavior remains outside the free-space transition; retrospective completed-step
parameters may not be knowable for a future rollout.

How I tested it: Ran the strict schema loader, evaluated all 119 rows from real previous state and
hidden context, preserved an invalid first evaluation as a reviewer finding, required the max speed
as a command-line argument, reran 174 Python tests, and generated CSV/JSON/PNG artifacts. Episode
1902 remains quarantined from training because its ID was reused.

Related config/commit/experiment: `NOM-001`; `artifacts/nominal/episode_1902/`.

Live correction addendum: unique schema-v4 episode 4001 proves the 165 cm/s value came from the
Blueprint mode's `MaxSpeedOverride`, not shared legacy settings. The v3 behavior identified the value
but could not identify its source. Re-evaluation using only recorded v4 fields reproduces all 104
non-collision rows to maximum `6.93e-6 cm/s` velocity error; no manual 165/facing arguments are used.

## D-029 - Version every causal Simple Walking input in episode schema 4

Status: accepted through unique live schema-v4 capture and independent evaluation

Decision: Upgrade Smooth Walking diagnostics and nominal context to protocol 2, transitions to
protocol 3, and episode files to schema 4. Record whether Simple Walking has an effective max speed,
its numeric value and source, the echoed world-space orientation intent, the derived desired-facing
yaw, and whether zero planar intent used the previous-facing fallback. During MotionWorld automation,
hold the last finalized facing so the velocity-only policy does not inherit unrecorded camera or
controller state. Continue reading schemas 1-3 without synthesizing their missing causal fields.

Why: Simple Walking transforms desired velocity and orientation before Smooth Walking. If either
transformation is absent from a row, two apparently equal model inputs can have different next states,
and the residual would receive credit for correcting a known interface omission. A versioned contract
lets new data be complete without relabelling old evidence.

Alternatives considered: learn the 165 cm/s clamp as a residual; infer max speed from observed
plateaus; preserve upstream orientation without recording it; face the velocity direction implicitly;
break old episode loading; overwrite schema-v3 meaning.

Evidence: The actual universal `GameAnimationSampleEditor` target compiled for arm64 and x86_64 in
213.19 seconds. All 11 MotionWorld tests passed inside the actual sample. The independent Python
loader passed valid schema-v4 rows and rejected mismatched completed-step preprocessing and facing
targets while retaining schema-v1/v2/v3 tests. The full Python suite passed 180 tests and Ruff passed
on all source.

Main assumption: The next finalized movement-mode/shared-settings snapshot governed the completed
step, just as documented for runtime parameters. The Game Animation Sample uses world Z as up; the
recorded orientation derivation mirrors that scenario's planar Simple Walking preparation.

How it could fail: Max speed or movement mode could change between move generation and post-finalize
capture; arbitrary-gravity scenarios would require recording the up vector; fixed-facing automation
does not explore turning; human-controlled data may contain a controller-produced facing policy that
the eventual planner cannot reproduce.

How I tested it: C++ builders fail closed on missing/non-finite orientation and invalid/unavailable
speed preparation, re-derive the facing target, and revalidate every transition before atomic export.
Python independently checks exact keys, enum/value consistency, zero-intent fallback, facing angle,
completed-step duplication, endpoint continuity, and legacy compatibility. Live capture is explicitly
not yet credited.

Related config/commit/experiment: `NOM-CONTRACT-002`; schema 4 closed-editor gate.

Live acceptance addendum: episode 4001 reset with zero measured error, recorded 105/105 attempted
transitions with no rejection or loss, and exported a complete 107-line schema-v4 file. Every row uses
transition protocol 3 and context protocol 2, records max speed 165 from `mode_override`, orientation
intent `[1,0,0]`, desired facing 0 degrees, and no zero-intent fallback. The strict Python loader
accepts the file. This proves the straight fixed-facing path only; it does not provide turn coverage.

## D-030 - Absolute-time varied-action coverage with derived facing

Status: closed-editor implementation accepted; live episode and coverage audit pending

Decision: Add a default-off, deterministic world-frame coverage schedule with forward, stop,
reverse, stop, right, left, diagonal, and final-stop phases. Evaluate it from absolute episode
simulation time using half-open intervals. During nonzero motion, set orientation intent to the
requested velocity direction; during stops, hold the preceding scheduled direction. Keep the timed
gate and coverage schedule mutually exclusive. Automatically issue zero and atomically stop/export
after 5.3 seconds. The eventual planner action remains two-dimensional desired velocity: facing is
a declared deterministic preprocessing policy, not an extra learned action dimension.

Why: Episode 4001 proves only straight fixed-facing behavior. Learning and recursive validation need
acceleration, braking, reversal, lateral motion, turning, and zero-input memory. Absolute time avoids
frame-count drift, while a derived-facing policy makes every causal input reproducible from the
schedule instead of inheriting camera state.

Alternatives considered: manual keyboard collection; random actions before deterministic coverage;
fixed facing during all direction changes; a separate yaw action; frame-count phase boundaries;
combining collection with the moving gate; continuing to record after the schedule ends.

Evidence: The actual universal Game Animation Sample Editor build passed for arm64 and x86_64. The
headless sample discovered 12 MotionWorld tests and all 12 passed. The new pure test covers every
half-open boundary, exact velocity/facing outputs, completion, unit facing, invalid timing/speeds,
negative time, and non-finite time.

Main assumption: World-frame scripted coverage can exercise the relevant turn dynamics while the
saved row's independently derived character-local action remains the learning/planning
representation. Stops retain useful orientation memory by design.

How it could fail: Animation/controller logic may react differently to abrupt facing changes; world
directions may encounter level geometry unevenly; a phase boundary could disagree with automatic
completion; a reset could start before a valid seed; the schedule could silently overlap a timed
gate; one short episode cannot establish broad dataset coverage.

How I tested it: Reviewer inspection found two issues before live use: an accidental integration
edit in reset code was removed, and repeated floating-point boundary accumulation disagreed with the
closed-form 4.8-second boundary. Production now derives every boundary from the same formula as total
duration. The component rejects conflicting scenarios, invalid configs, and missing finalized seed
state. Universal compilation and the complete 12-test headless suite pass.

Related config/commit/experiment: `VAR-DATA-001`; default schedule; live episode 4101 pending.

Live acceptance addendum: episode 4101 reset with zero measured error, executed all eight phases in
order, stopped at 5.302 seconds, recorded 191/191 transitions with no rejection/loss, and passed the
strict schema-v4 loader. It contains 48 zero-action rows, 59 braking rows, two executed velocity-sign
reversals, and 141 rows with more than 0.1 degrees of realized yaw change. The 191 rows span six
distinct world-action vectors, both positive and negative local lateral components, and 18–84 ms
timesteps. No collision occurred. This accepts the deterministic live coverage gate, not global
dataset sufficiency.

The first exact reverse row also refines the nominal claim. The recorded intent maps to -180 degrees,
but Unreal's next reflected intermediate-facing quaternion is -179 degrees for one row before using
the equivalent 180-degree representation. The scalar-yaw nominal takes the opposite equal-length arc,
creating one 16.266-degree yaw error and 677.733 deg/s yaw-rate error while translation remains at
micro-numerical parity. Treat this as a known 180-degree representation/preprocessing edge requiring
source-faithful resolution, not automatically as a learnable residual.

## D-031 - Recursive evaluation without intermediate observation re-seeding

Status: accepted for the nominal episode-4101 diagnostic; held-out residual comparison pending

Decision: For each start transition, initialize observable and known internal state once from the
real episode, then recursively feed every nominal prediction into the next step under the recorded
future action sequence. Evaluate 0.5, 1.0, and 1.5 seconds at the first real transition boundary at
or after each requested duration and report the actual duration. Never replace an intermediate
predicted state with an Unreal observation. Permit completed-step parameter snapshots only for this
explicitly retrospective diagnostic; do not claim they are available to online MPC.

Why: One-step evaluation can hide compounding because it gives the model the correct state again at
every row. Planning cannot do that. Variable Unreal timesteps also mean an exact requested duration
usually falls between finalized boundaries, so the endpoint rule must be explicit.

Alternatives considered: teacher-force every step; use a fixed number of rows as though timestep were
constant; interpolate the authoritative endpoint; use recorded hidden state at every step; silently
give MPC future Blueprint parameters; report only a mean across horizons.

Evidence: Ten focused tests include stationary zero-error rollouts, invalid horizons, and a trap
where an intermediate real state is deliberately corrupted while the start-to-end recursive result
must remain unchanged. All 189 Python tests pass. Episode 4101 yields 173/154/136 valid windows at
0.5/1.0/1.5 seconds. Translational errors remain below `8.35e-6 cm` position and `1.65e-5 cm/s`
velocity. Median angular errors are near numerical noise, but windows crossing transition 46 produce
all errors above one degree and raise p95 yaw to 82.917/94.194/39.768 degrees.

Main assumption: The recorded future action sequence is a legitimate open-loop intervention for
offline evaluation, and the retrospectively observed parameter snapshot governed its labeled step.

How it could fail: A future parameter regime may be unavailable to a planner; endpoint overshoot can
reach one long frame; one episode is not held-out evidence; exact-opposite quaternion representation
can dominate tail statistics; contacts and pushes require their own strata and state synchronization.

How I tested it: The evaluator reports requested and actual horizons, step/action-change/collision
counts, all four error types, median/p95/max, and explicit leakage semantics. Every rollout above one
degree crosses the already-identified transition 46; all non-crossing windows stay below
`2.21e-5 deg` yaw error, localizing rather than averaging away the failure.

Related config/commit/experiment: `NOM-ROLL-001`; episode 4101; horizons 0.5/1.0/1.5 seconds.

## D-032 - Make the exact-antipodal facing tie explicit

Status: accepted through unique live episode 4201

Decision: Preserve the exact reverse velocity request, but offset its orientation intent clockwise
from world -X by a configurable 0.5 degrees. Reject tie-break values below 0.25 degrees or above
5 degrees. This policy applies to the deterministic coverage schedule; the eventual online action
preprocessor must use the same declared rule whenever its desired world facing is exactly antipodal
to Unreal's forward basis.

Why: `FQuat::FindBetween(+X, -X)` sits on a mathematical tie: clockwise and counter-clockwise are
equally short. Episode 4101 records a scalar -180-degree intent but a one-frame -179-degree internal
target, after which the target becomes the equivalent +180-degree quaternion. That unobserved
one-frame choice dominates recursive yaw tails. A small explicit offset makes the turn direction
causal, unique, and reproducible without allowing a residual network to learn a known interface edge.

Alternatives considered: drop the failing windows; train the residual on them; use the next hidden
state as the current target; add yaw as a third planner action; change the requested reverse velocity;
assume one of the two 180-degree arcs without live evidence.

Evidence: Source inspection confirms UE 5.8 `SimpleWalkingMode` constructs facing with
`FQuat::FindBetween(FVector::ForwardVector, DesiredFacingDir)` and its exact-opposite helper has a
special branch. The unit cases require reverse velocity to remain exactly `(-150,0,0)`,
facing to remain unit length, yaw to equal -179.5 degrees, and the clockwise side of the tie to be
selected. The actual universal Game Animation Sample build succeeded in 158.65 seconds, and all 12
MotionWorld automation tests passed. Live replacement evidence is still pending.

Main assumption: A 0.5-degree facing-only deviation is negligible to the intended reverse-motion
task while safely exceeding the engine helper's opposite-vector threshold.

How it could fail: The Blueprint or runtime input pipeline could still transform the target; a
planner could use a different preprocessing path; the offset could create a measurable animation
artifact; a replacement episode might expose a different discontinuity.

How I tested it: The actual universal sample compiled for arm64 and x86_64, source parity was exact,
and the complete 12-test suite passed. Next collect a new unique varied episode. Require the first
reverse row to record -179.5 degrees and the one-step/recursive angular spike to disappear before
accepting the live policy.

Related config/commit/experiment: `FACING-001`; unique live episode 4201 accepted.

Live acceptance addendum: the first post-build run correctly used -179.5 degrees but repeated
episode ID 4101 because warmup-reset runs use `BeginPlayResetEpisodeId`, not
`BeginPlayEpisodeId`; it is excluded from manifests. Unique episode 4201 then reset exactly,
recorded 193/193 rows with no loss, passed strict schema-v4 validation, and reproduced the policy.
One-step yaw error max is 0.024337 degrees. Recursive yaw maxima at 0.5/1.0/1.5 seconds are
0.042917/0.042917/0.029078 degrees, versus 174.296/174.296/89.390 before the policy. A one-frame
internal -179.0 versus recorded -179.5 target remains below the 0.1-degree facing deadzone and is
preserved as known preprocessing residue, not a learned residual target.
