"""Frozen validation-only residual-network compression contract."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SELECTION_RULE = "eligible_then_lowest_runtime_p95_then_lowest_parameter_count"


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


def _fraction(value: object, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{context} must be finite and in [0, 1]")
    return result


@dataclass(frozen=True, slots=True)
class WidthCandidate:
    name: str
    hidden_widths: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError("candidate name must be alphanumeric/underscore")
        if not self.hidden_widths:
            raise ValueError("candidate must have at least one hidden layer")
        for width in self.hidden_widths:
            _positive_int(width, context="hidden width")


@dataclass(frozen=True, slots=True)
class CompressionQuery:
    episode_id: int
    transition_index: int

    def __post_init__(self) -> None:
        _positive_int(self.episode_id, context="episode_id")
        if (
            isinstance(self.transition_index, bool)
            or not isinstance(self.transition_index, int)
            or self.transition_index < 0
        ):
            raise ValueError("transition_index must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ResidualWidthSweep:
    status: str
    claim_boundary: str
    source_training_config_sha256: str
    source_training_comparison_sha256: str
    reference_checkpoint_sha256: str
    history_length: int
    candidates: tuple[WidthCandidate, ...]
    recursive_horizons_s: tuple[float, ...]
    maximum_recursive_relative_degradation: float
    validation_queries: tuple[CompressionQuery, ...]
    maximum_planner_p95_positive_relative_regret: float
    maximum_new_predicted_collisions: int
    deadline_ms: float
    warmups: int
    repetitions: int
    torch_threads: int
    selection_rule: str

    def __post_init__(self) -> None:
        if not self.status or not self.claim_boundary:
            raise ValueError("status and claim boundary must be non-empty")
        for value in (
            self.source_training_config_sha256,
            self.source_training_comparison_sha256,
            self.reference_checkpoint_sha256,
        ):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError("provenance hashes must be lowercase SHA-256 strings")
        if self.history_length != 1:
            raise ValueError("planner compression sweep requires no-history model")
        names = [candidate.name for candidate in self.candidates]
        if not names or len(names) != len(set(names)):
            raise ValueError("candidate names must be non-empty and unique")
        if not self.recursive_horizons_s or any(
            not math.isfinite(value) or value <= 0.0 for value in self.recursive_horizons_s
        ):
            raise ValueError("recursive horizons must be positive and finite")
        _fraction(
            self.maximum_recursive_relative_degradation,
            context="recursive degradation",
        )
        if not self.validation_queries or len(set(self.validation_queries)) != len(
            self.validation_queries
        ):
            raise ValueError("validation queries must be non-empty and unique")
        _fraction(
            self.maximum_planner_p95_positive_relative_regret,
            context="planner regret",
        )
        if (
            isinstance(self.maximum_new_predicted_collisions, bool)
            or not isinstance(self.maximum_new_predicted_collisions, int)
            or self.maximum_new_predicted_collisions < 0
        ):
            raise ValueError("maximum new collisions must be a non-negative integer")
        if not math.isfinite(self.deadline_ms) or self.deadline_ms <= 0.0:
            raise ValueError("deadline must be positive and finite")
        for value, name in (
            (self.warmups, "warmups"),
            (self.repetitions, "repetitions"),
            (self.torch_threads, "torch threads"),
        ):
            _positive_int(value, context=name)
        if self.selection_rule != SELECTION_RULE:
            raise ValueError("unsupported selection rule")


def load_residual_width_sweep(path: Path) -> ResidualWidthSweep:
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), context="width sweep")
    _exact_keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "status",
            "claim_boundary",
            "source_training_config_sha256",
            "source_training_comparison_sha256",
            "reference_checkpoint_sha256",
            "history_length",
            "candidates",
            "training_policy",
            "recursive_quality_gate",
            "planner_quality_gate",
            "runtime_gate",
            "selection_rule",
        },
        context="width sweep",
    )
    if raw["schema_name"] != "motionworld_residual_width_sweep" or raw["schema_version"] != 1:
        raise ValueError("unsupported residual width-sweep schema")
    training = _mapping(raw["training_policy"], context="training policy")
    _exact_keys(
        training,
        {"inherit_optimizer_loss_normalization_and_seed", "checkpoint_selection"},
        context="training policy",
    )
    if training != {
        "inherit_optimizer_loss_normalization_and_seed": True,
        "checkpoint_selection": "fixed_final_optimizer_step_no_validation_early_stopping",
    }:
        raise ValueError("compression candidates must inherit the frozen training protocol")

    candidate_rows = raw["candidates"]
    if not isinstance(candidate_rows, list):
        raise ValueError("candidates must be a list")
    candidates = []
    for index, value in enumerate(candidate_rows):
        record = _mapping(value, context=f"candidate[{index}]")
        _exact_keys(record, {"name", "hidden_widths"}, context=f"candidate[{index}]")
        widths = record["hidden_widths"]
        if not isinstance(widths, list):
            raise ValueError("hidden_widths must be a list")
        candidates.append(WidthCandidate(str(record["name"]), tuple(widths)))

    recursive = _mapping(raw["recursive_quality_gate"], context="recursive gate")
    _exact_keys(
        recursive,
        {
            "horizons_s",
            "statistic",
            "maximum_relative_degradation_vs_reference",
            "require_all_metrics_and_horizons",
        },
        context="recursive gate",
    )
    if recursive["statistic"] != "p95" or recursive["require_all_metrics_and_horizons"] is not True:
        raise ValueError("recursive gate must require every p95 metric and horizon")
    planner = _mapping(raw["planner_quality_gate"], context="planner gate")
    _exact_keys(
        planner,
        {
            "validation_queries",
            "maximum_p95_positive_relative_regret",
            "maximum_new_predicted_collisions",
        },
        context="planner gate",
    )
    queries = []
    for index, value in enumerate(planner["validation_queries"]):
        record = _mapping(value, context=f"validation query[{index}]")
        _exact_keys(record, {"episode_id", "transition_index"}, context="validation query")
        queries.append(CompressionQuery(**record))
    runtime = _mapping(raw["runtime_gate"], context="runtime gate")
    _exact_keys(
        runtime,
        {"deadline_ms", "warmups", "repetitions", "torch_threads"},
        context="runtime gate",
    )
    return ResidualWidthSweep(
        status=str(raw["status"]),
        claim_boundary=str(raw["claim_boundary"]),
        source_training_config_sha256=str(raw["source_training_config_sha256"]),
        source_training_comparison_sha256=str(raw["source_training_comparison_sha256"]),
        reference_checkpoint_sha256=str(raw["reference_checkpoint_sha256"]),
        history_length=raw["history_length"],
        candidates=tuple(candidates),
        recursive_horizons_s=tuple(float(value) for value in recursive["horizons_s"]),
        maximum_recursive_relative_degradation=float(
            recursive["maximum_relative_degradation_vs_reference"]
        ),
        validation_queries=tuple(queries),
        maximum_planner_p95_positive_relative_regret=float(
            planner["maximum_p95_positive_relative_regret"]
        ),
        maximum_new_predicted_collisions=planner["maximum_new_predicted_collisions"],
        deadline_ms=float(runtime["deadline_ms"]),
        warmups=runtime["warmups"],
        repetitions=runtime["repetitions"],
        torch_threads=runtime["torch_threads"],
        selection_rule=str(raw["selection_rule"]),
    )


def select_compressed_model(records: list[dict[str, Any]]) -> str | None:
    """Apply the frozen lexicographic rule without changing thresholds post-result."""

    eligible = [record for record in records if record["eligible"]]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda record: (record["runtime_p95_ms"], record["parameter_count"], record["name"]),
    )["name"]
