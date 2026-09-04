from __future__ import annotations

import copy
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from motionworld.control.config import ControllerConfig, load_control_service_config
from motionworld.control.controllers import (
    BranchPreviewController,
    EchoController,
    ReactiveController,
    build_controller,
)
from motionworld.control.live_mpc_config import load_live_nominal_mpc_config
from motionworld.control.live_nominal_mpc import LiveNominalMPCController
from motionworld.protocol import (
    MAX_ACTION_BYTES,
    decode_observation_json,
    encode_action_json,
    validate_action_mapping,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SERVICE_CONFIG_PATH = REPOSITORY_ROOT / "configs" / "control_service.yaml"
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


def _config(**changes: object) -> ControllerConfig:
    base = load_control_service_config(SERVICE_CONFIG_PATH).controller
    return replace(base, **changes)


def _observation(*, mode: str = "echo") -> dict[str, object]:
    result = decode_observation_json(OBSERVATION_FIXTURE.read_bytes().rstrip(b"\n"))
    result["source"]["controller_mode"] = mode
    return result


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ((0.0, 0.0), [0.0, 0.0]),
        ((160.0, 0.0), [160.0, 0.0]),
        ((0.0, 160.0), [0.0, 160.0]),
        ((120.0, 120.0), pytest.approx([116.6726189, 116.6726189])),
        ((-160.0, 0.0), [-160.0, 0.0]),
        ((300.0, 400.0), pytest.approx([99.0, 132.0])),
    ],
)
def test_echo_covers_direction_cases_and_clamps_to_observed_speed(
    requested: tuple[float, float], expected: object
) -> None:
    observation = _observation()
    action = EchoController(_config(echo_velocity_local_cm_per_s=requested))(
        observation, threading.Event()
    )
    assert action is not None
    validated = validate_action_mapping(action)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == expected
    assert validated["identity"] == {
        "episode_id": 7101,
        "source_observation_sequence": 1,
    }
    assert validated["fallback"] == {"is_safe_fallback": False, "reason": "none"}


def test_echo_uses_the_lower_configured_speed_limit() -> None:
    action = EchoController(
        _config(
            max_command_speed_cm_per_s=100.0,
            echo_velocity_local_cm_per_s=(300.0, 400.0),
        )
    )(_observation(), threading.Event())
    assert action is not None
    assert action["command"]["desired_velocity_local_cm_per_s"] == pytest.approx(
        [60.0, 80.0]
    )


def test_echo_honors_cancellation_without_an_action() -> None:
    cancelled = threading.Event()
    cancelled.set()
    assert EchoController(_config())(_observation(), cancelled) is None


@pytest.mark.parametrize(
    ("facing", "target_xy", "expected_local"),
    [
        ([1.0, 0.0], [110.0, 20.0], [160.0, 0.0]),
        ([1.0, 0.0], [10.0, 120.0], [0.0, 160.0]),
        ([0.0, 1.0], [110.0, 20.0], [0.0, -160.0]),
        ([0.0, 1.0], [10.0, 120.0], [160.0, 0.0]),
    ],
)
def test_reactive_maps_world_target_through_authoritative_facing(
    facing: list[float], target_xy: list[float], expected_local: list[float]
) -> None:
    observation = _observation(mode="reactive")
    observation["state"]["facing_unit_world"] = facing
    observation["state"]["facing_yaw_deg"] = 0.0 if facing == [1.0, 0.0] else 90.0
    observation["planner_context"]["target"]["position_world_cm"][:2] = target_xy
    action = ReactiveController(_config())(observation, threading.Event())
    assert action is not None
    validated = validate_action_mapping(action)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == pytest.approx(
        expected_local
    )


def test_reactive_uses_bounded_terminal_velocity_inside_arrival_radius() -> None:
    observation = _observation(mode="reactive")
    observation["planner_context"]["target"]["position_world_cm"] = [15.0, 20.0, 86.0]
    observation["planner_context"]["target"][
        "desired_terminal_velocity_local_cm_per_s"
    ] = [300.0, 400.0]
    action = ReactiveController(_config())(observation, threading.Event())
    assert action is not None
    assert action["command"]["desired_velocity_local_cm_per_s"] == pytest.approx(
        [96.0, 128.0]
    )


def test_reactive_fails_closed_when_target_is_absent() -> None:
    observation = _observation(mode="reactive")
    observation["planner_context"]["target"] = {"is_present": False}
    observation["validity"]["target_present"] = False
    action = ReactiveController(_config())(observation, threading.Event())
    assert action is not None
    validated = validate_action_mapping(action)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
    assert validated["fallback"] == {
        "is_safe_fallback": True,
        "reason": "invalid_observation",
    }


