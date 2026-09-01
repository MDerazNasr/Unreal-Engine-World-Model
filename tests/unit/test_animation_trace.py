from __future__ import annotations

from pathlib import Path

import pytest

from motionworld.diagnostics import AnimationTraceValidationError, load_animation_trace


def _line(
    *,
    session: str = "ABC123",
    sequence: int,
    time: float,
    actor_x: float,
    root_x: float,
    offset_x: float | None = None,
) -> str:
    offset = root_x - actor_x if offset_x is None else offset_x
    return (
        "[prefix] MotionWorld animation diagnostic: "
        f"session={session} protocol=1 state_sequence={sequence} sim_time_s={time:.6f} "
        "capture_phase=mover_on_post_finalize_current_pose_buffer "
        "visual_component=Mesh root_bone=root "
        f"actor_position_world_cm=({actor_x:.6f}, 0.000000, 90.000000) "
        f"visual_component_position_world_cm=({actor_x:.6f}, 0.000000, 0.000000) "
        "visual_component_rotation_world_deg=(0.000000, 0.000000, 0.000000) "
        "visual_component_scale=(1.000000, 1.000000, 1.000000) "
        f"animation_root_position_world_cm=({root_x:.6f}, 0.000000, 2.000000) "
        "animation_root_rotation_world_deg=(0.000000, 0.000000, 0.000000) "
        "animation_root_scale=(1.000000, 1.000000, 1.000000) "
        f"actor_to_animation_root_world_cm=({offset:.6f}, 0.000000, -88.000000) "
        "model_input=false"
    )


def _write(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "GameAnimationSample.log"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_loads_latest_complete_session_and_checks_offset(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            _line(session="ABC111", sequence=0, time=0.1, actor_x=0.0, root_x=1.0),
            _line(session="ABC111", sequence=1, time=0.2, actor_x=2.0, root_x=3.0),
            _line(session="DEF222", sequence=10, time=1.0, actor_x=10.0, root_x=11.5),
            _line(session="DEF222", sequence=11, time=1.1, actor_x=12.0, root_x=13.0),
        ],
    )

    trace = load_animation_trace(path)

    assert trace.session_id == "DEF222"
    assert trace.visual_component_name == "Mesh"
    assert trace.root_bone_name == "root"
    assert len(trace.samples) == 2
    assert trace.samples[0].actor_to_animation_root_world_cm == (1.5, 0.0, -88.0)


def test_rejects_non_monotonic_sequence(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            _line(sequence=3, time=0.1, actor_x=0.0, root_x=1.0),
            _line(sequence=3, time=0.2, actor_x=2.0, root_x=3.0),
        ],
    )

    with pytest.raises(AnimationTraceValidationError, match="sequence"):
        load_animation_trace(path)


def test_rejects_inconsistent_root_offset(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            _line(sequence=0, time=0.1, actor_x=0.0, root_x=1.0),
            _line(sequence=1, time=0.2, actor_x=2.0, root_x=3.0, offset_x=9.0),
        ],
    )

    with pytest.raises(AnimationTraceValidationError, match="offset"):
        load_animation_trace(path)
