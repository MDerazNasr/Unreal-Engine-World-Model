#include "MotionWorldControlAction.h"

#include "Containers/StringConv.h"
#include "Dom/JsonObject.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#include <cfloat>
#include <initializer_list>

namespace
{
using MotionWorld::EControlActionRejection;
using MotionWorld::FControlAction;
using MotionWorld::MaxControlActionBytes;
using MotionWorld::MaxControlTrajectorySteps;
using MotionWorld::MaxControlVisualizationBytes;
using MotionWorld::MaxControlVisualizationPaths;
using MotionWorld::MaxControlVisualizationPointsPerPath;
using MotionWorld::MaxSafeJsonInteger;

constexpr double MaxVisualizationAbsCoordinateCm = 10000000.0;
constexpr double MinVisualizationHorizonSeconds = 0.001;
constexpr double MaxVisualizationHorizonSeconds = 10.0;
constexpr double MinVisualizationTimestepSeconds = 0.001;
constexpr double MaxVisualizationTimestepSeconds = 1.0;

bool IsCompactJsonWithinByteLimit(
	const TSharedPtr<FJsonObject>& Object,
	const int32 MaxBytes)
{
	if (!Object.IsValid())
	{
		return false;
	}
	FString CompactJson;
	const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&CompactJson);
	if (!FJsonSerializer::Serialize(Object.ToSharedRef(), Writer))
	{
		return false;
	}
	const FTCHARToUTF8 Utf8(*CompactJson);
	return Utf8.Length() <= MaxBytes;
}

bool IsContinuationByte(const uint8 Byte)
{
	return (Byte & 0xC0) == 0x80;
}

bool IsStrictUtf8(const TConstArrayView<uint8> Bytes)
{
	for (int32 Index = 0; Index < Bytes.Num();)
	{
		const uint8 First = Bytes[Index++];
		if (First <= 0x7F)
		{
			continue;
		}
		if (First >= 0xC2 && First <= 0xDF)
		{
			if (Index >= Bytes.Num() || !IsContinuationByte(Bytes[Index++]))
			{
				return false;
			}
			continue;
		}
		if (First >= 0xE0 && First <= 0xEF)
		{
			if (Index + 1 >= Bytes.Num())
			{
				return false;
			}
			const uint8 Second = Bytes[Index++];
			const uint8 Third = Bytes[Index++];
			const bool bSecondValid = First == 0xE0
				? Second >= 0xA0 && Second <= 0xBF
				: (First == 0xED
					? Second >= 0x80 && Second <= 0x9F
					: IsContinuationByte(Second));
			if (!bSecondValid || !IsContinuationByte(Third))
			{
				return false;
			}
			continue;
		}
		if (First >= 0xF0 && First <= 0xF4)
		{
			if (Index + 2 >= Bytes.Num())
			{
				return false;
			}
			const uint8 Second = Bytes[Index++];
			const uint8 Third = Bytes[Index++];
			const uint8 Fourth = Bytes[Index++];
			const bool bSecondValid = First == 0xF0
				? Second >= 0x90 && Second <= 0xBF
				: (First == 0xF4
					? Second >= 0x80 && Second <= 0x8F
					: IsContinuationByte(Second));
			if (!bSecondValid || !IsContinuationByte(Third) || !IsContinuationByte(Fourth))
			{
				return false;
			}
			continue;
		}
		return false;
	}
	return true;
}

struct FJsonKeyScope
{
	bool bIsObject = false;
	TSet<FString> Keys;
};

bool HasDuplicateJsonKey(const FString& Text, bool& bOutMalformed)
{
	bOutMalformed = false;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
	TArray<FJsonKeyScope> Scopes;
	EJsonNotation Notation;
	while (Reader->ReadNext(Notation))
	{
		if (Notation == EJsonNotation::Error)
		{
			bOutMalformed = true;
			return false;
		}
		const FString Identifier = Reader->GetIdentifier();
		const bool bBeginsValue = Notation == EJsonNotation::ObjectStart
			|| Notation == EJsonNotation::ArrayStart
			|| Notation == EJsonNotation::Boolean
			|| Notation == EJsonNotation::String
			|| Notation == EJsonNotation::Number
			|| Notation == EJsonNotation::Null;
		if (bBeginsValue && !Scopes.IsEmpty() && Scopes.Last().bIsObject)
		{
			if (Identifier.IsEmpty())
			{
				bOutMalformed = true;
				return false;
			}
			if (Scopes.Last().Keys.Contains(Identifier))
			{
				return true;
			}
			Scopes.Last().Keys.Add(Identifier);
		}
		if (Notation == EJsonNotation::ObjectStart || Notation == EJsonNotation::ArrayStart)
		{
			FJsonKeyScope& Scope = Scopes.AddDefaulted_GetRef();
			Scope.bIsObject = Notation == EJsonNotation::ObjectStart;
		}
		else if (Notation == EJsonNotation::ObjectEnd || Notation == EJsonNotation::ArrayEnd)
		{
			if (Scopes.IsEmpty())
			{
				bOutMalformed = true;
				return false;
			}
			Scopes.Pop();
		}
	}
	bOutMalformed = !Reader->GetErrorMessage().IsEmpty() || !Scopes.IsEmpty();
	return false;
}

