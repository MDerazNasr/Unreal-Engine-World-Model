#include "MotionWorldBridgeComponent.h"

#include "DefaultMovementSet/InstantMovementEffects/BasicInstantMovementEffects.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/App.h"
#include "Misc/DateTime.h"
#include "Misc/EngineVersion.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "MoverComponent.h"
#include "MoverDataModelTypes.h"
#include "MoverTypes.h"
#include "MotionWorldArenaManager.h"
#include "MotionWorldCoordinateFrames.h"
#include "MotionWorldEpisodeExporter.h"
#include "MotionWorldStateSample.h"
#include "MotionWorldVelocityCommand.h"

DEFINE_LOG_CATEGORY_STATIC(LogMotionWorldBridge, Log, All);

UMotionWorldBridgeComponent::UMotionWorldBridgeComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

void UMotionWorldBridgeComponent::BeginPlay()
{
	Super::BeginPlay();

	MoverComponent = GetOwner() ? GetOwner()->FindComponentByClass<UMoverComponent>() : nullptr;
	if (!MoverComponent)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld bridge on '%s' requires a UMoverComponent."),
			*GetNameSafe(GetOwner()));
		return;
	}

	MoverComponent->OnPostFinalize.AddDynamic(
		this,
		&UMotionWorldBridgeComponent::HandlePostFinalize);

	UE_LOG(
		LogMotionWorldBridge,
		Display,
		TEXT("MotionWorld bridge ready on '%s'; automation=%s, max_planar_speed=%.2f cm/s, state_log_interval=%d samples, episode_capacity=%d transitions."),
		*GetNameSafe(GetOwner()),
		bAutomationEnabled ? TEXT("enabled") : TEXT("disabled"),
		MaxPlanarSpeedCmPerSec,
		StateDiagnosticLogIntervalSamples,
		MaxRecordedTransitions);

	if (bStartEpisodeRecordingOnBeginPlay && bRequestResetAfterWarmupOnBeginPlay)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld BeginPlay configuration on '%s' requested both immediate recording and warmup reset; immediate recording is suppressed to prevent a cross-reset episode."),
			*GetNameSafe(GetOwner()));
	}
	else if (bStartEpisodeRecordingOnBeginPlay)
	{
		StartEpisodeRecording(BeginPlayEpisodeId);
	}
}

void UMotionWorldBridgeComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (ResetStatus.bIsPending)
	{
		FailPendingReset(TEXT("component ended before verification"));
	}

	if (EpisodeRecorder.GetStats().bIsRecording)
	{
		StopEpisodeRecording();
	}

	if (MoverComponent)
	{
		MoverComponent->OnPostFinalize.RemoveDynamic(
			this,
			&UMotionWorldBridgeComponent::HandlePostFinalize);
	}
	if (IsValid(ArenaManager))
	{
		ArenaManager->Destroy();
		ArenaManager = nullptr;
	}

	Super::EndPlay(EndPlayReason);
}

void UMotionWorldBridgeComponent::SetAutomationEnabled(const bool bEnabled)
{
	if (ResetStatus.bIsPending && !bEnabled)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Warning,
			TEXT("Ignored request to disable MotionWorld automation while reset episode %lld is pending."),
			ResetStatus.RequestedEpisodeId);
		return;
	}

	if (bAutomationEnabled != bEnabled)
	{
		bAutomationEnabled = bEnabled;
		bLastCommandEchoMatched = false;
		LastEchoedVelocityWorldCmPerSec = FVector::ZeroVector;
		++CommandRevision;
	}
}

bool UMotionWorldBridgeComponent::SetDesiredVelocityWorldCmPerSec(
	const FVector& RequestedVelocity)
{
	if (ResetStatus.bIsPending)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Warning,
			TEXT("Ignored world-velocity change while MotionWorld reset episode %lld is pending."),
			ResetStatus.RequestedEpisodeId);
		return false;
	}

	if (RequestedVelocity.ContainsNaN())
	{
		UE_LOG(
			LogMotionWorldBridge,
			Warning,
			TEXT("Rejected non-finite MotionWorld velocity command on '%s'."),
			*GetNameSafe(GetOwner()));
		return false;
	}

	DesiredVelocityWorldCmPerSec = RequestedVelocity;
	VelocityCommandFrame = EMotionWorldVelocityCommandFrame::World;
	++CommandRevision;
	return true;
}

void UMotionWorldBridgeComponent::SetVelocityCommandFrame(
	const EMotionWorldVelocityCommandFrame NewFrame)
{
	if (ResetStatus.bIsPending)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Warning,
			TEXT("Ignored command-frame change while MotionWorld reset episode %lld is pending."),
			ResetStatus.RequestedEpisodeId);
		return;
	}

	if (VelocityCommandFrame != NewFrame)
	{
		VelocityCommandFrame = NewFrame;
		++CommandRevision;
	}
}

bool UMotionWorldBridgeComponent::SetDesiredVelocityLocalCmPerSec(
	const FVector& RequestedVelocity)
{
	if (ResetStatus.bIsPending)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Warning,
			TEXT("Ignored local-velocity change while MotionWorld reset episode %lld is pending."),
			ResetStatus.RequestedEpisodeId);
		return false;
	}

	if (RequestedVelocity.ContainsNaN())
	{
		UE_LOG(
			LogMotionWorldBridge,
			Warning,
			TEXT("Rejected non-finite MotionWorld local velocity command on '%s'."),
			*GetNameSafe(GetOwner()));
		return false;
	}

	DesiredVelocityLocalCmPerSec = RequestedVelocity;
	VelocityCommandFrame = EMotionWorldVelocityCommandFrame::CharacterLocal;
	++CommandRevision;
	return true;
}

