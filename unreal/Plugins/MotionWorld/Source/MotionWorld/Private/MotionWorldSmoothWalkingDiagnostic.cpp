#include "MotionWorldSmoothWalkingDiagnostic.h"

#include "DefaultMovementSet/Modes/SmoothWalkingMode.h"
#include "MovementMode.h"
#include "UObject/UnrealType.h"

namespace
{
	constexpr int32 ParameterCount = 14;

	bool IsFiniteQuat(const FQuat& Value)
	{
		return FMath::IsFinite(Value.X)
			&& FMath::IsFinite(Value.Y)
			&& FMath::IsFinite(Value.Z)
			&& FMath::IsFinite(Value.W);
	}

	bool ReadFloat(const UObject* Object, const FName Name, double& OutValue)
	{
		const FFloatProperty* Property = FindFProperty<FFloatProperty>(Object->GetClass(), Name);
		if (!Property)
		{
			return false;
		}
		OutValue = static_cast<double>(Property->GetPropertyValue_InContainer(Object));
		return FMath::IsFinite(OutValue);
	}

	bool ReadBool(const UObject* Object, const FName Name, bool& OutValue)
	{
		const FBoolProperty* Property = FindFProperty<FBoolProperty>(Object->GetClass(), Name);
		if (!Property)
		{
			return false;
		}
		OutValue = Property->GetPropertyValue_InContainer(Object);
		return true;
	}

	template <typename ValueType>
	bool ReadStructValue(
		const UScriptStruct* ContainerType,
		const void* Container,
		const FName Name,
		const UScriptStruct* ExpectedType,
		ValueType& OutValue)
	{
		const FStructProperty* Property = FindFProperty<FStructProperty>(ContainerType, Name);
		if (!Property || Property->Struct != ExpectedType)
		{
			return false;
		}
		OutValue = *Property->ContainerPtrToValuePtr<ValueType>(Container);
		return true;
	}
}

bool MotionWorld::ReadSmoothWalkingParameters(
	const UBaseMovementMode* MovementMode,
	FSmoothWalkingDiagnosticInputs& OutInputs,
	FName& OutFailureReason)
{
	OutFailureReason = NAME_None;
	OutInputs.bHasParameters = false;
	OutInputs.Parameters.Reset();
	OutInputs.MovementModeClass = NAME_None;
	if (!IsValid(MovementMode) || !MovementMode->IsA<USmoothWalkingMode>())
	{
		OutFailureReason = TEXT("active_mode_is_not_smooth_walking");
		return false;
	}

	static const FName FloatNames[] = {
		TEXT("Acceleration"),
		TEXT("Deceleration"),
		TEXT("DirectionalAccelerationFactor"),
		TEXT("TurningStrength"),
		TEXT("AccelerationSmoothingTime"),
		TEXT("DecelerationSmoothingTime"),
		TEXT("AccelerationSmoothingCompensation"),
		TEXT("DecelerationSmoothingCompensation"),
		TEXT("VelocityDeadzoneThreshold"),
		TEXT("AccelerationDeadzoneThreshold"),
		TEXT("OutsideInfluenceSmoothingTime"),
		TEXT("FacingSmoothingTime"),
		TEXT("FacingDeadzoneThreshold"),
		TEXT("AngularVelocityDeadzoneThreshold")
	};
	static_assert(UE_ARRAY_COUNT(FloatNames) == ParameterCount);

	OutInputs.Parameters.SetNumUninitialized(ParameterCount);
	for (int32 Index = 0; Index < ParameterCount; ++Index)
	{
		if (!ReadFloat(MovementMode, FloatNames[Index], OutInputs.Parameters[Index]))
		{
			OutInputs.Parameters.Reset();
			OutFailureReason = TEXT("missing_or_invalid_float_parameter");
			return false;
		}
	}
	if (!ReadBool(
		MovementMode,
		TEXT("bSmoothFacingWithDoubleSpring"),
		OutInputs.bSmoothFacingWithDoubleSpring))
	{
		OutInputs.Parameters.Reset();
		OutFailureReason = TEXT("missing_double_spring_parameter");
		return false;
	}
	OutInputs.MovementModeClass = MovementMode->GetClass()->GetFName();
	OutInputs.bHasParameters = true;
	return true;
}

bool MotionWorld::ReadSmoothWalkingSpringState(
	const FMoverDataCollection& SyncStateCollection,
	FSmoothWalkingDiagnosticInputs& OutInputs,
	FName& OutFailureReason)
{
	OutFailureReason = NAME_None;
	OutInputs.bHasSpringState = false;
	const FMoverDataStructBase* SmoothState = nullptr;
	const UScriptStruct* SmoothStateType = nullptr;
	for (const TSharedPtr<FMoverDataStructBase>& Entry : SyncStateCollection.GetDataArray())
	{
		if (Entry.IsValid()
			&& Entry->GetScriptStruct()
			&& Entry->GetScriptStruct()->GetFName() == TEXT("SmoothWalkingState"))
		{
			SmoothState = Entry.Get();
			SmoothStateType = Entry->GetScriptStruct();
			break;
		}
	}
	if (!SmoothState || !SmoothStateType)
	{
		OutFailureReason = TEXT("smooth_walking_state_not_found");
		return false;
	}

	const bool bReadAll =
		ReadStructValue(SmoothStateType, SmoothState, TEXT("SpringVelocity"), TBaseStructure<FVector>::Get(), OutInputs.SpringVelocity)
		&& ReadStructValue(SmoothStateType, SmoothState, TEXT("SpringAcceleration"), TBaseStructure<FVector>::Get(), OutInputs.SpringAcceleration)
		&& ReadStructValue(SmoothStateType, SmoothState, TEXT("IntermediateVelocity"), TBaseStructure<FVector>::Get(), OutInputs.IntermediateVelocity)
		&& ReadStructValue(SmoothStateType, SmoothState, TEXT("IntermediateFacing"), TBaseStructure<FQuat>::Get(), OutInputs.IntermediateFacing)
		&& ReadStructValue(SmoothStateType, SmoothState, TEXT("IntermediateAngularVelocity"), TBaseStructure<FVector>::Get(), OutInputs.IntermediateAngularVelocity);
	if (!bReadAll
		|| OutInputs.SpringVelocity.ContainsNaN()
		|| OutInputs.SpringAcceleration.ContainsNaN()
		|| OutInputs.IntermediateVelocity.ContainsNaN()
		|| !IsFiniteQuat(OutInputs.IntermediateFacing)
		|| OutInputs.IntermediateAngularVelocity.ContainsNaN())
	{
		OutFailureReason = TEXT("missing_or_invalid_spring_property");
		return false;
	}
	OutInputs.bHasSpringState = true;
	return true;
}

