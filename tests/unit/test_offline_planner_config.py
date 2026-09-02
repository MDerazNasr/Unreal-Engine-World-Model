from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.run_offline_paired_planner import _load_cem_config, _load_problem_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _mutated_problem_config(tmp_path: Path, **changes: object) -> Path:
    source = REPOSITORY_ROOT / "configs" / "offline_planner.yaml"
    value = yaml.safe_load(source.read_text(encoding="utf-8"))
    value.update(changes)
    result = tmp_path / "problem.yaml"
    result.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return result


def test_frozen_offline_and_cem_configs_form_one_exact_horizon() -> None:
    problem, geometry, weights = _load_problem_config(
        REPOSITORY_ROOT / "configs" / "offline_planner.yaml"
    )
    cem, rollout, seed, horizon_s = _load_cem_config(
        REPOSITORY_ROOT / "configs" / "cem_planner.yaml"
    )
    assert problem["source_validation_episode_id"] == 5202
    assert geometry.agent_radius_cm == 42.0
    assert weights.collision == 10_000.0
    assert cem.num_plan_steps == 15
    assert rollout.dynamics_substeps_per_plan_step == 3
    assert cem.num_plan_steps * rollout.plan_step_s == pytest.approx(horizon_s)
    assert seed == 20_260_903


@pytest.mark.parametrize(
    ("field", "invalid", "message"),
    [
        ("source_validation_episode_id", True, "non-negative integer"),
        ("source_transition_index", "0", "non-negative integer"),
        ("initial_scenario_time_s", float("nan"), "finite non-negative number"),
        ("claim_boundary", "   ", "non-empty string"),
    ],
)
def test_problem_config_rejects_ambiguous_or_nonfinite_values(
    tmp_path: Path,
    field: str,
    invalid: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _load_problem_config(_mutated_problem_config(tmp_path, **{field: invalid}))
