"""Strict loader for MotionWorld's version-1 Unreal episode files."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

EPISODE_SCHEMA_VERSION = 1
STATE_PROTOCOL_VERSION = 1
TRANSITION_PROTOCOL_VERSION = 1
MAX_TRANSITIONS = 100_000
_NUMERIC_TOLERANCE = 1e-6
_ACTION_TOLERANCE_CM_PER_S = 0.02


class EpisodeValidationError(ValueError):
    """Raised when an episode could silently corrupt a model or evaluation."""


@dataclass(frozen=True)
class ValidatedEpisode:
    """A fully validated, complete episode and its provenance records."""

    path: Path
    header: dict[str, Any]
    transitions: tuple[dict[str, Any], ...]
    footer: dict[str, Any]

    @property
    def episode_id(self) -> int:
        return int(self.header["episode_id"])


_HEADER_KEYS = {
    "record_type",
    "schema_name",
    "schema_version",
    "created_utc",
    "engine_version",
    "project_name",
    "episode_id",
    "state_source",
    "conventions",
    "recorder_stats",
}
_CONVENTION_KEYS = {
    "world_frame",
    "local_action_frame",
    "position_unit",
    "linear_velocity_unit",
    "angle_unit",
    "angular_velocity_unit",
    "time_unit",
}
_STATS_KEYS = {
    "observed_state_count",
    "attempted_transition_count",
    "recorded_transition_count",
    "rejected_transition_count",
    "rejected_seed_state_count",
    "capacity_drop_count",
}
_TRANSITION_KEYS = {
    "record_type",
    "schema_version",
    "transition_protocol_version",
    "episode_id",
    "transition_sequence",
    "start_simulation_time_s",
    "end_simulation_time_s",
    "delta_time_s",
    "previous_state",
    "applied_action",
    "next_state",
}
_STATE_KEYS = {
    "protocol_version",
    "sample_sequence",
    "mover_step_server_frame",
    "simulation_time_s",
    "step_s",
    "is_resimulation",
    "is_valid",
    "movement_mode",
    "position_world_cm",
    "velocity_world_cm_per_s",
    "velocity_local_planar_cm_per_s",
    "facing_yaw_deg",
    "facing_unit_world",
    "angular_velocity_world_deg_per_s",
}
_ACTION_KEYS = {
    "type",
    "is_valid",
    "was_motionworld_automated",
    "velocity_world_cm_per_s",
    "velocity_local_planar_cm_per_s",
}
_FOOTER_KEYS = {
    "record_type",
    "schema_version",
    "episode_id",
    "transition_count",
    "first_transition_sequence",
    "last_transition_sequence",
    "complete",
}


def _fail(context: str, message: str) -> None:
    raise EpisodeValidationError(f"{context}: {message}")


def _object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(context, "expected an object")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing or extra:
        _fail(context, f"schema keys differ; missing={sorted(missing)}, extra={sorted(extra)}")


def _integer(value: Any, context: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(context, "expected an integer")
    if minimum is not None and value < minimum:
        _fail(context, f"expected a value >= {minimum}")
    return value


def _number(value: Any, context: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(context, "expected a number")
    result = float(value)
    if not math.isfinite(result):
        _fail(context, "number must be finite")
    if positive and result <= 0.0:
        _fail(context, "number must be positive")
    return result


def _boolean(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        _fail(context, "expected a boolean")
    return value


def _string(value: Any, context: str, *, expected: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        _fail(context, "expected a non-empty string")
    if expected is not None and value != expected:
        _fail(context, f"expected {expected!r}, received {value!r}")
    return value


def _vector(value: Any, length: int, context: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        _fail(context, f"expected an array of length {length}")
    return tuple(_number(component, f"{context}[{index}]") for index, component in enumerate(value))


def _close(left: float, right: float, tolerance: float = _NUMERIC_TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def _validate_state(value: Any, context: str) -> dict[str, Any]:
    state = _object(value, context)
    _exact_keys(state, _STATE_KEYS, context)
    if _integer(state["protocol_version"], f"{context}.protocol_version") != STATE_PROTOCOL_VERSION:
        _fail(context, "unsupported state protocol version")
    _integer(state["sample_sequence"], f"{context}.sample_sequence", minimum=0)
    _integer(state["mover_step_server_frame"], f"{context}.mover_step_server_frame", minimum=-1)
    _number(state["simulation_time_s"], f"{context}.simulation_time_s")
    _number(state["step_s"], f"{context}.step_s", positive=True)
    if _boolean(state["is_resimulation"], f"{context}.is_resimulation"):
        _fail(context, "resimulated state cannot enter a training episode")
    if not _boolean(state["is_valid"], f"{context}.is_valid"):
        _fail(context, "state is not marked valid")
    _string(state["movement_mode"], f"{context}.movement_mode")
    _vector(state["position_world_cm"], 3, f"{context}.position_world_cm")
    world_velocity = _vector(
        state["velocity_world_cm_per_s"], 3, f"{context}.velocity_world_cm_per_s"
    )
    local_velocity = _vector(
        state["velocity_local_planar_cm_per_s"],
        3,
        f"{context}.velocity_local_planar_cm_per_s",
    )
    yaw_deg = _number(state["facing_yaw_deg"], f"{context}.facing_yaw_deg")
    if yaw_deg < -180.0 - _NUMERIC_TOLERANCE or yaw_deg > 180.0 + _NUMERIC_TOLERANCE:
        _fail(context, "facing yaw is not normalized to [-180, 180]")
    facing = _vector(state["facing_unit_world"], 2, f"{context}.facing_unit_world")
    if not _close(math.hypot(*facing), 1.0, 1e-4):
        _fail(context, "facing vector is not unit length")
    _vector(
        state["angular_velocity_world_deg_per_s"],
        3,
        f"{context}.angular_velocity_world_deg_per_s",
    )

    yaw_rad = math.radians(yaw_deg)
    expected_local = (
        math.cos(yaw_rad) * world_velocity[0] + math.sin(yaw_rad) * world_velocity[1],
        -math.sin(yaw_rad) * world_velocity[0] + math.cos(yaw_rad) * world_velocity[1],
    )
    if not _close(local_velocity[0], expected_local[0], _ACTION_TOLERANCE_CM_PER_S) or not _close(
        local_velocity[1], expected_local[1], _ACTION_TOLERANCE_CM_PER_S
    ):
        _fail(context, "local velocity does not match world velocity and facing")
    if not _close(local_velocity[2], 0.0):
        _fail(context, "local planar velocity must have zero Z")
    return state


def _validate_action(value: Any, previous_state: dict[str, Any], context: str) -> dict[str, Any]:
    action = _object(value, context)
    _exact_keys(action, _ACTION_KEYS, context)
    _string(action["type"], f"{context}.type", expected="desired_velocity")
    if not _boolean(action["is_valid"], f"{context}.is_valid"):
        _fail(context, "action is not marked valid")
    _boolean(action["was_motionworld_automated"], f"{context}.was_motionworld_automated")
    world_velocity = _vector(
        action["velocity_world_cm_per_s"], 3, f"{context}.velocity_world_cm_per_s"
    )
    local_velocity = _vector(
        action["velocity_local_planar_cm_per_s"],
        3,
        f"{context}.velocity_local_planar_cm_per_s",
    )
    if not _close(world_velocity[2], 0.0) or not _close(local_velocity[2], 0.0):
        _fail(context, "desired velocity action must be planar")
    yaw_rad = math.radians(float(previous_state["facing_yaw_deg"]))
    expected_local = (
        math.cos(yaw_rad) * world_velocity[0] + math.sin(yaw_rad) * world_velocity[1],
        -math.sin(yaw_rad) * world_velocity[0] + math.cos(yaw_rad) * world_velocity[1],
    )
    if not _close(local_velocity[0], expected_local[0], _ACTION_TOLERANCE_CM_PER_S) or not _close(
        local_velocity[1], expected_local[1], _ACTION_TOLERANCE_CM_PER_S
    ):
        _fail(context, "local action does not match world action and previous-state facing")
    return action


def _validate_transition(value: Any, episode_id: int, context: str) -> dict[str, Any]:
    transition = _object(value, context)
    _exact_keys(transition, _TRANSITION_KEYS, context)
    _string(transition["record_type"], f"{context}.record_type", expected="transition")
    schema_version = _integer(transition["schema_version"], f"{context}.schema_version")
    if schema_version != EPISODE_SCHEMA_VERSION:
        _fail(context, "unsupported episode schema version")
    if (
        _integer(
            transition["transition_protocol_version"],
            f"{context}.transition_protocol_version",
        )
        != TRANSITION_PROTOCOL_VERSION
    ):
        _fail(context, "unsupported transition protocol version")
    if _integer(transition["episode_id"], f"{context}.episode_id", minimum=0) != episode_id:
        _fail(context, "transition episode does not match the header")
    _integer(transition["transition_sequence"], f"{context}.transition_sequence", minimum=0)
    start = _number(transition["start_simulation_time_s"], f"{context}.start_simulation_time_s")
    end = _number(transition["end_simulation_time_s"], f"{context}.end_simulation_time_s")
    delta = _number(transition["delta_time_s"], f"{context}.delta_time_s", positive=True)
    previous_state = _validate_state(transition["previous_state"], f"{context}.previous_state")
    _validate_action(transition["applied_action"], previous_state, f"{context}.applied_action")
    next_state = _validate_state(transition["next_state"], f"{context}.next_state")

    if next_state["sample_sequence"] != previous_state["sample_sequence"] + 1:
        _fail(context, "state callback sequences are not adjacent")
    previous_frame = previous_state["mover_step_server_frame"]
    next_frame = next_state["mover_step_server_frame"]
    if previous_frame != -1 and next_frame != -1 and next_frame != previous_frame + 1:
        _fail(context, "Mover frames are not adjacent")
    if not _close(start, float(previous_state["simulation_time_s"])):
        _fail(context, "start time does not match the previous state")
    if not _close(end, float(next_state["simulation_time_s"])):
        _fail(context, "end time does not match the next state")
    if not _close(delta, end - start, 1e-3):
        _fail(context, "delta time does not equal end minus start")
    if not _close(delta, float(next_state["step_s"]), 1e-3):
        _fail(context, "delta time does not match the finalized next-state step")
    return transition


def _validate_header(value: Any) -> dict[str, Any]:
    header = _object(value, "header")
    _exact_keys(header, _HEADER_KEYS, "header")
    _string(header["record_type"], "header.record_type", expected="episode_header")
    _string(header["schema_name"], "header.schema_name", expected="motionworld_episode")
    if _integer(header["schema_version"], "header.schema_version") != EPISODE_SCHEMA_VERSION:
        _fail("header", "unsupported episode schema version")
    created_utc = _string(header["created_utc"], "header.created_utc")
    try:
        datetime.fromisoformat(created_utc.replace("Z", "+00:00"))
    except ValueError as error:
        raise EpisodeValidationError("header.created_utc: invalid ISO-8601 timestamp") from error
    _string(header["engine_version"], "header.engine_version")
    _string(header["project_name"], "header.project_name")
    _integer(header["episode_id"], "header.episode_id", minimum=0)
    _string(
        header["state_source"],
        "header.state_source",
        expected="mover_finalized_sync_state",
    )

    conventions = _object(header["conventions"], "header.conventions")
    _exact_keys(conventions, _CONVENTION_KEYS, "header.conventions")
    expected_conventions = {
        "world_frame": "unreal_world_x_forward_y_right_z_up",
        "local_action_frame": "previous_state_character_x_forward_y_right",
        "position_unit": "centimetres",
        "linear_velocity_unit": "centimetres_per_second",
        "angle_unit": "degrees",
        "angular_velocity_unit": "degrees_per_second",
        "time_unit": "seconds",
    }
    for key, expected in expected_conventions.items():
        _string(conventions[key], f"header.conventions.{key}", expected=expected)

    stats = _object(header["recorder_stats"], "header.recorder_stats")
    _exact_keys(stats, _STATS_KEYS, "header.recorder_stats")
    for key in _STATS_KEYS:
        _integer(stats[key], f"header.recorder_stats.{key}", minimum=0)
    if stats["attempted_transition_count"] != (
        stats["recorded_transition_count"]
        + stats["rejected_transition_count"]
        + stats["capacity_drop_count"]
    ):
        _fail("header.recorder_stats", "attempt counts do not reconcile")
    return header


def _validate_footer(value: Any, episode_id: int) -> dict[str, Any]:
    footer = _object(value, "footer")
    _exact_keys(footer, _FOOTER_KEYS, "footer")
    _string(footer["record_type"], "footer.record_type", expected="episode_footer")
    if _integer(footer["schema_version"], "footer.schema_version") != EPISODE_SCHEMA_VERSION:
        _fail("footer", "unsupported episode schema version")
    if _integer(footer["episode_id"], "footer.episode_id", minimum=0) != episode_id:
        _fail("footer", "episode does not match the header")
    _integer(footer["transition_count"], "footer.transition_count", minimum=1)
    _integer(footer["first_transition_sequence"], "footer.first_transition_sequence", minimum=0)
    _integer(footer["last_transition_sequence"], "footer.last_transition_sequence", minimum=0)
    if not _boolean(footer["complete"], "footer.complete"):
        _fail("footer", "file is not marked complete")
    return footer


def load_episode(path: str | Path, *, max_transitions: int = MAX_TRANSITIONS) -> ValidatedEpisode:
    """Load one complete episode, rejecting ambiguity, leakage, and malformed numerics."""

    episode_path = Path(path)
    if episode_path.suffix != ".jsonl" or not episode_path.is_file():
        raise EpisodeValidationError(f"episode path is not an existing .jsonl file: {episode_path}")
    if max_transitions < 1 or max_transitions > MAX_TRANSITIONS:
        raise ValueError(f"max_transitions must be between 1 and {MAX_TRANSITIONS}")

    records: list[dict[str, Any]] = []
    with episode_path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                _fail(f"line {line_number}", "blank records are forbidden")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise EpisodeValidationError(f"line {line_number}: invalid JSON") from error
            records.append(_object(record, f"line {line_number}"))
            if len(records) > max_transitions + 2:
                _fail("episode", "file exceeds the configured transition bound")

    if len(records) < 3:
        _fail("episode", "requires a header, at least one transition, and a footer")
    header = _validate_header(records[0])
    episode_id = int(header["episode_id"])
    footer = _validate_footer(records[-1], episode_id)
    transitions = tuple(
        _validate_transition(record, episode_id, f"transition line {index + 2}")
        for index, record in enumerate(records[1:-1])
    )

    stats = header["recorder_stats"]
    if len(transitions) != stats["recorded_transition_count"]:
        _fail("episode", "payload count does not match header recorder stats")
    if len(transitions) != footer["transition_count"]:
        _fail("episode", "payload count does not match footer")
    if stats["observed_state_count"] < len(transitions) + 1:
        _fail("episode", "too few observed states for the accepted transitions")

    previous_transition: dict[str, Any] | None = None
    previous_sequence = -1
    for transition in transitions:
        sequence = int(transition["transition_sequence"])
        if sequence <= previous_sequence:
            _fail("episode", "transition sequences are not strictly increasing")
        if (
            previous_transition is not None
            and sequence == previous_sequence + 1
            and transition["previous_state"] != previous_transition["next_state"]
        ):
            _fail("episode", "consecutive rows do not share the same finalized endpoint")
        previous_sequence = sequence
        previous_transition = transition

    if footer["first_transition_sequence"] != transitions[0]["transition_sequence"]:
        _fail("footer", "first transition sequence does not match the payload")
    if footer["last_transition_sequence"] != transitions[-1]["transition_sequence"]:
        _fail("footer", "last transition sequence does not match the payload")
    return ValidatedEpisode(episode_path, header, transitions, footer)
