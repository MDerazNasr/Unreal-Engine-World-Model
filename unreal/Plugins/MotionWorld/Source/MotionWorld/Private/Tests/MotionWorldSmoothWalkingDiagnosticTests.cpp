#if WITH_DEV_AUTOMATION_TESTS

#include "DefaultMovementSet/Modes/SmoothWalkingMode.h"
#include "Misc/AutomationTest.h"
#include "MotionWorldSmoothWalkingDiagnostic.h"

#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldSmoothWalkingDiagnosticTest,
	"MotionWorld.Diagnostics.SmoothWalking",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldSmoothWalkingDiagnosticTest::RunTest(const FString& Parameters)
{
	MotionWorld::FSmoothWalkingDiagnosticInputs Inputs;
	Inputs.AuthoritativeStateSampleSequence = 12;
	Inputs.MovementModeName = TEXT("Walking");
	FName FailureReason;
	const USmoothWalkingMode* Defaults = GetDefault<USmoothWalkingMode>();
	TestTrue(
		TEXT("Reflected class-default parameters are readable through public UObject metadata"),
		MotionWorld::ReadSmoothWalkingParameters(Defaults, Inputs, FailureReason));
	TestEqual(TEXT("Fourteen float parameters are captured"), Inputs.Parameters.Num(), 14);
	TestEqual(TEXT("Default acceleration is version-matched"), Inputs.Parameters[0], 1500.0);
	TestEqual(TEXT("Default turning strength is version-matched"), Inputs.Parameters[3], 10.0);
	TestTrue(
		TEXT("Simple Walking input preprocessing is readable"),
		MotionWorld::ReadSimpleWalkingInputPreparation(Defaults, Inputs, FailureReason));
	TestFalse(TEXT("A detached class default has no max-speed source"), Inputs.bHasMaxMoveSpeed);
	TestEqual(TEXT("Detached defaults are explicitly unbounded"), Inputs.MaxSpeedSource, EMotionWorldMaxSpeedSource::Unbounded);

	Inputs.bHasSpringState = true;
	Inputs.SpringVelocity = FVector(1.0, 2.0, 0.0);
	Inputs.SpringAcceleration = FVector(3.0, 4.0, 0.0);
	Inputs.IntermediateVelocity = FVector(5.0, 6.0, 0.0);
	Inputs.IntermediateFacing = FQuat::Identity;
	Inputs.IntermediateAngularVelocity = FVector(0.0, 0.0, 0.25);
	const FMotionWorldSmoothWalkingDiagnosticSample Valid =
		MotionWorld::BuildSmoothWalkingDiagnosticSample(Inputs);
	TestTrue(TEXT("Complete finite diagnostic is valid"), Valid.bIsValid);
	TestEqual(TEXT("Spring velocity is preserved"), Valid.SpringVelocityWorldCmPerSec, Inputs.SpringVelocity);
	TestEqual(TEXT("Input preparation is versioned in the diagnostic"), Valid.ProtocolVersion, 2);

	Inputs.Parameters[0] = std::numeric_limits<double>::quiet_NaN();
	const FMotionWorldSmoothWalkingDiagnosticSample Invalid =
		MotionWorld::BuildSmoothWalkingDiagnosticSample(Inputs);
	TestFalse(TEXT("Non-finite parameter fails closed"), Invalid.bIsValid);
	TestEqual(TEXT("Failure is explicit"), Invalid.FailureReason, FName(TEXT("non_finite_parameter")));

	Inputs.Parameters[0] = 1500.0;
	Inputs.Parameters[2] = 2.0;
	const FMotionWorldSmoothWalkingDiagnosticSample InvalidRange =
		MotionWorld::BuildSmoothWalkingDiagnosticSample(Inputs);
	TestFalse(TEXT("Out-of-range directional factor fails closed"), InvalidRange.bIsValid);
	TestEqual(
		TEXT("Range failure is explicit"),
		InvalidRange.FailureReason,
		FName(TEXT("invalid_parameter_range")));

	Inputs.Parameters[2] = 1.0;
	Inputs.SpringVelocity.X = std::numeric_limits<double>::infinity();
	const FMotionWorldSmoothWalkingDiagnosticSample InvalidSpringState =
		MotionWorld::BuildSmoothWalkingDiagnosticSample(Inputs);
	TestFalse(TEXT("Non-finite spring state fails closed"), InvalidSpringState.bIsValid);
	TestEqual(
		TEXT("Spring-state failure is explicit"),
		InvalidSpringState.FailureReason,
		FName(TEXT("non_finite_spring_state")));

	Inputs.SpringVelocity.X = 1.0;
	Inputs.FailureReason = TEXT("upstream_reflection_failure");
	const FMotionWorldSmoothWalkingDiagnosticSample UpstreamFailure =
		MotionWorld::BuildSmoothWalkingDiagnosticSample(Inputs);
	TestFalse(TEXT("Upstream reflection failure cannot become valid"), UpstreamFailure.bIsValid);
	TestEqual(
		TEXT("Upstream failure reason is preserved"),
		UpstreamFailure.FailureReason,
		FName(TEXT("upstream_reflection_failure")));

	TestFalse(
		TEXT("A failed parameter reread clears prior valid parameter state"),
		MotionWorld::ReadSmoothWalkingParameters(nullptr, Inputs, FailureReason));
	TestFalse(TEXT("Stale parameter flag is cleared"), Inputs.bHasParameters);
	TestEqual(TEXT("Stale parameter values are cleared"), Inputs.Parameters.Num(), 0);

	MotionWorld::FSmoothWalkingDiagnosticInputs MissingStateInputs;
	FName MissingStateReason;
	TestFalse(
		TEXT("Missing reflected spring state fails closed"),
		MotionWorld::ReadSmoothWalkingSpringState(
			FMoverDataCollection(),
			MissingStateInputs,
			MissingStateReason));
	TestEqual(
		TEXT("Missing state reason is explicit"),
		MissingStateReason,
		FName(TEXT("smooth_walking_state_not_found")));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
