"""A transparent one-dimensional velocity-update teaching oracle.

This module is deliberately simpler than Unreal's Smooth Walking movement mode.
It exists to verify acceleration clamping, timestep handling, and trapezoidal
position integration before the faithful nominal model is implemented. A batch
represents independent scalar examples; it is not an elementwise 2D movement law.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class BoundedVelocityStep:
    """One scalar teaching-oracle transition with explicit physical units."""

    position_next_cm: float
    velocity_next_cm_s: float
    acceleration_cm_s2: float
    desired_velocity_limited_cm_s: float


@dataclass(frozen=True, slots=True)
class BoundedVelocityBatchStep:
    """Independent scalar transitions evaluated together with NumPy."""

    position_next_cm: NDArray[np.float64]
    velocity_next_cm_s: NDArray[np.float64]
    acceleration_cm_s2: NDArray[np.float64]
    desired_velocity_limited_cm_s: NDArray[np.float64]


def _finite_scalar(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _parameters(
    *,
    max_acceleration_cm_s2: float,
    dt_s: float,
    max_speed_cm_s: float | None,
) -> tuple[float, float, float | None]:
    acceleration = _finite_scalar(max_acceleration_cm_s2, name="max_acceleration_cm_s2")
    timestep = _finite_scalar(dt_s, name="dt_s")
    if acceleration < 0.0:
        raise ValueError("max_acceleration_cm_s2 must be non-negative")
    if timestep <= 0.0:
        raise ValueError("dt_s must be positive")

    speed = None
    if max_speed_cm_s is not None:
        speed = _finite_scalar(max_speed_cm_s, name="max_speed_cm_s")
        if speed <= 0.0:
            raise ValueError("max_speed_cm_s must be positive when provided")
    return acceleration, timestep, speed


def _finite_array(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 0:
        raise ValueError(f"{name} must be a non-scalar batch")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _calculate(
    position_cm: NDArray[np.float64],
    velocity_cm_s: NDArray[np.float64],
    desired_velocity_cm_s: NDArray[np.float64],
    *,
    max_acceleration_cm_s2: float,
    dt_s: float,
    max_speed_cm_s: float | None,
) -> BoundedVelocityBatchStep:
    limited_desired = desired_velocity_cm_s
    if max_speed_cm_s is not None:
        limited_desired = np.clip(desired_velocity_cm_s, -max_speed_cm_s, max_speed_cm_s)

    maximum_velocity_change = max_acceleration_cm_s2 * dt_s
    velocity_change = np.clip(
        limited_desired - velocity_cm_s,
        -maximum_velocity_change,
        maximum_velocity_change,
    )
    velocity_next = velocity_cm_s + velocity_change
    position_next = position_cm + 0.5 * (velocity_cm_s + velocity_next) * dt_s
    acceleration = velocity_change / dt_s
    return BoundedVelocityBatchStep(
        position_next_cm=position_next,
        velocity_next_cm_s=velocity_next,
        acceleration_cm_s2=acceleration,
        desired_velocity_limited_cm_s=limited_desired,
    )


def bounded_velocity_step(
    position_cm: float,
    velocity_cm_s: float,
    desired_velocity_cm_s: float,
    *,
    max_acceleration_cm_s2: float,
    dt_s: float,
    max_speed_cm_s: float | None = None,
) -> BoundedVelocityStep:
    """Advance one scalar state with bounded acceleration and average velocity.

    The optional speed limit clamps the requested target, not the observed current
    velocity. Therefore an external push above the limit decelerates physically
    instead of being erased by an instantaneous state clamp.
    """

    position = _finite_scalar(position_cm, name="position_cm")
    velocity = _finite_scalar(velocity_cm_s, name="velocity_cm_s")
    desired = _finite_scalar(desired_velocity_cm_s, name="desired_velocity_cm_s")
    acceleration, timestep, speed = _parameters(
        max_acceleration_cm_s2=max_acceleration_cm_s2,
        dt_s=dt_s,
        max_speed_cm_s=max_speed_cm_s,
    )
    batch = _calculate(
        np.asarray([position]),
        np.asarray([velocity]),
        np.asarray([desired]),
        max_acceleration_cm_s2=acceleration,
        dt_s=timestep,
        max_speed_cm_s=speed,
    )
    return BoundedVelocityStep(
        position_next_cm=float(batch.position_next_cm[0]),
        velocity_next_cm_s=float(batch.velocity_next_cm_s[0]),
        acceleration_cm_s2=float(batch.acceleration_cm_s2[0]),
        desired_velocity_limited_cm_s=float(batch.desired_velocity_limited_cm_s[0]),
    )


def bounded_velocity_step_batch(
    position_cm: ArrayLike,
    velocity_cm_s: ArrayLike,
    desired_velocity_cm_s: ArrayLike,
    *,
    max_acceleration_cm_s2: float,
    dt_s: float,
    max_speed_cm_s: float | None = None,
) -> BoundedVelocityBatchStep:
    """Advance same-shaped batches of independent scalar oracle states."""

    position = _finite_array(position_cm, name="position_cm")
    velocity = _finite_array(velocity_cm_s, name="velocity_cm_s")
    desired = _finite_array(desired_velocity_cm_s, name="desired_velocity_cm_s")
    if position.shape != velocity.shape or position.shape != desired.shape:
        raise ValueError("position, velocity, and desired velocity batches must have equal shapes")
    acceleration, timestep, speed = _parameters(
        max_acceleration_cm_s2=max_acceleration_cm_s2,
        dt_s=dt_s,
        max_speed_cm_s=max_speed_cm_s,
    )
    return _calculate(
        position,
        velocity,
        desired,
        max_acceleration_cm_s2=acceleration,
        dt_s=timestep,
        max_speed_cm_s=speed,
    )
