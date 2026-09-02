#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldNominalContext.h"

#include <limits>

namespace
{
	FMotionWorldSmoothWalkingDiagnosticSample MakeValidDiagnostic()
	{
		FMotionWorldSmoothWalkingDiagnosticSample Sample;
		Sample.bIsValid = true;
		Sample.AuthoritativeStateSampleSequence = 42;
		Sample.MovementModeName = TEXT("Walking");
		Sample.MovementModeClass = TEXT("BP_MovementMode_Walking_C");
		Sample.bHasMaxMoveSpeed = true;
		Sample.EffectiveMaxSpeedCmPerSec = 165.0;
		Sample.MaxSpeedSource = EMotionWorldMaxSpeedSource::CommonLegacySettings;
		Sample.AccelerationCmPerSecSquared = 500.0;
		Sample.DecelerationCmPerSecSquared = 300.0;
		Sample.DirectionalAccelerationFactor = 1.0;
		Sample.TurningStrength = 8.0;
		Sample.AccelerationSmoothingTimeSeconds = 0.1;
		Sample.DecelerationSmoothingTimeSeconds = 0.1;
		Sample.VelocityDeadzoneCmPerSec = 0.01;
		Sample.AccelerationDeadzoneCmPerSecSquared = 0.001;
		Sample.OutsideInfluenceSmoothingTimeSeconds = 0.05;
		Sample.FacingSmoothingTimeSeconds = 0.2;
		Sample.FacingDeadzoneDegrees = 0.1;
		Sample.AngularVelocityDeadzoneDegreesPerSec = 0.01;
		Sample.SpringVelocityWorldCmPerSec = FVector(100.0, 20.0, 0.0);
		Sample.SpringAccelerationWorldCmPerSecSquared = FVector(10.0, -5.0, 0.0);
		Sample.IntermediateVelocityWorldCmPerSec = FVector(90.0, 18.0, 0.0);
		Sample.IntermediateFacingWorld = FQuat(FVector::UpVector, 0.25);
		Sample.IntermediateAngularVelocityWorldRadPerSec = FVector(0.0, 0.0, 0.5);
		return Sample;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldNominalContextTest,
	"MotionWorld.Data.NominalContext",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldNominalContextTest::RunTest(const FString& Parameters)
{
	FMotionWorldSmoothWalkingDiagnosticSample Diagnostic = MakeValidDiagnostic();
	const FMotionWorldNominalContextSample Valid = MotionWorld::BuildNominalContextSample(Diagnostic);
	TestTrue(TEXT("Valid telemetry becomes valid nominal context"), Valid.bIsValid);
	TestTrue(TEXT("Strict validator accepts complete context"), MotionWorld::IsNominalContextSampleValid(Valid));
	TestEqual(TEXT("State sequence remains aligned"), Valid.AuthoritativeStateSampleSequence, int64(42));
	TestEqual(TEXT("Acceleration is preserved"), Valid.Parameters.AccelerationCmPerSecSquared, 500.0);
	TestEqual(TEXT("Context protocol includes preprocessing"), Valid.ProtocolVersion, 2);
	TestEqual(TEXT("Effective max speed is preserved"), Valid.InputPreparation.EffectiveMaxSpeedCmPerSec, 165.0);
	TestEqual(
		TEXT("Hidden spring velocity is preserved"),
		Valid.InternalState.SpringVelocityWorldCmPerSec,
		Diagnostic.SpringVelocityWorldCmPerSec);

	Diagnostic.ProtocolVersion = 3;
	const FMotionWorldNominalContextSample Unsupported =
		MotionWorld::BuildNominalContextSample(Diagnostic);
	TestFalse(TEXT("Unknown telemetry version fails closed"), Unsupported.bIsValid);
	TestEqual(
		TEXT("Version failure is explicit"),
		Unsupported.FailureReason,
		FName(TEXT("unsupported_diagnostic_protocol")));

	Diagnostic = MakeValidDiagnostic();
	Diagnostic.DirectionalAccelerationFactor = 1.1;
	const FMotionWorldNominalContextSample InvalidRange =
		MotionWorld::BuildNominalContextSample(Diagnostic);
	TestFalse(TEXT("Invalid movement parameter fails closed"), InvalidRange.bIsValid);

	Diagnostic = MakeValidDiagnostic();
	Diagnostic.SpringVelocityWorldCmPerSec.X = std::numeric_limits<double>::infinity();
	const FMotionWorldNominalContextSample InvalidVector =
		MotionWorld::BuildNominalContextSample(Diagnostic);
	TestFalse(TEXT("Non-finite internal state fails closed"), InvalidVector.bIsValid);

	Diagnostic = MakeValidDiagnostic();
	Diagnostic.IntermediateFacingWorld = FQuat(0.0, 0.0, 0.0, 2.0);
	const FMotionWorldNominalContextSample InvalidQuaternion =
		MotionWorld::BuildNominalContextSample(Diagnostic);
	TestFalse(TEXT("Non-unit internal facing fails closed"), InvalidQuaternion.bIsValid);

	Diagnostic = MakeValidDiagnostic();
	Diagnostic.bIsValid = false;
	const FMotionWorldNominalContextSample InvalidUpstream =
		MotionWorld::BuildNominalContextSample(Diagnostic);
	TestFalse(TEXT("Invalid diagnostic cannot become model context"), InvalidUpstream.bIsValid);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
