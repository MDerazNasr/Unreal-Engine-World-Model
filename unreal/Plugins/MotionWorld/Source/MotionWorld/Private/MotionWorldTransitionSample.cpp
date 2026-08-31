#include "MotionWorldTransitionSample.h"

#include "MotionWorldCoordinateFrames.h"

namespace
{
constexpr int32 SupportedStateProtocolVersion = 1;
constexpr double TimestepToleranceSeconds = 0.001;
constexpr double PlanarToleranceCmPerSec = 0.011;
constexpr double FacingUnitTolerance = 0.001;

bool IsFiniteVector(const FVector& Value)
{
	return FMath::IsFinite(Value.X)
		&& FMath::IsFinite(Value.Y)
		&& FMath::IsFinite(Value.Z);
}

bool IsFiniteVector2D(const FVector2D& Value)
{
	return FMath::IsFinite(Value.X) && FMath::IsFinite(Value.Y);
}

bool IsStateNumericallyValid(const FMotionWorldStateSample& State)
{
	if (!State.bIsValid
		|| State.SampleSequence < 0
		|| (State.MoverStepServerFrame < 0
			&& State.MoverStepServerFrame != INDEX_NONE)
		|| !FMath::IsFinite(State.SimulationTimeSeconds)
		|| State.SimulationTimeSeconds < 0.0
		|| !FMath::IsFinite(State.StepSeconds)
		|| State.StepSeconds <= 0.0
		|| !IsFiniteVector(State.PositionWorldCm)
		|| !IsFiniteVector(State.VelocityWorldCmPerSec)
		|| !IsFiniteVector(State.VelocityLocalPlanarCmPerSec)
		|| !FMath::IsNearlyZero(State.VelocityLocalPlanarCmPerSec.Z)
		|| !FMath::IsFinite(State.FacingYawDegrees)
		|| !IsFiniteVector2D(State.FacingUnitWorld)
		|| !IsFiniteVector(State.AngularVelocityWorldDegPerSec))
	{
		return false;
	}

	const double FacingYawRadians = FMath::DegreesToRadians(State.FacingYawDegrees);
	const FVector2D ExpectedFacingUnit(
		FMath::Cos(FacingYawRadians),
		FMath::Sin(FacingYawRadians));

	return FMath::IsNearlyEqual(
			State.FacingUnitWorld.SizeSquared(),
			1.0,
			FacingUnitTolerance)
		&& State.FacingUnitWorld.Equals(ExpectedFacingUnit, FacingUnitTolerance);
}
} // namespace

