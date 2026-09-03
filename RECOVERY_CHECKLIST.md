# MotionWorld Recovery Plan and Execution Checklist

Status: active replacement execution checklist
Project memory: Obsidian task `M7UXD`
Starting branch: `feature/cem-runtime` at `96d8879`
Governing research contract: `PROJECT_SPEC.md`, after the reconciliation gate below
Historical checklist: `CHECKLIST.md` remains an audit record and is not the active dispatch list

## 0. Mission, acceptance rule, and operating rules

### 0.1 Target project

Build a reproducible Unreal Engine 5.8 MotionWorld demo in which a faithful Smooth Walking
predictor and a learned residual predictor are used by otherwise identical CEM-MPC controllers.
The demo must show whether the residual changes an action and whether Unreal execution from the
same initial condition improves.

The full positive claim requires all four links:

1. The causal nominal predictor has a reproducible, decision-relevant error.
2. The residual predicts that same error on held-out Unreal episodes.
3. Under an otherwise identical planner, the corrected predictor changes the selected action.
4. The changed action improves paired same-seed Unreal execution.

If link 4 fails, the project still succeeds as an honest negative control result, but it must not
claim improved control.

### 0.2 Priority labels

- **P0**: required for the targeted project and final causal evaluation.
- **P0-E**: required evidence, test, or reproducibility work for a P0 component.
- **P1**: useful only after every P0 gate passes.
- **Deferred**: excluded from this execution plan unless a new decision promotes it.

### 0.3 Non-negotiable execution rules

- [ ] Work strictly in dependency order; do not begin a later gate while an earlier gate is red.
- [ ] Build the smallest live vertical slice before further model or visualization expansion.
- [ ] Codex acts explicitly as the candidate's Teacher/Guide throughout development, not only as
      an implementer or reviewer.
- [ ] Before implementing a new concept, Codex explains its purpose, intuition, mathematics,
      assumptions, units, coordinate frames, implementation mapping, and relevance to the final
      causal claim at the candidate's current level of understanding.
- [ ] Codex must not assume that a concept is understood merely because the associated code or test
      passes.
- [ ] After each concept, Codex checks understanding through teach-back, derivation, comparison,
      debugging, or interview-style questions, corrects misconceptions explicitly, and records
      every question, candidate answer, corrected answer, and mastery status in
      `INTERVIEW_DEFENSE.md` rather than relying on chat history.
- [ ] When an answer is incomplete, Codex teaches the missing idea, gives a smaller worked example,
      and checks understanding again before recording mastery.
- [ ] Codex prepares the candidate to answer rigorous follow-up questions about design choices,
      alternatives, limitations, failure modes, evidence, and implementation details without
      relying on memorized slogans.
- [ ] Keep scalar/reference implementations as correctness oracles when optimizing runtime paths.
- [ ] Never weaken the nominal model to manufacture a residual advantage.
- [ ] Never expose future parameter snapshots, event labels, outcomes, goals, or obstacle state to
      character dynamics unless the evidence contract explicitly makes them causal inputs.
- [ ] Never open, collect, or inspect sealed final prediction episodes `5301` and `5302` before the
      final freeze gate.
- [ ] Do not use prediction-test episodes `5301` and `5302` as a substitute for paired controller
      scenario seeds.
- [ ] Never change a final-test configuration after seeing its outcome without creating a new,
      explicitly labeled experiment family.
- [ ] Replace repeated manual Blueprint editing with configuration-driven execution before final
      paired collection.
- [ ] Record failed runs and rejected approaches; do not delete inconvenient evidence.
- [ ] Update `PROJECT_SPEC.md` before knowingly changing the target system contract.
- [ ] Update `DECISIONS.md`, `EXPERIMENT_LOG.md`, `INTERVIEW_DEFENSE.md`, and task `M7UXD` at each
      material decision or gate.
- [ ] End each work block with tests, diff review, evidence location, current blocker, and next
      smallest action.

### 0.4 Explicitly deferred scope

- [ ] Do not implement AnimGen integration.
- [ ] Do not generate poses or replace the Game Animation Sample animation controller.
- [ ] Do not build a pixel/video world model, language controls, or multiple learned agents.
- [ ] Do not add a crossing-obstacle scenario before all P0 scenarios and evaluation gates pass.
- [ ] Do not claim foot sliding without reliable contact semantics.
- [ ] Do not add an uncertainty ensemble before the deterministic single-model control result.
- [ ] Treat ONNX/native inference as deferred unless runtime evidence promotes it into the minimum
      solution required for the 100 ms deadline.

## 1. Recovery baseline and contract reconciliation

Objective: establish one internally consistent target before changing runtime or model code.

### 1.1 Preserve and verify the current baseline

- [x] Record current branch, commit, worktree status, Python version, PyTorch version, Unreal
      version, machine, and threading configuration.
- [x] Run all 368 Python tests.
- [x] Run Ruff and `git diff --check`.
- [x] Run `scripts/verify_interview_package.py`.
- [x] Verify the official no-history and four-history checkpoint hashes.
- [x] Verify the accepted dataset-manifest hash and that pending test files are not opened.
- [x] Preserve OFFPLAN-001, RUNTIME-001, CEM-BUDGET-001, and RESIDUAL-COMPRESS-001 unchanged as
      historical evidence.
