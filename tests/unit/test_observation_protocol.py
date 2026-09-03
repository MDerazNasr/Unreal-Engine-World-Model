from __future__ import annotations

import copy
import json

import pytest

from motionworld.protocol import (
    MAX_OBSERVATION_BYTES,
    causal_dynamics_context,
    decode_observation_json,
    encode_observation_json,
    validate_observation_mapping,
)


def _observation() -> dict[str, object]:
    return {
        "protocol": {
            "name": "motionworld_control",
            "version": 1,
            "message_type": "observation",
        },
        "identity": {
            "episode_id": 7101,
            "observation_sequence": 1,
            "state_sample_sequence": 44,
        },
        "timing": {"simulation_time_s": 1.25, "control_interval_ms": 100},
        "source": {
            "controller_mode": "nominal_mpc",
            "authoritative_state_source": "mover_on_post_finalize",
            "movement_mode": "Walking",
        },
        "validity": {
            "authoritative_state_valid": True,
            "nominal_context_valid": True,
            "reset_verified": True,
            "is_resimulation": False,
            "target_present": True,
            "timed_gate_present": True,
        },
        "state": {
            "position_world_cm": [10.0, 20.0, 86.0],
            "velocity_world_cm_per_s": [100.0, 0.0, 0.0],
            "velocity_local_planar_cm_per_s": [100.0, 0.0],
            "facing_yaw_deg": 0.0,
            "facing_unit_world": [1.0, 0.0],
            "angular_velocity_world_deg_per_s": [0.0, 0.0, 5.0],
        },
        "nominal_context": {
            "authoritative_state_sample_sequence": 44,
            "movement_mode_class": "BP_MovementMode_Walking_C",
            "parameters": {
                "acceleration_cm_per_s2": 500.0,
                "deceleration_cm_per_s2": 300.0,
                "directional_acceleration_factor": 0.5,
                "turning_strength_per_s": 8.0,
                "acceleration_smoothing_time_s": 0.3,
                "deceleration_smoothing_time_s": 0.3,
                "acceleration_smoothing_compensation": 0.0,
                "deceleration_smoothing_compensation": 0.0,
                "velocity_deadzone_cm_per_s": 1.0,
                "acceleration_deadzone_cm_per_s2": 1.0,
                "outside_influence_smoothing_time_s": 0.1,
                "facing_smoothing_time_s": 0.4,
                "smooth_facing_with_double_spring": True,
                "facing_deadzone_deg": 0.1,
                "angular_velocity_deadzone_deg_per_s": 0.1,
            },
            "input_preparation": {
                "has_max_speed": True,
                "effective_max_speed_cm_per_s": 165.0,
                "max_speed_source": "mode_override",
            },
            "internal_state": {
                "spring_velocity_world_cm_per_s": [100.0, 0.0, 0.0],
                "spring_acceleration_world_cm_per_s2": [1.0, 2.0, 0.0],
                "intermediate_velocity_world_cm_per_s": [99.0, 1.0, 0.0],
                "intermediate_facing_world_xyzw": [0.0, 0.0, 0.0, 1.0],
                "intermediate_angular_velocity_world_rad_per_s": [0.0, 0.0, 0.1],
            },
        },
        "previous_action": {
            "is_present": True,
            "source_observation_sequence": 0,
            "applied_local_velocity_cm_per_s": [120.0, 0.0],
        },
        "planner_context": {
            "target": {
                "is_present": True,
                "position_world_cm": [700.0, 0.0, 86.0],
                "desired_terminal_velocity_local_cm_per_s": [0.0, 0.0],
            },
            "timed_gate": {
                "is_present": True,
                "scenario_time_s": 1.0,
                "motion_type": "sinusoidal_translation",
                "origin_world_cm": [600.0, 0.0, 90.0],
                "motion_axis_world": [0.0, 1.0, 0.0],
                "amplitude_cm": 200.0,
                "period_s": 4.0,
                "phase_offset_rad": 0.0,
                "timeout_s": 8.0,
                "center_world_cm": [600.0, 200.0, 90.0],
                "velocity_world_cm_per_s": [0.0, 0.0, 0.0],
                "half_extents_cm": [30.0, 150.0, 90.0],
                "crossing_plane_normal_world": [1.0, 0.0, 0.0],
            },
        },
        "scenario": {
            "scenario_id": "timed_gate",
            "scenario_seed": 7101,
            "reset_id": "timed_gate:7101:attempt0",
            "is_terminal": False,
            "termination_reason": "none",
        },
    }


