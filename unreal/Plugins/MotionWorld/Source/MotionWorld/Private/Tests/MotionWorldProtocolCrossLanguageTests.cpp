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

TSharedPtr<FJsonObject> MakeVisualizationFixture()
{
	auto Visualization = MakeShared<FJsonObject>();
	auto Schema = MakeShared<FJsonObject>();
	Schema->SetStringField(TEXT("name"), TEXT("motionworld_visualization"));
	Schema->SetNumberField(TEXT("version"), 1.0);
	Visualization->SetObjectField(TEXT("schema"), Schema);
	auto Identity = MakeShared<FJsonObject>();
	Identity->SetNumberField(TEXT("episode_id"), 7101.0);
	Identity->SetNumberField(TEXT("source_observation_sequence"), 12.0);
	Visualization->SetObjectField(TEXT("identity"), Identity);
	Visualization->SetStringField(TEXT("frame"), TEXT("unreal_world_xy_cm"));
	auto Sampling = MakeShared<FJsonObject>();
	Sampling->SetNumberField(TEXT("horizon_s"), 0.2);
	Sampling->SetNumberField(TEXT("timestep_s"), 0.1);
	Visualization->SetObjectField(TEXT("sampling"), Sampling);

	auto MakePath = [](const TCHAR* Role, const double Y)
	{
		auto Path = MakeShared<FJsonObject>();
		Path->SetStringField(TEXT("role"), Role);
		TArray<TSharedPtr<FJsonValue>> Points;
		for (int32 Index = 0; Index < 3; ++Index)
		{
			TArray<TSharedPtr<FJsonValue>> Components;
			Components.Add(MakeShared<FJsonValueNumber>(100.0 * Index));
			Components.Add(MakeShared<FJsonValueNumber>(Y));
			Points.Add(MakeShared<FJsonValueArray>(Components));
		}
		Path->SetArrayField(TEXT("points_world_xy_cm"), Points);
		return MakeShared<FJsonValueObject>(Path);
	};
	Visualization->SetArrayField(TEXT("paths"), {
		MakePath(TEXT("cem_candidate"), 10.0),
		MakePath(TEXT("selected"), 20.0)});
	return Visualization;
}

TArray<uint8> AttachVisualization(
	const TArray<uint8>& ActionBytes,
	const TSharedPtr<FJsonObject>& Visualization)
{
	TSharedPtr<FJsonObject> Action;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Utf8Text(ActionBytes));
	if (!FJsonSerializer::Deserialize(Reader, Action) || !Action.IsValid())
	{
		return {};
	}
	const TSharedPtr<FJsonObject>* Telemetry = nullptr;
	if (!Action->TryGetObjectField(TEXT("telemetry"), Telemetry) || !Telemetry || !Telemetry->IsValid())
	{
		return {};
	}
	(*Telemetry)->SetObjectField(TEXT("visualization"), Visualization);
	FString Text;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text);
	if (!FJsonSerializer::Serialize(Action.ToSharedRef(), Writer))
	{
		return {};
	}
	return Utf8Bytes(Text);
}

