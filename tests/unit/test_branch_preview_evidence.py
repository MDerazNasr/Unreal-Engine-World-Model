from __future__ import annotations

import pytest

from motionworld.control.branch_preview_evidence import audit_branch_preview_live

SESSION = "ABCDEF123456"


def _raw(*, desired="0.000000, 0.000000", second_action=True) -> bytes:
    lines = [
        "evidence started: network evidence started: "
        f"session={SESSION} controller=branch_preview\n",
        f"network reset boundary: session={SESSION} old_episode=-1 "
        "outstanding_observation=-1 action_state_cleared=true\n",
        "state sample: protocol=1 sequence=10 valid=true x resim=false mode=Walking "
        "position_world_cm=(1.00, 2.00, 3.00) velocity_world_cm_per_sec=(0.00, 0.00, 0.00) "
        "x angular_velocity_world_deg_per_sec=(0.00, 0.00, 0.00)\n",
        f"network episode started: session={SESSION} episode=7401 first_observation_sequence=0 "
        "applied_local_cm_per_sec=(0.00, 0.00) prior_state_cleared=true\n",
        "reset verified: episode=7401 attempts=1 state_sequence=10 x position_error_cm=0.000 "
        "facing_error_deg=0.000 linear_speed_cm_per_sec=0.000 angular_speed_deg_per_sec=0.000\n",
    ]
    for sequence in range(2):
        lines.append(
            f"network observation sent: session={SESSION} episode=7401 "
            f"observation={sequence} state_sequence={11 + sequence}\n"
        )
        if sequence == 0 or second_action:
            lines.append(
                f"network action accepted: session={SESSION} episode=7401 "
                f"source_observation={sequence} desired_local_cm_per_sec=({desired}) "
                f"unreal_end_to_end_latency_ms={10 + sequence}.0 "
                "current_identity_match=true before_deadline=true\n"
            )
        lines.append(
            f"command echo: revision={sequence + 1} finite=true requested_frame=(0.00, 0.00, 0.00) "
            "submitted_world=(0.00, 0.00, 0.00) echoed_world=(0.00, 0.00, 0.00) match=true\n"
        )
    return "".join(lines).encode()


def test_audit_accepts_identity_bound_zero_hold() -> None:
    audit = audit_branch_preview_live(_raw(), SESSION, 7401)

    assert audit.observation_sequences == (0, 1)
    assert audit.accepted_sequences == (0, 1)
    assert audit.contiguous_prefix_count == 2
    assert audit.echo_count == 2
    assert audit.latency_summary()["p95"] == pytest.approx(10.95)


def test_audit_reports_bounded_contiguous_prefix() -> None:
    audit = audit_branch_preview_live(_raw(second_action=False), SESSION, 7401)

    assert audit.contiguous_prefix_count == 1
    assert audit.accepted_gaps == ()


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (_raw(desired="1.000000, 0.000000"), "desired command"),
        (_raw().replace(b"match=true", b"match=false", 1), "accepted-action evidence"),
        (_raw() + _raw(), "exactly once"),
    ],
)
def test_audit_rejects_unsafe_or_ambiguous_source(raw: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        audit_branch_preview_live(raw, SESSION, 7401)
