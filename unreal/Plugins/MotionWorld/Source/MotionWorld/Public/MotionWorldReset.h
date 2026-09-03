#pragma once

#include "CoreMinimal.h"
#include "MotionWorldStateSample.h"
#include "MotionWorldReset.generated.h"

UENUM(BlueprintType)
enum class EMotionWorldResetCheckResult : uint8
{
	NotChecked UMETA(DisplayName = "Not Checked"),
	Passed UMETA(DisplayName = "Passed"),
	InvalidTolerances UMETA(DisplayName = "Invalid Tolerances"),
	InvalidTarget UMETA(DisplayName = "Invalid Target"),
	InvalidFinalizedState UMETA(DisplayName = "Invalid Finalized State"),
	Resimulation UMETA(DisplayName = "Resimulation"),
	PositionMismatch UMETA(DisplayName = "Position Mismatch"),
	FacingMismatch UMETA(DisplayName = "Facing Mismatch"),
	LinearVelocityMismatch UMETA(DisplayName = "Linear Velocity Mismatch"),
	AngularVelocityMismatch UMETA(DisplayName = "Angular Velocity Mismatch"),
	MovementModeMismatch UMETA(DisplayName = "Movement Mode Mismatch")
};

/** Fixed authoritative character pose to which later episodes return. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldResetTarget
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int64 SourceStateSequence = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	FVector PositionWorldCm = FVector::ZeroVector;

	/** Upright gameplay facing; pitch and roll are intentionally zero for this planar demo. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	FRotator OrientationWorldDegrees = FRotator::ZeroRotator;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	FName MovementMode = NAME_None;
};

USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldResetTolerances
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Reset", meta = (ClampMin = "0.0"))
	double PositionCm = 1.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Reset", meta = (ClampMin = "0.0", ClampMax = "180.0"))
	double FacingDegrees = 0.25;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Reset", meta = (ClampMin = "0.0"))
	double LinearSpeedCmPerSec = 1.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Reset", meta = (ClampMin = "0.0"))
	double AngularSpeedDegPerSec = 1.0;
};

/** Diagnostic result from comparing a finalized state with a reset target. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldResetCheck
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	EMotionWorldResetCheckResult Result = EMotionWorldResetCheckResult::NotChecked;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	double PositionErrorCm = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	double FacingErrorDegrees = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	double LinearSpeedCmPerSec = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	double AngularSpeedDegPerSec = 0.0;

	bool Passed() const { return Result == EMotionWorldResetCheckResult::Passed; }
};

/** Observable lifecycle counters for reset requests and their finalized verification. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldResetStatus
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	bool bHasAnchor = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	bool bIsPending = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	bool bLastResetSucceeded = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int64 RequestedEpisodeId = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int64 RequestCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int64 SuccessCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int64 FailureCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int32 VerificationAttemptCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int64 RequestStateSequence = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	int32 RequestMoverStepServerFrame = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	FMotionWorldResetCheck LastCheck;
};

namespace MotionWorld
{
/** Converts one ordinary finalized state into the fixed upright reset target. */
MOTIONWORLD_API FMotionWorldResetTarget BuildResetTarget(
	const FMotionWorldStateSample& AnchorState);

/** Return a copied planar reset target with normalized yaw, or an invalid target on bad input. */
MOTIONWORLD_API FMotionWorldResetTarget OverrideResetTargetYaw(
	const FMotionWorldResetTarget& Target,
	double FacingYawDegrees);

/** Fail-closed comparison used before a post-reset state may seed a new episode. */
MOTIONWORLD_API FMotionWorldResetCheck CheckFinalizedResetState(
	const FMotionWorldResetTarget& Target,
	const FMotionWorldStateSample& FinalizedState,
	const FMotionWorldResetTolerances& Tolerances);
} // namespace MotionWorld
