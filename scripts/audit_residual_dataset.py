#!/usr/bin/env python3
"""Freeze and visualize the accepted residual train/validation dataset boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from motionworld.data.residual_coverage import build_residual_coverage_report
from motionworld.data.residual_manifest import audit_residual_dataset


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_plot(coverage: dict[str, object], path: Path) -> None:
    splits = coverage["splits"]
    train = splits["train"]
    validation = splits["validation"]
    colors = {"train": "#3366aa", "validation": "#dd7f2a"}
    figure, axes = plt.subplots(2, 2, figsize=(11.0, 7.6), constrained_layout=True)

    labels = ("forward", "reverse", "right", "left", "diagonal", "stop")
    x = np.arange(len(labels))
    width = 0.38
    axes[0, 0].bar(
        x - width / 2,
        [train["action_direction_counts"][label] for label in labels],
        width,
        color=colors["train"],
        label="train",
    )
    axes[0, 0].bar(
        x + width / 2,
        [validation["action_direction_counts"][label] for label in labels],
        width,
        color=colors["validation"],
        label="validation",
    )
    axes[0, 0].set_xticks(x, labels, rotation=25, ha="right")
    axes[0, 0].set_ylabel("Transitions")
    axes[0, 0].set_title("Requested action coverage")
    axes[0, 0].legend()

    for split_name, summary in (("train", train), ("validation", validation)):
        histogram = summary["actual_speed_histogram_cm_s"]
        edges = np.asarray(histogram["bin_edges"])
        counts = np.asarray(histogram["counts"])
        axes[0, 1].stairs(
            counts,
            edges,
            color=colors[split_name],
            linewidth=2.0,
            label=split_name,
        )
    axes[0, 1].set_xlabel("Actual planar speed (cm/s)")
    axes[0, 1].set_ylabel("Transitions")
    axes[0, 1].set_title("Executed-speed coverage")
    axes[0, 1].legend()

    for split_name, summary in (("train", train), ("validation", validation)):
        histogram = summary["delta_time_histogram_ms"]
        edges = np.asarray(histogram["bin_edges"])
        counts = np.asarray(histogram["counts"])
        axes[1, 0].stairs(
            counts,
            edges,
            color=colors[split_name],
            linewidth=2.0,
            label=split_name,
        )
    axes[1, 0].set_xlabel("Recorded timestep (ms)")
    axes[1, 0].set_ylabel("Transitions")
    axes[1, 0].set_title("Variable-timestep coverage")
    axes[1, 0].legend()

    group_labels = ("parameter stable", "parameter change")
    train_targets = train["residual_targets"]
    validation_targets = validation["residual_targets"]
    train_values = (
        train_targets["parameter_stable"]["magnitude_p95"]["planar_position_cm"],
        train_targets["parameter_change"]["magnitude_p95"]["planar_position_cm"],
    )
    validation_values = (
        validation_targets["parameter_stable"]["magnitude_p95"]["planar_position_cm"],
        validation_targets["parameter_change"]["magnitude_p95"]["planar_position_cm"],
    )
    group_x = np.arange(len(group_labels))
    axes[1, 1].bar(
        group_x - width / 2,
        train_values,
        width,
        color=colors["train"],
        label="train",
    )
    axes[1, 1].bar(
        group_x + width / 2,
        validation_values,
        width,
        color=colors["validation"],
        label="validation",
    )
    axes[1, 1].set_xticks(group_x, group_labels)
    axes[1, 1].set_ylabel("Residual planar position p95 (cm)")
    axes[1, 1].set_title("Causal residual is concentrated at regime changes")
    axes[1, 1].legend()

    for axis in axes.flat:
        axis.grid(axis="y", alpha=0.25, linewidth=0.7)
    figure.suptitle("MotionWorld accepted train/validation coverage", fontsize=15)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_markdown(
    path: Path,
    manifest: dict[str, object],
    coverage: dict[str, object],
) -> None:
    totals = manifest["split_totals"]
    lines = [
        "# Accepted residual dataset audit",
        "",
        "This report freezes the seven accepted train/validation files. The audit does not glob or "
        "open pending test files.",
        "",
        "| Split | Episodes | Transitions | No history | Four history |",
        "|---|---:|---:|---:|---:|",
    ]
    for split in ("train", "validation"):
        row = totals[split]
        lines.append(
            f"| {split} | {row['episode_count']} | {row['transition_count']} | "
            f"{row['no_history_example_count']} | {row['four_history_example_count']} |"
        )
    lines.extend(
        [
            "",
            "## Accepted files",
            "",
            "| Episode | Split | Rows | File | SHA-256 |",
            "|---:|---|---:|---|---|",
        ]
    )
    for row in manifest["episodes"]:
        lines.append(
            f"| {row['episode_id']} | {row['split']} | {row['transition_count']} | "
            f"`{row['raw_file']}` | `{row['raw_sha256']}` |"
        )
    lines.extend(["", "## Coverage", ""])
    for split in ("train", "validation"):
        row = coverage["splits"][split]
        directions = row["action_direction_counts"]
        lines.extend(
            [
                f"### {split.title()}",
                "",
                f"- Requested directions: {directions}.",
                f"- Turning transitions: "
                f"{row['turning_transition_count_yaw_delta_gt_0_1_deg']}.",
                f"- Parameter-change transitions: {row['parameter_change_transition_count']}.",
                f"- Actual speed median/p95/max: {row['actual_planar_speed_cm_s']['median']:.3f} / "
                f"{row['actual_planar_speed_cm_s']['p95']:.3f} / "
                f"{row['actual_planar_speed_cm_s']['max']:.3f} cm/s.",
                f"- Timestep median/p95/max: {row['delta_time_ms']['median']:.3f} / "
                f"{row['delta_time_ms']['p95']:.3f} / {row['delta_time_ms']['max']:.3f} ms.",
                f"- Collision transitions: {row['collision_transition_count']}; external-event "
                f"transitions: {row['external_perturbation_transition_count']}.",
                "",
            ]
        )
    lines.extend(["## Known limitations", ""])
    lines.extend(f"- {item}" for item in coverage["known_coverage_gaps"])
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            ".venv/bin/python scripts/audit_residual_dataset.py \\",
            "  --raw-data-root \"/path/to/GameAnimationSample/Saved/MotionWorld/Episodes\" \\",
            "  --output-dir artifacts/residual/dataset_audit",
            "```",
            "",
            "## Scientific boundary",
            "",
            "Normalization and model weights may use the training split only. Validation may "
            "compare predeclared model variants and checkpoints. Test episodes remain uncollected "
            "and are "
            "reserved for one final evaluation.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("configs/residual_collection_plan.yaml"))
    parser.add_argument("--raw-data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    dataset = audit_residual_dataset(args.plan, args.raw_data_root)
    manifest = dataset.manifest_dict()
    coverage = build_residual_coverage_report(dataset)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "manifest.json": args.output_dir / "manifest.json",
        "coverage.json": args.output_dir / "coverage.json",
        "coverage.png": args.output_dir / "coverage.png",
        "README.md": args.output_dir / "README.md",
    }
    _write_json(paths["manifest.json"], manifest)
    _write_json(paths["coverage.json"], coverage)
    _write_plot(coverage, paths["coverage.png"])
    _write_markdown(paths["README.md"], manifest, coverage)
    hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()
    }
    _write_json(args.output_dir / "artifact_hashes.json", hashes)

    print(
        "audit=valid "
        f"train={manifest['split_totals']['train']['transition_count']} "
        f"validation={manifest['split_totals']['validation']['transition_count']} "
        "test_opened=0"
    )


if __name__ == "__main__":
    main()
