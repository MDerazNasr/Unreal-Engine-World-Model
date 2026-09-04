"""Identity-safe glue from live snapshots to authentic demo telemetry."""

from __future__ import annotations

import numpy as np

from motionworld.control.live_planner_adapter import LivePlannerSnapshot
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.planning.demo_futures import (
    DEMO_BRANCH_ORDER,
    DemoBranchRole,
    DemoFutures,
    DemoFuturesConfig,
    generate_demo_futures,
)
from motionworld.protocol.visualization import (
    TrajectoryRole,
    VisualizationPath,
    VisualizationPoint,
    VisualizationTelemetry,
)

_TRAJECTORY_ROLE_BY_BRANCH = {
    DemoBranchRole.FORWARD: TrajectoryRole.BRANCH_FORWARD,
    DemoBranchRole.LEFT: TrajectoryRole.BRANCH_LEFT,
    DemoBranchRole.RIGHT: TrajectoryRole.BRANCH_RIGHT,
    DemoBranchRole.STOP: TrajectoryRole.BRANCH_STOP,
}


def visualization_from_live_demo_futures(
    live_snapshot: LivePlannerSnapshot,
    futures: DemoFutures,
) -> VisualizationTelemetry:
    """Attach genuine future branches to their authoritative live identity.

    Identity is deliberately not accepted as a separate argument.  The strict
    seam also rejects a malformed or misattached bundle before it can be drawn
    as if it came from the current Unreal observation.
    """

    if not isinstance(live_snapshot, LivePlannerSnapshot):
        raise TypeError("live_snapshot must be a LivePlannerSnapshot")
    if not isinstance(futures, DemoFutures):
        raise TypeError("futures must be DemoFutures")

    config = futures.config
    if not isinstance(config, DemoFuturesConfig):
        raise ValueError("futures.config must be a DemoFuturesConfig")
    if tuple(branch.role for branch in futures.branches) != DEMO_BRANCH_ORDER:
        raise ValueError("demo futures must contain each branch exactly once in frozen order")
    expected_dynamics_steps = config.horizon_steps * config.dynamics_substeps_per_plan_step
    if futures.dynamics_step_count != expected_dynamics_steps:
        raise ValueError("demo futures dynamics step count disagrees with its configuration")

    expected_start = np.asarray(
        live_snapshot.snapshot.observable.position_world_cm[:2], dtype=np.float64
    )
    expected_point_count = config.horizon_steps + 1
    paths: list[VisualizationPath] = []
    for branch in futures.branches:
        points = branch.points_world_cm
        if not isinstance(points, np.ndarray) or points.dtype != np.float64:
            raise ValueError("demo future points must be float64 numpy arrays")
        if points.shape != (expected_point_count, 2):
            raise ValueError("demo future point count disagrees with its configuration")
        if not np.array_equal(points[0], expected_start):
            raise ValueError("demo future does not start at the authoritative live state")
        paths.append(
            VisualizationPath(
                role=_TRAJECTORY_ROLE_BY_BRANCH[branch.role],
                points=tuple(
                    VisualizationPoint(x_cm=float(point[0]), y_cm=float(point[1]))
                    for point in points
                ),
            )
        )

    telemetry = VisualizationTelemetry(
        episode_id=live_snapshot.episode_id,
        source_observation_sequence=live_snapshot.observation_sequence,
        horizon_s=config.horizon_steps * config.plan_step_s,
        timestep_s=config.plan_step_s,
        paths=tuple(paths),
    )
    # Enforce the production transport budget at this seam, not later in a UI caller.
    telemetry.encode_json()
    return telemetry


def generate_live_branch_visualization(
    live_snapshot: LivePlannerSnapshot,
    *,
    config: DemoFuturesConfig | None = None,
    residual_model: ResidualMLP | None = None,
    residual_normalization: ResidualNormalization | None = None,
) -> VisualizationTelemetry:
    """Generate and identity-bind four genuine branches in one safe operation."""

    if not isinstance(live_snapshot, LivePlannerSnapshot):
        raise TypeError("live_snapshot must be a LivePlannerSnapshot")
    futures = generate_demo_futures(
        live_snapshot.snapshot,
        config=config,
        residual_model=residual_model,
        residual_normalization=residual_normalization,
    )
    return visualization_from_live_demo_futures(live_snapshot, futures)
