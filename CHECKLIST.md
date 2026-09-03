# MotionWorld Master Execution Checklist

Hard deadline: Friday 4 September 2026 at 15:00 Europe/Copenhagen

Code freeze: Thursday 3 September at 22:00

Obsidian task: `M7UXD`

This is the canonical execution checklist. `PROJECT_PLAN.md` explains why and when; this file records whether every atomic obligation is actually complete.

## Status rules

- `[ ]` means incomplete. Never check an item because work merely started.
- `[x]` means the stated evidence exists and was reviewed.
- Every artifact must identify its config, seed, Git commit, and reproduction command.
- Every positive scientific claim must point to a real experiment entry.
- Synthetic results must be labeled synthetic and never substituted for Unreal evidence.
- A phase gate is passed only when all required boxes in its gate subsection are checked.
- P1/P2 boxes remain intentionally unchecked until every P0 gate that protects them passes.

## Daily dispatch and hard checkpoints

### Saturday 29 August - foundation

- [x] Complete specification/interviewer research.
- [x] Establish durable task memory and living documents.
- [x] Establish evidence ladder, branching policy, commit policy, and integrity rules.
- [x] Commit foundation documentation.

### Sunday 30 August - environment and Unreal feasibility

- [x] Verify Unreal 5.8 and Game Animation Sample installation/acquisition (completed later than the original 10:00 target).
- [x] While installation runs, bootstrap only independent Python environment/contracts/theory tests.
- [x] Open the sample and compile the smallest project-specific module (completed later than the original 13:00 target).
- [x] Apply programmatic desired velocity and capture authoritative post-movement state (completed after the original Sunday 18:00 target).
- [x] Demonstrate deterministic character reset and preserve complete in-memory episode lifecycle evidence.
- [x] Add the deterministic timed gate and its event/termination labels.
- [x] Persist one complete character-dynamics episode file and validate all 458 rows independently in Python.
- [ ] Close/merge `feature/unreal-feasibility` only if the Section 4 feasibility gate and required Section 5 safety checks pass.
- [x] Do not activate the Manny plus Mover fallback because the Game Animation Sample path is working.
- [x] Do not freeze Unreal claims at evidence levels 1-2 because UE 5.8.2 runtime evidence is available.

### Monday 31 August - nominal model and data

- [x] Implement and execute the core coordinate conversion tests in the actual UE 5.8 sample.
- [ ] Complete the candidate coordinate derivation and remaining robustness checks in Section 3.1.
- [ ] Complete the Section 3.2 hand-oracle calculations and tests.
- [ ] Complete the Section 3.3 deterministic theory backend.
- [ ] Complete Section 6 faithful nominal model and substep tests.
- [ ] Complete enough Section 7 collection/validation to measure real residual structure.
- [x] Produce first nominal-versus-Unreal recursive error plot.
- [x] Decide whether meaningful decision-relevant residual structure exists: NOM-002 is a bounded
  negative result for the faithful retrospective model; the hidden event step is large, while
  observed post-event recovery is reproduced to numerical tolerance.
- [ ] Merge nominal/data branches only after their respective gates pass.

### Tuesday 1 September - residual model

- [x] Complete residual target/composition and zero-residual invariant.
- [x] Complete no-history and four-history model training.
- [x] Complete recursive held-out comparison at 0.5/1.0/1.5 s.
- [x] Decide by end of day whether learned prediction is strong enough for planning integration:
  proceed with the no-history checkpoint selected on validation only.
- [x] Preserve negative outcome rather than weakening nominal baseline or tuning final test cases:
  the four-history model lost to the simpler model and no test episode was opened.
- [ ] Close/merge `feature/residual-model` only after Section 8.6 gate review.

### Wednesday 2 September - CEM and live control

- [x] Complete deterministic offline CEM and cost tests before Unreal integration.
- [x] Demonstrate identical candidate actions and planner settings for nominal/residual MPC.
- [ ] Demonstrate live nominal MPC.
- [ ] Demonstrate live residual MPC if prediction gate passed.
- [ ] Demonstrate pause-mode counterfactual futures.
- [ ] Complete service failure and reset-isolation tests.
- [ ] Close/merge planner/integration branches only after Sections 9.6 and 10.4 pass.

### Thursday 3 September - frozen evidence, demo, and package

- [ ] Freeze all final configs/checkpoints/seeds/metrics before final test inspection.
- [ ] Run paired timed-gate, push, and held-out-setting evaluations.
- [x] Produce bounded validation statistics, cross-model exploitation diagnostic, and offline
  runtime report; live/final-test statistics remain incomplete.
- [ ] Produce main table, prediction graph, causal trace, and failure case.
- [ ] Finish live HUD/trajectory view and record fallback video.
- [ ] Complete repository/artifact packaging and clean reproduction check.
- [ ] Stop feature coding at 22:00 even if stretch goals remain.

### Friday 4 September - defense and interview

- [ ] Make no feature changes.
- [ ] Run three fresh-launch rehearsals.
- [ ] Verify offline fallback package.
- [ ] Complete blank-page theory derivations.
- [ ] Complete Daniel-style and Viktoriia-style hostile examination.
- [ ] Repair only a proven launch-blocking defect, then rerun all rehearsals.
- [ ] Stop preparation early enough to enter the 15:00 interview rested and organized.

## 0. Project governance and ownership

### 0.1 Durable memory

- [x] Create one Obsidian task note for the entire project.
- [x] Record stable task ID `M7UXD`.
- [x] Record base branch `main` and current work branch.
- [x] Read the task note before broad exploration in each new session.
- [ ] Update memory whenever a material design decision changes.
- [ ] Update memory whenever an exploration path is rejected.
- [ ] Update memory whenever validation changes confidence.
- [ ] End every work block with a resume-ready handoff.
- [ ] Keep the task note readable in under two minutes.

### 0.2 Living documents

- [x] Create `PROJECT_SPEC.md` as the exact system contract.
- [x] Create `PROJECT_PLAN.md` as the dated execution plan.
- [x] Create `THEORY.md` for equations, hand calculations, and candidate explanations.
- [x] Create `DECISIONS.md` using the required decision template.
- [x] Create `EXPERIMENT_LOG.md` with immutable experiment provenance fields.
- [x] Create `INTERVIEW_DEFENSE.md` for adversarial questions and evidence-backed answers.
- [x] Create `CHECKLIST.md` as the canonical atomic execution tracker.
- [ ] Update `PROJECT_SPEC.md` before intentionally changing implemented behavior.
- [ ] Record every consequential choice in `DECISIONS.md`.
- [ ] Record every result that influences a conclusion in `EXPERIMENT_LOG.md`.
- [ ] Add every weak oral answer to `INTERVIEW_DEFENSE.md` until resolved.

### 0.3 AI ownership contract

