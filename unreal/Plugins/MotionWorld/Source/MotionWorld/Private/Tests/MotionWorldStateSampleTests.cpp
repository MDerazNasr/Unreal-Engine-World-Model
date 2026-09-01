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

	MotionWorld::FAnimationDiagnosticInputs DiagnosticInputs;
	DiagnosticInputs.AuthoritativeState = Valid;
	DiagnosticInputs.bHasPrimarySkeletalVisual = true;
	DiagnosticInputs.bBoneTransformsValid = true;
	DiagnosticInputs.VisualComponentName = TEXT("Mesh");
	DiagnosticInputs.RootBoneName = TEXT("root");
	DiagnosticInputs.VisualComponentWorldTransform = FTransform(
		FRotator(0.0, 90.0, 0.0),
		FVector(100.0, -50.0, 0.0),
		FVector::OneVector);
	DiagnosticInputs.AnimationRootWorldTransform = FTransform(
		FRotator(0.0, 95.0, 0.0),
		FVector(112.0, -53.0, 4.0),
		FVector::OneVector);
	const FMotionWorldAnimationDiagnosticSample Diagnostic =
		MotionWorld::BuildAnimationDiagnosticSample(DiagnosticInputs);
	TestTrue(
		TEXT("Complete primary-visual/root data produces valid QA telemetry"),
		Diagnostic.bIsValid);
	TestEqual(
		TEXT("Diagnostic remains aligned to the authoritative state sequence"),
		Diagnostic.AuthoritativeStateSampleSequence,
		Valid.SampleSequence);
	TestEqual(
		TEXT("Authoritative actor position is copied under an explicit field name"),
		Diagnostic.AuthoritativeActorPositionWorldCm,
		Valid.PositionWorldCm);
	TestEqual(
		TEXT("Actor-to-root offset is derived in world centimetres"),
		Diagnostic.ActorToAnimationRootWorldCm,
		FVector(12.0, -3.0, -86.0));

	DiagnosticInputs.bHasPrimarySkeletalVisual = false;
	const FMotionWorldAnimationDiagnosticSample MissingVisual =
		MotionWorld::BuildAnimationDiagnosticSample(DiagnosticInputs);
	TestFalse(
		TEXT("Missing Mover primary skeletal visual fails closed"),
		MissingVisual.bIsValid);
	TestEqual(
		TEXT("Invalid diagnostic does not propagate a visual root position"),
		MissingVisual.AnimationRootWorldTransform,
		FTransform::Identity);

	DiagnosticInputs.bHasPrimarySkeletalVisual = true;
	DiagnosticInputs.AnimationRootWorldTransform.SetTranslation(
		FVector(std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0));
	const FMotionWorldAnimationDiagnosticSample NonFiniteVisual =
		MotionWorld::BuildAnimationDiagnosticSample(DiagnosticInputs);
	TestFalse(
		TEXT("Non-finite animation transform fails closed"),
		NonFiniteVisual.bIsValid);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
