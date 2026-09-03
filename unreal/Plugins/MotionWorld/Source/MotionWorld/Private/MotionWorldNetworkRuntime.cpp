#include "MotionWorldNetworkRuntime.h"

#include "MotionWorldControlAction.h"

namespace MotionWorld
{
bool FNetworkRuntime::StartEpisode(const int64 EpisodeId)
{
	if (EpisodeId < 0 || EpisodeId > MaxSafeJsonInteger)
	{
		return false;
	}
	Stats = FNetworkRuntimeStats();
	Stats.bEnabled = true;
	Stats.EpisodeId = EpisodeId;
	bHasEpoch = false;
	bOutstanding = false;
	bOutstandingAnswered = false;
	EpochSimulationTimeSeconds = 0.0;
	NextBoundarySimulationTimeSeconds = 0.0;
	OutstandingDeadlineMonotonicSeconds = 0.0;
	CurrentAppliedVelocityLocalCmPerSec = FVector2D::ZeroVector;
	CurrentAppliedSourceObservationSequence = INDEX_NONE;
	return true;
}

void FNetworkRuntime::Stop()
{
	Stats = FNetworkRuntimeStats();
	bHasEpoch = false;
	bOutstanding = false;
	bOutstandingAnswered = false;
	CurrentAppliedVelocityLocalCmPerSec = FVector2D::ZeroVector;
	CurrentAppliedSourceObservationSequence = INDEX_NONE;
}

FNetworkObservationDecision FNetworkRuntime::ObserveFinalizedState(
	const double SimulationTimeSeconds,
	const double MonotonicNowSeconds,
	const bool bStateValid,
	const bool bIsResimulation)
{
	FNetworkObservationDecision Result;
	if (!Stats.bEnabled
		|| !bStateValid
		|| bIsResimulation
		|| !FMath::IsFinite(SimulationTimeSeconds)
		|| !FMath::IsFinite(MonotonicNowSeconds))
	{
		return Result;
	}

	const bool bAtBoundary = !bHasEpoch
		|| SimulationTimeSeconds + UE_DOUBLE_SMALL_NUMBER
			>= NextBoundarySimulationTimeSeconds;
	if (!bAtBoundary)
	{
		return Result;
	}

	Result.bHasPreviousAction = Stats.NextObservationSequence > 0;
	Result.PreviousActionSourceObservationSequence =
		CurrentAppliedSourceObservationSequence;
	Result.PreviousAppliedVelocityLocalCmPerSec =
		CurrentAppliedVelocityLocalCmPerSec;
	if (bOutstanding)
	{
		Result.ExpiryUpdate = ExpireOutstanding();
	}

	if (!bHasEpoch)
	{
		bHasEpoch = true;
		EpochSimulationTimeSeconds = SimulationTimeSeconds;
		NextBoundarySimulationTimeSeconds =
			EpochSimulationTimeSeconds + NetworkControlIntervalSeconds;
	}
	else
	{
		const double Elapsed = FMath::Max(
			0.0,
			SimulationTimeSeconds - EpochSimulationTimeSeconds);
		const int64 ElapsedSlots = FMath::FloorToInt64(
			(Elapsed + UE_DOUBLE_SMALL_NUMBER) / NetworkControlIntervalSeconds);
		NextBoundarySimulationTimeSeconds = EpochSimulationTimeSeconds
			+ static_cast<double>(ElapsedSlots + 1) * NetworkControlIntervalSeconds;
	}

	Result.bShouldEmit = true;
	Result.EpisodeId = Stats.EpisodeId;
	Result.ObservationSequence = Stats.NextObservationSequence++;
	Stats.CurrentOutstandingObservationSequence = Result.ObservationSequence;
	++Stats.ObservationsEmitted;
	bOutstanding = true;
	bOutstandingAnswered = false;
	OutstandingDeadlineMonotonicSeconds =
		MonotonicNowSeconds + NetworkActionDeadlineSeconds;
	if (CurrentAppliedSourceObservationSequence == INDEX_NONE)
	{
		CurrentAppliedSourceObservationSequence = Result.ObservationSequence;
	}
	return Result;
}

FNetworkCommandUpdate FNetworkRuntime::AdvanceDeadline(
	const double MonotonicNowSeconds)
{
	if (!Stats.bEnabled
		|| !bOutstanding
		|| !FMath::IsFinite(MonotonicNowSeconds)
		|| MonotonicNowSeconds < OutstandingDeadlineMonotonicSeconds)
	{
		return FNetworkCommandUpdate();
	}
	return ExpireOutstanding();
}

FNetworkCommandUpdate FNetworkRuntime::AcceptAction(
	const int64 EpisodeId,
	const int64 SourceObservationSequence,
	const FVector2D& DesiredVelocityLocalCmPerSec,
	const double MonotonicReceiveSeconds)
{
	FNetworkCommandUpdate Result;
	if (!Stats.bEnabled
		|| !bOutstanding
		|| bOutstandingAnswered
		|| EpisodeId != Stats.EpisodeId
		|| SourceObservationSequence
			!= Stats.CurrentOutstandingObservationSequence
		|| !FMath::IsFinite(MonotonicReceiveSeconds)
		|| MonotonicReceiveSeconds >= OutstandingDeadlineMonotonicSeconds
		|| !FMath::IsFinite(DesiredVelocityLocalCmPerSec.X)
		|| !FMath::IsFinite(DesiredVelocityLocalCmPerSec.Y))
	{
		return Result;
	}

	bOutstanding = false;
	bOutstandingAnswered = true;
	Stats.ConsecutiveMisses = 0;
	++Stats.ActionsAccepted;
	CurrentAppliedVelocityLocalCmPerSec = DesiredVelocityLocalCmPerSec;
	CurrentAppliedSourceObservationSequence = SourceObservationSequence;
	Result.bShouldApply = true;
	Result.DesiredVelocityLocalCmPerSec = DesiredVelocityLocalCmPerSec;
	Result.SourceObservationSequence = SourceObservationSequence;
	Result.Cause = ENetworkCommandCause::AcceptedAction;
	return Result;
}

FNetworkCommandUpdate FNetworkRuntime::ExpireOutstanding()
{
	FNetworkCommandUpdate Result;
	if (!bOutstanding)
	{
		return Result;
	}
	bOutstanding = false;
	bOutstandingAnswered = false;
	++Stats.MissedResponses;
	++Stats.ConsecutiveMisses;
	Result.bShouldApply = true;
	Result.SourceObservationSequence =
		Stats.CurrentOutstandingObservationSequence;
	if (Stats.ConsecutiveMisses >= NetworkSafeStopMissCount)
	{
		CurrentAppliedVelocityLocalCmPerSec = FVector2D::ZeroVector;
		CurrentAppliedSourceObservationSequence =
			Stats.CurrentOutstandingObservationSequence;
		++Stats.SafeStops;
		Result.DesiredVelocityLocalCmPerSec = FVector2D::ZeroVector;
		Result.Cause = ENetworkCommandCause::DeadlineSafeStop;
	}
	else
	{
		++Stats.HeldAfterMiss;
		Result.DesiredVelocityLocalCmPerSec =
			CurrentAppliedVelocityLocalCmPerSec;
		Result.Cause = ENetworkCommandCause::DeadlineHold;
	}
	return Result;
}
} // namespace MotionWorld