bool HasExactKeys(
	const TSharedPtr<FJsonObject>& Object,
	const std::initializer_list<const TCHAR*> Expected)
{
	if (!Object.IsValid() || Object->Values.Num() != static_cast<int32>(Expected.size()))
	{
		return false;
	}
	for (const TCHAR* Key : Expected)
	{
		if (!Object->HasField(Key))
		{
			return false;
		}
	}
	return true;
}

bool GetObject(
	const TSharedPtr<FJsonObject>& Parent,
	const TCHAR* Key,
	TSharedPtr<FJsonObject>& OutObject)
{
	const TSharedPtr<FJsonObject>* Value = nullptr;
	if (!Parent.IsValid() || !Parent->TryGetObjectField(Key, Value) || !Value || !Value->IsValid())
	{
		return false;
	}
	OutObject = *Value;
	return true;
}

bool GetFiniteNumber(
	const TSharedPtr<FJsonObject>& Object,
	const TCHAR* Key,
	double& OutValue,
	const double Minimum = -DBL_MAX)
{
	return Object.IsValid()
		&& Object->TryGetNumberField(Key, OutValue)
		&& FMath::IsFinite(OutValue)
		&& OutValue >= Minimum;
}

bool GetSafeInteger(
	const TSharedPtr<FJsonObject>& Object,
	const TCHAR* Key,
	int64& OutValue)
{
	double Number = 0.0;
	if (!GetFiniteNumber(Object, Key, Number, 0.0)
		|| Number > static_cast<double>(MaxSafeJsonInteger)
		|| FMath::TruncToDouble(Number) != Number)
	{
		return false;
	}
	OutValue = static_cast<int64>(Number);
	return true;
}

bool GetBoundedString(
	const TSharedPtr<FJsonObject>& Object,
	const TCHAR* Key,
	FString& OutValue)
{
	if (!Object.IsValid() || !Object->TryGetStringField(Key, OutValue) || OutValue.IsEmpty())
	{
		return false;
	}
	const FTCHARToUTF8 Utf8(*OutValue);
	return Utf8.Length() <= 128;
}

bool GetVector2(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, FVector2D& OutValue)
{
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Object.IsValid() || !Object->TryGetArrayField(Key, Values) || !Values || Values->Num() != 2)
	{
		return false;
	}
	double X = 0.0;
	double Y = 0.0;
	if (!(*Values)[0].IsValid() || !(*Values)[1].IsValid()
		|| !(*Values)[0]->TryGetNumber(X) || !(*Values)[1]->TryGetNumber(Y)
		|| !FMath::IsFinite(X) || !FMath::IsFinite(Y))
	{
		return false;
	}
	OutValue = FVector2D(X, Y);
	return true;
}

