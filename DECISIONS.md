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

## D-033 - Treat a controlled push as a labeled velocity intervention

Status: accepted in live schema-v5 episode 4301; recovery produced a bounded negative residual result

Decision: Implement the controlled external perturbation with Mover's public one-tick additive
velocity effect. Describe and store the intervention as a world-space velocity delta in cm/s, not as
a force or mass-based impulse. Use an absolute-time, one-shot schedule with pre- and post-event
observation intervals. If a long frame passes the trigger before the event is queued, keep the event
due rather than silently completing the schedule.

Why: `FApplyVelocityEffect` adds a requested velocity to Mover's current synchronized velocity for
one tick. Calling that value a physical impulse would invent mass semantics that the API does not
provide. The event-causing transition is not predictable when the model is intentionally denied the
future event; its purpose is to create a measured recovery trajectory and test whether observable
post-event history contains persistent, predictable error.

Alternatives considered: apply actor transform directly; call the value a force; inject the future
event into residual-model inputs; rely on a frame counter; discard the event transition; train on
terminal gate collisions without obstacle context.

Evidence: UE 5.8 `FApplyVelocityEffect` source explicitly supports additive velocity, applies it for
one tick, and takes cm/s. The pure schedule validates finite planar nonzero deltas bounded to
1000 cm/s, exact trigger/completion boundaries, one-shot behavior, and a late-frame case that cannot
skip an unqueued event. The actual universal Game Animation Sample target compiled in 49.28 seconds;
the focused headless automation test passed. A final 14.98-second rebuild added the excessive-kick
regression. Final raw log SHA-256 begins `a6296104`; deployed dylib SHA-256 begins `d21aff94`.

Main assumption: A bounded one-tick velocity kick is a useful reproducible proxy for an external
gameplay disturbance, even though it is not a rigid-body force simulation.

How it could fail: Mover may modify the requested delta during the affected step; forcing or
preserving the movement mode may change semantics; a callback gap or resimulation could misalign the
label; recovery may be exactly explained by the faithful nominal model and yield a negative result.

How I tested it: Boundary tests cover before, at, and after the trigger; a nine-second late sample
still requests an unqueued event; queued events are never requested twice; invalid timing, vertical,
zero, oversized, and non-finite configurations fail closed. Runtime application and exact label
alignment remain uncredited until the next protocol slice passes.

Related config/commit/experiment: `PERT-SCHEDULE-001`; runtime application pending.

Schema-v5 addendum: transition protocol 4 now stores a separate evaluation-only event packet with
the requested velocity delta and the exact finalized state sequence/Mover frame after which it was
queued. `none` rows require exact empty placeholders. Additive-velocity rows fail closed on invalid
numerics, nonplanarity, zero/excessive magnitude, or source-endpoint mismatch. The header explicitly
states that the label is not a model input and stores the schedule separately. Export revalidation
requires exactly one event, matching schedule/vector/timing, adequate post-event duration, and no
timed-gate coexistence. Schemas 1-4 remain readable without fabricated event fields.

The actual universal sample build succeeded in 126.84 seconds. All 13 MotionWorld automation tests
and all 196 Python tests passed. The independent Python tests reject wrong source identity, missing
or duplicated schedule events, mismatched velocity, and a contract that falsely declares the event
as a model input. Runtime queuing and a live schema-v5 episode remain uncredited.

Runtime addendum: the bridge exposes a default-off perturbation schedule mutually exclusive with the
timed gate and varied-action schedule. After a recorded finalized state reaches the trigger, it builds
the label from that exact state sequence/Mover frame, queues an additive `FApplyVelocityEffect`, and
requires the immediately following causal row to accept the pending label. Any rejection stops the
episode and the exporter refuses to publish an incomplete scheduled file. Completion requires both
the configured total duration and proof that the event row was recorded. The exact sample rebuilt in
19.99 seconds and all 13 MotionWorld tests passed. Live effect/application evidence was still
required at that gate and is supplied by the addendum below.

Live addendum: episode 4301 reset exactly, recorded 133/133 transitions without loss, attached one
event to transition 53 after state 83/Mover frame 84, completed its two-second post-event interval,
and passed the strict schema-v5 loader. The requested +250 cm/s world-Y delta became a +233.480 cm/s
observed transition change along Y after the same step's normal Mover dynamics. Lateral speed fell
below 1 cm/s after 0.416 s and settled at 24.433 cm displacement. The faithful nominal model is
numerically exact before and after the event when re-seeded from observed state/context; only windows
that cross the hidden intervention fail. Therefore the event row remains evaluation-only and is
excluded from any claim of predictable residual structure. Related experiment: `NOM-002`.

## D-034 - Separate the retrospective oracle from the deployable causal nominal

Status: accepted for residual-target discovery; dataset collection remains required

Decision: Retain completed-step parameter replay as a labelled equation-fidelity oracle. Define the
deployable baseline from only the current finalized state, current aligned Smooth Walking internal
context/parameters/input preparation, and candidate actions. For an open-loop imagined future, carry
the predicted state/internal memory forward and hold the rollout-start parameters until a separately
tested causal parameter selector exists.

Why: Parameters captured after a completed step reproduce Unreal almost exactly, but they are future
information at planning time. Episode 4201 proves that refusing them exposes a structured gap at
Game Animation Sample parameter-regime changes: every material one-step error is on a changed-
parameter row, and held-parameter recursive p95 position error reaches 22.971 cm at 0.5 seconds.
This is the first causal, decision-scale target that remains after implementing the faithful public
Smooth Walking equations.

Alternatives considered: use every recorded future parameter snapshot in MPC; freeze C++ defaults;
remove current internal state to make history look better; train on the hidden kick; reverse-engineer
the complete sample Blueprint scheduler before learning; predict future parameters explicitly.

Evidence: `02ae8bb`, `fc32430`, and `93fb741`; 202 Python tests pass. A regression mutates all future
parameter and input-preparation snapshots and proves that a rollout started earlier is unchanged.
Accepted episodes 4101 and 4201 show the same exact alignment between material causal error and
parameter-change rows. Reviewed plots and summaries are under `artifacts/nominal/*_current_snapshot/`.

Main assumption: Current state/action/history contain enough signal to predict the state-level effect
of the sample-specific parameter scheduler over 0.5-1.5 seconds.

How it could fail: The scheduler may depend on Blueprint/animation variables absent from the model;
two near-duplicate episodes may make the pattern look easier than it is; holding parameters may be a
weaker baseline than an implementable analytic selector; autoregressive rollouts may compound errors
outside the training distribution.

How I tested it: Compared current-snapshot and completed-step one-step replay; checked error/change-
row alignment; ran 0.5/1.0/1.5-second held-parameter rollouts; mutated later snapshots in a unit test;
kept the external kick evaluation-only. Future tests require episode-level splits and no-history/
history/explicit-selector comparisons.

Related config/commit/experiment: `NOM-CAUSAL-001`; `02ae8bb`, `fc32430`, `93fb741`.

## D-035 - Use a causal six-component planar residual in the previous-facing frame

Status: accepted for the P0 residual contract; training-only scales remain pending

Decision: Predict local planar position and velocity corrections, a wrapped scalar yaw correction,
and a yaw-rate correction. Express planar corrections in the previous observed facing frame. Keep
position in centimeters, velocity in centimeters/second, and learned angular values in radians and
radians/second. Reject vertical or time mismatch. Define exact-zero composition as the nominal-state
identity.