- [x] Reconcile stale status text in `unreal/Plugins/MotionWorld/README.md` against accepted live
      evidence without changing the evidence itself.

### 1.2 Freeze the control-frequency contract

- [x] Confirm that P0 emits observations and initiates replans at 10 Hz, then applies a validated
      current action immediately within its originating slot.
- [x] Define the observation sampling boundary precisely as Mover `OnPostFinalize`.
- [x] Define how 10 Hz control observations are selected from the higher-frequency finalized-state
      stream without introducing variable or duplicate control intervals.
- [x] Define one end-to-end response deadline in milliseconds.
- [x] Define whether a response arriving exactly at the deadline is accepted or rejected.
- [x] Define one-miss hold and three-consecutive-miss safe-stop semantics.
- [x] Define cold-start behavior separately from steady-state latency.
- [x] Define whether late results are discarded rather than applied on the next observation.
- [x] Record the timing decision in `PROJECT_SPEC.md` and `DECISIONS.md`.

### 1.3 Reconcile dynamics timestep and substeps

- [x] Measure the actual finalized-state cadence and its distribution in accepted Unreal episodes.
- [x] Compare three 1/30-second substeps, six 1/60-second substeps, and replay using recorded `dt`.
- [x] Check scalar/vectorized parity for the selected policy.
- [x] Check prediction accuracy and planner latency for the selected policy.
- [x] Select one causal deployment policy based on evidence, not convenience.
- [x] Update `PROJECT_SPEC.md`, configs, tests, `THEORY.md`, and checklist wording to agree.
- [x] Reject any hidden mismatch between training/evaluation substeps and planner substeps.

### 1.4 Reconcile the residual-training contract

- [x] Keep the current deterministic one-step checkpoints as immutable baselines.
- [x] Implement the originally specified discounted multi-step training objective, or formally amend
      the project claim and specification before proceeding.
- [x] Freeze rollout horizon, discount, Huber definition, residual penalty, clipping policy, seed,
      optimizer budget, and checkpoint-selection rule before validation.
- [x] Ensure recursive training advances predicted observable state and nominal internal state with
      no intermediate observed-state reseeding.
- [x] Ensure four-history features shift using predicted causal queries during training.
- [x] Add tests for horizon masking/rejection near episode ends.
- [x] Add a hand calculation for a two-step loss and residual composition.

### 1.5 Define separate prediction and control test contracts

- [x] Keep episodes `5301` and `5302` reserved only for final prediction evaluation.
- [x] Define a separate controller scenario manifest with paired seeds for timed gate, push recovery,
      and held-out/OOD settings.
- [x] Define target/goal state, reset pose, gate geometry, gate schedule, timeout, and agent geometry.
- [x] Define every task metric and unit before final runs.
- [x] Define the primary paired estimand and bootstrap procedure before final runs.
- [x] Define invalid-run handling and minimum valid pair count.
- [x] Define the exact positive, negative, and unresolved interpretations of the final result.

### 1.6 Gate R0 — reconciled contract

- [x] `PROJECT_SPEC.md`, configs, tests, and implementation describe one timing/substep contract.
- [x] Residual training behavior matches the specification.
- [x] Prediction-test and control-test identities are separate and frozen in draft manifests.
- [x] No final-test bytes have been opened.
- [x] Reviewer finds no future information, unit ambiguity, or contradictory acceptance rule.
- [x] Commit the reconciled contract before implementing the live runtime (`9e9c269`).

Required artifacts:

- `configs/control_runtime.yaml`
- `configs/final_prediction_manifest.yaml`
- `configs/final_control_manifest.yaml`
- Decision entries for timing, substeps, training objective, and final estimands

## 2. Versioned Unreal–Python protocol

Objective: create a bounded, testable protocol independently of planning quality.

### 2.1 Observation message

- [x] Define a protocol name and version.
- [x] Include episode ID and monotonic observation sequence.
- [x] Include simulation timestamp and declared control interval.
- [x] Include controller mode and explicit authoritative state-source label.
- [x] Include world position, world/local velocity as required, facing, and yaw rate with units.
- [x] Include all causal nominal internal state and current parameter/preparation values.
- [x] Include previous applied action and its sequence identity.
- [x] Include target and bounded timed-gate state for planner cost only.
- [x] Include reset/scenario identity and termination state.
- [x] Include validity flags instead of inventing defaults for unavailable fields.
- [x] Exclude animation-root data, future event schedules, completed-future parameter snapshots, and
      final outcomes from model inputs.
- [x] Reject missing, extra, wrong-type, unsupported-version, non-finite, oversized, and internally
      inconsistent messages.

### 2.2 Action message

- [x] Echo protocol version, episode ID, and source observation sequence.
- [x] Include selected local desired velocity in cm/s.
- [x] Include controller/model identifier.
- [x] Include planner start/end timestamps and measured planner latency.
- [x] Include safe-fallback status and reason.
- [x] Include selected trajectory and cost breakdown only as bounded diagnostic telemetry.
- [x] Reject wrong-episode, future-sequence, stale-sequence, duplicate, malformed, non-finite, and
      oversized actions.
