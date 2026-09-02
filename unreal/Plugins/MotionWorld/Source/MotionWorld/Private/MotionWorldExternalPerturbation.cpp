#include "MotionWorldExternalPerturbation.h"

namespace
{
constexpr int32 SupportedExternalPerturbationProtocolVersion = 1;
constexpr double MaximumPlanarVelocityKickCmPerSec = 1000.0;

bool IsFinitePlanarVector(const FVector& Value)
{
	return FMath::IsFinite(Value.X)
		&& FMath::IsFinite(Value.Y)
		&& FMath::IsFinite(Value.Z)
		&& FMath::IsNearlyZero(Value.Z);
}
} // namespace

FMotionWorldExternalPerturbation MotionWorld::MakeAdditiveVelocityPerturbation(
	const FVector& RequestedVelocityDeltaWorldCmPerSec,
	const int64 QueuedAfterStateSampleSequence,
	const int32 QueuedAfterMoverStepServerFrame,
	const bool bWasMotionWorldScheduled)
{
	FMotionWorldExternalPerturbation Result;
	Result.Type = EMotionWorldExternalPerturbationType::AdditiveVelocity;
	Result.bWasMotionWorldScheduled = bWasMotionWorldScheduled;
	Result.RequestedVelocityDeltaWorldCmPerSec =
		RequestedVelocityDeltaWorldCmPerSec;
	Result.QueuedAfterStateSampleSequence = QueuedAfterStateSampleSequence;
	Result.QueuedAfterMoverStepServerFrame = QueuedAfterMoverStepServerFrame;
	Result.bIsValid = IsExternalPerturbationValid(Result);
	if (!Result.bIsValid)
	{
		Result.RequestedVelocityDeltaWorldCmPerSec = FVector::ZeroVector;
		Result.QueuedAfterStateSampleSequence = -1;
		Result.QueuedAfterMoverStepServerFrame = INDEX_NONE;
	}
	return Result;
}

bool MotionWorld::IsExternalPerturbationValid(
	const FMotionWorldExternalPerturbation& Perturbation)
{
	if (Perturbation.ProtocolVersion
		!= SupportedExternalPerturbationProtocolVersion
		|| !Perturbation.bIsValid)
	{
		return false;
	}

	if (Perturbation.Type == EMotionWorldExternalPerturbationType::None)
	{
		return !Perturbation.bWasMotionWorldScheduled
			&& Perturbation.RequestedVelocityDeltaWorldCmPerSec.IsNearlyZero()
			&& Perturbation.QueuedAfterStateSampleSequence == -1
			&& Perturbation.QueuedAfterMoverStepServerFrame == INDEX_NONE;
	}

	return Perturbation.Type
			== EMotionWorldExternalPerturbationType::AdditiveVelocity
		&& IsFinitePlanarVector(
			Perturbation.RequestedVelocityDeltaWorldCmPerSec)
		&& !Perturbation.RequestedVelocityDeltaWorldCmPerSec.IsNearlyZero()
		&& Perturbation.RequestedVelocityDeltaWorldCmPerSec.Size2D()
			<= MaximumPlanarVelocityKickCmPerSec
		&& Perturbation.QueuedAfterStateSampleSequence >= 0
		&& Perturbation.QueuedAfterMoverStepServerFrame >= INDEX_NONE;
}
