#include "MotionWorldVariedActionSchedule.h"

namespace
{
bool IsFiniteNonNegative(const double Value)
{
	return FMath::IsFinite(Value) && Value >= 0.0;
}

FVector MakeReverseOrientationIntent(const double TieBreakDegrees)
{
	const double YawRadians = FMath::DegreesToRadians(-180.0 + TieBreakDegrees);
	return FVector(FMath::Cos(YawRadians), FMath::Sin(YawRadians), 0.0);
}
}

bool MotionWorld::IsVariedActionScheduleConfigValid(
	const FMotionWorldVariedActionScheduleConfig& Config)
{
	return FMath::IsFinite(Config.MotionPhaseDurationSeconds)
		&& Config.MotionPhaseDurationSeconds > 0.0
		&& FMath::IsFinite(Config.IntermediateStopDurationSeconds)
		&& Config.IntermediateStopDurationSeconds > 0.0
		&& FMath::IsFinite(Config.FinalStopDurationSeconds)
		&& Config.FinalStopDurationSeconds > 0.0
		&& IsFiniteNonNegative(Config.ForwardSpeedCmPerSec)
		&& IsFiniteNonNegative(Config.ReverseSpeedCmPerSec)
		&& FMath::IsFinite(Config.AntipodalFacingTieBreakDegrees)
		&& Config.AntipodalFacingTieBreakDegrees >= 0.25
		&& Config.AntipodalFacingTieBreakDegrees <= 5.0
		&& IsFiniteNonNegative(Config.LateralSpeedCmPerSec)
		&& IsFiniteNonNegative(Config.DiagonalComponentSpeedCmPerSec);
}

double MotionWorld::GetVariedActionScheduleDurationSeconds(
	const FMotionWorldVariedActionScheduleConfig& Config)
{
	if (!IsVariedActionScheduleConfigValid(Config))
	{
		return -1.0;
	}
	return 5.0 * Config.MotionPhaseDurationSeconds
		+ 2.0 * Config.IntermediateStopDurationSeconds
		+ Config.FinalStopDurationSeconds;
}

FMotionWorldVariedActionScheduleSample MotionWorld::EvaluateVariedActionSchedule(
	const FMotionWorldVariedActionScheduleConfig& Config,
	const double ElapsedSeconds)
{
	FMotionWorldVariedActionScheduleSample Result;
	Result.ElapsedSeconds = ElapsedSeconds;
	if (!IsVariedActionScheduleConfigValid(Config)
		|| !FMath::IsFinite(ElapsedSeconds)
		|| ElapsedSeconds < 0.0)
	{
		return Result;
	}

	const double MotionDuration = Config.MotionPhaseDurationSeconds;
	const double StopDuration = Config.IntermediateStopDurationSeconds;
	// Derive every boundary from the same closed-form sums used by the total
	// duration. Repeatedly mutating one floating-point accumulator can make a
	// mathematically identical boundary (for example 4.8 seconds) differ by one
	// representable value from the total duration or a caller's timestamp.
	const double ForwardEnd = MotionDuration;
	const double ForwardStopEnd = MotionDuration + StopDuration;
	const double ReverseEnd = 2.0 * MotionDuration + StopDuration;
	const double ReverseStopEnd = 2.0 * MotionDuration + 2.0 * StopDuration;
	const double RightEnd = 3.0 * MotionDuration + 2.0 * StopDuration;
	const double LeftEnd = 4.0 * MotionDuration + 2.0 * StopDuration;
	const double DiagonalEnd = 5.0 * MotionDuration + 2.0 * StopDuration;
	const double FinalStopEnd = DiagonalEnd + Config.FinalStopDurationSeconds;
	if (ElapsedSeconds < ForwardEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::Forward;
		Result.DesiredVelocityWorldCmPerSec = FVector(Config.ForwardSpeedCmPerSec, 0.0, 0.0);
		Result.OrientationIntentWorld = FVector::ForwardVector;
	}
	else if (ElapsedSeconds < ForwardStopEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::ForwardStop;
		Result.OrientationIntentWorld = FVector::ForwardVector;
	}
	else if (ElapsedSeconds < ReverseEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::Reverse;
		Result.DesiredVelocityWorldCmPerSec = FVector(-Config.ReverseSpeedCmPerSec, 0.0, 0.0);
		Result.OrientationIntentWorld = MakeReverseOrientationIntent(
			Config.AntipodalFacingTieBreakDegrees);
	}
	else if (ElapsedSeconds < ReverseStopEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::ReverseStop;
		Result.OrientationIntentWorld = MakeReverseOrientationIntent(
			Config.AntipodalFacingTieBreakDegrees);
	}
	else if (ElapsedSeconds < RightEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::Right;
		Result.DesiredVelocityWorldCmPerSec = FVector(0.0, Config.LateralSpeedCmPerSec, 0.0);
		Result.OrientationIntentWorld = FVector::RightVector;
	}
	else if (ElapsedSeconds < LeftEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::Left;
		Result.DesiredVelocityWorldCmPerSec = FVector(0.0, -Config.LateralSpeedCmPerSec, 0.0);
		Result.OrientationIntentWorld = -FVector::RightVector;
	}
	else if (ElapsedSeconds < DiagonalEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::Diagonal;
		Result.DesiredVelocityWorldCmPerSec = FVector(
			Config.DiagonalComponentSpeedCmPerSec,
			Config.DiagonalComponentSpeedCmPerSec,
			0.0);
		Result.OrientationIntentWorld = FVector(1.0, 1.0, 0.0).GetSafeNormal();
	}
	else if (ElapsedSeconds < FinalStopEnd)
	{
		Result.Phase = EMotionWorldVariedActionPhase::FinalStop;
		Result.OrientationIntentWorld = FVector(1.0, 1.0, 0.0).GetSafeNormal();
	}
	else
	{
		Result.Phase = EMotionWorldVariedActionPhase::Complete;
		Result.bIsComplete = true;
		Result.OrientationIntentWorld = FVector(1.0, 1.0, 0.0).GetSafeNormal();
	}

	Result.bIsValid = true;
	return Result;
}
