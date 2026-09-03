"""One-shot old-episode action probe for the R2 reset-boundary rejection test."""

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


def _nonnegative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _bounded_positive_int(value: int, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    return value


@dataclass(frozen=True, slots=True)
class OldEpisodeActionProbeConfig:
    """Exact source and successor identities for one retained action send."""

    service: ControlServiceConfig
    source_episode_id: int
    source_observation_sequence: int
    target_episode_id: int
    target_observation_sequence: int
    receive_timeout_ms: int

    def __post_init__(self) -> None:
        _nonnegative_int(self.source_episode_id, "source_episode_id")
        _nonnegative_int(self.source_observation_sequence, "source_observation_sequence")
        _nonnegative_int(self.target_episode_id, "target_episode_id")
        _nonnegative_int(self.target_observation_sequence, "target_observation_sequence")
        _bounded_positive_int(
            self.receive_timeout_ms,
            "receive_timeout_ms",
            MAX_RECEIVE_TIMEOUT_MS,
        )
        if self.target_episode_id != self.source_episode_id + 1:
            raise ValueError("target_episode_id must be the immediate successor episode")
        if self.target_observation_sequence != self.service.runtime.first_sequence:
            raise ValueError("target_observation_sequence must be the configured first sequence")


@dataclass(frozen=True, slots=True)
class OldEpisodeActionProbeReport:
    """Auditable identities and counts without retaining observation contents."""

    source_episode_id: int
    source_observation_sequence: int
    target_episode_id: int
    target_observation_sequence: int
    target_reset_verified: bool
    target_previous_action_absent: bool
    datagrams_received: int
    valid_observations_received: int
    ignored_observations: int
    action_bytes: int
    action_sent: bool


class OldEpisodeActionProbe:
    """Retain one valid action, observe a verified reset, send it once, and exit."""

    def __init__(self, config: OldEpisodeActionProbeConfig) -> None:
        self._config = config
        self._socket: socket.socket | None = None

    def start(self) -> None:
        if self._socket is not None:
            raise RuntimeError("old-episode action probe is already started")
        self._socket = open_bound_nonblocking_udp(
            self._config.service.transport.python_endpoint
        )

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def run_until_sent(self) -> OldEpisodeActionProbeReport:
        if self._socket is None:
            raise RuntimeError("old-episode action probe is not started")
        service = self._config.service
        transport = service.transport
        controller = build_controller(service.controller_mode, service.controller)
        receive_deadline = time.monotonic() + self._config.receive_timeout_ms / 1_000.0
        datagrams_received = 0
        valid_observations = 0
        ignored_observations = 0
        retained_action: bytes | None = None

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
                episode = identity["episode_id"]
                sequence = identity["observation_sequence"]
                if observation["source"]["controller_mode"] != service.controller_mode:
                    ignored_observations += 1
                    continue

                if retained_action is None:
                    if (
                        episode != self._config.source_episode_id
                        or sequence != self._config.source_observation_sequence
                    ):
                        ignored_observations += 1
                        continue
                    action = controller(observation, threading.Event())
                    if action is None:
                        raise RuntimeError("probe controller unexpectedly cancelled its action")
                    validated = validate_action_for_observation(
                        action,
                        expected_episode_id=self._config.source_episode_id,
                        expected_observation_sequence=self._config.source_observation_sequence,
                    )
                    retained_action = encode_action_json(validated)
                    continue

                if (
                    episode != self._config.target_episode_id
                    or sequence != self._config.target_observation_sequence
                ):
                    ignored_observations += 1
                    continue
                reset_verified = observation["validity"]["reset_verified"]
                previous_action_absent = not observation["previous_action"]["is_present"]
                if not reset_verified or not previous_action_absent:
                    ignored_observations += 1
                    continue
                send_bounded_datagram(
                    self._socket,
                    retained_action,
                    destination=transport.unreal_endpoint,
                    max_payload_bytes=transport.max_action_datagram_bytes,
                )
                return OldEpisodeActionProbeReport(
                    source_episode_id=self._config.source_episode_id,
                    source_observation_sequence=self._config.source_observation_sequence,
                    target_episode_id=self._config.target_episode_id,
                    target_observation_sequence=self._config.target_observation_sequence,
                    target_reset_verified=reset_verified,
                    target_previous_action_absent=previous_action_absent,
                    datagrams_received=datagrams_received,
                    valid_observations_received=valid_observations,
                    ignored_observations=ignored_observations,
                    action_bytes=len(retained_action),
                    action_sent=True,
                )
            time.sleep(service.poll_interval_ms / 1_000.0)
        raise TimeoutError(
            "source action and verified target reset were not observed before the bounded timeout"
        )


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
    parser.add_argument("--source-episode-id", type=_nonnegative_cli_int, required=True)
    parser.add_argument(
        "--source-observation-sequence",
        type=_nonnegative_cli_int,
        default=0,
    )
    parser.add_argument("--target-episode-id", type=_nonnegative_cli_int, required=True)
    parser.add_argument(
        "--target-observation-sequence",
        type=_nonnegative_cli_int,
        default=0,
    )
    parser.add_argument("--receive-timeout-ms", type=_positive_cli_int, default=300_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = OldEpisodeActionProbeConfig(
        service=load_control_service_config(args.service_config),
        source_episode_id=args.source_episode_id,
        source_observation_sequence=args.source_observation_sequence,
        target_episode_id=args.target_episode_id,
        target_observation_sequence=args.target_observation_sequence,
        receive_timeout_ms=args.receive_timeout_ms,
    )
    probe = OldEpisodeActionProbe(config)
    try:
        probe.start()
        print(
            json.dumps(
                {
                    "health": "ready",
                    "python_endpoint": asdict(config.service.transport.python_endpoint),
                    "source_episode_id": config.source_episode_id,
                    "source_observation_sequence": config.source_observation_sequence,
                    "target_episode_id": config.target_episode_id,
                    "target_observation_sequence": config.target_observation_sequence,
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
