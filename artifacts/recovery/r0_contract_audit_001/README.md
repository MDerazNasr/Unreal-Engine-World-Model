# R0 Reconciled Contract Audit

Date: 2026-09-03
Branch: `feature/cem-runtime`
Baseline before recovery: `96d8879673300d4d53db9d8dfb0df78bac090d1e`

## Scope

This is a pre-runtime, pre-final-result review of the MotionWorld recovery contract. It checks the
current specification, configs, strict loaders, implementations, tests, frozen identities, units,
coordinate frames, and causal availability. It does not claim that live UDP control or improved
Unreal execution exists.

## Accepted contract

- Control observations originate at Mover `OnPostFinalize` on fixed 100 ms simulation-time slots.
- A matching action must arrive before the next observation and strictly before 100 ms of Unreal
  monotonic send-to-receive time. Late or superseded actions are discarded.
- Cold start is zero; misses one and two hold the last valid action; miss three commands zero.
- Each 100 ms live model step uses three equal 1/30 s substeps. Future recorded callback `dt` is
  prohibited from live CEM; recorded `dt` remains valid for retrospective training/evaluation.
- Multi-step residual training uses 15 supervision boundaries, gamma 0.9, normalized component
  Huber beta 1, residual penalty 0.01, complete within-episode windows, held start parameters,
  recursive observable/nominal-hidden state, and recursively shifted four-query history.
- Final prediction IDs 5301/5302 are separate from controller IDs 7101-7112 and remain unopened.
- The final control comparison pairs nominal and residual MPC under common scenario identity and CEM
  noise; only their transition model may differ.

## Contradictions found and corrected before results

1. **Agent geometry:** the offline 42 cm radius / 96 cm half-height assumption was wrong for the
   actual sample pawn. A UE 5.8.2 transient construction found one capsule at 30/86 cm, unit scale.
   The final manifest now uses 30/86. Historical offline evidence remains labeled 42 cm.
2. **Impossible push task:** 700 cm in 3.5 s exceeded the absolute 577.5 cm distance possible at the
   165 cm/s speed cap, even before acceleration. The push target is now 500 cm with a 6 s timeout.
3. **Push frame:** world `+Y` was not guaranteed to be lateral under a relative reset orientation.
   The kick is now reset-local `[0, 250, 0]` cm/s, rotated once with verified reset yaw, with the
   derived world vector recorded.
4. **Effect unit:** `0.10 probability points` was ambiguous. The estimand is now a proportion
   difference; 0.10 explicitly equals 10 percentage points.
5. **Collision guardrail:** collision count alone did not define the binary safety estimand. The
   manifest now includes `collision_occurred` as an episode indicator.
6. **Missing prediction strata:** 5301/5302 are free-space schedules, not contact, push, or movement-
   setting tests. Those three prediction strata are preregistered absent and must be reported absent.

## Future-information audit

- Residual features contain current state/action, causal nominal proposal, current parameters, and
  current transition duration. They exclude actual next state, target, obstacle, event label,
  outcome, and later parameter snapshots.
- Recursive training uses recorded future actions and durations only because it is reconstructing an
  already observed training trajectory. Deployment CEM supplies candidate actions and fixed causal
  substeps instead.
- Gate state, goal, and scenario identity may enter planner cost/protocol context but not character
  residual features.
- The controlled push is unknown before application. Prediction/recovery evaluation begins from the
  first authoritative state after the disturbance; the event schedule is never a dynamics input.

## Unit and frame audit

- Distance: cm. Velocity: cm/s. Acceleration/deceleration: cm/s^2. Time: s internally and explicit
  ms at the network deadline. Facing: rad internally and deg only in declared report interfaces.
- Actions, targets, gate-relative geometry, and declared push use the reset/current character-local
  frame as specified; authoritative position and applied perturbation are recorded in world space.
- Capsule and gate values are half-extents where stated. Signed clearance is cm; negative means
  penetration.
- Success difference and collision difference are paired episode-indicator proportion differences.

## Known risks that remain honest, non-contradictory blockers

- The full residual CEM path still exceeds the 100 ms runtime gate. A positive final claim is
  impossible unless later R5 work passes the frozen runtime/quality gate.
- Multi-step checkpoints do not exist yet; their hashes remain pending until R4 training and must be
  frozen before R7 unsealing.
- Live protocol/runtime behavior is not implemented; that work begins only after R0 is committed.
- The headless capsule query verifies the constructed class geometry, not a completed paired live
  scenario. The configuration-driven runner must re-verify it before each final collection family.
- With 12 planned pairs, bootstrap intervals will be discrete and may be wide. An interval crossing
  zero is unresolved, not evidence of equivalence.

## Gate result

Passed. The reconciled pre-runtime contract is commit `9e9c269`. Final-test bytes opened: zero.
No R1 protocol implementation began before this commit.
