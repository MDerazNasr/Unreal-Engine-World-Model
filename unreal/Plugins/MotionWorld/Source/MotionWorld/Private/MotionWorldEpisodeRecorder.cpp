#include "MotionWorldEpisodeRecorder.h"

namespace
{
constexpr int32 SupportedStateProtocolVersion = 1;
constexpr int32 SupportedNominalContextProtocolVersion = 2;
constexpr int32 MaximumSupportedTransitionCapacity = 100000;
} // namespace

namespace MotionWorld
{
void FInMemoryEpisodeRecorder::Reset()
{
	Stats = FMotionWorldEpisodeRecorderStats();
	Transitions.Reset();
	RejectionCounts.Reset();
	PreviousState = FMotionWorldStateSample();
	PreviousNominalContext = FMotionWorldNominalContextSample();
	LastCandidate = FMotionWorldTransitionSample();
	NextTransitionSequence = 0;
	TransitionCapacity = 0;
	bHasLastCandidate = false;
}

bool FInMemoryEpisodeRecorder::StartEpisode(
	const int64 EpisodeId,
	const int32 MaxTransitions)
{
	Reset();
	if (EpisodeId < 0
		|| MaxTransitions <= 0
		|| MaxTransitions > MaximumSupportedTransitionCapacity)
	{
		return false;
	}

	Stats.EpisodeId = EpisodeId;
	Stats.bIsRecording = true;
	TransitionCapacity = MaxTransitions;
	Transitions.Reserve(MaxTransitions);
	return true;
}

void FInMemoryEpisodeRecorder::StopEpisode()
{
	Stats.bIsRecording = false;
	Stats.bHasSeedState = false;
	PreviousState = FMotionWorldStateSample();
	PreviousNominalContext = FMotionWorldNominalContextSample();
}

EMotionWorldTransitionRejectionReason
FInMemoryEpisodeRecorder::GetSeedRejectionReason(
	const FMotionWorldStateSample& State,
	const FMotionWorldNominalContextSample& NominalContext)
{
	if (!IsStateNumericallyValidForTransition(State))
	{
		return EMotionWorldTransitionRejectionReason::InvalidNextState;
	}

	if (State.ProtocolVersion != SupportedStateProtocolVersion)
	{
		return EMotionWorldTransitionRejectionReason::UnsupportedStateProtocol;
	}

	if (NominalContext.ProtocolVersion != SupportedNominalContextProtocolVersion)
	{
		return EMotionWorldTransitionRejectionReason::UnsupportedNominalContextProtocol;
	}

	if (!IsNominalContextSampleValid(NominalContext))
	{
		return EMotionWorldTransitionRejectionReason::InvalidNextNominalContext;
	}

	if (NominalContext.AuthoritativeStateSampleSequence != State.SampleSequence
		|| NominalContext.MovementModeName != State.MovementMode)
	{
		return EMotionWorldTransitionRejectionReason::NominalContextStateMismatch;
	}

	if (State.bIsResimulation)
	{
		return EMotionWorldTransitionRejectionReason::Resimulation;
	}

	return EMotionWorldTransitionRejectionReason::None;
}

bool FInMemoryEpisodeRecorder::CanUseAsSeed(
	const FMotionWorldStateSample& State,
	const FMotionWorldNominalContextSample& NominalContext)
{
	return GetSeedRejectionReason(State, NominalContext)
		== EMotionWorldTransitionRejectionReason::None;
}

void FInMemoryEpisodeRecorder::RecordRejection(
	const EMotionWorldTransitionRejectionReason Reason,
	const bool bWasSeed)
{
	Stats.LastRejectionReason = Reason;
	++RejectionCounts.FindOrAdd(Reason);
	if (bWasSeed)
	{
		++Stats.RejectedSeedStateCount;
	}
	else
	{
		++Stats.RejectedTransitionCount;
	}
}

EMotionWorldRecorderObservationResult
FInMemoryEpisodeRecorder::ObserveFinalizedStep(
	const FMotionWorldStateSample& CurrentState,
	const FMotionWorldNominalContextSample& CurrentNominalContext,
	const bool bAppliedInputWasVelocity,
	const bool bWasMotionWorldAutomated,
	const FVector& AppliedVelocityWorldCmPerSec,
	const bool bHasAppliedOrientationIntent,
	const FVector& AppliedOrientationIntentWorld)
{
	if (!Stats.bIsRecording)
	{
		return EMotionWorldRecorderObservationResult::IgnoredNotRecording;
	}

	++Stats.ObservedStateCount;
	if (!Stats.bHasSeedState)
	{
		const EMotionWorldTransitionRejectionReason SeedRejectionReason =
			GetSeedRejectionReason(CurrentState, CurrentNominalContext);
		if (SeedRejectionReason != EMotionWorldTransitionRejectionReason::None)
		{
			RecordRejection(SeedRejectionReason, true);
			return EMotionWorldRecorderObservationResult::RejectedSeed;
		}

		PreviousState = CurrentState;
		PreviousNominalContext = CurrentNominalContext;
		Stats.bHasSeedState = true;
		return EMotionWorldRecorderObservationResult::Seeded;
	}

	FTransitionSampleInputs Inputs;
	Inputs.EpisodeId = Stats.EpisodeId;
	Inputs.TransitionSequence = NextTransitionSequence++;
	Inputs.PreviousState = PreviousState;
	Inputs.NextState = CurrentState;
	Inputs.PreviousNominalContext = PreviousNominalContext;
	Inputs.NextNominalContext = CurrentNominalContext;
	Inputs.bAppliedInputWasVelocity = bAppliedInputWasVelocity;
	Inputs.bWasMotionWorldAutomated = bWasMotionWorldAutomated;
	Inputs.AppliedVelocityWorldCmPerSec = AppliedVelocityWorldCmPerSec;
	Inputs.bHasAppliedOrientationIntent = bHasAppliedOrientationIntent;
	Inputs.AppliedOrientationIntentWorld = AppliedOrientationIntentWorld;

	LastCandidate = BuildTransitionSample(Inputs);
	bHasLastCandidate = true;
	++Stats.AttemptedTransitionCount;

	if (CanUseAsSeed(CurrentState, CurrentNominalContext))
	{
		PreviousState = CurrentState;
		PreviousNominalContext = CurrentNominalContext;
		Stats.bHasSeedState = true;
	}
	else
	{
		PreviousState = FMotionWorldStateSample();
		PreviousNominalContext = FMotionWorldNominalContextSample();
		Stats.bHasSeedState = false;
	}

	if (!LastCandidate.bIsValid)
	{
		RecordRejection(LastCandidate.RejectionReason, false);
		return EMotionWorldRecorderObservationResult::RejectedTransition;
	}

	if (Transitions.Num() >= TransitionCapacity)
	{
		++Stats.CapacityDropCount;
		StopEpisode();
		return EMotionWorldRecorderObservationResult::StoppedBufferFull;
	}

	Transitions.Add(LastCandidate);
	++Stats.RecordedTransitionCount;
	Stats.LastRejectionReason = EMotionWorldTransitionRejectionReason::None;
	return EMotionWorldRecorderObservationResult::Recorded;
}

int64 FInMemoryEpisodeRecorder::GetRejectionCount(
	const EMotionWorldTransitionRejectionReason Reason) const
{
	return RejectionCounts.FindRef(Reason);
}
} // namespace MotionWorld
