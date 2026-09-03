from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml

from motionworld.dynamics.coordinates import YawRadians
from motionworld.dynamics.nominal_episode import current_snapshot_nominal_inputs
from motionworld.dynamics.smooth_walking_nominal import (
    SmoothWalkingObservableState,
    smooth_walking_nominal_step,
)
from motionworld.models.multistep_training import (
    RecursiveTrainingWindow,
    _nominal_step,
    _tensor_state,
    build_recursive_training_windows,
    discounted_recursive_loss,
    load_multistep_training_config,
    recursive_window_loss,
    train_multistep_residual_model,
    window_masks,
)
from motionworld.models.residual_contract import ResidualCorrection, compose_residual
from motionworld.models.residual_dataset import build_residual_examples
from motionworld.models.residual_mlp import ResidualMLP
from motionworld.models.residual_normalization import fit_residual_normalization
from tests.unit.test_residual_dataset import _episode

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "residual_multistep_training.yaml"


def _multistep_episode(**kwargs):
    episode = _episode(**kwargs)
    for transition in episode.transitions:
        transition["applied_action"]["velocity_local_planar_cm_per_s"] = [100.0, 0.0, 0.0]
    return episode


def test_frozen_multistep_contract_matches_planner_horizon() -> None:
    config = load_multistep_training_config(CONFIG_PATH)
    assert config.horizon_s == 1.5
    assert config.supervision_interval_s == 0.1
    assert config.supervision_count == 15
    assert config.discount_gamma == 0.9
    assert config.huber_beta == 1.0
    assert config.residual_magnitude_weight == 0.01
    assert config.seed == 20_260_904


def test_config_rejects_changed_one_step_baseline_hash(tmp_path: Path) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["immutable_one_step_baselines"]["no_history_checkpoint_sha256"] = "0" * 64
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint hashes changed"):
        load_multistep_training_config(path)


def test_config_rejects_changed_dataset_manifest_hash(tmp_path: Path) -> None:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw["source_dataset_manifest_sha256"] = "0" * 64
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="dataset manifest hash"):
        load_multistep_training_config(path)


def test_two_step_discounted_loss_matches_hand_calculation() -> None:
    errors = torch.zeros((1, 2, 6))
    errors[0, 0, 0] = 2.0
    errors[0, 1, 0] = 1.0
    residuals = torch.ones((1, 2, 6))
    valid = torch.tensor([[True, True]])
    weights = torch.tensor([[1.0, 0.9]])

    total, state, magnitude = discounted_recursive_loss(
        errors,
        residuals,
        valid,
        weights,
        huber_beta=1.0,
        residual_magnitude_weight=0.01,
    )

    expected_state = ((1.5 / 6.0) + 0.9 * (0.5 / 6.0)) / 1.9
    assert float(state) == pytest.approx(expected_state)
    assert float(magnitude) == pytest.approx(1.0)
    assert float(total) == pytest.approx(expected_state + 0.01)


def test_two_step_residual_composition_matches_hand_calculation() -> None:
    state = SmoothWalkingObservableState(
        position_world_cm=np.zeros(3),
        velocity_world_cm_s=np.zeros(3),
        facing_yaw_rad=0.0,
        angular_velocity_yaw_deg_s=0.0,
        simulation_time_s=0.1,
    )
    correction = ResidualCorrection(
        position_local_cm=np.asarray([1.0, 0.0]),
        velocity_local_cm_s=np.zeros(2),
        yaw_rad=0.0,
        angular_velocity_yaw_rad_s=0.0,
    )

    first = compose_residual(state, correction, reference_yaw=YawRadians(0.0))
    second_nominal = SmoothWalkingObservableState(
        position_world_cm=first.position_world_cm,
        velocity_world_cm_s=first.velocity_world_cm_s,
        facing_yaw_rad=first.facing_yaw_rad,
        angular_velocity_yaw_deg_s=first.angular_velocity_yaw_deg_s,
        simulation_time_s=0.2,
    )
    second = compose_residual(
        second_nominal, correction, reference_yaw=YawRadians(first.facing_yaw_rad)
    )

    np.testing.assert_array_equal(first.position_world_cm, [1.0, 0.0, 0.0])
    np.testing.assert_array_equal(second.position_world_cm, [2.0, 0.0, 0.0])


def test_window_masks_distinguish_padding_from_supervision() -> None:
    first = RecursiveTrainingWindow(
        episode_id=1,
        start_transition_sequence=0,
        transitions=({}, {}, {}),
        initial_history_features=(),
        supervision_weights=np.asarray([0.0, 1.0, 0.9]),
    )
    second = RecursiveTrainingWindow(
        episode_id=2,
        start_transition_sequence=4,
        transitions=({}, {}),
        initial_history_features=(),
        supervision_weights=np.asarray([0.0, 1.0]),
    )
    valid, weights = window_masks((first, second))

    assert valid.tolist() == [[True, True, True], [True, True, False]]
    assert weights.tolist() == [[0.0, 1.0, pytest.approx(0.9)], [0.0, 1.0, 0.0]]


def test_loss_rejects_supervision_on_padded_step() -> None:
    values = torch.zeros((1, 2, 6))
    with pytest.raises(ValueError, match="valid-step-only"):
        discounted_recursive_loss(
            values,
            values,
            torch.tensor([[True, False]]),
            torch.tensor([[1.0, 1.0]]),
            huber_beta=1.0,
            residual_magnitude_weight=0.01,
        )