- [x] Clamp velocity again inside Unreal.

### 2.3 Transport and serialization

- [x] Use versioned localhost UDP as the P0 transport unless R0 explicitly changes the contract.
- [x] Define maximum datagram size and bounded trajectory telemetry.
- [x] Define byte order, numeric representation, and text/binary encoding.
- [x] Define port configuration without hard-coded developer paths.
- [x] Ensure receive/send work cannot block the Unreal game thread.
- [x] Ensure parsing cannot allocate unbounded memory.
- [x] Define behavior for dropped, duplicated, reordered, and truncated datagrams.

### 2.4 Cross-language tests

- [x] Generate canonical valid observation and action fixtures.
- [x] Parse Unreal-produced observations in Python.
- [x] Parse Python-produced actions in Unreal.
- [x] Round-trip boundary values and zero values.
- [x] Reject NaN, infinity, wrong dimensions, unknown versions, and out-of-range values on both sides.
- [x] Reject wrong episode and stale sequence on both sides where applicable.
- [x] Fuzz or table-test malformed packets within a strict bounded corpus.
- [x] Confirm protocol logs never expose checkpoint payloads or unbounded source data.

### 2.5 Gate R1 — protocol correctness

- [x] Python serialization/validation tests pass.
- [x] Unreal parsing/validation automation tests pass in the actual Game Animation Sample.
- [x] Golden fixtures agree byte-for-byte or semantically under the declared encoding.
- [x] Protocol remains valid when optional telemetry is omitted.
- [x] No network path mutates gameplay state before full validation.
- [x] Commit protocol types and tests as an independent slice (`d85eeaf`).

## 3. Minimal live vertical slice and safety

Objective: prove the complete round trip before integrating CEM or retraining models.

### 3.1 Python service lifecycle

- [x] Add a stable service entry point and configuration loader.
- [x] Bind only to the configured localhost interface and port.
- [x] Validate every observation before dispatch.
- [x] Maintain state keyed by episode and sequence.
- [x] Drop superseded planning work when a newer observation arrives.
- [x] Expose health, readiness, controller mode, and bounded diagnostics.
- [x] Shut down cleanly and release the socket.
- [x] Start from a clean process without requiring imported notebook state.

### 3.2 Unreal runtime lifecycle

- [x] Add a default-off network controller component or clearly separated bridge subsystem.
- [x] Sample/send exactly one observation per 100 ms control interval.
- [x] Receive actions asynchronously.
- [x] Apply only the action matching the current episode and expected observation sequence.
- [x] Track missed, rejected, stale, and malformed responses separately.
- [x] Hold the last validated action after one miss.
- [x] Apply zero local velocity after three consecutive misses.
- [x] Clear network state on reset, controller switch, EndPlay, and service reconnection.
- [x] Ensure disabling network control restores normal human-input behavior.

### 3.3 Echo and reactive controller proof

- [x] Implement a Python echo controller with explicit clamping.
- [x] Implement a simple goal-directed reactive controller for visual context.
- [x] Run stop, forward, right, diagonal, reverse, and speed-bound cases live.
- [x] Prove requested local velocity resolves through authoritative yaw correctly.
- [x] Prove the applied command sequence matches the source observation sequence.
- [x] Prove reset creates no cross-episode action or history reuse.

### 3.4 Failure injection

- [x] Start Unreal with the Python service absent and verify safe stop.
- [x] Kill the service during motion and verify one-hold/three-stop behavior.
- [x] Restart the service and verify explicit recovery without stale state.
- [ ] Delay a valid action until it is stale and verify rejection.
- [ ] Deliver an old-episode action after reset and verify rejection.
- [ ] Send malformed and non-finite actions during motion and verify safe behavior.
- [ ] Saturate diagnostic telemetry and verify gameplay control remains bounded.
- [ ] Confirm no tested failure produces runaway motion.

### 3.5 Gate R2 — live safe round trip

- [ ] Observation → Python → action → Unreal works for at least 100 consecutive control intervals.
- [ ] Sequence and episode identity reconcile with zero unexplained gaps.
- [ ] Reset works three consecutive times without stale action/state leakage.
- [ ] Service-loss and stale-action tests pass in the actual sample.
- [ ] Steady-state echo/reactive end-to-end p95 is recorded and comfortably below 100 ms.
- [ ] A short unedited evidence recording and raw log are preserved.
- [ ] Do not proceed to live MPC until R2 passes.

Required artifacts:

- `motionworld/protocol/` implementation and tests
- Python service entry point
- Unreal protocol/runtime component and automation tests
- `evidence/unreal/runtime_roundtrip_001.log`
- `artifacts/runtime/roundtrip_001/summary.json`

## 4. Live nominal MPC

Objective: validate the controller and runtime architecture independently of learned inference.

### 4.1 Planner session state

- [ ] Construct `PlannerSnapshot` only from the validated current observation.
- [ ] Synchronize nominal internal state from the current Unreal context.
- [ ] Maintain previous and previous-previous applied actions.
- [ ] Maintain one warm-start knot sequence per episode/controller.
- [ ] Shift warm start only after the corresponding action is accepted/applied.
- [ ] Clear history, warm start, nominal state, and pending result on reset or controller switch.
- [ ] Reject a planner result whose source observation has been superseded.

