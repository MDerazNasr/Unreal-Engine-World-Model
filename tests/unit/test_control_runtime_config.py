from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from motionworld.planning.config import load_cem_planner_config
from motionworld.protocol import load_control_runtime_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "control_runtime.yaml"


def _mutated_config(tmp_path: Path, mutate) -> Path:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(raw)
    result = tmp_path / "runtime.yaml"
    result.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return result


def test_runtime_contract_is_exactly_ten_hertz_and_fail_safe() -> None:
    config = load_control_runtime_config(CONFIG_PATH)
    assert config.control_frequency_hz == 10
    assert config.decision_interval_ms == 100
    assert config.deadline_ms == 100
    assert config.deadline_boundary == "exclusive"
    assert config.late_response_policy == "discard"
    assert config.cold_start_action_local_cm_s == (0.0, 0.0)
    assert config.hold_last_valid_action_for_consecutive_misses == 2
    assert config.safe_stop_on_consecutive_miss == 3


def test_runtime_contract_uses_fixed_slots_without_burst_catch_up() -> None:
    config = load_control_runtime_config(CONFIG_PATH)
    assert config.observation_time_source == "unreal_simulation_time"
    assert config.observation_epoch == "first_valid_post_reset_finalize"
    assert config.boundary_selection == "first_valid_finalize_at_or_after_slot_boundary"
    assert config.catch_up_policy == "latest_elapsed_slot_only_no_burst"
    assert config.sequence_policy == "increment_once_per_emitted_observation"
    assert config.first_sequence == 0
    assert (
        config.valid_action_application
        == "apply_immediately_and_hold_until_replaced_or_fallback"
    )


def test_runtime_and_planner_timing_contracts_agree() -> None:
    runtime = load_control_runtime_config(CONFIG_PATH)
    _, rollout, _, _ = load_cem_planner_config(
        REPOSITORY_ROOT / "configs" / "cem_planner.yaml"
    )
    assert rollout.plan_step_s == runtime.decision_interval_ms / 1000.0
    assert rollout.dynamics_substeps_per_plan_step == 3
    assert rollout.dynamics_dt_s == pytest.approx(1.0 / 30.0)


def test_frequency_and_interval_cannot_disagree(tmp_path: Path) -> None:
    path = _mutated_config(tmp_path, lambda raw: raw.update(control_frequency_hz=20))
    with pytest.raises(ValueError, match="frequency and decision interval disagree"):
        load_control_runtime_config(path)


def test_deadline_must_equal_one_control_interval(tmp_path: Path) -> None:
    def mutate(raw: dict[str, object]) -> None:
        raw["response_deadline"]["duration_ms"] = 101

    with pytest.raises(ValueError, match="deadline must equal"):
        load_control_runtime_config(_mutated_config(tmp_path, mutate))


def test_deadline_boundary_and_late_policy_fail_closed(tmp_path: Path) -> None:
    def mutate(raw: dict[str, object]) -> None:
        raw["response_deadline"]["boundary"] = "inclusive"

    with pytest.raises(ValueError, match="deadline boundary"):
        load_control_runtime_config(_mutated_config(tmp_path, mutate))


def test_safe_stop_must_immediately_follow_hold_allowance(tmp_path: Path) -> None:
    def mutate(raw: dict[str, object]) -> None:
        raw["fallback"]["safe_stop_on_consecutive_miss"] = 4

    with pytest.raises(ValueError, match="safe stop must follow immediately"):
        load_control_runtime_config(_mutated_config(tmp_path, mutate))


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    path = _mutated_config(tmp_path, lambda raw: raw.update(extra=True))
    with pytest.raises(ValueError, match="keys must be exactly"):
        load_control_runtime_config(path)


@pytest.mark.parametrize("invalid_sequence", [False, "0", 0.0])
def test_first_sequence_rejects_coercible_wrong_types(
    tmp_path: Path, invalid_sequence: object
) -> None:
    def mutate(raw: dict[str, object]) -> None:
        raw["observation_schedule"]["first_sequence"] = invalid_sequence

    with pytest.raises(ValueError, match="first_sequence must be a non-negative integer"):
        load_control_runtime_config(_mutated_config(tmp_path, mutate))


@pytest.mark.parametrize("invalid_zero", [False, "0"])
def test_cold_start_action_rejects_coercible_wrong_types(
    tmp_path: Path, invalid_zero: object
) -> None:
    def mutate(raw: dict[str, object]) -> None:
        raw["fallback"]["cold_start_action_local_cm_s"] = [invalid_zero, 0]

    with pytest.raises(ValueError, match="cold-start action x must be a finite number"):
        load_control_runtime_config(_mutated_config(tmp_path, mutate))
