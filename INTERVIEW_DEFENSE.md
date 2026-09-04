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

### Why use paired seeds and a paired bootstrap?

Each seed fixes the same reset and scenario for nominal and residual MPC, so their within-seed
difference removes much of the variation caused by scenario difficulty. The bootstrap resamples
complete pairs, not individual controller runs, because the pair is the independent comparison
unit. The primary estimand is residual-minus-nominal timed-gate success probability. Twelve pairs
are planned, at least ten must be valid, and the small sample means an interval overlapping zero is
unresolved rather than proof that the controllers are equal.

### Why do timeouts and deadline misses remain valid results?

They are consequences of deploying the controller under the promised task and runtime contract.
Discarding them would condition the analysis on successful behavior and bias the comparison. Only
predeclared infrastructure faults—such as the wrong manifest, a failed reset, or unusable logging—
can invalidate an attempt, and every invalid attempt is retained in the audit trail.

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

### What exactly does the residual predict, and why use a local frame?

It predicts six corrections: planar position and velocity, yaw, and yaw rate. Planar corrections use
the previous observed facing frame, so forward and sideways retain the same meaning at every world
heading and the frame is known at prediction time. Using actual next facing would leak the answer.
Yaw is the shortest signed scalar correction, avoiding the plus/minus 180-degree discontinuity. A
zero output returns the exact nominal state; vertical motion is outside the P0 contract and fails
closed rather than being silently ignored.

### Why exclude absolute position, heading, goals, and the moving gate from model inputs?

Free-space execution dynamics should not change when I translate or rotate the same motion in the
world, so I encode velocities, actions, and nominal changes in the previous-facing local frame. The
goal and analytically known gate belong in the planner cost, not character dynamics. Including them
could lower validation error by memorizing scenario correlations without learning how an action
changes the character. If contact errors later prove important, I would add contact context only as a
declared ablation and compare it fairly.

### Why an MLP instead of a GRU or Transformer?

The state is low-dimensional and mostly observed, and four observations cover the hypothesized controller lag. The MLP is faster and easier to debug. This is a falsifiable simplicity choice: if the history MLP fails while error signatures indicate longer hidden state, a recurrent model becomes justified.

### Why CEM rather than gradient-based planning?

CEM handles bounded actions and non-differentiable analytic collision costs, is simple to batch, and does not require differentiating the whole service. Its tradeoff is sample cost, addressed through action knots, warm starts, and latency measurement.

### If CEM adapts, how can nominal and residual MPC use identical candidates?

They use identical initial distributions and the same pre-generated standard-normal noise. Their
first-iteration physical candidates are therefore identical. After costs are evaluated, different
dynamics models may select different elites, so later means, variances, and physical candidates can
legitimately diverge. Requiring identical later candidates would suppress part of the planner's
causal response. The defensible fairness claim is common random numbers plus identical optimizer,
bounds, horizon, cost, and compute—not identical adaptive trajectories after model-dependent costs.

### Why five action knots rather than fifteen independent actions?

With two velocity components, fifteen knots make a 30-dimensional search. The first bounded toy
attempt showed that 256 candidates and three CEM iterations were too sparse in that space. Five
knots reduce it to 10 dimensions and are held across 15 model steps. The one-knot quadratic test only
proves the optimizer math; the integrated gate experiment must still show that five knots are
expressive enough.

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

### Q6 - Why must reset clear hidden state? (passed 2026-09-03)

Question: Why is returning only the visible transform to the same pose insufficient for a fair
paired controller comparison?

Candidate answer, lightly spelling-normalized: "Because the hidden states remain and affect the
subsequent action."

Examiner assessment: Correct. Hidden velocity, angular velocity, Smooth Walking spring state,
previous-action state, model history, planner warm start, gate phase, and protocol sequence can all
change the next outcome despite an identical visible pose. Interview-ready refinement: distinguish
state that we explicitly reset, state that we resynchronize from authoritative Unreal observations,
and inaccessible state that remains a declared limitation.

### Q7 - Why not use future recorded timestep values in live MPC? (passed 2026-09-03)

Question: Why is replaying the recorded `dt` sequence acceptable as a retrospective oracle but not
as the live planner's future substep schedule?

Candidate answer, lightly spelling-normalized: "Because it would not be accurate. It would act
almost as a prediction that would not be reflected in the actual timestep."

Examiner assessment: Passed after refinement. The decisive issue is causality: future callback
durations are not known when CEM evaluates candidate actions. Supplying a previously recorded future
`dt` sequence would give the planner information unavailable at deployment and would not match the
next live run. The causal deployment policy is therefore three fixed 1/30-second substeps per 100 ms
control step; recorded `dt` remains evaluation-only.

