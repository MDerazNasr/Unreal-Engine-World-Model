#!/usr/bin/env python3
"""Compare causal fixed planner substeps with retrospective recorded-dt replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from motionworld.data.residual_manifest import AuditedEpisode, audit_residual_dataset
from motionworld.dynamics.coordinates import YawRadians, local_vector_to_world
from motionworld.dynamics.nominal_episode import (
    current_snapshot_nominal_inputs,
    observable_from_state_record,
)
from motionworld.dynamics.smooth_walking_math import find_delta_angle_radians
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
    smooth_walking_nominal_step,
)
from motionworld.planning.cem import project_velocity_actions

CONTROL_INTERVAL_S = 0.1
FIXED_POLICIES = {"fixed_30_hz": (1.0 / 30.0,) * 3, "fixed_60_hz": (1.0 / 60.0,) * 6}
METRICS = (
    "planar_position_error_cm",
    "planar_velocity_error_cm_s",
    "yaw_error_deg",
    "yaw_rate_error_deg_s",
)


@dataclass(frozen=True, slots=True)
class WindowResult:
    episode_id: int
    start_transition_sequence: int
    source_step_count: int
    policy: str
    planar_position_error_cm: float
    planar_velocity_error_cm_s: float
    yaw_error_deg: float
    yaw_rate_error_deg_s: float


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _same_action(left: dict[str, Any], right: dict[str, Any]) -> bool:
    names = ("velocity_local_planar_cm_per_s", "desired_facing_yaw_deg")
    return all(np.array_equal(np.asarray(left[name]), np.asarray(right[name])) for name in names)


def _same_parameters(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left == right


def _interpolate_angle_radians(start: float, end: float, fraction: float) -> float:
    return start + fraction * find_delta_angle_radians(start, end)


def _interpolated_observable(
    transition: dict[str, Any], target_time_s: float
) -> SmoothWalkingObservableState:
    previous = observable_from_state_record(transition["previous_state"])
    following = observable_from_state_record(transition["next_state"])
    fraction = (target_time_s - previous.simulation_time_s) / (
        following.simulation_time_s - previous.simulation_time_s
    )
    if fraction < -1.0e-9 or fraction > 1.0 + 1.0e-9:
        raise ValueError("target time does not lie inside interpolation transition")
    fraction = min(max(fraction, 0.0), 1.0)
    return SmoothWalkingObservableState(
        position_world_cm=(
            previous.position_world_cm
            + fraction * (following.position_world_cm - previous.position_world_cm)
        ),
        velocity_world_cm_s=(
            previous.velocity_world_cm_s
            + fraction * (following.velocity_world_cm_s - previous.velocity_world_cm_s)
        ),
        facing_yaw_rad=_interpolate_angle_radians(
            previous.facing_yaw_rad, following.facing_yaw_rad, fraction
        ),
        angular_velocity_yaw_deg_s=(
            previous.angular_velocity_yaw_deg_s
            + fraction
            * (
                following.angular_velocity_yaw_deg_s
                - previous.angular_velocity_yaw_deg_s
            )
        ),
        simulation_time_s=target_time_s,
    )


def _action_from_local(
    local_velocity_cm_s: np.ndarray,
    observable: SmoothWalkingObservableState,
    maximum_speed_cm_s: float,
) -> SmoothWalkingAction:
    bounded = project_velocity_actions(
        np.asarray(local_velocity_cm_s, dtype=np.float64),
        maximum_speed_cm_s=maximum_speed_cm_s,
    )
    world = local_vector_to_world(bounded, yaw=YawRadians(observable.facing_yaw_rad))
    world_velocity = np.asarray([world[0], world[1], 0.0], dtype=np.float64)
    desired_facing = (
        observable.facing_yaw_rad
        if np.linalg.norm(bounded) <= 1.0e-12
        else math.atan2(float(world[1]), float(world[0]))
    )
    return SmoothWalkingAction(world_velocity, desired_facing)


def _planar_local_action(record: dict[str, Any]) -> np.ndarray:
    value = np.asarray(record["velocity_local_planar_cm_per_s"], dtype=np.float64)
    if value.shape != (3,) or not np.all(np.isfinite(value)) or abs(float(value[2])) > 1.0e-6:
        raise ValueError("recorded local action must be a finite planar Unreal vector")
    return value[:2].copy()


def _rollout_schedule(
    initial_observable: SmoothWalkingObservableState,
    initial_internal: SmoothWalkingInternalState,
    local_action_cm_s: np.ndarray,
    maximum_speed_cm_s: float,
    parameters: Any,
    schedule_s: tuple[float, ...],
) -> SmoothWalkingObservableState:
    observable = initial_observable
    internal = initial_internal
    for dt_s in schedule_s:
        action = _action_from_local(local_action_cm_s, observable, maximum_speed_cm_s)
        prediction = smooth_walking_nominal_step(
            observable,
            internal,
            action,
            parameters=parameters,
            dt_s=dt_s,
        )
        observable = prediction.observable_next
        internal = prediction.internal_next
    return observable


def _recorded_schedule(
    transitions: tuple[dict[str, Any], ...], start_index: int, end_index: int
) -> tuple[float, ...]:
    remaining = CONTROL_INTERVAL_S
    result: list[float] = []
    for transition in transitions[start_index : end_index + 1]:
        dt_s = min(float(transition["delta_time_s"]), remaining)
        result.append(dt_s)
        remaining -= dt_s
        if remaining <= 1.0e-12:
            break
    if remaining > 1.0e-9:
        raise ValueError("recorded schedule does not cover one control interval")
    result[-1] += remaining
    return tuple(result)


def _window_results(episode: AuditedEpisode) -> tuple[WindowResult, ...]:
    transitions = episode.episode.transitions
    results: list[WindowResult] = []
    for start_index, first in enumerate(transitions):
        start_time_s = float(first["previous_state"]["simulation_time_s"])
        target_time_s = start_time_s + CONTROL_INTERVAL_S
        end_index = start_index
        while (
            end_index < len(transitions)
            and float(transitions[end_index]["next_state"]["simulation_time_s"])
            < target_time_s - 1.0e-12
        ):
            end_index += 1
        if end_index >= len(transitions):
            continue
        window = transitions[start_index : end_index + 1]
        first_action = first["applied_action"]
        first_parameters = first["nominal_context"]["previous"]["parameters"]
        if any(not _same_action(row["applied_action"], first_action) for row in window):
            continue
        if any(
            not _same_parameters(
                row["nominal_context"]["previous"]["parameters"], first_parameters
            )
            for row in window
        ):
            continue

        inputs = current_snapshot_nominal_inputs(first)
        preparation = first["nominal_context"]["previous"]["input_preparation"]
        if not preparation["has_max_move_speed"]:
            continue
        maximum_speed = float(preparation["effective_max_speed_cm_per_s"])
        local_action = _planar_local_action(first_action)
        actual = _interpolated_observable(transitions[end_index], target_time_s)
        policies = {
            "recorded_dt_replay": _recorded_schedule(transitions, start_index, end_index),
            **FIXED_POLICIES,
        }
        for policy, schedule in policies.items():
            predicted = _rollout_schedule(
                inputs.observable,
                inputs.internal,
                local_action,
                maximum_speed,
                inputs.parameters,
                schedule,
            )
            results.append(
                WindowResult(
                    episode_id=episode.episode_id,
                    start_transition_sequence=int(first["transition_sequence"]),
                    source_step_count=len(window),
                    policy=policy,
                    planar_position_error_cm=float(
                        np.linalg.norm(
                            predicted.position_world_cm[:2] - actual.position_world_cm[:2]
                        )
                    ),
                    planar_velocity_error_cm_s=float(
                        np.linalg.norm(
                            predicted.velocity_world_cm_s[:2]
                            - actual.velocity_world_cm_s[:2]
                        )
                    ),
                    yaw_error_deg=abs(
                        math.degrees(
                            find_delta_angle_radians(
                                predicted.facing_yaw_rad, actual.facing_yaw_rad
                            )
                        )
                    ),
                    yaw_rate_error_deg_s=abs(
                        predicted.angular_velocity_yaw_deg_s
                        - actual.angular_velocity_yaw_deg_s
                    ),
                )
            )
    return tuple(results)


def _distribution(values: list[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "minimum": float(np.min(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(np.max(array)),
    }


def build_report(dataset: Any) -> tuple[dict[str, Any], tuple[WindowResult, ...]]:
    cadence: dict[str, Any] = {}
    for split in ("train", "validation"):
        values = [
            1000.0 * float(row["delta_time_s"])
            for episode in dataset.episodes_for_split(split)
            for row in episode.episode.transitions
        ]
        cadence[split] = _distribution(values)
    rows = tuple(
        result
        for episode in dataset.episodes_for_split("validation")
        for result in _window_results(episode)
    )
    policy_names = ("recorded_dt_replay", "fixed_30_hz", "fixed_60_hz")
    summaries: dict[str, Any] = {}
    for policy in policy_names:
        selected = [row for row in rows if row.policy == policy]
        summaries[policy] = {
            "window_count": len(selected),
            "metrics": {
                metric: _distribution([float(getattr(row, metric)) for row in selected])
                for metric in METRICS
            },
        }
    report = {
        "schema_name": "motionworld_timestep_policy_audit",
        "schema_version": 1,
        "claim_boundary": (
            "accepted train/validation cadence and interpolated constant-context 100 ms "
            "validation windows; recorded dt is retrospective and not deployable"
        ),
        "control_interval_s": CONTROL_INTERVAL_S,
        "test_files_opened": 0,
        "cadence_ms": cadence,
        "window_filter": {
            "split": "validation",
            "constant_action": True,
            "constant_current_parameters": True,
            "authoritative_endpoint": "linear_interpolation_at_exactly_100_ms",
        },
        "policies": summaries,
    }
    return report, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-plan", type=Path, required=True)
    parser.add_argument("--raw-data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()

    dataset = audit_residual_dataset(args.collection_plan, args.raw_data_root)
    report, rows = build_report(dataset)
    report["git_commit"] = args.git_commit
    report["collection_plan_sha256"] = _sha256(args.collection_plan)
    report["accepted_raw_sha256"] = {
        str(episode.episode_id): episode.raw_sha256 for episode in dataset.episodes
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "result.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "windows.json").write_text(
        json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "timestep_policy_audit=complete "
        f"windows={report['policies']['fixed_30_hz']['window_count']} "
        f"validation_dt_p95_ms={report['cadence_ms']['validation']['p95']:.3f} "
        "test_opened=0"
    )


if __name__ == "__main__":
    main()
