# CEM-001 deterministic toy oracle

This is synthetic optimizer evidence, not an Unreal control result.

- Known constant-action optimum: `[90.0, -55.0]` cm/s.
- Returned first action: `[88.56554100463525, -55.90639616061771]` cm/s.
- First-action error: `1.696828` cm/s.
- Best cost: `2.879226609`.
- Fixed-seed repeat: exact.
- Maximum sampled speed: `165.000000` cm/s
  (limit `165.000000` cm/s).

Reproduce from the repository root:

```bash
MPLCONFIGDIR=/tmp/motionworld-mpl .venv/bin/python scripts/run_cem_toy.py \
  --config configs/cem_planner.yaml \
  --output-dir artifacts/planning/cem_001 \
  --git-commit 08d727e
```
