import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "motionworld-matplotlib"),
)

from scripts.evaluate_recursive_residual_models import _summarize  # noqa: E402


def _row(horizon: float, *, parameter_change_count: int) -> dict[str, object]:
    return {
        "requested_horizon_s": horizon,
        "parameter_change_count": parameter_change_count,
        "planar_position_error_cm": 1.0,
        "planar_velocity_error_cm_s": 2.0,
        "yaw_error_deg": 3.0,
        "angular_velocity_yaw_error_deg_s": 4.0,
    }


def test_summary_represents_empty_stable_stratum_without_failing() -> None:
    rows = [
        _row(0.5, parameter_change_count=0),
        _row(0.5, parameter_change_count=1),
        _row(1.0, parameter_change_count=1),
        _row(1.5, parameter_change_count=2),
    ]

    summary = _summarize(rows)

    assert summary["0.5"]["parameter_stable"]["window_count"] == 1
    assert summary["1.0"]["parameter_stable"]["window_count"] == 0
    assert summary["1.0"]["parameter_stable"]["metrics"][
        "planar_position_error_cm"
    ] is None
