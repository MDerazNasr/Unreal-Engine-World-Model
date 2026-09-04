"""Strict version-1 Unreal-to-Python control observation contract."""

from __future__ import annotations

import copy
import json
import math
from typing import Any

PROTOCOL_NAME = "motionworld_control"
PROTOCOL_VERSION = 1
OBSERVATION_MESSAGE_TYPE = "observation"
MAX_OBSERVATION_BYTES = 16_384
CONTROL_INTERVAL_MS = 100
MAX_SAFE_JSON_INTEGER = 2**53 - 1

CONTROLLER_MODES = frozenset(
    {"echo", "reactive", "branch_preview", "nominal_mpc", "residual_mpc"}
)
TERMINATION_REASONS = frozenset(
    {"none", "success", "gate_collision", "timeout", "invalid_configuration"}
)
MAX_SPEED_SOURCES = frozenset({"mode_override", "shared_settings"})

PARAMETER_KEYS = {
    "acceleration_cm_per_s2",
    "deceleration_cm_per_s2",
    "directional_acceleration_factor",
    "turning_strength_per_s",
    "acceleration_smoothing_time_s",
    "deceleration_smoothing_time_s",
    "acceleration_smoothing_compensation",
    "deceleration_smoothing_compensation",
    "velocity_deadzone_cm_per_s",
    "acceleration_deadzone_cm_per_s2",
    "outside_influence_smoothing_time_s",
    "facing_smoothing_time_s",
    "smooth_facing_with_double_spring",
    "facing_deadzone_deg",
    "angular_velocity_deadzone_deg_per_s",
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


def _integer(value: object, context: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context} must be an integer")
    if value < minimum or value > MAX_SAFE_JSON_INTEGER:
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


def _vector(value: object, length: int, context: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{context} must contain exactly {length} values")
    return tuple(_number(component, f"{context}[{index}]") for index, component in enumerate(value))


def _unit_vector(value: object, length: int, context: str) -> tuple[float, ...]:
    result = _vector(value, length, context)
    norm = math.sqrt(sum(component * component for component in result))
    if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1.0e-5):
        raise ValueError(f"{context} must be unit length")
    return result


def _validate_optional_target(value: object) -> bool:
    target = _mapping(value, "planner_context.target")
    present = _bool(target.get("is_present"), "target.is_present")
    if not present:
        _keys(target, {"is_present"}, "planner_context.target")
        return False
    _keys(
        target,
        {"is_present", "position_world_cm", "desired_terminal_velocity_local_cm_per_s"},
        "planner_context.target",
    )
    _vector(target["position_world_cm"], 3, "target.position_world_cm")
    _vector(
        target["desired_terminal_velocity_local_cm_per_s"],
        2,
        "target.desired_terminal_velocity_local_cm_per_s",
    )
    return True


_PRESENT_GATE_KEYS = {
    "is_present",
    "scenario_time_s",
    "center_world_cm",
    "velocity_world_cm_per_s",
    "half_extents_cm",
    "crossing_plane_normal_world",
    "motion_type",
    "origin_world_cm",
    "motion_axis_world",
    "amplitude_cm",
    "period_s",
    "phase_offset_rad",
    "timeout_s",
}


def _validate_optional_gate(
    value: object,
    *,
    context: str = "planner_context.timed_gate",
    obstacle_id: str | None = None,
) -> bool:
    gate = _mapping(value, context)
    present = _bool(gate.get("is_present"), "timed_gate.is_present")
    if not present:
        _keys(gate, {"is_present"}, context)
        return False
    expected = _PRESENT_GATE_KEYS | ({"obstacle_id"} if obstacle_id is not None else set())
    _keys(gate, expected, context)
    if obstacle_id is not None:
        _literal(gate["obstacle_id"], obstacle_id, f"{context}.obstacle_id")
    _number(gate["scenario_time_s"], "timed_gate.scenario_time_s", minimum=0.0)
    _literal(gate["motion_type"], "sinusoidal_translation", "timed_gate.motion_type")
    _vector(gate["origin_world_cm"], 3, "timed_gate.origin_world_cm")
    _unit_vector(gate["motion_axis_world"], 3, "timed_gate.motion_axis_world")
    _number(gate["amplitude_cm"], "timed_gate.amplitude_cm", minimum=0.0)
    _number(gate["period_s"], "timed_gate.period_s", minimum=1.0e-9)
    _number(gate["phase_offset_rad"], "timed_gate.phase_offset_rad")
    _number(gate["timeout_s"], "timed_gate.timeout_s", minimum=1.0e-9)
    _vector(gate["center_world_cm"], 3, "timed_gate.center_world_cm")
    _vector(gate["velocity_world_cm_per_s"], 3, "timed_gate.velocity_world_cm_per_s")
    half_extents = _vector(gate["half_extents_cm"], 3, "timed_gate.half_extents_cm")
    if any(component <= 0.0 for component in half_extents):
        raise ValueError("timed_gate.half_extents_cm must be positive")
    _unit_vector(
        gate["crossing_plane_normal_world"],
        3,
        "timed_gate.crossing_plane_normal_world",
    )
    return True


def _validate_two_obstacles(value: object, legacy_gate: dict[str, Any]) -> None:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("planner_context.obstacles must contain exactly two obstacles")
    identifiers = ("gate_primary", "gate_secondary")
    for index, identifier in enumerate(identifiers):
        if not _validate_optional_gate(
            value[index],
            context=f"planner_context.obstacles[{index}]",
            obstacle_id=identifier,
        ):
            raise ValueError("V3 obstacle records must be present")
    primary = dict(value[0])
    primary.pop("obstacle_id")
    if primary != legacy_gate:
        raise ValueError("legacy timed_gate must equal obstacles[0]")
    first_time = float(value[0]["scenario_time_s"])
    second_time = float(value[1]["scenario_time_s"])
    if not math.isclose(first_time, second_time, rel_tol=0.0, abs_tol=1.0e-6):
        raise ValueError("V3 obstacles must share authoritative scenario time")


def _validate_previous_action(value: object, observation_sequence: int) -> bool:
    action = _mapping(value, "previous_action")
    present = _bool(action.get("is_present"), "previous_action.is_present")
    if not present:
        _keys(action, {"is_present"}, "previous_action")
        if observation_sequence != 0:
            raise ValueError("only observation sequence zero may omit previous_action")
        return False
    _keys(
        action,
        {"is_present", "source_observation_sequence", "applied_local_velocity_cm_per_s"},
        "previous_action",
    )
    source_sequence = _integer(
        action["source_observation_sequence"], "previous_action.source_observation_sequence"
    )
    if source_sequence >= observation_sequence:
        raise ValueError("previous action must originate from an earlier observation")
    _vector(
        action["applied_local_velocity_cm_per_s"],
        2,
        "previous_action.applied_local_velocity_cm_per_s",
    )
    return True


def validate_observation_mapping(value: object) -> dict[str, Any]:
    """Validate one logical observation and return a detached copy."""

    raw = _mapping(value, "observation")
    _keys(
        raw,
        {
            "protocol",
            "identity",
            "timing",
            "source",
            "validity",
            "state",
            "nominal_context",
            "previous_action",
            "planner_context",
            "scenario",
        },
        "observation",
    )

    protocol = _mapping(raw["protocol"], "protocol")
    _keys(protocol, {"name", "version", "message_type"}, "protocol")
    _literal(protocol["name"], PROTOCOL_NAME, "protocol.name")
    _literal(protocol["version"], PROTOCOL_VERSION, "protocol.version")
    _literal(protocol["message_type"], OBSERVATION_MESSAGE_TYPE, "protocol.message_type")

    identity = _mapping(raw["identity"], "identity")
    _keys(identity, {"episode_id", "observation_sequence", "state_sample_sequence"}, "identity")
    _integer(identity["episode_id"], "identity.episode_id")
    observation_sequence = _integer(
        identity["observation_sequence"], "identity.observation_sequence"
    )
    state_sample_sequence = _integer(
        identity["state_sample_sequence"], "identity.state_sample_sequence"
    )

    timing = _mapping(raw["timing"], "timing")
    _keys(timing, {"simulation_time_s", "control_interval_ms"}, "timing")
    _number(timing["simulation_time_s"], "timing.simulation_time_s", minimum=0.0)
    _literal(timing["control_interval_ms"], CONTROL_INTERVAL_MS, "timing.control_interval_ms")

    source = _mapping(raw["source"], "source")
    _keys(source, {"controller_mode", "authoritative_state_source", "movement_mode"}, "source")
    if source["controller_mode"] not in CONTROLLER_MODES:
        raise ValueError("source.controller_mode is unsupported")
    _literal(
        source["authoritative_state_source"],
        "mover_on_post_finalize",
        "source.authoritative_state_source",
    )
    _string(source["movement_mode"], "source.movement_mode")

    validity = _mapping(raw["validity"], "validity")
    _keys(
        validity,
        {
            "authoritative_state_valid",
            "nominal_context_valid",
            "reset_verified",
            "is_resimulation",
            "target_present",
            "timed_gate_present",
        },
        "validity",
    )
    for required in ("authoritative_state_valid", "nominal_context_valid", "reset_verified"):
        if not _bool(validity[required], f"validity.{required}"):
            raise ValueError(f"validity.{required} must be true for a transmitted observation")
    if _bool(validity["is_resimulation"], "validity.is_resimulation"):
        raise ValueError("resimulated state cannot become a control observation")

    state = _mapping(raw["state"], "state")
    _keys(
        state,
        {
            "position_world_cm",
            "velocity_world_cm_per_s",
            "velocity_local_planar_cm_per_s",
            "facing_yaw_deg",
            "facing_unit_world",
            "angular_velocity_world_deg_per_s",
        },
        "state",
    )
    _vector(state["position_world_cm"], 3, "state.position_world_cm")
    _vector(state["velocity_world_cm_per_s"], 3, "state.velocity_world_cm_per_s")
    _vector(state["velocity_local_planar_cm_per_s"], 2, "state.velocity_local_planar_cm_per_s")
    yaw_deg = _number(state["facing_yaw_deg"], "state.facing_yaw_deg")
    if yaw_deg < -180.0 or yaw_deg > 180.0:
        raise ValueError("state.facing_yaw_deg must lie in [-180, 180]")
    facing = _unit_vector(state["facing_unit_world"], 2, "state.facing_unit_world")
    yaw_rad = math.radians(yaw_deg)
    if not (
        math.isclose(facing[0], math.cos(yaw_rad), rel_tol=0.0, abs_tol=1.0e-5)
        and math.isclose(facing[1], math.sin(yaw_rad), rel_tol=0.0, abs_tol=1.0e-5)
    ):
        raise ValueError("state facing yaw and unit vector disagree")
    _vector(
        state["angular_velocity_world_deg_per_s"],
        3,
        "state.angular_velocity_world_deg_per_s",
    )

    nominal = _mapping(raw["nominal_context"], "nominal_context")
    _keys(
        nominal,
        {
            "authoritative_state_sample_sequence",
            "movement_mode_class",
            "parameters",
            "input_preparation",
            "internal_state",
        },
        "nominal_context",
    )
    aligned_sequence = _integer(
        nominal["authoritative_state_sample_sequence"],
        "nominal_context.authoritative_state_sample_sequence",
    )
    if aligned_sequence != state_sample_sequence:
        raise ValueError("nominal context and authoritative state sequence disagree")
    _string(nominal["movement_mode_class"], "nominal_context.movement_mode_class")
    parameters = _mapping(nominal["parameters"], "nominal_context.parameters")
    _keys(parameters, PARAMETER_KEYS, "nominal_context.parameters")
    for key, parameter in parameters.items():
        if key == "smooth_facing_with_double_spring":
            _bool(parameter, f"parameters.{key}")
        else:
            _number(parameter, f"parameters.{key}", minimum=0.0)

    preparation = _mapping(nominal["input_preparation"], "nominal_context.input_preparation")
    _keys(
        preparation,
        {"has_max_speed", "effective_max_speed_cm_per_s", "max_speed_source"},
        "nominal_context.input_preparation",
    )
    if not _bool(preparation["has_max_speed"], "input_preparation.has_max_speed"):
        raise ValueError("a valid control observation requires known effective max speed")
    _number(
        preparation["effective_max_speed_cm_per_s"],
        "input_preparation.effective_max_speed_cm_per_s",
        minimum=0.0,
    )
    if preparation["max_speed_source"] not in MAX_SPEED_SOURCES:
        raise ValueError("input_preparation.max_speed_source is unsupported")

    internal = _mapping(nominal["internal_state"], "nominal_context.internal_state")
    _keys(
        internal,
        {
            "spring_velocity_world_cm_per_s",
            "spring_acceleration_world_cm_per_s2",
            "intermediate_velocity_world_cm_per_s",
            "intermediate_facing_world_xyzw",
            "intermediate_angular_velocity_world_rad_per_s",
        },
        "nominal_context.internal_state",
    )
    _vector(internal["spring_velocity_world_cm_per_s"], 3, "internal.spring_velocity")
    _vector(internal["spring_acceleration_world_cm_per_s2"], 3, "internal.spring_acceleration")
    _vector(internal["intermediate_velocity_world_cm_per_s"], 3, "internal.intermediate_velocity")
    _unit_vector(internal["intermediate_facing_world_xyzw"], 4, "internal.intermediate_facing")
    _vector(
        internal["intermediate_angular_velocity_world_rad_per_s"],
        3,
        "internal.intermediate_angular_velocity",
    )

    _validate_previous_action(raw["previous_action"], observation_sequence)

    planner = _mapping(raw["planner_context"], "planner_context")
    if set(planner) not in (
        {"target", "timed_gate"},
        {"target", "timed_gate", "obstacles"},
    ):
        raise ValueError("planner_context keys are invalid")
    target_present = _validate_optional_target(planner["target"])
    gate_present = _validate_optional_gate(planner["timed_gate"])
    if "obstacles" in planner:
        if not gate_present:
            raise ValueError("V3 obstacles require the legacy primary timed_gate")
        _validate_two_obstacles(planner["obstacles"], planner["timed_gate"])
    if _bool(validity["target_present"], "validity.target_present") != target_present:
        raise ValueError("target validity flag disagrees with target payload")
    if _bool(validity["timed_gate_present"], "validity.timed_gate_present") != gate_present:
        raise ValueError("timed-gate validity flag disagrees with gate payload")

    scenario = _mapping(raw["scenario"], "scenario")
    _keys(
        scenario,
        {"scenario_id", "scenario_seed", "reset_id", "is_terminal", "termination_reason"},
        "scenario",
    )
    _string(scenario["scenario_id"], "scenario.scenario_id")
    _integer(scenario["scenario_seed"], "scenario.scenario_seed")
    _string(scenario["reset_id"], "scenario.reset_id")
    terminal = _bool(scenario["is_terminal"], "scenario.is_terminal")
    if scenario["termination_reason"] not in TERMINATION_REASONS:
        raise ValueError("scenario.termination_reason is unsupported")
    if terminal != (scenario["termination_reason"] != "none"):
        raise ValueError("scenario terminal flag and reason disagree")

    return copy.deepcopy(raw)


def causal_dynamics_context(value: object) -> dict[str, Any]:
    """Return only causal character-dynamics context, excluding planner/scenario data."""

    validated = validate_observation_mapping(value)
    return {
        "identity": {
            "episode_id": validated["identity"]["episode_id"],
            "observation_sequence": validated["identity"]["observation_sequence"],
            "state_sample_sequence": validated["identity"]["state_sample_sequence"],
        },
        "timing": copy.deepcopy(validated["timing"]),
        "state": copy.deepcopy(validated["state"]),
        "nominal_context": copy.deepcopy(validated["nominal_context"]),
        "previous_action": copy.deepcopy(validated["previous_action"]),
    }


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def decode_observation_json(payload: bytes) -> dict[str, Any]:
    """Decode one bounded canonical-compatible JSON observation and validate it."""

    if not isinstance(payload, bytes):
        raise TypeError("observation payload must be bytes")
    if not payload or len(payload) > MAX_OBSERVATION_BYTES:
        raise ValueError("observation payload size is invalid")
    try:
        text = payload.decode("utf-8")
        raw = json.loads(
            text,
            parse_constant=_reject_nonfinite_json_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("observation payload is not valid UTF-8 JSON") from error
    return validate_observation_mapping(raw)


def encode_observation_json(value: object) -> bytes:
    """Validate and encode a deterministic compact UTF-8 JSON observation."""

    validated = validate_observation_mapping(value)
    payload = json.dumps(
        validated,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(payload) > MAX_OBSERVATION_BYTES:
        raise ValueError("encoded observation exceeds maximum size")
    return payload
