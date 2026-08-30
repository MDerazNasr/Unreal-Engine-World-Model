#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldVelocityCommand.h"

#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldVelocityCommandTest,
	"MotionWorld.Command.SanitizeWorldVelocity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldVelocityCommandTest::RunTest(const FString& Parameters)
{
	using MotionWorld::FSanitizedVelocityCommand;
	using MotionWorld::SanitizeWorldVelocityCommand;

	const FSanitizedVelocityCommand Zero =
		SanitizeWorldVelocityCommand(FVector::ZeroVector, 600.0);
	TestTrue(TEXT("Zero command is finite"), Zero.bInputWasFinite);
	TestFalse(TEXT("Zero command is not clamped"), Zero.bWasClamped);
	TestEqual(TEXT("Zero command stays zero"), Zero.WorldVelocityCmPerSec, FVector::ZeroVector);

	const FSanitizedVelocityCommand Boundary =
		SanitizeWorldVelocityCommand(FVector(360.0, 480.0, 0.0), 600.0);
	TestFalse(TEXT("Boundary command is not clamped"), Boundary.bWasClamped);
	TestTrue(
		TEXT("Boundary command is preserved"),
		Boundary.WorldVelocityCmPerSec.Equals(FVector(360.0, 480.0, 0.0)));

	const FSanitizedVelocityCommand Oversized =
		SanitizeWorldVelocityCommand(FVector(900.0, 1200.0, 50.0), 600.0);
	TestTrue(TEXT("Oversized command is clamped"), Oversized.bWasClamped);
	TestTrue(TEXT("Vertical input is projected out"), Oversized.bWasProjectedToPlanar);
	TestTrue(
		TEXT("Clamp preserves planar direction"),
		Oversized.WorldVelocityCmPerSec.Equals(FVector(360.0, 480.0, 0.0), UE_KINDA_SMALL_NUMBER));

	const FSanitizedVelocityCommand Reverse =
		SanitizeWorldVelocityCommand(FVector(-300.0, 0.0, 0.0), 600.0);
	TestEqual(
		TEXT("Reverse command keeps its sign"),
		Reverse.WorldVelocityCmPerSec,
		FVector(-300.0, 0.0, 0.0));

	const FSanitizedVelocityCommand NonFinite =
		SanitizeWorldVelocityCommand(
			FVector(std::numeric_limits<double>::quiet_NaN(), 1.0, 0.0),
			600.0);
	TestFalse(TEXT("NaN command is rejected"), NonFinite.bInputWasFinite);
	TestEqual(
		TEXT("Rejected command fails closed to zero"),
		NonFinite.WorldVelocityCmPerSec,
		FVector::ZeroVector);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