- [x] Adopt Mentor -> Builder -> Reviewer -> Examiner workflow.
- [ ] Candidate states each component's purpose before implementation.
- [ ] Candidate writes or validates the governing equation.
- [ ] Candidate completes at least one hand calculation for each mathematical module.
- [ ] Builder implements only the bounded component currently under review.
- [ ] Reviewer actively searches for leakage, unfairness, unit errors, sign errors, and unsupported claims.
- [ ] Examiner requires a roughly one-minute explanation without looking at code.
- [ ] Candidate explicitly approves each material design decision.
- [ ] Never treat AI output as final authority on Unreal APIs.
- [ ] Never treat AI output as final authority on mathematical or experimental claims.

### 0.4 Git discipline

- [x] Create `docs/project-foundation` from `main`.
- [x] Commit research and execution contract as `f855d33`.
- [x] Commit deadline-adjusted plan as `ee134f9`.
- [x] Review and merge `docs/project-foundation` into `main`.
- [x] Create `feature/unreal-feasibility` from updated `main`.
- [ ] Create later milestone branches only after the prior gate merges.
- [ ] Make small commits after coherent tested slices.
- [ ] Run focused tests before every commit.
- [ ] Run `git diff --check` before every branch close.
- [ ] Confirm living documents match actual behavior before branch close.
- [ ] Record commit hashes in Obsidian and relevant experiment entries.
- [ ] Never commit licensed Game Animation Sample content.
- [ ] Never commit raw private data, credentials, caches, build products, or oversized checkpoints.

## 1. Immediate environment and installation gate

### 1.1 Verified machine inventory

- [x] Record Apple M4 architecture.
- [x] Record 16 GB system memory.
- [x] Record Xcode 26.6 and Apple Clang 21.
- [x] Record `uv` 0.12.2 and Python 3.12.13 availability.
- [x] Record CMake 4.2.1 availability.
- [x] Record approximately 105 GiB free disk at inventory time.
- [x] Confirm default Python 3.14 does not contain PyTorch.
- [x] Confirm Epic Games Launcher is installed.
- [x] Confirm no `UnrealEditor.app` was detectable at inventory time.

### 1.2 Unreal installation - user/system prerequisite

- [x] Open Epic Games Launcher.
- [ ] Check free-space requirement before selecting engine components.
- [x] Install or locate Unreal Engine 5.7 or 5.8.
- [x] Record exact Unreal version and build identifier.
- [x] Acquire the matching Game Animation Sample.
- [x] Record the sample version/source.
- [x] Launch the unmodified sample once.
- [x] Confirm the sample editor opens on Apple Silicon.
- [ ] Record launch time and any warnings relevant to Mover or animation.
- [ ] Confirm project files can be generated for Xcode.
- [x] Compile the behavior-free MotionWorld plugin against UE 5.8.2.
- [x] Compile and load the behavior-free plugin in the actual Game Animation Sample.
- [x] Confirm manual Play-In-Editor movement parity with the plugin enabled.
- [x] Capture the exact engine and sample paths locally without committing licensed content.

### 1.3 Python environment

- [x] Create project metadata (`pyproject.toml`) with supported Python range.
- [x] Create `.python-version` targeting Python 3.12.
- [x] Create project-local `uv` virtual environment.
- [x] Add PyTorch, NumPy, SciPy, scikit-learn, plotting, configuration, and test dependencies.
- [x] Lock exact dependency versions.
- [x] Add `.venv`, caches, checkpoints, datasets, and generated results to `.gitignore` as appropriate.
- [x] Import all required packages in one smoke test.
- [x] Record PyTorch version.
- [x] Record CPU and MPS availability.
- [x] Run a deterministic tensor operation twice and compare results.
- [x] Decide CPU-versus-MPS policy for tests and training.
- [x] Record environment creation and verification commands in README.

### 1.4 Environment gate acceptance

- [x] Unreal editor and matching Game Animation Sample open successfully.
- [x] Minimal C++ plugin target compiles successfully.
- [x] Python 3.12 environment installs reproducibly from committed metadata.
- [x] At least one Python test runs successfully.
- [x] Environment inventory is entered as `FEAS-000` or equivalent.
- [x] Reviewer confirms no undocumented machine dependency blocks reproduction.

## 2. Repository and interface skeleton

### 2.1 Repository layout

- [ ] Create `configs/` for data, model, planner, evaluation, and scenario configs.
- [x] Create `motionworld/data/`.
- [ ] Create `motionworld/models/`.
- [ ] Create `motionworld/planning/`.
- [ ] Create `motionworld/evaluation/`.
- [x] Create `motionworld/protocol/` or an equivalent explicit protocol area.
- [x] Create `tests/unit/`.
- [ ] Create `tests/integration/`.
- [x] Create `scripts/` only for stable reproduction entry points.
- [ ] Create ignored/local `artifacts/`, `results/`, and dataset locations with tracked README/placeholders where useful.
- [x] Create project-specific Unreal plugin/module layout without copying the sample.

### 2.2 Shared typed contracts

- [ ] Define authoritative character state fields and shapes.
- [x] Define nominal internal state fields and shapes.
- [ ] Define local desired-velocity action fields and bounds.
- [ ] Define target state.
- [ ] Define obstacle state, type, radius/extent, position, and velocity.
- [ ] Define observation history item.
- [ ] Define episode metadata.
- [ ] Define planner output and telemetry.
- [ ] Define model feature-schema version.
- [ ] Define units explicitly for every field.
- [ ] Define coordinate frame explicitly for every vector.
- [ ] Add finite-value and shape validation.
- [ ] Add serialization round-trip tests.

### 2.3 Skeleton gate

- [x] Python imports succeed without circular dependencies.
- [ ] Empty/default typed objects cannot silently represent valid runtime data.
- [ ] Tests reject incorrect dimensions, units/version tags, and non-finite values.
- [ ] Candidate can draw the Unreal/Python system boundary from memory.
- [ ] Commit the tested repository and type skeleton.

## 3. Theory proof of concept

### 3.1 Coordinate transformations

- [ ] Explain world/global coordinates versus character-local coordinates.
- [x] Write the 2D yaw rotation matrix in `THEORY.md`.
- [x] Derive why global-to-local uses the transpose/inverse rotation.
- [x] Record local forward at 0 degrees in the theory/tests.
- [x] Record local forward at 90 degrees under Unreal X-forward/Y-right conventions.
- [x] Implement local-to-global vector conversion.
- [x] Implement global-to-local vector conversion.
- [x] Implement point conversion separately from vector conversion if translation is involved.
- [x] Test 0, 90, 180, and -90 degrees.
- [x] Test random round trips.
- [x] Test radians/degrees misuse is caught or impossible at the interface.
- [x] Reviewer verifies signs against an Unreal observation.
- [ ] Examiner asks candidate to derive one conversion on a blank page.

### 3.2 Minimal bounded velocity oracle

- [ ] Explain desired velocity, acceleration bound, timestep, and integration.
- [ ] Reproduce the scalar hand calculation currently in `THEORY.md`.
- [x] Implement the deliberately simple bounded-acceleration oracle.
- [x] Test zero current/zero desired velocity.
- [x] Test acceleration below the clamp.
- [x] Test acceleration at the clamp.
- [x] Test deceleration to zero without overshoot.
- [x] Test direction reversal.
- [x] Test trapezoidal position integration by hand.
- [x] Clearly label this module as a teaching oracle, not the final nominal model.

