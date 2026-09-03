# MotionWorld Theory Notebook

Status: living teaching document  
Ownership rule: the candidate must be able to derive, calculate, or explain every section without relying on generated prose.

## 1. What a world model means here

A world model predicts how the part of the environment relevant to a decision changes under an action. MotionWorld predicts a deliberately narrow state: authoritative planar character motion over a short horizon. It is not a visual world model and does not claim to model the whole Unreal scene.

The action-conditioned Markov form is:

`s[t+1] = f(s[t], a[t])`

When the observed state omits controller memory, recent history approximates a belief about hidden state:

`s[t+1] = f(h[t], s[t], a[t])`

History does not make an unpredictable future push predictable. It can expose the consequences after the push occurs.

## 2. Coordinate frames

Let global planar vector `x_g` be expressed in Unreal world axes. For character yaw `psi`, define:

`R(psi) = [[cos(psi), -sin(psi)], [sin(psi), cos(psi)]]`

Local to global:

`x_g = R(psi) x_l`

Global to local:

`x_l = R(psi)^T x_g`

Required hand check: at `psi = 90 degrees`, confirm which world direction local forward maps to under Unreal's X-forward, Y-right convention. A unit test, not memory, is the authority on sign.

For a local planar vector `x_l = (f, r)`, where `f` is forward and `r` is right:

`x_world = (cos(psi) f - sin(psi) r, sin(psi) f + cos(psi) r)`

At `psi = 90 degrees = pi/2 radians`, `cos(psi) = 0` and `sin(psi) = 1`. Therefore local forward velocity `(200, 0) cm/s` becomes world velocity `(0, 200) cm/s`. Local right `(0, 200) cm/s` becomes world `(-200, 0) cm/s`.

A vector has direction and magnitude but no location, so rotation is sufficient. A point also needs a world origin `o_world`:

`p_world = o_world + R(psi) p_local`

For `o_world = (1000, 500) cm`, `psi = 90 degrees`, and `p_local = (200, 0) cm`, the result is `p_world = (1000, 700) cm`. Subtract the origin before applying `R(psi)^T` to reverse the conversion.

The Python boundary requires an explicit `YawRadians` value. Unreal degrees enter through `YawRadians.from_degrees`; passing a bare number fails rather than silently interpreting degrees as radians.

## 3. Minimal velocity update proof of concept

Before implementing Smooth Walking springs, test a scalar bounded update:

`delta_v = clip(v_desired - v, -a_max * dt, a_max * dt)`

`v_next = v + delta_v`

`p_next = p + 0.5 * (v + v_next) * dt`

Hand calculation:

- `v = 200 cm/s`
- `v_desired = 500 cm/s`
- `a_max = 800 cm/s^2`
- `dt = 1/60 s`
- maximum change = `13.333 cm/s`
- `v_next = 213.333 cm/s`
- `p_next - p = 3.444 cm`

The implementation optionally limits the requested target speed before applying the acceleration
bound:

`v_desired_limited = clip(v_desired, -v_max, v_max)`

This does not erase an observed velocity above `v_max`. For example, an external push may make the
character faster than the normal target limit; the oracle then decelerates toward the limited target
at no more than `a_max` instead of teleporting the velocity back inside the range.

This is a one-dimensional unit-test oracle, not the final nominal model. Batched inputs represent
independent scalar examples, not the X and Y components of a realistic planar acceleration rule. It
does not include directional acceleration, Smooth Walking springs, facing dynamics, collisions, or
hidden controller state.

### Deterministic synthetic 2D backend

`SYNTHETIC / NOT UNREAL EVIDENCE`

The toy backend exists to test reset, hidden-state mismatch, event ordering, pushes, and episode
logging before those pieces depend on expensive Unreal collection. Its observable state is planar
position, planar velocity, scenario time, and step index. Its deliberately exposed hidden state is
a lagged target velocity `h`:

`alpha = 1 - exp(-dt / tau)`

`h_next = h + alpha * (action - h)`

The executed velocity moves toward `h_next` under a vector-magnitude acceleration limit. Position
uses the average pre/post-update velocity. A configured push adds a deterministic velocity impulse
at one declared step. The moving gate uses the absolute-time sinusoid from Section 19, and collision
has priority over crossing and timeout. A swept segment check prevents a fast discrete step from
jumping through the expanded gate box.

Reset seed controls the initial lateral offset and gate phase. The same configuration, seed, episode
ID, and actions must produce an exactly equal immutable episode record. This proves pipeline
determinism in the toy system only. It cannot prove Unreal API correctness, Mover fidelity, useful
residual structure in real data, or improved real control.

## 4. Faithful nominal dynamics

The final nominal predictor carries known internal spring state:

`s_nom_next, z_nom_next = f_nominal(s, z_nom, a, params)`

The smallest verified damping primitive follows UE 5.8 rather than substituting the textbook
exponential. With smoothing time `T`, `y=2/T`, displacement `j0=x-target`, rate term
`j1=v+j0*y`, and `e=InvExpApprox(y*dt)`:

`x_next = e * (j0 + j1*dt) + target`

`v_next = e * (v - j1*y*dt)`

“Critically damped” means the state approaches its target quickly without oscillating around it.
For yaw-only ground motion, an executed UE 5.8 parity test shows that applying this equation to the
wrapped shortest angle matches the engine's quaternion spring. This claim does not extend to pitch,
roll, or arbitrary 3D rotation.

`z_nom` may contain acceleration, immediate/intermediate velocity, intermediate rotation, and intermediate angular velocity. Omitting known state can make the learned model appear useful only because the baseline was unfairly simplified.

The movement model is not assumed delta-time invariant. A 100 ms planner transition is therefore composed from verified smaller simulation steps:

`f_100ms = f_16.67ms composed six times`

The installed UE 5.8 implementation map is recorded in
`research/ue58_smooth_walking_map.md`. A key distinction from the teaching oracle is position
integration: free-space Walking Mode applies the newly proposed linear velocity for the whole step,
`p_next = p + v_proposed*dt`. Collision, ramp, step, and slide resolution can then change the
finalized execution. The faithful port must also reproduce Unreal's rational `InvExpApprox` spring
kernel rather than silently substituting the mathematical exponential.

There is also a known transformation between the recorded velocity request and Smooth Walking's
actual target. `SimpleWalkingMode` clamps a velocity input to its effective maximum movement speed:

`v_desired = clamp_norm(v_recorded, max_speed_effective)`

`max_speed_effective` comes from a non-negative `MaxSpeedOverride`; otherwise it comes from the
active shared `UCommonLegacyMovementSettings`. This value is part of the known nominal context, not
a residual. The first all-row evaluation exposed this boundary cleanly: equations matched until the
intermediate target reached 165 cm/s, then diverged if the recorded 200 cm/s request was used
directly. Supplying an explicit 165 cm/s limit restored non-contact one-step velocity agreement to a
maximum error of about `3.12e-6 cm/s`. The current schema does not yet record that limit, so 165 is
labelled evaluator input rather than deployable evidence.

The nominal internal state is now version-bounded and typed as:

`z = [spring_velocity_world(3), spring_acceleration_world(3),`
`intermediate_velocity_world(3), intermediate_facing_world_quat(4),`
`intermediate_angular_velocity_world_rad_per_sec(3)]`.

The live sample also proves that `params` is `params_t`, not one constant vector. The active
`BP_MovementMode_Walking_C` changed acceleration, deceleration, and facing smoothing during a
single human-controlled trace. Therefore the nominal transition accepts an explicit parameter
snapshot/schedule. Using future recorded values is allowed only as a labelled oracle diagnostic;
the deployable planner must obtain or causally select parameters from information available at the
planning step. Silently freezing them across a rollout would create another hidden model mismatch.