Why: A local frame gives forward/sideways errors a consistent interpretation across world headings.
The previous facing is known when the prediction is made; using actual next facing would leak the
answer. A scalar shortest-angle correction avoids discontinuity at plus/minus 180 degrees. The exact
zero identity guarantees that disabling the learned model reproduces the nominal baseline exactly.

Alternatives considered: world-frame planar deltas; target-frame or actual-next-facing deltas; sine
and cosine facing output; predicting the complete next state; including vertical movement; silently
ignoring vertical/time disagreement.

Evidence: Eleven focused tests cover exact zero identity, difference/composition inversion, a
90-degree coordinate example, shortest-angle wrapping, frozen output ordering, and fail-closed
validation. The full suite has 213 passing tests.

Main assumption: P0 scenarios remain on a planar floor and six corrections are sufficient for the
decision-relevant character state.

How it could fail: slopes, jumping, root-motion vertical effects, or contact modes may require a 3D
state; previous-facing coordinates may be unstable if facing itself is unreliable; a scalar yaw
correction can still be difficult near genuinely ambiguous 180-degree behavior.

How I tested it: Hand-checked that at 90-degree facing a world `+Y` error is local `+X`; composed
computed differences back to the actual state; tested `+179` to `-179` as a `+2 degree` correction;
and rejected vertical position, vertical velocity, time, and non-finite discrepancies.

Related config/experiment: `RES-CONTRACT-001`.

## D-036 - Freeze causal invariant residual inputs before constructing windows

Status: accepted for feature schema version 1; recursive advancement remains pending

Decision: Encode each query as 28 values: current local velocity/yaw rate, candidate local velocity
and facing delta, the causal nominal model's local predicted change, timestep, and the 15 current
Smooth Walking parameters. Omit absolute position/heading and all goal, obstacle, episode-time,
future-snapshot, contact, and event fields. Define history as exactly four consecutive step-query
vectors in oldest-to-current order.

Why: Local features make the learned execution correction invariant to where the character is placed
or which compass direction it faces. Scenario and timeline fields create shortcuts rather than a
character dynamics model. A fixed schema catches silent reordering between training and runtime.

Alternatives considered: pass every JSON field; include world position and yaw; include gate phase;
include completed-step/future parameter snapshots; give history only raw states; use variable-length
history or a recurrent model immediately.

Evidence: Eleven focused tests freeze unique names/counts, verify previous-facing conversion with a
90-degree example, prove translation and rotation invariance, reject temporal misalignment and wrong
history widths, and preserve chronological order.

Main assumption: The nominal predicted change is a sufficient summary of available internal Smooth
Walking state for this small residual; four queries cover the short scheduler/controller context.

How it could fail: Relevant animation/contact mode is omitted; four frames are too short; parameters
do not expose the scheduler signal; the nominal summary discards useful internal state. These are
ablation questions, not reasons to leak targets or future snapshots.

How I tested it: Rotated an equivalent world-X motion to world-Y and translated the actor by a large
offset; feature vectors remained equal. Tested schema size, order, read-only storage, timing alignment,
history length, and oldest-to-current flattening.

Related implementation: `motionworld/models/residual_features.py`.

## D-037 - Start with matched small zero-output MLPs

Status: accepted for implementation; training comparison pending

Decision: Use 256/256/128 SiLU hidden layers for both no-history and four-history models. Change only
the schema-determined input width. Initialize the six-output layer to zero. Do not add LayerNorm or
output clipping without training evidence and training-only statistics.

Why: The input is low-dimensional and fixed-length, so a feed-forward model is the simplest adequate
hypothesis. Exact zero output makes the initial learned system identical to nominal. Keeping the body
matched makes the history comparison understandable while remaining far under the runtime budget.

Alternatives considered: GRU; Transformer; separate hand-tuned widths; random output initialization;
LayerNorm by default; clipping from validation/test extrema.

Evidence: The no-history model has 106,886 parameters and the history model 128,390, both below
500,000. Fourteen tests cover exact zero output, batch/horizon-prefix shape, CPU device, float64,
gradients, bad shapes/configuration, fixed initialization, and a reproducible optimizer step.

Main assumption: Four explicit queries contain enough short memory that recurrence is unnecessary.

How it could fail: Longer hidden state may require recurrence; the modest parameter-count difference
could partly explain a history gain; zero output initialization temporarily blocks gradients to early
layers on the first backward pass; unnormalized inputs may destabilize training.

How I tested it: Checked exact parameter counts and zero tensors, performed a gradient/optimizer
step, repeated a complete step under the same seed, and exercised prefix batches and float64.

Related experiment: `RES-MODEL-SMOKE-001`.

## D-038 - Freeze episode-level collection assignments before residual training

Status: accepted; train and validation collection complete, two final test episodes untouched

Decision: Preassign five distinct schedules to training IDs 5101-5105, two to validation IDs
5201-5202, and two untouched schedules to test IDs 5301-5302. Change status and add filename/hash only
after strict acceptance; do not move episodes between splits based on model results. Keep raw Epic
episode files outside Git.

Why: Adjacent transitions are highly correlated, so row-level random splitting would place nearly
identical moments from one trajectory in training and test. Freezing test configurations before model
selection prevents tuning to final outcomes. Explicit configuration provenance compensates for the
current episode schema recording realized actions but not the editable schedule object in its header.

Alternatives considered: random row split; assign splits after seeing model errors; reuse episodes
4101/4201 as independent training and test; commit raw sample data; inspect test episodes during
hyperparameter selection.

Evidence: The YAML plan and accepted manifest bind five training and two validation episodes to
unique IDs, filenames, exact schedules, and SHA-256 hashes. Training provides 740/725 and validation
283/277 no-history/four-history examples. Episodes 5301/5302 remain pending and unopened.

Main assumption: Nine short but distinct schedules provide enough variation for a bounded interview
experiment; the result may still be data-limited.

How it could fail: Fixed phase order may permit action-pattern shortcuts; fewer than roughly 1,000
training transitions may overfit the 100K-parameter MLP; frame-timing variation may dominate; manual
configuration could differ from the plan.

How I tested it: Validated plan invariants automatically; required unique embedded IDs, raw hashes,
strict loader acceptance, realized action sets matching every frozen configuration, unique global
transition identities, and disjoint accepted/rejected artifacts. A regression records loader calls
and proves the audit opens accepted train/validation filenames only.

Related experiment/evidence: `RES-COLLECTION-001`;
`evidence/unreal/res_collection_live_episode_5101.log`.

Live rejection addendum: a technically valid file embedded as 5201 used the frozen training-5102
configuration. It is excluded from all splits rather than renamed or reassigned. This preserves both
embedded identity and the validation configuration frozen before training. Retry 5102 with only the
reset episode ID corrected. SHA begins `4c5629c5`; see
`evidence/unreal/res_collection_rejected_5201_wrong_config.log`.

## D-039 - Fail closed at the accepted-file boundary before normalization

Status: accepted for train/validation; final test remains sealed

Decision: Build the learning dataset only through a machine-audited manifest derived from the frozen
collection plan. Resolve explicit accepted filenames without directory globbing, verify each byte
hash and embedded identity, run the strict episode loader, compare realized action values with the
frozen configuration, and reject all filename/hash/identity overlap. Do not open pending test files.

Why: A correct model experiment can still be invalid if a rejected run, duplicate identity, modified
file, or test episode silently enters preprocessing. The manifest makes the exact bytes and split
boundary independently reproducible while keeping Epic sample data outside Git.

Alternatives considered: glob every JSONL file and filter afterward; trust evidence notes without
rechecking bytes; copy raw files into the repository; inspect pending tests while building coverage.

