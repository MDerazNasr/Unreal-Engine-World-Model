from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from motionworld.control.demo_telemetry import (
    generate_live_branch_visualization,
    visualization_from_live_demo_futures,
)
from motionworld.control.live_planner_adapter import LivePlannerSnapshot
from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
)
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
)
from motionworld.planning.demo_futures import DemoFuturesConfig, generate_demo_futures
from motionworld.planning.planner_rollout import PlannerSnapshot
from motionworld.protocol.visualization import (
    MAX_POINTS_PER_PATH,
    MAX_VISUALIZATION_BYTES,
    TrajectoryRole,
)


def _live_snapshot() -> LivePlannerSnapshot:
    zeros = np.zeros(3, dtype=np.float64)
    snapshot = PlannerSnapshot(
        observable=SmoothWalkingObservableState(
            position_world_cm=np.array([125.0, -40.0, 7.0]),
            velocity_world_cm_s=zeros.copy(),
            facing_yaw_rad=0.0,
            angular_velocity_yaw_deg_s=0.0,
            simulation_time_s=3.0,
        ),
        internal=SmoothWalkingInternalState(
            velocity=SmoothWalkingVelocityState(
                spring_velocity_world_cm_s=zeros.copy(),
                spring_acceleration_world_cm_s2=zeros.copy(),
                intermediate_velocity_world_cm_s=zeros.copy(),
            ),
            facing=SmoothWalkingFacingState(
                intermediate_facing_yaw_rad=0.0,
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
    return LivePlannerSnapshot(
        snapshot=snapshot,
        episode_id=7310,
        observation_sequence=12,
        state_sample_sequence=91,
        previous_action_local_cm_s=(10.0, 20.0),
        previous_previous_action_local_cm_s=(5.0, 10.0),
        target_world_xy_cm=(500.0, 200.0),
        scenario_time_s=1.2,
    )


def test_convenience_glue_binds_identity_sampling_roles_and_source_point() -> None:
    live = _live_snapshot()
    before_position = live.snapshot.observable.position_world_cm.copy()
    telemetry = generate_live_branch_visualization(live)

    assert telemetry.episode_id == 7310
    assert telemetry.source_observation_sequence == 12
    assert telemetry.horizon_s == pytest.approx(1.5)
    assert telemetry.timestep_s == pytest.approx(0.1)
    assert tuple(path.role for path in telemetry.paths) == (
        TrajectoryRole.BRANCH_FORWARD,
        TrajectoryRole.BRANCH_LEFT,
        TrajectoryRole.BRANCH_RIGHT,
        TrajectoryRole.BRANCH_STOP,
    )
    assert all(len(path.points) == MAX_POINTS_PER_PATH == 16 for path in telemetry.paths)
    assert all(
        (path.points[0].x_cm, path.points[0].y_cm) == (125.0, -40.0) for path in telemetry.paths
    )
    assert len(telemetry.encode_json()) <= MAX_VISUALIZATION_BYTES
    np.testing.assert_array_equal(live.snapshot.observable.position_world_cm, before_position)


def test_glue_preserves_inputs_and_supports_valid_shorter_frozen_configuration() -> None:
    live = _live_snapshot()
    config = DemoFuturesConfig(horizon_steps=4, plan_step_s=0.2)
    futures = generate_demo_futures(live.snapshot, config=config)
    before = tuple(branch.points_world_cm.copy() for branch in futures.branches)

    telemetry = visualization_from_live_demo_futures(live, futures)

    assert telemetry.horizon_s == pytest.approx(0.8)
    assert telemetry.timestep_s == pytest.approx(0.2)
    assert all(len(path.points) == 5 for path in telemetry.paths)
    for original, branch in zip(before, futures.branches, strict=True):
        np.testing.assert_array_equal(branch.points_world_cm, original)
        assert not branch.points_world_cm.flags.writeable


def test_glue_rejects_futures_misattached_to_another_live_source() -> None:
    live = _live_snapshot()
    futures = generate_demo_futures(live.snapshot)
    other_observable = replace(
        live.snapshot.observable,
        position_world_cm=np.array([126.0, -40.0, 7.0]),
    )
    other = replace(live, snapshot=replace(live.snapshot, observable=other_observable))

    with pytest.raises(ValueError, match="authoritative live state"):
        visualization_from_live_demo_futures(other, futures)


def test_glue_rejects_configuration_inconsistent_metadata() -> None:
    live = _live_snapshot()
    futures = generate_demo_futures(live.snapshot)
    malformed = replace(futures, dynamics_step_count=futures.dynamics_step_count + 1)

    with pytest.raises(ValueError, match="dynamics step count"):
        visualization_from_live_demo_futures(live, malformed)
