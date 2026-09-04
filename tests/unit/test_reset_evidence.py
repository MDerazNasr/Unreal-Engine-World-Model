from __future__ import annotations

import hashlib

import pytest

from motionworld.control.reset_evidence import audit_multi_reset_session

SESSION = "ABCDEF123456"
EPISODES = (7310, 7311, 7312)


def _raw(*, episodes: tuple[int, ...] = EPISODES, dropped: int = 0) -> bytes:
    lines = [f"prefix network evidence started: session={SESSION} controller=echo\n"]
    for index, episode in enumerate(episodes):
        old_episode = -1 if index == 0 else episodes[index - 1]
        lines.extend(
            [
                f"prefix network reset boundary: session={SESSION} "
                f"old_episode={old_episode} outstanding_observation=2 "
                "action_state_cleared=true.\n",
                f"prefix network episode started: session={SESSION} episode={episode} "
                "first_observation_sequence=0 applied_local_cm_per_sec=(0, 0) "
                "prior_state_cleared=true.\n",
                f"prefix reset verified: episode={episode} attempts=1 state_sequence=60 "
                "position_error_cm=0.000 facing_error_deg=0.000 "
                "linear_speed_cm_per_sec=0.000 angular_speed_deg_per_sec=0.000; ok\n",
                f"prefix network observation sent: session={SESSION} episode={episode} "
                "observation=0 state_sequence=60 previous_action_present=false "
                "previous_action_source=-1.\n",
                f"prefix network action accepted: session={SESSION} episode={episode} "
                "source_observation=0 desired=(100, 0) current_identity_match=true "
                "before_deadline=true.\n",
            ]
        )
    lines.append(
        f"prefix network evidence stopped: session={SESSION} observations_sent=20 "
        "actions_accepted=10 rejected=3 stale=2 malformed=1 missed=2 held=2 "
        f"safe_stops=0 evidence_written=30 evidence_dropped={dropped}.\n"
    )
    return "".join(lines).encode()


def test_audit_proves_three_reset_boundaries_and_preserves_range() -> None:
    source = b"before\n" + _raw() + b"after\n"
    audit = audit_multi_reset_session(source, SESSION, EPISODES)

    assert tuple(item.episode_id for item in audit.episodes) == EPISODES
    assert tuple(item.old_episode_id for item in audit.episodes) == (-1, 7310, 7311)
    assert audit.final_stats["stale"] == 2
    assert audit.first_line_number == 2
    assert audit.preserved_range == _raw()
    assert audit.preserved_range_sha256 == hashlib.sha256(_raw()).hexdigest()


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("network episode started", "network reset boundary"),
        ("reset verified", "network episode started"),
        ("network observation sent", "reset verified"),
        ("network action accepted", "network observation sent"),
    ],
)
def test_audit_rejects_reordered_lifecycle_events(first: str, second: str) -> None:
    lines = _raw().decode().splitlines(keepends=True)
    first_index = next(index for index, line in enumerate(lines) if first in line)
    second_index = next(index for index, line in enumerate(lines) if second in line)
    lines[first_index], lines[second_index] = lines[second_index], lines[first_index]

    with pytest.raises(ValueError, match="required order"):
        audit_multi_reset_session("".join(lines).encode(), SESSION, EPISODES)


@pytest.mark.parametrize(
    ("raw", "expected", "message"),
    [
        (_raw(episodes=(7310, 7312)), EPISODES, "declared ordered"),
        (
            _raw().replace(
                b"prior_state_cleared=true", b"prior_state_cleared=false", 1
            ),
            EPISODES,
            "declared ordered",
        ),
        (
            _raw().replace(
                b"previous_action_present=false", b"previous_action_present=true", 1
            ),
            EPISODES,
            "observation zero",
        ),
        (
            _raw().replace(
                b"current_identity_match=true", b"current_identity_match=false", 1
            ),
            EPISODES,
            "action zero",
        ),
        (
            _raw().replace(b"position_error_cm=0.000", b"position_error_cm=0.125", 1),
            EPISODES,
            "not exact and stationary",
        ),
        (_raw(dropped=1), EPISODES, "dropped evidence"),
    ],
)
def test_audit_rejects_missing_or_unsafe_lifecycle_proof(
    raw: bytes, expected: tuple[int, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        audit_multi_reset_session(raw, SESSION, expected)


def test_audit_rejects_noncanonical_session_identity() -> None:
    with pytest.raises(ValueError, match="12 uppercase hex"):
        audit_multi_reset_session(_raw(), "abcdef123456", EPISODES)
