#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldExternalPerturbationSchedule.h"

#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldExternalPerturbationScheduleTest,
	"MotionWorld.Collection.ExternalPerturbationSchedule",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldExternalPerturbationScheduleTest::RunTest(
	const FString& Parameters)
{
	const FMotionWorldExternalPerturbationScheduleConfig Config;
	TestTrue(
		TEXT("Default perturbation schedule is valid"),
		MotionWorld::IsExternalPerturbationScheduleConfigValid(Config));
	TestEqual(
		TEXT("Total duration is warmup plus post-perturbation observation"),
		MotionWorld::GetExternalPerturbationScheduleDurationSeconds(Config),
		3.5);

	const FMotionWorldExternalPerturbationScheduleSample Before =
		MotionWorld::EvaluateExternalPerturbationSchedule(Config, 1.499, false);
	TestTrue(TEXT("Pre-perturbation sample is valid"), Before.bIsValid);
	TestEqual(
		TEXT("Time before the boundary remains pre-perturbation"),
		Before.Phase,
		EMotionWorldExternalPerturbationPhase::PrePerturbation);
	TestFalse(TEXT("The kick is not queued early"), Before.bShouldQueuePerturbation);

	const FMotionWorldExternalPerturbationScheduleSample AtTrigger =
		MotionWorld::EvaluateExternalPerturbationSchedule(Config, 1.5, false);
	TestEqual(
		TEXT("The half-open trigger boundary makes the kick due"),
		AtTrigger.Phase,
		EMotionWorldExternalPerturbationPhase::PerturbationDue);
	TestTrue(TEXT("The kick is requested exactly at the boundary"), AtTrigger.bShouldQueuePerturbation);
	TestTrue(
		TEXT("The requested world-space velocity delta is exact"),
		AtTrigger.AdditiveVelocityWorldCmPerSec.Equals(FVector(0.0, 250.0, 0.0)));

	const FMotionWorldExternalPerturbationScheduleSample LateUnqueued =
		MotionWorld::EvaluateExternalPerturbationSchedule(Config, 9.0, false);
	TestEqual(
		TEXT("A long frame cannot silently skip an unqueued kick"),
		LateUnqueued.Phase,
		EMotionWorldExternalPerturbationPhase::PerturbationDue);
	TestTrue(TEXT("A late unqueued kick remains due"), LateUnqueued.bShouldQueuePerturbation);
	TestFalse(TEXT("The schedule cannot complete before the kick is queued"), LateUnqueued.bIsComplete);

	const FMotionWorldExternalPerturbationScheduleSample After =
		MotionWorld::EvaluateExternalPerturbationSchedule(Config, 2.0, true);
	TestEqual(
		TEXT("A queued kick enters the recovery phase"),
		After.Phase,
		EMotionWorldExternalPerturbationPhase::PostPerturbation);
	TestFalse(TEXT("A queued kick is never requested twice"), After.bShouldQueuePerturbation);

	const FMotionWorldExternalPerturbationScheduleSample Complete =
		MotionWorld::EvaluateExternalPerturbationSchedule(Config, 3.5, true);
	TestEqual(
		TEXT("The total-duration boundary completes the schedule"),
		Complete.Phase,
		EMotionWorldExternalPerturbationPhase::Complete);
	TestTrue(TEXT("Completion is explicit"), Complete.bIsComplete);

	FMotionWorldExternalPerturbationScheduleConfig Invalid = Config;
	Invalid.WarmupDurationSeconds = 0.0;
	TestFalse(
		TEXT("Zero warmup fails closed"),
		MotionWorld::IsExternalPerturbationScheduleConfigValid(Invalid));
	Invalid = Config;
	Invalid.AdditiveVelocityWorldCmPerSec.Z = 1.0;
	TestFalse(
		TEXT("A vertical kick is rejected by the planar experiment"),
		MotionWorld::IsExternalPerturbationScheduleConfigValid(Invalid));
	Invalid = Config;
	Invalid.AdditiveVelocityWorldCmPerSec = FVector::ZeroVector;
	TestFalse(
		TEXT("A zero kick is not mislabeled as a perturbation"),
		MotionWorld::IsExternalPerturbationScheduleConfigValid(Invalid));
	Invalid = Config;
	Invalid.AdditiveVelocityWorldCmPerSec = FVector(1000.01, 0.0, 0.0);
	TestFalse(
		TEXT("An excessive kick fails the explicit experiment bound"),
		MotionWorld::IsExternalPerturbationScheduleConfigValid(Invalid));
	Invalid = Config;
	Invalid.AdditiveVelocityWorldCmPerSec.X =
		std::numeric_limits<double>::quiet_NaN();
	TestFalse(
		TEXT("A non-finite kick fails closed"),
		MotionWorld::IsExternalPerturbationScheduleConfigValid(Invalid));
	TestFalse(
		TEXT("A non-finite elapsed time fails closed"),
		MotionWorld::EvaluateExternalPerturbationSchedule(
			Config,
			std::numeric_limits<double>::infinity(),
			false).bIsValid);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
