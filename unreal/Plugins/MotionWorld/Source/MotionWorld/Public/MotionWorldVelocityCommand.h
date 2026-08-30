#pragma once

#include "CoreMinimal.h"

namespace MotionWorld
{
struct FSanitizedVelocityCommand
{
	FVector WorldVelocityCmPerSec = FVector::ZeroVector;
	bool bInputWasFinite = true;
	bool bWasClamped = false;
	bool bWasProjectedToPlanar = false;
};

/**
 * Validates and bounds a world-space ground-plane velocity command.
 *
 * Non-finite input fails closed to zero. Finite input is projected onto XY and
 * clamped without changing its planar direction.
 */
MOTIONWORLD_API FSanitizedVelocityCommand SanitizeWorldVelocityCommand(
	const FVector& RequestedWorldVelocityCmPerSec,
	double MaxPlanarSpeedCmPerSec);
} // namespace MotionWorld
