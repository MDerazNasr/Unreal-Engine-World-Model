"""Deterministic synthetic 2D dynamics for testing the research pipeline.

SYNTHETIC / NOT UNREAL EVIDENCE. The intentionally visible hidden lag creates a
controlled mismatch for tests and plots. It is not an emulation of Mover.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Literal

Vec2 = tuple[float, float]
Termination = Literal["none", "gate_collision", "success", "timeout"]


@dataclass(frozen=True, slots=True)
class SyntheticConfig:
    dt_s: float = 0.1
    max_action_speed_cm_s: float = 300.0
    max_acceleration_cm_s2: float = 600.0
    hidden_lag_time_constant_s: float = 0.35
    start_x_cm: float = -400.0
    start_y_jitter_cm: float = 20.0
    gate_x_cm: float = 200.0
    gate_y_origin_cm: float = 0.0
    gate_amplitude_cm: float = 120.0
    gate_period_s: float = 4.0
    gate_half_extents_cm: Vec2 = (20.0, 70.0)
    agent_radius_cm: float = 10.0
    timeout_s: float = 5.0
    push_step: int | None = None
    push_velocity_delta_cm_s: Vec2 = (0.0, 0.0)

    def __post_init__(self) -> None:
        scalar_values = (
            self.dt_s,
            self.max_action_speed_cm_s,
            self.max_acceleration_cm_s2,
            self.hidden_lag_time_constant_s,
            self.start_x_cm,
            self.start_y_jitter_cm,
            self.gate_x_cm,
            self.gate_y_origin_cm,
            self.gate_amplitude_cm,
            self.gate_period_s,
            self.agent_radius_cm,
            self.timeout_s,
            *self.gate_half_extents_cm,
            *self.push_velocity_delta_cm_s,
        )
        if not all(math.isfinite(value) for value in scalar_values):
            raise ValueError("synthetic configuration values must be finite")
        if self.dt_s <= 0.0 or self.hidden_lag_time_constant_s <= 0.0:
            raise ValueError("timestep and hidden lag time constant must be positive")
        if self.max_action_speed_cm_s <= 0.0 or self.max_acceleration_cm_s2 < 0.0:
            raise ValueError("action speed must be positive and acceleration non-negative")
        if self.gate_period_s <= 0.0 or self.timeout_s <= 0.0:
            raise ValueError("gate period and timeout must be positive")
        if self.start_y_jitter_cm < 0.0 or self.gate_amplitude_cm < 0.0:
            raise ValueError("jitter and gate amplitude must be non-negative")
        if self.agent_radius_cm < 0.0 or min(self.gate_half_extents_cm) <= 0.0:
            raise ValueError("agent radius must be non-negative and gate extents positive")
        if self.push_step is not None and self.push_step < 0:
            raise ValueError("push_step must be non-negative when provided")


@dataclass(frozen=True, slots=True)
class SyntheticState:
    position_world_cm: Vec2
    velocity_world_cm_s: Vec2
    scenario_time_s: float
    step_index: int


@dataclass(frozen=True, slots=True)
class SyntheticHiddenState:
    lagged_target_velocity_cm_s: Vec2


@dataclass(frozen=True, slots=True)
class SyntheticSnapshot:
    seed: int
    gate_phase_offset_rad: float
    state: SyntheticState
    hidden: SyntheticHiddenState
    termination: Termination = "none"


@dataclass(frozen=True, slots=True)
class SyntheticGateState:
    center_world_cm: Vec2
    velocity_world_cm_s: Vec2
    phase_rad: float


@dataclass(frozen=True, slots=True)
class SyntheticTransition:
    episode_id: int
    sequence_id: int
    previous_state: SyntheticState
    requested_action_world_cm_s: Vec2
    previous_hidden_state: SyntheticHiddenState
    next_hidden_state: SyntheticHiddenState
    applied_push_velocity_delta_cm_s: Vec2
    next_state: SyntheticState
    gate_state: SyntheticGateState
    collision: bool
    termination: Termination


@dataclass(frozen=True, slots=True)
class SyntheticEpisode:
    label: str
    episode_id: int
    seed: int
    transitions: tuple[SyntheticTransition, ...]
    final_termination: Termination


def _add(left: Vec2, right: Vec2) -> Vec2:
    return left[0] + right[0], left[1] + right[1]


def _subtract(left: Vec2, right: Vec2) -> Vec2:
    return left[0] - right[0], left[1] - right[1]


def _scale(vector: Vec2, scale: float) -> Vec2:
    return vector[0] * scale, vector[1] * scale


def _norm(vector: Vec2) -> float:
    return math.hypot(*vector)


def _clamp_norm(vector: Vec2, maximum: float) -> Vec2:
    length = _norm(vector)
    if length <= maximum or length == 0.0:
        return vector
    return _scale(vector, maximum / length)


def reset_synthetic(config: SyntheticConfig, *, seed: int) -> SyntheticSnapshot:
    """Create a deterministic initial observable and hidden state from one seed."""

    if seed < 0:
        raise ValueError("seed must be non-negative")
    generator = random.Random(seed)
    phase = generator.uniform(0.0, 2.0 * math.pi)
    start_y = generator.uniform(-config.start_y_jitter_cm, config.start_y_jitter_cm)
    return SyntheticSnapshot(
        seed=seed,
        gate_phase_offset_rad=phase,
        state=SyntheticState((config.start_x_cm, start_y), (0.0, 0.0), 0.0, 0),
        hidden=SyntheticHiddenState((0.0, 0.0)),
    )


def evaluate_synthetic_gate(
    config: SyntheticConfig,
    *,
    scenario_time_s: float,
    phase_offset_rad: float,
) -> SyntheticGateState:
    """Evaluate the sideways gate directly from absolute scenario time."""

    if not math.isfinite(scenario_time_s) or scenario_time_s < 0.0:
        raise ValueError("scenario_time_s must be finite and non-negative")
    angular_frequency = 2.0 * math.pi / config.gate_period_s
    unwrapped_phase = phase_offset_rad + angular_frequency * scenario_time_s
    phase = unwrapped_phase % (2.0 * math.pi)
    return SyntheticGateState(
        center_world_cm=(
            config.gate_x_cm,
            config.gate_y_origin_cm + config.gate_amplitude_cm * math.sin(unwrapped_phase),
        ),
        velocity_world_cm_s=(
            0.0,
            config.gate_amplitude_cm * angular_frequency * math.cos(unwrapped_phase),
        ),
        phase_rad=phase,
    )


def _segment_overlaps_gate(
    start: Vec2,
    end: Vec2,
    gate: SyntheticGateState,
    config: SyntheticConfig,
) -> bool:
    extent_x = config.gate_half_extents_cm[0] + config.agent_radius_cm
    extent_y = config.gate_half_extents_cm[1] + config.agent_radius_cm
    minimum = gate.center_world_cm[0] - extent_x, gate.center_world_cm[1] - extent_y
    maximum = gate.center_world_cm[0] + extent_x, gate.center_world_cm[1] + extent_y
    direction = _subtract(end, start)
    entry, exit_ = 0.0, 1.0
    for axis in range(2):
        if abs(direction[axis]) <= 1e-12:
            if start[axis] < minimum[axis] or start[axis] > maximum[axis]:
                return False
            continue
        first = (minimum[axis] - start[axis]) / direction[axis]
        second = (maximum[axis] - start[axis]) / direction[axis]
        axis_entry, axis_exit = min(first, second), max(first, second)
        entry, exit_ = max(entry, axis_entry), min(exit_, axis_exit)
        if entry > exit_:
            return False
    return True


def step_synthetic(
    config: SyntheticConfig,
    snapshot: SyntheticSnapshot,
    action_world_cm_s: Vec2,
    *,
    episode_id: int,
) -> tuple[SyntheticSnapshot, SyntheticTransition]:
    """Advance one deterministic step and return a complete conceptual transition."""

    if snapshot.termination != "none":
        raise RuntimeError("cannot step a terminated synthetic episode")
    if episode_id < 0 or len(action_world_cm_s) != 2:
        raise ValueError("episode ID must be non-negative and action must be planar")
    action = float(action_world_cm_s[0]), float(action_world_cm_s[1])
    if not all(math.isfinite(value) for value in action):
        raise ValueError("action must be finite")
    if _norm(action) > config.max_action_speed_cm_s + 1e-12:
        raise ValueError("action exceeds the legal synthetic speed range")

    previous = snapshot.state
    alpha = 1.0 - math.exp(-config.dt_s / config.hidden_lag_time_constant_s)
    lagged = _add(snapshot.hidden.lagged_target_velocity_cm_s, _scale(
        _subtract(action, snapshot.hidden.lagged_target_velocity_cm_s), alpha
    ))
    next_hidden = SyntheticHiddenState(lagged)

    push = (0.0, 0.0)
    if config.push_step is not None and previous.step_index == config.push_step:
        push = config.push_velocity_delta_cm_s
    velocity_after_push = _add(previous.velocity_world_cm_s, push)
    velocity_change = _clamp_norm(
        _subtract(lagged, velocity_after_push),
        config.max_acceleration_cm_s2 * config.dt_s,
    )
    velocity_next = _add(velocity_after_push, velocity_change)
    position_next = _add(
        previous.position_world_cm,
        _scale(_add(velocity_after_push, velocity_next), 0.5 * config.dt_s),
    )
    next_state = SyntheticState(
        position_next,
        velocity_next,
        previous.scenario_time_s + config.dt_s,
        previous.step_index + 1,
    )
    gate = evaluate_synthetic_gate(
        config,
        scenario_time_s=next_state.scenario_time_s,
        phase_offset_rad=snapshot.gate_phase_offset_rad,
    )
    collision = _segment_overlaps_gate(previous.position_world_cm, position_next, gate, config)
    crossed = previous.position_world_cm[0] <= config.gate_x_cm < position_next[0]
    termination: Termination = "none"
    if collision:
        termination = "gate_collision"
    elif crossed:
        termination = "success"
    elif next_state.scenario_time_s >= config.timeout_s:
        termination = "timeout"

    transition = SyntheticTransition(
        episode_id=episode_id,
        sequence_id=previous.step_index,
        previous_state=previous,
        requested_action_world_cm_s=action,
        previous_hidden_state=snapshot.hidden,
        next_hidden_state=next_hidden,
        applied_push_velocity_delta_cm_s=push,
        next_state=next_state,
        gate_state=gate,
        collision=collision,
        termination=termination,
    )
    return (
        SyntheticSnapshot(
            snapshot.seed,
            snapshot.gate_phase_offset_rad,
            next_state,
            next_hidden,
            termination,
        ),
        transition,
    )


def run_synthetic_episode(
    config: SyntheticConfig,
    *,
    seed: int,
    episode_id: int,
    actions_world_cm_s: tuple[Vec2, ...],
) -> SyntheticEpisode:
    """Run until actions are exhausted or a terminal event occurs."""

    snapshot = reset_synthetic(config, seed=seed)
    transitions: list[SyntheticTransition] = []
    for action in actions_world_cm_s:
        snapshot, transition = step_synthetic(config, snapshot, action, episode_id=episode_id)
        transitions.append(transition)
        if snapshot.termination != "none":
            break
    return SyntheticEpisode(
        label="SYNTHETIC / NOT UNREAL EVIDENCE",
        episode_id=episode_id,
        seed=seed,
        transitions=tuple(transitions),
        final_termination=snapshot.termination,
    )
