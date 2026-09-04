#include "MotionWorldNetworkControllerComponent.h"

#include "DrawDebugHelpers.h"
#include "Engine/Engine.h"
#include "GameFramework/Actor.h"
#include "HAL/PlatformTime.h"
#include "Misc/Guid.h"
#include "MotionWorldBridgeComponent.h"
#include "MotionWorldControlAction.h"
#include "MotionWorldControlObservation.h"
#include "MotionWorldDemoPresentation.h"
#include "MotionWorldNominalContext.h"
#include "MotionWorldStateSample.h"

DEFINE_LOG_CATEGORY_STATIC(LogMotionWorldNetwork, Log, All);

namespace MotionWorld
{
bool HasReactiveTargetContextChanged(
	const bool bOldTargetPresent,
	const FVector& OldTargetWorldCm,
	const FVector2D& OldTerminalVelocityLocalCmPerSec,
	const bool bNewTargetPresent,
	const FVector& NewTargetWorldCm,
	const FVector2D& NewTerminalVelocityLocalCmPerSec)
{
	constexpr float ContextTolerance = 0.01f;
	return bOldTargetPresent != bNewTargetPresent
		|| !OldTargetWorldCm.Equals(NewTargetWorldCm, ContextTolerance)
		|| !OldTerminalVelocityLocalCmPerSec.Equals(
			NewTerminalVelocityLocalCmPerSec,
			ContextTolerance);
}
} // namespace MotionWorld

UMotionWorldNetworkControllerComponent::UMotionWorldNetworkControllerComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
	PrimaryComponentTick.bTickEvenWhenPaused = true;
}

void UMotionWorldNetworkControllerComponent::BeginPlay()
{
	Super::BeginPlay();
	BridgeComponent = GetOwner()
		? GetOwner()->FindComponentByClass<UMotionWorldBridgeComponent>()
		: nullptr;
	if (!BridgeComponent)
	{
		UE_LOG(LogMotionWorldNetwork, Error,
			TEXT("MotionWorld network controller on '%s' requires a bridge component."),
			*GetNameSafe(GetOwner()));
		bNetworkControlEnabled = false;
		return;
	}
	const bool bEnableAtBeginPlay = bNetworkControlEnabled;
	bNetworkControlEnabled = false;
	if (bEnableAtBeginPlay && !SetNetworkControlEnabled(true))
	{
		UE_LOG(LogMotionWorldNetwork, Error,
			TEXT("MotionWorld network controller failed to enable at BeginPlay."));
	}
	if (bLogNetworkEvidence)
	{
		EvidenceSessionId =
			FGuid::NewGuid().ToString(EGuidFormats::Digits).Left(12);
		UE_LOG(LogMotionWorldNetwork, Display,
			TEXT("MotionWorld network evidence started: session=%s controller=%s max_lines=%d endpoints=127.0.0.1:%d->127.0.0.1:%d."),
			*EvidenceSessionId,
			*ControllerMode,
			FMath::Clamp(MaxNetworkEvidenceLines, 1, 10000),
			LocalPort,
			RemotePort);
	}
}

void UMotionWorldNetworkControllerComponent::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
	if (bLogNetworkEvidence)
	{
		UE_LOG(LogMotionWorldNetwork, Display,
			TEXT("MotionWorld network evidence stopped: session=%s observations_sent=%lld actions_accepted=%lld rejected=%lld stale=%lld malformed=%lld missed=%lld held=%lld safe_stops=%lld evidence_written=%lld evidence_dropped=%lld."),
			*EvidenceSessionId,
			ControllerStats.ObservationsSent,
			ControllerStats.ActionsAccepted,
			ControllerStats.RejectedActions,
			ControllerStats.StaleActions,
			ControllerStats.MalformedActions,
			ControllerStats.MissedResponses,
			ControllerStats.HeldAfterMiss,
			ControllerStats.SafeStops,
			ControllerStats.EvidenceLinesWritten,
			ControllerStats.EvidenceLinesDropped);
	}
	bNetworkControlEnabled = false;
	SetComponentTickEnabled(false);
	Transport.Close();
	ClearControlState();
	if (BridgeComponent)
	{
		BridgeComponent->SetAutomationEnabled(false);
	}
	BridgeComponent = nullptr;
	Super::EndPlay(EndPlayReason);
}

