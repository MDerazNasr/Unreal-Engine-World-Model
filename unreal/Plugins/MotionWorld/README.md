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
sample are logged for diagnostics. This is intentionally an in-memory proof before episode file I/O
or networking is added.

The causal layer defines a fail-closed transition candidate:
`previous state --(applied velocity, measured dt)--> next state`. It validates episode identity,
adjacent simulation chronology, schema, numerical values, and action semantics, and resolves the
world action in the previous state's character frame.

An opt-in in-memory recorder now seeds the first finalized state, obtains Mover's most recently used
input at each later finalization, and buffers only accepted transitions under explicit episode and
attempt sequence IDs. Rejections are counted, valid recovery states become the next seed, and a
hard capacity stops recording without overwriting older rows. Automatic BeginPlay recording is
disabled by default. In the actual UE 5.8.2 sample, live episode 1601 reconciled 923 observations
into 922 consecutive accepted transitions with zero rejected pair, rejected seed, or capacity drop.
The reset slice captures a fixed authoritative anchor, stops the old recorder, queues Mover-owned
teleport and zero-velocity effects, stales Smooth Walking history, and starts a new episode only
after a newer finalized state passes position, yaw, velocity, angular-velocity, and mode checks.
Its default-off live proof performs two resets in one PIE session so their seed states and episode
boundaries can be compared. Strict builds, actual-sample automation, and live repeatability pass:
both resets produced identical zero-speed finalized seeds, and 1,249 total accepted transitions
were recorded without rejection or a cross-reset row.

Completed episodes can be exported on opt-in stop as versioned UTF-8 JSON Lines beneath
`Saved/MotionWorld/Episodes`. The exporter revalidates every row, writes a header and completeness
footer through a sibling temporary file, and never replaces an existing destination. Strict and
actual-sample automation pass. Live episode 1801 exported 458 rows in 15.809 ms; the independent
Python loader validated every row, reconciled all counters, and found no partial temporary file.

The timed-gate foundation evaluates sinusoidal blocker position and velocity directly from absolute
scenario time. Its focused actual-sample automation test and strict universal builds pass. A
separate runtime actor owns blocking geometry and collision evidence; bridge integration, scenario
schema-v2 fields, and independent Python revalidation pass. Live episode 1901 captured a retained
gate collision, and same-seed episode 1902 reproduced the schedule and initial state. Later
schema-v5 episode 4301 captured one source-aligned controlled velocity perturbation and its
recovery interval.

A separate default-off Smooth Walking diagnostic reads the active public movement-mode object and
the finalized public Mover sync collection through a narrow UE 5.8 reflection contract. It captures
the 14 audited float parameters, double-facing flag, and five known spring-state fields without
including Epic's private state header. Missing, type-mismatched, out-of-range, or non-finite data
fails closed; output is throttled, capped, and explicitly excluded from model input. Closed-editor
build and automation evidence passes. Live session `FF6768704542` accepted 1,422 valid finalized
reads with no invalid read and established the runtime parameter/state contract subsequently used
by the Python nominal model.

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

The isolated control transport uses configurable IPv4 loopback UDP endpoints. It performs only
bounded nonblocking byte I/O: at most 16 datagrams per poll, a fixed full-UDP receive buffer, and
message-specific size/source rejection before parsing. It has no bridge reference and cannot mutate
gameplay state. Shared packaged fixtures prove that Python parses the Unreal observation contract and
Unreal parses typed Python actions, including zero/optional boundaries and bounded malformed input.
The action parser performs current-episode/observation admission, but remains disconnected from the
bridge until the live vertical-slice gate.

Gate R1 additionally deploys this exact source and its packaged fixtures to the actual UE 5.8 Game
Animation Sample. Its universal Editor target and both `MotionWorld.Protocol` automation tests pass.
This establishes project compatibility while intentionally making no live-control claim.

R2.2 connects the protocol to gameplay only through a separate, default-off
`UMotionWorldNetworkControllerComponent`. The component owns nonblocking polling, fixed 10 Hz
simulation-time slots, exclusive wall-time deadlines, episode/sequence admission, separate failure
counters, and the one-hold/two-hold/three-stop policy. The bridge remains the final local-to-world
conversion and clamp boundary. Reset, controller switch, reconnection, and EndPlay clear runtime
state; disabling network control restores the bridge's ordinary human-input no-op behavior. Two
focused `MotionWorld.Network` automation tests pass in the actual sample. Live round-trip evidence is
still required by Gate R2.

Use `/private/tmp` rather than its `/tmp` alias on macOS. UE 5.8's local build accelerator can retain
the spelling used by AutomationTool while Clang resolves the same path to `/private/tmp`, causing a
false missing-object linker failure.
