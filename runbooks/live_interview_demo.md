# MotionWorld live interview demo — operator runbook

This runbook prepares the demo; it does not replace the final human visual check or recording.
Target operator time after the project has built: 5–10 minutes.

## 1. Choose the evidence tier before the call

- **Live overlay:** use only if preflight passes and the current session visibly shows yellow
  authoritative movement, blue nominal prediction, and orange learned-residual prediction.
- **Live nominal plus preserved comparison:** use the accepted live nominal result when the learned
  overlay is not visibly reliable. Then show the preserved offline residual comparison.
- **Preserved evidence only:** use the offline sequence if Unreal, Python, rendering, or the network
  is unreliable. Never keep an unhealthy live process on screen and call it a result.

The orange path is prediction-only. Nominal MPC owns the executed action. Neither path establishes
that residual control is superior.

## 2. Read-only preflight

From the repository root, set the two machine-local paths without writing them into the repo:

```bash
export MOTIONWORLD_UNREAL_EDITOR="/path/to/UnrealEditor-Cmd"
export MOTIONWORLD_UNREAL_PROJECT="/path/to/GameAnimationSample.uproject"
uv run python scripts/preflight_interview_demo.py --require-unreal
uv run python -m motionworld.control.service \
  --config configs/control_service_demo_nominal_mpc.yaml \
  --residual-overlay-config configs/live_residual_overlay_demo.yaml \
  --check-config
```

Continue live only when every line is `PASS`, `live_launch_ready=true`, and
`fallback_ready=true`. This reads configuration and preserved summaries; it does not open raw
episodes, bind UDP ports, edit the Blueprint, or prove a new run successful.

## 3. Apply the reversible D6 settings with Unreal closed

```bash
MOTIONWORLD_DEMO_STAGE=D6 MOTIONWORLD_D6_DEMO_MODE=apply \
  "$MOTIONWORLD_UNREAL_EDITOR" "$MOTIONWORLD_UNREAL_PROJECT" \
  -unattended -nop4 -nosplash \
  -ExecutePythonScript="$(pwd)/scripts/configure_d5_nominal_mpc_unreal.py"
```

Stop if the command fails. Do not manually approximate the manifest values. The apply step creates
a recoverable settings backup and verifies Blueprint readback.

## 4. Run the live loop

Terminal A:

```bash
uv run python -m motionworld.control.service \
  --config configs/control_service_demo_nominal_mpc.yaml \
  --residual-overlay-config configs/live_residual_overlay_demo.yaml
```

Terminal B: launch the normal graphical Unreal Editor/game, press Play once, and wait through the
warm-up/reset. Confirm these five facts before presenting:

1. Yellow is the authoritative Unreal trail.
2. Blue and orange begin at the same current state and move forward as the observation changes.
3. Blue is nominal prediction; orange is learned-residual prediction under the **same** selected
   action sequence.
4. The character moves under nominal MPC, then reobserves and replans.
5. Stopping Python causes bounded safe stop; it does not leave runaway motion.

If the paths are absent, stale, confusing, or the character does not move, stop and use the
fallback. Do not troubleshoot during the interview.

## 5. Restore every time

Close the graphical editor and stop Python before restoring:

```bash
MOTIONWORLD_DEMO_STAGE=D6 MOTIONWORLD_D6_DEMO_MODE=restore \
  "$MOTIONWORLD_UNREAL_EDITOR" "$MOTIONWORLD_UNREAL_PROJECT" \
  -unattended -nop4 -nosplash \
  -ExecutePythonScript="$(pwd)/scripts/configure_d5_nominal_mpc_unreal.py"
```

The restore must succeed. A missing or mismatched backup is a stop condition, not permission to
overwrite settings manually.

## 6. Truthful fallback sequence

Use the already preserved files in this order:

1. `artifacts/interview/architecture.svg` — Unreal/Python authority boundary.
2. `artifacts/demo/d5_nominal_mpc_live/summary.json` — accepted live observe/plan/execute/replan.
3. `artifacts/residual/recursive_001/recursive_comparison.png` — recursive validation comparison.
4. `artifacts/planning/offplan_001/offline_paired_planner.png` — matched offline plan disagreement.
5. `artifacts/planning/runtime_001/README.md` — why residual MPC is not claimed live.

Say “preserved live evidence” for D5 and “offline matched comparison” for the residual planner.
Never describe the fallback plots as the current live session.
