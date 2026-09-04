#include "MotionWorldControlVisualizationState.h"

namespace MotionWorld
{
bool FControlVisualizationState::BeginEpisode(const int64 EpisodeId)
{
	if (EpisodeId < 0 || EpisodeId > MaxSafeJsonInteger)
	{
		return false;
	}

	InvalidateEpisodeBoundary();
	ActiveEpisodeId = EpisodeId;
	return true;
}

bool FControlVisualizationState::OnAuthoritativeObservationEmitted(
	const int64 EpisodeId,
	const int64 ObservationSequence)
{
	if (EpisodeId != ActiveEpisodeId
		|| ObservationSequence < 0
		|| ObservationSequence > MaxSafeJsonInteger
		|| ObservationSequence <= LatestObservationSequence)
	{
		return false;
	}

	if (bHasPrediction && Prediction.SourceObservationSequence < ObservationSequence)
	{
		ClearPrediction();
	}
	LatestObservationSequence = ObservationSequence;
	return true;
}

bool FControlVisualizationState::InstallFromAdmittedAction(
	const FControlAction& AdmittedAction,
	const int64 OutstandingEpisodeId,
	const int64 OutstandingObservationSequence)
{
	if (!AdmittedAction.bHasVisualization
		|| OutstandingEpisodeId != ActiveEpisodeId
		|| OutstandingObservationSequence != LatestObservationSequence
		|| AdmittedAction.EpisodeId != OutstandingEpisodeId
		|| AdmittedAction.SourceObservationSequence != OutstandingObservationSequence
		|| AdmittedAction.Visualization.EpisodeId != OutstandingEpisodeId
		|| AdmittedAction.Visualization.SourceObservationSequence != OutstandingObservationSequence)
	{
		return false;
	}

	Prediction = AdmittedAction.Visualization;
	PredictionSourceAction = AdmittedAction;
	bHasPrediction = true;
	return true;
}

bool FControlVisualizationState::AppendAuthoritativeFinalizedPosition(
	const int64 EpisodeId,
	const FVector2D& PositionWorldXYCm)
{
	if (EpisodeId != ActiveEpisodeId
		|| !FMath::IsFinite(PositionWorldXYCm.X)
		|| !FMath::IsFinite(PositionWorldXYCm.Y))
	{
		return false;
	}

	ActualTrailWorldXYCm.Add(PositionWorldXYCm);
	const int32 Overflow = ActualTrailWorldXYCm.Num() - MaxControlActualTrailPoints;
	if (Overflow > 0)
	{
		ActualTrailWorldXYCm.RemoveAt(0, Overflow, EAllowShrinking::No);
	}
	return true;
}

void FControlVisualizationState::InvalidateEpisodeBoundary()
{
	ClearPrediction();
	ActualTrailWorldXYCm.Reset();
	ActiveEpisodeId = -1;
	LatestObservationSequence = -1;
}

void FControlVisualizationState::ClearPredictionForSafeStop()
{
	ClearPrediction();
}

void FControlVisualizationState::ClearPrediction()
{
	bHasPrediction = false;
	Prediction = FControlVisualizationData();
	PredictionSourceAction = FControlAction();
}
} // namespace MotionWorld
