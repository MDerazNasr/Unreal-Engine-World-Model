from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionworld.control.v3_two_obstacle_demo_manifest import (
    load_v3_two_obstacle_demo_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "configs/v3_two_obstacle_demo_manifest.json"


def test_v3_manifest_freezes_two_obstacle_contract() -> None:
    manifest = load_v3_two_obstacle_demo_manifest(MANIFEST, ROOT)
    assert manifest.expected_episode_id == 7801
    assert manifest.planner_config_path.name == "live_two_obstacle_demo.yaml"
    assert manifest.bridge_settings["enable_second_timed_gate_obstacle"] is True
    assert manifest.bridge_settings["second_timed_gate_forward_distance_cm"] == 1050.0
    assert manifest.bridge_settings["second_timed_gate_half_extents_cm"] == [35.0, 80.0, 90.0]
    assert manifest.bridge_settings["timed_gate_timeout_seconds"] == 30.0


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("bridge_settings", "begin_play_reset_episode_id", 7701),
        ("bridge_settings", "enable_second_timed_gate_obstacle", False),
        ("bridge_settings", "second_timed_gate_lateral_offset_cm", 0.0),
        ("network_settings", "controller_mode", "reactive"),
        ("acceptance", "obstacle_count", 1),
    ],
)
def test_v3_manifest_rejects_boundary_drift(
    tmp_path: Path, section: str, key: str, value: object
) -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw[section][key] = value
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="weakened"):
        load_v3_two_obstacle_demo_manifest(candidate, ROOT)


def test_v3_manifest_rejects_planner_hash_drift(tmp_path: Path) -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw["service"]["planner_sha256"] = "0" * 64
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen hash mismatch"):
        load_v3_two_obstacle_demo_manifest(candidate, ROOT)
