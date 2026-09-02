#include "MotionWorldNominalContext.h"

namespace
{
	bool IsFiniteVector(const FVector& Value)
	{
		return FMath::IsFinite(Value.X)
			&& FMath::IsFinite(Value.Y)
			&& FMath::IsFinite(Value.Z);
	}

	bool IsFiniteUnitQuat(const FQuat& Value)
	{
		return FMath::IsFinite(Value.X)
			&& FMath::IsFinite(Value.Y)
			&& FMath::IsFinite(Value.Z)
			&& FMath::IsFinite(Value.W)
			&& FMath::IsNearlyEqual(Value.SizeSquared(), 1.0, 1.0e-4);
	}
}

bool MotionWorld::AreSmoothWalkingParametersValid(
	const FMotionWorldSmoothWalkingParameters& Parameters)
{
	const double Values[] = {
		Parameters.AccelerationCmPerSecSquared,
		Parameters.DecelerationCmPerSecSquared,
		Parameters.DirectionalAccelerationFactor,
		Parameters.TurningStrength,
		Parameters.AccelerationSmoothingTimeSeconds,
		Parameters.DecelerationSmoothingTimeSeconds,
		Parameters.AccelerationSmoothingCompensation,
		Parameters.DecelerationSmoothingCompensation,
		Parameters.VelocityDeadzoneCmPerSec,
		Parameters.AccelerationDeadzoneCmPerSecSquared,
		Parameters.OutsideInfluenceSmoothingTimeSeconds,
		Parameters.FacingSmoothingTimeSeconds,
		Parameters.FacingDeadzoneDegrees,
		Parameters.AngularVelocityDeadzoneDegreesPerSec
	};
	for (const double Value : Values)
	{
		if (!FMath::IsFinite(Value))
		{
			return false;
		}
	}
	return Parameters.AccelerationCmPerSecSquared >= 0.0
		&& Parameters.DecelerationCmPerSecSquared >= 0.0
		&& Parameters.DirectionalAccelerationFactor >= 0.0
		&& Parameters.DirectionalAccelerationFactor <= 1.0
		&& Parameters.TurningStrength >= 0.0
		&& Parameters.AccelerationSmoothingTimeSeconds >= 0.0
		&& Parameters.DecelerationSmoothingTimeSeconds >= 0.0
		&& Parameters.AccelerationSmoothingCompensation >= 0.0
		&& Parameters.AccelerationSmoothingCompensation <= 1.0
		&& Parameters.DecelerationSmoothingCompensation >= 0.0
		&& Parameters.DecelerationSmoothingCompensation <= 1.0
		&& Parameters.VelocityDeadzoneCmPerSec >= 0.0
		&& Parameters.AccelerationDeadzoneCmPerSecSquared >= 0.0
		&& Parameters.OutsideInfluenceSmoothingTimeSeconds >= 0.0
		&& Parameters.FacingSmoothingTimeSeconds >= 0.0
		&& Parameters.FacingDeadzoneDegrees >= 0.0
		&& Parameters.AngularVelocityDeadzoneDegreesPerSec >= 0.0;
}

bool MotionWorld::IsSimpleWalkingInputPreparationValid(
	const FMotionWorldSimpleWalkingInputPreparation& InputPreparation)
{
	if (InputPreparation.bHasMaxMoveSpeed)
	{
		return FMath::IsFinite(InputPreparation.EffectiveMaxSpeedCmPerSec)
			&& InputPreparation.EffectiveMaxSpeedCmPerSec >= 0.0
			&& (InputPreparation.MaxSpeedSource == EMotionWorldMaxSpeedSource::ModeOverride
				|| InputPreparation.MaxSpeedSource == EMotionWorldMaxSpeedSource::CommonLegacySettings);
	}
	return InputPreparation.EffectiveMaxSpeedCmPerSec == 0.0
		&& InputPreparation.MaxSpeedSource == EMotionWorldMaxSpeedSource::Unbounded;
}

bool MotionWorld::IsNominalContextSampleValid(
	const FMotionWorldNominalContextSample& Sample)
{
	return Sample.ProtocolVersion == 2
		&& Sample.bIsValid
		&& Sample.AuthoritativeStateSampleSequence >= 0
		&& !Sample.MovementModeName.IsNone()
		&& !Sample.MovementModeClass.IsNone()
		&& Sample.FailureReason.IsNone()
		&& AreSmoothWalkingParametersValid(Sample.Parameters)
		&& IsSimpleWalkingInputPreparationValid(Sample.InputPreparation)
		&& IsFiniteVector(Sample.InternalState.SpringVelocityWorldCmPerSec)
		&& IsFiniteVector(Sample.InternalState.SpringAccelerationWorldCmPerSecSquared)
		&& IsFiniteVector(Sample.InternalState.IntermediateVelocityWorldCmPerSec)
		&& IsFiniteUnitQuat(Sample.InternalState.IntermediateFacingWorld)
		&& IsFiniteVector(Sample.InternalState.IntermediateAngularVelocityWorldRadPerSec);
}

