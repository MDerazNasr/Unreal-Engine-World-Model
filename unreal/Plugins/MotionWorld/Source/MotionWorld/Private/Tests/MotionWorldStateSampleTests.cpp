#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldStateSample.h"

#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldStateSampleTest,
	"MotionWorld.State.AuthoritativeSample",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldStateSampleTest::RunTest(const FString& Parameters)
{
	MotionWorld::FAuthoritativeStateInputs Inputs;
	Inputs.bHasAuthoritativeSource = true;
	Inputs.SampleSequence = 41;
	Inputs.MoverStepServerFrame = 99;
	Inputs.SimulationTimeSeconds = 1.65;
	Inputs.StepSeconds = 1.0 / 60.0;
	Inputs.MovementMode = TEXT("Walking");
	Inputs.PositionWorldCm = FVector(100.0, -50.0, 90.0);
	Inputs.VelocityWorldCmPerSec = FVector(0.0, 200.0, 25.0);
	Inputs.OrientationWorldDegrees = FRotator(0.0, 450.0, 0.0);
	Inputs.AngularVelocityWorldDegPerSec = FVector(0.0, 0.0, 30.0);

	const FMotionWorldStateSample Valid =
		MotionWorld::BuildAuthoritativeStateSample(Inputs);
	TestTrue(TEXT("Complete finite source produces a valid packet"), Valid.bIsValid);
	TestEqual(TEXT("Protocol version is explicit"), Valid.ProtocolVersion, 1);
	TestEqual(TEXT("Sequence is retained"), Valid.SampleSequence, int64(41));
	TestEqual(TEXT("Mover frame is retained"), Valid.MoverStepServerFrame, 99);
	TestEqual(TEXT("Movement mode is retained"), Valid.MovementMode, FName(TEXT("Walking")));
	TestTrue(
		TEXT("World position is retained"),
		Valid.PositionWorldCm.Equals(Inputs.PositionWorldCm));
	TestTrue(
		TEXT("World velocity is retained, including vertical motion"),
		Valid.VelocityWorldCmPerSec.Equals(Inputs.VelocityWorldCmPerSec));
	TestTrue(
		TEXT("Yaw is normalized before model-facing conversion"),
		FMath::IsNearlyEqual(Valid.FacingYawDegrees, 90.0, 1.e-6));
	TestTrue(
		TEXT("World +Y becomes local forward at yaw 90 and vertical velocity is removed"),
		Valid.VelocityLocalPlanarCmPerSec.Equals(FVector(200.0, 0.0, 0.0), 1.e-6));
	TestTrue(
		TEXT("Facing unit vector is wraparound-safe"),
		Valid.FacingUnitWorld.Equals(FVector2D(0.0, 1.0), 1.e-6));
	TestTrue(
		TEXT("Angular velocity retains its declared world/degree units"),
		Valid.AngularVelocityWorldDegPerSec.Equals(Inputs.AngularVelocityWorldDegPerSec));

	Inputs.SampleSequence = 42;
	const FMotionWorldStateSample Next =
		MotionWorld::BuildAuthoritativeStateSample(Inputs);
	TestTrue(
		TEXT("Caller-supplied sequence advances monotonically"),
		Next.SampleSequence > Valid.SampleSequence);

	Inputs.VelocityWorldCmPerSec.X = std::numeric_limits<double>::quiet_NaN();
	const FMotionWorldStateSample NonFinite =
		MotionWorld::BuildAuthoritativeStateSample(Inputs);
	TestFalse(TEXT("Non-finite source data invalidates the packet"), NonFinite.bIsValid);
	TestEqual(
		TEXT("Invalid packets fail closed without propagating NaN"),
		NonFinite.VelocityWorldCmPerSec,
		FVector::ZeroVector);

	Inputs.VelocityWorldCmPerSec = FVector::ZeroVector;
	Inputs.StepSeconds = 0.0;
	const FMotionWorldStateSample ZeroStep =
		MotionWorld::BuildAuthoritativeStateSample(Inputs);
	TestFalse(TEXT("A non-positive timestep invalidates the packet"), ZeroStep.bIsValid);

	Inputs.StepSeconds = 1.0 / 60.0;
	Inputs.bHasAuthoritativeSource = false;
	const FMotionWorldStateSample MissingSource =
		MotionWorld::BuildAuthoritativeStateSample(Inputs);
	TestFalse(TEXT("A missing Mover state fails closed"), MissingSource.bIsValid);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
