"""Vectorized, analytic planning costs for the planar timed-gate scenario."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class TimedGateGeometry:
    """Known analytic obstacle and character geometry, all in centimeters/seconds."""

    gate_x_cm: float
    gate_y_origin_cm: float
    gate_amplitude_cm: float
    gate_period_s: float
    gate_phase_offset_rad: float
    gate_half_extent_x_cm: float
    gate_half_extent_y_cm: float
    agent_radius_cm: float
    safety_margin_cm: float

    def __post_init__(self) -> None:
        values = (
            self.gate_x_cm,
            self.gate_y_origin_cm,
            self.gate_amplitude_cm,
            self.gate_period_s,
            self.gate_phase_offset_rad,
            self.gate_half_extent_x_cm,
            self.gate_half_extent_y_cm,
            self.agent_radius_cm,
            self.safety_margin_cm,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("gate geometry values must be finite")
        if self.gate_period_s <= 0.0:
            raise ValueError("gate_period_s must be positive")
        if self.gate_amplitude_cm < 0.0:
            raise ValueError("gate_amplitude_cm must be non-negative")
        if self.gate_half_extent_x_cm <= 0.0 or self.gate_half_extent_y_cm <= 0.0:
            raise ValueError("gate half extents must be positive")
        if self.agent_radius_cm < 0.0 or self.safety_margin_cm < 0.0:
            raise ValueError("agent radius and safety margin must be non-negative")


@dataclass(frozen=True, slots=True)
class PlanningCostWeights:
    """Multipliers convert unlike component units into one scalar ranking."""

    terminal_goal_per_cm: float
    collision: float
    clearance_per_cm2: float
    action_change_per_cm2_s2: float
    action_second_difference_per_cm2_s2: float

    def __post_init__(self) -> None:
        values = (
            self.terminal_goal_per_cm,
            self.collision,
            self.clearance_per_cm2,
            self.action_change_per_cm2_s2,
            self.action_second_difference_per_cm2_s2,
        )
        if not all(math.isfinite(value) and value >= 0.0 for value in values):
            raise ValueError("planning cost weights must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class PlanningCostBreakdown:
    """Unweighted components plus their weighted total, one value per candidate."""

    terminal_goal_distance_cm: FloatArray
    collision_indicator: FloatArray
    clearance_deficit_squared_cm2: FloatArray
    action_change_squared_cm2_s2: FloatArray
    action_second_difference_squared_cm2_s2: FloatArray
    total: FloatArray


def _finite_array(name: str, values: FloatArray, *, ndim: int) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def evaluate_timed_gate_centers(
    geometry: TimedGateGeometry,
    scenario_times_s: FloatArray,
) -> FloatArray:
    """Evaluate the deterministic gate center directly from absolute scenario time."""

    times = _finite_array("scenario_times_s", scenario_times_s, ndim=1)
    if np.any(times < 0.0):
        raise ValueError("scenario times must be non-negative")
    angular_frequency = 2.0 * math.pi / geometry.gate_period_s
    phase = geometry.gate_phase_offset_rad + angular_frequency * times
    centers = np.empty((times.size, 2), dtype=np.float64)
    centers[:, 0] = geometry.gate_x_cm
    centers[:, 1] = geometry.gate_y_origin_cm + geometry.gate_amplitude_cm * np.sin(phase)
    return centers


def terminal_goal_distance(
    predicted_positions_world_cm: FloatArray,
    goal_world_cm: FloatArray,
) -> FloatArray:
    """Euclidean terminal distance in centimeters for every candidate."""

    positions = _finite_array(
        "predicted_positions_world_cm",
        predicted_positions_world_cm,
        ndim=3,
    )
    if positions.shape[1] == 0 or positions.shape[2] != 2:
        raise ValueError("predicted positions must have shape [candidate, step, 2]")
    goal = _finite_array("goal_world_cm", goal_world_cm, ndim=1)
    if goal.shape != (2,):
        raise ValueError("goal_world_cm must have shape [2]")
    return np.linalg.norm(positions[:, -1, :] - goal, axis=1)


def _segment_intersects_centered_box(
    starts: FloatArray,
    ends: FloatArray,
    half_extents: FloatArray,
) -> BoolArray:
    """Batched slab test for relative-motion line segments versus one centered AABB."""

    delta = ends - starts
    enter = np.zeros(starts.shape[0], dtype=np.float64)
    exit_ = np.ones(starts.shape[0], dtype=np.float64)
    possible = np.ones(starts.shape[0], dtype=np.bool_)
    for axis in range(2):
        stationary = np.abs(delta[:, axis]) <= 1.0e-12
        outside = np.abs(starts[:, axis]) > half_extents[axis]
        possible &= ~(stationary & outside)
        moving = ~stationary
        first = np.zeros(starts.shape[0], dtype=np.float64)
        second = np.zeros(starts.shape[0], dtype=np.float64)
        first[moving] = (-half_extents[axis] - starts[moving, axis]) / delta[moving, axis]
        second[moving] = (half_extents[axis] - starts[moving, axis]) / delta[moving, axis]
        axis_enter = np.minimum(first, second)
        axis_exit = np.maximum(first, second)
        enter[moving] = np.maximum(enter[moving], axis_enter[moving])
        exit_[moving] = np.minimum(exit_[moving], axis_exit[moving])
    return possible & (enter <= exit_) & (exit_ >= 0.0) & (enter <= 1.0)


def swept_gate_collision_indicator(
    initial_position_world_cm: FloatArray,
    predicted_positions_world_cm: FloatArray,
    *,
    initial_scenario_time_s: float,
    scenario_times_s: FloatArray,
    geometry: TimedGateGeometry,
) -> FloatArray:
    """Return one if any relative agent/gate segment intersects capsule-expanded gate bounds."""

    positions = _finite_array(
        "predicted_positions_world_cm",
        predicted_positions_world_cm,
        ndim=3,
    )
    if positions.shape[1] == 0 or positions.shape[2] != 2:
        raise ValueError("predicted positions must have shape [candidate, step, 2]")
    initial = _finite_array("initial_position_world_cm", initial_position_world_cm, ndim=1)
    if initial.shape != (2,):
        raise ValueError("initial_position_world_cm must have shape [2]")
    times = _validate_step_times(
        initial_scenario_time_s,
        scenario_times_s,
        expected_steps=positions.shape[1],
    )
    all_times = np.concatenate(([initial_scenario_time_s], times))
    gate_centers = evaluate_timed_gate_centers(geometry, all_times)
    initial_batch = np.broadcast_to(initial, (positions.shape[0], 1, 2))
    agent_positions = np.concatenate((initial_batch, positions), axis=1)
    relative = agent_positions - gate_centers[None, :, :]
    half_extents = np.array(
        [
            geometry.gate_half_extent_x_cm + geometry.agent_radius_cm,
            geometry.gate_half_extent_y_cm + geometry.agent_radius_cm,
        ],
        dtype=np.float64,
    )
    collided = np.zeros(positions.shape[0], dtype=np.bool_)
    for step in range(positions.shape[1]):
        collided |= _segment_intersects_centered_box(
            relative[:, step, :],
            relative[:, step + 1, :],
            half_extents,
        )
    return collided.astype(np.float64)


def _validate_step_times(
    initial_scenario_time_s: float,
    scenario_times_s: FloatArray,
    *,
    expected_steps: int,
) -> FloatArray:
    if not math.isfinite(initial_scenario_time_s) or initial_scenario_time_s < 0.0:
        raise ValueError("initial_scenario_time_s must be finite and non-negative")
    times = _finite_array("scenario_times_s", scenario_times_s, ndim=1)
    if times.shape != (expected_steps,):
        raise ValueError("scenario_times_s must contain one time per predicted step")
    if np.any(times <= initial_scenario_time_s) or np.any(np.diff(times) <= 0.0):
        raise ValueError("scenario times must increase strictly after the initial time")
    return times


def clearance_deficit_squared(
    predicted_positions_world_cm: FloatArray,
    *,
    scenario_times_s: FloatArray,
    geometry: TimedGateGeometry,
) -> FloatArray:
    """Mean squared shortfall from requested capsule-to-gate safety clearance."""

    positions = _finite_array(
        "predicted_positions_world_cm",
        predicted_positions_world_cm,
        ndim=3,
    )
    if positions.shape[1] == 0 or positions.shape[2] != 2:
        raise ValueError("predicted positions must have shape [candidate, step, 2]")
    times = _finite_array("scenario_times_s", scenario_times_s, ndim=1)
    if times.shape != (positions.shape[1],):
        raise ValueError("scenario_times_s must contain one time per predicted step")
    centers = evaluate_timed_gate_centers(geometry, times)
    relative = np.abs(positions - centers[None, :, :])
    box_extents = np.array(
        [geometry.gate_half_extent_x_cm, geometry.gate_half_extent_y_cm],
        dtype=np.float64,
    )
    outside_delta = np.maximum(relative - box_extents, 0.0)
    center_to_box_distance = np.linalg.norm(outside_delta, axis=-1)
    physical_clearance = center_to_box_distance - geometry.agent_radius_cm
    deficit = np.maximum(geometry.safety_margin_cm - physical_clearance, 0.0)
    return np.mean(np.square(deficit), axis=1)


def action_change_squared(
    actions_cm_s: FloatArray,
    previous_action_cm_s: FloatArray,
) -> FloatArray:
    """Mean squared first difference, including the observed previous action."""

    actions = _validate_actions(actions_cm_s)
    previous = _finite_array("previous_action_cm_s", previous_action_cm_s, ndim=1)
    if previous.shape != (2,):
        raise ValueError("previous_action_cm_s must have shape [2]")
    prefix = np.broadcast_to(previous, (actions.shape[0], 1, 2))
    differences = np.diff(np.concatenate((prefix, actions), axis=1), axis=1)
    return np.mean(np.sum(np.square(differences), axis=-1), axis=1)


def action_second_difference_squared(
    actions_cm_s: FloatArray,
    previous_action_cm_s: FloatArray,
    previous_previous_action_cm_s: FloatArray,
) -> FloatArray:
    """Mean squared second difference, including two observed action-history values."""

    actions = _validate_actions(actions_cm_s)
    previous = _finite_array("previous_action_cm_s", previous_action_cm_s, ndim=1)
    previous_previous = _finite_array(
        "previous_previous_action_cm_s",
        previous_previous_action_cm_s,
        ndim=1,
    )
    if previous.shape != (2,) or previous_previous.shape != (2,):
        raise ValueError("action history values must each have shape [2]")
    prefix_previous = np.broadcast_to(previous, (actions.shape[0], 1, 2))
    prefix_previous_previous = np.broadcast_to(
        previous_previous,
        (actions.shape[0], 1, 2),
    )
    extended = np.concatenate((prefix_previous_previous, prefix_previous, actions), axis=1)
    second_differences = np.diff(extended, n=2, axis=1)
    return np.mean(np.sum(np.square(second_differences), axis=-1), axis=1)


def _validate_actions(actions_cm_s: FloatArray) -> FloatArray:
    actions = _finite_array("actions_cm_s", actions_cm_s, ndim=3)
    if actions.shape[1] == 0 or actions.shape[2] != 2:
        raise ValueError("actions_cm_s must have shape [candidate, step, 2]")
    return actions


def evaluate_planning_cost(
    predicted_positions_world_cm: FloatArray,
    actions_cm_s: FloatArray,
    *,
    initial_position_world_cm: FloatArray,
    previous_action_cm_s: FloatArray,
    previous_previous_action_cm_s: FloatArray,
    goal_world_cm: FloatArray,
    initial_scenario_time_s: float,
    scenario_times_s: FloatArray,
    geometry: TimedGateGeometry,
    weights: PlanningCostWeights,
) -> PlanningCostBreakdown:
    """Evaluate every declared component and combine them without hidden terms."""

    positions = _finite_array(
        "predicted_positions_world_cm",
        predicted_positions_world_cm,
        ndim=3,
    )
    actions = _validate_actions(actions_cm_s)
    if positions.shape != actions.shape:
        raise ValueError("predicted positions and actions must share [candidate, step, 2]")
    times = _validate_step_times(
        initial_scenario_time_s,
        scenario_times_s,
        expected_steps=positions.shape[1],
    )
    terminal = terminal_goal_distance(positions, goal_world_cm)
    collision = swept_gate_collision_indicator(
        initial_position_world_cm,
        positions,
        initial_scenario_time_s=initial_scenario_time_s,
        scenario_times_s=times,
        geometry=geometry,
    )
    clearance = clearance_deficit_squared(
        positions,
        scenario_times_s=times,
        geometry=geometry,
    )
    change = action_change_squared(actions, previous_action_cm_s)
    second = action_second_difference_squared(
        actions,
        previous_action_cm_s,
        previous_previous_action_cm_s,
    )
    total = (
        weights.terminal_goal_per_cm * terminal
        + weights.collision * collision
        + weights.clearance_per_cm2 * clearance
        + weights.action_change_per_cm2_s2 * change
        + weights.action_second_difference_per_cm2_s2 * second
    )
    return PlanningCostBreakdown(terminal, collision, clearance, change, second, total)
