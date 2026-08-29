# MotionWorld End-to-End Project Plan

Status: active execution plan  
Build window: Saturday 29 August through Friday 4 September 2026 at 15:00 Europe/Copenhagen
Code freeze: Thursday 3 September at 22:00; Friday morning is rehearsal and recovery only
Operating principle: implementation speed never substitutes for personal ownership of design, mathematics, experiments, or conclusions.

## 0. Deadline reality and priority ladder

The PDF describes seven implementation days. The actual calendar provides five build days after project foundation plus Friday morning. The technical stages below retain their Day 0-7 names so they remain traceable to specification v1.1, but their dated execution is compressed:

| Calendar date | Logical stages | Non-negotiable result |
|---|---|---|
| Sat 29 Aug | Day 0 | Research contract, memory, living documents, branch/commit protocol. |
| Sun 30 Aug | Day 1 | Unreal installed/sample available; compiled control/reset/logger feasibility or a documented fallback decision. |
| Mon 31 Aug | Day 2 | Tested coordinates and nominal dynamics; episode-safe data path; first real prediction-error plot. |
| Tue 1 Sep | Day 3 | Nominal/no-history/history recursive prediction comparison. |
| Wed 2 Sep | Day 4 | Deterministic offline CEM and, if gates pass, live nominal/residual control. |
| Thu 3 Sep | Days 5-6 | Frozen paired evaluation, latency, failure case, recording, README, and package. Stop coding at 22:00. |
| Fri 4 Sep, morning | Day 7 | Three clean rehearsals, hostile examination, fallback verification. Interview at 15:00. |

### Evidence ladder

We pursue the strongest level that passes its gate without misrepresenting a lower level as a stronger result:

1. **Theory proof** - hand calculations and unit tests validate coordinates, nominal updates, residual composition, multi-step rollout, cost, and CEM.
2. **Synthetic causal proof** - a labeled deterministic 2D test double demonstrates nominal error -> residual correction -> different plan -> improved synthetic outcome. This proves the software/reasoning chain, not Unreal performance.
3. **Unreal feasibility proof** - programmatic desired velocity, authoritative post-movement state, deterministic reset, gate, and complete episode log work in the real engine.
4. **Unreal prediction proof** - the learned residual reduces held-out recursive Unreal state error over a faithful nominal baseline.
5. **Unreal control proof** - corrected prediction changes an otherwise identical CEM decision and improves paired same-seed Unreal execution. This is the full positive claim.

If level 5 is not reached, the interview package explicitly states the highest completed level and the missing evidence. We never present synthetic data as Unreal evidence or prediction improvement as control improvement.

### Immediate environment gate

The 30 August inventory found an Apple M4/16 GB Mac, Xcode 26.6, Apple Clang 21, `uv`, Python 3.12, CMake 4.2, and about 105 GiB free disk. Epic Games Launcher is installed, but no `UnrealEditor.app` or Game Animation Sample was detected. Default Python 3.14 has no PyTorch and must not be used for the ML environment.

- By Sunday 10:00: start/verify a version-matched Unreal 5.7 or 5.8 installation and Game Animation Sample acquisition; confirm required disk footprint before downloading.
- While installation runs: create a Python 3.12 `uv` environment and begin only the theory test double, coordinate tests, schemas, and protocol types.
- By Sunday 13:00: open and compile the sample or record the exact installation blocker.
- By Sunday 18:00: demonstrate external desired velocity and authoritative state capture.
- By Sunday 22:00: demonstrate deterministic reset and one logged episode. If the sample blocks integration, switch to Manny plus Mover. If the engine itself remains unavailable, freeze all Unreal claims and maximize evidence levels 1-2 while preserving an explicit integration plan.

## 1. How we will work

### Four responsibilities

The work has four explicit passes:

1. **Mentor/Research Engineer** - explains the concept, derives the contract, and identifies the smallest valid experiment.
2. **Builder** - implements boilerplate, tests, plots, and one bounded module.
3. **Reviewer** - checks equations, units, coordinate frames, leakage, fairness, failure handling, and code quality.
4. **Examiner** - asks adversarial interview questions and refuses completion when the explanation is weak.

These are sequential hats, not independent sources of truth. The candidate approves scientific decisions and must be able to explain the accepted result.

### Component loop