### Q8 - Why can one-step accuracy fail inside MPC? (learning; answer supplied 2026-09-03)

Question: Why can a residual model that looks accurate on one-step validation still select a worse
MPC action, and what evidence finally determines whether it helped?

Candidate answer: "I don't know."

Teacher answer: One-step validation repeatedly starts from real Unreal states. MPC recursively feeds
predicted states back into the model, so small errors compound and later queries can leave the
training distribution. CEM evaluates many candidates and can select trajectories that exploit these
model weaknesses because they look artificially cheap. Only paired same-seed authoritative Unreal
execution can establish that the resulting changed action improves control.

Examiner assessment: Not yet passed. The candidate must later explain, unaided, recursive error,
planner/model exploitation, why the model's own predicted return is not ground truth, and why Unreal
adjudicates the fourth causal link.

### Q9 - Why carry three sequence identities? (learning; partial answer 2026-09-03)

Question: Why does a control observation need an episode ID, a 10 Hz observation sequence, and the
underlying `OnPostFinalize` state-sample sequence instead of one shared counter?

Candidate answer: "To make sure we're not running anything redundant into the next episode that
could affect outcomes."

Teacher reference answer: Episode ID rejects packets across resets. Observation sequence identifies
the control decision that an action must echo. State-sample sequence identifies the exact higher-rate
authoritative sample and proves that nominal context was captured from that same finalized state.
They advance for different events, so collapsing them would lose either reset safety, action
matching, or state/context alignment.

Examiner assessment: Partial, not yet passed. The answer correctly explains why episode identity
prevents old work from leaking across reset boundaries. It does not yet explain that observation
sequence binds the returned action to one 10 Hz decision, or that state-sample sequence proves the
observation and nominal context came from the same higher-rate `OnPostFinalize` state. Retry later.

### Q10 - Why are action validation, admission, and clamping separate? (learning; partial answer 2026-09-03)

Question: A packet is valid v1 JSON and contains a finite local velocity. Why must Unreal still test
its episode/sequence against the current outstanding observation and clamp again after local-to-world
conversion? Also explain why Python and Unreal planner timestamps are not directly compared.

Candidate answer: "Python can be considered a little bit unreliable because, for example, it could
return action 52 after Unreal has reset the episode, so you have to check against an overall more
reliable source."

Teacher reference answer: Schema validation proves only that the packet is well formed. Admission
proves it is relevant now: same episode, exactly the unanswered observation, not stale, future, or a
duplicate. Unreal then enforces the velocity bound at its own trust boundary after coordinate
conversion, so a Python bug or delayed/replayed packet cannot bypass safety. Python's monotonic clock
measures planner duration; Unreal's monotonic clock measures observation-send to action-receive.
Their epochs are unrelated, so comparing their absolute timestamps would be invalid.

Examiner assessment: Partial, not yet passed. The answer correctly identifies Unreal as the
authoritative episode owner and explains why a structurally valid Python result can be obsolete
after reset. It still needs to distinguish schema validation from episode/sequence admission,
explain the final clamp after local-to-world conversion, and explain why absolute monotonic clocks
from two processes cannot be compared. Retry after R1.3.

### Q11 - Why use lossy UDP for a control loop? (teacher answer supplied)

Question: UDP can drop, duplicate, and reorder packets. Why is localhost UDP still appropriate for
this 10 Hz P0 control loop, why do we not retransmit a missing action, and why are both nonblocking
sockets and a maximum datagram count per poll required?

Candidate answer: "I don't know."

Teacher reference answer: UDP preserves one-message-per-datagram boundaries and avoids TCP stream
framing and connection lifecycle for two processes on one machine. A retransmitted action may arrive
after its observation has expired, so identity admission discards duplicate/reordered work and a
missing result becomes an explicit deadline miss handled by the frozen fallback. Nonblocking sockets
prevent waiting, but do not stop an endlessly nonempty receive queue from consuming a frame; the
16-datagram poll budget bounds CPU work as well as blocking time.

Examiner assessment: Not passed. The teacher answer was supplied at the candidate's request. Retry
without notes after completing Gate R1.

### Q12 - What do cross-language golden fixtures prove? (awaiting candidate answer)

Question: Why are Python-only and Unreal-only parser tests insufficient? What does a shared golden
fixture prove, and what important behavior does it still not prove?

