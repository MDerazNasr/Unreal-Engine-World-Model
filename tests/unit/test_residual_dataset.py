import copy
import math
from pathlib import Path

import numpy as np
import pytest

from motionworld.data import ValidatedEpisode
from motionworld.dynamics.smooth_walking_facing import SmoothWalkingFacingState
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingAction,
    SmoothWalkingInternalState,
    SmoothWalkingObservableState,
    planar_yaw_to_quaternion_xyzw,
    smooth_walking_nominal_step,
)
from motionworld.dynamics.smooth_walking_velocity import (
    SmoothWalkingParameters,
    SmoothWalkingVelocityState,
)
from motionworld.models.residual_dataset import (
    build_residual_dataset,
    build_residual_examples,
)


def _parameters() -> SmoothWalkingParameters:
    return SmoothWalkingParameters(
        acceleration_cm_s2=500.0,
        deceleration_cm_s2=300.0,
        directional_acceleration_factor=1.0,
        turning_strength_s_inv=8.0,
        acceleration_smoothing_time_s=0.1,
        deceleration_smoothing_time_s=0.2,
        acceleration_smoothing_compensation=0.0,
        deceleration_smoothing_compensation=0.0,
        velocity_deadzone_cm_s=0.01,
        acceleration_deadzone_cm_s2=0.001,
        outside_influence_smoothing_time_s=0.05,
        facing_smoothing_time_s=0.4,
        smooth_facing_with_double_spring=False,
        facing_deadzone_deg=0.1,
        angular_velocity_deadzone_deg_s=0.01,
    )


def _parameter_record(parameters: SmoothWalkingParameters) -> dict[str, object]:
    return {
        "acceleration_cm_per_s2": parameters.acceleration_cm_s2,
        "deceleration_cm_per_s2": parameters.deceleration_cm_s2,
        "directional_acceleration_factor": parameters.directional_acceleration_factor,
        "turning_strength": parameters.turning_strength_s_inv,
        "acceleration_smoothing_time_s": parameters.acceleration_smoothing_time_s,
        "deceleration_smoothing_time_s": parameters.deceleration_smoothing_time_s,
        "acceleration_smoothing_compensation": parameters.acceleration_smoothing_compensation,
        "deceleration_smoothing_compensation": parameters.deceleration_smoothing_compensation,
        "velocity_deadzone_cm_per_s": parameters.velocity_deadzone_cm_s,
        "acceleration_deadzone_cm_per_s2": parameters.acceleration_deadzone_cm_s2,
        "outside_influence_smoothing_time_s": parameters.outside_influence_smoothing_time_s,
        "facing_smoothing_time_s": parameters.facing_smoothing_time_s,
        "smooth_facing_with_double_spring": parameters.smooth_facing_with_double_spring,
        "facing_deadzone_deg": parameters.facing_deadzone_deg,
        "angular_velocity_deadzone_deg_per_s": parameters.angular_velocity_deadzone_deg_s,
    }


def _state_record(state: SmoothWalkingObservableState, sequence: int) -> dict[str, object]:
    return {
        "sample_sequence": sequence,
        "simulation_time_s": state.simulation_time_s,
        "position_world_cm": state.position_world_cm.tolist(),
        "velocity_world_cm_per_s": state.velocity_world_cm_s.tolist(),
        "facing_yaw_deg": math.degrees(state.facing_yaw_rad),
        "angular_velocity_world_deg_per_s": [
            0.0,
            0.0,
            state.angular_velocity_yaw_deg_s,
        ],
    }


def _context_record(
    state: SmoothWalkingObservableState,
    internal: SmoothWalkingInternalState,
    parameters: SmoothWalkingParameters,
) -> dict[str, object]:
    return {
        "authoritative_state_sample_sequence": 0,
        "parameters": _parameter_record(parameters),
        "input_preparation": {
            "has_max_move_speed": True,
            "effective_max_speed_cm_per_s": 165.0,
            "max_speed_source": "test",
        },
        "internal_state": {
            "spring_velocity_world_cm_per_s": (
                internal.velocity.spring_velocity_world_cm_s.tolist()
            ),
            "spring_acceleration_world_cm_per_s2": (
                internal.velocity.spring_acceleration_world_cm_s2.tolist()
            ),
            "intermediate_velocity_world_cm_per_s": (
                internal.velocity.intermediate_velocity_world_cm_s.tolist()
            ),
            "intermediate_facing_world_xyzw": planar_yaw_to_quaternion_xyzw(
                internal.facing.intermediate_facing_yaw_rad
            ).tolist(),
            "intermediate_angular_velocity_world_rad_per_s": [
                0.0,
                0.0,
                internal.facing.intermediate_angular_velocity_yaw_rad_s,
            ],
        },
    }


