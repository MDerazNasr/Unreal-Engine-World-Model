from __future__ import annotations

import json

import pytest

from motionworld.protocol.visualization import (
    MAX_ABS_COORDINATE_CM,
    MAX_PATHS,
    MAX_POINTS_PER_PATH,
    MAX_VISUALIZATION_BYTES,
    MIN_ACTION_ENVELOPE_RESERVE_BYTES,
    TrajectoryRole,
    VisualizationPath,
    VisualizationPoint,
    VisualizationTelemetry,
    decode_visualization_json,
    visualization_from_json_object,
)


def _telemetry() -> VisualizationTelemetry:
    points_a = tuple(VisualizationPoint(float(index), -2.0) for index in range(16))
    points_b = tuple(VisualizationPoint(float(index), 1.0) for index in range(16))
    return VisualizationTelemetry(
        episode_id=7312,
        source_observation_sequence=8,
        horizon_s=1.5,
        timestep_s=0.1,
        paths=(
            VisualizationPath(
                TrajectoryRole.CEM_CANDIDATE,
                points_a,
            ),
            VisualizationPath(
                TrajectoryRole.SELECTED,
                points_b,
            ),
        ),
    )


def test_round_trip_has_canonical_schema_frame_and_identity() -> None:
    telemetry = _telemetry()

    payload = telemetry.encode_json()
    decoded = decode_visualization_json(payload)

    assert decoded == telemetry
    assert payload == decoded.encode_json()
    assert json.loads(payload) == {
        "schema": {"name": "motionworld_visualization", "version": 1},
        "identity": {"episode_id": 7312, "source_observation_sequence": 8},
        "frame": "unreal_world_xy_cm",
        "sampling": {"horizon_s": 1.5, "timestep_s": 0.1},
        "paths": [
            {
                "role": "cem_candidate",
                "points_world_xy_cm": [[float(index), -2.0] for index in range(16)],
            },
            {
                "role": "selected",
                "points_world_xy_cm": [[float(index), 1.0] for index in range(16)],
            },
        ],
    }


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True])
def test_point_rejects_nonfinite_or_boolean_coordinates(value: object) -> None:
    with pytest.raises(ValueError, match="finite number"):
        VisualizationPoint(value, 0.0)  # type: ignore[arg-type]


def test_all_declared_roles_are_accepted() -> None:
    paths = tuple(
        VisualizationPath(
            role, tuple(VisualizationPoint(float(index), 0.0) for index in range(11))
        )
        for role in TrajectoryRole
    )
    telemetry = VisualizationTelemetry(1, 0, 1.0, 0.1, paths)

    assert [path["role"] for path in telemetry.to_json_object()["paths"]] == [
        role.value for role in TrajectoryRole
    ]


def test_only_cem_candidates_may_repeat() -> None:
    point = tuple(VisualizationPoint(float(index), 0.0) for index in range(11))
    VisualizationTelemetry(
        1,
        0,
        1.0,
        0.1,
        tuple(VisualizationPath(TrajectoryRole.CEM_CANDIDATE, point) for _ in range(MAX_PATHS)),
    )

    with pytest.raises(ValueError, match="only the cem_candidate"):
        VisualizationTelemetry(
            1,
            0,
            1.0,
            0.1,
            (
                VisualizationPath(TrajectoryRole.SELECTED, point),
                VisualizationPath(TrajectoryRole.SELECTED, point),
            ),
        )


def test_path_and_point_count_bounds_are_enforced() -> None:
    point = VisualizationPoint(0.0, 0.0)
    with pytest.raises(ValueError, match="between 1 and 16"):
        VisualizationPath(TrajectoryRole.SELECTED, (point,) * (MAX_POINTS_PER_PATH + 1))
    with pytest.raises(ValueError, match="between 1 and 12"):
        VisualizationTelemetry(
            1,
            0,
            1.0,
            0.1,
            tuple(
                VisualizationPath(TrajectoryRole.CEM_CANDIDATE, (point,))
                for _ in range(MAX_PATHS + 1)
            ),
    )


def test_every_path_has_source_plus_each_plan_boundary() -> None:
    point = VisualizationPoint(0.0, 0.0)
    with pytest.raises(ValueError, match="every path must contain exactly"):
        VisualizationTelemetry(
            1,
            0,
            1.5,
            0.1,
            (VisualizationPath(TrajectoryRole.SELECTED, (point,) * 15),),
        )