bool ParseVisualization(
	const TSharedPtr<FJsonObject>& Object,
	const int64 OuterEpisodeId,
	const int64 OuterSourceObservationSequence,
	FControlAction& OutAction)
{
	if (!HasExactKeys(Object, {
		TEXT("schema"), TEXT("identity"), TEXT("frame"), TEXT("sampling"), TEXT("paths")}))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Schema;
	FString SchemaName;
	int64 SchemaVersion = 0;
	if (!GetObject(Object, TEXT("schema"), Schema)
		|| !HasExactKeys(Schema, {TEXT("name"), TEXT("version")})
		|| !GetBoundedString(Schema, TEXT("name"), SchemaName)
		|| SchemaName != TEXT("motionworld_visualization")
		|| !GetSafeInteger(Schema, TEXT("version"), SchemaVersion)
		|| SchemaVersion != 1)
	{
		return false;
	}

	TSharedPtr<FJsonObject> Identity;
	auto& Result = OutAction.Visualization;
	if (!GetObject(Object, TEXT("identity"), Identity)
		|| !HasExactKeys(Identity, {TEXT("episode_id"), TEXT("source_observation_sequence")})
		|| !GetSafeInteger(Identity, TEXT("episode_id"), Result.EpisodeId)
		|| !GetSafeInteger(
			Identity,
			TEXT("source_observation_sequence"),
			Result.SourceObservationSequence)
		|| Result.EpisodeId != OuterEpisodeId
		|| Result.SourceObservationSequence != OuterSourceObservationSequence)
	{
		return false;
	}

	FString Frame;
	if (!GetBoundedString(Object, TEXT("frame"), Frame)
		|| Frame != TEXT("unreal_world_xy_cm"))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Sampling;
	if (!GetObject(Object, TEXT("sampling"), Sampling)
		|| !HasExactKeys(Sampling, {TEXT("horizon_s"), TEXT("timestep_s")})
		|| !GetFiniteNumber(
			Sampling,
			TEXT("horizon_s"),
			Result.HorizonSeconds,
			MinVisualizationHorizonSeconds)
		|| Result.HorizonSeconds > MaxVisualizationHorizonSeconds
		|| !GetFiniteNumber(
			Sampling,
			TEXT("timestep_s"),
			Result.TimestepSeconds,
			MinVisualizationTimestepSeconds)
		|| Result.TimestepSeconds > MaxVisualizationTimestepSeconds
		|| Result.TimestepSeconds > Result.HorizonSeconds)
	{
		return false;
	}
	const double StepRatio = Result.HorizonSeconds / Result.TimestepSeconds;
	const int32 RolloutSteps = FMath::RoundToInt(StepRatio);
	if (RolloutSteps < 1
		|| RolloutSteps > MaxControlVisualizationPointsPerPath - 1
		|| !FMath::IsNearlyEqual(StepRatio, static_cast<double>(RolloutSteps), 1.e-9))
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* Paths = nullptr;
	if (!Object->TryGetArrayField(TEXT("paths"), Paths)
		|| !Paths
		|| Paths->IsEmpty()
		|| Paths->Num() > MaxControlVisualizationPaths)
	{
		return false;
	}

	TSet<FString> UniqueRoles;
	const int32 ExpectedPointCount = RolloutSteps + 1;
	for (const TSharedPtr<FJsonValue>& PathValue : *Paths)
	{
		const TSharedPtr<FJsonObject>* Path = nullptr;
		FString Role;
		if (!PathValue.IsValid()
			|| !PathValue->TryGetObject(Path)
			|| !Path
			|| !Path->IsValid()
			|| !HasExactKeys(*Path, {TEXT("role"), TEXT("points_world_xy_cm")})
			|| !GetBoundedString(*Path, TEXT("role"), Role))
		{
			return false;
		}
		const bool bKnownRole = Role == TEXT("cem_candidate")
			|| Role == TEXT("selected")
			|| Role == TEXT("branch_forward")
			|| Role == TEXT("branch_left")
			|| Role == TEXT("branch_right")
			|| Role == TEXT("branch_stop")
			|| Role == TEXT("nominal")
			|| Role == TEXT("residual");
		if (!bKnownRole || (Role != TEXT("cem_candidate") && UniqueRoles.Contains(Role)))
		{
			return false;
		}
		UniqueRoles.Add(Role);

		const TArray<TSharedPtr<FJsonValue>>* Points = nullptr;
		if (!(*Path)->TryGetArrayField(TEXT("points_world_xy_cm"), Points)
			|| !Points
			|| Points->Num() != ExpectedPointCount)
		{
			return false;
		}

		auto& OutputPath = Result.Paths.AddDefaulted_GetRef();
		OutputPath.Role = Role;
		for (const TSharedPtr<FJsonValue>& Point : *Points)
		{
			const TArray<TSharedPtr<FJsonValue>>* Components = nullptr;
			double X = 0.0;
			double Y = 0.0;
			if (!Point.IsValid()
				|| !Point->TryGetArray(Components)
				|| !Components
				|| Components->Num() != 2
				|| !(*Components)[0].IsValid()
				|| !(*Components)[1].IsValid()
				|| !(*Components)[0]->TryGetNumber(X)
				|| !(*Components)[1]->TryGetNumber(Y)
				|| !FMath::IsFinite(X)
				|| !FMath::IsFinite(Y)
				|| FMath::Abs(X) > MaxVisualizationAbsCoordinateCm
				|| FMath::Abs(Y) > MaxVisualizationAbsCoordinateCm)
			{
				return false;
			}
			OutputPath.PointsWorldXYCm.Emplace(X, Y);
		}
	}
	return true;
}

