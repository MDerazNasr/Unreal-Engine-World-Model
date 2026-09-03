# MotionWorld Project Specification

Status: living contract  
Primary source: `MotionWorld_Project_Specification.pdf`, version 1.1  
Rule: update this file before intentionally changing the implemented system.

## 1. Research question

Can a learned residual dynamics model correct the remaining error of a faithful, inexpensive Unreal character predictor well enough to improve real-time, short-horizon planning?

The supported positive claim requires every link below:

1. The nominal model has a reproducible prediction error.
2. The residual model predicts that particular error on held-out episodes.
3. Corrected rollouts change the selected action under an otherwise identical planner.
4. The changed action improves same-seed Unreal execution.

Better prediction alone is not evidence of better control. Better control relative only to a reactive controller is not evidence that the residual helped.

## 2. Product and research boundary

### P0 - required

- Unreal Engine 5.7 or 5.8 Game Animation Sample with Mover Smooth Walking, with Manny plus Mover as the explicit fallback.
- Deterministic scenario reset and episode logging.
- Authoritative actor/capsule state separated from animation-root and foot telemetry.
- Faithful, inexpensive nominal Smooth Walking predictor.
- Residual MLP without history and residual MLP with four observations of history.
- Batched Cross-Entropy Method planner.
- Reactive, nominal-MPC, and residual-MPC controllers.
- Timed-gate, post-push recovery, and held-out movement-setting evaluations.
- Same-seed nominal-versus-residual demo with nominal, corrected, and actual paths.
- Fixed configs, fixed test seeds, paired statistics, latency reporting, and one honest failure case.

### P1 - only after every P0 gate passes

- Crossing obstacle.
- Small residual ensemble or uncertainty penalty.
- Reliable contact-conditioned toe-sliding metric.
- ONNX export and numerical parity.

### P2 - explicitly outside the one-week critical path

- AnimGen integration.
- Native Unreal inference.
- Pose generation or animation-controller replacement.
- Language/style controls.
- Multiple learned agents or a visual/video world model.
- Oracle planning through cloned Unreal simulations.

## 3. System boundary

### Unreal owns

- Authoritative movement and collision state.
- Scenario lifecycle, obstacles, impulses, success, timeout, and collision events.
- Application of validated desired-velocity commands.
- Animation execution and animation-quality telemetry.
- Debug trajectory and metric visualization.

### Python owns

- Dataset validation and preprocessing.
- Nominal dynamics test implementation.
- Residual models and recursive rollouts.
- Analytic cost and obstacle propagation.
- CEM planning.
- Training, evaluation, statistics, plots, and the localhost planning service.

### Communication

- Versioned localhost UDP messages at 10 Hz for P0.
- Every packet carries episode and sequence identifiers.
- Unreal rejects malformed, wrong-episode, and stale actions.
- Control protocol v1 is named `motionworld_control`. An observation is bounded to 16,384 bytes of
  canonical UTF-8 JSON and contains episode/control/state sequence identity, simulation time and
  the 100 ms interval, controller/source labels, finalized world/local state, aligned causal Smooth
  Walking parameters and internal state, the previous applied action identity, reset/scenario/
  termination identity, and explicit validity flags. Target and deterministic current/immutable
  timed-gate context occupy a separate planner-only branch that is removed before dynamics-model
  feature construction. Animation data, actual next state, later parameter snapshots, future push
  events, and outcome labels are excluded from dynamics inputs.
- An action is bounded to 8,192 bytes of deterministic compact UTF-8 JSON. It echoes protocol,
  episode, and source-observation identity; carries one character-local planar desired velocity,
  controller/model identity, Python monotonic planner timestamps and their measured latency, and
  explicit safe-fallback status/reason. An optional diagnostic branch contains at most 32 selected
  local trajectory actions and the six declared cost terms. Diagnostic trajectory and costs never
  participate in command application.
- P0 uses one strict RFC 8259 JSON object per IPv4 loopback UDP datagram. Unreal binds
  `127.0.0.1:52580`; Python binds `127.0.0.1:52581`. These endpoints and all bounds live in
  `configs/control_transport.yaml`, not developer paths. JSON text has no byte-order field; finite
  numbers become binary64 after parsing, and integer identities/timestamps are limited to the exact
  binary64 range `0..2^53-1`. Planner monotonic timestamps are integer microseconds.
- Both endpoints are nonblocking and drain at most 16 datagrams per poll. A full UDP receive buffer
  is capped at 65,507 bytes; empty, wrong-sender, truncated/oversized, malformed, and unsupported
  messages are discarded before gameplay mutation. UDP loss is not retransmitted. Duplicate and
  reordered actions are rejected by episode/current-observation admission, and an absent valid
  response reaches the existing deadline/fallback policy.
