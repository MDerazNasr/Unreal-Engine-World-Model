from __future__ import annotations

import copy
import math
import threading
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from motionworld.control.live_moving_obstacle_config import (
    load_live_moving_obstacle_config,
)
from motionworld.control.live_nominal_mpc import LiveNominalMPCController
from motionworld.protocol import validate_action_mapping
from tests.unit.test_live_planner_adapter import _observation

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/live_moving_obstacle_demo.yaml"


def _near_obstacle_observation(scenario_time_s: float):
    observation = _observation(9)
    observation["source"]["controller_mode"] = "nominal_mpc"
    observation["state"]["position_world_cm"] = [-610.0, 0.0, 86.0]
    observation["state"]["velocity_world_cm_per_s"] = [100.0, 0.0, 0.0]
    observation["state"]["velocity_local_planar_cm_per_s"] = [100.0, 0.0]
    observation["planner_context"]["target"]["position_world_cm"] = [800.0, 0.0, 86.0]
    gate = observation["planner_context"]["timed_gate"]
    omega = 2.0 * math.pi / 3.7
    angle = 0.83 + omega * scenario_time_s
    gate.update(
        {
            "scenario_time_s": scenario_time_s,
            "origin_world_cm": [-450.0, 0.0, 90.0],
            "motion_axis_world": [0.0, 1.0, 0.0],
            "amplitude_cm": 185.0,
            "period_s": 3.7,
            "phase_offset_rad": 0.83,
            "half_extents_cm": [35.0, 55.0, 90.0],
            "center_world_cm": [-450.0, 185.0 * math.sin(angle), 90.0],
            "velocity_world_cm_per_s": [
                0.0,
                185.0 * omega * math.cos(angle),
                0.0,
            ],
            "timeout_s": 20.0,
        }
    )
    return observation


