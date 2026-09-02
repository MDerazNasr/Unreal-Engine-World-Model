# Residual training experiment 001

Both MLPs use the frozen architecture, train-only normalization, identical fixed optimizer budgets, and no validation early stopping. Test episodes were not opened.

## Common held-out validation rows: all-row mean

| Model | Position (cm) | Velocity (cm/s) | Yaw (deg) | Yaw rate (deg/s) |
|---|---:|---:|---:|---:|
| nominal | 0.00120951 | 0.0423777 | 0.137137 | 5.27441 |
| no history | 0.000225756 | 0.00824939 | 0.0451377 | 1.3457 |
| four history | 0.000453994 | 0.0154654 | 0.0825581 | 3.07323 |

## Parameter-change rows: p95

| Model | Position (cm) | Velocity (cm/s) | Yaw (deg) | Yaw rate (deg/s) |
|---|---:|---:|---:|---:|
| nominal | 0.0523152 | 1.9376 | 3.60379 | 188.18 |
| no history | 0.00238128 | 0.107696 | 0.917758 | 18.9772 |
| four history | 0.00442551 | 0.233237 | 1.83564 | 83.2742 |

All-row position/velocity p95 is misleading because fewer than 5% of rows contain material nominal translation error. The report therefore shows all-row means and the predeclared parameter-change stratum separately. Stable-row errors remain in `comparison.json`.

These are one-step results. Recursive 0.5/1.0/1.5-second evaluation remains a separate gate and must not be inferred from this table.