### 3.3 Deterministic 2D backend

- [x] Define ground-truth toy state and hidden state.
- [x] Define deterministic reset from a seed.
- [x] Define legal action range.
- [x] Implement a transparent hidden lag/spring mismatch.
- [x] Implement a timed gate analytically.
- [x] Implement optional deterministic push intervention.
- [x] Log complete toy episodes in the same conceptual schema as Unreal.
- [x] Prove identical seed/actions produce identical trajectories.
- [x] Plot nominal versus toy ground truth before learning.
- [x] Mark every artifact `SYNTHETIC / NOT UNREAL EVIDENCE`.

### 3.4 Theory proof gate

- [x] Coordinate tests pass.
- [x] Hand-oracle dynamics tests pass.
- [x] Toy backend determinism test passes.
- [ ] Candidate explains why the toy backend exists and what it cannot prove.
- [x] Reviewer confirms no toy result is phrased as engine evidence.
- [ ] Commit the theory proof as a coherent tested slice.

## 4. Unreal feasibility

### 4.1 Version-matched API/source audit

- [x] Locate the exact Game Animation Sample character class/Blueprint.
- [x] Locate the exact Mover component and Smooth Walking mode used by the sample.
- [x] Locate the desired-velocity or movement-input control surface.
- [x] Locate where movement parameters live.
- [x] Locate post-movement tick/update hooks.
- [x] Locate authoritative velocity and angular-velocity access.
- [x] Locate collision/contact events.
- [x] Locate animation-root transform access through Mover's primary skeletal visual.
- [ ] Locate toe transforms and reliable contact labels before claiming foot sliding.
- [x] Verify every selected API in version-matched official docs or engine source.
- [x] Record source file/class/member names and engine version in `DECISIONS.md`.
- [x] Compile immediately after the smallest C++ change.

### 4.2 Unreal project-specific components

- [ ] Add `AMotionWorldArenaManager` or documented equivalent.
- [ ] Add `UMotionWorldAgentComponent` or documented equivalent.
- [ ] Add `AMotionWorldMovingObstacle` or documented equivalent.
- [ ] Add `UMotionWorldDebugComponent` or documented equivalent.
- [ ] Keep responsibilities separated rather than creating one monolithic actor.
- [x] Ensure the behavior-free module uses only `Core`, `CoreUObject`, `Engine`, and `Mover` dependencies.
- [x] Ensure project source does not hard-code one developer machine path.
- [x] Attach the bridge locally to the playable sample pawn with automation disabled.
- [x] Confirm the attached bridge initializes and preserves human-control behavior.

### 4.3 Programmatic character control

- [x] Implement and strictly compile a bounded world-space command probe; do not confuse it with the final character-local action interface.
- [x] Implement and strictly compile character-local/world planar conversion from authoritative Mover yaw.
- [x] Execute coordinate-frame automation tests in the actual sample: 2 passed, 0 failed/warnings.
- [x] Prove the character-local axes with combined evidence: visible perpendicular forward/right paths at one starting yaw plus executed cardinal and round-trip tests across additional yaws.
- [x] Execute the command-sanitizer automation tests in an actual-sample Editor process: 1 passed, 0 failed/warnings.
- [x] Prove `GetLastInputCmd()` echoes the velocity type and bounded vector.
- [x] Capture a live character-local request resolving through authoritative yaw and echoing the expected world vector.
- [x] Restore the attached bridge to automation disabled after the fixed-command test.
- [x] Apply zero desired velocity and verify the retained packet echo.
- [x] Apply forward desired velocity and retain a causally paired live episode under the consumed command.
- [x] Apply lateral desired velocity and verify the local-right path/echo.
- [ ] Apply diagonal desired velocity.
- [ ] Apply stop command from motion.
- [ ] Apply reverse command from forward motion.
- [ ] Clamp magnitude to active maximum speed.
- [x] Verify action is character-local at the interface.
- [ ] Verify facing-follows-motion behavior for P0.
- [ ] Verify action hold duration is 100 ms at the planner interface.
- [x] Confirm externally commanded movement still drives acceptable sample animation for the feasibility claim.

### 4.4 Authoritative state and tick order

- [x] Select actor/capsule/Mover state as the sole planning ground truth.
- [x] Sample global XY position after movement.
- [x] Sample velocity and convert to declared frame.
- [x] Sample facing in a valid representation.
- [x] Sample angular velocity with declared units.
- [x] Record engine timestamp and step index.
- [x] Prove sampling happens after movement rather than before it.
- [x] Log animation-root transform with a distinct field name.
- [ ] Log toe transforms only as diagnostics.
- [x] Plot actor and animation-root trajectories separately.
- [x] Confirm no code substitutes animation root for actor state.

### 4.5 Deterministic scenario lifecycle

- [x] Define scenario seed ownership.
- [x] Reset actor transform and velocity.
- [x] Reset Mover/controller hidden state as far as the API permits.
- [ ] Reset target.
- [x] Reset gate phase/schedule.
- [x] Reset collision counters.
- [x] Reset episode identity while keeping the global callback sequence monotonic.
- [ ] Reset observation history.
- [ ] Reset planner warm start.
- [x] Run two same-anchor resets and compare verified initial observations.
- [x] Run two same-seed gate schedules and compare trajectories/timestamps.
- [x] Prove no data from the prior episode appears after reset.

### 4.6 Timed gate and events

- [x] Create a gate with an explicit deterministic schedule.
- [x] Expose gate position, velocity, size/radius, motion type, and phase.
- [x] Log gate schedule metadata.
- [x] Detect character/gate collision consistently.
- [x] Detect successful crossing in the pure event contract and reject false-success files.
- [x] Detect timeout in the pure event contract and reject pre-deadline timeout files.
- [x] Record termination reason in each terminal row and the reconciled footer summary.
- [ ] Validate the scenario at slow/manual speed before automated collection.

### 4.7 Feasibility evidence and gate

- [ ] Record a short video of programmatic movement.
- [x] Record a deterministic character-reset comparison.
- [x] Preserve complete in-memory episode lifecycle evidence.
- [x] Validate every required episode field.
- [x] Save actor-versus-animation-root trace.
- [x] Enter `FEAS-001` with version, commit, seed, commands, and artifacts.
- [x] Reviewer checks tick phase, frames, units, stale state, and reset leakage.
- [x] Candidate answers: “Which transform is authoritative, at what tick point, and why?”
- [x] Candidate answers: “How do you know hidden controller state was reset?”
- [x] Gate passes: external control, authoritative state, reset, events, and logging are all reliable.
- [x] Retain the Game Animation Sample path; fallback was not required at this checkpoint.

## 5. Unreal-Python protocol and safety

### 5.1 Observation packet

- [x] Define protocol version.
- [x] Include episode ID.
- [x] Include monotonically increasing sequence number.
- [x] Include engine timestamp.
- [x] Include controller mode.
- [x] Include explicit state-source label.
- [x] Include character state and declared units.
- [ ] Include contact state only if its semantics are reliable.
- [x] Include target state.
- [x] Include bounded nearest-obstacle list and validity information (amended to one exact bounded timed-gate context for P0).
- [x] Include previous applied action.
- [x] Include movement parameters as metadata.
- [x] Reject missing, wrong-type, non-finite, or unsupported-version fields.

