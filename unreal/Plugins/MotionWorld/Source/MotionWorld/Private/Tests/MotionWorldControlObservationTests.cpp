#if WITH_DEV_AUTOMATION_TESTS

#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "MotionWorldControlObservation.h"
#include "MotionWorldNetworkControllerComponent.h"
#include "MotionWorldUdpTransport.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#include <limits>

namespace
{
MotionWorld::FControlObservation MakeObservation(const int64 Sequence)
{
	MotionWorld::FControlObservation Result;
	Result.EpisodeId = 7101;
	Result.ObservationSequence = Sequence;
	Result.ControllerMode = TEXT("echo");
	Result.ScenarioSeed = 7101;
	Result.ResetId = TEXT("network_vertical_slice:7101");
	Result.State.SampleSequence = 44 + Sequence;
	Result.State.SimulationTimeSeconds = 1.25;
	Result.State.bIsValid = true;
	Result.State.MovementMode = TEXT("Walking");
	Result.State.PositionWorldCm = FVector(10.0, 20.0, 86.0);
	Result.State.VelocityWorldCmPerSec = FVector(100.0, 0.0, 0.0);
	Result.State.VelocityLocalPlanarCmPerSec = FVector(100.0, 0.0, 0.0);
	Result.State.FacingYawDegrees = 0.0;
	Result.State.FacingUnitWorld = FVector2D(1.0, 0.0);
	Result.State.AngularVelocityWorldDegPerSec = FVector(0.0, 0.0, 5.0);
	Result.NominalContext.bIsValid = true;
	Result.NominalContext.AuthoritativeStateSampleSequence = Result.State.SampleSequence;
	Result.NominalContext.MovementModeName = TEXT("Walking");
	Result.NominalContext.MovementModeClass = TEXT("BP_MovementMode_Walking_C");
	Result.NominalContext.Parameters.AccelerationCmPerSecSquared = 500.0;
	Result.NominalContext.Parameters.DecelerationCmPerSecSquared = 300.0;
	Result.NominalContext.Parameters.DirectionalAccelerationFactor = 0.5;
	Result.NominalContext.Parameters.TurningStrength = 8.0;
	Result.NominalContext.Parameters.AccelerationSmoothingTimeSeconds = 0.3;
	Result.NominalContext.Parameters.DecelerationSmoothingTimeSeconds = 0.3;
	Result.NominalContext.Parameters.OutsideInfluenceSmoothingTimeSeconds = 0.1;
	Result.NominalContext.Parameters.FacingSmoothingTimeSeconds = 0.4;
	Result.NominalContext.Parameters.bSmoothFacingWithDoubleSpring = true;
	Result.NominalContext.Parameters.FacingDeadzoneDegrees = 0.1;
	Result.NominalContext.Parameters.AngularVelocityDeadzoneDegreesPerSec = 0.1;
	Result.NominalContext.InputPreparation.bHasMaxMoveSpeed = true;
	Result.NominalContext.InputPreparation.EffectiveMaxSpeedCmPerSec = 600.0;
	Result.NominalContext.InputPreparation.MaxSpeedSource =
		EMotionWorldMaxSpeedSource::CommonLegacySettings;
	return Result;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldControlObservationTest,
	"MotionWorld.Network.ObservationSerialization",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldControlObservationTest::RunTest(const FString& Parameters)
{
	UMotionWorldNetworkControllerComponent* DefaultController =
		NewObject<UMotionWorldNetworkControllerComponent>();
	TestNotNull(TEXT("Network controller can be constructed"), DefaultController);
	TestFalse(TEXT("Network control is default-off"),
		DefaultController && DefaultController->IsNetworkControlEnabled());
	TestTrue(TEXT("Finite reactive target is accepted"),
		DefaultController && DefaultController->SetReactiveTarget(
			true, FVector(700.0, -125.0, 86.0), FVector2D::ZeroVector));
	TestFalse(TEXT("Non-finite reactive target is rejected"),
		DefaultController && DefaultController->SetReactiveTarget(
			true,
			FVector(std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0),
			FVector2D::ZeroVector));

	MotionWorld::FControlObservation Observation = MakeObservation(0);
	TArray<uint8> Payload;
	FString Failure;
	TestTrue(TEXT("Valid sequence zero serializes"),
		MotionWorld::SerializeControlObservation(Observation, Payload, Failure));
	TestTrue(TEXT("Payload is bounded"),
		Payload.Num() > 0 && Payload.Num() <= MotionWorld::MaxObservationDatagramBytes);

	FUTF8ToTCHAR Decoded(reinterpret_cast<const ANSICHAR*>(Payload.GetData()), Payload.Num());
	const FString Json(Decoded.Length(), Decoded.Get());
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	TestTrue(TEXT("Output is JSON"), FJsonSerializer::Deserialize(Reader, Root));
	TestTrue(TEXT("Root is present"), Root.IsValid());
	if (Root.IsValid())
	{
		const TSharedPtr<FJsonObject>* Protocol = nullptr;
		TestTrue(TEXT("Protocol object exists"), Root->TryGetObjectField(TEXT("protocol"), Protocol));
		if (Protocol && Protocol->IsValid())
		{
			TestEqual(TEXT("Protocol name is exact"), (*Protocol)->GetStringField(TEXT("name")), FString(TEXT("motionworld_control")));
			TestEqual(TEXT("Protocol type is observation"), (*Protocol)->GetStringField(TEXT("message_type")), FString(TEXT("observation")));
		}
		const TSharedPtr<FJsonObject>* Previous = nullptr;
		TestTrue(TEXT("Previous action object exists"), Root->TryGetObjectField(TEXT("previous_action"), Previous));
		if (Previous && Previous->IsValid())
		{
			TestFalse(TEXT("Sequence zero marks previous action absent"), (*Previous)->GetBoolField(TEXT("is_present")));
			TestEqual(TEXT("Absent previous action has one exact key"), (*Previous)->Values.Num(), 1);
		}
		const TSharedPtr<FJsonObject>* Planner = nullptr;
		TestTrue(TEXT("Planner context exists"), Root->TryGetObjectField(TEXT("planner_context"), Planner));
		if (Planner && Planner->IsValid())
		{
			const TSharedPtr<FJsonObject>* Target = nullptr;
			TestTrue(TEXT("Target object exists"), (*Planner)->TryGetObjectField(TEXT("target"), Target));
			if (Target && Target->IsValid())
			{
				TestFalse(TEXT("Target defaults absent"), (*Target)->GetBoolField(TEXT("is_present")));
				TestEqual(TEXT("Absent target has one exact key"), (*Target)->Values.Num(), 1);
			}
		}
	}

	Observation = MakeObservation(1);
	Observation.bHasPreviousAction = true;
	Observation.PreviousActionSourceObservationSequence = 0;
	Observation.PreviousAppliedVelocityLocalCmPerSec = FVector2D(120.0, -30.0);
	TestTrue(TEXT("Later observation with causal previous action serializes"),
		MotionWorld::SerializeControlObservation(Observation, Payload, Failure));
	Observation.bHasTarget = true;
	Observation.TargetPositionWorldCm = FVector(700.0, -125.0, 86.0);
	Observation.DesiredTerminalVelocityLocalCmPerSec = FVector2D::ZeroVector;
	TestTrue(TEXT("Finite reactive target serializes"),
		MotionWorld::SerializeControlObservation(Observation, Payload, Failure));
	Observation.TargetPositionWorldCm.X = std::numeric_limits<double>::quiet_NaN();
	TestFalse(TEXT("Non-finite reactive target fails closed"),
		MotionWorld::SerializeControlObservation(Observation, Payload, Failure));
	Observation.TargetPositionWorldCm.X = 700.0;
	Observation.NominalContext.AuthoritativeStateSampleSequence += 1;
	TestFalse(TEXT("Misaligned hidden context fails closed"),
		MotionWorld::SerializeControlObservation(Observation, Payload, Failure));

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
