from __future__ import annotations

import select
import socket
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest

from motionworld.control.config import load_control_service_config
from motionworld.control.delayed_action_probe import (
    DelayedActionProbe,
    DelayedActionProbeConfig,
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
    value["scenario"]["reset_id"] = f"delayed:{episode}:attempt0"
    if sequence == 0:
        value["previous_action"] = {"is_present": False}
    else:
        value["previous_action"]["source_observation_sequence"] = sequence - 1
    return value, encode_observation_json(value)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"episode_id": -1}, "non-negative"),
        ({"observation_sequence": -1}, "non-negative"),
        ({"delay_ms": 100}, "strictly greater"),
        ({"delay_ms": 10_001}, "integer in"),
        ({"receive_timeout_ms": 60_001}, "integer in"),
    ],
)
def test_probe_config_rejects_unbounded_or_not_late_values(changes, message: str) -> None:
    values = {
        "service": _service_config(),
        "episode_id": 7295,
        "observation_sequence": 0,
        "delay_ms": 125,
        "receive_timeout_ms": 1_000,
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        DelayedActionProbeConfig(**values)


def test_probe_sends_exactly_one_valid_action_after_the_deadline() -> None:
    service = _service_config()
    config = DelayedActionProbeConfig(
        service=service,
        episode_id=7295,
        observation_sequence=0,
        delay_ms=125,
        receive_timeout_ms=1_000,
    )
    probe = DelayedActionProbe(config)
    unreal = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unreal.bind((service.transport.unreal_endpoint.host, service.transport.unreal_endpoint.port))
    unreal.setblocking(False)
    observation, payload = _observation(7295, 0)
    result: list[object] = []
    started = time.monotonic()

    def run_probe() -> None:
        result.append(probe.run_until_sent())

    try:
        probe.start()
        worker = threading.Thread(target=run_probe)
        worker.start()
        unreal.sendto(
            payload,
            (service.transport.python_endpoint.host, service.transport.python_endpoint.port),
        )
        assert select.select([unreal], [], [], 1.0)[0]
        action_payload, sender = unreal.recvfrom(service.transport.max_action_datagram_bytes)
        elapsed_ms = (time.monotonic() - started) * 1_000.0
        worker.join(1.0)

        assert not worker.is_alive()
        assert sender == (
            service.transport.python_endpoint.host,
            service.transport.python_endpoint.port,
        )
        action = decode_action_json(action_payload)
        validate_action_for_observation(
            action,
            expected_episode_id=7295,
            expected_observation_sequence=0,
        )
        assert action["command"]["desired_velocity_local_cm_per_s"] == [100.0, 0.0]
        assert action["planner"]["measured_latency_ms"] < service.runtime.deadline_ms
        assert elapsed_ms >= service.runtime.deadline_ms
        assert len(result) == 1
        report = result[0]
        assert report.action_sent
        assert report.measured_delay_ms >= 120.0
        assert report.datagrams_received == 1
        assert report.valid_observations_received == 1
        assert report.ignored_observations == 0
        with pytest.raises(BlockingIOError):
            unreal.recvfrom(service.transport.max_action_datagram_bytes)
    finally:
        probe.close()
        unreal.close()
