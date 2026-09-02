import math
from dataclasses import replace

import pytest

from motionworld.dynamics.smooth_walking_facing import (
    SmoothWalkingFacingState,
    smooth_walking_facing_step,
)
from motionworld.dynamics.smooth_walking_math import (
    critical_spring_damper_angle,
    find_delta_angle_radians,
)
from motionworld.dynamics.smooth_walking_velocity import SmoothWalkingParameters


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


def test_single_spring_matches_independent_angle_equation(
    live_parameters: SmoothWalkingParameters,
) -> None:
    current = math.radians(10.0)
    desired = math.radians(90.0)
    angular_velocity_deg_s = 5.0
    result = smooth_walking_facing_step(
        SmoothWalkingFacingState(0.0, 0.0),
        current_facing_yaw_rad=current,
        actual_angular_velocity_yaw_deg_s=angular_velocity_deg_s,
        desired_facing_yaw_rad=desired,
        parameters=live_parameters,
        dt_s=0.02,
    )
    expected = critical_spring_damper_angle(
        current,
        math.radians(angular_velocity_deg_s),
        desired,
        smoothing_time_s=0.4,
        dt_s=0.02,
    )

    assert result.spring_updated_facing_yaw_rad == pytest.approx(expected.angle_next_rad)
    assert result.proposed_angular_velocity_yaw_deg_s == pytest.approx(
        math.degrees(expected.angular_velocity_next_rad_s)
    )
    assert result.state_next.intermediate_facing_yaw_rad == desired
    assert result.state_next.intermediate_angular_velocity_yaw_rad_s == pytest.approx(
        math.radians(angular_velocity_deg_s)
    )
    assert not result.facing_deadzone_active


def test_single_spring_uses_short_path_across_wrap_boundary(
    live_parameters: SmoothWalkingParameters,
) -> None:
    current = math.radians(179.0)
    desired = math.radians(-179.0)
    result = smooth_walking_facing_step(
        SmoothWalkingFacingState(current, 0.0),
        current_facing_yaw_rad=current,
        actual_angular_velocity_yaw_deg_s=0.0,
        desired_facing_yaw_rad=desired,
        parameters=live_parameters,
        dt_s=0.02,
    )

    assert result.proposed_angular_velocity_yaw_deg_s > 0.0
    assert abs(
        find_delta_angle_radians(result.spring_updated_facing_yaw_rad, desired)
    ) < math.radians(2.0)


def test_double_spring_is_two_cascaded_half_time_springs(
    live_parameters: SmoothWalkingParameters,
) -> None:
    parameters = replace(live_parameters, smooth_facing_with_double_spring=True)
    current = math.radians(-20.0)
    intermediate = math.radians(5.0)
    desired = math.radians(100.0)
    intermediate_velocity = math.radians(3.0)
    current_velocity = math.radians(-4.0)
    result = smooth_walking_facing_step(
        SmoothWalkingFacingState(intermediate, intermediate_velocity),
        current_facing_yaw_rad=current,
        actual_angular_velocity_yaw_deg_s=math.degrees(current_velocity),
        desired_facing_yaw_rad=desired,
        parameters=parameters,
        dt_s=0.01,
    )
    stage_one = critical_spring_damper_angle(
        intermediate,
        intermediate_velocity,
        desired,
        smoothing_time_s=0.2,
        dt_s=0.01,
    )
    stage_two = critical_spring_damper_angle(
        current,
        current_velocity,
        stage_one.angle_next_rad,
        smoothing_time_s=0.2,
        dt_s=0.01,
    )

    assert result.state_next.intermediate_facing_yaw_rad == pytest.approx(stage_one.angle_next_rad)
    assert result.state_next.intermediate_angular_velocity_yaw_rad_s == pytest.approx(
        stage_one.angular_velocity_next_rad_s
    )
    assert result.spring_updated_facing_yaw_rad == pytest.approx(stage_two.angle_next_rad)
    assert result.proposed_angular_velocity_yaw_deg_s == pytest.approx(
        math.degrees(stage_two.angular_velocity_next_rad_s)
    )


def test_facing_deadzone_recomputes_exact_final_angular_velocity(
    live_parameters: SmoothWalkingParameters,
) -> None:
    parameters = replace(live_parameters, facing_deadzone_deg=180.0)
    current = math.radians(10.0)
    desired = math.radians(10.05)
    timestep = 0.02
    result = smooth_walking_facing_step(
        SmoothWalkingFacingState(current, 0.0),
        current_facing_yaw_rad=current,
        actual_angular_velocity_yaw_deg_s=0.0,
        desired_facing_yaw_rad=desired,
        parameters=parameters,
        dt_s=timestep,
    )
    applied_yaw = current + math.radians(result.proposed_angular_velocity_yaw_deg_s) * timestep

    assert result.facing_deadzone_active
    assert find_delta_angle_radians(
        applied_yaw,
        result.spring_updated_facing_yaw_rad,
    ) == pytest.approx(0.0)
    assert result.state_next.intermediate_facing_yaw_rad == desired


def test_angular_deadzone_zeroes_intermediate_rate_only_when_small(
    live_parameters: SmoothWalkingParameters,
) -> None:
    parameters = replace(
        live_parameters,
        facing_deadzone_deg=180.0,
        angular_velocity_deadzone_deg_s=1000.0,
    )
    result = smooth_walking_facing_step(
        SmoothWalkingFacingState(0.0, 2.0),
        current_facing_yaw_rad=0.0,
        actual_angular_velocity_yaw_deg_s=0.0,
        desired_facing_yaw_rad=math.radians(0.01),
        parameters=parameters,
        dt_s=0.02,
    )

    assert result.state_next.intermediate_angular_velocity_yaw_rad_s == 0.0


@pytest.mark.parametrize("dt_s", [0.0, -0.1, math.nan, math.inf])
def test_invalid_timestep_fails_closed(
    live_parameters: SmoothWalkingParameters,
    dt_s: float,
) -> None:
    with pytest.raises(ValueError):
        smooth_walking_facing_step(
            SmoothWalkingFacingState(0.0, 0.0),
            current_facing_yaw_rad=0.0,
            actual_angular_velocity_yaw_deg_s=0.0,
            desired_facing_yaw_rad=0.0,
            parameters=live_parameters,
            dt_s=dt_s,
        )


def test_nonfinite_facing_state_fails_closed(
    live_parameters: SmoothWalkingParameters,
) -> None:
    with pytest.raises(ValueError):
        smooth_walking_facing_step(
            SmoothWalkingFacingState(math.nan, 0.0),
            current_facing_yaw_rad=0.0,
            actual_angular_velocity_yaw_deg_s=0.0,
            desired_facing_yaw_rad=0.0,
            parameters=live_parameters,
            dt_s=0.02,
        )