Evidence: `artifacts/residual/dataset_audit/manifest.json` binds seven accepted files to hashes and
reports 740 train plus 283 validation transitions. `coverage.json` records directions, speeds,
timesteps, turning, stops, parameter regimes, residual strata, and honest zero counts for contact and
external events. `artifact_hashes.json` hashes the generated evidence.

Main assumption: The external raw directory continues to contain the exact hashed files. Relocating
the directory is safe because identity is filename plus SHA-256, not absolute path.

How it could fail: A raw file can disappear; the collection plan can be edited after artifacts are
generated; the fixed scripted phase order can still permit shortcut learning; free-space coverage
does not support claims about collision dynamics.

How I tested it: Seven focused tests cover accepted-only file access, split totals, pre-loader hash
failure, embedded-ID mismatch, accepted/rejected overlap, pending-test metadata rejection, and frozen
action mismatch. The real audit reloaded all seven accepted files, reproduced 740/725 train and
283/277 validation examples, and reported `test_opened=0`. The complete suite passes 262 tests.

Related implementation/evidence: `motionworld/data/residual_manifest.py`,
`motionworld/data/residual_coverage.py`, `scripts/audit_residual_dataset.py`, and
`artifacts/residual/dataset_audit/`.

## D-040 - Center inputs but only scale residual targets

Status: accepted and fitted on the frozen five-episode training split

Decision: Standardize features with training-only mean and population standard deviation. Normalize
each residual target component by its training-only standard deviation without subtracting a target
mean. Give constant dimensions unit scale and record their masks.

Why: Feature centering improves conditioning across mixed physical units. Target scale equalizes the
six losses, but target centering would make normalized output zero decode to a nonzero correction and
destroy the exact nominal fallback invariant.

Alternatives considered: no normalization; center both inputs and targets; fixed hand-chosen physical
scales; include validation when estimating more stable statistics.

Evidence: Ten tests cover feature/target round trips, exact zero preservation, declared training-ID
enforcement, constant-dimension handling, schema serialization, and both supported history widths.

Main assumption: Population standard deviation from five short training episodes is adequate for a
bounded first model. Highly sparse residual components may still make standard deviation sensitive to
the few regime-change rows.

How it could fail: A very small nonconstant scale can amplify numerical noise; a validation schedule
can sit outside the training feature range; scale-only targets leave any residual bias for the output
bias to learn.

How I tested it: Exact arrays survive normalize/denormalize round trips within `1e-12`; normalized
zero targets decode bit-exactly to zero; a tuple containing an undeclared episode ID fails closed.

Real fitted target scales for the no-history model, in the frozen six-component order, are
`[0.0101933 cm, 0.00175551 cm, 0.324062 cm/s, 0.0605781 cm/s, 0.0146909 rad,
0.521149 rad/s]`. The four-history values differ slightly because its first three transitions per
episode cannot form complete windows. Both artifacts record episode IDs 5101-5105 only.

Related implementation: `motionworld/models/residual_normalization.py`.

## D-041 - Freeze a fixed-step one-step baseline before recursive training

Status: accepted; frozen training and one-step validation completed

Decision: Train the no-history and four-history MLPs with the same 1,500 seeded CPU AdamW steps,
batch size 128, normalized Huber loss, and 0.01 normalized correction-magnitude regularizer. Use the
final fixed step as the checkpoint; do not inspect validation for early stopping. Compare both models
and nominal on the identical four-history-eligible validation rows.

Why: A one-step baseline isolates whether the frozen features contain predictive signal before adding
the substantially riskier recursive training path. A fixed optimizer budget prevents validation
checkpoint cherry-picking and makes a first negative result interpretable.

Alternatives considered: validation early stopping; MPS acceleration; tune architectures separately;
claim a teacher-forced multi-row loss as recursive training; open test episodes during development.

Evidence: Twelve tests cover a hand-calculated Huber value, regularizer composition, exact seeded
training reproduction, normalization provenance rejection, exact zero physical decoding, physical
angular-unit metrics, and invalid configurations. The frozen YAML binds the dataset-manifest hash,
architecture, optimizer, loss, seed, CPU dtype, common-row comparison, and sealed test policy.

Main assumption: 1,500 uniform-with-replacement updates are sufficient to expose useful one-step
signal without validation-guided epoch selection. The 100K-parameter models remain large for 725-740
examples.

How it could fail: Stable near-zero rows dominate; the MLP can overfit the fixed phase family; the
history model may hallucinate corrections between regime changes; one-step improvement may compound
badly under recursive rollout.

How I tested it: Two identical 12-step CPU runs produce equal traces and bit-equal state dictionaries.
The experiment script rebuilds and byte-compares the audited manifest before fitting, constructs
train-only normalization, saves checkpoint provenance/hashes, and opens validation only after both
training calls finish.

The real run trained both checkpoints before validation inference. On the 42 held-out
parameter-change rows, no-history reduced p95 position/velocity/yaw/yaw-rate error from
`0.052315 cm / 1.93760 cm/s / 3.60379 deg / 188.180 deg/s` to
`0.002381 cm / 0.107696 cm/s / 0.917758 deg / 18.9772 deg/s`. Four-history improved over nominal
but was weaker than no-history. On parameter-stable rows, the nominal equations remain essentially
exact and either learned model adds small error; results therefore remain stratified.

Related configuration/implementation: `configs/residual_training.yaml`,
`motionworld/models/residual_training.py`, and `scripts/train_residual_models.py`.

## D-042 - Select the no-history residual for planning on recursive validation

Status: accepted for planner integration; final test remains sealed

Decision: Carry the frozen no-history checkpoint into nominal-versus-residual MPC. Preserve the
four-history model as an evaluated ablation, not as the selected deployment model. Do not retrain or
inspect episodes 5301/5302 before final configuration freeze.

Why: On common, teacher-forcing-free validation windows, no-history has lower p95 error than both
nominal and four-history for position, velocity, yaw, and yaw rate at every requested horizon. At
0.5/1.0/1.5 seconds its p95 position error is `14.395/27.934/28.964 cm`, compared with
`16.719/30.222/31.229 cm` nominally. Its yaw error is `20.151/30.691/11.583 deg`, compared with
`46.156/97.287/52.302 deg`. The simpler model also costs less at inference.

Alternatives considered: select four-history because it was the richer hypothesis; tune history
length or capacity on validation; train a recursive loss immediately; stop before planning because
position gains are modest.

Evidence: The no-history relative p95 reductions at 0.5/1.0/1.5 seconds are 13.9/7.6/7.3% for
position, 10.7/9.7/12.1% for velocity, 56.3/68.5/77.9% for yaw, and 65.0/83.0/81.6% for yaw rate.
The comparison uses 241/202/171 common endpoints per model and future recorded actions and timesteps,
but only one real seed state. Predicted state and history advance recursively thereafter.

Main assumption: These angular and modest translational improvements are large enough to alter at
least some short-horizon planner rankings. The planner experiment, not this prediction result, must
test that assumption.

How it could fail: Both validation episodes share the scripted eight-phase collection family with
training; the model may learn scheduler regularities. There are no collision or external-push rows.
The no-history checkpoint can also add error in parameter-stable regions where nominal is already
near exact. Better open-loop prediction need not yield better closed-loop control.

How I tested it: The evaluator verifies checkpoint and manifest hashes, uses common endpoints,
rejects intermediate real-state substitution, labels `teacher_forcing=false`, reports empty strata
as null rather than zero, and records `test_files_opened=0`. Reviewer tests cover all of these
contracts. The first two evaluator attempts exposed reporting-schema defects only; they did not
alter weights, data, or model selection.

Related artifacts: `artifacts/residual/training_001/` and
`artifacts/residual/recursive_001/`.

