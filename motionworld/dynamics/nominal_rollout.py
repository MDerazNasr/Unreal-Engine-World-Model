"""Recursive evaluation of the faithful nominal model on validated episode rows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from motionworld.dynamics.nominal_episode import (
    current_snapshot_nominal_inputs,
    observable_from_state_record,
    retrospective_nominal_inputs,
)
from motionworld.dynamics.smooth_walking_input import prepare_velocity_input
from motionworld.dynamics.smooth_walking_math import find_delta_angle_radians
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    smooth_walking_nominal_step,
)


@dataclass(frozen=True, slots=True)
class RecursiveRolloutMetrics:
    """Endpoint error after advancing predicted rather than observed intermediate states."""

    start_transition_sequence: int
    end_transition_sequence: int
    requested_horizon_s: float
    actual_horizon_s: float
    step_count: int
    action_change_count: int
    collision_step_count: int
    external_perturbation_step_count: int
    perturbation_relation: str
    planar_position_error_cm: float
    planar_velocity_error_cm_s: float
    yaw_error_deg: float
    angular_velocity_yaw_error_deg_s: float


def _action_key(transition: dict[str, Any]) -> tuple[float, ...]:
    action = transition["applied_action"]
    return tuple(float(value) for value in action["velocity_world_cm_per_s"]) + (
        float(action["desired_facing_yaw_deg"]),
    )


def evaluate_recursive_nominal_rollouts(
    transitions: list[dict[str, Any]],
    *,
    horizons_s: tuple[float, ...] = (0.5, 1.0, 1.5),
    parameter_policy: str = "retrospective",
) -> tuple[RecursiveRolloutMetrics, ...]:
    """Evaluate open-loop recorded actions without intermediate state re-seeding.

    Each endpoint is the first real transition boundary at or after the requested
    duration. Consequently ``actual_horizon_s`` is reported explicitly and can
    exceed the requested duration by at most one recorded step.

    ``retrospective`` uses each completed-step parameter snapshot as an equation-
    parity oracle. ``hold-current`` reads parameters and max-speed preparation only
    from the rollout's initial finalized state, then holds them throughout that
    imagined future. The latter is causal but deliberately simple until a separate
    parameter selector is justified.
    """

    if not transitions:
        raise ValueError("transitions must not be empty")
    horizons = tuple(sorted(float(value) for value in horizons_s))
    if not horizons or len(set(horizons)) != len(horizons):
        raise ValueError("horizons_s must contain distinct values")
    if any(not math.isfinite(value) or value <= 0.0 for value in horizons):
        raise ValueError("horizons_s must contain positive finite values")
    if parameter_policy not in {"retrospective", "hold-current"}:
        raise ValueError("parameter_policy must be 'retrospective' or 'hold-current'")
    episode_duration_s = sum(float(row["delta_time_s"]) for row in transitions)
    if horizons[-1] > episode_duration_s + 1.0e-12:
        raise ValueError(
            "largest requested horizon exceeds the complete episode duration "
            f"({horizons[-1]:.6g}s > {episode_duration_s:.6g}s)"
        )

    event_indices = [
        index
        for index, row in enumerate(transitions)
        if row.get("external_perturbation", {}).get("type") == "additive_velocity"
    ]
    if len(event_indices) > 1:
        raise ValueError("recursive evaluator supports at most one external perturbation")
    event_index = event_indices[0] if event_indices else None

    results: list[RecursiveRolloutMetrics] = []
    for start_index, first_transition in enumerate(transitions):
        initial = (
            current_snapshot_nominal_inputs(first_transition)
            if parameter_policy == "hold-current"
            else retrospective_nominal_inputs(first_transition)
        )
        predicted_observable = initial.observable
        predicted_internal = initial.internal
        held_parameters = initial.parameters
        held_preparation = first_transition["nominal_context"]["previous"].get(
            "input_preparation"
        )
        if parameter_policy == "hold-current" and held_preparation is None:
            raise ValueError("hold-current policy requires schema-v4+ input preparation")
        elapsed_s = 0.0
        next_horizon_index = 0
        action_change_count = 0
        collision_step_count = 0
        external_perturbation_step_count = 0
        previous_action_key: tuple[float, ...] | None = None

        for end_index in range(start_index, len(transitions)):
            transition = transitions[end_index]
            if parameter_policy == "hold-current":
                action_record = transition["applied_action"]
                if "desired_facing_yaw_deg" not in action_record:
                    raise ValueError("hold-current policy requires schema-v4+ desired facing")
                requested_velocity = np.asarray(
                    action_record["velocity_world_cm_per_s"], dtype=np.float64
                )
                effective_max_speed = (
                    float(held_preparation["effective_max_speed_cm_per_s"])
                    if held_preparation["has_max_move_speed"]
                    else float(np.linalg.norm(requested_velocity[:2]))
                )
                prepared = prepare_velocity_input(
                    requested_velocity,
                    effective_max_speed_cm_s=effective_max_speed,
                )
                action = SmoothWalkingAction(
                    desired_velocity_world_cm_s=prepared.desired_velocity_world_cm_s,
                    desired_facing_yaw_rad=math.radians(
                        float(action_record["desired_facing_yaw_deg"])
                    ),
                )
                parameters = held_parameters
                dt_s = float(transition["delta_time_s"])
            else:
                inputs = retrospective_nominal_inputs(transition)
                action = inputs.action
                parameters = inputs.parameters
                dt_s = inputs.dt_s
            current_action_key = _action_key(transition)
            if previous_action_key is not None and current_action_key != previous_action_key:
                action_change_count += 1
            previous_action_key = current_action_key
            scenario = transition.get("scenario")
            if scenario is not None and bool(scenario["collision_this_step"]):
                collision_step_count += 1
            perturbation = transition.get("external_perturbation")
            if perturbation is not None and perturbation["type"] == "additive_velocity":
                external_perturbation_step_count += 1

            prediction = smooth_walking_nominal_step(
                predicted_observable,
                predicted_internal,
                action,
                parameters=parameters,
                dt_s=dt_s,
            )
            predicted_observable = prediction.observable_next
            predicted_internal = prediction.internal_next
            elapsed_s += dt_s

            while (
                next_horizon_index < len(horizons)
                and elapsed_s + 1.0e-12 >= horizons[next_horizon_index]
            ):
                actual = observable_from_state_record(transition["next_state"])
                position_error = float(
                    np.linalg.norm(
                        predicted_observable.position_world_cm[:2] - actual.position_world_cm[:2]
                    )
                )
                velocity_error = float(
                    np.linalg.norm(
                        predicted_observable.velocity_world_cm_s[:2]
                        - actual.velocity_world_cm_s[:2]
                    )
                )
                results.append(
                    RecursiveRolloutMetrics(
                        start_transition_sequence=int(first_transition["transition_sequence"]),
                        end_transition_sequence=int(transition["transition_sequence"]),
                        requested_horizon_s=horizons[next_horizon_index],
                        actual_horizon_s=elapsed_s,
                        step_count=end_index - start_index + 1,
                        action_change_count=action_change_count,
                        collision_step_count=collision_step_count,
                        external_perturbation_step_count=external_perturbation_step_count,
                        perturbation_relation=(
                            "no_event"
                            if event_index is None
                            else "event_crossing"
                            if start_index <= event_index <= end_index
                            else "pre_event"
                            if end_index < event_index
                            else "post_event"
                        ),
                        planar_position_error_cm=position_error,
                        planar_velocity_error_cm_s=velocity_error,
                        yaw_error_deg=abs(
                            math.degrees(
                                find_delta_angle_radians(
                                    predicted_observable.facing_yaw_rad,
                                    actual.facing_yaw_rad,
                                )
                            )
                        ),
                        angular_velocity_yaw_error_deg_s=abs(
                            predicted_observable.angular_velocity_yaw_deg_s
                            - actual.angular_velocity_yaw_deg_s
                        ),
                    )
                )
                next_horizon_index += 1

            if next_horizon_index == len(horizons):
                break

    return tuple(results)
