"""Bounded localhost UDP configuration and Python-side datagram I/O."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from motionworld.protocol.action import MAX_ACTION_BYTES, MAX_TRAJECTORY_STEPS
from motionworld.protocol.observation import (
    MAX_OBSERVATION_BYTES,
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
)


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _literal(value: object, expected: object, context: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError(f"{context} must be {expected!r}")


def _positive_int(value: object, context: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    if maximum is not None and value > maximum:
        raise ValueError(f"{context} must not exceed {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class UdpEndpoint:
    """One fixed IPv4 loopback endpoint."""

    host: str
    port: int

    def __post_init__(self) -> None:
        if self.host != "127.0.0.1":
            raise ValueError("control transport endpoints must use IPv4 loopback")
        _positive_int(self.port, "endpoint port", maximum=65_535)


@dataclass(frozen=True, slots=True)
class ControlTransportConfig:
    """Wire and failure policy shared by Unreal and Python."""

    unreal_endpoint: UdpEndpoint
    python_endpoint: UdpEndpoint
    max_observation_datagram_bytes: int
    max_action_datagram_bytes: int
    max_trajectory_steps: int
    max_datagrams_per_poll: int
    max_udp_payload_bytes: int
    dropped_policy: str
    duplicated_policy: str
    reordered_policy: str
    truncated_or_oversized_policy: str
    unknown_sender_policy: str

    def __post_init__(self) -> None:
        if self.unreal_endpoint == self.python_endpoint:
            raise ValueError("Unreal and Python endpoints must be distinct")
        _positive_int(self.max_datagrams_per_poll, "max_datagrams_per_poll", maximum=1_024)
        _positive_int(self.max_udp_payload_bytes, "max_udp_payload_bytes", maximum=65_507)
        if self.max_observation_datagram_bytes != MAX_OBSERVATION_BYTES:
            raise ValueError("transport and observation size limits disagree")
        if self.max_action_datagram_bytes != MAX_ACTION_BYTES:
            raise ValueError("transport and action size limits disagree")
        if self.max_trajectory_steps != MAX_TRAJECTORY_STEPS:
            raise ValueError("transport and action trajectory limits disagree")
        if max(self.max_observation_datagram_bytes, self.max_action_datagram_bytes) >= (
            self.max_udp_payload_bytes
        ):
            raise ValueError("wire message limits must leave one byte for oversize detection")


def _endpoint(value: object, context: str) -> UdpEndpoint:
    raw = _mapping(value, context)
    _keys(raw, {"host", "port"}, context)
    if not isinstance(raw["host"], str):
        raise ValueError(f"{context}.host must be a string")
    return UdpEndpoint(
        host=raw["host"],
        port=_positive_int(raw["port"], f"{context}.port", maximum=65_535),
    )


def load_control_transport_config(path: Path) -> ControlTransportConfig:
    """Load the exact v1 localhost UDP contract and reject policy drift."""

    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "transport config")
    _keys(
        raw,
        {
            "schema_name",
            "schema_version",
            "protocol_name",
            "protocol_version",
            "endpoints",
            "wire",
            "io",
            "packet_policy",
        },
        "transport config",
    )
    _literal(raw["schema_name"], "motionworld_control_transport_config", "schema_name")
    _literal(raw["schema_version"], 1, "schema_version")
    _literal(raw["protocol_name"], PROTOCOL_NAME, "protocol_name")
    _literal(raw["protocol_version"], PROTOCOL_VERSION, "protocol_version")

    endpoints = _mapping(raw["endpoints"], "endpoints")
    _keys(endpoints, {"unreal", "python"}, "endpoints")
    wire = _mapping(raw["wire"], "wire")
    _keys(
        wire,
        {
            "transport",
            "address_family",
            "framing",
            "text_encoding",
            "json_profile",
            "numeric_representation",
            "byte_order",
            "max_observation_datagram_bytes",
            "max_action_datagram_bytes",
            "max_trajectory_steps",
        },
        "wire",
    )
    literals = {
        "transport": "udp",
        "address_family": "ipv4",
        "framing": "one_json_object_per_datagram",
        "text_encoding": "utf-8",
        "json_profile": "rfc8259_strict_no_nan_infinity_or_duplicate_keys",
        "numeric_representation": "json_numbers_binary64_with_safe_integers",
        "byte_order": "not_applicable_utf8_json",
    }
    for key, expected in literals.items():
        _literal(wire[key], expected, f"wire.{key}")

    io = _mapping(raw["io"], "io")
    _keys(
        io,
        {
            "socket_mode",
            "unreal_io_model",
            "python_io_model",
            "max_datagrams_per_poll",
            "max_udp_payload_bytes",
        },
        "io",
    )
    _literal(io["socket_mode"], "nonblocking", "io.socket_mode")
    _literal(io["unreal_io_model"], "bounded_game_thread_poll", "io.unreal_io_model")
    _literal(io["python_io_model"], "bounded_event_loop_poll", "io.python_io_model")

    policies = _mapping(raw["packet_policy"], "packet_policy")
    _keys(
        policies,
        {"dropped", "duplicated", "reordered", "truncated_or_oversized", "unknown_sender"},
        "packet_policy",
    )
    expected_policies = {
        "dropped": "no_retransmission_deadline_fallback",
        "duplicated": "discard_by_episode_and_observation_identity",
        "reordered": "discard_unless_current_outstanding_identity",
        "truncated_or_oversized": "discard_before_json_parse",
        "unknown_sender": "discard_before_json_parse",
    }
    for key, expected in expected_policies.items():
        _literal(policies[key], expected, f"packet_policy.{key}")

    return ControlTransportConfig(
        unreal_endpoint=_endpoint(endpoints["unreal"], "endpoints.unreal"),
        python_endpoint=_endpoint(endpoints["python"], "endpoints.python"),
        max_observation_datagram_bytes=_positive_int(
            wire["max_observation_datagram_bytes"], "max_observation_datagram_bytes"
        ),
        max_action_datagram_bytes=_positive_int(
            wire["max_action_datagram_bytes"], "max_action_datagram_bytes"
        ),
        max_trajectory_steps=_positive_int(
            wire["max_trajectory_steps"], "max_trajectory_steps"
        ),
        max_datagrams_per_poll=_positive_int(
            io["max_datagrams_per_poll"], "max_datagrams_per_poll", maximum=1_024
        ),
        max_udp_payload_bytes=_positive_int(
            io["max_udp_payload_bytes"], "max_udp_payload_bytes", maximum=65_507
        ),
        dropped_policy=policies["dropped"],
        duplicated_policy=policies["duplicated"],
        reordered_policy=policies["reordered"],
        truncated_or_oversized_policy=policies["truncated_or_oversized"],
        unknown_sender_policy=policies["unknown_sender"],
    )


@dataclass(frozen=True, slots=True)
class ReceiveBatch:
    """Bounded result from one nonblocking socket poll."""

    payloads: tuple[bytes, ...]
    datagrams_read: int
    rejected_unknown_sender: int
    rejected_oversized_or_truncated: int
    poll_budget_exhausted: bool


def _require_nonblocking(udp_socket: socket.socket) -> None:
    if udp_socket.getblocking():
        raise ValueError("control UDP socket must be nonblocking")


def receive_bounded_datagrams(
    udp_socket: socket.socket,
    *,
    expected_sender: UdpEndpoint,
    max_payload_bytes: int,
    max_datagrams_per_poll: int,
) -> ReceiveBatch:
    """Drain at most one fixed poll budget without blocking or unbounded allocation."""

    _positive_int(max_payload_bytes, "max_payload_bytes", maximum=65_506)
    _positive_int(max_datagrams_per_poll, "max_datagrams_per_poll", maximum=1_024)
    _require_nonblocking(udp_socket)
    payloads: list[bytes] = []
    read = 0
    unknown = 0
    oversized = 0
    for _ in range(max_datagrams_per_poll):
        try:
            payload, sender = udp_socket.recvfrom(max_payload_bytes + 1)
        except BlockingIOError:
            break
        read += 1
        if sender != (expected_sender.host, expected_sender.port):
            unknown += 1
        elif not payload or len(payload) > max_payload_bytes:
            oversized += 1
        else:
            payloads.append(payload)
    return ReceiveBatch(
        payloads=tuple(payloads),
        datagrams_read=read,
        rejected_unknown_sender=unknown,
        rejected_oversized_or_truncated=oversized,
        poll_budget_exhausted=read == max_datagrams_per_poll,
    )


def open_bound_nonblocking_udp(endpoint: UdpEndpoint) -> socket.socket:
    """Create one IPv4 UDP socket whose receive operations never wait."""

    result = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        result.bind((endpoint.host, endpoint.port))
        result.setblocking(False)
    except BaseException:
        result.close()
        raise
    return result


def send_bounded_datagram(
    udp_socket: socket.socket,
    payload: bytes,
    *,
    destination: UdpEndpoint,
    max_payload_bytes: int,
) -> None:
    """Send exactly one bounded datagram or fail without partial-message recovery."""

    _positive_int(max_payload_bytes, "max_payload_bytes", maximum=65_506)
    if not isinstance(payload, bytes):
        raise TypeError("datagram payload must be bytes")
    if not payload or len(payload) > max_payload_bytes:
        raise ValueError("datagram payload size is invalid")
    _require_nonblocking(udp_socket)
    sent = udp_socket.sendto(payload, (destination.host, destination.port))
    if sent != len(payload):
        raise RuntimeError("UDP datagram send was incomplete")