def _mutated(path: tuple[str, ...], value: object) -> dict[str, object]:
    result = copy.deepcopy(_observation())
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return result


def test_valid_observation_has_deterministic_round_trip() -> None:
    source = _observation()
    first = encode_observation_json(source)
    second = encode_observation_json(source)
    assert first == second
    assert len(first) < MAX_OBSERVATION_BYTES
    assert decode_observation_json(first) == source


def test_sequence_zero_requires_explicit_absent_previous_action() -> None:
    source = _mutated(("identity", "observation_sequence"), 0)
    source["previous_action"] = {"is_present": False}
    assert validate_observation_mapping(source)["previous_action"] == {"is_present": False}


def test_planner_context_is_structurally_excluded_from_dynamics_context() -> None:
    context = causal_dynamics_context(_observation())
    assert set(context) == {"identity", "timing", "state", "nominal_context", "previous_action"}
    serialized = json.dumps(context)
    for forbidden in ("planner_context", "target", "timed_gate", "scenario", "animation_root"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("protocol", "version"), 2, "protocol.version"),
        (("protocol", "version"), True, "protocol.version"),
        (("identity", "episode_id"), "7101", "must be an integer"),
        (("timing", "control_interval_ms"), 99, "control_interval_ms"),
        (("timing", "simulation_time_s"), float("nan"), "finite number"),
        (("source", "controller_mode"), "oracle", "unsupported"),
        (("validity", "reset_verified"), False, "must be true"),
        (("validity", "is_resimulation"), True, "resimulated state"),
        (("state", "facing_unit_world"), [0.0, 1.0], "facing yaw and unit vector disagree"),
        (
            ("nominal_context", "authoritative_state_sample_sequence"),
            45,
            "sequence disagree",
        ),
        (("previous_action", "source_observation_sequence"), 1, "earlier observation"),
        (("scenario", "is_terminal"), True, "terminal flag and reason disagree"),
    ],
)
def test_inconsistent_or_wrong_typed_observation_is_rejected(
    path: tuple[str, ...], value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_observation_mapping(_mutated(path, value))


def test_unknown_field_is_rejected_at_nested_boundary() -> None:
    source = _observation()
    source["state"]["animation_root_world_cm"] = [0.0, 0.0, 0.0]
    with pytest.raises(ValueError, match="state keys must be exactly"):
        validate_observation_mapping(source)


def test_missing_top_level_field_is_rejected() -> None:
    source = _observation()
    del source["identity"]
    with pytest.raises(ValueError, match="observation keys must be exactly"):
        validate_observation_mapping(source)


def test_optional_payload_and_validity_flag_must_agree() -> None:
    source = _observation()
    source["planner_context"]["timed_gate"] = {"is_present": False}
    with pytest.raises(ValueError, match="validity flag disagrees"):
        validate_observation_mapping(source)


def test_duplicate_json_key_is_rejected() -> None:
    payload = encode_observation_json(_observation())
    duplicate = payload.replace(b'"version":1', b'"version":1,"version":1', 1)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        decode_observation_json(duplicate)


def test_invalid_utf8_and_oversized_payloads_are_rejected() -> None:
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        decode_observation_json(b"\xff")
    with pytest.raises(ValueError, match="size"):
        decode_observation_json(b"x" * (MAX_OBSERVATION_BYTES + 1))


def test_input_is_detached_from_validated_result() -> None:
    source = _observation()
    result = validate_observation_mapping(source)
    source["state"]["position_world_cm"][0] = 999.0
    assert result["state"]["position_world_cm"][0] == 10.0


def test_identity_rejects_integer_above_exact_json_binary64_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        validate_observation_mapping(_mutated(("identity", "episode_id"), 2**53))
