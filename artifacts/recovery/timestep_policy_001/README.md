# TSTEP-001 timestep-policy reconciliation

This recovery experiment selects the causal dynamics integration schedule used inside each 100 ms
MPC planning step. It does not claim live Unreal control or pass the residual runtime gate.

## Evidence boundary

- Exact accepted files: episodes 5101--5105 and 5201--5202, verified against the frozen collection
  plan before parsing.
- Pending prediction-test files opened: zero.
- Physical comparison: 74 validation windows with constant action and current parameters.
- Endpoint: authoritative state linearly interpolated at exactly 100 ms.
- `recorded_dt_replay` is retrospective only; a causal live planner cannot know future callback
  durations.

## Results

| Policy | Position p95 (cm) | Velocity p95 (cm/s) | Yaw p95 (deg) | Yaw-rate p95 (deg/s) |
|---|---:|---:|---:|---:|
| recorded `dt` oracle | 0.276 | 0.812 | 3.670 | 41.033 |
| three × `1/30 s` | 0.539 | 2.320 | 3.916 | 41.587 |
| six × `1/60 s` | 1.184 | 3.362 | 3.288 | 40.460 |

| Fixed policy | Nominal median/p95 (ms) | Residual median/p95 (ms) |
|---|---:|---:|
| three × `1/30 s` | 72.504 / 93.897 | 156.659 / 230.265 |
| six × `1/60 s` | 132.089 / 143.565 | 296.599 / 371.585 |

Training `dt` median/p95/max is `28.000/32.050/95.000 ms`; validation is
`27.000/40.900/96.000 ms`. Unreal's accepted callback cadence is variable and is not a fixed 60 Hz
stream.

## Decision

Use three equal `1/30 s` substeps for scalar and vectorized nominal/residual planning. This policy
better reproduces authoritative translation and is the only tested policy whose nominal offline
complete-CEM p95 remains below 100 ms. The residual planner still fails the deadline and requires
R5 optimization before live use.

Residual training and prediction evaluation continue to use recorded `dt`, because those tasks
operate on observed transitions. The residual feature vector includes `dt`, and `1/30 s` is inside
the accepted training range. Planning uses fixed substeps because future Unreal callback durations
are unknowable.

## Reproduce

```bash
uv run python scripts/audit_timestep_policy.py \
  --collection-plan configs/residual_collection_plan.yaml \
  --raw-data-root "/path/to/GameAnimationSample/Saved/MotionWorld/Episodes" \
  --output-dir artifacts/recovery/timestep_policy_001 \
  --git-commit 96d8879673300d4d53db9d8dfb0df78bac090d1e
```

Complete latency uses `scripts/benchmark_planner_runtime.py` with the active
`configs/cem_planner.yaml` for fixed-30 and `cem_planner_fixed_60.yaml` for fixed-60, one Torch
thread, three warmups, and 30 measured calls.