FMotionWorldNominalContextSample MotionWorld::BuildNominalContextSample(
	const FMotionWorldSmoothWalkingDiagnosticSample& Diagnostic)
{
	FMotionWorldNominalContextSample Result;
	Result.AuthoritativeStateSampleSequence = Diagnostic.AuthoritativeStateSampleSequence;
	Result.MovementModeName = Diagnostic.MovementModeName;
	Result.MovementModeClass = Diagnostic.MovementModeClass;
	Result.FailureReason = Diagnostic.FailureReason;

	if (Diagnostic.ProtocolVersion != 2)
	{
		Result.FailureReason = TEXT("unsupported_diagnostic_protocol");
		return Result;
	}
	if (!Diagnostic.bIsValid || !Diagnostic.FailureReason.IsNone())
	{
		if (Result.FailureReason.IsNone())
		{
			Result.FailureReason = TEXT("invalid_diagnostic_sample");
		}
		return Result;
	}

	Result.Parameters.AccelerationCmPerSecSquared = Diagnostic.AccelerationCmPerSecSquared;
	Result.Parameters.DecelerationCmPerSecSquared = Diagnostic.DecelerationCmPerSecSquared;
	Result.Parameters.DirectionalAccelerationFactor = Diagnostic.DirectionalAccelerationFactor;
	Result.Parameters.TurningStrength = Diagnostic.TurningStrength;
	Result.Parameters.AccelerationSmoothingTimeSeconds = Diagnostic.AccelerationSmoothingTimeSeconds;
	Result.Parameters.DecelerationSmoothingTimeSeconds = Diagnostic.DecelerationSmoothingTimeSeconds;
	Result.Parameters.AccelerationSmoothingCompensation = Diagnostic.AccelerationSmoothingCompensation;
	Result.Parameters.DecelerationSmoothingCompensation = Diagnostic.DecelerationSmoothingCompensation;
	Result.Parameters.VelocityDeadzoneCmPerSec = Diagnostic.VelocityDeadzoneCmPerSec;
	Result.Parameters.AccelerationDeadzoneCmPerSecSquared = Diagnostic.AccelerationDeadzoneCmPerSecSquared;
	Result.Parameters.OutsideInfluenceSmoothingTimeSeconds = Diagnostic.OutsideInfluenceSmoothingTimeSeconds;
	Result.Parameters.FacingSmoothingTimeSeconds = Diagnostic.FacingSmoothingTimeSeconds;
	Result.Parameters.bSmoothFacingWithDoubleSpring = Diagnostic.bSmoothFacingWithDoubleSpring;
	Result.Parameters.FacingDeadzoneDegrees = Diagnostic.FacingDeadzoneDegrees;
	Result.Parameters.AngularVelocityDeadzoneDegreesPerSec = Diagnostic.AngularVelocityDeadzoneDegreesPerSec;
	Result.InputPreparation.bHasMaxMoveSpeed = Diagnostic.bHasMaxMoveSpeed;
	Result.InputPreparation.EffectiveMaxSpeedCmPerSec = Diagnostic.EffectiveMaxSpeedCmPerSec;
	Result.InputPreparation.MaxSpeedSource = Diagnostic.MaxSpeedSource;
	Result.InternalState.SpringVelocityWorldCmPerSec = Diagnostic.SpringVelocityWorldCmPerSec;
	Result.InternalState.SpringAccelerationWorldCmPerSecSquared =
		Diagnostic.SpringAccelerationWorldCmPerSecSquared;
	Result.InternalState.IntermediateVelocityWorldCmPerSec = Diagnostic.IntermediateVelocityWorldCmPerSec;
	Result.InternalState.IntermediateFacingWorld = Diagnostic.IntermediateFacingWorld;
	Result.InternalState.IntermediateAngularVelocityWorldRadPerSec =
		Diagnostic.IntermediateAngularVelocityWorldRadPerSec;

	Result.bIsValid = true;
	Result.FailureReason = NAME_None;
	if (!IsNominalContextSampleValid(Result))
	{
		Result.bIsValid = false;
		Result.FailureReason = TEXT("invalid_nominal_context_fields");
	}
	return Result;
}
