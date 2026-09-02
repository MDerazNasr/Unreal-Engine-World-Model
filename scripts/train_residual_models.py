#!/usr/bin/env python3
"""Train and compare the frozen no-history and four-history residual baselines."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np
import torch
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from motionworld.data.residual_manifest import audit_residual_dataset
from motionworld.models.residual_dataset import build_residual_dataset
from motionworld.models.residual_normalization import fit_residual_normalization
from motionworld.models.residual_training import (
    ResidualOptimizerConfig,
    predict_physical_residuals,
    summarize_physical_residual_error,
    train_residual_model,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_config(path: Path, *, dataset_manifest_path: Path) -> dict[str, object]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("training config must be a mapping")
    if config.get("schema_name") != "motionworld_residual_training_config":
        raise ValueError("unexpected residual training config schema")
    if config.get("schema_version") != 1 or config.get("frozen_before_training") is not True:
        raise ValueError("training config must be version 1 and frozen before training")
    if config.get("source_dataset_manifest_sha256") != _sha256(dataset_manifest_path):
        raise ValueError("training config does not match the frozen dataset manifest bytes")
    reproducibility = config.get("reproducibility")
    if not isinstance(reproducibility, dict):
        raise ValueError("training config reproducibility must be a mapping")
    if reproducibility.get("device") != "cpu" or reproducibility.get("dtype") != "float32":
        raise ValueError("first frozen experiment requires deterministic CPU float32")
    evaluation = config.get("evaluation")
    if not isinstance(evaluation, dict) or evaluation.get("test_policy") != (
        "do_not_collect_or_open_during_training_or_model_selection"
    ):
        raise ValueError("training config must seal test data")
    return config


def _parameters_changed(transition: dict[str, object]) -> bool:
    context = transition["nominal_context"]
    return bool(
        context["previous"]["parameters"]
        != context["parameters_observed_for_completed_step"]
        or context["previous"]["input_preparation"]
        != context["input_preparation_observed_for_completed_step"]
    )


def _example_key(example) -> tuple[int, int]:
    return (example.episode_id, example.transition_sequence)


def _matrix(examples, field: str) -> np.ndarray:
    return np.stack([getattr(example, field) for example in examples])


def _subset_summary(targets: np.ndarray, predictions: np.ndarray, mask: np.ndarray):
    if not np.any(mask):
        raise ValueError("evaluation stratum is empty")
    return summarize_physical_residual_error(targets[mask], predictions[mask])


def _write_trace(path: Path, trace) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "optimizer_step",
                "total_loss",
                "huber_loss",
                "residual_magnitude_loss",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        for row in trace:
            writer.writerow(
                {
                    "optimizer_step": row.optimizer_step,
                    "total_loss": row.total_loss,
                    "huber_loss": row.huber_loss,
                    "residual_magnitude_loss": row.residual_magnitude_loss,
                }
            )


def _write_learning_plot(traces: dict[str, tuple], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), constrained_layout=True)
    colors = {"no_history": "#3366aa", "four_history": "#dd7f2a"}
    for name, trace in traces.items():
        steps = [row.optimizer_step for row in trace]
        axes[0].plot(
            steps,
            [row.huber_loss for row in trace],
            label=name.replace("_", " "),
            color=colors[name],
            linewidth=1.8,
        )
        axes[1].plot(
            steps,
            [row.residual_magnitude_loss for row in trace],
            label=name.replace("_", " "),
            color=colors[name],
            linewidth=1.8,
        )
    axes[0].set_title("Training-only normalized Huber loss")
    axes[0].set_ylabel("Mean loss")
    axes[1].set_title("Training-only correction magnitude")
    for axis in axes:
        axis.set_xlabel("Optimizer step")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_validation_plot(comparison: dict[str, object], path: Path) -> None:
    metrics = (
        ("planar_position_cm", "Position p95 (cm)"),
        ("planar_velocity_cm_s", "Velocity p95 (cm/s)"),
        ("yaw_deg", "Yaw p95 (deg)"),
        ("yaw_rate_deg_s", "Yaw-rate p95 (deg/s)"),
    )
    names = ("nominal", "no_history", "four_history")
    colors = ("#777777", "#3366aa", "#dd7f2a")
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 7.4), constrained_layout=True)
    for axis, (metric, title) in zip(axes.flat, metrics, strict=True):
        all_values = [
            comparison["common_validation"][name]["all"]["state_error"][metric]["p95"]
            for name in names
        ]
        change_values = [
            comparison["common_validation"][name]["parameter_change"]["state_error"][metric][
                "p95"
            ]
            for name in names
        ]
        x = np.arange(len(names))
        width = 0.36
        axis.bar(x - width / 2, all_values, width, color=colors, alpha=0.65, label="all")
        axis.bar(x + width / 2, change_values, width, color=colors, label="parameter change")
        axis.set_xticks(x, [name.replace("_", " ") for name in names], rotation=15)
        axis.set_title(title)
        axis.grid(axis="y", alpha=0.25)
        axis.legend(fontsize=8)
    figure.suptitle("Held-out validation: identical common rows", fontsize=14)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_residual_trace_plot(
    targets: np.ndarray,
    predictions: dict[str, np.ndarray],
    change_mask: np.ndarray,
    path: Path,
) -> None:
    indices = np.arange(len(targets))
    figure, axes = plt.subplots(2, 1, figsize=(11.0, 6.2), sharex=True, constrained_layout=True)
    axes[0].plot(indices, np.degrees(targets[:, 4]), color="#222222", label="target", linewidth=1.4)
    axes[1].plot(indices, np.degrees(targets[:, 5]), color="#222222", label="target", linewidth=1.4)
    for name, values, color in (
        ("no history", predictions["no_history"], "#3366aa"),
        ("four history", predictions["four_history"], "#dd7f2a"),
    ):
        axes[0].plot(indices, np.degrees(values[:, 4]), color=color, label=name, alpha=0.85)
        axes[1].plot(indices, np.degrees(values[:, 5]), color=color, label=name, alpha=0.85)
    for axis in axes:
        for index in indices[change_mask]:
            axis.axvline(index, color="#999999", alpha=0.12, linewidth=0.7)
        axis.grid(alpha=0.2)
        axis.legend(ncol=3)
    axes[0].set_ylabel("Yaw residual (deg)")
    axes[0].set_title("Held-out residual targets and predictions; gray lines are regime changes")
    axes[1].set_ylabel("Yaw-rate residual (deg/s)")
    axes[1].set_xlabel("Common validation example index")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _write_readme(path: Path, comparison: dict[str, object]) -> None:
    common = comparison["common_validation"]
    lines = [
        "# Residual training experiment 001",
        "",
        "Both MLPs use the frozen architecture, train-only normalization, identical fixed "
        "optimizer budgets, and no validation early stopping. Test episodes were not opened.",
        "",
        "## Common held-out validation rows",
        "",
        "| Model | Position p95 (cm) | Velocity p95 (cm/s) | Yaw p95 (deg) | "
        "Yaw-rate p95 (deg/s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("nominal", "no_history", "four_history"):
        state = common[name]["all"]["state_error"]
        lines.append(
            f"| {name.replace('_', ' ')} | {state['planar_position_cm']['p95']:.6g} | "
            f"{state['planar_velocity_cm_s']['p95']:.6g} | {state['yaw_deg']['p95']:.6g} | "
            f"{state['yaw_rate_deg_s']['p95']:.6g} |"
        )
    lines.extend(
        [
            "",
            "These are one-step results. Recursive 0.5/1.0/1.5-second evaluation remains a "
            "separate gate and must not be inferred from this table.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-plan", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--training-config", type=Path, required=True)
    parser.add_argument("--raw-data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()

    config = _load_config(args.training_config, dataset_manifest_path=args.dataset_manifest)
    dataset = audit_residual_dataset(args.collection_plan, args.raw_data_root)
    manifest = dataset.manifest_dict()
    expected_train_ids = tuple(int(value) for value in config["train_episode_ids"])
    expected_validation_ids = tuple(int(value) for value in config["validation_episode_ids"])
    actual_train_ids = tuple(item.episode_id for item in dataset.episodes_for_split("train"))
    actual_validation_ids = tuple(
        item.episode_id for item in dataset.episodes_for_split("validation")
    )
    if actual_train_ids != expected_train_ids or actual_validation_ids != expected_validation_ids:
        raise ValueError("training config split IDs differ from the audited dataset")
    if manifest != json.loads(args.dataset_manifest.read_text(encoding="utf-8")):
        raise ValueError("reconstructed dataset does not equal the frozen manifest")

    optimizer_values = config["optimizer"]
    loss_values = config["loss"]
    reproducibility = config["reproducibility"]
    optimizer_config = ResidualOptimizerConfig(
        optimizer_steps=int(optimizer_values["optimizer_steps"]),
        batch_size=int(optimizer_values["batch_size"]),
        learning_rate=float(optimizer_values["learning_rate"]),
        weight_decay=float(optimizer_values["weight_decay"]),
        huber_beta=float(loss_values["huber_beta"]),
        residual_magnitude_weight=float(loss_values["residual_magnitude_weight"]),
        trace_interval_steps=int(reproducibility["trace_interval_steps"]),
    )
    seed = int(reproducibility["seed"])
    train_episodes = tuple(item.episode for item in dataset.episodes_for_split("train"))
    validation_episodes = tuple(
        item.episode for item in dataset.episodes_for_split("validation")
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    trained = {}
    normalizations = {}
    train_examples = {}
    validation_examples = {}
    predictions = {}
    traces = {}
    checkpoint_hashes = {}
    for variant in config["variants"]:
        name = str(variant["name"])
        history_length = int(variant["history_length"])
        train_examples[name] = build_residual_dataset(
            train_episodes,
            history_length=history_length,
        )
        validation_examples[name] = build_residual_dataset(
            validation_episodes,
            history_length=history_length,
        )
        normalizations[name] = fit_residual_normalization(
            train_examples[name],
            history_length=history_length,
            expected_train_episode_ids=expected_train_ids,
            scale_floor=float(config["normalization"]["scale_floor"]),
        )
        trained[name] = train_residual_model(
            train_examples[name],
            normalizations[name],
            history_length=history_length,
            seed=seed,
            config=optimizer_config,
        )
        predictions[name] = predict_physical_residuals(
            trained[name].model,
            normalizations[name],
            _matrix(validation_examples[name], "features"),
        )
        traces[name] = trained[name].trace
        variant_dir = args.output_dir / name
        variant_dir.mkdir(exist_ok=True)
        _write_json(variant_dir / "normalization.json", normalizations[name].as_dict())
        _write_trace(variant_dir / "training_trace.csv", trained[name].trace)
        checkpoint_path = variant_dir / "checkpoint.pt"
        torch.save(
            {
                "state_dict": trained[name].model.state_dict(),
                "history_length": history_length,
                "input_width": trained[name].model.input_width,
                "hidden_widths": config["architecture"]["hidden_widths"],
                "seed": seed,
                "git_commit": args.git_commit,
                "training_config_sha256": _sha256(args.training_config),
                "dataset_manifest_sha256": _sha256(args.dataset_manifest),
                "normalization": normalizations[name].as_dict(),
            },
            checkpoint_path,
        )
        checkpoint_hashes[name] = _sha256(checkpoint_path)

    history_keys = {_example_key(example) for example in validation_examples["four_history"]}
    common_no_history = tuple(
        example
        for example in validation_examples["no_history"]
        if _example_key(example) in history_keys
    )
    if tuple(map(_example_key, common_no_history)) != tuple(
        map(_example_key, validation_examples["four_history"])
    ):
        raise ValueError("no-history and history validation rows do not align")
    no_history_lookup = {
        _example_key(example): prediction
        for example, prediction in zip(
            validation_examples["no_history"], predictions["no_history"], strict=True
        )
    }
    common_predictions = {
        "no_history": np.stack(
            [no_history_lookup[_example_key(example)] for example in common_no_history]
        ),
        "four_history": predictions["four_history"],
    }
    common_targets = _matrix(validation_examples["four_history"], "target")
    change_by_key = {
        (item.episode_id, int(row["transition_sequence"])): _parameters_changed(row)
        for item in dataset.episodes_for_split("validation")
        for row in item.episode.transitions
    }
    change_mask = np.asarray(
        [change_by_key[_example_key(example)] for example in validation_examples["four_history"]],
        dtype=bool,
    )
    masks = {
        "all": np.ones(len(common_targets), dtype=bool),
        "parameter_change": change_mask,
        "parameter_stable": ~change_mask,
    }
    comparison: dict[str, object] = {
        "schema_name": "motionworld_residual_training_comparison",
        "schema_version": 1,
        "git_commit": args.git_commit,
        "training_config_sha256": _sha256(args.training_config),
        "dataset_manifest_sha256": _sha256(args.dataset_manifest),
        "test_files_opened": 0,
        "checkpoint_selection": config["evaluation"]["checkpoint_selection"],
        "training": {},
        "validation_variant_eligible": {},
        "common_validation": {},
        "checkpoint_sha256": checkpoint_hashes,
        "claim_boundary": [
            "both checkpoints were fixed after the declared optimizer-step budget",
            "validation was not used for early stopping",
            "common-row comparison uses only four-history-eligible validation transitions",
            "these are one-step results; recursive evaluation is a separate gate",
            "test episodes 5301/5302 were not collected or opened",
        ],
    }
    for name in ("no_history", "four_history"):
        training_targets = _matrix(train_examples[name], "target")
        training_predictions = predict_physical_residuals(
            trained[name].model,
            normalizations[name],
            _matrix(train_examples[name], "features"),
        )
        comparison["training"][name] = {
            "training_seconds": trained[name].training_seconds,
            "example_count": len(train_examples[name]),
            "final_trace": {
                "optimizer_step": trained[name].trace[-1].optimizer_step,
                "total_loss": trained[name].trace[-1].total_loss,
                "huber_loss": trained[name].trace[-1].huber_loss,
                "residual_magnitude_loss": trained[name].trace[-1].residual_magnitude_loss,
            },
            "physical_error": summarize_physical_residual_error(
                training_targets,
                training_predictions,
            ),
        }
        validation_targets = _matrix(validation_examples[name], "target")
        comparison["validation_variant_eligible"][name] = summarize_physical_residual_error(
            validation_targets,
            predictions[name],
        )

    for model_name, model_predictions in {
        "nominal": np.zeros_like(common_targets),
        **common_predictions,
    }.items():
        comparison["common_validation"][model_name] = {
            stratum: _subset_summary(common_targets, model_predictions, mask)
            for stratum, mask in masks.items()
        }

    _write_json(args.output_dir / "comparison.json", comparison)
    _write_learning_plot(traces, args.output_dir / "training_curves.png")
    _write_validation_plot(comparison, args.output_dir / "validation_comparison.png")
    _write_residual_trace_plot(
        common_targets,
        common_predictions,
        change_mask,
        args.output_dir / "validation_residual_trace.png",
    )
    _write_readme(args.output_dir / "README.md", comparison)
    artifact_paths = sorted(
        path
        for path in args.output_dir.rglob("*")
        if path.is_file() and path.name != "artifact_hashes.json"
    )
    _write_json(
        args.output_dir / "artifact_hashes.json",
        {str(path.relative_to(args.output_dir)): _sha256(path) for path in artifact_paths},
    )
    print(
        "training=complete validation=reported test_opened=0 "
        f"no_history_checkpoint={checkpoint_hashes['no_history'][:12]} "
        f"four_history_checkpoint={checkpoint_hashes['four_history'][:12]}"
    )


if __name__ == "__main__":
    main()
