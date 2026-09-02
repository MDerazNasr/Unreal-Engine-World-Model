import math

import numpy as np
import pytest

from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
    planar_yaw_to_quaternion_xyzw,
    quaternion_xyzw_to_planar_yaw,
    smooth_walking_nominal_step,
    smooth_walking_nominal_step_batch,
)
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
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


def _observable(
    *,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
    facing_deg: float = 0.0,
    angular_velocity_deg_s: float = 0.0,
    simulation_time_s: float = 10.0,
) -> SmoothWalkingObservableState:
    return SmoothWalkingObservableState(
        position_world_cm=np.asarray(position),
        velocity_world_cm_s=np.asarray(velocity),
        facing_yaw_rad=math.radians(facing_deg),
        angular_velocity_yaw_deg_s=angular_velocity_deg_s,
        simulation_time_s=simulation_time_s,
    )


def _internal(
    *,
    spring_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
    spring_acceleration: tuple[float, float, float] = (0.0, 0.0, 0.0),
    intermediate_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
    intermediate_facing_deg: float = 0.0,
    intermediate_angular_velocity_rad_s: float = 0.0,
) -> SmoothWalkingInternalState:
    return SmoothWalkingInternalState(
        velocity=SmoothWalkingVelocityState(
            spring_velocity_world_cm_s=np.asarray(spring_velocity),
            spring_acceleration_world_cm_s2=np.asarray(spring_acceleration),
            intermediate_velocity_world_cm_s=np.asarray(intermediate_velocity),
        ),
        facing=SmoothWalkingFacingState(
            intermediate_facing_yaw_rad=math.radians(intermediate_facing_deg),
            intermediate_angular_velocity_yaw_rad_s=intermediate_angular_velocity_rad_s,
        ),
    )


def _action(
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
    *,
    facing_deg: float = 0.0,
) -> SmoothWalkingAction:
    return SmoothWalkingAction(
        desired_velocity_world_cm_s=np.asarray(velocity),
        desired_facing_yaw_rad=math.radians(facing_deg),
    )