### 4.2 Nominal planning service

- [ ] Run the existing vectorized nominal rollout and analytic cost from live observations.
- [ ] Use the frozen action bounds, horizon, knots, candidates, elites, and iterations.
- [ ] Return the first action before the end-to-end deadline.
- [ ] Return zero action on non-finite rollout, insufficient finite candidates, or internal failure.
- [ ] Report cost components, selected path, candidate summary, and latency as diagnostics.

### 4.3 Live nominal validation

- [ ] Demonstrate obstacle-free goal-directed control.
- [ ] Demonstrate stable start, acceleration, turning, stopping, and reset.
- [ ] Demonstrate the timed-gate scenario without claiming residual benefit.
- [ ] Check that observed state and selected trajectory use the same coordinate frame and origin.
- [ ] Compare predicted nominal trajectory with realized authoritative trajectory.
- [ ] Record deadline misses and fallback actions.
- [ ] Verify identical repeated seed/configuration produces equivalent initial conditions.

### 4.4 Gate R3 — nominal live control

- [ ] Nominal MPC controls the character for a complete episode.
- [ ] Nominal end-to-end p95 meets 100 ms with zero stale action application.
- [ ] Reset and controller switching do not reuse state.
- [ ] Predicted and actual trajectory telemetry are temporally aligned.
- [ ] Service failure still produces the R2 safe stop.
- [ ] Preserve one successful and one deliberately interrupted run.
- [ ] Do not begin final scenario tuning; this gate validates plumbing only.

## 5. Residual training and predictive gate

Objective: produce the final causal residual checkpoint before runtime optimization and final tests.

### 5.1 Dataset and target audit

- [ ] Re-run accepted-file hash, identity, schema, chronology, and leakage audits.
- [ ] Confirm train episodes are `5101`–`5105` and validation episodes are `5201`–`5202` unless R0
      creates a new explicitly versioned experiment family.
- [ ] Confirm final prediction episodes remain unopened.
- [ ] Report action, speed, stop, turn, parameter-change, contact, and perturbation coverage.
- [ ] Confirm hidden perturbation transitions cannot become supervised targets.
- [ ] Confirm all residual targets use the previous observed facing as their local frame.

### 5.2 Multi-step training implementation

- [ ] Construct complete 1.5-second training horizons without crossing episode boundaries.
- [ ] Apply the frozen incomplete-horizon policy.
- [ ] Roll nominal internal state forward causally.
- [ ] Apply learned corrections only to observable state unless a new contract explicitly changes it.
- [ ] Compute discounted per-horizon normalized Huber losses.
- [ ] Apply the frozen residual-magnitude regularizer.
- [ ] Keep normalization fitted on training episodes only.
- [ ] Train no-history and four-history variants under matched seeds/budgets.
- [ ] Create both checkpoints before any validation-based selection.
- [ ] Save config, normalization, feature names, seed, commit, traces, and hashes.

### 5.3 Validation and selection

- [ ] Evaluate nominal, one-step baseline residuals, and multi-step residuals recursively without
      teacher forcing at 0.5, 1.0, and 1.5 seconds.
- [ ] Report position, velocity, yaw, and yaw-rate median/p95/max.
- [ ] Report stable-parameter and parameter-change-crossing strata.
- [ ] Report any available free, contact, and post-observed-perturbation strata without pretending
      absent coverage exists.
- [ ] Compare no-history and four-history at matched and strongest-feasible capacity.
- [ ] Preserve history losing as a valid negative result.
- [ ] Inspect outliers and whether gains are confined to a narrow regime.
- [ ] Select exactly one residual checkpoint for planning using the frozen rule.

### 5.4 Gate R4 — final prediction model

- [ ] The selected model improves the preregistered decision-relevant recursive validation metrics.
- [ ] The checkpoint is selected without final-test access.
- [ ] Zero residual remains the exact nominal identity.
- [ ] No future parameter/event/outcome information reaches the model.
- [ ] Reviewer reproduces the evaluation and hashes from a clean worktree.
- [ ] If no model passes, preserve the negative result and stop the residual-control claim.

## 6. Deadline-safe residual MPC

Objective: meet the complete 10 Hz deadline without sacrificing the frozen planning-quality gate.

### 6.1 Component profiling

- [ ] Measure observation serialization and transport.
- [ ] Measure protocol parsing and `PlannerSnapshot` construction.
- [ ] Measure nominal rollout kernels.
- [ ] Measure residual feature construction.
- [ ] Measure each residual-model forward across candidates/horizon.
- [ ] Measure planning cost and CEM elite updates.
- [ ] Measure response serialization, transport, validation, and Unreal application.
- [ ] Report median, p95, maximum, cold start, warmup, device, threads, and batch shapes.
- [ ] Identify the dominant component before selecting an optimization.

### 6.2 Optimize without changing semantics

