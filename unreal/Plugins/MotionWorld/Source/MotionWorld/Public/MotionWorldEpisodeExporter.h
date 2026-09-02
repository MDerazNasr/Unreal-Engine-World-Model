#pragma once

#include "CoreMinimal.h"
#include "MotionWorldEpisodeRecorder.h"
#include "MotionWorldTimedGate.h"

namespace MotionWorld
{
constexpr int32 EpisodeFileSchemaVersion = 3;

struct FTimedGateEpisodeMetadata
{
	bool bIsPresent = false;
	FMotionWorldTimedGateConfig Config;
	double ScenarioStartSimulationTimeSeconds = 0.0;
	EMotionWorldScenarioTerminationReason TerminationReason =
		EMotionWorldScenarioTerminationReason::None;
	double TerminationScenarioTimeSeconds = 0.0;
	int64 CollisionCount = 0;
};

enum class EEpisodeExportResult : uint8
{
	Succeeded,
	InvalidOutputPath,
	InvalidStats,
	NoTransitions,
	InvalidTransition,
	DirectoryCreationFailed,
	DestinationExists,
	TemporaryFileOpenFailed,
	WriteFailed,
	AtomicMoveFailed
};

struct FEpisodeExportRequest
{
	FString OutputFilePath;
	FString CreatedUtcIso8601;
	FString EngineVersion;
	FString ProjectName;
	FMotionWorldEpisodeRecorderStats Stats;
	TConstArrayView<FMotionWorldTransitionSample> Transitions;
	FTimedGateEpisodeMetadata TimedGateScenario;
};

struct FEpisodeExportOutcome
{
	EEpisodeExportResult Result = EEpisodeExportResult::InvalidStats;
	FString OutputFilePath;
	FString Detail;
	int64 ExportedTransitionCount = 0;

	bool Succeeded() const { return Result == EEpisodeExportResult::Succeeded; }
};

/**
 * Validates and atomically writes one completed episode as UTF-8 JSON Lines.
 * The destination is never replaced, and a partial temporary file is never accepted as data.
 */
MOTIONWORLD_API FEpisodeExportOutcome ExportEpisodeJsonLines(
	const FEpisodeExportRequest& Request);

MOTIONWORLD_API const TCHAR* LexToString(EEpisodeExportResult Result);
} // namespace MotionWorld
