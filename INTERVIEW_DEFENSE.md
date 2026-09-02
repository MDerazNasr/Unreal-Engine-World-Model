# MotionWorld Interview Defense

Status: living rehearsal document.  
Answer rule: state the claim, point to evidence, state the limitation. Draft answers remain provisional until the referenced experiment exists.

## 1. Thirty-second explanation

MotionWorld is a compact action-conditioned residual dynamics model for Unreal character control. A faithful Smooth Walking predictor handles known movement behavior; a small MLP predicts the systematic execution error that remains. CEM evaluates corrected candidate futures and executes the first desired-velocity action before replanning. I compare nominal and residual MPC with identical actions, costs, seeds, and compute, and claim the learned model helped only when its corrected prediction changes the plan and improves same-seed Unreal execution.

## 2. Daniel Holden lens: movement, animation, control, implementation

### Why is your nominal model fair?

It implements the known Smooth Walking structure, carries known intermediate spring state, and substeps at the verified movement rate. The residual is not rewarded for rediscovering public baseline equations. Remaining mismatch is measured before learning, and nominal versus residual MPC differs only in the learned correction.

Evidence required: nominal hand tests, code/reference comparison, recursive Unreal error plot.

### Why is median rollout error tiny while p95 rotation error is large?

The failure is localized, not contradictory. Most episode-4101 windows avoid the exact 180-degree
turn and stay at numerical-noise angular error. Every window above one degree crosses one reverse
boundary where Unreal temporarily represents the target as -179 degrees while the scalar nominal
chooses the other equal 180-degree arc. Median describes typical windows; p95 exposes a rare but
planner-dangerous edge. I report both and define a deterministic -179.5-degree clockwise tie-break
before training a residual. In unique live episode 4201, recursive maximum yaw error fell from
174.30 degrees to 0.043 degrees; I preserve the original failure and do not credit the residual for
fixing a known controller-interface ambiguity.

### Why don't you give the residual model the external-push label?

Because that would reveal a future disturbance that the online planner cannot know. I label the
event transition for stratified evaluation and exclude it from ordinary predictable-error claims.
After the first disturbed state becomes observable, I test whether no-history or recent-history
models can predict recovery. This separates event detection from recovery modeling and prevents
evaluation leakage.

### Why keep actor and animation state separate?

The actor/capsule determines gameplay collision and is authoritative. Motion Matching and downstream animation can intentionally offset the rendered root to preserve visual quality. Mixing those signals would give the dynamics model inconsistent targets. I log animation root and toe behavior separately to show the control remains animation-friendly.

Evidence required: labeled actor/root traces from one run.

### Why desired velocity?

It is a compact, designer-readable control surface already aligned with Smooth Walking. It keeps CEM's action space small while preserving acceleration, turning, and stopping behavior inside the movement model.

### Why not generate poses?

The research question is whether corrected execution dynamics improve planning. Pose generation would introduce a second major problem and obscure causal attribution. Existing Unreal animation remains downstream and is evaluated rather than replaced.

### What happens to the spring state after a push?

Draft: external forces must be reflected in both authoritative velocity and any internal velocity-spring state. The exact synchronization mechanism depends on what Mover exposes and is a Day-1 feasibility decision. If internal state cannot be observed, the limitation is explicit and history becomes an estimator rather than a substitute hidden inside an unfair baseline.

## 3. Viktoriia Sharmanska lens: data, robustness, causality, evaluation

### Why call it a world model?

It predicts the decision-relevant future state of part of the environment conditioned on candidate actions. The scope is intentionally narrow: short-horizon character dynamics, not pixels or a complete scene. I use the term state-space world model and state the boundary every time.

### How do you know the model follows actions rather than correlations?

Training uses varied actions, evaluation includes same-state counterfactual commands, and target/obstacle features are excluded from character dynamics. I compare predicted futures under forward, left, right, and stop interventions, then execute one to compare with Unreal.

Evidence required: paused-action intervention panel and per-action rollout errors.

### How do you prevent leakage?

Splits are made by complete episode, scenario seed, obstacle layout, and movement regime. Adjacent transitions from one episode never cross splits. Normalization is fit on training data only. Test seeds are frozen before tuning.

Evidence required: split validator and immutable manifests.

### Can it predict an unpredictable push?

