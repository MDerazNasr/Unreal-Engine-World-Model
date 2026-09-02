#pragma once

#include "CoreMinimal.h"
#include "MotionWorldExternalPerturbationSchedule.generated.h"

UENUM(BlueprintType)
enum class EMotionWorldExternalPerturbationPhase : uint8
{
	Invalid,
	PrePerturbation,
	PerturbationDue,
	PostPerturbation,
	Complete
};

/** Configuration for one deterministic, one-tick additive velocity intervention. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldExternalPerturbationScheduleConfig
{
	GENERATED_BODY()

	/** Time recorded before the intervention becomes due. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.1"))
	double WarmupDurationSeconds = 1.5;

	/** Time recorded after the intervention has been queued. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection", meta = (ClampMin = "0.1"))
	double PostPerturbationDurationSeconds = 2.0;

	/**
	 * World-space velocity added by Mover for one tick, in cm/s.
	 * This is a velocity kick, not a force or mass-based impulse.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Collection")
	FVector AdditiveVelocityWorldCmPerSec = FVector(0.0, 250.0, 0.0);
};

USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldExternalPerturbationScheduleSample
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	bool bShouldQueuePerturbation = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	bool bIsComplete = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	EMotionWorldExternalPerturbationPhase Phase =
		EMotionWorldExternalPerturbationPhase::Invalid;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	double ElapsedSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Collection")
	FVector AdditiveVelocityWorldCmPerSec = FVector::ZeroVector;
};

namespace MotionWorld
{
MOTIONWORLD_API bool IsExternalPerturbationScheduleConfigValid(
	const FMotionWorldExternalPerturbationScheduleConfig& Config);

MOTIONWORLD_API double GetExternalPerturbationScheduleDurationSeconds(
	const FMotionWorldExternalPerturbationScheduleConfig& Config);

/**
 * Evaluates an absolute-time schedule.
 *
 * A late frame cannot skip the intervention: until the caller confirms it was
 * queued, every sample at or after the trigger remains PerturbationDue.
 */
MOTIONWORLD_API FMotionWorldExternalPerturbationScheduleSample
EvaluateExternalPerturbationSchedule(
	const FMotionWorldExternalPerturbationScheduleConfig& Config,
	double ElapsedSeconds,
	bool bPerturbationAlreadyQueued);
} // namespace MotionWorld
