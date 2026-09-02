from __future__ import annotations

import math

import numpy as np
import pytest

from motionworld.planning.cem import (
    CEMConfig,
    CEMState,
    expand_action_knots,
    optimize_cem,
    project_velocity_actions,
    sample_standard_normal_schedule,
    shift_action_knots,
    update_elite_distribution,
)


def test_fixed_seed_reproduces_noise_and_complete_solution() -> None:
    config = CEMConfig(
        num_candidates=64,
        num_elites=8,
        num_iterations=3,
        num_knots=2,
        num_plan_steps=4,
    )

    def cost(actions: np.ndarray) -> np.ndarray:
        return np.sum(np.square(actions - np.array([40.0, -25.0])), axis=(1, 2))

    first = optimize_cem(cost, config=config, seed=17)
    second = optimize_cem(cost, config=config, seed=17)
    np.testing.assert_array_equal(
        sample_standard_normal_schedule(config, seed=17),
        sample_standard_normal_schedule(config, seed=17),
    )
    np.testing.assert_array_equal(first.first_action_cm_s, second.first_action_cm_s)
    np.testing.assert_array_equal(first.best_knots_cm_s, second.best_knots_cm_s)
    assert first.best_cost == second.best_cost


def test_mean_candidate_is_exactly_zero_noise() -> None:
    config = CEMConfig(num_candidates=4, num_elites=1, num_iterations=2)
    noise = sample_standard_normal_schedule(config, seed=3)
    np.testing.assert_array_equal(noise[:, 0], 0.0)


def test_hand_computed_elite_mean_variance_and_momentum() -> None:
    old = CEMState(
        mean_knots_cm_s=np.array([[10.0, 20.0]]),
        std_knots_cm_s=np.array([[4.0, 6.0]]),
    )
    elites = np.array([[[2.0, 4.0]], [[6.0, 12.0]]])
    result = update_elite_distribution(
        old,
        elites,
        momentum=0.25,
        minimum_std_cm_s=0.0,
    )
    # Elite mean [4, 8], population variance [4, 16].
    np.testing.assert_allclose(result.mean_knots_cm_s, [[5.5, 11.0]])
    np.testing.assert_allclose(
        result.std_knots_cm_s,
        [[math.sqrt(7.0), math.sqrt(21.0)]],
    )


def test_quadratic_toy_optimum_is_recovered_within_sampling_tolerance() -> None:
    config = CEMConfig(
        num_candidates=1024,
        num_elites=64,
        num_iterations=6,
        num_knots=1,
        num_plan_steps=1,
        initial_std_cm_s=100.0,
        minimum_std_cm_s=0.1,
        momentum=0.0,
    )
    optimum = np.array([60.0, -35.0])

    def cost(actions: np.ndarray) -> np.ndarray:
        return np.sum(np.square(actions[:, 0, :] - optimum), axis=1)

    result = optimize_cem(cost, config=config, seed=2026)
    assert not result.used_safe_fallback
    np.testing.assert_allclose(result.first_action_cm_s, optimum, atol=0.15)


def test_velocity_projection_preserves_inside_and_scales_outside_norm() -> None:
    actions = np.array([[3.0, 4.0], [300.0, 400.0], [0.0, 0.0]])
    projected = project_velocity_actions(actions, maximum_speed_cm_s=10.0)
    np.testing.assert_allclose(projected[0], [3.0, 4.0])
    np.testing.assert_allclose(projected[1], [6.0, 8.0])
    np.testing.assert_array_equal(projected[2], [0.0, 0.0])
    assert np.all(np.linalg.norm(projected, axis=-1) <= 10.0)


def test_every_optimizer_candidate_respects_speed_ball() -> None:
    config = CEMConfig(
        num_candidates=32,
        num_elites=4,
        num_iterations=3,
        num_knots=3,
        num_plan_steps=7,
        max_action_speed_cm_s=20.0,
        initial_std_cm_s=1.0e6,
    )
    seen: list[np.ndarray] = []

    def cost(actions: np.ndarray) -> np.ndarray:
        seen.append(actions.copy())
        return np.sum(np.square(actions), axis=(1, 2))

    optimize_cem(cost, config=config, seed=9)
    assert len(seen) == config.num_iterations
    for candidates in seen:
        assert np.max(np.linalg.norm(candidates, axis=-1)) <= 20.0


def test_expansion_uses_piecewise_constant_balanced_intervals() -> None:
    knots = np.array([[[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]])
    expanded = expand_action_knots(knots, num_plan_steps=8)
    np.testing.assert_array_equal(expanded[0, :, 0], [1, 1, 1, 2, 2, 2, 3, 3])


def test_warm_start_shift_drops_executed_and_repeats_tail() -> None:
    knots = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0], [4.0, 40.0]])
    shifted = shift_action_knots(knots, executed_knots=1)
    np.testing.assert_array_equal(
        shifted,
        [[2.0, 20.0], [3.0, 30.0], [4.0, 40.0], [4.0, 40.0]],
    )


