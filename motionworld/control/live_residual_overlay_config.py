"""Fail-closed loader for the selected learned-model demo overlay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import yaml

from motionworld.control.live_mpc_config import load_live_nominal_mpc_config
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.models.residual_training import load_residual_checkpoint
from motionworld.planning.planner_rollout import PlannerRolloutConfig


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, relative: object, context: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"{context} must be a non-empty repository-relative path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"{context} must stay inside the repository") from error
    return path


def _verified(root: Path, record: dict[str, object], context: str) -> Path:
    if set(record) != {"path", "sha256"}:
        raise ValueError(f"{context} keys must be exactly path and sha256")
    path = _inside(root, record["path"], f"{context}.path")
    expected = record["sha256"]
    if not isinstance(expected, str) or len(expected) != 64 or _sha256(path) != expected:
        raise ValueError(f"{context} SHA-256 mismatch")
    return path


def load_live_residual_overlay_config(path: Path, repository_root: Path):
    """Verify every artifact before deserializing the trusted local checkpoint."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected_keys = {
        "schema_name", "schema_version", "status", "claim_boundary",
        "nominal_planner", "checkpoint", "normalization", "training_config",
        "dataset_manifest", "expected_checkpoint", "overlay_rollout",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise ValueError("residual overlay config has unexpected keys")
    if raw["schema_name"] != "motionworld_live_residual_overlay_demo" or raw["schema_version"] != 1:
        raise ValueError("unsupported residual overlay config schema")
    if raw["status"] != "matched_prediction_overlay_nominal_control_only":
        raise ValueError("overlay must preserve nominal-only control ownership")
    if (
        not isinstance(raw["claim_boundary"], str)
        or "not residual control" not in raw["claim_boundary"]
    ):
        raise ValueError("overlay claim boundary must reject a residual-control claim")

    nominal_path = _verified(repository_root, raw["nominal_planner"], "nominal_planner")
    checkpoint_path = _verified(repository_root, raw["checkpoint"], "checkpoint")
    normalization_path = _verified(repository_root, raw["normalization"], "normalization")
    training_path = _verified(repository_root, raw["training_config"], "training_config")
    dataset_path = _verified(repository_root, raw["dataset_manifest"], "dataset_manifest")

    expected = raw["expected_checkpoint"]
    if not isinstance(expected, dict) or set(expected) != {
        "history_length", "input_width", "hidden_widths", "parameter_count",
        "seed", "git_commit",
    }:
        raise ValueError("expected_checkpoint keys are invalid")
    checkpoint = load_residual_checkpoint(str(checkpoint_path))
    linear_widths = tuple(
        layer.out_features for layer in checkpoint.model.backbone if hasattr(layer, "out_features")
    )
    observed = {
        "history_length": checkpoint.history_length,
        "input_width": checkpoint.model.input_width,
        "hidden_widths": list(linear_widths),
        "parameter_count": checkpoint.model.parameter_count,
        "seed": checkpoint.seed,
        "git_commit": checkpoint.git_commit,
    }
    if observed != expected:
        raise ValueError("checkpoint architecture or training identity mismatch")
    if checkpoint.training_config_sha256 != _sha256(training_path):
        raise ValueError("checkpoint training-config provenance mismatch")
    if checkpoint.dataset_manifest_sha256 != _sha256(dataset_path):
        raise ValueError("checkpoint dataset-manifest provenance mismatch")
    standalone_record = json.loads(normalization_path.read_text(encoding="utf-8"))
    standalone = ResidualNormalization.from_dict(standalone_record)
    if standalone.as_dict() != checkpoint.normalization.as_dict():
        raise ValueError("standalone and checkpoint normalization differ")

    rollout_raw = raw["overlay_rollout"]
    if not isinstance(rollout_raw, dict) or set(rollout_raw) != set(
        PlannerRolloutConfig.__dataclass_fields__
    ):
        raise ValueError("overlay_rollout keys are invalid")
    overlay_rollout = PlannerRolloutConfig(**rollout_raw)
    if overlay_rollout.dynamics_substeps_per_plan_step != 3:
        raise ValueError("learned overlay requires three integration substeps")
    nominal = load_live_nominal_mpc_config(nominal_path, repository_root)
    return replace(
        nominal,
        residual_overlay_model=checkpoint.model,
        residual_overlay_normalization=checkpoint.normalization,
        residual_overlay_rollout=overlay_rollout,
    )