Questions to master:

- Why do acceleration and deceleration need different branches?
- What does directional acceleration change during a turn?
- Why can a velocity spring require intermediate state?
- Why must an external push update both visible and spring state?
- Why is the recorded request not necessarily Smooth Walking's desired velocity?
- What error appears if 100 ms is evaluated as one large step?

## 5. Residual dynamics

Nominal prediction:

`s_nom[t+1] = f_nominal(s[t], z[t], a[t])`

One-step target:

`delta_target[t] = difference(s_unreal[t+1], s_nom[t+1])`

Corrected prediction:

`s_hat[t+1] = compose(s_nom[t+1], r_theta(h[t], s[t], a[t]))`

Why residual learning can help:

- Known structure is handled analytically.
- The network spends capacity on systematic mismatch.
- Zero output has a meaningful interpretation.
- The nominal model remains usable when uncertainty is high.

Why it can fail:

- The nominal model is already accurate enough.
- Residual targets contain noise rather than repeatable structure.
- Dataset actions do not cover planner-selected actions.
- Recursive rollouts leave the training distribution.
- The model learns target/scenario correlations rather than dynamics.

## 6. Recursive rollout and compounding error

One-step evaluation supplies the real state at every transition. Planning cannot do that. It recursively feeds predictions back into the model:

`s_hat[t+k+1] = F_theta(s_hat[t+k], a[t+k])`

A small velocity bias accumulates into position error; that new position can change collision cost and drive the planner toward increasingly unrealistic trajectories. Therefore the training and evaluation interface must match recursive planning.

For variable Unreal timesteps, MotionWorld accumulates the recorded `delta_t` values and evaluates at
the first finalized boundary at or after the requested horizon. It reports both values. A 0.5-second
request might therefore represent 0.518 seconds of actual simulated time, but it never pretends that
a fractional Unreal state was observed between boundaries.

An open-loop evaluation is allowed to know the future action sequence because those are the
interventions whose consequences we are testing. It is not allowed to know intermediate future
states. Episode-4101 evaluation initializes `(s_hat,z_hat)` once, then advances:

`(s_hat[k+1], z_hat[k+1]) = f_nominal(s_hat[k], z_hat[k], a[k], theta[k], delta_t[k])`

The recorded `theta[k]` values are labeled retrospective. Using them diagnoses equation fidelity but
does not prove that an online planner can predict future Blueprint regime switches. A dedicated test
corrupts an intermediate recorded state and verifies that a rollout beginning earlier is unchanged;
this catches accidental teacher forcing.

Zero-residual invariant:

`r_theta(.) = 0` must make the corrected rollout numerically equal to the nominal rollout.

### Planar residual representation

For the first deployable model, the residual has six ordered components:

`r = [delta_p_local_x_cm, delta_p_local_y_cm, delta_v_local_x_cm_s,`
`     delta_v_local_y_cm_s, delta_yaw_rad, delta_yaw_rate_rad_s]`

The planar position and velocity differences are rotated into the coordinate frame of the previous
observed facing, not the unknown next facing. This makes the target causal and gives the same physical
meaning to “forward” and “sideways” corrections when the character turns in world space. The yaw
target is the shortest signed angular difference from nominal to actual, so a transition from
`+179 degrees` to `-179 degrees` is a `+2 degree` correction rather than `-358 degrees`.

Composition rotates the first four components back to world space and adds them to the nominal
position and velocity. It adds and wraps the yaw correction and converts yaw-rate correction from
radians/second to the nominal state's Unreal-facing degrees/second representation. Vertical motion
and simulation time are deliberately outside this planar contract; a mismatch in either fails closed
instead of being silently discarded. An exactly zero six-vector returns the nominal state itself, so
turning learning off is an exact baseline identity. Numeric normalization scales are not chosen yet:
they must be fitted using training episodes only after episode-level splits are frozen.

### Causal residual inputs

Each residual query is a frozen 28-value vector. It contains current local velocity/yaw rate, the
candidate local desired velocity/facing delta, the nominal model's local position/velocity/facing
change and yaw rate, `delta_time_s`, and all 15 current Smooth Walking parameters. The no-history
model receives one such vector. The history model receives exactly four consecutive vectors flattened
oldest-to-current, for 112 inputs.

Absolute world position and heading are omitted because free-space character dynamics should be
translation- and rotation-invariant. Goal, gate geometry, episode time, future parameter snapshots,
contact labels, and external-event labels are omitted because they either belong to planner cost or
would let the model exploit scenario/timeline correlations. During a future recursive rollout, the
predicted state and candidate action can create the next 28-value query; the four-query history then
shifts forward. This advancement still requires a dedicated rollout test before it is complete.

### Initial residual MLP

Both comparisons use three hidden layers of widths 256, 256, and 128 with SiLU activations, followed
by six residual outputs. The current-query model has 106,886 trainable parameters; the four-query
model has 128,390 because only its first layer is wider. SiLU is a smooth nonlinearity
`SiLU(x) = x * sigmoid(x)`. Unlike a hard ReLU, it retains a small smooth gradient for negative
inputs, which is useful for continuous dynamics.

The output layer's weights and bias start at exactly zero. Therefore every untrained prediction is
the zero residual and the complete system initially equals the nominal model. Earlier hidden layers
still receive ordinary random initialization; after the first update changes the output layer,
gradients can propagate into them. LayerNorm and residual clipping are intentionally absent until
training-only evidence supplies a reason and valid scale.

### Retrospective oracle versus causal nominal

There are now two deliberately different parameter policies:

`oracle step k: theta_k = parameter snapshot observed after real step k`

`causal rollout: theta_hat_(t+k) = theta_t until a causal selector predicts otherwise`

The oracle answers, “Did we reproduce the known Smooth Walking equation for what Unreal actually
used?” It is excellent for debugging but cannot be the deployed planning claim because it reads the
future. The causal version answers, “What can we predict now, using only what is currently known?”

Episode 4201 demonstrates the gap. One-step causal error is nearly zero whenever the parameter
snapshot stays unchanged. Every material position, velocity, and yaw error occurs when acceleration,
deceleration, or facing-smoothing parameters change during the step. Holding the initial parameters
over longer imagined futures then compounds those sparse errors into roughly 23 cm p95 position
error after 0.5 seconds and 39 cm after 1.5 seconds. This gives the residual model a causal question:
can present state, action, and recent history predict the *effect* of the unobserved future parameter
schedule? It is not allowed to read that schedule directly.

## 7. Huber and multi-step loss

For scalar error `e` and threshold `beta`:

`Huber(e) = 0.5 * e^2 / beta` when `|e| < beta`

`Huber(e) = |e| - 0.5 * beta` otherwise.

It is quadratic near zero and linear for large errors, reducing the influence of extreme perturbations compared with squared error.

Weighted recursive objective:

`L_state = sum(k=1..H) gamma^(k-1) * Huber(s_hat[t+k] - s[t+k])`

`L_total = L_state + lambda * mean(||delta||^2)`

The state components require explicit scales so centimeters do not dominate normalized facing or angular velocity.

For MotionWorld, input features use training-set mean and population standard deviation:

`x_normalized = (x - mean_train) / scale_train`.

Residual targets deliberately use scale only:

`delta_normalized = delta / scale_train`.

