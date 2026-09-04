from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from motionworld.control.live_mpc_config import load_live_nominal_mpc_config

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/live_nominal_mpc_demo.yaml"


def test_live_nominal_mpc_config_freezes_truthful_demo_budget() -> None:
    config = load_live_nominal_mpc_config(CONFIG, ROOT)

    assert config.problem_template.cem.num_candidates == 64
    assert config.problem_template.cem.num_iterations == 2
    assert config.preview_iteration_winners == 2
    assert config.problem_template.rollout.plan_step_s == 0.1
    assert config.problem_template.rollout.dynamics_substeps_per_plan_step == 1
    assert config.problem_template.weights.collision == 0.0
    assert config.problem_template.weights.clearance_per_cm2 == 0.0
    assert config.problem_template.weights.action_second_difference_per_cm2_s2 == 0.0


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("optimizer", "num_candidates", 128),
        ("weights", "collision", 1.0),
        ("weights", "clearance_per_cm2", 1.0),
        ("weights", "action_second_difference_per_cm2_s2", 1.0),
        ("rollout", "dynamics_substeps_per_plan_step", 3),
        ("budget_reference", "research_quality_gate_passed", True),
        ("budget_reference", "source_sha256", "0" * 64),
    ],
)
def test_live_nominal_mpc_config_rejects_drift(
    tmp_path: Path, section: str, field: str, value: object
) -> None:
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    changed = copy.deepcopy(raw)
    changed[section][field] = value
    path = tmp_path / "live.yaml"
    path.write_text(yaml.safe_dump(changed), encoding="utf-8")

    with pytest.raises(ValueError):
        load_live_nominal_mpc_config(path, ROOT)