bool ParseTelemetry(const TSharedPtr<FJsonObject>& Object, FControlAction& OutAction)
{
	bool bPresent = false;
	if (!Object.IsValid() || !Object->TryGetBoolField(TEXT("is_present"), bPresent))
	{
		return false;
	}
	OutAction.bHasTelemetry = bPresent;
	if (!bPresent)
	{
		return HasExactKeys(Object, {TEXT("is_present")});
	}
	const bool bLegacyOnly = HasExactKeys(Object, {
		TEXT("is_present"),
		TEXT("selected_desired_velocity_trajectory_local_cm_per_s"),
		TEXT("cost_breakdown")});
	const bool bVisualizationOnly = HasExactKeys(Object, {
		TEXT("is_present"),
		TEXT("visualization")});
	const bool bCombined = HasExactKeys(Object, {
			TEXT("is_present"),
			TEXT("selected_desired_velocity_trajectory_local_cm_per_s"),
			TEXT("cost_breakdown"),
			TEXT("visualization")});
	if (!bLegacyOnly && !bVisualizationOnly && !bCombined)
	{
		return false;
	}
	if (bLegacyOnly || bCombined)
	{
		const TArray<TSharedPtr<FJsonValue>>* Trajectory = nullptr;
		if (!Object->TryGetArrayField(
			TEXT("selected_desired_velocity_trajectory_local_cm_per_s"),
			Trajectory)
			|| !Trajectory
			|| Trajectory->IsEmpty()
			|| Trajectory->Num() > MaxControlTrajectorySteps)
		{
			return false;
		}
		for (const TSharedPtr<FJsonValue>& Step : *Trajectory)
		{
			const TArray<TSharedPtr<FJsonValue>>* Components = nullptr;
			if (!Step.IsValid() || !Step->TryGetArray(Components) || !Components || Components->Num() != 2)
			{
				return false;
			}
			double X = 0.0;
			double Y = 0.0;
			if (!(*Components)[0]->TryGetNumber(X) || !(*Components)[1]->TryGetNumber(Y)
				|| !FMath::IsFinite(X) || !FMath::IsFinite(Y))
			{
				return false;
			}
			OutAction.SelectedTrajectoryLocalCmPerSec.Emplace(X, Y);
		}

		TSharedPtr<FJsonObject> Costs;
		if (!GetObject(Object, TEXT("cost_breakdown"), Costs)
			|| !HasExactKeys(Costs, {
				TEXT("terminal_goal_distance_cm"),
				TEXT("collision_indicator"),
				TEXT("clearance_deficit_squared_cm2"),
				TEXT("action_change_squared_cm2_s2"),
				TEXT("action_second_difference_squared_cm2_s2"),
				TEXT("total")}))
		{
			return false;
		}
		auto& Result = OutAction.CostBreakdown;
		if (!GetFiniteNumber(Costs, TEXT("terminal_goal_distance_cm"), Result.TerminalGoalDistanceCm, 0.0)
			|| !GetFiniteNumber(Costs, TEXT("collision_indicator"), Result.CollisionIndicator, 0.0)
			|| (Result.CollisionIndicator != 0.0 && Result.CollisionIndicator != 1.0)
			|| !GetFiniteNumber(Costs, TEXT("clearance_deficit_squared_cm2"), Result.ClearanceDeficitSquaredCm2, 0.0)
			|| !GetFiniteNumber(Costs, TEXT("action_change_squared_cm2_s2"), Result.ActionChangeSquaredCm2PerS2, 0.0)
			|| !GetFiniteNumber(Costs, TEXT("action_second_difference_squared_cm2_s2"), Result.ActionSecondDifferenceSquaredCm2PerS2, 0.0)
			|| !GetFiniteNumber(Costs, TEXT("total"), Result.Total, 0.0))
		{
			return false;
		}
	}
	if (bLegacyOnly)
	{
		return true;
	}
	TSharedPtr<FJsonObject> Visualization;
	if (!GetObject(Object, TEXT("visualization"), Visualization)
		|| !IsCompactJsonWithinByteLimit(Visualization, MaxControlVisualizationBytes)
		|| !ParseVisualization(
			Visualization,
			OutAction.EpisodeId,
			OutAction.SourceObservationSequence,
			OutAction))
	{
		return false;
	}
	OutAction.bHasVisualization = true;
	return true;
}

