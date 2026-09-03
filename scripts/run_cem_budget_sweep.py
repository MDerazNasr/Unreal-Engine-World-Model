#!/usr/bin/env python3
"""Sweep reduced CEM budgets on frozen validation queries without opening test data."""

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

from motionworld.data.residual_manifest import audit_residual_dataset
from motionworld.models.residual_training import load_residual_checkpoint
from motionworld.planning.budget_sweep import (
    CEMBudgetSweep,
    derive_cem_config,
    load_cem_budget_sweep,
    nested_standard_normal_noise,
    select_eligible_budget,
)
from motionworld.planning.cem import CEMConfig, sample_standard_normal_schedule
from motionworld.planning.config import load_cem_planner_config, load_offline_planner_config
from motionworld.planning.mpc import ModelPlan, PlannerProblem, PlannerQuery, plan_model
from motionworld.planning.offline_context import build_counterfactual_query

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _problem(
    cem: CEMConfig,
    *,
    rollout: Any,
    geometry: Any,
    weights: Any,
    goal_world_cm: tuple[float, float],
) -> PlannerProblem:
    return PlannerProblem(
        cem=cem,
        rollout=rollout,
        geometry=geometry,
        weights=weights,
        goal_world_cm=goal_world_cm,
        rollout_backend="vectorized",
    )


def _solve(
    problem: PlannerProblem,
    query: PlannerQuery,
    noise: np.ndarray,
    *,
    model_name: str,
    checkpoint: Any,
) -> ModelPlan:
    use_residual = model_name == "residual"
    return plan_model(
        problem,
        query,
        standard_normal_noise=noise,
        model_name=model_name,
        residual_model=checkpoint.model if use_residual else None,
        residual_normalization=checkpoint.normalization if use_residual else None,
    )


def _quality_observation(
    candidate: ModelPlan,
    reference: ModelPlan,
    *,
    episode_id: int,
    transition_index: int,
    model_name: str,
) -> dict[str, Any]:
    reference_cost = float(reference.best_cost.total[0])
    candidate_cost = float(candidate.best_cost.total[0])
    relative_regret = (candidate_cost - reference_cost) / max(abs(reference_cost), 1.0)
    candidate_collision = bool(candidate.best_cost.collision_indicator[0])
    reference_collision = bool(reference.best_cost.collision_indicator[0])
    path_difference = (
        candidate.best_rollout.positions_world_cm - reference.best_rollout.positions_world_cm
    )
    return {
        "episode_id": episode_id,
        "transition_index": transition_index,
        "model": model_name,
        "reference_cost": reference_cost,
        "candidate_cost": candidate_cost,
        "signed_relative_regret": relative_regret,
        "positive_relative_regret": max(0.0, relative_regret),
        "reference_collision": reference_collision,
        "candidate_collision": candidate_collision,
        "new_predicted_collision": candidate_collision and not reference_collision,
        "first_action_distance_cm_s": float(
            np.linalg.norm(candidate.cem.first_action_cm_s - reference.cem.first_action_cm_s)
        ),
        "path_rms_difference_cm": float(np.sqrt(np.mean(np.square(path_difference)))),
    }


