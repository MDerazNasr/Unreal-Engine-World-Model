from __future__ import annotations

import select
import socket
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from motionworld.control.config import load_control_service_config
from motionworld.control.invalid_action_probe import (
    InvalidActionProbe,
    InvalidActionProbeConfig,
)
from motionworld.protocol import (
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
    value["scenario"]["reset_id"] = f"invalid-action:{episode}:attempt0"
    if sequence == 0:
        value["previous_action"] = {"is_present": False}
    else:
        value["previous_action"]["source_observation_sequence"] = sequence - 1
    return encode_observation_json(value)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"episode_id": -1}, "non-negative"),
        ({"malformed_sequence": 2}, "three valid actions"),
        ({"nonfinite_sequence": 4}, "valid recovery action"),
        ({"completion_sequence": 5}, "post-fault recovery"),
        ({"receive_timeout_ms": 300_001}, "integer in"),
    ],
)
def test_probe_config_rejects_unbounded_or_unisolated_faults(changes, message: str) -> None:
    values = {
        "service": _service_config(),
        "episode_id": 7298,
        "malformed_sequence": 3,
        "nonfinite_sequence": 5,
        "completion_sequence": 7,
        "receive_timeout_ms": 1_000,
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        InvalidActionProbeConfig(**values)


def test_probe_sends_two_exact_faults_surrounded_by_valid_forward_actions() -> None:
    service = _service_config()
    config = InvalidActionProbeConfig(
        service=service,
        episode_id=7298,
        malformed_sequence=3,
        nonfinite_sequence=5,
        completion_sequence=7,
        receive_timeout_ms=1_000,
    )
    probe = InvalidActionProbe(config)
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
        received: list[bytes] = []
        for sequence in range(8):
            unreal.sendto(_observation(7298, sequence), destination)
            assert select.select([unreal], [], [], 1.0)[0]
            payload, sender = unreal.recvfrom(service.transport.max_action_datagram_bytes)
            assert sender == (
                service.transport.python_endpoint.host,
                service.transport.python_endpoint.port,
            )
            received.append(payload)
        worker.join(1.0)

        assert not worker.is_alive()
        assert received[3] == b"{"
        assert b'"desired_velocity_local_cm_per_s":[1e309,0.0]' in received[5]
        with pytest.raises(ValueError, match="finite"):
            decode_action_json(received[5])
        for sequence in (0, 1, 2, 4, 6, 7):
            action = decode_action_json(received[sequence])
            validate_action_for_observation(
                action,
                expected_episode_id=7298,
                expected_observation_sequence=sequence,
            )
            assert action["command"]["desired_velocity_local_cm_per_s"] == [100.0, 0.0]
        assert len(result) == 1
        report = result[0]
        assert report.completed
        assert report.valid_actions_sent == 6
        assert report.malformed_actions_sent == 1
        assert report.nonfinite_actions_sent == 1
        assert report.datagrams_received == 8
        assert report.valid_observations_received == 8
        assert report.ignored_observations == 0
        with pytest.raises(BlockingIOError):
            unreal.recvfrom(service.transport.max_action_datagram_bytes)
    finally:
        probe.close()
        unreal.close()
