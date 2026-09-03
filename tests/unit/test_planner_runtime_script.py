from __future__ import annotations

import argparse

import pytest

from scripts.benchmark_planner_runtime import _positive_int, _statistics


def test_runtime_statistics_preserve_samples_and_deadline_result() -> None:
    result = _statistics([40.0, 50.0, 60.0, 70.0], deadline_ms=65.0)
    assert result["sample_count"] == 4
    assert result["median_ms"] == 55.0
    assert result["p95_ms"] == pytest.approx(68.5)
    assert result["median_meets_deadline"] is True
    assert result["p95_meets_deadline"] is False
    assert result["latencies_ms"] == [40.0, 50.0, 60.0, 70.0]


@pytest.mark.parametrize("value", ["0", "-1"])
def test_runtime_count_must_be_positive(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _positive_int(value)
