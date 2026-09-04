"""Strict reversible Blueprint contract for the D6 learned-model overlay."""

from __future__ import annotations

import hashlib
import json
import math
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
    if any(
        type(item) not in {int, float} or not math.isfinite(item) for item in value
    ):
        raise ValueError(f"{context} coordinates must be finite numbers")
    return tuple(float(item) for item in value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class D6DemoGeometry:
    reset_anchor_world_cm: tuple[float, float, float]
    reactive_target_world_cm: tuple[float, float, float]
    terminal_velocity_local_cm_per_sec: tuple[float, float]


@dataclass(frozen=True, slots=True)
class D6ResidualOverlayManifest:
    blueprint_asset: str
    service_config_path: Path
    planner_config_path: Path
    bridge_settings: Mapping[str, object]
    network_settings: Mapping[str, object]
    geometry: D6DemoGeometry
    expected_episode_id: int
    visual_inspection_transitions: int
    canonical_sha256: str


def load_d6_residual_overlay_manifest(
    path: Path,
    repository_root: Path,
) -> D6ResidualOverlayManifest:
    """Load D6 without weakening D5's reset, producer, or safety constraints."""

    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "manifest")
    _keys(
        raw,
        {
            "schema_name", "schema_version", "blueprint_asset", "service",
            "demo_geometry", "bridge_settings", "network_settings", "acceptance",
        },
        "manifest",
    )
    if raw["schema_name"] != "motionworld_d6_residual_overlay_manifest":
        raise ValueError("unsupported D6 manifest schema")
    if raw["schema_version"] != 1:
        raise ValueError("unsupported D6 manifest version")
    blueprint = "/Game/Blueprints/SandboxCharacter_Mover"
    if raw["blueprint_asset"] != blueprint:
        raise ValueError("D6 may alter only the frozen demo Blueprint")

    service = _mapping(raw["service"], "service")
    _keys(
        service,
        {
            "config_path", "sha256", "planner_config_path", "planner_sha256",
            "runtime_config_sha256", "transport_config_sha256",
        },
        "service",
    )
    if service["config_path"] != "configs/control_service_demo_nominal_mpc.yaml":
        raise ValueError("D6 must retain the nominal MPC service")
    if service["planner_config_path"] != "configs/live_residual_overlay_demo.yaml":
        raise ValueError("D6 must use the verified matched-overlay config")
    service_path = repository_root / service["config_path"]
    planner_path = repository_root / service["planner_config_path"]
    for source, expected_hash in {
        service_path: service["sha256"],
        planner_path: service["planner_sha256"],
        repository_root / "configs/control_runtime.yaml": service["runtime_config_sha256"],
        repository_root / "configs/control_transport.yaml": service["transport_config_sha256"],
    }.items():
        if not isinstance(expected_hash, str) or _sha256(source) != expected_hash:
            raise ValueError(f"D6 frozen hash mismatch for {source.relative_to(repository_root)}")

    geometry = _mapping(raw["demo_geometry"], "demo_geometry")
    _keys(
        geometry,
        {
            "reset_anchor_world_cm", "reactive_target_world_cm",
            "terminal_velocity_local_cm_per_sec",
        },
        "demo_geometry",
    )
    reset = _vector(geometry["reset_anchor_world_cm"], 3, "reset anchor")
    target = _vector(geometry["reactive_target_world_cm"], 3, "target")
    terminal = _vector(
        geometry["terminal_velocity_local_cm_per_sec"], 2, "terminal velocity"
    )
    if reset != (-800.0, 0.0, 90.0) or target != (800.0, 0.0, 90.0):
        raise ValueError("D6 geometry must match the accepted clear-path scene")
    if terminal != (0.0, 0.0):
        raise ValueError("D6 terminal velocity must be zero")

    bridge = _mapping(raw["bridge_settings"], "bridge_settings")
    network = _mapping(raw["network_settings"], "network_settings")
    _keys(bridge, _BRIDGE_KEYS, "bridge_settings")
    _keys(network, _NETWORK_KEYS, "network_settings")
    if bridge["begin_play_reset_episode_id"] != 7601:
        raise ValueError("D6 primary live identity is episode 7601")
    if bridge["reset_live_test_repeat_count"] != 1:
        raise ValueError("D6 must perform exactly one reset episode")
    if bridge["reset_live_test_transitions_per_episode"] != 120:
        raise ValueError("D6 visual episode must contain 120 transitions")
    if bridge["start_episode_recording_on_begin_play"] is not False:
        raise ValueError("recording must wait for the verified reset")
    if bridge["request_reset_after_warmup_on_begin_play"] is not True:
        raise ValueError("D6 requires the verified begin-play reset")
    for key in (
        "enable_timed_gate_scenario", "enable_varied_action_schedule",
        "enable_external_perturbation_schedule",
    ):
        if bridge[key] is not False:
            raise ValueError("competing scenario producers must remain disabled")
    if float(bridge["max_planar_speed_cm_per_sec"]) != 165.0:
        raise ValueError("D6 maximum speed must match the nominal planner")
    if network["controller_mode"] != "nominal_mpc":
        raise ValueError("the learned overlay must not claim action ownership")
    for key in (
        "network_control_enabled", "has_reactive_target",
        "draw_world_model_visualization", "log_network_evidence",
    ):
        if network[key] is not True:
            raise ValueError(f"D6 requires network setting {key}")
    if _vector(network["reactive_target_world_cm"], 3, "target") != target:
        raise ValueError("network target differs from D6 geometry")
    if _vector(network["reactive_terminal_velocity_local_cm_per_sec"], 2, "terminal") != terminal:
        raise ValueError("network terminal velocity differs from D6 geometry")
    local = _int(network["local_port"], "local port", 1, 65_535)
    remote = _int(network["remote_port"], "remote port", 1, 65_535)
    if local == remote:
        raise ValueError("D6 network endpoints must differ")

    acceptance = _mapping(raw["acceptance"], "acceptance")
    _keys(
        acceptance,
        {
            "expected_episode_id", "visual_inspection_transitions",
            "require_network_evidence", "controller_owns_actions",
            "overlay_is_prediction_only",
        },
        "acceptance",
    )
    if acceptance != {
        "expected_episode_id": 7601,
        "visual_inspection_transitions": 120,
        "require_network_evidence": True,
        "controller_owns_actions": "nominal_mpc",
        "overlay_is_prediction_only": True,
    }:
        raise ValueError("D6 acceptance boundary was weakened")

    normalized_network = dict(network)
    normalized_network["reactive_target_world_cm"] = list(target)
    normalized_network["reactive_terminal_velocity_local_cm_per_sec"] = list(terminal)
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    return D6ResidualOverlayManifest(
        blueprint_asset=blueprint,
        service_config_path=service_path,
        planner_config_path=planner_path,
        bridge_settings=MappingProxyType(dict(bridge)),
        network_settings=MappingProxyType(normalized_network),
        geometry=D6DemoGeometry(reset, target, terminal),
        expected_episode_id=7601,
        visual_inspection_transitions=120,
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
    )