Every component follows this checklist:

1. **Understand** - purpose, inputs, outputs, assumptions, necessity, and failure signature.
2. **Derive** - equation, units, coordinate frame, and one hand calculation.
3. **Build small** - one isolated implementation with variable-to-equation mapping.
4. **Test independently** - hand oracle, edge cases, deterministic test, and negative test.
5. **Teach back** - explain purpose, math, complexity, and limitation in about one minute.
6. **Review and commit** - Reviewer pass, Examiner questions, living-document update, small commit.

No component advances merely because it compiles or produces a plausible animation.

## 2. Git and documentation protocol

### Durable memory

- Obsidian task ID: `M7UXD`.
- Read the task note at the beginning of every session.
- Append decisions, ruled-out paths, validation changes, and handoff state during work.
- Update the resume-ready summary before ending every session.

### Repository documents

- `PROJECT_SPEC.md` changes only when the intended system changes.
- `THEORY.md` receives derivations, hand calculations, and candidate explanations.
- `DECISIONS.md` receives every material decision before or immediately after implementation.
- `EXPERIMENT_LOG.md` receives every run that may influence a conclusion.
- `INTERVIEW_DEFENSE.md` receives questions, weak answers, and evidence-backed revisions.

### Branches

Use sequential, short-lived milestone branches:

1. `docs/project-foundation`
2. `feature/unreal-feasibility`
3. `feature/nominal-dynamics`
4. `feature/data-pipeline`
5. `feature/residual-model`
6. `feature/cem-planner`
7. `feature/unreal-control-integration`
8. `experiment/final-evaluation`
9. `release/interview-demo`

If two items cannot be tested or reviewed independently, keep them on the same branch. Do not create branches merely to increase branch count. Never overlap branches that modify the same Unreal assets.

### Commit rhythm

Commit after a coherent tested slice, normally several times per day. Examples:

- `Document MotionWorld research and evaluation contract`
- `Add tested coordinate frame conversions`
- `Implement substepped Smooth Walking nominal dynamics`
- `Validate episode-safe dataset splits`
- `Train residual model with recursive rollout loss`
- `Add deterministic batched CEM planner`
- `Integrate stale-packet rejection and safe stop`
- `Record paired final evaluation artifacts`

Before a branch closes: tests pass, `git diff --check` passes, docs reflect behavior, experiment artifacts are traceable, and the Obsidian handoff names the next gate.

## 3. Two implementation tracks

### Track A - theory proof of concept

A deterministic Python 2D backend validates interfaces without Unreal:

- known acceleration and turn dynamics;
- configurable hidden lag or spring mismatch;
- analytic timed gate;
- residual target and recursive rollout;
- fixed-seed CEM;
- demonstration that zero residual equals nominal;
- a constructed but clearly labeled causal example where corrected prediction changes the plan.

This is a test double and teaching tool, not final evidence. It lets us find tensor, rollout, cost, and planner bugs cheaply.

### Track B - actual Unreal experiment

The same state/action/rollout interfaces connect to Game Animation Sample/Mover. Only Unreal results support the interview claim. Track A must never be presented as if it were engine evidence.

## 4. Day 0 - project foundation (Saturday 29 August; completed)

### Objectives

- Freeze terminology, scope, scientific claim, and integrity rules.
- Establish memory, documentation, branch, commit, and experiment protocols.
- Inventory the machine: Unreal version/source access, Game Animation Sample availability, compiler/toolchain, Python, PyTorch, GPU, disk, and recording tools.

### Deliverables

- Six living project documents.
- Initial decision records.
- Initial experiment registry.
- Clean `docs/project-foundation` commit.
- Environment inventory added to the experiment log.

### Checkpoint

Candidate can explain the causal claim, why prediction and control are separate, why the baseline must be faithful, and why actor state is authoritative.

### Stop/go gate

Do not write model or Unreal integration code until the repository contract and environment constraints are visible.

## 5. Day 1 - Unreal feasibility (Sunday 30 August)

Branch: `feature/unreal-feasibility`

### 5.1 Version and API audit

- Confirm exact Unreal version and Game Animation Sample release.
- Locate Mover Smooth Walking classes/assets and the desired-velocity control surface.
- Verify all APIs in version-matched official documentation or engine source.
- Compile the smallest project-specific module immediately.