bool ParseSchema(const TSharedPtr<FJsonObject>& Root, FControlAction& OutAction)
{
	if (!HasExactKeys(Root, {
		TEXT("protocol"), TEXT("identity"), TEXT("command"), TEXT("controller"),
		TEXT("planner"), TEXT("fallback"), TEXT("telemetry")}))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Protocol;
	FString Name;
	FString MessageType;
	int64 Version = 0;
	if (!GetObject(Root, TEXT("protocol"), Protocol)
		|| !HasExactKeys(Protocol, {TEXT("name"), TEXT("version"), TEXT("message_type")})
		|| !GetBoundedString(Protocol, TEXT("name"), Name)
		|| Name != TEXT("motionworld_control")
		|| !GetSafeInteger(Protocol, TEXT("version"), Version)
		|| Version != 1
		|| !GetBoundedString(Protocol, TEXT("message_type"), MessageType)
		|| MessageType != TEXT("action"))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Identity;
	if (!GetObject(Root, TEXT("identity"), Identity)
		|| !HasExactKeys(Identity, {TEXT("episode_id"), TEXT("source_observation_sequence")})
		|| !GetSafeInteger(Identity, TEXT("episode_id"), OutAction.EpisodeId)
		|| !GetSafeInteger(
			Identity,
			TEXT("source_observation_sequence"),
			OutAction.SourceObservationSequence))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Command;
	if (!GetObject(Root, TEXT("command"), Command)
		|| !HasExactKeys(Command, {TEXT("desired_velocity_local_cm_per_s")})
		|| !GetVector2(
			Command,
			TEXT("desired_velocity_local_cm_per_s"),
			OutAction.DesiredVelocityLocalCmPerSec))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Controller;
	if (!GetObject(Root, TEXT("controller"), Controller)
		|| !HasExactKeys(Controller, {TEXT("controller_id"), TEXT("model_id")})
		|| !GetBoundedString(Controller, TEXT("controller_id"), OutAction.ControllerId)
		|| !GetBoundedString(Controller, TEXT("model_id"), OutAction.ModelId)
		|| !(OutAction.ControllerId == TEXT("echo")
			|| OutAction.ControllerId == TEXT("reactive")
			|| OutAction.ControllerId == TEXT("branch_preview")
			|| OutAction.ControllerId == TEXT("nominal_mpc")
			|| OutAction.ControllerId == TEXT("residual_mpc")))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Planner;
	if (!GetObject(Root, TEXT("planner"), Planner)
		|| !HasExactKeys(Planner, {
			TEXT("started_monotonic_us"),
			TEXT("finished_monotonic_us"),
			TEXT("measured_latency_ms")})
		|| !GetSafeInteger(
			Planner,
			TEXT("started_monotonic_us"),
			OutAction.PlannerStartedMonotonicUs)
		|| !GetSafeInteger(
			Planner,
			TEXT("finished_monotonic_us"),
			OutAction.PlannerFinishedMonotonicUs)
		|| !GetFiniteNumber(
			Planner,
			TEXT("measured_latency_ms"),
			OutAction.PlannerMeasuredLatencyMs,
			0.0)
		|| OutAction.PlannerFinishedMonotonicUs < OutAction.PlannerStartedMonotonicUs
		|| !FMath::IsNearlyEqual(
			OutAction.PlannerMeasuredLatencyMs,
			static_cast<double>(OutAction.PlannerFinishedMonotonicUs
				- OutAction.PlannerStartedMonotonicUs) / 1000.0,
			1.e-6))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Fallback;
	if (!GetObject(Root, TEXT("fallback"), Fallback)
		|| !HasExactKeys(Fallback, {TEXT("is_safe_fallback"), TEXT("reason")})
		|| !Fallback->TryGetBoolField(TEXT("is_safe_fallback"), OutAction.bIsSafeFallback)
		|| !GetBoundedString(Fallback, TEXT("reason"), OutAction.FallbackReason))
	{
		return false;
	}
	const bool bKnownReason = OutAction.FallbackReason == TEXT("none")
		|| OutAction.FallbackReason == TEXT("deadline_risk")
		|| OutAction.FallbackReason == TEXT("planner_error")
		|| OutAction.FallbackReason == TEXT("invalid_observation")
		|| OutAction.FallbackReason == TEXT("nonfinite_plan")
		|| OutAction.FallbackReason == TEXT("no_feasible_candidate")
		|| OutAction.FallbackReason == TEXT("service_shutdown");
	if (!bKnownReason
		|| OutAction.bIsSafeFallback != (OutAction.FallbackReason != TEXT("none"))
		|| (OutAction.bIsSafeFallback && !OutAction.DesiredVelocityLocalCmPerSec.IsNearlyZero()))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Telemetry;
	return GetObject(Root, TEXT("telemetry"), Telemetry)
		&& ParseTelemetry(Telemetry, OutAction);
}
} // namespace

