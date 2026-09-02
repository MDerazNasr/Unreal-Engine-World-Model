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


def _summary(rows: tuple[object, ...], horizons: tuple[float, ...]) -> dict[str, object]:
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
    return {
        "evaluation": "recursive_open_loop_recorded_actions",
        "requested_horizons_s": list(horizons),
        "parameter_semantics": (
            "retrospective_completed_step_snapshots_not_proven_planner_available"
        ),
        "state_reseeding": "initial_endpoint_only_no_intermediate_observation_reseeding",
        "endpoint_policy": "first_recorded_boundary_at_or_after_requested_horizon",
        "by_horizon_s": by_horizon,
    }


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--horizons", nargs="+", type=float, default=[0.5, 1.0, 1.5])
    args = parser.parse_args()

    episode = load_episode(args.episode)
    if int(episode.header["schema_version"]) != 4:
        raise ValueError("recursive evaluator currently requires schema version 4")
    horizons = tuple(args.horizons)
    rows = evaluate_recursive_nominal_rollouts(
        episode.transitions,
        horizons_s=horizons,
    )
    summary = _summary(rows, tuple(sorted(horizons)))
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
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