## D-043 - Use bounded five-knot CEM with reusable common random numbers

Status: core optimizer, synthetic oracle, and offline nominal/residual integration accepted;
live-control and runtime gates pending

Decision: At each 10 Hz planning update, represent the 1.5-second action plan with five planar
velocity knots expanded piecewise-constantly across 15 planning steps, with three internal dynamics
substeps per planning step. Begin with 256 candidates,
32 elites, three iterations, population-variance updates, 0.1 distribution momentum, a 5 cm/s
standard-deviation floor, and a 165 cm/s L2 speed bound. Pre-generate the standard-normal noise so
nominal and residual solvers can use common randomness.

Why: CEM supports the coming discontinuous collision indicator without requiring differentiable
dynamics. Five knots reduce the adaptive search from 30 to 10 dimensions while retaining temporal
control. Common noise removes irrelevant random-seed variation without pretending adaptive candidate
distributions must remain identical after their costs select different elites.

Alternatives considered: 15 independent action knots; one constant action for the whole horizon;
componentwise clipping; direct gradient optimization; require identical physical candidates at every
adaptive iteration.

Evidence: Twenty-three focused tests cover exact seed reproduction, a hand-computed elite update,
quadratic recovery, L2 bounds, zero variance, warm shifting, minimization direction, batch/scalar
ordering, common first-iteration candidates, invalid shapes/settings, and finite-cost fallback. In
CEM-001, the frozen 256/32/3 budget returns `[88.5655, -55.9064]` cm/s for a known
`[90, -55]` cm/s two-dimensional optimum: 1.69683 cm/s error. Best cost falls from 180.798 to
5.12003 to 2.87923, and an exact rerun reproduces JSON and PNG bytes.

Main assumption: Five knots are expressive enough for the timed gate while keeping the small sample
budget useful. This is not yet established by the one-knot oracle.

How it could fail: Coarse knots can miss a narrow timing maneuver; three iterations can be
insufficient in the full 10-dimensional search; projecting a Gaussian onto a disk distorts its
boundary distribution; a fixed variance floor can retain too much late exploration.

How I tested it: The first attempted artifact applied the runtime 15-knot plan to the toy oracle and
returned 88.275 cm/s first-action error. That failure exposed the dimensionality problem rather than
being hidden. The accepted oracle isolates a single two-dimensional decision, while the runtime
configuration separately declares five knots/15 steps and remains gated on integrated tests.

Related implementation/evidence: `motionworld/planning/cem.py`, `configs/cem_planner.yaml`,
`tests/unit/test_cem.py`, `scripts/run_cem_toy.py`, and `artifacts/planning/cem_001/`.

## D-044 - Keep timed-gate geometry and every planning-cost term explicit

Status: independent cost kernels and integrated plot accepted; geometry/weights remain provisional
until live verification

Decision: Rank trajectories with five separately returned quantities: terminal Euclidean goal
distance, any swept gate collision, mean squared clearance deficit, mean squared action first
difference, and mean squared action second difference. Recompute the sinusoidal gate center from
absolute scenario time. Expand collision bounds by agent radius only; apply safety margin separately
as a soft clearance preference.

Why: A single opaque scalar makes sign errors, unit dominance, collision tunnelling, and accidental
reward hacking hard to detect. Separate physical components can be hand-checked and plotted before
weights are chosen. Relative-motion swept collision accounts for both agent and gate movement
between endpoints.

Alternatives considered: endpoint overlap only; learned collision probability; fold safety margin
into the binary collision definition; name unscaled action differences acceleration and jerk;
silently normalize components using validation outcomes.

Evidence: Fourteen focused tests cover the analytic quarter-period gate location, a 3-4-5 terminal
distance, endpoint tunnelling, relative gate motion, exact clearance deficits, first and second
action-difference hand calculations, explicit weighted summation, collision cost sign, invalid
geometry, non-finite values, and non-monotonic time.

Main assumption: Piecewise-linear relative motion between 100 ms analytic gate samples is adequate
for candidate ranking. The full Unreal gate follows a sinusoid continuously, so an integrated
conservatism/step-size review remains necessary.

How it could fail: A high-curvature gate segment can deviate from its endpoint chord; unverified
capsule dimensions make clearance physically wrong; an excessively large smoothness weight can
prevent an otherwise safe avoidance maneuver; a collision weight that is too small lets goal
progress dominate safety.

How I tested it: The initial hand-authored miss from `(-20,0)` to `(20,30)` failed because its segment
actually clips the capsule-expanded gate corner. Recomputing the intersection showed the test
expectation was wrong; moving the endpoint to `(20,50)` creates the intended miss. The geometry test
was corrected without weakening the collision implementation.

Related implementation: `motionworld/planning/cost.py` and
`tests/unit/test_planning_cost.py` (`8c22ae9`).

## D-045 - Treat offline paired planning as an integration and model-risk test

Status: accepted as OFFPLAN-001; explicitly not accepted as Unreal control evidence

Decision: Integrate the frozen no-history checkpoint and faithful nominal transition into the same
batched CEM/cost pipeline using one accepted validation snapshot, common first-iteration actions,
and the same compute configuration. Cross-evaluate each selected action sequence under both models.
Do not call the lower within-model cost a controller win; require execution in Unreal before making
that claim.

Why: A planner optimizes what its model predicts, not what the real system will necessarily do.
Cross-evaluation makes disagreement visible: if a plan is safe only under the model that selected
it, that may be real learned information or model exploitation. Unreal execution is the adjudicator.

Alternatives considered: compare only each controller's reported best cost; force identical
physical candidates at every adaptive CEM iteration; open final test episodes now; describe the
residual plan's lower predicted cost as improved control.

Evidence: Starting from validation episode 5202 transition 0 relocated to `[-100, 0]` cm, nominal
and residual receive the same 256 first-iteration candidates (identical SHA-256) and select first
actions `[40.192, -139.872]` and `[23.420, -102.090]` cm/s. Their own predicted costs are 106.476
and 86.081, both collision-free. Cross-evaluation is sharply inconsistent: the nominal-selected
plan is predicted to collide by the residual model (cost 10070.711), while the residual-selected
plan has cost 216.360 under the nominal model. This is evidence that the model changes planner
rankings, not evidence that either prediction is physically right. Test files opened remains zero.

Main assumption: The counterfactual relocation is valid because absolute position is excluded from
the residual input and the motion equations are translation invariant; gate geometry, capsule
radius, and cost weights are still provisional hypotheses.

How it could fail: The residual was trained only on free-space scripted data and can extrapolate
badly under candidate actions. CEM can exploit those errors. The assumed 42 cm capsule radius may
not match the live pawn. The pure Python paired call takes about 10 seconds, far above the 100 ms
deadline. Neither offline model is ground truth.

How I tested it: Fifty-eight focused planning tests and 350 total tests pass with Ruff. A clean
rerun byte-matches the JSON, CSV, PNG, README, and artifact hashes. The residual batch-versus-single
inference cost differs by only `8.77e-6`, which is recorded rather than mistaken for nondeterminism.
The plot and cross-model cost matrix were visually reviewed. Final episodes 5301/5302 were not
opened.

Related implementation/evidence: `motionworld/planning/planner_rollout.py`,
`motionworld/planning/mpc.py`, `scripts/run_offline_paired_planner.py`,
`configs/offline_planner.yaml`, and `artifacts/planning/offplan_001/`.

## D-046 - Keep a scalar dynamics oracle and deploy only a parity-checked vectorized backend

Status: vectorized backend accepted; residual 100 ms runtime gate failed