def test_stationary_equilibrium_advances_only_time(
    live_parameters: SmoothWalkingParameters,
) -> None:
    result = smooth_walking_nominal_step(
        _observable(position=(1.0, 2.0, 3.0), simulation_time_s=10.0),
        _internal(),
        _action(),
        parameters=live_parameters,
        dt_s=0.02,
    )

    np.testing.assert_array_equal(result.observable_next.position_world_cm, [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(result.observable_next.velocity_world_cm_s, [0.0, 0.0, 0.0])
    assert result.observable_next.facing_yaw_rad == 0.0
    assert result.observable_next.angular_velocity_yaw_deg_s == 0.0
    assert result.observable_next.simulation_time_s == pytest.approx(10.02)


def test_position_uses_new_proposed_velocity_explicit_euler(
    live_parameters: SmoothWalkingParameters,
) -> None:
    timestep = 0.01
    result = smooth_walking_nominal_step(
        _observable(position=(10.0, -2.0, 5.0)),
        _internal(),
        _action((100.0, 0.0, 0.0)),
        parameters=live_parameters,
        dt_s=timestep,
    )
    proposed_velocity = result.observable_next.velocity_world_cm_s

    np.testing.assert_allclose(
        result.observable_next.position_world_cm,
        np.asarray([10.0, -2.0, 5.0]) + proposed_velocity * timestep,
    )
    trapezoidal_x = 10.0 + 0.5 * proposed_velocity[0] * timestep
    assert result.observable_next.position_world_cm[0] != pytest.approx(trapezoidal_x)


def test_facing_uses_proposed_angular_velocity(
    live_parameters: SmoothWalkingParameters,
) -> None:
    timestep = 0.02
    result = smooth_walking_nominal_step(
        _observable(facing_deg=10.0),
        _internal(intermediate_facing_deg=10.0),
        _action(facing_deg=90.0),
        parameters=live_parameters,
        dt_s=timestep,
    )
    expected = math.radians(10.0 + result.observable_next.angular_velocity_yaw_deg_s * timestep)

    assert result.observable_next.facing_yaw_rad == pytest.approx(expected)
    assert result.observable_next.angular_velocity_yaw_deg_s > 0.0


def test_output_preserves_environment_boundary_label(
    live_parameters: SmoothWalkingParameters,
) -> None:
    # A collision is not an argument to this function. It predicts the proposal
    # that Unreal will subsequently attempt, leaving executed collision mismatch
    # to the observed next state and residual target.
    result = smooth_walking_nominal_step(
        _observable(velocity=(100.0, 0.0, 0.0)),
        _internal(
            spring_velocity=(100.0, 0.0, 0.0),
            intermediate_velocity=(100.0, 0.0, 0.0),
        ),
        _action((100.0, 0.0, 0.0)),
        parameters=live_parameters,
        dt_s=0.02,
    )

    assert result.observable_next.position_world_cm[0] > 0.0
    assert result.observable_next.velocity_world_cm_s[0] == pytest.approx(100.0)


@pytest.mark.parametrize("yaw_deg", [-179.0, -90.0, 0.0, 90.0, 179.0, 360.0])
def test_planar_yaw_quaternion_roundtrip(yaw_deg: float) -> None:
    yaw_rad = math.radians(yaw_deg)
    quaternion = planar_yaw_to_quaternion_xyzw(yaw_rad)
    recovered = quaternion_xyzw_to_planar_yaw(quaternion)
    expected = (yaw_rad + math.pi) % math.tau - math.pi

    assert recovered == pytest.approx(expected)
    assert np.linalg.norm(quaternion) == pytest.approx(1.0)


def test_quaternion_and_its_negation_have_same_yaw() -> None:
    quaternion = planar_yaw_to_quaternion_xyzw(math.radians(70.0))

    assert quaternion_xyzw_to_planar_yaw(quaternion) == pytest.approx(
        quaternion_xyzw_to_planar_yaw(-quaternion)
    )


def test_nonplanar_quaternion_fails_closed() -> None:
    roll_quaternion = [math.sin(0.25), 0.0, 0.0, math.cos(0.25)]

    with pytest.raises(ValueError, match="planar"):
        quaternion_xyzw_to_planar_yaw(roll_quaternion)


def test_batch_matches_repeated_scalar_transitions(
    live_parameters: SmoothWalkingParameters,
) -> None:
    observables = [_observable(), _observable(position=(10.0, 20.0, 0.0), facing_deg=30.0)]
    internals = [_internal(), _internal(intermediate_facing_deg=30.0)]
    actions = [_action((100.0, 0.0, 0.0)), _action((0.0, 80.0, 0.0), facing_deg=60.0)]
    parameters = [live_parameters, live_parameters]
    timesteps = [0.01, 0.02]
    batch = smooth_walking_nominal_step_batch(
        observables,
        internals,
        actions,
        parameters=parameters,
        dt_s=timesteps,
    )
    scalar = [
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
            timesteps,
            strict=True,
        )
    ]

    np.testing.assert_allclose(
        batch.position_world_cm,
        [step.observable_next.position_world_cm for step in scalar],
    )
    np.testing.assert_allclose(
        batch.velocity_world_cm_s,
        [step.observable_next.velocity_world_cm_s for step in scalar],
    )
    np.testing.assert_allclose(
        batch.facing_yaw_rad,
        [step.observable_next.facing_yaw_rad for step in scalar],
    )


def test_batch_rejects_length_mismatch(
    live_parameters: SmoothWalkingParameters,
) -> None:
    with pytest.raises(ValueError, match="equal lengths"):
        smooth_walking_nominal_step_batch(
            [_observable()],
            [],
            [_action()],
            parameters=[live_parameters],
            dt_s=[0.02],
        )


def test_empty_batch_fails_closed() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        smooth_walking_nominal_step_batch([], [], [], parameters=[], dt_s=[])
