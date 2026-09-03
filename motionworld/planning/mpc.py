"""Fair paired CEM-MPC orchestration for nominal and residual dynamics."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.planning.cem import (
    CEMConfig,
    CEMResult,
    optimize_cem,
    sample_standard_normal_schedule,
)
from motionworld.planning.cost import (
    PlanningCostBreakdown,
    PlanningCostWeights,
    TimedGateGeometry,
    evaluate_planning_cost,
)
from motionworld.planning.planner_rollout import (
    PlannerRollout,
    PlannerRolloutConfig,
    PlannerSnapshot,
    rollout_action_candidates,
)
from motionworld.planning.vectorized_rollout import rollout_action_candidates_vectorized

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class PlannerProblem:
    """Every fairness-critical setting shared by the compared controllers."""

    cem: CEMConfig
    rollout: PlannerRolloutConfig
    geometry: TimedGateGeometry
    weights: PlanningCostWeights
    goal_world_cm: tuple[float, float]
    rollout_backend: str = "vectorized"

    def __post_init__(self) -> None:
        goal = np.asarray(self.goal_world_cm, dtype=np.float64)
        if goal.shape != (2,) or not np.all(np.isfinite(goal)):
            raise ValueError("goal_world_cm must contain exactly two finite values")
        if not math.isclose(
            self.cem.num_plan_steps * self.rollout.plan_step_s,
            1.5,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("P0 planner horizon must be exactly 1.5 seconds")
        if self.rollout_backend not in {"scalar_reference", "vectorized"}:
            raise ValueError("rollout_backend must be scalar_reference or vectorized")


@dataclass(frozen=True, slots=True)
class PlannerQuery:
    """One replanning observation and action history."""

    snapshot: PlannerSnapshot
    scenario_time_s: float
    previous_action_local_cm_s: tuple[float, float]
    previous_previous_action_local_cm_s: tuple[float, float]
    initial_mean_knots_local_cm_s: FloatArray | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.scenario_time_s) or self.scenario_time_s < 0.0:
            raise ValueError("scenario_time_s must be finite and non-negative")
        for name, value in (
            ("previous_action_local_cm_s", self.previous_action_local_cm_s),
            ("previous_previous_action_local_cm_s", self.previous_previous_action_local_cm_s),
        ):
            array = np.asarray(value, dtype=np.float64)
            if array.shape != (2,) or not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must contain exactly two finite values")


@dataclass(frozen=True, slots=True)
class ModelPlan:
    """One controller's selected action, trajectory, and audit trail."""

    model_name: str
    cem: CEMResult
    best_rollout: PlannerRollout
    best_cost: PlanningCostBreakdown
    evaluated_action_sha256: tuple[str, ...]
    selected_cost_reproduction_error: float


@dataclass(frozen=True, slots=True)
class PairedPlan:
    nominal: ModelPlan
    residual: ModelPlan
    common_noise_sha256: str
    first_iteration_candidates_identical: bool
    fairness_verified: bool


