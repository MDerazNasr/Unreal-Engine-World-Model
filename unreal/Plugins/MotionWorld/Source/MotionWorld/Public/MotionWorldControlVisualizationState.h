#pragma once

#include "CoreMinimal.h"
#include "MotionWorldControlAction.h"

namespace MotionWorld
{
constexpr int32 MaxControlActualTrailPoints = 256;

/**
 * Game-thread-owned visualization state with the same episode/observation boundary as control.
 *
 * The renderer reads this object, but cannot install unvalidated packet data directly. Callers
 * first admit an action through the control runtime, then present that action here alongside the
 * currently outstanding authoritative observation identity.
 */
class MOTIONWORLD_API FControlVisualizationState
{
public:
	/** Start a new authoritative episode and discard every path from the previous one. */
	bool BeginEpisode(int64 EpisodeId);

	/** Record that Unreal emitted a finalized observation. Newer observations expire predictions. */
	bool OnAuthoritativeObservationEmitted(int64 EpisodeId, int64 ObservationSequence);

	/** Install visualization only when every identity matches the outstanding observation. */
	bool InstallFromAdmittedAction(
		const FControlAction& AdmittedAction,
		int64 OutstandingEpisodeId,
		int64 OutstandingObservationSequence);

	/** Add one authoritative, collision-finalized world position to the bounded actual trail. */
	bool AppendAuthoritativeFinalizedPosition(int64 EpisodeId, const FVector2D& PositionWorldXYCm);

	/**
	 * Invalidate the current episode at reset, reconnect, controller switch, EndPlay, or any
	 * equivalent identity boundary. Every path and identity is discarded.
	 */
	void InvalidateEpisodeBoundary();

	/**
	 * Clear only the current prediction when the controller enters a safe stop. The authoritative
	 * episode, latest observation, and actual trail survive so the same episode can recover.
	 */
	void ClearPredictionForSafeStop();

	bool HasPrediction() const { return bHasPrediction; }
	const FControlVisualizationData& GetPrediction() const { return Prediction; }
	/** Exact admitted action that owns the current prediction and its telemetry. */
	const FControlAction& GetPredictionSourceAction() const { return PredictionSourceAction; }
	const TArray<FVector2D>& GetActualTrailWorldXYCm() const { return ActualTrailWorldXYCm; }
	int64 GetActiveEpisodeId() const { return ActiveEpisodeId; }
	int64 GetLatestObservationSequence() const { return LatestObservationSequence; }

private:
	void ClearPrediction();

	int64 ActiveEpisodeId = -1;
	int64 LatestObservationSequence = -1;
	bool bHasPrediction = false;
	FControlVisualizationData Prediction;
	FControlAction PredictionSourceAction;
	TArray<FVector2D> ActualTrailWorldXYCm;
};
} // namespace MotionWorld