We do **not** subtract the target mean. Otherwise a zero network output would decode to the learned
mean residual instead of physical zero, breaking the exact guarantee that disabling learning returns
the nominal model. Constant input or target dimensions receive unit scale and are recorded explicitly.
The fitter requires the observed episode IDs to equal the declared training IDs, so accidentally
passing validation examples fails before any statistic is computed.

### What the first residual result means

The no-history residual improved recursive held-out p95 error at 0.5, 1.0, and 1.5 seconds for all
four reported state metrics. It did not make the simulator universally more accurate: on the many
parameter-stable rows, the known nominal equations are already near numerical precision and a neural
correction can only add a small approximation error. The gain comes from windows that cross runtime
parameter changes, which is the causal mismatch this experiment was designed to expose.

Four observations of history did not improve on one observation. More information is useful only if
the dataset and model can exploit it reliably. Here the history model has more parameters, fewer
eligible examples, and correlated observations from a fixed phase schedule. The current finalized
state, action, and known movement context already identify much of the useful signal. Therefore the
history result is an ablation result—not evidence that temporal models are generally unnecessary.

Recursive evaluation is stricter than one-step evaluation. Starting with one real state, each
predicted next state becomes the input to the following step. The evaluator may use the future action
sequence and timestep because a planner proposes those actions and knows its control interval, but it
may not replace a predicted intermediate state with a recorded Unreal state. That replacement would
be teacher forcing and would hide compounding error.

## 8. Cross-Entropy Method

For each planning update:

1. Sample candidate action-knot sequences from `N(mu, sigma^2)`.
2. Clamp or transform candidates into the legal action space.
3. Roll all candidates through the same transition model interface.
4. Compute cost for every trajectory.
5. Select the lowest-cost `K` elites.
6. Compute elite mean and variance.
7. Update the sampling distribution, optionally with momentum.
8. Repeat and execute only the first action interval.

Elite updates:

`mu_elite = mean(A_elite)`

`sigma_elite^2 = mean((A_elite - mu_elite)^2)`

With momentum `alpha`:

`mu_next = alpha * mu_old + (1 - alpha) * mu_elite`

`sigma_next^2 = alpha * sigma_old^2 + (1 - alpha) * sigma_elite^2`

MotionWorld samples **five action knots**, each a two-dimensional local desired velocity, then holds
those knots piecewise-constant over 15 planning steps of 100 ms. Each planning step is evaluated by
three internal nominal/residual dynamics substeps of approximately 33.3 ms, near the training-step
distribution. Thus the deployed search space has 10 numbers,
not 30 independent per-step numbers. Reducing dimensionality is necessary because a finite CEM
budget becomes exponentially sparse as dimensions increase. The one-knot CEM-001 oracle isolates
the optimizer math; it is not evidence that the full five-knot control problem is already solved.

TSTEP-001 reconciled this choice against the accepted Unreal cadence instead of assuming a 60 Hz
tick. Across 740 training transitions, recorded `dt` had median/p95/max
`28.000/32.050/95.000 ms`; across 283 validation transitions it was
`27.000/40.900/96.000 ms`. On 74 constant-action, constant-parameter validation windows, three
`1/30 s` substeps produced lower p95 position and velocity error than six `1/60 s` substeps
(`0.539 vs 1.184 cm` and `2.320 vs 3.362 cm/s`). Six substeps modestly improved yaw p95
(`3.288 vs 3.916 deg`) but caused nominal full-CEM p95 to rise from `93.897` to `143.565 ms`,
breaking the 100 ms compute gate. Recorded-`dt` replay is a retrospective oracle, not a deployment
option, because future frame durations are unknown. Training and held-out prediction evaluation
continue to use recorded transition durations; the residual explicitly receives `dt` as a feature.

All action vectors are projected onto an L2 ball of radius 165 cm/s. This differs from clipping each
coordinate: component clipping would permit a diagonal speed of `sqrt(2) * 165` cm/s. The projector
also corrects one floating-point unit inward when norm rounding would otherwise produce a value just
above the hard boundary.

For a fair nominal/residual comparison, both solvers receive the same pre-generated standard-normal
noise tensor. Their physical candidates are identical in iteration one when their initial
distributions match. Later candidates may legitimately differ because model-dependent costs select
different elites and therefore update the distributions differently. Claiming that every later
physical candidate is identical would contradict adaptive CEM; common random numbers and identical
optimizer configuration are the correct fairness contract.

MPC executes only the first action because Unreal supplies a new observation after 100 ms, allowing replanning to correct prediction errors and perturbations.

## 9. Planning cost

Initial form:

`J = w_goal * terminal_goal_distance`

`  + w_collision * collision_indicator`

`  + w_clearance * clearance_penalty`

`  + w_delta * action_change`

`  + w_jerk * action_second_difference`

Physical clearance is geometry in centimeters after capsule radii and a safety margin. It is not a probability. A learned collision probability would answer a different question and is unnecessary for the P0 arena.

The collision and clearance terms answer different questions. Collision is a hard event: between
two model boundaries, form the agent position relative to the analytically evaluated moving gate and
test the whole relative line segment against the gate box expanded by the capsule radius. This
catches tunnelling even when neither endpoint lies inside. Clearance is a soft preference evaluated
at model boundaries: compute the Euclidean distance from the agent center to the box, subtract the
capsule radius, then penalize only the shortfall below the explicit safety margin.

For actions `a`, first difference measures changes in requested velocity:

`D1_t = a_t - a_(t-1)`.

Second difference measures curvature of the action sequence:

`D2_t = a_t - 2*a_(t-1) + a_(t-2)`.

Both include the real one- or two-action history at the start of the candidate plan. In the initial
implementation these are squared velocity differences, not physical acceleration or jerk, because
they are not divided by timestep. Naming the units honestly prevents a smoothness regularizer from
being misrepresented as a dynamics measurement.

## 10. Evaluation concepts

### ID versus OOD

- In-distribution tests sample held-out episodes from represented movement regimes.
- OOD tests change a regime such as acceleration, smoothing, or push strength beyond the training range.
- Splitting transitions from one episode across train and test is leakage because adjacent states are nearly duplicates.

### Prediction versus control

Lower average state error does not guarantee better task performance. Errors may be reduced in irrelevant dimensions while the remaining error changes a gate-crossing decision. Prediction and control must both be measured.

### Median versus p95

- Median latency describes the typical planning update.
- p95 exposes tail latency and deadline risk.
- Missed deadlines report the actual real-time consequence.

### Paired bootstrap

Because both controllers run the same seeds, resample paired episode differences rather than independently resampling controller results. The interval estimates uncertainty in the mean or median paired effect without discarding the pairing.

## 11. Unreal bridge design: D-011

### The integration problem

The Game Animation Sample already owns four valuable systems:

1. a playable `APawn` Blueprint;
2. Mover/Smooth Walking gameplay motion;
3. collision through Mover's updated component;
4. Motion Matching and visual animation.

MotionWorld needs to control and observe that system without replacing it. The smallest boundary is therefore a source-controlled actor component attached to the existing pawn.

```text
human input or planner command
            |
            v
UMotionWorldBridgeComponent (automated mode only)
            |
            v
FCharacterDefaultInputs: desired world velocity, cm/s
            |
            v
Mover -> Smooth Walking -> collision
            |
            v
OnPostFinalize(FMoverDefaultSyncState)
            |
            v
episode sample: executed position, velocity, facing, time

visual mesh / Motion Matching is observed separately for QA
```

### Plugin versus component

A **plugin** is the source-controlled package: descriptor, module, C++ code, and tests. It keeps MotionWorld code separate from Epic's licensed sample assets and can be copied into the sample's `Plugins/` directory.

