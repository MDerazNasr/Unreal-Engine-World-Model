"""Strict frozen configuration contract for the final Gate-R2 live proof."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

_BRIDGE_KEYS = {
    "start_episode_recording_on_begin_play",
    "request_reset_after_warmup_on_begin_play",
    "reset_warmup_finalized_samples",
    "begin_play_reset_episode_id",
    "reset_live_test_repeat_count",
    "reset_live_test_transitions_per_episode",
    "override_reset_anchor_yaw_for_live_test",
    "enable_timed_gate_scenario",
    "enable_varied_action_schedule",
    "enable_external_perturbation_schedule",
}
_NETWORK_KEYS = {
    "network_control_enabled",
    "local_port",
    "remote_port",
    "controller_mode",
    "has_reactive_target",
    "log_network_evidence",
    "max_network_evidence_lines",
}


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _int(value: object, context: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{context} must be an integer in [{minimum}, {maximum}]")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class GateR2Acceptance:
    expected_episode_ids: tuple[int, int, int]
    minimum_consecutive_intervals: int
    maximum_p95_latency_ms: float
    required_verified_resets: int
    require_unedited_recording: bool


@dataclass(frozen=True, slots=True)
class GateR2Manifest:
    blueprint_asset: str
    service_config_path: Path
    bridge_settings: Mapping[str, bool | int | str]
    network_settings: Mapping[str, bool | int | str]
    acceptance: GateR2Acceptance
    canonical_sha256: str


def load_gate_r2_manifest(path: Path, repository_root: Path) -> GateR2Manifest:
    """Load, validate, and hash the exact default-off Gate-R2 setup."""

    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "manifest")
    _keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "blueprint_asset",
            "service",
            "bridge_settings",
            "network_settings",
            "acceptance",
        },
        "manifest",
    )
    if raw["schema_name"] != "motionworld_gate_r2_live_manifest":
        raise ValueError("unsupported Gate-R2 manifest schema name")
    if raw["schema_version"] != 1:
        raise ValueError("unsupported Gate-R2 manifest schema version")
    blueprint_asset = raw["blueprint_asset"]
    if not isinstance(blueprint_asset, str) or not blueprint_asset.startswith("/Game/"):
        raise ValueError("blueprint_asset must be a /Game/ asset path")

    service = _mapping(raw["service"], "service")
    _keys(
        service,
        {"config_path", "sha256", "runtime_config_sha256", "transport_config_sha256"},
        "service",
    )
    relative = service["config_path"]
    if (
        not isinstance(relative, str)
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
    ):
        raise ValueError("service.config_path must stay inside the repository")
    service_path = repository_root / relative
    hashes = {
        service_path: service["sha256"],
        repository_root / "configs/control_runtime.yaml": service["runtime_config_sha256"],
        repository_root / "configs/control_transport.yaml": service["transport_config_sha256"],
    }
    for source, expected in hashes.items():
        if not isinstance(expected, str) or _sha256(source) != expected:
            raise ValueError(f"frozen SHA-256 mismatch for {source.relative_to(repository_root)}")

    bridge = _mapping(raw["bridge_settings"], "bridge_settings")
    network = _mapping(raw["network_settings"], "network_settings")
    _keys(bridge, _BRIDGE_KEYS, "bridge_settings")
    _keys(network, _NETWORK_KEYS, "network_settings")
    bool_bridge = _BRIDGE_KEYS - {
        "reset_warmup_finalized_samples",
        "begin_play_reset_episode_id",
        "reset_live_test_repeat_count",
        "reset_live_test_transitions_per_episode",
    }
    if any(type(bridge[name]) is not bool for name in bool_bridge):
        raise ValueError("bridge boolean settings must be booleans")
    _int(bridge["reset_warmup_finalized_samples"], "reset warmup", 2, 10_000)
    first_episode = _int(bridge["begin_play_reset_episode_id"], "first episode", 0, 2**63 - 4)
    repeats = _int(bridge["reset_live_test_repeat_count"], "reset repeats", 1, 10)
    if repeats != 3:
        raise ValueError("Gate R2 requires exactly three configured resets")
    _int(bridge["reset_live_test_transitions_per_episode"], "episode transitions", 1, 10_000)
    if bridge["start_episode_recording_on_begin_play"]:
        raise ValueError("immediate recording must be disabled before the warmup reset")
    if not bridge["request_reset_after_warmup_on_begin_play"]:
        raise ValueError("configured warmup resets must be enabled")
    network_booleans = {
        "network_control_enabled",
        "has_reactive_target",
        "log_network_evidence",
    }
    if any(type(network[name]) is not bool for name in network_booleans):
        raise ValueError("network boolean settings must be booleans")
    if not network["network_control_enabled"] or not network["log_network_evidence"]:
        raise ValueError("network control and bounded evidence must be enabled")
    if network["controller_mode"] != "echo":
        raise ValueError("Gate R2 requires the echo controller")
    local = _int(network["local_port"], "local port", 1, 65_535)
    remote = _int(network["remote_port"], "remote port", 1, 65_535)
    if local == remote:
        raise ValueError("local and remote ports must differ")
    _int(network["max_network_evidence_lines"], "evidence cap", 1, 10_000)

    acceptance = _mapping(raw["acceptance"], "acceptance")
    _keys(
        acceptance,
        {
            "expected_episode_ids",
            "minimum_consecutive_intervals",
            "maximum_p95_latency_ms",
            "required_verified_resets",
            "require_unedited_recording",
        },
        "acceptance",
    )
    episodes = acceptance["expected_episode_ids"]
    if (
        not isinstance(episodes, list)
        or len(episodes) != 3
        or any(type(value) is not int for value in episodes)
    ):
        raise ValueError("acceptance.expected_episode_ids must contain exactly three integers")
    expected_episodes = tuple(first_episode + index for index in range(repeats))
    if tuple(episodes) != expected_episodes:
        raise ValueError("expected episodes must exactly match the three configured resets")
    minimum = _int(acceptance["minimum_consecutive_intervals"], "minimum intervals", 100, 100_000)
    reset_count = _int(acceptance["required_verified_resets"], "required resets", 3, 3)
    latency = acceptance["maximum_p95_latency_ms"]
    if type(latency) not in {int, float} or not 0.0 < float(latency) <= 100.0:
        raise ValueError("maximum p95 latency must be in (0, 100] ms")
    if acceptance["require_unedited_recording"] is not True:
        raise ValueError("the unedited recording requirement cannot be disabled")

    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return GateR2Manifest(
        blueprint_asset=blueprint_asset,
        service_config_path=service_path,
        bridge_settings=MappingProxyType(dict(bridge)),
        network_settings=MappingProxyType(dict(network)),
        acceptance=GateR2Acceptance(
            expected_episode_ids=expected_episodes,
            minimum_consecutive_intervals=minimum,
            maximum_p95_latency_ms=float(latency),
            required_verified_resets=reset_count,
            require_unedited_recording=True,
        ),
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
    )