Candidate answer: "I don't know."

Teacher reference answer: Each side can be internally correct while disagreeing about field names,
types, numeric limits, optional values, or identity semantics. Feeding the same declared bytes across
both implementations proves they agree on that wire contract, including representative boundary
and rejection cases. A finite fixture corpus cannot prove every packet, live timing, packet loss,
deadline fallback, or gameplay application. Those require bounded malformed tests and later
end-to-end runtime tests in the actual sample.

Examiner assessment: Awaiting unaided answer.

### Q13 - Why test the protocol inside the actual Unreal sample? (teacher answer supplied)

Question: If the isolated plugin already compiles and its automation passes, what additional claim
does building and testing it inside the actual Game Animation Sample support? What does it still not
prove?

Candidate answer: "I don't know."

Teacher reference answer: The actual-sample run checks integration assumptions that an artificial
host cannot: the real enabled-plugin set, module/dependency graph, target rules, platform binary,
resource discovery, and test execution environment. It shows that the protocol seam is compatible
with the project we will demo. Because R1 deliberately has no bridge connection, it still does not
prove live observation timing, action deadlines/fallback, coordinate conversion, or gameplay
control; those belong to the R2 vertical slice.

Examiner assessment: Not passed. The teacher answer was supplied at the candidate's request. Retry
without notes after completing the first live vertical slice.

### Q14 - Can Python forcibly cancel an obsolete planner thread? (teacher answer supplied)

Question: When observation 13 arrives while Python is still planning for observation 12, why is it
not enough merely to ignore action 12 after planning finishes? Can Python safely kill that planning
thread, and what guarantees does the service actually provide?

Candidate answer: "I don't know."

Teacher reference answer: Ignoring the late result protects correctness but can still let obsolete
work consume the only worker and delay observation 13. Python cannot safely kill an arbitrary
thread. The service therefore sets a cooperative cancellation event, retains at most one newest
pending observation, and never publishes a result unless its episode/sequence is still current.
Planners must check the event at bounded internal boundaries. Even if a planner ignores it, the old
result cannot be sent as current; the bounded shutdown timeout faults diagnostics rather than
blocking socket release or process exit indefinitely.

Examiner assessment: Not passed. The teacher answer was supplied at the candidate's request. Retry
without notes after the live echo round trip.

### Q15 - Why does the Unreal runtime use two clocks? (partial; retry required)

Question: Why are 10 Hz observation boundaries based on Unreal simulation time while the 100 ms
action deadline is based on Unreal monotonic wall time? What failure would occur if simulation time
were used for both?

Candidate answer: "the simulation time presents predicted values so these could be incorrect and
not actually match up with the wall time and or the collision time."

Teacher reference answer: Simulation time identifies when the authoritative world state exists, so
it gives stable 100 ms world-timeline slots and naturally stops producing observations while the
world is paused. Monotonic wall time measures the real delay between Unreal sending an observation
and receiving its action. If the deadline used simulation time, pausing or slowing the simulation
could make a genuinely late Python result appear timely. Using Unreal's own monotonic send/receive
clock also avoids comparing unsynchronized clocks across processes.

Examiner assessment: Partial, not passed. The answer correctly recognized that simulation time and
real elapsed time can disagree, but incorrectly called simulation time predicted. Unreal simulation
time is the authoritative world timeline: finalized state and collision events exist on it. The
monotonic clock is separately authoritative for real process/network delay. Retry after the live
round trip and explicitly explain what pause or time dilation would do to a simulation-time
deadline.

### Q16 - How does a world-space goal become a character-local command? (awaiting candidate answer)

Question: The reactive controller receives a world-space goal, but Unreal's action is character-
local (`+X` forward, `+Y` right). Using authoritative facing `(f_x, f_y)`, how do you calculate the
local command direction, why is the inverse rotation used, and which speed limit wins?

Candidate answer: No conceptual answer supplied; the candidate replied only that the Unreal
configuration task was done.

Teacher reference answer: Subtract authoritative world position from the target and normalize its
planar direction `(d_x, d_y)`. The character's world forward is `(f_x, f_y)` and world right is
`(-f_y, f_x)`, so the inverse rotation gives local forward
`f_x d_x + f_y d_y` and local right `-f_y d_x + f_x d_y`. It is the inverse because we are
expressing an existing world vector in the character basis; Unreal later applies the forward
rotation when producing the Mover command. The magnitude is the minimum of reactive cruise speed,
the Python configured ceiling, and Unreal's observed effective max speed. Unreal still performs the
final independent finite/planar/magnitude clamp after converting back to world space.