void UMotionWorldNetworkControllerComponent::TickComponent(
	const float DeltaTime,
	const ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!bNetworkControlEnabled)
	{
		return;
	}
	const double Now = FPlatformTime::Seconds();
	PollActions(Now);
	ApplyCommand(Runtime.AdvanceDeadline(Now));
	RefreshRuntimeStats();
	DrawWorldModelVisualization();
	DrawWorldModelHud();
}

bool UMotionWorldNetworkControllerComponent::SetNetworkControlEnabled(
	const bool bEnabled)
{
	if (bEnabled == bNetworkControlEnabled)
	{
		return true;
	}
	if (!bEnabled)
	{
		if (BridgeComponent && BridgeComponent->GetResetStatus().bIsPending)
		{
			UE_LOG(LogMotionWorldNetwork, Warning,
				TEXT("Network disable deferred: deterministic reset verification is pending."));
			return false;
		}
		bNetworkControlEnabled = false;
		SetComponentTickEnabled(false);
		Transport.Close();
		ClearControlState();
		if (BridgeComponent)
		{
			BridgeComponent->SetAutomationEnabled(false);
		}
		return true;
	}
	if (!BridgeComponent || !IsSupportedControllerMode(ControllerMode))
	{
		return false;
	}
	if (!MotionWorld::IsNetworkActionProducerConfigurationValid(
		BridgeComponent->HasCompetingNetworkActionProducer()))
	{
		UE_LOG(LogMotionWorldNetwork, Error,
			TEXT("MotionWorld network control refused: the varied-action schedule is a competing command producer and must be disabled."));
		return false;
	}
	if (!OpenTransport())
	{
		Transport.Close();
		return false;
	}
	ControllerStats = FMotionWorldNetworkControllerStats();
	bNetworkControlEnabled = true;
	BridgeComponent->SetVelocityCommandFrame(
		EMotionWorldVelocityCommandFrame::CharacterLocal);
	BridgeComponent->SetDesiredVelocityLocalCmPerSec(FVector::ZeroVector);
	BridgeComponent->SetAutomationEnabled(true);
	SetComponentTickEnabled(true);
	UE_LOG(LogMotionWorldNetwork, Display,
		TEXT("MotionWorld network control enabled: controller=%s local_port=%d remote_port=%d interval_ms=100 deadline_ms=100; waiting for a verified reset episode."),
		*ControllerMode, LocalPort, RemotePort);
	return true;
}

bool UMotionWorldNetworkControllerComponent::SetControllerMode(
	const FString& NewControllerMode)
{
	if (!IsSupportedControllerMode(NewControllerMode))
	{
		return false;
	}
	if (ControllerMode == NewControllerMode)
	{
		return true;
	}
	ControllerMode = NewControllerMode;
	VisualizationState.InvalidateEpisodeBoundary();
	if (bNetworkControlEnabled)
	{
		return ReconnectService();
	}
	return true;
}

bool UMotionWorldNetworkControllerComponent::ReconnectService()
{
	if (!bNetworkControlEnabled)
	{
		return false;
	}
	Transport.Close();
	ClearControlState();
	return OpenTransport();
}

