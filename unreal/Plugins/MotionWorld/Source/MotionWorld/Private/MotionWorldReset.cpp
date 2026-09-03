#include "MotionWorldReset.h"

namespace
{
bool AreTolerancesValid(const FMotionWorldResetTolerances& Tolerances)
{
	return FMath::IsFinite(Tolerances.PositionCm)
		&& Tolerances.PositionCm >= 0.0
		&& FMath::IsFinite(Tolerances.FacingDegrees)
		&& Tolerances.FacingDegrees >= 0.0
		&& Tolerances.FacingDegrees <= 180.0
		&& FMath::IsFinite(Tolerances.LinearSpeedCmPerSec)
		&& Tolerances.LinearSpeedCmPerSec >= 0.0
		&& FMath::IsFinite(Tolerances.AngularSpeedDegPerSec)
		&& Tolerances.AngularSpeedDegPerSec >= 0.0;
}

bool IsTargetNumericallyValid(const FMotionWorldResetTarget& Target)
{
	return Target.bIsValid
		&& Target.SourceStateSequence >= 0
		&& !Target.PositionWorldCm.ContainsNaN()
		&& !Target.OrientationWorldDegrees.ContainsNaN()
		&& !Target.MovementMode.IsNone();
}
} // namespace

namespace MotionWorld
{
FMotionWorldResetTarget BuildResetTarget(
	const FMotionWorldStateSample& AnchorState)
{
	FMotionWorldResetTarget Target;
	if (!AnchorState.bIsValid
		|| AnchorState.bIsResimulation
		|| AnchorState.SampleSequence < 0
		|| AnchorState.PositionWorldCm.ContainsNaN()
		|| !FMath::IsFinite(AnchorState.FacingYawDegrees)
		|| AnchorState.MovementMode.IsNone())
	{
		return Target;
	}

	Target.bIsValid = true;
	Target.SourceStateSequence = AnchorState.SampleSequence;
	Target.PositionWorldCm = AnchorState.PositionWorldCm;
	Target.OrientationWorldDegrees = FRotator(
		0.0,
		FRotator::NormalizeAxis(AnchorState.FacingYawDegrees),
		0.0);
	Target.MovementMode = AnchorState.MovementMode;
	return Target;
}

FMotionWorldResetTarget OverrideResetTargetYaw(
	const FMotionWorldResetTarget& Target,
	const double FacingYawDegrees)
{
	FMotionWorldResetTarget OverriddenTarget;
	if (!IsTargetNumericallyValid(Target)
		|| !FMath::IsFinite(FacingYawDegrees))
	{
		return OverriddenTarget;
	}

	OverriddenTarget = Target;
	OverriddenTarget.OrientationWorldDegrees = FRotator(
		0.0,
		FRotator::NormalizeAxis(FacingYawDegrees),
		0.0);
	return OverriddenTarget;
}

FMotionWorldResetCheck CheckFinalizedResetState(
	const FMotionWorldResetTarget& Target,
	const FMotionWorldStateSample& FinalizedState,
	const FMotionWorldResetTolerances& Tolerances)
{
	FMotionWorldResetCheck Check;
	if (!AreTolerancesValid(Tolerances))
	{
		Check.Result = EMotionWorldResetCheckResult::InvalidTolerances;
		return Check;
	}

	if (!IsTargetNumericallyValid(Target))
	{
		Check.Result = EMotionWorldResetCheckResult::InvalidTarget;
		return Check;
	}

	if (!FinalizedState.bIsValid
		|| FinalizedState.SampleSequence < 0
		|| FinalizedState.PositionWorldCm.ContainsNaN()
		|| FinalizedState.VelocityWorldCmPerSec.ContainsNaN()
		|| !FMath::IsFinite(FinalizedState.FacingYawDegrees)
		|| FinalizedState.AngularVelocityWorldDegPerSec.ContainsNaN()
		|| FinalizedState.MovementMode.IsNone())
	{
		Check.Result = EMotionWorldResetCheckResult::InvalidFinalizedState;
		return Check;
	}

	if (FinalizedState.bIsResimulation)
	{
		Check.Result = EMotionWorldResetCheckResult::Resimulation;
		return Check;
	}

	Check.PositionErrorCm = FVector::Distance(
		FinalizedState.PositionWorldCm,
		Target.PositionWorldCm);
	Check.FacingErrorDegrees = FMath::Abs(FMath::FindDeltaAngleDegrees(
		Target.OrientationWorldDegrees.Yaw,
		FinalizedState.FacingYawDegrees));
	Check.LinearSpeedCmPerSec = FinalizedState.VelocityWorldCmPerSec.Size();
	Check.AngularSpeedDegPerSec =
		FinalizedState.AngularVelocityWorldDegPerSec.Size();

	if (Check.PositionErrorCm > Tolerances.PositionCm)
	{
		Check.Result = EMotionWorldResetCheckResult::PositionMismatch;
	}
	else if (Check.FacingErrorDegrees > Tolerances.FacingDegrees)
	{
		Check.Result = EMotionWorldResetCheckResult::FacingMismatch;
	}
	else if (Check.LinearSpeedCmPerSec > Tolerances.LinearSpeedCmPerSec)
	{
		Check.Result = EMotionWorldResetCheckResult::LinearVelocityMismatch;
	}
	else if (Check.AngularSpeedDegPerSec > Tolerances.AngularSpeedDegPerSec)
	{
		Check.Result = EMotionWorldResetCheckResult::AngularVelocityMismatch;
	}
	else if (FinalizedState.MovementMode != Target.MovementMode)
	{
		Check.Result = EMotionWorldResetCheckResult::MovementModeMismatch;
	}
	else
	{
		Check.Result = EMotionWorldResetCheckResult::Passed;
	}

	return Check;
}
} // namespace MotionWorld
