"""Strict configuration contract for the 10 Hz live control loop."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], *, context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _positive_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def _nonnegative_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{context} must be a non-negative integer")
    return value


def _finite_number(value: object, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{context} must be a finite number")
    return result


def _nonempty_string(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _literal(value: object, expected: str, *, context: str) -> str:
    if value != expected:
        raise ValueError(f"{context} must be {expected!r}")
    return expected


@dataclass(frozen=True, slots=True)
class ControlRuntimeConfig:
    """Timing and failure semantics shared by the future Unreal/Python runtime."""

    status: str
    control_frequency_hz: int
    decision_interval_ms: int
    observation_time_source: str
    observation_epoch: str
    boundary_selection: str
    catch_up_policy: str
    sequence_policy: str
    first_sequence: int
    deadline_ms: int
    deadline_boundary: str
    deadline_measurement: str
    stale_when: str
    late_response_policy: str
    valid_action_application: str
    cold_start_action_local_cm_s: tuple[float, float]
    hold_last_valid_action_for_consecutive_misses: int
    safe_stop_on_consecutive_miss: int
    miss_definition: str
    valid_recovery_policy: str
    reset_policy: str

    def __post_init__(self) -> None:
        if not self.status.strip():
            raise ValueError("status must be non-empty")
        _positive_int(self.control_frequency_hz, context="control_frequency_hz")
        _positive_int(self.decision_interval_ms, context="decision_interval_ms")
        expected_interval_ms = 1000.0 / self.control_frequency_hz
        if not math.isclose(
            float(self.decision_interval_ms), expected_interval_ms, rel_tol=0.0, abs_tol=1.0e-12
        ):
            raise ValueError("control frequency and decision interval disagree")
        if self.first_sequence != 0:
            raise ValueError("first observation sequence must be zero")
        _positive_int(self.deadline_ms, context="deadline_ms")
        if self.deadline_ms != self.decision_interval_ms:
            raise ValueError("response deadline must equal one decision interval")
        if len(self.cold_start_action_local_cm_s) != 2 or not all(
            math.isfinite(value) for value in self.cold_start_action_local_cm_s
        ):
            raise ValueError("cold-start action must contain two finite values")
        if self.cold_start_action_local_cm_s != (0.0, 0.0):
            raise ValueError("cold-start action must be the safe zero action")
        _positive_int(
            self.hold_last_valid_action_for_consecutive_misses,
            context="hold miss count",
        )
        _positive_int(
            self.safe_stop_on_consecutive_miss,
            context="safe-stop miss count",
        )
        if (
            self.safe_stop_on_consecutive_miss
            != self.hold_last_valid_action_for_consecutive_misses + 1
        ):
            raise ValueError("safe stop must follow immediately after the allowed hold misses")


def load_control_runtime_config(path: Path) -> ControlRuntimeConfig:
    """Load the frozen runtime contract and reject semantic or schema drift."""

    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), context="runtime config")
    _exact_keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "status",
            "control_frequency_hz",
            "decision_interval_ms",
            "observation_schedule",
            "response_deadline",
            "fallback",
        },
        context="runtime config",
    )
    _literal(raw["schema_name"], "motionworld_control_runtime_config", context="schema_name")
    if raw["schema_version"] != 1:
        raise ValueError("unsupported control runtime schema version")

    observation = _mapping(raw["observation_schedule"], context="observation_schedule")
    _exact_keys(
        observation,
        {
            "time_source",
            "epoch",
            "boundary_selection",
            "catch_up_policy",
            "sequence_policy",
            "first_sequence",
        },
        context="observation_schedule",
    )
    deadline = _mapping(raw["response_deadline"], context="response_deadline")
    _exact_keys(
        deadline,
        {
            "duration_ms",
            "boundary",
            "measurement",
            "stale_when",
            "late_response_policy",
            "valid_action_application",
        },
        context="response_deadline",
    )
    fallback = _mapping(raw["fallback"], context="fallback")
    _exact_keys(
        fallback,
        {
            "cold_start_action_local_cm_s",
            "hold_last_valid_action_for_consecutive_misses",
            "safe_stop_on_consecutive_miss",
            "miss_definition",
            "valid_recovery_policy",
            "reset_policy",
        },
        context="fallback",
    )
    cold_start = fallback["cold_start_action_local_cm_s"]
    if not isinstance(cold_start, list) or len(cold_start) != 2:
        raise ValueError("cold_start_action_local_cm_s must be a two-value list")

    return ControlRuntimeConfig(
        status=_nonempty_string(raw["status"], context="status"),
        control_frequency_hz=_positive_int(
            raw["control_frequency_hz"], context="control_frequency_hz"
        ),
        decision_interval_ms=_positive_int(
            raw["decision_interval_ms"], context="decision_interval_ms"
        ),
        observation_time_source=_literal(
            observation["time_source"], "unreal_simulation_time", context="time_source"
        ),
        observation_epoch=_literal(
            observation["epoch"],
            "first_valid_post_reset_finalize",
            context="observation epoch",
        ),
        boundary_selection=_literal(
            observation["boundary_selection"],
            "first_valid_finalize_at_or_after_slot_boundary",
            context="boundary_selection",
        ),
        catch_up_policy=_literal(
            observation["catch_up_policy"],
            "latest_elapsed_slot_only_no_burst",
            context="catch_up_policy",
        ),
        sequence_policy=_literal(
            observation["sequence_policy"],
            "increment_once_per_emitted_observation",
            context="sequence_policy",
        ),
        first_sequence=_nonnegative_int(
            observation["first_sequence"], context="first_sequence"
        ),
        deadline_ms=_positive_int(deadline["duration_ms"], context="deadline duration"),
        deadline_boundary=_literal(
            deadline["boundary"], "exclusive", context="deadline boundary"
        ),
        deadline_measurement=_literal(
            deadline["measurement"],
            "unreal_monotonic_observation_send_to_action_receive",
            context="deadline measurement",
        ),
        stale_when=_literal(
            deadline["stale_when"],
            "next_observation_emitted_or_deadline_reached",
            context="stale_when",
        ),
        late_response_policy=_literal(
            deadline["late_response_policy"], "discard", context="late_response_policy"
        ),
        valid_action_application=_literal(
            deadline["valid_action_application"],
            "apply_immediately_and_hold_until_replaced_or_fallback",
            context="valid_action_application",
        ),
        cold_start_action_local_cm_s=(
            _finite_number(cold_start[0], context="cold-start action x"),
            _finite_number(cold_start[1], context="cold-start action y"),
        ),
        hold_last_valid_action_for_consecutive_misses=_positive_int(
            fallback["hold_last_valid_action_for_consecutive_misses"],
            context="hold miss count",
        ),
        safe_stop_on_consecutive_miss=_positive_int(
            fallback["safe_stop_on_consecutive_miss"], context="safe-stop miss count"
        ),
        miss_definition=_literal(
            fallback["miss_definition"],
            "no_valid_matching_action_by_deadline",
            context="miss_definition",
        ),
        valid_recovery_policy=_literal(
            fallback["valid_recovery_policy"],
            "reset_miss_count_after_current_matching_action",
            context="valid_recovery_policy",
        ),
        reset_policy=_literal(
            fallback["reset_policy"],
            "clear_action_sequence_deadline_and_miss_state",
            context="reset_policy",
        ),
    )