bool UMotionWorldNetworkControllerComponent::SetReactiveTarget(
	const bool bTargetPresent,
	const FVector TargetWorldCm,
	const FVector2D DesiredTerminalVelocityLocalCmPerSec)
{
	const bool bTargetFinite = FMath::IsFinite(TargetWorldCm.X)
		&& FMath::IsFinite(TargetWorldCm.Y)
		&& FMath::IsFinite(TargetWorldCm.Z);
	const bool bTerminalVelocityFinite =
		FMath::IsFinite(DesiredTerminalVelocityLocalCmPerSec.X)
		&& FMath::IsFinite(DesiredTerminalVelocityLocalCmPerSec.Y);
	if ((bTargetPresent && !bTargetFinite) || !bTerminalVelocityFinite)
	{
		return false;
	}
	const FVector NewTargetWorldCm = bTargetPresent
		? TargetWorldCm
		: FVector::ZeroVector;
	const FVector2D NewTerminalVelocityLocalCmPerSec = bTargetPresent
		? DesiredTerminalVelocityLocalCmPerSec
		: FVector2D::ZeroVector;
	const bool bContextChanged = MotionWorld::HasReactiveTargetContextChanged(
		bHasReactiveTarget,
		ReactiveTargetWorldCm,
		ReactiveTerminalVelocityLocalCmPerSec,
		bTargetPresent,
		NewTargetWorldCm,
		NewTerminalVelocityLocalCmPerSec);
	const bool bHadActiveEpisode = Runtime.GetStats().bEnabled;
	if (bContextChanged && bHadActiveEpisode)
	{
		const int64 InvalidatedEpisodeId = Runtime.GetExpectedEpisodeId();
		ClearControlState();
		UE_LOG(LogMotionWorldNetwork, Warning,
			TEXT("MotionWorld reactive target changed during active episode=%lld; control state invalidated and safe zero commanded. A new verified BeginNetworkEpisode is required."),
			InvalidatedEpisodeId);
	}
	bHasReactiveTarget = bTargetPresent;
	ReactiveTargetWorldCm = NewTargetWorldCm;
	ReactiveTerminalVelocityLocalCmPerSec =
		NewTerminalVelocityLocalCmPerSec;
	if (bContextChanged && !bHadActiveEpisode)
	{
		// No episode is active, but any cached prediction still describes the
		// old planner context and must not be drawn.
		VisualizationState.ClearPredictionForSafeStop();
	}
	return true;
}

void UMotionWorldNetworkControllerComponent::PrepareForReset()
{
	if (!bNetworkControlEnabled)
	{
		return;
	}
	if (ReserveEvidenceLine())
	{
		UE_LOG(LogMotionWorldNetwork, Display,
			TEXT("MotionWorld network reset boundary: session=%s old_episode=%lld outstanding_observation=%lld action_state_cleared=true."),
			*EvidenceSessionId,
			Runtime.GetExpectedEpisodeId(),
			Runtime.GetExpectedObservationSequence());
	}
	ClearControlState();
}

bool UMotionWorldNetworkControllerComponent::BeginNetworkEpisode(
	const int64 EpisodeId)
{
	if (!bNetworkControlEnabled || !Runtime.StartEpisode(EpisodeId))
	{
		return false;
	}
	if (!VisualizationState.BeginEpisode(EpisodeId))
	{
		Runtime.Stop();
		return false;
	}
	if (BridgeComponent)
	{
		BridgeComponent->SetVelocityCommandFrame(
			EMotionWorldVelocityCommandFrame::CharacterLocal);
		BridgeComponent->SetDesiredVelocityLocalCmPerSec(FVector::ZeroVector);
	}
	if (ReserveEvidenceLine())
	{
		UE_LOG(LogMotionWorldNetwork, Display,
			TEXT("MotionWorld network episode started: session=%s episode=%lld first_observation_sequence=0 applied_local_cm_per_sec=(0.00, 0.00) prior_state_cleared=true."),
			*EvidenceSessionId,
			EpisodeId);
	}
	return true;
}

