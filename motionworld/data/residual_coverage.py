"""Deterministic coverage summaries for an audited residual dataset."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence

import numpy as np

from motionworld.data.residual_manifest import AuditedEpisode, AuditedResidualDataset
from motionworld.models.residual_contract import RESIDUAL_OUTPUT_NAMES
from motionworld.models.residual_dataset import build_residual_examples

RESIDUAL_COVERAGE_SCHEMA_VERSION = 1
_ACTION_SPEED_BINS_CM_S = (0.0, 1.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0, 250.0)
_STATE_SPEED_BINS_CM_S = (0.0, 1.0, 25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 175.0)
_DT_BINS_MS = (0.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 80.0, 200.0)


def _percentiles(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return {"min": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "min": float(np.min(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "max": float(np.max(array)),
    }


def _histogram(values: Sequence[float], bins: Sequence[float]) -> dict[str, object]:
    counts, edges = np.histogram(np.asarray(values, dtype=np.float64), bins=np.asarray(bins))
    return {"bin_edges": edges.tolist(), "counts": counts.astype(int).tolist()}


def _action_label(vector: Sequence[float], tolerance: float = 1.0e-6) -> str:
    x, y = float(vector[0]), float(vector[1])
    if math.hypot(x, y) <= tolerance:
        return "stop"
    if x > tolerance and abs(y) <= tolerance:
        return "forward"
    if x < -tolerance and abs(y) <= tolerance:
        return "reverse"
    if y > tolerance and abs(x) <= tolerance:
        return "right"
    if y < -tolerance and abs(x) <= tolerance:
        return "left"
    if x > tolerance and y > tolerance:
        return "diagonal"
    return "other"


def _parameters_changed(transition: dict[str, object]) -> bool:
    context = transition["nominal_context"]
    return bool(
        context["previous"]["parameters"]
        != context["parameters_observed_for_completed_step"]
        or context["previous"]["input_preparation"]
        != context["input_preparation_observed_for_completed_step"]
    )


def _wrapped_yaw_delta_degrees(previous: float, next_value: float) -> float:
    return abs((float(next_value) - float(previous) + 180.0) % 360.0 - 180.0)


def _target_summary(episodes: Iterable[AuditedEpisode]) -> dict[str, object]:
    targets: list[np.ndarray] = []
    change_targets: list[np.ndarray] = []
    stable_targets: list[np.ndarray] = []
    for item in episodes:
        changed_by_sequence = {
            int(row["transition_sequence"]): _parameters_changed(row)
            for row in item.episode.transitions
        }
        for example in build_residual_examples(item.episode, history_length=1):
            target = np.asarray(example.target, dtype=np.float64)
            targets.append(target)
            destination = (
                change_targets
                if changed_by_sequence[example.transition_sequence]
                else stable_targets
            )
            destination.append(target)

    def group(rows: list[np.ndarray]) -> dict[str, object]:
        if not rows:
            return {"count": 0, "absolute_component_p95": {}, "magnitude_p95": {}}
        values = np.stack(rows)
        position = np.linalg.norm(values[:, 0:2], axis=1)
        velocity = np.linalg.norm(values[:, 2:4], axis=1)
        yaw_deg = np.abs(np.degrees(values[:, 4]))
        yaw_rate_deg_s = np.abs(np.degrees(values[:, 5]))
        return {
            "count": len(rows),
            "absolute_component_p95": {
                name: float(np.percentile(np.abs(values[:, index]), 95))
                for index, name in enumerate(RESIDUAL_OUTPUT_NAMES)
            },
            "magnitude_p95": {
                "planar_position_cm": float(np.percentile(position, 95)),
                "planar_velocity_cm_s": float(np.percentile(velocity, 95)),
                "yaw_deg": float(np.percentile(yaw_deg, 95)),
                "yaw_rate_deg_s": float(np.percentile(yaw_rate_deg_s, 95)),
            },
            "material_count": {
                "planar_position_gt_0_001_cm": int(np.sum(position > 0.001)),
                "planar_velocity_gt_0_01_cm_s": int(np.sum(velocity > 0.01)),
                "yaw_gt_0_1_deg": int(np.sum(yaw_deg > 0.1)),
                "yaw_rate_gt_1_deg_s": int(np.sum(yaw_rate_deg_s > 1.0)),
            },
        }

    return {
        "all": group(targets),
        "parameter_change": group(change_targets),
        "parameter_stable": group(stable_targets),
    }


def _split_coverage(episodes: tuple[AuditedEpisode, ...]) -> dict[str, object]:
    action_counts: Counter[str] = Counter()
    movement_modes: Counter[str] = Counter()
    action_speeds: list[float] = []
    state_speeds: list[float] = []
    dt_ms: list[float] = []
    yaw_deltas: list[float] = []
    parameter_changes = 0
    collisions = 0
    external_events = 0
    parameter_values: dict[str, set[float | bool]] = {}
    parameter_signatures: set[tuple[tuple[str, float | bool], ...]] = set()
    for item in episodes:
        for transition in item.episode.transitions:
            action = transition["applied_action"]["velocity_world_cm_per_s"]
            next_state = transition["next_state"]
            next_velocity = next_state["velocity_world_cm_per_s"]
            action_counts[_action_label(action)] += 1
            movement_modes[str(next_state["movement_mode"])] += 1
            action_speeds.append(math.hypot(float(action[0]), float(action[1])))
            state_speeds.append(math.hypot(float(next_velocity[0]), float(next_velocity[1])))
            dt_ms.append(1000.0 * float(transition["delta_time_s"]))
            yaw_deltas.append(
                _wrapped_yaw_delta_degrees(
                    transition["previous_state"]["facing_yaw_deg"],
                    next_state["facing_yaw_deg"],
                )
            )
            parameter_changes += int(_parameters_changed(transition))
            parameters = transition["nominal_context"]["previous"]["parameters"]
            signature: list[tuple[str, float | bool]] = []
            for name in sorted(parameters):
                value = parameters[name]
                normalized = value if isinstance(value, bool) else float(value)
                parameter_values.setdefault(name, set()).add(normalized)
                signature.append((name, normalized))
            parameter_signatures.add(tuple(signature))
            scenario = transition.get("scenario")
            collisions += int(
                isinstance(scenario, dict) and bool(scenario["collision_this_step"])
            )
            external = transition.get("external_perturbation")
            external_events += int(
                isinstance(external, dict) and external.get("type") != "none"
            )

    ordered_labels = ("forward", "reverse", "right", "left", "diagonal", "stop", "other")
    return {
        "episode_count": len(episodes),
        "transition_count": sum(item.transition_count for item in episodes),
        "no_history_example_count": sum(item.no_history_example_count for item in episodes),
        "four_history_example_count": sum(item.four_history_example_count for item in episodes),
        "action_direction_counts": {label: action_counts[label] for label in ordered_labels},
        "movement_mode_counts": dict(sorted(movement_modes.items())),
        "turning_transition_count_yaw_delta_gt_0_1_deg": int(
            np.sum(np.asarray(yaw_deltas) > 0.1)
        ),
        "parameter_change_transition_count": parameter_changes,
        "causal_parameter_signature_count": len(parameter_signatures),
        "causal_parameter_value_coverage": {
            name: {"unique_values": sorted(values), "unique_count": len(values)}
            for name, values in sorted(parameter_values.items())
        },
        "collision_transition_count": collisions,
        "external_perturbation_transition_count": external_events,
        "action_speed_cm_s": _percentiles(action_speeds),
        "actual_planar_speed_cm_s": _percentiles(state_speeds),
        "delta_time_ms": _percentiles(dt_ms),
        "action_speed_histogram_cm_s": _histogram(action_speeds, _ACTION_SPEED_BINS_CM_S),
        "actual_speed_histogram_cm_s": _histogram(state_speeds, _STATE_SPEED_BINS_CM_S),
        "delta_time_histogram_ms": _histogram(dt_ms, _DT_BINS_MS),
        "residual_targets": _target_summary(episodes),
    }


def build_residual_coverage_report(dataset: AuditedResidualDataset) -> dict[str, object]:
    """Summarize train/validation coverage without consulting pending test files."""

    training = dataset.episodes_for_split("train")
    validation = dataset.episodes_for_split("validation")
    train_signatures = {
        tuple(item.configuration[name] for name in sorted(item.configuration))
        for item in training
    }
    validation_signature_novelty = {
        str(item.episode_id): (
            tuple(item.configuration[name] for name in sorted(item.configuration))
            not in train_signatures
        )
        for item in validation
    }
    return {
        "schema_name": "motionworld_residual_dataset_coverage",
        "schema_version": RESIDUAL_COVERAGE_SCHEMA_VERSION,
        "source_plan_sha256": dataset.plan_sha256,
        "splits": {
            "train": _split_coverage(training),
            "validation": _split_coverage(validation),
        },
        "validation_configuration_is_not_exact_train_duplicate": validation_signature_novelty,
        "known_coverage_gaps": [
            "accepted train/validation episodes contain no collision transitions",
            "accepted train/validation episodes contain no external perturbation transitions",
            "only one deterministic eight-phase action family is represented",
            "final test episodes remain uncollected and unopened",
        ],
        "claim_boundary": [
            "coverage describes seven accepted scripted free-space episodes, not all gameplay",
            "zero contact/event counts are reported rather than hidden",
            "validation schedules are episode-disjoint and exact-configuration novel",
            "no validation value may fit normalization or model weights",
        ],
    }
