"""Strict parser and plotter for visual-only Unreal animation-root diagnostics."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_HEADER = re.compile(
    rf"MotionWorld animation diagnostic: session=(?P<session>[A-Fa-f0-9]+) "
    rf"protocol=(?P<protocol>\d+) state_sequence=(?P<sequence>\d+) "
    rf"sim_time_s=(?P<time>{_NUMBER}) "
    r"capture_phase=mover_on_post_finalize_current_pose_buffer "
    r"visual_component=(?P<component>\S+) root_bone=(?P<root>\S+) "
)


class AnimationTraceValidationError(ValueError):
    """Raised when a diagnostic trace is ambiguous or internally inconsistent."""


@dataclass(frozen=True)
class AnimationTraceSample:
    session_id: str
    state_sequence: int
    simulation_time_s: float
    visual_component_name: str
    root_bone_name: str
    actor_position_world_cm: tuple[float, float, float]
    visual_component_position_world_cm: tuple[float, float, float]
    animation_root_position_world_cm: tuple[float, float, float]
    actor_to_animation_root_world_cm: tuple[float, float, float]


@dataclass(frozen=True)
class AnimationTrace:
    session_id: str
    visual_component_name: str
    root_bone_name: str
    samples: tuple[AnimationTraceSample, ...]


def _vector(line: str, field: str) -> tuple[float, float, float]:
    match = re.search(
        rf"{re.escape(field)}=\(({_NUMBER}), ({_NUMBER}), ({_NUMBER})\)",
        line,
    )
    if match is None:
        raise AnimationTraceValidationError(f"missing or malformed {field}")
    result = tuple(float(match.group(index)) for index in range(1, 4))
    if not all(math.isfinite(value) for value in result):
        raise AnimationTraceValidationError(f"{field} contains a non-finite value")
    return result  # type: ignore[return-value]


def _distance(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def load_animation_trace(path: Path, *, session_id: str | None = None) -> AnimationTrace:
    """Load one session, selecting the last observed session when none is specified."""

    if not path.is_file():
        raise AnimationTraceValidationError(f"log file does not exist: {path}")

    grouped: dict[str, list[AnimationTraceSample]] = {}
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    for line_number, line in enumerate(lines, 1):
        if "MotionWorld animation diagnostic:" not in line:
            continue
        header = _HEADER.search(line)
        if header is None:
            raise AnimationTraceValidationError(f"line {line_number}: malformed diagnostic header")
        if " model_input=false" not in line:
            raise AnimationTraceValidationError(
                f"line {line_number}: missing model_input=false guard"
            )
        if int(header.group("protocol")) != 1:
            raise AnimationTraceValidationError(f"line {line_number}: unsupported protocol")

        sample = AnimationTraceSample(
            session_id=header.group("session"),
            state_sequence=int(header.group("sequence")),
            simulation_time_s=float(header.group("time")),
            visual_component_name=header.group("component"),
            root_bone_name=header.group("root"),
            actor_position_world_cm=_vector(line, "actor_position_world_cm"),
            visual_component_position_world_cm=_vector(
                line, "visual_component_position_world_cm"
            ),
            animation_root_position_world_cm=_vector(line, "animation_root_position_world_cm"),
            actor_to_animation_root_world_cm=_vector(
                line, "actor_to_animation_root_world_cm"
            ),
        )
        if not math.isfinite(sample.simulation_time_s) or sample.simulation_time_s < 0.0:
            raise AnimationTraceValidationError(f"line {line_number}: invalid simulation time")
        expected_offset = tuple(
            root - actor
            for root, actor in zip(
                sample.animation_root_position_world_cm,
                sample.actor_position_world_cm,
                strict=True,
            )
        )
        if _distance(sample.actor_to_animation_root_world_cm, expected_offset) > 1e-3:
            raise AnimationTraceValidationError(f"line {line_number}: root offset is inconsistent")
        grouped.setdefault(sample.session_id, []).append(sample)

    if not grouped:
        raise AnimationTraceValidationError("no animation diagnostic samples found")
    selected_session = session_id or next(reversed(grouped))
    if selected_session not in grouped:
        raise AnimationTraceValidationError(f"session not found: {selected_session}")
    samples = grouped[selected_session]
    if len(samples) < 2:
        raise AnimationTraceValidationError("trace requires at least two samples")

    component_names = {sample.visual_component_name for sample in samples}
    root_names = {sample.root_bone_name for sample in samples}
    if len(component_names) != 1 or len(root_names) != 1:
        raise AnimationTraceValidationError(
            "visual component or root bone changed within the session"
        )
    for previous, current in zip(samples, samples[1:], strict=False):
        if current.state_sequence <= previous.state_sequence:
            raise AnimationTraceValidationError("state sequence is not strictly increasing")
        if current.simulation_time_s <= previous.simulation_time_s:
            raise AnimationTraceValidationError("simulation time is not strictly increasing")

    return AnimationTrace(
        session_id=selected_session,
        visual_component_name=next(iter(component_names)),
        root_bone_name=next(iter(root_names)),
        samples=tuple(samples),
    )


def plot_animation_trace(trace: AnimationTrace, output_path: Path) -> None:
    """Plot authoritative and visual trajectories plus their offset magnitude."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path.parent.mkdir(parents=True, exist_ok=True)
    actor_x = [sample.actor_position_world_cm[0] for sample in trace.samples]
    actor_y = [sample.actor_position_world_cm[1] for sample in trace.samples]
    root_x = [sample.animation_root_position_world_cm[0] for sample in trace.samples]
    root_y = [sample.animation_root_position_world_cm[1] for sample in trace.samples]
    start_time = trace.samples[0].simulation_time_s
    times = [sample.simulation_time_s - start_time for sample in trace.samples]
    planar_offsets = [
        math.hypot(
            sample.actor_to_animation_root_world_cm[0],
            sample.actor_to_animation_root_world_cm[1],
        )
        for sample in trace.samples
    ]

    figure, (trajectory_axis, offset_axis) = plt.subplots(1, 2, figsize=(11, 4.5))
    trajectory_axis.plot(actor_x, actor_y, label="Authoritative Mover actor", linewidth=2.2)
    trajectory_axis.plot(root_x, root_y, label="Animation root (visual QA)", linewidth=1.6)
    trajectory_axis.set_title("Gameplay vs visual trajectory")
    trajectory_axis.set_xlabel("World X (cm)")
    trajectory_axis.set_ylabel("World Y (cm)")
    trajectory_axis.axis("equal")
    trajectory_axis.grid(alpha=0.25)
    trajectory_axis.legend()

    offset_axis.plot(times, planar_offsets, color="#d95f02", linewidth=1.8)
    offset_axis.set_title("Planar actor-to-root offset")
    offset_axis.set_xlabel("Trace time (s)")
    offset_axis.set_ylabel("Offset magnitude (cm)")
    offset_axis.grid(alpha=0.25)
    figure.suptitle(
        f"MotionWorld animation diagnostic — {trace.visual_component_name}/{trace.root_bone_name}"
    )
    figure.tight_layout()
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