void UMotionWorldNetworkControllerComponent::ObserveFinalizedState(
	const FMotionWorldStateSample& State,
	const FMotionWorldNominalContextSample& NominalContext,
	const MotionWorld::FControlTimedGateContext& TimedGate)
{
	if (!bNetworkControlEnabled)
	{
		return;
	}
	const int64 ActiveEpisodeId = Runtime.GetExpectedEpisodeId();
	if (ActiveEpisodeId >= 0 && State.bIsValid && !State.bIsResimulation)
	{
		VisualizationState.AppendAuthoritativeFinalizedPosition(
			ActiveEpisodeId,
			FVector2D(State.PositionWorldCm.X, State.PositionWorldCm.Y));
	}
	const double MonotonicNowSeconds = FPlatformTime::Seconds();
	const MotionWorld::FNetworkObservationDecision Decision =
		Runtime.ObserveFinalizedState(
			State.SimulationTimeSeconds,
			MonotonicNowSeconds,
			State.bIsValid && NominalContext.bIsValid,
			State.bIsResimulation);
	ApplyCommand(Decision.ExpiryUpdate);
	RefreshRuntimeStats();
	if (!Decision.bShouldEmit)
	{
		return;
	}
	if (!VisualizationState.OnAuthoritativeObservationEmitted(
		Decision.EpisodeId,
		Decision.ObservationSequence))
	{
		VisualizationState.ClearPredictionForSafeStop();
		UE_LOG(LogMotionWorldNetwork, Error,
			TEXT("MotionWorld visualization identity rejected an emitted observation: episode=%lld observation=%lld; prediction cleared."),
			Decision.EpisodeId,
			Decision.ObservationSequence);
		return;
	}

	MotionWorld::FControlObservation Observation;
	Observation.EpisodeId = Decision.EpisodeId;
	Observation.ObservationSequence = Decision.ObservationSequence;
	Observation.ControllerMode = ControllerMode;
	Observation.State = State;
	Observation.NominalContext = NominalContext;
	Observation.bHasPreviousAction = Decision.bHasPreviousAction;
	Observation.PreviousActionSourceObservationSequence =
		Decision.PreviousActionSourceObservationSequence;
	Observation.PreviousAppliedVelocityLocalCmPerSec =
		Decision.PreviousAppliedVelocityLocalCmPerSec;
	Observation.bHasTarget = bHasReactiveTarget;
	Observation.TargetPositionWorldCm = ReactiveTargetWorldCm;
	Observation.DesiredTerminalVelocityLocalCmPerSec =
		ReactiveTerminalVelocityLocalCmPerSec;
	Observation.TimedGate = TimedGate;
	if (TimedGate.bIsPresent)
	{
		Observation.ScenarioId = TEXT("timed_gate");
		Observation.ScenarioSeed = TimedGate.Config.ScenarioSeed;
		Observation.ResetId = FString::Printf(
			TEXT("timed_gate:%lld:episode%lld"),
			TimedGate.Config.ScenarioSeed,
			Decision.EpisodeId);
	}
	else
	{
		Observation.ScenarioSeed = Decision.EpisodeId;
		Observation.ResetId = FString::Printf(
			TEXT("network_vertical_slice:%lld"), Decision.EpisodeId);
	}
	TArray<uint8> Payload;
	FString Failure;
	if (!MotionWorld::SerializeControlObservation(Observation, Payload, Failure)
		|| !Transport.Send(Payload))
	{
		++ControllerStats.ObservationSendFailures;
		UE_LOG(LogMotionWorldNetwork, Warning,
			TEXT("MotionWorld observation send failed: episode=%lld observation=%lld reason=%s."),
			Decision.EpisodeId, Decision.ObservationSequence,
			Failure.IsEmpty() ? TEXT("udp_send_failed") : *Failure);
		return;
	}
	++ControllerStats.ObservationsSent;
	OutstandingObservationSentMonotonicSeconds = MonotonicNowSeconds;
	if (ReserveEvidenceLine())
	{
		UE_LOG(LogMotionWorldNetwork, Display,
			TEXT("MotionWorld network observation sent: session=%s episode=%lld observation=%lld state_sequence=%lld simulation_time_s=%.6f facing_yaw_deg=%.6f previous_action_present=%s previous_action_source=%lld."),
			*EvidenceSessionId,
			Decision.EpisodeId,
			Decision.ObservationSequence,
			State.SampleSequence,
			State.SimulationTimeSeconds,
			State.FacingYawDegrees,
			Decision.bHasPreviousAction ? TEXT("true") : TEXT("false"),
			Decision.PreviousActionSourceObservationSequence);
	}
}

