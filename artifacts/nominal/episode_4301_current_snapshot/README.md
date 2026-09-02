# Episode 4301 causal nominal analysis

- Episode SHA-256: `e8bcecc12724f7e8a5ccf9c90cbc7249ae3703091dc713191f175f74cc60df0f`
- Policy: current finalized context for one step; rollout-start parameters held recursively.
- Evaluator commits: `02ae8bb`, `fc32430`, `93fb741`.
- Role: confirms the hidden kick remains evaluation-only under the causal parameter policy.

Reproduce with `scripts/evaluate_nominal_episode.py --parameter-source current-snapshot` and
`scripts/evaluate_recursive_nominal_episode.py --parameter-policy hold-current --horizons 0.5 1.0 1.5`.
The raw licensed Unreal episode is local and is not committed.