def test_window_builder_rejects_incomplete_episode_tails() -> None:
    config = load_multistep_training_config(CONFIG_PATH)
    windows = build_recursive_training_windows(
        (_episode(count=100),), history_length=1, config=config
    )

    assert len(windows) == 26
    assert windows[0].start_transition_sequence == 0
    assert windows[-1].start_transition_sequence == 25
    assert all(len(window.transitions) == 75 for window in windows)
    assert all(np.count_nonzero(window.supervision_weights) == 15 for window in windows)


def test_four_history_window_has_real_prefix_but_no_incomplete_prefix() -> None:
    config = load_multistep_training_config(CONFIG_PATH)
    windows = build_recursive_training_windows(
        (_episode(count=100),), history_length=4, config=config
    )

    assert len(windows) == 23
    assert windows[0].start_transition_sequence == 3
    assert len(windows[0].initial_history_features) == 3
    assert all(feature.shape == (28,) for feature in windows[0].initial_history_features)


def test_differentiable_nominal_step_matches_scalar_oracle() -> None:
    transition = _multistep_episode(count=1).transitions[0]
    state, parameters, maximum_speed = _tensor_state(transition)
    action = torch.tensor(
        transition["applied_action"]["velocity_local_planar_cm_per_s"][:2]
    )
    actual_inputs = current_snapshot_nominal_inputs(transition)
    expected = smooth_walking_nominal_step(
        actual_inputs.observable,
        actual_inputs.internal,
        actual_inputs.action,
        parameters=actual_inputs.parameters,
        dt_s=actual_inputs.dt_s,
    )

    result, features = _nominal_step(
        state, action, torch.tensor(actual_inputs.dt_s), parameters, maximum_speed
    )

    np.testing.assert_allclose(
        result["position"].detach().numpy(), expected.observable_next.position_world_cm, atol=1e-5
    )
    np.testing.assert_allclose(
        result["velocity"].detach().numpy(), expected.observable_next.velocity_world_cm_s, atol=1e-5
    )
    assert float(result["facing"]) == pytest.approx(
        expected.observable_next.facing_yaw_rad, abs=1e-5
    )
    np.testing.assert_allclose(
        result["spring_velocity"].detach().numpy(),
        expected.internal_next.velocity.spring_velocity_world_cm_s,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        result["spring_acceleration"].detach().numpy(),
        expected.internal_next.velocity.spring_acceleration_world_cm_s2,
        atol=1e-5,
    )
    np.testing.assert_allclose(
        result["intermediate_velocity"].detach().numpy(),
        expected.internal_next.velocity.intermediate_velocity_world_cm_s,
        atol=1e-5,
    )
    assert float(result["intermediate_facing"]) == pytest.approx(
        expected.internal_next.facing.intermediate_facing_yaw_rad, abs=1e-5
    )
    assert float(result["intermediate_yaw_rate"]) == pytest.approx(
        expected.internal_next.facing.intermediate_angular_velocity_yaw_rad_s,
        abs=1e-5,
    )
    assert features.shape == (28,)


@pytest.mark.parametrize("history_length", [1, 4])
def test_recursive_window_loss_backpropagates_without_observed_reseeding(
    history_length: int,
) -> None:
    episode = _multistep_episode(count=100, position_error_index=40)
    examples = build_residual_examples(episode, history_length=history_length)
    normalization = fit_residual_normalization(
        examples,
        history_length=history_length,
        expected_train_episode_ids=(episode.episode_id,),
    )
    config = load_multistep_training_config(CONFIG_PATH)
    window = build_recursive_training_windows(
        (episode,), history_length=history_length, config=config
    )[0]
    model = ResidualMLP(normalization.feature_width, hidden_widths=(8,))

    total, state_loss, residual_loss = recursive_window_loss(
        model,
        normalization,
        window,
        history_length=history_length,
        config=config,
    )
    total.backward()

    assert torch.isfinite(total)
    assert float(state_loss.detach()) > 0.0
    assert float(residual_loss.detach()) == 0.0
    assert model.output.bias.grad is not None
    assert torch.isfinite(model.output.bias.grad).all()
    assert torch.any(model.output.bias.grad != 0.0)


def test_multistep_training_is_seed_reproducible() -> None:
    episode = _multistep_episode(count=80, position_error_index=40)
    examples = build_residual_examples(episode, history_length=1)
    normalization = fit_residual_normalization(
        examples,
        history_length=1,
        expected_train_episode_ids=(episode.episode_id,),
    )
    config = replace(
        load_multistep_training_config(CONFIG_PATH),
        optimizer_steps=2,
        batch_size=1,
        trace_interval_steps=1,
    )
    windows = build_recursive_training_windows(
        (episode,), history_length=1, config=config
    )

    first = train_multistep_residual_model(
        windows, normalization, history_length=1, config=config, hidden_widths=(8,)
    )
    second = train_multistep_residual_model(
        windows, normalization, history_length=1, config=config, hidden_widths=(8,)
    )

    assert first.trace == second.trace
    assert all(
        torch.equal(first.model.state_dict()[name], second.model.state_dict()[name])
        for name in first.model.state_dict()
    )
