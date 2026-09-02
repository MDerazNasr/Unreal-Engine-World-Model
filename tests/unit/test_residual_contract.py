import math

import numpy as np
import pytest

from motionworld.dynamics.coordinates import YawRadians
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState
from motionworld.models.residual_contract import (
    ResidualCorrection,
    compose_residual,
    residual_difference,
    zero_residual,
)


def _state(
    *,
    position: tuple[float, float, float] = (10.0, 20.0, 5.0),
    velocity: tuple[float, float, float] = (30.0, 40.0, 0.0),
    yaw_deg: float = 15.0,
    yaw_rate_deg_s: float = 20.0,
    time_s: float = 1.25,
) -> SmoothWalkingObservableState:
    return SmoothWalkingObservableState(
        position_world_cm=np.asarray(position, dtype=np.float64),
        velocity_world_cm_s=np.asarray(velocity, dtype=np.float64),
        facing_yaw_rad=math.radians(yaw_deg),
        angular_velocity_yaw_deg_s=yaw_rate_deg_s,
        simulation_time_s=time_s,
    )


def test_zero_residual_is_exact_nominal_identity() -> None:
    nominal = _state()

    corrected = compose_residual(
        nominal,
        zero_residual(),
        reference_yaw=YawRadians.from_degrees(73.0),
    )

    np.testing.assert_array_equal(corrected.position_world_cm, nominal.position_world_cm)
    np.testing.assert_array_equal(corrected.velocity_world_cm_s, nominal.velocity_world_cm_s)
    assert corrected.facing_yaw_rad == nominal.facing_yaw_rad
    assert corrected.angular_velocity_yaw_deg_s == nominal.angular_velocity_yaw_deg_s
    assert corrected.simulation_time_s == nominal.simulation_time_s


def test_difference_then_composition_recovers_actual_planar_state() -> None:
    nominal = _state()
    actual = _state(
        position=(14.0, 17.0, 5.0),
        velocity=(20.0, 55.0, 0.0),
        yaw_deg=22.0,
        yaw_rate_deg_s=-12.0,
    )
    reference = YawRadians.from_degrees(35.0)

    residual = residual_difference(actual, nominal, reference_yaw=reference)
    corrected = compose_residual(nominal, residual, reference_yaw=reference)

    np.testing.assert_allclose(corrected.position_world_cm, actual.position_world_cm, atol=1e-12)
    np.testing.assert_allclose(
        corrected.velocity_world_cm_s,
        actual.velocity_world_cm_s,
        atol=1e-12,
    )
    assert corrected.facing_yaw_rad == pytest.approx(actual.facing_yaw_rad)
    assert corrected.angular_velocity_yaw_deg_s == pytest.approx(
        actual.angular_velocity_yaw_deg_s
    )


def test_target_frame_is_previous_facing_not_unknown_actual_facing() -> None:
    nominal = _state(position=(0.0, 0.0, 0.0), velocity=(0.0, 0.0, 0.0))
    actual = _state(position=(0.0, 10.0, 0.0), velocity=(0.0, 20.0, 0.0))

    residual = residual_difference(
        actual,
        nominal,
        reference_yaw=YawRadians.from_degrees(90.0),
    )

    np.testing.assert_allclose(residual.position_local_cm, [10.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(residual.velocity_local_cm_s, [20.0, 0.0], atol=1e-12)


def test_yaw_difference_uses_shortest_wrapped_correction() -> None:
    nominal = _state(yaw_deg=179.0)
    actual = _state(yaw_deg=-179.0)

    residual = residual_difference(actual, nominal, reference_yaw=YawRadians(0.0))
    corrected = compose_residual(nominal, residual, reference_yaw=YawRadians(0.0))

    assert math.degrees(residual.yaw_rad) == pytest.approx(2.0)
    assert math.degrees(corrected.facing_yaw_rad) == pytest.approx(-179.0)


def test_output_feature_order_is_frozen() -> None:
    residual = ResidualCorrection(
        position_local_cm=np.asarray([1.0, 2.0]),
        velocity_local_cm_s=np.asarray([3.0, 4.0]),
        yaw_rad=5.0,
        angular_velocity_yaw_rad_s=6.0,
    )

    np.testing.assert_array_equal(residual.as_array(), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


@pytest.mark.parametrize(
    ("actual", "message"),
    [
        (_state(position=(10.0, 20.0, 5.1)), "vertical position"),
        (_state(velocity=(30.0, 40.0, 0.1)), "vertical velocity"),
        (_state(time_s=1.3), "simulation-time"),
    ],
)
def test_unmodelled_nonplanar_or_time_difference_fails_closed(
    actual: SmoothWalkingObservableState,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        residual_difference(actual, _state(), reference_yaw=YawRadians(0.0))


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_nonfinite_residual_fails_closed(bad_value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        ResidualCorrection(
            position_local_cm=np.asarray([bad_value, 0.0]),
            velocity_local_cm_s=np.zeros(2),
            yaw_rad=0.0,
            angular_velocity_yaw_rad_s=0.0,
        )