No. Evaluation begins after the impulse. The question is whether observed post-push history exposes hidden controller response quickly enough to improve subsequent predictions and replanning.

### Does better prediction imply better control?

No. That is why the project has separate prediction and task metrics. The positive claim requires a specific corrected prediction to change the selected action and improve same-seed execution.

### What happens outside the training distribution?

I sweep movement parameters and push strength inside and outside the training range, show degradation curves, and preserve a failure case. The model is only claimed to be reliable near represented state-action distributions.

### How do you detect planner exploitation?

I compare predicted and realized return for CEM-selected trajectories with the gap on randomly sampled in-distribution trajectories. A much larger optimistic selected-plan gap is evidence that optimization is exploiting model error.

## 4. Architecture challenges

### Why use an isolated Unreal bridge plugin instead of editing the sample Blueprint?

The Game Animation Sample pawn is a large licensed Blueprint derived from `APawn`, and its project module is distributed precompiled without visible source. Editing the Blueprint would produce a fragile binary diff and entangle MotionWorld with sample input and animation logic. UE 5.8.2 already provides a compositional seam: Mover gathers actor components implementing `IMoverInputProducerInterface`, and `OnPostFinalize` exposes finalized authoritative state. A small source-controlled bridge can therefore override input only in automated mode, leave human control untouched otherwise, and record gameplay state without replacing the pawn or animation stack. The main risk is producer ordering, so the first runtime test checks `GetLastInputCmd()` rather than assuming the command won.

Evidence required: plugin compile, human-control passthrough test, fixed velocity command echo, and finalized-state trace.

### Why residual learning rather than a full transition model?

Known movement structure is inexpensive and testable. Residual learning gives zero a meaningful baseline, focuses capacity on systematic mismatch, and provides a clean scientific comparison. It can fail if residuals are mostly noise or the nominal model is already sufficient.

### Why an MLP instead of a GRU or Transformer?

The state is low-dimensional and mostly observed, and four observations cover the hypothesized controller lag. The MLP is faster and easier to debug. This is a falsifiable simplicity choice: if the history MLP fails while error signatures indicate longer hidden state, a recurrent model becomes justified.

### Why CEM rather than gradient-based planning?

CEM handles bounded actions and non-differentiable analytic collision costs, is simple to batch, and does not require differentiating the whole service. Its tradeoff is sample cost, addressed through action knots, warm starts, and latency measurement.

### Why not run Unreal itself for every candidate?

At each 10 Hz decision, CEM evaluates hundreds of candidates over 12-15 steps and several iterations. Cloning and advancing that many full Unreal worlds is outside the real-time budget. The nominal-plus-residual model is the batched approximation whose accuracy is directly evaluated.

### How do you know each action is paired with the correct state transition?

The first finalized state seeds the episode. UE 5.8 stores the input used by a simulation step and
its timestep before broadcasting the post-finalization callback. On the next callback I therefore
pair the prior cached state with that just-used input and the newly finalized state. I require
adjacent state and Mover-frame IDs, increasing simulation time, and agreement between timestamp
difference and reported step length. Rejected attempts consume sequence IDs and are counted, so
missing data cannot masquerade as a continuous trajectory.

Evidence: UE source ordering, the recorder automation test, and live episode 1601. The live run
reconciled 923 observations into 922 adjacent attempted pairs and accepted all 922, with no rejected
pair, rejected seed, or capacity drop. This proves the implemented callback join behaved
consistently in that run; it does not prove all future engine configurations or callback paths.

### Why stop when the episode buffer is full instead of overwriting old rows?

Overwriting silently changes the episode's start and breaks provenance. A hard bound controls memory
while a counted capacity drop and automatic stop make truncation explicit. The final persisted
episodes will be intentionally shorter than the bound.

### How do you know reset cleared hidden controller state?

I do not infer reset from the visible Actor transform. The request runs through Mover: it teleports
the authoritative state, applies non-additive zero linear velocity and zero angular velocity in the
captured movement mode, and marks Smooth Walking's `DidGenerateMove` value stale. In the audited UE
5.8 source, that stale marker reinitializes spring velocity, acceleration, intermediate velocity,
intermediate facing, and intermediate angular velocity from the reset velocity and facing. I then
accept only a newer non-resimulated finalized state whose position, yaw, velocities, and mode meet
explicit tolerances. Recording starts after that check, so no teleport crosses an episode boundary.

