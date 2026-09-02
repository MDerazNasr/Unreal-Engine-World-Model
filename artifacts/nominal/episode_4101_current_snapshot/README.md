# Episode 4101 causal nominal analysis

- Episode SHA-256: `4fdd65f02cdf83f9c4858f3b2ea423305f24b417c6171ed252b8bdfe50e09afb`
- Policy: current finalized context for one step; rollout-start parameters held recursively.
- Evaluator commits: `02ae8bb`, `fc32430`, `93fb741`.
- Limitation: this episode retains the known exact-opposite-facing failure and is secondary evidence.

Reproduce with `scripts/evaluate_nominal_episode.py --parameter-source current-snapshot` and
`scripts/evaluate_recursive_nominal_episode.py --parameter-policy hold-current --horizons 0.5 1.0 1.5`.
The raw licensed Unreal episode is local and is not committed.
