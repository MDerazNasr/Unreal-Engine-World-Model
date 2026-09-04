from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from motionworld.control.live_residual_overlay_config import (
    load_live_residual_overlay_config,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/live_residual_overlay_demo.yaml"


def test_selected_residual_overlay_loads_with_complete_provenance() -> None:
    config = load_live_residual_overlay_config(CONFIG, ROOT)

    assert config.residual_overlay_model is not None
    assert config.residual_overlay_model.input_width == 28
    assert config.residual_overlay_model.parameter_count == 106_886
    assert config.residual_overlay_normalization is not None
    assert config.residual_overlay_normalization.history_length == 1
    assert config.residual_overlay_normalization.train_episode_ids == (5101, 5102, 5103, 5104, 5105)
    assert config.residual_overlay_rollout is not None
    assert config.residual_overlay_rollout.dynamics_substeps_per_plan_step == 3


def test_residual_overlay_hash_mismatch_fails_before_checkpoint_load(
    tmp_path: Path,
    monkeypatch,
) -> None:
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    raw["checkpoint"]["sha256"] = "0" * 64
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    called = False

    def forbidden(_path: str):
        nonlocal called
        called = True
        raise AssertionError("unverified checkpoint deserialized")

    monkeypatch.setattr(
        "motionworld.control.live_residual_overlay_config.load_residual_checkpoint",
        forbidden,
    )
    with pytest.raises(ValueError, match="checkpoint SHA-256 mismatch"):
        load_live_residual_overlay_config(path, ROOT)
    assert not called


def test_residual_overlay_rejects_path_escape(tmp_path: Path) -> None:
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    raw["checkpoint"]["path"] = "../outside.pt"
    path = tmp_path / "escape.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="must stay inside the repository"):
        load_live_residual_overlay_config(path, ROOT)
