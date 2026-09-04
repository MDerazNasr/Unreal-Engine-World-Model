# V3 Two-Obstacle Demo Checklist

## Goal

Extend the accepted V2 live demo to two physically collidable, authoritatively synchronized moving
obstacles. The nominal world-model MPC must visibly alter its route at both obstacles, reach the
green target zone, and stop stably. Learned residual output remains a prediction-only overlay.

## A. Preserve the accepted fallback

- [x] Keep V1 frozen at tag `demo-v1` / commit `2d6f005`.
- [x] Keep accepted one-obstacle V2 frozen at commit `ce68698`.
- [x] Stop the V2 service, close Unreal, and successfully restore its reversible Blueprint settings.
- [x] Create isolated branch `feature/two-obstacle-demo-v3`.

## B. Freeze the two-obstacle contract

- [x] Define exactly two obstacle identities and full analytic schedules.
- [x] Preserve legacy absent/single-obstacle observation compatibility.
- [x] Require V3 to receive exactly two finite, authoritative obstacle records.
- [x] Keep Unreal simulation time as chronology and monotonic wall time as the action deadline.
- [x] Keep nominal CEM as the sole action owner and first-action-only execution.

## C. Implement Unreal authority

- [x] Spawn two differently colored physical `BlockAllDynamic` obstacles only in V3.
- [x] Give the obstacles separated crossing planes and visibly different deterministic motion.
- [x] Reset, advance, freeze, and destroy both through one arena lifecycle.
- [x] Treat collision with either obstacle as terminal and count it once.
- [x] Serialize both exact analytic states/configurations with explicit identities.
- [x] Add focused C++ lifecycle and serialization tests.

## D. Extend Python world-model MPC

- [x] Strictly validate the two-obstacle payload and legacy first-obstacle mirror.
- [x] Reproduce each transmitted center/velocity from its analytic schedule.
- [x] Predict both obstacle centers at every CEM horizon step.
- [x] Sum swept collision and clearance cost across both obstacles.
- [x] Fail safe on missing, duplicate, inconsistent, or drifting V3 obstacle context.
- [x] Preserve blue nominal, orange learned, and yellow actual paths; deliberately remove only the
      optional gray candidate paths after live evidence showed they consumed deadline margin.
- [x] Add focused configuration, protocol, geometry, determinism, and safe-stop tests.

## E. Configure and validate

- [x] Add a separate reversible V3 manifest and planner configuration.
- [x] Choose geometry that produces two readable steering decisions rather than an impossible trap.
- [x] Verify exact Blueprint apply/readback and preserve a recovery backup.
- [x] Run 798 Python tests, Ruff, diff integrity, the universal Unreal build, and all 20 Unreal tests.
- [x] Run ordinary V3 tuning episodes and retain the collision attempt honestly.
- [x] Accept only if both obstacles move, both affect the route, collision count is zero, the target
      zone is reached, and the final stop is stable.

## F. Handoff

- [x] Freeze the accepted V3 commit, live evidence summary, launch/restore commands, and Q&A.
- [x] Leave Unreal and the Python service ready for the user's manual recording.
- [ ] User records and stops immediately after stable target-zone arrival.

## Accepted live result

Session `149FAA6F1546`, episode `7801`, is the accepted optimized V3 run. The character crossed the
primary region from approximately y=+60 to y=-16, crossed the second obstacle near y=-33, curved
back toward the goal, and latched a stable zero command at `(737.58,57.78,88.27)`, 85.06 cm from
target center. Unreal reported `collision_count=0`. The later timeout happened only because the
validation run was intentionally left playing after arrival. Network evidence recorded 442
observations, 340 admitted actions, 83 stale rejections, 101 missed responses, 31 safe stops, zero
malformed packets, and zero evidence drops. The earlier unoptimized collision replay is retained as
a real failed outcome; it also proves physical contact with obstacle one terminates and freezes both.

## Deliberately deferred

- Stochastic or adversarial obstacle motion.
- More than two obstacles.
- Pixel perception or learned obstacle dynamics.
- Learned residual action ownership or statistical superiority claims.
