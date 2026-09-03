"""One-shot valid-but-late action probe for the R2 stale-rejection test."""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from motionworld.control.config import ControlServiceConfig, load_control_service_config
from motionworld.control.controllers import build_controller
from motionworld.protocol import (
    decode_observation_json,
    encode_action_json,
    open_bound_nonblocking_udp,
    receive_bounded_datagrams,
    send_bounded_datagram,
    validate_action_for_observation,
)

MAX_DELAY_MS = 10_000
MAX_RECEIVE_TIMEOUT_MS = 60_000


def _bounded_positive_int(value: int, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    return value


def _nonnegative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class DelayedActionProbeConfig:
    """Strict bounds for one intentionally late action and no other sends."""

    service: ControlServiceConfig
    episode_id: int
    observation_sequence: int
    delay_ms: int
    receive_timeout_ms: int

    def __post_init__(self) -> None:
        _nonnegative_int(self.episode_id, "episode_id")
        _nonnegative_int(self.observation_sequence, "observation_sequence")
        _bounded_positive_int(self.delay_ms, "delay_ms", MAX_DELAY_MS)
        _bounded_positive_int(
            self.receive_timeout_ms,
            "receive_timeout_ms",
            MAX_RECEIVE_TIMEOUT_MS,
        )
        if self.delay_ms <= self.service.runtime.deadline_ms:
            raise ValueError("delay_ms must be strictly greater than the action deadline")


@dataclass(frozen=True, slots=True)
class DelayedActionProbeReport:
    """Auditable result containing identity and timing, never observation contents."""

    episode_id: int
    observation_sequence: int
    configured_delay_ms: int
    measured_delay_ms: float
    datagrams_received: int
    valid_observations_received: int
    ignored_observations: int
    action_bytes: int
    action_sent: bool


class DelayedActionProbe:
    """Receive one selected observation, delay its valid action, send once, and exit."""

    def __init__(self, config: DelayedActionProbeConfig) -> None:
        self._config = config
        self._socket: socket.socket | None = None

    def start(self) -> None:
        if self._socket is not None:
            raise RuntimeError("delayed action probe is already started")
        self._socket = open_bound_nonblocking_udp(
            self._config.service.transport.python_endpoint
        )

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def run_until_sent(self) -> DelayedActionProbeReport:
        if self._socket is None:
            raise RuntimeError("delayed action probe is not started")
        service = self._config.service
        transport = service.transport
        controller = build_controller(service.controller_mode, service.controller)
        receive_deadline = time.monotonic() + self._config.receive_timeout_ms / 1_000.0
        datagrams_received = 0
        valid_observations = 0
        ignored_observations = 0

        while time.monotonic() < receive_deadline:
            batch = receive_bounded_datagrams(
                self._socket,
                expected_sender=transport.unreal_endpoint,
                max_payload_bytes=transport.max_observation_datagram_bytes,
                max_datagrams_per_poll=transport.max_datagrams_per_poll,
            )
            datagrams_received += batch.datagrams_read
            ignored_observations += (
                batch.rejected_unknown_sender + batch.rejected_oversized_or_truncated
            )
            for payload in batch.payloads:
                try:
                    observation = decode_observation_json(payload)
                except (TypeError, ValueError):
                    ignored_observations += 1
                    continue
                valid_observations += 1
                identity = observation["identity"]
                if (
                    identity["episode_id"] != self._config.episode_id
                    or identity["observation_sequence"]
                    != self._config.observation_sequence
                    or observation["source"]["controller_mode"]
                    != service.controller_mode
                ):
                    ignored_observations += 1
                    continue

                action = controller(observation, threading.Event())
                if action is None:
                    raise RuntimeError("probe controller unexpectedly cancelled its action")
                validated = validate_action_for_observation(
                    action,
                    expected_episode_id=self._config.episode_id,
                    expected_observation_sequence=self._config.observation_sequence,
                )
                encoded = encode_action_json(validated)
                delay_started = time.monotonic()
                time.sleep(self._config.delay_ms / 1_000.0)
                measured_delay_ms = (time.monotonic() - delay_started) * 1_000.0
                send_bounded_datagram(
                    self._socket,
                    encoded,
                    destination=transport.unreal_endpoint,
                    max_payload_bytes=transport.max_action_datagram_bytes,
                )
                return DelayedActionProbeReport(
                    episode_id=self._config.episode_id,
                    observation_sequence=self._config.observation_sequence,
                    configured_delay_ms=self._config.delay_ms,
                    measured_delay_ms=measured_delay_ms,
                    datagrams_received=datagrams_received,
                    valid_observations_received=valid_observations,
                    ignored_observations=ignored_observations,
                    action_bytes=len(encoded),
                    action_sent=True,
                )
            time.sleep(service.poll_interval_ms / 1_000.0)
        raise TimeoutError("target observation was not received before the bounded timeout")


def _positive_cli_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative_cli_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service-config", type=Path, required=True)
    parser.add_argument("--episode-id", type=_nonnegative_cli_int, required=True)
    parser.add_argument(
        "--observation-sequence",
        type=_nonnegative_cli_int,
        default=0,
    )
    parser.add_argument("--delay-ms", type=_positive_cli_int, default=250)
    parser.add_argument("--receive-timeout-ms", type=_positive_cli_int, default=30_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = DelayedActionProbeConfig(
        service=load_control_service_config(args.service_config),
        episode_id=args.episode_id,
        observation_sequence=args.observation_sequence,
        delay_ms=args.delay_ms,
        receive_timeout_ms=args.receive_timeout_ms,
    )
    probe = DelayedActionProbe(config)
    try:
        probe.start()
        print(
            json.dumps(
                {
                    "delay_ms": config.delay_ms,
                    "episode_id": config.episode_id,
                    "health": "ready",
                    "observation_sequence": config.observation_sequence,
                    "python_endpoint": asdict(config.service.transport.python_endpoint),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        report = probe.run_until_sent()
        print(json.dumps(asdict(report), sort_keys=True), flush=True)
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
