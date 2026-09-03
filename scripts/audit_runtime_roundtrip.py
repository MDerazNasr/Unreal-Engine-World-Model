#!/usr/bin/env python3
"""Preserve an unedited raw Gate-R2 session slice and its strict summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from motionworld.control.roundtrip_evidence import audit_roundtrip_session

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-log", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--expected-episode-id", type=int, required=True)
    parser.add_argument("--minimum-consecutive-intervals", type=int, default=100)
    parser.add_argument("--maximum-p95-latency-ms", type=float, default=100.0)
    args = parser.parse_args()
    if args.minimum_consecutive_intervals < 100:
        raise ValueError("minimum consecutive intervals cannot weaken Gate R2 below 100")
    if not 0.0 < args.maximum_p95_latency_ms <= 100.0:
        raise ValueError("maximum p95 latency must be in (0, 100] ms")

    audit = audit_roundtrip_session(args.source_log.read_bytes(), args.session_id)
    if audit.episode_ids != (args.expected_episode_id,):
        raise ValueError("source episode does not match the declared identity")
    if len(audit.action_sequences) < args.minimum_consecutive_intervals:
        raise ValueError("too few consecutive accepted control intervals")
    if audit.p95_latency_ms >= args.maximum_p95_latency_ms:
        raise ValueError("p95 latency is not comfortably below the deadline")

    raw_output = REPOSITORY_ROOT / "evidence/unreal/runtime_roundtrip_001.log"
    summary_output = REPOSITORY_ROOT / "artifacts/runtime/roundtrip_001/summary.json"
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text("".join(audit.raw_lines), encoding="utf-8", newline="")
    summary = {
        "schema_name": "motionworld_runtime_roundtrip_summary",
        "schema_version": 1,
        "session_id": audit.session_id,
        "episode_id": audit.episode_ids[0],
        "source_log": {
            "sha256": audit.source_sha256,
            "first_line_number": audit.first_line_number,
            "last_line_number": audit.last_line_number,
            "extraction": "inclusive byte-preserving decoded UTF-8 line range",
        },
        "identity_reconciliation": {
            "observations": len(audit.observation_sequences),
            "accepted_actions": len(audit.action_sequences),
            "first_sequence": audit.action_sequences[0],
            "last_sequence": audit.action_sequences[-1],
            "observation_gaps": 0,
            "action_gaps": 0,
            "unexplained_gaps": 0,
        },
        "unreal_end_to_end_latency_ms": {
            "minimum": min(audit.latencies_ms),
            "p95": audit.p95_latency_ms,
            "maximum": max(audit.latencies_ms),
            "exclusive_deadline_ms": 100.0,
        },
        "final_stats": audit.final_stats,
        "gate_r2": {
            "minimum_consecutive_intervals": args.minimum_consecutive_intervals,
            "consecutive_interval_pass": True,
            "identity_reconciliation_pass": True,
            "latency_pass": True,
            "claim_boundary": "echo round trip only; reset/failure/video evidence is separate",
            "final_prediction_episodes_opened": 0,
        },
    }
    summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
