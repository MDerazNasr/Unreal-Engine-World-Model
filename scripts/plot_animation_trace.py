#!/usr/bin/env python3
"""Validate and plot one MotionWorld actor-versus-animation-root log session."""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path

from motionworld.diagnostics import load_animation_trace, plot_animation_trace


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--session")
    args = parser.parse_args()

    trace = load_animation_trace(args.log, session_id=args.session)
    plot_animation_trace(trace, args.output)
    offsets = [
        math.hypot(
            sample.actor_to_animation_root_world_cm[0],
            sample.actor_to_animation_root_world_cm[1],
        )
        for sample in trace.samples
    ]
    print(
        "valid=true",
        f"session={trace.session_id}",
        f"samples={len(trace.samples)}",
        f"component={trace.visual_component_name}",
        f"root_bone={trace.root_bone_name}",
        f"median_planar_offset_cm={statistics.median(offsets):.6f}",
        f"max_planar_offset_cm={max(offsets):.6f}",
        f"output={args.output.resolve()}",
    )


if __name__ == "__main__":
    main()
