"""Composed free-space nominal transition for UE 5.8 Smooth Walking.

The transition ends at Unreal's proposed movement boundary.  It advances known
controller state and predicts free-space position/orientation, but it does not
duplicate WalkingMode's collision solver.  Comparing this proposal with the
finalized Unreal observation defines the measured nominal error.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from motionworld.dynamics.smooth_walking_facing import (
    SmoothWalkingFacingState,
    SmoothWalkingFacingStep,
    smooth_walking_facing_step,
)
from motionworld.dynamics.smooth_walking_math import find_delta_angle_radians
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
    SmoothWalkingVelocityStep,
    smooth_walking_velocity_step,
)


def _finite_scalar(value: float, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _vector3(value: ArrayLike, *, name: str) -> NDArray[np.float64]:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (3,):
        raise ValueError(f"{name} must have shape (3,)")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


@dataclass(frozen=True, slots=True)
class SmoothWalkingObservableState:
    """Authoritative fields needed by the planar nominal transition."""

    position_world_cm: NDArray[np.float64]
    velocity_world_cm_s: NDArray[np.float64]
    facing_yaw_rad: float
    angular_velocity_yaw_deg_s: float
    simulation_time_s: float


@dataclass(frozen=True, slots=True)
class SmoothWalkingInternalState:
    """All five known Smooth Walking fields at the planar project boundary."""

    velocity: SmoothWalkingVelocityState
    facing: SmoothWalkingFacingState


@dataclass(frozen=True, slots=True)
class SmoothWalkingAction:
    """Post-input-preparation world velocity and explicit world facing target."""

    desired_velocity_world_cm_s: NDArray[np.float64]
    desired_facing_yaw_rad: float


@dataclass(frozen=True, slots=True)
class SmoothWalkingNominalStep:
    """One free-space nominal transition plus inspectable substep diagnostics."""

    observable_next: SmoothWalkingObservableState
    internal_next: SmoothWalkingInternalState
    velocity_step: SmoothWalkingVelocityStep
    facing_step: SmoothWalkingFacingStep


@dataclass(frozen=True, slots=True)
class SmoothWalkingNominalBatchStep:
    """Independent nominal transitions evaluated under one explicit batch API."""

    steps: tuple[SmoothWalkingNominalStep, ...]

    @property
    def position_world_cm(self) -> NDArray[np.float64]:
        return np.stack([step.observable_next.position_world_cm for step in self.steps])

    @property
    def velocity_world_cm_s(self) -> NDArray[np.float64]:
        return np.stack([step.observable_next.velocity_world_cm_s for step in self.steps])

    @property
    def facing_yaw_rad(self) -> NDArray[np.float64]:
        return np.asarray([step.observable_next.facing_yaw_rad for step in self.steps])


def quaternion_xyzw_to_planar_yaw(
    quaternion_xyzw: ArrayLike,
    *,
    planar_tolerance: float = 1.0e-4,
) -> float:
    """Validate a unit yaw quaternion and convert it to a wrapped scalar yaw."""

    quaternion = np.asarray(quaternion_xyzw, dtype=np.float64)
    if quaternion.shape != (4,):
        raise ValueError("quaternion_xyzw must have shape (4,)")
    if not np.isfinite(quaternion).all():
        raise ValueError("quaternion_xyzw must contain only finite values")
    tolerance = _finite_scalar(planar_tolerance, name="planar_tolerance")
    if tolerance < 0.0:
        raise ValueError("planar_tolerance must be non-negative")
    norm = float(np.linalg.norm(quaternion))
    if abs(norm - 1.0) > tolerance:
        raise ValueError("quaternion_xyzw must have unit norm")
    x, y, z, w = quaternion
    if abs(x) > tolerance or abs(y) > tolerance:
        raise ValueError("quaternion_xyzw is outside the planar yaw boundary")
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return find_delta_angle_radians(0.0, yaw)


def planar_yaw_to_quaternion_xyzw(yaw_rad: float) -> NDArray[np.float64]:
    """Convert a finite planar yaw to Unreal's quaternion component order."""

    yaw = _finite_scalar(yaw_rad, name="yaw_rad")
    half_yaw = 0.5 * yaw
    return np.asarray([0.0, 0.0, math.sin(half_yaw), math.cos(half_yaw)])


