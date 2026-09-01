#include "MotionWorldTimedGate.h"

namespace
{
	bool IsFiniteVector(const FVector& Value)
	{
		return !Value.ContainsNaN();
	}

	double WrapPositiveRadians(const double Radians)
	{
		const double Wrapped = FMath::Fmod(Radians, 2.0 * UE_DOUBLE_PI);
		return Wrapped < 0.0 ? Wrapped + 2.0 * UE_DOUBLE_PI : Wrapped;
	}
}

bool MotionWorld::IsTimedGateConfigValid(
	const FMotionWorldTimedGateConfig& Config)
{
	return Config.ScenarioSeed >= 0
		&& Config.MotionType
			== EMotionWorldGateMotionType::SinusoidalTranslation
		&& IsFiniteVector(Config.OriginWorldCm)
		&& IsFiniteVector(Config.MotionAxisWorld)
		&& Config.MotionAxisWorld.SizeSquared() > UE_DOUBLE_SMALL_NUMBER
		&& FMath::IsFinite(Config.AmplitudeCm)
		&& Config.AmplitudeCm >= 0.0
		&& FMath::IsFinite(Config.PeriodSeconds)
		&& Config.PeriodSeconds > UE_DOUBLE_SMALL_NUMBER
		&& FMath::IsFinite(Config.PhaseOffsetRadians)
		&& IsFiniteVector(Config.HalfExtentsCm)
		&& Config.HalfExtentsCm.X > 0.0
		&& Config.HalfExtentsCm.Y > 0.0
		&& Config.HalfExtentsCm.Z > 0.0
		&& IsFiniteVector(Config.CrossingPlaneNormalWorld)
		&& Config.CrossingPlaneNormalWorld.SizeSquared() > UE_DOUBLE_SMALL_NUMBER
		&& FMath::Abs(FVector::DotProduct(
			Config.MotionAxisWorld.GetSafeNormal(),
			Config.CrossingPlaneNormalWorld.GetSafeNormal())) <= 1.e-6
		&& FMath::IsFinite(Config.TimeoutSeconds)
		&& Config.TimeoutSeconds > 0.0;
}

FMotionWorldTimedGateState MotionWorld::EvaluateTimedGateSchedule(
	const FMotionWorldTimedGateConfig& Config,
	const double ScenarioTimeSeconds)
{
	FMotionWorldTimedGateState State;
	State.ScenarioTimeSeconds = ScenarioTimeSeconds;
	if (!IsTimedGateConfigValid(Config)
		|| !FMath::IsFinite(ScenarioTimeSeconds)
		|| ScenarioTimeSeconds < 0.0)
	{
		return State;
	}

	const FVector MotionAxis = Config.MotionAxisWorld.GetSafeNormal();
	const double AngularFrequencyRadiansPerSecond =
		2.0 * UE_DOUBLE_PI / Config.PeriodSeconds;
	const double UnwrappedPhase = Config.PhaseOffsetRadians
		+ AngularFrequencyRadiansPerSecond * ScenarioTimeSeconds;
	State.PhaseRadians = WrapPositiveRadians(UnwrappedPhase);
	State.CenterWorldCm = Config.OriginWorldCm
		+ MotionAxis * Config.AmplitudeCm * FMath::Sin(UnwrappedPhase);
	State.VelocityWorldCmPerSec = MotionAxis
		* Config.AmplitudeCm
		* AngularFrequencyRadiansPerSecond
		* FMath::Cos(UnwrappedPhase);
	State.bIsValid = IsFiniteVector(State.CenterWorldCm)
		&& IsFiniteVector(State.VelocityWorldCmPerSec)
		&& FMath::IsFinite(State.PhaseRadians);
	return State;
}

FMotionWorldScenarioStepResult MotionWorld::EvaluateTimedGateScenarioStep(
	const FMotionWorldTimedGateConfig& Config,
	const FVector& PreviousAgentPositionWorldCm,
	const FVector& CurrentAgentPositionWorldCm,
	const double ScenarioTimeSeconds,
	const bool bGateCollisionThisStep)
{
	FMotionWorldScenarioStepResult Result;
	if (!IsTimedGateConfigValid(Config)
		|| !IsFiniteVector(PreviousAgentPositionWorldCm)
		|| !IsFiniteVector(CurrentAgentPositionWorldCm)
		|| !FMath::IsFinite(ScenarioTimeSeconds)
		|| ScenarioTimeSeconds < 0.0)
	{
		Result.TerminationReason =
			EMotionWorldScenarioTerminationReason::InvalidConfiguration;
		return Result;
	}

	if (bGateCollisionThisStep)
	{
		Result.TerminationReason =
			EMotionWorldScenarioTerminationReason::GateCollision;
		return Result;
	}

	const FVector CrossingNormal =
		Config.CrossingPlaneNormalWorld.GetSafeNormal();
	const double PreviousSignedDistance = FVector::DotProduct(
		PreviousAgentPositionWorldCm - Config.OriginWorldCm,
		CrossingNormal);
	const double CurrentSignedDistance = FVector::DotProduct(
		CurrentAgentPositionWorldCm - Config.OriginWorldCm,
		CrossingNormal);
	Result.bCrossedSuccessPlaneThisStep =
		PreviousSignedDistance <= 0.0 && CurrentSignedDistance > 0.0;
	if (Result.bCrossedSuccessPlaneThisStep)
	{
		Result.TerminationReason =
			EMotionWorldScenarioTerminationReason::Success;
	}
	else if (ScenarioTimeSeconds >= Config.TimeoutSeconds)
	{
		Result.TerminationReason =
			EMotionWorldScenarioTerminationReason::Timeout;
	}
	return Result;
}

const TCHAR* MotionWorld::LexToString(
	const EMotionWorldScenarioTerminationReason Reason)
{
	switch (Reason)
	{
	case EMotionWorldScenarioTerminationReason::None:
		return TEXT("none");
	case EMotionWorldScenarioTerminationReason::Success:
		return TEXT("success");
	case EMotionWorldScenarioTerminationReason::GateCollision:
		return TEXT("gate_collision");
	case EMotionWorldScenarioTerminationReason::Timeout:
		return TEXT("timeout");
	case EMotionWorldScenarioTerminationReason::InvalidConfiguration:
		return TEXT("invalid_configuration");
	default:
		return TEXT("unknown");
	}
}