An **actor component** is the runtime object from that plugin. It is attached to the existing sample pawn and adds behavior without changing the pawn's inheritance hierarchy. This is composition: the pawn keeps being the sample pawn, while the bridge contributes one narrow responsibility.

### Input production

Mover does not read keyboard keys directly. Before a simulation step, one or more **input producers** fill an `FMoverInputCmdContext`. The decision-relevant block is `FCharacterDefaultInputs`.

For automated control:

`inputs.SetMoveInput(EMoveInputType::Velocity, clamp(a_world))`

The action `a_world = (v_x, v_y, 0)` is a requested velocity in Unreal centimeters per second. It is not the executed velocity and does not teleport the pawn. Smooth Walking acceleration, smoothing, turning, collision, and hidden spring state determine the next executed state.

When automated mode is disabled, the bridge writes nothing, so ordinary sample input remains intact. This **passthrough mode** is essential for a usable demo and for proving that merely installing the plugin does not change the baseline.

The installed UE 5.8.2 implementation adds the pawn producer before gathered producer components. D-011 proposes using the bridge component as the later automated override. This ordering is an assumption, not a guarantee to hide: the first runtime test must inspect `GetLastInputCmd()` and reject the design if the command does not win reliably.

### Finalized authoritative state

`OnPostMovement` is too early for logging because its output state is explicitly still mutable. `OnPostFinalize` runs after finalization on the game thread. The bridge reads `FMoverDefaultSyncState` there:

- world location in cm;
- world linear velocity in cm/s;
- world orientation;
- angular velocity in degrees/s;
- movement/timestep metadata where available.

This Mover state represents gameplay motion. `GetPrimaryVisualComponent()` represents the rendered mesh, which may be offset by animation. Mixing the two would teach the model an inconsistent target: collision follows gameplay state, while visual feet and root can move for presentation.

### Why the alternatives are weaker

- Editing the sample Blueprint creates a hard-to-review binary asset change inside a large input graph.
- Replacing the pawn risks breaking the carefully configured animation stack.
- Editing the precompiled sample module is impossible without its project source and would couple us to Epic internals.
- Sampling ordinary actor tick can occur before or after movement depending on tick ordering and can duplicate or miss simulation steps.
- Calling `AMoverExamplesCharacter::RequestMoveByVelocity` is invalid because the sample pawn derives directly from `APawn`, not that example class.

### Safety and episode identity

The bridge eventually accepts only bounded planar commands and labels every command/observation with protocol version, episode ID, and sequence number. It rejects stale or wrong-episode commands and clamps again inside Unreal. Python-side validation is not enough because delayed packets, bugs, or a restarted service must not send an unsafe action to the current episode.

The v1 observation has three identities with different jobs. `episode_id` prevents a packet from a
previous reset entering the current episode. `observation_sequence` identifies the 10 Hz control
decision and is echoed by the action. `state_sample_sequence` identifies the particular higher-rate
`OnPostFinalize` sample selected for that control slot and must equal the nominal-context source
sequence. Treating these as one counter would either lose the state/context join or invent phantom
control decisions when finalized callbacks are skipped.

Planner context and dynamics context are intentionally separate views of the same validated packet.
The planner may know the target and the gate's deterministic analytic schedule because it must score
future geometry. The residual receives neither: character dynamics should not change merely because
a target moved, and giving it scenario variables would invite correlation shortcuts. A dedicated
extractor returns only identity, timing, authoritative state, aligned nominal context, and the
previous applied action.

The action contract separates two kinds of validity. Structural validity asks whether bytes decode
as the exact bounded v1 schema, all values are finite, timestamps agree with measured Python planner
latency, fallback semantics are consistent, and optional telemetry is bounded. Runtime admission
then asks whether the action answers the current episode's one outstanding observation and has not
already been accepted. A perfectly formed packet can still be unsafe because it is late, duplicated,
from a previous reset, or computed for a newer observation than Unreal has emitted.

Planner timestamps use Python's monotonic clock only to report planner duration. Unreal never
compares that clock with its own. The end-to-end deadline remains an Unreal monotonic send-to-receive
measurement, avoiding an invalid cross-process clock-synchronization assumption.

The selected trajectory and cost breakdown are diagnostics, not authority. Unreal applies only the
first local desired-velocity pair. It then resolves that pair through authoritative Mover yaw and
passes the resulting world vector through `SanitizeWorldVelocityCommand`, which removes Z,
fails closed on non-finite values, and clamps planar magnitude. This final engine-side clamp remains
necessary even after Python validation because trust boundaries should enforce safety locally.

### UDP framing and bounded work

UDP preserves message boundaries: one send becomes one datagram, so v1 puts exactly one JSON object
in each datagram. There is no length prefix or stream reassembly. P0 binds both peers only to IPv4
loopback. This is intentionally a local-process transport, not a reliable distributed protocol.

UDP can drop, duplicate, or reorder datagrams. We do not add retransmission because a resent action
may arrive after its 100 ms control decision has expired. Instead, episode and observation identity
decide relevance, while a missing current action becomes a measured deadline miss and invokes the
frozen hold/stop fallback. Unknown senders and oversized or empty datagrams are discarded before
JSON parsing.

Nonblocking alone does not bound CPU work: a malfunctioning peer could keep the receive queue
nonempty indefinitely. Therefore each Unreal and Python poll drains at most 16 datagrams. Each read
uses at most the 65,507-byte IPv4 UDP payload ceiling, and the JSON decoder receives only a packet
already within its message-specific 16,384-byte observation or 8,192-byte action limit. Unreal's
transport only returns byte arrays; it cannot mutate gameplay state.

JSON is UTF-8 text, so byte order is not applicable. Parsed real values use binary64. Because every
integer through `2^53-1` is exactly representable in binary64, wire identities are restricted to
that safe range. Nanosecond uptime counters could eventually exceed it, so planner diagnostic
timestamps use integer monotonic microseconds. Python computes its own duration from those values;
Unreal still measures the independent end-to-end deadline on its own monotonic clock.

### Acceptance tests

D-011 is accepted only if all of these pass:

1. Empty plugin compiles without modifying licensed assets.
2. Plugin disabled: human movement matches the unmodified baseline.
3. Fixed command: `GetLastInputCmd()` echoes velocity type and clamped vector.
4. Zero command: the character decelerates through Smooth Walking rather than teleporting or freezing.
5. Finalized samples are monotonic, one per intended simulation step, and use declared units/frames.
6. Visual-root and gameplay-state traces remain separately labeled.
7. Repeated reset clears command, episode identity, velocity, and relevant Mover hidden state.

Failure of producer ordering does not justify silently relying on it. The fallback is an explicit composite input producer that owns the ordering of sample and automated commands.

## 12. Bounded command-echo probe

The first control slice uses a world-space Mover velocity only to test the engine seam. It is not yet
the final model-facing action, which remains character-local according to the project specification.
The later frame adapter will rotate local velocity into world velocity using the character's facing.

For a requested Unreal velocity `u = (u_x, u_y, u_z)` and maximum planar speed `v_max`, define:

`q = (u_x, u_y, 0)`

`u_safe = (0, 0, 0)` if any input or `v_max` is non-finite.

Otherwise:

`u_safe = q * min(1, max(0, v_max) / ||q||_2)`

with the zero-vector case handled without division. This gives four safety properties:

- `Z` is removed because the P0 action cannot command jumping or flying;
- magnitude never exceeds `v_max`;
- clamping preserves planar direction;
- NaN or infinity fails closed to zero rather than contaminating simulation state.

