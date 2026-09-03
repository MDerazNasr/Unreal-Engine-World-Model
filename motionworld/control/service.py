"""Standalone bounded, latest-observation-only Python control service."""

from __future__ import annotations

import argparse
import json
import signal
import socket
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from types import FrameType
from typing import Any

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

Observation = dict[str, Any]
PlannerResult = Mapping[str, Any] | None
Planner = Callable[[Observation, threading.Event], PlannerResult]
Identity = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ServiceSnapshot:
    """Bounded public health/diagnostic state with no packet contents."""

    health: str
    ready: bool
    controller_mode: str
    current_episode_id: int | None
    current_observation_sequence: int | None
    tracked_episode_count: int
    datagrams_received: int
    observations_validated: int
    observations_dispatched: int
    actions_sent: int
    malformed_observations: int
    rejected_observations: int
    superseded_plans: int
    planner_errors: int
    send_errors: int
    recent_rejections: tuple[str, ...]


@dataclass(slots=True)
class _Counters:
    datagrams_received: int = 0
    observations_validated: int = 0
    observations_dispatched: int = 0
    actions_sent: int = 0
    malformed_observations: int = 0
    rejected_observations: int = 0
    superseded_plans: int = 0
    planner_errors: int = 0
    send_errors: int = 0


@dataclass(slots=True)
class _PlanningRequest:
    identity: Identity
    observation: Observation
    cancelled: threading.Event


@dataclass(slots=True)
class _PlanningCompletion:
    request: _PlanningRequest
    result: PlannerResult = None
    error: BaseException | None = None


