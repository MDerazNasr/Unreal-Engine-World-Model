"""Known input preparation performed before Smooth Walking's spring update."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True, slots=True)
class PreparedVelocityInput:
    """Post-clamp desired velocity consumed by ``GenerateWalkMove``."""

    desired_velocity_world_cm_s: NDArray[np.float64]
    was_clamped: bool


def prepare_velocity_input(
    requested_velocity_world_cm_s: ArrayLike,
    *,
    effective_max_speed_cm_s: float,
) -> PreparedVelocityInput:
    """Reproduce SimpleWalkingMode's velocity-input max-size clamp.

    The effective limit is ``MaxSpeedOverride`` when non-negative, otherwise the
    active ``UCommonLegacyMovementSettings::MaxSpeed``.  The caller must provide
    that observed value; this function never estimates it from outcomes.
    """

    requested = np.asarray(requested_velocity_world_cm_s, dtype=np.float64)
    if requested.shape != (3,):
        raise ValueError("requested_velocity_world_cm_s must have shape (3,)")
    if not np.isfinite(requested).all():
        raise ValueError("requested_velocity_world_cm_s must contain only finite values")
    maximum_speed = float(effective_max_speed_cm_s)
    if not math.isfinite(maximum_speed) or maximum_speed < 0.0:
        raise ValueError("effective_max_speed_cm_s must be finite and non-negative")

    speed = float(np.linalg.norm(requested))
    if speed > maximum_speed:
        if maximum_speed == 0.0:
            prepared = np.zeros(3, dtype=np.float64)
        else:
            prepared = requested * (maximum_speed / speed)
        return PreparedVelocityInput(prepared, was_clamped=True)
    return PreparedVelocityInput(requested.copy(), was_clamped=False)
