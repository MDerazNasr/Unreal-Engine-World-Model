#pragma once

#include "CoreMinimal.h"
#include "MoverTypes.h"
#include "MotionWorldSmoothWalkingDiagnostic.generated.h"

class UBaseMovementMode;

UENUM(BlueprintType)
enum class EMotionWorldMaxSpeedSource : uint8
{
	Unavailable,
	ModeOverride,
	CommonLegacySettings,
	Unbounded
};

/** Default-off research telemetry; never part of authoritative model state. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldSmoothWalkingDiagnosticSample
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	int32 ProtocolVersion = 2;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	int64 AuthoritativeStateSampleSequence = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FName MovementModeName = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FName MovementModeClass = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FName FailureReason = NAME_None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double AccelerationCmPerSecSquared = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double DecelerationCmPerSecSquared = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double DirectionalAccelerationFactor = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double TurningStrength = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double AccelerationSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double DecelerationSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double AccelerationSmoothingCompensation = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double DecelerationSmoothingCompensation = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double VelocityDeadzoneCmPerSec = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double AccelerationDeadzoneCmPerSecSquared = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double OutsideInfluenceSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double FacingSmoothingTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	bool bSmoothFacingWithDoubleSpring = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double FacingDeadzoneDegrees = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double AngularVelocityDeadzoneDegreesPerSec = 0.0;

	/** Input preprocessing performed by USimpleWalkingMode before Smooth Walking. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	bool bHasMaxMoveSpeed = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	double EffectiveMaxSpeedCmPerSec = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	EMotionWorldMaxSpeedSource MaxSpeedSource = EMotionWorldMaxSpeedSource::Unavailable;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FVector SpringVelocityWorldCmPerSec = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FVector SpringAccelerationWorldCmPerSecSquared = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FVector IntermediateVelocityWorldCmPerSec = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FQuat IntermediateFacingWorld = FQuat::Identity;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FVector IntermediateAngularVelocityWorldRadPerSec = FVector::ZeroVector;
};

namespace MotionWorld
{
struct FSmoothWalkingDiagnosticInputs
{
	int64 AuthoritativeStateSampleSequence = INDEX_NONE;
	FName MovementModeName = NAME_None;
	FName MovementModeClass = NAME_None;
	bool bHasParameters = false;
	bool bHasInputPreparation = false;
	bool bHasSpringState = false;
	TArray<double> Parameters;
	bool bSmoothFacingWithDoubleSpring = false;
	bool bHasMaxMoveSpeed = false;
	double EffectiveMaxSpeedCmPerSec = 0.0;
	EMotionWorldMaxSpeedSource MaxSpeedSource = EMotionWorldMaxSpeedSource::Unavailable;
	FVector SpringVelocity = FVector::ZeroVector;
	FVector SpringAcceleration = FVector::ZeroVector;
	FVector IntermediateVelocity = FVector::ZeroVector;
	FQuat IntermediateFacing = FQuat::Identity;
	FVector IntermediateAngularVelocity = FVector::ZeroVector;
	FName FailureReason = NAME_None;
};

MOTIONWORLD_API bool ReadSmoothWalkingParameters(
	const UBaseMovementMode* MovementMode,
	FSmoothWalkingDiagnosticInputs& OutInputs,
	FName& OutFailureReason);

MOTIONWORLD_API bool ReadSimpleWalkingInputPreparation(
	const UBaseMovementMode* MovementMode,
	FSmoothWalkingDiagnosticInputs& OutInputs,
	FName& OutFailureReason);

MOTIONWORLD_API bool ReadSmoothWalkingSpringState(
	const FMoverDataCollection& SyncStateCollection,
	FSmoothWalkingDiagnosticInputs& OutInputs,
	FName& OutFailureReason);

MOTIONWORLD_API FMotionWorldSmoothWalkingDiagnosticSample BuildSmoothWalkingDiagnosticSample(
	const FSmoothWalkingDiagnosticInputs& Inputs);
} // namespace MotionWorld
