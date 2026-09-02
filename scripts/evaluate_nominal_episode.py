#!/usr/bin/env python3
"""Evaluate the faithful nominal model one step at a time on a schema-v3/v4/v5 episode."""

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
    current_snapshot_nominal_inputs,
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
    perturbation_phase: str
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
    perturbation_phase: str,
    parameter_source: str,
) -> RowMetrics:
    desired_facing = (
        None
        if "desired_facing_yaw_deg" in transition["applied_action"]
        else math.radians(float(transition["previous_state"]["facing_yaw_deg"]))
    )
    if parameter_source == "current-snapshot":
        inputs = current_snapshot_nominal_inputs(transition)
    else:
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
        perturbation_phase=perturbation_phase,
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
    header: dict[str, object],
    transitions: list[dict[str, object]],
    parameter_source: str,
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
        "evaluation": (
            "causal_current_snapshot_one_step"
            if parameter_source == "current-snapshot"
            else "retrospective_one_step"
        ),
        "desired_facing_source": (
            "recorded_applied_action"
            if schema_version >= 4
            else "legacy_hold_previous_authoritative_facing_assumption"
        ),
        "parameter_source": (
            "previous_finalized_context"
            if parameter_source == "current-snapshot"
            else "parameters_observed_for_completed_step"
        ),
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
            (
                "parameters and input preparation come only from the current finalized state"
                if parameter_source == "current-snapshot"
                else "completed-step parameters are retrospective and are not automatically "
                "planner-available"
            ),
            (
                "schema v4+ supplies recorded facing and SimpleWalking input preparation"
                if schema_version >= 4
                else "schema v3 omits orientation and max speed; explicit legacy assumptions apply"
            ),
            "dataset eligibility and split membership are decided outside this evaluator",
        ],
    }
    if schema_version >= 5:
        phase_order = ("pre_event", "event", "post_event", "no_event")
        result["perturbation_phase_metrics"] = {
            phase: {
                "transition_count": len(selected),
                "metrics": {field: stats(field, selected) for field in metric_fields},
            }
            for phase in phase_order
            if (selected := [row for row in rows if row.perturbation_phase == phase])
        }
        event_rows = [
            transition
            for transition in transitions
            if transition["external_perturbation"]["type"] == "additive_velocity"
        ]
        if event_rows:
            event_row = event_rows[0]
            requested = np.asarray(
                event_row["external_perturbation"][
                    "requested_velocity_delta_world_cm_per_s"
                ],
                dtype=float,
            )
            previous_velocity = np.asarray(
                event_row["previous_state"]["velocity_world_cm_per_s"], dtype=float
            )
            next_velocity = np.asarray(
                event_row["next_state"]["velocity_world_cm_per_s"], dtype=float
            )
            observed_change = next_velocity - previous_velocity
            requested_norm = _norm(requested)
            requested_direction = requested / requested_norm
            observed_along_request = float(np.dot(observed_change, requested_direction))
            result["external_perturbation_observation"] = {
                "transition_sequence": int(event_row["transition_sequence"]),
                "queued_after_state_sample_sequence": int(
                    event_row["external_perturbation"][
                        "queued_after_state_sample_sequence"
                    ]
                ),
                "previous_state_sample_sequence": int(
                    event_row["previous_state"]["sample_sequence"]
                ),
                "next_state_sample_sequence": int(event_row["next_state"]["sample_sequence"]),
                "requested_velocity_delta_world_cm_per_s": requested.tolist(),
                "observed_transition_velocity_change_world_cm_per_s": observed_change.tolist(),
                "observed_component_along_request_cm_per_s": observed_along_request,
                "observed_to_requested_component_ratio": (
                    observed_along_request / requested_norm
                ),
                "warning": (
                    "the observed transition change includes ordinary Mover dynamics during "
                    "the same step; it is not a direct measurement of effect application"
                ),
            }
            result["claim_boundary"].extend(
                [
                    "the scheduled perturbation label is evaluation-only and is not a model input",
                    "the event transition is unforeseeable from pre-event state and action alone",
                    "pre-event, event, and post-event errors are reported separately",
                ]
            )
        elif header.get("external_perturbation_schedule") is not None:
            raise ValueError("scheduled schema-v5 episode has no external perturbation row")
    if collision_rows:
        result["collision_metrics"] = {
            field: stats(field, collision_rows) for field in metric_fields
        }
    return result


