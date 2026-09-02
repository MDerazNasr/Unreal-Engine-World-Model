#include "MotionWorldExternalPerturbationSchedule.h"

namespace
{
constexpr double MaximumPlanarVelocityKickCmPerSec = 1000.0;

bool IsFinitePlanarVector(const FVector& Value)
{
	return FMath::IsFinite(Value.X)
		&& FMath::IsFinite(Value.Y)
		&& FMath::IsFinite(Value.Z)
		&& FMath::IsNearlyZero(Value.Z);
}
} // namespace

bool MotionWorld::IsExternalPerturbationScheduleConfigValid(
	const FMotionWorldExternalPerturbationScheduleConfig& Config)
{
	return FMath::IsFinite(Config.WarmupDurationSeconds)
		&& Config.WarmupDurationSeconds > 0.0
		&& FMath::IsFinite(Config.PostPerturbationDurationSeconds)
		&& Config.PostPerturbationDurationSeconds > 0.0
		&& IsFinitePlanarVector(Config.AdditiveVelocityWorldCmPerSec)
		&& !Config.AdditiveVelocityWorldCmPerSec.IsNearlyZero()
		&& Config.AdditiveVelocityWorldCmPerSec.Size2D()
			<= MaximumPlanarVelocityKickCmPerSec;
}

double MotionWorld::GetExternalPerturbationScheduleDurationSeconds(
	const FMotionWorldExternalPerturbationScheduleConfig& Config)
{
	if (!IsExternalPerturbationScheduleConfigValid(Config))
	{
		return -1.0;
	}
	return Config.WarmupDurationSeconds
		+ Config.PostPerturbationDurationSeconds;
}

FMotionWorldExternalPerturbationScheduleSample
MotionWorld::EvaluateExternalPerturbationSchedule(
	const FMotionWorldExternalPerturbationScheduleConfig& Config,
	const double ElapsedSeconds,
	const bool bPerturbationAlreadyQueued)
{
	FMotionWorldExternalPerturbationScheduleSample Result;
	Result.ElapsedSeconds = ElapsedSeconds;
	if (!IsExternalPerturbationScheduleConfigValid(Config)
		|| !FMath::IsFinite(ElapsedSeconds)
		|| ElapsedSeconds < 0.0)
	{
		return Result;
	}

	Result.AdditiveVelocityWorldCmPerSec =
		Config.AdditiveVelocityWorldCmPerSec;
	if (ElapsedSeconds < Config.WarmupDurationSeconds)
	{
		Result.Phase = EMotionWorldExternalPerturbationPhase::PrePerturbation;
	}
	else if (!bPerturbationAlreadyQueued)
	{
		Result.Phase = EMotionWorldExternalPerturbationPhase::PerturbationDue;
		Result.bShouldQueuePerturbation = true;
	}
	else if (ElapsedSeconds
		< GetExternalPerturbationScheduleDurationSeconds(Config))
	{
		Result.Phase = EMotionWorldExternalPerturbationPhase::PostPerturbation;
	}
	else
	{
		Result.Phase = EMotionWorldExternalPerturbationPhase::Complete;
		Result.bIsComplete = true;
	}

	Result.bIsValid = true;
	return Result;
}
