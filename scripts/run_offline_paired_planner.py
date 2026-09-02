#!/usr/bin/env python3
"""Run the frozen nominal/residual CEM comparison without opening test episodes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import yaml

from motionworld.data.residual_manifest import audit_residual_dataset
from motionworld.dynamics.nominal_episode import current_snapshot_nominal_inputs
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState
from motionworld.models.residual_training import load_residual_checkpoint
from motionworld.planning.cem import CEMConfig
from motionworld.planning.cost import (
    PlanningCostBreakdown,
    PlanningCostWeights,
    TimedGateGeometry,
    evaluate_planning_cost,
    evaluate_timed_gate_centers,
)
from motionworld.planning.mpc import (
    ModelPlan,
    PlannerProblem,
    PlannerQuery,
    plan_paired_nominal_residual,
)
from motionworld.planning.planner_rollout import (
    PlannerRollout,
    PlannerRolloutConfig,
    PlannerSnapshot,
    rollout_action_candidates,
)

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], *, context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _vector2(value: object, *, context: str) -> tuple[float, float]:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (2,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{context} must contain exactly two finite values")
    return float(array[0]), float(array[1])


def _nonempty_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _nonnegative_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{context} must be a non-negative integer")
    return value


def _nonnegative_float(value: object, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a finite non-negative number")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{context} must be a finite non-negative number")
    return result


def _load_cem_config(path: Path) -> tuple[CEMConfig, PlannerRolloutConfig, int, float]:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), context="CEM config")
    expected = {
        "schema_name",
        "schema_version",
        "seed",
        "decision_interval_s",
        "horizon_s",
        "dynamics_substeps_per_plan_step",
        "optimizer",
        "toy_oracle",
    }
    _exact_keys(raw, expected, context="CEM config")
    if raw["schema_name"] != "motionworld_cem_planner_config" or raw["schema_version"] != 1:
        raise ValueError("unsupported CEM config schema")
    optimizer = _mapping(raw["optimizer"], context="optimizer")
    _exact_keys(optimizer, set(CEMConfig.__dataclass_fields__), context="optimizer")
    cem = CEMConfig(**optimizer)
    seed = _nonnegative_int(raw["seed"], context="CEM seed")
    rollout = PlannerRolloutConfig(
        plan_step_s=float(raw["decision_interval_s"]),
        dynamics_substeps_per_plan_step=raw["dynamics_substeps_per_plan_step"],
    )
    horizon_s = float(raw["horizon_s"])
    if not math.isclose(
        cem.num_plan_steps * rollout.plan_step_s,
        horizon_s,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError("CEM step count and decision interval do not match horizon")
    return cem, rollout, seed, horizon_s


def _load_problem_config(
    path: Path,
) -> tuple[dict[str, Any], TimedGateGeometry, PlanningCostWeights]:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), context="problem config")
    expected = {
        "schema_name",
        "schema_version",
        "status",
        "claim_boundary",
        "source_validation_episode_id",
        "source_transition_index",
        "counterfactual_start_world_cm",
        "goal_world_cm",
        "initial_scenario_time_s",
        "previous_action_local_cm_s",
        "previous_previous_action_local_cm_s",
        "initial_mean_action_local_cm_s",
        "geometry",
        "weights",
    }
    _exact_keys(raw, expected, context="problem config")
    if raw["schema_name"] != "motionworld_offline_planner_config" or raw["schema_version"] != 1:
        raise ValueError("unsupported offline planner config schema")
    raw["status"] = _nonempty_string(raw["status"], context="status")
    raw["claim_boundary"] = _nonempty_string(
        raw["claim_boundary"], context="claim_boundary"
    )
    raw["source_validation_episode_id"] = _nonnegative_int(
        raw["source_validation_episode_id"],
        context="source_validation_episode_id",
    )
    raw["source_transition_index"] = _nonnegative_int(
        raw["source_transition_index"],
        context="source_transition_index",
    )
    raw["initial_scenario_time_s"] = _nonnegative_float(
        raw["initial_scenario_time_s"], context="initial_scenario_time_s"
    )
    for name in (
        "counterfactual_start_world_cm",
        "goal_world_cm",
        "previous_action_local_cm_s",
        "previous_previous_action_local_cm_s",
        "initial_mean_action_local_cm_s",
    ):
        raw[name] = _vector2(raw[name], context=name)
    geometry_record = _mapping(raw["geometry"], context="geometry").copy()
    geometry_provenance = _nonempty_string(
        geometry_record.pop("provenance", None), context="geometry provenance"
    )
    _exact_keys(
        geometry_record,
        set(TimedGateGeometry.__dataclass_fields__),
        context="geometry",
    )
    weights_record = _mapping(raw["weights"], context="weights").copy()
    weights_provenance = _nonempty_string(
        weights_record.pop("provenance", None), context="weights provenance"
    )
    _exact_keys(
        weights_record,
        set(PlanningCostWeights.__dataclass_fields__),
        context="weights",
    )
    raw["geometry_provenance"] = geometry_provenance
    raw["weights_provenance"] = weights_provenance
    return raw, TimedGateGeometry(**geometry_record), PlanningCostWeights(**weights_record)


def _breakdown_record(cost: PlanningCostBreakdown) -> dict[str, float]:
    return {
        "terminal_goal_distance_cm": float(cost.terminal_goal_distance_cm[0]),
        "collision_indicator": float(cost.collision_indicator[0]),
        "clearance_deficit_squared_cm2": float(cost.clearance_deficit_squared_cm2[0]),
        "action_change_squared_cm2_s2": float(cost.action_change_squared_cm2_s2[0]),
        "action_second_difference_squared_cm2_s2": float(
            cost.action_second_difference_squared_cm2_s2[0]
        ),
        "total": float(cost.total[0]),
    }


def _model_plan_record(plan: ModelPlan) -> dict[str, Any]:
    return {
        "first_action_local_cm_s": plan.cem.first_action_cm_s.tolist(),
        "best_cost_as_ranked": plan.cem.best_cost,
        "best_cost_reevaluated": _breakdown_record(plan.best_cost),
        "selected_cost_reproduction_error": plan.selected_cost_reproduction_error,
        "iteration_best_cost": [item.best_cost for item in plan.cem.iterations],
        "evaluated_action_sha256": list(plan.evaluated_action_sha256),
        "predicted_terminal_position_world_cm": plan.best_rollout.positions_world_cm[
            0, -1
        ].tolist(),
    }


def _evaluate_actions(
    actions: np.ndarray,
    *,
    problem: PlannerProblem,
    query: PlannerQuery,
    residual_model: Any = None,
    residual_normalization: Any = None,
) -> tuple[PlannerRollout, PlanningCostBreakdown]:
    action_batch = actions[np.newaxis, :, :]
    rollout = rollout_action_candidates(
        query.snapshot,
        action_batch,
        config=problem.rollout,
        residual_model=residual_model,
        residual_normalization=residual_normalization,
    )
    times = query.scenario_time_s + problem.rollout.plan_step_s * np.arange(
        1,
        problem.cem.num_plan_steps + 1,
    )
    cost = evaluate_planning_cost(
        rollout.positions_world_cm,
        action_batch,
        initial_position_world_cm=np.asarray(
            query.snapshot.observable.position_world_cm[:2],
            dtype=np.float64,
        ),
        previous_action_cm_s=np.asarray(query.previous_action_local_cm_s),
        previous_previous_action_cm_s=np.asarray(
            query.previous_previous_action_local_cm_s
        ),
        goal_world_cm=np.asarray(problem.goal_world_cm),
        initial_scenario_time_s=query.scenario_time_s,
        scenario_times_s=times,
        geometry=problem.geometry,
        weights=problem.weights,
    )
    return rollout, cost


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_paths(
    path: Path,
    *,
    times: np.ndarray,
    gate_centers: np.ndarray,
    paths: dict[str, PlannerRollout],
) -> None:
    names = tuple(paths)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        header = ["plan_step", "scenario_time_s", "gate_x_cm", "gate_y_cm"]
        for name in names:
            header.extend((f"{name}_x_cm", f"{name}_y_cm"))
        writer.writerow(header)
        for step, scenario_time in enumerate(times):
            row: list[object] = [step, scenario_time, *gate_centers[step]]
            for name in names:
                row.extend(paths[name].positions_world_cm[0, step])
            writer.writerow(row)


def _plot(
    path: Path,
    *,
    problem: PlannerProblem,
    query: PlannerQuery,
    paired: Any,
    paths: dict[str, PlannerRollout],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    axis = axes[0, 0]
    style = {
        "nominal_plan_nominal_model": ("tab:blue", "-"),
        "nominal_plan_residual_model": ("tab:blue", "--"),
        "residual_plan_nominal_model": ("tab:orange", "--"),
        "residual_plan_residual_model": ("tab:orange", "-"),
    }
    start = np.asarray(query.snapshot.observable.position_world_cm[:2])
    for name, rollout in paths.items():
        values = np.vstack((start, rollout.positions_world_cm[0]))
        color, line = style[name]
        axis.plot(values[:, 0], values[:, 1], line, color=color, label=name.replace("_", " "))
    times = query.scenario_time_s + problem.rollout.plan_step_s * np.arange(
        1,
        problem.cem.num_plan_steps + 1,
    )
    gates = evaluate_timed_gate_centers(problem.geometry, times)
    axis.scatter(
        gates[:, 0],
        gates[:, 1],
        marker="s",
        s=18,
        color="gray",
        alpha=0.5,
        label="gate centers",
    )
    axis.scatter(*problem.goal_world_cm, marker="*", s=160, color="green", label="goal")
    axis.scatter(*start, marker="o", s=60, color="black", label="start")
    axis.set_title("Selected plans cross-evaluated under both models")
    axis.set_xlabel("world X (cm)")
    axis.set_ylabel("world Y (cm)")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=7)
    axis.set_aspect("equal", adjustable="datalim")

    axis = axes[0, 1]
    for plan, color in ((paired.nominal, "tab:blue"), (paired.residual, "tab:orange")):
        axis.plot(
            np.arange(1, len(plan.cem.iterations) + 1),
            [item.best_cost for item in plan.cem.iterations],
            marker="o",
            color=color,
            label=plan.model_name,
        )
    axis.set_title("Adaptive CEM cost by model")
    axis.set_xlabel("iteration")
    axis.set_ylabel("best predicted cost")
    axis.grid(alpha=0.25)
    axis.legend()

    axis = axes[1, 0]
    component_names = ("goal", "collision", "clearance", "action change", "action curvature")
    for index, plan in enumerate((paired.nominal, paired.residual)):
        cost = plan.best_cost
        weighted = (
            problem.weights.terminal_goal_per_cm * cost.terminal_goal_distance_cm[0],
            problem.weights.collision * cost.collision_indicator[0],
            problem.weights.clearance_per_cm2 * cost.clearance_deficit_squared_cm2[0],
            problem.weights.action_change_per_cm2_s2 * cost.action_change_squared_cm2_s2[0],
            problem.weights.action_second_difference_per_cm2_s2
            * cost.action_second_difference_squared_cm2_s2[0],
        )
        axis.bar(
            np.arange(len(component_names)) + (index - 0.5) * 0.35,
            weighted,
            width=0.35,
            label=plan.model_name,
        )
    axis.set_xticks(np.arange(len(component_names)), component_names, rotation=20, ha="right")
    axis.set_ylabel("weighted cost contribution")
    axis.set_title("No cost component is hidden")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)

    axis = axes[1, 1]
    actions = np.stack(
        (paired.nominal.cem.first_action_cm_s, paired.residual.cem.first_action_cm_s)
    )
    for action, color, label in zip(
        actions,
        ("tab:blue", "tab:orange"),
        ("nominal", "residual"),
        strict=True,
    ):
        axis.quiver(
            0.0,
            0.0,
            action[0],
            action[1],
            angles="xy",
            scale_units="xy",
            scale=1.0,
            color=color,
            label=label,
        )
    limit = problem.cem.max_action_speed_cm_s * 1.1
    axis.set_xlim(-limit, limit)
    axis.set_ylim(-limit, limit)
    axis.set_aspect("equal")
    axis.set_xlabel("local forward request (cm/s)")
    axis.set_ylabel("local right request (cm/s)")
    axis.set_title("Different model predictions select different first actions")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.suptitle("OFFPLAN-001 — offline model-based comparison, not Unreal control evidence")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
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

    cem, rollout_config, seed, horizon_s = _load_cem_config(args.cem_config)
    raw_problem, geometry, weights = _load_problem_config(args.problem_config)
    checkpoint = load_residual_checkpoint(str(args.checkpoint))
    if checkpoint.history_length != 1:
        raise ValueError("offline planner requires the selected no-history checkpoint")
    comparison = json.loads(args.training_comparison.read_text(encoding="utf-8"))
    if _sha256(args.checkpoint) != comparison["checkpoint_sha256"]["no_history"]:
        raise ValueError("checkpoint hash differs from frozen training comparison")
    manifest_hash = _sha256(args.dataset_manifest)
    if checkpoint.dataset_manifest_sha256 != manifest_hash:
        raise ValueError("checkpoint dataset manifest hash differs")

    dataset = audit_residual_dataset(args.collection_plan, args.raw_data_root)
    source_episode_id = raw_problem["source_validation_episode_id"]
    source = next(
        (
            item
            for item in dataset.episodes_for_split("validation")
            if item.episode_id == source_episode_id
        ),
        None,
    )
    if source is None:
        raise ValueError("source episode is not an accepted validation episode")
    transition_index = raw_problem["source_transition_index"]
    if not 0 <= transition_index < len(source.episode.transitions):
        raise ValueError("source_transition_index is outside the accepted episode")
    initial = current_snapshot_nominal_inputs(source.episode.transitions[transition_index])
    preparation = source.episode.transitions[transition_index]["nominal_context"]["previous"][
        "input_preparation"
    ]
    if not preparation["has_max_move_speed"]:
        raise ValueError("source snapshot must provide an effective max speed")
    effective_max_speed = float(preparation["effective_max_speed_cm_per_s"])
    start = np.asarray(raw_problem["counterfactual_start_world_cm"], dtype=np.float64)
    relocated_observable = SmoothWalkingObservableState(
        position_world_cm=np.array(
            [start[0], start[1], initial.observable.position_world_cm[2]],
            dtype=np.float64,
        ),
        velocity_world_cm_s=initial.observable.velocity_world_cm_s.copy(),
        facing_yaw_rad=initial.observable.facing_yaw_rad,
        angular_velocity_yaw_deg_s=initial.observable.angular_velocity_yaw_deg_s,
        simulation_time_s=0.0,
    )
    snapshot = PlannerSnapshot(
        observable=relocated_observable,
        internal=initial.internal,
        parameters=initial.parameters,
        effective_max_speed_cm_s=effective_max_speed,
    )
    problem = PlannerProblem(
        cem=cem,
        rollout=rollout_config,
        geometry=geometry,
        weights=weights,
        goal_world_cm=raw_problem["goal_world_cm"],
    )
    mean_action = np.asarray(raw_problem["initial_mean_action_local_cm_s"], dtype=np.float64)
    query = PlannerQuery(
        snapshot=snapshot,
        scenario_time_s=float(raw_problem["initial_scenario_time_s"]),
        previous_action_local_cm_s=raw_problem["previous_action_local_cm_s"],
        previous_previous_action_local_cm_s=raw_problem[
            "previous_previous_action_local_cm_s"
        ],
        initial_mean_knots_local_cm_s=np.tile(mean_action, (cem.num_knots, 1)),
    )

    start_time = time.perf_counter()
    paired = plan_paired_nominal_residual(
        problem,
        query,
        seed=seed,
        residual_model=checkpoint.model,
        residual_normalization=checkpoint.normalization,
    )
    elapsed_s = time.perf_counter() - start_time

    selected_actions = {
        "nominal_plan": paired.nominal.cem.best_actions_cm_s,
        "residual_plan": paired.residual.cem.best_actions_cm_s,
    }
    paths: dict[str, PlannerRollout] = {}
    cross_cost: dict[str, dict[str, float]] = {}
    for plan_name, actions in selected_actions.items():
        for model_name in ("nominal_model", "residual_model"):
            use_residual = model_name == "residual_model"
            result, cost = _evaluate_actions(
                actions,
                problem=problem,
                query=query,
                residual_model=checkpoint.model if use_residual else None,
                residual_normalization=checkpoint.normalization if use_residual else None,
            )
            key = f"{plan_name}_{model_name}"
            paths[key] = result
            cross_cost[key] = _breakdown_record(cost)

    times = query.scenario_time_s + rollout_config.plan_step_s * np.arange(
        1,
        cem.num_plan_steps + 1,
    )
    gates = evaluate_timed_gate_centers(geometry, times)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_paths(
        args.output_dir / "cross_evaluated_paths.csv",
        times=times,
        gate_centers=gates,
        paths=paths,
    )
    _plot(
        args.output_dir / "offline_paired_planner.png",
        problem=problem,
        query=query,
        paired=paired,
        paths=paths,
    )
    summary = {
        "schema_name": "motionworld_offline_paired_planner_result",
        "schema_version": 1,
        "claim_boundary": raw_problem["claim_boundary"],
        "configuration_status": raw_problem["status"],
        "git_commit": args.git_commit,
        "seed": seed,
        "horizon_s": horizon_s,
        "source_validation_episode_id": source_episode_id,
        "source_transition_index": transition_index,
        "source_raw_sha256": source.raw_sha256,
        "test_files_opened": 0,
        "checkpoint_sha256": _sha256(args.checkpoint),
        "dataset_manifest_sha256": manifest_hash,
        "cem_config": asdict(cem),
        "rollout_config": asdict(rollout_config),
        "geometry": asdict(geometry),
        "geometry_provenance": raw_problem["geometry_provenance"],
        "weights": asdict(weights),
        "weights_provenance": raw_problem["weights_provenance"],
        "query": {
            "counterfactual_start_world_cm": start.tolist(),
            "goal_world_cm": list(problem.goal_world_cm),
            "initial_scenario_time_s": query.scenario_time_s,
            "previous_action_local_cm_s": list(query.previous_action_local_cm_s),
            "previous_previous_action_local_cm_s": list(
                query.previous_previous_action_local_cm_s
            ),
            "initial_mean_action_local_cm_s": mean_action.tolist(),
        },
        "common_noise_sha256": paired.common_noise_sha256,
        "first_iteration_candidates_identical": paired.first_iteration_candidates_identical,
        "later_candidate_batches_identical": (
            paired.nominal.evaluated_action_sha256[1:]
            == paired.residual.evaluated_action_sha256[1:]
        ),
        "later_candidate_batches_may_diverge_by_design": True,
        "fairness_verified": paired.fairness_verified,
        "nominal": _model_plan_record(paired.nominal),
        "residual": _model_plan_record(paired.residual),
        "selected_plan_cross_evaluation": cross_cost,
        "timing_policy": (
            "wall time printed only; excluded from deterministic artifact and not RUNTIME-001"
        ),
    }
    _write_json(args.output_dir / "summary.json", summary)
    readme = f"""# OFFPLAN-001 offline paired planner