- [ ] Preserve scalar nominal/residual rollout as the mathematical oracle.
- [ ] Fuse or batch residual rollout operations across candidates where profiling supports it.
- [ ] Avoid Python object construction inside candidate/horizon hot loops.
- [ ] Avoid repeated tensor/NumPy conversions and redundant normalization.
- [ ] Preallocate bounded workspaces where measurements justify it.
- [ ] Verify every optimized path against randomized scalar oracle cases.
- [ ] Verify selected actions and cost reproduction under the reference configuration.
- [ ] Measure rather than assume benefits from Torch compilation, exported inference, threading, or
      native inference.

### 6.3 Runtime/quality trade-off gate

- [ ] Keep the reference 256/32/3 CEM result as the search-quality comparator.
- [ ] If changing CEM budget, freeze candidates before measuring validation quality.
- [ ] Compare positive cost regret, first-action distance, path difference, and new predicted
      collisions over the frozen validation query set.
- [ ] If changing the residual model, compare recursive metrics and cross-evaluate plans under the
      frozen reference model.
- [ ] Reject any candidate that passes runtime but violates quality or collision tolerances.
- [ ] Do not relax thresholds after seeing results.

### 6.4 Gate R5 — residual runtime

- [ ] Residual MPC complete end-to-end p95 is at or below 100 ms.
- [ ] No benchmark call uses test episodes.
- [ ] No accepted optimization violates scalar/vectorized parity.
- [ ] No accepted optimization violates the frozen planning-quality gate.
- [ ] Thirty or more alternating live/representative calls produce no stale action application.
- [ ] Cold-start behavior is separately reported.
- [ ] If R5 cannot pass, formally choose between changing the project timing contract or accepting a
      negative runtime result; do not proceed to a false 10 Hz control claim.

## 7. Live residual MPC and controller fairness

Objective: prove both controllers use the same live problem and differ only by transition model.

### 7.1 Residual controller integration

- [ ] Load the frozen checkpoint and normalization with strict hash/schema checks.
- [ ] Reject mismatched feature names, history length, checkpoint, config, or normalization.
- [ ] Initialize residual history according to the declared cold-start policy.
- [ ] Advance history using real observations between replans and predicted queries inside rollouts.
- [ ] Clear history and model state on reset/controller switch.
- [ ] Use the same target, obstacle state, action history, and nominal context as nominal MPC.

### 7.2 Enforce fairness in code

- [ ] Construct one shared `PlannerProblem` and live `PlannerQuery` per comparison state.
- [ ] Reuse identical CEM random noise and identical first-iteration physical candidates.
- [ ] Use identical cost terms, weights, bounds, horizon, knots, candidates, elites, and iterations.
- [ ] Use identical deadlines and fallback policy.
- [ ] Record first-candidate hashes and every fairness-critical config hash.
- [ ] Permit only the transition model/checkpoint to differ.

### 7.3 Obstacle-free and timed-gate smoke

- [ ] Run residual MPC obstacle-free to a fixed target.
- [ ] Verify stable start, turn, stop, and reset.
- [ ] Run nominal and residual from repeated identical seeds/configurations.
- [ ] Record selected-action disagreement and trajectory disagreement.
- [ ] Cross-evaluate each selected plan under both models.
- [ ] Execute each selected action in Unreal before interpreting its value.
- [ ] Record predicted-versus-realized trajectory and cost.

### 7.4 Gate R6 — fair live controllers

- [ ] Nominal and residual MPC each complete live episodes.
- [ ] Both meet the same end-to-end timing and safety policy.
- [ ] First-iteration candidate equality is proven from live records.
- [ ] Same-seed reset equality is demonstrated.
- [ ] Controller switching produces no stale state.
- [ ] At least one live action disagreement is recorded without yet claiming improvement.

## 8. Final scenarios and freeze

Objective: freeze every choice that could change after seeing final outcomes.

### 8.1 Timed-gate scenario

- [ ] Freeze target, start, gate geometry, analytic schedule, timeout, agent radius, and margin.
- [ ] Freeze cost weights and units.
- [ ] Ensure the scenario is not engineered around one observed residual win.
- [ ] Verify acceleration/timing differences can affect feasibility naturally.
- [ ] Use identical gate schedule and obstacle information for every controller.

### 8.2 Push-recovery scenario

- [ ] Freeze perturbation direction, magnitude, time, and application API semantics.
- [ ] Apply the identical perturbation schedule to every paired controller.
- [ ] Define trajectory-error recovery threshold and recovery-time measurement.
- [ ] Start recovery evaluation after the unobservable event has occurred.
- [ ] Never claim pre-event prediction of an undisclosed perturbation.

### 8.3 Held-out/OOD movement scenario

- [ ] Select one movement parameter family before final testing.
- [ ] Record the training support range.
- [ ] Freeze in-range held-out and outside-range OOD values.
- [ ] State whether each parameter is visible to nominal dynamics and residual features.
- [ ] Distinguish parameter-conditioned prediction from robustness to unobserved change.
- [ ] Preserve degradation/failure results.

### 8.4 Configuration-driven runner

- [ ] Load scenario/controller/seed combinations from the frozen manifest.
- [ ] Set every mutable Unreal experiment property programmatically or verify it against the manifest
      before starting.
