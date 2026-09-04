"""Strict, bounded audit of one preserved Unreal nominal-MPC session."""

from __future__ import annotations

import hashlib
import math
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
    r"state_sequence=(?P<state>\d+) simulation_time_s=(?P<time>[0-9.]+)"
)
_ACTION = re.compile(
    r"network action accepted: session=(?P<session>[A-F0-9]{12}) "
    r"episode=(?P<episode>\d+) source_observation=(?P<sequence>\d+) "
    r"desired_local_cm_per_sec=\((?P<x>-?[0-9.]+), (?P<y>-?[0-9.]+)\) "
    r"unreal_end_to_end_latency_ms=(?P<latency>[0-9.]+) "
    r"current_identity_match=true before_deadline=true"
)
_STATE = re.compile(
    r"state sample: protocol=1 sequence=(?P<sequence>\d+) valid=true .*"
    r"sim_time_s=(?P<time>[0-9.]+).*resim=false mode=Walking "
    r"position_world_cm=\((?P<px>-?[0-9.]+), (?P<py>-?[0-9.]+), "
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
class NominalMPCAudit:
    source_sha256: str
    session_id: str
    episode_id: int
    first_line_number: int
    last_line_number: int
    observation_sequences: tuple[int, ...]
    accepted_sequences: tuple[int, ...]
    missing_action_sequences: tuple[int, ...]
    command_magnitudes_cm_s: tuple[float, ...]
    latencies_ms: tuple[float, ...]
    matched_action_echo_count: int
    unmatched_final_action_count: int
    state_sample_count: int
    reset_state_sequence: int
    maximum_planar_displacement_cm: float
    final_planar_displacement_cm: float

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


def audit_nominal_mpc_live(
    raw: bytes,
    session_id: str,
    episode_id: int,
    *,
    maximum_command_speed_cm_s: float = 165.0,
    deadline_ms: float = 100.0,
) -> NominalMPCAudit:
    """Audit the declared live session without inferring unlogged visualization state."""

    if not re.fullmatch(r"[A-F0-9]{12}", session_id):
        raise ValueError("session_id must contain exactly 12 uppercase hex characters")
    if episode_id != 7504:
        raise ValueError("D5 audit requires prospective demo episode 7504")
    if maximum_command_speed_cm_s != 165.0 or deadline_ms != 100.0:
        raise ValueError("D5 command and deadline bounds are frozen at 165 cm/s and 100 ms")
    lines = raw.decode("utf-8-sig").splitlines()

    start_index, start = _one(
        [(i, m) for i, line in enumerate(lines) if (m := _START.search(line))],
        "network evidence start",
    )
    if start["session"] != session_id or start["controller"] != "nominal_mpc":
        raise ValueError("source is not the declared single nominal_mpc session")
    boundary_index, _ = _one(
        [
            (i, m)
            for i, line in enumerate(lines)
            if (m := _BOUNDARY.search(line)) and m["session"] == session_id
        ],
        "cleared reset boundary",
    )
    episode_index, episode = _one(
        [(i, m) for i, line in enumerate(lines) if (m := _EPISODE.search(line))],
        "network episode start",
    )
    if episode["session"] != session_id or int(episode["episode"]) != episode_id:
        raise ValueError("source is not the declared single episode")
    reset_index, reset = _one(
        [
            (i, m)
            for i, line in enumerate(lines)
            if (m := _RESET.search(line)) and int(m["episode"]) == episode_id
        ],
        "verified reset",
    )
    _zero(reset, ("position", "facing", "linear", "angular"), "verified reset errors")
    if int(reset["attempts"]) < 1:
        raise ValueError("verified reset must have at least one attempt")

    state_matches = [(i, m) for i, line in enumerate(lines) if (m := _STATE.search(line))]
    reset_state_index, _ = _one(
        [(i, m) for i, m in state_matches if int(m["sequence"]) == int(reset["state"])],
        "authoritative reset state",
    )
    if not (start_index < boundary_index < reset_state_index < episode_index < reset_index):
        raise ValueError("reset gate and episode lifecycle are not in the required order")

    observations: list[int] = []
    observation_states: list[int] = []
    observation_times: list[float] = []
    actions: list[int] = []
    commands: list[tuple[float, float]] = []
    magnitudes: list[float] = []
    latencies: list[float] = []
    last_relevant = reset_index
    for index, line in enumerate(lines[episode_index:], start=episode_index):
        if f"network action accepted: session={session_id} episode={episode_id} " in line:
            match = _ACTION.search(line)
            if match is None:
                raise ValueError("malformed or non-admitted accepted-action evidence")
            x, y = float(match["x"]), float(match["y"])
            magnitude = math.hypot(x, y)
            latency = float(match["latency"])
            if not math.isfinite(magnitude) or magnitude <= 0.0:
                raise ValueError("accepted desired command must be finite and nonzero")
            if magnitude > maximum_command_speed_cm_s + 1.0e-6:
                raise ValueError("accepted desired command exceeds the 165 cm/s bound")
            if not 0.0 <= latency < deadline_ms:
                raise ValueError("accepted action latency must be below the 100 ms deadline")
            actions.append(int(match["sequence"]))
            commands.append((x, y))
            magnitudes.append(magnitude)
            latencies.append(latency)
            last_relevant = index
        if (match := _OBSERVATION.search(line)) and match["session"] == session_id:
            if int(match["episode"]) != episode_id:
                raise ValueError("declared session contains another episode")
            observations.append(int(match["sequence"]))
            observation_states.append(int(match["state"]))
            observation_times.append(float(match["time"]))
            last_relevant = index

    if observations != list(range(len(observations))):
        raise ValueError("observations must be contiguous from zero")
    if observation_states != sorted(set(observation_states)):
        raise ValueError("observation state sequences must be unique and strictly increasing")
    if any(
        right <= left
        for left, right in zip(observation_times, observation_times[1:], strict=False)
    ):
        raise ValueError("observation simulation times must be strictly increasing")
    if not actions or actions != sorted(set(actions)):
        raise ValueError("accepted identities must be unique and strictly increasing")
    observation_set = set(observations)
    if any(sequence not in observation_set for sequence in actions):
        raise ValueError("accepted action lacks its matching observation")
    missing = tuple(sequence for sequence in observations if sequence not in set(actions))

    pending: tuple[float, float] | None = None
    matched_echoes = 0
    for line in lines[episode_index + 1 :]:
        action_match = _ACTION.search(line)
        if action_match and action_match["session"] == session_id:
            if pending is not None:
                raise ValueError("accepted action was superseded before a matching command echo")
            pending = (float(action_match["x"]), float(action_match["y"]))
            continue
        if "command echo:" not in line:
            continue
        echo = _ECHO.search(line)
        if echo is None:
            raise ValueError("malformed or non-matching command echo evidence")
        _zero(echo, ("rz", "sz", "ez"), "command echo vertical components")
        if pending is None:
            continue
        requested = (float(echo["rx"]), float(echo["ry"]))
        submitted = (float(echo["sx"]), float(echo["sy"]))
        echoed = (float(echo["ex"]), float(echo["ey"]))
        if any(
            abs(actual - expected) > 0.0051
            for vector in (requested, submitted, echoed)
            for actual, expected in zip(vector, pending, strict=True)
        ):
            raise ValueError("command echo does not match the preceding accepted action")
        pending = None
        matched_echoes += 1
    unmatched_final = int(pending is not None)
    if matched_echoes < len(actions) - 1 or unmatched_final > 1:
        raise ValueError("accepted actions lack matching command echoes")

    episode_states = [(i, m) for i, m in state_matches if i >= reset_state_index]
    if len(episode_states) < 2:
        raise ValueError("episode must contain multiple authoritative state samples")
    state_sequences = [int(match["sequence"]) for _, match in episode_states]
    state_times = [float(match["time"]) for _, match in episode_states]
    if state_sequences != sorted(set(state_sequences)):
        raise ValueError("authoritative state sequences must be unique and strictly increasing")
    if any(
        right <= left for left, right in zip(state_times, state_times[1:], strict=False)
    ):
        raise ValueError("authoritative state times must be strictly increasing")
    positions = [
        tuple(float(match[name]) for name in ("px", "py", "pz"))
        for _, match in episode_states
    ]
    if any(not all(math.isfinite(value) for value in position) for position in positions):
        raise ValueError("authoritative positions must be finite")
    anchor = positions[0]
    displacements = [
        math.hypot(position[0] - anchor[0], position[1] - anchor[1])
        for position in positions
    ]
    if max(displacements) <= 0.0:
        raise ValueError("authoritative pawn never displaced from the reset anchor")

    return NominalMPCAudit(
        source_sha256=hashlib.sha256(raw).hexdigest(),
        session_id=session_id,
        episode_id=episode_id,
        first_line_number=start_index + 1,
        last_line_number=last_relevant + 1,
        observation_sequences=tuple(observations),
        accepted_sequences=tuple(actions),
        missing_action_sequences=missing,
        command_magnitudes_cm_s=tuple(magnitudes),
        latencies_ms=tuple(latencies),
        matched_action_echo_count=matched_echoes,
        unmatched_final_action_count=unmatched_final,
        state_sample_count=len(episode_states),
        reset_state_sequence=int(reset["state"]),
        maximum_planar_displacement_cm=max(displacements),
        final_planar_displacement_cm=displacements[-1],
    )
