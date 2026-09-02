# OFFPLAN-001 offline paired planner

This is model-based counterfactual integration evidence, not Unreal control evidence.

- Source context: accepted validation episode `5202`, transition
  `0`,
  relocated to `[-100.0, 0.0]` cm because absolute position is excluded from residual features.
- Test files opened: `0`.
- Common first-iteration candidate batch: `True`.
- Nominal first action: `[40.191712579378816, -139.87240341458457]` cm/s.
- Residual first action: `[23.419774979886355, -102.09038201786595]` cm/s.
- Nominal predicted collision: `0`.
- Residual predicted collision: `0`.
- Wall time is printed to the terminal only. It is not part of this deterministic artifact and is
  not a `RUNTIME-001` latency measurement.

The cost matrix cross-evaluates both selected action sequences under both models. It is a
model-error diagnostic, not realized-world return. Final controller claims require same-seed Unreal
execution.
