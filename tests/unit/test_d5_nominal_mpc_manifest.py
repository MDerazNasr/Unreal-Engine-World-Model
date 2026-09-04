from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionworld.control.d5_nominal_mpc_manifest import load_d5_nominal_mpc_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "configs" / "d5_nominal_mpc_manifest.json"


def test_frozen_d5_manifest_is_self_consistent() -> None:
    manifest = load_d5_nominal_mpc_manifest(MANIFEST_PATH, REPOSITORY_ROOT)

    assert manifest.blueprint_asset == "/Game/Blueprints/SandboxCharacter_Mover"
    assert manifest.service_config_path == (
        REPOSITORY_ROOT / "configs" / "control_service_demo_nominal_mpc.yaml"
    )
    assert manifest.planner_config_path == (
        REPOSITORY_ROOT / "configs" / "live_nominal_mpc_demo.yaml"
    )
    assert manifest.expected_episode_id == 7504
    assert manifest.visual_inspection_transitions == 120
    assert manifest.geometry.reset_anchor_world_cm == (-800.0, 0.0, 90.0)
    assert manifest.geometry.reactive_target_world_cm == (800.0, 0.0, 90.0)
    assert manifest.geometry.terminal_velocity_local_cm_per_sec == (0.0, 0.0)
    assert manifest.bridge_settings["max_planar_speed_cm_per_sec"] == 165.0
    assert manifest.network_settings["controller_mode"] == "nominal_mpc"
    assert manifest.network_settings["has_reactive_target"]
    assert manifest.network_settings["draw_world_model_visualization"]
    assert manifest.network_settings["log_network_evidence"]
    assert len(manifest.canonical_sha256) == 64


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("bridge_settings", "begin_play_reset_episode_id"), 7503, "id 7504"),
        (
            ("bridge_settings", "max_planar_speed_cm_per_sec"),
            600.0,
            "exactly 165",
        ),
        (("bridge_settings", "reset_live_test_repeat_count"), 2, "exactly one"),
        (("bridge_settings", "reset_live_test_transitions_per_episode"), 60, "120"),
        (("bridge_settings", "enable_timed_gate_scenario"), True, "producers"),
        (("network_settings", "network_control_enabled"), False, "must be enabled"),
        (("network_settings", "controller_mode"), "branch_preview", "nominal_mpc"),
        (("network_settings", "has_reactive_target"), False, "requires the reactive"),
        (("network_settings", "draw_world_model_visualization"), False, "must be enabled"),
        (("network_settings", "log_network_evidence"), False, "must be enabled"),
        (("acceptance", "require_network_evidence"), False, "cannot be disabled"),
    ],
)
def test_manifest_rejects_unsafe_or_weakened_demo(
    tmp_path: Path, path: tuple[str, str], value: object, message: str
) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw[path[0]][path[1]] = value
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_d5_nominal_mpc_manifest(candidate, REPOSITORY_ROOT)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("demo_geometry", "reset_anchor_world_cm"), [-700, 0, 90], "reset anchor"),
        (("demo_geometry", "reactive_target_world_cm"), [0, 0, 90], "clear forward"),
        (("demo_geometry", "terminal_velocity_local_cm_per_sec"), [1, 0], "must be zero"),
        (("network_settings", "reactive_target_world_cm"), [700, 0, 90], "match"),
        (
            ("network_settings", "reactive_terminal_velocity_local_cm_per_sec"),
            [1, 0],
            "match",
        ),
    ],
)
def test_manifest_rejects_geometry_drift(
    tmp_path: Path, path: tuple[str, str], value: object, message: str
) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw[path[0]][path[1]] = value
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_d5_nominal_mpc_manifest(candidate, REPOSITORY_ROOT)


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["network_settings"]["surprise"] = True
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="keys must be exactly"):
        load_d5_nominal_mpc_manifest(candidate, REPOSITORY_ROOT)


@pytest.mark.parametrize(
    "hash_name",
    ["sha256", "planner_sha256", "runtime_config_sha256", "transport_config_sha256"],
)
def test_manifest_rejects_configuration_drift(tmp_path: Path, hash_name: str) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["service"][hash_name] = "0" * 64
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="frozen SHA-256 mismatch"):
        load_d5_nominal_mpc_manifest(candidate, REPOSITORY_ROOT)