bool UMotionWorldNetworkControllerComponent::OpenTransport()
{
	if (LocalPort <= 0 || LocalPort > MAX_uint16
		|| RemotePort <= 0 || RemotePort > MAX_uint16
		|| LocalPort == RemotePort)
	{
		return false;
	}
	MotionWorld::FMotionWorldUdpTransportConfig Config;
	Config.LocalPort = static_cast<uint16>(LocalPort);
	Config.RemotePort = static_cast<uint16>(RemotePort);
	return Transport.Open(Config);
}

void UMotionWorldNetworkControllerComponent::ClearControlState()
{
	Runtime.Stop();
	VisualizationState.InvalidateEpisodeBoundary();
	OutstandingObservationSentMonotonicSeconds = 0.0;
	LastAcceptedEndToEndLatencyMs = -1.0;
	if (BridgeComponent)
	{
		BridgeComponent->SetVelocityCommandFrame(
			EMotionWorldVelocityCommandFrame::CharacterLocal);
		BridgeComponent->SetDesiredVelocityLocalCmPerSec(FVector::ZeroVector);
	}
}

void UMotionWorldNetworkControllerComponent::ApplyCommand(
	const MotionWorld::FNetworkCommandUpdate& Update)
{
	if (Update.Cause == MotionWorld::ENetworkCommandCause::DeadlineSafeStop)
	{
		VisualizationState.ClearPredictionForSafeStop();
	}
	if (!Update.bShouldApply || !BridgeComponent)
	{
		return;
	}
	BridgeComponent->SetDesiredVelocityLocalCmPerSec(FVector(
		Update.DesiredVelocityLocalCmPerSec.X,
		Update.DesiredVelocityLocalCmPerSec.Y,
		0.0));
}

void UMotionWorldNetworkControllerComponent::RefreshRuntimeStats()
{
	const MotionWorld::FNetworkRuntimeStats& Source = Runtime.GetStats();
	ControllerStats.MissedResponses = Source.MissedResponses;
	ControllerStats.HeldAfterMiss = Source.HeldAfterMiss;
	ControllerStats.SafeStops = Source.SafeStops;
}

