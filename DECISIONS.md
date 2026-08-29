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

Why: Isolates risk without creating unnecessary concurrent integration work in a seven-day solo build.

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
