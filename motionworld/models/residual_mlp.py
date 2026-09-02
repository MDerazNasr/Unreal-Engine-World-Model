"""Small feed-forward residual model with an exact nominal initialization."""

from __future__ import annotations

from collections.abc import Sequence

from torch import Tensor, nn

from motionworld.models.residual_contract import RESIDUAL_OUTPUT_COUNT
from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_FEATURE_COUNT,
    RESIDUAL_STEP_FEATURE_COUNT,
)

DEFAULT_HIDDEN_WIDTHS = (256, 256, 128)


class ResidualMLP(nn.Module):
    """Predict a six-component residual from one causal feature vector."""

    def __init__(
        self,
        input_width: int,
        *,
        hidden_widths: Sequence[int] = DEFAULT_HIDDEN_WIDTHS,
        zero_initialize_output: bool = True,
    ) -> None:
        super().__init__()
        if input_width not in (
            RESIDUAL_STEP_FEATURE_COUNT,
            RESIDUAL_HISTORY_FEATURE_COUNT,
        ):
            raise ValueError("input_width must match the no-history or four-history schema")
        widths = tuple(int(width) for width in hidden_widths)
        if not widths or any(width <= 0 for width in widths):
            raise ValueError("hidden_widths must contain positive integers")
        self.input_width = input_width
        layers: list[nn.Module] = []
        previous_width = input_width
        for width in widths:
            layers.extend((nn.Linear(previous_width, width), nn.SiLU()))
            previous_width = width
        self.backbone = nn.Sequential(*layers)
        self.output = nn.Linear(previous_width, RESIDUAL_OUTPUT_COUNT)
        if zero_initialize_output:
            nn.init.zeros_(self.output.weight)
            nn.init.zeros_(self.output.bias)

    def forward(self, features: Tensor) -> Tensor:
        if features.ndim < 1 or features.shape[-1] != self.input_width:
            raise ValueError(
                f"features must end with input width {self.input_width}; "
                f"received shape {tuple(features.shape)}"
            )
        return self.output(self.backbone(features))

    @property
    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())


def make_no_history_residual_mlp() -> ResidualMLP:
    """Construct the P0 current-query model."""

    return ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT)


def make_four_history_residual_mlp() -> ResidualMLP:
    """Construct the matched P0 four-query-history model."""

    return ResidualMLP(RESIDUAL_HISTORY_FEATURE_COUNT)
