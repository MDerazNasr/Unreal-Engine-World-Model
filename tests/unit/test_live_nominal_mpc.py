from __future__ import annotations

import threading
from dataclasses import replace

import numpy as np
import pytest

from motionworld.control.live_nominal_mpc import (
    LiveNominalMPCConfig,
    LiveNominalMPCController,
)
from motionworld.planning.cem import CEMConfig, expand_action_knots, sample_standard_normal_schedule
from motionworld.planning.mpc import plan_model
from motionworld.planning.planner_rollout import PlannerRolloutConfig
from motionworld.planning.vectorized_rollout import rollout_action_candidates_vectorized
from motionworld.protocol import encode_action_json, validate_action_mapping
from tests.unit.test_live_planner_adapter import _observation
from tests.unit.test_mpc import _problem


def _demo_problem():
    base = _problem()
    return replace(
        base,
        cem=CEMConfig(
            num_candidates=16,
            num_elites=4,
            num_iterations=3,
            num_knots=5,
            num_plan_steps=15,
            max_action_speed_cm_s=165.0,
            initial_std_cm_s=40.0,
            minimum_std_cm_s=2.0,
        ),
        rollout=PlannerRolloutConfig(plan_step_s=0.1, dynamics_substeps_per_plan_step=1),
        weights=replace(
            base.weights,
            collision=0.0,
            clearance_per_cm2=0.0,
            action_second_difference_per_cm2_s2=0.0,
        ),
    )


def test_live_nominal_mpc_emits_first_action_and_genuine_iteration_paths() -> None:
    config = LiveNominalMPCConfig(_demo_problem(), seed=17)
    controller = LiveNominalMPCController(config)
    observation = _observation(9)
    observation["source"]["controller_mode"] = "nominal_mpc"

    first = controller(observation, threading.Event())
    second = controller(observation, threading.Event())

    assert first is not None and second is not None
    validated = validate_action_mapping(first)
    assert validated["command"] == second["command"]
    assert validated["fallback"] == {"is_safe_fallback": False, "reason": "none"}
    assert validated["controller"]["controller_id"] == "nominal_mpc"
    visualization = validated["telemetry"]["visualization"]
    assert [path["role"] for path in visualization["paths"]] == [
        "cem_candidate",
        "cem_candidate",
        "cem_candidate",
        "selected",
    ]
    assert all(
        path["points_world_xy_cm"][0] == observation["state"]["position_world_cm"][:2]
        for path in visualization["paths"]
    )
    assert len(encode_action_json(validated)) <= 8_192

    from motionworld.control.live_planner_adapter import planner_snapshot_from_observation

    live = planner_snapshot_from_observation(observation)
    problem = replace(config.problem_template, goal_world_cm=live.target_world_xy_cm)
    query = replace(
        live.to_stateless_mpc_query(problem),
        initial_mean_knots_local_cm_s=np.tile([130.0, 0.0], (5, 1)),
    )
    plan = plan_model(
        problem,
        query,
        standard_normal_noise=sample_standard_normal_schedule(problem.cem, seed=17),
        model_name="nominal",
    )
    np.testing.assert_array_equal(
        validated["command"]["desired_velocity_local_cm_per_s"],
        plan.cem.first_action_cm_s,
    )
    iteration_actions = np.stack(
        [
            expand_action_knots(
                iteration.best_knots_cm_s,
                num_plan_steps=problem.cem.num_plan_steps,
            )
            for iteration in plan.cem.iterations
        ]
    )
    rerolled = rollout_action_candidates_vectorized(
        live.snapshot,
        iteration_actions,
        config=problem.rollout,
    )
    for index in range(3):
        np.testing.assert_array_equal(
            visualization["paths"][index]["points_world_xy_cm"][1:],
            rerolled.positions_world_cm[index],
        )
    np.testing.assert_array_equal(
        visualization["paths"][3]["points_world_xy_cm"][1:],
        plan.best_rollout.positions_world_cm[0],
    )