def _array_sha256(values: FloatArray) -> str:
    array = np.ascontiguousarray(values, dtype="<f8")
    digest = hashlib.sha256()
    digest.update(str(array.shape).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _scenario_times(problem: PlannerProblem, query: PlannerQuery) -> FloatArray:
    return query.scenario_time_s + problem.rollout.plan_step_s * np.arange(
        1,
        problem.cem.num_plan_steps + 1,
        dtype=np.float64,
    )


def _rollout_candidates(
    problem: PlannerProblem,
    query: PlannerQuery,
    actions_local_cm_s: FloatArray,
    *,
    residual_model: ResidualMLP | None,
    residual_normalization: ResidualNormalization | None,
) -> PlannerRollout:
    rollout_function = (
        rollout_action_candidates_vectorized
        if problem.rollout_backend == "vectorized"
        else rollout_action_candidates
    )
    return rollout_function(
        query.snapshot,
        actions_local_cm_s,
        config=problem.rollout,
        residual_model=residual_model,
        residual_normalization=residual_normalization,
    )


def plan_model(
    problem: PlannerProblem,
    query: PlannerQuery,
    *,
    standard_normal_noise: FloatArray,
    model_name: str,
    residual_model: ResidualMLP | None = None,
    residual_normalization: ResidualNormalization | None = None,
) -> ModelPlan:
    """Solve one model-specific CEM plan under an otherwise shared problem/query."""

    if model_name not in {"nominal", "residual"}:
        raise ValueError("model_name must be nominal or residual")
    if model_name == "nominal" and (
        residual_model is not None or residual_normalization is not None
    ):
        raise ValueError("nominal plan cannot receive a residual model")
    if model_name == "residual" and (residual_model is None or residual_normalization is None):
        raise ValueError("residual plan requires its model and normalization")
    if not math.isclose(
        problem.cem.max_action_speed_cm_s,
        query.snapshot.effective_max_speed_cm_s,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError("CEM and snapshot effective speed limits must match")

    goal = np.asarray(problem.goal_world_cm, dtype=np.float64)
    previous = np.asarray(query.previous_action_local_cm_s, dtype=np.float64)
    previous_previous = np.asarray(
        query.previous_previous_action_local_cm_s,
        dtype=np.float64,
    )
    times = _scenario_times(problem, query)
    initial_position = np.asarray(
        query.snapshot.observable.position_world_cm[:2],
        dtype=np.float64,
    )
    action_hashes: list[str] = []

    def cost_function(actions_local_cm_s: FloatArray) -> FloatArray:
        action_hashes.append(_array_sha256(actions_local_cm_s))
        rollout = _rollout_candidates(
            problem,
            query,
            actions_local_cm_s,
            residual_model=residual_model,
            residual_normalization=residual_normalization,
        )
        return evaluate_planning_cost(
            rollout.positions_world_cm,
            actions_local_cm_s,
            initial_position_world_cm=initial_position,
            previous_action_cm_s=previous,
            previous_previous_action_cm_s=previous_previous,
            goal_world_cm=goal,
            initial_scenario_time_s=query.scenario_time_s,
            scenario_times_s=times,
            geometry=problem.geometry,
            weights=problem.weights,
        ).total

    cem = optimize_cem(
        cost_function,
        config=problem.cem,
        standard_normal_noise=standard_normal_noise,
        initial_mean_knots_cm_s=query.initial_mean_knots_local_cm_s,
    )
    best_actions = cem.best_actions_cm_s[np.newaxis, :, :]
    best_rollout = _rollout_candidates(
        problem,
        query,
        best_actions,
        residual_model=residual_model,
        residual_normalization=residual_normalization,
    )
    best_cost = evaluate_planning_cost(
        best_rollout.positions_world_cm,
        best_actions,
        initial_position_world_cm=initial_position,
        previous_action_cm_s=previous,
        previous_previous_action_cm_s=previous_previous,
        goal_world_cm=goal,
        initial_scenario_time_s=query.scenario_time_s,
        scenario_times_s=times,
        geometry=problem.geometry,
        weights=problem.weights,
    )
    cost_reproduction_error = float(best_cost.total[0]) - cem.best_cost
    if not cem.used_safe_fallback and not math.isclose(
        cem.best_cost,
        float(best_cost.total[0]),
        rel_tol=1.0e-7,
        abs_tol=1.0e-4,
    ):
        raise RuntimeError(
            "selected trajectory cost does not reproduce the CEM ranking; "
            f"ranked={cem.best_cost:.17g}, reevaluated={float(best_cost.total[0]):.17g}, "
            f"difference={float(best_cost.total[0]) - cem.best_cost:.17g}"
        )
    return ModelPlan(
        model_name=model_name,
        cem=cem,
        best_rollout=best_rollout,
        best_cost=best_cost,
        evaluated_action_sha256=tuple(action_hashes),
        selected_cost_reproduction_error=cost_reproduction_error,
    )


def plan_paired_nominal_residual(
    problem: PlannerProblem,
    query: PlannerQuery,
    *,
    seed: int,
    residual_model: ResidualMLP,
    residual_normalization: ResidualNormalization,
) -> PairedPlan:
    """Run both adaptive solvers with one shared query, config, cost, and random tensor."""

    noise = sample_standard_normal_schedule(problem.cem, seed=seed)
    nominal = plan_model(
        problem,
        query,
        standard_normal_noise=noise,
        model_name="nominal",
    )
    residual = plan_model(
        problem,
        query,
        standard_normal_noise=noise,
        model_name="residual",
        residual_model=residual_model,
        residual_normalization=residual_normalization,
    )
    if not nominal.evaluated_action_sha256 or not residual.evaluated_action_sha256:
        raise RuntimeError("both controllers must evaluate at least one candidate batch")
    identical_first = nominal.evaluated_action_sha256[0] == residual.evaluated_action_sha256[0]
    if not identical_first:
        raise RuntimeError("nominal and residual first-iteration candidates differ")
    return PairedPlan(
        nominal=nominal,
        residual=residual,
        common_noise_sha256=_array_sha256(noise),
        first_iteration_candidates_identical=identical_first,
        fairness_verified=True,
    )
