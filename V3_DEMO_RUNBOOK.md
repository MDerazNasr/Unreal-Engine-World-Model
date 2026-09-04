# V3 Two-Obstacle Demo Runbook

## What the recording shows

- A large red obstacle and a smaller orange obstacle move on different deterministic schedules.
- The character changes route around obstacle one, reverses its lateral direction around obstacle
  two, returns toward the green goal, and stops inside the 100 cm arrival zone.
- Blue is the nominal world-model forecast, orange is the learned residual forecast under the same
  selected actions, and yellow is Unreal's collision-finalized path.
- Nominal CEM executes only the first selected action, then observes and replans.

## Before recording

Pause browser video, game streaming, or other CPU/GPU-heavy applications. A deliberately preserved
replay under simultaneous video load missed enough deadlines to collide; stale results failed safe,
but the contention makes a poor presentation. V3 does not need an internet connection.

Start the controller from the repository root:

```bash
.venv/bin/python -m motionworld.control.service \
  --config configs/control_service_demo_nominal_mpc.yaml \
  --two-obstacle-config configs/live_two_obstacle_demo.yaml
```

Require `"health": "running"` and `"ready": true` before pressing Play.

## Record

1. Bring Unreal Editor fully to the foreground and begin screen recording.
2. Press Play once and wait through the short reset warm-up.
3. Keep recording while the red and orange obstacles appear in sequence and the yellow trail bends
   around them.
4. Stop recording as soon as the character reaches the green target and remains still. Do not wait
   for the 30-second diagnostic arena cutoff.
5. Press Escape to stop Play, then stop Python with Control-C.

Suggested narration:

> Unreal owns collision and sends the exact current character state plus both obstacles' clocks and
> geometry. My world model rolls candidate actions into the future and predicts where both moving
> obstacles will be. CEM chooses one safe sequence, executes only its first action, and replans from
> Unreal's real result. Yellow is reality, blue is the nominal prediction, and orange is the learned
> correction under the same actions.

## Claim boundary

Call this a narrow state-space world model with two reproducible analytic moving obstacles. Do not
call their motion random or claim the learned residual owns control. The live result establishes
two-obstacle nominal world-model MPC, not general navigation or learned-control superiority.

## Restore after recording

Close Unreal Editor first, then run:

```bash
MOTIONWORLD_V3_DEMO_MODE=restore \
  "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor" \
  "/Users/mderaznasr/Documents/Unreal Projects/GameAnimationSample/GameAnimationSample.uproject" \
  -unattended -nop4 -nosplash \
  -ExecutePythonScript="$(pwd)/scripts/configure_v3_two_obstacle_demo_unreal.py"
```

V1 remains at `demo-v1`; one-obstacle V2 remains at commit `ce68698`.
