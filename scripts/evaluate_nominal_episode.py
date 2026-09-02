#!/usr/bin/env python3
"""Evaluate the faithful nominal model one step at a time on a schema-v3/v4 episode."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from motionworld.data import load_episode
from motionworld.dynamics.nominal_episode import (
    internal_from_context_record,
    observable_from_state_record,
    retrospective_nominal_inputs,
)
from motionworld.dynamics.smooth_walking_math import find_delta_angle_radians
from motionworld.dynamics.smooth_walking_nominal import smooth_walking_nominal_step


@dataclass(frozen=True, slots=True)
class RowMetrics:
    transition_sequence: int
    end_simulation_time_s: float
    dt_s: float
    collision_this_step: bool
    position_error_cm: float
    planar_position_error_cm: float
    velocity_error_cm_s: float
    planar_velocity_error_cm_s: float
    yaw_error_deg: float
    angular_velocity_yaw_error_deg_s: float
    spring_velocity_error_cm_s: float
    spring_acceleration_error_cm_s2: float
    intermediate_velocity_error_cm_s: float


def _norm(values: np.ndarray) -> float:
    return float(np.linalg.norm(values))


def _metrics(
    transition: dict[str, object],
    *,
    effective_max_speed_cm_s: float | None,
) -> RowMetrics:
    desired_facing = (
        None
        if "desired_facing_yaw_deg" in transition["applied_action"]
        else math.radians(float(transition["previous_state"]["facing_yaw_deg"]))
    )
    inputs = retrospective_nominal_inputs(
        transition,
        desired_facing_yaw_rad=desired_facing,
        effective_max_speed_cm_s=effective_max_speed_cm_s,
    )
    prediction = smooth_walking_nominal_step(
        inputs.observable,
        inputs.internal,
        inputs.action,
        parameters=inputs.parameters,
        dt_s=inputs.dt_s,
    )
    actual = observable_from_state_record(transition["next_state"])
    actual_internal = internal_from_context_record(transition["nominal_context"]["next"])
    position_delta = prediction.observable_next.position_world_cm - actual.position_world_cm
    velocity_delta = prediction.observable_next.velocity_world_cm_s - actual.velocity_world_cm_s
    predicted_velocity_state = prediction.internal_next.velocity
    actual_velocity_state = actual_internal.velocity
    scenario = transition.get("scenario")
    collision = bool(scenario["collision_this_step"]) if scenario is not None else False
    return RowMetrics(
        transition_sequence=int(transition["transition_sequence"]),
        end_simulation_time_s=float(transition["end_simulation_time_s"]),
        dt_s=inputs.dt_s,
        collision_this_step=collision,
        position_error_cm=_norm(position_delta),
        planar_position_error_cm=_norm(position_delta[:2]),
        velocity_error_cm_s=_norm(velocity_delta),
        planar_velocity_error_cm_s=_norm(velocity_delta[:2]),
        yaw_error_deg=abs(
            math.degrees(
                find_delta_angle_radians(
                    prediction.observable_next.facing_yaw_rad,
                    actual.facing_yaw_rad,
                )
            )
        ),
        angular_velocity_yaw_error_deg_s=abs(
            prediction.observable_next.angular_velocity_yaw_deg_s
            - actual.angular_velocity_yaw_deg_s
        ),
        spring_velocity_error_cm_s=_norm(
            predicted_velocity_state.spring_velocity_world_cm_s
            - actual_velocity_state.spring_velocity_world_cm_s
        ),
        spring_acceleration_error_cm_s2=_norm(
            predicted_velocity_state.spring_acceleration_world_cm_s2
            - actual_velocity_state.spring_acceleration_world_cm_s2
        ),
        intermediate_velocity_error_cm_s=_norm(
            predicted_velocity_state.intermediate_velocity_world_cm_s
            - actual_velocity_state.intermediate_velocity_world_cm_s
        ),
    )


def _summary(
    path: Path,
    rows: list[RowMetrics],
    *,
    effective_max_speed_cm_s: float | None,
    schema_version: int,
    recorded_input_preparations: list[dict[str, object]],
) -> dict[str, object]:
    def stats(field: str, selected_rows: list[RowMetrics]) -> dict[str, float]:
        values = np.asarray([getattr(row, field) for row in selected_rows])
        return {
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95)),
            "max": float(np.max(values)),
        }

    metric_fields = (
        "position_error_cm",
        "planar_position_error_cm",
        "velocity_error_cm_s",
        "planar_velocity_error_cm_s",
        "yaw_error_deg",
        "angular_velocity_yaw_error_deg_s",
        "spring_velocity_error_cm_s",
        "spring_acceleration_error_cm_s2",
        "intermediate_velocity_error_cm_s",
    )
    non_collision_rows = [row for row in rows if not row.collision_this_step]
    collision_rows = [row for row in rows if row.collision_this_step]
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    result: dict[str, object] = {
        "episode_file": path.name,
        "episode_sha256": file_hash,
        "evaluation": "retrospective_one_step",
        "desired_facing_source": (
            "recorded_applied_action"
            if schema_version >= 4
            else "legacy_hold_previous_authoritative_facing_assumption"
        ),
        "parameter_source": "parameters_observed_for_completed_step",
        "effective_max_speed_cm_s": (
            sorted(
                {
                    float(item["effective_max_speed_cm_per_s"])
                    for item in recorded_input_preparations
                }
            )
            if schema_version >= 4
            else effective_max_speed_cm_s
        ),
        "effective_max_speed_source": (
            sorted({str(item["max_speed_source"]) for item in recorded_input_preparations})
            if schema_version >= 4
            else "required_explicit_evaluator_input"
        ),
        "transition_count": len(rows),
        "collision_step_count": sum(row.collision_this_step for row in rows),
        "metrics": {field: stats(field, rows) for field in metric_fields},
        "non_collision_metrics": {
            field: stats(field, non_collision_rows) for field in metric_fields
        },
        "claim_boundary": [
            "one-step evaluation re-seeds observable and internal state from every real transition",
            "completed-step parameters are retrospective and are not automatically "
            "planner-available",
            (
                "schema v4 supplies recorded facing and SimpleWalking input preparation"
                if schema_version >= 4
                else "schema v3 omits orientation and max speed; explicit legacy assumptions apply"
            ),
            "dataset eligibility and split membership are decided outside this evaluator",
        ],
    }
    if collision_rows:
        result["collision_metrics"] = {
            field: stats(field, collision_rows) for field in metric_fields
        }
    return result


def _write_plot(rows: list[RowMetrics], path: Path) -> None:
    times = np.asarray([row.end_simulation_time_s for row in rows])
    position_errors = np.asarray([row.planar_position_error_cm for row in rows])
    velocity_errors = np.asarray([row.planar_velocity_error_cm_s for row in rows])
    collision_times = [row.end_simulation_time_s for row in rows if row.collision_this_step]

    figure, axes = plt.subplots(2, 1, figsize=(9.0, 5.8), sharex=True, constrained_layout=True)
    axes[0].plot(times, position_errors, color="#3366aa", linewidth=1.8)
    axes[0].set_ylabel("Planar position error (cm)")
    axes[0].set_title("Faithful nominal model: retrospective one-step error")
    axes[1].plot(times, velocity_errors, color="#aa5533", linewidth=1.8)
    axes[1].set_ylabel("Planar velocity error (cm/s)")
    axes[1].set_xlabel("Unreal simulation time (s)")
    for axis in axes:
        axis.grid(alpha=0.25, linewidth=0.7)
        for collision_time in collision_times:
            axis.axvline(collision_time, color="#333333", linestyle="--", linewidth=1.0)
    if collision_times:
        axes[0].annotate(
            "recorded gate collision",
            xy=(collision_times[0], np.max(position_errors)),
            xytext=(-8, -20),
            textcoords="offset points",
            ha="right",
            fontsize=9,
        )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--effective-max-speed-cm-s", type=float)
    args = parser.parse_args()

    episode = load_episode(args.episode)
    schema_version = int(episode.header["schema_version"])
    if schema_version not in {3, 4}:
        raise ValueError("faithful nominal evaluation requires episode schema version 3 or 4")
    if schema_version == 3 and args.effective_max_speed_cm_s is None:
        raise ValueError("schema-v3 evaluation requires --effective-max-speed-cm-s")
    rows = [
        _metrics(
            transition,
            effective_max_speed_cm_s=args.effective_max_speed_cm_s,
        )
        for transition in episode.transitions
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.output_dir / "one_step_errors.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0])))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    summary = _summary(
        args.episode,
        rows,
        effective_max_speed_cm_s=args.effective_max_speed_cm_s,
        schema_version=schema_version,
        recorded_input_preparations=[
            transition["nominal_context"]["input_preparation_observed_for_completed_step"]
            for transition in episode.transitions
        ]
        if schema_version >= 4
        else [],
    )
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_plot(rows, args.output_dir / "one_step_error.png")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
