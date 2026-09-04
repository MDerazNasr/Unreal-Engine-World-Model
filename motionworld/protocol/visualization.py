"""Bounded version-1 telemetry for visualizing real world-model rollouts.

One optional telemetry object is carried atomically inside the action for the
same source observation.  The outer action remains the authority for
controller/model ownership and the final datagram-size check; duplicated inner
identity lets the receiver reject a mismatched visualization bundle.

The four-branch view and the CEM/model comparison are separate display modes,
so twelve path slots are sufficient.  Unreal owns and records the yellow
actual-motion trail locally; it is not sent back as predicted telemetry.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from motionworld.protocol.action import MAX_ACTION_BYTES

VISUALIZATION_SCHEMA_NAME = "motionworld_visualization"
VISUALIZATION_SCHEMA_VERSION = 1
VISUALIZATION_FRAME = "unreal_world_xy_cm"

# Leave room in the 8 KiB action datagram for its required control and identity
# fields. The outer action encoder is still the final size authority.
MAX_VISUALIZATION_BYTES = 6_500
MIN_ACTION_ENVELOPE_RESERVE_BYTES = MAX_ACTION_BYTES - MAX_VISUALIZATION_BYTES
MAX_PATHS = 12
MAX_POINTS_PER_PATH = 16
MAX_TOTAL_POINTS = MAX_PATHS * MAX_POINTS_PER_PATH
MAX_ABS_COORDINATE_CM = 10_000_000.0
MAX_SAFE_JSON_INTEGER = 2**53 - 1
MIN_TIMESTEP_S = 0.001
MAX_TIMESTEP_S = 1.0
MIN_HORIZON_S = 0.001
MAX_HORIZON_S = 10.0


class TrajectoryRole(StrEnum):
    """Meaning of a path drawn in the Unreal demo."""

    CEM_CANDIDATE = "cem_candidate"
    SELECTED = "selected"
    BRANCH_FORWARD = "branch_forward"
    BRANCH_LEFT = "branch_left"
    BRANCH_RIGHT = "branch_right"
    BRANCH_STOP = "branch_stop"
    NOMINAL = "nominal"
    RESIDUAL = "residual"


def _finite_number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{context} must be a finite number")
    return 0.0 if result == 0.0 else result


def _bounded_integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context} must be an integer")
    if value < 0 or value > MAX_SAFE_JSON_INTEGER:
        raise ValueError(f"{context} is out of range")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


@dataclass(frozen=True, slots=True)
class VisualizationPoint:
    """One Unreal-world XY position, measured in centimetres."""

    x_cm: float
    y_cm: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x_cm", _finite_number(self.x_cm, "point.x_cm"))
        object.__setattr__(self, "y_cm", _finite_number(self.y_cm, "point.y_cm"))
        if abs(self.x_cm) > MAX_ABS_COORDINATE_CM:
            raise ValueError("point.x_cm is out of range")
        if abs(self.y_cm) > MAX_ABS_COORDINATE_CM:
            raise ValueError("point.y_cm is out of range")

    def to_json_value(self) -> list[float]:
        return [self.x_cm, self.y_cm]


@dataclass(frozen=True, slots=True)
class VisualizationPath:
    """A single bounded trajectory with a semantic drawing role."""

    role: TrajectoryRole
    points: tuple[VisualizationPoint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.role, TrajectoryRole):
            raise ValueError("path.role must be a TrajectoryRole")
        if not isinstance(self.points, tuple):
            raise ValueError("path.points must be a tuple")
        if not 1 <= len(self.points) <= MAX_POINTS_PER_PATH:
            raise ValueError(
                f"path.points must contain between 1 and {MAX_POINTS_PER_PATH} points"
            )
        if any(not isinstance(point, VisualizationPoint) for point in self.points):
            raise ValueError("path.points must contain VisualizationPoint values")

    def to_json_object(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "points_world_xy_cm": [point.to_json_value() for point in self.points],
        }


@dataclass(frozen=True, slots=True)
class VisualizationTelemetry:
    """Visualization data tied to one authoritative Unreal observation."""

    episode_id: int
    source_observation_sequence: int
    horizon_s: float
    timestep_s: float
    paths: tuple[VisualizationPath, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "episode_id", _bounded_integer(self.episode_id, "identity.episode_id")
        )
        object.__setattr__(
            self,
            "source_observation_sequence",
            _bounded_integer(
                self.source_observation_sequence, "identity.source_observation_sequence"
            ),
        )
        horizon = _finite_number(self.horizon_s, "sampling.horizon_s")
        timestep = _finite_number(self.timestep_s, "sampling.timestep_s")
        if not MIN_HORIZON_S <= horizon <= MAX_HORIZON_S:
            raise ValueError("sampling.horizon_s is out of range")
        if not MIN_TIMESTEP_S <= timestep <= MAX_TIMESTEP_S:
            raise ValueError("sampling.timestep_s is out of range")
        if timestep > horizon:
            raise ValueError("sampling.timestep_s must not exceed horizon_s")
        ratio = horizon / timestep
        rollout_steps = round(ratio)
        if (
            not 1 <= rollout_steps <= MAX_POINTS_PER_PATH - 1
            or not math.isclose(ratio, rollout_steps, rel_tol=0.0, abs_tol=1e-9)
        ):
            raise ValueError(
                "sampling.horizon_s/timestep_s must be an integer between 1 and 15"
            )
        object.__setattr__(self, "horizon_s", horizon)
        object.__setattr__(self, "timestep_s", timestep)

        if not isinstance(self.paths, tuple):
            raise ValueError("paths must be a tuple")
        if not 1 <= len(self.paths) <= MAX_PATHS:
            raise ValueError(f"paths must contain between 1 and {MAX_PATHS} paths")
        if any(not isinstance(path, VisualizationPath) for path in self.paths):
            raise ValueError("paths must contain VisualizationPath values")
        expected_points = rollout_steps + 1
        if any(len(path.points) != expected_points for path in self.paths):
            raise ValueError(
                "every path must contain exactly horizon_s/timestep_s + 1 points"
            )
        total_points = sum(len(path.points) for path in self.paths)
        if total_points > MAX_TOTAL_POINTS:
            raise ValueError(f"visualization exceeds the {MAX_TOTAL_POINTS}-point limit")

        unique_roles = [
            path.role for path in self.paths if path.role != TrajectoryRole.CEM_CANDIDATE
        ]
        if len(unique_roles) != len(set(unique_roles)):
            raise ValueError("only the cem_candidate role may appear more than once")

    def to_json_object(self) -> dict[str, object]:
        """Return a deterministic, JSON-ready object using only protocol primitives."""

        return {
            "schema": {
                "name": VISUALIZATION_SCHEMA_NAME,
                "version": VISUALIZATION_SCHEMA_VERSION,
            },
            "identity": {
                "episode_id": self.episode_id,
                "source_observation_sequence": self.source_observation_sequence,
            },
            "frame": VISUALIZATION_FRAME,
            "sampling": {
                "horizon_s": self.horizon_s,
                "timestep_s": self.timestep_s,
            },
            "paths": [path.to_json_object() for path in self.paths],
        }

    def encode_json(self) -> bytes:
        """Encode deterministically and enforce the transport-size ceiling."""

        payload = json.dumps(
            self.to_json_object(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(payload) > MAX_VISUALIZATION_BYTES:
            raise ValueError(
                f"visualization payload exceeds the {MAX_VISUALIZATION_BYTES}-byte limit"
            )
        return payload


def visualization_from_json_object(value: object) -> VisualizationTelemetry:
    """Strictly validate a decoded JSON object and construct immutable telemetry."""

    if not isinstance(value, dict):
        raise ValueError("visualization must be an object")
    _exact_keys(value, {"schema", "identity", "frame", "sampling", "paths"}, "visualization")

    schema = value["schema"]
    if not isinstance(schema, dict):
        raise ValueError("schema must be an object")
    _exact_keys(schema, {"name", "version"}, "schema")
    if schema["name"] != VISUALIZATION_SCHEMA_NAME:
        raise ValueError("schema.name is unsupported")
    if type(schema["version"]) is not int or schema["version"] != VISUALIZATION_SCHEMA_VERSION:
        raise ValueError("schema.version is unsupported")
    if value["frame"] != VISUALIZATION_FRAME:
        raise ValueError("frame is unsupported")

    identity = value["identity"]
    if not isinstance(identity, dict):
        raise ValueError("identity must be an object")
    _exact_keys(identity, {"episode_id", "source_observation_sequence"}, "identity")
    sampling = value["sampling"]
    if not isinstance(sampling, dict):
        raise ValueError("sampling must be an object")
    _exact_keys(sampling, {"horizon_s", "timestep_s"}, "sampling")

    raw_paths = value["paths"]
    if not isinstance(raw_paths, list):
        raise ValueError("paths must be an array")
    paths: list[VisualizationPath] = []
    for path_index, raw_path in enumerate(raw_paths):
        if not isinstance(raw_path, dict):
            raise ValueError(f"paths[{path_index}] must be an object")
        _exact_keys(raw_path, {"role", "points_world_xy_cm"}, f"paths[{path_index}]")
        try:
            role = TrajectoryRole(raw_path["role"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"paths[{path_index}].role is unsupported") from error
        raw_points = raw_path["points_world_xy_cm"]
        if not isinstance(raw_points, list):
            raise ValueError(f"paths[{path_index}].points_world_xy_cm must be an array")
        points: list[VisualizationPoint] = []
        for point_index, raw_point in enumerate(raw_points):
            if not isinstance(raw_point, list) or len(raw_point) != 2:
                raise ValueError(
                    f"paths[{path_index}].points_world_xy_cm[{point_index}] "
                    "must contain exactly 2 values"
                )
            points.append(VisualizationPoint(raw_point[0], raw_point[1]))
        paths.append(VisualizationPath(role=role, points=tuple(points)))

    return VisualizationTelemetry(
        episode_id=identity["episode_id"],
        source_observation_sequence=identity["source_observation_sequence"],
        horizon_s=sampling["horizon_s"],
        timestep_s=sampling["timestep_s"],
        paths=tuple(paths),
    )


def decode_visualization_json(payload: bytes) -> VisualizationTelemetry:
    """Decode a bounded UTF-8 JSON payload into strict visualization telemetry."""

    if not isinstance(payload, bytes):
        raise TypeError("visualization payload must be bytes")
    if not payload or len(payload) > MAX_VISUALIZATION_BYTES:
        raise ValueError("visualization payload size is invalid")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            parse_constant=_reject_nonfinite_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("visualization payload is not valid UTF-8 JSON") from error
    return visualization_from_json_object(value)


def _reject_nonfinite_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is forbidden: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result
