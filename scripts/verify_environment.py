#!/usr/bin/env python3
"""Report and verify the local MotionWorld numerical environment."""

from __future__ import annotations

import json
import platform
import sys
from importlib import metadata

import torch


def package_version(distribution: str) -> str:
    """Return an installed distribution version without importing private APIs."""

    return metadata.version(distribution)


def seeded_cpu_result(seed: int = 1042) -> torch.Tensor:
    """Return a small deterministic CPU result used by the environment smoke check."""

    torch.manual_seed(seed)
    left = torch.randn(32, dtype=torch.float64, device="cpu")
    right = torch.randn(32, dtype=torch.float64, device="cpu")
    return left @ right


def main() -> int:
    first = seeded_cpu_result()
    second = seeded_cpu_result()
    deterministic_cpu_smoke = torch.equal(first, second)

    report = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "packages": {
            name: package_version(distribution)
            for name, distribution in {
                "matplotlib": "matplotlib",
                "numpy": "numpy",
                "pyyaml": "PyYAML",
                "scikit_learn": "scikit-learn",
                "scipy": "scipy",
                "torch": "torch",
            }.items()
        },
        "torch": {
            "cpu_available": True,
            "mps_available": torch.backends.mps.is_available(),
            "mps_built": torch.backends.mps.is_built(),
        },
        "deterministic_cpu_smoke": deterministic_cpu_smoke,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if deterministic_cpu_smoke else 1


if __name__ == "__main__":
    raise SystemExit(main())

