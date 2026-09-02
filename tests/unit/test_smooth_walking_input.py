import math

import numpy as np
import pytest

from motionworld.dynamics.smooth_walking_input import prepare_velocity_input


def test_request_below_limit_is_unchanged() -> None:
    result = prepare_velocity_input([3.0, 4.0, 0.0], effective_max_speed_cm_s=10.0)

    np.testing.assert_array_equal(result.desired_velocity_world_cm_s, [3.0, 4.0, 0.0])
    assert not result.was_clamped


def test_request_above_limit_preserves_direction_and_clamps_norm() -> None:
    result = prepare_velocity_input([300.0, 400.0, 0.0], effective_max_speed_cm_s=165.0)

    np.testing.assert_allclose(result.desired_velocity_world_cm_s, [99.0, 132.0, 0.0])
    assert np.linalg.norm(result.desired_velocity_world_cm_s) == pytest.approx(165.0)
    assert result.was_clamped


def test_zero_limit_returns_zero_for_nonzero_request() -> None:
    result = prepare_velocity_input([100.0, 0.0, 0.0], effective_max_speed_cm_s=0.0)

    np.testing.assert_array_equal(result.desired_velocity_world_cm_s, [0.0, 0.0, 0.0])
    assert result.was_clamped


@pytest.mark.parametrize("invalid", [-1.0, math.nan, math.inf])
def test_invalid_limit_fails_closed(invalid: float) -> None:
    with pytest.raises(ValueError):
        prepare_velocity_input([0.0, 0.0, 0.0], effective_max_speed_cm_s=invalid)


def test_invalid_request_shape_fails_closed() -> None:
    with pytest.raises(ValueError, match=r"shape \(3,\)"):
        prepare_velocity_input([1.0, 2.0], effective_max_speed_cm_s=165.0)
