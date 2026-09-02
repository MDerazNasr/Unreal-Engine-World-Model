"""Failure-closed tests for the Unreal-to-Python episode boundary."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from motionworld.data import EpisodeValidationError, load_episode


def _state(sequence: int, frame: int, time_s: float, position_x: float) -> dict[str, object]:
    return {
        "protocol_version": 1,
        "sample_sequence": sequence,
        "mover_step_server_frame": frame,
        "simulation_time_s": time_s,
        "step_s": 0.05,
        "is_resimulation": False,
        "is_valid": True,
        "movement_mode": "Walking",
        "position_world_cm": [position_x, 0.0, 88.0],
        "velocity_world_cm_per_s": [100.0, 0.0, 0.0],
        "velocity_local_planar_cm_per_s": [100.0, 0.0, 0.0],
        "facing_yaw_deg": 0.0,
        "facing_unit_world": [1.0, 0.0],
        "angular_velocity_world_deg_per_s": [0.0, 0.0, 0.0],
    }


def _transition(
    transition_sequence: int,
    previous: dict[str, object],
    next_state: dict[str, object],
) -> dict[str, object]:
    return {
        "record_type": "transition",
        "schema_version": 1,
        "transition_protocol_version": 1,
        "episode_id": 42,
        "transition_sequence": transition_sequence,
        "start_simulation_time_s": previous["simulation_time_s"],
        "end_simulation_time_s": next_state["simulation_time_s"],
        "delta_time_s": 0.05,
        "previous_state": previous,
        "applied_action": {
            "type": "desired_velocity",
            "is_valid": True,
            "was_motionworld_automated": True,
            "velocity_world_cm_per_s": [100.0, 0.0, 0.0],
            "velocity_local_planar_cm_per_s": [100.0, 0.0, 0.0],
        },
        "next_state": next_state,
    }


def _records() -> list[dict[str, object]]:
    state_10 = _state(10, 20, 1.0, 0.0)
    state_11 = _state(11, 21, 1.05, 5.0)
    state_12 = _state(12, 22, 1.1, 10.0)
    return [
        {
            "record_type": "episode_header",
            "schema_name": "motionworld_episode",
            "schema_version": 1,
            "created_utc": "2026-08-31T12:00:00.000Z",
            "engine_version": "5.8.2-test",
            "project_name": "MotionWorldTest",
            "episode_id": 42,
            "state_source": "mover_finalized_sync_state",
            "conventions": {
                "world_frame": "unreal_world_x_forward_y_right_z_up",
                "local_action_frame": "previous_state_character_x_forward_y_right",
                "position_unit": "centimetres",
                "linear_velocity_unit": "centimetres_per_second",
                "angle_unit": "degrees",
                "angular_velocity_unit": "degrees_per_second",
                "time_unit": "seconds",
            },
            "recorder_stats": {
                "observed_state_count": 3,
                "attempted_transition_count": 2,
                "recorded_transition_count": 2,
                "rejected_transition_count": 0,
                "rejected_seed_state_count": 0,
                "capacity_drop_count": 0,
            },
        },
        _transition(0, state_10, state_11),
        _transition(1, copy.deepcopy(state_11), state_12),
        {
            "record_type": "episode_footer",
            "schema_version": 1,
            "episode_id": 42,
            "transition_count": 2,
            "first_transition_sequence": 0,
            "last_transition_sequence": 1,
            "complete": True,
        },
    ]


def _gate_state(time_s: float) -> dict[str, object]:
    phase = 2.0 * math.pi * time_s / 4.0
    return {
        "scenario_time_s": time_s,
        "phase_rad": phase % (2.0 * math.pi),
        "center_world_cm": [5.0, 100.0 * math.sin(phase), 88.0],
        "velocity_world_cm_per_s": [0.0, 50.0 * math.pi * math.cos(phase), 0.0],
    }


def _scenario_records() -> list[dict[str, object]]:
    records = _records()
    records[0]["schema_version"] = 2
    records[0]["scenario"] = {
        "type": "timed_gate",
        "scenario_seed": 1901,
        "motion_type": "sinusoidal_translation",
        "origin_world_cm": [5.0, 0.0, 88.0],
        "motion_axis_world": [0.0, 1.0, 0.0],
        "amplitude_cm": 100.0,
        "period_s": 4.0,
        "phase_offset_rad": 0.0,
        "half_extents_cm": [20.0, 40.0, 90.0],
        "crossing_plane_normal_world": [1.0, 0.0, 0.0],
        "timeout_s": 8.0,
        "scenario_start_simulation_time_s": 1.0,
        "obstacle_state_source": "analytic_absolute_time_schedule",
    }
    for index, row in enumerate(records[1:-1]):
        row["schema_version"] = 2
        previous_time = float(row["previous_state"]["simulation_time_s"]) - 1.0
        next_time = float(row["next_state"]["simulation_time_s"]) - 1.0
        is_last = index == len(records[1:-1]) - 1
        row["scenario"] = {
            "previous_gate_state": _gate_state(previous_time),
            "next_gate_state": _gate_state(next_time),
            "collision_this_step": False,
            "crossed_success_plane_this_step": is_last,
            "termination_reason": "success" if is_last else "none",
        }
    records[-1]["schema_version"] = 2
    records[-1]["scenario_summary"] = {
        "termination_reason": "success",
        "termination_scenario_time_s": 0.1,
        "collision_count": 0,
    }
    return records


def _smooth_walking_parameters() -> dict[str, object]:
    return {
        "acceleration_cm_per_s2": 500.0,
        "deceleration_cm_per_s2": 300.0,
        "directional_acceleration_factor": 1.0,
        "turning_strength": 8.0,
        "acceleration_smoothing_time_s": 0.1,
        "deceleration_smoothing_time_s": 0.1,
        "acceleration_smoothing_compensation": 0.0,
        "deceleration_smoothing_compensation": 0.0,
        "velocity_deadzone_cm_per_s": 0.01,
        "acceleration_deadzone_cm_per_s2": 0.001,
        "outside_influence_smoothing_time_s": 0.05,
        "facing_smoothing_time_s": 0.2,
        "smooth_facing_with_double_spring": False,
        "facing_deadzone_deg": 0.1,
        "angular_velocity_deadzone_deg_per_s": 0.01,
    }


def _nominal_context(state: dict[str, object]) -> dict[str, object]:
    sequence = int(state["sample_sequence"])
    return {
        "protocol_version": 1,
        "is_valid": True,
        "authoritative_state_sample_sequence": sequence,
        "movement_mode_name": state["movement_mode"],
        "movement_mode_class": "BP_MovementMode_Walking_C",
        "parameters": _smooth_walking_parameters(),
        "internal_state": {
            "spring_velocity_world_cm_per_s": [float(sequence), 2.0, 0.0],
            "spring_acceleration_world_cm_per_s2": [3.0, 4.0, 0.0],
            "intermediate_velocity_world_cm_per_s": [5.0, 6.0, 0.0],
            "intermediate_facing_world_xyzw": [0.0, 0.0, 0.0, 1.0],
            "intermediate_angular_velocity_world_rad_per_s": [0.0, 0.0, 0.25],
        },
    }


def _v3_records() -> list[dict[str, object]]:
    records = _scenario_records()
    records[0]["schema_version"] = 3
    records[0]["nominal_context_contract"] = {
        "protocol_version": 1,
        "source": "ue58_smooth_walking_public_reflection",
        "capture_phase": "mover_on_post_finalize",
        "step_parameter_semantics": ("next_finalized_snapshot_assumed_used_during_completed_step"),
        "missing_policy": "reject_transition",
        "future_planner_availability": "not_guaranteed_requires_causal_selector",
    }
    previous_next_context: dict[str, object] | None = None
    for row in records[1:-1]:
        row["schema_version"] = 3
        row["transition_protocol_version"] = 2
        previous_context = (
            copy.deepcopy(previous_next_context)
            if previous_next_context is not None
            else _nominal_context(row["previous_state"])
        )
        next_context = _nominal_context(row["next_state"])
        row["nominal_context"] = {
            "previous": previous_context,
            "parameters_observed_for_completed_step": copy.deepcopy(next_context["parameters"]),
            "next": next_context,
        }
        previous_next_context = next_context
    records[-1]["schema_version"] = 3
    return records


def _input_preparation() -> dict[str, object]:
    return {
        "has_max_move_speed": True,
        "effective_max_speed_cm_per_s": 165.0,
        "max_speed_source": "common_legacy_settings",
    }


def _v4_records() -> list[dict[str, object]]:
    records = _v3_records()
    records[0]["schema_version"] = 4
    contract = records[0]["nominal_context_contract"]
    contract["protocol_version"] = 2
    contract["input_preparation_source"] = "simple_walking_mode_and_shared_settings"
    contract["orientation_intent_semantics"] = (
        "echoed_world_space_input_with_simple_walking_planar_fallback"
    )
    for row in records[1:-1]:
        row["schema_version"] = 4
        row["transition_protocol_version"] = 3
        row["applied_action"]["orientation_intent_world"] = [1.0, 0.0, 0.0]
        row["applied_action"]["desired_facing_yaw_deg"] = 0.0
        row["applied_action"]["used_previous_facing_for_zero_orientation_intent"] = False
        nominal = row["nominal_context"]
        for endpoint in ("previous", "next"):
            nominal[endpoint]["protocol_version"] = 2
            nominal[endpoint]["input_preparation"] = _input_preparation()
        nominal["input_preparation_observed_for_completed_step"] = copy.deepcopy(
            nominal["next"]["input_preparation"]
        )
    records[-1]["schema_version"] = 4
    return records


def _empty_external_perturbation() -> dict[str, object]:
    return {
        "protocol_version": 1,
        "is_valid": True,
        "type": "none",
        "was_motionworld_scheduled": False,
        "requested_velocity_delta_world_cm_per_s": [0.0, 0.0, 0.0],
        "queued_after_state_sample_sequence": -1,
        "queued_after_mover_step_server_frame": -1,
    }


def _v5_records(*, with_perturbation: bool = False) -> list[dict[str, object]]:
    records = _v4_records()
    records[0]["schema_version"] = 5
    records[0]["external_perturbation_contract"] = {
        "protocol_version": 1,
        "semantics": "evaluation_only_event_label_not_model_input",
        "application": "mover_one_tick_additive_velocity",
        "alignment": "queued_after_previous_finalized_state_before_next_state",
        "unit": "centimetres_per_second",
    }
    records[0]["external_perturbation_schedule"] = None
    for row in records[1:-1]:
        row["schema_version"] = 5
        row["transition_protocol_version"] = 4
        row["external_perturbation"] = _empty_external_perturbation()
    records[-1]["schema_version"] = 5
    if with_perturbation:
        records[0]["scenario"] = None
        for row in records[1:-1]:
            row["scenario"] = None
        records[-1]["scenario_summary"] = None
        records[0]["external_perturbation_schedule"] = {
            "warmup_duration_s": 0.05,
            "post_perturbation_duration_s": 0.05,
            "additive_velocity_world_cm_per_s": [0.0, 250.0, 0.0],
            "schedule_start_simulation_time_s": 1.0,
        }
        records[2]["external_perturbation"] = {
            "protocol_version": 1,
            "is_valid": True,
            "type": "additive_velocity",
            "was_motionworld_scheduled": True,
            "requested_velocity_delta_world_cm_per_s": [0.0, 250.0, 0.0],
            "queued_after_state_sample_sequence": 11,
            "queued_after_mover_step_server_frame": 21,
        }
    return records


def _write(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_text("".join(f"{json.dumps(record)}\n" for record in records), encoding="utf-8")
    return path


def test_valid_complete_episode_loads(tmp_path: Path) -> None:
    episode = load_episode(_write(tmp_path / "episode.jsonl", _records()))

    assert episode.episode_id == 42
    assert len(episode.transitions) == 2
    assert episode.transitions[0]["previous_state"]["sample_sequence"] == 10
    assert episode.transitions[-1]["next_state"]["sample_sequence"] == 12


def test_valid_v2_timed_gate_episode_recomputes_every_obstacle_state(tmp_path: Path) -> None:
    episode = load_episode(_write(tmp_path / "scenario.jsonl", _scenario_records()))

    assert episode.header["schema_version"] == 2
    assert episode.header["scenario"]["scenario_seed"] == 1901
    assert episode.transitions[-1]["scenario"]["termination_reason"] == "success"


def test_valid_v3_episode_loads_aligned_nominal_context(tmp_path: Path) -> None:
    episode = load_episode(_write(tmp_path / "nominal_context.jsonl", _v3_records()))

    assert episode.header["schema_version"] == 3
    assert episode.transitions[0]["transition_protocol_version"] == 2
    assert (
        episode.transitions[0]["nominal_context"]["previous"]["authoritative_state_sample_sequence"]
        == 10
    )


def test_valid_v4_episode_loads_complete_causal_contract(tmp_path: Path) -> None:
    episode = load_episode(_write(tmp_path / "complete_contract.jsonl", _v4_records()))

    first = episode.transitions[0]
    assert episode.header["schema_version"] == 4
    assert first["transition_protocol_version"] == 3
    assert first["applied_action"]["desired_facing_yaw_deg"] == 0.0
    assert (
        first["nominal_context"]["input_preparation_observed_for_completed_step"][
            "effective_max_speed_cm_per_s"
        ]
        == 165.0
    )


def test_valid_v5_character_episode_has_explicit_empty_event_labels(tmp_path: Path) -> None:
    episode = load_episode(_write(tmp_path / "v5_character.jsonl", _v5_records()))

    assert episode.header["schema_version"] == 5
    assert episode.header["external_perturbation_schedule"] is None
    assert episode.transitions[0]["transition_protocol_version"] == 4
    assert episode.transitions[0]["external_perturbation"]["type"] == "none"


def test_valid_v5_controlled_perturbation_is_source_aligned(tmp_path: Path) -> None:
    episode = load_episode(
        _write(tmp_path / "v5_perturbed.jsonl", _v5_records(with_perturbation=True))
    )

    event = episode.transitions[1]["external_perturbation"]
    assert event["type"] == "additive_velocity"
    assert event["queued_after_state_sample_sequence"] == 11


def test_v5_perturbation_rejects_wrong_source_state(tmp_path: Path) -> None:
    records = _v5_records(with_perturbation=True)
    records[2]["external_perturbation"]["queued_after_state_sample_sequence"] = 10

    with pytest.raises(EpisodeValidationError, match="wrong state sequence"):
        load_episode(_write(tmp_path / "wrong_event_state.jsonl", records))


def test_v5_schedule_requires_exactly_one_event(tmp_path: Path) -> None:
    records = _v5_records(with_perturbation=True)
    records[2]["external_perturbation"] = _empty_external_perturbation()

    with pytest.raises(EpisodeValidationError, match="exactly one event row"):
        load_episode(_write(tmp_path / "missing_event.jsonl", records))


def test_v5_event_velocity_must_match_schedule(tmp_path: Path) -> None:
    records = _v5_records(with_perturbation=True)
    records[2]["external_perturbation"]["requested_velocity_delta_world_cm_per_s"] = [
        0.0,
        200.0,
        0.0,
    ]

    with pytest.raises(EpisodeValidationError, match="does not match its schedule"):
        load_episode(_write(tmp_path / "wrong_event_velocity.jsonl", records))


def test_v5_event_label_is_not_declared_as_model_input(tmp_path: Path) -> None:
    records = _v5_records()
    records[0]["external_perturbation_contract"]["semantics"] = "model_input"

    with pytest.raises(EpisodeValidationError, match="expected"):
        load_episode(_write(tmp_path / "leaked_event_contract.jsonl", records))


def test_v4_effective_speed_must_match_next_snapshot(tmp_path: Path) -> None:
    records = _v4_records()
    records[1]["nominal_context"]["input_preparation_observed_for_completed_step"][
        "effective_max_speed_cm_per_s"
    ] = 200.0

    with pytest.raises(EpisodeValidationError, match="completed-step input preparation"):
        load_episode(_write(tmp_path / "wrong_speed_preparation.jsonl", records))


def test_v4_facing_target_must_match_orientation_intent(tmp_path: Path) -> None:
    records = _v4_records()
    records[1]["applied_action"]["orientation_intent_world"] = [0.0, 1.0, 0.0]

    with pytest.raises(EpisodeValidationError, match="desired facing"):
        load_episode(_write(tmp_path / "wrong_facing_target.jsonl", records))


def test_v4_zero_orientation_requires_previous_facing_fallback(tmp_path: Path) -> None:
    records = _v4_records()
    records[1]["applied_action"]["orientation_intent_world"] = [0.0, 0.0, 5.0]
    records[1]["applied_action"]["used_previous_facing_for_zero_orientation_intent"] = True
    episode = load_episode(_write(tmp_path / "zero_orientation.jsonl", records))

    assert episode.transitions[0]["applied_action"][
        "used_previous_facing_for_zero_orientation_intent"
    ]


def test_v3_context_from_wrong_state_sequence_is_rejected(tmp_path: Path) -> None:
    records = _v3_records()
    records[1]["nominal_context"]["next"]["authoritative_state_sample_sequence"] = 99

    with pytest.raises(EpisodeValidationError, match="wrong state sequence"):
        load_episode(_write(tmp_path / "misaligned_context.jsonl", records))


def test_v3_completed_step_parameters_must_equal_next_snapshot(tmp_path: Path) -> None:
    records = _v3_records()
    records[1]["nominal_context"]["parameters_observed_for_completed_step"][
        "acceleration_cm_per_s2"
    ] = 999.0

    with pytest.raises(EpisodeValidationError, match="completed-step parameters"):
        load_episode(_write(tmp_path / "wrong_step_parameters.jsonl", records))


def test_v3_consecutive_rows_share_exact_hidden_endpoint(tmp_path: Path) -> None:
    records = _v3_records()
    records[2]["nominal_context"]["previous"]["internal_state"]["spring_velocity_world_cm_per_s"][
        0
    ] += 1.0

    with pytest.raises(EpisodeValidationError, match="same finalized endpoint"):
        load_episode(_write(tmp_path / "broken_hidden_chain.jsonl", records))


def test_v3_non_unit_internal_facing_is_rejected(tmp_path: Path) -> None:
    records = _v3_records()
    records[1]["nominal_context"]["next"]["internal_state"]["intermediate_facing_world_xyzw"] = [
        0.0,
        0.0,
        0.0,
        2.0,
    ]

    with pytest.raises(EpisodeValidationError, match="not unit length"):
        load_episode(_write(tmp_path / "bad_internal_facing.jsonl", records))


def test_v2_gate_state_that_disagrees_with_schedule_is_rejected(tmp_path: Path) -> None:
    records = _scenario_records()
    records[1]["scenario"]["next_gate_state"]["center_world_cm"][1] += 1.0

    with pytest.raises(EpisodeValidationError, match="analytic schedule"):
        load_episode(_write(tmp_path / "bad_gate.jsonl", records))


def test_v2_footer_must_match_final_terminal_event(tmp_path: Path) -> None:
    records = _scenario_records()
    records[-1]["scenario_summary"]["termination_reason"] = "timeout"

    with pytest.raises(EpisodeValidationError, match="final transition"):
        load_episode(_write(tmp_path / "bad_terminal.jsonl", records))


def test_v2_success_requires_a_real_forward_plane_crossing(tmp_path: Path) -> None:
    records = _scenario_records()
    records[1]["next_state"]["position_world_cm"][0] = 6.0
    records[2]["previous_state"]["position_world_cm"][0] = 6.0

    with pytest.raises(EpisodeValidationError, match="cross the fixed plane"):
        load_episode(_write(tmp_path / "false_success.jsonl", records))


def test_v2_timeout_cannot_precede_declared_deadline(tmp_path: Path) -> None:
    records = _scenario_records()
    records[2]["scenario"]["crossed_success_plane_this_step"] = False
    records[2]["scenario"]["termination_reason"] = "timeout"
    records[-1]["scenario_summary"]["termination_reason"] = "timeout"

    with pytest.raises(EpisodeValidationError, match="before the declared deadline"):
        load_episode(_write(tmp_path / "early_timeout.jsonl", records))


def test_missing_footer_rejects_partial_file(tmp_path: Path) -> None:
    with pytest.raises(EpisodeValidationError, match="footer"):
        load_episode(_write(tmp_path / "partial.jsonl", _records()[:-1]))


def test_non_finite_numeric_value_is_rejected(tmp_path: Path) -> None:
    records = _records()
    records[1]["next_state"]["position_world_cm"][0] = float("nan")

    with pytest.raises(EpisodeValidationError, match="finite"):
        load_episode(_write(tmp_path / "nan.jsonl", records))


def test_action_frame_mismatch_is_rejected(tmp_path: Path) -> None:
    records = _records()
    records[1]["applied_action"]["velocity_local_planar_cm_per_s"] = [0.0, 100.0, 0.0]

    with pytest.raises(EpisodeValidationError, match="local action"):
        load_episode(_write(tmp_path / "bad_action.jsonl", records))


def test_mixed_episode_identity_is_rejected(tmp_path: Path) -> None:
    records = _records()
    records[2]["episode_id"] = 43

    with pytest.raises(EpisodeValidationError, match="does not match the header"):
        load_episode(_write(tmp_path / "mixed.jsonl", records))


def test_consecutive_rows_must_share_the_exact_endpoint(tmp_path: Path) -> None:
    records = _records()
    records[2]["previous_state"]["position_world_cm"][0] = 999.0

    with pytest.raises(EpisodeValidationError, match="same finalized endpoint"):
        load_episode(_write(tmp_path / "broken_chain.jsonl", records))


def test_unknown_schema_field_is_rejected(tmp_path: Path) -> None:
    records = _records()
    records[0]["mystery"] = "silent schema drift"

    with pytest.raises(EpisodeValidationError, match="extra"):
        load_episode(_write(tmp_path / "extra.jsonl", records))


def test_explicit_rejection_gap_starts_a_new_contiguous_segment(tmp_path: Path) -> None:
    records = _records()
    recovery_previous = _state(12, 22, 1.1, 10.0)
    recovery_next = _state(13, 23, 1.15, 15.0)
    records[2] = _transition(2, recovery_previous, recovery_next)
    records[0]["recorder_stats"] = {
        "observed_state_count": 4,
        "attempted_transition_count": 3,
        "recorded_transition_count": 2,
        "rejected_transition_count": 1,
        "rejected_seed_state_count": 0,
        "capacity_drop_count": 0,
    }
    records[-1]["last_transition_sequence"] = 2

    episode = load_episode(_write(tmp_path / "gap.jsonl", records))

    assert [row["transition_sequence"] for row in episode.transitions] == [0, 2]
