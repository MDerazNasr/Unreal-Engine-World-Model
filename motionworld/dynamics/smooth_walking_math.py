"""Small mathematical kernels used by Unreal 5.8 Smooth Walking.

These functions mirror the equations in ``FMath`` and ``SpringMath`` before we
compose them into a character transition.  Keeping this layer small gives us a
place to test the mathematics independently of movement logic, collisions, and
machine learning.

The implementation evaluates in NumPy float64 for research analysis.  It follows
the Unreal 5.8 equations and branch thresholds, but does not claim bit-for-bit
float32 identity until it is checked against C++ golden outputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

# Engine/Source/Runtime/Core/Public/Math/NumericLimits.h in Unreal Engine 5.8.
UE_SMALL_NUMBER = 1.0e-8
UE_KINDA_SMALL_NUMBER = 1.0e-4


@dataclass(frozen=True, slots=True)
class CriticalSpringStep:
    """The value and its rate after one critically damped spring step."""

    value_next: NDArray[np.float64]
    velocity_next: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class CriticalAngleSpringStep:
    """One wrapped angular spring step, with all quantities in radians."""

    angle_next_rad: float
    angular_velocity_next_rad_s: float


def _finite_nonnegative_scalar(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if result < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _finite_array(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    result = np.asarray(values, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


def inv_exp_approx(x: float) -> float:
    """Reproduce ``FMath::InvExpApprox(x)``, Epic's approximation of exp(-x).

    Smooth Walking only supplies non-negative ``x`` because it is a damping rate
    multiplied by elapsed time.  Rejecting negative values catches invalid time
    or smoothing parameters before they can create plausible-looking bad data.
    """

    argument = _finite_nonnegative_scalar(x, name="x")
    denominator = (
        1.0
        + 1.00746054 * argument
        + 0.45053901 * argument * argument
        + 0.25724632 * argument * argument * argument
    )
    return 1.0 / denominator


def exponential_smoothing_approx(
    value: ArrayLike,
    target: ArrayLike,
    *,
    dt_s: float,
    smoothing_time_s: float,
) -> NDArray[np.float64]:
    """Move a scalar or vector toward a target using Unreal's approximate damping.

    ``smoothing_time_s`` controls lag: a larger value changes more slowly.  Unreal
    snaps to the target when that time is at most ``UE_KINDA_SMALL_NUMBER``.
    """

    current = _finite_array(value, name="value")
    goal = _finite_array(target, name="target")
    if current.shape != goal.shape:
        raise ValueError("value and target must have equal shapes")
    timestep = _finite_nonnegative_scalar(dt_s, name="dt_s")
    smoothing_time = _finite_nonnegative_scalar(
        smoothing_time_s,
        name="smoothing_time_s",
    )

    if smoothing_time > UE_KINDA_SMALL_NUMBER:
        decay = inv_exp_approx(timestep / smoothing_time)
        return goal + (current - goal) * decay
    return goal.copy()


def smoothing_time_to_damping(smoothing_time_s: float) -> float:
    """Convert Epic's user-facing smoothing time into a spring damping rate."""

    smoothing_time = _finite_nonnegative_scalar(
        smoothing_time_s,
        name="smoothing_time_s",
    )
    return 4.0 / max(smoothing_time, UE_SMALL_NUMBER)


def strength_to_smoothing_time(strength_s_inv: float) -> float:
    """Convert Smooth Walking's turning strength into an exponential time scale."""

    strength = _finite_nonnegative_scalar(strength_s_inv, name="strength_s_inv")
    return 2.0 / max(strength, UE_SMALL_NUMBER)


def critical_spring_damper(
    value: ArrayLike,
    velocity: ArrayLike,
    target: ArrayLike,
    *,
    smoothing_time_s: float,
    dt_s: float,
) -> CriticalSpringStep:
    """Advance Unreal's non-oscillating spring for a scalar or vector value.

    Variable mapping to ``SpringMath::CriticalSpringDamper``:

    * ``value`` is ``InOutX``;
    * ``velocity`` is ``InOutV`` (the rate of ``value``);
    * ``target`` is ``TargetX``;
    * ``smoothing_time_s`` and ``dt_s`` use seconds.
    """

    current = _finite_array(value, name="value")
    current_velocity = _finite_array(velocity, name="velocity")
    goal = _finite_array(target, name="target")
    if current.shape != current_velocity.shape or current.shape != goal.shape:
        raise ValueError("value, velocity, and target must have equal shapes")
    smoothing_time = _finite_nonnegative_scalar(
        smoothing_time_s,
        name="smoothing_time_s",
    )
    timestep = _finite_nonnegative_scalar(dt_s, name="dt_s")

    if smoothing_time < UE_SMALL_NUMBER:
        return CriticalSpringStep(
            value_next=goal.copy(),
            velocity_next=np.zeros_like(current_velocity),
        )

    half_damping = smoothing_time_to_damping(smoothing_time) / 2.0
    displacement = current - goal
    combined_rate = current_velocity + displacement * half_damping
    decay = inv_exp_approx(half_damping * timestep)
    return CriticalSpringStep(
        value_next=decay * (displacement + combined_rate * timestep) + goal,
        velocity_next=decay * (current_velocity - combined_rate * half_damping * timestep),
    )


def find_delta_angle_radians(angle_a_rad: float, angle_b_rad: float) -> float:
    """Return Unreal's shortest signed delta ``angle_b - angle_a`` in [-pi, pi)."""

    angle_a = float(_finite_array(angle_a_rad, name="angle_a_rad"))
    angle_b = float(_finite_array(angle_b_rad, name="angle_b_rad"))
    return (angle_b - angle_a + math.pi) % math.tau - math.pi


def critical_spring_damper_angle(
    angle_rad: float,
    angular_velocity_rad_s: float,
    target_angle_rad: float,
    *,
    smoothing_time_s: float,
    dt_s: float,
) -> CriticalAngleSpringStep:
    """Advance Unreal's critical spring while taking the shortest angular path."""

    current_angle = float(_finite_array(angle_rad, name="angle_rad"))
    current_velocity = float(_finite_array(angular_velocity_rad_s, name="angular_velocity_rad_s"))
    target_angle = float(_finite_array(target_angle_rad, name="target_angle_rad"))
    smoothing_time = _finite_nonnegative_scalar(
        smoothing_time_s,
        name="smoothing_time_s",
    )
    timestep = _finite_nonnegative_scalar(dt_s, name="dt_s")

    if smoothing_time < UE_SMALL_NUMBER:
        return CriticalAngleSpringStep(
            angle_next_rad=target_angle,
            angular_velocity_next_rad_s=0.0,
        )

    half_damping = smoothing_time_to_damping(smoothing_time) / 2.0
    displacement = find_delta_angle_radians(target_angle, current_angle)
    combined_rate = current_velocity + displacement * half_damping
    decay = inv_exp_approx(half_damping * timestep)
    return CriticalAngleSpringStep(
        angle_next_rad=decay * (displacement + combined_rate * timestep) + target_angle,
        angular_velocity_next_rad_s=decay
        * (current_velocity - combined_rate * half_damping * timestep),
    )
