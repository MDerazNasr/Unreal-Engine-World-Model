"""Teacher-forcing-free recursive rollout of a learned residual world model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from motionworld.dynamics.coordinates import YawRadians
from motionworld.dynamics.nominal_episode import (
    NominalTransitionInputs,
    current_snapshot_nominal_inputs,
    observable_from_state_record,
)
from motionworld.dynamics.smooth_walking_input import prepare_velocity_input
from motionworld.dynamics.smooth_walking_math import find_delta_angle_radians
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    smooth_walking_nominal_step,
)
from motionworld.models.residual_contract import ResidualCorrection, compose_residual
from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_LENGTH,
    encode_residual_step_features,
    stack_residual_history,
)
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.models.residual_training import predict_physical_residuals


@dataclass(frozen=True, slots=True)
class RecursiveResidualRolloutMetrics:
    """Endpoint error after every intermediate observable is model-predicted."""

    start_transition_sequence: int
    end_transition_sequence: int
    requested_horizon_s: float
    actual_horizon_s: float
    step_count: int
    action_change_count: int
    parameter_change_count: int
    planar_position_error_cm: float
    planar_velocity_error_cm_s: float
    yaw_error_deg: float
    angular_velocity_yaw_error_deg_s: float


def _action_key(transition: dict[str, Any]) -> tuple[float, ...]:
    action = transition["applied_action"]
    return tuple(float(value) for value in action["velocity_world_cm_per_s"]) + (
        float(action["desired_facing_yaw_deg"]),
    )


def _parameters_changed(transition: dict[str, Any]) -> bool:
    context = transition["nominal_context"]
    return bool(
        context["previous"]["parameters"]
        != context["parameters_observed_for_completed_step"]
        or context["previous"]["input_preparation"]
        != context["input_preparation_observed_for_completed_step"]
    )


def _held_action(
    transition: dict[str, Any],
    held_preparation: dict[str, Any],
) -> SmoothWalkingAction:
    action_record = transition["applied_action"]
    if "desired_facing_yaw_deg" not in action_record:
        raise ValueError("residual rollout requires schema-v4+ desired facing")
    requested_velocity = np.asarray(action_record["velocity_world_cm_per_s"], dtype=np.float64)
    effective_max_speed = (
        float(held_preparation["effective_max_speed_cm_per_s"])
        if held_preparation["has_max_move_speed"]
        else float(np.linalg.norm(requested_velocity[:2]))
    )
    prepared = prepare_velocity_input(
        requested_velocity,
        effective_max_speed_cm_s=effective_max_speed,
    )
    return SmoothWalkingAction(
        desired_velocity_world_cm_s=prepared.desired_velocity_world_cm_s,
        desired_facing_yaw_rad=math.radians(float(action_record["desired_facing_yaw_deg"])),
    )


def _correction(values: np.ndarray) -> ResidualCorrection:
    if values.shape != (6,):
        raise ValueError("residual model must return exactly six values")
    return ResidualCorrection(
        position_local_cm=values[0:2],
        velocity_local_cm_s=values[2:4],
        yaw_rad=float(values[4]),
        angular_velocity_yaw_rad_s=float(values[5]),
    )


def evaluate_recursive_residual_rollouts(
    transitions: list[dict[str, Any]],
    *,
    model: ResidualMLP,
    normalization: ResidualNormalization,
    history_length: int,
    horizons_s: tuple[float, ...] = (0.5, 1.0, 1.5),
) -> tuple[RecursiveResidualRolloutMetrics, ...]:
    """Evaluate held-parameter residual rollouts without intermediate real-state re-seeding.

    Recorded future actions and timesteps define the evaluation query. Parameters and max-speed
    preparation are read only from the rollout's initial current snapshot and held. Four-history
    rollouts seed three past real queries, then append predicted queries recursively.
    """

    if not transitions:
        raise ValueError("transitions must not be empty")
    if history_length not in (1, RESIDUAL_HISTORY_LENGTH):
        raise ValueError(f"history_length must be 1 or {RESIDUAL_HISTORY_LENGTH}")
    if history_length != normalization.history_length or model.input_width != (
        normalization.feature_width
    ):
        raise ValueError("model, normalization, and history schemas differ")
    horizons = tuple(sorted(float(value) for value in horizons_s))
    if not horizons or len(set(horizons)) != len(horizons):
        raise ValueError("horizons_s must contain distinct values")
    if any(not math.isfinite(value) or value <= 0.0 for value in horizons):
        raise ValueError("horizons_s must contain positive finite values")
    episode_duration_s = sum(float(row["delta_time_s"]) for row in transitions)
    if horizons[-1] > episode_duration_s + 1.0e-12:
        raise ValueError("largest requested horizon exceeds the complete episode duration")

    results: list[RecursiveResidualRolloutMetrics] = []
    for start_index in range(history_length - 1, len(transitions)):
        first_transition = transitions[start_index]
        initial = current_snapshot_nominal_inputs(first_transition)
        predicted_observable = initial.observable
        predicted_internal = initial.internal
        held_parameters = initial.parameters
        held_preparation = first_transition["nominal_context"]["previous"].get(
            "input_preparation"
        )
        if held_preparation is None:
            raise ValueError("residual rollout requires schema-v4+ input preparation")

        feature_history: list[np.ndarray] = []
        if history_length == RESIDUAL_HISTORY_LENGTH:
            for past_index in range(start_index - history_length + 1, start_index):
                past_inputs = current_snapshot_nominal_inputs(transitions[past_index])
                past_nominal = smooth_walking_nominal_step(
                    past_inputs.observable,
                    past_inputs.internal,
                    past_inputs.action,
                    parameters=past_inputs.parameters,
                    dt_s=past_inputs.dt_s,
                ).observable_next
                feature_history.append(
                    encode_residual_step_features(past_inputs, past_nominal)
                )

        elapsed_s = 0.0
        next_horizon_index = 0
        action_change_count = 0
        parameter_change_count = 0
        previous_action_key: tuple[float, ...] | None = None
        for end_index in range(start_index, len(transitions)):
            transition = transitions[end_index]
            action = _held_action(transition, held_preparation)
            dt_s = float(transition["delta_time_s"])
            inputs = NominalTransitionInputs(
                observable=predicted_observable,
                internal=predicted_internal,
                action=action,
                parameters=held_parameters,
                dt_s=dt_s,
            )
            nominal = smooth_walking_nominal_step(
                predicted_observable,
                predicted_internal,
                action,
                parameters=held_parameters,
                dt_s=dt_s,
            )
            step_features = encode_residual_step_features(inputs, nominal.observable_next)
            feature_history.append(step_features)
            if len(feature_history) > history_length:
                feature_history.pop(0)
            model_features = (
                step_features
                if history_length == 1
                else stack_residual_history(feature_history)
            )
            correction_values = predict_physical_residuals(
                model,
                normalization,
                model_features[np.newaxis, :],
            )[0]
            predicted_observable = compose_residual(
                nominal.observable_next,
                _correction(correction_values),
                reference_yaw=YawRadians(float(inputs.observable.facing_yaw_rad)),
            )
            predicted_internal = nominal.internal_next

            current_action_key = _action_key(transition)
            if previous_action_key is not None and current_action_key != previous_action_key:
                action_change_count += 1
            previous_action_key = current_action_key
            parameter_change_count += int(_parameters_changed(transition))
            elapsed_s += dt_s

            while (
                next_horizon_index < len(horizons)
                and elapsed_s + 1.0e-12 >= horizons[next_horizon_index]
            ):
                actual = observable_from_state_record(transition["next_state"])
                results.append(
                    RecursiveResidualRolloutMetrics(
                        start_transition_sequence=int(
                            first_transition["transition_sequence"]
                        ),
                        end_transition_sequence=int(transition["transition_sequence"]),
                        requested_horizon_s=horizons[next_horizon_index],
                        actual_horizon_s=elapsed_s,
                        step_count=end_index - start_index + 1,
                        action_change_count=action_change_count,
                        parameter_change_count=parameter_change_count,
                        planar_position_error_cm=float(
                            np.linalg.norm(
                                predicted_observable.position_world_cm[:2]
                                - actual.position_world_cm[:2]
                            )
                        ),
                        planar_velocity_error_cm_s=float(
                            np.linalg.norm(
                                predicted_observable.velocity_world_cm_s[:2]
                                - actual.velocity_world_cm_s[:2]
                            )
                        ),
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
