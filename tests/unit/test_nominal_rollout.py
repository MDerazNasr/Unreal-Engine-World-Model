import copy
import math

import pytest

from motionworld.dynamics.nominal_rollout import evaluate_recursive_nominal_rollouts


def _parameters() -> dict[str, float | bool]:
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
        "facing_smoothing_time_s": 0.4,
        "smooth_facing_with_double_spring": False,
        "facing_deadzone_deg": 0.1,
        "angular_velocity_deadzone_deg_per_s": 0.01,
    }


def _state(sequence: int, time_s: float) -> dict[str, object]:
    return {
        "sample_sequence": sequence,
        "simulation_time_s": time_s,
        "position_world_cm": [0.0, 0.0, 0.0],
        "velocity_world_cm_per_s": [0.0, 0.0, 0.0],
        "facing_yaw_deg": 0.0,
        "angular_velocity_world_deg_per_s": [0.0, 0.0, 0.0],
    }


def _context(sequence: int) -> dict[str, object]:
    return {
        "authoritative_state_sample_sequence": sequence,
        "parameters": _parameters(),
        "internal_state": {
            "spring_velocity_world_cm_per_s": [0.0, 0.0, 0.0],
            "spring_acceleration_world_cm_per_s2": [0.0, 0.0, 0.0],
            "intermediate_velocity_world_cm_per_s": [0.0, 0.0, 0.0],
            "intermediate_facing_world_xyzw": [0.0, 0.0, 0.0, 1.0],
            "intermediate_angular_velocity_world_rad_per_s": [0.0, 0.0, 0.0],
        },
    }


def _stationary_transitions(count: int = 5) -> list[dict[str, object]]:
    transitions: list[dict[str, object]] = []
    for sequence in range(count):
        transitions.append(
            {
                "transition_sequence": sequence,
                "delta_time_s": 0.1,
                "previous_state": _state(sequence, sequence * 0.1),
                "next_state": _state(sequence + 1, (sequence + 1) * 0.1),
                "applied_action": {
                    "velocity_world_cm_per_s": [0.0, 0.0, 0.0],
                    "desired_facing_yaw_deg": 0.0,
                },
                "nominal_context": {
                    "previous": _context(sequence),
                    "next": _context(sequence + 1),
                    "parameters_observed_for_completed_step": _parameters(),
                    "input_preparation_observed_for_completed_step": {
                        "has_max_move_speed": True,
                        "effective_max_speed_cm_per_s": 165.0,
                    },
                },
                "scenario": None,
            }
        )
    return transitions


def test_stationary_recursive_rollout_remains_exact() -> None:
    rows = evaluate_recursive_nominal_rollouts(
        _stationary_transitions(),
        horizons_s=(0.2, 0.4),
    )

    assert {row.requested_horizon_s for row in rows} == {0.2, 0.4}
    assert all(row.planar_position_error_cm == 0.0 for row in rows)
    assert all(row.planar_velocity_error_cm_s == 0.0 for row in rows)
    assert all(row.yaw_error_deg == 0.0 for row in rows)
    assert all(row.external_perturbation_step_count == 0 for row in rows)
    assert all(row.perturbation_relation == "no_event" for row in rows)


def test_recursive_rollouts_label_event_crossing_without_using_event_as_input() -> None:
    transitions = _stationary_transitions(5)
    for transition in transitions:
        transition["external_perturbation"] = {"type": "none"}
    transitions[2]["external_perturbation"] = {"type": "additive_velocity"}

    rows = evaluate_recursive_nominal_rollouts(transitions, horizons_s=(0.2,))

    relations = {
        row.start_transition_sequence: (
            row.perturbation_relation,
            row.external_perturbation_step_count,
        )
        for row in rows
    }
    assert relations == {
        0: ("pre_event", 0),
        1: ("event_crossing", 1),
        2: ("event_crossing", 1),
        3: ("post_event", 0),
    }


def test_recursive_rollout_rejects_multiple_perturbations() -> None:
    transitions = _stationary_transitions(3)
    for transition in transitions:
        transition["external_perturbation"] = {"type": "additive_velocity"}

    with pytest.raises(ValueError, match="at most one"):
        evaluate_recursive_nominal_rollouts(transitions, horizons_s=(0.2,))


def test_rollout_does_not_reseed_from_intermediate_real_state() -> None:
    transitions = _stationary_transitions(3)
    corrupted = copy.deepcopy(transitions)
    corrupted[1]["previous_state"]["position_world_cm"] = [999.0, 0.0, 0.0]

    rows = evaluate_recursive_nominal_rollouts(corrupted, horizons_s=(0.3,))
    from_first = next(row for row in rows if row.start_transition_sequence == 0)

    assert from_first.end_transition_sequence == 2
    assert from_first.step_count == 3
    assert from_first.planar_position_error_cm == 0.0


@pytest.mark.parametrize(
    "horizons",
    [(), (0.0,), (-0.1,), (math.nan,), (math.inf,), (0.5, 0.5)],
)
def test_invalid_horizons_fail_closed(horizons: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="horizons"):
        evaluate_recursive_nominal_rollouts(
            _stationary_transitions(),
            horizons_s=horizons,
        )


def test_empty_transitions_fail_closed() -> None:
    with pytest.raises(ValueError, match="transitions"):
        evaluate_recursive_nominal_rollouts([])


def test_horizon_longer_than_episode_fails_with_clear_error() -> None:
    with pytest.raises(ValueError, match="exceeds the complete episode duration"):
        evaluate_recursive_nominal_rollouts(
            _stationary_transitions(3),
            horizons_s=(0.31,),
        )
