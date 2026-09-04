#include "MotionWorldArenaManager.h"

#include "Engine/World.h"
#include "MotionWorldTimedGateActor.h"

DEFINE_LOG_CATEGORY_STATIC(LogMotionWorldArena, Log, All);

AMotionWorldArenaManager::AMotionWorldArenaManager()
{
	PrimaryActorTick.bCanEverTick = false;
	SetReplicates(false);
}

void AMotionWorldArenaManager::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (IsValid(TimedGate))
	{
		TimedGate->Destroy();
	}
	if (IsValid(SecondaryTimedGate))
	{
		SecondaryTimedGate->Destroy();
	}
	Super::EndPlay(EndPlayReason);
}

bool AMotionWorldArenaManager::InitializeArena(
	AActor* NewTrackedAgent,
	const FMotionWorldTimedGateConfig& NewGateConfig,
	const double ScenarioStartWorldTimeSeconds,
	const bool bNewContinueAfterSuccessPlaneCrossing,
	const FMotionWorldTimedGateConfig* NewSecondaryGateConfig)
{
	UWorld* World = GetWorld();
	if (!World
		|| !IsValid(NewTrackedAgent)
		|| !MotionWorld::IsTimedGateConfigValid(NewGateConfig)
		|| (NewSecondaryGateConfig
			&& !MotionWorld::IsTimedGateConfigValid(*NewSecondaryGateConfig)))
	{
		return false;
	}

	if (!IsValid(TimedGate))
	{
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.Owner = this;
		SpawnParameters.SpawnCollisionHandlingOverride =
			ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		TimedGate = World->SpawnActor<AMotionWorldTimedGateActor>(
			AMotionWorldTimedGateActor::StaticClass(),
			NewGateConfig.OriginWorldCm,
			FRotator::ZeroRotator,
			SpawnParameters);
	}

	if (!IsValid(TimedGate)
		|| !TimedGate->InitializeTimedGate(
			NewGateConfig,
			NewTrackedAgent,
			ScenarioStartWorldTimeSeconds))
	{
		return false;
	}
	TimedGate->SetObstacleColor(FLinearColor(1.0f, 0.025f, 0.005f, 1.0f));

	if (NewSecondaryGateConfig)
	{
		if (!IsValid(SecondaryTimedGate))
		{
			FActorSpawnParameters SpawnParameters;
			SpawnParameters.Owner = this;
			SpawnParameters.SpawnCollisionHandlingOverride =
				ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			SecondaryTimedGate = World->SpawnActor<AMotionWorldTimedGateActor>(
				AMotionWorldTimedGateActor::StaticClass(),
				NewSecondaryGateConfig->OriginWorldCm,
				FRotator::ZeroRotator,
				SpawnParameters);
		}
		if (!IsValid(SecondaryTimedGate)
			|| !SecondaryTimedGate->InitializeTimedGate(
				*NewSecondaryGateConfig,
				NewTrackedAgent,
				ScenarioStartWorldTimeSeconds))
		{
			return false;
		}
		SecondaryTimedGate->SetObstacleColor(
			FLinearColor(1.0f, 0.22f, 0.01f, 1.0f));
		SecondaryGateConfig = *NewSecondaryGateConfig;
	}

	TrackedAgent = NewTrackedAgent;
	GateConfig = NewGateConfig;
	bContinueAfterSuccessPlaneCrossing =
		bNewContinueAfterSuccessPlaneCrossing;
	ArenaStatus = FMotionWorldArenaStatus();
	ArenaStatus.bIsInitialized = true;
	ArenaStatus.bIsActive = true;
	ArenaStatus.ScenarioSeed = GateConfig.ScenarioSeed;
	bHasPreviousAgentPosition = false;
	return true;
}

bool AMotionWorldArenaManager::ResetArena(
	const double ScenarioStartWorldTimeSeconds)
{
	if (!ArenaStatus.bIsInitialized
		|| !IsValid(TimedGate)
		|| !TimedGate->ResetTimedGate(ScenarioStartWorldTimeSeconds)
		|| (IsValid(SecondaryTimedGate)
			&& !SecondaryTimedGate->ResetTimedGate(
				ScenarioStartWorldTimeSeconds)))
	{
		return false;
	}

	ArenaStatus.bIsActive = true;
	ArenaStatus.ScenarioTimeSeconds = 0.0;
	ArenaStatus.CollisionCount = 0;
	ArenaStatus.TerminationReason =
		EMotionWorldScenarioTerminationReason::None;
	bHasPreviousAgentPosition = false;
	return true;
}

