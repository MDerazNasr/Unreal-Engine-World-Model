"""Strict loaders for the frozen CEM and offline planning configurations."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from motionworld.planning.cem import CEMConfig
from motionworld.planning.cost import PlanningCostWeights, TimedGateGeometry
from motionworld.planning.planner_rollout import PlannerRolloutConfig


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


def load_cem_planner_config(
    path: Path,
) -> tuple[CEMConfig, PlannerRolloutConfig, int, float]:
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


def load_offline_planner_config(
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
    raw["claim_boundary"] = _nonempty_string(raw["claim_boundary"], context="claim_boundary")
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
    _exact_keys(geometry_record, set(TimedGateGeometry.__dataclass_fields__), context="geometry")
    weights_record = _mapping(raw["weights"], context="weights").copy()
    weights_provenance = _nonempty_string(
        weights_record.pop("provenance", None), context="weights provenance"
    )
    _exact_keys(weights_record, set(PlanningCostWeights.__dataclass_fields__), context="weights")
    raw["geometry_provenance"] = geometry_provenance
    raw["weights_provenance"] = weights_provenance
    return raw, TimedGateGeometry(**geometry_record), PlanningCostWeights(**weights_record)
