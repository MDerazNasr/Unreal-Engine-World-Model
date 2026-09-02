"""Deterministic one-step residual training and physical-unit evaluation."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
import torch
from numpy.typing import ArrayLike, NDArray
from torch import Tensor, nn

from motionworld.models.residual_contract import RESIDUAL_OUTPUT_COUNT, RESIDUAL_OUTPUT_NAMES
from motionworld.models.residual_dataset import ResidualExample
from motionworld.models.residual_features import RESIDUAL_HISTORY_LENGTH
from motionworld.models.residual_mlp import (
    DEFAULT_HIDDEN_WIDTHS,
    ResidualMLP,
    make_four_history_residual_mlp,
    make_no_history_residual_mlp,
)
from motionworld.models.residual_normalization import ResidualNormalization


@dataclass(frozen=True, slots=True)
class ResidualOptimizerConfig:
    optimizer_steps: int = 1500
    batch_size: int = 128
    learning_rate: float = 1.0e-3
    weight_decay: float = 1.0e-4
    huber_beta: float = 1.0
    residual_magnitude_weight: float = 0.01
    trace_interval_steps: int = 50

    def __post_init__(self) -> None:
        if self.optimizer_steps <= 0 or self.batch_size <= 0 or self.trace_interval_steps <= 0:
            raise ValueError("step, batch, and trace counts must be positive")
        for name in ("learning_rate", "huber_beta"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("weight_decay", "residual_magnitude_weight"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class TrainingTraceRow:
    optimizer_step: int
    total_loss: float
    huber_loss: float
    residual_magnitude_loss: float


@dataclass(frozen=True, slots=True)
class TrainedResidualModel:
    model: ResidualMLP
    history_length: int
    seed: int
    training_seconds: float
    trace: tuple[TrainingTraceRow, ...]


@dataclass(frozen=True, slots=True)
class LoadedResidualCheckpoint:
    """Inference-ready model, normalization, and immutable provenance metadata."""

    model: ResidualMLP
    normalization: ResidualNormalization
    history_length: int
    seed: int
    git_commit: str
    training_config_sha256: str
    dataset_manifest_sha256: str


def normalized_huber_loss(prediction: Tensor, target: Tensor, *, beta: float) -> Tensor:
    """Mean per-component Huber loss in normalized residual coordinates."""

    if prediction.shape != target.shape or prediction.ndim != 2:
        raise ValueError("prediction and target must be same-shape matrices")
    if prediction.shape[1] != RESIDUAL_OUTPUT_COUNT:
        raise ValueError("residual matrices must have six columns")
    if not math.isfinite(beta) or beta <= 0.0:
        raise ValueError("beta must be finite and positive")
    return nn.functional.smooth_l1_loss(prediction, target, reduction="mean", beta=beta)


def residual_training_loss(
    prediction: Tensor,
    target: Tensor,
    *,
    huber_beta: float,
    residual_magnitude_weight: float,
) -> tuple[Tensor, Tensor, Tensor]:
    """Huber data term plus a small normalized correction-magnitude penalty."""

    huber = normalized_huber_loss(prediction, target, beta=huber_beta)
    magnitude = torch.mean(prediction.square())
    total = huber + residual_magnitude_weight * magnitude
    return total, huber, magnitude


def _training_matrices(
    examples: tuple[ResidualExample, ...],
    normalization: ResidualNormalization,
) -> tuple[Tensor, Tensor]:
    if not examples:
        raise ValueError("training examples must be non-empty")
    observed_ids = tuple(sorted({example.episode_id for example in examples}))
    if observed_ids != normalization.train_episode_ids:
        raise ValueError("training examples do not match normalization episode provenance")
    if len(examples) != normalization.sample_count:
        raise ValueError("training example count does not match normalization provenance")
    features = np.stack([example.features for example in examples])
    targets = np.stack([example.target for example in examples])
    normalized_features = normalization.normalize_features(features)
    normalized_targets = normalization.normalize_targets(targets)
    return (
        torch.as_tensor(normalized_features, dtype=torch.float32, device="cpu"),
        torch.as_tensor(normalized_targets, dtype=torch.float32, device="cpu"),
    )


def train_residual_model(
    examples: tuple[ResidualExample, ...],
    normalization: ResidualNormalization,
    *,
    history_length: int,
    seed: int,
    config: ResidualOptimizerConfig,
    hidden_widths: tuple[int, ...] = DEFAULT_HIDDEN_WIDTHS,
) -> TrainedResidualModel:
    """Train a fixed-step CPU model without consulting validation or test data."""

    if history_length != normalization.history_length:
        raise ValueError("model history length and normalization history length differ")
    if history_length not in (1, RESIDUAL_HISTORY_LENGTH):
        raise ValueError(f"history_length must be 1 or {RESIDUAL_HISTORY_LENGTH}")
    torch.manual_seed(seed)
    model = (
        make_no_history_residual_mlp()
        if history_length == 1 and hidden_widths == DEFAULT_HIDDEN_WIDTHS
        else make_four_history_residual_mlp()
        if history_length == RESIDUAL_HISTORY_LENGTH and hidden_widths == DEFAULT_HIDDEN_WIDTHS
        else ResidualMLP(normalization.feature_width, hidden_widths=hidden_widths)
    )
    features, targets = _training_matrices(examples, normalization)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    batch_generator = torch.Generator(device="cpu")
    batch_generator.manual_seed(seed + 1)
    trace: list[TrainingTraceRow] = []
    start = time.perf_counter()
    for optimizer_step in range(1, config.optimizer_steps + 1):
        indices = torch.randint(
            len(examples),
            (config.batch_size,),
            generator=batch_generator,
        )
        prediction = model(features[indices])
        total, huber, magnitude = residual_training_loss(
            prediction,
            targets[indices],
            huber_beta=config.huber_beta,
            residual_magnitude_weight=config.residual_magnitude_weight,
        )
        optimizer.zero_grad(set_to_none=True)
        total.backward()
        optimizer.step()
        if optimizer_step == 1 or optimizer_step % config.trace_interval_steps == 0:
            with torch.no_grad():
                full_prediction = model(features)
                full_total, full_huber, full_magnitude = residual_training_loss(
                    full_prediction,
                    targets,
                    huber_beta=config.huber_beta,
                    residual_magnitude_weight=config.residual_magnitude_weight,
                )
            trace.append(
                TrainingTraceRow(
                    optimizer_step=optimizer_step,
                    total_loss=float(full_total),
                    huber_loss=float(full_huber),
                    residual_magnitude_loss=float(full_magnitude),
                )
            )
    return TrainedResidualModel(
        model=model.eval(),
        history_length=history_length,
        seed=seed,
        training_seconds=time.perf_counter() - start,
        trace=tuple(trace),
    )


def predict_physical_residuals(
    model: ResidualMLP,
    normalization: ResidualNormalization,
    features: ArrayLike,
) -> NDArray[np.float64]:
    """Run CPU inference and decode normalized outputs into the six physical units."""

    normalized = normalization.normalize_features(features)
    tensor = torch.as_tensor(normalized, dtype=torch.float32, device="cpu")
    with torch.no_grad():
        prediction = model(tensor).cpu().numpy().astype(np.float64)
    return normalization.denormalize_targets(prediction)


def load_residual_checkpoint(path: str) -> LoadedResidualCheckpoint:
    """Load a trusted MotionWorld checkpoint and reject schema/shape drift."""

    record = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(record, dict) or record.get("schema_name") != (
        "motionworld_residual_checkpoint"
    ):
        raise ValueError("unexpected residual checkpoint schema")
    if record.get("schema_version") != 1:
        raise ValueError("unsupported residual checkpoint schema version")
    history_length = int(record["history_length"])
    input_width = int(record["input_width"])
    hidden_widths = tuple(int(value) for value in record["hidden_widths"])
    normalization = ResidualNormalization.from_dict(record["normalization"])
    if history_length != normalization.history_length or input_width != normalization.feature_width:
        raise ValueError("checkpoint model and normalization schemas differ")
    model = ResidualMLP(
        input_width,
        hidden_widths=hidden_widths,
        zero_initialize_output=False,
    )
    model.load_state_dict(record["state_dict"], strict=True)
    return LoadedResidualCheckpoint(
        model=model.eval(),
        normalization=normalization,
        history_length=history_length,
        seed=int(record["seed"]),
        git_commit=str(record["git_commit"]),
        training_config_sha256=str(record["training_config_sha256"]),
        dataset_manifest_sha256=str(record["dataset_manifest_sha256"]),
    )


def _distribution(values: NDArray[np.float64]) -> dict[str, float]:
    if values.ndim != 1 or values.size == 0:
        raise ValueError("metric distribution must be a non-empty vector")
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }


def summarize_physical_residual_error(
    targets: ArrayLike,
    predictions: ArrayLike,
) -> dict[str, object]:
    """Report prediction error as next-state error in the residual's physical frame."""

    target = np.asarray(targets, dtype=np.float64)
    prediction = np.asarray(predictions, dtype=np.float64)
    if target.shape != prediction.shape or target.ndim != 2:
        raise ValueError("target and prediction must be same-shape matrices")
    if target.shape[0] == 0 or target.shape[1] != RESIDUAL_OUTPUT_COUNT:
        raise ValueError("residual matrices must be non-empty with six columns")
    if not np.isfinite(target).all() or not np.isfinite(prediction).all():
        raise ValueError("residual metrics require finite values")
    error = prediction - target
    absolute = np.abs(error)
    return {
        "example_count": int(target.shape[0]),
        "component_mae": {
            name: float(np.mean(absolute[:, index]))
            for index, name in enumerate(RESIDUAL_OUTPUT_NAMES)
        },
        "component_rmse": {
            name: float(np.sqrt(np.mean(np.square(error[:, index]))))
            for index, name in enumerate(RESIDUAL_OUTPUT_NAMES)
        },
        "component_absolute_p95": {
            name: float(np.percentile(absolute[:, index], 95))
            for index, name in enumerate(RESIDUAL_OUTPUT_NAMES)
        },
        "state_error": {
            "planar_position_cm": _distribution(np.linalg.norm(error[:, 0:2], axis=1)),
            "planar_velocity_cm_s": _distribution(np.linalg.norm(error[:, 2:4], axis=1)),
            "yaw_deg": _distribution(np.abs(np.degrees(error[:, 4]))),
            "yaw_rate_deg_s": _distribution(np.abs(np.degrees(error[:, 5]))),
        },
    }
