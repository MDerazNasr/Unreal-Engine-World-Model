"""Faithful translational substep for Unreal Engine 5.8 Smooth Walking.

This module predicts the *proposed* velocity produced by ``GenerateWalkMove``.
It deliberately does not predict collision resolution: Unreal applies collision,
step-up, sliding, and external forces after this controller calculation.  Their
difference from the proposal is precisely part of the mismatch we will measure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from motionworld.dynamics.smooth_walking_math import (
    UE_KINDA_SMALL_NUMBER,
    UE_SMALL_NUMBER,
    critical_spring_damper,
    exponential_smoothing_approx,
    strength_to_smoothing_time,
)

UE_FLOAT_EPSILON = float(np.finfo(np.float32).eps)


def _finite_parameter(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _bounded_parameter(
    value: float,
    *,
    name: str,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> float:
    result = _finite_parameter(value, name=name)
    if result < minimum or (maximum is not None and result > maximum):
        interval = f"[{minimum}, {maximum}]" if maximum is not None else f">= {minimum}"
        raise ValueError(f"{name} must be {interval}")
    return result


@dataclass(frozen=True, slots=True)
class SmoothWalkingParameters:
    """Runtime parameters captured from the active Smooth Walking mode."""

    acceleration_cm_s2: float
    deceleration_cm_s2: float
    directional_acceleration_factor: float
    turning_strength_s_inv: float
    acceleration_smoothing_time_s: float
    deceleration_smoothing_time_s: float
    acceleration_smoothing_compensation: float
    deceleration_smoothing_compensation: float
    velocity_deadzone_cm_s: float
    acceleration_deadzone_cm_s2: float
    outside_influence_smoothing_time_s: float
    facing_smoothing_time_s: float
    smooth_facing_with_double_spring: bool
    facing_deadzone_deg: float
    angular_velocity_deadzone_deg_s: float

    def __post_init__(self) -> None:
        nonnegative = (
            "acceleration_cm_s2",
            "deceleration_cm_s2",
            "turning_strength_s_inv",
            "acceleration_smoothing_time_s",
            "deceleration_smoothing_time_s",
            "velocity_deadzone_cm_s",
            "acceleration_deadzone_cm_s2",
            "outside_influence_smoothing_time_s",
            "facing_smoothing_time_s",
            "facing_deadzone_deg",
            "angular_velocity_deadzone_deg_s",
        )
        for name in nonnegative:
            _bounded_parameter(getattr(self, name), name=name)
        for name in (
            "directional_acceleration_factor",
            "acceleration_smoothing_compensation",
            "deceleration_smoothing_compensation",
        ):
            _bounded_parameter(getattr(self, name), name=name, maximum=1.0)
        if not isinstance(self.smooth_facing_with_double_spring, bool):
            raise ValueError("smooth_facing_with_double_spring must be a boolean")


@dataclass(frozen=True, slots=True)
class SmoothWalkingVelocityState:
    """The three translational fields carried in ``FSmoothWalkingState``."""

    spring_velocity_world_cm_s: NDArray[np.float64]
    spring_acceleration_world_cm_s2: NDArray[np.float64]
    intermediate_velocity_world_cm_s: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class SmoothWalkingVelocityStep:
    """One proposed velocity and the hidden state needed by the next step."""

    proposed_velocity_world_cm_s: NDArray[np.float64]
    state_next: SmoothWalkingVelocityState
    is_accelerating: bool
    velocity_match: float
    desired_acceleration_world_cm_s2: NDArray[np.float64]
    track_velocity_world_cm_s: NDArray[np.float64]


def _vector3(value: ArrayLike, *, name: str) -> NDArray[np.float64]:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (3,):
        raise ValueError(f"{name} must have shape (3,)")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


def _safe_normal(vector: NDArray[np.float64]) -> NDArray[np.float64]:
    squared_length = float(vector @ vector)
    if squared_length < UE_SMALL_NUMBER:
        return np.zeros(3, dtype=np.float64)
    return vector / math.sqrt(squared_length)


def _clamp_to_max_size(
    vector: NDArray[np.float64],
    maximum_size: float,
) -> NDArray[np.float64]:
    if maximum_size < UE_KINDA_SMALL_NUMBER:
        return np.zeros(3, dtype=np.float64)
    squared_length = float(vector @ vector)
    if squared_length > maximum_size * maximum_size:
        return vector * (maximum_size / math.sqrt(squared_length))
    return vector


def _integrate_without_overshoot(
    intermediate_velocity: NDArray[np.float64],
    desired_velocity: NDArray[np.float64],
    desired_acceleration: NDArray[np.float64],
    interval_s: float,
    maximum_size: float,
) -> NDArray[np.float64]:
    difference = desired_velocity - intermediate_velocity
    acceleration_delta = desired_acceleration * interval_s
    if float(difference @ acceleration_delta) < float(difference @ difference):
        integrated = intermediate_velocity + acceleration_delta
    else:
        integrated = desired_velocity.copy()
    return _clamp_to_max_size(integrated, maximum_size)


def smooth_walking_velocity_step(
    state: SmoothWalkingVelocityState,
    *,
    actual_velocity_world_cm_s: ArrayLike,
    desired_velocity_world_cm_s: ArrayLike,
    parameters: SmoothWalkingParameters,
    dt_s: float,
) -> SmoothWalkingVelocityStep:
    """Reproduce the translational portion of UE 5.8 ``GenerateWalkMove``.

    ``actual_velocity_world_cm_s`` is the finalized velocity entering the step,
    not the previous requested action.  This distinction lets the controller
    react to collision or a push instead of pretending its last proposal happened.
    """

    spring_velocity_previous = _vector3(
        state.spring_velocity_world_cm_s,
        name="state.spring_velocity_world_cm_s",
    )
    spring_acceleration_previous = _vector3(
        state.spring_acceleration_world_cm_s2,
        name="state.spring_acceleration_world_cm_s2",
    )
    intermediate_velocity = _vector3(
        state.intermediate_velocity_world_cm_s,
        name="state.intermediate_velocity_world_cm_s",
    ).copy()
    actual_velocity = _vector3(actual_velocity_world_cm_s, name="actual_velocity_world_cm_s")
    desired_velocity = _vector3(desired_velocity_world_cm_s, name="desired_velocity_world_cm_s")
    timestep = _finite_parameter(dt_s, name="dt_s")
    if timestep <= UE_FLOAT_EPSILON:
        raise ValueError(f"dt_s must be greater than Unreal float epsilon ({UE_FLOAT_EPSILON})")

    length_product = float(
        np.linalg.norm(actual_velocity) * np.linalg.norm(spring_velocity_previous)
    )
    velocity_match = float(
        np.clip(
            (spring_velocity_previous @ actual_velocity) / max(length_product, UE_SMALL_NUMBER),
            0.0,
            1.0,
        )
    )

    # At an exact match Unreal calculates an infinite smoothing time, which makes
    # its decay factor exactly one.  The explicit branch avoids manufacturing an
    # infinity while preserving the same result.
    if velocity_match < 1.0:
        outside_smoothing_time = (
            parameters.outside_influence_smoothing_time_s + UE_KINDA_SMALL_NUMBER
        ) / (1.0 - velocity_match)
        intermediate_velocity = exponential_smoothing_approx(
            intermediate_velocity,
            actual_velocity,
            dt_s=timestep,
            smoothing_time_s=outside_smoothing_time,
        )

    spring_velocity = actual_velocity.copy()
    if parameters.turning_strength_s_inv > 0.0 and not np.all(
        np.abs(desired_velocity) <= UE_KINDA_SMALL_NUMBER
    ):
        turning_target = _safe_normal(desired_velocity) * np.linalg.norm(intermediate_velocity)
        intermediate_velocity = exponential_smoothing_approx(
            intermediate_velocity,
            turning_target,
            dt_s=timestep,
            smoothing_time_s=strength_to_smoothing_time(parameters.turning_strength_s_inv),
        )

    is_accelerating = bool(
        1.01 * float(desired_velocity @ desired_velocity) > float(spring_velocity @ spring_velocity)
    )
    if is_accelerating:
        lateral_magnitude = (
            1.0 - parameters.directional_acceleration_factor
        ) * parameters.acceleration_cm_s2
        directional_magnitude = (
            parameters.directional_acceleration_factor * parameters.acceleration_cm_s2
        )
        smoothing_time = parameters.acceleration_smoothing_time_s
        smoothing_compensation = parameters.acceleration_smoothing_compensation
    else:
        lateral_magnitude = parameters.deceleration_cm_s2
        directional_magnitude = 0.0
        smoothing_time = parameters.deceleration_smoothing_time_s
        smoothing_compensation = parameters.deceleration_smoothing_compensation

    previous_velocity_length = float(np.linalg.norm(intermediate_velocity))
    velocity_difference = desired_velocity - intermediate_velocity
    lateral_acceleration = _safe_normal(velocity_difference) * min(
        lateral_magnitude,
        float(np.linalg.norm(velocity_difference)) / max(timestep, UE_SMALL_NUMBER),
    )
    directional_acceleration = _safe_normal(desired_velocity) * directional_magnitude
    desired_acceleration = lateral_acceleration + directional_acceleration
    maximum_size = max(previous_velocity_length, float(np.linalg.norm(desired_velocity)))

    next_intermediate_velocity = _integrate_without_overshoot(
        intermediate_velocity,
        desired_velocity,
        desired_acceleration,
        timestep,
        maximum_size,
    )
    lag_seconds = timestep + smoothing_compensation * smoothing_time
    track_velocity = _integrate_without_overshoot(
        intermediate_velocity,
        desired_velocity,
        desired_acceleration,
        lag_seconds,
        maximum_size,
    )
    spring = critical_spring_damper(
        spring_velocity,
        spring_acceleration_previous,
        track_velocity,
        smoothing_time_s=smoothing_time,
        dt_s=timestep,
    )
    proposed_velocity = spring.value_next
    spring_acceleration = spring.velocity_next

    if float((desired_velocity - proposed_velocity) @ (desired_velocity - proposed_velocity)) < (
        parameters.velocity_deadzone_cm_s * parameters.velocity_deadzone_cm_s
    ):
        proposed_velocity = desired_velocity.copy()
        if float(spring_acceleration @ spring_acceleration) < (
            parameters.acceleration_deadzone_cm_s2 * parameters.acceleration_deadzone_cm_s2
        ):
            spring_acceleration = np.zeros(3, dtype=np.float64)

    state_next = SmoothWalkingVelocityState(
        spring_velocity_world_cm_s=proposed_velocity.copy(),
        spring_acceleration_world_cm_s2=spring_acceleration.copy(),
        intermediate_velocity_world_cm_s=next_intermediate_velocity.copy(),
    )
    return SmoothWalkingVelocityStep(
        proposed_velocity_world_cm_s=proposed_velocity.copy(),
        state_next=state_next,
        is_accelerating=is_accelerating,
        velocity_match=velocity_match,
        desired_acceleration_world_cm_s2=desired_acceleration.copy(),
        track_velocity_world_cm_s=track_velocity.copy(),
    )