Examiner assessment: Still awaiting an unaided answer after the R2.3 live proof; task completion is
not evidence of conceptual mastery.

### Q17 - Why is a stale reply a successful safety result rather than an applied action? (awaiting candidate answer)

Question: In live episode 7211, Unreal emitted observation 8 and then observation 9 before Python's
reply to 8 arrived. Why is rejecting reply 8 correct, why must it not be relabelled as action 9, and
what evidence proves it did not affect episode 7212?

Candidate answer: Pending.

Teacher reference answer: Observation 8 describes an older finalized state, so its command was
computed for conditions that are no longer the current control decision. Relabelling it as action 9
would fabricate causality: the payload was never computed from observation 9. Unreal therefore
keeps one outstanding identity, rejects the superseded reply as stale, and accepts only a reply
whose episode and source sequence match the current outstanding observation before its deadline.
At the reset boundary, it clears outstanding/action state; episode 7212 then starts at observation
zero with `previous_action_present=false` and `previous_action_source=-1`. The live log contains no
7211 action accepted under episode 7212.

Examiner assessment: Not passed. The teacher answer was supplied at the candidate's request. Retry
later without notes. Live evidence is `evidence/unreal/r2_live_echo_stop_sequence_reset.log`.

### Q18 - Why is visible stillness insufficient evidence for service-loss safety? (awaiting candidate answer)

Question: In episode 7281 the pawn visibly remained stopped while Python was absent. Why is that
observation alone insufficient, and which runtime facts distinguish a working fail-safe from a
disabled or broken controller path?

Candidate answer: Pending.

Teacher reference answer: Visible stillness alone is ambiguous: the network component might be
disabled, reset might have failed, observations might never be sent, or an unrelated system might
hold the pawn. The accepted trace shows the network session and verified reset started, 201
observations were emitted, zero Python actions were accepted, observation zero had no prior action,
the first two misses held the initial zero command, and later misses explicitly selected safe zero.
Matching zero bridge echoes and unchanged authoritative finalized states prove that policy reached
Mover execution. Together those facts establish fail-safe behavior and exclude stale action reuse.

Examiner assessment: Awaiting unaided candidate answer after the service-absent trial.

### Q19 - What exactly happens after the Python service dies during motion? (teacher answer supplied)

Question: If Python dies while the last validated command is forward, why does the pawn not stop on
the first missed response, and what proves that the third-miss stop was actually executed?

Candidate answer: The candidate supplied the operational observations `moving` before the service
was killed and `stopped` afterward, but did not yet supply a conceptual explanation.

Teacher reference answer: A single missed response may be transient jitter, so the runtime retains
the last fully validated action for the first and second consecutive misses. At the third miss it
replaces that action with exact local zero and continues selecting zero while responses remain
absent. In episode 7293, action 85 was the last accepted `(100,0)` command. Two subsequent command
cycles still echoed `(100,0)`; the next echoed `(0,0)`, and all later echoes remained zero. The
authoritative finalized velocity then changed from `(100,0,0)` to `(0,0,0)`, and later samples kept
the same position. That chain proves the fallback reached Mover execution; the candidate's visual
confirmation independently agrees with it.

Examiner assessment: Not passed. The operational observation is valid evidence, but the candidate
must explain the policy and evidence chain unaided in a later teach-back.

### Q20 - What does recovery "without stale state" mean? (teacher answer supplied)

Question: Episode 7294 had many stale same-episode replies. How can it still prove recovery without
stale state, and what claim does it not prove?

Candidate answer: The candidate confirmed `moving` after the clean service restart but did not yet
supply a conceptual explanation.

Teacher reference answer: The recovery requirement concerns state crossing the killed-service and
episode boundary. The restarted Python process began with no current identity or tracked episode;
Unreal verified a fresh reset, explicitly cleared prior action state, and emitted episode-7294
observation zero with no previous action. The first applied forward command explicitly named 7294/0,
so episode 7293 was not reused. Later same-episode replies missed their current observation and were
counted/rejected as stale rather than relabelled. Thus lifecycle recovery is proven, while the 701
stale rejections mean this run does not prove stable 10 Hz performance, zero gaps, or the Gate-R2
latency criterion.

Examiner assessment: Not passed. The visual observation supports the runtime evidence, but the
candidate must later distinguish cross-lifecycle stale-state exclusion from same-episode late-packet
performance unaided.

### Q21 - How can a valid action still be unsafe to apply? (teacher answer supplied)