### 5.2 Authoritative state

- Sample actor/capsule position, velocity, facing, and angular velocity after movement.
- Record animation-root transform separately.
- Determine tick order and prove labels do not swap state sources.
- Document units, frame conversion, and timestamp convention.

### 5.3 External control and safety

- Apply a programmatic desired-local-velocity command.
- Clamp commands and define facing behavior.
- Implement sequence/episode validation and safe stop.
- Verify loss of the planning service cannot leave a runaway character.

### 5.4 Scenario and logging

- Deterministically reset character, target, gate, controller state, history, and seed.
- Create one timed moving gate.
- Log one complete episode with required metadata.
- Replay/reset twice and compare initial state and obstacle schedule.

### Builder output

- Minimal Unreal module/components, packet structs, state logger, reset path, gate actor, and smoke tests.

### Reviewer attack

- Wrong tick phase, degrees/radians confusion, local/global mix, stale packets, history leakage across reset, invented API, nondeterministic gate schedule.

### Examiner questions

- Which transform is authoritative and why?
- At exactly what point in the tick is it sampled?
- How do you know reset cleared hidden controller state?
- What happens after three missed packets?

### Deliverables

- Short video of programmatic control and deterministic reset.
- One valid episode file plus schema.
- Actor-versus-animation-root trace.
- `FEAS-001` entry and exact reproduction command.

### Stop/go gate

Proceed only when external desired velocity, post-movement state, deterministic reset, collision events, and logging work reliably. If Game Animation Sample blocks progress by the end of the gate, switch to Manny plus Mover and document the reason.

### Suggested commits

- `Add versioned Unreal observation and action protocol`
- `Expose authoritative Mover state and safe desired velocity control`
- `Add deterministic arena reset and episode logger`

## 6. Day 2 - nominal dynamics, data foundation, and theory POC (Monday 31 August)

Branches: `feature/nominal-dynamics`, then `feature/data-pipeline`

### 6.1 Coordinate module

- Implement global/local vector conversion and facing representation.
- Add round-trip, 0/90/180-degree, and sign tests.
- Perform and record one manual calculation.

### 6.2 Nominal model

- Transcribe verified Smooth Walking equations into a small testable module.
- Map every variable to the engine parameter or known internal state.
- Substep the 100 ms macro transition.
- Define synchronization after each real observation.
- Test zero motion, acceleration, deceleration, reversal, turn, stop, push-state synchronization, and timestep sensitivity.

### 6.3 Theory backend

- Implement the deterministic 2D backend using the same public interfaces.
- Introduce one clearly labeled hidden-lag mismatch.
- Produce nominal-versus-ground-truth rollouts before learning.

### 6.4 Dataset pipeline

- Define typed episode schema and feature version.
- Validate monotonic sequence/timestamps, finite values, units, state source, and action alignment.
- Generate train/validation/test manifests by episode and regime.
- Fit normalization only on training data.
- Collect the action mixture and inspect coverage.

### Builder output

- Coordinate, nominal, toy-backend, schema, split, and plotting modules with tests.

### Reviewer attack

- Artificially weak nominal baseline, one-large-step integration, future-action misalignment, train/test adjacency leakage, normalization leakage, residual target mixing coordinate frames.

### Examiner questions

- Derive one velocity and position update.
- Which state is known, hidden, or estimated?
- Why does substepping matter?
- What empirical evidence shows learnable residual structure exists?

### Deliverables

- Passing hand-oracle tests.
- Prediction error at 0.1, 0.5, 1.0, and 1.5 s before learning.
- Error plots stratified by free motion, turns, stops, and contact/push.
- Dataset coverage and split report.
- `NOM-001` and `NOM-002` entries.

### Stop/go gate

Do not train a residual unless nominal error is reproducible, systematic, and large enough in decision-relevant scenarios. If error is negligible, preserve the result and revise the research question instead of weakening the baseline.

### Suggested commits

- `Add tested coordinate and normalization contracts`
- `Implement substepped Smooth Walking nominal dynamics`
- `Add deterministic toy dynamics backend`
- `Validate episode-safe dataset manifests`

## 7. Day 3 - residual model (Tuesday 1 September)

Branch: `feature/residual-model`

### 7.1 Target and composition

