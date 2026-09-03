#if WITH_DEV_AUTOMATION_TESTS

#include "Dom/JsonObject.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "MotionWorldControlAction.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
bool LoadFixture(const TCHAR* Name, TArray<uint8>& OutBytes)
{
	const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("MotionWorld"));
	if (!Plugin.IsValid())
	{
		return false;
	}
	return FFileHelper::LoadFileToArray(
		OutBytes,
		*FPaths::Combine(
			Plugin->GetBaseDir(),
			TEXT("Resources"),
			TEXT("ProtocolFixtures"),
			TEXT("v1"),
			Name));
}

TArray<uint8> Utf8Bytes(const FString& Text)
{
	const FTCHARToUTF8 Converted(*Text);
	TArray<uint8> Result;
	Result.Append(reinterpret_cast<const uint8*>(Converted.Get()), Converted.Length());
	return Result;
}

FString Utf8Text(const TArray<uint8>& Bytes)
{
	const FUTF8ToTCHAR Converted(
		reinterpret_cast<const ANSICHAR*>(Bytes.GetData()),
		Bytes.Num());
	return FString(Converted.Length(), Converted.Get());
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldProtocolCrossLanguageTest,
	"MotionWorld.Protocol.CrossLanguageFixtures",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldProtocolCrossLanguageTest::RunTest(const FString& Parameters)
{
	using namespace MotionWorld;

	TArray<uint8> ActionBytes;
	TArray<uint8> ZeroActionBytes;
	TArray<uint8> ObservationBytes;
	if (!TestTrue(TEXT("Python action fixture loads"), LoadFixture(TEXT("action.json"), ActionBytes))
		|| !TestTrue(
			TEXT("Python zero-boundary action fixture loads"),
			LoadFixture(TEXT("action_zero_no_telemetry.json"), ZeroActionBytes))
		|| !TestTrue(
			TEXT("Unreal observation fixture loads"),
			LoadFixture(TEXT("observation.json"), ObservationBytes)))
	{
		return false;
	}

	FControlAction Action;
	EControlActionRejection Rejection = EControlActionRejection::InvalidSchema;
	TestTrue(
		TEXT("Unreal admits the Python-produced action"),
		ParseAndValidateControlAction(ActionBytes, 7101, 12, false, Action, Rejection));
	TestEqual(TEXT("Action episode survives the boundary"), Action.EpisodeId, int64(7101));
	TestEqual(
		TEXT("Action observation identity survives the boundary"),
		Action.SourceObservationSequence,
		int64(12));
	TestTrue(
		TEXT("Action vector survives the boundary"),
		Action.DesiredVelocityLocalCmPerSec.Equals(FVector2D(120.0, -30.0)));
	TestEqual(TEXT("Diagnostic trajectory remains bounded"), Action.SelectedTrajectoryLocalCmPerSec.Num(), 2);

	FControlAction ZeroAction;
	TestTrue(
		TEXT("Zero/boundary action is admitted"),
		ParseAndValidateControlAction(ZeroActionBytes, 0, 0, false, ZeroAction, Rejection));
	TestTrue(TEXT("Zero action remains exactly zero"), ZeroAction.DesiredVelocityLocalCmPerSec.IsZero());
	TestFalse(TEXT("Optional telemetry is explicitly absent"), ZeroAction.bHasTelemetry);

	const FString ObservationText = Utf8Text(ObservationBytes);
	TSharedPtr<FJsonObject> Observation;
	const TSharedRef<TJsonReader<>> ObservationReader = TJsonReaderFactory<>::Create(ObservationText);
	TestTrue(
		TEXT("Unreal-produced observation fixture is valid JSON in Unreal"),
		FJsonSerializer::Deserialize(ObservationReader, Observation) && Observation.IsValid());
	if (Observation.IsValid())
	{
		const TSharedPtr<FJsonObject>* Protocol = nullptr;
		const TSharedPtr<FJsonObject>* Identity = nullptr;
		TestTrue(
			TEXT("Observation protocol object is present"),
			Observation->TryGetObjectField(TEXT("protocol"), Protocol) && Protocol && Protocol->IsValid());
		TestTrue(
			TEXT("Observation identity object is present"),
			Observation->TryGetObjectField(TEXT("identity"), Identity) && Identity && Identity->IsValid());
		if (Protocol && Protocol->IsValid())
		{
			TestEqual(TEXT("Observation protocol version is v1"), (*Protocol)->GetNumberField(TEXT("version")), 1.0);
			TestEqual(
				TEXT("Observation message type is explicit"),
				(*Protocol)->GetStringField(TEXT("message_type")),
				FString(TEXT("observation")));
		}
		if (Identity && Identity->IsValid())
		{
			TestEqual(TEXT("Observation episode is exact"), (*Identity)->GetNumberField(TEXT("episode_id")), 7101.0);
			TestEqual(
				TEXT("Observation sequence is exact"),
				(*Identity)->GetNumberField(TEXT("observation_sequence")),
				1.0);
		}
	}

	auto ExpectRejection = [this](
		const TCHAR* What,
		const TArray<uint8>& Payload,
		const EControlActionRejection Expected)
	{
		FControlAction Parsed;
		EControlActionRejection Actual = EControlActionRejection::None;
		TestFalse(What, ParseAndValidateControlAction(Payload, 7101, 12, false, Parsed, Actual));
		TestEqual(*FString::Printf(TEXT("%s rejection"), What), Actual, Expected);
		TestTrue(
			*FString::Printf(TEXT("%s diagnostic is bounded"), What),
			FCString::Strlen(LexToString(Actual)) <= 32);
	};

	TArray<uint8> InvalidUtf8 = {0xff};
	ExpectRejection(TEXT("Invalid UTF-8"), InvalidUtf8, EControlActionRejection::InvalidUtf8);
	ExpectRejection(TEXT("Truncated JSON"), Utf8Bytes(TEXT("{")), EControlActionRejection::InvalidJson);

	FString Mutated = Utf8Text(ActionBytes);
	Mutated.ReplaceInline(TEXT("\"episode_id\":7101"), TEXT("\"episode_id\":7101,\"episode_id\":7101"));
	ExpectRejection(TEXT("Duplicate JSON key"), Utf8Bytes(Mutated), EControlActionRejection::DuplicateJsonKey);

	Mutated = Utf8Text(ActionBytes);
	Mutated.ReplaceInline(TEXT("[120.0,-30.0]"), TEXT("[120.0]"));
	ExpectRejection(TEXT("Wrong vector dimension"), Utf8Bytes(Mutated), EControlActionRejection::InvalidSchema);

	Mutated = Utf8Text(ActionBytes);
	Mutated.ReplaceInline(TEXT("\"version\":1"), TEXT("\"version\":2"));
	ExpectRejection(TEXT("Unknown protocol version"), Utf8Bytes(Mutated), EControlActionRejection::InvalidSchema);

	Mutated = Utf8Text(ActionBytes);
	Mutated.ReplaceInline(TEXT("12.5"), TEXT("1e309"));
	ExpectRejection(TEXT("Infinite parsed number"), Utf8Bytes(Mutated), EControlActionRejection::InvalidSchema);

	Mutated = Utf8Text(ActionBytes);
	Mutated.ReplaceInline(TEXT("\"episode_id\":7101"), TEXT("\"episode_id\":9007199254740992"));
	ExpectRejection(TEXT("Unsafe JSON integer"), Utf8Bytes(Mutated), EControlActionRejection::InvalidSchema);

	FControlAction RejectedAction;
	TestFalse(
		TEXT("Wrong episode is rejected"),
		ParseAndValidateControlAction(ActionBytes, 7102, 12, false, RejectedAction, Rejection));
	TestEqual(TEXT("Wrong episode has a stable reason"), Rejection, EControlActionRejection::WrongEpisode);
	TestFalse(
		TEXT("Future action is rejected"),
		ParseAndValidateControlAction(ActionBytes, 7101, 11, false, RejectedAction, Rejection));
	TestEqual(TEXT("Future action has a stable reason"), Rejection, EControlActionRejection::FutureObservation);
	TestFalse(
		TEXT("Stale action is rejected"),
		ParseAndValidateControlAction(ActionBytes, 7101, 13, false, RejectedAction, Rejection));
	TestEqual(TEXT("Stale action has a stable reason"), Rejection, EControlActionRejection::StaleObservation);
	TestFalse(
		TEXT("Duplicate accepted action is rejected"),
		ParseAndValidateControlAction(ActionBytes, 7101, 12, true, RejectedAction, Rejection));
	TestEqual(
		TEXT("Duplicate action has a stable reason"),
		Rejection,
		EControlActionRejection::DuplicateObservation);

	FRandomStream Random(20260903);
	for (int32 PacketIndex = 0; PacketIndex < 128; ++PacketIndex)
	{
		TArray<uint8> Fuzz;
		Fuzz.SetNumUninitialized(Random.RandRange(1, 256));
		for (uint8& Byte : Fuzz)
		{
			Byte = static_cast<uint8>(Random.RandRange(0, 255));
		}
		FControlAction Ignored;
		EControlActionRejection FuzzRejection = EControlActionRejection::None;
		TestFalse(
			TEXT("Bounded malformed fuzz packet fails closed"),
			ParseAndValidateControlAction(Fuzz, 7101, 12, false, Ignored, FuzzRejection));
	}

	TestTrue(TEXT("Action fixture respects the action byte cap"), ActionBytes.Num() <= MaxControlActionBytes);
	TestTrue(TEXT("Observation fixture respects its frozen byte cap"), ObservationBytes.Num() <= 16384);
	TestFalse(TEXT("Diagnostic rejection never contains packet data"), FString(LexToString(Rejection)).Contains(TEXT("SECRET")));
	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
