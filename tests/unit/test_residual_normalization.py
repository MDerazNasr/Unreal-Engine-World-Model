from __future__ import annotations

import numpy as np
import pytest

from motionworld.models.residual_dataset import ResidualExample
from motionworld.models.residual_features import RESIDUAL_STEP_FEATURE_COUNT
from motionworld.models.residual_normalization import (
    ResidualNormalization,
    feature_names_for_history,
    fit_residual_normalization,
)


def _example(
    episode_id: int,
    sequence: int,
    *,
    feature_offset: float,
    target_scale: float,
) -> ResidualExample:
    return ResidualExample(
        episode_id=episode_id,
        transition_sequence=sequence,
        previous_sample_sequence=100 + sequence,
        next_sample_sequence=101 + sequence,
        history_transition_sequences=(sequence,),
        features=np.arange(RESIDUAL_STEP_FEATURE_COUNT, dtype=np.float64) + feature_offset,
        target=np.asarray([1.0, -2.0, 3.0, -4.0, 0.5, -0.25]) * target_scale,
    )


def _normalization():
    examples = (
        _example(11, 0, feature_offset=0.0, target_scale=0.0),
        _example(11, 1, feature_offset=2.0, target_scale=1.0),
        _example(12, 0, feature_offset=4.0, target_scale=-1.0),
    )
    return fit_residual_normalization(
        examples,
        history_length=1,
        expected_train_episode_ids=(11, 12),
    )


def test_train_statistics_normalize_and_round_trip() -> None:
    normalization = _normalization()
    values = np.stack(
        [
            np.arange(RESIDUAL_STEP_FEATURE_COUNT, dtype=np.float64),
            np.arange(RESIDUAL_STEP_FEATURE_COUNT, dtype=np.float64) + 4.0,
        ]
    )
    normalized = normalization.normalize_features(values)

    np.testing.assert_allclose(
        normalization.denormalize_features(normalized),
        values,
        atol=1.0e-12,
    )
    assert normalization.train_episode_ids == (11, 12)
    assert normalization.sample_count == 3


def test_target_scale_only_preserves_exact_zero_residual() -> None:
    normalization = _normalization()
    zeros = np.zeros((4, 6), dtype=np.float64)

    assert np.array_equal(normalization.normalize_targets(zeros), zeros)
    assert np.array_equal(normalization.denormalize_targets(zeros), zeros)


def test_target_normalization_round_trip() -> None:
    normalization = _normalization()
    targets = np.asarray([[0.1, -0.2, 3.0, 0.0, 0.05, -2.0]])

    np.testing.assert_allclose(
        normalization.denormalize_targets(normalization.normalize_targets(targets)),
        targets,
        atol=1.0e-12,
    )


def test_declared_training_ids_reject_validation_contamination() -> None:
    examples = (
        _example(11, 0, feature_offset=0.0, target_scale=1.0),
        _example(21, 0, feature_offset=1.0, target_scale=1.0),
    )

    with pytest.raises(ValueError, match="differ from declared training split"):
        fit_residual_normalization(
            examples,
            history_length=1,
            expected_train_episode_ids=(11,),
        )


def test_constant_dimensions_receive_unit_scale() -> None:
    repeated = tuple(
        _example(11, index, feature_offset=0.0, target_scale=1.0)
        for index in range(3)
    )
    normalization = fit_residual_normalization(
        repeated,
        history_length=1,
        expected_train_episode_ids=(11,),
    )

    assert normalization.constant_feature_mask.all()
    np.testing.assert_array_equal(normalization.feature_scale, np.ones(28))
    assert normalization.constant_target_mask.all()
    np.testing.assert_array_equal(normalization.target_scale, np.ones(6))


def test_serialized_contract_names_train_only_policy_and_all_dimensions() -> None:
    record = _normalization().as_dict()

    assert record["policy"]["fit_split"] == "train_only"
    assert record["policy"]["zero_residual_identity"].startswith("normalized_zero")
    assert len(record["feature_names"]) == 28
    assert len(feature_names_for_history(4)) == 112
    assert record["target_center"] == [0.0] * 6


def test_saved_normalization_round_trip_preserves_all_statistics() -> None:
    normalization = _normalization()
    restored = ResidualNormalization.from_dict(normalization.as_dict())

    assert restored.as_dict() == normalization.as_dict()


def test_saved_normalization_rejects_nonzero_target_center() -> None:
    record = _normalization().as_dict()
    record["target_center"][0] = 1.0

    with pytest.raises(ValueError, match="zero-residual"):
        ResidualNormalization.from_dict(record)


@pytest.mark.parametrize("history_length", [0, 2, 3, 5])
def test_unsupported_history_length_is_rejected(history_length: int) -> None:
    with pytest.raises(ValueError, match="history_length"):
        feature_names_for_history(history_length)
