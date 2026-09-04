from __future__ import annotations

import json
from pathlib import Path

import pytest

from motionworld.control.d6_residual_overlay_manifest import (
    load_d6_residual_overlay_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "configs/d6_residual_overlay_manifest.json"


def test_d6_manifest_freezes_nominal_control_and_fresh_episode() -> None:
    manifest = load_d6_residual_overlay_manifest(MANIFEST, ROOT)

    assert manifest.expected_episode_id == 7603
    assert manifest.network_settings["controller_mode"] == "nominal_mpc"
    assert manifest.bridge_settings["begin_play_reset_episode_id"] == 7603
    assert manifest.network_settings["draw_world_model_visualization"]
    assert manifest.planner_config_path.name == "live_residual_overlay_demo.yaml"


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("bridge_settings", "begin_play_reset_episode_id", 7504, "episode 7603"),
        ("network_settings", "controller_mode", "residual_mpc", "must not claim"),
        ("acceptance", "overlay_is_prediction_only", False, "weakened"),
    ],
)
def test_d6_manifest_rejects_weakened_boundary(
    tmp_path: Path,
    section: str,
    key: str,
    value: object,
    message: str,
) -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw[section][key] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_d6_residual_overlay_manifest(path, ROOT)
