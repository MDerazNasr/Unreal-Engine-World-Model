"""Planar-yaw form of Unreal Engine 5.8 Smooth Walking facing dynamics.

Smooth Walking uses quaternion springs in Unreal.  For the project's planar
ground-motion boundary, all rotations are yaw-only, so the same shortest-arc
spring can be written as one wrapped angle.  This module keeps the desired facing
explicit; callers may not invent it from an unrecorded engine input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from motionworld.dynamics.smooth_walking_math import (
    critical_spring_damper_angle,
    find_delta_angle_radians,
)
from motionworld.dynamics.smooth_walking_velocity import (
    UE_FLOAT_EPSILON,
    SmoothWalkingParameters,
)


@dataclass(frozen=True, slots=True)
class SmoothWalkingFacingState:
    """Planar projection of Smooth Walking's two internal facing fields."""

    intermediate_facing_yaw_rad: float
    intermediate_angular_velocity_yaw_rad_s: float


@dataclass(frozen=True, slots=True)
class SmoothWalkingFacingStep:
    """Proposed angular velocity and internal state after one facing update."""

    proposed_angular_velocity_yaw_deg_s: float
    spring_updated_facing_yaw_rad: float
    state_next: SmoothWalkingFacingState
    facing_deadzone_active: bool


def _finite_angle(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def smooth_walking_facing_step(
    state: SmoothWalkingFacingState,
    *,
    current_facing_yaw_rad: float,
    actual_angular_velocity_yaw_deg_s: float,
    desired_facing_yaw_rad: float,
    parameters: SmoothWalkingParameters,
    dt_s: float,
) -> SmoothWalkingFacingStep:
    """Reproduce the yaw-only facing portion of UE 5.8 ``GenerateWalkMove``.

    ``spring_updated_facing_yaw_rad`` is the temporary ``UpdatedFacing`` used by
    Smooth Walking's spring and deadzone logic.  Walking simulation actually
    applies the returned angular velocity to the current orientation afterward.
    """

    intermediate_facing = _finite_angle(
        state.intermediate_facing_yaw_rad,
        name="state.intermediate_facing_yaw_rad",
    )
    intermediate_angular_velocity = _finite_angle(
        state.intermediate_angular_velocity_yaw_rad_s,
        name="state.intermediate_angular_velocity_yaw_rad_s",
    )
    current_facing = _finite_angle(current_facing_yaw_rad, name="current_facing_yaw_rad")
    current_angular_velocity = math.radians(
        _finite_angle(
            actual_angular_velocity_yaw_deg_s,
            name="actual_angular_velocity_yaw_deg_s",
        )
    )
    desired_facing = _finite_angle(desired_facing_yaw_rad, name="desired_facing_yaw_rad")
    timestep = _finite_angle(dt_s, name="dt_s")
    if timestep <= UE_FLOAT_EPSILON:
        raise ValueError(f"dt_s must be greater than Unreal float epsilon ({UE_FLOAT_EPSILON})")

    if parameters.smooth_facing_with_double_spring:
        intermediate_step = critical_spring_damper_angle(
            intermediate_facing,
            intermediate_angular_velocity,
            desired_facing,
            smoothing_time_s=parameters.facing_smoothing_time_s / 2.0,
            dt_s=timestep,
        )
        intermediate_facing = intermediate_step.angle_next_rad
        intermediate_angular_velocity = intermediate_step.angular_velocity_next_rad_s
        output_step = critical_spring_damper_angle(
            current_facing,
            current_angular_velocity,
            intermediate_facing,
            smoothing_time_s=parameters.facing_smoothing_time_s / 2.0,
            dt_s=timestep,
        )
    else:
        intermediate_facing = desired_facing
        intermediate_angular_velocity = current_angular_velocity
        output_step = critical_spring_damper_angle(
            current_facing,
            current_angular_velocity,
            desired_facing,
            smoothing_time_s=parameters.facing_smoothing_time_s,
            dt_s=timestep,
        )

    updated_facing = output_step.angle_next_rad
    proposed_angular_velocity = output_step.angular_velocity_next_rad_s
    facing_error = abs(find_delta_angle_radians(desired_facing, updated_facing))
    facing_deadzone_active = facing_error < math.radians(parameters.facing_deadzone_deg)
    if facing_deadzone_active:
        # Quaternion source computes the shortest current-to-updated rotation and
        # divides it by dt so Walking will apply exactly that small final motion.
        proposed_angular_velocity = (
            find_delta_angle_radians(current_facing, updated_facing) / timestep
        )
        intermediate_facing = desired_facing
        if abs(proposed_angular_velocity) < math.radians(
            parameters.angular_velocity_deadzone_deg_s
        ):
            intermediate_angular_velocity = 0.0

    return SmoothWalkingFacingStep(
        proposed_angular_velocity_yaw_deg_s=math.degrees(proposed_angular_velocity),
        spring_updated_facing_yaw_rad=updated_facing,
        state_next=SmoothWalkingFacingState(
            intermediate_facing_yaw_rad=intermediate_facing,
            intermediate_angular_velocity_yaw_rad_s=intermediate_angular_velocity,
        ),
        facing_deadzone_active=facing_deadzone_active,
    )