### 5.2 Action packet

- [x] Echo protocol version, episode ID, and observation sequence.
- [x] Include desired velocity with units.
- [x] Include planner latency measured consistently.
- [x] Include selected controller/model identifier.
- [x] Optionally include prediction telemetry without making it control-critical.
- [x] Reject wrong episode.
- [x] Reject stale sequence.
- [x] Reject malformed or non-finite action.
- [x] Clamp velocity again inside Unreal.

### 5.3 Timeout behavior

- [x] Define one-response deadline.
- [x] Hold the last safe action after one missed response.
- [x] Stop after three consecutive misses.
- [x] Clear missed-response state after valid recovery.
- [ ] Test Python service absent at startup.
- [ ] Test service disappears during movement.
- [ ] Test delayed stale response arrives after reset.
- [ ] Test malformed response during movement.
- [ ] Confirm no failure mode produces runaway motion.

### 5.4 Protocol gate

- [x] Serialization tests pass on Python side.
- [x] Parsing/validation tests pass on Unreal side.
- [ ] Unreal observation reaches Python and a valid action returns.
- [x] Wrong-episode and stale packets are demonstrably rejected in bounded automation; live injection remains in Recovery 3.4.
- [ ] Safe stop is demonstrated.
- [x] Commit protocol as an independently tested slice; live safety closure remains Gate R2.

## 6. Faithful nominal movement model

### 6.1 Understand and map the model

- [ ] Explain why a cheap predictor is required for hundreds of CEM futures.
- [x] Identify known Smooth Walking visible and internal state.
- [x] Map every nominal parameter to an engine/sample setting or documented approximation.
- [ ] Explain acceleration versus deceleration selection.
- [ ] Explain directional acceleration during turns.
- [ ] Explain turn response.
- [ ] Explain velocity spring smoothing and its intermediate state.
- [ ] Explain facing/rotation spring dynamics.
- [ ] Explain why a push may require synchronization of visible and internal spring state.
- [ ] Explain why the movement model is substepped.

### 6.2 Implement state and synchronization

- [ ] Define authoritative planning state `s`.
- [x] Define nominal internal state `z`.
- [ ] Define initialization at episode reset.
- [ ] Define synchronization after each real Unreal observation.
- [x] Decide what happens when internal Mover state is not exposed.
- [x] Record whether missing state is estimated, reconstructed, or accepted as nominal mismatch.
- [ ] Prevent residual history from being used to conceal an intentionally omitted known equation.

### 6.3 Implement nominal transition

- [x] Implement acceleration/deceleration branch.
- [x] Implement directional acceleration.
- [x] Implement turn response.
- [x] Implement intermediate target velocity.
- [x] Implement velocity spring update.
- [x] Implement facing/rotation update.
- [x] Integrate position using declared convention.
- [x] Normalize or wrap orientation consistently.
- [ ] Compose six verified substeps for one 100 ms macro step.
- [ ] Support batched candidate/horizon dimensions without changing scalar semantics.

### 6.4 Nominal unit tests

- [x] Zero state plus zero action remains stationary.
- [x] Forward acceleration matches hand/reference calculation.
- [x] Deceleration approaches stop without unstable overshoot.
- [x] Reverse command uses the intended branch.
- [x] Ninety-degree desired direction turns with correct sign.
- [x] Speed limit is respected.
- [x] Facing remains valid.
- [ ] Scalar and batch-one outputs match.
- [ ] Six substeps match six repeated scalar calls.
- [ ] One 100 ms step is compared against six substeps and the difference is documented.
- [ ] Push/state resynchronization test passes under chosen policy.
- [ ] CPU and selected accelerator results are within tolerance.

### 6.5 Nominal empirical validation

- [x] Align action at time `t` with correct next state at `t+1`; live episode 1601 accepted all 922 adjacent pairs with zero rejection.
- [x] Compare nominal and Unreal one-step transitions; schema-v4 episode 4001 reproduces 104 non-collision rows to micro-numerical tolerance without manual facing/max-speed inputs.
- [x] Compare recursive errors at 0.5, 1.0, and 1.5 s.
- [x] Compile and automation-test the explicit -179.5-degree antipodal facing tie-break.
- [x] Live-validate that the tie-break removes the isolated angular rollout spike.
- [ ] Stratify free motion, acceleration, stopping, reversing, turning, contact, and post-push.
- [x] Plot position, velocity, facing, and angular-velocity error separately.
- [x] Inspect systematic bias rather than only aggregate mean.
- [x] Enter `NOM-001` hand/reference validation.
- [x] Enter `NOM-002` real Unreal mismatch study using accepted schema-v5 episode 4301.
- [x] Compare the retrospective equation oracle with a causal current-snapshot/held-parameter
  baseline; `NOM-CAUSAL-001` isolates future parameter scheduling as a decision-relevant mismatch.

### 6.6 Nominal gate

- [ ] Reviewer confirms the nominal is not deliberately weak.
- [x] Reviewer confirms causal evaluation uses no future state or parameter/preparation snapshot;
  future recorded actions are used only as known candidate interventions in open-loop replay.
- [ ] Candidate derives one transition and explains substepping.
- [ ] Candidate explains every known, hidden, and estimated state variable.
- [x] Meaningful decision-relevant residual structure exists, or a negative result is recorded;
  NOM-002 records the negative post-observation result and forbids learning the unforeseeable kick.
- [ ] Commit nominal model, tests, plots, and decision record.

## 7. Dataset collection and validation

### 7.1 Episode schema

- [x] Include episode, scenario, seed, timestamp, and step index.
- [x] Include authoritative character state.
- [x] Include next authoritative state.
- [x] Include the exact echoed requested velocity and orientation inputs plus Simple Walking's versioned max-speed preparation.
- [ ] Include target state.
- [x] Include analytically revalidated timed-gate obstacle states.
- [x] Include collision flag/count.
- [x] Include and live-validate an external velocity perturbation as a schema-v5 evaluation-only
  label; episode 4301 contains exactly one source-aligned event row.
- [x] Include controller parameters with explicit post-step observation semantics.
- [x] Include both endpoints of the five-field known Smooth Walking internal context.
- [x] Reject missing, invalid, wrong-version, or state-misaligned nominal context.
- [x] Preserve schema-v1/v2 reader compatibility without fabricating missing context.
- [x] Validate one live Unreal schema-v3 episode end to end in the independent Python loader.
- [x] Validate one uniquely identified live schema-v4 episode, including max-speed source/value and facing intent, end to end.
- [x] Enforce and manifest-check globally unique episode identity across accepted files.
- [x] Include termination reason.
- [x] Include state-source and schema-version labels.
- [ ] Include animation-root/toe diagnostics in distinct optional fields.

### 7.2 Collection policy

