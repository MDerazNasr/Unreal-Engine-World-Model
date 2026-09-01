# UE 5.8 Smooth Walking implementation map

Status: version-matched source audit; implementation has not yet been ported to Python.

## Claim boundary

This maps installed UE 5.8.2 source. It does not establish the live Game Animation Sample's
Blueprint-overridden parameter values. Those must be captured from the runtime movement-mode
instance before the nominal baseline is frozen.

## Version-matched sources

- `Mover/Public/DefaultMovementSet/Modes/SmoothWalkingMode.h`
- `Mover/Private/DefaultMovementSet/Modes/SmoothWalkingMode.cpp`
- `Mover/Private/DefaultMovementSet/Modes/SmoothWalkingState.h`
- `Mover/Private/DefaultMovementSet/Modes/SimpleWalkingMode.cpp`
- `Mover/Private/DefaultMovementSet/Modes/WalkingMode.cpp`
- `Core/Public/Math/SpringMath.h`
- `Core/Public/Math/UnrealMathUtility.h`

Installed engine root: `/Users/Shared/Epic Games/UE_5.8/Engine`.

## Input preparation

`USimpleWalkingMode::GenerateMove_Implementation`:

1. Converts `StepMs` to seconds and rejects a negligible step.
2. Reads world-space movement and orientation intent.
3. Removes the component along Mover's up vector while preserving requested magnitude.
4. Converts directional intent to velocity or clamps velocity input to the configured maximum speed.
5. Initializes proposed linear/angular velocity from the authoritative starting sync state.
6. Calls Smooth Walking's `GenerateWalkMove`.

The Python action must therefore already represent the post-input-preparation planar desired
velocity, or reproduce this preparation explicitly. MotionWorld's velocity command uses the
velocity-input path, but the live maximum-speed value still needs capture.

## Persistent known internal state

`FSmoothWalkingState` contains:

- `SpringVelocity` in cm/s;
- `SpringAcceleration` in cm/s^2;
- `IntermediateVelocity` in cm/s;
- `IntermediateFacing` as a quaternion;
- `IntermediateAngularVelocity` in rad/s.

This state is copied into the output Mover sync state every simulation tick. The header is in
Mover's private source tree, so a project plugin must not include it as a public API. However,
`FMoverDataCollection` publicly exposes a const iterator over `FMoverDataStructBase`. A later,
strictly tested diagnostic can identify the script struct and read named reflected properties
without copying Epic's private struct definition. If that fails, these values must be estimated or
the remaining mismatch declared; they must not be silently omitted.

## Initialization and external-influence synchronization

When the spring state is new or `DidGenerateMove` is stale during local simulation:

- spring velocity = actual input velocity;
- spring acceleration = zero;
- intermediate velocity = actual input velocity;
- intermediate facing = current facing;
- intermediate angular velocity = zero.

Otherwise, Smooth Walking computes a clamped cosine match between spring velocity and actual
executed velocity. It exponentially moves intermediate velocity toward actual velocity using
`(OutsideInfluenceSmoothingTime + epsilon) / (1 - velocity_match)`, then overwrites spring velocity
with actual velocity. This is how collision or push mismatch influences the internal controller.

## Translational update order

Let `v_i` be intermediate velocity, `v_s` spring velocity after synchronization, `v_d` desired
velocity, and `dt` the movement step.

1. If turning strength is positive and desired velocity is nonzero, exponentially smooth `v_i`
   toward `normalize(v_d) * length(v_i)`. Turning smoothing time is `2 / TurningStrength`.
2. Acceleration branch:
   `accelerating = 1.01 * |v_d|^2 > |v_s|^2`.
3. Lateral magnitude is `(1-DirectionalFactor)*Acceleration` while accelerating, otherwise
   `Deceleration`.
4. Directional magnitude is `DirectionalFactor*Acceleration` while accelerating, otherwise zero.
5. `difference = v_d - v_i`.
6. Lateral acceleration points directly along `difference` and is limited so it cannot close more
   than the difference in one step.
