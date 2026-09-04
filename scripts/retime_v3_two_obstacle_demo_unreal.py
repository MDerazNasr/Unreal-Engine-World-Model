"""Set synchronized V3 obstacle periods inside the demo Blueprint.

Run through Unreal Editor with MOTIONWORLD_PRIMARY_PERIOD_S and
MOTIONWORLD_SECONDARY_PERIOD_S in the environment. This intentionally changes
only the two analytic obstacle periods; all controller, geometry, and display
settings remain untouched.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import unreal

BLUEPRINT_ASSET = "/Game/Blueprints/SandboxCharacter_Mover"


def _period(name: str, default: float) -> float:
    value = float(os.environ.get(name, default))
    if not math.isfinite(value) or not 2.5 <= value <= 12.0:
        raise RuntimeError(f"{name} must be finite and in [2.5, 12.0] seconds")
    return value


def _bridge_component(blueprint):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    library = unreal.SubobjectDataBlueprintFunctionLibrary
    found = []
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        component = library.get_object_for_blueprint(library.get_data(handle), blueprint)
        if isinstance(component, unreal.MotionWorldBridgeComponent):
            found.append(component)
    if len(found) != 1:
        raise RuntimeError(f"expected exactly one MotionWorld bridge; found {len(found)}")
    return found[0]


def main() -> None:
    primary = _period("MOTIONWORLD_PRIMARY_PERIOD_S", 3.7)
    secondary = _period("MOTIONWORLD_SECONDARY_PERIOD_S", 8.0)
    blueprint = unreal.EditorAssetLibrary.load_asset(BLUEPRINT_ASSET)
    if blueprint is None:
        raise RuntimeError(f"could not load {BLUEPRINT_ASSET}")
    bridge = _bridge_component(blueprint)
    bridge.set_editor_property("timed_gate_period_seconds", primary)
    bridge.set_editor_property("second_timed_gate_period_seconds", secondary)
    if not unreal.BlueprintEditorLibrary.compile_blueprint(blueprint):
        raise RuntimeError("retimed V3 Blueprint did not compile cleanly")
    if not unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False):
        raise RuntimeError("failed to save retimed V3 Blueprint")
    actual = {
        "primary_period_s": float(
            bridge.get_editor_property("timed_gate_period_seconds")
        ),
        "secondary_period_s": float(
            bridge.get_editor_property("second_timed_gate_period_seconds")
        ),
    }
    expected = {"primary_period_s": primary, "secondary_period_s": secondary}
    if actual != expected:
        raise RuntimeError(f"retimed V3 readback mismatch: {actual}")
    report_path = (
        Path(unreal.Paths.project_saved_dir())
        / "MotionWorld/V3TwoObstacleDemo/randomized_periods_report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    unreal.log(f"MotionWorld V3 obstacle periods updated: {json.dumps(actual)}")


main()
