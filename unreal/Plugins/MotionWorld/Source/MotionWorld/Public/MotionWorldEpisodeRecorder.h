#pragma once

#include "CoreMinimal.h"
#include "MotionWorldTransitionSample.h"
#include "MotionWorldEpisodeRecorder.generated.h"

UENUM(BlueprintType)
enum class EMotionWorldRecorderObservationResult : uint8
{
	IgnoredNotRecording,
	Seeded,
	Recorded,
	RejectedSeed,
	RejectedTransition,
	StoppedBufferFull
};

/** Small, copyable status packet for inspecting an in-memory recording episode. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldEpisodeRecorderStats
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 EpisodeId = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	bool bIsRecording = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	bool bHasSeedState = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 ObservedStateCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 AttemptedTransitionCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 RecordedTransitionCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 RejectedTransitionCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 RejectedSeedStateCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 CapacityDropCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	EMotionWorldTransitionRejectionReason LastRejectionReason =
		EMotionWorldTransitionRejectionReason::None;
};

namespace MotionWorld
{
/**
 * Bounded, game-thread-owned recorder for one episode.
 *
 * The first eligible state is a seed. Each later observation attempts exactly
 * one causal transition using the input consumed during the just-ended step.
 */
class MOTIONWORLD_API FInMemoryEpisodeRecorder
{
public:
	bool StartEpisode(int64 EpisodeId, int32 MaxTransitions);
	void StopEpisode();

	EMotionWorldRecorderObservationResult ObserveFinalizedStep(
		const FMotionWorldStateSample& CurrentState,
		const FMotionWorldNominalContextSample& CurrentNominalContext,
		bool bAppliedInputWasVelocity,
		bool bWasMotionWorldAutomated,
		const FVector& AppliedVelocityWorldCmPerSec);

	const FMotionWorldEpisodeRecorderStats& GetStats() const { return Stats; }
	const TArray<FMotionWorldTransitionSample>& GetTransitions() const { return Transitions; }
	const FMotionWorldTransitionSample& GetLastCandidate() const { return LastCandidate; }
	bool HasLastCandidate() const { return bHasLastCandidate; }
	int64 GetRejectionCount(EMotionWorldTransitionRejectionReason Reason) const;

private:
	void Reset();
	void RecordRejection(EMotionWorldTransitionRejectionReason Reason, bool bWasSeed);
	static EMotionWorldTransitionRejectionReason GetSeedRejectionReason(
		const FMotionWorldStateSample& State,
		const FMotionWorldNominalContextSample& NominalContext);
	static bool CanUseAsSeed(
		const FMotionWorldStateSample& State,
		const FMotionWorldNominalContextSample& NominalContext);

	FMotionWorldEpisodeRecorderStats Stats;
	TArray<FMotionWorldTransitionSample> Transitions;
	TMap<EMotionWorldTransitionRejectionReason, int64> RejectionCounts;
	FMotionWorldStateSample PreviousState;
	FMotionWorldNominalContextSample PreviousNominalContext;
	FMotionWorldTransitionSample LastCandidate;
	int64 NextTransitionSequence = 0;
	int32 TransitionCapacity = 0;
	bool bHasLastCandidate = false;
};
} // namespace MotionWorld