@pytest.mark.parametrize(
    ("horizon_s", "timestep_s"),
    [(1.0, 0.3), (1.6, 0.1)],
)
def test_sampling_requires_one_to_fifteen_integral_steps(
    horizon_s: float, timestep_s: float
) -> None:
    with pytest.raises(ValueError, match="must be an integer between 1 and 15"):
        VisualizationTelemetry(
            1,
            0,
            horizon_s,
            timestep_s,
            (VisualizationPath(TrajectoryRole.SELECTED, (VisualizationPoint(0.0, 0.0),)),),
        )


@pytest.mark.parametrize(
    ("horizon_s", "timestep_s"),
    [(0.0, 0.1), (10.1, 0.1), (1.0, 0.0), (1.0, 1.1), (0.1, 0.2)],
)
def test_sampling_bounds_are_enforced(horizon_s: float, timestep_s: float) -> None:
    with pytest.raises(ValueError):
        VisualizationTelemetry(
            1,
            0,
            horizon_s,
            timestep_s,
            (VisualizationPath(TrajectoryRole.SELECTED, (VisualizationPoint(0.0, 0.0),)),),
        )


def test_decoded_object_rejects_extra_keys_and_unknown_role() -> None:
    raw = _telemetry().to_json_object()
    raw["unexpected"] = True
    with pytest.raises(ValueError, match="keys must be exactly"):
        visualization_from_json_object(raw)

    raw = _telemetry().to_json_object()
    raw["paths"][0]["role"] = "decorative_guess"  # type: ignore[index]
    with pytest.raises(ValueError, match="role is unsupported"):
        visualization_from_json_object(raw)


def test_wire_size_limit_is_checked_before_decode() -> None:
    with pytest.raises(ValueError, match="payload size"):
        decode_visualization_json(b" " * (MAX_VISUALIZATION_BYTES + 1))


def test_encoder_rejects_valid_but_oversized_bundle() -> None:
    verbose_point = VisualizationPoint(-9_999_999.999999998, 9_999_999.999999998)
    path = tuple(verbose_point for _ in range(MAX_POINTS_PER_PATH))
    telemetry = VisualizationTelemetry(
        2**53 - 1,
        2**53 - 1,
        1.5,
        0.1,
        tuple(
            VisualizationPath(TrajectoryRole.CEM_CANDIDATE, path)
            for _ in range(MAX_PATHS)
        ),
    )

    with pytest.raises(ValueError, match="exceeds the 6500-byte limit"):
        telemetry.encode_json()


def test_wire_decoder_rejects_duplicate_keys() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        decode_visualization_json(b'{"schema":{},"schema":{}}')


def test_visualization_ceiling_leaves_room_in_outer_action_datagram() -> None:
    from motionworld.protocol.action import MAX_ACTION_BYTES

    assert MAX_VISUALIZATION_BYTES <= 6_500
    assert MIN_ACTION_ENVELOPE_RESERVE_BYTES == MAX_ACTION_BYTES - MAX_VISUALIZATION_BYTES
    assert MIN_ACTION_ENVELOPE_RESERVE_BYTES >= 1_500


@pytest.mark.parametrize("coordinate", [MAX_ABS_COORDINATE_CM + 1.0, -MAX_ABS_COORDINATE_CM - 1.0])
def test_point_rejects_coordinates_outside_world_bound(coordinate: float) -> None:
    with pytest.raises(ValueError, match="out of range"):
        VisualizationPoint(coordinate, 0.0)


@pytest.mark.parametrize("field", ["episode_id", "source_observation_sequence"])
@pytest.mark.parametrize("value", [True, -1, 2**53])
def test_identity_rejects_boolean_or_unsafe_integer(field: str, value: object) -> None:
    raw = _telemetry().to_json_object()
    raw["identity"][field] = value  # type: ignore[index]
    with pytest.raises(ValueError):
        visualization_from_json_object(raw)


@pytest.mark.parametrize("field", ["horizon_s", "timestep_s"])
@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_sampling_rejects_boolean_or_nonfinite_value(field: str, value: object) -> None:
    raw = _telemetry().to_json_object()
    raw["sampling"][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match="finite number"):
        visualization_from_json_object(raw)


def test_wire_decoder_rejects_invalid_utf8_and_nonstandard_nonfinite_json() -> None:
    with pytest.raises(ValueError, match="not valid UTF-8 JSON"):
        decode_visualization_json(b"\xff")
    with pytest.raises(ValueError, match="non-standard JSON constant"):
        decode_visualization_json(b'{"value":NaN}')


def test_schema_version_rejects_boolean_even_though_bool_is_an_int() -> None:
    raw = _telemetry().to_json_object()
    raw["schema"]["version"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="schema.version is unsupported"):
        visualization_from_json_object(raw)
