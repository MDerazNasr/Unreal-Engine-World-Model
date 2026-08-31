#pragma once

#include "CoreMinimal.h"
#include "MotionWorldStateSample.generated.h"

/**
 * One immutable snapshot of finalized gameplay movement state.
 *
 * Names carry units and coordinate frames so this packet cannot silently mix
 * Unreal gameplay state with animation-root telemetry or planner-local values.
 */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldStateSample
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	int32 ProtocolVersion = 1;

	/** Monotonic order in which this bridge observed OnPostFinalize callbacks. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	int64 SampleSequence = -1;

	/** Mover frame that produced this state; INDEX_NONE is valid for variable-dt backends. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	int32 MoverStepServerFrame = INDEX_NONE;

	/** Simulation time at the end of the finalized step, in seconds. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	double SimulationTimeSeconds = -1.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	double StepSeconds = -1.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	bool bIsResimulation = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	FName MovementMode = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	FVector PositionWorldCm = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	FVector VelocityWorldCmPerSec = FVector::ZeroVector;

	/** Horizontal velocity in character axes: +X forward, +Y right, Z always zero. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	FVector VelocityLocalPlanarCmPerSec = FVector::ZeroVector;

	/** Diagnostic yaw in Unreal degrees, normalized to [-180, 180]. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	double FacingYawDegrees = 0.0;

	/** World-facing unit vector (cos(yaw), sin(yaw)); model-safe across yaw wraparound. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	FVector2D FacingUnitWorld = FVector2D(1.0, 0.0);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|State")
	FVector AngularVelocityWorldDegPerSec = FVector::ZeroVector;
};

namespace MotionWorld
{
/** Primitive inputs extracted from UE Mover's finalized sync state and timestep. */
struct FAuthoritativeStateInputs
{
	bool bHasAuthoritativeSource = false;
	int64 SampleSequence = -1;
	int32 MoverStepServerFrame = INDEX_NONE;
	double SimulationTimeSeconds = -1.0;
	double StepSeconds = -1.0;
	bool bIsResimulation = false;
	FName MovementMode = NAME_None;
	FVector PositionWorldCm = FVector::ZeroVector;
	FVector VelocityWorldCmPerSec = FVector::ZeroVector;
	FRotator OrientationWorldDegrees = FRotator::ZeroRotator;
	FVector AngularVelocityWorldDegPerSec = FVector::ZeroVector;
};

/** Builds a finite, explicitly framed state packet or a fail-closed invalid packet. */
MOTIONWORLD_API FMotionWorldStateSample BuildAuthoritativeStateSample(
	const FAuthoritativeStateInputs& Inputs);
} // namespace MotionWorld
