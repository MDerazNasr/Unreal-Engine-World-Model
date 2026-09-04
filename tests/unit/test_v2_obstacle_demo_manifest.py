from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionworld.control.v2_obstacle_demo_manifest import (
    load_v2_obstacle_demo_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "configs/v2_obstacle_demo_manifest.json"


def test_v2_manifest_freezes_collision_aware_demo_contract() -> None:
    manifest = load_v2_obstacle_demo_manifest(MANIFEST, ROOT)

    assert manifest.expected_episode_id == 7701
    assert manifest.geometry.reset_anchor_world_cm == (-800.0, 0.0, 90.0)
    assert manifest.geometry.reactive_target_world_cm == (800.0, 0.0, 90.0)
    assert manifest.planner_config_path.name == "live_moving_obstacle_demo.yaml"
    assert manifest.bridge_settings["enable_timed_gate_scenario"] is True
    assert manifest.bridge_settings[
        "timed_gate_continue_after_success_plane_crossing"
    ] is True
    assert manifest.bridge_settings["timed_gate_forward_distance_cm"] == 350.0
    assert manifest.bridge_settings["timed_gate_half_extents_cm"] == [35.0, 55.0, 90.0]
    assert manifest.network_settings["controller_mode"] == "nominal_mpc"
    assert manifest.network_settings["draw_world_model_visualization"] is True


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("bridge_settings", "begin_play_reset_episode_id", 7603, "boundary"),
        ("bridge_settings", "enable_timed_gate_scenario", False, "boundary"),
        (
            "bridge_settings",
            "timed_gate_continue_after_success_plane_crossing",
            False,
            "boundary",
        ),
        ("bridge_settings", "timed_gate_forward_distance_cm", 600.0, "boundary"),
        ("network_settings", "controller_mode", "reactive", "nominal MPC"),
        ("acceptance", "obstacle_motion_is_reproducible", False, "weakened"),
    ],
)
def test_v2_manifest_rejects_demo_boundary_drift(
    tmp_path: Path,
    section: str,
    key: str,
    value: object,
    message: str,
) -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw[section][key] = value
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_v2_obstacle_demo_manifest(candidate, ROOT)


def test_v2_manifest_rejects_planner_configuration_drift(tmp_path: Path) -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw["service"]["planner_sha256"] = "0" * 64
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="frozen hash mismatch"):
        load_v2_obstacle_demo_manifest(candidate, ROOT)