int32 CompactJsonUtf8Size(const TSharedPtr<FJsonObject>& Object)
{
	FString Text;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text);
	if (!Object.IsValid() || !FJsonSerializer::Serialize(Object.ToSharedRef(), Writer))
	{
		return INDEX_NONE;
	}
	return FTCHARToUTF8(*Text).Length();
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
	TArray<uint8> FourBranchesActionBytes;
	TArray<uint8> ObservationBytes;
	if (!TestTrue(TEXT("Python action fixture loads"), LoadFixture(TEXT("action.json"), ActionBytes))
		|| !TestTrue(
			TEXT("Python four-branch visualization fixture loads"),
			LoadFixture(TEXT("action_visualization_four_branches.json"), FourBranchesActionBytes))
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
	TestFalse(TEXT("Legacy present telemetry has no visualization"), Action.bHasVisualization);

	FControlAction FourBranchesAction;
	TestTrue(
		TEXT("Python four-branch visualization fixture is admitted directly"),
		ParseAndValidateControlAction(
			FourBranchesActionBytes,
			7101,
			12,
			false,
			FourBranchesAction,
			Rejection));
	TestTrue(TEXT("Four-branch fixture carries visualization"), FourBranchesAction.bHasVisualization);
	TestEqual(TEXT("Four-branch episode identity survives"), FourBranchesAction.Visualization.EpisodeId, int64(7101));
	TestEqual(TEXT("Four-branch source identity survives"), FourBranchesAction.Visualization.SourceObservationSequence, int64(12));
	TestEqual(TEXT("Four visualization roles survive"), FourBranchesAction.Visualization.Paths.Num(), 4);
	const TArray<FString> ExpectedBranchRoles = {
		TEXT("branch_forward"), TEXT("branch_left"), TEXT("branch_right"), TEXT("branch_stop")};
	for (int32 Index = 0; Index < FourBranchesAction.Visualization.Paths.Num(); ++Index)
	{
		TestEqual(
			*FString::Printf(TEXT("Four-branch role %d survives"), Index),
			FourBranchesAction.Visualization.Paths[Index].Role,
			ExpectedBranchRoles[Index]);
		TestEqual(
			*FString::Printf(TEXT("Four-branch point count %d survives"), Index),
			FourBranchesAction.Visualization.Paths[Index].PointsWorldXYCm.Num(),
			3);
	}
	TestTrue(TEXT("Four-branch fixture respects outer action cap"), FourBranchesActionBytes.Num() <= MaxControlActionBytes);

	const TArray<uint8> VisualizationActionBytes = AttachVisualization(
		ActionBytes,
		MakeVisualizationFixture());
	FControlAction VisualizationAction;
	TestTrue(
		TEXT("Action with visualization telemetry is admitted"),
		ParseAndValidateControlAction(
			VisualizationActionBytes,
			7101,
			12,
			false,
			VisualizationAction,
			Rejection));
	TestTrue(TEXT("Visualization presence survives parsing"), VisualizationAction.bHasVisualization);
	TestEqual(TEXT("Visualization identity survives parsing"), VisualizationAction.Visualization.EpisodeId, int64(7101));
	TestEqual(TEXT("Visualization paths survive parsing"), VisualizationAction.Visualization.Paths.Num(), 2);
	if (VisualizationAction.Visualization.Paths.Num() == 2)
	{
		TestEqual(
			TEXT("Visualization selected role survives parsing"),
			VisualizationAction.Visualization.Paths[1].Role,
			FString(TEXT("selected")));
		TestEqual(
			TEXT("Visualization points survive parsing"),
			VisualizationAction.Visualization.Paths[1].PointsWorldXYCm.Num(),
			3);
	}

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
		Parsed.EpisodeId = 999;
		Parsed.ControllerId = TEXT("sentinel");
		Parsed.bHasVisualization = true;
		EControlActionRejection Actual = EControlActionRejection::None;
		TestFalse(What, ParseAndValidateControlAction(Payload, 7101, 12, false, Parsed, Actual));
		TestEqual(*FString::Printf(TEXT("%s rejection"), What), Actual, Expected);
		TestEqual(*FString::Printf(TEXT("%s leaves default episode"), What), Parsed.EpisodeId, int64(0));
		TestTrue(*FString::Printf(TEXT("%s leaves default controller"), What), Parsed.ControllerId.IsEmpty());
		TestFalse(*FString::Printf(TEXT("%s leaves default visualization"), What), Parsed.bHasVisualization);
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

	auto InvalidVisualization = MakeVisualizationFixture();
	InvalidVisualization->GetObjectField(TEXT("identity"))->SetNumberField(TEXT("episode_id"), 7102.0);
	ExpectRejection(
		TEXT("Visualization identity mismatch"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	InvalidVisualization = MakeVisualizationFixture();
	InvalidVisualization->SetStringField(TEXT("frame"), TEXT("unreal_local_xy_cm"));
	ExpectRejection(
		TEXT("Visualization wrong frame"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	InvalidVisualization = MakeVisualizationFixture();
	InvalidVisualization->GetObjectField(TEXT("identity"))->SetNumberField(
		TEXT("source_observation_sequence"),
		11.0);
	ExpectRejection(
		TEXT("Visualization source observation mismatch"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	auto RepeatedCemVisualization = MakeVisualizationFixture();
	TArray<TSharedPtr<FJsonValue>> RepeatedCemPaths = RepeatedCemVisualization->GetArrayField(TEXT("paths"));
	RepeatedCemPaths[1]->AsObject()->SetStringField(TEXT("role"), TEXT("cem_candidate"));
	RepeatedCemVisualization->SetArrayField(TEXT("paths"), RepeatedCemPaths);
	FControlAction RepeatedCemAction;
	TestTrue(
		TEXT("Repeated CEM candidate roles are admitted"),
		ParseAndValidateControlAction(
			AttachVisualization(ActionBytes, RepeatedCemVisualization),
			7101,
			12,
			false,
			RepeatedCemAction,
			Rejection));
	TestEqual(TEXT("Both repeated CEM candidates survive"), RepeatedCemAction.Visualization.Paths.Num(), 2);

	InvalidVisualization = MakeVisualizationFixture();
	InvalidVisualization->GetObjectField(TEXT("sampling"))->SetNumberField(TEXT("horizon_s"), 0.25);
	ExpectRejection(
		TEXT("Visualization fractional rollout steps"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	InvalidVisualization = MakeVisualizationFixture();
	TArray<TSharedPtr<FJsonValue>> InvalidPaths = InvalidVisualization->GetArrayField(TEXT("paths"));
	InvalidPaths[0]->AsObject()->SetStringField(TEXT("role"), TEXT("selected"));
	InvalidVisualization->SetArrayField(TEXT("paths"), InvalidPaths);
	ExpectRejection(
		TEXT("Visualization duplicate non-CEM role"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	InvalidVisualization = MakeVisualizationFixture();
	InvalidPaths = InvalidVisualization->GetArrayField(TEXT("paths"));
	InvalidPaths[0]->AsObject()->SetStringField(TEXT("role"), TEXT("decorative_guess"));
	InvalidVisualization->SetArrayField(TEXT("paths"), InvalidPaths);
	ExpectRejection(
		TEXT("Visualization unknown role"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	InvalidVisualization = MakeVisualizationFixture();
	InvalidPaths = InvalidVisualization->GetArrayField(TEXT("paths"));
	const TSharedPtr<FJsonValue> PathToDuplicate = InvalidPaths[0];
	InvalidPaths.Pop();
	while (InvalidPaths.Num() <= MaxControlVisualizationPaths)
	{
		InvalidPaths.Add(PathToDuplicate);
	}
	InvalidVisualization->SetArrayField(TEXT("paths"), InvalidPaths);
	ExpectRejection(
		TEXT("Visualization path count above bound"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	InvalidVisualization = MakeVisualizationFixture();
	InvalidPaths = InvalidVisualization->GetArrayField(TEXT("paths"));
	TArray<TSharedPtr<FJsonValue>> InvalidPoints = InvalidPaths[0]->AsObject()->GetArrayField(
		TEXT("points_world_xy_cm"));
	InvalidPoints.Pop();
	InvalidPaths[0]->AsObject()->SetArrayField(TEXT("points_world_xy_cm"), InvalidPoints);
	InvalidVisualization->SetArrayField(TEXT("paths"), InvalidPaths);
	ExpectRejection(
		TEXT("Visualization wrong point count"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	InvalidVisualization = MakeVisualizationFixture();
	InvalidPaths = InvalidVisualization->GetArrayField(TEXT("paths"));
	InvalidPoints = InvalidPaths[0]->AsObject()->GetArrayField(TEXT("points_world_xy_cm"));
	TArray<TSharedPtr<FJsonValue>> OutOfRangePoint;
	OutOfRangePoint.Add(MakeShared<FJsonValueNumber>(10000001.0));
	OutOfRangePoint.Add(MakeShared<FJsonValueNumber>(0.0));
	InvalidPoints[0] = MakeShared<FJsonValueArray>(OutOfRangePoint);
	InvalidPaths[0]->AsObject()->SetArrayField(TEXT("points_world_xy_cm"), InvalidPoints);
	InvalidVisualization->SetArrayField(TEXT("paths"), InvalidPaths);
	ExpectRejection(
		TEXT("Visualization coordinate outside world bound"),
		AttachVisualization(ActionBytes, InvalidVisualization),
		EControlActionRejection::InvalidSchema);

	auto OversizedVisualization = MakeVisualizationFixture();
	TArray<TSharedPtr<FJsonValue>> OversizedPaths;
	for (int32 PathIndex = 0; PathIndex < MaxControlVisualizationPaths - 1; ++PathIndex)
	{
		auto Path = MakeShared<FJsonObject>();
		Path->SetStringField(TEXT("role"), TEXT("cem_candidate"));
		TArray<TSharedPtr<FJsonValue>> Points;
		for (int32 PointIndex = 0; PointIndex < MaxControlVisualizationPointsPerPath; ++PointIndex)
		{
			TArray<TSharedPtr<FJsonValue>> Components;
			Components.Add(MakeShared<FJsonValueNumber>(-999999.123456 + PointIndex));
			Components.Add(MakeShared<FJsonValueNumber>(999999.654321 - PathIndex));
			Points.Add(MakeShared<FJsonValueArray>(Components));
		}
		Path->SetArrayField(TEXT("points_world_xy_cm"), Points);
		OversizedPaths.Add(MakeShared<FJsonValueObject>(Path));
	}
	OversizedVisualization->SetArrayField(TEXT("paths"), OversizedPaths);
	OversizedVisualization->GetObjectField(TEXT("sampling"))->SetNumberField(TEXT("horizon_s"), 1.5);
	OversizedVisualization->GetObjectField(TEXT("sampling"))->SetNumberField(TEXT("timestep_s"), 0.1);
	const TArray<uint8> NestedOversizeOuterValid = AttachVisualization(ActionBytes, OversizedVisualization);
	const int32 NestedVisualizationBytes = CompactJsonUtf8Size(OversizedVisualization);
	TestTrue(
		*FString::Printf(
			TEXT("Nested visualization is %d bytes and exceeds its %d-byte compact cap"),
			NestedVisualizationBytes,
			MaxControlVisualizationBytes),
		NestedVisualizationBytes > MaxControlVisualizationBytes);
	TestTrue(
		*FString::Printf(
			TEXT("Nested-oversize action is %d bytes and respects its %d-byte outer cap"),
			NestedOversizeOuterValid.Num(),
			MaxControlActionBytes),
		NestedOversizeOuterValid.Num() <= MaxControlActionBytes);
	ExpectRejection(
		TEXT("Nested-oversize outer-valid visualization"),
		NestedOversizeOuterValid,
		EControlActionRejection::InvalidSchema);

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
