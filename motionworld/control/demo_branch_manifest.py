"""Strict, frozen configuration contract for the D4 live branch-preview demo."""

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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class DemoBranchAcceptance:
    expected_episode_id: int
    visual_inspection_transitions: int
    require_network_evidence: bool


@dataclass(frozen=True, slots=True)
class DemoBranchManifest:
    blueprint_asset: str
    service_config_path: Path
    bridge_settings: Mapping[str, bool | int | str]
    network_settings: Mapping[str, bool | int | str]
    acceptance: DemoBranchAcceptance
    canonical_sha256: str


def load_demo_branch_manifest(path: Path, repository_root: Path) -> DemoBranchManifest:
    """Load and validate the exact reversible D4 Blueprint configuration."""

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
    if raw["schema_name"] != "motionworld_d4_branch_preview_manifest":
        raise ValueError("unsupported D4 manifest schema name")
    if raw["schema_version"] != 1:
        raise ValueError("unsupported D4 manifest schema version")
    blueprint_asset = raw["blueprint_asset"]
    if blueprint_asset != "/Game/Blueprints/SandboxCharacter_Mover":
        raise ValueError("D4 must target only /Game/Blueprints/SandboxCharacter_Mover")

    service = _mapping(raw["service"], "service")
    _keys(
        service,
        {"config_path", "sha256", "runtime_config_sha256", "transport_config_sha256"},
        "service",
    )
    relative = service["config_path"]
    if relative != "configs/control_service_demo_branches.yaml":
        raise ValueError("D4 must bind configs/control_service_demo_branches.yaml")
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
    bridge_integer_keys = {
        "reset_warmup_finalized_samples",
        "begin_play_reset_episode_id",
        "reset_live_test_repeat_count",
        "reset_live_test_transitions_per_episode",
    }
    if any(type(bridge[name]) is not bool for name in _BRIDGE_KEYS - bridge_integer_keys):
        raise ValueError("bridge boolean settings must be booleans")
    _int(bridge["reset_warmup_finalized_samples"], "reset warmup", 2, 10_000)
    episode_id = _int(bridge["begin_play_reset_episode_id"], "episode id", 0, 2**63 - 1)
    repeats = _int(bridge["reset_live_test_repeat_count"], "reset repeats", 1, 10)
    transitions = _int(
        bridge["reset_live_test_transitions_per_episode"], "episode transitions", 1, 10_000
    )
    if episode_id != 7401 or repeats != 1:
        raise ValueError("D4 requires exactly one nonsealed episode with id 7401")
    if transitions != 120:
        raise ValueError("D4 requires exactly 120 transitions for visual inspection")
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
    if network["controller_mode"] != "branch_preview":
        raise ValueError("D4 requires the branch_preview controller")
    if network["has_reactive_target"]:
        raise ValueError("D4 branch preview must not have a reactive target")
    if not network["draw_world_model_visualization"]:
        raise ValueError("D4 world-model visualization must be enabled")
    if not network["log_network_evidence"]:
        raise ValueError("D4 bounded network evidence must be enabled")
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

    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return DemoBranchManifest(
        blueprint_asset=blueprint_asset,
        service_config_path=service_path,
        bridge_settings=MappingProxyType(dict(bridge)),
        network_settings=MappingProxyType(dict(network)),
        acceptance=DemoBranchAcceptance(
            expected_episode_id=episode_id,
            visual_inspection_transitions=transitions,
            require_network_evidence=True,
        ),
        canonical_sha256=hashlib.sha256(canonical).hexdigest(),
    )
