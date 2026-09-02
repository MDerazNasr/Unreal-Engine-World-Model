from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

import motionworld.data.residual_coverage as coverage_module
from motionworld.data.episode import ValidatedEpisode
from motionworld.data.residual_coverage import build_residual_coverage_report
from motionworld.data.residual_manifest import AuditedEpisode, AuditedResidualDataset


def _transition(sequence: int, action: list[float], *, parameter_change: bool) -> dict[str, object]:
    previous_parameters = {"acceleration": 500.0}
    completed_parameters = {"acceleration": 300.0 if parameter_change else 500.0}
    return {
        "transition_sequence": sequence,
        "delta_time_s": 0.02 + 0.001 * sequence,
        "applied_action": {"velocity_world_cm_per_s": action},
        "previous_state": {"facing_yaw_deg": float(sequence)},
        "next_state": {
            "facing_yaw_deg": float(sequence + 1),
            "velocity_world_cm_per_s": [50.0, 0.0, 0.0],
            "movement_mode": "Walking",
        },
        "nominal_context": {
            "previous": {
                "parameters": previous_parameters,
                "input_preparation": {"max_speed": 165.0},
            },
            "parameters_observed_for_completed_step": completed_parameters,
            "input_preparation_observed_for_completed_step": {"max_speed": 165.0},
        },
        "scenario": None,
        "external_perturbation": {"type": "none"},
    }


def _audited_episode(episode_id: int, split: str, speed: float) -> AuditedEpisode:
    transitions = (
        _transition(0, [speed, 0.0, 0.0], parameter_change=False),
        _transition(1, [0.0, 0.0, 0.0], parameter_change=True),
    )
    episode = ValidatedEpisode(
        path=Path(f"episode_{episode_id}.jsonl"),
        header={"episode_id": episode_id, "schema_version": 5},
        transitions=transitions,
        footer={"complete": True},
    )
    return AuditedEpisode(
        episode_id=episode_id,
        split=split,
        raw_file=episode.path.name,
        raw_sha256=("a" if split == "train" else "b") * 64,
        schema_version=5,
        transition_count=2,
        no_history_example_count=2,
        four_history_example_count=0,
        configuration={
            "motion_phase_duration_s": 0.5 if split == "train" else 0.6,
            "intermediate_stop_duration_s": 0.2,
            "final_stop_duration_s": 0.3,
            "forward_speed_cm_s": speed,
            "reverse_speed_cm_s": 90.0,
            "lateral_speed_cm_s": 110.0,
            "diagonal_component_speed_cm_s": 75.0,
        },
        episode=episode,
    )


def test_coverage_reports_splits_novelty_and_known_zero_counts(monkeypatch) -> None:
    dataset = AuditedResidualDataset(
        plan_sha256="c" * 64,
        episodes=(
            _audited_episode(11, "train", 120.0),
            _audited_episode(21, "validation", 130.0),
        ),
        rejected_files=(),
        rejected_sha256=(),
    )

    def examples(episode, *, history_length):
        assert history_length == 1
        return (
            SimpleNamespace(transition_sequence=0, target=np.zeros(6)),
            SimpleNamespace(
                transition_sequence=1,
                target=np.asarray([2.0, 0.0, 3.0, 0.0, 0.2, 0.4]),
            ),
        )

    monkeypatch.setattr(coverage_module, "build_residual_examples", examples)
    report = build_residual_coverage_report(dataset)

    assert report["validation_configuration_is_not_exact_train_duplicate"] == {"21": True}
    assert report["splits"]["train"]["action_direction_counts"]["forward"] == 1
    assert report["splits"]["train"]["action_direction_counts"]["stop"] == 1
    assert report["splits"]["train"]["parameter_change_transition_count"] == 1
    assert report["splits"]["train"]["collision_transition_count"] == 0
    assert report["splits"]["validation"]["external_perturbation_transition_count"] == 0
    assert report["splits"]["train"]["residual_targets"]["parameter_change"][
        "material_count"
    ]["planar_position_gt_0_001_cm"] == 1
