from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionworld.control.demo_branch_manifest import load_demo_branch_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "configs" / "d4_branch_preview_manifest.json"


def test_frozen_d4_manifest_is_self_consistent() -> None:
    manifest = load_demo_branch_manifest(MANIFEST_PATH, REPOSITORY_ROOT)

    assert manifest.blueprint_asset == "/Game/Blueprints/SandboxCharacter_Mover"
    assert manifest.service_config_path == (
        REPOSITORY_ROOT / "configs" / "control_service_demo_branches.yaml"
    )
    assert manifest.acceptance.expected_episode_id == 7401
    assert manifest.acceptance.visual_inspection_transitions == 120
    assert manifest.acceptance.require_network_evidence
    assert manifest.bridge_settings["request_reset_after_warmup_on_begin_play"]
    assert not manifest.bridge_settings["start_episode_recording_on_begin_play"]
    assert manifest.network_settings["controller_mode"] == "branch_preview"
    assert manifest.network_settings["draw_world_model_visualization"]
    assert not manifest.network_settings["has_reactive_target"]
    assert len(manifest.canonical_sha256) == 64


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("bridge_settings", "begin_play_reset_episode_id"), 5301, "id 7401"),
        (("bridge_settings", "reset_live_test_repeat_count"), 2, "exactly one"),
        (("bridge_settings", "reset_live_test_transitions_per_episode"), 60, "120"),
        (("bridge_settings", "enable_varied_action_schedule"), True, "producers"),
        (("network_settings", "network_control_enabled"), False, "must be enabled"),
        (("network_settings", "controller_mode"), "echo", "branch_preview"),
        (("network_settings", "has_reactive_target"), True, "must not have"),
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
        load_demo_branch_manifest(candidate, REPOSITORY_ROOT)


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["network_settings"]["surprise"] = True
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="keys must be exactly"):
        load_demo_branch_manifest(candidate, REPOSITORY_ROOT)


@pytest.mark.parametrize(
    "hash_name", ["sha256", "runtime_config_sha256", "transport_config_sha256"]
)
def test_manifest_rejects_service_configuration_drift(
    tmp_path: Path, hash_name: str
) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["service"][hash_name] = "0" * 64
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="frozen SHA-256 mismatch"):
        load_demo_branch_manifest(candidate, REPOSITORY_ROOT)
