#pragma once

#include "CoreMinimal.h"
#include "MotionWorldTimedGate.generated.h"

UENUM(BlueprintType)
enum class EMotionWorldGateMotionType : uint8
{
	SinusoidalTranslation UMETA(DisplayName = "Sinusoidal Translation")
};

UENUM(BlueprintType)
enum class EMotionWorldScenarioTerminationReason : uint8
{
	None,
	Success,
	GateCollision,
	Timeout,
	InvalidConfiguration
};

/** Immutable parameters that fully determine one timed-gate schedule. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldTimedGateConfig
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate")
	int64 ScenarioSeed = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate")
	EMotionWorldGateMotionType MotionType =
		EMotionWorldGateMotionType::SinusoidalTranslation;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate")
	FVector OriginWorldCm = FVector::ZeroVector;

	/** Normalized internally; must be finite and nonzero. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate")
	FVector MotionAxisWorld = FVector::RightVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate", meta = (ClampMin = "0.0"))
	double AmplitudeCm = 200.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate", meta = (ClampMin = "0.001"))
	double PeriodSeconds = 4.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate")
	double PhaseOffsetRadians = 0.0;

	/** Collision half-size of the moving blocker. Every component must be positive. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate")
	FVector HalfExtentsCm = FVector(30.0, 150.0, 120.0);

	/** Fixed success plane through OriginWorldCm; normalized internally. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate")
	FVector CrossingPlaneNormalWorld = FVector::ForwardVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "MotionWorld|Gate", meta = (ClampMin = "0.001"))
	double TimeoutSeconds = 8.0;
};

/** Analytic gate state evaluated directly from config and scenario time. */
USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldTimedGateState
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	bool bIsValid = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	double ScenarioTimeSeconds = 0.0;

	/** Wrapped to [0, 2*pi). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	double PhaseRadians = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	FVector CenterWorldCm = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	FVector VelocityWorldCmPerSec = FVector::ZeroVector;
};

USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldScenarioStepResult
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Scenario")
	bool bCrossedSuccessPlaneThisStep = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Scenario")
	EMotionWorldScenarioTerminationReason TerminationReason =
		EMotionWorldScenarioTerminationReason::None;
};

namespace MotionWorld
{
	MOTIONWORLD_API bool IsTimedGateConfigValid(
		const FMotionWorldTimedGateConfig& Config);

	MOTIONWORLD_API FMotionWorldTimedGateState EvaluateTimedGateSchedule(
		const FMotionWorldTimedGateConfig& Config,
		double ScenarioTimeSeconds);

	/**
	 * Evaluates terminal events for one finalized character step.
	 * Collision has priority over crossing, which has priority over timeout.
	 * Demo continuation reports a crossing but does not classify it as terminal.
	 */
	MOTIONWORLD_API FMotionWorldScenarioStepResult EvaluateTimedGateScenarioStep(
		const FMotionWorldTimedGateConfig& Config,
		const FVector& PreviousAgentPositionWorldCm,
		const FVector& CurrentAgentPositionWorldCm,
		double ScenarioTimeSeconds,
		bool bGateCollisionThisStep,
		bool bContinueAfterSuccessPlaneCrossing = false);

	MOTIONWORLD_API const TCHAR* LexToString(
		EMotionWorldScenarioTerminationReason Reason);
}
