#pragma once

#include "CoreMinimal.h"

namespace MotionWorld
{
/** Converts an Unreal planar velocity from character-local axes to world axes. */
MOTIONWORLD_API FVector CharacterLocalToWorldPlanarVelocity(
	const FVector& LocalVelocityCmPerSec,
	double FacingYawDegrees);

/** Converts an Unreal planar velocity from world axes to character-local axes. */
MOTIONWORLD_API FVector WorldToCharacterLocalPlanarVelocity(
	const FVector& WorldVelocityCmPerSec,
	double FacingYawDegrees);
} // namespace MotionWorld
