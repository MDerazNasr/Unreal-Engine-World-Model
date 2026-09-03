from __future__ import annotations

import copy
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from motionworld.control.config import ControllerConfig, load_control_service_config
from motionworld.control.controllers import EchoController, ReactiveController, build_controller
from motionworld.protocol import decode_observation_json, validate_action_mapping

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


def test_factory_rejects_mpc_modes_until_their_stateful_runtime_gate() -> None:
    assert isinstance(build_controller("echo", _config()), EchoController)
    assert isinstance(build_controller("reactive", _config()), ReactiveController)
    with pytest.raises(ValueError, match="not implemented"):
        build_controller("nominal_mpc", _config())


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
