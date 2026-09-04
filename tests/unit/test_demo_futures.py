from __future__ import annotations

import math

import numpy as np
import pytest

from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
)
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
)
from motionworld.planning.demo_futures import (
    DEMO_BRANCH_ORDER,
    MAX_DEMO_HORIZON_STEPS,
    DemoBranchRole,
    DemoFuturesConfig,
    generate_demo_futures,
)
from motionworld.planning.planner_rollout import PlannerSnapshot, rollout_action_candidates
from motionworld.protocol.visualization import (
    MAX_POINTS_PER_PATH,
    TrajectoryRole,
    VisualizationPath,
    VisualizationPoint,
    VisualizationTelemetry,
    decode_visualization_json,
)


def _snapshot(*, facing_yaw_rad: float = 0.0) -> PlannerSnapshot:
    return PlannerSnapshot(
        observable=SmoothWalkingObservableState(
            position_world_cm=np.array([125.0, -40.0, 7.0]),
            velocity_world_cm_s=np.zeros(3),
            facing_yaw_rad=facing_yaw_rad,
            angular_velocity_yaw_deg_s=0.0,
            simulation_time_s=3.0,
        ),
        internal=SmoothWalkingInternalState(
            velocity=SmoothWalkingVelocityState(
                spring_velocity_world_cm_s=np.zeros(3),
                spring_acceleration_world_cm_s2=np.zeros(3),
                intermediate_velocity_world_cm_s=np.zeros(3),
            ),
            facing=SmoothWalkingFacingState(
                intermediate_facing_yaw_rad=facing_yaw_rad,
                intermediate_angular_velocity_yaw_rad_s=0.0,
            ),
        ),
        parameters=SmoothWalkingParameters(
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
        ),
        effective_max_speed_cm_s=165.0,
    )


def test_branches_are_tagged_and_share_the_bit_exact_authoritative_start() -> None:
    snapshot = _snapshot()
    before_arrays = (
        snapshot.observable.position_world_cm.copy(),
        snapshot.observable.velocity_world_cm_s.copy(),
        snapshot.internal.velocity.spring_velocity_world_cm_s.copy(),
        snapshot.internal.velocity.spring_acceleration_world_cm_s2.copy(),
        snapshot.internal.velocity.intermediate_velocity_world_cm_s.copy(),
    )
    before_scalars = (
        snapshot.observable.facing_yaw_rad,
        snapshot.observable.angular_velocity_yaw_deg_s,
        snapshot.observable.simulation_time_s,
        snapshot.internal.facing.intermediate_facing_yaw_rad,
        snapshot.internal.facing.intermediate_angular_velocity_yaw_rad_s,
    )
    futures = generate_demo_futures(snapshot)

    assert tuple(branch.role for branch in futures.branches) == DEMO_BRANCH_ORDER
    starts = tuple(branch.points_world_cm[0] for branch in futures.branches)
    for start in starts:
        np.testing.assert_array_equal(start, before_arrays[0][:2])
        assert start.tobytes() == starts[0].tobytes()
    after_arrays = (
        snapshot.observable.position_world_cm,
        snapshot.observable.velocity_world_cm_s,
        snapshot.internal.velocity.spring_velocity_world_cm_s,
        snapshot.internal.velocity.spring_acceleration_world_cm_s2,
        snapshot.internal.velocity.intermediate_velocity_world_cm_s,
    )
    for before, after in zip(before_arrays, after_arrays, strict=True):
        np.testing.assert_array_equal(after, before)
    assert before_scalars == (
        snapshot.observable.facing_yaw_rad,
        snapshot.observable.angular_velocity_yaw_deg_s,
        snapshot.observable.simulation_time_s,
        snapshot.internal.facing.intermediate_facing_yaw_rad,
        snapshot.internal.facing.intermediate_angular_velocity_yaw_rad_s,
    )


def test_points_are_exact_production_rollout_outputs_without_interpolation() -> None:
    snapshot = _snapshot()
    config = DemoFuturesConfig(
        horizon_steps=4,
        plan_step_s=0.2,
        dynamics_substeps_per_plan_step=2,
        action_speed_cm_s=90.0,
    )
    futures = generate_demo_futures(snapshot, config=config)
    velocities = np.asarray(((90.0, 0.0), (0.0, -90.0), (0.0, 90.0), (0.0, 0.0)))
    actions = np.repeat(velocities[:, np.newaxis, :], 4, axis=1)
    production = rollout_action_candidates(snapshot, actions, config=config.rollout_config)

    for index, branch in enumerate(futures.branches):
        assert branch.points_world_cm.shape == (5, 2)
        np.testing.assert_array_equal(
            branch.points_world_cm[1:],
            production.positions_world_cm[index],
        )
        assert not branch.points_world_cm.flags.writeable
    assert futures.dynamics_step_count == 8