def _quality_summary(
    observations: list[dict[str, Any]],
    *,
    sweep: CEMBudgetSweep,
) -> tuple[dict[str, Any], bool, float]:
    by_model: dict[str, Any] = {}
    for model_name in ("nominal", "residual"):
        rows = [row for row in observations if row["model"] == model_name]
        positive_regret = np.asarray(
            [row["positive_relative_regret"] for row in rows], dtype=np.float64
        )
        signed_regret = np.asarray(
            [row["signed_relative_regret"] for row in rows], dtype=np.float64
        )
        action_distance = np.asarray(
            [row["first_action_distance_cm_s"] for row in rows], dtype=np.float64
        )
        path_difference = np.asarray(
            [row["path_rms_difference_cm"] for row in rows], dtype=np.float64
        )
        by_model[model_name] = {
            "query_count": len(rows),
            "mean_signed_relative_regret": float(np.mean(signed_regret)),
            "mean_positive_relative_regret": float(np.mean(positive_regret)),
            "p95_positive_relative_regret": float(np.percentile(positive_regret, 95)),
            "maximum_positive_relative_regret": float(np.max(positive_regret)),
            "new_predicted_collision_count": sum(
                int(row["new_predicted_collision"]) for row in rows
            ),
            "median_first_action_distance_cm_s": float(np.median(action_distance)),
            "p95_first_action_distance_cm_s": float(np.percentile(action_distance, 95)),
            "median_path_rms_difference_cm": float(np.median(path_difference)),
        }
    new_collisions = sum(
        by_model[model_name]["new_predicted_collision_count"]
        for model_name in ("nominal", "residual")
    )
    p95_regret = max(
        by_model[model_name]["p95_positive_relative_regret"]
        for model_name in ("nominal", "residual")
    )
    worst_mean = max(
        by_model[model_name]["mean_positive_relative_regret"]
        for model_name in ("nominal", "residual")
    )
    passed = (
        new_collisions <= sweep.maximum_new_predicted_collisions
        and p95_regret <= sweep.maximum_p95_positive_relative_regret
    )
    return (
        {
            "by_model": by_model,
            "new_predicted_collision_count": new_collisions,
            "worst_model_p95_positive_relative_regret": p95_regret,
            "worst_model_mean_positive_relative_regret": worst_mean,
            "passed": passed,
        },
        passed,
        worst_mean,
    )


def _runtime_statistics(values_ms: list[float], *, deadline_ms: float) -> dict[str, Any]:
    values = np.asarray(values_ms, dtype=np.float64)
    median = float(np.median(values))
    p95 = float(np.percentile(values, 95))
    return {
        "sample_count": len(values_ms),
        "median_ms": median,
        "p95_ms": p95,
        "minimum_ms": float(np.min(values)),
        "maximum_ms": float(np.max(values)),
        "missed_deadline_count": int(np.count_nonzero(values > deadline_ms)),
        "deadline_ms": deadline_ms,
        "median_meets_deadline": median <= deadline_ms,
        "p95_meets_deadline": p95 <= deadline_ms,
        "latencies_ms": values_ms,
    }


def _measure_runtime(
    problem: PlannerProblem,
    query: PlannerQuery,
    noise: np.ndarray,
    *,
    checkpoint: Any,
    sweep: CEMBudgetSweep,
) -> dict[str, Any]:
    functions = {
        model_name: (
            lambda name=model_name: _solve(
                problem,
                query,
                noise,
                model_name=name,
                checkpoint=checkpoint,
            )
        )
        for model_name in ("nominal", "residual")
    }
    for _ in range(sweep.warmups_per_controller):
        functions["nominal"]()
        functions["residual"]()
    values: dict[str, list[float]] = {"nominal": [], "residual": []}
    for repetition in range(sweep.repetitions_per_controller):
        order = ("nominal", "residual") if repetition % 2 == 0 else ("residual", "nominal")
        for model_name in order:
            started_ns = time.perf_counter_ns()
            functions[model_name]()
            values[model_name].append((time.perf_counter_ns() - started_ns) / 1_000_000.0)
    return {
        model_name: _runtime_statistics(values[model_name], deadline_ms=sweep.deadline_ms)
        for model_name in ("nominal", "residual")
    }