- Implement state-difference and residual-composition functions explicitly.
- Choose and document facing correction representation.
- Prove zero residual equals nominal prediction.
- Implement autoregressive history updates; resolve future contact context rather than freezing it.

### 7.2 Dataset and model

- Build horizon windows without crossing episode boundaries.
- Implement no-history and four-observation MLPs.
- Record parameter count and feature schema.
- Add shape, device, dtype, gradient, and deterministic smoke tests.

### 7.3 Recursive training

- Train with multi-step Huber loss and residual regularization.
- Keep one-step diagnostics but select on recursive validation.
- Save configs, normalization, seeds, commit, and checkpoint hashes.

### 7.4 Evaluation

- Compare nominal, no-history, and history models at 0.5, 1.0, and 1.5 s.
- Report each state component and required strata.
- Inspect residual magnitude, bias, outliers, and error growth.
- Run the theory POC causal prediction comparison.

### Reviewer attack

- Horizon windows crossing episodes, future leakage through features, teacher forcing at evaluation, inconsistent normalization during rollout, invalid facing vectors, cherry-picked checkpoints, history containing future contact information.

### Examiner questions

- Why residual rather than full dynamics?
- Why MLP rather than GRU?
- What exactly is inside history during imagined future steps?
- Why can multi-step training outperform one-step training for planning?

### Deliverables

- Three-model prediction table and graph.
- Reproducible training command and checkpoint manifest.
- One predicted-versus-actual trajectory panel.
- `RES-001` and `RES-002` entries.

### Stop/go gate

Do not connect residual predictions to planning until held-out recursive prediction improves in at least one decision-relevant stratum without a serious regression elsewhere. A negative outcome triggers diagnosis, not test-set tuning.

### Suggested commits

- `Add validated recursive residual rollout interface`
- `Train no-history and history residual baselines`
- `Report stratified full-horizon prediction errors`

## 8. Day 4 - CEM and control integration (Wednesday 2 September)

Branches: `feature/cem-planner`, then `feature/unreal-control-integration`

### 8.1 Offline CEM

- Implement action-knot sampling, expansion, clamping, elite selection, moment update, momentum, and warm start.
- Vectorize candidate and horizon dimensions.
- Test deterministic fixed-seed output, elite update by hand, bounds, zero-variance handling, and known toy optima.
- Visualize iterations on the theory backend.

### 8.2 Cost

- Implement terminal goal, analytic collision, clearance, first difference, and second difference terms separately.
- Test units and sign of every term.
- Visualize each cost component for simple trajectories.

### 8.3 Fair controllers

- Reactive controller for visual context.
- Nominal MPC and residual MPC share candidate noise, seeds, horizon, costs, knots, iterations, and obstacle propagation.
- Only the character transition differs.
- Execute the first 100 ms action and warm-start the next solve.

### 8.4 Unreal integration

- Connect observation -> rollout -> selection -> validated action.
- Clear history and warm start on reset.
- Add pause-mode forward/left/right/stop predictions.
- Add safe fallback for timeout or non-finite planning output.

### Reviewer attack

- Different random candidates between controllers, accidental different cost weights, obstacle data leakage, selecting highest rather than lowest cost, wrong warm-start shift, planner exploiting unclamped actions, state/history not reset.

### Examiner questions

- Derive the elite mean and variance update.
- Why use knots?
- Why execute only the first action?
- Why CEM rather than gradients?
- How is planner fairness enforced in code rather than by intention?

### Deliverables

- Offline CEM animation/plot.
- Deterministic CEM and analytic-geometry tests.
- Live nominal and residual MPC control.
- Paused counterfactual futures.
- `CEM-001` entry.

### Stop/go gate

Proceed only when nominal and residual controllers consume the exact same candidate action tensor and cost implementation, and both remain stable in obstacle-free Unreal control.

### Suggested commits

- `Add deterministic batched CEM with action knots`
- `Implement tested analytic planning costs`
- `Integrate fair nominal and residual MPC controllers`

## 9. Day 5 - frozen experiments (Thursday 3 September, morning/afternoon)

Branch: `experiment/final-evaluation`

### 9.1 Freeze before testing

- Freeze model checkpoint, normalization, planner config, cost weights, scenario definitions, and test seed manifest.
- Generate a run manifest containing every hash.
- No changes after viewing final test outcomes without starting a clearly labeled new experiment family.

