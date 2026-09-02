from __future__ import annotations

import copy

import numpy as np

from motionworld.dynamics.nominal_rollout import evaluate_recursive_nominal_rollouts
from motionworld.models.residual_features import (
    RESIDUAL_HISTORY_FEATURE_COUNT,
    RESIDUAL_STEP_FEATURE_COUNT,
)
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import ResidualNormalization
from motionworld.models.residual_rollout import evaluate_recursive_residual_rollouts


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
        "input_preparation": {
            "has_max_move_speed": True,
            "effective_max_speed_cm_per_s": 165.0,
            "max_speed_source": "mode_override",
        },
        "internal_state": {
            "spring_velocity_world_cm_per_s": [0.0, 0.0, 0.0],
            "spring_acceleration_world_cm_per_s2": [0.0, 0.0, 0.0],
            "intermediate_velocity_world_cm_per_s": [0.0, 0.0, 0.0],
            "intermediate_facing_world_xyzw": [0.0, 0.0, 0.0, 1.0],
            "intermediate_angular_velocity_world_rad_per_s": [0.0, 0.0, 0.0],
        },
    }


def _stationary_transitions(count: int = 8) -> list[dict[str, object]]:
    return [
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
        }
        for sequence in range(count)
    ]


def _normalization(history_length: int) -> ResidualNormalization:
    width = RESIDUAL_STEP_FEATURE_COUNT if history_length == 1 else RESIDUAL_HISTORY_FEATURE_COUNT
    return ResidualNormalization(
        history_length=history_length,
        train_episode_ids=(1,),
        sample_count=1,
        feature_mean=np.zeros(width),
        feature_scale=np.ones(width),
        constant_feature_mask=np.ones(width, dtype=bool),
        target_scale=np.ones(6),
        constant_target_mask=np.ones(6, dtype=bool),
    )


def _zero_model(history_length: int) -> ResidualMLP:
    width = RESIDUAL_STEP_FEATURE_COUNT if history_length == 1 else RESIDUAL_HISTORY_FEATURE_COUNT
    return ResidualMLP(width, hidden_widths=(8,))


def test_zero_residual_rollout_matches_hold_current_nominal_exactly() -> None:
    transitions = _stationary_transitions()
    nominal = evaluate_recursive_nominal_rollouts(
        transitions,
        horizons_s=(0.2, 0.4),
        parameter_policy="hold-current",
    )
    residual = evaluate_recursive_residual_rollouts(
        transitions,
        model=_zero_model(1),
        normalization=_normalization(1),
        history_length=1,
        horizons_s=(0.2, 0.4),
    )

    assert len(residual) == len(nominal)
    for residual_row, nominal_row in zip(residual, nominal, strict=True):
        assert residual_row.start_transition_sequence == nominal_row.start_transition_sequence
        assert residual_row.end_transition_sequence == nominal_row.end_transition_sequence
        assert residual_row.planar_position_error_cm == nominal_row.planar_position_error_cm
        assert residual_row.planar_velocity_error_cm_s == nominal_row.planar_velocity_error_cm_s
        assert residual_row.yaw_error_deg == nominal_row.yaw_error_deg


def test_four_history_starts_only_after_three_past_queries() -> None:
    rows = evaluate_recursive_residual_rollouts(
        _stationary_transitions(),
        model=_zero_model(4),
        normalization=_normalization(4),
        history_length=4,
        horizons_s=(0.2,),
    )

    assert rows
    assert min(row.start_transition_sequence for row in rows) == 3


def test_rollout_does_not_reseed_from_intermediate_real_state() -> None:
    transitions = _stationary_transitions(5)
    corrupted = copy.deepcopy(transitions)
    corrupted[1]["previous_state"]["position_world_cm"] = [999.0, 0.0, 0.0]

    original = evaluate_recursive_residual_rollouts(
        transitions,
        model=_zero_model(1),
        normalization=_normalization(1),
        history_length=1,
        horizons_s=(0.3,),
    )
    changed = evaluate_recursive_residual_rollouts(
        corrupted,
        model=_zero_model(1),
        normalization=_normalization(1),
        history_length=1,
        horizons_s=(0.3,),
    )

    assert next(row for row in changed if row.start_transition_sequence == 0) == next(
        row for row in original if row.start_transition_sequence == 0
    )
