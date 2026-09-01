import math

import numpy as np
import pytest

from motionworld.dynamics.bounded_velocity import (
    bounded_velocity_step,
    bounded_velocity_step_batch,
)


def test_zero_state_and_zero_request_remain_stationary() -> None:
    result = bounded_velocity_step(
        0.0,
        0.0,
        0.0,
        max_acceleration_cm_s2=800.0,
        dt_s=1.0 / 60.0,
    )

    assert result.position_next_cm == 0.0
    assert result.velocity_next_cm_s == 0.0
    assert result.acceleration_cm_s2 == 0.0


def test_acceleration_below_clamp_reaches_desired_velocity() -> None:
    result = bounded_velocity_step(
        0.0,
        0.0,
        5.0,
        max_acceleration_cm_s2=10.0,
        dt_s=1.0,
    )

    assert result.velocity_next_cm_s == 5.0
    assert result.acceleration_cm_s2 == 5.0
    assert result.position_next_cm == 2.5


def test_acceleration_at_clamp_uses_maximum_change() -> None:
    result = bounded_velocity_step(
        0.0,
        0.0,
        100.0,
        max_acceleration_cm_s2=10.0,
        dt_s=0.5,
    )

    assert result.velocity_next_cm_s == 5.0
    assert result.acceleration_cm_s2 == 10.0
    assert result.position_next_cm == 1.25


def test_theory_hand_calculation_matches_oracle() -> None:
    result = bounded_velocity_step(
        0.0,
        200.0,
        500.0,
        max_acceleration_cm_s2=800.0,
        dt_s=1.0 / 60.0,
    )

    assert result.velocity_next_cm_s == pytest.approx(213.33333333333334)
    assert result.position_next_cm == pytest.approx(3.4444444444444446)
    assert result.acceleration_cm_s2 == pytest.approx(800.0)


def test_deceleration_reaches_zero_without_overshoot() -> None:
    result = bounded_velocity_step(
        0.0,
        3.0,
        0.0,
        max_acceleration_cm_s2=10.0,
        dt_s=1.0,
    )

    assert result.velocity_next_cm_s == 0.0
    assert result.acceleration_cm_s2 == -3.0
    assert result.position_next_cm == 1.5


def test_direction_reversal_reaches_negative_target_without_overshoot() -> None:
    result = bounded_velocity_step(
        0.0,
        10.0,
        -10.0,
        max_acceleration_cm_s2=30.0,
        dt_s=1.0,
    )

    assert result.velocity_next_cm_s == -10.0
    assert result.acceleration_cm_s2 == -20.0
    assert result.position_next_cm == 0.0


def test_requested_speed_is_limited_before_acceleration_update() -> None:
    result = bounded_velocity_step(
        0.0,
        0.0,
        1000.0,
        max_acceleration_cm_s2=1000.0,
        max_speed_cm_s=100.0,
        dt_s=1.0,
    )

    assert result.desired_velocity_limited_cm_s == 100.0
    assert result.velocity_next_cm_s == 100.0
    assert result.position_next_cm == 50.0


def test_observed_speed_above_limit_is_not_instantly_erased() -> None:
    result = bounded_velocity_step(
        0.0,
        150.0,
        1000.0,
        max_acceleration_cm_s2=10.0,
        max_speed_cm_s=100.0,
        dt_s=1.0,
    )

    assert result.desired_velocity_limited_cm_s == 100.0
    assert result.velocity_next_cm_s == 140.0
    assert result.acceleration_cm_s2 == -10.0


def test_zero_acceleration_preserves_observed_velocity() -> None:
    result = bounded_velocity_step(
        5.0,
        12.0,
        -50.0,
        max_acceleration_cm_s2=0.0,
        dt_s=0.25,
    )

    assert result.velocity_next_cm_s == 12.0
    assert result.position_next_cm == 8.0


