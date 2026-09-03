from __future__ import annotations

import copy

import pytest

from motionworld.protocol import (
    MAX_ACTION_BYTES,
    MAX_TRAJECTORY_STEPS,
    decode_action_json,
    encode_action_json,
    validate_action_for_observation,
    validate_action_mapping,
)


def _action() -> dict[str, object]:
    return {
        "protocol": {
            "name": "motionworld_control",
            "version": 1,
            "message_type": "action",
        },
        "identity": {"episode_id": 7101, "source_observation_sequence": 12},
        "command": {"desired_velocity_local_cm_per_s": [120.0, -30.0]},
        "controller": {
            "controller_id": "nominal_mpc",
            "model_id": "smooth_walking_nominal_v1",
        },
        "planner": {
            "started_monotonic_us": 1_000_000,
            "finished_monotonic_us": 1_012_500,
            "measured_latency_ms": 12.5,
        },
        "fallback": {"is_safe_fallback": False, "reason": "none"},
        "telemetry": {
            "is_present": True,
            "selected_desired_velocity_trajectory_local_cm_per_s": [
                [120.0, -30.0],
                [100.0, 0.0],
            ],
            "cost_breakdown": {
                "terminal_goal_distance_cm": 42.0,
                "collision_indicator": 0.0,
                "clearance_deficit_squared_cm2": 4.0,
                "action_change_squared_cm2_s2": 900.0,
                "action_second_difference_squared_cm2_s2": 400.0,
                "total": 61.5,
            },
        },
    }


def _mutated(path: tuple[str, ...], value: object) -> dict[str, object]:
    result = copy.deepcopy(_action())
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return result


def test_valid_action_has_deterministic_round_trip() -> None:
    source = _action()
    first = encode_action_json(source)
    assert first == encode_action_json(source)
    assert len(first) < MAX_ACTION_BYTES
    assert decode_action_json(first) == source


def test_diagnostic_telemetry_can_be_explicitly_absent() -> None:
    source = _action()
    source["telemetry"] = {"is_present": False}
    assert validate_action_mapping(source)["telemetry"] == {"is_present": False}


def test_safe_fallback_is_explicit_and_zero() -> None:
    source = _action()
    source["command"]["desired_velocity_local_cm_per_s"] = [0.0, 0.0]
    source["fallback"] = {"is_safe_fallback": True, "reason": "planner_error"}
    assert validate_action_mapping(source)["fallback"]["is_safe_fallback"] is True


@pytest.mark.parametrize(
    ("episode", "sequence", "accepted", "message"),
    [
        (7102, 12, (), "episode"),
        (7101, 13, (), "future"),
        (7101, 11, (), "stale"),
        (7101, 12, (12,), "already accepted"),
    ],
)
def test_runtime_identity_admission_rejects_cross_episode_or_wrong_sequence(
    episode: int, sequence: int, accepted: tuple[int, ...], message: str
) -> None:
    source = _action()
    source["identity"] = {
        "episode_id": episode,
        "source_observation_sequence": sequence,
    }
    with pytest.raises(ValueError, match=message):
        validate_action_for_observation(
            source,
            expected_episode_id=7101,
            expected_observation_sequence=12,
            accepted_source_sequences=accepted,
        )


def test_matching_current_action_is_admitted() -> None:
    result = validate_action_for_observation(
        _action(),
        expected_episode_id=7101,
        expected_observation_sequence=12,
    )
    assert result["identity"]["source_observation_sequence"] == 12


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("protocol", "version"), 2, "protocol.version"),
        (("identity", "episode_id"), True, "integer"),
        (("command", "desired_velocity_local_cm_per_s"), [1.0], "exactly 2"),
        (("command", "desired_velocity_local_cm_per_s"), [float("nan"), 0.0], "finite"),
        (("controller", "model_id"), "", "bounded non-empty"),
        (("controller", "controller_id"), "oracle", "unsupported"),
        (("controller", "controller_id"), ["nominal_mpc"], "bounded non-empty"),
        (("planner", "finished_monotonic_us"), 999_000, "precede"),
        (("planner", "measured_latency_ms"), 12.0, "disagrees"),
        (("fallback", "reason"), "crash", "unsupported"),
        (("fallback", "reason"), ["none"], "bounded non-empty"),
        (("telemetry", "cost_breakdown", "collision_indicator"), 0.5, "zero or one"),
    ],
)
def test_malformed_nonfinite_or_inconsistent_action_is_rejected(
    path: tuple[str, ...], value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_action_mapping(_mutated(path, value))


def test_nonzero_safe_fallback_is_rejected() -> None:
    source = _action()
    source["fallback"] = {"is_safe_fallback": True, "reason": "planner_error"}
    with pytest.raises(ValueError, match="must command zero"):
        validate_action_mapping(source)


def test_trajectory_has_a_strict_step_bound() -> None:
    source = _action()
    source["telemetry"]["selected_desired_velocity_trajectory_local_cm_per_s"] = [
        [0.0, 0.0]
    ] * (MAX_TRAJECTORY_STEPS + 1)
    with pytest.raises(ValueError, match="between 1 and"):
        validate_action_mapping(source)


def test_unknown_and_missing_fields_are_rejected() -> None:
    unknown = _action()
    unknown["command"]["world_velocity_cm_per_s"] = [1.0, 2.0]
    with pytest.raises(ValueError, match="command keys must be exactly"):
        validate_action_mapping(unknown)
    missing = _action()
    del missing["controller"]
    with pytest.raises(ValueError, match="action keys must be exactly"):
        validate_action_mapping(missing)


def test_duplicate_invalid_utf8_and_oversized_json_are_rejected() -> None:
    duplicate = encode_action_json(_action()).replace(
        b'"version":1', b'"version":1,"version":1', 1
    )
    with pytest.raises(ValueError, match="duplicate JSON key"):
        decode_action_json(duplicate)
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        decode_action_json(b"\xff")
    with pytest.raises(ValueError, match="size"):
        decode_action_json(b"x" * (MAX_ACTION_BYTES + 1))


def test_input_is_detached_from_validated_result() -> None:
    source = _action()
    result = validate_action_mapping(source)
    source["command"]["desired_velocity_local_cm_per_s"][0] = 999.0
    assert result["command"]["desired_velocity_local_cm_per_s"][0] == 120.0


def test_identity_and_timestamp_reject_integers_above_exact_json_binary64_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        validate_action_mapping(_mutated(("identity", "episode_id"), 2**53))
    with pytest.raises(ValueError, match="out of range"):
        validate_action_mapping(_mutated(("planner", "started_monotonic_us"), 2**53))
