"""Typed planar residual target and composition for authoritative character state."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from motionworld.dynamics.coordinates import (
    YawRadians,
    local_vector_to_world,
    world_vector_to_local,
)
from motionworld.dynamics.smooth_walking_math import find_delta_angle_radians
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState


def _planar_vector(value: ArrayLike, *, name: str) -> NDArray[np.float64]:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (2,):
        raise ValueError(f"{name} must have shape (2,)")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    result = result.copy()
    result.setflags(write=False)
    return result


def _finite_scalar(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _state_vector(value: ArrayLike, *, name: str) -> NDArray[np.float64]:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (3,):
        raise ValueError(f"{name} must have shape (3,)")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


@dataclass(frozen=True, slots=True)
class ResidualCorrection:
    """Six model outputs, expressed relative to the previous observed facing.

    Position and velocity are planar local-frame corrections. Facing is a signed
    shortest-angle correction in radians. Yaw-rate correction is radians/second,
    even though the Unreal-facing nominal state stores degrees/second.
    """

    position_local_cm: NDArray[np.float64]
    velocity_local_cm_s: NDArray[np.float64]
    yaw_rad: float
    angular_velocity_yaw_rad_s: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "position_local_cm",
            _planar_vector(self.position_local_cm, name="position_local_cm"),
        )
        object.__setattr__(
            self,
            "velocity_local_cm_s",
            _planar_vector(self.velocity_local_cm_s, name="velocity_local_cm_s"),
        )
        object.__setattr__(self, "yaw_rad", _finite_scalar(self.yaw_rad, name="yaw_rad"))
        object.__setattr__(
            self,
            "angular_velocity_yaw_rad_s",
            _finite_scalar(
                self.angular_velocity_yaw_rad_s,
                name="angular_velocity_yaw_rad_s",
            ),
        )

    def as_array(self) -> NDArray[np.float64]:
        """Return the frozen feature order used by the learned output head."""

        return np.asarray(
            [
                *self.position_local_cm,
                *self.velocity_local_cm_s,
                self.yaw_rad,
                self.angular_velocity_yaw_rad_s,
            ],
            dtype=np.float64,
        )


def zero_residual() -> ResidualCorrection:
    """Return the semantic identity element for residual composition."""

    return ResidualCorrection(
        position_local_cm=np.zeros(2),
        velocity_local_cm_s=np.zeros(2),
        yaw_rad=0.0,
        angular_velocity_yaw_rad_s=0.0,
    )


def residual_difference(
    actual: SmoothWalkingObservableState,
    nominal: SmoothWalkingObservableState,
    *,
    reference_yaw: YawRadians,
    planar_tolerance: float = 1.0e-6,
) -> ResidualCorrection:
    """Compute ``actual - nominal`` without using actual next-facing as the frame."""

    actual_position = _state_vector(actual.position_world_cm, name="actual.position_world_cm")
    nominal_position = _state_vector(nominal.position_world_cm, name="nominal.position_world_cm")
    actual_velocity = _state_vector(actual.velocity_world_cm_s, name="actual.velocity_world_cm_s")
    nominal_velocity = _state_vector(
        nominal.velocity_world_cm_s,
        name="nominal.velocity_world_cm_s",
    )
    tolerance = _finite_scalar(planar_tolerance, name="planar_tolerance")
    if tolerance < 0.0:
        raise ValueError("planar_tolerance must be non-negative")
    if abs(actual_position[2] - nominal_position[2]) > tolerance:
        raise ValueError("vertical position mismatch is outside the planar residual contract")
    if abs(actual_velocity[2] - nominal_velocity[2]) > tolerance:
        raise ValueError("vertical velocity mismatch is outside the planar residual contract")
    actual_time = _finite_scalar(actual.simulation_time_s, name="actual.simulation_time_s")
    nominal_time = _finite_scalar(nominal.simulation_time_s, name="nominal.simulation_time_s")
    if abs(actual_time - nominal_time) > tolerance:
        raise ValueError("simulation-time mismatch cannot be corrected by the residual")
    actual_yaw = _finite_scalar(actual.facing_yaw_rad, name="actual.facing_yaw_rad")
    nominal_yaw = _finite_scalar(nominal.facing_yaw_rad, name="nominal.facing_yaw_rad")
    actual_yaw_rate_deg_s = _finite_scalar(
        actual.angular_velocity_yaw_deg_s,
        name="actual.angular_velocity_yaw_deg_s",
    )
    nominal_yaw_rate_deg_s = _finite_scalar(
        nominal.angular_velocity_yaw_deg_s,
        name="nominal.angular_velocity_yaw_deg_s",
    )
    return ResidualCorrection(
        position_local_cm=world_vector_to_local(
            actual_position[:2] - nominal_position[:2],
            yaw=reference_yaw,
        ),
        velocity_local_cm_s=world_vector_to_local(
            actual_velocity[:2] - nominal_velocity[:2],
            yaw=reference_yaw,
        ),
        yaw_rad=find_delta_angle_radians(nominal_yaw, actual_yaw),
        angular_velocity_yaw_rad_s=math.radians(
            actual_yaw_rate_deg_s - nominal_yaw_rate_deg_s
        ),
    )


def compose_residual(
    nominal: SmoothWalkingObservableState,
    residual: ResidualCorrection,
    *,
    reference_yaw: YawRadians,
) -> SmoothWalkingObservableState:
    """Add a valid local residual to a nominal planar state prediction."""

    nominal_position = _state_vector(nominal.position_world_cm, name="nominal.position_world_cm")
    nominal_velocity = _state_vector(
        nominal.velocity_world_cm_s,
        name="nominal.velocity_world_cm_s",
    )
    nominal_yaw = _finite_scalar(nominal.facing_yaw_rad, name="nominal.facing_yaw_rad")
    nominal_yaw_rate = _finite_scalar(
        nominal.angular_velocity_yaw_deg_s,
        name="nominal.angular_velocity_yaw_deg_s",
    )
    simulation_time = _finite_scalar(
        nominal.simulation_time_s,
        name="nominal.simulation_time_s",
    )
    if np.array_equal(residual.as_array(), np.zeros(6, dtype=np.float64)):
        return nominal
    position_world = nominal_position.copy()
    position_world[:2] += local_vector_to_world(
        residual.position_local_cm,
        yaw=reference_yaw,
    )
    velocity_world = nominal_velocity.copy()
    velocity_world[:2] += local_vector_to_world(
        residual.velocity_local_cm_s,
        yaw=reference_yaw,
    )
    return SmoothWalkingObservableState(
        position_world_cm=position_world,
        velocity_world_cm_s=velocity_world,
        facing_yaw_rad=find_delta_angle_radians(0.0, nominal_yaw + residual.yaw_rad),
        angular_velocity_yaw_deg_s=(
            nominal_yaw_rate + math.degrees(residual.angular_velocity_yaw_rad_s)
        ),
        simulation_time_s=simulation_time,
    )
