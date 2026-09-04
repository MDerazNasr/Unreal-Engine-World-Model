#include "MotionWorldTimedGateActor.h"

#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

DEFINE_LOG_CATEGORY_STATIC(LogMotionWorldTimedGate, Log, All);

AMotionWorldTimedGateActor::AMotionWorldTimedGateActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	SetReplicates(false);

	CollisionBox = CreateDefaultSubobject<UBoxComponent>(TEXT("GateCollision"));
	SetRootComponent(CollisionBox);
	CollisionBox->SetMobility(EComponentMobility::Movable);
	CollisionBox->SetCollisionProfileName(UCollisionProfile::BlockAllDynamic_ProfileName);
	CollisionBox->SetGenerateOverlapEvents(false);
	CollisionBox->SetNotifyRigidBodyCollision(true);
	CollisionBox->OnComponentHit.AddDynamic(
		this,
		&AMotionWorldTimedGateActor::HandleCollisionBoxHit);

	VisualMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("GateVisual"));
	VisualMesh->SetupAttachment(CollisionBox);
	VisualMesh->SetMobility(EComponentMobility::Movable);
	VisualMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (CubeMesh.Succeeded())
	{
		VisualMesh->SetStaticMesh(CubeMesh.Object);
	}
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BasicShapeMaterial(
		TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (BasicShapeMaterial.Succeeded())
	{
		VisualMesh->SetMaterial(0, BasicShapeMaterial.Object);
	}
}

void AMotionWorldTimedGateActor::BeginPlay()
{
	Super::BeginPlay();
	// The engine basic-shape material exposes Color. A saturated obstacle is
	// much easier to read against the sample project's natural backgrounds.
	VisualMesh->SetVectorParameterValueOnMaterials(
		TEXT("Color"),
		FVector(1.0, 0.025, 0.005));
	if (!bScenarioActive)
	{
		SetActorTickEnabled(false);
	}
}

bool AMotionWorldTimedGateActor::InitializeTimedGate(
	const FMotionWorldTimedGateConfig& NewConfig,
	AActor* NewTrackedAgent,
	const double NewScenarioStartWorldTimeSeconds)
{
	if (!MotionWorld::IsTimedGateConfigValid(NewConfig)
		|| !IsValid(NewTrackedAgent)
		|| !FMath::IsFinite(NewScenarioStartWorldTimeSeconds)
		|| NewScenarioStartWorldTimeSeconds < 0.0)
	{
		bScenarioActive = false;
		SetActorTickEnabled(false);
		return false;
	}

	GateConfig = NewConfig;
	TrackedAgent = NewTrackedAgent;
	CollisionBox->SetBoxExtent(GateConfig.HalfExtentsCm, false);
	VisualMesh->SetRelativeScale3D(GateConfig.HalfExtentsCm / 50.0);
	return ResetTimedGate(NewScenarioStartWorldTimeSeconds);
}

bool AMotionWorldTimedGateActor::ResetTimedGate(
	const double NewScenarioStartWorldTimeSeconds)
{
	if (!MotionWorld::IsTimedGateConfigValid(GateConfig)
		|| !IsValid(TrackedAgent)
		|| !FMath::IsFinite(NewScenarioStartWorldTimeSeconds)
		|| NewScenarioStartWorldTimeSeconds < 0.0)
	{
		bScenarioActive = false;
		SetActorTickEnabled(false);
		return false;
	}

	ScenarioStartWorldTimeSeconds = NewScenarioStartWorldTimeSeconds;
	TrackedAgentCollisionCount = 0;
	bTrackedAgentCollisionPending = false;
	CollisionBox->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	bScenarioActive = ApplyScheduleAtScenarioTime(0.0);
	SetActorTickEnabled(bScenarioActive);
	if (bScenarioActive)
	{
		UE_LOG(
			LogMotionWorldTimedGate,
			Display,
			TEXT("MotionWorld timed gate reset: seed=%lld motion=sinusoidal_translation origin_world_cm=(%.2f, %.2f, %.2f) axis_world=(%.6f, %.6f, %.6f) amplitude_cm=%.2f period_s=%.3f phase_offset_rad=%.6f half_extents_cm=(%.2f, %.2f, %.2f) crossing_normal_world=(%.6f, %.6f, %.6f) timeout_s=%.3f."),
			GateConfig.ScenarioSeed,
			GateConfig.OriginWorldCm.X,
			GateConfig.OriginWorldCm.Y,
			GateConfig.OriginWorldCm.Z,
			GateConfig.MotionAxisWorld.GetSafeNormal().X,
			GateConfig.MotionAxisWorld.GetSafeNormal().Y,
			GateConfig.MotionAxisWorld.GetSafeNormal().Z,
			GateConfig.AmplitudeCm,
			GateConfig.PeriodSeconds,
			GateConfig.PhaseOffsetRadians,
			GateConfig.HalfExtentsCm.X,
			GateConfig.HalfExtentsCm.Y,
			GateConfig.HalfExtentsCm.Z,
			GateConfig.CrossingPlaneNormalWorld.GetSafeNormal().X,
			GateConfig.CrossingPlaneNormalWorld.GetSafeNormal().Y,
			GateConfig.CrossingPlaneNormalWorld.GetSafeNormal().Z,
			GateConfig.TimeoutSeconds);
	}
	return bScenarioActive;
}

