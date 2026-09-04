# MotionWorld Interview Demo Sprint

## Immediate objective

Deliver a visually compelling, technically defensible Unreal demonstration of an
action-conditioned movement world model. The demo must show genuine model predictions,
model-predictive action selection, authoritative Unreal execution, and prediction-versus-reality
evidence. The complete research study remains follow-up scope.

## Truth and safety guardrails

- [x] Describe the system as an action-conditioned movement world model, not a general visual
      foundation model.
- [x] Draw only trajectories produced by the actual nominal or residual rollout code.
- [x] Keep final prediction episodes `5301` and `5302` sealed unless Recovery Gate R7 passes.
- [x] Do not claim that residual control is statistically superior without the locked paired study.
- [x] Preserve Unreal as the authority for realized movement and collision outcomes.
- [x] Preserve episode/sequence validation, deadline rejection, reset clearing, and safe stop.
- [ ] Label prerecorded, offline, paused-state, and live evidence accurately.

## Sprint 1 — Close the runtime foundation

- [x] Audit the accepted three-reset Gate-R2 session and unedited recording.
- [x] Preserve the exact raw log range, configuration, hashes, and machine-readable summary.
- [x] Restore temporary Unreal Blueprint settings and stop leftover services.
- [x] Run focused and full tests, update project records, and commit Section 3.

## Sprint 2 — Build the visual world-model moment

- [x] Load one authoritative current Unreal state into a planner snapshot.
- [x] Generate forward, left, right, and stop futures from that identical state.
- [ ] Render genuine futures in distinct colors with a clear legend.
- [ ] Render the target and any timed-gate geometry.
- [ ] Support a frozen/paused comparison view suitable for explanation.
- [ ] Show model name, horizon, timestep, source observation, and prediction status.

Checkpoint evidence: the strict live adapter, authentic production-rollout branches, and atomic
identity-bound visualization/action protocol pass 661/661 Python tests, Ruff, lock verification,
diff integrity, the strict universal Unreal build, and the actual-sample cross-language fixture.
The default four-branch visualization is 2,252 bytes; its representative complete action is about
3,721 bytes, within the independent 6,500-byte visualization and 8,192-byte action ceilings.
Unreal drawing, the HUD, the actual trail, and live MPC remain open.

D3 checkpoint: Unreal now stores and draws only visualization attached to an admitted current
action, expires prediction when a newer authoritative observation is emitted, and maintains a
separate bounded yellow trail from collision-finalized Unreal states. Reset, reconnect, controller
switch, end play, and a meaningful live target change invalidate the full visualization identity;
a deadline safe stop clears prediction while preserving the same-episode actual trail. Exact-source
actual-sample deployment, the universal Editor build, and the full `MotionWorld.` automation suite
pass. On-screen path alignment remains deliberately open until D4 emits live branch telemetry.

D4 checkpoint: the live `branch_preview` controller now emits four authentic nominal-model futures
from each current authoritative observation while deliberately commanding exact zero desired
velocity. Python and Unreal bind the controller identity and accept only the synchronized strict
telemetry variants. In session `5CBAA02AF440`, episode 7401, Unreal logged 702 contiguous
observations and 691 unique, increasing admitted actions; every admitted command and all 702 command
echoes were exactly zero, 48 authoritative samples remained stationary, and end-to-end latency was
72.614 ms median / 76.372 ms p95 / 87.480 ms maximum. The initial admitted prefix is contiguous
through action 259; ten later action identities are absent and are disclosed rather than presented
as a zero-gap run. Code, cross-language automation, and live admission establish the telemetry path,
but the preserved log does not contain pixels; the distinct-color rendering checkbox stays open
until a person confirms the paths on screen. The reversible demo configuration was restored after
the run, and episodes 5301/5302 remained sealed.

## Sprint 3 — Show planning and reality

- [ ] Render faint CEM candidates and one prominent selected trajectory.
- [x] Execute only the first selected action, then reobserve and replan.
- [ ] Render the authoritative realized trail separately from predictions.
- [ ] Display planning/end-to-end latency and fallback status.
- [x] Enforce current-identity deadline admission for live MPC; retain accurately labelled stepped
      or offline fallback rather than applying stale actions if a later run misses the deadline.

D5 checkpoint: after preserving two rejected runs and one partial run, nominal-only episode 7504
sustained the real observe -> CEM select -> first-action execute -> reobserve loop. Session
`3D16FF3BC647` logged 390 contiguous observations and 387 unique, increasing, before-deadline
actions; identities 0, 194, and 253 had no admitted action. End-to-end latency was 57.765 ms median /
60.736 ms p95 / 86.881 ms maximum. Unreal moved from the verified `(-800,0,90)` reset, passed near
the `(800,0,90)` target, then overshot and oscillated, so this is a live integration result rather
than a stable-convergence or control-win result. The text log cannot prove rendered pixels; the
candidate, realized-trail, and HUD checkboxes stay open pending human confirmation. The exact apply
readback, live audit, raw log, and disclosed failed attempts are preserved; the Blueprint was
restored and episodes 5301/5302 remained sealed.

## Sprint 4 — Add the learned-model comparison if defensible

- [ ] Load the already selected no-history residual checkpoint with strict schema/hash checks.
- [ ] Display nominal prediction in blue and residual-corrected prediction in orange.
- [ ] Keep the same state, action futures, horizon, and cost context for both models.
- [ ] Execute at least one selected action in Unreal and compare both predictions with reality.
- [ ] Present improvement, degradation, or disagreement honestly; do not require a residual win.

## Sprint 5 — Polish one interviewer-focused scenario

- [ ] Use one visually readable target-and-timed-gate scene.
- [ ] Add a controlled sideways push only if it is reliable and visible.
- [ ] Explain that an undisclosed future push is not predictable before observation.
- [ ] Replan after the pushed state becomes authoritative.
- [ ] Demonstrate or preserve reset clearing and service-loss safe stop.
- [ ] Keep the HUD compact and readable at presentation resolution.

## Sprint 6 — Package and rehearse

- [ ] Capture one clean 60–90 second presentation video.
- [ ] Preserve one unedited technical evidence recording.
- [ ] Prepare a fresh-launch runbook and an offline fallback.
- [ ] Run all relevant Python tests, Ruff, lockfile, diff, and available Unreal automation checks.
- [ ] Prepare the 30-second explanation and 90-second narration.
- [ ] Prepare one movement/runtime explanation and one causal/ML explanation.
- [ ] State completed work, limitations, and deferred full-study items explicitly.

## Demo acceptance criteria

- [ ] A viewer can identify the current state, alternative futures, selected future, and actual path
      without reading source code.
- [ ] At least one displayed future can be traced to the real rollout implementation and source
      observation identity.
- [ ] The demo visibly communicates observe -> imagine -> choose -> execute -> compare -> replan.
- [ ] Runtime safety remains active and no stale action is knowingly applied.
- [ ] The candidate can explain why this qualifies as a world model and what it cannot claim.

## Deferred after the interview demo

- Full Recovery Sections 4–13 remain the authoritative research-completion checklist.
- Multi-seed final prediction and paired-control evaluation remain incomplete until their gates pass.
- Statistical superiority, complete reproducibility, and release-candidate claims remain deferred.
