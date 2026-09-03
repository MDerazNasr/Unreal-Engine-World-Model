#pragma once

#include "CoreMinimal.h"

namespace MotionWorld
{
constexpr double NetworkControlIntervalSeconds = 0.1;
constexpr double NetworkActionDeadlineSeconds = 0.1;
constexpr int32 NetworkHoldMissCount = 2;
constexpr int32 NetworkSafeStopMissCount = 3;

enum class ENetworkCommandCause : uint8
{
	None,
	AcceptedAction,
	DeadlineHold,
	DeadlineSafeStop
};

struct FNetworkCommandUpdate
{
	bool bShouldApply = false;
	FVector2D DesiredVelocityLocalCmPerSec = FVector2D::ZeroVector;
	int64 SourceObservationSequence = INDEX_NONE;
	ENetworkCommandCause Cause = ENetworkCommandCause::None;
};

struct FNetworkObservationDecision
{
	bool bShouldEmit = false;
	int64 EpisodeId = INDEX_NONE;
	int64 ObservationSequence = INDEX_NONE;
	bool bHasPreviousAction = false;
	int64 PreviousActionSourceObservationSequence = INDEX_NONE;
	FVector2D PreviousAppliedVelocityLocalCmPerSec = FVector2D::ZeroVector;
	FNetworkCommandUpdate ExpiryUpdate;
};

struct FNetworkRuntimeStats
{
	bool bEnabled = false;
	int64 EpisodeId = INDEX_NONE;
	int64 NextObservationSequence = 0;
	int64 CurrentOutstandingObservationSequence = INDEX_NONE;
	int64 ObservationsEmitted = 0;
	int64 ActionsAccepted = 0;
	int64 MissedResponses = 0;
	int64 HeldAfterMiss = 0;
	int64 SafeStops = 0;
	int32 ConsecutiveMisses = 0;
};

class MOTIONWORLD_API FNetworkRuntime
{
public:
	bool StartEpisode(int64 EpisodeId);
	void Stop();

	FNetworkObservationDecision ObserveFinalizedState(
		double SimulationTimeSeconds,
		double MonotonicNowSeconds,
		bool bStateValid,
		bool bIsResimulation);

	FNetworkCommandUpdate AdvanceDeadline(double MonotonicNowSeconds);
	FNetworkCommandUpdate AcceptAction(
		int64 EpisodeId,
		int64 SourceObservationSequence,
		const FVector2D& DesiredVelocityLocalCmPerSec,
		double MonotonicReceiveSeconds);

	bool HasOutstandingObservation() const { return bOutstanding; }
	bool WasOutstandingObservationAnswered() const { return bOutstandingAnswered; }
	int64 GetExpectedEpisodeId() const { return Stats.EpisodeId; }
	int64 GetExpectedObservationSequence() const
	{
		return Stats.CurrentOutstandingObservationSequence;
	}
	const FNetworkRuntimeStats& GetStats() const { return Stats; }

private:
	FNetworkCommandUpdate ExpireOutstanding();

	FNetworkRuntimeStats Stats;
	bool bHasEpoch = false;
	bool bOutstanding = false;
	bool bOutstandingAnswered = false;
	double EpochSimulationTimeSeconds = 0.0;
	double NextBoundarySimulationTimeSeconds = 0.0;
	double OutstandingDeadlineMonotonicSeconds = 0.0;
	FVector2D CurrentAppliedVelocityLocalCmPerSec = FVector2D::ZeroVector;
	int64 CurrentAppliedSourceObservationSequence = INDEX_NONE;
};
} // namespace MotionWorld
