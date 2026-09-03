"""Build translation-invariant planner queries from accepted episode snapshots."""

from __future__ import annotations

from typing import Any

import numpy as np

from motionworld.data.residual_manifest import AuditedEpisode
from motionworld.dynamics.nominal_episode import current_snapshot_nominal_inputs
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState
from motionworld.planning.cem import CEMConfig
from motionworld.planning.mpc import PlannerQuery
from motionworld.planning.planner_rollout import PlannerSnapshot


def build_counterfactual_query(
    source: AuditedEpisode,
    transition_index: int,
    *,
    problem_config: dict[str, Any],
    cem: CEMConfig,
) -> PlannerQuery:
    """Relocate one accepted state while retaining its causal dynamics context."""

    if isinstance(transition_index, bool) or not isinstance(transition_index, int):
        raise ValueError("transition_index must be an integer")
    if not 0 <= transition_index < len(source.episode.transitions):
        raise ValueError("transition_index is outside the accepted episode")
    transition = source.episode.transitions[transition_index]
    initial = current_snapshot_nominal_inputs(transition)
    preparation = transition["nominal_context"]["previous"]["input_preparation"]
    if not preparation["has_max_move_speed"]:
        raise ValueError("source snapshot must provide an effective max speed")
    effective_max_speed = float(preparation["effective_max_speed_cm_per_s"])
    if effective_max_speed != cem.max_action_speed_cm_s:
        raise ValueError("source and CEM effective maximum speeds differ")

    start = np.asarray(problem_config["counterfactual_start_world_cm"], dtype=np.float64)
    observable = SmoothWalkingObservableState(
        position_world_cm=np.asarray(
            [start[0], start[1], initial.observable.position_world_cm[2]],
            dtype=np.float64,
        ),
        velocity_world_cm_s=initial.observable.velocity_world_cm_s.copy(),
        facing_yaw_rad=initial.observable.facing_yaw_rad,
        angular_velocity_yaw_deg_s=initial.observable.angular_velocity_yaw_deg_s,
        simulation_time_s=0.0,
    )
    snapshot = PlannerSnapshot(
        observable=observable,
        internal=initial.internal,
        parameters=initial.parameters,
        effective_max_speed_cm_s=effective_max_speed,
    )
    mean_action = np.asarray(problem_config["initial_mean_action_local_cm_s"], dtype=np.float64)
    return PlannerQuery(
        snapshot=snapshot,
        scenario_time_s=float(problem_config["initial_scenario_time_s"]),
        previous_action_local_cm_s=problem_config["previous_action_local_cm_s"],
        previous_previous_action_local_cm_s=problem_config["previous_previous_action_local_cm_s"],
        initial_mean_knots_local_cm_s=np.tile(mean_action, (cem.num_knots, 1)),
    )
