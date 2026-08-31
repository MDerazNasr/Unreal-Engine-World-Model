#include "MotionWorldStateSample.h"

#include "MotionWorldCoordinateFrames.h"

namespace MotionWorld
{
FMotionWorldStateSample BuildAuthoritativeStateSample(
	const FAuthoritativeStateInputs& Inputs)
{
	FMotionWorldStateSample Result;
	Result.SampleSequence = Inputs.SampleSequence;
	Result.MoverStepServerFrame = Inputs.MoverStepServerFrame;
	Result.bIsResimulation = Inputs.bIsResimulation;
	Result.MovementMode = Inputs.MovementMode;

	const bool bTimeIsFinite = FMath::IsFinite(Inputs.SimulationTimeSeconds);
	const bool bStepIsFinite = FMath::IsFinite(Inputs.StepSeconds);
	Result.SimulationTimeSeconds = bTimeIsFinite
		? Inputs.SimulationTimeSeconds
		: -1.0;
	Result.StepSeconds = bStepIsFinite ? Inputs.StepSeconds : -1.0;

	const bool bStateIsFinite = !Inputs.PositionWorldCm.ContainsNaN()
		&& !Inputs.VelocityWorldCmPerSec.ContainsNaN()
		&& !Inputs.OrientationWorldDegrees.ContainsNaN()
		&& !Inputs.AngularVelocityWorldDegPerSec.ContainsNaN();

	Result.bIsValid = Inputs.bHasAuthoritativeSource
		&& Inputs.SampleSequence >= 0
		&& bTimeIsFinite
		&& Inputs.SimulationTimeSeconds >= 0.0
		&& bStepIsFinite
		&& Inputs.StepSeconds > 0.0
		&& bStateIsFinite;

	if (!Result.bIsValid)
	{
		return Result;
	}

	Result.PositionWorldCm = Inputs.PositionWorldCm;
	Result.VelocityWorldCmPerSec = Inputs.VelocityWorldCmPerSec;
	Result.FacingYawDegrees = FRotator::NormalizeAxis(Inputs.OrientationWorldDegrees.Yaw);
	Result.VelocityLocalPlanarCmPerSec = WorldToCharacterLocalPlanarVelocity(
		Inputs.VelocityWorldCmPerSec,
		Result.FacingYawDegrees);
	Result.AngularVelocityWorldDegPerSec = Inputs.AngularVelocityWorldDegPerSec;

	double SinYaw = 0.0;
	double CosYaw = 1.0;
	FMath::SinCos(
		&SinYaw,
		&CosYaw,
		FMath::DegreesToRadians(Result.FacingYawDegrees));
	Result.FacingUnitWorld = FVector2D(CosYaw, SinYaw);

	return Result;
}
} // namespace MotionWorld