def smooth_walking_nominal_step(
    observable: SmoothWalkingObservableState,
    internal: SmoothWalkingInternalState,
    action: SmoothWalkingAction,
    *,
    parameters: SmoothWalkingParameters,
    dt_s: float,
) -> SmoothWalkingNominalStep:
    """Advance one proposed Smooth Walking step before environmental collision."""

    position = _vector3(observable.position_world_cm, name="observable.position_world_cm")
    actual_velocity = _vector3(
        observable.velocity_world_cm_s,
        name="observable.velocity_world_cm_s",
    )
    facing_yaw = _finite_scalar(observable.facing_yaw_rad, name="observable.facing_yaw_rad")
    angular_velocity = _finite_scalar(
        observable.angular_velocity_yaw_deg_s,
        name="observable.angular_velocity_yaw_deg_s",
    )
    simulation_time = _finite_scalar(
        observable.simulation_time_s,
        name="observable.simulation_time_s",
    )
    desired_velocity = _vector3(
        action.desired_velocity_world_cm_s,
        name="action.desired_velocity_world_cm_s",
    )
    desired_facing = _finite_scalar(
        action.desired_facing_yaw_rad,
        name="action.desired_facing_yaw_rad",
    )
    timestep = _finite_scalar(dt_s, name="dt_s")

    velocity_step = smooth_walking_velocity_step(
        internal.velocity,
        actual_velocity_world_cm_s=actual_velocity,
        desired_velocity_world_cm_s=desired_velocity,
        parameters=parameters,
        dt_s=timestep,
    )
    facing_step = smooth_walking_facing_step(
        internal.facing,
        current_facing_yaw_rad=facing_yaw,
        actual_angular_velocity_yaw_deg_s=angular_velocity,
        desired_facing_yaw_rad=desired_facing,
        parameters=parameters,
        dt_s=timestep,
    )

    proposed_velocity = velocity_step.proposed_velocity_world_cm_s
    proposed_angular_velocity = facing_step.proposed_angular_velocity_yaw_deg_s
    position_next = position + proposed_velocity * timestep
    facing_next = find_delta_angle_radians(
        0.0,
        facing_yaw + math.radians(proposed_angular_velocity) * timestep,
    )
    observable_next = SmoothWalkingObservableState(
        position_world_cm=position_next,
        velocity_world_cm_s=proposed_velocity.copy(),
        facing_yaw_rad=facing_next,
        angular_velocity_yaw_deg_s=proposed_angular_velocity,
        simulation_time_s=simulation_time + timestep,
    )
    internal_next = SmoothWalkingInternalState(
        velocity=velocity_step.state_next,
        facing=facing_step.state_next,
    )
    return SmoothWalkingNominalStep(
        observable_next=observable_next,
        internal_next=internal_next,
        velocity_step=velocity_step,
        facing_step=facing_step,
    )


def smooth_walking_nominal_step_batch(
    observables: Sequence[SmoothWalkingObservableState],
    internals: Sequence[SmoothWalkingInternalState],
    actions: Sequence[SmoothWalkingAction],
    *,
    parameters: Sequence[SmoothWalkingParameters],
    dt_s: Sequence[float],
) -> SmoothWalkingNominalBatchStep:
    """Evaluate equal-length independent transitions with scalar-reference parity.

    This correctness-first batch API intentionally calls the verified scalar
    transition.  A later profiling gate may vectorize it without changing its
    interface or mathematical reference behavior.
    """

    batch_size = len(observables)
    lengths = {
        "internals": len(internals),
        "actions": len(actions),
        "parameters": len(parameters),
        "dt_s": len(dt_s),
    }
    mismatched = {name: length for name, length in lengths.items() if length != batch_size}
    if mismatched:
        raise ValueError(f"batch fields must have equal lengths; mismatched={mismatched}")
    if batch_size == 0:
        raise ValueError("batch must not be empty")

    return SmoothWalkingNominalBatchStep(
        steps=tuple(
            smooth_walking_nominal_step(
                observable,
                internal,
                action,
                parameters=parameter,
                dt_s=timestep,
            )
            for observable, internal, action, parameter, timestep in zip(
                observables,
                internals,
                actions,
                parameters,
                dt_s,
                strict=True,
            )
        )
    )