void AMotionWorldTimedGateActor::Tick(const float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	(void)DeltaSeconds;

	const UWorld* World = GetWorld();
	if (!bScenarioActive || !World)
	{
		return;
	}

	const double ScenarioTimeSeconds =
		static_cast<double>(World->GetTimeSeconds()) - ScenarioStartWorldTimeSeconds;
	if (!ApplyScheduleAtScenarioTime(FMath::Max(0.0, ScenarioTimeSeconds)))
	{
		bScenarioActive = false;
		SetActorTickEnabled(false);
		UE_LOG(
			LogMotionWorldTimedGate,
			Error,
			TEXT("MotionWorld timed gate stopped because analytic schedule evaluation failed."));
	}
}

bool AMotionWorldTimedGateActor::ApplyScheduleAtScenarioTime(
	const double ScenarioTimeSeconds)
{
	const FMotionWorldTimedGateState EvaluatedState =
		MotionWorld::EvaluateTimedGateSchedule(GateConfig, ScenarioTimeSeconds);
	if (!EvaluatedState.bIsValid)
	{
		return false;
	}

	GateState = EvaluatedState;
	SetActorLocation(
		GateState.CenterWorldCm,
		false,
		nullptr,
		ETeleportType::TeleportPhysics);
	return true;
}

void AMotionWorldTimedGateActor::HandleCollisionBoxHit(
	UPrimitiveComponent* HitComponent,
	AActor* OtherActor,
	UPrimitiveComponent* OtherComponent,
	FVector NormalImpulse,
	const FHitResult& Hit)
{
	(void)HitComponent;
	(void)OtherComponent;
	(void)NormalImpulse;

	if (!bScenarioActive || OtherActor != TrackedAgent)
	{
		return;
	}
	if (bTrackedAgentCollisionPending)
	{
		// Physics may report several contacts before the next authoritative
		// character observation. They represent one scenario-step collision.
		return;
	}

	++TrackedAgentCollisionCount;
	bTrackedAgentCollisionPending = true;
	UE_LOG(
		LogMotionWorldTimedGate,
		Display,
		TEXT("MotionWorld timed gate collision: seed=%lld count=%lld scenario_time_s=%.6f gate_center_world_cm=(%.2f, %.2f, %.2f) agent='%s' impact_world_cm=(%.2f, %.2f, %.2f)."),
		GateConfig.ScenarioSeed,
		TrackedAgentCollisionCount,
		GateState.ScenarioTimeSeconds,
		GateState.CenterWorldCm.X,
		GateState.CenterWorldCm.Y,
		GateState.CenterWorldCm.Z,
		*GetNameSafe(OtherActor),
		Hit.ImpactPoint.X,
		Hit.ImpactPoint.Y,
		Hit.ImpactPoint.Z);
}

bool AMotionWorldTimedGateActor::ConsumeTrackedAgentCollision()
{
	const bool bHadCollision = bTrackedAgentCollisionPending;
	bTrackedAgentCollisionPending = false;
	return bHadCollision;
}

void AMotionWorldTimedGateActor::FreezeTimedGateAtTerminal()
{
	bScenarioActive = false;
	bTrackedAgentCollisionPending = false;
	SetActorTickEnabled(false);
	UE_LOG(
		LogMotionWorldTimedGate,
		Display,
		TEXT("MotionWorld timed gate frozen at terminal state: seed=%lld scenario_time_s=%.6f collision_retained=%s."),
		GateConfig.ScenarioSeed,
		GateState.ScenarioTimeSeconds,
		IsPhysicalCollisionEnabled() ? TEXT("true") : TEXT("false"));
}

bool AMotionWorldTimedGateActor::IsPhysicalCollisionEnabled() const
{
	return CollisionBox
		&& CollisionBox->GetCollisionEnabled() != ECollisionEnabled::NoCollision;
}
