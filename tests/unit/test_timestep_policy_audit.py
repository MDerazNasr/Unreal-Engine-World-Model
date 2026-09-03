from __future__ import annotations

import math

import numpy as np

from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState
from scripts.audit_timestep_policy import (
    FIXED_POLICIES,
    _interpolated_observable,
    _planar_local_action,
    _recorded_schedule,
)


def _state(time_s: float, yaw_deg: float) -> dict[str, object]:
    return {
        "position_world_cm": [10.0 * time_s, 0.0, 0.0],
        "velocity_world_cm_per_s": [10.0, 0.0, 0.0],
        "facing_yaw_deg": yaw_deg,
        "angular_velocity_world_deg_per_s": [0.0, 0.0, 20.0],
        "simulation_time_s": time_s,
    }


def test_fixed_schedules_are_exactly_one_control_interval() -> None:
    assert len(FIXED_POLICIES["fixed_30_hz"]) == 3
    assert len(FIXED_POLICIES["fixed_60_hz"]) == 6
    assert math.fsum(FIXED_POLICIES["fixed_30_hz"]) == 0.1
    assert math.fsum(FIXED_POLICIES["fixed_60_hz"]) == 0.1


def test_recorded_schedule_truncates_only_final_step() -> None:
    transitions = tuple(
        {"delta_time_s": value} for value in (0.027, 0.030, 0.025, 0.028)
    )
    schedule = _recorded_schedule(transitions, 0, 3)
    np.testing.assert_allclose(schedule, (0.027, 0.030, 0.025, 0.018))
    assert math.isclose(math.fsum(schedule), 0.1, abs_tol=1.0e-15)


def test_authoritative_interpolation_uses_shortest_yaw_path() -> None:
    transition = {
        "previous_state": _state(2.0, 179.0),
        "next_state": _state(2.2, -179.0),
    }
    result = _interpolated_observable(transition, 2.1)
    assert isinstance(result, SmoothWalkingObservableState)
    assert result.position_world_cm[0] == 21.0
    assert abs(abs(math.degrees(result.facing_yaw_rad)) - 180.0) < 1.0e-12
    assert result.simulation_time_s == 2.1


def test_unreal_local_action_requires_zero_z_and_returns_xy() -> None:
    record = {"velocity_local_planar_cm_per_s": [12.0, -4.0, 0.0]}
    np.testing.assert_array_equal(_planar_local_action(record), [12.0, -4.0])
