#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldNetworkRuntime.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldNetworkRuntimeTest,
	"MotionWorld.Network.RuntimeLifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldNetworkRuntimeTest::RunTest(const FString& Parameters)
{
	using namespace MotionWorld;
	TestTrue(TEXT("Network owns command when varied schedule is off"),
		IsNetworkActionProducerConfigurationValid(false));
	TestFalse(TEXT("Competing varied schedule is rejected"),
		IsNetworkActionProducerConfigurationValid(true));
	FNetworkRuntime Runtime;
	TestFalse(TEXT("Negative episode is rejected"), Runtime.StartEpisode(-1));
	TestTrue(TEXT("Episode starts"), Runtime.StartEpisode(7101));

	FNetworkObservationDecision Observation = Runtime.ObserveFinalizedState(5.0, 10.0, true, false);
	TestTrue(TEXT("First valid finalize emits slot zero"), Observation.bShouldEmit);
	TestEqual(TEXT("First sequence is zero"), Observation.ObservationSequence, int64(0));
	TestFalse(TEXT("Slot zero has no previous action"), Observation.bHasPreviousAction);
	TestFalse(
		TEXT("No early extra observation"),
		Runtime.ObserveFinalizedState(5.099, 10.099, true, false).bShouldEmit);
	Observation = Runtime.ObserveFinalizedState(5.1, 10.1, true, false);
	TestTrue(TEXT("Boundary emits once"), Observation.bShouldEmit);
	TestEqual(TEXT("Second emission increments once"), Observation.ObservationSequence, int64(1));
	Observation = Runtime.ObserveFinalizedState(5.39, 10.39, true, false);
	TestTrue(TEXT("Jump emits latest elapsed slot only"), Observation.bShouldEmit);
	TestEqual(TEXT("Skipped time does not create phantom sequences"), Observation.ObservationSequence, int64(2));
	TestFalse(
		TEXT("Same elapsed slot cannot burst"),
		Runtime.ObserveFinalizedState(5.399, 10.399, true, false).bShouldEmit);

	Runtime.StartEpisode(7102);
	Observation = Runtime.ObserveFinalizedState(1.0, 20.0, true, false);
	const FNetworkCommandUpdate Accepted = Runtime.AcceptAction(
		7102, 0, FVector2D(120.0, -30.0), 20.05);
	TestTrue(TEXT("Current action before exclusive deadline is accepted"), Accepted.bShouldApply);
	TestEqual(TEXT("Accepted action cause is explicit"), Accepted.Cause, ENetworkCommandCause::AcceptedAction);

	Observation = Runtime.ObserveFinalizedState(1.1, 20.1, true, false);
	TestTrue(TEXT("Next observation carries previous action"), Observation.bHasPreviousAction);
	TestEqual(TEXT("Previous action identity is exact"), Observation.PreviousActionSourceObservationSequence, int64(0));
	TestTrue(TEXT("Previous action value is exact"), Observation.PreviousAppliedVelocityLocalCmPerSec.Equals(FVector2D(120.0, -30.0)));
	FNetworkCommandUpdate Miss = Runtime.AdvanceDeadline(20.201);
	TestEqual(TEXT("First miss holds"), Miss.Cause, ENetworkCommandCause::DeadlineHold);
	TestTrue(TEXT("First miss holds last value"), Miss.DesiredVelocityLocalCmPerSec.Equals(FVector2D(120.0, -30.0)));

	Runtime.ObserveFinalizedState(1.2, 20.201, true, false);
	Miss = Runtime.AdvanceDeadline(20.302);
	TestEqual(TEXT("Second miss still holds"), Miss.Cause, ENetworkCommandCause::DeadlineHold);
	Runtime.ObserveFinalizedState(1.3, 20.302, true, false);
	Miss = Runtime.AdvanceDeadline(20.403);
	TestEqual(TEXT("Third miss safe stops"), Miss.Cause, ENetworkCommandCause::DeadlineSafeStop);
	TestTrue(TEXT("Third miss commands exact zero"), Miss.DesiredVelocityLocalCmPerSec.IsZero());
	TestEqual(TEXT("Three misses counted"), Runtime.GetStats().MissedResponses, int64(3));

	Runtime.StartEpisode(7103);
	Runtime.ObserveFinalizedState(2.0, 30.0, true, false);
	TestFalse(
		TEXT("Exclusive deadline rejects exact-boundary action"),
		Runtime.AcceptAction(7103, 0, FVector2D(1.0, 0.0), 30.1).bShouldApply);
	TestFalse(
		TEXT("Wrong episode is rejected"),
		Runtime.AcceptAction(7104, 0, FVector2D(1.0, 0.0), 30.05).bShouldApply);
	Runtime.Stop();
	TestFalse(TEXT("Stopped runtime emits nothing"), Runtime.ObserveFinalizedState(3.0, 40.0, true, false).bShouldEmit);
	TestFalse(TEXT("Stopped runtime is disabled"), Runtime.GetStats().bEnabled);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