- [ ] Refuse duplicate episode IDs, wrong configuration, missing reset, or stale asset state.
- [ ] Run controllers in counterbalanced order where order could affect the machine/session.
- [ ] Export complete raw metadata and a reconciled footer for every attempt.
- [ ] Retain rejected attempts with explicit reasons.

### 8.5 Gate R7 — final freeze

- [ ] Freeze dataset manifests, checkpoints, normalization, schema, planner config, cost weights,
      scenarios, controller seeds, metric code, and bootstrap seed.
- [ ] Hash every frozen input and record the Git commit plus hardware/software environment.
- [ ] Run all unit, protocol, Unreal automation, runtime, reset, and smoke gates.
- [ ] Confirm no final prediction or paired-control result has been inspected.
- [ ] Reviewer signs off on leakage, fairness, pair construction, missing-run policy, and multiplicity.
- [ ] Tag or commit the pre-test freeze.

## 9. Locked final evaluation

Objective: let Unreal adjudicate the model-selected actions under a frozen paired protocol.

### 9.1 Prediction test

- [ ] Collect/open episodes `5301` and `5302` only after R7 passes.
- [ ] Validate exact identity, configuration, hashes, schema, and completeness before evaluation.
- [ ] Evaluate nominal, no-history, and four-history/final selected model as preregistered.
- [ ] Report 0.5/1.0/1.5-second position, velocity, yaw, and yaw-rate metrics.
- [ ] Report all preregistered strata and explicitly mark absent strata.
- [ ] Do not retrain or change thresholds after seeing results.

### 9.2 Paired controller execution

- [ ] Run reactive, nominal MPC, and residual MPC on every frozen timed-gate seed.
- [ ] Run the declared nominal/residual controllers on every frozen push-recovery seed.
- [ ] Run the declared controllers on every held-out/OOD setting and seed.
- [ ] Confirm pair validity and identical starting state/configuration.
- [ ] Retain timeouts, collisions, service failures, and invalid attempts.
- [ ] Record per-episode actions, predictions, realized states, costs, latency, and outcomes.

### 9.3 Metrics and statistics

- [ ] Report success, collision count/rate, time to goal, minimum clearance, and recovery time.
- [ ] Report median, IQR, paired differences, bootstrap confidence intervals, and episode counts.
- [ ] Report missed deadlines and fallback-action counts.
- [ ] Report selected-action disagreement.
- [ ] Trace at least one disagreement from nominal error through correction and action to Unreal
      outcome.
- [ ] Separate statistical uncertainty from practical effect size.
- [ ] Avoid uncorrected storytelling across many metrics.

### 9.4 Planner-exploitation audit

- [ ] Record predicted return for every selected plan.
- [ ] Record realized Unreal return for every executed plan.
- [ ] Compute selected-plan prediction gaps.
- [ ] Compare selected gaps with random in-distribution trajectory gaps.
- [ ] Inspect extreme selected actions and trajectories.
- [ ] Report bound saturation, OOD states, collision optimism, or model-specific exploitation.
- [ ] Enter the frozen result as `EXPLOIT-001`.

### 9.5 Gate R8 — final claim

- [ ] Complete the four-link causal audit explicitly.
- [ ] Rule out different candidates, seeds, costs, budgets, obstacle information, deadlines, or reset
      state as explanations.
- [ ] State plausible remaining alternative explanations.
- [ ] Choose the weakest evidence-supported conclusion.
- [ ] Preserve a negative or mixed result without changing the frozen experiment.
- [ ] Commit raw manifests, evaluation code, tables, plots, and interpretation together.

## 10. Demo visualization and controls

Objective: make the final evidence understandable in a 90-second live or prerecorded demonstration.

### 10.1 Trajectories

- [ ] Render faint gray CEM candidate trajectories.
- [ ] Render the selected trajectory prominently.
- [ ] Render nominal prediction in blue.
- [ ] Render residual-corrected prediction in orange.
- [ ] Render actual authoritative execution in yellow.
- [ ] Render goal and timed-gate position/velocity.
- [ ] Label horizon, timestep, current observation sequence, and source controller.
- [ ] Ensure every displayed trajectory comes from the current episode/sequence.

### 10.2 HUD

- [ ] Display active controller, scenario, seed, and movement setting.
- [ ] Display selected local desired velocity.
- [ ] Display planning and end-to-end latency plus missed-deadline count.
- [ ] Display prediction error at the declared horizon.
- [ ] Display collision count, clearance, and termination/outcome.
- [ ] Display safe-fallback/service status.
- [ ] Reject or visibly invalidate stale telemetry.

### 10.3 Live controls and pause futures

- [ ] Select/reset target and scenario.
- [ ] Switch reactive/nominal/residual controllers safely.
- [ ] Apply the controlled perturbation.
- [ ] Pause on one authoritative state.
- [ ] Generate forward, left, right, and stop futures from the identical frozen state.
- [ ] Display nominal and corrected futures together.
- [ ] Optionally execute one intervention and compare actual motion.
- [ ] Toggle trajectories and metrics without changing controller state.
- [ ] Document every control in the runbook.

### 10.4 Gate R9 — demonstrable result

