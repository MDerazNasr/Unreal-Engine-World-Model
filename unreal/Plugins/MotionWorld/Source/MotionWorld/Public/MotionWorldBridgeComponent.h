#pragma once

#include "Components/ActorComponent.h"
#include "MoverSimulationTypes.h"
#include "MotionWorldBridgeComponent.generated.h"

class UMoverComponent;

/**
 * Safe, opt-in command seam between MotionWorld and Unreal Mover.
 *
 * With automation disabled (the default), this component does not modify
 * Mover input. When enabled, it contributes a bounded world-space planar
 * velocity and verifies the command retained by Mover after simulation.
 */
UCLASS(ClassGroup = (MotionWorld), BlueprintType, meta = (BlueprintSpawnableComponent))
class MOTIONWORLD_API UMotionWorldBridgeComponent final
	: public UActorComponent
	, public IMoverInputProducerInterface
{
	GENERATED_BODY()

public:
	UMotionWorldBridgeComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void ProduceInput_Implementation(
		int32 SimTimeMs,
		FMoverInputCmdContext& InputCmdResult) override;

	/** Enables or disables replacement of the ordinary movement command. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Command")
	void SetAutomationEnabled(bool bEnabled);

	/**
	 * Stores a world-space velocity request in centimetres per second.
	 * Returns false and leaves the previous request unchanged for NaN/infinity.
	 */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Command")
	bool SetDesiredVelocityWorldCmPerSec(const FVector& RequestedVelocity);

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	bool IsAutomationEnabled() const { return bAutomationEnabled; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	FVector GetDesiredVelocityWorldCmPerSec() const { return DesiredVelocityWorldCmPerSec; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	FVector GetLastEchoedVelocityWorldCmPerSec() const { return LastEchoedVelocityWorldCmPerSec; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	bool DidLastCommandEchoMatch() const { return bLastCommandEchoMatched; }

protected:
	/** False by default so merely adding the component preserves human control. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Command")
	bool bAutomationEnabled = false;

	/** Requested world-space XY velocity. Unreal distance units are centimetres. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Command")
	FVector DesiredVelocityWorldCmPerSec = FVector::ZeroVector;

	/** Maximum allowed XY speed in centimetres per second. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Command", meta = (ClampMin = "0.0"))
	double MaxPlanarSpeedCmPerSec = 600.0;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Evidence")
	FVector LastEchoedVelocityWorldCmPerSec = FVector::ZeroVector;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Evidence")
	bool bLastCommandEchoMatched = false;

private:
	UFUNCTION()
	void HandlePostFinalize(
		const FMoverSyncState& SyncState,
		const FMoverAuxStateContext& AuxState);

	UPROPERTY(Transient)
	TObjectPtr<UMoverComponent> MoverComponent;

	FVector LastSubmittedVelocityWorldCmPerSec = FVector::ZeroVector;
	uint64 CommandRevision = 0;
	uint64 LastLoggedRevision = MAX_uint64;
	bool bLastSubmittedInputWasFinite = true;
};