Evidence required: two same-session resets from nonzero displacement, matching finalized seeds,
zero residual speeds within tolerance, and separate episode summaries. This character-level claim
does not include animation-graph history, external actors, the timed gate, RNG, or planner state;
the arena reset must handle those separately.

Observed result: the two resets began 483.813 cm and 509.037 cm away, passed on the first finalized
check at the identical pose/mode with zero measured residual speeds, and separated episodes 1701
and 1702 without an accepted cross-reset transition.

### Why not NavMesh?

NavMesh provides global/static routing. MotionWorld addresses short-horizon local control under timing, perturbation, and model mismatch. They are complementary layers.

### Why is Smooth Walking context separate from authoritative state?

Authoritative state answers what physically happened after collision resolution: position, velocity,
facing, angular velocity, mode, and time. Smooth Walking's spring variables are controller memory used
to explain how that state evolves. I version them separately so I do not redefine the gameplay state or
pretend private controller internals are universally observable. A transition is accepted only when the
context sequence and movement mode match its state endpoint.

### Are you leaking future parameters into the planner?

Not in the deployable claim. Schema v3 records the parameter object observed at the next finalized
boundary and labels it as assumed to have governed the completed step. That is useful for reconstructing
past Unreal transitions. It is privileged for a future rollout unless a causal selector can determine
the same regime before planning, so the header explicitly says future availability is not guaranteed.
The initial faithful predictor can be evaluated within fixed observed regimes; online regime selection
is a separate experiment.

### Why not fill missing hidden context with zeros?

Zero is a real controller state, not a neutral missing value. Substituting it would convert capture
failures into false physical evidence and teach the residual to compensate for a data-pipeline bug.
Missing, wrong-version, non-finite, or misaligned context therefore rejects the seed or transition and
increments an explicit rejection counter.

### Why did schema v4 add both a speed limit and orientation intent?

Because the logged velocity packet is not yet the exact target consumed by Smooth Walking. Simple
Walking can clamp its magnitude using a mode override or shared max speed, and it converts orientation
intent into a desired-facing quaternion. Both can change the next state. Omitting either makes the
transition non-causal from the model's point of view and encourages the learned residual to compensate
for a known logging error. Schema v4 records the raw causal inputs and the deterministic preparation;
schemas 1-3 remain readable but their missing fields are never silently invented.

## 5. Examiner checklist

Before marking a component finished, answer aloud:

- What exact tensor or struct enters it?
- What exact tensor or struct leaves it?
- Which equation does each variable implement?
- Which units and coordinate frame are used?
- What state is hidden or estimated?
- What is the asymptotic and measured runtime cost?
- Which hand-calculated test would catch a sign or timestep error?
- What comparison would be unfair?
- What result would falsify the current hypothesis?
- What is the weakest claim the evidence supports?

Record weak answers here and resolve them before the final rehearsal.

## 6. Candidate teach-back record

### Q1 - Desired versus executed velocity (passed 2026-09-01)

Candidate answer, lightly normalized for terminology: Desired velocity is a request, not the actual
result. Acceleration limits, collisions, controller smoothing, and external forces acting on Mover
can change the executed motion. Record the previous state, requested/applied action, actual timestep,
and finalized next position and velocity separately.

Examiner assessment: Passed after one retry. The first attempt recognized timestep variation but
mixed position, timing, and velocity. The retry correctly separated the commanded action from the
post-simulation outcome. Remaining refinement: call the last measurement the finalized next
velocity, part of `s_(t+1)`, rather than the current speed.

### Q2 - Authoritative transform and sampling point (passed 2026-09-01)

Candidate answer, lightly normalized for terminology: The authoritative transform is Mover's final
synchronized gameplay state. Record it at the end of the movement process, specifically in
`OnPostFinalize`, after movement and collision resolution. A requested movement or visual animation
transform is not authoritative because external simulation conditions can prevent the character
from executing that requested or depicted motion.

Examiner assessment: Passed after teaching. The candidate identified what, when, and why. Interview
refinement: say `OnPostFinalize` rather than only "the end," and explicitly distinguish the
gameplay/Mover state from the skeletal mesh and animation root. Resimulated or invalid callbacks are
rejected from chronological training data.

