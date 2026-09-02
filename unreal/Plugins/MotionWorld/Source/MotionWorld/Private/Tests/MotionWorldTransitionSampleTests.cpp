#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "MotionWorldTransitionSample.h"

#include <limits>

namespace
{
FMotionWorldStateSample MakeValidState(
	const int64 SampleSequence,
	const int32 MoverFrame,
	const double SimulationTimeSeconds,
	const double StepSeconds,
	const double FacingYawDegrees)
{
	FMotionWorldStateSample State;
	State.SampleSequence = SampleSequence;
	State.MoverStepServerFrame = MoverFrame;
	State.SimulationTimeSeconds = SimulationTimeSeconds;
	State.StepSeconds = StepSeconds;
	State.bIsValid = true;
	State.MovementMode = TEXT("Walking");
	State.FacingYawDegrees = FacingYawDegrees;
	const double YawRadians = FMath::DegreesToRadians(FacingYawDegrees);
	State.FacingUnitWorld = FVector2D(FMath::Cos(YawRadians), FMath::Sin(YawRadians));
	return State;
}

FMotionWorldNominalContextSample MakeValidContext(const int64 SampleSequence)
{
	FMotionWorldNominalContextSample Context;
	Context.bIsValid = true;
	Context.AuthoritativeStateSampleSequence = SampleSequence;
	Context.MovementModeName = TEXT("Walking");
	Context.MovementModeClass = TEXT("BP_MovementMode_Walking_C");
	Context.InputPreparation.bHasMaxMoveSpeed = true;
	Context.InputPreparation.EffectiveMaxSpeedCmPerSec = 165.0;
	Context.InputPreparation.MaxSpeedSource = EMotionWorldMaxSpeedSource::CommonLegacySettings;
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
	return Context;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMotionWorldTransitionSampleTest,
	"MotionWorld.Transition.CausalPairing",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMotionWorldTransitionSampleTest::RunTest(const FString& Parameters)
{
	MotionWorld::FTransitionSampleInputs Inputs;
	Inputs.EpisodeId = 7;
	Inputs.TransitionSequence = 12;
	Inputs.PreviousState = MakeValidState(40, 100, 1.000, 0.050, 90.0);
	Inputs.NextState = MakeValidState(41, 101, 1.050, 0.050, 45.0);
	Inputs.PreviousNominalContext = MakeValidContext(40);
	Inputs.NextNominalContext = MakeValidContext(41);
	Inputs.bAppliedInputWasVelocity = true;
	Inputs.bWasMotionWorldAutomated = true;
	Inputs.AppliedVelocityWorldCmPerSec = FVector(0.0, 200.0, 0.0);
	Inputs.bHasAppliedOrientationIntent = true;
	Inputs.AppliedOrientationIntentWorld = FVector(0.0, 1.0, 0.0);

	const FMotionWorldTransitionSample Valid =
		MotionWorld::BuildTransitionSample(Inputs);
	TestTrue(TEXT("Adjacent causal data produces a valid transition"), Valid.bIsValid);
	TestEqual(TEXT("Transition protocol is explicit"), Valid.ProtocolVersion, 4);
	TestEqual(TEXT("Episode identity is retained"), Valid.EpisodeId, int64(7));
	TestEqual(TEXT("Transition sequence is retained"), Valid.TransitionSequence, int64(12));
	TestEqual(
		TEXT("A valid transition has no rejection reason"),
		Valid.RejectionReason,
		EMotionWorldTransitionRejectionReason::None);
	TestTrue(
		TEXT("Delta time is derived from adjacent finalized state times"),
		FMath::IsNearlyEqual(Valid.DeltaTimeSeconds, 0.050, 1.e-9));
	TestTrue(
		TEXT("The applied world velocity is retained"),
		Valid.AppliedAction.VelocityWorldCmPerSec.Equals(FVector(0.0, 200.0, 0.0)));
	TestTrue(
		TEXT("World +Y is local forward in the previous yaw-90 frame"),
		Valid.AppliedAction.VelocityLocalPlanarCmPerSec.Equals(
			FVector(200.0, 0.0, 0.0),
			1.e-6));
	TestTrue(
		TEXT("The action conversion does not incorrectly use the next yaw-45 frame"),
		FMath::IsNearlyZero(Valid.AppliedAction.VelocityLocalPlanarCmPerSec.Y, 1.e-6));
	TestTrue(
		TEXT("Automation source is retained"),
		Valid.AppliedAction.bWasMotionWorldAutomated);
	TestEqual(TEXT("Orientation intent becomes a causal facing target"), Valid.AppliedAction.DesiredFacingYawDegrees, 90.0);
	TestFalse(TEXT("Nonzero orientation does not use the fallback"), Valid.AppliedAction.bUsedPreviousFacingForZeroOrientationIntent);
	TestEqual(
		TEXT("Previous hidden context remains frame-aligned"),
		Valid.PreviousNominalContext.AuthoritativeStateSampleSequence,
		int64(40));
	TestEqual(
		TEXT("Completed-step parameters come from the next finalized context"),
		Valid.ParametersObservedForCompletedStep.AccelerationCmPerSecSquared,
		Inputs.NextNominalContext.Parameters.AccelerationCmPerSecSquared);
	TestEqual(
		TEXT("Completed-step input preparation comes from the next context"),
		Valid.InputPreparationObservedForCompletedStep.EffectiveMaxSpeedCmPerSec,
		165.0);
	TestEqual(
		TEXT("Ordinary rows explicitly carry no external perturbation"),
		Valid.ExternalPerturbation.Type,
		EMotionWorldExternalPerturbationType::None);

	MotionWorld::FTransitionSampleInputs PerturbedInputs = Inputs;
	PerturbedInputs.ExternalPerturbation =
		MotionWorld::MakeAdditiveVelocityPerturbation(
			FVector(0.0, 250.0, 0.0),
			40,
			100,
			true);
	const FMotionWorldTransitionSample Perturbed =
		MotionWorld::BuildTransitionSample(PerturbedInputs);
	TestTrue(TEXT("A source-aligned velocity kick is retained"), Perturbed.bIsValid);
	TestEqual(
		TEXT("The velocity-kick type remains distinct from the planner action"),
		Perturbed.ExternalPerturbation.Type,
		EMotionWorldExternalPerturbationType::AdditiveVelocity);
	TestTrue(
		TEXT("The requested world-space kick is exact"),
		Perturbed.ExternalPerturbation.RequestedVelocityDeltaWorldCmPerSec.Equals(
			FVector(0.0, 250.0, 0.0)));

	PerturbedInputs.ExternalPerturbation.QueuedAfterStateSampleSequence = 39;
	TestEqual(
		TEXT("A kick attached to the wrong state is rejected"),
		MotionWorld::BuildTransitionSample(PerturbedInputs).RejectionReason,
		EMotionWorldTransitionRejectionReason::ExternalPerturbationStateMismatch);
	PerturbedInputs.ExternalPerturbation.QueuedAfterStateSampleSequence = 40;
	PerturbedInputs.ExternalPerturbation.QueuedAfterMoverStepServerFrame = 99;
	TestEqual(
		TEXT("A kick attached to the wrong Mover frame is rejected"),
		MotionWorld::BuildTransitionSample(PerturbedInputs).RejectionReason,
		EMotionWorldTransitionRejectionReason::ExternalPerturbationStateMismatch);
	PerturbedInputs.ExternalPerturbation =
		MotionWorld::MakeAdditiveVelocityPerturbation(
			FVector(
				std::numeric_limits<double>::quiet_NaN(),
				0.0,
				0.0),
			40,
			100,
			true);
	TestEqual(
		TEXT("An invalid kick fails the whole causal row closed"),
		MotionWorld::BuildTransitionSample(PerturbedInputs).RejectionReason,
		EMotionWorldTransitionRejectionReason::InvalidExternalPerturbation);

	MotionWorld::FTransitionSampleInputs Failure = Inputs;
	Failure.EpisodeId = -1;
	TestEqual(
		TEXT("Missing episode identity is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::InvalidEpisodeId);

	Failure = Inputs;
	Failure.TransitionSequence = -1;
	TestEqual(
		TEXT("Missing transition sequence is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::InvalidTransitionSequence);

	Failure = Inputs;
	Failure.bAppliedInputWasVelocity = false;
	const FMotionWorldTransitionSample UnsupportedAction =
		MotionWorld::BuildTransitionSample(Failure);
	TestEqual(
		TEXT("Directional intent is rejected from the desired-velocity dataset"),
		UnsupportedAction.RejectionReason,
		EMotionWorldTransitionRejectionReason::UnsupportedActionType);

	Failure = Inputs;
	Failure.AppliedVelocityWorldCmPerSec.X = std::numeric_limits<double>::quiet_NaN();
	const FMotionWorldTransitionSample NonFiniteAction =
		MotionWorld::BuildTransitionSample(Failure);
	TestEqual(
		TEXT("Non-finite actions are rejected"),
		NonFiniteAction.RejectionReason,
		EMotionWorldTransitionRejectionReason::NonFiniteAction);
	TestEqual(
		TEXT("Rejected actions fail closed to zero"),
		NonFiniteAction.AppliedAction.VelocityWorldCmPerSec,
		FVector::ZeroVector);

	Failure = Inputs;
	Failure.AppliedVelocityWorldCmPerSec.Y =
		std::numeric_limits<double>::infinity();
	TestEqual(
		TEXT("Infinite actions are rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NonFiniteAction);

	Failure = Inputs;
	Failure.AppliedVelocityWorldCmPerSec.Z = 25.0;
	TestEqual(
		TEXT("Vertical desired velocity is not silently relabeled as planar"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NonPlanarAction);

	Failure = Inputs;
	Failure.bHasAppliedOrientationIntent = false;
	TestEqual(
		TEXT("Missing facing input is rejected rather than hidden"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::MissingOrientationIntent);

	Failure = Inputs;
	Failure.AppliedOrientationIntentWorld.X = std::numeric_limits<double>::quiet_NaN();
	TestEqual(
		TEXT("Non-finite facing input is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NonFiniteOrientationIntent);

	Failure = Inputs;
	Failure.AppliedOrientationIntentWorld = FVector::ZeroVector;
	const FMotionWorldTransitionSample ZeroOrientation =
		MotionWorld::BuildTransitionSample(Failure);
	TestTrue(TEXT("Zero orientation uses Simple Walking's valid fallback"), ZeroOrientation.bIsValid);
	TestTrue(TEXT("Zero orientation marks the fallback"), ZeroOrientation.AppliedAction.bUsedPreviousFacingForZeroOrientationIntent);
	TestEqual(TEXT("Fallback targets previous facing"), ZeroOrientation.AppliedAction.DesiredFacingYawDegrees, 90.0);

	Failure = Inputs;
	Failure.NextState.bIsResimulation = true;
	TestEqual(
		TEXT("Resimulation is explicit rather than accepted as fresh causal data"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::Resimulation);

	Failure = Inputs;
	Failure.NextState.SampleSequence = 42;
	Failure.NextNominalContext.AuthoritativeStateSampleSequence = 42;
	TestEqual(
		TEXT("A skipped state sample is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NonContiguousStateSequence);

	Failure = Inputs;
	Failure.NextState.MoverStepServerFrame = 102;
	TestEqual(
		TEXT("A skipped available Mover frame is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NonContiguousMoverFrame);

	Failure = Inputs;
	Failure.NextState.MoverStepServerFrame = INDEX_NONE;
	TestEqual(
		TEXT("Changing Mover frame availability inside an episode is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NonContiguousMoverFrame);

	Failure = Inputs;
	Failure.PreviousState.MoverStepServerFrame = -2;
	TestEqual(
		TEXT("An invalid negative Mover frame is rejected as invalid state"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::InvalidPreviousState);

	Failure = Inputs;
	Failure.NextState.SimulationTimeSeconds = 1.000;
	TestEqual(
		TEXT("Repeated simulation time is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NonIncreasingSimulationTime);

	Failure = Inputs;
	Failure.NextState.SimulationTimeSeconds = 1.060;
	TestEqual(
		TEXT("State-time difference must agree with the finalized step duration"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::TimestepMismatch);

	Failure = Inputs;
	Failure.NextState.ProtocolVersion = 2;
	TestEqual(
		TEXT("Unknown state schemas are rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::UnsupportedStateProtocol);

	Failure = Inputs;
	Failure.PreviousNominalContext.bIsValid = false;
	TestEqual(
		TEXT("Invalid previous hidden context is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::InvalidPreviousNominalContext);

	Failure = Inputs;
	Failure.NextNominalContext.ProtocolVersion = 3;
	TestEqual(
		TEXT("Unknown nominal-context schemas are rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::UnsupportedNominalContextProtocol);

	Failure = Inputs;
	Failure.NextNominalContext.AuthoritativeStateSampleSequence = 40;
	TestEqual(
		TEXT("Context from the wrong finalized frame is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::NominalContextStateMismatch);

	Failure = Inputs;
	Failure.NextState.bIsValid = false;
	TestEqual(
		TEXT("Invalid next state is rejected"),
		MotionWorld::BuildTransitionSample(Failure).RejectionReason,
		EMotionWorldTransitionRejectionReason::InvalidNextState);

	(void)Parameters;
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
