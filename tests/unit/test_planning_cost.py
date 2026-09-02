from __future__ import annotations

import math

import numpy as np
import pytest

from motionworld.planning.cost import (
    PlanningCostWeights,
    TimedGateGeometry,
    action_change_squared,
    action_second_difference_squared,
    clearance_deficit_squared,
    evaluate_planning_cost,
    evaluate_timed_gate_centers,
    swept_gate_collision_indicator,
    terminal_goal_distance,
)


def _geometry(**changes: float) -> TimedGateGeometry:
    values = {
        "gate_x_cm": 0.0,
        "gate_y_origin_cm": 0.0,
        "gate_amplitude_cm": 0.0,
        "gate_period_s": 4.0,
        "gate_phase_offset_rad": 0.0,
        "gate_half_extent_x_cm": 5.0,
        "gate_half_extent_y_cm": 10.0,
        "agent_radius_cm": 2.0,
        "safety_margin_cm": 3.0,
    }
    values.update(changes)
    return TimedGateGeometry(**values)


def test_timed_gate_center_matches_quarter_period_hand_example() -> None:
    geometry = _geometry(gate_y_origin_cm=20.0, gate_amplitude_cm=10.0)
    centers = evaluate_timed_gate_centers(geometry, np.array([0.0, 1.0, 2.0]))
    np.testing.assert_allclose(centers[:, 0], 0.0)
    np.testing.assert_allclose(centers[:, 1], [20.0, 30.0, 20.0], atol=1.0e-12)


def test_terminal_goal_distance_is_three_four_five() -> None:
    positions = np.array([[[0.0, 0.0], [3.0, 4.0]], [[9.0, 1.0], [0.0, 0.0]]])
    np.testing.assert_allclose(terminal_goal_distance(positions, np.zeros(2)), [5.0, 0.0])


def test_swept_collision_catches_endpoint_tunnelling() -> None:
    positions = np.array([[[20.0, 0.0]], [[20.0, 50.0]]])
    collision = swept_gate_collision_indicator(
        np.array([-20.0, 0.0]),
        positions,
        initial_scenario_time_s=0.0,
        scenario_times_s=np.array([0.1]),
        geometry=_geometry(),
    )
    np.testing.assert_array_equal(collision, [1.0, 0.0])


def test_swept_collision_uses_relative_gate_motion() -> None:
    geometry = _geometry(
        gate_amplitude_cm=20.0,
        gate_period_s=4.0,
        gate_half_extent_x_cm=2.0,
        gate_half_extent_y_cm=2.0,
        agent_radius_cm=0.0,
    )
    # Agent is stationary at y=10 while the gate moves from y=0 to y=20 over a quarter period.
    positions = np.array([[[0.0, 10.0]]])
    collision = swept_gate_collision_indicator(
        np.array([0.0, 10.0]),
        positions,
        initial_scenario_time_s=0.0,
        scenario_times_s=np.array([1.0]),
        geometry=geometry,
    )
    np.testing.assert_array_equal(collision, [1.0])


def test_clearance_penalty_has_physical_hand_values() -> None:
    geometry = _geometry()
    # At x=10, center-to-box distance=5, capsule clearance=3, exactly the margin: zero.
    # At x=8, center-to-box distance=3, capsule clearance=1, deficit=2: squared penalty four.
    positions = np.array([[[10.0, 0.0]], [[8.0, 0.0]]])
    penalty = clearance_deficit_squared(
        positions,
        scenario_times_s=np.array([0.1]),
        geometry=geometry,
    )
    np.testing.assert_allclose(penalty, [0.0, 4.0])


def test_first_action_difference_includes_observed_previous_action() -> None:
    actions = np.array([[[3.0, 4.0], [6.0, 8.0]]])
    # Squared changes are 25 and 25, so their mean is 25.
    np.testing.assert_allclose(action_change_squared(actions, np.zeros(2)), [25.0])


def test_second_difference_is_zero_for_linear_action_sequence() -> None:
    actions = np.array([[[2.0, 0.0], [3.0, 0.0], [4.0, 0.0]]])
    penalty = action_second_difference_squared(
        actions,
        previous_action_cm_s=np.array([1.0, 0.0]),
        previous_previous_action_cm_s=np.array([0.0, 0.0]),
    )
    np.testing.assert_array_equal(penalty, [0.0])


def test_full_cost_is_exact_weighted_sum_of_visible_components() -> None:
    positions = np.array([[[8.0, 0.0]]])
    actions = np.array([[[3.0, 4.0]]])
    weights = PlanningCostWeights(
        terminal_goal_per_cm=2.0,
        collision=100.0,
        clearance_per_cm2=3.0,
        action_change_per_cm2_s2=4.0,
        action_second_difference_per_cm2_s2=5.0,
    )
    result = evaluate_planning_cost(
        positions,
        actions,
        initial_position_world_cm=np.array([8.0, 0.0]),
        previous_action_cm_s=np.zeros(2),
        previous_previous_action_cm_s=np.zeros(2),
        goal_world_cm=np.zeros(2),
        initial_scenario_time_s=0.0,
        scenario_times_s=np.array([0.1]),
        geometry=_geometry(),
        weights=weights,
    )
    assert result.terminal_goal_distance_cm[0] == 8.0
    assert result.collision_indicator[0] == 0.0
    assert result.clearance_deficit_squared_cm2[0] == 4.0
    assert result.action_change_squared_cm2_s2[0] == 25.0
    assert result.action_second_difference_squared_cm2_s2[0] == 25.0
    assert result.total[0] == 16.0 + 0.0 + 12.0 + 100.0 + 125.0


def test_collision_weight_increases_cost_and_never_rewards_collision() -> None:
    weights = PlanningCostWeights(0.0, 1000.0, 0.0, 0.0, 0.0)
    result = evaluate_planning_cost(
        np.array([[[20.0, 0.0]], [[20.0, 50.0]]]),
        np.zeros((2, 1, 2)),
        initial_position_world_cm=np.array([-20.0, 0.0]),
        previous_action_cm_s=np.zeros(2),
        previous_previous_action_cm_s=np.zeros(2),
        goal_world_cm=np.zeros(2),
        initial_scenario_time_s=0.0,
        scenario_times_s=np.array([0.1]),
        geometry=_geometry(),
        weights=weights,
    )
    np.testing.assert_array_equal(result.total, [1000.0, 0.0])


@pytest.mark.parametrize(
    "changes",
    [
        {"gate_period_s": 0.0},
        {"gate_half_extent_x_cm": -1.0},
        {"agent_radius_cm": -1.0},
        {"safety_margin_cm": math.nan},
    ],
)
def test_invalid_geometry_fails(changes: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        _geometry(**changes)


def test_nonfinite_or_nonmonotonic_cost_inputs_fail() -> None:
    with pytest.raises(ValueError, match="finite"):
        terminal_goal_distance(np.array([[[math.nan, 0.0]]]), np.zeros(2))
    with pytest.raises(ValueError, match="increase strictly"):
        evaluate_planning_cost(
            np.zeros((1, 2, 2)),
            np.zeros((1, 2, 2)),
            initial_position_world_cm=np.zeros(2),
            previous_action_cm_s=np.zeros(2),
            previous_previous_action_cm_s=np.zeros(2),
            goal_world_cm=np.zeros(2),
            initial_scenario_time_s=0.0,
            scenario_times_s=np.array([0.1, 0.1]),
            geometry=_geometry(),
            weights=PlanningCostWeights(1.0, 1.0, 1.0, 1.0, 1.0),
        )
