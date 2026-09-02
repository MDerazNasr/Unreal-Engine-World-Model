# Recursive residual evaluation 001

Every rollout starts from one real current snapshot, then advances predicted state and nominal hidden state without intermediate teacher forcing. Recorded future actions and timesteps define the query; initial parameters are held for the imagined future.

## All common validation windows: p95

| Horizon | Model | Position (cm) | Velocity (cm/s) | Yaw (deg) | Yaw rate (deg/s) |
|---:|---|---:|---:|---:|---:|
| 0.5 | nominal | 16.7193 | 64.3936 | 46.1563 | 292.599 |
| 0.5 | no history | 14.3949 | 57.4833 | 20.1507 | 102.55 |
| 0.5 | four history | 15.9289 | 63.1534 | 41.7916 | 255.78 |
| 1.0 | nominal | 30.2221 | 61.1513 | 97.2873 | 441.489 |
| 1.0 | no history | 27.9338 | 55.2062 | 30.6909 | 75.0996 |
| 1.0 | four history | 29.4045 | 57.8196 | 40.3845 | 125.581 |
| 1.5 | nominal | 31.2294 | 66.6286 | 52.3024 | 361.373 |
| 1.5 | no history | 28.9644 | 58.5575 | 11.5832 | 66.6702 |
| 1.5 | four history | 30.3905 | 63.1155 | 25.7865 | 106.986 |

Dashed lines in the plot show windows that cross a parameter-regime change. Stable windows and every raw endpoint remain available in JSON/CSV. Test episodes were not opened.
