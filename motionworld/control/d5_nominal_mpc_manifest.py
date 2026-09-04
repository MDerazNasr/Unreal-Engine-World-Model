"""Strict, frozen configuration contract for the D5 live nominal-MPC demo."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

_BLUEPRINT_ASSET = "/Game/Blueprints/SandboxCharacter_Mover"
_EPISODE_ID = 7504
_TRANSITIONS = 120
_RESET_ANCHOR = (-800.0, 0.0, 90.0)
_TARGET = (800.0, 0.0, 90.0)
_TERMINAL_VELOCITY = (0.0, 0.0)
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
    "max_planar_speed_cm_per_sec",
}
_NETWORK_KEYS = {
    "network_control_enabled",
    "local_port",
    "remote_port",
    "controller_mode",
    "has_reactive_target",
    "reactive_target_world_cm",
    "reactive_terminal_velocity_local_cm_per_sec",
    "draw_world_model_visualization",
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


def _vector(value: object, size: int, context: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{context} must contain exactly {size} coordinates")
    if any(type(item) not in {int, float} or not math.isfinite(item) for item in value):
        raise ValueError(f"{context} coordinates must be finite numbers")
    return tuple(float(item) for item in value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class D5DemoGeometry:
    reset_anchor_world_cm: tuple[float, float, float]
    reactive_target_world_cm: tuple[float, float, float]
    terminal_velocity_local_cm_per_sec: tuple[float, float]


@dataclass(frozen=True, slots=True)
class D5NominalMpcManifest:
    blueprint_asset: str
    service_config_path: Path
    planner_config_path: Path
    bridge_settings: Mapping[str, object]
    network_settings: Mapping[str, object]
    geometry: D5DemoGeometry
    expected_episode_id: int
    visual_inspection_transitions: int
    canonical_sha256: str


def load_d5_nominal_mpc_manifest(path: Path, repository_root: Path) -> D5NominalMpcManifest:
    """Load and validate the exact reversible D5 Blueprint configuration."""

    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "manifest")
    _keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "blueprint_asset",
            "service",
            "demo_geometry",
            "bridge_settings",
            "network_settings",
            "acceptance",
        },
        "manifest",
    )
    if raw["schema_name"] != "motionworld_d5_nominal_mpc_manifest":
        raise ValueError("unsupported D5 manifest schema name")
    if raw["schema_version"] != 1:
        raise ValueError("unsupported D5 manifest schema version")
    if raw["blueprint_asset"] != _BLUEPRINT_ASSET:
        raise ValueError(f"D5 must target only {_BLUEPRINT_ASSET}")

    service = _mapping(raw["service"], "service")
    _keys(
        service,
        {
            "config_path",
            "sha256",
            "planner_config_path",
            "planner_sha256",
            "runtime_config_sha256",
            "transport_config_sha256",
        },
        "service",
    )
    if service["config_path"] != "configs/control_service_demo_nominal_mpc.yaml":
        raise ValueError("D5 must bind configs/control_service_demo_nominal_mpc.yaml")
    if service["planner_config_path"] != "configs/live_nominal_mpc_demo.yaml":
        raise ValueError("D5 must bind configs/live_nominal_mpc_demo.yaml")
    service_path = repository_root / service["config_path"]
    planner_path = repository_root / service["planner_config_path"]
    hashes = {
        service_path: service["sha256"],
        planner_path: service["planner_sha256"],
        repository_root / "configs/control_runtime.yaml": service["runtime_config_sha256"],
        repository_root / "configs/control_transport.yaml": service["transport_config_sha256"],
    }
    for source, expected in hashes.items():
        if not isinstance(expected, str) or _sha256(source) != expected:
            raise ValueError(f"frozen SHA-256 mismatch for {source.relative_to(repository_root)}")

    geometry = _mapping(raw["demo_geometry"], "demo_geometry")
    _keys(
        geometry,
        {
            "reset_anchor_world_cm",
            "reactive_target_world_cm",
            "terminal_velocity_local_cm_per_sec",
        },
        "demo_geometry",
    )
    reset_anchor = _vector(geometry["reset_anchor_world_cm"], 3, "reset anchor")
    target = _vector(geometry["reactive_target_world_cm"], 3, "reactive target")
    terminal_velocity = _vector(
        geometry["terminal_velocity_local_cm_per_sec"], 2, "terminal velocity"
    )
    if reset_anchor != _RESET_ANCHOR:
        raise ValueError("D5 reset anchor must be (-800, 0, 90) cm")
    if target != _TARGET:
        raise ValueError("D5 target must be the clear forward point (800, 0, 90) cm")
    if terminal_velocity != _TERMINAL_VELOCITY:
        raise ValueError("D5 terminal velocity must be zero")

    bridge = _mapping(raw["bridge_settings"], "bridge_settings")
    network = _mapping(raw["network_settings"], "network_settings")
    _keys(bridge, _BRIDGE_KEYS, "bridge_settings")
    _keys(network, _NETWORK_KEYS, "network_settings")
    bridge_integer_keys = {
        "reset_warmup_finalized_samples",
        "begin_play_reset_episode_id",
        "reset_live_test_repeat_count",
        "reset_live_test_transitions_per_episode",
    }
    bridge_boolean_keys = _BRIDGE_KEYS - bridge_integer_keys - {
        "max_planar_speed_cm_per_sec"
    }
    if any(type(bridge[name]) is not bool for name in bridge_boolean_keys):
        raise ValueError("bridge boolean settings must be booleans")
    _int(bridge["reset_warmup_finalized_samples"], "reset warmup", 2, 10_000)
    episode_id = _int(bridge["begin_play_reset_episode_id"], "episode id", 0, 2**63 - 1)
    repeats = _int(bridge["reset_live_test_repeat_count"], "reset repeats", 1, 10)
    transitions = _int(
        bridge["reset_live_test_transitions_per_episode"], "episode transitions", 1, 10_000
    )
    if episode_id != _EPISODE_ID or repeats != 1:
        raise ValueError("D5 requires exactly one nonsealed episode with id 7504")
    if transitions != _TRANSITIONS:
        raise ValueError("D5 requires exactly 120 transitions for visual inspection")
    bridge_max_speed = bridge["max_planar_speed_cm_per_sec"]
    if (
        type(bridge_max_speed) not in {int, float}
        or not math.isfinite(bridge_max_speed)
        or float(bridge_max_speed) != 165.0
    ):
        raise ValueError("D5 bridge maximum automated planar speed must be exactly 165 cm/s")
    if bridge["start_episode_recording_on_begin_play"]:
        raise ValueError("recording must wait for the verified begin-play reset")
    if not bridge["request_reset_after_warmup_on_begin_play"]:
        raise ValueError("the verified begin-play reset must be enabled")
    disabled_producers = {
        "enable_timed_gate_scenario",
        "enable_varied_action_schedule",
        "enable_external_perturbation_schedule",
    }
    if any(bridge[name] for name in disabled_producers):
        raise ValueError("competing scenario producers must be disabled")

    network_boolean_keys = {
        "network_control_enabled",
        "has_reactive_target",
        "draw_world_model_visualization",
        "log_network_evidence",
    }
    if any(type(network[name]) is not bool for name in network_boolean_keys):
        raise ValueError("network boolean settings must be booleans")
    if not network["network_control_enabled"]:
        raise ValueError("network control must be enabled")
    if network["controller_mode"] != "nominal_mpc":
        raise ValueError("D5 requires the nominal_mpc controller")
    if not network["has_reactive_target"]:
        raise ValueError("D5 requires the reactive target")
    if _vector(network["reactive_target_world_cm"], 3, "network reactive target") != target:
        raise ValueError("network reactive target must match demo geometry")
    if (
        _vector(
            network["reactive_terminal_velocity_local_cm_per_sec"],
            2,
            "network terminal velocity",
        )
        != terminal_velocity
    ):
        raise ValueError("network terminal velocity must match demo geometry")
    if not network["draw_world_model_visualization"]:
        raise ValueError("D5 world-model visualization must be enabled")
    if not network["log_network_evidence"]:
        raise ValueError("D5 bounded network evidence must be enabled")
    local = _int(network["local_port"], "local port", 1, 65_535)
    remote = _int(network["remote_port"], "remote port", 1, 65_535)
    if local == remote:
        raise ValueError("local and remote ports must differ")
    _int(network["max_network_evidence_lines"], "evidence cap", 1, 10_000)

    acceptance = _mapping(raw["acceptance"], "acceptance")
    _keys(
        acceptance,
        {"expected_episode_id", "visual_inspection_transitions", "require_network_evidence"},
        "acceptance",
    )
    if acceptance["expected_episode_id"] != episode_id:
        raise ValueError("acceptance episode must match the configured episode")
    if acceptance["visual_inspection_transitions"] != transitions:
        raise ValueError("acceptance transitions must match the configured transitions")
    if acceptance["require_network_evidence"] is not True:
        raise ValueError("network evidence requirement cannot be disabled")

    normalized_network = dict(network)
    normalized_network["reactive_target_world_cm"] = list(target)
    normalized_network["reactive_terminal_velocity_local_cm_per_sec"] = list(
        terminal_velocity
    )
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return D5NominalMpcManifest(
        blueprint_asset=_BLUEPRINT_ASSET,
        service_config_path=service_path,
        planner_config_path=planner_path,
        bridge_settings=MappingProxyType(dict(bridge)),
        network_settings=MappingProxyType(normalized_network),
        geometry=D5DemoGeometry(reset_anchor, target, terminal_velocity),
        expected_episode_id=episode_id,
        visual_inspection_transitions=transitions,
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
    )
