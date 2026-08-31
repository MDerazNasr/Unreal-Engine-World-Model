# MotionWorld Unreal plugin

This directory is the source-controlled Unreal Engine side of MotionWorld. It deliberately contains
no Epic Game Animation Sample assets.

The first module gate was behavior-free and proved that the plugin descriptor, runtime module,
UE 5.8 toolchain, and dependency on the experimental `Mover` plugin compile. The next bounded slice
adds `UMotionWorldBridgeComponent`: an opt-in planar velocity command with validation, speed
clamping, coordinate conversion, and a post-finalization echo check. Automation is disabled by
default, so adding the component alone preserves human control.

The bridge now defaults to a character-local action (`+X` forward, `+Y` right) and resolves it from
the current authoritative Mover yaw into the world-space packet consumed by Unreal. Direct
world-space commands remain available only as an explicit diagnostic mode.

Build the isolated plugin package on macOS with:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/RunUAT.sh" BuildPlugin \
  -Plugin="$PWD/unreal/Plugins/MotionWorld/MotionWorld.uplugin" \
  -Package=/private/tmp/MotionWorldPluginPackage \
  -TargetPlatforms=Mac \
  -StrictIncludes
```

The package location is disposable and must not be committed. The plugin source is copied into the
local sample without committing Epic assets. Runtime acceptance requires an echoed Mover velocity
packet before state recording or reset logic is added.

Use `/private/tmp` rather than its `/tmp` alias on macOS. UE 5.8's local build accelerator can retain
the spelling used by AutomationTool while Clang resolves the same path to `/private/tmp`, causing a
false missing-object linker failure.
