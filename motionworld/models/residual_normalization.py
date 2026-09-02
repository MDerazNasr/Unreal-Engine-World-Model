"""Training-only normalization that preserves the exact zero-residual identity."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from motionworld.models.residual_contract import RESIDUAL_OUTPUT_COUNT, RESIDUAL_OUTPUT_NAMES
from motionworld.models.residual_dataset import ResidualExample
from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_FEATURE_COUNT,
    RESIDUAL_HISTORY_LENGTH,
    RESIDUAL_STEP_FEATURE_COUNT,
    RESIDUAL_STEP_FEATURE_NAMES,
)

RESIDUAL_NORMALIZATION_SCHEMA_VERSION = 1
DEFAULT_SCALE_FLOOR = 1.0e-8


def feature_names_for_history(history_length: int) -> tuple[str, ...]:
    if history_length == 1:
        return RESIDUAL_STEP_FEATURE_NAMES
    if history_length == RESIDUAL_HISTORY_LENGTH:
        return tuple(
            f"history[{history_index}].{name}"
            for history_index in range(RESIDUAL_HISTORY_LENGTH)
            for name in RESIDUAL_STEP_FEATURE_NAMES
        )
    raise ValueError(f"history_length must be 1 or {RESIDUAL_HISTORY_LENGTH}")


def _finite_vector(value: ArrayLike, *, width: int, name: str) -> NDArray[np.float64]:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != (width,):
        raise ValueError(f"{name} must have shape ({width},)")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    result = result.copy()
    result.setflags(write=False)
    return result


def _normalize_array(
    values: ArrayLike,
    *,
    offset: NDArray[np.float64],
    scale: NDArray[np.float64],
    name: str,
) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim < 1 or array.shape[-1] != offset.shape[0]:
        raise ValueError(f"{name} must end with width {offset.shape[0]}")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return (array - offset) / scale


@dataclass(frozen=True, slots=True)
class ResidualNormalization:
    """Train-derived feature standardization and zero-centered target scaling."""

    history_length: int
    train_episode_ids: tuple[int, ...]
    sample_count: int
    feature_mean: NDArray[np.float64]
    feature_scale: NDArray[np.float64]
    constant_feature_mask: NDArray[np.bool_]
    target_scale: NDArray[np.float64]
    constant_target_mask: NDArray[np.bool_]
    scale_floor: float = DEFAULT_SCALE_FLOOR

    def __post_init__(self) -> None:
        feature_width = len(feature_names_for_history(self.history_length))
        if not self.train_episode_ids or len(set(self.train_episode_ids)) != len(
            self.train_episode_ids
        ):
            raise ValueError("train_episode_ids must be non-empty and unique")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if not np.isfinite(self.scale_floor) or self.scale_floor <= 0.0:
            raise ValueError("scale_floor must be finite and positive")
        for name, width in (
            ("feature_mean", feature_width),
            ("feature_scale", feature_width),
            ("target_scale", RESIDUAL_OUTPUT_COUNT),
        ):
            object.__setattr__(
                self,
                name,
                _finite_vector(getattr(self, name), width=width, name=name),
            )
        for name, width in (
            ("constant_feature_mask", feature_width),
            ("constant_target_mask", RESIDUAL_OUTPUT_COUNT),
        ):
            value = np.asarray(getattr(self, name), dtype=np.bool_)
            if value.shape != (width,):
                raise ValueError(f"{name} must have shape ({width},)")
            value = value.copy()
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if np.any(self.feature_scale <= 0.0) or np.any(self.target_scale <= 0.0):
            raise ValueError("normalization scales must be positive")

    @property
    def feature_width(self) -> int:
        return len(self.feature_mean)

    def normalize_features(self, values: ArrayLike) -> NDArray[np.float64]:
        return _normalize_array(
            values,
            offset=self.feature_mean,
            scale=self.feature_scale,
            name="features",
        )

    def denormalize_features(self, values: ArrayLike) -> NDArray[np.float64]:
        array = _normalize_array(
            values,
            offset=np.zeros_like(self.feature_mean),
            scale=np.ones_like(self.feature_scale),
            name="normalized features",
        )
        return array * self.feature_scale + self.feature_mean

    def normalize_targets(self, values: ArrayLike) -> NDArray[np.float64]:
        zeros = np.zeros(RESIDUAL_OUTPUT_COUNT, dtype=np.float64)
        return _normalize_array(
            values,
            offset=zeros,
            scale=self.target_scale,
            name="targets",
        )

    def denormalize_targets(self, values: ArrayLike) -> NDArray[np.float64]:
        zeros = np.zeros(RESIDUAL_OUTPUT_COUNT, dtype=np.float64)
        array = _normalize_array(
            values,
            offset=zeros,
            scale=np.ones_like(self.target_scale),
            name="normalized targets",
        )
        return array * self.target_scale

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_name": "motionworld_residual_normalization",
            "schema_version": RESIDUAL_NORMALIZATION_SCHEMA_VERSION,
            "history_length": self.history_length,
            "train_episode_ids": list(self.train_episode_ids),
            "sample_count": self.sample_count,
            "feature_names": list(feature_names_for_history(self.history_length)),
            "feature_mean": self.feature_mean.tolist(),
            "feature_scale": self.feature_scale.tolist(),
            "constant_feature_mask": self.constant_feature_mask.tolist(),
            "target_names": list(RESIDUAL_OUTPUT_NAMES),
            "target_center": [0.0] * RESIDUAL_OUTPUT_COUNT,
            "target_scale": self.target_scale.tolist(),
            "constant_target_mask": self.constant_target_mask.tolist(),
            "scale_floor": self.scale_floor,
            "policy": {
                "fit_split": "train_only",
                "features": "population_mean_and_population_standard_deviation",
                "constant_features": "unit_scale_after_centering",
                "targets": "population_standard_deviation_without_mean_centering",
                "zero_residual_identity": "normalized_zero_decodes_to_exact_physical_zero",
            },
        }


def fit_residual_normalization(
    examples: tuple[ResidualExample, ...],
    *,
    history_length: int,
    expected_train_episode_ids: tuple[int, ...],
    scale_floor: float = DEFAULT_SCALE_FLOOR,
) -> ResidualNormalization:
    """Fit all statistics from an explicitly declared training-example tuple."""

    if not examples:
        raise ValueError("cannot fit normalization from an empty training set")
    if not np.isfinite(scale_floor) or scale_floor <= 0.0:
        raise ValueError("scale_floor must be finite and positive")
    expected_ids = tuple(sorted(expected_train_episode_ids))
    observed_ids = tuple(sorted({example.episode_id for example in examples}))
    if not expected_ids or len(expected_ids) != len(set(expected_ids)):
        raise ValueError("expected_train_episode_ids must be non-empty and unique")
    if observed_ids != expected_ids:
        raise ValueError(
            f"normalization episode IDs differ from declared training split: "
            f"observed={observed_ids}, expected={expected_ids}"
        )
    feature_width = (
        RESIDUAL_STEP_FEATURE_COUNT
        if history_length == 1
        else RESIDUAL_HISTORY_FEATURE_COUNT
        if history_length == RESIDUAL_HISTORY_LENGTH
        else None
    )
    if feature_width is None:
        raise ValueError(f"history_length must be 1 or {RESIDUAL_HISTORY_LENGTH}")
    features = np.stack([example.features for example in examples])
    targets = np.stack([example.target for example in examples])
    if features.shape != (len(examples), feature_width):
        raise ValueError("training feature matrix does not match the declared history schema")
    if targets.shape != (len(examples), RESIDUAL_OUTPUT_COUNT):
        raise ValueError("training target matrix does not match the residual output schema")
    if not np.isfinite(features).all() or not np.isfinite(targets).all():
        raise ValueError("training data contains a non-finite value")

    feature_mean = np.mean(features, axis=0)
    feature_std = np.std(features, axis=0)
    target_std = np.std(targets, axis=0)
    constant_feature_mask = feature_std <= scale_floor
    constant_target_mask = target_std <= scale_floor
    feature_scale = np.where(constant_feature_mask, 1.0, feature_std)
    target_scale = np.where(constant_target_mask, 1.0, target_std)
    return ResidualNormalization(
        history_length=history_length,
        train_episode_ids=expected_ids,
        sample_count=len(examples),
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        constant_feature_mask=constant_feature_mask,
        target_scale=target_scale,
        constant_target_mask=constant_target_mask,
        scale_floor=scale_floor,
    )
