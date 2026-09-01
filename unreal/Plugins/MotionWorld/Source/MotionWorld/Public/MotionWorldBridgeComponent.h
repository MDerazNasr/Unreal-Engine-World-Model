#pragma once

#include "Components/ActorComponent.h"
#include "MoverSimulationTypes.h"
#include "MotionWorldArenaManager.h"
#include "MotionWorldEpisodeRecorder.h"
#include "MotionWorldReset.h"
#include "MotionWorldSmoothWalkingDiagnostic.h"
#include "MotionWorldStateSample.h"
#include "MotionWorldBridgeComponent.generated.h"

class UMoverComponent;

UENUM(BlueprintType)
enum class EMotionWorldVelocityCommandFrame : uint8
{
	CharacterLocal UMETA(DisplayName = "Character Local"),
	World UMETA(DisplayName = "World")
};

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

	/** Selects whether the active request is character-local or world-space. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Command")
	void SetVelocityCommandFrame(EMotionWorldVelocityCommandFrame NewFrame);

	/** Stores a planar velocity relative to character forward (+X) and right (+Y). */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Command")
	bool SetDesiredVelocityLocalCmPerSec(const FVector& RequestedVelocity);

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	bool IsAutomationEnabled() const { return bAutomationEnabled; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	FVector GetDesiredVelocityWorldCmPerSec() const { return DesiredVelocityWorldCmPerSec; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	FVector GetDesiredVelocityLocalCmPerSec() const { return DesiredVelocityLocalCmPerSec; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	EMotionWorldVelocityCommandFrame GetVelocityCommandFrame() const { return VelocityCommandFrame; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	FVector GetLastEchoedVelocityWorldCmPerSec() const { return LastEchoedVelocityWorldCmPerSec; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Command")
	bool DidLastCommandEchoMatch() const { return bLastCommandEchoMatched; }

	/** Latest immutable gameplay-state snapshot captured after Mover finalization. */
	UFUNCTION(BlueprintPure, Category = "MotionWorld|State")
	FMotionWorldStateSample GetLastAuthoritativeState() const { return LastAuthoritativeState; }

	/** Latest visual-only QA sample; never used by the recorder or model state. */
	UFUNCTION(BlueprintPure, Category = "MotionWorld|Animation Diagnostic")
	FMotionWorldAnimationDiagnosticSample GetLastAnimationDiagnostic() const
	{
		return LastAnimationDiagnostic;
	}

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Smooth Walking Diagnostic")
	FMotionWorldSmoothWalkingDiagnosticSample GetLastSmoothWalkingDiagnostic() const
	{
		return LastSmoothWalkingDiagnostic;
	}

	/** Clears prior rows and starts one explicitly identified in-memory episode. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Episode")
	bool StartEpisodeRecording(int64 EpisodeId);

	/** Stops accepting rows while retaining the current episode in memory. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Episode")
	void StopEpisodeRecording();

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Episode")
	FMotionWorldEpisodeRecorderStats GetEpisodeRecorderStats() const
	{
		return EpisodeRecorder.GetStats();
	}

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Episode")
	FMotionWorldTransitionSample GetLastRecordedTransition() const
	{
		return LastRecordedTransition;
	}

	/** Queues a Mover-owned character reset; the new episode starts only after verification. */
	UFUNCTION(BlueprintCallable, Category = "MotionWorld|Reset")
	bool RequestDeterministicResetAndStartEpisode(int64 EpisodeId);

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Reset")
	FMotionWorldResetTarget GetResetAnchor() const { return ResetAnchor; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Reset")
	FMotionWorldResetStatus GetResetStatus() const { return ResetStatus; }

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Arena")
	FMotionWorldArenaStatus GetArenaStatus() const
	{
		return ArenaManager
			? ArenaManager->GetArenaStatus()
			: FMotionWorldArenaStatus();
	}

	UFUNCTION(BlueprintPure, Category = "MotionWorld|Arena")
	FMotionWorldTimedGateState GetTimedGateState() const
	{
		return ArenaManager
			? ArenaManager->GetGateState()
			: FMotionWorldTimedGateState();
	}

protected:
	/** False by default so merely adding the component preserves human control. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Command")
	bool bAutomationEnabled = false;

	/** The final planner interface is character-local; World remains for engine diagnostics. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Command")
	EMotionWorldVelocityCommandFrame VelocityCommandFrame =
		EMotionWorldVelocityCommandFrame::CharacterLocal;

	/** Requested XY velocity: +X forward, +Y right, in centimetres per second. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Command")
	FVector DesiredVelocityLocalCmPerSec = FVector::ZeroVector;

	/** Diagnostic world-space request retained for direct Mover seam tests. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, AdvancedDisplay, Category = "MotionWorld|Command")
	FVector DesiredVelocityWorldCmPerSec = FVector::ZeroVector;

	/** Maximum allowed XY speed in centimetres per second. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Command", meta = (ClampMin = "0.0"))
	double MaxPlanarSpeedCmPerSec = 600.0;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Evidence")
	FVector LastEchoedVelocityWorldCmPerSec = FVector::ZeroVector;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Evidence")
	bool bLastCommandEchoMatched = false;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|State")
	FMotionWorldStateSample LastAuthoritativeState;

	/** Default-off visual QA logging; does not alter episode/model state. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Animation Diagnostic")
	bool bLogAnimationRootDiagnostics = false;

	/** Log every Nth aligned valid sample while animation diagnostics are enabled. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Animation Diagnostic", meta = (ClampMin = "1", ClampMax = "600"))
	int32 AnimationDiagnosticLogIntervalSamples = 1;

	/** Hard cap on logged rows per PIE session. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Animation Diagnostic", meta = (ClampMin = "1", ClampMax = "100000"))
	int32 MaxAnimationDiagnosticLogSamples = 4096;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Animation Diagnostic")
	FMotionWorldAnimationDiagnosticSample LastAnimationDiagnostic;

	/** Default-off research logging; does not alter authoritative state or episodes. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	bool bLogSmoothWalkingDiagnostics = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic", meta = (ClampMin = "1", ClampMax = "600"))
	int32 SmoothWalkingDiagnosticLogIntervalSamples = 60;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic", meta = (ClampMin = "1", ClampMax = "10000"))
	int32 MaxSmoothWalkingDiagnosticLogSamples = 512;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Smooth Walking Diagnostic")
	FMotionWorldSmoothWalkingDiagnosticSample LastSmoothWalkingDiagnostic;

	/** Log every N valid finalized samples after the first; zero disables periodic logs. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|State", meta = (ClampMin = "0"))
	int32 StateDiagnosticLogIntervalSamples = 60;

	/** Hard per-episode bound; overflow stops recording and never overwrites earlier rows. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode", meta = (ClampMin = "1", ClampMax = "100000"))
	int32 MaxRecordedTransitions = 4096;

	/** Opt-in convenience for a self-contained PIE recording trial. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	bool bStartEpisodeRecordingOnBeginPlay = false;

	/** Opt-in durable export under Saved/MotionWorld/Episodes when an episode stops. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode")
	bool bExportEpisodeOnStop = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode", meta = (ClampMin = "0"))
	int64 BeginPlayEpisodeId = 0;

	/** Log every N accepted transitions after the first; zero disables periodic logs. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Episode", meta = (ClampMin = "0"))
	int32 TransitionDiagnosticLogIntervalSamples = 60;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Episode")
	FMotionWorldTransitionSample LastRecordedTransition;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Episode")
	EMotionWorldRecorderObservationResult LastRecorderObservationResult =
		EMotionWorldRecorderObservationResult::IgnoredNotRecording;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Episode")
	bool bLastEpisodeExportSucceeded = false;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Episode")
	FString LastEpisodeExportPath;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Episode")
	FString LastEpisodeExportResult;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Episode")
	int64 LastEpisodeExportTransitionCount = 0;

	/** Capture the first valid ordinary finalized state as the fixed character reset pose. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	bool bCaptureResetAnchorFromFirstValidState = true;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset")
	FMotionWorldResetTolerances ResetTolerances;

	/** Fail explicitly after this many newer finalized states do not match the reset target. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset", meta = (ClampMin = "1", ClampMax = "60"))
	int32 ResetMaxVerificationSamples = 3;

	/** Default-off proof: move away, then perform repeated verified resets in one PIE session. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset|Live Test")
	bool bRequestResetAfterWarmupOnBeginPlay = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset|Live Test", meta = (ClampMin = "2", ClampMax = "10000"))
	int32 ResetWarmupFinalizedSamples = 60;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset|Live Test", meta = (ClampMin = "0"))
	int64 BeginPlayResetEpisodeId = 1701;

	/** Number of same-session resets; episode IDs increment from BeginPlayResetEpisodeId. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset|Live Test", meta = (ClampMin = "1", ClampMax = "10"))
	int32 ResetLiveTestRepeatCount = 2;

	/** Accepted transitions before the next proof reset is requested. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Reset|Live Test", meta = (ClampMin = "1", ClampMax = "10000"))
	int32 ResetLiveTestTransitionsPerEpisode = 60;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Reset")
	FMotionWorldResetTarget ResetAnchor;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "MotionWorld|Reset")
	FMotionWorldResetStatus ResetStatus;

	/** Default-off deterministic arena; initialized relative to the captured reset anchor. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	bool bEnableTimedGateScenario = false;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena", meta = (ClampMin = "0"))
	int64 TimedGateScenarioSeed = 1901;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena", meta = (ClampMin = "100.0"))
	double TimedGateForwardDistanceCm = 600.0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena", meta = (ClampMin = "0.0"))
	double TimedGateAmplitudeCm = 200.0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena", meta = (ClampMin = "0.1"))
	double TimedGatePeriodSeconds = 4.0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	double TimedGatePhaseOffsetRadians = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena")
	FVector TimedGateHalfExtentsCm = FVector(30.0, 150.0, 90.0);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "MotionWorld|Arena", meta = (ClampMin = "0.1"))
	double TimedGateTimeoutSeconds = 8.0;

private:
	void ExportCurrentEpisode(const FMotionWorldEpisodeRecorderStats& CompletedStats);

	UFUNCTION()
	void HandlePostFinalize(
		const FMoverSyncState& SyncState,
		const FMoverAuxStateContext& AuxState);

	void RestorePreResetCommand();
	void FailPendingReset(const TCHAR* FailureContext);
	void ProcessPendingResetVerification();
	void CaptureResetAnchorIfEligible();
	void RequestConfiguredWarmupResetIfDue();
	void InitializeTimedArenaIfEligible();
	void ProcessTimedArenaObservation();
	void CaptureAnimationDiagnosticIfEnabled();
	void CaptureSmoothWalkingDiagnosticIfEnabled(const FMoverSyncState& SyncState);
	void ApplyArenaTerminalSafeStop(
		EMotionWorldScenarioTerminationReason TerminationReason);

	UPROPERTY(Transient)
	TObjectPtr<UMoverComponent> MoverComponent;

	UPROPERTY(Transient)
	TObjectPtr<AMotionWorldArenaManager> ArenaManager;

	FVector LastSubmittedVelocityWorldCmPerSec = FVector::ZeroVector;
	FVector LastRequestedVelocityInCommandFrameCmPerSec = FVector::ZeroVector;
	double LastResolvedFacingYawDegrees = 0.0;
	uint64 CommandRevision = 0;
	uint64 LastLoggedRevision = MAX_uint64;
	int64 NextStateSampleSequence = 0;
	bool bLastSubmittedInputWasFinite = true;
	bool bLastCommandFrameResolved = true;
	bool bHasAuthoritativeStateSample = false;
	bool bPreviousAuthoritativeStateWasValid = false;
	MotionWorld::FInMemoryEpisodeRecorder EpisodeRecorder;
	EMotionWorldTransitionRejectionReason LastLoggedRecorderRejectionReason =
		EMotionWorldTransitionRejectionReason::None;
	bool bHasLoggedRecorderRejection = false;
	EMotionWorldVelocityCommandFrame PreResetCommandFrame =
		EMotionWorldVelocityCommandFrame::CharacterLocal;
	FVector PreResetDesiredVelocityLocalCmPerSec = FVector::ZeroVector;
	FVector PreResetDesiredVelocityWorldCmPerSec = FVector::ZeroVector;
	int64 ValidFinalizedStateCount = 0;
	bool bHasSavedPreResetCommand = false;
	int32 ConfiguredResetRequestsIssued = 0;
	bool bConfiguredResetSequenceAborted = false;
	bool bDeferCommandEchoUntilNextProduction = false;
	bool bArenaInitializationAttempted = false;
	bool bArenaTerminalSafeStopIssued = false;
	bool bCurrentEpisodeHasTimedGateScenario = false;
	double CurrentEpisodeScenarioStartSimulationTimeSeconds = 0.0;
	FString AnimationDiagnosticSessionId;
	int64 ValidAnimationDiagnosticSampleCount = 0;
	int64 InvalidAnimationDiagnosticSampleCount = 0;
	int64 LoggedAnimationDiagnosticSampleCount = 0;
	bool bHasLoggedAnimationDiagnosticFailure = false;
	bool bHasLoggedAnimationDiagnosticCapacity = false;
	FString SmoothWalkingDiagnosticSessionId;
	int64 ValidSmoothWalkingDiagnosticSampleCount = 0;
	int64 InvalidSmoothWalkingDiagnosticSampleCount = 0;
	int64 LoggedSmoothWalkingDiagnosticSampleCount = 0;
	bool bHasLoggedSmoothWalkingDiagnosticFailure = false;
	bool bHasLoggedSmoothWalkingDiagnosticCapacity = false;
};
