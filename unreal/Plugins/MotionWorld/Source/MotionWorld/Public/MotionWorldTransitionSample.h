#pragma once

#include "CoreMinimal.h"
#include "MotionWorldStateSample.h"
#include "MotionWorldTransitionSample.generated.h"

UENUM(BlueprintType)
enum class EMotionWorldAppliedActionType : uint8
{
	Invalid,
	DesiredVelocity
};

UENUM(BlueprintType)
enum class EMotionWorldTransitionRejectionReason : uint8
{
	None,
	InvalidEpisodeId,
	InvalidTransitionSequence,
	InvalidPreviousState,
	InvalidNextState,
	UnsupportedStateProtocol,
	Resimulation,
	NonContiguousStateSequence,
	NonContiguousMoverFrame,
	NonIncreasingSimulationTime,
	TimestepMismatch,
	UnsupportedActionType,
	NonFiniteAction,
	NonPlanarAction
};

/** Velocity input actually consumed by Mover for one finalized transition. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldAppliedVelocityAction
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	EMotionWorldAppliedActionType Type = EMotionWorldAppliedActionType::Invalid;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	bool bWasMotionWorldAutomated = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FVector VelocityWorldCmPerSec = FVector::ZeroVector;

	/** Applied velocity expressed using the previous state's character frame. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FVector VelocityLocalPlanarCmPerSec = FVector::ZeroVector;
};

/** One causal training candidate: previous state, applied action, and finalized next state. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldTransitionSample
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	int32 ProtocolVersion = 1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	int64 EpisodeId = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	int64 TransitionSequence = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	EMotionWorldTransitionRejectionReason RejectionReason =
		EMotionWorldTransitionRejectionReason::None;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	double StartSimulationTimeSeconds = -1.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	double EndSimulationTimeSeconds = -1.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	double DeltaTimeSeconds = -1.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldStateSample PreviousState;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldAppliedVelocityAction AppliedAction;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldStateSample NextState;
};

namespace MotionWorld
{
/** Revalidates all numeric state fields before the state can seed or enter a transition. */
MOTIONWORLD_API bool IsStateNumericallyValidForTransition(
	const FMotionWorldStateSample& State);

struct FTransitionSampleInputs
{
	int64 EpisodeId = -1;
	int64 TransitionSequence = -1;
	FMotionWorldStateSample PreviousState;
	FMotionWorldStateSample NextState;
	bool bAppliedInputWasVelocity = false;
	bool bWasMotionWorldAutomated = false;
	FVector AppliedVelocityWorldCmPerSec = FVector::ZeroVector;
};

/** Builds a causal transition candidate or returns an explicit rejection reason. */
MOTIONWORLD_API FMotionWorldTransitionSample BuildTransitionSample(
	const FTransitionSampleInputs& Inputs);
} // namespace MotionWorld
