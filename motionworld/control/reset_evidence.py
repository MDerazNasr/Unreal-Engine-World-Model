"""Strict lifecycle-boundary audit for a multi-reset Unreal evidence session."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_START = re.compile(r"network evidence started: session=(?P<session>[A-F0-9]+)")
_STOP = re.compile(
    r"network evidence stopped: session=(?P<session>[A-F0-9]+) "
    r"observations_sent=(?P<observations>\d+) actions_accepted=(?P<accepted>\d+) "
    r"rejected=(?P<rejected>\d+) stale=(?P<stale>\d+) malformed=(?P<malformed>\d+) "
    r"missed=(?P<missed>\d+) held=(?P<held>\d+) safe_stops=(?P<safe_stops>\d+) "
    r"evidence_written=(?P<written>\d+) evidence_dropped=(?P<dropped>\d+)"
)
_BOUNDARY = re.compile(
    r"network reset boundary: session=(?P<session>[A-F0-9]+) "
    r"old_episode=(?P<old_episode>-?\d+).*action_state_cleared=true"
)
_EPISODE = re.compile(
    r"network episode started: session=(?P<session>[A-F0-9]+) "
    r"episode=(?P<episode>\d+) first_observation_sequence=0 .*"
    r"prior_state_cleared=true"
)
_RESET = re.compile(
    r"reset verified: episode=(?P<episode>\d+) attempts=(?P<attempts>\d+).*"
    r"position_error_cm=(?P<position_error>[0-9.]+) "
    r"facing_error_deg=(?P<facing_error>[0-9.]+) "
    r"linear_speed_cm_per_sec=(?P<linear_speed>[0-9.]+) "
    r"angular_speed_deg_per_sec=(?P<angular_speed>[0-9.]+)"
)
_OBSERVATION_ZERO = re.compile(
    r"network observation sent: session=(?P<session>[A-F0-9]+) "
    r"episode=(?P<episode>\d+) observation=0 .*"
    r"previous_action_present=false previous_action_source=-1"
)
_ACTION_ZERO = re.compile(
    r"network action accepted: session=(?P<session>[A-F0-9]+) "
    r"episode=(?P<episode>\d+) source_observation=0 .*"
    r"current_identity_match=true before_deadline=true"
)

@dataclass(frozen=True, slots=True)
class ResetEpisodeAudit:
    episode_id: int
    old_episode_id: int
    reset_attempts: int


@dataclass(frozen=True, slots=True)
class MultiResetAudit:
    session_id: str
    source_sha256: str
    preserved_range_sha256: str
    first_line_number: int
    last_line_number: int
    preserved_range: bytes
    raw_lines: tuple[str, ...]
    episodes: tuple[ResetEpisodeAudit, ...]
    final_stats: dict[str, int]


def _exactly_once[T](matches: list[T], context: str) -> T:
    if len(matches) != 1:
        raise ValueError(f"{context} must occur exactly once")
    return matches[0]


def audit_multi_reset_session(
    raw: bytes, session_id: str, expected_episode_ids: tuple[int, ...]
) -> MultiResetAudit:
    """Prove that each declared episode begins from cleared authoritative state.

    This audit intentionally permits stale, malformed, missed, held, and rejected
    traffic.  Its claim is reset isolation, not clean round-trip performance.
    """

    if not re.fullmatch(r"[A-F0-9]{12}", session_id):
        raise ValueError("session_id must contain exactly 12 uppercase hex characters")
    if not expected_episode_ids or len(set(expected_episode_ids)) != len(
        expected_episode_ids
    ):
        raise ValueError("expected episode IDs must be a non-empty unique sequence")

    byte_lines = raw.splitlines(keepends=True)
    lines = [line.decode("utf-8") for line in byte_lines]
    starts = [
        index
        for index, line in enumerate(lines)
        if (match := _START.search(line)) and match["session"] == session_id
    ]
    stops = [
        index
        for index, line in enumerate(lines)
        if (match := _STOP.search(line)) and match["session"] == session_id
    ]
    if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
        raise ValueError("session must have exactly one ordered evidence start and stop")

    first, last = starts[0], stops[0]
    session_lines = lines[first : last + 1]
    preserved_range = b"".join(byte_lines[first : last + 1])
    episode_matches = [
        match
        for line in session_lines
        if (match := _EPISODE.search(line)) and match["session"] == session_id
    ]
    actual_episode_ids = tuple(int(match["episode"]) for match in episode_matches)
    if actual_episode_ids != expected_episode_ids:
        raise ValueError(
            "session episodes do not exactly match the declared ordered episode IDs"
        )

    boundaries = [
        (index, match)
        for index, line in enumerate(session_lines)
        if (match := _BOUNDARY.search(line)) and match["session"] == session_id
    ]
    if len(boundaries) != len(expected_episode_ids):
        raise ValueError("each episode must have exactly one cleared reset boundary")
    expected_old_ids = (-1, *expected_episode_ids[:-1])
    actual_old_ids = tuple(int(match["old_episode"]) for _, match in boundaries)
    if actual_old_ids != expected_old_ids:
        raise ValueError("reset boundaries do not follow the expected episode sequence")

    audits: list[ResetEpisodeAudit] = []
    for episode_index, (episode_id, old_episode_id) in enumerate(
        zip(expected_episode_ids, actual_old_ids, strict=True)
    ):
        boundary_index = boundaries[episode_index][0]
        next_boundary_index = (
            boundaries[episode_index + 1][0]
            if episode_index + 1 < len(boundaries)
            else len(session_lines) - 1
        )
        episode_start_index, _ = _exactly_once(
            [
                (index, match)
                for index, line in enumerate(session_lines)
                if (match := _EPISODE.search(line))
                and match["session"] == session_id
                and int(match["episode"]) == episode_id
            ],
            f"episode start for episode {episode_id}",
        )
        reset_index, reset = _exactly_once(
            [
                (index, match)
                for index, line in enumerate(session_lines)
                if (match := _RESET.search(line))
                and int(match["episode"]) == episode_id
            ],
            f"verified reset for episode {episode_id}",
        )
        if int(reset["attempts"]) < 1 or any(
            float(reset[name]) != 0.0
            for name in ("position_error", "facing_error", "linear_speed", "angular_speed")
        ):
            raise ValueError(f"episode {episode_id} reset was not exact and stationary")
        observation_index, _ = _exactly_once(
            [
                (index, match)
                for index, line in enumerate(session_lines)
                if (match := _OBSERVATION_ZERO.search(line))
                and match["session"] == session_id
                and int(match["episode"]) == episode_id
            ],
            f"cleared observation zero for episode {episode_id}",
        )
        action_index, _ = _exactly_once(
            [
                (index, match)
                for index, line in enumerate(session_lines)
                if (match := _ACTION_ZERO.search(line))
                and match["session"] == session_id
                and int(match["episode"]) == episode_id
            ],
            f"accepted action zero for episode {episode_id}",
        )
        if not (
            boundary_index
            < episode_start_index
            < reset_index
            < observation_index
            < action_index
            < next_boundary_index
        ):
            raise ValueError(
                f"episode {episode_id} lifecycle events are not in required order "
                "before the next reset boundary"
            )
        audits.append(
            ResetEpisodeAudit(
                episode_id=episode_id,
                old_episode_id=old_episode_id,
                reset_attempts=int(reset["attempts"]),
            )
        )

    stop = _STOP.search(session_lines[-1])
    if stop is None or stop["session"] != session_id:
        raise ValueError("final session statistics must be the final preserved line")
    stats = {
        name: int(stop[name])
        for name in (
            "observations",
            "accepted",
            "rejected",
            "stale",
            "malformed",
            "missed",
            "held",
            "safe_stops",
            "written",
            "dropped",
        )
    }
    if stats["safe_stops"] != 0 or stats["dropped"] != 0:
        raise ValueError("session contains a safe stop or dropped evidence")

    return MultiResetAudit(
        session_id=session_id,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        preserved_range_sha256=hashlib.sha256(preserved_range).hexdigest(),
        first_line_number=first + 1,
        last_line_number=last + 1,
        preserved_range=preserved_range,
        raw_lines=tuple(session_lines),
        episodes=tuple(audits),
        final_stats=stats,
    )