def test_stop_is_exactly_zero_and_direction_roles_follow_local_axis_contract() -> None:
    futures = generate_demo_futures(_snapshot(), config=DemoFuturesConfig(horizon_steps=5))
    by_role = {branch.role: branch for branch in futures.branches}

    assert by_role[DemoBranchRole.STOP].requested_velocity_local_cm_s == (0.0, 0.0)
    np.testing.assert_array_equal(
        by_role[DemoBranchRole.STOP].points_world_cm,
        np.repeat(np.array([[125.0, -40.0]]), 6, axis=0),
    )
    assert by_role[DemoBranchRole.FORWARD].points_world_cm[-1, 0] > 125.0
    assert by_role[DemoBranchRole.LEFT].points_world_cm[-1, 1] < -40.0
    assert by_role[DemoBranchRole.RIGHT].points_world_cm[-1, 1] > -40.0


def test_direction_roles_rotate_from_character_local_axes_at_nonzero_yaw() -> None:
    origin = np.array([125.0, -40.0])
    futures = generate_demo_futures(
        _snapshot(facing_yaw_rad=math.pi / 2.0),
        config=DemoFuturesConfig(horizon_steps=5),
    )
    endpoints = {
        branch.role: branch.points_world_cm[-1] - origin for branch in futures.branches
    }

    # At +90 degrees, local forward is world +Y, local left initially drives
    # world +X, and local right initially drives world -X. The walking model
    # also turns its facing toward each lateral request, so lateral paths curve.
    assert endpoints[DemoBranchRole.FORWARD][1] > 0.0
    assert abs(endpoints[DemoBranchRole.FORWARD][0]) < 1.0e-9
    assert endpoints[DemoBranchRole.LEFT][0] > 0.0
    assert endpoints[DemoBranchRole.RIGHT][0] < 0.0
    assert abs(endpoints[DemoBranchRole.LEFT][0]) > abs(
        endpoints[DemoBranchRole.LEFT][1]
    )
    assert abs(endpoints[DemoBranchRole.RIGHT][0]) > abs(
        endpoints[DemoBranchRole.RIGHT][1]
    )
    assert endpoints[DemoBranchRole.LEFT][0] == pytest.approx(
        -endpoints[DemoBranchRole.RIGHT][0]
    )
    assert endpoints[DemoBranchRole.LEFT][1] == pytest.approx(
        endpoints[DemoBranchRole.RIGHT][1]
    )


def test_default_futures_fit_and_round_trip_through_visualization_telemetry() -> None:
    assert MAX_DEMO_HORIZON_STEPS + 1 == MAX_POINTS_PER_PATH
    futures = generate_demo_futures(_snapshot())
    roles = {
        DemoBranchRole.FORWARD: TrajectoryRole.BRANCH_FORWARD,
        DemoBranchRole.LEFT: TrajectoryRole.BRANCH_LEFT,
        DemoBranchRole.RIGHT: TrajectoryRole.BRANCH_RIGHT,
        DemoBranchRole.STOP: TrajectoryRole.BRANCH_STOP,
    }
    paths = tuple(
        VisualizationPath(
            role=roles[branch.role],
            points=tuple(
                VisualizationPoint(float(point[0]), float(point[1]))
                for point in branch.points_world_cm
            ),
        )
        for branch in futures.branches
    )
    telemetry = VisualizationTelemetry(
        episode_id=7310,
        source_observation_sequence=12,
        horizon_s=futures.config.horizon_steps * futures.config.plan_step_s,
        timestep_s=futures.config.plan_step_s,
        paths=paths,
    )

    assert all(len(path.points) == MAX_POINTS_PER_PATH for path in telemetry.paths)
    assert decode_visualization_json(telemetry.encode_json()) == telemetry


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("horizon_steps", 0, "horizon_steps"),
        ("horizon_steps", True, "horizon_steps"),
        ("horizon_steps", 16, "must not exceed 15"),
        ("plan_step_s", math.nan, "plan_step_s"),
        ("dynamics_substeps_per_plan_step", 0, "dynamics_substeps"),
        ("action_speed_cm_s", math.inf, "action_speed_cm_s"),
    ],
)
def test_invalid_frozen_demo_configuration_fails(field: str, value: object, message: str) -> None:
    kwargs = {field: value}
    with pytest.raises(ValueError, match=message):
        DemoFuturesConfig(**kwargs)