bool UMotionWorldBridgeComponent::StartEpisodeRecording(const int64 EpisodeId)
{
	if (!ensureMsgf(IsInGameThread(), TEXT("MotionWorld episode recording is game-thread owned."))
		|| !MoverComponent)
	{
		return false;
	}
	if (ResetStatus.bIsPending)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld episode %lld cannot start while reset episode %lld is unverified."),
			EpisodeId,
			ResetStatus.RequestedEpisodeId);
		return false;
	}

	const bool bStarted = EpisodeRecorder.StartEpisode(EpisodeId, MaxRecordedTransitions);
	LastRecordedTransition = FMotionWorldTransitionSample();
	LastRecorderObservationResult =
		EMotionWorldRecorderObservationResult::IgnoredNotRecording;
	LastLoggedRecorderRejectionReason =
		EMotionWorldTransitionRejectionReason::None;
	bHasLoggedRecorderRejection = false;

	if (bStarted)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Display,
			TEXT("MotionWorld episode started: episode=%lld capacity=%d; awaiting seed state."),
			EpisodeId,
			MaxRecordedTransitions);
	}
	else
	{
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld episode start rejected: episode=%lld capacity=%d."),
			EpisodeId,
			MaxRecordedTransitions);
	}

	return bStarted;
}

void UMotionWorldBridgeComponent::StopEpisodeRecording()
{
	if (!ensureMsgf(IsInGameThread(), TEXT("MotionWorld episode recording is game-thread owned.")))
	{
		return;
	}

	const FMotionWorldEpisodeRecorderStats BeforeStop = EpisodeRecorder.GetStats();
	EpisodeRecorder.StopEpisode();
	UE_LOG(
		LogMotionWorldBridge,
		Display,
		TEXT("MotionWorld episode stopped: episode=%lld observed=%lld attempted=%lld recorded=%lld rejected=%lld rejected_seeds=%lld capacity_drops=%lld."),
		BeforeStop.EpisodeId,
		BeforeStop.ObservedStateCount,
		BeforeStop.AttemptedTransitionCount,
		BeforeStop.RecordedTransitionCount,
		BeforeStop.RejectedTransitionCount,
		BeforeStop.RejectedSeedStateCount,
		BeforeStop.CapacityDropCount);

	if (bExportEpisodeOnStop && BeforeStop.bIsRecording)
	{
		ExportCurrentEpisode(BeforeStop);
	}
}

void UMotionWorldBridgeComponent::ExportCurrentEpisode(
	const FMotionWorldEpisodeRecorderStats& CompletedStats)
{
	const FDateTime CreatedUtc = FDateTime::UtcNow();
	const FString UniqueSuffix = FGuid::NewGuid().ToString(EGuidFormats::Digits).Left(12);
	const FString FileName = FString::Printf(
		TEXT("episode_%lld_%s_%s.jsonl"),
		CompletedStats.EpisodeId,
		*CreatedUtc.ToString(TEXT("%Y%m%dT%H%M%SZ")),
		*UniqueSuffix);
	const FString OutputPath = FPaths::Combine(
		FPaths::ProjectSavedDir(),
		TEXT("MotionWorld"),
		TEXT("Episodes"),
		FileName);

	MotionWorld::FEpisodeExportRequest Request;
	Request.OutputFilePath = OutputPath;
	Request.CreatedUtcIso8601 = CreatedUtc.ToIso8601();
	Request.EngineVersion = FEngineVersion::Current().ToString();
	Request.ProjectName = FApp::GetProjectName();
	Request.Stats = CompletedStats;
	Request.Transitions = EpisodeRecorder.GetTransitions();

	const double ExportStartSeconds = FPlatformTime::Seconds();
	const MotionWorld::FEpisodeExportOutcome Outcome =
		MotionWorld::ExportEpisodeJsonLines(Request);
	const double ExportDurationMilliseconds =
		(FPlatformTime::Seconds() - ExportStartSeconds) * 1000.0;

	bLastEpisodeExportSucceeded = Outcome.Succeeded();
	LastEpisodeExportPath = Outcome.OutputFilePath;
	LastEpisodeExportResult = MotionWorld::LexToString(Outcome.Result);
	LastEpisodeExportTransitionCount = Outcome.ExportedTransitionCount;

	if (Outcome.Succeeded())
	{
		UE_LOG(
			LogMotionWorldBridge,
			Display,
			TEXT("MotionWorld episode exported: episode=%lld transitions=%lld schema_version=%d duration_ms=%.3f path='%s'."),
			CompletedStats.EpisodeId,
			Outcome.ExportedTransitionCount,
			MotionWorld::EpisodeFileSchemaVersion,
			ExportDurationMilliseconds,
			*Outcome.OutputFilePath);
	}
	else
	{
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld episode export failed: episode=%lld result=%s detail='%s' duration_ms=%.3f path='%s'."),
			CompletedStats.EpisodeId,
			MotionWorld::LexToString(Outcome.Result),
			*Outcome.Detail,
			ExportDurationMilliseconds,
			*Outcome.OutputFilePath);
	}
}

