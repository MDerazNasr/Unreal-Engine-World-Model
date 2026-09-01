"""Explicit planar coordinate conversions for Unreal character motion.

Unreal uses world ``+X`` and ``+Y`` as its horizontal axes. MotionWorld uses
character-local ``+X`` for forward and ``+Y`` for right. Model-facing angles are
radians even though the Unreal bridge exposes diagnostic yaw in degrees.

Vectors describe direction or velocity, so translation never applies to them.
Points describe locations, so point conversion also uses a world-space origin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class YawRadians:
    """A finite planar yaw explicitly stored in radians.

    Coordinate functions require this wrapper instead of accepting a bare float.
    Callers crossing the Unreal boundary must therefore make the degree-to-radian
    conversion visible in code.
    """

    value: float

    def __post_init__(self) -> None:
        value = float(self.value)
        if not math.isfinite(value):
            raise ValueError("yaw must be finite")
        object.__setattr__(self, "value", value)

    @classmethod
    def from_degrees(cls, degrees: float) -> YawRadians:
        """Convert a finite Unreal yaw in degrees to model-facing radians."""

        if not math.isfinite(float(degrees)):
            raise ValueError("yaw degrees must be finite")
        return cls(math.radians(float(degrees)))


def _planar(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 0 or array.shape[-1] != 2:
        raise ValueError(f"{name} must have shape (2,) or (..., 2)")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _rotation(yaw: YawRadians) -> NDArray[np.float64]:
    if not isinstance(yaw, YawRadians):
        raise TypeError("yaw must be YawRadians; convert Unreal degrees explicitly")
    cosine = math.cos(yaw.value)
    sine = math.sin(yaw.value)
    return np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64)


def local_vector_to_world(vector_local: ArrayLike, *, yaw: YawRadians) -> NDArray[np.float64]:
    """Rotate local planar vectors into Unreal world axes.

    Inputs may be one vector with shape ``(2,)`` or a batch with shape ``(..., 2)``.
    Vector units are preserved; for example, cm/s remains cm/s.
    """

    local = _planar(vector_local, name="vector_local")
    return local @ _rotation(yaw).T


def world_vector_to_local(vector_world: ArrayLike, *, yaw: YawRadians) -> NDArray[np.float64]:
    """Rotate world planar vectors into character-local axes."""

    world = _planar(vector_world, name="vector_world")
    return world @ _rotation(yaw)


def local_point_to_world(
    point_local: ArrayLike,
    *,
    origin_world: ArrayLike,
    yaw: YawRadians,
) -> NDArray[np.float64]:
    """Rotate local points and translate them by the character's world origin."""

    local = _planar(point_local, name="point_local")
    origin = _planar(origin_world, name="origin_world")
    return local_vector_to_world(local, yaw=yaw) + origin


def world_point_to_local(
    point_world: ArrayLike,
    *,
    origin_world: ArrayLike,
    yaw: YawRadians,
) -> NDArray[np.float64]:
    """Subtract the world origin and rotate world points into local axes."""

    world = _planar(point_world, name="point_world")
    origin = _planar(origin_world, name="origin_world")
    return world_vector_to_local(world - origin, yaw=yaw)