### 9.2 Timed gate

- Run reactive, nominal MPC, and residual MPC on identical seeds.
- Identify cases where prediction changes the selected action.
- Report task outcome and the full causal trace.

### 9.3 Push recovery

- Apply the same impulse schedule.
- Measure from immediately after the push.
- Compare nominal, no-history residual, and history residual prediction and recovery time.

### 9.4 Held-out movement settings

- Sweep acceleration, smoothing, turn response, or push strength inside and outside training support.
- Clearly distinguish robustness to unobserved mismatch from parameter-conditioned generalization.

### 9.5 Exploitation and statistics

- Compare selected-plan predicted/realized return gaps with random in-distribution plans.
- Compute paired bootstrap intervals.
- Report counts, medians, IQRs, failures, and missing/invalid episodes.

### Reviewer attack

- Seed cherry-picking, test-set tuning, invalid paired samples, hidden controller-budget difference, survivorship bias, multiple-comparison storytelling, metric definitions changed after seeing results.

### Examiner questions

- What was frozen before the test?
- Which result supports causality rather than correlation?
- Does improved average prediction explain the successful episodes?
- What is the weakest defensible claim?

### Deliverables

- Main paired result table.
- Prediction-error graph.
- Causal trace for at least one episode.
- OOD/failure-boundary graph.
- Exploitation diagnostic.
- `CTRL-001`, `CTRL-002`, `OOD-001`, and `EXPLOIT-001` entries.

### Stop/go gate

The result is accepted whether positive or negative if the protocol is fair and reproducible. Do not reopen frozen design choices merely to turn a negative result positive.

### Suggested commits

- `Freeze final evaluation manifests and configurations`
- `Add paired controller evaluation and bootstrap reporting`
- `Record model exploitation and OOD diagnostics`

## 10. Day 6 - runtime, demo, and package (Thursday 3 September, afternoon/evening)

Branch: `release/interview-demo`

### 10.1 Visualization

- Same-seed split-screen nominal versus residual.
- Faint candidate paths, selected path, nominal/corrected/actual trajectories, obstacle vectors, and target marker.
- HUD with controller, seed, setting, prediction error, selected action, latency, collision count, and outcome.
- Actor/root trajectory diagnostic; toe sliding only if contact data is reliable.

### 10.2 Runtime

- Benchmark exact final CEM configuration after warmup.
- Report median, p95, missed deadlines, hardware, threading, and model batch dimensions.
- Apply the documented degradation policy if deadlines fail.

### 10.3 Failure demonstration

- Select one representative, predeclared or objectively chosen failure.
- Provide exact seed/config and a concise diagnosis.
- Do not hide visual or quantitative failure.

### 10.4 Packaging

Repository package:

- source without licensed sample content;
- environment/setup instructions;
- sample acquisition and Unreal project integration instructions;
- frozen configs and seed manifests;
- test command and expected summary;
- data-generation instructions and schema;
- checkpoint/normalization hashes and download location if too large;
- results tables, plots, and video;
- limitations and license/provenance notes.

Demo package:

- 60-90 second primary video;
- live-demo runbook and reset keys;
- prerecorded fallback video;
- one architecture diagram;
- one main result table;
- one prediction graph;
- one failure example;
- exact reproduction command.

### Reviewer attack

- Cold-start latency hidden, stale HUD metrics, edited videos using different seeds, missing licenses, unreproducible paths, undocumented manual steps, oversized repository, accidental raw/private data.

### Examiner questions

- What runs in Unreal versus Python?
- What is the measured end-to-end deadline?
- What would be required for production deployment?
- Which parts are research prototype limitations?

### Deliverables

- Stable live demo and fallback recording.
- `RUNTIME-001` entry.
- Release-candidate README and package manifest.
- Clean-clone or clean-worktree reproduction check.

### Stop/go gate

No ONNX, ensemble, crossing obstacle, or AnimGen work unless the central result, runtime report, video, and reproducibility package are already complete.

### Suggested commits

- `Add same-seed trajectory and metric visualization`
- `Benchmark final planner latency and deadlines`
- `Package reproducible MotionWorld interview demo`

## 11. Day 7 - defense and rehearsal (Friday 4 September, morning)

Branch: continue `release/interview-demo`; stop feature development.

