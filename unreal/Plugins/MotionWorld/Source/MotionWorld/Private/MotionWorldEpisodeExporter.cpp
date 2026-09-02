#include "MotionWorldEpisodeExporter.h"

#include "HAL/FileManager.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "MotionWorldTransitionSample.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonWriter.h"

namespace
{
constexpr int32 SupportedTransitionProtocolVersion = 4;
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

const TCHAR* ExternalPerturbationTypeToString(
	const EMotionWorldExternalPerturbationType Type)
{
	return Type == EMotionWorldExternalPerturbationType::AdditiveVelocity
		? TEXT("additive_velocity")
		: TEXT("none");
}

void WriteExternalPerturbation(
	FCondensedWriter& Writer,
	const FMotionWorldExternalPerturbation& Perturbation)
{
	Writer.WriteObjectStart(TEXT("external_perturbation"));
	Writer.WriteValue(TEXT("protocol_version"), Perturbation.ProtocolVersion);
	Writer.WriteValue(TEXT("is_valid"), Perturbation.bIsValid);
	Writer.WriteValue(
		TEXT("type"),
		ExternalPerturbationTypeToString(Perturbation.Type));
	Writer.WriteValue(
		TEXT("was_motionworld_scheduled"),
		Perturbation.bWasMotionWorldScheduled);
	WriteVector(
		Writer,
		TEXT("requested_velocity_delta_world_cm_per_s"),
		Perturbation.RequestedVelocityDeltaWorldCmPerSec);
	Writer.WriteValue(
		TEXT("queued_after_state_sample_sequence"),
		Perturbation.QueuedAfterStateSampleSequence);
	Writer.WriteValue(
		TEXT("queued_after_mover_step_server_frame"),
		Perturbation.QueuedAfterMoverStepServerFrame);
	Writer.WriteObjectEnd();
}

void WriteQuaternion(FCondensedWriter& Writer, const TCHAR* Name, const FQuat& Value)
{
	Writer.WriteArrayStart(Name);
	Writer.WriteValue(Value.X);
	Writer.WriteValue(Value.Y);
	Writer.WriteValue(Value.Z);
	Writer.WriteValue(Value.W);
	Writer.WriteArrayEnd();
}

void WriteSmoothWalkingParameters(
	FCondensedWriter& Writer,
	const TCHAR* Name,
	const FMotionWorldSmoothWalkingParameters& Parameters)
{
	Writer.WriteObjectStart(Name);
	Writer.WriteValue(TEXT("acceleration_cm_per_s2"), Parameters.AccelerationCmPerSecSquared);
	Writer.WriteValue(TEXT("deceleration_cm_per_s2"), Parameters.DecelerationCmPerSecSquared);
	Writer.WriteValue(TEXT("directional_acceleration_factor"), Parameters.DirectionalAccelerationFactor);
	Writer.WriteValue(TEXT("turning_strength"), Parameters.TurningStrength);
	Writer.WriteValue(TEXT("acceleration_smoothing_time_s"), Parameters.AccelerationSmoothingTimeSeconds);
	Writer.WriteValue(TEXT("deceleration_smoothing_time_s"), Parameters.DecelerationSmoothingTimeSeconds);
	Writer.WriteValue(TEXT("acceleration_smoothing_compensation"), Parameters.AccelerationSmoothingCompensation);
	Writer.WriteValue(TEXT("deceleration_smoothing_compensation"), Parameters.DecelerationSmoothingCompensation);
	Writer.WriteValue(TEXT("velocity_deadzone_cm_per_s"), Parameters.VelocityDeadzoneCmPerSec);
	Writer.WriteValue(TEXT("acceleration_deadzone_cm_per_s2"), Parameters.AccelerationDeadzoneCmPerSecSquared);
	Writer.WriteValue(TEXT("outside_influence_smoothing_time_s"), Parameters.OutsideInfluenceSmoothingTimeSeconds);
	Writer.WriteValue(TEXT("facing_smoothing_time_s"), Parameters.FacingSmoothingTimeSeconds);
	Writer.WriteValue(TEXT("smooth_facing_with_double_spring"), Parameters.bSmoothFacingWithDoubleSpring);
	Writer.WriteValue(TEXT("facing_deadzone_deg"), Parameters.FacingDeadzoneDegrees);
	Writer.WriteValue(TEXT("angular_velocity_deadzone_deg_per_s"), Parameters.AngularVelocityDeadzoneDegreesPerSec);
	Writer.WriteObjectEnd();
}

const TCHAR* MaxSpeedSourceToString(const EMotionWorldMaxSpeedSource Source)
{
	switch (Source)
	{
	case EMotionWorldMaxSpeedSource::ModeOverride:
		return TEXT("mode_override");
	case EMotionWorldMaxSpeedSource::CommonLegacySettings:
		return TEXT("common_legacy_settings");
	case EMotionWorldMaxSpeedSource::Unbounded:
		return TEXT("unbounded");
	default:
		return TEXT("unavailable");
	}
}

void WriteInputPreparation(
	FCondensedWriter& Writer,
	const TCHAR* Name,
	const FMotionWorldSimpleWalkingInputPreparation& InputPreparation)
{
	Writer.WriteObjectStart(Name);
	Writer.WriteValue(TEXT("has_max_move_speed"), InputPreparation.bHasMaxMoveSpeed);
	Writer.WriteValue(TEXT("effective_max_speed_cm_per_s"), InputPreparation.EffectiveMaxSpeedCmPerSec);
	Writer.WriteValue(TEXT("max_speed_source"), MaxSpeedSourceToString(InputPreparation.MaxSpeedSource));
	Writer.WriteObjectEnd();
}

void WriteNominalContext(
	FCondensedWriter& Writer,
	const TCHAR* Name,
	const FMotionWorldNominalContextSample& Context)
{
	Writer.WriteObjectStart(Name);
	Writer.WriteValue(TEXT("protocol_version"), Context.ProtocolVersion);
	Writer.WriteValue(TEXT("is_valid"), Context.bIsValid);
	Writer.WriteValue(TEXT("authoritative_state_sample_sequence"), Context.AuthoritativeStateSampleSequence);
	Writer.WriteValue(TEXT("movement_mode_name"), Context.MovementModeName.ToString());
	Writer.WriteValue(TEXT("movement_mode_class"), Context.MovementModeClass.ToString());
	WriteSmoothWalkingParameters(Writer, TEXT("parameters"), Context.Parameters);
	WriteInputPreparation(Writer, TEXT("input_preparation"), Context.InputPreparation);
	Writer.WriteObjectStart(TEXT("internal_state"));
	WriteVector(Writer, TEXT("spring_velocity_world_cm_per_s"), Context.InternalState.SpringVelocityWorldCmPerSec);
	WriteVector(Writer, TEXT("spring_acceleration_world_cm_per_s2"), Context.InternalState.SpringAccelerationWorldCmPerSecSquared);
	WriteVector(Writer, TEXT("intermediate_velocity_world_cm_per_s"), Context.InternalState.IntermediateVelocityWorldCmPerSec);
	WriteQuaternion(Writer, TEXT("intermediate_facing_world_xyzw"), Context.InternalState.IntermediateFacingWorld);
	WriteVector(Writer, TEXT("intermediate_angular_velocity_world_rad_per_s"), Context.InternalState.IntermediateAngularVelocityWorldRadPerSec);
	Writer.WriteObjectEnd();
	Writer.WriteObjectEnd();
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
	Writer->WriteObjectStart(TEXT("nominal_context_contract"));
	Writer->WriteValue(TEXT("protocol_version"), 2);
	Writer->WriteValue(TEXT("source"), TEXT("ue58_smooth_walking_public_reflection"));
	Writer->WriteValue(TEXT("capture_phase"), TEXT("mover_on_post_finalize"));
	Writer->WriteValue(
		TEXT("step_parameter_semantics"),
		TEXT("next_finalized_snapshot_assumed_used_during_completed_step"));
	Writer->WriteValue(TEXT("missing_policy"), TEXT("reject_transition"));
	Writer->WriteValue(TEXT("input_preparation_source"), TEXT("simple_walking_mode_and_shared_settings"));
	Writer->WriteValue(TEXT("orientation_intent_semantics"), TEXT("echoed_world_space_input_with_simple_walking_planar_fallback"));
	Writer->WriteValue(TEXT("future_planner_availability"), TEXT("not_guaranteed_requires_causal_selector"));
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("external_perturbation_contract"));
	Writer->WriteValue(TEXT("protocol_version"), 1);
	Writer->WriteValue(
		TEXT("semantics"),
		TEXT("evaluation_only_event_label_not_model_input"));
	Writer->WriteValue(
		TEXT("application"),
		TEXT("mover_one_tick_additive_velocity"));
	Writer->WriteValue(
		TEXT("alignment"),
		TEXT("queued_after_previous_finalized_state_before_next_state"));
	Writer->WriteValue(TEXT("unit"), TEXT("centimetres_per_second"));
	Writer->WriteObjectEnd();
	if (Request.ExternalPerturbationSchedule.bIsPresent)
	{
		const FMotionWorldExternalPerturbationScheduleConfig& Config =
			Request.ExternalPerturbationSchedule.Config;
		Writer->WriteObjectStart(TEXT("external_perturbation_schedule"));
		Writer->WriteValue(
			TEXT("warmup_duration_s"),
			Config.WarmupDurationSeconds);
		Writer->WriteValue(
			TEXT("post_perturbation_duration_s"),
			Config.PostPerturbationDurationSeconds);
		WriteVector(
			*Writer,
			TEXT("additive_velocity_world_cm_per_s"),
			Config.AdditiveVelocityWorldCmPerSec);
		Writer->WriteValue(
			TEXT("schedule_start_simulation_time_s"),
			Request.ExternalPerturbationSchedule
				.ScheduleStartSimulationTimeSeconds);
		Writer->WriteObjectEnd();
	}
	else
	{
		Writer->WriteNull(TEXT("external_perturbation_schedule"));
	}
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
	Writer->WriteObjectStart(TEXT("nominal_context"));
	WriteNominalContext(
		*Writer,
		TEXT("previous"),
		Transition.PreviousNominalContext);
	WriteSmoothWalkingParameters(
		*Writer,
		TEXT("parameters_observed_for_completed_step"),
		Transition.ParametersObservedForCompletedStep);
	WriteInputPreparation(
		*Writer,
		TEXT("input_preparation_observed_for_completed_step"),
		Transition.InputPreparationObservedForCompletedStep);
	WriteNominalContext(
		*Writer,
		TEXT("next"),
		Transition.NextNominalContext);
	Writer->WriteObjectEnd();
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
	WriteVector(
		*Writer,
		TEXT("orientation_intent_world"),
		Transition.AppliedAction.OrientationIntentWorld);
	Writer->WriteValue(
		TEXT("desired_facing_yaw_deg"),
		Transition.AppliedAction.DesiredFacingYawDegrees);
	Writer->WriteValue(
		TEXT("used_previous_facing_for_zero_orientation_intent"),
		Transition.AppliedAction.bUsedPreviousFacingForZeroOrientationIntent);
	Writer->WriteObjectEnd();
	WriteExternalPerturbation(*Writer, Transition.ExternalPerturbation);
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

bool ParametersEqual(
	const FMotionWorldSmoothWalkingParameters& Left,
	const FMotionWorldSmoothWalkingParameters& Right)
{
	return FMath::IsNearlyEqual(Left.AccelerationCmPerSecSquared, Right.AccelerationCmPerSecSquared, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.DecelerationCmPerSecSquared, Right.DecelerationCmPerSecSquared, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.DirectionalAccelerationFactor, Right.DirectionalAccelerationFactor, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.TurningStrength, Right.TurningStrength, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.AccelerationSmoothingTimeSeconds, Right.AccelerationSmoothingTimeSeconds, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.DecelerationSmoothingTimeSeconds, Right.DecelerationSmoothingTimeSeconds, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.AccelerationSmoothingCompensation, Right.AccelerationSmoothingCompensation, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.DecelerationSmoothingCompensation, Right.DecelerationSmoothingCompensation, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.VelocityDeadzoneCmPerSec, Right.VelocityDeadzoneCmPerSec, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.AccelerationDeadzoneCmPerSecSquared, Right.AccelerationDeadzoneCmPerSecSquared, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.OutsideInfluenceSmoothingTimeSeconds, Right.OutsideInfluenceSmoothingTimeSeconds, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.FacingSmoothingTimeSeconds, Right.FacingSmoothingTimeSeconds, NumericTolerance)
		&& Left.bSmoothFacingWithDoubleSpring == Right.bSmoothFacingWithDoubleSpring
		&& FMath::IsNearlyEqual(Left.FacingDeadzoneDegrees, Right.FacingDeadzoneDegrees, NumericTolerance)
		&& FMath::IsNearlyEqual(Left.AngularVelocityDeadzoneDegreesPerSec, Right.AngularVelocityDeadzoneDegreesPerSec, NumericTolerance);
}

bool InputPreparationEqual(
	const FMotionWorldSimpleWalkingInputPreparation& Left,
	const FMotionWorldSimpleWalkingInputPreparation& Right)
{
	return Left.bHasMaxMoveSpeed == Right.bHasMaxMoveSpeed
		&& FMath::IsNearlyEqual(
			Left.EffectiveMaxSpeedCmPerSec,
			Right.EffectiveMaxSpeedCmPerSec,
			NumericTolerance)
		&& Left.MaxSpeedSource == Right.MaxSpeedSource;
}

bool NominalContextsShareEndpoint(
	const FMotionWorldNominalContextSample& Left,
	const FMotionWorldNominalContextSample& Right)
{
	return Left.ProtocolVersion == Right.ProtocolVersion
		&& Left.bIsValid == Right.bIsValid
		&& Left.AuthoritativeStateSampleSequence == Right.AuthoritativeStateSampleSequence
		&& Left.MovementModeName == Right.MovementModeName
		&& Left.MovementModeClass == Right.MovementModeClass
		&& ParametersEqual(Left.Parameters, Right.Parameters)
		&& InputPreparationEqual(Left.InputPreparation, Right.InputPreparation)
		&& Left.InternalState.SpringVelocityWorldCmPerSec.Equals(Right.InternalState.SpringVelocityWorldCmPerSec, NumericTolerance)
		&& Left.InternalState.SpringAccelerationWorldCmPerSecSquared.Equals(Right.InternalState.SpringAccelerationWorldCmPerSecSquared, NumericTolerance)
		&& Left.InternalState.IntermediateVelocityWorldCmPerSec.Equals(Right.InternalState.IntermediateVelocityWorldCmPerSec, NumericTolerance)
		&& Left.InternalState.IntermediateFacingWorld.Equals(Right.InternalState.IntermediateFacingWorld, NumericTolerance)
		&& Left.InternalState.IntermediateAngularVelocityWorldRadPerSec.Equals(Right.InternalState.IntermediateAngularVelocityWorldRadPerSec, NumericTolerance);
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
	Inputs.PreviousNominalContext = Transition.PreviousNominalContext;
	Inputs.NextNominalContext = Transition.NextNominalContext;
	Inputs.bAppliedInputWasVelocity = true;
	Inputs.bWasMotionWorldAutomated =
		Transition.AppliedAction.bWasMotionWorldAutomated;
	Inputs.AppliedVelocityWorldCmPerSec =
		Transition.AppliedAction.VelocityWorldCmPerSec;
	Inputs.bHasAppliedOrientationIntent = true;
	Inputs.AppliedOrientationIntentWorld =
		Transition.AppliedAction.OrientationIntentWorld;
	Inputs.ExternalPerturbation = Transition.ExternalPerturbation;

	const FMotionWorldTransitionSample Rebuilt =
		MotionWorld::BuildTransitionSample(Inputs);
	return Rebuilt.bIsValid
		&& ParametersEqual(
			Rebuilt.ParametersObservedForCompletedStep,
			Transition.ParametersObservedForCompletedStep)
		&& InputPreparationEqual(
			Rebuilt.InputPreparationObservedForCompletedStep,
			Transition.InputPreparationObservedForCompletedStep)
		&& Rebuilt.AppliedAction.VelocityLocalPlanarCmPerSec.Equals(
			Transition.AppliedAction.VelocityLocalPlanarCmPerSec,
			NumericTolerance)
		&& Rebuilt.AppliedAction.OrientationIntentWorld.Equals(
			Transition.AppliedAction.OrientationIntentWorld,
			NumericTolerance)
		&& FMath::IsNearlyEqual(
			Rebuilt.AppliedAction.DesiredFacingYawDegrees,
			Transition.AppliedAction.DesiredFacingYawDegrees,
			NumericTolerance)
		&& Rebuilt.AppliedAction.bUsedPreviousFacingForZeroOrientationIntent
			== Transition.AppliedAction.bUsedPreviousFacingForZeroOrientationIntent
		&& Rebuilt.ExternalPerturbation.ProtocolVersion
			== Transition.ExternalPerturbation.ProtocolVersion
		&& Rebuilt.ExternalPerturbation.bIsValid
			== Transition.ExternalPerturbation.bIsValid
		&& Rebuilt.ExternalPerturbation.Type
			== Transition.ExternalPerturbation.Type
		&& Rebuilt.ExternalPerturbation.bWasMotionWorldScheduled
			== Transition.ExternalPerturbation.bWasMotionWorldScheduled
		&& Rebuilt.ExternalPerturbation.RequestedVelocityDeltaWorldCmPerSec.Equals(
			Transition.ExternalPerturbation.RequestedVelocityDeltaWorldCmPerSec,
			NumericTolerance)
		&& Rebuilt.ExternalPerturbation.QueuedAfterStateSampleSequence
			== Transition.ExternalPerturbation.QueuedAfterStateSampleSequence
		&& Rebuilt.ExternalPerturbation.QueuedAfterMoverStepServerFrame
			== Transition.ExternalPerturbation.QueuedAfterMoverStepServerFrame
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
	const FMotionWorldTransitionSample& FinalTransition = Transitions.Last();
	const double FinalScenarioTime =
		FinalTransition.NextState.SimulationTimeSeconds
		- Metadata.ScenarioStartSimulationTimeSeconds;
	if (!FMath::IsNearlyEqual(
		Metadata.TerminationScenarioTimeSeconds,
		FinalScenarioTime,
		NumericTolerance)
		|| (Metadata.TerminationReason
			!= EMotionWorldScenarioTerminationReason::GateCollision
			&& Metadata.CollisionCount != 0))
	{
		return false;
	}
	if (Metadata.TerminationReason
		== EMotionWorldScenarioTerminationReason::Timeout
		&& FinalScenarioTime + NumericTolerance < Metadata.Config.TimeoutSeconds)
	{
		return false;
	}
	if (Metadata.TerminationReason
		== EMotionWorldScenarioTerminationReason::Success)
	{
		const FVector Normal =
			Metadata.Config.CrossingPlaneNormalWorld.GetSafeNormal();
		const double PreviousDistance = FVector::DotProduct(
			FinalTransition.PreviousState.PositionWorldCm
				- Metadata.Config.OriginWorldCm,
			Normal);
		const double NextDistance = FVector::DotProduct(
			FinalTransition.NextState.PositionWorldCm
				- Metadata.Config.OriginWorldCm,
			Normal);
		if (PreviousDistance > 0.0 || NextDistance <= 0.0)
		{
			return false;
		}
	}
	return true;
}

bool IsExternalPerturbationMetadataValid(
	const MotionWorld::FExternalPerturbationEpisodeMetadata& Metadata,
	const TConstArrayView<FMotionWorldTransitionSample> Transitions)
{
	int32 PerturbationCount = 0;
	const FMotionWorldTransitionSample* PerturbedTransition = nullptr;
	for (const FMotionWorldTransitionSample& Transition : Transitions)
	{
		if (Transition.ExternalPerturbation.Type
			== EMotionWorldExternalPerturbationType::AdditiveVelocity)
		{
			++PerturbationCount;
			PerturbedTransition = &Transition;
		}
	}

	if (!Metadata.bIsPresent)
	{
		return PerturbationCount == 0;
	}
	if (!MotionWorld::IsExternalPerturbationScheduleConfigValid(Metadata.Config)
		|| !FMath::IsFinite(Metadata.ScheduleStartSimulationTimeSeconds)
		|| Metadata.ScheduleStartSimulationTimeSeconds < 0.0
		|| PerturbationCount != 1
		|| !PerturbedTransition)
	{
		return false;
	}

	const FMotionWorldExternalPerturbation& Perturbation =
		PerturbedTransition->ExternalPerturbation;
	const double QueueElapsedSeconds =
		PerturbedTransition->PreviousState.SimulationTimeSeconds
		- Metadata.ScheduleStartSimulationTimeSeconds;
	const double FinalElapsedSeconds =
		Transitions.Last().NextState.SimulationTimeSeconds
		- Metadata.ScheduleStartSimulationTimeSeconds;
	return Perturbation.bWasMotionWorldScheduled
		&& Perturbation.RequestedVelocityDeltaWorldCmPerSec.Equals(
			Metadata.Config.AdditiveVelocityWorldCmPerSec,
			NumericTolerance)
		&& QueueElapsedSeconds + NumericTolerance
			>= Metadata.Config.WarmupDurationSeconds
		&& FinalElapsedSeconds + NumericTolerance
			>= MotionWorld::GetExternalPerturbationScheduleDurationSeconds(
				Metadata.Config);
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
	if ((Request.TimedGateScenario.bIsPresent
			&& Request.ExternalPerturbationSchedule.bIsPresent)
		|| !IsExternalPerturbationMetadataValid(
			Request.ExternalPerturbationSchedule,
			Request.Transitions))
	{
		Outcome.Result = EEpisodeExportResult::InvalidStats;
		Outcome.Detail =
			TEXT("external-perturbation metadata is inconsistent or conflicts with the timed gate");
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
			&& (!StatesShareEndpoint(
					PreviousTransition->NextState,
					Transition.PreviousState)
				|| !NominalContextsShareEndpoint(
					PreviousTransition->NextNominalContext,
					Transition.PreviousNominalContext)))
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
