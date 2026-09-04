"""Strict stateful adapter from live control observations to planner snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from motionworld.dynamics.coordinates import YawRadians, world_vector_to_local
from motionworld.dynamics.nominal_episode import (
    internal_from_context_record,
    smooth_walking_parameters_from_record,
)
from motionworld.dynamics.smooth_walking_nominal import SmoothWalkingObservableState
from motionworld.planning.mpc import PlannerProblem, PlannerQuery
from motionworld.planning.planner_rollout import PlannerSnapshot
from motionworld.protocol.observation import validate_observation_mapping

_ZERO_ACTION = (0.0, 0.0)
# These exact strings are frozen demo/runtime protocol constants mirrored from the
# Unreal Smooth Walking Blueprint. Changing them requires updating Unreal and its
# protocol fixtures together; fuzzy or case-insensitive matching would hide drift.
_SMOOTH_WALKING_MODE = "Walking"
_SMOOTH_WALKING_CLASS = "BP_MovementMode_Walking_C"


@dataclass(frozen=True, slots=True)
class LivePlannerSnapshot:
    """Planner state plus the source identity and causally available action history."""

    snapshot: PlannerSnapshot
    episode_id: int
    observation_sequence: int
    state_sample_sequence: int
    previous_action_local_cm_s: tuple[float, float]
    previous_previous_action_local_cm_s: tuple[float, float]
    target_world_xy_cm: tuple[float, float] | None
    scenario_time_s: float
    timed_gate_is_present: bool = False
    timed_gate_contract: tuple[float, ...] | None = None
    has_contiguous_action_history: bool = False

    def to_planner_query(self) -> PlannerQuery:
        """Build the causal MPC query, requiring a goal-bearing observation.

        The goal remains a separate field because it belongs in ``PlannerProblem``;
        requiring it here prevents a caller from accidentally launching goal-free MPC.
        """

        if not self.has_contiguous_action_history:
            raise ValueError("live MPC requires contiguous action history")
        if self.target_world_xy_cm is None:
            raise ValueError("live MPC requires an authoritative target")
        return PlannerQuery(
            snapshot=self.snapshot,
            scenario_time_s=self.scenario_time_s,
            previous_action_local_cm_s=self.previous_action_local_cm_s,
            previous_previous_action_local_cm_s=self.previous_previous_action_local_cm_s,
        )

    def to_stateless_mpc_query(self, problem: PlannerProblem) -> PlannerQuery:
        """Build the restricted gate-free query that needs no prior-prior action.

        A standalone mid-episode packet cannot recover the prior-prior action.
        This is truthful only when every unavailable-history and absent-gate cost
        has exactly zero weight.
        """

        if not isinstance(problem, PlannerProblem):
            raise TypeError("problem must be a PlannerProblem")
        if self.target_world_xy_cm is None:
            raise ValueError("stateless live MPC requires an authoritative target")
        if problem.goal_world_cm != self.target_world_xy_cm:
            raise ValueError("stateless live MPC problem goal must equal the authoritative target")
        weights = problem.weights
        if weights.collision != 0.0:
            raise ValueError("stateless live MPC requires zero collision weight")
        if weights.clearance_per_cm2 != 0.0:
            raise ValueError("stateless live MPC requires zero clearance weight")
        if weights.action_second_difference_per_cm2_s2 != 0.0:
            raise ValueError("stateless live MPC requires zero action-second-difference weight")
        return PlannerQuery(
            snapshot=self.snapshot,
            scenario_time_s=self.scenario_time_s,
            previous_action_local_cm_s=self.previous_action_local_cm_s,
            previous_previous_action_local_cm_s=_ZERO_ACTION,
        )

    def to_stateless_obstacle_mpc_query(self, problem: PlannerProblem) -> PlannerQuery:
        """Build a mid-episode query using the authoritative moving-obstacle clock.

        Collision and clearance do not consume the unavailable prior-prior action.
        The second-action-difference term must remain disabled so this stateless
        live path never invents history.
        """

        if not isinstance(problem, PlannerProblem):
            raise TypeError("problem must be a PlannerProblem")
        if self.target_world_xy_cm is None:
            raise ValueError("moving-obstacle MPC requires an authoritative target")
        if problem.goal_world_cm != self.target_world_xy_cm:
            raise ValueError("moving-obstacle MPC goal must equal the authoritative target")
        if not self.timed_gate_is_present:
            raise ValueError("moving-obstacle MPC requires authoritative obstacle timing")
        if self.timed_gate_contract is None:
            raise ValueError("moving-obstacle MPC requires authoritative obstacle geometry")
        (
            origin_x,
            origin_y,
            axis_x,
            axis_y,
            amplitude,
            period,
            phase,
            half_x,
            half_y,
            center_x,
            center_y,
            velocity_x,
            velocity_y,
        ) = self.timed_gate_contract
        geometry = problem.geometry
        frozen = np.asarray(
            [
                geometry.gate_x_cm,
                geometry.gate_y_origin_cm,
                0.0,
                1.0,
                geometry.gate_amplitude_cm,
                geometry.gate_period_s,
                geometry.gate_phase_offset_rad,
                geometry.gate_half_extent_x_cm,
                geometry.gate_half_extent_y_cm,
            ],
            dtype=np.float64,
        )
        observed = np.asarray(
            [origin_x, origin_y, axis_x, axis_y, amplitude, period, phase, half_x, half_y],
            dtype=np.float64,
        )
        if not np.allclose(observed, frozen, rtol=0.0, atol=1.0e-6):
            raise ValueError("authoritative obstacle geometry differs from planner geometry")
        omega = 2.0 * np.pi / period
        angle = phase + omega * self.scenario_time_s
        expected_state = np.asarray(
            [
                origin_x,
                origin_y + amplitude * np.sin(angle),
                0.0,
                amplitude * omega * np.cos(angle),
            ],
            dtype=np.float64,
        )
        observed_state = np.asarray(
            [center_x, center_y, velocity_x, velocity_y], dtype=np.float64
        )
        if not np.allclose(observed_state, expected_state, rtol=0.0, atol=1.0e-3):
            raise ValueError("authoritative obstacle state differs from its analytic schedule")
        weights = problem.weights
        if weights.collision <= 0.0 or weights.clearance_per_cm2 <= 0.0:
            raise ValueError("moving-obstacle MPC requires positive obstacle costs")
        if weights.action_second_difference_per_cm2_s2 != 0.0:
            raise ValueError(
                "stateless moving-obstacle MPC requires zero action-second-difference weight"
            )
        return PlannerQuery(
            snapshot=self.snapshot,
            scenario_time_s=self.scenario_time_s,
            previous_action_local_cm_s=self.previous_action_local_cm_s,
            previous_previous_action_local_cm_s=_ZERO_ACTION,
        )


def planner_snapshot_from_observation(observation: object) -> LivePlannerSnapshot:
    """Strictly convert one observation without requiring stream contiguity.

    This stateless seam is intended for branch visualization, which consumes the
    authoritative dynamics snapshot but not the MPC action-change history.  A
    mid-episode result is explicitly barred from ``to_planner_query`` because its
    second action-history slot cannot be recovered from one packet.
    """

    validated = validate_observation_mapping(observation)
    observation_sequence = int(validated["identity"]["observation_sequence"])
    previous_action, _ = _previous_action(validated, observation_sequence)
    return _snapshot_from_validated(
        validated,
        previous_action=previous_action,
        previous_previous_action=_ZERO_ACTION,
        has_contiguous_action_history=observation_sequence == 0,
    )


class LivePlannerSnapshotAdapter:
    """Admit contiguous observations and clear cached history at episode boundaries.

    A standalone observation contains only the action applied immediately before it.
    The second history slot required by the planning cost is therefore recoverable only
    from a contiguous stream beginning at observation zero. The adapter fails closed
    instead of inventing that missing causal context.
    """

    def __init__(self) -> None:
        self._last_episode_id: int | None = None
        self._last_observation_sequence: int | None = None
        self._last_state_sample_sequence: int | None = None
        self._last_simulation_time_s: float | None = None
        self._last_previous_action: tuple[float, float] | None = None
        self._last_applied_action_source: int | None = None
        self._last_applied_action: tuple[float, float] | None = None

    def adapt(self, observation: object) -> LivePlannerSnapshot:
        """Validate and convert one observation without mutating state on rejection."""

        validated = validate_observation_mapping(observation)
        identity = validated["identity"]
        episode_id = int(identity["episode_id"])
        observation_sequence = int(identity["observation_sequence"])
        state_sample_sequence = int(identity["state_sample_sequence"])
        simulation_time_s = float(validated["timing"]["simulation_time_s"])
        same_episode = episode_id == self._last_episode_id

        if not same_episode:
            if self._last_episode_id is not None and episode_id <= self._last_episode_id:
                raise ValueError("live episode identity must increase across resets")
            if observation_sequence != 0:
                raise ValueError("a new live episode must begin at observation sequence zero")
            previous_previous_action = _ZERO_ACTION
        else:
            assert self._last_observation_sequence is not None
            assert self._last_state_sample_sequence is not None
            assert self._last_simulation_time_s is not None
            if observation_sequence != self._last_observation_sequence + 1:
                raise ValueError("live observations must be contiguous within an episode")
            if state_sample_sequence <= self._last_state_sample_sequence:
                raise ValueError("authoritative state sample sequence must increase")
            if simulation_time_s <= self._last_simulation_time_s:
                raise ValueError("simulation time must strictly increase within an episode")
            previous_previous_action = self._last_previous_action or _ZERO_ACTION

        previous_action, applied_action_source = _previous_action(validated, observation_sequence)
        if same_episode and applied_action_source is not None:
            if (
                self._last_applied_action_source is not None
                and applied_action_source < self._last_applied_action_source
            ):
                raise ValueError("applied action source must not regress within an episode")
            if (
                applied_action_source == self._last_applied_action_source
                and previous_action != self._last_applied_action
            ):
                raise ValueError("a repeated applied action source must retain its value")

        result = _snapshot_from_validated(
            validated,
            previous_action=previous_action,
            previous_previous_action=previous_previous_action,
            has_contiguous_action_history=True,
        )

        self._last_episode_id = episode_id
        self._last_observation_sequence = observation_sequence
        self._last_state_sample_sequence = state_sample_sequence
        self._last_simulation_time_s = simulation_time_s
        self._last_previous_action = previous_action
        self._last_applied_action_source = applied_action_source
        self._last_applied_action = previous_action if applied_action_source is not None else None
        return result

    def reset(self) -> None:
        """Forget local stream state, requiring the next observation to be sequence zero."""

        self._last_episode_id = None
        self._last_observation_sequence = None
        self._last_state_sample_sequence = None
        self._last_simulation_time_s = None
        self._last_previous_action = None
        self._last_applied_action_source = None
        self._last_applied_action = None



def _previous_action(
    validated: dict[str, Any], observation_sequence: int
) -> tuple[tuple[float, float], int | None]:
    previous = validated["previous_action"]
    if not previous["is_present"]:
        return _ZERO_ACTION, None
    source_sequence = int(previous["source_observation_sequence"])
    if source_sequence > observation_sequence - 1:
        raise ValueError("previous action source is newer than the preceding observation")
    values = previous["applied_local_velocity_cm_per_s"]
    return (float(values[0]), float(values[1])), source_sequence


def _snapshot_from_validated(
    validated: dict[str, Any],
    *,
    previous_action: tuple[float, float],
    previous_previous_action: tuple[float, float],
    has_contiguous_action_history: bool,
) -> LivePlannerSnapshot:
    source = validated["source"]
    nominal = validated["nominal_context"]
    if source["movement_mode"] != _SMOOTH_WALKING_MODE:
        raise ValueError("live planner supports only the Walking movement mode")
    if nominal["movement_mode_class"] != _SMOOTH_WALKING_CLASS:
        raise ValueError("live planner requires the Smooth Walking movement-mode class")

    state = validated["state"]
    yaw = YawRadians.from_degrees(float(state["facing_yaw_deg"]))
    derived_local_velocity = world_vector_to_local(
        np.asarray(state["velocity_world_cm_per_s"], dtype=np.float64)[:2], yaw=yaw
    )
    transmitted_local_velocity = np.asarray(
        state["velocity_local_planar_cm_per_s"], dtype=np.float64
    )
    if not np.allclose(
        derived_local_velocity, transmitted_local_velocity, rtol=0.0, atol=1.0e-4
    ):
        raise ValueError("authoritative world and local velocities disagree")

    identity = validated["identity"]
    planner_context = validated["planner_context"]
    target = planner_context["target"]
    target_world_xy_cm = (
        (float(target["position_world_cm"][0]), float(target["position_world_cm"][1]))
        if target["is_present"]
        else None
    )
    timed_gate = planner_context["timed_gate"]
    # Gate-free planning has no shared scenario clock. Zero is deterministic because
    # no time-varying gate cost consumes it in that case.
    scenario_time_s = (
        float(timed_gate["scenario_time_s"]) if timed_gate["is_present"] else 0.0
    )
    timed_gate_contract = None
    if timed_gate["is_present"]:
        timed_gate_contract = (
            float(timed_gate["origin_world_cm"][0]),
            float(timed_gate["origin_world_cm"][1]),
            float(timed_gate["motion_axis_world"][0]),
            float(timed_gate["motion_axis_world"][1]),
            float(timed_gate["amplitude_cm"]),
            float(timed_gate["period_s"]),
            float(timed_gate["phase_offset_rad"]),
            float(timed_gate["half_extents_cm"][0]),
            float(timed_gate["half_extents_cm"][1]),
            float(timed_gate["center_world_cm"][0]),
            float(timed_gate["center_world_cm"][1]),
            float(timed_gate["velocity_world_cm_per_s"][0]),
            float(timed_gate["velocity_world_cm_per_s"][1]),
        )
    parameters = dict(nominal["parameters"])
    parameters["turning_strength"] = parameters.pop("turning_strength_per_s")
    preparation = nominal["input_preparation"]
    snapshot = PlannerSnapshot(
        observable=SmoothWalkingObservableState(
            position_world_cm=np.asarray(state["position_world_cm"], dtype=np.float64),
            velocity_world_cm_s=np.asarray(state["velocity_world_cm_per_s"], dtype=np.float64),
            facing_yaw_rad=yaw.value,
            angular_velocity_yaw_deg_s=float(state["angular_velocity_world_deg_per_s"][2]),
            simulation_time_s=float(validated["timing"]["simulation_time_s"]),
        ),
        internal=internal_from_context_record(nominal),
        parameters=smooth_walking_parameters_from_record(parameters),
        effective_max_speed_cm_s=float(preparation["effective_max_speed_cm_per_s"]),
    )
    return LivePlannerSnapshot(
        snapshot=snapshot,
        episode_id=int(identity["episode_id"]),
        observation_sequence=int(identity["observation_sequence"]),
        state_sample_sequence=int(identity["state_sample_sequence"]),
        previous_action_local_cm_s=previous_action,
        previous_previous_action_local_cm_s=previous_previous_action,
        target_world_xy_cm=target_world_xy_cm,
        scenario_time_s=scenario_time_s,
        timed_gate_is_present=bool(timed_gate["is_present"]),
        timed_gate_contract=timed_gate_contract,
        has_contiguous_action_history=has_contiguous_action_history,
    )