Question: The delayed-action probe creates a correctly encoded, finite, bounded action with the
right episode/source identity and a short embedded Python planner duration. Why must Unreal still
reject it after the 250 ms transport delay?

Candidate answer: The candidate confirmed that the pawn remained stopped after the delayed packet,
but did not supply a conceptual answer.

Teacher reference answer: Structural validity says the packet has the correct schema, values, and
declared identity; it does not establish that the described observation is still the current control
decision. The 100 ms deadline is measured from Unreal's own monotonic send time to its own receive
time. After 250 ms, the deadline has expired and usually a newer observation is outstanding, so the
action was computed for obsolete world state. Python's embedded planner duration excludes the
injected transport hold and is not trusted for admission. Applying or relabelling the packet would
fabricate causality. Unreal must count it stale, leave it unapplied, and follow the bounded fallback.

Examiner assessment: Not passed. The operational observation agrees with the trace, but the teacher
answer was supplied; retry later without notes and explain structural versus temporal validity.

### Q22 - Why trigger the old-episode packet from observation zero instead of a timer?

Question: Why does the reset-boundary probe wait for verified observation zero from episode 7297
before sending its retained episode-7296 action, instead of sleeping for a fixed interval after the
reset request?

Candidate answer: The candidate supplied the operational observation `stopped` through the live
exercise but has not yet explained the reset-boundary reasoning unaided.

Teacher reference answer: A reset request is not proof that the reset has completed. Editor load,
frame scheduling, Mover finalization, and reset verification can all vary, so either Python wall time
or predicted simulation time could fire before or long after the authoritative boundary. Episode
7297 observation zero is emitted only after Unreal has verified the new reset, installed the new
episode identity, cleared prior network action state, and restarted sequencing at zero; its absent
previous action is an additional observable check. Sending the retained 7296/0 packet only after
that observation isolates one cause for rejection: the packet names an obsolete episode. Unreal
must count it as rejected/stale and must not relabel or apply it.

Examiner assessment: Not passed. The operational observation agrees with the accepted trace, but the
candidate must still explain the difference between a reset request, elapsed time, and an
authoritative verified reset boundary unaided.

### Q23 - Why separate invalid packets with valid recovery actions?

Question: Why does the malformed/non-finite probe establish valid motion first and place a valid
matching action between its two invalid packets?

Candidate answer: The candidate observed and reported `move then stop`, with no runaway behavior,
but has not yet explained the separation and fallback reasoning unaided.

Teacher reference answer: The test has two claims to isolate. First, malformed syntax and non-finite
values must fail structural parsing before they can reach action admission or Mover. Second, their
absence must enter the already-declared bounded missed-response policy. Starting with valid forward
actions proves the faults occur during real control. Separating them with a valid current action
resets the consecutive-miss count, so each fault causes only one hold of the last validated bounded
command rather than combining into an unrelated multi-miss safe stop. A valid response after each
fault proves recovery; exact malformed counters, no invalid acceptance, bounded command echoes, and
authoritative state prove safety.

Examiner assessment: Not passed. The operational observation agrees with the accepted trace; require
the candidate to distinguish structural rejection, temporal admission, and missed-response fallback
unaided in a later teach-back.

### Q24 - Why must telemetry and logging be non-control-critical?

Question: What should happen when every action carries maximum diagnostic trajectory telemetry and
Unreal's evidence log reaches its capacity?

Candidate answer: The candidate completed the live exercise and visually confirmed forward motion
followed by stop, but has not yet explained the control/telemetry separation unaided.

Teacher reference answer: The command, identity, and deadline determine control admission;
trajectory/cost telemetry only explains the planner's decision. Its schema and length are bounded so
parsing work and datagram size cannot grow without limit. Evidence logging is separately capped; at
capacity it increments a dropped-line counter and skips the log line. Neither condition may change,
delay, or replace the validated command. Therefore Unreal should continue applying exact bounded
motion while reporting diagnostic drops, with no malformed acceptance or runaway state.

Examiner assessment: Not passed. The operational result agrees with the accepted trace; require an
unaided explanation of why full telemetry and dropped evidence lines cannot change control.

### Q25 - Why are rejection counters alone insufficient to rule out runaway motion?

Question: What evidence distinguishes a packet being rejected from safe execution by the pawn?

Candidate answer: Not yet attempted.

