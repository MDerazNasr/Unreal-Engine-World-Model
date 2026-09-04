#!/usr/bin/env python3
"""Audit preserved D5 nominal-MPC evidence and write its bounded summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from motionworld.control.nominal_mpc_evidence import audit_nominal_mpc_live

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-log",
        type=Path,
        default=ROOT / "evidence/unreal/d5_nominal_mpc_live.log",
    )
    parser.add_argument("--session-id", default="3D16FF3BC647")
    parser.add_argument("--episode-id", type=int, default=7504)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/demo/d5_nominal_mpc_live/summary.json",
    )
    args = parser.parse_args()
    audit = audit_nominal_mpc_live(
        args.source_log.read_bytes(), args.session_id, args.episode_id
    )
    summary = {
        "schema_name": "motionworld_d5_nominal_mpc_live_summary",
        "schema_version": 1,
        "source_log": {
            "path": str(args.source_log),
            "sha256": audit.source_sha256,
            "first_audited_line": audit.first_line_number,
            "last_audited_line": audit.last_line_number,
        },
        "identity": {"session_id": audit.session_id, "episode_id": audit.episode_id},
        "reset_gate": {
            "pass": True,
            "reset_state_sequence": audit.reset_state_sequence,
            "lifecycle_order_verified": True,
        },
        "identity_reconciliation": {
            "observations_logged": len(audit.observation_sequences),
            "accepted_actions_logged": len(audit.accepted_sequences),
            "first_observation_sequence": audit.observation_sequences[0],
            "last_observation_sequence": audit.observation_sequences[-1],
            "accepted_identities_unique_strictly_increasing": True,
            "accepted_actions_have_matching_observations": True,
            "missing_action_sequences": list(audit.missing_action_sequences),
        },
        "bounded_nonzero_control": {
            "all_commands_finite_nonzero_and_within_logged_tolerance_of_165_cm_s": True,
            "logged_magnitude_tolerance_cm_s": 1.0e-6,
            "minimum_command_magnitude_cm_s": min(audit.command_magnitudes_cm_s),
            "maximum_command_magnitude_cm_s": max(audit.command_magnitudes_cm_s),
            "matching_command_echoes": audit.matched_action_echo_count,
            "unmatched_final_action_at_shutdown": audit.unmatched_final_action_count,
        },
        "authoritative_motion": {
            "state_samples_logged": audit.state_sample_count,
            "maximum_planar_displacement_from_reset_cm": audit.maximum_planar_displacement_cm,
            "final_planar_displacement_from_reset_cm": audit.final_planar_displacement_cm,
            "pawn_displacement_observed": True,
        },
        "unreal_end_to_end_latency_ms": audit.latency_summary(),
        "deadline": {
            "deadline_ms": 100.0,
            "all_accepted_actions_logged_current_identity_and_before_deadline": True,
        },
        "claim_boundary": {
            "log_proves_selected_action_was_cem_first_action": False,
            "reason": (
                "controller/unit tests establish selection semantics; the Unreal text log "
                "contains accepted commands but not the complete CEM candidate tensors"
            ),
            "visual_paths_seen": False,
            "visual_confirmation_required_separately": True,
            "final_prediction_episodes_opened": 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
