#include "MotionWorldNetworkControllerComponent.h"

#include "GameFramework/Actor.h"
#include "HAL/PlatformTime.h"
#include "MotionWorldBridgeComponent.h"
#include "MotionWorldControlAction.h"
#include "MotionWorldControlObservation.h"
#include "MotionWorldNominalContext.h"
#include "MotionWorldStateSample.h"

DEFINE_LOG_CATEGORY_STATIC(LogMotionWorldNetwork, Log, All);

UMotionWorldNetworkControllerComponent::UMotionWorldNetworkControllerComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
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
}

void UMotionWorldNetworkControllerComponent::EndPlay(
	const EEndPlayReason::Type EndPlayReason)
{
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
	if (!BridgeComponent || !IsSupportedControllerMode(ControllerMode)
		|| !OpenTransport())
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
	bHasReactiveTarget = bTargetPresent;
	ReactiveTargetWorldCm = bTargetPresent
		? TargetWorldCm
		: FVector::ZeroVector;
	ReactiveTerminalVelocityLocalCmPerSec = bTargetPresent
		? DesiredTerminalVelocityLocalCmPerSec
		: FVector2D::ZeroVector;
	return true;
}

void UMotionWorldNetworkControllerComponent::PrepareForReset()
{
	if (!bNetworkControlEnabled)
	{
		return;
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
	if (BridgeComponent)
	{
		BridgeComponent->SetVelocityCommandFrame(
			EMotionWorldVelocityCommandFrame::CharacterLocal);
		BridgeComponent->SetDesiredVelocityLocalCmPerSec(FVector::ZeroVector);
	}
	return true;
}

void UMotionWorldNetworkControllerComponent::ObserveFinalizedState(
	const FMotionWorldStateSample& State,
	const FMotionWorldNominalContextSample& NominalContext)
{
	if (!bNetworkControlEnabled)
	{
		return;
	}
	const MotionWorld::FNetworkObservationDecision Decision =
		Runtime.ObserveFinalizedState(
			State.SimulationTimeSeconds,
			FPlatformTime::Seconds(),
			State.bIsValid && NominalContext.bIsValid,
			State.bIsResimulation);
	ApplyCommand(Decision.ExpiryUpdate);
	RefreshRuntimeStats();
	if (!Decision.bShouldEmit)
	{
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
	Observation.ScenarioSeed = Decision.EpisodeId;
	Observation.ResetId = FString::Printf(
		TEXT("network_vertical_slice:%lld"), Decision.EpisodeId);
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
		MotionWorld::FControlAction Action;
		MotionWorld::EControlActionRejection Rejection =
			MotionWorld::EControlActionRejection::None;
		const bool bParsed = MotionWorld::ParseAndValidateControlAction(
			Payload,
			Runtime.GetExpectedEpisodeId(),
			Runtime.GetExpectedObservationSequence(),
			!Runtime.HasOutstandingObservation()
				|| Runtime.WasOutstandingObservationAnswered(),
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
		ApplyCommand(Update);
		RefreshRuntimeStats();
	}
}

bool UMotionWorldNetworkControllerComponent::IsSupportedControllerMode(
	const FString& Value)
{
	return Value == TEXT("echo")
		|| Value == TEXT("reactive")
		|| Value == TEXT("nominal_mpc")
		|| Value == TEXT("residual_mpc");
}
