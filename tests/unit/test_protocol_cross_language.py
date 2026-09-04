from __future__ import annotations

import copy
import random
from contextlib import suppress
from pathlib import Path

import pytest

from motionworld.protocol import (
    decode_action_json,
    decode_observation_json,
    encode_action_json,
    encode_observation_json,
    validate_action_for_observation,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    REPOSITORY_ROOT
    / "unreal"
    / "Plugins"
    / "MotionWorld"
    / "Resources"
    / "ProtocolFixtures"
    / "v1"
)


def _fixture(name: str) -> bytes:
    return (FIXTURE_ROOT / name).read_bytes().removesuffix(b"\n")


def test_unreal_observation_fixture_is_canonical_and_python_valid() -> None:
    payload = _fixture("observation.json")
    decoded = decode_observation_json(payload)
    assert decoded["identity"] == {
        "episode_id": 7101,
        "observation_sequence": 1,
        "state_sample_sequence": 44,
    }
    assert encode_observation_json(decoded) == payload


@pytest.mark.parametrize(
    "name",
    [
        "action.json",
        "action_zero_no_telemetry.json",
        "action_visualization_four_branches.json",
    ],
)
def test_python_action_fixtures_are_canonical_and_round_trip(name: str) -> None:
    payload = _fixture(name)
    decoded = decode_action_json(payload)
    assert encode_action_json(decoded) == payload


def test_four_branch_visualization_fixture_preserves_legacy_action_contract() -> None:
    payload = _fixture("action_visualization_four_branches.json")
    decoded = decode_action_json(payload)

    assert len(payload) < 8_192
    assert decoded["identity"] == {
        "episode_id": 7101,
        "source_observation_sequence": 12,
    }
    telemetry = decoded["telemetry"]
    assert telemetry["is_present"] is True
    assert telemetry["selected_desired_velocity_trajectory_local_cm_per_s"] == [
        [120.0, -30.0],
        [100.0, 0.0],
    ]
    assert set(telemetry["cost_breakdown"]) == {
        "terminal_goal_distance_cm",
        "collision_indicator",
        "clearance_deficit_squared_cm2",
        "action_change_squared_cm2_s2",
        "action_second_difference_squared_cm2_s2",
        "total",
    }
    visualization = telemetry["visualization"]
    assert visualization["identity"] == decoded["identity"]
    assert visualization["frame"] == "unreal_world_xy_cm"
    assert [path["role"] for path in visualization["paths"]] == [
        "branch_forward",
        "branch_left",
        "branch_right",
        "branch_stop",
    ]
    assert all(len(path["points_world_xy_cm"]) == 3 for path in visualization["paths"])


def test_zero_boundary_fixture_has_explicit_optional_telemetry_absence() -> None:
    decoded = decode_action_json(_fixture("action_zero_no_telemetry.json"))
    assert decoded["identity"] == {"episode_id": 0, "source_observation_sequence": 0}
    assert decoded["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
    assert decoded["planner"]["measured_latency_ms"] == 0.0
    assert decoded["telemetry"] == {"is_present": False}


@pytest.mark.parametrize(
    "payload",
    [
        b"{",
        b"\xff",
        b'{"protocol":{"version":NaN}}',
        b'{"protocol":{"version":Infinity}}',
        b"[]",
        b"null",
    ],
)
@pytest.mark.parametrize("decoder", [decode_action_json, decode_observation_json])
def test_bounded_malformed_corpus_fails_closed(decoder, payload: bytes) -> None:
    with pytest.raises(ValueError):
        decoder(payload)


def test_deterministic_bounded_byte_fuzz_never_escapes_validation() -> None:
    generator = random.Random(20260903)
    for _ in range(128):
        payload = generator.randbytes(generator.randrange(1, 257))
        for decoder in (decode_action_json, decode_observation_json):
            with suppress(ValueError):
                decoder(payload)


def test_cross_language_identity_admission_rejects_wrong_episode_and_stale_action() -> None:
    action = decode_action_json(_fixture("action.json"))
    with pytest.raises(ValueError, match="episode"):
        validate_action_for_observation(
            action,
            expected_episode_id=7102,
            expected_observation_sequence=12,
        )
    with pytest.raises(ValueError, match="stale"):
        validate_action_for_observation(
            action,
            expected_episode_id=7101,
            expected_observation_sequence=13,
        )


@pytest.mark.parametrize("fixture_name", ["action.json", "observation.json"])
def test_protocol_rejection_never_echoes_checkpoint_payload(fixture_name: str) -> None:
    sentinel = "SECRET_CHECKPOINT_BYTES_MUST_NOT_BE_LOGGED"
    decoder = decode_action_json if fixture_name.startswith("action") else decode_observation_json
    valid = decoder(_fixture(fixture_name))
    invalid = copy.deepcopy(valid)
    invalid["checkpoint_payload"] = sentinel
    encoder = encode_action_json if fixture_name.startswith("action") else encode_observation_json
    with pytest.raises(ValueError) as captured:
        encoder(invalid)
    assert sentinel not in str(captured.value)


def test_fixtures_contain_no_checkpoint_or_unbounded_source_data() -> None:
    for path in sorted(FIXTURE_ROOT.glob("*.json")):
        payload = path.read_bytes()
        assert len(payload) <= 16_384
        assert b"checkpoint" not in payload.lower()
        assert b"model_state_dict" not in payload.lower()
