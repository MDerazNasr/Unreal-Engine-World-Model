#pragma once

#include "CoreMinimal.h"

namespace MotionWorld
{
constexpr int64 MaxSafeJsonInteger = 9007199254740991LL;
constexpr int32 MaxControlActionBytes = 8192;
constexpr int32 MaxControlTrajectorySteps = 32;

enum class EControlActionRejection : uint8
{
	None,
	Empty,
	Oversized,
	InvalidUtf8,
	InvalidJson,
	DuplicateJsonKey,
	InvalidSchema,
	WrongEpisode,
	FutureObservation,
	StaleObservation,
	DuplicateObservation
};

struct FControlCostBreakdown
{
	double TerminalGoalDistanceCm = 0.0;
	double CollisionIndicator = 0.0;
	double ClearanceDeficitSquaredCm2 = 0.0;
	double ActionChangeSquaredCm2PerS2 = 0.0;
	double ActionSecondDifferenceSquaredCm2PerS2 = 0.0;
	double Total = 0.0;
};

struct FControlAction
{
	int64 EpisodeId = 0;
	int64 SourceObservationSequence = 0;
	FVector2D DesiredVelocityLocalCmPerSec = FVector2D::ZeroVector;
	FString ControllerId;
	FString ModelId;
	int64 PlannerStartedMonotonicUs = 0;
	int64 PlannerFinishedMonotonicUs = 0;
	double PlannerMeasuredLatencyMs = 0.0;
	bool bIsSafeFallback = false;
	FString FallbackReason;
	bool bHasTelemetry = false;
	TArray<FVector2D> SelectedTrajectoryLocalCmPerSec;
	FControlCostBreakdown CostBreakdown;
};

/** Parse and admit one Python action for exactly one outstanding Unreal observation. */
MOTIONWORLD_API bool ParseAndValidateControlAction(
	TConstArrayView<uint8> Payload,
	int64 ExpectedEpisodeId,
	int64 ExpectedObservationSequence,
	bool bObservationAlreadyAccepted,
	FControlAction& OutAction,
	EControlActionRejection& OutRejection);

/** Stable bounded diagnostic label; never contains packet or checkpoint bytes. */
MOTIONWORLD_API const TCHAR* LexToString(EControlActionRejection Rejection);
} // namespace MotionWorld
