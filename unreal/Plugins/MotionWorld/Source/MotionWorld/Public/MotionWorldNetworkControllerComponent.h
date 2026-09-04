#pragma once

#include "Components/ActorComponent.h"
#include "MotionWorldControlVisualizationState.h"
#include "MotionWorldNetworkRuntime.h"
#include "MotionWorldUdpTransport.h"
#include "MotionWorldNetworkControllerComponent.generated.h"

class UMotionWorldBridgeComponent;
struct FMotionWorldNominalContextSample;
struct FMotionWorldStateSample;

namespace MotionWorld
{
/** Compare canonical planner-target contexts without reacting to float noise. */
MOTIONWORLD_API bool HasReactiveTargetContextChanged(
	bool bOldTargetPresent,
	const FVector& OldTargetWorldCm,
	const FVector2D& OldTerminalVelocityLocalCmPerSec,
	bool bNewTargetPresent,
	const FVector& NewTargetWorldCm,
	const FVector2D& NewTerminalVelocityLocalCmPerSec);

/** Actions are admitted only from the controller configured for this episode. */
MOTIONWORLD_API bool IsControlActionControllerCompatible(
	const FString& ConfiguredControllerMode,
	const FString& ActionControllerId);
}

USTRUCT(BlueprintType)
struct MOTIONWORLD_API FMotionWorldNetworkControllerStats
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 ObservationsSent = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 ObservationSendFailures = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 ActionsAccepted = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 RejectedActions = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 StaleActions = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 MalformedActions = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 MissedResponses = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 HeldAfterMiss = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 SafeStops = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 RejectedTransportDatagrams = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 EvidenceLinesWritten = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	int64 EvidenceLinesDropped = 0;
};

/**
 * Default-off owner of the live UDP control loop. It polls without blocking,
 * admits only the current episode/observation action, and delegates the final
 * bounded command mutation to UMotionWorldBridgeComponent.
 */
UCLASS(ClassGroup = (MotionWorld), BlueprintType, meta = (BlueprintSpawnableComponent))
class MOTIONWORLD_API UMotionWorldNetworkControllerComponent final
	: public UActorComponent
{
	GENERATED_BODY()

public:
	UMotionWorldNetworkControllerComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(
		float DeltaTime,
		ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Network")
	bool SetNetworkControlEnabled(bool bEnabled);

	/** Switching controllers invalidates all outstanding work; a new episode must follow. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Network")
	bool SetControllerMode(const FString& NewControllerMode);

	/** Close/reopen the socket and invalidate all old sequence state. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Network")
	bool ReconnectService();

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Network")
	bool IsNetworkControlEnabled() const { return bNetworkControlEnabled; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Network")
	FMotionWorldNetworkControllerStats GetNetworkStats() const { return ControllerStats; }

	/** Set the planner-only world target used by the stateless reactive proof controller. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Network")
	bool SetReactiveTarget(
		bool bTargetPresent,
		FVector TargetWorldCm,
		FVector2D DesiredTerminalVelocityLocalCmPerSec);

	/** Called by the bridge before a reset is queued. */
	void PrepareForReset();

	/** Called only after Unreal verifies the reset's finalized state. */
	bool BeginNetworkEpisode(int64 EpisodeId);

	/** Called by the bridge after state and hidden nominal context are finalized. */
	void ObserveFinalizedState(
		const FMotionWorldStateSample& State,
		const FMotionWorldNominalContextSample& NominalContext);

protected:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	bool bNetworkControlEnabled = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network", meta = (ClampMin = "1", ClampMax = "65535"))
	int32 LocalPort = 52580;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network", meta = (ClampMin = "1", ClampMax = "65535"))
	int32 RemotePort = 52581;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network")
	FString ControllerMode = TEXT("echo");

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Reactive")
	bool bHasReactiveTarget = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Reactive")
	FVector ReactiveTargetWorldCm = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Reactive")
	FVector2D ReactiveTerminalVelocityLocalCmPerSec = FVector2D::ZeroVector;

	/** Draw only visualization data admitted for the current control identity. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Visualization")
	bool bDrawWorldModelVisualization = true;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Visualization", meta = (ClampMin = "0.0", ClampMax = "1000.0"))
	float VisualizationHeightOffsetCm = 12.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Visualization", meta = (ClampMin = "0.0", ClampMax = "50.0"))
	float VisualizationLineThickness = 3.0f;

	/** Compact truthful legend/status panel for the interview demo. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Visualization")
	bool bDrawWorldModelHud = true;

	/** Default-off bounded evidence for live episode/sequence/yaw reconciliation. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Evidence")
	bool bLogNetworkEvidence = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Network|Evidence", meta = (ClampMin = "1", ClampMax = "10000"))
	int32 MaxNetworkEvidenceLines = 2048;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Network")
	FMotionWorldNetworkControllerStats ControllerStats;

private:
	bool OpenTransport();
	void ClearControlState();
	void ApplyCommand(const MotionWorld::FNetworkCommandUpdate& Update);
	void DrawWorldModelVisualization() const;
	void DrawWorldModelHud() const;
	void RefreshRuntimeStats();
	void PollActions(double MonotonicNowSeconds);
	bool ReserveEvidenceLine();
	static bool IsSupportedControllerMode(const FString& Value);

	UPROPERTY(Transient)
	TObjectPtr<UMotionWorldBridgeComponent> BridgeComponent;

	MotionWorld::FMotionWorldUdpTransport Transport;
	MotionWorld::FNetworkRuntime Runtime;
	MotionWorld::FControlVisualizationState VisualizationState;
	double OutstandingObservationSentMonotonicSeconds = 0.0;
	double LastAcceptedEndToEndLatencyMs = -1.0;
	FString EvidenceSessionId;
};
