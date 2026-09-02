#!/usr/bin/env python3
"""Generate deterministic, synthetic-only evidence for the CEM optimizer."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import yaml

from motionworld.planning.cem import CEMConfig, optimize_cem

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_config(path: Path) -> tuple[CEMConfig, int, float, float, np.ndarray]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("CEM config must be a mapping")
    required = {
        "schema_name",
        "schema_version",
        "seed",
        "decision_interval_s",
        "horizon_s",
        "optimizer",
        "toy_oracle",
    }
    if set(raw) != required:
        raise ValueError(f"CEM config keys must be exactly {sorted(required)}")
    if raw["schema_name"] != "motionworld_cem_planner_config" or raw["schema_version"] != 1:
        raise ValueError("unsupported CEM config schema")
    optimizer = raw["optimizer"]
    if not isinstance(optimizer, dict) or set(optimizer) != set(CEMConfig.__dataclass_fields__):
        raise ValueError("optimizer keys do not match CEMConfig")
    config = CEMConfig(**optimizer)
    seed = raw["seed"]
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    decision_interval_s = float(raw["decision_interval_s"])
    horizon_s = float(raw["horizon_s"])
    if (
        not math.isfinite(decision_interval_s)
        or not math.isfinite(horizon_s)
        or decision_interval_s <= 0.0
        or horizon_s <= 0.0
    ):
        raise ValueError("planner timing must be positive and finite")
    expected_model_steps = round(horizon_s / decision_interval_s)
    if config.num_model_steps != expected_model_steps:
        raise ValueError("num_model_steps must equal horizon / decision interval")
    if config.num_knots > config.num_model_steps:
        raise ValueError("num_knots cannot exceed num_model_steps")
    toy = raw["toy_oracle"]
    if not isinstance(toy, dict) or set(toy) != {"target_action_cm_s"}:
        raise ValueError("toy_oracle must contain only target_action_cm_s")
    target = np.asarray(toy["target_action_cm_s"], dtype=np.float64)
    if target.shape != (2,) or not np.all(np.isfinite(target)):
        raise ValueError("toy target must contain two finite values")
    if np.linalg.norm(target) > config.max_action_speed_cm_s:
        raise ValueError("toy target must lie inside the legal speed ball")
    return config, seed, decision_interval_s, horizon_s, target


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plot(result: Any, target: np.ndarray, output: Path, maximum_speed: float) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)
    circle_angles = np.linspace(0.0, 2.0 * np.pi, 361)
    for diagnostic, axis in zip(result.iterations, axes.flat[:3], strict=True):
        candidates = diagnostic.candidate_first_actions_cm_s
        axis.scatter(candidates[:, 0], candidates[:, 1], s=9, alpha=0.23, label="candidates")
        axis.plot(
            maximum_speed * np.cos(circle_angles),
            maximum_speed * np.sin(circle_angles),
            color="black",
            linewidth=1.0,
            label="legal speed boundary",
        )
        axis.scatter(*target, marker="*", s=180, color="green", label="known optimum")
        axis.scatter(
            *diagnostic.best_knots_cm_s[0],
            marker="X",
            s=90,
            color="tab:red",
            label="iteration best",
        )
        axis.set_title(f"Iteration {diagnostic.iteration + 1}: first action candidates")
        axis.set_xlabel("local forward velocity (cm/s)")
        axis.set_ylabel("local right velocity (cm/s)")
        axis.set_aspect("equal")
        axis.grid(alpha=0.25)
    axes.flat[0].legend(fontsize=8, loc="lower left")

    costs = [diagnostic.best_cost for diagnostic in result.iterations]
    mean_errors = [
        float(np.linalg.norm(diagnostic.mean_knots_cm_s[0] - target))
        for diagnostic in result.iterations
    ]
    axis = axes.flat[3]
    x = np.arange(1, len(costs) + 1)
    axis.semilogy(x, costs, marker="o", label="best full-plan squared cost")
    axis.semilogy(x, mean_errors, marker="s", label="first-knot mean distance")
    axis.set_xticks(x)
    axis.set_xlabel("CEM iteration")
    axis.set_ylabel("cost / distance (log scale)")
    axis.set_title("Distribution concentrates near the toy optimum")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    figure.suptitle("CEM-001 synthetic quadratic oracle — not Unreal control evidence", fontsize=15)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()

    planner_config, seed, decision_interval_s, horizon_s, target = _read_config(args.config)
    # The oracle isolates one two-dimensional CEM decision. The deployable planner retains the
    # same sample/elite/iteration/bound settings but optimizes five knots over fifteen steps.
    config = replace(planner_config, num_knots=1, num_model_steps=1)

    def quadratic_cost(actions: np.ndarray) -> np.ndarray:
        return np.mean(np.sum(np.square(actions - target), axis=-1), axis=1)

    result = optimize_cem(quadratic_cost, config=config, seed=seed)
    repeated = optimize_cem(quadratic_cost, config=config, seed=seed)
    if (
        result.best_cost != repeated.best_cost
        or not np.array_equal(result.best_knots_cm_s, repeated.best_knots_cm_s)
        or not np.array_equal(result.first_action_cm_s, repeated.first_action_cm_s)
    ):
        raise RuntimeError("fixed-seed CEM did not reproduce exactly")
    if result.used_safe_fallback:
        raise RuntimeError(f"unexpected safe fallback: {result.fallback_reason}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_name": "motionworld_cem_toy_result",
        "schema_version": 1,
        "claim_boundary": "synthetic quadratic oracle; not Unreal control evidence",
        "git_commit": args.git_commit,
        "seed": seed,
        "decision_interval_s": decision_interval_s,
        "horizon_s": horizon_s,
        "tensor_shapes": {
            "noise": list(config.noise_shape),
            "knot_candidates_per_iteration": [
                config.num_candidates,
                config.num_knots,
                config.action_dim,
            ],
            "expanded_actions_per_iteration": [
                config.num_candidates,
                config.num_model_steps,
                config.action_dim,
            ],
        },
        "toy_optimizer_config": asdict(config),
        "planned_runtime_config": asdict(planner_config),
        "target_action_cm_s": target.tolist(),
        "best_first_action_cm_s": result.first_action_cm_s.tolist(),
        "best_first_action_error_cm_s": float(np.linalg.norm(result.first_action_cm_s - target)),
        "best_cost": result.best_cost,
        "iteration_best_costs": [item.best_cost for item in result.iterations],
        "iteration_first_knot_mean_error_cm_s": [
            float(np.linalg.norm(item.mean_knots_cm_s[0] - target)) for item in result.iterations
        ],
        "maximum_sampled_speed_cm_s": max(
            float(np.max(np.linalg.norm(item.candidate_first_actions_cm_s, axis=-1)))
            for item in result.iterations
        ),
        "fixed_seed_exact_repeat": True,
        "used_safe_fallback": result.used_safe_fallback,
    }
    _write_json(args.output_dir / "summary.json", summary)
    _plot(
        result,
        target,
        args.output_dir / "convergence.png",
        config.max_action_speed_cm_s,
    )
    readme = f"""# CEM-001 deterministic toy oracle

