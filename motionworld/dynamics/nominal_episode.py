"""Typed adapter from validated episode-schema-v3 rows to nominal dynamics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_input import prepare_velocity_input
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
    quaternion_xyzw_to_planar_yaw,
)
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
)


@dataclass(frozen=True, slots=True)
class NominalTransitionInputs:
    """Explicit inputs for retrospective one-step nominal evaluation."""

    observable: SmoothWalkingObservableState
    internal: SmoothWalkingInternalState
    action: SmoothWalkingAction
    parameters: SmoothWalkingParameters
    dt_s: float


def smooth_walking_parameters_from_record(record: dict[str, Any]) -> SmoothWalkingParameters:
    """Map the schema's completed-step parameter snapshot to model names."""

    return SmoothWalkingParameters(
        acceleration_cm_s2=record["acceleration_cm_per_s2"],
        deceleration_cm_s2=record["deceleration_cm_per_s2"],
        directional_acceleration_factor=record["directional_acceleration_factor"],
        turning_strength_s_inv=record["turning_strength"],
        acceleration_smoothing_time_s=record["acceleration_smoothing_time_s"],
        deceleration_smoothing_time_s=record["deceleration_smoothing_time_s"],
        acceleration_smoothing_compensation=record["acceleration_smoothing_compensation"],
        deceleration_smoothing_compensation=record["deceleration_smoothing_compensation"],
        velocity_deadzone_cm_s=record["velocity_deadzone_cm_per_s"],
        acceleration_deadzone_cm_s2=record["acceleration_deadzone_cm_per_s2"],
        outside_influence_smoothing_time_s=record["outside_influence_smoothing_time_s"],
        facing_smoothing_time_s=record["facing_smoothing_time_s"],
        smooth_facing_with_double_spring=record["smooth_facing_with_double_spring"],
        facing_deadzone_deg=record["facing_deadzone_deg"],
        angular_velocity_deadzone_deg_s=record["angular_velocity_deadzone_deg_per_s"],
    )


def observable_from_state_record(record: dict[str, Any]) -> SmoothWalkingObservableState:
    """Map one already-validated authoritative state to the nominal state type."""

    angular_velocity = record["angular_velocity_world_deg_per_s"]
    return SmoothWalkingObservableState(
        position_world_cm=np.asarray(record["position_world_cm"], dtype=np.float64),
        velocity_world_cm_s=np.asarray(
            record["velocity_world_cm_per_s"],
            dtype=np.float64,
        ),
        facing_yaw_rad=math.radians(float(record["facing_yaw_deg"])),
        angular_velocity_yaw_deg_s=float(angular_velocity[2]),
        simulation_time_s=float(record["simulation_time_s"]),
    )


def internal_from_context_record(record: dict[str, Any]) -> SmoothWalkingInternalState:
    """Map all five validated Smooth Walking hidden fields to the planar model."""

    internal = record["internal_state"]
    intermediate_angular_velocity = internal["intermediate_angular_velocity_world_rad_per_s"]
    return SmoothWalkingInternalState(
        velocity=SmoothWalkingVelocityState(
            spring_velocity_world_cm_s=np.asarray(
                internal["spring_velocity_world_cm_per_s"],
                dtype=np.float64,
            ),
            spring_acceleration_world_cm_s2=np.asarray(
                internal["spring_acceleration_world_cm_per_s2"],
                dtype=np.float64,
            ),
            intermediate_velocity_world_cm_s=np.asarray(
                internal["intermediate_velocity_world_cm_per_s"],
                dtype=np.float64,
            ),
        ),
        facing=SmoothWalkingFacingState(
            intermediate_facing_yaw_rad=quaternion_xyzw_to_planar_yaw(
                internal["intermediate_facing_world_xyzw"]
            ),
            intermediate_angular_velocity_yaw_rad_s=float(intermediate_angular_velocity[2]),
        ),
    )


def retrospective_nominal_inputs(
    transition: dict[str, Any],
    *,
    desired_facing_yaw_rad: float,
    effective_max_speed_cm_s: float,
) -> NominalTransitionInputs:
    """Build one-step inputs without inventing the unrecorded orientation intent.

    The schema explicitly labels ``parameters_observed_for_completed_step`` as
    retrospective.  It is correct for equation-parity evaluation, but a planner
    may use it only when the same parameter setting is known before its action.
    Desired facing remains an explicit caller argument because schema v3 records
    only desired velocity; silently deriving it would hide a causal assumption.
    """

    nominal_context = transition["nominal_context"]
    prepared_input = prepare_velocity_input(
        transition["applied_action"]["velocity_world_cm_per_s"],
        effective_max_speed_cm_s=effective_max_speed_cm_s,
    )
    return NominalTransitionInputs(
        observable=observable_from_state_record(transition["previous_state"]),
        internal=internal_from_context_record(nominal_context["previous"]),
        action=SmoothWalkingAction(
            desired_velocity_world_cm_s=prepared_input.desired_velocity_world_cm_s,
            desired_facing_yaw_rad=float(desired_facing_yaw_rad),
        ),
        parameters=smooth_walking_parameters_from_record(
            nominal_context["parameters_observed_for_completed_step"]
        ),
        dt_s=float(transition["delta_time_s"]),
    )
