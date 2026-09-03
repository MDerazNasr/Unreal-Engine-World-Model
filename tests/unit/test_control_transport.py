from __future__ import annotations

import select
import socket
from pathlib import Path

import pytest
import yaml

from motionworld.protocol import (
    MAX_ACTION_BYTES,
    MAX_OBSERVATION_BYTES,
    MAX_TRAJECTORY_STEPS,
    UdpEndpoint,
    load_control_transport_config,
    open_bound_nonblocking_udp,
    receive_bounded_datagrams,
    send_bounded_datagram,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "control_transport.yaml"


def _mutated_config(tmp_path: Path, mutate) -> Path:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(raw)
    result = tmp_path / "transport.yaml"
    result.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return result


def _udp_socket() -> socket.socket:
    result = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    result.bind(("127.0.0.1", 0))
    result.setblocking(False)
    return result


def _endpoint(udp_socket: socket.socket) -> UdpEndpoint:
    host, port = udp_socket.getsockname()
    return UdpEndpoint(host=host, port=port)


def test_transport_config_freezes_localhost_udp_wire_contract() -> None:
    config = load_control_transport_config(CONFIG_PATH)
    assert config.unreal_endpoint == UdpEndpoint("127.0.0.1", 52580)
    assert config.python_endpoint == UdpEndpoint("127.0.0.1", 52581)
    assert config.max_observation_datagram_bytes == MAX_OBSERVATION_BYTES
    assert config.max_action_datagram_bytes == MAX_ACTION_BYTES
    assert config.max_trajectory_steps == MAX_TRAJECTORY_STEPS
    assert config.max_datagrams_per_poll == 16
    assert config.dropped_policy == "no_retransmission_deadline_fallback"
    assert config.duplicated_policy == "discard_by_episode_and_observation_identity"
    assert config.reordered_policy == "discard_unless_current_outstanding_identity"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda raw: raw.update(extra=True), "keys must be exactly"),
        (lambda raw: raw.update(protocol_version=2), "protocol_version"),
        (lambda raw: raw["endpoints"]["unreal"].update(host="0.0.0.0"), "loopback"),
        (
            lambda raw: raw["endpoints"].update(python=raw["endpoints"]["unreal"].copy()),
            "must be distinct",
        ),
        (
            lambda raw: raw["wire"].update(max_action_datagram_bytes=8193),
            "action size limits disagree",
        ),
        (lambda raw: raw["io"].update(socket_mode="blocking"), "socket_mode"),
        (lambda raw: raw["io"].update(max_datagrams_per_poll=False), "positive integer"),
        (
            lambda raw: raw["packet_policy"].update(reordered="accept_latest_arrival"),
            "packet_policy.reordered",
        ),
    ],
)
def test_transport_config_rejects_schema_or_safety_drift(
    tmp_path: Path, mutate, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        load_control_transport_config(_mutated_config(tmp_path, mutate))


def test_receive_poll_is_nonblocking_and_bounded() -> None:
    receiver = _udp_socket()
    sender = _udp_socket()
    try:
        empty = receive_bounded_datagrams(
            receiver,
            expected_sender=_endpoint(sender),
            max_payload_bytes=8,
            max_datagrams_per_poll=2,
        )
        assert empty.datagrams_read == 0
        sender.sendto(b"one", receiver.getsockname())
        sender.sendto(b"two", receiver.getsockname())
        sender.sendto(b"three", receiver.getsockname())
        assert select.select([receiver], [], [], 1.0)[0]

        first = receive_bounded_datagrams(
            receiver,
            expected_sender=_endpoint(sender),
            max_payload_bytes=8,
            max_datagrams_per_poll=2,
        )
        assert first.payloads == (b"one", b"two")
        assert first.datagrams_read == 2
        assert first.poll_budget_exhausted

        second = receive_bounded_datagrams(
            receiver,
            expected_sender=_endpoint(sender),
            max_payload_bytes=8,
            max_datagrams_per_poll=2,
        )
        assert second.payloads == (b"three",)
        assert not second.poll_budget_exhausted
    finally:
        sender.close()
        receiver.close()


def test_receive_rejects_unknown_empty_and_oversized_datagrams_before_parse() -> None:
    receiver = _udp_socket()
    sender = _udp_socket()
    intruder = _udp_socket()
    try:
        intruder.sendto(b"valid-shape", receiver.getsockname())
        sender.sendto(b"", receiver.getsockname())
        sender.sendto(b"123456789", receiver.getsockname())
        sender.sendto(b"valid", receiver.getsockname())
        assert select.select([receiver], [], [], 1.0)[0]
        batch = receive_bounded_datagrams(
            receiver,
            expected_sender=_endpoint(sender),
            max_payload_bytes=8,
            max_datagrams_per_poll=8,
        )
        assert batch.payloads == (b"valid",)
        assert batch.rejected_unknown_sender == 1
        assert batch.rejected_oversized_or_truncated == 2
    finally:
        intruder.close()
        sender.close()
        receiver.close()


def test_send_is_one_bounded_datagram() -> None:
    receiver = _udp_socket()
    sender = _udp_socket()
    try:
        send_bounded_datagram(
            sender,
            b'{"message":1}',
            destination=_endpoint(receiver),
            max_payload_bytes=32,
        )
        assert select.select([receiver], [], [], 1.0)[0]
        assert receiver.recvfrom(32)[0] == b'{"message":1}'
        with pytest.raises(ValueError, match="size"):
            send_bounded_datagram(
                sender, b"", destination=_endpoint(receiver), max_payload_bytes=32
            )
        with pytest.raises(ValueError, match="size"):
            send_bounded_datagram(
                sender, b"x" * 33, destination=_endpoint(receiver), max_payload_bytes=32
            )
        with pytest.raises(ValueError, match="must not exceed"):
            send_bounded_datagram(
                sender, b"x", destination=_endpoint(receiver), max_payload_bytes=65_507
            )
    finally:
        sender.close()
        receiver.close()


def test_transport_helpers_reject_blocking_sockets() -> None:
    blocking = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(ValueError, match="nonblocking"):
            receive_bounded_datagrams(
                blocking,
                expected_sender=UdpEndpoint("127.0.0.1", 52580),
                max_payload_bytes=8,
                max_datagrams_per_poll=1,
            )
        with pytest.raises(ValueError, match="nonblocking"):
            send_bounded_datagram(
                blocking,
                b"x",
                destination=UdpEndpoint("127.0.0.1", 52580),
                max_payload_bytes=8,
            )
    finally:
        blocking.close()


def test_open_helper_binds_ipv4_loopback_and_sets_nonblocking() -> None:
    probe = _udp_socket()
    endpoint = _endpoint(probe)
    probe.close()
    opened = open_bound_nonblocking_udp(endpoint)
    try:
        assert opened.getsockname() == (endpoint.host, endpoint.port)
        assert not opened.getblocking()
    finally:
        opened.close()
