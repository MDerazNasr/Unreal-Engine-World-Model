from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from motionworld.evaluation import (
    load_final_control_manifest,
    load_final_prediction_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
PREDICTION_PATH = ROOT / "configs" / "final_prediction_manifest.yaml"
CONTROL_PATH = ROOT / "configs" / "final_control_manifest.yaml"
COLLECTION_PATH = ROOT / "configs" / "residual_collection_plan.yaml"


def _mutate(tmp_path: Path, source: Path, mutation) -> Path:
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    mutation(raw)
    result = tmp_path / source.name
    result.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return result


def test_prediction_manifest_keeps_5301_and_5302_sealed_and_separate() -> None:
    prediction = load_final_prediction_manifest(PREDICTION_PATH)
    control = load_final_control_manifest(CONTROL_PATH)
    assert prediction.episode_ids == (5301, 5302)
    assert prediction.horizons_s == (0.5, 1.0, 1.5)
    assert not set(prediction.episode_ids).intersection(control.paired_seeds)


def test_prediction_manifest_contains_no_raw_test_identity() -> None:
    text = PREDICTION_PATH.read_text(encoding="utf-8")
    assert "raw_file:" not in text
    assert "raw_sha256:" not in text


def test_prediction_manifest_declares_unavailable_strata_instead_of_inventing_them() -> None:
    raw = yaml.safe_load(PREDICTION_PATH.read_text(encoding="utf-8"))
    strata = {entry["name"]: entry["status"] for entry in raw["strata"]}
    assert strata == {
        "free_space": "predeclared_present",
        "near_contact": "predeclared_absent",
        "post_push": "predeclared_absent",
        "held_out_movement_setting": "predeclared_absent",
    }


def test_prediction_schedules_match_the_original_pretraining_collection_freeze() -> None:
    prediction = yaml.safe_load(PREDICTION_PATH.read_text(encoding="utf-8"))
    collection = yaml.safe_load(COLLECTION_PATH.read_text(encoding="utf-8"))
    prediction_by_id = {episode["episode_id"]: episode for episode in prediction["episodes"]}
    collection_by_id = {episode["episode_id"]: episode for episode in collection["episodes"]}
    for episode_id in (5301, 5302):
        expected = dict(collection_by_id[episode_id])
        expected["status"] = "pending_uncollected"
        assert prediction_by_id[episode_id] == expected


def test_prediction_manifest_rejects_raw_test_metadata(tmp_path: Path) -> None:
    def mutation(raw: dict[str, object]) -> None:
        raw["episodes"][0]["raw_file"] = "forbidden.jsonl"

    with pytest.raises(ValueError, match="forbidden metadata|keys must be exactly"):
        load_final_prediction_manifest(_mutate(tmp_path, PREDICTION_PATH, mutation))


def test_prediction_manifest_rejects_teacher_forcing(tmp_path: Path) -> None:
    def mutation(raw: dict[str, object]) -> None:
        raw["rollout"]["mode"] = "teacher_forced"

    with pytest.raises(ValueError, match="rollout mode"):
        load_final_prediction_manifest(_mutate(tmp_path, PREDICTION_PATH, mutation))


def test_control_manifest_freezes_pairing_geometry_and_primary_estimand() -> None:
    control = load_final_control_manifest(CONTROL_PATH)
    assert len(control.paired_seeds) == 12
    assert control.minimum_valid_pairs == 10
    assert control.scenario_names == (
        "timed_gate",
        "push_recovery",
        "held_out_setting",
        "ood_setting",
    )
    assert control.status == "frozen_draft_geometry_verified_headless"
    assert control.agent_radius_cm == 30.0
    assert control.agent_half_height_cm == 86.0
    assert control.primary_estimand.endswith("residual_minus_nominal")


def test_push_scenario_is_reachable_and_frame_explicit() -> None:
    raw = yaml.safe_load(CONTROL_PATH.read_text(encoding="utf-8"))
    push = raw["scenarios"]["push_recovery"]
    maximum_kinematic_distance_cm = 165.0 * push["timeout_s"]
    assert push["target_position_reset_local_cm"][0] < maximum_kinematic_distance_cm
    assert push["perturbation"]["declared_frame"] == "reset_anchor_character_local"
    assert "delta_world_cm_per_s" not in push["perturbation"]
    assert push["perturbation"]["post_perturbation_observation_s"] == pytest.approx(
        push["timeout_s"] - push["perturbation"]["trigger_time_s"]
    )


def test_control_manifest_rejects_prediction_episode_as_control_seed(tmp_path: Path) -> None:
    def mutation(raw: dict[str, object]) -> None:
        raw["identity"]["paired_scenario_seeds"][0] = 5301
        for scenario in raw["scenarios"].values():
            scenario["paired_seeds"][0] = 5301

    with pytest.raises(ValueError, match="separate from prediction"):
        load_final_control_manifest(_mutate(tmp_path, CONTROL_PATH, mutation))


def test_control_manifest_rejects_seed_mismatch_between_scenarios(tmp_path: Path) -> None:
    def mutation(raw: dict[str, object]) -> None:
        raw["scenarios"]["push_recovery"]["paired_seeds"][0] = 9999

    with pytest.raises(ValueError, match="frozen paired seeds"):
        load_final_control_manifest(_mutate(tmp_path, CONTROL_PATH, mutation))


def test_control_manifest_counts_timeouts_as_results_not_infrastructure(tmp_path: Path) -> None:
    def mutation(raw: dict[str, object]) -> None:
        raw["validity"]["valid_controller_failures"].remove("timeout")

    with pytest.raises(ValueError, match="must not be excluded"):
        load_final_control_manifest(_mutate(tmp_path, CONTROL_PATH, mutation))


def test_control_manifest_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    path = _mutate(tmp_path, CONTROL_PATH, lambda raw: raw.update(post_hoc_override=True))
    with pytest.raises(ValueError, match="keys must be exactly"):
        load_final_control_manifest(path)


def test_control_manifest_rejects_unverified_geometry_drift(tmp_path: Path) -> None:
    def mutation(raw: dict[str, object]) -> None:
        raw["geometry_and_reset"]["agent_capsule"]["radius_cm"] = 42.0

    with pytest.raises(ValueError, match="verified capsule radius"):
        load_final_control_manifest(_mutate(tmp_path, CONTROL_PATH, mutation))


def test_control_manifest_rejects_nested_scenario_schema_drift(tmp_path: Path) -> None:
    def mutation(raw: dict[str, object]) -> None:
        raw["scenarios"]["push_recovery"]["perturbation"]["future_push_known"] = True

    with pytest.raises(ValueError, match="perturbation keys must be exactly"):
        load_final_control_manifest(_mutate(tmp_path, CONTROL_PATH, mutation))