### Q3 - Why visible-position reset is insufficient (passed 2026-09-01)

Candidate answer, lightly normalized for terminology: Resetting only the visible position leaves
hidden state from the previous episode, including velocity and history. That retained state can
change subsequent movement even if the character appears to start at the correct location.

Examiner assessment: Passed. Interview refinement: examples include linear/angular velocity,
Mover's smoothing or spring state, the previous movement marker, gate phase, action/sequence IDs,
and model/planner history. Each state must be reset, explicitly synchronized, or documented as an
uncontrolled limitation. This answers why position-only reset is invalid; evidence that the actual
reset worked is a separate question.

### Q4 - Reset evidence and limitation (passed 2026-09-01)

Candidate answer, lightly normalized for terminology: Reset-state checks directly compare the
observable state after reset; episode and sequence IDs establish clean data boundaries; repeated
behavior, including similar collision times, supports reproducibility. Even near-identical results
do not prove that every inaccessible hidden state is identical.

Examiner assessment: Passed after one retry. The first attempt relied too heavily on IDs, which
prove identity and chronology rather than physical reset. The bounded claim is that observable
position, yaw, linear/angular velocity, and movement mode reset correctly, no transition crossed an
episode boundary, and two same-seed gate trials behaved closely. Do not claim bitwise determinism or
complete observation of Mover internals.

### Q5 - Rejecting stale and cross-reset transitions (passed 2026-09-01)

Candidate answer, lightly normalized for terminology: Episode IDs prevent transitions from crossing
resets, sequence IDs require consecutive states, and action IDs ensure the recorded action belongs
to that exact movement step.

Examiner assessment: Passed after teaching. A transition is accepted only when its previous and next
states share the active episode, its finalized sequence is adjacent, and its applied action identity
matches the attempted step. Any mismatch fails closed instead of becoming a false teleport or
state-action training pair.

## 7. Day 1 closeout answers to practise

These are study answers, not passed candidate teach-backs yet.

### What exact evidence shows the feasibility gate passed?

The isolated plugin compiled against UE 5.8 and the actual Game Animation Sample, and the focused
Unreal and Python tests passed. External character-local commands visibly controlled the pawn and
matched Mover's retained command. `OnPostFinalize` supplied valid authoritative post-collision
state. Mover-owned resets produced matching observable seeds without a cross-episode transition.
Complete episodes exported atomically and passed an independent strict loader. Two same-seed timed
gate trials reached the same collision outcome with collision times 3.995 ms apart and terminal
agent positions 0.153 cm apart. Animation-root data remained in a separately typed QA path.

### What remains unproven after Day 1?

The evidence does not prove bitwise determinism or equality of every inaccessible Mover/animation
state. Live gate success and timeout outcomes have not been demonstrated. The Unreal dataset is not
yet sufficiently varied for modelling. A faithful nominal predictor, a learned residual, MPC
improvement, held-out/OOD behavior, runtime latency, deployment, the final comparison video, and
toe/contact or foot-sliding claims all remain unproven.

## 8. Day 2 perturbation defense

### Can your model predict an unpredictable push?

No. If two histories are identical through state `s_t` and only one receives an external kick after
that observation, a deterministic model given only `s_t` and action `a_t` cannot know which future
occurred. Episode 4301 therefore labels the kick for evaluation but never supplies it as a model
input. I report the event-causing transition separately. Once the next disturbed state is observed,
the model can predict recovery from that new state.

### Why not train the residual model on the large error at the kick?

Because that error is not causally predictable from the model inputs. Training on it would either
learn an average sideways jump that is wrong on ordinary frames or require leaking the known event
schedule. The honest result is that the faithful retrospective nominal model is effectively exact
before and after the hidden event and fails only while crossing it. A learned model now needs a
different justified target, such as reconstructing nominal internal context that will not be
available to the deployed planner from recent observable history.

### What does the +250 versus +233.48 cm/s difference mean?

+250 cm/s is the requested additive velocity. +233.48 cm/s is the observed world-Y velocity change
between the finalized states bracketing the 0.023-second event transition. Mover's ordinary update
and smoothing also act during that transition, so 93.39% is a descriptive realized ratio, not a
claim that the API applied only 93.39% instantaneously. The final lateral displacement was 24.43 cm,
and lateral speed fell below 1 cm/s after 0.416 s.
