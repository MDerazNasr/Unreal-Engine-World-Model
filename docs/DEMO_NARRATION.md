# MotionWorld interview narration

## 30-second explanation

“I built a narrow action-conditioned world model for Unreal character motion. Unreal is always the
authority: it supplies finalized state and decides what really moved or collided. Python uses a
faithful movement model plus a learned residual to imagine short futures. A CEM planner compares
candidate action sequences, executes only the first nominal-selected action before its deadline,
then reobserves and replans. Yellow is reality, blue is the nominal forecast, and orange is the
learned correction using the same state and actions. The overlay demonstrates model disagreement,
not that residual control is better.”

## 90-second visual narration

**0–15 seconds — establish the loop**

“This is an observe → imagine → choose → execute → compare → replan loop. The current sample has
an episode and sequence identity, so an old Python response cannot control a newer Unreal state.”

**15–35 seconds — explain the trajectories**

“Yellow is the collision-finalized Unreal path. Blue is the known Smooth Walking model. Orange is
the learned residual correction. Blue and orange start from the exact same authoritative state and
receive the exact same nominal-selected action sequence, so differences come from model dynamics,
not different inputs.”

**35–55 seconds — explain MPC**

“CEM samples short action sequences and scores their predicted outcomes. The controller executes
only the first action, because after Unreal advances, the remaining plan is conditional on an old
state. It then replans from the new authoritative observation.”

**55–72 seconds — explain safety and latency**

“Unreal admits a reply only if its episode and observation identity are current and it arrives
before the wall-clock deadline. Missing, late, malformed, or old replies cannot become movement;
the runtime falls back to bounded zero.”

**72–90 seconds — state the result honestly**

“The accepted live nominal run proves the end-to-end MPC loop under deadline. The learned model
improves recursive validation metrics and produces a matched visual forecast, but I am not claiming
superior live residual control: full residual planning missed the runtime gate, and the sealed
paired study remains future work.”

## Two technical explanations

### Movement/runtime interviewer

Unreal owns collision, finalized state, reset, and command sanitization. Python owns prediction and
planning. Simulation time determines state chronology; monotonic wall time determines whether a
reply is still safe to apply. Identity plus deadline checks prevent a valid-looking action computed
for an obsolete state from becoming movement. Receding-horizon control applies only action zero,
then closes the loop around the actual engine result.

### Causal/ML interviewer

The model learns a six-value local planar correction to the nominal transition: position, velocity,
yaw, and yaw rate. Inputs exclude absolute pose, goal, future disturbances, and held-out outcomes.
Training normalization comes only from training episodes, evaluation is recursive without teacher
forcing, and final episodes 5301/5302 remain sealed. The blue/orange overlay holds current state and
action sequence fixed, isolating model disagreement. Only Unreal execution can establish control
quality, so prediction improvement is not reported as control improvement.

## Fast challenge answers

- **Why is this a world model?** It predicts action-conditioned future state recursively and is
  queried counterfactually by a planner. It is intentionally a movement-state model, not a visual
  foundation model.
- **Why execute only the first planned action?** Hidden movement state and collision outcomes evolve;
  reusing the rest would act on a predicted state instead of the new authoritative state.
- **Why wall time for deadlines?** Simulation time describes world chronology and can pause or run at
  a different rate. Monotonic wall time measures whether the asynchronous response arrived in time.
- **Why can orange differ if actions are identical?** The residual changes the predicted transition,
  not the action. Holding inputs fixed makes that difference interpretable.
- **What is not proven?** Statistical superiority of residual control, generalization to unseen
  collision/push regimes, and the sealed final paired study.
