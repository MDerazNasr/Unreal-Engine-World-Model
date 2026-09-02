"""Fixed-seed Cross-Entropy Method optimizer for bounded velocity plans.

Tensor convention:

* standard noise and knot candidates: ``[iteration, candidate, knot, action]``;
* one iteration of knot candidates: ``[candidate, knot, action]``;
* expanded model actions: ``[candidate, model_step, action]``;
* distribution mean and standard deviation: ``[knot, action]``.

The optimizer is transition-model agnostic.  Its callback receives the complete
expanded candidate batch and returns one scalar cost per candidate.  Lower cost
is always better.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
CostFunction = Callable[[FloatArray], FloatArray]


@dataclass(frozen=True, slots=True)
class CEMConfig:
    """All fairness-critical dimensions and optimizer settings."""

    num_candidates: int = 256
    num_elites: int = 32
    num_iterations: int = 3
    num_knots: int = 15
    num_model_steps: int = 45
    action_dim: int = 2
    max_action_speed_cm_s: float = 165.0
    initial_std_cm_s: float = 110.0
    minimum_std_cm_s: float = 5.0
    momentum: float = 0.1
    include_mean_candidate: bool = True

    def __post_init__(self) -> None:
        integer_values = (
            self.num_candidates,
            self.num_elites,
            self.num_iterations,
            self.num_knots,
            self.num_model_steps,
            self.action_dim,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in integer_values
        ):
            raise ValueError("CEM dimensions and counts must be positive integers")
        if self.action_dim != 2:
            raise ValueError("MotionWorld CEM requires exactly two planar velocity components")
        if self.num_elites > self.num_candidates:
            raise ValueError("num_elites cannot exceed num_candidates")
        scalars = (
            self.max_action_speed_cm_s,
            self.initial_std_cm_s,
            self.minimum_std_cm_s,
            self.momentum,
        )
        if not all(math.isfinite(value) for value in scalars):
            raise ValueError("CEM scalar settings must be finite")
        if self.max_action_speed_cm_s <= 0.0 or self.initial_std_cm_s < 0.0:
            raise ValueError("maximum action speed must be positive and initial std non-negative")
        if self.minimum_std_cm_s < 0.0:
            raise ValueError("minimum std must be non-negative")
        if not 0.0 <= self.momentum < 1.0:
            raise ValueError("momentum must be in [0, 1)")
        if not isinstance(self.include_mean_candidate, bool):
            raise ValueError("include_mean_candidate must be boolean")

    @property
    def noise_shape(self) -> tuple[int, int, int, int]:
        return (
            self.num_iterations,
            self.num_candidates,
            self.num_knots,
            self.action_dim,
        )


@dataclass(frozen=True, slots=True)
class CEMState:
    mean_knots_cm_s: FloatArray
    std_knots_cm_s: FloatArray


@dataclass(frozen=True, slots=True)
class CEMIteration:
    iteration: int
    best_cost: float
    finite_candidate_count: int
    mean_knots_cm_s: FloatArray
    std_knots_cm_s: FloatArray
    best_knots_cm_s: FloatArray
    candidate_first_actions_cm_s: FloatArray


@dataclass(frozen=True, slots=True)
class CEMResult:
    first_action_cm_s: FloatArray
    best_knots_cm_s: FloatArray
    best_actions_cm_s: FloatArray
    best_cost: float
    final_state: CEMState
    iterations: tuple[CEMIteration, ...]
    used_safe_fallback: bool
    fallback_reason: str | None


def _require_shape(name: str, values: FloatArray, shape: tuple[int, ...]) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def sample_standard_normal_schedule(config: CEMConfig, *, seed: int) -> FloatArray:
    """Generate reusable common random numbers for a complete CEM solve."""

    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    generator = np.random.Generator(np.random.PCG64(seed))
    noise = generator.standard_normal(config.noise_shape, dtype=np.float64)
    if config.include_mean_candidate:
        noise[:, 0, :, :] = 0.0
    return noise


def project_velocity_actions(actions_cm_s: FloatArray, *, maximum_speed_cm_s: float) -> FloatArray:
    """Project each planar action onto the closed L2 speed ball."""

    values = np.asarray(actions_cm_s, dtype=np.float64)
    if values.ndim < 1 or values.shape[-1] != 2:
        raise ValueError("velocity actions must end in exactly two planar components")
    if not np.all(np.isfinite(values)):
        raise ValueError("velocity actions must be finite")
    if not math.isfinite(maximum_speed_cm_s) or maximum_speed_cm_s <= 0.0:
        raise ValueError("maximum_speed_cm_s must be positive and finite")
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    scale = np.minimum(1.0, maximum_speed_cm_s / np.maximum(norms, 1.0e-300))
    return values * scale


def expand_action_knots(knots_cm_s: FloatArray, *, num_model_steps: int) -> FloatArray:
    """Hold piecewise-constant knots across an exact number of model steps."""

    knots = np.asarray(knots_cm_s, dtype=np.float64)
    if knots.ndim < 2:
        raise ValueError("knots must have at least knot and action dimensions")
    if not np.all(np.isfinite(knots)):
        raise ValueError("knots must be finite")
    if isinstance(num_model_steps, bool) or num_model_steps <= 0:
        raise ValueError("num_model_steps must be a positive integer")
    num_knots = knots.shape[-2]
    if num_knots <= 0:
        raise ValueError("knots cannot be empty")
    indices = np.floor(np.arange(num_model_steps) * num_knots / num_model_steps).astype(int)
    return np.take(knots, indices, axis=-2)


def shift_action_knots(knots_cm_s: FloatArray, *, executed_knots: int = 1) -> FloatArray:
    """Drop executed controls and repeat the last knot to preserve horizon length."""

    knots = np.asarray(knots_cm_s, dtype=np.float64)
    if knots.ndim != 2 or knots.shape[0] == 0:
        raise ValueError("knots must have shape [knot, action] and be non-empty")
    if not np.all(np.isfinite(knots)):
        raise ValueError("knots must be finite")
    if isinstance(executed_knots, bool) or not 0 <= executed_knots <= knots.shape[0]:
        raise ValueError("executed_knots must be between zero and the knot count")
    if executed_knots == 0:
        return knots.copy()
    retained = knots[executed_knots:]
    tail = np.repeat(knots[-1:, :], executed_knots, axis=0)
    return np.concatenate((retained, tail), axis=0)


def update_elite_distribution(
    old_state: CEMState,
    elite_knots_cm_s: FloatArray,
    *,
    momentum: float,
    minimum_std_cm_s: float,
) -> CEMState:
    """Apply population elite moments, momentum, and an elementwise std floor."""

    mean = np.asarray(old_state.mean_knots_cm_s, dtype=np.float64)
    std = np.asarray(old_state.std_knots_cm_s, dtype=np.float64)
    if mean.shape != std.shape or mean.ndim != 2:
        raise ValueError("CEM state arrays must share shape [knot, action]")
    elites = np.asarray(elite_knots_cm_s, dtype=np.float64)
    if elites.ndim != 3 or elites.shape[1:] != mean.shape or elites.shape[0] == 0:
        raise ValueError("elites must have shape [elite, knot, action]")
    if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)):
        raise ValueError("CEM state must be finite")
    if np.any(std < 0.0) or not np.all(np.isfinite(elites)):
        raise ValueError("standard deviation must be non-negative and elites finite")
    if not math.isfinite(momentum) or not 0.0 <= momentum < 1.0:
        raise ValueError("momentum must be in [0, 1)")
    if not math.isfinite(minimum_std_cm_s) or minimum_std_cm_s < 0.0:
        raise ValueError("minimum_std_cm_s must be finite and non-negative")

    elite_mean = np.mean(elites, axis=0)
    elite_variance = np.mean(np.square(elites - elite_mean), axis=0)
    new_mean = momentum * mean + (1.0 - momentum) * elite_mean
    mixed_variance = momentum * np.square(std) + (1.0 - momentum) * elite_variance
    new_std = np.maximum(np.sqrt(mixed_variance), minimum_std_cm_s)
    return CEMState(new_mean.copy(), new_std.copy())


def _initial_state(config: CEMConfig, initial_mean_knots_cm_s: FloatArray | None) -> CEMState:
    shape = (config.num_knots, config.action_dim)
    if initial_mean_knots_cm_s is None:
        mean = np.zeros(shape, dtype=np.float64)
    else:
        mean = _require_shape("initial_mean_knots_cm_s", initial_mean_knots_cm_s, shape).copy()
    if config.action_dim == 2:
        mean = project_velocity_actions(mean, maximum_speed_cm_s=config.max_action_speed_cm_s)
    std = np.full(
        shape,
        max(config.initial_std_cm_s, config.minimum_std_cm_s),
        dtype=np.float64,
    )
    return CEMState(mean, std)


def _safe_result(config: CEMConfig, state: CEMState, reason: str) -> CEMResult:
    knots = np.zeros((config.num_knots, config.action_dim), dtype=np.float64)
    return CEMResult(
        first_action_cm_s=knots[0].copy(),
        best_knots_cm_s=knots,
        best_actions_cm_s=expand_action_knots(knots, num_model_steps=config.num_model_steps),
        best_cost=math.inf,
        final_state=state,
        iterations=(),
        used_safe_fallback=True,
        fallback_reason=reason,
    )


def optimize_cem(
    cost_function: CostFunction,
    *,
    config: CEMConfig,
    seed: int | None = None,
    standard_normal_noise: FloatArray | None = None,
    initial_mean_knots_cm_s: FloatArray | None = None,
) -> CEMResult:
    """Minimize a batched trajectory cost and return the best candidate's first action.

    Exactly one of ``seed`` and ``standard_normal_noise`` must be supplied.  Supplying reusable
    standard-normal noise is the fair-comparison seam: different dynamics models receive identical
    randomness, while later physical candidates may diverge because their elite costs differ.
    """

    if (seed is None) == (standard_normal_noise is None):
        raise ValueError("provide exactly one of seed or standard_normal_noise")
    noise = (
        sample_standard_normal_schedule(config, seed=seed)
        if standard_normal_noise is None
        else _require_shape("standard_normal_noise", standard_normal_noise, config.noise_shape)
    )
    state = _initial_state(config, initial_mean_knots_cm_s)
    diagnostics: list[CEMIteration] = []
    global_best_cost = math.inf
    global_best_knots: FloatArray | None = None

    for iteration in range(config.num_iterations):
        candidates = state.mean_knots_cm_s + state.std_knots_cm_s * noise[iteration]
        if config.action_dim == 2:
            candidates = project_velocity_actions(
                candidates,
                maximum_speed_cm_s=config.max_action_speed_cm_s,
            )
        expanded = expand_action_knots(candidates, num_model_steps=config.num_model_steps)
        costs = np.asarray(cost_function(expanded), dtype=np.float64)
        if costs.shape != (config.num_candidates,):
            raise ValueError(
                f"cost_function must return shape {(config.num_candidates,)}, got {costs.shape}"
            )
        finite_indices = np.flatnonzero(np.isfinite(costs))
        if finite_indices.size < config.num_elites:
            return _safe_result(config, state, "fewer finite candidate costs than num_elites")
        ordered_finite = finite_indices[np.argsort(costs[finite_indices], kind="stable")]
        elite_indices = ordered_finite[: config.num_elites]
        best_index = int(ordered_finite[0])
        best_cost = float(costs[best_index])
        best_knots = candidates[best_index].copy()
        if best_cost < global_best_cost:
            global_best_cost = best_cost
            global_best_knots = best_knots.copy()
        state = update_elite_distribution(
            state,
            candidates[elite_indices],
            momentum=config.momentum,
            minimum_std_cm_s=config.minimum_std_cm_s,
        )
        diagnostics.append(
            CEMIteration(
                iteration=iteration,
                best_cost=best_cost,
                finite_candidate_count=int(finite_indices.size),
                mean_knots_cm_s=state.mean_knots_cm_s.copy(),
                std_knots_cm_s=state.std_knots_cm_s.copy(),
                best_knots_cm_s=best_knots,
                candidate_first_actions_cm_s=candidates[:, 0, :].copy(),
            )
        )

    if global_best_knots is None:
        return _safe_result(config, state, "no finite candidate was selected")
    best_actions = expand_action_knots(
        global_best_knots,
        num_model_steps=config.num_model_steps,
    )
    return CEMResult(
        first_action_cm_s=best_actions[0].copy(),
        best_knots_cm_s=global_best_knots,
        best_actions_cm_s=best_actions,
        best_cost=global_best_cost,
        final_state=state,
        iterations=tuple(diagnostics),
        used_safe_fallback=False,
        fallback_reason=None,
    )
