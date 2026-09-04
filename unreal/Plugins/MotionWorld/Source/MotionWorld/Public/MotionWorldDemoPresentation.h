#pragma once

#include "CoreMinimal.h"
#include "MotionWorldControlVisualizationState.h"

namespace MotionWorld
{
/** Runtime facts used to label the demo without making claims beyond admitted telemetry. */
struct FDemoPresentationContext
{
	bool bNetworkEnabled = false;
	bool bWorldPaused = false;
	bool bHasTarget = false;
	FString ConfiguredControllerMode;
	double LastEndToEndLatencyMs = -1.0;
	int64 ActionsAccepted = 0;
	int64 SafeStops = 0;
};

struct FDemoPresentation
{
	FString HudText;
	FColor StatusColor = FColor::White;
	bool bHasCemCandidate = false;
	bool bHasSelected = false;
	bool bHasNominal = false;
	bool bHasResidual = false;
};

/** Build the compact interview HUD exclusively from current admitted visualization state. */
MOTIONWORLD_API FDemoPresentation BuildDemoPresentation(
	const FControlVisualizationState& VisualizationState,
	const FDemoPresentationContext& Context);
} // namespace MotionWorld
