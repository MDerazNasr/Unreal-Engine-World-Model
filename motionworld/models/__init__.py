"""Learned-model contracts for MotionWorld."""

from motionworld.models.residual_contract import (
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

__all__ = [
    "ResidualCorrection",
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
]
