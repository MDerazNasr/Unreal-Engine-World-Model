# V3 two-obstacle live evidence summary

Date: 2026-09-04  
Episode: `7801`  
Accepted session: `149FAA6F1546`  
Manifest identity: `74547c0febd9579f15676231acbd4b81f1f868d3ac76c5645e4de47ab30755e3`

Source log at audit time:
`~/Library/Logs/Unreal Engine/GameAnimationSampleEditor/GameAnimationSample.log`

## Accepted optimized run

- Arena initialization reported `obstacle_count=2`.
- Logged positions show the first steering transition from
  `(-522.28,59.87,88.27)` to `(-384.87,-16.06,88.27)`.
- The second encounter passed through `(227.44,-32.87,88.27)`.
- The arrival latch stopped at `(737.58,57.78,88.27)`, 85.06 cm from target center.
- Terminal audit: `reason=timeout scenario_time_s=30.037526 collision_count=0`; timeout followed
  the already-stable arrival stop and is not presented as target detection.
- Network closeout: 442 observations, 340 accepted actions, 83 stale rejections, 101 misses,
  70 holds, 31 safe stops, zero malformed packets, and zero evidence drops.

## Retained tuning/failure outcomes

- `E81F81FFD94C`: collision-free target-zone arrival, but 100 safe stops; valid tuning evidence,
  rejected as the polished presentation run.
- `A0AF978F0C49`: primary-gate collision at scenario time `10.500024`, aggregate collision count 1,
  followed by terminal safe stop and coordinated freeze of both obstacles. The replay ran while a
  browser video was active and is retained as a real failed outcome rather than pooled with success.

Only optional gray CEM-candidate visualization was removed between the failed/tuning runs and the
accepted run. Nominal planning, two-obstacle cost, executed actions, blue nominal forecast, orange
learned forecast, yellow realized trail, geometry, and safety contracts were unchanged.

## Automated validation

- Complete Python suite: 798 passed.
- Ruff and `git diff --check`: passed.
- Actual `GameAnimationSampleEditor Mac Development -architecture=arm64+x86_64`: passed.
- Complete `MotionWorld.` Unreal automation suite: 20 tests passed, exit code 0.