def test_batch_matches_repeated_scalar_calls() -> None:
    positions = np.asarray((0.0, 10.0, -5.0))
    velocities = np.asarray((0.0, 20.0, -10.0))
    desired = np.asarray((50.0, 0.0, 30.0))

    batch = bounded_velocity_step_batch(
        positions,
        velocities,
        desired,
        max_acceleration_cm_s2=20.0,
        dt_s=0.5,
    )
    scalar = [
        bounded_velocity_step(
            float(position),
            float(velocity),
            float(target),
            max_acceleration_cm_s2=20.0,
            dt_s=0.5,
        )
        for position, velocity, target in zip(positions, velocities, desired, strict=True)
    ]

    np.testing.assert_allclose(batch.position_next_cm, [step.position_next_cm for step in scalar])
    np.testing.assert_allclose(
        batch.velocity_next_cm_s,
        [step.velocity_next_cm_s for step in scalar],
    )
    np.testing.assert_allclose(
        batch.acceleration_cm_s2,
        [step.acceleration_cm_s2 for step in scalar],
    )


def test_fixed_seed_batch_respects_equation_invariants() -> None:
    generator = np.random.default_rng(27116)
    positions = generator.uniform(-1000.0, 1000.0, size=1024)
    velocities = generator.uniform(-700.0, 700.0, size=1024)
    desired = generator.uniform(-1000.0, 1000.0, size=1024)
    acceleration_limit = 800.0
    timestep = 1.0 / 60.0

    result = bounded_velocity_step_batch(
        positions,
        velocities,
        desired,
        max_acceleration_cm_s2=acceleration_limit,
        max_speed_cm_s=500.0,
        dt_s=timestep,
    )

    velocity_change = result.velocity_next_cm_s - velocities
    assert np.all(np.abs(velocity_change) <= acceleration_limit * timestep + 1e-12)
    np.testing.assert_allclose(
        result.position_next_cm,
        positions + 0.5 * (velocities + result.velocity_next_cm_s) * timestep,
    )
    assert np.all(np.abs(result.desired_velocity_limited_cm_s) <= 500.0)


@pytest.mark.parametrize("dt_s", [0.0, -0.1, math.nan, math.inf])
def test_invalid_timestep_fails_closed(dt_s: float) -> None:
    with pytest.raises(ValueError):
        bounded_velocity_step(0.0, 0.0, 0.0, max_acceleration_cm_s2=1.0, dt_s=dt_s)


@pytest.mark.parametrize("acceleration", [-1.0, math.nan, math.inf])
def test_invalid_acceleration_fails_closed(acceleration: float) -> None:
    with pytest.raises(ValueError):
        bounded_velocity_step(
            0.0,
            0.0,
            0.0,
            max_acceleration_cm_s2=acceleration,
            dt_s=1.0,
        )


@pytest.mark.parametrize("max_speed", [0.0, -1.0, math.nan, math.inf])
def test_invalid_optional_speed_limit_fails_closed(max_speed: float) -> None:
    with pytest.raises(ValueError):
        bounded_velocity_step(
            0.0,
            0.0,
            0.0,
            max_acceleration_cm_s2=1.0,
            max_speed_cm_s=max_speed,
            dt_s=1.0,
        )


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", ["position", "velocity", "desired"])
def test_nonfinite_state_or_request_fails_closed(invalid: float, field: str) -> None:
    values = {"position": 0.0, "velocity": 0.0, "desired": 0.0}
    values[field] = invalid

    with pytest.raises(ValueError):
        bounded_velocity_step(
            values["position"],
            values["velocity"],
            values["desired"],
            max_acceleration_cm_s2=1.0,
            dt_s=1.0,
        )


def test_batch_shape_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="equal shapes"):
        bounded_velocity_step_batch(
            (0.0, 1.0),
            (0.0,),
            (0.0, 1.0),
            max_acceleration_cm_s2=1.0,
            dt_s=1.0,
        )


def test_batch_rejects_scalar_inputs() -> None:
    with pytest.raises(ValueError, match="non-scalar batch"):
        bounded_velocity_step_batch(
            0.0,
            0.0,
            0.0,
            max_acceleration_cm_s2=1.0,
            dt_s=1.0,
        )


def test_batch_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        bounded_velocity_step_batch(
            (0.0, math.nan),
            (0.0, 0.0),
            (0.0, 0.0),
            max_acceleration_cm_s2=1.0,
            dt_s=1.0,
        )
