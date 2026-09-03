"""Run inside Unreal Editor Python to apply, verify, or restore Gate-R2 settings."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import unreal

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from motionworld.control.gate_r2_manifest import load_gate_r2_manifest  # noqa: E402

MANIFEST_PATH = REPOSITORY_ROOT / "configs" / "gate_r2_live_manifest.json"


def _single_component(cdo, component_class, label: str):
    components = cdo.get_components_by_class(component_class)
    if len(components) != 1:
        raise RuntimeError(f"expected exactly one {label}; found {len(components)}")
    return components[0]


def _read(component, settings):
    return {name: component.get_editor_property(name) for name in settings}


def _write(component, settings):
    for name, value in settings.items():
        component.set_editor_property(name, value)


def main() -> None:
    manifest = load_gate_r2_manifest(MANIFEST_PATH, REPOSITORY_ROOT)
    mode = os.environ.get("MOTIONWORLD_GATE_R2_MODE", "verify")
    if mode not in {"apply", "verify", "restore"}:
        raise RuntimeError("MOTIONWORLD_GATE_R2_MODE must be apply, verify, or restore")
    asset = unreal.EditorAssetLibrary.load_asset(manifest.blueprint_asset)
    if asset is None:
        raise RuntimeError(f"could not load {manifest.blueprint_asset}")
    cdo = unreal.get_default_object(asset.generated_class())
    bridge = _single_component(cdo, unreal.MotionWorldBridgeComponent, "MotionWorld bridge")
    network = _single_component(
        cdo, unreal.MotionWorldNetworkControllerComponent, "MotionWorld network controller"
    )
    saved_dir = Path(unreal.Paths.project_saved_dir()) / "MotionWorld" / "GateR2"
    saved_dir.mkdir(parents=True, exist_ok=True)
    backup_path = saved_dir / "blueprint_settings_backup.json"

    if mode == "apply":
        if backup_path.exists():
            raise RuntimeError(f"refusing to overwrite existing backup: {backup_path}")
        backup = {
            "blueprint_asset": manifest.blueprint_asset,
            "bridge_settings": _read(bridge, manifest.bridge_settings),
            "network_settings": _read(network, manifest.network_settings),
        }
        backup_path.write_text(
            json.dumps(backup, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write(bridge, manifest.bridge_settings)
        _write(network, manifest.network_settings)
        unreal.KismetEditorUtilities.compile_blueprint(asset)
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError("failed to save configured Blueprint")
    elif mode == "restore":
        if not backup_path.is_file():
            raise RuntimeError(f"missing settings backup: {backup_path}")
        backup = json.loads(backup_path.read_text(encoding="utf-8"))
        if backup.get("blueprint_asset") != manifest.blueprint_asset:
            raise RuntimeError("backup Blueprint identity mismatch")
        _write(bridge, backup["bridge_settings"])
        _write(network, backup["network_settings"])
        unreal.KismetEditorUtilities.compile_blueprint(asset)
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError("failed to save restored Blueprint")
        backup_path.unlink()

    actual = {
        "bridge_settings": _read(bridge, manifest.bridge_settings),
        "network_settings": _read(network, manifest.network_settings),
    }
    expected = {
        "bridge_settings": dict(manifest.bridge_settings),
        "network_settings": dict(manifest.network_settings),
    }
    matches = actual == expected
    report = {
        "mode": mode,
        "manifest_sha256": manifest.canonical_sha256,
        "matches_gate_r2_manifest": matches,
        "actual": actual,
    }
    (saved_dir / "configuration_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if mode != "restore" and not matches:
        raise RuntimeError("Blueprint readback does not match the Gate-R2 manifest")
    unreal.log(f"MotionWorld Gate R2 configuration {mode}: {json.dumps(report, sort_keys=True)}")


main()