Manual example: `(900, 1200, 50)` cm/s has planar magnitude `1500` cm/s. With
`v_max = 600` cm/s, the scale is `600 / 1500 = 0.4`, so the safe command is
`(360, 480, 0)` cm/s.

`SetMoveInput` quantizes each component to `0.01` cm/s. The bridge therefore saves the value after
that setter, not the unquantized request. After Mover finalizes the frame, it reads
`GetLastInputCmd()` and checks both:

1. the retained type is `Velocity`;
2. the retained world vector matches the submitted vector within `0.011` cm/s.

This is an **echo test**, not a movement-quality test. A matching echo proves Mover retained the
command after all input producers ran. It does not yet prove the pawn moved correctly, that local
and world frames are correct, or that state logging is synchronized.

The sample's standalone backend defaults to game-thread input production. The bridge explicitly
refuses off-thread production because its command/evidence fields are ordinary component state, not
an asynchronous mailbox. Supporting asynchronous or networked input later requires a separately
designed thread-safe command handoff.

## 13. Character-local and world coordinate frames

The planner action is character-local: `+X` means forward and `+Y` means right regardless of where
the character faces in the map. Unreal Mover ultimately consumes a world-space vector. For yaw
`theta`, measured in degrees by Unreal but converted to radians for trigonometry:

`v_world_x = cos(theta) * v_local_x - sin(theta) * v_local_y`

`v_world_y = sin(theta) * v_local_x + cos(theta) * v_local_y`

The inverse used to express observed world velocity in the model frame is the transpose rotation:

`v_local_x = cos(theta) * v_world_x + sin(theta) * v_world_y`

`v_local_y = -sin(theta) * v_world_x + cos(theta) * v_world_y`

The adapter uses the yaw from `FMoverDefaultSyncState`, not camera yaw, controller yaw, or animated
mesh orientation. That makes action and later observation conversion share the same authoritative
gameplay frame.

Hand checks for local forward `(200, 0)` cm/s:

- yaw `0` degrees -> world `(200, 0)`;
- yaw `90` degrees -> world `(0, 200)`;
- yaw `180` degrees -> world `(-200, 0)`;
- yaw `-90` degrees -> world `(0, -200)`.

At yaw `90` degrees, local right `(0, 200)` becomes world `(-200, 0)`. A round-trip test at a
non-cardinal angle checks that `world_to_local(local_to_world(v))` recovers `v` within floating-point
tolerance. Cardinal tests catch axis/sign mistakes; the round trip catches inconsistencies between
the forward and inverse formulas.

The frame conversion runs before speed sanitization. Rotation preserves planar magnitude in exact
mathematics, but sanitizing afterward ensures the actual world packet is finite, planar, and bounded.
An unavailable authoritative Mover state fails closed to zero and cannot produce `match=true`.

## 14. Finalized authoritative state sample

The command answers, "What velocity did we ask for?" The authoritative state answers, "What did
Unreal actually do after acceleration, turning, gravity, and collision?" MotionWorld samples the
`FMoverDefaultSyncState` passed directly to `OnPostFinalize`, rather than the rendered mesh or an
ordinary actor tick. UE 5.8 documents this callback as immutable and game-thread-only.

Protocol version 1 records:

- global gameplay position in centimeters;
- full world velocity in centimeters per second;
- planar velocity rotated into character-local forward/right axes;
- normalized diagnostic yaw in degrees and the model-facing pair `(cos(yaw), sin(yaw))`;
- full world angular velocity in degrees per second;
- movement mode, finalized simulation time, step duration, and resimulation status;
- a monotonically increasing callback sequence.

For world velocity `(v_x, v_y)`, the local velocity uses the inverse rotation from Section 13. As a
manual example, a character facing `90` degrees with world velocity `(0, 200)` cm/s has local
velocity `(200, 0)` cm/s: it is moving forward, not sideways, in its own frame.

Facing is stored as both yaw and `(cos(yaw), sin(yaw))`. Yaw `179` degrees and yaw `-179` degrees
are physically close but numerically differ by `358` degrees. Their sine/cosine vectors are close,
so a neural network does not see a false discontinuity at the wrap boundary. Degrees remain in the
Unreal-facing diagnostic contract; later preprocessing converts learned angular quantities to the
specification's internal radians.

The finalized state belongs to the end of Mover's step, so:

`sample_time_seconds = (BaseSimTimeMs + StepMs) / 1000`

The callback sequence and Mover time are deliberately separate. The sequence says in which order
the bridge received callbacks. Mover time/frame identifies simulation chronology and can repeat or
rewind during smoothing or resimulation. Episode logging must later detect and handle those cases;
it must not assume every callback is a unique causal transition.

A packet is valid only when the Mover state exists, sequence and time metadata are valid, the step
is positive, and every numeric state value is finite. Invalid packets retain diagnostic identity but
fail closed to zero state values, so a NaN cannot contaminate a dataset or model. One first sample
and then every configurable Nth sample is logged for runtime evidence without writing at 60 Hz.

## 15. Causal transition contract

A state snapshot alone is a photograph. A learned dynamics model needs a cause-and-effect record:

`s_t --(a_t, delta_t)--> s_(t+1)`

Here `s_t` is the finalized state before a Mover step, `a_t` is the velocity command Mover actually
consumed during that step, `delta_t` is the measured step duration, and `s_(t+1)` is the finalized
outcome. This becomes one supervised-learning example: given the old state and action, predict the
new state. The first state in an episode only seeds the pair; it cannot produce a transition because
there is no earlier state in that episode.

The action must be expressed in the **previous** state's character frame. The command acted from
the character orientation at the start of the transition; using the next orientation would leak
information from the answer into the input. For previous yaw `90` degrees, world velocity
`(0, 200)` cm/s is local `(200, 0)` cm/s even if the character ends the step at yaw `45` degrees.

For adjacent accepted states, MotionWorld requires:

`state_sequence_(t+1) = state_sequence_t + 1`

`delta_t = time_(t+1) - time_t > 0`

`abs(delta_t - reported_step_(t+1)) <= 0.001 seconds`

If Mover frame IDs are available, they must also differ by exactly one. Both states must use state
protocol version 1, be numerically valid, and be ordinary forward simulation rather than
resimulation. The current action schema admits only a finite planar desired velocity. Directional
intent is not silently mixed into the same dataset because it has different semantics.

The contract fails closed: a rejected candidate stays `valid=false`, carries an explicit rejection
reason, and never exposes a usable action. This is preferable to "best effort" logging because one
misaligned row teaches the model a false causal relationship. The builder is constant-time and
constant-memory: it performs only validation, two timestamp operations, and one planar rotation.

This slice defines and tests the pairing rules independently. Section 16 explains the recorder that
supplies live Mover data to this contract.

## 16. In-memory episode recorder

An episode is one uninterrupted causal sequence identified by a non-negative integer. Recording is
opt-in. Starting an episode clears old rows, fixes a hard capacity, and waits for a seed state.

The callback timeline is:

| Finalized callback | What is known | Recorder action |
|---|---|---|
| First callback | Current state `s_0`; no earlier endpoint in this episode | Store `s_0` as the seed |
| Second callback | Mover has used `a_0` and finalized `s_1` | Attempt `(s_0, a_0, delta_0, s_1)` |
| Third callback | Mover has used `a_1` and finalized `s_2` | Attempt `(s_1, a_1, delta_1, s_2)` |

UE 5.8's implementation supports this ordering. At the end of simulation it assigns
`CachedLastUsedInputCmd = StartData.InputCmd` and caches the matching timestep. The backend then
calls `FinalizeFrame`, which broadcasts `OnPostFinalize`. Therefore `GetLastInputCmd()` inside this
callback refers to the input for the step that produced the new finalized state, not the next step.

