#if WITH_DEV_AUTOMATION_TESTS

#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "MotionWorldEpisodeExporter.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
FMotionWorldStateSample MakeExporterState(
	const int64 SampleSequence,
	const int32 MoverFrame,
	const double SimulationTimeSeconds,
	const double PositionX)
{
	FMotionWorldStateSample State;
	State.SampleSequence = SampleSequence;
	State.MoverStepServerFrame = MoverFrame;
	State.SimulationTimeSeconds = SimulationTimeSeconds;
	State.StepSeconds = 0.050;
	State.bIsValid = true;
	State.MovementMode = TEXT("Walking");
	State.PositionWorldCm = FVector(PositionX, 0.0, 88.0);
	State.VelocityWorldCmPerSec = FVector(100.0, 0.0, 0.0);
	State.VelocityLocalPlanarCmPerSec = FVector(100.0, 0.0, 0.0);
	State.FacingUnitWorld = FVector2D(1.0, 0.0);
	return State;
}

bool ParseJsonLine(const FString& Line, TSharedPtr<FJsonObject>& OutObject)
{
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Line);
	return FJsonSerializer::Deserialize(Reader, OutObject) && OutObject.IsValid();
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldEpisodeExporterTest,
	"MotionWorld.Episode.AtomicJsonLinesExporter",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldEpisodeExporterTest::RunTest(const FString& Parameters)
{
	MotionWorld::FInMemoryEpisodeRecorder Recorder;
	TestTrue(TEXT("Test episode starts"), Recorder.StartEpisode(42, 4));
	TestEqual(
		TEXT("Initial state seeds"),
		Recorder.ObserveFinalizedStep(
			MakeExporterState(10, 20, 1.000, 0.0),
			true,
			true,
			FVector(100.0, 0.0, 0.0)),
		EMotionWorldRecorderObservationResult::Seeded);
	TestEqual(
		TEXT("First row records"),
		Recorder.ObserveFinalizedStep(
			MakeExporterState(11, 21, 1.050, 5.0),
			true,
			true,
			FVector(100.0, 0.0, 0.0)),
		EMotionWorldRecorderObservationResult::Recorded);
	TestEqual(
		TEXT("Second row records"),
		Recorder.ObserveFinalizedStep(
			MakeExporterState(12, 22, 1.100, 10.0),
			true,
			true,
			FVector(100.0, 0.0, 0.0)),
		EMotionWorldRecorderObservationResult::Recorded);

	const FMotionWorldEpisodeRecorderStats CompletedStats = Recorder.GetStats();
	Recorder.StopEpisode();

	const FString TestDirectory = FPaths::Combine(
		FPaths::AutomationTransientDir(),
		TEXT("MotionWorldEpisodeExporter"));
	IFileManager& FileManager = IFileManager::Get();
	FileManager.DeleteDirectory(*TestDirectory, false, true);
	const FString OutputPath = FPaths::Combine(TestDirectory, TEXT("episode_42.jsonl"));

	MotionWorld::FEpisodeExportRequest Request;
	Request.OutputFilePath = OutputPath;
	Request.CreatedUtcIso8601 = TEXT("2026-08-31T12:00:00.000Z");
	Request.EngineVersion = TEXT("5.8.2-test");
	Request.ProjectName = TEXT("MotionWorldTest");
	Request.Stats = CompletedStats;
	Request.Transitions = Recorder.GetTransitions();

	const MotionWorld::FEpisodeExportOutcome Success =
		MotionWorld::ExportEpisodeJsonLines(Request);
	TestTrue(TEXT("Valid episode export succeeds"), Success.Succeeded());
	TestEqual(TEXT("Two rows were exported"), Success.ExportedTransitionCount, int64(2));
	TestTrue(TEXT("Published destination exists"), FileManager.FileExists(*OutputPath));

	TArray<FString> Lines;
	TestTrue(
		TEXT("UTF-8 JSON Lines file loads"),
		FFileHelper::LoadFileToStringArray(Lines, *OutputPath));
	TestEqual(TEXT("Header, two rows, and footer are present"), Lines.Num(), 4);
	if (Lines.Num() == 4)
	{
		TSharedPtr<FJsonObject> Header;
		TSharedPtr<FJsonObject> FirstTransition;
		TSharedPtr<FJsonObject> Footer;
		TestTrue(TEXT("Header is valid JSON"), ParseJsonLine(Lines[0], Header));
		TestTrue(TEXT("Transition is valid JSON"), ParseJsonLine(Lines[1], FirstTransition));
		TestTrue(TEXT("Footer is valid JSON"), ParseJsonLine(Lines[3], Footer));
		if (Header && FirstTransition && Footer)
		{
			TestEqual(
				TEXT("Header record is typed"),
				Header->GetStringField(TEXT("record_type")),
				FString(TEXT("episode_header")));
			TestEqual(
				TEXT("Header carries episode identity"),
				static_cast<int64>(Header->GetNumberField(TEXT("episode_id"))),
				int64(42));
			TestEqual(
				TEXT("First transition identity is retained"),
				static_cast<int64>(
					FirstTransition->GetNumberField(TEXT("transition_sequence"))),
				int64(0));
			TestTrue(TEXT("Footer marks the file complete"), Footer->GetBoolField(TEXT("complete")));
			TestEqual(
				TEXT("Footer count matches the payload"),
				static_cast<int64>(Footer->GetNumberField(TEXT("transition_count"))),
				int64(2));
		}
	}

	const MotionWorld::FEpisodeExportOutcome NoOverwrite =
		MotionWorld::ExportEpisodeJsonLines(Request);
	TestEqual(
		TEXT("Existing destination is never overwritten"),
		NoOverwrite.Result,
		MotionWorld::EEpisodeExportResult::DestinationExists);

	MotionWorld::FEpisodeExportRequest EmptyRequest = Request;
	EmptyRequest.OutputFilePath = FPaths::Combine(TestDirectory, TEXT("empty.jsonl"));
	EmptyRequest.Stats.RecordedTransitionCount = 0;
	EmptyRequest.Stats.AttemptedTransitionCount = 0;
	EmptyRequest.Stats.ObservedStateCount = 0;
	EmptyRequest.Transitions = TConstArrayView<FMotionWorldTransitionSample>();
	TestEqual(
		TEXT("Empty episode fails explicitly"),
		MotionWorld::ExportEpisodeJsonLines(EmptyRequest).Result,
		MotionWorld::EEpisodeExportResult::NoTransitions);

	MotionWorld::FEpisodeExportRequest BadStatsRequest = Request;
	BadStatsRequest.OutputFilePath = FPaths::Combine(TestDirectory, TEXT("bad_stats.jsonl"));
	++BadStatsRequest.Stats.RecordedTransitionCount;
	TestEqual(
		TEXT("Count mismatch fails before writing"),
		MotionWorld::ExportEpisodeJsonLines(BadStatsRequest).Result,
		MotionWorld::EEpisodeExportResult::InvalidStats);

	TArray<FMotionWorldTransitionSample> CorruptTransitions = Recorder.GetTransitions();
	CorruptTransitions[1].EpisodeId = 43;
	MotionWorld::FEpisodeExportRequest CorruptRequest = Request;
	CorruptRequest.OutputFilePath = FPaths::Combine(TestDirectory, TEXT("corrupt.jsonl"));
	CorruptRequest.Transitions = CorruptTransitions;
	TestEqual(
		TEXT("Mixed episode identity fails before writing"),
		MotionWorld::ExportEpisodeJsonLines(CorruptRequest).Result,
		MotionWorld::EEpisodeExportResult::InvalidTransition);
	TestFalse(
		TEXT("Rejected export leaves no published file"),
		FileManager.FileExists(*CorruptRequest.OutputFilePath));

	FileManager.DeleteDirectory(*TestDirectory, false, true);
	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
