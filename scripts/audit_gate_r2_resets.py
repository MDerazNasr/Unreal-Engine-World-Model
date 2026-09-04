#!/usr/bin/env python3
"""Preserve and summarize a strict Gate-R2 multi-reset lifecycle audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from motionworld.control.reset_evidence import audit_multi_reset_session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-log", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--expected-episode-id", type=int, action="append", required=True)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()

    audit = audit_multi_reset_session(
        args.source_log.read_bytes(), args.session_id, tuple(args.expected_episode_id)
    )
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_bytes(audit.preserved_range)
    summary = {
        "schema_name": "motionworld_gate_r2_reset_summary",
        "schema_version": 1,
        "session_id": audit.session_id,
        "source_log": {
            "sha256": audit.source_sha256,
            "preserved_range_sha256": audit.preserved_range_sha256,
            "first_line_number": audit.first_line_number,
            "last_line_number": audit.last_line_number,
            "extraction": "inclusive byte-preserving line range",
        },
        "episodes": [
            {
                "episode_id": episode.episode_id,
                "old_episode_id": episode.old_episode_id,
                "reset_attempts": episode.reset_attempts,
                "reset_exact_and_stationary": True,
                "prior_state_cleared": True,
                "observation_zero_has_no_previous_action": True,
                "action_zero_identity_and_deadline_valid": True,
            }
            for episode in audit.episodes
        ],
        "final_stats": audit.final_stats,
        "gate_r2_reset_isolation": {
            "pass": True,
            "claim_boundary": (
                "reset lifecycle isolation only; latency and uninterrupted round-trip "
                "quality are established by separate evidence"
            ),
            "permitted_nonzero_counters": [
                "rejected",
                "stale",
                "malformed",
                "missed",
                "held",
            ],
        },
    }
    args.summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
