"""Smoke tests for the reproducible MotionWorld Python environment."""

from __future__ import annotations

import importlib

import torch

import motionworld


def test_required_packages_import() -> None:
    """The locked environment exposes the packages required by the project contract."""

    for module_name in ("matplotlib", "numpy", "scipy", "sklearn", "torch", "yaml"):
        assert importlib.import_module(module_name) is not None


def test_package_version_is_declared() -> None:
    assert motionworld.__version__ == "0.1.0"


def test_seeded_cpu_tensor_operation_is_repeatable() -> None:
    """CPU unit-test oracles must be repeatable under an explicitly reset seed."""

    torch.manual_seed(1042)
    first = torch.randn(32, dtype=torch.float64) @ torch.randn(32, dtype=torch.float64)

    torch.manual_seed(1042)
    second = torch.randn(32, dtype=torch.float64) @ torch.randn(32, dtype=torch.float64)

    torch.testing.assert_close(first, second, rtol=0.0, atol=0.0)