- The standalone Python service loads `configs/control_service.yaml` plus relative runtime/transport
  contracts, binds only the declared loopback endpoint, validates every observation before planner
  dispatch, and exposes bounded in-process health/readiness/counter diagnostics without packet
  contents. It tracks a bounded set of episode identities and only the newest observation request.
  A newer valid observation cooperatively cancels active work, replaces queued work, and makes every
  older completion ineligible for transmission. Shutdown closes the socket first, cancels pending
  work, and waits only the configured bounded interval. The R2.1 command-line default emits an
  explicit zero `planner_error` fallback; it is not presented as the later echo or MPC controller.
- The first valid `OnPostFinalize` state after reset defines control slot zero. Thereafter Unreal
  emits the first valid finalized state at or after each fixed 100 ms simulation-time boundary. If
  multiple boundaries elapse, it emits only the latest slot and never sends a catch-up burst.
  Observation sequence increments once per emitted observation; skipped slots are diagnostics, not
  phantom sequence entries.
- An action is valid only if Unreal receives it less than 100 ms after sending its matching
  observation and before emitting the next observation. The 100 ms boundary is exclusive; late or
  superseded results are discarded rather than applied to a newer state.
- A validated current action is applied immediately on receipt and held until a newer validated
  action or the fallback policy replaces it. Thus observations/replans are scheduled at 10 Hz;
  network response latency determines the within-slot action-application instant.
- Cold start commands zero velocity. After one or two consecutive slots without a valid matching
  action, Unreal holds the last valid action; the third consecutive miss commands a safe zero stop.
  A current valid action clears the miss count.
- Reset, controller switch, shutdown, and service reconnection clear sequence, pending deadline,
  held-action, and consecutive-miss state.
- Unreal rejects a validly shaped action unless it answers the one current outstanding observation,
  has not already been accepted, and arrived before the separately measured Unreal deadline.
  Irrespective of Python validation, the existing Unreal command-production path converts local to
  world space, projects to the plane, rejects non-finite input, and magnitude-clamps the command.

## 4. State and coordinates

### Authoritative state

The authoritative planning state is sampled after the movement tick:

`s = [global_position_xy, local_velocity_xy, facing_sin_cos, angular_velocity]`

The actor/capsule and Mover state are the single source of truth. Animation root and toe transforms are diagnostics and never substitute for gameplay state.

### Known nominal internal state

The nominal predictor also carries the known Smooth Walking internal state required by its equations, including acceleration, intermediate velocity, intermediate rotation, and intermediate angular velocity where applicable. This internal state is not silently delegated to the residual network.

At every real observation boundary, the synchronization policy for nominal internal state must be explicit, tested, and recorded in `DECISIONS.md`.

### Conventions

- Unreal X is forward and Y is right.
- Authoritative global position is retained for integration and goal tests.
- Velocities, actions, target vectors, and obstacle-relative features use the character-local frame at the model boundary.
- Facing uses sine/cosine for input; learned facing output uses a normalized representation or a scalar yaw increment.
- Model steps are 100 ms. Live planning uses exactly three equal `1/30 s` nominal/residual
  substeps per model step. Recorded-`dt` replay remains a retrospective accuracy oracle only:
  future Unreal callback durations are unavailable to a causal planner. Residual training and
  prediction evaluation use each recorded transition's actual `dt`; the residual feature schema
  includes `dt`, and the selected `1/30 s` deployment value lies inside accepted training support.
- Units are centimeters, seconds, radians internally unless an interface explicitly declares degrees.

## 5. Action

P0 action:

`a = [desired_local_velocity_x, desired_local_velocity_y]`

- Magnitude is clamped to the active maximum speed.
- The action is held for one 100 ms control interval.
- The planner optimizes four or five knots rather than fifteen unrelated frame actions.
- Facing follows movement direction in P0.

## 6. Transition models

### Nominal

`s_nom[t+1], z_nom[t+1] = f_nominal(s[t], z_nom[t], a[t], parameters)`

The nominal model implements known Smooth Walking behavior rather than an intentionally weak approximation. It includes acceleration/deceleration selection, directional acceleration, turn response, velocity smoothing, rotation dynamics, integration, and required internal spring state.

### Residual

`delta[t] = r_theta(history[t], s[t], a[t])`

`s_hat[t+1] = compose(f_nominal(s[t], z_nom[t], a[t]), delta[t])`

The composition rule must preserve coordinate and facing validity. Target and obstacle features are excluded from character dynamics unless a later, documented ablation demonstrates they are required. Their geometric influence belongs in the planner cost.

P0 network: MLP with hidden widths 256, 256, and 128, SiLU activations, fewer than approximately 500,000 parameters. LayerNorm is added only in response to observed instability.

### History rollout contract