This is synthetic optimizer evidence, not an Unreal control result.

- Known constant-action optimum: `{target.tolist()}` cm/s.
- Returned first action: `{result.first_action_cm_s.tolist()}` cm/s.
- First-action error: `{summary['best_first_action_error_cm_s']:.6f}` cm/s.
- Best cost: `{result.best_cost:.9f}`.
- Fixed-seed repeat: exact.
- Maximum sampled speed: `{summary['maximum_sampled_speed_cm_s']:.6f}` cm/s
  (limit `{config.max_action_speed_cm_s:.6f}` cm/s).

Reproduce from the repository root:

```bash
MPLCONFIGDIR=/tmp/motionworld-mpl .venv/bin/python scripts/run_cem_toy.py \\
  --config configs/cem_planner.yaml \\
  --output-dir artifacts/planning/cem_001 \\
  --git-commit {args.git_commit}
```
"""
    (args.output_dir / "README.md").write_text(readme, encoding="utf-8")
    artifact_paths = sorted(
        path
        for path in args.output_dir.iterdir()
        if path.is_file() and path.name != "artifact_hashes.json"
    )
    _write_json(
        args.output_dir / "artifact_hashes.json",
        {path.name: _sha256(path) for path in artifact_paths},
    )
    print(
        "cem=complete "
        f"best_error_cm_s={summary['best_first_action_error_cm_s']:.6f} "
        f"best_cost={result.best_cost:.9f} exact_repeat=true"
    )


if __name__ == "__main__":
    main()
