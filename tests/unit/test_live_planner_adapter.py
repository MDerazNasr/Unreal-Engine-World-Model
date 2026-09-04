from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from motionworld.control.live_planner_adapter import LivePlannerSnapshotAdapter

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OBSERVATION_FIXTURE = (
    REPOSITORY_ROOT
    / "unreal"
    / "Plugins"
    / "MotionWorld"
    / "Resources"
    / "ProtocolFixtures"
    / "v1"
    / "observation.json"
)


def _observation(sequence: int, *, episode_id: int = 7101) -> dict[str, object]:
    value = json.loads(OBSERVATION_FIXTURE.read_text(encoding="utf-8"))
    value["identity"]["episode_id"] = episode_id
    value["identity"]["observation_sequence"] = sequence
    value["identity"]["state_sample_sequence"] = 43 + sequence
    value["nominal_context"]["authoritative_state_sample_sequence"] = 43 + sequence
    value["timing"]["simulation_time_s"] = 1.25 + 0.1 * sequence
    value["planner_context"]["timed_gate"]["scenario_time_s"] = 1.0 + 0.1 * sequence
    if sequence == 0:
        value["previous_action"] = {"is_present": False}
    else:
        value["previous_action"]["source_observation_sequence"] = sequence - 1
        value["previous_action"]["applied_local_velocity_cm_per_s"] = [
            100.0 + sequence,
            -float(sequence),
        ]
    return value


def test_converts_authoritative_state_hidden_context_and_units() -> None:
    result = LivePlannerSnapshotAdapter().adapt(_observation(0))

    assert (result.episode_id, result.observation_sequence, result.state_sample_sequence) == (
        7101,
        0,
        43,
    )
    assert result.previous_action_local_cm_s == (0.0, 0.0)
    assert result.previous_previous_action_local_cm_s == (0.0, 0.0)
    assert np.array_equal(result.snapshot.observable.position_world_cm, [10.0, 20.0, 86.0])
    assert np.array_equal(result.snapshot.observable.velocity_world_cm_s, [100.0, 0.0, 0.0])
    assert result.snapshot.observable.facing_yaw_rad == pytest.approx(math.radians(0.0))
    assert result.snapshot.observable.angular_velocity_yaw_deg_s == 5.0
    assert result.snapshot.observable.simulation_time_s == 1.25
    assert np.array_equal(
        result.snapshot.internal.velocity.spring_acceleration_world_cm_s2,
        [1.0, 2.0, 0.0],
    )
    assert result.snapshot.internal.facing.intermediate_angular_velocity_yaw_rad_s == 0.1
    assert result.snapshot.parameters.turning_strength_s_inv == 8.0
    assert result.snapshot.effective_max_speed_cm_s == 165.0
    assert result.target_world_xy_cm == (700.0, 0.0)
    assert result.scenario_time_s == 1.0

    query = result.to_planner_query()
    assert query.snapshot is result.snapshot
    assert query.scenario_time_s == 1.0
    assert query.previous_action_local_cm_s == (0.0, 0.0)
    assert query.previous_previous_action_local_cm_s == (0.0, 0.0)


def test_recovers_two_action_history_slots_from_contiguous_stream() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    first = adapter.adapt(_observation(1))
    second = adapter.adapt(_observation(2))

    assert first.previous_action_local_cm_s == (101.0, -1.0)
    assert first.previous_previous_action_local_cm_s == (0.0, 0.0)
    assert second.previous_action_local_cm_s == (102.0, -2.0)
    assert second.previous_previous_action_local_cm_s == (101.0, -1.0)


def test_episode_zero_clears_cached_action_history() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    adapter.adapt(_observation(1))

    reset = adapter.adapt(_observation(0, episode_id=7102))

    assert reset.previous_action_local_cm_s == (0.0, 0.0)
    assert reset.previous_previous_action_local_cm_s == (0.0, 0.0)


def test_old_episode_cannot_be_reintroduced_after_reset() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0, episode_id=7101))
    adapter.adapt(_observation(0, episode_id=7102))
    with pytest.raises(ValueError, match="must increase"):
        adapter.adapt(_observation(0, episode_id=7101))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["source"].update(movement_mode="Flying"), "Walking"),
        (
            lambda value: value["nominal_context"].update(
                movement_mode_class="BP_MovementMode_Flying_C"
            ),
            "Smooth Walking",
        ),
        (
            lambda value: value["state"].update(
                velocity_local_planar_cm_per_s=[0.0, 100.0]
            ),
            "velocities disagree",
        ),
        (
            lambda value: value["nominal_context"]["input_preparation"].update(
                effective_max_speed_cm_per_s=0.0
            ),
            "must be positive",
        ),
    ],
)
def test_fails_closed_on_missing_or_inconsistent_planner_context(mutation, message: str) -> None:
    value = _observation(0)
    mutation(value)
    with pytest.raises(ValueError, match=message):
        LivePlannerSnapshotAdapter().adapt(value)


