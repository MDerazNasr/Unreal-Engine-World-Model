#!/usr/bin/env python3
"""Compare nominal and learned residual models in teacher-forcing-free rollouts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from motionworld.data.residual_manifest import audit_residual_dataset
from motionworld.dynamics.nominal_rollout import evaluate_recursive_nominal_rollouts
from motionworld.models.residual_rollout import evaluate_recursive_residual_rollouts
from motionworld.models.residual_training import load_residual_checkpoint


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _distribution(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        raise ValueError("recursive metric stratum is empty")
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "max": float(np.max(array)),
    }


def _summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    metrics = (
        "planar_position_error_cm",
        "planar_velocity_error_cm_s",
        "yaw_error_deg",
        "angular_velocity_yaw_error_deg_s",
    )
    result = {}
    for horizon in (0.5, 1.0, 1.5):
        horizon_rows = [row for row in rows if row["requested_horizon_s"] == horizon]
        crossing_rows = [row for row in horizon_rows if row["parameter_change_count"] > 0]
        stable_rows = [row for row in horizon_rows if row["parameter_change_count"] == 0]
        result[str(horizon)] = {
            "all": {
                "window_count": len(horizon_rows),
                "metrics": {
                    metric: _distribution([float(row[metric]) for row in horizon_rows])
                    for metric in metrics
                },
            },
            "parameter_change_crossing": {
                "window_count": len(crossing_rows),
                "metrics": {
                    metric: _distribution([float(row[metric]) for row in crossing_rows])
                    for metric in metrics
                },
            },
            "parameter_stable": {
                "window_count": len(stable_rows),
                "metrics": {
                    metric: _distribution([float(row[metric]) for row in stable_rows])
                    for metric in metrics
                },
            },
        }
    return result


def _key(episode_id: int, row: object) -> tuple[int, int, int, float]:
    return (
        episode_id,
        row.start_transition_sequence,
        row.end_transition_sequence,
        row.requested_horizon_s,
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = tuple(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_plot(summary: dict[str, object], path: Path) -> None:
    metrics = (
        ("planar_position_error_cm", "Position p95 (cm)"),
        ("planar_velocity_error_cm_s", "Velocity p95 (cm/s)"),
        ("yaw_error_deg", "Yaw p95 (deg)"),
        ("angular_velocity_yaw_error_deg_s", "Yaw-rate p95 (deg/s)"),
    )
    colors = {"nominal": "#777777", "no_history": "#3366aa", "four_history": "#dd7f2a"}
    horizons = (0.5, 1.0, 1.5)
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 7.4), constrained_layout=True)
    for axis, (metric, title) in zip(axes.flat, metrics, strict=True):
        for model_name in ("nominal", "no_history", "four_history"):
            all_values = [
                summary[model_name][str(horizon)]["all"]["metrics"][metric]["p95"]
                for horizon in horizons
            ]
            crossing_values = [
                summary[model_name][str(horizon)]["parameter_change_crossing"]["metrics"][
                    metric
                ]["p95"]
                for horizon in horizons
            ]
            axis.plot(
                horizons,
                all_values,
                color=colors[model_name],
                marker="o",
                linewidth=2.0,
                label=model_name.replace("_", " "),
            )
            axis.plot(
                horizons,
                crossing_values,
                color=colors[model_name],
                linestyle="--",
                marker="x",
                alpha=0.75,
            )
        axis.set_title(title)
        axis.set_xlabel("Requested horizon (s)")
        axis.grid(alpha=0.25)
    axes[0, 0].legend()
    figure.suptitle(
        "Held-out recursive validation: solid=all, dashed=parameter-change crossing",
        fontsize=13,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_readme(path: Path, summary: dict[str, object]) -> None:
    lines = [
        "# Recursive residual evaluation 001",
        "",
        "Every rollout starts from one real current snapshot, then advances predicted state and "
        "nominal hidden state without intermediate teacher forcing. Recorded future actions and "
        "timesteps define the query; initial parameters are held for the imagined future.",
        "",
        "## All common validation windows: p95",
        "",
        "| Horizon | Model | Position (cm) | Velocity (cm/s) | Yaw (deg) | Yaw rate (deg/s) |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for horizon in (0.5, 1.0, 1.5):
        for model_name in ("nominal", "no_history", "four_history"):
            metrics = summary[model_name][str(horizon)]["all"]["metrics"]
            lines.append(
                f"| {horizon:.1f} | {model_name.replace('_', ' ')} | "
                f"{metrics['planar_position_error_cm']['p95']:.6g} | "
                f"{metrics['planar_velocity_error_cm_s']['p95']:.6g} | "
                f"{metrics['yaw_error_deg']['p95']:.6g} | "
                f"{metrics['angular_velocity_yaw_error_deg_s']['p95']:.6g} |"
            )
    lines.extend(
        [
            "",
            "Dashed lines in the plot show windows that cross a parameter-regime change. Stable "
            "windows and every raw endpoint remain available in JSON/CSV. Test episodes were not "
            "opened.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-plan", type=Path, required=True)
    parser.add_argument("--raw-data-root", type=Path, required=True)
    parser.add_argument("--training-comparison", type=Path, required=True)
    parser.add_argument("--no-history-checkpoint", type=Path, required=True)
    parser.add_argument("--four-history-checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()

    training_comparison = json.loads(args.training_comparison.read_text(encoding="utf-8"))
    checkpoint_paths = {
        "no_history": args.no_history_checkpoint,
        "four_history": args.four_history_checkpoint,
    }
    checkpoints = {
        name: load_residual_checkpoint(str(path)) for name, path in checkpoint_paths.items()
    }
    for name, path in checkpoint_paths.items():
        if _sha256(path) != training_comparison["checkpoint_sha256"][name]:
            raise ValueError(f"{name} checkpoint hash differs from training comparison")
    if checkpoints["no_history"].history_length != 1:
        raise ValueError("no-history checkpoint has wrong history length")
    if checkpoints["four_history"].history_length != 4:
        raise ValueError("four-history checkpoint has wrong history length")
    if checkpoints["no_history"].dataset_manifest_sha256 != (
        checkpoints["four_history"].dataset_manifest_sha256
    ):
        raise ValueError("checkpoint dataset manifests differ")

    dataset = audit_residual_dataset(args.collection_plan, args.raw_data_root)
    all_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for audited in dataset.episodes_for_split("validation"):
        transitions = list(audited.episode.transitions)
        nominal = evaluate_recursive_nominal_rollouts(
            transitions,
            horizons_s=(0.5, 1.0, 1.5),
            parameter_policy="hold-current",
        )
        residual_by_model = {
            name: evaluate_recursive_residual_rollouts(
                transitions,
                model=checkpoint.model,
                normalization=checkpoint.normalization,
                history_length=checkpoint.history_length,
                horizons_s=(0.5, 1.0, 1.5),
            )
            for name, checkpoint in checkpoints.items()
        }
        common_keys = {_key(audited.episode_id, row) for row in residual_by_model["four_history"]}
        selected = {
            "nominal": [row for row in nominal if _key(audited.episode_id, row) in common_keys],
            "no_history": [
                row
                for row in residual_by_model["no_history"]
                if _key(audited.episode_id, row) in common_keys
            ],
            "four_history": list(residual_by_model["four_history"]),
        }
        expected_keys = [_key(audited.episode_id, row) for row in selected["four_history"]]
        for name, rows in selected.items():
            if [_key(audited.episode_id, row) for row in rows] != expected_keys:
                raise ValueError(f"{name} recursive rows do not share identical endpoints")
            for row in rows:
                record = asdict(row)
                record["model"] = name
                record["episode_id"] = audited.episode_id
                all_rows[name].append(record)

    summary = {name: _summarize(rows) for name, rows in all_rows.items()}
    result = {
        "schema_name": "motionworld_recursive_residual_comparison",
        "schema_version": 1,
        "git_commit": args.git_commit,
        "training_comparison_sha256": _sha256(args.training_comparison),
        "checkpoint_sha256": {name: _sha256(path) for name, path in checkpoint_paths.items()},
        "test_files_opened": 0,
        "common_start_policy": "four_history_eligible_starts_and_identical_endpoints",
        "parameter_policy": "hold_initial_current_snapshot_through_imagined_future",
        "teacher_forcing": False,
        "summary": summary,
        "claim_boundary": [
            "recorded future actions and variable timesteps define the evaluation query",
            "no observed intermediate state or hidden state re-seeds a rollout",
            "four-history seeds three past observed queries then appends predicted queries",
            "the learned correction updates observable state; nominal hidden state advances",
            "test episodes 5301/5302 remain uncollected and unopened",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_dir / "recursive_comparison.json", result)
    csv_rows = [row for name in ("nominal", "no_history", "four_history") for row in all_rows[name]]
    _write_csv(args.output_dir / "recursive_rollouts.csv", csv_rows)
    _write_plot(summary, args.output_dir / "recursive_comparison.png")
    _write_readme(args.output_dir / "README.md", summary)
    paths = [
        args.output_dir / "recursive_comparison.json",
        args.output_dir / "recursive_rollouts.csv",
        args.output_dir / "recursive_comparison.png",
        args.output_dir / "README.md",
    ]
    _write_json(
        args.output_dir / "artifact_hashes.json",
        {path.name: _sha256(path) for path in paths},
    )
    print(
        "recursive=complete teacher_forcing=false common_endpoints=true test_opened=0 "
        f"windows_per_model={len(all_rows['nominal'])}"
    )


if __name__ == "__main__":
    main()
