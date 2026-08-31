#include "MotionWorldBridgeComponent.h"

#include "GameFramework/Actor.h"
#include "MoverComponent.h"
#include "MoverDataModelTypes.h"
#include "MoverTypes.h"
#include "MotionWorldCoordinateFrames.h"
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

	if (bStartEpisodeRecordingOnBeginPlay)
	{
		StartEpisodeRecording(BeginPlayEpisodeId);
	}
}

void UMotionWorldBridgeComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (MoverComponent)
	{
		MoverComponent->OnPostFinalize.RemoveDynamic(
			this,
			&UMotionWorldBridgeComponent::HandlePostFinalize);
	}

	Super::EndPlay(EndPlayReason);
}

void UMotionWorldBridgeComponent::SetAutomationEnabled(const bool bEnabled)
{
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
	if (VelocityCommandFrame != NewFrame)
	{
		VelocityCommandFrame = NewFrame;
		++CommandRevision;
	}
}

bool UMotionWorldBridgeComponent::SetDesiredVelocityLocalCmPerSec(
	const FVector& RequestedVelocity)
{
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
	Inputs.OrientationIntent = ExistingOrientationIntentWorld;
	Inputs.SetMoveInput(EMoveInputType::Velocity, Sanitized.WorldVelocityCmPerSec);

	// Read back the value stored by SetMoveInput because Mover quantizes it to 0.01 cm/s.
	LastSubmittedVelocityWorldCmPerSec = Inputs.GetMoveInput();
	bLastSubmittedInputWasFinite =
		Sanitized.bInputWasFinite && bLastCommandFrameResolved;

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
		}
	}

	if (!bAutomationEnabled || !MoverComponent)
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
