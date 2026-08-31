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
	Super::EndPlay(EndPlayReason);
}

bool AMotionWorldArenaManager::InitializeArena(
	AActor* NewTrackedAgent,
	const FMotionWorldTimedGateConfig& NewGateConfig,
	const double ScenarioStartWorldTimeSeconds)
{
	UWorld* World = GetWorld();
	if (!World
		|| !IsValid(NewTrackedAgent)
		|| !MotionWorld::IsTimedGateConfigValid(NewGateConfig))
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

	TrackedAgent = NewTrackedAgent;
	GateConfig = NewGateConfig;
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
		|| !TimedGate->ResetTimedGate(ScenarioStartWorldTimeSeconds))
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
	if (!GateState.bIsValid)
	{
		Result.TerminationReason =
			EMotionWorldScenarioTerminationReason::InvalidConfiguration;
	}
	else
	{
		ArenaStatus.ScenarioTimeSeconds = GateState.ScenarioTimeSeconds;
		const bool bCollisionThisStep =
			TimedGate->ConsumeTrackedAgentCollision();
		ArenaStatus.CollisionCount =
			TimedGate->GetTrackedAgentCollisionCount();
		if (bHasPreviousAgentPosition)
		{
			Result = MotionWorld::EvaluateTimedGateScenarioStep(
				GateConfig,
				PreviousAgentPositionWorldCm,
				AgentPositionWorldCm,
				ArenaStatus.ScenarioTimeSeconds,
				bCollisionThisStep);
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
		TimedGate->DeactivateTimedGate();
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
