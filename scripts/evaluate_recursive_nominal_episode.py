#!/usr/bin/env python3
"""Evaluate recursive faithful-nominal rollouts at fixed requested durations."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from motionworld.data import load_episode
from motionworld.dynamics.nominal_rollout import evaluate_recursive_nominal_rollouts

METRIC_FIELDS = (
    "planar_position_error_cm",
    "planar_velocity_error_cm_s",
    "yaw_error_deg",
    "angular_velocity_yaw_error_deg_s",
)


def _stats(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }


def _summary(
    rows: tuple[object, ...],
    horizons: tuple[float, ...],
    parameter_policy: str,
) -> dict[str, object]:
    by_horizon: dict[str, object] = {}
    for horizon in horizons:
        selected = [row for row in rows if row.requested_horizon_s == horizon]
        actual = np.asarray([row.actual_horizon_s for row in selected])
        by_horizon[f"{horizon:.1f}"] = {
            "window_count": len(selected),
            "actual_horizon_s": {
                "min": float(np.min(actual)),
                "max": float(np.max(actual)),
            },
            "metrics": {
                field: _stats(np.asarray([getattr(row, field) for row in selected]))
                for field in METRIC_FIELDS
            },
        }
    result = {
        "evaluation": "recursive_open_loop_recorded_actions",
        "parameter_policy": parameter_policy,
        "requested_horizons_s": list(horizons),
        "parameter_semantics": (
            "initial_current_snapshot_held_through_each_imagined_future"
            if parameter_policy == "hold-current"
            else "retrospective_completed_step_snapshots_not_proven_planner_available"
        ),
        "state_reseeding": "initial_endpoint_only_no_intermediate_observation_reseeding",
        "endpoint_policy": "first_recorded_boundary_at_or_after_requested_horizon",
        "by_horizon_s": by_horizon,
    }
    relations = ("pre_event", "event_crossing", "post_event", "no_event")
    result["perturbation_relation_metrics"] = {
        relation: {
            "window_count": len(selected),
            "metrics": {
                field: _stats(np.asarray([getattr(row, field) for row in selected]))
                for field in METRIC_FIELDS
            },
        }
        for relation in relations
        if (selected := [row for row in rows if row.perturbation_relation == relation])
    }
    result["claim_boundary"] = []
    if "event_crossing" in result["perturbation_relation_metrics"]:
        result["claim_boundary"].extend(
            [
                "event-crossing windows contain an unforeseeable evaluation-only intervention",
                "post-event windows re-seed from an observed post-event state only at their start",
                "event-crossing and non-crossing windows must not be averaged into one "
                "causal claim",
            ]
        )
    if parameter_policy == "hold-current":
        result["claim_boundary"].extend(
            [
                "no parameter or input-preparation snapshot after the rollout start is read",
                "holding current parameters is a causal baseline, not a learned regime selector",
            ]
        )
    return result


def _plot(summary: dict[str, object], path: Path) -> None:
    horizon_items = summary["by_horizon_s"]
    horizons = np.asarray([float(value) for value in horizon_items])
    figure, axes = plt.subplots(4, 1, figsize=(8.8, 9.2), sharex=True, constrained_layout=True)
    labels = (
        "Planar position error (cm)",
        "Planar velocity error (cm/s)",
        "Yaw error (deg)",
        "Yaw-rate error (deg/s)",
    )
    colors = ("#3366aa", "#aa5533", "#6b4c9a", "#2f7d61")
    for axis, field, label, color in zip(axes, METRIC_FIELDS, labels, colors, strict=True):
        medians = np.asarray(
            [horizon_items[f"{value:.1f}"]["metrics"][field]["median"] for value in horizons]
        )
        p95 = np.asarray(
            [horizon_items[f"{value:.1f}"]["metrics"][field]["p95"] for value in horizons]
        )
        maxima = np.asarray(
            [horizon_items[f"{value:.1f}"]["metrics"][field]["max"] for value in horizons]
        )
        axis.plot(horizons, medians, marker="o", color=color, label="median")
        axis.plot(horizons, p95, marker="s", linestyle="--", color=color, label="p95")
        axis.plot(horizons, maxima, marker="^", linestyle=":", color=color, label="max")
        axis.set_ylabel(label)
        axis.grid(alpha=0.25)
    axes[0].set_title("Faithful nominal model: recursive open-loop error")
    axes[0].legend(ncol=3, fontsize=9)
    axes[-1].set_xlabel("Requested rollout horizon (s)")
    axes[-1].set_xticks(horizons)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_perturbation_relations(summary: dict[str, object], path: Path) -> None:
    relation_items = summary["perturbation_relation_metrics"]
    order = [
        relation
        for relation in ("pre_event", "event_crossing", "post_event")
        if relation in relation_items
    ]
    if "event_crossing" not in order:
        return

    labels = {
        "pre_event": "Before kick",
        "event_crossing": "Crosses hidden kick",
        "post_event": "After kick observed",
    }
    fields = ("planar_position_error_cm", "planar_velocity_error_cm_s")
    axis_labels = ("p95 endpoint position error (cm)", "p95 endpoint velocity error (cm/s)")
    colors = ("#4c78a8", "#e45756", "#54a24b")
    floor = 1.0e-12
    figure, axes = plt.subplots(1, 2, figsize=(10.2, 4.5), constrained_layout=True)
    for axis, field, axis_label in zip(axes, fields, axis_labels, strict=True):
        actual_values = [
            float(relation_items[item]["metrics"][field]["p95"])
            for item in order
        ]
        values = [max(value, floor) for value in actual_values]
        bars = axis.bar(
            [labels[item] for item in order],
            values,
            color=[
                colors[("pre_event", "event_crossing", "post_event").index(item)]
                for item in order
            ],
        )
        axis.set_yscale("log")
        axis.set_ylabel(axis_label)
        axis.grid(axis="y", alpha=0.25)
        axis.tick_params(axis="x", rotation=12)
        for bar, value, actual_value in zip(bars, values, actual_values, strict=True):
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                value * 1.35,
                f"{actual_value:.3g}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    figure.suptitle("Recursive nominal error, separated by causal relation to the kick")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--horizons", nargs="+", type=float, default=[0.5, 1.0, 1.5])
    parser.add_argument(
        "--parameter-policy",
        choices=("retrospective", "hold-current"),
        default="retrospective",
    )
    args = parser.parse_args()

    episode = load_episode(args.episode)
    if int(episode.header["schema_version"]) not in {4, 5}:
        raise ValueError("recursive evaluator currently requires schema version 4 or 5")
    horizons = tuple(args.horizons)
    rows = evaluate_recursive_nominal_rollouts(
        episode.transitions,
        horizons_s=horizons,
        parameter_policy=args.parameter_policy,
    )
    summary = _summary(rows, tuple(sorted(horizons)), args.parameter_policy)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "recursive_rollouts.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(asdict(rows[0])),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    (args.output_dir / "recursive_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(summary, args.output_dir / "recursive_error.png")
    _plot_perturbation_relations(
        summary,
        args.output_dir / "recursive_perturbation_error.png",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
