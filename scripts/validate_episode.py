#!/usr/bin/env python3
"""Validate one exported MotionWorld episode and print a compact audit summary."""

from __future__ import annotations

import argparse
from pathlib import Path

from motionworld.data import load_episode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    args = parser.parse_args()

    episode = load_episode(args.episode)
    stats = episode.header["recorder_stats"]
    print(
        "valid=true",
        f"episode={episode.episode_id}",
        f"transitions={len(episode.transitions)}",
        f"attempted={stats['attempted_transition_count']}",
        f"rejected={stats['rejected_transition_count']}",
        f"capacity_drops={stats['capacity_drop_count']}",
        f"path={episode.path.resolve()}",
    )


if __name__ == "__main__":
    main()