Decision: Preserve the scalar Smooth Walking rollout as the readable mathematical reference, while
using a NumPy batch-state implementation for CEM. Select the backend explicitly in
`PlannerProblem`, fail closed on unknown values, and require randomized state/action/residual parity
tests before the vectorized path may become the default.

Why: Profiling showed that the earlier “batch” wrapper still invoked the scalar transition about
71,000 times during one paired plan. That is interpreter overhead, not necessary model complexity.
Vectorizing candidates evaluates the same equations over arrays while keeping the oracle available
to detect optimization drift.

Alternatives considered: reduce the CEM budget before locating the bottleneck; delete the scalar
implementation; accept approximate visual agreement; wire the 10-second reference into Unreal;
claim that a faster rollout automatically meets the controller deadline.

Evidence: For one 256-candidate, 15-step, three-substep residual rollout, the pilot changes from
1.992 seconds to 0.044 seconds (45.3x). Maximum scalar/vectorized disagreement is `9.77e-14 cm`
position and `3.55e-15 rad` yaw. The full paired solve retains identical first actions and falls to
0.244 seconds. Three parity tests include randomized bounded/unbounded commands, stop, turn,
nonzero hidden memory, both facing-spring modes, and nonzero residual composition.

Main assumption: NumPy's array operations preserve every relevant scalar branch within declared
float64 tolerances. The scalar oracle and live Unreal evidence remain authoritative if edge cases
disagree.

How it could fail: Uncovered threshold-adjacent values could choose a different branch. Small
floating-point changes could change elite ordering when candidate costs nearly tie. Transport and
Unreal work add latency not present here. Most importantly, formal RUNTIME-001 measures residual
median/p95 at `149.655/169.401 ms`, so it misses all 30 100 ms deadlines despite vectorization.

How I tested it: 358 tests and Ruff pass. Complete per-controller calls were warmed three times and
measured 30 times in alternating order on one CPU thread. Nominal records `70.709/81.549 ms` median/
p95 with 0 misses; residual records `149.655/169.401 ms` with 30 misses. Test files opened is zero.

Related implementation/evidence: `motionworld/planning/vectorized_rollout.py`,
`scripts/benchmark_planner_runtime.py`, and `artifacts/planning/runtime_001/`.

## D-047 - Reject reduced CEM budgets that buy speed by violating the frozen quality gate

Status: CEM-BUDGET-001 completed; no budget accepted

Decision: Keep 256 candidates/32 elites/three iterations as the planning-quality reference. Do not
deploy any tested reduced budget because none satisfies both 100 ms p95 and the prospectively frozen
10% p95 positive predicted-cost-regret threshold across both models.

Why: Runtime is a constraint, not the only objective. A fast optimizer that materially worsens the
cost it was designed to minimize can change the experiment for convenience and obscure whether
control differences come from the world model or unequal search quality.

Alternatives considered: accept 192/24/2 because its residual p95 is 92.209 ms; accept 256/32/2
because residual quality is close; relax the 10% threshold after seeing the plot; evaluate only the
residual controller; use final test episodes to choose a budget.

Evidence: Every 64-192 candidate/two-iteration budget meets runtime but has 43.47-68.97% worst-model
p95 positive regret. The 256/32/2 budget has 7.31% residual regret but 32.48% nominal regret and
also misses residual runtime at 104.632 ms. None creates a new model-predicted collision, yet none
passes the complete quality rule. Test files opened is zero.

Main assumption: Full-budget model-predicted cost is the appropriate validation-only reference for
search-quality preservation. It is not ground truth and does not replace Unreal evaluation.

How it could fail: The full stochastic optimizer can itself miss better actions; ten validation
snapshots are small; predicted cost can reward model exploitation. The gate only prevents a large
known optimization regression before live testing.

How I tested it: Counts and validation indices were committed before execution. Reduced budgets use
nested common random numbers, retain the elite fraction, and are scored under identical dynamics,
cost, geometry, bounds, and starting states. The plot was visually inspected and the test counter
remained zero.

Related evidence: `configs/cem_budget_sweep.yaml` and
`artifacts/planning/budget_sweep_001/`.

## D-048 - Reject width compression that fails planning and runtime gates

Status: RESIDUAL-COMPRESS-001 completed; no compressed model accepted

Decision: Retain the 256/256/128 no-history residual checkpoint as the prediction reference. Do
not replace it with any of the four tested 192/192/96, 128/128/64, 96/96/48, or 64/64/32 models.
Do not claim that the 128/128/64 model is deployment-ready merely because it passed the recursive
prediction gate.

Why: A world model is useful to MPC only if its errors do not change the optimizer into selecting
bad trajectories. Model size, recursive prediction, planner behavior, and complete-call latency
therefore need independent gates. The 128/128/64 network stayed within the predeclared 15% limit on
all recursive p95 metrics, but its chosen plans failed when evaluated by the frozen reference model.

Alternatives considered: select the smallest or fastest model on latency alone; select 128/128/64
on recursive accuracy alone; relax the planner-regret threshold after seeing the result; use test
episodes for compression selection; use NumPy, Torch tracing, `torch.compile`, or dynamic int8
quantization as unverified speed claims.

Evidence: No candidate passes all three gates. Parameter counts fall from 106,886 to 61,734,
28,870, 17,046, and 8,294. Only 128/128/64 passes recursive quality, with worst p95 degradation
8.43%. All four fail reference-model cross-evaluated planning: p95 positive regret is 10227.6%,
10693.8%, 6400.2%, and 9014.7%, with one or two new predicted collisions. All four also miss the
100 ms full-CEM p95 deadline; the smallest records 114.695/117.234 ms median/p95. Test files opened
is zero.

Main assumption: The frozen full-width checkpoint is a useful validation-only arbiter of whether
compression changes its planning behavior. It is not physical ground truth; only Unreal execution
can adjudicate model disagreement.

How it could fail: A compressed model might be closer to Unreal than the reference despite disagreeing
with it. The 20-call runtime sample is small and the 128/128/64 p95 contains a large tail. The
training objective uses ground-truth residuals rather than teacher distillation on planner-query
states. The accepted dataset is free-space and narrow.

How I tested it: Candidate widths, hashes, seed inheritance, validation queries, and all thresholds
were committed before training. All candidates received identical fixed optimizer budgets and
train-only normalization; none consulted validation until every checkpoint existed. Recursive
rollouts were teacher-forcing-free. Candidate-selected plans were re-evaluated through the frozen
reference model to expose exploitation. Test episodes 5301/5302 remained sealed. Exploratory
threading improved the full model only slightly at two threads; NumPy, JIT, and compile did not
speed it up, and this Apple build exposes no quantized linear engine.

Related evidence: `configs/residual_width_sweep.yaml`,
`scripts/run_residual_width_sweep.py`, and `artifacts/residual/compression_001/`.

## D-049 - Use fixed 10 Hz slots with sequence-gated exclusive deadlines

Status: accepted for the recovery live-control vertical slice

Decision: Keep the original 10 Hz control target. The first valid post-reset `OnPostFinalize`
sample defines slot and sequence zero. Unreal then emits the first valid finalized sample at or
after each fixed 100 ms simulation-time boundary. It never sends a burst to catch up; if several
boundaries elapsed, only the latest elapsed slot is emitted. An action is accepted only for its
matching current episode and observation sequence, less than 100 ms after Unreal sent that
observation, and before the next observation is emitted. The deadline boundary is exclusive.
Sequence increments once per emitted observation, not once per skipped slot; skipped-slot count is
diagnostic telemetry. A validated current action is applied immediately and held until a newer
validated action or the fallback policy replaces it. Replanning is scheduled at 10 Hz, while the
within-slot application instant reflects measured response latency.

