"""Run inside Unreal Editor Python to apply, verify, or restore V3 settings."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs/v3_two_obstacle_demo_manifest.json"
_VECTOR3 = {
    "reactive_target_world_cm", "timed_gate_half_extents_cm",
    "second_timed_gate_half_extents_cm",
}
_VECTOR2 = {"reactive_terminal_velocity_local_cm_per_sec"}


def _load_manifest():
    path = ROOT / "motionworld/control/v3_two_obstacle_demo_manifest.py"
    spec = importlib.util.spec_from_file_location("motionworld_v3_manifest", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load manifest module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_v3_two_obstacle_demo_manifest(MANIFEST, ROOT)


def _single_component(blueprint, component_class, label: str):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    found = []
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        component = library.get_object_for_blueprint(library.get_data(handle), blueprint)
        if isinstance(component, component_class):
            found.append(component)
    if len(found) != 1:
        raise RuntimeError(f"expected exactly one {label}; found {len(found)}")
    return found[0]


def _json_value(name, value):
    if name in _VECTOR3:
        return [float(value.x), float(value.y), float(value.z)]
    if name in _VECTOR2:
        return [float(value.x), float(value.y)]
    return value


def _editor_value(name, value):
    if name in _VECTOR3:
        return unreal.Vector(float(value[0]), float(value[1]), float(value[2]))
    if name in _VECTOR2:
        return unreal.Vector2D(float(value[0]), float(value[1]))
    return value


def _read(component, settings):
    return {name: _json_value(name, component.get_editor_property(name)) for name in settings}


def _write(component, settings):
    for name, value in settings.items():
        component.set_editor_property(name, _editor_value(name, value))


def _compile_save(asset, context: str) -> None:
    if not unreal.BlueprintEditorLibrary.compile_blueprint(asset):
        raise RuntimeError(f"{context} Blueprint did not compile cleanly")
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f"failed to save {context} Blueprint")


def _validate_vector(settings, name: str, size: int) -> None:
    value = settings.get(name)
    if (
        not isinstance(value, list) or len(value) != size
        or any(type(item) not in {int, float} or not math.isfinite(item) for item in value)
    ):
        raise RuntimeError(f"V3 backup {name} must contain {size} finite coordinates")


def main() -> None:
    manifest = _load_manifest()
    mode = os.environ.get("MOTIONWORLD_V3_DEMO_MODE", "verify")
    if mode not in {"apply", "verify", "restore"}:
        raise RuntimeError("MOTIONWORLD_V3_DEMO_MODE must be apply, verify, or restore")
    asset = unreal.EditorAssetLibrary.load_asset(manifest.blueprint_asset)
    if asset is None:
        raise RuntimeError(f"could not load {manifest.blueprint_asset}")
    bridge = _single_component(asset, unreal.MotionWorldBridgeComponent, "MotionWorld bridge")
    network = _single_component(
        asset, unreal.MotionWorldNetworkControllerComponent, "MotionWorld network controller"
    )
    saved = Path(unreal.Paths.project_saved_dir()) / "MotionWorld/V3TwoObstacleDemo"
    saved.mkdir(parents=True, exist_ok=True)
    backup_path = saved / "blueprint_settings_backup.json"
    expected = {
        "bridge_settings": dict(manifest.bridge_settings),
        "network_settings": dict(manifest.network_settings),
    }

    if mode == "apply":
        if backup_path.exists():
            raise RuntimeError(f"refusing to overwrite existing V3 backup: {backup_path}")
        backup = {
            "schema_name": "motionworld_v3_blueprint_settings_backup",
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
        actual = {
            "bridge_settings": _read(bridge, manifest.bridge_settings),
            "network_settings": _read(network, manifest.network_settings),
        }
        if actual != expected:
            raise RuntimeError(f"V3 apply readback mismatch: {actual}")
        _compile_save(asset, "configured V3")
    elif mode == "restore":
        if not backup_path.is_file():
            raise RuntimeError(f"missing V3 settings backup: {backup_path}")
        backup = json.loads(backup_path.read_text(encoding="utf-8"))
        if set(backup) != {
            "schema_name", "schema_version", "manifest_sha256", "blueprint_asset",
            "bridge_settings", "network_settings",
        }:
            raise RuntimeError("V3 backup keys are not exact")
        if (
            backup["schema_name"] != "motionworld_v3_blueprint_settings_backup"
            or backup["schema_version"] != 1
            or backup["manifest_sha256"] != manifest.canonical_sha256
            or backup["blueprint_asset"] != manifest.blueprint_asset
        ):
            raise RuntimeError("V3 backup identity mismatch")
        if set(backup["bridge_settings"]) != set(manifest.bridge_settings):
            raise RuntimeError("V3 backup bridge keys mismatch")
        if set(backup["network_settings"]) != set(manifest.network_settings):
            raise RuntimeError("V3 backup network keys mismatch")
        _validate_vector(backup["bridge_settings"], "timed_gate_half_extents_cm", 3)
        _validate_vector(backup["bridge_settings"], "second_timed_gate_half_extents_cm", 3)
        _validate_vector(backup["network_settings"], "reactive_target_world_cm", 3)
        _validate_vector(
            backup["network_settings"], "reactive_terminal_velocity_local_cm_per_sec", 2
        )
        restored = {
            "bridge_settings": backup["bridge_settings"],
            "network_settings": backup["network_settings"],
        }
        _write(bridge, restored["bridge_settings"])
        _write(network, restored["network_settings"])
        if {
            "bridge_settings": _read(bridge, manifest.bridge_settings),
            "network_settings": _read(network, manifest.network_settings),
        } != restored:
            raise RuntimeError("V3 restore readback mismatch")
        _compile_save(asset, "restored V3")
        backup_path.unlink()

    actual = {
        "bridge_settings": _read(bridge, manifest.bridge_settings),
        "network_settings": _read(network, manifest.network_settings),
    }
    matches = actual == expected
    report = {
        "mode": mode,
        "manifest_sha256": manifest.canonical_sha256,
        "service_config": str(manifest.service_config_path.relative_to(ROOT)),
        "planner_config": str(manifest.planner_config_path.relative_to(ROOT)),
        "matches_v3_manifest": matches,
        "actual": actual,
    }
    (saved / "configuration_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if mode != "restore" and not matches:
        raise RuntimeError("Blueprint readback does not match the V3 manifest")
    unreal.log(f"MotionWorld V3 configuration {mode}: {json.dumps(report, sort_keys=True)}")


main()
