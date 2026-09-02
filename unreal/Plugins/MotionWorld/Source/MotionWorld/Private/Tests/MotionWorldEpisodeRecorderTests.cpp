#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldEpisodeRecorder.h"

namespace
{
FMotionWorldStateSample MakeRecorderState(
	const int64 SampleSequence,
	const int32 MoverFrame,
	const double SimulationTimeSeconds,
	const double FacingYawDegrees = 90.0)
{
	FMotionWorldStateSample State;
	State.SampleSequence = SampleSequence;
	State.MoverStepServerFrame = MoverFrame;
	State.SimulationTimeSeconds = SimulationTimeSeconds;
	State.StepSeconds = 0.050;
	State.bIsValid = true;
	State.MovementMode = TEXT("Walking");
	State.FacingYawDegrees = FacingYawDegrees;
	const double YawRadians = FMath::DegreesToRadians(FacingYawDegrees);
	State.FacingUnitWorld = FVector2D(FMath::Cos(YawRadians), FMath::Sin(YawRadians));
	return State;
}

FMotionWorldNominalContextSample MakeRecorderContext(const int64 SampleSequence)
{
	FMotionWorldNominalContextSample Context;
	Context.bIsValid = true;
	Context.AuthoritativeStateSampleSequence = SampleSequence;
	Context.MovementModeName = TEXT("Walking");
	Context.MovementModeClass = TEXT("BP_MovementMode_Walking_C");
	Context.Parameters.AccelerationCmPerSecSquared = 500.0;
	Context.Parameters.DecelerationCmPerSecSquared = 300.0;
	Context.Parameters.DirectionalAccelerationFactor = 1.0;
	Context.Parameters.TurningStrength = 8.0;
	Context.Parameters.AccelerationSmoothingTimeSeconds = 0.1;
	Context.Parameters.DecelerationSmoothingTimeSeconds = 0.1;
	Context.Parameters.VelocityDeadzoneCmPerSec = 0.01;
	Context.Parameters.AccelerationDeadzoneCmPerSecSquared = 0.001;
	Context.Parameters.OutsideInfluenceSmoothingTimeSeconds = 0.05;
	Context.Parameters.FacingSmoothingTimeSeconds = 0.2;
	Context.Parameters.FacingDeadzoneDegrees = 0.1;
	Context.Parameters.AngularVelocityDeadzoneDegreesPerSec = 0.01;
	return Context;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldEpisodeRecorderTest,
	"MotionWorld.Episode.InMemoryRecorder",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldEpisodeRecorderTest::RunTest(const FString& Parameters)
{
	MotionWorld::FInMemoryEpisodeRecorder Recorder;
	const FVector WorldVelocity(0.0, 200.0, 0.0);

	TestEqual(
		TEXT("Observations are ignored until an episode starts"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(10, 20, 1.000),
			MakeRecorderContext(10),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::IgnoredNotRecording);
	TestFalse(TEXT("Negative episode IDs fail closed"), Recorder.StartEpisode(-1, 2));
	TestFalse(TEXT("Zero capacity fails closed"), Recorder.StartEpisode(7, 0));
	TestFalse(TEXT("Unbounded-looking capacity is rejected"), Recorder.StartEpisode(7, 100001));

	TestTrue(TEXT("A bounded episode starts"), Recorder.StartEpisode(7, 2));
	TestEqual(
		TEXT("The first eligible state seeds but does not create a transition"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(10, 20, 1.000),
			MakeRecorderContext(10),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::Seeded);
	TestEqual(
		TEXT("Seeding stores no row"),
		Recorder.GetTransitions().Num(),
		0);

	TestEqual(
		TEXT("The next state records one causal transition"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(11, 21, 1.050),
			MakeRecorderContext(11),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::Recorded);
	const FMotionWorldTransitionSample& First = Recorder.GetTransitions()[0];
	TestEqual(TEXT("Episode identity reaches the row"), First.EpisodeId, int64(7));
	TestEqual(TEXT("First attempted pair has sequence zero"), First.TransitionSequence, int64(0));
	TestEqual(TEXT("Previous endpoint is the seed"), First.PreviousState.SampleSequence, int64(10));
	TestEqual(TEXT("Next endpoint is the new state"), First.NextState.SampleSequence, int64(11));
	TestTrue(
		TEXT("World +Y becomes local forward in previous yaw-90 coordinates"),
		First.AppliedAction.VelocityLocalPlanarCmPerSec.Equals(
			FVector(200.0, 0.0, 0.0),
			1.e-6));

	TestEqual(
		TEXT("Unsupported human-style directional input is rejected"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(12, 22, 1.100),
			MakeRecorderContext(12),
			false,
			false,
			FVector::ZeroVector),
		EMotionWorldRecorderObservationResult::RejectedTransition);
	TestEqual(
		TEXT("The rejection reason is counted"),
		Recorder.GetRejectionCount(
			EMotionWorldTransitionRejectionReason::UnsupportedActionType),
		int64(1));

	TestEqual(
		TEXT("A valid current state becomes the recovery seed"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(13, 23, 1.150),
			MakeRecorderContext(13),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::Recorded);
	TestEqual(
		TEXT("Rejected attempts leave a visible transition-sequence gap"),
		Recorder.GetTransitions()[1].TransitionSequence,
		int64(2));
	TestEqual(
		TEXT("Recovery starts from the state after the rejected action"),
		Recorder.GetTransitions()[1].PreviousState.SampleSequence,
		int64(12));

	TestEqual(
		TEXT("The first row beyond capacity stops instead of overwriting"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(14, 24, 1.200),
			MakeRecorderContext(14),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::StoppedBufferFull);
	const FMotionWorldEpisodeRecorderStats FullStats = Recorder.GetStats();
	TestFalse(TEXT("Capacity overflow stops recording"), FullStats.bIsRecording);
	TestEqual(TEXT("Two rows remain stored"), Recorder.GetTransitions().Num(), 2);
	TestEqual(TEXT("Four pairs were attempted"), FullStats.AttemptedTransitionCount, int64(4));
	TestEqual(TEXT("Two pairs were recorded"), FullStats.RecordedTransitionCount, int64(2));
	TestEqual(TEXT("One pair was rejected"), FullStats.RejectedTransitionCount, int64(1));
	TestEqual(TEXT("One valid pair was dropped at capacity"), FullStats.CapacityDropCount, int64(1));

	TestTrue(TEXT("Starting a new episode clears old evidence"), Recorder.StartEpisode(9, 2));
	FMotionWorldStateSample InvalidSeed = MakeRecorderState(50, 60, 2.000);
	InvalidSeed.bIsValid = false;
	TestEqual(
		TEXT("An invalid initial state cannot seed an episode"),
		Recorder.ObserveFinalizedStep(
			InvalidSeed,
			MakeRecorderContext(50),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::RejectedSeed);
	TestEqual(TEXT("Restart cleared stored rows"), Recorder.GetTransitions().Num(), 0);
	TestEqual(
		TEXT("Invalid seed rejection is counted separately"),
		Recorder.GetStats().RejectedSeedStateCount,
		int64(1));

	TestEqual(
		TEXT("The next valid state can seed after an invalid one"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(50, 60, 2.000),
			MakeRecorderContext(50),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::Seeded);
	FMotionWorldStateSample Resimulated = MakeRecorderState(51, 61, 2.050);
	Resimulated.bIsResimulation = true;
	TestEqual(
		TEXT("A resimulated endpoint rejects the pair"),
		Recorder.ObserveFinalizedStep(
			Resimulated,
			MakeRecorderContext(51),
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::RejectedTransition);
	TestFalse(
		TEXT("A resimulated endpoint is never retained as the next seed"),
		Recorder.GetStats().bHasSeedState);
	TestEqual(
		TEXT("Resimulation rejection is counted"),
		Recorder.GetRejectionCount(EMotionWorldTransitionRejectionReason::Resimulation),
		int64(1));

	TestTrue(TEXT("A new episode starts for context rejection"), Recorder.StartEpisode(10, 2));
	FMotionWorldNominalContextSample MisalignedSeed = MakeRecorderContext(70);
	MisalignedSeed.AuthoritativeStateSampleSequence = 69;
	TestEqual(
		TEXT("A mismatched hidden-state frame cannot seed an episode"),
		Recorder.ObserveFinalizedStep(
			MakeRecorderState(70, 80, 3.000),
			MisalignedSeed,
			true,
			true,
			WorldVelocity),
		EMotionWorldRecorderObservationResult::RejectedSeed);
	TestEqual(
		TEXT("Context mismatch is counted explicitly"),
		Recorder.GetRejectionCount(
			EMotionWorldTransitionRejectionReason::NominalContextStateMismatch),
		int64(1));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