class _LatestOnlyPlannerWorker:
    def __init__(self, planner: Planner) -> None:
        self._planner = planner
        self._condition = threading.Condition()
        self._pending: _PlanningRequest | None = None
        self._active: _PlanningRequest | None = None
        self._completion: _PlanningCompletion | None = None
        self._stopping = False
        self._thread = threading.Thread(
            target=self._run,
            name="motionworld-planner",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def submit(self, identity: Identity, observation: Observation) -> int:
        request = _PlanningRequest(identity, observation, threading.Event())
        superseded = 0
        with self._condition:
            if self._stopping:
                raise RuntimeError("planner worker is stopping")
            if self._active is not None and not self._active.cancelled.is_set():
                self._active.cancelled.set()
                superseded += 1
            if self._pending is not None:
                self._pending.cancelled.set()
                superseded += 1
            if self._completion is not None:
                self._completion.request.cancelled.set()
                self._completion = None
                superseded += 1
            self._pending = request
            self._condition.notify()
        return superseded

    def take_completion(self) -> _PlanningCompletion | None:
        with self._condition:
            completion = self._completion
            self._completion = None
            return completion

    def stop(self, timeout_s: float) -> bool:
        with self._condition:
            self._stopping = True
            if self._active is not None:
                self._active.cancelled.set()
            if self._pending is not None:
                self._pending.cancelled.set()
                self._pending = None
            self._completion = None
            self._condition.notify_all()
        self._thread.join(timeout_s)
        return not self._thread.is_alive()

    def _run(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._stopping:
                    self._condition.wait()
                if self._stopping:
                    return
                request = self._pending
                self._pending = None
                self._active = request
            assert request is not None
            completion = _PlanningCompletion(request=request)
            try:
                completion.result = self._planner(request.observation, request.cancelled)
            except BaseException as error:  # contained at the worker trust boundary
                completion.error = error
            with self._condition:
                if self._active is request:
                    self._active = None
                if not self._stopping and not request.cancelled.is_set():
                    self._completion = completion


class ControlService:
    """Own one bounded UDP endpoint and dispatch only the newest valid observation."""

    def __init__(self, config: ControlServiceConfig, planner: Planner) -> None:
        self._config = config
        self._planner = planner
        self._socket: socket.socket | None = None
        self._worker: _LatestOnlyPlannerWorker | None = None
        self._health = "stopped"
        self._current_identity: Identity | None = None
        self._latest_by_episode: OrderedDict[int, int] = OrderedDict()
        self._counters = _Counters()
        self._recent_rejections: deque[str] = deque(
            maxlen=config.max_recent_rejections
        )

    def start(self) -> None:
        if self._health != "stopped":
            raise RuntimeError("control service is already started")
        self._health = "starting"
        try:
            self._socket = open_bound_nonblocking_udp(
                self._config.transport.python_endpoint
            )
            self._worker = _LatestOnlyPlannerWorker(self._planner)
            self._worker.start()
        except BaseException:
            if self._socket is not None:
                self._socket.close()
                self._socket = None
            self._health = "faulted"
            raise
        self._health = "running"

    def poll_once(self) -> ServiceSnapshot:
        if self._health != "running" or self._socket is None or self._worker is None:
            raise RuntimeError("control service is not running")
        transport = self._config.transport
        batch = receive_bounded_datagrams(
            self._socket,
            expected_sender=transport.unreal_endpoint,
            max_payload_bytes=transport.max_observation_datagram_bytes,
            max_datagrams_per_poll=transport.max_datagrams_per_poll,
        )
        self._counters.datagrams_received += batch.datagrams_read
        self._counters.rejected_observations += (
            batch.rejected_unknown_sender + batch.rejected_oversized_or_truncated
        )
        for _ in range(batch.rejected_unknown_sender):
            self._reject("unknown_sender")
        for _ in range(batch.rejected_oversized_or_truncated):
            self._reject("invalid_datagram_size")
        for payload in batch.payloads:
            self._accept_payload(payload)
        self._publish_completion(self._worker.take_completion())
        return self.snapshot()

    def snapshot(self) -> ServiceSnapshot:
        episode, sequence = self._current_identity or (None, None)
        return ServiceSnapshot(
            health=self._health,
            ready=(
                self._health == "running"
                and self._socket is not None
                and self._worker is not None
            ),
            controller_mode=self._config.controller_mode,
            current_episode_id=episode,
            current_observation_sequence=sequence,
            tracked_episode_count=len(self._latest_by_episode),
            recent_rejections=tuple(self._recent_rejections),
            **asdict(self._counters),
        )

    def close(self) -> None:
        if self._health == "stopped":
            return
        self._health = "stopping"
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        worker = self._worker
        self._worker = None
        stopped = worker is None or worker.stop(
            self._config.planner_shutdown_timeout_ms / 1000.0
        )
        self._health = "stopped" if stopped else "faulted"
        if not stopped:
            self._reject("planner_shutdown_timeout")

    def _accept_payload(self, payload: bytes) -> None:
        try:
            observation = decode_observation_json(payload)
        except (TypeError, ValueError):
            self._counters.malformed_observations += 1
            self._counters.rejected_observations += 1
            self._reject("invalid_observation")
            return
        self._counters.observations_validated += 1
        if observation["source"]["controller_mode"] != self._config.controller_mode:
            self._counters.rejected_observations += 1
            self._reject("controller_mode_mismatch")
            return
        identity = observation["identity"]
        episode = identity["episode_id"]
        sequence = identity["observation_sequence"]
        if not self._admit_identity(episode, sequence, observation):
            self._counters.rejected_observations += 1
            return
        assert self._worker is not None
        self._current_identity = (episode, sequence)
        self._counters.superseded_plans += self._worker.submit(
            self._current_identity, observation
        )
        self._counters.observations_dispatched += 1

    def _admit_identity(
        self,
        episode: int,
        sequence: int,
        observation: Observation,
    ) -> bool:
        if self._current_identity is not None and episode != self._current_identity[0]:
            if episode in self._latest_by_episode:
                self._reject("noncurrent_episode")
                return False
            if sequence != self._config.runtime.first_sequence:
                self._reject("new_episode_without_first_sequence")
                return False
            if not observation["validity"]["reset_verified"]:
                self._reject("new_episode_without_verified_reset")
                return False
        latest = self._latest_by_episode.get(episode)
        if latest is not None and sequence <= latest:
            self._reject("duplicate_or_stale_observation")
            return False
        self._latest_by_episode[episode] = sequence
        self._latest_by_episode.move_to_end(episode)
        while len(self._latest_by_episode) > self._config.max_tracked_episodes:
            self._latest_by_episode.popitem(last=False)
        return True

    def _publish_completion(self, completion: _PlanningCompletion | None) -> None:
        if completion is None or completion.request.cancelled.is_set():
            return
        if completion.request.identity != self._current_identity:
            self._counters.superseded_plans += 1
            return
        if completion.error is not None:
            self._counters.planner_errors += 1
            self._reject(f"planner_error:{type(completion.error).__name__}")
            return
        if completion.result is None:
            return
        episode, sequence = completion.request.identity
        try:
            action = validate_action_for_observation(
                completion.result,
                expected_episode_id=episode,
                expected_observation_sequence=sequence,
            )
            payload = encode_action_json(action)
            assert self._socket is not None
            send_bounded_datagram(
                self._socket,
                payload,
                destination=self._config.transport.unreal_endpoint,
                max_payload_bytes=self._config.transport.max_action_datagram_bytes,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            self._counters.send_errors += 1
            self._reject(f"action_rejected:{type(error).__name__}")
            return
        self._counters.actions_sent += 1

    def _reject(self, reason: str) -> None:
        encoded = reason.encode("utf-8", errors="replace")
        bounded = encoded[: self._config.max_error_utf8_bytes].decode(
            "utf-8", errors="ignore"
        )
        self._recent_rejections.append(bounded)


def safe_zero_planner(observation: Observation, cancelled: threading.Event) -> PlannerResult:
    """Lifecycle-safe zero helper retained for service cancellation tests."""

    if cancelled.is_set():
        return None
    started_us = time.monotonic_ns() // 1_000
    finished_us = time.monotonic_ns() // 1_000
    identity = observation["identity"]
    return {
        "protocol": {"name": "motionworld_control", "version": 1, "message_type": "action"},
        "identity": {
            "episode_id": identity["episode_id"],
            "source_observation_sequence": identity["observation_sequence"],
        },
        "command": {"desired_velocity_local_cm_per_s": [0.0, 0.0]},
        "controller": {
            "controller_id": observation["source"]["controller_mode"],
            "model_id": "r2_lifecycle_safe_zero",
        },
        "planner": {
            "started_monotonic_us": started_us,
            "finished_monotonic_us": finished_us,
            "measured_latency_ms": (finished_us - started_us) / 1_000.0,
        },
        "fallback": {"is_safe_fallback": True, "reason": "planner_error"},
        "telemetry": {"is_present": False},
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/control_service.yaml"),
        help="service config whose nested paths are resolved relative to it",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate configuration in a clean process and exit without binding",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_control_service_config(args.config)
    if args.check_config:
        print(
            json.dumps(
                {
                    "controller_mode": config.controller_mode,
                    "python_endpoint": asdict(config.transport.python_endpoint),
                    "status": "config_valid",
                },
                sort_keys=True,
            )
        )
        return 0

    service = ControlService(config, build_controller(config.controller_mode, config.controller))
    stop = threading.Event()

    def request_stop(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    previous_sigint = signal.signal(signal.SIGINT, request_stop)
    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    try:
        service.start()
        print(json.dumps(asdict(service.snapshot()), sort_keys=True), flush=True)
        while not stop.is_set():
            service.poll_once()
            stop.wait(config.poll_interval_ms / 1_000.0)
    finally:
        service.close()
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
