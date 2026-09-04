"""Strict V2 loader for nominal MPC around one synchronized moving obstacle."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import yaml

from motionworld.control.live_residual_overlay_config import (
    load_live_residual_overlay_config,
)
from motionworld.planning.cost import PlanningCostWeights, TimedGateGeometry


def _verified_relative_path(
    repository_root: Path, record: object, context: str
) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ValueError(f"{context} keys must be exactly path and sha256")
    relative = record["path"]
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"{context}.path must be repository-relative")
    path = (repository_root / relative).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as error:
        raise ValueError(f"{context}.path must stay inside the repository") from error
    expected = record["sha256"]
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if not isinstance(expected, str) or observed != expected:
        raise ValueError(f"{context} SHA-256 mismatch")
    return path


def load_live_moving_obstacle_config(path: Path, repository_root: Path):
    """Load the frozen visual-demo obstacle on top of the verified D6 model overlay."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {
        "schema_name",
        "schema_version",
        "status",
        "claim_boundary",
        "base_residual_overlay",
        "motion_seed",
        "motion_formula",
        "scenario_time_source",
        "arrival_radius_cm",
        "show_cem_candidates_with_overlay",
        "geometry",
        "weights",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("moving-obstacle config has unexpected keys")
    if (
        raw["schema_name"] != "motionworld_live_moving_obstacle_demo"
        or raw["schema_version"] != 1
    ):
        raise ValueError("unsupported moving-obstacle config schema")
    if raw["status"] != "visual_demo_nominal_control_with_learned_overlay":
        raise ValueError("moving-obstacle status must preserve nominal control ownership")
    claim = raw["claim_boundary"]
    if not isinstance(claim, str) or "nominal MPC controls" not in claim:
        raise ValueError("moving-obstacle claim must disclose nominal MPC ownership")
    if type(raw["motion_seed"]) is not int or raw["motion_seed"] < 0:
        raise ValueError("motion_seed must be a non-negative metadata integer")
    if raw["motion_formula"] != "y=y_origin+amplitude*sin(phase+2*pi*t/period)":
        raise ValueError("moving-obstacle motion formula is unsupported")
    if raw["scenario_time_source"] != "authoritative_timed_gate_scenario_time":
        raise ValueError("moving-obstacle clock must be authoritative timed-gate time")
    arrival_radius_cm = raw["arrival_radius_cm"]
    if (
        isinstance(arrival_radius_cm, bool)
        or not isinstance(arrival_radius_cm, (int, float))
        or not 0.0 < float(arrival_radius_cm) <= 150.0
    ):
        raise ValueError("arrival_radius_cm must be in (0, 150]")
    if raw["show_cem_candidates_with_overlay"] is not True:
        raise ValueError("V2 must show CEM candidates with the learned overlay")

    geometry_raw = raw["geometry"]
    if not isinstance(geometry_raw, dict) or set(geometry_raw) != set(
        TimedGateGeometry.__dataclass_fields__
    ):
        raise ValueError("moving-obstacle geometry keys are invalid")
    weights_raw = raw["weights"]
    if not isinstance(weights_raw, dict) or set(weights_raw) != set(
        PlanningCostWeights.__dataclass_fields__
    ):
        raise ValueError("moving-obstacle weight keys are invalid")
    geometry = TimedGateGeometry(**geometry_raw)
    weights = PlanningCostWeights(**weights_raw)
    if weights.collision <= 0.0 or weights.clearance_per_cm2 <= 0.0:
        raise ValueError("moving-obstacle collision and clearance weights must be positive")
    if weights.action_second_difference_per_cm2_s2 != 0.0:
        raise ValueError("stateless V2 requires zero action-second-difference weight")

    base_path = _verified_relative_path(
        repository_root, raw["base_residual_overlay"], "base_residual_overlay"
    )
    base = load_live_residual_overlay_config(base_path, repository_root)
    return replace(
        base,
        problem_template=replace(base.problem_template, geometry=geometry, weights=weights),
        moving_obstacle_enabled=True,
        arrival_radius_cm=float(arrival_radius_cm),
        show_cem_candidates_with_overlay=True,
    )
