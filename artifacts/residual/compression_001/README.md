# RESIDUAL-COMPRESS-001 validation-only width sweep

Selected model: `none`.

| Model | Parameters | Recursive pass | Planner pass | Runtime p95 (ms) | Runtime pass | Eligible |
|---|---:|:---:|:---:|---:|:---:|:---:|
| width_192_192_96 | 61734 | False | False | 137.515 | False | False |
| width_128_128_64 | 28870 | True | False | 184.242 | False | False |
| width_96_96_48 | 17046 | False | False | 135.987 | False | False |
| width_64_64_32 | 8294 | False | False | 117.234 | False | False |

All thresholds and candidates were committed before training. Planner regret is cross-evaluated with the frozen reference model. Final test files opened: `0`.
