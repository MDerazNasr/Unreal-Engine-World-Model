#pragma once

#include "CoreMinimal.h"
#include "MotionWorldExternalPerturbation.generated.h"

UENUM(BlueprintType)
enum class EMotionWorldExternalPerturbationType : uint8
{
	None,
	AdditiveVelocity
};

/** Evaluation-only label for an external intervention during one causal step. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldExternalPerturbation
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Perturbation")
	int32 ProtocolVersion = 1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Perturbation")
	bool bIsValid = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Perturbation")
	EMotionWorldExternalPerturbationType Type =
		EMotionWorldExternalPerturbationType::None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Perturbation")
	bool bWasMotionWorldScheduled = false;

	/** Requested one-tick additive velocity, not a mass-based physical impulse. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Perturbation")
	FVector RequestedVelocityDeltaWorldCmPerSec = FVector::ZeroVector;

	/** Finalized state after which the effect was queued. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Perturbation")
	int64 QueuedAfterStateSampleSequence = -1;

	/** Mover frame of that finalized source state, or INDEX_NONE when unavailable. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Perturbation")
	int32 QueuedAfterMoverStepServerFrame = INDEX_NONE;
};

namespace MotionWorld
{
MOTIONWORLD_API FMotionWorldExternalPerturbation MakeAdditiveVelocityPerturbation(
	const FVector& RequestedVelocityDeltaWorldCmPerSec,
	int64 QueuedAfterStateSampleSequence,
	int32 QueuedAfterMoverStepServerFrame,
	bool bWasMotionWorldScheduled);

MOTIONWORLD_API bool IsExternalPerturbationValid(
	const FMotionWorldExternalPerturbation& Perturbation);
} // namespace MotionWorld