The four-observation history buffer covers about 0.4 s. During imagined rollouts it is shifted autoregressively using predicted state and candidate action. Any context that cannot be advanced consistently, including contact timing, must either be derived analytically, predicted and evaluated, or removed from P0 inputs. It must never be silently frozen.

## 7. Training

- Split complete episodes and scenario regimes, never individual transitions.
- Train recursively over the planning horizon, not only for one-step error.
- Compare nominal, residual without history, and residual with four-step history.
- Store normalization statistics, feature schema version, config, seed, Git commit, and checkpoint hash.
- Stop increasing data after validation performance saturates.

Primary objective:

`L_state = sum(k=1..H) gamma^(k-1) * Huber(s_hat[t+k], s[t+k])`

`L_total = L_state + lambda_residual * mean(||delta||^2)`

For the recovery multi-step run, `H=15` supervision boundaries at 100 ms intervals over 1.5
seconds, `gamma=0.9`, normalized component Huber `beta=1.0`, and
`lambda_residual=0.01`. Training advances through recorded causal actions and recorded transition
durations, holds the rollout-start parameter snapshot, and rejects starts without a complete
1.5-second within-episode horizon. Four-history starts with three real past queries and shifts in
predicted causal queries thereafter. Exact optimizer and clipping choices are frozen in
`configs/residual_multistep_training.yaml` before training.

## 8. Planning

- Replan at 10 Hz over 1.2-1.5 s.
- Begin with 256 candidates, 32 elites, and three CEM iterations.
- Warm-start from the shifted previous solution.
- Nominal and residual MPC use identical seeds, candidate actions, horizon, cost, obstacle information, and compute budget.
- Only the transition model may differ in the decisive comparison.

The initial cost combines terminal goal distance, analytic collision, analytic clearance, action change, and action second difference. All terms, units, and weights must be tested and logged.

## 9. Evaluation

### Prediction

- Position, velocity, facing, and angular-velocity error at 0.5, 1.0, and 1.5 s.
- Final prediction episodes 5301/5302 are sealed free-space schedules. Near-contact, post-push,
  and held-out-setting prediction strata are preregistered as absent from those episodes and must
  be reported as absent, not inferred from unrelated controller runs.
- Recursive rather than teacher-forced evaluation.

### Control

- Success and collision rates.
- Time to goal and minimum clearance.
- Push-recovery time.
- Selected-plan predicted-versus-realized return gap.

### Runtime

- Median and p95 planning latency.
- Missed 100 ms planning deadlines.
- Exact candidate, iteration, horizon, device, and batch configuration.

### Statistics

- Identical fixed test seeds for each controller.
- Paired bootstrap confidence intervals for nominal MPC versus residual MPC.
- Episode count, medians, and interquartile ranges.
- Test seeds remain frozen and are never used for tuning.
- The primary estimand is the mean paired timed-gate success-proportion difference, residual MPC
  minus nominal MPC, over 12 fixed scenario identities. At least 10 complete pairs are required. Use 10,000
  paired percentile-bootstrap resamples with seed 20260905 and a 95% interval.
- A positive result requires an observed improvement of at least 0.10 (10 percentage points), a primary interval strictly
  above zero, no collision-rate increase under the frozen guardrail, residual end-to-end p95 below
  the exclusive 100 ms deadline, and evidence for all four causal links. Significant harm or a
  failed safety/runtime guardrail is negative; every other outcome is unresolved.
- Collision, timeout, missed deadline, safe fallback, and failure to recover are controller results,
  not infrastructure exclusions. Fewer than 10 valid pairs makes the scenario unresolved; seeds
  are never substituted after results are seen.

Exact episode schedules, paired seeds, reset tolerances, geometry hypotheses, scenario parameters,
metric units, retry rules, and interpretations are frozen in
`configs/final_prediction_manifest.yaml` and `configs/final_control_manifest.yaml`. The expected
30 cm capsule radius and 86 cm half-height were verified by transiently constructing the actual
`SandboxCharacter_Mover` Blueprint in UE 5.8.2. Historical offline planning artifacts used a
provisional 42 cm radius and remain unchanged as historical evidence; all final-control planning
must use the verified geometry.

## 10. Demo acceptance

The interview demo must show:

- Nominal and residual MPC side by side from the same seed and schedule.
- Nominal prediction, residual-corrected prediction, and actual execution together.
- A paused forward/left/right/stop intervention view.
- Active controller, seed, movement setting, prediction error, selected action, latency, collision count, and task outcome.
- One successful causal example and one reproducible limitation or failure.

## 11. Integrity rules

- Never invent Unreal APIs; verify against version-matched official documentation and compile immediately.
- Never report fabricated or manually transcribed metrics as experiment output.
- Never change a test scenario to manufacture a positive residual result.
- Never tune on held-out test seeds.
- Never describe prediction as physical understanding without a targeted evaluation.
- A negative result is retained, diagnosed, and presented honestly.