void UMotionWorldNetworkControllerComponent::PollActions(
	const double MonotonicNowSeconds)
{
	const MotionWorld::FMotionWorldUdpPollResult Poll = Transport.Poll();
	ControllerStats.RejectedTransportDatagrams +=
		Poll.RejectedUnknownSender + Poll.RejectedOversizedOrEmpty;
	for (const TArray<uint8>& Payload : Poll.Payloads)
	{
		const int64 ExpectedEpisodeId = Runtime.GetExpectedEpisodeId();
		const int64 ExpectedObservationSequence =
			Runtime.GetExpectedObservationSequence();
		const bool bExpectedObservationAlreadyAnswered =
			!Runtime.HasOutstandingObservation()
				|| Runtime.WasOutstandingObservationAnswered();
		MotionWorld::FControlAction Action;
		MotionWorld::EControlActionRejection Rejection =
			MotionWorld::EControlActionRejection::None;
		const bool bParsed = MotionWorld::ParseAndValidateControlAction(
			Payload,
			ExpectedEpisodeId,
			ExpectedObservationSequence,
			bExpectedObservationAlreadyAnswered,
			Action,
			Rejection);
		if (!bParsed)
		{
			++ControllerStats.RejectedActions;
			switch (Rejection)
			{
			case MotionWorld::EControlActionRejection::WrongEpisode:
			case MotionWorld::EControlActionRejection::FutureObservation:
			case MotionWorld::EControlActionRejection::StaleObservation:
			case MotionWorld::EControlActionRejection::DuplicateObservation:
				++ControllerStats.StaleActions;
				break;
			default:
				++ControllerStats.MalformedActions;
				break;
			}
			continue;
		}
		if (!MotionWorld::IsControlActionControllerCompatible(
			ControllerMode,
			Action.ControllerId))
		{
			++ControllerStats.RejectedActions;
			++ControllerStats.MalformedActions;
			continue;
		}
		const MotionWorld::FNetworkCommandUpdate Update = Runtime.AcceptAction(
			Action.EpisodeId,
			Action.SourceObservationSequence,
			Action.DesiredVelocityLocalCmPerSec,
			MonotonicNowSeconds);
		if (!Update.bShouldApply)
		{
			++ControllerStats.RejectedActions;
			++ControllerStats.StaleActions;
			continue;
		}
		++ControllerStats.ActionsAccepted;
		LastAcceptedEndToEndLatencyMs =
			OutstandingObservationSentMonotonicSeconds > 0.0
				? FMath::Max(0.0,
					MonotonicNowSeconds
						- OutstandingObservationSentMonotonicSeconds) * 1000.0
				: -1.0;
		if (Action.bHasVisualization
			&& !VisualizationState.InstallFromAdmittedAction(
				Action,
				ExpectedEpisodeId,
				ExpectedObservationSequence))
		{
			VisualizationState.ClearPredictionForSafeStop();
			UE_LOG(LogMotionWorldNetwork, Error,
				TEXT("MotionWorld admitted action visualization failed the final identity check: episode=%lld observation=%lld; prediction cleared."),
				ExpectedEpisodeId,
				ExpectedObservationSequence);
		}
		if (ReserveEvidenceLine())
		{
			UE_LOG(LogMotionWorldNetwork, Display,
				TEXT("MotionWorld network action accepted: session=%s episode=%lld source_observation=%lld desired_local_cm_per_sec=(%.6f, %.6f) unreal_end_to_end_latency_ms=%.6f current_identity_match=true before_deadline=true."),
				*EvidenceSessionId,
				Action.EpisodeId,
				Action.SourceObservationSequence,
				Action.DesiredVelocityLocalCmPerSec.X,
				Action.DesiredVelocityLocalCmPerSec.Y,
				LastAcceptedEndToEndLatencyMs);
		}
		ApplyCommand(Update);
		RefreshRuntimeStats();
	}
}