FMotionWorldScenarioStepResult AMotionWorldArenaManager::ObserveFinalizedAgentPosition(
	const FVector& AgentPositionWorldCm)
{
	FMotionWorldScenarioStepResult Result;
	if (!ArenaStatus.bIsInitialized
		|| !ArenaStatus.bIsActive
		|| !IsValid(TimedGate)
		|| AgentPositionWorldCm.ContainsNaN())
	{
		return Result;
	}

	const FMotionWorldTimedGateState GateState = TimedGate->GetGateState();
	const FMotionWorldTimedGateState SecondaryGateState =
		IsValid(SecondaryTimedGate)
			? SecondaryTimedGate->GetGateState()
			: FMotionWorldTimedGateState();
	if (!GateState.bIsValid
		|| (IsValid(SecondaryTimedGate) && !SecondaryGateState.bIsValid))
	{
		Result.TerminationReason =
			EMotionWorldScenarioTerminationReason::InvalidConfiguration;
	}
	else
	{
		ArenaStatus.ScenarioTimeSeconds = GateState.ScenarioTimeSeconds;
		const bool bCollisionThisStep =
			TimedGate->ConsumeTrackedAgentCollision()
			|| (IsValid(SecondaryTimedGate)
				&& SecondaryTimedGate->ConsumeTrackedAgentCollision());
		ArenaStatus.CollisionCount =
			TimedGate->GetTrackedAgentCollisionCount()
			+ (IsValid(SecondaryTimedGate)
				? SecondaryTimedGate->GetTrackedAgentCollisionCount()
				: 0);
		if (bHasPreviousAgentPosition)
		{
			Result = MotionWorld::EvaluateTimedGateScenarioStep(
				GateConfig,
				PreviousAgentPositionWorldCm,
				AgentPositionWorldCm,
				ArenaStatus.ScenarioTimeSeconds,
				bCollisionThisStep,
				bContinueAfterSuccessPlaneCrossing);
		}
		else if (bCollisionThisStep)
		{
			Result.TerminationReason =
				EMotionWorldScenarioTerminationReason::GateCollision;
		}
	}

	PreviousAgentPositionWorldCm = AgentPositionWorldCm;
	bHasPreviousAgentPosition = true;
	if (Result.TerminationReason != EMotionWorldScenarioTerminationReason::None)
	{
		ArenaStatus.bIsActive = false;
		ArenaStatus.TerminationReason = Result.TerminationReason;
		TimedGate->FreezeTimedGateAtTerminal();
		if (IsValid(SecondaryTimedGate))
		{
			SecondaryTimedGate->FreezeTimedGateAtTerminal();
		}
		UE_LOG(
			LogMotionWorldArena,
			Display,
			TEXT("MotionWorld arena terminated: seed=%lld reason=%s scenario_time_s=%.6f collision_count=%lld agent_position_world_cm=(%.2f, %.2f, %.2f)."),
			ArenaStatus.ScenarioSeed,
			MotionWorld::LexToString(ArenaStatus.TerminationReason),
			ArenaStatus.ScenarioTimeSeconds,
			ArenaStatus.CollisionCount,
			AgentPositionWorldCm.X,
			AgentPositionWorldCm.Y,
			AgentPositionWorldCm.Z);
	}
	return Result;
}

FMotionWorldTimedGateState AMotionWorldArenaManager::GetGateState() const
{
	return IsValid(TimedGate)
		? TimedGate->GetGateState()
		: FMotionWorldTimedGateState();
}

FMotionWorldTimedGateState AMotionWorldArenaManager::GetSecondaryGateState() const
{
	return IsValid(SecondaryTimedGate)
		? SecondaryTimedGate->GetGateState()
		: FMotionWorldTimedGateState();
}

bool AMotionWorldArenaManager::HasSecondaryGate() const
{
	return IsValid(SecondaryTimedGate);
}