- [ ] Same-seed nominal/residual comparison works from a fresh launch.
- [ ] The principal causal or negative result is reproducible.
- [ ] One honest failure case is reproducible.
- [ ] Reset works three consecutive times.
- [ ] Service-failure recovery works during the demonstration.
- [ ] HUD and trajectories contain no stale or contradictory values.
- [ ] Record one unedited evidence run and one 60–90 second presentation video.

## 11. Packaging, reproducibility, and release

### 11.1 Repository instructions

- [ ] Document exact hardware/software prerequisites.
- [ ] Document Unreal Engine and Game Animation Sample acquisition.
- [ ] Document plugin installation without licensed-content redistribution.
- [ ] Document Python environment creation from `uv.lock`.
- [ ] Document protocol/service configuration and launch order.
- [ ] Document data generation, validation, training, planning, evaluation, and demo commands.
- [ ] Document expected test counts and representative output.
- [ ] Document all manual Unreal steps that cannot be automated.
- [ ] Document limitations, negative results, and production gaps.

### 11.2 Final artifact package

- [ ] Architecture diagram.
- [ ] Main paired result table.
- [ ] Final prediction graph.
- [ ] One four-link causal trace or explicit broken-link trace.
- [ ] Runtime table.
- [ ] Planner-exploitation/OOD failure graph.
- [ ] Primary 60–90 second video.
- [ ] Offline fallback video and runbook.
- [ ] Frozen manifest containing every artifact size and SHA-256.

### 11.3 Reproduction

- [ ] Recreate the Python environment from the lockfile in a clean clone/worktree.
- [ ] Run all Python tests, Ruff, and diff checks.
- [ ] Run deterministic synthetic and CEM smoke experiments.
- [ ] Reproduce final tables/plots from frozen non-private artifacts where possible.
- [ ] Build the plugin and run Unreal automation in the separately acquired sample.
- [ ] Verify package files contain no developer-only absolute paths.
- [ ] Verify no raw private/licensed data, credentials, caches, or accidental large files are tracked.
- [ ] Record unavoidable local Unreal reproduction deviations.

### 11.4 Gate R10 — release candidate

- [ ] Worktree is clean.
- [ ] Documentation matches actual commands and behavior.
- [ ] Every final claim links to a frozen artifact.
- [ ] Obsidian task `M7UXD` contains a final resume-ready handoff.
- [ ] Create a release-candidate commit and tag only after checklist review.

## 12. Candidate ownership and rehearsal

### 12.0 Teacher/Guide contract

For every new project component, Codex must run a visible learning loop alongside the engineering
loop:

1. **Orient** — connect the component to the complete MotionWorld system and four-link claim.
2. **Teach** — explain intuition first, then equations, units, frames, timing, and code mapping.
3. **Demonstrate** — work one concrete numerical, trace, or code example from input to output.
4. **Question** — ask progressively harder factual, conceptual, mathematical, design, failure, and
   evidence questions of the kind an interviewer could ask.
5. **Diagnose** — distinguish a vocabulary gap, conceptual gap, derivation error, implementation
   misunderstanding, or unsupported claim.
6. **Remediate** — reteach the specific gap and provide a smaller exercise or counterexample.
7. **Verify** — require an unaided explanation, derivation, or debugging exercise before marking the
   concept understood.
8. **Retain** — revisit earlier concepts during later components so understanding is cumulative.

- [ ] Maintain a concept-mastery register covering every core MotionWorld topic.
- [ ] Mark each topic `unintroduced`, `learning`, `can explain`, or `can defend under follow-up`.
- [ ] Record the evidence for mastery: teach-back, hand derivation, code walkthrough, or debugging
      exercise.
- [ ] Never mark mastery solely because Codex supplied the correct answer.
- [ ] Revisit any topic whose explanation conflicts with current code, experiments, or claims.
- [ ] Add unresolved misconceptions and difficult questions to `INTERVIEW_DEFENSE.md`.
- [ ] Ensure the candidate can move between intuition, equations, code, experiment, and limitation
      for each core concept.
- [ ] Treat “can defend under follow-up” as the required interview-ready state.

### 12.1 Required explanations

- [ ] Deliver the 30-second project explanation.
- [ ] Deliver the 90-second evidence/demo narrative.
- [ ] Deliver the five-minute technical narrative.
- [ ] Explain why the nominal model is faithful and cheap.
- [ ] Explain exactly what the residual sees, predicts, and cannot predict.
- [ ] Explain why better prediction does not imply better control.
- [ ] Explain why Unreal, not either learned/planning model, adjudicates the final claim.
- [ ] Explain the strongest and weakest supported conclusions.

### 12.2 Blank-page derivations

- [ ] Coordinate rotation and inverse.
- [ ] Smooth Walking velocity and facing updates.
- [ ] Residual target and local-frame composition.
- [ ] Multi-step loss and recursive rollout.
- [ ] CEM sampling, elite moments, momentum, and MPC receding horizon.
- [ ] Planning-cost terms and units.
- [ ] Episode-safe split and leakage prevention.
- [ ] Paired bootstrap and median versus p95 latency.

### 12.3 Hostile review