void UMotionWorldNetworkControllerComponent::DrawWorldModelVisualization() const
{
	if (!bDrawWorldModelVisualization || !GetWorld() || !GetOwner())
	{
		return;
	}

	const float DrawZ = GetOwner()->GetActorLocation().Z
		+ FMath::Max(0.0f, VisualizationHeightOffsetCm);
	const float Thickness = FMath::Max(0.0f, VisualizationLineThickness);
	// Visualization packets contain planar Unreal world XY coordinates in cm.
	const auto DrawPath = [this, DrawZ, Thickness](
		const TArray<FVector2D>& Points,
		const FColor& Color,
		const float ThicknessScale)
	{
		for (int32 Index = 1; Index < Points.Num(); ++Index)
		{
			DrawDebugLine(
				GetWorld(),
				FVector(Points[Index - 1].X, Points[Index - 1].Y, DrawZ),
				FVector(Points[Index].X, Points[Index].Y, DrawZ),
				Color,
				false,
				0.0f,
				0,
				Thickness * ThicknessScale);
		}
	};

	if (VisualizationState.HasPrediction())
	{
		const auto DrawRole = [this, &DrawPath](
			const TCHAR* Role,
			const FColor& Color,
			const float ThicknessScale)
		{
			for (const MotionWorld::FControlVisualizationPath& Path
				: VisualizationState.GetPrediction().Paths)
			{
				if (Path.Role == Role)
				{
					DrawPath(Path.PointsWorldXYCm, Color, ThicknessScale);
				}
			}
		};

		// Fixed painter's order keeps the high-signal paths visible regardless
		// of the order supplied by the controller packet.
		DrawRole(TEXT("cem_candidate"), FColor(110, 110, 110), 0.5f);
		DrawRole(TEXT("branch_forward"), FColor::Cyan, 1.0f);
		DrawRole(TEXT("branch_left"), FColor::Magenta, 1.0f);
		DrawRole(TEXT("branch_right"), FColor::Red, 1.0f);
		DrawRole(TEXT("branch_stop"), FColor::White, 1.0f);
		DrawRole(TEXT("nominal"), FColor::Blue, 1.0f);
		DrawRole(TEXT("residual"), FColor(255, 128, 0), 1.0f);
		DrawRole(TEXT("selected"), FColor::Green, 1.5f);
	}

	DrawPath(
		VisualizationState.GetActualTrailWorldXYCm(),
		FColor::Yellow,
		1.25f);

	if (bHasReactiveTarget)
	{
		const FColor TargetColor(150, 255, 20);
		const FVector TargetBase = ReactiveTargetWorldCm
			+ FVector(0.0, 0.0, FMath::Max(0.0f, VisualizationHeightOffsetCm));
		DrawDebugSphere(
			GetWorld(), TargetBase, 35.0f, 16, TargetColor, false, 0.0f, 0, Thickness);
		DrawDebugLine(
			GetWorld(),
			TargetBase,
			TargetBase + FVector(0.0, 0.0, 180.0),
			TargetColor,
			false,
			0.0f,
			0,
			Thickness);
	}
}

void UMotionWorldNetworkControllerComponent::DrawWorldModelHud() const
{
	if (!bDrawWorldModelHud || !bHasReactiveTarget || !GEngine)
	{
		return;
	}
	MotionWorld::FDemoPresentationContext Context;
	Context.bNetworkEnabled = bNetworkControlEnabled;
	Context.bWorldPaused = GetWorld() && GetWorld()->IsPaused();
	Context.bHasTarget = bHasReactiveTarget;
	Context.ConfiguredControllerMode = ControllerMode;
	Context.LastEndToEndLatencyMs = LastAcceptedEndToEndLatencyMs;
	Context.ActionsAccepted = ControllerStats.ActionsAccepted;
	Context.SafeStops = ControllerStats.SafeStops;
	const MotionWorld::FDemoPresentation Presentation =
		MotionWorld::BuildDemoPresentation(VisualizationState, Context);

	constexpr uint64 MotionWorldHudMessageKey = 0x4D4F54494F4E574CULL;
	GEngine->AddOnScreenDebugMessage(
		MotionWorldHudMessageKey,
		0.2f,
		Presentation.StatusColor,
		Presentation.HudText,
		true,
		FVector2D(1.15f, 1.15f));
}

bool UMotionWorldNetworkControllerComponent::ReserveEvidenceLine()
{
	if (!bLogNetworkEvidence)
	{
		return false;
	}
	if (ControllerStats.EvidenceLinesWritten
		>= FMath::Clamp(MaxNetworkEvidenceLines, 1, 10000))
	{
		++ControllerStats.EvidenceLinesDropped;
		return false;
	}
	++ControllerStats.EvidenceLinesWritten;
	return true;
}

bool UMotionWorldNetworkControllerComponent::IsSupportedControllerMode(
	const FString& Value)
{
	return Value == TEXT("echo")
		|| Value == TEXT("reactive")
		|| Value == TEXT("branch_preview")
		|| Value == TEXT("nominal_mpc")
		|| Value == TEXT("residual_mpc");
}

namespace MotionWorld
{
bool IsControlActionControllerCompatible(
	const FString& ConfiguredControllerMode,
	const FString& ActionControllerId)
{
	return ConfiguredControllerMode == ActionControllerId;
}
} // namespace MotionWorld
