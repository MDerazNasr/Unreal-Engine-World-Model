#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldControlVisualizationState.h"

#include <limits>

namespace
{
MotionWorld::FControlAction MakeAdmittedVisualizationAction(
	const int64 EpisodeId,
	const int64 SourceObservationSequence)
{
	MotionWorld::FControlAction Action;
	Action.EpisodeId = EpisodeId;
	Action.SourceObservationSequence = SourceObservationSequence;
	Action.bHasVisualization = true;
	Action.Visualization.EpisodeId = EpisodeId;
	Action.Visualization.SourceObservationSequence = SourceObservationSequence;
	MotionWorld::FControlVisualizationPath Path;
	Path.Role = TEXT("selected");
	Path.PointsWorldXYCm = {FVector2D(1.0, 2.0), FVector2D(3.0, 4.0)};
	Action.Visualization.Paths.Add(MoveTemp(Path));
	return Action;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldControlVisualizationStateTest,
	"MotionWorld.Control.VisualizationStateLifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldControlVisualizationStateTest::RunTest(const FString& Parameters)
{
	using namespace MotionWorld;
	FControlVisualizationState State;
	TestTrue(TEXT("Valid episode starts"), State.BeginEpisode(7101));
	TestTrue(TEXT("First authoritative observation is admitted"),
		State.OnAuthoritativeObservationEmitted(7101, 0));

	const FControlAction Current = MakeAdmittedVisualizationAction(7101, 0);
	TestTrue(TEXT("Current admitted action visualization installs"),
		State.InstallFromAdmittedAction(Current, 7101, 0));
	TestTrue(TEXT("Prediction is readable after installation"), State.HasPrediction());
	TestEqual(TEXT("Installed path is preserved"), State.GetPrediction().Paths.Num(), 1);
	TestTrue(TEXT("Authoritative position is admitted before invalid episode attempt"),
		State.AppendAuthoritativeFinalizedPosition(7101, FVector2D(0.25, 0.5)));
	const FControlVisualizationData PredictionBeforeInvalidBegin = State.GetPrediction();
	const TArray<FVector2D> TrailBeforeInvalidBegin = State.GetActualTrailWorldXYCm();
	TestFalse(TEXT("Negative episode is rejected"), State.BeginEpisode(-1));
	TestEqual(TEXT("Invalid episode does not change active identity"),
		State.GetActiveEpisodeId(), int64(7101));
	TestEqual(TEXT("Invalid episode does not change observation identity"),
		State.GetLatestObservationSequence(), int64(0));
	TestTrue(TEXT("Invalid episode does not clear prediction"), State.HasPrediction());
	TestEqual(TEXT("Invalid episode preserves prediction identity"),
		State.GetPrediction().SourceObservationSequence,
		PredictionBeforeInvalidBegin.SourceObservationSequence);
	TestTrue(TEXT("Invalid episode preserves the exact actual trail"),
		State.GetActualTrailWorldXYCm() == TrailBeforeInvalidBegin);

	FControlAction Stale = MakeAdmittedVisualizationAction(7101, 0);
	TestFalse(TEXT("Identity API rejects an action against a newer outstanding slot"),
		State.InstallFromAdmittedAction(Stale, 7101, 1));
	TestTrue(TEXT("Rejected installation does not mutate current prediction"), State.HasPrediction());
	TestFalse(TEXT("Wrong-episode action cannot install"),
		State.InstallFromAdmittedAction(MakeAdmittedVisualizationAction(7102, 0), 7101, 0));

	TestTrue(TEXT("Newer observation is admitted"),
		State.OnAuthoritativeObservationEmitted(7101, 1));
	TestFalse(TEXT("Newer observation clears the old prediction"), State.HasPrediction());
	TestFalse(TEXT("Stale action cannot install after the newer observation"),
		State.InstallFromAdmittedAction(Stale, 7101, 1));

	bool bAcceptedAllFiniteTrailPoints = true;
	for (int32 Index = 0; Index < MaxControlActualTrailPoints + 5; ++Index)
	{
		bAcceptedAllFiniteTrailPoints &=
			State.AppendAuthoritativeFinalizedPosition(7101, FVector2D(Index, -Index));
	}
	TestTrue(TEXT("Authoritative trail points are admitted"), bAcceptedAllFiniteTrailPoints);
	TestEqual(TEXT("Actual trail is bounded"),
		State.GetActualTrailWorldXYCm().Num(), MaxControlActualTrailPoints);
	TestTrue(TEXT("Bounded trail removes its oldest point"),
		State.GetActualTrailWorldXYCm()[0].Equals(FVector2D(5.0, -5.0)));
	const TArray<FVector2D> TrailBeforeRejectedAppend = State.GetActualTrailWorldXYCm();
	const int64 EpisodeBeforeRejectedAppend = State.GetActiveEpisodeId();
	const int64 ObservationBeforeRejectedAppend = State.GetLatestObservationSequence();
	TestFalse(TEXT("Non-finite actual position is rejected"),
		State.AppendAuthoritativeFinalizedPosition(
			7101,
			FVector2D(std::numeric_limits<double>::infinity(), 0.0)));
	TestFalse(TEXT("Wrong-episode actual position is rejected"),
		State.AppendAuthoritativeFinalizedPosition(7102, FVector2D::ZeroVector));
	TestTrue(TEXT("Rejected appends leave the exact trail unchanged"),
		State.GetActualTrailWorldXYCm() == TrailBeforeRejectedAppend);
	TestEqual(TEXT("Rejected appends preserve active episode"),
		State.GetActiveEpisodeId(), EpisodeBeforeRejectedAppend);
	TestEqual(TEXT("Rejected appends preserve observation identity"),
		State.GetLatestObservationSequence(), ObservationBeforeRejectedAppend);

	TestTrue(TEXT("Reset begins a new episode"), State.BeginEpisode(7102));
	TestFalse(TEXT("Reset clears prediction"), State.HasPrediction());
	TestEqual(TEXT("Reset clears actual trail"), State.GetActualTrailWorldXYCm().Num(), 0);
	TestEqual(TEXT("Reset replaces active episode identity"), State.GetActiveEpisodeId(), int64(7102));
	TestEqual(TEXT("Reset clears observation identity"), State.GetLatestObservationSequence(), int64(-1));

	TestTrue(TEXT("New episode observation is admitted"),
		State.OnAuthoritativeObservationEmitted(7102, 0));
	TestTrue(TEXT("New episode action installs"),
		State.InstallFromAdmittedAction(MakeAdmittedVisualizationAction(7102, 0), 7102, 0));
	TestTrue(TEXT("New episode actual point is admitted"),
		State.AppendAuthoritativeFinalizedPosition(7102, FVector2D(10.0, 20.0)));
	State.ClearPredictionForSafeStop();
	TestFalse(TEXT("Safe stop clears prediction"), State.HasPrediction());
	TestEqual(TEXT("Safe stop preserves active episode"), State.GetActiveEpisodeId(), int64(7102));
	TestEqual(TEXT("Safe stop preserves observation identity"),
		State.GetLatestObservationSequence(), int64(0));
	TestEqual(TEXT("Safe stop preserves actual trail"), State.GetActualTrailWorldXYCm().Num(), 1);
	TestTrue(TEXT("Same episode admits the next observation after safe stop"),
		State.OnAuthoritativeObservationEmitted(7102, 1));
	TestTrue(TEXT("Same episode admits a new action after safe stop"),
		State.InstallFromAdmittedAction(MakeAdmittedVisualizationAction(7102, 1), 7102, 1));

	State.InvalidateEpisodeBoundary();
	TestFalse(TEXT("Episode boundary clears prediction"), State.HasPrediction());
	TestEqual(TEXT("Episode boundary clears actual trail"), State.GetActualTrailWorldXYCm().Num(), 0);
	TestEqual(TEXT("Episode boundary invalidates active episode"),
		State.GetActiveEpisodeId(), int64(-1));
	TestEqual(TEXT("Episode boundary invalidates the outstanding observation"),
		State.GetLatestObservationSequence(), int64(-1));
	TestFalse(TEXT("Boundary prevents the old admitted action from being reinstalled"),
		State.InstallFromAdmittedAction(MakeAdmittedVisualizationAction(7102, 1), 7102, 1));
	TestFalse(TEXT("Boundary rejects an old authoritative trail append"),
		State.AppendAuthoritativeFinalizedPosition(7102, FVector2D(30.0, 40.0)));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
