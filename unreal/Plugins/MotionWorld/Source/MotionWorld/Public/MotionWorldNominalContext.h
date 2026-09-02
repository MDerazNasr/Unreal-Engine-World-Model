#pragma once

#include "CoreMinimal.h"
#include "MotionWorldSmoothWalkingDiagnostic.h"
#include "MotionWorldNominalContext.generated.h"

/** Known runtime parameters used by Unreal's Smooth Walking movement mode. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldSmoothWalkingParameters
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double AccelerationCmPerSecSquared = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double DecelerationCmPerSecSquared = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double DirectionalAccelerationFactor = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double TurningStrength = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double AccelerationSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double DecelerationSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double AccelerationSmoothingCompensation = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double DecelerationSmoothingCompensation = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double VelocityDeadzoneCmPerSec = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double AccelerationDeadzoneCmPerSecSquared = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double OutsideInfluenceSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double FacingSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	bool bSmoothFacingWithDoubleSpring = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double FacingDeadzoneDegrees = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double AngularVelocityDeadzoneDegreesPerSec = 0.0;
};

/** Hidden Smooth Walking memory carried between finalized movement steps. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldSmoothWalkingInternalState
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FVector SpringVelocityWorldCmPerSec = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FVector SpringAccelerationWorldCmPerSecSquared = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FVector IntermediateVelocityWorldCmPerSec = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FQuat IntermediateFacingWorld = FQuat::Identity;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FVector IntermediateAngularVelocityWorldRadPerSec = FVector::ZeroVector;
};

/** Known velocity preprocessing performed immediately before Smooth Walking. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldSimpleWalkingInputPreparation
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	bool bHasMaxMoveSpeed = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	double EffectiveMaxSpeedCmPerSec = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	EMotionWorldMaxSpeedSource MaxSpeedSource = EMotionWorldMaxSpeedSource::Unavailable;
};

/**
 * Versioned context observed at the same post-finalize boundary as an authoritative state.
 * This augments a transition; it does not replace or redefine authoritative state.
 */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldNominalContextSample
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	int32 ProtocolVersion = 2;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	int64 AuthoritativeStateSampleSequence = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FName MovementModeName = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FName MovementModeClass = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FName FailureReason = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FMotionWorldSmoothWalkingParameters Parameters;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FMotionWorldSimpleWalkingInputPreparation InputPreparation;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Nominal Context")
	FMotionWorldSmoothWalkingInternalState InternalState;
};

namespace MotionWorld
{
MOTIONWORLD_API bool AreSmoothWalkingParametersValid(
	const FMotionWorldSmoothWalkingParameters& Parameters);

MOTIONWORLD_API bool IsSimpleWalkingInputPreparationValid(
	const FMotionWorldSimpleWalkingInputPreparation& InputPreparation);

MOTIONWORLD_API bool IsNominalContextSampleValid(
	const FMotionWorldNominalContextSample& Sample);

/** Convert validated research telemetry into a strict model-facing context sample. */
MOTIONWORLD_API FMotionWorldNominalContextSample BuildNominalContextSample(
	const FMotionWorldSmoothWalkingDiagnosticSample& Diagnostic);
} // namespace MotionWorld
