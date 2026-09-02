"""Batched candidate rollouts through nominal or no-history residual dynamics."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from motionworld.dynamics.coordinates import YawRadians, local_vector_to_world
from motionworld.dynamics.nominal_episode import NominalTransitionInputs
from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
    smooth_walking_nominal_step_batch,
)
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
)
from motionworld.models.residual_contract import ResidualCorrection, compose_residual
from motionworld.models.residual_features import (
    RESIDUAL_STEP_FEATURE_COUNT,
    encode_residual_step_features,
)
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.models.residual_training import predict_physical_residuals
from motionworld.planning.cem import project_velocity_actions

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class PlannerSnapshot:
    """One authoritative state and known causal context shared by all candidates."""

    observable: SmoothWalkingObservableState
    internal: SmoothWalkingInternalState
    parameters: SmoothWalkingParameters
    effective_max_speed_cm_s: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.effective_max_speed_cm_s):
            raise ValueError("effective_max_speed_cm_s must be finite")
        if self.effective_max_speed_cm_s <= 0.0:
            raise ValueError("effective_max_speed_cm_s must be positive")


@dataclass(frozen=True, slots=True)
class PlannerRolloutConfig:
    plan_step_s: float = 0.1
    dynamics_substeps_per_plan_step: int = 3

    def __post_init__(self) -> None:
        if not math.isfinite(self.plan_step_s) or self.plan_step_s <= 0.0:
            raise ValueError("plan_step_s must be positive and finite")
        substeps = self.dynamics_substeps_per_plan_step
        if isinstance(substeps, bool) or not isinstance(substeps, int) or substeps <= 0:
            raise ValueError("dynamics_substeps_per_plan_step must be a positive integer")

    @property
    def dynamics_dt_s(self) -> float:
        return self.plan_step_s / self.dynamics_substeps_per_plan_step


@dataclass(frozen=True, slots=True)
class PlannerRollout:
    """Plan-boundary predictions and final per-candidate hidden state."""

    positions_world_cm: FloatArray
    velocities_world_cm_s: FloatArray
    facing_yaw_rad: FloatArray
    angular_velocity_yaw_deg_s: FloatArray
    final_observables: tuple[SmoothWalkingObservableState, ...]
    final_internals: tuple[SmoothWalkingInternalState, ...]
    dynamics_step_count: int
    residual_model_used: bool


def _clone_observable(state: SmoothWalkingObservableState) -> SmoothWalkingObservableState:
    return SmoothWalkingObservableState(
        position_world_cm=np.asarray(state.position_world_cm, dtype=np.float64).copy(),
        velocity_world_cm_s=np.asarray(state.velocity_world_cm_s, dtype=np.float64).copy(),
        facing_yaw_rad=float(state.facing_yaw_rad),
        angular_velocity_yaw_deg_s=float(state.angular_velocity_yaw_deg_s),
        simulation_time_s=float(state.simulation_time_s),
    )


def _clone_internal(state: SmoothWalkingInternalState) -> SmoothWalkingInternalState:
    return SmoothWalkingInternalState(
        velocity=SmoothWalkingVelocityState(
            spring_velocity_world_cm_s=np.asarray(
                state.velocity.spring_velocity_world_cm_s,
                dtype=np.float64,
            ).copy(),
            spring_acceleration_world_cm_s2=np.asarray(
                state.velocity.spring_acceleration_world_cm_s2,
                dtype=np.float64,
            ).copy(),
            intermediate_velocity_world_cm_s=np.asarray(
                state.velocity.intermediate_velocity_world_cm_s,
                dtype=np.float64,
            ).copy(),
        ),
        facing=SmoothWalkingFacingState(
            intermediate_facing_yaw_rad=float(state.facing.intermediate_facing_yaw_rad),
            intermediate_angular_velocity_yaw_rad_s=float(
                state.facing.intermediate_angular_velocity_yaw_rad_s
            ),
        ),
    )


def _validate_candidate_actions(actions_local_cm_s: FloatArray) -> FloatArray:
    actions = np.asarray(actions_local_cm_s, dtype=np.float64)
    if actions.ndim != 3 or actions.shape[0] == 0 or actions.shape[1] == 0:
        raise ValueError("candidate actions must have shape [candidate, plan_step, 2]")
    if actions.shape[2] != 2:
        raise ValueError("candidate actions must have exactly two planar components")
    if not np.all(np.isfinite(actions)):
        raise ValueError("candidate actions must contain only finite values")
    return actions


def _action_from_local_velocity(
    local_velocity_cm_s: FloatArray,
    observable: SmoothWalkingObservableState,
    *,
    maximum_speed_cm_s: float,
) -> SmoothWalkingAction:
    bounded_local = project_velocity_actions(
        np.asarray(local_velocity_cm_s, dtype=np.float64),
        maximum_speed_cm_s=maximum_speed_cm_s,
    )
    current_yaw = YawRadians(float(observable.facing_yaw_rad))
    world_planar = local_vector_to_world(bounded_local, yaw=current_yaw)
    desired_world = np.asarray([world_planar[0], world_planar[1], 0.0], dtype=np.float64)
    if np.linalg.norm(world_planar) <= 1.0e-12:
        desired_facing = current_yaw.value
    else:
        desired_facing = math.atan2(float(world_planar[1]), float(world_planar[0]))
    return SmoothWalkingAction(
        desired_velocity_world_cm_s=desired_world,
        desired_facing_yaw_rad=desired_facing,
    )


def _correction(values: FloatArray) -> ResidualCorrection:
    if values.shape != (6,):
        raise ValueError("residual prediction must contain six values")
    return ResidualCorrection(
        position_local_cm=values[0:2],
        velocity_local_cm_s=values[2:4],
        yaw_rad=float(values[4]),
        angular_velocity_yaw_rad_s=float(values[5]),
    )


def rollout_action_candidates(
    snapshot: PlannerSnapshot,
    actions_local_cm_s: FloatArray,
    *,
    config: PlannerRolloutConfig,
    residual_model: ResidualMLP | None = None,
    residual_normalization: ResidualNormalization | None = None,
) -> PlannerRollout:
    """Roll all candidates from the exact same snapshot without cross-candidate state sharing.

    Actions are character-local requests resolved against each candidate's predicted current yaw at
    every dynamics substep. Nonzero desired velocity also defines desired facing; zero holds facing.
    The selected residual model is no-history, so every correction uses only recursively available
    current state, action, known parameters, timestep, and the just-computed nominal proposal.
    """

    actions = _validate_candidate_actions(actions_local_cm_s)
    if (residual_model is None) != (residual_normalization is None):
        raise ValueError("residual model and normalization must be supplied together")
    if residual_model is not None:
        if residual_model.input_width != RESIDUAL_STEP_FEATURE_COUNT:
            raise ValueError("planner supports only the selected no-history residual model")
        if (
            residual_normalization is None
            or residual_normalization.history_length != 1
            or residual_normalization.feature_width != residual_model.input_width
        ):
            raise ValueError("residual model and normalization schemas differ")

    candidate_count, plan_step_count, _ = actions.shape
    observables = [_clone_observable(snapshot.observable) for _ in range(candidate_count)]
    internals = [_clone_internal(snapshot.internal) for _ in range(candidate_count)]
    positions = np.empty((candidate_count, plan_step_count, 2), dtype=np.float64)
    velocities = np.empty_like(positions)
    facing = np.empty((candidate_count, plan_step_count), dtype=np.float64)
    yaw_rate = np.empty_like(facing)
    dt_s = config.dynamics_dt_s

    for plan_step in range(plan_step_count):
        for _ in range(config.dynamics_substeps_per_plan_step):
            substep_actions = [
                _action_from_local_velocity(
                    actions[candidate, plan_step],
                    observables[candidate],
                    maximum_speed_cm_s=snapshot.effective_max_speed_cm_s,
                )
                for candidate in range(candidate_count)
            ]
            batch = smooth_walking_nominal_step_batch(
                observables,
                internals,
                substep_actions,
                parameters=[snapshot.parameters] * candidate_count,
                dt_s=[dt_s] * candidate_count,
            )
            nominal_next = [step.observable_next for step in batch.steps]
            if residual_model is None:
                corrected_next = nominal_next
            else:
                inputs = [
                    NominalTransitionInputs(
                        observable=observables[candidate],
                        internal=internals[candidate],
                        action=substep_actions[candidate],
                        parameters=snapshot.parameters,
                        dt_s=dt_s,
                    )
                    for candidate in range(candidate_count)
                ]
                feature_batch = np.stack(
                    [
                        encode_residual_step_features(inputs[candidate], nominal_next[candidate])
                        for candidate in range(candidate_count)
                    ]
                )
                predictions = predict_physical_residuals(
                    residual_model,
                    residual_normalization,
                    feature_batch,
                )
                corrected_next = [
                    compose_residual(
                        nominal_next[candidate],
                        _correction(predictions[candidate]),
                        reference_yaw=YawRadians(
                            float(inputs[candidate].observable.facing_yaw_rad)
                        ),
                    )
                    for candidate in range(candidate_count)
                ]
            observables = corrected_next
            internals = [step.internal_next for step in batch.steps]

        positions[:, plan_step, :] = np.stack(
            [observable.position_world_cm[:2] for observable in observables]
        )
        velocities[:, plan_step, :] = np.stack(
            [observable.velocity_world_cm_s[:2] for observable in observables]
        )
        facing[:, plan_step] = [observable.facing_yaw_rad for observable in observables]
        yaw_rate[:, plan_step] = [
            observable.angular_velocity_yaw_deg_s for observable in observables
        ]

    return PlannerRollout(
        positions_world_cm=positions,
        velocities_world_cm_s=velocities,
        facing_yaw_rad=facing,
        angular_velocity_yaw_deg_s=yaw_rate,
        final_observables=tuple(observables),
        final_internals=tuple(internals),
        dynamics_step_count=plan_step_count * config.dynamics_substeps_per_plan_step,
        residual_model_used=residual_model is not None,
    )
