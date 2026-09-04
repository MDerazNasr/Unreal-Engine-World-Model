"""Read-only preflight checks for the MotionWorld interview demonstration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

Status = Literal["pass", "warn", "fail"]


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    schema_name: str
    schema_version: int
    checks: tuple[PreflightCheck, ...]
    live_launch_ready: bool
    fallback_ready: bool
    claim_boundary: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "checks": [asdict(check) for check in self.checks],
            "live_launch_ready": self.live_launch_ready,
            "fallback_ready": self.fallback_ready,
            "claim_boundary": self.claim_boundary,
        }


_FALLBACK_FILES = (
    "artifacts/interview/architecture.svg",
    "artifacts/residual/recursive_001/recursive_comparison.png",
    "artifacts/planning/offplan_001/offline_paired_planner.png",
    "artifacts/planning/runtime_001/README.md",
)
_D5_SUMMARY = "artifacts/demo/d5_nominal_mpc_live/summary.json"
_D6_MANIFEST = "configs/d6_residual_overlay_manifest.json"
_D6_SUMMARY = "artifacts/demo/d6_residual_overlay_live/summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {relative}") from exc
    return path


def _load_mapping(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping in {path.name}")
    return value


def _check_fallback(root: Path) -> PreflightCheck:
    missing = [relative for relative in _FALLBACK_FILES if not _inside(root, relative).is_file()]
    if missing:
        return PreflightCheck("offline_fallback_assets", "fail", f"missing: {', '.join(missing)}")
    return PreflightCheck(
        "offline_fallback_assets",
        "pass",
        f"{len(_FALLBACK_FILES)} preserved architecture/result artifacts are present",
    )


def _check_d5_summary(root: Path) -> PreflightCheck:
    path = _inside(root, _D5_SUMMARY)
    try:
        value = _load_mapping(path)
        accepted = value["identity_reconciliation"]["accepted_actions_logged"]
        valid = (
            value["schema_name"] == "motionworld_d5_nominal_mpc_live_summary"
            and accepted >= 100
            and value["deadline"][
                "all_accepted_actions_logged_current_identity_and_before_deadline"
            ]
            is True
            and value["authoritative_motion"]["pawn_displacement_observed"] is True
            and value["claim_boundary"]["final_prediction_episodes_opened"] == 0
        )
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return PreflightCheck("accepted_live_nominal_evidence", "fail", str(exc))
    if not valid:
        return PreflightCheck(
            "accepted_live_nominal_evidence", "fail", "summary does not preserve acceptance bounds"
        )
    return PreflightCheck(
        "accepted_live_nominal_evidence",
        "pass",
        f"{accepted} accepted live actions; deadlines and authoritative motion verified",
    )


def _check_hash_reference(root: Path, entry: Any, label: str) -> None:
    if not isinstance(entry, dict) or set(entry) < {"path", "sha256"}:
        raise ValueError(f"{label} path/hash reference is incomplete")
    path = _inside(root, entry["path"])
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {entry['path']}")
    if _sha256(path) != entry["sha256"]:
        raise ValueError(f"{label} hash mismatch: {entry['path']}")


def _check_learned_overlay(root: Path) -> PreflightCheck:
    try:
        overlay = _load_mapping(_inside(root, "configs/live_residual_overlay_demo.yaml"))
        if overlay.get("status") != "matched_prediction_overlay_nominal_control_only":
            raise ValueError("learned overlay claim boundary changed")
        for key in ("nominal_planner", "checkpoint", "normalization", "training_config"):
            _check_hash_reference(root, overlay.get(key), key)
        _check_hash_reference(root, overlay.get("dataset_manifest"), "dataset_manifest")

        manifest = _load_mapping(_inside(root, _D6_MANIFEST))
        if manifest.get("schema_name") != "motionworld_d6_residual_overlay_manifest":
            raise ValueError("unexpected D6 manifest schema")
        if manifest["network_settings"]["controller_mode"] != "nominal_mpc":
            raise ValueError("learned overlay must not own control")
        if manifest["acceptance"]["overlay_is_prediction_only"] is not True:
            raise ValueError("learned overlay is not marked prediction-only")
        service = manifest["service"]
        for path_key, hash_key, label in (
            ("config_path", "sha256", "service config"),
            ("planner_config_path", "planner_sha256", "overlay config"),
        ):
            _check_hash_reference(
                root,
                {"path": service[path_key], "sha256": service[hash_key]},
                label,
            )
        summary = _load_mapping(_inside(root, _D6_SUMMARY))
        runtime = summary["live_runtime"]
        configuration = summary["configuration"]
        if (
            summary["schema_name"] != "motionworld_d6_residual_overlay_live_summary"
            or summary["identity"]["episode_id"]
            != manifest["acceptance"]["expected_episode_id"]
            or runtime["accepted_actions_logged"] < 100
            or runtime["accepted_actions_current_and_before_100_ms_deadline"] is not True
            or configuration["nominal_mpc_is_only_action_owner"] is not True
            or configuration["checkpoint_sha256"] != overlay["checkpoint"]["sha256"]
            or configuration["overlay_config_sha256"] != service["planner_sha256"]
            or summary["claim_boundary"]["residual_controls_character"] is not False
            or summary["claim_boundary"]["final_prediction_episodes_opened"] != 0
        ):
            raise ValueError("accepted D6 live summary does not preserve claim boundaries")
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return PreflightCheck("learned_overlay_configuration", "fail", str(exc))
    return PreflightCheck(
        "learned_overlay_configuration",
        "pass",
        "accepted D6 live evidence and all lineage hashes pass; nominal MPC remains action owner",
    )


def _check_external(path: Path | None, *, name: str, suffix: str | None = None) -> PreflightCheck:
    if path is None:
        return PreflightCheck(name, "warn", "not supplied; set the documented environment variable")
    if not path.is_file():
        return PreflightCheck(name, "fail", f"not a file: {path}")
    if suffix is not None and path.suffix != suffix:
        return PreflightCheck(name, "fail", f"expected a {suffix} file: {path}")
    return PreflightCheck(name, "pass", str(path))


def run_preflight(
    root: Path,
    *,
    unreal_editor: Path | None = None,
    unreal_project: Path | None = None,
    require_unreal: bool = False,
) -> PreflightReport:
    """Validate immutable inputs without opening Unreal, binding ports, or reading raw episodes."""

    root = root.resolve()
    checks = [
        _check_fallback(root),
        _check_d5_summary(root),
        _check_learned_overlay(root),
        _check_external(unreal_editor, name="unreal_editor"),
        _check_external(unreal_project, name="unreal_project", suffix=".uproject"),
    ]
    repository_checks_pass = all(check.status == "pass" for check in checks[:3])
    unreal_checks_pass = all(check.status == "pass" for check in checks[3:])
    if require_unreal and not unreal_checks_pass:
        checks.append(
            PreflightCheck(
                "required_live_environment",
                "fail",
                "both Unreal editor command and project are required for a live launch",
            )
        )
    fallback_ready = checks[0].status == "pass" and checks[1].status == "pass"
    return PreflightReport(
        schema_name="motionworld_interview_demo_preflight",
        schema_version=1,
        checks=tuple(checks),
        live_launch_ready=repository_checks_pass and unreal_checks_pass,
        fallback_ready=fallback_ready,
        claim_boundary=(
            "Preflight validates files, lineage, and launch prerequisites only; it does not prove "
            "that a new live run was accepted or that residual control outperforms nominal control."
        ),
    )