Every attempted pair consumes one `transition_sequence`, including rejected pairs. For example, if
sequences 0 and 2 are stored while sequence 1 was rejected, the gap is evidence of missing data. If
the current state itself is eligible, it becomes the next seed even when its incoming pair was
rejected because of an unsupported action. That permits recovery on the next step. A corrupt or
resimulated state is never used as a seed.

The recorder distinguishes four quantities:

- observed states: callbacks seen while recording;
- attempted transitions: callbacks for which both endpoints existed;
- recorded transitions: valid candidates retained in memory;
- rejected/dropped data: invalid candidates or valid candidates beyond capacity.

The default capacity is 4096 transitions. When it is full, the first extra valid candidate is
counted as a capacity drop and recording stops. Earlier rows are never overwritten. Per callback,
validation and appending are amortized `O(1)` time; total memory is `O(N)` up to the fixed capacity.

Mover does not expose which producer authored a packet. The `automated` flag is therefore a checked
inference: automation was enabled, the input is velocity type, and the consumed world velocity
matches MotionWorld's last finite submitted packet within Mover's 0.01 cm/s quantization tolerance.
It must not be described as cryptographic producer identity.

File persistence and deterministic reset remain separate. First, a live episode must show one seed,
adjacent accepted state/frame/time indices, matching applied actions, zero unexplained rejections,
and a correct stop summary. Ending PIE explicitly stops an active recorder and logs its counters
before the component is destroyed, so evidence is not lost with the in-memory buffer.

## 17. Deterministic character reset

A visible teleport is not a deterministic reset. Mover owns a simulation state that includes the
authoritative transform, linear and angular velocity, movement mode, cached floor/base information,
and Smooth Walking's internal spring variables. Moving only the Actor can leave those values from
the previous episode alive, so the next Mover frame can overwrite the visible pose or accelerate
from inherited momentum.

D-017 resets through Mover's simulation seam. The bridge first captures one valid finalized state
as the fixed reset anchor. When a reset is requested, it stops the old recorder, temporarily sends a
zero desired-velocity command, marks Smooth Walking's `DidGenerateMove` history stale, and queues
Mover's teleport followed by a non-additive zero-velocity effect for the same next simulation frame.
The velocity effect explicitly retains the anchor's movement mode. In UE 5.8, a stale Smooth
Walking marker causes its next move generation to initialize spring velocity and intermediate
velocity from the now-zero authoritative velocity, and to zero spring acceleration and intermediate
angular velocity.

The reset lifecycle is:

`old episode -> stop recorder -> queue reset -> finalized verification -> start new episode`

The teleport/reset callback is never recorded as a training transition. The bridge waits for a new
ordinary finalized state and checks position, yaw, linear velocity, angular velocity, and movement
mode against explicit tolerances. Only a passing state starts the new episode and becomes its seed.
The global callback sequence remains monotonic across resets for stale-data detection, while the
new episode's transition sequence restarts at zero.

For position anchor `p*`, yaw anchor `theta*`, and finalized reset state `s`, the main checks are:

`||p(s) - p*||_2 <= epsilon_position`

`abs(wrap_degrees(theta(s) - theta*)) <= epsilon_yaw`

`||v(s)||_2 <= epsilon_velocity`

`||omega(s)||_2 <= epsilon_angular_velocity`

The yaw wrap matters: `179` and `-179` degrees are only two degrees apart, not 358. A bounded number
of failed finalized checks turns the reset into an explicit failure; recording never starts on an
unverified state.

This slice resets the character gameplay state and the inspected Smooth Walking history. It does
not yet reset a target, timed gate, external actors, arbitrary untagged layered moves/modifiers, the
animation graph's visual history, a planner warm start, or random-number generators. Those belong
to the later arena-level reset. Claiming more would make the experiment look deterministic without
actually controlling all of its initial conditions.

## 18. Durable episode files

The in-memory recorder proves causal ordering, but its rows disappear when the process ends. A
model-training pipeline needs a durable boundary: Unreal writes accepted evidence, and an
independent Python reader refuses anything incomplete or internally inconsistent.

D-018 uses JSON Lines rather than one giant JSON array. Each line is one complete JSON object:

1. the header declares schema version, episode identity, engine/project provenance, coordinate
   frames, units, and recorder counters;
2. each transition stores `(previous finalized state, applied action, next finalized state)`;
3. the footer repeats episode identity and row counts and marks the file complete.

JSON Lines keeps temporary serialization memory `O(1)` per row instead of constructing a second
episode-sized JSON tree. Runtime remains `O(N)` because each of `N` accepted transitions is written
once. The in-memory recorder is still bounded to prevent unbounded growth.

The destination is published atomically. Unreal writes a unique temporary file in the destination
directory, closes it after the footer, then renames it without replacement. A crash before rename
leaves no file that the dataset loader will mistake for a complete episode. A pre-existing filename
is never silently overwritten.

The exporter revalidates every accepted transition before writing. Python then independently
checks exact schema keys, finite numerics, protocol versions, units/frames, episode identity,
timestamps, state and Mover-frame adjacency, action-frame conversion, shared endpoints, counts, and
the complete footer. A transition-sequence gap is allowed only as visible evidence that an earlier
attempt was rejected; model windows must never cross that gap.

Schema version 2 adds an optional typed scenario block. A timed-gate header stores the immutable
seed and schedule. Every transition stores previous/next analytic gate state plus collision,
crossing, and termination labels. The footer reconciles terminal reason, terminal scenario time,
and collision count. Python retains version-1 compatibility but recomputes every version-2 gate
position, velocity, and phase from the header equation; it also proves a claimed success crossed
the fixed plane forward and a claimed timeout did not precede the deadline. Target and external
impulse fields remain future scenario extensions rather than fabricated values.

## 19. Deterministic timed gate

The timed gate is a moving collision box whose center is evaluated from absolute scenario time.
It does not update its position by repeatedly adding `velocity * frame_time`, because small
frame-time differences would then accumulate into different schedules. For origin `o`, normalized
sideways motion axis `u`, amplitude `A`, period `T`, phase offset `phi_0`, and scenario time `t`:

`omega = 2*pi/T`

`phi(t) = wrap_[0,2pi)(phi_0 + omega*t)`

`p_gate(t) = o + u*A*sin(phi_0 + omega*t)`

`v_gate(t) = u*A*omega*cos(phi_0 + omega*t)`

The derivative explains the velocity equation: the derivative of `sin(omega*t)` is
`omega*cos(omega*t)`. The motion axis must lie within the success plane, so its dot product with
the plane normal is zero. This makes the blocker move sideways across the route rather than moving
the definition of success itself.

Hand example: let `o=(100,200,50)` cm, `u=(0,1,0)`, `A=100` cm, `T=4` s, and `phi_0=0`.
Then `omega=pi/2` rad/s. At `t=0`, the center is `(100,200,50)` and velocity is
`(0,50*pi,0)` cm/s. At `t=1` s, the phase is `pi/2`, the center is `(100,300,50)`, and velocity is
zero. At `t=4` s, center and velocity repeat their `t=0` values.

The success plane is fixed through `o` with forward normal `n`. For consecutive authoritative
character positions `x_prev` and `x_now`, a forward crossing occurs when:

`dot(x_prev-o, n) <= 0` and `dot(x_now-o, n) > 0`.

Terminal events have a declared priority: gate collision, then successful forward crossing, then
timeout. Collision wins if collision and crossing appear in the same finalized step; otherwise a
discrete step could claim the character passed through a blocker. Backward crossing is not success.