- [x] Implement and unit-test a default-off deterministic varied-action schedule.
- [x] Validate the schedule in live episode 4101 and audit realized action/facing coverage.
- [ ] Implement goal-directed action generator.
- [ ] Implement random piecewise-constant velocities.
- [ ] Implement near-contact/boundary-following collection.
- [x] Implement stops, reversals, and rapid turns.
- [x] Implement and live-validate a default-off controlled external velocity perturbation; episode
  4301 records the requested kick, realized next state, and 2.0-second recovery interval.
- [x] Record realized action-mixture proportions for every accepted train/validation split.
- [x] Verify bounded free-space actions cover stop, cardinal, diagonal, and 0-160 cm/s requests.
- [ ] Ensure free-space data does not dominate all other strata.
- [ ] Stop collection based on validation saturation rather than an arbitrary large count.

### 7.3 Dataset validation

- [x] Reject duplicate/non-increasing transition identities within one episode file.
- [x] Reject non-monotonic timestamps or state/Mover step indices within accepted rows.
- [x] Reject sequence gaps unless explicitly recorded.
- [x] Reject non-finite states/actions.
- [ ] Validate units and plausible ranges.
- [x] Validate action/next-state temporal alignment.
- [x] Validate nominal-context/state alignment and consecutive hidden endpoints.
- [x] Validate duplicated completed-step parameters equal the next finalized snapshot.
- [x] Validate duplicated completed-step input preparation equals the next snapshot and facing target matches orientation intent.
- [x] Validate one file has one episode identity and no row crosses its boundary.
- [x] Validate no residual window crosses episode termination or joins two episodes.
- [x] Produce coverage counts/histograms for requested direction, requested/executed speed, turns,
  stops, parameter signatures, contact, external perturbations, and variable timestep; report the
  zero-contact/zero-perturbation gaps explicitly.

### 7.4 Split discipline

- [x] Freeze pre-training train/validation/test episode IDs and schedule configurations in the tested
  collection plan.
- [x] Finalize train/validation accepted-file manifest with every raw filename and SHA-256; pending
  test files remain unopened.
- [x] Split complete episodes, never individual transitions.
- [ ] Separate scenario seeds.
- [ ] Separate obstacle layouts.
- [ ] Define represented/held-out movement regimes.
- [x] Freeze final test episode IDs/configurations before model selection: 5301 and 5302.
- [ ] Fit normalization only on training data.
- [ ] Store normalization with schema and checkpoint.
- [x] Add accepted-file identity/hash/rejected-attempt overlap and split-leakage tests after
  collection completes.
- [x] Hash manifest, coverage report, Markdown summary, and coverage plot.

### 7.5 Dataset gate

- [x] Coverage report and plot are inspected manually.
- [x] Leakage/overlap tests pass, including a test proving pending test files are not opened.
- [x] Reviewer checks temporal alignment and normalization leakage.
- [ ] Candidate explains why adjacent-transition splitting is invalid.
- [x] Dataset-audit regeneration command is documented without embedding a private absolute path.
- [x] Commit schema, validators, manifests, and coverage report without raw licensed/private data
  as `311ea7b`.

## 8. Residual model

### 8.1 Residual contract

- [x] Define `delta_target = difference(Unreal_next, nominal_next)`.
- [x] Freeze output order and physical units: local position cm, local velocity cm/s, wrapped yaw
  radians, and yaw rate radians/s.
- [x] Fit numeric normalization scales from training episodes only; never from validation/test rows.
- [x] Choose a shortest-path scalar yaw correction in radians.
- [x] Define `compose(nominal, residual)`.
- [x] Prove zero residual returns the exact nominal state, including bit-for-bit scalar identity.
- [x] Exclude goal/target features from character dynamics for P0.
- [x] Exclude simple obstacle geometry unless a documented contact-context ablation justifies it.
- [x] Define each of four chronological observations as the same frozen 28-value causal step query.
- [x] Implement and test how imagined four-step history advances recursively.
- [x] Exclude absolute position, absolute heading, episode time, contact labels, and other features that
  cannot advance causally; retain only the known per-step `delta_time_s`.
- [x] Define the causal baseline boundary: current finalized state/context/parameters plus candidate
  actions are available; later finalized states, parameter snapshots, and event labels are forbidden.

### 8.2 Window construction

- [x] Create current/no-history examples.
- [x] Create four-observation-history examples.
- [ ] Create 1.2-1.5 second target horizons.
- [x] Prevent windows from crossing episodes and reject duplicate episode IDs.
- [x] Prevent features from including future actions, states, completed-step parameters, or hidden
  event labels.
- [ ] Mask or reject incomplete horizons consistently.
- [x] Test the 28-value step and 112-value history order against a frozen schema.
- [x] Test feature and target normalization/denormalization round trips and exact zero-target
  preservation.

### 8.3 Model implementation

- [x] Implement no-history MLP.
- [x] Implement history MLP.
- [x] Use initial hidden widths 256, 256, 128 with SiLU.
- [x] Confirm total parameter count is below approximately 500K: 106,886 no-history and 128,390
  four-history parameters.
- [x] Omit LayerNorm initially; add it only if training-instability evidence justifies it.
- [x] Initialize the final residual layer to exact zero.
- [ ] Add residual clipping only from training-set statistics.
- [x] Test batch/horizon-prefix shape, CPU device, float64 dtype, and gradient behavior.
- [x] Test deterministic initialization and one optimizer step under a fixed seed.

### 8.4 Recursive training

- [x] Implement recursive rollout using the same transition interface intended for planning.
- [x] Implement per-component state error.
- [x] Implement and hand-check normalized per-component Huber loss for the fixed one-step baseline.
- [ ] Implement discounted multi-step loss.
- [x] Implement a declared normalized residual-magnitude regularizer.
- [x] Log one-step and recursive validation separately.
- [x] Never use teacher forcing for the reported recursive evaluation.
- [x] Save training config, seed, normalization, schema, commit, and checkpoint hash.
- [x] Save learning curves and failure diagnostics.

### 8.5 Residual evaluation

- [x] Evaluate nominal baseline.
- [x] Evaluate residual without history.
- [x] Evaluate residual with four-step history.
- [x] Report 0.5, 1.0, and 1.5 s errors.
- [x] Report position, velocity, facing, and angular-velocity separately.
- [ ] Report free-space, near-contact, post-push, and held-out-setting strata.
- [x] Plot recursive error growth.
- [x] Plot residual magnitude and outliers.
- [x] Inspect whether gains come only from one easy regime; gains concentrate around the declared
  parameter-change stratum, while the near-exact stable nominal rows expose learned-model cost.
- [ ] Inspect whether history gains persist after controlling for model size.
- [x] Enter `RES-001` and `RES-002` with raw artifacts.

### 8.6 Residual gate

- [x] Reviewer checks episode leakage, future leakage, teacher forcing, checkpoint selection, and facing validity.
- [ ] Candidate explains residual versus full-model learning.
- [ ] Candidate explains MLP versus GRU/Transformer choice.
- [ ] Candidate explains why history cannot predict a future random push.
- [ ] Candidate explains recursive compounding error and multi-step loss.
- [x] Held-out recursive prediction improves in a decision-relevant stratum, and the weaker history
  result is preserved.
- [x] Commit model, training, evaluation, and documentation updates as `249f39e`.

