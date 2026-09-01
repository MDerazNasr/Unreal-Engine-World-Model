#!/usr/bin/env python3
"""Plot the Day 2 toy mismatch. SYNTHETIC / NOT UNREAL EVIDENCE."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from motionworld.dynamics.synthetic_backend import (
    SyntheticConfig,
    reset_synthetic,
    run_synthetic_episode,
)

Vec2 = tuple[float, float]


def _clamp_norm(vector: Vec2, maximum: float) -> Vec2:
    length = math.hypot(*vector)
    if length <= maximum or length == 0.0:
        return vector
    scale = maximum / length
    return vector[0] * scale, vector[1] * scale


def _direct_nominal_rollout(
    start_position: Vec2,
    actions: tuple[Vec2, ...],
    config: SyntheticConfig,
) -> tuple[list[Vec2], list[Vec2]]:
    """Lag-free comparison predictor; deliberately not the faithful nominal model."""

    positions = [start_position]
    velocities: list[Vec2] = [(0.0, 0.0)]
    for action in actions:
        previous_velocity = velocities[-1]
        delta = _clamp_norm(
            (action[0] - previous_velocity[0], action[1] - previous_velocity[1]),
            config.max_acceleration_cm_s2 * config.dt_s,
        )
        next_velocity = previous_velocity[0] + delta[0], previous_velocity[1] + delta[1]
        previous_position = positions[-1]
        next_position = (
            previous_position[0]
            + 0.5 * (previous_velocity[0] + next_velocity[0]) * config.dt_s,
            previous_position[1]
            + 0.5 * (previous_velocity[1] + next_velocity[1]) * config.dt_s,
        )
        velocities.append(next_velocity)
        positions.append(next_position)
    return positions, velocities


def build_plot(output: Path) -> None:
    config = SyntheticConfig(gate_x_cm=5000.0, timeout_s=10.0)
    actions = (
        ((260.0, 0.0),) * 12
        + ((180.0, 180.0),) * 12
        + ((260.0, 0.0),) * 10
        + ((0.0, 0.0),) * 10
    )
    seed = 27116
    initial = reset_synthetic(config, seed=seed)
    episode = run_synthetic_episode(
        config,
        seed=seed,
        episode_id=1,
        actions_world_cm_s=actions,
    )
    toy_positions = [initial.state.position_world_cm]
    toy_velocities = [initial.state.velocity_world_cm_s]
    toy_positions.extend(row.next_state.position_world_cm for row in episode.transitions)
    toy_velocities.extend(row.next_state.velocity_world_cm_s for row in episode.transitions)
    nominal_positions, nominal_velocities = _direct_nominal_rollout(
        initial.state.position_world_cm,
        actions,
        config,
    )
    times = [index * config.dt_s for index in range(len(toy_positions))]

    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    axes[0].plot(
        [point[0] for point in nominal_positions],
        [point[1] for point in nominal_positions],
        label="lag-free nominal",
        color="#1f77b4",
    )
    axes[0].plot(
        [point[0] for point in toy_positions],
        [point[1] for point in toy_positions],
        label="synthetic hidden-lag ground truth",
        color="#ff7f0e",
    )
    axes[0].set(xlabel="world X (cm)", ylabel="world Y (cm)", title="Planar rollout")
    axes[0].axis("equal")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    axes[1].plot(
        times,
        [math.hypot(*velocity) for velocity in nominal_velocities],
        label="lag-free nominal",
        color="#1f77b4",
    )
    axes[1].plot(
        times,
        [math.hypot(*velocity) for velocity in toy_velocities],
        label="synthetic hidden-lag ground truth",
        color="#ff7f0e",
    )
    axes[1].set(xlabel="scenario time (s)", ylabel="speed (cm/s)", title="Speed response")
    axes[1].grid(alpha=0.25)
    axes[1].legend()
    figure.suptitle("SYNTHETIC / NOT UNREAL EVIDENCE — controlled hidden-lag mismatch")

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/plots/day2_synthetic_nominal_vs_ground_truth.png"),
    )
    args = parser.parse_args()
    build_plot(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
