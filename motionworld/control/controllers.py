"""Small, stateless controllers used to prove the live R2 control seam."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any

from motionworld.control.config import ControllerConfig

Observation = dict[str, Any]
Action = dict[str, Any] | None


def _clamp_planar(vector: tuple[float, float], maximum: float) -> tuple[float, float]:
    """Magnitude-clamp one finite planar vector without changing its direction."""

    if not all(math.isfinite(value) for value in (*vector, maximum)) or maximum < 0.0:
        raise ValueError("command vector and maximum speed must be finite and non-negative")
    magnitude = math.hypot(*vector)
    if magnitude == 0.0 or magnitude <= maximum:
        return vector
    scale = maximum / magnitude
    return vector[0] * scale, vector[1] * scale


def _effective_limit(observation: Observation, configured_limit: float) -> float:
    observed_limit = float(
        observation["nominal_context"]["input_preparation"][
            "effective_max_speed_cm_per_s"
        ]
    )
    if not math.isfinite(observed_limit) or observed_limit < 0.0:
        raise ValueError("validated observation contains an invalid effective max speed")
    return min(configured_limit, observed_limit)


def _action(
    observation: Observation,
    desired_velocity: tuple[float, float],
    *,
    model_id: str,
    started_us: int,
    is_fallback: bool = False,
    fallback_reason: str = "none",
) -> dict[str, Any]:
    finished_us = time.monotonic_ns() // 1_000
    identity = observation["identity"]
    return {
        "protocol": {
            "name": "motionworld_control",
            "version": 1,
            "message_type": "action",
        },
        "identity": {
            "episode_id": identity["episode_id"],
            "source_observation_sequence": identity["observation_sequence"],
        },
        "command": {
            "desired_velocity_local_cm_per_s": [
                desired_velocity[0],
                desired_velocity[1],
            ]
        },
        "controller": {
            "controller_id": observation["source"]["controller_mode"],
            "model_id": model_id,
        },
        "planner": {
            "started_monotonic_us": started_us,
            "finished_monotonic_us": finished_us,
            "measured_latency_ms": (finished_us - started_us) / 1_000.0,
        },
        "fallback": {
            "is_safe_fallback": is_fallback,
            "reason": fallback_reason,
        },
        "telemetry": {"is_present": False},
    }


@dataclass(frozen=True, slots=True)
class EchoController:
    """Return one configured local command while echoing source observation identity."""

    config: ControllerConfig

    def __call__(self, observation: Observation, cancelled: threading.Event) -> Action:
        if cancelled.is_set():
            return None
        started_us = time.monotonic_ns() // 1_000
        command = _clamp_planar(
            self.config.echo_velocity_local_cm_per_s,
            _effective_limit(observation, self.config.max_command_speed_cm_per_s),
        )
        if cancelled.is_set():
            return None
        return _action(
            observation,
            command,
            model_id="r2_fixed_echo_v1",
            started_us=started_us,
        )


@dataclass(frozen=True, slots=True)
class ReactiveController:
    """Steer toward the current world-space target using authoritative facing."""

    config: ControllerConfig

    def __call__(self, observation: Observation, cancelled: threading.Event) -> Action:
        if cancelled.is_set():
            return None
        started_us = time.monotonic_ns() // 1_000
        target = observation["planner_context"]["target"]
        if not target["is_present"]:
            return _action(
                observation,
                (0.0, 0.0),
                model_id="r2_goal_reactive_v1",
                started_us=started_us,
                is_fallback=True,
                fallback_reason="invalid_observation",
            )

        position = observation["state"]["position_world_cm"]
        delta_world_x = float(target["position_world_cm"][0]) - float(position[0])
        delta_world_y = float(target["position_world_cm"][1]) - float(position[1])
        distance = math.hypot(delta_world_x, delta_world_y)
        limit = _effective_limit(
            observation,
            min(
                self.config.max_command_speed_cm_per_s,
                self.config.reactive_cruise_speed_cm_per_s,
            ),
        )
        if distance <= self.config.reactive_arrival_radius_cm:
            requested = tuple(target["desired_terminal_velocity_local_cm_per_s"])
            command = _clamp_planar((float(requested[0]), float(requested[1])), limit)
        else:
            facing_x, facing_y = (
                float(value) for value in observation["state"]["facing_unit_world"]
            )
            direction_world_x = delta_world_x / distance
            direction_world_y = delta_world_y / distance
            # R(theta)^T maps world direction into character-local forward/right.
            command = (
                limit * (facing_x * direction_world_x + facing_y * direction_world_y),
                limit * (-facing_y * direction_world_x + facing_x * direction_world_y),
            )
        if cancelled.is_set():
            return None
        return _action(
            observation,
            command,
            model_id="r2_goal_reactive_v1",
            started_us=started_us,
        )


def build_controller(mode: str, config: ControllerConfig) -> EchoController | ReactiveController:
    """Construct only the R2 proof controllers; MPC modes require their later session state."""

    if mode == "echo":
        return EchoController(config)
    if mode == "reactive":
        return ReactiveController(config)
    raise ValueError(f"controller mode {mode!r} is not implemented by the R2 service")
