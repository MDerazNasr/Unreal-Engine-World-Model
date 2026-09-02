"""Learned-model contracts for MotionWorld."""

from motionworld.models.residual_contract import (
    RESIDUAL_OUTPUT_COUNT,
    RESIDUAL_OUTPUT_NAMES,
    ResidualCorrection,
    compose_residual,
    residual_difference,
    zero_residual,
)
from motionworld.models.residual_dataset import (
    ResidualExample,
    build_residual_dataset,
    build_residual_examples,
)
from motionworld.models.residual_features import (
    RESIDUAL_FEATURE_SCHEMA_VERSION,
    RESIDUAL_HISTORY_FEATURE_COUNT,
    RESIDUAL_HISTORY_LENGTH,
    RESIDUAL_STEP_FEATURE_COUNT,
    RESIDUAL_STEP_FEATURE_NAMES,
    encode_residual_step_features,
    stack_residual_history,
)
from motionworld.models.residual_mlp import (
    DEFAULT_HIDDEN_WIDTHS,
    ResidualMLP,
    make_four_history_residual_mlp,
    make_no_history_residual_mlp,
)
from motionworld.models.residual_normalization import (
    DEFAULT_SCALE_FLOOR,
    RESIDUAL_NORMALIZATION_SCHEMA_VERSION,
    ResidualNormalization,
    feature_names_for_history,
    fit_residual_normalization,
)

__all__ = [
    "ResidualCorrection",
    "RESIDUAL_OUTPUT_COUNT",
    "RESIDUAL_OUTPUT_NAMES",
    "compose_residual",
    "residual_difference",
    "zero_residual",
    "ResidualExample",
    "build_residual_dataset",
    "build_residual_examples",
    "RESIDUAL_FEATURE_SCHEMA_VERSION",
    "RESIDUAL_HISTORY_FEATURE_COUNT",
    "RESIDUAL_HISTORY_LENGTH",
    "RESIDUAL_STEP_FEATURE_COUNT",
    "RESIDUAL_STEP_FEATURE_NAMES",
    "encode_residual_step_features",
    "stack_residual_history",
    "DEFAULT_HIDDEN_WIDTHS",
    "ResidualMLP",
    "make_four_history_residual_mlp",
    "make_no_history_residual_mlp",
    "DEFAULT_SCALE_FLOOR",
    "RESIDUAL_NORMALIZATION_SCHEMA_VERSION",
    "ResidualNormalization",
    "feature_names_for_history",
    "fit_residual_normalization",
]