bool UMotionWorldBridgeComponent::RequestDeterministicResetAndStartEpisode(
	const int64 EpisodeId)
{
	if (!ensureMsgf(IsInGameThread(), TEXT("MotionWorld reset is game-thread owned."))
		|| !MoverComponent)
	{
		return false;
	}
	if (EpisodeId < 0
		|| !ResetAnchor.bIsValid
		|| ResetAnchor.MovementMode.IsNone()
		|| !MoverComponent->FindMovementModeByName(ResetAnchor.MovementMode)
		|| !bAutomationEnabled
		|| ResetStatus.bIsPending)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld reset request rejected: episode=%lld anchor_valid=%s mode=%s mode_registered=%s automation=%s pending=%s."),
			EpisodeId,
			ResetAnchor.bIsValid ? TEXT("true") : TEXT("false"),
			*ResetAnchor.MovementMode.ToString(),
			MoverComponent->FindMovementModeByName(ResetAnchor.MovementMode)
				? TEXT("true")
				: TEXT("false"),
			bAutomationEnabled ? TEXT("true") : TEXT("false"),
			ResetStatus.bIsPending ? TEXT("true") : TEXT("false"));
		return false;
	}

	if (EpisodeRecorder.GetStats().bIsRecording)
	{
		StopEpisodeRecording();
	}

	PreResetCommandFrame = VelocityCommandFrame;
	PreResetDesiredVelocityLocalCmPerSec = DesiredVelocityLocalCmPerSec;
	PreResetDesiredVelocityWorldCmPerSec = DesiredVelocityWorldCmPerSec;
	bHasSavedPreResetCommand = true;

	if (VelocityCommandFrame == EMotionWorldVelocityCommandFrame::CharacterLocal)
	{
		DesiredVelocityLocalCmPerSec = FVector::ZeroVector;
	}
	else
	{
		DesiredVelocityWorldCmPerSec = FVector::ZeroVector;
	}
	++CommandRevision;
	bLastCommandEchoMatched = false;
	LastEchoedVelocityWorldCmPerSec = FVector::ZeroVector;

	ResetStatus.RequestedEpisodeId = EpisodeId;
	++ResetStatus.RequestCount;
	ResetStatus.bLastResetSucceeded = false;
	ResetStatus.VerificationAttemptCount = 0;
	ResetStatus.RequestStateSequence = LastAuthoritativeState.SampleSequence;
	ResetStatus.RequestMoverStepServerFrame =
		LastAuthoritativeState.MoverStepServerFrame;
	ResetStatus.LastCheck = FMotionWorldResetCheck();

	// Smooth Walking resets all spring/intermediate quantities when this marker is stale.
	constexpr TCHAR SmoothWalkingGeneratedMoveEntry[] = TEXT("DidGenerateMove");
	if (!MoverComponent->GetRollbackBlackboardExternal().TrySet<bool>(
		SmoothWalkingGeneratedMoveEntry,
		false))
	{
		++ResetStatus.FailureCount;
		RestorePreResetCommand();
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld reset episode %lld rejected because Smooth Walking history could not be marked stale."),
			EpisodeId);
		return false;
	}

	TSharedPtr<FTeleportEffect> TeleportEffect = MakeShared<FTeleportEffect>();
	TeleportEffect->TargetLocation = ResetAnchor.PositionWorldCm;
	TeleportEffect->bUseActorRotation = false;
	TeleportEffect->TargetRotation = ResetAnchor.OrientationWorldDegrees;
	MoverComponent->QueueInstantMovementEffect(TeleportEffect);

	TSharedPtr<FApplyVelocityEffect> VelocityEffect =
		MakeShared<FApplyVelocityEffect>();
	VelocityEffect->VelocityToApply = FVector::ZeroVector;
	VelocityEffect->bAdditiveVelocity = false;
	VelocityEffect->ForceMovementMode = ResetAnchor.MovementMode;
	MoverComponent->QueueInstantMovementEffect(VelocityEffect);

	ResetStatus.bIsPending = true;
	const double DistanceFromAnchorCm = LastAuthoritativeState.bIsValid
		? FVector::Distance(
			LastAuthoritativeState.PositionWorldCm,
			ResetAnchor.PositionWorldCm)
		: -1.0;
	UE_LOG(
		LogMotionWorldBridge,
		Display,
		TEXT("MotionWorld reset queued: episode=%lld request_state_sequence=%lld request_mover_frame=%d before_position_world_cm=(%.2f, %.2f, %.2f) distance_from_anchor_cm=%.3f target_position_world_cm=(%.2f, %.2f, %.2f) target_yaw_deg=%.2f target_mode=%s; recorder stopped and reset frame forced to zero input."),
		EpisodeId,
		ResetStatus.RequestStateSequence,
		ResetStatus.RequestMoverStepServerFrame,
		LastAuthoritativeState.PositionWorldCm.X,
		LastAuthoritativeState.PositionWorldCm.Y,
		LastAuthoritativeState.PositionWorldCm.Z,
		DistanceFromAnchorCm,
		ResetAnchor.PositionWorldCm.X,
		ResetAnchor.PositionWorldCm.Y,
		ResetAnchor.PositionWorldCm.Z,
		ResetAnchor.OrientationWorldDegrees.Yaw,
		*ResetAnchor.MovementMode.ToString());
	return true;
}

void UMotionWorldBridgeComponent::RestorePreResetCommand()
{
	if (!bHasSavedPreResetCommand)
	{
		return;
	}

	VelocityCommandFrame = PreResetCommandFrame;
	DesiredVelocityLocalCmPerSec = PreResetDesiredVelocityLocalCmPerSec;
	DesiredVelocityWorldCmPerSec = PreResetDesiredVelocityWorldCmPerSec;
	bHasSavedPreResetCommand = false;
	++CommandRevision;
	bLastCommandEchoMatched = false;
	LastEchoedVelocityWorldCmPerSec = FVector::ZeroVector;
	bDeferCommandEchoUntilNextProduction = true;
}

