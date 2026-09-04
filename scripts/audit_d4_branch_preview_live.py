#!/usr/bin/env python3
"""Audit preserved D4 live evidence and write its bounded summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from motionworld.control.branch_preview_evidence import audit_branch_preview_live

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-log", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--episode-id", type=int, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/demo/d4_branch_preview_live/summary.json",
    )
    args = parser.parse_args()
    audit = audit_branch_preview_live(
        args.source_log.read_bytes(), args.session_id, args.episode_id
    )
    summary = {
        "schema_name": "motionworld_d4_branch_preview_live_summary",
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
            "ordering_note": (
                "stationary authoritative reset state precedes BeginNetworkEpisode; the "
                "reset-verified confirmation is emitted immediately after that call"
            ),
        },
        "identity_reconciliation": {
            "observations_logged": len(audit.observation_sequences),
            "accepted_actions_logged": len(audit.accepted_sequences),
            "first_contiguous_accepted_sequence": 0,
            "last_contiguous_accepted_sequence": audit.contiguous_prefix_count - 1,
            "contiguous_prefix_count": audit.contiguous_prefix_count,
            "later_missing_action_sequences": list(audit.accepted_gaps),
            "accepted_identities_unique_strictly_increasing": True,
        },
        "zero_hold": {
            "all_accepted_desired_commands_exactly_zero": True,
            "zero_matching_command_echoes": audit.echo_count,
            "logged_authoritative_state_samples_stationary": audit.state_sample_count,
        },
        "unreal_end_to_end_latency_ms": audit.latency_summary(),
        "claim_boundary": {
            "live_telemetry_presence": (
                "established separately by controller/protocol tests; this old Unreal log "
                "does not serialize visualization fields"
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
