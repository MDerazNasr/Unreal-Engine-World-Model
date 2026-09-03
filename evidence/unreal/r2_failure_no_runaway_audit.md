# R2.4 aggregate no-runaway audit

Date: 2026-09-04 Europe/Copenhagen

Acceptance decision: PASS for “confirm no tested failure produces runaway motion.”

For this gate, runaway means non-finite or above-bound control/state, an obsolete or invalid action
reaching gameplay, or continued nonzero motion after the declared reset/three-miss fallback. A
counter alone cannot disprove runaway: every accepted case below includes command-echo or
authoritative finalized-state evidence, and the motion cases also include candidate observation.

| Failure case | Admission/fallback result | Execution evidence | Outcome |
| --- | --- | --- | --- |
| Service absent, episode 7281 | 0 accepted; two initial-zero holds then 199 safe stops | 203 exact zero echoes; ten stationary state samples | No motion |
| Service killed during motion, episode 7293 | last bounded action held for two misses; exact zero on the third | velocity changes from exact `(100,0)` before kill to zero afterward and remains zero | Bounded move, then stop |
| Clean service restart, episode 7294 | prior identity/state cleared; only fresh 7294 actions admitted; late same-episode replies rejected | accepted commands and finalized velocity are exact `(100,0)`; fallback handles late replies | Fresh bounded motion only |
| Delayed valid action, episode 7295 | sole 254.645 ms action rejected stale; 0 accepted | zero echoes and twelve stationary state samples | No motion |
| Old-episode action, episodes 7296→7297 | sole retained 7296 packet rejected after verified 7297 reset; 0 accepted | 233 zero echoes and nine stationary state samples | No cross-reset motion |
| Malformed/non-finite actions, episode 7298 | exactly two malformed rejections separated by valid recovery; invalid packets never accepted | exact bounded `(100,0)` echoes/state, then verified reset to zero | Bounded move, recover, reset/stop |
| Maximum telemetry plus full evidence log, episode 7300 | 19 accepted bounded actions; 2 stale rejections; log cap writes 8 and drops 395 | no bad echo; finalized velocity exact `(100,0)`; subsequent verified reset zero | Bounded move, then stop |

The independent speed-bound run for episode 7261 additionally proves that a raw `(1000,1000)`
request is direction-preservingly clamped to `(116.672619,116.672619)`, norm 165 cm/s, before
Unreal admission. Across every accepted failure-injection case, all applied nonzero commands are at
or below this bound, rejected packets do not appear as gameplay commands, and loss/reset paths
reach exact zero. No evidence supports non-finite, unbounded, obsolete, or persistent unintended
motion.

Source evidence:

- `evidence/unreal/r2_service_absent_safe_stop.log`
- `evidence/unreal/r2_service_kill_safe_stop.log`
- `evidence/unreal/r2_service_restart_recovery.log`
- `evidence/unreal/r2_delayed_action_stale_rejection.log`
- `evidence/unreal/r2_old_episode_action_rejection.log`
- `evidence/unreal/r2_invalid_action_rejection.log`
- `evidence/unreal/r2_telemetry_saturation.log`
- `evidence/unreal/r2_live_echo_speed_bound.log`

Final-test episodes 5301/5302 opened: zero.