The terminal observation is still caused by the action submitted for that simulation step, so it
must enter the episode before the controller changes its request. On the following input-production
step, MotionWorld commands zero velocity. This is a causal boundary: the dataset keeps the action
that actually caused the outcome, while future motion is stopped. “Terminal” freezes the gate's
schedule and event counter; it does not remove the physical obstacle. Multiple engine collision
callbacks received between two authoritative character observations are coalesced into one scenario
collision event because the learning row represents that whole finalized interval.

The schedule is deterministic for a fixed configuration and scenario-relative time. `ScenarioSeed`
identifies the episode configuration even though this first schedule uses no random samples. The
runtime actor and episode schema must still prove that reset restarts time at zero, collision events
join the correct finalized step, and the logged visible transform agrees with this analytic state.

## 20. Gameplay state versus animation-root diagnostics

The authoritative gameplay point and the visual animation root answer different questions:

- Mover's finalized actor position answers “where does collision and control say the character is?”
- the primary skeletal mesh's root bone answers “where does the currently buffered visual pose put
  the animation root?”

For authoritative position `p_actor` and animation-root world position `p_root`, the diagnostic
offset is:

`d_root = p_root - p_actor`.

This offset is measured in Unreal world centimetres. It is not appended to the learned state. The
sample sequence links the diagnostic to one finalized Mover observation, while the capture-phase
label warns that skeletal animation may have been evaluated on a different visual tick. A plot can
therefore reveal visual lag or deliberate pose offsets without redefining the physical trajectory.

The root bone is bone index zero of Mover's primary skeletal visual component. Index zero is the
skeleton root by reference-skeleton convention; reading Mover's selected visual component avoids
silently inspecting a secondary mesh. Toe transforms remain out of scope until contact annotations
can distinguish planted feet from swinging feet.

## 21. Required personal exercises

Before each component is accepted, explain without looking:

- its purpose;
- inputs and outputs;
- governing equation;
- assumptions;
- computational cost;
- one unit test;
- one realistic failure.

Add the explanation and any manual calculation to this file. Code is not complete until the explanation is owned.

## 22. Nominal context and schema-v3 transition semantics

The visible gameplay state is still `s_t`: finalized position, velocity, facing, angular velocity,
movement mode, time, and identity. Smooth Walking also has known persistent controller state `z_t`:

- spring velocity and spring acceleration;
- intermediate velocity;
- intermediate facing quaternion;
- intermediate angular velocity.

Let `theta_t` denote the active Smooth Walking parameters observed at the same finalized boundary.
A schema-v3 row represents:

`(s_t, z_t, a_t, theta_step, s_(t+1), z_(t+1))`

where `a_t` is the desired-velocity input consumed during the completed movement step. The nominal
transition will have the form:

`(s_hat_(t+1), z_hat_(t+1)) = f_nominal(s_t, z_t, a_t, theta_step, delta_t)`

The parameter timing needs care. The current Unreal seam reads the movement-mode object inside the
`OnPostFinalize` callback. Therefore `theta_step` is copied from the next finalized context and means
“the parameter snapshot observed after the step, assumed to have governed that completed step.” It is
not proof that the same parameter regime is available before every imagined MPC step. Offline analysis
may use this label; deployable planning needs a causal parameter selector or a fixed declared regime.

Both endpoints are required because hidden memory also evolves. If row `k+1` is consecutive with row
`k`, then both the visible endpoint and hidden endpoint must match exactly:

`s_previous^(k+1) = s_next^k`

`z_previous^(k+1) = z_next^k`

Sequence alignment additionally requires the context attached to `s_t` to carry the same authoritative
sample sequence and movement mode. Missing or invalid context rejects the transition rather than
inventing zero spring state. Old schema-v1/v2 evidence remains readable as historical data, but it
cannot be relabelled as schema v3 because it never recorded `z`.

## 23. Deterministic varied-action schedule

One straight trajectory cannot tell us how the controller accelerates in different directions,
brakes, reverses, or turns. D-030 therefore defines a short coverage experiment as a function of
elapsed episode simulation time:

`(v_desired_world(t), facing_intent_world(t), phase(t)) = schedule(t)`

The default phases are forward, stop, reverse, stop, right, left, diagonal, and final stop. Each
interval is half-open: it includes its start and excludes its end. For example, forward owns
`0 <= t < 0.8`, and the first stop owns `0.8 <= t < 1.2`. Therefore `t=0.8` belongs to exactly the
stop phase. This eliminates both gaps and double ownership.

The schedule uses absolute time measured from the verified episode start. It does not add one frame
duration to a phase clock every tick, because those increments can accumulate rounding and frame-rate
differences. Every boundary is computed from the same closed-form duration sums, and the automatic
completion check uses the same 5.3-second total.

For a nonzero planar command `v=(v_x,v_y,0)`, facing is derived as:

`f = v / ||v||`

and desired yaw is `atan2(f_y, f_x)`. At zero velocity, normalization is undefined, so the schedule
holds the previous phase's facing. That stop behavior is meaningful: zero desired velocity does not
erase the controller's rotation/spring memory. Although the script is written in world coordinates
to make level coverage reproducible, each transition already stores both the echoed world command
and its character-local representation relative to the previous authoritative facing.

There is one numerical exception to exact velocity alignment. World `-X` is exactly opposite the
fixed `+X` basis used by Unreal's `FQuat::FindBetween`. At that point both turn directions have the
same 180-degree length. The replacement schedule keeps velocity exactly `(-150,0,0)` but defines its
facing as -179.5 degrees:

`f_reverse = (cos(-179.5 degrees), sin(-179.5 degrees), 0)`

This changes only the facing target by 0.5 degrees and deterministically selects the clockwise arc.
It is a controller-interface rule, not learned physics. The value is large enough to avoid Unreal's
exact-opposite branch and small enough not to alter the requested translational task materially.

Unique live episode 4201 validates the practical effect. The exact-opposite version produced
recursive yaw maxima of 174.296, 174.296, and 89.390 degrees at 0.5, 1.0, and 1.5 seconds. The
declared -179.5-degree version produces only 0.042917, 0.042917, and 0.029078 degrees. The first
reverse row still contains a one-frame -179.0-degree reflected hidden target, but its 0.024337-degree
one-step yaw error is below the configured 0.1-degree facing deadzone and does not compound.

This is a coverage generator, not a claim that the final model has adequate data. A live episode
must still prove every phase occurred, the reset and export completed, the strict loader accepted all
rows, and the realized distributions actually contain braking, reversal, turning, and stopping.

## 24. Fair CEM comparison and cross-model evaluation

At one MPC update, CEM samples complete candidate action sequences. Here the tensor has shape

`[256 candidates, 15 planning steps, 2 local velocity components]`.

Five sampled knots are expanded piecewise-constantly across the 15 steps. Each 100 ms planning
step contains three nominal/residual dynamics updates of about 33.3 ms. This distinction matters:
15 is the number of decisions scored along the horizon, while 45 is the number of transition-model
applications used to predict one candidate.

For a fair first comparison, nominal and residual planning receive the same initial state, common
standard-normal noise `epsilon`, action mean `mu`, and standard deviation `sigma`:

`a_i = project(mu + sigma * epsilon_i)`.

They therefore evaluate the same physical candidates in the first iteration. Each model assigns
different costs, selects different elites, and updates its distribution as

`mu_new = alpha * mu_old + (1-alpha) * mean(elites)`

`var_new = alpha * var_old + (1-alpha) * population_variance(elites)`.

