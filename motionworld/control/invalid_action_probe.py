"""Bounded malformed/non-finite action probe for the R2 live safety test."""

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

MAX_RECEIVE_TIMEOUT_MS = 300_000
MIN_VALID_ACTIONS_BEFORE_FAULT = 3


def _nonnegative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _bounded_positive_int(value: int, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    return value


@dataclass(frozen=True, slots=True)
class InvalidActionProbeConfig:
    """Exact identities for two isolated faults surrounded by valid actions."""

    service: ControlServiceConfig
    episode_id: int
    malformed_sequence: int
    nonfinite_sequence: int
    completion_sequence: int
    receive_timeout_ms: int

    def __post_init__(self) -> None:
        _nonnegative_int(self.episode_id, "episode_id")
        _nonnegative_int(self.malformed_sequence, "malformed_sequence")
        _nonnegative_int(self.nonfinite_sequence, "nonfinite_sequence")
        _nonnegative_int(self.completion_sequence, "completion_sequence")
        _bounded_positive_int(
            self.receive_timeout_ms,
            "receive_timeout_ms",
            MAX_RECEIVE_TIMEOUT_MS,
        )
        first = self.service.runtime.first_sequence
        if self.malformed_sequence < first + MIN_VALID_ACTIONS_BEFORE_FAULT:
            raise ValueError("malformed_sequence must follow at least three valid actions")
        if self.nonfinite_sequence < self.malformed_sequence + 2:
            raise ValueError("nonfinite_sequence must follow a valid recovery action")
        if self.completion_sequence < self.nonfinite_sequence + 2:
            raise ValueError("completion_sequence must prove a valid post-fault recovery")


@dataclass(frozen=True, slots=True)
class InvalidActionProbeReport:
    """Auditable send counts and identities without observation contents."""

    episode_id: int
    first_sequence: int
    malformed_sequence: int
    nonfinite_sequence: int
    completion_sequence: int
    datagrams_received: int
    valid_observations_received: int
    ignored_observations: int
    valid_actions_sent: int
    malformed_actions_sent: int
    nonfinite_actions_sent: int
    completed: bool


def _nonfinite_command_payload(valid_payload: bytes) -> bytes:
    needle = b'"desired_velocity_local_cm_per_s":[100.0,0.0]'
    replacement = b'"desired_velocity_local_cm_per_s":[1e309,0.0]'
    if valid_payload.count(needle) != 1:
        raise RuntimeError("probe requires the frozen forward echo command")
    return valid_payload.replace(needle, replacement, 1)


class InvalidActionProbe:
    """Send valid motion around two exact invalid responses, then exit."""

    def __init__(self, config: InvalidActionProbeConfig) -> None:
        self._config = config
        self._socket: socket.socket | None = None

    def start(self) -> None:
        if self._socket is not None:
            raise RuntimeError("invalid-action probe is already started")
        self._socket = open_bound_nonblocking_udp(
            self._config.service.transport.python_endpoint
        )

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def run_until_complete(self) -> InvalidActionProbeReport:
        if self._socket is None:
            raise RuntimeError("invalid-action probe is not started")
        service = self._config.service
        transport = service.transport
        controller = build_controller(service.controller_mode, service.controller)
        deadline = time.monotonic() + self._config.receive_timeout_ms / 1_000.0
        next_sequence = service.runtime.first_sequence
        datagrams_received = 0
        valid_observations = 0
        ignored_observations = 0
        valid_actions_sent = 0
        malformed_actions_sent = 0
        nonfinite_actions_sent = 0

        while time.monotonic() < deadline:
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
                episode = identity["episode_id"]
                sequence = identity["observation_sequence"]
                if episode != self._config.episode_id:
                    ignored_observations += 1
                    continue
                if observation["source"]["controller_mode"] != service.controller_mode:
                    raise RuntimeError("target episode changed controller mode")
                if sequence < next_sequence:
                    ignored_observations += 1
                    continue
                if sequence > next_sequence:
                    raise RuntimeError(
                        f"target observation gap: expected {next_sequence}, received {sequence}"
                    )

                action = controller(observation, threading.Event())
                if action is None:
                    raise RuntimeError("probe controller unexpectedly cancelled its action")
                validated = validate_action_for_observation(
                    action,
                    expected_episode_id=self._config.episode_id,
                    expected_observation_sequence=sequence,
                )
                valid_payload = encode_action_json(validated)
                if sequence == self._config.malformed_sequence:
                    action_payload = b"{"
                    malformed_actions_sent += 1
                elif sequence == self._config.nonfinite_sequence:
                    action_payload = _nonfinite_command_payload(valid_payload)
                    nonfinite_actions_sent += 1
                else:
                    action_payload = valid_payload
                    valid_actions_sent += 1
                send_bounded_datagram(
                    self._socket,
                    action_payload,
                    destination=transport.unreal_endpoint,
                    max_payload_bytes=transport.max_action_datagram_bytes,
                )
                next_sequence += 1
                if sequence == self._config.completion_sequence:
                    return InvalidActionProbeReport(
                        episode_id=self._config.episode_id,
                        first_sequence=service.runtime.first_sequence,
                        malformed_sequence=self._config.malformed_sequence,
                        nonfinite_sequence=self._config.nonfinite_sequence,
                        completion_sequence=self._config.completion_sequence,
                        datagrams_received=datagrams_received,
                        valid_observations_received=valid_observations,
                        ignored_observations=ignored_observations,
                        valid_actions_sent=valid_actions_sent,
                        malformed_actions_sent=malformed_actions_sent,
                        nonfinite_actions_sent=nonfinite_actions_sent,
                        completed=True,
                    )
            time.sleep(service.poll_interval_ms / 1_000.0)
        raise TimeoutError("contiguous target observations did not complete before timeout")


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
    parser.add_argument("--malformed-sequence", type=_nonnegative_cli_int, default=10)
    parser.add_argument("--nonfinite-sequence", type=_nonnegative_cli_int, default=20)
    parser.add_argument("--completion-sequence", type=_nonnegative_cli_int, default=25)
    parser.add_argument("--receive-timeout-ms", type=_positive_cli_int, default=300_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = InvalidActionProbeConfig(
        service=load_control_service_config(args.service_config),
        episode_id=args.episode_id,
        malformed_sequence=args.malformed_sequence,
        nonfinite_sequence=args.nonfinite_sequence,
        completion_sequence=args.completion_sequence,
        receive_timeout_ms=args.receive_timeout_ms,
    )
    probe = InvalidActionProbe(config)
    try:
        probe.start()
        print(
            json.dumps(
                {
                    "completion_sequence": config.completion_sequence,
                    "episode_id": config.episode_id,
                    "health": "ready",
                    "malformed_sequence": config.malformed_sequence,
                    "nonfinite_sequence": config.nonfinite_sequence,
                    "python_endpoint": asdict(config.service.transport.python_endpoint),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        report = probe.run_until_complete()
        print(json.dumps(asdict(report), sort_keys=True), flush=True)
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