- [ ] Complete Daniel-style movement/animation/runtime questioning.
- [ ] Complete Viktoriia-style causal/data/robustness questioning.
- [ ] Explain the model-exploitation evidence without overclaiming.
- [ ] Explain the one-step-training history and final reconciled decision.
- [ ] Explain all rejected runtime shortcuts and why they were rejected.
- [ ] Complete one protocol/stale-packet debugging exercise.
- [ ] Complete one coordinate, model, and CEM coding exercise without project scaffolding.

### 12.4 Final rehearsal

- [ ] Run the full live demo from a fresh launch three times.
- [ ] Time the 90-second and five-minute narratives.
- [ ] Practice recovery from Unreal launch failure.
- [ ] Practice recovery from Python service failure.
- [ ] Verify all videos, diagrams, tables, and plots work offline.
- [ ] After freeze, repair only a demonstrated launch blocker and rerun the complete rehearsal.

### 12.5 Core concept-mastery register

- [ ] World model: explain the narrow action-conditioned meaning used here and how it differs from a
      visual foundation model.
- [ ] Causal chain: explain all four links and why each requires different evidence.
- [ ] Unreal authority: explain requested motion, Mover proposal, collision-finalized state, and
      animation-root state.
- [ ] Tick timing: explain `OnPostFinalize`, action-to-transition alignment, and why endpoint yaw or
      future parameters can leak information.
- [ ] Coordinate frames: derive local/world transforms and identify the reference yaw for actions
      and residuals.
- [ ] Smooth Walking: explain acceleration/deceleration, turning, spring memory, facing, substeps,
      and resynchronization after external influence.
- [ ] Nominal versus residual modeling: explain why known dynamics remain nominal and what the MLP is
      permitted to correct.
- [ ] Residual features and targets: explain all feature families, six outputs, normalization, and
      exact zero-residual identity.
- [ ] History: explain real-history initialization, imagined-history advancement, teacher forcing,
      and why history cannot predict an undisclosed future push.
- [ ] Training: derive normalized Huber loss, residual regularization, discounted multi-step loss,
      and checkpoint selection without validation leakage.
- [ ] Dataset integrity: explain episode-safe splitting, frozen manifests, rejected-run quarantine,
      train-only normalization, and sealed-test policy.
- [ ] CEM: derive candidate sampling, knot expansion, projection, elite moments, momentum, variance
      floor, warm start, and safe fallback.
- [ ] MPC: explain recursive counterfactual rollout, why only the first action executes, and why the
      controller replans after the next observation.
- [ ] Planning cost: explain goal, swept collision, clearance, action-change, and curvature terms,
      including units and common exploitation modes.
- [ ] Fair comparison: explain common random numbers, identical first candidates, adaptive later
      divergence, and why only the transition model may differ.
- [ ] Runtime: explain median/p95, cold versus warm latency, end-to-end deadline accounting, stale
      actions, and the runtime/quality Pareto gate.
- [ ] Protocol safety: explain episode/sequence identity, malformed/stale rejection, one-miss hold,
      three-miss stop, and reset/reconnection state clearing.
- [ ] Evaluation: explain recursive prediction metrics, paired controller estimands, paired
      bootstrap intervals, OOD strata, and invalid-run handling.
- [ ] Planner exploitation: explain why a model's own low predicted cost is not truth and how Unreal
      predicted-versus-realized return adjudicates it.
- [ ] Claim discipline: state the strongest and weakest supported conclusions and defend a negative
      or mixed result without changing the experiment.

## 13. Definition of done

The targeted MotionWorld project is complete only when all of the following are true:

- [ ] R0–R10 pass with linked evidence.
- [ ] Nominal and residual MPC run through the same safe live Unreal–Python control loop.
- [ ] Both controllers satisfy the same declared end-to-end deadline and fallback policy.
- [ ] Final paired scenarios were executed from frozen configurations without test-driven tuning.
- [ ] Prediction, action selection, and realized Unreal outcome are connected in one auditable trace.
- [ ] The conclusion—positive, negative, or mixed—matches the four-link evidence.
- [ ] The demo, fallback, clean reproduction, and candidate defense all pass.

## 14. Original-checklist mapping

| Original `CHECKLIST.md` area | Recovery checklist destination |
|---|---|
| 0. Governance | Sections 0, 1, 11, 12 |
| 1. Environment | R0 baseline and R10 reproduction |
| 2. Skeleton/contracts | R0 and R1 |
| 3. Theory proof | Preserved baseline; R4/R5 oracle checks and Section 12 |
| 4. Unreal feasibility | Preserved baseline; remaining lifecycle work in R2/R3 |
| 5. Protocol/safety | R1 and R2 |
| 6. Nominal model | R0, R3, and R4 |
| 7. Dataset | R0, R4, R7, and R8 |
| 8. Residual model | R0, R4, and R5 |
| 9. CEM planner | Preserved offline baseline; R3, R5, and R6 |
| 10. Live MPC | R2, R3, and R6 |
| 11. Scenarios | R7 |
| 12. Final evaluation | R7 and R8 |
| 13. Demo UX | R9 |
| 14. Packaging | R10 |
| 15. Interview mastery | Section 12 |
| 16. Deferred work | Section 0.4 |
| 17. Work-block handoff | Section 0.3 |
