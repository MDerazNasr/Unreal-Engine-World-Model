from __future__ import annotations

import copy
import math
import threading
from pathlib import Path

import numpy as np
import pytest

from motionworld.control.live_nominal_mpc import LiveNominalMPCController
from motionworld.control.live_two_obstacle_config import load_live_two_obstacle_config
from motionworld.planning.cost import (
    PlanningCostWeights,
    TimedGateGeometry,
    evaluate_multi_obstacle_planning_cost,
)
from motionworld.protocol import validate_action_mapping, validate_observation_mapping
from tests.unit.test_live_moving_obstacle_config import _near_obstacle_observation

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/live_two_obstacle_demo.yaml"


def _two_obstacle_observation(scenario_time_s: float = 0.0):
    observation = _near_obstacle_observation(scenario_time_s)
    observation["planner_context"]["timed_gate"]["timeout_s"] = 30.0
    primary = copy.deepcopy(observation["planner_context"]["timed_gate"])
    primary["obstacle_id"] = "gate_primary"
    omega = 2.0 * math.pi / 8.0
    angle = 5.497787144 + omega * scenario_time_s
    secondary = {
        **copy.deepcopy(observation["planner_context"]["timed_gate"]),
        "obstacle_id": "gate_secondary",
        "scenario_time_s": scenario_time_s,
        "origin_world_cm": [250.0, 80.0, 90.0],
        "amplitude_cm": 45.0,
        "period_s": 8.0,
        "phase_offset_rad": 5.497787144,
        "half_extents_cm": [35.0, 80.0, 90.0],
        "center_world_cm": [250.0, 80.0 + 45.0 * math.sin(angle), 90.0],
        "velocity_world_cm_per_s": [0.0, 45.0 * omega * math.cos(angle), 0.0],
        "timeout_s": 30.0,
    }
    observation["planner_context"]["obstacles"] = [primary, secondary]
    return observation


def test_v3_protocol_accepts_exact_two_obstacles_and_preserves_legacy_gate() -> None:
    validated = validate_observation_mapping(_two_obstacle_observation())

    assert [item["obstacle_id"] for item in validated["planner_context"]["obstacles"]] == [
        "gate_primary",
        "gate_secondary",
    ]
    assert "obstacles" not in validate_observation_mapping(
        _near_obstacle_observation(0.0)
    )["planner_context"]


@pytest.mark.parametrize("mutation", ["missing", "identity", "legacy", "clock"])
def test_v3_protocol_rejects_incomplete_or_inconsistent_obstacles(mutation: str) -> None:
    observation = _two_obstacle_observation()
    if mutation == "missing":
        observation["planner_context"]["obstacles"].pop()
    elif mutation == "identity":
        observation["planner_context"]["obstacles"][1]["obstacle_id"] = "wrong"
    elif mutation == "legacy":
        observation["planner_context"]["obstacles"][0]["amplitude_cm"] = 1.0
    else:
        observation["planner_context"]["obstacles"][1]["scenario_time_s"] = 0.1

    with pytest.raises(ValueError):
        validate_observation_mapping(observation)


def test_v3_config_loads_exactly_one_additional_geometry() -> None:
    config = load_live_two_obstacle_config(CONFIG, ROOT)
    assert not config.show_cem_candidates_with_overlay

    assert len(config.problem_template.additional_geometries) == 1
    secondary = config.problem_template.additional_geometries[0]
    assert secondary.gate_x_cm == 250.0
    assert secondary.gate_y_origin_cm == 80.0
    assert secondary.gate_amplitude_cm == 45.0
    assert secondary.gate_period_s == 8.0


def test_multi_obstacle_cost_counts_risk_from_both_obstacles() -> None:
    geometry = TimedGateGeometry(0, 0, 0, 1, 0, 1, 1, 0, 0)
    second = TimedGateGeometry(4, 0, 0, 1, 0, 1, 1, 0, 0)
    positions = np.asarray([[[2.0, 0.0], [5.0, 0.0]]])
    actions = np.zeros((1, 2, 2))
    result = evaluate_multi_obstacle_planning_cost(
        positions,
        actions,
        initial_position_world_cm=np.asarray([-2.0, 0.0]),
        previous_action_cm_s=np.zeros(2),
        previous_previous_action_cm_s=np.zeros(2),
        goal_world_cm=np.asarray([5.0, 0.0]),
        initial_scenario_time_s=0.0,
        scenario_times_s=np.asarray([0.1, 0.2]),
        geometries=(geometry, second),
        weights=PlanningCostWeights(0, 10, 0, 0, 0),
    )

    assert result.collision_indicator[0] == 2.0
    assert result.total[0] == 20.0


def test_v3_controller_keeps_nominal_owner_and_learned_overlay() -> None:
    config = load_live_two_obstacle_config(CONFIG, ROOT)
    result = LiveNominalMPCController(config)(
        _two_obstacle_observation(), threading.Event()
    )

    assert result is not None
    validated = validate_action_mapping(result)
    assert validated["fallback"] == {"is_safe_fallback": False, "reason": "none"}
    assert validated["controller"] == {
        "controller_id": "nominal_mpc",
        "model_id": "nominal_mpc_two_obstacle_residual_overlay_v3",
    }


def test_v3_controller_fails_safe_without_secondary_context() -> None:
    config = load_live_two_obstacle_config(CONFIG, ROOT)
    observation = _two_obstacle_observation()
    del observation["planner_context"]["obstacles"]
    result = LiveNominalMPCController(config)(observation, threading.Event())

    assert result is not None
    validated = validate_action_mapping(result)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
    assert validated["fallback"] == {
        "is_safe_fallback": True,
        "reason": "invalid_observation",
    }
