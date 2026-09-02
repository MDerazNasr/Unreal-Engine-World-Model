"""Causal, frame-invariant input features for the planar residual model."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from motionworld.dynamics.coordinates import YawRadians, world_vector_to_local
from motionworld.dynamics.nominal_episode import NominalTransitionInputs
from motionworld.dynamics.smooth_walking_math import find_delta_angle_radians
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState

RESIDUAL_FEATURE_SCHEMA_VERSION = 1
RESIDUAL_HISTORY_LENGTH = 4

_DYNAMIC_FEATURE_NAMES = (
    "state.velocity_local_x_cm_s",
    "state.velocity_local_y_cm_s",
    "state.yaw_rate_rad_s",
    "action.desired_velocity_local_x_cm_s",
    "action.desired_velocity_local_y_cm_s",
    "action.desired_facing_delta_rad",
    "nominal.position_delta_local_x_cm",
    "nominal.position_delta_local_y_cm",
    "nominal.velocity_local_x_cm_s",
    "nominal.velocity_local_y_cm_s",
    "nominal.facing_delta_rad",
    "nominal.yaw_rate_rad_s",
    "delta_time_s",
)

_PARAMETER_FEATURE_NAMES = (
    "parameters.acceleration_cm_s2",
    "parameters.deceleration_cm_s2",
    "parameters.directional_acceleration_factor",
    "parameters.turning_strength_s_inv",
    "parameters.acceleration_smoothing_time_s",
    "parameters.deceleration_smoothing_time_s",
    "parameters.acceleration_smoothing_compensation",
    "parameters.deceleration_smoothing_compensation",
    "parameters.velocity_deadzone_cm_s",
    "parameters.acceleration_deadzone_cm_s2",
    "parameters.outside_influence_smoothing_time_s",
    "parameters.facing_smoothing_time_s",
    "parameters.smooth_facing_with_double_spring",
    "parameters.facing_deadzone_rad",
    "parameters.angular_velocity_deadzone_rad_s",
)

RESIDUAL_STEP_FEATURE_NAMES = _DYNAMIC_FEATURE_NAMES + _PARAMETER_FEATURE_NAMES
RESIDUAL_STEP_FEATURE_COUNT = len(RESIDUAL_STEP_FEATURE_NAMES)
RESIDUAL_HISTORY_FEATURE_COUNT = RESIDUAL_HISTORY_LENGTH * RESIDUAL_STEP_FEATURE_COUNT


def _freeze_finite_vector(values: Sequence[float], *, expected: int) -> NDArray[np.float64]:
    result = np.asarray(values, dtype=np.float64)
    if result.shape != (expected,):
        raise ValueError(f"feature vector must have shape ({expected},)")
    if not np.isfinite(result).all():
        raise ValueError("feature vector must contain only finite values")
    result.setflags(write=False)
    return result


def encode_residual_step_features(
    inputs: NominalTransitionInputs,
    nominal_next: SmoothWalkingObservableState,
) -> NDArray[np.float64]:
    """Encode one causal transition query relative to its observed facing.

    ``nominal_next`` must have been computed from ``inputs``. The encoder never
    receives the actual next state, scenario target, obstacle, event label, or a
    parameter snapshot observed after the queried transition.
    """

    state = inputs.observable
    yaw = YawRadians(float(state.facing_yaw_rad))
    state_velocity_local = world_vector_to_local(state.velocity_world_cm_s[:2], yaw=yaw)
    action_velocity_local = world_vector_to_local(
        inputs.action.desired_velocity_world_cm_s[:2],
        yaw=yaw,
    )
    nominal_position_delta_local = world_vector_to_local(
        nominal_next.position_world_cm[:2] - state.position_world_cm[:2],
        yaw=yaw,
    )
    nominal_velocity_local = world_vector_to_local(
        nominal_next.velocity_world_cm_s[:2],
        yaw=yaw,
    )
    expected_time = float(state.simulation_time_s) + float(inputs.dt_s)
    if not math.isclose(
        float(nominal_next.simulation_time_s),
        expected_time,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise ValueError("nominal_next simulation time is not aligned with inputs")

    parameters = inputs.parameters
    values = (
        *state_velocity_local,
        math.radians(float(state.angular_velocity_yaw_deg_s)),
        *action_velocity_local,
        find_delta_angle_radians(
            float(state.facing_yaw_rad),
            float(inputs.action.desired_facing_yaw_rad),
        ),
        *nominal_position_delta_local,
        *nominal_velocity_local,
        find_delta_angle_radians(
            float(state.facing_yaw_rad),
            float(nominal_next.facing_yaw_rad),
        ),
        math.radians(float(nominal_next.angular_velocity_yaw_deg_s)),
        float(inputs.dt_s),
        float(parameters.acceleration_cm_s2),
        float(parameters.deceleration_cm_s2),
        float(parameters.directional_acceleration_factor),
        float(parameters.turning_strength_s_inv),
        float(parameters.acceleration_smoothing_time_s),
        float(parameters.deceleration_smoothing_time_s),
        float(parameters.acceleration_smoothing_compensation),
        float(parameters.deceleration_smoothing_compensation),
        float(parameters.velocity_deadzone_cm_s),
        float(parameters.acceleration_deadzone_cm_s2),
        float(parameters.outside_influence_smoothing_time_s),
        float(parameters.facing_smoothing_time_s),
        float(parameters.smooth_facing_with_double_spring),
        math.radians(float(parameters.facing_deadzone_deg)),
        math.radians(float(parameters.angular_velocity_deadzone_deg_s)),
    )
    return _freeze_finite_vector(values, expected=RESIDUAL_STEP_FEATURE_COUNT)


def stack_residual_history(
    chronological_steps: Sequence[NDArray[np.float64]],
) -> NDArray[np.float64]:
    """Flatten exactly four consecutive steps from oldest to current."""

    if len(chronological_steps) != RESIDUAL_HISTORY_LENGTH:
        raise ValueError(
            f"history requires exactly {RESIDUAL_HISTORY_LENGTH} chronological steps"
        )
    validated = [
        _freeze_finite_vector(step, expected=RESIDUAL_STEP_FEATURE_COUNT)
        for step in chronological_steps
    ]
    return _freeze_finite_vector(
        np.concatenate(validated),
        expected=RESIDUAL_HISTORY_FEATURE_COUNT,
    )
