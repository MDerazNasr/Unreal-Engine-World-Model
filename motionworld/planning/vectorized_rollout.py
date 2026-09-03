"""Vectorized planner rollout with scalar-reference parity tests."""

from __future__ import annotations

import math

import numpy as np

from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_math import UE_KINDA_SMALL_NUMBER, UE_SMALL_NUMBER
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
)
from motionworld.dynamics.smooth_walking_velocity import SmoothWalkingVelocityState
from motionworld.models.residual_features import RESIDUAL_STEP_FEATURE_COUNT
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.models.residual_training import predict_physical_residuals
from motionworld.planning.cem import project_velocity_actions
from motionworld.planning.planner_rollout import (
    FloatArray,
    PlannerRollout,
    PlannerRolloutConfig,
    PlannerSnapshot,
)


def _wrap_angle(value: FloatArray) -> FloatArray:
    return (value + math.pi) % math.tau - math.pi


def _safe_normal(value: FloatArray) -> FloatArray:
    squared = np.sum(np.square(value), axis=1)
    denominator = np.sqrt(np.where(squared < UE_SMALL_NUMBER, 1.0, squared))
    return np.where((squared < UE_SMALL_NUMBER)[:, None], 0.0, value / denominator[:, None])


def _inv_exp_approx(value: FloatArray) -> FloatArray:
    return 1.0 / (1.0 + 1.00746054 * value + 0.45053901 * value**2 + 0.25724632 * value**3)


def _exponential_smoothing(
    value: FloatArray,
    target: FloatArray,
    *,
    dt_s: float,
    smoothing_time_s: FloatArray,
) -> FloatArray:
    active = smoothing_time_s > UE_KINDA_SMALL_NUMBER
    safe_time = np.where(active, smoothing_time_s, 1.0)
    decay = _inv_exp_approx(dt_s / safe_time)
    smoothed = target + (value - target) * decay[:, None]
    return np.where(active[:, None], smoothed, target)


def _clamp_to_max_size(value: FloatArray, maximum_size: FloatArray) -> FloatArray:
    squared = np.sum(np.square(value), axis=1)
    active = (maximum_size >= UE_KINDA_SMALL_NUMBER) & (squared > maximum_size**2)
    denominator = np.sqrt(np.where(squared > 0.0, squared, 1.0))
    scale = maximum_size / denominator
    result = np.where(active[:, None], value * scale[:, None], value)
    return np.where((maximum_size < UE_KINDA_SMALL_NUMBER)[:, None], 0.0, result)


def _integrate_without_overshoot(
    intermediate_velocity: FloatArray,
    desired_velocity: FloatArray,
    desired_acceleration: FloatArray,
    *,
    interval_s: FloatArray,
    maximum_size: FloatArray,
) -> FloatArray:
    difference = desired_velocity - intermediate_velocity
    acceleration_delta = desired_acceleration * interval_s[:, None]
    integrate = np.sum(difference * acceleration_delta, axis=1) < np.sum(
        np.square(difference), axis=1
    )
    value = np.where(
        integrate[:, None],
        intermediate_velocity + acceleration_delta,
        desired_velocity,
    )
    return _clamp_to_max_size(value, maximum_size)


def _critical_spring_vector(
    value: FloatArray,
    velocity: FloatArray,
    target: FloatArray,
    *,
    smoothing_time_s: FloatArray,
    dt_s: float,
) -> tuple[FloatArray, FloatArray]:
    active = smoothing_time_s >= UE_SMALL_NUMBER
    safe_time = np.where(active, smoothing_time_s, 1.0)
    half_damping = 2.0 / np.maximum(safe_time, UE_SMALL_NUMBER)
    displacement = value - target
    combined_rate = velocity + displacement * half_damping[:, None]
    decay = _inv_exp_approx(half_damping * dt_s)
    value_next = decay[:, None] * (displacement + combined_rate * dt_s) + target
    velocity_next = decay[:, None] * (velocity - combined_rate * half_damping[:, None] * dt_s)
    return (
        np.where(active[:, None], value_next, target),
        np.where(active[:, None], velocity_next, 0.0),
    )