def test_v2_config_layers_obstacle_over_verified_learned_overlay() -> None:
    config = load_live_moving_obstacle_config(CONFIG, ROOT)

    assert config.moving_obstacle_enabled
    assert config.arrival_radius_cm == 100.0
    assert config.show_cem_candidates_with_overlay
    assert config.problem_template.geometry.agent_radius_cm == 30.0
    assert config.problem_template.geometry.gate_x_cm == -450.0
    assert config.problem_template.geometry.gate_period_s == 3.7
    assert config.problem_template.geometry.gate_phase_offset_rad == 0.83
    assert config.problem_template.weights.collision == 5000.0
    assert config.problem_template.weights.clearance_per_cm2 == 0.02
    assert config.residual_overlay_model is not None
    assert config.residual_overlay_steps == 5


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        (
            "base_residual_overlay",
            "sha256",
            "0" * 64,
            "SHA-256 mismatch",
        ),
        ("weights", "collision", 0.0, "must be positive"),
        (
            None,
            "scenario_time_source",
            "observation_simulation_time",
            "authoritative timed-gate time",
        ),
    ],
)
def test_v2_config_rejects_contract_drift(
    tmp_path: Path,
    section: str | None,
    field: str,
    value: object,
    message: str,
) -> None:
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    changed = copy.deepcopy(raw)
    target = changed if section is None else changed[section]
    target[field] = value
    path = tmp_path / "v2.yaml"
    path.write_text(yaml.safe_dump(changed), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_live_moving_obstacle_config(path, ROOT)


def test_v2_nominal_mpc_uses_authoritative_obstacle_phase_deterministically(
    monkeypatch,
) -> None:
    from motionworld.control import live_nominal_mpc

    full = load_live_moving_obstacle_config(CONFIG, ROOT)
    nominal_only = replace(
        full,
        residual_overlay_model=None,
        residual_overlay_normalization=None,
        residual_overlay_rollout=None,
        residual_overlay_steps=None,
    )
    controller = LiveNominalMPCController(nominal_only)
    plans = []
    real_plan = live_nominal_mpc.plan_model

    def capture_plan(*args, **kwargs):
        plan = real_plan(*args, **kwargs)
        plans.append(plan)
        return plan

    monkeypatch.setattr(live_nominal_mpc, "plan_model", capture_plan)

    phase_zero_first = controller(_near_obstacle_observation(0.0), threading.Event())
    phase_zero_second = controller(_near_obstacle_observation(0.0), threading.Event())
    later_phase = controller(_near_obstacle_observation(0.75), threading.Event())

    assert phase_zero_first is not None
    assert phase_zero_second is not None
    assert later_phase is not None
    assert phase_zero_first["command"] == phase_zero_second["command"]
    assert phase_zero_first["command"] != later_phase["command"]
    validated = validate_action_mapping(phase_zero_first)
    assert validated["fallback"] == {"is_safe_fallback": False, "reason": "none"}
    assert validated["controller"]["model_id"] == "nominal_mpc_moving_obstacle_v2"
    # At this frozen near-obstacle state and phase, the selected command visibly
    # commits to a lateral avoidance maneuver rather than continuing straight.
    assert abs(validated["command"]["desired_velocity_local_cm_per_s"][1]) > 80.0
    assert plans[0].best_cost.collision_indicator[0] == 0.0


def test_v2_keeps_nominal_action_owner_and_emits_matched_learned_overlay() -> None:
    config = load_live_moving_obstacle_config(CONFIG, ROOT)
    observation = _near_obstacle_observation(0.0)
    result = LiveNominalMPCController(config)(observation, threading.Event())

    assert result is not None
    validated = validate_action_mapping(result)
    assert validated["controller"] == {
        "controller_id": "nominal_mpc",
        "model_id": "nominal_mpc_moving_obstacle_residual_overlay_v2",
    }
    assert [path["role"] for path in validated["telemetry"]["visualization"]["paths"]] == [
        "cem_candidate",
        "cem_candidate",
        "nominal",
        "residual",
    ]


def test_v2_fails_safe_when_authoritative_obstacle_timing_is_absent() -> None:
    config = load_live_moving_obstacle_config(CONFIG, ROOT)
    observation = _near_obstacle_observation(0.0)
    observation["planner_context"]["timed_gate"] = {"is_present": False}
    observation["validity"]["timed_gate_present"] = False

    result = LiveNominalMPCController(config)(observation, threading.Event())

    assert result is not None
    validated = validate_action_mapping(result)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
    assert validated["fallback"] == {
        "is_safe_fallback": True,
        "reason": "invalid_observation",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amplitude_cm", 184.0),
        ("origin_world_cm", [-449.0, 0.0, 90.0]),
        ("motion_axis_world", [1.0, 0.0, 0.0]),
        ("center_world_cm", [-450.0, 0.0, 90.0]),
    ],
)
def test_v2_fails_safe_on_obstacle_geometry_or_schedule_drift(
    field: str, value: object
) -> None:
    config = load_live_moving_obstacle_config(CONFIG, ROOT)
    observation = _near_obstacle_observation(0.0)
    observation["planner_context"]["timed_gate"][field] = value

    result = LiveNominalMPCController(config)(observation, threading.Event())

    assert result is not None
    validated = validate_action_mapping(result)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
    assert validated["fallback"] == {
        "is_safe_fallback": True,
        "reason": "invalid_observation",
    }


def test_v2_stops_stably_inside_arrival_radius_without_replanning() -> None:
    config = load_live_moving_obstacle_config(CONFIG, ROOT)
    observation = _near_obstacle_observation(0.0)
    observation["state"]["position_world_cm"] = [725.0, 0.0, 86.0]

    result = LiveNominalMPCController(config)(observation, threading.Event())

    assert result is not None
    validated = validate_action_mapping(result)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
    assert validated["fallback"] == {"is_safe_fallback": False, "reason": "none"}
    assert validated["controller"]["model_id"] == (
        "nominal_mpc_moving_obstacle_arrival_stop_v2"
    )
    assert validated["telemetry"]["is_present"] is False