No feature code may be added Friday morning. Only a demonstrated launch-blocking defect may be repaired, followed by a complete rehearsal rerun.

### 11.1 Narrative

- Rehearse 30-second, 90-second, and five-minute explanations.
- Tie every claim to a visible artifact.
- State scope and limitations before being forced to concede them.

### 11.2 Technical teach-back

- Derive coordinate transforms, nominal transition, residual composition, multi-step loss, CEM update, cost, split logic, bootstrap pairing, and latency statistics on a blank page.
- Explain every final config field and important module.

### 11.3 Hostile examination

- Daniel-style round: movement state, spring behavior, root/actor separation, responsiveness, foot sliding, runtime design, C++ ownership.
- Viktoriia-style round: action adherence, leakage, distribution shift, privileged evaluation state, ablations, causal evidence, uncertainty, failure claims.
- Coding round: implement or debug one bounded Python/C++ function without project scaffolding.

### 11.4 Demo rehearsal

- Run from a fresh launch three times.
- Practice recovery from service failure and failed scenario reset.
- Verify the prerecorded fallback and local artifact links without internet.
- Time the presentation and reserve discussion time.

### Final deliverables

- Tagged release candidate.
- Final demo/video/runbook.
- Architecture diagram, result table, prediction graph, and failure slide.
- Completed `INTERVIEW_DEFENSE.md` with evidence links.
- Final Obsidian handoff and project status.

### Acceptance checkpoint

The candidate can explain any core function in roughly one minute, reproduce every reported result, distinguish evidence from interpretation, and defend a negative result without changing the story.

## 12. Daily status format

At the end of every working block, report:

```text
Built:
Learned/derived:
Tests and evidence:
Reviewer findings:
Examiner weakness:
Decisions recorded:
Commits:
Current gate:
Blocked/risk:
Next smallest action:
```

This same compressed information is added to Obsidian task `M7UXD` so a new session can resume without relying on chat history.

## 13. Alignment with specification version 1.1

| Specification area | Execution location | Added safeguard or clarification |
|---|---|---|
| Scope, non-goals, final causal rule | Day 0 and `PROJECT_SPEC.md` | The four-link causal claim is the release criterion; negative results remain valid. |
| User-visible demo and controls | Days 4 and 6 | Live controls are implemented only after scientific gates; a prerecorded fallback is packaged. |
| Unreal architecture and feasibility | Day 1 | Version/API audit, immediate compilation, tick-order proof, and Manny plus Mover fallback are explicit. |
| State, coordinates, and observations | Days 1-2 | Known nominal spring state is separated from authoritative actor state; every context feature needs a future-rollout rule. |
| Action interface | Days 1, 2, and 4 | Bounds, units, hold duration, knot expansion, and packet safety are independently tested. |
| Nominal movement model | Day 2 | Faithful Smooth Walking state and 60 Hz substeps prevent an artificially weak baseline. |
| Residual model and training objective | Day 3 | Residual composition, facing validity, zero-residual identity, recursive history, and episode-bounded windows are gates. |
| Dataset and split discipline | Day 2 | Immutable episode/regime manifests and training-only normalization prevent leakage. |
| CEM and cost | Day 4 | Toy optima, hand elite updates, component cost tests, and identical candidate tensors enforce correctness and fairness. |
| Baselines and experimental isolation | Days 4-5 | The controller comparison differs only in transition model and shares candidate noise and compute. |
| Evaluation, robustness, and exploitation | Day 5 | Configuration freezes before test access; paired statistics, return gaps, and failure boundaries are required. |
| Unreal-Python communication | Days 1 and 4 | Version, episode, sequence, timeout, finite-value, and safe-stop behavior are tested before learned control. |
| ONNX and deployment | P1 after Day 6 gate | Scientific validity and reproducibility take priority over a deployment stretch goal. |
| Animation diagnostics | Days 1 and 6 | Actor/root traces are required; toe metrics are included only with reliable contact annotations. |
| Repository, verification, acceptance | Every branch | Component tests, branch-close review, experiment provenance, and memory handoff operationalize the specification. |
| Seven-day plan and risks | Days 0-7 | Day 0 foundation, daily stop/go gates, Reviewer attacks, Examiner questions, and fallback packaging reduce schedule risk. |