## 9. Cross-Entropy Method planner

### 9.1 Understand CEM and MPC

- [ ] Candidate explains candidate action sequences.
- [ ] Candidate explains action knots and horizon expansion.
- [ ] Candidate derives elite mean and variance updates.
- [ ] Candidate explains distribution momentum.
- [ ] Candidate explains warm start.
- [ ] Candidate explains why only the first 100 ms is executed.
- [ ] Candidate explains CEM versus gradient planning.

### 9.2 CEM implementation

- [x] Define exact tensor shapes for candidates, knots, steps, and action dimensions.
- [x] Sample from fixed-seed Gaussian distribution.
- [x] Expand knots to 100 ms planning/action steps; dynamics substeps are a separate contract.
- [x] Clamp/project actions into the legal planar speed ball, including a literal floating-point
  boundary guarantee.
- [x] Batch rollout all candidates, with independent cloned hidden state per candidate and three
  nominal/residual dynamics substeps per 100 ms planning step.
- [x] Select lowest-cost elites.
- [x] Update mean and population variance.
- [x] Apply variance floor before and during optimization.
- [x] Apply configured momentum.
- [x] Repeat configured iterations.
- [x] Return first action and diagnostic best trajectory.
- [x] Shift previous solution for warm start.
- [x] Handle NaN/Inf with safe zero-action fallback.

### 9.3 CEM tests

- [x] Fixed seed produces identical candidates and output.
- [x] Hand-computed elite mean/variance test passes.
- [x] Known quadratic toy optimum is recovered.
- [x] Bounds are always respected.
- [x] Zero/small variance remains stable.
- [x] Warm-start shift is correct.
- [x] Lowest rather than highest cost is selected.
- [x] Batch and scalar cost ordering agree.
- [x] Visualize mean/candidate convergence by iteration.
- [x] Enter `CEM-001`.

### 9.4 Planning cost

- [x] Implement terminal goal-distance term independently.
- [x] Implement swept analytic collision indicator independently.
- [x] Implement analytic clearance penalty independently.
- [x] Implement action first-difference term independently.
- [x] Implement action second-difference term independently.
- [x] Propagate scripted obstacle motion analytically at every model boundary.
- [x] Include capsule/obstacle geometry and safety margin explicitly.
- [x] Test each term's sign and units.
- [x] Test zero-cost or known-cost hand cases.
- [x] Plot each component for representative trajectories.
- [x] Record initial weights as provisional dimensional hypotheses, not truths.
- [x] Keep final test episodes 5301/5302 sealed while freezing the offline pilot weights.

### 9.5 Fair nominal/residual MPC

- [ ] Reactive controller exists only as visual context.
- [x] Nominal and residual MPC use identical initial state.
- [x] Use identical random noise and identical physical candidates on iteration one; record that
  later adaptive candidate batches diverge after model-specific elite selection.
- [x] Use identical horizon, knots, candidate count, elite count, and iterations.
- [x] Use identical cost implementation and weights.
- [x] Use identical obstacle information and propagation.
- [x] Use identical action constraints and compute policy.
- [x] Only character transition model differs.
- [x] Assert fairness-critical config equality in code/tests.

### 9.6 Planner gate

- [x] Deterministic CEM tests pass.
- [x] Cost component tests pass.
- [x] Nominal and residual controllers consume the same first-iteration candidate tensor.
- [ ] Both remain stable in obstacle-free control.
- [x] Reviewer searches for exploitation through bounds, costs, and model error; OFFPLAN-001 finds
  severe cross-model disagreement and therefore blocks any control-success claim before Unreal.
- [ ] Candidate performs blank-page CEM explanation.
- [x] Commit CEM, costs, fairness assertions, and the reproducible OFFPLAN-001 plot/artifact.

## 10. Live Unreal MPC integration

### 10.1 Runtime loop

- [ ] Receive one authoritative observation at 10 Hz.
- [ ] Validate episode/sequence/version.
- [ ] Synchronize nominal internal state.
- [ ] Update real observation history.
- [ ] Construct candidate actions.
- [ ] Roll nominal or residual futures.
- [ ] Compute analytic costs.
- [ ] Select first desired-velocity action.
- [ ] Return action before deadline.
- [ ] Apply/clamp action in Unreal.
- [ ] Repeat after the next observation.

### 10.2 Reset and controller switching

- [ ] Switch reactive/nominal/residual modes live.
- [ ] Clear history on reset.
- [ ] Clear CEM warm start on reset.
- [ ] Clear nominal hidden state on reset.
- [x] Clear network/service episode state on reset.
- [x] Ensure controller switch does not reuse incompatible stale state.
- [ ] Verify same-seed left/right agents start identically.

### 10.3 Counterfactual pause mode

- [ ] Pause from one authoritative state.
- [ ] Generate forward candidate future.
- [ ] Generate left candidate future.
- [ ] Generate right candidate future.
- [ ] Generate stop candidate future.
- [ ] Display nominal and corrected trajectories together.
- [ ] Optionally execute one selected intervention.
- [ ] Compare its actual Unreal trajectory.
- [ ] Label prediction horizon and seed.

### 10.4 Live integration gate

- [ ] Nominal MPC controls the live character.
- [ ] Residual MPC controls the live character.
- [ ] Both share the fairness-critical planner inputs.
- [ ] Reset produces no state leakage.
- [ ] Service loss produces safe stop.
- [ ] Paused futures are repeatable from the same state.
- [ ] Reviewer checks deadline, stale HUD, state mismatch, and reset behavior.
- [ ] Commit live integration and safety tests.

## 11. Scenario implementation

### 11.1 Timed gate

- [ ] Predefine gate geometry and schedule without looking at test outcomes.
- [ ] Ensure acceleration/timing error can affect feasibility naturally.
- [ ] Avoid an obviously artificial scenario designed only for residual victory.
- [ ] Define success, collision, timeout, clearance, and time-to-goal metrics.
- [ ] Validate same schedule for all controllers.
- [ ] Save exact scenario config and seeds.

### 11.2 External push recovery

- [x] Predefine velocity-kick direction, magnitude, and time: world +Y, 250 cm/s, at 1.5 s.
- [ ] Apply identical impulse schedule to compared controllers.
- [x] Begin evaluation on the exact event-causing transition and stratify every later row.
- [x] Do not claim the model predicts the push before it occurs; the label is evaluation-only.
- [ ] Define trajectory-error recovery threshold.
- [ ] Define recovery time metric.
- [ ] Compare nominal, no-history residual, and history residual prediction.
- [ ] Compare resulting replanning/control recovery.

### 11.3 Held-out movement setting

- [ ] Select acceleration, smoothing, turn response, or related parameter before final testing.
- [ ] Define training-support range.
- [ ] Define in-range held-out values.
- [ ] Define outside-range OOD values.
- [ ] Clarify whether the parameter is visible to nominal/model/planner.
- [ ] Distinguish parameter-conditioned generalization from robustness to unobserved mismatch.
- [ ] Preserve degradation and failure results.

### 11.4 Optional crossing obstacle - P1

