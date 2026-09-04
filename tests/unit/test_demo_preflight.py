from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from motionworld.demo_preflight import run_preflight


def _write(root: Path, relative: str, content: bytes = b"evidence") -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _fixture(root: Path) -> tuple[Path, Path]:
    for relative in (
        "artifacts/interview/architecture.svg",
        "artifacts/residual/recursive_001/recursive_comparison.png",
        "artifacts/planning/offplan_001/offline_paired_planner.png",
        "artifacts/planning/runtime_001/README.md",
    ):
        _write(root, relative)
    summary = {
        "schema_name": "motionworld_d5_nominal_mpc_live_summary",
        "identity_reconciliation": {"accepted_actions_logged": 387},
        "deadline": {
            "all_accepted_actions_logged_current_identity_and_before_deadline": True
        },
        "authoritative_motion": {"pawn_displacement_observed": True},
        "claim_boundary": {"final_prediction_episodes_opened": 0},
    }
    _write(
        root,
        "artifacts/demo/d5_nominal_mpc_live/summary.json",
        (json.dumps(summary) + "\n").encode(),
    )

    references = {}
    for name, relative in (
        ("nominal_planner", "configs/live_nominal_mpc_demo.yaml"),
        ("checkpoint", "artifacts/residual/training_001/no_history/checkpoint.pt"),
        ("normalization", "artifacts/residual/training_001/no_history/normalization.json"),
        ("training_config", "configs/residual_training.yaml"),
        ("dataset_manifest", "artifacts/residual/dataset_audit/manifest.json"),
    ):
        references[name] = {"path": relative, "sha256": _write(root, relative)}
    overlay = {
        "status": "matched_prediction_overlay_nominal_control_only",
        **references,
    }
    overlay_bytes = yaml.safe_dump(overlay).encode()
    overlay_hash = _write(root, "configs/live_residual_overlay_demo.yaml", overlay_bytes)
    service_hash = _write(root, "configs/control_service_demo_nominal_mpc.yaml")
    manifest = {
        "schema_name": "motionworld_d6_residual_overlay_manifest",
        "service": {
            "config_path": "configs/control_service_demo_nominal_mpc.yaml",
            "sha256": service_hash,
            "planner_config_path": "configs/live_residual_overlay_demo.yaml",
            "planner_sha256": overlay_hash,
        },
        "network_settings": {"controller_mode": "nominal_mpc"},
        "acceptance": {"overlay_is_prediction_only": True, "expected_episode_id": 7603},
    }
    _write(root, "configs/d6_residual_overlay_manifest.json", json.dumps(manifest).encode())
    d6_summary = {
        "schema_name": "motionworld_d6_residual_overlay_live_summary",
        "identity": {"episode_id": 7603},
        "configuration": {
            "checkpoint_sha256": references["checkpoint"]["sha256"],
            "overlay_config_sha256": overlay_hash,
            "nominal_mpc_is_only_action_owner": True,
        },
        "live_runtime": {
            "accepted_actions_logged": 254,
            "accepted_actions_current_and_before_100_ms_deadline": True,
        },
        "claim_boundary": {
            "residual_controls_character": False,
            "final_prediction_episodes_opened": 0,
        },
    }
    _write(
        root,
        "artifacts/demo/d6_residual_overlay_live/summary.json",
        (json.dumps(d6_summary) + "\n").encode(),
    )
    editor = root / "UnrealEditor-Cmd"
    project = root / "GameAnimationSample.uproject"
    editor.write_bytes(b"editor")
    project.write_bytes(b"project")
    return editor, project


def test_preflight_passes_complete_launch_and_preserves_claim_boundary(tmp_path: Path) -> None:
    editor, project = _fixture(tmp_path)

    report = run_preflight(
        tmp_path,
        unreal_editor=editor,
        unreal_project=project,
        require_unreal=True,
    )

    assert all(check.status == "pass" for check in report.checks)
    assert report.live_launch_ready
    assert report.fallback_ready
    assert "does not prove" in report.claim_boundary


def test_preflight_keeps_offline_fallback_when_unreal_is_absent(tmp_path: Path) -> None:
    _fixture(tmp_path)

    report = run_preflight(tmp_path)

    assert not report.live_launch_ready
    assert report.fallback_ready
    assert [check.status for check in report.checks[-2:]] == ["warn", "warn"]


def test_preflight_fails_closed_on_checkpoint_hash_drift(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "artifacts/residual/training_001/no_history/checkpoint.pt").write_bytes(
        b"changed"
    )

    report = run_preflight(tmp_path)

    check = next(check for check in report.checks if check.name == "learned_overlay_configuration")
    assert check.status == "fail"
    assert "checkpoint hash mismatch" in check.detail
    assert not report.live_launch_ready


def test_require_unreal_converts_missing_paths_to_failure(tmp_path: Path) -> None:
    _fixture(tmp_path)

    report = run_preflight(tmp_path, require_unreal=True)

    assert report.checks[-1].name == "required_live_environment"
    assert report.checks[-1].status == "fail"