Teacher reference answer: A rejected, stale, or malformed counter proves how the network runtime
classified a received packet, but it does not by itself prove what command remained active or what
Mover executed. The evidence chain must show the fallback decision, the requested/submitted/echoed
command, and authoritative finalized velocity or stationary state. Episode/sequence and reset
records establish which lifecycle the command belongs to. Candidate visual observation is useful
corroboration but is not numerically authoritative. Only that combined chain rules out invalid,
obsolete, unbounded, or persistent unintended motion.

Examiner assessment: Not yet attempted. Require an unaided explanation after reviewing the R2.4
aggregate evidence matrix.

### Q26 - Why can one clean run satisfy several Gate-R2 requirements?

Question: Why is it legitimate to use episode 7221 for consecutive control, identity reconciliation,
and latency instead of repeating those measurements?

Candidate answer: Not yet attempted.

Teacher reference answer: These are different measurements over the same declared round-trip path,
not independent interventions. The untouched raw session contains every emitted observation,
matching accepted action, admission flag, and Unreal-clock latency, so one prespecified audit can
evaluate all three without changing the data. Reuse is legitimate only when each claim's exact
criterion is checked and claim boundaries remain explicit; the same run cannot be stretched to
prove three resets, service loss, or video evidence that it does not contain.

Examiner assessment: Not yet attempted. Require an unaided explanation before Section 3 closes.

### Q27 - Why does configuration automation not invalidate the experiment?

Question: Under what conditions is automated Blueprint setup scientifically equivalent to entering
the same values manually?

Candidate answer: Not yet attempted.

Teacher reference answer: Automation is equivalent when it applies a frozen input selected before
outcomes, changes only the same configuration fields a person would change, reads every value back,
binds the exact manifest and service files by hash, and refuses any mismatch. It must not issue
gameplay commands, modify controller/model logic, inspect results to choose settings, or silently
rerun failures. A recoverable snapshot preserves the prior asset state. The execution and acceptance
evidence still come from Unreal, not from the configuration script.

Examiner assessment: Not yet attempted. Require an unaided explanation after the live apply/readback.

### Q28 - Why do nonzero rejection counters not invalidate the three-reset claim?

Question: Session `8D77D263F54B` ended with nonzero rejected, stale, malformed, missed, and held
response counters. Why can it still support reset isolation, and why is episode 7221 still the
evidence for timing and continuous control?

Candidate answer: Not yet attempted.

Teacher reference answer: The claim assigned to session `8D77D263F54B` is lifecycle isolation, not
stable 10 Hz performance. At each of its three verified resets, the runtime installed the new
episode identity, reported `prior_state_cleared=true`, emitted observation zero with
`previous_action_present=false` and `previous_action_source=-1`, and accepted a newly matched action
zero for that episode. Late or invalid packets were counted and rejected rather than relabelled or
allowed across a reset, so those counters expose load and timing faults without demonstrating state
leakage. This run must not be used to claim zero gaps or Gate-R2 latency. Those separate claims come
from the untouched episode-7221 session, whose 224 observations and actions reconcile consecutively
with zero gaps or failure counters and whose Unreal-clock latency satisfies the declared bound.
Using separate, claim-scoped runs is stronger than hiding the failures or stretching either run
beyond what it measured. Final prediction episodes 5301 and 5302 remain sealed.

Examiner assessment: Not passed. The reference answer was supplied before an unaided candidate
teach-back. Require the candidate to distinguish reset-boundary correctness from within-episode
timing/continuity evidence and explain why rejected stale work cannot be renamed as current work.

### Q29 - Why do branching futures qualify as a world-model demonstration?

Question: Why do forward, left, right, and stop futures generated from one authoritative Unreal
state demonstrate an action-conditioned world model, and what prevents the display from being only
decorative trajectories?

Candidate answer: Not yet attempted.

Teacher reference answer: The four branches begin from the same collision-finalized Unreal state and
differ only in the proposed future action sequence. A learned or analytical transition model then
rolls each sequence forward, so the display answers the action-conditioned counterfactual question,
"What state trajectory does the model predict if I take these actions?" Every displayed point must
declare its units and frame—for example, centimetres in Unreal world space after converting any
character-local action—and carry the source episode and observation identity. The selected branch's
first action is sent with that same identity; stale results are rejected, and the predicted path is
compared with the later collision-finalized Unreal states. That identity chain and prediction-versus-
actual comparison make the visualization auditable rather than decorative. A stop action means zero
requested input and may predict physical braking over several steps, not an instantaneous frozen
pose. The demonstration proves that the implemented model can generate distinct, causally aligned
futures and participate in closed-loop planning. By itself it does not prove that the model is
generally accurate, that the learned residual is better than the nominal model, or that the selected
controller improves outcomes statistically; those require held-out errors and controlled trials.