- [ ] Begin only after timed gate, push, and held-out scenario gates pass.
- [ ] Use known scripted motion and analytic propagation.
- [ ] Do not add a learned collision head for simple known geometry.
- [ ] Drop immediately if it threatens evaluation or packaging.

## 12. Experiment freeze and causal evaluation

### 12.1 Freeze manifest

- [ ] Freeze dataset split manifests.
- [ ] Freeze model checkpoint and normalization.
- [ ] Freeze feature-schema version.
- [ ] Freeze planner config and cost weights.
- [ ] Freeze scenario definitions.
- [ ] Freeze test seeds.
- [ ] Freeze metric definitions.
- [ ] Record Git commit and hardware/software.
- [ ] Hash every frozen artifact.
- [ ] Do not revise after viewing final test outcomes without creating a new labeled experiment family.

### 12.2 Paired controller runs

- [ ] Run reactive controller on fixed seeds.
- [ ] Run nominal MPC on the same seeds.
- [ ] Run residual MPC on the same seeds.
- [ ] Confirm identical valid-pair counts.
- [ ] Retain failed/invalid episodes with explicit reason.
- [ ] Avoid survivorship filtering.
- [ ] Save per-episode raw metrics.

### 12.3 Prediction metrics

- [ ] Position error at 0.5, 1.0, and 1.5 s.
- [ ] Velocity error at 0.5, 1.0, and 1.5 s.
- [ ] Facing error at 0.5, 1.0, and 1.5 s.
- [ ] Angular-velocity error at 0.5, 1.0, and 1.5 s.
- [ ] Report nominal/no-history/history.
- [ ] Report every required data stratum.

### 12.4 Task metrics

- [ ] Success rate.
- [ ] Collision rate/count.
- [ ] Time to goal.
- [ ] Minimum clearance.
- [ ] Push-recovery time.
- [ ] Selected-action disagreement between nominal and residual MPC.
- [ ] Identify whether disagreement occurs for the predicted reason.

### 12.5 Runtime metrics

- [x] Warm up the vectorized offline runtime path with three calls per controller.
- [x] Measure the complete offline planning call, not model-only latency; Unreal transport and
  application remain outside this bounded benchmark.
- [x] Report median.
- [x] Report p95.
- [x] Report missed 100 ms deadlines.
- [x] Report exact candidates, elites, iterations, knots, horizon, device, and threading.
- [x] Run a prospectively frozen validation-only budget/quality sweep; retain the negative result
  that no reduced budget passes both 100 ms p95 and the 10% predicted-cost-regret gate.
- [x] Run a prospectively frozen residual-width sweep; retain the negative result that no smaller
  model passes recursive, reference-cross-planning, and 100 ms p95 gates together.
- [ ] Preserve cold-start latency separately rather than hiding it.

### 12.6 Paired statistics

- [ ] Choose paired estimand before computing final interval.
- [ ] Bootstrap paired episode differences.
- [ ] Use deterministic bootstrap seed.
- [ ] Report confidence interval.
- [ ] Report episode count, median, and IQR.
- [ ] Avoid uncorrected storytelling across many metrics.
- [ ] State statistical uncertainty separately from practical effect size.

### 12.7 Planner exploitation

- [ ] Record predicted return for every selected plan.
- [ ] Record realized return after execution.
- [ ] Compute selected-plan prediction gap.
- [ ] Compute gap for random in-distribution trajectories.
- [ ] Compare optimism of selected versus random plans.
- [ ] Inspect extreme selected plans visually.
- [ ] Record whether action bounds or OOD states are being exploited.
- [ ] Enter `EXPLOIT-001`.

### 12.8 Causal claim audit

- [ ] Show a specific nominal prediction error.
- [ ] Show residual correction for that same error.
- [ ] Show nominal and residual planners select different actions.
- [ ] Show changed action improves same-seed Unreal execution.
- [ ] Rule out different costs, candidates, seeds, budgets, or obstacle information.
- [ ] State alternative explanations.
- [ ] If any link is absent, do not make the full positive claim.

### 12.9 Final evaluation gate

- [ ] Complete `CTRL-001`, `CTRL-002`, `OOD-001`, `EXPLOIT-001`, and `RUNTIME-001` as applicable.
- [ ] Reviewer audits seed selection, tuning history, pair construction, and missing episodes.
- [ ] Candidate states the weakest defensible claim.
- [ ] Candidate explains whether better prediction produced better control.
- [ ] Negative results and failure boundaries are retained.
- [ ] Commit frozen manifests, evaluation code, tables, and plots.

## 13. Debug visualization and demo UX

### 13.1 Trajectory rendering

- [ ] Faint gray candidate trajectories.
- [ ] Bright green selected trajectory.
- [ ] Blue nominal character prediction.
- [ ] Orange residual-corrected prediction.
- [ ] Yellow actual authoritative execution.
- [ ] Cyan obstacle velocity vectors.
- [ ] Purple goal marker.
- [ ] Clear time horizon/timestep interpretation.
- [ ] Selected path visually dominates candidates.
- [ ] Nominal, corrected, and actual paths are visible together.

### 13.2 HUD

- [ ] Active controller.
- [ ] Scenario and seed.
- [ ] Active movement mismatch setting.
- [ ] Prediction error at declared horizon.
- [ ] Selected desired velocity.
- [ ] Planning latency.
- [ ] Missed-deadline count.
- [ ] Collision count.
- [ ] Success/termination state.
- [ ] Ensure metrics update from the current episode/sequence only.

### 13.3 Live controls

- [ ] Select target.
- [ ] Switch reactive/nominal/residual controllers.
- [ ] Reset scenario.
- [ ] Load next scenario.
- [ ] Apply external impulse.
- [ ] Adjust selected mismatch.
- [ ] Pause and inspect futures.
- [ ] Toggle trajectories.
- [ ] Toggle metrics overlay.
- [ ] Print controls in runbook and optionally on screen.

### 13.4 Animation-quality diagnostics

- [ ] Requested planner path versus authoritative actor path.
- [x] Authoritative actor path versus animation-root path.
- [ ] Facing relative to requested and executed motion.
- [ ] Animation-root acceleration/jerk if reliable.
- [ ] Toe/foot sliding only if contact data is reliable.
- [x] Avoid modifying animation/IK merely to improve these metrics during P0.
- [x] State clearly that MotionWorld does not generate poses.

### 13.5 Demo gate

- [ ] Same-seed nominal-left/residual-right comparison works.
- [ ] Reset works three times consecutively.
- [ ] Primary causal episode is reproducible.
- [ ] Honest failure episode is reproducible.
- [ ] HUD shows no stale or contradictory values.
- [ ] Service-failure recovery works during rehearsal.
- [ ] Record 60-90 second primary fallback video.
- [ ] Keep an unedited evidence recording where appropriate.

## 14. Packaging and reproducibility

### 14.1 Repository package

