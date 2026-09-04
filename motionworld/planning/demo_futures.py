"""Authentic, fixed-action future branches for the interview demo.

The paths in this module are direct outputs of the planner rollout.  It does not
interpolate, smooth, or otherwise manufacture points for presentation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.planning.planner_rollout import (
    PlannerRolloutConfig,
    PlannerSnapshot,
    rollout_action_candidates,
)

FloatArray = NDArray[np.float64]

# A branch includes its authoritative source point in addition to one point per
# rollout step. Keep the default and every caller-supplied horizon within the
# version-1 visualization protocol's 16-point path limit.
MAX_DEMO_HORIZON_STEPS = 15


class DemoBranchRole(StrEnum):
    """Semantic role of a counterfactual branch in the demo."""

    FORWARD = "forward"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"


DEMO_BRANCH_ORDER = (
    DemoBranchRole.FORWARD,
    DemoBranchRole.LEFT,
    DemoBranchRole.RIGHT,
    DemoBranchRole.STOP,
)


@dataclass(frozen=True, slots=True)
class DemoFuturesConfig:
    """Frozen horizon, integration cadence, and nonzero branch magnitude."""

    horizon_steps: int = 15
    plan_step_s: float = 0.1
    dynamics_substeps_per_plan_step: int = 3
    action_speed_cm_s: float = 120.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.horizon_steps, bool)
            or not isinstance(self.horizon_steps, int)
            or self.horizon_steps <= 0
        ):
            raise ValueError("horizon_steps must be a positive integer")
        if self.horizon_steps > MAX_DEMO_HORIZON_STEPS:
            raise ValueError(
                f"horizon_steps must not exceed {MAX_DEMO_HORIZON_STEPS} "
                "so the source point and rollout fit one visualization path"
            )
        if not math.isfinite(self.action_speed_cm_s) or self.action_speed_cm_s <= 0.0:
            raise ValueError("action_speed_cm_s must be positive and finite")
        # Reuse the production rollout validation for cadence fields.
        PlannerRolloutConfig(
            plan_step_s=self.plan_step_s,
            dynamics_substeps_per_plan_step=self.dynamics_substeps_per_plan_step,
        )

    @property
    def rollout_config(self) -> PlannerRolloutConfig:
        return PlannerRolloutConfig(
            plan_step_s=self.plan_step_s,
            dynamics_substeps_per_plan_step=self.dynamics_substeps_per_plan_step,
        )


@dataclass(frozen=True, slots=True)
class DemoFuture:
    """One tagged branch and its genuine Unreal-world XY rollout points."""

    role: DemoBranchRole
    requested_velocity_local_cm_s: tuple[float, float]
    points_world_cm: FloatArray


@dataclass(frozen=True, slots=True)
class DemoFutures:
    """Four counterfactuals produced together from one authoritative snapshot."""

    config: DemoFuturesConfig
    branches: tuple[DemoFuture, ...]
    dynamics_step_count: int
    residual_model_used: bool


def _branch_velocities(speed_cm_s: float) -> FloatArray:
    # MotionWorld local axes are +X forward and +Y right, so left is -Y.
    return np.asarray(
        (
            (speed_cm_s, 0.0),
            (0.0, -speed_cm_s),
            (0.0, speed_cm_s),
            (0.0, 0.0),
        ),
        dtype=np.float64,
    )


def generate_demo_futures(
    snapshot: PlannerSnapshot,
    *,
    config: DemoFuturesConfig | None = None,
    residual_model: ResidualMLP | None = None,
    residual_normalization: ResidualNormalization | None = None,
) -> DemoFutures:
    """Roll forward/left/right/stop branches in one shared production call.

    A single batched call guarantees that the production rollout clones the same
    snapshot for every branch.  Returned points contain the exact authoritative
    start followed by exact plan-boundary outputs; there is no display-only
    interpolation.  Arrays are read-only to protect the evidence/visualization
    seam from accidental mutation.
    """

    if config is None:
        config = DemoFuturesConfig()
    branch_velocities = _branch_velocities(config.action_speed_cm_s)
    actions = np.repeat(
        branch_velocities[:, np.newaxis, :],
        config.horizon_steps,
        axis=1,
    )
    rollout = rollout_action_candidates(
        snapshot,
        actions,
        config=config.rollout_config,
        residual_model=residual_model,
        residual_normalization=residual_normalization,
    )

    start = np.asarray(snapshot.observable.position_world_cm[:2], dtype=np.float64)
    branches: list[DemoFuture] = []
    for index, role in enumerate(DEMO_BRANCH_ORDER):
        points = np.concatenate((start[np.newaxis, :], rollout.positions_world_cm[index]), axis=0)
        points.setflags(write=False)
        requested = branch_velocities[index]
        branches.append(
            DemoFuture(
                role=role,
                requested_velocity_local_cm_s=(float(requested[0]), float(requested[1])),
                points_world_cm=points,
            )
        )

    return DemoFutures(
        config=config,
        branches=tuple(branches),
        dynamics_step_count=rollout.dynamics_step_count,
        residual_model_used=rollout.residual_model_used,
    )
