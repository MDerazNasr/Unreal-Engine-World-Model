#include "MotionWorldEpisodeExporter.h"

#include "HAL/FileManager.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "MotionWorldTransitionSample.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonWriter.h"

namespace
{
constexpr int32 SupportedTransitionProtocolVersion = 1;
constexpr int32 MaximumExportedTransitions = 100000;
constexpr double NumericTolerance = 1.e-6;

using FCondensedWriter =
	TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>;

void WriteVector(FCondensedWriter& Writer, const TCHAR* Name, const FVector& Value)
{
	Writer.WriteArrayStart(Name);
	Writer.WriteValue(Value.X);
	Writer.WriteValue(Value.Y);
	Writer.WriteValue(Value.Z);
	Writer.WriteArrayEnd();
}

void WriteVector2D(FCondensedWriter& Writer, const TCHAR* Name, const FVector2D& Value)
{
	Writer.WriteArrayStart(Name);
	Writer.WriteValue(Value.X);
	Writer.WriteValue(Value.Y);
	Writer.WriteArrayEnd();
}

void WriteGateState(
	FCondensedWriter& Writer,
	const TCHAR* Name,
	const FMotionWorldTimedGateState& State)
{
	Writer.WriteObjectStart(Name);
	Writer.WriteValue(TEXT("scenario_time_s"), State.ScenarioTimeSeconds);
	Writer.WriteValue(TEXT("phase_rad"), State.PhaseRadians);
	WriteVector(Writer, TEXT("center_world_cm"), State.CenterWorldCm);
	WriteVector(
		Writer,
		TEXT("velocity_world_cm_per_s"),
		State.VelocityWorldCmPerSec);
	Writer.WriteObjectEnd();
}

void WriteState(
	FCondensedWriter& Writer,
	const TCHAR* Name,
	const FMotionWorldStateSample& State)
{
	Writer.WriteObjectStart(Name);
	Writer.WriteValue(TEXT("protocol_version"), State.ProtocolVersion);
	Writer.WriteValue(TEXT("sample_sequence"), State.SampleSequence);
	Writer.WriteValue(TEXT("mover_step_server_frame"), State.MoverStepServerFrame);
	Writer.WriteValue(TEXT("simulation_time_s"), State.SimulationTimeSeconds);
	Writer.WriteValue(TEXT("step_s"), State.StepSeconds);
	Writer.WriteValue(TEXT("is_resimulation"), State.bIsResimulation);
	Writer.WriteValue(TEXT("is_valid"), State.bIsValid);
	Writer.WriteValue(TEXT("movement_mode"), State.MovementMode.ToString());
	WriteVector(Writer, TEXT("position_world_cm"), State.PositionWorldCm);
	WriteVector(
		Writer,
		TEXT("velocity_world_cm_per_s"),
		State.VelocityWorldCmPerSec);
	WriteVector(
		Writer,
		TEXT("velocity_local_planar_cm_per_s"),
		State.VelocityLocalPlanarCmPerSec);
	Writer.WriteValue(TEXT("facing_yaw_deg"), State.FacingYawDegrees);
	WriteVector2D(Writer, TEXT("facing_unit_world"), State.FacingUnitWorld);
	WriteVector(
		Writer,
		TEXT("angular_velocity_world_deg_per_s"),
		State.AngularVelocityWorldDegPerSec);
	Writer.WriteObjectEnd();
}

FString SerializeHeader(const MotionWorld::FEpisodeExportRequest& Request)
{
	FString Line;
	const TSharedRef<FCondensedWriter> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line);
	Writer->WriteObjectStart();
	Writer->WriteValue(TEXT("record_type"), TEXT("episode_header"));
	Writer->WriteValue(TEXT("schema_name"), TEXT("motionworld_episode"));
	Writer->WriteValue(
		TEXT("schema_version"),
		MotionWorld::EpisodeFileSchemaVersion);
	Writer->WriteValue(TEXT("created_utc"), Request.CreatedUtcIso8601);
	Writer->WriteValue(TEXT("engine_version"), Request.EngineVersion);
	Writer->WriteValue(TEXT("project_name"), Request.ProjectName);
	Writer->WriteValue(TEXT("episode_id"), Request.Stats.EpisodeId);
	Writer->WriteValue(TEXT("state_source"), TEXT("mover_finalized_sync_state"));
	if (Request.TimedGateScenario.bIsPresent)
	{
		const FMotionWorldTimedGateConfig& Config =
			Request.TimedGateScenario.Config;
		Writer->WriteObjectStart(TEXT("scenario"));
		Writer->WriteValue(TEXT("type"), TEXT("timed_gate"));
		Writer->WriteValue(TEXT("scenario_seed"), Config.ScenarioSeed);
		Writer->WriteValue(TEXT("motion_type"), TEXT("sinusoidal_translation"));
		WriteVector(*Writer, TEXT("origin_world_cm"), Config.OriginWorldCm);
		WriteVector(
			*Writer,
			TEXT("motion_axis_world"),
			Config.MotionAxisWorld.GetSafeNormal());
		Writer->WriteValue(TEXT("amplitude_cm"), Config.AmplitudeCm);
		Writer->WriteValue(TEXT("period_s"), Config.PeriodSeconds);
		Writer->WriteValue(
			TEXT("phase_offset_rad"),
			Config.PhaseOffsetRadians);
		WriteVector(*Writer, TEXT("half_extents_cm"), Config.HalfExtentsCm);
		WriteVector(
			*Writer,
			TEXT("crossing_plane_normal_world"),
			Config.CrossingPlaneNormalWorld.GetSafeNormal());
		Writer->WriteValue(TEXT("timeout_s"), Config.TimeoutSeconds);
		Writer->WriteValue(
			TEXT("scenario_start_simulation_time_s"),
			Request.TimedGateScenario.ScenarioStartSimulationTimeSeconds);
		Writer->WriteValue(
			TEXT("obstacle_state_source"),
			TEXT("analytic_absolute_time_schedule"));
		Writer->WriteObjectEnd();
	}
	else
	{
		Writer->WriteNull(TEXT("scenario"));
	}
	Writer->WriteObjectStart(TEXT("conventions"));
	Writer->WriteValue(TEXT("world_frame"), TEXT("unreal_world_x_forward_y_right_z_up"));
	Writer->WriteValue(
		TEXT("local_action_frame"),
		TEXT("previous_state_character_x_forward_y_right"));
	Writer->WriteValue(TEXT("position_unit"), TEXT("centimetres"));
	Writer->WriteValue(TEXT("linear_velocity_unit"), TEXT("centimetres_per_second"));
	Writer->WriteValue(TEXT("angle_unit"), TEXT("degrees"));
	Writer->WriteValue(TEXT("angular_velocity_unit"), TEXT("degrees_per_second"));
	Writer->WriteValue(TEXT("time_unit"), TEXT("seconds"));
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("recorder_stats"));
	Writer->WriteValue(TEXT("observed_state_count"), Request.Stats.ObservedStateCount);
	Writer->WriteValue(
		TEXT("attempted_transition_count"),
		Request.Stats.AttemptedTransitionCount);
	Writer->WriteValue(
		TEXT("recorded_transition_count"),
		Request.Stats.RecordedTransitionCount);
	Writer->WriteValue(
		TEXT("rejected_transition_count"),
		Request.Stats.RejectedTransitionCount);
	Writer->WriteValue(
		TEXT("rejected_seed_state_count"),
		Request.Stats.RejectedSeedStateCount);
	Writer->WriteValue(TEXT("capacity_drop_count"), Request.Stats.CapacityDropCount);
	Writer->WriteObjectEnd();
	Writer->WriteObjectEnd();
	Writer->Close();
	return Line;
}