7. Directional acceleration points along desired velocity.
8. Add both accelerations; use a dot-product overshoot test to choose integrated velocity versus an
   exact snap to desired velocity.
9. Clamp magnitude to `max(previous |v_i|, |v_d|)` to prevent directional acceleration from creating
   unbounded speed.
10. Repeat the integration with a future tracking interval
    `dt + compensation*smoothing_time` to obtain the spring's track velocity.
11. Critically damp spring velocity/acceleration toward that track velocity.
12. Apply velocity and acceleration deadzones; output spring velocity; store the ordinary-step
    integrated velocity as the next intermediate velocity.

## Exact smoothing kernels

Unreal's exponential approximation uses:

`inv_exp(x) = 1 / (1 + 1.00746054*x + 0.45053901*x^2 + 0.25724632*x^3)`.

For a critical spring with smoothing time `T`, `y = 2/T`, displacement `j0=x-target`, and
`j1=v+j0*y`:

`e = inv_exp(y*dt)`

`x_next = e*(j0+j1*dt)+target`

`v_next = e*(v-j1*y*dt)`

Using ordinary `exp(-y*dt)` would be close but would not be the installed-engine equation.

## Facing update

Facing uses either one quaternion spring or two cascaded quaternion springs. The default C++ mode
uses the double spring and half the configured facing smoothing time for each stage. It applies
shortest-arc quaternion differences, a facing deadzone in degrees, and an angular-velocity deadzone
converted to radians. The Mover interface receives/returns angular velocity in degrees/s, while the
spring state stores radians/s.

A planar yaw implementation may use the angle spring only after a golden comparison proves it
matches the quaternion path for yaw-only rotations and sign/wrap conventions.

## Position and collision

`UWalkingMode::SimulationTick_Implementation` computes:

`OrigMoveDelta = ProposedMove.LinearVelocity * dt`.

Therefore free-space position integration uses the newly proposed velocity for the whole step
(explicit Euler), not the trapezoidal teaching-oracle formula. Unreal then performs safe movement,
ramp deflection, step-up, slide, and impact processing. The finalized executed velocity can differ
from the proposal. The nominal model must keep free-space controller dynamics distinct from
collision/residual mismatch.

## C++ class defaults requiring live verification

- acceleration: 1500 cm/s^2;
- deceleration: 1500 cm/s^2;
- directional acceleration factor: 1;
- turning strength: 10;
- acceleration/deceleration smoothing time: 0.1 s;
- acceleration/deceleration compensation: 0;
- velocity deadzone: 0.01 cm/s;
- acceleration deadzone: 0.001 cm/s^2;
- outside-influence smoothing time: 0.05 s;
- facing smoothing time: 0.25 s;
- double-facing spring: enabled;
- facing deadzone: 0.1 degrees;
- angular-velocity deadzone: 0.01 degrees/s.

The sample asset contains Blueprint logic referencing Smooth Walking settings, including turning and
facing controls. These defaults are not treated as the live parameter record.

## Stop/go checks before Python implementation

- [ ] Capture the live movement-mode class and all reflected parameter values in one opt-in PIE trace.
- [x] Implement a safe, version-bounded `FSmoothWalkingState` diagnostic seam: iterate the public
  `FMoverDataCollection`, identify `SmoothWalkingState`, and read only five named reflected struct
  properties. The plugin never includes the private state header, fails closed on missing/type/
  non-finite values, is default-off, capped, and marks every row `model_input=false`. The actual
  sample test proves the parameter reflection and pure validation contract; a live trace is still
  required to prove the sample's runtime state entry and Blueprint overrides.
- Define planar quaternion/angle golden cases, including wraparound.
- Implement Unreal's `InvExpApprox`, not the mathematical exponential.
- Use explicit Euler position integration and six verified 1/60 s substeps for a 100 ms macro step.
- Record which collision behavior is outside the nominal transition and becomes measured mismatch.
