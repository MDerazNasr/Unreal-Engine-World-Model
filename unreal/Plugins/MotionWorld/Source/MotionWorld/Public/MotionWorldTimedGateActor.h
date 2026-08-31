#pragma once

#include "GameFramework/Actor.h"
#include "MotionWorldTimedGate.h"
#include "MotionWorldTimedGateActor.generated.h"

class AActor;
class UBoxComponent;
class UPrimitiveComponent;
class UStaticMeshComponent;
struct FHitResult;

/**
 * Visible, collidable runtime realization of the pure timed-gate schedule.
 * Position is recomputed from absolute scenario time every tick; it is never integrated.
 */
UCLASS(BlueprintType, Blueprintable)
class MOTIONWORLD_API AMotionWorldTimedGateActor final : public AActor
{
	GENERATED_BODY()

public:
	AMotionWorldTimedGateActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Applies a complete validated schedule and starts it at ScenarioStartWorldTimeSeconds. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Gate")
	bool InitializeTimedGate(
		const FMotionWorldTimedGateConfig& NewConfig,
		AActor* NewTrackedAgent,
		double ScenarioStartWorldTimeSeconds);

	/** Restarts schedule time and clears all collision evidence. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Gate")
	bool ResetTimedGate(double ScenarioStartWorldTimeSeconds);

	/** Returns and clears whether the tracked agent contacted the gate since the last call. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Gate")
	bool ConsumeTrackedAgentCollision();

	/** Freezes the gate and disables collision after a terminal scenario event. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Gate")
	void DeactivateTimedGate();

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Gate")
	FMotionWorldTimedGateConfig GetGateConfig() const { return GateConfig; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Gate")
	FMotionWorldTimedGateState GetGateState() const { return GateState; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Gate")
	int64 GetTrackedAgentCollisionCount() const { return TrackedAgentCollisionCount; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Gate")
	bool IsScenarioActive() const { return bScenarioActive; }

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	TObjectPtr<UBoxComponent> CollisionBox;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	TObjectPtr<UStaticMeshComponent> VisualMesh;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Gate")
	FMotionWorldTimedGateConfig GateConfig;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Gate")
	FMotionWorldTimedGateState GateState;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Gate")
	int64 TrackedAgentCollisionCount = 0;

private:
	UFUNCTION()
	void HandleCollisionBoxHit(
		UPrimitiveComponent* HitComponent,
		AActor* OtherActor,
		UPrimitiveComponent* OtherComponent,
		FVector NormalImpulse,
		const FHitResult& Hit);

	bool ApplyScheduleAtScenarioTime(double ScenarioTimeSeconds);

	UPROPERTY(Transient)
	TObjectPtr<AActor> TrackedAgent;

	double ScenarioStartWorldTimeSeconds = 0.0;
	bool bScenarioActive = false;
	bool bTrackedAgentCollisionPending = false;
};
