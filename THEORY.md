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

## 11. Required personal exercises

Before each component is accepted, explain without looking:

- its purpose;
- inputs and outputs;
- governing equation;
- assumptions;
- computational cost;
- one unit test;
- one realistic failure.

Add the explanation and any manual calculation to this file. Code is not complete until the explanation is owned.
