# V2 Moving-Obstacle World-Model Demo Checklist

## Goal and truthful claim

Build a short, reproducible Unreal demo in which a character reaches a visible target while avoiding one physically collidable, deterministically moving obstacle. A nominal dynamics world model predicts future character and obstacle motion; CEM searches candidate action sequences; the controller executes only the first action and replans from the next authoritative Unreal observation at 10 Hz.

The learned residual model is a prediction overlay, not the action owner. The obstacle motion is seed-labelled and reproducible, not unpredictable randomness.

## A. Preserve the fallback

- [x] Freeze V1 in commit `2d6f005` and annotated tag `demo-v1`.
- [x] Record the V1 fallback and stop the recording at the target.
- [x] Restore Unreal from the temporary V1/D6 recording configuration.
- [x] Create the isolated branch `feature/obstacle-demo-v2`.

## B. Freeze the V2 contract

- [x] Reuse the existing timed-gate actor and analytic sinusoidal motion.
- [x] Keep one obstacle; skip a new multi-obstacle/procedural system.
- [x] Make Unreal's transmitted scenario time, phase, origin, axis, amplitude, period, and extents the prediction truth.
- [x] Keep the Python controller as the sole action owner and the 100 ms exclusive deadline.
- [x] Add a separate V2 configuration without weakening or changing V1.
- [x] Add a target-arrival latch so the character remains stopped at the end.

## C. Make the world-model planner obstacle-aware

- [x] Load the V2 moving-obstacle cost and geometry.
- [x] Require a present timed-gate context and verify its live geometry matches the frozen V2 configuration.
- [x] Predict obstacle centers at every future planning step from authoritative scenario time.
- [x] Use swept collision, clearance, goal, and action-smoothing costs.
- [x] Preserve receding-horizon behavior: apply only the first planned action.
- [x] Add focused unit tests for configuration, timing, avoidance, fallback, and arrival stop.
- [x] Run the focused Python tests and the full Python test suite.
- [x] Skip a separate offline tuning study after the real live loop produced a collision-free,
      decisive dodge; this saves time without weakening the demo evidence.

## D. Integrate the physical Unreal obstacle

- [x] Enable the existing runtime-spawned collidable obstacle only in V2.
- [x] Give it a clearly visible red demo appearance.
- [x] Allow a collision-free gate-plane crossing to continue toward the target in V2; keep collision terminal.
- [x] Preserve the original default terminal behavior outside V2.
- [x] Add focused Unreal automation coverage.
- [x] Build the plugin and the actual Game Animation Sample editor target.
- [x] Run the complete 20-test `MotionWorld.` Unreal automation suite.

## E. Assemble and validate the live demo

- [x] Apply a reversible V2 Blueprint/demo manifest with exact readback and a recovery backup.
- [x] Place the target behind the moving obstacle and frame both clearly in camera.
- [x] Start the Python service with the frozen V2 configuration.
- [x] Preserve the rejected missing-context attempt and audit the first valid tuning attempt.
- [x] Confirm obstacle motion, visible avoidance, no collision, arrival-zone entry, and stable stop.
- [x] Confirm nominal-MPC command ownership, valid identity admission, zero malformed packets, and
      fail-safe handling of missed/stale replies.
- [x] Extend only the scenario cutoff from 14 to 20 seconds after the first valid attempt passed the
      obstacle collision-free but timed out before the target; do not change the successful geometry.

## F. Polish and hand off

- [x] Show the red obstacle, green target, blue nominal prediction, orange learned comparison, gray
      candidates, and yellow actual trail clearly.
- [x] Freeze the successful configuration, exact launch commands, and evidence summary.
- [x] Run final Python and Unreal regression checks.
- [x] Update the interview questions-and-answers notes with the V2 concepts.
- [x] Give the user a simple recording script and narration.
- [ ] User records the final demo manually.

## Accepted live V2 result

Session `80F4B74AFD4E`, episode `7701`, used the 20-second V2 manifest. The character
started at `(-800, 0, 90)`, passed the moving gate, entered the 100 cm target-arrival zone, and
stopped stably at approximately `(724.77, 34.56, 88.27)`, 82.78 cm from the target at
`(800, 0, 90)`. Unreal reported `collision_count=0`. The later arena timeout occurred only because
the validation run was intentionally left playing after the arrival stop. The network summary was
480 observations, 407 accepted actions, 58 stale rejections, 73 missed replies, 26 safe stops,
zero malformed packets, and zero evidence drops. Missed/stale responses failed safe and never became
current movement commands.

## Explicitly deferred because they do not improve the final demo enough

- Multiple independently moving obstacles.
- Retraining the learned residual model.
- Letting the learned residual model control the character.
- Research-scale paired evaluation and statistical superiority claims.
- Procedural level generation, perception from pixels, and broad UI redesign.
