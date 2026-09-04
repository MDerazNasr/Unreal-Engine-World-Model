#!/usr/bin/env python3
"""Run the read-only MotionWorld interview-demo preflight."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from motionworld.demo_preflight import run_preflight

ROOT = Path(__file__).resolve().parents[1]


def _optional_path(value: str | None) -> Path | None:
    return Path(value).expanduser().resolve() if value else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--unreal-editor",
        type=Path,
        default=_optional_path(os.environ.get("MOTIONWORLD_UNREAL_EDITOR")),
    )
    parser.add_argument(
        "--unreal-project",
        type=Path,
        default=_optional_path(os.environ.get("MOTIONWORLD_UNREAL_PROJECT")),
    )
    parser.add_argument("--require-unreal", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit the complete report as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_preflight(
        args.repo_root,
        unreal_editor=args.unreal_editor,
        unreal_project=args.unreal_project,
        require_unreal=args.require_unreal,
    )
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        for check in report.checks:
            print(f"{check.status.upper():4} {check.name}: {check.detail}")
        print(f"live_launch_ready={str(report.live_launch_ready).lower()}")
        print(f"fallback_ready={str(report.fallback_ready).lower()}")
        print(f"claim_boundary={report.claim_boundary}")
    return 1 if any(check.status == "fail" for check in report.checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