def test_rejection_does_not_advance_adapter_state() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    invalid = _observation(1)
    invalid["state"]["velocity_local_planar_cm_per_s"] = [0.0, 100.0]
    with pytest.raises(ValueError, match="velocities disagree"):
        adapter.adapt(invalid)

    accepted = adapter.adapt(_observation(1))
    assert accepted.observation_sequence == 1


def test_simulation_time_must_strictly_increase_without_mutating_state() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    invalid = _observation(1)
    invalid["timing"]["simulation_time_s"] = 1.25
    with pytest.raises(ValueError, match="simulation time must strictly increase"):
        adapter.adapt(invalid)

    assert adapter.adapt(_observation(1)).observation_sequence == 1


def test_applied_action_source_may_hold_only_with_the_same_value() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    first = _observation(1)
    first["previous_action"]["applied_local_velocity_cm_per_s"] = [101.0, -1.0]
    adapter.adapt(first)

    held = _observation(2)
    held["previous_action"]["source_observation_sequence"] = 0
    held["previous_action"]["applied_local_velocity_cm_per_s"] = [101.0, -1.0]
    result = adapter.adapt(held)
    assert result.previous_previous_action_local_cm_s == (101.0, -1.0)


def test_applied_action_source_regression_is_rejected_without_mutating_state() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    adapter.adapt(_observation(1))
    adapter.adapt(_observation(2))
    invalid = _observation(3)
    invalid["previous_action"]["source_observation_sequence"] = 0
    with pytest.raises(ValueError, match="must not regress"):
        adapter.adapt(invalid)

    assert adapter.adapt(_observation(3)).observation_sequence == 3


def test_repeated_action_source_with_changed_value_is_rejected() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    adapter.adapt(_observation(1))
    invalid = _observation(2)
    invalid["previous_action"]["source_observation_sequence"] = 0
    invalid["previous_action"]["applied_local_velocity_cm_per_s"] = [99.0, 4.0]
    with pytest.raises(ValueError, match="must retain its value"):
        adapter.adapt(invalid)

    assert adapter.adapt(_observation(2)).observation_sequence == 2


def test_gate_free_snapshot_uses_zero_scenario_time_and_requires_target_for_mpc() -> None:
    gate_free = _observation(0)
    gate_free["planner_context"]["timed_gate"] = {"is_present": False}
    gate_free["validity"]["timed_gate_present"] = False
    result = LivePlannerSnapshotAdapter().adapt(gate_free)
    assert result.scenario_time_s == 0.0
    assert result.to_planner_query().scenario_time_s == 0.0

    no_target = _observation(0)
    no_target["planner_context"]["target"] = {"is_present": False}
    no_target["validity"]["target_present"] = False
    missing = LivePlannerSnapshotAdapter().adapt(no_target)
    assert missing.target_world_xy_cm is None
    with pytest.raises(ValueError, match="requires an authoritative target"):
        missing.to_planner_query()


def test_gap_or_duplicate_is_rejected() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    with pytest.raises(ValueError, match="contiguous"):
        adapter.adapt(_observation(2))

    adapter.adapt(_observation(1))
    with pytest.raises(ValueError, match="contiguous"):
        adapter.adapt(_observation(1))


def test_adapter_cannot_join_an_episode_midstream() -> None:
    with pytest.raises(ValueError, match="must begin"):
        LivePlannerSnapshotAdapter().adapt(_observation(4))


def test_explicit_reset_requires_a_new_sequence_zero() -> None:
    adapter = LivePlannerSnapshotAdapter()
    adapter.adapt(_observation(0))
    adapter.reset()
    with pytest.raises(ValueError, match="must begin"):
        adapter.adapt(_observation(1))


def test_input_is_detached_from_planner_arrays() -> None:
    value = _observation(0)
    result = LivePlannerSnapshotAdapter().adapt(value)
    value["state"]["position_world_cm"][0] = 999.0
    assert result.snapshot.observable.position_world_cm[0] == 10.0
