"""Frozen validation-only CEM budget-sweep contract."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from motionworld.planning.cem import CEMConfig, FloatArray

SELECTION_RULE = "eligible_then_lowest_worst_model_mean_positive_regret_then_lowest_residual_p95"


def _mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], *, context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _positive_int(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def _finite_positive(value: object, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a finite positive number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{context} must be a finite positive number")
    return result


@dataclass(frozen=True, slots=True)
class SweepBudget:
    name: str
    num_candidates: int
    num_elites: int
    num_iterations: int

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError("budget name must be non-empty and alphanumeric/underscore")
        for field in ("num_candidates", "num_elites", "num_iterations"):
            _positive_int(getattr(self, field), context=f"budget {field}")
        if self.num_elites > self.num_candidates:
            raise ValueError("budget elites cannot exceed candidates")


@dataclass(frozen=True, slots=True)
class ValidationQueryIndex:
    episode_id: int
    transition_index: int

    def __post_init__(self) -> None:
        _positive_int(self.episode_id, context="validation episode_id")
        if (
            isinstance(self.transition_index, bool)
            or not isinstance(self.transition_index, int)
            or self.transition_index < 0
        ):
            raise ValueError("validation transition_index must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class CEMBudgetSweep:
    status: str
    claim_boundary: str
    reference: SweepBudget
    validation_queries: tuple[ValidationQueryIndex, ...]
    candidates: tuple[SweepBudget, ...]
    maximum_p95_positive_relative_regret: float
    maximum_new_predicted_collisions: int
    deadline_ms: float
    warmups_per_controller: int
    repetitions_per_controller: int
    torch_threads: int
    selection_rule: str

    def __post_init__(self) -> None:
        if not self.status or not self.claim_boundary:
            raise ValueError("sweep status and claim boundary must be non-empty")
        if not self.validation_queries or len(set(self.validation_queries)) != len(
            self.validation_queries
        ):
            raise ValueError("validation queries must be non-empty and unique")
        names = [candidate.name for candidate in self.candidates]
        if not names or len(names) != len(set(names)):
            raise ValueError("candidate budget names must be non-empty and unique")
        if not math.isfinite(self.maximum_p95_positive_relative_regret) or not (
            0.0 <= self.maximum_p95_positive_relative_regret <= 1.0
        ):
            raise ValueError("maximum regret must be finite and in [0, 1]")
        if (
            isinstance(self.maximum_new_predicted_collisions, bool)
            or not isinstance(self.maximum_new_predicted_collisions, int)
            or self.maximum_new_predicted_collisions < 0
        ):
            raise ValueError("maximum new collisions must be a non-negative integer")
        _finite_positive(self.deadline_ms, context="runtime deadline")
        _positive_int(self.warmups_per_controller, context="runtime warmups")
        _positive_int(self.repetitions_per_controller, context="runtime repetitions")
        _positive_int(self.torch_threads, context="torch threads")
        if self.selection_rule != SELECTION_RULE:
            raise ValueError("unsupported selection rule")
        reference_ratio = self.reference.num_elites / self.reference.num_candidates
        for candidate in self.candidates:
            if candidate.num_candidates > self.reference.num_candidates:
                raise ValueError("candidate count cannot exceed reference count")
            if candidate.num_iterations > self.reference.num_iterations:
                raise ValueError("candidate iterations cannot exceed reference iterations")
            if not math.isclose(
                candidate.num_elites / candidate.num_candidates,
                reference_ratio,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ValueError("candidate budgets must preserve the reference elite fraction")


def load_cem_budget_sweep(path: Path) -> CEMBudgetSweep:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), context="budget sweep")
    _exact_keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "status",
            "claim_boundary",
            "reference",
            "validation_queries",
            "candidates",
            "quality_gate",
            "runtime_gate",
            "selection_rule",
        },
        context="budget sweep",
    )
    if raw["schema_name"] != "motionworld_cem_budget_sweep" or raw["schema_version"] != 1:
        raise ValueError("unsupported budget-sweep schema")

    def budget(value: object, *, context: str, reference: bool = False) -> SweepBudget:
        record = _mapping(value, context=context)
        expected = {"num_candidates", "num_elites", "num_iterations"}
        if not reference:
            expected.add("name")
        _exact_keys(record, expected, context=context)
        return SweepBudget(
            name="reference" if reference else record["name"],
            **{name: record[name] for name in ("num_candidates", "num_elites", "num_iterations")},
        )

    query_rows = raw["validation_queries"]
    if not isinstance(query_rows, list):
        raise ValueError("validation_queries must be a list")
    queries: list[ValidationQueryIndex] = []
    for index, value in enumerate(query_rows):
        record = _mapping(value, context=f"validation_queries[{index}]")
        _exact_keys(record, {"episode_id", "transition_index"}, context="validation query")
        queries.append(ValidationQueryIndex(**record))
    candidate_rows = raw["candidates"]
    if not isinstance(candidate_rows, list):
        raise ValueError("candidates must be a list")
    candidates = tuple(
        budget(value, context=f"candidates[{index}]") for index, value in enumerate(candidate_rows)
    )
    quality = _mapping(raw["quality_gate"], context="quality_gate")
    _exact_keys(
        quality,
        {"maximum_p95_positive_relative_regret", "maximum_new_predicted_collisions"},
        context="quality_gate",
    )
    runtime = _mapping(raw["runtime_gate"], context="runtime_gate")
    _exact_keys(
        runtime,
        {"deadline_ms", "warmups_per_controller", "repetitions_per_controller", "torch_threads"},
        context="runtime_gate",
    )
    return CEMBudgetSweep(
        status=raw["status"],
        claim_boundary=raw["claim_boundary"],
        reference=budget(raw["reference"], context="reference", reference=True),
        validation_queries=tuple(queries),
        candidates=candidates,
        maximum_p95_positive_relative_regret=float(quality["maximum_p95_positive_relative_regret"]),
        maximum_new_predicted_collisions=quality["maximum_new_predicted_collisions"],
        deadline_ms=float(runtime["deadline_ms"]),
        warmups_per_controller=runtime["warmups_per_controller"],
        repetitions_per_controller=runtime["repetitions_per_controller"],
        torch_threads=runtime["torch_threads"],
        selection_rule=raw["selection_rule"],
    )


def derive_cem_config(base: CEMConfig, budget: SweepBudget) -> CEMConfig:
    return replace(
        base,
        num_candidates=budget.num_candidates,
        num_elites=budget.num_elites,
        num_iterations=budget.num_iterations,
    )


def nested_standard_normal_noise(
    reference_noise: FloatArray,
    *,
    config: CEMConfig,
) -> FloatArray:
    noise = np.asarray(reference_noise, dtype=np.float64)
    expected_tail = (config.num_knots, config.action_dim)
    if noise.ndim != 4 or noise.shape[2:] != expected_tail:
        raise ValueError("reference noise shape is incompatible with CEM knots/actions")
    if noise.shape[0] < config.num_iterations or noise.shape[1] < config.num_candidates:
        raise ValueError("reference noise does not cover the requested budget")
    result = noise[: config.num_iterations, : config.num_candidates].copy()
    if result.shape != config.noise_shape:
        raise RuntimeError("nested noise slicing produced the wrong shape")
    return result


def select_eligible_budget(records: list[dict[str, Any]]) -> str | None:
    eligible = [record for record in records if record["eligible"] is True]
    if not eligible:
        return None
    selected = min(
        eligible,
        key=lambda record: (
            record["worst_model_mean_positive_relative_regret"],
            record["runtime"]["residual"]["p95_ms"],
            record["name"],
        ),
    )
    return str(selected["name"])