namespace MotionWorld
{
bool ParseAndValidateControlAction(
	const TConstArrayView<uint8> Payload,
	const int64 ExpectedEpisodeId,
	const int64 ExpectedObservationSequence,
	const bool bObservationAlreadyAccepted,
	FControlAction& OutAction,
	EControlActionRejection& OutRejection)
{
	OutAction = FControlAction();
	OutRejection = EControlActionRejection::InvalidSchema;
	if (Payload.IsEmpty())
	{
		OutRejection = EControlActionRejection::Empty;
		return false;
	}
	if (Payload.Num() > MaxControlActionBytes)
	{
		OutRejection = EControlActionRejection::Oversized;
		return false;
	}
	if (!IsStrictUtf8(Payload))
	{
		OutRejection = EControlActionRejection::InvalidUtf8;
		return false;
	}

	const FUTF8ToTCHAR Converted(
		reinterpret_cast<const ANSICHAR*>(Payload.GetData()),
		Payload.Num());
	const FString Text(Converted.Length(), Converted.Get());
	bool bMalformed = false;
	if (HasDuplicateJsonKey(Text, bMalformed))
	{
		OutRejection = EControlActionRejection::DuplicateJsonKey;
		return false;
	}
	if (bMalformed)
	{
		OutRejection = EControlActionRejection::InvalidJson;
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutRejection = EControlActionRejection::InvalidJson;
		return false;
	}
	FControlAction Candidate;
	if (!ParseSchema(Root, Candidate)
		|| ExpectedEpisodeId < 0
		|| ExpectedEpisodeId > MaxSafeJsonInteger
		|| ExpectedObservationSequence < 0
		|| ExpectedObservationSequence > MaxSafeJsonInteger)
	{
		OutRejection = EControlActionRejection::InvalidSchema;
		return false;
	}
	if (Candidate.EpisodeId != ExpectedEpisodeId)
	{
		OutRejection = EControlActionRejection::WrongEpisode;
		return false;
	}
	if (Candidate.SourceObservationSequence > ExpectedObservationSequence)
	{
		OutRejection = EControlActionRejection::FutureObservation;
		return false;
	}
	if (Candidate.SourceObservationSequence < ExpectedObservationSequence)
	{
		OutRejection = EControlActionRejection::StaleObservation;
		return false;
	}
	if (bObservationAlreadyAccepted)
	{
		OutRejection = EControlActionRejection::DuplicateObservation;
		return false;
	}
	OutAction = MoveTemp(Candidate);
	OutRejection = EControlActionRejection::None;
	return true;
}

const TCHAR* LexToString(const EControlActionRejection Rejection)
{
	switch (Rejection)
	{
	case EControlActionRejection::None: return TEXT("none");
	case EControlActionRejection::Empty: return TEXT("empty");
	case EControlActionRejection::Oversized: return TEXT("oversized");
	case EControlActionRejection::InvalidUtf8: return TEXT("invalid_utf8");
	case EControlActionRejection::InvalidJson: return TEXT("invalid_json");
	case EControlActionRejection::DuplicateJsonKey: return TEXT("duplicate_json_key");
	case EControlActionRejection::InvalidSchema: return TEXT("invalid_schema");
	case EControlActionRejection::WrongEpisode: return TEXT("wrong_episode");
	case EControlActionRejection::FutureObservation: return TEXT("future_observation");
	case EControlActionRejection::StaleObservation: return TEXT("stale_observation");
	case EControlActionRejection::DuplicateObservation: return TEXT("duplicate_observation");
	default: return TEXT("unknown");
	}
}
} // namespace MotionWorld
