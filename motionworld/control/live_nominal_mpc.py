"""Stateless, fixed-noise nominal MPC for the gate-free interview demo."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from motionworld.control.live_planner_adapter import planner_snapshot_from_observation
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.planning.cem import expand_action_knots, sample_standard_normal_schedule
from motionworld.planning.mpc import PlannerProblem, plan_model
from motionworld.planning.planner_rollout import PlannerRolloutConfig
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
    residual_overlay_model: ResidualMLP | None = None
    residual_overlay_normalization: ResidualNormalization | None = None
    residual_overlay_rollout: PlannerRolloutConfig | None = None
    residual_overlay_steps: int | None = None

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
        overlay_values = (
            self.residual_overlay_model,
            self.residual_overlay_normalization,
            self.residual_overlay_rollout,
            self.residual_overlay_steps,
        )
        if any(value is None for value in overlay_values) != all(
            value is None for value in overlay_values
        ):
            raise ValueError("residual overlay model, normalization, and rollout are atomic")
        if self.residual_overlay_model is not None:
            if not isinstance(self.residual_overlay_model, ResidualMLP):
                raise TypeError("residual_overlay_model must be a ResidualMLP")
            if not isinstance(self.residual_overlay_normalization, ResidualNormalization):
                raise TypeError("residual_overlay_normalization must be ResidualNormalization")
            if not isinstance(self.residual_overlay_rollout, PlannerRolloutConfig):
                raise TypeError("residual_overlay_rollout must be PlannerRolloutConfig")
            if self.residual_overlay_model.input_width != 28:
                raise ValueError("live residual overlay requires the no-history model")
            if self.residual_overlay_normalization.history_length != 1:
                raise ValueError("live residual overlay requires no-history normalization")
            if (
                self.residual_overlay_rollout.plan_step_s
                != self.problem_template.rollout.plan_step_s
            ):
                raise ValueError("overlay and planner sampling timesteps must match")
            if (
                type(self.residual_overlay_steps) is not int
                or not 1
                <= self.residual_overlay_steps
                <= self.problem_template.cem.num_plan_steps
            ):
                raise ValueError("residual overlay step count is out of range")


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
                residual_model=self.config.residual_overlay_model,
                residual_normalization=self.config.residual_overlay_normalization,
                overlay_rollout=self.config.residual_overlay_rollout,
                overlay_steps=self.config.residual_overlay_steps,
                cancelled=cancelled,
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
        action = _action(
            observation,
            selected,
            started_us=started_us,
            model_id=(
                "nominal_mpc_matched_residual_overlay_v1"
                if self.config.residual_overlay_model is not None
                else "smooth_walking_nominal_mpc_v1"
            ),
        )
        action["telemetry"] = {
            "is_present": True,
            "visualization": visualization.to_json_object(),
        }
        return action


def _visualization(
    live,
    problem,
    plan,
    *,
    winner_count: int,
    residual_model: ResidualMLP | None = None,
    residual_normalization: ResidualNormalization | None = None,
    overlay_rollout: PlannerRolloutConfig | None = None,
    overlay_steps: int | None = None,
    cancelled: threading.Event | None = None,
) -> VisualizationTelemetry:
    start = np.asarray(live.snapshot.observable.position_world_cm[:2], dtype=np.float64)

    def path(role: TrajectoryRole, predicted: np.ndarray) -> VisualizationPath:
        points = np.concatenate((start[np.newaxis, :], predicted), axis=0)
        return VisualizationPath(
            role=role,
            points=tuple(VisualizationPoint(float(point[0]), float(point[1])) for point in points),
        )

    if residual_model is None:
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
        paths = tuple(
            path(TrajectoryRole.CEM_CANDIDATE, candidates.positions_world_cm[index])
            for index in range(winner_count)
        )
        paths += (path(TrajectoryRole.SELECTED, plan.best_rollout.positions_world_cm[0]),)
    else:
        if (
            residual_normalization is None
            or overlay_rollout is None
            or overlay_steps is None
        ):
            raise ValueError("residual overlay inputs must be supplied atomically")
        selected_actions = np.asarray(
            plan.cem.best_actions_cm_s[:overlay_steps], dtype=np.float64
        )
        matched = np.broadcast_to(selected_actions, (2, *selected_actions.shape)).copy()
        nominal_overlay = rollout_action_candidates_vectorized(
            live.snapshot,
            matched[:1],
            config=overlay_rollout,
        )
        if cancelled is not None and cancelled.is_set():
            raise _CancelledOverlay
        residual_overlay = rollout_action_candidates_vectorized(
            live.snapshot,
            matched[1:],
            config=overlay_rollout,
            residual_model=residual_model,
            residual_normalization=residual_normalization,
        )
        if cancelled is not None and cancelled.is_set():
            raise _CancelledOverlay
        # D6 is a dedicated matched-model view. Avoid computing or transmitting
        # D5 candidate previews: they have a different point count and consume
        # deadline margin without contributing to this comparison.
        paths = (
            path(TrajectoryRole.NOMINAL, nominal_overlay.positions_world_cm[0]),
            path(TrajectoryRole.RESIDUAL, residual_overlay.positions_world_cm[0]),
        )
        horizon_s = overlay_steps * overlay_rollout.plan_step_s
    if residual_model is None:
        horizon_s = problem.cem.num_plan_steps * problem.rollout.plan_step_s
    telemetry = VisualizationTelemetry(
        episode_id=live.episode_id,
        source_observation_sequence=live.observation_sequence,
        horizon_s=horizon_s,
        timestep_s=(overlay_rollout or problem.rollout).plan_step_s,
        paths=paths,
    )
    telemetry.encode_json()
    return telemetry


class _CancelledOverlay(Exception):
    """Internal signal; the controller suppresses publication for superseded work."""


def _action(
    observation: Observation,
    desired_velocity: tuple[float, float],
    *,
    started_us: int,
    fallback_reason: str = "none",
    model_id: str = "smooth_walking_nominal_mpc_v1",
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
            "model_id": model_id,
        },
        "planner": {
            "started_monotonic_us": started_us,
            "finished_monotonic_us": finished_us,
            "measured_latency_ms": (finished_us - started_us) / 1_000.0,
        },
        "fallback": {"is_safe_fallback": is_fallback, "reason": fallback_reason},
        "telemetry": {"is_present": False},
    }
