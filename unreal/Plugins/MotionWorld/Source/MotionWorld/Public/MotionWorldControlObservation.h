#pragma once

#include "CoreMinimal.h"
#include "MotionWorldNominalContext.h"
#include "MotionWorldStateSample.h"

namespace MotionWorld
{
struct FControlObservation
{
	int64 EpisodeId = INDEX_NONE;
	int64 ObservationSequence = INDEX_NONE;
	FString ControllerMode = TEXT("echo");
	FMotionWorldStateSample State;
	FMotionWorldNominalContextSample NominalContext;
	bool bHasPreviousAction = false;
	int64 PreviousActionSourceObservationSequence = INDEX_NONE;
	FVector2D PreviousAppliedVelocityLocalCmPerSec = FVector2D::ZeroVector;
	bool bHasTarget = false;
	FVector TargetPositionWorldCm = FVector::ZeroVector;
	FVector2D DesiredTerminalVelocityLocalCmPerSec = FVector2D::ZeroVector;
	FString ScenarioId = TEXT("network_vertical_slice");
	int64 ScenarioSeed = 0;
	FString ResetId;
};

/** Build one bounded UTF-8 v1 observation accepted by Python's strict decoder. */
MOTIONWORLD_API bool SerializeControlObservation(
	const FControlObservation& Observation,
	TArray<uint8>& OutPayload,
	FString& OutFailureReason);
} // namespace MotionWorld
