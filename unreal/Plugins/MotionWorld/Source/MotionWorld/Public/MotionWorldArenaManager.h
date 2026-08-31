#pragma once

#include "GameFramework/Actor.h"
#include "MotionWorldTimedGate.h"
#include "MotionWorldArenaManager.generated.h"

class AMotionWorldTimedGateActor;

USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldArenaStatus
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	bool bIsInitialized = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	bool bIsActive = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	int64 ScenarioSeed = -1;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	double ScenarioTimeSeconds = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	int64 CollisionCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	EMotionWorldScenarioTerminationReason TerminationReason =
		EMotionWorldScenarioTerminationReason::None;
};

/** Owns timed-gate lifecycle and turns finalized character observations into scenario events. */
UCLASS(BlueprintType)
class MOTIONWORLD_API AMotionWorldArenaManager final : public AActor
{
	GENERATED_BODY()

public:
	AMotionWorldArenaManager();

	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	bool InitializeArena(
		AActor* NewTrackedAgent,
		const FMotionWorldTimedGateConfig& NewGateConfig,
		double ScenarioStartWorldTimeSeconds);

	bool ResetArena(double ScenarioStartWorldTimeSeconds);

	FMotionWorldScenarioStepResult ObserveFinalizedAgentPosition(
		const FVector& AgentPositionWorldCm);

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Arena")
	FMotionWorldArenaStatus GetArenaStatus() const { return ArenaStatus; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Arena")
	FMotionWorldTimedGateConfig GetGateConfig() const { return GateConfig; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Arena")
	FMotionWorldTimedGateState GetGateState() const;

private:
	UPROPERTY(Transient)
	TObjectPtr<AActor> TrackedAgent;

	UPROPERTY(Transient)
	TObjectPtr<AMotionWorldTimedGateActor> TimedGate;

	FMotionWorldTimedGateConfig GateConfig;
	FMotionWorldArenaStatus ArenaStatus;
	FVector PreviousAgentPositionWorldCm = FVector::ZeroVector;
	bool bHasPreviousAgentPosition = false;
};
