"""Strict, bounded audit of one preserved Unreal branch-preview session."""

from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass

_START = re.compile(
    r"network evidence started: session=(?P<session>[A-F0-9]{12}) "
    r"controller=(?P<controller>\w+)"
)
_BOUNDARY = re.compile(
    r"network reset boundary: session=(?P<session>[A-F0-9]{12}) "
    r"old_episode=-1 outstanding_observation=-1 action_state_cleared=true"
)
_EPISODE = re.compile(
    r"network episode started: session=(?P<session>[A-F0-9]{12}) "
    r"episode=(?P<episode>\d+) first_observation_sequence=0 "
    r"applied_local_cm_per_sec=\(0\.00, 0\.00\) prior_state_cleared=true"
)
_RESET = re.compile(
    r"reset verified: episode=(?P<episode>\d+) attempts=(?P<attempts>\d+) "
    r"state_sequence=(?P<state>\d+).*position_error_cm=(?P<position>[0-9.]+) "
    r"facing_error_deg=(?P<facing>[0-9.]+) "
    r"linear_speed_cm_per_sec=(?P<linear>[0-9.]+) "
    r"angular_speed_deg_per_sec=(?P<angular>[0-9.]+)"
)
_OBSERVATION = re.compile(
    r"network observation sent: session=(?P<session>[A-F0-9]{12}) "
    r"episode=(?P<episode>\d+) observation=(?P<sequence>\d+) "
    r"state_sequence=(?P<state>\d+)"
)
_ACTION = re.compile(
    r"network action accepted: session=(?P<session>[A-F0-9]{12}) "
    r"episode=(?P<episode>\d+) source_observation=(?P<sequence>\d+) "
    r"desired_local_cm_per_sec=\((?P<x>-?[0-9.]+), (?P<y>-?[0-9.]+)\) "
    r"unreal_end_to_end_latency_ms=(?P<latency>[0-9.]+) "
    r"current_identity_match=true before_deadline=true"
)
_STATE = re.compile(
    r"state sample: protocol=1 sequence=(?P<sequence>\d+) valid=true .*resim=false "
    r"mode=Walking position_world_cm=\((?P<px>-?[0-9.]+), (?P<py>-?[0-9.]+), "
    r"(?P<pz>-?[0-9.]+)\) velocity_world_cm_per_sec=\((?P<vx>-?[0-9.]+), "
    r"(?P<vy>-?[0-9.]+), (?P<vz>-?[0-9.]+)\).*"
    r"angular_velocity_world_deg_per_sec=\((?P<ax>-?[0-9.]+), (?P<ay>-?[0-9.]+), "
    r"(?P<az>-?[0-9.]+)\)"
)
_ECHO = re.compile(
    r"command echo: revision=(?P<revision>\d+).*finite=true "
    r"requested_frame=\((?P<rx>-?[0-9.]+), (?P<ry>-?[0-9.]+), (?P<rz>-?[0-9.]+)\) "
    r"submitted_world=\((?P<sx>-?[0-9.]+), (?P<sy>-?[0-9.]+), (?P<sz>-?[0-9.]+)\) "
    r"echoed_world=\((?P<ex>-?[0-9.]+), (?P<ey>-?[0-9.]+), (?P<ez>-?[0-9.]+)\) "
    r"match=true"
)


@dataclass(frozen=True, slots=True)
class BranchPreviewAudit:
    source_sha256: str
    session_id: str
    episode_id: int
    first_line_number: int
    last_line_number: int
    observation_sequences: tuple[int, ...]
    accepted_sequences: tuple[int, ...]
    accepted_gaps: tuple[int, ...]
    contiguous_prefix_count: int
    latencies_ms: tuple[float, ...]
    echo_count: int
    state_sample_count: int
    reset_state_sequence: int

    def latency_summary(self) -> dict[str, float | int]:
        values = sorted(self.latencies_ms)
        index = (len(values) - 1) * 0.95
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        p95 = values[lower] + (index - lower) * (values[upper] - values[lower])
        return {
            "count": len(values),
            "median": statistics.median(values),
            "p95": p95,
            "maximum": max(values),
        }


def _one(matches: list[tuple[int, re.Match[str]]], context: str) -> tuple[int, re.Match[str]]:
    if len(matches) != 1:
        raise ValueError(f"{context} must occur exactly once")
    return matches[0]


def _zero(match: re.Match[str], names: tuple[str, ...], context: str) -> None:
    if any(float(match[name]) != 0.0 for name in names):
        raise ValueError(f"{context} must be exactly zero")


