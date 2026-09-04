#!/usr/bin/env python3
"""Audit the clean D6 matched learned-model overlay run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from motionworld.control.d6_residual_overlay_manifest import (
    load_d6_residual_overlay_manifest,
)
from motionworld.control.live_residual_overlay_config import (
    load_live_residual_overlay_config,
)
from motionworld.control.nominal_mpc_evidence import audit_d6_residual_overlay_live

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-log",
        type=Path,
        default=ROOT / "evidence/unreal/d6_residual_overlay_live.log",
    )
    parser.add_argument("--session-id", default="DD64FEF0C742")
    parser.add_argument("--episode-id", type=int, default=7603)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/demo/d6_residual_overlay_live/summary.json",
    )
    args = parser.parse_args()

    manifest_path = ROOT / "configs/d6_residual_overlay_manifest.json"
    overlay_path = ROOT / "configs/live_residual_overlay_demo.yaml"
    manifest = load_d6_residual_overlay_manifest(manifest_path, ROOT)
    overlay = load_live_residual_overlay_config(overlay_path, ROOT)
    if args.episode_id != manifest.expected_episode_id:
        raise ValueError("requested episode does not match the verified D6 manifest")
    audit = audit_d6_residual_overlay_live(
        args.source_log.read_bytes(), args.session_id, args.episode_id
    )
    checkpoint_path = ROOT / "artifacts/residual/training_001/no_history/checkpoint.pt"
    latencies = audit.latency_summary()
    summary = {
        "schema_name": "motionworld_d6_residual_overlay_live_summary",
        "schema_version": 1,
        "source_log": {
            "path": str(args.source_log),
            "sha256": audit.source_sha256,
            "first_audited_line": audit.first_line_number,
            "last_audited_line": audit.last_line_number,
        },
        "identity": {"session_id": audit.session_id, "episode_id": audit.episode_id},
        "configuration": {
            "manifest_sha256": manifest.canonical_sha256,
            "overlay_config_sha256": _sha256(overlay_path),
            "checkpoint_sha256": _sha256(checkpoint_path),
            "overlay_steps": overlay.residual_overlay_steps,
            "overlay_horizon_s": (
                overlay.residual_overlay_steps
                * overlay.residual_overlay_rollout.plan_step_s
            ),
            "nominal_mpc_is_only_action_owner": True,
        },
        "live_runtime": {
            "observations_logged": len(audit.observation_sequences),
            "accepted_actions_logged": len(audit.accepted_sequences),
            "accepted_identities_unique_strictly_increasing": True,
            "accepted_actions_current_and_before_100_ms_deadline": True,
            "missing_action_sequences": list(audit.missing_action_sequences),
            "matching_command_echoes": audit.matched_action_echo_count,
            "unmatched_final_action_at_shutdown": audit.unmatched_final_action_count,
            "latency_ms": latencies,
            "maximum_planar_displacement_from_reset_cm": (
                audit.maximum_planar_displacement_cm
            ),
        },
        "claim_boundary": {
            "comparison": (
                "matched nominal and selected learned-residual forecasts from the same "
                "authoritative state and nominal-selected action sequence"
            ),
            "residual_controls_character": False,
            "residual_is_better": False,
            "pixels_proved_by_text_log": False,
            "human_visual_confirmation_required": True,
            "final_prediction_episodes_opened": 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