Why: Mover finalization is observed at a variable roughly 25--35 ms cadence in existing evidence,
while MPC actions have a 100 ms semantic duration. Fixed simulation-time slots avoid callback-rate
dependence and accumulated scheduling drift. Sequence plus elapsed-time checks prevent a quick
answer to an obsolete state from being applied as if it were current.

Alternatives considered: emit every finalized callback; use every third or fourth callback; advance
the next slot from the actual callback time; send all missed slots in a burst; accept a late result
for the next slot; silently reduce the controller to 5 Hz. These either create variable semantics,
accumulate drift, overload the planner, apply stale actions, or change the target project.

Failure behavior: Before the first valid result, command zero. A slot with no valid matching action
by its deadline is one miss. Misses one and two hold the last valid action; miss three and later
command zero. A valid current action clears the count. Reset, controller switch, shutdown, and
reconnection clear held action, pending sequence/deadline, and miss state. A timely explicit
planner fallback to zero is a valid safe result and is diagnosed separately from transport loss.

Main assumption: Unreal simulation time is monotonic within an episode and `OnPostFinalize` is the
authoritative sampling boundary. Unreal's own monotonic clock measures send-to-receive elapsed time;
no cross-process clock comparison is required.

How it could fail: Large game-thread stalls can skip control slots, variable observation lateness
reduces the useful planner budget, and holding an earlier action for two misses may be unsafe near a
fast obstacle. The live vertical-slice failure tests must measure these cases. Scenario-specific
safety may later choose an earlier stop, but may not extend the three-miss bound.

How I tested it: `configs/control_runtime.yaml` is loaded through an exact-key, exact-literal parser.
Tests reject frequency/interval disagreement, a deadline longer than one slot, inclusive deadline
semantics, coercible wrong types, an inconsistent hold/stop threshold, and unknown schema fields.

Related evidence: `configs/control_runtime.yaml`,
`motionworld/protocol/runtime_config.py`, and
`tests/unit/test_control_runtime_config.py`.

## D-050 - Use three 1/30-second dynamics substeps per 100 ms planning step

Status: accepted for nominal and residual live-planner rollouts

Decision: Keep `dynamics_substeps_per_plan_step: 3`, giving three equal `1/30 s` dynamics
substeps inside every 100 ms planner step. Use the same schedule in scalar and vectorized planning
and for both nominal and residual controllers. Continue to use each real transition's recorded
`dt` during residual training and prediction evaluation. Recorded-`dt` future replay is an accuracy
oracle only and is prohibited in live counterfactual planning.

Why: Accepted Unreal callbacks are variable rather than 60 Hz. Train median/p95/max is
`28.000/32.050/95.000 ms`; validation is `27.000/40.900/96.000 ms`. On 74 validation windows with
constant action and current parameters, three `1/30 s` steps beat six `1/60 s` steps on p95
position (`0.539 vs 1.184 cm`) and velocity (`2.320 vs 3.362 cm/s`). Six steps improved yaw p95
slightly (`3.288 vs 3.916 deg`) and yaw-rate p95 (`40.460 vs 41.587 deg/s`), but its complete
nominal CEM p95 was `143.565 ms`, versus `93.897 ms` for three steps, so it violates the 100 ms
compute budget before transport or Unreal application is counted.

Alternatives considered: assume Unreal is fixed 60 Hz; use six `1/60 s` substeps; replay future
recorded `dt`; use callback count as control time; use one 100 ms dynamics step. Six steps lose the
runtime gate and translation accuracy, future `dt` leaks unavailable information, callback count is
variable, and one large step was not the original fidelity target.

Main assumption: Linear interpolation between surrounding authoritative samples is adequate for
comparing exact 100 ms endpoints in these free-space, constant-context windows. The result does not
claim collision accuracy or bit-exact Unreal reproduction.

How it could fail: The 74 windows exclude action and parameter changes, the fixed-30 nominal p95
leaves little room under 100 ms for transport, and residual p95 remains `230.265 ms`. Live profiling
and multi-step residual reconciliation remain mandatory; this decision does not pass R5.

How I tested it: The audit uses only the seven SHA-256-approved train/validation files and reports
zero test files opened. Both schedules total exactly 100 ms. Scalar/vectorized parity uses the
selected three-substep configuration. Complete CEM timing used the same snapshot, candidate budget,
seed, one CPU thread, three warmups, and 30 alternating calls per controller.

Related evidence: `scripts/audit_timestep_policy.py`,
`artifacts/recovery/timestep_policy_001/`, `configs/cem_planner.yaml`, and
`tests/unit/test_timestep_policy_audit.py`.

## D-051 - Freeze the recursive residual-training contract before implementation

Status: contract and correctness-first differentiable implementation accepted

Decision: Preserve both schema-v1 one-step checkpoints byte-for-byte as baselines. Train new,
separately identified no-history and four-history multi-step variants over complete 1.5-second
within-episode windows. Supervise at 15 elapsed-time boundaries, weight boundary `k` by
`0.9^(k-1)`, use normalized component Huber with beta 1.0, and add `0.01` times mean normalized
predicted-residual magnitude. Hold the rollout-start parameters, advance nominal internal state and
predicted observable state recursively, and seed four-history with three real past queries before
shifting predicted queries. Reject incomplete tails rather than pad them as targets.

Training contract: CPU float32, widths 256/256/128, AdamW at 0.001 with weight decay 0.0001,
batch size 16, 600 fixed optimizer steps, global gradient-norm clipping at 1.0, seed 20260904, and
fixed-final-step checkpoint selection. Both variants must exist before validation is opened.

Why: The current model is a legitimate deterministic one-step baseline, but its loss contradicts
the original recursive-training specification. Merely looping NumPy inference would detach the
gradient graph and cannot be called recursive training. The new path must backpropagate through
predicted state, nominal hidden state, residual composition, and predicted history.

Evidence so far: Exact config validation binds the accepted dataset-manifest hash and immutable
baseline checkpoint hashes. The five accepted training episodes yield 475 no-history and 460
four-history complete windows, each 52--56 recorded transitions. Unit tests cover the 15-boundary
contract, incomplete-tail rejection, history prefix, padding masks, wrong hashes, and a two-step
discounted-loss hand calculation.

Implementation evidence: The Torch nominal step matches the scalar observable and all five hidden
state fields within `1e-5`. Full 1.5-second no-history and four-history tests produce finite nonzero
gradients from a zero-output model. A masked zero-vector normalization bug that initially produced
NaN gradients was caught and corrected before acceptance. Two identical seeded training runs have
equal traces and bit-equal weights. The implementation is correctness-first and processes sampled
windows sequentially; runtime optimization may be required before the frozen full run.

Remaining risk: The smaller fixed optimizer budget is a compute-bounded hypothesis and cannot be
tuned after inspecting validation. Passing synthetic parity and gradient tests does not establish
that the new model will improve held-out recursive prediction; that remains R4 evidence.

Related files: `configs/residual_multistep_training.yaml`,
`motionworld/models/multistep_training.py`, and `tests/unit/test_multistep_training.py`.

## D-052 - Freeze separate final prediction and paired-control evaluation drafts

Status: accepted draft; live capsule verification and R7 hash freeze remain mandatory

