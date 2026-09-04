from __future__ import annotations

import copy
import json
import select
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from motionworld.control.config import ControlServiceConfig, load_control_service_config
from motionworld.control.controllers import BranchPreviewController
from motionworld.control.live_mpc_config import load_live_nominal_mpc_config
from motionworld.control.live_nominal_mpc import LiveNominalMPCController
from motionworld.control.service import ControlService, safe_zero_planner
from motionworld.protocol import (
    UdpEndpoint,
    decode_action_json,
    decode_observation_json,
    encode_observation_json,
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


def _endpoint() -> UdpEndpoint:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        host, port = probe.getsockname()
        return UdpEndpoint(host, port)
    finally:
        probe.close()


def _config(*, mode: str = "nominal_mpc") -> ControlServiceConfig:
    config = load_control_service_config(SERVICE_CONFIG_PATH)
    transport = replace(
        config.transport,
        unreal_endpoint=_endpoint(),
        python_endpoint=_endpoint(),
    )
    return replace(
        config,
        transport=transport,
        controller_mode=mode,
        planner_shutdown_timeout_ms=250,
    )


def _observation(
    sequence: int = 1,
    *,
    episode: int = 7101,
    mode: str = "nominal_mpc",
) -> bytes:
    value = decode_observation_json(OBSERVATION_FIXTURE.read_bytes().removesuffix(b"\n"))
    value["identity"]["episode_id"] = episode
    value["identity"]["observation_sequence"] = sequence
    value["source"]["controller_mode"] = mode
    value["scenario"]["scenario_seed"] = episode
    value["scenario"]["reset_id"] = f"timed_gate:{episode}:attempt0"
    if sequence == 0:
        value["previous_action"] = {"is_present": False}
    else:
        value["previous_action"]["source_observation_sequence"] = sequence - 1
    return encode_observation_json(value)


def _sender(config: ControlServiceConfig) -> socket.socket:
    result = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    result.bind(
        (config.transport.unreal_endpoint.host, config.transport.unreal_endpoint.port)
    )
    result.setblocking(False)
    return result


def _send_observation(
    sender: socket.socket,
    config: ControlServiceConfig,
    payload: bytes,
) -> None:
    sender.sendto(
        payload,
        (config.transport.python_endpoint.host, config.transport.python_endpoint.port),
    )


def _pump_until(service: ControlService, predicate, timeout_s: float = 1.0):
    deadline = time.monotonic() + timeout_s
    snapshot = service.snapshot()
    while time.monotonic() < deadline:
        snapshot = service.poll_once()
        if predicate(snapshot):
            return snapshot
        time.sleep(0.002)
    pytest.fail(f"service condition was not reached; final snapshot={snapshot}")


def _copy_config_tree(tmp_path: Path) -> Path:
    for name in ("control_service.yaml", "control_transport.yaml", "control_runtime.yaml"):
        shutil.copyfile(REPOSITORY_ROOT / "configs" / name, tmp_path / name)
    return tmp_path / "control_service.yaml"


def test_service_config_loads_relative_frozen_contracts() -> None:
    config = load_control_service_config(SERVICE_CONFIG_PATH)
    assert config.controller_mode == "echo"
    assert config.transport.python_endpoint == UdpEndpoint("127.0.0.1", 52581)
    assert config.runtime.decision_interval_ms == 100
    assert config.controller.max_command_speed_cm_per_s == 600.0
    assert config.controller.echo_velocity_local_cm_per_s == (0.0, 0.0)
    assert config.controller.reactive_cruise_speed_cm_per_s == 160.0
    assert config.controller.reactive_arrival_radius_cm == 25.0
    assert config.poll_interval_ms == 5
    assert config.max_tracked_episodes == 16


def test_demo_branch_preview_config_is_strict_and_zero_commanded() -> None:
    config = load_control_service_config(
        REPOSITORY_ROOT / "configs" / "control_service_demo_branches.yaml"
    )
    assert config.controller_mode == "branch_preview"
    assert config.controller.echo_velocity_local_cm_per_s == (0.0, 0.0)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "motionworld.control.service",
            "--config",
            str(REPOSITORY_ROOT / "configs" / "control_service_demo_branches.yaml"),
            "--check-config",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert json.loads(completed.stdout)["controller_mode"] == "branch_preview"


def test_demo_nominal_mpc_cli_requires_and_loads_frozen_planner_config() -> None:
    service_path = REPOSITORY_ROOT / "configs/control_service_demo_nominal_mpc.yaml"
    planner_path = REPOSITORY_ROOT / "configs/live_nominal_mpc_demo.yaml"
    config = load_control_service_config(service_path)
    assert config.controller_mode == "nominal_mpc"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "motionworld.control.service",
            "--config",
            str(service_path),
            "--planner-config",
            str(planner_path),
            "--check-config",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert json.loads(completed.stdout)["controller_mode"] == "nominal_mpc"

    missing = subprocess.run(
        [
            sys.executable,
            "-m",
            "motionworld.control.service",
            "--config",
            str(service_path),
            "--check-config",
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert missing.returncode != 0
    assert "requires --planner-config" in missing.stderr


@pytest.mark.parametrize(
    ("name", "expected_velocity"),
    [
        ("control_service_echo_forward.yaml", (100.0, 0.0)),
        ("control_service_echo_right.yaml", (0.0, 100.0)),
        ("control_service_echo_diagonal.yaml", (100.0, 100.0)),
        ("control_service_echo_reverse.yaml", (-100.0, 0.0)),
        ("control_service_echo_speed_bound.yaml", (1000.0, 1000.0)),
    ],
)
def test_live_echo_case_configs_are_strict_and_named(
    name: str, expected_velocity: tuple[float, float]
) -> None:
    config = load_control_service_config(REPOSITORY_ROOT / "configs" / name)
    assert config.controller_mode == "echo"
    assert config.controller.echo_velocity_local_cm_per_s == expected_velocity
    assert config.controller.max_command_speed_cm_per_s == 600.0
    assert config.transport.python_endpoint == UdpEndpoint("127.0.0.1", 52581)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw.update(extra=True), "keys must be exactly"),
        (lambda raw: raw.update(schema_version=1), "unsupported service schema version"),
        (lambda raw: raw.update(controller_mode="unsafe"), "unsupported"),
        (lambda raw: raw.update(transport_config="/tmp/transport.yaml"), "relative path"),
        (lambda raw: raw.update(runtime_config="../runtime.yaml"), "stay inside"),
        (
            lambda raw: raw["diagnostics"].update(max_recent_rejections=0),
            "integer in",
        ),
    ],
)
def test_service_config_rejects_schema_and_path_drift(
    tmp_path: Path, mutation, message: str
) -> None:
    path = _copy_config_tree(tmp_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutation(raw)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_control_service_config(path)


def test_start_exposes_health_and_close_releases_configured_socket() -> None:
    config = _config()
    service = ControlService(config, lambda _observation, _cancelled: None)
    service.start()
    running = service.snapshot()
    assert running.health == "running"
    assert running.ready
    assert running.controller_mode == "nominal_mpc"
    service.close()
    stopped = service.snapshot()
    assert stopped.health == "stopped"
    assert not stopped.ready

    rebound = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        rebound.bind(
            (config.transport.python_endpoint.host, config.transport.python_endpoint.port)
        )
    finally:
        rebound.close()


def test_close_cancels_active_planning_before_releasing_socket() -> None:
    config = _config()
    started = threading.Event()
    cancellation_observed = threading.Event()

    def planner(_observation, cancelled: threading.Event):
        started.set()
        if cancelled.wait(1.0):
            cancellation_observed.set()

    service = ControlService(config, planner)
    sender = _sender(config)
    try:
        service.start()
        _send_observation(sender, config, _observation())
        _pump_until(service, lambda state: state.observations_dispatched == 1)
        assert started.wait(1.0)
        service.close()
        assert cancellation_observed.is_set()
        assert service.snapshot().health == "stopped"
    finally:
        service.close()
        sender.close()

    rebound = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        rebound.bind(
            (config.transport.python_endpoint.host, config.transport.python_endpoint.port)
        )
    finally:
        rebound.close()


def test_every_observation_is_validated_before_dispatch_and_diagnostics_are_bounded() -> None:
    config = replace(_config(), max_error_utf8_bytes=12, max_recent_rejections=2)
    dispatched: list[dict[str, object]] = []
    service = ControlService(
        config,
        lambda observation, _cancelled: dispatched.append(copy.deepcopy(observation)),
    )
    sender = _sender(config)
    try:
        service.start()
        _send_observation(
            sender,
            config,
            b'{"SECRET_CHECKPOINT_PAYLOAD_MUST_NOT_ESCAPE":',
        )
        _send_observation(sender, config, _observation())
        snapshot = _pump_until(service, lambda _state: len(dispatched) == 1)
        assert snapshot.datagrams_received == 2
        assert snapshot.malformed_observations == 1
        assert snapshot.observations_validated == 1
        assert len(dispatched) == 1
        assert all(len(reason.encode("utf-8")) <= 12 for reason in snapshot.recent_rejections)
        assert "SECRET" not in repr(snapshot.recent_rejections)
    finally:
        service.close()
        sender.close()


def test_identity_state_rejects_duplicate_and_old_episode_packets() -> None:
    config = _config()
    service = ControlService(config, lambda _observation, _cancelled: None)
    sender = _sender(config)
    try:
        service.start()
        _send_observation(sender, config, _observation(sequence=1, episode=7101))
        _send_observation(sender, config, _observation(sequence=1, episode=7101))
        _send_observation(sender, config, _observation(sequence=0, episode=7102))
        _send_observation(sender, config, _observation(sequence=2, episode=7101))
        snapshot = _pump_until(service, lambda state: state.datagrams_received == 4)
        assert snapshot.observations_validated == 4
        assert snapshot.observations_dispatched == 2
        assert snapshot.rejected_observations == 2
        assert snapshot.current_episode_id == 7102
        assert snapshot.current_observation_sequence == 0
        assert snapshot.tracked_episode_count == 2
        assert snapshot.recent_rejections == (
            "duplicate_or_stale_observation",
            "noncurrent_episode",
        )
    finally:
        service.close()
        sender.close()


def test_episode_identity_state_has_a_fixed_memory_bound() -> None:
    config = replace(_config(), max_tracked_episodes=2)
    service = ControlService(config, lambda _observation, _cancelled: None)
    sender = _sender(config)
    try:
        service.start()
        for episode in (7101, 7102, 7103):
            _send_observation(sender, config, _observation(sequence=0, episode=episode))
        snapshot = _pump_until(service, lambda state: state.datagrams_received == 3)
        assert snapshot.observations_dispatched == 3
        assert snapshot.tracked_episode_count == 2
        assert snapshot.current_episode_id == 7103
        assert snapshot.current_observation_sequence == 0
    finally:
        service.close()
        sender.close()


def test_newer_observation_cancels_old_plan_and_only_new_action_is_sent() -> None:
    config = _config()
    first_started = threading.Event()
    first_cancelled = threading.Event()
    second_started = threading.Event()

    def planner(observation: dict[str, object], cancelled: threading.Event):
        sequence = observation["identity"]["observation_sequence"]
        if sequence == 1:
            first_started.set()
            if cancelled.wait(1.0):
                first_cancelled.set()
            return safe_zero_planner(observation, cancelled)
        second_started.set()
        return safe_zero_planner(observation, cancelled)

    service = ControlService(config, planner)
    sender = _sender(config)
    try:
        service.start()
        _send_observation(sender, config, _observation(sequence=1))
        _pump_until(service, lambda state: state.observations_dispatched == 1)
        assert first_started.wait(1.0)

        _send_observation(sender, config, _observation(sequence=2))
        snapshot = _pump_until(service, lambda state: state.observations_dispatched == 2)
        assert first_cancelled.wait(1.0)
        assert second_started.wait(1.0)
        snapshot = _pump_until(service, lambda state: state.actions_sent == 1)
        assert snapshot.superseded_plans >= 1
        assert select.select([sender], [], [], 1.0)[0]
        payload, _ = sender.recvfrom(config.transport.max_action_datagram_bytes)
        action = decode_action_json(payload)
        assert action["identity"] == {
            "episode_id": 7101,
            "source_observation_sequence": 2,
        }
        with pytest.raises(BlockingIOError):
            sender.recvfrom(config.transport.max_action_datagram_bytes)
    finally:
        service.close()
        sender.close()


def test_real_branch_preview_service_publishes_only_latest_zero_action() -> None:
    config = _config(mode="branch_preview")
    service = ControlService(config, BranchPreviewController(config.controller))
    sender = _sender(config)
    try:
        service.start()
        _send_observation(sender, config, _observation(sequence=1, mode="branch_preview"))
        _send_observation(sender, config, _observation(sequence=2, mode="branch_preview"))
        snapshot = _pump_until(service, lambda state: state.actions_sent == 1)
        assert snapshot.superseded_plans >= 1
        assert select.select([sender], [], [], 1.0)[0]
        payload, _ = sender.recvfrom(config.transport.max_action_datagram_bytes)
        action = decode_action_json(payload)
        assert action["identity"] == {
            "episode_id": 7101,
            "source_observation_sequence": 2,
        }
        assert action["command"]["desired_velocity_local_cm_per_s"] == [0.0, 0.0]
        assert action["controller"]["controller_id"] == "branch_preview"
        assert action["telemetry"]["is_present"] is True
        with pytest.raises(BlockingIOError):
            sender.recvfrom(config.transport.max_action_datagram_bytes)
    finally:
        service.close()
        sender.close()


def test_real_nominal_mpc_service_publishes_only_latest_first_action() -> None:
    config = _config(mode="nominal_mpc")
    planner_config = load_live_nominal_mpc_config(
        REPOSITORY_ROOT / "configs/live_nominal_mpc_demo.yaml",
        REPOSITORY_ROOT,
    )
    service = ControlService(config, LiveNominalMPCController(planner_config))
    sender = _sender(config)
    try:
        service.start()
        _send_observation(sender, config, _observation(sequence=1))
        _send_observation(sender, config, _observation(sequence=2))
        snapshot = _pump_until(service, lambda state: state.actions_sent == 1, timeout_s=3.0)
        assert snapshot.superseded_plans >= 1
        assert select.select([sender], [], [], 1.0)[0]
        payload, _ = sender.recvfrom(config.transport.max_action_datagram_bytes)
        action = decode_action_json(payload)
        assert action["identity"] == {
            "episode_id": 7101,
            "source_observation_sequence": 2,
        }
        assert action["controller"]["controller_id"] == "nominal_mpc"
        assert action["command"]["desired_velocity_local_cm_per_s"] != [0.0, 0.0]
        assert [path["role"] for path in action["telemetry"]["visualization"]["paths"]] == [
            "cem_candidate",
            "cem_candidate",
            "selected",
        ]
        with pytest.raises(BlockingIOError):
            sender.recvfrom(config.transport.max_action_datagram_bytes)
    finally:
        service.close()
        sender.close()


def test_service_rejects_planner_action_from_wrong_controller() -> None:
    config = _config(mode="branch_preview")

    def wrong_controller(observation, cancelled):
        action = safe_zero_planner(observation, cancelled)
        assert action is not None
        action["controller"]["controller_id"] = "echo"
        return action

    service = ControlService(config, wrong_controller)
    sender = _sender(config)
    try:
        service.start()
        _send_observation(sender, config, _observation(mode="branch_preview"))
        snapshot = _pump_until(service, lambda state: state.send_errors == 1)
        assert snapshot.actions_sent == 0
        assert snapshot.recent_rejections == ("action_rejected:ValueError",)
        with pytest.raises(BlockingIOError):
            sender.recvfrom(config.transport.max_action_datagram_bytes)
    finally:
        service.close()
        sender.close()


def test_controller_mode_mismatch_is_not_dispatched() -> None:
    config = _config(mode="echo")
    called = False

    def planner(_observation, _cancelled):
        nonlocal called
        called = True

    service = ControlService(config, planner)
    sender = _sender(config)
    try:
        service.start()
        _send_observation(sender, config, _observation(mode="nominal_mpc"))
        snapshot = _pump_until(service, lambda state: state.datagrams_received == 1)
        assert not called
        assert snapshot.observations_validated == 1
        assert snapshot.rejected_observations == 1
        assert snapshot.recent_rejections == ("controller_mode_mismatch",)
    finally:
        service.close()
        sender.close()


def test_clean_process_entry_point_loads_without_notebook_state() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "motionworld.control.service",
            "--config",
            str(SERVICE_CONFIG_PATH),
            "--check-config",
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10.0,
    )
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "controller_mode": "echo",
        "python_endpoint": {"host": "127.0.0.1", "port": 52581},
        "status": "config_valid",
    }
