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

FMotionWorldNominalContextSample MakeExporterContext(const int64 SampleSequence)
{
	FMotionWorldNominalContextSample Context;
	Context.bIsValid = true;
	Context.AuthoritativeStateSampleSequence = SampleSequence;
	Context.MovementModeName = TEXT("Walking");
	Context.MovementModeClass = TEXT("BP_MovementMode_Walking_C");
	Context.Parameters.AccelerationCmPerSecSquared = 500.0;
	Context.Parameters.DecelerationCmPerSecSquared = 300.0;
	Context.Parameters.DirectionalAccelerationFactor = 1.0;
	Context.Parameters.TurningStrength = 8.0;
	Context.Parameters.AccelerationSmoothingTimeSeconds = 0.1;
	Context.Parameters.DecelerationSmoothingTimeSeconds = 0.1;
	Context.Parameters.VelocityDeadzoneCmPerSec = 0.01;
	Context.Parameters.AccelerationDeadzoneCmPerSecSquared = 0.001;
	Context.Parameters.OutsideInfluenceSmoothingTimeSeconds = 0.05;
	Context.Parameters.FacingSmoothingTimeSeconds = 0.2;
	Context.Parameters.FacingDeadzoneDegrees = 0.1;
	Context.Parameters.AngularVelocityDeadzoneDegreesPerSec = 0.01;
	Context.InternalState.SpringVelocityWorldCmPerSec =
		FVector(static_cast<double>(SampleSequence), 0.0, 0.0);
	return Context;
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
			MakeExporterContext(10),
			true,
			true,
			FVector(100.0, 0.0, 0.0)),
		EMotionWorldRecorderObservationResult::Seeded);
	TestEqual(
		TEXT("First row records"),
		Recorder.ObserveFinalizedStep(
			MakeExporterState(11, 21, 1.050, 5.0),
			MakeExporterContext(11),
			true,
			true,
			FVector(100.0, 0.0, 0.0)),
		EMotionWorldRecorderObservationResult::Recorded);
	TestEqual(
		TEXT("Second row records"),
		Recorder.ObserveFinalizedStep(
			MakeExporterState(12, 22, 1.100, 10.0),
			MakeExporterContext(12),
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
				TEXT("Header declares schema version three"),
				static_cast<int32>(Header->GetNumberField(TEXT("schema_version"))),
				3);
			TestEqual(
				TEXT("Context source contract is explicit"),
				Header->GetObjectField(TEXT("nominal_context_contract"))->GetStringField(TEXT("source")),
				FString(TEXT("ue58_smooth_walking_public_reflection")));
			TestEqual(
				TEXT("First transition identity is retained"),
				static_cast<int64>(
					FirstTransition->GetNumberField(TEXT("transition_sequence"))),
				int64(0));
			TestEqual(
				TEXT("Transition carries aligned previous hidden context"),
				static_cast<int64>(FirstTransition->GetObjectField(TEXT("nominal_context"))->GetObjectField(TEXT("previous"))->GetNumberField(TEXT("authoritative_state_sample_sequence"))),
				int64(10));
			TestEqual(
				TEXT("Completed-step acceleration is serialized"),
				FirstTransition->GetObjectField(TEXT("nominal_context"))->GetObjectField(TEXT("parameters_observed_for_completed_step"))->GetNumberField(TEXT("acceleration_cm_per_s2")),
				500.0);
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

	MotionWorld::FEpisodeExportRequest ScenarioRequest = Request;
	ScenarioRequest.OutputFilePath =
		FPaths::Combine(TestDirectory, TEXT("episode_42_scenario.jsonl"));
	ScenarioRequest.TimedGateScenario.bIsPresent = true;
	ScenarioRequest.TimedGateScenario.Config.ScenarioSeed = 1901;
	ScenarioRequest.TimedGateScenario.Config.OriginWorldCm =
		FVector(5.0, 0.0, 88.0);
	ScenarioRequest.TimedGateScenario.Config.MotionAxisWorld = FVector::RightVector;
	ScenarioRequest.TimedGateScenario.Config.AmplitudeCm = 100.0;
	ScenarioRequest.TimedGateScenario.Config.PeriodSeconds = 4.0;
	ScenarioRequest.TimedGateScenario.Config.HalfExtentsCm =
		FVector(20.0, 40.0, 90.0);
	ScenarioRequest.TimedGateScenario.Config.CrossingPlaneNormalWorld =
		FVector::ForwardVector;
	ScenarioRequest.TimedGateScenario.Config.TimeoutSeconds = 8.0;
	ScenarioRequest.TimedGateScenario.ScenarioStartSimulationTimeSeconds = 1.0;
	ScenarioRequest.TimedGateScenario.TerminationReason =
		EMotionWorldScenarioTerminationReason::Success;
	ScenarioRequest.TimedGateScenario.TerminationScenarioTimeSeconds = 0.1;
	const MotionWorld::FEpisodeExportOutcome ScenarioSuccess =
		MotionWorld::ExportEpisodeJsonLines(ScenarioRequest);
	TestTrue(TEXT("Timed-gate episode export succeeds"), ScenarioSuccess.Succeeded());
	TArray<FString> ScenarioLines;
	TestTrue(
		TEXT("Timed-gate JSON Lines file loads"),
		FFileHelper::LoadFileToStringArray(
			ScenarioLines,
			*ScenarioRequest.OutputFilePath));
	if (ScenarioLines.Num() == 4)
	{
		TSharedPtr<FJsonObject> ScenarioHeader;
		TSharedPtr<FJsonObject> FinalTransition;
		TSharedPtr<FJsonObject> ScenarioFooter;
		TestTrue(TEXT("Scenario header parses"), ParseJsonLine(ScenarioLines[0], ScenarioHeader));
		TestTrue(TEXT("Scenario transition parses"), ParseJsonLine(ScenarioLines[2], FinalTransition));
		TestTrue(TEXT("Scenario footer parses"), ParseJsonLine(ScenarioLines[3], ScenarioFooter));
		if (ScenarioHeader && FinalTransition && ScenarioFooter)
		{
			TestEqual(
				TEXT("Scenario seed is persisted"),
				static_cast<int64>(ScenarioHeader->GetObjectField(TEXT("scenario"))->GetNumberField(TEXT("scenario_seed"))),
				int64(1901));
			TestEqual(
				TEXT("Terminal row records success"),
				FinalTransition->GetObjectField(TEXT("scenario"))->GetStringField(TEXT("termination_reason")),
				FString(TEXT("success")));
			TestEqual(
				TEXT("Footer scenario summary records success"),
				ScenarioFooter->GetObjectField(TEXT("scenario_summary"))->GetStringField(TEXT("termination_reason")),
				FString(TEXT("success")));
		}
	}

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
