from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
import torch

from motionworld.models.residual_features import RESIDUAL_STEP_FEATURE_COUNT
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.planning.cem import CEMConfig, sample_standard_normal_schedule
from motionworld.planning.cost import PlanningCostWeights, TimedGateGeometry
from motionworld.planning.mpc import (
    PlannerProblem,
    PlannerQuery,
    plan_model,
    plan_paired_nominal_residual,
)
from motionworld.planning.planner_rollout import PlannerRolloutConfig
from tests.unit.test_planner_rollout import _normalization, _snapshot


def _problem() -> PlannerProblem:
    return PlannerProblem(
        cem=CEMConfig(
            num_candidates=32,
            num_elites=4,
            num_iterations=2,
            num_knots=2,
            num_plan_steps=3,
            initial_std_cm_s=80.0,
            minimum_std_cm_s=2.0,
            momentum=0.1,
        ),
        rollout=PlannerRolloutConfig(plan_step_s=0.5, dynamics_substeps_per_plan_step=2),
        geometry=TimedGateGeometry(
            gate_x_cm=10_000.0,
            gate_y_origin_cm=0.0,
            gate_amplitude_cm=0.0,
            gate_period_s=4.0,
            gate_phase_offset_rad=0.0,
            gate_half_extent_x_cm=30.0,
            gate_half_extent_y_cm=150.0,
            agent_radius_cm=42.0,
            safety_margin_cm=20.0,
        ),
        weights=PlanningCostWeights(
            terminal_goal_per_cm=1.0,
            collision=10_000.0,
            clearance_per_cm2=0.0,
            action_change_per_cm2_s2=0.0,
            action_second_difference_per_cm2_s2=0.0,
        ),
        goal_world_cm=(100.0, 0.0),
    )


def _query() -> PlannerQuery:
    return PlannerQuery(
        snapshot=_snapshot(),
        scenario_time_s=0.0,
        previous_action_local_cm_s=(0.0, 0.0),
        previous_previous_action_local_cm_s=(0.0, 0.0),
    )


def test_nominal_planner_returns_reproducible_forward_action_and_cost() -> None:
    problem = _problem()
    noise = sample_standard_normal_schedule(problem.cem, seed=8)
    first = plan_model(
        problem,
        _query(),
        standard_normal_noise=noise,
        model_name="nominal",
    )
    second = plan_model(
        problem,
        _query(),
        standard_normal_noise=noise,
        model_name="nominal",
    )
    assert first.cem.first_action_cm_s[0] > 0.0
    np.testing.assert_array_equal(first.cem.first_action_cm_s, second.cem.first_action_cm_s)
    assert first.cem.best_cost == second.cem.best_cost
    assert first.evaluated_action_sha256 == second.evaluated_action_sha256
    assert first.best_cost.total[0] == pytest.approx(first.cem.best_cost)
    assert abs(first.selected_cost_reproduction_error) <= 1.0e-4


def test_zero_residual_paired_plans_are_exactly_identical() -> None:
    model = ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,))
    paired = plan_paired_nominal_residual(
        _problem(),
        _query(),
        seed=19,
        residual_model=model,
        residual_normalization=_normalization(),
    )
    assert paired.fairness_verified
    assert paired.first_iteration_candidates_identical
    assert paired.nominal.evaluated_action_sha256 == paired.residual.evaluated_action_sha256
    np.testing.assert_array_equal(
        paired.nominal.cem.first_action_cm_s,
        paired.residual.cem.first_action_cm_s,
    )
    np.testing.assert_array_equal(
        paired.nominal.best_rollout.positions_world_cm,
        paired.residual.best_rollout.positions_world_cm,
    )


def test_nonzero_residual_keeps_common_first_candidates_but_can_change_plan() -> None:
    model = ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,))
    with torch.no_grad():
        model.output.bias[0] = 4.0
    paired = plan_paired_nominal_residual(
        _problem(),
        _query(),
        seed=23,
        residual_model=model,
        residual_normalization=_normalization(),
    )
    assert paired.first_iteration_candidates_identical
    assert paired.nominal.evaluated_action_sha256[0] == paired.residual.evaluated_action_sha256[0]
    assert not np.array_equal(
        paired.nominal.best_rollout.positions_world_cm,
        paired.residual.best_rollout.positions_world_cm,
    )


def test_wrong_model_boundary_fails_closed() -> None:
    problem = _problem()
    noise = sample_standard_normal_schedule(problem.cem, seed=1)
    model = ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,))
    with pytest.raises(ValueError, match="nominal plan"):
        plan_model(
            problem,
            _query(),
            standard_normal_noise=noise,
            model_name="nominal",
            residual_model=model,
            residual_normalization=_normalization(),
        )
    with pytest.raises(ValueError, match="requires"):
        plan_model(
            problem,
            _query(),
            standard_normal_noise=noise,
            model_name="residual",
        )


def test_cem_and_snapshot_speed_limits_must_match() -> None:
    problem = _problem()
    mismatched = PlannerQuery(
        snapshot=replace(_snapshot(), effective_max_speed_cm_s=120.0),
        scenario_time_s=0.0,
        previous_action_local_cm_s=(0.0, 0.0),
        previous_previous_action_local_cm_s=(0.0, 0.0),
    )
    with pytest.raises(ValueError, match="speed limits"):
        plan_model(
            problem,
            mismatched,
            standard_normal_noise=sample_standard_normal_schedule(problem.cem, seed=1),
            model_name="nominal",
        )
