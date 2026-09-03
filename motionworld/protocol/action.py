"""Strict version-1 Python-to-Unreal control action contract."""

from __future__ import annotations

import copy
import json
import math
from collections.abc import Collection
from typing import Any

from motionworld.protocol.observation import CONTROLLER_MODES, PROTOCOL_NAME, PROTOCOL_VERSION

ACTION_MESSAGE_TYPE = "action"
MAX_ACTION_BYTES = 8_192
MAX_TRAJECTORY_STEPS = 32
MAX_SAFE_JSON_INTEGER = 2**53 - 1

FALLBACK_REASONS = frozenset(
    {
        "none",
        "deadline_risk",
        "planner_error",
        "invalid_observation",
        "nonfinite_plan",
        "no_feasible_candidate",
        "service_shutdown",
    }
)

COST_KEYS = {
    "terminal_goal_distance_cm",
    "collision_indicator",
    "clearance_deficit_squared_cm2",
    "action_change_squared_cm2_s2",
    "action_second_difference_squared_cm2_s2",
    "total",
}


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return value


def _keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _bool(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{context} must be a boolean")
    return value


def _integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context} must be an integer")
    if value < 0 or value > MAX_SAFE_JSON_INTEGER:
        raise ValueError(f"{context} is out of range")
    return value


