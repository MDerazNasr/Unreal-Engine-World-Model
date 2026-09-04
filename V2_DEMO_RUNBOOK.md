# V2 Moving-Obstacle Demo Runbook

## What the viewer should see

- A bright red physical obstacle moves sideways across the route.
- The character leaves the reset point and replans around it instead of following a fixed dodge.
- Gray paths are sampled CEM candidates, blue is the nominal selected prediction, orange is the
  learned residual comparison under the same actions, and yellow is Unreal's realized trail.
- The character enters the green target's 100 cm arrival zone and remains stopped.

## Start the controller

From the repository root:

```bash
.venv/bin/python -m motionworld.control.service \
  --config configs/control_service_demo_nominal_mpc.yaml \
  --moving-obstacle-config configs/live_moving_obstacle_demo.yaml
```

The first printed status must contain `"health": "running"` and `"ready": true`.

## Record

1. Open `GameAnimationSample.uproject` in Unreal Editor.
2. Begin screen recording before pressing Play.
3. Press Play once and wait through the short reset warm-up.
4. Keep the red obstacle, green target, paths, character, and HUD visible.
5. Stop recording as soon as the character reaches the green target and remains still. Do not wait
   for the 20-second diagnostic arena cutoff.
6. Press Escape to stop Play, then stop the Python service with Control-C.

Suggested narration:

> Unreal sends its collision-finalized state and the moving obstacle's authoritative clock to
> Python. My world model imagines candidate action-conditioned futures. CEM chooses a safe route,
> executes only the first action, and replans from reality. Yellow is what Unreal actually did;
> blue is the nominal forecast; orange is the learned-model comparison. The character avoids the
> physical obstacle with zero collisions and stops inside the target zone.

## Truthful claim boundary

Say “a narrow state-space world model for character motion and one analytic moving obstacle.” The
accepted live result proves the nominal world-model MPC loop dodged the obstacle. The learned model
is a prediction-only comparison overlay; this demo does not prove learned control superiority or
generalization to arbitrary unseen obstacle behavior.

## Restore after the final recording

Close Unreal Editor first, then run:

```bash
MOTIONWORLD_V2_DEMO_MODE=restore \
  "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor" \
  "/Users/mderaznasr/Documents/Unreal Projects/GameAnimationSample/GameAnimationSample.uproject" \
  -unattended -nop4 -nosplash \
  -ExecutePythonScript="$(pwd)/scripts/configure_v2_obstacle_demo_unreal.py"
```

V1 remains frozen at annotated tag `demo-v1` and commit `2d6f005`.