void UMotionWorldBridgeComponent::FailPendingReset(const TCHAR* FailureContext)
{
	if (!ResetStatus.bIsPending)
	{
		return;
	}

	ResetStatus.bIsPending = false;
	ResetStatus.bLastResetSucceeded = false;
	++ResetStatus.FailureCount;
	RestorePreResetCommand();
	UE_LOG(
		LogMotionWorldBridge,
		Error,
		TEXT("MotionWorld reset failed: episode=%lld attempts=%d result=%d context=%s position_error_cm=%.3f facing_error_deg=%.3f linear_speed_cm_per_sec=%.3f angular_speed_deg_per_sec=%.3f; recording remains stopped."),
		ResetStatus.RequestedEpisodeId,
		ResetStatus.VerificationAttemptCount,
		static_cast<int32>(ResetStatus.LastCheck.Result),
		FailureContext,
		ResetStatus.LastCheck.PositionErrorCm,
		ResetStatus.LastCheck.FacingErrorDegrees,
		ResetStatus.LastCheck.LinearSpeedCmPerSec,
		ResetStatus.LastCheck.AngularSpeedDegPerSec);
}

void UMotionWorldBridgeComponent::ProcessPendingResetVerification()
{
	if (!ResetStatus.bIsPending
		|| LastAuthoritativeState.SampleSequence <= ResetStatus.RequestStateSequence)
	{
		return;
	}

	++ResetStatus.VerificationAttemptCount;
	ResetStatus.LastCheck = MotionWorld::CheckFinalizedResetState(
		ResetAnchor,
		LastAuthoritativeState,
		ResetTolerances);
	if (ResetStatus.LastCheck.Passed())
	{
		const int64 EpisodeId = ResetStatus.RequestedEpisodeId;
		ResetStatus.bIsPending = false;
		ResetStatus.bLastResetSucceeded = true;
		++ResetStatus.SuccessCount;
		RestorePreResetCommand();

		if (bEnableTimedGateScenario)
		{
			const UWorld* World = GetWorld();
			if (!IsValid(ArenaManager)
				|| !World
				|| !ArenaManager->ResetArena(
					static_cast<double>(World->GetTimeSeconds())))
			{
				ResetStatus.bLastResetSucceeded = false;
				--ResetStatus.SuccessCount;
				++ResetStatus.FailureCount;
				UE_LOG(
					LogMotionWorldBridge,
					Error,
					TEXT("MotionWorld character reset passed but timed arena reset failed for episode %lld; recording remains stopped."),
					EpisodeId);
				return;
			}
		}

		if (!StartEpisodeRecording(EpisodeId))
		{
			ResetStatus.bLastResetSucceeded = false;
			--ResetStatus.SuccessCount;
			++ResetStatus.FailureCount;
			UE_LOG(
				LogMotionWorldBridge,
				Error,
				TEXT("MotionWorld reset state passed but episode %lld could not start; recording remains stopped."),
				EpisodeId);
			return;
		}

		UE_LOG(
			LogMotionWorldBridge,
			Display,
			TEXT("MotionWorld reset verified: episode=%lld attempts=%d state_sequence=%lld mover_frame=%d position_world_cm=(%.2f, %.2f, %.2f) yaw_deg=%.2f mode=%s position_error_cm=%.3f facing_error_deg=%.3f linear_speed_cm_per_sec=%.3f angular_speed_deg_per_sec=%.3f; new episode may seed this state."),
			EpisodeId,
			ResetStatus.VerificationAttemptCount,
			LastAuthoritativeState.SampleSequence,
			LastAuthoritativeState.MoverStepServerFrame,
			LastAuthoritativeState.PositionWorldCm.X,
			LastAuthoritativeState.PositionWorldCm.Y,
			LastAuthoritativeState.PositionWorldCm.Z,
			LastAuthoritativeState.FacingYawDegrees,
			*LastAuthoritativeState.MovementMode.ToString(),
			ResetStatus.LastCheck.PositionErrorCm,
			ResetStatus.LastCheck.FacingErrorDegrees,
			ResetStatus.LastCheck.LinearSpeedCmPerSec,
			ResetStatus.LastCheck.AngularSpeedDegPerSec);
		return;
	}

	if (ResetStatus.VerificationAttemptCount
		>= FMath::Max(1, ResetMaxVerificationSamples))
	{
		FailPendingReset(TEXT("finalized state did not meet reset tolerances"));
	}
}

void UMotionWorldBridgeComponent::CaptureResetAnchorIfEligible()
{
	if (!bCaptureResetAnchorFromFirstValidState
		|| ResetAnchor.bIsValid
		|| !LastAuthoritativeState.bIsValid
		|| LastAuthoritativeState.bIsResimulation)
	{
		return;
	}

	ResetAnchor = MotionWorld::BuildResetTarget(LastAuthoritativeState);
	ResetStatus.bHasAnchor = ResetAnchor.bIsValid;
	if (ResetAnchor.bIsValid)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Display,
			TEXT("MotionWorld reset anchor captured: source_state_sequence=%lld position_world_cm=(%.2f, %.2f, %.2f) yaw_deg=%.2f mode=%s."),
			ResetAnchor.SourceStateSequence,
			ResetAnchor.PositionWorldCm.X,
			ResetAnchor.PositionWorldCm.Y,
			ResetAnchor.PositionWorldCm.Z,
			ResetAnchor.OrientationWorldDegrees.Yaw,
			*ResetAnchor.MovementMode.ToString());
		InitializeTimedArenaIfEligible();
	}
}

