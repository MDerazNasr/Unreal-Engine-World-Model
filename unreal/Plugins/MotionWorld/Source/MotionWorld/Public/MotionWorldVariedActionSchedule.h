#pragma once

#include "CoreMinimal.h"
#include "MotionWorldVariedActionSchedule.generated.h"

UENUM(BlueprintType)
enum class EMotionWorldVariedActionPhase : uint8
{
	Invalid,
	Forward,
	ForwardStop,
	Reverse,
	ReverseStop,
	Right,
	Left,
	Diagonal,
	FinalStop,
	Complete
};

/** Fixed-shape, editable timings and speeds for one deterministic coverage episode. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldVariedActionScheduleConfig
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.1"))
	double MotionPhaseDurationSeconds = 0.8;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.1"))
	double IntermediateStopDurationSeconds = 0.4;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.1"))
	double FinalStopDurationSeconds = 0.5;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.0"))
	double ForwardSpeedCmPerSec = 200.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.0"))
	double ReverseSpeedCmPerSec = 150.0;

	/**
	 * Clockwise offset from the exactly antipodal world -X facing target.
	 *
	 * FQuat::FindBetween has two equally short answers at exactly 180 degrees.
	 * Keeping this above the engine's opposite-vector branch threshold makes the
	 * intended turn direction causal and reproducible without changing velocity.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.25", ClampMax = "5.0"))
	double AntipodalFacingTieBreakDegrees = 0.5;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.0"))
	double LateralSpeedCmPerSec = 140.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.0"))
	double DiagonalComponentSpeedCmPerSec = 100.0;
};

USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldVariedActionScheduleSample
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	bool bIsComplete = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	EMotionWorldVariedActionPhase Phase = EMotionWorldVariedActionPhase::Invalid;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	double ElapsedSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	FVector DesiredVelocityWorldCmPerSec = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	FVector OrientationIntentWorld = FVector::ForwardVector;
};

namespace MotionWorld
{
MOTIONWORLD_API bool IsVariedActionScheduleConfigValid(
	const FMotionWorldVariedActionScheduleConfig& Config);

MOTIONWORLD_API double GetVariedActionScheduleDurationSeconds(
	const FMotionWorldVariedActionScheduleConfig& Config);

/** Evaluate a half-open, absolute-time schedule; no frame counter or random state is used. */
MOTIONWORLD_API FMotionWorldVariedActionScheduleSample EvaluateVariedActionSchedule(
	const FMotionWorldVariedActionScheduleConfig& Config,
	double ElapsedSeconds);
} // namespace MotionWorld
