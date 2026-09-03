from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from motionworld.planning.budget_sweep import (
    derive_cem_config,
    load_cem_budget_sweep,
    nested_standard_normal_noise,
    select_eligible_budget,
)
from motionworld.planning.cem import CEMConfig, sample_standard_normal_schedule

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_frozen_sweep_preserves_elite_fraction_and_reference_limits() -> None:
    sweep = load_cem_budget_sweep(REPOSITORY_ROOT / "configs" / "cem_budget_sweep.yaml")
    assert len(sweep.validation_queries) == 10
    assert len(sweep.candidates) == 8
    assert sweep.reference.num_candidates == 256
    assert all(
        candidate.num_elites * 8 == candidate.num_candidates for candidate in sweep.candidates
    )
    assert sweep.deadline_ms == 100.0


def test_derived_config_changes_only_budget_counts() -> None:
    base = CEMConfig(num_knots=5, num_plan_steps=15)
    sweep = load_cem_budget_sweep(REPOSITORY_ROOT / "configs" / "cem_budget_sweep.yaml")
    result = derive_cem_config(base, sweep.candidates[0])
    assert result.num_candidates == 64
    assert result.num_elites == 8
    assert result.num_iterations == 2
    assert result.num_knots == base.num_knots
    assert result.max_action_speed_cm_s == base.max_action_speed_cm_s


def test_nested_noise_is_exact_reference_prefix() -> None:
    reference = CEMConfig(
        num_candidates=16,
        num_elites=2,
        num_iterations=3,
        num_knots=2,
        num_plan_steps=4,
    )
    noise = sample_standard_normal_schedule(reference, seed=4)
    reduced = replace(reference, num_candidates=8, num_elites=1, num_iterations=2)
    nested = nested_standard_normal_noise(noise, config=reduced)
    np.testing.assert_array_equal(nested, noise[:2, :8])


def test_selector_uses_declared_quality_then_runtime_order() -> None:
    records = [
        {
            "name": "fast",
            "eligible": True,
            "worst_model_mean_positive_relative_regret": 0.03,
            "runtime": {"residual": {"p95_ms": 60.0}},
        },
        {
            "name": "accurate",
            "eligible": True,
            "worst_model_mean_positive_relative_regret": 0.01,
            "runtime": {"residual": {"p95_ms": 90.0}},
        },
        {
            "name": "ineligible",
            "eligible": False,
            "worst_model_mean_positive_relative_regret": 0.0,
            "runtime": {"residual": {"p95_ms": 10.0}},
        },
    ]
    assert select_eligible_budget(records) == "accurate"
    assert select_eligible_budget([{**records[0], "eligible": False}]) is None


def test_nested_noise_rejects_insufficient_reference() -> None:
    with pytest.raises(ValueError, match="does not cover"):
        nested_standard_normal_noise(
            np.zeros((1, 2, 5, 2)),
            config=CEMConfig(
                num_candidates=3,
                num_elites=1,
                num_iterations=1,
                num_knots=5,
                num_plan_steps=15,
            ),
        )
