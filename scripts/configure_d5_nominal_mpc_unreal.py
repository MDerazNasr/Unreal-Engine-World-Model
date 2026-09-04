"""Run inside Unreal Editor Python to apply, verify, or restore D5 MPC settings."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import unreal

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "configs" / "d5_nominal_mpc_manifest.json"
_VECTOR3 = "reactive_target_world_cm"
_VECTOR2 = "reactive_terminal_velocity_local_cm_per_sec"


def _load_manifest_function():
    module_path = REPOSITORY_ROOT / "motionworld/control/d5_nominal_mpc_manifest.py"
    spec = importlib.util.spec_from_file_location("motionworld_d5_nominal_manifest", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load manifest module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_d5_nominal_mpc_manifest


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


def _json_value(name, value):
    if name == _VECTOR3:
        return [float(value.x), float(value.y), float(value.z)]
    if name == _VECTOR2:
        return [float(value.x), float(value.y)]
    return value


def _editor_value(name, value):
    if name == _VECTOR3:
        return unreal.Vector(float(value[0]), float(value[1]), float(value[2]))
    if name == _VECTOR2:
        return unreal.Vector2D(float(value[0]), float(value[1]))
    return value


def _read(component, settings):
    return {
        name: _json_value(name, component.get_editor_property(name)) for name in settings
    }


def _write(component, settings):
    for name, value in settings.items():
        component.set_editor_property(name, _editor_value(name, value))


def _require_exact(actual, expected, context: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{context} readback mismatch: expected {expected}, got {actual}")


def _require_backup_vector(settings, name: str, size: int) -> None:
    value = settings.get(name)
    if (
        not isinstance(value, list)
        or len(value) != size
        or any(type(item) not in {int, float} or not math.isfinite(item) for item in value)
    ):
        raise RuntimeError(f"D5 backup {name} must contain {size} finite coordinates")


def _compile_and_save(asset, context: str) -> None:
    if not unreal.BlueprintEditorLibrary.compile_blueprint(asset):
        raise RuntimeError(f"{context} Blueprint did not compile cleanly")
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f"failed to save {context} Blueprint")


def main() -> None:
    manifest = _load_manifest_function()(MANIFEST_PATH, REPOSITORY_ROOT)
    mode = os.environ.get("MOTIONWORLD_D5_DEMO_MODE", "verify")
    if mode not in {"apply", "verify", "restore"}:
        raise RuntimeError("MOTIONWORLD_D5_DEMO_MODE must be apply, verify, or restore")
    asset = unreal.EditorAssetLibrary.load_asset(manifest.blueprint_asset)
    if asset is None:
        raise RuntimeError(f"could not load {manifest.blueprint_asset}")
    bridge = _single_component(asset, unreal.MotionWorldBridgeComponent, "MotionWorld bridge")
    network = _single_component(
        asset, unreal.MotionWorldNetworkControllerComponent, "MotionWorld network controller"
    )
    saved_dir = Path(unreal.Paths.project_saved_dir()) / "MotionWorld" / "D5NominalMpc"
    saved_dir.mkdir(parents=True, exist_ok=True)
    backup_path = saved_dir / "blueprint_settings_backup.json"
    expected = {
        "bridge_settings": dict(manifest.bridge_settings),
        "network_settings": dict(manifest.network_settings),
    }

    if mode == "apply":
        if backup_path.exists():
            raise RuntimeError(f"refusing to overwrite existing D5 backup: {backup_path}")
        backup = {
            "schema_name": "motionworld_d5_blueprint_settings_backup",
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
            "D5 apply",
        )
        _compile_and_save(asset, "configured D5")
    elif mode == "restore":
        if not backup_path.is_file():
            raise RuntimeError(f"missing D5 settings backup: {backup_path}")
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
            raise RuntimeError("D5 backup keys are not exact")
        if backup["schema_name"] != "motionworld_d5_blueprint_settings_backup":
            raise RuntimeError("D5 backup schema name mismatch")
        if backup["schema_version"] != 1:
            raise RuntimeError("D5 backup schema version mismatch")
        if backup["manifest_sha256"] != manifest.canonical_sha256:
            raise RuntimeError("D5 backup manifest identity mismatch")
        if backup["blueprint_asset"] != manifest.blueprint_asset:
            raise RuntimeError("D5 backup Blueprint identity mismatch")
        if set(backup["bridge_settings"]) != set(manifest.bridge_settings):
            raise RuntimeError("D5 backup bridge keys mismatch")
        if set(backup["network_settings"]) != set(manifest.network_settings):
            raise RuntimeError("D5 backup network keys mismatch")
        _require_backup_vector(backup["network_settings"], _VECTOR3, 3)
        _require_backup_vector(backup["network_settings"], _VECTOR2, 2)
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
            "D5 restore",
        )
        _compile_and_save(asset, "restored D5")
        _require_exact(
            {
                "bridge_settings": _read(bridge, manifest.bridge_settings),
                "network_settings": _read(network, manifest.network_settings),
            },
            restored,
            "saved D5 restore",
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
        "planner_config": str(manifest.planner_config_path.relative_to(REPOSITORY_ROOT)),
        "matches_d5_manifest": matches,
        "actual": actual,
    }
    (saved_dir / "configuration_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if mode != "restore" and not matches:
        raise RuntimeError("Blueprint readback does not match the D5 manifest")
    unreal.log(f"MotionWorld D5 configuration {mode}: {json.dumps(report, sort_keys=True)}")


main()
