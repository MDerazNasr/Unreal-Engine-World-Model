"""Run inside Unreal Python to report the constructed sample pawn's capsule geometry."""

import unreal

ASSET_PATH = "/Game/Blueprints/SandboxCharacter_Mover"

blueprint = unreal.load_asset(ASSET_PATH)
if blueprint is None:
    raise RuntimeError(f"Could not load {ASSET_PATH}")

generated_class = blueprint.generated_class()
if generated_class is None:
    raise RuntimeError(f"{ASSET_PATH} has no generated class")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actor = actor_subsystem.spawn_actor_from_class(generated_class, unreal.Vector(0.0, 0.0, 0.0))
if actor is None:
    raise RuntimeError(f"Could not transiently instantiate {ASSET_PATH}")

capsules = actor.get_components_by_class(unreal.CapsuleComponent)
if len(capsules) != 1:
    raise RuntimeError(f"Expected exactly one constructed capsule, found {len(capsules)}")

capsule = capsules[0]
unreal.log(
    "MOTIONWORLD_CAPSULE "
    f"name={capsule.get_name()} "
    f"unscaled_radius_cm={capsule.get_unscaled_capsule_radius():.9f} "
    f"unscaled_half_height_cm={capsule.get_unscaled_capsule_half_height():.9f} "
    f"scaled_radius_cm={capsule.get_scaled_capsule_radius():.9f} "
    f"scaled_half_height_cm={capsule.get_scaled_capsule_half_height():.9f}"
)
actor_subsystem.destroy_actor(actor)
