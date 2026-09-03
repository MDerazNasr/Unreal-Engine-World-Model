from pathlib import Path

import pytest

from motionworld.models.compression_sweep import (
    load_residual_width_sweep,
    select_compressed_model,
)

CONFIG = Path("configs/residual_width_sweep.yaml")


def test_repository_width_sweep_is_frozen_and_valid() -> None:
    sweep = load_residual_width_sweep(CONFIG)

    assert sweep.status == "frozen_before_training_or_validation"
    assert sweep.history_length == 1
    assert len(sweep.candidates) == 4
    assert sweep.recursive_horizons_s == (0.5, 1.0, 1.5)
    assert sweep.maximum_recursive_relative_degradation == pytest.approx(0.15)
    assert len(sweep.validation_queries) == 10
    assert sweep.deadline_ms == pytest.approx(100.0)


def test_selection_rejects_all_ineligible_models() -> None:
    assert select_compressed_model([{"name": "small", "eligible": False}]) is None


def test_selection_prefers_runtime_then_parameter_count_then_name() -> None:
    records = [
        {"name": "b", "eligible": True, "runtime_p95_ms": 90.0, "parameter_count": 10},
        {"name": "a", "eligible": True, "runtime_p95_ms": 80.0, "parameter_count": 20},
        {"name": "c", "eligible": False, "runtime_p95_ms": 70.0, "parameter_count": 5},
    ]

    assert select_compressed_model(records) == "a"