def test_controllers_are_stateless_across_episode_reset() -> None:
    controller = ReactiveController(_config())
    first = _observation(mode="reactive")
    reset = copy.deepcopy(first)
    reset["identity"]["episode_id"] = 7102
    reset["identity"]["observation_sequence"] = 0
    reset["previous_action"] = {"is_present": False}
    reset["planner_context"]["target"]["position_world_cm"] = [-90.0, 20.0, 86.0]
    before = controller(first, threading.Event())
    after = controller(reset, threading.Event())
    assert before is not None and after is not None
    assert before["identity"] == {
        "episode_id": 7101,
        "source_observation_sequence": 1,
    }
    assert after["identity"] == {
        "episode_id": 7102,
        "source_observation_sequence": 0,
    }
    assert after["command"]["desired_velocity_local_cm_per_s"] == [-160.0, 0.0]


def test_factory_requires_explicit_config_for_nominal_mpc() -> None:
    assert isinstance(build_controller("echo", _config()), EchoController)
    assert isinstance(build_controller("reactive", _config()), ReactiveController)
    assert isinstance(build_controller("branch_preview", _config()), BranchPreviewController)
    with pytest.raises(ValueError, match="requires an explicit"):
        build_controller("nominal_mpc", _config())


def test_factory_constructs_only_configured_nominal_mpc() -> None:
    planner = load_live_nominal_mpc_config(
        REPOSITORY_ROOT / "configs/live_nominal_mpc_demo.yaml",
        REPOSITORY_ROOT,
    )

    assert isinstance(
        build_controller("nominal_mpc", _config(), planner),
        LiveNominalMPCController,
    )
    with pytest.raises(ValueError, match="valid only"):
        build_controller("echo", _config(), planner)


def test_branch_preview_holds_execution_and_emits_authentic_identity_bound_branches() -> None:
    observation = _observation(mode="branch_preview")
    action = BranchPreviewController(_config())(observation, threading.Event())
    assert action is not None
    validated = validate_action_mapping(action)
    assert validated["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
    assert validated["controller"] == {
        "controller_id": "branch_preview",
        "model_id": "nominal_branch_preview_v1",
    }
    visualization = validated["telemetry"]["visualization"]
    assert visualization["identity"] == validated["identity"]
    assert [path["role"] for path in visualization["paths"]] == [
        "branch_forward",
        "branch_left",
        "branch_right",
        "branch_stop",
    ]
    starts = [path["points_world_xy_cm"][0] for path in visualization["paths"]]
    assert starts == [observation["state"]["position_world_cm"][:2]] * 4
    endpoints = [path["points_world_xy_cm"][-1] for path in visualization["paths"]]
    assert len({tuple(point) for point in endpoints}) == 4
    assert len(encode_action_json(validated)) <= MAX_ACTION_BYTES


def test_branch_preview_honors_cancellation_before_rollout() -> None:
    cancelled = threading.Event()
    cancelled.set()
    assert BranchPreviewController(_config())(
        _observation(mode="branch_preview"), cancelled
    ) is None


def test_branch_preview_honors_cancellation_after_snapshot_conversion(monkeypatch) -> None:
    cancelled = threading.Event()
    from motionworld.control import controllers

    real_convert = controllers.planner_snapshot_from_observation

    def convert_then_cancel(observation):
        result = real_convert(observation)
        cancelled.set()
        return result

    monkeypatch.setattr(controllers, "planner_snapshot_from_observation", convert_then_cancel)
    assert BranchPreviewController(_config())(
        _observation(mode="branch_preview"), cancelled
    ) is None


def test_branch_preview_honors_cancellation_after_rollout(monkeypatch) -> None:
    cancelled = threading.Event()
    from motionworld.control import controllers

    real_generate = controllers.generate_live_branch_visualization

    def generate_then_cancel(snapshot):
        result = real_generate(snapshot)
        cancelled.set()
        return result

    monkeypatch.setattr(controllers, "generate_live_branch_visualization", generate_then_cancel)
    assert BranchPreviewController(_config())(
        _observation(mode="branch_preview"), cancelled
    ) is None


def test_branch_preview_fails_closed_on_malformed_observation() -> None:
    observation = _observation(mode="branch_preview")
    observation["state"]["position_world_cm"][0] = float("nan")
    with pytest.raises(ValueError):
        BranchPreviewController(_config())(observation, threading.Event())


@pytest.mark.parametrize(
    "changes",
    [
        {"max_command_speed_cm_per_s": float("nan")},
        {"echo_velocity_local_cm_per_s": (float("inf"), 0.0)},
        {"reactive_cruise_speed_cm_per_s": -1.0},
        {"reactive_arrival_radius_cm": 10_001.0},
    ],
)
def test_controller_config_rejects_nonfinite_or_unbounded_values(
    changes: dict[str, object]
) -> None:
    with pytest.raises(ValueError):
        _config(**changes)
