from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from motionworld.planning.cem import CEMConfig
from motionworld.planning.offline_context import build_counterfactual_query
from tests.unit.test_nominal_episode import _transition


def _source() -> SimpleNamespace:
    transition = _transition()
    transition["applied_action"]["desired_facing_yaw_deg"] = 20.0
    return SimpleNamespace(episode=SimpleNamespace(transitions=(transition,)))


def _problem_config() -> dict[str, object]:
    return {
        "counterfactual_start_world_cm": (-100.0, 25.0),
        "initial_mean_action_local_cm_s": (70.0, -10.0),
        "initial_scenario_time_s": 0.5,
        "previous_action_local_cm_s": (1.0, 2.0),
        "previous_previous_action_local_cm_s": (3.0, 4.0),
    }


def test_counterfactual_query_relocates_only_planar_position() -> None:
    query = build_counterfactual_query(
        _source(),
        0,
        problem_config=_problem_config(),
        cem=CEMConfig(max_action_speed_cm_s=120.0, num_knots=5),
    )
    np.testing.assert_array_equal(
        query.snapshot.observable.position_world_cm,
        [-100.0, 25.0, 30.0],
    )
    np.testing.assert_array_equal(query.snapshot.observable.velocity_world_cm_s, [7.0, 8.0, 0.0])
    np.testing.assert_array_equal(
        query.initial_mean_knots_local_cm_s,
        np.tile([70.0, -10.0], (5, 1)),
    )
    assert query.snapshot.internal.velocity.spring_velocity_world_cm_s[0] == 1.0
    assert query.scenario_time_s == 0.5


def test_counterfactual_query_rejects_wrong_speed_or_transition_index() -> None:
    with pytest.raises(ValueError, match="maximum speeds differ"):
        build_counterfactual_query(
            _source(),
            0,
            problem_config=_problem_config(),
            cem=CEMConfig(max_action_speed_cm_s=165.0),
        )
    with pytest.raises(ValueError, match="outside"):
        build_counterfactual_query(
            _source(),
            1,
            problem_config=_problem_config(),
            cem=CEMConfig(max_action_speed_cm_s=120.0),
        )
