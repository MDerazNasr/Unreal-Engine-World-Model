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

This is a unit-test oracle, not the final nominal model.

## 4. Faithful nominal dynamics

The final nominal predictor carries known internal spring state:

`s_nom_next, z_nom_next = f_nominal(s, z_nom, a, params)`

`z_nom` may contain acceleration, immediate/intermediate velocity, intermediate rotation, and intermediate angular velocity. Omitting known state can make the learned model appear useful only because the baseline was unfairly simplified.

The movement model is not assumed delta-time invariant. A 100 ms planner transition is therefore composed from verified smaller simulation steps:

`f_100ms = f_16.67ms composed six times`

Questions to master:

- Why do acceleration and deceleration need different branches?
- What does directional acceleration change during a turn?
- Why can a velocity spring require intermediate state?
- Why must an external push update both visible and spring state?
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

Zero-residual invariant:

`r_theta(.) = 0` must make the corrected rollout numerically equal to the nominal rollout.

## 7. Huber and multi-step loss

For scalar error `e` and threshold `beta`:

`Huber(e) = 0.5 * e^2 / beta` when `|e| < beta`

`Huber(e) = |e| - 0.5 * beta` otherwise.

It is quadratic near zero and linear for large errors, reducing the influence of extreme perturbations compared with squared error.

Weighted recursive objective:

`L_state = sum(k=1..H) gamma^(k-1) * Huber(s_hat[t+k] - s[t+k])`

`L_total = L_state + lambda * mean(||delta||^2)`

The state components require explicit scales so centimeters do not dominate normalized facing or angular velocity.

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

`sigma_next = alpha * sigma_old + (1 - alpha) * sigma_elite`

MPC executes only the first action because Unreal supplies a new observation after 100 ms, allowing replanning to correct prediction errors and perturbations.

## 9. Planning cost

Initial form:

`J = w_goal * terminal_goal_distance`

`  + w_collision * collision_indicator`

`  + w_clearance * clearance_penalty`

`  + w_delta * action_change`

`  + w_jerk * action_second_difference`

Physical clearance is geometry in centimeters after capsule radii and a safety margin. It is not a probability. A learned collision probability would answer a different question and is unnecessary for the P0 arena.

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

## 13. Required personal exercises

Before each component is accepted, explain without looking:

- its purpose;
- inputs and outputs;
- governing equation;
- assumptions;
- computational cost;
- one unit test;
- one realistic failure.

Add the explanation and any manual calculation to this file. Code is not complete until the explanation is owned.
