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

After every Mover finalization, the bridge also retains a versioned authoritative gameplay-state
snapshot with explicit frames and units. The first valid state and then every configurable Nth
sample are logged for diagnostics. This is intentionally an in-memory proof before episode file I/O,
networking, or reset behavior is added.

The next bounded layer defines a fail-closed causal transition candidate:
`previous state --(applied velocity, measured dt)--> next state`. It validates episode identity,
adjacent simulation chronology, schema, numerical values, and action semantics, and resolves the
world action in the previous state's character frame. It is currently a pure tested contract; the
recorder that obtains Mover's last consumed input and buffers complete episodes is the next slice.

Build the isolated plugin package on macOS with:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/RunUAT.sh" BuildPlugin \
  -Plugin="$PWD/unreal/Plugins/MotionWorld/MotionWorld.uplugin" \
  -Package=/private/tmp/MotionWorldPluginPackage \
  -TargetPlatforms=Mac \
  -StrictIncludes
```

The package location is disposable and must not be committed. The plugin source is copied into the
local sample without committing Epic assets. Runtime acceptance for each slice requires executing
its automation test and inspecting the corresponding command or state evidence in the real sample.

Use `/private/tmp` rather than its `/tmp` alias on macOS. UE 5.8's local build accelerator can retain
the spelling used by AutomationTool while Clang resolves the same path to `/private/tmp`, causing a
false missing-object linker failure.
