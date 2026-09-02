import math
from itertools import pairwise

import numpy as np
import pytest

from motionworld.dynamics.smooth_walking_math import (
    UE_KINDA_SMALL_NUMBER,
    UE_SMALL_NUMBER,
    critical_spring_damper,
    critical_spring_damper_angle,
    exponential_smoothing_approx,
    find_delta_angle_radians,
    inv_exp_approx,
    smoothing_time_to_damping,
    strength_to_smoothing_time,
)


def test_inv_exp_matches_hand_calculation() -> None:
    expected = 1.0 / (1.0 + 1.00746054 + 0.45053901 + 0.25724632)

    assert inv_exp_approx(0.0) == 1.0
    assert inv_exp_approx(1.0) == pytest.approx(expected)


def test_inv_exp_decreases_for_nonnegative_inputs() -> None:
    values = [inv_exp_approx(x) for x in np.linspace(0.0, 10.0, num=101)]

    assert all(left > right for left, right in pairwise(values))
    assert values[-1] > 0.0


def test_exponential_smoothing_matches_hand_calculation() -> None:
    result = exponential_smoothing_approx(2.0, 10.0, dt_s=0.05, smoothing_time_s=0.1)
    expected = 10.0 + (2.0 - 10.0) * inv_exp_approx(0.5)

    assert float(result) == pytest.approx(expected)


def test_exponential_smoothing_handles_vectors_componentwise() -> None:
    result = exponential_smoothing_approx(
        [0.0, 10.0, -4.0],
        [10.0, 0.0, 2.0],
        dt_s=0.025,
        smoothing_time_s=0.1,
    )
    decay = inv_exp_approx(0.25)

    np.testing.assert_allclose(
        result,
        np.asarray([10.0, 0.0, 2.0])
        + (np.asarray([0.0, 10.0, -4.0]) - np.asarray([10.0, 0.0, 2.0])) * decay,
    )


def test_exponential_smoothing_uses_unreal_snap_threshold() -> None:
    result = exponential_smoothing_approx(
        [1.0, 2.0],
        [5.0, 6.0],
        dt_s=0.01,
        smoothing_time_s=UE_KINDA_SMALL_NUMBER,
    )

    np.testing.assert_array_equal(result, [5.0, 6.0])


def test_critical_spring_matches_hand_calculation() -> None:
    # x=0, v=0, target=10, smoothing time=.2, dt=.05:
    # y=2/T=10; j0=x-target=-10; j1=v+j0*y=-100; decay=InvExp(.5).
    result = critical_spring_damper(
        0.0,
        0.0,
        10.0,
        smoothing_time_s=0.2,
        dt_s=0.05,
    )
    decay = inv_exp_approx(0.5)

    assert float(result.value_next) == pytest.approx(decay * (-10.0 - 5.0) + 10.0)
    assert float(result.velocity_next) == pytest.approx(decay * 50.0)


def test_critical_spring_vector_matches_independent_scalar_steps() -> None:
    values = np.asarray([0.0, 3.0, -2.0])
    velocities = np.asarray([0.0, -1.0, 4.0])
    targets = np.asarray([10.0, -3.0, 5.0])
    vector = critical_spring_damper(
        values,
        velocities,
        targets,
        smoothing_time_s=0.4,
        dt_s=0.02,
    )
    scalars = [
        critical_spring_damper(
            value,
            velocity,
            target,
            smoothing_time_s=0.4,
            dt_s=0.02,
        )
        for value, velocity, target in zip(values, velocities, targets, strict=True)
    ]

    np.testing.assert_allclose(vector.value_next, [float(step.value_next) for step in scalars])
    np.testing.assert_allclose(
        vector.velocity_next,
        [float(step.velocity_next) for step in scalars],
    )