def test_lowest_cost_candidate_is_selected() -> None:
    config = CEMConfig(
        num_candidates=3,
        num_elites=1,
        num_iterations=1,
        num_knots=1,
        num_plan_steps=1,
        initial_std_cm_s=1.0,
        minimum_std_cm_s=0.0,
        momentum=0.0,
        include_mean_candidate=False,
    )
    noise = np.array([[[[2.0, 0.0]], [[-1.0, 0.0]], [[0.5, 0.0]]]])

    def cost(actions: np.ndarray) -> np.ndarray:
        return np.array([10.0, -4.0, 3.0])

    result = optimize_cem(cost, config=config, standard_normal_noise=noise)
    np.testing.assert_array_equal(result.first_action_cm_s, [-1.0, 0.0])
    assert result.best_cost == -4.0


def test_batched_and_scalar_quadratic_cost_ordering_agree() -> None:
    generator = np.random.default_rng(81)
    actions = generator.normal(size=(12, 5, 2))
    goal = np.array([0.25, -0.75])
    batched = np.sum(np.square(actions - goal), axis=(1, 2))
    scalar = np.array(
        [
            sum(float(np.dot(step - goal, step - goal)) for step in candidate)
            for candidate in actions
        ]
    )
    np.testing.assert_allclose(batched, scalar)
    np.testing.assert_array_equal(np.argsort(batched), np.argsort(scalar))


def test_reusable_noise_gives_identical_first_iteration_candidates() -> None:
    config = CEMConfig(
        num_candidates=16,
        num_elites=4,
        num_iterations=2,
        num_knots=2,
        num_plan_steps=2,
    )
    noise = sample_standard_normal_schedule(config, seed=44)
    first = optimize_cem(
        lambda actions: np.sum(np.square(actions - 10.0), axis=(1, 2)),
        config=config,
        standard_normal_noise=noise,
    )
    second = optimize_cem(
        lambda actions: np.sum(np.square(actions + 10.0), axis=(1, 2)),
        config=config,
        standard_normal_noise=noise,
    )
    np.testing.assert_array_equal(
        first.iterations[0].candidate_first_actions_cm_s,
        second.iterations[0].candidate_first_actions_cm_s,
    )
    assert not np.array_equal(
        first.iterations[1].candidate_first_actions_cm_s,
        second.iterations[1].candidate_first_actions_cm_s,
    )


def test_variance_floor_stabilizes_identical_elites() -> None:
    old = CEMState(np.zeros((2, 2)), np.zeros((2, 2)))
    elites = np.zeros((4, 2, 2))
    result = update_elite_distribution(
        old,
        elites,
        momentum=0.0,
        minimum_std_cm_s=3.0,
    )
    np.testing.assert_array_equal(result.std_knots_cm_s, 3.0)


def test_nonfinite_costs_are_ignored_or_trigger_safe_zero_fallback() -> None:
    config = CEMConfig(
        num_candidates=4,
        num_elites=2,
        num_iterations=1,
        num_knots=1,
        num_plan_steps=1,
    )
    partly_valid = optimize_cem(
        lambda _: np.array([math.nan, 2.0, 1.0, math.inf]),
        config=config,
        seed=1,
    )
    assert not partly_valid.used_safe_fallback
    invalid = optimize_cem(
        lambda _: np.array([math.nan, 2.0, math.inf, math.inf]),
        config=config,
        seed=1,
    )
    assert invalid.used_safe_fallback
    np.testing.assert_array_equal(invalid.first_action_cm_s, [0.0, 0.0])
    assert invalid.best_cost == math.inf


def test_cost_shape_is_checked() -> None:
    config = CEMConfig(num_candidates=4, num_elites=1, num_iterations=1)
    with pytest.raises(ValueError, match="cost_function"):
        optimize_cem(lambda _: np.zeros(3), config=config, seed=0)


@pytest.mark.parametrize(
    "changes",
    [
        {"num_candidates": 0},
        {"num_candidates": 2, "num_elites": 3},
        {"momentum": 1.0},
        {"minimum_std_cm_s": -1.0},
        {"max_action_speed_cm_s": math.nan},
        {"action_dim": 1},
        {"num_knots": 1.5},
        {"include_mean_candidate": 1},
    ],
)
def test_invalid_configurations_fail(changes: dict[str, float | int | bool]) -> None:
    with pytest.raises(ValueError):
        CEMConfig(**changes)


def test_invalid_seed_type_fails_before_numpy() -> None:
    with pytest.raises(ValueError, match="seed"):
        sample_standard_normal_schedule(CEMConfig(), seed=1.5)  # type: ignore[arg-type]