def _episode(
    *,
    episode_id: int = 101,
    count: int = 6,
    position_error_index: int | None = None,
    event_index: int | None = None,
) -> ValidatedEpisode:
    parameters = _parameters()
    observable = SmoothWalkingObservableState(
        position_world_cm=np.asarray([0.0, 0.0, 88.0]),
        velocity_world_cm_s=np.zeros(3),
        facing_yaw_rad=0.0,
        angular_velocity_yaw_deg_s=0.0,
        simulation_time_s=0.0,
    )
    internal = SmoothWalkingInternalState(
        velocity=SmoothWalkingVelocityState(
            spring_velocity_world_cm_s=np.zeros(3),
            spring_acceleration_world_cm_s2=np.zeros(3),
            intermediate_velocity_world_cm_s=np.zeros(3),
        ),
        facing=SmoothWalkingFacingState(
            intermediate_facing_yaw_rad=0.0,
            intermediate_angular_velocity_yaw_rad_s=0.0,
        ),
    )
    action = SmoothWalkingAction(
        desired_velocity_world_cm_s=np.asarray([100.0, 0.0, 0.0]),
        desired_facing_yaw_rad=0.0,
    )
    transitions: list[dict[str, object]] = []
    for index in range(count):
        previous = observable
        previous_internal = internal
        nominal_step = smooth_walking_nominal_step(
            previous,
            previous_internal,
            action,
            parameters=parameters,
            dt_s=0.02,
        )
        observable = nominal_step.observable_next
        internal = nominal_step.internal_next
        if index == position_error_index:
            shifted_position = observable.position_world_cm.copy()
            shifted_position[0] += 2.0
            observable = SmoothWalkingObservableState(
                position_world_cm=shifted_position,
                velocity_world_cm_s=observable.velocity_world_cm_s,
                facing_yaw_rad=observable.facing_yaw_rad,
                angular_velocity_yaw_deg_s=observable.angular_velocity_yaw_deg_s,
                simulation_time_s=observable.simulation_time_s,
            )
        transitions.append(
            {
                "episode_id": episode_id,
                "transition_sequence": index,
                "delta_time_s": 0.02,
                "previous_state": _state_record(previous, 100 + index),
                "next_state": _state_record(observable, 101 + index),
                "applied_action": {
                    "velocity_world_cm_per_s": [100.0, 0.0, 0.0],
                    "desired_facing_yaw_deg": 0.0,
                },
                "nominal_context": {
                    "previous": _context_record(
                        previous,
                        previous_internal,
                        parameters,
                    ),
                    "parameters_observed_for_completed_step": _parameter_record(
                        parameters
                    ),
                },
                "external_perturbation": {
                    "type": "additive_velocity" if index == event_index else "none"
                },
            }
        )
    return ValidatedEpisode(
        path=Path(f"episode_{episode_id}.jsonl"),
        header={"episode_id": episode_id},
        transitions=tuple(transitions),
        footer={"complete": True},
    )


def test_no_history_builds_one_example_per_transition() -> None:
    examples = build_residual_examples(_episode(), history_length=1)

    assert len(examples) == 6
    assert [example.transition_sequence for example in examples] == list(range(6))
    assert all(example.features.shape == (28,) for example in examples)
    assert all(example.target.shape == (6,) for example in examples)


def test_four_history_rejects_incomplete_prefix_and_preserves_sequences() -> None:
    examples = build_residual_examples(_episode(), history_length=4)

    assert len(examples) == 3
    assert examples[0].history_transition_sequences == (0, 1, 2, 3)
    assert examples[-1].history_transition_sequences == (2, 3, 4, 5)
    assert all(example.features.shape == (112,) for example in examples)


def test_target_is_actual_next_minus_causal_nominal() -> None:
    examples = build_residual_examples(
        _episode(position_error_index=2),
        history_length=1,
    )

    np.testing.assert_allclose(examples[2].target, [2.0, 0.0, 0.0, 0.0, 0.0, 0.0])


def test_hidden_event_is_excluded_as_target_but_can_remain_in_past_history() -> None:
    episode = _episode(event_index=3)

    excluded = build_residual_examples(episode, history_length=4)
    included = build_residual_examples(
        episode,
        history_length=4,
        exclude_hidden_external_events=False,
    )

    assert [example.transition_sequence for example in excluded] == [4, 5]
    assert [example.transition_sequence for example in included] == [3, 4, 5]
    assert excluded[0].history_transition_sequences == (1, 2, 3, 4)


def test_completed_step_future_parameters_cannot_change_example() -> None:
    episode = _episode()
    changed = copy.deepcopy(episode)
    changed.transitions[2]["nominal_context"]["parameters_observed_for_completed_step"][
        "acceleration_cm_per_s2"
    ] = 999999.0

    original_example = build_residual_examples(episode, history_length=1)[2]
    changed_example = build_residual_examples(changed, history_length=1)[2]

    np.testing.assert_array_equal(changed_example.features, original_example.features)
    np.testing.assert_array_equal(changed_example.target, original_example.target)


def test_state_sequence_gap_fails_closed() -> None:
    episode = _episode()
    episode.transitions[3]["previous_state"]["sample_sequence"] += 10
    episode.transitions[3]["next_state"]["sample_sequence"] += 10

    with pytest.raises(ValueError, match="reset or gap"):
        build_residual_examples(episode, history_length=1)


def test_transition_sequence_gap_fails_closed() -> None:
    episode = _episode()
    episode.transitions[3]["transition_sequence"] += 10

    with pytest.raises(ValueError, match="not consecutive"):
        build_residual_examples(episode, history_length=1)


def test_nonadjacent_state_pair_fails_closed() -> None:
    episode = _episode()
    episode.transitions[2]["next_state"]["sample_sequence"] += 1

    with pytest.raises(ValueError, match="adjacent state"):
        build_residual_examples(episode, history_length=1)


def test_dataset_windows_each_episode_independently() -> None:
    examples = build_residual_dataset(
        (_episode(episode_id=101, count=4), _episode(episode_id=202, count=4)),
        history_length=4,
    )

    assert len(examples) == 2
    assert {example.episode_id for example in examples} == {101, 202}
    assert all(example.history_transition_sequences == (0, 1, 2, 3) for example in examples)


def test_duplicate_episode_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_residual_dataset((_episode(), _episode()), history_length=1)


@pytest.mark.parametrize("history_length", [0, 2, 3, 5])
def test_unsupported_history_length_is_rejected(history_length: int) -> None:
    with pytest.raises(ValueError, match="must be 1 or 4"):
        build_residual_examples(_episode(), history_length=history_length)