FMotionWorldSmoothWalkingDiagnosticSample MotionWorld::BuildSmoothWalkingDiagnosticSample(
	const FSmoothWalkingDiagnosticInputs& Inputs)
{
	FMotionWorldSmoothWalkingDiagnosticSample Result;
	Result.AuthoritativeStateSampleSequence = Inputs.AuthoritativeStateSampleSequence;
	Result.MovementModeName = Inputs.MovementModeName;
	Result.MovementModeClass = Inputs.MovementModeClass;
	Result.FailureReason = Inputs.FailureReason;
	if (!Inputs.FailureReason.IsNone()
		|| Inputs.AuthoritativeStateSampleSequence < 0
		|| Inputs.MovementModeName.IsNone()
		|| Inputs.MovementModeClass.IsNone()
		|| !Inputs.bHasParameters
		|| !Inputs.bHasSpringState
		|| Inputs.Parameters.Num() != ParameterCount)
	{
		if (Result.FailureReason.IsNone())
		{
			Result.FailureReason = TEXT("incomplete_diagnostic_inputs");
		}
		return Result;
	}

	for (const double Parameter : Inputs.Parameters)
	{
		if (!FMath::IsFinite(Parameter))
		{
			Result.FailureReason = TEXT("non_finite_parameter");
			return Result;
		}
	}
	const bool bParameterRangesValid =
		Inputs.Parameters[0] >= 0.0
		&& Inputs.Parameters[1] >= 0.0
		&& Inputs.Parameters[2] >= 0.0
		&& Inputs.Parameters[2] <= 1.0
		&& Inputs.Parameters[3] >= 0.0
		&& Inputs.Parameters[4] >= 0.0
		&& Inputs.Parameters[5] >= 0.0
		&& Inputs.Parameters[6] >= 0.0
		&& Inputs.Parameters[6] <= 1.0
		&& Inputs.Parameters[7] >= 0.0
		&& Inputs.Parameters[7] <= 1.0
		&& Inputs.Parameters[8] >= 0.0
		&& Inputs.Parameters[9] >= 0.0
		&& Inputs.Parameters[10] >= 0.0
		&& Inputs.Parameters[11] >= 0.0
		&& Inputs.Parameters[12] >= 0.0
		&& Inputs.Parameters[13] >= 0.0;
	if (!bParameterRangesValid)
	{
		Result.FailureReason = TEXT("invalid_parameter_range");
		return Result;
	}
	if (Inputs.SpringVelocity.ContainsNaN()
		|| Inputs.SpringAcceleration.ContainsNaN()
		|| Inputs.IntermediateVelocity.ContainsNaN()
		|| !IsFiniteQuat(Inputs.IntermediateFacing)
		|| Inputs.IntermediateAngularVelocity.ContainsNaN())
	{
		Result.FailureReason = TEXT("non_finite_spring_state");
		return Result;
	}
	Result.AccelerationCmPerSecSquared = Inputs.Parameters[0];
	Result.DecelerationCmPerSecSquared = Inputs.Parameters[1];
	Result.DirectionalAccelerationFactor = Inputs.Parameters[2];
	Result.TurningStrength = Inputs.Parameters[3];
	Result.AccelerationSmoothingTimeSeconds = Inputs.Parameters[4];
	Result.DecelerationSmoothingTimeSeconds = Inputs.Parameters[5];
	Result.AccelerationSmoothingCompensation = Inputs.Parameters[6];
	Result.DecelerationSmoothingCompensation = Inputs.Parameters[7];
	Result.VelocityDeadzoneCmPerSec = Inputs.Parameters[8];
	Result.AccelerationDeadzoneCmPerSecSquared = Inputs.Parameters[9];
	Result.OutsideInfluenceSmoothingTimeSeconds = Inputs.Parameters[10];
	Result.FacingSmoothingTimeSeconds = Inputs.Parameters[11];
	Result.FacingDeadzoneDegrees = Inputs.Parameters[12];
	Result.AngularVelocityDeadzoneDegreesPerSec = Inputs.Parameters[13];
	Result.bSmoothFacingWithDoubleSpring = Inputs.bSmoothFacingWithDoubleSpring;
	Result.SpringVelocityWorldCmPerSec = Inputs.SpringVelocity;
	Result.SpringAccelerationWorldCmPerSecSquared = Inputs.SpringAcceleration;
	Result.IntermediateVelocityWorldCmPerSec = Inputs.IntermediateVelocity;
	Result.IntermediateFacingWorld = Inputs.IntermediateFacing;
	Result.IntermediateAngularVelocityWorldRadPerSec = Inputs.IntermediateAngularVelocity;
	Result.bIsValid = true;
	Result.FailureReason = NAME_None;
	return Result;
}
