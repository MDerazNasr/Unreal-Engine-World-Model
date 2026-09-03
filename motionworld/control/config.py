"""Strict configuration for the standalone Python control service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from motionworld.protocol.observation import CONTROLLER_MODES
from motionworld.protocol.runtime_config import ControlRuntimeConfig, load_control_runtime_config
from motionworld.protocol.transport import ControlTransportConfig, load_control_transport_config


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _positive_int(value: object, context: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{context} must be an integer in [1, {maximum}]")
    return value


def _relative_config_path(base: Path, value: object, context: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"{context} must be a non-empty relative path")
    relative = Path(value)
    if ".." in relative.parts:
        raise ValueError(f"{context} must stay inside the service config directory")
    return base / relative


@dataclass(frozen=True, slots=True)
class ControlServiceConfig:
    """Fully resolved and bounded service configuration."""

    transport: ControlTransportConfig
    runtime: ControlRuntimeConfig
    controller_mode: str
    poll_interval_ms: int
    planner_shutdown_timeout_ms: int
    max_tracked_episodes: int
    max_recent_rejections: int
    max_error_utf8_bytes: int

    def __post_init__(self) -> None:
        if self.controller_mode not in CONTROLLER_MODES:
            raise ValueError("controller_mode is unsupported")
        _positive_int(self.poll_interval_ms, "poll_interval_ms", 100)
        _positive_int(
            self.planner_shutdown_timeout_ms,
            "planner_shutdown_timeout_ms",
            10_000,
        )
        _positive_int(self.max_tracked_episodes, "max_tracked_episodes", 1_024)
        _positive_int(self.max_recent_rejections, "max_recent_rejections", 1_024)
        _positive_int(self.max_error_utf8_bytes, "max_error_utf8_bytes", 4_096)


def load_control_service_config(path: Path) -> ControlServiceConfig:
    """Load the service plus its relative runtime/transport contracts."""

    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "service config")
    _keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "transport_config",
            "runtime_config",
            "controller_mode",
            "event_loop",
            "diagnostics",
        },
        "service config",
    )
    if raw["schema_name"] != "motionworld_control_service_config":
        raise ValueError("unsupported service schema name")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ValueError("unsupported service schema version")
    if not isinstance(raw["controller_mode"], str):
        raise ValueError("controller_mode must be a string")

    event_loop = _mapping(raw["event_loop"], "event_loop")
    _keys(
        event_loop,
        {"poll_interval_ms", "planner_shutdown_timeout_ms", "max_tracked_episodes"},
        "event_loop",
    )
    diagnostics = _mapping(raw["diagnostics"], "diagnostics")
    _keys(
        diagnostics,
        {"max_recent_rejections", "max_error_utf8_bytes"},
        "diagnostics",
    )
    base = path.parent
    transport_path = _relative_config_path(
        base, raw["transport_config"], "transport_config"
    )
    runtime_path = _relative_config_path(base, raw["runtime_config"], "runtime_config")
    return ControlServiceConfig(
        transport=load_control_transport_config(transport_path),
        runtime=load_control_runtime_config(runtime_path),
        controller_mode=raw["controller_mode"],
        poll_interval_ms=_positive_int(
            event_loop["poll_interval_ms"], "poll_interval_ms", 100
        ),
        planner_shutdown_timeout_ms=_positive_int(
            event_loop["planner_shutdown_timeout_ms"],
            "planner_shutdown_timeout_ms",
            10_000,
        ),
        max_tracked_episodes=_positive_int(
            event_loop["max_tracked_episodes"], "max_tracked_episodes", 1_024
        ),
        max_recent_rejections=_positive_int(
            diagnostics["max_recent_rejections"], "max_recent_rejections", 1_024
        ),
        max_error_utf8_bytes=_positive_int(
            diagnostics["max_error_utf8_bytes"], "max_error_utf8_bytes", 4_096
        ),
    )