def audit_branch_preview_live(raw: bytes, session_id: str, episode_id: int) -> BranchPreviewAudit:
    """Audit only the declared session/episode; unrelated log text is ignored."""

    if not re.fullmatch(r"[A-F0-9]{12}", session_id):
        raise ValueError("session_id must contain exactly 12 uppercase hex characters")
    lines = raw.decode("utf-8-sig").splitlines()
    starts = [(i, m) for i, line in enumerate(lines) if (m := _START.search(line))]
    start_index, start = _one(starts, "network evidence start")
    if start["session"] != session_id or start["controller"] != "branch_preview":
        raise ValueError("source is not the declared single branch_preview session")

    boundaries = [
        (i, m)
        for i, line in enumerate(lines)
        if (m := _BOUNDARY.search(line)) and m["session"] == session_id
    ]
    boundary_index, _ = _one(boundaries, "cleared reset boundary")
    episodes = [(i, m) for i, line in enumerate(lines) if (m := _EPISODE.search(line))]
    episode_index, episode = _one(episodes, "network episode start")
    if episode["session"] != session_id or int(episode["episode"]) != episode_id:
        raise ValueError("source is not the declared single episode")
    resets = [
        (i, m)
        for i, line in enumerate(lines)
        if (m := _RESET.search(line)) and int(m["episode"]) == episode_id
    ]
    reset_index, reset = _one(resets, "verified reset")
    _zero(reset, ("position", "facing", "linear", "angular"), "verified reset errors")
    if int(reset["attempts"]) < 1:
        raise ValueError("verified reset must have at least one attempt")

    state_matches = [(i, m) for i, line in enumerate(lines) if (m := _STATE.search(line))]
    reset_states = [(i, m) for i, m in state_matches if int(m["sequence"]) == int(reset["state"])]
    reset_state_index, _ = _one(reset_states, "authoritative reset state")
    if not (start_index < boundary_index < reset_state_index < episode_index < reset_index):
        raise ValueError("reset gate and episode lifecycle are not in the required order")

    observations: list[int] = []
    actions: list[int] = []
    latencies: list[float] = []
    last_relevant = reset_index
    for index, line in enumerate(lines[episode_index:], start=episode_index):
        if (
            f"network action accepted: session={session_id} episode={episode_id} " in line
            and _ACTION.search(line) is None
        ):
            raise ValueError("malformed or non-admitted accepted-action evidence")
        if (match := _OBSERVATION.search(line)) and match["session"] == session_id:
            if int(match["episode"]) != episode_id:
                raise ValueError("declared session contains another episode")
            observations.append(int(match["sequence"]))
            last_relevant = index
        if (match := _ACTION.search(line)) and match["session"] == session_id:
            if int(match["episode"]) != episode_id:
                raise ValueError("declared session contains another episode")
            _zero(match, ("x", "y"), "accepted desired command")
            actions.append(int(match["sequence"]))
            latencies.append(float(match["latency"]))
            last_relevant = index
    if observations != list(range(len(observations))):
        raise ValueError("observations must be contiguous from zero")
    if not actions or actions != sorted(set(actions)):
        raise ValueError("accepted identities must be unique and strictly increasing")
    if any(sequence not in set(observations) for sequence in actions):
        raise ValueError("accepted action lacks its matching observation")
    prefix = 0
    for sequence in actions:
        if sequence != prefix:
            break
        prefix += 1
    gaps = tuple(sequence for sequence in range(actions[-1] + 1) if sequence not in set(actions))

    episode_tail = lines[episode_index + 1 :]
    if any("command echo:" in line and _ECHO.search(line) is None for line in episode_tail):
        raise ValueError("malformed or non-matching command echo evidence")
    echoes = [(i, m) for i, m in ((i, _ECHO.search(line)) for i, line in enumerate(lines)) if m]
    episode_echoes = [m for i, m in echoes if episode_index < i]
    if not episode_echoes:
        raise ValueError("episode contains no command echoes")
    for match in episode_echoes:
        _zero(
            match,
            ("rx", "ry", "rz", "sx", "sy", "sz", "ex", "ey", "ez"),
            "command echo vectors",
        )

    episode_states = [m for i, m in state_matches if reset_state_index <= i]
    if not episode_states:
        raise ValueError("episode contains no authoritative state samples")
    anchor = tuple(float(episode_states[0][name]) for name in ("px", "py", "pz"))
    for match in episode_states:
        if tuple(float(match[name]) for name in ("px", "py", "pz")) != anchor:
            raise ValueError("authoritative position changed")
        _zero(match, ("vx", "vy", "vz", "ax", "ay", "az"), "authoritative motion")

    return BranchPreviewAudit(
        source_sha256=hashlib.sha256(raw).hexdigest(),
        session_id=session_id,
        episode_id=episode_id,
        first_line_number=start_index + 1,
        last_line_number=last_relevant + 1,
        observation_sequences=tuple(observations),
        accepted_sequences=tuple(actions),
        accepted_gaps=gaps,
        contiguous_prefix_count=prefix,
        latencies_ms=tuple(latencies),
        echo_count=len(episode_echoes),
        state_sample_count=len(episode_states),
        reset_state_sequence=int(reset["state"]),
    )
