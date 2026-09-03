from __future__ import annotations

import select
import socket
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from motionworld.control.config import load_control_service_config
from motionworld.control.telemetry_saturation_probe import (
    TelemetrySaturationProbe,
    TelemetrySaturationProbeConfig,
)
from motionworld.protocol import (
    MAX_TRAJECTORY_STEPS,
    UdpEndpoint,
    decode_action_json,
    decode_observation_json,
    encode_observation_json,
    validate_action_for_observation,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SERVICE_CONFIG_PATH = REPOSITORY_ROOT / "configs" / "control_service_echo_forward.yaml"
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


def _service_config():
    config = load_control_service_config(SERVICE_CONFIG_PATH)
    return replace(
        config,
        transport=replace(
            config.transport,
            unreal_endpoint=_endpoint(),
            python_endpoint=_endpoint(),
        ),
    )


def _observation(episode: int, sequence: int) -> bytes:
    value = decode_observation_json(OBSERVATION_FIXTURE.read_bytes().removesuffix(b"\n"))
    value["identity"]["episode_id"] = episode
    value["identity"]["observation_sequence"] = sequence
    value["source"]["controller_mode"] = "echo"
    value["scenario"]["scenario_seed"] = episode
    value["scenario"]["reset_id"] = f"telemetry:{episode}:attempt0"
    if sequence == 0:
        value["previous_action"] = {"is_present": False}
    else:
        value["previous_action"]["source_observation_sequence"] = sequence - 1
    return encode_observation_json(value)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"episode_id": -1}, "non-negative"),
        ({"completion_sequence": 14}, "at least 16 actions"),
        ({"receive_timeout_ms": 300_001}, "integer in"),
    ],
)
def test_probe_config_rejects_unbounded_or_too_short_runs(changes, message: str) -> None:
    values = {
        "service": _service_config(),
        "episode_id": 7300,
        "completion_sequence": 15,
        "receive_timeout_ms": 1_000,
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        TelemetrySaturationProbeConfig(**values)


def test_probe_sends_maximum_telemetry_without_changing_the_command() -> None:
    service = _service_config()
    config = TelemetrySaturationProbeConfig(
        service=service,
        episode_id=7300,
        completion_sequence=15,
        receive_timeout_ms=1_000,
    )
    probe = TelemetrySaturationProbe(config)
    unreal = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unreal.bind((service.transport.unreal_endpoint.host, service.transport.unreal_endpoint.port))
    unreal.setblocking(False)
    result: list[object] = []

    def run_probe() -> None:
        result.append(probe.run_until_complete())

    try:
        probe.start()
        worker = threading.Thread(target=run_probe)
        worker.start()
        destination = (
            service.transport.python_endpoint.host,
            service.transport.python_endpoint.port,
        )
        action_sizes: list[int] = []
        for sequence in range(16):
            unreal.sendto(_observation(7300, sequence), destination)
            assert select.select([unreal], [], [], 1.0)[0]
            payload, _ = unreal.recvfrom(service.transport.max_action_datagram_bytes)
            action_sizes.append(len(payload))
            action = decode_action_json(payload)
            validate_action_for_observation(
                action,
                expected_episode_id=7300,
                expected_observation_sequence=sequence,
            )
            assert action["command"]["desired_velocity_local_cm_per_s"] == [100.0, 0.0]
            telemetry = action["telemetry"]
            assert telemetry["is_present"]
            assert len(
                telemetry["selected_desired_velocity_trajectory_local_cm_per_s"]
            ) == MAX_TRAJECTORY_STEPS
            assert all(
                step == [100.0, 0.0]
                for step in telemetry[
                    "selected_desired_velocity_trajectory_local_cm_per_s"
                ]
            )
            assert telemetry["cost_breakdown"]["collision_indicator"] == 1.0
        worker.join(1.0)

        assert not worker.is_alive()
        assert len(result) == 1
        report = result[0]
        assert report.completed
        assert report.actions_sent == 16
        assert report.telemetry_steps_per_action == MAX_TRAJECTORY_STEPS
        assert report.minimum_action_bytes == min(action_sizes)
        assert report.maximum_action_bytes == max(action_sizes)
        assert report.datagrams_received == 16
        assert report.valid_observations_received == 16
        assert report.ignored_observations == 0
        with pytest.raises(BlockingIOError):
            unreal.recvfrom(service.transport.max_action_datagram_bytes)
    finally:
        probe.close()
        unreal.close()
