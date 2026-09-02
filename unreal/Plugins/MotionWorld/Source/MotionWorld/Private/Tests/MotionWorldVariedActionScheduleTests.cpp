#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldVariedActionSchedule.h"

#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldVariedActionScheduleTest,
	"MotionWorld.Collection.VariedActionSchedule",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldVariedActionScheduleTest::RunTest(const FString& Parameters)
{
	const FMotionWorldVariedActionScheduleConfig Config;
	TestTrue(TEXT("Default schedule is valid"), MotionWorld::IsVariedActionScheduleConfigValid(Config));
	const double Motion = Config.MotionPhaseDurationSeconds;
	const double Stop = Config.IntermediateStopDurationSeconds;
	const double Duration = MotionWorld::GetVariedActionScheduleDurationSeconds(Config);
	const double ReverseFacingRadians = FMath::DegreesToRadians(
		-180.0 + Config.AntipodalFacingTieBreakDegrees);
	const FVector ReverseFacing(
		FMath::Cos(ReverseFacingRadians),
		FMath::Sin(ReverseFacingRadians),
		0.0);
	TestEqual(TEXT("Default duration follows the documented sum"), Duration, 5.3);

	struct FCase
	{
		double TimeSeconds;
		EMotionWorldVariedActionPhase Phase;
		FVector Velocity;
		FVector Facing;
		bool bComplete;
	};
	const FCase Cases[] = {
		{0.0, EMotionWorldVariedActionPhase::Forward, FVector(200.0, 0.0, 0.0), FVector::ForwardVector, false},
		{Motion, EMotionWorldVariedActionPhase::ForwardStop, FVector::ZeroVector, FVector::ForwardVector, false},
		{Motion + Stop, EMotionWorldVariedActionPhase::Reverse, FVector(-150.0, 0.0, 0.0), ReverseFacing, false},
		{2.0 * Motion + Stop, EMotionWorldVariedActionPhase::ReverseStop, FVector::ZeroVector, ReverseFacing, false},
		{2.0 * Motion + 2.0 * Stop, EMotionWorldVariedActionPhase::Right, FVector(0.0, 140.0, 0.0), FVector::RightVector, false},
		{3.0 * Motion + 2.0 * Stop, EMotionWorldVariedActionPhase::Left, FVector(0.0, -140.0, 0.0), -FVector::RightVector, false},
		{4.0 * Motion + 2.0 * Stop, EMotionWorldVariedActionPhase::Diagonal, FVector(100.0, 100.0, 0.0), FVector(1.0, 1.0, 0.0).GetSafeNormal(), false},
		{5.0 * Motion + 2.0 * Stop, EMotionWorldVariedActionPhase::FinalStop, FVector::ZeroVector, FVector(1.0, 1.0, 0.0).GetSafeNormal(), false},
		{Duration, EMotionWorldVariedActionPhase::Complete, FVector::ZeroVector, FVector(1.0, 1.0, 0.0).GetSafeNormal(), true},
	};
	for (const FCase& Case : Cases)
	{
		const FMotionWorldVariedActionScheduleSample Sample =
			MotionWorld::EvaluateVariedActionSchedule(Config, Case.TimeSeconds);
		TestTrue(TEXT("Boundary sample is valid"), Sample.bIsValid);
		TestEqual(TEXT("Half-open boundary selects expected phase"), Sample.Phase, Case.Phase);
		TestTrue(TEXT("Boundary velocity is exact"), Sample.DesiredVelocityWorldCmPerSec.Equals(Case.Velocity, 1.e-9));
		TestTrue(TEXT("Boundary facing is exact"), Sample.OrientationIntentWorld.Equals(Case.Facing, 1.e-9));
		TestEqual(TEXT("Completion flag is exact"), Sample.bIsComplete, Case.bComplete);
		TestTrue(TEXT("Facing remains unit length"), FMath::IsNearlyEqual(Sample.OrientationIntentWorld.SizeSquared(), 1.0, 1.e-9));
	}
	const FMotionWorldVariedActionScheduleSample ReverseSample =
		MotionWorld::EvaluateVariedActionSchedule(Config, Motion + Stop);
	TestTrue(
		TEXT("Reverse velocity remains exactly world -X"),
		ReverseSample.DesiredVelocityWorldCmPerSec.Equals(FVector(-150.0, 0.0, 0.0), 1.e-9));
	TestTrue(
		TEXT("Reverse facing is not exactly antipodal"),
		FVector::DotProduct(FVector::ForwardVector, ReverseSample.OrientationIntentWorld) > -1.0);
	TestTrue(
		TEXT("Reverse facing selects the clockwise side of the tie"),
		ReverseSample.OrientationIntentWorld.Y < 0.0);
	TestTrue(
		TEXT("Reverse facing yaw is the configured unambiguous target"),
		FMath::IsNearlyEqual(
			FMath::RadiansToDegrees(FMath::Atan2(
				ReverseSample.OrientationIntentWorld.Y,
				ReverseSample.OrientationIntentWorld.X)),
			-179.5,
			1.e-9));

	FMotionWorldVariedActionScheduleConfig InvalidConfig = Config;
	InvalidConfig.MotionPhaseDurationSeconds = 0.0;
	TestFalse(TEXT("Zero phase duration fails closed"), MotionWorld::EvaluateVariedActionSchedule(InvalidConfig, 0.0).bIsValid);
	TestFalse(TEXT("Negative time fails closed"), MotionWorld::EvaluateVariedActionSchedule(Config, -0.1).bIsValid);
	TestFalse(TEXT("Non-finite time fails closed"), MotionWorld::EvaluateVariedActionSchedule(Config, std::numeric_limits<double>::quiet_NaN()).bIsValid);
	InvalidConfig = Config;
	InvalidConfig.AntipodalFacingTieBreakDegrees = 0.0;
	TestFalse(TEXT("Ambiguous zero-degree tie break fails closed"), MotionWorld::IsVariedActionScheduleConfigValid(InvalidConfig));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
