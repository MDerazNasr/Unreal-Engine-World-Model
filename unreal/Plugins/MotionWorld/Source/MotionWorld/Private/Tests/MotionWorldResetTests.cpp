#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldReset.h"

namespace
{
FMotionWorldStateSample MakeResetState(
	const int64 Sequence = 10,
	const double FacingYawDegrees = 179.0)
{
	FMotionWorldStateSample State;
	State.SampleSequence = Sequence;
	State.MoverStepServerFrame = 20;
	State.SimulationTimeSeconds = 1.0;
	State.StepSeconds = 0.05;
	State.bIsValid = true;
	State.MovementMode = TEXT("Walking");
	State.PositionWorldCm = FVector(100.0, -50.0, 88.0);
	State.FacingYawDegrees = FacingYawDegrees;
	return State;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldResetVerifierTest,
	"MotionWorld.Reset.FinalizedVerifier",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldResetVerifierTest::RunTest(const FString& Parameters)
{
	const FMotionWorldStateSample Anchor = MakeResetState();
	const FMotionWorldResetTarget Target = MotionWorld::BuildResetTarget(Anchor);
	FMotionWorldResetTolerances Tolerances;

	TestTrue(TEXT("A valid ordinary state creates an anchor"), Target.bIsValid);
	TestEqual(TEXT("Anchor retains source identity"), Target.SourceStateSequence, int64(10));
	TestEqual(TEXT("Anchor retains movement mode"), Target.MovementMode, FName(TEXT("Walking")));

	FMotionWorldStateSample Exact = MakeResetState(11, 179.0);
	TestEqual(
		TEXT("Exact stationary state passes"),
		MotionWorld::CheckFinalizedResetState(Target, Exact, Tolerances).Result,
		EMotionWorldResetCheckResult::Passed);

	FMotionWorldStateSample WrappedYaw = MakeResetState(11, -179.0);
	Tolerances.FacingDegrees = 2.0;
	TestEqual(
		TEXT("Yaw comparison uses shortest wrapped angle at the boundary"),
		MotionWorld::CheckFinalizedResetState(Target, WrappedYaw, Tolerances).Result,
		EMotionWorldResetCheckResult::Passed);
	Tolerances.FacingDegrees = 0.25;

	FMotionWorldStateSample InvalidAnchor = Anchor;
	InvalidAnchor.bIsResimulation = true;
	TestFalse(
		TEXT("A resimulated state cannot become the fixed anchor"),
		MotionWorld::BuildResetTarget(InvalidAnchor).bIsValid);

	FMotionWorldResetTolerances InvalidTolerances = Tolerances;
	InvalidTolerances.PositionCm = -1.0;
	TestEqual(
		TEXT("Negative tolerance fails closed"),
		MotionWorld::CheckFinalizedResetState(Target, Exact, InvalidTolerances).Result,
		EMotionWorldResetCheckResult::InvalidTolerances);

	FMotionWorldResetTarget InvalidTarget = Target;
	InvalidTarget.MovementMode = NAME_None;
	TestEqual(
		TEXT("Incomplete target fails closed"),
		MotionWorld::CheckFinalizedResetState(InvalidTarget, Exact, Tolerances).Result,
		EMotionWorldResetCheckResult::InvalidTarget);

	FMotionWorldStateSample InvalidState = Exact;
	InvalidState.bIsValid = false;
	TestEqual(
		TEXT("Invalid finalized packet fails closed"),
		MotionWorld::CheckFinalizedResetState(Target, InvalidState, Tolerances).Result,
		EMotionWorldResetCheckResult::InvalidFinalizedState);

	FMotionWorldStateSample Resimulation = Exact;
	Resimulation.bIsResimulation = true;
	TestEqual(
		TEXT("A resimulation cannot verify reset"),
		MotionWorld::CheckFinalizedResetState(Target, Resimulation, Tolerances).Result,
		EMotionWorldResetCheckResult::Resimulation);

	FMotionWorldStateSample PositionMismatch = Exact;
	PositionMismatch.PositionWorldCm.X += Tolerances.PositionCm + 0.01;
	TestEqual(
		TEXT("Position outside tolerance is rejected"),
		MotionWorld::CheckFinalizedResetState(Target, PositionMismatch, Tolerances).Result,
		EMotionWorldResetCheckResult::PositionMismatch);

	FMotionWorldStateSample FacingMismatch = Exact;
	FacingMismatch.FacingYawDegrees += Tolerances.FacingDegrees + 0.01;
	TestEqual(
		TEXT("Facing outside tolerance is rejected"),
		MotionWorld::CheckFinalizedResetState(Target, FacingMismatch, Tolerances).Result,
		EMotionWorldResetCheckResult::FacingMismatch);

	FMotionWorldStateSample Moving = Exact;
	Moving.VelocityWorldCmPerSec = FVector(Tolerances.LinearSpeedCmPerSec + 0.01, 0.0, 0.0);
	TestEqual(
		TEXT("Residual linear motion is rejected"),
		MotionWorld::CheckFinalizedResetState(Target, Moving, Tolerances).Result,
		EMotionWorldResetCheckResult::LinearVelocityMismatch);

	FMotionWorldStateSample Rotating = Exact;
	Rotating.AngularVelocityWorldDegPerSec = FVector(0.0, 0.0, Tolerances.AngularSpeedDegPerSec + 0.01);
	TestEqual(
		TEXT("Residual angular motion is rejected"),
		MotionWorld::CheckFinalizedResetState(Target, Rotating, Tolerances).Result,
		EMotionWorldResetCheckResult::AngularVelocityMismatch);

	FMotionWorldStateSample WrongMode = Exact;
	WrongMode.MovementMode = TEXT("Falling");
	TestEqual(
		TEXT("Wrong movement mode is rejected"),
		MotionWorld::CheckFinalizedResetState(Target, WrongMode, Tolerances).Result,
		EMotionWorldResetCheckResult::MovementModeMismatch);

	FMotionWorldStateSample Boundary = Exact;
	Boundary.PositionWorldCm.X += Tolerances.PositionCm;
	Boundary.FacingYawDegrees += Tolerances.FacingDegrees;
	Boundary.VelocityWorldCmPerSec.X = Tolerances.LinearSpeedCmPerSec;
	Boundary.AngularVelocityWorldDegPerSec.Z = Tolerances.AngularSpeedDegPerSec;
	TestEqual(
		TEXT("Every exact tolerance boundary is inclusive"),
		MotionWorld::CheckFinalizedResetState(Target, Boundary, Tolerances).Result,
		EMotionWorldResetCheckResult::Passed);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