- [x] README begins with claim, evidence level achieved, and limitations.
- [ ] Document exact prerequisites.
- [ ] Document Unreal Engine and Game Animation Sample acquisition.
- [ ] Document project-specific source integration.
- [x] Document Python environment creation.
- [x] Document test commands.
- [ ] Document data-generation command and schema.
- [ ] Document training command.
- [ ] Document evaluation command.
- [ ] Document demo launch order.
- [x] Include frozen configs and seed manifests.
- [x] Include normalization/schema/checkpoint hashes.
- [x] Include result tables and plots.
- [x] Include license and provenance notes.
- [x] Exclude licensed sample assets and generated engine directories.
- [x] Exclude raw/private data.

### 14.2 Artifact package

- [x] Architecture diagram.
- [ ] Main paired result table.
- [x] Recursive prediction-error graph.
- [ ] One causal trace.
- [ ] One OOD/failure graph.
- [x] Runtime/latency summary.
- [ ] 60-90 second demo video.
- [ ] Prerecorded fallback video stored locally.
- [x] Offline fallback runbook; live-demo runbook remains blocked by absent live MPC.
- [x] Exact package/test reproduction commands.
- [x] Artifact manifest with sizes and hashes.

### 14.3 Reproduction check

- [ ] Test from a clean worktree or clean clone.
- [ ] Recreate Python environment from lockfile.
- [x] Run 368 unit tests successfully on the packaging worktree.
- [ ] Run deterministic synthetic smoke experiment.
- [x] Validate configs and manifests load through automated tests.
- [x] Validate package contains no absolute developer-only paths in its eight required files.
- [x] Validate all eight required local artifacts exist, are nonempty, and are hashed.
- [ ] Validate fallback video plays offline.
- [ ] Record deviations that require local Unreal sample installation.

### 14.4 Release gate

- [ ] Working tree is clean.
- [x] Tests pass (368/368 before the package/evidence commit).
- [x] `git diff --check` passes before the package/evidence commit.
- [ ] No secrets or oversized accidental files are tracked.
- [ ] Documentation and actual commands agree.
- [ ] Obsidian contains final resume-ready handoff.
- [ ] Create release candidate commit/tag only after checklist review.

## 15. Interview mastery and defense

### 15.1 Thirty-second explanation

- [ ] Define MotionWorld in one sentence.
- [ ] Explain why the nominal model is cheap and faithful.
- [ ] Explain what the residual learns.
- [ ] Explain how CEM/MPC uses predictions.
- [ ] State the causal acceptance rule.
- [ ] Complete within 30-40 seconds without jargon overload.

### 15.2 Ninety-second demo narrative

- [ ] State problem and hypothesis.
- [ ] Identify blue/orange/yellow trajectories.
- [ ] Show same-seed fairness.
- [ ] Show the prediction correction.
- [ ] Show the action difference.
- [ ] Show the actual outcome.
- [ ] State latency and one limitation.

### 15.3 Five-minute technical narrative

- [ ] Research question and scope.
- [ ] Unreal/Python architecture.
- [ ] Authoritative versus animation state.
- [ ] Faithful nominal dynamics.
- [ ] Residual/history architecture and loss.
- [ ] CEM and cost.
- [ ] Dataset split and leakage controls.
- [ ] Prediction and control results.
- [ ] Runtime, failure boundary, and weakest claim.

### 15.4 Daniel-style examination

- [ ] Why desired velocity?
- [ ] How does Smooth Walking model acceleration, turns, and smoothing?
- [ ] Why is the nominal baseline fair?
- [ ] What internal state does the spring carry?
- [ ] What happens to that state after a push?
- [ ] Why substep?
- [ ] Which transform is authoritative?
- [ ] Why can actor and animation root diverge?
- [ ] How do you measure animation friendliness?
- [ ] Why not generate poses or use AnimGen?
- [ ] What is the C++/runtime ownership boundary?

### 15.5 Viktoriia-style examination

- [ ] Why is this a world model?
- [ ] How do you prove action adherence rather than correlation?
- [ ] What information is privileged and how is it used?
- [ ] How do you prevent episode and normalization leakage?
- [ ] Why residual instead of full transition?
- [ ] Why MLP instead of GRU/Transformer?
- [ ] Why does history help?
- [ ] Can it predict an unpredictable push?
- [ ] Does lower prediction error imply better control?
- [ ] How do you detect planner exploitation?
- [ ] What happens OOD?
- [ ] What is the weakest evidence-supported claim?

### 15.6 Blank-page derivations

- [ ] Coordinate rotation and inverse.
- [ ] Nominal velocity/position update.
- [ ] Residual target and composition.
- [ ] Recursive rollout.
- [ ] Huber loss.
- [ ] Weighted multi-step loss.
- [ ] CEM elite mean/variance/momentum.
- [ ] MPC cost terms and units.
- [ ] Episode-safe split logic.
- [ ] Paired bootstrap concept.
- [ ] Median versus p95 latency.

### 15.7 Coding/debug rehearsal

- [ ] Implement/test one coordinate conversion without scaffolding.
- [ ] Diagnose one timestep bug.
- [ ] Diagnose one episode-window leakage bug.
- [ ] Implement a small residual MLP forward pass.
- [ ] Implement one CEM elite update.
- [ ] Parse/reject one stale packet in Python or C++.
- [ ] Explain complexity and edge cases while coding.

### 15.8 Final rehearsal

- [ ] Run live demo from fresh launch three times.
- [ ] Time the 90-second demonstration.
- [ ] Time the five-minute explanation.
- [ ] Practice fallback when Unreal fails to launch.
- [ ] Practice fallback when Python service fails.
- [ ] Verify offline video, diagram, table, and graph.
- [ ] Stop feature development Friday morning.
- [ ] Fix only demonstrated launch-blocking defects.
- [ ] After any fix, rerun the complete rehearsal.

## 16. Explicitly deferred work

- [ ] ONNX export only after full P0 evidence/package gate.
- [ ] Native Unreal inference only after ONNX and central result.
- [ ] Residual ensemble only after deterministic single-model evidence.
- [ ] Crossing obstacle only after three required scenarios.
- [ ] Reliable foot-sliding metric only with trustworthy contacts.
- [ ] AnimGen integration only after interview package is complete.
- [ ] Language/style controls are out of scope.
- [ ] Visual/video world model is out of scope.
- [ ] Multiple learned agents are out of scope.
- [ ] Oracle cloned-Unreal planning is out of scope.

Unchecked items in this section are not omissions; they are guarded stretch goals. They should normally remain unchecked for the interview build.

## 17. End-of-work-block checklist

- [ ] Built: record exact files/modules changed.
- [ ] Learned/derived: record candidate-owned concept or equation.
- [ ] Tests/evidence: record commands and artifacts.
- [ ] Reviewer findings: record unresolved scientific/engineering risks.
- [ ] Examiner weakness: record the weakest oral answer.
- [ ] Decisions: update `DECISIONS.md` if material.
- [ ] Experiments: update `EXPERIMENT_LOG.md` if results affected a conclusion.
- [ ] Defense: update `INTERVIEW_DEFENSE.md` if a question was weak.
- [ ] Commit: create a small tested commit when the slice is coherent.
- [ ] Memory: update Obsidian task `M7UXD` with current gate and next smallest action.
- [ ] Report: tell the user what changed, evidence, risks, commit, and next action.
