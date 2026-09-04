"""Strict reversible Blueprint contract for the V3 two-obstacle demo."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

_NETWORK_KEYS = {
    "network_control_enabled", "local_port", "remote_port", "controller_mode",
    "has_reactive_target", "reactive_target_world_cm",
    "reactive_terminal_velocity_local_cm_per_sec", "draw_world_model_visualization",
    "log_network_evidence", "max_network_evidence_lines",
}
_BRIDGE_KEYS = {
    "start_episode_recording_on_begin_play", "request_reset_after_warmup_on_begin_play",
    "reset_warmup_finalized_samples", "begin_play_reset_episode_id",
    "reset_live_test_repeat_count", "reset_live_test_transitions_per_episode",
    "override_reset_anchor_yaw_for_live_test", "enable_timed_gate_scenario",
    "timed_gate_continue_after_success_plane_crossing", "timed_gate_scenario_seed",
    "timed_gate_forward_distance_cm", "timed_gate_amplitude_cm",
    "timed_gate_period_seconds", "timed_gate_phase_offset_radians",
    "timed_gate_half_extents_cm", "timed_gate_timeout_seconds",
    "enable_second_timed_gate_obstacle", "second_timed_gate_forward_distance_cm",
    "second_timed_gate_lateral_offset_cm", "second_timed_gate_amplitude_cm",
    "second_timed_gate_period_seconds", "second_timed_gate_phase_offset_radians",
    "second_timed_gate_half_extents_cm", "enable_varied_action_schedule",
    "enable_external_perturbation_schedule", "max_planar_speed_cm_per_sec",
}


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _vector(value: object, size: int, context: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f"{context} must contain exactly {size} coordinates")
    if any(type(item) not in {int, float} or not math.isfinite(item) for item in value):
        raise ValueError(f"{context} coordinates must be finite numbers")
    return tuple(float(item) for item in value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class V3TwoObstacleDemoManifest:
    blueprint_asset: str
    service_config_path: Path
    planner_config_path: Path
    bridge_settings: Mapping[str, object]
    network_settings: Mapping[str, object]
    expected_episode_id: int
    canonical_sha256: str


def load_v3_two_obstacle_demo_manifest(
    path: Path, repository_root: Path
) -> V3TwoObstacleDemoManifest:
    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "manifest")
    _exact_keys(raw, {
        "schema_name", "schema_version", "blueprint_asset", "service",
        "demo_geometry", "bridge_settings", "network_settings", "acceptance",
    }, "manifest")
    if (
        raw["schema_name"] != "motionworld_v3_two_obstacle_demo_manifest"
        or raw["schema_version"] != 1
    ):
        raise ValueError("unsupported V3 two-obstacle manifest")
    blueprint = "/Game/Blueprints/SandboxCharacter_Mover"
    if raw["blueprint_asset"] != blueprint:
        raise ValueError("V3 may alter only the frozen demo Blueprint")

    service = _mapping(raw["service"], "service")
    _exact_keys(service, {
        "config_path", "sha256", "planner_config_path", "planner_sha256",
        "runtime_config_sha256", "transport_config_sha256",
    }, "service")
    if service["config_path"] != "configs/control_service_demo_nominal_mpc.yaml":
        raise ValueError("V3 must retain the nominal MPC service")
    if service["planner_config_path"] != "configs/live_two_obstacle_demo.yaml":
        raise ValueError("V3 must use the two-obstacle planner config")
    service_path = repository_root / service["config_path"]
    planner_path = repository_root / service["planner_config_path"]
    for source, key in (
        (service_path, "sha256"), (planner_path, "planner_sha256"),
        (repository_root / "configs/control_runtime.yaml", "runtime_config_sha256"),
        (repository_root / "configs/control_transport.yaml", "transport_config_sha256"),
    ):
        if not isinstance(service[key], str) or _sha256(source) != service[key]:
            raise ValueError(f"V3 frozen hash mismatch for {source.relative_to(repository_root)}")

    geometry = _mapping(raw["demo_geometry"], "demo_geometry")
    _exact_keys(geometry, {
        "reset_anchor_world_cm", "reactive_target_world_cm",
        "terminal_velocity_local_cm_per_sec",
    }, "demo_geometry")
    if _vector(geometry["reset_anchor_world_cm"], 3, "reset") != (-800.0, 0.0, 90.0):
        raise ValueError("V3 reset differs from the accepted corridor")
    target = _vector(geometry["reactive_target_world_cm"], 3, "target")
    terminal = _vector(geometry["terminal_velocity_local_cm_per_sec"], 2, "terminal")
    if target != (800.0, 0.0, 90.0) or terminal != (0.0, 0.0):
        raise ValueError("V3 target contract was weakened")

    bridge = _mapping(raw["bridge_settings"], "bridge_settings")
    network = _mapping(raw["network_settings"], "network_settings")
    _exact_keys(bridge, _BRIDGE_KEYS, "bridge_settings")
    _exact_keys(network, _NETWORK_KEYS, "network_settings")
    expected_bridge = {
        "start_episode_recording_on_begin_play": False,
        "request_reset_after_warmup_on_begin_play": True,
        "reset_warmup_finalized_samples": 60,
        "begin_play_reset_episode_id": 7801,
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
        "timed_gate_timeout_seconds": 30.0,
        "enable_second_timed_gate_obstacle": True,
        "second_timed_gate_forward_distance_cm": 1050.0,
        "second_timed_gate_lateral_offset_cm": 80.0,
        "second_timed_gate_amplitude_cm": 45.0,
        "second_timed_gate_period_seconds": 8.0,
        "second_timed_gate_phase_offset_radians": 5.497787143782138,
        "second_timed_gate_half_extents_cm": [35.0, 80.0, 90.0],
        "enable_varied_action_schedule": False,
        "enable_external_perturbation_schedule": False,
        "max_planar_speed_cm_per_sec": 165.0,
    }
    for key, expected_value in expected_bridge.items():
        if type(expected_value) is bool and bridge[key] is not expected_value:
            raise ValueError("V3 bridge/two-obstacle boundary was weakened")
        if type(expected_value) is int and type(bridge[key]) is not int:
            raise ValueError("V3 bridge integer settings must be integers")
    if bridge != expected_bridge:
        raise ValueError("V3 bridge/two-obstacle boundary was weakened")
    expected_network = {
        "network_control_enabled": True, "local_port": 52580, "remote_port": 52581,
        "controller_mode": "nominal_mpc", "has_reactive_target": True,
        "reactive_target_world_cm": [800.0, 0.0, 90.0],
        "reactive_terminal_velocity_local_cm_per_sec": [0.0, 0.0],
        "draw_world_model_visualization": True, "log_network_evidence": True,
        "max_network_evidence_lines": 4096,
    }
    for key in (
        "network_control_enabled", "has_reactive_target",
        "draw_world_model_visualization", "log_network_evidence",
    ):
        if network[key] is not True:
            raise ValueError("V3 network boundary was weakened")
    for key in ("local_port", "remote_port", "max_network_evidence_lines"):
        if type(network[key]) is not int:
            raise ValueError("V3 network integer settings must be integers")
    if network != expected_network:
        raise ValueError("V3 network boundary was weakened")

    acceptance = _mapping(raw["acceptance"], "acceptance")
    expected_acceptance = {
        "expected_episode_id": 7801, "obstacle_count": 2,
        "require_network_evidence": True, "controller_owns_actions": "nominal_mpc",
        "obstacle_motion_is_reproducible": True,
        "learned_overlay_is_prediction_only": True,
    }
    if acceptance != expected_acceptance:
        raise ValueError("V3 acceptance boundary was weakened")

    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    return V3TwoObstacleDemoManifest(
        blueprint_asset=blueprint,
        service_config_path=service_path,
        planner_config_path=planner_path,
        bridge_settings=MappingProxyType(dict(bridge)),
        network_settings=MappingProxyType(dict(network)),
        expected_episode_id=7801,
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
    )