def _critical_spring_angle(
    angle: FloatArray,
    angular_velocity: FloatArray,
    target: FloatArray,
    *,
    smoothing_time_s: float,
    dt_s: float,
) -> tuple[FloatArray, FloatArray]:
    if smoothing_time_s < UE_SMALL_NUMBER:
        return target.copy(), np.zeros_like(angular_velocity)
    half_damping = 2.0 / max(smoothing_time_s, UE_SMALL_NUMBER)
    displacement = _wrap_angle(angle - target)
    combined_rate = angular_velocity + displacement * half_damping
    decay = float(_inv_exp_approx(np.asarray([half_damping * dt_s]))[0])
    return (
        decay * (displacement + combined_rate * dt_s) + target,
        decay * (angular_velocity - combined_rate * half_damping * dt_s),
    )


def _world_from_local(value: FloatArray, yaw: FloatArray) -> FloatArray:
    cosine = np.cos(yaw)
    sine = np.sin(yaw)
    return np.column_stack(
        (value[:, 0] * cosine - value[:, 1] * sine, value[:, 0] * sine + value[:, 1] * cosine)
    )


def _local_from_world(value: FloatArray, yaw: FloatArray) -> FloatArray:
    cosine = np.cos(yaw)
    sine = np.sin(yaw)
    return np.column_stack(
        (value[:, 0] * cosine + value[:, 1] * sine, -value[:, 0] * sine + value[:, 1] * cosine)
    )


def _parameter_features(snapshot: PlannerSnapshot, candidate_count: int) -> FloatArray:
    parameters = snapshot.parameters
    values = np.asarray(
        [
            parameters.acceleration_cm_s2,
            parameters.deceleration_cm_s2,
            parameters.directional_acceleration_factor,
            parameters.turning_strength_s_inv,
            parameters.acceleration_smoothing_time_s,
            parameters.deceleration_smoothing_time_s,
            parameters.acceleration_smoothing_compensation,
            parameters.deceleration_smoothing_compensation,
            parameters.velocity_deadzone_cm_s,
            parameters.acceleration_deadzone_cm_s2,
            parameters.outside_influence_smoothing_time_s,
            parameters.facing_smoothing_time_s,
            float(parameters.smooth_facing_with_double_spring),
            math.radians(parameters.facing_deadzone_deg),
            math.radians(parameters.angular_velocity_deadzone_deg_s),
        ],
        dtype=np.float64,
    )
    return np.broadcast_to(values, (candidate_count, len(values)))


