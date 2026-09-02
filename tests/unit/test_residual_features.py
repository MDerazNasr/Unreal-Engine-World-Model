import math
from dataclasses import replace

import numpy as np
import pytest

from motionworld.dynamics.nominal_episode import NominalTransitionInputs
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
from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_FEATURE_COUNT,
    RESIDUAL_HISTORY_LENGTH,
    RESIDUAL_STEP_FEATURE_COUNT,
    RESIDUAL_STEP_FEATURE_NAMES,
    encode_residual_step_features,
    stack_residual_history,
)


def _inputs(
    *,
    yaw_deg: float = 0.0,
    position_xy: tuple[float, float] = (10.0, 20.0),
) -> NominalTransitionInputs:
    yaw_rad = math.radians(yaw_deg)
    velocity_world = np.asarray([100.0 * math.cos(yaw_rad), 100.0 * math.sin(yaw_rad), 0.0])
    action_world = np.asarray([150.0 * math.cos(yaw_rad), 150.0 * math.sin(yaw_rad), 0.0])
    state = SmoothWalkingObservableState(
        position_world_cm=np.asarray([*position_xy, 88.0]),
        velocity_world_cm_s=velocity_world,
        facing_yaw_rad=yaw_rad,
        angular_velocity_yaw_deg_s=30.0,
        simulation_time_s=1.0,
    )
    internal = SmoothWalkingInternalState(
        velocity=SmoothWalkingVelocityState(
            spring_velocity_world_cm_s=velocity_world,
            spring_acceleration_world_cm_s2=np.zeros(3),
            intermediate_velocity_world_cm_s=velocity_world,
        ),
        facing=SmoothWalkingFacingState(
            intermediate_facing_yaw_rad=math.radians(yaw_deg),
            intermediate_angular_velocity_yaw_rad_s=math.radians(30.0),
        ),
    )
    parameters = SmoothWalkingParameters(
        acceleration_cm_s2=500.0,
        deceleration_cm_s2=300.0,
        directional_acceleration_factor=1.0,
        turning_strength_s_inv=8.0,
        acceleration_smoothing_time_s=0.1,
        deceleration_smoothing_time_s=0.2,
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
    return NominalTransitionInputs(
        observable=state,
        internal=internal,
        action=SmoothWalkingAction(
            desired_velocity_world_cm_s=action_world,
            desired_facing_yaw_rad=math.radians(yaw_deg + 20.0),
        ),
        parameters=parameters,
        dt_s=0.02,
    )


def _features(inputs: NominalTransitionInputs) -> np.ndarray:
    nominal = smooth_walking_nominal_step(
        inputs.observable,
        inputs.internal,
        inputs.action,
        parameters=inputs.parameters,
        dt_s=inputs.dt_s,
    ).observable_next
    return encode_residual_step_features(inputs, nominal)


def test_feature_schema_has_frozen_unique_28_value_order() -> None:
    assert RESIDUAL_STEP_FEATURE_COUNT == 28
    assert len(RESIDUAL_STEP_FEATURE_NAMES) == RESIDUAL_STEP_FEATURE_COUNT
    assert len(set(RESIDUAL_STEP_FEATURE_NAMES)) == RESIDUAL_STEP_FEATURE_COUNT
    assert RESIDUAL_STEP_FEATURE_NAMES[:3] == (
        "state.velocity_local_x_cm_s",
        "state.velocity_local_y_cm_s",
        "state.yaw_rate_rad_s",
    )


def test_features_use_previous_facing_local_frame() -> None:
    features = _features(_inputs(yaw_deg=90.0))

    np.testing.assert_allclose(features[0:2], [100.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(features[3:5], [150.0, 0.0], atol=1e-12)
    assert features[5] == pytest.approx(math.radians(20.0))


def test_absolute_position_is_excluded() -> None:
    first = _features(_inputs(position_xy=(10.0, 20.0)))
    translated = _features(_inputs(position_xy=(1010.0, -480.0)))

    np.testing.assert_allclose(first, translated, atol=1e-12)


def test_absolute_world_heading_is_excluded() -> None:
    world_x_heading = _features(_inputs(yaw_deg=0.0))
    world_y_heading = _features(_inputs(yaw_deg=90.0))

    np.testing.assert_allclose(world_x_heading, world_y_heading, atol=1e-12)


def test_nominal_time_must_match_current_time_plus_dt() -> None:
    inputs = _inputs()
    nominal = smooth_walking_nominal_step(
        inputs.observable,
        inputs.internal,
        inputs.action,
        parameters=inputs.parameters,
        dt_s=inputs.dt_s,
    ).observable_next
    misaligned = replace(nominal, simulation_time_s=nominal.simulation_time_s + 0.01)

    with pytest.raises(ValueError, match="not aligned"):
        encode_residual_step_features(inputs, misaligned)


def test_feature_vector_is_read_only() -> None:
    features = _features(_inputs())

    with pytest.raises(ValueError, match="read-only"):
        features[0] = 999.0


def test_history_is_oldest_to_current_and_has_frozen_size() -> None:
    steps = [np.full(RESIDUAL_STEP_FEATURE_COUNT, index) for index in range(4)]

    history = stack_residual_history(steps)

    assert history.shape == (RESIDUAL_HISTORY_FEATURE_COUNT,)
    assert RESIDUAL_HISTORY_FEATURE_COUNT == RESIDUAL_HISTORY_LENGTH * 28
    np.testing.assert_array_equal(history[:28], np.zeros(28))
    np.testing.assert_array_equal(history[-28:], np.full(28, 3))


@pytest.mark.parametrize("length", [0, 3, 5])
def test_history_rejects_wrong_number_of_steps(length: int) -> None:
    steps = [np.zeros(RESIDUAL_STEP_FEATURE_COUNT) for _ in range(length)]

    with pytest.raises(ValueError, match="exactly 4"):
        stack_residual_history(steps)


def test_history_rejects_wrong_step_width() -> None:
    steps = [np.zeros(RESIDUAL_STEP_FEATURE_COUNT) for _ in range(4)]
    steps[2] = np.zeros(RESIDUAL_STEP_FEATURE_COUNT + 1)

    with pytest.raises(ValueError, match="shape"):
        stack_residual_history(steps)