def test_live_nominal_mpc_cancels_after_planning(monkeypatch) -> None:
    from motionworld.control import live_nominal_mpc

    cancelled = threading.Event()
    real_plan = live_nominal_mpc.plan_model

    def plan_then_cancel(*args, **kwargs):
        result = real_plan(*args, **kwargs)
        cancelled.set()
        return result

    monkeypatch.setattr(live_nominal_mpc, "plan_model", plan_then_cancel)
    observation = _observation(4)
    observation["source"]["controller_mode"] = "nominal_mpc"
    controller = LiveNominalMPCController(LiveNominalMPCConfig(_demo_problem(), seed=2))

    assert controller(observation, cancelled) is None


def test_live_nominal_mpc_cancels_after_visualization(monkeypatch) -> None:
    from motionworld.control import live_nominal_mpc

    cancelled = threading.Event()
    real_visualization = live_nominal_mpc._visualization

    def visualize_then_cancel(*args, **kwargs):
        result = real_visualization(*args, **kwargs)
        cancelled.set()
        return result

    monkeypatch.setattr(live_nominal_mpc, "_visualization", visualize_then_cancel)
    observation = _observation(4)
    observation["source"]["controller_mode"] = "nominal_mpc"
    controller = LiveNominalMPCController(LiveNominalMPCConfig(_demo_problem(), seed=2))

    assert controller(observation, cancelled) is None


def test_live_nominal_mpc_suppresses_fallback_when_exception_coincides_with_cancel(
    monkeypatch,
) -> None:
    from motionworld.control import live_nominal_mpc

    cancelled = threading.Event()

    def cancel_then_fail(*_args, **_kwargs):
        cancelled.set()
        raise RuntimeError("cancelled planner failed")

    monkeypatch.setattr(live_nominal_mpc, "plan_model", cancel_then_fail)
    observation = _observation(4)
    observation["source"]["controller_mode"] = "nominal_mpc"
    controller = LiveNominalMPCController(LiveNominalMPCConfig(_demo_problem(), seed=2))

    assert controller(observation, cancelled) is None


def test_live_nominal_mpc_supplies_fixed_noise_and_five_knot_initial_mean(
    monkeypatch,
) -> None:
    from motionworld.control import live_nominal_mpc

    captured = {}
    real_plan = live_nominal_mpc.plan_model

    def capture(problem, query, **kwargs):
        captured["query"] = query
        captured["noise"] = kwargs["standard_normal_noise"].copy()
        return real_plan(problem, query, **kwargs)

    monkeypatch.setattr(live_nominal_mpc, "plan_model", capture)
    config = LiveNominalMPCConfig(_demo_problem(), seed=31)
    observation = _observation(6)
    observation["source"]["controller_mode"] = "nominal_mpc"

    assert LiveNominalMPCController(config)(observation, threading.Event()) is not None
    np.testing.assert_array_equal(
        captured["query"].initial_mean_knots_local_cm_s,
        np.tile([130.0, 0.0], (5, 1)),
    )
    np.testing.assert_array_equal(
        captured["noise"],
        live_nominal_mpc.sample_standard_normal_schedule(config.problem_template.cem, seed=31),
    )


def test_live_nominal_mpc_returns_safe_zero_on_planner_error(monkeypatch) -> None:
    from motionworld.control import live_nominal_mpc

    def fail(*_args, **_kwargs):
        raise RuntimeError("planner failed")

    monkeypatch.setattr(live_nominal_mpc, "plan_model", fail)
    observation = _observation(2)
    observation["source"]["controller_mode"] = "nominal_mpc"
    action = LiveNominalMPCController(LiveNominalMPCConfig(_demo_problem(), seed=2))(
        observation, threading.Event()
    )

    assert action is not None
    assert validate_action_mapping(action)["fallback"] == {
        "is_safe_fallback": True,
        "reason": "planner_error",
    }
    assert action["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]


@pytest.mark.parametrize(
    "changes",
    [
        {"seed": -1},
        {"preview_iteration_winners": 0},
        {"initial_mean_action_local_cm_s": (200.0, 0.0)},
    ],
)
def test_live_nominal_mpc_config_rejects_invalid_fixed_inputs(changes) -> None:
    values = {"problem_template": _demo_problem(), "seed": 1, **changes}
    with pytest.raises(ValueError):
        LiveNominalMPCConfig(**values)
