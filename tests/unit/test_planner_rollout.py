from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
    smooth_walking_nominal_step,
)
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
)
from motionworld.models.residual_features import RESIDUAL_STEP_FEATURE_COUNT
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.planning.planner_rollout import (
    PlannerRolloutConfig,
    PlannerSnapshot,
    rollout_action_candidates,
)


def _parameters() -> SmoothWalkingParameters:
    return SmoothWalkingParameters(
        acceleration_cm_s2=500.0,
        deceleration_cm_s2=300.0,
        directional_acceleration_factor=1.0,
        turning_strength_s_inv=8.0,
        acceleration_smoothing_time_s=0.1,
        deceleration_smoothing_time_s=0.1,
        acceleration_smoothing_compensation=0.0,
        deceleration_smoothing_compensation=0.0,
        velocity_deadzone_cm_s=0.01,
        acceleration_deadzone_cm_s2=0.001,
        outside_influence_smoothing_time_s=0.05,
        facing_smoothing_time_s=0.4,
        smooth_facing_with_double_spring=False,
        facing_deadzone_deg=0.1,
        angular_velocity_deadzone_deg_s=0.01,
    )


def _snapshot(*, yaw_rad: float = 0.0) -> PlannerSnapshot:
    return PlannerSnapshot(
        observable=SmoothWalkingObservableState(
            position_world_cm=np.zeros(3),
            velocity_world_cm_s=np.zeros(3),
            facing_yaw_rad=yaw_rad,
            angular_velocity_yaw_deg_s=0.0,
            simulation_time_s=4.0,
        ),
        internal=SmoothWalkingInternalState(
            velocity=SmoothWalkingVelocityState(
                spring_velocity_world_cm_s=np.zeros(3),
                spring_acceleration_world_cm_s2=np.zeros(3),
                intermediate_velocity_world_cm_s=np.zeros(3),
            ),
            facing=SmoothWalkingFacingState(
                intermediate_facing_yaw_rad=yaw_rad,
                intermediate_angular_velocity_yaw_rad_s=0.0,
            ),
        ),
        parameters=_parameters(),
        effective_max_speed_cm_s=165.0,
    )


def _normalization() -> ResidualNormalization:
    return ResidualNormalization(
        history_length=1,
        train_episode_ids=(1,),
        sample_count=1,
        feature_mean=np.zeros(RESIDUAL_STEP_FEATURE_COUNT),
        feature_scale=np.ones(RESIDUAL_STEP_FEATURE_COUNT),
        constant_feature_mask=np.ones(RESIDUAL_STEP_FEATURE_COUNT, dtype=bool),
        target_scale=np.ones(6),
        constant_target_mask=np.ones(6, dtype=bool),
    )


def test_rollout_shape_time_and_substep_count_are_exact() -> None:
    result = rollout_action_candidates(
        _snapshot(),
        np.zeros((4, 15, 2)),
        config=PlannerRolloutConfig(0.1, 3),
    )
    assert result.positions_world_cm.shape == (4, 15, 2)
    assert result.velocities_world_cm_s.shape == (4, 15, 2)
    assert result.facing_yaw_rad.shape == (4, 15)
    assert result.dynamics_step_count == 45
    for final in result.final_observables:
        assert math.isclose(final.simulation_time_s, 5.5, abs_tol=1.0e-12)


def test_zero_residual_is_bit_exact_with_nominal_for_every_output() -> None:
    actions = np.array(
        [
            [[100.0, 0.0], [0.0, 80.0], [0.0, 0.0]],
            [[-70.0, 20.0], [40.0, -50.0], [20.0, 0.0]],
        ]
    )
    config = PlannerRolloutConfig(0.1, 3)
    nominal = rollout_action_candidates(_snapshot(), actions, config=config)
    zero_model = ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,))
    residual = rollout_action_candidates(
        _snapshot(),
        actions,
        config=config,
        residual_model=zero_model,
        residual_normalization=_normalization(),
    )
    np.testing.assert_array_equal(residual.positions_world_cm, nominal.positions_world_cm)
    np.testing.assert_array_equal(residual.velocities_world_cm_s, nominal.velocities_world_cm_s)
    np.testing.assert_array_equal(residual.facing_yaw_rad, nominal.facing_yaw_rad)
    np.testing.assert_array_equal(
        residual.angular_velocity_yaw_deg_s,
        nominal.angular_velocity_yaw_deg_s,
    )


