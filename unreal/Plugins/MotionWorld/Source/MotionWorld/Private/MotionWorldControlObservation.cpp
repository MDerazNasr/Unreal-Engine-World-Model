#include "MotionWorldControlObservation.h"

#include "Containers/StringConv.h"
#include "MotionWorldControlAction.h"
#include "MotionWorldUdpTransport.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonWriter.h"

namespace
{
using FCondensedWriter =
	TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>;

bool IsFiniteVector(const FVector& Value)
{
	return FMath::IsFinite(Value.X)
		&& FMath::IsFinite(Value.Y)
		&& FMath::IsFinite(Value.Z);
}

bool IsFiniteQuaternion(const FQuat& Value)
{
	return FMath::IsFinite(Value.X)
		&& FMath::IsFinite(Value.Y)
		&& FMath::IsFinite(Value.Z)
		&& FMath::IsFinite(Value.W);
}

bool IsBoundedText(const FString& Value)
{
	return !Value.IsEmpty() && FTCHARToUTF8(*Value).Length() <= 128;
}

bool IsSupportedController(const FString& Value)
{
	return Value == TEXT("echo")
		|| Value == TEXT("reactive")
		|| Value == TEXT("nominal_mpc")
		|| Value == TEXT("residual_mpc");
}

const TCHAR* MaxSpeedSourceToProtocolString(
	const EMotionWorldMaxSpeedSource Source)
{
	switch (Source)
	{
	case EMotionWorldMaxSpeedSource::ModeOverride:
		return TEXT("mode_override");
	case EMotionWorldMaxSpeedSource::CommonLegacySettings:
		return TEXT("shared_settings");
	default:
		return nullptr;
	}
}

void WriteVector(FCondensedWriter& Writer, const TCHAR* Name, const FVector& Value)
{
	Writer.WriteArrayStart(Name);
	Writer.WriteValue(Value.X);
	Writer.WriteValue(Value.Y);
	Writer.WriteValue(Value.Z);
	Writer.WriteArrayEnd();
}

void WriteVector2(FCondensedWriter& Writer, const TCHAR* Name, const FVector2D& Value)
{
	Writer.WriteArrayStart(Name);
	Writer.WriteValue(Value.X);
	Writer.WriteValue(Value.Y);
	Writer.WriteArrayEnd();
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
} // namespace

namespace MotionWorld
{
bool SerializeControlObservation(
	const FControlObservation& Observation,
	TArray<uint8>& OutPayload,
	FString& OutFailureReason)
{
	OutPayload.Reset();
	OutFailureReason.Reset();
	const FMotionWorldStateSample& State = Observation.State;
	const FMotionWorldNominalContextSample& Context = Observation.NominalContext;
	const FMotionWorldSmoothWalkingParameters& Parameters = Context.Parameters;
	const FMotionWorldSmoothWalkingInternalState& Internal = Context.InternalState;
	const TCHAR* MaxSpeedSource =
		MaxSpeedSourceToProtocolString(Context.InputPreparation.MaxSpeedSource);

	const bool bIdentityValid = Observation.EpisodeId >= 0
		&& Observation.EpisodeId <= MaxSafeJsonInteger
		&& Observation.ObservationSequence >= 0
		&& Observation.ObservationSequence <= MaxSafeJsonInteger
		&& State.SampleSequence >= 0
		&& State.SampleSequence <= MaxSafeJsonInteger;
	const bool bPreviousValid = Observation.ObservationSequence == 0
		? !Observation.bHasPreviousAction
		: Observation.bHasPreviousAction
			&& Observation.PreviousActionSourceObservationSequence >= 0
			&& Observation.PreviousActionSourceObservationSequence
				< Observation.ObservationSequence
			&& FMath::IsFinite(Observation.PreviousAppliedVelocityLocalCmPerSec.X)
			&& FMath::IsFinite(Observation.PreviousAppliedVelocityLocalCmPerSec.Y);
	const bool bStateFinite = FMath::IsFinite(State.SimulationTimeSeconds)
		&& State.SimulationTimeSeconds >= 0.0
		&& IsFiniteVector(State.PositionWorldCm)
		&& IsFiniteVector(State.VelocityWorldCmPerSec)
		&& IsFiniteVector(State.VelocityLocalPlanarCmPerSec)
		&& FMath::IsFinite(State.FacingYawDegrees)
		&& State.FacingYawDegrees >= -180.0
		&& State.FacingYawDegrees <= 180.0
		&& FMath::IsFinite(State.FacingUnitWorld.X)
		&& FMath::IsFinite(State.FacingUnitWorld.Y)
		&& IsFiniteVector(State.AngularVelocityWorldDegPerSec);
	const bool bContextAligned = Context.bIsValid
		&& IsNominalContextSampleValid(Context)
		&& Context.AuthoritativeStateSampleSequence == State.SampleSequence
		&& Context.MovementModeName == State.MovementMode
		&& Context.InputPreparation.bHasMaxMoveSpeed
		&& MaxSpeedSource != nullptr
		&& IsFiniteQuaternion(Internal.IntermediateFacingWorld);
	if (!bIdentityValid || !bPreviousValid || !State.bIsValid
		|| State.bIsResimulation || !bStateFinite || !bContextAligned
		|| !IsSupportedController(Observation.ControllerMode)
		|| State.MovementMode.IsNone()
		|| !IsBoundedText(State.MovementMode.ToString())
		|| !IsBoundedText(Context.MovementModeClass.ToString())
		|| !IsBoundedText(Observation.ScenarioId)
		|| Observation.ScenarioSeed < 0
		|| Observation.ScenarioSeed > MaxSafeJsonInteger
		|| !IsBoundedText(Observation.ResetId))
	{
		OutFailureReason = TEXT("invalid_or_unaligned_observation_fields");
		return false;
	}

	FString Json;
	const TSharedRef<FCondensedWriter> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Json);
	Writer->WriteObjectStart();
	Writer->WriteObjectStart(TEXT("protocol"));
	Writer->WriteValue(TEXT("name"), TEXT("motionworld_control"));
	Writer->WriteValue(TEXT("version"), 1);
	Writer->WriteValue(TEXT("message_type"), TEXT("observation"));
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("identity"));
	Writer->WriteValue(TEXT("episode_id"), Observation.EpisodeId);
	Writer->WriteValue(TEXT("observation_sequence"), Observation.ObservationSequence);
	Writer->WriteValue(TEXT("state_sample_sequence"), State.SampleSequence);
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("timing"));
	Writer->WriteValue(TEXT("simulation_time_s"), State.SimulationTimeSeconds);
	Writer->WriteValue(TEXT("control_interval_ms"), 100);
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("source"));
	Writer->WriteValue(TEXT("controller_mode"), Observation.ControllerMode);
	Writer->WriteValue(TEXT("authoritative_state_source"), TEXT("mover_on_post_finalize"));
	Writer->WriteValue(TEXT("movement_mode"), State.MovementMode.ToString());
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("validity"));
	Writer->WriteValue(TEXT("authoritative_state_valid"), true);
	Writer->WriteValue(TEXT("nominal_context_valid"), true);
	Writer->WriteValue(TEXT("reset_verified"), true);
	Writer->WriteValue(TEXT("is_resimulation"), false);
	Writer->WriteValue(TEXT("target_present"), false);
	Writer->WriteValue(TEXT("timed_gate_present"), false);
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("state"));
	WriteVector(*Writer, TEXT("position_world_cm"), State.PositionWorldCm);
	WriteVector(*Writer, TEXT("velocity_world_cm_per_s"), State.VelocityWorldCmPerSec);
	WriteVector2(*Writer, TEXT("velocity_local_planar_cm_per_s"),
		FVector2D(State.VelocityLocalPlanarCmPerSec.X, State.VelocityLocalPlanarCmPerSec.Y));
	Writer->WriteValue(TEXT("facing_yaw_deg"), State.FacingYawDegrees);
	WriteVector2(*Writer, TEXT("facing_unit_world"), State.FacingUnitWorld);
	WriteVector(*Writer, TEXT("angular_velocity_world_deg_per_s"), State.AngularVelocityWorldDegPerSec);
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("nominal_context"));
	Writer->WriteValue(TEXT("authoritative_state_sample_sequence"), Context.AuthoritativeStateSampleSequence);
	Writer->WriteValue(TEXT("movement_mode_class"), Context.MovementModeClass.ToString());
	Writer->WriteObjectStart(TEXT("parameters"));
	Writer->WriteValue(TEXT("acceleration_cm_per_s2"), Parameters.AccelerationCmPerSecSquared);
	Writer->WriteValue(TEXT("deceleration_cm_per_s2"), Parameters.DecelerationCmPerSecSquared);
	Writer->WriteValue(TEXT("directional_acceleration_factor"), Parameters.DirectionalAccelerationFactor);
	Writer->WriteValue(TEXT("turning_strength_per_s"), Parameters.TurningStrength);
	Writer->WriteValue(TEXT("acceleration_smoothing_time_s"), Parameters.AccelerationSmoothingTimeSeconds);
	Writer->WriteValue(TEXT("deceleration_smoothing_time_s"), Parameters.DecelerationSmoothingTimeSeconds);
	Writer->WriteValue(TEXT("acceleration_smoothing_compensation"), Parameters.AccelerationSmoothingCompensation);
	Writer->WriteValue(TEXT("deceleration_smoothing_compensation"), Parameters.DecelerationSmoothingCompensation);
	Writer->WriteValue(TEXT("velocity_deadzone_cm_per_s"), Parameters.VelocityDeadzoneCmPerSec);
	Writer->WriteValue(TEXT("acceleration_deadzone_cm_per_s2"), Parameters.AccelerationDeadzoneCmPerSecSquared);
	Writer->WriteValue(TEXT("outside_influence_smoothing_time_s"), Parameters.OutsideInfluenceSmoothingTimeSeconds);
	Writer->WriteValue(TEXT("facing_smoothing_time_s"), Parameters.FacingSmoothingTimeSeconds);
	Writer->WriteValue(TEXT("smooth_facing_with_double_spring"), Parameters.bSmoothFacingWithDoubleSpring);
	Writer->WriteValue(TEXT("facing_deadzone_deg"), Parameters.FacingDeadzoneDegrees);
	Writer->WriteValue(TEXT("angular_velocity_deadzone_deg_per_s"), Parameters.AngularVelocityDeadzoneDegreesPerSec);
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("input_preparation"));
	Writer->WriteValue(TEXT("has_max_speed"), true);
	Writer->WriteValue(TEXT("effective_max_speed_cm_per_s"), Context.InputPreparation.EffectiveMaxSpeedCmPerSec);
	Writer->WriteValue(TEXT("max_speed_source"), MaxSpeedSource);
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("internal_state"));
	WriteVector(*Writer, TEXT("spring_velocity_world_cm_per_s"), Internal.SpringVelocityWorldCmPerSec);
	WriteVector(*Writer, TEXT("spring_acceleration_world_cm_per_s2"), Internal.SpringAccelerationWorldCmPerSecSquared);
	WriteVector(*Writer, TEXT("intermediate_velocity_world_cm_per_s"), Internal.IntermediateVelocityWorldCmPerSec);
	WriteQuaternion(*Writer, TEXT("intermediate_facing_world_xyzw"), Internal.IntermediateFacingWorld);
	WriteVector(*Writer, TEXT("intermediate_angular_velocity_world_rad_per_s"), Internal.IntermediateAngularVelocityWorldRadPerSec);
	Writer->WriteObjectEnd();
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("previous_action"));
	Writer->WriteValue(TEXT("is_present"), Observation.bHasPreviousAction);
	if (Observation.bHasPreviousAction)
	{
		Writer->WriteValue(TEXT("source_observation_sequence"), Observation.PreviousActionSourceObservationSequence);
		WriteVector2(*Writer, TEXT("applied_local_velocity_cm_per_s"), Observation.PreviousAppliedVelocityLocalCmPerSec);
	}
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("planner_context"));
	Writer->WriteObjectStart(TEXT("target"));
	Writer->WriteValue(TEXT("is_present"), false);
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("timed_gate"));
	Writer->WriteValue(TEXT("is_present"), false);
	Writer->WriteObjectEnd();
	Writer->WriteObjectEnd();
	Writer->WriteObjectStart(TEXT("scenario"));
	Writer->WriteValue(TEXT("scenario_id"), Observation.ScenarioId);
	Writer->WriteValue(TEXT("scenario_seed"), Observation.ScenarioSeed);
	Writer->WriteValue(TEXT("reset_id"), Observation.ResetId);
	Writer->WriteValue(TEXT("is_terminal"), false);
	Writer->WriteValue(TEXT("termination_reason"), TEXT("none"));
	Writer->WriteObjectEnd();
	Writer->WriteObjectEnd();
	if (!Writer->Close())
	{
		OutFailureReason = TEXT("json_writer_failed");
		return false;
	}

	const FTCHARToUTF8 Utf8(*Json);
	if (Utf8.Length() <= 0 || Utf8.Length() > MaxObservationDatagramBytes)
	{
		OutFailureReason = TEXT("serialized_observation_size_invalid");
		return false;
	}
	OutPayload.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
	return true;
}
} // namespace MotionWorld
