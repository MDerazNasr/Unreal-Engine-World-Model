# MotionWorld Unreal plugin

This directory is the source-controlled Unreal Engine side of MotionWorld. It deliberately contains
no Epic Game Animation Sample assets.

The initial module is behavior-free. Its only purpose is to prove that the plugin descriptor,
runtime module, UE 5.8 toolchain, and dependency on the experimental `Mover` plugin compile before
control or logging logic is introduced.

Build the isolated plugin package on macOS with:

```bash
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/RunUAT.sh" BuildPlugin \
  -Plugin="$PWD/unreal/Plugins/MotionWorld/MotionWorld.uplugin" \
  -Package=/private/tmp/MotionWorldPluginPackage \
  -TargetPlatforms=Mac \
  -StrictIncludes
```

The package location is disposable and must not be committed. The next gate copies only the tracked
plugin source into the local sample and verifies that disabling the plugin preserves normal human
control.

Use `/private/tmp` rather than its `/tmp` alias on macOS. UE 5.8's local build accelerator can retain
the spelling used by AutomationTool while Clang resolves the same path to `/private/tmp`, causing a
false missing-object linker failure.