Examiner assessment: Not passed. Require an unaided explanation of the fixed-start counterfactual,
units/frame conversion, episode-observation identity chain, braking semantics, and claim boundary.

### Q30 - Why does a new observation remove the prediction but a deadline stop keep the actual trail?

Question: Why must an older predicted path disappear as soon as Unreal emits a newer observation,
and why is the realized trail allowed to survive a same-episode deadline safe stop?

Candidate answer: Not yet attempted.

Teacher reference answer: A prediction is conditional on one exact source state, target context, and
observation identity. As soon as Unreal emits a newer collision-finalized observation, that older
future is no longer the current forecast, even if no replacement action has arrived, so leaving it
visible would present stale imagination as current. The actual trail has different semantics: it is
historical evidence already measured by Unreal. A missed deadline clears the untrusted prediction
and commands the bounded fallback, but it does not erase what physically happened in the same
episode; retaining that trail lets the display show recovery honestly. Reset, reconnect, controller
switch, target-context change, and end play are true identity boundaries, so they clear both. In
short, predictions expire with their conditioning information, while observations remain evidence
until the episode itself changes.

Examiner assessment: Not passed. Require an unaided explanation that distinguishes conditional
future state from immutable realized evidence and identifies same-episode versus episode boundaries.

### Q31 - Is the four-branch preview MPC, and why does it command zero?

Question: If the system evaluates forward, left, right, and stop futures, why is that not already
model-predictive control, and what does exact-zero desired velocity prove?

Candidate answer: Not yet attempted.

Teacher reference answer: The preview performs the imagination half of model-predictive control but
not the optimization-and-execution half. It takes one collision-finalized Unreal state, applies four
predefined counterfactual action sequences to the same nominal transition model, and displays the
resulting futures. It does not score those paths with the task cost, select the best one, or execute
its first action; the outer action deliberately carries exact-zero desired velocity. The live run
therefore proves that current identity-bound model futures can traverse the real service and Unreal
admission path while the authoritative pawn remains stationary. Zero desired velocity means zero
requested control, not an instantaneous physical freeze: a moving character could still decelerate
according to the dynamics. This run began from a verified settled reset, so all sampled state stayed
stationary. The next MPC checkpoint must add candidates, costs, a selected trajectory, first-action-
only execution, reobservation, and replanning before I can call the closed loop MPC.

Examiner assessment: Not passed. Require an unaided distinction between counterfactual rollout,
optimization, first-action execution, and replanning, including zero-input braking semantics.

### Q32 - What does the first live nominal-MPC run prove, and what does it not prove?

Question: The character moved under `nominal_mpc`; does that mean the controller or learned world
model succeeded?

Candidate answer: Not yet attempted.

Teacher reference answer: Unlike `branch_preview`, `nominal_mpc` scores a CEM candidate population,
selects a trajectory, transmits only its first action for the current episode and observation, then
replans after Unreal finalizes another state. Episode 7504 proves that this loop can repeatedly cross
Python and Unreal with current identity and under the exclusive 100 ms deadline: 387 actions were
admitted from 390 observations, p95 latency was 60.736 ms, and the logged Unreal command echoes
matched. It does not prove that the controller is good. The sampled pawn approached the target,
overshot, and continued oscillating; three observation identities had no admitted action; no gate or
collision objective and no residual comparator were active; and the text log contains no pixels.
The defensible claim is therefore a live nominal-MPC integration prototype, not stable convergence,
robustness, residual superiority, or a population-level control win.

Examiner assessment: Not passed. Require an unaided distinction between loop validity, task success,
visualization evidence, and comparative evaluation.

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

### If the faithful model is exact, what is left for the residual to learn?

It is exact only as a retrospective oracle when I replay the parameter snapshot observed after every
real step. A planner does not own those future snapshots. My causal baseline starts from the current
finalized context and holds those parameters while imagining candidate actions. On corrected episode
4201, every material one-step error aligns with an actual parameter-regime change, and p95 position
error reaches 22.97 cm by 0.5 seconds. The residual question is whether current state/action and short
history predict that sample-specific execution effect without seeing future parameters.

### Is holding current parameters an artificially weak baseline?

It is the smallest honest baseline when no causal future-regime selector has been established: it
uses the complete current state, all audited Smooth Walking memory, current runtime parameters, and
the exact public equations. I also report the completed-step oracle as an upper-bound diagnostic.
An explicit parameter predictor is a valid alternative baseline, so I cannot claim residual learning
is uniquely necessary until I compare against one or explain why its required Blueprint variables
are unavailable. I never remove known spring state or clamp logic to create error.