void UMotionWorldBridgeComponent::InitializeTimedArenaIfEligible()
{
	if (!bEnableTimedGateScenario
		|| bArenaInitializationAttempted
		|| !ResetAnchor.bIsValid)
	{
		return;
	}
	bArenaInitializationAttempted = true;

	UWorld* World = GetWorld();
	AActor* Owner = GetOwner();
	if (!World || !Owner)
	{
		UE_LOG(LogMotionWorldBridge, Error, TEXT("MotionWorld timed arena initialization requires a world and owner."));
		return;
	}

	FVector ForwardWorld = ResetAnchor.OrientationWorldDegrees.Vector();
	ForwardWorld.Z = 0.0;
	ForwardWorld = ForwardWorld.GetSafeNormal();
	const FVector RightWorld = FVector::CrossProduct(FVector::UpVector, ForwardWorld).GetSafeNormal();

	FMotionWorldTimedGateConfig Config;
	Config.ScenarioSeed = TimedGateScenarioSeed;
	Config.OriginWorldCm = ResetAnchor.PositionWorldCm
		+ ForwardWorld * TimedGateForwardDistanceCm;
	Config.MotionAxisWorld = RightWorld;
	Config.AmplitudeCm = TimedGateAmplitudeCm;
	Config.PeriodSeconds = TimedGatePeriodSeconds;
	Config.PhaseOffsetRadians = TimedGatePhaseOffsetRadians;
	Config.HalfExtentsCm = TimedGateHalfExtentsCm;
	Config.CrossingPlaneNormalWorld = ForwardWorld;
	Config.TimeoutSeconds = TimedGateTimeoutSeconds;

	FActorSpawnParameters SpawnParameters;
	SpawnParameters.Owner = Owner;
	SpawnParameters.SpawnCollisionHandlingOverride =
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ArenaManager = World->SpawnActor<AMotionWorldArenaManager>(
		AMotionWorldArenaManager::StaticClass(),
		Config.OriginWorldCm,
		FRotator::ZeroRotator,
		SpawnParameters);
	if (!IsValid(ArenaManager)
		|| !ArenaManager->InitializeArena(
			Owner,
			Config,
			static_cast<double>(World->GetTimeSeconds())))
	{
		UE_LOG(LogMotionWorldBridge, Error, TEXT("MotionWorld timed arena initialization failed; scenario recording is unavailable."));
		if (IsValid(ArenaManager))
		{
			ArenaManager->Destroy();
			ArenaManager = nullptr;
		}
		return;
	}

	UE_LOG(
		LogMotionWorldBridge,
		Display,
		TEXT("MotionWorld timed arena initialized: seed=%lld gate_origin_world_cm=(%.2f, %.2f, %.2f) forward_distance_cm=%.2f."),
		Config.ScenarioSeed,
		Config.OriginWorldCm.X,
		Config.OriginWorldCm.Y,
		Config.OriginWorldCm.Z,
		TimedGateForwardDistanceCm);
}

void UMotionWorldBridgeComponent::ProcessTimedArenaObservation()
{
	if (!bEnableTimedGateScenario
		|| !IsValid(ArenaManager)
		|| !LastAuthoritativeState.bIsValid
		|| LastAuthoritativeState.bIsResimulation)
	{
		return;
	}

	const FMotionWorldScenarioStepResult Result =
		ArenaManager->ObserveFinalizedAgentPosition(
			LastAuthoritativeState.PositionWorldCm);
	if (Result.TerminationReason != EMotionWorldScenarioTerminationReason::None
		&& EpisodeRecorder.GetStats().bIsRecording)
	{
		StopEpisodeRecording();
	}
}

void UMotionWorldBridgeComponent::RequestConfiguredWarmupResetIfDue()
{
	if (!bRequestResetAfterWarmupOnBeginPlay
		|| bConfiguredResetSequenceAborted
		|| ResetStatus.bIsPending
		|| ConfiguredResetRequestsIssued
			>= FMath::Clamp(ResetLiveTestRepeatCount, 1, 10))
	{
		return;
	}

	bool bResetIsDue = false;
	if (ConfiguredResetRequestsIssued == 0)
	{
		bResetIsDue = ValidFinalizedStateCount
			>= FMath::Max<int64>(2, ResetWarmupFinalizedSamples);
	}
	else
	{
		const FMotionWorldEpisodeRecorderStats RecorderStats =
			EpisodeRecorder.GetStats();
		const int64 ExpectedEpisodeId = BeginPlayResetEpisodeId
			+ static_cast<int64>(ConfiguredResetRequestsIssued - 1);
		if (RecorderStats.bIsRecording
			&& RecorderStats.EpisodeId != ExpectedEpisodeId)
		{
			bConfiguredResetSequenceAborted = true;
			UE_LOG(
				LogMotionWorldBridge,
				Error,
				TEXT("MotionWorld configured reset sequence aborted: expected active episode %lld but found %lld."),
				ExpectedEpisodeId,
				RecorderStats.EpisodeId);
			return;
		}
		bResetIsDue = RecorderStats.bIsRecording
			&& RecorderStats.RecordedTransitionCount
				>= FMath::Max<int64>(1, ResetLiveTestTransitionsPerEpisode);
	}

	if (!bResetIsDue
		|| BeginPlayResetEpisodeId
			> MAX_int64 - static_cast<int64>(ConfiguredResetRequestsIssued))
	{
		if (bResetIsDue)
		{
			bConfiguredResetSequenceAborted = true;
			UE_LOG(
				LogMotionWorldBridge,
				Error,
				TEXT("MotionWorld configured reset sequence aborted because its episode ID would overflow."));
		}
		return;
	}

	const int64 EpisodeId = BeginPlayResetEpisodeId
		+ static_cast<int64>(ConfiguredResetRequestsIssued);
	if (RequestDeterministicResetAndStartEpisode(EpisodeId))
	{
		++ConfiguredResetRequestsIssued;
	}
	else
	{
		bConfiguredResetSequenceAborted = true;
	}
}