FString SerializeTransition(
	const MotionWorld::FEpisodeExportRequest& Request,
	const FMotionWorldTransitionSample& Transition,
	const bool bIsLastTransition)
{
	FString Line;
	const TSharedRef<FCondensedWriter> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line);
	Writer->WriteObjectStart();
	Writer->WriteValue(TEXT("record_type"), TEXT("transition"));
	Writer->WriteValue(
		TEXT("schema_version"),
		MotionWorld::EpisodeFileSchemaVersion);
	Writer->WriteValue(TEXT("transition_protocol_version"), Transition.ProtocolVersion);
	Writer->WriteValue(TEXT("episode_id"), Transition.EpisodeId);
	Writer->WriteValue(TEXT("transition_sequence"), Transition.TransitionSequence);
	Writer->WriteValue(TEXT("start_simulation_time_s"), Transition.StartSimulationTimeSeconds);
	Writer->WriteValue(TEXT("end_simulation_time_s"), Transition.EndSimulationTimeSeconds);
	Writer->WriteValue(TEXT("delta_time_s"), Transition.DeltaTimeSeconds);
	WriteState(*Writer, TEXT("previous_state"), Transition.PreviousState);
	Writer->WriteObjectStart(TEXT("applied_action"));
	Writer->WriteValue(TEXT("type"), TEXT("desired_velocity"));
	Writer->WriteValue(TEXT("is_valid"), Transition.AppliedAction.bIsValid);
	Writer->WriteValue(
		TEXT("was_motionworld_automated"),
		Transition.AppliedAction.bWasMotionWorldAutomated);
	WriteVector(
		*Writer,
		TEXT("velocity_world_cm_per_s"),
		Transition.AppliedAction.VelocityWorldCmPerSec);
	WriteVector(
		*Writer,
		TEXT("velocity_local_planar_cm_per_s"),
		Transition.AppliedAction.VelocityLocalPlanarCmPerSec);
	Writer->WriteObjectEnd();
	WriteState(*Writer, TEXT("next_state"), Transition.NextState);
	if (Request.TimedGateScenario.bIsPresent)
	{
		const double StartTime =
			Request.TimedGateScenario.ScenarioStartSimulationTimeSeconds;
		const double PreviousScenarioTime = FMath::Max(
			0.0,
			Transition.PreviousState.SimulationTimeSeconds - StartTime);
		const double NextScenarioTime = FMath::Max(
			0.0,
			Transition.NextState.SimulationTimeSeconds - StartTime);
		const FMotionWorldTimedGateState PreviousGateState =
			MotionWorld::EvaluateTimedGateSchedule(
				Request.TimedGateScenario.Config,
				PreviousScenarioTime);
		const FMotionWorldTimedGateState NextGateState =
			MotionWorld::EvaluateTimedGateSchedule(
				Request.TimedGateScenario.Config,
				NextScenarioTime);
		const EMotionWorldScenarioTerminationReason RowTermination =
			bIsLastTransition
				? Request.TimedGateScenario.TerminationReason
				: EMotionWorldScenarioTerminationReason::None;
		Writer->WriteObjectStart(TEXT("scenario"));
		WriteGateState(*Writer, TEXT("previous_gate_state"), PreviousGateState);
		WriteGateState(*Writer, TEXT("next_gate_state"), NextGateState);
		Writer->WriteValue(
			TEXT("collision_this_step"),
			RowTermination
				== EMotionWorldScenarioTerminationReason::GateCollision);
		Writer->WriteValue(
			TEXT("crossed_success_plane_this_step"),
			RowTermination == EMotionWorldScenarioTerminationReason::Success);
		Writer->WriteValue(
			TEXT("termination_reason"),
			MotionWorld::LexToString(RowTermination));
		Writer->WriteObjectEnd();
	}
	else
	{
		Writer->WriteNull(TEXT("scenario"));
	}
	Writer->WriteObjectEnd();
	Writer->Close();
	return Line;
}

