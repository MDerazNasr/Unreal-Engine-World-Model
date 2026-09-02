# Episode 4201 causal nominal analysis

- Episode SHA-256: `73717460108db8c3b9092e37cb7ef48c4ba5f8e4fdbbeb5252b210977270bfb5`
- Policy: current finalized context for one step; rollout-start parameters held recursively.
- Evaluator commits: `02ae8bb`, `fc32430`, `93fb741`.
- Role: primary corrected-facing evidence for `NOM-CAUSAL-001`.

Reproduce with `scripts/evaluate_nominal_episode.py --parameter-source current-snapshot` and
`scripts/evaluate_recursive_nominal_episode.py --parameter-policy hold-current --horizons 0.5 1.0 1.5`.
The raw licensed Unreal episode is local and is not committed.
