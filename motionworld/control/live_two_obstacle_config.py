"""Strict V3 loader for exactly two authoritative analytic obstacles."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import yaml

from motionworld.control.live_moving_obstacle_config import (
    load_live_moving_obstacle_config,
)
from motionworld.planning.cost import TimedGateGeometry


def load_live_two_obstacle_config(path: Path, repository_root: Path):
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {
        "schema_name",
        "schema_version",
        "status",
        "claim_boundary",
        "show_cem_candidates_with_overlay",
        "base_moving_obstacle",
        "secondary_geometry",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("two-obstacle config has unexpected keys")
    if raw["schema_name"] != "motionworld_live_two_obstacle_demo" or raw[
        "schema_version"
    ] != 1:
        raise ValueError("unsupported two-obstacle config schema")
    if raw["status"] != "visual_demo_nominal_control_two_learned_forecast_obstacles":
        raise ValueError("two-obstacle status must preserve nominal control ownership")
    claim = raw["claim_boundary"]
    if not isinstance(claim, str) or "nominal MPC controls" not in claim:
        raise ValueError("two-obstacle claim must disclose nominal MPC ownership")
    if raw["show_cem_candidates_with_overlay"] is not False:
        raise ValueError("V3 must disable optional CEM candidate rendering")
    record = raw["base_moving_obstacle"]
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ValueError("base_moving_obstacle keys must be path and sha256")
    relative = record["path"]
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("base_moving_obstacle.path must be repository-relative")
    base_path = (repository_root / relative).resolve()
    try:
        base_path.relative_to(repository_root.resolve())
    except ValueError as error:
        raise ValueError("base_moving_obstacle.path must stay inside repository") from error
    if hashlib.sha256(base_path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("base_moving_obstacle SHA-256 mismatch")
    geometry_raw = raw["secondary_geometry"]
    if not isinstance(geometry_raw, dict) or set(geometry_raw) != set(
        TimedGateGeometry.__dataclass_fields__
    ):
        raise ValueError("secondary_geometry keys are invalid")
    secondary = TimedGateGeometry(**geometry_raw)
    base = load_live_moving_obstacle_config(base_path, repository_root)
    if base.problem_template.additional_geometries:
        raise ValueError("V3 base must contain exactly one obstacle")
    return replace(
        base,
        show_cem_candidates_with_overlay=False,
        problem_template=replace(
            base.problem_template,
            additional_geometries=(secondary,),
        ),
    )
