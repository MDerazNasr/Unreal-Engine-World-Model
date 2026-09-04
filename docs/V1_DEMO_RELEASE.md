# MotionWorld interview demo V1

## Release purpose

V1 is the preserved fallback demonstration before obstacle-dodging work begins. It is a real-time,
action-conditioned character-movement world model integrated with Unreal Engine. It is intentionally
not presented as an obstacle-avoidance result or a completed research study.

## What the recording should show

1. Unreal supplies the collision-finalized current character state.
2. Nominal CEM chooses a short action sequence and executes only its first action.
3. The character moves toward the lime target, then Unreal is observed again and planning repeats.
4. Blue shows the nominal forecast for the selected actions.
5. Orange shows the selected learned residual's matched forecast from the same state and actions.
6. Yellow shows the authoritative path actually realized by Unreal.
7. The HUD identifies action ownership, model, episode/observation, horizon, timing, and safety.

## Frozen claim boundary

- Nominal MPC is the only action owner; the learned residual is a prediction overlay.
- V1 demonstrates a live world-model/MPC integration, not stable target convergence.
- V1 does not demonstrate obstacle avoidance, timed-gate navigation, or disturbance recovery.
- V1 does not prove that the learned residual is visually different on every frame or superior for
  live control.
- Frozen prediction episodes 5301 and 5302 remain sealed.

## Accepted evidence before release

- Clean learned-overlay session: `DD64FEF0C742`, episode `7603`.
- 266 contiguous observations and 254 accepted current/before-deadline actions.
- End-to-end latency: 36.048 ms median, 70.162 ms p95, 81.513 ms maximum.
- Maximum authoritative displacement from reset: 17.289 m.
- Python: 762 tests passed; Ruff, lockfile, environment, and package checks passed.
- Actual Game Animation Sample: universal arm64/x86_64 editor build passed.
- Unreal: all 20 `MotionWorld.` automation tests passed.
- Machine-readable evidence: `artifacts/demo/d6_residual_overlay_live/summary.json`.

## Recording and recovery

Follow `runbooks/live_interview_demo.md`. Run preflight first, apply the D6 settings only with Unreal
closed, start the Python service, then start the graphical Unreal session. If blue, orange, yellow,
the target, or the HUD are unclear, stop and use the preserved fallback rather than making a live
claim. After recording, close Unreal and stop Python before running the documented restore command.

The Git tag `demo-v1` identifies the exact saved source/documentation state for this fallback.