def _write_plot(rows: list[RowMetrics], path: Path, *, parameter_source: str) -> None:
    times = np.asarray([row.end_simulation_time_s for row in rows])
    position_errors = np.asarray([row.planar_position_error_cm for row in rows])
    velocity_errors = np.asarray([row.planar_velocity_error_cm_s for row in rows])
    yaw_errors = np.asarray([row.yaw_error_deg for row in rows])
    angular_velocity_errors = np.asarray([row.angular_velocity_yaw_error_deg_s for row in rows])
    collision_times = [row.end_simulation_time_s for row in rows if row.collision_this_step]
    perturbation_times = [
        row.end_simulation_time_s for row in rows if row.perturbation_phase == "event"
    ]

    figure, axes = plt.subplots(4, 1, figsize=(9.0, 9.2), sharex=True, constrained_layout=True)
    axes[0].plot(times, position_errors, color="#3366aa", linewidth=1.8)
    axes[0].set_ylabel("Planar position error (cm)")
    axes[0].set_title(
        "Faithful nominal model: causal current-snapshot one-step error"
        if parameter_source == "current-snapshot"
        else "Faithful nominal model: retrospective one-step error"
    )
    axes[1].plot(times, velocity_errors, color="#aa5533", linewidth=1.8)
    axes[1].set_ylabel("Planar velocity error (cm/s)")
    axes[2].plot(times, yaw_errors, color="#6b4c9a", linewidth=1.8)
    axes[2].set_ylabel("Yaw error (deg)")
    axes[3].plot(times, angular_velocity_errors, color="#2f7d61", linewidth=1.8)
    axes[3].set_ylabel("Yaw-rate error\n(deg/s)")
    axes[3].set_xlabel("Unreal simulation time (s)")
    for axis in axes:
        axis.grid(alpha=0.25, linewidth=0.7)
        for collision_time in collision_times:
            axis.axvline(collision_time, color="#333333", linestyle="--", linewidth=1.0)
        for perturbation_time in perturbation_times:
            axis.axvline(perturbation_time, color="#c23b22", linestyle="--", linewidth=1.2)
    if collision_times:
        axes[0].annotate(
            "recorded gate collision",
            xy=(collision_times[0], np.max(position_errors)),
            xytext=(-8, -20),
            textcoords="offset points",
            ha="right",
            fontsize=9,
        )
    if perturbation_times:
        axes[0].annotate(
            "unobserved velocity kick",
            xy=(perturbation_times[0], np.max(position_errors)),
            xytext=(8, -20),
            textcoords="offset points",
            ha="left",
            fontsize=9,
            color="#9c2f1b",
        )
    largest_yaw_index = int(np.argmax(yaw_errors))
    if yaw_errors[largest_yaw_index] > 1.0e-3:
        axes[2].annotate(
            f"max={yaw_errors[largest_yaw_index]:.3f}°",
            xy=(times[largest_yaw_index], yaw_errors[largest_yaw_index]),
            xytext=(8, -18),
            textcoords="offset points",
            fontsize=9,
        )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--effective-max-speed-cm-s", type=float)
    parser.add_argument(
        "--parameter-source",
        choices=("completed-step", "current-snapshot"),
        default="completed-step",
    )
    args = parser.parse_args()

    episode = load_episode(args.episode)
    schema_version = int(episode.header["schema_version"])
    if schema_version not in {3, 4, 5}:
        raise ValueError("faithful nominal evaluation requires episode schema version 3, 4, or 5")
    if schema_version == 3 and args.effective_max_speed_cm_s is None:
        raise ValueError("schema-v3 evaluation requires --effective-max-speed-cm-s")
    if args.parameter_source == "current-snapshot" and schema_version < 4:
        raise ValueError("current-snapshot evaluation requires episode schema version 4 or 5")
    event_indices = [
        index
        for index, transition in enumerate(episode.transitions)
        if schema_version >= 5
        and transition["external_perturbation"]["type"] == "additive_velocity"
    ]
    if len(event_indices) > 1:
        raise ValueError("one-step evaluator supports at most one external perturbation")

    def phase(index: int) -> str:
        if not event_indices:
            return "no_event"
        event_index = event_indices[0]
        if index < event_index:
            return "pre_event"
        if index == event_index:
            return "event"
        return "post_event"

    rows = [
        _metrics(
            transition,
            effective_max_speed_cm_s=args.effective_max_speed_cm_s,
            perturbation_phase=phase(index),
            parameter_source=args.parameter_source,
        )
        for index, transition in enumerate(episode.transitions)
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.output_dir / "one_step_errors.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(asdict(rows[0])),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    summary = _summary(
        args.episode,
        rows,
        effective_max_speed_cm_s=args.effective_max_speed_cm_s,
        schema_version=schema_version,
        header=episode.header,
        transitions=episode.transitions,
        parameter_source=args.parameter_source,
        recorded_input_preparations=[
            (
                transition["nominal_context"]["previous"]["input_preparation"]
                if args.parameter_source == "current-snapshot"
                else transition["nominal_context"][
                    "input_preparation_observed_for_completed_step"
                ]
            )
            for transition in episode.transitions
        ]
        if schema_version >= 4
        else [],
    )
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_plot(
        rows,
        args.output_dir / "one_step_error.png",
        parameter_source=args.parameter_source,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
