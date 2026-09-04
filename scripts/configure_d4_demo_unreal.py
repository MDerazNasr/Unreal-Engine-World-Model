"""Run inside Unreal Editor Python to apply, verify, or restore D4 demo settings."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import unreal

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "configs" / "d4_branch_preview_manifest.json"


def _load_manifest_function():
    module_path = REPOSITORY_ROOT / "motionworld/control/demo_branch_manifest.py"
    spec = importlib.util.spec_from_file_location("motionworld_demo_branch_manifest", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load manifest module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_demo_branch_manifest


def _single_component(blueprint, component_class, label: str):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    components = []
    for handle in handles:
        data = library.get_data(handle)
        component = library.get_object_for_blueprint(data, blueprint)
        if isinstance(component, component_class):
            components.append(component)
    if len(components) != 1:
        raise RuntimeError(f"expected exactly one {label}; found {len(components)}")
    return components[0]


def _read(component, settings):
    return {name: component.get_editor_property(name) for name in settings}


def _write(component, settings):
    for name, value in settings.items():
        component.set_editor_property(name, value)


def _require_exact(actual, expected, context: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{context} readback mismatch: expected {expected}, got {actual}")


def _compile_and_save(asset, context: str) -> None:
    if not unreal.BlueprintEditorLibrary.compile_blueprint(asset):
        raise RuntimeError(f"{context} Blueprint did not compile cleanly")
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f"failed to save {context} Blueprint")


def main() -> None:
    manifest = _load_manifest_function()(MANIFEST_PATH, REPOSITORY_ROOT)
    mode = os.environ.get("MOTIONWORLD_D4_DEMO_MODE", "verify")
    if mode not in {"apply", "verify", "restore"}:
        raise RuntimeError("MOTIONWORLD_D4_DEMO_MODE must be apply, verify, or restore")
    asset = unreal.EditorAssetLibrary.load_asset(manifest.blueprint_asset)
    if asset is None:
        raise RuntimeError(f"could not load {manifest.blueprint_asset}")
    bridge = _single_component(asset, unreal.MotionWorldBridgeComponent, "MotionWorld bridge")
    network = _single_component(
        asset, unreal.MotionWorldNetworkControllerComponent, "MotionWorld network controller"
    )
    saved_dir = Path(unreal.Paths.project_saved_dir()) / "MotionWorld" / "D4BranchPreview"
    saved_dir.mkdir(parents=True, exist_ok=True)
    backup_path = saved_dir / "blueprint_settings_backup.json"
    expected = {
        "bridge_settings": dict(manifest.bridge_settings),
        "network_settings": dict(manifest.network_settings),
    }

    if mode == "apply":
        if backup_path.exists():
            raise RuntimeError(f"refusing to overwrite existing D4 backup: {backup_path}")
        backup = {
            "schema_name": "motionworld_d4_blueprint_settings_backup",
            "schema_version": 1,
            "manifest_sha256": manifest.canonical_sha256,
            "blueprint_asset": manifest.blueprint_asset,
            "bridge_settings": _read(bridge, manifest.bridge_settings),
            "network_settings": _read(network, manifest.network_settings),
        }
        backup_path.write_text(
            json.dumps(backup, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _write(bridge, manifest.bridge_settings)
        _write(network, manifest.network_settings)
        _require_exact(
            {
                "bridge_settings": _read(bridge, manifest.bridge_settings),
                "network_settings": _read(network, manifest.network_settings),
            },
            expected,
            "D4 apply",
        )
        _compile_and_save(asset, "configured D4")
    elif mode == "restore":
        if not backup_path.is_file():
            raise RuntimeError(f"missing D4 settings backup: {backup_path}")
        backup = json.loads(backup_path.read_text(encoding="utf-8"))
        required_backup_keys = {
            "schema_name",
            "schema_version",
            "manifest_sha256",
            "blueprint_asset",
            "bridge_settings",
            "network_settings",
        }
        if set(backup) != required_backup_keys:
            raise RuntimeError("D4 backup keys are not exact")
        if backup["schema_name"] != "motionworld_d4_blueprint_settings_backup":
            raise RuntimeError("D4 backup schema name mismatch")
        if backup["schema_version"] != 1:
            raise RuntimeError("D4 backup schema version mismatch")
        if backup["manifest_sha256"] != manifest.canonical_sha256:
            raise RuntimeError("D4 backup manifest identity mismatch")
        if backup["blueprint_asset"] != manifest.blueprint_asset:
            raise RuntimeError("D4 backup Blueprint identity mismatch")
        if set(backup["bridge_settings"]) != set(manifest.bridge_settings):
            raise RuntimeError("D4 backup bridge keys mismatch")
        if set(backup["network_settings"]) != set(manifest.network_settings):
            raise RuntimeError("D4 backup network keys mismatch")
        restored = {
            "bridge_settings": backup["bridge_settings"],
            "network_settings": backup["network_settings"],
        }
        _write(bridge, restored["bridge_settings"])
        _write(network, restored["network_settings"])
        _require_exact(
            {
                "bridge_settings": _read(bridge, manifest.bridge_settings),
                "network_settings": _read(network, manifest.network_settings),
            },
            restored,
            "D4 restore",
        )
        _compile_and_save(asset, "restored D4")
        _require_exact(
            {
                "bridge_settings": _read(bridge, manifest.bridge_settings),
                "network_settings": _read(network, manifest.network_settings),
            },
            restored,
            "saved D4 restore",
        )
        backup_path.unlink()

    actual = {
        "bridge_settings": _read(bridge, manifest.bridge_settings),
        "network_settings": _read(network, manifest.network_settings),
    }
    matches = actual == expected
    report = {
        "mode": mode,
        "manifest_sha256": manifest.canonical_sha256,
        "service_config": str(manifest.service_config_path.relative_to(REPOSITORY_ROOT)),
        "matches_d4_manifest": matches,
        "actual": actual,
    }
    (saved_dir / "configuration_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if mode != "restore" and not matches:
        raise RuntimeError("Blueprint readback does not match the D4 manifest")
    unreal.log(f"MotionWorld D4 configuration {mode}: {json.dumps(report, sort_keys=True)}")


main()