def _plot(path: Path, records: list[dict[str, Any]], *, sweep: CEMBudgetSweep) -> None:
    names = [record["name"] for record in records]
    x = np.arange(len(names))
    figure, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    axis = axes[0]
    axis.plot(
        x,
        [record["runtime"]["nominal"]["p95_ms"] for record in records],
        marker="o",
        label="nominal p95",
    )
    axis.plot(
        x,
        [record["runtime"]["residual"]["p95_ms"] for record in records],
        marker="o",
        label="residual p95",
    )
    axis.axhline(sweep.deadline_ms, color="black", linestyle="--", label="100 ms deadline")
    axis.set_ylabel("complete planner latency (ms)")
    axis.set_title("Runtime gate")
    axis.grid(alpha=0.25)
    axis.legend()

    axis = axes[1]
    width = 0.36
    axis.bar(
        x - width / 2,
        [
            100.0 * record["quality"]["by_model"]["nominal"]["p95_positive_relative_regret"]
            for record in records
        ],
        width,
        label="nominal",
    )
    axis.bar(
        x + width / 2,
        [
            100.0 * record["quality"]["by_model"]["residual"]["p95_positive_relative_regret"]
            for record in records
        ],
        width,
        label="residual",
    )
    axis.axhline(
        100.0 * sweep.maximum_p95_positive_relative_regret,
        color="black",
        linestyle="--",
        label="quality threshold",
    )
    axis.set_ylabel("p95 positive cost regret (%)")
    axis.set_title("Validation-only quality gate versus 256/32/3 reference")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    axis.set_xticks(x, names, rotation=25, ha="right")
    figure.suptitle("CEM-BUDGET-001 — lower model cost is not realized Unreal return")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep-config", type=Path, required=True)
    parser.add_argument("--cem-config", type=Path, required=True)
    parser.add_argument("--problem-config", type=Path, required=True)
    parser.add_argument("--collection-plan", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--training-comparison", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--raw-data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()

    sweep = load_cem_budget_sweep(args.sweep_config)
    base_cem, rollout, seed, horizon_s = load_cem_planner_config(args.cem_config)
    reference_counts = (
        base_cem.num_candidates,
        base_cem.num_elites,
        base_cem.num_iterations,
    )
    declared_counts = (
        sweep.reference.num_candidates,
        sweep.reference.num_elites,
        sweep.reference.num_iterations,
    )
    if reference_counts != declared_counts:
        raise ValueError("budget-sweep reference does not match the frozen CEM config")
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
    validation_by_id = {
        source.episode_id: source for source in dataset.episodes_for_split("validation")
    }
    if any(query.episode_id not in validation_by_id for query in sweep.validation_queries):
        raise ValueError("sweep query references a non-accepted validation episode")
    torch.set_num_threads(sweep.torch_threads)

    queries: dict[tuple[int, int], PlannerQuery] = {}
    for query_index in sweep.validation_queries:
        source = validation_by_id[query_index.episode_id]
        queries[(query_index.episode_id, query_index.transition_index)] = (
            build_counterfactual_query(
                source,
                query_index.transition_index,
                problem_config=raw_problem,
                cem=base_cem,
            )
        )
    reference_noise = sample_standard_normal_schedule(base_cem, seed=seed)
    reference_problem = _problem(
        base_cem,
        rollout=rollout,
        geometry=geometry,
        weights=weights,
        goal_world_cm=raw_problem["goal_world_cm"],
    )
    references: dict[tuple[int, int, str], ModelPlan] = {}
    for (episode_id, transition_index), query in queries.items():
        for model_name in ("nominal", "residual"):
            references[(episode_id, transition_index, model_name)] = _solve(
                reference_problem,
                query,
                reference_noise,
                model_name=model_name,
                checkpoint=checkpoint,
            )

    quality_records: list[dict[str, Any]] = []
    runtime_records: list[dict[str, Any]] = []
    selection_records: list[dict[str, Any]] = []
    canonical_key = (
        sweep.validation_queries[0].episode_id,
        sweep.validation_queries[0].transition_index,
    )
    for budget in sweep.candidates:
        cem = derive_cem_config(base_cem, budget)
        noise = nested_standard_normal_noise(reference_noise, config=cem)
        problem = _problem(
            cem,
            rollout=rollout,
            geometry=geometry,
            weights=weights,
            goal_world_cm=raw_problem["goal_world_cm"],
        )
        observations: list[dict[str, Any]] = []
        for (episode_id, transition_index), query in queries.items():
            for model_name in ("nominal", "residual"):
                candidate = _solve(
                    problem,
                    query,
                    noise,
                    model_name=model_name,
                    checkpoint=checkpoint,
                )
                observations.append(
                    _quality_observation(
                        candidate,
                        references[(episode_id, transition_index, model_name)],
                        episode_id=episode_id,
                        transition_index=transition_index,
                        model_name=model_name,
                    )
                )
        quality, quality_pass, worst_mean = _quality_summary(observations, sweep=sweep)
        quality_records.append(
            {
                "name": budget.name,
                "cem_counts": asdict(budget),
                "summary": quality,
                "observations": observations,
            }
        )
        runtime = _measure_runtime(
            problem,
            queries[canonical_key],
            noise,
            checkpoint=checkpoint,
            sweep=sweep,
        )
        runtime_pass = all(runtime[model_name]["p95_meets_deadline"] for model_name in runtime)
        runtime_records.append(
            {
                "name": budget.name,
                "cem_counts": asdict(budget),
                "runtime": runtime,
                "passed": runtime_pass,
            }
        )
        selection_records.append(
            {
                "name": budget.name,
                "eligible": quality_pass and runtime_pass,
                "quality_pass": quality_pass,
                "runtime_pass": runtime_pass,
                "worst_model_mean_positive_relative_regret": worst_mean,
                "runtime": runtime,
                "quality": quality,
            }
        )
    selected_name = select_eligible_budget(selection_records)
    selected_budget = next(
        (budget for budget in sweep.candidates if budget.name == selected_name), None
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    common = {
        "claim_boundary": sweep.claim_boundary,
        "configuration_status": sweep.status,
        "git_commit": args.git_commit,
        "seed": seed,
        "horizon_s": horizon_s,
        "test_files_opened": 0,
        "checkpoint_sha256": checkpoint_hash,
        "dataset_manifest_sha256": manifest_hash,
        "sweep_config_sha256": _sha256(args.sweep_config),
        "cem_config_sha256": _sha256(args.cem_config),
        "problem_config_sha256": _sha256(args.problem_config),
    }
    quality_artifact = {
        "schema_name": "motionworld_cem_budget_quality_sweep",
        "schema_version": 1,
        **common,
        "reference": asdict(sweep.reference),
        "validation_queries": [asdict(query) for query in sweep.validation_queries],
        "quality_gate": {
            "maximum_p95_positive_relative_regret": (sweep.maximum_p95_positive_relative_regret),
            "maximum_new_predicted_collisions": sweep.maximum_new_predicted_collisions,
        },
        "budgets": quality_records,
    }
    runtime_artifact = {
        "schema_name": "motionworld_cem_budget_runtime_sweep",
        "schema_version": 1,
        **common,
        "runtime_gate": {
            "deadline_ms": sweep.deadline_ms,
            "warmups_per_controller": sweep.warmups_per_controller,
            "repetitions_per_controller": sweep.repetitions_per_controller,
            "torch_threads": torch.get_num_threads(),
            "canonical_validation_query": {
                "episode_id": canonical_key[0],
                "transition_index": canonical_key[1],
            },
        },
        "budgets": runtime_records,
    }
    selection_artifact = {
        "schema_name": "motionworld_cem_budget_selection",
        "schema_version": 1,
        **common,
        "selection_rule": sweep.selection_rule,
        "selected_budget": asdict(selected_budget) if selected_budget is not None else None,
        "eligible_budget_names": [
            record["name"] for record in selection_records if record["eligible"]
        ],
        "records": selection_records,
    }
    _write_json(args.output_dir / "quality.json", quality_artifact)
    _write_json(args.output_dir / "runtime.json", runtime_artifact)
    _write_json(args.output_dir / "selection.json", selection_artifact)
    _plot(args.output_dir / "budget_sweep.png", selection_records, sweep=sweep)
    selected_text = selected_name if selected_name is not None else "none"
    (args.output_dir / "README.md").write_text(
        "# CEM-BUDGET-001 validation-only runtime/quality sweep\n\n"
        f"Selected budget: `{selected_text}`.\n\n"
        "Quality is predicted cost under the same model and is not realized Unreal return. "
        "All ten source snapshots are accepted validation data; final test files opened: `0`. "
        "See `selection.json` for the prospective gate and full audit record.\n",
        encoding="utf-8",
    )
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
        f"cem_budget_sweep=complete selected={selected_text} "
        f"eligible={[record['name'] for record in selection_records if record['eligible']]} "
        "test_opened=0"
    )


if __name__ == "__main__":
    main()
