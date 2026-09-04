#include "MotionWorldDemoPresentation.h"

namespace
{
bool HasRole(
	const MotionWorld::FControlVisualizationState& VisualizationState,
	const TCHAR* Role)
{
	if (!VisualizationState.HasPrediction())
	{
		return false;
	}
	for (const MotionWorld::FControlVisualizationPath& Path
		: VisualizationState.GetPrediction().Paths)
	{
		if (Path.Role == Role)
		{
			return true;
		}
	}
	return false;
}
} // namespace

namespace MotionWorld
{
FDemoPresentation BuildDemoPresentation(
	const FControlVisualizationState& VisualizationState,
	const FDemoPresentationContext& Context)
{
	FDemoPresentation Result;
	Result.bHasCemCandidate = HasRole(VisualizationState, TEXT("cem_candidate"));
	Result.bHasSelected = HasRole(VisualizationState, TEXT("selected"));
	Result.bHasNominal = HasRole(VisualizationState, TEXT("nominal"));
	Result.bHasResidual = HasRole(VisualizationState, TEXT("residual"));

	const TCHAR* ViewStatus = Context.bWorldPaused
		? TEXT("PAUSED VIEW - latest admitted snapshot retained")
		: (Context.bNetworkEnabled ? TEXT("LIVE") : TEXT("STOPPED"));
	Result.HudText = FString::Printf(
		TEXT("MOTIONWORLD | ACTION-CONDITIONED MOVEMENT WORLD MODEL\n%s | OBSERVE > IMAGINE > CHOOSE > EXECUTE FIRST ACTION > REPLAN"),
		ViewStatus);

	if (!VisualizationState.HasPrediction())
	{
		Result.HudText += FString::Printf(
			TEXT("\nCONTROL: %s | awaiting a current admitted prediction\nSAFETY: actions=%lld | safe stops=%lld"),
			*Context.ConfiguredControllerMode,
			Context.ActionsAccepted,
			Context.SafeStops);
		Result.StatusColor = Context.bNetworkEnabled
			? FColor(255, 220, 80)
			: FColor(200, 200, 200);
		return Result;
	}

	const FControlVisualizationData& Prediction = VisualizationState.GetPrediction();
	const FControlAction& Action = VisualizationState.GetPredictionSourceAction();
	Result.HudText += FString::Printf(
		TEXT("\nCONTROL: %s owns action | MODEL: %s\nSOURCE: episode %lld / observation %lld | horizon %.2fs @ dt %.2fs"),
		*Action.ControllerId,
		*Action.ModelId,
		Prediction.EpisodeId,
		Prediction.SourceObservationSequence,
		Prediction.HorizonSeconds,
		Prediction.TimestepSeconds);

	TArray<FString> LegendItems;
	if (Result.bHasCemCandidate)
	{
		LegendItems.Add(TEXT("GRAY candidate futures"));
	}
	if (Result.bHasSelected)
	{
		LegendItems.Add(TEXT("GREEN selected future"));
	}
	if (Result.bHasNominal)
	{
		LegendItems.Add(TEXT("BLUE nominal prediction"));
	}
	if (Result.bHasResidual)
	{
		LegendItems.Add(TEXT("ORANGE learned-residual prediction"));
	}
	LegendItems.Add(TEXT("YELLOW actual Unreal trail"));
	if (Context.bHasTarget)
	{
		LegendItems.Add(TEXT("LIME target"));
	}
	Result.HudText += TEXT("\n") + FString::Join(LegendItems, TEXT(" | "));

	const FString EndToEndText = Context.LastEndToEndLatencyMs >= 0.0
		? FString::Printf(TEXT("%.1fms"), Context.LastEndToEndLatencyMs)
		: TEXT("pending");
	Result.HudText += FString::Printf(
		TEXT("\nTIMING: planner %.1fms | Unreal round-trip %s | current identity admitted"),
		Action.PlannerMeasuredLatencyMs,
		*EndToEndText);
	if (Action.bIsSafeFallback)
	{
		Result.HudText += FString::Printf(
			TEXT("\nSAFETY: FALLBACK - %s"),
			*Action.FallbackReason);
		Result.StatusColor = FColor(255, 128, 0);
	}
	else
	{
		Result.HudText += FString::Printf(
			TEXT("\nSAFETY: before deadline | actions=%lld | safe stops=%lld"),
			Context.ActionsAccepted,
			Context.SafeStops);
		Result.StatusColor = FColor(120, 255, 160);
	}
	return Result;
}
} // namespace MotionWorld
