#include "MotionWorldBridgeComponent.h"

#include "GameFramework/Actor.h"
#include "MoverComponent.h"
#include "MoverDataModelTypes.h"
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
		TEXT("MotionWorld bridge ready on '%s'; automation=%s, max_planar_speed=%.2f cm/s."),
		*GetNameSafe(GetOwner()),
		bAutomationEnabled ? TEXT("enabled") : TEXT("disabled"),
		MaxPlanarSpeedCmPerSec);
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
	++CommandRevision;
	return true;
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

	const MotionWorld::FSanitizedVelocityCommand Sanitized =
		MotionWorld::SanitizeWorldVelocityCommand(
			DesiredVelocityWorldCmPerSec,
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
	bLastSubmittedInputWasFinite = Sanitized.bInputWasFinite;

	(void)SimTimeMs;
}

void UMotionWorldBridgeComponent::HandlePostFinalize(
	const FMoverSyncState& SyncState,
	const FMoverAuxStateContext& AuxState)
{
	(void)SyncState;
	(void)AuxState;

	if (!bAutomationEnabled || !MoverComponent)
	{
		return;
	}

	const FMoverInputCmdContext& EchoedCommand = MoverComponent->GetLastInputCmd();
	const FCharacterDefaultInputs* EchoedInputs =
		EchoedCommand.InputCollection.FindDataByType<FCharacterDefaultInputs>();

	bLastCommandEchoMatched = EchoedInputs
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
			TEXT("MotionWorld command echo: revision=%llu finite=%s requested=(%.2f, %.2f, %.2f) submitted=(%.2f, %.2f, %.2f) echoed=(%.2f, %.2f, %.2f) match=%s"),
			CommandRevision,
			bLastSubmittedInputWasFinite ? TEXT("true") : TEXT("false"),
			DesiredVelocityWorldCmPerSec.X,
			DesiredVelocityWorldCmPerSec.Y,
			DesiredVelocityWorldCmPerSec.Z,
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