Decision: Reserve episodes 5301/5302 only for final recursive prediction evaluation and keep their
raw identities absent until R7 authorizes collection. These schedules are free-space; near-contact,
post-push, and held-out-setting prediction strata must therefore be reported as absent rather than
manufactured from other runs. Use separate controller seeds 7101-7112 for timed-gate, push-recovery,
interpolated deceleration (650 cm/s^2), and OOD deceleration (1300 cm/s^2) scenarios. Counterbalance
controller order and give nominal and residual MPC identical CEM randomness and all inputs except
the transition model. Reactive control is contextual and required on timed-gate seeds, but is not
part of the primary causal contrast.

Primary estimand: Mean paired timed-gate success-proportion difference, residual MPC minus nominal
MPC; 0.10 means 10 percentage points. Plan
12 pairs and require at least 10. Compute a 95% paired percentile-bootstrap interval using 10,000
resamples and seed 20260905. A positive claim requires observed improvement of at least 0.10, an
interval strictly above zero, a non-inferior collision guardrail, residual end-to-end p95 strictly
below 100 ms, and all four causal links. Significant primary harm, significant collision harm, or
runtime failure is negative. The exact complement, including insufficient pairs or an interval
overlapping zero, is unresolved.

Why: Prediction accuracy, action selection, executed task outcome, safety, and deployability are
different questions. Fixing identities and interpretation before results prevents seed selection,
metric selection, and missing-run rules from adapting to the desired story. Pairing reduces
scenario variance without pretending that 12 runs provide high power.

Invalid-run rule: Collision, timeout, missed deadline, safe fallback, and non-recovery are valid
controller outcomes. Only the enumerated infrastructure failures invalidate an attempt. Retain all
attempts, retry the same identity at most once, never substitute a seed after results, and label a
scenario with fewer than 10 valid pairs unresolved.

Geometry correction: The provisional offline-planner assumption was 42 cm radius and 96 cm
half-height. A headless UE 5.8.2 query transiently constructed the actual
`SandboxCharacter_Mover` Blueprint and found one `CapsuleComponent` named `Capsule`, with both
scaled and unscaled dimensions 30 cm radius and 86 cm half-height. The final-control draft now uses
30/86. Historical offline evidence remains unchanged and must be described with its provisional
42 cm planning radius.

Pre-result scenario audit: The first draft accidentally combined a 700 cm push target with a 3.5 s
timeout, although 165 cm/s permits at most 577.5 cm even without acceleration. It also declared a
world-Y kick despite defining reset pose relatively. Correct the push target to reset-local
`[500, 0]` cm, timeout to 6 s, and observation horizon to 4.5 s after the 1.5 s kick. Declare the
kick as reset-local `[0, 250, 0]` cm/s and rotate it once into world space using verified reset yaw.
This is a contract correction before any controller result, not post-result tuning.

How I tested it: Fail-closed Python loaders reject test/control identity overlap, scenario seed
drift, teacher forcing, raw test metadata, missing failure outcomes, and schema additions. The
focused suite passes without opening any episode file.

Related files: `configs/final_prediction_manifest.yaml`,
`configs/final_control_manifest.yaml`, `motionworld/evaluation/contracts.py`, and
`tests/unit/test_final_evaluation_contracts.py`.

## D-053 - Define a bounded causal observation protocol before transport

Status: accepted Python logical/serialization contract and cross-language fixture; live Unreal
producer integration remains R2 work

Decision: Name protocol v1 `motionworld_control` and encode observations as deterministic compact
UTF-8 JSON bounded to 16,384 bytes. Carry separate episode, 10 Hz observation, and authoritative
state-sample identities. Include the fixed 100 ms interval, simulation time, controller/source,
finalized state, aligned current Smooth Walking parameters/preparation/internal state, previous
applied action, reset/scenario/termination state, and explicit validity. Reject resimulation.

Keep target and deterministic gate configuration/current state in `planner_context`. Validate that
branch, but remove it through `causal_dynamics_context` before model feature construction. Never
admit animation-root data, actual next state, later parameter snapshots, a future perturbation, or
outcome labels into dynamics context.

Why: The planner legitimately needs known future obstacle geometry, while character dynamics do
not. Structural separation is stronger than relying on each caller to remember which keys are
privileged. Three identities are required because resets, 10 Hz decisions, and higher-rate finalized
states advance under different rules.

How it is tested: Exact-key/type/range checks cover protocol literals, finite values, vector sizes,
unit facing/quaternion constraints, state/context alignment, previous-action chronology, optional
payload/validity agreement, terminal consistency, duplicate JSON keys, malformed UTF-8, oversize,
unknown animation fields, detached outputs, deterministic round trips, and planner exclusion.

## D-054 - Separate action structure from current-observation admission

Status: accepted Python and Unreal logical/serialization contract; live bridge admission remains R2
work

Decision: Encode `motionworld_control` action v1 as deterministic compact UTF-8 JSON bounded to
8,192 bytes. Echo episode and source-observation identity; transmit the selected character-local
planar velocity, bounded controller/model identifiers, Python monotonic start/end timestamps and
consistent measured planner latency, and explicit safe-fallback status/reason. Safe fallback actions
must command zero. Optional diagnostics contain no more than 32 selected trajectory steps and the
six declared planning-cost components.

Validate packet structure independently from runtime admission. Admission requires the current
episode, exactly the current outstanding observation sequence, and a sequence not already accepted;
classify lower sequences as stale and higher sequences as future. Unreal's existing production path
remains the final safety boundary: after local-to-world resolution it rejects non-finite vectors,
projects out Z, and magnitude-clamps every command. Do not duplicate that sanitizer merely because
the network action source is new.

Why: Schema validity cannot establish temporal relevance. Separating the checks makes malformed data
and delayed/replayed work diagnosable without ever reassigning a result to a different timestep.
Planner clocks measure only Python duration; Unreal owns end-to-end deadline measurement, so the
design makes no cross-process clock comparison. Telemetry is bounded and non-authoritative to keep
large diagnostic payloads out of command semantics.

How it is tested: Python tests cover deterministic round trip, exact keys/types, finite two-value
local action, bounded identifiers/trajectory, timestamp ordering and duration consistency, explicit
zero fallback, six finite non-negative cost fields, binary collision indicator, wrong episode,
future/stale/duplicate sequences, malformed/duplicate/invalid UTF-8 JSON, oversize, and detached
results. Existing Unreal `MotionWorld.Command.SanitizeWorldVelocity` automation covers zero,
boundary, oversized, vertical, reverse, and non-finite requests at the application boundary.

## D-055 - Use bounded nonblocking IPv4 loopback UDP

Status: accepted transport/serialization seam; gameplay integration remains R2

Decision: Carry one strict RFC 8259 UTF-8 JSON object per IPv4 loopback UDP datagram. Configure
Unreal at `127.0.0.1:52580` and Python at `127.0.0.1:52581` through
`configs/control_transport.yaml`. Bound observations to 16,384 bytes, actions to 8,192 bytes,
diagnostic trajectories to 32 steps, raw UDP receives to 65,507 bytes, and each nonblocking poll to
16 datagrams. Both implementations reject empty, oversized/truncated, and unknown-sender datagrams
before JSON parsing. The Unreal byte transport has no reference to the bridge and cannot mutate
gameplay state.

Declare JSON byte order not applicable, parse real numbers as binary64, and restrict integer wire
values to the exactly representable range `0..2^53-1`. Change Python diagnostic planner timestamps
from nanoseconds to monotonic microseconds so their integer values remain safely representable while
retaining sub-millisecond resolution.

Failure policy: UDP loss is not retransmitted because the original decision expires at the next
observation/deadline. Duplicates and reordered packets reach semantic episode/current-observation
admission and are discarded unless they answer the one outstanding decision. Transport rejection
and deadline fallback remain separately counted.

