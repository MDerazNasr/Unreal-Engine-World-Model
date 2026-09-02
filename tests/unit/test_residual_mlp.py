import pytest
import torch

from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_FEATURE_COUNT,
    RESIDUAL_STEP_FEATURE_COUNT,
)
from motionworld.models.residual_mlp import (
    ResidualMLP,
    make_four_history_residual_mlp,
    make_no_history_residual_mlp,
)


@pytest.mark.parametrize(
    ("factory", "input_width", "expected_parameters"),
    [
        (make_no_history_residual_mlp, RESIDUAL_STEP_FEATURE_COUNT, 106_886),
        (make_four_history_residual_mlp, RESIDUAL_HISTORY_FEATURE_COUNT, 128_390),
    ],
)
def test_default_models_have_expected_shape_and_bounded_size(
    factory,
    input_width: int,
    expected_parameters: int,
) -> None:
    model = factory()
    output = model(torch.ones(5, input_width))

    assert output.shape == (5, 6)
    assert model.parameter_count == expected_parameters
    assert model.parameter_count < 500_000


@pytest.mark.parametrize(
    "factory",
    [make_no_history_residual_mlp, make_four_history_residual_mlp],
)
def test_zero_initialized_output_is_exact_nominal_fallback(factory) -> None:
    model = factory()
    features = torch.randn(3, model.input_width)

    assert torch.equal(model(features), torch.zeros(3, 6))


def test_training_signal_reaches_output_layer_and_changes_prediction() -> None:
    torch.manual_seed(7)
    model = make_no_history_residual_mlp()
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    features = torch.randn(4, RESIDUAL_STEP_FEATURE_COUNT)
    target = torch.ones(4, 6)

    loss = torch.nn.functional.mse_loss(model(features), target)
    loss.backward()

    assert model.output.weight.grad is not None
    assert torch.isfinite(model.output.weight.grad).all()
    assert torch.count_nonzero(model.output.weight.grad) > 0
    optimizer.step()
    assert torch.count_nonzero(model(features)) > 0


def test_batch_prefix_and_float64_dtype_are_preserved() -> None:
    model = make_no_history_residual_mlp().to(dtype=torch.float64)
    features = torch.ones(2, 3, RESIDUAL_STEP_FEATURE_COUNT, dtype=torch.float64)

    output = model(features)

    assert output.shape == (2, 3, 6)
    assert output.dtype == torch.float64
    assert output.device == features.device


@pytest.mark.parametrize("shape", [(), (27,), (2, 29)])
def test_wrong_input_shape_fails_closed(shape: tuple[int, ...]) -> None:
    model = make_no_history_residual_mlp()

    with pytest.raises(ValueError, match="input width"):
        model(torch.zeros(shape))


@pytest.mark.parametrize("widths", [(), (256, 0), (-1,)])
def test_invalid_hidden_widths_are_rejected(widths: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="positive"):
        ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=widths)


def test_fixed_seed_reproduces_initial_parameters() -> None:
    torch.manual_seed(123)
    first = make_no_history_residual_mlp()
    torch.manual_seed(123)
    second = make_no_history_residual_mlp()

    for first_parameter, second_parameter in zip(
        first.parameters(),
        second.parameters(),
        strict=True,
    ):
        assert torch.equal(first_parameter, second_parameter)


def test_fixed_seed_reproduces_one_training_step() -> None:
    def train_once(seed: int) -> tuple[float, dict[str, torch.Tensor]]:
        torch.manual_seed(seed)
        model = make_no_history_residual_mlp()
        optimizer = torch.optim.AdamW(model.parameters(), lr=1.0e-3)
        features = torch.randn(8, RESIDUAL_STEP_FEATURE_COUNT)
        targets = torch.randn(8, 6)
        loss = torch.nn.functional.smooth_l1_loss(model(features), targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        return float(loss.detach()), {
            name: value.detach().clone() for name, value in model.state_dict().items()
        }

    first_loss, first_state = train_once(456)
    second_loss, second_state = train_once(456)

    assert first_loss == second_loss
    assert first_state.keys() == second_state.keys()
    assert all(
        torch.equal(first_state[name], second_state[name]) for name in first_state
    )
