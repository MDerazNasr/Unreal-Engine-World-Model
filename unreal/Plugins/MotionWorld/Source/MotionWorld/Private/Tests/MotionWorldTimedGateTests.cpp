#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldTimedGate.h"

namespace
{
	FMotionWorldTimedGateConfig MakeValidConfig()
	{
		FMotionWorldTimedGateConfig Config;
		Config.ScenarioSeed = 1901;
		Config.OriginWorldCm = FVector(100.0, 200.0, 50.0);
		Config.MotionAxisWorld = FVector(0.0, 2.0, 0.0);
		Config.AmplitudeCm = 100.0;
		Config.PeriodSeconds = 4.0;
		Config.PhaseOffsetRadians = 0.0;
		Config.HalfExtentsCm = FVector(20.0, 40.0, 100.0);
		Config.CrossingPlaneNormalWorld = FVector::ForwardVector;
		Config.TimeoutSeconds = 8.0;
		return Config;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldTimedGateTest,
	"MotionWorld.Gate.DeterministicScheduleAndEvents",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldTimedGateTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	const FMotionWorldTimedGateConfig Config = MakeValidConfig();
	TestTrue(TEXT("Reference config is valid"), MotionWorld::IsTimedGateConfigValid(Config));

	const FMotionWorldTimedGateState AtStart =
		MotionWorld::EvaluateTimedGateSchedule(Config, 0.0);
	TestTrue(TEXT("Start state is valid"), AtStart.bIsValid);
	TestTrue(
		TEXT("Start center equals origin"),
		AtStart.CenterWorldCm.Equals(Config.OriginWorldCm, 1.e-6));
	TestEqual(TEXT("Start phase is zero"), AtStart.PhaseRadians, 0.0);
	TestTrue(
		TEXT("Start velocity points along normalized +Y"),
		AtStart.VelocityWorldCmPerSec.Equals(
			FVector(0.0, 50.0 * UE_DOUBLE_PI, 0.0),
			1.e-6));

	const FMotionWorldTimedGateState AtQuarterPeriod =
		MotionWorld::EvaluateTimedGateSchedule(Config, 1.0);
	TestTrue(
		TEXT("Quarter-period center is positive-amplitude endpoint"),
		AtQuarterPeriod.CenterWorldCm.Equals(FVector(100.0, 300.0, 50.0), 1.e-6));
	TestTrue(
		TEXT("Quarter-period velocity is zero"),
		AtQuarterPeriod.VelocityWorldCmPerSec.IsNearlyZero(1.e-6));

	const FMotionWorldTimedGateState AtFullPeriod =
		MotionWorld::EvaluateTimedGateSchedule(Config, 4.0);
	TestTrue(
		TEXT("Full-period center repeats exactly within tolerance"),
		AtFullPeriod.CenterWorldCm.Equals(AtStart.CenterWorldCm, 1.e-6));
	TestTrue(
		TEXT("Full-period velocity repeats exactly within tolerance"),
		AtFullPeriod.VelocityWorldCmPerSec.Equals(
			AtStart.VelocityWorldCmPerSec,
			1.e-6));

	const FMotionWorldTimedGateState RepeatedQuery =
		MotionWorld::EvaluateTimedGateSchedule(Config, 1.0);
	TestTrue(
		TEXT("Same config/time gives the same center"),
		RepeatedQuery.CenterWorldCm.Equals(AtQuarterPeriod.CenterWorldCm, 0.0));
	TestTrue(
		TEXT("Same config/time gives the same velocity"),
		RepeatedQuery.VelocityWorldCmPerSec.Equals(
			AtQuarterPeriod.VelocityWorldCmPerSec,
			0.0));

	const FMotionWorldScenarioStepResult Crossing =
		MotionWorld::EvaluateTimedGateScenarioStep(
			Config,
			FVector(99.0, 200.0, 50.0),
			FVector(101.0, 200.0, 50.0),
			1.0,
			false);
	TestTrue(TEXT("Forward plane crossing is detected"), Crossing.bCrossedSuccessPlaneThisStep);
	TestEqual(
		TEXT("Forward plane crossing terminates with success"),
		Crossing.TerminationReason,
		EMotionWorldScenarioTerminationReason::Success);

	const FMotionWorldScenarioStepResult CollisionWins =
		MotionWorld::EvaluateTimedGateScenarioStep(
			Config,
			FVector(99.0, 200.0, 50.0),
			FVector(101.0, 200.0, 50.0),
			1.0,
			true);
	TestFalse(
		TEXT("Collision suppresses a same-step success claim"),
		CollisionWins.bCrossedSuccessPlaneThisStep);
	TestEqual(
		TEXT("Collision has highest event priority"),
		CollisionWins.TerminationReason,
		EMotionWorldScenarioTerminationReason::GateCollision);

	const FMotionWorldScenarioStepResult Backward =
		MotionWorld::EvaluateTimedGateScenarioStep(
			Config,
			FVector(101.0, 200.0, 50.0),
			FVector(99.0, 200.0, 50.0),
			1.0,
			false);
	TestFalse(TEXT("Backward crossing is not success"), Backward.bCrossedSuccessPlaneThisStep);
	TestEqual(
		TEXT("Backward crossing remains active"),
		Backward.TerminationReason,
		EMotionWorldScenarioTerminationReason::None);

	const FMotionWorldScenarioStepResult Timeout =
		MotionWorld::EvaluateTimedGateScenarioStep(
			Config,
			FVector(50.0, 200.0, 50.0),
			FVector(60.0, 200.0, 50.0),
			8.0,
			false);
	TestEqual(
		TEXT("Timeout is detected at the inclusive deadline"),
		Timeout.TerminationReason,
		EMotionWorldScenarioTerminationReason::Timeout);

	FMotionWorldTimedGateConfig InvalidConfig = Config;
	InvalidConfig.PeriodSeconds = 0.0;
	TestFalse(
		TEXT("Zero-period config fails closed"),
		MotionWorld::IsTimedGateConfigValid(InvalidConfig));
	TestFalse(
		TEXT("Invalid schedule produces no valid state"),
		MotionWorld::EvaluateTimedGateSchedule(InvalidConfig, 0.0).bIsValid);

	InvalidConfig = Config;
	InvalidConfig.MotionAxisWorld = InvalidConfig.CrossingPlaneNormalWorld;
	TestFalse(
		TEXT("Motion through the crossing plane is rejected"),
		MotionWorld::IsTimedGateConfigValid(InvalidConfig));

	InvalidConfig = Config;
	InvalidConfig.MotionType = static_cast<EMotionWorldGateMotionType>(255);
	TestFalse(
		TEXT("Unknown motion type is rejected"),
		MotionWorld::IsTimedGateConfigValid(InvalidConfig));

	return true;
}

#endif
