"""Strict extraction and reconciliation of one raw Unreal network-evidence session."""

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
_EPISODE = re.compile(
    r"network episode started: session=(?P<session>[A-F0-9]+) episode=(?P<episode>\d+)"
)
_OBSERVATION = re.compile(
    r"network observation sent: session=(?P<session>[A-F0-9]+) "
    r"episode=(?P<episode>\d+) observation=(?P<sequence>\d+)"
)
_ACTION = re.compile(
    r"network action accepted: session=(?P<session>[A-F0-9]+) "
    r"episode=(?P<episode>\d+) source_observation=(?P<sequence>\d+).*"
    r"unreal_end_to_end_latency_ms=(?P<latency>[0-9.]+) "
    r"current_identity_match=true before_deadline=true"
)


@dataclass(frozen=True, slots=True)
class RoundtripAudit:
    session_id: str
    source_sha256: str
    first_line_number: int
    last_line_number: int
    raw_lines: tuple[str, ...]
    episode_ids: tuple[int, ...]
    observation_sequences: tuple[int, ...]
    action_sequences: tuple[int, ...]
    latencies_ms: tuple[float, ...]
    final_stats: dict[str, int]

    @property
    def p95_latency_ms(self) -> float:
        values = sorted(self.latencies_ms)
        index = (len(values) - 1) * 0.95
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        fraction = index - lower
        return values[lower] + fraction * (values[upper] - values[lower])


def _contiguous(values: list[int], context: str) -> None:
    if values != list(range(len(values))):
        raise ValueError(f"{context} must be contiguous from zero")


def audit_roundtrip_session(raw: bytes, session_id: str) -> RoundtripAudit:
    """Extract an unedited session range and reject incomplete or inconsistent identity."""

    if not re.fullmatch(r"[A-F0-9]{12}", session_id):
        raise ValueError("session_id must contain exactly 12 uppercase hex characters")
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    starts = [
        index
        for index, line in enumerate(lines)
        if _START.search(line) and session_id in line
    ]
    stops = [
        index
        for index, line in enumerate(lines)
        if _STOP.search(line) and session_id in line
    ]
    if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
        raise ValueError("session must have exactly one ordered evidence start and stop")
    first, last = starts[0], stops[0]
    session_lines = lines[first : last + 1]
    episodes: list[int] = []
    observations: list[int] = []
    actions: list[int] = []
    latencies: list[float] = []
    stop_match = None
    for line in session_lines:
        if (match := _EPISODE.search(line)) and match["session"] == session_id:
            episodes.append(int(match["episode"]))
        if (match := _OBSERVATION.search(line)) and match["session"] == session_id:
            observations.append(int(match["sequence"]))
        if (match := _ACTION.search(line)) and match["session"] == session_id:
            actions.append(int(match["sequence"]))
            latencies.append(float(match["latency"]))
        if (match := _STOP.search(line)) and match["session"] == session_id:
            stop_match = match
    if len(episodes) != 1:
        raise ValueError("round-trip source session must contain exactly one episode")
    _contiguous(observations, "observation sequences")
    _contiguous(actions, "accepted action sequences")
    if observations != actions or not latencies:
        raise ValueError("every observation must have one matching accepted action")
    if stop_match is None:
        raise ValueError("missing final session statistics")
    stats = {name: int(stop_match[name]) for name in (
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
    )}
    if stats["observations"] != len(observations) or stats["accepted"] != len(actions):
        raise ValueError("final counters disagree with parsed observation/action lines")
    if any(stats[name] != 0 for name in (
        "rejected",
        "stale",
        "malformed",
        "missed",
        "held",
        "safe_stops",
        "dropped",
    )):
        raise ValueError("round-trip source session contains a control failure or evidence drop")
    return RoundtripAudit(
        session_id=session_id,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        first_line_number=first + 1,
        last_line_number=last + 1,
        raw_lines=tuple(session_lines),
        episode_ids=tuple(episodes),
        observation_sequences=tuple(observations),
        action_sequences=tuple(actions),
        latencies_ms=tuple(latencies),
        final_stats=stats,
    )
