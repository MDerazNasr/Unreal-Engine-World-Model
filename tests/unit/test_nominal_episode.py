import math

import numpy as np
import pytest

from motionworld.dynamics.nominal_episode import retrospective_nominal_inputs


def _transition() -> dict[str, object]:
    parameters = {
        "acceleration_cm_per_s2": 500.0,
        "deceleration_cm_per_s2": 300.0,
        "directional_acceleration_factor": 1.0,
        "turning_strength": 8.0,
        "acceleration_smoothing_time_s": 0.1,
        "deceleration_smoothing_time_s": 0.1,
        "acceleration_smoothing_compensation": 0.0,
        "deceleration_smoothing_compensation": 0.0,
        "velocity_deadzone_cm_per_s": 0.01,
        "acceleration_deadzone_cm_per_s2": 0.001,
        "outside_influence_smoothing_time_s": 0.05,
        "facing_smoothing_time_s": 0.4,
        "smooth_facing_with_double_spring": False,
        "facing_deadzone_deg": 0.1,
        "angular_velocity_deadzone_deg_per_s": 0.01,
    }
    internal = {
        "spring_velocity_world_cm_per_s": [1.0, 2.0, 0.0],
        "spring_acceleration_world_cm_per_s2": [3.0, 4.0, 0.0],
        "intermediate_velocity_world_cm_per_s": [5.0, 6.0, 0.0],
        "intermediate_facing_world_xyzw": [
            0.0,
            0.0,
            math.sin(math.radians(15.0)),
            math.cos(math.radians(15.0)),
        ],
        "intermediate_angular_velocity_world_rad_per_s": [0.0, 0.0, 0.25],
    }
    return {
        "delta_time_s": 0.02,
        "previous_state": {
            "position_world_cm": [10.0, 20.0, 30.0],
            "velocity_world_cm_per_s": [7.0, 8.0, 0.0],
            "facing_yaw_deg": 20.0,
            "angular_velocity_world_deg_per_s": [0.0, 0.0, 9.0],
            "simulation_time_s": 1.5,
        },
        "applied_action": {"velocity_world_cm_per_s": [100.0, -20.0, 0.0]},
        "nominal_context": {
            "previous": {
                "parameters": {**parameters, "acceleration_cm_per_s2": 999.0},
                "internal_state": internal,
            },
            "parameters_observed_for_completed_step": parameters,
        },
    }


def test_adapter_uses_previous_state_and_hidden_context() -> None:
    result = retrospective_nominal_inputs(
        _transition(),
        desired_facing_yaw_rad=math.radians(70.0),
        effective_max_speed_cm_s=165.0,
    )

    np.testing.assert_array_equal(result.observable.position_world_cm, [10.0, 20.0, 30.0])
    np.testing.assert_array_equal(result.observable.velocity_world_cm_s, [7.0, 8.0, 0.0])
    assert math.degrees(result.observable.facing_yaw_rad) == 20.0
    assert result.observable.angular_velocity_yaw_deg_s == 9.0
    np.testing.assert_array_equal(
        result.internal.velocity.intermediate_velocity_world_cm_s,
        [5.0, 6.0, 0.0],
    )
    assert math.degrees(result.internal.facing.intermediate_facing_yaw_rad) == pytest.approx(30.0)
    assert result.internal.facing.intermediate_angular_velocity_yaw_rad_s == 0.25


def test_adapter_uses_completed_step_parameters_not_stale_previous_snapshot() -> None:
    result = retrospective_nominal_inputs(
        _transition(),
        desired_facing_yaw_rad=0.0,
        effective_max_speed_cm_s=165.0,
    )

    assert result.parameters.acceleration_cm_s2 == 500.0
    assert result.parameters.acceleration_cm_s2 != 999.0
    assert result.dt_s == 0.02


def test_adapter_keeps_desired_facing_explicit() -> None:
    desired_facing = math.radians(-45.0)
    result = retrospective_nominal_inputs(
        _transition(),
        desired_facing_yaw_rad=desired_facing,
        effective_max_speed_cm_s=165.0,
    )

    np.testing.assert_array_equal(
        result.action.desired_velocity_world_cm_s,
        [100.0, -20.0, 0.0],
    )
    assert result.action.desired_facing_yaw_rad == desired_facing


def test_adapter_applies_explicit_simple_walking_speed_limit() -> None:
    transition = _transition()
    transition["applied_action"]["velocity_world_cm_per_s"] = [200.0, 0.0, 0.0]

    result = retrospective_nominal_inputs(
        transition,
        desired_facing_yaw_rad=0.0,
        effective_max_speed_cm_s=165.0,
    )

    np.testing.assert_array_equal(
        result.action.desired_velocity_world_cm_s,
        [165.0, 0.0, 0.0],
    )


def test_adapter_infers_schema_v4_facing_and_speed_limit() -> None:
    transition = _transition()
    transition["applied_action"]["velocity_world_cm_per_s"] = [200.0, 0.0, 0.0]
    transition["applied_action"]["desired_facing_yaw_deg"] = 70.0
    transition["nominal_context"]["input_preparation_observed_for_completed_step"] = {
        "has_max_move_speed": True,
        "effective_max_speed_cm_per_s": 165.0,
        "max_speed_source": "common_legacy_settings",
    }

    result = retrospective_nominal_inputs(transition)

    np.testing.assert_array_equal(result.action.desired_velocity_world_cm_s, [165.0, 0.0, 0.0])
    assert result.action.desired_facing_yaw_rad == pytest.approx(math.radians(70.0))


def test_adapter_refuses_to_invent_missing_legacy_causal_fields() -> None:
    with pytest.raises(ValueError, match="desired_facing"):
        retrospective_nominal_inputs(_transition())