def rollout_action_candidates_vectorized(
    snapshot: PlannerSnapshot,
    actions_local_cm_s: FloatArray,
    *,
    config: PlannerRolloutConfig,
    residual_model: ResidualMLP | None = None,
    residual_normalization: ResidualNormalization | None = None,
) -> PlannerRollout:
    """Roll candidates in arrays; the scalar rollout remains the mathematical oracle."""

    actions = np.asarray(actions_local_cm_s, dtype=np.float64)
    if actions.ndim != 3 or actions.shape[0] == 0 or actions.shape[1] == 0 or actions.shape[2] != 2:
        raise ValueError("candidate actions must have shape [candidate, plan_step, 2]")
    if not np.all(np.isfinite(actions)):
        raise ValueError("candidate actions must contain only finite values")
    if (residual_model is None) != (residual_normalization is None):
        raise ValueError("residual model and normalization must be supplied together")
    if residual_model is not None and (
        residual_model.input_width != RESIDUAL_STEP_FEATURE_COUNT
        or residual_normalization is None
        or residual_normalization.history_length != 1
        or residual_normalization.feature_width != residual_model.input_width
    ):
        raise ValueError("planner supports only a schema-matched no-history residual model")

    candidate_count, plan_step_count, _ = actions.shape
    parameters = snapshot.parameters
    dt_s = config.dynamics_dt_s
    position = np.broadcast_to(
        np.asarray(snapshot.observable.position_world_cm, dtype=np.float64),
        (candidate_count, 3),
    ).copy()
    velocity = np.broadcast_to(
        np.asarray(snapshot.observable.velocity_world_cm_s, dtype=np.float64),
        (candidate_count, 3),
    ).copy()
    facing = np.full(candidate_count, snapshot.observable.facing_yaw_rad, dtype=np.float64)
    yaw_rate_deg_s = np.full(
        candidate_count,
        snapshot.observable.angular_velocity_yaw_deg_s,
        dtype=np.float64,
    )
    simulation_time = np.full(
        candidate_count,
        snapshot.observable.simulation_time_s,
        dtype=np.float64,
    )
    spring_velocity = np.broadcast_to(
        snapshot.internal.velocity.spring_velocity_world_cm_s,
        (candidate_count, 3),
    ).copy()
    spring_acceleration = np.broadcast_to(
        snapshot.internal.velocity.spring_acceleration_world_cm_s2,
        (candidate_count, 3),
    ).copy()
    intermediate_velocity = np.broadcast_to(
        snapshot.internal.velocity.intermediate_velocity_world_cm_s,
        (candidate_count, 3),
    ).copy()
    intermediate_facing = np.full(
        candidate_count,
        snapshot.internal.facing.intermediate_facing_yaw_rad,
        dtype=np.float64,
    )
    intermediate_yaw_rate = np.full(
        candidate_count,
        snapshot.internal.facing.intermediate_angular_velocity_yaw_rad_s,
        dtype=np.float64,
    )
    output_positions = np.empty((candidate_count, plan_step_count, 2), dtype=np.float64)
    output_velocities = np.empty_like(output_positions)
    output_facing = np.empty((candidate_count, plan_step_count), dtype=np.float64)
    output_yaw_rate = np.empty_like(output_facing)
    parameter_features = _parameter_features(snapshot, candidate_count)

    for plan_step in range(plan_step_count):
        bounded_local = project_velocity_actions(
            actions[:, plan_step, :],
            maximum_speed_cm_s=snapshot.effective_max_speed_cm_s,
        )
        for _ in range(config.dynamics_substeps_per_plan_step):
            previous_position = position
            previous_velocity = velocity
            previous_facing = facing
            previous_yaw_rate = yaw_rate_deg_s
            desired_planar = _world_from_local(bounded_local, previous_facing)
            desired_velocity = np.column_stack((desired_planar, np.zeros(candidate_count)))
            nonzero_action = np.linalg.norm(bounded_local, axis=1) > 1.0e-12
            desired_facing = np.where(
                nonzero_action,
                np.arctan2(desired_planar[:, 1], desired_planar[:, 0]),
                previous_facing,
            )

            length_product = np.linalg.norm(previous_velocity, axis=1) * np.linalg.norm(
                spring_velocity, axis=1
            )
            velocity_match = np.clip(
                np.sum(spring_velocity * previous_velocity, axis=1)
                / np.maximum(length_product, UE_SMALL_NUMBER),
                0.0,
                1.0,
            )
            match_active = velocity_match < 1.0
            outside_time = (
                parameters.outside_influence_smoothing_time_s + UE_KINDA_SMALL_NUMBER
            ) / np.where(match_active, 1.0 - velocity_match, 1.0)
            matched_intermediate = _exponential_smoothing(
                intermediate_velocity,
                previous_velocity,
                dt_s=dt_s,
                smoothing_time_s=outside_time,
            )
            intermediate_velocity = np.where(
                match_active[:, None], matched_intermediate, intermediate_velocity
            )

            if parameters.turning_strength_s_inv > 0.0:
                turning_active = np.any(
                    np.abs(desired_velocity) > UE_KINDA_SMALL_NUMBER,
                    axis=1,
                )
                turning_target = (
                    _safe_normal(desired_velocity)
                    * np.linalg.norm(intermediate_velocity, axis=1)[:, None]
                )
                turn_time = np.full(
                    candidate_count,
                    2.0 / max(parameters.turning_strength_s_inv, UE_SMALL_NUMBER),
                )
                turned = _exponential_smoothing(
                    intermediate_velocity,
                    turning_target,
                    dt_s=dt_s,
                    smoothing_time_s=turn_time,
                )
                intermediate_velocity = np.where(
                    turning_active[:, None], turned, intermediate_velocity
                )

            accelerating = 1.01 * np.sum(np.square(desired_velocity), axis=1) > np.sum(
                np.square(previous_velocity), axis=1
            )
            lateral_magnitude = np.where(
                accelerating,
                (1.0 - parameters.directional_acceleration_factor) * parameters.acceleration_cm_s2,
                parameters.deceleration_cm_s2,
            )
            directional_magnitude = np.where(
                accelerating,
                parameters.directional_acceleration_factor * parameters.acceleration_cm_s2,
                0.0,
            )
            smoothing_time = np.where(
                accelerating,
                parameters.acceleration_smoothing_time_s,
                parameters.deceleration_smoothing_time_s,
            )
            smoothing_compensation = np.where(
                accelerating,
                parameters.acceleration_smoothing_compensation,
                parameters.deceleration_smoothing_compensation,
            )
            velocity_difference = desired_velocity - intermediate_velocity
            lateral_limit = np.minimum(
                lateral_magnitude,
                np.linalg.norm(velocity_difference, axis=1) / max(dt_s, UE_SMALL_NUMBER),
            )
            desired_acceleration = (
                _safe_normal(velocity_difference) * lateral_limit[:, None]
                + _safe_normal(desired_velocity) * directional_magnitude[:, None]
            )
            maximum_size = np.maximum(
                np.linalg.norm(intermediate_velocity, axis=1),
                np.linalg.norm(desired_velocity, axis=1),
            )
            next_intermediate = _integrate_without_overshoot(
                intermediate_velocity,
                desired_velocity,
                desired_acceleration,
                interval_s=np.full(candidate_count, dt_s),
                maximum_size=maximum_size,
            )
            track_velocity = _integrate_without_overshoot(
                intermediate_velocity,
                desired_velocity,
                desired_acceleration,
                interval_s=dt_s + smoothing_compensation * smoothing_time,
                maximum_size=maximum_size,
            )
            proposed_velocity, next_spring_acceleration = _critical_spring_vector(
                previous_velocity,
                spring_acceleration,
                track_velocity,
                smoothing_time_s=smoothing_time,
                dt_s=dt_s,
            )
            velocity_deadzone = (
                np.sum(np.square(desired_velocity - proposed_velocity), axis=1)
                < parameters.velocity_deadzone_cm_s**2
            )
            proposed_velocity = np.where(
                velocity_deadzone[:, None], desired_velocity, proposed_velocity
            )
            acceleration_deadzone = (
                np.sum(np.square(next_spring_acceleration), axis=1)
                < parameters.acceleration_deadzone_cm_s2**2
            )
            next_spring_acceleration = np.where(
                (velocity_deadzone & acceleration_deadzone)[:, None],
                0.0,
                next_spring_acceleration,
            )

            current_yaw_rate = np.radians(previous_yaw_rate)
            if parameters.smooth_facing_with_double_spring:
                intermediate_facing, intermediate_yaw_rate = _critical_spring_angle(
                    intermediate_facing,
                    intermediate_yaw_rate,
                    desired_facing,
                    smoothing_time_s=parameters.facing_smoothing_time_s / 2.0,
                    dt_s=dt_s,
                )
                updated_facing, proposed_yaw_rate = _critical_spring_angle(
                    previous_facing,
                    current_yaw_rate,
                    intermediate_facing,
                    smoothing_time_s=parameters.facing_smoothing_time_s / 2.0,
                    dt_s=dt_s,
                )
            else:
                intermediate_facing = desired_facing.copy()
                intermediate_yaw_rate = current_yaw_rate.copy()
                updated_facing, proposed_yaw_rate = _critical_spring_angle(
                    previous_facing,
                    current_yaw_rate,
                    desired_facing,
                    smoothing_time_s=parameters.facing_smoothing_time_s,
                    dt_s=dt_s,
                )
            facing_deadzone = np.abs(_wrap_angle(updated_facing - desired_facing)) < math.radians(
                parameters.facing_deadzone_deg
            )
            deadzone_yaw_rate = _wrap_angle(updated_facing - previous_facing) / dt_s
            proposed_yaw_rate = np.where(facing_deadzone, deadzone_yaw_rate, proposed_yaw_rate)
            intermediate_facing = np.where(facing_deadzone, desired_facing, intermediate_facing)
            intermediate_yaw_rate = np.where(
                facing_deadzone
                & (
                    np.abs(proposed_yaw_rate)
                    < math.radians(parameters.angular_velocity_deadzone_deg_s)
                ),
                0.0,
                intermediate_yaw_rate,
            )

            nominal_position = previous_position + proposed_velocity * dt_s
            nominal_facing = _wrap_angle(previous_facing + proposed_yaw_rate * dt_s)
            nominal_yaw_rate_deg_s = np.degrees(proposed_yaw_rate)
            nominal_time = simulation_time + dt_s

            if residual_model is None:
                position = nominal_position
                velocity = proposed_velocity
                facing = nominal_facing
                yaw_rate_deg_s = nominal_yaw_rate_deg_s
            else:
                feature_batch = np.column_stack(
                    (
                        _local_from_world(previous_velocity[:, :2], previous_facing),
                        np.radians(previous_yaw_rate),
                        bounded_local,
                        _wrap_angle(desired_facing - previous_facing),
                        _local_from_world(
                            nominal_position[:, :2] - previous_position[:, :2],
                            previous_facing,
                        ),
                        _local_from_world(proposed_velocity[:, :2], previous_facing),
                        _wrap_angle(nominal_facing - previous_facing),
                        np.radians(nominal_yaw_rate_deg_s),
                        np.full(candidate_count, dt_s),
                        parameter_features,
                    )
                )
                if feature_batch.shape != (candidate_count, RESIDUAL_STEP_FEATURE_COUNT):
                    raise RuntimeError("vectorized residual feature width drifted")
                correction = predict_physical_residuals(
                    residual_model,
                    residual_normalization,
                    feature_batch,
                )
                correction_is_zero = np.all(correction == 0.0, axis=1)
                position = nominal_position.copy()
                position[:, :2] += _world_from_local(correction[:, :2], previous_facing)
                velocity = proposed_velocity.copy()
                velocity[:, :2] += _world_from_local(correction[:, 2:4], previous_facing)
                facing = _wrap_angle(nominal_facing + correction[:, 4])
                yaw_rate_deg_s = nominal_yaw_rate_deg_s + np.degrees(correction[:, 5])
                position = np.where(correction_is_zero[:, None], nominal_position, position)
                velocity = np.where(correction_is_zero[:, None], proposed_velocity, velocity)
                facing = np.where(correction_is_zero, nominal_facing, facing)
                yaw_rate_deg_s = np.where(
                    correction_is_zero, nominal_yaw_rate_deg_s, yaw_rate_deg_s
                )

            spring_velocity = proposed_velocity.copy()
            spring_acceleration = next_spring_acceleration
            intermediate_velocity = next_intermediate
            simulation_time = nominal_time

        output_positions[:, plan_step] = position[:, :2]
        output_velocities[:, plan_step] = velocity[:, :2]
        output_facing[:, plan_step] = facing
        output_yaw_rate[:, plan_step] = yaw_rate_deg_s

    final_observables = tuple(
        SmoothWalkingObservableState(
            position_world_cm=position[index].copy(),
            velocity_world_cm_s=velocity[index].copy(),
            facing_yaw_rad=float(facing[index]),
            angular_velocity_yaw_deg_s=float(yaw_rate_deg_s[index]),
            simulation_time_s=float(simulation_time[index]),
        )
        for index in range(candidate_count)
    )
    final_internals = tuple(
        SmoothWalkingInternalState(
            velocity=SmoothWalkingVelocityState(
                spring_velocity_world_cm_s=spring_velocity[index].copy(),
                spring_acceleration_world_cm_s2=spring_acceleration[index].copy(),
                intermediate_velocity_world_cm_s=intermediate_velocity[index].copy(),
            ),
            facing=SmoothWalkingFacingState(
                intermediate_facing_yaw_rad=float(intermediate_facing[index]),
                intermediate_angular_velocity_yaw_rad_s=float(intermediate_yaw_rate[index]),
            ),
        )
        for index in range(candidate_count)
    )
    return PlannerRollout(
        positions_world_cm=output_positions,
        velocities_world_cm_s=output_velocities,
        facing_yaw_rad=output_facing,
        angular_velocity_yaw_deg_s=output_yaw_rate,
        final_observables=final_observables,
        final_internals=final_internals,
        dynamics_step_count=plan_step_count * config.dynamics_substeps_per_plan_step,
        residual_model_used=residual_model is not None,
    )