void UMotionWorldBridgeComponent::ProduceInput_Implementation(
	const int32 SimTimeMs,
	FMoverInputCmdContext& InputCmdResult)
{
	if (!ensureMsgf(
		IsInGameThread(),
		TEXT("MotionWorld command production currently requires Mover's game-thread input mode.")))
	{
		return;
	}

	if (!bAutomationEnabled)
	{
		return;
	}

	FVector RequestedVelocityWorldCmPerSec = DesiredVelocityWorldCmPerSec;
	LastRequestedVelocityInCommandFrameCmPerSec = DesiredVelocityWorldCmPerSec;
	LastResolvedFacingYawDegrees = 0.0;
	bLastCommandFrameResolved = true;

	if (VelocityCommandFrame == EMotionWorldVelocityCommandFrame::CharacterLocal)
	{
		LastRequestedVelocityInCommandFrameCmPerSec = DesiredVelocityLocalCmPerSec;
		const FMoverDefaultSyncState* CurrentState = MoverComponent
			? MoverComponent->GetSyncState().SyncStateCollection
				.FindDataByType<FMoverDefaultSyncState>()
			: nullptr;

		if (CurrentState)
		{
			LastResolvedFacingYawDegrees =
				CurrentState->GetOrientation_WorldSpace().Yaw;
			RequestedVelocityWorldCmPerSec =
				MotionWorld::CharacterLocalToWorldPlanarVelocity(
					DesiredVelocityLocalCmPerSec,
					LastResolvedFacingYawDegrees);
		}
		else
		{
			RequestedVelocityWorldCmPerSec = FVector::ZeroVector;
			bLastCommandFrameResolved = false;
		}
	}

	const MotionWorld::FSanitizedVelocityCommand Sanitized =
		MotionWorld::SanitizeWorldVelocityCommand(
			RequestedVelocityWorldCmPerSec,
			MaxPlanarSpeedCmPerSec);

	FCharacterDefaultInputs& Inputs =
		InputCmdResult.InputCollection.FindOrAddMutableDataByType<FCharacterDefaultInputs>();

	// Preserve the existing facing intent before changing the movement-base frame.
	const FVector ExistingOrientationIntentWorld = Inputs.GetOrientationIntentDir_WorldSpace();
	Inputs.bUsingMovementBase = false;
	Inputs.MovementBase = nullptr;
	Inputs.MovementBaseBoneName = NAME_None;
	Inputs.OrientationIntent = ResetStatus.bIsPending
		? ResetAnchor.OrientationWorldDegrees.Vector()
		: ExistingOrientationIntentWorld;
	Inputs.SetMoveInput(EMoveInputType::Velocity, Sanitized.WorldVelocityCmPerSec);

	// Read back the value stored by SetMoveInput because Mover quantizes it to 0.01 cm/s.
	LastSubmittedVelocityWorldCmPerSec = Inputs.GetMoveInput();
	bLastSubmittedInputWasFinite =
		Sanitized.bInputWasFinite && bLastCommandFrameResolved;
	bDeferCommandEchoUntilNextProduction = false;

	(void)SimTimeMs;
}

