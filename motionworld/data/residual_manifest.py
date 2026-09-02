"""Failure-closed manifest audit for accepted residual-learning episodes."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from motionworld.data.episode import ValidatedEpisode, load_episode
from motionworld.models.residual_dataset import build_residual_examples

RESIDUAL_MANIFEST_SCHEMA_VERSION = 1
_ACCEPTED_SPLITS = frozenset({"train", "validation"})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_ACTION_TOLERANCE_CM_S = 1.0e-6


@dataclass(frozen=True, slots=True)
class AuditedEpisode:
    """One accepted raw file plus its independently validated metadata."""

    episode_id: int
    split: str
    raw_file: str
    raw_sha256: str
    schema_version: int
    transition_count: int
    no_history_example_count: int
    four_history_example_count: int
    configuration: dict[str, float]
    episode: ValidatedEpisode

    def manifest_record(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "split": self.split,
            "raw_file": self.raw_file,
            "raw_sha256": self.raw_sha256,
            "schema_version": self.schema_version,
            "transition_count": self.transition_count,
            "no_history_example_count": self.no_history_example_count,
            "four_history_example_count": self.four_history_example_count,
            "configuration": self.configuration,
        }


@dataclass(frozen=True, slots=True)
class AuditedResidualDataset:
    """Accepted episodes after file, schema, identity, split, and leakage checks."""

    plan_sha256: str
    episodes: tuple[AuditedEpisode, ...]
    rejected_files: tuple[str, ...]
    rejected_sha256: tuple[str, ...]

    def episodes_for_split(self, split: str) -> tuple[AuditedEpisode, ...]:
        if split not in _ACCEPTED_SPLITS:
            raise ValueError(f"unknown accepted split: {split}")
        return tuple(episode for episode in self.episodes if episode.split == split)

    def manifest_dict(self) -> dict[str, object]:
        split_totals: dict[str, dict[str, int]] = {}
        for split in sorted(_ACCEPTED_SPLITS):
            episodes = self.episodes_for_split(split)
            split_totals[split] = {
                "episode_count": len(episodes),
                "transition_count": sum(item.transition_count for item in episodes),
                "no_history_example_count": sum(
                    item.no_history_example_count for item in episodes
                ),
                "four_history_example_count": sum(
                    item.four_history_example_count for item in episodes
                ),
            }
        return {
            "schema_name": "motionworld_residual_dataset_manifest",
            "schema_version": RESIDUAL_MANIFEST_SCHEMA_VERSION,
            "source_plan_sha256": self.plan_sha256,
            "raw_data_policy": "external_untracked_files_verified_by_sha256",
            "test_data_policy": "pending_test_entries_are_not_opened_by_this_audit",
            "checks": {
                "accepted_filenames_unique": True,
                "accepted_hashes_unique": True,
                "accepted_episode_ids_unique": True,
                "episode_splits_disjoint": True,
                "transition_identities_unique": True,
                "accepted_files_disjoint_from_rejected_attempts": True,
                "realized_actions_match_frozen_configuration": True,
                "strict_episode_loader_passed": True,
            },
            "split_totals": split_totals,
            "episodes": [episode.manifest_record() for episode in self.episodes],
            "rejected_attempts": {
                "count": len(self.rejected_files),
                "raw_files": list(self.rejected_files),
                "raw_sha256": list(self.rejected_sha256),
                "policy": "quarantined_and_not_opened",
            },
        }


def _require_mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _require_sha256(value: object, *, context: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return value


def _safe_basename(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be a non-empty filename")
    if Path(value).name != value:
        raise ValueError(f"{context} must not contain a path")
    return value


def _configuration(row: dict[str, Any]) -> dict[str, float]:
    names = (
        "motion_phase_duration_s",
        "intermediate_stop_duration_s",
        "final_stop_duration_s",
        "forward_speed_cm_s",
        "reverse_speed_cm_s",
        "lateral_speed_cm_s",
        "diagonal_component_speed_cm_s",
    )
    result: dict[str, float] = {}
    for name in names:
        value = row.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"accepted episode {name} must be numeric")
        numeric = float(value)
        if numeric <= 0.0:
            raise ValueError(f"accepted episode {name} must be positive")
        result[name] = numeric
    return result


def _expected_actions(configuration: dict[str, float]) -> set[tuple[float, float]]:
    return {
        (configuration["forward_speed_cm_s"], 0.0),
        (-configuration["reverse_speed_cm_s"], 0.0),
        (0.0, configuration["lateral_speed_cm_s"]),
        (0.0, -configuration["lateral_speed_cm_s"]),
        (
            configuration["diagonal_component_speed_cm_s"],
            configuration["diagonal_component_speed_cm_s"],
        ),
        (0.0, 0.0),
    }


def _canonical_action(value: object) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("accepted transition action must be a three-component list")
    x, y, z = (float(component) for component in value)
    if abs(z) > _ACTION_TOLERANCE_CM_S:
        raise ValueError("accepted transition action must be planar")
    return (round(x, 6), round(y, 6))


def _validate_realized_actions(
    episode: ValidatedEpisode,
    configuration: dict[str, float],
) -> None:
    actual = {
        _canonical_action(transition["applied_action"]["velocity_world_cm_per_s"])
        for transition in episode.transitions
    }
    expected = {
        (round(x, 6), round(y, 6)) for x, y in _expected_actions(configuration)
    }
    if actual != expected:
        raise ValueError(
            f"episode {episode.episode_id} realized actions differ from frozen configuration; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def audit_residual_dataset(
    plan_path: Path,
    raw_data_root: Path,
    *,
    episode_loader: Callable[[Path], ValidatedEpisode] = load_episode,
) -> AuditedResidualDataset:
    """Audit only explicitly accepted files; pending test and rejected files remain unopened."""

    plan_bytes = plan_path.read_bytes()
    plan = _require_mapping(yaml.safe_load(plan_bytes), context="collection plan")
    if plan.get("schema_name") != "motionworld_residual_collection_plan":
        raise ValueError("unexpected residual collection plan schema")
    if plan.get("schema_version") != 1 or plan.get("frozen_before_training") is not True:
        raise ValueError("collection plan must be version 1 and frozen before training")
    common = _require_mapping(plan.get("common"), context="collection plan common")
    if common.get("timed_gate") is not False or common.get("external_perturbation") is not False:
        raise ValueError("residual collection must exclude gates and external perturbations")

    rejected_rows = plan.get("rejected_attempts")
    if not isinstance(rejected_rows, list):
        raise ValueError("rejected_attempts must be a list")
    rejected_files: list[str] = []
    rejected_hashes: list[str] = []
    for index, raw_row in enumerate(rejected_rows):
        row = _require_mapping(raw_row, context=f"rejected_attempts[{index}]")
        rejected_files.append(
            _safe_basename(row.get("raw_file"), context=f"rejected_attempts[{index}].raw_file")
        )
        rejected_hashes.append(
            _require_sha256(
                row.get("raw_sha256"),
                context=f"rejected_attempts[{index}].raw_sha256",
            )
        )

    episode_rows = plan.get("episodes")
    if not isinstance(episode_rows, list) or not episode_rows:
        raise ValueError("collection plan episodes must be a non-empty list")
    accepted_rows: list[dict[str, Any]] = []
    pending_ids: set[int] = set()
    for index, raw_row in enumerate(episode_rows):
        row = _require_mapping(raw_row, context=f"episodes[{index}]")
        episode_id = row.get("episode_id")
        if isinstance(episode_id, bool) or not isinstance(episode_id, int):
            raise ValueError(f"episodes[{index}].episode_id must be an integer")
        status = row.get("status")
        if status == "accepted":
            if row.get("split") not in _ACCEPTED_SPLITS:
                raise ValueError("only train or validation episodes may be accepted before test")
            accepted_rows.append(row)
        elif status == "pending":
            if "raw_file" in row or "raw_sha256" in row:
                raise ValueError("pending episode must not contain observed raw-file metadata")
            pending_ids.add(episode_id)
        else:
            raise ValueError(f"unknown collection status for episode {episode_id}: {status}")

    accepted_ids = [int(row["episode_id"]) for row in accepted_rows]
    if len(accepted_ids) != len(set(accepted_ids)):
        raise ValueError("accepted episode IDs must be globally unique")
    if set(accepted_ids) & pending_ids:
        raise ValueError("episode ID appears in both accepted and pending sets")

    filenames = [
        _safe_basename(row.get("raw_file"), context=f"episode {row['episode_id']} raw_file")
        for row in accepted_rows
    ]
    hashes = [
        _require_sha256(row.get("raw_sha256"), context=f"episode {row['episode_id']} raw_sha256")
        for row in accepted_rows
    ]
    if len(filenames) != len(set(filenames)):
        raise ValueError("accepted raw filenames must be unique")
    if len(hashes) != len(set(hashes)):
        raise ValueError("accepted raw hashes must be unique")
    if set(filenames) & set(rejected_files) or set(hashes) & set(rejected_hashes):
        raise ValueError("an accepted artifact also appears in rejected_attempts")

    audited: list[AuditedEpisode] = []
    transition_identities: set[tuple[int, int]] = set()
    for row, raw_file, expected_hash in zip(accepted_rows, filenames, hashes, strict=True):
        path = raw_data_root / raw_file
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"SHA-256 mismatch for accepted episode file {raw_file}")
        episode = episode_loader(path)
        episode_id = int(row["episode_id"])
        if episode.episode_id != episode_id:
            raise ValueError(
                f"accepted episode ID {episode_id} does not match embedded ID {episode.episode_id}"
            )
        configuration = _configuration(row)
        _validate_realized_actions(episode, configuration)
        for transition in episode.transitions:
            identity = (episode_id, int(transition["transition_sequence"]))
            if identity in transition_identities:
                raise ValueError(f"duplicate transition identity: {identity}")
            transition_identities.add(identity)
        no_history = build_residual_examples(episode, history_length=1)
        four_history = build_residual_examples(episode, history_length=4)
        audited.append(
            AuditedEpisode(
                episode_id=episode_id,
                split=str(row["split"]),
                raw_file=raw_file,
                raw_sha256=expected_hash,
                schema_version=int(episode.header["schema_version"]),
                transition_count=len(episode.transitions),
                no_history_example_count=len(no_history),
                four_history_example_count=len(four_history),
                configuration=configuration,
                episode=episode,
            )
        )

    return AuditedResidualDataset(
        plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
        episodes=tuple(audited),
        rejected_files=tuple(rejected_files),
        rejected_sha256=tuple(rejected_hashes),
    )
