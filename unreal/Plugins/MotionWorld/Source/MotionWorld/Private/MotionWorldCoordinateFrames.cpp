#include "MotionWorldCoordinateFrames.h"

namespace MotionWorld
{
FVector CharacterLocalToWorldPlanarVelocity(
	const FVector& LocalVelocityCmPerSec,
	const double FacingYawDegrees)
{
	double SinYaw = 0.0;
	double CosYaw = 1.0;
	FMath::SinCos(
		&SinYaw,
		&CosYaw,
		FMath::DegreesToRadians(FacingYawDegrees));

	return FVector(
		CosYaw * LocalVelocityCmPerSec.X - SinYaw * LocalVelocityCmPerSec.Y,
		SinYaw * LocalVelocityCmPerSec.X + CosYaw * LocalVelocityCmPerSec.Y,
		0.0);
}

FVector WorldToCharacterLocalPlanarVelocity(
	const FVector& WorldVelocityCmPerSec,
	const double FacingYawDegrees)
{
	double SinYaw = 0.0;
	double CosYaw = 1.0;
	FMath::SinCos(
		&SinYaw,
		&CosYaw,
		FMath::DegreesToRadians(FacingYawDegrees));

	return FVector(
		CosYaw * WorldVelocityCmPerSec.X + SinYaw * WorldVelocityCmPerSec.Y,
		-SinYaw * WorldVelocityCmPerSec.X + CosYaw * WorldVelocityCmPerSec.Y,
		0.0);
}
} // namespace MotionWorld
