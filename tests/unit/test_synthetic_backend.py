import math

import pytest

from motionworld.dynamics.synthetic_backend import (
    SyntheticConfig,
    evaluate_synthetic_gate,
    reset_synthetic,
    run_synthetic_episode,
    step_synthetic,
)


def test_same_seed_produces_identical_reset() -> None:
    config = SyntheticConfig()

    assert reset_synthetic(config, seed=27116) == reset_synthetic(config, seed=27116)
    assert reset_synthetic(config, seed=27116) != reset_synthetic(config, seed=27117)


def test_gate_matches_analytic_quarter_period_example() -> None:
    config = SyntheticConfig(
        gate_x_cm=100.0,
        gate_y_origin_cm=200.0,
        gate_amplitude_cm=100.0,
        gate_period_s=4.0,
    )

    start = evaluate_synthetic_gate(config, scenario_time_s=0.0, phase_offset_rad=0.0)
    quarter = evaluate_synthetic_gate(config, scenario_time_s=1.0, phase_offset_rad=0.0)

    assert start.center_world_cm == pytest.approx((100.0, 200.0))
    assert start.velocity_world_cm_s == pytest.approx((0.0, 50.0 * math.pi))
    assert quarter.center_world_cm == pytest.approx((100.0, 300.0))
    assert quarter.velocity_world_cm_s == pytest.approx((0.0, 0.0), abs=1e-12)


def test_hidden_target_lags_requested_action_transparently() -> None:
    config = SyntheticConfig(start_y_jitter_cm=0.0, gate_x_cm=10_000.0)
    snapshot = reset_synthetic(config, seed=1)

    _, transition = step_synthetic(config, snapshot, (300.0, 0.0), episode_id=10)

    lagged_x = transition.next_hidden_state.lagged_target_velocity_cm_s[0]
    assert 0.0 < lagged_x < 300.0
    assert (
        transition.next_state.velocity_world_cm_s[0]
        <= config.max_acceleration_cm_s2 * config.dt_s
    )


def test_same_seed_and_actions_produce_identical_complete_episode() -> None:
    config = SyntheticConfig(gate_x_cm=10_000.0, timeout_s=2.0)
    actions = ((250.0, 0.0),) * 30

    first = run_synthetic_episode(config, seed=42, episode_id=100, actions_world_cm_s=actions)
    second = run_synthetic_episode(config, seed=42, episode_id=100, actions_world_cm_s=actions)

    assert first == second
    assert first.label == "SYNTHETIC / NOT UNREAL EVIDENCE"
    assert first.final_termination == "timeout"
    assert [row.sequence_id for row in first.transitions] == list(range(len(first.transitions)))


def test_action_outside_legal_range_fails_closed() -> None:
    config = SyntheticConfig(max_action_speed_cm_s=100.0)
    snapshot = reset_synthetic(config, seed=0)

    with pytest.raises(ValueError, match="legal"):
        step_synthetic(config, snapshot, (100.0, 100.0), episode_id=1)


def test_configured_push_occurs_once_at_declared_step() -> None:
    config = SyntheticConfig(
        gate_x_cm=10_000.0,
        push_step=1,
        push_velocity_delta_cm_s=(0.0, 100.0),
    )
    snapshot = reset_synthetic(config, seed=2)

    snapshot, first = step_synthetic(config, snapshot, (0.0, 0.0), episode_id=1)
    snapshot, second = step_synthetic(config, snapshot, (0.0, 0.0), episode_id=1)
    _, third = step_synthetic(config, snapshot, (0.0, 0.0), episode_id=1)

    assert first.applied_push_velocity_delta_cm_s == (0.0, 0.0)
    assert second.applied_push_velocity_delta_cm_s == (0.0, 100.0)
    assert third.applied_push_velocity_delta_cm_s == (0.0, 0.0)


def test_gate_collision_has_priority_over_success_crossing() -> None:
    config = SyntheticConfig(
        dt_s=1.0,
        max_acceleration_cm_s2=1000.0,
        hidden_lag_time_constant_s=0.001,
        start_x_cm=-10.0,
        start_y_jitter_cm=0.0,
        gate_x_cm=0.0,
        gate_amplitude_cm=0.0,
        gate_half_extents_cm=(20.0, 20.0),
        timeout_s=2.0,
    )
    snapshot = reset_synthetic(config, seed=0)

    _, transition = step_synthetic(config, snapshot, (30.0, 0.0), episode_id=1)

    assert transition.next_state.position_world_cm[0] > 0.0
    assert transition.collision is True
    assert transition.termination == "gate_collision"


def test_swept_collision_prevents_fast_step_tunnelling() -> None:
    config = SyntheticConfig(
        dt_s=1.0,
        max_action_speed_cm_s=300.0,
        max_acceleration_cm_s2=1000.0,
        hidden_lag_time_constant_s=0.001,
        start_x_cm=-100.0,
        start_y_jitter_cm=0.0,
        gate_x_cm=0.0,
        gate_amplitude_cm=0.0,
        gate_half_extents_cm=(5.0, 20.0),
        agent_radius_cm=1.0,
        timeout_s=2.0,
    )
    snapshot = reset_synthetic(config, seed=0)

    _, transition = step_synthetic(config, snapshot, (300.0, 0.0), episode_id=1)

    assert transition.next_state.position_world_cm[0] > 6.0
    assert transition.collision is True
    assert transition.termination == "gate_collision"


def test_step_after_terminal_fails_closed() -> None:
    config = SyntheticConfig(dt_s=1.0, gate_x_cm=10_000.0, timeout_s=1.0)
    snapshot = reset_synthetic(config, seed=0)
    snapshot, _ = step_synthetic(config, snapshot, (0.0, 0.0), episode_id=1)

    with pytest.raises(RuntimeError, match="terminated"):
        step_synthetic(config, snapshot, (0.0, 0.0), episode_id=1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dt_s": 0.0},
        {"hidden_lag_time_constant_s": 0.0},
        {"max_action_speed_cm_s": -1.0},
        {"gate_period_s": 0.0},
        {"push_step": -1},
        {"gate_amplitude_cm": math.nan},
    ],
)
def test_invalid_configuration_fails_closed(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        SyntheticConfig(**kwargs)  # type: ignore[arg-type]
