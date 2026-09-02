from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
import yaml

import motionworld.data.residual_manifest as manifest_module
from motionworld.data.episode import ValidatedEpisode
from motionworld.data.residual_manifest import audit_residual_dataset


def _configuration() -> dict[str, float]:
    return {
        "motion_phase_duration_s": 0.5,
        "intermediate_stop_duration_s": 0.2,
        "final_stop_duration_s": 0.3,
        "forward_speed_cm_s": 120.0,
        "reverse_speed_cm_s": 90.0,
        "lateral_speed_cm_s": 110.0,
        "diagonal_component_speed_cm_s": 75.0,
    }


def _actions(configuration: dict[str, float]) -> list[list[float]]:
    return [
        [configuration["forward_speed_cm_s"], 0.0, 0.0],
        [0.0, 0.0, 0.0],
        [-configuration["reverse_speed_cm_s"], 0.0, 0.0],
        [0.0, configuration["lateral_speed_cm_s"], 0.0],
        [0.0, -configuration["lateral_speed_cm_s"], 0.0],
        [
            configuration["diagonal_component_speed_cm_s"],
            configuration["diagonal_component_speed_cm_s"],
            0.0,
        ],
    ]


def _episode(episode_id: int, configuration: dict[str, float]) -> ValidatedEpisode:
    transitions = tuple(
        {
            "episode_id": episode_id,
            "transition_sequence": index,
            "applied_action": {"velocity_world_cm_per_s": action},
        }
        for index, action in enumerate(_actions(configuration))
    )
    return ValidatedEpisode(
        path=Path(f"episode_{episode_id}.jsonl"),
        header={"episode_id": episode_id, "schema_version": 5},
        transitions=transitions,
        footer={"complete": True},
    )


def _write_plan(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    train_bytes = b"accepted train\n"
    validation_bytes = b"accepted validation\n"
    (raw_root / "train.jsonl").write_bytes(train_bytes)
    (raw_root / "validation.jsonl").write_bytes(validation_bytes)
    configuration = _configuration()
    plan: dict[str, object] = {
        "schema_name": "motionworld_residual_collection_plan",
        "schema_version": 1,
        "frozen_before_training": True,
        "common": {"timed_gate": False, "external_perturbation": False},
        "rejected_attempts": [
            {
                "raw_file": "rejected.jsonl",
                "raw_sha256": "f" * 64,
            }
        ],
        "episodes": [
            {
                "episode_id": 11,
                "split": "train",
                "status": "accepted",
                **configuration,
                "raw_file": "train.jsonl",
                "raw_sha256": hashlib.sha256(train_bytes).hexdigest(),
            },
            {
                "episode_id": 21,
                "split": "validation",
                "status": "accepted",
                **configuration,
                "raw_file": "validation.jsonl",
                "raw_sha256": hashlib.sha256(validation_bytes).hexdigest(),
            },
            {
                "episode_id": 31,
                "split": "test",
                "status": "pending",
                **configuration,
            },
        ],
    }
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")
    return plan_path, raw_root, plan


@pytest.fixture(autouse=True)
def _stub_example_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        manifest_module,
        "build_residual_examples",
        lambda episode, *, history_length: tuple(
            range(len(episode.transitions) - history_length + 1)
        ),
    )


def test_audit_opens_only_accepted_files_and_freezes_split_totals(tmp_path: Path) -> None:
    plan_path, raw_root, _ = _write_plan(tmp_path)
    opened: list[str] = []

    def loader(path: Path) -> ValidatedEpisode:
        opened.append(path.name)
        episode_id = 11 if path.name == "train.jsonl" else 21
        return _episode(episode_id, _configuration())

    dataset = audit_residual_dataset(plan_path, raw_root, episode_loader=loader)
    result = dataset.manifest_dict()

    assert opened == ["train.jsonl", "validation.jsonl"]
    assert result["test_data_policy"] == "pending_test_entries_are_not_opened_by_this_audit"
    assert result["split_totals"] == {
        "train": {
            "episode_count": 1,
            "transition_count": 6,
            "no_history_example_count": 6,
            "four_history_example_count": 3,
        },
        "validation": {
            "episode_count": 1,
            "transition_count": 6,
            "no_history_example_count": 6,
            "four_history_example_count": 3,
        },
    }


def test_hash_mismatch_fails_before_loading_episode(tmp_path: Path) -> None:
    plan_path, raw_root, plan = _write_plan(tmp_path)
    plan["episodes"][0]["raw_sha256"] = "0" * 64
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")
    opened: list[Path] = []

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit_residual_dataset(
            plan_path,
            raw_root,
            episode_loader=lambda path: opened.append(path),
        )
    assert opened == []


def test_embedded_episode_id_mismatch_is_rejected(tmp_path: Path) -> None:
    plan_path, raw_root, _ = _write_plan(tmp_path)

    with pytest.raises(ValueError, match="does not match embedded ID"):
        audit_residual_dataset(
            plan_path,
            raw_root,
            episode_loader=lambda path: _episode(999, _configuration()),
        )


def test_accepted_hash_cannot_also_be_rejected(tmp_path: Path) -> None:
    plan_path, raw_root, plan = _write_plan(tmp_path)
    plan["rejected_attempts"][0]["raw_sha256"] = plan["episodes"][0]["raw_sha256"]
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="also appears in rejected"):
        audit_residual_dataset(plan_path, raw_root)


def test_pending_test_must_not_contain_observed_file_metadata(tmp_path: Path) -> None:
    plan_path, raw_root, plan = _write_plan(tmp_path)
    plan["episodes"][2]["raw_file"] = "test.jsonl"
    plan_path.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="pending episode"):
        audit_residual_dataset(plan_path, raw_root)


def test_realized_action_set_must_match_frozen_configuration(tmp_path: Path) -> None:
    plan_path, raw_root, _ = _write_plan(tmp_path)
    changed = copy.deepcopy(_configuration())
    changed["forward_speed_cm_s"] = 999.0

    with pytest.raises(ValueError, match="realized actions differ"):
        audit_residual_dataset(
            plan_path,
            raw_root,
            episode_loader=lambda path: _episode(
                11 if path.name == "train.jsonl" else 21,
                changed,
            ),
        )
