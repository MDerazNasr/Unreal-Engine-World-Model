import math

import numpy as np
import pytest

from motionworld.dynamics.coordinates import (
    YawRadians,
    local_point_to_world,
    local_vector_to_world,
    world_point_to_local,
    world_vector_to_local,
)


@pytest.mark.parametrize(
    ("yaw_degrees", "expected_world"),
    [
        (0.0, (200.0, 0.0)),
        (90.0, (0.0, 200.0)),
        (180.0, (-200.0, 0.0)),
        (-90.0, (0.0, -200.0)),
    ],
)
def test_local_forward_matches_unreal_cardinal_convention(
    yaw_degrees: float,
    expected_world: tuple[float, float],
) -> None:
    actual = local_vector_to_world((200.0, 0.0), yaw=YawRadians.from_degrees(yaw_degrees))

    np.testing.assert_allclose(actual, expected_world, atol=1e-12)


def test_local_right_at_yaw_90_points_toward_world_negative_x() -> None:
    actual = local_vector_to_world((0.0, 200.0), yaw=YawRadians.from_degrees(90.0))

    np.testing.assert_allclose(actual, (-200.0, 0.0), atol=1e-12)


def test_fixed_seed_random_vector_round_trips_and_preserves_length() -> None:
    generator = np.random.default_rng(27116)
    local = generator.uniform(-500.0, 500.0, size=(512, 2))
    yaw = YawRadians.from_degrees(37.0)

    world = local_vector_to_world(local, yaw=yaw)
    recovered = world_vector_to_local(world, yaw=yaw)

    np.testing.assert_allclose(recovered, local, atol=1e-12)
    np.testing.assert_allclose(np.linalg.norm(world, axis=-1), np.linalg.norm(local, axis=-1))


def test_point_conversion_rotates_then_translates_and_round_trips() -> None:
    yaw = YawRadians.from_degrees(90.0)
    origin_world = np.asarray((1000.0, 500.0))

    world = local_point_to_world((200.0, 0.0), origin_world=origin_world, yaw=yaw)
    recovered = world_point_to_local(world, origin_world=origin_world, yaw=yaw)

    np.testing.assert_allclose(world, (1000.0, 700.0), atol=1e-12)
    np.testing.assert_allclose(recovered, (200.0, 0.0), atol=1e-12)


def test_vector_conversion_does_not_apply_point_origin() -> None:
    yaw = YawRadians.from_degrees(90.0)

    vector_world = local_vector_to_world((200.0, 0.0), yaw=yaw)
    point_world = local_point_to_world((200.0, 0.0), origin_world=(1000.0, 500.0), yaw=yaw)

    np.testing.assert_allclose(vector_world, (0.0, 200.0), atol=1e-12)
    np.testing.assert_allclose(point_world, (1000.0, 700.0), atol=1e-12)


def test_unreal_degrees_are_converted_explicitly() -> None:
    yaw = YawRadians.from_degrees(180.0)

    assert yaw.value == pytest.approx(math.pi)


def test_bare_numeric_yaw_is_rejected() -> None:
    with pytest.raises(TypeError, match="YawRadians"):
        local_vector_to_world((1.0, 0.0), yaw=90.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid",
    [(), (1.0,), (1.0, 2.0, 3.0), (math.nan, 0.0), (0.0, math.inf)],
)
def test_invalid_vector_shape_or_value_fails_closed(invalid: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        local_vector_to_world(invalid, yaw=YawRadians(0.0))


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_nonfinite_yaw_fails_closed(invalid: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        YawRadians(invalid)
