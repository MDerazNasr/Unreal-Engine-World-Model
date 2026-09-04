"""Strict loader for the prospective nominal-only live demo budget."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from motionworld.control.live_nominal_mpc import LiveNominalMPCConfig
from motionworld.planning.cem import CEMConfig
from motionworld.planning.cost import PlanningCostWeights, TimedGateGeometry
from motionworld.planning.mpc import PlannerProblem
from motionworld.planning.planner_rollout import PlannerRolloutConfig


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def load_live_nominal_mpc_config(path: Path, repository_root: Path) -> LiveNominalMPCConfig:
    """Load the exact D5 budget without weakening the rejected research gate."""

    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "live MPC config")
    _keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "status",
            "claim_boundary",
            "seed",
            "preview_iteration_winners",
            "initial_mean_action_local_cm_s",
            "optimizer",
            "rollout",
            "inactive_gate_geometry",
            "weights",
            "budget_reference",
        },
        "live MPC config",
    )
    if raw["schema_name"] != "motionworld_live_nominal_mpc_demo" or raw["schema_version"] != 1:
        raise ValueError("unsupported live MPC config schema")
    if raw["status"] != "prospective_live_demo_only_not_research_qualified":
        raise ValueError("live MPC status must preserve the research-gate failure")
    if not isinstance(raw["claim_boundary"], str) or "do not claim" not in raw[
        "claim_boundary"
    ]:
        raise ValueError("live MPC claim boundary must disclose the research-gate failure")

    optimizer = _mapping(raw["optimizer"], "optimizer")
    _keys(optimizer, set(CEMConfig.__dataclass_fields__), "optimizer")
    rollout = _mapping(raw["rollout"], "rollout")
    _keys(rollout, set(PlannerRolloutConfig.__dataclass_fields__), "rollout")
    geometry = _mapping(raw["inactive_gate_geometry"], "inactive_gate_geometry")
    _keys(geometry, set(TimedGateGeometry.__dataclass_fields__), "inactive_gate_geometry")
    weights = _mapping(raw["weights"], "weights")
    _keys(weights, set(PlanningCostWeights.__dataclass_fields__), "weights")

    evidence = _mapping(raw["budget_reference"], "budget_reference")
    _keys(
        evidence,
        {
            "budget_name",
            "reference_scope",
            "source_path",
            "source_sha256",
            "reference_nominal_offline_p95_ms",
            "reference_nominal_mean_positive_relative_regret",
            "reference_nominal_p95_positive_relative_regret",
            "reference_nominal_new_predicted_collisions",
            "research_quality_gate_passed",
        },
        "budget_evidence",
    )
    if (
        evidence["budget_name"] != "c064_i2"
        or evidence["reference_scope"] != "cem_counts_only_live_rollout_differs"
        or evidence["research_quality_gate_passed"] is not False
    ):
        raise ValueError("D5 must retain the rejected c064_i2 research-gate result")
    frozen_metrics = {
        "reference_nominal_offline_p95_ms": 35.81699615,
        "reference_nominal_mean_positive_relative_regret": 0.2243087143919738,
        "reference_nominal_p95_positive_relative_regret": 0.4237719521033547,
        "reference_nominal_new_predicted_collisions": 0,
    }
    if any(evidence[name] != expected for name, expected in frozen_metrics.items()):
        raise ValueError("D5 budget metrics must match the frozen selection artifact")
    source_relative = evidence["source_path"]
    if source_relative != "artifacts/planning/budget_sweep_001/selection.json":
        raise ValueError("budget evidence must use the frozen selection artifact")
    source = repository_root / source_relative
    if hashlib.sha256(source.read_bytes()).hexdigest() != evidence["source_sha256"]:
        raise ValueError("budget evidence SHA-256 mismatch")

    cem = CEMConfig(**optimizer)
    if (cem.num_candidates, cem.num_elites, cem.num_iterations) != (64, 8, 2):
        raise ValueError("D5 requires the deadline-first c064_i2 nominal budget")
    rollout_config = PlannerRolloutConfig(**rollout)
    if rollout_config.dynamics_substeps_per_plan_step != 1:
        raise ValueError("D5 live rollout must use one integration substep per plan step")
    if cem.num_plan_steps * rollout_config.plan_step_s != 1.5:
        raise ValueError("D5 horizon must be exactly 1.5 seconds")
    planning_weights = PlanningCostWeights(**weights)
    problem = PlannerProblem(
        cem=cem,
        rollout=rollout_config,
        geometry=TimedGateGeometry(**geometry),
        weights=planning_weights,
        goal_world_cm=(0.0, 0.0),
        rollout_backend="vectorized",
    )
    initial_mean = raw["initial_mean_action_local_cm_s"]
    if not isinstance(initial_mean, list) or len(initial_mean) != 2:
        raise ValueError("initial_mean_action_local_cm_s must contain exactly two values")
    return LiveNominalMPCConfig(
        problem_template=problem,
        seed=raw["seed"],
        preview_iteration_winners=raw["preview_iteration_winners"],
        initial_mean_action_local_cm_s=(initial_mean[0], initial_mean[1]),
    )
