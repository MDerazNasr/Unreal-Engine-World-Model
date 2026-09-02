import math

import numpy as np
import pytest

from motionworld.dynamics.smooth_walking_math import inv_exp_approx
from motionworld.dynamics.smooth_walking_velocity import (
    UE_FLOAT_EPSILON,
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
    smooth_walking_velocity_step,
)


@pytest.fixture
def live_parameters() -> SmoothWalkingParameters:
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


def _state(
    spring_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
    spring_acceleration: tuple[float, float, float] = (0.0, 0.0, 0.0),
    intermediate_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> SmoothWalkingVelocityState:
    return SmoothWalkingVelocityState(
        spring_velocity_world_cm_s=np.asarray(spring_velocity),
        spring_acceleration_world_cm_s2=np.asarray(spring_acceleration),
        intermediate_velocity_world_cm_s=np.asarray(intermediate_velocity),
    )


def test_acceleration_step_matches_hand_calculation(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_velocity_step(
        _state(),
        actual_velocity_world_cm_s=[0.0, 0.0, 0.0],
        desired_velocity_world_cm_s=[100.0, 0.0, 0.0],
        parameters=live_parameters,
        dt_s=0.01,
    )
    # Directional acceleration is 500 cm/s², so the ordinary and tracked target
    # after .01 s is 5 cm/s. The critical spring has y=2/T=20 and decay=InvExp(.2).
    decay = inv_exp_approx(0.2)
    expected_velocity = decay * (-5.0 + -100.0 * 0.01) + 5.0
    expected_acceleration = decay * (0.0 - (-100.0) * 20.0 * 0.01)

    assert result.is_accelerating
    assert result.velocity_match == 0.0
    np.testing.assert_allclose(result.desired_acceleration_world_cm_s2, [500.0, 0.0, 0.0])
    np.testing.assert_allclose(result.track_velocity_world_cm_s, [5.0, 0.0, 0.0])
    np.testing.assert_allclose(result.state_next.intermediate_velocity_world_cm_s, [5.0, 0.0, 0.0])
    np.testing.assert_allclose(
        result.proposed_velocity_world_cm_s,
        [expected_velocity, 0.0, 0.0],
    )
    np.testing.assert_allclose(
        result.state_next.spring_acceleration_world_cm_s2,
        [expected_acceleration, 0.0, 0.0],
    )


def test_exact_actual_velocity_match_preserves_intermediate_before_update(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_velocity_step(
        _state(
            spring_velocity=(100.0, 0.0, 0.0),
            intermediate_velocity=(100.0, 0.0, 0.0),
        ),
        actual_velocity_world_cm_s=[100.0, 0.0, 0.0],
        desired_velocity_world_cm_s=[100.0, 0.0, 0.0],
        parameters=live_parameters,
        dt_s=0.01,
    )

    assert result.velocity_match == pytest.approx(1.0)
    np.testing.assert_array_equal(result.proposed_velocity_world_cm_s, [100.0, 0.0, 0.0])
    np.testing.assert_array_equal(
        result.state_next.intermediate_velocity_world_cm_s,
        [100.0, 0.0, 0.0],
    )


def test_collision_mismatch_pulls_hidden_intermediate_toward_actual_velocity(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_velocity_step(
        _state(
            spring_velocity=(165.0, 0.0, 0.0),
            intermediate_velocity=(165.0, 0.0, 0.0),
        ),
        actual_velocity_world_cm_s=[0.0, 0.0, 0.0],
        desired_velocity_world_cm_s=[0.0, 0.0, 0.0],
        parameters=live_parameters,
        dt_s=0.02,
    )

    assert result.velocity_match == 0.0
    assert 0.0 < result.state_next.intermediate_velocity_world_cm_s[0] < 165.0
    assert result.proposed_velocity_world_cm_s[0] > 0.0


def test_deceleration_uses_lateral_deceleration_even_with_directional_factor_one(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_velocity_step(
        _state(
            spring_velocity=(100.0, 0.0, 0.0),
            intermediate_velocity=(100.0, 0.0, 0.0),
        ),
        actual_velocity_world_cm_s=[100.0, 0.0, 0.0],
        desired_velocity_world_cm_s=[0.0, 0.0, 0.0],
        parameters=live_parameters,
        dt_s=0.01,
    )

    assert not result.is_accelerating
    np.testing.assert_allclose(result.desired_acceleration_world_cm_s2, [-300.0, 0.0, 0.0])
    np.testing.assert_allclose(result.state_next.intermediate_velocity_world_cm_s, [97.0, 0.0, 0.0])


def test_turning_rotates_intermediate_velocity_toward_desired_direction(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_velocity_step(
        _state(
            spring_velocity=(100.0, 0.0, 0.0),
            intermediate_velocity=(100.0, 0.0, 0.0),
        ),
        actual_velocity_world_cm_s=[100.0, 0.0, 0.0],
        desired_velocity_world_cm_s=[0.0, 100.0, 0.0],
        parameters=live_parameters,
        dt_s=0.02,
    )

    assert result.state_next.intermediate_velocity_world_cm_s[1] > 0.0
    assert result.state_next.intermediate_velocity_world_cm_s[0] < 100.0


def test_speed_clamp_prevents_directional_acceleration_from_exceeding_target(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_velocity_step(
        _state(),
        actual_velocity_world_cm_s=[0.0, 0.0, 0.0],
        desired_velocity_world_cm_s=[1.0, 0.0, 0.0],
        parameters=live_parameters,
        dt_s=1.0,
    )

    assert np.linalg.norm(result.state_next.intermediate_velocity_world_cm_s) <= 1.0
    assert np.linalg.norm(result.track_velocity_world_cm_s) <= 1.0


def test_velocity_deadzone_snaps_to_desired_and_small_acceleration_to_zero(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_velocity_step(
        _state(
            spring_velocity=(100.0, 0.0, 0.0),
            spring_acceleration=(0.0001, 0.0, 0.0),
            intermediate_velocity=(100.0, 0.0, 0.0),
        ),
        actual_velocity_world_cm_s=[100.0, 0.0, 0.0],
        desired_velocity_world_cm_s=[100.0, 0.0, 0.0],
        parameters=live_parameters,
        dt_s=0.01,
    )

    np.testing.assert_array_equal(result.proposed_velocity_world_cm_s, [100.0, 0.0, 0.0])
    np.testing.assert_array_equal(
        result.state_next.spring_acceleration_world_cm_s2,
        [0.0, 0.0, 0.0],
    )


def test_step_does_not_mutate_input_arrays(live_parameters: SmoothWalkingParameters) -> None:
    spring_velocity = np.asarray([1.0, 2.0, 3.0])
    spring_acceleration = np.asarray([4.0, 5.0, 6.0])
    intermediate_velocity = np.asarray([7.0, 8.0, 9.0])
    state = SmoothWalkingVelocityState(
        spring_velocity,
        spring_acceleration,
        intermediate_velocity,
    )
    originals = [
        array.copy() for array in (spring_velocity, spring_acceleration, intermediate_velocity)
    ]

    smooth_walking_velocity_step(
        state,
        actual_velocity_world_cm_s=[1.0, 2.0, 3.0],
        desired_velocity_world_cm_s=[20.0, 0.0, 0.0],
        parameters=live_parameters,
        dt_s=0.01,
    )

    for array, original in zip(
        (spring_velocity, spring_acceleration, intermediate_velocity),
        originals,
        strict=True,
    ):
        np.testing.assert_array_equal(array, original)


@pytest.mark.parametrize("dt_s", [0.0, UE_FLOAT_EPSILON, -1.0, math.nan, math.inf])
def test_invalid_timestep_fails_closed(
    live_parameters: SmoothWalkingParameters,
    dt_s: float,
) -> None:
    with pytest.raises(ValueError):
        smooth_walking_velocity_step(
            _state(),
            actual_velocity_world_cm_s=[0.0, 0.0, 0.0],
            desired_velocity_world_cm_s=[0.0, 0.0, 0.0],
            parameters=live_parameters,
            dt_s=dt_s,
        )


def test_invalid_vector_shape_fails_closed(live_parameters: SmoothWalkingParameters) -> None:
    with pytest.raises(ValueError, match=r"shape \(3,\)"):
        smooth_walking_velocity_step(
            _state(),
            actual_velocity_world_cm_s=[0.0, 0.0],
            desired_velocity_world_cm_s=[0.0, 0.0, 0.0],
            parameters=live_parameters,
            dt_s=0.01,
        )


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("acceleration_cm_s2", -1.0),
        ("directional_acceleration_factor", 1.1),
        ("acceleration_smoothing_compensation", -0.1),
        ("deceleration_smoothing_compensation", 1.1),
        ("facing_smoothing_time_s", math.nan),
    ],
)
def test_invalid_parameters_fail_closed(
    live_parameters: SmoothWalkingParameters,
    field: str,
    invalid: float,
) -> None:
    values = {name: getattr(live_parameters, name) for name in live_parameters.__dataclass_fields__}
    values[field] = invalid

    with pytest.raises(ValueError):
        SmoothWalkingParameters(**values)
