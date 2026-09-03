from __future__ import annotations

import pytest

from motionworld.control.roundtrip_evidence import audit_roundtrip_session

SESSION = "ABCDEF123456"


def _raw(*, action_sequences=(0, 1, 2), rejected=0) -> bytes:
    lines = [
        f"prefix network evidence started: session={SESSION} controller=echo\n",
        f"prefix network episode started: session={SESSION} episode=7221\n",
    ]
    for sequence in range(3):
        lines.append(
            f"prefix network observation sent: session={SESSION} episode=7221 "
            f"observation={sequence} state_sequence={sequence + 30}\n"
        )
        if sequence in action_sequences:
            lines.append(
                f"prefix network action accepted: session={SESSION} episode=7221 "
                f"source_observation={sequence} desired_local_cm_per_sec=(100, 0) "
                f"unreal_end_to_end_latency_ms={10 + sequence}.0 "
                "current_identity_match=true before_deadline=true\n"
            )
    accepted = len(action_sequences)
    lines.append(
        f"prefix network evidence stopped: session={SESSION} observations_sent=3 "
        f"actions_accepted={accepted} rejected={rejected} stale={rejected} malformed=0 "
        "missed=0 held=0 safe_stops=0 evidence_written=8 evidence_dropped=0.\n"
    )
    return "".join(lines).encode()


def test_audit_preserves_exact_range_and_reconciles_identity() -> None:
    raw = b"outside before\n" + _raw() + b"outside after\n"
    audit = audit_roundtrip_session(raw, SESSION)

    assert audit.episode_ids == (7221,)
    assert audit.observation_sequences == (0, 1, 2)
    assert audit.action_sequences == (0, 1, 2)
    assert audit.p95_latency_ms == pytest.approx(11.9)
    assert audit.first_line_number == 2
    assert audit.last_line_number == 10
    assert "".join(audit.raw_lines).encode() == _raw()


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (_raw(action_sequences=(0, 2)), "contiguous"),
        (_raw(action_sequences=(0, 1), rejected=1), "every observation"),
        (_raw() + _raw(), "exactly one ordered"),
    ],
)
def test_audit_rejects_incomplete_or_ambiguous_sessions(raw: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        audit_roundtrip_session(raw, SESSION)


def test_audit_rejects_noncanonical_session_identity() -> None:
    with pytest.raises(ValueError, match="12 uppercase hex"):
        audit_roundtrip_session(_raw(), "abcdef123456")