Consequently, later candidate tensors should usually differ. Forcing them to remain identical would
prevent CEM from adapting to each model's predictions. Fairness means identical rules, resources,
random numbers, initial candidates, and costs—not identical learned search trajectories after the
models produce different rankings.

Cross-model evaluation then scores both selected plans under both transition models:

| Selected action sequence | Nominal prediction | Residual prediction |
|---|---:|---:|
| Nominal plan | 106.476 | 10070.711, collision |
| Residual plan | 216.360 | 86.081 |

The diagonal cells answer, “How good does each plan look to the model that selected it?” The
off-diagonal cells ask, “Does the other model agree?” OFFPLAN-001 shows strong disagreement. This
proves the learned residual is decision-relevant because it changes rankings and actions. It does
not prove the residual plan is better: either model may be wrong, and an optimizer actively searches
for places where model errors look advantageous. That is called model exploitation. The remedy is
not to choose the nicer predicted number; it is to execute paired trials in Unreal, inspect failure
cases, and add uncertainty or conservative penalties if exploitation appears.

One selected residual trajectory costs `86.08109497` when evaluated inside a batch of 256 and
`86.08110374` when re-evaluated alone. The `8.77e-6` difference comes from float32 neural-network
arithmetic using different batch shapes. Floating-point addition is not perfectly associative, so
tiny changes do not imply stochasticity. The implementation records the reproduction error and
uses a declared small tolerance instead of demanding misleading bitwise equality across shapes.

## 25. Controlled disturbance: velocity kick versus physical impulse

The controlled push uses Mover's public additive-velocity effect. If the synchronized velocity just
before the event is `v_t` and the requested kick is `Delta v`, the API requests:

`v_event = v_t + Delta v`.

`Delta v` has units of cm/s. A mechanical impulse would instead satisfy `J = m Delta v` and have
units of mass times velocity. Because this experiment neither supplies nor uses mass, calling
`Delta v` an impulse would overstate the physics.

The event transition is deliberately not a fair prediction target when the future kick is hidden
from the model. It should be reported separately. The scientifically useful question begins after
the first disturbed state is observed: does the faithful nominal model recover exactly, or does
recent observable history explain a persistent mismatch? This distinction prevents a model from
appearing accurate merely because evaluation leaked the future intervention into its inputs.

Live episode 4301 makes the distinction concrete. Let the nominal prediction be
`f_nominal(s_t,a_t)` and the recorded next state be `s_(t+1)`. On the hidden event row,

`r_t = s_(t+1) - f_nominal(s_t,a_t)`

is large: 5.370 cm planar position error and 233.480 cm/s planar velocity error. But this `r_t` is
not a function of the supplied `s_t,a_t`; it contains an intervention deliberately omitted from the
inputs. A learner cannot infer which otherwise identical episode will be kicked. After `s_(t+1)` is
observed, the disturbance is inside the new state and the nominal model predicts the recovery to
micro-numerical tolerance. This is the difference between predicting a surprise before it happens
and predicting dynamics after observing its effect.

The physical response also shows why requested and realized change are different. The requested
+250 cm/s world-Y kick produced +233.480 cm/s in the first finalized next state because the normal
movement update acted during the same 0.023-second transition. Smoothing reduced lateral speed below
1 cm/s in 0.416 s and left 24.433 cm total lateral displacement. These are measured outcomes, not
values assumed from the command.

Episode 4101 exposes why rotations cannot always be reduced to an ordinary scalar angle without a
declared tie rule. A requested 180-degree turn has two equally short physical paths: clockwise and
counter-clockwise. Quaternions also identify `q` and `-q` as the same orientation. On the first
reverse row, Unreal's reflected intermediate target represents -179 degrees, while the recorded
intent-derived scalar target is -180 degrees. A scalar shortest-angle function selected the other
equal arc, producing a one-row angular mismatch. This is not evidence that the movement is random;
it is evidence that exact-opposite quaternion construction/representation is part of the known
nominal transformation and must be reproduced or explicitly declared unresolved. D-032 resolves the
input policy prospectively with the -179.5-degree tie-break; episode 4101 remains preserved as the
failure that motivated it, not rewritten after the fact.

The recursive result makes the difference between median and tail statistics concrete. Most rollout
windows never cross the exact-opposite edge, so median yaw error is near zero. Every window with more
than one degree of yaw error crosses that single row, so p95 and maximum error are large. Reporting
only the median would hide a planner-dangerous failure; reporting only the maximum would falsely
suggest every trajectory fails.

## 26. Vectorization and the runtime deadline

Scalar code processes one candidate after another. Vectorized code stores the same field from all
256 candidates in one array and applies an equation to the full array at once. For example, instead
of 256 Python calls for position integration, it computes

`P_next = P + V_next * delta_t`

where `P` and `V_next` have shape `[256, 3]`. This does not change the model or reduce the search
budget; it removes interpreter overhead and lets optimized numeric kernels do the repeated work.
The risk is that branch conditions and floating-point operation order can drift, so the scalar
implementation remains the oracle and randomized parity tests compare observable and hidden state.

Runtime must time the whole planner call: sample/project candidates, recursively roll dynamics,
compute costs, select elites, update CEM, and re-evaluate the winner. Timing only the MLP would omit
most of the system. Warm-ups prevent one-time initialization from contaminating steady-state
results. Median describes a typical call; p95 asks for a latency below which 95% of calls fall.
For a 100 ms control interval, p95 is especially important because occasional late actions become
stale even when the median passes.

RUNTIME-001 finds nominal median/p95 `70.709/81.549 ms`, but residual
`149.655/169.401 ms`. Thus vectorization is a large engineering success and still a deployment-gate
failure for the learned controller. Both statements can be true. The benchmark also excludes Unreal
transport and application, so passing 100 ms offline would be necessary but not sufficient for the
live loop.

### Runtime-quality Pareto gate

A reduced optimizer budget is useful only if it is both fast enough and sufficiently faithful to
the reference search. For each validation query and model, define positive relative regret as

`max(0, (J_reduced - J_reference) / max(abs(J_reference), 1))`.

Negative regret is clipped to zero because occasionally a smaller stochastic search finds a better
candidate; that is not a quality failure. CEM-BUDGET-001 requires p95 positive regret at most 10%,
zero newly predicted collisions, and p95 latency at most 100 ms for both controllers. No tested
budget passes all three. This is a Pareto problem: some options are fast, and others preserve more
quality, but none lies in the acceptable region. Changing the threshold afterward would be
post-hoc tuning, so the correct action is to retain the negative result and optimize a different
part of the system.

### Why a smaller prediction model can still make a worse planner

Compression reduces matrix-multiplication work, but prediction error is not interchangeable with
planning error. Let the reference model assign cost `J_ref(a)` to an action sequence. A compressed
model chooses

`a_small = argmin_a J_small(a)`,

while the reference chooses

`a_ref = argmin_a J_ref(a)`.

Even if typical recursive state error changes only slightly, CEM searches specifically for action
sequences where the learned model predicts low cost. A small local error near the collision
boundary can therefore change an indicator by 10,000 cost units. Cross-evaluation measures

`max(0, (J_ref(a_small) - J_ref(a_ref)) / max(abs(J_ref(a_ref)), 1))`.

This does not prove that the reference is physically correct. It asks a narrower validation
question: did compression preserve the behavior of the already-selected model? In
RESIDUAL-COMPRESS-001, 128/128/64 preserved all recursive p95 metrics within 8.43% but failed this
planner test severely. That is a concrete example of why an ML component must be evaluated inside
the decision system that consumes it.
