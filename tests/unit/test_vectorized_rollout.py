from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
import torch

from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingInternalState
from motionworld.dynamics.smooth_walking_velocity import SmoothWalkingVelocityState
from motionworld.models.residual_features import RESIDUAL_STEP_FEATURE_COUNT
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.planning.planner_rollout import PlannerRollout, PlannerRolloutConfig
from motionworld.planning.vectorized_rollout import rollout_action_candidates_vectorized
from tests.unit.test_planner_rollout import _normalization, _snapshot


def _assert_rollout_close(reference: PlannerRollout, vectorized: PlannerRollout) -> None:
    np.testing.assert_allclose(
        vectorized.positions_world_cm, reference.positions_world_cm, rtol=1.0e-12, atol=1.0e-12
    )
    np.testing.assert_allclose(
        vectorized.velocities_world_cm_s,
        reference.velocities_world_cm_s,
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    np.testing.assert_allclose(
        vectorized.facing_yaw_rad, reference.facing_yaw_rad, rtol=1.0e-12, atol=1.0e-12
    )
    np.testing.assert_allclose(
        vectorized.angular_velocity_yaw_deg_s,
        reference.angular_velocity_yaw_deg_s,
        rtol=1.0e-12,
        atol=1.0e-12,
    )
    assert vectorized.dynamics_step_count == reference.dynamics_step_count
    assert vectorized.residual_model_used == reference.residual_model_used
    for expected, actual in zip(
        reference.final_observables, vectorized.final_observables, strict=True
    ):
        np.testing.assert_allclose(actual.position_world_cm, expected.position_world_cm)
        np.testing.assert_allclose(actual.velocity_world_cm_s, expected.velocity_world_cm_s)
        assert actual.facing_yaw_rad == pytest.approx(expected.facing_yaw_rad, abs=1.0e-12)
        assert actual.angular_velocity_yaw_deg_s == pytest.approx(
            expected.angular_velocity_yaw_deg_s, abs=1.0e-12
        )
        assert actual.simulation_time_s == expected.simulation_time_s
    for expected, actual in zip(reference.final_internals, vectorized.final_internals, strict=True):
        np.testing.assert_allclose(
            actual.velocity.spring_velocity_world_cm_s,
            expected.velocity.spring_velocity_world_cm_s,
        )
        np.testing.assert_allclose(
            actual.velocity.spring_acceleration_world_cm_s2,
            expected.velocity.spring_acceleration_world_cm_s2,
        )
        np.testing.assert_allclose(
            actual.velocity.intermediate_velocity_world_cm_s,
            expected.velocity.intermediate_velocity_world_cm_s,
        )
        assert actual.facing.intermediate_facing_yaw_rad == pytest.approx(
            expected.facing.intermediate_facing_yaw_rad, abs=1.0e-12
        )
        assert actual.facing.intermediate_angular_velocity_yaw_rad_s == pytest.approx(
            expected.facing.intermediate_angular_velocity_yaw_rad_s, abs=1.0e-12
        )


def _reference(*args: object, **kwargs: object) -> PlannerRollout:
    from motionworld.planning.planner_rollout import rollout_action_candidates

    return rollout_action_candidates(*args, **kwargs)


def test_vectorized_nominal_matches_scalar_across_candidates_and_turns() -> None:
    generator = np.random.default_rng(20260903)
    actions = generator.uniform(-220.0, 220.0, size=(37, 15, 2))
    actions[:, 4] = 0.0
    config = PlannerRolloutConfig(0.1, 3)
    reference = _reference(_snapshot(yaw_rad=-1.2), actions, config=config)
    vectorized = rollout_action_candidates_vectorized(
        _snapshot(yaw_rad=-1.2), actions, config=config
    )
    _assert_rollout_close(reference, vectorized)


def test_vectorized_double_spring_and_nonzero_hidden_state_match_scalar() -> None:
    base = _snapshot(yaw_rad=2.4)
    snapshot = replace(
        base,
        observable=replace(
            base.observable,
            velocity_world_cm_s=np.array([72.0, -31.0, 0.0]),
            angular_velocity_yaw_deg_s=-17.0,
        ),
        internal=SmoothWalkingInternalState(
            velocity=SmoothWalkingVelocityState(
                spring_velocity_world_cm_s=np.array([65.0, -20.0, 0.0]),
                spring_acceleration_world_cm_s2=np.array([12.0, -4.0, 0.0]),
                intermediate_velocity_world_cm_s=np.array([80.0, -22.0, 0.0]),
            ),
            facing=SmoothWalkingFacingState(
                intermediate_facing_yaw_rad=2.1,
                intermediate_angular_velocity_yaw_rad_s=0.3,
            ),
        ),
        parameters=replace(base.parameters, smooth_facing_with_double_spring=True),
    )
    actions = np.array(
        [
            [[-165.0, 0.0], [0.0, 0.0], [30.0, 90.0]],
            [[20.0, -140.0], [20.0, -140.0], [-90.0, 40.0]],
        ]
    )
    config = PlannerRolloutConfig(0.5, 2)
    _assert_rollout_close(
        _reference(snapshot, actions, config=config),
        rollout_action_candidates_vectorized(snapshot, actions, config=config),
    )


def test_vectorized_residual_features_and_composition_match_scalar() -> None:
    torch.manual_seed(71)
    model = ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,))
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.uniform_(-0.01, 0.01)
    actions = np.random.default_rng(4).uniform(-120.0, 120.0, size=(11, 4, 2))
    config = PlannerRolloutConfig(0.1, 3)
    arguments = {
        "config": config,
        "residual_model": model,
        "residual_normalization": _normalization(),
    }
    _assert_rollout_close(
        _reference(_snapshot(yaw_rad=0.7), actions, **arguments),
        rollout_action_candidates_vectorized(_snapshot(yaw_rad=0.7), actions, **arguments),
    )
