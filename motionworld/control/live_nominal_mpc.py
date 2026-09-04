"""Stateless, fixed-noise nominal MPC for the gate-free interview demo."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from motionworld.control.live_planner_adapter import planner_snapshot_from_observation
from motionworld.planning.cem import expand_action_knots, sample_standard_normal_schedule
from motionworld.planning.mpc import PlannerProblem, plan_model
from motionworld.planning.vectorized_rollout import rollout_action_candidates_vectorized
from motionworld.protocol.visualization import (
    TrajectoryRole,
    VisualizationPath,
    VisualizationPoint,
    VisualizationTelemetry,
)

Observation = dict[str, Any]
Action = dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class LiveNominalMPCConfig:
    """Immutable runtime inputs for one reproducible nominal MPC solve."""

    problem_template: PlannerProblem
    seed: int
    preview_iteration_winners: int = 3
    initial_mean_action_local_cm_s: tuple[float, float] = (130.0, 0.0)

    def __post_init__(self) -> None:
        if not isinstance(self.problem_template, PlannerProblem):
            raise TypeError("problem_template must be a PlannerProblem")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        count = self.preview_iteration_winners
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 3:
            raise ValueError("preview_iteration_winners must be an integer in [1, 3]")
        if count > self.problem_template.cem.num_iterations:
            raise ValueError("preview_iteration_winners exceeds the CEM iteration count")
        if self.problem_template.cem.num_knots != 5:
            raise ValueError("live nominal MPC requires exactly five action knots")
        if self.problem_template.rollout_backend != "vectorized":
            raise ValueError("live nominal MPC requires the vectorized rollout backend")
        weights = self.problem_template.weights
        if (
            weights.collision != 0.0
            or weights.clearance_per_cm2 != 0.0
            or weights.action_second_difference_per_cm2_s2 != 0.0
        ):
            raise ValueError(
                "live nominal MPC requires exact zero collision, clearance, "
                "and action-second-difference weights"
            )
        if not isinstance(self.initial_mean_action_local_cm_s, tuple) or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in self.initial_mean_action_local_cm_s
        ):
            raise ValueError("initial_mean_action_local_cm_s must be an immutable numeric tuple")
        action = np.asarray(self.initial_mean_action_local_cm_s, dtype=np.float64)
        if action.shape != (2,) or not np.all(np.isfinite(action)):
            raise ValueError("initial_mean_action_local_cm_s must contain two finite values")
        if np.linalg.norm(action) > self.problem_template.cem.max_action_speed_cm_s:
            raise ValueError("initial mean action exceeds the CEM speed limit")


@dataclass(frozen=True, slots=True)
class LiveNominalMPCController:
    """Run independent nominal MPC solves and emit only the first selected action."""

    config: LiveNominalMPCConfig

    def __call__(self, observation: Observation, cancelled: threading.Event) -> Action:
        if cancelled.is_set():
            return None
        started_us = time.monotonic_ns() // 1_000
        try:
            live = planner_snapshot_from_observation(observation)
            problem = replace(
                self.config.problem_template,
                goal_world_cm=live.target_world_xy_cm,
            )
            query = live.to_stateless_mpc_query(problem)
            query = replace(
                query,
                initial_mean_knots_local_cm_s=np.tile(
                    np.asarray(self.config.initial_mean_action_local_cm_s, dtype=np.float64),
                    (5, 1),
                ),
            )
        except (TypeError, ValueError):
            return _action(
                observation,
                (0.0, 0.0),
                started_us=started_us,
                fallback_reason="invalid_observation",
            )
        if cancelled.is_set():
            return None

        try:
            noise = sample_standard_normal_schedule(problem.cem, seed=self.config.seed)
            plan = plan_model(
                problem,
                query,
                standard_normal_noise=noise,
                model_name="nominal",
            )
            if cancelled.is_set():
                return None
            if plan.cem.used_safe_fallback:
                return _action(
                    observation,
                    (0.0, 0.0),
                    started_us=started_us,
                    fallback_reason="no_feasible_candidate",
                )
            visualization = _visualization(
                live,
                problem,
                plan,
                winner_count=self.config.preview_iteration_winners,
            )
        except Exception:
            if cancelled.is_set():
                return None
            return _action(
                observation,
                (0.0, 0.0),
                started_us=started_us,
                fallback_reason="planner_error",
            )
        if cancelled.is_set():
            return None

        selected = tuple(float(value) for value in plan.cem.first_action_cm_s)
        action = _action(observation, selected, started_us=started_us)
        action["telemetry"] = {
            "is_present": True,
            "visualization": visualization.to_json_object(),
        }
        return action


def _visualization(live, problem, plan, *, winner_count: int) -> VisualizationTelemetry:
    iteration_actions = np.stack(
        [
            expand_action_knots(
                iteration.best_knots_cm_s,
                num_plan_steps=problem.cem.num_plan_steps,
            )
            for iteration in plan.cem.iterations[:winner_count]
        ]
    )
    candidates = rollout_action_candidates_vectorized(
        live.snapshot,
        iteration_actions,
        config=problem.rollout,
    )
    start = np.asarray(live.snapshot.observable.position_world_cm[:2], dtype=np.float64)

    def path(role: TrajectoryRole, predicted: np.ndarray) -> VisualizationPath:
        points = np.concatenate((start[np.newaxis, :], predicted), axis=0)
        return VisualizationPath(
            role=role,
            points=tuple(VisualizationPoint(float(point[0]), float(point[1])) for point in points),
        )

    paths = tuple(
        path(TrajectoryRole.CEM_CANDIDATE, candidates.positions_world_cm[index])
        for index in range(winner_count)
    ) + (path(TrajectoryRole.SELECTED, plan.best_rollout.positions_world_cm[0]),)
    telemetry = VisualizationTelemetry(
        episode_id=live.episode_id,
        source_observation_sequence=live.observation_sequence,
        horizon_s=problem.cem.num_plan_steps * problem.rollout.plan_step_s,
        timestep_s=problem.rollout.plan_step_s,
        paths=paths,
    )
    telemetry.encode_json()
    return telemetry


def _action(
    observation: Observation,
    desired_velocity: tuple[float, float],
    *,
    started_us: int,
    fallback_reason: str = "none",
) -> dict[str, Any]:
    finished_us = time.monotonic_ns() // 1_000
    identity = observation["identity"]
    is_fallback = fallback_reason != "none"
    return {
        "protocol": {
            "name": "motionworld_control",
            "version": 1,
            "message_type": "action",
        },
        "identity": {
            "episode_id": identity["episode_id"],
            "source_observation_sequence": identity["observation_sequence"],
        },
        "command": {"desired_velocity_local_cm_per_s": list(desired_velocity)},
        "controller": {
            "controller_id": "nominal_mpc",
            "model_id": "smooth_walking_nominal_mpc_v1",
        },
        "planner": {
            "started_monotonic_us": started_us,
            "finished_monotonic_us": finished_us,
            "measured_latency_ms": (finished_us - started_us) / 1_000.0,
        },
        "fallback": {"is_safe_fallback": is_fallback, "reason": fallback_reason},
        "telemetry": {"is_present": False},
    }