def _number(value: object, context: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{context} must be a finite number")
    if minimum is not None and result < minimum:
        raise ValueError(f"{context} must be at least {minimum}")
    return result


def _string(value: object, context: str, *, maximum_length: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum_length:
        raise ValueError(f"{context} must be a bounded non-empty string")
    return value


def _literal(value: object, expected: object, context: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError(f"{context} must be {expected!r}")


def _vector2(value: object, context: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{context} must contain exactly 2 values")
    return (
        _number(value[0], f"{context}[0]"),
        _number(value[1], f"{context}[1]"),
    )


def _validate_telemetry(value: object) -> None:
    telemetry = _mapping(value, "telemetry")
    present = _bool(telemetry.get("is_present"), "telemetry.is_present")
    if not present:
        _keys(telemetry, {"is_present"}, "telemetry")
        return

    _keys(
        telemetry,
        {
            "is_present",
            "selected_desired_velocity_trajectory_local_cm_per_s",
            "cost_breakdown",
        },
        "telemetry",
    )
    trajectory = telemetry["selected_desired_velocity_trajectory_local_cm_per_s"]
    if not isinstance(trajectory, list) or not 1 <= len(trajectory) <= MAX_TRAJECTORY_STEPS:
        raise ValueError(
            "telemetry selected trajectory must contain between 1 and "
            f"{MAX_TRAJECTORY_STEPS} steps"
        )
    for index, action in enumerate(trajectory):
        _vector2(action, f"telemetry.selected_trajectory[{index}]")

    costs = _mapping(telemetry["cost_breakdown"], "telemetry.cost_breakdown")
    _keys(costs, COST_KEYS, "telemetry.cost_breakdown")
    for key, component in costs.items():
        value_number = _number(component, f"telemetry.cost_breakdown.{key}", minimum=0.0)
        if key == "collision_indicator" and value_number not in (0.0, 1.0):
            raise ValueError("telemetry cost collision_indicator must be zero or one")


def validate_action_mapping(value: object) -> dict[str, Any]:
    """Validate one logical action and return a detached copy."""

    raw = _mapping(value, "action")
    _keys(
        raw,
        {"protocol", "identity", "command", "controller", "planner", "fallback", "telemetry"},
        "action",
    )

    protocol = _mapping(raw["protocol"], "protocol")
    _keys(protocol, {"name", "version", "message_type"}, "protocol")
    _literal(protocol["name"], PROTOCOL_NAME, "protocol.name")
    _literal(protocol["version"], PROTOCOL_VERSION, "protocol.version")
    _literal(protocol["message_type"], ACTION_MESSAGE_TYPE, "protocol.message_type")

    identity = _mapping(raw["identity"], "identity")
    _keys(identity, {"episode_id", "source_observation_sequence"}, "identity")
    _integer(identity["episode_id"], "identity.episode_id")
    _integer(identity["source_observation_sequence"], "identity.source_observation_sequence")

    command = _mapping(raw["command"], "command")
    _keys(command, {"desired_velocity_local_cm_per_s"}, "command")
    desired_velocity = _vector2(
        command["desired_velocity_local_cm_per_s"],
        "command.desired_velocity_local_cm_per_s",
    )

    controller = _mapping(raw["controller"], "controller")
    _keys(controller, {"controller_id", "model_id"}, "controller")
    controller_id = _string(controller["controller_id"], "controller.controller_id")
    if controller_id not in CONTROLLER_MODES:
        raise ValueError("controller.controller_id is unsupported")
    _string(controller["model_id"], "controller.model_id")

    planner = _mapping(raw["planner"], "planner")
    _keys(
        planner,
        {"started_monotonic_us", "finished_monotonic_us", "measured_latency_ms"},
        "planner",
    )
    started_us = _integer(planner["started_monotonic_us"], "planner.started_monotonic_us")
    finished_us = _integer(planner["finished_monotonic_us"], "planner.finished_monotonic_us")
    if finished_us < started_us:
        raise ValueError("planner finish timestamp must not precede start timestamp")
    measured_ms = _number(
        planner["measured_latency_ms"], "planner.measured_latency_ms", minimum=0.0
    )
    timestamp_ms = (finished_us - started_us) / 1_000.0
    if not math.isclose(measured_ms, timestamp_ms, rel_tol=0.0, abs_tol=1.0e-6):
        raise ValueError("planner measured latency disagrees with timestamps")

    fallback = _mapping(raw["fallback"], "fallback")
    _keys(fallback, {"is_safe_fallback", "reason"}, "fallback")
    is_fallback = _bool(fallback["is_safe_fallback"], "fallback.is_safe_fallback")
    fallback_reason = _string(fallback["reason"], "fallback.reason")
    if fallback_reason not in FALLBACK_REASONS:
        raise ValueError("fallback.reason is unsupported")
    if is_fallback != (fallback_reason != "none"):
        raise ValueError("fallback status and reason disagree")
    if is_fallback and desired_velocity != (0.0, 0.0):
        raise ValueError("safe fallback action must command zero local velocity")

    _validate_telemetry(raw["telemetry"])
    return copy.deepcopy(raw)


def validate_action_for_observation(
    value: object,
    *,
    expected_episode_id: int,
    expected_observation_sequence: int,
    accepted_source_sequences: Collection[int] = (),
) -> dict[str, Any]:
    """Validate packet content and admit it only for the current unanswered observation."""

    expected_episode = _integer(expected_episode_id, "expected_episode_id")
    expected_sequence = _integer(expected_observation_sequence, "expected_observation_sequence")
    action = validate_action_mapping(value)
    identity = action["identity"]
    if identity["episode_id"] != expected_episode:
        raise ValueError("action episode does not match the current episode")
    source_sequence = identity["source_observation_sequence"]
    if source_sequence > expected_sequence:
        raise ValueError("action source observation sequence is from the future")
    if source_sequence < expected_sequence:
        raise ValueError("action source observation sequence is stale")
    if source_sequence in accepted_source_sequences:
        raise ValueError("action source observation sequence was already accepted")
    return action


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def decode_action_json(payload: bytes) -> dict[str, Any]:
    """Decode one bounded UTF-8 JSON action and validate it."""

    if not isinstance(payload, bytes):
        raise TypeError("action payload must be bytes")
    if not payload or len(payload) > MAX_ACTION_BYTES:
        raise ValueError("action payload size is invalid")
    try:
        text = payload.decode("utf-8")
        raw = json.loads(
            text,
            parse_constant=_reject_nonfinite_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("action payload is not valid UTF-8 JSON") from error
    return validate_action_mapping(raw)


def encode_action_json(value: object) -> bytes:
    """Validate and encode a deterministic compact UTF-8 JSON action."""

    validated = validate_action_mapping(value)
    payload = json.dumps(
        validated,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(payload) > MAX_ACTION_BYTES:
        raise ValueError("encoded action exceeds maximum size")
    return payload