def test_local_forward_at_ninety_degrees_moves_only_positive_world_y() -> None:
    result = rollout_action_candidates(
        _snapshot(yaw_rad=math.pi / 2.0),
        np.array([[[100.0, 0.0]]]),
        config=PlannerRolloutConfig(0.1, 3),
    )
    assert abs(result.positions_world_cm[0, 0, 0]) < 1.0e-12
    assert result.positions_world_cm[0, 0, 1] > 0.0
    assert abs(result.facing_yaw_rad[0, 0] - math.pi / 2.0) < 1.0e-12


def test_one_plan_step_exactly_matches_three_manual_nominal_substeps() -> None:
    snapshot = _snapshot()
    result = rollout_action_candidates(
        snapshot,
        np.array([[[100.0, 0.0]]]),
        config=PlannerRolloutConfig(0.1, 3),
    )
    observable = snapshot.observable
    internal = snapshot.internal
    action = SmoothWalkingAction(
        desired_velocity_world_cm_s=np.array([100.0, 0.0, 0.0]),
        desired_facing_yaw_rad=0.0,
    )
    for _ in range(3):
        manual = smooth_walking_nominal_step(
            observable,
            internal,
            action,
            parameters=snapshot.parameters,
            dt_s=0.1 / 3.0,
        )
        observable = manual.observable_next
        internal = manual.internal_next
    np.testing.assert_array_equal(result.positions_world_cm[0, 0], observable.position_world_cm[:2])
    np.testing.assert_array_equal(
        result.velocities_world_cm_s[0, 0],
        observable.velocity_world_cm_s[:2],
    )
    assert result.facing_yaw_rad[0, 0] == observable.facing_yaw_rad


def test_candidates_do_not_share_mutable_hidden_state() -> None:
    actions = np.array(
        [
            [[100.0, 0.0], [100.0, 0.0]],
            [[0.0, 0.0], [0.0, 0.0]],
            [[100.0, 0.0], [100.0, 0.0]],
        ]
    )
    result = rollout_action_candidates(
        _snapshot(),
        actions,
        config=PlannerRolloutConfig(0.1, 3),
    )
    np.testing.assert_array_equal(result.positions_world_cm[0], result.positions_world_cm[2])
    np.testing.assert_array_equal(result.velocities_world_cm_s[0], result.velocities_world_cm_s[2])
    np.testing.assert_array_equal(result.positions_world_cm[1], 0.0)


def test_nonzero_residual_bias_is_applied_recursively() -> None:
    model = ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,))
    with torch.no_grad():
        model.output.bias[0] = 1.0
    result = rollout_action_candidates(
        _snapshot(),
        np.zeros((1, 1, 2)),
        config=PlannerRolloutConfig(0.1, 3),
        residual_model=model,
        residual_normalization=_normalization(),
    )
    # One local-forward centimeter is added after each of three dynamics substeps.
    np.testing.assert_allclose(result.positions_world_cm[0, 0], [3.0, 0.0], atol=1.0e-12)


def test_input_actions_are_rebounded_to_snapshot_limit() -> None:
    huge = rollout_action_candidates(
        _snapshot(),
        np.array([[[1.0e6, 0.0]]]),
        config=PlannerRolloutConfig(0.1, 1),
    )
    bounded = rollout_action_candidates(
        _snapshot(),
        np.array([[[165.0, 0.0]]]),
        config=PlannerRolloutConfig(0.1, 1),
    )
    np.testing.assert_array_equal(huge.positions_world_cm, bounded.positions_world_cm)


def test_model_and_normalization_must_be_supplied_together() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        rollout_action_candidates(
            _snapshot(),
            np.zeros((1, 1, 2)),
            config=PlannerRolloutConfig(),
            residual_model=ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,)),
        )


@pytest.mark.parametrize(
    "actions",
    [np.zeros((0, 1, 2)), np.zeros((1, 0, 2)), np.zeros((1, 1, 3))],
)
def test_invalid_candidate_shapes_fail(actions: np.ndarray) -> None:
    with pytest.raises(ValueError, match="candidate actions"):
        rollout_action_candidates(_snapshot(), actions, config=PlannerRolloutConfig())