Why: Loopback UDP is the frozen P0 choice and avoids stream framing or connection lifecycle work.
Nonblocking operations protect the Unreal game thread from waiting, while a fixed poll count also
bounds CPU work under a flooded queue. Fixed buffers and pre-parse size/source checks prevent packet
contents from causing unbounded parsing allocation. Exact JSON-safe integers prevent silent identity
rounding between Python integers and Unreal binary64 JSON numbers.

How it is tested: Python config tests reject endpoint, schema, policy, size, and blocking-mode drift.
Real loopback tests cover empty polls, one-datagram framing, fixed poll budgets, unknown senders,
empty and oversized packets, bounded sends, and blocking-socket rejection. Strict UE 5.8 universal
Editor/Development/Shipping builds pass. The first Unreal automation run exposed that macOS
`HasPendingData` can reflect queued bytes rather than the next datagram size; using actual
`RecvFrom` bytes fixed the false rejection. The corrected focused automation test passes and is
preserved in `evidence/unreal/r1_transport_udp_automation.log`.

## D-056 - Use shared semantic fixtures at the Python/Unreal trust boundary

Status: accepted cross-language protocol test seam; live control-loop behavior remains R2 work

Decision: Preserve three version-1 fixtures inside the plugin package: one full Unreal observation,
one normal Python action with bounded diagnostic telemetry, and one zero-identity/zero-action packet
with telemetry explicitly absent. Python must strictly parse and deterministically re-encode every
fixture it consumes. Unreal must parse Python action bytes into typed fields and perform separate
current-observation admission.

The Unreal parser rejects empty/oversized packets and invalid UTF-8 before JSON allocation, rejects
duplicate keys before DOM deserialization, requires exact schema keys and safe binary64 integers,
and classifies wrong-episode, future, stale, and duplicate work with bounded labels that contain no
packet bytes. Both implementations exercise a deterministic 128-packet, maximum-256-byte malformed
corpus; fixtures contain no checkpoint/model-state payload and remain below their frozen caps.

Why: Parser tests written independently against independently invented examples can both pass while
the real wire formats disagree. Shared bytes expose naming, shape, optional-field, number, and
identity drift. Golden fixtures are boundary evidence, not live-system evidence: they do not prove
UDP timing, fallback behavior, or gameplay mutation, which remain later gates.

How it is tested: Python cross-language tests pass 21/21 and the full Python suite passes 495/495.
The Unreal `MotionWorld.Protocol.CrossLanguageFixtures` automation test passes in a headless UE 5.8
host, with evidence in `evidence/unreal/r1_cross_language_automation.log`. Strict universal Mac
Editor Development, Game Development, and Game Shipping builds pass. Ruff, environment verification,
interview-package verification, and `git diff --check` pass. The deployed source/resources match the
repository, the actual Game Animation Sample universal Editor target builds, and both discovered
`MotionWorld.Protocol` tests pass there with exit code zero. Actual-sample evidence is preserved in
`evidence/unreal/r1_actual_sample_protocol_automation.log`. The independent protocol implementation
commit is `d85eeaf`; Gate R1 is accepted without making a live-control claim.

## D-057 - Make the Python service latest-only with cooperative planner cancellation

Status: accepted Python lifecycle seam; Unreal round trip and real controllers remain R2 work

Decision: Provide the installed `motionworld-control-service` entry point backed by the exact
`configs/control_service.yaml` schema. Resolve runtime/transport files only beneath that config's
directory, bind the declared IPv4 loopback endpoint, validate before dispatch, and maintain bounded
episode/sequence plus diagnostic state. Use one daemon planning worker with one active and at most one
pending newest observation. A newer observation cancels active/pending work cooperatively and makes
all older results ineligible for sending.

Close the UDP socket before bounded worker shutdown. Expose health/readiness/controller and counters
as a bounded snapshot containing no packet data. The temporary CLI planner returns an explicit zero
`planner_error` safe fallback; do not call it echo, reactive, nominal MPC, or residual MPC behavior.

Why: FIFO work becomes stale under planner overload, while forcibly terminating Python threads is
unsafe. Cooperative cancellation protects compute freshness; episode/sequence revalidation protects
command correctness even when cancellation is ignored. Bounded identity/diagnostic storage prevents
a long-running service from accumulating episode or attacker-controlled payload state.

How it is tested: Configuration tests reject unknown keys, unsupported modes, absolute/traversing
paths, and invalid bounds. Real loopback tests cover configured binding, validation-before-dispatch,
bounded non-payload diagnostics, duplicate/old-episode rejection, bounded episode tracking, active
planner cancellation, newest-only action output, mode mismatch, cooperative shutdown/socket release,
and a clean-process module entry point. The installed console entry point also validates successfully
after a frozen environment refresh.

## D-058 - Keep scheduling, admission, and gameplay mutation in separate Unreal layers

Status: accepted for R2.2; live round-trip evidence remains R2.3-R2.5

Decision: Add a default-off `UMotionWorldNetworkControllerComponent` beside the existing bridge. A
pure `FNetworkRuntime` owns fixed 100 ms simulation-time slots, one outstanding observation, the
exclusive 100 ms monotonic deadline, previous-applied-action chronology, miss count, and hold/stop
fallback. The component owns bounded nonblocking UDP polling, strict parser invocation, separate
malformed/stale/rejected/transport counters, observation serialization, and lifecycle clearing. It
may request only a character-local velocity through `UMotionWorldBridgeComponent`; the bridge keeps
the final game-thread local-to-world conversion, finite check, planar projection, magnitude clamp,
and Mover input production.

The bridge notifies the network component only after both authoritative `OnPostFinalize` state and
aligned Smooth Walking parameters/internal state have been captured. Simulation time chooses which
world-state slot to emit; Unreal monotonic wall time measures real response latency. There is no
catch-up burst after skipped slots. A result must match the one outstanding episode/sequence and
arrive strictly before its deadline and before the next observation. Misses one and two hold the
last validated command; miss three and later command exact local zero. Reset, controller switch,
service reconnection, and EndPlay invalidate runtime state and zero the held command. Normal disable
also closes transport and disables bridge automation; a disable request during pending reset is
rejected explicitly because the bridge cannot safely restore human input until verification ends.

Why: Transport arrival, temporal eligibility, and safe application are different trust boundaries.
Keeping them separate makes the pure timing policy exhaustively testable and prevents a valid JSON
packet from bypassing the established movement clamp. Split clocks prevent pause/time dilation from
making a genuinely late service response appear timely. Nonblocking game-thread polling avoids both
waiting and unsafe background UObject mutation.

Alternatives rejected: put sockets directly in the bridge; emit every finalized callback; queue
catch-up observations; accept a late action for a newer slot; use simulation time for network
deadlines; or mutate Mover inputs from a worker thread. These respectively create a monolith,
variable control semantics, obsolete work bursts, causal reassignment, pause-dependent deadline
errors, or unsafe engine-thread ownership.

How it is tested: Strict non-unity universal Mac Editor, Development Game, and Shipping Game plugin
builds compile the component and pure kernel. The actual UE 5.8.2 Game Animation Sample universal
Editor target also builds. `MotionWorld.Network.ObservationSerialization` proves default-off
construction, bounded v1 JSON, sequence-zero absence, causal previous-action identity, and
state/context alignment rejection. `MotionWorld.Network.RuntimeLifecycle` covers slot boundaries,
no burst after a time jump, accepted action identity, exclusive deadlines, two holds, third-miss
zero, and stopped/reset state. Both focused actual-sample tests pass. The full Python suite remains
509/509 and Ruff passes. Final-test episodes 5301/5302 were not opened.
