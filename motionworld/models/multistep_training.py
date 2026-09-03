"""Contracts and episode-safe windows for recursive residual training."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from numpy.typing import NDArray
from torch import Tensor, nn

from motionworld.data import ValidatedEpisode
from motionworld.dynamics.nominal_episode import (
    current_snapshot_nominal_inputs,
    observable_from_state_record,
)
from motionworld.dynamics.smooth_walking_nominal import smooth_walking_nominal_step
from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_LENGTH,
    encode_residual_step_features,
)
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization


@dataclass(frozen=True, slots=True)
class MultistepTrainingConfig:
    horizon_s: float
    supervision_interval_s: float
    supervision_count: int
    huber_beta: float
    discount_gamma: float
    residual_magnitude_weight: float
    gradient_norm_clip: float
    batch_size: int
    optimizer_steps: int
    learning_rate: float
    weight_decay: float
    trace_interval_steps: int
    seed: int
    hidden_widths: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RecursiveTrainingWindow:
    episode_id: int
    start_transition_sequence: int
    transitions: tuple[dict[str, Any], ...]
    initial_history_features: tuple[NDArray[np.float64], ...]
    supervision_weights: NDArray[np.float64]

    def __post_init__(self) -> None:
        weights = np.asarray(self.supervision_weights, dtype=np.float64)
        if weights.shape != (len(self.transitions),) or not np.isfinite(weights).all():
            raise ValueError("supervision weights must align with window transitions")
        if np.any(weights < 0.0) or not np.any(weights > 0.0):
            raise ValueError(
                "window must contain non-negative supervision with at least one target"
            )
        weights = weights.copy()
        weights.setflags(write=False)
        object.__setattr__(self, "supervision_weights", weights)


@dataclass(frozen=True, slots=True)
class MultistepTraceRow:
    optimizer_step: int
    total_loss: float
    state_loss: float
    residual_magnitude_loss: float
    gradient_norm_before_clip: float


@dataclass(frozen=True, slots=True)
class TrainedMultistepResidual:
    model: ResidualMLP
    history_length: int
    seed: int
    trace: tuple[MultistepTraceRow, ...]


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], *, context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _positive_number(value: object, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be positive and finite")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{context} must be positive and finite")
    return result


def _nonnegative_number(value: object, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be non-negative and finite")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{context} must be non-negative and finite")
    return result


def _positive_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def _literal(value: object, expected: object, *, context: str) -> None:
    if value != expected:
        raise ValueError(f"{context} must be {expected!r}")


def load_multistep_training_config(path: Path) -> MultistepTrainingConfig:
    """Load the exact recursive-training contract and reject semantic drift."""

    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), context="config")
    _exact_keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "status",
            "source_dataset_manifest_sha256",
            "immutable_one_step_baselines",
            "variants",
            "horizon",
            "loss",
            "architecture",
            "optimizer",
            "reproducibility",
        },
        context="config",
    )
    _literal(raw["schema_name"], "motionworld_residual_multistep_training_config", context="schema")
    _literal(raw["schema_version"], 1, context="schema version")
    _literal(raw["status"], "frozen_before_multistep_training", context="status")
    _literal(
        raw["source_dataset_manifest_sha256"],
        "4c5d921194d339ba0617c930ce1ae41497ac5e04b14280c9ea8610bc3cc4d770",
        context="dataset manifest hash",
    )

    baselines = _mapping(raw["immutable_one_step_baselines"], context="baselines")
    _exact_keys(
        baselines,
        {"no_history_checkpoint_sha256", "four_history_checkpoint_sha256"},
        context="baselines",
    )
    expected_hashes = {
        "no_history_checkpoint_sha256": (
            "d979549b30bd01b3a304697074c295caf6c7fa16a4a8e25a08c15eec1da7a4f6"
        ),
        "four_history_checkpoint_sha256": (
            "da4e2281c50b5ff329dd41ea3b02811ba634a35c461923c7afc240c11872c30f"
        ),
    }
    if baselines != expected_hashes:
        raise ValueError("immutable one-step checkpoint hashes changed")

    variants = raw["variants"]
    if variants != [
        {"name": "no_history_multistep", "history_length": 1},
        {"name": "four_history_multistep", "history_length": 4},
    ]:
        raise ValueError("multistep variants must be the frozen matched pair")

    horizon = _mapping(raw["horizon"], context="horizon")
    _exact_keys(
        horizon,
        {
            "duration_s",
            "supervision_interval_s",
            "endpoint_policy",
            "incomplete_window_policy",
            "action_and_dt_policy",
            "parameter_policy",
            "nominal_internal_state_policy",
            "history_policy",
        },
        context="horizon",
    )
    horizon_s = _positive_number(horizon["duration_s"], context="horizon duration")
    interval_s = _positive_number(
        horizon["supervision_interval_s"], context="supervision interval"
    )
    supervision_count = round(horizon_s / interval_s)
    if not math.isclose(supervision_count * interval_s, horizon_s, abs_tol=1.0e-12):
        raise ValueError("horizon must contain an exact number of supervision intervals")
    literals = {
        "endpoint_policy": "first_recorded_boundary_at_or_after_each_supervision_time",
        "incomplete_window_policy": "reject",
        "action_and_dt_policy": "recorded_future_queries_known_to_training_evaluator",
        "parameter_policy": "hold_rollout_start_current_snapshot",
        "nominal_internal_state_policy": "advance_recursively_without_observed_reseeding",
        "history_policy": "three_real_prefix_queries_then_predicted_queries",
    }
    for name, expected in literals.items():
        _literal(horizon[name], expected, context=name)

    loss = _mapping(raw["loss"], context="loss")
    _exact_keys(
        loss,
        {
            "state",
            "huber_beta",
            "discount_gamma_per_supervision_interval",
            "state_reduction",
            "residual_magnitude_weight",
            "residual_magnitude_reduction",
            "residual_output_clipping",
            "gradient_norm_clip",
        },
        context="loss",
    )
    _literal(loss["state"], "normalized_component_huber", context="state loss")
    _literal(
        loss["state_reduction"],
        "weighted_mean_over_windows_boundaries_and_six_components",
        context="state reduction",
    )
    _literal(
        loss["residual_magnitude_reduction"],
        "mean_normalized_squared_output_over_valid_dynamics_steps",
        context="residual reduction",
    )
    _literal(loss["residual_output_clipping"], "none", context="residual clipping")
    gamma = _positive_number(
        loss["discount_gamma_per_supervision_interval"], context="discount gamma"
    )
    if gamma > 1.0:
        raise ValueError("discount gamma must not exceed one")

    architecture = _mapping(raw["architecture"], context="architecture")
    _exact_keys(
        architecture,
        {"hidden_widths", "activation", "zero_initialized_output"},
        context="architecture",
    )
    _literal(architecture["activation"], "silu", context="activation")
    _literal(architecture["zero_initialized_output"], True, context="output initialization")
    widths = architecture["hidden_widths"]
    if not isinstance(widths, list) or not widths:
        raise ValueError("hidden widths must be a non-empty list")
    hidden_widths = tuple(_positive_int(value, context="hidden width") for value in widths)

    optimizer = _mapping(raw["optimizer"], context="optimizer")
    _exact_keys(
        optimizer,
        {
            "name",
            "learning_rate",
            "weight_decay",
            "batch_size",
            "optimizer_steps",
            "batch_sampling",
            "trace_interval_steps",
        },
        context="optimizer",
    )
    _literal(optimizer["name"], "adamw", context="optimizer name")
    _literal(
        optimizer["batch_sampling"],
        "fixed_seed_uniform_windows_with_replacement",
        context="batch sampling",
    )
    reproducibility = _mapping(raw["reproducibility"], context="reproducibility")
    _exact_keys(
        reproducibility,
        {
            "seed",
            "device",
            "dtype",
            "train_both_variants_before_validation",
            "checkpoint_selection",
            "test_policy",
        },
        context="reproducibility",
    )
    _literal(reproducibility["device"], "cpu", context="device")
    _literal(reproducibility["dtype"], "float32", context="dtype")
    _literal(
        reproducibility["train_both_variants_before_validation"],
        True,
        context="variant ordering",
    )
    _literal(
        reproducibility["checkpoint_selection"],
        "fixed_final_optimizer_step_no_validation_early_stopping",
        context="checkpoint selection",
    )
    _literal(
        reproducibility["test_policy"],
        "do_not_collect_or_open_during_training_or_model_selection",
        context="test policy",
    )
    return MultistepTrainingConfig(
        horizon_s=horizon_s,
        supervision_interval_s=interval_s,
        supervision_count=supervision_count,
        huber_beta=_positive_number(loss["huber_beta"], context="Huber beta"),
        discount_gamma=gamma,
        residual_magnitude_weight=_nonnegative_number(
            loss["residual_magnitude_weight"], context="residual magnitude weight"
        ),
        gradient_norm_clip=_positive_number(
            loss["gradient_norm_clip"], context="gradient norm clip"
        ),
        batch_size=_positive_int(optimizer["batch_size"], context="batch size"),
        optimizer_steps=_positive_int(
            optimizer["optimizer_steps"], context="optimizer steps"
        ),
        learning_rate=_positive_number(
            optimizer["learning_rate"], context="learning rate"
        ),
        weight_decay=_nonnegative_number(
            optimizer["weight_decay"], context="weight decay"
        ),
        trace_interval_steps=_positive_int(
            optimizer["trace_interval_steps"], context="trace interval"
        ),
        seed=_positive_int(reproducibility["seed"], context="seed"),
        hidden_widths=hidden_widths,
    )


def _step_feature(transition: dict[str, Any]) -> NDArray[np.float64]:
    inputs = current_snapshot_nominal_inputs(transition)
    nominal = smooth_walking_nominal_step(
        inputs.observable,
        inputs.internal,
        inputs.action,
        parameters=inputs.parameters,
        dt_s=inputs.dt_s,
    )
    return encode_residual_step_features(inputs, nominal.observable_next)


def build_recursive_training_windows(
    episodes: tuple[ValidatedEpisode, ...],
    *,
    history_length: int,
    config: MultistepTrainingConfig,
) -> tuple[RecursiveTrainingWindow, ...]:
    """Build complete within-episode horizons; incomplete tails are rejected."""

    if history_length not in (1, RESIDUAL_HISTORY_LENGTH):
        raise ValueError(f"history_length must be 1 or {RESIDUAL_HISTORY_LENGTH}")
    episode_ids = [episode.episode_id for episode in episodes]
    if len(episode_ids) != len(set(episode_ids)):
        raise ValueError("training episode IDs must be unique")
    windows: list[RecursiveTrainingWindow] = []
    for episode in episodes:
        transitions = episode.transitions
        for start_index in range(history_length - 1, len(transitions)):
            elapsed_s = 0.0
            next_boundary = config.supervision_interval_s
            boundary_index = 0
            selected: list[dict[str, Any]] = []
            weights: list[float] = []
            for transition in transitions[start_index:]:
                event = transition.get("external_perturbation")
                if isinstance(event, dict) and event.get("type") != "none":
                    selected = []
                    break
                selected.append(transition)
                elapsed_s += float(transition["delta_time_s"])
                weight = 0.0
                while (
                    boundary_index < config.supervision_count
                    and elapsed_s + 1.0e-12 >= next_boundary
                ):
                    weight += config.discount_gamma**boundary_index
                    boundary_index += 1
                    next_boundary = (boundary_index + 1) * config.supervision_interval_s
                weights.append(weight)
                if boundary_index == config.supervision_count:
                    break
            if boundary_index != config.supervision_count:
                continue
            prefix = tuple(
                _step_feature(transitions[index])
                for index in range(start_index - history_length + 1, start_index)
            )
            windows.append(
                RecursiveTrainingWindow(
                    episode_id=episode.episode_id,
                    start_transition_sequence=int(
                        transitions[start_index]["transition_sequence"]
                    ),
                    transitions=tuple(selected),
                    initial_history_features=prefix,
                    supervision_weights=np.asarray(weights, dtype=np.float64),
                )
            )
    if not windows:
        raise ValueError("no complete recursive training windows")
    return tuple(windows)


def window_masks(
    windows: tuple[RecursiveTrainingWindow, ...],
) -> tuple[Tensor, Tensor]:
    """Return padded dynamics-valid and supervision-weight matrices."""

    if not windows:
        raise ValueError("windows must not be empty")
    width = max(len(window.transitions) for window in windows)
    valid = torch.zeros((len(windows), width), dtype=torch.bool)
    supervision = torch.zeros((len(windows), width), dtype=torch.float32)
    for index, window in enumerate(windows):
        length = len(window.transitions)
        valid[index, :length] = True
        supervision[index, :length] = torch.as_tensor(
            window.supervision_weights.copy(), dtype=torch.float32
        )
    return valid, supervision


def discounted_recursive_loss(
    state_error_normalized: Tensor,
    predicted_residual_normalized: Tensor,
    valid_mask: Tensor,
    supervision_weights: Tensor,
    *,
    huber_beta: float,
    residual_magnitude_weight: float,
) -> tuple[Tensor, Tensor, Tensor]:
    """Compute the frozen discounted state loss plus correction regularizer."""

    if state_error_normalized.shape != predicted_residual_normalized.shape:
        raise ValueError("state errors and residual predictions must have equal shape")
    if state_error_normalized.ndim != 3 or state_error_normalized.shape[2] != 6:
        raise ValueError("recursive tensors must have shape [batch, step, 6]")
    if valid_mask.shape != state_error_normalized.shape[:2]:
        raise ValueError("valid mask must align with batch and step dimensions")
    if supervision_weights.shape != valid_mask.shape:
        raise ValueError("supervision weights must align with valid mask")
    if valid_mask.dtype is not torch.bool:
        raise ValueError("valid mask must be boolean")
    if torch.any(supervision_weights < 0) or torch.any(
        supervision_weights[~valid_mask] != 0
    ):
        raise ValueError("supervision weights must be non-negative and valid-step-only")
    if not torch.any(supervision_weights > 0):
        raise ValueError("at least one supervised boundary is required")
    if not math.isfinite(huber_beta) or huber_beta <= 0.0:
        raise ValueError("Huber beta must be positive and finite")
    if not math.isfinite(residual_magnitude_weight) or residual_magnitude_weight < 0.0:
        raise ValueError("residual magnitude weight must be non-negative and finite")

    component_loss = nn.functional.smooth_l1_loss(
        state_error_normalized,
        torch.zeros_like(state_error_normalized),
        beta=huber_beta,
        reduction="none",
    )
    per_step_state = component_loss.mean(dim=2)
    state_loss = torch.sum(per_step_state * supervision_weights) / torch.sum(
        supervision_weights
    )
    valid = valid_mask.unsqueeze(2).expand_as(predicted_residual_normalized)
    residual_loss = torch.mean(predicted_residual_normalized[valid].square())
    total = state_loss + residual_magnitude_weight * residual_loss
    return total, state_loss, residual_loss


def _wrap(value: Tensor) -> Tensor:
    return torch.remainder(value + math.pi, math.tau) - math.pi


def _safe_normal(value: Tensor) -> Tensor:
    squared = torch.sum(value.square())
    denominator = torch.sqrt(torch.clamp(squared, min=1.0e-8))
    return torch.where(squared < 1.0e-8, torch.zeros_like(value), value / denominator)


def _inv_exp(value: Tensor) -> Tensor:
    return 1.0 / (
        1.0 + 1.00746054 * value + 0.45053901 * value.square() + 0.25724632 * value**3
    )


def _smooth(value: Tensor, target: Tensor, dt: Tensor, smoothing_time: Tensor) -> Tensor:
    active = smoothing_time > 1.0e-4
    safe_time = torch.where(active, smoothing_time, torch.ones_like(smoothing_time))
    result = target + (value - target) * _inv_exp(dt / safe_time)
    return torch.where(active, result, target)


def _clamp_size(value: Tensor, maximum: Tensor) -> Tensor:
    length = torch.linalg.vector_norm(value)
    scaled = value * maximum / torch.clamp(length, min=1.0e-30)
    result = torch.where((maximum >= 1.0e-4) & (length > maximum), scaled, value)
    return torch.where(maximum < 1.0e-4, torch.zeros_like(value), result)


def _integrate(
    intermediate: Tensor,
    desired: Tensor,
    acceleration: Tensor,
    interval: Tensor,
    maximum: Tensor,
) -> Tensor:
    difference = desired - intermediate
    delta = acceleration * interval
    value = torch.where(
        torch.dot(difference, delta) < torch.dot(difference, difference),
        intermediate + delta,
        desired,
    )
    return _clamp_size(value, maximum)


def _spring_vector(
    value: Tensor,
    velocity: Tensor,
    target: Tensor,
    smoothing_time: Tensor,
    dt: Tensor,
) -> tuple[Tensor, Tensor]:
    active = smoothing_time >= 1.0e-8
    safe_time = torch.where(active, smoothing_time, torch.ones_like(smoothing_time))
    half_damping = 2.0 / torch.clamp(safe_time, min=1.0e-8)
    displacement = value - target
    combined = velocity + displacement * half_damping
    decay = _inv_exp(half_damping * dt)
    next_value = decay * (displacement + combined * dt) + target
    next_velocity = decay * (velocity - combined * half_damping * dt)
    return (
        torch.where(active, next_value, target),
        torch.where(active, next_velocity, torch.zeros_like(velocity)),
    )


def _spring_angle(
    angle: Tensor,
    velocity: Tensor,
    target: Tensor,
    smoothing_time: Tensor,
    dt: Tensor,
) -> tuple[Tensor, Tensor]:
    active = smoothing_time >= 1.0e-8
    safe_time = torch.where(active, smoothing_time, torch.ones_like(smoothing_time))
    half_damping = 2.0 / torch.clamp(safe_time, min=1.0e-8)
    displacement = _wrap(angle - target)
    combined = velocity + displacement * half_damping
    decay = _inv_exp(half_damping * dt)
    next_angle = decay * (displacement + combined * dt) + target
    next_velocity = decay * (velocity - combined * half_damping * dt)
    return (
        torch.where(active, next_angle, target),
        torch.where(active, next_velocity, torch.zeros_like(velocity)),
    )


def _world_from_local(value: Tensor, yaw: Tensor) -> Tensor:
    cosine = torch.cos(yaw)
    sine = torch.sin(yaw)
    return torch.stack(
        (value[0] * cosine - value[1] * sine, value[0] * sine + value[1] * cosine)
    )


def _local_from_world(value: Tensor, yaw: Tensor) -> Tensor:
    cosine = torch.cos(yaw)
    sine = torch.sin(yaw)
    return torch.stack(
        (value[0] * cosine + value[1] * sine, -value[0] * sine + value[1] * cosine)
    )


def _tensor_state(transition: dict[str, Any]) -> tuple[dict[str, Tensor], Any, Tensor]:
    inputs = current_snapshot_nominal_inputs(transition)
    observable = inputs.observable
    internal = inputs.internal
    state = {
        "position": torch.tensor(observable.position_world_cm, dtype=torch.float32),
        "velocity": torch.tensor(observable.velocity_world_cm_s, dtype=torch.float32),
        "facing": torch.tensor(observable.facing_yaw_rad, dtype=torch.float32),
        "yaw_rate": torch.tensor(
            math.radians(observable.angular_velocity_yaw_deg_s), dtype=torch.float32
        ),
        "spring_velocity": torch.tensor(
            internal.velocity.spring_velocity_world_cm_s, dtype=torch.float32
        ),
        "spring_acceleration": torch.tensor(
            internal.velocity.spring_acceleration_world_cm_s2, dtype=torch.float32
        ),
        "intermediate_velocity": torch.tensor(
            internal.velocity.intermediate_velocity_world_cm_s, dtype=torch.float32
        ),
        "intermediate_facing": torch.tensor(
            internal.facing.intermediate_facing_yaw_rad, dtype=torch.float32
        ),
        "intermediate_yaw_rate": torch.tensor(
            internal.facing.intermediate_angular_velocity_yaw_rad_s,
            dtype=torch.float32,
        ),
    }
    preparation = transition["nominal_context"]["previous"]["input_preparation"]
    if not preparation["has_max_move_speed"]:
        raise ValueError("recursive training requires an explicit maximum speed")
    maximum_speed = torch.tensor(
        preparation["effective_max_speed_cm_per_s"], dtype=torch.float32
    )
    return state, inputs.parameters, maximum_speed


def _parameter_features(parameters: Any) -> Tensor:
    return torch.tensor(
        [
            parameters.acceleration_cm_s2,
            parameters.deceleration_cm_s2,
            parameters.directional_acceleration_factor,
            parameters.turning_strength_s_inv,
            parameters.acceleration_smoothing_time_s,
            parameters.deceleration_smoothing_time_s,
            parameters.acceleration_smoothing_compensation,
            parameters.deceleration_smoothing_compensation,
            parameters.velocity_deadzone_cm_s,
            parameters.acceleration_deadzone_cm_s2,
            parameters.outside_influence_smoothing_time_s,
            parameters.facing_smoothing_time_s,
            float(parameters.smooth_facing_with_double_spring),
            math.radians(parameters.facing_deadzone_deg),
            math.radians(parameters.angular_velocity_deadzone_deg_s),
        ],
        dtype=torch.float32,
    )


def _nominal_step(
    state: dict[str, Tensor],
    local_action: Tensor,
    dt: Tensor,
    parameters: Any,
    maximum_speed: Tensor,
) -> tuple[dict[str, Tensor], Tensor]:
    local_action = _clamp_size(local_action, maximum_speed)
    planar_desired = _world_from_local(local_action, state["facing"])
    desired = torch.cat((planar_desired, torch.zeros(1)))
    desired_facing = torch.where(
        torch.linalg.vector_norm(local_action) > 1.0e-12,
        torch.atan2(planar_desired[1], planar_desired[0]),
        state["facing"],
    )
    length_product = torch.linalg.vector_norm(state["velocity"]) * torch.linalg.vector_norm(
        state["spring_velocity"]
    )
    match = torch.clamp(
        torch.dot(state["spring_velocity"], state["velocity"])
        / torch.clamp(length_product, min=1.0e-8),
        0.0,
        1.0,
    )
    match_active = match < 1.0
    outside_time = torch.tensor(
        parameters.outside_influence_smoothing_time_s + 1.0e-4
    ) / torch.where(match_active, 1.0 - match, torch.ones_like(match))
    intermediate = torch.where(
        match_active,
        _smooth(state["intermediate_velocity"], state["velocity"], dt, outside_time),
        state["intermediate_velocity"],
    )
    turning_active = torch.any(torch.abs(desired) > 1.0e-4)
    turning_target = _safe_normal(desired) * torch.linalg.vector_norm(intermediate)
    turn_time = torch.tensor(2.0 / max(parameters.turning_strength_s_inv, 1.0e-8))
    intermediate = torch.where(
        turning_active & (parameters.turning_strength_s_inv > 0.0),
        _smooth(intermediate, turning_target, dt, turn_time),
        intermediate,
    )
    accelerating = 1.01 * torch.sum(desired.square()) > torch.sum(state["velocity"].square())
    lateral = torch.where(
        accelerating,
        torch.tensor(
            (1.0 - parameters.directional_acceleration_factor)
            * parameters.acceleration_cm_s2
        ),
        torch.tensor(parameters.deceleration_cm_s2),
    )
    directional = torch.where(
        accelerating,
        torch.tensor(
            parameters.directional_acceleration_factor * parameters.acceleration_cm_s2
        ),
        torch.tensor(0.0),
    )
    smoothing_time = torch.where(
        accelerating,
        torch.tensor(parameters.acceleration_smoothing_time_s),
        torch.tensor(parameters.deceleration_smoothing_time_s),
    )
    compensation = torch.where(
        accelerating,
        torch.tensor(parameters.acceleration_smoothing_compensation),
        torch.tensor(parameters.deceleration_smoothing_compensation),
    )
    difference = desired - intermediate
    lateral_limit = torch.minimum(
        lateral, torch.linalg.vector_norm(difference) / torch.clamp(dt, min=1.0e-8)
    )
    acceleration = _safe_normal(difference) * lateral_limit + _safe_normal(desired) * directional
    maximum = torch.maximum(
        torch.linalg.vector_norm(intermediate), torch.linalg.vector_norm(desired)
    )
    next_intermediate = _integrate(intermediate, desired, acceleration, dt, maximum)
    track = _integrate(
        intermediate, desired, acceleration, dt + compensation * smoothing_time, maximum
    )
    proposed_velocity, next_spring_acceleration = _spring_vector(
        state["velocity"], state["spring_acceleration"], track, smoothing_time, dt
    )
    velocity_deadzone = torch.sum((desired - proposed_velocity).square()) < (
        parameters.velocity_deadzone_cm_s**2
    )
    proposed_velocity = torch.where(velocity_deadzone, desired, proposed_velocity)
    acceleration_deadzone = torch.sum(next_spring_acceleration.square()) < (
        parameters.acceleration_deadzone_cm_s2**2
    )
    next_spring_acceleration = torch.where(
        velocity_deadzone & acceleration_deadzone,
        torch.zeros_like(next_spring_acceleration),
        next_spring_acceleration,
    )
    if parameters.smooth_facing_with_double_spring:
        intermediate_facing, intermediate_yaw = _spring_angle(
            state["intermediate_facing"],
            state["intermediate_yaw_rate"],
            desired_facing,
            torch.tensor(parameters.facing_smoothing_time_s / 2.0),
            dt,
        )
        updated_facing, proposed_yaw = _spring_angle(
            state["facing"],
            state["yaw_rate"],
            intermediate_facing,
            torch.tensor(parameters.facing_smoothing_time_s / 2.0),
            dt,
        )
    else:
        intermediate_facing = desired_facing
        intermediate_yaw = state["yaw_rate"]
        updated_facing, proposed_yaw = _spring_angle(
            state["facing"],
            state["yaw_rate"],
            desired_facing,
            torch.tensor(parameters.facing_smoothing_time_s),
            dt,
        )
    facing_deadzone = torch.abs(_wrap(updated_facing - desired_facing)) < math.radians(
        parameters.facing_deadzone_deg
    )
    proposed_yaw = torch.where(
        facing_deadzone, _wrap(updated_facing - state["facing"]) / dt, proposed_yaw
    )
    intermediate_facing = torch.where(facing_deadzone, desired_facing, intermediate_facing)
    intermediate_yaw = torch.where(
        facing_deadzone
        & (torch.abs(proposed_yaw) < math.radians(parameters.angular_velocity_deadzone_deg_s)),
        torch.zeros_like(intermediate_yaw),
        intermediate_yaw,
    )
    nominal = {
        "position": state["position"] + proposed_velocity * dt,
        "velocity": proposed_velocity,
        "facing": _wrap(state["facing"] + proposed_yaw * dt),
        "yaw_rate": proposed_yaw,
        "spring_velocity": proposed_velocity,
        "spring_acceleration": next_spring_acceleration,
        "intermediate_velocity": next_intermediate,
        "intermediate_facing": intermediate_facing,
        "intermediate_yaw_rate": intermediate_yaw,
    }
    features = torch.cat(
        (
            _local_from_world(state["velocity"][:2], state["facing"]),
            state["yaw_rate"].reshape(1),
            local_action,
            _wrap(desired_facing - state["facing"]).reshape(1),
            _local_from_world(nominal["position"][:2] - state["position"][:2], state["facing"]),
            _local_from_world(proposed_velocity[:2], state["facing"]),
            _wrap(nominal["facing"] - state["facing"]).reshape(1),
            proposed_yaw.reshape(1),
            dt.reshape(1),
            _parameter_features(parameters),
        )
    )
    return nominal, features


def recursive_window_loss(
    model: ResidualMLP,
    normalization: ResidualNormalization,
    window: RecursiveTrainingWindow,
    *,
    history_length: int,
    config: MultistepTrainingConfig,
) -> tuple[Tensor, Tensor, Tensor]:
    """Evaluate one fully differentiable teacher-forcing-free training window."""

    if history_length != normalization.history_length:
        raise ValueError("history length and normalization differ")
    state, parameters, maximum_speed = _tensor_state(window.transitions[0])
    feature_mean = torch.tensor(normalization.feature_mean, dtype=torch.float32)
    feature_scale = torch.tensor(normalization.feature_scale, dtype=torch.float32)
    target_scale = torch.tensor(normalization.target_scale, dtype=torch.float32)
    history = [
        torch.tensor(value.copy(), dtype=torch.float32)
        for value in window.initial_history_features
    ]
    errors: list[Tensor] = []
    residuals: list[Tensor] = []
    for transition in window.transitions:
        previous_facing = state["facing"]
        action_value = torch.tensor(
            transition["applied_action"]["velocity_local_planar_cm_per_s"][:2],
            dtype=torch.float32,
        )
        dt = torch.tensor(transition["delta_time_s"], dtype=torch.float32)
        nominal, step_features = _nominal_step(
            state, action_value, dt, parameters, maximum_speed
        )
        history.append(step_features)
        history = history[-history_length:]
        if len(history) != history_length:
            raise ValueError("recursive history is not fully initialized")
        raw_features = history[0] if history_length == 1 else torch.cat(history)
        normalized_prediction = model((raw_features - feature_mean) / feature_scale)
        physical = normalized_prediction * target_scale
        position = nominal["position"].clone()
        position[:2] = position[:2] + _world_from_local(physical[:2], previous_facing)
        velocity = nominal["velocity"].clone()
        velocity[:2] = velocity[:2] + _world_from_local(physical[2:4], previous_facing)
        state = {
            **nominal,
            "position": position,
            "velocity": velocity,
            "facing": _wrap(nominal["facing"] + physical[4]),
            "yaw_rate": nominal["yaw_rate"] + physical[5],
        }
        actual = observable_from_state_record(transition["next_state"])
        actual_position = torch.tensor(actual.position_world_cm[:2], dtype=torch.float32)
        actual_velocity = torch.tensor(actual.velocity_world_cm_s[:2], dtype=torch.float32)
        error = torch.cat(
            (
                _local_from_world(state["position"][:2] - actual_position, previous_facing),
                _local_from_world(state["velocity"][:2] - actual_velocity, previous_facing),
                _wrap(state["facing"] - actual.facing_yaw_rad).reshape(1),
                (state["yaw_rate"] - math.radians(actual.angular_velocity_yaw_deg_s)).reshape(1),
            )
        )
        errors.append(error / target_scale)
        residuals.append(normalized_prediction)
    stacked_errors = torch.stack(errors).unsqueeze(0)
    stacked_residuals = torch.stack(residuals).unsqueeze(0)
    valid = torch.ones(stacked_errors.shape[:2], dtype=torch.bool)
    weights = torch.tensor(window.supervision_weights.copy(), dtype=torch.float32).unsqueeze(0)
    return discounted_recursive_loss(
        stacked_errors,
        stacked_residuals,
        valid,
        weights,
        huber_beta=config.huber_beta,
        residual_magnitude_weight=config.residual_magnitude_weight,
    )


def train_multistep_residual_model(
    windows: tuple[RecursiveTrainingWindow, ...],
    normalization: ResidualNormalization,
    *,
    history_length: int,
    config: MultistepTrainingConfig,
    hidden_widths: tuple[int, ...] | None = None,
) -> TrainedMultistepResidual:
    """Train at fixed steps without validation access or intermediate state reseeding."""

    if not windows:
        raise ValueError("recursive training windows must not be empty")
    if history_length != normalization.history_length:
        raise ValueError("history length and normalization differ")
    observed_ids = tuple(sorted({window.episode_id for window in windows}))
    if observed_ids != normalization.train_episode_ids:
        raise ValueError("training windows do not match normalization episode provenance")
    torch.manual_seed(config.seed)
    model = ResidualMLP(
        normalization.feature_width,
        hidden_widths=hidden_widths or config.hidden_widths,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(config.seed + history_length)
    trace: list[MultistepTraceRow] = []
    for optimizer_step in range(1, config.optimizer_steps + 1):
        indices = torch.randint(
            len(windows), (config.batch_size,), generator=generator
        ).tolist()
        losses = [
            recursive_window_loss(
                model,
                normalization,
                windows[index],
                history_length=history_length,
                config=config,
            )
            for index in indices
        ]
        total = torch.stack([loss[0] for loss in losses]).mean()
        state = torch.stack([loss[1] for loss in losses]).mean()
        magnitude = torch.stack([loss[2] for loss in losses]).mean()
        optimizer.zero_grad(set_to_none=True)
        total.backward()
        gradient_norm = nn.utils.clip_grad_norm_(
            model.parameters(), max_norm=config.gradient_norm_clip
        )
        if not torch.isfinite(gradient_norm):
            raise ValueError("recursive training produced a non-finite gradient norm")
        optimizer.step()
        if optimizer_step == 1 or optimizer_step % config.trace_interval_steps == 0:
            trace.append(
                MultistepTraceRow(
                    optimizer_step=optimizer_step,
                    total_loss=float(total.detach()),
                    state_loss=float(state.detach()),
                    residual_magnitude_loss=float(magnitude.detach()),
                    gradient_norm_before_clip=float(gradient_norm.detach()),
                )
            )
    return TrainedMultistepResidual(
        model=model.eval(),
        history_length=history_length,
        seed=config.seed,
        trace=tuple(trace),
    )