namespace MotionWorld
{
FMotionWorldTransitionSample BuildTransitionSample(
	const FTransitionSampleInputs& Inputs)
{
	FMotionWorldTransitionSample Result;
	Result.EpisodeId = Inputs.EpisodeId;
	Result.TransitionSequence = Inputs.TransitionSequence;

	if (Inputs.EpisodeId < 0)
	{
		Result.RejectionReason = EMotionWorldTransitionRejectionReason::InvalidEpisodeId;
		return Result;
	}

	if (Inputs.TransitionSequence < 0)
	{
		Result.RejectionReason =
			EMotionWorldTransitionRejectionReason::InvalidTransitionSequence;
		return Result;
	}

	if (!IsStateNumericallyValid(Inputs.PreviousState))
	{
		Result.RejectionReason = EMotionWorldTransitionRejectionReason::InvalidPreviousState;
		return Result;
	}

	if (!IsStateNumericallyValid(Inputs.NextState))
	{
		Result.RejectionReason = EMotionWorldTransitionRejectionReason::InvalidNextState;
		return Result;
	}

	Result.PreviousState = Inputs.PreviousState;
	Result.NextState = Inputs.NextState;
	Result.StartSimulationTimeSeconds = Inputs.PreviousState.SimulationTimeSeconds;
	Result.EndSimulationTimeSeconds = Inputs.NextState.SimulationTimeSeconds;

	if (Inputs.PreviousState.ProtocolVersion != SupportedStateProtocolVersion
		|| Inputs.NextState.ProtocolVersion != SupportedStateProtocolVersion)
	{
		Result.RejectionReason =
			EMotionWorldTransitionRejectionReason::UnsupportedStateProtocol;
		return Result;
	}

	if (Inputs.PreviousState.bIsResimulation || Inputs.NextState.bIsResimulation)
	{
		Result.RejectionReason = EMotionWorldTransitionRejectionReason::Resimulation;
		return Result;
	}

	if (Inputs.NextState.SampleSequence <= Inputs.PreviousState.SampleSequence
		|| Inputs.NextState.SampleSequence - Inputs.PreviousState.SampleSequence != 1)
	{
		Result.RejectionReason =
			EMotionWorldTransitionRejectionReason::NonContiguousStateSequence;
		return Result;
	}

	const bool bPreviousMoverFrameIsAvailable =
		Inputs.PreviousState.MoverStepServerFrame != INDEX_NONE;
	const bool bNextMoverFrameIsAvailable =
		Inputs.NextState.MoverStepServerFrame != INDEX_NONE;
	if (bPreviousMoverFrameIsAvailable != bNextMoverFrameIsAvailable)
	{
		Result.RejectionReason =
			EMotionWorldTransitionRejectionReason::NonContiguousMoverFrame;
		return Result;
	}

	const bool bBothMoverFramesAreAvailable =
		bPreviousMoverFrameIsAvailable && bNextMoverFrameIsAvailable;
	if (bBothMoverFramesAreAvailable
		&& (Inputs.NextState.MoverStepServerFrame
				<= Inputs.PreviousState.MoverStepServerFrame
			|| Inputs.NextState.MoverStepServerFrame
				- Inputs.PreviousState.MoverStepServerFrame != 1))
	{
		Result.RejectionReason =
			EMotionWorldTransitionRejectionReason::NonContiguousMoverFrame;
		return Result;
	}

	Result.DeltaTimeSeconds =
		Inputs.NextState.SimulationTimeSeconds
		- Inputs.PreviousState.SimulationTimeSeconds;
	if (!FMath::IsFinite(Result.DeltaTimeSeconds) || Result.DeltaTimeSeconds <= 0.0)
	{
		Result.RejectionReason =
			EMotionWorldTransitionRejectionReason::NonIncreasingSimulationTime;
		return Result;
	}

	if (!FMath::IsNearlyEqual(
		Result.DeltaTimeSeconds,
		Inputs.NextState.StepSeconds,
		TimestepToleranceSeconds))
	{
		Result.RejectionReason = EMotionWorldTransitionRejectionReason::TimestepMismatch;
		return Result;
	}

	if (!Inputs.bAppliedInputWasVelocity)
	{
		Result.RejectionReason =
			EMotionWorldTransitionRejectionReason::UnsupportedActionType;
		return Result;
	}

	if (!IsFiniteVector(Inputs.AppliedVelocityWorldCmPerSec))
	{
		Result.RejectionReason = EMotionWorldTransitionRejectionReason::NonFiniteAction;
		return Result;
	}

	if (!FMath::IsNearlyZero(
		Inputs.AppliedVelocityWorldCmPerSec.Z,
		PlanarToleranceCmPerSec))
	{
		Result.RejectionReason = EMotionWorldTransitionRejectionReason::NonPlanarAction;
		return Result;
	}

	Result.AppliedAction.Type = EMotionWorldAppliedActionType::DesiredVelocity;
	Result.AppliedAction.bIsValid = true;
	Result.AppliedAction.bWasMotionWorldAutomated = Inputs.bWasMotionWorldAutomated;
	Result.AppliedAction.VelocityWorldCmPerSec = FVector(
		Inputs.AppliedVelocityWorldCmPerSec.X,
		Inputs.AppliedVelocityWorldCmPerSec.Y,
		0.0);
	Result.AppliedAction.VelocityLocalPlanarCmPerSec =
		WorldToCharacterLocalPlanarVelocity(
			Result.AppliedAction.VelocityWorldCmPerSec,
			Inputs.PreviousState.FacingYawDegrees);
	Result.bIsValid = true;
	Result.RejectionReason = EMotionWorldTransitionRejectionReason::None;
	return Result;
}
} // namespace MotionWorld
