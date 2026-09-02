# Episode 4301 perturbation analysis

- Scenario: one evaluation-only additive world-velocity request `(0,250,0)` cm/s after 1.5 s,
  followed by 2.0 s of observation.
- Episode ID: `4301`
- Episode SHA-256: `e8bcecc12724f7e8a5ccf9c90cbc7249ae3703091dc713191f175f74cc60df0f`
- Schema: episode 5, transition protocol 4
- Evaluator commit: `f0d7348`
- Result: bounded negative post-observation residual result; the only large mismatch is the hidden
  event transition and recursive windows that cross it.

The raw Game Animation Sample episode is local licensed data and is not committed. Reproduce from
the local file with:

```bash
MPLCONFIGDIR=/tmp/motionworld-mpl .venv/bin/python \
  scripts/evaluate_nominal_episode.py \
  '<local-episode-4301.jsonl>' \
  --output-dir artifacts/nominal/episode_4301_perturbation

MPLCONFIGDIR=/tmp/motionworld-mpl .venv/bin/python \
  scripts/evaluate_recursive_nominal_episode.py \
  '<local-episode-4301.jsonl>' \
  --output-dir artifacts/nominal/episode_4301_perturbation \
  --horizons 0.5 1.0 1.5
```

`summary.json` contains one-step pre/event/post strata and the observed requested-versus-realized
velocity change. `recursive_summary.json` separates pre-event, event-crossing, and post-event
windows. The causal comparison figure is `recursive_perturbation_error.png`.
