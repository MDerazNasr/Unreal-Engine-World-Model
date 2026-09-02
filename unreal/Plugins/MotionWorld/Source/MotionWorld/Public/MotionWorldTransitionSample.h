#pragma once

#include "CoreMinimal.h"
#include "MotionWorldExternalPerturbation.h"
#include "MotionWorldNominalContext.h"
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
	InvalidPreviousNominalContext,
	InvalidNextNominalContext,
	UnsupportedNominalContextProtocol,
	NominalContextStateMismatch,
	Resimulation,
	NonContiguousStateSequence,
	NonContiguousMoverFrame,
	NonIncreasingSimulationTime,
	TimestepMismatch,
	UnsupportedActionType,
	NonFiniteAction,
	NonPlanarAction,
	MissingOrientationIntent,
	NonFiniteOrientationIntent,
	InvalidExternalPerturbation,
	ExternalPerturbationStateMismatch
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

	/** Orientation intent consumed by Simple Walking, before planar normalization. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FVector OrientationIntentWorld = FVector::ZeroVector;

	/** Facing target after Simple Walking's zero-vector fallback and planar normalization. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	double DesiredFacingYawDegrees = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	bool bUsedPreviousFacingForZeroOrientationIntent = false;
};

/** One causal training candidate: previous state, applied action, and finalized next state. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldTransitionSample
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	int32 ProtocolVersion = 4;

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
	FMotionWorldNominalContextSample PreviousNominalContext;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldAppliedVelocityAction AppliedAction;

	/** Evaluation-only event label; never part of the requested control action. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldExternalPerturbation ExternalPerturbation;

	/**
	 * Runtime parameters observed at the next finalized boundary. They are assumed
	 * to have governed the completed step; the episode schema states this timing.
	 */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldSmoothWalkingParameters ParametersObservedForCompletedStep;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldSimpleWalkingInputPreparation InputPreparationObservedForCompletedStep;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldStateSample NextState;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Transition")
	FMotionWorldNominalContextSample NextNominalContext;
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
	FMotionWorldNominalContextSample PreviousNominalContext;
	FMotionWorldNominalContextSample NextNominalContext;
	bool bAppliedInputWasVelocity = false;
	bool bWasMotionWorldAutomated = false;
	FVector AppliedVelocityWorldCmPerSec = FVector::ZeroVector;
	bool bHasAppliedOrientationIntent = false;
	FVector AppliedOrientationIntentWorld = FVector::ZeroVector;
	FMotionWorldExternalPerturbation ExternalPerturbation;
};

/** Builds a causal transition candidate or returns an explicit rejection reason. */
MOTIONWORLD_API FMotionWorldTransitionSample BuildTransitionSample(
	const FTransitionSampleInputs& Inputs);
} // namespace MotionWorld
