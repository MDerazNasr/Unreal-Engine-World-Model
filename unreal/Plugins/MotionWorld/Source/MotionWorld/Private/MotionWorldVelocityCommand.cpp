#include "MotionWorldVelocityCommand.h"

namespace MotionWorld
{
FSanitizedVelocityCommand SanitizeWorldVelocityCommand(
	const FVector& RequestedWorldVelocityCmPerSec,
	const double MaxPlanarSpeedCmPerSec)
{
	FSanitizedVelocityCommand Result;

	if (RequestedWorldVelocityCmPerSec.ContainsNaN() || !FMath::IsFinite(MaxPlanarSpeedCmPerSec))
	{
		Result.bInputWasFinite = false;
		return Result;
	}

	Result.bWasProjectedToPlanar = !FMath::IsNearlyZero(RequestedWorldVelocityCmPerSec.Z);
	const FVector PlanarVelocity(
		RequestedWorldVelocityCmPerSec.X,
		RequestedWorldVelocityCmPerSec.Y,
		0.0);

	const double SafeMaxSpeed = FMath::Max(0.0, MaxPlanarSpeedCmPerSec);
	Result.bWasClamped = PlanarVelocity.SizeSquared2D() > FMath::Square(SafeMaxSpeed);
	Result.WorldVelocityCmPerSec = PlanarVelocity.GetClampedToMaxSize2D(SafeMaxSpeed);
	return Result;
}

void ApplyZeroVelocitySafeStop(
	FVector& DesiredVelocityLocalCmPerSec,
	FVector& DesiredVelocityWorldCmPerSec)
{
	DesiredVelocityLocalCmPerSec = FVector::ZeroVector;
	DesiredVelocityWorldCmPerSec = FVector::ZeroVector;
}
} // namespace MotionWorld
