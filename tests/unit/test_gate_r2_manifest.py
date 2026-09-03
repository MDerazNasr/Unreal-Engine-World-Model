from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionworld.control.gate_r2_manifest import load_gate_r2_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "configs" / "gate_r2_live_manifest.json"


def test_frozen_gate_r2_manifest_is_self_consistent() -> None:
    manifest = load_gate_r2_manifest(MANIFEST_PATH, REPOSITORY_ROOT)

    assert manifest.acceptance.expected_episode_ids == (7310, 7311, 7312)
    assert manifest.acceptance.minimum_consecutive_intervals == 100
    assert manifest.acceptance.maximum_p95_latency_ms == 100.0
    assert manifest.acceptance.required_verified_resets == 3
    assert manifest.acceptance.require_unedited_recording
    assert manifest.bridge_settings["reset_live_test_repeat_count"] == 3
    assert manifest.network_settings["network_control_enabled"]
    assert manifest.network_settings["log_network_evidence"]
    assert manifest.service_config_path == (
        REPOSITORY_ROOT / "configs" / "control_service_echo_forward.yaml"
    )
    assert len(manifest.canonical_sha256) == 64


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("bridge_settings", "reset_live_test_repeat_count"), 2, "three configured resets"),
        (("network_settings", "network_control_enabled"), False, "must be enabled"),
        (("network_settings", "controller_mode"), "residual_mpc", "echo controller"),
        (("acceptance", "minimum_consecutive_intervals"), 99, "minimum intervals"),
        (("acceptance", "require_unedited_recording"), False, "cannot be disabled"),
    ],
)
def test_manifest_rejects_weakened_gate(tmp_path: Path, path, value, message: str) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw[path[0]][path[1]] = value
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_gate_r2_manifest(candidate, REPOSITORY_ROOT)


def test_manifest_rejects_service_configuration_drift(tmp_path: Path) -> None:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["service"]["sha256"] = "0" * 64
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="frozen SHA-256 mismatch"):
        load_gate_r2_manifest(candidate, REPOSITORY_ROOT)
