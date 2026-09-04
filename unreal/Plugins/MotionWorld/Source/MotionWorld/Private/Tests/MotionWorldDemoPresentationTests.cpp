#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldDemoPresentation.h"

namespace
{
MotionWorld::FControlAction MakeOverlayAction()
{
	MotionWorld::FControlAction Action;
	Action.EpisodeId = 7603;
	Action.SourceObservationSequence = 14;
	Action.ControllerId = TEXT("nominal_mpc");
	Action.ModelId = TEXT("selected_no_history_residual");
	Action.PlannerMeasuredLatencyMs = 28.24;
	Action.bHasVisualization = true;
	Action.Visualization.EpisodeId = Action.EpisodeId;
	Action.Visualization.SourceObservationSequence = Action.SourceObservationSequence;
	Action.Visualization.HorizonSeconds = 0.5;
	Action.Visualization.TimestepSeconds = 0.1;
	for (const TCHAR* Role : {TEXT("nominal"), TEXT("residual")})
	{
		MotionWorld::FControlVisualizationPath Path;
		Path.Role = Role;
		Path.PointsWorldXYCm = {FVector2D::ZeroVector, FVector2D(10.0, 0.0)};
		Action.Visualization.Paths.Add(MoveTemp(Path));
	}
	return Action;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldDemoPresentationTest,
	"MotionWorld.Control.DemoPresentation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldDemoPresentationTest::RunTest(const FString& Parameters)
{
	MotionWorld::FControlVisualizationState State;
	TestTrue(TEXT("Episode starts"), State.BeginEpisode(7603));
	TestTrue(TEXT("Observation becomes current"), State.OnAuthoritativeObservationEmitted(7603, 14));
	TestTrue(TEXT("Overlay installs"), State.InstallFromAdmittedAction(MakeOverlayAction(), 7603, 14));

	MotionWorld::FDemoPresentationContext Context;
	Context.bNetworkEnabled = true;
	Context.bHasTarget = true;
	Context.ConfiguredControllerMode = TEXT("nominal_mpc");
	Context.LastEndToEndLatencyMs = 57.75;
	Context.ActionsAccepted = 15;
	const MotionWorld::FDemoPresentation Presentation =
		MotionWorld::BuildDemoPresentation(State, Context);
	TestTrue(TEXT("Nominal role is detected"), Presentation.bHasNominal);
	TestTrue(TEXT("Residual role is detected"), Presentation.bHasResidual);
	TestFalse(TEXT("Absent selected role is not claimed"), Presentation.bHasSelected);
	TestTrue(TEXT("Nominal controller ownership is explicit"),
		Presentation.HudText.Contains(TEXT("CONTROL: nominal_mpc owns action")));
	TestTrue(TEXT("Residual is labelled as a prediction"),
		Presentation.HudText.Contains(TEXT("ORANGE learned-residual prediction")));
	TestTrue(TEXT("Authoritative actual trail is labelled"),
		Presentation.HudText.Contains(TEXT("YELLOW actual Unreal trail")));
	TestTrue(TEXT("Exact source identity is visible"),
		Presentation.HudText.Contains(TEXT("episode 7603 / observation 14")));
	TestTrue(TEXT("Timing distinguishes planner and Unreal round trip"),
		Presentation.HudText.Contains(TEXT("planner 28.2ms | Unreal round-trip 57.8ms")));

	State.OnAuthoritativeObservationEmitted(7603, 15);
	const MotionWorld::FDemoPresentation Awaiting =
		MotionWorld::BuildDemoPresentation(State, Context);
	TestTrue(TEXT("Expired prediction is not presented as current"),
		Awaiting.HudText.Contains(TEXT("awaiting a current admitted prediction")));
	TestFalse(TEXT("Expired nominal path is not claimed"), Awaiting.bHasNominal);
	TestFalse(TEXT("Expired residual path is not claimed"), Awaiting.bHasResidual);

	MotionWorld::FControlAction FallbackAction = MakeOverlayAction();
	FallbackAction.SourceObservationSequence = 15;
	FallbackAction.Visualization.SourceObservationSequence = 15;
	FallbackAction.bIsSafeFallback = true;
	FallbackAction.FallbackReason = TEXT("no_feasible_candidate");
	TestTrue(TEXT("Fallback overlay installs"),
		State.InstallFromAdmittedAction(FallbackAction, 7603, 15));
	const MotionWorld::FDemoPresentation Fallback =
		MotionWorld::BuildDemoPresentation(State, Context);
	TestTrue(TEXT("Fallback is explicit"),
		Fallback.HudText.Contains(TEXT("SAFETY: FALLBACK - no_feasible_candidate")));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