FString SerializeFooter(
	const MotionWorld::FEpisodeExportRequest& Request,
	const int64 FirstTransitionSequence,
	const int64 LastTransitionSequence)
{
	FString Line;
	const TSharedRef<FCondensedWriter> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line);
	Writer->WriteObjectStart();
	Writer->WriteValue(TEXT("record_type"), TEXT("episode_footer"));
	Writer->WriteValue(
		TEXT("schema_version"),
		MotionWorld::EpisodeFileSchemaVersion);
	Writer->WriteValue(TEXT("episode_id"), Request.Stats.EpisodeId);
	Writer->WriteValue(
		TEXT("transition_count"),
		static_cast<int64>(Request.Transitions.Num()));
	Writer->WriteValue(TEXT("first_transition_sequence"), FirstTransitionSequence);
	Writer->WriteValue(TEXT("last_transition_sequence"), LastTransitionSequence);
	Writer->WriteValue(TEXT("complete"), true);
	if (Request.TimedGateScenario.bIsPresent)
	{
		Writer->WriteObjectStart(TEXT("scenario_summary"));
		Writer->WriteValue(
			TEXT("termination_reason"),
			MotionWorld::LexToString(
				Request.TimedGateScenario.TerminationReason));
		Writer->WriteValue(
			TEXT("termination_scenario_time_s"),
			Request.TimedGateScenario.TerminationScenarioTimeSeconds);
		Writer->WriteValue(
			TEXT("collision_count"),
			Request.TimedGateScenario.CollisionCount);
		Writer->WriteObjectEnd();
	}
	else
	{
		Writer->WriteNull(TEXT("scenario_summary"));
	}
	Writer->WriteObjectEnd();
	Writer->Close();
	return Line;
}