### Why did four observations of history lose to no history?

History was a hypothesis, not a guaranteed improvement. The history model has 128,390 parameters
versus 106,886, loses the first three examples of every episode, and sees highly correlated windows
from only five scripted training episodes. Meanwhile, the current finalized state, requested action,
runtime parameters, and nominal memory already expose much of the useful transition context. The
four-history model still improved over nominal around parameter changes, but its recursive validation
error was consistently above the no-history model. I therefore selected no-history on validation and
kept the weaker history result. This does not prove recurrent models are useless; it says added
history did not earn its complexity in this bounded dataset.

### Does better residual prediction prove the controller will improve?

No. It only passes the prerequisite for planning. The translational p95 gain is roughly 7-14%, while
the angular gain is much larger, and planner rankings depend on the task cost and candidate actions.
The next causal test holds candidates, cost, seeds, and compute fixed between nominal and residual
MPC, then asks whether changed predictions cause changed actions and better Unreal outcomes. If they
do not, the correct conclusion is better prediction without demonstrated control benefit.

## 9. Day 4 planner defense

### Did both controllers evaluate the same candidates?

They evaluate the exact same 256 physical action sequences in the first CEM iteration, and the
artifact records their common hash. After scoring them, each model can choose different elites, so
its next Gaussian distribution and later physical candidates legitimately differ. The controllers
still have the same seed, noise schedule, state, horizon, knots, candidate and elite counts, bounds,
obstacle trajectory, cost, and iteration budget. Forcing identical later candidates would stop CEM
from adapting to the different model rankings.

### Why does the residual planner's lower predicted cost not prove success?

Because a planner minimizes its model's cost, not measured Unreal cost. OFFPLAN-001 exposes severe
disagreement: the residual model predicts a collision for the nominal-selected plan, while the
nominal model predicts poor progress for the residual-selected plan. This proves the residual affects
decisions, but one model may be wrong and CEM may exploit its error. I need same-seed live Unreal
rollouts to determine actual collision, clearance, and goal progress before claiming better control.

### Why was a roughly ten-second planner useful if MPC has a 100 ms deadline?

It was a correctness-first offline reference implementation. It proved the tensor contracts,
recursive model integration, common-random-number comparison, cost decomposition, and deterministic
artifact generation. Profiling then showed about 71,000 scalar transition calls. A parity-tested
vectorized backend reduced one representative paired solve to 0.244 seconds without changing either
first action. The formal single-controller benchmark is nominal 70.709/81.549 ms median/p95 and
residual 149.655/169.401 ms. Nominal passes the bounded offline compute gate; residual misses all
30 deadlines and is not deployable at 10 Hz yet. A prospective budget sweep then rejected all eight
smaller configurations: the fast ones exceeded the 10% p95 predicted-cost-regret gate. I therefore
did not trade away planning quality or relax the threshold after seeing the outcome. The next step
is model/inference optimization, followed by transport-inclusive measurement—not hiding the miss.

### What does the cross-evaluation matrix tell you?

Its diagonal entries show how each selected plan looks to the model that optimized it. Its
off-diagonal entries show whether the other model agrees. Large disagreement is a risk signal, not
ground truth. It motivates live validation, error inspection near the selected paths, and possibly
an uncertainty or model-disagreement penalty. It cannot tell me by itself which model is physically
correct.

### Why not just use the smaller network that passed prediction quality?

Because prediction was only one gate. The 128/128/64 model stayed within 8.43% of the full model on
all recursive p95 metrics, but CEM found action sequences where the models disagreed badly. When I
evaluated the smaller model's selected plans under the frozen full model, p95 positive cost regret
was over 100 times the reference cost and two newly predicted collisions appeared. Its full-planner
p95 was also above 100 ms. This is a useful negative result: average rollout accuracy did not
protect the optimizer from model error. I rejected the model rather than selecting the metric that
made it look good.

### What would you do next to make residual MPC deployable?

First, I would not put the current 150 ms residual planner into a 100 ms synchronous loop. The
lowest-risk engineering paths are a transport-safe slower control interval as an explicitly changed
experiment, asynchronous planning with stale-action safeguards, or a compiled/native inference
backend with numerical and planning parity. On the modelling side I would train with multi-step and
planner-distribution data or distillation, then repeat recursive, cross-planning, and runtime gates.
The present evidence does not authorize claiming any of those paths works.