void UMotionWorldBridgeComponent::HandlePostFinalize(
	const FMoverSyncState& SyncState,
	const FMoverAuxStateContext& AuxState)
{
	(void)AuxState;

	MotionWorld::FAuthoritativeStateInputs StateInputs;
	StateInputs.SampleSequence = NextStateSampleSequence++;
	StateInputs.MovementMode = SyncState.MovementMode;

	if (MoverComponent)
	{
		const FMoverTimeStep& TimeStep = MoverComponent->GetLastTimeStep();
		StateInputs.MoverStepServerFrame = TimeStep.ServerFrame;
		StateInputs.SimulationTimeSeconds =
			(TimeStep.BaseSimTimeMs + static_cast<double>(TimeStep.StepMs)) * 0.001;
		StateInputs.StepSeconds = static_cast<double>(TimeStep.StepMs) * 0.001;
		StateInputs.bIsResimulation = TimeStep.bIsResimulating;
	}

	const FMoverDefaultSyncState* FinalizedState =
		SyncState.SyncStateCollection.FindDataByType<FMoverDefaultSyncState>();
	if (FinalizedState)
	{
		StateInputs.bHasAuthoritativeSource = true;
		StateInputs.PositionWorldCm = FinalizedState->GetLocation_WorldSpace();
		StateInputs.VelocityWorldCmPerSec = FinalizedState->GetVelocity_WorldSpace();
		StateInputs.OrientationWorldDegrees = FinalizedState->GetOrientation_WorldSpace();
		StateInputs.AngularVelocityWorldDegPerSec =
			FinalizedState->GetAngularVelocityDegrees_WorldSpace();
	}

	LastAuthoritativeState = MotionWorld::BuildAuthoritativeStateSample(StateInputs);
	const bool bValidityChanged = !bHasAuthoritativeStateSample
		|| LastAuthoritativeState.bIsValid != bPreviousAuthoritativeStateWasValid;
	const bool bPeriodicStateLog = StateDiagnosticLogIntervalSamples > 0
		&& LastAuthoritativeState.SampleSequence % StateDiagnosticLogIntervalSamples == 0;

	if (LastAuthoritativeState.bIsValid
		&& (bValidityChanged || bPeriodicStateLog))
	{
		UE_LOG(
			LogMotionWorldBridge,
			Display,
			TEXT("MotionWorld state sample: protocol=%d sequence=%lld valid=true mover_step_frame=%d sim_time_s=%.6f step_s=%.6f resim=%s mode=%s position_world_cm=(%.2f, %.2f, %.2f) velocity_world_cm_per_sec=(%.2f, %.2f, %.2f) velocity_local_planar_cm_per_sec=(%.2f, %.2f, %.2f) facing_yaw_deg=%.2f facing_unit_world=(%.6f, %.6f) angular_velocity_world_deg_per_sec=(%.2f, %.2f, %.2f)"),
			LastAuthoritativeState.ProtocolVersion,
			LastAuthoritativeState.SampleSequence,
			LastAuthoritativeState.MoverStepServerFrame,
			LastAuthoritativeState.SimulationTimeSeconds,
			LastAuthoritativeState.StepSeconds,
			LastAuthoritativeState.bIsResimulation ? TEXT("true") : TEXT("false"),
			*LastAuthoritativeState.MovementMode.ToString(),
			LastAuthoritativeState.PositionWorldCm.X,
			LastAuthoritativeState.PositionWorldCm.Y,
			LastAuthoritativeState.PositionWorldCm.Z,
			LastAuthoritativeState.VelocityWorldCmPerSec.X,
			LastAuthoritativeState.VelocityWorldCmPerSec.Y,
			LastAuthoritativeState.VelocityWorldCmPerSec.Z,
			LastAuthoritativeState.VelocityLocalPlanarCmPerSec.X,
			LastAuthoritativeState.VelocityLocalPlanarCmPerSec.Y,
			LastAuthoritativeState.VelocityLocalPlanarCmPerSec.Z,
			LastAuthoritativeState.FacingYawDegrees,
			LastAuthoritativeState.FacingUnitWorld.X,
			LastAuthoritativeState.FacingUnitWorld.Y,
			LastAuthoritativeState.AngularVelocityWorldDegPerSec.X,
			LastAuthoritativeState.AngularVelocityWorldDegPerSec.Y,
			LastAuthoritativeState.AngularVelocityWorldDegPerSec.Z);
	}
	else if (!LastAuthoritativeState.bIsValid && bValidityChanged)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Error,
			TEXT("MotionWorld authoritative state became invalid at sequence %lld; source=%s sim_time_s=%.6f step_s=%.6f."),
			LastAuthoritativeState.SampleSequence,
			StateInputs.bHasAuthoritativeSource ? TEXT("present") : TEXT("missing"),
			LastAuthoritativeState.SimulationTimeSeconds,
			LastAuthoritativeState.StepSeconds);
	}

	bHasAuthoritativeStateSample = true;
	bPreviousAuthoritativeStateWasValid = LastAuthoritativeState.bIsValid;
	if (LastAuthoritativeState.bIsValid && !LastAuthoritativeState.bIsResimulation)
	{
		++ValidFinalizedStateCount;
	}
	CaptureResetAnchorIfEligible();
	ProcessPendingResetVerification();
	RequestConfiguredWarmupResetIfDue();

	const FCharacterDefaultInputs* EchoedInputs = nullptr;
	if (MoverComponent)
	{
		const FMoverInputCmdContext& EchoedCommand = MoverComponent->GetLastInputCmd();
		EchoedInputs =
			EchoedCommand.InputCollection.FindDataByType<FCharacterDefaultInputs>();
	}

	if (EpisodeRecorder.GetStats().bIsRecording)
	{
		const bool bAppliedInputWasVelocity = EchoedInputs
			&& EchoedInputs->GetMoveInputType() == EMoveInputType::Velocity;
		const FVector AppliedVelocityWorldCmPerSec = EchoedInputs
			? EchoedInputs->GetMoveInput_WorldSpace()
			: FVector::ZeroVector;
		const bool bWasMotionWorldAutomated = bAutomationEnabled
			&& bLastCommandFrameResolved
			&& bLastSubmittedInputWasFinite
			&& bAppliedInputWasVelocity
			&& AppliedVelocityWorldCmPerSec.Equals(
				LastSubmittedVelocityWorldCmPerSec,
				0.011);

		LastRecorderObservationResult = EpisodeRecorder.ObserveFinalizedStep(
			LastAuthoritativeState,
			bAppliedInputWasVelocity,
			bWasMotionWorldAutomated,
			AppliedVelocityWorldCmPerSec);
		const FMotionWorldEpisodeRecorderStats RecorderStats =
			EpisodeRecorder.GetStats();

		if (LastRecorderObservationResult
			== EMotionWorldRecorderObservationResult::Seeded)
		{
			UE_LOG(
				LogMotionWorldBridge,
				Display,
				TEXT("MotionWorld episode seeded: episode=%lld state_sequence=%lld mover_step_frame=%d sim_time_s=%.6f."),
				RecorderStats.EpisodeId,
				LastAuthoritativeState.SampleSequence,
				LastAuthoritativeState.MoverStepServerFrame,
				LastAuthoritativeState.SimulationTimeSeconds);
		}
		else if (LastRecorderObservationResult
			== EMotionWorldRecorderObservationResult::Recorded)
		{
			LastRecordedTransition = EpisodeRecorder.GetTransitions().Last();
			const bool bPeriodicTransitionLog =
				TransitionDiagnosticLogIntervalSamples > 0
				&& RecorderStats.RecordedTransitionCount
					% TransitionDiagnosticLogIntervalSamples == 0;
			if (RecorderStats.RecordedTransitionCount == 1 || bPeriodicTransitionLog)
			{
				UE_LOG(
					LogMotionWorldBridge,
					Display,
					TEXT("MotionWorld transition recorded: episode=%lld transition_sequence=%lld previous_state_sequence=%lld next_state_sequence=%lld delta_s=%.6f action_world_cm_per_sec=(%.2f, %.2f, %.2f) action_local_cm_per_sec=(%.2f, %.2f, %.2f) automated=%s recorded=%lld rejected=%lld."),
					LastRecordedTransition.EpisodeId,
					LastRecordedTransition.TransitionSequence,
					LastRecordedTransition.PreviousState.SampleSequence,
					LastRecordedTransition.NextState.SampleSequence,
					LastRecordedTransition.DeltaTimeSeconds,
					LastRecordedTransition.AppliedAction.VelocityWorldCmPerSec.X,
					LastRecordedTransition.AppliedAction.VelocityWorldCmPerSec.Y,
					LastRecordedTransition.AppliedAction.VelocityWorldCmPerSec.Z,
					LastRecordedTransition.AppliedAction.VelocityLocalPlanarCmPerSec.X,
					LastRecordedTransition.AppliedAction.VelocityLocalPlanarCmPerSec.Y,
					LastRecordedTransition.AppliedAction.VelocityLocalPlanarCmPerSec.Z,
					LastRecordedTransition.AppliedAction.bWasMotionWorldAutomated
						? TEXT("true")
						: TEXT("false"),
					RecorderStats.RecordedTransitionCount,
					RecorderStats.RejectedTransitionCount);
			}
		}
		else if (LastRecorderObservationResult
			== EMotionWorldRecorderObservationResult::RejectedSeed
			|| LastRecorderObservationResult
				== EMotionWorldRecorderObservationResult::RejectedTransition)
		{
			if (!bHasLoggedRecorderRejection
				|| RecorderStats.LastRejectionReason
					!= LastLoggedRecorderRejectionReason)
			{
				UE_LOG(
					LogMotionWorldBridge,
					Warning,
					TEXT("MotionWorld episode rejected observation: episode=%lld result=%d reason=%d state_sequence=%lld attempted=%lld recorded=%lld rejected=%lld rejected_seeds=%lld."),
					RecorderStats.EpisodeId,
					static_cast<int32>(LastRecorderObservationResult),
					static_cast<int32>(RecorderStats.LastRejectionReason),
					LastAuthoritativeState.SampleSequence,
					RecorderStats.AttemptedTransitionCount,
					RecorderStats.RecordedTransitionCount,
					RecorderStats.RejectedTransitionCount,
					RecorderStats.RejectedSeedStateCount);
				LastLoggedRecorderRejectionReason = RecorderStats.LastRejectionReason;
				bHasLoggedRecorderRejection = true;
			}
		}
		else if (LastRecorderObservationResult
			== EMotionWorldRecorderObservationResult::StoppedBufferFull)
		{
			UE_LOG(
				LogMotionWorldBridge,
				Error,
				TEXT("MotionWorld episode buffer full: episode=%lld capacity=%d recorded=%lld; recording stopped without overwriting rows."),
				RecorderStats.EpisodeId,
				MaxRecordedTransitions,
				RecorderStats.RecordedTransitionCount);
			if (bExportEpisodeOnStop)
			{
				ExportCurrentEpisode(RecorderStats);
			}
		}
	}

	ProcessTimedArenaObservation();

	if (!bAutomationEnabled || !MoverComponent)
	{
		return;
	}
	if (bDeferCommandEchoUntilNextProduction)
	{
		return;
	}

	bLastCommandEchoMatched = bLastCommandFrameResolved
		&& bLastSubmittedInputWasFinite
		&& EchoedInputs
		&& EchoedInputs->GetMoveInputType() == EMoveInputType::Velocity
		&& EchoedInputs->GetMoveInput_WorldSpace().Equals(
			LastSubmittedVelocityWorldCmPerSec,
			0.011);

	LastEchoedVelocityWorldCmPerSec = EchoedInputs
		? EchoedInputs->GetMoveInput_WorldSpace()
		: FVector::ZeroVector;

	if (LastLoggedRevision != CommandRevision)
	{
		UE_LOG(
			LogMotionWorldBridge,
			Display,
			TEXT("MotionWorld command echo: revision=%llu frame=%s resolved=%s facing_yaw_deg=%.2f finite=%s requested_frame=(%.2f, %.2f, %.2f) submitted_world=(%.2f, %.2f, %.2f) echoed_world=(%.2f, %.2f, %.2f) match=%s"),
			CommandRevision,
			VelocityCommandFrame == EMotionWorldVelocityCommandFrame::CharacterLocal
				? TEXT("character_local")
				: TEXT("world"),
			bLastCommandFrameResolved ? TEXT("true") : TEXT("false"),
			LastResolvedFacingYawDegrees,
			bLastSubmittedInputWasFinite ? TEXT("true") : TEXT("false"),
			LastRequestedVelocityInCommandFrameCmPerSec.X,
			LastRequestedVelocityInCommandFrameCmPerSec.Y,
			LastRequestedVelocityInCommandFrameCmPerSec.Z,
			LastSubmittedVelocityWorldCmPerSec.X,
			LastSubmittedVelocityWorldCmPerSec.Y,
			LastSubmittedVelocityWorldCmPerSec.Z,
			LastEchoedVelocityWorldCmPerSec.X,
			LastEchoedVelocityWorldCmPerSec.Y,
			LastEchoedVelocityWorldCmPerSec.Z,
			bLastCommandEchoMatched ? TEXT("true") : TEXT("false"));

		if (!bLastCommandEchoMatched)
		{
			UE_LOG(
				LogMotionWorldBridge,
				Error,
				TEXT("Mover did not retain MotionWorld command revision %llu."),
				CommandRevision);
		}

		LastLoggedRevision = CommandRevision;
	}
}
