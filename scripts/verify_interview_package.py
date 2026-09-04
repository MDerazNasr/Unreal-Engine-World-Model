#!/usr/bin/env python3
"""Fail closed if an interview-package artifact is missing or contains a developer path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts/interview/package_manifest.json"
REQUIRED = (
    "docs/INTERVIEW_PACKAGE.md",
    "runbooks/interview_fallback.md",
    "artifacts/interview/architecture.svg",
    "artifacts/residual/recursive_001/recursive_comparison.png",
    "artifacts/planning/offplan_001/offline_paired_planner.png",
    "artifacts/planning/runtime_001/runtime.json",
    "artifacts/planning/budget_sweep_001/budget_sweep.png",
    "artifacts/residual/compression_001/width_sweep.png",
)
FORBIDDEN_TEXT = ("/Users/", "mderaznasr", "file://")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    records = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"missing or empty package file: {relative}")
        if path.suffix.lower() in {".md", ".svg", ".json"}:
            text = path.read_text(encoding="utf-8")
            found = [value for value in FORBIDDEN_TEXT if value in text]
            if found:
                raise ValueError(f"developer-only path in {relative}: {found}")
        records.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    payload = {
        "schema_name": "motionworld_interview_package_manifest",
        "schema_version": 1,
        "file_count": len(records),
        "files": records,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"interview_package=valid files={len(records)} developer_paths=0")


if __name__ == "__main__":
    main()
