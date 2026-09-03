"""Fail-closed loaders for the predeclared final-evaluation manifests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _map(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys must be exactly {sorted(expected)}")


def _list(value: object, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return value


def _int(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context} must be an integer")
    return value


def _number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{context} must be a finite number")
    return result


def _literal(value: object, expected: object, context: str) -> None:
    if value != expected:
        raise ValueError(f"{context} must be {expected!r}")


def _load(path: Path, schema_name: str, expected_keys: set[str]) -> dict[str, Any]:
    raw = _map(yaml.safe_load(path.read_text(encoding="utf-8")), "manifest")
    _keys(raw, expected_keys, "manifest")
    _literal(raw["schema_name"], schema_name, "schema_name")
    _literal(raw["schema_version"], 1, "schema_version")
    return raw


def _reject_key_recursively(value: object, forbidden: set[str]) -> None:
    if isinstance(value, dict):
        overlap = set(value) & forbidden
        if overlap:
            raise ValueError(f"sealed manifest contains forbidden metadata: {sorted(overlap)}")
        for child in value.values():
            _reject_key_recursively(child, forbidden)
    elif isinstance(value, list):
        for child in value:
            _reject_key_recursively(child, forbidden)


@dataclass(frozen=True, slots=True)
class FinalPredictionManifest:
    status: str
    episode_ids: tuple[int, ...]
    horizons_s: tuple[float, ...]
    metric_names: tuple[str, ...]
    bootstrap_seed: int
    bootstrap_resamples: int


@dataclass(frozen=True, slots=True)
class FinalControlManifest:
    status: str
    paired_seeds: tuple[int, ...]
    minimum_valid_pairs: int
    scenario_names: tuple[str, ...]
    primary_estimand: str
    agent_radius_cm: float
    agent_half_height_cm: float


def load_final_prediction_manifest(path: Path) -> FinalPredictionManifest:
    """Load the sealed prediction-test declaration without opening any episode data."""

    raw = _load(
        path,
        "motionworld_final_prediction_manifest",
        {
            "schema_name",
            "schema_version",
            "status",
            "purpose",
            "integrity",
            "episodes",
            "model_roles",
            "checkpoint_policy",
            "rollout",
            "metrics",
            "strata",
            "statistics",
            "interpretation",
        },
    )
    _literal(raw["status"], "frozen_draft_before_test_collection", "status")
    _literal(raw["purpose"], "final_prediction_only_not_controller_evaluation", "purpose")
    _reject_key_recursively(raw, {"raw_file", "raw_sha256"})

    integrity = _map(raw["integrity"], "integrity")
    _keys(
        integrity,
        {"reserved_episode_ids", "forbidden_uses", "raw_file_metadata_policy", "unseal_gate"},
        "integrity",
    )
    reserved = tuple(
        _int(v, "reserved episode id")
        for v in _list(integrity["reserved_episode_ids"], "reserved_episode_ids")
    )
    _literal(reserved, (5301, 5302), "reserved episode ids")
    forbidden_uses = set(_list(integrity["forbidden_uses"], "forbidden_uses"))
    required_forbidden = {
        "training",
        "validation",
        "checkpoint_selection",
        "controller_seed_selection",
        "scenario_tuning",
    }
    if forbidden_uses != required_forbidden:
        raise ValueError("prediction forbidden uses are incomplete")
    _literal(
        integrity["raw_file_metadata_policy"],
        "absent_until_r7_authorized_collection",
        "raw metadata policy",
    )
    _literal(integrity["unseal_gate"], "r7_final_freeze_complete", "unseal gate")

    episodes = _list(raw["episodes"], "episodes")
    episode_ids = []
    expected_episode_keys = {
        "episode_id",
        "split",
        "status",
        "motion_phase_duration_s",
        "intermediate_stop_duration_s",
        "final_stop_duration_s",
        "forward_speed_cm_s",
        "reverse_speed_cm_s",
        "lateral_speed_cm_s",
        "diagonal_component_speed_cm_s",
    }
    expected_schedules = {
        5301: (0.60, 0.40, 0.35, 155.0, 75.0, 100.0, 105.0),
        5302: (0.75, 0.18, 0.55, 90.0, 140.0, 150.0, 70.0),
    }
    for index, episode_value in enumerate(episodes):
        episode = _map(episode_value, f"episodes[{index}]")
        _keys(episode, expected_episode_keys, f"episodes[{index}]")
        episode_id = _int(episode["episode_id"], "episode_id")
        episode_ids.append(episode_id)
        _literal(episode["split"], "test", "episode split")
        _literal(episode["status"], "pending_uncollected", "episode status")
        schedule_keys = (
            "motion_phase_duration_s",
            "intermediate_stop_duration_s",
            "final_stop_duration_s",
            "forward_speed_cm_s",
            "reverse_speed_cm_s",
            "lateral_speed_cm_s",
            "diagonal_component_speed_cm_s",
        )
        for key in schedule_keys:
            if _number(episode[key], key) <= 0.0:
                raise ValueError(f"{key} must be positive")
        _literal(
            tuple(float(episode[key]) for key in schedule_keys),
            expected_schedules[episode_id],
            f"episode {episode_id} schedule",
        )
    _literal(tuple(episode_ids), reserved, "episode identities")

    roles = tuple(_list(raw["model_roles"], "model_roles"))
    _literal(
        roles,
        ("faithful_nominal", "residual_no_history_multistep", "residual_four_history_multistep"),
        "model roles",
    )
    checkpoint = _map(raw["checkpoint_policy"], "checkpoint_policy")
    _keys(
        checkpoint,
        {"residual_identity_source", "checkpoint_hashes"},
        "checkpoint_policy",
    )
    _literal(
        checkpoint["residual_identity_source"],
        "validation_only_fixed_final_step_selection",
        "residual identity source",
    )
    _literal(
        checkpoint["checkpoint_hashes"],
        "pending_r4_training_before_r7_unseal",
        "checkpoint hash status",
    )
    strata = _list(raw["strata"], "strata")
    expected_strata = (
        ("free_space", "predeclared_present"),
        ("near_contact", "predeclared_absent"),
        ("post_push", "predeclared_absent"),
        ("held_out_movement_setting", "predeclared_absent"),
    )
    actual_strata = []
    for index, stratum_value in enumerate(strata):
        stratum = _map(stratum_value, f"strata[{index}]")
        if stratum.get("status") == "predeclared_present":
            _keys(stratum, {"name", "status", "source_episode_ids"}, f"strata[{index}]")
            _literal(stratum["source_episode_ids"], [5301, 5302], "stratum sources")
        else:
            _keys(stratum, {"name", "status", "reason"}, f"strata[{index}]")
            if not isinstance(stratum["reason"], str) or not stratum["reason"]:
                raise ValueError("absent strata require a reason")
        actual_strata.append((stratum["name"], stratum["status"]))
    _literal(tuple(actual_strata), expected_strata, "prediction strata")
    rollout = _map(raw["rollout"], "rollout")
    _keys(
        rollout,
        {
            "mode",
            "horizons_s",
            "endpoint_rule",
            "action_source",
            "duration_source",
            "parameter_policy",
        },
        "rollout",
    )
    _literal(rollout["mode"], "recursive_no_teacher_forcing", "rollout mode")
    _literal(
        rollout["endpoint_rule"],
        "first_recorded_boundary_at_or_after_horizon",
        "endpoint rule",
    )
    _literal(rollout["action_source"], "recorded_causal_actions", "action source")
    _literal(rollout["duration_source"], "recorded_transition_dt", "duration source")
    _literal(
        rollout["parameter_policy"],
        "hold_rollout_start_snapshot",
        "parameter policy",
    )
    horizons = tuple(_number(v, "horizon") for v in _list(rollout["horizons_s"], "horizons_s"))
    _literal(horizons, (0.5, 1.0, 1.5), "prediction horizons")

    metrics = _list(raw["metrics"], "metrics")
    names = []
    expected_units = {
        "planar_position_error": "cm",
        "local_velocity_error": "cm_per_s",
        "facing_error": "deg",
        "angular_velocity_error": "deg_per_s",
    }
    for metric_value in metrics:
        metric = _map(metric_value, "metric")
        _keys(metric, {"name", "unit", "summaries"}, "metric")
        name = metric["name"]
        if name not in expected_units or metric["unit"] != expected_units[name]:
            raise ValueError("prediction metric name or unit drifted")
        _literal(metric["summaries"], ["median", "p95"], "metric summaries")
        names.append(name)
    if tuple(names) != tuple(expected_units):
        raise ValueError("prediction metrics must be complete and ordered")

    statistics = _map(raw["statistics"], "statistics")
    _keys(
        statistics,
        {"pairing_unit", "bootstrap_seed", "bootstrap_resamples", "confidence_level", "interval"},
        "statistics",
    )
    seed = _int(statistics["bootstrap_seed"], "bootstrap seed")
    resamples = _int(statistics["bootstrap_resamples"], "bootstrap resamples")
    _literal(seed, 20260905, "prediction bootstrap seed")
    _literal(statistics["pairing_unit"], "identical_episode_start_and_horizon", "pairing unit")
    _literal(statistics["interval"], "percentile_paired_bootstrap", "bootstrap interval")
    if resamples != 10000 or _number(statistics["confidence_level"], "confidence level") != 0.95:
        raise ValueError("prediction bootstrap contract drifted")

    interpretation = _map(raw["interpretation"], "prediction interpretation")
    _keys(
        interpretation,
        {"primary_metric", "positive", "negative", "unresolved"},
        "prediction interpretation",
    )
    _literal(
        interpretation["primary_metric"],
        "planar_position_error_p95_at_1.5_s",
        "prediction primary metric",
    )

    return FinalPredictionManifest(raw["status"], reserved, horizons, tuple(names), seed, resamples)


def load_final_control_manifest(path: Path) -> FinalControlManifest:
    """Load and cross-check the paired authoritative-Unreal evaluation declaration."""

    raw = _load(
        path,
        "motionworld_final_control_manifest",
        {
            "schema_name",
            "schema_version",
            "status",
            "purpose",
            "controllers",
            "identity",
            "geometry_and_reset",
            "common_target",
            "scenarios",
            "metrics",
            "primary_analysis",
            "validity",
            "interpretation",
        },
    )
    _literal(raw["status"], "frozen_draft_geometry_verified_headless", "status")
    _literal(raw["purpose"], "paired_authoritative_unreal_controller_evaluation", "purpose")

    controllers = _map(raw["controllers"], "controllers")
    _keys(
        controllers,
        {
            "primary_pair",
            "contextual_only",
            "contextual_required_scenarios",
            "fairness_rule",
        },
        "controllers",
    )
    _literal(controllers["primary_pair"], ["nominal_mpc", "residual_mpc"], "primary pair")
    _literal(controllers["contextual_only"], ["reactive"], "contextual controller")
    _literal(
        controllers["contextual_required_scenarios"],
        ["timed_gate"],
        "contextual controller scenarios",
    )

    identity = _map(raw["identity"], "identity")
    _keys(
        identity,
        {
            "prediction_episode_ids_forbidden",
            "paired_scenario_seeds",
            "controller_order_by_pair",
            "cem_randomness_rule",
        },
        "identity",
    )
    forbidden = {
        _int(v, "forbidden id")
        for v in _list(
            identity["prediction_episode_ids_forbidden"], "prediction_episode_ids_forbidden"
        )
    }
    _literal(forbidden, {5301, 5302}, "forbidden prediction identities")
    seeds = tuple(
        _int(v, "paired seed")
        for v in _list(identity["paired_scenario_seeds"], "paired_scenario_seeds")
    )
    if len(seeds) != 12 or len(set(seeds)) != 12 or forbidden.intersection(seeds):
        raise ValueError("control seeds must be twelve unique identities separate from prediction")
    orders = _list(identity["controller_order_by_pair"], "controller_order_by_pair")
    if len(orders) != len(seeds) or set(orders) != {"nominal_first", "residual_first"}:
        raise ValueError("controller order must be complete and counterbalanced")
    if orders.count("nominal_first") != orders.count("residual_first"):
        raise ValueError("controller order must be balanced")

    geometry = _map(raw["geometry_and_reset"], "geometry_and_reset")
    _keys(
        geometry,
        {"reset_pose", "equality_tolerance", "agent_capsule", "mismatch_policy"},
        "geometry_and_reset",
    )
    capsule = _map(geometry["agent_capsule"], "agent_capsule")
    _keys(capsule, {"radius_cm", "half_height_cm", "source"}, "agent_capsule")
    radius = _number(capsule["radius_cm"], "capsule radius")
    half_height = _number(capsule["half_height_cm"], "capsule half height")
    _literal(radius, 30.0, "verified capsule radius")
    _literal(half_height, 86.0, "verified capsule half height")
    _literal(
        capsule["source"],
        "headless_transient_sandbox_character_mover_query_2026_09_03",
        "capsule source",
    )

    target = _map(raw["common_target"], "common_target")
    _keys(target, {"frame", "position_cm", "desired_terminal_velocity_cm_per_s"}, "common_target")
    _literal(target["frame"], "reset_anchor_character_local_xy", "target frame")
    _literal(target["position_cm"], [700.0, 0.0], "common target position")
    _literal(
        target["desired_terminal_velocity_cm_per_s"],
        [0.0, 0.0],
        "terminal target velocity",
    )

    scenarios = _map(raw["scenarios"], "scenarios")
    expected_scenarios = ("timed_gate", "push_recovery", "held_out_setting", "ood_setting")
    _keys(scenarios, set(expected_scenarios), "scenarios")
    for name in expected_scenarios:
        scenario = _map(scenarios[name], name)
        scenario_seeds = tuple(
            _int(v, f"{name} seed") for v in _list(scenario["paired_seeds"], f"{name} paired_seeds")
        )
        if scenario_seeds != seeds:
            raise ValueError(f"{name} does not use the frozen paired seeds")
    timed_gate = _map(scenarios["timed_gate"], "timed_gate")
    _keys(timed_gate, {"paired_seeds", "timeout_s", "goal", "gate"}, "timed_gate")
    _literal(timed_gate["timeout_s"], 8.0, "timed-gate timeout")
    _literal(timed_gate["goal"], "cross_gate_plane_without_gate_collision", "timed-gate goal")
    gate = _map(timed_gate["gate"], "timed_gate gate")
    _keys(
        gate,
        {
            "origin_from_reset_cm",
            "motion_axis_reset_local",
            "crossing_plane_normal_reset_local",
            "half_extents_cm",
            "amplitude_cm",
            "period_s",
            "phase_offsets_rad",
        },
        "timed_gate gate",
    )
    _literal(gate["origin_from_reset_cm"], [600.0, 0.0, 0.0], "gate origin")
    _literal(gate["motion_axis_reset_local"], [0.0, 1.0, 0.0], "gate motion axis")
    _literal(
        gate["crossing_plane_normal_reset_local"],
        [1.0, 0.0, 0.0],
        "gate crossing normal",
    )
    _literal(gate["half_extents_cm"], [30.0, 150.0, 90.0], "gate half extents")
    _literal(gate["amplitude_cm"], 200.0, "gate amplitude")
    _literal(gate["period_s"], 4.0, "gate period")
    if len(_list(gate["phase_offsets_rad"], "phase offsets")) != len(seeds):
        raise ValueError("each timed-gate pair needs one frozen phase")
    push = _map(scenarios["push_recovery"], "push_recovery")
    _keys(
        push,
        {
            "paired_seeds",
            "timeout_s",
            "goal",
            "target_position_reset_local_cm",
            "perturbation",
            "recovery_definition",
        },
        "push_recovery",
    )
    _literal(push["timeout_s"], 6.0, "push timeout")
    _literal(push["target_position_reset_local_cm"], [500.0, 0.0], "push target")
    perturbation = _map(push["perturbation"], "perturbation")
    _keys(
        perturbation,
        {
            "type",
            "trigger_time_s",
            "declared_frame",
            "delta_reset_local_cm_per_s",
            "application_rule",
            "post_perturbation_observation_s",
        },
        "perturbation",
    )
    _literal(perturbation["type"], "one_tick_additive_world_velocity_not_force", "push type")
    _literal(
        perturbation["declared_frame"],
        "reset_anchor_character_local",
        "push frame",
    )
    _literal(
        perturbation["delta_reset_local_cm_per_s"],
        [0.0, 250.0, 0.0],
        "push velocity delta",
    )
    _literal(perturbation["trigger_time_s"], 1.5, "push trigger time")
    _literal(perturbation["post_perturbation_observation_s"], 4.5, "push observation time")

    for setting_name, value, relation in (
        ("held_out_setting", 650.0, "interpolated_between_observed_300_and_1000"),
        ("ood_setting", 1300.0, "above_observed_maximum_1000"),
    ):
        setting = _map(scenarios[setting_name], setting_name)
        _keys(
            setting,
            {
                "paired_seeds",
                "base_scenario",
                "changed_parameter",
                "value",
                "relation_to_training_support",
                "parameter_visibility",
            },
            setting_name,
        )
        _literal(setting["base_scenario"], "timed_gate", f"{setting_name} base scenario")
        _literal(
            setting["changed_parameter"],
            "deceleration_cm_per_s2",
            f"{setting_name} parameter",
        )
        _literal(setting["value"], value, f"{setting_name} value")
        _literal(setting["relation_to_training_support"], relation, f"{setting_name} relation")
        _literal(
            setting["parameter_visibility"],
            "causal_current_parameter_visible_to_nominal_and_residual",
            f"{setting_name} visibility",
        )

    metrics = _list(raw["metrics"], "metrics")
    metric_names = []
    expected_metric_units = {
        "success": "binary_episode_indicator",
        "collision_occurred": "binary_episode_indicator",
        "collision_count": "count_per_episode",
        "completion_time": "s_from_scenario_start_capped_at_timeout",
        "time_to_goal": "s_from_scenario_start_or_null_if_unsuccessful",
        "minimum_capsule_gate_clearance": "cm_signed_negative_means_penetration",
        "push_recovered": "binary_episode_indicator",
        "push_recovery_time": "s_after_kick_or_null_if_not_recovered",
        "predicted_realized_return_gap": "planner_cost_units",
        "selected_action_disagreement": "cm_per_s_l2",
        "end_to_end_latency": "ms_unreal_send_to_matching_receive",
        "deadline_miss_count": "count_per_episode",
        "fallback_action_count": "count_per_episode",
    }
    for metric_value in metrics:
        metric = _map(metric_value, "metric")
        _keys(metric, {"name", "unit"}, "control metric")
        if metric["name"] not in expected_metric_units:
            raise ValueError("unknown control metric")
        _literal(metric["unit"], expected_metric_units[metric["name"]], "control metric unit")
        metric_names.append(metric["name"])
    required_metrics = set(expected_metric_units)
    if set(metric_names) != required_metrics or len(metric_names) != len(required_metrics):
        raise ValueError("control metrics must be complete and unique")

    primary = _map(raw["primary_analysis"], "primary_analysis")
    _keys(
        primary,
        {
            "estimand",
            "effect_unit",
            "minimum_effect",
            "bootstrap",
            "safety_guardrail",
            "runtime_guardrail",
        },
        "primary_analysis",
    )
    estimand = primary["estimand"]
    _literal(
        estimand,
        "mean_paired_timed_gate_success_difference_residual_minus_nominal",
        "primary estimand",
    )
    _literal(
        primary["effect_unit"],
        "proportion_residual_minus_nominal_where_0.10_equals_10_percentage_points",
        "primary effect unit",
    )
    _literal(primary["minimum_effect"], 0.10, "minimum effect")
    bootstrap = _map(primary["bootstrap"], "control bootstrap")
    _keys(
        bootstrap,
        {"resampling_unit", "seed", "resamples", "confidence_level", "interval"},
        "control bootstrap",
    )
    if _int(bootstrap["resamples"], "bootstrap resamples") != 10000:
        raise ValueError("control bootstrap must use 10000 resamples")

    validity = _map(raw["validity"], "validity")
    _keys(
        validity,
        {
            "minimum_valid_pairs_per_scenario",
            "planned_pairs_per_scenario",
            "infrastructure_invalid_reasons",
            "valid_controller_failures",
            "retry_policy",
            "insufficient_pairs_policy",
        },
        "validity",
    )
    minimum = _int(validity["minimum_valid_pairs_per_scenario"], "minimum valid pairs")
    planned = _int(validity["planned_pairs_per_scenario"], "planned pairs")
    if planned != len(seeds) or minimum != 10 or minimum > planned:
        raise ValueError("valid-pair counts drifted")
    controller_failures = set(_list(validity["valid_controller_failures"], "valid failures"))
    if not {"collision", "timeout", "missed_deadline", "safe_fallback"}.issubset(
        controller_failures
    ):
        raise ValueError("controller failures must not be excluded as invalid infrastructure")

    interpretation = _map(raw["interpretation"], "interpretation")
    _keys(interpretation, {"positive", "negative", "unresolved"}, "interpretation")
    if not all(
        isinstance(interpretation[key], str) and interpretation[key] for key in interpretation
    ):
        raise ValueError("all three result interpretations must be explicit")

    return FinalControlManifest(
        raw["status"], seeds, minimum, expected_scenarios, estimand, radius, half_height
    )