This is model-based counterfactual integration evidence, not Unreal control evidence.

- Source context: accepted validation episode `{source_episode_id}`, transition
  `{transition_index}`,
  relocated to `{start.tolist()}` cm because absolute position is excluded from residual features.
- Test files opened: `0`.
- Common first-iteration candidate batch: `{paired.first_iteration_candidates_identical}`.
- Nominal first action: `{paired.nominal.cem.first_action_cm_s.tolist()}` cm/s.
- Residual first action: `{paired.residual.cem.first_action_cm_s.tolist()}` cm/s.
- Nominal predicted collision: `{int(paired.nominal.best_cost.collision_indicator[0])}`.
- Residual predicted collision: `{int(paired.residual.best_cost.collision_indicator[0])}`.
- Wall time is printed to the terminal only. It is not part of this deterministic artifact and is
  not a `RUNTIME-001` latency measurement.

The cost matrix cross-evaluates both selected action sequences under both models. It is a
model-error diagnostic, not realized-world return. Final controller claims require same-seed Unreal
execution.
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
        "offline_planner=complete "
        f"nominal_action={paired.nominal.cem.first_action_cm_s.tolist()} "
        f"residual_action={paired.residual.cem.first_action_cm_s.tolist()} "
        f"first_candidates_same={paired.first_iteration_candidates_identical} "
        f"test_opened=0 wall_s={elapsed_s:.3f}"
    )


if __name__ == "__main__":
    main()