bool WriteUtf8Line(FArchive& Archive, const FString& Line)
{
	FTCHARToUTF8 Utf8(*Line);
	Archive.Serialize(const_cast<ANSICHAR*>(Utf8.Get()), Utf8.Length());
	const ANSICHAR Newline = '\n';
	Archive.Serialize(const_cast<ANSICHAR*>(&Newline), 1);
	return !Archive.IsError();
}

bool StatesShareEndpoint(
	const FMotionWorldStateSample& Left,
	const FMotionWorldStateSample& Right)
{
	return Left.SampleSequence == Right.SampleSequence
		&& Left.MoverStepServerFrame == Right.MoverStepServerFrame
		&& FMath::IsNearlyEqual(
			Left.SimulationTimeSeconds,
			Right.SimulationTimeSeconds,
			NumericTolerance);
}

bool IsTransitionReproducible(const FMotionWorldTransitionSample& Transition)
{
	if (!Transition.bIsValid
		|| Transition.RejectionReason
			!= EMotionWorldTransitionRejectionReason::None
		|| Transition.ProtocolVersion != SupportedTransitionProtocolVersion
		|| !Transition.AppliedAction.bIsValid
		|| Transition.AppliedAction.Type
			!= EMotionWorldAppliedActionType::DesiredVelocity)
	{
		return false;
	}

	MotionWorld::FTransitionSampleInputs Inputs;
	Inputs.EpisodeId = Transition.EpisodeId;
	Inputs.TransitionSequence = Transition.TransitionSequence;
	Inputs.PreviousState = Transition.PreviousState;
	Inputs.NextState = Transition.NextState;
	Inputs.bAppliedInputWasVelocity = true;
	Inputs.bWasMotionWorldAutomated =
		Transition.AppliedAction.bWasMotionWorldAutomated;
	Inputs.AppliedVelocityWorldCmPerSec =
		Transition.AppliedAction.VelocityWorldCmPerSec;

	const FMotionWorldTransitionSample Rebuilt =
		MotionWorld::BuildTransitionSample(Inputs);
	return Rebuilt.bIsValid
		&& Rebuilt.AppliedAction.VelocityLocalPlanarCmPerSec.Equals(
			Transition.AppliedAction.VelocityLocalPlanarCmPerSec,
			NumericTolerance)
		&& FMath::IsNearlyEqual(
			Rebuilt.StartSimulationTimeSeconds,
			Transition.StartSimulationTimeSeconds,
			NumericTolerance)
		&& FMath::IsNearlyEqual(
			Rebuilt.EndSimulationTimeSeconds,
			Transition.EndSimulationTimeSeconds,
			NumericTolerance)
		&& FMath::IsNearlyEqual(
			Rebuilt.DeltaTimeSeconds,
			Transition.DeltaTimeSeconds,
			NumericTolerance);
}

bool IsTimedGateMetadataValid(
	const MotionWorld::FTimedGateEpisodeMetadata& Metadata,
	const TConstArrayView<FMotionWorldTransitionSample> Transitions)
{
	if (!Metadata.bIsPresent)
	{
		return true;
	}
	if (!MotionWorld::IsTimedGateConfigValid(Metadata.Config)
		|| !FMath::IsFinite(Metadata.ScenarioStartSimulationTimeSeconds)
		|| !FMath::IsFinite(Metadata.TerminationScenarioTimeSeconds)
		|| Metadata.ScenarioStartSimulationTimeSeconds < 0.0
		|| Metadata.TerminationScenarioTimeSeconds < 0.0
		|| Metadata.CollisionCount < 0)
	{
		return false;
	}
	if (Metadata.TerminationReason
			== EMotionWorldScenarioTerminationReason::InvalidConfiguration
		|| (Metadata.TerminationReason
				== EMotionWorldScenarioTerminationReason::GateCollision
			&& Metadata.CollisionCount < 1))
	{
		return false;
	}
	for (const FMotionWorldTransitionSample& Transition : Transitions)
	{
		const double PreviousTime = Transition.PreviousState.SimulationTimeSeconds
			- Metadata.ScenarioStartSimulationTimeSeconds;
		const double NextTime = Transition.NextState.SimulationTimeSeconds
			- Metadata.ScenarioStartSimulationTimeSeconds;
		if (PreviousTime < -NumericTolerance
			|| NextTime < -NumericTolerance
			|| !MotionWorld::EvaluateTimedGateSchedule(
				Metadata.Config,
				FMath::Max(0.0, PreviousTime)).bIsValid
			|| !MotionWorld::EvaluateTimedGateSchedule(
				Metadata.Config,
				FMath::Max(0.0, NextTime)).bIsValid)
		{
			return false;
		}
	}
	return true;
}
} // namespace

