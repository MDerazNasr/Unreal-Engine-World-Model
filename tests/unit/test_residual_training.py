from __future__ import annotations

import numpy as np
import pytest
import torch

from motionworld.models.residual_dataset import ResidualExample
from motionworld.models.residual_features import RESIDUAL_STEP_FEATURE_COUNT
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import fit_residual_normalization
from motionworld.models.residual_training import (
    ResidualOptimizerConfig,
    normalized_huber_loss,
    predict_physical_residuals,
    residual_training_loss,
    summarize_physical_residual_error,
    train_residual_model,
)


def _examples() -> tuple[ResidualExample, ...]:
    examples: list[ResidualExample] = []
    for index in range(8):
        examples.append(
            ResidualExample(
                episode_id=11,
                transition_sequence=index,
                previous_sample_sequence=100 + index,
                next_sample_sequence=101 + index,
                history_transition_sequences=(index,),
                features=np.sin(
                    np.arange(RESIDUAL_STEP_FEATURE_COUNT, dtype=np.float64) + index
                ),
                target=np.asarray(
                    [
                        0.1 * index,
                        -0.05 * index,
                        0.2 * index,
                        -0.1 * index,
                        0.01 * index,
                        -0.02 * index,
                    ]
                ),
            )
        )
    return tuple(examples)


def _normalization():
    return fit_residual_normalization(
        _examples(),
        history_length=1,
        expected_train_episode_ids=(11,),
    )


def test_huber_matches_hand_calculation() -> None:
    prediction = torch.zeros(1, 6)
    target = torch.tensor([[2.0, 0.0, 0.0, 0.0, 0.0, 0.0]])

    loss = normalized_huber_loss(prediction, target, beta=1.0)

    assert float(loss) == pytest.approx(1.5 / 6.0)


def test_total_loss_adds_residual_magnitude_regularizer() -> None:
    prediction = torch.ones(2, 6)
    target = torch.zeros(2, 6)

    total, huber, magnitude = residual_training_loss(
        prediction,
        target,
        huber_beta=1.0,
        residual_magnitude_weight=0.1,
    )

    assert float(huber) == pytest.approx(0.5)
    assert float(magnitude) == pytest.approx(1.0)
    assert float(total) == pytest.approx(0.6)


def test_fixed_seed_training_is_exactly_reproducible() -> None:
    config = ResidualOptimizerConfig(
        optimizer_steps=12,
        batch_size=4,
        trace_interval_steps=4,
    )
    first = train_residual_model(
        _examples(),
        _normalization(),
        history_length=1,
        seed=123,
        config=config,
        hidden_widths=(8,),
    )
    second = train_residual_model(
        _examples(),
        _normalization(),
        history_length=1,
        seed=123,
        config=config,
        hidden_widths=(8,),
    )

    assert first.trace == second.trace
    assert all(
        torch.equal(first.model.state_dict()[name], second.model.state_dict()[name])
        for name in first.model.state_dict()
    )


def test_training_rejects_normalization_from_other_episode_provenance() -> None:
    examples = _examples()
    normalization = fit_residual_normalization(
        examples,
        history_length=1,
        expected_train_episode_ids=(11,),
    )
    changed = list(examples)
    changed[0] = ResidualExample(
        episode_id=21,
        transition_sequence=0,
        previous_sample_sequence=100,
        next_sample_sequence=101,
        history_transition_sequences=(0,),
        features=changed[0].features,
        target=changed[0].target,
    )

    with pytest.raises(ValueError, match="normalization episode provenance"):
        train_residual_model(
            tuple(changed),
            normalization,
            history_length=1,
            seed=123,
            config=ResidualOptimizerConfig(optimizer_steps=1),
            hidden_widths=(8,),
        )


def test_training_rejects_different_row_count_under_same_episode_id() -> None:
    examples = _examples()
    normalization = _normalization()

    with pytest.raises(ValueError, match="example count"):
        train_residual_model(
            examples[:-1],
            normalization,
            history_length=1,
            seed=123,
            config=ResidualOptimizerConfig(optimizer_steps=1),
            hidden_widths=(8,),
        )


def test_zero_model_decodes_to_exact_zero_physical_residual() -> None:
    normalization = _normalization()
    model = ResidualMLP(RESIDUAL_STEP_FEATURE_COUNT, hidden_widths=(8,))
    features = np.stack([example.features for example in _examples()[:2]])

    prediction = predict_physical_residuals(model, normalization, features)

    assert np.array_equal(prediction, np.zeros((2, 6)))


def test_physical_summary_converts_angular_units_and_vector_norms() -> None:
    targets = np.asarray([[3.0, 4.0, 0.0, 0.0, np.pi / 2.0, np.pi]])
    predictions = np.zeros((1, 6))

    summary = summarize_physical_residual_error(targets, predictions)

    assert summary["state_error"]["planar_position_cm"]["mean"] == pytest.approx(5.0)
    assert summary["state_error"]["yaw_deg"]["mean"] == pytest.approx(90.0)
    assert summary["state_error"]["yaw_rate_deg_s"]["mean"] == pytest.approx(180.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"optimizer_steps": 0},
        {"batch_size": 0},
        {"learning_rate": 0.0},
        {"weight_decay": -1.0},
        {"huber_beta": 0.0},
        {"residual_magnitude_weight": -1.0},
    ],
)
def test_invalid_optimizer_config_is_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        ResidualOptimizerConfig(**kwargs)
