from __future__ import annotations

import select
import socket
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from motionworld.control.config import load_control_service_config
from motionworld.control.old_episode_action_probe import (
    OldEpisodeActionProbe,
    OldEpisodeActionProbeConfig,
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


def _observation(episode: int, sequence: int) -> tuple[dict[str, object], bytes]:
    value = decode_observation_json(OBSERVATION_FIXTURE.read_bytes().removesuffix(b"\n"))
    value["identity"]["episode_id"] = episode
    value["identity"]["observation_sequence"] = sequence
    value["source"]["controller_mode"] = "echo"
    value["scenario"]["scenario_seed"] = episode
    value["scenario"]["reset_id"] = f"old-episode:{episode}:attempt0"
    if sequence == 0:
        value["previous_action"] = {"is_present": False}
    else:
        value["previous_action"]["source_observation_sequence"] = sequence - 1
    return value, encode_observation_json(value)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_episode_id": -1}, "non-negative"),
        ({"source_observation_sequence": -1}, "non-negative"),
        ({"target_episode_id": -1}, "non-negative"),
        ({"target_episode_id": 7298}, "immediate successor"),
        ({"target_observation_sequence": 1}, "configured first sequence"),
        ({"receive_timeout_ms": 300_001}, "integer in"),
    ],
)
def test_probe_config_rejects_unsafe_or_ambiguous_boundaries(changes, message: str) -> None:
    values = {
        "service": _service_config(),
        "source_episode_id": 7296,
        "source_observation_sequence": 0,
        "target_episode_id": 7297,
        "target_observation_sequence": 0,
        "receive_timeout_ms": 1_000,
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        OldEpisodeActionProbeConfig(**values)


def test_probe_sends_retained_action_once_only_after_verified_successor_reset() -> None:
    service = _service_config()
    config = OldEpisodeActionProbeConfig(
        service=service,
        source_episode_id=7296,
        source_observation_sequence=0,
        target_episode_id=7297,
        target_observation_sequence=0,
        receive_timeout_ms=1_000,
    )
    probe = OldEpisodeActionProbe(config)
    unreal = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unreal.bind((service.transport.unreal_endpoint.host, service.transport.unreal_endpoint.port))
    unreal.setblocking(False)
    _, source_payload = _observation(7296, 0)
    _, wrong_target_payload = _observation(7297, 1)
    _, target_payload = _observation(7297, 0)
    result: list[object] = []

    def run_probe() -> None:
        result.append(probe.run_until_sent())

    try:
        probe.start()
        worker = threading.Thread(target=run_probe)
        worker.start()
        destination = (
            service.transport.python_endpoint.host,
            service.transport.python_endpoint.port,
        )
        unreal.sendto(source_payload, destination)
        assert not select.select([unreal], [], [], 0.05)[0]
        unreal.sendto(wrong_target_payload, destination)
        assert not select.select([unreal], [], [], 0.05)[0]
        unreal.sendto(target_payload, destination)
        assert select.select([unreal], [], [], 1.0)[0]
        action_payload, sender = unreal.recvfrom(service.transport.max_action_datagram_bytes)
        worker.join(1.0)

        assert not worker.is_alive()
        assert sender == (
            service.transport.python_endpoint.host,
            service.transport.python_endpoint.port,
        )
        action = decode_action_json(action_payload)
        validate_action_for_observation(
            action,
            expected_episode_id=7296,
            expected_observation_sequence=0,
        )
        assert action["command"]["desired_velocity_local_cm_per_s"] == [100.0, 0.0]
        assert len(result) == 1
        report = result[0]
        assert report.action_sent
        assert report.target_reset_verified
        assert report.target_previous_action_absent
        assert report.datagrams_received == 3
        assert report.valid_observations_received == 3
        assert report.ignored_observations == 1
        with pytest.raises(BlockingIOError):
            unreal.recvfrom(service.transport.max_action_datagram_bytes)
    finally:
        probe.close()
        unreal.close()
