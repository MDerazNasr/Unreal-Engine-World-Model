# MotionWorld Interview Defense

Status: living rehearsal document.  
Answer rule: state the claim, point to evidence, state the limitation. Draft answers remain provisional until the referenced experiment exists.

## 1. Thirty-second explanation

MotionWorld is a compact action-conditioned residual dynamics model for Unreal character control. A faithful Smooth Walking predictor handles known movement behavior; a small MLP predicts the systematic execution error that remains. CEM evaluates corrected candidate futures and executes the first desired-velocity action before replanning. I compare nominal and residual MPC with identical actions, costs, seeds, and compute, and claim the learned model helped only when its corrected prediction changes the plan and improves same-seed Unreal execution.

## 2. Daniel Holden lens: movement, animation, control, implementation

### Why is your nominal model fair?

It implements the known Smooth Walking structure, carries known intermediate spring state, and substeps at the verified movement rate. The residual is not rewarded for rediscovering public baseline equations. Remaining mismatch is measured before learning, and nominal versus residual MPC differs only in the learned correction.

Evidence required: nominal hand tests, code/reference comparison, recursive Unreal error plot.

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

### Why not NavMesh?

NavMesh provides global/static routing. MotionWorld addresses short-horizon local control under timing, perturbation, and model mismatch. They are complementary layers.

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