namespace MotionWorld
{
const TCHAR* LexToString(const EEpisodeExportResult Result)
{
	switch (Result)
	{
	case EEpisodeExportResult::Succeeded:
		return TEXT("succeeded");
	case EEpisodeExportResult::InvalidOutputPath:
		return TEXT("invalid_output_path");
	case EEpisodeExportResult::InvalidStats:
		return TEXT("invalid_stats");
	case EEpisodeExportResult::NoTransitions:
		return TEXT("no_transitions");
	case EEpisodeExportResult::InvalidTransition:
		return TEXT("invalid_transition");
	case EEpisodeExportResult::DirectoryCreationFailed:
		return TEXT("directory_creation_failed");
	case EEpisodeExportResult::DestinationExists:
		return TEXT("destination_exists");
	case EEpisodeExportResult::TemporaryFileOpenFailed:
		return TEXT("temporary_file_open_failed");
	case EEpisodeExportResult::WriteFailed:
		return TEXT("write_failed");
	case EEpisodeExportResult::AtomicMoveFailed:
		return TEXT("atomic_move_failed");
	default:
		return TEXT("unknown");
	}
}

FEpisodeExportOutcome ExportEpisodeJsonLines(
	const FEpisodeExportRequest& Request)
{
	FEpisodeExportOutcome Outcome;
	FString OutputFilePath = FPaths::ConvertRelativePathToFull(Request.OutputFilePath);
	FPaths::NormalizeFilename(OutputFilePath);
	Outcome.OutputFilePath = OutputFilePath;

	if (Request.OutputFilePath.IsEmpty()
		|| FPaths::GetExtension(OutputFilePath, true) != TEXT(".jsonl")
		|| FPaths::GetPath(OutputFilePath).IsEmpty())
	{
		Outcome.Result = EEpisodeExportResult::InvalidOutputPath;
		Outcome.Detail = TEXT("output path must have a parent directory and end in .jsonl");
		return Outcome;
	}

	if (Request.Stats.EpisodeId < 0
		|| Request.Stats.RecordedTransitionCount != Request.Transitions.Num()
		|| Request.Stats.AttemptedTransitionCount
			!= Request.Stats.RecordedTransitionCount
				+ Request.Stats.RejectedTransitionCount
				+ Request.Stats.CapacityDropCount
		|| Request.Stats.RejectedSeedStateCount < 0)
	{
		Outcome.Result = EEpisodeExportResult::InvalidStats;
		Outcome.Detail = TEXT("recorder counts or episode identity are inconsistent");
		return Outcome;
	}

	if (Request.Transitions.IsEmpty())
	{
		Outcome.Result = EEpisodeExportResult::NoTransitions;
		Outcome.Detail = TEXT("completed episode contains no accepted transitions");
		return Outcome;
	}
	if (Request.Stats.ObservedStateCount
		< Request.Stats.RecordedTransitionCount + 1)
	{
		Outcome.Result = EEpisodeExportResult::InvalidStats;
		Outcome.Detail = TEXT("too few observed states for the accepted transitions");
		return Outcome;
	}
	if (Request.Transitions.Num() > MaximumExportedTransitions)
	{
		Outcome.Result = EEpisodeExportResult::InvalidStats;
		Outcome.Detail = TEXT("transition count exceeds the bounded exporter limit");
		return Outcome;
	}
	if (!IsTimedGateMetadataValid(
		Request.TimedGateScenario,
		Request.Transitions))
	{
		Outcome.Result = EEpisodeExportResult::InvalidStats;
		Outcome.Detail = TEXT("timed-gate scenario metadata is inconsistent");
		return Outcome;
	}

	int64 PreviousTransitionSequence = -1;
	const FMotionWorldTransitionSample* PreviousTransition = nullptr;
	for (const FMotionWorldTransitionSample& Transition : Request.Transitions)
	{
		if (Transition.EpisodeId != Request.Stats.EpisodeId
			|| Transition.TransitionSequence <= PreviousTransitionSequence
			|| !IsTransitionReproducible(Transition))
		{
			Outcome.Result = EEpisodeExportResult::InvalidTransition;
			Outcome.Detail = FString::Printf(
				TEXT("transition %lld failed export revalidation"),
				Transition.TransitionSequence);
			return Outcome;
		}

		if (PreviousTransition
			&& Transition.TransitionSequence
				== PreviousTransition->TransitionSequence + 1
			&& !StatesShareEndpoint(
				PreviousTransition->NextState,
				Transition.PreviousState))
		{
			Outcome.Result = EEpisodeExportResult::InvalidTransition;
			Outcome.Detail = FString::Printf(
				TEXT("consecutive transition %lld does not share the previous endpoint"),
				Transition.TransitionSequence);
			return Outcome;
		}

		PreviousTransitionSequence = Transition.TransitionSequence;
		PreviousTransition = &Transition;
	}

	IFileManager& FileManager = IFileManager::Get();
	const FString OutputDirectory = FPaths::GetPath(OutputFilePath);
	if (!FileManager.DirectoryExists(*OutputDirectory)
		&& !FileManager.MakeDirectory(*OutputDirectory, true))
	{
		Outcome.Result = EEpisodeExportResult::DirectoryCreationFailed;
		Outcome.Detail = TEXT("could not create output directory");
		return Outcome;
	}
	if (FileManager.FileExists(*OutputFilePath))
	{
		Outcome.Result = EEpisodeExportResult::DestinationExists;
		Outcome.Detail = TEXT("destination already exists and will not be overwritten");
		return Outcome;
	}

	const FString TemporaryFilePath = FString::Printf(
		TEXT("%s.%s.tmp"),
		*OutputFilePath,
		*FGuid::NewGuid().ToString(EGuidFormats::Digits));
	TUniquePtr<FArchive> Archive(
		FileManager.CreateFileWriter(
			*TemporaryFilePath,
			FILEWRITE_NoReplaceExisting));
	if (!Archive)
	{
		Outcome.Result = EEpisodeExportResult::TemporaryFileOpenFailed;
		Outcome.Detail = TEXT("could not open unique temporary file");
		return Outcome;
	}

	bool bWriteSucceeded = WriteUtf8Line(*Archive, SerializeHeader(Request));
	for (int32 TransitionIndex = 0;
		TransitionIndex < Request.Transitions.Num();
		++TransitionIndex)
	{
		const FMotionWorldTransitionSample& Transition =
			Request.Transitions[TransitionIndex];
		bWriteSucceeded = bWriteSucceeded
			&& WriteUtf8Line(
				*Archive,
				SerializeTransition(
					Request,
					Transition,
					TransitionIndex == Request.Transitions.Num() - 1));
		if (!bWriteSucceeded)
		{
			break;
		}
	}
	if (bWriteSucceeded)
	{
		bWriteSucceeded = WriteUtf8Line(
			*Archive,
			SerializeFooter(
				Request,
				Request.Transitions[0].TransitionSequence,
				Request.Transitions.Last().TransitionSequence));
	}
	Archive->Close();
	bWriteSucceeded = bWriteSucceeded && !Archive->IsError();
	Archive.Reset();

	if (!bWriteSucceeded)
	{
		FileManager.Delete(*TemporaryFilePath, false, true, true);
		Outcome.Result = EEpisodeExportResult::WriteFailed;
		Outcome.Detail = TEXT("temporary file write or close failed");
		return Outcome;
	}

	if (!FileManager.Move(
		*OutputFilePath,
		*TemporaryFilePath,
		false,
		false,
		false,
		true))
	{
		FileManager.Delete(*TemporaryFilePath, false, true, true);
		Outcome.Result = EEpisodeExportResult::AtomicMoveFailed;
		Outcome.Detail = TEXT("completed temporary file could not be atomically published");
		return Outcome;
	}

	Outcome.Result = EEpisodeExportResult::Succeeded;
	Outcome.Detail = TEXT("episode file published without replacing an existing destination");
	Outcome.ExportedTransitionCount = Request.Transitions.Num();
	return Outcome;
}
} // namespace MotionWorld
