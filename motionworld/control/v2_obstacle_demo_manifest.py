"""Strict reversible Blueprint contract for the V2 moving-obstacle demo."""

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
    "timed_gate_continue_after_success_plane_crossing",
    "timed_gate_scenario_seed",
    "timed_gate_forward_distance_cm",
    "timed_gate_amplitude_cm",
    "timed_gate_period_seconds",
    "timed_gate_phase_offset_radians",
    "timed_gate_half_extents_cm",
    "timed_gate_timeout_seconds",
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


def _number(value: object, context: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(value):
        raise ValueError(f"{context} must be a finite number")
    return float(value)


def _vector(value: object, size: int, context: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{context} must contain exactly {size} coordinates")
    return tuple(_number(item, f"{context} coordinate") for item in value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class V2DemoGeometry:
    reset_anchor_world_cm: tuple[float, float, float]
    reactive_target_world_cm: tuple[float, float, float]
    terminal_velocity_local_cm_per_sec: tuple[float, float]


@dataclass(frozen=True, slots=True)
class V2ObstacleDemoManifest:
    blueprint_asset: str
    service_config_path: Path
    planner_config_path: Path
    bridge_settings: Mapping[str, object]
    network_settings: Mapping[str, object]
    geometry: V2DemoGeometry
    expected_episode_id: int
    visual_inspection_transitions: int
    canonical_sha256: str


def load_v2_obstacle_demo_manifest(
    path: Path,
    repository_root: Path,
) -> V2ObstacleDemoManifest:
    """Load V2 while freezing its controller, obstacle, and safety boundary."""

    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "manifest")
    _keys(
        raw,
        {
            "schema_name", "schema_version", "blueprint_asset", "service",
            "demo_geometry", "bridge_settings", "network_settings", "acceptance",
        },
        "manifest",
    )
    if raw["schema_name"] != "motionworld_v2_obstacle_demo_manifest":
        raise ValueError("unsupported V2 obstacle demo manifest schema")
    if raw["schema_version"] != 1:
        raise ValueError("unsupported V2 obstacle demo manifest version")
    blueprint = "/Game/Blueprints/SandboxCharacter_Mover"
    if raw["blueprint_asset"] != blueprint:
        raise ValueError("V2 may alter only the frozen demo Blueprint")

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
        raise ValueError("V2 must retain the nominal MPC service")
    if service["planner_config_path"] != "configs/live_moving_obstacle_demo.yaml":
        raise ValueError("V2 must use the moving-obstacle planner config")
    service_path = repository_root / service["config_path"]
    planner_path = repository_root / service["planner_config_path"]
    for source, expected_hash in {
        service_path: service["sha256"],
        planner_path: service["planner_sha256"],
        repository_root / "configs/control_runtime.yaml": service["runtime_config_sha256"],
        repository_root / "configs/control_transport.yaml": service["transport_config_sha256"],
    }.items():
        if not isinstance(expected_hash, str) or _sha256(source) != expected_hash:
            raise ValueError(
                f"V2 frozen hash mismatch for {source.relative_to(repository_root)}"
            )

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
        raise ValueError("V2 geometry must match the accepted demo corridor")
    if terminal != (0.0, 0.0):
        raise ValueError("V2 terminal velocity must be zero")

    bridge = _mapping(raw["bridge_settings"], "bridge_settings")
    network = _mapping(raw["network_settings"], "network_settings")
    _keys(bridge, _BRIDGE_KEYS, "bridge_settings")
    _keys(network, _NETWORK_KEYS, "network_settings")

    expected_bridge = {
        "start_episode_recording_on_begin_play": False,
        "request_reset_after_warmup_on_begin_play": True,
        "reset_warmup_finalized_samples": 60,
        "begin_play_reset_episode_id": 7701,
        "reset_live_test_repeat_count": 1,
        "reset_live_test_transitions_per_episode": 160,
        "override_reset_anchor_yaw_for_live_test": False,
        "enable_timed_gate_scenario": True,
        "timed_gate_continue_after_success_plane_crossing": True,
        "timed_gate_scenario_seed": 20260904,
        "timed_gate_forward_distance_cm": 350.0,
        "timed_gate_amplitude_cm": 185.0,
        "timed_gate_period_seconds": 3.7,
        "timed_gate_phase_offset_radians": 0.83,
        "timed_gate_half_extents_cm": [35.0, 55.0, 90.0],
        "timed_gate_timeout_seconds": 20.0,
        "enable_varied_action_schedule": False,
        "enable_external_perturbation_schedule": False,
        "max_planar_speed_cm_per_sec": 165.0,
    }
    for key, expected_value in expected_bridge.items():
        if type(expected_value) is bool and bridge[key] is not expected_value:
            raise ValueError("V2 bridge and moving-obstacle boundary was weakened")
        if type(expected_value) is int and type(bridge[key]) is not int:
            raise ValueError("V2 bridge integer settings must be integers")
    if bridge != expected_bridge:
        raise ValueError("V2 bridge and moving-obstacle boundary was weakened")

    expected_network = {
        "network_control_enabled": True,
        "local_port": 52580,
        "remote_port": 52581,
        "controller_mode": "nominal_mpc",
        "has_reactive_target": True,
        "reactive_target_world_cm": [800.0, 0.0, 90.0],
        "reactive_terminal_velocity_local_cm_per_sec": [0.0, 0.0],
        "draw_world_model_visualization": True,
        "log_network_evidence": True,
        "max_network_evidence_lines": 4096,
    }
    for key in (
        "network_control_enabled", "has_reactive_target",
        "draw_world_model_visualization", "log_network_evidence",
    ):
        if network[key] is not True:
            raise ValueError(f"V2 requires network setting {key}")
    if network["controller_mode"] != "nominal_mpc":
        raise ValueError("V2 requires nominal MPC to own the actions")
    if _vector(network["reactive_target_world_cm"], 3, "target") != target:
        raise ValueError("network target differs from V2 geometry")
    if _vector(
        network["reactive_terminal_velocity_local_cm_per_sec"], 2, "terminal"
    ) != terminal:
        raise ValueError("network terminal velocity differs from V2 geometry")
    local = _int(network["local_port"], "local port", 1, 65_535)
    remote = _int(network["remote_port"], "remote port", 1, 65_535)
    if local == remote:
        raise ValueError("V2 network endpoints must differ")
    _int(network["max_network_evidence_lines"], "evidence cap", 1, 10_000)
    if network != expected_network:
        raise ValueError("V2 network boundary was weakened")

    acceptance = _mapping(raw["acceptance"], "acceptance")
    _keys(
        acceptance,
        {
            "expected_episode_id", "visual_inspection_transitions",
            "require_network_evidence", "controller_owns_actions",
            "obstacle_motion_is_reproducible", "motion_seed_is_metadata_only",
            "learned_overlay_is_prediction_only",
        },
        "acceptance",
    )
    expected_acceptance = {
        "expected_episode_id": 7701,
        "visual_inspection_transitions": 160,
        "require_network_evidence": True,
        "controller_owns_actions": "nominal_mpc",
        "obstacle_motion_is_reproducible": True,
        "motion_seed_is_metadata_only": True,
        "learned_overlay_is_prediction_only": True,
    }
    if acceptance != expected_acceptance:
        raise ValueError("V2 acceptance boundary was weakened")

    normalized_bridge = dict(bridge)
    normalized_bridge["timed_gate_half_extents_cm"] = list(
        _vector(bridge["timed_gate_half_extents_cm"], 3, "gate half extents")
    )
    normalized_network = dict(network)
    normalized_network["reactive_target_world_cm"] = list(target)
    normalized_network["reactive_terminal_velocity_local_cm_per_sec"] = list(terminal)
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    return V2ObstacleDemoManifest(
        blueprint_asset=blueprint,
        service_config_path=service_path,
        planner_config_path=planner_path,
        bridge_settings=MappingProxyType(normalized_bridge),
        network_settings=MappingProxyType(normalized_network),
        geometry=V2DemoGeometry(reset, target, terminal),
        expected_episode_id=7701,
        visual_inspection_transitions=160,
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
    )