def test_critical_spring_equilibrium_does_not_move() -> None:
    result = critical_spring_damper(
        [2.0, -5.0],
        [0.0, 0.0],
        [2.0, -5.0],
        smoothing_time_s=0.3,
        dt_s=1.0 / 60.0,
    )

    np.testing.assert_array_equal(result.value_next, [2.0, -5.0])
    np.testing.assert_array_equal(result.velocity_next, [0.0, 0.0])


def test_critical_spring_zero_timestep_is_identity() -> None:
    result = critical_spring_damper(
        [2.0, -5.0],
        [4.0, 8.0],
        [100.0, 100.0],
        smoothing_time_s=0.3,
        dt_s=0.0,
    )

    np.testing.assert_array_equal(result.value_next, [2.0, -5.0])
    np.testing.assert_array_equal(result.velocity_next, [4.0, 8.0])


def test_critical_spring_uses_strict_unreal_snap_threshold() -> None:
    snapped = critical_spring_damper(
        1.0,
        7.0,
        5.0,
        smoothing_time_s=np.nextafter(UE_SMALL_NUMBER, 0.0),
        dt_s=0.01,
    )
    integrated = critical_spring_damper(
        1.0,
        7.0,
        5.0,
        smoothing_time_s=UE_SMALL_NUMBER,
        dt_s=0.01,
    )

    assert float(snapped.value_next) == 5.0
    assert float(snapped.velocity_next) == 0.0
    assert float(integrated.value_next) != 5.0


def test_angle_delta_takes_shortest_path_across_wrap_boundary() -> None:
    assert math.degrees(
        find_delta_angle_radians(math.radians(179.0), math.radians(-179.0))
    ) == pytest.approx(2.0)
    assert math.degrees(
        find_delta_angle_radians(math.radians(-179.0), math.radians(179.0))
    ) == pytest.approx(-2.0)


def test_angle_spring_moves_across_wrap_boundary_on_short_path() -> None:
    current = math.radians(179.0)
    target = math.radians(-179.0)
    result = critical_spring_damper_angle(
        current,
        0.0,
        target,
        smoothing_time_s=0.4,
        dt_s=0.05,
    )

    movement = find_delta_angle_radians(current, result.angle_next_rad)
    remaining = find_delta_angle_radians(result.angle_next_rad, target)
    assert movement > 0.0
    assert 0.0 < remaining < math.radians(2.0)


def test_parameter_conversion_matches_unreal_equations() -> None:
    assert smoothing_time_to_damping(0.4) == pytest.approx(10.0)
    assert strength_to_smoothing_time(8.0) == pytest.approx(0.25)
    assert smoothing_time_to_damping(0.0) == pytest.approx(4.0 / UE_SMALL_NUMBER)
    assert strength_to_smoothing_time(0.0) == pytest.approx(2.0 / UE_SMALL_NUMBER)


@pytest.mark.parametrize("invalid", [-1.0, math.nan, math.inf])
@pytest.mark.parametrize(
    "function",
    [
        inv_exp_approx,
        smoothing_time_to_damping,
        strength_to_smoothing_time,
    ],
)
def test_scalar_helpers_reject_invalid_inputs(invalid: float, function: object) -> None:
    with pytest.raises(ValueError):
        function(invalid)  # type: ignore[operator]


def test_smoothing_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="equal shapes"):
        exponential_smoothing_approx([1.0, 2.0], [1.0], dt_s=0.1, smoothing_time_s=0.2)


def test_spring_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="equal shapes"):
        critical_spring_damper(
            [1.0, 2.0],
            [0.0],
            [3.0, 4.0],
            smoothing_time_s=0.2,
            dt_s=0.1,
        )


@pytest.mark.parametrize("invalid", [-0.1, math.nan, math.inf])
def test_spring_rejects_invalid_timestep(invalid: float) -> None:
    with pytest.raises(ValueError):
        critical_spring_damper(
            0.0,
            0.0,
            1.0,
            smoothing_time_s=0.2,
            dt_s=invalid,
        )
