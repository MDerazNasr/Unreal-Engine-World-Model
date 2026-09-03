#!/usr/bin/env python3
"""Benchmark complete nominal and residual MPC calls on one frozen validation query."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from motionworld.data.residual_manifest import audit_residual_dataset
from motionworld.dynamics.nominal_episode import current_snapshot_nominal_inputs
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState
from motionworld.models.residual_training import load_residual_checkpoint
from motionworld.planning.cem import sample_standard_normal_schedule
from motionworld.planning.config import load_cem_planner_config, load_offline_planner_config
from motionworld.planning.mpc import PlannerProblem, PlannerQuery, plan_model
from motionworld.planning.planner_rollout import PlannerSnapshot


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return result


def _statistics(milliseconds: list[float], deadline_ms: float) -> dict[str, Any]:
    values = np.asarray(milliseconds, dtype=np.float64)
    return {
        "sample_count": len(milliseconds),
        "median_ms": float(np.median(values)),
        "p95_ms": float(np.percentile(values, 95)),
        "minimum_ms": float(np.min(values)),
        "maximum_ms": float(np.max(values)),
        "deadline_ms": deadline_ms,
        "median_meets_deadline": bool(np.median(values) <= deadline_ms),
        "p95_meets_deadline": bool(np.percentile(values, 95) <= deadline_ms),
        "latencies_ms": milliseconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cem-config", type=Path, required=True)
    parser.add_argument("--problem-config", type=Path, required=True)
    parser.add_argument("--collection-plan", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--training-comparison", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--raw-data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--warmups", type=_positive_int, default=3)
    parser.add_argument("--repetitions", type=_positive_int, default=30)
    parser.add_argument("--torch-threads", type=_positive_int, default=1)
    parser.add_argument("--deadline-ms", type=float, default=100.0)
    args = parser.parse_args()
    if not np.isfinite(args.deadline_ms) or args.deadline_ms <= 0.0:
        raise ValueError("deadline-ms must be positive and finite")

    torch.set_num_threads(args.torch_threads)
    cem, rollout, seed, horizon_s = load_cem_planner_config(args.cem_config)
    raw_problem, geometry, weights = load_offline_planner_config(args.problem_config)
    checkpoint = load_residual_checkpoint(str(args.checkpoint))
    comparison = json.loads(args.training_comparison.read_text(encoding="utf-8"))
    checkpoint_hash = _sha256(args.checkpoint)
    manifest_hash = _sha256(args.dataset_manifest)
    if checkpoint_hash != comparison["checkpoint_sha256"]["no_history"]:
        raise ValueError("checkpoint hash differs from frozen training comparison")
    if checkpoint.dataset_manifest_sha256 != manifest_hash:
        raise ValueError("checkpoint dataset manifest hash differs")

    dataset = audit_residual_dataset(args.collection_plan, args.raw_data_root)
    episode_id = raw_problem["source_validation_episode_id"]
    source = next(
        (
            item
            for item in dataset.episodes_for_split("validation")
            if item.episode_id == episode_id
        ),
        None,
    )
    if source is None:
        raise ValueError("source episode is not accepted validation data")
    transition_index = raw_problem["source_transition_index"]
    initial = current_snapshot_nominal_inputs(source.episode.transitions[transition_index])
    preparation = source.episode.transitions[transition_index]["nominal_context"]["previous"][
        "input_preparation"
    ]
    if not preparation["has_max_move_speed"]:
        raise ValueError("source snapshot has no effective maximum speed")
    start = np.asarray(raw_problem["counterfactual_start_world_cm"], dtype=np.float64)
    observable = SmoothWalkingObservableState(
        position_world_cm=np.asarray(
            [start[0], start[1], initial.observable.position_world_cm[2]], dtype=np.float64
        ),
        velocity_world_cm_s=initial.observable.velocity_world_cm_s.copy(),
        facing_yaw_rad=initial.observable.facing_yaw_rad,
        angular_velocity_yaw_deg_s=initial.observable.angular_velocity_yaw_deg_s,
        simulation_time_s=0.0,
    )
    snapshot = PlannerSnapshot(
        observable=observable,
        internal=initial.internal,
        parameters=initial.parameters,
        effective_max_speed_cm_s=float(preparation["effective_max_speed_cm_per_s"]),
    )
    problem = PlannerProblem(
        cem=cem,
        rollout=rollout,
        geometry=geometry,
        weights=weights,
        goal_world_cm=raw_problem["goal_world_cm"],
        rollout_backend="vectorized",
    )
    mean = np.asarray(raw_problem["initial_mean_action_local_cm_s"], dtype=np.float64)
    query = PlannerQuery(
        snapshot=snapshot,
        scenario_time_s=raw_problem["initial_scenario_time_s"],
        previous_action_local_cm_s=raw_problem["previous_action_local_cm_s"],
        previous_previous_action_local_cm_s=raw_problem["previous_previous_action_local_cm_s"],
        initial_mean_knots_local_cm_s=np.tile(mean, (cem.num_knots, 1)),
    )
    noise = sample_standard_normal_schedule(cem, seed=seed)

    def run_nominal() -> None:
        plan_model(
            problem,
            query,
            standard_normal_noise=noise,
            model_name="nominal",
        )

    def run_residual() -> None:
        plan_model(
            problem,
            query,
            standard_normal_noise=noise,
            model_name="residual",
            residual_model=checkpoint.model,
            residual_normalization=checkpoint.normalization,
        )

    for _ in range(args.warmups):
        run_nominal()
        run_residual()

    measurements: dict[str, list[float]] = {"nominal": [], "residual": []}
    functions = {"nominal": run_nominal, "residual": run_residual}
    for repetition in range(args.repetitions):
        order = ("nominal", "residual") if repetition % 2 == 0 else ("residual", "nominal")
        for model_name in order:
            started_ns = time.perf_counter_ns()
            functions[model_name]()
            elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
            measurements[model_name].append(elapsed_ms)

    result = {
        "schema_name": "motionworld_planner_runtime_benchmark",
        "schema_version": 1,
        "claim_boundary": "offline Python CPU MPC latency; excludes Unreal transport and control",
        "git_commit": args.git_commit,
        "source_validation_episode_id": episode_id,
        "source_transition_index": transition_index,
        "source_raw_sha256": source.raw_sha256,
        "test_files_opened": 0,
        "checkpoint_sha256": checkpoint_hash,
        "dataset_manifest_sha256": manifest_hash,
        "cem_config_sha256": _sha256(args.cem_config),
        "problem_config_sha256": _sha256(args.problem_config),
        "seed": seed,
        "horizon_s": horizon_s,
        "rollout_backend": problem.rollout_backend,
        "warmup_calls_per_controller": args.warmups,
        "measured_calls_per_controller": args.repetitions,
        "alternating_measurement_order": True,
        "torch_threads": torch.get_num_threads(),
        "hardware_software": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "torch": torch.__version__,
        },
        "nominal": _statistics(measurements["nominal"], args.deadline_ms),
        "residual": _statistics(measurements["residual"], args.deadline_ms),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "planner_runtime=complete "
        f"nominal_median_ms={result['nominal']['median_ms']:.3f} "
        f"nominal_p95_ms={result['nominal']['p95_ms']:.3f} "
        f"residual_median_ms={result['residual']['median_ms']:.3f} "
        f"residual_p95_ms={result['residual']['p95_ms']:.3f} "
        "test_opened=0"
    )


if __name__ == "__main__":
    main()
