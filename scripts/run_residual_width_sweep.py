#!/usr/bin/env python3
"""Train and gate smaller no-history residual MLPs on validation data only."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import torch
import yaml

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from motionworld.data.residual_manifest import audit_residual_dataset
from motionworld.models.compression_sweep import (
    ResidualWidthSweep,
    load_residual_width_sweep,
    select_compressed_model,
)
from motionworld.models.residual_dataset import build_residual_dataset
from motionworld.models.residual_normalization import fit_residual_normalization
from motionworld.models.residual_rollout import evaluate_recursive_residual_rollouts
from motionworld.models.residual_training import (
    LoadedResidualCheckpoint,
    ResidualOptimizerConfig,
    load_residual_checkpoint,
    predict_physical_residuals,
    summarize_physical_residual_error,
    train_residual_model,
)
from motionworld.planning.cem import sample_standard_normal_schedule
from motionworld.planning.config import load_cem_planner_config, load_offline_planner_config
from motionworld.planning.cost import evaluate_planning_cost
from motionworld.planning.mpc import PlannerProblem, PlannerQuery, plan_model
from motionworld.planning.offline_context import build_counterfactual_query
from motionworld.planning.vectorized_rollout import rollout_action_candidates_vectorized

RECURSIVE_METRICS = (
    "planar_position_error_cm",
    "planar_velocity_error_cm_s",
    "yaw_error_deg",
    "angular_velocity_yaw_error_deg_s",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _matrix(examples: tuple[Any, ...], field: str) -> np.ndarray:
    return np.stack([getattr(example, field) for example in examples])


def _optimizer_config(training: dict[str, Any]) -> ResidualOptimizerConfig:
    optimizer = training["optimizer"]
    loss = training["loss"]
    reproducibility = training["reproducibility"]
    return ResidualOptimizerConfig(
        optimizer_steps=int(optimizer["optimizer_steps"]),
        batch_size=int(optimizer["batch_size"]),
        learning_rate=float(optimizer["learning_rate"]),
        weight_decay=float(optimizer["weight_decay"]),
        huber_beta=float(loss["huber_beta"]),
        residual_magnitude_weight=float(loss["residual_magnitude_weight"]),
        trace_interval_steps=int(reproducibility["trace_interval_steps"]),
    )


def _recursive_summary(rows: tuple[Any, ...], horizons: tuple[float, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for horizon in horizons:
        selected = [row for row in rows if row.requested_horizon_s == horizon]
        if not selected:
            raise ValueError(f"no recursive rows for horizon {horizon}")
        result[str(horizon)] = {
            "window_count": len(selected),
            "p95": {
                metric: float(np.percentile([getattr(row, metric) for row in selected], 95))
                for metric in RECURSIVE_METRICS
            },
        }
    return result


def _recursive_gate(
    candidate: dict[str, Any],
    reference: dict[str, Any],
    *,
    sweep: ResidualWidthSweep,
) -> tuple[dict[str, Any], bool]:
    comparisons = []
    for horizon in sweep.recursive_horizons_s:
        for metric in RECURSIVE_METRICS:
            reference_value = reference[str(horizon)]["p95"][metric]
            candidate_value = candidate[str(horizon)]["p95"][metric]
            relative_degradation = (candidate_value - reference_value) / max(
                abs(reference_value), 1.0e-12
            )
            comparisons.append(
                {
                    "horizon_s": horizon,
                    "metric": metric,
                    "reference_p95": reference_value,
                    "candidate_p95": candidate_value,
                    "relative_degradation": relative_degradation,
                    "passed": relative_degradation
                    <= sweep.maximum_recursive_relative_degradation,
                }
            )
    maximum = max(row["relative_degradation"] for row in comparisons)
    return {
        "maximum_relative_degradation": maximum,
        "threshold": sweep.maximum_recursive_relative_degradation,
        "comparisons": comparisons,
    }, all(row["passed"] for row in comparisons)


def _evaluate_actions_with_reference(
    actions: np.ndarray,
    *,
    problem: PlannerProblem,
    query: PlannerQuery,
    reference: LoadedResidualCheckpoint,
) -> Any:
    action_batch = actions[np.newaxis, :, :]
    rollout = rollout_action_candidates_vectorized(
        query.snapshot,
        action_batch,
        config=problem.rollout,
        residual_model=reference.model,
        residual_normalization=reference.normalization,
    )
    times = query.scenario_time_s + problem.rollout.plan_step_s * np.arange(
        1, problem.cem.num_plan_steps + 1, dtype=np.float64
    )
    return evaluate_planning_cost(
        rollout.positions_world_cm,
        action_batch,
        initial_position_world_cm=np.asarray(
            query.snapshot.observable.position_world_cm[:2], dtype=np.float64
        ),
        previous_action_cm_s=np.asarray(query.previous_action_local_cm_s),
        previous_previous_action_cm_s=np.asarray(query.previous_previous_action_local_cm_s),
        goal_world_cm=np.asarray(problem.goal_world_cm),
        initial_scenario_time_s=query.scenario_time_s,
        scenario_times_s=times,
        geometry=problem.geometry,
        weights=problem.weights,
    )


def _planner_gate(
    checkpoint: LoadedResidualCheckpoint,
    *,
    reference: LoadedResidualCheckpoint,
    reference_plans: dict[tuple[int, int], Any],
    queries: dict[tuple[int, int], PlannerQuery],
    problem: PlannerProblem,
    noise: np.ndarray,
    sweep: ResidualWidthSweep,
) -> tuple[dict[str, Any], bool]:
    observations = []
    for key, query in queries.items():
        candidate_plan = plan_model(
            problem,
            query,
            standard_normal_noise=noise,
            model_name="residual",
            residual_model=checkpoint.model,
            residual_normalization=checkpoint.normalization,
        )
        reference_cost = _evaluate_actions_with_reference(
            reference_plans[key].cem.best_actions_cm_s,
            problem=problem,
            query=query,
            reference=reference,
        )
        candidate_cost = _evaluate_actions_with_reference(
            candidate_plan.cem.best_actions_cm_s,
            problem=problem,
            query=query,
            reference=reference,
        )
        reference_total = float(reference_cost.total[0])
        candidate_total = float(candidate_cost.total[0])
        signed_regret = (candidate_total - reference_total) / max(abs(reference_total), 1.0)
        reference_collision = bool(reference_cost.collision_indicator[0])
        candidate_collision = bool(candidate_cost.collision_indicator[0])
        observations.append(
            {
                "episode_id": key[0],
                "transition_index": key[1],
                "reference_model_reference_plan_cost": reference_total,
                "reference_model_candidate_plan_cost": candidate_total,
                "signed_relative_regret": signed_regret,
                "positive_relative_regret": max(0.0, signed_regret),
                "reference_collision": reference_collision,
                "candidate_collision": candidate_collision,
                "new_predicted_collision": candidate_collision and not reference_collision,
                "first_action_distance_cm_s": float(
                    np.linalg.norm(
                        candidate_plan.cem.first_action_cm_s
                        - reference_plans[key].cem.first_action_cm_s
                    )
                ),
            }
        )
    regrets = np.asarray([row["positive_relative_regret"] for row in observations])
    p95 = float(np.percentile(regrets, 95))
    new_collisions = sum(int(row["new_predicted_collision"]) for row in observations)
    passed = (
        p95 <= sweep.maximum_planner_p95_positive_relative_regret
        and new_collisions <= sweep.maximum_new_predicted_collisions
    )
    return {
        "p95_positive_relative_regret": p95,
        "mean_positive_relative_regret": float(np.mean(regrets)),
        "maximum_positive_relative_regret": float(np.max(regrets)),
        "new_predicted_collision_count": new_collisions,
        "maximum_p95_positive_relative_regret": (
            sweep.maximum_planner_p95_positive_relative_regret
        ),
        "maximum_new_predicted_collisions": sweep.maximum_new_predicted_collisions,
        "cross_evaluation_model": "frozen_reference_residual_model",
        "observations": observations,
    }, passed


def _runtime_gate(
    checkpoint: LoadedResidualCheckpoint,
    *,
    query: PlannerQuery,
    problem: PlannerProblem,
    noise: np.ndarray,
    sweep: ResidualWidthSweep,
) -> tuple[dict[str, Any], bool]:
    def run() -> None:
        plan_model(
            problem,
            query,
            standard_normal_noise=noise,
            model_name="residual",
            residual_model=checkpoint.model,
            residual_normalization=checkpoint.normalization,
        )

    for _ in range(sweep.warmups):
        run()
    latencies = []
    for _ in range(sweep.repetitions):
        started = time.perf_counter_ns()
        run()
        latencies.append((time.perf_counter_ns() - started) / 1_000_000.0)
    values = np.asarray(latencies)
    p95 = float(np.percentile(values, 95))
    return {
        "sample_count": len(latencies),
        "median_ms": float(np.median(values)),
        "p95_ms": p95,
        "minimum_ms": float(np.min(values)),
        "maximum_ms": float(np.max(values)),
        "deadline_ms": sweep.deadline_ms,
        "missed_deadline_count": int(np.count_nonzero(values > sweep.deadline_ms)),
        "latencies_ms": latencies,
    }, p95 <= sweep.deadline_ms


def _plot(path: Path, records: list[dict[str, Any]], *, deadline_ms: float) -> None:
    names = [record["name"].replace("width_", "") for record in records]
    parameters = [record["parameter_count"] for record in records]
    latency = [record["runtime"]["p95_ms"] for record in records]
    degradation = [
        100.0 * record["recursive"]["maximum_relative_degradation"] for record in records
    ]
    colors = ["#2a9d8f" if record["eligible"] else "#d1495b" for record in records]
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.0), constrained_layout=True)
    axes[0].bar(names, parameters, color=colors)
    axes[0].set_title("Parameter count")
    axes[1].bar(names, latency, color=colors)
    axes[1].axhline(deadline_ms, color="#222222", linestyle="--", label="deadline")
    axes[1].set_title("Full CEM p95 latency (ms)")
    axes[1].legend()
    axes[2].bar(names, degradation, color=colors)
    axes[2].axhline(15.0, color="#222222", linestyle="--", label="quality limit")
    axes[2].set_title("Worst recursive p95 change (%)")
    axes[2].legend()
    for axis in axes:
        axis.tick_params(axis="x", rotation=35)
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("Residual-width sweep: green passes all gates")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-config", type=Path, required=True)
    parser.add_argument("--training-config", type=Path, required=True)
    parser.add_argument("--training-comparison", type=Path, required=True)
    parser.add_argument("--reference-checkpoint", type=Path, required=True)
    parser.add_argument("--collection-plan", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--cem-config", type=Path, required=True)
    parser.add_argument("--problem-config", type=Path, required=True)
    parser.add_argument("--raw-data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()

    sweep = load_residual_width_sweep(args.sweep_config)
    for path, expected in (
        (args.training_config, sweep.source_training_config_sha256),
        (args.training_comparison, sweep.source_training_comparison_sha256),
        (args.reference_checkpoint, sweep.reference_checkpoint_sha256),
    ):
        if _sha256(path) != expected:
            raise ValueError(f"frozen provenance hash differs: {path}")
    training = yaml.safe_load(args.training_config.read_text(encoding="utf-8"))
    reference = load_residual_checkpoint(str(args.reference_checkpoint))
    if reference.history_length != sweep.history_length:
        raise ValueError("reference checkpoint history differs from sweep")
    if reference.dataset_manifest_sha256 != _sha256(args.dataset_manifest):
        raise ValueError("reference checkpoint dataset manifest differs")

    torch.set_num_threads(sweep.torch_threads)
    dataset = audit_residual_dataset(args.collection_plan, args.raw_data_root)
    train_ids = tuple(int(value) for value in training["train_episode_ids"])
    validation_ids = tuple(int(value) for value in training["validation_episode_ids"])
    if tuple(item.episode_id for item in dataset.episodes_for_split("train")) != train_ids:
        raise ValueError("training episode IDs differ from frozen training config")
    actual_validation_ids = tuple(
        item.episode_id for item in dataset.episodes_for_split("validation")
    )
    if actual_validation_ids != validation_ids:
        raise ValueError("validation episode IDs differ from frozen training config")
    train_episodes = tuple(item.episode for item in dataset.episodes_for_split("train"))
    validation_episodes = tuple(item.episode for item in dataset.episodes_for_split("validation"))
    train_examples = build_residual_dataset(train_episodes, history_length=1)
    validation_examples = build_residual_dataset(validation_episodes, history_length=1)
    normalization = fit_residual_normalization(
        train_examples,
        history_length=1,
        expected_train_episode_ids=train_ids,
        scale_floor=float(training["normalization"]["scale_floor"]),
    )
    if normalization.as_dict() != reference.normalization.as_dict():
        raise ValueError("reconstructed train-only normalization differs from reference")
    optimizer = _optimizer_config(training)
    seed = int(training["reproducibility"]["seed"])
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Every candidate is fully trained and checkpointed before any validation is consulted.
    trained: dict[str, Any] = {}
    checkpoint_paths: dict[str, Path] = {}
    for candidate in sweep.candidates:
        trained[candidate.name] = train_residual_model(
            train_examples,
            normalization,
            history_length=1,
            seed=seed,
            config=optimizer,
            hidden_widths=candidate.hidden_widths,
        )
        candidate_dir = args.output_dir / candidate.name
        candidate_dir.mkdir(exist_ok=True)
        checkpoint_path = candidate_dir / "checkpoint.pt"
        torch.save(
            {
                "schema_name": "motionworld_residual_checkpoint",
                "schema_version": 1,
                "state_dict": trained[candidate.name].model.state_dict(),
                "history_length": 1,
                "input_width": trained[candidate.name].model.input_width,
                "hidden_widths": list(candidate.hidden_widths),
                "seed": seed,
                "git_commit": args.git_commit,
                "training_config_sha256": _sha256(args.training_config),
                "dataset_manifest_sha256": _sha256(args.dataset_manifest),
                "normalization": normalization.as_dict(),
            },
            checkpoint_path,
        )
        checkpoint_paths[candidate.name] = checkpoint_path

    cem, rollout_config, planner_seed, _ = load_cem_planner_config(args.cem_config)
    raw_problem, geometry, weights = load_offline_planner_config(args.problem_config)
    problem = PlannerProblem(
        cem=cem,
        rollout=rollout_config,
        geometry=geometry,
        weights=weights,
        goal_world_cm=raw_problem["goal_world_cm"],
        rollout_backend="vectorized",
    )
    validation_by_id = {
        item.episode_id: item for item in dataset.episodes_for_split("validation")
    }
    queries = {
        (item.episode_id, item.transition_index): build_counterfactual_query(
            validation_by_id[item.episode_id],
            item.transition_index,
            problem_config=raw_problem,
            cem=cem,
        )
        for item in sweep.validation_queries
    }
    noise = sample_standard_normal_schedule(cem, seed=planner_seed)
    reference_plans = {
        key: plan_model(
            problem,
            query,
            standard_normal_noise=noise,
            model_name="residual",
            residual_model=reference.model,
            residual_normalization=reference.normalization,
        )
        for key, query in queries.items()
    }
    reference_recursive_rows = tuple(
        row
        for episode in validation_episodes
        for row in evaluate_recursive_residual_rollouts(
            list(episode.transitions),
            model=reference.model,
            normalization=reference.normalization,
            history_length=1,
            horizons_s=sweep.recursive_horizons_s,
        )
    )
    reference_recursive = _recursive_summary(
        reference_recursive_rows, sweep.recursive_horizons_s
    )

    validation_features = _matrix(validation_examples, "features")
    validation_targets = _matrix(validation_examples, "target")
    records = []
    canonical_query = next(iter(queries.values()))
    for candidate in sweep.candidates:
        trained_model = trained[candidate.name]
        checkpoint = load_residual_checkpoint(str(checkpoint_paths[candidate.name]))
        recursive_rows = tuple(
            row
            for episode in validation_episodes
            for row in evaluate_recursive_residual_rollouts(
                list(episode.transitions),
                model=checkpoint.model,
                normalization=checkpoint.normalization,
                history_length=1,
                horizons_s=sweep.recursive_horizons_s,
            )
        )
        recursive_summary = _recursive_summary(recursive_rows, sweep.recursive_horizons_s)
        recursive, recursive_pass = _recursive_gate(
            recursive_summary, reference_recursive, sweep=sweep
        )
        planner, planner_pass = _planner_gate(
            checkpoint,
            reference=reference,
            reference_plans=reference_plans,
            queries=queries,
            problem=problem,
            noise=noise,
            sweep=sweep,
        )
        runtime, runtime_pass = _runtime_gate(
            checkpoint,
            query=canonical_query,
            problem=problem,
            noise=noise,
            sweep=sweep,
        )
        predictions = predict_physical_residuals(
            checkpoint.model, normalization, validation_features
        )
        records.append(
            {
                "name": candidate.name,
                "hidden_widths": list(candidate.hidden_widths),
                "parameter_count": trained_model.model.parameter_count,
                "training_seconds": trained_model.training_seconds,
                "checkpoint_sha256": _sha256(checkpoint_paths[candidate.name]),
                "one_step_validation": summarize_physical_residual_error(
                    validation_targets, predictions
                ),
                "recursive_summary": recursive_summary,
                "recursive": recursive,
                "recursive_pass": recursive_pass,
                "planner": planner,
                "planner_pass": planner_pass,
                "runtime": runtime,
                "runtime_p95_ms": runtime["p95_ms"],
                "runtime_pass": runtime_pass,
                "eligible": recursive_pass and planner_pass and runtime_pass,
            }
        )
    selected_name = select_compressed_model(records)
    result = {
        "schema_name": "motionworld_residual_width_sweep_result",
        "schema_version": 1,
        "claim_boundary": sweep.claim_boundary,
        "configuration_status": sweep.status,
        "git_commit": args.git_commit,
        "test_files_opened": 0,
        "sweep_config_sha256": _sha256(args.sweep_config),
        "training_config_sha256": _sha256(args.training_config),
        "training_comparison_sha256": _sha256(args.training_comparison),
        "dataset_manifest_sha256": _sha256(args.dataset_manifest),
        "reference_checkpoint_sha256": _sha256(args.reference_checkpoint),
        "reference_parameter_count": reference.model.parameter_count,
        "reference_recursive_summary": reference_recursive,
        "cem_config": asdict(cem),
        "selection_rule": sweep.selection_rule,
        "selected_model": selected_name,
        "eligible_model_names": [record["name"] for record in records if record["eligible"]],
        "records": records,
        "claim_limits": [
            "all selection used accepted validation episodes 5201/5202 only",
            "candidate plans were cross-evaluated under the frozen reference residual model",
            "latency is offline Python CPU and excludes Unreal transport and control",
            "test episodes 5301/5302 were not collected or opened",
        ],
    }
    _write_json(args.output_dir / "result.json", result)
    _plot(args.output_dir / "width_sweep.png", records, deadline_ms=sweep.deadline_ms)
    lines = [
        "# RESIDUAL-COMPRESS-001 validation-only width sweep",
        "",
        f"Selected model: `{selected_name or 'none'}`.",
        "",
        "| Model | Parameters | Recursive pass | Planner pass | Runtime p95 (ms) "
        "| Runtime pass | Eligible |",
        "|---|---:|:---:|:---:|---:|:---:|:---:|",
    ]
    for record in records:
        lines.append(
            f"| {record['name']} | {record['parameter_count']} | "
            f"{record['recursive_pass']} | {record['planner_pass']} | "
            f"{record['runtime']['p95_ms']:.3f} | {record['runtime_pass']} | "
            f"{record['eligible']} |"
        )
    lines.extend(
        [
            "",
            "All thresholds and candidates were committed before training. Planner regret is "
            "cross-evaluated with the frozen reference model. Final test files opened: `0`.",
            "",
        ]
    )
    (args.output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    paths = sorted(
        path
        for path in args.output_dir.rglob("*")
        if path.is_file() and path.name != "artifact_hashes.json"
    )
    _write_json(
        args.output_dir / "artifact_hashes.json",
        {str(path.relative_to(args.output_dir)): _sha256(path) for path in paths},
    )
    print(
        f"residual_width_sweep=complete selected={selected_name or 'none'} "
        f"eligible={len(result['eligible_model_names'])} test_opened=0"
    )


if __name__ == "__main__":
    main()
